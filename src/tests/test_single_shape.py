"""Unit tests for Shape B (single ReAct agent)."""

from __future__ import annotations

import json

import pytest

from lab8.db import init_store
from lab8.durability import InjectedCrash
from lab8.shapes.single import run_claim
from tests.conftest import CLAIMS, WORLD


def _make_store(tmp_path, name: str) -> str:
    path = tmp_path / name
    init_store(path, WORLD, CLAIMS).close()
    return str(path)


def test_single_ignores_ticket_delay_at_seed_55(tmp_path):
    """C-002 ticket claims 5 days late, but order row has 2 days; single must deny."""
    store = _make_store(tmp_path, "single-c002.sqlite")
    result = run_claim("C-002", seed=55, store_path=store)

    assert result.shape == "single"
    assert result.status == "denied"
    assert result.proposal_amount == 0
    assert result.refund_effects == []
    assert result.committed_audit_count == 0
    assert result.model_calls > 0
    assert result.tool_calls > 0

    with open(result.trace_path, encoding="utf-8") as f:
        trace = json.load(f)
    assert trace["run_id"] == result.run_id
    assert isinstance(trace["events"], list)


def test_single_crash_and_resume_is_idempotent(tmp_path):
    """Crash after ledger write must still leave exactly one refund after resume."""
    store = _make_store(tmp_path, "single-crash.sqlite")

    with pytest.raises(InjectedCrash):
        run_claim(
            "C-001",
            seed=11,
            store_path=store,
            crash_at="after_effect_before_checkpoint",
        )

    resumed = run_claim("C-001", seed=11, store_path=store)
    assert resumed.status == "resolved"
    assert len(resumed.refund_effects) == 1
    assert resumed.committed_audit_count == 1
