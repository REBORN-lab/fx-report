## MODIFIED Requirements

### Requirement: 宏观数据增量采集
系统 SHALL 采集五经济体关键宏观指标的最新值与前值,来源优先级为 **BLS > BIS > DBnomics**。

美国 CPI SHALL 优先取自 BLS 公共 API(零 key);该 API 返回指数点位时,同比 SHALL 由采集脚本按同月同比确定性计算,MUST NOT 用相邻月份近似替代;上月同比 SHALL 由同一份响应算出作为 `prev`(基期缺失时记 null),使报告不必自找比较基准;BLS 路径失败或同月基期缺失时 SHALL 回落后续来源并记入缺漏。BIS MUST NOT 覆盖已由 BLS 取得的美国 CPI。

五经济体的 CPI 同比与政策利率 SHALL 直连 BIS Stats API 取得(`WS_LONG_CPI` 与 `WS_CBPOL`),MUST NOT 经由 DBnomics 镜像——实测该镜像滞后 8–17 个月且政策利率给出过期值。BIS 响应 SHALL 按列名解析(`REF_AREA` / `TIME_PERIOD` / `OBS_VALUE`),MUST NOT 按列位置索引。BIS 整体不可达、缺少必需列、或缺少某经济体时,受影响的指标 SHALL **逐条**回落 DBnomics 并记入缺漏,未受影响的指标保持 BIS 来源。缺漏的 scope SHALL 定位到受影响的**具体指标**(经济体/指标),MUST NOT 只记到 dataflow 一级——回落取到的是滞后 8–17 个月的镜像陈值,在快照里与正常取数同形,缺漏不落到指标上,报告层无从知道该对哪一条打折扣。

BIS 取数 SHALL 只覆盖 `config/indicators.json` 实际跟踪的(经济体, 指标):某 dataflow 无任何跟踪项时 MUST NOT 发出该请求;未被跟踪的经济体缺席 MUST NOT 记入缺漏(无人引用的指标缺席不是缺漏,记录会淹没真正影响报告的条目)。

`is_new_release` 的判据 SHALL 随序列频率而定:月频序列比对**期号**(相邻月份同值也是两次独立发布);日频序列 SHALL 比对**数值水平**,MUST NOT 比对期号——日频政策利率序列每个日历日追加一行,期号推进反映的是数据管道刷新而非央行动作。取不到可比数值(首次落地、上一份快照无该 series、旧值非数值)时 SHALL 记为 false,MUST NOT 猜测。

政策利率取自日频序列时,非交易日的观测值为 `NaN`;系统 SHALL 取最近一个非 `NaN` 观测作为当前值,`NaN` MUST NOT 参与数值比较。政策利率的 `prev` SHALL 为**上一个与当前值不同的利率水平**及其生效日,MUST NOT 取"上一个观测"——日频序列绝大多数相邻观测相同,后者会恒等于当前值而不含信息;回溯窗口内未出现变动时 `prev` SHALL 为 null,MUST NOT 等于当前值。

条目的 `series_id` SHALL 指向实际取数的源,MUST NOT 沿用其他 provider 的标识。每个宏观条目 SHALL 携带 `lag_months`——期号相对当日快照日期的滞后月数;期号形态无法解析时记为 null。

零 key 为默认运行路径:"前一日发布了哪些数据"的判定 SHALL 由静态年历与 GDELT 事件流承担,该路径 MUST NOT 记为缺漏;当环境变量 FRED_API_KEY 存在时,系统 SHALL 额外调用 FRED release dates 端点增强前一日美国数据发布判定,该增强调用失败时记入缺漏但不中断其余采集。

#### Scenario: 有新数据发布
- **WHEN** 前一日某跟踪指标发布了新值
- **THEN** 快照列出该指标的名称、最新值、前值与发布日期

#### Scenario: 美国 CPI 走 BLS 主源
- **WHEN** BLS 公共 API 可用且返回的指数序列含同月基期
- **THEN** 美国 CPI 同比由脚本按同月同比计算并落盘,条目标注来源为 BLS

#### Scenario: BLS 同月基期缺失
- **WHEN** BLS 返回的序列不含同月基期
- **THEN** 记入缺漏并回落后续来源,MUST NOT 用相邻月份近似计算同比

#### Scenario: BIS 直连取得五经济体指标
- **WHEN** 两个 BIS dataflow 均可达且含必需列
- **THEN** 五经济体的 CPI 同比与政策利率取自 BIS,条目标注来源为 BIS,美国 CPI 仍标注来源为 BLS

#### Scenario: BIS 整体不可达
- **WHEN** BIS 请求失败或响应无法解析
- **THEN** 受影响的 10 个指标逐条回落 DBnomics,每次失败记入缺漏,经常账户等未走 BIS 的指标不受影响

#### Scenario: BIS 缺少某经济体
- **WHEN** BIS 响应中某个**被跟踪的**经济体没有任何可用观测(缺席或全 `NaN`)
- **THEN** 仅该经济体的对应指标回落 DBnomics,其余经济体保持 BIS 来源;同时记入一条 scope 为"经济体/指标"的缺漏,使报告层能对这条陈值打折扣

#### Scenario: 未跟踪的指标不请求也不记缺漏
- **WHEN** `config/indicators.json` 未跟踪某 BIS 指标的任何经济体
- **THEN** 不发出该 dataflow 的请求;未被跟踪的经济体缺席不记入缺漏

#### Scenario: 日频政策利率序列追加同值观测
- **WHEN** BIS 政策利率序列相对上一份快照多了若干行,但最新观测的利率水平未变
- **THEN** `is_new_release` 为 false(期号推进来自数据管道刷新,不是央行动作),报告 MUST NOT 据此列出"数据发布"行

#### Scenario: 日频政策利率水平变动
- **WHEN** 最新观测的利率水平与上一份快照同 series 的值不同
- **THEN** `is_new_release` 为 true,`prev` 为变动前的水平及其最后生效日

#### Scenario: 无可比旧值
- **WHEN** 上一份快照没有该 series,或其值不是可比数值
- **THEN** `is_new_release` 为 false(漏列一次真实变动只是少说,凭不可比的输入打出发布行是编造)

#### Scenario: BIS 响应缺少必需列
- **WHEN** BIS CSV 不含 `REF_AREA` / `TIME_PERIOD` / `OBS_VALUE` 中的任一列
- **THEN** 该 dataflow 整体回落并记入缺漏,MUST NOT 按列位置猜测取值

#### Scenario: 政策利率日频序列末端为 NaN
- **WHEN** 政策利率序列最新若干观测的值为 `NaN`(非交易日)
- **THEN** 取最近一个非 `NaN` 观测作为当前值;全部观测均为 `NaN` 时该经济体回落 DBnomics

#### Scenario: 政策利率前值取上一个不同水平
- **WHEN** 回溯窗口内出现过利率变动
- **THEN** `prev` 为变动前的利率水平,并记录该水平的最后生效日

#### Scenario: 回溯窗口内政策利率未变动
- **WHEN** 回溯窗口内所有非 `NaN` 观测的值都相同
- **THEN** `prev` 为 null,MUST NOT 等于当前值(等值会被读成"持平",而事实是窗口内未观测到变动)

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

## ADDED Requirements

### Requirement: HTTP 响应压缩兜底
采集层的 HTTP 取数封装 SHALL 在响应体为 gzip 时按魔数(前两字节 `0x1f 0x8b`)自动解压后再解码,MUST NOT 依赖请求侧的 `Accept-Encoding` 协商——实测存在无视该请求头恒返回 gzip 的源。

解压失败 SHALL 抛出可被上层转为缺漏的异常,MUST NOT 回退为有损解码。以有损解码方式读取压缩体会产出乱码,使"压缩未解开"与"源返回了垃圾"在缺漏记录中不可区分,属静默劣化。

取数封装 SHALL 接受可选的额外请求头参数;未提供时默认 User-Agent 保持不变。

#### Scenario: 源返回 gzip 响应
- **WHEN** 某源返回的响应体以 gzip 魔数开头
- **THEN** 取数封装自动解压并正常返回文本/JSON,不记缺漏

#### Scenario: 源无视 identity 协商
- **WHEN** 请求已声明 `Accept-Encoding: identity` 但响应体仍为 gzip
- **THEN** 仍按响应体魔数解压,取数成功

#### Scenario: 压缩体损坏
- **WHEN** 响应体以 gzip 魔数开头但解压失败
- **THEN** 抛出异常由调用方记入缺漏,MUST NOT 以有损解码返回乱码

#### Scenario: 未压缩响应不受影响
- **WHEN** 响应体不以 gzip 魔数开头
- **THEN** 按原有路径解码,行为与本变更前一致

#### Scenario: 自定义请求头
- **WHEN** 调用方传入额外请求头
- **THEN** 这些头随请求发出,且默认 User-Agent 在未被覆盖时保持不变
