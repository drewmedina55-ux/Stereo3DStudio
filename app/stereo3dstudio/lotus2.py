"""Lotus-2 depth (EnVision-Research, Apache-2.0) as an EXPERIMENTAL, images-only iw3 depth model.

Lotus-2 is built on Black Forest Labs' FLUX.1-dev (12B). The authors run it on 40 GB+ GPUs. To make it fit a
16 GB card, Stereo3D Studio:
  * quantizes the FLUX transformer to 4-bit NF4 (bitsandbytes) once, during setup, and keeps only that copy;
  * computes FLUX's text embeddings for the empty prompt (all Lotus-2 ever uses) once, during setup, so the
    9.5 GB T5 text encoder is never loaded again — and is deleted afterwards;
  * then runs Lotus-2's two stages: the core predictor (one step + local continuity module) and the detail
    sharpener (10 flow-matching steps), each a LoRA on the same transformer.

FLUX.1-dev is a gated model under the FLUX.1 [dev] Non-Commercial License: the user must accept it on Hugging
Face and give a token once for the download. The inference below follows Lotus-2's pipeline.py (Apache-2.0).
"""
import json
import os
import shutil
import threading
import time
from os import path

import numpy as np
import torch
import torch.nn.functional as F
from torch import nn
from torchvision.transforms import functional as TF

from iw3.base_depth_model import BaseDepthModel
from iw3.dilation import dilate_edge, edge_dilation_is_enabled
from iw3.hub_dir import HUB_MODEL_DIR

FLUX_REPO = "black-forest-labs/FLUX.1-dev"
FLUX_PAGE = "https://huggingface.co/black-forest-labs/FLUX.1-dev"
TOKEN_PAGE = "https://huggingface.co/settings/tokens"
LOTUS2_REPO = "jingheya/Lotus-2"
LOTUS2_FILES = {
    "core": "lotus-2_core_predictor_depth.safetensors",
    "lcm": "lotus-2_lcm_depth.safetensors",
    "sharpener": "lotus-2_detail_sharpener_depth.safetensors",
}
FLUX_PATTERNS = ["model_index.json", "scheduler/*", "vae/*", "transformer/*",
                 "text_encoder/*", "tokenizer/*", "text_encoder_2/*", "tokenizer_2/*"]

ROOT = path.join(HUB_MODEL_DIR, "checkpoints", "lotus-2")
FLUX_DIR = path.join(ROOT, "flux1-dev")                     # download (most of it is deleted after setup)
NF4_DIR = path.join(ROOT, "flux1-dev-transformer-nf4")      # the 4-bit transformer that is kept
EMBEDS = path.join(ROOT, "empty_prompt_embeds.pt")
LORA_DIR = path.join(ROOT, "lotus-2")
MODEL_TYPES = {"Lotus2_D": "Lotus-2 depth"}

LORA_RANK = 128
LORA_TARGETS = ["attn.to_k", "attn.to_q", "attn.to_v", "attn.to_out.0", "attn.add_k_proj", "attn.add_q_proj",
                "attn.add_v_proj", "attn.to_add_out", "ff.net.0.proj", "ff.net.2", "ff_context.net.0.proj",
                "ff_context.net.2"]
STEPS = 10                      # detail sharpener steps (Lotus-2 default)
GUIDANCE = 3.5
DEFAULT_MAX_EDGE = 1024         # Lotus-2 processes at most 1024 px on the long side
MIN_EDGE = 512


def is_ready():
    need = [path.join(NF4_DIR, "config.json"), path.join(FLUX_DIR, "vae", "config.json"),
            path.join(FLUX_DIR, "scheduler", "scheduler_config.json"), EMBEDS]
    need += [path.join(LORA_DIR, f) for f in LOTUS2_FILES.values()]
    return all(path.exists(p) for p in need)


class LocalContinuityModule(nn.Module):
    """Lotus-2's local continuity module (LCM), from its infer.py."""

    def __init__(self, num_channels):
        super().__init__()
        self.lcm = nn.Sequential(
            nn.Conv2d(num_channels, num_channels * 2, kernel_size=3, padding=1),
            nn.GELU(),
            nn.Conv2d(num_channels * 2, num_channels, kernel_size=3, padding=1),
        )

    def forward(self, x):
        dt = next(self.lcm.parameters()).dtype
        return x + self.lcm(x.to(dt)).to(x.dtype)


# ======================================================================================= setup (one time)
class SetupError(RuntimeError):
    pass


def _dir_size(p):
    total = 0
    for root, _d, files in os.walk(p):
        for f in files:
            try:
                total += path.getsize(path.join(root, f))
            except OSError:
                pass
    return total


def setup(token, progress=None, cancel=None, log=print):
    """Download FLUX.1-dev (needs the user's accepted license + token) and Lotus-2, compute the empty-prompt
    embeddings, quantize the transformer to NF4, and delete what is no longer needed.
    progress(fraction 0..1, text). Runs for a long time; call it from a worker thread."""
    from fnmatch import fnmatch
    from huggingface_hub import HfApi, hf_hub_download, snapshot_download
    from huggingface_hub.errors import GatedRepoError, RepositoryNotFoundError, HfHubHTTPError

    def report(frac, text):
        if progress:
            progress(max(0.0, min(1.0, frac)), text)

    def check_cancel():
        if cancel is not None and cancel.is_set():
            raise SetupError("Setup stopped. Run it again to continue where it left off.")

    if not torch.cuda.is_available():
        raise SetupError("Lotus-2 needs an NVIDIA GPU (CUDA).")
    try:
        import bitsandbytes  # noqa: F401
        import peft  # noqa: F401
        import transformers  # noqa: F401
    except ImportError as e:
        raise SetupError(f"A package Lotus-2 needs is missing ({e.name}). Reinstall Stereo3D Studio 1.2 or newer.")
    os.makedirs(ROOT, exist_ok=True)
    token = (token or "").strip() or None

    # ---- 1. FLUX.1-dev (gated) -------------------------------------------------------- 0 .. 70 %
    if not path.exists(path.join(NF4_DIR, "config.json")) or not path.exists(EMBEDS):
        report(0.0, "Checking your access to FLUX.1-dev…")
        try:
            info = HfApi().model_info(FLUX_REPO, files_metadata=True, token=token)
        except GatedRepoError:
            raise SetupError("Your Hugging Face account hasn't been granted FLUX.1-dev yet. Open the FLUX.1-dev page, "
                             "accept the license, then try again with a token from that same account.")
        except (RepositoryNotFoundError, HfHubHTTPError) as e:
            raise SetupError(f"Couldn't reach FLUX.1-dev with this token ({e.__class__.__name__}). "
                             "Check the token and that you accepted the license.")
        except Exception as e:
            raise SetupError(f"Couldn't connect to Hugging Face ({e.__class__.__name__}). Check your internet "
                             "connection and try again.")
        patterns = list(FLUX_PATTERNS)
        if path.exists(path.join(NF4_DIR, "config.json")):
            patterns = [p for p in patterns if not p.startswith("transformer")]
        if path.exists(EMBEDS):
            patterns = [p for p in patterns if not p.startswith(("text_encoder", "tokenizer"))]
        total = sum((s.size or 0) for s in info.siblings if any(fnmatch(s.rfilename, p) for p in patterns))
        start = _dir_size(FLUX_DIR) if path.exists(FLUX_DIR) else 0
        done_evt = threading.Event()

        def watch():
            while not done_evt.wait(1.0):
                got = _dir_size(FLUX_DIR)
                if total:
                    report(0.70 * min(1.0, got / total),
                           f"Downloading FLUX.1-dev… {got / 1e9:.1f} / {total / 1e9:.1f} GB")
        threading.Thread(target=watch, daemon=True).start()
        log(f"Downloading FLUX.1-dev ({total / 1e9:.1f} GB, {start / 1e9:.1f} GB already here)…")
        try:
            snapshot_download(FLUX_REPO, allow_patterns=patterns, local_dir=FLUX_DIR, token=token)
        except GatedRepoError:
            raise SetupError("Access to FLUX.1-dev was refused. Accept the license on its page first.")
        finally:
            done_evt.set()
        check_cancel()

    # ---- 2. Lotus-2 weights (public) -------------------------------------------------- 70 .. 74 %
    os.makedirs(LORA_DIR, exist_ok=True)
    for i, fn in enumerate(LOTUS2_FILES.values()):
        if not path.exists(path.join(LORA_DIR, fn)):
            report(0.70 + 0.01 * i, f"Downloading Lotus-2: {fn}…")
            hf_hub_download(LOTUS2_REPO, fn, local_dir=LORA_DIR, token=token)
            check_cancel()

    # ---- 3. empty-prompt embeddings, then drop the text encoders ---------------------- 74 .. 80 %
    if not path.exists(EMBEDS):
        report(0.74, "Preparing text embeddings (one time)…")
        from transformers import CLIPTextModel, CLIPTokenizer, T5EncoderModel, T5TokenizerFast
        dev = torch.device("cuda")
        tok = CLIPTokenizer.from_pretrained(path.join(FLUX_DIR, "tokenizer"))
        te = CLIPTextModel.from_pretrained(path.join(FLUX_DIR, "text_encoder"), torch_dtype=torch.bfloat16).to(dev)
        ids = tok([""], padding="max_length", max_length=tok.model_max_length, truncation=True,
                  return_tensors="pt").input_ids.to(dev)
        with torch.inference_mode():
            pooled = te(ids, output_hidden_states=False).pooler_output.cpu()
        del te
        torch.cuda.empty_cache()
        tok2 = T5TokenizerFast.from_pretrained(path.join(FLUX_DIR, "tokenizer_2"))
        te2 = T5EncoderModel.from_pretrained(path.join(FLUX_DIR, "text_encoder_2"), torch_dtype=torch.bfloat16).to(dev)
        ids2 = tok2([""], padding="max_length", max_length=512, truncation=True, return_tensors="pt").input_ids.to(dev)
        with torch.inference_mode():
            embeds = te2(ids2, output_hidden_states=False)[0].cpu()
        del te2
        torch.cuda.empty_cache()
        torch.save({"prompt_embeds": embeds, "pooled_prompt_embeds": pooled}, EMBEDS + ".part")
        os.replace(EMBEDS + ".part", EMBEDS)
        for sub in ("text_encoder", "text_encoder_2", "tokenizer", "tokenizer_2"):
            shutil.rmtree(path.join(FLUX_DIR, sub), ignore_errors=True)
        log("Text embeddings ready — removed the text encoders (about 10 GB).")
        check_cancel()

    # ---- 4. quantize the transformer to NF4 and keep only that ------------------------ 80 .. 100 %
    if not path.exists(path.join(NF4_DIR, "config.json")):
        report(0.80, "Shrinking the FLUX transformer to 4-bit (one time, several minutes)…")
        from diffusers import BitsAndBytesConfig, FluxTransformer2DModel
        q = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.bfloat16)
        tr = FluxTransformer2DModel.from_pretrained(path.join(FLUX_DIR, "transformer"), quantization_config=q,
                                                    torch_dtype=torch.bfloat16)
        tmp = NF4_DIR + ".part"
        shutil.rmtree(tmp, ignore_errors=True)
        tr.save_pretrained(tmp)
        del tr
        torch.cuda.empty_cache()
        os.replace(tmp, NF4_DIR)
        shutil.rmtree(path.join(FLUX_DIR, "transformer"), ignore_errors=True)
        log("4-bit transformer saved — removed the full-size one (about 24 GB).")
    report(1.0, "Lotus-2 is ready.")


# ======================================================================================= model
class Lotus2Model(BaseDepthModel):
    order: int = 23

    def __init__(self, model_type):
        super().__init__(model_type)
        self.max_edge = DEFAULT_MAX_EDGE

    def load_model(self, model_type, resolution=None, device=None):
        from diffusers import AutoencoderKL, FlowMatchEulerDiscreteScheduler, FluxTransformer2DModel
        from diffusers.utils import convert_unet_state_dict_to_peft
        from peft import LoraConfig, set_peft_model_state_dict
        from safetensors.torch import load_file

        if not is_ready() and not getattr(self, "test_mode", False):
            raise RuntimeError("Lotus-2 isn't set up yet — open Models → “Set up Lotus-2 (experimental)…”.")
        if resolution:
            self.max_edge = max(MIN_EDGE, int(resolution))
        dtype = torch.bfloat16 if device.type == "cuda" else torch.float32

        if getattr(self, "test_mode", False):                 # tiny random model (tests only)
            transformer, vae, sched, embeds, lcm_sd = self._test_parts()
        else:
            transformer = FluxTransformer2DModel.from_pretrained(NF4_DIR, torch_dtype=dtype)
            vae = AutoencoderKL.from_pretrained(path.join(FLUX_DIR, "vae"), torch_dtype=dtype)
            with open(path.join(FLUX_DIR, "scheduler", "scheduler_config.json"), encoding="utf-8") as f:
                sc = {k: v for k, v in json.load(f).items() if not k.startswith("_")}
            sched = FlowMatchEulerDiscreteScheduler.from_config(dict(sc, num_train_timesteps=10))
            embeds = torch.load(EMBEDS, map_location="cpu", weights_only=True)
            lcm_sd = torch.load(path.join(LORA_DIR, LOTUS2_FILES["lcm"]), map_location="cpu", weights_only=True)

        # two LoRA adapters on the same transformer, like Lotus-2's load_lora_and_lcm_weights()
        for name, key in (("core_predictor", "core"), ("detail_sharpener", "sharpener")):
            transformer.add_adapter(LoraConfig(r=LORA_RANK, lora_alpha=LORA_RANK, init_lora_weights="gaussian",
                                               target_modules=LORA_TARGETS), adapter_name=name)
            if getattr(self, "test_mode", False):
                continue
            sd = load_file(path.join(LORA_DIR, LOTUS2_FILES[key]))
            sd = {k.replace("transformer.", "", 1): v for k, v in sd.items() if k.startswith("transformer.")}
            set_peft_model_state_dict(transformer, convert_unet_state_dict_to_peft(sd), adapter_name=name)
        transformer.requires_grad_(False)

        lcm = LocalContinuityModule(transformer.config.in_channels // 4)
        lcm.load_state_dict(lcm_sd)
        if not getattr(transformer, "is_quantized", False):
            transformer.to(device, dtype)
        self.transformer = transformer.eval()
        self.vae = vae.to(device, dtype).eval()
        self.lcm = lcm.to(device, dtype).eval()
        self.sched = sched
        self.prompt_embeds = embeds["prompt_embeds"].to(device, dtype)
        self.pooled = embeds["pooled_prompt_embeds"].to(device, dtype)
        self.text_ids = torch.zeros(self.prompt_embeds.shape[1], 3, device=device, dtype=dtype)
        self.dtype = dtype
        self.vae_scale = 2 ** (len(self.vae.config.block_out_channels) - 1)
        return nn.ModuleDict({"vae": self.vae, "lcm": self.lcm})

    def _test_parts(self):
        """Random tiny FLUX-shaped parts, so the pipeline can be exercised without the 30 GB download."""
        from diffusers import AutoencoderKL, FlowMatchEulerDiscreteScheduler, FluxTransformer2DModel
        tr = FluxTransformer2DModel(patch_size=1, in_channels=64, num_layers=1, num_single_layers=1,
                                    attention_head_dim=16, num_attention_heads=2, joint_attention_dim=32,
                                    pooled_projection_dim=16, guidance_embeds=True, axes_dims_rope=(4, 6, 6))
        vae = AutoencoderKL(in_channels=3, out_channels=3, latent_channels=16, block_out_channels=(32, 32, 32, 32),
                            down_block_types=("DownEncoderBlock2D",) * 4, up_block_types=("UpDecoderBlock2D",) * 4,
                            layers_per_block=1, norm_num_groups=8, shift_factor=0.1159, scaling_factor=0.3611)
        sched = FlowMatchEulerDiscreteScheduler(num_train_timesteps=10, shift=3.0, use_dynamic_shifting=True,
                                                base_image_seq_len=256, max_image_seq_len=4096,
                                                base_shift=0.5, max_shift=1.15)
        embeds = {"prompt_embeds": torch.randn(1, 8, 32), "pooled_prompt_embeds": torch.randn(1, 16)}
        lcm_sd = LocalContinuityModule(16).state_dict()
        return tr, vae, sched, embeds, lcm_sd

    # ------------------------------------------------------------------ inference
    def _work_size(self, H, W):
        long_edge = max(H, W)
        s = 1.0
        if long_edge > self.max_edge:
            s = self.max_edge / long_edge
        elif long_edge < MIN_EDGE:
            s = MIN_EDGE / long_edge
        return max(16, round(H * s / 16) * 16), max(16, round(W * s / 16) * 16)

    def _predict(self, rgb):
        """rgb: (1, 3, h, w) in -1..1 -> (1, 1, h, w) disparity in 0..1 (near = bright)."""
        from diffusers import FluxPipeline
        from diffusers.pipelines.flux.pipeline_flux import calculate_shift, retrieve_timesteps
        B, _, h, w = rgb.shape
        dev = rgb.device
        vc = self.vae.config
        lat = self.vae.encode(rgb.to(self.dtype)).latent_dist.mode()
        lat = (lat - vc.shift_factor) * vc.scaling_factor
        C, lh, lw = lat.shape[1:]
        packed = FluxPipeline._pack_latents(lat, B, C, lh, lw)
        img_ids = FluxPipeline._prepare_latent_image_ids(B, lh // 2, lw // 2, dev, lat.dtype)
        guidance = (torch.full([B], GUIDANCE, device=dev, dtype=torch.float32)
                    if self.transformer.config.guidance_embeds else None)
        common = dict(guidance=guidance, pooled_projections=self.pooled.expand(B, -1),
                      encoder_hidden_states=self.prompt_embeds.expand(B, -1, -1),
                      txt_ids=self.text_ids, img_ids=img_ids, joint_attention_kwargs={}, return_dict=False)

        # stage 1: core predictor (one step) + local continuity module
        self.transformer.set_adapter("core_predictor")
        t_core = torch.full([B], 1 / 1000, device=dev, dtype=lat.dtype)
        out = self.transformer(hidden_states=packed, timestep=t_core, **common)[0]
        lat = self.lcm(FluxPipeline._unpack_latents(out, h, w, self.vae_scale))

        # stage 2: detail sharpener (flow-matching steps)
        self.transformer.set_adapter("detail_sharpener")
        packed = FluxPipeline._pack_latents(lat, B, lat.shape[1], lat.shape[2], lat.shape[3])
        sc = self.sched.config
        mu = calculate_shift(packed.shape[1], sc.base_image_seq_len, sc.max_image_seq_len, sc.base_shift, sc.max_shift)
        timesteps, _ = retrieve_timesteps(self.sched, STEPS, dev, sigmas=np.linspace(1.0, 1 / STEPS, STEPS), mu=mu)
        for t in timesteps:
            noise = self.transformer(hidden_states=packed, timestep=t.expand(B).to(packed.dtype) / 1000, **common)[0]
            packed = self.sched.step(noise, t, packed, return_dict=False)[0]

        lat = FluxPipeline._unpack_latents(packed.to(self.dtype), h, w, self.vae_scale)
        lat = lat / vc.scaling_factor + vc.shift_factor
        img = self.vae.decode(lat, return_dict=False)[0]
        return (img.float() * 0.5 + 0.5).clamp(0, 1).mean(dim=1, keepdim=True)

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
        xs = F.interpolate(x.float(), size=(h, w), mode="bicubic", align_corners=False, antialias=True)
        xs = xs.clamp(0, 1) * 2 - 1
        outs = []
        for i in range(B):                               # one image at a time keeps GPU memory low
            d = self._predict(xs[i:i + 1])
            if tta:
                d = (d + torch.flip(self._predict(torch.flip(xs[i:i + 1], dims=[3])), dims=[3])) * 0.5
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
        return "Lotus2"

    @classmethod
    def supported(cls, model_type):
        return model_type in MODEL_TYPES

    @classmethod
    def get_model_types(cls):
        return list(MODEL_TYPES)

    @classmethod
    def get_model_path(cls, model_type):
        return path.join(NF4_DIR, "config.json")

    @classmethod
    def has_checkpoint_file(cls, model_type):
        return cls.supported(model_type) and is_ready()

    @classmethod
    def has_auto_download(cls, model_type):
        return True                     # set up in its own dialog, not the Models table

    @classmethod
    def is_resolution_change_supported(cls, model_type):
        return True

    @classmethod
    def is_limit_resolution_supported(cls, model_type):
        return False

    def is_metric(self):
        return False

    def is_video_supported(self):
        return False                    # far too slow for video

    @classmethod
    def multi_gpu_supported(cls, model_type):
        return False

    @classmethod
    def force_update(cls):
        pass

    def compile(self):
        pass
