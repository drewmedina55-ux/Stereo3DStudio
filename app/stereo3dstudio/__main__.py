"""Stereo3D Studio entry point."""
import os
import sys
import time
from os import path

HERE = path.dirname(path.abspath(__file__))
ROOT = path.normpath(path.join(HERE, "..", ".."))           # install root
ENGINE = path.join(ROOT, "engine")                          # bundled nunif/iw3 source


def _data_dir():
    base = os.environ.get("LOCALAPPDATA") or path.expanduser("~/.local/share")
    return path.join(base, "Stereo3DStudio")


def _setup_env():
    try:
        from .migrate import migrate_old_data
        migrate_old_data()
    except Exception:
        pass
    data = _data_dir()
    # Models live in a "models" folder next to Stereo3DStudio.exe - copy it into new versions.
    models = path.join(ROOT, "models")
    try:
        from .migrate import migrate_models
        migrate_models(models)
    except Exception:
        pass
    os.environ.setdefault("NUNIF_HOME", models)
    os.environ.setdefault("TORCH_HOME", path.join(models, "torch"))
    os.makedirs(os.environ["NUNIF_HOME"], exist_ok=True)
    os.makedirs(path.join(data, "logs"), exist_ok=True)
    if ENGINE not in sys.path:
        sys.path.insert(0, ENGINE)
    return data


def selftest():
    """Used by the installer: proves the app can start (imports, GPU, Qt, main window)."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    _setup_env()
    print("python", sys.version.split()[0], flush=True)
    import torch
    print("torch", torch.__version__, "cuda", torch.cuda.is_available(), flush=True)
    from nunif.utils.video import pyav_init_cuda_primary_context
    try:
        pyav_init_cuda_primary_context()
    except Exception as e:
        print("pyav cuda context:", e, flush=True)
    import PySide6
    from PySide6.QtWidgets import QApplication
    print("PySide6", PySide6.__version__, flush=True)
    app = QApplication(["stereo3dstudio"])
    from .ui import MainWindow, STYLE
    app.setStyleSheet(STYLE)
    win = MainWindow()
    win.show()
    app.processEvents()
    print("main window OK:", win.windowTitle(), flush=True)
    win.close()
    return 0


def main():
    if "--selftest" in sys.argv:
        return selftest()
    data = _setup_env()
    log_path = path.join(data, "logs", time.strftime("stereo3dstudio_%Y%m%d_%H%M%S.log"))
    logfile = open(log_path, "w", encoding="utf-8", errors="replace")
    print("log:", log_path, flush=True)
    try:
        import faulthandler
        faulthandler.enable(logfile)
    except Exception:
        pass
    # torch must load its CUDA DLLs before Qt on Windows (avoids DLL init conflicts)
    import torch  # noqa: F401

    from PySide6.QtCore import Qt
    from PySide6.QtGui import QPixmap, QIcon, QFont
    from PySide6.QtWidgets import QApplication, QSplashScreen, QMessageBox

    app = QApplication(sys.argv)
    app.setApplicationName("Stereo3DStudio")
    app.setFont(QFont("Segoe UI", 10))
    icon_png = path.join(ROOT, "assets", "icon.png")
    if path.exists(icon_png):
        app.setWindowIcon(QIcon(icon_png))

    splash = None
    splash_png = path.join(ROOT, "assets", "splash.png")
    if path.exists(splash_png):
        from PySide6.QtGui import QPainter, QColor, QFont as _QFont
        from . import VERSION as _V, AUTHOR as _A
        pm = QPixmap(splash_png)
        p = QPainter(pm)
        p.setRenderHint(QPainter.TextAntialiasing)
        f = _QFont("Segoe UI")
        f.setPixelSize(17)
        p.setFont(f)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QColor("#8c8c96"))
        p.drawText(178, 161, f"by {_A}   ·   version {_V}")   # logo is part of splash.png
        p.end()
        splash = QSplashScreen(pm)
        splash.setAttribute(Qt.WA_TranslucentBackground)       # rounded, bevelled corners
        splash.show()
        splash.showMessage("Loading GPU engine…", Qt.AlignBottom | Qt.AlignHCenter, Qt.white)
        app.processEvents()

    try:
        if sys.platform == "win32":  # no console windows flashing for child processes
            import subprocess
            _orig_init = subprocess.Popen.__init__

            def _popen_init(self, *a, **kw):
                kw["creationflags"] = kw.get("creationflags", 0) | 0x08000000
                return _orig_init(self, *a, **kw)

            subprocess.Popen.__init__ = _popen_init
        from nunif.utils.video import pyav_init_cuda_primary_context
        try:
            pyav_init_cuda_primary_context()
        except Exception:
            pass
        from .ui import MainWindow, STYLE, Bridge, StreamToSignal
    except Exception:
        import traceback
        msg = traceback.format_exc()
        logfile.write(msg)
        logfile.flush()
        if splash:
            splash.close()
        QMessageBox.critical(None, "Stereo3D Studio", "The 3D engine failed to load.\n\n" + msg[-1500:] +
                             f"\n\nLog: {log_path}")
        return 1

    app.setStyleSheet(STYLE)
    win = MainWindow(icon_path=icon_png, log_path=log_path)

    # route print/tqdm/warnings into the log panel + log file
    stream = StreamToSignal(win.bridge, logfile)
    sys.stdout = stream
    sys.stderr = stream
    import warnings
    warnings.showwarning = lambda m, c, f, l, file=None, line=None: stream.write(f"{c.__name__}: {m}\n")

    win.showMaximized()
    if splash:
        splash.finish(win)
    win.append_log(f"Stereo3D Studio ready. Models folder: {os.environ['NUNIF_HOME']}")
    win.append_log(f"Log file: {log_path}")
    if len(sys.argv) > 1:
        win.add_paths([a for a in sys.argv[1:] if path.exists(a)])
    return app.exec()


if __name__ == "__main__":
    try:
        code = main()
    except SystemExit:
        raise
    except BaseException:
        import traceback
        traceback.print_exc()
        sys.stderr.flush()
        code = 1
    sys.exit(code or 0)
