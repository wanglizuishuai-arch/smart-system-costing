#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""capacity.py —— 智能化项目容量推导（纯标准库）

四组最常被追问的量，一次算清并给出边界提示：
    1. 视频存储（分重点/一般保存天数）
    2. 网络带宽（接入 / 跨地块回传）
    3. UPS 容量与后备时间
    4. 光缆芯数

用法：
    python capacity.py --video "重点路数,码率,天数;一般路数,码率,天数" [--margin 0.2]
    python capacity.py --bandwidth 350 --bitrate 4
    python capacity.py --ups "控制3,通信1.5,存储4,业务6"
    python capacity.py --fiber 6
    python capacity.py --selftest

输出一律含"边界"一行：告诉你这个数在什么条件下才成立。
"""
import argparse, sys


def video_capacity(groups, margin=0.2):
    """groups: [(路数, 码率Mbps, 天数)] → (原始TB, 要求有效TB, 建议配置TB)"""
    raw = sum(n * br * 86400 * d for n, br, d in groups) / 8 / 1e6   # Mbps·s → TB(十进制)
    need = raw / (1 - margin)
    return raw, need


def bandwidth(streams, bitrate, overhead=1.2):
    """并发路数 × 码率 × 余量 → Mbps"""
    return streams * bitrate * overhead


def ups(loads_kw, pf=0.9, margin=1.25, hours=0.5):
    """负载 kW → (kVA, 电池 Ah@48V 需求)"""
    total = sum(loads_kw)
    kva = total / pf * margin
    ah = total * 1000 * hours / 48 / 0.8
    return total, kva, ah


def fiber(links, spare=0.5, standard=(12, 24, 48, 96)):
    need = links * 2 * (1 + spare)
    pick = next((s for s in standard if s >= need), standard[-1])
    return need, pick


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default="")
    ap.add_argument("--bandwidth", type=float, default=0)
    ap.add_argument("--bitrate", type=float, default=4.0)
    ap.add_argument("--ups", default="")
    ap.add_argument("--fiber", type=float, default=0)
    ap.add_argument("--margin", type=float, default=0.2)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    out = []
    if a.selftest:
        a.video = "64,4,90;128,4,30"
        a.bandwidth = 350
        a.ups = "3,1.5,4,6"
        a.fiber = 6

    if a.video:
        groups = []
        for seg in a.video.split(";"):
            seg = seg.strip()
            if not seg:
                continue
            try:
                n, br, d = [float(x) for x in seg.split(",")]
            except ValueError:
                print("输入错误：--video 格式应为 路数,码率,天数;...", file=sys.stderr)
                return 2
            groups.append((n, br, d))
        raw, need = video_capacity(groups, a.margin)
        cfg = 2 ** 0
        for cand in (260, 340, 420, 520, 640, 780, 1000):
            if cand >= need:
                cfg = cand
                break
        out.append("【视频存储】原始 %.1f TB｜要求有效 %.1f TB（余量 %.0f%%）｜建议配置 %d TB"
                   % (raw, need, a.margin * 100, cfg))
        out.append("  边界：十进制 TB；RAID 校验与热备须在 %d TB 内扣除；码率按 H.265 主码流，夜间红外更高" % cfg)

    if a.bandwidth:
        out.append("【网络带宽】并发 %.0f 路 × %.1f Mbps × 1.2 = %.0f Mbps（跨地块/集中存储时按此核算）"
                   % (a.bandwidth, a.bitrate, bandwidth(a.bandwidth, a.bitrate)))
        out.append("  边界：本地存储只需回传告警与缩略图（≤50Mbps）；集中存储才需按此带宽建链路")

    if a.ups:
        try:
            loads = [float(x) for x in a.ups.split(",")]
        except ValueError:
            print("输入错误：--ups 应为 kW 列表，用逗号分隔", file=sys.stderr)
            return 2
        total, kva, ah = ups(loads)
        out.append("【UPS】负载合计 %.1f kW｜所需容量 %.1f kVA（PF 0.9、裕量 25%%）｜30 分钟电池 48V/%.0fAh"
                   % (total, kva, ah))
        out.append("  边界：只带控制/通信/存储/业务，不带泵、风机、卷膜电机等动力负载")

    if a.fiber:
        need, pick = fiber(a.fiber)
        out.append("【光缆】%d 条业务链路 → 需 %.0f 芯（含 50%% 备用）→ 选 %d 芯单模"
                   % (a.fiber, need, pick))
        out.append("  边界：跨地块自建约 20–25 万元/5km（含管道协调），租线 4–8 万元/年；二者互斥")

    if not out:
        print("未指定计算项：用 --video / --bandwidth / --ups / --fiber 或 --selftest", file=sys.stderr)
        return 2

    text = "\n".join(out)
    try:
        print(text)
    except UnicodeEncodeError:
        sys.stdout.write(text.encode("utf-8", "replace").decode("utf-8", "replace"))
    return 0


if __name__ == "__main__":
    sys.exit(main())