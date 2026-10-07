#!/usr/bin/env python3
"""Serve the local Studio UI and JSON API with Python's standard library."""
from __future__ import annotations

import argparse
import json
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from studio import KINDS, Studio, StudioError, bounded, VERSION

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = Path(__file__).resolve().parents[1] / 'frontend'


class Handler(BaseHTTPRequestHandler):
    server_version = 'KnowledgeStudio/1.4'

    def json_response(self, payload, status=200):
        data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers(); self.wfile.write(data)

    def guard(self):
        host = self.headers.get('Host', '')
        port = self.server.server_address[1]
        allowed = {f'127.0.0.1:{port}', f'localhost:{port}'}
        if host not in allowed:
            raise StudioError('仅允许通过 localhost / 127.0.0.1 访问本地工作台', 403)
        origin = self.headers.get('Origin')
        if origin and origin not in {'http://' + h for h in allowed}:
            raise StudioError('不接受跨站请求；请在工作台页面操作', 403)

    def do_GET(self):
        self.handle_request(False)

    def do_POST(self):
        self.handle_request(True)

    def handle_request(self, mutation):
        try:
            self.guard()
            url = urlsplit(self.path); path = unquote(url.path)
            qs = parse_qs(url.query)
            args = {k:v[0] for k,v in qs.items()}
            for k in ('kinds','relations'):
                if k in args: args[k] = [x for x in args[k].split(',') if x]
            service = self.server.studio
            if mutation:
                if self.headers.get('Content-Type','').split(';')[0] != 'application/json':
                    raise StudioError('请求必须使用 application/json',415)
                length = bounded(self.headers.get('Content-Length'),1,1024*1024,'Content-Length')
                try:
                    payload = json.loads(self.rfile.read(length), parse_constant=lambda s: (_ for _ in ()).throw(ValueError(s)))
                except (ValueError,UnicodeDecodeError):
                    raise StudioError('JSON 无效')
                if not isinstance(payload,dict): raise StudioError('请求体必须是 JSON 对象')
                if path == '/api/query': result = service.query(payload)
                elif path == '/api/multihop': result = service.query_paths(payload)
                elif path == '/api/feedback': result = service.feedback(payload)
                elif path == '/api/evidence/bind': result = service.bind(payload)
                elif path == '/api/evidence/unbind': result = service.unbind(payload)
                elif path == '/api/rollback': result = service.rollback(payload)
                elif path.startswith(('/api/save/','/api/preview/')):
                    action, kind, node_id = path.removeprefix('/api/').split('/',2)
                    ref = f'{kind}://{node_id}'
                    result = service.save(ref,payload) if action=='save' else service.preview(ref,payload)[0]
                else: raise StudioError('接口不存在',404)
                self.json_response(result); return
            if path == '/api/status': result = service.status()
            elif path == '/api/health': result = {'ok':True,'version':VERSION}
            elif path == '/api/overview': result = service.overview()
            elif path == '/api/traces': result = service.traces()
            elif path == '/api/trace': result = service.trace(args.get('trace_id'))
            elif path == '/api/search': result = service.search(args.get('q',''),args.get('kind'))
            elif path == '/api/detail': result = service.detail(args.get('ref'))
            elif path == '/api/history': result = service.history(args.get('ref'))
            elif path == '/api/source':
                source = args.get('path')
                if source not in service.snapshot()[3]: raise StudioError('来源不在准入清单中',404)
                result = service.source_index(source)
            elif path.startswith('/api/evidence/'):
                result = service.locate(path.removeprefix('/api/evidence/'))
            elif path.startswith('/api/model/'):
                kind = path.removeprefix('/api/model/')
                if kind not in KINDS: raise StudioError('未知模型类型')
                result = service.snapshot()[0][kind][KINDS[kind]]
            elif path.startswith('/api/node/'):
                kind, node_id = path.removeprefix('/api/node/').split('/',1)
                if node_id.endswith('/evidence'):
                    ref = f'{kind}://{node_id.removesuffix("/evidence")}'
                    result = service.evidence(ref,args.get('q',''),args.get('limit',8))
                else: result = service.find(f'{kind}://{node_id}')['data']
            elif path.startswith('/api/graph/'):
                kind, node_id = path.removeprefix('/api/graph/').split('/',1)
                result = service.graph(f'{kind}://{node_id}',args.get('depth',1),args.get('direction','both'),
                                       args.get('kinds'),args.get('relations'),args.get('max_nodes',60))
            elif path.startswith('/api/'):
                raise StudioError('接口不存在',404)
            else:
                name = {'/':'index.html','/index.html':'index.html','/main.js':'main.js',
                        '/workflows.js':'workflows.js','/styles.css':'styles.css'}.get(path)
                if not name: raise StudioError('页面不存在',404)
                data = (FRONTEND/name).read_bytes()
                self.send_response(200)
                self.send_header('Content-Type', {'html':'text/html','js':'text/javascript','css':'text/css'}[name.split('.')[-1]]+'; charset=utf-8')
                self.send_header('Content-Length',str(len(data)))
                self.send_header('Cache-Control','no-store')
                self.send_header('X-Content-Type-Options','nosniff')
                self.send_header('Content-Security-Policy', "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'")
                self.end_headers(); self.wfile.write(data); return
            self.json_response(result)
        except StudioError as exc:
            self.json_response({'error':str(exc)},exc.status)
        except (ValueError,TypeError,KeyError,AttributeError) as exc:
            self.json_response({'error':f'参数或数据结构无效：{exc}'},422)
        except Exception as exc:
            print(f'[{type(exc).__name__}] {exc}',file=sys.stderr)
            self.json_response({'error':'读取或写入失败；详见服务终端。'},500)


def create_server(root=ROOT, port=8787):
    server = ThreadingHTTPServer(('127.0.0.1',port),Handler)
    server.studio = Studio(root)
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',default=str(ROOT))
    parser.add_argument('--port',type=int,default=8787)
    parser.add_argument('--open',action='store_true')
    args = parser.parse_args()
    try:
        server = create_server(args.project,args.port)
        status = server.studio.status()
    except Exception as exc:
        print(f'启动失败：{exc}\n请检查项目目录、PyYAML 和端口占用。',file=sys.stderr)
        return 1
    address = f'http://127.0.0.1:{server.server_address[1]}'
    print(f'Knowledge Studio {status["version"]} | {address}\nCtrl+C 停止。',flush=True)
    if args.open: webbrowser.open(address)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
    return 0


if __name__=='__main__':
    raise SystemExit(main())
