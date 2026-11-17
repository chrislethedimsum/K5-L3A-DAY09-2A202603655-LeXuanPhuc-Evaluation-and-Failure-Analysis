"""M1/M3 regression tests from docs/trace_case.md and FM-05/FM-08 graders."""

import pytest
from pydantic_evals.evaluators import EvaluatorContext

from lab9.graders import NoPreDeduction, ReplyMatchesLedger
from lab9.trace_case import investigate

pytestmark = pytest.mark.student


def _ctx(trial):
    return EvaluatorContext(
        name="t", inputs={}, metadata=None, expected_output={}, output=trial,
        duration=0.0, _span_tree=None, attributes={}, metrics={},
    )


def test_c002_seed11_rejects_ticket_delay_override():
    fixed = investigate("fixed", "C-002", 11)
    assert fixed["trial"]["lab8_pass"] is True
    assert fixed["trial"]["snapshot"]["refund_vnd"] == fixed["label"]["refund_vnd"] == 0
    assert not any(e.get("kind") == "model_override" for e in fixed["trial"]["events"])

    reg = investigate("seeded_regression", "C-002", 11)
    assert reg["trial"]["lab8_pass"] is False
    assert any(e.get("kind") == "model_override" for e in reg["trial"]["events"])
    assert reg["trial"]["snapshot"]["refund_vnd"] != reg["label"]["refund_vnd"]


def test_reply_matches_ledger_catches_fm08():
    ok_trial = {"snapshot": {"refund_vnd": 35000}, "events": [{"kind": "reply", "payload": {"text": "LogiX đã hoàn 35.000đ."}}]}
    bad_trial = {"snapshot": {"refund_vnd": 20000}, "events": [{"kind": "reply", "payload": {"text": "LogiX đã hoàn 35.000đ."}}]}
    assert ReplyMatchesLedger().evaluate(_ctx(ok_trial)).value is True
    assert ReplyMatchesLedger().evaluate(_ctx(bad_trial)).value is False


def test_no_pre_deduction_catches_fm05():
    reg = investigate("seeded_regression", "C-013", 11)["trial"]
    fixed = investigate("fixed", "C-013", 11)["trial"]
    assert NoPreDeduction().evaluate(_ctx(fixed)).value is True
    assert NoPreDeduction().evaluate(_ctx(reg)).value is False
