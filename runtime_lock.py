"""One local writer per canonical data directory (POSIX deployments)."""
from contextlib import contextmanager
from pathlib import Path
import fcntl
import db


@contextmanager
def exclusive():
    root=Path(db.GAMES_DIR).resolve();root.mkdir(parents=True,exist_ok=True)
    handle=open(root/'.runner.lock','a')
    try:
        try:fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise RuntimeError('runner is active for this data directory; stop it before maintenance') from None
        yield
    finally:handle.close()
