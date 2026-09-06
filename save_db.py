"""💾 ذخیره‌ی دنیاهای گروه‌ها در گیت‌هاب از طریق API.

چرا API و نه git push؟ رانرِ گیت‌هاب روی detached HEAD است و pull/push
دردسر دارد؛ Contents API اتمیک و بدون وضعیت git است — همیشه کار می‌کند.
"""
import base64
import json
import os
import sqlite3
import urllib.request

REPO = "amojigger-max/darkzone-rpg"
API = f"https://api.github.com/repos/{REPO}/contents/"


def checkpoint(path: str = None) -> bytes:
    """WAL را در فایل اصلی ادغام کن و محتوای db را برگردان."""
    path = path or os.environ.get("DZ_DB", "worldwar.db")
    con = sqlite3.connect(path)
    con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    con.close()
    with open(path, "rb") as f:
        return f.read()


def put(pat: str, data: bytes = None, path: str = "worldwar.db") -> bool:
    """فایل db را در main ذخیره کن (ایجاد یا به‌روزرسانی)."""
    if data is None:
        data = checkpoint(path)
    api = API + path
    hdr = {"Authorization": f"token {pat}",
           "Accept": "application/vnd.github+json"}
    sha = None
    try:
        with urllib.request.urlopen(
                urllib.request.Request(api, headers=hdr), timeout=30) as r:
            sha = json.load(r).get("sha")
    except Exception:
        pass                                   # هنوز در ریپو نیست — ایجاد
    body = json.dumps({"message": "autosave db [skip ci]", "branch": "main",
                       "content": base64.b64encode(data).decode(),
                       **({"sha": sha} if sha else {})}).encode()
    req = urllib.request.Request(api, data=body, method="PUT", headers=hdr)
    with urllib.request.urlopen(req, timeout=30) as r:
        return 200 <= r.status < 300


def save_all(pat: str) -> int:
    """همه‌ی دنیاهای گروه‌ها را ذخیره کن — تعداد موفق را برگردان."""
    import db
    ok = 0
    for g in db.list_games():
        try:
            if put(pat, checkpoint(db.game_path(g)), db.game_path(g)):
                ok += 1
        except Exception as e:
            print("save failed", g, e)
    return ok


if __name__ == "__main__":
    import sys
    pat = os.environ.get("PAT") or (sys.argv[1] if len(sys.argv) > 1 else "")
    if not pat:
        print("PAT لازم است"); raise SystemExit(1)
    n = save_all(pat)
    print(f"saved {n} world(s)")
    raise SystemExit(0 if n >= 0 else 1)
