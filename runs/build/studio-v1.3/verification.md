# Studio v1.3 验证报告

本轮为一次合并交付，日期按用户时区记为 2026-10-02。环境为 Linux / Python 3.12 / Node；日志中的 UTC 机器时间与用户本地日期可能不同。

## 已执行与证据

| 检查 | 结果 | 证据 |
|---|---|---|
| 正式模型校验 | 17 场景、234 概念、163 实体、50 来源；0 错误、0 断链 | `model-validation.json` |
| 原始模型和来源保护 | 三份 YAML 与原始包字节一致；50 篇来源内容一致；不含人工确认伪数据 | `baseline-integrity.json` |
| Python 自动测试 | 20/20 通过，包含原有 7 项与新增 13 项 | `unit-tests.txt`、`tests/test_studio.py` |
| 真实 HTTP | 本机服务启动；静态页面、Unicode 路由、预览→保存、错误与跨站请求检查通过 | `unit-tests.txt` |
| 前端交互 | 11 项 DOM/API 联动检查通过 | `frontend-smoke.txt`、`tests/frontend_smoke.cjs` |
| 24 道种子题回归 | Top1 61.11%、Top3 94.44%；模型/Raw 来源命中均 83.33%；边界行为 100% | `retrieval-regression.json` |
| ZIP 解压运行 | 解压后清单哈希、模型、HTTP 和指定两跳路径通过 | `package-smoke.json` |
| 语法 | Python 编译、JS `node --check` 通过 | 下列执行命令 |

模型原有的两类提示保留：8 个节点超过 6 项关系、99 个实体只使用 `related_to`，属于知识语义复核项，不是程序错误；3 个概念的弱证据标签也未自动修改。

## 验证覆盖

新增自动测试覆盖：明确关系排除正文提及；同名不同类型节点；入向/出向、类型与关系过滤；真实两跳字段；反向标记、无路径和限深度；原文行号和章节；证据确认、重复提交、撤销与失效；来源路径越界；三类节点保存、无变化重复保存、回滚；错误结构与断链不写入；版本冲突保护；后续修改不允许回滚；模拟磁盘替换失败仍保留原文件；更新脚本保留本地数据/Git且重复执行不重复写入；真实 HTTP 错误处理。

前端联动使用 DOM 模拟与真实 API，覆盖完整导航、IPO 展示、原文定位、确认/撤销、编辑/差异/保存、历史回滚、二跳 SVG 结构及引用字段、多跳解释、越界拒答、搜索不丢全量导航、未保存切换保护。该检查没有浏览器渲染引擎。

## 命令

```bash
python scripts/validate_model.py . --report runs/build/studio-v1.3/model-validation.json
python -m unittest discover -s tests -p 'test*.py' -v
python scripts/verify_frontend.py
python scripts/evaluate_retrieval.py . --no-save
python -m py_compile gui/backend/app.py gui/backend/studio.py apply_update.py scripts/kb_multihop.py scripts/verify_frontend.py
node --check gui/frontend/main.js
python scripts/package_project.py . --output <zip-path>
```

`verify_frontend.py` 只在临时项目副本写入测试修改，完成后销毁副本，不污染正式模型。

## 未验证与限制

- 未完成 Windows 本机启动：当前执行环境为 Linux。启动脚本的实际 Windows 行为仍需本机检查。
- 未完成真实浏览器视觉检查：本环境无 Chromium，安装器下载返回无效 ZIP，未重复相同安装方法。下一步是 Windows 浏览器检查页面、证据弹窗和图的布局。
- 没有自动确认原始 414 个节点的段落依据；候选检索不能替代人工支持关系判断。
- 种子题标签仍为 `needs_human_review`，数字属于回归结果，不是正式业务准确率或多跳效果评测。最终回答质量与多跳查询实用性待用户审查。
- 多跳是有上限的引用遍历，不穷举所有路径、不自动回答、不证明因果；截断会明示。
- GUI 与外部编辑器没有共享锁；提交前哈希能识别一般冲突，但极短的检查与替换间隔仍无法保证外部多进程同时写入。当前应采用单一编辑入口。

没有阻止本轮程序与 ZIP 交付的环境障碍；以上边界继续保留为待验证项。
