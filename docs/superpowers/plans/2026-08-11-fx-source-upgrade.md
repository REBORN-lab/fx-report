---
change: fx-source-upgrade
design-doc: docs/superpowers/specs/2026-08-11-fx-source-upgrade-design.md
base-ref: a5dccf025225ff91391e47a4320ceeec66eff35e
archived-with: 2026-08-11-fx-source-upgrade
---

# 实施计划:fx-source-upgrade

按 tasks.md 六个任务 TDD 逐个执行,每任务一次提交。测试命令 `python3 -m unittest discover -s tests -t .`(基线 206)。

1.1 feeds.py + endpoints:先写 tests/test_feeds.py(正常两源/单源404/非XML/缺字段/条数上限),再实现
1.2 __main__ 接线:先写快照断言(official 存在、GDELT 全挂时仍在),再实现
2.1 macro BLS 主源:先写同比精度/同月缺失回落/请求失败回落/坏值,再实现
2.2 lag_months:先写两种期号形态/跨年/不可解析,再实现
3.1 SKILL + README:官方公告行、数据发布行带滞后、数据源节记录探针失败
3.2 回归:全量测试 + 真实采集 + check_report 退出码不变
