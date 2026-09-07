"""Per-world transactional outbox. A grant commits even if Telegram is unavailable.

Delivery is at-most-once on ambiguous network failures: mark UNKNOWN for operator
review instead of falsely claiming success or automatically duplicating a notice.
Telegram has no idempotency key for sendMessage; exactly-once delivery is not claimed.
"""
import asyncio
import re
import uuid

import db
import texts
from htmlsafe import split_html


def player_ids(cids=None):
    if cids is None:
        return [r['uid'] for r in db.q("SELECT uid FROM users WHERE country IS NOT NULL AND country<>'' ORDER BY uid")]
    cids = tuple(dict.fromkeys(cids))
    if not cids:
        return []
    return [r['uid'] for r in db.q(f"SELECT uid FROM users WHERE country IN ({','.join('?' for _ in cids)}) ORDER BY uid", cids)]


def with_tags(body, uids):
    present = {int(x) for x in re.findall(r'tg://user\?id=(\d+)', body)}
    links = []
    for uid in dict.fromkeys(uids):
        if uid in present:
            continue
        row = db.one('SELECT name FROM users WHERE uid=?', (uid,))
        links.append(texts.mention(uid, row['name'] if row else str(uid)))
        present.add(uid)
    return body + ('\n\n📣 ' + ' '.join(links) if links else '')


@db.atomic
def emit(body, *, cids=(), uids=(), key=None, all_players=False, chat_id=None):
    chat_id = db.GAME.get() if chat_id is None else chat_id
    if chat_id is None or int(chat_id) >= 0:
        return []  # isolated unit tests do not produce real messages
    recipients = player_ids(None if all_players else cids) + list(uids)
    body = with_tags(body, recipients)
    event = key or uuid.uuid4().hex
    ids=[]
    for i, part in enumerate(split_html(body)):
        inserted=db.ex('INSERT OR IGNORE INTO outbox(event_key,chat_id,body,created) VALUES(?,?,?,?)',
              (f'{event}:{i}', chat_id, part, db.now()))
        if i==0 and inserted.rowcount==1:
            db.ex('INSERT INTO news(text,ts) VALUES(?,?)',(body,db.now()))
            db.ex('DELETE FROM news WHERE id NOT IN (SELECT id FROM news ORDER BY id DESC LIMIT 200)')
        ids.append(db.one('SELECT id FROM outbox WHERE event_key=?', (f'{event}:{i}',))['id'])
    return ids


def personal(uid, body):
    return with_tags(body, [uid])


@db.atomic
def _claim():
    row = db.one("SELECT * FROM outbox WHERE status='pending' AND next_at<=? ORDER BY id LIMIT 1", (db.now(),))
    if not row:
        return None
    db.ex("UPDATE outbox SET status='sending', attempts=attempts+1 WHERE id=? AND status='pending'", (row['id'],))
    return dict(row)


async def drain(bot, limit=8):
    from aiogram.exceptions import TelegramRetryAfter, TelegramBadRequest, TelegramForbiddenError
    sent=0
    for _ in range(limit):
        row=_claim()
        if not row:
            break
        try:
            result=await bot.send_message(row['chat_id'], row['body'], parse_mode='HTML')
        except TelegramRetryAfter as exc:
            db.ex("UPDATE outbox SET status='pending', next_at=?, error='rate limited' WHERE id=?",
                  (db.now()+int(exc.retry_after)+1, row['id']))
            break
        except (TelegramBadRequest, TelegramForbiddenError) as exc:
            db.ex("UPDATE outbox SET status='blocked', error=? WHERE id=?", (type(exc).__name__,row['id']))
        except asyncio.CancelledError:
            db.ex("UPDATE outbox SET status='unknown', error='shutdown during send' WHERE id=?", (row['id'],))
            raise
        except Exception as exc:
            db.ex("UPDATE outbox SET status='unknown', error=? WHERE id=?", (type(exc).__name__,row['id']))
        else:
            db.ex("UPDATE outbox SET status='sent', message_id=?, sent_at=?, error='' WHERE id=?",
                  (result.message_id, db.now(),row['id']))
            sent+=1
    return sent


@db.atomic
def recover():
    db.ex("UPDATE outbox SET status='unknown', error='interrupted send; review required' WHERE status='sending'")


def status():
    rows=db.q('SELECT status,COUNT(*) n FROM outbox GROUP BY status')
    return texts.hdr('وضعیت اعلان‌ها','📣')+'\n'+'\n'.join(f"{r['status']}: {r['n']}" for r in rows)


class NewsQueue:
    """Compatibility adapter for retained politics/welfare code; no process-global queue."""
    def append(self, body):
        emit(body, all_players=True)
    def pop(self, index=0):
        return ''
    def clear(self):
        # Never discard persisted pending notices through a legacy UI hook.
        return None
    def __bool__(self):
        return False
