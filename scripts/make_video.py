"""Turn the raw recording into submission/DocPipe_demo.mp4:
  1. camera: zoom smoothly into the element being narrated (demo/zooms.json from record_demo.py) and back out;
  2. the wait for the jobs is played 10x faster (and the subtitle says so);
  3. the narration is burned in as subtitles; submission/DocPipe_demo.srt keeps the timings for a voice-over.

Run after scripts/record_demo.py:  uv run python scripts/make_video.py      (needs ffmpeg and Pillow)
"""
import json
import subprocess
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
DEMO, SUB = ROOT / "demo", ROOT / "submission"
W, H, FPS = 1440, 900, 25
SPEED = 10.0
EASE = 0.8           # seconds for a zoom move
MIN_W = 560          # narrowest crop (about 2.6x zoom), keeps text sharp enough
CAP_W = 900          # wide but short elements (full-width rows) get at least 1.6x
WAIT_CUE = "Back in the inbox, the jobs are finishing."


def srt_time(t):
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def wrap(text, width=80):
    lines, cur = [], ""
    for w in text.split():
        if cur and len(cur) + len(w) + 1 > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    return "\n".join(lines + [cur])


# ---------- camera ----------
FULL = (0.0, 0.0, float(W))


def fit(box):
    """Smallest 16:10 crop (x, y, width) that shows the element; tall elements are shown from their top."""
    if box is None:
        return FULL
    x, y, w, h = box
    cw = min(float(W), max(min(w, CAP_W), h * W / H, MIN_W))
    ch = cw * H / W
    cx = x + w / 2 if w <= cw else x + cw / 2   # wide rows: show their left part, where the text starts
    cy = y + h / 2 if h <= ch else y + ch / 2
    x0 = min(max(cx - cw / 2, 0.0), W - cw)
    y0 = min(max(cy - ch / 2, 0.0), H - ch)
    return (x0, y0, cw)


def smooth(u):
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)


def build_camera(keys):
    segs, cur_start, cur_target, cur_t = [], FULL, FULL, -1e9
    for k in sorted(keys, key=lambda k: k["t"]):
        e = smooth((k["t"] - cur_t) / EASE)
        start = tuple(a + (b - a) * e for a, b in zip(cur_start, cur_target))  # where the camera is right now
        target = fit(k["box"])
        segs.append((k["t"], start, target))
        cur_start, cur_target, cur_t = start, target, k["t"]

    def at(t):
        seg = None
        for s in segs:
            if s[0] <= t:
                seg = s
            else:
                break
        if seg is None:
            return FULL
        e = smooth((t - seg[0]) / EASE)
        return tuple(a + (b - a) * e for a, b in zip(seg[1], seg[2]))
    return at


def render_camera(src: Path, dst: Path, keys):
    cam = build_camera(keys)
    dec = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-i", str(src), "-vf", f"fps={FPS},scale={W}:{H}",
                            "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    enc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "fast", "-crf", "14",
                            "-pix_fmt", "yuv420p", str(dst)], stdin=subprocess.PIPE)
    n, size = 0, W * H * 3
    while True:
        buf = dec.stdout.read(size)
        if len(buf) < size:
            break
        x0, y0, cw = cam(n / FPS)
        img = Image.frombytes("RGB", (W, H), buf)
        if cw < W - 0.5:
            img = img.crop((x0, y0, x0 + cw, y0 + cw * H / W)).resize((W, H), Image.Resampling.BICUBIC)
        enc.stdin.write(img.tobytes())
        n += 1
    enc.stdin.close()
    enc.wait()
    dec.wait()
    return n / FPS


def main():
    cues = json.loads((DEMO / "narration.json").read_text(encoding="utf-8"))
    zf = DEMO / "zooms.json"
    cam = json.loads(zf.read_text(encoding="utf-8")) if zf.exists() else {"keys": [], "t_close": None}
    keys = cam["keys"]
    # the video starts when the browser context opens, a moment before the recorder's clock: align both timelines
    # by the moment the context closed (the end of the video)
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", "raw.webm"],
                               cwd=DEMO, capture_output=True, text=True, check=True).stdout.strip())
    shift = dur - (cam["t_close"] if cam.get("t_close") else cues[-1]["end"])
    print(f"timeline shift {shift:+.2f} s")
    for c in cues:
        c["start"], c["end"] = max(0.0, c["start"] + shift), max(0.0, c["end"] + shift)
    for k in keys:
        k["t"] = max(0.0, k["t"] + shift)

    zoomed = DEMO / "zoomed.mp4"
    secs = render_camera(DEMO / "raw.webm", zoomed, keys)
    print(f"camera pass: {secs:.0f} s, {len(keys)} moves")

    i = next(k for k, c in enumerate(cues) if c["text"] == WAIT_CUE)
    a, b = cues[i]["start"] + 3.0, cues[i + 1]["start"] - 3.0   # keep 3 s of real time on each side
    gap = (b - a) * (1 - 1 / SPEED)

    def remap(t):
        return t if t <= a else (a + (t - a) / SPEED if t <= b else t - gap)

    out = []
    for c in cues:
        text = c["text"] + (f" (waiting shown {SPEED:.0f}x faster)" if c["text"] == WAIT_CUE else "")
        out.append({"start": remap(c["start"]), "end": remap(c["end"]), "text": text})
    srt = "\n".join(f"{k}\n{srt_time(c['start'])} --> {srt_time(c['end'])}\n{wrap(c['text'])}\n" for k, c in enumerate(out, 1))
    (DEMO / "final.srt").write_text(srt, encoding="utf-8")
    SUB.mkdir(exist_ok=True)
    (SUB / "DocPipe_demo.srt").write_text(srt, encoding="utf-8")

    style = ("FontName=Arial,FontSize=12,PrimaryColour=&H00FFFFFF,BackColour=&H99000000,BorderStyle=4,"
             "Outline=0,Shadow=0,MarginV=24")
    fc = (f"[0:v]trim=0:{a:.2f},setpts=PTS-STARTPTS[v1];"
          f"[0:v]trim={a:.2f}:{b:.2f},setpts=(PTS-STARTPTS)/{SPEED}[v2];"
          f"[0:v]trim=start={b:.2f},setpts=PTS-STARTPTS[v3];"
          f"[v1][v2][v3]concat=n=3:v=1:a=0[cat];[cat]subtitles=final.srt:force_style='{style}'[out]")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", "zoomed.mp4", "-filter_complex", fc, "-map", "[out]",
                    "-r", str(FPS), "-c:v", "libx264", "-preset", "medium", "-crf", "22", "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart", str(SUB / "DocPipe_demo.mp4")], cwd=DEMO, check=True)
    print(f"wrote {SUB / 'DocPipe_demo.mp4'} ({out[-1]['end']:.0f} s) and DocPipe_demo.srt")


if __name__ == "__main__":
    main()
