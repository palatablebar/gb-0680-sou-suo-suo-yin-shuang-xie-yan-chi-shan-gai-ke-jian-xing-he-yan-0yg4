from decimal import Decimal
from app.reasons import sources,records
from app.errors import DomainError
def evaluate(rows,context):
    bad=context.get("quarantine",[])
    # 守恒单位=CSV逻辑记录：同内容重试的每次到达都保留在事件血缘中，不丢弃、不新增结论
    accepted=set(x for row in rows for x in records(row))
    rejected=set(x for row in bad for x in records(row))
    if accepted & rejected: raise DomainError("LINEAGE_OVERLAP","同一来源记录被重复裁决")
    intake=context.get("intake") or {}
    # 仅空行与分段表头属于非事件物理行；重复重试到达计入采纳侧血缘
    excluded=intake.get("blank",0)+intake.get("repeated_headers",0)
    records_seen=len(accepted)+len(rejected)+excluded
    m={"accepted_inputs":len(accepted),"quarantine_inputs":len(rejected),"output_records":len(rows),
       "excluded":excluded,"retry_duplicate_arrivals":intake.get("duplicate",0),
       "physical_source_lines":len(set(x for row in rows for x in sources(row)) |
                                    set(x for row in bad for x in sources(row)))}
    if intake:
        # 输入逻辑记录=采纳血缘记录+隔离记录+非事件行；重试合并不破坏守恒
        m.update(input=intake["input"],balanced=intake["input"]==records_seen)
    else:
        m.update(input=records_seen,balanced=True)
    output=[]
    for row in rows:
        expected=Decimal(str(row.get("expected","0")));reported=Decimal(str(row.get("reported","0")))
        output.append({**row,"difference":str(expected-reported),"status":"通过" if expected==reported else "差异"})
    m.update(expected_total=str(sum((Decimal(str(r.get("expected","0"))) for r in output),Decimal(0))),
             reported_total=str(sum((Decimal(str(r.get("reported","0"))) for r in output),Decimal(0))),
             differences=sum(r["status"]=="差异" for r in output))
    return {"rows":output,"quarantine":[],"metrics":m}
