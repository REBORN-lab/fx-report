"""结构化观点:登记(`validate_claim`)与判定(`resolve_claim`)。

---- 为什么要有这一层 ----

2026-08-14 实测:`state/decision-log.jsonl` 40 条里 33 条的 verdict 是
「无法判定」,六份产物正文出现 30 次。根因不是数据不够,是**复盘时点与观点
时限不匹配**:旧 `scripts/review.py` 永远只复盘"上一个记过的日子",而速览表
的触发条件写的是 `(T+3)`;于是一条"三个运行日内升破 33.13"的观点,第二天
就被拿去判,判据还只是两次定盘的高低。参考价没更新的那两天(实测 08-12 与
08-14 的 `ref_date == prev_ref_date`),两次读数相等 → 直接「无法判定」。

**那 33 条里绝大多数的诚实答案不是「无法判定」,是「未到期」。** 两档在旧
实现里是同一个值,把"我们还没到该看的时候"伪装成了"我们看了但看不出来"。
本模块把这两档拆开,并且把结论收进一个纯函数 —— 结论只能由它给出。

---- LLM 只做"抄"与"选" ----

`claim.legs[*].threshold` 是**字符串**,必须逐字取自散文 `trigger`;
`field` / `op` 从下面的固定枚举里选;`horizon.quote` 同样是散文里的原文片段。
校验器与 `add` 入口共用 `validate_claim`,对不上就红。LLM 不做任何计算。

---- 运行日只由快照里的事实得出 ----

一个"运行日"= 窗口内某个快照日上,该观点的**读数键**(参考价的定盘日期 /
宏观序列的期号)出现了此前没见过的值。本模块**不查任何日程表**:它手上只有
各日快照里的 `ref_date` 与 `period`,没有任何交易所日程输入。这条约束继承自
`scripts/review.py` 修前就写明的那一条,不得破坏。

窗口的**外沿**用快照日数(跑过采集的天数)界定:一个快照日最多贡献一个新
读数键,所以"n 个快照日过去了"是"至多 n 个运行日发生过"的可靠上界,不需要
任何日程输入。到了外沿而运行日不足 n,诚实答案就是「无法判定」,并且必须
说清缺的是哪一次观测。
"""
import math
import re

from collections import namedtuple

# 结论句的拼装口只有一个(head 与 caveat 列表怎么连,只有 verdicts 说了算)。
# 与 `scripts/review.py` 修前同一条理由:自己用 % / join 拼会在分隔符、括号与
# "没有 caveat 时不得拼出空括号"三处各漂一次,而这三处正是逐字引用检查的
# 比对对象。两条分支对应包内导入与脚本直跑两种运行形态。
try:
    from scripts.verdicts import join_verdict
except ImportError:                                  # pragma: no cover - 直跑分支
    from verdicts import join_verdict

# ---- 四档:互斥且穷尽 ----
# 未到期 : 时限还没到 —— 本轮的主要收益,与「无法判定」严格分开
# 命中/未命中 : 时限内有足够观测,可判
# 无法判定 : 观测缺失,再等也判不出 —— 必须说清缺的是哪一次观测
STATUS_PENDING = "未到期"
STATUS_HIT = "命中"
STATUS_MISS = "未命中"
STATUS_UNDECIDABLE = "无法判定"
STATUSES = (STATUS_PENDING, STATUS_HIT, STATUS_MISS, STATUS_UNDECIDABLE)

# 币种 → 经济体码。宏观序列按经济体归档,而 LLM 只在币种上做选择;
# 这张表是**唯一**的换算处,让"选哪个币种"与"读哪条序列"不必分两处填。
CURRENCY_ECONOMY = {"USD": "US", "EUR": "EA", "PHP": "PH", "THB": "TH",
                    "BRL": "BR"}

# ---- 可观测量的固定枚举 ----
# 键 = LLM 能填的字段名;值 = (取值路径种类, 快照内的定位, 中文标签)。
# **只许从这里选**:自由填字段名等于把"读哪个数"交给散文,而散文里的字段名
# 没有任何东西保证它在快照里存在 —— 那正是旧实现"结论恒为无法判定"的另一半。
FIELD_SPECS = {
    "primary": ("rate", "primary", "参考价"),
    "range_5d_high": ("derived_rate", "range_5d_high", "5 运行日区间上沿"),
    "range_5d_low": ("derived_rate", "range_5d_low", "5 运行日区间下沿"),
    "cpi_yoy": ("macro", "CPI 同比", "CPI 同比"),
    "policy_rate": ("macro", "政策利率", "政策利率"),
}
FIELDS = tuple(sorted(FIELD_SPECS))

# 比较方向的固定枚举:(成立时的说法, 不成立时的说法, 判定)。
# 中文标签直接进结论句,句子要落进**正文**,所以措辞里不得出现管道语汇。
#
# **两套说法缺一不可。** 只留一套(取自 `op`、与是否成立无关)时,判「未命中」
# 的那一句会写成「0.86655 高于 0.86693」—— 而 0.86655 并不高于 0.86693。
# 结论与依据当场打架,并且这一句会被逐字抄进正文,读者只看得到那半句假话。
# 这条缺陷是变异验证(把时限从 T+3 改成 T+1)实跑出来的,不是设想出来的。
OP_SPECS = {
    "gt": ("高于", "未高于", lambda a, b: a > b),
    "gte": ("不低于", "低于", lambda a, b: a >= b),
    "lt": ("低于", "未低于", lambda a, b: a < b),
    "lte": ("不高于", "高于", lambda a, b: a <= b),
    "eq": ("等于", "不等于", lambda a, b: a == b),
}
OPS = tuple(sorted(OP_SPECS))


def op_labels(op):
    """(成立时的说法, 不成立时的说法)。"""
    held, not_held, _ = OP_SPECS[op]
    return held, not_held


def op_holds(op, value, threshold):
    return OP_SPECS[op][2](value, threshold)

HORIZON_KINDS = ("running_days", "date", "open")
ISO_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
# 时限措辞里的 T+N。用来把散文写的运行日数与 `horizon.n` 对上。
T_PLUS_N_RE = re.compile(r"T\+(\d+)")

ClaimResolution = namedtuple("ClaimResolution",
                             "status sentence window_days running_days")


def unchanged_ref_note(ref_date):
    """两日同定盘时的那句话。**唯一事实源在这里**(本模块是产出方)。

    `scripts/check_report.py` 只许导入、据它推出行式样,不许自己再写一遍:
    两处各写一遍必然漂移,而漂移的后果是识别器一条真行都认不出、整块豁免
    失效,不会有人发现。实测踩过一脚同型的 —— 括号是 **ASCII** `()`,
    手抄的正则没转义,式样反而要求「没有括号」。

    **只陈述事实,不断言原因。** 本模块从不查任何日程表:它手上只有两个定盘
    日期。至于为什么没更新(休市?源未刷新?采集时点早于定盘?),交给读者
    据这个日期自己判断。修前这里写的是「参考价未更新(非工作日)」,而实测
    2026-08-12 是周三、2026-08-14 是周五,四个币种都不休市,那句假归因还经
    报告复盘节逐字引用流回了正文。

    措辞里不得出现管道语汇(「快照」等):这句话要落进**正文**,而正文位置
    闸门禁的正是那些词,脚本自己的产出不得触发它(自伤形态)。
    """
    return "参考价未更新(仍为 %s 定盘)" % ref_date


# ---------------------------------------------------------------- 登记侧

def _problem(code, msg):
    return "%s: %s" % (code, msg)


def _validate_horizon(horizon, trigger):
    """时限:运行日 T+N / 绝对日期 / 未登记。返回问题列表。"""
    problems = []
    if not isinstance(horizon, dict):
        return [_problem("CLAIM_HORIZON_MALFORMED",
                         "horizon 须为对象,收到 %r" % (horizon,))]
    kind = horizon.get("kind")
    if kind not in HORIZON_KINDS:
        return [_problem("CLAIM_HORIZON_MALFORMED",
                         "horizon.kind 须为 %s 之一,收到 %r"
                         % ("/".join(HORIZON_KINDS), kind))]
    quote = horizon.get("quote")
    if kind == "open":
        # 散文没写时限 → 这条观点没有到期日,只能"命中"或"仍在观察"。
        # 此时 quote 必须是 null:填了字符串就等于声称散文写了时限,
        # 而这一档的全部含义正是"散文没写"。
        if quote is not None:
            problems.append(_problem(
                "CLAIM_HORIZON_MALFORMED",
                "horizon.kind 为 open 时 quote 须为 null,收到 %r" % (quote,)))
        return problems
    if not isinstance(quote, str) or not quote.strip():
        problems.append(_problem("CLAIM_HORIZON_MALFORMED",
                                 "horizon.quote 须为非空字符串,收到 %r"
                                 % (quote,)))
    elif not isinstance(trigger, str) or quote not in trigger:
        # LLM 只准抄:时限也得逐字取自散文,否则"时限"就是事后编的
        problems.append(_problem(
            "CLAIM_HORIZON_NOT_SOURCED",
            "horizon.quote「%s」未逐字出现在 trigger 里;trigger 原文:%r"
            % (quote, trigger)))
    if kind == "running_days":
        n = horizon.get("n")
        if isinstance(n, bool) or not isinstance(n, int) or n < 1:
            problems.append(_problem("CLAIM_HORIZON_MALFORMED",
                                     "horizon.n 须为 ≥1 的整数,收到 %r" % (n,)))
        elif isinstance(quote, str):
            # `quote` 写 T+3 而 `n` 填 9:散文说三个运行日、判定按九个算,
            # 时限被凭空延长而两边各自都"合法"。变异验证实跑出来的缺口。
            # 措辞里没有 T+N(如「在下一次定盘」)时不强判 —— 没有可比的数,
            # 硬判只会逼出一个假的 quote。
            m = T_PLUS_N_RE.search(quote)
            if m and int(m.group(1)) != n:
                problems.append(_problem(
                    "CLAIM_HORIZON_N_MISMATCH",
                    "horizon.quote 写的是「%s」,horizon.n 却是 %d —— "
                    "散文与判定用的不是同一个时限" % (quote, n)))
    else:
        on = horizon.get("on")
        if not isinstance(on, str) or not ISO_DATE_RE.fullmatch(on):
            problems.append(_problem("CLAIM_HORIZON_MALFORMED",
                                     "horizon.on 须为 YYYY-MM-DD,收到 %r"
                                     % (on,)))
    return problems


def _sourced_as_a_whole_number(threshold, trigger):
    """阈值是否**作为一个完整的数**逐字出现在散文里。

    判据不是纯子串:`0.8669` 是散文里 `0.86693` 的前缀,纯子串会放它过去,
    而判定用的是被截短的那个数 —— 散文写着"升破 0.86693"、脚本比的却是
    0.8669,两者从此各说各话,读者只看得到散文那半。所以两侧都不许再接
    数字或小数点。
    """
    if not isinstance(trigger, str):
        return False
    for m in re.finditer(re.escape(threshold), trigger):
        before = trigger[m.start() - 1] if m.start() else ""
        after = trigger[m.end()] if m.end() < len(trigger) else ""
        if not (before.isdigit() or before == ".") and \
                not (after.isdigit() or after == "."):
            return True
    return False


def _validate_leg(idx, leg, trigger):
    problems = []
    if not isinstance(leg, dict):
        return [_problem("CLAIM_LEG_MALFORMED",
                         "legs[%d] 须为对象,收到 %r" % (idx, leg))]
    currency = leg.get("currency")
    if currency not in CURRENCY_ECONOMY:
        problems.append(_problem("CLAIM_LEG_MALFORMED",
                                 "legs[%d].currency 须为 %s 之一,收到 %r"
                                 % (idx, "/".join(sorted(CURRENCY_ECONOMY)),
                                    currency)))
    if leg.get("field") not in FIELD_SPECS:
        problems.append(_problem("CLAIM_FIELD_UNKNOWN",
                                 "legs[%d].field 须为 %s 之一,收到 %r"
                                 % (idx, "/".join(FIELDS), leg.get("field"))))
    if leg.get("op") not in OP_SPECS:
        problems.append(_problem("CLAIM_OP_UNKNOWN",
                                 "legs[%d].op 须为 %s 之一,收到 %r"
                                 % (idx, "/".join(OPS), leg.get("op"))))
    threshold = leg.get("threshold")
    if not isinstance(threshold, str) or not threshold.strip():
        problems.append(_problem("CLAIM_THRESHOLD_MALFORMED",
                                 "legs[%d].threshold 须为非空字符串(逐字抄自"
                                 "散文),收到 %r" % (idx, threshold)))
        return problems
    if _parse_threshold(threshold) is None:
        problems.append(_problem("CLAIM_THRESHOLD_MALFORMED",
                                 "legs[%d].threshold 不是可比较的数:%r"
                                 % (idx, threshold)))
    if not _sourced_as_a_whole_number(threshold, trigger):
        # **这一条是本轮的硬要求**:阈值必须逐字出现在该条的散文 trigger 里。
        # 允许"差不多"就等于允许 LLM 在结构化字段里另写一个数,而结构化字段
        # 才是判定入口 —— 散文与判定从此各说各话,读者只看得到散文那半。
        problems.append(_problem(
            "CLAIM_THRESHOLD_NOT_SOURCED",
            "legs[%d].threshold「%s」未作为一个完整的数逐字出现在 trigger 里;"
            "trigger 原文:%r" % (idx, threshold, trigger)))
    return problems


def validate_claim(claim, trigger):
    """结构化观点的形状与溯源校验。返回问题字符串列表(空 = 合格)。

    `scripts/log_decision.py` 的 add 入口与 `scripts/check_report.py` 共用
    这一份判据:两处各写一遍必然漂移,而漂移的后果是登记时放行、校验时打红
    (或反过来),都不会有人发现。
    """
    if not isinstance(claim, dict):
        return [_problem("CLAIM_MALFORMED", "claim 须为对象,收到 %r" % (claim,))]
    problems = list(_validate_horizon(claim.get("horizon"), trigger))
    legs = claim.get("legs")
    reason = claim.get("unstructurable_reason")
    if legs is None:
        # 散文里没有可机器求值的阈值 —— 如实标注,**不得编造阈值**。
        # 但必须说明是哪一句话不可结构化,否则这一档就成了万能豁免。
        if not isinstance(reason, str) or not reason.strip():
            problems.append(_problem(
                "CLAIM_UNSTRUCTURABLE_REASON_MISSING",
                "legs 为 null 时须给出 unstructurable_reason 说明散文哪一处"
                "没有可机器求值的阈值,收到 %r" % (reason,)))
        return problems
    if reason is not None:
        problems.append(_problem(
            "CLAIM_MALFORMED",
            "legs 非 null 时不得同时给 unstructurable_reason,收到 %r"
            % (reason,)))
    if not isinstance(legs, list) or not legs:
        problems.append(_problem("CLAIM_MALFORMED",
                                 "legs 须为 null 或非空数组,收到 %r" % (legs,)))
        return problems
    for idx, leg in enumerate(legs):
        problems.extend(_validate_leg(idx, leg, trigger))
    return problems


# ---------------------------------------------------------------- 取值侧

def _parse_threshold(text):
    """阈值字符串 → float。**只解析,不换算**:它逐字来自散文。"""
    try:
        value = float(text)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _num(value):
    """数值门:bool 与非数值 → None;NaN/Infinity 穿过数值比较会给出确定性
    错误结论 → 同样视为缺失(与 `scripts/review.py` 修前同一条约定)。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


def _rate_entry(snap, currency):
    if not isinstance(snap, dict):
        return None
    rates = snap.get("rates")
    if not isinstance(rates, dict):
        return None
    entry = rates.get(currency)
    return entry if isinstance(entry, dict) else None


def _derived_rate_entry(snap, currency):
    if not isinstance(snap, dict):
        return None
    derived = snap.get("derived")
    if not isinstance(derived, dict):
        return None
    rates = derived.get("rates")
    if not isinstance(rates, dict):
        return None
    entry = rates.get(currency)
    return entry if isinstance(entry, dict) else None


def _macro_entry(snap, currency, indicator):
    if not isinstance(snap, dict):
        return None
    rows = snap.get("macro")
    if not isinstance(rows, list):
        return None
    economy = CURRENCY_ECONOMY.get(currency)
    for row in rows:
        if (isinstance(row, dict) and row.get("economy") == economy
                and row.get("indicator") == indicator):
            return row
    return None


def read_leg(snap, leg):
    """一条腿在某日快照上的 (读数, 读数键)。任一为 None = 这一天读不到。

    读数键是"这次读数是不是新的"的**唯一判据**:参考价用定盘日期,宏观序列
    用期号。两者都是快照里已有的事实,不需要任何日程输入。
    """
    kind, locator, _ = FIELD_SPECS[leg["field"]]
    currency = leg["currency"]
    if kind == "rate":
        entry = _rate_entry(snap, currency)
        if entry is None:
            return None, None
        ref = entry.get("ref_date")
        return _num(entry.get(locator)), ref if isinstance(ref, str) else None
    if kind == "derived_rate":
        entry = _derived_rate_entry(snap, currency)
        if entry is None:
            return None, None
        # 派生量本身没有自己的定盘日期,它是由参考价序列算出来的 ——
        # 新旧判据只能取参考价那一个,取别的就是另建一份事实源。
        rate = _rate_entry(snap, currency)
        ref = rate.get("ref_date") if isinstance(rate, dict) else None
        return _num(entry.get(locator)), ref if isinstance(ref, str) else None
    entry = _macro_entry(snap, currency, locator)
    if entry is None:
        return None, None
    period = entry.get("period")
    return _num(entry.get("value")), period if isinstance(period, str) else None


# ---------------------------------------------------------------- 判定侧

def _fmt(value):
    return ("%d" % value) if float(value).is_integer() and abs(value) >= 1e16 \
        else repr(value)


def _leg_desc(leg, value):
    """一条腿的读数描述。**比较词取自实际观测到的关系**,不是观点声称的那个 ——
    否则「未命中」那一句会写成"高于",与它自己的结论打架。

    句内只给事实、不给原因,不出现管道语汇 —— 这句话要落进**正文**,而正文
    位置闸门禁的正是那些词。
    """
    _, _, label = FIELD_SPECS[leg["field"]]
    held, not_held = op_labels(leg["op"])
    threshold = _parse_threshold(leg["threshold"])
    word = held if (threshold is not None
                    and op_holds(leg["op"], value, threshold)) else not_held
    return "%s %s %s %s %s" % (leg["currency"], label, _fmt(value), word,
                               leg["threshold"])


def _horizon_caveat(horizon):
    kind = horizon.get("kind")
    if kind == "running_days":
        return "时限 %s、按 %d 个运行日计" % (horizon.get("quote"),
                                            horizon.get("n"))
    if kind == "date":
        return "时限 %s、按 %s 到期计" % (horizon.get("quote"),
                                        horizon.get("on"))
    return "该观点未登记时限"


def _usable_horizon(claim):
    """能不能按这条 horizon 划窗口。形状坏掉时返回 None(判定侧不抛错:
    一条坏条目不该让当日整轮复盘崩掉,它自己落进「无法判定」即可)。"""
    if not isinstance(claim, dict):
        return None
    horizon = claim.get("horizon")
    if not isinstance(horizon, dict) or horizon.get("kind") not in HORIZON_KINDS:
        return None
    kind = horizon.get("kind")
    if kind == "running_days":
        n = horizon.get("n")
        if isinstance(n, bool) or not isinstance(n, int) or n < 1:
            return None
    elif kind == "date":
        on = horizon.get("on")
        if not isinstance(on, str) or not ISO_DATE_RE.fullmatch(on):
            return None
    return horizon


def _usable_legs(claim):
    legs = claim.get("legs")
    if not isinstance(legs, list) or not legs:
        return None
    for leg in legs:
        if not isinstance(leg, dict):
            return None
        if (leg.get("currency") not in CURRENCY_ECONOMY
                or leg.get("field") not in FIELD_SPECS
                or leg.get("op") not in OP_SPECS
                or _parse_threshold(leg.get("threshold")) is None):
            return None
    return legs


def _check_snapshots(snapshots):
    if not isinstance(snapshots, (list, tuple)):
        raise TypeError("snapshots 必须是 list/tuple,收到 %s"
                        % type(snapshots).__name__)
    if not snapshots:
        raise ValueError("snapshots 至少要有观点日当日那一项")
    for item in snapshots:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            raise TypeError("snapshots 的每一项须为 (日期, 快照) 二元组,"
                            "收到 %r" % (item,))
        date, snap = item
        if not isinstance(date, str) or not date:
            raise TypeError("snapshots 的日期须为非空 str,收到 %r" % (date,))
        if snap is not None and not isinstance(snap, dict):
            raise TypeError("snapshots 的快照须为 dict 或 None,收到 %s"
                            % type(snap).__name__)


def _window(horizon, rest):
    """窗口 = 观点日之后、时限之内的那些快照日。

    运行日窗口用**快照日数**界定外沿:一个快照日最多贡献一个新读数键,
    所以"前 n 个快照日"是"至多 n 个运行日"的可靠上界。这样划窗口不需要
    任何日程输入 —— 缺的那几次定盘由「无法判定」如实说出来,而不是靠猜
    哪天该有定盘把它补上。
    """
    kind = horizon.get("kind")
    if kind == "running_days":
        n = horizon["n"]
        return rest[:n], len(rest) >= n
    if kind == "date":
        on = horizon["on"]
        inside = [item for item in rest if item[0] <= on]
        return inside, bool(rest) and rest[-1][0] >= on
    return list(rest), False


def resolve_claim(entry, snapshots):
    """**结论只能由这里给出。** 纯函数:同样的入参恒给同样的四档与依据句。

    entry     : 一条决策日志条目(须带 `claim`)
    snapshots : `[(日期, 快照或 None), …]` 升序,**第一项须为观点日当日**
                (它给出各条腿的基线读数键),其余为其后每个跑过采集的日子。

    返回 `ClaimResolution(status, sentence, window_days, running_days)`。
    `status` 取自 `STATUSES` 四档之一,互斥且穷尽;`sentence` 是供报告
    **逐字引用**的整句,经 `verdicts.join_verdict` 拼装 —— 与 events_verdict
    走同一条通道,分隔符与括号宽度因此不可能在两处不相等。
    """
    if not isinstance(entry, dict):
        raise TypeError("entry 必须是 dict,收到 %s" % type(entry).__name__)
    _check_snapshots(snapshots)
    date = entry.get("date")
    currency = entry.get("currency")
    head_date = date if isinstance(date, str) and date else snapshots[0][0]
    head_cur = currency if isinstance(currency, str) and currency else "?"

    def done(status, caveats):
        return ClaimResolution(status,
                               join_verdict("%s %s %s"
                                            % (head_date, head_cur, status),
                                            caveats),
                               window_days, running_days)

    window_days = 0
    running_days = 0
    claim = entry.get("claim")
    horizon = _usable_horizon(claim)
    if horizon is None:
        return done(STATUS_UNDECIDABLE, ["该观点未登记可机器判定的时限与观测量"])
    horizon_caveat = _horizon_caveat(horizon)
    legs = _usable_legs(claim)
    if legs is None:
        # 不可结构化:**再等也判不出**,没有可求值的观测量,把它压到时限之后
        # 只是把同一句话延后几天说。这一档必须带上是哪一句话不可结构化。
        reason = claim.get("unstructurable_reason")
        detail = reason if isinstance(reason, str) and reason.strip() \
            else "该观点未登记可机器求值的观测量"
        return done(STATUS_UNDECIDABLE, [horizon_caveat, detail])

    window, due = _window(horizon, list(snapshots[1:]))
    window_days = len(window)
    base_snap = snapshots[0][1]
    seen = []
    for leg in legs:
        _, key = read_leg(base_snap, leg)
        seen.append({key} if key is not None else set())

    hit_at = None
    gap_days = 0
    gap_legs = set()
    last_desc = None
    last_repeat_ref = None
    for day_date, snap in window:
        readings = [read_leg(snap, leg) for leg in legs]
        if any(value is None or key is None for value, key in readings):
            gap_days += 1
            for leg, (value, key) in zip(legs, readings):
                if value is None or key is None:
                    gap_legs.add("%s %s" % (leg["currency"],
                                            FIELD_SPECS[leg["field"]][2]))
            continue
        fresh = any(key not in seen[i] for i, (_, key) in enumerate(readings))
        for i, (_, key) in enumerate(readings):
            seen[i].add(key)
        if not fresh:
            # 没有新读数的一天不是运行日 —— 把它算成一次观测,正是修前
            # "两次读数相等 → 无法判定"那条缺陷的源头。
            rate_keys = [key for leg, (_, key) in zip(legs, readings)
                         if FIELD_SPECS[leg["field"]][0] != "macro"]
            last_repeat_ref = rate_keys[0] if rate_keys else None
            continue
        running_days += 1
        last_desc = "、".join(_leg_desc(leg, value)
                             for leg, (value, _) in zip(legs, readings))
        if all(op_holds(leg["op"], value, _parse_threshold(leg["threshold"]))
               for leg, (value, _) in zip(legs, readings)):
            hit_at = (running_days, day_date, last_desc)
            break

    if hit_at is not None:
        idx, day_date, desc = hit_at
        return done(STATUS_HIT,
                    [horizon_caveat, "第 %d 个运行日 %s %s" % (idx, day_date, desc)])
    if not due:
        progress = ("窗口内已过 %d 个运行日、%s" % (running_days, last_desc)
                    if last_desc is not None else "窗口内尚无新定盘")
        return done(STATUS_PENDING, [horizon_caveat, progress])

    required = horizon["n"] if horizon.get("kind") == "running_days" else 1
    if running_days >= required:
        return done(STATUS_MISS,
                    [horizon_caveat,
                     "窗口内 %d 个运行日均未满足、末次 %s"
                     % (running_days, last_desc)])
    # 第四档:时限已到但观测缺失。**必须说清缺的是哪一次观测。**
    caveats = [horizon_caveat,
               "窗口 %d 个运行日只取到 %d 次新定盘" % (required, running_days)]
    if last_repeat_ref is not None:
        caveats.append(unchanged_ref_note(last_repeat_ref))
    if gap_days:
        caveats.append("另有 %d 天取不到 %s 的读数"
                       % (gap_days, "、".join(sorted(gap_legs))))
    return done(STATUS_UNDECIDABLE, caveats)
