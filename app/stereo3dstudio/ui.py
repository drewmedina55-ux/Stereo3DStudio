"""Stereo3D Studio main window (PySide6)."""
import os
import sys
import threading
import time
import tempfile
from os import path

from PySide6.QtCore import Qt, QPoint, QRectF, QSize, QObject, Signal, QTimer, QUrl, QSize
from PySide6.QtGui import QIcon, QPixmap, QImage, QDesktopServices, QAction, QColor, QFont
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QGridLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QFileDialog, QLineEdit, QComboBox,
    QDoubleSpinBox, QSpinBox, QSlider, QCheckBox, QTabWidget, QProgressBar, QPlainTextEdit, QSplitter,
    QMessageBox, QInputDialog, QDialog, QButtonGroup, QRadioButton, QFrame, QScrollArea, QSizePolicy,
)

from . import APP_NAME, VERSION, AUTHOR, WEBSITE, ENGINE_CREDIT
from . import settings as S
from . import engine as E
from . import modelstore as M

# Charcoal dashboard look
BG, SIDE, CARD, ROW, FIELD = "#1d1d21", "#151517", "#26262b", "#2f2f35", "#323238"
TXT, MUTED, DIM = "#f4f4f5", "#8c8c96", "#5d5d66"
ACCENT = RED = "#ff4f52"
AMBER, GREEN = "#f7b23b", "#3ad07d"
ACCENT2 = AMBER

STYLE = f"""
* {{ font-family: 'Segoe UI', 'Inter', sans-serif; font-size: 10pt; color: {TXT}; }}
QMainWindow, QDialog {{ background: {BG}; }}
QWidget#side {{ background: {SIDE}; }}
QWidget#content {{ background: {BG}; }}
QFrame#card, QWidget#panel {{ background: {CARD}; border-radius: 16px; border: none; }}
QLabel#logo {{ font-size: 13.5pt; font-weight: 800; }}
QLabel#h1 {{ font-size: 21pt; font-weight: 800; }}
QLabel#h2 {{ font-size: 11.5pt; font-weight: 700; }}
QLabel#big {{ font-size: 23pt; font-weight: 800; }}
QLabel#title {{ font-size: 17pt; font-weight: 800; }}
QLabel#muted, QLabel.muted {{ color: {MUTED}; }}
QLabel#up {{ color: {GREEN}; font-weight: 600; }}
QLabel#section {{ color: {MUTED}; font-size: 8.5pt; font-weight: 600; }}
QLabel#chip {{ background: {CARD}; color: {TXT}; border-radius: 15px; padding: 7px 16px; }}
QLabel#chipwarn {{ background: #3a2226; color: #ff9a9c; border-radius: 15px; padding: 7px 16px; }}
QLabel#datepill {{ border: 1px solid #3a3a42; border-radius: 10px; padding: 7px 12px; color: {MUTED}; }}
QPushButton {{ background: {ROW}; border: none; border-radius: 10px; padding: 7px 14px; }}
QPushButton:hover {{ background: #3a3a41; }}
QPushButton:disabled {{ color: {DIM}; background: #242428; }}
QPushButton#nav {{ background: transparent; text-align: left; padding: 10px 14px; color: {MUTED};
    font-weight: 600; border-radius: 10px; }}
QPushButton#nav:hover {{ background: #1f1f23; color: {TXT}; }}
QPushButton#nav:checked {{ color: {TXT}; background: #222227; }}
QPushButton#navActive {{ background: transparent; text-align: left; padding: 10px 14px; color: {RED};
    font-weight: 700; border-radius: 10px; }}
QPushButton#primary {{ background: {RED}; color: white; font-weight: 700; padding: 9px 22px; }}
QPushButton#primary:hover {{ background: #ff7072; }}
QPushButton#primary:disabled {{ background: #5a2a2c; color: #a07577; }}
QPushButton#go {{ background: {GREEN}; color: #06210f; font-weight: 800; font-size: 11pt; padding: 12px 22px; border-radius: 12px; }}
QPushButton#go:hover {{ background: #5fe39a; }}
QPushButton#go:disabled {{ background: #1f3d2b; color: #4f7a61; }}
QDialog#liveview {{ background: {CARD}; border: 1px solid #3a3a42; }}
QPushButton#liveicon {{ background: transparent; padding: 3px 8px; border-radius: 7px; color: {MUTED}; }}
QPushButton#liveicon:hover {{ background: {ROW}; color: {TXT}; }}
QPushButton#liveicon:checked {{ background: #3b2f35; color: {TXT}; }}
QPushButton#rowx {{ background: transparent; color: {RED}; font-weight: 800; font-size: 11pt; padding: 0; border-radius: 14px; }}
QPushButton#rowx:hover {{ background: {RED}; color: white; }}
QPushButton#danger {{ color: #ff8a8c; }}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{ background: {FIELD}; border: none; border-radius: 9px; padding: 6px 10px; }}
QPlainTextEdit {{ background: {CARD}; border: none; border-radius: 12px; padding: 8px; }}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox QAbstractItemView {{ background: {ROW}; border: none; selection-background-color: #45343a; padding: 4px; }}
QTableWidget {{ background: transparent; border: none; selection-background-color: transparent; }}
QTableWidget::item {{ background: {ROW}; border-bottom: 6px solid {CARD}; padding-left: 10px; }}
QTableWidget::item:selected {{ background: #3b2f35; color: {TXT}; }}
QHeaderView::section {{ background: {CARD}; color: {MUTED}; border: none; padding: 2px 10px 6px 10px;
    font-size: 8.5pt; font-weight: 600; }}
QTabWidget::pane {{ border: none; background: transparent; top: 6px; }}
QTabBar::tab {{ background: transparent; color: {MUTED}; padding: 6px 16px; border-radius: 9px; margin-right: 4px; font-weight: 600; }}
QTabBar::tab:selected {{ background: {ROW}; color: {TXT}; }}
QProgressBar {{ background: #38383f; border: none; border-radius: 3px; max-height: 6px; text-align: center; color: transparent; }}
QProgressBar::chunk {{ background: {RED}; border-radius: 3px; }}
QSlider::groove:horizontal {{ height: 6px; background: #3a3a41; border-radius: 3px; }}
QSlider::sub-page:horizontal {{ background: {RED}; border-radius: 3px; }}
QSlider::handle:horizontal {{ background: {TXT}; width: 14px; margin: -4px 0; border-radius: 7px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 5px; border: none; background: {FIELD}; }}
QCheckBox::indicator:checked {{ background: {RED}; }}
QScrollArea {{ border: none; background: {CARD}; }}
QScrollBar:vertical {{ background: transparent; width: 8px; margin: 0; }}
QScrollBar::handle:vertical {{ background: #3e3e46; border-radius: 4px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QWidget#form, QWidget#formvp {{ background: {CARD}; }}
QSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{ width: 0; border: none; }}
QToolTip {{ background: {ROW}; color: {TXT}; border: none; padding: 6px; }}
"""


# ---------------------------------------------------------------- dashboard widgets
class Gauge(QProgressBar):
    """Half-circle progress gauge (drop-in QProgressBar)."""

    def __init__(self):
        super().__init__()
        self.setTextVisible(False)
        self.setMinimumSize(190, 118)
        self.setStyleSheet("QProgressBar { background: transparent; max-height: 100000px; }")

    def paintEvent(self, e):
        from PySide6.QtGui import QPainter, QPen
        from PySide6.QtCore import QRectF
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        thick = max(12, int(min(w, h * 2) * 0.09))
        d = min(w - thick - 4, (h - thick / 2 - 4) * 2)
        rect = QRectF((w - d) / 2, thick / 2 + 2, d, d)
        p.setPen(QPen(QColor("#3a3a41"), thick, Qt.SolidLine, Qt.FlatCap))
        p.drawArc(rect, 180 * 16, -180 * 16)
        mx, v = self.maximum() - self.minimum(), self.value() - self.minimum()
        frac = (v / mx) if mx > 0 and v > 0 else 0.0
        if frac > 0:
            p.setPen(QPen(QColor(progress_color(frac)), thick, Qt.SolidLine, Qt.FlatCap))
            p.drawArc(rect, 180 * 16, int(-180 * 16 * frac))
        f = p.font()
        f.setPointSizeF(22)
        f.setWeight(QFont.ExtraBold)
        p.setFont(f)
        p.setPen(QColor(TXT))
        txt = "…" if mx <= 0 else f"{int(round(frac * 100))}"
        tr = QRectF(0, rect.center().y() - 40, w, 44)
        p.drawText(tr, Qt.AlignHCenter | Qt.AlignBottom, txt)
        if mx > 0:
            fm = p.fontMetrics()
            x = w / 2 + fm.horizontalAdvance(txt) / 2 + 2
            f.setPointSizeF(10)
            f.setWeight(QFont.DemiBold)
            p.setFont(f)
            p.setPen(QColor(MUTED))
            p.drawText(QRectF(x, tr.top(), 30, 40), Qt.AlignLeft | Qt.AlignBottom, "%")
        p.end()


class SpeedLine(QWidget):
    """Slowly scrolling green line of conversion speed (fps) over the last couple of minutes."""
    WINDOW = 120.0        # seconds shown across the card

    def __init__(self):
        super().__init__()
        self.points = []  # (time, fps)
        self.setMinimumSize(160, 70)
        self.timer = QTimer(self)
        self.timer.setInterval(100)       # smooth, slow scroll
        self.timer.timeout.connect(self.update)

    def push(self, fps):
        now = time.time()
        self.points.append((now, max(0.0, float(fps))))
        self.points = [pt for pt in self.points if now - pt[0] <= self.WINDOW + 5]
        if not self.timer.isActive():
            self.timer.start()

    def clear(self):
        self.points = []
        self.update()

    def stop(self):
        self.timer.stop()
        self.update()

    def paintEvent(self, e):
        from PySide6.QtGui import QPainter, QPen, QPainterPath, QLinearGradient
        from PySide6.QtCore import QPointF
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        pad = 6
        # faint baseline grid
        p.setPen(QPen(QColor("#303036"), 1, Qt.DashLine))
        for frac in (0.25, 0.5, 0.75):
            y = pad + (h - 2 * pad) * frac
            p.drawLine(0, int(y), w, int(y))
        pts = self.points
        if len(pts) >= 2:
            now = time.time() if self.timer.isActive() else pts[-1][0]
            top = max(v for _, v in pts) * 1.15 or 1.0
            xy = [QPointF(w - (now - t) / self.WINDOW * w, h - pad - (h - 2 * pad) * (v / top)) for t, v in pts]
            path = QPainterPath(xy[0])
            for a, b in zip(xy, xy[1:]):          # smooth curve through the samples
                mx = (a.x() + b.x()) / 2
                path.cubicTo(QPointF(mx, a.y()), QPointF(mx, b.y()), b)
            fill = QPainterPath(path)
            fill.lineTo(xy[-1].x(), h)
            fill.lineTo(xy[0].x(), h)
            fill.closeSubpath()
            g = QLinearGradient(0, 0, 0, h)
            c1 = QColor(GREEN)
            c1.setAlpha(70)
            c2 = QColor(GREEN)
            c2.setAlpha(0)
            g.setColorAt(0, c1)
            g.setColorAt(1, c2)
            p.fillPath(fill, g)
            p.setPen(QPen(QColor(GREEN), 2.4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.drawPath(path)
            p.setBrush(QColor(GREEN))
            p.setPen(Qt.NoPen)
            p.drawEllipse(xy[-1], 3.5, 3.5)
        p.end()


class SpeedBars(QWidget):
    """Little bar chart of recent conversion speed (fps), amber/red like the dashboard."""

    def __init__(self, n=14):
        super().__init__()
        self.n = n
        self.values = []
        self.setMinimumSize(120, 60)

    def push(self, v):
        self.values = (self.values + [max(0.0, float(v))])[-self.n:]
        self.update()

    def clear(self):
        self.values = []
        self.update()

    def paintEvent(self, e):
        from PySide6.QtGui import QPainter
        from PySide6.QtCore import QRectF
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        slot = w / self.n
        bw = max(4.0, slot * 0.55)
        vals = self.values or []
        top = max(vals) if vals else 1.0
        low = min(vals) * 0.6 if vals else 0.0
        for i in range(self.n):
            x = i * slot + (slot - bw) / 2
            j = i - (self.n - len(vals))
            if j < 0:
                bh, col = h * 0.18, QColor("#34343b")
            else:
                bh = max(4.0, h * (0.25 + 0.75 * ((vals[j] - low) / (top - low) if top > low else 1.0)))
                col = QColor(RED if i % 2 else AMBER)
            p.setBrush(col)
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(QRectF(x, h - bh, bw, bh), 2.5, 2.5)
        p.end()


def make_icon(kind, color="#8c8c96", size=18):
    from PySide6.QtGui import QPainter, QPen
    from PySide6.QtCore import QRectF, QPointF
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    c = QColor(color)
    p.setPen(Qt.NoPen)
    p.setBrush(c)
    s = size
    if kind == "convert":           # grid of tiles
        g = s * 0.12
        t = (s - g) / 2
        p.drawRoundedRect(QRectF(0, 0, t, s), 2, 2)
        p.drawRoundedRect(QRectF(t + g, 0, t, t), 2, 2)
        p.drawRoundedRect(QRectF(t + g, t + g, t, t), 2, 2)
    elif kind == "models":          # stacked bars
        for i, ww in enumerate((1.0, 0.75, 0.5)):
            p.drawRoundedRect(QRectF(0, i * s * 0.36, s * ww, s * 0.26), 2, 2)
    elif kind == "live":            # two screens (stereo pair)
        p.drawRoundedRect(QRectF(0, s * 0.22, s * 0.46, s * 0.56), 2, 2)
        p.drawRoundedRect(QRectF(s * 0.54, s * 0.22, s * 0.46, s * 0.56), 2, 2)
    elif kind == "log":             # lines
        for i in range(3):
            p.drawRoundedRect(QRectF(0, s * (0.12 + i * 0.3), s, s * 0.16), 2, 2)
    elif kind == "about":           # circle with i
        p.drawEllipse(QRectF(0, 0, s, s))
        p.setBrush(QColor(SIDE))
        p.drawRoundedRect(QRectF(s * 0.43, s * 0.42, s * 0.14, s * 0.38), 1.5, 1.5)
        p.drawEllipse(QRectF(s * 0.42, s * 0.18, s * 0.16, s * 0.16))
    p.end()
    return QIcon(pm)


def make_avatar(size=64, text="DM"):
    from PySide6.QtGui import QPainter
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#3a3a41"))
    p.drawEllipse(0, 0, size, size)
    f = p.font()
    f.setPointSizeF(size * 0.22)
    f.setWeight(QFont.ExtraBold)
    p.setFont(f)
    p.setPen(QColor(TXT))
    p.drawText(pm.rect(), Qt.AlignCenter, text)
    p.end()
    return pm


ORANGE = "#ff9a2e"


def progress_color(frac):
    """Red below 50 %, orange from 50 %, green when complete."""
    if frac >= 0.999:
        return GREEN
    return ORANGE if frac >= 0.5 else RED


IMAGE_PRESET = "Images · Lotus (sharp detail)"


def _fmt_t(t):
    t = max(0.0, float(t))
    h, m, sec = int(t // 3600), int(t % 3600 // 60), t % 60
    return f"{h}:{m:02d}:{sec:04.1f}" if h else f"{m}:{sec:04.1f}"


class MomentTimeline(QWidget):
    """Filmstrip timeline of the selected video with your own preview moments on it.

    Click or drag on the strip to move the playhead · double-click to add a moment there ·
    drag a moment to move it · drag its edges to change its length · right-click a moment to remove it.
    The moments are shared by every clip in the queue, so the same moments can be converted again with
    another model or other settings for a fair A/B comparison."""
    changed = Signal()                      # moments edited
    playhead_moved = Signal(float)          # seconds
    _thumbs_ready = Signal(int, object)     # generation, [QImage]

    STRIP_H, RULER_H, EDGE = 54, 18, 7

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(self.STRIP_H + self.RULER_H + 6)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.duration = 0.0
        self.moments = []                   # [[start, length], ...]
        self.playhead = 0.0
        self.default_len = 8.0
        self.thumbs = []
        self._gen = 0
        self._drag = None                   # (mode, index, grab offset seconds)
        self._thumbs_ready.connect(self._on_thumbs)

    # ----- data
    def set_video(self, video_path, duration):
        self.duration = max(0.0, float(duration or 0))
        self.playhead = min(self.playhead, self.duration)
        self.thumbs = []
        self._gen += 1
        if video_path and self.duration > 0:
            gen, n = self._gen, 14
            threading.Thread(target=self._load_thumbs, args=(gen, video_path, n), daemon=True).start()
        self.update()

    def _load_thumbs(self, gen, video_path, n):
        imgs = []
        try:
            import av
            with av.open(video_path) as c:
                st = c.streams.video[0]
                st.thread_type = "AUTO"
                for i in range(n):
                    if gen != self._gen:
                        return
                    t = self.duration * (i + 0.5) / n
                    try:
                        c.seek(int(t / st.time_base), stream=st, backward=True, any_frame=False)
                        for fr in c.decode(st):
                            im = fr.to_image()
                            im.thumbnail((160, 90))
                            data = im.convert("RGB").tobytes()
                            imgs.append(QImage(data, im.width, im.height, im.width * 3,
                                               QImage.Format_RGB888).copy())
                            break
                    except Exception:
                        imgs.append(None)
        except Exception:
            pass
        self._thumbs_ready.emit(gen, imgs)

    def _on_thumbs(self, gen, imgs):
        if gen == self._gen:
            self.thumbs = [QPixmap.fromImage(i) if i is not None else None for i in imgs]
            self.update()

    def set_moments(self, moments):
        self.moments = [[float(a), float(b)] for a, b in (moments or [])]
        self.update()

    def get_moments(self):
        return sorted([round(a, 2), round(b, 2)] for a, b in self.moments)

    def set_playhead(self, t, emit=False):
        self.playhead = max(0.0, min(float(t), self.duration))
        self.update()
        if emit:
            self.playhead_moved.emit(self.playhead)

    def add_moment(self, at=None, length=None):
        if self.duration <= 0:
            return
        length = float(length or self.default_len)
        start = self.playhead if at is None else at
        start = max(0.0, min(start, max(0.0, self.duration - length)))
        self.moments.append([start, min(length, self.duration)])
        self.changed.emit()
        self.update()

    def clear_moments(self):
        self.moments = []
        self.changed.emit()
        self.update()

    # ----- geometry
    def _strip(self):
        return QRectF(1, 1, self.width() - 2, self.STRIP_H)

    def _x(self, t):
        r = self._strip()
        return r.left() + r.width() * (t / self.duration if self.duration else 0)

    def _t(self, x):
        r = self._strip()
        return max(0.0, min(self.duration, (x - r.left()) / max(1.0, r.width()) * self.duration))

    def _hit(self, x):
        """(mode, index) under x: 'left'/'right' edge or 'move' body, newest moment first."""
        for i in range(len(self.moments) - 1, -1, -1):
            a, b = self.moments[i]
            x0, x1 = self._x(a), self._x(a + b)
            if abs(x - x0) <= self.EDGE:
                return "left", i
            if abs(x - x1) <= self.EDGE:
                return "right", i
            if x0 < x < x1:
                return "move", i
        return None, -1

    # ----- painting
    def paintEvent(self, _e):
        from PySide6.QtGui import QPainter, QPen, QBrush
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self._strip()
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(FIELD))
        p.drawRoundedRect(r, 8, 8)
        if self.duration <= 0:
            p.setPen(QColor(MUTED))
            p.drawText(r, Qt.AlignCenter, "Select a video in the queue to place your moments")
            return
        # filmstrip
        if self.thumbs:
            p.save()
            from PySide6.QtGui import QPainterPath
            clip = QPainterPath()
            clip.addRoundedRect(r, 8, 8)
            p.setClipPath(clip)
            n = len(self.thumbs)
            for i, pm in enumerate(self.thumbs):
                cell = QRectF(r.left() + r.width() * i / n, r.top(), r.width() / n + 1, r.height())
                if pm is not None and not pm.isNull():
                    sc = max(cell.width() / pm.width(), cell.height() / pm.height())
                    w, h = pm.width() * sc, pm.height() * sc
                    p.drawPixmap(QRectF(cell.center().x() - w / 2, cell.center().y() - h / 2, w, h), pm,
                                 QRectF(pm.rect()))
            p.fillRect(r, QColor(0, 0, 0, 90))
            p.restore()
        # moments
        for i, (a, b) in enumerate(self.moments):
            x0, x1 = self._x(a), self._x(min(a + b, self.duration))
            box = QRectF(x0, r.top() + 2, max(3.0, x1 - x0), r.height() - 4)
            p.setPen(QPen(QColor(ACCENT), 2))
            p.setBrush(QColor(255, 79, 82, 95))
            p.drawRoundedRect(box, 4, 4)
            p.setPen(QColor("#ffffff"))
            f = p.font()
            f.setPointSizeF(8.5)
            f.setBold(True)
            p.setFont(f)
            if box.width() > 18:
                p.drawText(box.adjusted(4, 2, -2, 0), Qt.AlignLeft | Qt.AlignTop, str(i + 1))
        # playhead
        x = self._x(self.playhead)
        p.setPen(QPen(QColor("#ffffff"), 2))
        p.drawLine(int(x), int(r.top()), int(x), int(r.bottom()))
        # ruler
        f = p.font()
        f.setPointSizeF(8)
        f.setBold(False)
        p.setFont(f)
        p.setPen(QColor(MUTED))
        y = r.bottom() + 3
        ticks = 6
        for k in range(ticks + 1):
            t = self.duration * k / ticks
            tx = self._x(t)
            al = Qt.AlignLeft if k == 0 else (Qt.AlignRight if k == ticks else Qt.AlignHCenter)
            box = QRectF(tx - 60 if k else tx, y, 120 if 0 < k < ticks else 60, self.RULER_H)
            if k == ticks:
                box = QRectF(tx - 60, y, 60, self.RULER_H)
            p.drawText(box, al | Qt.AlignVCenter, _fmt_t(t))

    # ----- mouse
    def mousePressEvent(self, e):
        if self.duration <= 0:
            return
        x = e.position().x()
        mode, i = self._hit(x)
        if e.button() == Qt.RightButton:
            if i >= 0:
                del self.moments[i]
                self.changed.emit()
                self.update()
            return
        if mode:
            a, _b = self.moments[i]
            self._drag = (mode, i, self._t(x) - a)
        else:
            self._drag = ("scrub", -1, 0.0)
            self.set_playhead(self._t(x), emit=True)

    def mouseMoveEvent(self, e):
        x = e.position().x()
        if self._drag is None:
            mode, _ = self._hit(x)
            self.setCursor(Qt.SizeHorCursor if mode in ("left", "right") else
                           (Qt.OpenHandCursor if mode == "move" else Qt.PointingHandCursor))
            if mode:
                a, b = self.moments[_]
                self.setToolTip(f"Moment {_ + 1}: {_fmt_t(a)} – {_fmt_t(a + b)}  ({b:.1f} s)\n"
                                "Drag to move · drag an edge to resize · right-click to remove")
            else:
                self.setToolTip("Click to move the playhead · double-click to add a moment here")
            return
        mode, i, off = self._drag
        t = self._t(x)
        if mode == "scrub":
            self.set_playhead(t, emit=True)
            return
        a, b = self.moments[i]
        if mode == "move":
            a = max(0.0, min(t - off, self.duration - b))
        elif mode == "left":
            end = a + b
            a = max(0.0, min(t, end - 0.5))
            b = end - a
        elif mode == "right":
            b = max(0.5, min(t, self.duration) - a)
        self.moments[i] = [a, b]
        self.update()

    def mouseReleaseEvent(self, e):
        if self._drag and self._drag[0] != "scrub":
            self.changed.emit()
        self._drag = None

    def mouseDoubleClickEvent(self, e):
        if self.duration > 0 and self._hit(e.position().x())[0] is None:
            self.add_moment(at=self._t(e.position().x()) - self.default_len / 2)


class ColorBar(QProgressBar):
    """Thin progress bar whose colour follows progress_color()."""

    def __init__(self):
        super().__init__()
        self.setTextVisible(False)
        self._col = None
        self.valueChanged.connect(self._recolor)

    def setMaximum(self, m):
        super().setMaximum(m)
        self._recolor()

    def _recolor(self, *_):
        mx = self.maximum() - self.minimum()
        frac = (self.value() - self.minimum()) / mx if mx > 0 else 0.0
        col = progress_color(frac)
        if col != self._col:
            self._col = col
            self.setStyleSheet(f"QProgressBar::chunk {{ background: {col}; border-radius: 3px; }}")


def logo_pixmap(size):
    """Drew's circular logo at `size` logical pixels (sharp on high-DPI screens)."""
    p = path.normpath(path.join(path.dirname(__file__), "..", "..", "assets", "logo.png"))
    pm = QPixmap(p)
    if pm.isNull():
        return None
    app = QApplication.instance()
    dpr = app.devicePixelRatio() if app else 1.0
    pm = pm.scaled(int(size * dpr), int(size * dpr), Qt.KeepAspectRatio, Qt.SmoothTransformation)
    pm.setDevicePixelRatio(dpr)
    return pm


def card():
    f = QFrame()
    f.setObjectName("card")
    return f


class Bridge(QObject):
    progress = Signal(str, str, int, int)
    item = Signal(int, str, str)
    log = Signal(str)
    done = Signal(bool)
    preview_ready = Signal(object, str)
    live_frame = Signal(object, int, str)
    thumb = Signal(int, object)


class StreamToSignal:
    """Redirects stdout/stderr into the log panel (and a log file)."""

    def __init__(self, bridge, logfile):
        self.bridge = bridge
        self.logfile = logfile
        self._buf = ""

    def write(self, s):
        if not s:
            return 0
        try:
            if self.logfile:
                self.logfile.write(s)
                self.logfile.flush()
        except Exception:
            pass
        # tqdm uses \r for in-place updates; only forward complete, non-progress lines
        self._buf += s
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            line = line.split("\r")[-1].strip()
            if line and "it/s]" not in line and "s/it]" not in line:
                self.bridge.log.emit(line)
        if len(self._buf) > 4000:
            self._buf = self._buf[-1000:]
        return len(s)

    def flush(self):
        pass

    def isatty(self):
        return False


class SliderSpin(QWidget):
    """Slider + numeric box, kept in sync."""

    def __init__(self, lo, hi, step, decimals=2, tip=""):
        super().__init__()
        self.scale = 10 ** decimals
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(int(lo * self.scale), int(hi * self.scale))
        self.spin = QDoubleSpinBox() if decimals else QSpinBox()
        self.spin.setRange(lo, hi)
        self.spin.setSingleStep(step)
        if decimals:
            self.spin.setDecimals(decimals)
        self.spin.setFixedWidth(72)
        lay.addWidget(self.slider, 1)
        lay.addWidget(self.spin)
        self.slider.valueChanged.connect(lambda v: self.spin.setValue(v / self.scale if decimals else v))
        self.spin.valueChanged.connect(lambda v: self._sync_slider(v))
        if tip:
            self.setToolTip(tip)

    def _sync_slider(self, v):
        self.slider.blockSignals(True)
        self.slider.setValue(int(round(v * self.scale)))
        self.slider.blockSignals(False)

    def value(self):
        return self.spin.value()

    def setValue(self, v):
        self.spin.setValue(v)
        self._sync_slider(self.spin.value())


def section(text):
    lbl = QLabel(text.upper())
    lbl.setObjectName("section")
    return lbl


def pil_to_qpixmap(im):
    im = im.convert("RGB")
    data = im.tobytes("raw", "RGB")
    qimg = QImage(data, im.width, im.height, im.width * 3, QImage.Format_RGB888).copy()
    return QPixmap.fromImage(qimg)


# ---------------------------------------------------------------- preview
class PreviewDialog(QDialog):
    def __init__(self, parent, sbs_image, title):
        super().__init__(parent)
        self.setWindowTitle(f"Preview — {title}")
        self.resize(1280, 760)
        w = sbs_image.width // 2
        self.left = sbs_image.crop((0, 0, w, sbs_image.height))
        self.right = sbs_image.crop((w, 0, w * 2, sbs_image.height))
        self.sbs = sbs_image
        self.cache = {}
        self.wiggle_on = False

        lay = QVBoxLayout(self)
        bar = QHBoxLayout()
        self.group = QButtonGroup(self)
        for i, name in enumerate(["Side-by-side", "Anaglyph", "Wiggle", "Left eye", "Right eye"]):
            rb = QRadioButton(name)
            self.group.addButton(rb, i)
            bar.addWidget(rb)
            if i == 0:
                rb.setChecked(True)
        bar.addStretch(1)
        hint = QLabel("Wiggle flips eyes rapidly so you can judge depth on a 2D screen")
        hint.setObjectName("muted")
        bar.addWidget(hint)
        lay.addLayout(bar)
        self.view = QLabel()
        self.view.setAlignment(Qt.AlignCenter)
        self.view.setMinimumSize(400, 240)
        self.view.setStyleSheet("background:#141417;border-radius:8px;")
        lay.addWidget(self.view, 1)
        self.group.idClicked.connect(self.render)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._wiggle)
        self._flip = False
        self.render(0)

    def _anaglyph(self):
        from PIL import Image
        l, r = self.left.convert("RGB"), self.right.convert("RGB")
        lr, _, _ = l.split()
        _, rg, rb = r.split()
        return Image.merge("RGB", (lr, rg, rb))

    def _pix(self, key):
        if key not in self.cache:
            im = {"sbs": self.sbs, "ana": None, "l": self.left, "r": self.right}[key]
            if key == "ana":
                im = self._anaglyph()
            self.cache[key] = pil_to_qpixmap(im)
        return self.cache[key]

    def _show(self, pm):
        self.view.setPixmap(pm.scaled(self.view.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _wiggle(self):
        self._flip = not self._flip
        self._show(self._pix("l" if self._flip else "r"))

    def render(self, mode=None):
        mode = self.group.checkedId() if mode is None else mode
        self.timer.stop()
        if mode == 2:
            self.timer.start(140)
            return
        self._show(self._pix({0: "sbs", 1: "ana", 3: "l", 4: "r"}[mode]))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.group.checkedId() != 2:
            self.render()


# ---------------------------------------------------------------- about
def stereo_eyes(im, L):
    """(left_eye, right_eye) at their true aspect for a converted frame, or None if the layout isn't a stereo pair."""
    w, h = im.size
    if L.startswith("Half SBS"):
        l, r = im.crop((0, 0, w // 2, h)), im.crop((w // 2, 0, w, h))
        return l.resize((w, h)), r.resize((w, h))
    if L.startswith(("Full SBS", "VR180")):
        return im.crop((0, 0, w // 2, h)), im.crop((w // 2, 0, w, h))
    if L.startswith("Half Top"):
        t, b = im.crop((0, 0, w, h // 2)), im.crop((0, h // 2, w, h))
        return t.resize((w, h)), b.resize((w, h))
    if L.startswith("Full Top"):
        return im.crop((0, 0, w, h // 2)), im.crop((0, h // 2, w, h))
    if L.startswith("Cross"):
        return im.crop((w // 2, 0, w, h)), im.crop((0, 0, w // 2, h))   # file is right|left
    return None


class LiveViewWindow(QDialog):
    """Small window showing the latest converted stereo frame. Pinned = locked to the main window."""
    MODES = ["Cross-eyed (eyes swapped)", "Parallel", "Raw output frame"]
    PARALLEL = 1
    closed = Signal()

    def __init__(self, parent, every, on_every, mode=1, on_mode=None, pinned=True, on_pin=None):
        super().__init__(parent, Qt.Tool | Qt.FramelessWindowHint)
        self.setObjectName("liveview")
        self.setModal(False)
        self.setWindowTitle("Live view")
        self.resize(660, 300)
        self.on_every = on_every
        self.on_pin = on_pin
        self.im = None
        self.layout_name = ""
        self.frame_no = 0
        self._drag = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 6, 10, 6)
        lay.setSpacing(6)

        head = QHBoxLayout()
        self.title = QLabel("Live view")
        self.title.setStyleSheet("font-weight: 700;")
        head.addWidget(self.title)
        head.addStretch(1)
        self.b_pin = QPushButton("📌")
        self.b_pin.setObjectName("liveicon")
        self.b_pin.setCheckable(True)
        self.b_pin.setChecked(pinned)
        self.b_pin.toggled.connect(self._pin_changed)
        b_close = QPushButton("✕")
        b_close.setObjectName("rowx")
        b_close.setFixedSize(24, 24)
        b_close.clicked.connect(self.reject)
        for wdg in (self.b_pin, b_close):
            head.addWidget(wdg)
        lay.addLayout(head)

        bar = QHBoxLayout()
        self.cb_mode = QComboBox()
        self.cb_mode.addItems(self.MODES)
        self.cb_mode.setMinimumContentsLength(8)
        self.cb_mode.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.cb_mode.setCurrentIndex(mode if 0 <= mode < len(self.MODES) else self.PARALLEL)
        self.cb_mode.currentIndexChanged.connect(lambda *_: self._render())
        if on_mode:
            self.cb_mode.currentIndexChanged.connect(on_mode)
        self.sp_every = QSpinBox()
        self.sp_every.setRange(10, 5000)
        self.sp_every.setSingleStep(50)
        self.sp_every.setValue(int(every))
        self.sp_every.setFixedWidth(70)
        self.sp_every.valueChanged.connect(lambda v: self.on_every(v))
        self.ck_top = QCheckBox("On top")
        self.ck_top.toggled.connect(self._set_top)
        bar.addWidget(self.cb_mode, 1)
        bar.addWidget(QLabel("every"))
        bar.addWidget(self.sp_every)
        bar.addWidget(QLabel("frames"))
        bar.addWidget(self.ck_top)
        lay.addLayout(bar)
        self.view = QLabel("Waiting for the first converted frame…")
        self.view.setAlignment(Qt.AlignCenter)
        self.view.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)   # pixmap must not resize the window
        self.view.setMinimumSize(200, 90)
        self.view.setStyleSheet("background:#141417;border-radius:6px;color:#8c8c96;")
        lay.addWidget(self.view, 1)
        foot = QHBoxLayout()
        self.info = QLabel("")
        self.info.setObjectName("muted")
        foot.addWidget(self.info, 1)
        from PySide6.QtWidgets import QSizeGrip
        foot.addWidget(QSizeGrip(self), 0, Qt.AlignBottom | Qt.AlignRight)
        lay.addLayout(foot)
        self._pin_changed(pinned, notify=False)

    # ---- pin: locked to the main window vs. free floating
    def pinned(self):
        return self.b_pin.isChecked()

    def _pin_changed(self, on, notify=True):
        self.b_pin.setToolTip("Pinned to the main window — click to let it move freely" if on
                              else "Free floating — drag the header to move it. Click to pin it here")
        self.title.setText("Live view" if on else "Live view  ·  drag to move")
        self.setCursor(Qt.ArrowCursor)
        if notify and self.on_pin:
            self.on_pin(on)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and not self.pinned() and e.position().y() < 34:
            self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._drag is not None:
            self.move(e.globalPosition().toPoint() - self._drag)
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        self._drag = None
        super().mouseReleaseEvent(e)

    def _set_top(self, on):
        self.setWindowFlag(Qt.WindowStaysOnTopHint, on)
        self.show()

    def set_frame(self, im, n, layout_name):
        self.im, self.frame_no, self.layout_name = im, n, layout_name
        self._render()

    def _render(self):
        if self.im is None:
            return
        from PIL import Image
        mode = self.cb_mode.currentIndex()
        eyes = None if mode == 2 else stereo_eyes(self.im, self.layout_name)
        if eyes is None:
            out = self.im
        else:
            l, r = eyes
            first, second = (r, l) if mode == 0 else (l, r)
            gap = max(4, first.width // 60)
            out = Image.new("RGB", (first.width * 2 + gap, first.height), (5, 7, 10))
            out.paste(first.convert("RGB"), (0, 0))
            out.paste(second.convert("RGB"), (first.width + gap, 0))
        pm = pil_to_qpixmap(out)
        self.view.setPixmap(pm.scaled(self.view.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.info.setText(f"Frame {self.frame_no:,}  ·  {self.layout_name}")

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._render()

    def closeEvent(self, e):
        self.closed.emit()
        super().closeEvent(e)

    def reject(self):
        self.closed.emit()
        super().reject()


class ModelManagerDialog(QDialog):
    """Download / import depth models that need a license acceptance."""
    _prog = Signal(int, int)
    _fin = Signal(str, str)   # model, error ('' = ok)

    def __init__(self, parent, focus=None):
        super().__init__(parent)
        self.setWindowTitle("Depth models")
        self.resize(900, 520)
        self.cancel = threading.Event()
        self.busy = None
        lay = QVBoxLayout(self)
        intro = QLabel(
            "These higher-quality depth models are released under a <b>non-commercial or research-only license</b>, "
            "so the 3D engine can't download them automatically. Accept the license below and Stereo3D Studio "
            "fetches them from their official pages. Small models (the default) don't need this.")
        intro.setWordWrap(True)
        lay.addWidget(intro)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Model", "Size", "License", "Status"])
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        for c in (1, 2, 3):
            hh.setSectionResizeMode(c, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.itemSelectionChanged.connect(self._sync)
        lay.addWidget(self.table, 1)
        self.models = list(M.CATALOG.keys())
        for m in self.models:
            r = self.table.rowCount()
            self.table.insertRow(r)
            url, page, lic, size = M.CATALOG[m]
            self.table.setItem(r, 0, QTableWidgetItem(S.DEPTH_MODEL_LABELS.get(m, m)))
            self.table.setItem(r, 1, QTableWidgetItem(size))
            self.table.setItem(r, 2, QTableWidgetItem(lic))
            self.table.setItem(r, 3, QTableWidgetItem(""))
        self.ck_accept = QCheckBox("I accept the model license")
        self.ck_accept.toggled.connect(self._sync)
        self.table.itemSelectionChanged.connect(self._license_text)
        lay.addWidget(self.ck_accept)
        self.pb = QProgressBar()
        self.pb.setVisible(False)
        lay.addWidget(self.pb)
        row = QHBoxLayout()
        self.b_folder = QPushButton("Open models folder")
        self.b_folder.clicked.connect(lambda: QDesktopServices.openUrl(
            QUrl.fromLocalFile(os.environ.get("NUNIF_HOME", ""))))
        self.b_page = QPushButton("Open page")
        self.b_import = QPushButton("Import file…")
        self.b_dl = QPushButton("Download")
        self.b_dl.setObjectName("primary")
        self.b_cancel = QPushButton("Cancel download")
        self.b_close = QPushButton("Close")
        self.b_page.clicked.connect(self._open_page)
        self.b_import.clicked.connect(self._import)
        self.b_dl.clicked.connect(self._download)
        self.b_cancel.clicked.connect(self.cancel.set)
        self.b_close.clicked.connect(self.accept)
        for b in (self.b_page, self.b_import, self.b_folder):
            row.addWidget(b)
        row.addStretch(1)
        for b in (self.b_cancel, self.b_dl, self.b_close):
            row.addWidget(b)
        lay.addLayout(row)
        self._prog.connect(self._on_prog)
        self._fin.connect(self._on_fin)
        self._refresh()
        focus = M.canonical(focus) if focus else None
        self.table.selectRow(self.models.index(focus) if focus in self.models else 0)

    def _refresh(self):
        for r, m in enumerate(self.models):
            ok = M.is_installed(m)
            it = self.table.item(r, 3)
            it.setText("Installed" if ok else ("Downloading…" if m == self.busy else "Not installed"))
            it.setForeground(QColor("#4ade80" if ok else ("#22d3ee" if m == self.busy else "#94a3b8")))
        self._sync()

    def _cur(self):
        rows = self.table.selectionModel().selectedRows()
        return self.models[rows[0].row()] if rows else None

    def _sync(self):
        m = self._cur()
        has_url = bool(m and M.CATALOG[m][0])
        idle = self.busy is None
        self.b_dl.setEnabled(idle and has_url and self.ck_accept.isChecked() and not M.is_installed(m))
        self.b_dl.setToolTip("" if has_url else "No direct download — use Open page, then Import file…")
        self.b_import.setEnabled(idle and m is not None)
        self.b_cancel.setVisible(not idle)
        self.b_close.setEnabled(idle)

    def _license_text(self):
        m = self._cur()
        if m:
            lic = M.CATALOG[m][2]
            self.ck_accept.setText(f"I accept this model's license: {lic}")
            self.ck_accept.setChecked(False)              # accept each license separately

    def _open_page(self):
        m = self._cur()
        if m:
            QDesktopServices.openUrl(QUrl(M.CATALOG[m][1]))

    def _import(self):
        m = self._cur()
        if not m:
            return
        f, _ = QFileDialog.getOpenFileName(self, "Choose the downloaded model file", "",
                                           "Model files (*.pth *.pt *.safetensors)")
        if f:
            try:
                M.import_file(m, f)
            except Exception as e:
                QMessageBox.warning(self, "Import", str(e))
            self._refresh()

    def _download(self):
        m = self._cur()
        if not m:
            return
        self.busy = m
        self.cancel.clear()
        self.pb.setVisible(True)
        self.pb.setRange(0, 0)
        self._refresh()

        def work():
            try:
                M.download(m, progress=lambda d, t: self._prog.emit(int(d // 1048576), int(t // 1048576)),
                           cancel=self.cancel)
                self._fin.emit(m, "")
            except Exception as e:
                self._fin.emit(m, str(e))

        threading.Thread(target=work, daemon=True).start()

    def _on_prog(self, done_mb, total_mb):
        if total_mb:
            self.pb.setRange(0, total_mb)
            self.pb.setValue(done_mb)
            self.pb.setFormat(f"{done_mb} / {total_mb} MB")
        else:
            self.pb.setFormat(f"{done_mb} MB")

    def _on_fin(self, m, err):
        self.busy = None
        self.pb.setVisible(False)
        self._refresh()
        if err and err != "Cancelled":
            QMessageBox.warning(self, "Download failed", err)

    def reject(self):
        if self.busy:
            return
        super().reject()


class AboutDialog(QDialog):
    def showEvent(self, e):
        b = getattr(self, "_body", None)
        if b is not None:                               # styled fonts are known now: fit the wrapped text
            b.ensurePolished()
            b.setMinimumHeight(b.heightForWidth(b.width()))
            self.adjustSize()
        super().showEvent(e)

    def __init__(self, parent, icon_path):
        super().__init__(parent)
        self.setWindowTitle(f"About {APP_NAME}")
        self.setFixedWidth(460)
        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        if icon_path and path.exists(icon_path):
            ic = QLabel()
            ic.setPixmap(QPixmap(icon_path).scaled(72, 72, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            ic.setAlignment(Qt.AlignCenter)
            lay.addWidget(ic)
        t = QLabel(f"<span style='font-size:18pt;font-weight:700'>Stereo3D <span style='color:{ACCENT}'>Studio</span></span>"
                   f"<br><span style='color:#8c8c96'>Version {VERSION}</span>")
        t.setAlignment(Qt.AlignCenter)
        lay.addWidget(t)
        intro = QLabel("2D → 3D image & video converter with GPU acceleration.")
        intro.setAlignment(Qt.AlignCenter)
        lay.addWidget(intro)
        lp = logo_pixmap(104)
        if lp:
            lg = QLabel()
            lg.setPixmap(lp)
            lg.setAlignment(Qt.AlignCenter)
            lay.addSpacing(6)
            lay.addWidget(lg)
        body = QLabel(
            f"Created by <b>{AUTHOR}</b><br>"
            f"<a style='color:{ACCENT}' href='{WEBSITE}'>drewmedina.com</a><br><br>"
            f"Made with <b>Claude Opus 5.5</b><br><br>"
            f"Free for noncommercial use — not for sale<br>"
            f"<span style='color:#8c8c96'>PolyForm Noncommercial License 1.0.0</span><br><br>"
            f"<span style='color:#8c8c96'>{ENGINE_CREDIT}.<br>"
            f"Depth models are downloaded from their authors on first use and keep their own licenses "
            f"(some Depth Anything V2 sizes are non‑commercial).</span>")
        body.setWordWrap(True)
        body.setAlignment(Qt.AlignCenter)
        body.setOpenExternalLinks(True)
        body.setFixedWidth(410)                         # lets the wrapped text report its full height
        self._body = body
        lay.addWidget(body)
        ok = QPushButton("Close")
        ok.clicked.connect(self.accept)
        lay.addWidget(ok, 0, Qt.AlignCenter)


# ---------------------------------------------------------------- main window
class MainWindow(QMainWindow):
    COL_NAME, COL_TYPE, COL_STATUS, COL_INFO, COL_X = range(5)
    THUMB = QSize(80, 45)

    def __init__(self, icon_path=None, log_path=None):
        super().__init__()
        self.icon_path = icon_path
        self.log_path = log_path
        self.setWindowTitle(f"{APP_NAME} {VERSION}")
        if icon_path and path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.resize(1460, 920)
        self.setAcceptDrops(True)

        self.bridge = Bridge()
        self.converter = E.Converter(
            on_progress=self.bridge.progress.emit,
            on_item=self.bridge.item.emit,
            on_log=self.bridge.log.emit,
            on_done=self.bridge.done.emit,
            on_frame=self.bridge.live_frame.emit,
        )
        self.live = None
        self.bridge.live_frame.connect(self.on_live_frame)
        from concurrent.futures import ThreadPoolExecutor
        self._thumb_pool = ThreadPoolExecutor(max_workers=2)
        self.bridge.thumb.connect(self.on_thumb)
        self.bridge.progress.connect(self.on_progress)
        self.bridge.item.connect(self.on_item)
        self.bridge.log.connect(self.append_log)
        self.bridge.done.connect(self.on_done)
        self.bridge.preview_ready.connect(self.on_preview_ready)

        self.items = []           # list of dicts {id, path, type}; row i == items[i]
        self._next_id = 1
        self.job_total = 0
        self.job_done = 0
        self.paused = False
        self._rate = (0.0, 0, 0.0)  # (t, n, fps)
        self._loading = False

        self._build()
        self._apply(S.load_last())
        self._refresh_presets()
        self._update_buttons()

    # ---------- layout
    def _build(self):
        root = QWidget()
        self.setCentralWidget(root)
        rootl = QHBoxLayout(root)
        rootl.setContentsMargins(0, 0, 0, 0)
        rootl.setSpacing(0)

        # ================= sidebar
        side = QWidget()
        side.setObjectName("side")
        side.setFixedWidth(220)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(18, 26, 18, 22)
        sl.setSpacing(4)
        logo_row = QHBoxLayout()
        if self.icon_path and path.exists(self.icon_path):
            ic = QLabel()
            ic.setPixmap(QPixmap(self.icon_path).scaled(28, 28, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            logo_row.addWidget(ic)
        logo = QLabel("Stereo3D Studio")
        logo.setObjectName("logo")
        logo_row.addWidget(logo)
        logo_row.addStretch(1)
        sl.addLayout(logo_row)
        sl.addSpacing(30)

        def nav(text, kind, checkable=False):
            b = QPushButton("  " + text)
            b.setObjectName("nav")
            b.setIcon(make_icon(kind))
            b.setIconSize(QSize(17, 17))
            b.setCheckable(checkable)
            b.setCursor(Qt.PointingHandCursor)
            sl.addWidget(b)
            return b

        b_conv = nav("Convert", "convert")
        b_conv.setObjectName("navActive")
        b_conv.setIcon(make_icon("convert", RED))
        b_models = nav("Models", "models")
        b_models.setToolTip("Download the larger depth models")
        b_models.clicked.connect(lambda: self.open_models())
        self.btn_live = nav("Live view", "live", True)
        self.btn_live.setToolTip("Small window showing a converted SBS frame every N frames while encoding")
        self.btn_live.toggled.connect(self.toggle_live)
        self.btn_log = nav("Log", "log", True)
        self.btn_log.toggled.connect(lambda on: self.log.setVisible(on))
        about = nav("About", "about")
        about.clicked.connect(lambda: AboutDialog(self, self.icon_path).exec())
        sl.addStretch(1)

        lp = logo_pixmap(88)
        if lp:
            lg = QLabel()
            lg.setPixmap(lp)
            lg.setAlignment(Qt.AlignCenter)
            lg.setCursor(Qt.PointingHandCursor)
            lg.setToolTip(WEBSITE)
            lg.mousePressEvent = lambda e: QDesktopServices.openUrl(QUrl(WEBSITE))
            sl.addWidget(lg)
            sl.addSpacing(8)
        sl.addSpacing(22)
        date = QLabel(time.strftime("%d %b %Y").lstrip("0") + f"  ·  v{VERSION}")
        date.setObjectName("datepill")
        date.setAlignment(Qt.AlignCenter)
        sl.addWidget(date)
        rootl.addWidget(side)

        # ================= content
        content = QWidget()
        content.setObjectName("content")
        outer = QVBoxLayout(content)
        outer.setContentsMargins(30, 24, 30, 24)
        outer.setSpacing(18)
        rootl.addWidget(content, 1)

        head = QHBoxLayout()
        tb = QVBoxLayout()
        tb.setSpacing(0)
        h1 = QLabel("Convert")
        h1.setObjectName("h1")
        sub = QLabel("2D → 3D images and video for the Odyssey 3D")
        sub.setObjectName("muted")
        tb.addWidget(h1)
        tb.addWidget(sub)
        head.addLayout(tb)
        head.addStretch(1)
        ok, msg = E.cuda_summary()
        chip = QLabel(("<span style='color:%s'>●</span>&nbsp; " % GREEN if ok else "▲ ") + msg)
        chip.setObjectName("chip" if ok else "chipwarn")
        head.addWidget(chip, 0, Qt.AlignTop)
        outer.addLayout(head)

        body = QHBoxLayout()
        body.setSpacing(18)
        outer.addLayout(body, 1)
        leftc = QVBoxLayout()
        leftc.setSpacing(18)
        rightc = QVBoxLayout()
        rightc.setSpacing(18)
        body.addLayout(leftc, 3)
        body.addLayout(rightc, 2)

        # ----- queue card
        qc = card()
        ql = QVBoxLayout(qc)
        ql.setContentsMargins(20, 16, 20, 14)
        top = QHBoxLayout()
        h = QLabel("Queue")
        h.setObjectName("h2")
        top.addWidget(h)
        top.addStretch(1)
        self.btn_add = QPushButton("+ Files")
        self.btn_add_dir = QPushButton("+ Folder")
        self.btn_remove = QPushButton("Remove")
        self.btn_clear = QPushButton("Clear")
        self.btn_add.clicked.connect(self.add_files_dialog)
        self.btn_add_dir.clicked.connect(self.add_folder_dialog)
        self.btn_remove.clicked.connect(self.remove_selected)
        self.btn_clear.clicked.connect(self.clear_queue)
        for b in (self.btn_add, self.btn_add_dir, self.btn_remove, self.btn_clear):
            top.addWidget(b)
        ql.addLayout(top)
        ql.addSpacing(6)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["File", "Type", "Status", "Info", ""])
        self.table.setIconSize(self.THUMB)
        hh = self.table.horizontalHeader()
        hh.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        for c in (1, 2):
            hh.setSectionResizeMode(c, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.Interactive)
        self.table.setColumnWidth(3, 170)
        hh.setSectionResizeMode(4, QHeaderView.Fixed)
        self.table.setColumnWidth(4, 44)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(58)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.itemSelectionChanged.connect(self._on_selection)
        ql.addWidget(self.table, 1)
        self.drop_hint = QLabel("Drop images, videos or folders anywhere in this window")
        self.drop_hint.setObjectName("muted")
        self.drop_hint.setAlignment(Qt.AlignCenter)
        ql.addWidget(self.drop_hint)
        leftc.addWidget(qc, 1)

        # ----- stats row: speed card + progress gauge card
        stats = QHBoxLayout()
        stats.setSpacing(18)
        sc = card()
        sg = QGridLayout(sc)
        sg.setContentsMargins(20, 16, 20, 16)
        h = QLabel("Speed")
        h.setObjectName("h2")
        sg.addWidget(h, 0, 0)
        self.lbl_cur = QLabel("Idle")
        self.lbl_cur.setObjectName("muted")
        self.lbl_cur.setMinimumWidth(10)
        sg.addWidget(self.lbl_cur, 1, 0, 1, 2)
        self.lbl_speed = QLabel("—")
        self.lbl_speed.setObjectName("big")
        sg.addWidget(self.lbl_speed, 2, 0)
        self.lbl_eta = QLabel("")
        self.lbl_eta.setObjectName("muted")
        sg.addWidget(self.lbl_eta, 3, 0)
        self.lbl_elapsed = QLabel("")
        self.lbl_elapsed.setObjectName("muted")
        sg.addWidget(self.lbl_elapsed, 4, 0)
        self.speed_line = SpeedLine()
        sg.addWidget(self.speed_line, 2, 1, 3, 1)
        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.setInterval(1000)
        self._elapsed_timer.timeout.connect(self._tick_elapsed)
        sg.setColumnStretch(1, 1)
        sg.setColumnMinimumWidth(0, 130)
        stats.addWidget(sc, 1)

        gc = card()
        gl = QVBoxLayout(gc)
        gl.setContentsMargins(20, 16, 20, 14)
        h = QLabel("Progress")
        h.setObjectName("h2")
        gl.addWidget(h)
        self.pb_cur = Gauge()
        gl.addWidget(self.pb_cur, 1)
        qrow = QHBoxLayout()
        self.lbl_queue = QLabel("Queue 0 / 0")
        self.lbl_queue.setObjectName("muted")
        qrow.addWidget(self.lbl_queue)
        self.pb_queue = ColorBar()
        qrow.addWidget(self.pb_queue, 1)
        gl.addLayout(qrow)
        stats.addWidget(gc, 1)
        leftc.addLayout(stats)

        # ----- tools card: preview, reel, output
        tc = card()
        tg = QGridLayout(tc)
        tg.setContentsMargins(20, 16, 20, 16)
        tg.setHorizontalSpacing(12)
        tg.setVerticalSpacing(10)
        self.preview_time = QSlider(Qt.Horizontal)
        self.preview_time.setRange(0, 1000)
        self.preview_time.setEnabled(False)
        self.preview_time.valueChanged.connect(self._preview_time_label)
        self.lbl_ptime = QLabel("—")
        self.lbl_ptime.setObjectName("muted")
        self.lbl_ptime.setFixedWidth(56)
        self.btn_preview = QPushButton("Preview frame")
        self.btn_preview.clicked.connect(self.preview_selected)
        prow = QHBoxLayout()
        prow.addWidget(self.preview_time, 1)
        prow.addWidget(self.lbl_ptime)
        tg.addWidget(section("Preview"), 0, 0)
        tg.addLayout(prow, 0, 1)
        tg.addWidget(self.btn_preview, 0, 2)

        self.sp_reel_total = QSpinBox()
        self.sp_reel_total.setRange(10, 900)
        self.sp_reel_total.setSingleStep(10)
        self.sp_reel_total.setSuffix(" s total")
        self.sp_reel_clip = QSpinBox()
        self.sp_reel_clip.setRange(2, 120)
        self.sp_reel_clip.setSuffix(" s moments")
        tip = ("Converts a short reel of random moments spread through the selected video, "
               "using the current settings — a quick way to judge the 3D before a full conversion.")
        self.btn_reel = QPushButton("Conversion preview")
        self.btn_reel.setToolTip(tip)
        self.btn_reel.clicked.connect(self.conversion_preview)
        rrow = QHBoxLayout()
        rrow.addWidget(self.sp_reel_total, 1)
        rrow.addWidget(self.sp_reel_clip, 1)
        tg.addWidget(section("Reel"), 1, 0)
        tg.addLayout(rrow, 1, 1)
        tg.addWidget(self.btn_reel, 1, 2)

        # your own moments: same moments every time -> fair A/B tests of models and settings
        self.timeline = MomentTimeline()
        self.timeline.changed.connect(self._moments_changed)
        self.timeline.playhead_moved.connect(self._timeline_scrubbed)
        self.btn_add_moment = QPushButton("+ Add moment")
        self.btn_add_moment.setToolTip("Adds a moment at the playhead, as long as the “s moments” value above. "
                                       "Tip: double-click the timeline to add one right there.")
        self.btn_add_moment.clicked.connect(lambda: self.timeline.add_moment())
        self.btn_clear_moments = QPushButton("Clear")
        self.btn_clear_moments.clicked.connect(self.timeline.clear_moments)
        self.ck_moments_all = QCheckBox("All videos in the queue")
        self.ck_moments_all.setToolTip("Convert the same moments of every video in the queue "
                                       "(moments past a video's end are skipped)")
        self.ck_moments_all.toggled.connect(lambda *_: self._update_buttons())
        self.lbl_moments = QLabel("")
        self.lbl_moments.setObjectName("muted")
        mtools = QHBoxLayout()
        mtools.setContentsMargins(0, 0, 0, 0)
        mtools.addWidget(self.btn_add_moment)
        mtools.addWidget(self.btn_clear_moments)
        mtools.addWidget(self.lbl_moments, 1)
        mtools.addWidget(self.ck_moments_all)
        mcol = QVBoxLayout()
        mcol.setSpacing(6)
        mcol.addWidget(self.timeline)
        mcol.addLayout(mtools)
        self.btn_moments = QPushButton("Moments preview")
        self.btn_moments.setToolTip(
            "Converts only your moments with the current settings. The moments stay the same, so you can run "
            "it again with another depth model or other settings and compare like for like (A/B testing). "
            "Moments are shared by every clip in the queue.")
        self.btn_moments.clicked.connect(self.moments_preview)
        tg.addWidget(section("Moments"), 2, 0, Qt.AlignTop)
        tg.addLayout(mcol, 2, 1)
        tg.addWidget(self.btn_moments, 2, 2, Qt.AlignTop)
        self.sp_reel_clip.valueChanged.connect(lambda v: setattr(self.timeline, "default_len", float(v)))
        self.preview_time.valueChanged.connect(self._preview_slider_to_timeline)

        self.ed_out = QLineEdit()
        self.ed_out.setPlaceholderText("Empty = a “3D” folder next to each source file")
        b_out = QPushButton("Browse…")
        b_out.clicked.connect(self.choose_output)
        b_open = QPushButton("Open")
        b_open.clicked.connect(self.open_output)
        orow = QHBoxLayout()
        orow.addWidget(self.ed_out, 1)
        orow.addWidget(b_out)
        self.ck_open_done = QCheckBox("Open when done")
        self.ck_open_done.setToolTip("Open the output folder when a conversion or the whole queue has finished")
        orow.addWidget(self.ck_open_done)
        tg.addWidget(section("Output"), 3, 0)
        tg.addLayout(orow, 3, 1)
        tg.addWidget(b_open, 3, 2)
        tg.setColumnStretch(1, 1)
        leftc.addWidget(tc)

        # ----- settings card
        right = card()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(20, 16, 20, 16)
        h = QLabel("Settings")
        h.setObjectName("h2")
        rl.addWidget(h)
        prs = QHBoxLayout()
        self.cb_preset = QComboBox()
        self.cb_preset.setMinimumWidth(160)
        self.cb_preset.activated.connect(self._on_preset)
        b_save = QPushButton("Save as…")
        b_save.clicked.connect(self.save_preset)
        b_del = QPushButton("Delete")
        b_del.clicked.connect(self.delete_preset)
        prs.addWidget(self.cb_preset, 1)
        prs.addWidget(b_save)
        prs.addWidget(b_del)
        rl.addLayout(prs)
        tabs = QTabWidget()
        tabs.addTab(self._tab_3d(), "3D")
        tabs.addTab(self._tab_video(), "Video")
        tabs.addTab(self._tab_output(), "Files")
        tabs.addTab(self._tab_perf(), "GPU")
        tabs.addTab(self._tab_title(), "Title")
        rl.addWidget(tabs, 1)
        rightc.addWidget(right, 1)

        # ----- action card
        ac = card()
        al = QHBoxLayout(ac)
        al.setContentsMargins(16, 14, 16, 14)
        self.btn_pause = QPushButton("Pause")
        self.btn_pause.clicked.connect(self.toggle_pause)
        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setObjectName("danger")
        self.btn_stop.clicked.connect(self.stop)
        self.btn_start = QPushButton("Convert to 3D")
        self.btn_start.setObjectName("go")
        self.btn_start.clicked.connect(self.start)
        for b in (self.btn_pause, self.btn_stop):
            b.setMinimumHeight(44)
            al.addWidget(b)
        al.addWidget(self.btn_start, 1)
        rightc.addWidget(ac)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(3000)
        self.log.setFixedHeight(150)
        self.log.setStyleSheet("font-family: Consolas, monospace; font-size: 9pt;")
        self.log.setVisible(False)
        outer.addWidget(self.log)

    def _form(self):
        w = QWidget()
        w.setObjectName("form")
        g = QGridLayout(w)
        g.setContentsMargins(12, 12, 12, 12)
        g.setVerticalSpacing(9)
        g.setHorizontalSpacing(12)
        g.setColumnStretch(1, 1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(w)
        scroll.viewport().setObjectName("formvp")
        return scroll, g

    def _row(self, g, label, widget, tip=""):
        if isinstance(widget, QComboBox):
            widget.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
            widget.setMinimumContentsLength(12)
            widget.view().setMinimumWidth(320)
        r = g.rowCount()
        lbl = QLabel(label)
        if tip:
            lbl.setToolTip(tip)
            widget.setToolTip(tip)
        g.addWidget(lbl, r, 0)
        g.addWidget(widget, r, 1)
        return widget

    def _tab_3d(self):
        scroll, g = self._form()
        self.cb_layout = self._row(g, "Output layout", QComboBox(),
                                   "Half SBS keeps a normal 16:9 frame (each eye squeezed) — what the Odyssey 3D and 3D TVs expect. Full SBS is double-width for VR players.")
        self.cb_layout.addItems(list(S.LAYOUTS.keys()))
        self.cb_model = self._row(g, "Depth model", QComboBox(),
                                  "Small = fastest. Large = best edges. Video Depth Anything = least flicker on video.")
        self._fill_models()
        self.cb_model.currentIndexChanged.connect(self._update_aa)
        self.cb_res = self._row(g, "Depth resolution", QComboBox(),
                                "Higher = finer depth detail, slower. Default lets the model decide.")
        for r in (0, 392, 518, 644, 770, 1036):
            self.cb_res.addItem("Model default" if r == 0 else str(r), r)

        g.addWidget(section("Depth effect"), g.rowCount(), 0, 1, 2)
        self.sl_div = self._row(g, "3D strength", SliderSpin(0.0, 6.0, 0.1, 2),
                                "How deep the scene looks. 2 is natural; above 3 shows more stretching.")
        self.sl_conv = self._row(g, "Screen plane", SliderSpin(0.0, 1.0, 0.05, 2),
                                 "0 = everything pops out of the screen, 1 = everything sits behind it.")
        self.sl_fg = self._row(g, "Foreground boost", SliderSpin(-3.0, 3.0, 0.5, 1),
                               "Positive makes people/near objects rounder. Good for photos; keep 0 for video.")
        self.sl_edge = self._row(g, "Edge fix", SliderSpin(0, 20, 1, 0),
                                 "Reduces halos at object edges. 2 is default, 4 is most comfortable.")
        self.sl_ipd = self._row(g, "IPD offset", SliderSpin(0.0, 10.0, 0.5, 1),
                                "Shifts eye separation. Leave 0 unless your player can't adjust it.")

        g.addWidget(section("Stereo generation"), g.rowCount(), 0, 1, 2)
        self.cb_method = self._row(g, "Method", QComboBox(),
                                   "How the second eye is built from depth. Inpaint methods fill revealed gaps.")
        for label, v in S.METHODS.items():
            self.cb_method.addItem(label, v)
        self.cb_synth = self._row(g, "Synthesize", QComboBox(),
                                  "Both = artifacts split between eyes. Left/Right = one eye stays original.")
        for label, v in (("Both eyes", "both"), ("Right eye only", "right"), ("Left eye only", "left")):
            self.cb_synth.addItem(label, v)
        self.ck_border = QCheckBox("Keep screen edges flat")
        self.ck_aa = QCheckBox("Depth anti-aliasing")
        self.ck_tta = QCheckBox("Flip TTA (slower, cleaner depth)")
        for c in (self.ck_border, self.ck_aa, self.ck_tta):
            g.addWidget(c, g.rowCount(), 1)
        g.setRowStretch(g.rowCount(), 1)
        return scroll

    def _tab_video(self):
        scroll, g = self._form()
        self.cb_container = self._row(g, "Container", QComboBox(), "mp4 = most compatible. mkv can be previewed while converting.")
        self.cb_container.addItems(["mp4", "mkv", "avi"])
        self.cb_codec = self._row(g, "Codec", QComboBox(), "NVENC codecs encode on the GPU (much faster).")
        nv = E.nvenc_available()
        for c in S.CODECS:
            self.cb_codec.addItem(c + ("" if (not c.endswith("nvenc") or nv) else "  (not available)"), c)
        self.sp_crf = self._row(g, "Quality (CRF)", SliderSpin(0, 51, 1, 0), "Lower = better quality, bigger file. 16–22 is typical.")
        self.cb_enc = self._row(g, "Encoder preset", QComboBox(), "x264/x265: ultrafast…veryslow. NVENC: p1 (fast) … p7 (best).")
        self.cb_enc.addItems(S.PRESETS_ENC)
        self.cb_pix = self._row(g, "Pixel format", QComboBox())
        self.cb_pix.addItems(S.PIX_FMTS)
        fps = QWidget()
        fl = QHBoxLayout(fps)
        fl.setContentsMargins(0, 0, 0, 0)
        self.sp_fps = QDoubleSpinBox()
        self.sp_fps.setRange(1, 240)
        self.sp_fps.setDecimals(2)
        self.ck_srcfps = QCheckBox("Keep source FPS")
        self.ck_srcfps.toggled.connect(lambda on: self.sp_fps.setEnabled(not on))
        fl.addWidget(self.sp_fps)
        fl.addWidget(self.ck_srcfps)
        fl.addStretch(1)
        self._row(g, "Max FPS", fps)
        self.cb_maxh = self._row(g, "Processing size", QComboBox(),
                                 "Videos taller than this are scaled down before converting. 4K takes about 4x the "
                                 "time and GPU memory of 1080p; Half SBS from 1080p looks great on the Odyssey 3D.")
        for label, v in (("1080p · fast (recommended)", 1080), ("1440p", 1440), ("4K · 2160p (slow)", 2160),
                         ("720p · fastest", 720), ("Source size (no scaling)", 0)):
            self.cb_maxh.addItem(label, v)
        self.ck_pad169 = QCheckBox("Fit 4:3 videos to 16:9 (black side bars)")
        self.ck_pad169.setToolTip("Needed for 3D on the Odyssey 3D and 3D TVs: they split the screen in half, so a "
                                  "4:3 side-by-side frame that the player shrinks to fit puts each eye in the wrong place.")
        g.addWidget(self.ck_pad169, g.rowCount(), 1)

        g.addWidget(section("Stability"), g.rowCount(), 0, 1, 2)
        self.ck_ema = QCheckBox("Flicker reduction (smooth depth over time)")
        g.addWidget(self.ck_ema, g.rowCount(), 1)
        self.sl_ema = self._row(g, "Smoothing", SliderSpin(0.1, 0.99, 0.05, 2), "Higher = smoother but slower to react to cuts.")
        self.ck_scene = QCheckBox("Scene-cut detection (reset smoothing at cuts)")
        g.addWidget(self.ck_scene, g.rowCount(), 1)
        self.cb_autocrop = self._row(g, "Auto-crop", QComboBox(), "Remove letterbox bars before converting.")
        for label, v in (("Off", ""), ("Black bars top/bottom", "BLACK_TB"), ("Black bars all sides", "BLACK"),
                         ("Flat borders top/bottom", "FLAT_TB"), ("Flat borders all sides", "FLAT")):
            self.cb_autocrop.addItem(label, v)
        self.ck_hwdec = QCheckBox("GPU video decoding (NVDEC)")
        g.addWidget(self.ck_hwdec, g.rowCount(), 1)
        g.setRowStretch(g.rowCount(), 1)
        return scroll

    def _tab_output(self):
        scroll, g = self._form()
        self.cb_imgfmt = self._row(g, "Image format", QComboBox())
        self.cb_imgfmt.addItems(["png", "jpeg", "webp"])
        self.ck_recursive = QCheckBox("Include sub-folders when a folder is queued")
        self.ck_meta = QCheckBox("Put settings in output file names")
        self.ck_auto_img = QCheckBox("Images added → switch to the Lotus image preset (videos switch back)")
        self.ck_auto_img.setToolTip(f"Adding images loads “{IMAGE_PRESET}”. Adding videos afterwards restores "
                                    "the settings you had before.")
        for c in (self.ck_recursive, self.ck_meta, self.ck_auto_img):
            g.addWidget(c, g.rowCount(), 1)
        note = QLabel("Half SBS files are saved as <i>name_HSBS.mp4</i>, Full SBS as <i>name_LRF_Full_SBS.mp4</i>.")
        note.setWordWrap(True)
        note.setObjectName("muted")
        g.addWidget(note, g.rowCount(), 0, 1, 2)
        g.setRowStretch(g.rowCount(), 1)
        return scroll

    def _tab_title(self):
        from PySide6.QtWidgets import QFontComboBox, QColorDialog
        from .title import PLACEMENTS
        scroll, g = self._form()
        self.ck_title = QCheckBox("Add a title to converted videos")
        g.addWidget(self.ck_title, g.rowCount(), 0, 1, 2)
        self.ed_title = QPlainTextEdit()
        self.ed_title.setPlaceholderText("Title text (Enter for a second line)")
        self.ed_title.setFixedHeight(64)
        self.ed_title.setStyleSheet(f"background: {FIELD}; border-radius: 9px;")
        self._row(g, "Text", self.ed_title)
        self.cb_tfont = QFontComboBox()
        self._row(g, "Font", self.cb_tfont)
        fr = QWidget()
        fl = QHBoxLayout(fr)
        fl.setContentsMargins(0, 0, 0, 0)
        self.ck_tbold = QCheckBox("Bold")
        self.ck_tshadow = QCheckBox("Shadow")
        self.b_tcolor = QPushButton("Colour")
        self._tcolor = "#ffffff"

        def pick_color():
            c = QColorDialog.getColor(QColor(self._tcolor), self, "Title colour")
            if c.isValid():
                self._set_tcolor(c.name())
        self.b_tcolor.clicked.connect(pick_color)
        fl.addWidget(self.ck_tbold)
        fl.addWidget(self.ck_tshadow)
        fl.addStretch(1)
        fl.addWidget(self.b_tcolor)
        self._row(g, "Style", fr)
        self.sl_tsize = self._row(g, "Size", SliderSpin(2.0, 25.0, 0.5, 1), "Text height as % of the picture height.")
        self.cb_tplace = self._row(g, "Placement", QComboBox())
        self.cb_tplace.addItems(PLACEMENTS)
        self.sl_tdepth = self._row(g, "Depth", SliderSpin(-100, 100, 5, 0),
                                   "Where the title sits in 3D: negative = behind the screen, 0 = on the screen, "
                                   "positive = floats in front of the screen.")
        self.sl_topac = self._row(g, "Opacity", SliderSpin(0, 100, 5, 0), "How solid the title is at full fade (%).")

        g.addWidget(section("Timing"), g.rowCount(), 0, 1, 2)
        self.cb_twhen = self._row(g, "When", QComboBox())
        self.cb_twhen.addItems(["Start", "End"])
        self.sp_toff = self._row(g, "Offset (s)", QDoubleSpinBox(),
                                 "Seconds after the start (or before the end) before the title appears.")
        self.sp_tin = self._row(g, "Fade in (s)", QDoubleSpinBox())
        self.sp_thold = self._row(g, "Hold (s)", QDoubleSpinBox())
        self.sp_tout = self._row(g, "Fade out (s)", QDoubleSpinBox())
        for sp in (self.sp_toff, self.sp_tin, self.sp_thold, self.sp_tout):
            sp.setRange(0, 600)
            sp.setDecimals(1)
            sp.setSingleStep(0.5)

        self.title_preview = QLabel()
        self.title_preview.setMinimumHeight(150)
        self.title_preview.setAlignment(Qt.AlignCenter)
        g.addWidget(section("Preview (one eye)"), g.rowCount(), 0, 1, 2)
        g.addWidget(self.title_preview, g.rowCount(), 0, 1, 2)
        note = QLabel("The title is drawn into both eyes after conversion, so the depth model never warps it. "
                      "Conversion preview reels show it too.")
        note.setWordWrap(True)
        note.setObjectName("muted")
        g.addWidget(note, g.rowCount(), 0, 1, 2)
        g.setRowStretch(g.rowCount(), 1)
        for wdg, sig in ((self.ck_title, "toggled"), (self.ed_title, "textChanged"), (self.cb_tfont, "currentFontChanged"),
                         (self.ck_tbold, "toggled"), (self.ck_tshadow, "toggled"), (self.cb_tplace, "currentIndexChanged"),
                         (self.sl_tsize.spin, "valueChanged"), (self.sl_topac.spin, "valueChanged"),
                         (self.sl_tdepth.spin, "valueChanged")):
            getattr(wdg, sig).connect(lambda *_: self._update_title_preview())
        return scroll

    def _set_tcolor(self, name):
        self._tcolor = name
        self.b_tcolor.setStyleSheet(f"background: {name}; color: {'#000' if QColor(name).lightness() > 128 else '#fff'};")
        self._update_title_preview()

    def _title_settings(self):
        return {
            "title_on": self.ck_title.isChecked(),
            "title_text": self.ed_title.toPlainText(),
            "title_font": self.cb_tfont.currentFont().family(),
            "title_bold": self.ck_tbold.isChecked(),
            "title_size": round(self.sl_tsize.value(), 1),
            "title_color": self._tcolor,
            "title_shadow": self.ck_tshadow.isChecked(),
            "title_place": self.cb_tplace.currentText(),
            "title_when": self.cb_twhen.currentText(),
            "title_offset": self.sp_toff.value(),
            "title_fade_in": self.sp_tin.value(),
            "title_hold": self.sp_thold.value(),
            "title_fade_out": self.sp_tout.value(),
            "title_opacity": int(self.sl_topac.value()),
            "title_depth": int(self.sl_tdepth.value()),
        }

    def _apply_title(self, s):
        from PySide6.QtGui import QFont as _F
        self.ck_title.setChecked(bool(s.get("title_on", False)))
        self.ed_title.setPlainText(s.get("title_text", ""))
        self.cb_tfont.setCurrentFont(_F(s.get("title_font", "Segoe UI")))
        self.ck_tbold.setChecked(bool(s.get("title_bold", True)))
        self.ck_tshadow.setChecked(bool(s.get("title_shadow", True)))
        self.sl_tsize.setValue(float(s.get("title_size", 8.0)))
        self.cb_tplace.setCurrentText(s.get("title_place", "Center"))
        self.cb_twhen.setCurrentText(s.get("title_when", "Start"))
        self.sp_toff.setValue(float(s.get("title_offset", 1.0)))
        self.sp_tin.setValue(float(s.get("title_fade_in", 1.0)))
        self.sp_thold.setValue(float(s.get("title_hold", 3.0)))
        self.sp_tout.setValue(float(s.get("title_fade_out", 1.0)))
        self.sl_topac.setValue(float(s.get("title_opacity", 100)))
        self.sl_tdepth.setValue(float(s.get("title_depth", 0)))
        self._set_tcolor(s.get("title_color", "#ffffff"))

    def _update_title_preview(self):
        """Small 16:9 mock-up of where and how the title will appear (one eye, full opacity)."""
        if not hasattr(self, "title_preview"):
            return
        try:
            from .title import TitleOverlay
            from PIL import Image
            ts = self._title_settings()
            if not ts["title_text"].strip():
                ts["title_text"] = "Your title"
            ov = TitleOverlay(dict(ts, layout="Full SBS"), 30, 300)
            w, h = 384, 216
            layer = ov.render_rgba(w, h)
            bg = Image.new("RGB", (w, h), (52, 56, 66))
            for y in range(h):                                  # simple dusk gradient backdrop
                c = (40 + y // 6, 46 + y // 8, 62 + y // 10)
                bg.paste(c, (0, y, w, y + 1))
            img = Image.fromarray(layer, "RGBA")
            a = img.getchannel("A").point(lambda v: int(v * ov.opacity))
            bg.paste(img.convert("RGB"), (0, 0), a)
            pm = pil_to_qpixmap(bg)
            if not self.ck_title.isChecked():
                pm = pil_to_qpixmap(bg.point(lambda v: v // 2 + 20))
            self.title_preview.setPixmap(pm)
        except Exception as e:
            self.title_preview.setText(f"(preview unavailable: {e})")

    def _tab_perf(self):
        scroll, g = self._form()
        self.cb_gpu = self._row(g, "Device", QComboBox())
        for i, label in E.list_gpus():
            self.cb_gpu.addItem(label, i)
        self.sp_batch = self._row(g, "Batch size", SliderSpin(1, 32, 1, 0), "Frames processed at once. Lower if you run out of VRAM.")
        self.cb_workers = self._row(g, "Worker threads", QComboBox(), "Parallel inference threads for video. 0 = off.")
        for w in (0, 1, 2, 3, 4, 8):
            self.cb_workers.addItem(str(w), w)
        self.ck_fp16 = QCheckBox("FP16 / mixed precision (faster)")
        self.ck_lowvram = QCheckBox("Low VRAM mode")
        self.ck_stream = QCheckBox("Multiple CUDA streams")
        for c in (self.ck_fp16, self.ck_lowvram, self.ck_stream):
            g.addWidget(c, g.rowCount(), 1)
        b_free = QPushButton("Unload model from VRAM")
        b_free.clicked.connect(lambda: (self.converter.free_model(), self.append_log("Model unloaded.")))
        g.addWidget(b_free, g.rowCount(), 1, Qt.AlignLeft)
        g.setRowStretch(g.rowCount(), 1)
        return scroll

    # ---------- settings <-> widgets
    def _set_combo_data(self, cb, value):
        i = cb.findData(value)
        if i < 0:
            i = cb.findText(str(value))
        if i >= 0:
            cb.setCurrentIndex(i)

    def _apply(self, s):
        self._loading = True
        self.cb_layout.setCurrentText(s["layout"])
        self._set_combo_data(self.cb_model, s["depth_model"])
        self._set_combo_data(self.cb_res, s["resolution"])
        self._set_combo_data(self.cb_method, s["method"])
        self.sl_div.setValue(s["divergence"])
        self.sl_conv.setValue(s["convergence"])
        self.sl_fg.setValue(s["foreground_scale"])
        self.sl_edge.setValue(s["edge_dilation"])
        self.sl_ipd.setValue(s["ipd_offset"])
        self._set_combo_data(self.cb_synth, s["synthetic_view"])
        self.ck_border.setChecked(s["preserve_screen_border"])
        self.ck_aa.setChecked(s["depth_aa"])
        self.ck_tta.setChecked(s["tta"])
        self.cb_container.setCurrentText(s["video_format"])
        self._set_combo_data(self.cb_codec, s["video_codec"])
        self.sp_crf.setValue(s["crf"])
        self.cb_enc.setCurrentText(s["enc_preset"])
        self.cb_pix.setCurrentText(s["pix_fmt"])
        self.sp_fps.setValue(s["max_fps"])
        self.ck_srcfps.setChecked(s["keep_source_fps"])
        i = self.cb_maxh.findData(int(s.get("max_height", 1080)))
        self.cb_maxh.setCurrentIndex(i if i >= 0 else 0)
        self.ck_pad169.setChecked(bool(s.get("pad_16x9", True)))
        self.ck_ema.setChecked(s["ema_normalize"])
        self.sl_ema.setValue(s["ema_decay"])
        self.ck_scene.setChecked(s["scene_detect"])
        self.ck_hwdec.setChecked(s["hwaccel_decode"])
        self._set_combo_data(self.cb_autocrop, s["autocrop"])
        self.cb_imgfmt.setCurrentText(s["image_format"])
        self._set_combo_data(self.cb_gpu, s["gpu"])
        self.sp_batch.setValue(s["batch_size"])
        self._set_combo_data(self.cb_workers, s["max_workers"])
        self.ck_fp16.setChecked(s["fp16"])
        self.ck_lowvram.setChecked(s["low_vram"])
        self.ck_stream.setChecked(s["cuda_stream"])
        self.ck_recursive.setChecked(s["recursive"])
        self.ck_auto_img.setChecked(bool(s.get("auto_image_preset", True)))
        self.ck_meta.setChecked(s["metadata_in_name"])
        self.ck_open_done.setChecked(bool(s.get("open_when_done", True)))
        self._apply_title(s)
        self._live_every = int(s.get("live_every", 100))
        self.sp_reel_total.setValue(int(s.get("reel_total", 60)))
        self.sp_reel_clip.setValue(int(s.get("reel_clip", 8)))
        self.timeline.default_len = float(self.sp_reel_clip.value())
        self.timeline.set_moments(s.get("reel_moments", []))
        self._moments_changed(save=False)
        self._live_mode = int(s.get("live_mode", 1))
        self._live_pinned = bool(s.get("live_pinned", True))
        self.converter.set_live_every(self._live_every)
        self.btn_live.blockSignals(True)
        self.btn_live.setChecked(bool(s.get("live_view", True)))
        self.btn_live.blockSignals(False)
        if s.get("output_dir"):
            self.ed_out.setText(s["output_dir"])
        self._loading = False
        self._update_aa()

    def collect(self):
        return {
            "layout": self.cb_layout.currentText(),
            "depth_model": self.cb_model.currentData(),
            "resolution": self.cb_res.currentData(),
            "method": self.cb_method.currentData(),
            "divergence": round(self.sl_div.value(), 3),
            "convergence": round(self.sl_conv.value(), 3),
            "foreground_scale": round(self.sl_fg.value(), 2),
            "edge_dilation": int(self.sl_edge.value()),
            "ipd_offset": round(self.sl_ipd.value(), 2),
            "synthetic_view": self.cb_synth.currentData(),
            "preserve_screen_border": self.ck_border.isChecked(),
            "depth_aa": self.ck_aa.isChecked(),
            "tta": self.ck_tta.isChecked(),
            "video_format": self.cb_container.currentText(),
            "video_codec": self.cb_codec.currentData(),
            "crf": int(self.sp_crf.value()),
            "enc_preset": self.cb_enc.currentText(),
            "pix_fmt": self.cb_pix.currentText(),
            "max_fps": self.sp_fps.value(),
            "keep_source_fps": self.ck_srcfps.isChecked(),
            "max_height": int(self.cb_maxh.currentData()),
            "pad_16x9": self.ck_pad169.isChecked(),
            "ema_normalize": self.ck_ema.isChecked(),
            "ema_decay": round(self.sl_ema.value(), 3),
            "scene_detect": self.ck_scene.isChecked(),
            "hwaccel_decode": self.ck_hwdec.isChecked(),
            "autocrop": self.cb_autocrop.currentData(),
            "image_format": self.cb_imgfmt.currentText(),
            "gpu": self.cb_gpu.currentData(),
            "batch_size": int(self.sp_batch.value()),
            "low_vram": self.ck_lowvram.isChecked(),
            "fp16": self.ck_fp16.isChecked(),
            "max_workers": self.cb_workers.currentData(),
            "cuda_stream": self.ck_stream.isChecked(),
            "output_dir": self.ed_out.text().strip(),
            "recursive": self.ck_recursive.isChecked(),
            "auto_image_preset": self.ck_auto_img.isChecked(),
            "resume": False,
            "metadata_in_name": self.ck_meta.isChecked(),
            "open_when_done": self.ck_open_done.isChecked(),
            **self._title_settings(),
            "live_view": self.btn_live.isChecked(),
            "live_every": getattr(self, "_live_every", 100),
            "reel_total": self.sp_reel_total.value(),
            "reel_clip": self.sp_reel_clip.value(),
            "reel_moments": self.timeline.get_moments(),
            "live_mode": getattr(self, "_live_mode", 1),
            "live_pinned": getattr(self, "_live_pinned", True),
        }

    def _fill_models(self):
        cur = self.cb_model.currentData()
        self.cb_model.blockSignals(True)
        self.cb_model.clear()
        for m in E.depth_models():
            label = S.DEPTH_MODEL_LABELS.get(m, m)
            if not M.is_ready(m):
                label += "   ⬇ needs download"
            self.cb_model.addItem(label, m)
        if cur:
            self._set_combo_data(self.cb_model, cur)
        self.cb_model.blockSignals(False)

    def open_models(self, focus=None):
        ModelManagerDialog(self, focus or self.cb_model.currentData()).exec()
        self._fill_models()

    def _ensure_model(self, s):
        """Make sure the selected depth model is available; offer the model manager if not."""
        m = s["depth_model"]
        if M.is_ready(m):
            return True
        r = QMessageBox.question(
            self, APP_NAME,
            f"“{S.DEPTH_MODEL_LABELS.get(m, m)}” is a non-commercial model that has to be downloaded "
            f"once ({M.CATALOG[M.canonical(m)][3]}).\n\nOpen the model manager now?")
        if r == QMessageBox.Yes:
            self.open_models(m)
        return M.is_ready(m)

    def _update_aa(self):
        try:
            from iw3.depth_model_factory import is_depth_aa_supported
            ok = is_depth_aa_supported(self.cb_model.currentData())
        except Exception:
            ok = False
        self.ck_aa.setEnabled(ok)

    # ---------- presets
    def _refresh_presets(self, select=None):
        self.cb_preset.blockSignals(True)
        self.cb_preset.clear()
        self.cb_preset.addItem("— choose a preset —", None)
        gpu = E.gpu_short_name()
        for n in S.BUILTIN_PRESETS:
            label = f"{n} ({gpu})" if (n == "Odyssey 3D · Best" and gpu) else n   # name this PC's own GPU
            self.cb_preset.addItem("★ " + label, n)
        for n in S.list_user_presets():
            self.cb_preset.addItem(n, n)
        if select:
            self._set_combo_data(self.cb_preset, select)
        self.cb_preset.blockSignals(False)

    def _auto_image_preset(self, added):
        """Images added -> Lotus image preset; videos added later -> back to the settings from before."""
        if not self.ck_auto_img.isChecked() or self.converter.running():
            return
        saved = getattr(self, "_pre_image_settings", None)
        if added == {"Image"} and saved is None:
            if "Lotus_D" not in E.depth_models():
                return
            self._pre_image_settings = self.collect()
            self._set_combo_data(self.cb_preset, IMAGE_PRESET)     # loads it via _on_preset
            if self.cb_preset.currentData() == IMAGE_PRESET and self.cb_model.currentData() != "Lotus_D":
                self._on_preset(0)
            self.append_log(f"Images added — switched to “{IMAGE_PRESET}”.")
        elif "Video" in added and saved is not None:
            self._pre_image_settings = None
            keep = {k: v for k, v in self.collect().items()
                    if k.startswith("title_") or k in ("reel_moments", "output_dir", "auto_image_preset")}
            saved.update(keep)
            self.cb_preset.blockSignals(True)
            self.cb_preset.setCurrentIndex(0)
            self.cb_preset.blockSignals(False)
            self._apply(saved)
            self.append_log("Videos added — switched back to your video settings.")

    def _on_preset(self, _i):
        name = self.cb_preset.currentData()
        if not name:
            return
        try:
            s = S.load_preset(name)
            s["output_dir"] = self.ed_out.text().strip()
            s.update(self._title_settings())          # presets never change the title
            s["reel_moments"] = self.timeline.get_moments()   # ... or your moments
            s["auto_image_preset"] = self.ck_auto_img.isChecked()
            self._apply(s)
            self.append_log(f"Preset loaded: {name}")
        except Exception as e:
            QMessageBox.warning(self, APP_NAME, f"Could not load preset:\n{e}")

    def save_preset(self):
        name, ok = QInputDialog.getText(self, "Save preset", "Preset name:")
        if ok and name.strip():
            if name.strip() in S.BUILTIN_PRESETS:
                QMessageBox.information(self, APP_NAME, "That name is used by a built-in preset. Pick another.")
                return
            saved = S.save_preset(name.strip(), self.collect())
            self._refresh_presets(select=saved)

    def delete_preset(self):
        name = self.cb_preset.currentData()
        if not name or name in S.BUILTIN_PRESETS:
            QMessageBox.information(self, APP_NAME, "Select one of your own presets to delete (built-in ★ presets can't be removed).")
            return
        S.delete_preset(name)
        self._refresh_presets()

    # ---------- queue
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        self.add_paths([u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()])

    def add_files_dialog(self):
        exts = " ".join("*" + x for x in sorted(E.VIDEO_EXTS | E.IMAGE_EXTS))
        files, _ = QFileDialog.getOpenFileNames(self, "Add images or videos", "", f"Media ({exts});;All files (*)")
        self.add_paths(files)

    def add_folder_dialog(self):
        d = QFileDialog.getExistingDirectory(self, "Add a folder")
        if d:
            self.add_paths([d])

    def load_settings_from(self, p):
        """If `p` is a video made by Stereo3D Studio, apply its stored settings. Returns True if it was."""
        found = E.read_settings_from_video(p)
        if not found:
            return False
        stored, info = found
        s = self.collect()
        for k, v in stored.items():
            if k in s:
                s[k] = v
        self._apply(S._merged(s))
        self._set_combo_data(self.cb_preset, None)
        model = S.DEPTH_MODEL_LABELS.get(s["depth_model"], s["depth_model"])
        msg = (f"Settings loaded from {path.basename(p)} (made with Stereo3D Studio {info.get('version', '?')} "
               f"from {info.get('source', '?')}): {model}")
        self.append_log(msg)
        self.lbl_cur.setText("Settings loaded from " + path.basename(p))
        return True

    def add_paths(self, paths):
        existing = {it["path"] for it in self.items}
        skipped = 0
        added = set()
        for p in paths:
            p = path.normpath(p)
            kind = E.classify(p)
            if kind is None:
                skipped += 1
                continue
            if kind == "Video" and self.load_settings_from(p):
                continue          # a Stereo3D Studio output: restore its settings instead of queueing it
            if p in existing:
                continue
            existing.add(p)
            added.add(kind)
            self.items.append({"id": self._next_id, "path": p, "type": kind})
            self._next_id += 1
            r = self.table.rowCount()
            self.table.insertRow(r)
            name = QTableWidgetItem(path.basename(p) or p)
            name.setToolTip(p)
            self.table.setItem(r, self.COL_NAME, name)
            self.table.setItem(r, self.COL_TYPE, QTableWidgetItem(kind))
            self.table.setItem(r, self.COL_STATUS, QTableWidgetItem("Ready"))
            self.table.setItem(r, self.COL_INFO, QTableWidgetItem(""))
            self._add_x_button(r, self.items[-1]["id"])
            self._request_thumb(self.items[-1])
        if skipped:
            self.append_log(f"Skipped {skipped} unsupported file(s).")
        self._auto_image_preset(added)
        if self.items and not self.table.selectedItems():
            self.table.selectRow(0)
        self._update_buttons()

    # ---------- per-row thumbnail + remove button
    def _add_x_button(self, r, item_id):
        b = QPushButton("✕")
        b.setObjectName("rowx")
        b.setToolTip("Remove from the list (the file itself is never deleted)")
        b.setCursor(Qt.PointingHandCursor)
        b.setFixedSize(28, 28)
        b.clicked.connect(lambda: self.remove_item(item_id))
        holder = QWidget()
        hl = QHBoxLayout(holder)
        hl.setContentsMargins(0, 0, 8, 0)
        hl.addWidget(b, 0, Qt.AlignCenter)
        self.table.setCellWidget(r, self.COL_X, holder)

    def remove_item(self, item_id):
        """Take one entry off the list. Never touches the file on disk."""
        r = self._row_of(item_id)
        if r < 0:
            return
        if self.table.item(r, self.COL_STATUS).text() == "Working":
            QMessageBox.information(self, APP_NAME, "This file is converting right now. Press Stop first.")
            return
        self._pending = [j for j in getattr(self, "_pending", []) if j[0] != item_id]
        self._remove_row(r)
        self._on_selection()
        self._update_buttons()

    def _request_thumb(self, item):
        item_id, p, kind = item["id"], item["path"], item["type"]
        if kind not in ("Video", "Image"):
            return

        def work():
            try:
                if kind == "Video":
                    dur = E.video_duration(p)
                    im = E.grab_frame(p, dur * 0.1 if dur else 0.0)
                else:
                    from PIL import Image
                    im = Image.open(p)
                    im.draft("RGB", (320, 180))
                    im = im.convert("RGB")
                im.thumbnail((self.THUMB.width() * 2, self.THUMB.height() * 2))
                self.bridge.thumb.emit(item_id, im)
            except Exception:
                pass

        self._thumb_pool.submit(work)

    def on_thumb(self, item_id, im):
        r = self._row_of(item_id)
        if r < 0:
            return
        from PIL import Image
        W, H = self.THUMB.width() * 2, self.THUMB.height() * 2
        canvas = Image.new("RGB", (W, H), (20, 20, 23))       # letterbox into a 16:9 tile
        canvas.paste(im, ((W - im.width) // 2, (H - im.height) // 2))
        pm = pil_to_qpixmap(canvas)
        it = self.table.item(r, self.COL_NAME)
        if it:
            it.setIcon(QIcon(pm))

    def remove_selected(self):
        if self.converter.running():
            return
        rows = sorted({i.row() for i in self.table.selectedItems()}, reverse=True)
        for r in rows:
            self.table.removeRow(r)
            del self.items[r]
        self._update_buttons()

    def clear_queue(self):
        if self.converter.running():
            return
        self.table.setRowCount(0)
        self.items.clear()
        self._update_buttons()

    def _set_status(self, row, status, info=None):
        colors = {"Done": GREEN, "Error": "#fb7185", "Working": AMBER, "Stopped": "#fbbf24",
                  "Queued": "#94a3b8", "Ready": "#94a3b8", "Preview ready": "#c4a1ff"}
        it = self.table.item(row, self.COL_STATUS)
        if it:
            it.setText(status)
            it.setForeground(QColor(colors.get(status, "#e5e7eb")))
        if info is not None:
            inf = self.table.item(row, self.COL_INFO)
            if inf:
                inf.setText(info.splitlines()[0][:200] if info else "")
                inf.setToolTip(info)

    def _row_of(self, item_id):
        for r, it in enumerate(self.items):
            if it["id"] == item_id:
                return r
        return -1

    def _remove_row(self, r):
        if 0 <= r < len(self.items):
            self.table.removeRow(r)
            del self.items[r]

    def _selected_row(self):
        rows = sorted({i.row() for i in self.table.selectedItems()})
        return rows[0] if rows else -1

    def _on_selection(self):
        r = self._selected_row()
        self._dur = 0.0
        if r >= 0 and self.items[r]["type"] == "Video":
            self._dur = E.video_duration(self.items[r]["path"])
        self.preview_time.setEnabled(self._dur > 0)
        self._preview_time_label()
        self.timeline.set_video(self.items[r]["path"] if self._dur > 0 else None, self._dur)
        self._moments_changed(save=False)
        self._update_buttons()

    def _preview_time_label(self, *_):
        if getattr(self, "_dur", 0) > 0:
            t = self._dur * self.preview_time.value() / 1000.0
            self.lbl_ptime.setText(f"{int(t // 60)}:{t % 60:04.1f}")
        else:
            self.lbl_ptime.setText("—")

    def choose_output(self):
        d = QFileDialog.getExistingDirectory(self, "Output folder", self.ed_out.text())
        if d:
            self.ed_out.setText(path.normpath(d))

    def _output_for(self, p):
        out = self.ed_out.text().strip()
        if out:
            return out
        base = p if path.isdir(p) else path.dirname(p)
        return path.join(base, "3D")

    def open_output(self):
        out = self.ed_out.text().strip()
        if not out and self.items:
            out = self._output_for(self.items[0]["path"])
        if out and path.isdir(out):
            QDesktopServices.openUrl(QUrl.fromLocalFile(out))
        else:
            QMessageBox.information(self, APP_NAME, "The output folder doesn't exist yet.")

    # ---------- run
    def _update_buttons(self):
        busy = self.converter.running() or getattr(self, "_previewing", False)
        self.btn_start.setEnabled(not busy and bool(self.items))
        self.btn_stop.setEnabled(self.converter.running())
        self.btn_pause.setEnabled(self.converter.running())
        self.btn_preview.setEnabled(not busy and self._selected_row() >= 0
                                    and self.items[self._selected_row()]["type"] in ("Image", "Video"))
        self.btn_reel.setEnabled(not busy and self._selected_row() >= 0
                                 and self.items[self._selected_row()]["type"] == "Video")
        has_videos = any(it["type"] == "Video" for it in self.items)
        sel_video = self._selected_row() >= 0 and self.items[self._selected_row()]["type"] == "Video"
        self.btn_moments.setEnabled(not busy and bool(self.timeline.moments)
                                    and (has_videos if self.ck_moments_all.isChecked() else sel_video))
        for b in (self.btn_add, self.btn_add_dir, self.btn_remove, self.btn_clear):
            b.setEnabled(not self.converter.running())

    def conversion_preview(self):
        r = self._selected_row()
        if r < 0 or self.items[r]["type"] != "Video" or self.converter.running():
            return
        s = self.collect()
        S.save_last(s)
        if not self._ensure_model(s):
            return
        item = self.items[r]
        total, clip = self.sp_reel_total.value(), min(self.sp_reel_clip.value(), self.sp_reel_total.value())
        self._pending = []
        self.job_total, self.job_done = 1, 0
        self.pb_queue.setMaximum(1)
        self.pb_queue.setValue(0)
        self.lbl_queue.setText("Conversion preview")
        self.paused = False
        self.btn_pause.setText("Pause")
        self._t_start = time.time()
        self._settings = s
        self._run_dirs, self._run_ok = [], 0
        if self.btn_live.isChecked():
            w = self._ensure_live()
            w.im = None
            w.view.setText("Waiting for the first converted frame…")
            w.show()
        self._set_status(r, "Queued", "")
        self._run_dirs.append(self._output_for(item["path"]))
        self.converter.start([(item["id"], item["path"], {"sizzle": (total, clip)})], s,
                             self._output_for(item["path"]))
        self._update_buttons()

    # ---------- your moments
    def _moments_changed(self, save=True):
        ms = self.timeline.get_moments()
        dur = getattr(self, "_dur", 0)
        if ms:
            total = sum(b for _, b in ms)
            past = sum(1 for a, _ in ms if dur and a >= dur)
            txt = f"{len(ms)} moment{'s' if len(ms) != 1 else ''} · {total:.0f} s"
            if past:
                txt += f" · {past} past this video's end"
            self.lbl_moments.setText(txt)
        else:
            self.lbl_moments.setText("No moments yet — double-click the timeline")
        if save:
            try:
                S.save_last(self.collect())
            except Exception:
                pass
        if hasattr(self, "btn_moments") and hasattr(self, "btn_start"):
            self._update_buttons()

    def _timeline_scrubbed(self, t):
        if getattr(self, "_dur", 0) > 0:
            self.preview_time.blockSignals(True)
            self.preview_time.setValue(int(round(t / self._dur * 1000)))
            self.preview_time.blockSignals(False)
            self._preview_time_label()

    def _preview_slider_to_timeline(self, v):
        if getattr(self, "_dur", 0) > 0:
            self.timeline.set_playhead(self._dur * v / 1000.0)

    def moments_preview(self):
        if self.converter.running():
            return
        moments = [tuple(m) for m in self.timeline.get_moments()]
        if not moments:
            return
        if self.ck_moments_all.isChecked():
            rows = [i for i, it in enumerate(self.items) if it["type"] == "Video"]
        else:
            r = self._selected_row()
            rows = [r] if r >= 0 and self.items[r]["type"] == "Video" else []
        if not rows:
            return
        s = self.collect()
        S.save_last(s)
        if not self._ensure_model(s):
            return
        self._pending = [(self.items[r]["id"], self.items[r]["path"], self._output_for(self.items[r]["path"]),
                          {"moments": moments}) for r in rows]
        for r in rows:
            self._set_status(r, "Queued", "")
        self.job_total, self.job_done = len(rows), 0
        self.pb_queue.setMaximum(len(rows))
        self.pb_queue.setValue(0)
        self.lbl_queue.setText("Moments preview")
        self.paused = False
        self.btn_pause.setText("Pause")
        self._t_start = time.time()
        self._settings = s
        self._run_dirs, self._run_ok = [], 0
        if self.btn_live.isChecked():
            w = self._ensure_live()
            w.im = None
            w.view.setText("Waiting for the first converted frame…")
            w.show()
        self._run_next()

    def start(self):
        if not self.items:
            return
        s = self.collect()
        S.save_last(s)
        if not self._ensure_model(s):
            return
        # everything in the queue is converted from scratch - never resumed or skipped
        pending = list(range(len(self.items)))
        self._pending = [(self.items[i]["id"], self.items[i]["path"], self._output_for(self.items[i]["path"]))
                         for i in pending]
        for i in pending:
            self._set_status(i, "Queued", "")
        self.job_total = len(pending)
        self.job_done = 0
        self.pb_queue.setMaximum(self.job_total)
        self.pb_queue.setValue(0)
        self.lbl_queue.setText(f"Queue 0 / {self.job_total}")
        self.paused = False
        self.btn_pause.setText("Pause")
        self._t_start = time.time()
        self._settings = s
        self._run_dirs, self._run_ok = [], 0
        if self.btn_live.isChecked():
            w = self._ensure_live()
            w.im = None
            w.view.setText("Waiting for the first converted frame…")
            w.show()
        self._run_next()

    def _run_next(self):
        if not self._pending:
            return False
        i, p, out, *opts = self._pending.pop(0)
        if out not in self._run_dirs:
            self._run_dirs.append(out)
        self.converter.start([(i, p, opts[0]) if opts else (i, p)], self._settings, out)
        self._update_buttons()
        return True

    def stop(self):
        self._pending = []
        self.converter.stop()
        self.lbl_cur.setText("Stopping…")

    def toggle_pause(self):
        self.paused = not self.paused
        self.converter.pause(self.paused)
        self.btn_pause.setText("Resume" if self.paused else "Pause")
        self.lbl_cur.setText("Paused" if self.paused else self.lbl_cur.text())

    def on_progress(self, phase, desc, n, total):
        now = time.time()
        if phase == "start":
            self.pb_cur.setMaximum(max(total, 1))
            self.pb_cur.setValue(0)
            self._rate = (now, 0, 0.0)
            self._cur_desc = desc
            # each pass (scene analysis, auto-crop, conversion) runs at a very different speed:
            # start a fresh line so a fast analysis pass can't squash the conversion line flat
            self.speed_line.clear()
        elif phase == "update":
            self.pb_cur.setMaximum(max(total, 1))
            self.pb_cur.setValue(min(n, max(total, 1)))
            t0, n0, fps = self._rate
            if now - t0 >= 1.0:
                inst = (n - n0) / (now - t0)
                fps = inst if fps == 0 else fps * 0.7 + inst * 0.3
                self._rate = (now, n, fps)
                self.speed_line.push(fps)
            label = desc or "Converting"
            self.lbl_cur.setText(f"{label[:48]} — frame {n:,} / {total:,}")
            if fps > 0:
                self.lbl_speed.setText(f"{fps:.1f}<span style='font-size:12pt;font-weight:600;color:{MUTED}'>"
                                       f"&nbsp;fps</span>")
                if total:
                    rem = (total - n) / fps
                    self.lbl_eta.setText(f"<span style='color:{GREEN};font-weight:600'>ETA "
                                         f"{int(rem // 3600)}:{int(rem % 3600 // 60):02d}:{int(rem % 60):02d}</span>")

    @staticmethod
    def _hms(sec):
        sec = int(max(0, sec))
        return f"{sec // 3600}:{sec % 3600 // 60:02d}:{sec % 60:02d}"

    def _tick_elapsed(self):
        t0 = getattr(self, "_item_t0", None)
        if t0 is not None:
            self.lbl_elapsed.setText(f"Render time {self._hms(time.time() - t0)}")

    def on_item(self, item_id, status, info):
        r = self._row_of(item_id)
        if status == "Working":                     # current file's render clock
            self._item_t0 = time.time()
            self._tick_elapsed()
            self._elapsed_timer.start()
        elif status in ("Done", "Error", "Stopped", "Preview ready"):
            self._tick_elapsed()
            self._elapsed_timer.stop()
        if status in ("Done", "Preview ready"):
            self._run_ok = getattr(self, "_run_ok", 0) + 1
        if status in ("Done", "Error", "Preview ready"):
            self.job_done += 1
            self.pb_queue.setValue(self.job_done)
            self.lbl_queue.setText(f"Queue {self.job_done} / {self.job_total}")
        if status == "Done":
            name = path.basename(self.items[r]["path"]) if r >= 0 else ""
            self._remove_row(r)          # finished items leave the queue
            self._on_selection()
            if name:
                self.append_log(f"Removed from queue: {name}")
            return
        if r >= 0:
            self._set_status(r, status, info)

    def on_done(self, stopped):
        if stopped:
            for item_id, *_ in getattr(self, "_pending", []):
                self._set_status(self._row_of(item_id), "Ready", "")
            self._pending = []
        if not stopped and self._run_next():
            return
        self.speed_line.stop()
        self._line_started = False
        elapsed = time.time() - getattr(self, "_t_start", time.time())
        self.lbl_cur.setText(("Stopped" if stopped else "Finished") + f" in {elapsed / 60:.1f} min")
        for r in range(self.table.rowCount()):
            if self.table.item(r, self.COL_STATUS).text() == "Queued":
                self._set_status(r, "Ready", "")
        self._update_buttons()
        if not stopped:
            QApplication.alert(self)
            if self.ck_open_done.isChecked() and getattr(self, "_run_ok", 0) > 0:
                for d in getattr(self, "_run_dirs", [])[:3]:      # whole run finished: open its folder(s)
                    if path.isdir(d):
                        QDesktopServices.openUrl(QUrl.fromLocalFile(d))

    # ---------- preview
    def preview_selected(self):
        r = self._selected_row()
        if r < 0:
            return
        item = self.items[r]
        t = 0.0
        if item["type"] == "Video" and getattr(self, "_dur", 0) > 0:
            t = self._dur * self.preview_time.value() / 1000.0
        s = self.collect()
        if not self._ensure_model(s):
            return
        self._previewing = True
        self._update_buttons()
        self.lbl_cur.setText("Rendering preview… (first run downloads the depth model)")
        self.pb_cur.setMaximum(0)
        tmp = path.join(tempfile.gettempdir(), "Stereo3DStudio_preview")

        def work():
            try:
                im = self.converter.render_preview(s, item["path"], tmp, t)
                self.bridge.preview_ready.emit(im, path.basename(item["path"]))
            except Exception as e:
                import traceback
                self.bridge.log.emit(traceback.format_exc())
                self.bridge.preview_ready.emit(None, str(e))

        threading.Thread(target=work, daemon=True).start()

    def on_preview_ready(self, im, title):
        self._previewing = False
        self.pb_cur.setMaximum(1)
        self.pb_cur.setValue(0)
        self._update_buttons()
        if im is None:
            self.lbl_cur.setText("Preview failed")
            QMessageBox.warning(self, APP_NAME, f"Preview failed:\n{title}\n\nOpen the Log for details.")
            return
        self.lbl_cur.setText("Idle")
        PreviewDialog(self, im, title).exec()

    # ---------- log
    def append_log(self, text):
        self.log.appendPlainText(text)
        if text.startswith("✖") and not self.btn_log.isChecked():
            self.btn_log.setChecked(True)

    # ---------- live view
    def _ensure_live(self):
        if self.live is None:
            self.live = LiveViewWindow(self, getattr(self, "_live_every", 100), self._set_live_every,
                                       mode=getattr(self, "_live_mode", 1),
                                       on_mode=lambda i: setattr(self, "_live_mode", int(i)),
                                       pinned=getattr(self, "_live_pinned", True),
                                       on_pin=self._live_pin_changed)
            self.live.closed.connect(lambda: self.btn_live.setChecked(False))
            self.live.resize(400, 268)          # small: each eye ~180 px wide, easy to free-view
            # default spot: centred over the lower part of the queue list
            t = self.table
            self._live_offset = QPoint((t.width() - self.live.width()) // 2,
                                       max(40, t.height() - self.live.height() - 30))
            self._dock_live()
        return self.live

    def _dock_live(self):
        """Keep a pinned Live view locked to the same spot over the queue."""
        if self.live is not None and self.live.pinned() and hasattr(self, "_live_offset"):
            self.live.move(self.table.mapToGlobal(QPoint(0, 0)) + self._live_offset)

    def _live_pin_changed(self, on):
        self._live_pinned = bool(on)
        if on and self.live is not None:   # pin it where it is now
            self._live_offset = self.live.pos() - self.table.mapToGlobal(QPoint(0, 0))

    def moveEvent(self, e):
        super().moveEvent(e)
        self._dock_live()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        QTimer.singleShot(0, self._dock_live)

    def changeEvent(self, e):
        super().changeEvent(e)
        if e.type() == e.Type.WindowStateChange:
            QTimer.singleShot(50, self._dock_live)

    def _set_live_every(self, n):
        self._live_every = int(n)
        self.converter.set_live_every(n)

    def toggle_live(self, on):
        if on:
            self._ensure_live().show()
        elif self.live is not None and self.live.isVisible():
            self.live.hide()

    def on_live_frame(self, im, n, layout_name):
        if self.btn_live.isChecked():
            w = self._ensure_live()
            if not w.isVisible():
                w.show()
            w.set_frame(im, n, layout_name)

    def closeEvent(self, e):
        if self.converter.running():
            if QMessageBox.question(self, APP_NAME, "A conversion is running. Stop it and quit?") != QMessageBox.Yes:
                e.ignore()
                return
            self.converter.stop()
            self.converter.thread.join(timeout=10)
        S.save_last(self.collect())
        e.accept()
