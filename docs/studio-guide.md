# v1.3 工作台操作与覆盖更新

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

## 浏览与编辑

左侧搜索完整节点内容，可以按场景、概念、实体切换；所有节点可访问，不再截断前 80 个。选定节点后，查看定义、IPO、场景阶段、明确关系和被引用节点。编辑 JSON 可以维护所有字段。

编辑顺序：修改 → 检查并预览差异 → 查看受影响引用节点 → 保存。保存前检验结构、已准入来源和显式引用。id 不可直接修改，以免引用断链。每次保存比对整个模型文件 SHA256；外部编辑或另一窗口保存后，旧版本提交会被拒绝，需刷新后重新编辑。

仅替换选中节点的 YAML 文本段，保留其他节点、文件头和顶层元数据；被编辑节点内部的注释及排版可能重新序列化。每次写入先记录唯一备份，再通过临时文件和 `os.replace` 原子替换。历史位于 `runs/gui/history/`。重复保存无变化内容不会新增备份。

回滚仅允许当前文件仍等于那次保存结果时执行。存在后续修改时按钮不可用，接口也会拒绝整文件回滚，避免覆盖其他修改。外部编辑器与工作台不共享锁；提交前哈希检查能识别一般冲突，但建议同一时刻只使用一个编辑入口。

## 证据定位

右栏仅检索当前节点 `sources` 指向的已准入文件，显示章节、原文段落、Evidence ID、行号。点击“定位原文”显示上下文并高亮原始行；也可查看全文。

“检索候选”是文本相似度召回，不能据此宣称段落充分支持知识。“确认该段支持节点”由人判断后登记到 `registry/gui_evidence.yaml`，可撤销确认。确认记录包括来源内容哈希；任何来源内容变化都会将旧确认标记为失效，需重新审查。源文件哈希与 manifest 不一致会在界面提示，但不自动修改 manifest。Evidence ID 由来源路径、段落内容和同内容出现次数确定，前面插入普通段落后原 ID 通常不变；段落本身变更后 ID 变化。

本包没有伪造人工确认记录，所有已有模型仍只具备文件级来源引用；段落候选应由你确认。

## 关系图

默认展开一跳，支持二跳、场景/概念/实体类型、关系类型、出向/入向/双向过滤。浏览器展示最多 45 个节点，后端最多 120 个，达到上限明确提示；大邻域可先过滤再展开。

边来自 `relations.<type>`、`composition[i].uses[j]`、`ipo.process.tools[i]`、`decomposition[i].uses`。正文出现名称、ID 子串相似、同名或共用来源都不会创建边。箭头始终表示 YAML 记录方向。点击图节点切换中心，展开下方关系明细可回查字段路径及场景阶段。

## 多跳查询

可以输入问题自动召回起点，或直接指定起点/终点（推荐在明确比较两节点时使用）。支持 1–4 跳、三种方向，返回逐步引用解释与终点证据候选。反向浏览会明确标注，不会改写原关系方向。问题越界或召回接近时返回无证据/需澄清，手动指定起点可以直接探索模型。

算法是有上限的 BFS：每个起点到每个节点保留一条最短引用路径，至多 3 个起点、3,000 次关系展开；默认显示 6 条，最多 12 条。达到展开上限、候选未全展示均明确提示。路径探索不是穷举所有可能路径，也不是 LLM 推理或因果证明。无明确关系时返回 `no_path`，不靠共用来源造出路径。

页面可导出路径 JSON。桌面 Agent 可调用同一只读逻辑：

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
| POST | `/api/evidence/bind` | `{ref, evidence_id, source_sha256, revision}` |
| POST | `/api/evidence/unbind` | `{ref, evidence_id, revision}` |
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

本轮实际验证结果见 [v1.3 验证报告](../runs/build/studio-v1.3/verification.md)。Windows 启动脚本需要在 Windows 本机确认，其实现不等同于已经完成 Windows 运行测试。
