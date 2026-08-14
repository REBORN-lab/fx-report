# 数字出处清点(P3.7)

三类出处:**引自源**(字面出现在被引来源中,无标注)/ **自测** `[自测 YYYY-MM-DD]` / **派生** `[推导 <算式或口径>]`。

---

## 引自源(无标注)

| 数字 | 出处 |
|---|---|
| GSM8K `claude-3-haiku` 86.51 → 23.44;`gpt-3.5-turbo` 75.99 → 49.25 | [13] |
| `parsing error rate ... is only 0.148%` / `38.15% performance gap` | [13] |
| `100% of GPT 3.5 Turbo JSON-mode responses placed the 'answer' key before the 'reason' key` | [13] |
| CoT 不忠实导致最多 36% 准确率下降 | [15] |
| IMF LLM 评分 71–75%(评级)/ 76–81%(二元) | [12] |
| EconCausal 符号修正情境 73.9% → 41.3%(降 32.6pp);零效应识别率 13.8% | [18] |
| GERB 一段无关文字致准确率降 12.3pp | [19] |
| GPT-4o GDP 方向准确率 训练截止前 97.6% / 截止后 40% | [16] |
| persona 提示 2368 条 vs 无 persona 基线 100 条,ECB SPF 50 个季度,`no measurable forecasting advantage` | [17] |
| Macro Alibi:6.3 万份 Morgan Stanley 报告;熊市叙事宏观归因多 6.3pp | [22] |
| IMF RAM 概率校准:low <10% / medium 10–30% / high 30–50%(UK 2017 版) | [3] |
| IMF RAM 概率校准:「30 percent or more」(Algeria 2014 版) | [4] |
| ICD 203 概率词数值区间 `01-05% … 95-99%` | [1] |
| BoE:2026 年 4 月 MPR 三情景覆盖参考风险分布 99%;去掉情景 C 降至 87–89% | [9] |
| 宏观新闻解释不到三分之一的收益率方差 | [24] |
| ECB 官方传导机制 7 节点 | [8] |
| Soros 作者原话 `we don't have any formal calibration data yet` | [44] |
| GitHub star 数:OpenBB 71856 / AKShare 22022 / RKiding 2775 / tradermonty 2636 / QuantEcon.py 2388 / Awesome-Journal-Skills 985 / digital-oracle 775 / econ-writing-skill 530 / open-synthesis 213 / Burton ACH 109 / MoneyAtlas 53 / senior-analyst 49 / social-science-claude-scholar 21 / econstack 4 | [30]–[43] 各自仓库 |
| digital-oracle:36 commits、单一贡献者、零 release、末次提交 2026-07-26 | [36] |
| RKiding:`pushed_at 2026-03-29`、末次提交 `853f09b4 2026-03-29 doc: update doc` | [37] |

## 自测(本轮子代理实地调接口/跑命令观测)

| 数字 | 标注 |
|---|---|
| GitHub `macroeconomics` `total_available = 5519` | `[自测 2026-08-14]` |
| Layer 1 合并去重 430 行 → 272 个唯一仓库;stars ≥100 共 18、≥50 共 35、≥10 共 149 | `[自测 2026-08-14]` |
| `--sort updated` 溢出复查独家贡献 93 个仓库,最高 star 数 8 | `[自测 2026-08-14]` |
| `claude skill macro economics` 全网仅 3 个仓库、最高 2 stars | `[自测 2026-08-14]` |
| `macroeconomic analysis` 1316 个仓库 | `[自测 2026-08-14]` |
| `langgraph macro economic research report` → `total_available 0 total 0` | `[自测 2026-08-14]` |
| `--hn "LLM macroeconomic analysis"` → `"total": 2` | `[自测 2026-08-14]` |
| digital-oracle provider 文件实测 19 个 | `[自测 2026-08-14]` |
| `jessegrabowski/py-econ` HTTP 404(对照组 `gEconpy` 200) | `[自测 2026-08-14]` |
| `OpenSourcedMacroModels` 距上次推送 393 天 | `[自测 2026-08-14]` |
| DSGE.jl 最后 tag v1.3.0 @ 2021-11-23,124 个 open issue+PR | `[自测 2026-08-14]` |
| arXiv 四条「LLM×宏观×推理质量」查询全部返回 0 | `[自测 2026-08-14]` |

## 派生(由前两类计数/求和/比例得出)

| 数字 | 标注 |
|---|---|
| approved 46 条、19 个唯一域 | `[推导 registry.md 的 Approved 段按 ^\[N\] 行计数;域按 URL host 去重]` |
| official+academic = 27/46 = 58.7% | `[推导 Type 字段为 official 或 academic 的行数 ÷ approved 总数]` |
| github.com 14/46 = 30.4% | `[推导 URL host 为 github.com 的行数 ÷ approved 总数]` |
| 按 owner 计最大单一 owner 占比 1/46 = 2.2% | `[推导 14 个 GitHub 条目分属 14 个不同 owner,故任一 owner 占 1 条]` |
| 生态孤岛:排除 github-sweep 后样本 45,ddg 26/45 = 57.8% | `[推导 registry Path 字段计数,分母排除 Path 恰为 github-sweep 的条目]` |
| 课程仓库占 50+ 星段 34%(12/35) | `[推导 Layer 1 合并列表中 stars≥50 的 35 个仓库里人工判定为课程用途的 12 个]`(子代理自纠:初稿写「近半」,实测 34%) |
| 全部笔记去重后 URL 110 个 | `[推导 五份笔记正则抽 https?:// 后 sort -u]` |
| 五份笔记各自唯一 URL:10 / 30 / 18 / 32 / 23 | `[推导 逐文件 grep -oE 后 sort -u \| wc -l]` |

---

Number provenance: 21 cited, 12 self-measured, 8 derived (41 total)
