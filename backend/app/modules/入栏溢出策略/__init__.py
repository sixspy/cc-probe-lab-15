"""入栏溢出策略（已落地）：双写两轨·切流归档。

契约：
- 入栏条数超阈不拒装、不静默丢：超容点切流进只读「溢出归档」，钉 sha256 指纹。
- 现行入栏缓冲只读容限内集，永不破容；归档无回刷路径，重发走幂等驳回。
- 读容限与写命运在同一 BEGIN IMMEDIATE 事务内同成败；装载/结栏同锁纪律，
  临界两路并发只串行裁决，不双突破。
- 不改基线默认门槛 happy path：未设「入栏容限」时全部入现行。
- 页面须能读到：当前策略名、命运变化、可点的下一步（GET /api/溢出裁决）。
"""
from app.services import 溢出 as _服务

NAME = "入栏溢出策略"
CONTRACT = "入栏条数超阈切流进只读归档，现行缓冲只读容限内集"
HOOKS = ("before_load", "after_load", "decide_gate", "before_close", "after_close", "extra_verify_checks")


def describe() -> dict:
    return {
        "策略": NAME,
        "形态": _服务.STRATEGY,
        "契约": CONTRACT,
        "钩子": list(HOOKS),
        "默认启用": False,
        "启用条件": "栏规设置正数「入栏容限」",
        "旁路表": "溢出归档（只读，钉指纹，不回刷）",
        "只读接口": "/api/溢出裁决",
    }


def before_load(batch: dict) -> dict:
    return batch


def after_load(report: dict) -> dict:
    # 命运变化显式化：报告须带溢出口径，缺失则补零防假绿
    report.setdefault("溢出", 0)
    return report


def decide_gate(event: dict, rules: dict) -> str:
    """只表达策略语义；真实裁决在装载写事务内按实时水位执行。"""
    if _服务.取容限(rules) is None:
        return "入栏"
    return "入栏或溢出-按容限实时裁决"


def before_close(pen_id: str) -> None:
    return None


def after_close(report: dict) -> dict:
    return report


def extra_verify_checks(snapshot: dict) -> list[str]:
    问题 = []
    对账 = (snapshot or {}).get("对账")
    if 对账 and not 对账.get("是否对齐"):
        问题.append(
            f"溢出水位撕裂：入流={对账.get('入流')} 去向合计={对账.get('去向合计')} "
            f"归档={对账.get('溢出')} 已标溢出={对账.get('已标溢出')}"
        )
    return 问题
