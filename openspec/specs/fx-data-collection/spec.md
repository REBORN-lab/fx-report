# fx-data-collection Specification

## Purpose
TBD - created by archiving change fx-daily-report-skill. Update Purpose after archive.
## Requirements
### Requirement: 五币种汇率双源采集与交叉校验
系统 SHALL 从 Frankfurter(主源)获取 USD 兑 PHP/THB/BRL/EUR 的日频汇率,并 SHALL 用 exchange-api 版本化日期端点做异源交叉校验;同一币种两源偏差超过 0.5% 时 SHALL 在快照中标记该币种数据可疑并保留两源数值。系统 SHALL 逐币种保存主源响应中的参考价定盘日期(`ref_date`)与上一份快照的对应日期(`prev_ref_date`),使"汇率是否真的变化过"在数据层可判定;主源响应缺该字段、该币种降级到副源、或双源皆失败时 `ref_date` 记为 null,采集继续。

#### Scenario: 双源正常
- **WHEN** Frankfurter 与 exchange-api 均可用且各币种偏差 ≤ 0.5%
- **THEN** 快照含四对汇率、两源数值与校验通过标记

#### Scenario: 主源失败降级
- **WHEN** Frankfurter 请求失败(超时/非 200/无数据)
- **THEN** 系统采用 exchange-api 数据作为当日汇率,并把主源失败记入缺漏记录(含原因),采集继续

#### Scenario: 双源偏差超阈
- **WHEN** 某币种两源偏差 > 0.5%
- **THEN** 快照标记该币种"数据可疑"并保留两源数值,日报层可引用该标记

#### Scenario: 参考价定盘日期落盘
- **WHEN** Frankfurter 响应含参考价定盘日期字段
- **THEN** 各币种条目记录该 `ref_date`,并记录上一份快照的 `prev_ref_date`

#### Scenario: 降级到副源时无参考日期
- **WHEN** 某币种因主源失败而采用 exchange-api 数值
- **THEN** 该币种 `ref_date` 为 null(主源定盘日期对该数值不成立)

#### Scenario: 存量快照无参考日期
- **WHEN** 上一份快照不含参考日期字段(本变更之前生成)
- **THEN** `prev_ref_date` 记为 null,采集与后续比对退回按数值比较的既有行为

### Requirement: 宏观数据增量采集
系统 SHALL 从 DBnomics(五经济体;provider 以实测可用为准,当前为 IMF/BIS/ECB 口径)采集关键宏观指标的最新值与前值。美国 CPI SHALL 优先取自 BLS 公共 API(零 key);该 API 返回指数点位时,同比 SHALL 由采集脚本按同月同比确定性计算,MUST NOT 用相邻月份近似替代;上月同比 SHALL 由同一份响应算出作为 `prev`(基期缺失时记 null),使报告不必自找比较基准;条目的 `series_id` SHALL 指向实际取数的源,MUST NOT 沿用其他 provider 的标识;BLS 路径失败或同月基期缺失时 SHALL 回落 DBnomics 并记入缺漏。每个宏观条目 SHALL 携带 `lag_months`——期号相对当日快照日期的滞后月数;期号形态无法解析时记为 null。零 key 为默认运行路径:"前一日发布了哪些数据"的判定 SHALL 由静态年历与 GDELT 事件流承担,该路径 MUST NOT 记为缺漏;当环境变量 FRED_API_KEY 存在时,系统 SHALL 额外调用 FRED release dates 端点增强前一日美国数据发布判定,该增强调用失败时记入缺漏但不中断其余采集。

#### Scenario: 有新数据发布
- **WHEN** 前一日某跟踪指标发布了新值
- **THEN** 快照列出该指标的名称、最新值、前值与发布日期

#### Scenario: 美国 CPI 走 BLS 主源
- **WHEN** BLS 公共 API 可用且返回的指数序列含同月基期
- **THEN** 美国 CPI 同比由脚本按同月同比计算并落盘,条目标注来源为 BLS

#### Scenario: BLS 同月基期缺失
- **WHEN** BLS 返回的序列不含同月基期
- **THEN** 记入缺漏并回落 DBnomics 数值,MUST NOT 用相邻月份近似计算同比

#### Scenario: 换源当日标记不可比
- **WHEN** 某指标当日的数据源与上一份快照不同(**两个方向都算**:切到新源,以及新源失败回落旧源)
- **THEN** 该条目含 `source_changed_from` 标记且 `is_new_release` 为 false(期号跳变来自换源而非新发布),报告据此禁用比较表述

#### Scenario: 存量快照无来源字段
- **WHEN** 上一份快照的条目不含 `source` 字段(本变更之前生成)
- **THEN** 视其为 `dbnomics`,据此正确识别出换源

#### Scenario: 滞后月数披露
- **WHEN** 某宏观条目的期号可解析
- **THEN** 该条目含 `lag_months`,报告层可据此说明数值的陈旧程度

#### Scenario: 期号不可解析
- **WHEN** 某宏观条目的期号形态无法解析为年月
- **THEN** `lag_months` 记为 null,不做猜测

#### Scenario: 零 key 默认路径
- **WHEN** 环境变量中无 FRED_API_KEY
- **THEN** 采集按默认路径完成(静态年历与 GDELT 承担发布判定),gaps 中不出现 FRED 相关条目

#### Scenario: FRED 增强路径失败
- **WHEN** FRED_API_KEY 存在但 FRED 请求失败
- **THEN** FRED 失败记入缺漏,DBnomics 与其余采集照常进行

### Requirement: 前一日事件采集(GDELT)
系统 SHALL 按五币种关键词组串行查询 GDELT DOC 2.0 API(请求间隔 SHALL ≥ 5 秒,默认 20 秒),采集前一日窗口的 top 文章列表;系统 MUST 识别"HTTP 200 但正文为限速提示"的软失败形态**与 HTTP 429 硬限流**,退避后重试一次,仍失败则记为缺漏。查询顺序 SHALL 按采集日期确定性轮转,使限流造成的缺失不恒定落在同一批币种(公平性措施;实测表明本机限流与查询位置无关,轮转不构成 429 缓解手段);同一币种内标题重复的文章 SHALL 只保留一条。快照 MUST NOT 包含 tone 字段——所使用的 artlist 端点不返回该字段。

#### Scenario: 正常采集
- **WHEN** 五组关键词查询串行完成
- **THEN** 快照含每币种的前一日文章列表(标题/URL/来源/时间),且不含 tone 字段

#### Scenario: 限速软失败退避
- **WHEN** 响应为 HTTP 200 但正文是限速提示文本
- **THEN** 系统识别为软失败,等待后重试一次;重试成功则正常记录,再失败则该币种事件记为缺漏

#### Scenario: 硬限流退避
- **WHEN** 请求返回 HTTP 429
- **THEN** 系统等待后重试一次;重试成功则正常记录,再失败则该币种事件记为缺漏

#### Scenario: 查询顺序轮转
- **WHEN** 以不同采集日期运行
- **THEN** 五币种查询顺序按日期确定性轮转;同一日期重复运行顺序一致

#### Scenario: 标题去重
- **WHEN** 某币种返回的文章中存在标题完全相同的多条
- **THEN** 快照中该币种只保留其中一条

#### Scenario: 端点不可用
- **WHEN** GDELT 请求超时或返回错误
- **THEN** 该币种事件记为缺漏(含原因),其余币种查询继续,管线不中断

### Requirement: 央行议息静态年历对照
系统 SHALL 维护一份含五家央行(Fed/ECB/BSP/BOT/BCB)议息会议日程与可验证的统计发布日程的静态年历文件,采集时 SHALL 标注前一日与当日是否命中日历事件。日程条目 SHALL 仅录入可从官方来源验证的日期,来源 URL 与抓取日期 SHALL 记录在文件内;无法验证的日程 MUST NOT 录入推测值,其缺口 SHALL 记录在文件的维护说明中。

#### Scenario: 昨日为议息日
- **WHEN** 静态年历中前一日存在某央行议息会议
- **THEN** 快照标记该事件(央行名/事件类型/日期)供日报引用

#### Scenario: 命中统计发布日
- **WHEN** 静态年历中当日或前一日存在某项统计发布(如美国 CPI)
- **THEN** 快照同样标记该事件,报告可据此写出具体的催化剂日期

#### Scenario: 无法验证的日程不录入
- **WHEN** 某经济体的官方发布日历无法从本机验证
- **THEN** 该经济体的发布日期一条不录,缺口写入维护说明

### Requirement: 快照落盘与缺漏记录
系统 SHALL 把当日全部采集结果写入按日期命名的快照文件,内含逐数据源的成功/失败状态与失败原因;任一数据源失败 MUST NOT 中断其余数据源的采集。快照 SHALL 含由脚本确定性计算的 `derived` 派生指标节,其每一项 MUST 可由快照与近若干份历史快照的原始值复算得出;任一输入缺失或非有限数值时该项 SHALL 记为 null 而非省略,派生计算的内部异常 MUST 转为缺漏记录且不阻断快照落盘。

#### Scenario: 部分源失败时快照完整
- **WHEN** 任一数据源采集失败
- **THEN** 其余源照常采集落盘,快照的 gaps 字段逐条列出失败源与原因

#### Scenario: 派生指标落盘
- **WHEN** 当日与历史快照提供了足够输入
- **THEN** 快照 `derived` 节含日涨跌百分比、近 5 次定盘高低区间、双源偏差前值、事件计数变化与实际利率

#### Scenario: 事件采集失败不得记为零篇
- **WHEN** 某币种事件采集失败(快照 events 无该币种条目)
- **THEN** 该币种派生的事件计数记为 null;仅当确实采到且文章数为 0 时才记为 0

#### Scenario: 定盘日期未知时按值去重
- **WHEN** 历史快照不含参考价定盘日期(本变更之前生成)
- **THEN** 区间计算按 primary 值去重,同值的多份视为同一次定盘,不重复计入天数

#### Scenario: 定盘日期未知且价格相等时不计涨跌
- **WHEN** 某币种 `prev_ref_date` 缺失且当日 primary 与 prev_primary 完全相等
- **THEN** 该币种日涨跌百分比记为 null(无法区分真持平与参考价未更新)

#### Scenario: 参考价未更新时不计涨跌
- **WHEN** 当日某币种 `ref_date` 与其 `prev_ref_date` 相同
- **THEN** 该币种日涨跌百分比记为 null(参考价未更新,不构成价格变动)

#### Scenario: 实际利率携带双期号
- **WHEN** 某经济体政策利率与 CPI 同比均可用
- **THEN** 派生的实际利率同时携带政策利率与 CPI 各自的期号原文;任一缺失时 `value` 记为 null(键与已知的另一半仍保留,便于说明缺的是哪一侧)

#### Scenario: 派生计算异常不阻断
- **WHEN** 派生计算过程抛出异常
- **THEN** 异常转为缺漏记录,快照其余部分照常落盘

### Requirement: 央行官方公告采集
系统 SHALL 从央行官方新闻 RSS 采集公告条目,作为 GDELT 之外的高可信事件通道,并按发布方归入对应币种的 `official` 列表;每源至多保留 3 条,条目 SHALL 含标题与发布方(必填,缺标题的条目跳过),链接与发布时间尽力而为、缺失记 null。解析成功但未取到任何条目时 SHALL 记为缺漏——健康的源恒有条目,零条目通常意味着源改版(如换成带默认命名空间的 RDF/Atom),静默归零会与"未配置"不可区分。任一源失败 MUST 记为缺漏且 MUST NOT 影响其余源与其余采集模块。仅纳入实测可达的官方源;不可达的源 MUST NOT 写入配置(避免每日缺漏噪音),其缺口 SHALL 记录在文档中。

#### Scenario: 官方源正常
- **WHEN** Fed 与 ECB 的 RSS 均可访问
- **THEN** 快照 `events.USD.official` 与 `events.EUR.official` 各含至多 3 条(标题/链接/时间/发布方)

#### Scenario: 未配置的官方源静默跳过
- **WHEN** 某官方源未出现在端点配置中
- **THEN** 该源视为有意停用,静默跳过且 MUST NOT 记为缺漏(否则每份快照都带永久噪音,淹没真正的采集失败)

#### Scenario: 单个官方源失败
- **WHEN** 某官方源请求失败或返回非 XML
- **THEN** 该源记为缺漏,其余官方源与 GDELT 采集照常完成

#### Scenario: 解析成功但无条目
- **WHEN** 某官方源返回可解析的 XML 但未取到任何条目(如源改版为带默认命名空间的格式)
- **THEN** 该源记为缺漏,MUST NOT 静默产出空结果

#### Scenario: GDELT 失败时官方通道仍在
- **WHEN** 某币种 GDELT 采集被限流而其官方源可用
- **THEN** 该币种仍有 `official` 条目可供报告引用,GDELT 缺漏照常披露

#### Scenario: 官方公告不计入事件计数
- **WHEN** 派生指标计算某币种事件计数
- **THEN** 计数只统计 GDELT `articles`,`official` 不计入(两个通道口径不同,合并会让计数不可比)

