"""Monitoring and alerts computed from what the pipeline already writes (audit log, review queue, state files).

No extra infrastructure: `metrics()` reads the files, `check()` compares them with the thresholds in
`config/pipeline.yaml` (section `monitoring`) and records alert transitions (firing / resolved) in
`<out>/alerts.jsonl`, the audit log and, if configured, a webhook. Safe to run as often as you like: an alert that
is already firing is not re-sent.
"""
import json
import statistics
import threading
import time
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

from . import filing, llm

TS = "%Y-%m-%dT%H:%M:%S"
_LOCK = threading.Lock()  # the web watcher thread and API calls must not interleave state writes

# rule, metric key, comparison, threshold key in cfg.monitoring, severity, description
RULES = [
    ("review_queue_size", "review_queue_size", ">", "review_queue_max", "warning", "review queue is larger than agreed"),
    ("review_queue_age", "review_oldest_hours", ">", "review_oldest_hours_max", "warning", "oldest review ticket is too old"),
    ("review_rate", "review_rate", ">", "review_rate_max", "warning", "share of documents sent to review is above the ceiling"),
    ("validator_failure_rate", "validator_failure_rate", ">", "validator_failure_rate_max", "warning",
     "validator failures jumped (new template or model change?)"),
    ("model_invalid_rate", "llm_invalid_rate", ">", "llm_invalid_rate_max", "critical", "model replies failing the schema"),
    ("model_errors", "model_error_docs", ">", "model_error_docs_max", "critical", "documents hit model errors"),
    ("cost_per_doc", "cost_per_doc_usd", ">", "cost_per_doc_max_usd", "warning", "cost per document above budget"),
    ("call_latency_p95", "llm_p95_seconds", ">", "llm_p95_seconds_max", "warning", "model latency p95 above limit"),
    ("kb_sync_errors", "kb_sync_errors", ">", "kb_sync_errors_max", "critical", "knowledge-base publishing failed"),
    ("corrections_after_autofile", "corrected_after_autofile", ">", "corrected_after_autofile_max", "critical",
     "auto-filed documents later corrected or rolled back (quality signal)"),
    ("kill_switch", "kill_switch", "==", None, "info", "kill switch is on: nothing is auto-filed"),
]

DEFAULTS = {"window_hours": 24, "check_interval_minutes": 10, "webhook_url": None, "review_queue_max": 20,
            "review_oldest_hours_max": 24, "review_rate_max": 0.5, "validator_failure_rate_max": 0.5,
            "llm_invalid_rate_max": 0.2, "model_error_docs_max": 0, "cost_per_doc_max_usd": 0.10,
            "llm_p95_seconds_max": 90, "kb_sync_errors_max": 0, "corrected_after_autofile_max": 0}


def _cfg(cfg) -> dict:
    m = getattr(cfg, "monitoring", None)
    return {**DEFAULTS, **(vars(m) if m is not None else {})}


def _events(out: Path, since: datetime):
    f = out / "audit.jsonl"
    if not f.exists():
        return
    with open(f, encoding="utf-8") as fh:
        for line in fh:
            try:
                e = json.loads(line)
                if datetime.strptime(e["ts"], TS) >= since:
                    yield e
            except (ValueError, KeyError):
                continue  # a torn or foreign line must not break monitoring


def metrics(cfg, now: datetime | None = None) -> dict:
    out = Path(cfg.paths.out)
    mc = _cfg(cfg)
    now = now or datetime.now()
    since = now - timedelta(hours=mc["window_hours"])
    decisions, calls, kb_errors, auto_filed_ids, touched_after = [], [], 0, set(), set()
    for e in _events(out, since):
        ev = e.get("event")
        if ev == "decision":
            decisions.append(e)
            if e.get("decision") == "auto_filed":
                auto_filed_ids.add(e.get("doc_id"))
        elif ev == "llm_call":
            calls.append(e)
        elif ev == "kb_sync" and e.get("ov_status") == "error":
            kb_errors += 1
        elif ev in ("human_correction", "rollback") and e.get("doc_id") in auto_filed_ids:
            touched_after.add(e.get("doc_id"))
    n = len(decisions)
    review = [d for d in decisions if d.get("decision") == "review"]
    val_fail = [d for d in decisions if any(str(r).startswith("validator_failed") for r in d.get("reasons") or [])]
    model_err = [d for d in decisions if any(str(r).startswith("model_error") for r in d.get("reasons") or [])]
    costs = [d.get("usage", {}).get("cost_usd_list_price", 0) for d in decisions if d.get("usage")]
    secs = sorted(c.get("seconds", 0) for c in calls)
    items = list((out / "_review").glob("*.json")) if (out / "_review").exists() else []
    oldest = max(((now.timestamp() - f.stat().st_mtime) / 3600 for f in items), default=0.0)
    return {
        "window_hours": mc["window_hours"], "at": now.strftime(TS),
        "documents": n, "auto_filed": sum(d.get("decision") == "auto_filed" for d in decisions),
        "review_rate": round(len(review) / n, 3) if n else 0.0,
        "validator_failure_rate": round(len(val_fail) / n, 3) if n else 0.0,
        "model_error_docs": len(model_err),
        "review_queue_size": len(items), "review_oldest_hours": round(max(oldest, 0.0), 1),
        "llm_calls": len(calls),
        "llm_invalid_rate": round(sum(not c.get("valid", True) for c in calls) / len(calls), 3) if calls else 0.0,
        "llm_p50_seconds": round(statistics.median(secs), 1) if secs else 0.0,
        "llm_p95_seconds": round(secs[min(len(secs) - 1, int(0.95 * len(secs)))], 1) if secs else 0.0,
        "cost_per_doc_usd": round(sum(costs) / len(costs), 5) if costs else 0.0,
        "kb_sync_errors": kb_errors,
        "corrected_after_autofile": len(touched_after),
        "kill_switch": (out / cfg.governance.kill_switch_file).exists(),
    }


def evaluate(m: dict, cfg) -> list:
    """Pure: which rules fire for these metrics."""
    mc = _cfg(cfg)
    firing = []
    for rule, key, op, tkey, sev, desc in RULES:
        v = m.get(key)
        thr = True if tkey is None else mc[tkey]
        hit = (v == thr) if op == "==" else (v is not None and thr is not None and v > thr)
        if hit:
            firing.append({"rule": rule, "severity": sev, "value": v, "threshold": thr, "message": desc})
    return firing


def _state_path(out: Path) -> Path:
    return out / "_monitor" / "active.json"


def active(cfg) -> list:
    f = _state_path(Path(cfg.paths.out))
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else []


def _notify(url: str, payload: dict) -> bool:
    try:
        req = urllib.request.Request(url, data=json.dumps(payload, ensure_ascii=False).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
        urllib.request.urlopen(req, timeout=5).close()
        return True
    except Exception:  # noqa: BLE001 - a dead webhook must not stop monitoring; alerts.jsonl still has the alert
        return False


def check(cfg, now: datetime | None = None) -> dict:
    """Compute metrics, compare with thresholds, record transitions. Returns metrics, active alerts and transitions."""
    with _LOCK:
        return _check(cfg, now)


def _check(cfg, now):
    out = Path(cfg.paths.out)
    mc = _cfg(cfg)
    m = metrics(cfg, now)
    firing = evaluate(m, cfg)
    before = {a["rule"]: a for a in active(cfg)}
    after = {a["rule"]: a for a in firing}
    ts = m["at"]
    transitions = [{"state": "firing", **a} for r, a in after.items() if r not in before]
    transitions += [{"state": "resolved", **a} for r, a in before.items() if r not in after]
    current = [{**a, "since": before.get(r, {}).get("since", ts)} for r, a in after.items()]
    _state_path(out).parent.mkdir(parents=True, exist_ok=True)
    _state_path(out).write_text(json.dumps(current, ensure_ascii=False, indent=1), encoding="utf-8")
    if transitions:
        audit = llm.AuditLog(out / "audit.jsonl")
        with open(out / "alerts.jsonl", "a", encoding="utf-8") as f:
            for t in transitions:
                f.write(json.dumps({**t, "ts": ts}, ensure_ascii=False) + "\n")
                audit.write(event="alert", **{k: v for k, v in t.items() if k not in ("ts", "since")})
        if mc.get("webhook_url"):
            _notify(mc["webhook_url"], {"source": "docpipe", "pipeline_version": filing.PIPELINE_VERSION,
                                        "transitions": transitions, "metrics": m})
    return {"metrics": m, "active": current, "transitions": transitions}


def history(cfg, limit: int = 50) -> list:
    f = Path(cfg.paths.out) / "alerts.jsonl"
    if not f.exists():
        return []
    lines = f.read_text(encoding="utf-8").splitlines()[-limit:]
    return [json.loads(x) for x in reversed(lines) if x.strip()]


def watch(cfg, stop=None):
    """Loop for a scheduler-less deployment (the web app runs this in a thread)."""
    interval = max(30, int(_cfg(cfg)["check_interval_minutes"] * 60))
    while not (stop and stop.is_set()):
        try:
            check(cfg)
        except Exception:  # noqa: BLE001 - keep watching; the next tick retries
            pass
        if stop:
            stop.wait(interval)
        else:
            time.sleep(interval)
