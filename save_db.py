"""Verified SQLite snapshots and fail-closed optimistic GitHub saves.

Preflight compares the actual local file to the remote blob BEFORE SQLite/migrations
can modify it. A plausible Git HEAD alone does not prove that local data is current.
"""
import base64
import hashlib
import json
import os
from pathlib import Path,PurePosixPath
import re
import sqlite3
import urllib.error
import urllib.parse
import urllib.request

import config

REPO=config.REPO
API=f'https://api.github.com/repos/{REPO}/contents/'
_EXPECTED={}
MAX_SNAPSHOT_BYTES=95*1024*1024


class SaveConflict(RuntimeError):pass


def _revisions_path():
    import db
    return Path(db.GAMES_DIR)/'_save_revisions.json'


def _remember():
    p=_revisions_path();p.parent.mkdir(parents=True,exist_ok=True)
    obj={'format':2,'repository':REPO,'branch':config.STATE_BRANCH,'revisions':_EXPECTED}
    tmp=p.with_suffix('.tmp')
    with tmp.open('w') as f:
        json.dump(obj,f,sort_keys=True);f.flush();os.fsync(f.fileno())
    os.chmod(tmp,0o600);tmp.replace(p)


def _restore_revisions():
    p=_revisions_path()
    if not p.is_file():return
    try:obj=json.loads(p.read_text())
    except (ValueError,OSError):raise SaveConflict('invalid saved revision metadata; run verified preflight') from None
    if not isinstance(obj,dict) or obj.get('format')!=2 or obj.get('repository')!=REPO or obj.get('branch')!=config.STATE_BRANCH:
        raise SaveConflict('revision metadata belongs to another source/branch or is unverified')
    revisions=obj.get('revisions')
    if not isinstance(revisions,dict):raise SaveConflict('invalid revision map')
    for path,sha in revisions.items():
        _remote(path)
        if sha is not None and (not isinstance(sha,str) or not re.fullmatch('[a-f0-9]{40}',sha)):
            raise SaveConflict('invalid stored blob revision')
    _EXPECTED.update(revisions)


def blob_sha(data):
    return hashlib.sha1(f'blob {len(data)}\0'.encode()+data).hexdigest()


def _sqlite_uri(path,immutable=False):
    return 'file:'+urllib.parse.quote(str(Path(path).resolve()),safe='/')+'?mode=ro'+('&immutable=1' if immutable else '')


def checkpoint(path=None):
    import tempfile
    path=path or config.DB_PATH
    if not Path(path).is_file():raise FileNotFoundError('snapshot source is missing')
    source=sqlite3.connect(_sqlite_uri(path),uri=True,timeout=30)
    try:
        with tempfile.TemporaryDirectory(prefix='darkzone-snapshot-') as folder:
            output=Path(folder)/'snapshot.db';dest=sqlite3.connect(output)
            try:
                source.backup(dest);dest.execute('PRAGMA journal_mode=DELETE')
                if dest.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise RuntimeError('snapshot failed integrity check')
                dest.commit()
            finally:dest.close()
            return output.read_bytes()
    finally:source.close()


def _headers(pat):
    if not pat:raise ValueError('GitHub write token is required when cloud autosave is enabled')
    return {'Authorization':f'Bearer {pat}','Accept':'application/vnd.github+json','User-Agent':'DarkZone-v41'}


def _remote(path):
    if not isinstance(path,str):raise ValueError('invalid remote database path')
    p=PurePosixPath(path)
    if p.is_absolute() or '..' in p.parts or not str(p).endswith('.db'):raise ValueError('invalid remote database path')
    return str(p)


def _read_json(pat,url):
    req=urllib.request.Request(url,headers=_headers(pat))
    with urllib.request.urlopen(req,timeout=30) as response:return json.load(response)


def _sha(pat,path):
    try:
        return _read_json(pat,API+urllib.parse.quote(path,safe='/')+'?ref='+urllib.parse.quote(config.STATE_BRANCH,safe=''))['sha']
    except urllib.error.HTTPError as exc:
        if exc.code==404:return None
        raise RuntimeError(f'GitHub metadata request failed ({exc.code})') from None


def check_write_access(pat):
    base=f'https://api.github.com/repos/{REPO}'
    try:
        repo=_read_json(pat,base)
        branch=_read_json(pat,base+'/branches/'+urllib.parse.quote(config.STATE_BRANCH,safe=''))
    except urllib.error.HTTPError as exc:raise SaveConflict(f'cannot verify writable state destination ({exc.code})') from None
    if repo.get('archived') or not repo.get('permissions',{}).get('push'):
        raise SaveConflict('repository token has no write permission; refusing unsavable polling')
    if branch.get('protected'):
        raise SaveConflict('state branch is protected; use an explicitly configured unprotected state branch with current local snapshots')


def prime(pat,paths):
    """Verify pristine local snapshots. Call BEFORE db.init or migrations."""
    sources=paths if isinstance(paths,dict) else {path:path for path in paths}
    verified={}
    for remote_path,local_path in sources.items():
        remote_path=_remote(remote_path);local=Path(local_path)
        if not local.is_file():raise SaveConflict('local database missing during preflight')
        wal=Path(str(local)+'-wal')
        if wal.exists() and wal.stat().st_size:
            raise SaveConflict('uncheckpointed local WAL exists; back up and reconcile local state before cloud polling')
        raw=local.read_bytes()
        if not raw.startswith(b'SQLite format 3\0'):raise SaveConflict('local file is not a SQLite database')
        remote=_sha(pat,remote_path)
        if remote is not None and blob_sha(raw)!=remote:
            raise SaveConflict('local database does not match the latest remote snapshot; refusing a stale overwrite')
        con=sqlite3.connect(_sqlite_uri(local,immutable=True),uri=True)
        try:
            if con.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise SaveConflict('local snapshot is corrupt')
        finally:con.close()
        verified[remote_path]=remote
    _EXPECTED.clear();_EXPECTED.update(verified);_remember()


def preflight(pat,paths):
    check_write_access(pat);prime(pat,paths)


def put(pat,data=None,path='worldwar.db'):
    path=_remote(path)
    if data is None:data=checkpoint(path)
    current=_sha(pat,path)
    if path not in _EXPECTED:
        _restore_revisions()
        if path not in _EXPECTED and current is not None:
            raise SaveConflict('untracked existing remote database; verified preflight is required')
    if path in _EXPECTED and _EXPECTED[path]!=current:
        raise SaveConflict('remote database changed; refusing to overwrite another runner')
    if not isinstance(data,bytes) or not data.startswith(b'SQLite format 3\0'):raise ValueError('snapshot payload is not SQLite')
    if len(data)>MAX_SNAPSHOT_BYTES:raise ValueError('snapshot too large for GitHub backup; use durable database storage')
    expected_new=blob_sha(data)
    payload={'message':'autosave v41 database [skip ci]','branch':config.STATE_BRANCH,'content':base64.b64encode(data).decode()}
    if current:payload['sha']=current
    req=urllib.request.Request(API+urllib.parse.quote(path,safe='/'),data=json.dumps(payload).encode(),method='PUT',headers=_headers(pat))
    try:
        with urllib.request.urlopen(req,timeout=45) as response:
            result=json.load(response)
            if not 200<=response.status<300 or result.get('content',{}).get('sha')!=expected_new:
                raise RuntimeError('saved content could not be verified; not reporting success')
            _EXPECTED[path]=expected_new;_remember();return True
    except urllib.error.HTTPError as exc:
        if exc.code in (409,422):raise SaveConflict('remote write conflict; no blind retry') from None
        raise RuntimeError(f'GitHub save failed ({exc.code}); not saved') from None


def save_all(pat):
    import db
    failures=[];saved=0
    for gid in db.list_games():
        try:
            data=checkpoint(db.game_path(gid));put(pat,data,f'games/{gid}.db');saved+=1
        except Exception as exc:failures.append((gid,type(exc).__name__))
    if failures:raise RuntimeError(f'{len(failures)} world save(s) failed: {failures}')
    return saved


if __name__=='__main__':
    try:print(f"saved {save_all(os.environ.get('PAT',''))} world(s)")
    except Exception as exc:
        print(type(exc).__name__+': '+str(exc));raise SystemExit(1)
