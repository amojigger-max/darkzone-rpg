import io
import json
from pathlib import Path
import sqlite3
import pytest
import db
import config
import save_db


@pytest.fixture(autouse=True)
def revisions():
    save_db._EXPECTED.clear()
    yield
    save_db._EXPECTED.clear()


def database(path,value=1):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect(p);c.execute('CREATE TABLE content(value INTEGER)');c.execute('INSERT INTO content VALUES(?)',(value,));c.commit();c.close()
    return p.read_bytes()


def test_prime_verifies_actual_bytes_not_a_plausible_git_revision(tmp_path,monkeypatch):
    local=tmp_path/'stale.db';database(local,1)
    latest=database(tmp_path/'latest.db',2)
    monkeypatch.setattr(save_db,'_sha',lambda *args:save_db.blob_sha(latest))
    with pytest.raises(save_db.SaveConflict,match='does not match'):save_db.prime('FAKE',{'games/-1.db':local})
    assert not save_db._EXPECTED
    assert not save_db._revisions_path().exists()


def test_matching_download_without_git_metadata_is_accepted(tmp_path,monkeypatch):
    local=tmp_path/'download.db';raw=database(local,7)
    sha=save_db.blob_sha(raw);monkeypatch.setattr(save_db,'_sha',lambda *args:sha)
    save_db.prime('FAKE',{'games/-1.db':local})
    assert local.read_bytes()==raw
    assert save_db._EXPECTED=={'games/-1.db':sha}
    meta=json.loads(save_db._revisions_path().read_text())
    assert meta['format']==2 and meta['repository']==save_db.REPO and meta['branch']==config.STATE_BRANCH


def test_wal_data_cannot_be_ignored_even_if_main_file_matches(tmp_path,monkeypatch):
    local=tmp_path/'wal.db';database(local)
    c=sqlite3.connect(local);c.execute('PRAGMA journal_mode=WAL');c.execute('UPDATE content SET value=10');c.commit()
    monkeypatch.setattr(save_db,'_sha',lambda *args:save_db.blob_sha(local.read_bytes()))
    with pytest.raises(save_db.SaveConflict,match='WAL'):save_db.prime('FAKE',{'games/-1.db':local})
    c.close()


def test_preflight_rejects_read_only_token_before_creating_revision_metadata(monkeypatch):
    monkeypatch.setattr(save_db,'_read_json',lambda token,url:{'permissions':{'push':False}} if '/branches/' not in url else {'protected':False})
    with pytest.raises(save_db.SaveConflict,match='no write'):save_db.preflight('FAKE',{})
    assert not save_db._revisions_path().exists()


def test_preflight_rejects_protected_state_branch(monkeypatch):
    monkeypatch.setattr(save_db,'_read_json',lambda token,url:{'permissions':{'push':True}} if '/branches/' not in url else {'protected':True})
    with pytest.raises(save_db.SaveConflict,match='protected'):save_db.preflight('FAKE',{})


def test_new_destination_requires_a_valid_database_not_random_bytes(tmp_path,monkeypatch):
    local=tmp_path/'bad.db';local.write_bytes(b'not a sqlite database')
    monkeypatch.setattr(save_db,'_sha',lambda *args:None)
    with pytest.raises(save_db.SaveConflict,match='not a SQLite'):save_db.prime('FAKE',{'games/-1.db':local})


@pytest.mark.parametrize('change',['repository','branch','format'])
def test_final_save_cannot_reuse_foreign_or_legacy_metadata(monkeypatch,change):
    obj={'format':2,'repository':save_db.REPO,'branch':config.STATE_BRANCH,'revisions':{'games/-1.db':'a'*40}}
    obj[change]='other' if change!='format' else 1
    p=save_db._revisions_path();p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj))
    monkeypatch.setattr(save_db,'_sha',lambda *args:'a'*40)
    with pytest.raises(save_db.SaveConflict,match='another source'):save_db.put('FAKE',b'not sent','games/-1.db')


def test_successful_upload_records_verified_content_for_separate_final_save(tmp_path,monkeypatch):
    raw=database(tmp_path/'new.db',8);sha=save_db.blob_sha(raw)
    monkeypatch.setattr(save_db,'_sha',lambda *args:None)
    class Response(io.BytesIO):status=201
    calls=[]
    def request(req,timeout):
        calls.append(req)
        return Response(json.dumps({'content':{'sha':sha}}).encode())
    monkeypatch.setattr(save_db.urllib.request,'urlopen',request)
    assert save_db.put('FAKE',raw,'games/-1.db')
    assert len(calls)==1 and calls[0].get_method()=='PUT'
    save_db._EXPECTED.clear();save_db._restore_revisions()
    assert save_db._EXPECTED['games/-1.db']==sha


def test_mismatched_upload_receipt_is_not_reported_as_success(tmp_path,monkeypatch):
    raw=database(tmp_path/'new.db')
    monkeypatch.setattr(save_db,'_sha',lambda *args:None)
    class Response(io.BytesIO):status=201
    monkeypatch.setattr(save_db.urllib.request,'urlopen',lambda *a,**k:Response(json.dumps({'content':{'sha':'f'*40}}).encode()))
    with pytest.raises(RuntimeError,match='could not be verified'):save_db.put('FAKE',raw,'games/-1.db')
    assert 'games/-1.db' not in save_db._EXPECTED


def test_readonly_snapshot_with_uri_characters_in_path(tmp_path):
    p=tmp_path/'directory & ?'/'input ? file.db';database(p,31)
    raw=save_db.checkpoint(p);c=sqlite3.connect(':memory:');c.deserialize(raw)
    assert c.execute('SELECT value FROM content').fetchone()[0]==31
    c.close()


async def test_startup_preflight_runs_before_any_migration_or_polling(monkeypatch):
    import run
    from runtime_lock import exclusive
    monkeypatch.setattr(config,'TOKEN','123456:OFFLINE_FAKE_TEST_TOKEN')
    monkeypatch.setattr(config,'PAT','FAKE');monkeypatch.setenv('INLOOP_AUTOSAVE','1')
    events=[]
    def fail(*args):events.append('preflight');raise save_db.SaveConflict('stale database')
    monkeypatch.setattr(save_db,'preflight',fail)
    monkeypatch.setattr(run.migrations,'run_all',lambda:events.append('migration'))
    monkeypatch.setattr(run,'Bot',lambda *a,**k:events.append('bot constructed'))
    with pytest.raises(save_db.SaveConflict):await run.main()
    assert events==['preflight']
    with exclusive():pass  # failure did not strand the data-directory lock


async def test_boot_constructor_failure_does_not_strand_local_lock(monkeypatch):
    import run
    from runtime_lock import exclusive
    monkeypatch.setenv('INLOOP_AUTOSAVE','0')
    monkeypatch.setattr(config,'TOKEN','invalid local token')
    def fail(*args,**kwargs):raise ValueError('constructor failure')
    monkeypatch.setattr(run,'Bot',fail)
    with pytest.raises(ValueError):await run.main()
    with exclusive():pass


def test_manual_rollout_has_validation_before_runner_concurrency():
    source=Path('.github/workflows/apply-upgrade.yml').read_text()
    validation=source.split('  validate:',1)[1].split('  apply:',1)[0]
    application=source.split('  apply:',1)[1]
    assert 'concurrency:' not in validation
    assert 'save_db.check_write_access' in validation
    assert 'needs: validate' in application and 'group: worldwar-run' in application
    assert 'secrets.PAT' not in source and 'github.token' in source
