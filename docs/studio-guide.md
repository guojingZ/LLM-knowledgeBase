# v1.5 工作台操作与覆盖更新

## 安装或更新

Python 3.10+。新项目可直接使用 ZIP 中的 `LLM-knowledgeBase/`。已有本地项目请把新包解压到项目外部目录，从新包根目录执行：

```powershell
python apply_update.py --target "C:\Tool\Code\Project\LLM-knowledgeBase"
```

路径请改为实际项目位置。该脚本覆盖程序与文档；对本地已有 `model/`、`raw/`、`registry/`、`runs/`、`eval/` 文件保留原内容，只补充缺失文件；保留 `.git`、`.venv`，不删除任何旧文件。可以重复执行，未变化的程序文件不会重复写入。没有需要先手工删除的项目目录。

如果手动覆盖，请先备份或提交 Git，再覆盖程序和文档，保留上述数据目录中已有文件。整包包含 v1.0.0 的知识快照：17 场景、234 概念、163 实体、50 来源；不要用快照替换你在本地新修改的知识。

## 启动

Windows 双击 `start-studio.bat`，首次会创建虚拟环境并安装依赖，然后打开页面。网络不可用时可在已有 PyYAML 的 Python 环境手动启动：

```powershell
python -m pip install -r requirements.txt
python gui/backend/app.py --open
```

地址为 `http://127.0.0.1:8787`。终端按 Ctrl+C 停止。端口被占用可运行 `python gui/backend/app.py --port 8788 --open`。Mac/Linux 可运行 `sh start-studio.sh`。界面与 API 同一地址提供，无需单独打开 HTML，无需 Flask / npm。

## 资料与知识建设

新增页面按资料准入、两轮提取/比较、候选审查、预览发布推进。资料状态与知识处理状态分开；来源更新可创建新任务复核。详细步骤和数据位置见 [建设手册](knowledge-construction.md)，Agent 定向操作见 [操作指南](../application/agent-operations.md) 与根目录 [AGENTS.md](../AGENTS.md)。

## 一跳检索与多跳预览

默认入口为“一跳检索”。输入问题后，程序选择场景，取阶段直接引用的知识项（最多 12 个），再从对应来源检索段落（默认 8 段）。匹配分是词语匹配启发式，不是正确概率。需要澄清时，选择候选场景后重新检索；Raw 模式直接搜索已准入原文，用于对照，不展开图关系。

结果展示选定场景、直接知识、阶段与引用位置、原文、文本摘要和实际上下文 JSON。JSON 比文本摘要更完整；本期没有扩展 IPO/decomposition 参与主问答。“查看可继续探索的路径”定位到后续关系预览。预览只展示“场景 → 本次直接知识 → 场景未直接引用的后续节点”，不检索后续原文，不加入本次上下文。点击“用此路径开始探索”只填写表单；在“多跳探索”提交后，才运行多跳并创建独立 trace。

## 全局视角

- 全局图加载全部节点，包括独立节点。圆环按类型排布，不表示层级。默认隐藏一般 related_to 关系，可改为全部；有缩放、名称、类型和证据状态筛选。
- 场景—知识矩阵包含全部场景和概念/实体列，仅标记阶段直接 uses。可横向滚动、筛选知识列、悬停查看阶段或点击节点。
- 证据覆盖显示来源数、有效支持记录、具体已审范围、待复核数和查询使用次数。“有已确认字段”只表示部分字段已有支持，不能当作整体知识正确率；节点关联类确认不计入已审字段数量。
- 运行记录可以叠加使用节点和已记录路径到当前全局图。历史事实仍以运行快照为准，当前图不保证与当时版本相同。

## 运行记录与人工评价

GUI 一跳、Raw 和主动多跳提交，以及两种 CLI 默认保存到 runs/evaluation/<trace_id>/。普通节点搜索、浏览和段落定位不单独生成问题 trace。CLI --no-save 只输出结果。

新记录有 query.json、context.json、metadata.json；包括当时的段落/上下文或路径快照、完整查询参数、版本、相关文件哈希和检索耗时。耗时不含记录落盘与传输。查询前后模型、来源、登记或代码版本变化会提示复核。旧记录保留回放，未保存的版本与耗时标为未记录，不补造历史信息。

在“运行记录”筛选并打开记录，可查看快照、当前原文定位、参数/版本、图中叠加及 JSON 导出。定位原文读的是当前来源；来源与历史哈希不同会提示，原段落已不存在则拒绝定位，历史段落仍保留。

评价分为场景是否合适、证据是否充分、结果是否有用，并可填说明和预期场景。保存反馈并同步待审队列，不自动修改正式模型。相同反馈重复提交不新增，旧窗口版本冲突会被拒绝。队列审查状态由 registry/application_feedback_queue.yaml 维护；改变反馈后重回待审。队列同步失败会保留已保存评价并说明部分成功，刷新本次记录、再次保存即可重试。

运行列表汇总人工有用性数量，这不是答案准确率。最终 Agent 回答未自动采集，完整旧版本重新执行仍需要保留对应 Git 或项目文件版本。

## 浏览与编辑

左侧搜索完整节点内容，可以按场景、概念、实体切换；所有节点可访问，不再截断前 80 个。选定节点后，查看定义、IPO、场景阶段、明确关系和被引用节点。编辑 JSON 可以维护所有字段。

编辑顺序：修改 → 检查并预览差异 → 查看受影响引用节点 → 保存。保存前检验结构、已准入来源和显式引用。id 不可直接修改，以免引用断链。每次保存比对整个模型文件 SHA256；外部编辑或另一窗口保存后，旧版本提交会被拒绝，需刷新后重新编辑。

仅替换选中节点的 YAML 文本段，保留其他节点、文件头和顶层元数据；被编辑节点内部的注释及排版可能重新序列化。每次写入先记录唯一备份，再通过临时文件和 `os.replace` 原子替换。历史位于 `runs/gui/history/`。重复保存无变化内容不会新增备份。

回滚仅允许当前文件仍等于那次保存结果时执行。存在后续修改时按钮不可用，接口也会拒绝整文件回滚，避免覆盖其他修改。外部编辑器与工作台不共享锁；提交前哈希检查能识别一般冲突，但建议同一时刻只使用一个编辑入口。

## 证据定位

右栏仅检索当前节点 `sources` 指向的已准入文件，显示章节、原文段落、Evidence ID、行号。点击“定位原文”显示上下文并高亮原始行；也可查看全文。

“检索候选”是文本相关召回，不能据此宣称支持充分。先选“这段支持什么”（定义、阶段规则、IPO 或某条明确引用），可填理由，再点击“确认该段支持节点”。记录同时保存来源与支持范围哈希，确认、候选不会重复展示。

有效确认统一用于 GUI、问题 CLI、Raw 对照及多跳终点。问题词语命中的相关已确认段落有有限排序偏好，不会因确认而忽略相关性。任何来源内容变化、所选支持范围变化或段落移除都会使旧确认需复核；无效确认不作为有效已审支持加入排序。可以重新确认或撤销。

v1.3 的旧记录保留为“旧确认 · 待补充复核”，需人补充范围，不自动认定为逐字段审查。原文哈希与 manifest 不一致会提示，不自动修改准入清单。Evidence ID 仍由路径、段落内容及重复出现次数确定。

本包知识快照没有人工确认样例，测试中的确认与反馈仅在临时目录执行，不冒充业务金标准。

## 关系图

默认展开一跳，支持二跳、场景/概念/实体类型、关系类型、出向/入向/双向过滤。浏览器展示最多 45 个节点，后端最多 120 个，达到上限明确提示；大邻域可先过滤再展开。

边来自 `relations.<type>`、`composition[i].uses[j]`、`ipo.process.tools[i]`、`decomposition[i].uses`。正文出现名称、ID 子串相似、同名或共用来源都不会创建边。箭头始终表示 YAML 记录方向。点击图节点切换中心，展开下方关系明细可回查字段路径及场景阶段。

## 多跳查询

可以输入问题自动召回起点，或直接指定起点/终点（推荐在明确比较两节点时使用）。支持 1–4 跳、三种方向，返回逐步引用解释与终点证据候选。反向浏览会明确标注，不会改写原关系方向。问题越界或召回接近时返回无证据/需澄清，手动指定起点可以直接探索模型。

算法是有上限的 BFS：每个起点到每个节点保留一条最短引用路径，至多 3 个起点、3,000 次关系展开；默认显示 6 条，最多 12 条。达到展开上限、候选未全展示均明确提示。路径探索不是穷举所有可能路径，也不是 LLM 推理或因果证明。无明确关系时返回 `no_path`，不靠共用来源造出路径。

页面可导出路径 JSON。桌面 Agent 可调用同一路径逻辑（默认保存 trace；--no-save 仅输出）：

```powershell
python scripts/kb_multihop.py --question "面对复杂业务故障时，如何定位根因？"
python scripts/kb_multihop.py --start-ref "scenario://如何分析和解决复杂问题" --target-ref "entity://金字塔原理" --direction outgoing --max-depth 3
```

最终回答仍由桌面 Agent 基于原文组织。没有自动模型 API、向量数据库、MCP 或 Onto-Model 六类扩展。

## API

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/api/status`、`/api/health` | 数量、版本、关系、健康状态 |
| GET | `/api/model/{kind}`、`/api/search?q=…&kind=…` | 完整模型/过滤导航 |
| GET | `/api/detail?ref=…` | 节点、revision、入向/出向引用 |
| GET | `/api/node/{kind}/{id}` | 兼容节点读取 |
| GET | `/api/node/{kind}/{id}/evidence?q=…` | 来源、候选、已登记证据 |
| GET | `/api/evidence/{id}`、`/api/source?path=…` | 段落定位/全文 |
| GET | `/api/graph/{kind}/{id}?depth=2&direction=both` | 局部图（可加 kinds/relations/max_nodes） |
| POST | `/api/preview/{kind}/{id}` | `{node, revision}`，差异/影响/preview_token |
| POST | `/api/save/{kind}/{id}` | `{node, revision, preview_token}`，安全回写 |
| GET / POST | `/api/history?ref=…`、`/api/rollback` | 保存记录/`{backup_id, revision}` |
| POST | `/api/evidence/bind` | `{ref, evidence_id, source_sha256, revision, node_revision?, support_field?, review_note?}` |
| POST | `/api/evidence/unbind` | `{ref, evidence_id, revision, support_field?}`；传范围时只撤销该字段 |
| POST | `/api/build/<operation>` | 资料、任务、候选、发布；`tools` 返回操作契约，详见 Agent 操作指南 |
| POST | `/api/query` | `{question, mode?, scenario?, top_k?, evidence_k?}`，一跳／Raw 与保存 trace |
| GET | `/api/overview` | 全部节点、聚合关系、矩阵、证据覆盖与使用统计 |
| GET | `/api/traces`、`/api/trace?trace_id=…` | 运行列表／历史快照 |
| POST | `/api/feedback` | `{trace_id, revision, rating, issues?, notes?, scenario_verdict?, evidence_verdict?, expected_scenario?}`，评价与队列同步 |
| POST | `/api/multihop` | `{query, start_ref?, target_ref?, max_depth?, max_paths?, direction?}` |

JSON 请求需 `Content-Type: application/json`；POST 上限 1 MiB。浏览器跨站请求被拒绝，服务只监听本机。旧版直接提交裸节点的无版本保存接口不再支持，需按 preview→save 调用。

## 验证

```powershell
python scripts/validate_model.py .
python -m unittest discover -s tests -p "test*.py" -v
python scripts/evaluate_retrieval.py . --no-save
# 可选开发检查，需要 Node；使用 DOM 模拟，不检查视觉布局
python scripts/verify_frontend.py
```

本轮实际验证结果见 [v1.5 验证报告](../runs/build/studio-v1.5/verification.md)。Windows 启动脚本需要在 Windows 本机确认，其实现不等同于已经完成 Windows 运行测试。
