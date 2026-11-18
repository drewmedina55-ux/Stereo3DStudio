"""Conversion preview ("sizzle reel"): random moments spread through a video, joined into one short 2D clip."""
import os
import random
from fractions import Fraction
from os import path

import av


def pick_moments(duration, total_sec=60.0, clip_sec=8.0, seed=None):
    """Return sorted [(start, length)] evenly spread through the video, random within each slice."""
    rng = random.Random(seed)
    total_sec = max(1.0, float(total_sec))
    clip_sec = max(1.0, min(float(clip_sec), total_sec))
    if duration <= 0:
        return []
    if duration <= total_sec + 1:
        return [(0.0, duration)]
    n = max(1, int(-(-total_sec // clip_sec)))          # ceil: last clip is trimmed so the total is exact
    lengths = [clip_sec] * (n - 1) + [total_sec - clip_sec * (n - 1)]
    # skip the very start/end (logos, credits)
    margin = min(duration * 0.03, 60.0)
    lo, hi = margin, duration - margin
    if hi - lo < n * clip_sec:
        lo, hi = 0.0, duration
    slice_len = (hi - lo) / n
    moments = []
    for i in range(n):
        a = lo + i * slice_len
        b = a + slice_len - lengths[i]
        start = a if b <= a else rng.uniform(a, b)
        moments.append((round(start, 3), lengths[i]))
    return moments


def _even(x):
    return x - (x % 2)


def build_sizzle(src, dst, total_sec=60.0, clip_sec=8.0, seed=None, progress=None, stop_event=None):
    """Write a 2D clip made of random moments of `src` to `dst`. Returns the moments used."""
    with av.open(src) as probe:
        dur = probe.duration / 1_000_000 if probe.duration else 0.0
        if not dur and probe.streams.video:
            s = probe.streams.video[0]
            if s.duration and s.time_base:
                dur = float(s.duration * s.time_base)
    moments = pick_moments(dur, total_sec, clip_sec, seed)
    if not moments:
        raise RuntimeError("Could not read the video's length.")

    inp = av.open(src)
    try:
        vin = inp.streams.video[0]
        ain = inp.streams.audio[0] if inp.streams.audio else None
        fps = vin.average_rate or vin.guessed_rate or Fraction(30, 1)
        fps = Fraction(fps).limit_denominator(1001)
        w, h = _even(vin.codec_context.width), _even(vin.codec_context.height)

        os.makedirs(path.dirname(dst) or ".", exist_ok=True)
        out = av.open(dst, "w")
        try:
            vout = out.add_stream("libx264", rate=fps)
            vout.width, vout.height, vout.pix_fmt = w, h, "yuv420p"
            vout.codec_context.time_base = 1 / fps
            vout.options = {"crf": "14", "preset": "veryfast"}
            aout = None
            if ain is not None:
                try:
                    aout = out.add_stream("aac", rate=48000, layout="stereo")
                    aout.bit_rate = 192000
                except Exception:
                    aout = None
            resampler = av.AudioResampler(format="fltp", layout="stereo", rate=48000) if aout else None

            vpts = 0
            apts = 0
            steps = len(moments) * (2 if aout else 1)
            step = 0
            for start, length in moments:
                end = start + length
                seg_start_vpts = vpts
                # ---- video
                inp.seek(int(start / vin.time_base), stream=vin, backward=True, any_frame=False)
                for frame in inp.decode(vin):
                    if stop_event is not None and stop_event.is_set():
                        raise RuntimeError("Cancelled")
                    t = frame.time
                    if t is None:
                        continue
                    if t < start - 1e-3:
                        continue
                    if t >= end:
                        break
                    f = frame.reformat(width=w, height=h, format="yuv420p")
                    f.pts = vpts
                    f.time_base = vout.codec_context.time_base
                    vpts += 1
                    for p in vout.encode(f):
                        out.mux(p)
                step += 1
                if progress:
                    progress(step, steps)
                # ---- audio (same length as the video we actually got)
                if aout:
                    seg_len = (vpts - seg_start_vpts) / float(fps)
                    seg_samples = int(round(seg_len * 48000))
                    written = 0
                    try:
                        inp.seek(int(start / ain.time_base), stream=ain, backward=True, any_frame=False)
                        for frame in inp.decode(ain):
                            t = frame.time
                            if t is None or t + frame.samples / frame.sample_rate <= start:
                                continue
                            if t >= start + seg_len or written >= seg_samples:
                                break
                            for rf in resampler.resample(frame):
                                if written >= seg_samples:
                                    break
                                rf.pts = apts
                                rf.time_base = Fraction(1, 48000)
                                apts += rf.samples
                                written += rf.samples
                                for p in aout.encode(rf):
                                    out.mux(p)
                    except Exception:
                        pass
                    # keep audio in step with video if the segment's audio was short
                    if written < seg_samples:
                        apts += seg_samples - written
                    step += 1
                    if progress:
                        progress(step, steps)
            for p in vout.encode(None):
                out.mux(p)
            if aout:
                for p in aout.encode(None):
                    out.mux(p)
        finally:
            out.close()
    finally:
        inp.close()
    if vpts == 0:
        raise RuntimeError("No frames could be read for the conversion preview.")
    return moments
