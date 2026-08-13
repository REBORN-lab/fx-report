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

    head: str;caveats: 非空 str 组成的 list/tuple(可以是空序列)。返回 str。

    caveats 为空序列时**不得拼出空括号**:「区间内至少 3 条()」会把"没有
    任何观测缺口"这条最强的结论渲染成一个像是漏填的括号。

    形状不对一律抛错,**不静默拼**。这个函数产出的句子会被逐字抄进报告,
    而 Task 3 起的整句包含检查只比"报告与快照是否一致",不会发现快照里的
    句子本身已经坏了 —— 坏句子一旦落盘就无人拦截。尤其 caveats 为 None 时
    静默返回 head,等于把"有观测缺口"改写成"没有缺口"。

    括号沿用仓库既有写法(ASCII 0x28/0x29),分隔符用全角顿号(0x3001)——
    Task 3 起整句包含检查是逐字节的,任何一处改宽度都会让同一条结论在两处
    不相等。
    """
    if not isinstance(head, str):
        raise TypeError("head 必须是 str,收到 %s" % type(head).__name__)
    if not isinstance(caveats, (list, tuple)):
        # str 会被逐字拆开、生成器求值一次即空、None 静默变成"没有缺口"
        raise TypeError("caveats 必须是 list/tuple,收到 %s"
                        % type(caveats).__name__)
    if not all(isinstance(c, str) and c for c in caveats):
        raise ValueError("caveat 必须是非空 str:%r" % (caveats,))
    if not caveats:
        return head
    return "%s(%s)" % (head, "、".join(caveats))
