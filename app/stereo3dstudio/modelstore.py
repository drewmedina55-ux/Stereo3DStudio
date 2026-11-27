"""Depth models that iw3 can't auto-download (non-commercial licenses).

Stereo3D Studio downloads them from the official model pages only after the user accepts the license."""
import os
import time
from os import path

HF = "https://huggingface.co/depth-anything/"
NC = "CC BY-NC 4.0 (non-commercial)"

# model_type -> (download url or None, page url, license, approx size)
CATALOG = {
    "Any_V2_B": (HF + "Depth-Anything-V2-Base/resolve/main/depth_anything_v2_vitb.pth",
                 HF + "Depth-Anything-V2-Base", NC, "390 MB"),
    "Any_V2_L": (HF + "Depth-Anything-V2-Large/resolve/main/depth_anything_v2_vitl.pth",
                 HF + "Depth-Anything-V2-Large", NC, "1.3 GB"),
    "Any_V2_N_L": (HF + "Depth-Anything-V2-Metric-Hypersim-Large/resolve/main/depth_anything_v2_metric_hypersim_vitl.pth",
                   HF + "Depth-Anything-V2-Metric-Hypersim-Large", NC, "1.3 GB"),
    "Any_V2_K_L": (HF + "Depth-Anything-V2-Metric-VKITTI-Large/resolve/main/depth_anything_v2_metric_vkitti_vitl.pth",
                   HF + "Depth-Anything-V2-Metric-VKITTI-Large", NC, "1.3 GB"),
    "VDA_B": (HF + "Video-Depth-Anything-Base/resolve/main/video_depth_anything_vitb.pth",
              HF + "Video-Depth-Anything-Base", NC, "460 MB"),
    "VDA_L": (HF + "Video-Depth-Anything-Large/resolve/main/video_depth_anything_vitl.pth",
              HF + "Video-Depth-Anything-Large", NC, "1.5 GB"),
    "VDA_Metric_B": (HF + "Metric-Video-Depth-Anything-Base/resolve/main/metric_video_depth_anything_vitb.pth",
                     HF + "Metric-Video-Depth-Anything-Base", NC, "460 MB"),
    "VDA_Metric_L": (HF + "Metric-Video-Depth-Anything-Large/resolve/main/metric_video_depth_anything_vitl.pth",
                     HF + "Metric-Video-Depth-Anything-Large", NC, "1.5 GB"),
    # these need a manual download from their page, then "Import file…"
    "Distill_Any_B": ("https://huggingface.co/xingyang1/Distill-Any-Depth/resolve/main/base/model.safetensors?download=true",
                      "https://github.com/Westlake-AGI-Lab/Distill-Any-Depth",
                      "Apache 2.0 (trained from CC BY-NC weights)", "~400 MB"),
    "Distill_Any_L": ("https://huggingface.co/xingyang1/Distill-Any-Depth/resolve/main/large/model.safetensors?download=true",
                      "https://github.com/Westlake-AGI-Lab/Distill-Any-Depth",
                      "Apache 2.0 (trained from CC BY-NC weights)", "~1.3 GB"),
    "Ultimate_DAV2_UL": (None, "https://huggingface.co/Jokeru1983/Ultimate_DAV2_ViT-S_Gaming", NC, "~100 MB"),
    "Ultimate_DAV2_S": (None, "https://huggingface.co/Jokeru1983/Ultimate_DAV2_ViT-S_Gaming", NC, "~100 MB"),
    "Ultimate_DAV2_B": (None, "https://huggingface.co/Jokeru1983/Ultimate_DAV2_ViT-S_Gaming", NC, "~400 MB"),
}
# Apple Depth Pro 2 — weights from Apple's model CDN (the URLs its own code downloads from)
_APPLE = "Apple ML Research Model License (research use only, non-commercial)"
_DP2_PAGE = "https://huggingface.co/apple/DepthPro2"
for _k, _size in (("DepthPro2_S", "97 MB"), ("DepthPro2_B", "386 MB"), ("DepthPro2_L", "1.3 GB"),
                  ("DepthPro2_H", "3.5 GB")):
    from .depthpro2 import DOWNLOAD_URLS as _DP2_URLS
    CATALOG[_k] = (_DP2_URLS[_k], _DP2_PAGE, _APPLE, _size)

# Apple SHARP (3D scene stereo method) — not a depth model, so it has its own file path
from .sharp3d import MODEL_URL as _SHARP_URL, MODEL_PAGE as _SHARP_PAGE, MODEL_FILE as _SHARP_FILE
CATALOG["SHARP_3D"] = (_SHARP_URL, _SHARP_PAGE, _APPLE, "2.7 GB")
EXTRA_PATHS = {"SHARP_3D": _SHARP_FILE}

# models that share one checkpoint file
ALIASES = {
    "VDA_Stream_B": "VDA_B", "VDA_Stream_L": "VDA_L",
    "VDA_Stream_Metric_B": "VDA_Metric_B", "VDA_Stream_Metric_L": "VDA_Metric_L",
}


def canonical(model_type):
    return ALIASES.get(model_type, model_type)


def needs_manual(model_type):
    return canonical(model_type) in CATALOG


def target_path(model_type):
    if model_type in EXTRA_PATHS:
        return EXTRA_PATHS[model_type]
    from iw3.base_depth_model import BaseDepthModel
    cls = BaseDepthModel.get_depth_model_class(model_type)
    return cls.get_model_path(model_type) if cls else None


def is_installed(model_type):
    p = target_path(model_type)
    return bool(p) and path.exists(p) and path.getsize(p) > 1_000_000


def is_ready(model_type):
    """True when the model can run (auto-downloaded models are always 'ready')."""
    return not needs_manual(model_type) or is_installed(model_type)


def download(model_type, progress=None, cancel=None):
    """Download to the exact file iw3 expects. progress(done_bytes, total_bytes)."""
    import requests
    url = CATALOG[canonical(model_type)][0]
    if not url:
        raise ValueError("This model has no direct download. Use “Open page”, then “Import file…”.")
    dest = target_path(model_type)
    os.makedirs(path.dirname(dest), exist_ok=True)
    tmp = dest + ".part"
    with requests.get(url, stream=True, timeout=60, allow_redirects=True,
                      headers={"User-Agent": "Stereo3DStudio/1.0"}) as r:
        if r.status_code == 404:
            raise RuntimeError("The model page no longer has this file (404). Use “Open page” to get it manually.")
        r.raise_for_status()
        total = int(r.headers.get("content-length") or 0)
        done = 0
        last = 0.0
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(chunk_size=4 * 1024 * 1024):
                if cancel is not None and cancel.is_set():
                    f.close()
                    os.remove(tmp)
                    raise RuntimeError("Cancelled")
                f.write(chunk)
                done += len(chunk)
                if progress and time.time() - last > 0.2:
                    last = time.time()
                    progress(done, total)
    if total and os.path.getsize(tmp) != total:
        os.remove(tmp)
        raise RuntimeError("Download was incomplete. Please try again.")
    os.replace(tmp, dest)
    if progress:
        progress(total or done, total or done)
    return dest


def import_file(model_type, src):
    import shutil
    dest = target_path(model_type)
    os.makedirs(path.dirname(dest), exist_ok=True)
    ext_need = path.splitext(dest)[1].lower()
    if path.splitext(src)[1].lower() != ext_need:
        raise ValueError(f"This model needs a {ext_need} file.")
    shutil.copyfile(src, dest + ".part")
    os.replace(dest + ".part", dest)
    return dest
