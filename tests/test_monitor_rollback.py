"""Offline tests for the Part C controls: monitoring/alerts and version rollback (no model or server calls)."""
import json
from datetime import datetime

from docpipe import config, filing, monitor, pipeline

DOC = "0123456789abcdef"


def cfg_at(tmp_path, **mon):
    cfg = config.load()
    cfg.paths.out = str(tmp_path)  # redirected output: the publish guard keeps the real KB untouched
    for k, v in mon.items():
        setattr(cfg.monitoring, k, v)
    return cfg


def audit(tmp_path, *events, ts="2026-11-09T10:00:00"):
    with open(tmp_path / "audit.jsonl", "a", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps({**e, "ts": ts}) + "\n")


NOW = datetime(2026, 11, 9, 12, 0, 0)


def test_metrics_from_audit_log(tmp_path):
    cfg = cfg_at(tmp_path)
    audit(tmp_path,
          {"event": "decision", "doc_id": "a", "decision": "auto_filed", "reasons": [], "usage": {"cost_usd_list_price": 0.002}},
          {"event": "decision", "doc_id": "b", "decision": "review", "reasons": ["validator_failed: x"], "usage": {"cost_usd_list_price": 0.004}},
          {"event": "llm_call", "seconds": 4.0, "valid": True}, {"event": "llm_call", "seconds": 10.0, "valid": False},
          {"event": "kb_sync", "ov_status": "error"}, {"event": "human_correction", "doc_id": "a"})
    audit(tmp_path, {"event": "decision", "doc_id": "old", "decision": "review", "reasons": []}, ts="2026-11-01T10:00:00")
    m = monitor.metrics(cfg, NOW)
    assert m["documents"] == 2  # the event outside the 24 h window is ignored
    assert m["review_rate"] == 0.5 and m["validator_failure_rate"] == 0.5
    assert m["llm_invalid_rate"] == 0.5 and m["cost_per_doc_usd"] == 0.003
    assert m["kb_sync_errors"] == 1 and m["corrected_after_autofile"] == 1


def test_alerts_fire_once_then_resolve(tmp_path):
    cfg = cfg_at(tmp_path, review_queue_max=1, webhook_url=None)
    (tmp_path / "_review").mkdir()
    for i in range(3):
        (tmp_path / "_review" / f"{i:016x}.json").write_text("{}")
    r1 = monitor.check(cfg, NOW)
    assert "review_queue_size" in {a["rule"] for a in r1["active"]}
    assert [t["rule"] for t in r1["transitions"] if t["state"] == "firing"].count("review_queue_size") == 1
    r2 = monitor.check(cfg, NOW)
    assert not [t for t in r2["transitions"] if t["rule"] == "review_queue_size"]  # already firing: not re-sent
    for f in (tmp_path / "_review").glob("*.json"):
        f.unlink()
    r3 = monitor.check(cfg, NOW)
    assert next(t for t in r3["transitions"] if t["rule"] == "review_queue_size")["state"] == "resolved"
    lines = (tmp_path / "alerts.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(x)["state"] for x in lines if "review_queue_size" in x] == ["firing", "resolved"]


def test_kill_switch_is_reported(tmp_path):
    cfg = cfg_at(tmp_path)
    (tmp_path / cfg.governance.kill_switch_file).write_text("on")
    assert "kill_switch" in {a["rule"] for a in monitor.check(cfg, NOW)["active"]}


def test_dead_webhook_does_not_break_monitoring(tmp_path):
    cfg = cfg_at(tmp_path, webhook_url="http://127.0.0.1:9/never", review_queue_max=0)
    (tmp_path / "_review").mkdir()
    (tmp_path / "_review" / f"{DOC}.json").write_text("{}")
    assert monitor.check(cfg, NOW)["active"]


def _res(doc_type, version="0.3", decision="auto_filed"):
    return {"doc_id": DOC, "pipeline_version": version, "decision": decision, "confidence": 0.99,
            "meta": {"company": "A Co", "fiscal_year": 2025, "period": "unknown", "doc_type": doc_type,
                     "scope": "unknown", "audited": None}}


def test_refiling_snapshots_and_rollback_restores(tmp_path):
    cfg = cfg_at(tmp_path)
    store = filing.Store(tmp_path)
    src = tmp_path / "x.pdf"
    src.write_bytes(b"%PDF-1.4\n")
    p1 = store.file_document(_res("contract", "0.2"), src, "md v1", {})
    store.set_state(DOC, status="filed", path=str(p1), pipeline_version="0.2")
    assert store.history(DOC) == []  # first filing: nothing to keep
    p2 = store.file_document(_res("invoice", "0.3"), src, "md v2", {})
    store.set_state(DOC, status="filed", path=str(p2), pipeline_version="0.3")
    h = store.history(DOC)
    assert len(h) == 1 and h[0]["pipeline_version"] == "0.2" and h[0]["folder"] == "a-co/2025/contract"

    r = pipeline.rollback(DOC, cfg, actor="tester", reason="bad release")
    assert r["restored_version"] == 1 and "kb" not in r  # redirected output never publishes
    assert (tmp_path / "filed" / "a-co" / "2025" / "contract").exists()
    assert not (tmp_path / "filed" / "a-co" / "2025" / "invoice").exists()
    assert (tmp_path / "kb_export" / f"{DOC}.md").read_text(encoding="utf-8") == "md v1"
    st = store.state(DOC)
    assert st["pipeline_version"] == "0.2" and st["rolled_back_to"] == 1
    assert len(store.history(DOC)) == 2  # the replaced version was kept: the rollback is reversible
    ev = [json.loads(x) for x in (tmp_path / "audit.jsonl").read_text(encoding="utf-8").splitlines()]
    assert ev[-1]["event"] == "rollback" and ev[-1]["actor"] == "tester"


def test_release_rollback_only_touches_bad_version(tmp_path):
    cfg = cfg_at(tmp_path)
    store = filing.Store(tmp_path)
    src = tmp_path / "x.pdf"
    src.write_bytes(b"%PDF-1.4\n")
    store.file_document(_res("contract", "0.2"), src, "v1", {})
    p = store.file_document(_res("invoice", "0.3"), src, "v2", {})
    store.set_state(DOC, status="filed", path=str(p), pipeline_version="0.3")
    store.set_state("fedcba9876543210", status="filed", path="x", pipeline_version="0.2")
    rep = pipeline.rollback_release("0.3", cfg, actor="tester")
    assert [(r["doc_id"], r["status"]) for r in rep] == [(DOC, "rolled_back")]


def test_rollback_without_history_is_refused(tmp_path):
    cfg = cfg_at(tmp_path)
    try:
        pipeline.rollback(DOC, cfg, actor="t")
    except ValueError as e:
        assert "no earlier version" in str(e)
    else:
        raise AssertionError("expected ValueError")
