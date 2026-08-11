# Proposal: fx-daily-report-skill

## Why

公司团队需要每天了解影响 USD/PHP/BRL/THB/EUR 五种法币价格的前一日事件与宏观数据,但目前没有任何自动化手段——市面上也不存在现成的"多币种 FX 宏观日报"开源方案(2026-08-10 调研确认,见 `super-research/…方案调研/report.md`)。需要一个可在 Claude Code 无头模式(`claude -p`)下一条命令运行的 skill:采集前一天数据、生成带叙事逻辑链条的简明中文日报、按周聚合周报,任何数据缺漏在报告中显式说明。

## What Changes

- 新增数据采集脚本层:从 Frankfurter(主)+ exchange-api(交叉校验)取五币种汇率,从 DBnomics(IMF/BIS/ECB 口径,series 实测定案)与可选 FRED 取宏观增量,从 GDELT DOC 2.0 取前一日事件(串行限速),对照央行议息静态年历;全部落盘为当日数据快照,采集失败记为缺漏而非中断
- 新增 `fx-daily-report` skill:读数据快照生成中文日报——五币种分节,每节走"事件→定价含义→情景与触发条件"叙事链条;不做方向性预测;报告含执行摘要与数据缺漏节;所有数字来自快照文件,LLM 只写叙事
- 新增决策日志机制:每日报告的币种观点追加存档,次日对照实际走势生成一句话复盘写入新日报
- 新增 `fx-weekly-report` 聚合能力:读最近 7 天日报与决策日志,按主题重聚类(非流水账)生成中文周报
- 输出为本地 markdown 文件(`reports/daily/`、`reports/weekly/`);Slack 推送、定时调度、异机部署明确不在本 change 范围内(用户自行接线)

## Capabilities

### New Capabilities
- `fx-data-collection`: 五币种汇率/宏观/事件数据的每日采集与快照落盘,含双源交叉校验、限速退避、缺漏记录
- `fx-daily-report`: 从数据快照生成带叙事逻辑链条的中文日报,含缺漏披露与决策日志复盘
- `fx-weekly-report`: 从最近 7 天日报与决策日志按主题重聚类生成中文周报

### Modified Capabilities
(无——本仓库尚无既有 spec)

## Impact

- 新增目录:`skills/`(skill 定义)、`scripts/`(数据采集,Python 3 标准库 + 免费无 key API)、`data/`(每日快照)、`reports/`(日报/周报输出)、`state/`(决策日志、静态年历)
- 外部依赖:Frankfurter、exchange-api(jsDelivr CDN)、DBnomics(IMF/BIS/ECB provider)、FRED(需免费 API key,可选)、GDELT DOC 2.0——全部免费;无付费依赖,无爬虫
- 运行环境:目标机器需装 Claude Code + Anthropic API key(用户自备);skill 本体与脚本无其他运行时依赖
- 无既有代码受影响(全新仓库首个 change)
