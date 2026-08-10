---
change: fx-daily-report-skill
design-doc: docs/superpowers/specs/2026-08-10-fx-daily-report-skill-design.md
base-ref: 2c7603481407e66b0666b8762d714a4d2e68b700
---

# fx-daily-report-skill 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 零 API key、零第三方依赖的五币种(USD/EUR/PHP/THB/BRL)外汇日报/周报管线:脚本采集数据快照 → LLM 两步生成中文报告 → 校验器强制数字溯源。

**Architecture:** 两段式管线,快照文件 `data/YYYY-MM-DD.json` 是采集段与报告段的唯一接口;报告生成分两步(快照→要点表→叙事),`scripts/review.py` 用两日快照做确定性方向复盘,`scripts/check_report.py` 做结构+数字溯源硬校验。周报独立 skill 读最近 7 天日报按主题重聚类。

**Tech Stack:** Python 3 标准库 only(urllib/json/unittest/http.server),Claude Code skill(SKILL.md),无任何 pip 依赖。

---

## 全局约束(每个任务都必须遵守,不可协商)

1. **Python 3 标准库 only**,测试用 `unittest`。任何任务不得引入 pip 依赖。
2. **endpoint base URL 全部走 `config/endpoints.json`**(完整 URL 模板),代码里不得硬编码线上 URL——故障注入测试靠把模板改写为本地 fixture 服务器地址实现。
3. **GDELT 串行间隔 ≥5 秒**(生产默认值,常量 `DEFAULT_DELAY_S = 5`),且必须识别"HTTP 200 但正文为限速提示"的软失败,退避 30s 重试一次。
4. **报告数字只准逐字来自快照**(经要点表转抄),校验器做文本级逐字比对,禁止任何计算/四舍五入。
5. **LLM 生成报告后必须跑 `scripts/check_report.py`**,不过自修一次,再不过在报告头部标注"未通过自检"照常落盘。
6. 采集模块统一接口 `collect(cfg) -> (payload, gaps)`,任何异常捕获后转 gap 记录,绝不向上抛;单源失败不得中断其余源。
7. 测试命令统一:`python3 -m unittest discover -s tests -t . -v`(在仓库根目录运行)。
8. 每个任务验收通过后立即 commit;协调者按 SuperCoding 规则对 tasks.md 定向勾选(一个 tasks.md 条目由多个计划任务组成时,在其最后一个计划任务通过后勾选)。

## 文件结构总览

```
config/endpoints.json            全部外部 URL 模板(任务 4 创建,含全部 5 个源)
config/indicators.json           DBnomics series 清单(任务 5 实测固化)
state/calendar-2026.json         五央行静态年历(任务 2)
state/decision-log.jsonl         决策日志(运行时生成,append 由脚本代笔)
scripts/__init__.py              包标记(空)
scripts/collect/__init__.py      包标记(空)
scripts/collect/util.py          urllib 封装 + gap 构造(任务 4)
scripts/collect/rates.py         汇率双源采集(任务 4)
scripts/collect/macro.py         DBnomics + FRED 增强(任务 5)
scripts/collect/events.py        GDELT 事件采集(任务 6)
scripts/collect/calendar.py      年历命中判定(任务 7)
scripts/collect/__main__.py      快照聚合主入口(任务 8)
scripts/log_decision.py          决策日志 add/set-review/stats(任务 10)
scripts/review.py                两日快照方向复盘(任务 10)
scripts/check_report.py          报告校验器 daily(任务 12)+ weekly(任务 14)
skills/fx-daily-report/SKILL.md  日报 skill(任务 11)
skills/fx-weekly-report/SKILL.md 周报 skill(任务 14)
.claude/skills/fx-daily-report   → symlink 到 skills/fx-daily-report(任务 11)
.claude/skills/fx-weekly-report  → symlink 到 skills/fx-weekly-report(任务 14)
tests/__init__.py                包标记(空)
tests/helpers.py                 FixtureServer + make_test_cfg + make_test_root(任务 3)
tests/fixtures/gdelt_artlist_sample.json  GDELT 真实形态样例(任务 6)
tests/test_helpers.py            任务 3
tests/test_rates.py              任务 4
tests/test_macro.py              任务 5
tests/test_events.py             任务 6
tests/test_calendar.py           任务 7
tests/test_snapshot.py           任务 8
tests/test_fault_injection.py    任务 9
tests/test_log_decision.py       任务 10
tests/test_review.py             任务 10
tests/test_check_report.py       任务 12 + 任务 14(weekly 部分)
data/  briefs/  reports/daily/  reports/weekly/   输出目录(.gitkeep 占位)
```

## 关键实现决定(执行时不得随意改动;改动须记录理由)

1. **采集入口是 `python3 -m scripts.collect`**,不是设计图里字面的 `python3 scripts/collect.py`——`scripts/collect.py` 文件与 `scripts/collect/` 包同名冲突,而 brainstorm 确认"scripts/collect/ 分模块 + 主入口",故主入口放 `scripts/collect/__main__.py`。SKILL.md、README 一律写 `python3 -m scripts.collect`。
2. **skill 正典位置在 `skills/`(设计文档规定),`.claude/skills/` 放同名 symlink** 让 `claude -p "/fx-daily-report"` 能发现。端到端任务验证发现失败时,改为实体目录放 `.claude/skills/`、`skills/` 放 symlink,并在计划执行记录中注明。
3. **币种节字数上限常量 `MAX_SECTION_CJK = 330`**(spec"约 300 中文字"+10% 容差),只数 CJK 字符(`[一-鿿]`)。
4. **数字溯源校验是文本级逐字比对**:允许集 = 快照 JSON 原文数字串 ∪ 要点表原文数字串 ∪ 0–12 小整数;报告文本先剔除日期模式再抽数字。允许集从原文抽取保证"逐字"语义(60.843 合法、60.84 违规)。
5. **`is_new_release` 判定 = 与前一日快照同 series 的 period 比对**(period 变化即视为新发布);无前日快照时为 False。零 key 路径下 period 充当发布期字段,精确 release date 只在 FRED 增强路径存在。
6. **决策日志一律由脚本代笔**(`scripts/log_decision.py`),LLM 不得直接编辑 jsonl;"append-only"指 LLM 只能通过 add 追加、review 字段只由 `review.py`(direction_outcome)与 `set-review`(judgement/verdict)回填。
7. **USD 观点无对价汇率,方向核对恒为"无法判定"**,`watch_direction` 填 `null`;其余币种 `watch_direction ∈ {"up","down"}`,语义为 USD/该币汇率方向("up"=该币对美元走弱)。
8. **GDELT artlist 的 tone 字段容错**:逐文章读 `tone` 字段,存在则算 `tone_avg`,不存在(GDELT 实际可能不返回)则 `tone_avg: null`,不为此多发请求。
9. **回填支持**:`--date` 不等于今天时,GDELT 用 `startdatetime/enddatetime` 替代 `timespan=48h`(用于周报端到端验收回填 3 天);汇率/宏观本身就是按日期取。
10. **测试提速用环境变量 `FX_GDELT_DELAY_S` / `FX_GDELT_BACKOFF_S` 覆盖延时**;不设时默认 5/30,且有测试断言默认值 ≥5(守住 spec)。

## 与 tasks.md 的对应

| tasks.md | 计划任务 | | tasks.md | 计划任务 |
|---|---|---|---|---|
| 1.1 骨架 | Task 1 | | 3.1 日报 SKILL | Task 11、Task 12(校验器为其组成部分) |
| 1.2 年历 | Task 2 | | 3.2 决策日志+复盘 | Task 10 |
| 2.1 汇率 | Task 4 | | 3.3 日报端到端 | Task 13 |
| 2.2 宏观 | Task 5 | | 4.1 周报 SKILL | Task 14 |
| 2.3 GDELT | Task 6 | | 4.2 周报端到端 | Task 15 |
| 2.4 快照聚合 | Task 7、Task 8 | | 5.1 README | Task 16 |
| 2.5 故障注入测试 | Task 3(基建)、Task 9 | | 5.2 Scenario 核对 | Task 17 |

---

### Task 1: 仓库骨架与目录(tasks.md 1.1)

**Files:**
- Create: `.gitignore`、`README.md`、`scripts/__init__.py`、`scripts/collect/__init__.py`、`tests/__init__.py`、`tests/fixtures/.gitkeep`、`data/.gitkeep`、`briefs/.gitkeep`、`reports/daily/.gitkeep`、`reports/weekly/.gitkeep`、`config/.gitkeep`、`state/.gitkeep`、`skills/.gitkeep`

**验收标准:** 目录树与"文件结构总览"一致;README 有目标概述段;`python3 -m unittest discover -s tests -t .` 可运行(0 个测试也算通过)。

- [x] **Step 1: 建目录与占位文件**

```bash
cd /home/ubuntu/repos-REBORN-lab/macro
mkdir -p scripts/collect skills data briefs reports/daily reports/weekly state config tests/fixtures
touch scripts/__init__.py scripts/collect/__init__.py tests/__init__.py
touch data/.gitkeep briefs/.gitkeep reports/daily/.gitkeep reports/weekly/.gitkeep \
      config/.gitkeep state/.gitkeep skills/.gitkeep tests/fixtures/.gitkeep
```

- [x] **Step 2: 写 `.gitignore`**

```
__pycache__/
*.pyc
.pytest_cache/
```

- [x] **Step 3: 写 `README.md` 目标概述段(运行文档在 Task 16 补全)**

```markdown
# macro — 五币种外汇日报/周报管线

零 API key、零第三方依赖(Python 3 标准库 only)的外汇报告管线:
每日用免费公开数据源(Frankfurter / exchange-api / DBnomics / GDELT / 静态央行年历)
采集 USD 兑 PHP/THB/BRL/EUR 的汇率、宏观指标与事件快照,
再由 Claude Code skill 两步生成中文日报(快照 → 要点表 → 叙事),
报告数字经 `scripts/check_report.py` 强制溯源校验;周报按主题聚合最近 7 天日报。
Slack 推送与 cron 调度由使用者自行接线(范围外)。

(运行文档见下文,由实施任务 16 补全。)
```

- [x] **Step 4: 验证测试骨架可运行**

Run: `python3 -m unittest discover -s tests -t . -v`
Expected: `Ran 0 tests` + `OK`(或 `NO TESTS RAN`,退出码 0/5 均可,只要无 import 错误)

- [x] **Step 5: Commit**

```bash
git add .gitignore README.md scripts tests data briefs reports config state skills
git commit -m "chore(fx): 仓库骨架与输出目录(tasks 1.1)"
```

---

### Task 2: 五央行静态年历(tasks.md 1.2)

**Files:**
- Create: `state/calendar-2026.json`

**验收标准:** spec fx-data-collection"央行议息静态年历对照"的数据前提——文件含 Fed/ECB/BSP/BOT/BCB 五家 2026 年剩余议息日程、`valid_until`、`sources`(每家央行的官方日程 URL)、`maintenance` 说明;`python3 -m json.tool` 通过。

**数据纪律(硬规则):日程日期禁止凭记忆填写。**必须用 WebSearch/WebFetch 逐家查官方日程页(Fed: federalreserve.gov FOMC calendars;ECB: ecb.europa.eu Governing Council schedule;BSP: bsp.gov.ph Monetary Policy calendar;BOT: bot.or.th MPC schedule;BCB: bcb.gov.br COPOM calendário),把来源 URL 记入 `sources`。任何一家查不到官方 2026 日程 → 该行 events 留空并在 `maintenance` 注明,不得填臆测日期;若执行环境无网络搜索能力,暂停此任务并上报用户。

- [x] **Step 1: 逐家央行 WebSearch/WebFetch 取 2026 官方议息日程,记录来源 URL**

- [x] **Step 2: 写 `state/calendar-2026.json`(结构如下,dates 用第 1 步实查结果)**

```json
{
  "valid_until": "2026-12-31",
  "updated_at": "<今日日期>",
  "sources": [
    {"bank": "Fed", "url": "<实查的 FOMC 日程页 URL>"},
    {"bank": "ECB", "url": "<实查 URL>"},
    {"bank": "BSP", "url": "<实查 URL>"},
    {"bank": "BOT", "url": "<实查 URL>"},
    {"bank": "BCB", "url": "<实查 URL>"}
  ],
  "maintenance": "每年 12 月按 sources 官网更新次年日程:新增次年 events、顺延 valid_until;文件名 calendar-<年>.json,采集入口自动取字典序最大的 state/calendar-*.json。",
  "events": [
    {"date": "<YYYY-MM-DD>", "bank": "Fed", "event": "FOMC 议息会议"},
    {"date": "<YYYY-MM-DD>", "bank": "BCB", "event": "COPOM 议息会议"}
  ]
}
```

(`events` 逐条一行一个会议日;两天会议写两条或写决议公布日,按官网口径,并在 event 文本注明。可顺带加入主要统计发布日,如美国 CPI 发布日,`bank` 字段用 `"US-BLS"` 等标识,非必需。)

- [x] **Step 3: 校验 JSON 合法**

Run: `python3 -m json.tool state/calendar-2026.json > /dev/null && echo OK`
Expected: `OK`

- [x] **Step 4: Commit**

```bash
git add state/calendar-2026.json
git commit -m "feat(fx): 五央行 2026 静态议息年历(tasks 1.2)"
```

---

### Task 3: 测试基建 FixtureServer(tasks.md 2.5 前置)

**Files:**
- Create: `tests/helpers.py`、`tests/test_helpers.py`

**验收标准:** 本地 fixture HTTP 服务器可按路径前缀返回定制响应(静态元组或可调用),支撑后续全部故障注入测试(Design"Testing:本地 fixture + 注入")。

- [x] **Step 1: 写 `tests/helpers.py`**

```python
"""测试基建:本地 fixture HTTP 服务器与测试配置构造。零第三方依赖。"""
import http.server
import json
import os
import threading

# 指向必然连接失败的地址,模拟"端点不可用"
DEAD_URL = "http://127.0.0.1:9"


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        for prefix, resp in self.server.fixture_routes.items():
            if self.path.startswith(prefix):
                status, body = resp(self) if callable(resp) else resp
                data = body.encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
        self.send_response(404)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *args):  # 静音测试输出
        pass


class FixtureServer:
    """with FixtureServer({"/frank": (200, '{"rates":{}}')}) as srv: srv.base_url"""

    def __init__(self, routes):
        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self.httpd.fixture_routes = routes
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    @property
    def base_url(self):
        return "http://127.0.0.1:%d" % self.httpd.server_address[1]

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.httpd.shutdown()
        self.httpd.server_close()


def make_test_cfg(**over):
    """采集模块单测用 cfg;延时全 0,线上 URL 全空,由测试逐项覆盖。"""
    cfg = {
        "date": "2026-08-10",
        "yesterday": "2026-08-09",
        "backfill": False,
        "endpoints": {},
        "indicators": [],
        "calendar_path": None,
        "prev_snapshot": None,
        "fred_api_key": None,
        "gdelt_delay_s": 0,
        "gdelt_backoff_s": 0,
        "timeout_s": 5,
        "data_dir": None,
    }
    cfg.update(over)
    return cfg


def make_test_root(tmp, endpoints, indicators=None, calendar=None):
    """聚合/故障注入测试用:构造带 config/ state/ data/ 的临时仓库根。"""
    for d in ("config", "state", "data", "briefs"):
        os.makedirs(os.path.join(tmp, d), exist_ok=True)
    with open(os.path.join(tmp, "config", "endpoints.json"), "w", encoding="utf-8") as f:
        json.dump(endpoints, f)
    with open(os.path.join(tmp, "config", "indicators.json"), "w", encoding="utf-8") as f:
        json.dump(indicators or [], f)
    cal = calendar or {"valid_until": "2099-01-01", "sources": [], "events": []}
    with open(os.path.join(tmp, "state", "calendar-2026.json"), "w", encoding="utf-8") as f:
        json.dump(cal, f, ensure_ascii=False)
    return tmp
```

- [x] **Step 2: 写自测 `tests/test_helpers.py`**

```python
import json
import unittest
import urllib.request
import urllib.error

from tests.helpers import FixtureServer


class FixtureServerTest(unittest.TestCase):
    def test_static_route(self):
        with FixtureServer({"/a": (200, json.dumps({"x": 1}))}) as srv:
            body = urllib.request.urlopen(srv.base_url + "/a?q=1").read()
        self.assertEqual(json.loads(body), {"x": 1})

    def test_callable_route_and_404(self):
        def dyn(handler):
            return (500, "boom") if "bad" in handler.path else (200, "ok")

        with FixtureServer({"/d": dyn}) as srv:
            self.assertEqual(urllib.request.urlopen(srv.base_url + "/d").read(), b"ok")
            with self.assertRaises(urllib.error.HTTPError):
                urllib.request.urlopen(srv.base_url + "/d/bad")
            with self.assertRaises(urllib.error.HTTPError):
                urllib.request.urlopen(srv.base_url + "/none")


if __name__ == "__main__":
    unittest.main()
```

- [x] **Step 3: 跑测试**

Run: `python3 -m unittest discover -s tests -t . -v`
Expected: 2 tests, `OK`

- [x] **Step 4: Commit**

```bash
git add tests/helpers.py tests/test_helpers.py
git commit -m "test(fx): 本地 fixture HTTP 服务器测试基建(tasks 2.5 前置)"
```

---

### Task 4: endpoints.json + 汇率双源采集(tasks.md 2.1)

**Files:**
- Create: `config/endpoints.json`、`scripts/collect/util.py`、`scripts/collect/rates.py`
- Test: `tests/test_rates.py`

**验收标准(spec fx-data-collection"五币种汇率双源采集与交叉校验"):**
- Scenario"双源正常":两源可用且偏差 ≤0.5% → 快照含四对汇率、两源数值、`suspect: false`
- Scenario"主源失败降级":Frankfurter 失败 → 采用 exchange-api 值为当日汇率,gap 记入原因,采集继续
- Scenario"双源偏差超阈":偏差 >0.5% → `suspect: true` 且保留两源数值
- 追加(Design 降级矩阵):双源全挂 → 四币种 `primary: null`,gaps 记两条,不抛异常

- [ ] **Step 1: 写 `config/endpoints.json`(一次写全 5 个源的完整 URL 模板;后续任务不再改动)**

```json
{
  "frankfurter_url": "https://api.frankfurter.dev/v1/{date}?base=USD&symbols=PHP,THB,BRL,EUR",
  "exchange_api_urls": [
    "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@{date}/v1/currencies/usd.json",
    "https://{date}.currency-api.pages.dev/v1/currencies/usd.json"
  ],
  "dbnomics_series_url": "https://api.db.nomics.world/v22/series/{series_id}?observations=1&format=json",
  "gdelt_doc_url": "https://api.gdeltproject.org/api/v2/doc/doc",
  "fred_release_dates_url": "https://api.stlouisfed.org/fred/releases/dates"
}
```

- [ ] **Step 2: 实测线上端点形态并按需修正模板(只改 JSON,不改代码)**

```bash
curl -s "https://api.frankfurter.dev/v1/2026-08-08?base=USD&symbols=PHP,THB,BRL,EUR" | head -c 300; echo
curl -s "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json" | head -c 200; echo
curl -s "https://2026-08-08.currency-api.pages.dev/v1/currencies/usd.json" | head -c 200; echo
```

Expected: 第一条返回 `{"base":"USD",...,"rates":{"PHP":...}}`;后两条返回 `{"date":...,"usd":{...}}`。任何一条形态不符(如 Frankfurter 实为 `/v2/rates?quotes=`)→ 修正 `endpoints.json` 里的模板与(必要时)解析键名,把实测输出粘进 commit message。exchange-api 若日期版本号格式不同(如 `2026.8.8`),在模板里保留 `{date}` 并在 rates.py 的 `_secondary_date()` 做格式转换。

- [ ] **Step 3: 写 `scripts/collect/util.py`**

```python
"""采集层共用:urllib 封装 + gap 构造。标准库 only。"""
import json
import urllib.request
from datetime import datetime, timezone


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def fetch_text(url, timeout_s=20):
    req = urllib.request.Request(url, headers={"User-Agent": "macro-fx-collector/0.1"})
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        return resp.read().decode("utf-8", errors="replace")


def fetch_json(url, timeout_s=20):
    return json.loads(fetch_text(url, timeout_s))


def make_gap(source, scope, reason):
    return {"source": source, "scope": scope, "reason": reason, "at": now_iso()}
```

- [ ] **Step 4: 写失败测试 `tests/test_rates.py`**

```python
import json
import unittest

from scripts.collect import rates
from tests.helpers import DEAD_URL, FixtureServer, make_test_cfg

FRANK = {"base": "USD", "date": "2026-08-10",
         "rates": {"PHP": 60.843, "THB": 35.2, "BRL": 5.43, "EUR": 0.921}}
EXCH = {"date": "2026-08-10",
        "usd": {"php": 60.834, "thb": 35.21, "brl": 5.431, "eur": 0.9211}}


def cfg_with(srv, frank_path="/frank", exch_paths=("/exch",)):
    return make_test_cfg(endpoints={
        "frankfurter_url": srv.base_url + frank_path + "?date={date}",
        "exchange_api_urls": [srv.base_url + p + "?date={date}" for p in exch_paths],
    })


class RatesTest(unittest.TestCase):
    def test_dual_source_ok(self):
        with FixtureServer({"/frank": (200, json.dumps(FRANK)),
                            "/exch": (200, json.dumps(EXCH))}) as srv:
            out, gaps = rates.collect(cfg_with(srv))
        self.assertEqual(gaps, [])
        self.assertEqual(sorted(out), ["BRL", "EUR", "PHP", "THB"])
        self.assertEqual(out["PHP"]["primary"], 60.843)
        self.assertEqual(out["PHP"]["secondary"], 60.834)
        self.assertFalse(out["PHP"]["suspect"])
        self.assertEqual(out["PHP"]["primary_source"], "frankfurter")

    def test_primary_fail_degrades_to_secondary(self):
        with FixtureServer({"/exch": (200, json.dumps(EXCH))}) as srv:
            cfg = cfg_with(srv)
            cfg["endpoints"]["frankfurter_url"] = DEAD_URL + "/frank?date={date}"
            out, gaps = rates.collect(cfg)
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0]["source"], "frankfurter")
        self.assertTrue(gaps[0]["reason"])
        self.assertEqual(out["PHP"]["primary"], 60.834)
        self.assertEqual(out["PHP"]["primary_source"], "exchange-api")

    def test_deviation_over_threshold_marks_suspect(self):
        bad = dict(EXCH, usd=dict(EXCH["usd"], php=62.0))
        with FixtureServer({"/frank": (200, json.dumps(FRANK)),
                            "/exch": (200, json.dumps(bad))}) as srv:
            out, gaps = rates.collect(cfg_with(srv))
        self.assertTrue(out["PHP"]["suspect"])
        self.assertEqual(out["PHP"]["primary"], 60.843)
        self.assertEqual(out["PHP"]["secondary"], 62.0)
        self.assertFalse(out["THB"]["suspect"])

    def test_both_sources_down(self):
        cfg = make_test_cfg(endpoints={
            "frankfurter_url": DEAD_URL + "/f?date={date}",
            "exchange_api_urls": [DEAD_URL + "/e?date={date}"],
        })
        out, gaps = rates.collect(cfg)
        self.assertEqual({g["source"] for g in gaps}, {"frankfurter", "exchange-api"})
        self.assertIsNone(out["PHP"]["primary"])

    def test_secondary_fallback_url_used(self):
        with FixtureServer({"/frank": (200, json.dumps(FRANK)),
                            "/exch2": (200, json.dumps(EXCH))}) as srv:
            cfg = cfg_with(srv, exch_paths=("/nope", "/exch2"))
            out, gaps = rates.collect(cfg)
        self.assertEqual(gaps, [])
        self.assertEqual(out["EUR"]["secondary"], 0.9211)

    def test_prev_primary_from_prev_snapshot(self):
        prev = {"rates": {"PHP": {"primary": 60.9}}}
        with FixtureServer({"/frank": (200, json.dumps(FRANK)),
                            "/exch": (200, json.dumps(EXCH))}) as srv:
            cfg = cfg_with(srv)
            cfg["prev_snapshot"] = prev
            out, _ = rates.collect(cfg)
        self.assertEqual(out["PHP"]["prev_primary"], 60.9)
        self.assertIsNone(out["THB"]["prev_primary"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 5: 跑测试确认失败**

Run: `python3 -m unittest tests.test_rates -v`
Expected: FAIL/ERROR(`rates` 无 `collect`)

- [ ] **Step 6: 写 `scripts/collect/rates.py`**

```python
"""汇率双源采集:Frankfurter 主源 + exchange-api 交叉校验。"""
from . import util

CURRENCIES = ["PHP", "THB", "BRL", "EUR"]
SUSPECT_THRESHOLD_PCT = 0.5  # 偏差 = |主-副|/主 ×100,超过即 suspect


def collect(cfg):
    gaps = []
    primary = _fetch_primary(cfg, gaps)
    secondary = _fetch_secondary(cfg, gaps)
    prev = _prev_primary(cfg)
    out = {}
    for c in CURRENCIES:
        p, s = primary.get(c), secondary.get(c)
        entry = {"primary": p, "secondary": s, "primary_source": "frankfurter",
                 "deviation_pct": None, "suspect": False, "prev_primary": prev.get(c)}
        if p is None and s is not None:
            entry["primary"] = s
            entry["primary_source"] = "exchange-api"
        elif p is not None and s is not None:
            dev = abs(p - s) / p * 100.0
            entry["deviation_pct"] = round(dev, 3)
            entry["suspect"] = dev > SUSPECT_THRESHOLD_PCT
        out[c] = entry
    return out, gaps


def _fetch_primary(cfg, gaps):
    url = cfg["endpoints"]["frankfurter_url"].format(date=cfg["date"])
    try:
        doc = util.fetch_json(url, cfg["timeout_s"])
        got = doc.get("rates", {})
        return {c: float(got[c]) for c in CURRENCIES if c in got}
    except Exception as e:
        gaps.append(util.make_gap("frankfurter", "all", "%s: %s" % (type(e).__name__, e)))
        return {}


def _secondary_date(date_str):
    """exchange-api 的 {date}。若 Step 2 实测其版本号非 YYYY-MM-DD,在此转换。"""
    return date_str


def _fetch_secondary(cfg, gaps):
    last_err = None
    for tpl in cfg["endpoints"]["exchange_api_urls"]:
        url = tpl.format(date=_secondary_date(cfg["date"]))
        try:
            doc = util.fetch_json(url, cfg["timeout_s"])
            usd = doc.get("usd", {})
            got = {c: float(usd[c.lower()]) for c in CURRENCIES if c.lower() in usd}
            if got:
                return got
            last_err = ValueError("empty usd map")
        except Exception as e:
            last_err = e
    gaps.append(util.make_gap("exchange-api", "all",
                              "%s: %s" % (type(last_err).__name__, last_err)))
    return {}


def _prev_primary(cfg):
    snap = cfg.get("prev_snapshot") or {}
    out = {}
    for c, entry in (snap.get("rates") or {}).items():
        if isinstance(entry, dict) and entry.get("primary") is not None:
            out[c] = entry["primary"]
    return out
```

- [ ] **Step 7: 跑测试确认通过**

Run: `python3 -m unittest tests.test_rates -v`
Expected: 6 tests, `OK`

- [ ] **Step 8: Commit**

```bash
git add config/endpoints.json scripts/collect/util.py scripts/collect/rates.py tests/test_rates.py
git commit -m "feat(fx): 汇率双源采集与交叉校验(tasks 2.1)"
```

---

### Task 5: 指标清单固化 + 宏观采集(tasks.md 2.2)

**Files:**
- Create: `config/indicators.json`、`scripts/collect/macro.py`
- Test: `tests/test_macro.py`

**验收标准(spec fx-data-collection"宏观数据增量采集"):**
- Scenario"有新数据发布":跟踪指标出新值 → 快照列出名称/最新值/前值/period,`is_new_release: true`
- Scenario"零 key 默认路径":无 `FRED_API_KEY` → 不调用 FRED,gaps 无 FRED 条目
- Scenario"FRED 增强路径失败":有 key 但 FRED 失败 → gap 记 `fred`,DBnomics 照常
- 追加(Design 降级矩阵):DBnomics 单 series 失败 → 该 series 记 gap,其余照常

- [ ] **Step 1: 实测候选 series ID,固化 `config/indicators.json`**

跑探针脚本(候选 ID 覆盖 五经济体 × CPI 同比/政策利率/外部账户;**FAIL 的条目必须替换,禁止把未验证 ID 写进 config**):

```bash
python3 - <<'EOF'
import json, urllib.request
CANDIDATES = [
    ("US", "CPI 同比",  "IMF/CPI/M.US.PCPI_PC_CP_A_PT"),
    ("EA", "CPI 同比",  "IMF/CPI/M.U2.PCPI_PC_CP_A_PT"),
    ("PH", "CPI 同比",  "IMF/CPI/M.PH.PCPI_PC_CP_A_PT"),
    ("TH", "CPI 同比",  "IMF/CPI/M.TH.PCPI_PC_CP_A_PT"),
    ("BR", "CPI 同比",  "IMF/CPI/M.BR.PCPI_PC_CP_A_PT"),
    ("US", "政策利率",  "BIS/WS_CBPOL_D/D.US"),
    ("EA", "政策利率",  "BIS/WS_CBPOL_D/D.XM"),
    ("PH", "政策利率",  "BIS/WS_CBPOL_D/D.PH"),
    ("TH", "政策利率",  "BIS/WS_CBPOL_D/D.TH"),
    ("BR", "政策利率",  "BIS/WS_CBPOL_D/D.BR"),
    ("US", "经常账户", "IMF/BOP/Q.US.BCA_BP6_USD"),
    ("EA", "经常账户", "IMF/BOP/Q.U2.BCA_BP6_USD"),
    ("PH", "经常账户", "IMF/BOP/Q.PH.BCA_BP6_USD"),
    ("TH", "经常账户", "IMF/BOP/Q.TH.BCA_BP6_USD"),
    ("BR", "经常账户", "IMF/BOP/Q.BR.BCA_BP6_USD"),
]
for eco, name, sid in CANDIDATES:
    url = "https://api.db.nomics.world/v22/series/%s?observations=1&format=json" % sid
    try:
        doc = json.load(urllib.request.urlopen(url, timeout=20))
        d = doc["series"]["docs"][0]
        pairs = [(p, v) for p, v in zip(d["period"], d["value"]) if isinstance(v, (int, float))]
        print("OK  ", eco, name, sid, pairs[-1] if pairs else "EMPTY")
    except Exception as e:
        print("FAIL", eco, name, sid, type(e).__name__, e)
EOF
```

FAIL/EMPTY 的条目用 DBnomics 搜索 API 找替代(`curl -s "https://api.db.nomics.world/v22/search?q=<关键词>&limit=10"`,BIS 政策利率旧代号可试 `BIS/CBPOL/D.<区码>`,BR 可试 BCB provider)。确实找不到的类别 → 从 config 中剔除并在 commit message 与 Task 17 核对表注明,等用户确认。把最终**全部 OK** 的清单写入 `config/indicators.json`:

```json
[
  {"economy": "US", "indicator": "CPI 同比", "series_id": "IMF/CPI/M.US.PCPI_PC_A_PT_或实测替代"},
  {"economy": "US", "indicator": "政策利率", "series_id": "BIS/WS_CBPOL_D/D.US 或实测替代"}
]
```

(15 条为目标;格式三字段固定:economy/indicator/series_id。)

- [ ] **Step 2: 写失败测试 `tests/test_macro.py`**

```python
import json
import unittest

from scripts.collect import macro
from tests.helpers import DEAD_URL, FixtureServer, make_test_cfg

SERIES_OK = {"series": {"docs": [{
    "period": ["2026-05", "2026-06", "2026-07"],
    "value": [3.7, 3.4, 3.1],
}]}}
IND = [{"economy": "PH", "indicator": "CPI 同比", "series_id": "IMF/CPI/M.PH.X"},
       {"economy": "TH", "indicator": "CPI 同比", "series_id": "IMF/CPI/M.TH.X"}]


def cfg_with(srv, **over):
    base = {"endpoints": {
        "dbnomics_series_url": srv.base_url + "/db/{series_id}",
        "fred_release_dates_url": srv.base_url + "/fred",
    }, "indicators": IND}
    base.update(over)
    return make_test_cfg(**base)


class MacroTest(unittest.TestCase):
    def test_latest_prev_and_new_release_flag(self):
        prev_snap = {"macro": [{"series_id": "IMF/CPI/M.PH.X", "period": "2026-06"}]}
        with FixtureServer({"/db/": (200, json.dumps(SERIES_OK))}) as srv:
            cfg = cfg_with(srv, prev_snapshot=prev_snap)
            payload, gaps = macro.collect(cfg)
        self.assertEqual(gaps, [])
        row = payload["indicators"][0]
        self.assertEqual((row["value"], row["prev"], row["period"]), (3.1, 3.4, "2026-07"))
        self.assertTrue(row["is_new_release"])          # period 变化 → 新发布
        self.assertFalse(payload["indicators"][1]["is_new_release"])  # 前快照无此 series

    def test_zero_key_default_path_no_fred_gap(self):
        with FixtureServer({"/db/": (200, json.dumps(SERIES_OK))}) as srv:
            payload, gaps = macro.collect(cfg_with(srv))  # fred_api_key=None
        self.assertEqual([g for g in gaps if g["source"] == "fred"], [])
        self.assertIsNone(payload["us_release_dates"])

    def test_fred_enhancement_failure_recorded(self):
        with FixtureServer({"/db/": (200, json.dumps(SERIES_OK)),
                            "/fred": (500, "err")}) as srv:
            cfg = cfg_with(srv, fred_api_key="k")
            payload, gaps = macro.collect(cfg)
        self.assertEqual([g["source"] for g in gaps], ["fred"])
        self.assertEqual(len(payload["indicators"]), 2)   # DBnomics 照常

    def test_fred_enhancement_success(self):
        fred = {"release_dates": [{"release_id": 10, "release_name": "CPI", "date": "2026-08-09"}]}
        with FixtureServer({"/db/": (200, json.dumps(SERIES_OK)),
                            "/fred": (200, json.dumps(fred))}) as srv:
            cfg = cfg_with(srv, fred_api_key="k")
            payload, gaps = macro.collect(cfg)
        self.assertEqual(gaps, [])
        self.assertEqual(payload["us_release_dates"], ["CPI"])

    def test_single_series_failure_does_not_stop_rest(self):
        def db(handler):
            return (500, "boom") if "M.PH.X" in handler.path else (200, json.dumps(SERIES_OK))

        with FixtureServer({"/db/": db}) as srv:
            payload, gaps = macro.collect(cfg_with(srv))
        self.assertEqual(len(payload["indicators"]), 1)
        self.assertEqual(gaps[0]["source"], "dbnomics")
        self.assertEqual(gaps[0]["scope"], "IMF/CPI/M.PH.X")

    def test_dbnomics_down_entirely(self):
        cfg = make_test_cfg(endpoints={
            "dbnomics_series_url": DEAD_URL + "/db/{series_id}",
            "fred_release_dates_url": DEAD_URL + "/fred",
        }, indicators=IND)
        payload, gaps = macro.collect(cfg)
        self.assertEqual(payload["indicators"], [])
        self.assertEqual(len(gaps), 2)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: 跑测试确认失败**

Run: `python3 -m unittest tests.test_macro -v`
Expected: ERROR(`macro` 无 `collect`)

- [ ] **Step 4: 写 `scripts/collect/macro.py`**

```python
"""宏观指标采集:DBnomics 主体 + FRED release dates 可选增强(零 key 默认路径)。"""
from . import util


def collect(cfg):
    gaps, indicators = [], []
    for ind in cfg["indicators"]:
        try:
            url = cfg["endpoints"]["dbnomics_series_url"].format(series_id=ind["series_id"])
            doc = util.fetch_json(url, cfg["timeout_s"])
            value, prev, period = _last_two(doc)
            indicators.append({
                "economy": ind["economy"], "indicator": ind["indicator"],
                "series_id": ind["series_id"], "value": value, "prev": prev,
                "period": period,
                "is_new_release": _is_new(cfg, ind["series_id"], period),
            })
        except Exception as e:
            gaps.append(util.make_gap("dbnomics", ind["series_id"],
                                      "%s: %s" % (type(e).__name__, e)))
    return {"indicators": indicators, "us_release_dates": _fred(cfg, gaps)}, gaps


def _last_two(doc):
    d = doc["series"]["docs"][0]
    pairs = [(p, v) for p, v in zip(d["period"], d["value"])
             if isinstance(v, (int, float))]
    if not pairs:
        raise ValueError("series has no numeric observations")
    period, value = pairs[-1]
    prev = pairs[-2][1] if len(pairs) >= 2 else None
    return value, prev, period


def _is_new(cfg, series_id, period):
    snap = cfg.get("prev_snapshot") or {}
    for row in snap.get("macro") or []:
        if row.get("series_id") == series_id:
            return row.get("period") != period
    return False


def _fred(cfg, gaps):
    key = cfg.get("fred_api_key")
    if not key:
        return None  # 零 key 默认路径:不调用、不记缺漏(spec Scenario)
    url = ("%s?api_key=%s&file_type=json&realtime_start=%s&realtime_end=%s"
           % (cfg["endpoints"]["fred_release_dates_url"], key,
              cfg["yesterday"], cfg["yesterday"]))
    try:
        doc = util.fetch_json(url, cfg["timeout_s"])
        return [r.get("release_name") or str(r.get("release_id"))
                for r in doc.get("release_dates", [])]
    except Exception as e:
        gaps.append(util.make_gap("fred", "us-release-dates",
                                  "%s: %s" % (type(e).__name__, e)))
        return None
```

注意:`_last_two` 依赖 DBnomics 返回 `series.docs[0].period/value` 平行数组——Step 1 探针已实测该形态;若实测形态不同,以实测为准修正解析并同步修 fixture。

- [ ] **Step 5: 跑测试确认通过**

Run: `python3 -m unittest tests.test_macro -v`
Expected: 6 tests, `OK`

- [ ] **Step 6: Commit**

```bash
git add config/indicators.json scripts/collect/macro.py tests/test_macro.py
git commit -m "feat(fx): DBnomics 宏观采集 + FRED 可选增强,series 清单实测固化(tasks 2.2)"
```

---

### Task 6: GDELT 事件采集(tasks.md 2.3)

**Files:**
- Create: `scripts/collect/events.py`、`tests/fixtures/gdelt_artlist_sample.json`
- Test: `tests/test_events.py`

**验收标准(spec fx-data-collection"前一日事件采集(GDELT)"):**
- Scenario"正常采集":五组关键词串行完成 → 每币种文章列表(title/url/domain/seendate)与 tone
- Scenario"限速软失败退避":HTTP 200 + 限速正文 → 识别软失败、退避重试一次;重试成功正常记录,再失败记缺漏
- Scenario"端点不可用":超时/错误 → 该币种记缺漏(含原因),其余币种继续
- 约束:生产默认串行间隔常量 ≥5 秒(有测试断言守住)

- [ ] **Step 1: 写 fixture `tests/fixtures/gdelt_artlist_sample.json`(GDELT artlist 真实形态样例)**

```json
{
  "articles": [
    {
      "url": "https://example.com/bsp-rate-cut",
      "url_mobile": "",
      "title": "BSP signals possible rate cut in September",
      "seendate": "20260809T120000Z",
      "socialimage": "",
      "domain": "reuters.com",
      "language": "English",
      "sourcecountry": "Philippines"
    },
    {
      "url": "https://example.com/peso-weakens",
      "url_mobile": "",
      "title": "Peso weakens ahead of inflation data",
      "seendate": "20260809T083000Z",
      "socialimage": "",
      "domain": "businessworld.com.ph",
      "language": "English",
      "sourcecountry": "Philippines"
    }
  ]
}
```

- [ ] **Step 2: 写失败测试 `tests/test_events.py`**

```python
import json
import os
import unittest
import urllib.parse

from scripts.collect import events
from tests.helpers import DEAD_URL, FixtureServer, make_test_cfg

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "gdelt_artlist_sample.json")
with open(FIXTURE, encoding="utf-8") as f:
    SAMPLE = f.read()
LIMIT_TEXT = "You have exceeded the rate limit, please try again later."


def cfg_with(srv):
    return make_test_cfg(endpoints={"gdelt_doc_url": srv.base_url + "/doc"})


class EventsTest(unittest.TestCase):
    def test_default_delay_meets_spec(self):
        self.assertGreaterEqual(events.DEFAULT_DELAY_S, 5)   # spec: 串行 ≥5s
        self.assertGreaterEqual(events.DEFAULT_BACKOFF_S, 1)

    def test_normal_collection_all_currencies(self):
        with FixtureServer({"/doc": (200, SAMPLE)}) as srv:
            out, gaps = events.collect(cfg_with(srv))
        self.assertEqual(gaps, [])
        self.assertEqual(sorted(out), ["BRL", "EUR", "PHP", "THB", "USD"])
        art = out["PHP"]["articles"][0]
        self.assertEqual(art["title"], "BSP signals possible rate cut in September")
        self.assertEqual(art["domain"], "reuters.com")
        self.assertIn("tone_avg", out["PHP"])   # tone 字段容错,可为 None

    def test_soft_rate_limit_retry_succeeds(self):
        state = {"n": 0}

        def route(handler):
            state["n"] += 1
            return (200, LIMIT_TEXT) if state["n"] == 1 else (200, SAMPLE)

        with FixtureServer({"/doc": route}) as srv:
            out, gaps = events.collect(cfg_with(srv))
        self.assertEqual(gaps, [])
        self.assertEqual(len(out), 5)

    def test_soft_rate_limit_persistent_becomes_gap(self):
        def route(handler):
            q = urllib.parse.unquote_plus(handler.path)
            if "Thai" in q:
                return (200, LIMIT_TEXT)
            return (200, SAMPLE)

        with FixtureServer({"/doc": route}) as srv:
            out, gaps = events.collect(cfg_with(srv))
        self.assertEqual([g["scope"] for g in gaps], ["THB"])
        self.assertIn("rate-limited", gaps[0]["reason"])
        self.assertNotIn("THB", out)
        self.assertIn("PHP", out)               # 其余币种继续

    def test_endpoint_error_single_currency(self):
        def route(handler):
            q = urllib.parse.unquote_plus(handler.path)
            return (500, "boom") if "Brazilian" in q else (200, SAMPLE)

        with FixtureServer({"/doc": route}) as srv:
            out, gaps = events.collect(cfg_with(srv))
        self.assertEqual([g["scope"] for g in gaps], ["BRL"])
        self.assertEqual(len(out), 4)

    def test_endpoint_down_entirely(self):
        cfg = make_test_cfg(endpoints={"gdelt_doc_url": DEAD_URL + "/doc"})
        out, gaps = events.collect(cfg)
        self.assertEqual(out, {})
        self.assertEqual(len(gaps), 5)          # 五币种各一条,管线不中断

    def test_backfill_uses_datetime_window(self):
        captured = {}

        def route(handler):
            captured["q"] = handler.path
            return (200, SAMPLE)

        with FixtureServer({"/doc": route}) as srv:
            cfg = cfg_with(srv)
            cfg["backfill"] = True
            events.collect(cfg)
        self.assertIn("startdatetime=20260809000000", captured["q"])
        self.assertIn("enddatetime=20260810000000", captured["q"])
        self.assertNotIn("timespan", captured["q"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: 跑测试确认失败**

Run: `python3 -m unittest tests.test_events -v`
Expected: ERROR(`events` 无 `collect`)

- [ ] **Step 4: 写 `scripts/collect/events.py`**

```python
"""GDELT DOC 2.0 事件采集:五币种关键词组串行查询,软限速识别+退避重试一次。"""
import json
import time
import urllib.parse

from . import util

KEYWORDS = {
    "USD": '("Federal Reserve" OR "US dollar")',
    "EUR": '("European Central Bank" OR "euro zone")',
    "PHP": '("Philippine peso" OR "Bangko Sentral")',
    "THB": '("Thai baht" OR "Bank of Thailand")',
    "BRL": '("Brazilian real" OR "Banco Central do Brasil" OR Copom)',
}
DEFAULT_DELAY_S = 5      # spec 硬约束:生产串行间隔 ≥5 秒
DEFAULT_BACKOFF_S = 30   # 软限速退避
RATE_LIMIT_MARKERS = ("rate limit", "too many", "quota", "please try again", "throttl")
MAX_RECORDS = 8


def collect(cfg):
    gaps, out = [], {}
    first = True
    for currency, query in KEYWORDS.items():
        if not first:
            time.sleep(cfg["gdelt_delay_s"])
        first = False
        articles, err = _query_with_retry(cfg, query)
        if err is not None:
            gaps.append(util.make_gap("gdelt", currency, err))
            continue
        tones = [a["tone"] for a in articles if isinstance(a.get("tone"), (int, float))]
        out[currency] = {
            "articles": articles,
            "tone_avg": round(sum(tones) / len(tones), 2) if tones else None,
        }
    return out, gaps


def _query_with_retry(cfg, query):
    articles, err = _fetch(cfg, query)
    if err == "soft-rate-limited":
        time.sleep(cfg["gdelt_backoff_s"])
        articles, err = _fetch(cfg, query)
        if err == "soft-rate-limited":
            return None, "rate-limited after retry"
    return articles, err


def _fetch(cfg, query):
    params = {"query": query, "mode": "artlist", "format": "json",
              "maxrecords": MAX_RECORDS, "sort": "hybridrel"}
    params.update(_window(cfg))
    url = cfg["endpoints"]["gdelt_doc_url"] + "?" + urllib.parse.urlencode(params)
    try:
        text = util.fetch_text(url, cfg["timeout_s"])
    except Exception as e:
        return None, "%s: %s" % (type(e).__name__, e)
    try:
        doc = json.loads(text)
    except ValueError:
        low = text.lower()
        if any(m in low for m in RATE_LIMIT_MARKERS):
            return None, "soft-rate-limited"
        return None, "unparseable response (HTTP 200)"
    arts = [{"title": a.get("title"), "url": a.get("url"), "domain": a.get("domain"),
             "seendate": a.get("seendate"), "tone": a.get("tone")}
            for a in doc.get("articles", [])]
    return arts, None


def _window(cfg):
    if cfg.get("backfill"):
        return {"startdatetime": cfg["yesterday"].replace("-", "") + "000000",
                "enddatetime": cfg["date"].replace("-", "") + "000000"}
    return {"timespan": "48h"}
```

- [ ] **Step 5: 跑测试确认通过**

Run: `python3 -m unittest tests.test_events -v`
Expected: 7 tests, `OK`(延时注入为 0,应在 1 秒内跑完)

- [ ] **Step 6: Commit**

```bash
git add scripts/collect/events.py tests/test_events.py tests/fixtures/gdelt_artlist_sample.json
git commit -m "feat(fx): GDELT 事件采集,软限速退避与串行间隔(tasks 2.3)"
```

---

### Task 7: 年历命中模块(tasks.md 2.4 的年历部分)

**Files:**
- Create: `scripts/collect/calendar.py`
- Test: `tests/test_calendar.py`

**验收标准(spec fx-data-collection"央行议息静态年历对照"):**
- Scenario"昨日为议息日":前一日有议息 → `calendar_hits` 标记 央行名/事件/日期
- 追加(Design):`valid_until` 过期 → gap 提示更新年历(命中判定仍执行);文件缺失/损坏 → gap

- [ ] **Step 1: 写失败测试 `tests/test_calendar.py`**

```python
import json
import os
import tempfile
import unittest

from scripts.collect import calendar as calendar_mod
from tests.helpers import make_test_cfg


def write_cal(tmp, cal):
    path = os.path.join(tmp, "calendar-2026.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cal, f, ensure_ascii=False)
    return path


class CalendarTest(unittest.TestCase):
    def test_yesterday_meeting_hit(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_cal(tmp, {"valid_until": "2099-01-01", "events": [
                {"date": "2026-08-09", "bank": "BCB", "event": "COPOM 议息会议"},
                {"date": "2026-08-10", "bank": "Fed", "event": "FOMC 议息会议"},
                {"date": "2026-09-17", "bank": "BOT", "event": "MPC 议息会议"},
            ]})
            hits, gaps = calendar_mod.collect(make_test_cfg(calendar_path=path))
        self.assertEqual(gaps, [])
        self.assertEqual([(h["date"], h["bank"]) for h in hits],
                         [("2026-08-09", "BCB"), ("2026-08-10", "Fed")])

    def test_no_hits(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_cal(tmp, {"valid_until": "2099-01-01", "events": [
                {"date": "2026-12-09", "bank": "Fed", "event": "FOMC 议息会议"}]})
            hits, gaps = calendar_mod.collect(make_test_cfg(calendar_path=path))
        self.assertEqual((hits, gaps), ([], []))

    def test_expired_calendar_records_gap_but_still_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_cal(tmp, {"valid_until": "2026-01-01", "events": [
                {"date": "2026-08-09", "bank": "BSP", "event": "货币委员会议息"}]})
            hits, gaps = calendar_mod.collect(make_test_cfg(calendar_path=path))
        self.assertEqual(len(hits), 1)
        self.assertEqual(gaps[0]["source"], "calendar")
        self.assertIn("expired", gaps[0]["reason"])

    def test_missing_file_records_gap(self):
        hits, gaps = calendar_mod.collect(make_test_cfg(calendar_path="/nonexistent/c.json"))
        self.assertEqual(hits, [])
        self.assertEqual(gaps[0]["source"], "calendar")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python3 -m unittest tests.test_calendar -v` — Expected: ERROR

- [ ] **Step 3: 写 `scripts/collect/calendar.py`**

```python
"""静态央行年历命中判定:标注昨日/今日议息等日历事件,valid_until 过期告警。"""
import json

from . import util


def collect(cfg):
    gaps, hits = [], []
    try:
        with open(cfg["calendar_path"], encoding="utf-8") as f:
            cal = json.load(f)
    except Exception as e:
        gaps.append(util.make_gap("calendar", "all", "%s: %s" % (type(e).__name__, e)))
        return hits, gaps
    if cfg["date"] > cal.get("valid_until", ""):
        gaps.append(util.make_gap(
            "calendar", "all",
            "calendar expired (valid_until=%s), 请按 README 年历维护说明更新"
            % cal.get("valid_until")))
    watch = {cfg["yesterday"], cfg["date"]}
    for ev in cal.get("events", []):
        if ev.get("date") in watch:
            hits.append({"date": ev["date"], "bank": ev["bank"], "event": ev["event"]})
    return hits, gaps
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python3 -m unittest tests.test_calendar -v` — Expected: 4 tests, `OK`

- [ ] **Step 5: Commit**

```bash
git add scripts/collect/calendar.py tests/test_calendar.py
git commit -m "feat(fx): 年历命中判定与过期告警(tasks 2.4 部分)"
```

---

### Task 8: 快照聚合主入口(tasks.md 2.4)

**Files:**
- Create: `scripts/collect/__main__.py`
- Test: `tests/test_snapshot.py`

**验收标准(spec fx-data-collection"快照落盘与缺漏记录"):**
- Scenario"部分源失败时快照完整":任一源失败 → 其余源照常落盘,gaps 逐条列失败源与原因
- 快照 schema 与 Design 第 2 节一致(date/run_at/schema_version/rates/macro/events/calendar_hits/gaps/meta;FRED 增强时另有 us_release_dates)
- `python3 -m scripts.collect --date D` 写 `data/D.json`,退出码 0(即使有 gaps)

- [ ] **Step 1: 写失败测试 `tests/test_snapshot.py`**

```python
import json
import os
import tempfile
import unittest
from unittest import mock

from scripts.collect import __main__ as entry
from tests.helpers import DEAD_URL, FixtureServer, make_test_root

FRANK = {"rates": {"PHP": 60.843, "THB": 35.2, "BRL": 5.43, "EUR": 0.921}}
EXCH = {"usd": {"php": 60.834, "thb": 35.21, "brl": 5.431, "eur": 0.9211}}
SERIES = {"series": {"docs": [{"period": ["2026-06", "2026-07"], "value": [3.4, 3.1]}]}}
GDELT = {"articles": [{"url": "u", "title": "t", "domain": "d", "seendate": "s"}]}
IND = [{"economy": "PH", "indicator": "CPI 同比", "series_id": "X"}]


def endpoints(srv):
    return {
        "frankfurter_url": srv.base_url + "/frank?d={date}",
        "exchange_api_urls": [srv.base_url + "/exch?d={date}"],
        "dbnomics_series_url": srv.base_url + "/db/{series_id}",
        "gdelt_doc_url": srv.base_url + "/doc",
        "fred_release_dates_url": srv.base_url + "/fred",
    }


ROUTES = {"/frank": (200, json.dumps(FRANK)), "/exch": (200, json.dumps(EXCH)),
          "/db/": (200, json.dumps(SERIES)), "/doc": (200, json.dumps(GDELT))}


@mock.patch.dict(os.environ, {"FX_GDELT_DELAY_S": "0", "FX_GDELT_BACKOFF_S": "0"})
class SnapshotTest(unittest.TestCase):
    def test_all_sources_ok_snapshot_schema(self):
        with tempfile.TemporaryDirectory() as tmp, FixtureServer(dict(ROUTES)) as srv:
            make_test_root(tmp, endpoints(srv), indicators=IND, calendar={
                "valid_until": "2099-01-01",
                "events": [{"date": "2026-08-09", "bank": "BCB", "event": "COPOM 议息会议"}]})
            rc = entry.main(["--date", "2026-08-10", "--root", tmp])
            self.assertEqual(rc, 0)
            with open(os.path.join(tmp, "data", "2026-08-10.json"), encoding="utf-8") as f:
                snap = json.load(f)
        self.assertEqual(snap["date"], "2026-08-10")
        self.assertEqual(snap["schema_version"], 1)
        self.assertEqual(snap["rates"]["PHP"]["primary"], 60.843)
        self.assertEqual(snap["macro"][0]["value"], 3.1)
        self.assertEqual(len(snap["events"]), 5)
        self.assertEqual(snap["calendar_hits"][0]["bank"], "BCB")
        self.assertEqual(snap["gaps"], [])
        self.assertIn("collector_version", snap["meta"])
        self.assertNotIn("us_release_dates", snap)   # 零 key 不出现该键

    def test_one_source_down_others_intact(self):
        with tempfile.TemporaryDirectory() as tmp, FixtureServer(dict(ROUTES)) as srv:
            eps = endpoints(srv)
            eps["dbnomics_series_url"] = DEAD_URL + "/db/{series_id}"
            make_test_root(tmp, eps, indicators=IND)
            rc = entry.main(["--date", "2026-08-10", "--root", tmp])
            self.assertEqual(rc, 0)                  # 单源失败不中断
            with open(os.path.join(tmp, "data", "2026-08-10.json"), encoding="utf-8") as f:
                snap = json.load(f)
        self.assertEqual(snap["macro"], [])
        self.assertEqual([g["source"] for g in snap["gaps"]], ["dbnomics"])
        self.assertTrue(snap["gaps"][0]["reason"])
        self.assertEqual(snap["rates"]["EUR"]["primary"], 0.921)
        self.assertEqual(len(snap["events"]), 5)

    def test_prev_snapshot_feeds_prev_primary(self):
        with tempfile.TemporaryDirectory() as tmp, FixtureServer(dict(ROUTES)) as srv:
            make_test_root(tmp, endpoints(srv), indicators=IND)
            prev = {"date": "2026-08-09", "rates": {"PHP": {"primary": 60.9}}, "macro": []}
            with open(os.path.join(tmp, "data", "2026-08-09.json"), "w", encoding="utf-8") as f:
                json.dump(prev, f)
            entry.main(["--date", "2026-08-10", "--root", tmp])
            with open(os.path.join(tmp, "data", "2026-08-10.json"), encoding="utf-8") as f:
                snap = json.load(f)
        self.assertEqual(snap["rates"]["PHP"]["prev_primary"], 60.9)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python3 -m unittest tests.test_snapshot -v` — Expected: ERROR(无 `__main__.main`)

- [ ] **Step 3: 写 `scripts/collect/__main__.py`**

```python
"""快照聚合主入口:python3 -m scripts.collect --date YYYY-MM-DD(默认今天,UTC)。
单源失败绝不中断;全部结果 + gaps 落盘 data/YYYY-MM-DD.json,退出码 0。"""
import argparse
import glob
import json
import os
import sys
from datetime import date, timedelta

from . import calendar as calendar_mod
from . import events, macro, rates, util

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
COLLECTOR_VERSION = "0.1.0"


def build_cfg(date_str, root=ROOT):
    with open(os.path.join(root, "config", "endpoints.json"), encoding="utf-8") as f:
        endpoints = json.load(f)
    with open(os.path.join(root, "config", "indicators.json"), encoding="utf-8") as f:
        indicators = json.load(f)
    d = date.fromisoformat(date_str)
    yesterday = (d - timedelta(days=1)).isoformat()
    data_dir = os.path.join(root, "data")
    prev_snapshot = None
    prev_path = os.path.join(data_dir, yesterday + ".json")
    if os.path.exists(prev_path):
        with open(prev_path, encoding="utf-8") as f:
            prev_snapshot = json.load(f)
    cals = sorted(glob.glob(os.path.join(root, "state", "calendar-*.json")))
    return {
        "date": date_str,
        "yesterday": yesterday,
        "backfill": date_str != date.today().isoformat(),
        "endpoints": endpoints,
        "indicators": indicators,
        "data_dir": data_dir,
        "calendar_path": cals[-1] if cals else os.path.join(root, "state", "calendar-2026.json"),
        "prev_snapshot": prev_snapshot,
        "fred_api_key": os.environ.get("FRED_API_KEY"),
        # FX_GDELT_*_S 仅测试提速用;生产不设,落在 spec 要求的默认值上
        "gdelt_delay_s": float(os.environ.get("FX_GDELT_DELAY_S", events.DEFAULT_DELAY_S)),
        "gdelt_backoff_s": float(os.environ.get("FX_GDELT_BACKOFF_S", events.DEFAULT_BACKOFF_S)),
        "timeout_s": 20,
    }


def run(cfg):
    gaps = []

    def call(mod, name, default):
        try:
            payload, g = mod.collect(cfg)
            gaps.extend(g)
            return payload
        except Exception as e:  # 模块级兜底:绝不让一个源的意外中断其余源
            gaps.append(util.make_gap(name, "all",
                                      "internal error %s: %s" % (type(e).__name__, e)))
            return default

    rates_p = call(rates, "rates", {})
    macro_p = call(macro, "macro", {"indicators": [], "us_release_dates": None})
    events_p = call(events, "gdelt", {})
    hits = call(calendar_mod, "calendar", [])
    snapshot = {
        "date": cfg["date"], "run_at": util.now_iso(), "schema_version": 1,
        "rates": rates_p, "macro": macro_p["indicators"], "events": events_p,
        "calendar_hits": hits, "gaps": gaps,
        "meta": {"collector_version": COLLECTOR_VERSION},
    }
    if macro_p.get("us_release_dates") is not None:
        snapshot["us_release_dates"] = macro_p["us_release_dates"]
    return snapshot


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python3 -m scripts.collect")
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument("--root", default=ROOT, help=argparse.SUPPRESS)  # 测试注入用
    args = ap.parse_args(argv)
    cfg = build_cfg(args.date, args.root)
    snapshot = run(cfg)
    os.makedirs(cfg["data_dir"], exist_ok=True)
    out_path = os.path.join(cfg["data_dir"], args.date + ".json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)
    print("snapshot: %s" % out_path)
    print("gaps: %d" % len(snapshot["gaps"]))
    for g in snapshot["gaps"]:
        print("  - [%s/%s] %s" % (g["source"], g["scope"], g["reason"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python3 -m unittest tests.test_snapshot -v` — Expected: 3 tests, `OK`

- [ ] **Step 5: 全量回归**

Run: `python3 -m unittest discover -s tests -t . -v`
Expected: 此前全部测试 + 本任务 3 个,全 `OK`

- [ ] **Step 6: Commit**

```bash
git add scripts/collect/__main__.py tests/test_snapshot.py
git commit -m "feat(fx): 快照聚合主入口,单源失败不中断(tasks 2.4)"
```

---

### Task 9: 采集层故障注入矩阵测试(tasks.md 2.5)

**Files:**
- Create: `tests/test_fault_injection.py`

**验收标准:** 逐源故障注入下,其余源照常采集且 gaps 符合 spec 场景(覆盖"主源失败降级""端点不可用""部分源失败时快照完整"的**聚合层**表现;单模块行为已在任务 4–7 覆盖)。本任务全部走 `python3 -m scripts.collect` 真实入口(唯一差别是 endpoints 指向 fixture)。

- [ ] **Step 1: 写测试 `tests/test_fault_injection.py`**

```python
"""聚合层故障注入矩阵:每次打掉一个源,断言其余源完好、gaps 精确。"""
import json
import os
import tempfile
import unittest
from unittest import mock

from scripts.collect import __main__ as entry
from tests.helpers import DEAD_URL, FixtureServer, make_test_root

FRANK = {"rates": {"PHP": 60.843, "THB": 35.2, "BRL": 5.43, "EUR": 0.921}}
EXCH = {"usd": {"php": 60.834, "thb": 35.21, "brl": 5.431, "eur": 0.9211}}
SERIES = {"series": {"docs": [{"period": ["2026-06", "2026-07"], "value": [3.4, 3.1]}]}}
GDELT = {"articles": [{"url": "u", "title": "t", "domain": "d", "seendate": "s"}]}
IND = [{"economy": "PH", "indicator": "CPI 同比", "series_id": "X"}]
ROUTES = {"/frank": (200, json.dumps(FRANK)), "/exch": (200, json.dumps(EXCH)),
          "/db/": (200, json.dumps(SERIES)), "/doc": (200, json.dumps(GDELT))}


def endpoints(srv):
    return {
        "frankfurter_url": srv.base_url + "/frank?d={date}",
        "exchange_api_urls": [srv.base_url + "/exch?d={date}"],
        "dbnomics_series_url": srv.base_url + "/db/{series_id}",
        "gdelt_doc_url": srv.base_url + "/doc",
        "fred_release_dates_url": srv.base_url + "/fred",
    }


def run_with(eps_mutator, calendar=None):
    with tempfile.TemporaryDirectory() as tmp, FixtureServer(dict(ROUTES)) as srv:
        eps = endpoints(srv)
        eps_mutator(eps)
        make_test_root(tmp, eps, indicators=IND, calendar=calendar)
        rc = entry.main(["--date", "2026-08-10", "--root", tmp])
        with open(os.path.join(tmp, "data", "2026-08-10.json"), encoding="utf-8") as f:
            return rc, json.load(f)


@mock.patch.dict(os.environ, {"FX_GDELT_DELAY_S": "0", "FX_GDELT_BACKOFF_S": "0"})
class FaultMatrixTest(unittest.TestCase):
    def test_frankfurter_down(self):
        rc, snap = run_with(lambda e: e.update(frankfurter_url=DEAD_URL + "/f?d={date}"))
        self.assertEqual(rc, 0)
        self.assertEqual([g["source"] for g in snap["gaps"]], ["frankfurter"])
        self.assertEqual(snap["rates"]["PHP"]["primary"], 60.834)      # 副源顶上
        self.assertEqual(snap["rates"]["PHP"]["primary_source"], "exchange-api")
        self.assertEqual(snap["macro"][0]["value"], 3.1)

    def test_exchange_api_down(self):
        rc, snap = run_with(lambda e: e.update(exchange_api_urls=[DEAD_URL + "/e?d={date}"]))
        self.assertEqual([g["source"] for g in snap["gaps"]], ["exchange-api"])
        self.assertEqual(snap["rates"]["PHP"]["primary"], 60.843)      # 主源不受影响
        self.assertIsNone(snap["rates"]["PHP"]["secondary"])

    def test_both_rate_sources_down(self):
        rc, snap = run_with(lambda e: e.update(
            frankfurter_url=DEAD_URL + "/f?d={date}",
            exchange_api_urls=[DEAD_URL + "/e?d={date}"]))
        self.assertEqual({g["source"] for g in snap["gaps"]},
                         {"frankfurter", "exchange-api"})
        self.assertIsNone(snap["rates"]["PHP"]["primary"])             # 当日无汇率
        self.assertEqual(len(snap["events"]), 5)                       # 其余源完好

    def test_dbnomics_down(self):
        rc, snap = run_with(lambda e: e.update(dbnomics_series_url=DEAD_URL + "/db/{s}".replace("{s}", "{series_id}")))
        self.assertEqual([g["source"] for g in snap["gaps"]], ["dbnomics"])
        self.assertEqual(snap["macro"], [])
        self.assertEqual(snap["rates"]["EUR"]["primary"], 0.921)

    def test_gdelt_down(self):
        rc, snap = run_with(lambda e: e.update(gdelt_doc_url=DEAD_URL + "/doc"))
        self.assertEqual([g["source"] for g in snap["gaps"]],
                         ["gdelt"] * 5)                                # 五币种各一条
        self.assertEqual(snap["events"], {})
        self.assertEqual(snap["rates"]["PHP"]["primary"], 60.843)

    def test_calendar_expired(self):
        rc, snap = run_with(lambda e: None, calendar={
            "valid_until": "2026-01-01",
            "events": [{"date": "2026-08-09", "bank": "BSP", "event": "货币委员会议息"}]})
        self.assertEqual([g["source"] for g in snap["gaps"]], ["calendar"])
        self.assertIn("expired", snap["gaps"][0]["reason"])
        self.assertEqual(snap["calendar_hits"][0]["bank"], "BSP")      # 仍执行命中


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 跑本文件测试**

Run: `python3 -m unittest tests.test_fault_injection -v` — Expected: 6 tests, `OK`

- [ ] **Step 3: 全量回归并记录实测数字**

Run: `python3 -m unittest discover -s tests -t . -v`
Expected: 全部 `OK`。**把命令输出的实际测试数抄进 commit message(硬规则:先跑后抄,禁止先写预期)。**

- [ ] **Step 4: Commit**

```bash
git add tests/test_fault_injection.py
git commit -m "test(fx): 聚合层逐源故障注入矩阵(tasks 2.5)——unittest 实测 N 项全过(N 抄自输出)"
```

---

### Task 10: 决策日志脚本 + 复盘脚本(tasks.md 3.2)

**Files:**
- Create: `scripts/log_decision.py`、`scripts/review.py`
- Test: `tests/test_log_decision.py`、`tests/test_review.py`

**验收标准(spec fx-daily-report"决策日志与次日复盘"):**
- Scenario"存在前日日志":有前一运行日观点 → 复盘材料逐币种注入要点表,`direction_outcome` 由脚本按 `sign(今 primary − 昨 primary)` vs `watch_direction` 确定性回填
- Scenario"首次运行无日志":日志缺失/为空 → 要点表注明"首次运行,无历史观点可复盘",退出码 0
- Design 测试要求四用例:方向命中/未命中/昨日无观点/首次运行
- 日志只由脚本写(add / set-review / review.py 回填),LLM 不直接碰 jsonl

- [ ] **Step 1: 写失败测试 `tests/test_log_decision.py`**

```python
import json
import os
import subprocess
import sys
import tempfile
import unittest

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "scripts", "log_decision.py")


def run_cmd(args, stdin_text=None):
    return subprocess.run([sys.executable, SCRIPT] + args, input=stdin_text,
                          capture_output=True, text=True)


def read_log(root):
    path = os.path.join(root, "state", "decision-log.jsonl")
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


ENTRY = {"date": "2026-08-10", "currency": "PHP",
         "scenario": "BSP 鸽派信号推动宽松预期",
         "trigger": "BSP 官员再释降息信号", "watch_direction": "up"}


class LogDecisionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.makedirs(os.path.join(self.tmp.name, "state"))

    def tearDown(self):
        self.tmp.cleanup()

    def test_add_appends_with_empty_review(self):
        r = run_cmd(["add", "--root", self.tmp.name], json.dumps([ENTRY]))
        self.assertEqual(r.returncode, 0, r.stderr)
        log = read_log(self.tmp.name)
        self.assertEqual(log[0]["currency"], "PHP")
        self.assertEqual(log[0]["review"],
                         {"direction_outcome": None, "trigger_judgement": None, "verdict": None})

    def test_add_rejects_missing_field(self):
        bad = {k: v for k, v in ENTRY.items() if k != "trigger"}
        r = run_cmd(["add", "--root", self.tmp.name], json.dumps([bad]))
        self.assertEqual(r.returncode, 2)

    def test_add_allows_null_watch_direction_for_usd(self):
        usd = dict(ENTRY, currency="USD", watch_direction=None)
        r = run_cmd(["add", "--root", self.tmp.name], json.dumps([usd]))
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_set_review_fills_judgement_and_verdict(self):
        run_cmd(["add", "--root", self.tmp.name], json.dumps([ENTRY]))
        r = run_cmd(["set-review", "--root", self.tmp.name, "--date", "2026-08-10",
                     "--currency", "PHP", "--judgement", "快照事件含 BSP 降息报道",
                     "--verdict", "命中"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(read_log(self.tmp.name)[0]["review"]["verdict"], "命中")

    def test_set_review_unknown_entry_fails(self):
        r = run_cmd(["set-review", "--root", self.tmp.name, "--date", "2026-08-10",
                     "--currency", "THB", "--judgement", "x", "--verdict", "命中"])
        self.assertEqual(r.returncode, 2)

    def test_stats_counts_by_command(self):
        run_cmd(["add", "--root", self.tmp.name],
                json.dumps([ENTRY, dict(ENTRY, currency="THB")]))
        run_cmd(["set-review", "--root", self.tmp.name, "--date", "2026-08-10",
                 "--currency", "PHP", "--judgement", "j", "--verdict", "命中"])
        r = run_cmd(["stats", "--root", self.tmp.name,
                     "--from", "2026-08-04", "--to", "2026-08-10"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("命中 1 / 未命中 0 / 无法判定 0 / 未判定 1", r.stdout)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 写失败测试 `tests/test_review.py`**

```python
import json
import os
import subprocess
import sys
import tempfile
import unittest

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "scripts", "review.py")


def setup_root(tmp, log_entries=None, snapshots=None, brief_date="2026-08-10"):
    for d in ("state", "data", "briefs"):
        os.makedirs(os.path.join(tmp, d), exist_ok=True)
    if log_entries is not None:
        with open(os.path.join(tmp, "state", "decision-log.jsonl"), "w", encoding="utf-8") as f:
            for e in log_entries:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
    for date_str, snap in (snapshots or {}).items():
        with open(os.path.join(tmp, "data", date_str + ".json"), "w", encoding="utf-8") as f:
            json.dump(snap, f)
    brief = os.path.join(tmp, "briefs", brief_date + "-brief.md")
    with open(brief, "w", encoding="utf-8") as f:
        f.write("# 要点表 %s\n" % brief_date)
    return brief


def run_review(tmp, date="2026-08-10"):
    return subprocess.run([sys.executable, SCRIPT, "--date", date, "--root", tmp],
                          capture_output=True, text=True)


def opinion(**over):
    base = {"date": "2026-08-09", "currency": "PHP", "scenario": "s", "trigger": "t",
            "watch_direction": "up",
            "review": {"direction_outcome": None, "trigger_judgement": None, "verdict": None}}
    base.update(over)
    return base


def snap(php_primary):
    return {"rates": {"PHP": {"primary": php_primary}}}


class ReviewTest(unittest.TestCase):
    def _run(self, entries, snapshots):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        brief = setup_root(tmp.name, entries, snapshots)
        r = run_review(tmp.name)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(brief, encoding="utf-8") as f:
            text = f.read()
        log_path = os.path.join(tmp.name, "state", "decision-log.jsonl")
        log = []
        if os.path.exists(log_path):
            with open(log_path, encoding="utf-8") as f:
                log = [json.loads(l) for l in f if l.strip()]
        return text, log

    def test_direction_hit(self):
        text, log = self._run([opinion()],
                              {"2026-08-09": snap(60.0), "2026-08-10": snap(60.5)})
        self.assertIn("方向核对: 命中", text)
        self.assertEqual(log[0]["review"]["direction_outcome"], "命中")

    def test_direction_miss(self):
        text, log = self._run([opinion(watch_direction="down")],
                              {"2026-08-09": snap(60.0), "2026-08-10": snap(60.5)})
        self.assertIn("方向核对: 未命中", text)
        self.assertEqual(log[0]["review"]["direction_outcome"], "未命中")

    def test_missing_rate_undecidable(self):
        text, log = self._run([opinion()],
                              {"2026-08-09": snap(60.0), "2026-08-10": snap(None)})
        self.assertIn("无法判定", text)
        self.assertEqual(log[0]["review"]["direction_outcome"], "无法判定")

    def test_no_pending_opinions_yesterday(self):
        reviewed = opinion()
        reviewed["review"]["direction_outcome"] = "命中"
        text, _ = self._run([reviewed],
                            {"2026-08-09": snap(60.0), "2026-08-10": snap(60.5)})
        self.assertIn("无未复盘观点", text)

    def test_first_run_no_log(self):
        text, _ = self._run(None, {"2026-08-10": snap(60.5)})
        self.assertIn("首次运行,无历史观点可复盘", text)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: 跑两个测试文件确认失败**

Run: `python3 -m unittest tests.test_log_decision tests.test_review -v` — Expected: 全 ERROR/FAIL(脚本不存在)

- [ ] **Step 4: 写 `scripts/log_decision.py`**

```python
#!/usr/bin/env python3
"""决策日志唯一写入口(LLM 经此脚本代笔,禁止直接编辑 jsonl)。
add        : stdin 传 JSON 数组,校验后追加(review 三字段置 null)
set-review : 回填指定 date+currency 的 trigger_judgement 与 verdict
stats      : 按日期区间输出 命中/未命中/无法判定/未判定 计数与明细"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REQUIRED = ("date", "currency", "scenario", "trigger", "watch_direction")
VERDICTS = ("命中", "未命中", "无法判定")


def log_path(root):
    return os.path.join(root, "state", "decision-log.jsonl")


def load(root):
    p = log_path(root)
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def save(root, entries):
    p = log_path(root)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    os.replace(tmp, p)


def cmd_add(args):
    try:
        items = json.load(sys.stdin)
    except ValueError as e:
        print("stdin 不是合法 JSON: %s" % e, file=sys.stderr)
        return 2
    if not isinstance(items, list):
        print("需要 JSON 数组", file=sys.stderr)
        return 2
    for it in items:
        missing = [k for k in REQUIRED if k not in it]
        if missing:
            print("缺字段 %s: %s" % (missing, it), file=sys.stderr)
            return 2
        if it["watch_direction"] not in ("up", "down", None):
            print("watch_direction 须为 up/down/null: %s" % it, file=sys.stderr)
            return 2
        it["review"] = {"direction_outcome": None, "trigger_judgement": None,
                        "verdict": None}
    entries = load(args.root)
    entries.extend(items)
    save(args.root, entries)
    print("appended %d entries" % len(items))
    return 0


def cmd_set_review(args):
    if args.verdict not in VERDICTS:
        print("verdict 须为 %s" % (VERDICTS,), file=sys.stderr)
        return 2
    entries = load(args.root)
    for e in entries:
        if (e["date"] == args.date and e["currency"] == args.currency
                and e.get("review", {}).get("verdict") is None):
            e.setdefault("review", {})
            e["review"]["trigger_judgement"] = args.judgement
            e["review"]["verdict"] = args.verdict
            save(args.root, entries)
            print("review set: %s %s -> %s" % (args.date, args.currency, args.verdict))
            return 0
    print("未找到待复盘条目 %s/%s" % (args.date, args.currency), file=sys.stderr)
    return 2


def cmd_stats(args):
    counts = {"命中": 0, "未命中": 0, "无法判定": 0, "未判定": 0}
    detail = []
    for e in load(args.root):
        if args.date_from <= e["date"] <= args.date_to:
            v = (e.get("review") or {}).get("verdict")
            key = v if v in counts else "未判定"
            counts[key] += 1
            detail.append("  - %s %s %s" % (e["date"], e["currency"], v or "未判定"))
    print("命中 %(命中)d / 未命中 %(未命中)d / 无法判定 %(无法判定)d / 未判定 %(未判定)d"
          % counts)
    for line in detail:
        print(line)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("add")
    p.add_argument("--root", default=ROOT)
    p.set_defaults(fn=cmd_add)
    p = sub.add_parser("set-review")
    p.add_argument("--date", required=True)
    p.add_argument("--currency", required=True)
    p.add_argument("--judgement", required=True)
    p.add_argument("--verdict", required=True)
    p.add_argument("--root", default=ROOT)
    p.set_defaults(fn=cmd_set_review)
    p = sub.add_parser("stats")
    p.add_argument("--from", dest="date_from", required=True)
    p.add_argument("--to", dest="date_to", required=True)
    p.add_argument("--root", default=ROOT)
    p.set_defaults(fn=cmd_stats)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: 写 `scripts/review.py`**

```python
#!/usr/bin/env python3
"""混合复盘的确定性一半:用两日快照算汇率方向,回填 direction_outcome,
并把复盘材料追加进当日要点表。触发条件是否发生由 LLM 判定(SKILL 第 4 步)。"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_log(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def save_log(path, entries):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def load_snapshot(data_dir, date_str):
    p = os.path.join(data_dir, date_str + ".json")
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def rate_of(snap, currency):
    if not snap:
        return None
    entry = (snap.get("rates") or {}).get(currency) or {}
    return entry.get("primary")


def direction_outcome(prev_rate, today_rate, watch_direction):
    if prev_rate is None or today_rate is None or watch_direction not in ("up", "down"):
        return "无法判定"
    if today_rate == prev_rate:
        return "无法判定"
    actual = "up" if today_rate > prev_rate else "down"
    return "命中" if actual == watch_direction else "未命中"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True)
    ap.add_argument("--root", default=ROOT)
    args = ap.parse_args(argv)
    log_path = os.path.join(args.root, "state", "decision-log.jsonl")
    data_dir = os.path.join(args.root, "data")
    brief_path = os.path.join(args.root, "briefs", args.date + "-brief.md")
    if not os.path.exists(brief_path):
        print("要点表不存在: %s(须先执行 SKILL 第 2 步)" % brief_path, file=sys.stderr)
        return 1

    entries = load_log(log_path)
    lines = ["", "## 复盘材料(scripts/review.py 生成,勿手改)", ""]
    prior_dates = sorted({e["date"] for e in entries if e["date"] < args.date})
    if not prior_dates:
        lines.append("- 首次运行,无历史观点可复盘")
    else:
        target = prior_dates[-1]
        prev_snap = load_snapshot(data_dir, target)
        today_snap = load_snapshot(data_dir, args.date)
        pending = [e for e in entries
                   if e["date"] == target
                   and (e.get("review") or {}).get("direction_outcome") is None]
        if not pending:
            lines.append("- 上一运行日(%s)无未复盘观点" % target)
        for e in pending:
            prev_r = rate_of(prev_snap, e["currency"])
            today_r = rate_of(today_snap, e["currency"])
            oc = direction_outcome(prev_r, today_r, e.get("watch_direction"))
            e.setdefault("review", {})["direction_outcome"] = oc
            lines.append(
                "- %s | 观点日 %s | 情景: %s | 触发条件: %s | 关注方向: %s"
                " | 汇率 %s→%s | 方向核对: %s"
                % (e["currency"], target, e["scenario"], e["trigger"],
                   e.get("watch_direction"), prev_r, today_r, oc))
        save_log(log_path, entries)
    with open(brief_path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("review material appended to %s" % brief_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 6: 跑测试确认通过**

Run: `python3 -m unittest tests.test_log_decision tests.test_review -v`
Expected: 11 tests, `OK`

- [ ] **Step 7: Commit**

```bash
git add scripts/log_decision.py scripts/review.py tests/test_log_decision.py tests/test_review.py
git commit -m "feat(fx): 决策日志脚本代笔 + 两日快照方向复盘(tasks 3.2)"
```

---

### Task 11: 日报 skill(tasks.md 3.1)

**Files:**
- Create: `skills/fx-daily-report/SKILL.md`
- Create: `.claude/skills/fx-daily-report`(symlink)

**验收标准(spec fx-daily-report 全部 Requirement 的操作化载体):** SKILL.md 完整编排五步管线;内嵌日报模板(执行摘要 ≤6 条 → 五币种节 ≤约 300 字 → 复盘节 → 数据缺漏节)与全部禁令;数字纪律与"生成后必须跑 check_report.py"逐字写入。真实报告质量在 Task 13 端到端验收。

- [ ] **Step 1: 写 `skills/fx-daily-report/SKILL.md`(以下为完整内容)**

````markdown
---
name: fx-daily-report
description: 生成五币种(USD/EUR/PHP/THB/BRL)中文外汇日报。先跑采集脚本得数据快照,再两步生成(快照→要点表→叙事),数字强制溯源校验。可选参数:日期 YYYY-MM-DD,默认今天(UTC)。
---

# 外汇日报生成

严格按五步顺序执行,任何一步不得跳过。数字纪律条款不可协商。
设 DATE = 参数给出的日期(YYYY-MM-DD);未给参数时 DATE = 今天(UTC)。
全部命令在仓库根目录执行。

## 第 1 步:采集快照(脚本)

运行:`python3 -m scripts.collect --date DATE`

确认 `data/DATE.json` 已生成;**若不存在,立即终止并报错**——采集是前置步骤,
禁止在无快照时生成报告。命令输出的 gaps 列表记下,后面缺漏节要用。

## 第 2 步:生成要点表(LLM,产物落盘)

只读 `data/DATE.json`,写 `briefs/DATE-brief.md`,模板:

    # 要点表 DATE

    ## 跨币种共同主线
    -(≤3 条候选,基于快照事件与年历命中归纳)

    ## USD
    - 昨日事件 top:<title>(<domain>)……至多 3 条;tone_avg: <值或 无>
    - 数据发布:<indicator> 最新 <value> 前值 <prev> 期 <period>(只列 is_new_release
      为 true 或与年历命中相关的;没有写"无")
    - 汇率变动:primary <primary>,prev <prev_primary>(USD 为基准货币,本行写"—")
    - 年历命中:<bank> <event>(<date>)(没有写"无")
    - 缺漏:<gaps 中 scope 为本币种或 all 的条目>(没有写"无")

    ## EUR
    (同 USD 结构;汇率行填 EUR 的 primary/prev_primary)

    ## PHP / ## THB / ## BRL
    (同上,各一节)

    ## 快照缺漏总表
    - [<source>/<scope>] <reason>(逐条照抄快照 gaps;为空写"无")

**数字纪律:要点表中每个数字必须从快照 JSON 逐字复制**(60.843 就写 60.843,
不得写 60.84)。禁止计算涨跌幅、百分比、差值;禁止写快照里不存在的任何数字。
rates 中 suspect 为 true 的币种,汇率行须注明"(双源偏差超阈,数据可疑,
主源 <primary> / 副源 <secondary>)"。

## 第 3 步:注入复盘材料(脚本)

运行:`python3 scripts/review.py --date DATE`

它把"## 复盘材料"追加到要点表末尾,并回填决策日志的 direction_outcome。

## 第 4 步:生成日报(LLM)

**只依据 `briefs/DATE-brief.md`(含复盘材料)**写 `reports/daily/DATE.md`,模板:

    # 外汇日报 DATE

    ## 执行摘要
    -(≤6 条,每条一句话;跨币种共同主线优先)

    ## 美元(USD)
    **昨日发生**:……
    **定价含义**:……
    **情景与触发条件**:若 <触发条件>,则关注 <方向/影响>。

    ## 欧元(EUR)
    (同结构;随后 ## 菲律宾比索(PHP)、## 泰铢(THB)、## 巴西雷亚尔(BRL))

    ## 复盘
    -(逐币种一句话:对照复盘材料中前一运行日观点、触发判定与方向核对结果;
      复盘材料写"首次运行"时,本节正文写"首次运行,无历史观点可复盘")

    ## 数据缺漏
    - [<source>/<scope>] <reason> — 影响:<对哪些结论打折扣>
    (逐条对应要点表"快照缺漏总表";总表为"无"时本节正文恰为一个字:无)

**禁令(违反任何一条即校验失败):**
1. 禁止无条件方向预测——所有观点必须是"若 X 发生则关注 Y"的情景+触发条件式。
2. 数字只准逐字抄自要点表(其唯一源头是快照);禁止计算、估算、回忆任何行情数字。
3. 缺漏节列出的数据,正文禁止引用或臆测(该币种如实写"昨日无××数据(采集失败)")。
4. 市场共识/预期值只在 GDELT 文章标题明说时可用,且必须标"据报道"转引。
5. 禁止逐条罗列快照原始数据(流水账);只呈现驱动结论的关键数字。
6. 无明确驱动的币种如实写"昨日无明确驱动",不编造归因。
7. 每币种节正文不超过约 300 中文字;执行摘要不超过 6 条。

**决策日志(写完报告立即执行,经脚本代笔,禁止直接编辑 jsonl):**
把当日五币种"情景与触发条件"整理成 JSON 数组,经 stdin 传入:

    python3 scripts/log_decision.py add <<'EOF'
    [{"date": "DATE", "currency": "PHP", "scenario": "<情景一句话>",
      "trigger": "<触发条件一句话>", "watch_direction": "up|down"},
     {"date": "DATE", "currency": "USD", "scenario": "…", "trigger": "…",
      "watch_direction": null}]
    EOF

watch_direction 语义:USD/该币汇率方向,"up"=该币对美元走弱;USD 自身填 null。

**复盘判定(要点表含复盘材料时执行):**对复盘材料中每条观点,依据**当日要点表
里的证据**判断触发条件是否发生,逐条运行:

    python3 scripts/log_decision.py set-review --date <观点日> --currency <币> \
      --judgement "<引用要点表证据的一句话>" --verdict <命中|未命中|无法判定>

verdict 规则:触发条件未发生 → 无法判定;触发发生且方向核对=命中 → 命中;
触发发生且方向核对=未命中 → 未命中;引不出证据 → 无法判定。

## 第 5 步:校验(脚本,不可跳过)

运行:
`python3 scripts/check_report.py reports/daily/DATE.md data/DATE.json --brief briefs/DATE-brief.md --mode daily`

- 退出码 0:完成,输出报告路径,结束。
- 非 0:按输出的违规项修改报告**一次**(仍只准用要点表数字),重跑校验。
- 第二次仍非 0:在报告首行前插入一行
  `> ⚠ 本报告未通过自动自检:<违规项摘要>`,保留落盘,如实结束。
````

- [ ] **Step 2: 建 `.claude/skills` symlink**

```bash
cd /home/ubuntu/repos-REBORN-lab/macro
mkdir -p .claude/skills
ln -sfn ../../skills/fx-daily-report .claude/skills/fx-daily-report
ls -l .claude/skills/fx-daily-report/SKILL.md
```

Expected: 能列出 SKILL.md(symlink 解析成功)。失败则按"关键实现决定 2"反向放置。

- [ ] **Step 3: Commit**

```bash
git add skills/fx-daily-report/SKILL.md .claude/skills/fx-daily-report
git commit -m "feat(fx): 日报 skill 五步编排,模板+禁令+数字纪律(tasks 3.1)"
```

---

### Task 12: 报告校验器 daily 模式(tasks.md 3.1/3.3 支撑;Design"校验器")

**Files:**
- Create: `scripts/check_report.py`
- Test: `tests/test_check_report.py`

**验收标准(spec fx-daily-report"数字纪律/数据缺漏显式披露/简明扼要约束"的机器可查子集):**
- Scenario"数字可溯源":报告数字(剔除日期)⊆ 快照原文数字 ∪ 要点表原文数字 ∪ 0–12
- Scenario"缺漏日披露"/"无缺漏日":gaps 非空 → 缺漏节逐条提及;gaps 空 → 节正文恰为"无"
- Scenario"篇幅合规":摘要 ≤6 条;币种节 CJK ≤330(约 300+容差)
- 结构:五币种节 + 执行摘要 + 复盘 + 数据缺漏 齐全;违规退出码 1、逐条打印;合规退出码 0

- [ ] **Step 1: 写失败测试 `tests/test_check_report.py`(daily 部分)**

```python
import json
import unittest

from scripts import check_report

SNAP = {"date": "2026-08-10",
        "rates": {"PHP": {"primary": 60.843, "prev_primary": 60.9},
                  "THB": {"primary": 35.2}, "BRL": {"primary": 5.43},
                  "EUR": {"primary": 0.921}},
        "macro": [{"indicator": "CPI 同比", "value": 3.1, "prev": 3.4,
                   "period": "2026-07"}],
        "events": {}, "calendar_hits": [], "gaps": []}
SNAP_TEXT = json.dumps(SNAP, ensure_ascii=False)
BRIEF = "# 要点表 2026-08-10\n- 汇率变动:primary 60.843,prev 60.9\n- CPI 3.1 前值 3.4\n"


def make_report(summary_items=3, missing=None, php_body=None, gap_body="无",
                extra_number=None):
    lines = ["# 外汇日报 2026-08-10", "", "## 执行摘要"]
    lines += ["- 摘要第 %d 条" % (i + 1) for i in range(summary_items)]
    sections = {
        "美元(USD)": "**昨日发生**:无明确驱动。**定价含义**:观望。"
                      "**情景与触发条件**:若有 FOMC 信号,则关注美元流动性。",
        "欧元(EUR)": "**昨日发生**:无明确驱动。**情景与触发条件**:若 ECB 表态,则关注 0.921 附近波动。",
        "菲律宾比索(PHP)": php_body or (
            "**昨日发生**:CPI 同比 3.1,前值 3.4。**定价含义**:通胀回落。"
            "**情景与触发条件**:若 BSP 释放降息信号,则关注 60.843 上方压力。"),
        "泰铢(THB)": "**昨日发生**:无明确驱动。**情景与触发条件**:若出口数据走弱,则关注 35.2 附近。",
        "巴西雷亚尔(BRL)": "**昨日发生**:无明确驱动。**情景与触发条件**:若 COPOM 表态,则关注 5.43。",
    }
    for name, body in sections.items():
        if missing and missing in name:
            continue
        lines += ["", "## " + name, body]
    lines += ["", "## 复盘", "- 首次运行,无历史观点可复盘"]
    lines += ["", "## 数据缺漏", gap_body]
    if extra_number:
        lines.append("另外汇率大约是 %s。" % extra_number)
    return "\n".join(lines)


class CheckDailyTest(unittest.TestCase):
    def test_valid_report_passes(self):
        v = check_report.check_daily(make_report(), SNAP_TEXT, BRIEF)
        self.assertEqual(v, [])

    def test_missing_currency_section(self):
        v = check_report.check_daily(make_report(missing="THB"), SNAP_TEXT, BRIEF)
        self.assertTrue(any("THB" in x and "SECTION_MISSING" in x for x in v))

    def test_summary_too_long(self):
        v = check_report.check_daily(make_report(summary_items=7), SNAP_TEXT, BRIEF)
        self.assertTrue(any("SUMMARY_TOO_LONG" in x for x in v))

    def test_section_too_long(self):
        long_body = "很" * 400 + "。**情景与触发条件**:若如此,则关注。"
        v = check_report.check_daily(make_report(php_body=long_body), SNAP_TEXT, BRIEF)
        self.assertTrue(any("SECTION_TOO_LONG" in x and "PHP" in x for x in v))

    def test_untraceable_number(self):
        v = check_report.check_daily(make_report(extra_number="99.99"), SNAP_TEXT, BRIEF)
        self.assertTrue(any("NUMBER_UNTRACEABLE" in x and "99.99" in x for x in v))

    def test_dates_are_not_flagged(self):
        v = check_report.check_daily(make_report(), SNAP_TEXT, BRIEF)
        self.assertFalse(any("NUMBER_UNTRACEABLE" in x for x in v))  # 2026-08-10 被剔除

    def test_gaps_not_disclosed(self):
        snap = dict(SNAP, gaps=[{"source": "gdelt", "scope": "THB",
                                 "reason": "rate-limited after retry", "at": "x"}])
        v = check_report.check_daily(make_report(gap_body="无"),
                                     json.dumps(snap, ensure_ascii=False), BRIEF)
        self.assertTrue(any("GAPS_NOT_DISCLOSED" in x for x in v))

    def test_gap_scope_must_be_mentioned(self):
        snap = dict(SNAP, gaps=[{"source": "gdelt", "scope": "THB",
                                 "reason": "rate-limited after retry", "at": "x"}])
        report = make_report(gap_body="- [gdelt/THB] rate-limited after retry — 影响:泰铢事件面结论缺依据")
        v = check_report.check_daily(report, json.dumps(snap, ensure_ascii=False), BRIEF)
        self.assertFalse(any("GAP" in x for x in v))

    def test_empty_gaps_section_must_say_none(self):
        v = check_report.check_daily(make_report(gap_body="- [gdelt/THB] 编造的缺漏"),
                                     SNAP_TEXT, BRIEF)
        self.assertTrue(any("GAPS_MISMATCH" in x for x in v))


class MainExitCodeTest(unittest.TestCase):
    def test_exit_codes(self):
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            rp = os.path.join(tmp, "r.md")
            sp = os.path.join(tmp, "s.json")
            bp = os.path.join(tmp, "b.md")
            with open(sp, "w", encoding="utf-8") as f:
                f.write(SNAP_TEXT)
            with open(bp, "w", encoding="utf-8") as f:
                f.write(BRIEF)
            with open(rp, "w", encoding="utf-8") as f:
                f.write(make_report())
            self.assertEqual(check_report.main([rp, sp, "--brief", bp, "--mode", "daily"]), 0)
            with open(rp, "w", encoding="utf-8") as f:
                f.write(make_report(missing="THB"))
            self.assertEqual(check_report.main([rp, sp, "--brief", bp, "--mode", "daily"]), 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python3 -m unittest tests.test_check_report -v` — Expected: ERROR(模块不存在)

- [ ] **Step 3: 写 `scripts/check_report.py`(daily 模式;weekly 在 Task 14 扩展)**

```python
#!/usr/bin/env python3
"""报告校验器:结构 + 数字溯源(文本级逐字比对)。
daily : check_report.py <report.md> <snapshot.json> --brief <brief.md> --mode daily
退出码 0=合规,1=违规(逐条打印),2=用法错误。"""
import argparse
import json
import re
import sys

CURRENCIES = ["USD", "EUR", "PHP", "THB", "BRL"]
MAX_SUMMARY_ITEMS = 6
MAX_SECTION_CJK = 330        # spec“约 300 中文字”+10% 容差
DATE_RE = re.compile(
    r"\d{4}-W\d{2}|\d{4}-\d{2}-\d{2}|\d{4}\s*年|\d{1,2}\s*月\s*\d{1,2}\s*日|\d{1,2}\s*月")
NUM_RE = re.compile(r"\d+(?:\.\d+)?")
CJK_RE = re.compile(r"[一-鿿]")
ALLOWED_SMALL = {str(i) for i in range(0, 13)}   # 序数/条数/月份类小整数
LIST_ITEM_RE = re.compile(r"\s*(?:[-*]|\d+[.、])\s+\S")


def sections(md):
    out, cur, buf = [], None, []
    for line in md.splitlines():
        if line.startswith("## "):
            if cur is not None:
                out.append((cur, "\n".join(buf)))
            cur, buf = line[3:].strip(), []
        elif cur is not None:
            buf.append(line)
    if cur is not None:
        out.append((cur, "\n".join(buf)))
    return out


def find_section(secs, key):
    for h, b in secs:
        if key in h:
            return h, b
    return None


def numbers_in(text):
    return set(NUM_RE.findall(DATE_RE.sub(" ", text)))


def list_items(body):
    return [l for l in body.splitlines() if LIST_ITEM_RE.match(l)]


def check_daily(report, snapshot_text, brief_text):
    v = []
    secs = sections(report)
    snap = json.loads(snapshot_text)

    for c in CURRENCIES:
        if not find_section(secs, c):
            v.append("SECTION_MISSING: 缺少币种节 %s" % c)
    s = find_section(secs, "执行摘要")
    if not s:
        v.append("SECTION_MISSING: 缺少执行摘要")
    elif len(list_items(s[1])) > MAX_SUMMARY_ITEMS:
        v.append("SUMMARY_TOO_LONG: 执行摘要 %d 条 > %d"
                 % (len(list_items(s[1])), MAX_SUMMARY_ITEMS))
    for c in CURRENCIES:
        sec = find_section(secs, c)
        if sec:
            n = len(CJK_RE.findall(sec[1]))
            if n > MAX_SECTION_CJK:
                v.append("SECTION_TOO_LONG: %s 节 %d 中文字 > %d" % (c, n, MAX_SECTION_CJK))
    rev = find_section(secs, "复盘")
    if not rev or not rev[1].strip():
        v.append("SECTION_MISSING: 缺少复盘节(首次运行也须保留并注明)")

    gap_sec = find_section(secs, "数据缺漏")
    gaps = snap.get("gaps", [])
    if not gap_sec:
        v.append("SECTION_MISSING: 缺少数据缺漏节")
    else:
        body = gap_sec[1].strip()
        if gaps and (not body or body == "无"):
            v.append("GAPS_NOT_DISCLOSED: 快照有 %d 条缺漏但缺漏节为空/无" % len(gaps))
        if not gaps and body != "无":
            v.append("GAPS_MISMATCH: 快照无缺漏,缺漏节应恰为“无”")
        for g in gaps:
            token = g.get("scope") if g.get("scope") not in (None, "all") else g.get("source")
            if token and token not in gap_sec[1]:
                v.append("GAP_OMITTED: 缺漏节未提及 %s/%s" % (g.get("source"), g.get("scope")))

    allowed = numbers_in(snapshot_text) | numbers_in(brief_text) | ALLOWED_SMALL
    for n in sorted(numbers_in(report) - allowed):
        v.append("NUMBER_UNTRACEABLE: 数字 %s 不见于快照或要点表" % n)
    return v


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("report")
    ap.add_argument("snapshot", nargs="?")
    ap.add_argument("--brief", default=None)
    ap.add_argument("--mode", choices=["daily", "weekly"], default="daily")
    args = ap.parse_args(argv)
    with open(args.report, encoding="utf-8") as f:
        report = f.read()
    if args.mode == "daily":
        if not args.snapshot:
            print("daily 模式需要快照路径", file=sys.stderr)
            return 2
        with open(args.snapshot, encoding="utf-8") as f:
            snapshot_text = f.read()
        brief_text = ""
        if args.brief:
            with open(args.brief, encoding="utf-8") as f:
                brief_text = f.read()
        violations = check_daily(report, snapshot_text, brief_text)
    else:
        violations = check_weekly(report)   # Task 14 实现
    if violations:
        print("CHECK FAILED (%d):" % len(violations))
        for x in violations:
            print(" - " + x)
        return 1
    print("CHECK PASSED")
    return 0


def check_weekly(report):
    raise NotImplementedError("weekly 模式在周报任务实现")


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python3 -m unittest tests.test_check_report -v` — Expected: 10 tests, `OK`

- [ ] **Step 5: Commit**

```bash
git add scripts/check_report.py tests/test_check_report.py
git commit -m "feat(fx): 报告校验器 daily 模式,结构+数字逐字溯源(design 校验器)"
```

---

### Task 13: 日报端到端验收(tasks.md 3.3)

**Files:**
- 产物: `data/<今日>.json`、`briefs/<今日>-brief.md`、`reports/daily/<今日>.md`、`state/decision-log.jsonl`

**验收标准:**
- spec"数据齐全的正常日"(或当日实际 gaps 情形下的对应场景)、"数字可溯源"、"缺漏日披露/无缺漏日"、"首次运行无日志"、"篇幅合规"在真实产物上成立
- 全部数字与快照逐字一致(校验器 + 人工抽查双重确认);缺漏节如实;`claude -p` 无头模式全程无人工干预

前置:真实网络可达。GDELT 串行 5s,采集约需 ≥25s,属正常。

- [ ] **Step 1: 真实运行日报 skill**

```bash
cd /home/ubuntu/repos-REBORN-lab/macro
claude -p "/fx-daily-report" --permission-mode acceptEdits
```

Expected: 依次完成五步;终端可见 `python3 -m scripts.collect` 的 gaps 输出与 `CHECK PASSED`(或自修流程)。若 skill 未被发现("Unknown skill"),按"关键实现决定 2"调整 symlink 方向后重跑。

- [ ] **Step 2: 复跑校验器,独立确认退出码(不信任 skill 转述)**

```bash
D=$(date -u +%F)
python3 scripts/check_report.py reports/daily/$D.md data/$D.json --brief briefs/$D-brief.md --mode daily; echo "exit=$?"
```

Expected: `CHECK PASSED` + `exit=0`。若报告头部带"未通过自检"标注,列出违规项交用户决策,不得静默接受。

- [ ] **Step 3: 人工抽查清单(逐项核对,结果写进 commit message)**

```bash
D=$(date -u +%F)
# 1) 从报告中抽出现的 3 个行情数字,逐一在快照中逐字查找:
grep -o '[0-9]\+\.[0-9]\+' reports/daily/$D.md | sort -u | head -5
grep -F "<上面抽的数字>" data/$D.json
# 2) 缺漏节与快照 gaps 对照:
python3 -c "import json;print(json.load(open('data/$D.json'))['gaps'])"
sed -n '/## 数据缺漏/,$p' reports/daily/$D.md
# 3) 决策日志已追加当日观点:
grep -c "\"date\": \"$D\"" state/decision-log.jsonl
# 4) 复盘节存在(首次运行应注明"首次运行"):
sed -n '/## 复盘/,/## 数据缺漏/p' reports/daily/$D.md
```

核对项:抽查数字全部逐字命中快照;缺漏节与 gaps 一一对应;日志条数=5(五币种);复盘节符合首次运行/正常日预期;叙事无"无条件方向预测"。任何一项不符 → 加载 systematic-debugging 定位(区分 SKILL.md 措辞问题 vs 校验器漏检),修复后重跑本任务。

- [ ] **Step 4: Commit(产物入库)**

```bash
D=$(date -u +%F)
git add data/$D.json briefs/$D-brief.md reports/daily/$D.md state/decision-log.jsonl
git commit -m "feat(fx): 首次端到端日报验收通过(tasks 3.3)——抽查结果:<逐项实测结果>"
```

---

### Task 14: 周报 skill + 校验器 weekly 模式(tasks.md 4.1)

**Files:**
- Create: `skills/fx-weekly-report/SKILL.md`、`.claude/skills/fx-weekly-report`(symlink)
- Modify: `scripts/check_report.py`(实现 `check_weekly`,替换 NotImplementedError)
- Test: `tests/test_check_report.py`(追加 weekly 用例)

**验收标准(spec fx-weekly-report 全部 Requirement):**
- Scenario"正常周聚合":一级结构为主题(本周主线 ≤3/各币种归因/复盘汇总/下周关注/缺漏汇总),非日期
- Scenario"日报不足":<3 份 → 开头注明覆盖天数与缺失日期(校验器查"覆盖日报:N 份"声明)
- Scenario"周内有缺漏日":缺漏汇总列出日期与缺失内容
- Scenario"观点复盘汇总":命中/未命中/无法判定 计数与明细(计数来自 `log_decision.py stats`,禁止心算)

- [ ] **Step 1: 追加 weekly 失败测试到 `tests/test_check_report.py`**

```python
def make_weekly(coverage="覆盖日报:5 份(2026-08-04 至 2026-08-08);缺失日期:无",
                theme_items=3, date_heading=False, drop=None,
                review_body="- 命中 2 / 未命中 1 / 无法判定 2\n- 2026-08-05 PHP 命中"):
    lines = ["# 外汇周报 2026-W32", "", "> " + coverage if coverage else "", ""]
    lines += ["## 本周主线"] + ["- 主线 %d" % (i + 1) for i in range(theme_items)]
    if date_heading:
        lines += ["", "## 2026-08-05", "当日流水"]
    body = {
        "各币种一周归因": "USD 观望;EUR 震荡;PHP 通胀回落主导;THB 出口疲弱;BRL 政策预期反复。",
        "复盘汇总": review_body,
        "下周关注": "- 关注五央行表态",
        "缺漏汇总": "- 2026-08-06: [gdelt/THB] rate-limited after retry",
    }
    for name, b in body.items():
        if name != drop:
            lines += ["", "## " + name, b]
    return "\n".join(lines)


class CheckWeeklyTest(unittest.TestCase):
    def test_valid_weekly_passes(self):
        self.assertEqual(check_report.check_weekly(make_weekly()), [])

    def test_date_heading_forbidden(self):
        v = check_report.check_weekly(make_weekly(date_heading=True))
        self.assertTrue(any("DATE_STRUCTURE" in x for x in v))

    def test_coverage_declaration_required(self):
        v = check_report.check_weekly(make_weekly(coverage=""))
        self.assertTrue(any("COVERAGE_MISSING" in x for x in v))

    def test_low_coverage_needs_missing_dates(self):
        v = check_report.check_weekly(
            make_weekly(coverage="覆盖日报:2 份(2026-08-04、2026-08-05)"))
        self.assertTrue(any("COVERAGE_GAP_DATES" in x for x in v))

    def test_theme_limit(self):
        v = check_report.check_weekly(make_weekly(theme_items=4))
        self.assertTrue(any("THEME_TOO_MANY" in x for x in v))

    def test_review_tokens_required(self):
        v = check_report.check_weekly(make_weekly(review_body="- 表现不错"))
        self.assertTrue(any("REVIEW_TOKEN_MISSING" in x for x in v))

    def test_missing_weekly_section(self):
        v = check_report.check_weekly(make_weekly(drop="缺漏汇总"))
        self.assertTrue(any("SECTION_MISSING" in x and "缺漏汇总" in x for x in v))
```

(放在文件末尾、`if __name__` 之前;`make_weekly` 为模块级函数。)

- [ ] **Step 2: 跑测试确认失败**

Run: `python3 -m unittest tests.test_check_report -v` — Expected: weekly 用例 ERROR(NotImplementedError)

- [ ] **Step 3: 在 `scripts/check_report.py` 用以下实现替换 `check_weekly` 占位**

```python
MAX_THEME_ITEMS = 3
WEEKLY_SECTIONS = ["本周主线", "各币种", "复盘汇总", "下周关注", "缺漏汇总"]
COVERAGE_RE = re.compile(r"覆盖日报[::]\s*(\d+)\s*份")
DATE_HEADING_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")


def check_weekly(report):
    v = []
    secs = sections(report)
    for key in WEEKLY_SECTIONS:
        if not find_section(secs, key):
            v.append("SECTION_MISSING: 缺少 %s 节" % key)
    ml = find_section(secs, "本周主线")
    if ml and len(list_items(ml[1])) > MAX_THEME_ITEMS:
        v.append("THEME_TOO_MANY: 本周主线 %d 条 > %d"
                 % (len(list_items(ml[1])), MAX_THEME_ITEMS))
    for h, _ in secs:
        if DATE_HEADING_RE.match(h):
            v.append("DATE_STRUCTURE: 一级结构含日期标题 %s(必须按主题组织)" % h)
    m = COVERAGE_RE.search(report)
    if not m:
        v.append("COVERAGE_MISSING: 缺少“覆盖日报:N 份”声明")
    elif int(m.group(1)) < 3 and "缺失日期" not in report:
        v.append("COVERAGE_GAP_DATES: 覆盖不足 3 份但未注明缺失日期")
    for c in CURRENCIES:
        if c not in report:
            v.append("CURRENCY_MISSING: 周报未覆盖 %s" % c)
    rs = find_section(secs, "复盘汇总")
    if rs:
        for tok in ("命中", "未命中", "无法判定"):
            if tok not in rs[1]:
                v.append("REVIEW_TOKEN_MISSING: 复盘汇总缺少“%s”" % tok)
    return v
```

(常量与正则放到文件顶部常量区;删除 `raise NotImplementedError` 版本。)

- [ ] **Step 4: 跑测试确认通过**

Run: `python3 -m unittest tests.test_check_report -v` — Expected: 17 tests, `OK`

- [ ] **Step 5: 写 `skills/fx-weekly-report/SKILL.md`(完整内容)**

````markdown
---
name: fx-weekly-report
description: 聚合最近 7 个自然日的外汇日报与决策日志,按主题重聚类生成中文周报(本周主线/各币种归因/复盘汇总/下周关注/缺漏汇总),结构强制校验。
---

# 外汇周报生成

设 TODAY = 今天(UTC),WEEK = TODAY 的 ISO 周号(格式 YYYY-Www,如 2026-W33,
用 `date -u +%G-W%V` 取得)。输出 `reports/weekly/WEEK.md`。

## 第 1 步:收集素材(脚本辅助,数字禁止心算)

1. 列出最近 7 个自然日(TODAY-6 … TODAY)中存在的日报:
   `ls reports/daily/ | sort`(对照日期清点)
   记录:覆盖日报 N 份、日期列表、缺失日期列表。
2. 复盘计数用脚本取得,输出原样照抄:
   `python3 scripts/log_decision.py stats --from <TODAY-6> --to <TODAY>`
3. 逐份读取这 N 份日报全文(含各自的"数据缺漏"节)。

**N 为 0 时终止并报错(无素材不生成周报)。N < 3 时照常生成,但覆盖声明
必须写明缺失日期(spec"日报不足"场景)。**

## 第 2 步:生成周报(LLM)

只依据第 1 步素材写 `reports/weekly/WEEK.md`,模板:

    # 外汇周报 WEEK

    > 覆盖日报:N 份(<日期列表>);缺失日期:<列表,无则写"无">

    ## 本周主线
    -(≤3 条,主题式,跨币种归纳)

    ## 各币种一周归因
    (五币种各一小段:USD/EUR/PHP/THB/BRL,基于日报内容做一周归因)

    ## 复盘汇总
    - <stats 命令输出的计数行,原样照抄>
    - 明细逐条:<日期> <币种> <verdict>(照抄 stats 明细)

    ## 下周关注
    -(基于各日报"情景与触发条件"与年历,≤5 条)

    ## 缺漏汇总
    - <日期>: [<source>/<scope>] <内容>(取自各日报缺漏节;全周无缺漏写"无")

**禁令:**
1. 一级/二级结构禁止按日期组织(不得出现 `## 2026-08-05` 式标题)。
2. 数字只准逐字来自日报原文与 stats 命令输出;禁止自行计算或汇总数字。
3. 复盘汇总的计数行必须与 stats 输出逐字一致。
4. 不得引用缺失日期的任何"数据"。

## 第 3 步:校验(脚本,不可跳过)

运行:`python3 scripts/check_report.py reports/weekly/WEEK.md --mode weekly`

- 退出码 0:完成。
- 非 0:按违规项修改一次,重跑。
- 二次仍非 0:报告首行前插入 `> ⚠ 本报告未通过自动自检:<违规摘要>`,
  保留落盘,如实结束。
````

- [ ] **Step 6: 建 symlink 并 Commit**

```bash
ln -sfn ../../skills/fx-weekly-report .claude/skills/fx-weekly-report
ls -l .claude/skills/fx-weekly-report/SKILL.md
git add skills/fx-weekly-report/SKILL.md .claude/skills/fx-weekly-report \
        scripts/check_report.py tests/test_check_report.py
git commit -m "feat(fx): 周报 skill 主题聚类模板 + 校验器 weekly 模式(tasks 4.1)"
```

---

### Task 15: 周报端到端验收(tasks.md 4.2)

**Files:**
- 产物: 3 份回填日报 + `reports/weekly/<本周>.md`

**验收标准:** spec"正常周聚合"(≥3 份日报,一级结构为主题非日期)、"周内有缺漏日"(如有)、"观点复盘汇总"在真实产物上成立;校验器 weekly 模式退出码 0。

- [ ] **Step 1: 回填三天快照与日报(利用 `--date` 与 skill 日期参数;GDELT 回填走 datetimerange)**

```bash
cd /home/ubuntu/repos-REBORN-lab/macro
for D in $(date -u -d "3 days ago" +%F) $(date -u -d "2 days ago" +%F) $(date -u -d "1 day ago" +%F); do
  claude -p "/fx-daily-report $D" --permission-mode acceptEdits
  ls reports/daily/$D.md || echo "MISSING $D"
done
```

Expected: 三份 `reports/daily/*.md` 生成(加上 Task 13 的当日报告,共 ≥4 份可聚合)。注意每轮含 GDELT 串行 5s 间隔,单轮采集 ≥25s 属正常。若 Task 13 已在今日运行,今日报告直接复用。

- [ ] **Step 2: 真实运行周报 skill**

```bash
claude -p "/fx-weekly-report" --permission-mode acceptEdits
```

Expected: 生成 `reports/weekly/$(date -u +%G-W%V).md` 且校验通过。

- [ ] **Step 3: 独立复核(结果写进 commit message)**

```bash
W=$(date -u +%G-W%V)
python3 scripts/check_report.py reports/weekly/$W.md --mode weekly; echo "exit=$?"
# 一级结构人工确认为主题:
grep '^## ' reports/weekly/$W.md
# 复盘汇总计数与 stats 输出逐字比对:
python3 scripts/log_decision.py stats --from $(date -u -d "6 days ago" +%F) --to $(date -u +%F)
sed -n '/## 复盘汇总/,/## 下周关注/p' reports/weekly/$W.md
# 缺漏汇总与各日报缺漏节对照:
grep -A3 '## 数据缺漏' reports/daily/*.md
```

核对项:`exit=0`;`## ` 标题无日期;计数行与 stats 输出逐字一致;缺漏汇总覆盖各日报非"无"的缺漏节。不符 → systematic-debugging 定位后修复重跑。

- [ ] **Step 4: Commit**

```bash
git add data briefs reports state/decision-log.jsonl
git commit -m "feat(fx): 周报端到端验收通过(tasks 4.2)——复核结果:<逐项实测结果>"
```

---

### Task 16: README 运行文档(tasks.md 5.1)

**Files:**
- Modify: `README.md`

**验收标准:** 文档覆盖:无头模式命令、可选环境变量、目录说明、年历维护方式、交付边界;命令与实际实现逐字一致(照抄 Task 13/15 实际用过的命令)。

- [ ] **Step 1: 在 README.md 追加以下章节(命令须与端到端实测一致,不一致以实测为准修正)**

```markdown
## 运行

日报(无头模式;cron 接线自理):

    cd <仓库根>
    claude -p "/fx-daily-report" --permission-mode acceptEdits
    # 指定日期回填: claude -p "/fx-daily-report 2026-08-08" --permission-mode acceptEdits

周报(建议每周一跑,聚合最近 7 天):

    claude -p "/fx-weekly-report" --permission-mode acceptEdits

只跑采集(不生成报告):

    python3 -m scripts.collect --date 2026-08-10

测试:

    python3 -m unittest discover -s tests -t . -v

## 环境变量

- `FRED_API_KEY`(可选):存在时用 FRED release dates 增强前一日美国数据发布判定;
  不设时走零 key 默认路径(静态年历 + GDELT 承担判定,不记缺漏)。
- `FX_GDELT_DELAY_S` / `FX_GDELT_BACKOFF_S`:仅测试提速用,生产禁止设置
  (默认串行 5s / 退避 30s,是 GDELT 限速约束的一部分)。

## 目录

    config/    endpoints.json(全部外部 URL 模板)与 indicators.json(DBnomics series)
    state/     calendar-<年>.json 静态央行年历;decision-log.jsonl 决策日志(脚本代笔)
    data/      每日快照 YYYY-MM-DD.json(报告数字的唯一来源)
    briefs/    每日要点表(LLM 第一步产物 + review.py 注入复盘材料)
    reports/   daily/YYYY-MM-DD.md 与 weekly/YYYY-Www.md
    scripts/   collect 采集包、review.py、log_decision.py、check_report.py
    skills/    fx-daily-report 与 fx-weekly-report(.claude/skills 有同名链接)

## 年历维护

`state/calendar-<年>.json`:每年 12 月按文件内 `sources` 列出的各央行官网
更新次年 events 并顺延 `valid_until`;过期后采集会在快照 gaps 中持续告警。
日期必须来自官网,禁止凭记忆填写。

## 边界

本仓库交付到"本地 markdown 报告落盘"为止:Slack/邮件推送、cron 调度、部署
由使用者自行接线。报告数字均逐字来自快照,LLM 不做任何计算——校验器
(`scripts/check_report.py`)在每次生成后强制执行该纪律。
```

- [ ] **Step 2: 复核文档命令可执行**

Run: `python3 -m unittest discover -s tests -t . -v && python3 -m scripts.collect --help`
Expected: 测试全过;help 正常输出。

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs(fx): 运行文档与年历维护说明(tasks 5.1)"
```

---

### Task 17: Scenario 全量核对(tasks.md 5.2)

**Files:**
- Create: `openspec/changes/fx-daily-report-skill/.super-coding/scenario-coverage.md`

**验收标准:** 三份 delta spec 的全部 Scenario 逐条有核对记录(覆盖方式 + 实测证据);核对当场重跑命令取证,**禁止先写结论再补跑**(硬规则)。

- [ ] **Step 1: 重跑全量测试取证**

Run: `python3 -m unittest discover -s tests -t . -v 2>&1 | tail -5`
把实际输出(`Ran N tests ... OK`)原样记录。

- [ ] **Step 2: 写核对表(每行的"证据"必须是实测输出/文件路径,不得留空或写"应该")**

```markdown
# Scenario 覆盖核对 — fx-daily-report-skill

测试全量实测:<粘贴 Step 1 输出原文>

| # | Spec | Scenario | 覆盖方式 | 证据 |
|---|------|----------|----------|------|
| 1 | fx-data-collection | 双源正常 | tests/test_rates.py::test_dual_source_ok | <PASS 输出行> |
| 2 | fx-data-collection | 主源失败降级 | test_rates + test_fault_injection::test_frankfurter_down | |
| 3 | fx-data-collection | 双源偏差超阈 | test_rates.py::test_deviation_over_threshold_marks_suspect | |
| 4 | fx-data-collection | 有新数据发布 | test_macro.py::test_latest_prev_and_new_release_flag | |
| 5 | fx-data-collection | 零 key 默认路径 | test_macro.py::test_zero_key_default_path_no_fred_gap | |
| 6 | fx-data-collection | FRED 增强路径失败 | test_macro.py::test_fred_enhancement_failure_recorded | |
| 7 | fx-data-collection | 正常采集(GDELT) | test_events.py::test_normal_collection_all_currencies | |
| 8 | fx-data-collection | 限速软失败退避 | test_events.py::test_soft_rate_limit_*(2 个用例) | |
| 9 | fx-data-collection | 端点不可用 | test_events.py::test_endpoint_* + fault_injection::test_gdelt_down | |
| 10 | fx-data-collection | 昨日为议息日 | test_calendar.py::test_yesterday_meeting_hit | |
| 11 | fx-data-collection | 部分源失败时快照完整 | test_snapshot + test_fault_injection 全矩阵 | |
| 12 | fx-daily-report | 数据齐全的正常日 | Task 13 端到端 + check_report 结构检查 | reports/daily/<日期>.md |
| 13 | fx-daily-report | 无明确驱动的币种 | SKILL 禁令 6 + Task 13 人工抽查 | |
| 14 | fx-daily-report | 数字可溯源 | check_report NUMBER_UNTRACEABLE + Task 13 抽查 | |
| 15 | fx-daily-report | 缺漏日披露 | check_report GAPS_NOT_DISCLOSED/GAP_OMITTED | |
| 16 | fx-daily-report | 无缺漏日 | check_report GAPS_MISMATCH(test_empty_gaps_section_must_say_none) | |
| 17 | fx-daily-report | 存在前日日志 | test_review.py::test_direction_hit/miss + Task 15 实跑 | |
| 18 | fx-daily-report | 首次运行无日志 | test_review.py::test_first_run_no_log + Task 13 实跑 | |
| 19 | fx-daily-report | 篇幅合规 | check_report SUMMARY_TOO_LONG/SECTION_TOO_LONG | |
| 20 | fx-weekly-report | 正常周聚合 | Task 15 端到端 + check_weekly DATE_STRUCTURE | reports/weekly/<周>.md |
| 21 | fx-weekly-report | 日报不足 | check_weekly COVERAGE_GAP_DATES(test_low_coverage_needs_missing_dates) | |
| 22 | fx-weekly-report | 周内有缺漏日 | 周报缺漏汇总节 + Task 15 复核第 3 步 | |
| 23 | fx-weekly-report | 观点复盘汇总 | log_decision stats + check_weekly REVIEW_TOKEN_MISSING + Task 15 复核 | |

结论:23/23 覆盖(该数字须与上表实际行数一致后方可写下)。
遗留事项:<如 indicators 清单有剔除、年历某央行日程缺失等,逐条列出>
```

- [ ] **Step 3: Commit**

```bash
git add openspec/changes/fx-daily-report-skill/.super-coding/scenario-coverage.md
git commit -m "docs(fx): 23 个 Scenario 逐条核对记录(tasks 5.2)"
```

---

## Scenario → 任务映射(计划自审用)

- fx-data-collection(11 个 Scenario)→ Task 4(3)/Task 5(3)/Task 6(3)/Task 7(1)/Task 8+9(1)
- fx-daily-report(8 个 Scenario)→ Task 10(复盘 2)/Task 11+12(结构、数字、缺漏、篇幅 5)/Task 13(端到端整体含"无明确驱动"1)
- fx-weekly-report(4 个 Scenario)→ Task 14(结构与声明规则)+ Task 15(端到端实证)

## 执行提示

- 依赖链:1→2→3→4→5→6→7→8→9→10→11→12→13→14→15→16→17(严格顺序;3–7 之间理论上可并行,但按序执行最稳)。
- Task 2(年历)与 Task 5 Step 1(series 实测)、Task 13/15(端到端)需要真实网络;其余任务全程离线可测。
- 每任务完成即 commit;tasks.md 勾选按"与 tasks.md 的对应"表,在对应计划任务全部通过后由协调者定向勾选并验证。
