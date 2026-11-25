import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

数据目录 = Path(os.environ.get("数据目录", Path(__file__).resolve().parent.parent / "data"))
夹具目录 = Path(os.environ.get("夹具目录", Path(__file__).resolve().parent.parent.parent / "fixtures"))
库路径 = 数据目录 / "探栏.db"

# 临界两路同灌时，第二路在 RESERVED 锁上重试到超时，而不是立即 SQLITE_BUSY
锁等待毫秒 = 5000


def 连接() -> sqlite3.Connection:
    数据目录.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(库路径, timeout=锁等待毫秒 / 1000)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    c.execute(f"PRAGMA busy_timeout = {锁等待毫秒}")
    return c


@contextmanager
def 写事务():
    """即时锁写事务：BEGIN IMMEDIATE 先拿 RESERVED 锁。

    读容限与写命运在同一事务内同成败；并发装载/结栏被强制串行裁决，
    杜绝两路同读一个水位后双突破。
    """
    conn = 连接()
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
