"""One-time move of data from the app's old name (StereoForge) to Stereo3DStudio.

Keeps downloaded depth models (several GB), settings and presets."""
import os
import shutil
from os import path


def _merge_move(old, new):
    if not path.isdir(old):
        return
    os.makedirs(new, exist_ok=True)
    for name in os.listdir(old):
        src, dst = path.join(old, name), path.join(new, name)
        if path.exists(dst):
            if path.isdir(src) and path.isdir(dst):
                _merge_move(src, dst)
            continue
        try:
            shutil.move(src, dst)
        except Exception:
            pass
    try:
        if not os.listdir(old):
            os.rmdir(old)
    except Exception:
        pass


def migrate_old_data():
    for var in ("LOCALAPPDATA", "APPDATA"):
        base = os.environ.get(var)
        if base:
            for old_name in ("StereoForge", "Convert3D", "StereoStudio"):     # the app's earlier names
                old = path.join(base, old_name)
                if path.isdir(old):
                    _merge_move(old, path.join(base, "Stereo3DStudio"))


def _safe_move_tree(src, dst, log=None):
    """Move every file from src into dst, resumable: copy to .part, rename, then delete the source."""
    moved = 0
    for dirpath, _dirs, files in os.walk(src):
        rel = path.relpath(dirpath, src)
        out_dir = path.join(dst, rel) if rel != "." else dst
        os.makedirs(out_dir, exist_ok=True)
        for name in files:
            s, d = path.join(dirpath, name), path.join(out_dir, name)
            try:
                if path.exists(d) and path.getsize(d) == path.getsize(s):
                    os.remove(s)
                    continue
                if path.getsize(s) > 50_000_000 and log:
                    log(f"  moving {name} ({path.getsize(s) / 1e9:.1f} GB)...")
                try:
                    os.replace(s, d)                     # same drive: instant
                except OSError:
                    shutil.copy2(s, d + ".part")         # other drive: copy, then swap in
                    os.replace(d + ".part", d)
                    os.remove(s)
                moved += 1
            except Exception:
                pass
    # remove emptied folders
    for dirpath, _dirs, _files in sorted(os.walk(src), key=lambda x: -len(x[0])):
        try:
            os.rmdir(dirpath)
        except OSError:
            pass
    return moved


def migrate_models(dst, log=None):
    """Move depth models from the old AppData location(s) into the app's own models folder."""
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        return 0
    total = 0
    for name in ("StereoForge", "Convert3D", "StereoStudio", "Stereo3DStudio"):
        src = path.join(base, name, "models")
        if path.isdir(src) and path.normcase(path.abspath(src)) != path.normcase(path.abspath(dst)):
            if log:
                log(f"Moving downloaded models from {src} to {dst}")
            total += _safe_move_tree(src, dst, log)
    return total
