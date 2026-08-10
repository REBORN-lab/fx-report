# macro — 五币种外汇日报/周报管线

零 API key、零第三方依赖(Python 3 标准库 only)的外汇报告管线:
每日用免费公开数据源(Frankfurter / exchange-api / DBnomics / GDELT / 静态央行年历)
采集 USD 兑 PHP/THB/BRL/EUR 的汇率、宏观指标与事件快照,
再由 Claude Code skill 两步生成中文日报(快照 → 要点表 → 叙事),
报告数字经 `scripts/check_report.py` 强制溯源校验;周报按主题聚合最近 7 天日报。
Slack 推送与 cron 调度由使用者自行接线(范围外)。

(运行文档见下文,由实施任务 16 补全。)
