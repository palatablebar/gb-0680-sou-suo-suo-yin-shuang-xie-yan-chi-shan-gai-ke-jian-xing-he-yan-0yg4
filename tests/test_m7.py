from app.modules.m7_backfills.rules import evaluate
from app.errors import DomainError
from app.archive import build_archive
import pytest,csv,io
def test_real_sample_archive_ready(result): assert result["stages"][6]["metrics"]["ready"] is True
def test_real_sample_archive_source_count(result): assert result["stages"][6]["metrics"]["source_lines"]==result["stages"][5]["metrics"]["accepted_inputs"]
def test_real_sample_seal_stable(result):
    rows=result["stages"][5]["rows"];assert evaluate(rows,{})["metrics"]["sha256"]==evaluate(rows,{})["metrics"]["sha256"]
def test_unbalanced_blocked():
    with pytest.raises(DomainError) as e:evaluate([],{"reconcile":{"metrics":{"balanced":False}}})
    assert e.value.code=="UNBALANCED"
def test_duplicate_archive_key():
    with pytest.raises(DomainError):evaluate([{"doc_id":"1"},{"doc_id":"1"}],{})
def test_real_sample_manifest_has_hash(result): assert len(result["manifest"]["input_sha256"])==64
def test_real_sample_export_rows_match(result): assert result["stages"][6]["rows"]==result["stages"][5]["rows"]
def test_export_contains_full_lineage_ledger(result):
    "导出沿用同一份血缘账：每个事件身份一行，重试与冲突逐到达可追回"
    text=build_archive(result)
    rows=list(csv.reader(io.StringIO(text.lstrip("﻿"))))
    lineage=[x for x in rows[1:] if x[3].startswith("lineage")]
    assert len(lineage)==len(result["lineage_ledger"])
    states={x[3] for x in lineage}
    assert "lineage:retry_merged" in states and "lineage:conflict" in states
    # 冲突事件在导出中明确标注，不与 accepted 混同
    conflict=[x for x in lineage if x[3]=="lineage:conflict"]
    assert all("0102" in x[5] for x in conflict)
    assert not any(x[3]=="accepted" and '"doc_id": "0102"' in x[6] for x in rows[1:])
