# Knowledge Studio v1.5

从项目根目录运行 python gui/backend/app.py --open，访问 http://127.0.0.1:8787。Windows 可双击 start-studio.bat。不要直接打开 frontend/index.html。

新增“资料与知识建设”，完成资料准入、两轮任务、候选审查与增量发布，见 [建设流程](../docs/knowledge-construction.md)。Agent 从 [AGENTS.md](../AGENTS.md) 开始，通过 CLI 或本机 JSON API 操作同一内核。

默认从一跳检索开始，另有全局视角、运行记录、知识浏览、局部关系图和多跳探索。操作及 API 见 [工作台手册](../docs/studio-guide.md)，范围见 [ADR 005](../docs/adr/005-one-hop-first-observable-studio.md)。

后台使用 Python 标准库 HTTP 与 PyYAML，前端为本地静态文件；无 Flask、npm、CDN 或模型 API 运行依赖。
