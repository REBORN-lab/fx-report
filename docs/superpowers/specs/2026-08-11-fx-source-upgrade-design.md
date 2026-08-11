---
super_coding_change: fx-source-upgrade
role: technical-design
canonical_spec: openspec
archived-with: 2026-08-11-fx-source-upgrade
status: final
---

# Technical Design: fx-source-upgrade

需求规格以 OpenSpec delta spec 为准(`openspec/changes/fx-source-upgrade/specs/`);本文档回答 HOW。
上游依据:2026-08-11 四视角诊断(workflow `wf_e1d49d18-70d`)与同日本机端点探针(结果见 proposal 表格,全部实跑)。

## Architecture

```
python3 -m scripts.collect
  ├─ collect/feeds.py    ← 新增:Fed / ECB 官方 RSS(xml.etree)
  │     → events[<cur>]["official"]  (Fed→USD, ECB→EUR)
  ├─ collect/events.py   (不变,产出 events[<cur>]["articles"])
  ├─ collect/macro.py    + 美国 CPI 走 BLS v1(同比脚本算)+ 全条目 lag_months
  └─ collect/derive.py   (不变;count 仍只数 articles)
```

## Components

**feeds.py** 暴露 `collect(cfg) -> (payload, gaps)`,`payload = {"USD": [item…], "EUR": [item…]}`:
- 源表硬编码两条(`FEEDS = [{"issuer": "Fed", "currency": "USD", "key": "fed_press_rss"}, …]`),URL 从 `cfg["endpoints"]` 取,便于 fixture 注入
- `xml.etree.ElementTree.fromstring` 解析;`ParseError` 与任何异常 → 该源一条 gap
- 逐条取 `title`/`link`/`pubDate`,缺字段的条目跳过而非整源失败;至多 `MAX_ITEMS = 3`
- **不做 XXE 风险处理之外的加固**:`xml.etree` 默认不解析外部实体,标准库行为已足够

**macro.py**:
- `_bls_us_cpi(cfg, gaps)`:取 `Results.series[0].data`,建 `(year, period) -> value` 表,取最新月 `m` 与其同月上年基期;缺基期 → gap + 返回 None(由调用方回落 DBnomics)
- 同比 `round((cur / base - 1) * 100, 3)`;`base == 0` 视为不可用
- `_lag_months(period, date_str)`:解析 `YYYY-MM` / `YYYY-MM-DD` 前 7 位,返回月差;不可解析 → None

## Testing

- feeds:正常两源、单源 404、非 XML 正文、item 缺 title、条数上限、endpoints 缺键
- macro:BLS 正常同比(断言 3 位精度)、同月基期缺失回落、BLS 请求失败回落、非数值/bool 指数值、lag_months 两种期号形态与跨年、不可解析
- 端到端:fixture 注入两源,断言快照 `events.USD.official` 存在且 GDELT 全挂时仍在

## Risks

- BLS 公共 API 无 key 有日配额 → 每日一次,远低于配额;失败有回落
- 探针失败的 BCB/BSP/BOT **不写入配置**:不可达源只会每天刷 gap 噪音;缺口记在 proposal 与 README
