# Studio v1.5 验证记录

日期：2026-10-08。范围是资料与知识建设、定向 Agent 操作及原有功能回归；正式知识快照保持 v1.4，未向其植入测试候选。

## 实际结果

| 检查 | 结果 | 证据 |
|---|---|---|
| Python 自动测试 | 48 项通过 | python-tests.log；tests/test_knowledge_build.py 与原有测试 |
| 前端 DOM/API 事件检查 | 23 项通过 | frontend-checks.json、frontend-checks.log |
| 正式模型结构与引用 | 0 错误、0 断链；2 项既有质量警告 | model-validation.json |
| 原有 model/raw/registry | 60 文件字节一致；未生成测试建设状态 | baseline-integrity.json |
| 固定种子题 | 24 题，指标与 v1.4 完全一致 | retrieval-v14.json、retrieval-v15.json |
| 兼容正式分解引用列表 | 通过 | list-reference-validation.json |
| 原项目覆盖升级 | 141 本地数据/Git 文件保留，第二次 created/updated 均 0 | upgrade-verification.json、package-upgrade-check.json |
| ZIP 解压与清单 | 全条目 SHA-256 正确，无重复、缓存或活动写锁；解压后 CLI 可运行 | package-upgrade-check.json |
| GUI 与 CLI 操作契约 | 17 项，HTTP/CLI 返回相同契约，新前端资源 HTTP 200 | upgrade-verification.json |

归档检查记录对应最终文档合入前的打包验证；最终 ZIP 交付前再次校验完整清单和覆盖升级。manifest_verified_files 以被检查的归档为准，不把前一次文件数当作最终归档文件数。

## 有效测试覆盖

隔离项目中验证导入、重复内容、准入移动、拒绝保留、扫描幂等、原文快照、两轮任务、伪造摘录拒绝、候选必须全覆盖、重复结果保留审查、完整节点和同批引用、未通过依赖阻止发布、审查/预览保护、字段支持共用、同段多字段与范围撤销、merge 保持 id 与别名登记、全部拒绝/空任务完成、部分发布、来源/模型变动拒绝旧任务、来源缺失提示、路径/写锁/版本、故障补偿与中断恢复拒绝外部覆盖。保留来源自定义元数据、未变 YAML 条目、文件头、空模型首条插入与 UTF-8 BOM。

DOM 检查覆盖原有问答、图、证据、编辑/回滚、trace/评价；新增资料导入/准入/全文、创建任务、两轮 JSON 导入、人审、发布后当前节点刷新、字段证据和工具发现。DOM 模拟不检查 CSS 或浏览器下载行为。

旧 inventory_sources 默认写入转到统一扫描，project_status 使用同一状态，测试覆盖 .txt 准入计数和“不纳入”不会被旧盘点改回 pending。

## 种子题指标

18 道回答题、6 道边界题。Top1 场景准确率 0.6111，Top3 召回 0.9444，模型/Raw 来源命中均 0.8333，边界行为 1.0；题集状态 needs_human_review。主检索算法与展开预算没有改变；不能把相同指标描述为答案质量提升。

## 复现

从项目根目录：

```bash
python -m unittest discover -s tests -p "test*.py" -v
python scripts/verify_frontend.py
python scripts/validate_model.py .
python scripts/evaluate_retrieval.py . --no-save
python scripts/kb_manage.py tools
python runs/build/studio-v1.5/verify-release.py 新ZIP路径 v1.4项目路径 --report 检查结果.json
```

模型校验仍有关系超过 6 个目标的 8 项、仅 related_to 的 99 个实体两类质量警告，本轮未擅自重写模型。

## 尚未验证

- 实际桌面 Agent 对新资料的提取、比较与支持判断是否准确；本地程序没有内置 LLM 调用。工程测试用明确构造的候选，不能冒充业务金标准。
- 最终问答答案质量、完整字段参与问答收益或语义多跳；这些不属于本期实现。
- Windows 本机启动与真实浏览器视觉布局；环境未提供 Playwright/Chrome 内核，没有将 DOM 检查写成浏览器测试。

跨进程锁协调 GUI/CLI，外部编辑器不共享锁。多文件写入采用日志与补偿恢复，不是数据库事务；异常强制退出可能需确认旧进程停止后移除残留写锁，再 recover。遇到其他外部版本保留现场。
