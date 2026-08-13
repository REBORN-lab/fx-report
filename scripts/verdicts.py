"""结论句的唯一拼装口:head 与 caveat 列表怎么连,只有这一处说了算。

**共享拼装,不共享判定。** 周报的判定输入是跨日统计(days_collected /
window_days / in_window),日报是单日事实(count / count_capped /
sample_capped / channel_changed_from);两者定义域不同,强行复用判定正是
`_entry_of` 读 rates 却被用于 events 那类事故的成因(上一个 change 第四轮)。
会漂移的只有措辞与连接方式,抽出来的也只有这一层。

先例:scripts/fixings.py 已为采集层与周度聚合器共用。
"""


def join_verdict(head, caveats):
    """head 与 caveat 列表的唯一拼装口。

    caveats 为空时**不得拼出空括号**:「区间内至少 3 条()」会把"没有任何
    观测缺口"这条最强的结论渲染成一个像是漏填的括号。括号与顿号都用全角 ——
    整句包含检查是逐字节的,半角会让同一条结论在两处不相等。
    """
    if not caveats:
        return head
    return "%s（%s）" % (head, "、".join(caveats))
