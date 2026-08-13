import json
import os
import tempfile
import unittest

from scripts import check_report

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


DIGEST = json.dumps({"week": "2026-W33",
                     "rates": {"PHP": {"chg_pct_week": -0.192, "range_low": 60.75,
                                       "range_high": 60.867, "fixings": 2}},
                     "verdicts": {"命中": 1, "未命中": 0, "无法判定": 15, "未判定": 10}})

WEEKLY_OK = """# 外汇周报 2026-W33

> 覆盖日报:3 份(2026-08-07, 2026-08-08, 2026-08-10);缺失日期:无

## 本周主线
- 比索本周走强

## 各币种一周归因
USD / EUR / PHP 周涨跌 -0.192%,区间 60.75–60.867(2 次定盘) / THB / BRL

## 复盘汇总
- 命中 1、未命中 0、无法判定 15、未判定 10

## 下周关注
- 关注定盘更新

## 缺漏汇总
- 无
"""


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
        with tempfile.TemporaryDirectory() as tmp:
            body = json.dumps({"week": "2026-W33", "generated_from": [],
                               "rates": {"PHP": {"chg_pct_week": -0.192,
                                                 "range_low": 60.75,
                                                 "range_high": 60.867,
                                                 "fixings": 2}},
                               "verdicts": {"命中": 1, "未命中": 0,
                                            "无法判定": 15, "未判定": 10}})
            self.assertEqual(self._run(tmp, body), 0)


class WeeklyGapOmittedTest(unittest.TestCase):
    """I9 收口检查此前零测试(变异存活):digest 的每个缺漏源须在缺漏汇总出现。"""

    DIGEST_OBJ = {"week": "2026-W33", "generated_from": ["2026-08-10"],
                  "gaps_by_source": {"gdelt": 18, "dbnomics": 3}}

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
        for bad in ({"a": 1}, 7, ["x"], True, 1.5):
            v, _ = self._run("任意报告", {"USD": {"articles_verdict": bad}})
            self.assertTrue(any("VERDICT_MALFORMED" in x for x in v), (bad, v))

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


class VerdictFieldConstantsTest(unittest.TestCase):
    """字段名 SHALL 显式枚举,MUST NOT 按名字模式搜集 —— digest 顶层的
    `verdicts` 是计数 dict、`verdict_details` 是 list,模式匹配会把非字符串
    结构送进字符串比对。"""

    def test_constants_are_explicit_tuples(self):
        self.assertEqual(check_report.VERDICT_FIELDS_EVENTS,
                         ("articles_verdict", "official_verdict"))
        self.assertEqual(check_report.VERDICT_FIELDS_RATES, ("fixings_verdict",))
        self.assertEqual(check_report.VERDICT_FIELD_DAILY, ("events_verdict",))

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
