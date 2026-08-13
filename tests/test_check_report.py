import contextlib
import io
import json
import os
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


class NoLegacyExemptionSwitchTest(unittest.TestCase):
    """豁免机制本身会成为下一个绕过点(Design Doc §6)。校验器的 CLI 开关
    集合按**注册表**钉死:开关一旦注册就躲不过这条断言,想加就得先改掉它,
    而那是显式动作。

    **不能扫 `--help` 的输出**:argparse 对 `help=argparse.SUPPRESS` 的选项
    根本不打印。实测按 SUPPRESS 注册 `--tolerant` 并在 main 里据它滤掉整类
    `VERDICT_*` 违规 —— 同一份输入的 rc 由 1(CHECK FAILED 5 条)变成
    0(CHECK PASSED),而全量 674 全绿、旧断言(扫 --help 文本)照过。
    """

    def test_cli_option_set_is_frozen(self):
        opts = {s for a in check_report.build_parser()._actions
                for s in a.option_strings}
        self.assertEqual(opts, {"-h", "--help", "--brief", "--mode",
                                "--strict-brief", "--digest", "--daily"})


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
