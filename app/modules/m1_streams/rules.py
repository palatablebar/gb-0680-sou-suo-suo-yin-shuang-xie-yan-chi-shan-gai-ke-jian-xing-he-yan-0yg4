import csv,io
from collections import defaultdict
from app.config import COLUMNS
from app.errors import DomainError
from app.reasons import reject
# 事件身份=事件号+数据端；同一事件号在 source/index 是两条独立到达，禁止跨端合并
# note 仅为批注，不参与重试指纹（批注变化不构成冲突）
FINGERPRINT_COLUMNS=[c for c in COLUMNS if c!="note"]
def fingerprint(row):
    return tuple(row.get(c,"") for c in FINGERPRINT_COLUMNS)
def evaluate(raw,context=None):
    text,encoding=decode(raw)
    if not text: raise DomainError("EMPTY_FILE","文件为空")
    if not text.strip(): raise DomainError("BLANK_ONLY","全部为空行")
    stream=csv.reader(io.StringIO(text,newline=""));header=next(stream,None)
    if header!=COLUMNS: raise DomainError("BAD_HEADER","表头不匹配")
    physical=[];bad=[];blank=repeated=count=0
    try:
        for cells in stream:
            count+=1;line=stream.line_num;record=count
            if not cells or not any(c.strip() for c in cells): blank+=1;continue
            if cells==header: repeated+=1;continue
            row={"_line":line,"_record":record,"_sources":[line],"_raw":cells}
            if len(cells)!=len(header): bad.append(reject(row,"BAD_COLUMNS","列数不匹配"));continue
            row.update(dict(zip(header,[x.strip() for x in cells])))
            if not row[header[0]]: bad.append(reject(row,"EMPTY_VALUE","业务键为空"));continue
            physical.append(row)
    except csv.Error: raise DomainError("BAD_CSV","引号未闭合或文件损坏")
    if count==0: raise DomainError("HEADER_ONLY","仅有表头")
    # 按事件身份(event_id,side)挂账：重试归并、内容冲突隔离，两端同事件号各自独立
    grouped=defaultdict(list)
    for row in physical: grouped[(row["event_id"],row["side"])].append(row)
    rows=[];duplicate=0;retried=0;event_conflicts=0;ledger=[]
    for (event_id,side),arrivals in sorted(grouped.items()):
        entry={"event_id":event_id,"side":side,"arrival_count":len(arrivals),"arrivals":[]}
        for a in arrivals:
            entry["arrivals"].append({"source_line":a["_line"],"source_record":a["_record"],"source_time":a.get("source_time",""),"visible_time":a.get("visible_time",""),"note":a.get("note","")})
        signatures={fingerprint(a) for a in arrivals}
        if len(signatures)>1:
            # 同身份重试但业务内容不一致：整组隔离，禁止回落旧值、禁止冒充对平
            event_conflicts+=1;entry["state"]="conflict"
            for a in arrivals: bad.append(reject(a,"EVENT_CONFLICT","同一事件号同端重试内容不一致，禁止冒充对平"))
            ledger.append(entry);continue
        canonical=arrivals[0]
        entry["state"]="retry_merged" if len(arrivals)>1 else "single"
        entry["canonical_line"]=canonical["_line"]
        ledger.append(entry)
        if len(arrivals)>1:
            # 完全相同的重试到达：不新增结论，仅记账；除首条外计重复行
            retried+=1;duplicate+=len(arrivals)-1
        rows.append({**canonical,"_sources":[n for a in arrivals for n in a["_sources"]],"_records":[a["_record"] for a in arrivals],"retry_count":len(arrivals)-1})
    if not rows and not bad: raise DomainError("BLANK_ONLY","全部为空行")
    accepted_records=set(n for row in rows for n in row["_records"])
    rejected_records=set(n for row in bad for n in (row.get("_records") or [row["_record"]]))
    # 守恒：每条逻辑记录要么归入某事件血缘（含同内容重试的每次到达），要么被隔离；
    # 仅空行与分段表头属于非事件物理行。重试重复到达不丢弃，计入采纳侧血缘而非排除。
    non_events=blank+repeated
    metrics={"input":count,"accepted":len(rows),"quarantine":len(bad),"duplicate":duplicate,"blank":blank,"repeated_headers":repeated,"encoding":encoding,"retry_events":retried,"event_conflict_events":event_conflicts,"distinct_event_arrivals":len(physical),"accepted_records":len(accepted_records),"rejected_records":len(rejected_records),"non_event_lines":non_events,"lineage_balanced":count==len(accepted_records)+len(rejected_records)+non_events,"event_ledger":ledger}
    return {"rows":rows,"quarantine":bad,"metrics":metrics}
def decode(raw):
    for encoding in ("utf-8-sig","gb18030"):
        try: return raw.decode(encoding),encoding
        except UnicodeDecodeError: continue
    raise DomainError("ENCODING","无法识别文件编码")
