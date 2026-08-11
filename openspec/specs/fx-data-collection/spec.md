# fx-data-collection Specification

## Purpose
TBD - created by archiving change fx-daily-report-skill. Update Purpose after archive.
## Requirements
### Requirement: 五币种汇率双源采集与交叉校验
系统 SHALL 从 Frankfurter(主源)获取 USD 兑 PHP/THB/BRL/EUR 的日频汇率,并 SHALL 用 exchange-api 版本化日期端点做异源交叉校验;同一币种两源偏差超过 0.5% 时 SHALL 在快照中标记该币种数据可疑并保留两源数值。

#### Scenario: 双源正常
- **WHEN** Frankfurter 与 exchange-api 均可用且各币种偏差 ≤ 0.5%
- **THEN** 快照含四对汇率、两源数值与校验通过标记

#### Scenario: 主源失败降级
- **WHEN** Frankfurter 请求失败(超时/非 200/无数据)
- **THEN** 系统采用 exchange-api 数据作为当日汇率,并把主源失败记入缺漏记录(含原因),采集继续

#### Scenario: 双源偏差超阈
- **WHEN** 某币种两源偏差 > 0.5%
- **THEN** 快照标记该币种"数据可疑"并保留两源数值,日报层可引用该标记

### Requirement: 宏观数据增量采集
系统 SHALL 从 DBnomics(五经济体;provider 以实测可用为准,当前为 IMF/BIS/ECB 口径)采集关键宏观指标的最新值与前值。零 key 为默认运行路径:"前一日发布了哪些数据"的判定 SHALL 由静态年历与 GDELT 事件流承担,该路径 MUST NOT 记为缺漏;当环境变量 FRED_API_KEY 存在时,系统 SHALL 额外调用 FRED release dates 端点增强前一日美国数据发布判定,该增强调用失败时记入缺漏但不中断其余采集。

#### Scenario: 有新数据发布
- **WHEN** 前一日某跟踪指标发布了新值
- **THEN** 快照列出该指标的名称、最新值、前值与发布日期

#### Scenario: 零 key 默认路径
- **WHEN** 环境变量中无 FRED_API_KEY
- **THEN** 采集按默认路径完成(静态年历与 GDELT 承担发布判定),gaps 中不出现 FRED 相关条目

#### Scenario: FRED 增强路径失败
- **WHEN** FRED_API_KEY 存在但 FRED 请求失败
- **THEN** FRED 失败记入缺漏,DBnomics 与其余采集照常进行

### Requirement: 前一日事件采集(GDELT)
系统 SHALL 按五币种关键词组串行查询 GDELT DOC 2.0 API(请求间隔 ≥ 5 秒),采集前一日窗口的 top 文章列表与 tone;系统 MUST 识别"HTTP 200 但正文为限速提示"的软失败形态,退避后重试一次,仍失败则记为缺漏。

#### Scenario: 正常采集
- **WHEN** 五组关键词查询串行完成
- **THEN** 快照含每币种的前一日文章列表(标题/URL/来源/时间)与 tone 值

#### Scenario: 限速软失败退避
- **WHEN** 响应为 HTTP 200 但正文是限速提示文本
- **THEN** 系统识别为软失败,等待后重试一次;重试成功则正常记录,再失败则该币种事件记为缺漏

#### Scenario: 端点不可用
- **WHEN** GDELT 请求超时或返回错误
- **THEN** 该币种事件记为缺漏(含原因),其余币种查询继续,管线不中断

### Requirement: 央行议息静态年历对照
系统 SHALL 维护一份含五家央行(Fed/ECB/BSP/BOT/BCB)议息会议日程的静态年历文件,采集时 SHALL 标注前一日与当日是否命中日历事件。

#### Scenario: 昨日为议息日
- **WHEN** 静态年历中前一日存在某央行议息会议
- **THEN** 快照标记该事件(央行名/事件类型/日期)供日报引用

### Requirement: 快照落盘与缺漏记录
系统 SHALL 把当日全部采集结果写入按日期命名的快照文件,内含逐数据源的成功/失败状态与失败原因;任一数据源失败 MUST NOT 中断其余数据源的采集。

#### Scenario: 部分源失败时快照完整
- **WHEN** 任一数据源采集失败
- **THEN** 其余源照常采集落盘,快照的 gaps 字段逐条列出失败源与原因

