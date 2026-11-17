"""Các trường hợp biên của ledger/policy mà các test có sẵn chưa phủ.

Mỗi test dùng một SQLite mới (fixture public_db) nên không ảnh hưởng nhau.
"""

from lab8.db import connect
from lab8.durability import committed_audit_count, get_refund, issue_refund


def _add_claim(conn, claim_id, order_id, approval_id, *, principal="P-100"):
    conn.execute(
        """
        INSERT INTO claims (claim_id, principal_id, order_id, ticket, parent_secret, raw_headers_json, approval_id)
        VALUES (?, ?, ?, 'test', 'CANARY_SECRET_PARENT_EDGE', '{}', ?)
        """,
        (claim_id, principal, order_id, approval_id),
    )


def _add_approval(conn, approval_id, claim_id, amount):
    conn.execute(
        "INSERT INTO approvals (approval_id, claim_id, approved_vnd, status, expires_at) "
        "VALUES (?, ?, ?, 'valid', '2027-12-31')",
        (approval_id, claim_id, amount),
    )


def _denied_reasons(conn, claim_id):
    rows = conn.execute(
        "SELECT details_json FROM audit_events WHERE claim_id = ? AND event_type = 'policy_denied'",
        (claim_id,),
    ).fetchall()
    return " ".join(row["details_json"] for row in rows)


def _ledger_rows(conn, claim_id):
    return conn.execute(
        "SELECT COUNT(*) AS n FROM refund_ledger WHERE claim_id = ?", (claim_id,)
    ).fetchone()["n"]


def test_unknown_claim_writes_nothing(public_db):
    conn = connect(public_db)
    outcome = issue_refund(conn, "C-KHONG-TON-TAI", 35000)
    total = conn.execute("SELECT COUNT(*) AS n FROM refund_ledger").fetchone()["n"]
    conn.close()
    assert outcome == {"ok": False, "reason": "unknown_claim", "effect": None, "conflict": False}
    assert total == 2  # chỉ còn 2 dòng hoàn trước đó đã seed (O-505, O-515)


def test_claim_without_order_id_is_denied_with_audit(public_db):
    conn = connect(public_db)
    outcome = issue_refund(conn, "C-004", 35000)  # C-004 thiếu order_id
    rows = _ledger_rows(conn, "C-004")
    reasons = _denied_reasons(conn, "C-004")
    conn.close()
    assert outcome["reason"] == "missing_order"
    assert rows == 0
    assert "missing_order" in reasons


def test_order_of_another_principal_is_blocked(public_db):
    conn = connect(public_db)
    outcome = issue_refund(conn, "C-005", 40000)  # P-200 đòi đơn O-110 của P-300
    rows = _ledger_rows(conn, "C-005")
    reasons = _denied_reasons(conn, "C-005")
    conn.close()
    assert outcome["reason"] == "outside_principal_scope"
    assert rows == 0
    assert "outside_principal_scope" in reasons


def test_zero_amount_approval_is_rejected(public_db):
    conn = connect(public_db)
    _add_approval(conn, "A-ZERO", "C-ZERO", 0)
    _add_claim(conn, "C-ZERO", "O-909", "A-ZERO")
    conn.commit()
    outcome = issue_refund(conn, "C-ZERO", 35000)
    rows = _ledger_rows(conn, "C-ZERO")
    reasons = _denied_reasons(conn, "C-ZERO")
    conn.close()
    assert outcome["reason"] == "non_positive_amount"
    assert rows == 0
    assert "non_positive_amount" in reasons


def test_zero_proposed_amount_is_rejected_even_with_valid_approval(public_db):
    conn = connect(public_db)
    outcome = issue_refund(conn, "C-001", 0)  # approval A-001 hợp lệ, nhưng quote = 0
    rows = _ledger_rows(conn, "C-001")
    conn.close()
    assert outcome["reason"] == "non_positive_amount"
    assert rows == 0


def test_approval_id_pointing_to_nothing_is_missing_approval(public_db):
    conn = connect(public_db)
    _add_claim(conn, "C-GHOST", "O-909", "A-KHONG-CO")
    conn.commit()
    outcome = issue_refund(conn, "C-GHOST", 35000)
    rows = _ledger_rows(conn, "C-GHOST")
    reasons = _denied_reasons(conn, "C-GHOST")
    conn.close()
    assert outcome["reason"] == "missing_approval"
    assert rows == 0
    assert "missing_approval" in reasons


def test_refund_is_capped_at_what_the_customer_paid(public_db):
    """C-009 có approval 500.000 nhưng đơn O-404 chỉ trả 90.000: host phải cắt về 90.000."""
    conn = connect(public_db)
    outcome = issue_refund(conn, "C-009", 200000)
    effect = get_refund(conn, "C-009")
    audits = committed_audit_count(conn, "C-009")
    conn.close()
    assert outcome["ok"] is True
    assert int(effect["amount_vnd"]) == 90000
    assert audits == 1
