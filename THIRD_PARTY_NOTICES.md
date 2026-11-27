# Third-party notices

## Bundled in this repository

| Component | Where | License |
|---|---|---|
| nunif / iw3 by nagadomi | `engine/` (unmodified snapshot, commit in `engine/ENGINE_VERSION.txt`) | MIT — `engine/LICENSE`; code nunif itself borrows is listed in `engine/NOTICE` |

| SHARP by Apple | `thirdparty/sharp` (unmodified, commit in `thirdparty/SHARP_VERSION.txt`) | Apple sample code license — `thirdparty/sharp_licenses/LICENSE`, acknowledgements in `ACKNOWLEDGEMENTS` |
| Depth Pro 2 by Apple | `thirdparty/depth_pro_2` (unmodified, commit in `thirdparty/DEPTH_PRO_2_VERSION.txt`) | Apple sample code license — `thirdparty/depth_pro_2_licenses/LICENSE`, acknowledgements in `ACKNOWLEDGEMENTS` |

## Downloaded by the installer (not redistributed here)

| Component | License |
|---|---|
| Python 3.12 (via uv / python-build-standalone) | PSF License |
| uv (Astral) | MIT / Apache 2.0 |
| PyTorch, torchvision | BSD-3-Clause |
| PySide6 / Qt for Python | LGPL v3 |
| PyAV, FFmpeg libraries | BSD / LGPL |
| diffusers, transformers, peft (Hugging Face) — used to run Lotus / Lotus-2 | Apache 2.0 |
| bitsandbytes — 4-bit Lotus-2 | MIT |
| plyfile — used by SHARP's code | GPL-3.0 (installed as a separate package, not bundled) |
| Other Python packages from `engine/requirements.txt` | their respective licenses |

## Depth models (downloaded on first use or from the Models window)

No model weights are included in this repository or in release packages.

| Model | License |
|---|---|
| Depth Anything V2 Small | Apache 2.0 |
| Depth Anything V2 Base / Large, Metric Large | **CC BY-NC 4.0 (non-commercial)** |
| Video Depth Anything Base / Large, Metric | **CC BY-NC 4.0 (non-commercial)** |
| Distill Any Depth Base / Large | see the model page (trained from Depth Anything weights) |
| Ultimate DAV2 (gaming fine-tunes) | **CC BY-NC 4.0 (non-commercial)** |
| Lotus depth (lotus-depth-d-v2-0-disparity, EnVision-Research) — downloaded automatically on first use | Apache 2.0 |
| Empty-prompt text embedding for Lotus (from kijai/ComfyUI-Lotus, downloaded on first use) | see the ComfyUI-Lotus repository |
| Lotus-2 depth weights (EnVision-Research, set up by the user) | Apache 2.0 |
| FLUX.1-dev by Black Forest Labs (base model for Lotus-2, downloaded by the user with their own Hugging Face access) | **FLUX.1 [dev] Non-Commercial License** |
| Apple SHARP (3D scene method) | **Apple Machine Learning Research Model License — research use only, non-commercial** (`thirdparty/sharp_licenses/LICENSE_MODEL`) |
| Apple Depth Pro 2 (S / B / L / H+) | **Apple Machine Learning Research Model License — research use only, non-commercial** (`thirdparty/depth_pro_2_licenses/LICENSE_MODEL`) |
| Depth Anything V3, Depth Pro, ZoeDepth and others | see each model's page |
| iw3 stereo / inpaint / anti-aliasing models (nagadomi) | MIT |

Stereo3D Studio only downloads CC BY-NC models after the user ticks the license box in the Models window
(or answers "Y" in the installer for Depth Anything V2 Large).
