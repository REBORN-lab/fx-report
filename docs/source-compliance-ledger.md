# 数据源合规台账(2026-08-21 建)

本文件登记**每一个被考察过的数据源的裁定与实测证据**。它不是"推荐源列表" ——
出局的那些同样重要:没有它们,同一个源会被反复重新调研、反复得出同一个结论。

- 每条裁定必须附**实测证据**:命令、HTTP 码、字节数、以及返回内容里的逐字片段。
- **先跑命令后抄输出**。取不到就写取不到,404 如实写成 404(= 未发布限制),
  **不得写成「允许」**。
- 状态是「已接入 / 可接未接 / 出局 / **待裁定**」。待裁定的那一档必须写明**卡在哪**。

## 五道检查(缺一不可)

前四道是本仓一直在用的。**第五道是 2026-08-21 补的** —— 审计发现前四道会对
FRED 与 Cboe **全部放行**,而两者的服务条款都逐字禁止我们要做的事。

| # | 检查 | 判据 |
|---|---|---|
| 1 | 零 API key | 需注册 / 需 token / 需签名 → 出局。**不写「注册后即可用」** |
| 2 | Python 标准库可解析 | 需 requests / pandas / lxml / bs4 / 浏览器渲染 → 出局。`html.parser` 啃得动的静态表算通过 |
| 3 | robots.txt | 实测目标**主机**的 `/robots.txt`,逐字抄相关行。**robots.txt 本身取不到(403/429/挑战页)= 出局** |
| 4 | 不绕过封锁 | 被拒就是被拒。不试 stealth、不伪装 UA、不用代理、不换 IP、不顶着人机验证重试 |
| 5 | **服务条款正文** | robots 放行 ≠ 条款放行。要读 `/terms`、`/legal`、`/use-of-content` 一类页面的**正文** |

第 5 道的实例(2026-08-21 实测)。**只有 FRED 一个**是干净的实例 ——
Cboe 曾被写成第二个,复核发现它的数据主机 robots 取不到,先卡在第 3 道(见下与出局表):

- **FRED**:`robots.txt` 200 且未禁 `fredgraph.csv`,零 key、端点 200、CSV 可解析 —— 四道全过。
  但 `fred.stlouisfed.org/legal` 逐字:*"Don’t do any data mining, scraping or extraction of FRED data."*(原文是 U+2019 弯撇,不是直撇)
  以及 *"In order to use the FRED® API, you must have register for an API Key."*
  → **出局**。`fredgraph.csv` 是执行漏洞,不是许可。
  (`scripts/collect/macro.py` 的 `_fred()` 现状是零 key 就不调用 —— **这是对的,不要改**。)
- **Cboe VIX**:**先卡在第 3 道**。数据主机 `cdn.cboe.com/robots.txt` = **HTTP 403**(S3 AccessDenied,
  正文含随机 RequestId,字节数不稳定,不写死);按本文件第 3 道「robots.txt 本身取不到 = 出局」,
  它与 CME 同判。`www.cboe.com/robots.txt` 200/78B 只禁 `/book/` 与 volume_reports —— 但那是**另一个 origin**,
  不为 `cdn` 上的数据背书。
  另有第 5 道的独立理由(**引文未复核,标注为待取证**):`www.cboe.com/terms` 与 `/use-of-content`
  据称禁止 "store ... in an electronic retrieval system" 与 "distribute" 并要求事前签署许可协议 ——
  这两段本轮**没有取到正文**,不得当成已证实的引文使用。
  **本文件此前写的「471748 字节 / 9256 行」已删**:那个读数取自 robots 不可获取的主机,
  按第 4 道不得复现,也就无法核对。

## 已接入

| 源 | 取什么 | 备注 |
|---|---|---|
| frankfurter | 五币种参考价(主源) | |
| exchange-api | 参考价(副源,算双源偏差) | |
| BIS `WS_CBPOL` | 政策利率,日频 | **有署名义务**,见下 |
| BIS `WS_LONG_CPI` | CPI 同比,月频 | 同上 |
| BIS `WS_EER` | 名义 / 实际有效汇率,**本轮取月频** | 2026-08-21 接入。五经济体全覆盖(实测最新期均为 2026-07),PH/TH 不慢一档。该 dataflow 另有日频名义序列(实测滞后约 3 天),日频实际不存在(404);取哪一档是我方选择,不是源的限制 |
| IMF SDMX `BOP` | 经常账户,季频 | 2026-08-16 由 dbnomics 换来,同时消一条违规 |
| BLS | 美国 CPI | |
| PSA OpenSTAT PXWeb | 菲律宾 CPI | **只有 px 格式带 `NEXT-UPDATE`**;json-stat2 会静默丢数据 |
| Fed / ECB 官方 RSS | 央行公告 | RSS 只给最新 N 条、不按日期过滤 |
| gdelt / gnews | 事件通道 | |

**BIS 的署名义务(2026-08-21 实测,适用于上面三条 BIS 源)**:
`www.bis.org/terms_statistics.htm` HTTP=200 / 39691 字节,逐字 ——
*"The use of the statistics is unrestricted, provided that: if the statistics are reproduced,
**the BIS must be cited** in your publication or product as the source of the statistics ...
No other use is permissible."* 且 *"**Use of the APIs constitutes agreement** by users of the APIs
(“Users”) with the following terms and conditions"*。**这一条此前未满足,2026-08-21 已修**:实测十二天里 12/12 的快照含 `source == "bis"` 的序列,
而 **7/12 的日报正文一次都没提过 BIS**(任何大小写);提到过的五份里有四份只是附录出处行里的
小写 `bis`(口径注,不是署名)。处置是把它做成不变量而不是叮嘱 ——
`check_report.py` 的 `BIS_ATTRIBUTION_MISSING`:快照里存在 `source == "bis"` 的行时,
报告必须逐字包含固定串「本报告的政策利率、CPI 同比与有效汇率取自 BIS。」。
新码上线当场把 8/9 份存量报告打红,已逐份补上附录 D。

## 出局(逐条附实测)

| 源 | 卡在第几道 | 实测证据 |
|---|---|---|
| BSP | 3 | 对非搜索引擎 UA `Disallow: /` |
| CME(含 CME FedWatch) | 3 | `/robots.txt` 本身 403 + 明文禁止脚本访问。**robots 不可获取即不得再发请求** |
| PDS / PDEx / BTr / PSE / SET | 3 | PDS robots 403(Incapsula);PDEx `Disallow: /`;BTr robots 返回挑战页而非指令;PSE robots 200/2592B 共 103 行,第 98 行是 `User-agent: *`、**第 99 行**是 `Disallow: /`;SET 数据端点 403 |
| `psa.gov.ph` 正文站 | 4 | Cloudflare JS 挑战 403(**API 子域 `openstat` 可用,见已接入**) |
| `data.adb.org` | 4 | robots 放行但边缘 WAF 403 |
| stooq | 3 | `stooq.com/robots.txt` 200/96B,`*` → `Disallow: /`(只放行 Bingbot/Googlebot) |
| Yahoo Finance | 2 + 3 | `query1.finance.yahoo.com/robots.txt` 200/26B 逐字 `Disallow: /`;且 yfinance 带 12 个传递依赖 |
| `data.go.th` | 3 | robots 403 |
| `api.db.nomics.world` | 3 | 全站 `Disallow: /`。**曾违规**,2026-08-16 换 IMF 直连消除 |
| **CoinGecko** | 3 + 5 | `api.coingecko.com/robots.txt` 200/117B 逐字含 `Disallow: /api/v3` —— 正是全部数据路径;ToS 另禁 scraping 且限非商用 |
| **CNN 恐惧贪婪指数** | 4 | `production.dataviz.cnn.io` 端点对诚实 UA 返回 **HTTP=418**,正文逐字 `I'm a teapot. You're a bot.` **出局理由是「入口只有伪装」,不是「暂时不通」** |
| **Polymarket** | — | 所测全部数据 URL(gamma-api / clob / data-api / 主站)一律 Cloudflare **HTTP=451,BYTES=17**,正文逐字 `error code: 1026`(16 字符 + 换行)。此前写的「零字节」是错的,已改。**成因未确定**,唯一变通是换出口 = 犯第 4 道 |
| **SEC EDGAR** | 3 | `www` 403/1925B(`Request Rate Threshold Exceeded`)、`data` 与 `efts` 各 403/4819B(`Undeclared Automated Tool`)—— **robots.txt 本身取不到**。此前引的 *"The SEC does not allow botnets or automated tools to crawl the site."* **复现不了**(三份 403 正文里逐字检索均为 False,且原引文未记出处),已删;够得着的正文给的其实是准入路径:*"Please declare your traffic by updating your user agent"* 与 *"no more than 10 requests per second"* |
| **FRED** | 5 | 见上 |
| **Cboe** | **3 + 5** | 见上 |
| **DuckDuckGo HTML** | 4 | robots 是 `Allow: /`,**不按 robots 出局**;出局理由是「检出 CAPTCHA 后继续重试」这一手法,以及返回值不可复现、不可溯源、时点未知 |

## 待裁定

### Kalshi 事件合约(`KXFED` = FOMC 后的联邦基金利率上限门槛)

**它能补的是我方唯一完全空白的一格**:美国利率路径的市场定价。现状只能转述新闻标题。

四道全过,卡在第 5 道,**而且是"读不到"不是"读到了禁令"**(2026-08-21 实测):

```
api.elections.kalshi.com/robots.txt   → HTTP=404 BYTES=0        未发布限制
external-api.kalshi.com/robots.txt    → HTTP=404 BYTES=0        同上
docs.kalshi.com/robots.txt            → HTTP=200 BYTES=171      Content-Signal: ai-train=yes, search=yes, ai-input=yes
kalshi.com/robots.txt                 → HTTP=429               Vercel Security Checkpoint(挑战页含随机 ID,字节数在 33789~33793 间漂移,不写死)
kalshi.com/developer-agreement        → HTTP=429 BYTES=33789    同上
kalshi.com/terms                      → HTTP=429 BYTES=33793    同上

数据端点(不带任何认证头):
GET api.elections.kalshi.com/trade-api/v2/events?series_ticker=KXFED&status=open&limit=5
  → HTTP=200,KXFED-26SEP / 26OCT / 26DEC,strike_date 2026-09-16T18:00:00Z 等
```

**两边的道理都要写下来:**

- **可接的一侧**:robots.txt 是**按 origin** 生效的(RFC 9309)。我们要打的
  `api.elections.kalshi.com` 未发布任何限制,对诚实 UA 返回 200,日频一次请求。
  我们从不触碰 429 的那个主站。
- **出局的一侧**:`docs.kalshi.com` 逐字写着 *"By continuing to use or access Kalshi's API,
  you are agreeing to be bound to our Developer Agreement"* —— 而**那份协议我方读不到**。
  这不是「条款无禁止」,是**「条款未取证」**。而且主站 robots.txt 自身 429 这一形态,
  与我方判 CME(403)、判 BTr(挑战页)出局时用的是同一把尺子。

**卡点是判断不是事实,应当由人裁定,与 2026-08-15 的 PSA/ClaudeBot 裁定同型**
(那次裁定记录在会话记忆里,仓库内无留痕 —— 这本身是个缺口,值得把历次人工裁定补进仓库)。
在裁定之前**不接**。

若裁为可接,采集器规格(约 60 行 urllib,**不复用 digital-oracle 的代码**):
只打 `api.elections.kalshi.com`、禁触 `kalshi.com`;近月合约由 `status=open` 按
`strike_date` 程序化定位(不硬编码);字段读 `*_dollars` / `*_fp` **字符串原样落盘、不做除法**;
报价时刻取 candlesticks 最后一根**已完成**的 K 的 `end_period_ts`;
报告只准写「买 0.32 / 卖 0.33 美元」与合约名,**不得写成「32.5%」或「加息概率」**
(中点是算出来的;合约条款是"上限 > 3.75%",翻译成"加息"需要一步外部事实 + 一步推理)。

### 其它可接未接

| 源 | 取什么 | 补哪一格 | 为什么没接 |
|---|---|---|---|
| 美国财政部收益率曲线 | 名义 / 实际,日频 T+1,纯 CSV | 美国短端水平锚 + 实际利率直读 | 四道全过。**但它对 PH/TH/BR 覆盖为 0**,补不上「政策空间见底」那条(那条的主语是 PHP/THB) |
| CFTC COT(`gpe5-46if`) | EUR / BRL 投机与资管持仓 | 离岸投机头寸的代理量 | 严格**周频**,滞后 3~10 天的锯齿 → **只该进周报,不该进日报** |
| Deribit DVOL | BTC/ETH 波动率指数 | 风险偏好的加密侧一角 | 真 Terms of Use 是 SPA 外壳,**条款未取证**;且其 API 政策逐字警告未认证请求更易被封 IP |

## 一条方法论结论

**robots 放行 + 零 key + 端点 200 + 标准库可解析 —— 四条全绿,仍然可能是不许用的。**
**FRED 就是**(实例只有这一个;Cboe 曾被误列,它先卡在第 3 道)。加第 5 道之前,我方的检查会把 FRED 放行。

还有一条同样重要的:**robots.txt 是按 origin 生效的(RFC 9309)**。
`www.cboe.com` 放行不为 `cdn.cboe.com` 背书,`api.elections.kalshi.com` 未发布限制
也不受 `kalshi.com` 的 429 约束 —— 两个方向都要按同一把尺子量,
不得在一处按 origin 判、在另一处按品牌判。
