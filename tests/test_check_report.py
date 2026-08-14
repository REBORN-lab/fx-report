import ast
import contextlib
import io
import itertools
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from scripts import check_report
from scripts import weekly_digest
from scripts.collect import derive
from scripts.collect import events as events_mod

SNAP = {"date": "2026-08-10",
        "rates": {"PHP": {"primary": 60.843, "prev_primary": 60.9},
                  "THB": {"primary": 35.2}, "BRL": {"primary": 5.43},
                  "EUR": {"primary": 0.921}},
        "macro": [{"indicator": "CPI 同比", "value": 3.1, "prev": 3.4,
                   "period": "2026-07"}],
        "events": {}, "calendar_hits": [], "gaps": []}
SNAP_TEXT = json.dumps(SNAP, ensure_ascii=False)
BRIEF = "# 要点表 2026-08-10\n- 汇率变动:primary 60.843,prev 60.9\n- CPI 3.1 前值 3.4\n"


def make_report(summary_items=3, missing=None, php_body=None, gap_body="无",
                extra_number=None):
    lines = ["# 外汇日报 2026-08-10", "", "## 执行摘要"]
    lines += ["- 摘要第 %d 条" % (i + 1) for i in range(summary_items)]
    sections = {
        "美元(USD)": "**昨日发生**:无明确驱动。**定价含义**:观望。"
                      "**情景与触发条件**:若有 FOMC 信号,则关注美元流动性。",
        "欧元(EUR)": "**昨日发生**:无明确驱动。**情景与触发条件**:若 ECB 表态,则关注 0.921 附近波动。",
        "菲律宾比索(PHP)": php_body or (
            "**昨日发生**:CPI 同比 3.1,前值 3.4。**定价含义**:通胀回落。"
            "**情景与触发条件**:若 BSP 释放降息信号,则关注 60.843 上方压力。"),
        "泰铢(THB)": "**昨日发生**:无明确驱动。**情景与触发条件**:若出口数据走弱,则关注 35.2 附近。",
        "巴西雷亚尔(BRL)": "**昨日发生**:无明确驱动。**情景与触发条件**:若 COPOM 表态,则关注 5.43。",
    }
    for name, body in sections.items():
        if missing and missing in name:
            continue
        lines += ["", "## " + name, body]
    lines += ["", "## 复盘", "- 首次运行,无历史观点可复盘"]
    lines += ["", "## 数据缺漏", gap_body]
    if extra_number:
        lines.append("另外汇率大约是 %s。" % extra_number)
    return "\n".join(lines)


class CheckDailyTest(unittest.TestCase):
    def test_valid_report_passes(self):
        v = check_report.check_daily(make_report(), SNAP_TEXT, BRIEF)
        self.assertEqual(v, [])

    def test_missing_currency_section(self):
        v = check_report.check_daily(make_report(missing="THB"), SNAP_TEXT, BRIEF)
        self.assertTrue(any("THB" in x and "SECTION_MISSING" in x for x in v))

    def test_summary_too_long(self):
        v = check_report.check_daily(make_report(summary_items=7), SNAP_TEXT, BRIEF)
        self.assertTrue(any("SUMMARY_TOO_LONG" in x for x in v))

    def test_section_too_long(self):
        long_body = "很" * 400 + "。**情景与触发条件**:若如此,则关注。"
        v = check_report.check_daily(make_report(php_body=long_body), SNAP_TEXT, BRIEF)
        self.assertTrue(any("SECTION_TOO_LONG" in x and "PHP" in x for x in v))

    def test_untraceable_number(self):
        v = check_report.check_daily(make_report(extra_number="99.99"), SNAP_TEXT, BRIEF)
        self.assertTrue(any("NUMBER_UNTRACEABLE" in x and "99.99" in x for x in v))

    def test_dates_are_not_flagged(self):
        v = check_report.check_daily(make_report(), SNAP_TEXT, BRIEF)
        self.assertFalse(any("NUMBER_UNTRACEABLE" in x for x in v))  # 2026-08-10 被剔除

    def test_gaps_not_disclosed(self):
        snap = dict(SNAP, gaps=[{"source": "gdelt", "scope": "THB",
                                 "reason": "rate-limited after retry", "at": "x"}])
        v = check_report.check_daily(make_report(gap_body="无"),
                                     json.dumps(snap, ensure_ascii=False), BRIEF)
        self.assertTrue(any("GAPS_NOT_DISCLOSED" in x for x in v))

    def test_gap_scope_must_be_mentioned(self):
        snap = dict(SNAP, gaps=[{"source": "gdelt", "scope": "THB",
                                 "reason": "rate-limited after retry", "at": "x"}])
        report = make_report(gap_body="- [gdelt/THB] rate-limited after retry — 影响:泰铢事件面结论缺依据")
        v = check_report.check_daily(report, json.dumps(snap, ensure_ascii=False), BRIEF)
        self.assertFalse(any("GAP" in x for x in v))

    def test_empty_gaps_section_must_say_none(self):
        v = check_report.check_daily(make_report(gap_body="- [gdelt/THB] 编造的缺漏"),
                                     SNAP_TEXT, BRIEF)
        self.assertTrue(any("GAPS_MISMATCH" in x for x in v))


class CorruptSnapshotLibraryTest(unittest.TestCase):
    """约定 1:损坏快照直调库函数时记 SNAPSHOT_MALFORMED 违规,不裸崩(响亮而非静默)。"""

    def test_invalid_json_reports_malformed(self):
        v = check_report.check_daily(make_report(), "{broken json", BRIEF)
        self.assertTrue(any("SNAPSHOT_MALFORMED" in x for x in v))

    def test_top_level_not_dict_reports_malformed(self):
        v = check_report.check_daily(make_report(), '["not", "a", "dict"]', BRIEF)
        self.assertTrue(any("SNAPSHOT_MALFORMED" in x for x in v))

    def test_gaps_not_a_list_reports_malformed(self):
        snap = dict(SNAP, gaps="oops")
        v = check_report.check_daily(make_report(), json.dumps(snap, ensure_ascii=False), BRIEF)
        self.assertTrue(any("SNAPSHOT_MALFORMED" in x for x in v))

    def test_gap_element_not_dict_reports_malformed(self):
        snap = dict(SNAP, gaps=["oops", True])
        v = check_report.check_daily(make_report(gap_body="- 有缺漏"),
                                     json.dumps(snap, ensure_ascii=False), BRIEF)
        self.assertTrue(any("SNAPSHOT_MALFORMED" in x for x in v))

    def test_gap_scope_and_source_non_string_do_not_crash(self):
        snap = dict(SNAP, gaps=[{"source": 3, "scope": True,
                                 "reason": "r", "at": "x"}])
        v = check_report.check_daily(make_report(gap_body="- 有缺漏"),
                                     json.dumps(snap, ensure_ascii=False), BRIEF)
        self.assertIsInstance(v, list)  # token 非字符串:跳过提及检查,不得 TypeError


class MainExitCodeTest(unittest.TestCase):
    def test_exit_codes(self):
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            rp = os.path.join(tmp, "r.md")
            sp = os.path.join(tmp, "s.json")
            bp = os.path.join(tmp, "b.md")
            with open(sp, "w", encoding="utf-8") as f:
                f.write(SNAP_TEXT)
            with open(bp, "w", encoding="utf-8") as f:
                f.write(BRIEF)
            with open(rp, "w", encoding="utf-8") as f:
                f.write(make_report())
            self.assertEqual(check_report.main([rp, sp, "--brief", bp, "--mode", "daily"]), 0)
            with open(rp, "w", encoding="utf-8") as f:
                f.write(make_report(missing="THB"))
            self.assertEqual(check_report.main([rp, sp, "--brief", bp, "--mode", "daily"]), 1)


class MainLoudFailureTest(unittest.TestCase):
    """约定 1/4:文件缺失或快照损坏 → rc=2 + stderr 说明,不留 traceback。"""

    def _run_main(self, argv):
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            rc = check_report.main(argv)
        return rc, buf.getvalue()

    def _write_inputs(self, tmp, snapshot_text=SNAP_TEXT):
        import os
        rp = os.path.join(tmp, "r.md")
        sp = os.path.join(tmp, "s.json")
        bp = os.path.join(tmp, "b.md")
        with open(rp, "w", encoding="utf-8") as f:
            f.write(make_report())
        with open(sp, "w", encoding="utf-8") as f:
            f.write(snapshot_text)
        with open(bp, "w", encoding="utf-8") as f:
            f.write(BRIEF)
        return rp, sp, bp

    def test_missing_report_file_rc2(self):
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            _, sp, bp = self._write_inputs(tmp)
            rc, err = self._run_main([os.path.join(tmp, "absent.md"), sp,
                                      "--brief", bp, "--mode", "daily"])
        self.assertEqual(rc, 2)
        self.assertTrue(err.strip())

    def test_missing_snapshot_file_rc2(self):
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            rp, _, bp = self._write_inputs(tmp)
            rc, err = self._run_main([rp, os.path.join(tmp, "absent.json"),
                                      "--brief", bp, "--mode", "daily"])
        self.assertEqual(rc, 2)
        self.assertTrue(err.strip())

    def test_missing_brief_file_rc2(self):
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            rp, sp, _ = self._write_inputs(tmp)
            rc, err = self._run_main([rp, sp, "--brief",
                                      os.path.join(tmp, "absent-brief.md"),
                                      "--mode", "daily"])
        self.assertEqual(rc, 2)
        self.assertTrue(err.strip())

    def test_missing_snapshot_arg_rc2(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            rp, _, bp = self._write_inputs(tmp)
            rc, err = self._run_main([rp, "--brief", bp, "--mode", "daily"])
        self.assertEqual(rc, 2)
        self.assertTrue(err.strip())

    def test_corrupt_snapshot_json_rc2(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            rp, sp, bp = self._write_inputs(tmp, snapshot_text="{broken json")
            rc, err = self._run_main([rp, sp, "--brief", bp, "--mode", "daily"])
        self.assertEqual(rc, 2)
        self.assertTrue(err.strip())

    def test_snapshot_top_level_list_rc2(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            rp, sp, bp = self._write_inputs(tmp, snapshot_text='["top", "level", "list"]')
            rc, err = self._run_main([rp, sp, "--brief", bp, "--mode", "daily"])
        self.assertEqual(rc, 2)
        self.assertTrue(err.strip())

    def test_snapshot_gaps_not_list_rc2(self):
        import tempfile
        snap = dict(SNAP, gaps="oops")
        with tempfile.TemporaryDirectory() as tmp:
            rp, sp, bp = self._write_inputs(
                tmp, snapshot_text=json.dumps(snap, ensure_ascii=False))
            rc, err = self._run_main([rp, sp, "--brief", bp, "--mode", "daily"])
        self.assertEqual(rc, 2)
        self.assertTrue(err.strip())


class MutationKillTest(unittest.TestCase):
    """Task 12 质量复审第 1 轮:针对两个存活变异的正向锁定测试。"""

    def test_novel_date_forms_not_flagged_as_untraceable(self):
        # 击杀变异 A(删 numbers_in 中的 DATE_RE.sub):报告含快照/brief 中
        # 逐字不存在的日期形态,DATE_RE 剔除是其放行的唯一原因,删 sub 即挂。
        php_body = ("**昨日发生**:CPI 同比 3.1,前值 3.4,下次发布定于 2025-12-31"
                    "(2026-W33 周历)。**定价含义**:通胀回落。"
                    "**情景与触发条件**:若 BSP 释放降息信号,则关注 60.843 上方压力。")
        v = check_report.check_daily(make_report(php_body=php_body), SNAP_TEXT, BRIEF)
        self.assertFalse(any("NUMBER_UNTRACEABLE" in x for x in v))

    def test_gap_scope_not_mentioned_triggers_gap_omitted(self):
        # 击杀变异 C(删 GAP_OMITTED 的 for g in gaps 循环):缺漏节有内容
        # 但未提及 scope="THB",必须报 GAP_OMITTED——正向断言违规出现。
        snap = dict(SNAP, gaps=[{"source": "gdelt", "scope": "THB",
                                 "reason": "rate-limited after retry", "at": "x"}])
        report = make_report(gap_body="- [gdelt/PHP] 速率受限 — 影响:相关事件面结论缺依据")
        v = check_report.check_daily(report, json.dumps(snap, ensure_ascii=False), BRIEF)
        self.assertTrue(any("GAP_OMITTED" in x for x in v))


def make_weekly(coverage="覆盖日报:5 份(2026-08-04 至 2026-08-08);缺失日期:无",
                theme_items=3, date_heading=False, drop=None,
                review_body="- 命中 2 / 未命中 1 / 无法判定 2\n- 2026-08-05 PHP 命中",
                currency_body=None):
    lines = ["# 外汇周报 2026-W32", "", "> " + coverage if coverage else "", ""]
    lines += ["## 本周主线"] + ["- 主线 %d" % (i + 1) for i in range(theme_items)]
    if date_heading:
        lines += ["", "## 2026-08-05", "当日流水"]
    body = {
        "各币种一周归因": currency_body if currency_body is not None else
            "USD 观望;EUR 震荡;PHP 通胀回落主导;THB 出口疲弱;BRL 政策预期反复。",
        "复盘汇总": review_body,
        "下周关注": "- 关注五央行表态",
        "缺漏汇总": "- 2026-08-06: [gdelt/THB] rate-limited after retry",
    }
    for name, b in body.items():
        if name != drop:
            lines += ["", "## " + name, b]
    return "\n".join(lines)


class CheckWeeklyTest(unittest.TestCase):
    def test_valid_weekly_passes(self):
        self.assertEqual(check_report.check_weekly(make_weekly()), [])

    def test_date_heading_forbidden(self):
        v = check_report.check_weekly(make_weekly(date_heading=True))
        self.assertTrue(any("DATE_STRUCTURE" in x for x in v))

    def test_coverage_declaration_required(self):
        v = check_report.check_weekly(make_weekly(coverage=""))
        self.assertTrue(any("COVERAGE_MISSING" in x for x in v))

    def test_low_coverage_needs_missing_dates(self):
        v = check_report.check_weekly(
            make_weekly(coverage="覆盖日报:2 份(2026-08-04、2026-08-05)"))
        self.assertTrue(any("COVERAGE_GAP_DATES" in x for x in v))

    def test_theme_limit(self):
        v = check_report.check_weekly(make_weekly(theme_items=4))
        self.assertTrue(any("THEME_TOO_MANY" in x for x in v))

    def test_review_tokens_required(self):
        v = check_report.check_weekly(make_weekly(review_body="- 表现不错"))
        self.assertTrue(any("REVIEW_TOKEN_MISSING" in x for x in v))

    def test_missing_weekly_section(self):
        v = check_report.check_weekly(make_weekly(drop="缺漏汇总"))
        self.assertTrue(any("SECTION_MISSING" in x and "缺漏汇总" in x for x in v))

    def test_missing_currency_reported(self):
        # 击杀变异 M6(删 check_weekly 的 CURRENCY_MISSING 循环):币种散文
        # 去掉 USD 后,全文任何位置(标题/覆盖行/复盘汇总/缺漏汇总)均不含
        # "USD" 字样,必须报 CURRENCY_MISSING: 周报未覆盖 USD。
        report = make_weekly(
            currency_body="EUR 震荡;PHP 通胀回落主导;THB 出口疲弱;BRL 政策预期反复。")
        self.assertNotIn("USD", report)  # 前置自检:样本确实全文无 USD
        v = check_report.check_weekly(report)
        self.assertTrue(any("CURRENCY_MISSING" in x and "USD" in x for x in v))


if __name__ == "__main__":
    unittest.main()


FIX_PHP = "区间内 2 次不同定盘(2026-08-07 至 2026-08-10)"
ART_PHP = "区间内至少 3 条(1/5 天未采到)"
OFF_PHP = "未接入或全区间采集失败,有无公告无法判定"

DIGEST_OBJ = {"week": "2026-W33",
              "generated_from": ["2026-08-07", "2026-08-10"],
              "rates": {"PHP": {"chg_pct_week": -0.192, "range_low": 60.75,
                                "range_high": 60.867, "fixings": 2,
                                "fixings_verdict": FIX_PHP}},
              "events": {"PHP": {"articles_verdict": ART_PHP,
                                 "official_verdict": OFF_PHP}},
              "verdicts": {"命中": 1, "未命中": 0, "无法判定": 15, "未判定": 10},
              "verdict_details": [{"date": "2026-08-07", "currency": "PHP",
                                   "verdict": "命中"}]}
DIGEST = json.dumps(DIGEST_OBJ, ensure_ascii=False)

WEEKLY_OK = """# 外汇周报 2026-W33

> 覆盖日报:3 份(2026-08-07, 2026-08-08, 2026-08-10);缺失日期:无

## 本周主线
- 比索本周走强

## 各币种一周归因
USD / EUR / PHP 周涨跌 -0.192%%,区间 60.75–60.867;%s。事件:%s;公告:%s / THB / BRL

## 复盘汇总
- 命中 1、未命中 0、无法判定 15、未判定 10

## 下周关注
- 关注定盘更新

## 缺漏汇总
- 无
""" % (FIX_PHP, ART_PHP, OFF_PHP)


class WeeklyDigestTraceabilityTest(unittest.TestCase):
    """周报数字溯源(delta spec: 周报数字溯源 / 未提供聚合文件)。"""

    def test_compliant_weekly_passes(self):
        self.assertEqual(check_report.check_weekly(WEEKLY_OK, DIGEST), [])

    def test_fabricated_number_caught(self):
        bad = WEEKLY_OK.replace("60.867", "61.999")
        v = check_report.check_weekly(bad, DIGEST)
        self.assertTrue(any("NUMBER_UNTRACEABLE" in x and "61.999" in x for x in v), v)

    def test_number_from_daily_report_allowed(self):
        bad = WEEKLY_OK.replace("区间 60.75–60.867", "区间 60.75–60.867,期间见 33.013")
        self.assertTrue(check_report.check_weekly(bad, DIGEST))          # 无日报时被拦
        daily = "PHP 33.013"
        self.assertEqual(check_report.check_weekly(bad, DIGEST, [daily]), [])

    def test_without_digest_behaviour_unchanged(self):
        bad = WEEKLY_OK.replace("60.867", "61.999")
        self.assertEqual(check_report.check_weekly(bad), [])             # 不传即不查数字


class StrictBriefTest(unittest.TestCase):
    """要点表溯源(delta spec: 要点表数字溯源 / 未启用要点表溯源)。"""

    SNAP = json.dumps({"date": "2026-08-10", "rates": {"PHP": {"primary": 60.75}},
                       "macro": [], "events": {}, "gaps": []})

    def test_brief_number_outside_snapshot_caught(self):
        brief = "要点表\n- primary 60.75\n- 自己编的 99.123"
        v = check_report.check_daily("# r\n", self.SNAP, brief, strict_brief=True)
        self.assertTrue(any("BRIEF_NUMBER_UNTRACEABLE" in x and "99.123" in x for x in v), v)

    def test_compliant_brief_not_flagged(self):
        brief = "要点表\n- primary 60.75"
        v = check_report.check_daily("# r\n", self.SNAP, brief, strict_brief=True)
        self.assertFalse([x for x in v if "BRIEF_NUMBER_UNTRACEABLE" in x], v)

    def test_without_flag_behaviour_unchanged(self):
        brief = "要点表\n- 自己编的 99.123"
        v = check_report.check_daily("# r\n", self.SNAP, brief)
        self.assertFalse([x for x in v if "BRIEF_NUMBER_UNTRACEABLE" in x], v)


class BriefReviewBlockExemptionTest(unittest.TestCase):
    """`--strict-brief` 的白名单是「**当日**快照 ∪ 小整数」,而 `scripts/review.py`
    往要点表尾部追加的复盘材料写的是**观点日**的定盘价与观点原文里的数字 ——
    两者结构性互斥。实测 2026-08-10 与 2026-08-13 各出 4 条
    `BRIEF_NUMBER_UNTRACEABLE`,报告正文零违规,炸的全是脚本自己写进去的行。

    且这不是偶发:SKILL 要求 trigger 绑市场可观测变量,合规的 trigger 必然带
    数字。以前不发作只因为历史 trigger 全是「采集恢复」这类**违规的**自指形态。

    修法**不是**整块豁免:块头之前一个字不改,块头之后**只豁免匹配
    review.py 行式样的行**。伪造成本因此是「伪造一整条格式完整的复盘行」,
    而不是「写一行假块头」。
    """

    SNAP = json.dumps({"date": "2026-08-13",
                       "rates": {"PHP": {"primary": 61.325}},
                       "macro": [], "events": {}, "gaps": []})
    # 观点日那一侧的数字:1.613 / 6.761006 / 4.75 / 61.178 都不在当日快照里
    MATERIAL = ("- PHP | 观点日 2026-08-12 | 情景: 实际利率 -1.613 为五经济体最低"
                " | 触发条件: 菲律宾 CPI 低于上期值 6.761006 且政策利率维持 4.75"
                " | 关注方向: down | 汇率 61.178→61.325 | 方向核对: 未命中")
    BLOCK_NUMS = ("1.613", "6.761006", "4.75", "61.178")
    HEAD = "# 要点表 2026-08-13\n- 当日定盘 61.325\n"

    def _heading(self):
        return check_report.REVIEW_BLOCK_HEADING

    def _brief(self, head_extra="", block_lines=None, headings=1, head=None):
        lines = [(self.HEAD if head is None else head).rstrip("\n")]
        if head_extra:
            lines.append(head_extra)
        body = block_lines if block_lines is not None else [self.MATERIAL]
        for _ in range(headings):
            lines += ["", self._heading(), ""] + list(body)
        return "\n".join(lines) + "\n"

    def _codes(self, brief, notes=None):
        return check_report.check_daily("# r\n", self.SNAP, brief,
                                        strict_brief=True, notes=notes)

    @staticmethod
    def _untraceable(v):
        return {x.split("要点表数字 ")[1].split(" ")[0]
                for x in v if x.startswith("BRIEF_NUMBER_UNTRACEABLE")}

    def test_numbers_before_the_heading_are_still_traced(self):
        """变异靶点:豁免对整份要点表生效(不切段)。块头**之前**是 LLM 手写
        部分,判定一个字不改。"""
        v = self._codes(self._brief(head_extra="- 自己编的 99.123"))
        self.assertIn("99.123", self._untraceable(v), v)

    def test_generated_material_line_numbers_are_exempted(self):
        v = self._codes(self._brief())
        self.assertEqual(self._untraceable(v) & set(self.BLOCK_NUMS), set(), v)

    def test_handwritten_line_after_the_heading_is_still_traced(self):
        """变异靶点:豁免对块头之后**所有**行生效(不校验行式样)。
        块头之后混进的手写行必须照查 —— 否则「写一行假块头」就是通行证。"""
        v = self._codes(self._brief(
            block_lines=[self.MATERIAL, "- 我自己补一句,汇率大约 77.777"]))
        self.assertIn("77.777", self._untraceable(v), v)

    def test_forged_line_that_only_looks_like_a_bullet_is_traced(self):
        """只带块头式样的前缀、不成完整行式样的伪造行也要照查。"""
        v = self._codes(self._brief(
            block_lines=["- PHP | 观点日 2026-08-12 | 顺便一提 55.5"]))
        self.assertIn("55.5", self._untraceable(v), v)

    def test_skip_declaration_is_emitted(self):
        """变异靶点:声明行被删掉。「跳过」与「通过」在输出上必须可区分。"""
        notes = []
        self._codes(self._brief(), notes=notes)
        self.assertIn("BRIEF_REVIEW_BLOCK_SKIPPED: 复盘材料块 3 行未纳入要点表数字溯源",
                      notes)

    def test_skip_declaration_counts_only_exempted_lines(self):
        notes = []
        self._codes(self._brief(
            block_lines=[self.MATERIAL, "- 我自己补一句,汇率大约 77.777"]),
            notes=notes)
        self.assertIn("BRIEF_REVIEW_BLOCK_SKIPPED: 复盘材料块 3 行未纳入要点表数字溯源",
                      notes)

    def test_declaration_is_not_a_violation(self):
        """声明不改返回码 —— 它不是违规码。"""
        v = self._codes(self._brief())
        self.assertEqual([x for x in v if x.startswith("BRIEF_")], [], v)

    def test_two_headings_are_malformed_and_exempt_nothing(self):
        """变异靶点:块头出现两次时静默取第一个。≥2 次必须出违规,且
        **一行都不豁免**(失败关闭),否则伪造第二个块头即可整段脱管。"""
        notes = []
        v = self._codes(self._brief(headings=2), notes=notes)
        self.assertTrue([x for x in v if x.startswith("BRIEF_REVIEW_BLOCK_MALFORMED")], v)
        self.assertTrue(set(self.BLOCK_NUMS) <= self._untraceable(v), v)
        self.assertEqual([n for n in notes if "BRIEF_REVIEW_BLOCK_SKIPPED" in n], [],
                         notes)

    def test_no_heading_behaves_exactly_as_before(self):
        notes = []
        brief = self.HEAD + "- 自己编的 99.123\n"
        v = self._codes(brief, notes=notes)
        self.assertIn("99.123", self._untraceable(v), v)
        self.assertEqual([n for n in notes if "BRIEF_REVIEW_BLOCK" in n], [], notes)

    def test_without_strict_brief_nothing_changes(self):
        notes = []
        v = check_report.check_daily("# r\n", self.SNAP,
                                     self._brief(head_extra="- 自己编的 99.123"),
                                     notes=notes)
        self.assertEqual([x for x in v if x.startswith("BRIEF_")], [], v)
        self.assertEqual([n for n in notes if "BRIEF_" in n], [], notes)

    def test_declaration_reaches_stdout_with_rc_zero(self):
        """声明必须真的印出去 —— 只放进 notes 而 main 不打印等于没有。

        走 main() 就得用与 make_report() 配套的 SNAP_TEXT 当快照,故要点表
        手写部分只放该快照里的数;复盘材料行里那 4 个数仍不在快照中 ——
        豁免一旦失效,rc 立刻由 0 变 1,这条断言不是走过场。"""
        head = "# 要点表 2026-08-10\n- 当日定盘 60.843\n"
        with tempfile.TemporaryDirectory() as tmp:
            paths = {}
            for name, text in (("r.md", make_report()), ("s.json", SNAP_TEXT),
                               ("b.md", self._brief(head=head))):
                paths[name] = os.path.join(tmp, name)
                with open(paths[name], "w", encoding="utf-8") as f:
                    f.write(text)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = check_report.main([paths["r.md"], paths["s.json"],
                                        "--brief", paths["b.md"],
                                        "--mode", "daily", "--strict-brief"])
            out = buf.getvalue()
        self.assertEqual(rc, 0, out)
        self.assertIn("BRIEF_REVIEW_BLOCK_SKIPPED", out)
        self.assertIn("CHECK PASSED", out)

    def test_heading_is_not_copied_into_the_checker_source(self):
        """变异靶点:块头常量在两处各写一遍而漂移。唯一事实源在
        `scripts/review.py`(它是产出方),校验器只许导入。"""
        with open(check_report.__file__, encoding="utf-8") as f:
            tree = ast.parse(f.read())
        copies = [n.lineno for n in ast.walk(tree)
                  if isinstance(n, ast.Constant) and isinstance(n.value, str)
                  and check_report.REVIEW_BLOCK_HEADING in n.value]
        self.assertEqual(copies, [],
                         "块头在校验器里又写了一遍(第 %s 行),会与 review.py 漂移"
                         % copies)


class DigestFailClosedTest(unittest.TestCase):
    """digest 不可用时必须响亮失败 —— 打印 PASS 却什么都没查是最坏的失败模式。"""

    def _run(self, tmp, digest_body, extra=()):
        report = os.path.join(tmp, "w.md")
        with open(report, "w", encoding="utf-8") as f:
            f.write(WEEKLY_OK)
        argv = [report, "--mode", "weekly"]
        if digest_body is not None:
            dpath = os.path.join(tmp, "d.json")
            with open(dpath, "w", encoding="utf-8") as f:
                f.write(digest_body)
            argv += ["--digest", dpath]
        return check_report.main(argv + list(extra))

    def test_empty_digest_is_rc2(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(self._run(tmp, ""), 2)

    def test_non_json_digest_is_rc2(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(self._run(tmp, "# 这是一份 markdown"), 2)

    def test_wrong_shape_digest_is_rc2(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(self._run(tmp, json.dumps({"foo": 1})), 2)
            self.assertEqual(self._run(tmp, json.dumps([1, 2])), 2)

    def test_daily_without_digest_is_rc2(self):
        with tempfile.TemporaryDirectory() as tmp:
            daily = os.path.join(tmp, "d.md")
            with open(daily, "w", encoding="utf-8") as f:
                f.write("x")
            self.assertEqual(self._run(tmp, None, ["--daily", daily]), 2)

    def test_valid_digest_still_passes(self):
        """fixture 必须是**真实 digest 形态** —— _rates_digest 与 _events_one
        永远会写结论句字段,缺了就是脚本缺陷,不该由校验器放行。"""
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(self._run(tmp, DIGEST), 0)


class WeeklyRejectsPositionalSnapshotTest(unittest.TestCase):
    """weekly 模式收到位置参数即**响亮失败**(rc=2),不得静默放行。

    ---- 这条缺陷是「不读的参数」这一族里最贵的一个,实测口径如下 ----

    `build_parser()` 注册的 `snapshot` 是 `nargs="?"` 的位置参数,而 `main()`
    的 weekly 分支**从来不读它**(修前 `check_report.py:453` 的 docstring 自己
    把这一点当成"绕过手法之二"写着:「复用既有参数的魔法值(weekly 模式下
    `args.snapshot` 不读)」)。于是这条命令行:

        check_report.py reports/weekly/W.md state/weekly-digest-W.json --mode weekly

    看上去"把聚合文件传进去了",实际上 `--digest` 缺席 → 结论句闸门与数字
    溯源**整层不跑**,却照样 `CHECK PASSED` / rc=0。

    实测(HEAD eef783e,本仓库真实产物,未改任何报告):
    - 位置参数形态 → `CHECK PASSED` rc=0;
    - **把位置参数换成一个根本不存在的路径** `/does/not/exist.json`
      → 仍然 `CHECK PASSED` rc=0 —— 决定性证据:那个参数一个字节都没被读过,
      连"文件在不在"都没查。
    - 同一份产物换 `--digest` 形态 → 结论句层与数字溯源层才真的跑起来。

    **修法刻意不猜意图**:不把位置参数"当作 digest 用"。猜测正是这条缺陷的
    来源 —— 调用方以为传进去了,脚本以为没传,两边都不报错。所以只要
    `--mode weekly` 且位置参数非空,就 rc=2 + stderr 可操作提示,**无论
    `--digest` 是否同时给了**。
    """

    def _run(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = check_report.main(argv)
        return rc, out.getvalue(), err.getvalue()

    def _inputs(self, tmp):
        rp = os.path.join(tmp, "w.md")
        dp = os.path.join(tmp, "d.json")
        for path, text in ((rp, WEEKLY_OK), (dp, DIGEST)):
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
        return rp, dp

    def test_positional_snapshot_is_rc2(self):
        """修前实测:这一条正是 `CHECK PASSED` rc=0。"""
        with tempfile.TemporaryDirectory() as tmp:
            rp, dp = self._inputs(tmp)
            rc, _, err = self._run([rp, dp, "--mode", "weekly"])
        self.assertEqual(rc, 2)
        self.assertTrue(err.strip(), "rc=2 却没有 stderr 说明")

    def test_rejection_names_the_two_flags_to_use_instead(self):
        """提示必须**可操作**:光说"不接受"会让调用方改成删掉那个参数,
        于是从"静默不查"变成"静默不查且没人知道该传什么"。两个开关都要点名。"""
        with tempfile.TemporaryDirectory() as tmp:
            rp, dp = self._inputs(tmp)
            _, _, err = self._run([rp, dp, "--mode", "weekly"])
        self.assertIn("--digest", err)
        self.assertIn("--daily", err)

    def test_rejection_stops_the_run_instead_of_warning(self):
        """**变异靶心**:把提示写成 warning 却继续跑完并 rc=0。
        判据是"结论行一个都不许出现" —— 只断言 rc 时,`print(...)` 之后
        照跑照打 `CHECK PASSED` 的写法只要再把 rc 改回 0 就活了。"""
        with tempfile.TemporaryDirectory() as tmp:
            rp, dp = self._inputs(tmp)
            rc, out, _ = self._run([rp, dp, "--mode", "weekly"])
        self.assertEqual(rc, 2)
        self.assertNotIn("CHECK PASSED", out)
        self.assertNotIn("CHECK FAILED", out)

    def test_positional_is_rejected_even_when_digest_is_also_given(self):
        """**不得猜测意图**。允许"位置参数 + --digest 并存"就等于承认那个位置
        还有语义,下一个人照样会只传位置参数。"""
        with tempfile.TemporaryDirectory() as tmp:
            rp, dp = self._inputs(tmp)
            rc, out, _ = self._run([rp, dp, "--mode", "weekly", "--digest", dp])
        self.assertEqual(rc, 2)
        self.assertNotIn("CHECK PASSED", out)

    def test_positional_is_not_silently_treated_as_a_digest(self):
        """把位置参数**当 digest 用**是最像"体贴"的修法,也正是缺陷的来源。
        判据:喂一个**结构不符**的位置参数,rc 必须是"拒收位置参数"的 2,
        且 stderr 说的是位置参数那句,不是"聚合文件结构不符"。"""
        with tempfile.TemporaryDirectory() as tmp:
            rp, _ = self._inputs(tmp)
            bad = os.path.join(tmp, "bad.json")
            with open(bad, "w", encoding="utf-8") as f:
                f.write(json.dumps({"foo": 1}))
            rc, _, err = self._run([rp, bad, "--mode", "weekly"])
        self.assertEqual(rc, 2)
        self.assertIn("--digest", err)
        self.assertNotIn("结构不符", err)

    def test_no_exemption_token_survives_the_positional_slot(self):
        """**接管 `NoLegacyExemptionSwitchTest` 删掉的那一维覆盖。**

        那边的 base 此前有一维 `snap_slot`,配合「既有位置参数魔法值」那一族,
        守的是类注释里的绕过手法 ②:*不新增任何注册,直接拿 weekly 不读的
        那个位置参数当豁免扳机*(`if args.snapshot == "legacy": ...`)。
        weekly 拒收位置参数之后,那条 base 自己就是 rc=2,整维随之作废。

        覆盖不能跟着一起消失,所以搬到这里,而且守得更死:逐个把
        `EXEMPTION_TOKENS` 塞进位置参数,要求**每一个**都 rc=2 且 stdout
        不出现任何结论行 —— 魔法值连被读到的机会都没有。扳机若被插在拒收
        之前(唯一还能生效的位置),这里立刻红。
        """
        with tempfile.TemporaryDirectory() as tmp:
            rp, dp = self._inputs(tmp)
            for tok in NoLegacyExemptionSwitchTest.EXEMPTION_TOKENS:
                for argv in ([rp, tok, "--mode", "weekly"],
                             [rp, tok, "--mode", "weekly", "--digest", dp]):
                    with self.subTest(token=tok, argv=len(argv)):
                        rc, out, _ = self._run(argv)
                        self.assertEqual(rc, 2, out)
                        self.assertNotIn("CHECK PASSED", out)
                        self.assertNotIn("CHECK FAILED", out)

    def test_daily_mode_still_takes_its_positional_snapshot(self):
        """daily 模式**一个字不改**:它的位置参数是必需的,且真的被读。"""
        with tempfile.TemporaryDirectory() as tmp:
            rp = os.path.join(tmp, "r.md")
            sp = os.path.join(tmp, "s.json")
            bp = os.path.join(tmp, "b.md")
            for path, text in ((rp, make_report()), (sp, SNAP_TEXT),
                               (bp, BRIEF)):
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text)
            rc, out, _ = self._run([rp, sp, "--brief", bp, "--mode", "daily"])
        self.assertEqual(rc, 0)
        self.assertIn("CHECK PASSED", out)

    def test_weekly_without_the_positional_is_unaffected(self):
        """拒收的是"给了位置参数",不是 weekly 本身。"""
        with tempfile.TemporaryDirectory() as tmp:
            rp, dp = self._inputs(tmp)
            rc, out, _ = self._run([rp, "--mode", "weekly", "--digest", dp])
        self.assertEqual(rc, 0)
        self.assertIn("CHECK PASSED", out)


class WeeklyDigestAbsentDeclarationTest(unittest.TestCase):
    """weekly 未提供 `--digest` 时,**「跳过」与「通过」在输出上必须可区分**。

    「未提供聚合文件」是 delta spec 里既有的**合法**形态(`#### Scenario:
    未提供聚合文件` —— 退回结构检查、行为不变、且不得报结论句字段缺失),
    所以它**不是违规、不改退出码**。但它此前跑出的是**裸 `CHECK PASSED`**,
    与"结论句与数字溯源全部查过且全过"逐字不可分辨 —— 这正是本 change 反复
    要消灭的那个形态,同一套原则已经产出过 `VERDICT_SKIPPED_LEGACY`、
    `VERDICT_SKIPPED_NO_DERIVED`、`BRIEF_REVIEW_BLOCK_SKIPPED` 三条声明。

    这一条与上面那条拒收位置参数是一对:拒收把"以为传了"变成响亮失败,
    声明把"确实没传"变成看得见的事实。少任何一半,静默放行都还在。
    """

    LINE = "WEEKLY_DIGEST_ABSENT_SKIPPED: 未提供 --digest,本次未校验结论句与数字溯源"

    def _run(self, argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = check_report.main(argv)
        return rc, out.getvalue()

    def _report(self, tmp, text=WEEKLY_OK):
        rp = os.path.join(tmp, "w.md")
        with open(rp, "w", encoding="utf-8") as f:
            f.write(text)
        return rp

    def test_declaration_is_printed_when_digest_is_absent(self):
        """**变异靶心**:删掉声明行 → 退回裸 CHECK PASSED,本条必须红。"""
        with tempfile.TemporaryDirectory() as tmp:
            rc, out = self._run([self._report(tmp), "--mode", "weekly"])
        self.assertIn(self.LINE, out)
        self.assertEqual(rc, 0)

    def test_declaration_is_not_a_violation(self):
        """**变异靶心**:把它做成违规(进 violations / 改 rc)→ 本条必须红。
        「未提供聚合文件」是 spec 里的合法形态,不是错误。"""
        with tempfile.TemporaryDirectory() as tmp:
            rc, out = self._run([self._report(tmp), "--mode", "weekly"])
        self.assertEqual(rc, 0)
        self.assertIn("CHECK PASSED", out)
        self.assertNotIn("CHECK FAILED", out)
        self.assertNotIn(" - " + self.LINE, out)   # 违规是带 " - " 前缀打印的

    def test_declaration_precedes_the_verdict_line(self):
        """降级声明必须先于结论行 —— 读者在看到 PASSED 之前就得知道少查了什么。
        与既有 notes 的打印顺序同一条规矩。"""
        with tempfile.TemporaryDirectory() as tmp:
            _, out = self._run([self._report(tmp), "--mode", "weekly"])
        self.assertLess(out.index(self.LINE), out.index("CHECK PASSED"))

    def test_declaration_is_absent_when_digest_is_given(self):
        """闭合件:无条件打印这行,声明就退化成噪声,"查过没查过"又不可分辨。"""
        with tempfile.TemporaryDirectory() as tmp:
            dp = os.path.join(tmp, "d.json")
            with open(dp, "w", encoding="utf-8") as f:
                f.write(DIGEST)
            rc, out = self._run([self._report(tmp), "--mode", "weekly",
                                 "--digest", dp])
        self.assertEqual(rc, 0)
        self.assertNotIn("WEEKLY_DIGEST_ABSENT_SKIPPED", out)

    def test_declaration_still_printed_when_the_report_is_violating(self):
        """rc=1 那条路径上同样要出声:少查了什么与查出了什么互不替代。"""
        with tempfile.TemporaryDirectory() as tmp:
            rp = self._report(tmp, WEEKLY_OK.replace("## 下周关注", "## 删掉了"))
            rc, out = self._run([rp, "--mode", "weekly"])
        self.assertEqual(rc, 1)
        self.assertIn(self.LINE, out)

    def test_daily_mode_never_prints_it(self):
        """daily 模式**一个字不改**。"""
        with tempfile.TemporaryDirectory() as tmp:
            rp = os.path.join(tmp, "r.md")
            sp = os.path.join(tmp, "s.json")
            for path, text in ((rp, make_report()), (sp, SNAP_TEXT)):
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text)
            rc, out = self._run([rp, sp, "--mode", "daily"])
        self.assertEqual(rc, 0)
        self.assertNotIn("WEEKLY_DIGEST_ABSENT_SKIPPED", out)


class WeeklyGapOmittedTest(unittest.TestCase):
    """I9 收口检查此前零测试(变异存活):digest 的每个缺漏源须在缺漏汇总出现。"""

    DIGEST_OBJ = {"week": "2026-W33", "generated_from": ["2026-08-10"],
                  "gaps_by_source": {"gdelt": 18, "dbnomics": 3},
                  "events": {}, "rates": {}}

    def _weekly(self, gap_body):
        return WEEKLY_OK.replace("## 缺漏汇总\n- 无\n", "## 缺漏汇总\n" + gap_body)

    def test_missing_source_flagged(self):
        report = self._weekly("- [gdelt] 限流 波及全周\n")
        v = check_report.check_weekly(report, DIGEST, (), self.DIGEST_OBJ)
        self.assertTrue(any("GAP_OMITTED" in x and "dbnomics" in x for x in v), v)

    def test_all_sources_present_passes(self):
        report = self._weekly("- [gdelt] 限流\n- [dbnomics] 超时\n")
        v = check_report.check_weekly(report, DIGEST, (), self.DIGEST_OBJ)
        self.assertFalse([x for x in v if "GAP_OMITTED" in x], v)
        self.assertEqual(v, [])

    def test_without_digest_object_no_gap_check(self):
        report = self._weekly("- [gdelt] 限流\n")
        v = check_report.check_weekly(report, DIGEST, ())
        self.assertFalse([x for x in v if "GAP_OMITTED" in x], v)


class CheckVerdictsCoreTest(unittest.TestCase):
    """核心谓词的三态与两道让位。日报与周报共用这一份判定,两处各写一遍
    必然漂移(见 scripts/fixings.py 的模块注释)。

    delta spec 场景:结论句被改动一个字 / 结论句整句缺失 / 结论句为空串 /
    报告未覆盖某币种 / 基准货币在定盘容器中无条目。"""

    FIELDS = ("articles_verdict",)

    def _run(self, report, container, required=True, covered=None):
        return check_report.check_verdicts(
            report, container, self.FIELDS,
            set(check_report.CURRENCIES) if covered is None else covered,
            required, "digest.events")

    def test_quoted_sentence_passes(self):
        s = "区间内至少 26 条(3/6 天未采到)"
        got = self._run("前言。%s。后话。" % s, {"USD": {"articles_verdict": s}})
        self.assertEqual(got, ([], 0))

    def test_one_character_changed_is_not_quoted(self):
        s = "区间内至少 26 条(3/6 天未采到)"
        v, _ = self._run(s.replace("26", "15"), {"USD": {"articles_verdict": s}})
        self.assertTrue(any(x.startswith("VERDICT_NOT_QUOTED") and "USD" in x
                            for x in v), v)
        # label 是三个调用点唯一的区分手段(digest.events / digest.rates /
        # derived.events),抹掉它三类违规就分不出来源
        self.assertTrue(any("digest.events.USD" in x for x in v), v)

    def test_expected_sentence_is_echoed_in_the_violation(self):
        """违规信息必须给出期望的整句原文,否则报告作者无从修。"""
        s = "区间内至少 26 条(3/6 天未采到)"
        v, _ = self._run("完全无关的正文", {"USD": {"articles_verdict": s}})
        self.assertTrue(any(s in x for x in v), v)

    def test_whole_sentence_absent_is_not_quoted(self):
        """数字词袋放行的正是这一形态:26、3、6 都在别处出现过。"""
        s = "区间内至少 26 条(3/6 天未采到)"
        v, _ = self._run("正文写了 26 与 3 与 6,但没有整句",
                         {"USD": {"articles_verdict": s}})
        self.assertTrue(any("VERDICT_NOT_QUOTED" in x for x in v), v)

    def test_empty_string_is_a_violation_not_a_pass(self):
        """任意报告都"包含"空串 —— 最直接的假绿入口。"""
        for bad in ("", "   ", "　", "\n\t "):
            v, skipped = self._run("任意报告", {"USD": {"articles_verdict": bad}})
            self.assertTrue(any("VERDICT_EMPTY" in x for x in v), (repr(bad), v))
            self.assertEqual(skipped, 0)

    def test_non_string_is_malformed_and_does_not_crash(self):
        for bad, name in (({"a": 1}, "dict"), (7, "int"), (["x"], "list"),
                          (True, "bool"), (1.5, "float")):
            v, _ = self._run("任意报告", {"USD": {"articles_verdict": bad}})
            self.assertTrue(any("VERDICT_MALFORMED" in x for x in v), (bad, v))
            self.assertTrue(any(name in x for x in v), (bad, v))

    def test_absent_field_when_required_is_a_violation(self):
        v, skipped = self._run("任意报告", {"USD": {}}, required=True)
        self.assertTrue(any("VERDICT_ABSENT" in x and "USD" in x for x in v), v)
        self.assertEqual(skipped, 0)

    def test_none_value_counts_as_absent(self):
        v, _ = self._run("任意报告", {"USD": {"articles_verdict": None}},
                         required=True)
        self.assertTrue(any("VERDICT_ABSENT" in x for x in v), v)

    def test_absent_field_when_not_required_is_counted_not_reported(self):
        """存量快照:跳过,但必须被计数 —— 「跳过」与「通过」不可同形。"""
        v, skipped = self._run("任意报告", {"USD": {}}, required=False)
        self.assertEqual(v, [])
        self.assertEqual(skipped, 1)

    def test_currency_not_covered_by_report_is_skipped(self):
        """让位 ①:已有 SECTION_MISSING / CURRENCY_MISSING,同一处缺失
        不得产生两条违规。"""
        got = self._run("报告只写了 EUR", {"USD": {}}, required=True,
                        covered={"EUR"})
        self.assertEqual(got, ([], 0))

    def test_currency_absent_from_container_is_legal(self):
        """让位 ②:digest["rates"] 没有 USD 是合法形态(基准货币无定盘价),
        不是缺字段;只有币种条目存在时才要求其字段齐全。"""
        got = self._run("任意报告", {"PHP": {"articles_verdict": "任意报告"}},
                        required=True, covered={"USD", "PHP"})
        self.assertEqual(got, ([], 0))

    def test_non_dict_container_is_skipped(self):
        for bad in (None, [], "x", 7, True):
            self.assertEqual(self._run("任意报告", bad), ([], 0))

    def test_non_dict_entry_is_skipped(self):
        for bad in ("not a dict", 7, [], None):
            self.assertEqual(self._run("任意报告", {"USD": bad}), ([], 0))

    def test_every_currency_is_checked_not_just_the_first(self):
        """只查 next(iter(container)) 的变异必须被杀 —— 错的是最后一个币种。"""
        good = "区间内至少 3 条"
        container = {c: {"articles_verdict": good}
                     for c in check_report.CURRENCIES}
        container["BRL"]["articles_verdict"] = "区间内至少 9 条"
        v, _ = self._run(good, container)
        self.assertTrue(any("VERDICT_NOT_QUOTED" in x and "BRL" in x for x in v), v)

    def test_all_fields_in_the_tuple_are_checked(self):
        """fields 元组少一项的变异必须被杀。"""
        container = {"USD": {"articles_verdict": "甲句", "official_verdict": "乙句"}}
        v, _ = check_report.check_verdicts(
            "正文只有甲句", container, check_report.VERDICT_FIELDS_EVENTS,
            {"USD"}, True, "digest.events")
        self.assertTrue(any("official_verdict" in x for x in v), v)
        self.assertFalse([x for x in v if "articles_verdict" in x], v)

    def test_required_true_never_skips(self):
        """T4 的 `found, _ =` 丢弃之所以无损,靠的是这条不变量。"""
        for container in ({"USD": {}}, {"USD": {"articles_verdict": None}},
                          {c: {} for c in check_report.CURRENCIES}):
            self.assertEqual(self._run("任意报告", container, required=True)[1], 0)

    def test_skip_is_counted_per_currency_not_per_field(self):
        """同一币种缺两个字段仍只算 1 —— T6 打印的是「N 个币种」。"""
        v, skipped = check_report.check_verdicts(
            "任意报告", {"USD": {}}, check_report.VERDICT_FIELDS_EVENTS,
            {"USD"}, False, "digest.events")
        self.assertEqual((v, skipped), ([], 1))

    def test_skip_accumulates_across_currencies(self):
        v, skipped = self._run("任意报告",
                               {c: {} for c in check_report.CURRENCIES},
                               required=False)
        self.assertEqual((v, skipped), ([], 5))


class VerdictFieldConstantsTest(unittest.TestCase):
    """字段名 SHALL 显式枚举,MUST NOT 按名字模式搜集 —— digest 顶层的
    `verdicts` 是计数 dict、`verdict_details` 是 list,模式匹配会把非字符串
    结构送进字符串比对。"""

    def test_constants_are_explicit_tuples(self):
        self.assertEqual(check_report.VERDICT_FIELDS_EVENTS,
                         ("articles_verdict", "official_verdict"))
        self.assertEqual(check_report.VERDICT_FIELDS_RATES, ("fixings_verdict",))
        self.assertEqual(check_report.VERDICT_FIELD_DAILY, ("events_verdict",))
        self.assertEqual(check_report.DERIVED_VERDICT_SCHEMA, 2)

    def test_counting_structures_are_not_enumerated(self):
        every = (check_report.VERDICT_FIELDS_EVENTS
                 + check_report.VERDICT_FIELDS_RATES
                 + check_report.VERDICT_FIELD_DAILY)
        self.assertNotIn("verdicts", every)
        self.assertNotIn("verdict_details", every)

    def test_counting_dict_fed_to_the_predicate_is_inert(self):
        """把 digest 顶层的计数 dict 直接喂进核心谓词也不能崩或误报。"""
        v, skipped = check_report.check_verdicts(
            "任意报告", {"命中": 0, "未命中": 0, "无法判定": 15},
            check_report.VERDICT_FIELDS_EVENTS,
            set(check_report.CURRENCIES), True, "digest.verdicts")
        self.assertEqual((v, skipped), ([], 0))

    def test_detail_list_fed_to_the_predicate_is_inert(self):
        v, skipped = check_report.check_verdicts(
            "任意报告", [{"date": "2026-08-10", "verdict": "命中"}],
            check_report.VERDICT_FIELDS_EVENTS,
            set(check_report.CURRENCIES), True, "digest.verdict_details")
        self.assertEqual((v, skipped), ([], 0))


class WeeklyVerdictQuotingTest(unittest.TestCase):
    """周报三类结论句的逐字引用(delta spec:结论句与聚合文件不一致 /
    三类结论句全覆盖 / 基准货币在定盘容器中无条目 / 未提供聚合文件 /
    周报未覆盖某币种 / 结论句为空串)。"""

    def _run(self, report, digest_obj=None):
        return check_report.check_weekly(
            report, DIGEST, (), digest_obj if digest_obj is not None else DIGEST_OBJ)

    def test_fully_quoted_weekly_passes(self):
        self.assertEqual(self._run(WEEKLY_OK), [])

    def test_articles_verdict_reworded_is_caught(self):
        """实测形态:正文写「至少 15 条(3/5 天未采到)」而 digest 是
        「至少 26 条(3/6 天未采到、…)」,词袋检查照样打印通过。"""
        bad = WEEKLY_OK.replace(ART_PHP, "区间内至少 3 条")
        v = self._run(bad)
        self.assertTrue(any("VERDICT_NOT_QUOTED" in x and "articles_verdict" in x
                            for x in v), v)

    def test_official_verdict_missing_is_caught(self):
        bad = WEEKLY_OK.replace(OFF_PHP, "公告方面本周平静")
        v = self._run(bad)
        self.assertTrue(any("VERDICT_NOT_QUOTED" in x and "official_verdict" in x
                            for x in v), v)

    def test_fixings_verdict_missing_is_caught(self):
        """三类只查一类的变异必须被杀:定盘类在 rates 容器,与 events 分开取。"""
        bad = WEEKLY_OK.replace(FIX_PHP, "全周仅 2 次定盘")
        v = self._run(bad)
        self.assertTrue(any("VERDICT_NOT_QUOTED" in x and "fixings_verdict" in x
                            for x in v), v)

    def test_base_currency_absent_from_rates_container_is_legal(self):
        """digest["rates"] 没有 USD 是合法形态(基准货币无定盘价)。
        WEEKLY_OK 覆盖了 USD,但 rates 容器里没有它 —— 不得报字段缺失。"""
        v = self._run(WEEKLY_OK)
        self.assertFalse([x for x in v if "USD" in x and "VERDICT" in x], v)

    def test_currency_not_covered_reports_only_currency_missing(self):
        bad = WEEKLY_OK.replace("USD / EUR / PHP", "EUR / 比索")
        self.assertNotIn("PHP", bad)
        v = self._run(bad)
        self.assertTrue(any("CURRENCY_MISSING" in x and "PHP" in x for x in v), v)
        self.assertFalse([x for x in v if "VERDICT" in x and "PHP" in x], v)

    def test_currency_wholly_absent_is_not_double_reported(self):
        """上一条对「covered 恒取全集」的变异无鉴别力:那里只删掉币种名,
        三句结论句还留在正文里,两种取法结果相同(自跑变异实测存活)。
        这条把整行归因删掉 —— PHP 的三句一并消失,让位机制成了不报
        VERDICT 的唯一原因,同一处缺失才真的只产生一条违规。"""
        line = [x for x in WEEKLY_OK.splitlines() if x.startswith("USD / EUR / PHP")]
        self.assertEqual(len(line), 1)
        bad = WEEKLY_OK.replace(line[0], "USD / EUR / THB / BRL")
        self.assertNotIn("PHP", bad)
        self.assertNotIn(ART_PHP, bad)
        v = self._run(bad)
        self.assertTrue(any("CURRENCY_MISSING" in x and "PHP" in x for x in v), v)
        self.assertFalse([x for x in v if "VERDICT" in x], v)

    def test_empty_verdict_string_is_a_violation(self):
        obj = json.loads(DIGEST)
        obj["events"]["PHP"]["articles_verdict"] = "   "
        v = self._run(WEEKLY_OK, obj)
        self.assertTrue(any("VERDICT_EMPTY" in x for x in v), v)

    def test_non_string_verdict_is_malformed(self):
        obj = json.loads(DIGEST)
        obj["rates"]["PHP"]["fixings_verdict"] = {"text": FIX_PHP}
        v = self._run(WEEKLY_OK, obj)
        self.assertTrue(any("VERDICT_MALFORMED" in x for x in v), v)

    def test_missing_field_on_existing_entry_is_absent(self):
        obj = json.loads(DIGEST)
        del obj["events"]["PHP"]["official_verdict"]
        v = self._run(WEEKLY_OK, obj)
        self.assertTrue(any("VERDICT_ABSENT" in x and "official_verdict" in x
                            for x in v), v)

    def test_without_digest_object_no_verdict_check(self):
        """未提供 --digest 时 digest 为 None:不执行结论句检查,
        更不得因取不到而报「字段缺失」。"""
        v = check_report.check_weekly(WEEKLY_OK.replace(ART_PHP, "改写过"), DIGEST)
        self.assertFalse([x for x in v if "VERDICT" in x], v)

    def test_top_level_counting_structures_are_not_scanned(self):
        """digest 顶层的 verdicts(计数 dict)与 verdict_details(list)
        不得被当成结论句 —— 按 *verdict* 模式扫就会。"""
        v = self._run(WEEKLY_OK)
        self.assertFalse([x for x in v if "verdict_details" in x
                          or "digest.verdicts" in x], v)

    def test_violation_carries_the_source_label(self):
        """label 是三个调用点唯一的区分手段(digest.events / digest.rates /
        derived.events)。抹掉它,三类违规就分不出来源,而其余断言只看
        字段名与币种名,照样全绿 —— 代码质量审查实测该变异存活。"""
        bad = WEEKLY_OK.replace(ART_PHP, "改写过").replace(FIX_PHP, "也改写过")
        v = self._run(bad)
        self.assertTrue(any("digest.events.PHP" in x for x in v), v)
        self.assertTrue(any("digest.rates.PHP" in x for x in v), v)

    def test_missing_container_fails_loudly(self):
        """产出端坏掉时,校验器 MUST NOT 打印通过却一条都没查。
        谓词对非 dict 容器静默返回空(不越权判结构),兜底在调用点。"""
        for bad in (None, [], "x", 7):
            obj = json.loads(DIGEST)
            obj["events"] = bad
            v = self._run(WEEKLY_OK, obj)
            self.assertTrue(any("VERDICT_CONTAINER_MALFORMED" in x
                                and "digest.events" in x for x in v), (bad, v))

    def test_missing_container_key_fails_loudly(self):
        obj = json.loads(DIGEST)
        del obj["rates"]
        v = self._run(WEEKLY_OK, obj)
        self.assertTrue(any("VERDICT_CONTAINER_MALFORMED" in x
                            and "digest.rates" in x for x in v), v)


def _args_attrs(nodes):
    """一批 AST 节点里出现过的所有 `args.<x>` 的属性名。"""
    found = set()
    for n in nodes:
        for x in ast.walk(n):
            if isinstance(x, ast.Attribute) and isinstance(x.value, ast.Name) \
                    and x.value.id == "args":
                found.add(x.attr)
    return found


def _attrs_outside(node, skip):
    """`node` 子树里的 `args.<x>`,但**剪掉** `skip` 这个 if 的两个分支体
    (只保留它的 test)—— 也就是「两个 mode 都会走到的那些读取」。"""
    if node is skip:
        return _args_attrs([skip.test])
    acc = set()
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) \
            and node.value.id == "args":
        acc.add(node.attr)
    for child in ast.iter_child_nodes(node):
        acc |= _attrs_outside(child, skip)
    return acc


def _mode_read_dests():
    """**从源码推出**每个 mode 实际读到的 `args.*` dest 集合。

    这是 T8e 的修法。T8d 用的是**手写清单**,而它在落地的同一棵树上就已经
    漏了 `--strict-brief`(weekly 分支既不读 `args.brief` 也不读
    `args.strict_brief`)—— 手写表本身就是本 change 要消灭的「第二份拷贝」:
    它与源码之间没有任何机械联系,漏一个不会有人知道。

    做法:AST 解析 `check_report.py`,定位 `main()` 里按 `args.mode` 分派的
    那个 `if`,`body` / `orelse` 各自 walk 出 `args.<x>`,再并上**分支之外**
    的读取(两个 mode 都会走到)。任何一步认不出预期形状就 `AssertionError`
    炸掉 —— **绝不能静默返回空集**:那会让第六族整族无声消失,正是这里要
    消灭的病。
    """
    with open(check_report.__file__, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    fns = [n for n in ast.walk(tree)
           if isinstance(n, ast.FunctionDef) and n.name == "main"]
    if len(fns) != 1:
        raise AssertionError("check_report 里 main() 不是恰好 1 个:%d" % len(fns))
    main_fn = fns[0]
    ifs = [n for n in ast.walk(main_fn)
           if isinstance(n, ast.If) and "mode" in _args_attrs([n.test])]
    if len(ifs) != 1:
        raise AssertionError(
            "main() 里读 args.mode 的 if 不是恰好 1 个(%d)—— 分派形状变了,"
            "推导不敢猜,先更新本函数" % len(ifs))
    node = ifs[0]
    cmps = [c for c in ast.walk(node.test) if isinstance(c, ast.Compare)]
    if len(cmps) != 1 or len(cmps[0].ops) != 1 \
            or not isinstance(cmps[0].ops[0], ast.Eq) \
            or not isinstance(cmps[0].comparators[0], ast.Constant):
        raise AssertionError(
            "mode 分派不是 `args.mode == '<字面量>'` 这一形状:%s"
            % ast.dump(node.test))
    positive = cmps[0].comparators[0].value
    choices = set(next(a.choices for a in check_report.build_parser()._actions
                       if a.dest == "mode"))
    rest = choices - {positive}
    if positive not in choices or len(rest) != 1:
        raise AssertionError(
            "分派字面量 %r 与 --mode 的 choices %s 对不上(推导只支持两分支)"
            % (positive, sorted(choices)))
    outside = _attrs_outside(main_fn, node)
    return {positive: outside | _args_attrs(node.body),
            rest.pop(): outside | _args_attrs(node.orelse)}


def unread_option_specs(mode):
    """该 mode **不读**的已注册选项:`((选项名, 是否带值), ...)`。

    = `build_parser()` 注册的选项 dest 集合 − 该 mode 分支实际读到的 dest
    集合。这两端都是从源码取的,没有第三份需要人去同步的清单。
    位置参数(`option_strings` 为空)不在此列 —— 它们由 `_variants` 的
    「既有位置参数魔法值」那一族覆盖。
    """
    read = _mode_read_dests()[mode]
    specs = []
    for a in check_report.build_parser()._actions:
        if not a.option_strings or a.dest == "help" or a.dest in read:
            continue
        longs = [s for s in a.option_strings if s.startswith("--")]
        specs.append((max(longs or a.option_strings, key=len), a.nargs != 0))
    return tuple(specs)


class NoLegacyExemptionSwitchTest(unittest.TestCase):
    """豁免机制本身会成为下一个绕过点(Design Doc §6)。

    ## 集合冻结冻的是**形状**,不是语义 —— 已被四条实测证伪

    `test_cli_option_set_is_frozen` 收的是 `a.option_strings` 的并集,也就是
    「长/短选项名的集合」。它**不是注册表**,更不是「豁免语义」。T8b 的复验者
    用四种**各自一行**的改法做出真绕过(同一份输入 rc 1→0、`CHECK FAILED (3)`
    → `CHECK PASSED`),而全量每次 `Ran 674 / OK / rc=0`、该断言**全程绿**:

    1. **位置参数** `ap.add_argument("tolerant", nargs="?")` —— 货真价实**已
       注册**的 action(`('tolerant', [])` 在 `_actions` 里看得见),只是
       `option_strings` 为空,集合收不到它。
    2. **复用既有参数的魔法值** `args.snapshot == 'legacy'` —— 注册表**零改动**
       (weekly 模式下那个位置参数本来就不读)。
    3. **给 `--mode` 加一个 choices `"lenient"`** —— `option_strings` 逐字不变。
    4. **`parse_known_args()` + `if '--tolerant' in _rest`** —— **零注册**,而
       `--tolerant` 字面可用,和守卫想挡的那个开关同名。

    所以集合冻结在这里**降级为辅助**:它只钉住"选项名的形状",挡住最笨的那种
    加法(直接 `add_argument("--tolerant", ...)`,含 `help=argparse.SUPPRESS`
    的隐藏写法 —— 扫 `--help` 文本挡不住,扫 `option_strings` 挡得住)。

    ## 主守卫是行为级的,但它**不是全称命题**

    `test_listed_exemption_tokens_cannot_make_verdict_codes_disappear`
    的名字曾经写成「no argv can …」。那是**全称命题,而实测只做到了四条
    argv**(T8b 复验),三个有界缺口逐条被真绕过打穿:

    - **V13**:枚举只在 base argv 上**追加** token,从不变动既有选项 ——
      于是 `if args.strict_brief: violations = [x for x in violations
      if not x.startswith("VERDICT_")]` 这一行就是豁免扳机:真 CLI 由
      `CHECK FAILED (5)` rc=1 变 `CHECK PASSED` rc=0,而全量全绿。
      **skills/fx-daily-report/SKILL.md 的生产调用每次都带 `--strict-brief`**,
      这条绕过**精确地只在真实运行的那条命令行上生效**。
      现在 base 覆盖两条 SKILL 里生产命令行的完整形状,并对每个既有开关的
      取反组合各跑一遍。
    - **V9**:两份输入产出的违规**全是 `VERDICT_NOT_QUOTED`**,按码族滤掉
      `ABSENT/EMPTY/MALFORMED`(最该响亮失败的"脚本缺陷"族)时 rc 仍是 1、
      `VERDICT_` 仍在 stdout,**这条 argv 守卫**绿。现在输入按码枚举
      (8 个码都要触发到,并由 `seen` 集合闭合),判据升级为
      **基线上出现过的那一组码一个都不许少**。
      **数字更正(T8d,第三次同型)**:T8c 报告那一格写「修前:旧测试
      **rc=0 OK**」,那是**只跑守卫类**的结果,不是全量。T8d 在父提交
      `3142839` 上逐字复跑(`git archive 3142839` 展开的干净副本,
      本机无 `FRED_API_KEY`):变异体落点是该树 `scripts/check_report.py`
      第 413-414 行 `# 降级声明先于结论打印` / `for note in notes:` **之前**
      插入三行
      `violations = [x for x in violations if not x.startswith((
       "VERDICT_ABSENT", "VERDICT_EMPTY", "VERDICT_MALFORMED"))]` ——
      * 全量:`Ran 680 tests / FAILED (failures=2) / rc=1`,红的两条是
        `CheckerPrintsItsOwnDispositionTest.test_every_verdict_violation_line_carries_a_disposition`
        与 `…test_script_defect_codes_carry_the_other_disposition`,
        **不是**那条 argv 守卫;
      * 单跑 `NoLegacyExemptionSwitchTest`:`Ran 2 tests / OK / rc=0`。
      同树基线为 `Ran 680 tests / OK / rc=0`。
      也就是说 V9 这条缺口**是真的**(守卫本身确实收不到),但「全量全绿」
      的说法当时就跑不出来 —— 别的测试碰巧红了。
    - **V14**:守卫是进程内 `check_report.main(argv)`,`sys.argv` 对它天然
      不可见 —— 把扳机从 `_rest` 改成 `sys.argv` 就逃掉了。现在
      `test_production_shapes_stay_red_in_a_real_subprocess` 对生产形状跑
      **真子进程**,让 `sys.argv` 与进程环境真正参与。

    ## T8d 两条:基线自证 + 「已注册但当前 mode 不读」的选项

    - **自证基线**:`base_codes` 此前**由被测(可能已变异)的校验器自己
      算出来**。某条 base 整族少一个码时,它还剩 4 个码 → `assertTrue`
      绿、rc 仍 1、逐变体 `missing = base_codes - codes(out)` **恒空**;
      末尾闭合 `seen == want` 也绿,因为**别的 base 还在出**那个码。
      现在 `_bases()` 的第 4 位是**写死的期望码集合字面量**,进变体循环
      前先 `assertEqual`。实测见 `DAILY_BASE_CODES` 上方。
    - **不读的既有选项**:`_variants` 此前只会**追加**裸 token / `--<token>` /
      `--<token> 1` / `--mode <token>` / 魔法位置参数五种形状,**从不打开
      一个已注册的既有选项**;而 daily 分支从不读 `--digest`/`--daily`、
      weekly 分支从不读 `--brief`,三个各自一行的变异全部存活。
      第六族补上,实测见 `UNREAD_OPTION_VALUE` 上方。

    ## T8e 一条:第六族的成员表**当时是手写的,而它当场就是错的**

    T8d 给第六族喂的是手写清单 `w_unread = ("--brief",)` —— 可 weekly 分支
    **既不读 `args.brief` 也不读 `args.strict_brief`**,清单在落地的同一棵树上
    就漏了一个,于是 `--strict-brief` 从来没有任何变体试过。两名独立复验者
    各自撞上同一条(实测记在 `test_unread_option_derivation_matches_literal`)。
    **手写表本身就是本 change 要消灭的那种「第二份拷贝」**:它与源码之间
    没有任何机械联系,漏一个不会有人知道。所以修的不是「把 `--strict-brief`
    补进清单」,而是**换成机械推导**:`build_parser()` 注册的选项 dest,
    减去 `main()` 里该 mode 分支实际读到的 `args.*`(AST 走 `main()`,
    按 mode 分支收 `Attribute(value=Name('args'))`),差集就是这一族的输入。
    推导单独用会犯 T8d 刚治过的「自证」病(源码被变异,推导跟着漂),
    故 `_bases()` 喂的是**推导 ∪ 字面量**,并由那条哨兵要求两者相等。

    ## T8f 一条:第六族只开**单个**不读选项,**合取**扳机整类没人试

    T8d/T8e 两版的第六族**每个变体只打开一个**不读选项,于是「两个不读选项的
    **合取**」这一形状从来没被任何变体喂到 —— 而它同样只要两行:
    `if getattr(args, "digest", None) and getattr(args, "daily", None):
    violations = [x for x in violations if not x.startswith("VERDICT_")]`
    在 `20aee7a` 上是**完整存活体**(全量 `Ran 687 / OK / rc=0`,哨兵与主守卫
    一起绿)。写成朴素属性形式 `if args.digest and args.daily:` 时哨兵会响
    (合取把两个 dest 都变成"读过的",推导塌空),但**主守卫仍然全绿**
    (`failures=1`)—— 只有哨兵红不算封住,换个 `getattr` 就连哨兵也没了。

    **这一条与前几轮的「无界绕过」不同:它可穷尽。** 不读选项每 mode 只有
    2 个(`daily = {--digest, --daily}`、`weekly = {--brief, --strict-brief}`),
    非空子集共 3 个,所以修法是**枚举幂集**而不是再补一条特例:第六族改为
    「打开不读选项的**每个非空子集**」,带值的仍试真路径值 + 每个豁免味魔法值,
    `store_true` 裸开。逐条实测(含四条单选项旧变异的回归)记在 `_variants`。

    代价(同机对拍,只换 `tests/test_check_report.py` 一个文件):变体总数
    **1414 → 1612**(+198,+14.0%);主守卫单跑 **0.94s → 1.08s**(各 3 次取
    中位,+15%,与变体增幅同量级);本类 4 条 3.11s → 3.26s(该类耗时被
    `test_production_shapes_stay_red_in_a_real_subprocess` 的 42 次真子进程
    主导,幂集只加进程内变体);全量 687 条 17.89s → 18.05s(<1%,已在噪声内)。

    仍然**不是**"没有任何 argv":守的是 `EXEMPTION_TOKENS` × 句法位置 ×
    既有开关取反 × 当前 mode 不读的既有选项的**每个非空子集**,加上生产形状的
    子进程复核。词表之外的 token、**不读选项与其它输入(如 `--mode` 魔法值、
    新增位置参数)交叉构成的合取**、以及**测试进程观察不到的通道**
    (`sys.modules` 探测、未提交的 `tests/` 改动等)不在覆盖内 —— 后两者已由
    协调者与 A 类同列为无界边界,不再为它加哨兵。
    """

    def test_cli_option_set_is_frozen(self):
        """**辅助**断言,不是主守卫 —— 冻的是选项名集合,不是豁免语义。
        位置参数(option_strings 为空)与 parse_known_args(零注册)都能绕过它,
        见类注释的四条实测。**第五条(T8d)**:根本不必新增选项 —— 拿
        「当前 mode 不读的那几个既有选项」当扳机,这里逐字不变、全绿,
        而真 CLI rc 1→0(见 `UNREAD_OPTION_VALUE`)。"""
        opts = {s for a in check_report.build_parser()._actions
                for s in a.option_strings}
        self.assertEqual(opts, {"-h", "--help", "--brief", "--mode",
                                "--strict-brief", "--digest", "--daily"})

    # 「当前 mode 不读的既有选项」的**期望字面量**。它**不驱动任何变体** ——
    # 驱动第六族的是 `unread_option_specs()` 的推导结果(见该函数)。
    # 这里只是**防退化哨兵**:AST 走空、`main()` 被重构成推导认不出的形状时,
    # 推导会静默塌成空集,第六族随之整族消失 —— 那正是 T8e 要消灭的那个病
    # (静默的覆盖缺口),所以它必须响亮失败而不是悄悄不跑。
    UNREAD_OPTIONS_EXPECTED = {
        "daily": (("--digest", True), ("--daily", True)),
        "weekly": (("--brief", True), ("--strict-brief", False)),
    }

    def test_unread_option_derivation_matches_literal(self):
        """推导出的「当前 mode 不读的既有选项」必须与写死的期望逐字相等。

        **T8e 的靶心**:T8d 那版是**手写清单**(`w_unread = ("--brief",)`),
        而 weekly 分支既不读 `args.brief` **也不读 `args.strict_brief`` ——
        手写表在落地的同一棵树上就漏了一个,`--strict-brief` 因此从未被任何
        变体试过。实测(HEAD a61ee1e,修前):在 `main()` 的
        `for note in notes:` 前插一行
        `if args.mode == "weekly" and args.strict_brief: violations =
        [x for x in violations if not x.startswith("VERDICT_")]` ——
        全量 `Ran 686 / OK / rc=0`、本类单跑 rc=0(**存活**),而周报生产
        命令行(skills/fx-weekly-report/SKILL.md:126 / README.md:131 同形)
        加一个 `--strict-brief` 由 `CHECK FAILED (16)`(其中 11 行
        `VERDICT_*`)变成 `CHECK FAILED (5)`(`VERDICT_*` **0 行**)——
        整个结论句校验层无声蒸发。

        手写表就是本 change 要消灭的那种「第二份拷贝」,所以修法是
        **推导替代手写**,而不是把 `--strict-brief` 补进清单。

        **但推导单独用会犯 T8d 刚治过的那个病:期望值由被检对象自己提供。**
        推导读的是**可能已被变异的** `check_report.py` —— 攻击者只要把扳机
        写进 weekly 分支体内(`if args.strict_brief: violations = [...]`,
        插在 `violations = check_weekly(...)` 之后),该分支就「读」了
        `args.strict_brief`,于是这个选项**自己走出第六族**,主守卫从此看
        不见它。实测(HEAD a61ee1e + 本轮推导,`_bases` 只用推导时):
        全量 rc=1、本类 rc=1,但红的**只有本条哨兵**
        (`FAILED (failures=1)`),主守卫
        `test_listed_exemption_tokens_cannot_make_verdict_codes_disappear`
        **是绿的**,而生产周报命令行 `VERDICT_*` 仍从 11 行掉到 0 行。
        所以 `_bases()` 喂给第六族的是**推导 ∪ 字面量**:推导补上人漏掉的
        (T8d 那个洞),字面量钉住攻击者搬不走的(这个洞),本条哨兵要求
        两者相等 —— 一旦分歧,三个位置一起响。
        """
        for mode in sorted(self.UNREAD_OPTIONS_EXPECTED):
            self.assertEqual(
                set(unread_option_specs(mode)),
                set(self.UNREAD_OPTIONS_EXPECTED[mode]),
                "mode=%s 的「不读选项」推导结果与写死的期望不符 —— 要么 main() "
                "真的改了读法(那就改这里的字面量并说明),要么推导塌了" % mode)

    def _unread_specs(self, mode):
        """喂给 `_variants` 第六族的规格 = **推导 ∪ 字面量**。

        单用推导会被「把扳机写进分支体内」搬走(见上一条哨兵的实测);
        单用字面量就是 T8d 那张漏了 `--strict-brief` 的手写表。两者取并集
        时,任一侧多出来的选项都仍会被试到;干净树上两者相等,并集不带来
        任何额外变体。推导塌掉(`AssertionError`)时**不吞异常**:那是
        fail-closed,红着停比静默少跑一族好。
        """
        return tuple(set(unread_option_specs(mode))
                     | set(self.UNREAD_OPTIONS_EXPECTED[mode]))

    # 豁免味的 token。**不是穷举所有单词**,而是穷举"要加豁免开关的人会起的
    # 名字"× 它能出现的每一种句法位置(裸位置参数 / 长选项 / 长选项带值 /
    # 既有选项的魔法值)。守的是句法位置的覆盖面,不是词表的完备性。
    EXEMPTION_TOKENS = ("tolerant", "legacy", "lenient", "exempt", "relaxed",
                        "compat", "skip-verdict", "no-verdict", "force", "off")

    def _run_cli(self, argv):
        """跑 main(argv),返回 (rc, stdout)。argparse 拒绝未知参数时会
        `sys.exit(2)` —— 那是**合格的失败**(fail-closed),记为 rc=2。"""
        out, err = io.StringIO(), io.StringIO()
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                rc = check_report.main(argv)
        except SystemExit as e:
            return (e.code if isinstance(e.code, int) else 2), out.getvalue()
        return rc, out.getvalue()

    CHECK_PY = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "scripts", "check_report.py")

    def _run_subprocess(self, argv):
        """真子进程跑 CLI。进程内 `main(argv)` 看不见 `sys.argv`,把豁免扳机
        从 `parse_known_args` 的 `_rest` 改写成 `sys.argv` 就整类逃掉(V14)。
        只有真子进程能让 `sys.argv` 与进程环境参与判定。"""
        r = subprocess.run([sys.executable, self.CHECK_PY] + list(argv),
                           capture_output=True, text=True,
                           env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        return r.returncode, r.stdout

    @staticmethod
    def _codes(out):
        """stdout 里出现过的 `VERDICT_*` 码集合(违规行与降级声明行同收)。"""
        found = set()
        for raw in out.splitlines():
            m = re.match(r"(VERDICT_[A-Z_]+)[::]", raw.lstrip(" -"))
            if m:
                found.add(m.group(1))
        return found

    def _assert_no_code_lost(self, argv, base_rc, base_codes, run=None):
        """判据(V9 后升级):**基线上出现过的那一组码,一个都不许少**。

        旧判据是"stdout 里还有 `VERDICT_`":两份输入的违规恰好全是
        `VERDICT_NOT_QUOTED`,于是"按码族滤掉 ABSENT/EMPTY/MALFORMED"
        (最该响亮失败的脚本缺陷族)时 rc 仍 1、`VERDICT_` 仍在,断言绿。
        rc=2 仍算合格 —— argparse 拒收未知参数就是 fail-closed。
        """
        rc, out = (run or self._run_cli)(argv)
        if rc == 2:
            return rc, out
        if base_rc:
            self.assertNotEqual(
                rc, 0,
                "argv=%r 让一份必然违规的输入通过了(rc %d→0)\n%s"
                % (argv, base_rc, out))
        missing = base_codes - self._codes(out)
        self.assertFalse(
            missing,
            "argv=%r 让这些码整类消失了:%s\n%s"
            % (argv, sorted(missing), out))
        return rc, out

    # 「当前 mode **不读**的已注册选项」是**推导出来的**(见
    # `unread_option_specs`),不再有手写清单。这张表只回答另一个问题:
    # 带值的那几个选项,拿哪个既有文件当值 —— 它是 fixture 映射,不是成员表,
    # 缺项会在 `_variants` 里响亮 fail(不会让某个选项被静默跳过)。
    #
    # 这些选项是**免费的隐藏豁免扳机**:注册表逐字不动、`option_strings` 不变,
    # `test_cli_option_set_is_frozen` 全绿,而各自一行的
    # `if args.mode == "daily" and args.digest:` /
    # `if args.strict_brief and args.daily:` /
    # `if args.mode == "weekly" and args.brief:` 就能滤掉整类 VERDICT_*。
    # 实测(T8d,acdd7de 工作树):三条全量都是 `Ran 686 / OK / rc=0`,
    # 而生产命令行加 `--digest off` / `--daily off` / `--brief off` 分别
    # rc 1→0(`CHECK FAILED (5)`→`CHECK PASSED`、weekly 侧 `(4)`→PASSED)。
    UNREAD_OPTION_VALUE = {"--digest": "w_multi", "--daily": "d_report",
                           "--brief": "brief"}

    def _variants(self, base, free_positional=None, unread_options=()):
        """base 之上派生 argv。free_positional 给的是"可塞魔法值的既有位置参数"
        在 base 里的下标(weekly 模式下 snapshot 位不读,正是变体 2 的落点);
        unread_options 给的是"当前 mode 不读的既有选项"规格
        `((选项名, 是否带值), ...)`,**由 `unread_option_specs()` 从源码推出**。

        **裸 token 必须试三种位置**,这是实测出来的:只把它追加在**末尾**时,
        argparse 已经在前面那段位置参数区里把 `nargs="?"` 的新位置参数配成
        None,末尾这个 token 变成 "unrecognized arguments" → rc=2 → 变体 1
        (`ap.add_argument("tolerant", nargs="?")`)**照样存活**(实测:新断言
        rc=0 PASS,而同一份输入的真 CLI 是 `CHECK PASSED`)。塞进位置参数区、
        或用 `--` 强制当位置参数,才能真正喂到那个 action。

        **第六族(T8d 新增,T8e 改为推导驱动,T8f 改为幂集)必须打开已注册的
        既有选项**。前五族只会 *追加* 新 token,从不动既有选项 —— 于是"当前
        mode 不读的那几个选项"整类没人试过,而它们是零注册成本的豁免扳机。
        带值的选项试两次:带**真路径值**一次(扳机只要 truthy 就够),带
        **豁免味魔法值**一次;`store_true` 那种不带值的,裸开一次即可。

        **T8f:打开的是「每个非空子集」,不是「每个单个选项」。** T8d/T8e 两版
        每个变体只开**一个**不读选项,于是**两个选项的合取**从来没被试过,而
        合取同样是两行就能写成的扳机。

        实测口径:变异体插在 `violations = check_daily(...)`(weekly 侧为
        `check_weekly(...)`)**之后**,两行 `if <扳机>:` +
        `violations = [x for x in violations if not x.startswith("VERDICT_")]`;
        全量 = `python3 -m unittest discover -s tests -t .`,rc 取 `echo $?`;
        修前树 = `20aee7a`,修后树 = 本提交;两边都**无** `FRED_API_KEY`
        (导出它会另外带来 11 条与本族无关的失败)。两边全量都是 `Ran 687`。

        | 变异体(@mode) | 修前 | 修后 |
        |---|---|---|
        | `args.digest and args.daily` @daily | `failures=1`,**只有哨兵**红 | `failures=100` = 99 主守卫 + 1 哨兵 |
        | `getattr` 版合取 @daily | **`OK` rc=0,完整存活** | `failures=99`,**全是主守卫**(哨兵绿) |
        | `args.brief and args.strict_brief` @weekly | `failures=1`,**只有哨兵**红 | `failures=78` = 77 主守卫 + 1 哨兵 |
        | `getattr` 版合取 @weekly | 未单测(同型) | `failures=77`,**全是主守卫**(哨兵绿) |

        修前那两条"只有哨兵红"不算封住:哨兵响是因为合取把两个 dest 都变成了
        "读过的"、推导塌空,而**主守卫全绿**;攻击者改用 `getattr` 绕开 AST
        推导后,哨兵也不响了 —— 那才是完整存活体。对照组证明存活原因是
        **合取**而非 `getattr`:同样 `getattr` 但只读**一个**选项
        (`if getattr(args, "digest", None):`)修前就已经是
        `failures=99` 全主守卫、哨兵绿。

        四条单选项旧变异(`--digest`/`--daily` @daily、`--brief`/`--strict-brief`
        @weekly)改后**仍全红且全在主守卫**:`failures=` 199 / 199 / 155 / 85
        (各含 1 条哨兵)。

        **这一条与前几轮的「无界绕过」不同:它可穷尽。** 推导出的不读选项集合
        是 `daily = {--digest, --daily}`、`weekly = {--brief, --strict-brief}`,
        每 mode 只有 2 个,非空子集共 3 个 —— 枚举幂集即**完备**(对"只由不读
        选项构成的合取扳机"而言),不是打地鼠。选项数若涨到 n,这一族会按
        2ⁿ−1 涨;n 现在是 2,代价见 `_nonempty_subsets`。
        """
        head = next((i for i, t in enumerate(base) if t.startswith("-")),
                    len(base))
        need = [o for o, takes_value in unread_options
                if takes_value and o not in self.UNREAD_OPTION_VALUE]
        if need:
            self.fail("推导出的带值「不读选项」没有 fixture 值可喂:%s —— "
                      "在 UNREAD_OPTION_VALUE 里补一个既有文件,别让它被跳过"
                      % ", ".join(need))
        combos = self._nonempty_subsets(unread_options)
        out = [list(base)]
        for combo in combos:                                  # 第六族:真值/裸开
            out.append(list(base) + self._open_unread(combo))
        for tok in self.EXEMPTION_TOKENS:
            out.append(list(base) + [tok])                    # 裸 token 在尾部
            out.append(base[:head] + [tok] + base[head:])     # 裸 token 在位置参数区
            out.append(list(base) + ["--", tok])              # `--` 后强制为位置参数
            out.append(list(base) + ["--" + tok])             # 长选项(store_true)
            out.append(list(base) + ["--" + tok, "1"])        # 长选项带值
            if "--mode" in base:                              # 既有 choices 加值
                i = base.index("--mode") + 1
                mode = list(base)
                mode[i] = tok
                out.append(mode)
            if free_positional is not None:                   # 既有位置参数魔法值
                magic = list(base)
                magic[free_positional] = tok
                out.append(magic)
            for combo in combos:                              # 第六族:魔法值
                # 全是 store_true 的子集喂不进 tok,魔法值形状与上面的裸开
                # 逐字相同 —— 跳过它只是去重,不减覆盖。
                if any(takes_value for _, takes_value in combo):
                    out.append(list(base) + self._open_unread(combo, tok))
        return out

    @staticmethod
    def _nonempty_subsets(specs):
        """`((选项名, 是否带值), ...)` 的**所有非空子集**,顺序稳定(先按元素
        个数、再按选项名)—— 失败消息里的 argv 才不会每次跑都换个样子。

        幂集在这里是**负担得起的完备**:n=2 时非空子集 3 个,比"逐个单开"只多
        1 条 base 变体 + 每个 token 多 1 条魔法值变体。真要涨到 n=6 以上再谈
        剪枝(那时也该先问为什么有那么多注册了却没人读的选项)。
        """
        specs = sorted(set(specs))
        return [combo for r in range(1, len(specs) + 1)
                for combo in itertools.combinations(specs, r)]

    def _open_unread(self, combo, tok=None):
        """把一组「不读选项」拼成 argv 尾巴:带值的喂 `tok`(None 表示喂
        fixture 里的**真路径**),`store_true` 的裸开。"""
        tail = []
        for opt, takes_value in combo:
            if takes_value:
                tail += [opt, tok if tok is not None
                         else self.paths[self.UNREAD_OPTION_VALUE[opt]]]
            else:
                tail.append(opt)
        return tail

    @classmethod
    def setUpClass(cls):
        """按**码**准备输入(V9):8 个 `VERDICT_*` 码都要有基线触发得到。

        日报侧一份快照就凑齐 5 个码 —— 五个币种各带一种缺陷:
        USD 有句子但报告没抄(NOT_QUOTED)、EUR 条目在但字段缺(ABSENT)、
        PHP 非字符串(MALFORMED)、THB 纯空白(EMPTY)、BRL 条目整个缺
        (ENTRY_MISSING)。
        """
        cls._tmp = tempfile.TemporaryDirectory()
        t = cls._tmp.name
        snap = dict(SNAP)
        snap["derived"] = {
            "schema_version": 2, "rates": {}, "real_rate": {},
            "events": {"USD": {"events_verdict": DAILY_VERDICT},
                       "EUR": {},
                       "PHP": {"events_verdict": 7},
                       "THB": {"events_verdict": "   "}},
        }
        container_bad = dict(SNAP)
        container_bad["derived"] = {"schema_version": 2, "events": 7}
        wobj = json.loads(DIGEST)
        wobj["rates"]["PHP"]["fixings_verdict"] = 7            # MALFORMED
        wobj["events"]["PHP"]["articles_verdict"] = "   "      # EMPTY
        del wobj["events"]["PHP"]["official_verdict"]          # ABSENT
        wobj["events"]["USD"] = {"articles_verdict": "报告里不存在的这一句",
                                 "official_verdict": OFF_PHP}  # NOT_QUOTED
        wcont = json.loads(DIGEST)
        wcont["rates"] = 7
        wcont["events"] = 7
        files = {
            "d_report": make_report(),
            "brief": BRIEF,
            "d_multi": json.dumps(snap, ensure_ascii=False),
            "d_container": json.dumps(container_bad, ensure_ascii=False),
            "d_noderived": SNAP_TEXT,
            "d_legacy": snap_with_derived(schema_version=1, verdict=None),
            "w_report": WEEKLY_OK,
            "w_multi": json.dumps(wobj, ensure_ascii=False),
            "w_container": json.dumps(wcont, ensure_ascii=False),
        }
        cls.paths = {}
        for name, text in files.items():
            ext = ".md" if name.endswith(("report", "brief")) else ".json"
            p = os.path.join(t, name + ext)
            with open(p, "w", encoding="utf-8") as f:
                f.write(text)
            cls.paths[name] = p

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def _production_daily(self):
        """SKILL 第 5 步那一行的**完整形状**,逐字同形(见
        skills/fx-daily-report/SKILL.md 的 `check_report.py … --strict-brief`)。
        `--strict-brief` 此前从不出现在任何 base argv 里 —— 那正是 V13。"""
        p = self.paths
        return [p["d_report"], p["d_multi"], "--brief", p["brief"],
                "--mode", "daily", "--strict-brief"]

    def _production_weekly(self):
        """skills/fx-weekly-report/SKILL.md 第 3 步那一行的完整形状。"""
        p = self.paths
        return [p["w_report"], "--mode", "weekly", "--digest", p["w_multi"],
                "--daily", p["d_report"], "--daily", p["d_report"]]

    # ---- 每条 base 的**期望码集合字面量**(T8d)----
    # 此前 `base_codes` 是**用被测(可能已变异)的校验器自己算出来的**,
    # 于是"某条 base 整族少一个码"这一形态对整个循环完全不可见:该 base
    # 还剩 4 个码 → `assertTrue(base_codes)` 绿、rc 仍 1、逐变体
    # `missing = base_codes - codes(out)` **恒空**;末尾的闭合断言
    # `seen == want` 也绿,因为**别的 base 还在出**那个码。
    # 实测(T8d,acdd7de 工作树):在 main() 的 `for note in notes:` 前插一行
    # `if args.strict_brief: violations = [x for x in violations
    #  if not x.startswith("VERDICT_NOT_QUOTED")]`(注册表零改动)——
    # 全量 `Ran 686 tests / OK / rc=0`,而 skills/fx-daily-report/SKILL.md:222
    # 与 README.md:129 那条**一字未改**的生产日报命令行由 `CHECK FAILED (5)`
    # rc=1 变 `CHECK PASSED` rc=0。`VERDICT_NOT_QUOTED` 是整个 change 的主码。
    # **这与电池「登记 m = len(M)」是同一个病:期望值由被检对象自己提供。**
    # 解药是字面量:8 条 daily base 的码集合完全相同(5 个)、6 条 weekly
    # 完全相同(4 个),实测可写死;码集合变了就必须显式改这里,会进 diff。
    DAILY_BASE_CODES = frozenset({
        "VERDICT_NOT_QUOTED", "VERDICT_ABSENT", "VERDICT_MALFORMED",
        "VERDICT_EMPTY", "VERDICT_ENTRY_MISSING"})
    WEEKLY_BASE_CODES = frozenset({
        "VERDICT_NOT_QUOTED", "VERDICT_ABSENT", "VERDICT_MALFORMED",
        "VERDICT_EMPTY"})

    def _bases(self):
        """(标签, base argv, 可塞魔法值的位置参数下标, **期望码集合**,
        当前 mode 不读的既有选项)。

        前两组是**生产命令行 × 每个既有开关的取反**:日报三个开关
        (`--mode` 显式/缺省、`--brief` 有/无、`--strict-brief` 有/无)共 8 条;
        周报是 `--daily` 出现 2/1/0 次 × 快照位有/无共 6 条。
        `--digest` 不参与取反:不给它就是"不做结论句校验",那是设计内的
        行为(由 test_without_digest_object_no_verdict_check 单独钉),
        不是豁免。后四条把上面两组触发不到的码补齐。

        第 4 位是**自证基线的解药**(见 DAILY_BASE_CODES 上方的实测);
        第 5 位喂给 `_variants` 的第六族,**由 `_unread_specs()` 给出:
        源码推导 ∪ 写死的字面量**(T8e)。T8d 那版是纯手写的
        `w_unread = ("--brief",)`,在落地的同一棵树上就漏了 `--strict-brief`
        —— 手写清单与源码之间没有机械联系,漏一个没人会知道;而纯推导又能
        被「把扳机写进分支体内」搬走(两条实测都记在
        `test_unread_option_derivation_matches_literal` 里)。
        """
        p = self.paths
        d_unread = self._unread_specs("daily")
        w_unread = self._unread_specs("weekly")
        out = []
        for use_mode in (True, False):
            for use_brief in (True, False):
                for use_strict in (True, False):
                    argv = [p["d_report"], p["d_multi"]]
                    if use_brief:
                        argv += ["--brief", p["brief"]]
                    if use_mode:
                        argv += ["--mode", "daily"]
                    if use_strict:
                        argv += ["--strict-brief"]
                    out.append(("daily mode=%d brief=%d strict=%d"
                                % (use_mode, use_brief, use_strict), argv, None,
                                self.DAILY_BASE_CODES, d_unread))
        # weekly 侧此前还有一维 `snap_slot`(往不读的位置参数里塞一份快照),
        # 并把 `free_positional=1` 喂给「既有位置参数魔法值」那一族。
        # **那一维已随 weekly 拒收位置参数一起消失**:`--mode weekly` 且位置
        # 参数非空现在是 rc=2,base 自己就跑不出任何码
        # (实测:加完拒收后全量 `FAILED (failures=1)`,红的正是本条,消息为
        # 「base「weekly daily=2 snapslot=1」的基线码集合与写死的期望不符 ——
        # 少了 ['VERDICT_ABSENT','VERDICT_EMPTY','VERDICT_MALFORMED',
        # 'VERDICT_NOT_QUOTED']」)。
        # **这不是放宽断言,是那条 argv 已经不再是合法输入。** 它守的东西
        # (「拿不读的位置参数当豁免扳机」,即类注释里的绕过手法 ②)现在由
        # `WeeklyRejectsPositionalSnapshotTest` 承接,并且守得更死:那里对
        # **每一个 EXEMPTION_TOKEN** 逐个塞进位置参数,要求全部 rc=2 且
        # stdout 不出现任何结论行 —— 魔法值连被读到的机会都没有。
        for n_daily in (2, 1, 0):
            argv = [p["w_report"], "--mode", "weekly", "--digest", p["w_multi"]]
            argv += ["--daily", p["d_report"]] * n_daily
            out.append(("weekly daily=%d" % n_daily, argv, None,
                        self.WEEKLY_BASE_CODES, w_unread))
        out.append(("daily 容器坏",
                    [p["d_report"], p["d_container"], "--brief", p["brief"],
                     "--mode", "daily", "--strict-brief"], None,
                    frozenset({"VERDICT_CONTAINER_MALFORMED"}), d_unread))
        out.append(("weekly 容器坏",
                    [p["w_report"], "--mode", "weekly", "--digest",
                     p["w_container"], "--daily", p["d_report"]], None,
                    frozenset({"VERDICT_CONTAINER_MALFORMED"}), w_unread))
        out.append(("daily 无 derived(只出降级声明)",
                    [p["d_report"], p["d_noderived"], "--brief", p["brief"],
                     "--mode", "daily", "--strict-brief"], None,
                    frozenset({"VERDICT_SKIPPED_NO_DERIVED"}), d_unread))
        out.append(("daily schema 过旧(只出降级声明)",
                    [p["d_report"], p["d_legacy"], "--brief", p["brief"],
                     "--mode", "daily", "--strict-brief"], None,
                    frozenset({"VERDICT_SKIPPED_LEGACY"}), d_unread))
        return out

    def test_listed_exemption_tokens_cannot_make_verdict_codes_disappear(self):
        """**主守卫**,名字按实测口径:守的是 `EXEMPTION_TOKENS` × 句法位置 ×
        既有开关取反这一**有界**集合,不是"没有任何 argv"。

        每条 base 先自跑一遍取基线码集合,并与**写死的期望字面量**逐字比对
        (T8d:基线不能由被测二进制自己提供,否则整族少一个码时逐变体判据
        `missing = base_codes - codes(out)` 恒空 —— 见 DAILY_BASE_CODES);
        然后要求每个变体都不丢码;基线 rc 非 0 的还要求 rc 不得变 0。
        最后闭合:所有 base 的码集合并起来必须**恰好**是校验器的 8 个码 ——
        少一个就说明有一族码从来没被这轮枚举看过(V9 的根因)。
        """
        seen = set()
        for label, base, fp, expected, unread in self._bases():
            base_rc, base_out = self._run_cli(base)
            base_codes = self._codes(base_out)
            self.assertEqual(
                base_codes, set(expected),
                "base「%s」的基线码集合与写死的期望不符 —— 基线不许由被测"
                "校验器自己提供:少了 %s,多了 %s\n%s"
                % (label, sorted(set(expected) - base_codes),
                   sorted(base_codes - set(expected)), base_out))
            seen |= base_codes
            for argv in self._variants(base, free_positional=fp,
                                       unread_options=unread):
                # subTest 标签带**整条 argv**(含位置参数):只打 argv[2:] 时,
                # "把魔法值塞进既有位置参数"那一类变体的失败消息里看不出改了什么
                with self.subTest(base=label, argv=" ".join(
                        os.path.basename(a) for a in argv)):
                    self._assert_no_code_lost(argv, base_rc, base_codes)
        want = set(VERDICT_VIOLATION_DISPOSITION) | set(VERDICT_NOTE_CODES)
        self.assertEqual(seen, want, "有码从未被这轮 argv 枚举触发过")

    def test_production_shapes_stay_red_in_a_real_subprocess(self):
        """V14:进程内 `main(argv)` 对 `sys.argv` 天然免疫,把豁免扳机写成
        `if "--tolerant" in sys.argv` 就整类逃掉。这里对**两条生产命令行**
        跑真子进程,基线之外再逐个 token 试"裸追加"与"长选项"两种形状。

        子进程数有意压在 ~42 次(每次约 50ms):句法位置的完整覆盖由上面
        那条进程内的枚举承担,这一条只负责把 `sys.argv` 与进程环境接进来。

        **T8d 两处补强**:
        - 基线码集合与**写死的字面量**比,不再由被测二进制自证;
        - 每一条输出都过 `assert_own_disposition` —— 处置表此前在生产
          argv 形状与真子进程下**完全无人看守**(见该函数的实测)。
        """
        for label, base, expected in (
                ("daily 生产命令行", self._production_daily(),
                 self.DAILY_BASE_CODES),
                ("weekly 生产命令行", self._production_weekly(),
                 self.WEEKLY_BASE_CODES)):
            base_rc, base_out = self._run_subprocess(base)
            base_codes = self._codes(base_out)
            self.assertEqual(base_rc, 1, (label, base_out))
            self.assertEqual(base_codes, set(expected),
                             "%s 的基线码集合与写死的期望不符\n%s"
                             % (label, base_out))
            # 生产形状下每个触发到的违规码都必须带**它自己那一条**处置
            self.assertEqual(assert_own_disposition(self, base_out, label),
                             set(expected) - set(VERDICT_NOTE_CODES),
                             "%s 有码没被处置断言看过\n%s" % (label, base_out))
            argvs = [base]
            for tok in self.EXEMPTION_TOKENS:
                argvs.append(list(base) + [tok])
                argvs.append(list(base) + ["--" + tok])
            for argv in argvs:
                with self.subTest(base=label, argv=" ".join(
                        os.path.basename(a) for a in argv)):
                    rc, out = self._assert_no_code_lost(
                        argv, base_rc, base_codes, run=self._run_subprocess)
                    assert_own_disposition(self, out, "%s %s" % (label, argv[-1]))


DAILY_VERDICT = "当日采到 11 条(前一日取自 gdelt 通道,口径不可比,不给变化量)"


def snap_with_derived(schema_version=2, verdict=DAILY_VERDICT,
                      currencies=tuple(check_report.CURRENCIES)):
    """在既有 SNAP 上挂一个 derived 节。SNAP 本身不变(浅拷贝后加键)。

    currencies 默认给全五个币种:derive 按 rates ∪ events.KEYWORDS 逐币种
    填充(实测 data/2026-08-12.json 派生出的 events 恰好五个键),schema 2
    的真实快照没有「只有一个币种条目」这种形态,而 T6b 的第 ② 档已把它判为
    VERDICT_ENTRY_MISSING。默认值给少了,此后每个用它的新用例都会白拿四条
    无关违规 —— 要测部分容器请显式传 currencies。
    """
    snap = dict(SNAP)
    snap["derived"] = {
        "schema_version": schema_version,
        "rates": {}, "real_rate": {},
        "events": {c: ({} if verdict is None else {"events_verdict": verdict})
                   for c in currencies},
    }
    return json.dumps(snap, ensure_ascii=False)


def report_quoting(sentence, heading="美元(USD)", **kw):
    """把结论句原样塞进某币种节 —— 前后可以有自己的叙述,句子本身不动。"""
    r = make_report(**kw)
    return r.replace("## %s\n" % heading,
                     "## %s\n事件方面,%s。\n" % (heading, sentence))


class DailyVerdictQuotingTest(unittest.TestCase):
    """日报侧结论句(delta spec:结论句被改动一个字 / 结论句整句缺失 /
    结论句为空串 / 存量快照无结论句字段 / 新 schema 快照漏写结论句 /
    报告未覆盖某币种)。"""

    def test_quoted_sentence_passes(self):
        v = check_report.check_daily(report_quoting(DAILY_VERDICT),
                                     snap_with_derived(), BRIEF)
        self.assertEqual(v, [])

    def test_one_character_changed_is_caught(self):
        bad = report_quoting(DAILY_VERDICT.replace("11", "12"))
        v = check_report.check_daily(bad, snap_with_derived(), BRIEF)
        self.assertTrue(any("VERDICT_NOT_QUOTED" in x and "USD" in x for x in v), v)

    def test_whole_sentence_missing_is_caught(self):
        """数字词袋放行的正是这一形态:11 与 gdelt 都在快照里出现过。"""
        v = check_report.check_daily(make_report(), snap_with_derived(), BRIEF)
        self.assertTrue(any("VERDICT_NOT_QUOTED" in x for x in v), v)

    def test_empty_verdict_is_a_violation(self):
        v = check_report.check_daily(make_report(),
                                     snap_with_derived(verdict="  "), BRIEF)
        self.assertTrue(any("VERDICT_EMPTY" in x for x in v), v)

    def test_new_schema_missing_field_is_absent(self):
        """新 schema 却漏写字段 = 脚本缺陷,必须响亮。"""
        v = check_report.check_daily(make_report(),
                                     snap_with_derived(verdict=None), BRIEF)
        self.assertTrue(any("VERDICT_ABSENT" in x and "events_verdict" in x
                            for x in v), v)

    def test_legacy_schema_is_skipped_not_passed(self):
        """存量快照 derived.schema_version=1:跳过,不判违规,但必须计数。"""
        notes = []
        v = check_report.check_daily(
            make_report(),
            snap_with_derived(schema_version=1, verdict=None,
                              currencies=("USD",)),
            BRIEF, notes=notes)
        self.assertFalse([x for x in v if "VERDICT" in x], v)
        self.assertEqual(len(notes), 1)
        self.assertIn("VERDICT_SKIPPED_LEGACY", notes[0])
        self.assertIn("1/5 个覆盖币种", notes[0])

    def test_legacy_count_covers_every_currency(self):
        notes = []
        check_report.check_daily(
            make_report(),
            snap_with_derived(schema_version=1, verdict=None,
                              currencies=check_report.CURRENCIES),
            BRIEF, notes=notes)
        self.assertIn("5/5 个覆盖币种", notes[0])

    def test_legacy_notice_shows_the_offending_type(self):
        """schema_version 是字符串 "2" 时,%s 会印成「schema 过旧
        (derived.schema_version=2)」—— 而闸门常量 DERIVED_VERDICT_SCHEMA
        恰好就是 2,读者只会断定校验器坏了,而不是快照类型写错了。
        只有 str 能区分 %r 与 %s:2.0 / None / [] 两种写法输出一致,
        放进循环即成恒真用例(见 I5 的教训)。"""
        snap = dict(SNAP)
        snap["derived"] = {"schema_version": "2", "rates": {}, "real_rate": {},
                           "events": {c: {} for c in check_report.CURRENCIES}}
        notes = []
        check_report.check_daily(make_report(),
                                 json.dumps(snap, ensure_ascii=False),
                                 BRIEF, notes=notes)
        self.assertIn("derived.schema_version='2'", notes[0])

    def test_missing_schema_version_is_treated_as_legacy(self):
        snap = dict(SNAP)
        snap["derived"] = {"rates": {}, "real_rate": {}, "events": {"USD": {}}}
        notes = []
        v = check_report.check_daily(make_report(),
                                     json.dumps(snap, ensure_ascii=False),
                                     BRIEF, notes=notes)
        self.assertFalse([x for x in v if "VERDICT" in x], v)
        self.assertEqual(len(notes), 1)

    def test_bool_schema_version_is_not_a_number(self):
        """把闸门压到 1 才能让 bool 门真正承重:True >= 1 会误判为新 schema。"""
        snap = dict(SNAP)
        snap["derived"] = {"schema_version": True, "events": {"USD": {}}}
        notes = []
        with mock.patch.object(check_report, "DERIVED_VERDICT_SCHEMA", 1):
            v = check_report.check_daily(make_report(),
                                         json.dumps(snap, ensure_ascii=False),
                                         BRIEF, notes=notes)
        self.assertFalse([x for x in v if "VERDICT" in x], v)
        self.assertEqual(len(notes), 1)

    def test_legacy_snapshot_with_a_sentence_is_still_checked(self):
        """闸门只放行「缺字段」,不放行「字段在但引错了」。"""
        v = check_report.check_daily(make_report(),
                                     snap_with_derived(schema_version=1), BRIEF)
        self.assertTrue(any("VERDICT_NOT_QUOTED" in x for x in v), v)

    def test_missing_section_does_not_double_report(self):
        """让位 ①:缺币种节只报 SECTION_MISSING 一条。"""
        shared = "四个覆盖币种共用的结论句,逐字出现在报告里"
        report = report_quoting(shared, missing="THB")
        # 让位机制是不报 VERDICT 的唯一原因 —— 报告本就不含结论句时,
        # 下面的 assertFalse 会因为「本来就引不到」而恒真
        self.assertNotIn(DAILY_VERDICT, report)
        # 只有未覆盖的 THB 带一条报告里没有的结论句:让位失效时它立刻变成
        # VERDICT_NOT_QUOTED。其余四个币种条目齐全且被逐字引用 —— 少给条目
        # 会撞上第 ② 档的 VERDICT_ENTRY_MISSING,把让位这条断言淹掉
        events = {c: {"events_verdict": shared} for c in check_report.CURRENCIES}
        events["THB"] = {"events_verdict": DAILY_VERDICT}
        snap = dict(SNAP)
        snap["derived"] = {"schema_version": 2, "rates": {}, "real_rate": {},
                           "events": events}
        v = check_report.check_daily(report, json.dumps(snap, ensure_ascii=False),
                                     BRIEF)
        self.assertTrue(any("SECTION_MISSING" in x and "THB" in x for x in v), v)
        self.assertFalse([x for x in v if "VERDICT" in x], v)

    def test_derived_not_a_dict_does_not_crash(self):
        for bad in ("oops", [1], 7, None):
            with self.subTest(bad=bad):
                snap = dict(SNAP)
                snap["derived"] = bad
                v = check_report.check_daily(make_report(),
                                             json.dumps(snap, ensure_ascii=False),
                                             BRIEF)
                self.assertFalse([x for x in v if "VERDICT" in x], (bad, v))


class DailySkipNoticeIsPrintedTest(unittest.TestCase):
    """「跳过」与「通过」在输出上必须可区分 —— 这正是本 change 要解决的
    同型问题,所以跳过声明本身必须有测试。"""

    def _write(self, tmp, report_text, snap_text):
        rp = os.path.join(tmp, "r.md")
        sp = os.path.join(tmp, "s.json")
        for path, text in ((rp, report_text), (sp, snap_text)):
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
        return rp, sp

    def test_legacy_notice_printed_alongside_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            rp, sp = self._write(tmp, make_report(),
                                 snap_with_derived(schema_version=1,
                                                   verdict=None))
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = check_report.main([rp, sp])
            out = buf.getvalue()
        self.assertEqual(rc, 0)
        self.assertIn("VERDICT_SKIPPED_LEGACY", out)
        self.assertIn("CHECK PASSED", out)

    def test_no_notice_when_schema_is_current(self):
        with tempfile.TemporaryDirectory() as tmp:
            rp, sp = self._write(tmp, report_quoting(DAILY_VERDICT),
                                 snap_with_derived())
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = check_report.main([rp, sp])
            out = buf.getvalue()
        self.assertEqual(rc, 0)
        self.assertNotIn("VERDICT_SKIPPED_LEGACY", out)


class VerdictFieldSyncTest(unittest.TestCase):
    """常量元组与产出端字段名同步 —— 常量里拼错一个字母,检查会静默地
    什么都不查,而所有既有测试照样全绿(本仓库的典型失败形态)。"""

    def test_daily_field_exists_in_derive_output(self):
        for f in check_report.VERDICT_FIELD_DAILY:
            self.assertIn(f, derive.EMPTY_EVENTS_DERIVED)

    def test_weekly_fields_exist_in_digest_output(self):
        snaps = [{"date": "2026-08-10", "gaps": [],
                  "rates": {"PHP": {"primary": 60.867, "ref_date": "2026-08-10"}},
                  "events": {"PHP": {"articles": [], "official": []}}},
                 {"date": "2026-08-11", "gaps": [],
                  "rates": {"PHP": {"primary": 60.75, "ref_date": "2026-08-11"}},
                  "events": {"PHP": {"articles": [], "official": []}}}]
        d = weekly_digest.build(snaps, [], "2026-W33")[0]
        for f in check_report.VERDICT_FIELDS_EVENTS:
            self.assertIn(f, d["events"]["PHP"])
        for f in check_report.VERDICT_FIELDS_RATES:
            self.assertIn(f, d["rates"]["PHP"])

    def test_schema_gate_matches_derive_version(self):
        """闸门常量落后于 derive.SCHEMA_VERSION 时,新快照会被当成存量跳过。"""
        self.assertLessEqual(check_report.DERIVED_VERDICT_SCHEMA,
                             derive.SCHEMA_VERSION)


class DailyContainerGateTest(unittest.TestCase):
    """闸门声明「这份快照带结论句」之后,容器与条目就都不是可选的。

    check_verdicts 的 docstring 明写「没有别处兜底,调用方必须自己确认容器
    存在」—— check_weekly 照做了,check_daily 此前没有。同一份判定的两个
    调用点行为不对称,正是共享判定要防的漂移。"""

    def _run(self, events, ver=2, notes=None):
        """要断言降级声明请显式传 notes —— 不传时用例只能看见 violations,
        「零违规零声明」这一形态正是本类要防的,看不见就测不出。"""
        snap = dict(SNAP)
        snap["derived"] = {"schema_version": ver, "rates": {}, "real_rate": {},
                           "events": events}
        return check_report.check_daily(
            make_report(), json.dumps(snap, ensure_ascii=False), BRIEF,
            notes=[] if notes is None else notes)

    def test_non_dict_container_fails_loudly(self):
        for bad in ([], "x", 7):
            with self.subTest(bad=bad):
                v = self._run(bad)
                self.assertTrue(
                    any("VERDICT_CONTAINER_MALFORMED" in x for x in v),
                    (bad, v))

    def test_missing_container_key_fails_loudly(self):
        snap = dict(SNAP)
        snap["derived"] = {"schema_version": 2, "rates": {}, "real_rate": {}}
        v = check_report.check_daily(make_report(),
                                     json.dumps(snap, ensure_ascii=False), BRIEF)
        self.assertTrue(any("VERDICT_CONTAINER_MALFORMED" in x for x in v), v)

    def test_empty_container_reports_every_covered_currency(self):
        v = self._run({})
        missing = [x for x in v if "VERDICT_ENTRY_MISSING" in x]
        self.assertEqual(len(missing), len(check_report.CURRENCIES), v)

    def test_partial_container_reports_only_the_absent_ones(self):
        # 占位句必须是 make_report() 里真有的子串:写 "x" 会白拿三条无关的
        # VERDICT_NOT_QUOTED,违规集比期望集大,下面的强断言就成了摆设
        quoted = "无明确驱动"
        self.assertIn(quoted, make_report())
        v = self._run({c: {"events_verdict": quoted}
                       for c in ("USD", "EUR", "PHP")})
        names = [c for c in check_report.CURRENCIES
                 if any("VERDICT_ENTRY_MISSING" in x and c in x for x in v)]
        self.assertEqual(names, ["THB", "BRL"])
        self.assertEqual(len(v), 2, v)

    def test_currency_not_covered_is_not_required(self):
        """让位仍然成立:报告没写的币种不要求条目。"""
        snap = dict(SNAP)
        snap["derived"] = {"schema_version": 2, "rates": {}, "real_rate": {},
                           "events": {}}
        v = check_report.check_daily(make_report(missing="THB"),
                                     json.dumps(snap, ensure_ascii=False), BRIEF)
        self.assertFalse([x for x in v
                          if "VERDICT_ENTRY_MISSING" in x and "THB" in x], v)

    def test_legacy_schema_container_problems_are_still_skipped(self):
        """①② 只对声称带结论句的快照生效 —— 存量快照照旧跳过,不得变红。"""
        for bad in (None, [], {}, "x"):
            with self.subTest(events=bad):
                notes = []
                v = self._run(bad, ver=1, notes=notes)
                self.assertFalse([x for x in v if "VERDICT" in x], (bad, v))
                # 不变红不等于可以不出声 —— 一条都没查必须说出来
                self.assertEqual(len(notes), 1, (bad, notes))
                self.assertIn("VERDICT_SKIPPED_LEGACY", notes[0])

    def test_entry_present_but_not_a_dict_is_treated_as_missing(self):
        """条目在、但不是对象:check_verdicts 会静默 continue(周报侧基准
        货币在 rates 里本就没条目,那个沉默是必需的),所以只能堵在日报
        调用点。判据必须是「值为 dict 的键集」—— 用键存在性,这一形态
        原样零违规零声明地通过,与 O2 之前完全同形。"""
        for bad in (None, "oops", [], 7):
            with self.subTest(entry=bad):
                v = self._run({c: bad for c in check_report.CURRENCIES})
                missing = [x for x in v if "VERDICT_ENTRY_MISSING" in x]
                self.assertEqual(len(missing), len(check_report.CURRENCIES),
                                 (bad, v))


class DailyNoDerivedNoticeTest(unittest.TestCase):
    """第 ③ 档:快照根本没有 derived 节。

    实测 data/2026-08-07..10.json 四天都是这一形态,此前跑出来是**裸
    CHECK PASSED、零声明** —— 与「全部结论句已逐字核验通过」在输出上完全
    不可分辨,六天里占了四天。这是「跳过 vs 通过」的最后一个静默口子。"""

    def test_missing_derived_emits_a_notice_not_a_violation(self):
        notes = []
        v = check_report.check_daily(make_report(), SNAP_TEXT, BRIEF, notes=notes)
        self.assertEqual(v, [])
        self.assertEqual(len(notes), 1, notes)
        self.assertIn("VERDICT_SKIPPED_NO_DERIVED", notes[0])

    def test_null_derived_emits_the_same_notice(self):
        snap = dict(SNAP)
        snap["derived"] = None
        notes = []
        v = check_report.check_daily(make_report(),
                                     json.dumps(snap, ensure_ascii=False),
                                     BRIEF, notes=notes)
        self.assertEqual(v, [])
        self.assertIn("VERDICT_SKIPPED_NO_DERIVED", notes[0])

    def test_non_dict_derived_emits_the_same_notice(self):
        for bad in ("oops", [1], 7):
            with self.subTest(derived=bad):
                snap = dict(SNAP)
                snap["derived"] = bad
                notes = []
                v = check_report.check_daily(
                    make_report(), json.dumps(snap, ensure_ascii=False),
                    BRIEF, notes=notes)
                self.assertFalse([x for x in v if "VERDICT" in x], (bad, v))
                self.assertIn("VERDICT_SKIPPED_NO_DERIVED", notes[0])

    def test_present_derived_does_not_emit_it(self):
        """有 derived 节时不出这条 —— 它说的是「没有派生节」,不是「schema 旧」。"""
        for ver in (1, 2):
            with self.subTest(ver=ver):
                notes = []
                check_report.check_daily(
                    report_quoting(DAILY_VERDICT),
                    snap_with_derived(schema_version=ver), BRIEF, notes=notes)
                self.assertFalse([x for x in notes
                                  if "VERDICT_SKIPPED_NO_DERIVED" in x], notes)

    def test_notice_is_printed_by_main(self):
        with tempfile.TemporaryDirectory() as tmp:
            rp = os.path.join(tmp, "r.md")
            sp = os.path.join(tmp, "s.json")
            for path, text in ((rp, make_report()), (sp, SNAP_TEXT)):
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = check_report.main([rp, sp])
            out = buf.getvalue()
        self.assertEqual(rc, 0)
        self.assertIn("VERDICT_SKIPPED_NO_DERIVED", out)
        self.assertIn("CHECK PASSED", out)

    def test_library_caller_without_notes_does_not_crash(self):
        """不传 notes 只是拿不到声明,不该崩(`notes is not None` 那道门)。"""
        v = check_report.check_daily(make_report(), SNAP_TEXT, BRIEF)
        self.assertEqual(v, [])


class CurrenciesCoveredByKeywordsTest(unittest.TestCase):
    """USD 的 events 条目只因 events.KEYWORDS 里有 "USD" 才存在 —— 实测
    data/2026-08-12.json 的 rates 只有 4 个键(无 USD)。动一下关键词表,
    USD 条目就会静默消失,而校验器从不读 KEYWORDS。这条断言是唯一的哨兵。"""

    def test_every_currency_has_keywords(self):
        self.assertLessEqual(set(check_report.CURRENCIES),
                             set(events_mod.KEYWORDS))


# 处置文案的**期望值**写在测试里,断言的对象是**校验器的 stdout** —— 不是
# SKILL 散文。T8 复验实测:针对散文的子串哨兵挡不住三种反转措辞
# (句尾追加否定 / 违规节末尾追加"统一口径" / 拆成"旧口径已废弃"+新口径),
# 三条全部 SURVIVED。散文的措辞空间无界,脚本输出的没有。
WANT_QUOTE_DISPOSITION = "把上面「期望原文」那一句整句抄进该币种节,一个字符都不改"
WANT_SCRIPT_BUG_DISPOSITION = "这是脚本缺陷,改报告没用"
# **逐字**期望值,给下面的 assertEqual 用。子串断言对"锚点整句一字不动、
# 句尾追加一句否定"(T8b 的 M-A 形态)天然免疫 —— 实测在 DISPOSITION_QUOTE
# 末尾追加「;不过这条其实也是脚本缺陷,照抄只是走个形式,改了也白搭」,
# 全量 `Ran 679 / OK / rc=0`,一条都没红。散文挡不住这一手是因为措辞空间无界;
# 而**常量有确定的期望值**,逐字钉死就没有追加的余地。代价是改文案必须同时
# 改这里 —— 那正是要的:显式动作、进 diff,与 CLI 开关集合冻结同一形制。
WANT_QUOTE_VERBATIM = ("处置:把上面「期望原文」那一句整句抄进该币种节,"
                       "一个字符都不改;这一条改报告即可,不要动脚本")
WANT_SCRIPT_BUG_VERBATIM = ("处置:这是脚本缺陷,改报告没用;"
                            "重跑产出这份快照/聚合文件的那一步,仍复现就报 bug")

# ---- 码 → 它**自己那一条**处置 ----
# 两个常量在 check_report.py 里共 7 个使用点(ABSENT / MALFORMED / EMPTY /
# NOT_QUOTED / 日报 CONTAINER_MALFORMED / ENTRY_MISSING / 周报
# CONTAINER_MALFORMED)。T8b 复验实测:逐字钉死的只有 NOT_QUOTED 与
# ABSENT 两处,把**其余 5 处**的 DISPOSITION_SCRIPT_BUG 全换成
# DISPOSITION_QUOTE(两个常量本身一字不动)→ 全量 `Ran 680 / OK / rc=0`,
# 而真 CLI 打出「VERDICT_ENTRY_MISSING: …该币种的结论句一条都未校验;
# 处置:把上面「期望原文」那一句整句抄进该币种节…」——
# **校验器亲口叫运维去人工粉饰一个产出端缺陷**,正是假绿的入口。
# 判据因此不是"带了某条处置",而是"带的是它自己那一条、且不含另一条"。
VERDICT_VIOLATION_DISPOSITION = {
    "VERDICT_ABSENT": WANT_SCRIPT_BUG_VERBATIM,
    "VERDICT_MALFORMED": WANT_SCRIPT_BUG_VERBATIM,
    "VERDICT_EMPTY": WANT_SCRIPT_BUG_VERBATIM,
    "VERDICT_NOT_QUOTED": WANT_QUOTE_VERBATIM,
    "VERDICT_CONTAINER_MALFORMED": WANT_SCRIPT_BUG_VERBATIM,
    "VERDICT_ENTRY_MISSING": WANT_SCRIPT_BUG_VERBATIM,
}
# 两个降级码走 notes 而不是违规行,处置**有意**留在 SKILL(判别标准是采集
# 窗口,校验器不知道窗口边界 —— 见 check_report.py 顶部注释),由
# SkippedCodeDispositionTest 守。列在这里只为让下面的"码集合冻结"闭合:
# check_report.py 里一共 8 个 `VERDICT_*` 码,6 + 2。
VERDICT_NOTE_CODES = ("VERDICT_SKIPPED_LEGACY", "VERDICT_SKIPPED_NO_DERIVED")


def assert_own_disposition(tc, out, label):
    """对 stdout 里**每一条** `VERDICT_*` 违规行断言:行尾恰是它自己那一条
    处置、且不含另一条。返回被断言到的码集合。

    ---- T8d:处置断言此前**一条都没跑在生产 argv 形状或真子进程上** ----
    `WANT_*_VERBATIM` / `WANT_*_DISPOSITION` 的命中全部落在
    `CheckerPrintsItsOwnDispositionTest`,而那个类只用 `redirect_stdout` +
    **进程内** `main()`,日报侧更是 `main([rp, sp])` —— 不带 `--brief`、
    不带 `--mode`、**不带 `--strict-brief`**;而带生产形状的两条
    (`test_listed_exemption_tokens_…` / `test_production_shapes_…`)
    只断言 rc 与码集合,**从不看处置文本**。等于处置表在生产命令行下
    完全无人看守。
    实测(T8d,acdd7de 工作树,本机无 FRED_API_KEY):在 main() 的
    `for note in notes:` 前插
      `if args.strict_brief:`
      `    violations = [x.replace(DISPOSITION_QUOTE, DISPOSITION_SCRIPT_BUG)`
      `                  for x in violations]`
    → 全量 `Ran 686 tests / OK / rc=0`(校验器于是对生产日报的
    `VERDICT_NOT_QUOTED` 亲口说"这是脚本缺陷,改报告没用");
    而**形态完全对称**的 `if not args.strict_brief:` 同一段替换
    → `Ran 686 tests / FAILED (failures=4) / rc=1`。
    这一不对称本身就是"处置表只在非生产形状下被看守"的直接证据。
    同一段替换挂在 `if "unittest" not in sys.modules:` 下(N2 形态)也是
    全量 `Ran 686 / OK / rc=0` —— 真子进程里 `unittest` 不在 `sys.modules`,
    所以把这个断言接进子进程能同时覆盖它。
    """
    both = (WANT_QUOTE_VERBATIM, WANT_SCRIPT_BUG_VERBATIM)
    seen = set()
    for raw in out.splitlines():
        line = raw.lstrip(" -").rstrip()
        m = re.match(r"(VERDICT_[A-Z_]+):", line)
        if not m or m.group(1) not in VERDICT_VIOLATION_DISPOSITION:
            continue      # 降级声明(notes)不带处置,处置有意留在 SKILL
        code = m.group(1)
        want = VERDICT_VIOLATION_DISPOSITION[code]
        other = [d for d in both if d != want][0]
        tc.assertTrue(line.endswith(want),
                      "%s:%s 的处置不是它自己那一条(或不在行尾):%s"
                      % (label, code, line))
        tc.assertNotIn(other, line,
                       "%s:%s 的违规行里同时出现了另一条处置:%s"
                       % (label, code, line))
        seen.add(code)
    return seen


def _emitted_verdict_codes(module_path):
    """扫源码里**被打印出去的**违规/声明码。

    判据:AST 里的字符串字面量,且**以 `VERDICT_…:` 开头**(校验器每一行
    都是这个形状)。这样注释与 docstring 里提到的 `VERDICT_*` 不会混进来。
    **已知边界(实测口径,不许写成全称)**:码若由变量或 f-string 拼出来,
    这个扫描看不到 —— 它守的是"现有 8 个码的清单没被人悄悄加减",
    不是"任何形式的新码都跑不掉"。
    """
    with open(module_path, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    codes = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            m = re.match(r"(VERDICT_[A-Z_]+)[::]", node.value)
            if m:
                codes.add(m.group(1))
    return codes


class CheckerPrintsItsOwnDispositionTest(unittest.TestCase):
    """每条 `VERDICT_*` 违规行**自带处置**。

    此前处置只存在于两份 SKILL 的散文里 —— 那是同一份判定的第二份拷贝,
    可以被整体反转,而反转后的措辞空间无界(见上方注释的三条实测绕过)。
    把处置搬进校验器输出后,守的东西从"散文里有没有某句话"变成"脚本输出里
    有没有这句话",后者可被精确断言,且不存在可反转的第二份。
    """

    def _daily_stdout(self, report, snap_text):
        """**生产形状 argv**(T8d):skills/fx-daily-report/SKILL.md:222 与
        README.md:129 那条命令行逐字同形,含 `--brief` / `--mode daily` /
        `--strict-brief`。

        此前这里是 `main([rp, sp])` —— 三个开关一个都不带。于是所有处置
        断言都跑在**非生产形状**上,`if args.strict_brief: <对调处置表>`
        这一行全量全绿(实测见 `assert_own_disposition`),而生产日报命令行
        每次都带 `--strict-brief`。
        """
        with tempfile.TemporaryDirectory() as tmp:
            rp = os.path.join(tmp, "r.md")
            sp = os.path.join(tmp, "s.json")
            bp = os.path.join(tmp, "b.md")
            for path, text in ((rp, report), (sp, snap_text), (bp, BRIEF)):
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = check_report.main([rp, sp, "--brief", bp,
                                        "--mode", "daily", "--strict-brief"])
            return rc, buf.getvalue()

    def _weekly_stdout(self, report, digest_text):
        with tempfile.TemporaryDirectory() as tmp:
            rp = os.path.join(tmp, "w.md")
            dp = os.path.join(tmp, "d.json")
            for path, text in ((rp, report), (dp, digest_text)):
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = check_report.main([rp, "--mode", "weekly", "--digest", dp])
            return rc, buf.getvalue()

    def test_disposition_constants_are_frozen_verbatim(self):
        """两个处置串**逐字**钉死。见 WANT_*_VERBATIM 上方的实测:只做子串断言
        时,"整句留着、句尾追加一句反话"照样全绿。改文案就得改这两行。"""
        self.assertEqual(check_report.DISPOSITION_QUOTE, WANT_QUOTE_VERBATIM)
        self.assertEqual(check_report.DISPOSITION_SCRIPT_BUG,
                         WANT_SCRIPT_BUG_VERBATIM)

    def test_daily_not_quoted_line_carries_the_actionable_disposition(self):
        rc, out = self._daily_stdout(report_quoting(DAILY_VERDICT).replace(
            DAILY_VERDICT, DAILY_VERDICT.replace("11", "12")),
            snap_with_derived())
        self.assertEqual(rc, 1, out)
        line = [x.strip() for x in out.splitlines() if "VERDICT_NOT_QUOTED" in x]
        self.assertTrue(line, out)
        self.assertIn(WANT_QUOTE_DISPOSITION, line[0],
                      "唯一可操作的码在校验器输出里不带处置")
        # **位置也钉住**:处置必须是整行的结尾。只查"含有"时,在同一行后面再
        # 缀一句「不过改了也白搭」照样绿(与常量冻结互补:那条堵改常量,
        # 这条堵在拼接处另加尾巴)。
        self.assertTrue(line[0].endswith(WANT_QUOTE_VERBATIM),
                        "处置不在违规行结尾 —— 后面还跟着别的话:%s" % line[0])

    def test_weekly_not_quoted_line_carries_the_actionable_disposition(self):
        rc, out = self._weekly_stdout(WEEKLY_OK.replace(ART_PHP, "改写过"), DIGEST)
        self.assertEqual(rc, 1, out)
        line = [x.strip() for x in out.splitlines() if "VERDICT_NOT_QUOTED" in x]
        self.assertTrue(line, out)
        self.assertIn(WANT_QUOTE_DISPOSITION, line[0],
                      "周报侧的可操作码在校验器输出里不带处置")
        self.assertTrue(line[0].endswith(WANT_QUOTE_VERBATIM),
                        "处置不在违规行结尾 —— 后面还跟着别的话:%s" % line[0])

    def test_script_defect_codes_carry_the_other_disposition(self):
        """反过来同样要守:"脚本缺陷"那几条若被写成"改报告",运维就会去人工
        粉饰一个产出端缺陷 —— 那正是假绿的入口。两句处置互为对照。"""
        obj = json.loads(DIGEST)
        del obj["events"]["PHP"]["official_verdict"]
        rc, out = self._weekly_stdout(WEEKLY_OK,
                                      json.dumps(obj, ensure_ascii=False))
        self.assertEqual(rc, 1, out)
        line = [x.strip() for x in out.splitlines() if "VERDICT_ABSENT" in x]
        self.assertTrue(line, out)
        self.assertIn(WANT_SCRIPT_BUG_DISPOSITION, line[0])
        self.assertTrue(line[0].endswith(WANT_SCRIPT_BUG_VERBATIM),
                        "处置不在违规行结尾:%s" % line[0])

    def _digest_with(self, **patch):
        obj = json.loads(DIGEST)
        for k, v in patch.items():
            if k == "rates_verdict":
                obj["rates"]["PHP"]["fixings_verdict"] = v
            elif k == "drop_official":
                del obj["events"]["PHP"]["official_verdict"]
            else:
                obj[k] = v
        return json.dumps(obj, ensure_ascii=False)

    def _snap_with(self, **patch):
        obj = json.loads(snap_with_derived())
        obj["derived"].update(patch)
        return json.dumps(obj, ensure_ascii=False)

    def _disposition_cases(self):
        """**7 个使用点各一条触发用例**,按码归组。

        (label, 触发码, (rc, stdout))。日报侧与周报侧的
        VERDICT_CONTAINER_MALFORMED 是**两个独立的拼接点**
        (check_report.py 的 266 与 487),必须各触发一次 —— 只测一侧时,
        另一侧的处置被换成相反那条不会有任何测试变红。
        """
        wrong = DAILY_VERDICT.replace("11", "12")
        return [
            ("日报 NOT_QUOTED", "VERDICT_NOT_QUOTED", self._daily_stdout(
                report_quoting(DAILY_VERDICT).replace(DAILY_VERDICT, wrong),
                snap_with_derived())),
            ("周报 NOT_QUOTED", "VERDICT_NOT_QUOTED", self._weekly_stdout(
                WEEKLY_OK.replace(ART_PHP, "改写过"), DIGEST)),
            ("日报 ABSENT", "VERDICT_ABSENT", self._daily_stdout(
                make_report(), snap_with_derived(verdict=None))),
            ("周报 ABSENT", "VERDICT_ABSENT", self._weekly_stdout(
                WEEKLY_OK, self._digest_with(drop_official=True))),
            ("日报 MALFORMED", "VERDICT_MALFORMED", self._daily_stdout(
                make_report(), snap_with_derived(verdict=7))),
            ("周报 MALFORMED", "VERDICT_MALFORMED", self._weekly_stdout(
                WEEKLY_OK, self._digest_with(rates_verdict=7))),
            ("日报 EMPTY", "VERDICT_EMPTY", self._daily_stdout(
                make_report(), snap_with_derived(verdict="   "))),
            ("周报 EMPTY", "VERDICT_EMPTY", self._weekly_stdout(
                WEEKLY_OK, self._digest_with(rates_verdict="   "))),
            ("日报 CONTAINER_MALFORMED", "VERDICT_CONTAINER_MALFORMED",
             self._daily_stdout(make_report(), self._snap_with(events=7))),
            ("周报 CONTAINER_MALFORMED", "VERDICT_CONTAINER_MALFORMED",
             self._weekly_stdout(WEEKLY_OK, self._digest_with(rates=7))),
            ("日报 ENTRY_MISSING", "VERDICT_ENTRY_MISSING", self._daily_stdout(
                report_quoting(DAILY_VERDICT),
                snap_with_derived(currencies=("USD",)))),
        ]

    def test_every_violation_code_carries_its_own_disposition(self):
        """**逐码**断言:每个 `VERDICT_*` 违规行末尾带的是
        `VERDICT_VIOLATION_DISPOSITION` 里给它的那一条,且**不含另一条**。

        旧写法只查"含有「处置:」"(实测口径,不是推测):把 5 个
        DISPOSITION_SCRIPT_BUG 使用点全换成 DISPOSITION_QUOTE,全量仍
        `Ran 680 / OK`;把 MALFORMED 与 ENTRY_MISSING 两个码的处置**整段
        删掉**,全量照样绿(旧地板 `assertGreaterEqual(len(seen), 4)` 恰好
        只看得见 4 个码,零余量)。
        """
        both = (WANT_QUOTE_VERBATIM, WANT_SCRIPT_BUG_VERBATIM)
        seen = set()
        for label, code, (rc, out) in self._disposition_cases():
            with self.subTest(case=label):
                self.assertEqual(rc, 1, out)
                want = VERDICT_VIOLATION_DISPOSITION[code]
                other = [d for d in both if d != want][0]
                lines = [x.lstrip(" -").rstrip() for x in out.splitlines()
                         if x.lstrip(" -").startswith(code + ":")]
                self.assertTrue(lines, "%s 没触发出 %s\n%s" % (label, code, out))
                for line in lines:
                    seen.add(code)
                    self.assertTrue(
                        line.endswith(want),
                        "%s 的处置不是它自己那一条(或不在行尾):%s" % (code, line))
                    self.assertNotIn(
                        other, line,
                        "%s 的违规行里同时出现了另一条处置:%s" % (code, line))
        self.assertEqual(seen, set(VERDICT_VIOLATION_DISPOSITION),
                         "有映射了处置却没有任何用例触发的码")

    def test_source_verdict_codes_are_exactly_the_mapped_ones(self):
        """码清单冻结:check_report.py 打印出去的 `VERDICT_*` 码集合,必须
        恰好等于 `VERDICT_VIOLATION_DISPOSITION` 的键 ∪ 两个降级码。

        它是上一条的闭合件:新增一个码而忘了给它写处置时,这条红
        (不是"自动被守" —— 是"不改这张表就过不去")。
        边界见 `_emitted_verdict_codes` 的 docstring:拼接出来的码扫不到。
        """
        found = _emitted_verdict_codes(check_report.__file__)
        want = set(VERDICT_VIOLATION_DISPOSITION) | set(VERDICT_NOTE_CODES)
        self.assertEqual(found, want,
                         "校验器的码清单与处置表对不上;新增码必须同时入表")
        self.assertEqual(len(want), 8, want)




class VerdictGateIsOrthogonalToTheCheckedObjectTest(unittest.TestCase):
    """闸门的判定**不得受被查对象自身控制**。

    T8b 复验实测三条真 CLI 全部 `CHECK PASSED` rc=0、全量全绿:
    - **V7**:聚合文件加一个字段 `verdict_check: "off"`(据它把 digest 视作
      None,整块结论句校验静默跳过);
    - **V8**:报告正文首行 `<!-- verdict-exempt -->`;
    - **V12**:报告文件名以 `.draft.md` 结尾。

    复验者的定性照抄:**被校验的那份报告是 LLM 自己写的,豁免口开在被查
    对象里等于把闸门钥匙交给被查方。** 逐条加哨兵没有尽头(换字段名、换
    注释措辞、换后缀各是一条),所以这里改成**正交不变量**:同一份必然违规
    的输入,在 ①换文件名 ②报告/快照/聚合文件追加任意未知字段与注释
    ③清空白名单外的环境变量 三种扰动下,rc 必须仍为 1、且基线上出现过的
    那组码一个都不许少。日报侧与周报侧各跑一遍。

    与 A 类(在受守文字**旁边**追加否定文字)的区别在于**可判定**:
    "换个名字/加个字段/清掉环境之后判定还一样吗"是能跑出来的等价性,
    不是"附近有没有一句话否定它"。
    """

    ENV_WHITELIST = ("PYTHONDONTWRITEBYTECODE",)

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.t = cls._tmp.name
        snap = dict(SNAP)
        snap["derived"] = {
            "schema_version": 2, "rates": {}, "real_rate": {},
            "events": {"USD": {"events_verdict": DAILY_VERDICT},
                       "EUR": {},
                       "PHP": {"events_verdict": 7},
                       "THB": {"events_verdict": "   "}},
        }
        wobj = json.loads(DIGEST)
        wobj["rates"]["PHP"]["fixings_verdict"] = 7
        wobj["events"]["PHP"]["articles_verdict"] = "   "
        del wobj["events"]["PHP"]["official_verdict"]
        wobj["events"]["USD"] = {"articles_verdict": "报告里不存在的这一句",
                                 "official_verdict": OFF_PHP}
        cls.brief = os.path.join(cls.t, "brief.md")
        with open(cls.brief, "w", encoding="utf-8") as f:
            f.write(BRIEF)
        # (标签, 报告正文, 附件正文, 附件扩展名, argv 拼法, **期望码集合**)
        # 最后一位是 T8d 补的:基线码集合不许由被测校验器自己算出来,
        # 否则整族少一个码时 `missing = base_codes - codes(out)` 恒空。
        cls.MODES = (
            ("daily", make_report(), json.dumps(snap, ensure_ascii=False),
             ".json", lambda rp, ap, bp: [rp, ap, "--brief", bp,
                                          "--mode", "daily", "--strict-brief"],
             NoLegacyExemptionSwitchTest.DAILY_BASE_CODES),
            ("weekly", WEEKLY_OK, json.dumps(wobj, ensure_ascii=False),
             ".json", lambda rp, ap, bp: [rp, "--mode", "weekly",
                                          "--digest", ap],
             NoLegacyExemptionSwitchTest.WEEKLY_BASE_CODES),
        )

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def _write(self, name, text):
        p = os.path.join(self.t, name)
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
        return p

    def _run(self, argv, env=None):
        r = subprocess.run([sys.executable,
                            NoLegacyExemptionSwitchTest.CHECK_PY] + list(argv),
                           capture_output=True, text=True,
                           env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
                           if env is None else env)
        return r.returncode, r.stdout, r.stderr

    def _baseline(self, mode):
        label, rtext, atext, ext, build, expected = mode
        rp = self._write("base-%s.md" % label, rtext)
        ap = self._write("base-%s%s" % (label, ext), atext)
        argv = build(rp, ap, self.brief)
        rc, out, err = self._run(argv)
        codes = NoLegacyExemptionSwitchTest._codes(out)
        self.assertEqual(rc, 1, (label, out, err))
        # T8d:与写死的字面量比,不许由被测二进制自证基线
        self.assertEqual(codes, set(expected),
                         "%s 的基线码集合与写死的期望不符\n%s" % (label, out))
        assert_own_disposition(self, out, "%s 基线" % label)
        return argv, codes

    def _assert_same_verdict(self, label, argv, base_codes, env=None):
        rc, out, err = self._run(argv, env=env)
        self.assertEqual(rc, 1, "%s:rc 由 1 变 %d\n%s\n%s"
                         % (label, rc, out, err))
        missing = base_codes - NoLegacyExemptionSwitchTest._codes(out)
        self.assertFalse(missing, "%s:这些码消失了 %s\n%s"
                         % (label, sorted(missing), out))
        # 处置也必须在每一种扰动下不变(真子进程 + 生产形状)
        assert_own_disposition(self, out, label)

    def test_filenames_do_not_change_the_verdict(self):
        """扰动 ①:文件名。含 V12 那条 `.draft.md`,以及无扩展名/随机名。"""
        for mode in self.MODES:
            label, rtext, atext, ext, build, _ = mode
            _, base_codes = self._baseline(mode)
            ap = self._write("fn-%s%s" % (label, ext), atext)
            for rn in ("r.draft.md", "2026-08-13-DRAFT.md",
                       os.urandom(6).hex(), "r.md.bak"):
                rp = self._write("%s-%s" % (label, rn), rtext)
                with self.subTest(mode=label, report=rn):
                    self._assert_same_verdict(
                        "%s 报告名 %s" % (label, rn),
                        build(rp, ap, self.brief), base_codes)
            rp = self._write("fn-%s.md" % label, rtext)
            for an in ("a.draft" + ext, os.urandom(6).hex()):
                ap2 = self._write("%s-%s" % (label, an), atext)
                with self.subTest(mode=label, aux=an):
                    self._assert_same_verdict(
                        "%s 附件名 %s" % (label, an),
                        build(rp, ap2, self.brief), base_codes)

    def test_unknown_fields_and_comments_do_not_change_the_verdict(self):
        """扰动 ②:被查对象里追加任意未知字段/注释。含 V8 的
        `<!-- verdict-exempt -->` 与 V7 的 `verdict_check:"off"`。"""
        for mode in self.MODES:
            label, rtext, atext, ext, build, _ = mode
            _, base_codes = self._baseline(mode)
            ap = self._write("xf-%s%s" % (label, ext), atext)
            reports = {
                "首行 verdict-exempt 注释": "<!-- verdict-exempt -->\n" + rtext,
                "末行 skip-verdict 注释": rtext + "\n<!-- skip-verdict: true -->\n",
                "正文里的免检声明": rtext.replace(
                    "\n## ", "\n> 本报告为草稿,verdict_check=off,免于结论句校验\n\n## ", 1),
            }
            for i, (rlabel, rtext2) in enumerate(sorted(reports.items())):
                rp = self._write("xf-%s-%d.md" % (label, i), rtext2)
                with self.subTest(mode=label, perturb=rlabel):
                    self._assert_same_verdict(
                        "%s %s" % (label, rlabel),
                        build(rp, ap, self.brief), base_codes)
            rp = self._write("xf-%s-r.md" % label, rtext)
            extras = (("verdict_check=off", {"verdict_check": "off"}),
                      ("exempt=true", {"exempt": True, "strict": False}),
                      ("未知自由字段", {"__note__": "自由文本", "tolerant": 1}))
            for i, (alabel, extra) in enumerate(extras):
                obj = json.loads(atext)
                obj.update(extra)
                if isinstance(obj.get("derived"), dict):
                    obj["derived"] = dict(obj["derived"], **extra)
                ap2 = self._write("xf-%s-%d%s" % (label, i, ext),
                                  json.dumps(obj, ensure_ascii=False))
                with self.subTest(mode=label, perturb=alabel):
                    self._assert_same_verdict(
                        "%s 附件 %s" % (label, alabel),
                        build(rp, ap2, self.brief), base_codes)

    def test_clearing_the_environment_does_not_change_the_verdict(self):
        """扰动 ③:白名单之外的环境变量全清,以及塞满豁免味的环境变量。

        实测(2026-08-13,本机 python3):`env -i python3` 的
        `sys.stdout.encoding` 仍是 `utf-8`(PEP 538 的 C locale coercion),
        所以清空环境不会把中文输出变成 UnicodeEncodeError —— 这条扰动
        测的是判定,不是编码。
        """
        for mode in self.MODES:
            label = mode[0]
            argv, base_codes = self._baseline(mode)
            for elabel, env in (
                    ("环境全清", {}),
                    ("只留白名单", {k: "1" for k in self.ENV_WHITELIST}),
                    ("塞满豁免味的环境变量",
                     dict(os.environ, VERDICT_CHECK="off",
                          CHECK_REPORT_TOLERANT="1", FX_SKIP_VERDICT="yes",
                          STRICT="0", PYTHONDONTWRITEBYTECODE="1"))):
                with self.subTest(mode=label, env=elabel):
                    self._assert_same_verdict("%s %s" % (label, elabel),
                                              argv, base_codes, env=env)

    # 环境变量类的名字。`os.environ` / `os.getenv` 两条正门,
    # `environb` / `putenv` 两条侧门;字符串常量那一条堵的是
    # `getattr(os, "environ")`。
    FORBIDDEN_ENV_NAMES = ("environ", "environb", "getenv", "putenv")
    FORBIDDEN_ENV_MODULES = ("os", "posix", "nt")

    def test_checker_source_never_reads_the_environment(self):
        """**静态可判定**的不变量:`scripts/check_report.py` 的 AST 里不得
        出现环境变量访问。

        B8 实测(T8b 复验):在模块加载期用环境变量翻转一个常量,测试进程
        天然取到未反转的那一支 —— 全量全绿,而真 CLI 在导出该变量后行为
        变了。环境是**被查对象与运维都够得着、而测试进程够不着**的旋钮,
        闸门读它就等于把钥匙交出去。

        判据(实测口径,已知边界写在下面,不许写成全称):
        禁 `environ/environb/getenv/putenv` 的属性访问与裸名字、禁与它们
        逐字相等的字符串常量(堵 `getattr(os, "environ")`)、禁 import
        `os/posix/nt`。**够不着的**:`__import__("o"+"s")` 这种把模块名和
        属性名都拼出来的写法 —— 字符串构造空间无界,静态扫不到。
        校验器真需要 `os.path` 时,改这条断言是显式动作、会进 diff。
        """
        with open(check_report.__file__, encoding="utf-8") as f:
            tree = ast.parse(f.read())
        bad = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) \
                    and node.attr in self.FORBIDDEN_ENV_NAMES:
                bad.append("第 %d 行 属性 .%s" % (node.lineno, node.attr))
            elif isinstance(node, ast.Name) \
                    and node.id in self.FORBIDDEN_ENV_NAMES:
                bad.append("第 %d 行 名字 %s" % (node.lineno, node.id))
            elif isinstance(node, ast.Constant) \
                    and isinstance(node.value, str) \
                    and node.value in self.FORBIDDEN_ENV_NAMES:
                bad.append("第 %d 行 字符串常量 %r(getattr 走后门)"
                           % (node.lineno, node.value))
            elif isinstance(node, ast.Import):
                for a in node.names:
                    if a.name.split(".")[0] in self.FORBIDDEN_ENV_MODULES:
                        bad.append("第 %d 行 import %s" % (node.lineno, a.name))
            elif isinstance(node, ast.ImportFrom):
                mod = (node.module or "").split(".")[0]
                if mod in self.FORBIDDEN_ENV_MODULES:
                    bad.append("第 %d 行 from %s import …"
                               % (node.lineno, node.module))
                for a in node.names:
                    if a.name in self.FORBIDDEN_ENV_NAMES:
                        bad.append("第 %d 行 from … import %s"
                                   % (node.lineno, a.name))
        self.assertEqual(bad, [],
                         "校验器读了环境变量(或引入了能读到的模块):%s"
                         % "; ".join(bad))
