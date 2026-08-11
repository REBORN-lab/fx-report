---
super_coding_change: fx-bis-macro-direct
role: technical-design
canonical_spec: openspec
archived-with: 2026-08-11-fx-bis-macro-direct
status: final
---

# 技术设计:BIS 宏观直连 + HTTP 取数封装加固

OpenSpec 是需求的唯一权威(`openspec/changes/fx-bis-macro-direct/`)。本文只写**怎么实现**。
`design.md` 的 D1–D7 是已定的方向;本文把它们落到函数边界、参数取值与测试靶点上。

## 1. 端点参数:`detail=dataonly` 是决定性的

实测同一查询的响应体积:

| 参数 | 体积 | 覆盖 |
|---|---|---|
| `lastNObservations=180` | 401 KB | 4/5 经济体能找到上一次利率变动 |
| `lastNObservations=400` | 891 KB | 5/5 |
| **`lastNObservations=400&detail=dataonly`** | **40 KB** | 5/5 |
| `startPeriod=2025-01-01&detail=dataonly` | 55 KB | 5/5,但体积随时间单调增长 |

`detail=dataonly` 去掉全部元数据列后仍保留所需列:

```
WS_CBPOL   dataonly → FREQ, REF_AREA, TIME_PERIOD, OBS_VALUE
WS_LONG_CPI dataonly → FREQ, REF_AREA, UNIT_MEASURE, TIME_PERIOD, OBS_VALUE
```

两者列集合**仍然不同**(CPI 多一个 `UNIT_MEASURE`),这正是 D5「按列名取」的现实依据——
必需列只认这三个:`REF_AREA` / `TIME_PERIOD` / `OBS_VALUE`。

**取值决定**

- `WS_CBPOL`:`lastNObservations=400&detail=dataonly`。**设计时写的"400 个交易日约 19
  个月、美国约需 170 个观测"两个数字未经实测,verify 阶段实跑后更正**(见第 9 节 §9.1):
  该序列按**日历日**出行,400 个观测跨 399 天 ≈ 13.1 个月;美国上次变动 2025-12-10
  需回溯 **237** 个观测,余量 163 个(≈ 5 个月)。取值 400 不变,结论(够用)不变。
  某央行若连续持稳超过 13.1 个月,`prev` 退化为 `null` —— 这是 spec 明文允许的诚实退化,
  不是缺陷。
- `WS_LONG_CPI`:`lastNObservations=4&detail=dataonly`(约 1 KB)。只需最新月同比与上月同比,
  多取两期作 NaN 余量。

不用 `startPeriod`:体积随日历单调增长,而 `lastNObservations` 是有界的。

## 2. 函数边界:一个新函数,`collect()` 形状不变

`macro.py` 现有 `collect(cfg)` 是「先算 `bls_row` → 遍历 `cfg["indicators"]` 逐条打 DBnomics」。
BIS 是**批量**取数,与逐条循环形状不同。硬塞进循环会让每条指标都发一次请求,
浪费掉 D1 的全部好处。

因此:**在循环之前把 BIS 结果拉平成一张查找表**,循环内只查表。

```
collect(cfg)
  ├─ bls_row   = _bls_us_cpi(cfg, gaps)          # 既有
  ├─ bis_table = _bis_table(cfg, gaps)           # 新增,返回 {(economy, indicator): row}
  └─ for ind in cfg["indicators"]:
        ├─ 命中 US CPI 且 bls_row 存在  → 用 BLS          （优先级 1）
        ├─ (economy, indicator) 在 bis_table → 用 BIS      （优先级 2）
        └─ 否则                          → 打 DBnomics     （优先级 3,既有代码）
```

这个形状让「逐指标回落」**不需要额外分支**:BIS 整体失败 → `_bis_table` 返回 `{}` →
全部未命中 → 全部走 DBnomics;BIS 只缺某经济体 → 只有那个键不在表里 → 只有它回落。
三种降级路径共用同一条代码路径,是它们能被同一组测试覆盖的原因。

`_bis_table` 内部再拆两个纯函数,便于单测不打网络:

- `_bis_parse(text, want)` — CSV 文本 → `{REF_AREA: [(period, value_str), ...]}`;
  缺必需列时抛 `ValueError`
- `_latest_and_prev_distinct(obs)` — 观测序列 → `(value, period, prev, prev_period)`

## 3. `NaN` 与数值门

`WS_CBPOL` 非交易日的 `OBS_VALUE` 是**字符串** `"NaN"`(实测 2000 行里大量存在)。

```python
def _obs_value(raw):
    """BIS 的非交易日写字符串 "NaN"。必须在**转 float 之前**按字符串判掉——
    float("NaN") 会成功,随后穿进比较,而 NaN 的任何比较都是 False,
    会让"取最新非 NaN"和"找上一个不同值"同时给出错误结果。"""
    s = (raw or "").strip()
    if not s or s.upper() == "NAN":
        return None
    try:
        v = float(s)
    except ValueError:
        return None
    return v if math.isfinite(v) else None
```

注意 `OBS_VALUE` 实测有 `"1"` 这样的整数字面量(泰国),不能假定含小数点。

## 4. 上一个**不同**水平(D4)

```python
def _latest_and_prev_distinct(obs):
    """obs 按 TIME_PERIOD 升序的 (period, value)。返回当前值、当前值的观测日、
    上一个与之不同的水平、以及**那个水平的最后一天**。

    日频政策利率绝大多数相邻观测相同,取"上一个观测"会恒等于当前值,
    对报告零信息(14.25 → 14.25)。窗口内始终未变动时 prev 为 None,
    绝不等于 value —— 等值会被读成"持平",而事实是"窗口内没看到变动"。
    """
```

`prev_period` 取的是**旧水平的最后一天**(而非它第一次出现的日子):报告要说的是
「上次变动之前是 A,一直到 X 日」。

## 5. `util` 的 headers 合并

```python
DEFAULT_UA = "macro-fx-collector/0.1"

def fetch_text(url, timeout_s=20, headers=None):
    hdrs = {"User-Agent": DEFAULT_UA}
    hdrs.update(headers or {})      # 调用方可覆盖 UA,语义明确
    ...
    raw = resp.read()
    if raw[:2] == b"\x1f\x8b":      # gzip 魔数
        raw = gzip.decompress(raw)  # 失败即抛,由调用方转 gap
    return raw.decode("utf-8", errors="replace")
```

顺序很关键:**先解压再 decode**。当前代码的缺陷正是 `errors="replace"` 在解压之前
就把压缩体变成了乱码,使「压缩没解开」与「源返回了垃圾」在 gap 里不可区分。

`gzip.decompress` 的异常**不捕获**——`macro`/`feeds` 等调用方本来就在 try/except 里
把异常转 gap,再包一层只会重复。

## 6. 测试策略:变异靶点

本仓库以变异测试为审查标准(存活即未测住)。以下判断**必须**有测试杀掉对应变异:

| 变异 | 必须失败的测试 |
|---|---|
| 去掉 `"NaN"` 字符串判定(改为直接 `float()`) | 末端 NaN 的序列仍取到正确的最新值 |
| `prev = obs[-2]`(取上一个观测而非上一个不同水平) | 有变动的序列返回变动前水平,而非等值 |
| 窗口内无变动时 `prev = value` | 无变动序列的 `prev` 为 `None` |
| 按列位置索引取值 | 列序被打乱的 CSV 仍解析正确 |
| 删掉必需列检测 | 缺 `OBS_VALUE` 列时记 gap 并回落,而非静默取空 |
| BIS 覆盖美国 CPI | 两者都可用时美国 CPI 的 `source` 仍为 `bls` |
| 回落粒度改为「全有或全无」 | BIS 只缺一个经济体时,其余四个仍为 `bis` |
| `XM` ↔ `EA` 映射互换 | 欧元区取到的是欧元区的值 |
| 去掉 gzip 魔数判定 | 压缩响应能被正常读出 |
| gzip 解压失败改为回退有损解码 | 损坏压缩体抛异常而非返回乱码 |
| `prev_period` 取旧水平的首日而非末日 | 断言末日 |

`OBS_VALUE` 为 `"1"`(无小数点)这一实测形态需单独有用例,避免实现里写出
依赖小数点的解析。

## 7. 边界条件清单

- CSV 空响应 / 只有表头 → `_bis_parse` 返回空表 → 全部回落,记 gap
- `REF_AREA` 含配置外的经济体 → 忽略,不进查找表
- 某经济体全部观测为 `NaN` → 该键不进表 → 只有它回落
- `TIME_PERIOD` 形态混用(日频 `2026-08-04` vs 月频 `2026-06`)→ 两个 dataflow 分开解析,
  不共用比较逻辑;`lag_months` 已有的 `PERIOD_RE` 对两者都能取到年月
- BIS 落后央行决议数日(实测 BR 停在 2026-08-04 = 14.25,而 COPOM 2026-08-05 已定 14.00)
  → 如实呈现 `period`,不补算、不外推
- 端点未配置 → 静默跳过 BIS(与 `feeds.py`「未配置 = 有意停用」同一约定),
  使删掉两个 URL 即整体回滚

## 8. 报告层的一处必要改动

政策利率的 `prev` 现在有意义了(`14.5 → 14.25`),但**日频序列的前值不带日期就是歧义的**——
这正是本仓库反复栽跟头的形态。因此 `skills/fx-daily-report/SKILL.md` 的「数据发布」行
需要在 `prev` 之后加 `prev_period`,写成「前值 <prev>(截至 <prev_period>)」;
`prev` 为 null 时写「前值 不可得(回溯窗口内未观测到变动)」。

这是本 change 唯一触及报告层的改动,一行模板 + 一句说明。

## Spec Patch

无。delta spec 的 16 个场景已覆盖上述全部行为;`prev_period` 已由
「`prev` 为变动前的利率水平,并记录该水平的最后生效日」这条场景要求。

> **verify 阶段更正**:delta spec 最终为 **25** 个场景(build 阶段按审查发现补了 4 个,
> 见 §9.2);本节写下"16 个"时是设计时的计数,保留原文并在此更正,不静默改。

archived-with: 2026-08-11-fx-bis-macro-direct
status: final
---

# 9. Implementation Divergence(verify 阶段记录)

本节由 verify 阶段追加,记录实现与本文/`design.md` 的偏差及原因。写在这里而不是回改
正文,是为了让"设计当时怎么想"与"实现最后怎么做"都能被读到。

## 9.1 两个未经实测就写下的数字(已更正)

第 1 节原写"400 个交易日约 19 个月""美国约需 170 个观测"。verify 阶段用真实端点实测:

| 项 | 设计时写的 | 实测(2026-08-11) |
|---|---|---|
| `lastNObservations=400` 覆盖时长 | 约 19 个月 | 400 个观测跨 **399 天 ≈ 13.1 个月**(按日历日出行) |
| 美国回溯到上次变动所需观测数 | 约 170 | **237**(上次变动 2025-12-10) |
| 余量 | "一倍" | 163 个观测 ≈ 5 个月(约 0.7 倍) |

参数取值与结论均不变(400 仍然够用),但按仓库数字硬规则,已写下而未验证的数字按错误
处理、逐字更正入档。README 同处两个数字一并更正。

## 9.2 审查后新增的两条行为(delta spec +4 场景)

build 阶段的强制代码审查(20 条发现 / 6 条被推翻 / 2 条 Important 幸存)暴露了本文
未覆盖的两个判断,均已实现并写入 delta spec:

1. **`is_new_release` 的判据必须随频率分开**。本文第 2 节只写了取数与前值口径,默认沿用
   既有的"比 period"。但 `WS_CBPOL` 每个日历日追加一行,期号推进反映的是数据管道刷新,
   不是央行动作 —— 实测(真实 BIS 字节 + 回拨一天的真实快照)旧判据 5/5 假阳性。新增
   `_is_new_level`:日频比**数值水平**,月频仍比**期号**(相邻月份同值也是两次独立发布)。
   取不到可比数值时记 false —— 漏列一次真实变动只是少说,凭不可比的输入打出发布行是编造。
2. **缺席经济体必须记 gap,且 scope 定位到具体指标**。本文第 2 节写"三种降级路径共用同一
   条代码路径,不需要额外分支" —— 这条在**回落是否可见**这一维度上是错的:回落取到的是
   滞后 8–17 个月的镜像陈值,快照里与正常取数同形,上一日若也是 dbnomics 则连
   `source_changed_from` 都没有,禁令 3 永不触发。缺席路径因此有了自己的记 gap 分支。
   连带确立:BIS 只为 `config/indicators.json` 实际跟踪的(经济体, 指标)取数与记 gap
   (与 BLS「没跟踪就别打这一枪」同约定),否则缺漏节会被无人跟踪的条目淹没。

变异靶点相应从本文第 6 节的 11 条扩到 21 条(新增 M12–M21),全部 KILLED。

## 9.3 与 `design.md` D4 的参数偏差

D4 写「`lastNObservations` 取 90(约三个月工作日)」。本文第 1 节据实测改为 **400**:
90 个观测覆盖不到美国上次变动(需 237 个),会让美国的 `prev` 长期退化为 `null`。
以本文取值为准,D4 的 90 作废。

## 9.4 `config/indicators.json` 未补 `REF_AREA` 维度键

proposal「What Changes」与 tasks 2.1 后半写了「`config/indicators.json` 为五经济体的
CPI 与政策利率补 BIS 维度键(`REF_AREA`)」,实现**未做**(该文件本次零改动),但 tasks 2.1
已勾选。判定为**被 D6 取代**而非遗漏:D6 决定把 `XM ↔ EA` 映射写成模块级常量 `BIS_AREA`,
它同时充当"BIS 覆盖哪些经济体"的闸门。再在 config 里放一份等价映射会制造两个可能互相
矛盾的真相源,且 config 里的 `REF_AREA` 拼错会静默停用该经济体的 BIS 分支。
维持现状,记录为已接受的偏差。

## 9.5 `_bis_parse` 签名

第 2 节写 `_bis_parse(text, want)`。实现为 `_bis_parse(text)`:按经济体裁剪发生在
`_bis_table` 的 `wanted` 列表里(§9.2 第 2 点),解析函数保持无状态、只做 CSV → 观测序列,
更好测。

## 9.6 `tests/test_snapshot.py` 未改

proposal「Impact」列了该文件。实际 BIS 分支的行为全部由 `tests/test_macro.py` 与
`tests/test_util.py` 覆盖(25/25 验收场景已逐条映射到具体用例),快照层形状未变,
无需改动。
