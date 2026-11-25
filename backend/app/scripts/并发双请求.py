"""并发双请求脚本：溢出临界两路同灌的锁纪律实证。

用法（独立库）：
    python -m app.scripts.并发双请求
或：
    python backend/app/scripts/并发双请求.py

断言：两路并发装载后，现行在栏绝不突破容限；超容点全部在只读溢出归档；
双轨不相交；再跑栏贯验必须对齐。
"""
from __future__ import annotations
import os
import sys
import threading
from pathlib import Path

# 允许 `python backend/app/scripts/并发双请求.py` 直接运行
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.db import 库路径  # noqa: E402
from app import seed  # noqa: E402
from app.services import 装载, 目录, 贯验  # noqa: E402
from app.services import 溢出  # noqa: E402


def _报文(n: int) -> dict:
    return {
        "报文编号": f"race-{n}",
        "站点键": "站-河东",
        "指标键": "PM25",
        "读数": 22.0 + (n % 9),
        "观测时": f"2026-11-25T11:{n % 60:02d}:00Z",
    }


def 两路灌(容限: int = 3, 预置: int = 2, 每路: int = 2) -> dict:
    目录.改栏规({"入栏容限": str(容限)})
    if 预置:
        装载.装一批({"批次编号": "race-pre", "报文": [_报文(900 + i) for i in range(预置)]})

    果: list[dict] = []
    锁 = threading.Lock()

    def 灌(seed: int) -> None:
        r = 装载.装一批({
            "批次编号": f"race-t{seed}",
            "报文": [_报文(seed * 100 + j) for j in range(每路)],
        })
        with 锁:
            果.append(r)

    t1 = threading.Thread(target=灌, args=(1,))
    t2 = threading.Thread(target=灌, args=(2,))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    在栏 = [r for r in 目录.缓冲列表() if r["命运"] == "在栏"]
    归档 = 溢出.归档列表()
    验 = 贯验.跑一次()
    裁决 = 溢出.裁决快照()
    return {
        "两路报告": 果,
        "容限": 容限,
        "在栏数": len(在栏),
        "归档数": len(归档),
        "双轨相交": bool({r["报文编号"] for r in 在栏} & {r["报文编号"] for r in 归档}),
        "贯验": 验,
        "裁决": 裁决,
        "库路径": str(库路径),
    }


def main() -> int:
    seed.初始化库()
    r = 两路灌()
    print("== 并发双请求：溢出临界 ==")
    print(f"库: {r['库路径']}")
    for i, rep in enumerate(r["两路报告"], 1):
        print(f"路{i}: 入流={rep['入流']} 入栏={rep['入栏']} 溢出={rep['溢出']} 驳回={rep['驳回']}")
    print(f"容限={r['容限']} 在栏={r['在栏数']} 归档={r['归档数']} 双轨相交={r['双轨相交']}")
    print(f"贯验: 对齐={r['贯验']['是否对齐']} 溢出={r['贯验']['溢出']} · {r['贯验']['说明']}")
    守住 = (
        r["在栏数"] <= r["容限"]
        and not r["双轨相交"]
        and r["贯验"]["是否对齐"]
        and r["裁决"]["对账"]["是否对齐"]
    )
    print("结果:", "守住容限，无双突破" if 守住 else "失败：双突破或撕裂")
    return 0 if 守住 else 1


if __name__ == "__main__":
    raise SystemExit(main())
