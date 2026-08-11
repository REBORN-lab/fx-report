# Tasks: fx-source-upgrade

## 1. 央行官方公告通道

- [ ] 1.1 新建 `scripts/collect/feeds.py`:用 `xml.etree` 解析 Fed / ECB 官方 RSS,每源至多取 3 条(title/link/pubDate/issuer),Fed→USD、ECB→EUR;单源失败记 gap 不影响其余;非 XML/结构异常/深嵌套一律转 gap 不上抛。`config/endpoints.json` 增两个 feed URL。测试:正常解析、单源 404、非 XML 正文、items 缺字段、条数上限
- [ ] 1.2 `__main__.py` 接线:feeds 结果并入 `events[<cur>]["official"]`,GDELT 失败的币种也能有 official;`derived.events.count` 语义不变(仍只数 GDELT `articles`)。测试:端到端快照含 official、GDELT 全挂时 official 仍在

## 2. 宏观源升级与滞后披露

- [ ] 2.1 `macro.py` 美国 CPI 走 BLS v1:解析指数序列,按同月同比计算同比(round 3 位),记 `source: "bls"`;同月缺失或请求失败 → 记 gap 并回落 DBnomics。测试:正常同比计算、同月缺失、BLS 失败回落、bool/非数值输入
- [ ] 2.2 全部宏观条目加 `lag_months`(期号相对快照日期的滞后月数,支持 `YYYY-MM` 与 `YYYY-MM-DD`,不可解析记 null)。测试:两种期号形态、跨年、不可解析

## 3. 报告侧与回归

- [ ] 3.1 `skills/fx-daily-report/SKILL.md`:要点表加"官方公告"行(引 `official`,注明发布方与日期);数据发布行要求带 `lag_months`;README 数据源节补 Fed/ECB RSS 与 BLS,并写明 BCB/BSP/BOT 探针失败
- [ ] 3.2 全量测试通过;真实跑一次采集确认 official 与 lag_months 落盘;既有报告重跑 `check_report.py` 退出码不变
