from app.modules.m6_parity.rules import evaluate
from decimal import Decimal
def test_real_sample_four_books(result): assert result["stages"][5]["metrics"]["balanced"] is True
def test_real_sample_final_lineage(result):
    m=result["stages"][5]["metrics"];assert m["accepted_inputs"]+m["quarantine_inputs"]+m["excluded"]==m["input"]
def test_real_sample_difference_is_explicit(result):
    rows=result["stages"][5]["rows"];assert any(r["status"]=="差异" for r in rows)
def test_real_sample_totals_exact(result):
    rows=result["stages"][5]["rows"];m=result["stages"][5]["metrics"]
    assert sum((Decimal(r["difference"]) for r in rows),Decimal(0))==Decimal(m["expected_total"])-Decimal(m["reported_total"])
def test_empty_reconcile():
    r=evaluate([],{});assert r["metrics"]["balanced"] is True and r["metrics"]["expected_total"]=="0"
def test_overlap_is_rejected():
    import pytest
    from app.errors import DomainError
    with pytest.raises(DomainError):evaluate([{"_line":1,"_records":[1]}],{"quarantine":[{"_line":1,"_records":[1]}]})
def test_real_sample_rejected_have_reason(result):
    assert all(r["reason"] and r["detail"] for r in result["stages"][5]["cumulative_quarantine"])
def test_retry_arrivals_kept_in_accepted_lineage(result):
    "重试的每次到达都在采纳侧血缘中，不被当作排除行抹掉"
    m=result["stages"][5]["metrics"]
    assert m["retry_duplicate_arrivals"]>=1
    # 排除行只含非事件物理行，重试重复到达不计入排除
    assert m["excluded"]==result["stages"][0]["metrics"]["non_event_lines"]
def test_conflict_event_never_reconciled(result):
    "冲突事件只出现在隔离，不进入任何对账结论行"
    rows=result["stages"][5]["rows"]
    assert all(r.get("doc_id")!="0102" for r in rows)
    assert any(q.get("event_id")=="0102" and q["reason"]=="EVENT_CONFLICT" for q in result["stages"][5]["cumulative_quarantine"])
def test_dual_side_same_event_id_both_landed(result):
    "同事件号两端各自挂账，独立到达记录均可追回"
    ledger=result["lineage_ledger"]
    recs={(e["event_id"],e["side"]):[a["source_record"] for a in e["arrivals"]] for e in ledger}
    assert ("0101","source") in recs and ("0101","index") in recs
    assert recs[("0101","source")]!=recs[("0101","index")]
