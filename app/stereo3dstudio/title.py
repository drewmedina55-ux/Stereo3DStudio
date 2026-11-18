"""Title overlay: text faded on, held, then faded off at the start or end of a converted video.

The text is drawn into BOTH eyes of the finished stereo frame at the same spot, so it sits on the
screen plane and never gets warped by the depth model."""
import torch

PLACEMENTS = ["Center", "Top", "Bottom", "Top left", "Top right", "Bottom left", "Bottom right"]

TITLE_DEFAULTS = {
    "title_on": False,
    "title_text": "",
    "title_font": "Segoe UI",
    "title_bold": True,
    "title_size": 8.0,          # % of the picture height
    "title_color": "#ffffff",
    "title_shadow": True,
    "title_place": "Center",
    "title_when": "Start",      # Start / End
    "title_offset": 1.0,        # seconds after the start / before the end
    "title_fade_in": 1.0,
    "title_hold": 3.0,
    "title_fade_out": 1.0,
    "title_opacity": 100,       # %
    "title_depth": 0,           # -100 (behind the screen) .. 0 (on the screen) .. 100 (in front)
}

MAX_DISPARITY = 0.03            # eye-width fraction at depth +-100


def video_timing(path, settings):
    """(output fps, approx. output frame count) the way iw3 will write the video."""
    import av
    with av.open(path) as c:
        s = c.streams.video[0]
        fps = float(s.average_rate or s.guessed_rate or 30)
        dur = c.duration / 1_000_000 if c.duration else (float(s.duration * s.time_base) if s.duration else 0.0)
    if not settings.get("keep_source_fps") and fps > float(settings.get("max_fps", 30)):
        fps = float(settings["max_fps"])
    return fps, int(dur * fps)


class TitleOverlay:
    def __init__(self, settings, fps, total_frames):
        self.s = {k: settings.get(k, v) for k, v in TITLE_DEFAULTS.items()}
        self.layout = settings.get("layout", "")
        self.fps = max(1.0, float(fps))
        fi, hold, fo = (max(0.0, float(self.s[k])) for k in ("title_fade_in", "title_hold", "title_fade_out"))
        self.fi, self.hold, self.fo = fi, hold, fo
        length = fi + hold + fo
        off = max(0.0, float(self.s["title_offset"]))
        if self.s["title_when"] == "End":
            self.t0 = max(0.0, total_frames / self.fps - off - length)
        else:
            self.t0 = off
        self.opacity = max(0.0, min(1.0, float(self.s["title_opacity"]) / 100.0))
        self._cache = {}

    @classmethod
    def create(cls, settings, video_path):
        if not settings.get("title_on") or not str(settings.get("title_text", "")).strip():
            return None
        if settings.get("layout", "").startswith(("RGB + Depth", "Half RGB + Depth")):
            return None                                       # would corrupt the depth half
        fps, total = video_timing(video_path, settings)
        return cls(settings, fps, total)

    # ------------------------------------------------------------ timing
    def alpha(self, frame_index):
        t = frame_index / self.fps - self.t0
        if t < 0:
            return 0.0
        if t < self.fi:
            a = t / self.fi if self.fi > 0 else 1.0
        elif t < self.fi + self.hold:
            a = 1.0
        elif t < self.fi + self.hold + self.fo:
            a = 1.0 - (t - self.fi - self.hold) / self.fo if self.fo > 0 else 0.0
        else:
            return 0.0
        a = a * a * (3 - 2 * a)                               # smooth ease in/out
        return a * self.opacity

    # ------------------------------------------------------------ drawing
    def render_rgba(self, w, h, dx=0.0):
        """Title on a transparent w x h picture (one eye at its true aspect), shifted dx px for depth."""
        import numpy as np
        from PySide6.QtGui import QImage, QPainter, QFont, QColor, QFontMetricsF
        from PySide6.QtCore import Qt, QRectF
        img = QImage(w, h, QImage.Format_RGBA8888)
        img.fill(Qt.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        f = QFont(self.s["title_font"])
        f.setPixelSize(max(6, int(h * float(self.s["title_size"]) / 100.0)))
        f.setBold(bool(self.s["title_bold"]))
        p.setFont(f)
        text = str(self.s["title_text"])
        place = self.s["title_place"]
        m = int(h * 0.06)                                     # safe margin
        area = QRectF(m + dx, m, w - 2 * m, h - 2 * m)
        align = {"Center": Qt.AlignCenter, "Top": Qt.AlignTop | Qt.AlignHCenter,
                 "Bottom": Qt.AlignBottom | Qt.AlignHCenter, "Top left": Qt.AlignTop | Qt.AlignLeft,
                 "Top right": Qt.AlignTop | Qt.AlignRight, "Bottom left": Qt.AlignBottom | Qt.AlignLeft,
                 "Bottom right": Qt.AlignBottom | Qt.AlignRight}.get(place, Qt.AlignCenter)
        flags = int(align) | int(Qt.TextWordWrap)
        if self.s["title_shadow"]:
            d = max(1.0, f.pixelSize() * 0.06)
            p.setPen(QColor(0, 0, 0, 170))
            p.drawText(area.translated(d, d), flags, text)
        p.setPen(QColor(self.s["title_color"]))
        p.drawText(area, flags, text)
        p.end()
        ptr = img.constBits()
        arr = np.frombuffer(ptr, dtype=np.uint8, count=img.sizeInBytes()).reshape(h, img.bytesPerLine() // 4, 4)
        return arr[:, :w, :].copy()

    def _layer(self, H, W, device):
        """(rgb, alpha) tensors the size of the whole output frame, title placed in each eye."""
        key = (H, W, str(device))
        if key in self._cache:
            return self._cache[key]
        import numpy as np
        L = self.layout
        depth = max(-100.0, min(100.0, float(self.s["title_depth"]))) / 100.0

        def pair(ew, eh):
            """Left and right eye pictures. In front of the screen = left eye shifted right, right eye left."""
            d = depth * MAX_DISPARITY * ew / 2
            return self.render_rgba(ew, eh, d), self.render_rgba(ew, eh, -d)

        if L.startswith("Half SBS"):
            l, r = pair(W, H)                                 # draw at the eye's true aspect, then squeeze
            full = np.concatenate([_resize(l, W // 2, H), _resize(r, W - W // 2, H)], axis=1)
        elif L.startswith(("Full SBS", "VR180")):
            l, r = pair(W // 2, H)
            full = np.concatenate([l, _resize(r, W - W // 2, H)], axis=1)
        elif L.startswith("Cross"):                           # file is right | left
            l, r = pair(W // 2, H)
            full = np.concatenate([r, _resize(l, W - W // 2, H)], axis=1)
        elif L.startswith("Half Top"):
            l, r = pair(W, H)
            full = np.concatenate([_resize(l, W, H // 2), _resize(r, W, H - H // 2)], axis=0)
        elif L.startswith("Full Top"):
            l, r = pair(W, H // 2)
            full = np.concatenate([l, _resize(r, W, H - H // 2)], axis=0)
        else:                                                 # anaglyph etc.: one picture
            full = self.render_rgba(W, H)
        t = torch.from_numpy(full).to(device).permute(2, 0, 1).float() / 255.0
        out = (t[:3], t[3:4])
        self._cache = {key: out}
        return out

    def apply(self, frame, frame_index):
        """Return the frame with the title blended in (or the frame unchanged)."""
        a = self.alpha(frame_index)
        if a <= 0:
            return frame
        x = getattr(frame, "planes", frame)
        if not torch.is_tensor(x) or x.ndim != 3 or x.shape[0] not in (3, 4):
            return frame
        H, W = x.shape[-2:]
        rgb, al = self._layer(H, W, x.device)
        scale = 255.0 if (x.dtype == torch.uint8 or (x.is_floating_point() and x.max() > 1.5)) else 1.0
        xf = x[:3].float() / scale
        k = al * a
        blended = xf * (1 - k) + rgb * k
        if x.dtype == torch.uint8:
            blended = (blended * 255.0 + 0.5).clamp(0, 255).to(torch.uint8)
        else:
            blended = (blended * scale).to(x.dtype)
        new = torch.cat([blended, x[3:]], dim=0) if x.shape[0] == 4 else blended
        if new is not x and hasattr(frame, "planes"):
            frame.planes = new
            return frame
        return new


def _resize(arr, w, h):
    from PIL import Image
    import numpy as np
    if arr.shape[1] == w and arr.shape[0] == h:
        return arr
    return np.asarray(Image.fromarray(arr, "RGBA").resize((max(1, w), max(1, h)), Image.LANCZOS))
