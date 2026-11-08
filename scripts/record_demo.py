"""Record the DocPipe demo video by driving the real web UI with Playwright, and write narration subtitles.

Prerequisites: services running (scripts/start_services.ps1) and the UI on http://127.0.0.1:8800.
Run:  uv run --group gateway --with playwright==1.55.0 python scripts/record_demo.py
Out:  demo/raw.webm and demo/DocPipe_demo.srt (narration = subtitles); scripts/make_video.ps1 burns them into an MP4.

The three uploads are synthetic scans of fictional companies from evals/make_eval_set.py.
"""
import hashlib
import json
import shutil
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:8800"
OUT = Path("demo")
SET = Path("data/eval/general_set")
UPLOADS = ["03_hopdong_vay_hung_thinh.pdf", "04_hoadon_sao_viet_binh_minh.jpg", "11_thucdon_out_of_taxonomy.jpg"]
ROLLBACK_DOC = "06aaadd289439e91"  # sample invoice that already has filed versions
QUESTION = "Hợp đồng cho vay của Công ty Cổ phần Xây dựng Hưng Thịnh: số tiền vay, thời hạn và lãi suất là bao nhiêu?"

cues = []
t0 = 0.0


def say(text, hold=0.0):
    """Start a subtitle cue now; the previous cue ends here."""
    now = time.monotonic() - t0
    if cues and cues[-1]["end"] is None:
        cues[-1]["end"] = now
    cues.append({"start": now, "end": None, "text": text})
    print(f"[{now:6.1f}s] {text}", flush=True)
    if hold:
        time.sleep(hold)


def doc_id(name):
    return hashlib.sha256((SET / name).read_bytes()).hexdigest()[:16]


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


def wait_jobs_done(page, timeout=480):
    end = time.time() + timeout
    while time.time() < end:
        jobs = page.evaluate("fetch('/api/jobs').then(r => r.json())")
        if jobs and all(j.get("status") not in ("queued", "running") for j in jobs):
            return jobs
        time.sleep(2)
    raise TimeoutError("jobs did not finish")


def main():
    global t0
    OUT.mkdir(exist_ok=True)
    vid_dir = OUT / "_video"
    shutil.rmtree(vid_dir, ignore_errors=True)
    ids = {n: doc_id(n) for n in UPLOADS}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, record_video_dir=str(vid_dir),
                                  record_video_size={"width": 1440, "height": 900})
        page = ctx.new_page()
        t0 = time.monotonic()
        page.on("dialog", lambda d: d.accept("TuanBC" if "name" in d.message.lower() else "demo: restore the earlier version"))
        page.goto(URL + "/#inbox")
        page.wait_for_timeout(1500)

        say("DocPipe turns the scans in a corporate credit file into filed, checked and searchable documents.", 4)
        say("A credit officer drops three scans: a loan contract, a supplier invoice photo, and a restaurant menu that does not belong.", 2)
        page.check("#force")  # re-run even if these samples were processed before (cached pages make it cheap)
        page.set_input_files("#file", [str(SET / n) for n in UPLOADS])
        page.wait_for_timeout(2500)
        say("Each file becomes a job. Page images are read by a vision model; pages with a text layer are read for free.", 6)
        page.locator("#jobs").scroll_into_view_if_needed()
        say("The live log shows every step: OCR, classification against a fixed taxonomy, the checks, filing and publishing.", 7)

        say("While the jobs run, the System tab. Every service is healthy, and the monitor reads the audit log.", 0)
        page.click("#nav button[data-v=system]")
        page.wait_for_timeout(4000)
        page.locator("#mon-active").scroll_into_view_if_needed()
        say("It tracks review rate, queue age, schema errors, latency and cost per document, against thresholds in the config.", 6)
        say("A real alert is firing: one review ticket has waited longer than the 24-hour limit. Alerts also go to a team webhook.", 7)

        page.click("#nav button[data-v=inbox]")
        say("Back in the inbox, the jobs are finishing.", 0)
        wait_jobs_done(page)
        page.wait_for_timeout(2500)
        say("The contract and the invoice were filed automatically. The menu is outside the taxonomy, so it waits for a person.", 6)

        # library: contract
        page.click("#nav button[data-v=library]")
        page.wait_for_timeout(2000)
        page.evaluate("id => openDoc(id)", ids[UPLOADS[0]])
        page.wait_for_timeout(3500)
        say("The contract is filed under the borrower, Hung Thinh, not under the bank printed first: company, year, document type.", 6)
        say("The page image sits next to the OCR text, so anyone can check a line against the original.", 6)
        page.click("#d-tabs button[data-t=checks]")
        page.wait_for_timeout(1500)
        say("A contract has no tables, so two deterministic checks gate auto-filing: the quoted evidence and the company name must really appear in the text.", 8)

        # library: invoice
        page.evaluate("id => openDoc(id)", ids[UPLOADS[1]])
        page.wait_for_timeout(3500)
        say("The invoice goes to the buyer, the bank's customer, not to the seller printed at the top. Six test documents are built to trap exactly this.", 8)

        # review queue
        page.click("#nav button[data-v=review]")
        page.wait_for_timeout(2500)
        say("The review queue: the menu waits with its reasons. Nothing in this queue reaches the knowledge base until a named reviewer approves it.", 8)

        # knowledge base
        page.click("#nav button[data-v=kb]")
        page.wait_for_timeout(2500)
        page.fill("#q", QUESTION)
        say("Staff ask questions in Vietnamese. OpenViking ranks the documents; our own index picks the page and enforces the caller's clearance.", 1)
        page.click("#q-go")
        page.wait_for_function("!document.querySelector('#q-go').disabled", timeout=180000)
        page.wait_for_timeout(1500)
        say("The answer cites the page it came from. A question the documents cannot answer is refused instead of guessed.", 6)
        cite = page.locator("#answer [data-cite]").first
        if cite.count():
            cite.click()
            page.wait_for_timeout(3500)
            say("One click on the citation opens the exact page.", 4)
        page.click("#nav button[data-v=kb]")
        page.wait_for_timeout(2500)
        page.locator("#kbtree").scroll_into_view_if_needed()
        say("Inside OpenViking, published documents mirror the same folder tree, with masked text and a summary per document.", 6)

        # versions + rollback
        page.click("#nav button[data-v=library]")
        page.wait_for_timeout(1500)
        page.evaluate("id => openDoc(id)", ROLLBACK_DOC)
        page.wait_for_timeout(2500)
        page.click("#d-tabs button[data-t=versions]")
        page.wait_for_timeout(2000)
        say("Every time a filed document is replaced, the earlier version is kept.", 4)
        btn = page.locator("[data-rb]").first
        if btn.count():
            btn.click()
            page.wait_for_timeout(2500)
            say("Rolling back restores it to its folder, re-publishes it, and writes the reviewer's name to the audit log. A whole bad release can be undone the same way.", 7)

        # kill switch
        page.click("#nav button[data-v=system]")
        page.wait_for_timeout(2500)
        page.locator("#kill").scroll_into_view_if_needed()
        page.click("#kill")
        page.wait_for_timeout(2000)
        say("If something looks wrong, the kill switch sends every new document to review. One click, logged with who did it.", 5)
        page.click("#kill")
        page.wait_for_timeout(1500)
        page.click("#mon-check")
        page.locator("#mon-active").scroll_into_view_if_needed()
        say("A model reads; our checks decide; a person approves what is uncertain. All data shown is synthetic or public.", 6)
        say("", 0.5)

        ctx.close()
        browser.close()
    cues[-1]["end"] = cues[-1]["start"] + 0.5
    cues[:] = [c for c in cues if c["text"]]
    video = next(vid_dir.glob("*.webm"))
    shutil.move(str(video), OUT / "raw.webm")
    shutil.rmtree(vid_dir, ignore_errors=True)
    srt = "\n".join(f"{i}\n{srt_time(c['start'])} --> {srt_time(c['end'])}\n{wrap(c['text'])}\n" for i, c in enumerate(cues, 1))
    (OUT / "DocPipe_demo.srt").write_text(srt, encoding="utf-8")
    (OUT / "narration.json").write_text(json.dumps(cues, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"video {OUT / 'raw.webm'}  subtitles {OUT / 'DocPipe_demo.srt'}  length {cues[-1]['end']:.0f}s")


if __name__ == "__main__":
    main()
