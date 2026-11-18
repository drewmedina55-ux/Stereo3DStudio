# Third-party notices

## Bundled in this repository

| Component | Where | License |
|---|---|---|
| nunif / iw3 by nagadomi | `engine/` (unmodified snapshot, commit in `engine/ENGINE_VERSION.txt`) | MIT — `engine/LICENSE`; code nunif itself borrows is listed in `engine/NOTICE` |

## Downloaded by the installer (not redistributed here)

| Component | License |
|---|---|
| Python 3.12 (via uv / python-build-standalone) | PSF License |
| uv (Astral) | MIT / Apache 2.0 |
| PyTorch, torchvision | BSD-3-Clause |
| PySide6 / Qt for Python | LGPL v3 |
| PyAV, FFmpeg libraries | BSD / LGPL |
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
| Depth Anything V3, Depth Pro, ZoeDepth and others | see each model's page |
| iw3 stereo / inpaint / anti-aliasing models (nagadomi) | MIT |

Stereo3D Studio only downloads CC BY-NC models after the user ticks the license box in the Models window
(or answers "Y" in the installer for Depth Anything V2 Large).
