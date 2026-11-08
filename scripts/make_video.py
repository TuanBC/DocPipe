"""Turn the raw recording into submission/DocPipe_demo.mp4: the wait for the jobs is played 10x faster (and says so),
subtitle timings are shifted to match, and the narration is burned in. Also writes submission/DocPipe_demo.srt.

Run after scripts/record_demo.py:  uv run python scripts/make_video.py
Needs ffmpeg on PATH.
"""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEMO, SUB = ROOT / "demo", ROOT / "submission"
SPEED = 10.0
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


def main():
    cues = json.loads((DEMO / "narration.json").read_text(encoding="utf-8"))
    # the recorder's clock starts before the first video frame: align the cue timeline to the video's end
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", "raw.webm"],
                               cwd=DEMO, capture_output=True, text=True, check=True).stdout.strip())
    shift = min(0.0, dur - cues[-1]["end"])
    for c in cues:
        c["start"], c["end"] = max(0.0, c["start"] + shift), max(0.0, c["end"] + shift)
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
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", "raw.webm", "-filter_complex", fc, "-map", "[out]",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                    str(SUB / "DocPipe_demo.mp4")], cwd=DEMO, check=True)  # run in demo/: the subtitles filter dislikes drive colons
    print(f"wrote {SUB / 'DocPipe_demo.mp4'} ({out[-1]['end']:.0f} s) and DocPipe_demo.srt")


if __name__ == "__main__":
    main()
