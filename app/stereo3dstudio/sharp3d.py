"""Apple SHARP as an experimental 3D method: picture -> 3D Gaussian scene -> real left/right camera views.

Instead of shifting pixels by a depth map (iw3's methods), SHARP predicts a small 3D scene of Gaussian splats
from the picture (about a million of them, in two layers, so there is something behind foreground objects),
and two virtual cameras film it. Edges and the areas revealed behind objects come from real geometry.

SHARP's code is bundled unmodified in thirdparty/sharp (Apple sample code license). Its weights are downloaded
from Apple in the Models window (Apple Machine Learning Research Model License — research use only).
Videos are converted frame by frame (each frame is its own 3D scene), with the depth range smoothed between frames.
SHARP's own renderer needs gsplat, which compiles CUDA code on the user's machine; Stereo3D Studio renders with
the pure-PyTorch rasterizer below instead, so nothing has to be compiled.

The stereo cameras follow the app's "3D strength" and "Screen plane" exactly as iw3 does: the disparity between
the eyes spans divergence% of the long image side from the farthest to the nearest object, and the screen plane
sits at `convergence` (0 = everything in front of the screen, 1 = everything behind it).
"""
import math
import sys
import types
from os import path

import torch
from types import SimpleNamespace
import torch.nn.functional as F

from iw3.hub_dir import HUB_MODEL_DIR

MODEL_URL = "https://ml-site.cdn-apple.com/models/sharp/sharp_2572gikvuh.pt"
MODEL_PAGE = "https://huggingface.co/apple/Sharp"
MODEL_FILE = path.join(HUB_MODEL_DIR, "checkpoints", "sharp_2572gikvuh.pt")
INTERNAL = 1536                     # SHARP's working resolution (square)
DEFAULT_FOCAL_MM = 30.0             # SHARP's assumption when a picture has no focal length (35 mm equivalent)
METHOD = "sharp"
SUPPORTED_LAYOUTS = ("Half SBS", "Full SBS", "Half Top", "Full Top", "Cross", "Red-Cyan", "Anaglyph",
                     "RGB + Depth", "Half RGB + Depth", "Depth map only")


def is_ready():
    return path.exists(MODEL_FILE) and path.getsize(MODEL_FILE) > 1_000_000


def layout_supported(layout):
    return layout.startswith(SUPPORTED_LAYOUTS)


# ======================================================================================= model
_MODEL = {"net": None, "device": None}


def _no_ply():
    """SHARP's gaussians module imports plyfile (GPL-3.0) only to save .ply files, which Stereo3D Studio never
    does. A stand-in keeps that package out of the app entirely."""
    if "plyfile" in sys.modules:
        return
    stub = types.ModuleType("plyfile")

    def _unavailable(*_a, **_k):
        raise RuntimeError("Saving .ply files isn't available in Stereo3D Studio.")
    stub.PlyData = stub.PlyElement = _unavailable
    sys.modules["plyfile"] = stub


_no_ply()


def load(device, state_dict=None):
    """Load (once) and return the SHARP predictor. state_dict is for tests (random weights)."""
    if _MODEL["net"] is not None and _MODEL["device"] == device:
        return _MODEL["net"]
    from sharp.models import PredictorParams, create_predictor
    net = create_predictor(PredictorParams())
    if state_dict is None:
        if not is_ready():
            raise RuntimeError("SHARP's model isn't downloaded yet — open Models, select “Apple SHARP” and download it.")
        try:
            state_dict = torch.load(MODEL_FILE, map_location="cpu", weights_only=True, mmap=True)
        except RuntimeError:
            state_dict = torch.load(MODEL_FILE, map_location="cpu", weights_only=True)
    if state_dict != "random":
        net.load_state_dict(state_dict)
    net.eval().to(device)
    if device.type == "cuda":
        torch.backends.cudnn.benchmark = True        # SHARP always runs at 1536x1536: let cuDNN pick fast kernels
    _MODEL.update(net=net, device=device)
    return net


def unload():
    _MODEL.update(net=None, device=None)
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def focal_px(width, height, focal_mm=DEFAULT_FOCAL_MM):
    return focal_mm * math.sqrt(width ** 2 + height ** 2) / math.sqrt(36 ** 2 + 24 ** 2)


@torch.inference_mode()
def predict(net, image, f_px, half=False):
    """image: (3, H, W) float 0..1 on the model's device -> Gaussians3D in camera space (OpenCV axes).
    half=True runs the network in FP16 on the GPU (about twice as fast; the ComfyUI SHARP nodes default to it)."""
    from sharp.utils.gaussians import Gaussians3D, get_unprojection_matrix
    _, H, W = image.shape
    dev = image.device
    x = F.interpolate(image[None].float(), size=(INTERNAL, INTERNAL), mode="bilinear", align_corners=True)
    with torch.autocast("cuda", dtype=torch.float16, enabled=bool(half) and dev.type == "cuda"):
        g_ndc = net(x, torch.tensor([f_px / W], device=dev, dtype=torch.float32))
    g_ndc = Gaussians3D(*(t.float() for t in g_ndc))
    K = torch.tensor([[f_px, 0, W / 2, 0], [0, f_px, H / 2, 0], [0, 0, 1, 0], [0, 0, 0, 1]],
                     device=dev, dtype=torch.float32)
    K[0] *= INTERNAL / W
    K[1] *= INTERNAL / H
    # Same result as sharp's unproject_gaussians, but the splat shapes stay as covariance matrices on the GPU.
    # (unproject_gaussians decomposes every covariance with an SVD on the CPU in float64 — several seconds per frame
    # for ~1.2M splats — only for the renderer to rebuild the same matrices right away.)
    M = get_unprojection_matrix(torch.eye(4, device=dev), K, (INTERNAL, INTERNAL))[:3]
    A, o = M[:3, :3], M[:3, 3]
    cov = A @ _covariances(g_ndc.quaternions[0], g_ndc.singular_values[0]) @ A.T
    return SimpleNamespace(mean_vectors=g_ndc.mean_vectors @ A.T + o, covariances=cov[None],
                           colors=g_ndc.colors, opacities=g_ndc.opacities)


# ======================================================================================= renderer
def _covariances(quats, scales):
    q = quats / quats.norm(dim=-1, keepdim=True).clamp(min=1e-12)
    w, x, y, z = q.unbind(-1)
    R = torch.stack([
        1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y),
        2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x),
        2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y),
    ], dim=-1).reshape(*q.shape[:-1], 3, 3)
    S = scales.square()
    return (R * S[..., None, :]) @ R.transpose(-1, -2)


_RADII = (1, 2, 3, 4, 6, 8, 12, 16, 24, 32)        # footprint half-sizes in pixels (x and y bucketed separately)


@torch.inference_mode()
def rasterize(means, cov3, colors, opacities, fx, fy, cx, cy, W, H, eps2d=0.3, band=64):
    """Front-to-back alpha compositing of 3D Gaussians (EWA splatting), all in PyTorch.

    The image is rendered in horizontal bands so memory stays small and fixed whatever the scene (a whole frame
    at once can need many GB, and on Windows overflowing the graphics card makes it fall back to system RAM,
    which is extremely slow). Each splat's footprint is cut where it drops below 1/255 for its own opacity, with
    separate widths and heights, so thin or faint splats cost little.

    means (N,3), cov3 (N,3,3), colors (N,3), opacities (N,) in camera space; returns
    color (3,H,W), alpha (1,H,W), depth (1,H,W)."""
    dev = means.device
    z = means[:, 2]
    keep = (z > 1e-2) & (opacities > 1 / 255)
    means, cov3, colors, opacities, z = means[keep], cov3[keep], colors[keep], opacities[keep], z[keep]
    x, y = means[:, 0], means[:, 1]
    u = fx * x / z + cx
    v = fy * y / z + cy
    zero = torch.zeros_like(z)
    J = torch.stack([torch.stack([fx / z, zero, -fx * x / z ** 2], -1),
                     torch.stack([zero, fy / z, -fy * y / z ** 2], -1)], -2)          # (N,2,3)
    cov2 = J @ cov3 @ J.transpose(-1, -2)
    del J
    a = cov2[:, 0, 0] + eps2d
    b = cov2[:, 0, 1]
    c = cov2[:, 1, 1] + eps2d
    del cov2
    det = (a * c - b * b).clamp(min=1e-12)
    ia, ib, ic = c / det, -b / det, a / det                                             # conic (inverse cov)
    k = torch.sqrt(2 * torch.log((255 * opacities).clamp(min=1.0)))                     # alpha >= 1/255 inside
    rx = torch.ceil(k * torch.sqrt(a)).clamp(min=1, max=_RADII[-1])
    ry = torch.ceil(k * torch.sqrt(c)).clamp(min=1, max=_RADII[-1])
    onscreen = (u + rx > 0) & (u - rx < W) & (v + ry > 0) & (v - ry < H) & (k > 0)
    order = torch.argsort(z[onscreen])                                                  # front to back
    idx = torch.nonzero(onscreen).squeeze(1)[order]
    del order, onscreen
    n_vis = len(idx)
    rank = torch.empty(len(z), dtype=torch.long, device=dev)
    rank[idx] = torch.arange(n_vis, device=dev)
    radii = torch.tensor(_RADII, device=dev, dtype=rx.dtype)
    nb = len(_RADII)
    bucket = torch.bucketize(rx, radii) * nb + torch.bucketize(ry, radii)              # (x size, y size) bucket
    ylo, yhi = v - ry, v + ry

    color = torch.zeros(3, H * W, device=dev)
    acc = torch.zeros(H * W, device=dev)
    dep = torch.zeros(H * W, device=dev)
    for y0 in range(0, H, band):
        y1 = min(H, y0 + band)
        sel_all = idx[(yhi[idx] >= y0) & (ylo[idx] < y1)]
        if not len(sel_all):
            continue
        pix_l, rank_l, alpha_l = [], [], []
        bk = bucket[sel_all]
        for key in torch.unique(bk).tolist():
            sel = sel_all[bk == key]
            Rx, Ry = _RADII[key // nb], _RADII[key % nb]
            ox_r = torch.arange(-Rx, Rx + 1, device=dev)
            oy_r = torch.arange(-Ry, Ry + 1, device=dev)
            oy, ox = torch.meshgrid(oy_r, ox_r, indexing="ij")
            ox, oy = ox.reshape(-1), oy.reshape(-1)
            step = max(1, 1_048_576 // len(ox))
            for s in range(0, len(sel), step):
                g = sel[s:s + step]
                px = torch.floor(u[g])[:, None] + ox[None]
                py = torch.floor(v[g])[:, None] + oy[None]
                m = (px >= 0) & (px < W) & (py >= y0) & (py < y1)
                dx = px + 0.5 - u[g][:, None]
                dy = py + 0.5 - v[g][:, None]
                power = -0.5 * (ia[g][:, None] * dx * dx + ic[g][:, None] * dy * dy) - ib[g][:, None] * dx * dy
                alpha = (opacities[g][:, None] * torch.exp(power.clamp(max=0))).clamp(max=0.99)
                m &= alpha >= 1 / 255
                if not m.any():
                    continue
                gg = g[:, None].expand_as(m)[m]
                pix_l.append(((py[m] - y0) * W + px[m]).long())
                rank_l.append(rank[gg])
                alpha_l.append(alpha[m])
        if not pix_l:
            continue
        pix = torch.cat(pix_l)
        rk = torch.cat(rank_l)
        al = torch.cat(alpha_l)
        del pix_l, rank_l, alpha_l
        key = pix * (n_vis + 1) + rk                                                    # pixel, then depth order
        key, perm = torch.sort(key)
        del key
        pix, rk, al = pix[perm], rk[perm], al[perm]
        del perm
        lg = torch.log1p(-al)
        cs = torch.cumsum(lg, 0) - lg                                                   # sum before each fragment
        start = torch.ones_like(pix, dtype=torch.bool)
        start[1:] = pix[1:] != pix[:-1]
        seg = torch.cumsum(start.long(), 0) - 1
        T = torch.exp(cs - cs[start][seg])                                              # transmittance before frag
        del cs, lg, seg, start
        w = torch.where(T > 1e-4, al * T, torch.zeros_like(al))
        del T, al
        gi = idx[rk]
        off = y0 * W
        color[:, off:off + (y1 - y0) * W].index_add_(1, pix, colors[gi].T * w)
        acc[off:off + (y1 - y0) * W].index_add_(0, pix, w)
        dep[off:off + (y1 - y0) * W].index_add_(0, pix, w * z[gi])
        del pix, rk, w, gi
    return color.view(3, H, W), acc.view(1, H, W), dep.view(1, H, W)


# ======================================================================================= stereo
def stereo_params(gaussians, f_px, W, H, divergence, convergence, smooth=None, decay=0.75):
    """(baseline, zero-parallax inverse depth, near/far inverse depth) matching iw3's 3D strength / screen plane.

    smooth: a dict kept between video frames. SHARP sees every frame on its own, so the scene's depth range jumps
    a little from frame to frame; smoothing it (like iw3's "smooth depth between frames") keeps the 3D strength
    and screen plane steady. A big jump (a scene cut) restarts the smoothing."""
    z = gaussians.mean_vectors[0, :, 2]
    op = gaussians.opacities[0]
    zz = z[(op > 0.5) & (z > 1e-2)]
    if len(zz) < 100:
        zz = z[z > 1e-2]
    d = 1.0 / zz
    if len(d) > 2_000_000:
        d = d[torch.randperm(len(d), device=d.device)[:2_000_000]]
    d_far, d_near = torch.quantile(d.float(), torch.tensor([0.02, 0.98], device=d.device)).tolist()
    if smooth is not None:
        prev = smooth.get("range")
        if prev is not None:
            p_far, p_near = prev
            p_span, r_span = max(p_near - p_far, 1e-6), max(d_near - d_far, 1e-6)
            if 1 / 3 < r_span / p_span < 3 and abs(d_far - p_far) < p_span:          # same shot: smooth
                d_far = decay * p_far + (1 - decay) * d_far
                d_near = decay * p_near + (1 - decay) * d_near
        smooth["range"] = (d_far, d_near)
    span = max(d_near - d_far, 1e-6)
    disparity_range = divergence * 0.01 * max(W, H)                  # pixels between eyes, far -> near
    baseline = disparity_range / (f_px * span)
    d0 = d_far + convergence * span
    return baseline, d0, d_near, d_far


def _srgb(lin):
    from sharp.utils.color_space import linearRGB2sRGB
    return linearRGB2sRGB(lin.clamp(0, 1)).clamp(0, 1)


@torch.inference_mode()
def render_views(gaussians, f_px, W, H, divergence=2.0, convergence=0.5, background=None, need_depth=False,
                 smooth=None, decay=0.75, eye_size=None, need_eyes=True):
    """Left and right eye images 0..1 sRGB; optional center-view disparity map (1,h,w) 0..1 (near = 1).

    W, H: the picture's size (3D strength is measured in it). eye_size=(w, h) renders each eye directly at another
    size — e.g. half width for Half SBS, or a smaller render that is scaled up afterwards — which is much faster
    than rendering full size and shrinking. smooth/decay: see stereo_params (video)."""
    means = gaussians.mean_vectors[0]
    cov3 = (gaussians.covariances[0] if hasattr(gaussians, "covariances")
            else _covariances(gaussians.quaternions[0], gaussians.singular_values[0]))
    colors = gaussians.colors[0]
    opac = gaussians.opacities[0]
    baseline, d0, d_near, d_far = stereo_params(gaussians, f_px, W, H, divergence, convergence, smooth, decay)
    ew, eh = eye_size or (W, H)
    sx, sy = ew / W, eh / H
    fx, fy = f_px * sx, f_px * sy
    cx, cy = ew / 2, eh / 2
    if background is not None and tuple(background.shape[-2:]) != (eh, ew):
        background = F.interpolate(background[None], size=(eh, ew), mode="bilinear", antialias=True,
                                   align_corners=False)[0]
    eyes = [None, None]
    for i, sign in enumerate((-1.0, 1.0) if need_eyes else ()):       # left eye at -b/2, right eye at +b/2
        t = torch.tensor([-sign * baseline / 2, 0.0, 0.0], device=means.device)
        # parallel off-axis cameras: shift the principal point so depth d0 has zero parallax
        cxe = cx + sign * fx * baseline / 2 * d0
        col, acc, _ = rasterize(means + t, cov3, colors, opac, fx, fy, cxe, cy, ew, eh)
        img = _srgb(col)
        if background is not None:                                   # fill any uncovered pixels
            img = img + (1 - acc.clamp(0, 1)) * background
        eyes[i] = img.clamp(0, 1)
        del col, acc
    depth = None
    if need_depth:
        _, acc, dep = rasterize(means, cov3, colors, opac, fx, fy, cx, cy, ew, eh)
        inv = acc / dep.clamp(min=1e-6)
        depth = ((inv - d_far) / max(d_near - d_far, 1e-6)).clamp(0, 1)
        depth = torch.where(acc > 0.05, depth, torch.zeros_like(depth))
    return eyes[0], eyes[1], depth


# ======================================================================================= layouts
def compose(layout, left, right, depth=None, image=None):
    """Arrange the eyes like iw3's layouts. Tensors (3,H,W) 0..1. Returns (3,h,w)."""
    _, H, W = left.shape
    half_w = lambda t: F.interpolate(t[None], size=(H, W // 2), mode="bilinear", antialias=True, align_corners=False)[0]
    half_h = lambda t: F.interpolate(t[None], size=(H // 2, W), mode="bilinear", antialias=True, align_corners=False)[0]
    if layout.startswith("Half SBS"):
        return torch.cat([half_w(left), half_w(right)], dim=2)
    if layout.startswith("Full SBS"):
        return torch.cat([left, right], dim=2)
    if layout.startswith("Cross"):
        return torch.cat([right, left], dim=2)
    if layout.startswith("Half Top"):
        return torch.cat([half_h(left), half_h(right)], dim=1)
    if layout.startswith("Full Top"):
        return torch.cat([left, right], dim=1)
    if layout.startswith(("Red-Cyan", "Anaglyph")):
        from iw3.anaglyph import apply_anaglyph_redcyan
        return apply_anaglyph_redcyan(left[None], right[None], "dubois")[0]
    d3 = depth.expand(3, -1, -1)
    if layout.startswith("Depth map only"):
        return d3
    if layout.startswith("Half RGB + Depth"):
        return torch.cat([half_w(image), half_w(d3)], dim=2)
    return torch.cat([image, d3], dim=2)                             # RGB + Depth


def pad_16x9(t, new_w=None):
    """Black side bars so a narrower-than-16:9 eye becomes 16:9 (same as the video fix). new_w: target width
    (for eyes rendered at half width)."""
    _, H, W = t.shape
    if new_w is None:
        if W / H >= 16 / 9 - 0.02:
            return t
        new_w = int(round(H * 16 / 9))
    if new_w <= W:
        return t
    left = (new_w - W) // 2
    return F.pad(t, (left, new_w - W - left, 0, 0))
