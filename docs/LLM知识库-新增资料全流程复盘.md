# LLM 知识库：一篇新资料「准入 → 正式知识」全流程复盘

> 记录日期：2026-10-09
> 对象项目：`D:\Tool\Project\LLM-knowledgeBase`（版本 v1.5）
> 本次样本：`raw/accepted/知识图谱和本体的区别与联系.md`
> 来源 ID：`src-4cfc5117652611c6`（19,809 字节，sha256 `e6ca192d…5abd`）
> 任务 ID：`job-53e2b72341484645`
> 发布 ID：`pub-59daf45416ce4c91`

---

## 0. 一页速览

这篇记录的目的：把"新纳入一篇文章，直到它变成正式知识模型里的节点"这条链路从零讲清，并回答四个问题：

1. **信息来源分两类**：我直读了哪些项目文件，哪些是主动发起工具请求拿到的？
2. **文件清单**：整个流程新增、修改、留档了哪些文件，各起什么作用？
3. **批量再更新是否合理**：一次攒 5–8 篇统一更新，值不值得？
4. **其他值得注意的点、潜在问题、改进建议**。

**一句话结论**：这条链路是「人定框架 → Agent 提取/比较 → 人审查 → 程序校验并发布」，程序全程**不调用 LLM、不判断语义、不自动批准**，只做结构 / 引用 / 版本 / 原文位置的校验。Agent 的全部"写入"都必须经过 CLI/HTTP 操作，不允许手改 YAML。

**本次结果**：新增概念 5 个、实体 2 个、场景 1 个；复用已有节点 2 个（只追加来源）；丢弃 1 个（FDE）。模型规模：概念 234 → **239**，实体 163 → **165**，场景 17 → **18**。

### 时间线（GMT+8，括号内为 UTC）

| 时间 | 操作 | 产物登记号 | 结果 |
|---|---|---|---|
| 14:57（06:57） | `sources.scan` 基准扫描 | pub-3d879d415dbd4840 | 建立 v1.5 状态基线，生成 `knowledge_build.yaml` + 51 份原文快照 |
| 15:06（07:06） | `sources.import` | pub-ddcf99a46c744eb4 | 新文章进入系统，得到 source_id |
| 15:06（07:06） | `sources.admit` | pub-e2ec5eb6778f497d | 准入通过，落入 `raw/accepted/` |
| 15:21（07:21） | `jobs.create` | pub-2f4dbbf0b8204f4a | 冻结原文 + 三份模型基线，得到 job_id |
| 15:23（07:23） | `jobs.extract` | pub-0dfb8b317de943ad | 提交 11 条候选，逐字校验通过 |
| 15:37（07:37） | `jobs.compare`（第 1 版） | pub-f04f826535b34b47 | 提交 11 条建议 |
| 15:44（07:44） | `jobs.compare`（第 2 版，拆分 RDF/OWL 后重跑） | pub-014d069de110437e | 覆盖重提 |
| 15:44–15:45 | `jobs.review` ×11 | pub-396f… 到 pub-6cd501… | 11 条全部 approved |
| 15:45（07:45） | `jobs.publish` | pub-59daf45416ce4c91 | 状态 completed，落盘正式模型 |

> 注意：第 2 次 compare 是在"未发布前可重跑"的前提下覆盖第 1 次的结果，这属于正常操作；一旦 publish 过，任务就不能再改两轮内容，必须新建任务。

---

## 1. 全流程逐步拆解

整条链路按职责分五个阶段、十来个动作。**每一阶段都标清楚：谁触发、命令是什么、输入输出、写到哪、状态机怎么走。**

### 阶段 0 · 前置：建立状态基线（`sources.scan`）

- **目的**：v1.5 第一次运行时，为已有的 50 篇资料建立"处理状态基线"。
- **命令**：`python scripts/kb_manage.py sources.scan`
- **它做了什么**：注册所有来源、给每个来源做一份原文快照（`runs/build/knowledge/source_versions/<source_id>/<sha256>.txt`）、刷新 `registry/source_manifest.yaml`，并生成 `registry/knowledge_build.yaml`。
- **关键点**：这一步决定了后面"某篇是否处理过"的判断口径。**准入状态（accepted）和知识处理状态（processed）是两条独立状态**——accepted 只说明资料可用，不等于内容已提炼。

### 阶段 1 · 接入与准入

**动作 1｜`sources.import`（导入）**
- 命令：`{"name":"知识图谱和本体的区别与联系.md","text":"<原始全文>"}` → `sources.import`
- 结果：文件先进入 `raw/inbox/`，**尚未准入**；返回 `source_id`、sha256。
- 去重规则：相同内容再次导入返回现有记录（duplicate）；**同名不同内容拒绝覆盖**。

**动作 2｜`sources.admit`（准入）**
- 命令：`{"source_id":"src-4cfc5117652611c6","revision":<最新>,"source_sha256":"<当前>","decision":"accepted","note":""}` → `sources.admit`
- 结果：文件从 `raw/inbox/` 移到 `raw/accepted/`，登记到 `source_manifest.yaml`；`knowledge_build.yaml` 里该来源 `admission: accepted`。
- **边界**：准入是"人"的决定。Agent 不替用户拍板准入；本次是用户已准入后我才接手。

### 阶段 2 · 两轮任务（提取 + 比较）

**动作 3｜`jobs.create`（建任务）**
- 命令：`{"source_ids":["src-4cfc5117652611c6"],"title":"知识图谱与本体"}`
- 它冻结了什么：**完整原文** + **三份模型基线**（scenario / concept / entity 的版本与内容）。产物是任务目录：
  - `task.md`（可读任务书，469 B）
  - `job.json`（候选 + 审查 + 发布记录，初始 16 KB）
  - `models.json`（创建时的完整模型快照，548 KB，供回查）
- 返回：`job_id`、`revision`、`task_path`。状态 → `awaiting_extraction`。
- **一个任务可容纳 1–20 份资料**（这点对问题 3 很关键）。

**动作 4｜第一轮：忠实提取**
- 先导出任务包：`{"job_id":"...","phase":"extraction"}` → `jobs.packet`，得到**带行号的原文快照**、rubric、结果 schema、instructions。
- 我做的事：按判据逐行提取，产出 `observations`。**excerpt 必须与快照对应行逐字一致**（不是摘要）。
- 我的做法：不手打证据，而是**写脚本从任务包快照里按行号程序化截取**，避免引号/全半角偏差，保证逐字校验必过。
- 提交：`jobs.extract`（带 job_id、revision、observations、note）。状态 → `awaiting_comparison`。
- 本次产出 11 条候选：

| # | kind | id | 证据行 | 定义要点 |
|---|---|---|---|---|
| obs-0001 | concept | 本体 | L75,87 | 企业正式承认的对象类型/属性/关系/约束，可共享、校验、执行的语义定义 |
| obs-0002 | concept | 知识图谱 | L57,63 | 以业务对象为节点、关系连接分散系统数据，承载随业务变化的实例事实 |
| obs-0003 | concept | 模式层与事实层 | L107,117 | 本体=模式层（定义与约束），知识图谱=事实层（实例的组织与连接） |
| obs-0004 | concept | 场景闭环建设 | L127,135 | 全局蓝图约束下，从能形成闭环的场景开始建本体，真实数据反向修正 |
| obs-0005 | concept | 语义模块复用 | L131,139 | 场景中形成的语义模块可跨场景复用 |
| obs-0006 | concept | 智能体业务执行 | L159,163,175 | 智能体进入真实业务需要对象识别、事实获取、规则边界与行动条件 |
| obs-0007 | concept | 业务等价性 | L173 | 语言相似 ≠ 业务等价，不能由模型替企业决定 |
| obs-0008 | entity | RDF | L97 | 与 OWL 并称的技术体系之一 |
| obs-0009 | entity | OWL | L97 | 与 RDF 并称的技术体系之一 |
| obs-0010 | entity | FDE | L167 | 仅一处出现、无定义 |
| obs-0011 | scenario | 如何构建可运行的企业语义体系 | L127,197 | 有触发（系统多、数据连了却仍靠人判断）+ 目标的"如何…"任务 |

> 判据中"框架无法表达的内容写 question，不能编造 IPO" 是硬约束。

**动作 5｜第二轮：比较已有模型**
- 导出比较包：`{"job_id":"...","phase":"comparison"}` → `jobs.packet`，得到**原文 + 11 条候选 + 414 条基线目录**。
- 规范要求：**先读目录，再针对近似节点 `catalog ref` 读取完整字段**——不能只看 id 或 define。
- 提交：`jobs.compare`（带 proposals、note）。规则很严：
  - **全部 observations 都必须被 proposals 引用**（每个候选都要有归宿，忽略也要写理由）；
  - 每个正式目标只允许一条修改建议；
  - 动作枚举：`new` / `update` / `evidence` / `merge` / `conflict` / `ignore`。
- 本次 11 条建议（含按用户裁决处理的同名项与拆分项）见下表：

| proposal | action | target | 候选 | 依据行 |
|---|---|---|---|---|
| candidate-0001 | evidence | concept://本体论分析 | obs-0001 | L75,87 |
| candidate-0002 | evidence | entity://知识图谱 | obs-0002 | L57,63 |
| candidate-0003 | new | concept://模式层与事实层 | obs-0003 | L107,117 |
| candidate-0004 | new | concept://场景闭环建设 | obs-0004 | L127,135 |
| candidate-0005 | new | concept://语义模块复用 | obs-0005 | L131,139 |
| candidate-0006 | new | concept://智能体业务执行 | obs-0006 | L159,163,175 |
| candidate-0007 | new | concept://业务等价性 | obs-0007 | L173 |
| candidate-0008 | new | entity://RDF | obs-0008 | L97 |
| candidate-0009 | new | entity://OWL | obs-0009 | L97 |
| candidate-0010 | ignore | entity://FDE | obs-0010 | L167 |
| candidate-0011 | new | scenario://如何构建可运行的企业语义体系 | obs-0011 | L127,197 |

> 状态推进：`awaiting_comparison` → `review_required`。

### 阶段 3 · 人工审查（`jobs.review`）

- 命令：`{"job_id":"...","revision":<最新>,"proposal_id":"candidate-000X","decision":"approved|rejected|hold","note":"..."}`
- 决定：`approved` / `rejected` / `hold`。**拒绝和待定必须写理由；conflict 不能直接通过。**
- 本次 11 条全部 `approved`，**逐条提交**（每次 review 都会产生一条 `review_candidate` 发布记录，把 `job.json` 往前推一个版本）。
- **重要事实**：v1.5 的审查决定写进**任务 `job.json`**（以及 review_candidate 记录），**不写 `registry/review_decisions.yaml`**。后者是 v1.4 及更早的人工裁决台账（mtime 仍是 9-25），容易被误认，见问题 4。

### 阶段 4 · 预览与增量发布

**动作 6｜`jobs.preview`**
- 作用：输出模型差异（diffs）、涉及文件、别名、是否部分发布、`preview_token`。
- **不改模型**，纯预览。本次 `approved_count: 11`、`remaining_count: 0`、`will_complete: True`。

**动作 7｜`jobs.publish`**
- 命令：`{"job_id":"...","preview_token":"<最新>"}`。
- 只发布**已通过项**，**仅替换受影响的 YAML 条目**，保留其他节点和文件头。
- 结果：`status: completed`；`publication_id: pub-59daf45416ce4c91`。
- **保护机制**：来源/模型/登记任一变化都会让旧 `preview_token` 失效；不允许改哈希绕过。
- **落盘范围**：`model/*.yaml`、`registry/gui_evidence.yaml`、`registry/knowledge_build.yaml`、任务 `job.json`。

### 阶段 5 · 复核

- `sources.list` → 本篇 `processing` 由 `unprocessed` 变 **`processed`**，`linked_nodes` 挂到 **10 个节点**，`changed: false`。
- `jobs.get` → `status: completed`，11 条 proposal `published: true`。
- `publications.list` → 19 条写入记录，全部 `committed`。

---

## 2. 问题 1：两类信息来源与边界

整个流程里，我获得信息有**两条通道**，它们是分开的、职责不同。

### A 类 · 直接读取项目文件（用文件读取工具）

这类是**静态事实**：文档、判据、登记台账、源码、以及"已经被工具写下来的运行产物"。

| 文件 | 我读到什么 |
|---|---|
| `AGENTS.md` | 项目 Agent 入口，任务 ↔ 操作入口的对照表、处理约定 |
| `PROJECT.md` | 项目目标与当前边界（本期不改变主检索） |
| `WORKLOG.md` | 本轮状态：v1.5 做了什么、已验证什么、下一步做什么 |
| `application/agent-operations.md` | 17 个操作的顺序、请求字段、返回用途；第一轮/第二轮提交形状 |
| `application/build-rubric.md` | **判据**：什么算一个 concept/entity/scenario，new/update/evidence/merge/conflict 的判定标准 |
| `docs/knowledge-construction.md` | 流程与位置对照表、状态含义、来源更新与恢复章节 |
| `registry/source_manifest.yaml` | 来源清单与准入登记 |
| `registry/review_decisions.yaml`、`review_queue.yaml`、`aliases.yaml` | 历史人工裁决台账、待审队列、别名登记 |
| `model/concepts.yaml` / `entities.yaml` / `scenarios.yaml` | 直接读原有节点的**完整字段**（定义、ipo/decomposition、relations、sources） |
| `raw/accepted/知识图谱和本体的区别与联系.md` | 原文正文 |
| `scripts/kb_build.py`、`scripts/kb_manage.py`、`scripts/kb_evidence.py`、`gui/backend/studio.py`、`gui/backend/app.py`、`start-studio.bat`、`requirements.txt`、`VERSION` | 实现细节：processing 怎么算、compare/review 的状态机、preview/publish 的校验、HTTP 端口与同源限制 |
| `runs/build/knowledge/jobs/.../job.json`、`task.md`、`publications/*/manifest.json` | 已落盘的运行产物 |

### B 类 · 主动发起工具请求（CLI 操作）

这类是**程序计算出的当前事实**：状态、ID、哈希、目录、差异、token。这些"算出来的东西"在文件里读不准，必须走工具。

| 操作 | 我拿它做什么 |
|---|---|
| `tools` | 拉取 17 个操作的契约（JSON schema、必填字段、枚举、写入标记） |
| `sources.list` | 盘点全部来源 + 处理状态 → 借此发现"只有一篇 unprocessed" |
| `sources.scan` | 建立/刷新状态基线（前置步骤） |
| `sources.import` / `sources.admit` | 导入与准入 |
| `jobs.create` | 冻结原文与模型基线，得到 job_id |
| `jobs.packet`(extraction/comparison) | 导出两轮任务包（带行号原文、判据、基线目录） |
| `jobs.extract` | 提交第一轮候选（程序逐字校验 excerpt） |
| `catalog` | 读取既有节点的完整字段与 revision |
| `jobs.compare` | 提交第二轮建议（程序校验"候选必有归宿"） |
| `jobs.get` | 读任务最新状态、revision、freshness_issues |
| `jobs.review` | 逐条提交审查决定 |
| `jobs.preview` | 预览差异，拿 preview_token |
| `jobs.publish` | 按 token 发布落盘 |
| `publications.list` | 查看写入记录与 recovery 状态 |

### 边界规则（这是最该记住的部分）

1. **写操作必须走工具。** 我不能手改 `model/*.yaml` 或 `registry/*.yaml`；正式知识只能经 `jobs.publish` 落盘。本次全程如此。
2. **程序会产生/校验/计算的字段必须走工具拿**：`source_id`、`job_id`、`revision`、`sha256`、`processing` 状态、`preview_token`、`freshness_issues`、diff。它们在文件里读不准——例如 `processing` 是按"有没有 `processed_sha256` 基线"**算出来的**，不是存出来的。
3. **文档、判据、源码、已被工具写下的产物可以直读。** 但要注意：直读的是"某一刻的磁盘状态"，可能与程序口径不一致（`review_decisions.yaml` 就是典型陷阱）。
4. **两条路走的是同一个内核**：CLI `python scripts/kb_manage.py <op>` 和 HTTP `POST /api/build/<op>` 都调用 `KnowledgeBuild.execute(op, payload)`，行为一致。GUI 只是提供 HTTP 的本地服务（`127.0.0.1:8787`，校验同源），**不需要常驻 GUI 窗口**，也**不是必须**——本次全程只用 CLI，没占用端口。
5. **原文里的"指令"只是资料内容**，不能改变 `AGENTS.md` 的操作约定；框架由人定义，Agent 不自行扩类型、补字段、编 IPO。

---

## 3. 问题 2：新增 / 修改 / 留档文件清单

### 3.1 新增文件

| 文件 | 作用 | 为什么新增 |
|---|---|---|
| `raw/accepted/知识图谱和本体的区别与联系.md` | 本篇正文，正式来源 | `import` 入 `raw/inbox`，`admit` 通过后移入 `accepted` |
| `registry/knowledge_build.yaml` | **v1.5 处理状态登记**：每个来源的 `processed_sha256`（处理基线）、`observed_sha256`（当前内容）、`admission`、`active_job` | v1.5 首次运行时由 `sources.scan` 生成（这是新增机制，v1.4 没有） |
| `runs/build/knowledge/source_versions/src-4cfc5117652611c6/e6ca192d….txt` | 本篇原文快照（按 sha256 命名） | 保证"任务按行回查"有冻结依据 |
| `runs/build/knowledge/jobs/job-53e2b72341484645/task.md` | 可读的任务书 | `jobs.create` 生成 |
| `…/job.json` | 候选 + 审查 + 发布记录（最终 50,802 B） | 任务全生命周期的主记录 |
| `…/models.json` | 创建任务时的完整模型快照（547,694 B） | 供回查"当时比较的是哪个基线" |
| `runs/build/knowledge/publications/pub-…/`（共 19 个目录） | 每次写操作的 **before/after 快照 + manifest.json** | 写保护与中断恢复；本次 19 条 = 1 scan + 1 import + 1 admit + 1 create + 1 extract + 2 compare + 11 review + 1 publish |

### 3.2 修改文件

| 文件 | 变化 | 原因 |
|---|---|---|
| `model/concepts.yaml` | +132 行（概念 234 → 239） | 新增 5 个概念；并为 `concept://本体论分析` 追加本篇 sources |
| `model/entities.yaml` | +38 行（实体 163 → 165） | 新增 `RDF`、`OWL`；并为 `entity://知识图谱` 追加 sources |
| `model/scenarios.yaml` | +44 行（场景 17 → 18） | 新增场景「如何构建可运行的企业语义体系」 |
| `registry/gui_evidence.yaml` | +231 行 | 新增字段级证据绑定，本文来源共 36 处引用 |
| `registry/source_manifest.yaml` | +8 行 | 登记新来源（source_id / path / sha256 / 准入） |
| `registry/knowledge_build.yaml` | 更新该来源条目 | `import`/`admit` 写 `observed_sha256`；`publish` 写 `processed_sha256` 锁定基线 |
| `runs/build/knowledge/jobs/.../job.json` | 16 KB → 50 KB | 每步（提取/比较/审查/发布）推进一个版本 |

### 3.3 留档文件（审计 / 回滚用，不是"新知识"）

- `runs/build/knowledge/publications/pub-59daf45416ce4c91/`：本次发布的 **6 对被改写文件的 `N.before` / `N.after`** + `manifest.json`（含每个文件的 before/after 哈希）。涉及 `model/scenarios.yaml`、`model/concepts.yaml`、`model/entities.yaml`、`registry/gui_evidence.yaml`、`registry/knowledge_build.yaml`、任务 `job.json`。
- `runs/build/knowledge/publications/pub-…/`（其余 18 个）：同一批次的阶段性快照。
- `source_versions/`：51 份原文快照。
- `models.json`：任务创建时的模型基线快照。

> **可回滚性**：`publications.recover` 只在"当前文件等于记录里的 before 或 after"时才回退；发现外部改动会拒绝覆盖并保留现场。它是**中断恢复**工具，不是任意历史回滚。

### 3.4 明确"没有被改动"的文件（边界证明）

| 文件 | 状态 | 说明 |
|---|---|---|
| `registry/aliases.yaml` | 未动（10-08） | 本次没走 `merge`，没有登记别名 |
| `registry/review_decisions.yaml` | 未动（9-25） | 这是 v1.4 及以前的**人工裁决台账**，v1.5 审查不写它 |
| `registry/review_queue.yaml` | 未动 | 旧的待审队列 |
| `registry/application_feedback_queue.yaml` | 未动 | 应用反馈队列（与建设候选分开） |
| `model/` 中未被引用的其他节点 | 逐字节保持 | 发布只替换受影响条目 |

---

## 4. 问题 3：有必要一次攒 5–8 篇再统一更新吗？

### 先说结论

**方向对，但必须用对形态。** 正确的批量做法是"**一个任务挂 5–8 个 source_ids**"，**不是**"建 5–8 个独立任务再逐个发布"。后者会被程序的版本保护互相打断。

### 为什么"多个独立任务并行"行不通

文档写得很明确（`docs/knowledge-construction.md` 的"来源更新与复核"）：

> 旧任务遇到来源或**任一正式模型版本变化**，发布会被阻止。当前采用**保守的整文件基线检查**，即使改的是其他节点也需新建任务重新比较。

也就是说：任务 A 在创建时冻结了模型基线 R0；如果任务 B 发布后模型变成 R1，**A 的基线就过期了，A 就发布不了，必须重建**。所以"5–8 个单篇任务并行 → 逐个发布"会自相残杀。而 `jobs.create` 支持一次传 **1–20 个 source_ids**——批量合并进**一个任务**才顺。

### 批量（一个多源任务）的优点

1. **一次冻结基线**：省去反复复制 548 KB 的 `models.json`。
2. **比较更准**：5–8 篇一起看，能更好地判断"这几篇讲的是不是同一个概念"，减少"先建节点、后篇又来 update 改写"的历史抖动。
3. **一次发布**：减少 `model/*.yaml` 的版本漂移次数。
4. **审查能看到全局冲突**：同一主题的多篇一次性摆出来，冲突当场可见。
5. **去重机会大**：`sources.scan` 能报告同内容不同文件；批量时集中去重，避免同一概念被多篇重复引入。

### 批量的代价与风险

1. **知识滞后**：要攒够批量，新知识迟迟不入库。
2. **审查负担集中**：一次要审 5–8 篇 × N 条候选，卡片量陡增，人容易疲劳误判——而审查是这条链路里**唯一的语义判断环节**，不能糊弄。
3. **粒度粗、耦合高**：批次里只要有一篇有争议，整个任务的推进都会被拖住（虽然可以"部分发布"，但有争议项会一直挂着）。
4. **框架缺陷会被放大**：如果当前判据/类型框架还有问题，逐篇能很快暴露，批量会把同一个错误一次性污染 5–8 篇。
5. **主题漂移**：攒的文章若跨主题域，第二轮"同概念判定"难度直线上升。
6. **重复内容风险**：批量里若混入重复来源，要先去重。

### 我的建议（混合策略）

- **主题高度相关的一批**（例如同属"企业知识工程"的 5–8 篇）→ 用**一个多源任务**批量跑，收益最大。
- **引入全新领域、或高风险同名冲突的单篇**（比如本次的"本体/知识图谱"这种跨域同名）→ **单独建任务**，先探路，别混进大批次。
- **绝对不要**用"多个单篇任务并行 + 逐个发布"，会因整文件基线保护互相打断。
- **框架还在演进时优先逐篇**：等类型/判据稳定了，再上批量。
- 无论批量还是逐篇，**发布前先 `jobs.preview` 看 diff**，把不确定项留成 `hold`，确定项先 `publish`（支持部分发布）。

**一句话**：批量能省"比较与发布"的固定成本、提升跨篇判同能力；但把"审查"这个人工瓶颈集中放大了。适合"主题一致、框架已稳、能一次投入集中审查"的场景；不适合"领域跳跃、框架未定、需要快速反馈"的场景。

---

## 5. 问题 4：其他值得注意的环节、潜在问题与改进建议

### 5.1 本次流程里值得留意的机制

1. **逐字证据校验**：excerpt 必须与快照对应行逐字相等，程序会校验。**好的实践是用脚本按行号从任务包快照里截取**，而不是手打。
2. **候选必有归宿**：第一轮每条 observation 都必须在第二轮被某个 proposal 引用；忽略也要用 `ignore` + reason，不允许"候选凭空消失"。
3. **同名 ≠ 同义**：判据明确"名称不同但语义一致用 merge；不能只凭同名合并"。本次两处同名（本体、知识图谱）经用户裁决按**同一概念**处理，用 `evidence` 复用、只追加 sources。
4. **new 节点的硬校验**：concept 必须带 `ipo` 或 `decomposition`，entity 至少要有一条关系，scenario 必须有 composition——否则整批提交 422。所以节点草案要按判据搭，不能省。
5. **一键两版可重跑**：未发布前 `jobs.compare` 可重跑覆盖（本次 RDF/OWL 从 1 个实体拆成 2 个，就是重跑实现的）。
6. **写入是原子的、可恢复的**：一次多文件变化先存 before/after + manifest；中断后 `publications.recover` 回退。

### 5.2 潜在问题（需要持续留意）

1. **同名跨域概念的语义风险（本次最值得记的一条）**
   用户裁决把企业知识工程的「本体」「知识图谱」与个人认知域的 `concept://本体论分析`（哲学义）、`entity://知识图谱`（个人知识管理义）判为**同一概念**，因此只把本篇来源**追加进 sources**，**没有改写它们的 define**。
   - 影响：这两个节点的定义仍是哲学义 / 个人知识管理义，企业知识工程语境只体现在来源里。
   - 风险：将来检索/问答时，一个节点承载两种语境，可能把哲学本体和知识工程本体混在一起召回。
   - 建议：后续要么用 `update` 给它们**补一段企业语境的定义**，要么用 `aliases` 登记"企业本体"这类别名——但要记得**别名当前不参与问答召回**，只进建设目录。

2. **`registry/review_decisions.yaml` 是"沉默的旧台账"**
   v1.5 的审查不写它，但它长得像"审查决定文件"，很容易被误认为本次的裁决落点（本次实测 mtime 未变）。建议在文件头或 README 加一句"v1.4 及以前人工台账，v1.5 审查记录见任务 job.json"，或者干脆归档。

3. **`knowledge_build.yaml` 里 `active_job` 在发布后仍保留**
   本次 publish 后该来源条目仍是 `active_job: job-53e2b72341484645`。虽然 `status` 已是 completed，但残留字段可能让读它的人误判"还有活跃任务"。建议确认发布后是否应清空，或明确它的语义是"最近处理该来源的任务"。

4. **FDE 降级受格式限制**
   用户要求把 `FDE` 降为 `question`，但**第二轮结果格式只有 `proposals` + `note`，没有 `question` 字段**（`question` 只存在于第一轮提取）。所以只能记成 `ignore` 并在 reason 里写明疑问。建议第二轮格式补一个 question 兜底字段。

5. **整文件基线保护是"隐形约束"**
   "改任何节点都会让其他在途任务失效"这点，文档有写但极易被忽略，是批量/并行操作的主要踩坑点（见问题 3）。

6. **来源更新会按哈希失效**
   更新已有资料要**保持原路径**、本地改 `raw/accepted` 原文，再 `sources.scan`；相关字段确认会按来源哈希失效，需新建任务重新比较。

### 5.3 工程与流程改进建议

1. **尽快把 v1.5 基础设施单独提交一次。** 本次核对发现项目工作树里有**大量未提交的 v1.5 改动**（`AGENTS.md`、`scripts/kb_build.py`、`scripts/kb_manage.py`、`tests/test_knowledge_build.py`、`docs/knowledge-construction.md`、`runs/build/studio-v1.5/` 等全是未跟踪/已修改）。本次流程又叠加了 `model/` 与 `registry/` 的内容改动。**建议先提交"v1.5 基础设施"，再单独提交"本次知识增量"**，否则"功能"和"内容"混在一个 diff 里，将来很难定位。

2. **PyYAML 依赖要显式化。** 项目要求 Python 3.10+ 与 PyYAML，但本机默认 Python 没有 PyYAML。建议 `start-studio.bat` / README 增加依赖检测与一键安装，或在 `requirements.txt` 附近给安装说明。

3. **不要同时从两份项目目录操作。** 文档明确 GUI 与 CLI 要读同一项目。本次全程只用 CLI、默认项目根目录，没有第二副本。

4. **中间产物别进项目。** 本次我生成的提取/比较 payload 全部放在系统临时目录（`%LOCALAPPDATA%\Temp\`），项目内零新增临时文件——建议把这条固化成规范。

5. **搜索/问答尚未消费新知识。** 本期主检索仍是一跳，别名未接问答召回。新节点进了模型，**不等于**问答效果已验证——需要后续用真实问题做人工评测。

6. **已发布任务不可回头改。** 一旦 publish，只能继续裁决未发布项，想改两轮内容必须新建任务。这既是保护也是约束，排期时要预留"重跑"的成本。

7. **`models.json` 体积固定 548 KB。** 每个任务都复制一份完整模型快照；资料规模增长后建议评估是否改为引用式快照（记录 revision + 差量），避免任务目录线性膨胀。

8. **审查是唯一的语义闸门。** 程序不会判断文字含义、不会自动批准；`requires_user_decision` 表示必须有业务决定。**已授权的决定不用重复询问，但"开发迭代"不等于"所有未来候选自动通过"**——这条边界要一直守住。

---

## 6. 附：可复现命令模板

> 环境：项目缺 PyYAML，我建了隔离 venv（`~/.workbuddy/binaries/python/envs/default`），未改项目自己的 `.venv`，未占用 8787 端口。

```bash
PY="C:\Users\lenovo\.workbuddy\binaries\python\envs\default/Scripts/python.exe"
cd "D:\Tool\Project\LLM-knowledgeBase"

# 0) 盘点与状态
"$PY" scripts/kb_manage.py tools
"$PY" scripts/kb_manage.py sources.list
"$PY" scripts/kb_manage.py jobs.list
"$PY" scripts/kb_manage.py publications.list

# 1) 准入（人已决定后）
printf '{"source_id":"src-4cfc5117652611c6","revision":"<最新>","source_sha256":"<当前>","decision":"accepted","note":""}' \
  | "$PY" scripts/kb_manage.py sources.admit --input -

# 2) 建任务 + 第一轮
printf '{"source_ids":["src-4cfc5117652611c6"],"title":"知识图谱与本体"}' \
  | "$PY" scripts/kb_manage.py jobs.create --input -
printf '{"job_id":"job-53e2b72341484645","phase":"extraction"}' \
  | "$PY" scripts/kb_manage.py jobs.packet --input -
cat obs_payload.json | "$PY" scripts/kb_manage.py jobs.extract --input -

# 3) 第二轮
printf '{"job_id":"job-53e2b72341484645","phase":"comparison"}' \
  | "$PY" scripts/kb_manage.py jobs.packet --input -
cat cmp_payload.json | "$PY" scripts/kb_manage.py jobs.compare --input -

# 4) 审查 → 预览 → 发布
printf '{"job_id":"...","revision":"<最新>","proposal_id":"candidate-0001","decision":"approved","note":""}' \
  | "$PY" scripts/kb_manage.py jobs.review --input -
printf '{"job_id":"..."}' | "$PY" scripts/kb_manage.py jobs.preview --input -
printf '{"job_id":"...","preview_token":"<最新>"}' | "$PY" scripts/kb_manage.py jobs.publish --input -
```

---

*本文只记录本次真实发生的操作、落盘事实与推论；所有 ID、哈希、时间均取自项目自身产物，未做推测。*
