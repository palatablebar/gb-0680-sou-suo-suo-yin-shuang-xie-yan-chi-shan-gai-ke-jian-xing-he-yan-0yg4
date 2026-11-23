import csv,io,json
def build_archive(run):
    stream=io.StringIO(newline="");writer=csv.writer(stream)
    writer.writerow(["run_id","input_sha256","rule_version","kind","source_lines","reason","evidence"])
    meta=run["manifest"]
    for row in run["stages"][-1]["rows"]:
        writer.writerow([run["run_id"],meta["input_sha256"],meta["rule_version"],"accepted",json.dumps(row.get("_sources",[])),row.get("status",""),json.dumps(row,ensure_ascii=False)])
    for row in run["stages"][-1].get("cumulative_quarantine",[]):
        writer.writerow([run["run_id"],meta["input_sha256"],meta["rule_version"],"quarantine",json.dumps(row.get("_sources",[])),row.get("reason",""),json.dumps(row,ensure_ascii=False)])
    # 事件血缘账：每个事件身份一行，逐到达留痕，页面与导出共用同一份可追回账本
    for entry in run.get("lineage_ledger",[]):
        writer.writerow([run["run_id"],meta["input_sha256"],meta["rule_version"],"lineage:"+entry["state"],
                         json.dumps([a["source_line"] for a in entry["arrivals"]]),
                         entry["event_id"]+"@"+entry["side"],
                         json.dumps(entry,ensure_ascii=False)])
    return "\ufeff"+stream.getvalue()
