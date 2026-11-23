import pytest,csv,io
from app.pipeline import load_sample
from app.modules.m1_streams.rules import evaluate,decode
from app.config import COLUMNS
from app.errors import DomainError
def test_bom_real_sample(sample):
    "TRAP-02"
    r=evaluate(sample);assert r["metrics"]["encoding"]=="utf-8-sig" and r["rows"][0][COLUMNS[0]].startswith("00")
def test_legacy_encoding_real_sample():
    "TRAP-01"
    r=evaluate(load_sample("legacy.csv"));assert r["metrics"]["encoding"]=="gb18030" and r["metrics"]["accepted"]>=30
def test_bad_columns_real_sample(sample):
    "TRAP-05"
    assert any(r["reason"]=="BAD_COLUMNS" for r in evaluate(sample)["quarantine"])
def test_duplicate_conflict_real_sample(sample):
    "TRAP-14 同事件身份重试内容不一致整组隔离"
    q=evaluate(sample)["quarantine"]
    assert any(r["reason"]=="EVENT_CONFLICT" for r in q)
    assert all(r["event_id"]=="0102" for r in q if r["reason"]=="EVENT_CONFLICT")
def test_identifier_preserved_real_sample(sample):
    "TRAP-08"
    r=evaluate(sample)["rows"][0];assert r[COLUMNS[0]].startswith("00")
def test_three_empty_states():
    "TRAP-18"
    for raw,code in [(b"","EMPTY_FILE"),(b"\n\r\n","BLANK_ONLY"),((",".join(COLUMNS)+"\n").encode(),"HEADER_ONLY")]:
        with pytest.raises(DomainError) as e:evaluate(raw)
        assert e.value.code==code
def test_intake_conservation_real_sample(sample):
    r=evaluate(sample);m=r["metrics"]
    # 每条逻辑记录归入事件血缘或被隔离；仅空行/分段表头为非事件行
    assert m["lineage_balanced"] is True
    assert m["input"]==m["accepted_records"]+m["rejected_records"]+m["non_event_lines"]
def test_retry_does_not_add_conclusion(sample):
    "同内容重试合并为一条规范事件，每次到达均留痕"
    r=evaluate(sample)
    e100=next(e for e in r["metrics"]["event_ledger"] if e["event_id"]=="0100" and e["side"]=="source")
    assert e100["state"]=="retry_merged" and e100["arrival_count"]==2
    row=next(x for x in r["rows"] if x["event_id"]=="0100" and x["side"]=="source")
    assert row["retry_count"]==1 and len(row["_records"])==2
    assert [a["source_record"] for a in e100["arrivals"]]==row["_records"]
def test_same_event_id_two_sides_kept_apart(sample):
    "同一事件号分属两端是两条独立到达，禁止跨端合并抹痕"
    ledger=evaluate(sample)["metrics"]["event_ledger"]
    pair=[e for e in ledger if e["event_id"]=="0101"]
    assert {e["side"] for e in pair}=={"source","index"} and len(pair)==2
    assert all(e["state"]=="single" for e in pair)
def test_conflicting_retry_quarantined_not_reconciled(sample):
    "重试内容冲突整组隔离，事件不得冒充已对平"
    r=evaluate(sample)
    bad=[q for q in r["quarantine"] if q["reason"]=="EVENT_CONFLICT"]
    assert {q["event_id"] for q in bad}=={"0102"} and len(bad)==2
    assert not any(x.get("event_id")=="0102" for x in r["rows"])
def test_retry_lineage_is_order_independent():
    head=",".join(COLUMNS)+"\n"
    base='0100,d1,1,upsert,2026-11-16T10:00:00Z,-,source,"{""n"":1}",1,x\n'
    again='0100,d1,1,upsert,2026-11-16T10:00:00Z,-,source,"{""n"":1}",1,y\n'
    a=evaluate((head+base+again).encode());b=evaluate((head+again+base).encode())
    assert a["rows"][0]["_records"]==b["rows"][0]["_records"]
    assert a["metrics"]["retry_events"]==b["metrics"]["retry_events"]==1
def test_quoted_newline_is_one_record(sample):
    "TRAP-03"
    r=evaluate(sample);assert any("\n" in str(x) for row in r["rows"] for x in row.values())
