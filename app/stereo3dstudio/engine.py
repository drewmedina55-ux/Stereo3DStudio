"""Bridge between the Stereo3D Studio UI and the iw3 engine (nunif)."""
import gc
import os
import threading
import time
import traceback
from os import path

import torch

from iw3 import models  # noqa: F401  (registers model classes)
from . import depthpro2  # noqa: F401  (registers Apple Depth Pro 2)
from iw3.utils import create_parser, set_state_args, iw3_main, is_video, is_image
from iw3.depth_model_factory import get_all_depth_models, is_depth_aa_supported
from nunif.utils.video import VIDEO_EXTENSIONS, has_nvenc
from nunif.utils.image_loader import IMG_EXTENSIONS

from .settings import LAYOUTS, DEPTH_MODEL_ORDER
import iw3.utils as _iw3_utils

# iw3 names Half SBS files "<name>_LR". Windows Media Player treats that tag specially and shows
# only one eye, so Stereo3D Studio uses unambiguous tags instead.
_iw3_utils.HALF_SBS_SUFFIX = "_HSBS"
_iw3_utils.HALF_TB_SUFFIX = "_HTB"

VIDEO_EXTS = {e.lower() for e in VIDEO_EXTENSIONS}
IMAGE_EXTS = {e.lower() for e in IMG_EXTENSIONS}


def classify(p):
    if path.isdir(p):
        return "Folder"
    ext = path.splitext(p)[1].lower()
    if ext in VIDEO_EXTS:
        return "Video"
    if ext in IMAGE_EXTS:
        return "Image"
    return None


def list_gpus():
    """[(id, label)]; id -1 is CPU."""
    gpus = []
    try:
        if torch.cuda.is_available():
            for i in range(torch.cuda.device_count()):
                p = torch.cuda.get_device_properties(i)
                gpus.append((i, f"GPU {i}: {p.name} ({p.total_memory / 1024**3:.0f} GB)"))
    except Exception:
        pass
    gpus.append((-1, "CPU (very slow)"))
    return gpus


def gpu_short_name():
    """e.g. 'RTX 5080' for the GPU in this PC, or '' when there is no CUDA GPU."""
    try:
        if torch.cuda.is_available():
            n = torch.cuda.get_device_name(0)
            for pre in ("NVIDIA GeForce ", "NVIDIA ", "GeForce "):
                if n.startswith(pre):
                    n = n[len(pre):]
            return n.strip()
    except Exception:
        pass
    return ""


def cuda_summary():
    try:
        if torch.cuda.is_available():
            name = torch.cuda.get_device_name(0)
            return True, f"CUDA {torch.version.cuda} · {name}"
    except Exception:
        pass
    return False, "No CUDA GPU detected — running on CPU"


def depth_models():
    models_ = get_all_depth_models()
    ordered = [m for m in DEPTH_MODEL_ORDER if m in models_]
    ordered += [m for m in models_ if m not in ordered and not m.startswith(("VDA_Metric", "VDA_Stream_Metric"))]
    return ordered


def nvenc_available():
    try:
        return has_nvenc()
    except Exception:
        return False


def _video_info(p):
    """(width, height, sample aspect ratio, pixel format) of a video file, or None for images, folders and
    unreadable files."""
    if not path.isfile(p) or classify(p) != "Video":
        return None
    try:
        import av
        with av.open(p) as c:
            st = c.streams.video[0]
            sar = st.sample_aspect_ratio or st.codec_context.sample_aspect_ratio
            sar = float(sar) if sar and float(sar) > 0 else 1.0
            return int(st.width), int(st.height), sar, (st.codec_context.format.name if st.codec_context.format else "")
    except Exception:
        return None


# The engine's GPU-decode path only handles yuv420p / yuv420p10le sources. Others (full-range "yuvj420p" from
# phones and stock sites, 4:2:2, 4:4:4...) fail with "Invalid argument returned 22", so they decode on the CPU.
_NVDEC_PIX_FMTS = {"yuv420p", "yuv420p10le", ""}


def _nvdec_ok(info):
    return info is None or info[3] in _NVDEC_PIX_FMTS


# Layouts where the two eyes share one frame that a 3D display splits in half. If the picture isn't 16:9 the
# player pillarboxes it, the halves no longer line up with the screen halves, and the 3D breaks.
_SPLIT_LAYOUTS = ("Half SBS", "Full SBS", "Half Top", "Full Top", "Cross")


def build_args(s, input_path, output_dir, preview=False):
    """Translate Stereo3D Studio settings dict -> iw3 argparse Namespace (without state)."""
    parser = create_parser(required_true=False)
    layout = dict(LAYOUTS.get(s["layout"], {}))
    flags = dict(half_sbs=False, tb=False, half_tb=False, vr180=False, cross_eyed=False,
                 rgbd=False, half_rgbd=False, anaglyph=None)
    flags.update(layout)

    gpu = int(s["gpu"])
    if gpu >= 0 and not torch.cuda.is_available():
        gpu = -1
    codec = s["video_codec"]
    if codec in ("h264_nvenc", "hevc_nvenc") and not nvenc_available():
        codec = "libx264" if codec == "h264_nvenc" else "libx265"
    preset = s["enc_preset"]
    nv = codec.endswith("_nvenc")
    if nv and not preset.startswith("p"):
        preset = "p4"
    if not nv and preset.startswith("p"):
        preset = "medium"
    video_format = s["video_format"]
    if video_format == "avi" and codec not in ("utvideo", "ffv1"):
        codec = "utvideo"
    if video_format != "avi" and codec in ("utvideo",):
        video_format = "avi"

    # Processing size: scale tall videos down first (4K at full size is ~4x slower and can overflow VRAM),
    # and shrink the batch for anything bigger than 1080p so it stays inside GPU memory.
    batch = int(s["batch_size"])
    vf = ""
    pad_mode = "tblr"
    max_h = int(s.get("max_height", 1080) or 0)
    info = _video_info(input_path)
    if info:
        src_w, src_h, sar, pix_fmt = info
        # One plain "scale=W:H" with numbers: it works both in FFmpeg and in the GPU-decode (NVDEC) filter path,
        # which supports only a few filters and no SAR expressions.
        work_h = min(src_h, max_h) if max_h else src_h
        work_h -= work_h % 2
        work_w = round(src_w * sar * work_h / src_h / 2) * 2     # square pixels (DVD 720x480 at 8:9 -> 640x480)
        if (work_w, work_h) != (src_w, src_h):
            vf = f"scale={work_w}:{work_h}:flags=bicubic"
        if work_h > 1100:
            batch = max(1, round(batch * (1080 / work_h) ** 2))
        # 4:3 (or any picture narrower than 16:9): add black side bars to each eye so the frame is 16:9
        if s.get("pad_16x9", True) and s["layout"].startswith(_SPLIT_LAYOUTS) and src_w * sar / src_h < 16 / 9 - 0.02:
            pad_mode = "16:9"

    parser.set_defaults(
        input=input_path,
        vf=vf,
        pad_mode=pad_mode,
        output=output_dir,
        yes=True,
        gpu=[gpu],
        depth_model=s["depth_model"],
        resolution=(int(s["resolution"]) or None),
        method=s["method"],
        divergence=float(s["divergence"]),
        convergence=float(s["convergence"]),
        foreground_scale=float(s["foreground_scale"]),
        edge_dilation=int(s["edge_dilation"]),
        ipd_offset=float(s["ipd_offset"]),
        synthetic_view=s["synthetic_view"],
        preserve_screen_border=bool(s["preserve_screen_border"]),
        depth_aa=bool(s["depth_aa"]) and is_depth_aa_supported(s["depth_model"]),
        tta=bool(s["tta"]),
        video_format=video_format,
        video_codec=codec,
        crf=int(s["crf"]),
        preset=preset,
        pix_fmt=s["pix_fmt"],
        max_fps=(1000.0 if s["keep_source_fps"] else float(s["max_fps"])),
        ema_normalize=bool(s["ema_normalize"]),
        ema_decay=float(s["ema_decay"]),
        scene_detect=bool(s["scene_detect"]) and not preview,
        hwaccel=("cuda" if (s["hwaccel_decode"] and gpu >= 0 and _nvdec_ok(info)) else None),
        autocrop=(s["autocrop"] or None),
        format=("png" if preview else s["image_format"]),
        batch_size=batch,
        low_vram=bool(s["low_vram"]),
        disable_amp=not bool(s["fp16"]),
        max_workers=int(s["max_workers"]),
        cuda_stream=bool(s["cuda_stream"]) and gpu >= 0,
        recursive=bool(s["recursive"]) and path.isdir(input_path),
        resume=False,                 # always render from scratch; never skip/continue by file name
        disable_scene_cache=True,     # don't reuse scene data cached under the movie's name
        skip_error=True,
        metadata=("filename" if s["metadata_in_name"] else None),
        **flags,
    )
    return parser.parse_args([])


# ---------------------------------------------------------------- model name in output file names
_orig_make_output_filename = _iw3_utils.make_output_filename


def _make_output_filename(input_filename, args, video=False):
    name = _orig_make_output_filename(input_filename, args, video=video)
    base = path.splitext(path.basename(input_filename))[0]
    base = base.translate({ord(c): ord("_") for c in _iw3_utils.SMB_INVALID_CHARS})
    tag = f"_{args.depth_model}"
    if name.startswith(base) and tag not in name[len(base):]:
        name = base + tag + name[len(base):]
    # never overwrite an earlier output: add _01, _02, ... to the end
    out_dir = getattr(args, "output", None)
    if out_dir and not path.splitext(out_dir)[1] and path.exists(path.join(out_dir, name)):
        root, ext = path.splitext(name)
        for i in range(1, 1000):
            cand = f"{root}_{i:02d}{ext}"
            if not path.exists(path.join(out_dir, cand)):
                name = cand
                break
    return name


_iw3_utils.make_output_filename = _make_output_filename

# ---------------------------------------------------------------- settings stored inside output videos
import json as _json
import nunif.utils.video.processor as _VP

META_MARKER = "StereoStudio-settings:"
_META = {"comment": None}


class _AvShim:
    """Forwards to PyAV; output containers opened by the video processor get our settings comment."""

    def __init__(self, real):
        self._real = real

    def open(self, *args, **kwargs):
        c = self._real.open(*args, **kwargs)
        mode = kwargs.get("mode", args[1] if len(args) > 1 else "r")
        if mode == "w" and _META["comment"]:
            try:
                c.metadata["comment"] = _META["comment"]
            except Exception:
                pass
        return c

    def __getattr__(self, name):
        return getattr(self._real, name)


if not isinstance(_VP.av, _AvShim):
    _VP.av = _AvShim(_VP.av)

# settings that describe the conversion (not folders or window state)
_META_SKIP = {"output_dir", "recursive", "resume", "metadata_in_name", "live_view", "live_every",
              "live_mode", "reel_total", "reel_clip", "reel_moments", "settings_version"}


def settings_comment(settings, source_name):
    from . import VERSION
    data = {k: v for k, v in settings.items() if k not in _META_SKIP and not k.startswith("title_")}
    return META_MARKER + _json.dumps({"app": "Stereo3D Studio", "version": VERSION, "source": source_name,
                                      "settings": data}, separators=(",", ":"))


def read_settings_from_video(p):
    """Return (settings dict, info dict) if `p` was made by Stereo3D Studio, else None."""
    try:
        import av
        with av.open(p) as c:
            for key in ("comment", "COMMENT", "description"):
                v = c.metadata.get(key)
                if v and v.startswith(META_MARKER):
                    info = _json.loads(v[len(META_MARKER):])
                    return info.get("settings", {}), info
    except Exception:
        pass
    return None


# ---------------------------------------------------------------- live preview tap
import nunif.utils.video as _VU
from types import GeneratorType as _Gen

_LIVE = {"sink": None, "every": 100, "max_w": 1280, "title": None}   # sink(pil_image, frame_number) or None


def _frame_to_pil(f, max_w=1280):
    """Finished stereo frame (torch RGB tensor, TensorFrame or av.VideoFrame) -> small PIL image."""
    from PIL import Image
    if hasattr(f, "to_image"):
        im = f.to_image()
    else:
        x = getattr(f, "planes", f)
        if not torch.is_tensor(x):
            return None
        with torch.no_grad():
            x = x.detach()
            if x.ndim == 4:
                x = x[0]
            if x.ndim != 3 or x.shape[0] not in (3, 4):
                return None
            x = x[:3]
            h, w = x.shape[-2:]
            if w > max_w:
                x = torch.nn.functional.interpolate(x.unsqueeze(0).float(), size=(max(1, round(h * max_w / w)), max_w),
                                                    mode="area").squeeze(0)
            x = x.float()
            if x.max() > 1.5:          # 8/16-bit integer data
                x = x / (65535.0 if x.max() > 255.5 else 255.0)
            arr = (x.clamp(0, 1) * 255.0 + 0.5).to(torch.uint8).permute(1, 2, 0).cpu().numpy()
        return Image.fromarray(arr, "RGB")
    if im.width > max_w:
        im = im.resize((max_w, max(1, round(im.height * max_w / im.width))))
    return im


class _TapCallback:
    """Wraps iw3's per-frame callback and hands every Nth finished stereo frame to the UI."""

    def __init__(self, inner):
        self.inner = inner
        self.n = 0

    def __call__(self, frame):
        out = self.inner(frame)
        sink, title = _LIVE["sink"], _LIVE["title"]
        if (sink is None and title is None) or out is None:
            return out
        frames = list(out) if isinstance(out, _Gen) else (list(out) if isinstance(out, (list, tuple)) else [out])
        for i, f in enumerate(frames):
            if title is not None:                    # title overlay in both eyes
                try:
                    frames[i] = f = title.apply(f, self.n)
                except Exception:
                    pass
            self.n += 1
            if sink is None:
                continue
            every = max(1, int(_LIVE["every"]))
            if self.n == 1 or self.n % every == 0:
                try:
                    im = _frame_to_pil(f, max_w=_LIVE["max_w"])
                    if im is not None:
                        sink(im, self.n)
                except Exception:
                    pass
        return frames

    def __getattr__(self, name):
        return getattr(self.inner, name)


def _install_live_tap():
    if getattr(_VU.process_video, "_stereo3dstudio_tap", False):
        return
    original = _VU.process_video

    def process_video(*args, **kwargs):
        if "frame_callback" in kwargs and kwargs["frame_callback"] is not None:
            kwargs["frame_callback"] = _TapCallback(kwargs["frame_callback"])
        elif len(args) >= 3:
            args = list(args)
            args[2] = _TapCallback(args[2])
        return original(*args, **kwargs)

    process_video._stereo3dstudio_tap = True
    _VU.process_video = process_video


_install_live_tap()


class ProgressBar:
    """tqdm-compatible object handed to iw3; forwards to callbacks."""

    def __init__(self, sink, **kwargs):
        self.sink = sink
        self.total = kwargs.get("total") or 0
        self.desc = kwargs.get("desc") or ""
        self.n = 0
        self.t0 = time.time()
        self.sink("start", self.desc, 0, self.total)

    def update(self, n=1):
        self.n += n
        self.sink("update", self.desc, self.n, self.total)

    def set_description(self, desc=None, refresh=True):
        self.desc = desc or ""

    def set_postfix(self, *a, **k):
        pass

    def refresh(self):
        pass

    def close(self):
        self.sink("close", self.desc, self.n, self.total)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class Converter:
    """Runs a queue of jobs on a background thread, reusing the loaded depth model."""

    def __init__(self, on_progress, on_item, on_log, on_done, on_frame=None):
        self.on_progress = on_progress   # (phase, desc, n, total)
        self.on_item = on_item           # (index, status, message)
        self.on_log = on_log             # (text)
        self.on_done = on_done           # (stopped: bool)
        self.on_frame = on_frame         # (pil_image, frame_no, layout) live preview
        self.stop_event = threading.Event()
        self.suspend_event = threading.Event()
        self.suspend_event.set()
        self.thread = None
        self._depth_model = None
        self._depth_key = None

    # ---- control
    def running(self):
        return self.thread is not None and self.thread.is_alive()

    def stop(self):
        self.stop_event.set()
        self.suspend_event.set()

    def pause(self, paused):
        if paused:
            self.suspend_event.clear()
        else:
            self.suspend_event.set()

    def start(self, jobs, settings, output_dir):
        """jobs: list of (index, input_path)."""
        self.stop_event.clear()
        self.suspend_event.set()
        self.thread = threading.Thread(target=self._run, args=(jobs, dict(settings), output_dir), daemon=True)
        self.thread.start()

    def free_model(self):
        self._depth_model = None
        self._depth_key = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    # ---- worker
    def _prepare(self, settings, input_path, output_dir, preview=False):
        args = build_args(settings, input_path, output_dir, preview=preview)
        key = (args.depth_model, tuple(args.gpu), args.resolution)
        if key != self._depth_key:
            self.free_model()
        set_state_args(args, stop_event=self.stop_event, suspend_event=self.suspend_event,
                       tqdm_fn=lambda **kw: ProgressBar(self.on_progress, **kw),
                       depth_model=self._depth_model)
        self._depth_model = args.state["depth_model"]
        self._depth_key = key
        # a reused model may still carry video smoothing state; video jobs re-enable it themselves
        try:
            if self._depth_model.loaded():
                self._depth_model.reset()
            self._depth_model.disable_ema()
        except Exception:
            pass
        return args

    def set_live_max_width(self, w):
        _LIVE["max_w"] = int(w)

    def set_live_every(self, n):
        _LIVE["every"] = max(1, int(n))

    def _run(self, jobs, settings, output_dir):
        stopped = False
        layout = settings.get("layout", "")
        if self.on_frame is not None:
            _LIVE["sink"] = lambda im, n: self.on_frame(im, n, layout)
        try:
            for job in jobs:
                index, input_path = job[0], job[1]
                opts = job[2] if len(job) > 2 else {}
                if self.stop_event.is_set():
                    stopped = True
                    break
                if opts.get("sizzle") or opts.get("moments"):
                    total_clip = opts.get("sizzle") or (0, 0)
                    stopped = self._run_sizzle(index, input_path, settings, output_dir, *total_clip,
                                               moments=opts.get("moments"))
                    if stopped:
                        break
                    continue
                self.on_item(index, "Working", "in progress — output is named _tmp_… until finished")
                t0 = time.time()
                try:
                    os.makedirs(output_dir, exist_ok=True)
                    args = self._prepare(settings, input_path, output_dir)
                    if not self._depth_model.loaded():
                        self.on_log(f"Loading depth model {args.depth_model} (first run downloads it)…")
                    self.on_log(f"▶ {path.basename(input_path)}")
                    self._convert_with_recovery(settings, input_path, output_dir, args)
                    if self.stop_event.is_set():
                        self.on_item(index, "Stopped", "")
                        stopped = True
                        break
                    dt = time.time() - t0
                    self.on_item(index, "Done", f"{dt:.1f}s")
                    self.on_log(f"✔ {path.basename(input_path)} — {dt:.1f}s")
                except Exception as e:  # noqa
                    self.on_item(index, "Error", str(e))
                    self.on_log(f"✖ {path.basename(input_path)}: {e}\n{traceback.format_exc()}")
        finally:
            _LIVE["sink"] = None
            _LIVE["title"] = None
            self.on_done(stopped)

    # ---- conversion preview (sizzle reel)
    def _run_sizzle(self, index, input_path, settings, output_dir, total_sec, clip_sec, moments=None):
        """Build a short 2D reel of random moments (or your own `moments`), convert it, return True if stopped."""
        import shutil
        import tempfile
        from .sizzle import build_sizzle
        stem = path.splitext(path.basename(input_path))[0]
        tmp_dir = tempfile.mkdtemp(prefix="Stereo3DStudio_reel_")
        kind = "moments-preview" if moments else "conversion-preview"
        moments_in = list(moments) if moments else None
        reel = path.join(tmp_dir, f"{stem}_{kind}.mp4")
        t0 = time.time()
        try:
            self.on_item(index, "Working", "cutting your moments…" if moments else "picking preview moments…")
            if moments:
                self.on_log(f"▶ Moments preview of {path.basename(input_path)}: {len(moments)} moments, "
                            f"{sum(b for _, b in moments):g}s")
            else:
                self.on_log(f"▶ Conversion preview of {path.basename(input_path)}: "
                            f"{total_sec:g}s from {clip_sec:g}s moments")
            bar = ProgressBar(self.on_progress, total=1, desc=f"{stem}: picking moments")
            moments = build_sizzle(input_path, reel, total_sec, clip_sec, stop_event=self.stop_event, moments=moments,
                                   progress=lambda d, t: (setattr(bar, "total", t), setattr(bar, "n", d - 1),
                                                          bar.update(1)))
            bar.close()
            given = len(moments_in) if moments_in else 0
            if given and len(moments) < given:
                self.on_log(f"{given - len(moments)} moment(s) start after this video ends — skipped.")
            self.on_log("Moments used: " + ", ".join(
                f"{int(st // 3600)}:{int(st % 3600 // 60):02d}:{int(st % 60):02d}" for st, _ in moments))
            self.on_item(index, "Working", "converting preview…")
            os.makedirs(output_dir, exist_ok=True)
            args = self._prepare(settings, reel, output_dir)
            self._convert_with_recovery(settings, reel, output_dir, args)
            if self.stop_event.is_set():
                self.on_item(index, "Stopped", "")
                return True
            outs = sorted((f for f in os.listdir(output_dir)
                           if f.startswith(f"{stem}_{kind}") and not f.startswith("_tmp_")),
                          key=lambda f: os.path.getmtime(path.join(output_dir, f)))
            name = outs[-1] if outs else f"{stem}_{kind}"
            self.on_item(index, "Preview ready", name)
            what = "Moments preview" if moments_in else "Conversion preview"
            self.on_log(f"✔ {what} saved: {path.join(output_dir, name)} — {time.time() - t0:.1f}s")
        except Exception as e:  # noqa
            if self.stop_event.is_set():
                self.on_item(index, "Stopped", "")
                return True
            self.on_item(index, "Error", str(e))
            self.on_log(f"✖ Conversion preview of {path.basename(input_path)}: {e}\n{traceback.format_exc()}")
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        return False

    # ---- recovery
    GPU_MEMORY_HINTS = ("out of memory", "device not ready", "gpu mapping", "cublas_status_alloc",
                        "cudnn_status_alloc", "cudaerrormemoryallocation", "failed to allocate")

    @classmethod
    def is_gpu_memory_error(cls, e):
        m = str(e).lower()
        return any(h in m for h in cls.GPU_MEMORY_HINTS)

    def _convert_with_recovery(self, settings, input_path, output_dir, args):
        """Run iw3; on NVENC or GPU-memory failures retry with safer settings instead of failing."""
        gpu_retries = 0
        while True:
            try:
                _META["comment"] = settings_comment(settings, path.basename(input_path))
                try:
                    from .title import TitleOverlay
                    _LIVE["title"] = TitleOverlay.create(settings, input_path) if is_video(input_path) else None
                except Exception as e:
                    _LIVE["title"] = None
                    self.on_log(f"Title skipped: {e}")
                iw3_main(args)
                return
            except Exception as e:
                if self.stop_event.is_set():
                    raise
                msg = str(e).lower()
                if "nvenc" in msg and settings["video_codec"].endswith("nvenc"):
                    fallback = "libx265" if "hevc" in settings["video_codec"] else "libx264"
                    self.on_log(f"NVENC could not start ({e}). Retrying with {fallback}…")
                    settings = dict(settings, video_codec=fallback, enc_preset="medium")
                elif self.is_gpu_memory_error(e) and gpu_retries < 2:
                    gpu_retries += 1
                    if gpu_retries == 1:
                        settings = dict(settings, max_workers=0, cuda_stream=False,
                                        batch_size=max(1, int(settings["batch_size"]) // 2))
                        note = (f"worker threads off, CUDA streams off, batch size {settings['batch_size']}")
                    else:
                        settings = dict(settings, low_vram=True, batch_size=1)
                        note = "Low VRAM mode, batch size 1"
                    self.on_log(f"GPU ran out of memory ({str(e).splitlines()[0]}). "
                                f"Freeing VRAM and restarting this file with {note}…")
                    self.free_model()
                    try:
                        torch.cuda.synchronize()
                    except Exception:
                        pass
                else:
                    if self.is_gpu_memory_error(e):
                        raise RuntimeError(
                            f"{str(e).splitlines()[0]} — the GPU ran out of memory even with safe settings. "
                            "Restart Stereo3D Studio, then use a smaller depth model or lower Depth resolution.") from e
                    raise
                args = self._prepare(settings, input_path, output_dir)

    # ---- preview (synchronous, call from a worker thread)
    def render_preview(self, settings, input_path, out_dir, time_sec=None):
        """Converts one image (or one video frame) and returns path to the stereo PNG."""
        from PIL import Image
        os.makedirs(out_dir, exist_ok=True)
        for f in os.listdir(out_dir):
            try:
                os.remove(path.join(out_dir, f))
            except OSError:
                pass
        src = input_path
        if is_video(input_path):
            src = path.join(out_dir, "frame.png")
            grab_frame(input_path, time_sec or 0.0).save(src)
        elif not is_image(input_path):
            raise ValueError("Preview needs an image or video")
        s = dict(settings)
        s["layout"] = "Full SBS (VR players, double width)"   # preview always renders full SBS
        result_dir = path.join(out_dir, "result")
        args = self._prepare(s, src, result_dir, preview=True)
        self.stop_event.clear()
        iw3_main(args)
        outs = [path.join(result_dir, f) for f in os.listdir(result_dir)] if path.isdir(result_dir) else []
        if not outs:
            raise RuntimeError("Preview produced no output")
        im = Image.open(outs[0])
        im.load()
        return im


def grab_frame(video_path, time_sec):
    import av
    with av.open(video_path) as container:
        stream = container.streams.video[0]
        if time_sec and stream.time_base:
            container.seek(int(time_sec / stream.time_base), stream=stream, any_frame=False, backward=True)
        for frame in container.decode(stream):
            if frame.time is None or frame.time >= (time_sec or 0) - 0.05:
                return frame.to_image().convert("RGB")
        raise RuntimeError("Could not read a frame")


def video_duration(video_path):
    try:
        import av
        with av.open(video_path) as c:
            if c.duration:
                return c.duration / 1_000_000
            s = c.streams.video[0]
            if s.duration and s.time_base:
                return float(s.duration * s.time_base)
    except Exception:
        pass
    return 0.0
