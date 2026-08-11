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
  ├─ collect/rates.py      + rates_ref_date(顶层)/ prev_ref_date(每币种)
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

- `chg_pct_1d`:`round((today − prev) / prev × 100, 3)`;`rates_ref_date == prev_ref_date` 时为 null(参考价未更新不构成价格变动)
- `range_5d_*`:取最近 5 个**不同 ref_date** 的 primary(不足 5 个用现有个数,`range_5d_days` 记实际参与天数);保留原值精度不 round
- `real_rate.value`:`round(policy_rate − cpi, 3)`;双期号原文强制携带,任一缺失整项 null
- `deviation_pct_prev`:上一份快照该币种的 `deviation_pct`,供报告谈"偏差在扩大/收敛"
- `events.count_delta`:当日文章数 − 上一份快照文章数

## Components

**derive.py** 暴露 `derive(payload, history) -> (derived, gaps)`:
- `payload` 为已组装好的当日快照 dict,`history` 为按日期倒序的近 N 份历史快照 list
- 每个子计算独立 try,内部异常 → `util.make_gap("derive", <scope>, ...)` 并该项 null;**绝不向上抛**(与既有采集模块同一硬契约)
- 全部数值访问前过 isinstance 门,bool 排除在数值之外,`math.isfinite` 检查;除法前分母零检查

**rates.py**:`_fetch_primary` 额外返回响应 `date`;`_prev_ref_date` 从 `cfg["prev_snapshot"]` 读 `rates_ref_date`

**events.py**:
- `_query_with_retry` 的重试触发条件扩为 `err == "soft-rate-limited" or "429" in str(err)`
- `DEFAULT_DELAY_S` 5 → 20(`FX_GDELT_DELAY_S` 覆盖保留;spec 下限 ≥5 不变)
- 顺序轮转:`offset = sum(ord(ch) for ch in date) % 5`,对 `list(KEYWORDS.items())` 循环右移
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
