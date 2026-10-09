"""One cross-process write lock shared by Studio and knowledge construction."""
from contextlib import contextmanager
from functools import wraps
import os
import json
from pathlib import Path


class WriteConflict(ValueError):
    status = 409


@contextmanager
def project_write_lock(root):
    path = Path(root) / 'registry/.knowledge-write.lock'
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.resolve().is_relative_to(Path(root).resolve()):
        raise ValueError('写锁路径越界')
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise WriteConflict('项目正在写入，或上次进程意外退出留下写锁；确认旧进程已停止后移除 registry/.knowledge-write.lock，再重试')
    try:
        os.write(fd, str(os.getpid()).encode())
        yield
    finally:
        os.close(fd)
        path.unlink(missing_ok=True)


def serialized_write(method):
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        with self.lock, project_write_lock(self.root):
            for path in (self.root / 'runs/build/knowledge/publications').glob('*/manifest.json'):
                if json.loads(path.read_text(encoding='utf-8'))['status'] in {'prepared', 'recovery_required'}:
                    raise WriteConflict('有未完成写入，请先执行 publications.recover')
            return method(self, *args, **kwargs)
    return wrapped
