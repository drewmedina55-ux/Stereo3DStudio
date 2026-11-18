"""Installer helper: verifies the GPU runtime and pre-downloads the default models."""
import os
import sys
from os import path

ROOT = path.normpath(path.join(path.dirname(path.abspath(__file__)), ".."))
sys.path[:0] = [path.join(ROOT, "app"), path.join(ROOT, "engine")]
try:
    from stereo3dstudio.migrate import migrate_old_data
    migrate_old_data()
except Exception:
    pass
MODELS = path.join(ROOT, "models")          # next to Stereo3DStudio.exe
try:
    from stereo3dstudio.migrate import migrate_models
    if migrate_models(MODELS, log=lambda m: print(m, flush=True)):
        print("Models moved into", MODELS, flush=True)
except Exception as e:
    print("Model move skipped:", e, flush=True)
os.environ.setdefault("NUNIF_HOME", MODELS)
os.environ.setdefault("TORCH_HOME", path.join(MODELS, "torch"))
os.makedirs(os.environ["NUNIF_HOME"], exist_ok=True)

mode = sys.argv[1] if len(sys.argv) > 1 else "check"

import torch  # noqa: E402

if mode == "check":
    print(f"torch {torch.__version__}  CUDA build {torch.version.cuda}")
    if torch.cuda.is_available():
        p = torch.cuda.get_device_properties(0)
        x = torch.randn(1024, 1024, device="cuda")
        y = (x @ x).sum().item()  # noqa: F841  real kernel launch
        print(f"GPU OK: {p.name}, {p.total_memory / 1024**3:.1f} GB VRAM")
        sys.exit(0)
    print("GPU NOT AVAILABLE - Stereo3D Studio will run on CPU")
    sys.exit(3)

if mode == "models":
    from iw3 import models  # noqa: F401
    from iw3.depth_model_factory import create_depth_model
    from iw3.stereo_model_factory import create_stereo_model
    print("Downloading fallback depth model (Depth Anything V2 Small)...")
    m = create_depth_model("Any_V2_S")
    m.load(gpu=-1)
    if "large" in sys.argv:
        from stereo3dstudio import modelstore as M
        if M.is_installed("Any_V2_L"):
            print("Depth Anything V2 Large is already installed.")
        else:
            print("Downloading Depth Anything V2 Large (1.3 GB, the default model)...")
            last = [-1]

            def prog(d, t):
                if t:
                    pct = int(d * 100 / t) // 10 * 10
                    if pct != last[0]:
                        last[0] = pct
                        print(f"  {pct}%  ({d / 1e9:.2f} / {t / 1e9:.2f} GB)", flush=True)
            M.download("Any_V2_L", progress=prog)
            print("Depth Anything V2 Large installed.")
    print("Downloading stereo model (Row Flow v3)...")
    create_stereo_model("row_flow_v3", divergence=2.0, device_id=-1)
    print("Models ready in", os.environ["NUNIF_HOME"])
