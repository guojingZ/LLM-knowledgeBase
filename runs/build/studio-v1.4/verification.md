# Studio v1.4 验证报告

- 日期：2026-10-03
- 环境：Linux，Python 3.12.14；Node v24.19.0 仅用于开发 DOM 检查。
- 范围依据：用户确认第一批功能及一跳优先，见 ADR 005。

## 已验证

| 检查 | 结果 | 证据 |
|---|---|---|
| 正式模型与来源完整性 | 比较 55 个文件，字节一致 | baseline-integrity.json |
| 模型校验 | 17 场景、234 概念、163 实体、50 来源；0 错误、0 断链 | model-validation.json |
| Python 自动化 | 31 项通过 | unit-tests.txt |
| 前端 DOM 与真实 HTTP API | 17 项通过；不是截图或视觉检查 | frontend-dom.txt |
| 固定 24 题检索回归 | 与 v1.3 种子指标相同 | retrieval-regression.json |
| ZIP / 覆盖升级 | 检查压缩清单、完整解压、用户数据保留、重复升级及实际 HTTP 启动 | package-smoke.json |

模型校验的 2 类内容警告来自原模型：3 个概念定义/标签较薄，99 个实体仅有 related_to。未进行第二批关系治理，不以零断链代替语义正确。

核心行为包括：一跳不递归加入多跳预览终点；人工确认与候选去重；字段变化、来源变化和旧确认需要复核；GUI/CLI/Raw 的有效登记一致；trace ID 不覆盖历史；历史段落快照不随当前来源变化；评价不写正式模型；版本冲突拒绝旧窗口；队列同步失败保留评价，可重复保存重试；人工队列审查状态与更新反馈正确区分。

## 执行命令

    python scripts/validate_model.py . --report runs/build/studio-v1.4/model-validation.json
    python -m unittest discover -s tests -p "test*.py" -v
    python scripts/verify_frontend.py
    node --check gui/frontend/main.js
    node --check gui/frontend/workflows.js
    python scripts/evaluate_retrieval.py . --no-save
    python scripts/package_project.py . --output 外部输出路径

## 检索回归口径

18 个检索问题：场景 Top1 61.11%，Top3 94.44%，模型导航与 Raw 的预期来源命中率均 83.33%；6 个边界题行为 100%。问题集状态仍为 needs_human_review。这是种子回归，既非最终答案准确率，也非一跳/多跳效果对照。

## 实际失败及修正

- 开发初测发现 GUI 传入的场景参数名与旧检索函数不同，已改为 scenario_id，并增加 HTTP 新入口检查。
- 新静态 workflows.js 最初未进入资产白名单，已补齐并验证实际 HTTP 读取。
- 版本与界面状态更新引起的原检查断言已按 v1.4 实际行为更新，最终检查通过。
- 当前缺少 Chromium 可执行文件；尝试下载的结果不是有效 ZIP，内核安装失败。未重复发起下载或据 DOM 模拟宣称视觉通过。

## 未验证与保留边界

- Windows 启动脚本本轮没有在 Windows 执行，真实浏览器布局仍需本机检查。
- 外部 Agent 最终回答未自动采集，也未进行专家答案评分。
- 本轮没有引入自动跳数、语义重排、向量数据库、模型 API、MCP 或模型关系重构。
- Trace 回放保存时的上下文、段落与路径，不提供完整旧版执行环境；完整重跑还需对应 Git 或项目文件版本。
- 旧人工确认保持原记录，需人工补充支持范围，不等于记录丢失。

## 本机验收顺序

升级并重启 → 一跳示例查询 → 打开节点核对原文并确认定义 → 重查有效确认 → 查看全局图/矩阵/覆盖 → 回放 trace → 保存简单评价。多跳路径预览只填写表单，明确点击查询后才执行。
