# Changelog

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
