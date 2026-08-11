# Tasks: fx-skill-report-quality-tweaks

## 1. 日报 SKILL

- [x] 1.1 编辑 `skills/fx-daily-report/SKILL.md`:①"数据发布"行追加缺漏日回退分支(该币种"昨日事件 top"为空时可列快照存量政策利率/最新 CPI,标"(存量背景,非昨日发布)",数字逐字抄快照);②"昨日事件 top"行加 top-3 选取准则(FX/货币政策优先;主线反向标题至少保留一条,无则不强凑)

## 2. 周报 SKILL

- [x] 2.1 编辑 `skills/fx-weekly-report/SKILL.md`:③第 1 步素材清单补第 4 条"读 `state/calendar-*.json` 未来 2-3 周窗口",禁令 2 扩为允许年历文件原文;④复盘汇总模板首行加不含数字的 verdict 图例(无法判定 vs 未判定);⑤缺漏汇总模板行改按源聚类(`- [<source>] 波及 <日期列表>/<币种范围> — 影响:<一句话>`,无缺漏仍写"无")

## 3. 回归确认

- [x] 3.1 全量测试套件通过;用既有真实产物重跑 `check_report.py`(daily 与 weekly 各一份)确认退出码不变——实证 prompt 改动未破坏校验器兼容
