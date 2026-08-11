## Why

2026-08-11 诊断的两条数据源现实:①事件层只有 GDELT,限流时该币种当日归因归零,且"消息源是谁、可信吗"答不出;②DBnomics 镜像的宏观指标全部滞后 219–498 天,`is_new_release` 五天内为 true 的次数是 **0**,"数据发布"栏目对日频报告零增量。

本 change 的取舍由**实测探针**定案(2026-08-11,全部本机实跑):

| 候选源 | 结果 |
|---|---|
| Fed press RSS(press_all / press_monetary) | ✅ 200,monetary feed 首条即 "Federal Reserve issues FOMC statement" |
| ECB press RSS | ✅ 200,10 条 |
| BLS v1 timeseries(零 key) | ✅ 200,最新观测 **2026-06**,比 DBnomics 的 2025-07 新 11 个月 |
| BCB SGS API 与 BCB 新闻 feed | ❌ 全域 HTTP 502,两轮重试一致 |
| BSP RSS / 媒体发布页 | ❌ 404 |
| BOT | ❌ 无 feed,仅 HTML 页 |
| ECB Data Portal HICP | ✅ 200,但最新观测 2025-12 —— **与 DBnomics 同期**,滞后来自源本身,换源无收益 |

## What Changes

- 新增 `scripts/collect/feeds.py`:抓 Fed 与 ECB 官方新闻 RSS(`xml.etree`,零 key),按币种归入 `events[<cur>]["official"]`;失败逐源记 gap,不影响 GDELT 与其余采集
- `macro.py`:美国 CPI 改走 BLS v1(返回指数点位,**同比由脚本按同月同比确定性计算**,不交给 LLM);BLS 失败时回落 DBnomics 并记 gap
- 全部宏观条目新增 `lag_months`(期号相对快照日期的滞后月数,脚本计算):滞后不再隐形,报告可如实说明"该值滞后 N 个月"
- BR/PH/TH/EA **不换源**(探针无更优解),但滞后经 `lag_months` 显式披露
- `skills/fx-daily-report/SKILL.md`:要点表加"官方公告"行(引 `official`,注明发布方);数据发布行要求带滞后月数

## Capabilities

### New Capabilities

无(事件与宏观采集均属既有 `fx-data-collection`)。

### Modified Capabilities

- `fx-data-collection`:事件采集增加央行官方公告通道;宏观采集增加 BLS 主源与滞后披露

## Impact

- 新文件:`scripts/collect/feeds.py`、`tests/test_feeds.py`
- 改动:`scripts/collect/macro.py`、`scripts/collect/__main__.py`、`config/endpoints.json`、`skills/fx-daily-report/SKILL.md`、`tests/test_macro.py`
- `check_report.py` 零改动
