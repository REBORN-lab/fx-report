---
change: fx-weekly-digest-checker
design-doc: docs/superpowers/specs/2026-08-11-fx-weekly-digest-checker-design.md
base-ref: 6161bd9ce767d1dc2ea440175adf4ef2e399a852
archived-with: 2026-08-11-fx-weekly-digest-checker
---

# 实施计划:fx-weekly-digest-checker

按 tasks.md 五个任务 TDD 执行,每任务一次提交。基线 240 测试。

1.1 weekly_digest.py:先写 tests/test_weekly_digest.py,再实现 build()
1.2 周报 SKILL 接 digest
2.1 check_report --digest(周报数字溯源)
2.2 check_report --strict-brief(要点表溯源)
3.1 回归:全量测试 + 真实周报 + 既有日报过 --strict-brief
