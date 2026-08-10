# Tasks: fx-daily-report-skill

## 1. 仓库骨架与静态数据

- [x] 1.1 建立目录结构(`scripts/`、`skills/`、`data/`、`reports/daily/`、`reports/weekly/`、`state/`)与 `.gitignore`,README 写一段目标概述
- [x] 1.2 制作五央行(Fed/ECB/BSP/BOT/BCB)议息静态年历数据文件,含"有效期至"字段与维护说明

## 2. 数据采集层(fx-data-collection)

- [x] 2.1 汇率采集模块:Frankfurter 主源取 USD 兑 PHP/THB/BRL/EUR,exchange-api 版本化端点交叉校验,偏差 >0.5% 标记可疑,主源失败降级并记缺漏
- [x] 2.2 宏观采集模块:按 design 阶段确定的指标清单从 DBnomics 取最新值/前值,FRED release dates 判定前日美国数据发布(无 key 时降级记缺漏)
- [x] 2.3 GDELT 事件采集模块:五币种关键词组串行查询(间隔 ≥5s),识别"200 但正文为限速提示"软失败并退避重试一次,失败记缺漏
- [x] 2.4 快照聚合:年历对照标注 + 全部采集结果落盘 `data/YYYY-MM-DD.json`(含逐源状态与 gaps 结构),单源失败不中断
- [x] 2.5 采集层故障注入测试:逐源模拟失败,验证其余源照常采集且 gaps 记录符合 spec 场景

## 3. 日报生成(fx-daily-report skill)

- [x] 3.1 编写 `skills/fx-daily-report/SKILL.md`:先跑采集脚本再生成报告;模板含执行摘要(≤6 条)、五币种节(事件→定价含义→情景与触发条件,≤约 300 字/节)、数据缺漏节、复盘节;数字只准引快照;禁止方向性预测
- [x] 3.2 决策日志:每日观点追加 `state/decision-log.jsonl`;次日读取并对照快照汇率变动生成逐币种一句话复盘;首次运行优雅跳过
- [x] 3.3 端到端验收:真实跑一次 `claude -p` 生成当日日报,抽查全部数字与快照逐字一致、缺漏节如实、篇幅合规

## 4. 周报生成(fx-weekly-report skill)

- [x] 4.1 编写 `skills/fx-weekly-report/SKILL.md`:读最近 7 天日报与决策日志,按主题重聚类(本周主线 ≤3 条/各币种归因/复盘汇总/下周关注),日报不足 3 份时注明覆盖范围
- [x] 4.2 端到端验收:用 ≥3 份日报真实跑一次周报,验证一级结构为主题而非日期、缺漏与复盘汇总正确

## 5. 收尾

- [x] 5.1 README 运行文档:无头模式命令、环境变量(FRED key 可选)、目录说明、年历维护方式、"交付/调度自行接线"边界说明
- [ ] 5.2 对照三份 spec 的全部 Scenario 逐条核对已覆盖,记录核对结果
