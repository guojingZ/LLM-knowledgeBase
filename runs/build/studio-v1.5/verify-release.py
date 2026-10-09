import argparse, json, hashlib, tempfile, zipfile, shutil, sys, subprocess, importlib.util
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('archive');p.add_argument('baseline');p.add_argument('--report',required=True);args=p.parse_args()
with tempfile.TemporaryDirectory() as tmp:
    folder=Path(tmp)
    with zipfile.ZipFile(args.archive) as z:
        entries=z.namelist();assert len(entries)==len(set(entries))
        manifest=next(n for n in entries if n.endswith('/PACKAGE-MANIFEST.sha256'))
        prefix=manifest.rsplit('/',1)[0]
        lines=z.read(manifest).decode().splitlines()
        for line in lines:
            sha, relative=line.split('  ',1)
            assert '..' not in Path(relative).parts and not Path(relative).is_absolute()
            assert hashlib.sha256(z.read(prefix+'/'+relative)).hexdigest()==sha
        assert len(entries)==len(lines)+1
        assert not any(set(Path(n).parts)&{'.git','__pycache__','.venv','node_modules'} or n.endswith('/.knowledge-write.lock') for n in entries)
        z.extractall(folder)
    root=folder/prefix;assert (root/'VERSION').read_text().strip()=='1.5.0'
    def cli(project, operation):
        r=subprocess.run([sys.executable,str(root/'scripts/kb_manage.py'),operation,'--project',str(project)],capture_output=True,text=True,check=True)
        return json.loads(r.stdout)
    contract=cli(root,'tools');assert len(contract['operations'])==17
    assert len(cli(root,'sources.list')['items'])==50
    target=folder/'existing';shutil.copytree(args.baseline,target,ignore=shutil.ignore_patterns('__pycache__','.venv','.git'))
    for rel in ['model/concepts.yaml','registry/gui_evidence.yaml','registry/aliases.yaml']:
        f=target/rel;f.write_bytes(f.read_bytes()+b'\n# local edits remain\n')
    raw=next((target/'raw/accepted').glob('*.md'));raw.write_bytes(raw.read_bytes()+b'\nLocal source supplement.\n')
    for rel in ['raw/inbox/local-new.txt','registry/local.yaml','runs/evaluation/local/context.json','eval/local-case.json','.git/local-marker']:
        f=target/rel;f.parent.mkdir(parents=True,exist_ok=True);f.write_text('local content remains')
    preserved={str(f.relative_to(target)):f.read_bytes() for top in ['model','raw','registry','runs','eval','.git'] for f in (target/top).rglob('*') if f.is_file()}
    spec=importlib.util.spec_from_file_location('release_update',root/'apply_update.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    first=mod.apply(root,target)
    assert all((target/rel).read_bytes()==data for rel,data in preserved.items())
    second=mod.apply(root,target);assert second['created']==second['updated']==0
    assert (target/'VERSION').read_text().strip()=='1.5.0' and (target/'AGENTS.md').is_file()
    assert cli(target,'tools')['operations']==contract['operations']
    rows=cli(target,'sources.list')['items'];assert any(r['path']==str(raw.relative_to(target)) and r['processing']=='needs_update' for r in rows)
    result={'ok':True,'manifest_verified_files':len(lines),'no_duplicate_entries':True,'no_cache_or_write_lock':True,'extracted_cli_operations':17,'extracted_sources':50,'from':'1.4.0','to':'1.5.0','first_apply':first,'second_apply':second,'preserved_local_files':len(preserved),'updated_source_detected':True}
Path(args.report).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))
