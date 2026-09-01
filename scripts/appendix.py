#!/usr/bin/env python3
"""附录 A 生成器 —— 正文/附录分界锚点与附录块的**唯一事实源**。

存在理由:管道类结论句(有几条、顶没顶到上限、走的哪条通道、双源差多少)
过去要 LLM 逐字转抄进报告。实测这条通道有三个洞:转抄可以改一个字、可以
少抄一条(四币种撞串时去重后照样过闸)、可以整块塞进 HTML 注释。本模块把
整块附录**由脚本生成**,LLM 一个字符都不写 —— 不变量从「逐字引用」升级成
「不经手」。

三条硬性质,各由 tests/test_appendix.py 的一个类守着:

1. **锚点字面量只在这里写一份**。`scripts/check_report.py` 只许 import。
   与 `scripts/review.py:REVIEW_BLOCK_HEADING` 同规格:两处各写一遍必然漂移,
   漂移后分界要么整个失效、要么整个错位,两种都静默。
2. **确定性**:同一输入逐字节相同。校验端的判据是「报告逐字包含整块」,
   块本身抖一下,那道闸门当场变成噪声。故:币种序取固定表、日期集合排序后
   输出、浮点用同一个格式化口(不随 dict 插入序或 list 顺序变)。
3. **纯函数 + 薄 CLI**:导入期不读文件、不解析 argv —— 校验端要 import 它。

**本模块只转录,不判定**。例如「条目无 channel 字段视同 gdelt」是采集层
(`collect/derive._channel_of`)的判定,这里不复制一份,只如实写「未记录」;
复制判定就是给自己造第二个会漂移的口径。
"""
import argparse
import datetime
import email.utils
import json
import math
import sys

# ---- 正文/附录分界锚点:产出方拥有,校验端只许 import ----
APPENDIX_ANCHOR_DAILY = "## 附录 A:采集口径与结论句(scripts/appendix.py 生成,勿手改)"
APPENDIX_ANCHOR_WEEKLY = ("## 附录 A:结论句逐字引用与观测口径"
                          "(scripts/appendix.py 生成,勿手改)")
# 币种序写死:dict 插入序会随采集顺序(events.query_order 每日轮转)变,
# 跟着它走会让同一天的两次生成给出不同的块。与 check_report.CURRENCIES 的
# 一致性由测试机械钉住。
CURRENCIES = ("USD", "EUR", "PHP", "THB", "BRL")
# 结论句缺失时**不造句**:两处措辞分开,是因为两处的产出方不同,读者据此
# 知道该去重跑哪一步。
VERDICT_ABSENT_DAILY = "结论句不可得(快照未落结论句)"
VERDICT_ABSENT_WEEKLY = "结论句不可得(聚合文件未落结论句)"
# 缺输入写 null,不写 0 —— 0 是一个结论(「差为零」),null 只是信息缺失。
NULL = "null"
UNREADABLE_DAY = "不可辨认"
SEENDATE_FORMAT = "%Y%m%dT%H%M%SZ"


def _dict(obj):
    """isinstance 门:非 dict(缺失/外部损坏)一律当空 dict —— 本模块是格式化
    层,输入是外部数据,任何形状都不得裸崩(崩了就没有附录块可比对)。"""
    return obj if isinstance(obj, dict) else {}


def _verbatim(value, fallback):
    """结论句只有两种命运:逐字照抄,或如实写「不可得」。不存在第三种。"""
    return value if isinstance(value, str) and value else fallback


def num_text(value):
    """数值的唯一格式化口 —— `scripts/trend.py` 的趋势块也走它。

    两个模块的产物印在同一份报告里,格式化各写一份的话,同一个 0.85697
    会在两节里印成两种样子,而"同一个数印成两样"正是读者最先怀疑数据
    出错的地方。所以这个名字**没有下划线前缀**:它是跨模块的公开口。
bool 是 int 的子类,不挡住会印出「True」;
    NaN/Inf 印出来会被读成数字 —— 两者都写 null(信息缺失,不是 0)。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return NULL
    if isinstance(value, float) and not math.isfinite(value):
        return NULL
    return repr(value) if isinstance(value, float) else str(value)



def _str_text(value):
    return value if isinstance(value, str) and value else NULL


def _seen_day(value):
    """GDELT/gnews 的机读采见时间戳 → UTC 自然日。认不出返回 None(不猜)。

    走 strptime 而不是正则切片:正则会把 20269999T000000Z 这种坏值原样切成
    「2026-99-99」印进附录,而它其实是"认不出"。
    """
    if not isinstance(value, str):
        return None
    try:
        return datetime.datetime.strptime(value, SEENDATE_FORMAT).date().isoformat()
    except (ValueError, TypeError):
        return None


def _published_day(value):
    """RFC 2822 发布时间 → UTC 自然日。带时区的一律换算到 UTC 后取日,
    否则同一份输入在两台时区不同的机器上会给出不同的块。"""
    if not isinstance(value, str) or not value:
        return None
    try:
        dt = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError, IndexError):
        return None
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(datetime.timezone.utc)
    return dt.date().isoformat()


def _days_phrase(values, to_day):
    """一组时间戳 → 「日期、日期、不可辨认 N 条」。日期集合排序后输出:
    条目顺序不得影响结果(采集顺序是外部事实,块必须稳定)。"""
    days, unknown = set(), 0
    for v in values:
        day = to_day(v)
        if day is None:
            unknown += 1
        else:
            days.add(day)
    parts = sorted(days)
    if unknown:
        parts.append("%s %d 条" % (UNREADABLE_DAY, unknown))
    return "、".join(parts)


def _events_entry(snap, currency):
    return _dict(_dict(snap.get("events")).get(currency))


# ---------------------------------------------------------------- 日报附录 A

def _daily_verdict_lines(snap):
    derived_events = _dict(_dict(snap.get("derived")).get("events"))
    return ["- %s 事件结论(逐字):%s"
            % (c, _verbatim(_dict(derived_events.get(c)).get("events_verdict"),
                            VERDICT_ABSENT_DAILY))
            for c in CURRENCIES]


def _daily_seendate_line(snap):
    parts = []
    for c in CURRENCIES:
        arts = _events_entry(snap, c).get("articles")
        if not isinstance(arts, list):
            parts.append("%s 无事件条目" % c)
        elif not arts:
            # 空列表是「采到 0 条」,与「没有条目」不是一回事,不得合并
            parts.append("%s 无条目" % c)
        else:
            parts.append("%s %s" % (c, _days_phrase(
                [a.get("seendate") if isinstance(a, dict) else None for a in arts],
                _seen_day)))
    return "- 采见日口径:" + ";".join(parts)


def _daily_channel_line(snap):
    parts = []
    for c in CURRENCIES:
        entry = _events_entry(snap, c)
        if not isinstance(entry.get("articles"), list):
            parts.append("%s 无事件条目" % c)
            continue
        chan = entry.get("channel")
        # 「没写 channel 就是 gdelt」是采集层的判定,这里不复制,只写它没写
        parts.append("%s %s" % (c, chan if isinstance(chan, str) and chan
                                else "未记录(存量快照)"))
    return "- 通道口径:" + ";".join(parts)


def _daily_official_line(snap):
    parts = []
    for c in CURRENCIES:
        entry = _events_entry(snap, c)
        official = entry.get("official")
        if "official" not in entry:
            # 「没有这个键」与「键在但读不了」是两件事:前者是该币种没接公告源,
            # 后者是结构损坏,该去重跑采集。合并成一句会把缺陷说成常态
            parts.append("%s 快照无 official 键" % c)
        elif not isinstance(official, list):
            parts.append("%s official 键结构不可读" % c)
        elif not official:
            parts.append("%s 0 条" % c)
        else:
            parts.append("%s %d 条(发布日 %s)" % (
                c, len(official), _days_phrase(
                    [o.get("published") if isinstance(o, dict) else None
                     for o in official], _published_day)))
    cap = _dict(_dict(snap.get("meta")).get("caps")).get("official_daily")
    if isinstance(cap, int) and not isinstance(cap, bool) and cap > 0:
        parts.append("当日公告上限 %d 条" % cap)
    else:
        parts.append("当日公告上限不可知")
    return "- 公告口径:" + ";".join(parts)


def _daily_deviation_line(snap):
    derived_rates = _dict(_dict(snap.get("derived")).get("rates"))
    parts, suspects = [], []
    for c in CURRENCIES:
        entry = _dict(snap.get("rates")).get(c)
        if not isinstance(entry, dict):
            parts.append("%s 快照 rates 容器无该币种条目" % c)
            continue
        parts.append("%s %s(前值 %s)" % (
            c, num_text(entry.get("deviation_pct")),
            num_text(_dict(derived_rates.get(c)).get("deviation_pct_prev"))))
        if entry.get("suspect") is True:
            suspects.append(c)
    parts.append("可疑标记:" + ("、".join(suspects) if suspects else "无"))
    return "- 双源偏差:" + ";".join(parts)


def daily_appendix(snapshot):
    """日报附录 A 整块。纯函数:不读写文件、不改入参、同输入同输出。

    返回值第一行恒为 APPENDIX_ANCHOR_DAILY,结尾无换行 —— 调用方自己决定
    怎么拼进文件,块本身不带任何位置假设。
    """
    snap = _dict(snapshot)
    lines = [APPENDIX_ANCHOR_DAILY, ""]
    lines.extend(_daily_verdict_lines(snap))
    lines.append(_daily_seendate_line(snap))
    lines.append(_daily_channel_line(snap))
    lines.append(_daily_official_line(snap))
    lines.append(_daily_deviation_line(snap))
    return "\n".join(lines)


# ---------------------------------------------------------------- 周报附录 A

def _weekly_currency_lines(dg, currency):
    events = _dict(_dict(dg.get("events")).get(currency))
    out = ["- %s 事件(逐字):%s" % (currency, _verbatim(
        events.get("articles_verdict"), VERDICT_ABSENT_WEEKLY)),
        "- %s 公告(逐字):%s" % (currency, _verbatim(
            events.get("official_verdict"), VERDICT_ABSENT_WEEKLY))]
    entry = _dict(dg.get("rates")).get(currency)
    if not isinstance(entry, dict):
        # 基准货币在 rates 容器里本就没有条目 —— 这不是缺陷,必须写明理由,
        # 否则读者会把「没有这句」读成「这句被漏抄了」
        reason = "聚合文件 rates 容器无该币种条目,无定盘结论句"
        if currency == "USD":
            reason = "基准货币," + reason
        out.append("- %s 定盘与区间(逐字):%s" % (currency, reason))
    else:
        out.append("- %s 定盘与区间(逐字):%s" % (currency, _verbatim(
            entry.get("fixings_verdict"), VERDICT_ABSENT_WEEKLY)))
    return out


def weekly_appendix(digest):
    """周报附录 A 整块:14 条结论句槽位 + USD 定盘槽的理由 + 口径差异说明。"""
    dg = _dict(digest)
    lines = [APPENDIX_ANCHOR_WEEKLY, "", "以下逐字引自周度聚合文件,一个字符未改。", ""]
    for c in CURRENCIES:
        lines.extend(_weekly_currency_lines(dg, c))
    lines.append("- 口径差异:事件与公告结论句按区间累计条数计,定盘结论句按不同价位计,"
                 "三档口径不可比,不得相加;覆盖区间 %s 至 %s,跳过 %s 份。"
                 % (_str_text(dg.get("window_from")), _str_text(dg.get("window_to")),
                    num_text(dg.get("skipped"))))
    return "\n".join(lines)


# -------------------------------------------------------------------- 薄 CLI

def build_parser():
    """选项注册处。**没有位置参数**:本仓库栽过一次「多给一个位置参数就静默
    走另一条路」(check_report weekly),这里由测试钉死多余实参必须 rc=2。"""
    ap = argparse.ArgumentParser(
        description="生成报告附录 A 整块(日报读快照,周报读周度聚合文件)")
    ap.add_argument("--mode", required=True, choices=("daily", "weekly"))
    ap.add_argument("--input", required=True, help="快照或聚合文件路径")
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        with open(args.input, encoding="utf-8") as f:
            payload = json.load(f)
    except (OSError, UnicodeDecodeError, ValueError, RecursionError) as e:
        print("无法读取输入 %s: %s" % (args.input, e), file=sys.stderr)
        return 2
    print(daily_appendix(payload) if args.mode == "daily"
          else weekly_appendix(payload))
    return 0


if __name__ == "__main__":
    sys.exit(main())
