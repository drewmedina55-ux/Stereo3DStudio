"""Apple Depth Pro 2 as an iw3 depth model.

The Depth Pro 2 code is bundled unmodified in thirdparty/depth_pro_2. The weights are NOT bundled: the
model manager downloads them from Apple after the user accepts the Apple Machine Learning Research
Model License (research use only).

Videos: frames go through Depth Pro 2's own key-value cache ("unbuffered" streaming), so each frame
also attends the frames before it — that is what makes its depth temporally stable. The cache is
cleared at every new video and scene cut (iw3 calls reset()). Single images are predicted on their own.

Output is focal-normalised inverse depth (disparity), like iw3's Depth Pro v1 integration.
"""
from os import path

import torch
import torch.nn.functional as F
from PIL import Image
from torchvision.transforms import functional as TF

from iw3.base_depth_model import BaseDepthModel
from iw3.dilation import dilate_edge, edge_dilation_is_enabled
from iw3.hub_dir import HUB_MODEL_DIR

CDN = "https://ml-site.cdn-apple.com/models/depth-pro-2/"
# model_type -> (preset, checkpoint file name on Apple's CDN)
VARIANTS = {
    "DepthPro2_S": ("depthpro2-s", "depthpro2-s-bgcc6f8bg3.pt"),
    "DepthPro2_B": ("depthpro2-b", "depthpro2-b-xb7m9egktw.pt"),
    "DepthPro2_L": ("depthpro2-l", "depthpro2-l-tegstu7fim.pt"),
    "DepthPro2_H": ("depthpro2-h", "depthpro2-h-eivtm5w7m5.pt"),
}
MODEL_FILES = {k: path.join(HUB_MODEL_DIR, "checkpoints", f) for k, (_, f) in VARIANTS.items()}
DOWNLOAD_URLS = {k: CDN + f for k, (_, f) in VARIANTS.items()}

DEFAULT_SHORT_SIDE = 576          # depth is computed at this height (16:9 -> 1024x576), then upscaled
CACHE_WINDOW = 16                 # frames attended together (Depth Pro 2's default window)
IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


def _normalize(x):
    mean = torch.tensor(IMAGENET_MEAN, dtype=x.dtype, device=x.device).view(1, 3, 1, 1)
    std = torch.tensor(IMAGENET_STD, dtype=x.dtype, device=x.device).view(1, 3, 1, 1)
    return (x - mean) / std


class DepthPro2Model(BaseDepthModel):
    order: int = 21

    def __init__(self, model_type):
        super().__init__(model_type)
        self.short_side = DEFAULT_SHORT_SIDE
        self._caches = [None, None]       # [normal, flipped (TTA)]
        self._cache_shape = None

    # ------------------------------------------------------------------ loading
    def load_model(self, model_type, resolution=None, device=None):
        from depth_pro_2.model import PRESETS, DepthPro2

        preset, _ = VARIANTS[model_type]
        cfg = PRESETS[preset]
        if resolution:
            self.short_side = max(256, int(resolution))
        precision = torch.float32 if device.type == "cpu" else torch.bfloat16
        # No focal-length head: iw3 only needs relative depth, so its extra download is skipped.
        model = DepthPro2(
            backbone_preset=cfg.backbone_preset,
            reassembled_blocks=cfg.reassembled_blocks,
            cross_frame_blocks=cfg.cross_frame_blocks,
            dims_reassemble=cfg.dims_reassemble,
            dim_decoder=cfg.dim_decoder,
            fov=False,
            precision=precision,
        )
        ckpt = MODEL_FILES[model_type]
        if path.exists(ckpt):
            try:
                state = torch.load(ckpt, map_location="cpu", weights_only=True, mmap=True)
            except RuntimeError:
                state = torch.load(ckpt, map_location="cpu", weights_only=True)
            state = {k: v for k, v in state.items() if not k.startswith("fov.")}   # head not used
            model.load_state_dict(state, strict=True)
        elif not getattr(self, "allow_random_weights", False):    # (tests only)
            raise FileNotFoundError(f"{ckpt} is missing — download {model_type} in the Models window.")
        model.device = device
        return model.to(device).eval()

    # ------------------------------------------------------------------ state
    def reset_state(self):
        self._caches = [None, None]
        self._cache_shape = None

    def _cache(self, k, shape):
        from depth_pro_2.network.encoder import KVCache
        if self._cache_shape != shape:                 # a new size can't share the cache
            self._caches = [None, None]
            self._cache_shape = shape
        if self._caches[k] is None:
            self._caches[k] = KVCache(CACHE_WINDOW)
        return self._caches[k]

    # ------------------------------------------------------------------ inference
    def _work_size(self, H, W):
        if self.limit_resolution and min(H, W) <= self.short_side:
            h, w = H, W
        else:
            s = self.short_side / min(H, W)
            h, w = H * s, W * s
        return max(32, round(h / 32) * 32), max(32, round(w / 32) * 32)

    def _predict(self, x, cache):
        """x: (1, 3, h, w) normalised -> (1, h, w) inverse depth (float32)."""
        return self.model.predict_inverse_depth(x, cache).float()

    @torch.inference_mode()
    def infer(self, x, tta=False, low_vram=False, enable_amp=True, edge_dilation=0, depth_aa=False, **kwargs):
        if not torch.is_tensor(x):
            x = TF.to_tensor(x)
        x = x.to(self.device)
        single_image = x.ndim == 3                       # images: no cache; video batches: cached
        if single_image:
            x = x.unsqueeze(0)
        B, _, H, W = x.shape
        h, w = self._work_size(H, W)
        xs = F.interpolate(x.float(), size=(h, w), mode="bilinear", align_corners=False, antialias=True)
        xs = _normalize(xs)

        outs = []
        for i in range(B):
            frame = xs[i:i + 1]
            c0 = None if single_image else self._cache(0, (h, w))
            d = self._predict(frame, c0)
            if tta:
                c1 = None if single_image else self._cache(1, (h, w))
                d2 = self._predict(torch.flip(frame, dims=[3]), c1)
                d = (d + torch.flip(d2, dims=[2])) * 0.5
            outs.append(d)
        depth = torch.stack(outs)                        # (B, 1, h, w)
        depth = torch.nan_to_num(depth.clamp(min=0), nan=0.0, posinf=0.0)
        if (h, w) != (H, W):
            depth = F.interpolate(depth, size=(H, W), mode="bilinear", align_corners=False)
        if edge_dilation_is_enabled(edge_dilation):
            depth = dilate_edge(depth, edge_dilation)
        if single_image:
            depth = depth.squeeze(0)
        return depth

    # ------------------------------------------------------------------ iw3 model info
    @classmethod
    def get_name(cls):
        return "DepthPro2"

    @classmethod
    def supported(cls, model_type):
        return model_type in VARIANTS

    @classmethod
    def get_model_types(cls):
        return list(VARIANTS.keys())

    @classmethod
    def has_checkpoint_file(cls, model_type):
        return cls.supported(model_type) and path.exists(MODEL_FILES[model_type])

    @classmethod
    def get_model_path(cls, model_type):
        return MODEL_FILES[model_type]

    @classmethod
    def has_auto_download(cls, model_type):
        return False                                   # downloaded in the Models window (license)

    @classmethod
    def is_small(cls, model_type):
        return model_type == "DepthPro2_S"

    @classmethod
    def is_resolution_change_supported(cls, model_type):
        return True

    @classmethod
    def is_limit_resolution_supported(cls, model_type):
        return True

    def is_metric(self):
        return False                                   # disparity, like iw3's Depth Pro v1

    def is_video_supported(self):
        return True

    @classmethod
    def multi_gpu_supported(cls, model_type):
        return False

    @classmethod
    def force_update(cls):
        pass

    def compile(self):                                 # torch.compile would break the KV-cache calls
        pass
