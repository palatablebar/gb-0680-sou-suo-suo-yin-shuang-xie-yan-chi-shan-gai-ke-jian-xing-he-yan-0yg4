# 双写定义

事件身份=(event_id, side)。event_id在同一数据端内标识一次业务事件；同一event_id分别出现在source与index时是两条独立到达，各自挂账、禁止跨端合并抹痕。doc_id文本保留。side为source或index；版本正整数按Decimal比较并作为文本序列化。upsert要求JSON对象，delete忽略payload并产生墓碑。

重试裁决（m1 双端采信）：按(event_id, side)归集全部到达。除note外业务字段指纹完全相同的多次到达判定为生产方重试，合并为一条规范事件，retry_count=额外到达次数；每次到达的物理行号、逻辑记录号、source_time、visible_time、note逐笔写入event_ledger，重试不新增结论、不放大证据。若同身份多次到达的业务指纹不一致，整组隔离为EVENT_CONFLICT，禁止回落旧值、禁止该事件冒充已对平。note仅为批注，不参与指纹。

相同文档同端同版本不同内容全部隔离，存在未裁决冲突的主体不回落旧版本；同内容合并来源；较高版本覆盖低版本，迟到旧写不得覆盖墓碑。

双端最终版本、操作、文档分别核验。目标缺失、删除未确认、索引领先、陈旧索引、内容差异分开展示。source_time与visible_time带偏移；可见延迟按实际秒数。默认阈值120秒，等于阈值通过。已可见但超过阈值为延迟，尚无目标且等待时间超过阈值为缺失，等待中不冒充延迟。

对账expected=每文档应通过的1，reported=门禁通过1或未通过0，逐条保存visibility_state和gate原因，允许按文档复核。

业务ID和超大整数按文本保形；Decimal参与数量金额计算，对外序列化为字符串。哨兵集合定义在app/values.py，缺失值不能当零。所有时间带UTC偏移，先转UTC比较，业务日按指定地区划分。区间统一[start,end)。重复业务键的同内容重试合并到同一事件身份并逐笔留痕、不新增结论；指纹冲突行整组隔离且保留原值。空文件、全空白、仅表头分开拒绝。

血缘守恒以CSV逻辑记录（_record，按解析器记录序号；引号内换行不增加记录数）为单位：输入逻辑记录=采纳血缘记录+隔离记录+非事件物理行（空行+分段表头）。同内容重试的后续到达不是被丢弃的排除行，而是同一事件的可追回到达，保留在采纳侧_records与event_ledger中；duplicate仅作信息性计数（retry_duplicate_arrivals），不参与守恒扣减。物理行号_line/_sources保留用于现场追溯，带引号换行时物理行号与逻辑记录号可不连续。

event_ledger为事件血缘账，按(event_id, side)每身份一条，含state(single/retry_merged/conflict)、arrival_count、canonical_line与arrivals（逐到达的source_line/source_record/source_time/visible_time/note）。该账本随run载荷持久化，页面m1/m6面板与证据CSV导出（kind=lineage:<state>）共用同一份，确保重试不新增结论、两端独立到达不被误删、冲突事件不冒充对平。

运行清单包括输入sha256、规则版本、参数、生成时刻与耗时。源行同时保留CSV物理结束行号（_line，引号内换行不增加记录数）与逻辑记录号（_record）。输入超过4MB返回413，非法表头和类型返回422，失效版本复核返回409。