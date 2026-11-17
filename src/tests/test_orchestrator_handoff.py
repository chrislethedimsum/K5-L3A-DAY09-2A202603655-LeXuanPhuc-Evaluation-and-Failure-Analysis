"""Orchestrator + handoff: trace boundary, read-only workers, crash flush."""

import json
from pathlib import Path

import pytest

from lab8.durability import InjectedCrash
from lab8.handoff import HandoffError, make_handoff
from lab8.shapes.orchestrator import run_claim
from tests.conftest import CLAIMS

FORBIDDEN = ("CANARY_SECRET_", "parent_secret", "raw_headers", "Authorization")


def _trace_text(result) -> str:
    return Path(result.trace_path).read_text(encoding="utf-8")


def test_make_handoff_drops_non_fact_keys_and_write_tools():
    handoff = make_handoff(
        request_id="REQ-X",
        claim_id="C-001",
        task="t",
        facts={"delay_days": 4, "parent_secret": "CANARY_SECRET_X", "phone": "0900000000"},
        allowed_tools=["lookup_order"],
    )
    assert handoff["facts"] == {"delay_days": 4}
    for tool in ("issue_refund", "append_audit"):
        with pytest.raises(HandoffError):
            make_handoff(request_id="R", claim_id="C", task="t", facts={}, allowed_tools=[tool])


def test_every_public_claim_trace_is_clean_and_valid(public_db):
    for row in CLAIMS:
        result = run_claim(row["claim_id"], seed=11, store_path=str(public_db))
        text = _trace_text(result)
        data = json.loads(text)
        assert data["run_id"] == result.run_id
        assert isinstance(data["events"], list)
        assert not any(token in text for token in FORBIDDEN), row["claim_id"]
        assert "CANARY_SECRET_" not in repr(result)


def test_trace_records_sanitized_handoff_with_read_only_tools(public_db):
    result = run_claim("C-001", seed=11, store_path=str(public_db))
    data = json.loads(_trace_text(result))
    handoffs = [e for e in data["events"] if e.get("kind") == "handoff"]
    assert handoffs, "trace must record the handoff"
    payload = json.dumps(handoffs[0])
    assert "issue_refund" not in payload
    assert "append_audit" not in payload


def test_unknown_claim_still_writes_trace(public_db):
    result = run_claim("C-NOPE", seed=11, store_path=str(public_db))
    assert result.status == "failed"
    assert result.refund_effects == []
    assert json.loads(_trace_text(result))["run_id"] == result.run_id


def test_rerun_same_claim_keeps_single_refund(public_db):
    first = run_claim("C-001", seed=11, store_path=str(public_db))
    second = run_claim("C-001", seed=22, store_path=str(public_db))
    assert first.status == second.status == "resolved"
    assert len(second.refund_effects) == 1
    assert second.committed_audit_count == 1


def test_crash_propagates_and_flushes_trace_then_resume_is_single(public_db, monkeypatch):
    from lab8 import trace as trace_mod

    written = []
    original = trace_mod.Trace.write

    def spy(self):
        path = original(self)
        written.append(path)
        return path

    monkeypatch.setattr(trace_mod.Trace, "write", spy)
    with pytest.raises(InjectedCrash):
        run_claim("C-001", seed=11, store_path=str(public_db), crash_at="after_effect_before_checkpoint")
    assert written, "trace must be flushed before the crash propagates"
    resumed = run_claim("C-001", seed=11, store_path=str(public_db))
    assert resumed.status == "resolved"
    assert len(resumed.refund_effects) == 1
    assert resumed.committed_audit_count == 1
