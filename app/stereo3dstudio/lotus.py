"""Lotus depth (EnVision-Research) as an iw3 depth model — the same single-step model kijai's ComfyUI-Lotus runs.

Lotus is a Stable Diffusion 2 UNet fine-tuned to predict depth in one step: the picture is encoded by the SD
VAE, the UNet turns that latent into a depth latent at timestep 999 (empty prompt, "depth" task embedding),
and the VAE decodes it. It gives very fine, crisp detail, which suits photos and stills; it has no temporal
memory, so video can flicker.

Model: lotus-depth-d-v2-0-disparity — the deterministic ("regression") version, trained in disparity space,
so its output is already near = bright, the way iw3 expects. Apache-2.0. Downloaded automatically on first
use (UNet ~3.5 GB, VAE ~335 MB) into models/iw3/pretrained_models/hub/checkpoints/lotus-depth-d-v2-0-disparity.
"""
import json
import os
from os import path

import torch
import torch.nn.functional as F
from torchvision.transforms import functional as TF

from iw3.base_depth_model import BaseDepthModel
from iw3.dilation import dilate_edge, edge_dilation_is_enabled
from iw3.hub_dir import HUB_MODEL_DIR

REPO = "https://huggingface.co/jingheya/lotus-depth-d-v2-0-disparity/resolve/main/"
# CLIP embedding of an empty prompt, as used by ComfyUI-Lotus (pinned commit)
EMPTY_EMBED_URL = ("https://raw.githubusercontent.com/kijai/ComfyUI-Lotus/"
                   "07719d3195b9a31839e3c6c4875a9eb9d6b1734c/empty_text_embed.pt")
MODEL_DIR = path.join(HUB_MODEL_DIR, "checkpoints", "lotus-depth-d-v2-0-disparity")
FILES = {                               # local name -> url
    "unet.safetensors": REPO + "unet/diffusion_pytorch_model.safetensors",
    "unet_config.json": REPO + "unet/config.json",
    "vae.safetensors": REPO + "vae/diffusion_pytorch_model.safetensors",
    "vae_config.json": REPO + "vae/config.json",
    "empty_text_embed.pt": EMPTY_EMBED_URL,
}
MODEL_TYPES = {"Lotus_D": "lotus-depth-d-v2-0-disparity"}
LATENT_SCALE = 0.18215
TIMESTEP = 999
DEFAULT_LONG_SIDE = 768                 # Lotus's own default processing resolution


def _fetch_missing(log=print):
    os.makedirs(MODEL_DIR, exist_ok=True)
    for name, url in FILES.items():
        dest = path.join(MODEL_DIR, name)
        if path.exists(dest):
            continue
        log(f"Downloading Lotus: {name}…")
        tmp = dest + ".part"
        torch.hub.download_url_to_file(url, tmp, progress=True)
        os.replace(tmp, dest)


class LotusModel(BaseDepthModel):
    order: int = 22

    def __init__(self, model_type):
        super().__init__(model_type)
        self.long_side = DEFAULT_LONG_SIDE

    def load_model(self, model_type, resolution=None, device=None):
        from diffusers import AutoencoderKL, UNet2DConditionModel
        from safetensors.torch import load_file

        if not getattr(self, "allow_random_weights", False):     # (tests only)
            _fetch_missing()
        if resolution:
            self.long_side = max(256, int(resolution))
        dtype = torch.float32 if device.type == "cpu" else torch.float16

        def cfg(name):
            p = path.join(MODEL_DIR, name)
            with open(p, encoding="utf-8") as f:
                return {k: v for k, v in json.load(f).items() if not k.startswith("_")}

        unet = UNet2DConditionModel.from_config(cfg("unet_config.json"))
        vae = AutoencoderKL.from_config(cfg("vae_config.json"))
        if path.exists(path.join(MODEL_DIR, "unet.safetensors")):
            unet.load_state_dict(load_file(path.join(MODEL_DIR, "unet.safetensors")))
            vae.load_state_dict(load_file(path.join(MODEL_DIR, "vae.safetensors")))
        embed = torch.load(path.join(MODEL_DIR, "empty_text_embed.pt"), map_location="cpu", weights_only=True)

        self.unet = unet.to(device, dtype).eval()
        self.vae = vae.to(device, torch.float32).eval()      # fp32 VAE: fp16 SD VAEs can overflow
        self.embed = embed.to(device, dtype)
        task = torch.tensor([[1.0, 0.0]], device=device, dtype=dtype)        # [1, 0] = depth
        self.task_emb = torch.cat([torch.sin(task), torch.cos(task)], dim=-1)
        self.dtype = dtype
        return torch.nn.ModuleDict({"unet": self.unet, "vae": self.vae})

    # ------------------------------------------------------------------ inference
    def _work_size(self, H, W):
        if self.limit_resolution and max(H, W) <= self.long_side:
            h, w = H, W
        else:
            s = self.long_side / max(H, W)
            h, w = H * s, W * s
        return max(64, round(h / 64) * 64), max(64, round(w / 64) * 64)

    def _predict(self, x):
        """x: (B, 3, h, w) in 0..1 -> (B, 1, h, w) disparity in 0..1."""
        B = x.shape[0]
        lat = self.vae.encode(x.float() * 2 - 1).latent_dist.mode() * LATENT_SCALE
        out = self.unet(
            lat.to(self.dtype),
            torch.tensor(TIMESTEP, device=x.device).long(),
            encoder_hidden_states=self.embed.repeat(B, 1, 1),
            class_labels=self.task_emb.repeat(B, 1),
            return_dict=False,
        )[0]
        img = self.vae.decode(out.float() / LATENT_SCALE, return_dict=False)[0]
        return ((img + 1) * 0.5).clamp(0, 1).mean(dim=1, keepdim=True)

    @torch.inference_mode()
    def infer(self, x, tta=False, low_vram=False, enable_amp=True, edge_dilation=0, depth_aa=False, **kwargs):
        if not torch.is_tensor(x):
            x = TF.to_tensor(x)
        x = x.to(self.device)
        single = x.ndim == 3
        if single:
            x = x.unsqueeze(0)
        B, _, H, W = x.shape
        h, w = self._work_size(H, W)
        xs = F.interpolate(x.float(), size=(h, w), mode="bicubic", align_corners=False, antialias=True).clamp(0, 1)
        outs = []
        step = 1 if low_vram else B
        for i in range(0, B, step):
            chunk = xs[i:i + step]
            d = self._predict(chunk)
            if tta:
                d = (d + torch.flip(self._predict(torch.flip(chunk, dims=[3])), dims=[3])) * 0.5
            outs.append(d)
        depth = torch.cat(outs)
        if (h, w) != (H, W):
            depth = F.interpolate(depth, size=(H, W), mode="bilinear", align_corners=False)
        if edge_dilation_is_enabled(edge_dilation):
            depth = dilate_edge(depth, edge_dilation)
        return depth.squeeze(0) if single else depth

    # ------------------------------------------------------------------ iw3 model info
    @classmethod
    def get_name(cls):
        return "Lotus"

    @classmethod
    def supported(cls, model_type):
        return model_type in MODEL_TYPES

    @classmethod
    def get_model_types(cls):
        return list(MODEL_TYPES)

    @classmethod
    def get_model_path(cls, model_type):
        return path.join(MODEL_DIR, "unet.safetensors")

    @classmethod
    def has_checkpoint_file(cls, model_type):
        return cls.supported(model_type) and all(path.exists(path.join(MODEL_DIR, f)) for f in FILES)

    @classmethod
    def has_auto_download(cls, model_type):
        return True                                    # Apache-2.0: downloads on first use, no prompt

    @classmethod
    def is_resolution_change_supported(cls, model_type):
        return True

    @classmethod
    def is_limit_resolution_supported(cls, model_type):
        return True

    def is_metric(self):
        return False                                   # disparity, near = bright

    def is_video_supported(self):
        return True                                    # works, but per frame (may flicker)

    @classmethod
    def multi_gpu_supported(cls, model_type):
        return False

    @classmethod
    def force_update(cls):
        pass

    def compile(self):
        pass
