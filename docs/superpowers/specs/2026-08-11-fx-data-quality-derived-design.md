---
super_coding_change: fx-data-quality-derived
role: technical-design
canonical_spec: openspec
---

# Technical Design: fx-data-quality-derived

需求规格以 OpenSpec delta spec 为准(`openspec/changes/fx-data-quality-derived/specs/`);本文档回答 HOW。

上游依据:2026-08-11 四视角诊断(workflow `wf_e1d49d18-70d`,journal 在 `.../subagents/workflows/wf_e1d49d18-70d/`)。该诊断已完成问题空间探索、机制定位(文件:行号级证据)、方案对比与分层,并经实测复核关键计数(12/12 汇率对连平、23 条 gaps 中 20 条 GDELT 429、40 篇文章 tone 非空 0、25 条决策日志 0 命中 0 未命中)。本设计取其"数据底座"一层,故不再重复方案对比。

## Architecture

改动集中在采集层末端与复盘脚本,报告层只增引用通路:

```
python3 -m scripts.collect --date DATE
  ├─ collect/rates.py      + ref_date / prev_ref_date(逐币种)
  ├─ collect/macro.py      (不变)
  ├─ collect/events.py     + 硬 429 重试 / 顺序轮转 / 标题去重 / − tone
  ├─ collect/calendar.py   (不变)
  └─ collect/derive.py     ← 新增,读已成型 payload + 近 N 份历史快照
        → data/DATE.json.derived
scripts/review.py          + ref_date 三分支(连平 → "参考价未更新(非工作日)")
skills/fx-daily-report/SKILL.md
                           + 要点表"派生指标"行、汇率行带 ref_date、− tone_avg 行
                           + 禁算条款改写(derived 可逐字引用)
```

## derived 节 schema

```json
"derived": {
  "schema_version": 1,
  "rates": {
    "PHP": {"chg_pct_1d": -0.192, "range_5d_low": 60.75, "range_5d_high": 60.867,
            "range_5d_days": 4, "deviation_pct_prev": 0.31}
  },
  "real_rate": {
    "PH": {"value": 3.976, "policy_rate": 5.25, "policy_period": "2025-07-04",
           "cpi": 1.27388535031847, "cpi_period": "2025-05"}
  },
  "events": {"PHP": {"count": 0, "count_prev": 0, "count_delta": 0}}
}
```

- `chg_pct_1d`:`round((today − prev) / prev × 100, 3)`;`ref_date == prev_ref_date` 时为 null(参考价未更新不构成价格变动);`prev_ref_date` 未知且两值 bit 级相等时同样为 null(无法区分真持平与没定盘,而 0.0% 会被读成方向结论)
- `range_5d_*`:取最近 5 **次不同定盘**的 primary(定盘身份 = ref_date;存量快照 ref_date 缺失时退回按 primary 值去重,同值即同一次定盘)。历史窗口读 `RANGE_DAYS+4` 份,因为周末/假日让相邻快照共享同一次定盘。保留原值精度不 round
- `real_rate.value`:`round(policy_rate − cpi, 3)`;双期号原文强制携带,任一缺失则 `value` 为 null(键与已知的另一半保留)
- `deviation_pct_prev`:上一份快照该币种的 `deviation_pct`,供报告谈"偏差在扩大/收敛"
- `events.count`:**null 表示该币种事件采集失败,0 表示确实 0 篇** —— 合并二者就是把「没采到」报成「没发生」。覆盖币种取 `rates` 键与 `events.KEYWORDS` 键的并集(后者含基准货币 USD)
- `events.count_delta`:当日文章数 − 最近一份存在的快照的文章数(「前值」口径与 rates 的 prev_primary 不同,后者严格取昨日文件)

## Components

**derive.py** 暴露 `derive(payload, history) -> (derived, gaps)`:
- `payload` 为已组装好的当日快照 dict,`history` 为按日期倒序的近 N 份历史快照 list
- 每个子计算独立 try,内部异常 → `util.make_gap("derive", <scope>, ...)` 并该项 null;**绝不向上抛**(与既有采集模块同一硬契约)
- 全部数值访问前过 isinstance 门,bool 排除在数值之外,`math.isfinite` 检查;除法前分母零检查

**rates.py**:`_fetch_primary` 额外返回响应 `date`;`_prev_ref_date` 返回**逐币种 dict**(全快照共用值去顶替会让 derive 与 review.py 对同一币种给出相反的「参考价未更新」结论);逐币种写 `ref_date`(降级到副源或双源皆失败的币种为 null —— 主源定盘日期对该数值不成立,这是实现期发现的边界,顶层单值表达不了);`_prev_ref_date` 从上一份快照任一币种条目读 `ref_date`

**events.py**:
- 硬限流在 `_fetch` 源头按 `HTTPError.code == 429` 认出并返回哨兵值 `HARD_LIMIT_ERR`;`_is_rate_limited` 只比两个哨兵(不在错误串里搜数字,那会被 `IncompleteRead(429 bytes)` 误伤)
- `DEFAULT_DELAY_S` 5 → 20(`FX_GDELT_DELAY_S` 覆盖保留;spec 下限 ≥5 不变)
- 顺序轮转:`offset = sum(ord(ch) for ch in date) % 5`,对 `list(KEYWORDS)` 循环右移。**这是公平性措施,不是 429 缓解手段** —— 2026-08-11 实测证伪了「限流总落在尾部」的假设(轮转把 BRL 排首位它仍首个 429,位置 2、3 成功)
- 去重:同币种内按 `title` 精确匹配保留首条

**review.py**:新增 ref_date 取值 helper;材料行在"参考价未更新"分支输出专用文案,`direction_outcome` 仍为"无法判定"(不改既有 verdict 语义,只改可读性与 LLM 的判定依据)

## Testing

- 单元:derive 各子计算的正常/缺输入/坏输入(NaN、bool、非数值、分母零)/历史不足;rates ref_date 三态;events 429 重试两态、轮转确定性、去重;review 三分支
- 端到端:构造 fixture 快照跑 `-m scripts.collect`,断言 derived 落盘且 gaps 记录 derive 异常
- 回归:真实跑当日采集 + 要点表,`check_report.py` 不报 NUMBER_UNTRACEABLE(验证 derived 数值天然落在白名单内)

## Risks

- 延迟 20s × 5 币种 ≈ 80s/次 → cron 可接受,`FX_GDELT_DELAY_S` 可下调
- 历史快照无 ref_date/derived → 所有读取带缺失回退,测试专项覆盖"存量快照"
- round 精度漂移 → 精度写入本文与 delta spec 场景,测试断言小数位
