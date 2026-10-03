# Knowledge Studio v1.3

从项目根目录运行 `python gui/backend/app.py --open`，浏览器访问 `http://127.0.0.1:8787`。Windows 可双击根目录 `start-studio.bat`，首次创建 `.venv` 并安装 PyYAML；已有依赖后运行不需要联网。不要直接双击 `frontend/index.html`。

用户操作、API 和覆盖说明见 [工作台手册](../docs/studio-guide.md)。原始知识始终在 `model/`、`registry/`、`raw/accepted/`；界面只是维护入口。后台采用 Python 标准库 HTTP 服务，仅监听本机；不依赖 Flask、npm 或 CDN。
