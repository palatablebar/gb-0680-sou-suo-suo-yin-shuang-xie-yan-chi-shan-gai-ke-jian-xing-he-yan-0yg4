# 深度登记 搜索索引双写延迟与删改可见性核验

规模：中型。使用者：搜索数据同步值班工程师。核心规则：按源版本重建目标可见状态，删除墓碑拦截迟到旧写入；延迟与缺失分开定责。

## 功能模块

| 模块 | 使用者动作 | 入口 | 核心文件 | 测试 |
|---|---|---|---|---|
| M1 双端采信 | 查看并运行双端采信 | `/api/streams` | `app/modules/m1_streams/rules.py` | `tests/test_m1.py` |
| M2 字段契约 | 查看并运行字段契约 | `/api/schema` | `app/modules/m2_schema/rules.py` | `tests/test_m2.py` |
| M3 版本裁决 | 查看并运行版本裁决 | `/api/versions` | `app/modules/m3_versions/rules.py` | `tests/test_m3.py` |
| M4 可见性重建 | 查看并运行可见性重建 | `/api/visibility` | `app/modules/m4_visibility/rules.py` | `tests/test_m4.py` |
| M5 延迟闸门 | 查看并运行延迟闸门 | `/api/latency` | `app/modules/m5_latency/rules.py` | `tests/test_m5.py` |
| M6 双写对账 | 查看并运行双写对账 | `/api/parity` | `app/modules/m6_parity/rules.py` | `tests/test_m6.py` |
| M7 回补归档 | 查看并运行回补归档 | `/api/backfills` | `app/modules/m7_backfills/rules.py` | `tests/test_m7.py` |

## 陷阱登记

| TRAP | 现象 | 朴素实现 | 本项目处理 | 处理位置 | 测试 |
|---|---|---|---|---|---|
| TRAP-01 | 旧编码 | 默认解码失败 | 回退GB18030 | `app/modules/m1_streams/rules.py` | `tests/test_m1.py::test_legacy_encoding_real_sample` |
| TRAP-02 | BOM | 首列名多字符 | utf-8-sig | `app/modules/m1_streams/rules.py` | `tests/test_m1.py::test_bom_real_sample` |
| TRAP-03 | 带引号换行 | 拆成两条 | csv逻辑行 | `app/modules/m1_streams/rules.py` | `tests/test_m1.py::test_quoted_newline_is_one_record` |
| TRAP-05 | 列数不匹配 | 静默错列 | 隔离原行 | `app/modules/m1_streams/rules.py` | `tests/test_m1.py::test_bad_columns_real_sample` |
| TRAP-08 | 前导零ID | 编码变形 | 全程字符串 | `app/modules/m1_streams/rules.py` | `tests/test_m1.py::test_identifier_preserved_real_sample` |
| TRAP-14 | 重复键冲突 | 后写覆盖 | 同事件身份重试指纹冲突整组隔离EVENT_CONFLICT，不回落旧值 | `app/modules/m1_streams/rules.py` | `tests/test_m1.py::test_duplicate_conflict_real_sample` |
| TRAP-27 | 生产方重试 | 按事件号直接合并抹掉独立到达，或全量保留放大结论 | (event_id,side)归并：同指纹重试合一条规范事件并逐笔挂账，retry_count记账不新增结论 | `app/modules/m1_streams/rules.py` | `tests/test_m1.py::test_retry_does_not_add_conclusion` |
| TRAP-28 | 同事件号跨两端 | 裸event_id去重误删一端到达 | 身份含side，source/index同号各自独立挂账，两次到达均保留 | `app/modules/m1_streams/rules.py` | `tests/test_m1.py::test_same_event_id_two_sides_kept_apart` |
| TRAP-29 | 冲突重试冒充对平 | 取首条或最新条静默对平 | 指纹不一致整组EVENT_CONFLICT隔离，不进入任何对账结论行 | `app/modules/m1_streams/rules.py` | `tests/test_m6.py::test_conflict_event_never_reconciled` |
| TRAP-30 | 引号换行破坏守恒 | 用物理行号计数导致输入对不平 | 以逻辑记录_record守恒，物理行号仅作证据；重试到达计入采纳血缘而非排除 | `app/modules/m6_parity/rules.py` | `tests/test_m1.py::test_intake_conservation_real_sample` |
| TRAP-18 | 空态三态 | 一律成功 | 分别错误码 | `app/modules/m1_streams/rules.py` | `tests/test_m1.py::test_three_empty_states` |
| TRAP-26 | 旧版本提交 | 覆盖新结果 | 版本条件更新 | `app/store.py` | `tests/test_e2e.py::test_stale_review_409` |
| TRAP-06 | 全角版本 | 解析失败 | Decimal归一 | `app/values.py` | `tests/test_m2.py::test_fullwidth_version` |
| TRAP-07 | 缺版本 | 当零处理 | 空值隔离 | `app/values.py` | `tests/test_m2.py::test_real_sentinel_isolated` |
| TRAP-09 | 超大版本 | JSON精度损失 | 文本序列化 | `app/values.py` | `tests/test_m2.py::test_large_version_precise` |
| TRAP-13 | 删除后迟到旧写 | 文档复活 | 最大版本墓碑 | `app/modules/m3_versions/rules.py` | `tests/test_m3.py::test_tombstone_beats_late_old_write` |
| TRAP-23 | 延迟阈值边界 | 多判延迟 | 等于阈值通过 | `app/modules/m5_latency/rules.py` | `tests/test_m5.py::test_threshold_equal_pass` |

## 对账规则

事件身份=(event_id,side)。输入逻辑记录=最终采纳血缘记录+隔离记录+非事件物理行（空行/分段表头）。派生记录用_sources保留物理行、用_records保留逻辑记录，event_ledger按事件身份逐到达挂账，因此重试合并不丢到达、分组不丢行。同内容重试归一条规范事件，retry_count与arrivals可追回每次到达，不新增结论；同身份指纹冲突整组隔离，禁止冒充对平。业务预期合计与上游申报合计之差等于逐行差异之和。结果按输入摘要、规则版本及参数产生唯一批次，事务写入；同源重跑只复用已有批次。页面（m1/m6事件血缘账面板）与证据CSV导出（kind=lineage:<state>）读取同一lineage_ledger。

## 已知不覆盖

4MB以上文件需预先按业务键分批；不模拟生产支付与外部回调。人工复核只变更批次状态，不改写原始记录。
