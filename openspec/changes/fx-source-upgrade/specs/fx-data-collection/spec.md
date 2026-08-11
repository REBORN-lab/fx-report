# fx-data-collection Delta Spec

## ADDED Requirements

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

## MODIFIED Requirements

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
