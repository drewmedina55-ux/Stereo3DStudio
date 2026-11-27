"""Settings model, defaults, presets and persistence."""
import json
import os
from copy import deepcopy

# Output layouts shown to the user -> iw3 flags
LAYOUTS = {
    "Half SBS (Odyssey 3D / 3D TVs)": {"half_sbs": True},
    "Full SBS (VR players, double width)": {},
    "Full Top-Bottom": {"tb": True},
    "Half Top-Bottom": {"half_tb": True},
    "VR180 (headsets)": {"vr180": True},
    "Cross-eyed": {"cross_eyed": True},
    "Anaglyph (red/cyan glasses)": {"anaglyph": "dubois"},
    "RGB + Depth": {"rgbd": True},
    "Half RGB + Depth": {"half_rgbd": True},
    "Depth map only": {"rgbd": True},          # RGB + Depth, then only the depth half is kept
}
DEPTH_ONLY = "Depth map only"
IMAGE_OUTPUTS = {                              # how images are saved
    "single": "One 3D image (output layout)",
    "lr": "Two images: left eye + right eye",
    "rgb_depth": "Two images: colour + depth map",
}

# Friendly labels for depth models. Unknown models fall back to their raw name.
DEPTH_MODEL_LABELS = {
    "Any_V2_S": "Depth Anything V2 · Small (fast)",
    "Any_V2_B": "Depth Anything V2 · Base",
    "Any_V2_L": "Depth Anything V2 · Large (best detail)",
    "Distill_Any_S": "Distill Any Depth · Small",
    "Distill_Any_B": "Distill Any Depth · Base",
    "Distill_Any_L": "Distill Any Depth · Large",
    "Any_V3_Mono": "Depth Anything 3 · Mono",
    "Any_V3_Mono_01": "Depth Anything 3 · Mono 0.1",
    "VDA_S": "Video Depth Anything · Small (stable video)",
    "VDA_B": "Video Depth Anything · Base (stable video)",
    "VDA_L": "Video Depth Anything · Large (stable video)",
    "VDA_Stream_S": "Video Depth Anything Stream · Small",
    "VDA_Stream_B": "Video Depth Anything Stream · Base",
    "VDA_Stream_L": "Video Depth Anything Stream · Large",
    "DepthPro": "Apple Depth Pro",
    "DepthPro_S": "Apple Depth Pro · Small",
    "Lotus_D": "Lotus Depth (sharpest detail, images)",
    "Lotus2_D": "Lotus-2 (experimental · images only · very slow)",
    "SHARP_3D": "Apple SHARP — 3D scene method (experimental · images)",
    "DepthPro2_S": "Apple Depth Pro 2 · Small (fast, stable video)",
    "DepthPro2_B": "Apple Depth Pro 2 · Base (stable video)",
    "DepthPro2_L": "Apple Depth Pro 2 · Large (sharp, stable video)",
    "DepthPro2_H": "Apple Depth Pro 2 · Huge+ (sharpest, slow)",
    "ZoeD_Any_N": "ZoeDepth + Depth Anything (indoor)",
    "ZoeD_Any_K": "ZoeDepth + Depth Anything (outdoor)",
    "ZoeD_N": "ZoeDepth (indoor)",
    "ZoeD_K": "ZoeDepth (outdoor)",
    "ZoeD_NK": "ZoeDepth (indoor+outdoor)",
    "Any_S": "Depth Anything V1 · Small",
    "Any_B": "Depth Anything V1 · Base",
    "Any_L": "Depth Anything V1 · Large",
    "Any_V2_N_L": "Depth Anything V2 Metric · Indoor Large",
    "Any_V2_K_L": "Depth Anything V2 Metric · Outdoor Large",
    "VDA_Metric_B": "Video Depth Anything Metric · Base",
    "VDA_Metric_L": "Video Depth Anything Metric · Large",
    "Ultimate_DAV2_UL": "Ultimate DAV2 · Ultra-light (games)",
    "Ultimate_DAV2_S": "Ultimate DAV2 · Small (games)",
    "Ultimate_DAV2_B": "Ultimate DAV2 · Base (games)",
    "NULL": "None (flat — for testing)",
}
# Models listed first, in this order
DEPTH_MODEL_ORDER = [
    "Any_V2_S", "Any_V2_B", "Any_V2_L", "Distill_Any_S", "Distill_Any_B", "Distill_Any_L",
    "Any_V3_Mono", "VDA_S", "VDA_B", "VDA_L", "Lotus_D", "Lotus2_D", "DepthPro2_S", "DepthPro2_B", "DepthPro2_L",
    "DepthPro2_H", "DepthPro", "ZoeD_Any_N", "ZoeD_Any_K",
]

METHODS = {
    "Row Flow v3 (recommended)": "row_flow_v3",
    "Row Flow v3 symmetric": "row_flow_v3_sym",
    "Row Flow v2": "row_flow_v2",
    "MLBW L2 (less stretching)": "mlbw_l2",
    "MLBW L4": "mlbw_l4",
    "MLBW L2 + inpaint (fills gaps)": "mlbw_l2_inpaint",
    "Forward + fill": "forward_fill",
    "Forward + inpaint": "forward_inpaint",
    "Backward": "backward",
    "Grid sample (classic)": "grid_sample",
    "SHARP 3D scene (experimental · Apple, images)": "sharp",
}

CODECS = ["libx264", "libx265", "h264_nvenc", "hevc_nvenc", "libopenh264", "utvideo", "ffv1"]
PRESETS_ENC = ["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow",
               "p1", "p2", "p3", "p4", "p5", "p6", "p7"]
PIX_FMTS = ["yuv420p", "yuv444p", "yuv420p10le", "rgb24"]

# Tuned for a 16 GB NVIDIA card + Samsung Odyssey 3D.
# Best quality that still runs at full GPU speed without running out of VRAM.
SETTINGS_VERSION = 6

DEFAULTS = {
    "layout": "Half SBS (Odyssey 3D / 3D TVs)",
    "depth_model": "Any_V2_L",      # best detail; fits 16 GB at default resolution
    "resolution": 0,                # model default (higher multiplies VRAM + time)
    "method": "mlbw_l2_inpaint",    # fills revealed gaps - cleanest edges
    "max_height": 1080,
    "pad_16x9": True,
    "image_output": "single",       # images: one 3D file, or two files (left/right or colour/depth)
    "auto_image_preset": True,      # images added -> switch to the Lotus image preset (videos -> switch back)               # 4:3 videos get side bars so SBS / top-bottom frames are 16:9             # process videos at up to this height (0 = source size)
    "divergence": 2.2,
    "convergence": 0.45,
    "foreground_scale": 0.0,
    "edge_dilation": 1,             # thin, clean edges
    "ipd_offset": 0.0,
    "synthetic_view": "both",
    "preserve_screen_border": True, # no tearing at the frame's left/right edges
    "depth_aa": True,               # smoother depth edges (V2 models)
    "tta": False,
    # video
    "video_format": "mp4",
    "video_codec": "hevc_nvenc",    # GPU encoder - fast, frees the CPU
    "crf": 20,
    "enc_preset": "p5",
    "pix_fmt": "yuv420p",
    "max_fps": 30.0,
    "keep_source_fps": False,
    "ema_normalize": True,
    "ema_decay": 0.75,
    "scene_detect": True,
    "hwaccel_decode": True,         # GPU video decoding (NVDEC)
    "autocrop": "",
    # image
    "image_format": "png",
    # performance (16 GB VRAM)
    "gpu": 0,
    "batch_size": 4,
    "low_vram": False,
    "fp16": True,
    "max_workers": 0,
    "cuda_stream": False,
    # job
    "output_dir": "",
    "recursive": False,
    "resume": False,
    "metadata_in_name": False,
    # live view
    "live_view": True,
    "live_every": 100,
    "live_mode": 1,          # 0 cross-eyed, 1 parallel (default), 2 raw
    # conversion preview reel
    "reel_total": 60,
    "reel_clip": 8,
    "reel_moments": [],             # your own preview moments [[start, length], ...] - shared by every clip
    "open_when_done": True,
    "live_pinned": True,     # Live view locked to the main window
    # title overlay (see title.py)
    "title_on": False, "title_text": "", "title_font": "Segoe UI", "title_bold": True, "title_size": 8.0,
    "title_color": "#ffffff", "title_shadow": True, "title_place": "Center", "title_when": "Start",
    "title_offset": 1.0, "title_fade_in": 1.0, "title_hold": 3.0, "title_fade_out": 1.0, "title_opacity": 100,
    "title_depth": 0,
}

BUILTIN_PRESETS = {
    "Odyssey 3D · Best": {"layout": "Half SBS (Odyssey 3D / 3D TVs)", "depth_model": "Any_V2_L", "tta": True,
                          "edge_dilation": 1},
    "Odyssey 3D · Fast": {"depth_model": "Any_V2_S", "batch_size": 8,
                          "edge_dilation": 1, "enc_preset": "p4", "crf": 22},
    "Odyssey 3D · Max quality (slow, short clips)": {"layout": "Half SBS (Odyssey 3D / 3D TVs)",
                                                      "depth_model": "Any_V2_L", "edge_dilation": 1, "tta": True,
                                                      "resolution": 518, "batch_size": 2, "crf": 18,
                                                      "enc_preset": "p6"},
    "Video · least flicker": {"depth_model": "VDA_L", "method": "mlbw_l2", "batch_size": 4, "edge_dilation": 1},
    "VR headset · VR180": {"layout": "VR180 (headsets)", "edge_dilation": 1},
    "Images · Lotus (sharp detail)": {"layout": "Half SBS (Odyssey 3D / 3D TVs)", "depth_model": "Lotus_D",
                                      "resolution": 1036, "tta": True, "edge_dilation": 1,
                                      "method": "mlbw_l2_inpaint", "batch_size": 1},
    "Photos · Pop-out": {"foreground_scale": 1.0,
                         "edge_dilation": 1, "tta": True},
    "Anaglyph glasses": {"layout": "Anaglyph (red/cyan glasses)", "edge_dilation": 1},
}


def config_dir():
    base = os.environ.get("APPDATA") or os.path.expanduser("~/.config")
    d = os.path.join(base, "Stereo3DStudio")
    os.makedirs(os.path.join(d, "presets"), exist_ok=True)
    return d


OLD_LAYOUT_NAMES = {
    "Full SBS (Odyssey 3D / 3D TV)": "Full SBS (VR players, double width)",
    "Half SBS": "Half SBS (Odyssey 3D / 3D TVs)",
}


def _merged(values):
    out = deepcopy(DEFAULTS)
    if isinstance(values, dict):
        for k, v in values.items():
            if k in out:
                out[k] = v
    out["layout"] = OLD_LAYOUT_NAMES.get(out["layout"], out["layout"])
    if out["layout"] not in LAYOUTS:
        out["layout"] = DEFAULTS["layout"]
    return out


def load_last():
    try:
        with open(os.path.join(config_dir(), "last_settings.json"), encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return deepcopy(DEFAULTS)
    if not isinstance(data, dict):
        return deepcopy(DEFAULTS)
    ver = data.get("settings_version", 1)
    if ver < 3:
        # new recommended settings replace old ones once; keep the user's folders
        keep = {k: data[k] for k in ("output_dir", "recursive", "metadata_in_name") if k in data}
        return _merged(keep)
    if ver < 4:
        data["depth_model"] = "Any_V2_L"   # v1.2.2: Depth Anything V2 Large is the default again
    if ver < 6:
        data["max_height"] = 1080   # 4K sources were far too slow at full size
    if ver < 5:
        data["divergence"], data["convergence"] = 2.2, 0.45   # new 3D strength / screen plane defaults
    return _merged(data)


def save_last(values):
    values = dict(values, settings_version=SETTINGS_VERSION)
    try:
        with open(os.path.join(config_dir(), "last_settings.json"), "w", encoding="utf-8") as f:
            json.dump(values, f, indent=2)
    except Exception:
        pass


def list_user_presets():
    d = os.path.join(config_dir(), "presets")
    return sorted(os.path.splitext(f)[0] for f in os.listdir(d) if f.endswith(".json"))


def load_preset(name):
    if name in BUILTIN_PRESETS:
        return _merged(BUILTIN_PRESETS[name])
    with open(os.path.join(config_dir(), "presets", name + ".json"), encoding="utf-8") as f:
        return _merged(json.load(f))


def save_preset(name, values):
    safe = "".join(c for c in name if c not in '<>:"/\\|?*').strip() or "Preset"
    data = {k: v for k, v in values.items() if k not in ("output_dir",)}
    with open(os.path.join(config_dir(), "presets", safe + ".json"), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return safe


def delete_preset(name):
    p = os.path.join(config_dir(), "presets", name + ".json")
    if os.path.exists(p):
        os.remove(p)
