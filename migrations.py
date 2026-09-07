"""v41: additive boot migration; destructive reset is ALWAYS explicit and backed up."""
import hashlib
from pathlib import Path
import re
import sqlite3
import secrets

import config
import countries
import db
from game import notifications, rewards

VERSION='v41-campaigns'


@db.atomic
def upgrade_current():
    if db.one('SELECT 1 FROM schema_versions WHERE version=?',(VERSION,)):
        return False
    # Older versions marked every member as a leader. Keep all players, one leader per country.
    for r in db.q("SELECT DISTINCT country FROM users WHERE country IS NOT NULL AND country<>''"):
        cid=r['country']
        if cid not in countries.COUNTRIES:continue
        lead=db.one('SELECT uid FROM users WHERE country=? ORDER BY is_leader DESC,last_active DESC,uid LIMIT 1',(cid,))
        db.ex('UPDATE users SET is_leader=CASE WHEN uid=? THEN 1 ELSE 0 END WHERE country=?',(lead['uid'],cid))
        db.ex('INSERT OR REPLACE INTO country_claims(country,uid,claimed) VALUES(?,?,?)',(cid,lead['uid'],db.now()))
    db.ex('DELETE FROM alliances WHERE rowid NOT IN (SELECT MIN(rowid) FROM alliances GROUP BY MIN(a,b),MAX(a,b))')
    db.ex('INSERT INTO schema_versions(version,applied) VALUES(?,?)',(VERSION,db.now()))
    db.audit('schema_upgrade',version=VERSION)
    return True


def run_all():
    for gid in db.list_games():
        with db.world(gid):
            countries.init_items()
            upgrade_current()
            notifications.recover()
    # No country assignments, no gifts and NO reset merely by restarting the bot.


def backup_world(game_id,reset_id):
    path=Path(db.game_path(game_id))
    if not path.is_file():raise FileNotFoundError('target game database is missing')
    folder=Path(config.BACKUP_DIR)
    folder.mkdir(parents=True,exist_ok=True)
    backup=folder/f'{game_id}-{reset_id}-{db.now()}.sqlite3'
    if backup.exists():raise FileExistsError('backup already exists')
    source=db.con_for(game_id)
    if source.in_transaction:raise RuntimeError('backup must precede the reset transaction')
    with sqlite3.connect(backup) as dest:
        source.backup(dest)
        if dest.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
            raise RuntimeError('backup integrity check failed')
    digest=hashlib.sha256(backup.read_bytes()).hexdigest()
    return str(backup),digest


def reset_game(game_id,reset_id,*,confirmed=False,special_rewards=False):
    game_id=int(game_id)
    if not confirmed:raise PermissionError('explicit reset confirmation required')
    if game_id>=0 or not re.fullmatch(r'[A-Za-z0-9_-]{1,60}',reset_id):raise ValueError('invalid reset scope')
    if not Path(db.game_path(game_id)).is_file():raise FileNotFoundError('target database does not exist')
    with db.world(game_id):
        if db.one('SELECT 1 FROM reset_history WHERE reset_id=?',(reset_id,)):
            return {'changed':False,'reason':'already applied','game':game_id}
        backup,digest=backup_world(game_id,reset_id)
        with db.transaction():
            if db.one('SELECT 1 FROM reset_history WHERE reset_id=?',(reset_id,)):
                return {'changed':False,'reason':'already applied','game':game_id}
            preserve={r['k']:r['v'] for r in db.q("SELECT k,v FROM kv WHERE k IN ('bl_off','ev_off','main_group')")}
            for table in ('reward_stock','naval_escorts','voyages','tankers','strait_closures','city_energy','un_votes','un_resolutions','operation_plans','missile_launches','inventory','missions','sieges','campaigns','wars','alliances','country_claims',
                          'statements','parties','spyops','defense','structures','city_state','news','invest_accrual','outbox'):
                db.ex(f'DELETE FROM {table}')
            db.ex('UPDATE users SET country=NULL,is_leader=0,branch=NULL,rank=1,xp=0,level=1,money=1000,hp=100,max_hp=100,kills=0,spy_ops=0,party_id=NULL')
            db.ex('DELETE FROM kv')
            for k,v in preserve.items():db.kv_set(k,v)
            db.kv_set('season_epoch',secrets.token_hex(3))
            db.kv_set('current_season',reset_id)
            db.ex('INSERT INTO reset_history(reset_id,game_id,applied,backup_path,backup_sha256) VALUES(?,?,?,?,?)',(reset_id,game_id,db.now(),backup,digest))
            if special_rewards:rewards.schedule()
            db.audit('season_reset',config.OWNER_ID,game=game_id,season=reset_id,backup_sha256=digest)
            everyone=[r['uid'] for r in db.q('SELECT uid FROM users ORDER BY uid')]
            msg='🔄 <b>فصل تازهٔ دارک‌زون</b>\nهمهٔ حساب‌ها، حتی مالک و رهبر قبلی آمریکا، اکنون بدون کشورند. کشورها از «شروع» دوباره انتخاب می‌شوند.\nجنگ‌ها، مستعمره‌ها، تجهیزات، شهرها و پایگاه‌ها از نو شروع شدند؛ نام و شناسهٔ حساب حفظ شد.'
            if special_rewards:
                msg+='\n🎁 پاداش همگانی ۳۰٬۰۰۰ دلار؛ آیدی مشخص‌شدهٔ آمریکا مجموعاً ۸۰٬۰۰۰ + ۵ تجهیز و بهترین پدافند؛ آیدی مالک ایران مجموعاً ۹۰٬۰۰۰ + ۱۰ تجهیز. مبالغ جدید جایگزین وعدهٔ نقدی قبلی‌اند و فقط پس از انتخاب کشور صحیح یک بار واریز می‌شوند. هنوز پرداخت نشده است.'
            notifications.emit(msg,uids=everyone,key=f'reset:{reset_id}')
            return {'changed':True,'game':game_id,'backup':backup,'sha256':digest,'users_without_country':len(everyone)}
