"""Shape B — one ReAct agent. Student work.

Use `lab8.runtime.run_react` with max_steps=8. `decide` may pick a read tool.
It must not call `issue_refund`. After the loop, the host validates the quote
and is the only writer.

A decide() that trusts ticket text over the order row will fail hidden claims
where the customer overstates the delay or cites a superseded clause.

Per-order cap: an order may already have been refunded by an earlier claim.
The read tool `lookup_refund_history` shows how much. The host still enforces
the cap, so pass the full quote to `durability.issue_refund`, not a net amount.

Caps: stop at 8 steps. Count model calls in the Budget so cost stays comparable.

Trace contract v1 (docs/contracts.md): return a trace_path to a JSON file written in this run,
{"run_id": <same run_id>, "events": [...]}, on every return path including early
ones. `lab8.trace.Trace` does this; your own tracer is fine if it matches.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from lab8.db import connect
from lab8.durability import InjectedCrash, issue_refund
from lab8.mock_llm import complete
from lab8.runtime import run_react
from lab8.schemas import Budget, RunResult, make_run_id
from lab8.shapes.common import finish, safe_dump
from lab8.tools import get_claim_view, tool_cost
from lab8.trace import Trace


def run_claim(
    claim_id: str,
    *,
    seed: int,
    store_path: str,
    crash_at: str | None = None,
) -> RunResult:
    """Run Shape B (single ReAct agent) on a single claim."""
    conn = connect(store_path)
    try:
        return _run(conn, claim_id, seed=seed, crash_at=crash_at)
    finally:
        conn.close()


def _run(
    conn: sqlite3.Connection, claim_id: str, *, seed: int, crash_at: str | None
) -> RunResult:
    budget = Budget()
    run_id = make_run_id("single", claim_id, seed)
    trace = Trace(run_id)

    budget.add_tool(tool_cost())
    claim_view = get_claim_view(conn, claim_id)
    if not claim_view.get("found"):
        trace.add("error", {"reason": "unknown_claim"})
        return finish(
            conn,
            shape="single",
            claim_id=claim_id,
            seed=seed,
            status="failed",
            proposal_amount=0,
            budget=budget,
            trace=trace,
            error_reason="unknown_claim",
        )

    order_holder: dict[str, dict[str, Any]] = {}

    def decide(seen: dict[str, Any]) -> dict[str, Any]:
        claim = seen["claim"]
        last_tool = seen.get("last_tool")
        last_result = seen.get("last_result") or {}

        if last_tool is None:
            complete(budget, seed=seed, purpose="plan", prompt=claim.get("ticket", ""))
            if not claim.get("order_id"):
                return {
                    "final": {
                        "status": "needs_info",
                        "proposal_amount": 0,
                        "error_reason": "missing_order_id",
                    }
                }
            return {
                "tool": "lookup_order",
                "args": {
                    "order_id": claim["order_id"],
                    "principal_id": claim["principal_id"],
                },
            }

        if last_tool == "lookup_order":
            complete(
                budget,
                seed=seed,
                purpose="order_check",
                prompt=str(last_result.get("visible")),
            )
            trace.add("lookup_order", safe_dump(last_result))
            if not last_result.get("visible"):
                return {
                    "final": {
                        "status": "escalated",
                        "proposal_amount": 0,
                        "error_reason": last_result.get("reason"),
                    }
                }
            order_holder["order"] = last_result["order"]
            return {
                "tool": "lookup_refund_history",
                "args": {
                    "order_id": claim["order_id"],
                    "principal_id": claim["principal_id"],
                },
            }

        if last_tool == "lookup_refund_history":
            complete(
                budget,
                seed=seed,
                purpose="history_check",
                prompt=str(last_result.get("refunded_vnd", 0)),
            )
            trace.add("refund_history", safe_dump(last_result))
            return {
                "tool": "compute_compensation",
                "args": {"order": order_holder["order"]},
            }

        if last_tool == "compute_compensation":
            proposal = int(last_result["amount_vnd"])
            complete(budget, seed=seed, purpose="draft", prompt=f"proposal={proposal}")
            trace.add("quote", safe_dump(last_result))
            if proposal <= 0:
                return {
                    "final": {
                        "status": "denied",
                        "proposal_amount": 0,
                        "error_reason": last_result.get("reason"),
                    }
                }
            return {
                "final": {
                    "status": "ready",
                    "proposal_amount": proposal,
                    "error_reason": None,
                }
            }

        return {
            "final": {
                "status": "failed",
                "proposal_amount": 0,
                "error_reason": f"unexpected_tool:{last_tool}",
            }
        }

    react_out = run_react(
        conn,
        budget,
        observation={"claim": claim_view},
        decide=decide,
        max_steps=8,
    )
    final = react_out["final"]

    if react_out["stopped"] == "step_cap" or final["status"] in (
        "needs_info",
        "escalated",
        "denied",
        "failed",
    ):
        trace.add(
            "decision",
            {
                "status": final["status"],
                "error_reason": final.get("error_reason"),
            },
        )
        return finish(
            conn,
            shape="single",
            claim_id=claim_id,
            seed=seed,
            status=final["status"],
            proposal_amount=int(final.get("proposal_amount", 0)),
            budget=budget,
            trace=trace,
            error_reason=final.get("error_reason"),
        )

    proposal = int(final["proposal_amount"])
    try:
        outcome = issue_refund(conn, claim_id, proposal, crash_at=crash_at)
    except InjectedCrash:
        trace.add("crash", {"at": crash_at})
        trace.write()
        raise

    if not outcome["ok"]:
        status = "failed" if outcome["conflict"] else "denied"
        trace.add("decision", {"status": status, "error_reason": outcome["reason"]})
        return finish(
            conn,
            shape="single",
            claim_id=claim_id,
            seed=seed,
            status=status,
            proposal_amount=proposal,
            budget=budget,
            trace=trace,
            error_reason=outcome["reason"],
        )

    trace.add("decision", {"status": "resolved", "proposal_amount": proposal})
    return finish(
        conn,
        shape="single",
        claim_id=claim_id,
        seed=seed,
        status="resolved",
        proposal_amount=proposal,
        budget=budget,
        trace=trace,
        error_reason=None,
    )
