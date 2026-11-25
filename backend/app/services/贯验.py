"""栏贯验：已汇总缓冲报文数 == 汇总账报文数之和；旁路溢出同票对账。"""
from __future__ import annotations
from app.db import 连接
from app.seed import 此刻
from app.services import 溢出


def _口径(conn) -> dict:
    在栏 = conn.execute(
        "SELECT COUNT(*) AS c FROM 入栏缓冲 WHERE 命运='在栏'"
    ).fetchone()["c"]
    已汇总缓冲 = conn.execute(
        "SELECT COUNT(*) AS c FROM 入栏缓冲 WHERE 命运='已汇总'"
    ).fetchone()["c"]
    汇总报文 = conn.execute(
        "SELECT COALESCE(SUM(报文数),0) AS c FROM 站点汇总账"
    ).fetchone()["c"]
    坏点 = conn.execute("SELECT COUNT(*) AS c FROM 坏点匣").fetchone()["c"]
    对账 = 溢出.水位对账(conn)
    溢出数 = 对账["溢出"]
    账对齐 = int(已汇总缓冲) == int(汇总报文)
    # 强对账：原栏账互证不放松，另加入流闭合与溢点命运同票，假绿无处藏
    对齐 = 1 if (账对齐 and 对账["是否对齐"]) else 0
    if 对齐:
        说明 = "入栏已汇总与站点汇总报文数一致；入流四轨闭合，溢点命运同票"
    elif not 账对齐:
        说明 = f"撕裂：已汇总缓冲={已汇总缓冲} 汇总报文={汇总报文}"
    else:
        说明 = (
            f"水位撕裂：入流={对账['入流']} 去向合计={对账['去向合计']} "
            f"归档={溢出数} 已标溢出={对账['已标溢出']}"
        )
    return {
        "在栏": 在栏,
        "已汇总缓冲": int(已汇总缓冲),
        "汇总报文": int(汇总报文),
        "坏点": 坏点,
        "溢出": 溢出数,
        "对齐": 对齐,
        "说明": 说明,
    }


def 跑一次() -> dict:
    conn = 连接()
    try:
        k = _口径(conn)
        时刻 = 此刻()
        conn.execute(
            """INSERT INTO 栏贯验(时刻,在栏笔数,汇总报文数,坏点笔数,是否对齐,说明,溢出数)
               VALUES (?,?,?,?,?,?,?)""",
            (时刻, k["在栏"], k["汇总报文"], k["坏点"], k["对齐"], k["说明"], k["溢出"]),
        )
        conn.commit()
        return {
            "时刻": 时刻,
            "在栏": k["在栏"],
            "已汇总缓冲": k["已汇总缓冲"],
            "汇总报文": k["汇总报文"],
            "坏点": k["坏点"],
            "溢出": k["溢出"],
            "是否对齐": bool(k["对齐"]),
            "说明": k["说明"],
        }
    finally:
        conn.close()


def 只读快照() -> dict:
    """不落库的贯验快照，供页面预览。"""
    conn = 连接()
    try:
        k = _口径(conn)
        return {
            "在栏": k["在栏"],
            "已汇总缓冲": k["已汇总缓冲"],
            "汇总报文": k["汇总报文"],
            "坏点": k["坏点"],
            "溢出": k["溢出"],
            "是否对齐": bool(k["对齐"]),
            "说明": k["说明"],
        }
    finally:
        conn.close()
