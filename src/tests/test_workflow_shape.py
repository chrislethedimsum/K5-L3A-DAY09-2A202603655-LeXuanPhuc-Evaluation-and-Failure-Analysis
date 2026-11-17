"""Focused tests for the deterministic workflow shape."""

from __future__ import annotations


def test_workflow_passes_full_quote_to_host(public_db, monkeypatch):
    import lab8.shapes.workflow as workflow
    from lab8.durability import issue_refund as real_issue_refund

    captured = {}

    def spy(conn, claim_id, proposed_vnd, *, crash_at=None):
        captured.update(
            claim_id=claim_id,
            proposed_vnd=proposed_vnd,
            crash_at=crash_at,
        )
        return real_issue_refund(
            conn,
            claim_id,
            proposed_vnd,
            crash_at=crash_at,
        )

    monkeypatch.setattr(workflow, "issue_refund", spy)

    result = workflow.run_claim(
        "C-014",
        seed=11,
        store_path=str(public_db),
    )

    assert result.status == "resolved"
    assert captured == {
        "claim_id": "C-014",
        "proposed_vnd": 150000,
        "crash_at": None,
    }
    assert result.refund_effects[0]["amount_vnd"] == 120000
