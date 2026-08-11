"""定盘身份判定与数值门:采集层与周度聚合器共用。

为什么独立成模块:`_fixing_key` 曾被复制到两处,复制时只搬了 key、没搬
"定盘日未知且同值不得算作两次"的补偿守卫,于是周度聚合把快照 schema 换代
(同一次定盘一份有 ref_date、一份没有)算成两次定盘,产出 "0.0% 周涨跌" 与
虚高的定盘次数 —— 管道状态被呈现成市场事实。物理同源杜绝这类漂移。
"""
import math


def num(v):
    """数值门:bool 不是数,NaN/Inf 穿过比较会给出确定性错误结论。"""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    return v if math.isfinite(v) else None


def same_fixing(a_ref, a_value, b_ref, b_value):
    """两条观测是否来自同一次定盘。

    - 两侧 ref_date 都已知:同 ref 即同一次(不同 ref 即便同价也是两次,
      真实的两次定盘恰好同价必须算两次)
    - 任一侧 ref_date 未知(存量快照):只能靠值判断,同值即视为同一次 ——
      无法证明是两次时取保守解,宁可低估定盘次数,也不要凭空多出一次"行情"
    """
    if isinstance(a_ref, str) and isinstance(b_ref, str):
        return a_ref == b_ref
    return a_value == b_value


def distinct_fixings(observations):
    """observations: 按时间升序的 (ref_date, value);返回去重后的同序列表。"""
    out = []
    for ref, value in observations:
        if any(same_fixing(ref, value, r, v) for r, v in out):
            continue
        out.append((ref, value))
    return out
