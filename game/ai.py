"""Retained news API. There are no NPC governments, armies, rivals or counterattacks."""
import db
import texts


def news_add(text):
    with db.transaction():
        db.ex('INSERT INTO news(text,ts) VALUES(?,?)',(text,db.now()))
        db.ex('DELETE FROM news WHERE id NOT IN (SELECT id FROM news ORDER BY id DESC LIMIT 40)')


def news_feed():
    rows=db.q('SELECT text FROM news ORDER BY id DESC LIMIT 5')
    return texts.hdr('اخبار جهان','📰')+'\n\n'+'\n\n'.join(r['text'] for r in rows) if rows else texts.hdr('اخبار جهان','📰')+'\nهنوز رویدادی ثبت نشده است.'


def tick():
    return []


def respond_to_strike(attacker,defender,kind,hit):
    return []
