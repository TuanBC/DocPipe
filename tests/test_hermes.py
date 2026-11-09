"""Offline tests for the Agent tab's Hermes bridge (docpipe/hermes.py): no Hermes install, model or server needed.
The Hermes process is replaced by a fake that prints the same stream-json lines Hermes v0.22 emits."""
import io
import json

from docpipe import hermes

URI = "viking://resources/docpipe/xay-dung-hung-thinh/2025/contract/contract__unknown__d142d56ca0880477/d142d56ca0880477.md"
LINES = [
    {"type": "system", "subtype": "init", "model": "luna", "session_id": "s1"},
    {"type": "tool_use", "name": "mcp__openviking__find", "input": {"query": "Hưng Thịnh", "target_uri": "viking://resources/docpipe"}},
    {"type": "tool_result", "name": "mcp__openviking__find", "output": "x" * 2000},
    {"type": "text", "text": "Số tiền vay "},
    {"type": "text", "text": "12.500.000.000 đồng."},
    {"type": "result", "session_id": "s1", "exit_code": 0, "text": f"Số tiền vay **12.500.000.000 đồng** [{URI}]."},
]


class FakeProc:
    def __init__(self, lines, code=0):
        self.stdout = io.StringIO("banner noise\n" + "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in lines))
        self.code = code

    def wait(self, timeout=None):
        return self.code

    def poll(self):
        return self.code

    def kill(self):
        pass


def setup(monkeypatch, lines=LINES, code=0):
    seen = {}

    def popen(cmd, **kw):
        seen["cmd"], seen["env"] = cmd, kw.get("env", {})
        return FakeProc(lines, code)
    monkeypatch.setattr(hermes, "executable", lambda: "hermes")
    monkeypatch.setattr(hermes, "ensure_profile", lambda: None)
    monkeypatch.setattr(hermes.subprocess, "Popen", popen)
    return seen


def test_stream_events_answer_and_audit(tmp_path, monkeypatch):
    seen = setup(monkeypatch)
    evs = list(hermes.ask("Số tiền vay?", "viking://resources/docpipe", tmp_path))
    kinds = [e["type"] for e in evs]
    assert kinds == ["start", "tool", "tool_result", "text", "text", "done"]
    done = evs[-1]
    assert done["uris"] == [URI]                       # trailing "]." stripped
    assert done["tools"] == ["mcp__openviking__find"]
    assert len(evs[2]["output"]) < 800                 # long tool output truncated for the UI
    # isolated run: own profile, only the OpenViking toolset, no user rules, never a redirected HERMES_HOME
    cmd = seen["cmd"]
    assert cmd[cmd.index("-p") + 1] == hermes.PROFILE and cmd[cmd.index("-t") + 1] == "openviking"
    assert "--ignore-rules" in cmd and "HERMES_HOME" not in seen["env"]
    rec = json.loads((tmp_path / "audit.jsonl").read_text(encoding="utf-8").strip().splitlines()[-1])
    assert rec["event"] == "agent_ask" and rec["uris"] == [URI] and rec["exit_code"] == 0 and rec["error"] is None


def test_failed_run_reports_error_and_releases_lock(tmp_path, monkeypatch):
    setup(monkeypatch, lines=[{"type": "system", "session_id": "s2"}], code=1)
    evs = list(hermes.ask("q", "viking://resources/docpipe", tmp_path))
    assert evs[-1]["type"] == "error" and "code 1" in evs[-1]["message"]
    assert hermes._RUN_LOCK.acquire(blocking=False)    # the lock was released
    hermes._RUN_LOCK.release()


def test_one_run_at_a_time(tmp_path, monkeypatch):
    setup(monkeypatch)
    assert hermes._RUN_LOCK.acquire(blocking=False)
    try:
        evs = list(hermes.ask("q", "viking://resources/docpipe", tmp_path))
        assert evs == [{"type": "error", "message": "the agent is already answering another question; try again in a moment"}]
    finally:
        hermes._RUN_LOCK.release()


def test_empty_question_rejected(tmp_path):
    assert list(hermes.ask("  ", "viking://resources/docpipe", tmp_path))[0]["type"] == "error"


def test_profile_config_is_read_only():
    text = hermes.CONFIG_SRC.read_text(encoding="utf-8")
    include = text.split("include:")[1].splitlines()[0]
    for tool in ("write", "edit", "forget", "add_resource", "add_skill", "set_acl", "privacy", "remember"):
        assert tool not in include
    assert "1933/mcp" in text and "4010/v1" in text
