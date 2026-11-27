"""Apple SHARP as an experimental 3D method: picture -> 3D Gaussian scene -> real left/right camera views.

Instead of shifting pixels by a depth map (iw3's methods), SHARP predicts a small 3D scene of Gaussian splats
from the picture (about a million of them, in two layers, so there is something behind foreground objects),
and two virtual cameras film it. Edges and the areas revealed behind objects come from real geometry.

SHARP's code is bundled unmodified in thirdparty/sharp (Apple sample code license). Its weights are downloaded
from Apple in the Models window (Apple Machine Learning Research Model License — research use only).
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
    _MODEL.update(net=net, device=device)
    return net


def unload():
    _MODEL.update(net=None, device=None)
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def focal_px(width, height, focal_mm=DEFAULT_FOCAL_MM):
    return focal_mm * math.sqrt(width ** 2 + height ** 2) / math.sqrt(36 ** 2 + 24 ** 2)


@torch.inference_mode()
def predict(net, image, f_px):
    """image: (3, H, W) float 0..1 on the model's device -> Gaussians3D in camera space (OpenCV axes)."""
    from sharp.utils.gaussians import unproject_gaussians
    _, H, W = image.shape
    dev = image.device
    x = F.interpolate(image[None].float(), size=(INTERNAL, INTERNAL), mode="bilinear", align_corners=True)
    g_ndc = net(x, torch.tensor([f_px / W], device=dev, dtype=torch.float32))
    K = torch.tensor([[f_px, 0, W / 2, 0], [0, f_px, H / 2, 0], [0, 0, 1, 0], [0, 0, 0, 1]],
                     device=dev, dtype=torch.float32)
    K[0] *= INTERNAL / W
    K[1] *= INTERNAL / H
    return unproject_gaussians(g_ndc, torch.eye(4, device=dev), K, (INTERNAL, INTERNAL))


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


_RADII = (1, 2, 3, 4, 6, 8, 12, 16)


@torch.inference_mode()
def rasterize(means, cov3, colors, opacities, fx, fy, cx, cy, W, H, eps2d=0.3, chunk=262144):
    """Front-to-back alpha compositing of 3D Gaussians (EWA splatting), all in PyTorch.

    means (N,3), cov3 (N,3,3), colors (N,3), opacities (N,) in camera space; returns
    color (3,H,W), alpha (1,H,W), depth (1,H,W)."""
    dev = means.device
    z = means[:, 2]
    keep = z > 1e-2
    means, cov3, colors, opacities, z = means[keep], cov3[keep], colors[keep], opacities[keep], z[keep]
    x, y = means[:, 0], means[:, 1]
    u = fx * x / z + cx
    v = fy * y / z + cy
    zero = torch.zeros_like(z)
    J = torch.stack([torch.stack([fx / z, zero, -fx * x / z ** 2], -1),
                     torch.stack([zero, fy / z, -fy * y / z ** 2], -1)], -2)          # (N,2,3)
    cov2 = J @ cov3 @ J.transpose(-1, -2)
    a = cov2[:, 0, 0] + eps2d
    b = cov2[:, 0, 1]
    c = cov2[:, 1, 1] + eps2d
    det = (a * c - b * b).clamp(min=1e-12)
    mid = 0.5 * (a + c)
    lam = mid + torch.sqrt((mid * mid - det).clamp(min=0.01))
    radius = torch.ceil(3.0 * torch.sqrt(lam))
    ia, ib, ic = c / det, -b / det, a / det                                             # conic (inverse cov)
    onscreen = (u + radius > 0) & (u - radius < W) & (v + radius > 0) & (v - radius < H) & (opacities > 1 / 255)
    order = torch.argsort(z[onscreen])                                                  # front to back
    idx = torch.nonzero(onscreen).squeeze(1)[order]
    rank = torch.empty(len(z), dtype=torch.long, device=dev)
    rank[idx] = torch.arange(len(idx), device=dev)

    pix_l, rank_l, alpha_l = [], [], []
    bucket = torch.bucketize(radius[idx].clamp(max=_RADII[-1]), torch.tensor(_RADII, device=dev, dtype=radius.dtype))
    for bi, R in enumerate(_RADII):
        sel = idx[bucket == bi]
        if not len(sel):
            continue
        off = torch.arange(-R, R + 1, device=dev)
        oy, ox = torch.meshgrid(off, off, indexing="ij")
        ox, oy = ox.reshape(-1), oy.reshape(-1)
        for s in range(0, len(sel), max(1, chunk // len(ox))):
            g = sel[s:s + max(1, chunk // len(ox))]
            px = torch.floor(u[g])[:, None] + ox[None]
            py = torch.floor(v[g])[:, None] + oy[None]
            dx = px + 0.5 - u[g][:, None]
            dy = py + 0.5 - v[g][:, None]
            power = -0.5 * (ia[g][:, None] * dx * dx + ic[g][:, None] * dy * dy) - ib[g][:, None] * dx * dy
            alpha = (opacities[g][:, None] * torch.exp(power.clamp(max=0))).clamp(max=0.99)
            m = (alpha >= 1 / 255) & (px >= 0) & (px < W) & (py >= 0) & (py < H)
            if not m.any():
                continue
            gg = g[:, None].expand_as(m)[m]
            pix_l.append((py[m] * W + px[m]).long())
            rank_l.append(rank[gg])
            alpha_l.append(alpha[m])
    color = torch.zeros(3, H * W, device=dev)
    acc = torch.zeros(H * W, device=dev)
    dep = torch.zeros(H * W, device=dev)
    if not pix_l:
        return color.view(3, H, W), acc.view(1, H, W), dep.view(1, H, W)
    pix = torch.cat(pix_l)
    rk = torch.cat(rank_l)
    al = torch.cat(alpha_l)
    del pix_l, rank_l, alpha_l
    key = pix * (len(idx) + 1) + rk                                                     # pixel, then depth order
    key, perm = torch.sort(key)
    pix, rk, al = pix[perm], rk[perm], al[perm]
    lg = torch.log1p(-al)
    cs = torch.cumsum(lg, 0)
    start = torch.ones_like(pix, dtype=torch.bool)
    start[1:] = pix[1:] != pix[:-1]
    seg = torch.cumsum(start.long(), 0) - 1
    base = (cs - lg)[start]                                                              # cum sum before segment
    T = torch.exp(cs - lg - base[seg])                                                   # transmittance before frag
    w = al * T
    w = torch.where(T > 1e-4, w, torch.zeros_like(w))
    g = idx[rk]
    color.index_add_(1, pix, (colors[g].T * w))
    acc.index_add_(0, pix, w)
    dep.index_add_(0, pix, w * z[g])
    return color.view(3, H, W), acc.view(1, H, W), dep.view(1, H, W)


# ======================================================================================= stereo
def stereo_params(gaussians, f_px, W, H, divergence, convergence):
    """(baseline, zero-parallax inverse depth, near/far inverse depth) matching iw3's 3D strength / screen plane."""
    z = gaussians.mean_vectors[0, :, 2]
    op = gaussians.opacities[0]
    zz = z[(op > 0.5) & (z > 1e-2)]
    if len(zz) < 100:
        zz = z[z > 1e-2]
    d = 1.0 / zz
    if len(d) > 2_000_000:
        d = d[torch.randperm(len(d), device=d.device)[:2_000_000]]
    d_far, d_near = torch.quantile(d.float(), torch.tensor([0.02, 0.98], device=d.device)).tolist()
    span = max(d_near - d_far, 1e-6)
    disparity_range = divergence * 0.01 * max(W, H)                  # pixels between eyes, far -> near
    baseline = disparity_range / (f_px * span)
    d0 = d_far + convergence * span
    return baseline, d0, d_near, d_far


def _srgb(lin):
    from sharp.utils.color_space import linearRGB2sRGB
    return linearRGB2sRGB(lin.clamp(0, 1)).clamp(0, 1)


@torch.inference_mode()
def render_views(gaussians, f_px, W, H, divergence=2.0, convergence=0.5, background=None, need_depth=False):
    """Left and right eye images (3,H,W) 0..1 sRGB; optional center-view disparity map (1,H,W) 0..1 (near = 1)."""
    means = gaussians.mean_vectors[0]
    cov3 = _covariances(gaussians.quaternions[0], gaussians.singular_values[0])
    colors = gaussians.colors[0]
    opac = gaussians.opacities[0]
    baseline, d0, d_near, d_far = stereo_params(gaussians, f_px, W, H, divergence, convergence)
    cx, cy = W / 2, H / 2
    eyes = []
    for sign in (-1.0, 1.0):                                         # left eye at -b/2, right eye at +b/2
        t = torch.tensor([-sign * baseline / 2, 0.0, 0.0], device=means.device)
        # parallel off-axis cameras: shift the principal point so depth d0 has zero parallax
        cxe = cx + sign * f_px * baseline / 2 * d0
        col, acc, _ = rasterize(means + t, cov3, colors, opac, f_px, f_px, cxe, cy, W, H)
        img = _srgb(col)
        if background is not None:                                   # fill any uncovered pixels
            img = img + (1 - acc.clamp(0, 1)) * background
        eyes.append(img.clamp(0, 1))
    depth = None
    if need_depth:
        _, acc, dep = rasterize(means, cov3, colors, opac, f_px, f_px, cx, cy, W, H)
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


def pad_16x9(t):
    """Black side bars so a narrower-than-16:9 eye becomes 16:9 (same as the video fix)."""
    _, H, W = t.shape
    if W / H >= 16 / 9 - 0.02:
        return t
    new_w = int(round(H * 16 / 9))
    left = (new_w - W) // 2
    return F.pad(t, (left, new_w - W - left, 0, 0))
