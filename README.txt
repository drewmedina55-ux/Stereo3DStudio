Stereo3D Studio 1.4
2D -> 3D image & video converter with NVIDIA GPU acceleration
Created by Drew Medina - https://drewmedina.com
Made with Claude Opus 5.5

INSTALL
  Setup wizard (Stereo3DStudio_v1.4_Setup.exe): just run it and follow the
  steps. To update, run the newer setup into the same folder - your
  downloaded models are always kept. To repair, run the setup again.
  Uninstall from Windows Settings > Apps (it asks before deleting models).

  Zip package:
  1. Extract this whole folder where you want the app to live
     (e.g. C:\Apps\Stereo3DStudio). Don't move it after installing -
     if you do, just run the installer again.
  2. Double-click "Install Stereo3D Studio.bat".
     It downloads a private Python 3.12, PyTorch with CUDA (picked to
     match your NVIDIA driver), the 3D engine, and the default depth
     model. Nothing is installed system-wide.
  3. Launch Stereo3D Studio from the Desktop / Start-menu shortcut,
     or Stereo3DStudio.exe in this folder.

USING IT
  - Drop images, videos or whole folders onto the window (or onto
    Stereo3DStudio.exe).
  - Pick a preset (star = built-in) or tune the 3D / Video / GPU tabs.
  - "Preview selected" renders one frame and lets you flip between
    side-by-side, anaglyph, wiggle and single-eye views.
  - "Open when done" (next to the output folder) opens the output folder
    once a conversion, reel or whole queue has finished.
  - Default depth model: Depth Anything V2 Large. The installer offers to
    download it (1.3 GB, CC BY-NC 4.0 - personal / non-commercial use).
  - Output names include the depth model, e.g. Movie_Any_V2_L_HSBS.mp4.
  - Every output video stores the settings used. Drag a Stereo3D Studio
    video back into the window to load its settings (it isn't queued).
  - Conversion preview (Reel row): select a video and click it to convert
    a short reel of random moments spread through it (default 60 s made
    of 8 s moments) with the current settings. Saved as
    <name>_conversion-preview_HSBS.mp4; the video stays in the queue.
    Each click picks new moments.
  - Convert to 3D. Outputs go to a "3D" folder next to each source
    unless you choose an output folder. Files are named
    *_HSBS.mp4 (Half SBS) or *_LRF_Full_SBS.mp4 (Full SBS).
  - Pause / Stop work mid-video. The Log button shows details.
  - Live view: a small window that shows a converted frame every 100
    frames while encoding (Parallel, Cross-eyed or Raw). The pin keeps it
    locked to the main window (default); unpin it to drag it anywhere.
  - Finished files leave the queue. Every conversion starts from scratch;
    an existing output is never overwritten - the new one gets _01, _02...
  - The red X on a queue row removes it from the list (never the file).
  - Title tab: add text to converted videos that fades in, holds, then
    fades out - at the start or the end. Pick the font, colour, size,
    placement (centre, top, bottom or a corner), opacity and Depth:
    negative sits behind the screen, 0 on it, positive floats in front.
    The title is drawn into both eyes after conversion, so it stays sharp.

3D OUTPUT MODES  (Settings > 3D > Output layout; sizes for a 1920x1080 source)
  - Half SBS (default)  *_HSBS            1920x1080
      Left | right, each squeezed to half width. For the Odyssey 3D,
      3D TVs and 3D monitors: play fullscreen (VLC) and turn on 3D
      side-by-side in Odyssey 3D Hub.
  - Full SBS            *_LRF_Full_SBS    3840x1080
      Left | right at full resolution, double width. For 3D/VR players.
  - Full Top-Bottom     *_TBF_fulltb      1920x2160
      Left eye on top, right below, full resolution, double height.
  - Half Top-Bottom     *_HTB             1920x1080
      Left on top, right below, each squeezed to half height. For 3D
      TVs and projectors with a top-bottom mode.
  - VR180               *_180x180_LR      5760x2880
      Each eye projected onto a 180-degree half-sphere, side by side.
      For VR headsets (DeoVR, Skybox, Quest...) set to 180 SBS.
  - Cross-eyed          *_RLF_cross       3840x1080
      Full SBS with the eyes swapped, for free-viewing by crossing your
      eyes - no equipment needed.
  - Anaglyph            *_redcyan_dubois  1920x1080
      One red/cyan picture (Dubois colours) for red/cyan glasses.
  - RGB + Depth         *_RGBD            3840x1080
  - Half RGB + Depth    *_HRGBD           1920x1080
      Picture on the left, grey depth map (near = bright) on the right,
      for apps and displays that make their own 3D from depth. Titles
      are not drawn in these two modes.
  - Depth map only      *_DEPTH           1920x1080
      Just the greyscale depth map (near = bright).
  Images can also be saved as two files (Settings > Files > Save images
  as): left + right eye (*_L / *_R) or colour + depth (*_RGB / *_DEPTH).

TIPS
  - SHARP 3D scene (experimental): Settings > 3D > Method > SHARP.
    Apple's SHARP turns each picture (or video frame) into a 3D scene and
    films it with two virtual cameras. For video use the preset
    "Experimental - SHARP 3D scene (Odyssey)" and try a short clip first. Download it once in the Models window
    (2.7 GB, research-use-only license).
  - Images: adding pictures switches to the "Images · Lotus (sharp
    detail)" preset (Lotus depth, very fine detail); adding videos
    switches back. Lotus also works well for video, just slower. The
    first Lotus run downloads about 3.8 GB.
  - Depth maps: choose the "Depth map only" layout to save just the depth
    map of any image or video.
  - Lotus-2 (experimental, images only): Models > Set up Lotus-2. Needs
    a Hugging Face token with the FLUX.1-dev license accepted; about
    34 GB download, 7 GB kept. Minutes per image on a 16 GB GPU.
  - Moments preview (under the Reel): double-click the timeline to add
    your own moments, then convert just those. They stay the same, so
    you can rerun them with another model or settings and compare.
    Thanks to u/pagineinternet on Reddit for the idea!
  - Apple Depth Pro 2 (Models window) gives sharp, stable depth for
    video. Large is a good balance; Huge+ needs a lot of GPU memory.
    Its license allows research use only (non-commercial).
  - 4:3 / DVD videos: keep "Fit 4:3 videos to 16:9" on (Video tab) -
    without the side bars a 3D screen splits the picture in the wrong
    place and the 3D breaks.
  - 4K videos: Video tab > Processing size. 1080p (default) is several
    times faster than 4K; choose 1440p or 4K for more detail.
  - Samsung Odyssey 3D, 3D TVs: Half SBS.  Headsets: VR180 or Full SBS.
  - While a video converts it is written as _tmp_<name>; it gets its
    real name only when finished. Don't judge the _tmp_ file.
  - Defaults are tuned for a 16 GB NVIDIA card + Odyssey 3D: V2 Large,
    MLBW L2 + inpaint, Edge fix 1, depth anti-aliasing, flat screen edges,
    hevc_nvenc p5 + NVDEC, batch 4. Pick "Odyssey 3D - Best" to go back
    (it also turns on Flip TTA).
  - Avoid stacking: Large + depth resolution 770 + inpaint + workers/
    streams together needs more than 16 GB and becomes very slow.
  - Fastest: "Odyssey 3D - Fast". Least flicker: "Video - least flicker".
  - Out of VRAM? Stereo3D Studio retries automatically with safer GPU settings.
    Worker threads + CUDA streams + big batches with Large models use the
    most VRAM; turn those down first if it keeps happening.
  - Larger models (V2 Base/Large, Video Depth Anything Large...) are
    non-commercial: get them once via the Models button (accept license,
    click Download). Others download automatically on first use.

WHERE THINGS LIVE
  App + GPU runtime ....... this folder
  Depth models ............ models folder next to Stereo3DStudio.exe
                            (copy it into a new version's folder to keep
                            your downloads)
  Settings / presets ...... %APPDATA%\Stereo3DStudio
  Logs .................... %LOCALAPPDATA%\Stereo3DStudio\logs
  Installer log ........... install_log.txt (this folder)

TROUBLESHOOTING
  - Header says "No CUDA GPU detected": update your NVIDIA driver,
    then run "Install Stereo3D Studio.bat" again.
  - App won't open: run "Stereo3D Studio (console).bat" to see the error.
  - Uninstall: "Uninstall Stereo3D Studio.bat", then delete this folder.

CREDITS & LICENSES
  Stereo3D Studio (c) 2026 Drew Medina - PolyForm Noncommercial
  License 1.0.0 (see LICENSE): free for noncommercial use; selling it
  or any commercial use is not allowed.
  3D engine: iw3 from nunif by nagadomi (MIT License),
  https://github.com/nagadomi/nunif - bundled unmodified in .\engine
  (see engine\LICENSE, engine\NOTICE, engine\ENGINE_VERSION.txt).
  Depth models are downloaded from their authors and keep their own
  licenses; Depth Anything V2 Base/Large are non-commercial.
  UI: Qt for Python (PySide6, LGPL).
