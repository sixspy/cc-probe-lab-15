"""争用失败测：溢出临界两路同灌，双突破则红。

硬推理：不加锁时两路都读到同一水位、各自判可入、双双写入 → 在栏双突破。
锁纪律（BEGIN IMMEDIATE + busy_timeout）下两路串行裁决，容限只放一条，其余切流归档。
收尾再贯验：双轨不相交、总账对齐。
"""
import threading

from app.services import 装载, 目录, 贯验


def _报文(n: int) -> dict:
    return {
        "报文编号": f"ov-c-{n}",
        "站点键": "站-河东",
        "指标键": "PM25",
        "读数": 25.0 + (n % 10),
        "观测时": f"2026-11-25T10:{n % 60:02d}:00Z",
    }


def test_临界两路并发灌不得双突破():
    目录.改栏规({"入栏容限": "3"})
    # 预置两条在栏，临界只剩一个容限位
    装载.装一批({"批次编号": "ov-c-pre", "报文": [_报文(100 + i) for i in range(2)]})

    果: list[dict] = []
    锁 = threading.Lock()

    def 灌(seed: int) -> None:
        r = 装载.装一批({
            "批次编号": f"ov-c-t{seed}",
            "报文": [_报文(200 + seed * 10 + j) for j in range(2)],
        })
        with 锁:
            果.append(r)

    t1 = threading.Thread(target=灌, args=(1,))
    t2 = threading.Thread(target=灌, args=(2,))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert len(果) == 2
    在栏 = [r for r in 目录.缓冲列表() if r["命运"] == "在栏"]
    from app.services import 溢出
    归档 = 溢出.归档列表()

    # 两路合计四件抢一个位：现行恰好顶到容限，绝不双突破
    assert len(在栏) == 3
    assert len(归档) == 3
    # 双轨不相交，同一条报文不可能既在栏又溢出
    现行编号 = {r["报文编号"] for r in 在栏}
    旁路编号 = {r["报文编号"] for r in 归档}
    assert 现行编号.isdisjoint(旁路编号)
    assert len(现行编号 | 旁路编号) == 6

    # 再贯验：并发落库后账仍对齐
    v = 贯验.跑一次()
    assert v["是否对齐"] is True
    assert v["溢出"] == 3


def test_结栏与装载并发不产生双态():
    """溢出与结栏并发：同锁纪律下，一条报文不可能既被汇总又在在栏/溢出双态。"""
    from app.services import 结栏
    目录.改栏规({"入栏容限": "2"})
    装载.装一批({"批次编号": "ov-c-close", "报文": [_报文(300 + i) for i in range(2)]})

    果 = {}

    def 装():
        果["装"] = 装载.装一批({"批次编号": "ov-c-close-2", "报文": [_报文(400 + i) for i in range(3)]})

    def 结():
        果["结"] = 结栏.结当前栏()

    t1 = threading.Thread(target=装)
    t2 = threading.Thread(target=结)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # 现行永不破容
    在栏 = [r for r in 目录.缓冲列表() if r["命运"] == "在栏"]
    assert len(在栏) <= 2
    from app.services import 溢出
    归档编号 = {r["报文编号"] for r in 溢出.归档列表()}
    汇总编号 = {r["报文编号"] for r in 目录.缓冲列表() if r["命运"] == "已汇总"}
    # 无任何报文同时出现在两轨
    assert 归档编号.isdisjoint(汇总编号)
    assert 贯验.跑一次()["是否对齐"] is True
