# Changelog

## 1.3
- **SHARP 3D scene (experimental)** — a new stereo method using Apple's SHARP: each picture becomes a 3D scene of
  Gaussian splats, filmed by two virtual cameras, so edges and revealed areas come from real geometry instead of
  shifted pixels. Works on images, folders and videos (frame by frame, with sound; the depth range is smoothed
  between frames), with 3D strength, Screen plane, all layouts except VR180, the 16:9 side bars, two-file saving,
  Preview frame and Conversion / Moments preview. It's slow on video — seconds per frame.
- Stereo3D Studio renders SHARP's splats with its own PyTorch renderer, so nothing has to be compiled.
- SHARP's weights (2.7 GB, Apple research-use-only license) download in the Models window.
- **Standard Windows setup wizard** (Stereo3DStudio_v1.3_Setup.exe): per-user install without admin rights, live
  setup log, Start-menu entry and uninstall from Windows Settings → Apps. Updating into the same folder always keeps
  your downloaded models; the uninstaller asks before deleting them.

## 1.2
- **Lotus depth** (lotus-depth-d-v2-0-disparity, the model behind kijai's ComfyUI-Lotus): very fine, crisp depth
  for photos and stills, and it works well for video too (slower). Downloads automatically on first use
  (about 3.8 GB, Apache-2.0).
- New preset **Images · Lotus (sharp detail)**: Lotus at depth resolution 1036, flip TTA, edge fix 1,
  MLBW L2 + inpaint, Half SBS.
- Adding images switches to that preset automatically; adding videos afterwards switches back to your previous
  settings. Turn it off in Settings → Files.
- **Lotus-2 (experimental, images only):** the FLUX.1-dev-based successor to Lotus, for the most detailed depth.
  One-time guided setup in Models → “Set up Lotus-2 (experimental)…”: needs a Hugging Face token with the
  FLUX.1-dev license accepted; downloads ~34 GB, converts the model to 4-bit so it fits 16 GB GPUs, then keeps
  about 7 GB. Minutes per image.
- Lotus download shows its progress (queue status and log) the first time it's used.
- New output layout **Depth map only** — just the greyscale depth map, for images and videos (`name_DEPTH`).
- New **Save images as** option (Settings → Files): one 3D image, two images (left + right eye, `name_L` /
  `name_R`), or two images (colour + depth map, `name_RGB` / `name_DEPTH`).
- Fixed: images that aren't 16:9 (4:3, 3:2, portrait) now get side bars in each eye like videos, so side-by-side 3D
  lines up on the Odyssey 3D.
- Cleaner load screen: no light gradient around the edges.

## 1.1
- **Apple Depth Pro 2** depth models: Small, Base, Large and Huge+. Sharp edges and temporally stable depth
  for video — each frame also looks at the 16 frames before it, so the depth doesn't flicker. Download them in
  the Models window (Apple ML Research Model License: research use only, non-commercial).
- The Models window shows each model's own license.
- **Moments preview** for A/B testing: place your own moments on a new filmstrip timeline (under the Reel)
  and convert just those. The moments stay fixed and are shared by every clip in the queue, so you can rerun
  them with another model or settings and compare like for like; each run is kept (`_01`, `_02`…).
  Thanks to [u/pagineinternet](https://www.reddit.com/user/pagineinternet/) on Reddit for the idea!
- The load screen no longer shows "Loading GPU engine…".

## 1.0.3
- Fixed "Invalid argument returned 22" on some phone and stock videos (full-range `yuvj420p`, 4:2:2, 4:4:4):
  these now decode on the CPU, because the engine's GPU-decode path only supports standard 4:2:0 video.

## 1.0.2
- **4:3 videos now convert correctly** (DVDs, classic cartoons and TV). Each eye gets black side bars so the
  side-by-side / top-bottom frame is 16:9: 3D displays split the screen in half, and a 4:3 frame that the player
  shrank to fit put each eye in the wrong place. Video tab: "Fit 4:3 videos to 16:9" (on by default).
- Non-square-pixel videos (DVD 720×480 / 720×576) are converted to square pixels first, so the picture keeps its
  real shape instead of looking stretched.

## 1.0.1
- New **Processing size** setting (Video tab), default 1080p: 4K videos are scaled down before converting,
  which is several times faster and stays inside GPU memory. Choose 1440p, 4K or Source size for more detail.
- Videos larger than 1080p automatically use a smaller batch so they don't overflow GPU memory.

## 1.0 — first public release
- Windows GPU installer: private Python, PyTorch CUDA build matched to your driver, default depth model.
- Queue with thumbnails, drag & drop, per-row remove, "open folder when done".
- Odyssey 3D presets: Half SBS, Depth Anything V2 Large, MLBW + inpaint, flip TTA.
- Conversion preview reel: random moments spread through a movie, converted with your settings.
- Live view, pinned to the main window or floating.
- Titles: fade in / hold / fade out at the start or end, with font, placement, opacity and 3D depth.
- Frame preview with side-by-side, anaglyph, wiggle and single-eye views.
- Model manager for non-commercial depth models; models folder next to the app.
- Settings stored inside output videos; model name in file names; never overwrites earlier outputs.
- Licensed under the PolyForm Noncommercial License 1.0.0: free for noncommercial use, not for sale.
- NVENC / NVDEC, automatic GPU out-of-memory recovery, live speed graph, render time and ETA.
