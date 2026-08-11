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
    """observations: 按时间排列的 (ref_date, value);返回去重后的同序列表。

    只要求"按时间排列",不要求升序:derive 按今日在前、history 由新到旧喂入,
    weekly_digest 按日期升序喂入,两者都合法。首末元素的语义随之不同(前者的
    out[0] 是最新一次定盘,后者的 out[0] 是最早一次),由调用方负责解释。

    合并时"升级"已知定盘日:先来的观测若 ref 未知、后来的同值观测 ref 已知,
    把已知的那个记下来——否则 first/last 定盘日会全变 null,读者无从知道
    涨跌是从哪天量到哪天(信息倒退)。升级同时收敛了 same_fixing 的非传递性:
    A(None,V) 吸收 B(r1,V) 后升级为 r1,再遇 C(r2,V) 就是两个已知不同 ref,
    正确判为两次定盘。

    结果仍轻微依赖输入顺序,但偏差方向单一:只可能低估定盘次数(未知代吞掉
    同价观测),不会凭空多出一次"行情"——低估时 chg 退化为 null,落在安全侧。
    """
    out = []
    for ref, value in observations:
        merged = False
        for i, (r, v) in enumerate(out):
            if same_fixing(ref, value, r, v):
                if not isinstance(r, str) and isinstance(ref, str):
                    out[i] = (ref, v)      # 用已知定盘日升级占位
                merged = True
                break
        if not merged:
            out.append((ref, value))
    return out
