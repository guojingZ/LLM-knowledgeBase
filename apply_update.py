#!/usr/bin/env python3
"""Apply program updates while retaining existing local knowledge and Git state."""
import argparse
import os
import shutil
import tempfile
from pathlib import Path

PRESERVE={'model','raw','registry','runs','eval'}
EXCLUDE={'.git','.venv','__pycache__','node_modules'}


def apply(source,target):
    source=Path(source).resolve();target=Path(target).resolve()
    if target==source or target.is_relative_to(source) or source.is_relative_to(target):
        raise ValueError('更新源与目标目录不可相同或相互包含，请解压到项目外部目录。')
    paths=[p for p in sorted(source.rglob('*')) if p.is_file() and not set(p.relative_to(source).parts)&EXCLUDE
           and p.name!='PACKAGE-MANIFEST.sha256' and p.suffix not in {'.pyc','.bak'}]
    result={'created':0,'updated':0,'preserved':0,'unchanged':0}
    for p in paths:
        relative=p.relative_to(source);dest=target/relative
        if not dest.resolve().is_relative_to(target):
            raise ValueError(f'目标路径越界：{relative}')
        if dest.exists() and relative.parts[0] in PRESERVE:
            result['preserved']+=1;continue
        data=p.read_bytes()
        if dest.exists() and dest.read_bytes()==data:
            result['unchanged']+=1;continue
        existed=dest.exists();dest.parent.mkdir(parents=True,exist_ok=True)
        fd,tmp=tempfile.mkstemp(prefix='.kb-update-',dir=dest.parent)
        try:
            with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
            shutil.copymode(p,tmp);os.replace(tmp,dest)
        finally:
            if os.path.exists(tmp):os.unlink(tmp)
        result['updated' if existed else 'created']+=1
    # The source ZIP manifest describes the delivered snapshot, not locally edited data.
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--target',required=True,help='Existing local LLM-knowledgeBase folder')
    a=p.parse_args()
    print(apply(Path(__file__).resolve().parent,a.target))
    print('完成。正式模型、原始资料、注册表、运行历史、评测集和 Git 已保留。')


if __name__=='__main__':main()
