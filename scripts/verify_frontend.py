#!/usr/bin/env python3
"""Exercise UI event handlers against a real API; DOM simulation, no visual rendering."""
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'gui/backend'))
from app import create_server


def main():
    node=shutil.which('node')
    if not node:
        print('此可选前端 DOM 验证需要 Node；工作台运行不需要 Node。');return 1
    with tempfile.TemporaryDirectory() as folder:
        target=Path(folder)/'LLM-knowledgeBase'
        shutil.copytree(ROOT,target,ignore=shutil.ignore_patterns('.venv','__pycache__','.git','node_modules'))
        (target/'registry/gui_evidence.yaml').write_text("version: '1.0'\nbindings: {}\n",encoding='utf-8')
        shutil.rmtree(target/'runs/gui',ignore_errors=True)
        server=create_server(target,0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            env=dict(os.environ,QA_ADDRESS=f'http://127.0.0.1:{server.server_address[1]}')
            return subprocess.run([node,str(ROOT/'tests/frontend_smoke.cjs')],env=env).returncode
        finally:server.shutdown();server.server_close();thread.join()


if __name__=='__main__':raise SystemExit(main())
