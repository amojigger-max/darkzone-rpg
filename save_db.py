"""💾 ذخیره‌ی worldwar.db در گیت‌هاب از طریق API.

چرا API و نه git push؟ رانرِ گیت‌هاب روی detached HEAD است و pull/push
دردسر دارد؛ Contents API اتمیک و بدون وضعیت git است — همیشه کار می‌کند.
"""
import base64
import json
import os
import sqlite3
import urllib.request

REPO = "amojigger-max/darkzone-rpg"
PATH = os.environ.get("DZ_DB", "worldwar.db")
API = f"https://api.github.com/repos/{REPO}/contents/{PATH}"


def checkpoint() -> bytes:
    """WAL را در فایل اصلی ادغام کن و محتوای db را برگردان."""
    con = sqlite3.connect(PATH)
    con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    con.close()
    with open(PATH, "rb") as f:
        return f.read()


def put(pat: str, data: bytes = None) -> bool:
    """فایل db را در main ذخیره کن (ایجاد یا به‌روزرسانی)."""
    if data is None:
        data = checkpoint()
    hdr = {"Authorization": f"token {pat}",
           "Accept": "application/vnd.github+json"}
    sha = None
    try:
        with urllib.request.urlopen(
                urllib.request.Request(API, headers=hdr), timeout=30) as r:
            sha = json.load(r).get("sha")
    except Exception:
        pass                                   # هنوز در ریپو نیست — ایجاد
    body = json.dumps({"message": "autosave db [skip ci]", "branch": "main",
                       "content": base64.b64encode(data).decode(),
                       **({"sha": sha} if sha else {})}).encode()
    req = urllib.request.Request(API, data=body, method="PUT", headers=hdr)
    with urllib.request.urlopen(req, timeout=30) as r:
        return 200 <= r.status < 300


if __name__ == "__main__":
    import sys
    pat = os.environ.get("PAT") or (sys.argv[1] if len(sys.argv) > 1 else "")
    if not pat:
        print("PAT لازم است"); raise SystemExit(1)
    try:
        print("db saved ✓" if put(pat) else "db save FAILED")
    except Exception as e:
        print("db save FAILED:", e); raise SystemExit(1)
