"""入栏溢出策略：双写两轨的切流裁决与只读归档账册。

工程形态（两案合一）：
- 切流账册：超容点不进现行入栏缓冲，改写只读「溢出归档」，钉死 sha256 指纹，
  归档无任何回刷路径，重发同号报文由幂等驳回（拒回刷超容入现行）。
- 双写两轨：溢出点只在只读归档，现行缓冲只读容限内集；两轨读引用不同、不相交。
- 裁决纪律：容限读取与命运写入须在同一 BEGIN IMMEDIATE 事务内同成败。
"""
from __future__ import annotations
import hashlib
from app.db import 连接

NAME = "入栏溢出策略"
STRATEGY = "双写两轨·切流归档"
溢出原因 = "入栏容限溢出"
溢出命运 = "已溢出"


def 取容限(规: dict) -> int | None:
    """栏规未设容限或非正数 → 不启用，基线 happy path 不受影响。"""
    原 = (规 or {}).get("入栏容限")
    if 原 in (None, ""):
        return None
    try:
        n = int(float(原))
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def 指纹(行: dict) -> str:
    """溢出指纹：报文关键面的 sha256，归档钉痕、可复算。"""
    面 = "|".join(str(行[k]) for k in ("报文编号", "站点键", "指标键", "读数", "观测时", "栏号"))
    return hashlib.sha256(面.encode("utf-8")).hexdigest()[:16]


def 裁决(conn, 栏号: str, 规: dict) -> tuple[bool, int | None, int]:
    """同事务内读水位裁决：返回 (是否可入现行, 容限, 当前在栏数)。

    必须由调用方在 BEGIN IMMEDIATE 事务内调用，使读容限与写命运同成败。
    """
    容限 = 取容限(规)
    在栏数 = conn.execute(
        "SELECT COUNT(*) AS c FROM 入栏缓冲 WHERE 栏号=? AND 命运='在栏'", (栏号,)
    ).fetchone()["c"]
    if 容限 is None:
        return True, None, 在栏数
    return 在栏数 < 容限, 容限, 在栏数


def 归档写(conn, ev: dict, 栏号: str, 批次: str, 时刻: str) -> dict:
    """切流：把超容点写入只读归档账册（同一写事务内）。"""
    行 = {
        "报文编号": ev["报文编号"],
        "站点键": ev["站点键"],
        "指标键": ev["指标键"],
        "读数": float(ev["读数"]),
        "观测时": ev["观测时"],
        "栏号": 栏号,
    }
    痕 = 指纹(行)
    conn.execute(
        """INSERT INTO 溢出归档(报文编号,站点键,指标键,读数,观测时,栏号,原因,指纹,批次编号,归档时)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (行["报文编号"], 行["站点键"], 行["指标键"], 行["读数"], 行["观测时"],
         栏号, 溢出原因, 痕, 批次, 时刻),
    )
    return {"指纹": 痕, **行}


def 归档列表(限制: int = 200) -> list[dict]:
    conn = 连接()
    try:
        return [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM 溢出归档 ORDER BY 归档时 DESC, 报文编号 LIMIT ?", (限制,)
            ).fetchall()
        ]
    finally:
        conn.close()


def 水位对账(conn=None) -> dict:
    """水位与旁路同票：入流总去向 = 在栏 + 已汇总 + 坏点 + 溢出。"""
    自有 = conn is None
    if 自有:
        conn = 连接()
    try:
        入流 = conn.execute("SELECT COUNT(*) AS c FROM 观测报文").fetchone()["c"]
        在栏 = conn.execute(
            "SELECT COUNT(*) AS c FROM 入栏缓冲 WHERE 命运='在栏'"
        ).fetchone()["c"]
        已汇总 = conn.execute(
            "SELECT COUNT(*) AS c FROM 入栏缓冲 WHERE 命运='已汇总'"
        ).fetchone()["c"]
        坏点 = conn.execute("SELECT COUNT(*) AS c FROM 坏点匣").fetchone()["c"]
        溢出数 = conn.execute("SELECT COUNT(*) AS c FROM 溢出归档").fetchone()["c"]
        已标溢出 = conn.execute(
            "SELECT COUNT(*) AS c FROM 观测报文 WHERE 命运=?", (溢出命运,)
        ).fetchone()["c"]
        去向 = 在栏 + 已汇总 + 坏点 + 溢出数
        # 两道假绿防线：总账闭合，且归档溢点必须与报文命运同票
        对齐 = (入流 == 去向) and (已标溢出 == 溢出数)
        return {
            "入流": 入流,
            "在栏": 在栏,
            "已汇总": 已汇总,
            "坏点": 坏点,
            "溢出": 溢出数,
            "去向合计": 去向,
            "已标溢出": 已标溢出,
            "是否对齐": bool(对齐),
        }
    finally:
        if 自有:
            conn.close()


def 裁决快照() -> dict:
    """新增溢出裁决只读接口的数据源：策略、水位、对账、归档指纹。"""
    from app.services import 目录
    规 = 目录.栏规()
    容限 = 取容限(规)
    conn = 连接()
    try:
        对账 = 水位对账(conn)
        归档 = [dict(r) for r in conn.execute(
            "SELECT * FROM 溢出归档 ORDER BY 归档时 DESC, 报文编号 LIMIT 200"
        ).fetchall()]
        栏号 = 规.get("当前栏号", "B-demo")
        本栏在栏 = conn.execute(
            "SELECT COUNT(*) AS c FROM 入栏缓冲 WHERE 栏号=? AND 命运='在栏'", (栏号,)
        ).fetchone()["c"]
        return {
            "策略名": NAME,
            "形态": STRATEGY,
            "启用": 容限 is not None,
            "容限": 容限,
            "当前栏号": 栏号,
            "水位": {"在栏": 对账["在栏"], "溢出": 对账["溢出"], "本栏在栏": 本栏在栏},
            "对账": 对账,
            "归档": 归档,
            "可点下一步": (
                "继续装载：容限内入现行，超容点切流进溢出归档"
                if 容限 is not None
                else "栏规未设入栏容限：全部入现行，不触发溢出"
            ),
        }
    finally:
        conn.close()
