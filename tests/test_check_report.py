import ast
import contextlib
import io
import itertools
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from scripts import check_report
from scripts import claims
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


# ---- 「本期相对上期的变化」节:2026-08-14 起它是**每份合规日报的必备节** ----
# `--prior` 从这一天起是必给参数(缺席 rc=2),而 `check_prior_period` 的第二态
# 规定「当前报告缺该节 = PRIOR_PERIOD_SECTION_MISSING」—— 于是"结构合规的日报"
# 这个概念本身变了,`make_report()` 必须跟着变,否则库里每一条走 CLI 的断言
# 都在测一份**不合规**的报告。
# 两句都不含数字、不含句末标点,理由同 PriorPeriodBoilerplateTest:本仓多处
# 断言"除某码外零违规",数字会引来 NUMBER_UNTRACEABLE 把失败原因搅浑。
# 两句**必须互不相同**:当期与上一期用同一句就是 PRIOR_PERIOD_BOILERPLATE。
PRIOR_LINE_CUR = "- 本期五币种的判断相对上期均有更新,逐条见各币种节。"
PRIOR_LINE_PREV = "- 上一期相对更早一期未变,没变的原因是当周无数据发布。"


# ---- 判断环:2026-08-14 起**每个币种节都必须有**,没有任何豁免路径 ----
# 在此之前 `make_report()` 的五个币种节只有 PHP 在判断环用例里被单独换成四环,
# 其余四节一件都不写 —— 而那时快照默认没有 `derived.body_plan`,整层直接跳过,
# 于是"这份 fixture 是不是一份合规日报"这个问题从来没被问过。豁免删掉之后
# 它必须被问:五节各自带完整三件,否则库里每一条"除某码外零违规"的断言都在
# 测一份**不合规**的报告。
# 三件的措辞刻意各节不同(替代解释与翻转指标都换词):同句会撞 ②
# FLIP_INDICATOR_IS_INVALIDATION_RESTATED,那不是这些测试想测的东西。
# 数字只取 SNAP/BRIEF 里有的(60.843/60.9/3.1/35.2/5.43/0.921)与 ALLOWED_SMALL,
# 否则会引来 NUMBER_UNTRACEABLE 把失败原因搅浑。
def ring_clause(assumption, alternative, flip):
    """一节的「分歧与判断」三件。关键假设按 SKILL 要求带"不成立时"后半句 ——
    ② 要比的失效条件句就是它,缺了它 ② 在该节整条不执行。"""
    return ("**分歧与判断**:关键假设是%s,不成立时该档的位次读法作废。"
            "替代解释:%s(其翻转指标:同次定盘里另三盘同步跟随)。"
            "翻转指标:%s(T+3)。" % (assumption, alternative, flip))


def make_report(summary_items=3, missing=None, php_body=None, gap_body="无",
                extra_number=None, prior_line=PRIOR_LINE_CUR, review=None):
    lines = ["# 外汇日报 2026-08-10", "", "## 执行摘要"]
    lines += ["- 摘要第 %d 条" % (i + 1) for i in range(summary_items)]
    sections = {
        "美元(USD)": "**昨日发生**:无明确驱动。**定价含义**:观望。"
                      "**情景与触发条件**:若有 FOMC 信号,则关注美元流动性。"
                      + ring_clause("这 4 笔移动由同一批账户推出",
                                    "四个本地因子撞在同一天",
                                    "四盘出现反向分化"),
        "欧元(EUR)": "**昨日发生**:无明确驱动。**情景与触发条件**:若 ECB 表态,则关注 0.921 附近波动。"
                      + ring_clause("0.921 这一档仍由利差主导",
                                    "欧元这一档是美元一端在统一定价",
                                    "欧元脱离 0.921 一侧"),
        "菲律宾比索(PHP)": php_body or (
            "**昨日发生**:CPI 同比 3.1,前值 3.4。**定价含义**:通胀回落。"
            "**情景与触发条件**:若 BSP 释放降息信号,则关注 60.843 上方压力。"
            + ring_clause("3.1 这一读数仍代表当前通胀",
                          "比索走弱是美元一端在统一定价",
                          "参考价回落至 60.9 一侧")),
        "泰铢(THB)": "**昨日发生**:无明确驱动。**情景与触发条件**:若出口数据走弱,则关注 35.2 附近。"
                      + ring_clause("35.2 这一档仍由出口链主导",
                                    "泰铢这一档跟随区域资金流",
                                    "泰铢升破 35.2 一侧"),
        "巴西雷亚尔(BRL)": "**昨日发生**:无明确驱动。**情景与触发条件**:若 COPOM 表态,则关注 5.43。"
                            + ring_clause("5.43 这一档仍由套息厚度主导",
                                          "雷亚尔这一档在要价风险补偿",
                                          "雷亚尔回落至 5.43 一侧"),
    }
    for name, body in sections.items():
        if missing and missing in name:
            continue
        lines += ["", "## " + name, body]
    lines += ["", "## 复盘", review or "- 首次运行,无历史观点可复盘"]
    lines += ["", "## 数据缺漏", gap_body]
    if prior_line:
        # `prior_line=None` 给那些**故意**要造"缺该节"形态的测试用
        # (PriorPeriodBoilerplateTest 自己拼节、以及"上一份是旧格式"那一态)
        lines += ["", "## 本期相对上期的变化", prior_line]
    if extra_number:
        lines.append("另外汇率大约是 %s。" % extra_number)
    return "\n".join(lines)


def daily_files(tmp, report_text=None, snapshot_text=SNAP_TEXT,
                brief_text=BRIEF, prior_text=None, log_text=None, extra=()):
    """在 `tmp` 下写齐日报模式的**全部必给输入**,返回 (argv, paths)。

    2026-08-14 起 `--brief` / `--prior` / `--decision-log` 缺一个即 rc=2,
    测试里因此**再没有"少写一个参数"的合法形态**。所有构造日报 CLI 的地方
    都走这里:谁想再开一条"不带某个参数也能跑"的宽松路径,得先绕过这个
    helper,而绕过会进 diff。

    `prior_text` 默认是一份**内容不同的**合规日报 —— 与当期同句会撞
    PRIOR_PERIOD_BOILERPLATE,那不是这些测试想测的东西。
    """
    paths = {}
    for name, text in (
            ("r.md", make_report() if report_text is None else report_text),
            ("s.json", snapshot_text),
            ("b.md", brief_text),
            ("prior.md", make_report(prior_line=PRIOR_LINE_PREV)
             if prior_text is None else prior_text),
            # DECISION_LOG 定义在本文件靠后(挨着它自己那个测试类),
            # 这里用哨兵取值而不是把常量搬上来 —— 搬动会让 diff 里出现
            # 一大块与本轮无关的位移
            ("log.jsonl", DECISION_LOG if log_text is None else log_text)):
        paths[name] = os.path.join(tmp, name)
        with open(paths[name], "w", encoding="utf-8") as f:
            f.write(text)
    argv = [paths["r.md"], paths["s.json"], "--brief", paths["b.md"],
            "--prior", paths["prior.md"],
            "--decision-log", paths["log.jsonl"]] + list(extra)
    return argv, paths


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
        with tempfile.TemporaryDirectory() as tmp:
            argv, paths = daily_files(tmp, extra=("--mode", "daily"))
            self.assertEqual(check_report.main(argv), 0)
            with open(paths["r.md"], "w", encoding="utf-8") as f:
                f.write(make_report(missing="THB"))
            self.assertEqual(check_report.main(argv), 1)


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
                review_body="- 命中 2 / 未命中 1 / 无法判定 2 / 未到期 1 / 未复盘 0"
                            "\n- 2026-08-05 PHP 命中",
                currency_body=None):
    lines = ["# 外汇周报 2026-W32", "", "> " + coverage if coverage else "", ""]
    lines += ["## 本周主线"] + ["- 主线 %d" % (i + 1) for i in range(theme_items)]
    if date_heading:
        lines += ["", "## 2026-08-05", "当日流水"]
    body = {
        "各币种一周归因": currency_body if currency_body is not None else
            "USD 观望;EUR 震荡;PHP 通胀回落主导;THB 出口疲弱;BRL 政策预期反复。",
        "复盘汇总": review_body,
        "本周关注": "- 关注五央行表态",
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

    def test_pending_bucket_must_appear_in_the_weekly_review(self):
        """「未到期」是本轮拆出来的那一档 —— 周报复盘汇总不写它,读者就还是
        只看得到「无法判定」,病灶原样保留。"""
        body = "- 命中 1 / 未命中 1 / 无法判定 1 / 未复盘 0"
        v = check_report.check_weekly(make_weekly(review_body=body))
        self.assertTrue(any("REVIEW_TOKEN_MISSING" in x and "未到期" in x
                            for x in v), v)

    def test_review_tokens_come_from_the_resolver_vocabulary(self):
        """词表只有一份事实源 —— 校验器手抄一份,四档改名时它不会红。"""
        self.assertEqual(check_report.REVIEW_TOKENS, claims.STATUSES)

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
              "verdicts": {"命中": 1, "未命中": 0, "无法判定": 15, "未到期": 4,
                 "未复盘": 6},
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
- 命中 1、未命中 0、无法判定 15、未到期 4、未复盘 6

## 本周关注
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
        v = check_report.check_weekly(bad, DIGEST, RING_DAILY)
        self.assertTrue(any("NUMBER_UNTRACEABLE" in x and "61.999" in x for x in v), v)

    def test_number_from_daily_report_allowed(self):
        bad = WEEKLY_OK.replace("区间 60.75–60.867", "区间 60.75–60.867,期间见 33.013")
        self.assertTrue(check_report.check_weekly(bad, DIGEST, RING_DAILY))          # 无日报时被拦
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

    def test_explicitly_disabling_it_skips_the_layer_and_declares(self):
        """**弱化必须是显式动作**。2026-08-14 起 `strict_brief` 的默认值由
        False 翻成 True(CLI 侧唯一弱化入口是 `--no-strict-brief`),所以这
        一条测的不再是"不传这个参数",而是"显式传 False" —— 且它必须往
        notes 里放一条**带计数**的声明,否则"没查"与"查过且全过"不可分辨。
        """
        brief = "要点表\n- 自己编的 99.123"
        notes = []
        v = check_report.check_daily("# r\n", self.SNAP, brief,
                                     strict_brief=False, notes=notes)
        self.assertFalse([x for x in v if "BRIEF_NUMBER_UNTRACEABLE" in x], v)
        line = "\n".join(n for n in notes if n.startswith("STRICT_BRIEF_DISABLED"))
        self.assertIn("要点表 1 个数字", line, notes)

    def test_the_layer_is_on_without_passing_any_flag(self):
        """默认值本身是不变量:默认 False 时,"忘了传"与"决定不查"在调用点
        上不可分辨 —— 与 CLI 侧那三条 fail-open 是同一个病、只低一层。"""
        brief = "要点表\n- 自己编的 99.123"
        v = check_report.check_daily("# r\n", self.SNAP, brief)
        self.assertTrue(any("BRIEF_NUMBER_UNTRACEABLE" in x and "99.123" in x
                            for x in v), v)


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

    def test_explicitly_disabled_means_no_brief_codes_but_one_declaration(self):
        """显式关闭时这一层整块不跑(零 `BRIEF_*` 违规、零豁免声明),但
        **必须留下一条带计数的降级声明** —— 显式不等于可以静默。"""
        notes = []
        v = check_report.check_daily("# r\n", self.SNAP,
                                     self._brief(head_extra="- 自己编的 99.123"),
                                     strict_brief=False, notes=notes)
        self.assertEqual([x for x in v if x.startswith("BRIEF_")], [], v)
        self.assertEqual([n for n in notes if "BRIEF_REVIEW_BLOCK" in n], [],
                         notes)
        self.assertTrue([n for n in notes
                         if n.startswith("STRICT_BRIEF_DISABLED")], notes)

    def test_declaration_reaches_stdout_with_rc_zero(self):
        """声明必须真的印出去 —— 只放进 notes 而 main 不打印等于没有。

        走 main() 就得用与 make_report() 配套的 SNAP_TEXT 当快照,故要点表
        手写部分只放该快照里的数;复盘材料行里那 4 个数仍不在快照中 ——
        豁免一旦失效,rc 立刻由 0 变 1,这条断言不是走过场。"""
        head = "# 要点表 2026-08-10\n- 当日定盘 60.843\n"
        with tempfile.TemporaryDirectory() as tmp:
            argv, _ = daily_files(tmp, brief_text=self._brief(head=head),
                                  extra=("--mode", "daily"))
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = check_report.main(argv)
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
        """daily 模式的位置参数仍是必需的,且真的被读 —— 拒收位置参数是
        **weekly 一侧**的事,不许顺手把 daily 的也拒了。"""
        with tempfile.TemporaryDirectory() as tmp:
            argv, _ = daily_files(tmp, extra=("--mode", "daily"))
            rc, out, _ = self._run(argv)
        self.assertEqual(rc, 0, out)
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
            rp = self._report(tmp, WEEKLY_OK.replace("## 本周关注", "## 删掉了"))
            rc, out = self._run([rp, "--mode", "weekly"])
        self.assertEqual(rc, 1)
        self.assertIn(self.LINE, out)

    def test_daily_mode_never_prints_it(self):
        """daily 模式**一个字不改**。"""
        with tempfile.TemporaryDirectory() as tmp:
            argv, _ = daily_files(tmp, extra=("--mode", "daily"))
            rc, out = self._run(argv)
        self.assertEqual(rc, 0, out)
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
        # `--prior`(上一份日报,PRIOR_PERIOD_* 那条不变量的入参)是 2026-08-14
        # **新注册**的选项 —— 这条断言当场变红,正是它存在的意义:选项集合
        # 变了必须是显式动作、进 diff。这里是**加一项**,不是放宽判据。
        # `--decision-log`(决策日志 jsonl,DECISION_TRIGGER_NOT_SOURCED 那条
        # 不变量的入参)是 2026-08-14 **新注册**的选项 —— 与 `--prior` 同规矩,
        # 这里是**加一项**,不是放宽判据。
        # **`--strict-brief` 已删除,换成 `--no-strict-brief`**(2026-08-14):
        # 强判定成了默认,弱化改走一个必须显式写出、且会打印带计数声明的开关。
        # 有意**不**把旧名留成 no-op 兼容开关 —— no-op 开关就是一个"注册了却
        # 没人读"的选项,它会同时进两个 mode 的不读选项表(第六族的幂集翻倍),
        # 而陈旧调用点会**静默地什么都不做**。删掉之后,陈旧调用点在 argparse
        # 层就 rc=2 响亮死掉,这一条断言正是它进 diff 的地方。
        self.assertEqual(opts, {"-h", "--help", "--brief", "--mode",
                                "--no-strict-brief", "--digest", "--daily",
                                "--prior", "--decision-log"})

    # 「当前 mode 不读的既有选项」的**期望字面量**。它**不驱动任何变体** ——
    # 驱动第六族的是 `unread_option_specs()` 的推导结果(见该函数)。
    # 这里只是**防退化哨兵**:AST 走空、`main()` 被重构成推导认不出的形状时,
    # 推导会静默塌成空集,第六族随之整族消失 —— 那正是 T8e 要消灭的那个病
    # (静默的覆盖缺口),所以它必须响亮失败而不是悄悄不跑。
    # `--prior` 只在 daily 分支被读,于是它是 **weekly** 侧新的"注册了却不读"
    # 的选项,必须进这张表 —— 不进就意味着 `if args.mode == "weekly" and
    # args.prior:` 这种零成本扳机从来没被第六族试过。daily 侧不变。
    # `--strict-brief` → `--no-strict-brief`(2026-08-14,dest 仍是
    # `strict_brief`)。weekly 分支照旧不读它,所以它换个名字继续待在这张表
    # 里 —— 这一格**不是**新增,是改名;真要少一格才该警觉。
    UNREAD_OPTIONS_EXPECTED = {
        "daily": (("--digest", True), ("--daily", True)),
        # `--decision-log` 与 `--prior` 同形:只在 daily 分支被读,于是它是
        # weekly 侧新的"注册了却不读"的选项,必须进这张表 —— 不进就意味着
        # `if args.mode == "weekly" and args.decision_log:` 这种零成本扳机
        # 从来没被第六族试过。日报模式把这两个收成"必给"之后,它们在
        # **weekly 侧仍然不读**,所以这一格一个字不改:任务要求的"周报侧
        # 不得静默忽略"走的就是这张表 + 第六族幂集,不是新加一条特例。
        "weekly": (("--brief", True), ("--no-strict-brief", False),
                   ("--prior", True), ("--decision-log", True)),
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
                           "--brief": "brief", "--prior": "d_report",
                           "--decision-log": "d_log"}

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
            # `--prior` 自 2026-08-14 起必给。它必须是**另一份**日报:拿
            # `d_report` 当自己的上一份会撞 PRIOR_PERIOD_BOILERPLATE,那是
            # 另一族码,会把本类"基线码集合逐字相等"的断言搅浑。
            "d_prior": make_report(prior_line=PRIOR_LINE_PREV),
            "brief": BRIEF,
            "d_multi": json.dumps(snap, ensure_ascii=False),
            "d_container": json.dumps(container_bad, ensure_ascii=False),
            "d_noderived": SNAP_TEXT,
            "d_legacy": snap_with_derived(schema_version=1, verdict=None),
            "w_report": WEEKLY_OK,
            "w_multi": json.dumps(wobj, ensure_ascii=False),
            "w_container": json.dumps(wcont, ensure_ascii=False),
            "d_log": DECISION_LOG,
        }
        cls.paths = {}
        for name, text in files.items():
            ext = ".md" if name.endswith(("report", "brief")) \
                else (".jsonl" if name.endswith("log") else ".json")
            p = os.path.join(t, name + ext)
            with open(p, "w", encoding="utf-8") as f:
                f.write(text)
            cls.paths[name] = p

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def _production_daily(self):
        """SKILL 第 5 步那一行的**完整形状**,逐字同形(见
        skills/fx-daily-report/SKILL.md 的
        `check_report.py … --brief … --prior … --decision-log …`)。

        V13 的教训是"生产命令行上的开关组合必须进 base"。2026-08-14 之后
        生产形状里**没有** `--strict-brief` 了 —— 强判定是默认,三个溯源入参
        是必给项,唯一的开关是 `--no-strict-brief`,它在 `_bases()` 里按取反
        逐条覆盖。
        """
        p = self.paths
        return [p["d_report"], p["d_multi"], "--brief", p["brief"],
                "--prior", p["d_prior"], "--decision-log", p["d_log"]]

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
    # 全量 `Ran 686 tests / OK / rc=0`,而 skills/fx-daily-report/SKILL.md:437
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

        前两组是**生产命令行 × 每个既有开关的取反**:日报两个开关
        (`--mode` 显式/缺省、`--no-strict-brief` 有/无)共 4 条;
        周报是 `--daily` 出现 2/1/0 次共 3 条。

        **`--brief` 有/无那一维已随"三个溯源入参必给"一起消失**(2026-08-14):
        不给 `--brief` 现在是 rc=2,base 自己就跑不出任何码 —— 与 weekly 那
        一维(往不读的位置参数里塞快照)消失的理由逐字相同。这不是放宽断言,
        是那条 argv 已经不再是合法输入;它守的东西(「少写一个参数 = 静默
        弱化」)现在由 `DailyModeRequiresTheStrongFormTest` 承接,并且守得
        更死:那里对**每一种漏法**都要求 rc=2,还要把校验器印出去的那条
        命令行原样跑一遍。
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
            for loose in (True, False):
                argv = self._production_daily()
                if use_mode:
                    argv += ["--mode", "daily"]
                if loose:
                    argv += ["--no-strict-brief"]
                out.append(("daily mode=%d loose=%d" % (use_mode, loose),
                            argv, None, self.DAILY_BASE_CODES, d_unread))
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
        def daily_with(snapshot):
            """生产形状,只换快照 —— 三个溯源入参一个都不许少(rc=2)。"""
            argv = self._production_daily()
            argv[1] = snapshot
            return argv

        out.append(("daily 容器坏", daily_with(p["d_container"]), None,
                    frozenset({"VERDICT_CONTAINER_MALFORMED"}), d_unread))
        out.append(("weekly 容器坏",
                    [p["w_report"], "--mode", "weekly", "--digest",
                     p["w_container"], "--daily", p["d_report"]], None,
                    frozenset({"VERDICT_CONTAINER_MALFORMED"}), w_unread))
        out.append(("daily 无 derived(只出降级声明)",
                    daily_with(p["d_noderived"]), None,
                    frozenset({"VERDICT_SKIPPED_NO_DERIVED"}), d_unread))
        out.append(("daily schema 过旧(只出降级声明)",
                    daily_with(p["d_legacy"]), None,
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


def verdict_notes(notes):
    """notes 里属于**结论句那一层**的声明条数。

    同一份 notes 由多层检查共用(结论句 / 判断环 / 跨期重复 …),每层各自
    出声。按前缀分层计数,才能让「本层恰好一条」这个断言继续承重 —— 用
    `len(notes)` 会让任何一层新增声明都把别层的测试打红,那种红是噪声,
    而消噪的最省事做法是把断言改成 `>= 1`,那才是真的放宽。
    """
    return len([n for n in notes if n.startswith("VERDICT_")])


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
        # 计数按 `VERDICT_` 前缀过滤,**不是放宽**:本条守的是「结论句这一层
        # 恰好出一条声明,不多不少」,该层多出一条照样红。判断环那一层有它
        # 自己的声明与自己的计数断言(JudgementRingSkipDeclarationTest),
        # 两层的声明本来就该同时出现在同一份 notes 里。
        self.assertEqual(verdict_notes(notes), 1, notes)
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
        self.assertEqual(verdict_notes(notes), 1, notes)   # 见上方计数口径说明

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
        self.assertEqual(verdict_notes(notes), 1, notes)   # 见上方计数口径说明

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

    def _run(self, tmp, report_text, snap_text):
        argv, _ = daily_files(tmp, report_text=report_text,
                              snapshot_text=snap_text)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = check_report.main(argv)
        return rc, buf.getvalue()

    def test_legacy_notice_printed_alongside_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc, out = self._run(tmp, make_report(),
                                snap_with_derived(schema_version=1,
                                                  verdict=None))
        self.assertEqual(rc, 0, out)
        self.assertIn("VERDICT_SKIPPED_LEGACY", out)
        self.assertIn("CHECK PASSED", out)

    def test_no_notice_when_schema_is_current(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc, out = self._run(tmp, report_quoting(DAILY_VERDICT),
                                snap_with_derived())
        self.assertEqual(rc, 0, out)
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
                self.assertEqual(verdict_notes(notes), 1, (bad, notes))
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
        self.assertEqual(verdict_notes(notes), 1, notes)   # 见上方计数口径说明
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
            argv, _ = daily_files(tmp)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = check_report.main(argv)
            out = buf.getvalue()
        self.assertEqual(rc, 0, out)
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
        """**生产形状 argv**(T8d):skills/fx-daily-report/SKILL.md:437 与
        README.md:129 那条命令行逐字同形,含 `--brief` / `--mode daily` /
        `--strict-brief`。

        此前这里是 `main([rp, sp])` —— 三个开关一个都不带。于是所有处置
        断言都跑在**非生产形状**上,`if args.strict_brief: <对调处置表>`
        这一行全量全绿(实测见 `assert_own_disposition`),而生产日报命令行
        每次都带 `--strict-brief`。
        """
        with tempfile.TemporaryDirectory() as tmp:
            argv, _ = daily_files(tmp, report_text=report,
                                  snapshot_text=snap_text,
                                  extra=("--mode", "daily"))
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = check_report.main(argv)
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
        # `--prior` / `--decision-log` 自 2026-08-14 起必给,daily 那一支的
        # argv 拼法因此多两对。它们与本类要测的三种扰动正交 —— 上一份日报
        # 用**另一句**的合规日报(同句会撞 PRIOR_PERIOD_BOILERPLATE)。
        cls.prior = os.path.join(cls.t, "prior.md")
        with open(cls.prior, "w", encoding="utf-8") as f:
            f.write(make_report(prior_line=PRIOR_LINE_PREV))
        cls.log = os.path.join(cls.t, "log.jsonl")
        with open(cls.log, "w", encoding="utf-8") as f:
            f.write(DECISION_LOG)
        # (标签, 报告正文, 附件正文, 附件扩展名, argv 拼法, **期望码集合**)
        # 最后一位是 T8d 补的:基线码集合不许由被测校验器自己算出来,
        # 否则整族少一个码时 `missing = base_codes - codes(out)` 恒空。
        cls.MODES = (
            ("daily", make_report(), json.dumps(snap, ensure_ascii=False),
             ".json", lambda rp, ap, bp: [rp, ap, "--brief", bp,
                                          "--prior", cls.prior,
                                          "--decision-log", cls.log,
                                          "--mode", "daily"],
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


# ---- PRIOR_PERIOD_* 的处置文案:**逐字钉死在这里**,不从被测模块取 ----
# 与 WANT_QUOTE_VERBATIM / WANT_SCRIPT_BUG_VERBATIM 同一形制:期望值若由被测
# 二进制自己提供(`check_report.DISPOSITION_PRIOR_PERIOD`),改文案永远不会红,
# 断言等于没写。改文案就必须同时改这里 —— 显式动作、进 diff。
WANT_PRIOR_PERIOD_DISPOSITION = ("处置:写明本期相对上期究竟哪里变了;"
                                 "若确无变化,写明为什么没变")


class PriorPeriodBoilerplateTest(unittest.TestCase):
    """ICD 203 第 7 条的机器强制:周期性产品必须说明本期判断相对上期有何
    变化,**且不得使用模板套话**。

    实测缺陷(调研报告 §依据②):三个币种的实际利率四天一字未变,却把同一句
    话写了四遍。跨期逐字重复是少数**能机械判定**的论证质量信号 —— 而"论证
    有没有深度"不能机械判定(IMF 实测评分器只按关键词与章节存在性打分),
    所以本轮只加这一条,不加第二条。

    三态在这里各有一条测试,因为三态**互为对方的静默失败形态**:
    未提供上一份 → 声明跳过(不是通过);当前缺该节 → 违规;上一份缺该节
    → 声明跳过(上一份可能是改造前的旧格式,不是当前这份报告的错)。
    """

    HEADING = "## 本期相对上期的变化"
    # 每句都以「。」收尾,且**句内不含任何句末标点**(。;!? 及其半角),
    # 于是"这一节有几句"在测试里是可数的确定值,不随切分实现的细节漂移。
    # 句内也不含数字:本类多处断言「除本码外零违规」,数字会引来
    # NUMBER_UNTRACEABLE,把断言的失败原因搅浑。
    S_USD = "- USD:实际利率一档由上期的偏紧转为中性,这是本期新出现的变化。"
    S_EUR = "- EUR:与上期一致而判断未变,没变的原因是欧央行例会尚未召开。"
    S_PHP = "- PHP:替代解释由外需走弱换成了资本流出。"
    S_THB = "- THB:关键假设不变,但翻转指标新增了旅游收入的月度读数。"
    S_PHP_ALT = "- PHP:替代解释仍是外需走弱,只是权重下调。"
    S_THB_ALT = "- THB:关键假设不变,翻转指标维持原样。"

    def _report(self, sentences):
        """一份**结构合规**的日报,尾部带上「本期相对上期的变化」节。

        `prior_line=None` 关掉 `make_report()` 自带的那一节 —— 本类要自己
        控制节内的句子,两节并存会撞 SECTION_AMBIGUOUS(那是另一族码)。
        """
        return (make_report(prior_line=None) + "\n\n" + self.HEADING + "\n"
                + "\n".join(sentences) + "\n")

    def _prior_period_codes(self, v):
        return [x for x in v if x.startswith("PRIOR_PERIOD")]

    def _check(self, cur_sentences, prior_sentences, notes=None):
        prior = (make_report(prior_line=None) if prior_sentences is None
                 else self._report(prior_sentences))
        return check_report.check_daily(
            self._report(cur_sentences), SNAP_TEXT, BRIEF,
            notes=notes, prior_text=prior)

    # ---- 三态之一:上一份日报没给 ----

    def _cli(self, cur_text, prior_text=None):
        """真 CLI(进程内 main),返回 (rc, stdout)。

        `prior_text=None` 在这里的含义是「上一份是改造前的**旧格式**」
        (没有该节),不是「没给上一份」—— 后者自 2026-08-14 起是 rc=2 的
        用法错误,由本类下面第一条与 DailyModeRequiresTheStrongFormTest 守。
        """
        with tempfile.TemporaryDirectory() as tmp:
            argv, _ = daily_files(
                tmp, report_text=cur_text,
                prior_text=(make_report(prior_line=None)
                            if prior_text is None else prior_text))
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = check_report.main(argv)
            return rc, buf.getvalue()

    def test_absent_prior_is_a_usage_error_not_a_skip(self):
        """**变异靶点①:未提供上一份时静默通过。**

        修前这一条测的是"缺席 → 打一条降级声明 + rc=0"。那一形态本身就是
        fail-open:**忘带参数与「这份确实没有上一期」在命令行上不可分辨**,
        而 rc=0 让 CI 与运维都看不见区别。2026-08-14 起 `--prior` 必给,
        缺席即 rc=2 —— 这条测试跟着改判据,**不保留那条无参数的宽松路径**。
        """
        with tempfile.TemporaryDirectory() as tmp:
            argv, _ = daily_files(
                tmp, report_text=self._report([self.S_USD, self.S_EUR]))
            i = argv.index("--prior")
            del argv[i:i + 2]
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), \
                    contextlib.redirect_stderr(err):
                rc = check_report.main(argv)
        self.assertEqual(rc, 2, out.getvalue() + err.getvalue())
        self.assertNotIn("CHECK PASSED", out.getvalue())
        self.assertIn("DAILY_REQUIRED_OPTION_MISSING", err.getvalue())

    def test_giving_prior_does_not_print_the_absent_declaration(self):
        """跳过声明不许在**真比对过**的那一次也照打 —— 否则它退化成噪声,
        读者读到它也不知道到底比没比。"""
        cur = self._report([self.S_USD, self.S_PHP])
        rc, out = self._cli(cur, prior_text=self._report([self.S_EUR,
                                                          self.S_THB]))
        self.assertEqual(rc, 0, out)
        self.assertNotIn("PRIOR_PERIOD_ABSENT_SKIPPED", out)
        self.assertIn("CHECK PASSED", out)

    # ---- 三态之二:上一份日报没有该节(改造前的旧格式)----

    def test_prior_without_the_section_is_declared_skipped_not_violated(self):
        """**变异靶点⑤:上一份缺该节时误判违规。**

        上一份可能是本次改造**之前**产出的旧格式日报,那不是当前这份报告的
        缺陷 —— 判它违规会让改造落地当天的第一份报告必红,而"必红"很快就会
        被人用 `--prior` 不传绕过,整条不变量随之作废。
        """
        notes = []
        v = self._check([self.S_USD, self.S_EUR], None, notes=notes)
        self.assertEqual(self._prior_period_codes(v), [])
        self.assertTrue(any(n.startswith("PRIOR_PERIOD_SKIPPED_NO_SECTION")
                            for n in notes), notes)

    def test_prior_without_the_section_still_prints_a_declaration_in_cli(self):
        """声明必须真的打到 stdout —— 只进 notes 而 main 不打印,与静默同效。"""
        rc, out = self._cli(self._report([self.S_USD]),
                            prior_text=make_report(prior_line=None))
        self.assertEqual(rc, 0, out)
        self.assertIn("PRIOR_PERIOD_SKIPPED_NO_SECTION", out)
        self.assertIn("CHECK PASSED", out)

    # ---- 三态之三:当前报告缺该节 ----

    def test_current_report_without_the_section_is_a_violation(self):
        """**变异靶点④:当前报告缺该节时静默跳过。**

        "整节删掉"是绕过本不变量**最省事**的一条路:没有该节就没有可比的句子,
        逐句比对天然零重复。所以它必须是违规,而不是第二种跳过。
        """
        v = check_report.check_daily(
            make_report(prior_line=None), SNAP_TEXT, BRIEF,
            prior_text=self._report([self.S_USD, self.S_EUR]))
        codes = self._prior_period_codes(v)
        self.assertEqual(len(codes), 1, codes)
        self.assertTrue(codes[0].startswith("PRIOR_PERIOD_SECTION_MISSING:"),
                        codes)
        self.assertTrue(codes[0].endswith(WANT_PRIOR_PERIOD_DISPOSITION),
                        codes)

    # ---- 判据本身:逐句、过半 ----

    def test_half_the_sentences_repeat_verbatim_while_the_section_differs(self):
        """**变异靶点②:比对整节而非逐句。**

        两节的**整段文本不相等**(后两句都改过),整节比对因此零命中;而四句
        里有两句一字不差 —— 那正是实测缺陷的形状(几个币种照抄上期,其余几个
        真的更新了)。断言里显式钉住"整节不相等",免得日后有人把 fixture 改成
        整节相同,让这条测试对整节比对也绿。
        """
        cur = [self.S_USD, self.S_EUR, self.S_PHP, self.S_THB]
        prior = [self.S_USD, self.S_EUR, self.S_PHP_ALT, self.S_THB_ALT]
        self.assertNotEqual("\n".join(cur), "\n".join(prior))
        codes = self._prior_period_codes(self._check(cur, prior))
        self.assertEqual(len(codes), 1, codes)
        self.assertTrue(codes[0].startswith("PRIOR_PERIOD_BOILERPLATE:"), codes)

    def test_below_half_repeated_passes(self):
        """**变异靶点③:阈值反向。**

        四句里只有一句照抄 —— 这是**正常**的周期性产品(某个币种确实没动)。
        判为违规会把整条不变量变成"每句都必须改字",而"每句都必须改字"逼出的
        正是套话。与上一条(恰好一半 → 违规)成对,把阈值两侧都钉住。
        """
        cur = [self.S_USD, self.S_EUR, self.S_PHP, self.S_THB]
        prior = [self.S_USD, self.S_PHP_ALT, self.S_THB_ALT]
        self.assertEqual(self._prior_period_codes(self._check(cur, prior)), [])

    def test_exactly_half_is_already_a_violation(self):
        """阈值取 `≥ 一半`(不是 `>`)。上一条守下界,这一条守边界点本身:
        `>` 会让"四句抄两句"这个**实测最常见**的形态整类逃掉。"""
        cur = [self.S_USD, self.S_EUR, self.S_PHP, self.S_THB]
        prior = [self.S_USD, self.S_EUR, self.S_PHP_ALT, self.S_THB_ALT]
        v = self._check(cur, prior)
        self.assertTrue(any("PRIOR_PERIOD_BOILERPLATE" in x for x in v), v)

    def test_a_single_repeated_sentence_is_a_violation(self):
        """只有一句时,该句相同即违规 —— minimal 体裁的币种在该节仍占一行,
        "整节就一句"是合法形态,不能因为"分母小"就白送。"""
        v = self._check([self.S_USD], [self.S_USD, self.S_PHP_ALT])
        self.assertTrue(any("PRIOR_PERIOD_BOILERPLATE" in x for x in v), v)

    def test_a_single_changed_sentence_passes(self):
        v = self._check([self.S_USD], [self.S_PHP_ALT, self.S_THB_ALT])
        self.assertEqual(self._prior_period_codes(v), [], v)

    # ---- 错误信息必须可操作 ----

    def test_violation_message_quotes_the_repeated_sentences_and_disposition(self):
        """"有 2 句重复"不可操作 —— 读者得自己去两份报告里对拍才知道是哪两句。
        原文 + 处置一起打出来,才是拿到就能改的东西。"""
        cur = [self.S_USD, self.S_EUR, self.S_PHP, self.S_THB]
        prior = [self.S_USD, self.S_EUR, self.S_PHP_ALT, self.S_THB_ALT]
        line = [x for x in self._check(cur, prior)
                if x.startswith("PRIOR_PERIOD_BOILERPLATE")][0]
        self.assertIn(self.S_USD, line)
        self.assertIn(self.S_EUR, line)
        self.assertNotIn(self.S_PHP, line)      # 没重复的句子不该被点名
        self.assertTrue(line.endswith(WANT_PRIOR_PERIOD_DISPOSITION), line)

    def test_cli_turns_a_boilerplate_section_red(self):
        """端到端:进程内断言全绿而真 CLI 放行,是本仓库栽过的形态。"""
        cur = [self.S_USD, self.S_EUR, self.S_PHP, self.S_THB]
        prior = [self.S_USD, self.S_EUR, self.S_PHP_ALT, self.S_THB_ALT]
        rc, out = self._cli(self._report(cur), prior_text=self._report(prior))
        self.assertEqual(rc, 1, out)
        self.assertIn("PRIOR_PERIOD_BOILERPLATE", out)
        self.assertIn("CHECK FAILED", out)


# ==================== 判断环三码(①②③)====================
#
# 三码的诚实标注见 scripts/check_report.py 里 check_judgement_ring 的
# docstring:① 与 ③ 是**存在性检查**,② 是**质量检查**。测试按这个分工写 ——
# ①③ 只断言"标签/数字出没出现",② 断言"两句之间的关系"。

RING_HEAD = ("**驱动**:CPI 同比 3.1,前值 3.4。\n"
             "**传导**:通胀回落 → 本地利差收窄 → 套息头寸减仓 → 汇率。\n"
             "**是否已反映**:参考价 60.843 贴近区间上沿。\n")
RING_OK = ("关键假设是 3.1 这一读数仍代表当前通胀;"
           "不成立时利差这条腿失效,该改按估值修复处理。"
           "替代解释:比索走弱是美元一端在统一定价"
           "(其翻转指标:同次定盘里泰铢同步升破 35.2)。"
           "翻转指标:参考价回落至 60.9 一侧(T+3)。")


def ring_body(ring=RING_OK):
    return RING_HEAD + "**分歧与判断**:" + ring


def ring_snap(modes=None, schema_version=1):
    """SNAP + 一份 `derived`。

    schema_version 取 1(存量结论句档)是**刻意**的:本组测试要隔离判断环这
    一层,不让 VERDICT_* 那一族的违规混进 `v` 里干扰断言。

    `modes` 往 `derived` 里塞一个 **body_plan 形状的 blob**。2026-08-14 之后
    校验器**不再读它** —— 这个入参因此不是开关,而是**反向靶点**:
    `JudgementRingHasNoExemptionPathTest` 拿它证明"快照里塞 mode=minimal 也
    豁免不了"。谁把体裁闸门改回来,那条用例立刻红。
    """
    snap = dict(SNAP)
    derived = {"schema_version": schema_version,
               "rates": {}, "real_rate": {}, "events": {}}
    if modes:
        derived["body_plan"] = {c: {"mode": mode} for c, mode in modes.items()}
    snap["derived"] = derived
    return json.dumps(snap, ensure_ascii=False)


def ring_check(ring=RING_OK, snap=None, notes=None, php_body=None):
    return check_report.check_daily(
        make_report(php_body=php_body or ring_body(ring)),
        snap if snap is not None else ring_snap(), BRIEF, notes=notes)


def ring_codes(violations, prefix):
    return [x for x in violations if x.startswith(prefix)]


class JudgementRingCompletenessTest(unittest.TestCase):
    """① `JUDGEMENT_RING_INCOMPLETE` —— **存在性检查**。

    只查三个标签串在不在该币种节里,不查标签后面写的是不是真的假设/解释/
    指标。这是它能给的全部保证,不得说成"已强制论证质量"。
    """

    def test_complete_ring_passes(self):
        self.assertEqual(ring_codes(ring_check(), "JUDGEMENT_RING_INCOMPLETE"), [])

    def test_missing_key_assumption_is_a_violation(self):
        """**变异靶点:三件缺一仍通过。**"""
        ring = ("本日方向未定。替代解释:走弱是美元一端在统一定价"
                "(其翻转指标:泰铢同步升破 35.2)。"
                "翻转指标:参考价回落至 60.9 一侧(T+3)。")
        line = ring_codes(ring_check(ring), "JUDGEMENT_RING_INCOMPLETE")
        self.assertEqual(len(line), 1, line)
        self.assertIn("关键假设", line[0])
        self.assertIn("PHP", line[0])
        self.assertNotIn("替代解释", line[0].split("缺")[-1].split(";")[0])

    def test_missing_alternative_explanation_is_a_violation(self):
        ring = ("关键假设是 3.1 这一读数仍代表当前通胀;不成立时利差这条腿失效。"
                "翻转指标:参考价回落至 60.9 一侧(T+3)。")
        line = ring_codes(ring_check(ring), "JUDGEMENT_RING_INCOMPLETE")
        self.assertEqual(len(line), 1, line)
        self.assertIn("替代解释", line[0])

    def test_missing_flip_indicator_is_a_violation(self):
        ring = ("关键假设是 3.1 这一读数仍代表当前通胀;不成立时利差这条腿失效。"
                "替代解释:比索走弱是美元一端在统一定价。")
        line = ring_codes(ring_check(ring), "JUDGEMENT_RING_INCOMPLETE")
        self.assertEqual(len(line), 1, line)
        self.assertIn("翻转指标", line[0])

    def test_all_three_missing_are_named_in_one_line(self):
        line = ring_codes(ring_check("本日维持原判。"),
                          "JUDGEMENT_RING_INCOMPLETE")
        self.assertEqual(len(line), 1, line)
        for want in ("关键假设", "替代解释", "翻转指标"):
            self.assertIn(want, line[0])

    def test_a_one_line_section_is_a_violation(self):
        """"只有一行"的币种节必红 —— 2026-08-14 起没有体裁豁免。

        (此处此前有一条 `test_minimal_section_is_exempt`,断言同一份一行
        正文在 `mode=minimal` 时**不**违规。那条豁免的依据"该节只准写一行"
        在真实产物上当场为假,已随豁免一起删除;反向靶点移到
        `JudgementRingHasNoExemptionPathTest`。)
        """
        v = ring_check(php_body="PHP:本日只写了一行,判断环一件都没写。")
        line = ring_codes(v, "JUDGEMENT_RING_INCOMPLETE")
        self.assertEqual(len(line), 1, v)
        self.assertIn("PHP", line[0])

    def test_violation_line_carries_the_disposition(self):
        line = ring_codes(ring_check("本日维持原判。"),
                          "JUDGEMENT_RING_INCOMPLETE")[0]
        self.assertTrue(line.endswith(check_report.DISPOSITION_RING), line)


class FlipIndicatorIsNotInvalidationRestatedTest(unittest.TestCase):
    """② `FLIP_INDICATOR_IS_INVALIDATION_RESTATED` —— **质量检查**。

    判据是同一节内**两句之间的关系**(去标点空白后逐字相同,或互为子串),
    不是"某物出没出现"。ICD 203:翻转指标是"什么出现就改判",失效条件是
    "什么没发生就作废",最省事的作弊写法是把后者换个说法当前者交差。

    诚实边界:它只做逐字/子串比较,**不做语义判断**。同义改写(把"收窄"
    写成"回落")绕得过去 —— 它挡的是最省事的那条路,不是语义等价。
    """

    def test_distinct_flip_and_invalidation_pass(self):
        v = ring_check()
        self.assertEqual(ring_codes(v, "FLIP_INDICATOR_IS_INVALIDATION_RESTATED"),
                         [], v)

    def test_invalidation_restated_as_flip_is_a_violation(self):
        """失效条件 ⊂ 翻转指标(实测最省事的作弊形态:原句加个 T+N)。
        **变异靶点:子串方向写反。**"""
        ring = ("关键假设是 3.1 这一读数仍代表当前通胀;不成立时利差收窄。"
                "替代解释:比索走弱是美元一端在统一定价"
                "(其翻转指标:泰铢同步升破 35.2)。"
                "翻转指标:利差收窄(T+3)。")
        line = ring_codes(ring_check(ring),
                          "FLIP_INDICATOR_IS_INVALIDATION_RESTATED")
        self.assertEqual(len(line), 1, line)

    def test_flip_restated_as_invalidation_is_a_violation(self):
        """反方向同样要红:翻转指标 ⊂ 失效条件。
        **变异靶点:子串方向写反**(只查一个方向时,本条或上一条必有一条活)。"""
        ring = ("关键假设是 3.1 这一读数仍代表当前通胀;"
                "不成立时利差收窄,并且该判断整条作废。"
                "替代解释:比索走弱是美元一端在统一定价"
                "(其翻转指标:泰铢同步升破 35.2)。"
                "翻转指标:利差收窄。")
        line = ring_codes(ring_check(ring),
                          "FLIP_INDICATOR_IS_INVALIDATION_RESTATED")
        self.assertEqual(len(line), 1, line)

    def test_only_punctuation_differs_is_a_violation(self):
        """"去除标点与空白后逐字相同" —— 换个标点不算改写。"""
        ring = ("关键假设是 3.1 这一读数仍代表当前通胀;不成立时,利差收窄!"
                "替代解释:比索走弱是美元一端在统一定价"
                "(其翻转指标:泰铢同步升破 35.2)。"
                "翻转指标: 利差 收窄。")
        line = ring_codes(ring_check(ring),
                          "FLIP_INDICATOR_IS_INVALIDATION_RESTATED")
        self.assertEqual(len(line), 1, line)

    def test_same_first_character_is_not_enough(self):
        """**变异靶点:只比首字符(或只比前 N 字)。**

        两句都以"利"开头、内容不同 —— 这是**正常**报告的常见形态(同一个
        可观测量的两种用法)。判为违规会把这条码变成噪声,而噪声码会被整体
        关掉,等于回到零强制。
        """
        ring = ("关键假设是 3.1 这一读数仍代表当前通胀;不成立时利差这条腿失效。"
                "替代解释:比索走弱是美元一端在统一定价"
                "(其翻转指标:泰铢同步升破 35.2)。"
                "翻转指标:利率升破 35.2(T+3)。")
        v = ring_check(ring)
        self.assertEqual(ring_codes(v, "FLIP_INDICATOR_IS_INVALIDATION_RESTATED"),
                         [], v)

    def test_violation_prints_both_sentences_verbatim(self):
        """"有一句重复"不可操作 —— 两句原文都得打出来,读者才知道改哪句。"""
        ring = ("关键假设是 3.1 这一读数仍代表当前通胀;不成立时利差收窄。"
                "替代解释:比索走弱是美元一端在统一定价"
                "(其翻转指标:泰铢同步升破 35.2)。"
                "翻转指标:利差收窄(T+3)。")
        line = ring_codes(ring_check(ring),
                          "FLIP_INDICATOR_IS_INVALIDATION_RESTATED")[0]
        self.assertIn("不成立时利差收窄。", line)
        self.assertIn("翻转指标:利差收窄(T+3)。", line)
        self.assertTrue(line.endswith(check_report.DISPOSITION_FLIP), line)

    def test_disposition_spells_out_the_semantic_difference(self):
        """处置必须写明二者的语义差别,而不是只说"重复了"。"""
        d = check_report.DISPOSITION_FLIP
        self.assertIn("出现", d)
        self.assertIn("没发生", d)

    def test_a_snapshot_body_plan_blob_cannot_switch_it_off(self):
        """此前这里是 `test_minimal_section_is_exempt`,拿一份**没有任何判断环
        标签**的一行正文断言 ② 不响 —— 而两侧都判不出载荷时 ② 本就不会响,
        那条用例对豁免有没有生效**零分辨力**。改成正向靶点:同一节写着
        改写自失效条件的翻转指标,快照里塞 `mode=minimal`,② 必须照样红。"""
        ring = ("关键假设是 3.1 这一读数仍代表当前通胀;不成立时利差收窄。"
                "替代解释:比索走弱是美元一端在统一定价"
                "(其翻转指标:泰铢同步升破 35.2)。"
                "翻转指标:利差收窄(T+3)。")
        v = ring_check(ring, snap=ring_snap(modes={"PHP": "minimal"}))
        self.assertTrue(
            ring_codes(v, "FLIP_INDICATOR_IS_INVALIDATION_RESTATED"), v)


class AssumptionAnchorTest(unittest.TestCase):
    """③ `ASSUMPTION_UNANCHORED` —— **存在性检查**。

    只查关键假设句里有没有出现**一个**落在既有 `NUMBER_UNTRACEABLE` 白名单
    里的数字 token。它保证不了那个数字和假设有关系(那是语义)。
    """

    def test_anchored_assumption_passes(self):
        self.assertEqual(ring_codes(ring_check(), "ASSUMPTION_UNANCHORED"), [])

    def test_assumption_without_any_number_is_a_violation(self):
        ring = ("关键假设是通胀读数仍代表当前水平;不成立时利差这条腿失效。"
                "替代解释:比索走弱是美元一端在统一定价"
                "(其翻转指标:泰铢同步升破 35.2)。"
                "翻转指标:参考价回落至 60.9 一侧。")
        line = ring_codes(ring_check(ring), "ASSUMPTION_UNANCHORED")
        self.assertEqual(len(line), 1, line)
        self.assertIn("PHP", line[0])
        self.assertIn("关键假设是通胀读数仍代表当前水平;", line[0])
        self.assertTrue(line[0].endswith(check_report.DISPOSITION_ANCHOR), line)

    def test_untraceable_number_does_not_anchor(self):
        """假设句里那个数必须是**可溯源**的。写一个快照里没有的数,既触发既有
        NUMBER_UNTRACEABLE,也不算锚 —— 否则"编一个数"就是最省事的过关方式。"""
        ring = ("关键假设是 99.99 这一读数仍代表当前通胀;不成立时利差这条腿失效。"
                "替代解释:比索走弱是美元一端在统一定价"
                "(其翻转指标:泰铢同步升破 35.2)。"
                "翻转指标:参考价回落至 60.9 一侧(T+3)。")
        v = ring_check(ring)
        self.assertTrue(ring_codes(v, "ASSUMPTION_UNANCHORED"), v)
        self.assertTrue(ring_codes(v, "NUMBER_UNTRACEABLE"), v)

    def test_anchor_requirement_never_demands_a_threshold(self):
        """**变异靶点:③ 要求阈值(F1 冲突)。**

        阈值按定义是尚未发生的前瞻价位,不在快照里 —— 要求它必然触发
        `NUMBER_UNTRACEABLE`(本仓四个月前撞过,判据见 check_report.py 里
        `allowed` 的构成:快照 ∪ 要点表 ∪ 小整数)。所以本条钉两件事:

        1. 只带**当前值**、不带任何前瞻价位的关键假设,必须**同时**过
           ASSUMPTION_UNANCHORED 与 NUMBER_UNTRACEABLE;
        2. 反过来,把前瞻价位写进去必然触发 NUMBER_UNTRACEABLE ——
           即"要求阈值"是自相矛盾的,不是风格偏好。
        """
        ring = ("关键假设是 3.1 这一读数仍代表当前通胀;不成立时利差这条腿失效。"
                "替代解释:比索走弱是美元一端在统一定价"
                "(其翻转指标:泰铢同步升破 35.2)。"
                "翻转指标:参考价回落至 60.9 一侧(T+3)。")
        v = ring_check(ring)
        self.assertEqual(ring_codes(v, "ASSUMPTION_UNANCHORED"), [], v)
        self.assertEqual(ring_codes(v, "NUMBER_UNTRACEABLE"), [], v)

        threshold = ring.replace("3.1 这一读数", "61.5 这一前瞻价位")
        v2 = ring_check(threshold)
        self.assertTrue(ring_codes(v2, "NUMBER_UNTRACEABLE"), v2)

    def test_small_integer_counts_as_anchor(self):
        """判据逐字照 `allowed`(含 ALLOWED_SMALL)。这是本码的**已知弱点**,
        写成测试是为了让它可见、可改,而不是让它藏在实现里。"""
        ring = ("关键假设是这 3 条依据仍成立;不成立时利差这条腿失效。"
                "替代解释:比索走弱是美元一端在统一定价"
                "(其翻转指标:泰铢同步升破 35.2)。"
                "翻转指标:参考价回落至 60.9 一侧(T+3)。")
        self.assertEqual(ring_codes(ring_check(ring), "ASSUMPTION_UNANCHORED"), [])

    def test_a_snapshot_body_plan_blob_cannot_switch_it_off(self):
        """理由同 ② 那一条:旧的 `test_minimal_section_is_exempt` 用一行没有
        「关键假设」标签的正文断言 ③ 不响,对豁免零分辨力。改成正向靶点。"""
        ring = ("关键假设是通胀读数仍代表当前水平;不成立时利差这条腿失效。"
                "替代解释:比索走弱是美元一端在统一定价"
                "(其翻转指标:泰铢同步升破 35.2)。"
                "翻转指标:参考价回落至 60.9 一侧。")
        v = ring_check(ring, snap=ring_snap(modes={"PHP": "minimal"}))
        self.assertTrue(ring_codes(v, "ASSUMPTION_UNANCHORED"), v)


class JudgementRingReceiptTest(unittest.TestCase):
    """回执必须出声,且必须与"覆盖到的节数"相等。

    ---- 这个类此前是 `JudgementRingSkipDeclarationTest` ----
    它守的是三条跳过声明各自出声(无 body_plan / mode 不可判 / minimal 豁免)。
    三条跳过路径在 2026-08-14 一并删除:`MINIMAL_EXEMPT` 的依据"该节只准写
    一行"在真实产物上当场为假(reports/daily/2026-08-10.md 那四节各写着
    270–322 中文字的完整四环),另外两条只是同一道体裁闸门的另外两态。
    「跳过与通过在输出上不可分辨」这条原则**没有放弃**,而是换了实现:
    既然不再有跳过态,就用一条**正向回执**把"覆盖 N 节、查了 N 节"打出来。
    """

    RING_LESS = "**驱动**:无。**分歧与判断**:维持原判。"

    def test_a_legacy_snapshot_without_derived_is_checked_not_skipped(self):
        """**变异靶点:体裁闸门以"存量快照"的名义复活。**

        存量快照连 derived 节都没有 —— 而判断环 ①② 一个快照字段都不读,
        没有任何理由因此不查。
        """
        notes = []
        v = check_report.check_daily(make_report(php_body=self.RING_LESS),
                                     SNAP_TEXT, BRIEF, notes=notes)
        self.assertTrue(ring_codes(v, "JUDGEMENT_RING_INCOMPLETE"), v)
        self.assertTrue([n for n in notes
                         if n.startswith("JUDGEMENT_RING_CHECKED")], notes)

    def test_the_receipt_is_printed_exactly_once(self):
        notes = []
        check_report.check_daily(make_report(php_body=ring_body()),
                                 ring_snap(), BRIEF, notes=notes)
        line = [n for n in notes if n.startswith("JUDGEMENT_RING_CHECKED")]
        self.assertEqual(len(line), 1, notes)

    def test_no_skip_note_survives_in_the_notes(self):
        """反面:本层不许再出现任何 `JUDGEMENT_RING_SKIPPED*` 声明。"""
        notes = []
        check_report.check_daily(make_report(php_body=ring_body()),
                                 ring_snap(), BRIEF, notes=notes)
        self.assertEqual([n for n in notes
                          if n.startswith("JUDGEMENT_RING_SKIPPED")], [], notes)

    def test_cli_prints_the_receipt_alongside_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            argv, _ = daily_files(tmp)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = check_report.main(argv)
            out = buf.getvalue()
        self.assertEqual(rc, 0, out)
        self.assertIn("JUDGEMENT_RING_CHECKED: 5/5", out)
        self.assertIn("CHECK PASSED", out)

    def test_cli_turns_a_one_line_section_red_on_a_legacy_snapshot(self):
        """端到端:进程内全绿而真 CLI 放行,是本仓库栽过的形态。
        快照用默认的 `SNAP_TEXT`(无 derived)—— 正是此前整份跳过的那一态。"""
        with tempfile.TemporaryDirectory() as tmp:
            argv, _ = daily_files(
                tmp, report_text=make_report(php_body=self.RING_LESS))
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = check_report.main(argv)
            out = buf.getvalue()
        self.assertEqual(rc, 1, out)
        self.assertIn("JUDGEMENT_RING_INCOMPLETE", out)

    def test_cli_turns_an_incomplete_ring_red(self):
        """端到端:进程内全绿而真 CLI 放行,是本仓库栽过的形态。"""
        with tempfile.TemporaryDirectory() as tmp:
            argv, _ = daily_files(
                tmp, report_text=make_report(php_body=self.RING_LESS),
                snapshot_text=ring_snap())
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = check_report.main(argv)
            out = buf.getvalue()
        self.assertEqual(rc, 1, out)
        self.assertIn("JUDGEMENT_RING_INCOMPLETE", out)


class JudgementRingHonestyLabelTest(unittest.TestCase):
    """诚实标注不是散文承诺 —— 三个码各自的性质必须写在源码里,且不得三条
    都写成"质量检查"。调研实测:IMF 评分器停在存在性那一层,我们刚照出自己
    也停在那一层;把存在性说成质量,就是复现同一个病。
    """

    def setUp(self):
        self.doc = check_report.check_judgement_ring.__doc__ or ""

    def test_each_code_is_labelled_in_the_docstring(self):
        for code in ("JUDGEMENT_RING_INCOMPLETE",
                     "FLIP_INDICATOR_IS_INVALIDATION_RESTATED",
                     "ASSUMPTION_UNANCHORED"):
            self.assertIn(code, self.doc, code)
        self.assertIn("存在性检查", self.doc)
        self.assertIn("质量检查", self.doc)

    def test_not_all_three_are_claimed_to_be_quality_checks(self):
        """至少两条必须自称存在性 —— 三条全写"质量检查"就是那个病本身。"""
        self.assertGreaterEqual(self.doc.count("存在性检查"), 2, self.doc)


# ==================== 判断环没有任何豁免路径(2026-08-14)==================
#
# 修的缺陷:`JUDGEMENT_RING_MINIMAL_EXEMPT` 这条豁免**声称的依据是假的**。
# 它打印「该节只准写一行,本就没有判断环」,而 reports/daily/2026-08-10.md 的
# USD/PHP/THB/BRL 四节实测各写着 270–322 中文字的完整四环 —— 依据当场不成立,
# 而校验器从不核对它。豁免于是只是「这四节不查」的另一种说法。
# 处置不是"把豁免执行起来"(执行它等于把 `derived.body_plan.<币种>.line` 那句
# 「本日无可用增量」写进正文,违反正文禁词那条更高的规则),而是**删掉豁免
# 本身**:每个被报告覆盖的币种节都必须有完整判断环,快照里没有任何东西能免它。


class JudgementRingHasNoExemptionPathTest(unittest.TestCase):
    """**变异靶点:快照里的某个字段又一次成了判断环的豁免闸门。**

    三条已删的码(`MINIMAL_EXEMPT` / `SKIPPED_NO_MODE` / `SKIPPED_NO_BODY_PLAN`)
    全部以「快照说这一节不用查」为形态。这一类只要还剩一条,判断环就仍然
    可以对着一份写满四环的报告一节都不查,而 stdout 上只有一行看不出真假的
    声明。**判据因此是"覆盖到的节 = 查过的节",没有第三态。**
    """

    ONE_LINE = "PHP:本日无可用增量,不更新判断;详见附录 A。"

    def test_a_one_line_section_is_a_violation_whatever_the_snapshot_says(self):
        """快照里塞 `body_plan.PHP.mode = minimal` 也豁免不了 —— 这正是被删的
        那条路径的形状,留一条用例把它钉死在"再也不生效"上。"""
        v = ring_check(php_body=self.ONE_LINE,
                       snap=ring_snap(modes={"PHP": "minimal"}))
        line = ring_codes(v, "JUDGEMENT_RING_INCOMPLETE")
        self.assertEqual(len(line), 1, v)
        self.assertIn("PHP", line[0])

    def test_a_legacy_snapshot_without_derived_is_still_checked(self):
        """判断环是**报告结构**的要求,与快照新旧无关:①② 一个快照字段都
        不读,③ 读的是 `allowed`(存量快照照样建得起来)。"""
        v = check_report.check_daily(make_report(php_body=self.ONE_LINE),
                                     SNAP_TEXT, BRIEF)
        self.assertTrue(ring_codes(v, "JUDGEMENT_RING_INCOMPLETE"), v)

    def test_the_three_exemption_codes_are_no_longer_emitted(self):
        """判据取 `_emitted_codes`(AST 里**被打印出去的**码),不是"源码里
        出现过这个词":后者会连带禁止在注释里说明"这条为什么被删",而删除
        理由正是最该留在源码里的东西。"""
        emitted = _emitted_codes(check_report.__file__)
        for code in ("JUDGEMENT_RING_MINIMAL_EXEMPT",
                     "JUDGEMENT_RING_SKIPPED_NO_MODE",
                     "JUDGEMENT_RING_SKIPPED_NO_BODY_PLAN"):
            self.assertNotIn(code, emitted, code)

    def test_the_checker_declares_how_many_sections_it_checked(self):
        """删掉三条跳过声明之后,「这一层跑没跑」在 stdout 上就没有痕迹了。
        补一条**正向回执**:它不是豁免,是"覆盖 N 节、查了 N 节"的计数,
        本轮的关键指标(五份日报 21 → 25)直接从它数出来。"""
        notes = []
        check_report.check_daily(make_report(php_body=ring_body()),
                                 SNAP_TEXT, BRIEF, notes=notes)
        line = [n for n in notes if n.startswith("JUDGEMENT_RING_CHECKED")]
        self.assertEqual(len(line), 1, notes)
        self.assertIn("5/5", line[0])

    def test_the_receipt_counts_only_the_covered_sections(self):
        """回执的分母是**覆盖到的**币种,不是 CURRENCIES 常量 —— 写死 5
        会在缺节那一天谎报"全查过"。"""
        notes = []
        check_report.check_daily(make_report(missing="泰铢",
                                             php_body=ring_body()),
                                 SNAP_TEXT, BRIEF, notes=notes)
        line = [n for n in notes if n.startswith("JUDGEMENT_RING_CHECKED")][0]
        self.assertIn("4/4", line)


class RealDailyReportsGetEveryCoveredSectionCheckedTest(unittest.TestCase):
    """真实产物上的关键指标,先跑后抄:五份日报 × 5 个币种节 = 25 节全查。

    此前实测 21 —— reports/daily/2026-08-10.md 的四节被 `MINIMAL_EXEMPT`
    整节跳过。这一类走 `check_daily` 这个**生产入口**,不自己拼
    `check_judgement_ring` 的入参。
    """

    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DATES = ("2026-08-10", "2026-08-11", "2026-08-12", "2026-08-13",
             "2026-08-14")

    def _notes(self, date_str):
        notes = []
        check_report.check_daily(
            self._read("reports", "daily", date_str + ".md"),
            self._read("data", date_str + ".json"),
            self._read("briefs", date_str + "-brief.md"),
            notes=notes)
        return notes

    def _read(self, *parts):
        with open(os.path.join(self.ROOT, *parts), encoding="utf-8") as f:
            return f.read()

    def test_twenty_five_sections_are_checked_across_the_five_reports(self):
        total = 0
        for date_str in self.DATES:
            with self.subTest(date=date_str):
                line = [n for n in self._notes(date_str)
                        if n.startswith("JUDGEMENT_RING_CHECKED")]
                self.assertEqual(len(line), 1, date_str)
                self.assertIn("5/5", line[0])
                total += 5
        self.assertEqual(total, 25)

    def test_no_exemption_and_no_unreachable_declaration_survives(self):
        """`FLIP_INDICATOR_CHECK_UNREACHABLE` 一并钉住:② 判不出失效条件句
        时整条不执行,而那与"比过了、没重复"在 rc 上不可分辨。"""
        for date_str in self.DATES:
            with self.subTest(date=date_str):
                for n in self._notes(date_str):
                    self.assertFalse(
                        n.startswith("JUDGEMENT_RING_MINIMAL_EXEMPT")
                        or n.startswith("FLIP_INDICATOR_CHECK_UNREACHABLE"),
                        "%s:%s" % (date_str, n))


# ==================== 数字的**归属**:两条映射级检查 ====================
#
# 既有的 `NUMBER_UNTRACEABLE` 判据是 `allowed = numbers_in(snapshot) |
# numbers_in(brief) | ALLOWED_SMALL` 的**集合成员**判定(check_report.py 里
# `allowed` 的那三行),然后做集合差。它是**无序词袋**:把美元的数字写进
# 雷亚尔那一节,两边都在 `allowed` 里,校验器逐字放行。
# 这两条码补的是「同一个数在不同位置之间的**关系**」,不是「某物有没有出现」,
# 因此两条**都是质量检查**(诚实标注见 check_report.py 的两个 docstring)。
#
# ---- 共享池的定义在测试里**逐元素冻结**,与 DISPOSITION_* 同规格 ----
# "其余都算共享"等于没有约束。凡改这几行常量就必须改这里 —— 显式动作、进 diff。

MAP_SNAP = {
    "date": "2026-08-10",
    "run_at": "2026-08-10T04:56:51+00:00",
    "schema_version": 1,
    "rates": {"PHP": {"primary": 60.843, "prev_primary": 60.9},
              "THB": {"primary": 35.2}, "BRL": {"primary": 5.43},
              "EUR": {"primary": 0.921}},
    "macro": [{"economy": "PH", "indicator": "CPI 同比", "value": 3.1,
               "prev": 3.4, "period": "2026-07"},
              {"economy": "US", "indicator": "政策利率", "value": 4.25,
               "period": "2026-08"}],
    "events": {}, "calendar_hits": [], "gaps": [],
    "meta": {"caps": {"official_daily": 3}},
    "derived": {"schema_version": 1, "rates": {}, "events": {},
                "real_rate": {"US": {"value": 0.26}, "PH": {"value": -1.613},
                              "TH": {"value": -1.42}, "EA": {"value": -0.499},
                              "BR": {"value": 9.359}}},
}
MAP_SNAP_TEXT = json.dumps(MAP_SNAP, ensure_ascii=False)
# 要点表按币种分节(生产要点表逐字如此,见 briefs/2026-08-14-brief.md),
# 外加一个**显式的**跨币种块 —— 后者是共享池的两个来源之一。
MAP_BRIEF = "\n".join([
    "# 要点表 2026-08-10",
    "",
    "## 跨币种共同主线",
    "- 四盘同侧移动,统一推力候选值 0.4321",
    "",
    "## USD",
    "- 派生指标:实际利率 0.26(政策利率 4.25)",
    "",
    "## EUR",
    "- 汇率变动:primary 0.921;实际利率 -0.499",
    "",
    "## PHP",
    "- 汇率变动:primary 60.843,prev 60.9;CPI 3.1 前值 3.4;实际利率 -1.613",
    "",
    "## THB",
    "- 汇率变动:primary 35.2;实际利率 -1.42",
    "",
    "## BRL",
    "- 汇率变动:primary 5.43;实际利率 9.359",
    "",
])
MAP_BODIES = {
    "USD": "**驱动**:政策利率 4.25,实际利率 0.26。",
    "EUR": "**驱动**:参考价 0.921,实际利率 -0.499。",
    "PHP": "**驱动**:参考价 60.843(前值 60.9),CPI 3.1 前值 3.4,实际利率 -1.613。",
    "THB": "**驱动**:参考价 35.2,实际利率 -1.42。",
    "BRL": "**驱动**:参考价 5.43,实际利率 9.359。",
}
MAP_HEADINGS = (("USD", "美元(USD)"), ("EUR", "欧元(EUR)"),
                ("PHP", "菲律宾比索(PHP)"), ("THB", "泰铢(THB)"),
                ("BRL", "巴西雷亚尔(BRL)"))


def map_report(bodies=None, summary=None, quick="| 币种 | 方向 |\n| --- | --- |",
               review="- 首次运行,无历史观点可复盘", gaps="无", extra=None,
               prior_line=PRIOR_LINE_CUR):
    b = dict(MAP_BODIES)
    b.update(bodies or {})
    lines = ["# 外汇日报 2026-08-10", "", "## 执行摘要"]
    lines += summary if summary is not None else ["- 本日无跨币种主线可归纳。"]
    for code, heading in MAP_HEADINGS:
        lines += ["", "## " + heading, b[code]]
    lines += ["", "## 速览", quick]
    lines += ["", "## 昨日观点复盘", review]
    lines += ["", "## 数据缺漏", gaps]
    if prior_line:
        # 与 make_report() 同规矩:`--prior` 必给之后,「本期相对上期的变化」
        # 是每份合规日报的必备节,少了它走 CLI 的断言测的就是一份不合规报告
        lines += ["", "## 本期相对上期的变化", prior_line]
    if extra:
        lines += ["", "## 附录 B:出处", extra]
    return "\n".join(lines)


def map_check(bodies=None, notes=None, snap=None, brief=None, **kw):
    return check_report.check_daily(
        map_report(bodies=bodies, **kw),
        MAP_SNAP_TEXT if snap is None else snap,
        MAP_BRIEF if brief is None else brief, notes=notes)


def codes_of(violations, prefix):
    return [x for x in violations if x.startswith(prefix + ":")]


class NumberSectionMappingTest(unittest.TestCase):
    """`NUMBER_WRONG_SECTION` —— **质量检查**(映射级)。

    判据是「这个数出自**哪个**币种的快照切片」对上「它写在**哪个**币种节」,
    是两个位置之间的关系,不是某个 token 在不在一个大词袋里。
    """

    def test_clean_report_passes(self):
        self.assertEqual(codes_of(map_check(), "NUMBER_WRONG_SECTION"), [])

    def test_usd_number_in_the_brl_section_is_a_violation(self):
        """缺陷原文:**把美元的数字写进雷亚尔那一节,校验器放行**。

        4.25 是 macro 里 economy=US 的读数,只属于 USD 切片;写进雷亚尔节、
        且该节没有点名美元 —— 既有的 NUMBER_UNTRACEABLE 对它完全不敏感
        (4.25 就在快照里)。
        """
        v = map_check({"BRL": "**驱动**:参考价 5.43,另有 4.25 这一档。"})
        self.assertEqual(codes_of(v, "NUMBER_UNTRACEABLE"), [], v)
        line = codes_of(v, "NUMBER_WRONG_SECTION")
        self.assertEqual(len(line), 1, v)
        self.assertIn("BRL", line[0])
        self.assertIn("4.25", line[0])
        self.assertIn("USD", line[0])

    def test_naming_the_other_currency_licenses_its_numbers(self):
        """**归属的判定单位是「节」**(诚实边界,不是"同一句"）。

        跨币种比较是本仓报告的正常写法(替代解释环逐条如此),点名即放行。
        这一条同时是**误报的下界**:收紧到「同一句必须点名」会把
        reports/daily/2026-08-10.md 的美元节整段打红(实测 15 条)。
        """
        v = map_check({"BRL": "**驱动**:参考价 5.43;美元一端政策利率 4.25 未变。"})
        self.assertEqual(codes_of(v, "NUMBER_WRONG_SECTION"), [], v)

    def test_shared_pool_is_not_everything_else(self):
        """**变异靶点:共享池写成「其余都算共享」。**

        60.843 在快照里、在要点表里、也在 `allowed` 里 —— 唯独不属于泰铢。
        共享池若退化成"不属于本币种的都算共享",这一条不会红。
        """
        v = map_check({"THB": "**驱动**:参考价 35.2,另一档 60.843。"})
        line = codes_of(v, "NUMBER_WRONG_SECTION")
        self.assertEqual(len(line), 1, v)
        self.assertIn("60.843", line[0])
        self.assertIn("PHP", line[0])

    def test_shared_pool_never_contains_the_currency_keyed_containers(self):
        """同一个变异的**结构侧**:共享池的来源清单里不得出现按币种/经济体
        分键的容器(rates / events / macro / derived)—— 放进去就等于
        "其余都算共享"。"""
        for key in ("rates", "events", "macro", "derived"):
            self.assertNotIn(key, check_report.SHARED_SNAPSHOT_KEYS, key)

    def test_every_currency_section_is_checked_not_just_the_first(self):
        """**变异靶点:只查第一个币种节。**

        五节各塞一个别人的数,必须五条全红、且五个币种都被点名。
        """
        v = map_check({"USD": MAP_BODIES["USD"] + "另有 0.921 一档。",
                       "EUR": MAP_BODIES["EUR"] + "另有 60.843 一档。",
                       "PHP": MAP_BODIES["PHP"] + "另有 35.2 一档。",
                       "THB": MAP_BODIES["THB"] + "另有 5.43 一档。",
                       "BRL": MAP_BODIES["BRL"] + "另有 4.25 一档。"})
        lines = codes_of(v, "NUMBER_WRONG_SECTION")
        self.assertEqual(len(lines), 5, v)
        named = {c for c in check_report.CURRENCIES
                 for ln in lines if ln.startswith("NUMBER_WRONG_SECTION: %s " % c)}
        self.assertEqual(named, set(check_report.CURRENCIES), lines)

    def test_the_explicit_cross_currency_pool_licenses_a_number_anywhere(self):
        """共享池的第一个来源:要点表里**显式的**跨币种块。"""
        v = map_check({"THB": MAP_BODIES["THB"] + "统一推力候选值 0.4321。"})
        self.assertEqual(codes_of(v, "NUMBER_WRONG_SECTION"), [], v)

    def test_the_shared_snapshot_keys_license_a_number_anywhere(self):
        """共享池的第二个来源:快照里**不按币种分键**的顶层字段。"""
        v = map_check({"THB": MAP_BODIES["THB"] + "当日公告上限 3 条。"},
                      snap=json.dumps(dict(MAP_SNAP, meta={"caps": {
                          "official_daily": 3, "gnews_records": 99}}),
                          ensure_ascii=False))
        self.assertEqual(codes_of(v, "NUMBER_WRONG_SECTION"), [], v)

    def test_small_integers_are_never_mapped(self):
        """**变异靶点:把 ALLOWED_SMALL 也纳入映射约束。**

        序数/条数/月份类小整数没有币种归属,纳进来会把每个"第 3 条""T+3"
        全打红。ALLOWED_SMALL 必须整体在共享池里。
        """
        v = map_check({"THB": MAP_BODIES["THB"] + "这是本节第 7 条依据,时限 T+3。"})
        self.assertEqual(codes_of(v, "NUMBER_WRONG_SECTION"), [], v)
        self.assertTrue(check_report.ALLOWED_SMALL
                        <= check_report.shared_number_pool(MAP_SNAP, MAP_BRIEF))

    def test_untraceable_numbers_are_left_to_the_existing_code(self):
        """同一个 token 不得同时吃两条违规 —— 编造的数由
        `NUMBER_UNTRACEABLE` 管,本码只看**可溯源**的那些。"""
        v = map_check({"THB": MAP_BODIES["THB"] + "另有 77.77 一档。"})
        self.assertTrue(codes_of(v, "NUMBER_UNTRACEABLE"), v)
        self.assertEqual(codes_of(v, "NUMBER_WRONG_SECTION"), [], v)

    def test_non_currency_sections_are_not_constrained(self):
        """执行摘要 / 速览 / 复盘 / 缺漏节天然跨币种,不受本码约束。"""
        v = map_check(summary=["- 四盘:0.921、60.843、35.2、5.43、4.25。"],
                      quick="| USD | 4.25 | 0.921 | 60.843 | 35.2 | 5.43 |",
                      review="- 复盘:0.921、60.843、35.2、5.43、4.25 均未更新")
        self.assertEqual(codes_of(v, "NUMBER_WRONG_SECTION"), [], v)

    def test_currency_without_any_snapshot_slice_is_skipped_and_declared(self):
        """三态之三:该币种在快照里一个切片都没有(USD 本就没有 rates 条目;
        这里连 macro/real_rate/events 一并拿掉)—— 判不了归属就不判,
        但必须留下一行。「跳过」与「通过」在输出上不可分辨,正是这一族
        检查要消灭的形态。"""
        snap = json.loads(MAP_SNAP_TEXT)
        snap["macro"] = [m for m in snap["macro"] if m["economy"] != "US"]
        del snap["derived"]["real_rate"]["US"]
        notes = []
        v = map_check({"USD": "**驱动**:另有 60.843 一档。"}, notes=notes,
                      snap=json.dumps(snap, ensure_ascii=False))
        self.assertEqual(codes_of(v, "NUMBER_WRONG_SECTION"), [], v)
        line = [n for n in notes
                if n.startswith("NUMBER_WRONG_SECTION_SKIPPED_NO_SLICE")]
        self.assertEqual(len(line), 1, notes)
        self.assertIn("USD", line[0])

    def test_no_skip_note_when_every_covered_currency_had_a_slice(self):
        """反面:该查的都查了就不许再喊跳过,否则声明本身变成噪声。"""
        notes = []
        map_check(notes=notes)
        self.assertEqual([n for n in notes
                          if n.startswith("NUMBER_WRONG_SECTION_SKIPPED")],
                         [], notes)

    def test_unattributable_macro_rows_are_pooled_and_declared(self):
        """存量快照的 macro 条目没有 `economy`(tests 里的 SNAP 逐字如此)。
        判不了归属的行并入共享池 —— 但这等于给报告开了一条豁免,必须出声。"""
        snap = json.loads(MAP_SNAP_TEXT)
        for m in snap["macro"]:
            del m["economy"]
        notes = []
        v = map_check({"THB": MAP_BODIES["THB"] + "另有 3.1 一档。"}, notes=notes,
                      snap=json.dumps(snap, ensure_ascii=False))
        self.assertEqual(codes_of(v, "NUMBER_WRONG_SECTION"), [], v)
        line = [n for n in notes
                if n.startswith("NUMBER_WRONG_SECTION_MACRO_UNATTRIBUTED")]
        self.assertEqual(len(line), 1, notes)
        self.assertIn("2", line[0])

    def test_violation_line_carries_the_disposition(self):
        line = codes_of(map_check({"BRL": MAP_BODIES["BRL"] + "另有 4.25。"}),
                        "NUMBER_WRONG_SECTION")[0]
        self.assertTrue(line.endswith(check_report.DISPOSITION_WRONG_SECTION),
                        line)

    def test_cli_turns_a_wrong_section_number_red(self):
        """端到端:进程内全绿而真 CLI 放行,是本仓库栽过的形态。"""
        with tempfile.TemporaryDirectory() as tmp:
            argv, _ = daily_files(
                tmp, report_text=map_report({"BRL": MAP_BODIES["BRL"]
                                             + "另有 4.25。"}),
                snapshot_text=MAP_SNAP_TEXT, brief_text=MAP_BRIEF,
                prior_text=map_report(prior_line=PRIOR_LINE_PREV),
                extra=("--mode", "daily"))
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = check_report.main(argv)
            out = buf.getvalue()
        self.assertEqual(rc, 1, out)
        self.assertIn("NUMBER_WRONG_SECTION", out)


class SummaryNumbersAreInTheBodyTest(unittest.TestCase):
    """`SUMMARY_NUMBER_NOT_IN_BODY` —— **质量检查**(一致性级)。

    移植自 econstack 被删版本的 A1 检查项,逐字:
    `| A1 | Do all numbers in the executive summary match the tables? | RED |`
    """

    def test_summary_numbers_present_in_the_body_pass(self):
        v = map_check(summary=["- 比索参考价 60.843 未变。"])
        self.assertEqual(codes_of(v, "SUMMARY_NUMBER_NOT_IN_BODY"), [], v)

    def test_summary_only_number_is_a_violation(self):
        """摘要里那个 0.4321 只在要点表的跨币种块里有,正文一处都没写 ——
        既有的 NUMBER_UNTRACEABLE 放行(它在 `allowed` 里)。"""
        v = map_check(summary=["- 统一推力候选值 0.4321。"])
        self.assertEqual(codes_of(v, "NUMBER_UNTRACEABLE"), [], v)
        line = codes_of(v, "SUMMARY_NUMBER_NOT_IN_BODY")
        self.assertEqual(len(line), 1, v)
        self.assertIn("0.4321", line[0])

    def test_direction_is_summary_into_body_not_the_reverse(self):
        """**变异靶点:方向反过来(变成正文数字必须进摘要)。**

        正文有一堆摘要没写的数(本来就该如此,摘要只有 6 条),
        反向实现会把每一份正常报告打成几十条红。
        """
        v = map_check(summary=["- 本日无跨币种主线可归纳。"])
        self.assertEqual(codes_of(v, "SUMMARY_NUMBER_NOT_IN_BODY"), [], v)
        v2 = map_check(summary=["- 统一推力候选值 0.4321。"])
        self.assertEqual(len(codes_of(v2, "SUMMARY_NUMBER_NOT_IN_BODY")), 1, v2)

    def test_quick_table_and_review_and_gaps_all_count_as_body(self):
        """正文的范围是**冻结的清单**:币种节 ∪ 速览 ∪ 复盘 ∪ 缺漏节。
        缺漏节在列是实测要求的 —— reports/daily/2026-08-07.md 的摘要写
        「GDELT 事件采集均为 429」,429 只出现在缺漏节里。"""
        for kw in ({"quick": "| EUR | 0.4321 |"},
                   {"review": "- 上期统一推力候选值 0.4321"},
                   {"gaps": "- [gdelt/USD] HTTP Error 0.4321"}):
            with self.subTest(**kw):
                v = map_check(summary=["- 统一推力候选值 0.4321。"], **kw)
                self.assertEqual(codes_of(v, "SUMMARY_NUMBER_NOT_IN_BODY"), [], v)

    def test_an_appendix_outside_the_frozen_list_is_not_body(self):
        """反面:清单之外的节(附录)不算正文 —— 否则"正文"退化成
        "报告的其余部分",这条码就只剩摘要自己不在场时才可能红。"""
        v = map_check(summary=["- 统一推力候选值 0.4321。"],
                      extra="- [@X] 统一推力候选值 0.4321")
        self.assertEqual(len(codes_of(v, "SUMMARY_NUMBER_NOT_IN_BODY")), 1, v)

    def test_small_integers_are_never_required_to_be_in_the_body(self):
        """**变异靶点:摘要侧不豁免 ALLOWED_SMALL。**

        序数/条数(「摘要第 7 条」「T+3」)在正文里没有对应是常态,不是
        A1 说的那种数。不豁免时,本文件 `make_report` 的「摘要第 1/2/3 条」
        当场炸出 3 条,17 个既有用例连带变红 —— 那是这一类的真实形状。
        实测:在 reports/daily/2026-08-07..14 八份产物上,豁免与不豁免炸出
        的条数**都是 0**,这条豁免不换取任何已知的检出力。
        """
        v = map_check(summary=["- 摘要第 7 条:比索参考价 60.843 未变(T+3)。"])
        self.assertEqual(codes_of(v, "SUMMARY_NUMBER_NOT_IN_BODY"), [], v)

    def test_a_summary_with_only_small_integers_declares_the_skip(self):
        """豁免掉之后一个可查的数都不剩 —— 那与"全查过且全过"在输出上不可
        分辨,必须走跳过声明这一支。"""
        notes = []
        map_check(summary=["- 摘要第 7 条:本日无跨币种主线。"], notes=notes)
        line = [n for n in notes
                if n.startswith("SUMMARY_NUMBER_SKIPPED_NO_NUMBERS")]
        self.assertEqual(len(line), 1, notes)

    def test_summary_without_numbers_skips_and_declares(self):
        """三态:摘要里一个数都没有 → 跳过并声明。"""
        notes = []
        map_check(summary=["- 本日无跨币种主线可归纳。"], notes=notes)
        line = [n for n in notes
                if n.startswith("SUMMARY_NUMBER_SKIPPED_NO_NUMBERS")]
        self.assertEqual(len(line), 1, notes)

    def test_missing_summary_section_skips_and_declares(self):
        notes = []
        report = map_report().replace("## 执行摘要", "## 摘要占位")
        v = check_report.check_daily(report, MAP_SNAP_TEXT, MAP_BRIEF,
                                     notes=notes)
        self.assertEqual(codes_of(v, "SUMMARY_NUMBER_NOT_IN_BODY"), [], v)
        self.assertTrue([n for n in notes
                         if n.startswith("SUMMARY_NUMBER_SKIPPED_NO_SECTION")],
                        notes)

    def test_no_skip_note_when_the_summary_had_numbers(self):
        notes = []
        map_check(summary=["- 比索参考价 60.843 未变。"], notes=notes)
        self.assertEqual([n for n in notes
                          if n.startswith("SUMMARY_NUMBER_SKIPPED")], [], notes)

    def test_violation_line_carries_the_disposition(self):
        line = codes_of(map_check(summary=["- 统一推力候选值 0.4321。"]),
                        "SUMMARY_NUMBER_NOT_IN_BODY")[0]
        self.assertTrue(line.endswith(check_report.DISPOSITION_SUMMARY_BODY),
                        line)

    def test_cli_turns_a_summary_only_number_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            argv, _ = daily_files(
                tmp, report_text=map_report(summary=["- 统一推力候选值 0.4321。"]),
                snapshot_text=MAP_SNAP_TEXT, brief_text=MAP_BRIEF,
                prior_text=map_report(prior_line=PRIOR_LINE_PREV),
                extra=("--mode", "daily"))
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = check_report.main(argv)
            out = buf.getvalue()
        self.assertEqual(rc, 1, out)
        self.assertIn("SUMMARY_NUMBER_NOT_IN_BODY", out)


class NumberMappingPoolFrozenTest(unittest.TestCase):
    """共享池、币种↔经济体映射、别名表、正文节清单 —— **逐元素**冻结。

    与 DISPOSITION_* 同规格:这几张表是判定本身,悄悄多一个元素就等于悄悄
    多一条豁免。改它们必须同时改这里,显式动作、进 diff。
    """

    def test_shared_snapshot_keys_are_frozen(self):
        self.assertEqual(check_report.SHARED_SNAPSHOT_KEYS,
                         ("date", "calendar_hits", "gaps", "meta"))

    def test_shared_brief_headings_are_frozen(self):
        self.assertEqual(check_report.SHARED_BRIEF_HEADINGS,
                         ("跨币种共同主线",))

    def test_economy_of_currency_is_frozen(self):
        self.assertEqual(check_report.ECONOMY_OF_CURRENCY,
                         {"USD": "US", "EUR": "EA", "PHP": "PH",
                          "THB": "TH", "BRL": "BR"})

    def test_currency_aliases_are_frozen(self):
        self.assertEqual(check_report.CURRENCY_ALIASES,
                         {"USD": ("USD", "美元"), "EUR": ("EUR", "欧元"),
                          "PHP": ("PHP", "比索"), "THB": ("THB", "泰铢"),
                          "BRL": ("BRL", "雷亚尔")})

    def test_summary_body_section_keys_are_frozen(self):
        self.assertEqual(check_report.SUMMARY_BODY_SECTION_KEYS,
                         ("速览", "复盘", "数据缺漏"))

    def test_every_currency_has_an_economy_and_aliases(self):
        for c in check_report.CURRENCIES:
            self.assertIn(c, check_report.ECONOMY_OF_CURRENCY, c)
            self.assertIn(c, check_report.CURRENCY_ALIASES, c)


class NumberMappingHonestyLabelTest(unittest.TestCase):
    """诚实标注:两个码各自的性质写在源码 docstring 里,并写明**它管不了
    什么**。调研实测 IMF 那套评分器停在存在性那一层,而我们刚照出自己也停在
    那一层 —— 把存在性说成质量,就是复现同一个病;反过来,把质量检查的
    边界写没了,也是同一个病。"""

    def test_wrong_section_is_labelled_a_quality_check_with_its_boundary(self):
        doc = check_report.check_number_section_mapping.__doc__ or ""
        self.assertIn("NUMBER_WRONG_SECTION", doc)
        self.assertIn("质量检查", doc)
        self.assertIn("存在性", doc)

    def test_summary_body_is_labelled_a_quality_check_with_its_boundary(self):
        doc = check_report.check_summary_numbers_in_body.__doc__ or ""
        self.assertIn("SUMMARY_NUMBER_NOT_IN_BODY", doc)
        self.assertIn("质量检查", doc)
        self.assertIn("存在性", doc)


# ==================== 节定位唯一化(Fatal 1)====================
#
# `find_section` 取**首个**匹配 —— 报告里只要出现一个重名小节,五个新码
# 定位到的就是错的那一节,于是全部悄悄不跑,输出仍是 `CHECK PASSED`。
# 复现(本轮实测,见 SectionKeyMustResolveUniquelyTest.test_a_decoy_section_
# used_to_silence_all_five_new_codes 的 fixture):同一份报告加两行占位标题,
# 五码命中由 5 变 1,而那 1 条还是对着占位文本的**假**违规。
# **在修掉它之前,这五个码的强制力等于一行报告编辑。**
#
# 误报成本先复算再动手(本轮实测,不是抄对抗报告的数):
# 8 份日报 × 10 个日报键、8 份要点表 × 6 个要点表键、1 份周报 × 5 个周报键,
# 多重匹配**共 0 次**。所以唯一化是零成本的。

AMB_DECOY_SUMMARY = "## 执行摘要(草稿,占位)"
AMB_DECOY_PHP = "## 菲律宾比索(PHP)——占位"


def amb_snap(modes=None):
    snap = json.loads(MAP_SNAP_TEXT)
    m = {c: "full" for c in check_report.CURRENCIES}
    m.update(modes or {})
    snap["derived"]["body_plan"] = {c: {"mode": mode, "line": None}
                                    for c, mode in m.items()}
    return json.dumps(snap, ensure_ascii=False)


# PHP 节:五码里的 ①②③④ 一次踩全(④ 靠 35.2 —— 泰铢的数、本节不点名泰铢)
AMB_PHP_BODY = ("**分歧与判断**:关键假设是通胀已经见顶,这句里没有任何数。"
                "翻转指标:升破那条线。失效条件:升破那条线。"
                "另外 35.2 摆在这里。")
AMB_SUMMARY = ["- 摘要写了 0.4321 这个数。"]      # ⑤:只在要点表跨币种块里
# 其余四节写**完整且合规**的判断环:这样 ①②③ 的命中数恰好各为 1,
# "五码全中 → 加两行占位后只剩 1 条(且是假的)"这句话才是逐字可验的。
AMB_CLEAN_BODIES = {
    "USD": ("**驱动**:政策利率 4.25,实际利率 0.26。**分歧与判断**:"
            "关键假设是 4.25 在下期读数前不动;不成立时改按会议路径重写。"
            "替代解释:美元一端在统一定价。翻转指标:实际利率回落至 0 一侧(T+3)。"),
    "EUR": ("**驱动**:参考价 0.921,实际利率 -0.499。**分歧与判断**:"
            "关键假设是 0.921 仍代表当前定盘;不成立时本节整体作废。"
            "替代解释:欧洲一端的政策路径。翻转指标:参考价回落至上一次定盘之下(T+3)。"),
    "THB": ("**驱动**:参考价 35.2,实际利率 -1.42。**分歧与判断**:"
            "关键假设是 35.2 仍代表当前定盘;不成立时本节整体作废。"
            "替代解释:出口一端的季节性。翻转指标:参考价回落至上一次定盘之下(T+3)。"),
    "BRL": ("**驱动**:参考价 5.43,实际利率 9.359。**分歧与判断**:"
            "关键假设是 5.43 仍代表当前定盘;不成立时本节整体作废。"
            "替代解释:选举溢价而非套息厚度。翻转指标:参考价回落至上一次定盘之下(T+3)。"),
}


def amb_report(decoy=False, prior_line=PRIOR_LINE_CUR):
    bodies = dict(AMB_CLEAN_BODIES)
    bodies["PHP"] = AMB_PHP_BODY
    rep = map_report(bodies=bodies, summary=list(AMB_SUMMARY),
                     prior_line=prior_line)
    if not decoy:
        return rep
    rep = rep.replace("## 执行摘要\n",
                      AMB_DECOY_SUMMARY + "\n- 占位,无数字。\n\n## 执行摘要\n")
    return rep.replace("## 菲律宾比索(PHP)\n",
                       AMB_DECOY_PHP + "\n占位。\n\n## 菲律宾比索(PHP)\n")


FIVE_NEW_CODES = ("JUDGEMENT_RING_INCOMPLETE",
                  "FLIP_INDICATOR_IS_INVALIDATION_RESTATED",
                  "ASSUMPTION_UNANCHORED",
                  "NUMBER_WRONG_SECTION",
                  "SUMMARY_NUMBER_NOT_IN_BODY")


class SectionKeyMustResolveUniquelyTest(unittest.TestCase):
    """节定位**唯一化 + 失败关闭**:同一个键匹配到 ≥2 个小节即 `SECTION_AMBIGUOUS`,
    且依赖该节的检查一律不执行,**不得静默取第一个**。

    这是本仓反复出现的同一个病(「打印通过,但守的不是它声称的东西」)的
    第 14 次实例,所以修法按**不变量**做:唯一的解析入口 `find_section`
    对 ≥2 个匹配返回 `None`,任何调用点都拿不到"第一个"。
    """

    def _codes(self, v):
        return {c: len([x for x in v if x.startswith(c + ":")])
                for c in FIVE_NEW_CODES}

    def test_the_five_new_codes_all_fire_without_a_decoy(self):
        """基线:同一份报告在没有重名小节时,五个码**全部**命中。
        没有这一条,下面那条"加了占位就全灭"证明不了任何事。"""
        v = check_report.check_daily(amb_report(), amb_snap(), MAP_BRIEF)
        self.assertEqual(self._codes(v), {c: 1 for c in FIVE_NEW_CODES}, v)

    def test_a_decoy_section_must_not_silence_the_five_new_codes(self):
        """**变异靶点(Fatal 1 本体):两行占位标题把五个码全部关掉。**

        修前实测:五码命中 {① 1, ② 0, ③ 0, ④ 0, ⑤ 0} —— ② ③ ④ ⑤ 全灭,
        ① 退化成对着「占位。」那一行的假违规,而 stdout **零声明**。
        修后要求:重名即红,不允许静默取第一个。
        """
        v = check_report.check_daily(amb_report(decoy=True), amb_snap(),
                                     MAP_BRIEF)
        amb = [x for x in v if x.startswith("SECTION_AMBIGUOUS:")]
        self.assertEqual(len(amb), 2, v)
        self.assertTrue(any("执行摘要" in x for x in amb), amb)
        self.assertTrue(any("PHP" in x for x in amb), amb)

    def test_the_ambiguity_line_quotes_both_headings_and_the_disposition(self):
        """"有重名"不可操作 —— 读者得自己去报告里数标题。两个标题原文
        一起打出来,并带处置。"""
        v = check_report.check_daily(amb_report(decoy=True), amb_snap(),
                                     MAP_BRIEF)
        line = [x for x in v if x.startswith("SECTION_AMBIGUOUS:")
                and "执行摘要" in x][0]
        self.assertIn(AMB_DECOY_SUMMARY[3:], line)
        self.assertIn("2 个", line)
        self.assertTrue(line.endswith(check_report.DISPOSITION_AMBIGUOUS), line)

    def test_find_section_returns_none_when_the_key_is_ambiguous(self):
        """不变量本体:唯一的解析入口对 ≥2 个匹配返回 None。
        调用点因此**拿不到**"第一个",失败关闭是结构性的,不靠每个调用点自觉。
        """
        secs = [("菲律宾比索(PHP)——占位", "占位。"),
                ("菲律宾比索(PHP)", "正文。")]
        self.assertIsNone(check_report.find_section(secs, "PHP"))
        self.assertEqual(check_report.find_section(secs[1:], "PHP"),
                         ("菲律宾比索(PHP)", "正文。"))

    def test_zero_matches_keeps_the_existing_section_missing_semantics(self):
        """匹配 0 个**沿用既有行为**:SECTION_MISSING,不是 SECTION_AMBIGUOUS。"""
        rep = amb_report().replace("## 泰铢(THB)\n", "## 某某\n")
        v = check_report.check_daily(rep, amb_snap(), MAP_BRIEF)
        self.assertTrue(any(x == "SECTION_MISSING: 缺少币种节 THB" for x in v), v)
        self.assertEqual([x for x in v if x.startswith("SECTION_AMBIGUOUS:")], [])

    def test_an_ambiguous_currency_does_not_also_report_section_missing(self):
        """重名 ≠ 缺失。同一处缺陷不得产生两条互相矛盾的违规
        (「缺少币种节 PHP」而报告里明明有两节)。"""
        v = check_report.check_daily(amb_report(decoy=True), amb_snap(),
                                     MAP_BRIEF)
        self.assertNotIn("SECTION_MISSING: 缺少币种节 PHP", v)

    def test_an_ambiguous_brief_section_is_a_violation_too(self):
        """要点表侧同理:数字池按 `## <币种>` 切,重名就等于让被查方挑池子。"""
        brief = MAP_BRIEF.replace("## PHP\n", "## PHP(草稿)\n- 占位\n\n## PHP\n")
        v = check_report.check_daily(amb_report(), amb_snap(), brief)
        line = [x for x in v if x.startswith("SECTION_AMBIGUOUS:")]
        self.assertEqual(len(line), 1, v)
        self.assertIn("要点表", line[0])

    def test_an_ambiguous_prior_report_section_is_a_violation_too(self):
        """上一份日报里塞两个同名节 = 关掉今天的跨期重复检查。同样失败关闭。"""
        # `prior_line=None` 关掉 map_report 自带的那一节 —— 本条要自己造
        # "上一份里有两个同名节"的形态,自带的那一节会变成第三个
        prior = amb_report(prior_line=None) \
            + "\n\n## 本期相对上期的变化\n- A。\n\n" \
              "## 本期相对上期的变化(旧)\n- B。\n"
        cur = amb_report(prior_line=None) + "\n\n## 本期相对上期的变化\n- A。\n"
        v = check_report.check_daily(cur, amb_snap(), MAP_BRIEF,
                                     prior_text=prior)
        line = [x for x in v if x.startswith("SECTION_AMBIGUOUS:")]
        self.assertEqual(len(line), 1, v)
        self.assertIn("上一份日报", line[0])

    def test_weekly_section_keys_must_resolve_uniquely(self):
        """周报侧同理:`本周主线` 重名会让 THEME_TOO_MANY 数错那一节。"""
        rep = make_weekly().replace("## 本周主线\n",
                                    "## 本周主线(草稿)\n- 占位\n\n## 本周主线\n")
        v = check_report.check_weekly(rep)
        line = [x for x in v if x.startswith("SECTION_AMBIGUOUS:")]
        self.assertEqual(len(line), 1, v)
        self.assertIn("本周主线", line[0])

    def test_no_check_answers_a_question_about_the_wrong_section(self):
        """**变异靶点:`find_section` 退回"取首个匹配"。**

        只断言"重名要出 SECTION_AMBIGUOUS"是不够的 —— 那条断言在取首个的
        实现上照样绿(歧义是 `section_hits` 数出来的,与取谁无关)。
        要害是**取首个会对着错的那一节给出答案**:占位节写 5 条,
        `THEME_TOO_MANY` 就照着占位节数,打出一条关于**不存在的问题**的红。
        失败关闭的含义是"不回答",不是"回答错的那个"。
        """
        decoy = "## 本周主线(草稿)\n" + "\n".join(
            "- 占位 %d" % (i + 1) for i in range(5)) + "\n\n## 本周主线\n"
        v = check_report.check_weekly(
            make_weekly().replace("## 本周主线\n", decoy))
        self.assertEqual([x for x in v if x.startswith("THEME_TOO_MANY")], [], v)

    def test_an_ambiguous_currency_section_is_not_measured_against_the_decoy(self):
        """同一个变异的日报侧:占位节塞满中文字,`SECTION_TOO_LONG` 就照着
        占位节量,而真正那一节根本没被看过。"""
        long_decoy = ("## 菲律宾比索(PHP)——占位\n" + "占" * 400 +
                      "\n\n## 菲律宾比索(PHP)\n")
        rep = map_report(bodies={"PHP": AMB_PHP_BODY}).replace(
            "## 菲律宾比索(PHP)\n", long_decoy)
        v = check_report.check_daily(rep, amb_snap(), MAP_BRIEF)
        self.assertEqual([x for x in v if x.startswith("SECTION_TOO_LONG")],
                         [], v)
        self.assertTrue([x for x in v if x.startswith("SECTION_AMBIGUOUS:")], v)

    def test_the_five_new_codes_do_not_run_against_the_decoy_either(self):
        """失败关闭的另一半:五个码在歧义键上**一条都不出** —— 出了就说明
        它们对着占位文本算了答案(修前那条假的 ① 正是这个形状)。"""
        v = check_report.check_daily(amb_report(decoy=True), amb_snap(),
                                     MAP_BRIEF)
        self.assertEqual(self._codes(v), {c: 0 for c in FIVE_NEW_CODES}, v)

    def test_cli_turns_an_ambiguous_report_red(self):
        """端到端:进程内断言全绿而真 CLI 放行,是本仓库栽过的形态。"""
        with tempfile.TemporaryDirectory() as tmp:
            argv, _ = daily_files(
                tmp, report_text=amb_report(decoy=True),
                snapshot_text=amb_snap(), brief_text=MAP_BRIEF,
                prior_text=map_report(prior_line=PRIOR_LINE_PREV),
                extra=("--mode", "daily"))
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = check_report.main(argv)
            out = buf.getvalue()
        self.assertEqual(rc, 1, out)
        self.assertIn("SECTION_AMBIGUOUS", out)

    def test_section_key_lists_are_frozen(self):
        """三份键清单**逐元素**冻结:悄悄从清单里去掉一个键,就等于把那个键
        的唯一化悄悄关掉。与 SHARED_SNAPSHOT_KEYS 同规格。"""
        self.assertEqual(
            check_report.DAILY_REPORT_SECTION_KEYS,
            ("USD", "EUR", "PHP", "THB", "BRL", "执行摘要", "复盘",
             "数据缺漏", "本期相对上期", "速览"))
        self.assertEqual(check_report.BRIEF_SECTION_KEYS,
                         ("USD", "EUR", "PHP", "THB", "BRL", "跨币种共同主线"))
        self.assertEqual(check_report.WEEKLY_REPORT_SECTION_KEYS,
                         ("本周主线", "各币种", "复盘汇总", "本周关注", "缺漏汇总"))

    def test_every_key_reachable_by_find_section_is_in_a_frozen_list(self):
        """闭合件:源码里传给 `find_section` 的常量键,必须都在某份冻结清单里。
        新加一个 `find_section(secs, "新节")` 而不入清单 → 这条红,
        它的唯一化就不会被悄悄漏掉。"""
        with open(check_report.__file__, encoding="utf-8") as f:
            tree = ast.parse(f.read())
        listed = set(check_report.DAILY_REPORT_SECTION_KEYS)
        listed |= set(check_report.BRIEF_SECTION_KEYS)
        listed |= set(check_report.WEEKLY_REPORT_SECTION_KEYS)
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id in ("find_section", "section_hits")):
                continue
            arg = node.args[1] if len(node.args) > 1 else None
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                self.assertIn(arg.value, listed,
                              "find_section 的字面量键 %r 不在任何冻结清单里"
                              % arg.value)


# ==================== 共享池的归属减法(Major 2)====================

class SharedPoolIsNotWrittenByTheCheckedPartyTest(unittest.TestCase):
    """共享池里来自**要点表**的那一半由被查方(LLM)撰写 —— 于是"想让某个数
    在某节合法,只要把它写进要点表的跨币种块"。闸门的输入被被查方控制,而且
    **不出声**。

    修法:要点表那一部分先过**归属减法** —— 凡是在要点表 `## <币种>` 那节
    出现过的数,只解锁该币种,不进共享池。快照侧的 SHARED_SNAPSHOT_KEYS
    不参与减法(那一侧不由被查方撰写)。
    """

    CROSS = "- 四盘同侧移动,统一推力候选值 0.4321"

    def test_writing_a_currency_number_into_the_cross_block_cannot_unlock_it(self):
        """**变异靶点(Major 2 本体):逐个数自助解锁。**

        60.843 是比索的数。把它抄进要点表的跨币种块,修前它就进了共享池,
        于是泰铢节写 60.843 逐字放行 —— 而那一行是 LLM 自己写的。
        """
        brief = MAP_BRIEF.replace(
            self.CROSS, self.CROSS + ";比索 60.843 是当日锚")
        v = map_check({"THB": "**驱动**:参考价 35.2,另一档 60.843。"},
                      brief=brief)
        line = codes_of(v, "NUMBER_WRONG_SECTION")
        self.assertEqual(len(line), 1, v)
        self.assertIn("60.843", line[0])
        self.assertIn("PHP", line[0])

    def test_a_genuinely_cross_currency_number_stays_shared(self):
        """减法的**上界**:跨币种块里那些**没有**币种块认领的数仍是共享的。
        减过头就等于把跨币种比较这条正常写法整体判死。"""
        v = map_check({"THB": "**驱动**:参考价 35.2,统一推力 0.4321。"})
        self.assertEqual(codes_of(v, "NUMBER_WRONG_SECTION"), [], v)

    def test_snapshot_side_shared_keys_are_never_subtracted(self):
        """减法**只作用于要点表那一部分**:快照的 gaps/date/calendar_hits/meta
        不由被查方撰写,把它们也减掉是没有理由的收紧。

        429 同时出现在快照 gaps 与要点表的 PHP 块里 —— 它仍然是共享的。
        """
        snap = json.loads(MAP_SNAP_TEXT)
        snap["gaps"] = [{"source": "gdelt", "scope": "USD",
                         "note": "HTTP Error 429"}]
        brief = MAP_BRIEF.replace("## PHP\n", "## PHP\n- 事件源 429 未取到\n")
        v = map_check({"THB": "**驱动**:参考价 35.2,事件源 429 未取到。"},
                      snap=json.dumps(snap, ensure_ascii=False), brief=brief,
                      gaps="- [gdelt/USD] HTTP Error 429")
        self.assertEqual(codes_of(v, "NUMBER_WRONG_SECTION"), [], v)

    def test_shared_pool_helper_drops_brief_attributed_numbers(self):
        """单元级:同一个数同时出现在跨币种块与某币种块时,共享池里不得有它。"""
        brief = MAP_BRIEF.replace(
            self.CROSS, self.CROSS + ";比索 60.843 是当日锚")
        pool = check_report.shared_number_pool(json.loads(MAP_SNAP_TEXT), brief)
        self.assertNotIn("60.843", pool)
        self.assertIn("0.4321", pool)


# ==================== 三处放行/不可达必须出声(Major 3 / 5 / 6)============

class NamedPassThroughIsDeclaredTest(unittest.TestCase):
    """Major 3:**节内点名了别的币种 → 该币种池整个放行**,而且不出声。

    这是 `check_number_section_mapping` 自己写明的诚实边界(判定单位是节),
    不是缺陷 —— 但"放行了多少"必须打印出来,否则它与"全查过且全过"在输出上
    逐字不可分辨。声明**带计数**:放行了几个组合、放行了几个数字实例。
    """

    def test_no_declaration_when_nothing_was_released(self):
        notes = []
        map_check(notes=notes)
        self.assertEqual([n for n in notes
                          if n.startswith("NUMBER_WRONG_SECTION_NAMED_PASS:")],
                         [], notes)

    def test_declaration_carries_both_counts(self):
        """5 个币种节 × 4 个别的币种 = 20 个组合;本例点名 1 个,
        因此放行 1 个数字实例(4.25 是美元的数,写在雷亚尔节里)。"""
        notes = []
        map_check({"BRL": "**驱动**:参考价 5.43;美元一端政策利率 4.25 未变。"},
                  notes=notes)
        line = [n for n in notes
                if n.startswith("NUMBER_WRONG_SECTION_NAMED_PASS:")]
        self.assertEqual(len(line), 1, notes)
        self.assertIn("1/20", line[0])
        self.assertIn("1 个数字实例", line[0])

    def test_declaration_is_printed_by_the_cli(self):
        """进程内出声、真 CLI 不出声,是本仓库栽过的形态。"""
        with tempfile.TemporaryDirectory() as tmp:
            report = map_report(
                bodies={"BRL": "**驱动**:参考价 5.43;美元一端政策利率 4.25 未变。"})
            argv, _ = daily_files(
                tmp, report_text=report, snapshot_text=MAP_SNAP_TEXT,
                brief_text=MAP_BRIEF,
                prior_text=map_report(prior_line=PRIOR_LINE_PREV),
                extra=("--mode", "daily"))
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                check_report.main(argv)
            out = buf.getvalue()
        self.assertIn("NUMBER_WRONG_SECTION_NAMED_PASS:", out)


RING_NO_INVALIDATION = ("关键假设是 3.1 这一读数仍代表当前通胀。"
                        "替代解释:比索走弱是美元一端在统一定价。"
                        "翻转指标:参考价回落至 60.9 一侧(T+3)。")


class FlipCheckUnreachableIsDeclaredTest(unittest.TestCase):
    """Major 5:② 只有在同一节里**同时**判得出翻转指标句与失效条件句时才执行。
    判不出失效条件句就整条跳过 —— 而这一跳过此前**零声明**,与"比过了、没重复"
    逐字不可分辨。
    """

    def test_a_section_without_an_invalidation_sentence_declares_it(self):
        notes = []
        v = ring_check(RING_NO_INVALIDATION, notes=notes)
        self.assertEqual(ring_codes(v, "JUDGEMENT_RING_INCOMPLETE"), [], v)
        line = [n for n in notes
                if n.startswith("FLIP_INDICATOR_CHECK_UNREACHABLE:")]
        self.assertEqual(len(line), 1, notes)
        # 分母由 1(此前只有 PHP 走 full 体裁)变成 5:体裁闸门删掉之后
        # 五个覆盖币种节全查,分母就是"查过的节数"。分子仍是 1 —— 只有 PHP
        # 那一节写了翻转指标却判不出失效条件句。
        self.assertIn("1/5", line[0])
        self.assertIn("PHP", line[0])

    def test_a_reachable_section_declares_nothing(self):
        """反面:能比就不出声 —— 否则声明退化成每次都打的噪声。"""
        notes = []
        ring_check(notes=notes)
        self.assertEqual([n for n in notes
                          if n.startswith("FLIP_INDICATOR_CHECK_UNREACHABLE:")],
                         [], notes)

    def test_declaration_names_the_invalidation_labels_it_looked_for(self):
        """不可操作的声明等于没声明:读者得知道校验器找的是哪几个标签。"""
        notes = []
        ring_check(RING_NO_INVALIDATION, notes=notes)
        line = [n for n in notes
                if n.startswith("FLIP_INDICATOR_CHECK_UNREACHABLE:")][0]
        for lab in check_report.INVALIDATION_LABELS:
            self.assertIn(lab, line)


class WeeklyJudgementLayerIsDeclaredTest(unittest.TestCase):
    """Major 6:周报模式下五个新码**一个都不跑**,而周报里写满了判断环,
    输出却是**裸 `CHECK PASSED`**。整层不查同样必须出声,并带计数。
    """

    WITH_RING = ("USD 观望:关键假设是政策利率不动;替代解释:美元一端统一定价;"
                 "翻转指标:四盘同步回落。EUR 震荡;PHP 通胀回落主导;"
                 "THB 出口疲弱;BRL 政策预期反复。")

    def test_weekly_declares_the_whole_layer_is_not_run(self):
        notes = []
        check_report.check_weekly(make_weekly(), notes=notes)
        line = [n for n in notes
                if n.startswith("WEEKLY_JUDGEMENT_LAYER_SKIPPED:")]
        self.assertEqual(len(line), 1, notes)

    def test_the_declaration_counts_the_judgement_rings_it_did_not_check(self):
        """"有跳过"不够 —— 必须说跳过了多少。本例三个标签各 1 处,共 3 处。"""
        notes = []
        check_report.check_weekly(make_weekly(currency_body=self.WITH_RING),
                                  notes=notes)
        line = [n for n in notes
                if n.startswith("WEEKLY_JUDGEMENT_LAYER_SKIPPED:")][0]
        self.assertIn("3 处", line)

    def test_the_declaration_names_all_five_codes(self):
        """点名五个码:读者据此知道周报少了哪几层,而不是"少了点什么"。

        ---- 2026-08-14 更正:五个码现在分两条声明,理由不同 ----
        判断环三码**已经在周报模式跑起来了**(见 `check_weekly_judgement_ring`),
        所以 `WEEKLY_JUDGEMENT_LAYER_SKIPPED` 退化成**闸门不成立**时才出的那
        一条 —— 它点名的只剩三码。数字归属那两码是**结构性不适用**(周报输入
        没有按币种分键的快照切片),另出 `WEEKLY_NUMBER_ATTRIBUTION_NOT_APPLICABLE`
        并把"为什么不适用"写进去。
        断言因此拆成两半,**五个码一个都不许少** —— 少一个就意味着某一层
        既不跑、也不出声,那正是本类要消灭的形态。
        """
        notes = []
        check_report.check_weekly(make_weekly(), notes=notes)
        gate = [n for n in notes
                if n.startswith("WEEKLY_JUDGEMENT_LAYER_SKIPPED:")][0]
        na = [n for n in notes
              if n.startswith("WEEKLY_NUMBER_ATTRIBUTION_NOT_APPLICABLE:")][0]
        for code in FIVE_NEW_CODES[:3]:
            self.assertIn(code, gate)
        for code in FIVE_NEW_CODES[3:]:
            self.assertIn(code, na)
        self.assertIn("SUMMARY_NUMBER_WRONG_CURRENCY", na)

    def test_the_weekly_cli_no_longer_prints_a_bare_check_passed(self):
        """端到端:生产周报命令行(带 --digest)必须打出这条声明。"""
        with tempfile.TemporaryDirectory() as tmp:
            rp = os.path.join(tmp, "w.md")
            dp = os.path.join(tmp, "d.json")
            with open(rp, "w", encoding="utf-8") as f:
                f.write(make_weekly(currency_body=self.WITH_RING))
            with open(dp, "w", encoding="utf-8") as f:
                json.dump({"week": "2026-W32", "generated_from": [],
                           "events": {}, "rates": {}}, f)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = check_report.main([rp, "--mode", "weekly", "--digest", dp])
            out = buf.getvalue()
        self.assertEqual(rc, 0, out)
        self.assertIn("WEEKLY_JUDGEMENT_LAYER_SKIPPED:", out)
        self.assertIn("CHECK PASSED", out)


# ============ 摘要数字的**关系判定**(Major 4,选 (b))============

class SummaryNumberAttributionTest(unittest.TestCase):
    """`SUMMARY_NUMBER_WRONG_CURRENCY` —— **关系判定**(归属级)。

    Major 4 的原文:`SUMMARY_NUMBER_NOT_IN_BODY` 被标为「质量检查」,而实现
    是**换了参照池的集合差存在性判定**。二选一里选 (b)「把实现升级成真正的
    关系判定」——(a) 只改标注是诚实的下策。
    升级落在这一层:摘要 bullet 点名了币种 X,这一条里的数就必须出自 X
    (或共享池);只出自 Y 的数写在点名 X 的那一条里 = 归属错。
    判据是**数与币种之间的对应**,不是某个 token 在不在另一个池里。

    旧码一条都没删:它退回它本来的身份(存在性层),标注同步改正 ——
    见 SummaryHonestyLabelTest。
    """

    def test_clean_summary_passes(self):
        self.assertEqual(
            codes_of(map_check(summary=["- 比索参考价 60.843 未变。"]),
                     "SUMMARY_NUMBER_WRONG_CURRENCY"), [])

    def test_a_number_from_another_currency_is_a_violation(self):
        """**变异靶点(Major 4 本体):存在性判定对这一条完全不敏感。**

        60.843 是比索的数,写在点名泰铢的那一条里。它在正文的比索节里出现过
        —— 所以 `SUMMARY_NUMBER_NOT_IN_BODY` 逐字放行,`NUMBER_UNTRACEABLE`
        也放行(它在快照里)。只有关系判定看得见。
        """
        v = map_check(summary=["- 泰铢一档写成 60.843。"])
        self.assertEqual(codes_of(v, "SUMMARY_NUMBER_NOT_IN_BODY"), [], v)
        self.assertEqual(codes_of(v, "NUMBER_UNTRACEABLE"), [], v)
        line = codes_of(v, "SUMMARY_NUMBER_WRONG_CURRENCY")
        self.assertEqual(len(line), 1, v)
        self.assertIn("60.843", line[0])
        self.assertIn("THB", line[0])
        self.assertIn("PHP", line[0])

    def test_naming_the_owning_currency_in_the_same_bullet_passes(self):
        """判定单位是 **bullet**,点名即放行 —— 与 NUMBER_WRONG_SECTION 的
        节级点名同规矩,跨币种对照是摘要的正常写法。"""
        v = map_check(summary=["- 泰铢 35.2 与比索 60.843 同向。"])
        self.assertEqual(codes_of(v, "SUMMARY_NUMBER_WRONG_CURRENCY"), [], v)

    def test_a_number_no_currency_owns_is_not_this_codes_business(self):
        """**误报的下界**:归属不到任何币种的数(共享池、日期碎片如
        `2026-08` 剥出来的 `08`)不归本码管 —— 那一类由存在性层与
        NUMBER_UNTRACEABLE 管。同一个 token 不得吃两条违规。
        实测:不加这条门,reports/daily/2026-08-13.md 的摘要「参考月 2026-08」
        当场炸出一条 `08` 的假红。"""
        v = map_check(summary=["- 泰铢一档,统一推力 0.4321,参考月 2026-08。"])
        self.assertEqual(codes_of(v, "SUMMARY_NUMBER_WRONG_CURRENCY"), [], v)

    def test_a_bullet_naming_no_currency_declares_the_skip(self):
        """点不出币种就判不了归属 —— 不判,但出声,并带计数。"""
        notes = []
        v = map_check(summary=["- 某一档写成 60.843。"], notes=notes)
        self.assertEqual(codes_of(v, "SUMMARY_NUMBER_WRONG_CURRENCY"), [], v)
        line = [n for n in notes
                if n.startswith("SUMMARY_NUMBER_SKIPPED_NO_CURRENCY_NAMED:")]
        self.assertEqual(len(line), 1, notes)
        self.assertIn("1 条", line[0])

    def test_small_integers_are_exempt_here_too(self):
        """与 NUMBER_WRONG_SECTION / SUMMARY_NUMBER_NOT_IN_BODY 同一条豁免:
        序数/条数没有币种归属。三处口径必须一致,否则「T+3」在一处红一处绿。"""
        v = map_check(summary=["- 泰铢第 7 条:同向(T+3)。"])
        self.assertEqual(codes_of(v, "SUMMARY_NUMBER_WRONG_CURRENCY"), [], v)

    def test_violation_line_quotes_the_bullet_and_the_disposition(self):
        line = codes_of(map_check(summary=["- 泰铢一档写成 60.843。"]),
                        "SUMMARY_NUMBER_WRONG_CURRENCY")[0]
        self.assertIn("泰铢一档写成 60.843", line)
        self.assertTrue(
            line.endswith(check_report.DISPOSITION_SUMMARY_CURRENCY), line)


class SummaryHonestyLabelTest(unittest.TestCase):
    """诚实标注:Major 4 指出 `check_summary_numbers_in_body` 的 docstring
    **在同一页里自相矛盾** —— 既说"不是存在性",又说"只查出现过"。
    改法是让标注跟着实现走:存在性层就写存在性,关系判定写在新的那一层。
    """

    def test_the_existence_layer_no_longer_calls_itself_a_quality_check(self):
        """断言落在 docstring 的**首行**(也就是标注本身),不是全文:
        更正的来龙去脉要写在正文里,那一段自然会提到"质量检查"这四个字。
        旧的自称串另行逐字禁掉 —— 标注改回去必须显式动作、进 diff。"""
        doc = check_report.check_summary_numbers_in_body.__doc__ or ""
        first = doc.splitlines()[0]
        self.assertIn("SUMMARY_NUMBER_NOT_IN_BODY", first)
        self.assertIn("存在性检查", first)
        self.assertNotIn("质量检查", first)
        self.assertNotIn("**质量检查**(一致性级)", doc)

    def test_the_relation_layer_is_labelled_a_relation_check(self):
        doc = check_report.check_summary_number_attribution.__doc__ or ""
        self.assertIn("SUMMARY_NUMBER_WRONG_CURRENCY", doc)
        self.assertIn("关系判定", doc)
        self.assertIn("存在性", doc)


# ==================== 码清单冻结扩到新码与新声明(Minor 10)==============

def _emitted_codes(module_path):
    """扫源码里**被打印出去的**全部违规/声明码(不再只扫 `VERDICT_*`)。

    判据与 `_emitted_verdict_codes` 同:AST 里以 `大写码:` 开头的字符串
    字面量。**已知边界**(实测口径,不许写成全称):码若由变量或 f-string
    拼出来,这个扫描看不到。
    """
    with open(module_path, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    codes = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            m = re.match(r"([A-Z][A-Z0-9_]{3,})[::]", node.value)
            if m:
                codes.add(m.group(1))
    return codes


# 判断环 / 数字归属 / 节唯一化这一层的**违规码 → 它自己那一条处置**。
NEW_LAYER_VIOLATION_DISPOSITION = {
    "SECTION_AMBIGUOUS": "DISPOSITION_AMBIGUOUS",
    "JUDGEMENT_RING_INCOMPLETE": "DISPOSITION_RING",
    "FLIP_INDICATOR_IS_INVALIDATION_RESTATED": "DISPOSITION_FLIP",
    "ASSUMPTION_UNANCHORED": "DISPOSITION_ANCHOR",
    # 2026-08-19 新增:关键假设拿**带滞后**的宏观读数当锚点时必须写出期号。
    # 它判**披露**不判新鲜度 —— 快照回答不了"发布方有没有出新的一期"。
    # 实测:PH/TH/EA/BR 的 CPI 自换 BIS 起 lag_months 恒为 2,按"该序列
    # 自己历史上的最小滞后"判一条都标不出来,而 PH 的 2026-07 读数 6.2
    # 早已发布。真正的新鲜度判据要等发布日历接进来(A1 步骤 3)。
    "ASSUMPTION_VINTAGE_UNDISCLOSED": "DISPOSITION_VINTAGE",
    # 2026-08-19:速览表缺行由「声明 + rc=0」升成违规。缺行不是"少查了一点",
    # 是一个币种当天的判断根本没发布 —— 而 `OVERVIEW_ROW_MISSING` 那条声明
    # 在实测里与 rc=0 并存(docs/known-gate-escapes.md 逃逸 6)。
    "OVERVIEW_ROW_ABSENT": "DISPOSITION_ROW_ABSENT",
    # 2026-08-19:「格 ⊇ trigger」这条包含判据允许截断,而实测 15 条登记里
    # 砍掉的恰好总是时限那一截 —— `claim.horizon` 于是合法地登记成 open,
    # 观点永不到期(docs/known-gate-escapes.md 逃逸 8)。
    "DECISION_TRIGGER_TRUNCATED_DEADLINE": "DISPOSITION_TRUNCATED_DEADLINE",
    # 2026-08-21:BIS 的许可是**有条件的** —— 再现统计时必须署名。实测十二天
    # 里 12/12 的快照含 BIS 序列而 7/12 的报告正文零提及,条件一直没满足而
    # 闸门全绿。串写死在 BIS_ATTRIBUTION_LINE,报告只准逐字抄。
    "BIS_ATTRIBUTION_MISSING": "DISPOSITION_BIS_ATTRIBUTION",
    "NUMBER_WRONG_SECTION": "DISPOSITION_WRONG_SECTION",
    "SUMMARY_NUMBER_NOT_IN_BODY": "DISPOSITION_SUMMARY_BODY",
    "SUMMARY_NUMBER_WRONG_CURRENCY": "DISPOSITION_SUMMARY_CURRENCY",
    # 2026-08-14 新增:速览「条件方向」格与决策日志 trigger 的同源同字。
    # SKILL 第 180/388 行写了这条规则,而校验器此前对它零提及
    # (`grep -n "decision\|决策日志" scripts/check_report.py` 无输出),
    # 实测 25 条里 10 条当前就是违反的、六份产物却全绿。
    "DECISION_TRIGGER_NOT_SOURCED": "DISPOSITION_DECISION_TRIGGER",
    # 2026-08-14 新增:决策日志的结构化观点 `claim` 必须逐字溯源到散文
    # trigger。`claim` 是判定入口(`claims.resolve_claim` 只读它),读者却只
    # 看得到散文 —— 两者漂移时判定照常给出四档之一,只是判的不是读者以为的
    # 那件事,而没有任何自然后果会暴露它。
    "DECISION_CLAIM_NOT_SOURCED": "DISPOSITION_DECISION_CLAIM",
    # 2026-08-14 新增:复盘句必须逐字落在**正文的复盘节**。此前「结论由脚本
    # 给出、报告逐字引用」只是 SKILL 里的散文,校验器对它零强制 —— 脚本算出的
    # 结论走到报告边界就没人看着了。本仓库为此栽过 13 次同型。
    "REVIEW_SENTENCE_NOT_QUOTED": "DISPOSITION_REVIEW_QUOTE",
    # 2026-08-15 新增:表里「失效条件」格与宿主段「翻转指标」句**不得重合**。
    # 它是被删掉的 FLIP_INDICATOR_TABLE_COLUMN_IS_FLIP 的**反面** —— 那条码
    # 之所以只能声明不能判定,是因为 SKILL 当时要求二者同源同字;A 案解耦
    # 之后该要求没了,重合从"规定形态"变成违规形态。
    "INVALIDATION_COLUMN_IS_FLIP_RESTATED": "DISPOSITION_INVALIDATION_COLUMN",
    # ---- 2026-08-15 第二轮:第 4 列此前除「不得与翻转指标重合」外**零求值** ----
    # 四路对抗证伪实测,四种写法全是 rc=0 / 5/5 / CHECK PASSED,其中
    # 「若无新增信息、情况未变(T+3)」是 SKILL 速览表模板段逐字禁止的。
    # 闸门给的压力方向因此与 SKILL 要求的方向相反 —— 把这格写空洞最省力。
    "INVALIDATION_COLUMN_VACUOUS": "DISPOSITION_INVALIDATION_VACUOUS",
    "INVALIDATION_COLUMN_MIRRORS_TRIGGER": "DISPOSITION_INVALIDATION_MIRROR",
    # 修前 `_flip_payloads` 不区分「本判断的翻转指标」与「替代解释自带的
    # 其翻转指标」:把本判断那句的标签改两个字,池仍非空,`checked += 1`
    # 照走,回执宣称与该币种节翻转指标比过了 —— 而那东西此刻不存在。
    "INVALIDATION_COLUMN_FLIP_HOST_MISSING": "DISPOSITION_FLIP_HOST",
    # 「主线归属」格由报告自己写,修前全仓没有任何检查要求它命名一条真实
    # 存在的主线 —— 被查方自选宿主,归属写歪时比对当场落空而只少一分。
    "WEEKLY_THEME_ATTRIBUTION_UNKNOWN": "DISPOSITION_THEME_ATTRIBUTION",
}
# 同一层的**声明码**(走 notes,不改退出码,因此不带处置)。
NEW_LAYER_NOTE_CODES = frozenset({
    # ---- 2026-08-14:判断环的三条跳过声明整族删除,换成一条正向回执 ----
    # 删掉的是 JUDGEMENT_RING_SKIPPED_NO_BODY_PLAN / …_SKIPPED_NO_MODE /
    # …_MINIMAL_EXEMPT。三条都是同一道体裁闸门(`derived.body_plan.<币种>
    # .mode`)的三态,而 MINIMAL_EXEMPT 声称的依据「该节只准写一行」在真实
    # 产物上当场为假 —— reports/daily/2026-08-10.md 的四节各写着 270–322
    # 中文字的完整四环。闸门删了,三态一起无所指。
    # 「跳过必须出声」这条原则没有放弃:不再有跳过态,于是改由回执把
    # 「覆盖 N 节、查了 N 节」打进 stdout。
    "JUDGEMENT_RING_CHECKED", "FLIP_INDICATOR_CHECK_UNREACHABLE",
    # 2026-08-19:披露检查的正向回执 + lag_months 缺失时的跳过声明。
    "ASSUMPTION_VINTAGE_CHECKED", "ASSUMPTION_VINTAGE_SKIPPED_NO_LAG",
    "NUMBER_WRONG_SECTION_MACRO_UNATTRIBUTED",
    "NUMBER_WRONG_SECTION_SKIPPED_NO_SLICE",
    "NUMBER_WRONG_SECTION_NAMED_PASS",
    "SUMMARY_NUMBER_SKIPPED_NO_SECTION", "SUMMARY_NUMBER_SKIPPED_NO_NUMBERS",
    "SUMMARY_NUMBER_SKIPPED_NO_CURRENCY_NAMED",
    "SUMMARY_NUMBER_SKIPPED_AMBIGUOUS",
    "WEEKLY_JUDGEMENT_LAYER_SKIPPED",
    # ---- 2026-08-14:三个「强制力够不着」的洞接上之后新增的声明 ----
    # 速览表解析的三态(缺表 / 列名不符 / 缺行),各带计数。
    "OVERVIEW_TABLE_SKIPPED", "OVERVIEW_TABLE_COLUMN_MISMATCH",
    "OVERVIEW_ROW_MISSING",
    # ---- 2026-08-15:FLIP_INDICATOR_TABLE_COLUMN_IS_FLIP **已删** ----
    # 它是一条只声明不判定的码,存在的全部理由是 SKILL 当时要求速览「失效
    # 条件」格与该币种节的翻转指标**同源同字**(那样任何"两者不得相同"的
    # 检查都会恒红,只能把事实打印出来)。SKILL 走 A 案解耦之后理由消失,
    # 判定升级成违规码 INVALIDATION_COLUMN_IS_FLIP_RESTATED。
    # **本表第二次减项**,与加项同规格,显式记一笔。
    # 新增的正向回执与周报侧唯一的跳过态:
    "INVALIDATION_COLUMN_CHECKED", "WEEKLY_INVALIDATION_COLUMN_SKIPPED",
    # 2026-08-15 第二轮:周报落点表的丢行声明。分母口径改成**应有的行集合**
    # (五个币种)之后,"少一行"不再是从分母里消失,而是这条带计数的点名。
    "WEEKLY_LANDING_ROW_MISSING",
    # 2026-08-19(登记逃逸 5):主线标题的「(影响 …)」子句此前没有任何代码读它。
    # 比对池改按它扩;标题缺该子句的主线扩不了池,必须带计数出声。
    "WEEKLY_THEME_SCOPE_MISSING",
    # 周报:数字归属结构性不适用 / 无 --digest 时 ③ 判不了锚点。
    "WEEKLY_NUMBER_ATTRIBUTION_NOT_APPLICABLE",
    # 结构化字段之前登记的条目没有 `claim`,判不了也不该判红;但"没查"与
    # "查过且全过"必须可分辨,故带计数声明。
    "DECISION_CLAIM_ABSENT_SKIPPED",
    # 复盘句逐字引用的正向回执与它唯一的跳过态(复盘节标题重名)。
    "REVIEW_SENTENCE_CHECKED", "REVIEW_SENTENCE_SKIPPED_AMBIGUOUS",
    "WEEKLY_ASSUMPTION_ANCHOR_SKIPPED_NO_DIGEST",
    # 决策日志:未提供路径 / 日志里没有该日期该币种的条目。
    # `DECISION_LOG_ABSENT_SKIPPED` 与 `PRIOR_PERIOD_ABSENT_SKIPPED`
    # (在 LEGACY_CODES 里)**都没有被删**,2026-08-14 只是从 CLI 层挪进了
    # `check_daily` 本体:CLI 侧那两条 fail-open 收成了 rc=2,而"库调用方传
    # None"仍是可达的合法形态,由谁跳过谁出声。删掉它们才是错的 —— 那等于
    # 让别的调用方静默跳过。
    "DECISION_LOG_ABSENT_SKIPPED", "DECISION_LOG_NO_ENTRY",
    # 2026-08-14:「要点表 ⊆ 快照」被显式关掉时的带计数声明。它是
    # `--no-strict-brief` 存在的全部理由 —— 弱化可以,静默不行。
    "STRICT_BRIEF_DISABLED",
})
# ---- CLI 用法错误码(rc=2,走 stderr,不带处置)----
# 与违规码/声明码都不同:它在**跑校验之前**就把命令拦下来了,没有"被查对象"
# 可言,也就没有"改报告还是改脚本"的处置可选 —— 消息本身就是处置(一整行
# 可复制粘贴的正确命令行),由 DailyModeRequiresTheStrongFormTest 逐条守。
CLI_USAGE_CODES = frozenset({"DAILY_REQUIRED_OPTION_MISSING"})
# 这一层**之外**的既有码,写死在这里只为让上面两张表闭合:
# 「全部码 = 既有 ∪ VERDICT ∪ 本层」,新增任何码都必须显式入某一张表。
LEGACY_CODES = frozenset({
    "SNAPSHOT_MALFORMED", "SECTION_MISSING", "SECTION_TOO_LONG",
    "SUMMARY_TOO_LONG", "GAPS_NOT_DISCLOSED", "GAPS_MISMATCH", "GAP_OMITTED",
    "NUMBER_UNTRACEABLE", "BRIEF_NUMBER_UNTRACEABLE",
    "BRIEF_REVIEW_BLOCK_MALFORMED", "BRIEF_REVIEW_BLOCK_SKIPPED",
    "PRIOR_PERIOD_SECTION_MISSING", "PRIOR_PERIOD_BOILERPLATE",
    "PRIOR_PERIOD_SKIPPED_NO_SECTION", "PRIOR_PERIOD_ABSENT_SKIPPED",
    "THEME_TOO_MANY", "DATE_STRUCTURE", "COVERAGE_MISSING",
    "COVERAGE_GAP_DATES", "CURRENCY_MISSING", "REVIEW_TOKEN_MISSING",
    "WEEKLY_DIGEST_ABSENT_SKIPPED",
})


class NewLayerCodeInventoryFrozenTest(unittest.TestCase):
    """Minor 10:码清单冻结此前**只覆盖 `VERDICT_*`** —— 五个新码与它们的
    声明码不在任何冻结表里,于是"新增码必须同时入表"这句话对它们不成立,
    悄悄加一个码、或悄悄改一条处置,没有任何断言会红。

    这一条把冻结扩到全清单:`_emitted_codes` 扫出来的**全部**码,必须恰好
    等于三张表的并集。
    """

    def test_the_full_code_inventory_is_frozen(self):
        found = _emitted_codes(check_report.__file__)
        want = (set(NEW_LAYER_VIOLATION_DISPOSITION) | set(NEW_LAYER_NOTE_CODES)
                | set(LEGACY_CODES) | set(VERDICT_VIOLATION_DISPOSITION)
                | set(VERDICT_NOTE_CODES) | set(CLI_USAGE_CODES))
        self.assertEqual(found, want,
                         "校验器的码清单与冻结表对不上;新增码必须同时入表")
        # 58 → 60(2026-08-14):STRICT_BRIEF_DISABLED(声明)与
        # DAILY_REQUIRED_OPTION_MISSING(CLI 用法错误)。
        # 60 → 58(2026-08-14 同日,判断环豁免删除):删 3 条跳过声明、
        # 加 1 条正向回执 JUDGEMENT_RING_CHECKED。**本轮是本表第一次减项** ——
        # 减项与加项同规格,必须在这里显式记一笔,否则"码没了"与"码被漏登记"
        # 在这条断言上同形。
        # 58 → 60(2026-08-14,结构化观点):DECISION_CLAIM_NOT_SOURCED(违规)
        # 与 DECISION_CLAIM_ABSENT_SKIPPED(声明)。前者守"claim 的阈值与时限
        # 逐字溯源到散文 trigger",后者守"结构化字段之前的条目没查过"这件事
        # 不被静默。
        # 60 → 63(2026-08-14,复盘句逐字引用):REVIEW_SENTENCE_NOT_QUOTED
        # (违规)+ REVIEW_SENTENCE_CHECKED(回执)+
        # REVIEW_SENTENCE_SKIPPED_AMBIGUOUS(跳过态)。
        # 63 → 65(2026-08-15,失效条件/翻转指标解耦):删 1 条只声明的
        # FLIP_INDICATOR_TABLE_COLUMN_IS_FLIP,加 3 条 ——
        # INVALIDATION_COLUMN_IS_FLIP_RESTATED(违规)、
        # INVALIDATION_COLUMN_CHECKED(回执)、
        # WEEKLY_INVALIDATION_COLUMN_SKIPPED(周报侧取不到宿主时的跳过态)。
        # 65 → 70(2026-08-15 第二轮,第 4 列从零求值到有判据):加 4 条违规
        # (INVALIDATION_COLUMN_VACUOUS / …_MIRRORS_TRIGGER /
        #  …_FLIP_HOST_MISSING / WEEKLY_THEME_ATTRIBUTION_UNKNOWN)
        # 与 1 条声明(WEEKLY_LANDING_ROW_MISSING)。
        # 70 → 73(2026-08-19,读数期号披露):
        # ASSUMPTION_VINTAGE_UNDISCLOSED(违规)+ ASSUMPTION_VINTAGE_CHECKED
        # (回执)+ ASSUMPTION_VINTAGE_SKIPPED_NO_LAG(跳过态)。三条一起进,
        # 因为"判了几个组合""哪些判不了"必须与违规同批出声。
        # 73 → 74(2026-08-19,登记逃逸 6 的另一半):OVERVIEW_ROW_ABSENT。
        # 只加违规、不加声明 —— 「缺了哪几行」由既有的 OVERVIEW_ROW_MISSING
        # 与 INVALIDATION_COLUMN_CHECKED 的丢行子句负责,再加一条会把同一件事
        # 说三遍。
        # 74 → 75(2026-08-19,登记逃逸 8):DECISION_TRIGGER_TRUNCATED_DEADLINE。
        # 只加违规:「查了几个币种」由既有的 DECISION_LOG_NO_ENTRY 声明承担,
        # 这条码与 DECISION_TRIGGER_NOT_SOURCED 共用同一个循环与同一个分母。
        # 75 → 76(2026-08-19,登记逃逸 5):WEEKLY_THEME_SCOPE_MISSING(声明)。
        # 只加声明不加违规:抄袭本身由既有的 INVALIDATION_COLUMN_IS_FLIP_RESTATED
        # 判,本轮改的是它的**比对池**,不是新增一类违规。
        # 76 → 77(2026-08-21):BIS_ATTRIBUTION_MISSING。只加违规不加声明 ——
        # 前件(快照里有 BIS 序列)不成立时本码整条不适用,没有"跳过"这一态。
        self.assertEqual(len(want), 77, len(want))

    def test_every_new_layer_disposition_constant_exists_and_is_distinct(self):
        """七条处置**互不相同**:两条码共用一条处置时,"带的是它自己那一条"
        这句断言就失去分辨力。"""
        texts = [getattr(check_report, name)
                 for name in NEW_LAYER_VIOLATION_DISPOSITION.values()]
        for t in texts:
            self.assertTrue(t.startswith("处置:"), t)
        self.assertEqual(len(set(texts)), len(texts), texts)

    def test_each_new_layer_code_carries_its_own_disposition(self):
        """逐码处置对应:每条违规行**行尾恰是它自己那一条**处置,且不含
        另外六条中的任何一条。与 `assert_own_disposition` 同规格 ——
        只断言"带了某条处置"时,把六条互相对调照样全绿。"""
        seen = set()
        for label, out in self._stdouts():
            for raw in out.splitlines():
                line = raw.lstrip(" -").rstrip()
                m = re.match(r"([A-Z][A-Z0-9_]+):", line)
                if not m or m.group(1) not in NEW_LAYER_VIOLATION_DISPOSITION:
                    continue
                code = m.group(1)
                want = getattr(check_report,
                               NEW_LAYER_VIOLATION_DISPOSITION[code])
                self.assertTrue(line.endswith(want),
                                "%s:%s 的处置不是它自己那一条:%s"
                                % (label, code, line))
                for other_code, other_name in \
                        NEW_LAYER_VIOLATION_DISPOSITION.items():
                    if other_code != code:
                        self.assertNotIn(getattr(check_report, other_name),
                                         line, "%s 行里混入了 %s 的处置"
                                         % (code, other_code))
                seen.add(code)
        self.assertEqual(seen, set(NEW_LAYER_VIOLATION_DISPOSITION),
                         "有映射了处置却没有任何用例触发的码")

    def _stdouts(self):
        """两次**真 CLI**(生产 argv 形状),覆盖七个码。"""
        summary = ["- 摘要写了 0.4321 这个数。", "- 泰铢一档写成 60.843。"]
        out = []
        for label, report in (("no-decoy", amb_report()),
                              ("decoy", amb_report(decoy=True))):
            report = report.replace("- 摘要写了 0.4321 这个数。",
                                    "\n".join(summary))
            with tempfile.TemporaryDirectory() as tmp:
                argv, _ = daily_files(
                    tmp, report_text=report, snapshot_text=amb_snap(),
                    brief_text=MAP_BRIEF,
                    prior_text=map_report(prior_line=PRIOR_LINE_PREV),
                    extra=("--mode", "daily"))
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    check_report.main(argv)
                out.append((label, buf.getvalue()))
        # 第三次:决策日志那一条。它的宿主是**速览表**,而上面两份 fixture
        # 的速览表是 `| 币种 | 方向 |` 两列(走 OVERVIEW_TABLE_COLUMN_MISMATCH),
        # 取不到「条件方向」格,所以必须单独喂一份带完整表头的报告 ——
        # 否则 DECISION_TRIGGER_NOT_SOURCED 只有映射、没有任何用例触发。
        with tempfile.TemporaryDirectory() as tmp:
            drifted = DECISION_LOG.replace("若 C 升破 60.9 → 关注丙(T+2)",
                                           "日志里另写了一版触发条件")
            argv, _ = daily_files(tmp, report_text=OVERVIEW_REPORT,
                                  log_text=drifted, extra=("--mode", "daily"))
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                check_report.main(argv)
            out.append(("decision-log", buf.getvalue()))
        # 第四次:结构化观点那一条。宿主同为速览表那份报告,但违规在**日志
        # 内部**(claim 的阈值与散文 trigger 对不上),所以要另喂一份日志 ——
        # 否则 DECISION_CLAIM_NOT_SOURCED 只有映射、没有任何用例触发。
        with tempfile.TemporaryDirectory() as tmp:
            bad = json.loads(json.dumps(CLAIM_OK))
            bad["legs"][0]["threshold"] = "60.95"
            argv, _ = daily_files(
                tmp, report_text=OVERVIEW_REPORT,
                log_text=claim_log(bad, trigger="若 C 升破 60.9 → 关注丙(T+2)"),
                extra=("--mode", "daily"))
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                check_report.main(argv)
            out.append(("decision-claim", buf.getvalue()))
        # 第五次:复盘句没被逐字抄进正文。宿主是要点表的复盘材料块 + 报告的
        # 复盘节,与上面四份 fixture 都不同,必须单独喂一份。
        with tempfile.TemporaryDirectory() as tmp:
            brief = (BRIEF + "\n" + check_report.REVIEW_BLOCK_HEADING + "\n\n"
                     + "- PHP | 观点日 2026-08-09 | 情景: s | 触发条件: t"
                       " | 复盘句: 2026-08-09 PHP 命中(时限 T+1、按 1 个运行日计)"
                       " | 结论: 命中\n")
            argv, _ = daily_files(
                tmp, report_text=make_report(review="- 这次算命中。"),
                brief_text=brief, extra=("--mode", "daily"))
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                check_report.main(argv)
            out.append(("review-quote", buf.getvalue()))
        # 第六次:速览「失效条件」格照抄了该币种节的翻转指标。宿主同为速览表
        # 那份报告,但它的币种节原本只有一句"正文。"、判不出翻转指标句 ——
        # 必须补一个判断环进去,否则 INVALIDATION_COLUMN_IS_FLIP_RESTATED
        # 只有映射、没有任何用例触发。
        with tempfile.TemporaryDirectory() as tmp:
            # 2026-08-15 第二轮起 OVERVIEW_REPORT 的第 4 列本身已是合规形态
            # (带自己的时限),所以这里要**把它改回抄袭形态**才钓得到这条码。
            restated = OVERVIEW_REPORT.replace(
                "| 甲一次都没有升破 60.843(时限:2026-08-27) |",
                "| 甲位回落 60.843(T+3) |").replace(
                "## 美元(USD)\n正文。",
                "## 美元(USD)\n**分歧与判断**:关键假设 60.843 未变。"
                "替代解释乙。翻转指标:甲位回落 60.843(T+3)。")
            argv, _ = daily_files(tmp, report_text=restated,
                                  extra=("--mode", "daily"))
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                check_report.main(argv)
            out.append(("invalidation-column", buf.getvalue()))
        # 第六次半:关键假设拿带滞后的读数当锚点却没写期号。宿主是币种节的
        # 判断环 + 快照的 macro 行(要带 lag_months/period),与上面几份 fixture
        # 都不同 —— 否则 ASSUMPTION_VINTAGE_UNDISCLOSED 只有映射、没有用例触发。
        with tempfile.TemporaryDirectory() as tmp:
            ring = ("关键假设是 6.362922 这一档通胀仍主导定价;不成立时利差失效。"
                    "替代解释:比索走弱是美元一端在统一定价"
                    "(其翻转指标:泰铢同步升破 35.2)。"
                    "翻转指标:参考价回落至 60.9 一侧(T+3)。")
            argv, _ = daily_files(
                tmp, report_text=make_report(php_body=ring_body(ring)),
                snapshot_text=vintage_snap([PH_CPI_LAGGED]),
                extra=("--mode", "daily"))
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                check_report.main(argv)
            out.append(("assumption-vintage", buf.getvalue()))
        # 第六次三分之二:复现了 BIS 序列却没有来源声明。宿主是快照的 macro 节
        # 与报告全文,与上面几份都不同 —— 否则 BIS_ATTRIBUTION_MISSING 只有
        # 映射、没有任何用例触发。
        with tempfile.TemporaryDirectory() as tmp:
            argv, _ = daily_files(
                tmp, report_text=OVERVIEW_REPORT,
                snapshot_text=bis_snap([BIS_MACRO_ROW]),
                extra=("--mode", "daily"))
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                check_report.main(argv)
            out.append(("bis-attribution", buf.getvalue()))
        # 第六次七分之八:日志的 trigger 把时限截在登记之外。宿主同为速览表
        # 那份报告,但违规在日志与格的**差集**上 —— 否则
        # DECISION_TRIGGER_TRUNCATED_DEADLINE 只有映射、没有任何用例触发。
        with tempfile.TemporaryDirectory() as tmp:
            truncated = DECISION_LOG.replace("若 C 升破 60.9 → 关注丙(T+2)",
                                             "若 C 升破 60.9")
            argv, _ = daily_files(tmp, report_text=OVERVIEW_REPORT,
                                  log_text=truncated, extra=("--mode", "daily"))
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                check_report.main(argv)
            out.append(("trigger-truncated", buf.getvalue()))
        # 第六次四分之三:速览表少了一个**报告写了节**的币种的行。宿主是
        # 速览表那份报告,但违规在表的行集上,与上面几份都不同 —— 否则
        # OVERVIEW_ROW_ABSENT 只有映射、没有任何用例触发。
        with tempfile.TemporaryDirectory() as tmp:
            argv, _ = daily_files(
                tmp,
                report_text=OVERVIEW_REPORT.replace("| USD |", "| USDX |", 1),
                extra=("--mode", "daily"))
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                check_report.main(argv)
            out.append(("overview-row-absent", buf.getvalue()))
        # 第七/八/九次:2026-08-15 第二轮补的三条日报侧码。三条的宿主都是
        # 速览表那份报告,但触发形态互不相同 —— 空洞占位 / 第 2 列的机械否定 /
        # 宿主段取不到本判断的翻转指标,所以各喂一份。
        for label, cell, usd_section in (
                ("invalidation-vacuous", "无", None),
                ("invalidation-mirror", "若 A 升破 60.843 → 关注甲(T+2)", None),
                ("invalidation-flip-host", "丁位升破 61.1",
                 "## 美元(USD)\n**分歧与判断**:关键假设 60.843 未变。"
                 "替代解释乙(其翻转指标:丁位升破 61.1)。"
                 "反转指标:甲位回落(T+2)。")):
            rep = OVERVIEW_REPORT.replace(
                "| 甲一次都没有升破 60.843(时限:2026-08-27) |", "| %s |" % cell)
            if usd_section:
                rep = rep.replace("## 美元(USD)\n正文。", usd_section)
            with tempfile.TemporaryDirectory() as tmp:
                argv, _ = daily_files(tmp, report_text=rep,
                                      extra=("--mode", "daily"))
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    check_report.main(argv)
                out.append((label, buf.getvalue()))
        # 第十次:周报侧那一条(落点表「主线归属」写了一条不存在的主线)。
        # 它是本表里**唯一**走周报 CLI 的码 —— 日报没有主线段。
        with tempfile.TemporaryDirectory() as tmp:
            wp = os.path.join(tmp, "w.md")
            with open(wp, "w", encoding="utf-8") as f:
                f.write(weekly_landing(
                    "T+3 内比索一次都没有退回 60.75 一侧(时限:2026-08-27)",
                    belong="主线九"))
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                check_report.main([wp, "--mode", "weekly"])
            out.append(("weekly-theme-attribution", buf.getvalue()))
        return out

    def test_every_cli_usage_code_is_reachable_and_carries_no_disposition(self):
        """CLI 用法错误码也要闭合,并且**与违规码分家**。

        ① 表里列了却打不出来的码 = 死码,与"打印通过但没查"同族;
        ② 它**不带「处置:」** —— 消息本身就是处置(一整行可执行的命令行)。
           混进 `NEW_LAYER_VIOLATION_DISPOSITION` 会让"逐码处置对应"那条
           断言对着一个根本没有处置常量的码空转,而那条断言是本仓最贵的
           几条之一。
        """
        with open(check_report.__file__, encoding="utf-8") as f:
            src = f.read()
        for code in CLI_USAGE_CODES:
            self.assertIn('"%s: ' % code, src, "%s 是死码,没有任何地方打出它"
                          % code)
        msg = check_report.daily_required_options_error(
            "reports/daily/2026-08-14.md", "data/2026-08-14.json",
            None, None, None, ["--brief", "--prior", "--decision-log"])
        self.assertNotIn("处置:", msg)
        # 消息里必须**恰好一行**是可复制的命令行(多一行读者就得猜跑哪条)
        runnable = [x for x in msg.splitlines()
                    if x.startswith("python3 scripts/check_report.py")]
        self.assertEqual(len(runnable), 1, msg)
        # 三个必给项的值都补齐了,一个尖括号占位符都不许剩(日期认得出时)
        self.assertNotIn("<", runnable[0], runnable[0])
        for opt, _ in check_report.DAILY_REQUIRED_OPTIONS:
            self.assertIn(opt + " ", runnable[0], opt)

    def test_every_new_layer_note_code_is_reachable(self):
        """声明码也要闭合:表里列了却没有任何路径打得出来的码 = 死码,
        与"打印通过但没查"是同一族问题。"""
        with open(check_report.__file__, encoding="utf-8") as f:
            src = f.read()
        for code in NEW_LAYER_NOTE_CODES:
            self.assertIn('"%s: ' % code, src.replace("\n", " ").replace(
                '"\n', '"').replace("  ", " ") or src, code)


# ==================== 本轮:三个「强制力够不着」的洞 + 一处散文零强制 =========
#
# 上一轮把每处放行/不可达/整层不查都改成打印声明,声明照出了三个洞。
# 本轮把它们接上。四条的**判据来源**逐条写在各自的类里,不写在这里 ——
# 一处总述会与实现漂移,而漂移后没有断言看得见。

OVERVIEW_REPORT = """# 外汇日报 2026-08-10

## 执行摘要
- 摘要第 1 条

## 速览

| 币种 | 条件方向(时限) | 核心依据 | 失效条件 |
| --- | --- | --- | --- |
| USD | 若 A 升破 60.843 → 关注甲(T+2) | 依据甲 | 甲一次都没有升破 60.843(时限:2026-08-27) |
| EUR | 若 B 升破 0.921 → 关注乙(T+2) | 依据乙 | 乙一次都没有升破 0.921(时限:2026-08-27) |
| PHP | 若 C 升破 60.9 → 关注丙(T+2) | 依据丙 | 丙一次都没有升破 60.9(时限:2026-08-27) |
| THB | 若 D 升破 35.2 → 关注丁(T+2) | 依据丁 | 丁一次都没有升破 35.2(时限:2026-08-27) |
| BRL | 若 E 升破 5.43 → 关注戊(T+2) | 依据戊 | 戊一次都没有升破 5.43(时限:2026-08-27) |

## 美元(USD)
正文。

## 复盘
- 首次运行,无历史观点可复盘

## 数据缺漏
无
"""


class OverviewTableParseTest(unittest.TestCase):
    """速览表按**表头列名**解析,不得按固定列序号硬取。

    判据来源:`reports/daily/2026-08-14.md:11-16` 的实际表结构
    `| 币种 | 条件方向(时限) | 核心依据 | 失效条件 |`。

    ---- 为什么必须按列名 ----
    按序号硬取时,列序一变就**错位取值**且完全静默:把「核心依据」当成
    「失效条件」比对,判定照跑、结论全错。列名解析让"列序变了"变成一条
    带计数的声明,而不是一次错位。
    """

    def test_rows_are_keyed_by_currency_and_column_name(self):
        secs = check_report.sections(OVERVIEW_REPORT)
        rows = check_report.overview_rows(secs)
        self.assertEqual(set(rows), set(check_report.CURRENCIES))
        self.assertEqual(rows["PHP"][check_report.OVERVIEW_COL_TRIGGER],
                         "若 C 升破 60.9 → 关注丙(T+2)")
        self.assertEqual(rows["PHP"][check_report.OVERVIEW_COL_INVALIDATION],
                         "丙一次都没有升破 60.9(时限:2026-08-27)")

    def test_column_order_change_is_followed_not_mis_indexed(self):
        """把「核心依据」与「失效条件」两列**对调**(表头与数据行一起调):
        按列名解析必须仍然取到失效条件那一格;按序号硬取则会取到依据。"""
        cell = "丙一次都没有升破 60.9(时限:2026-08-27)"
        swapped = OVERVIEW_REPORT.replace(
            "| 币种 | 条件方向(时限) | 核心依据 | 失效条件 |",
            "| 币种 | 条件方向(时限) | 失效条件 | 核心依据 |")
        swapped = swapped.replace("| 依据丙 | %s |" % cell,
                                  "| %s | 依据丙 |" % cell)
        rows = check_report.overview_rows(check_report.sections(swapped))
        self.assertEqual(rows["PHP"][check_report.OVERVIEW_COL_INVALIDATION],
                         cell)

    def test_missing_column_declares_with_a_count(self):
        broken = OVERVIEW_REPORT.replace("| 核心依据 | 失效条件 |",
                                         "| 核心依据 | 没这一列 |")
        notes = []
        rows = check_report.overview_rows(check_report.sections(broken),
                                          notes=notes)
        self.assertEqual(rows, {})
        line = "\n".join(notes)
        self.assertIn("OVERVIEW_TABLE_COLUMN_MISMATCH", line)
        self.assertRegex(line, r"\d+")

    def test_missing_section_declares_with_a_count(self):
        notes = []
        rows = check_report.overview_rows(
            check_report.sections("# r\n\n## 执行摘要\n- 一\n"), notes=notes)
        self.assertEqual(rows, {})
        line = "\n".join(notes)
        self.assertIn("OVERVIEW_TABLE_SKIPPED", line)
        self.assertRegex(line, r"\d+")

    def test_missing_currency_row_declares_with_a_count(self):
        dropped = "\n".join(l for l in OVERVIEW_REPORT.splitlines()
                            if not l.startswith("| THB |"))
        notes = []
        rows = check_report.overview_rows(check_report.sections(dropped),
                                          notes=notes)
        self.assertNotIn("THB", rows)
        line = "\n".join(notes)
        self.assertIn("OVERVIEW_ROW_MISSING", line)
        self.assertIn("THB", line)
        self.assertRegex(line, r"\d+")


class FlipIndicatorReachabilityTest(unittest.TestCase):
    """② 的可达性:失效条件句的**两种落法**都要认得。

    ---- 实测口径(本轮,先跑后抄)----
    修前 `FLIP_INDICATOR_CHECK_UNREACHABLE` 在真实产物上:
    2026-08-13 5/5 个 full 体裁币种节判不出失效条件句;2026-08-14 2/5。
    根因是识别器只认**前缀式**「不成立时X」,而报告写的是:
      ① **后缀式**「……这条弱势腿不成立。」—— 标签在句尾,`_ring_payload`
         取标签之后的那一段,结果是空串,该句被当成"没有载荷"丢掉;
      ② 「……本判断**作废**。」—— 措辞根本不在标签表里。
    两条都不是"报告没写失效条件",是识别器认不出。与 e74134d
    「识别器认历史措辞」同一形制。
    """

    def test_suffix_form_yields_the_clause_before_the_label(self):
        s = "若下月加息后仍留有余地,-0.499 会被后续路径改写,这条弱势腿不成立。"
        got = check_report._ring_payload(s, check_report.INVALIDATION_LABELS)
        self.assertTrue(got, "后缀式失效条件句的载荷不得为空")
        self.assertIn("0499", got)

    def test_prefix_form_still_yields_the_clause_after_the_label(self):
        """前缀式一字不改 —— 后缀回退只在"标签之后为空"时才生效。"""
        s = "不成立时同一读数只剩这一条路径,美元反而走弱。"
        got = check_report._ring_payload(s, check_report.INVALIDATION_LABELS)
        self.assertIn("同一读数只剩这一条路径", got)
        self.assertNotIn("不成立时", got)

    def test_void_wording_is_recognised_as_an_invalidation_label(self):
        self.assertIn("作废", check_report.INVALIDATION_LABELS)

    def test_restated_flip_is_still_caught_through_the_suffix_form(self):
        """回退不得把 ② 变松:失效条件用后缀式写、翻转指标照抄它,仍要红。"""
        body = ("**分歧与判断**:关键假设是甲乙丙这一条继续成立;"
                "若不然,甲乙丙这一条不成立。替代解释:丁。"
                "翻转指标:甲乙丙这一条。")
        v, _ = check_report._check_one_ring("PHP", body, {"60.843"})
        self.assertTrue(any("FLIP_INDICATOR_IS_INVALIDATION_RESTATED" in x
                            for x in v), v)


RING_BODY = "**分歧与判断**:关键假设甲。替代解释乙。翻转指标:丙位回落(T+2)。"


class InvalidationColumnIsIndependentTest(unittest.TestCase):
    """2026-08-15:表里「失效条件」格与宿主段「翻转指标」句**必须是两件事**。

    ---- 这条码替换掉了什么 ----
    旧码 `FLIP_INDICATOR_TABLE_COLUMN_IS_FLIP` 是一条**只声明、不判定**的
    notes 行:它把"该列在 N/M 个币种上与翻转指标逐字相同"打进 stdout,却
    不改退出码。它之所以只能声明,是因为 SKILL 当时**要求**二者同源同字
    —— 任何"两者不得相同"的检查都会恒红。
    2026-08-15 SKILL 走 A 案解耦(失效条件 =「什么没发生就作废」、翻转指标
    =「什么一旦出现就改判」,两处不得写成同一句),那条要求没了,声明存在的
    理由随之没了。本码是旧要求的**反面**:重合即违规,退出码非 0。
    它同时是"解耦有没有真落地"的判据 —— 报告第 4 列若还抄着翻转指标,
    这条码当场红。

    ---- 与 ② `FLIP_INDICATOR_IS_INVALIDATION_RESTATED` 的分工 ----
    ② 比的是**同一段正文内两句**的关系(关键假设的「不成立/作废」半句 vs
    翻转指标句),本码比的是**表格与正文之间**。两者判的不是同一对字符串,
    所以不合并、也不互相取代。
    """

    def one(self, cell, bodies=(RING_BODY,), name="PHP", notes=None):
        # 第 3 位是同行「条件方向」格 —— 2026-08-15 第二轮补进 pairs,
        # ②③ 两条自身判据要拿它作参照(见 check_invalidation_independent)。
        # 这里给一个与各用例的 cell 无关的触发条件:本类只测 ①。
        return check_report.check_invalidation_independent(
            [(name, cell, "若 Z 升破 99.9 → 关注癸(时限:2026-08-27)",
              list(bodies))],
            check_report.INVALIDATION_SCOPE_DAILY, notes=notes)

    def test_a_column_identical_to_the_flip_is_a_violation(self):
        v = self.one("丙位回落(T+2)")
        self.assertTrue(
            any("INVALIDATION_COLUMN_IS_FLIP_RESTATED" in x for x in v), v)

    def test_punctuation_only_edits_do_not_get_past_it(self):
        """去标点空白后比对 —— 换个括号/顿号不算改写。"""
        v = self.one("丙位回落,T+2")
        self.assertTrue(
            any("INVALIDATION_COLUMN_IS_FLIP_RESTATED" in x for x in v), v)

    def test_a_column_that_is_a_substring_of_the_flip_is_a_violation(self):
        """互为子串也算重合:把翻转指标截半句填进表格是最省事的那条路。"""
        v = self.one("丙位回落")
        self.assertTrue(
            any("INVALIDATION_COLUMN_IS_FLIP_RESTATED" in x for x in v), v)

    def test_a_flip_that_is_a_substring_of_the_column_is_a_violation(self):
        """反方向同判:表格里在翻转指标外面套一层壳,重合照旧。"""
        v = self.one("丙位回落(T+2)且乙未出现")
        self.assertTrue(
            any("INVALIDATION_COLUMN_IS_FLIP_RESTATED" in x for x in v), v)

    def test_an_independent_column_passes(self):
        """「什么没发生就作废」写法:与「什么一旦出现就改判」不重合。"""
        v = self.one("T+2 内丙位一次都没有被触及")
        self.assertEqual(v, [], v)

    def test_the_violation_line_quotes_both_sides_and_its_own_disposition(self):
        line = self.one("丙位回落(T+2)")[0]
        self.assertIn("丙位回落(T+2)", line)
        self.assertTrue(line.endswith(check_report.DISPOSITION_INVALIDATION_COLUMN),
                        line)

    def test_the_receipt_counts_only_rows_where_both_sides_have_a_payload(self):
        """「查过」与「没得查」必须可分辨:一行缺格、一行宿主里没有翻转指标句,
        两行都不该算进分子,而分母是表里的全部行。"""
        notes = []
        trig = "若 Z 升破 99.9 → 关注癸(时限:2026-08-27)"
        v = check_report.check_invalidation_independent(
            [("USD", "T+2 内甲位一次都没有被触及", trig, [RING_BODY]),
             ("EUR", "", trig, [RING_BODY]),
             ("PHP", "T+2 内丙位一次都没有被触及", trig,
              ["**分歧与判断**:只有正文。"])],
            check_report.INVALIDATION_SCOPE_DAILY, notes=notes)
        # EUR 那一行空着 —— 2026-08-15 第二轮起它不再是"没得查"的静默态,
        # 而是 ② 的违规形态(空洞占位);① 仍然不算它的分子。
        # PHP 那一行取不到本判断的翻转指标 —— 同样由静默态改成响亮的失败关闭。
        self.assertEqual(sorted(x.split(":")[0] for x in v),
                         ["INVALIDATION_COLUMN_FLIP_HOST_MISSING",
                          "INVALIDATION_COLUMN_VACUOUS"], v)
        line = "\n".join(notes)
        self.assertIn("INVALIDATION_COLUMN_CHECKED", line)
        self.assertRegex(line, r"独立性 1/3")
        # PHP 那一行的宿主里一句翻转指标都没有 → ① 判不了(FLIP_HOST_MISSING),
        # 但 ②③ 与宿主无关,照判 —— 两层的分子因此不同。
        self.assertRegex(line, r"自身判据 2/3")

    def test_the_declaration_only_predecessor_is_gone(self):
        """旧码不许再**被打出去** —— 它与新码对同一对字符串给出相反口径:
        一个说"相同是 SKILL 规定的形态,只声明不判定",一个说"相同即违规"。
        两条同时在,stdout 上会一边放行一边判红。

        判据取 `_emitted_codes`(AST 里以 `码:` 开头的字符串字面量),
        **不是"全文零提及"**。这不是放宽:能改变退出码的只有被发出的码,
        而删除本身必须在源码里留下一笔说明(与冻结表那两次减项同规格),
        说明必然要点名被删的那个码 —— 拿全文子串当判据会逼着把理由删掉,
        下一个人就只看得到"这里少了点什么"。
        再发出它同时会被 `test_the_full_code_inventory_is_frozen` 抓住
        (它不在任何一张冻结表里),两条互为独立防线。
        """
        self.assertNotIn("FLIP_INDICATOR_TABLE_COLUMN_IS_FLIP",
                         _emitted_codes(check_report.__file__))
        self.assertFalse(hasattr(check_report,
                                 "check_overview_invalidation_column"))

    def test_the_judgement_has_exactly_one_implementation(self):
        """码字面量只准出现在唯一那个函数里 —— 日报与周报两条路径都落到它上面。
        判定复制两份后漂移是本仓库栽过的坑(与 `_check_one_ring` 同规格)。"""
        with open(check_report.__file__, encoding="utf-8") as f:
            tree = ast.parse(f.read())
        hosts = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            for sub in ast.walk(node):
                if (isinstance(sub, ast.Constant)
                        and isinstance(sub.value, str)
                        and sub.value.startswith(
                            "INVALIDATION_COLUMN_IS_FLIP_RESTATED:")):
                    hosts.add(node.name)
        self.assertEqual(hosts, {"check_invalidation_independent"}, hosts)


class DailyInvalidationColumnTest(unittest.TestCase):
    """日报整条路径:速览表第 4 列 → 该币种节的翻转指标。"""

    def report_with(self, usd_cell, usd_flip):
        rep = OVERVIEW_REPORT.replace(
            "| 甲一次都没有升破 60.843(时限:2026-08-27) |", "| %s |" % usd_cell)
        return rep.replace(
            "## 美元(USD)\n正文。",
            "## 美元(USD)\n**分歧与判断**:关键假设 60.843 未变。"
            "替代解释乙。翻转指标:%s。" % usd_flip)

    def run_cli(self, report):
        with tempfile.TemporaryDirectory() as tmp:
            argv, _ = daily_files(tmp, report_text=report,
                                  extra=("--mode", "daily"))
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = check_report.main(argv)
            return rc, buf.getvalue()

    def test_copying_the_flip_into_the_column_fails_the_report(self):
        rc, out = self.run_cli(
            self.report_with("甲位回落(T+2)", "甲位回落(T+2)"))
        self.assertIn("INVALIDATION_COLUMN_IS_FLIP_RESTATED", out)
        self.assertNotEqual(rc, 0)

    def test_an_independent_column_leaves_a_counted_receipt(self):
        rc, out = self.run_cli(
            self.report_with("甲一次都没有升破 60.843(时限:2026-08-27)",
                             "甲位回落(T+2)"))
        self.assertNotIn("INVALIDATION_COLUMN_IS_FLIP_RESTATED", out)
        self.assertIn("INVALIDATION_COLUMN_CHECKED", out)


class WeeklyInvalidationColumnTest(unittest.TestCase):
    """周报侧同构:`## 各币种一周落点` 表的「失效条件」列 ↔ 归属主线的
    `**翻转指标(T+N)**` 段。

    宿主由表里的**「主线归属」列**指定,不靠猜:猜就是编造(与
    `check_weekly_judgement_ring` 拒绝"凭标题猜该不该有判断环"同一条理由)。
    """

    def weekly(self, cell, belong="主线一"):
        return weekly_landing(cell, belong)

    def test_copying_the_theme_flip_into_the_column_is_a_violation(self):
        v = check_report.check_weekly(
            self.weekly("下一次定盘比索退回 60.9 之下"))
        self.assertTrue(
            any("INVALIDATION_COLUMN_IS_FLIP_RESTATED" in x for x in v), v)

    def test_an_independent_column_passes_with_a_receipt(self):
        notes = []
        v = check_report.check_weekly(
            self.weekly("T+3 内比索一次都没有退回 60.9 之下"), notes=notes)
        self.assertEqual(
            [x for x in v if "INVALIDATION_COLUMN_IS_FLIP_RESTATED" in x], [])
        self.assertIn("INVALIDATION_COLUMN_CHECKED", "\n".join(notes))

    def test_a_theme_claiming_this_currency_is_a_host_even_if_unattributed(self):
        """**本断言 2026-08-19 改口。**

        原文是「归属写的是主线二时,拿的就不该是主线一那一段的翻转指标」——
        而这正是 docs/known-gate-escapes.md 逃逸 5 的形态本身:宿主完全由
        报告自己写的归属格决定,于是把归属改挂到另一条**同样覆盖本币种**的
        真实主线上,抄袭对象就移出了比对池,`IS_FLIP_RESTATED` 消失而回执
        照印「独立性 5/5」。

        现在比对池 = 归属格点名的段 ∪ 标题「影响」子句点了本币种的段。
        这里 PHP 行抄的是主线一的翻转指标,而主线一的标题写着「(影响 PHP)」
        —— 归属格写什么都躲不掉。"宿主由归属列指定"这句话保留它仅剩的那半:
        归属格必须点到真实主线(`WEEKLY_THEME_ATTRIBUTION_UNKNOWN`)。
        """
        v = check_report.check_weekly(
            self.weekly("下一次定盘比索退回 60.9 之下", belong="主线二"))
        self.assertTrue(
            any("INVALIDATION_COLUMN_IS_FLIP_RESTATED" in x for x in v), v)

    def test_a_missing_landing_table_is_declared_with_counts(self):
        """WEEKLY_RING 那份 fixture 写的是 `## 各币种一周归因`(散文,不是表)
        —— 取不到宿主时必须出声,而不是裸 PASS。"""
        notes = []
        check_report.check_weekly(WEEKLY_RING, notes=notes)
        line = "\n".join(notes)
        self.assertIn("WEEKLY_INVALIDATION_COLUMN_SKIPPED", line)
        self.assertRegex(line, r"\d")


WEEKLY_RING = """# 外汇周报 2026-W33

> 覆盖日报:3 份(2026-08-07, 2026-08-08, 2026-08-10);缺失日期:无

## 本周主线

### 主线一:比索这条腿(影响 PHP)
**宏观背景**:参考价 60.843。
**关键假设**:参考价 60.843 在下一次定盘前不动;不成立时这条线退回按本地驱动重估。
**替代解释**:承接厚度(它自己的翻转指标:下一次定盘次序翻过来)。
**翻转指标(T+3)**:下一次定盘比索退回 60.9 之下。

### 主线二:泰铢那条腿(影响 THB)
**宏观背景**:参考价 35.2。
**关键假设**:参考价 35.2 之下已无政策空间;不成立时这条线整条作废。
**替代解释**:输入性成本(它自己的翻转指标:能源价回落而泰铢不动)。
**翻转指标(T+3)**:下一次定盘泰铢退回 35.2 之下。

## 各币种一周归因
USD / EUR / PHP 周涨跌 -0.192%%,区间 60.75–60.867;%s。事件:%s;公告:%s / THB / BRL

## 复盘汇总
- 命中 1、未命中 0、无法判定 15、未到期 4、未复盘 6

## 本周关注
- 关注定盘更新

## 缺漏汇总
- 无
""" % (FIX_PHP, ART_PHP, OFF_PHP)

# 周报数字白名单 = 聚合文件 ∪ 当周日报 ∪ 小整数。fixture 的主线段引了三个
# 参考价,它们来自日报那一侧,所以测试必须把日报正文一并传入 —— 否则红的是
# NUMBER_UNTRACEABLE,与本类要测的判断环无关。
RING_DAILY = ["PHP 60.843 60.9", "THB 35.2"]


def weekly_landing(cell, belong="主线一"):
    """在 WEEKLY_RING 之上补一张 `## 各币种一周落点` 表。

    单独建而不是往 WEEKLY_RING 里塞 `%s`:WEEKLY_RING 已经被 `%` 格式化过
    一轮,正文里留着一个真实的 `%`(周涨跌),再套一层格式化会当场炸。
    """
    row = ("| PHP | %s | 周涨跌 -0.192%% | 若比索升破 60.9 → 关注甲(T+3) | %s |"
           % (belong, cell))
    table = "\n".join(("## 各币种一周落点", "",
                       "| 币种 | 主线归属 | 周内价格落点 | 下周判断(时限)"
                       " | 失效条件 |",
                       "| --- | --- | --- | --- | --- |", row, "", ""))
    return WEEKLY_RING.replace("## 复盘汇总", table + "## 复盘汇总")


class WeeklyJudgementRingTest(unittest.TestCase):
    """判断环三码在**周报模式**也跑。

    ---- 修前实测(先跑后抄)----
    `python3 scripts/check_report.py --mode weekly reports/weekly/2026-W33.md
     --digest … --daily …×5` 打出:
      WEEKLY_JUDGEMENT_LAYER_SKIPPED: …本份周报里有 27 处判断环标签
      (关键假设 8、替代解释 5、翻转指标 14)未校验
    也就是三码在周报上的执行次数是 **0**。

    ---- 取数方式:H3 主线段,不是币种节 ----
    实测 `reports/weekly/2026-W33.md` 的结构:`## 本周主线` 之下是五个
    `### 主线N:…(影响 …)` 子节,每个子节自带
    **关键假设 / 替代解释 / 翻转指标** 三件。币种在周报里没有自己的节
    (`## 各币种一周落点` 是一张表),所以判断环的宿主是**主线段**。

    ---- 判定逻辑只有一份 ----
    走的是与日报**同一个** `_check_one_ring`,两侧只有"取哪些段"不同。
    判定复制两份后漂移是本仓库栽过的坑(见 scripts/fixings.py)。

    ---- 闸门 ----
    日报侧的闸门是 `derived.body_plan` 的体裁,周报侧没有这个东西。
    这里用**结构闸门**:`## 本周主线` 节之下的 `### ` 子节。理由是它
    与"判断环写在哪里"是同一件事 —— 有主线段才有判断环,没有主线段时
    三码无处可判。闸门不成立时照旧打 `WEEKLY_JUDGEMENT_LAYER_SKIPPED`,
    带计数。
    """

    def test_ring_codes_run_on_theme_subsections(self):
        broken = WEEKLY_RING.replace(
            "**替代解释**:承接厚度(它自己的翻转指标:下一次定盘次序翻过来)。\n", "")
        v = check_report.check_weekly(broken, DIGEST, RING_DAILY)
        self.assertTrue(any("JUDGEMENT_RING_INCOMPLETE" in x and "替代解释" in x
                            for x in v), v)

    def test_restated_flip_is_caught_in_weekly(self):
        bad = WEEKLY_RING.replace(
            "**翻转指标(T+3)**:下一次定盘比索退回 60.9 之下。",
            "**翻转指标(T+3)**:这条线退回按本地驱动重估。")
        v = check_report.check_weekly(bad, DIGEST, RING_DAILY)
        self.assertTrue(any("FLIP_INDICATOR_IS_INVALIDATION_RESTATED" in x
                            for x in v), v)

    def test_unanchored_assumption_is_caught_in_weekly(self):
        bad = WEEKLY_RING.replace(
            "**关键假设**:参考价 60.843 在下一次定盘前不动;不成立时这条线退回按本地驱动重估。",
            "**关键假设**:市场结构不会变;不成立时这条线整条作废。")
        v = check_report.check_weekly(bad, DIGEST, RING_DAILY)
        self.assertTrue(any("ASSUMPTION_UNANCHORED" in x for x in v), v)

    def test_compliant_weekly_with_rings_still_passes(self):
        self.assertEqual(check_report.check_weekly(WEEKLY_RING, DIGEST, RING_DAILY), [])

    def test_gate_not_met_declares_with_a_count(self):
        """没有 H3 主线子节时照旧声明,并带计数 —— 与修前同一条码。"""
        notes = []
        check_report.check_weekly(WEEKLY_OK, DIGEST, notes=notes)
        line = "\n".join(notes)
        self.assertIn("WEEKLY_JUDGEMENT_LAYER_SKIPPED", line)
        self.assertRegex(line, r"\d+ 处判断环标签")

    def test_number_attribution_inapplicability_is_declared_with_a_count(self):
        """数字归属两码在周报上**结构性不适用**,必须把"为什么"写成带计数
        的声明,不能只是不跑。

        理由(实测):两码的判据是"这个数出自**哪个币种的快照切片**",而
        周报的输入里根本没有按币种分键的快照 —— `--digest` 是周度聚合、
        `--daily` 是已过溯源的日报正文,两者都不提供 `rates[币种]` /
        `derived.real_rate[经济体]` 这种切片。没有切片就判不出归属。
        """
        notes = []
        check_report.check_weekly(WEEKLY_RING, DIGEST, RING_DAILY, notes=notes)
        line = "\n".join(notes)
        self.assertIn("WEEKLY_NUMBER_ATTRIBUTION_NOT_APPLICABLE", line)
        self.assertIn("NUMBER_WRONG_SECTION", line)
        self.assertRegex(line, r"\d+")

    def test_assumption_anchor_without_digest_declares_with_a_count(self):
        """没有 --digest 时白名单建不起来,③ 判不了锚点 —— 出声,不静默。"""
        notes = []
        check_report.check_weekly(WEEKLY_RING, notes=notes)
        line = "\n".join(notes)
        self.assertIn("WEEKLY_ASSUMPTION_ANCHOR_SKIPPED_NO_DIGEST", line)
        self.assertRegex(line, r"\d+")

    def test_the_ring_judgement_has_exactly_one_implementation(self):
        """判定逻辑只有一份:周报侧不得另写一套。

        判据是**源码级**的:`_check_one_ring` 是三码字符串唯一的产地,
        日报与周报两条路径都必须落到它上面。另写一套时三个码会在别的函数
        里再出现一次,这条断言就红。
        """
        with open(check_report.__file__, encoding="utf-8") as f:
            tree = ast.parse(f.read())
        owners = {}
        for fn in [n for n in ast.walk(tree)
                   if isinstance(n, ast.FunctionDef)]:
            for node in ast.walk(fn):
                if isinstance(node, ast.Constant) \
                        and isinstance(node.value, str):
                    for code in ("JUDGEMENT_RING_INCOMPLETE",
                                 "FLIP_INDICATOR_IS_INVALIDATION_RESTATED",
                                 "ASSUMPTION_UNANCHORED"):
                        if node.value.startswith(code + ":"):
                            owners.setdefault(code, set()).add(fn.name)
        self.assertEqual(owners, {c: {"_check_one_ring"} for c in owners},
                         "判断环三码的产地不唯一:%s" % owners)
        self.assertEqual(len(owners), 3, owners)


DECISION_LOG = "\n".join([
    json.dumps({"date": "2026-08-10", "currency": "PHP",
                "scenario": "情景丙", "trigger": "若 C 升破 60.9 → 关注丙(T+2)",
                "watch_direction": "up"}, ensure_ascii=False),
    json.dumps({"date": "2026-08-10", "currency": "USD",
                "scenario": "情景甲", "trigger": "若 A 升破 60.843 → 关注甲(T+2)",
                "watch_direction": None}, ensure_ascii=False),
]) + "\n"


CLAIM_OK = {"horizon": {"kind": "running_days", "n": 2, "quote": "T+2"},
            "legs": [{"currency": "PHP", "field": "primary", "op": "gt",
                      "threshold": "60.9"}]}


def claim_log(claim=None, **over):
    entry = {"date": "2026-08-10", "currency": "PHP", "scenario": "情景丙",
             "trigger": "若 C 升破 60.9 → 关注丙(T+2)", "watch_direction": "up",
             "claim": json.loads(json.dumps(CLAIM_OK)) if claim is None else claim}
    entry.update(over)
    return json.dumps(entry, ensure_ascii=False) + "\n"


class ReviewSentenceQuotedInBodyTest(unittest.TestCase):
    """`REVIEW_SENTENCE_NOT_QUOTED` —— 要点表里每条**结论行**的复盘句,
    必须逐字出现在报告的复盘节里。

    ---- 为什么这一码必须存在 ----
    「结论由脚本给出、报告逐字引用」此前**只是 SKILL 里的散文**,校验器对它
    零强制:脚本算出的结论走到报告边界就没人看着了,LLM 改一个字、漏抄一条、
    或者干脆自己写一个结论词,六份产物照样全绿。本仓库为此栽过 13 次同型,
    教训是"prompt 禁令堵不住,要改成不变量"。

    判据是**整句逐字包含**,不是逐词:改一个字符即红。
    """

    BRIEF = (BRIEF + "\n" + check_report.REVIEW_BLOCK_HEADING + "\n\n"
             + "- PHP | 观点日 2026-08-09 | 情景: s | 触发条件: t"
               " | 复盘句: 2026-08-09 PHP 命中(时限 T+1、按 1 个运行日计)"
               " | 结论: 命中\n")

    def _report(self, review_body):
        return make_report(review=review_body)

    def test_verbatim_quote_passes(self):
        v = check_report.check_daily(
            self._report("- 2026-08-09 PHP 命中(时限 T+1、按 1 个运行日计)"
                         " —— 该观点的分歧点已被检验。"),
            SNAP_TEXT, self.BRIEF)
        self.assertFalse([x for x in v if "REVIEW_SENTENCE_NOT_QUOTED" in x], v)

    def test_missing_sentence_is_a_violation(self):
        v = check_report.check_daily(
            self._report("- 比索那条这次算命中,分歧点已被检验。"),
            SNAP_TEXT, self.BRIEF)
        self.assertTrue(any("REVIEW_SENTENCE_NOT_QUOTED" in x for x in v), v)

    def test_one_character_changed_is_a_violation(self):
        v = check_report.check_daily(
            self._report("- 2026-08-09 PHP 命中(时限 T+1、按 2 个运行日计)"
                         " —— 分歧点已被检验。"),
            SNAP_TEXT, self.BRIEF)
        self.assertTrue(any("REVIEW_SENTENCE_NOT_QUOTED" in x for x in v), v)

    def test_quote_must_be_in_the_review_section_not_anywhere(self):
        """抄在附录里不算 —— 判定类结论要落在**正文的复盘节**,
        这与管道结论句必须留在附录是方向相反的两道闸门。"""
        report = self._report("- 本期无可复盘观点。")
        report += ("\n2026-08-09 PHP 命中(时限 T+1、按 1 个运行日计)\n")
        v = check_report.check_daily(report, SNAP_TEXT, self.BRIEF)
        self.assertTrue(any("REVIEW_SENTENCE_NOT_QUOTED" in x for x in v), v)

    def test_violation_carries_its_own_disposition(self):
        v = check_report.check_daily(
            self._report("- 比索那条这次算命中。"), SNAP_TEXT, self.BRIEF)
        line = [x for x in v if "REVIEW_SENTENCE_NOT_QUOTED" in x][0]
        self.assertTrue(line.endswith(check_report.DISPOSITION_REVIEW_QUOTE),
                        line)

    def test_the_check_prints_a_receipt_with_a_count(self):
        """「跳过必须出声」的正向形态:比过了几句要打进 stdout,
        否则"全过"与"一句都没比"在输出上不可分辨。"""
        notes = []
        check_report.check_daily(
            self._report("- 2026-08-09 PHP 命中(时限 T+1、按 1 个运行日计)"),
            SNAP_TEXT, self.BRIEF, notes=notes)
        line = "\n".join(notes)
        self.assertIn("REVIEW_SENTENCE_CHECKED", line)
        self.assertRegex(line, r"REVIEW_SENTENCE_CHECKED: 要点表给出 \d+ 条")


class DecisionClaimSourcedTest(unittest.TestCase):
    """`DECISION_CLAIM_NOT_SOURCED` —— 结构化观点必须**逐字**溯源到散文 trigger。

    LLM 在结构化字段里只做"抄"与"选":阈值逐字取自速览表那一格已有的数,
    比较方向与字段名从固定枚举里选。允许"差不多"就等于允许它在结构化字段里
    另写一个数,而结构化字段才是判定入口 —— 散文与判定从此各说各话,
    读者只看得到散文那半。校验器与 `log_decision.py` 共用同一份判据
    (`claims.validate_claim`),两处各写一遍必然漂移。
    """

    def _entries(self, text):
        entries, problems = check_report.parse_decision_log(text)
        self.assertEqual(problems, [])
        return entries

    def test_wellformed_claim_passes(self):
        v = check_report.check_decision_claim("2026-08-10",
                                              self._entries(claim_log()))
        self.assertEqual(v, [])

    def test_threshold_absent_from_the_prose_is_a_violation(self):
        bad = json.loads(json.dumps(CLAIM_OK))
        bad["legs"][0]["threshold"] = "60.95"
        v = check_report.check_decision_claim("2026-08-10",
                                              self._entries(claim_log(bad)))
        self.assertTrue(any("DECISION_CLAIM_NOT_SOURCED" in x
                            and "CLAIM_THRESHOLD_NOT_SOURCED" in x for x in v), v)

    def test_truncated_threshold_is_a_violation(self):
        bad = json.loads(json.dumps(CLAIM_OK))
        bad["legs"][0]["threshold"] = "60.9"
        v = check_report.check_decision_claim(
            "2026-08-10",
            self._entries(claim_log(bad, trigger="若 C 升破 60.91 → 关注丙(T+2)")))
        self.assertTrue(any("DECISION_CLAIM_NOT_SOURCED" in x for x in v), v)

    def test_horizon_quote_absent_from_the_prose_is_a_violation(self):
        bad = json.loads(json.dumps(CLAIM_OK))
        bad["horizon"]["quote"] = "T+9"
        v = check_report.check_decision_claim("2026-08-10",
                                              self._entries(claim_log(bad)))
        self.assertTrue(any("CLAIM_HORIZON_NOT_SOURCED" in x for x in v), v)

    def test_violation_carries_its_own_disposition(self):
        bad = json.loads(json.dumps(CLAIM_OK))
        bad["legs"][0]["threshold"] = "60.95"
        v = check_report.check_decision_claim("2026-08-10",
                                              self._entries(claim_log(bad)))
        self.assertTrue(v[0].endswith(check_report.DISPOSITION_DECISION_CLAIM),
                        v[0])

    def test_entries_without_a_claim_are_declared_with_a_count(self):
        notes = []
        legacy = json.dumps({"date": "2026-08-10", "currency": "PHP",
                             "scenario": "s", "trigger": "t",
                             "watch_direction": "up"}, ensure_ascii=False) + "\n"
        v = check_report.check_decision_claim("2026-08-10",
                                              self._entries(legacy), notes=notes)
        self.assertEqual(v, [])
        line = "\n".join(notes)
        self.assertIn("DECISION_CLAIM_ABSENT_SKIPPED", line)
        self.assertRegex(line, r"\d+")

    def test_unstructurable_claim_with_a_reason_passes(self):
        claim = {"horizon": {"kind": "running_days", "n": 2, "quote": "T+2"},
                 "legs": None, "unstructurable_reason": "散文未给出阈值"}
        v = check_report.check_decision_claim("2026-08-10",
                                              self._entries(claim_log(claim)))
        self.assertEqual(v, [])

    def test_checker_and_add_share_one_predicate(self):
        """两处各写一遍必然漂移:登记时放行、校验时打红(或反过来)。"""
        self.assertIs(check_report.claims.validate_claim,
                      claims.validate_claim)


class DecisionTriggerSourcedTest(unittest.TestCase):
    """速览「条件方向」格必须逐字包含决策日志同日同币种的 `trigger`。

    ---- 为什么新增这一码(实测,先跑后抄)----
    `skills/fx-daily-report/SKILL.md:180` 与 `:388` 两处写明二者**同源同字**,
    而校验器对它**零提及**:`grep -n "decision|决策日志" scripts/check_report.py`
    无输出。散文规则、零强制。
    本周实测违约率(判据:log 的 trigger 整串是否出现在当日速览「条件方向」
    那一格里):2026-08-10 五币种全 False、2026-08-11 五币种全 False、
    08-12/08-13/08-14 各五条全 True —— **25 条里 10 条当前就是违反的**,
    而六份产物全绿。

    ---- 方向:表是源,日志是抄件 ----
    `SKILL.md:387-388` 写的是"把速览表五行的条件方向整理成 JSON 数组"经
    `log_decision.py` 写入,所以两者不一致时,**错的是日志**。
    git 证据(本轮实测):日志最后一次写入 `eef783e`,五份日报重生成于
    `ee7a2c6`,且 `git merge-base --is-ancestor eef783e ee7a2c6` 为真 ——
    日志确实是旧的那一份。
    """

    def _entries(self, text=DECISION_LOG):
        entries, problems = check_report.parse_decision_log(text)
        self.assertEqual(problems, [])
        return entries

    def test_matching_trigger_passes(self):
        v = check_report.check_decision_trigger(
            check_report.sections(OVERVIEW_REPORT), "2026-08-10",
            self._entries())
        self.assertEqual(v, [])

    def test_trigger_not_verbatim_in_the_cell_is_a_violation(self):
        drifted = DECISION_LOG.replace("若 C 升破 60.9 → 关注丙(T+2)",
                                       "另写了一版触发条件")
        v = check_report.check_decision_trigger(
            check_report.sections(OVERVIEW_REPORT), "2026-08-10",
            self._entries(drifted))
        self.assertTrue(any("DECISION_TRIGGER_NOT_SOURCED" in x and "PHP" in x
                            for x in v), v)

    def test_violation_carries_its_own_disposition(self):
        drifted = DECISION_LOG.replace("若 C 升破 60.9 → 关注丙(T+2)", "另一版")
        v = check_report.check_decision_trigger(
            check_report.sections(OVERVIEW_REPORT), "2026-08-10",
            self._entries(drifted))
        self.assertTrue(v[0].endswith(check_report.DISPOSITION_DECISION_TRIGGER),
                        v[0])

    def test_no_entry_for_the_date_declares_with_a_count(self):
        notes = []
        check_report.check_decision_trigger(
            check_report.sections(OVERVIEW_REPORT), "2026-08-99",
            self._entries(), notes=notes)
        line = "\n".join(notes)
        self.assertIn("DECISION_LOG_NO_ENTRY", line)
        self.assertRegex(line, r"\d+")

    def test_corrupt_log_is_reported_not_swallowed(self):
        entries, problems = check_report.parse_decision_log("{ 这不是 JSON\n")
        self.assertTrue(problems)

    def test_cli_without_the_flag_is_a_usage_error(self):
        """修前这一条测的是"缺席 → 带计数的声明 + rc=0"。那一形态本身就是
        fail-open:实测在 2026-08-10 与 2026-08-11 两份日报上,不带这个参数
        时 10 条违约全部静默通过,而 SKILL 对此的处置只是一句「必须带上」的
        散文。2026-08-14 起 `--decision-log` 必给,缺席即 rc=2。
        **不保留那条无参数的宽松路径** —— 判据跟着改,不是给旧路径开后门。
        """
        with tempfile.TemporaryDirectory() as t:
            argv, _ = daily_files(t, extra=("--mode", "daily"))
            i = argv.index("--decision-log")
            del argv[i:i + 2]
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), \
                    contextlib.redirect_stderr(err):
                rc = check_report.main(argv)
        self.assertEqual(rc, 2, out.getvalue() + err.getvalue())
        self.assertNotIn("CHECK PASSED", out.getvalue())
        self.assertIn("DAILY_REQUIRED_OPTION_MISSING", err.getvalue())
        # 消息必须说清它守的是哪一道闸门,以及默认路径在哪
        self.assertIn("DECISION_TRIGGER_NOT_SOURCED", err.getvalue())
        self.assertIn("state/decision-log.jsonl", err.getvalue())

    def test_the_library_layer_still_declares_the_skip_with_a_count(self):
        """CLI 收成 rc=2 之后,`DECISION_LOG_ABSENT_SKIPPED` **没有被删** ——
        它挪进了 `check_daily` 本体:库调用方传 `decision_entries=None` 仍是
        可达的合法形态,而"谁跳过谁出声"。删掉它等于让别的调用方静默跳过。
        """
        notes = []
        check_report.check_daily(make_report(), SNAP_TEXT, BRIEF, notes=notes,
                                 decision_entries=None)
        line = "\n".join(n for n in notes
                         if n.startswith("DECISION_LOG_ABSENT_SKIPPED"))
        self.assertTrue(line, notes)
        self.assertRegex(line, r"\d+")

    def test_cli_with_a_corrupt_log_exits_2(self):
        """给了却读不成 = 响亮失败,与 `--digest` 同规格 rc=2。
        这一条不走 fail-open:调用方以为查了、脚本静默跳过,正是上一轮
        weekly 位置参数那条缺陷的形状。"""
        with tempfile.TemporaryDirectory() as t:
            rp, sp, bp, lp = (os.path.join(t, n)
                              for n in ("r.md", "s.json", "b.md", "log.jsonl"))
            for path, text in ((rp, make_report()), (sp, SNAP_TEXT),
                               (bp, BRIEF), (lp, "{ 坏掉的行\n")):
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text)
            buf = io.StringIO()
            with contextlib.redirect_stderr(buf):
                rc = check_report.main([rp, sp, "--brief", bp,
                                        "--decision-log", lp])
            self.assertEqual(rc, 2, buf.getvalue())


class NumberWrongSectionSentenceDeltaTest(unittest.TestCase):
    """`NUMBER_WRONG_SECTION` 的点名放行:判定单位**保留在节**,但声明必须
    把"收到句会多炸多少"这个数一起打出来。

    ---- 本轮实测(先跑后抄)----
    五份日报上「币种节 × 别的币种」整池放行:9/20、10/20、13/20、15/20、
    16/20。把判定单位从节收到句后,**新增 22 条**(节级 0 → 句级 22)。
    用户给的红线是 15,22 超线,于是逐条核了这 22 条:
    **22 条全部来自 6 个句子,且 6 个句子是同一个结构类** —— 句子用
    **集合指代**点名其余币种(「四条本币对美元的参考价……」「三条同时越过
    61.178、33.105、5.1049」「四者未同次同向升破 0.867、61.325、33.13、
    5.1811」「0.705%、0.279%、0.129% 与 -1.613、-1.42、-0.499 顺序一一
    对上」),然后按固定次序并列列出各自的值。别名表按构造看不见
    「四条」「四者」「三条」这类集合量词,所以句级判定对这一类**必然**误报。
    这正是"结构性误报"的允许项:保留节级 + 收紧声明。
    """

    def test_named_pass_note_also_reports_the_sentence_level_delta(self):
        notes = []
        # USD 节**跨句**引欧元:第一句点名「欧元」,第二句只写 0.921。
        # 节级判定放行(节内点过名),句级判定会炸第二句 —— 差值恰好 1,
        # 声明里的那个数因此是可断言的,不是"打印了某个数字"。
        bodies = {"USD": "**驱动**:欧元这一腿另算。参考价 0.921 同期未动。"}
        check_report.check_number_section_mapping(
            check_report.sections(map_report(bodies=bodies)), MAP_SNAP,
            MAP_BRIEF, set(check_report.CURRENCIES),
            check_report.numbers_in(MAP_SNAP_TEXT)
            | check_report.numbers_in(MAP_BRIEF)
            | check_report.ALLOWED_SMALL, notes=notes)
        line = "\n".join(notes)
        self.assertIn("NUMBER_WRONG_SECTION_NAMED_PASS", line)
        self.assertRegex(line, r"收到句会多炸 1 条")


# ============ 日报模式:强判定是默认,弱化必须显式且响亮(2026-08-14)========
#
# 本仓第 15 次同型缺陷(「打印通过,但守的不是它声称的东西」)的修法。
# 上一轮给 `--decision-log` 配的强制力是 skills/fx-daily-report/SKILL.md 里的
# 一句散文(「这一条**必须带上**」),而实测忘带时 stdout 只多一行
# `DECISION_LOG_ABSENT_SKIPPED`、**rc 仍是 0**;`--prior` 同形;`--brief` 更糟
# —— 连声明都没有,`BRIEF_NUMBER_UNTRACEABLE` 整层静默蒸发。
# 用散文守 fail-open,正是这个仓库反复栽的那件事:忘了带参数 = 闸门消失。
#
# 修法与 weekly 拒收位置参数那一轮同规格:**缺席即 rc=2**,并把能直接复制
# 粘贴的那条命令行印出去。判据不是"消息里提到了缺什么",而是**把它印的那
# 一行原样跑一遍,必须 rc=0** —— 只断言"提到了"时,印一条跑不通的命令行
# 照样全绿,而运维拿到的仍是一句空话。

WANT_DAILY_PROGRAM = "python3 scripts/check_report.py"
# 三个必给选项各自守的那条规则的**码名**:消息里必须逐字出现,否则运维只
# 知道"少了个参数",不知道少的是哪一道闸门(rc=2 的消息必须可执行)。
WANT_REQUIRED_OPTION_CODES = {
    "--brief": "BRIEF_NUMBER_UNTRACEABLE",
    "--prior": "PRIOR_PERIOD_BOILERPLATE",
    "--decision-log": "DECISION_TRIGGER_NOT_SOURCED",
}
WANT_DECISION_LOG_DEFAULT = "state/decision-log.jsonl"


class DailyModeRequiresTheStrongFormTest(unittest.TestCase):
    """日报模式下三个溯源入参**必须显式给**,缺一个即 rc=2。

    这一类**全部走真子进程 + 真目录布局**(仓库标准布局的最小复刻:
    `reports/daily/` `data/` `briefs/` `state/`,外加一个指向真 `scripts/`
    的符号链接)。理由是本轮的核心断言就是"把校验器印出去的那一行原样跑
    一遍" —— 进程内 `main(argv)` 拿不到 cwd 与相对路径这两件事,而它们
    正是"能不能复制粘贴"的全部内容。
    """

    DATE = "2026-08-10"
    PRIOR_DATE = "2026-08-09"
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        t = cls.root = cls._tmp.name
        for d in ("reports/daily", "data", "briefs", "state"):
            os.makedirs(os.path.join(t, *d.split("/")))
        cls.rel = {
            "report": "reports/daily/%s.md" % cls.DATE,
            "snapshot": "data/%s.json" % cls.DATE,
            "brief": "briefs/%s-brief.md" % cls.DATE,
            "prior": "reports/daily/%s.md" % cls.PRIOR_DATE,
            "log": WANT_DECISION_LOG_DEFAULT,
            # 手写部分写了一个**不在快照里**的数:strict 是不是默认,靠它分辨
            "loose_brief": "briefs/loose-brief.md",
        }
        for key, text in (
                ("report", make_report()),
                ("prior", make_report(prior_line=PRIOR_LINE_PREV)),
                ("snapshot", SNAP_TEXT), ("brief", BRIEF),
                ("loose_brief", BRIEF + "- 自己编的 99.123\n"),
                ("log", DECISION_LOG)):
            with open(os.path.join(t, cls.rel[key]), "w",
                      encoding="utf-8") as f:
                f.write(text)
        os.symlink(os.path.join(cls.ROOT, "scripts"),
                   os.path.join(t, "scripts"))

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def _run(self, argv, cwd=None):
        """真子进程跑 `python3 scripts/check_report.py <argv>`,cwd 默认是
        那份最小布局的根 —— 相对路径因此与生产命令行逐字同形。"""
        r = subprocess.run([sys.executable, "scripts/check_report.py"]
                           + list(argv), cwd=cwd or self.root,
                           capture_output=True, text=True,
                           env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        return r.returncode, r.stdout, r.stderr

    def _full(self, *extra, drop=()):
        """完整的生产形状;`drop` 里的选项(连同它的值)整对去掉。"""
        r = self.rel
        argv = [r["report"], r["snapshot"], "--brief", r["brief"],
                "--prior", r["prior"], "--decision-log", r["log"]]
        for opt in drop:
            i = argv.index(opt)
            del argv[i:i + 2]
        return argv + list(extra)

    # ---- 基线:完整形状必须 rc=0(否则下面每一条都在测噪声)----

    def test_the_complete_production_shape_passes(self):
        rc, out, err = self._run(self._full())
        self.assertEqual(rc, 0, out + err)
        self.assertIn("CHECK PASSED", out)

    # ---- 三个必给选项:逐个漏掉都必须 rc=2,不是 rc=0 ----

    def test_dropping_decision_log_exits_2(self):
        rc, out, err = self._run(self._full(drop=("--decision-log",)))
        self.assertEqual(rc, 2, out + err)
        self.assertNotIn("CHECK PASSED", out)
        self.assertIn("DAILY_REQUIRED_OPTION_MISSING", err)
        self.assertIn("--decision-log", err)

    def test_dropping_prior_exits_2(self):
        rc, out, err = self._run(self._full(drop=("--prior",)))
        self.assertEqual(rc, 2, out + err)
        self.assertNotIn("CHECK PASSED", out)
        self.assertIn("DAILY_REQUIRED_OPTION_MISSING", err)
        self.assertIn("--prior", err)

    def test_dropping_brief_exits_2(self):
        """`--brief` 是三个里**唯一连声明都没有**的那个:修前漏掉它时
        stdout 是裸 `CHECK PASSED` rc=0,而 `BRIEF_NUMBER_UNTRACEABLE` 与
        `BRIEF_REVIEW_BLOCK_MALFORMED` 整层没跑过 —— 比 `--no-strict-brief`
        更彻底的一条静默弱化路径。它不收成 rc=2,`--no-strict-brief` 就没有
        意义:绕过它只要少写一个参数。"""
        rc, out, err = self._run(self._full(drop=("--brief",)))
        self.assertEqual(rc, 2, out + err)
        self.assertNotIn("CHECK PASSED", out)
        self.assertIn("DAILY_REQUIRED_OPTION_MISSING", err)
        self.assertIn("--brief", err)

    def test_dropping_all_three_lists_all_three(self):
        """一次只报一个会让运维跑三遍才凑齐 —— 消息必须把缺的全列出来。"""
        rc, out, err = self._run(
            self._full(drop=("--brief", "--prior", "--decision-log")))
        self.assertEqual(rc, 2, out + err)
        for opt in WANT_REQUIRED_OPTION_CODES:
            self.assertIn(opt, err, opt)

    # ---- 消息必须**可执行**:把它印的那一行原样跑一遍 ----

    def test_the_printed_command_line_runs_verbatim_and_passes(self):
        """**本类的靶心。** 判据不是"消息里提到了缺什么"(那样印一条跑不通
        的命令行照样全绿),而是:从 stderr 里把那一行整句取出来、`shlex`
        切开、**在同一个 cwd 下原样执行**,必须 rc=0 且 `CHECK PASSED`。

        三个选项各漏一次、以及三个全漏,四种漏法各跑一遍 —— 只测"全漏"
        时,"把用户给了的那几个值原样带回去"这一半就没人看守。
        """
        for drop in (("--decision-log",), ("--prior",), ("--brief",),
                     ("--brief", "--prior", "--decision-log")):
            with self.subTest(drop=drop):
                rc, out, err = self._run(self._full(drop=drop))
                self.assertEqual(rc, 2, out + err)
                line = self._command_line(err)
                self.assertTrue(line.startswith(WANT_DAILY_PROGRAM),
                                "印出去的命令行不是完整可执行形态:%r" % line)
                argv = shlex.split(line)
                rc2 = subprocess.run(
                    [sys.executable] + argv[1:], cwd=self.root,
                    capture_output=True, text=True,
                    env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
                self.assertEqual(rc2.returncode, 0,
                                 "校验器印的这一行跑不通:\n%s\n%s\n%s"
                                 % (line, rc2.stdout, rc2.stderr))
                self.assertIn("CHECK PASSED", rc2.stdout)

    @staticmethod
    def _command_line(err):
        lines = [x.strip() for x in err.splitlines()
                 if x.strip().startswith(WANT_DAILY_PROGRAM)]
        if len(lines) != 1:
            raise AssertionError("stderr 里可复制的命令行不是恰好一行:%r"
                                 % lines)
        return lines[0]

    def test_the_message_names_the_default_decision_log_path(self):
        """默认路径写进消息里,运维不必回去翻 SKILL。"""
        rc, out, err = self._run(self._full(drop=("--decision-log",)))
        self.assertEqual(rc, 2, out + err)
        self.assertIn(WANT_DECISION_LOG_DEFAULT, err)

    def test_the_message_names_the_rule_each_missing_option_guards(self):
        """「缺少参数」不可执行 —— 消息必须说清这个参数守的是哪一道闸门,
        逐字给出那条码名。"""
        for opt, code in sorted(WANT_REQUIRED_OPTION_CODES.items()):
            with self.subTest(opt=opt):
                rc, out, err = self._run(self._full(drop=(opt,)))
                self.assertEqual(rc, 2, out + err)
                self.assertIn(code, err, "%s 的消息没写它守的是什么" % opt)

    # ---- strict 是默认;`--no-strict-brief` 是唯一的弱化入口,且必须出声 ----

    def test_strict_brief_is_the_default_with_no_flag_at_all(self):
        """修前:不加 `--strict-brief` 就不查「要点表 ⊆ 快照」,于是同一份
        要点表里写错的数字成为下游报告的合法来源,rc=0。修后:不加任何
        开关就是严格的。"""
        rc, out, err = self._run(
            self._full(drop=("--brief",)) + ["--brief",
                                             self.rel["loose_brief"]])
        self.assertEqual(rc, 1, out + err)
        self.assertIn("BRIEF_NUMBER_UNTRACEABLE", out)
        self.assertIn("99.123", out)

    def test_no_strict_brief_weakens_and_declares_with_a_count(self):
        """弱化的唯一入口,且**不是静默豁免**:退出码回到 0,但 stdout 必须
        出现一条带计数的声明 —— 「没查」与「查过且全过」在输出上必须可分辨,
        与 WEEKLY_DIGEST_ABSENT_SKIPPED / BRIEF_REVIEW_BLOCK_SKIPPED 同一原则。
        """
        rc, out, err = self._run(
            self._full(drop=("--brief",))
            + ["--brief", self.rel["loose_brief"], "--no-strict-brief"])
        self.assertEqual(rc, 0, out + err)
        # 判据是"没有一条**违规行**是这个码",不是"stdout 里不出现这个串"
        # —— 降级声明自己就点名了它关掉的是哪一层,那正是要的。
        self.assertEqual(self._lines_with_code(out, "BRIEF_NUMBER_UNTRACEABLE"),
                         [], out)
        self.assertIn("STRICT_BRIEF_DISABLED", out)
        # 计数是真的:要点表五个数(60.843 / 60.9 / 3.1 / 3.4 / 99.123)
        self.assertRegex(out, r"STRICT_BRIEF_DISABLED[^\n]*要点表 5 个数字")
        self.assertIn("CHECK PASSED", out)

    @staticmethod
    def _lines_with_code(out, code):
        return [x for x in out.splitlines()
                if x.lstrip(" -").startswith(code + ":")]

    def test_the_strong_form_does_not_print_the_weakening_declaration(self):
        """声明不许在**真查过**的那一次也照打 —— 否则它退化成噪声,读者
        读到它也不知道到底查没查(与 PRIOR_PERIOD_ABSENT_SKIPPED 同规矩)。"""
        rc, out, err = self._run(self._full())
        self.assertEqual(rc, 0, out + err)
        self.assertNotIn("STRICT_BRIEF_DISABLED", out)

    def test_the_old_strict_brief_switch_is_rejected_not_silently_accepted(self):
        """`--strict-brief` 被**删掉**而不是留成无操作的兼容开关。

        留成 no-op 等于新造一个"注册了却没人读"的选项:它会同时进两个 mode
        的「不读选项」表(第六族的幂集因此翻倍),而且陈旧调用点会**静默
        地什么都不做**——正是本轮要消灭的那种形态。删掉之后,任何陈旧调用
        点在 argparse 层就 rc=2 响亮死掉。
        """
        rc, out, err = self._run(self._full("--strict-brief"))
        self.assertEqual(rc, 2, out + err)
        self.assertNotIn("CHECK PASSED", out)

    # ---- 周报模式不受本轮影响 ----

    def test_weekly_mode_does_not_require_the_daily_options(self):
        """`--brief`/`--prior`/`--decision-log` 在周报模式仍不适用;那一侧
        由「当前 mode 不读的选项」冻结表 + 第六族变异守,不在这里改行为。"""
        wp = os.path.join(self.root, "reports", "weekly", "2026-W33.md")
        os.makedirs(os.path.dirname(wp), exist_ok=True)
        with open(wp, "w", encoding="utf-8") as f:
            f.write(WEEKLY_OK)
        rc, out, err = self._run(["reports/weekly/2026-W33.md",
                                  "--mode", "weekly"])
        self.assertEqual(rc, 0, out + err)
        self.assertIn("CHECK PASSED", out)


# ============ 2026-08-15 第二轮:第 4 列从「零求值」变成有判据 ==============
#
# 上一轮(8ee5e1e)把「失效条件」与「翻转指标」解耦,规则改对了、内容改砸了:
# 四路对抗证伪实测,第 4 列除「不得与翻转指标重合」之外**零求值** ——
#   col4 = col2 逐字复制                   → rc=0 / 5/5 / CHECK PASSED
#   col4 = col2 去掉「→ 关注…」半句        → rc=0 / 5/5 / CHECK PASSED
#   col4 = 「无」                           → rc=0 / 5/5 / CHECK PASSED
#   col4 = 「若无新增信息、情况未变(T+3)」 → rc=0 / 5/5 / CHECK PASSED
# 最后一行是 SKILL 逐字禁止的写法,校验器照样放行。闸门给的压力方向因此与
# SKILL 要求的方向**相反**:让这格变绿最省力的办法就是把它写空洞。
# 本轮补两条码把标准变成机器判据(空洞 / 机械否定),另修三处回执说谎。

MIRROR_TRIGGER = "若 C 升破 60.9 → 关注丙(T+2)"
# 主判断的翻转指标 + 替代解释自带的那一个,两条都在同一段里 —— 必须修 7 的
# 全部要害就是"这两者此前不分"。
RING_BODY_TWO_FLIPS = ("**分歧与判断**:关键假设甲。"
                       "替代解释乙(其翻转指标:丁位升破 61.1)。"
                       "翻转指标:丙位回落(T+2)。")
# 只有替代解释那一条(把主判断那句的标签改两个字就是这个形态)
RING_BODY_ALT_FLIP_ONLY = ("**分歧与判断**:关键假设甲。"
                           "替代解释乙(其翻转指标:丁位升破 61.1)。"
                           "反转指标:丙位回落(T+2)。")


def inval_pairs(cell, trigger=MIRROR_TRIGGER, bodies=(RING_BODY,), name="PHP"):
    return [(name, cell, trigger, list(bodies))]


class InvalidationColumnVacuousTest(unittest.TestCase):
    """`INVALIDATION_COLUMN_VACUOUS` —— SKILL 逐字禁止的空洞写法,做成可判定。

    判据来源:`skills/fx-daily-report/SKILL.md` 速览表模板段那一句
    「必须是价格或指标的**可观测量**并带时限,**不得是"若无新增信息"一类**」。
    修前它只是散文:实测把五格全写成「若无新增信息、情况未变(T+3)」,
    生产命令 rc=0、回执照打 `INVALIDATION_COLUMN_CHECKED: 5/5`。

    **诚实边界**:占位词与空洞短语都是**枚举**(两张冻结表),同义改写绕得过去。
    它挡的是 SKILL 已经逐字点名的那几种,不是"语义空洞"的通用判定。
    """

    def one(self, cell, notes=None, **kw):
        return check_report.check_invalidation_independent(
            inval_pairs(cell, **kw), check_report.INVALIDATION_SCOPE_DAILY,
            notes=notes)

    def test_an_empty_cell_is_a_violation(self):
        v = self.one("")
        self.assertTrue(any("INVALIDATION_COLUMN_VACUOUS" in x for x in v), v)

    def test_a_whitespace_only_cell_is_a_violation(self):
        v = self.one("  ")
        self.assertTrue(any("INVALIDATION_COLUMN_VACUOUS" in x for x in v), v)

    def test_a_bare_placeholder_word_is_a_violation(self):
        v = self.one("无")
        self.assertTrue(any("INVALIDATION_COLUMN_VACUOUS" in x for x in v), v)

    def test_the_phrase_the_skill_bans_verbatim_is_a_violation(self):
        v = self.one("若无新增信息、情况未变(T+3)")
        self.assertTrue(any("INVALIDATION_COLUMN_VACUOUS" in x for x in v), v)

    def test_punctuation_inserted_into_the_banned_phrase_does_not_get_past_it(self):
        """判据在去标点空白之后比 —— 顿号/括号不是改写。"""
        v = self.one("若无、新增,信息(T+3)")
        self.assertTrue(any("INVALIDATION_COLUMN_VACUOUS" in x for x in v), v)

    def test_a_concrete_cell_passes(self):
        v = self.one("比索一次都没有回到 60.75 一侧(时限:2026-08-27)")
        self.assertEqual(v, [], v)

    def test_a_vacuous_cell_is_not_counted_as_judged(self):
        """空洞的那一格**不算查过**:算进分子等于把"没得判"印成"判过了"。"""
        notes = []
        self.one("无", notes=notes)
        self.assertRegex("\n".join(notes), r"自身判据 0/1")

    def test_the_placeholder_and_phrase_tables_are_frozen(self):
        """逐元素冻结:少一项就是悄悄放行,多一项就是悄悄收紧。"""
        self.assertEqual(check_report.VACUOUS_INVALIDATION_CELLS,
                         ("", "无", "暂无", "不适用", "待定", "同上", "略"))
        self.assertEqual(check_report.VACUOUS_INVALIDATION_PHRASES,
                         ("若无新增信息", "无新增信息", "情况未变",
                          "无重大变化", "维持现状", "视情况而定"))


class InvalidationColumnMirrorsTriggerTest(unittest.TestCase):
    """`INVALIDATION_COLUMN_MIRRORS_TRIGGER` —— 第 4 列不得是第 2 列的机械否定。

    ---- 判据怎么定的,以及为什么不是"必须出现新数字" ----
    两条轴,**任一条上与同行第 2 列不同即通过**:
      轴 A「可观测量」:第 4 列带一个第 2 列没有的可核对量(数字 token,
                        时限串先剥掉,由轴 B 管);
      轴 B「时限」    :第 4 列自己的时限非空、且与第 2 列的时限不同。
    两轴都没有差异 = 这一格没有交付任何第 2 列之外的信息,它只是把触发条件
    取了个反 —— 那正是四路证伪里 `col4 = col2` 与 `col4 = col2 去掉后半句`
    两种写法能全绿的原因。

    **刻意不写成"必须出现新数字"**:那会逼出编造的数(而阈值类前瞻价位按
    定义不在快照里,写进去当场撞 NUMBER_UNTRACEABLE,两条规则会互斥 ——
    本仓四个月前撞过一次)。轴 B 单独就能让一格通过:保质期与触发窗口不同长
    是这一列本来就该交付的信息(触发等三个运行日,判断本身可以活到下一次
    议息),写出那个日期不需要任何新数字。

    **诚实边界**:只比数字 token 与时限串,不做语义判断。把 60.9 换算成
    别的单位、或用文字复述同一个价位,绕得过去。
    """

    def one(self, cell, trigger=MIRROR_TRIGGER, notes=None):
        return check_report.check_invalidation_independent(
            inval_pairs(cell, trigger=trigger),
            check_report.INVALIDATION_SCOPE_DAILY, notes=notes)

    def codes(self, v):
        return [x for x in v if "INVALIDATION_COLUMN_MIRRORS_TRIGGER" in x]

    def test_a_verbatim_copy_of_the_trigger_is_a_violation(self):
        self.assertTrue(self.codes(self.one(MIRROR_TRIGGER)),
                        "col4 = col2 逐字复制照样绿")

    def test_dropping_the_watch_half_is_still_a_violation(self):
        self.assertTrue(self.codes(self.one("若 C 升破 60.9")),
                        "col4 = col2 去掉「→ 关注…」半句照样绿")

    def test_the_plain_negation_of_the_trigger_is_a_violation(self):
        self.assertTrue(self.codes(self.one("T+2 内 C 一次都没有升破 60.9")),
                        "把触发条件取个反、时限照抄,这一格没交付任何信息")

    def test_a_cell_without_any_deadline_is_a_violation(self):
        self.assertTrue(self.codes(self.one("C 一次都没有升破 60.9")))

    def test_a_different_deadline_alone_passes(self):
        """轴 B 单独成立即通过 —— 这条钉的就是"不逼出新数字"。"""
        self.assertEqual(
            self.codes(self.one("C 一次都没有升破 60.9(时限:2026-08-27)")), [])

    def test_a_new_observable_alone_passes(self):
        """轴 A 单独成立即通过 —— 时限与触发同长是允许的,只要这一格
        自己带一个可核对量。"""
        self.assertEqual(self.codes(self.one(
            "C 一次都没有升破 60.9,60.75 那一端也一次都没有被触及(T+2)")), [])

    def test_the_violation_line_states_both_axes_with_their_values(self):
        line = self.codes(self.one("T+2 内 C 一次都没有升破 60.9"))[0]
        self.assertIn("可观测量", line)
        self.assertIn("时限", line)
        self.assertIn("60.9", line)
        self.assertTrue(
            line.endswith(check_report.DISPOSITION_INVALIDATION_MIRROR), line)

    def test_a_row_without_a_trigger_cell_is_not_counted_as_judged(self):
        notes = []
        check_report.check_invalidation_independent(
            [("PHP", "T+2 内 C 一次都没有升破 60.9", None, [RING_BODY])],
            check_report.INVALIDATION_SCOPE_DAILY, notes=notes)
        self.assertRegex("\n".join(notes), r"自身判据 0/1")

    def test_the_judgement_has_exactly_one_implementation(self):
        with open(check_report.__file__, encoding="utf-8") as f:
            tree = ast.parse(f.read())
        hosts = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            for sub in ast.walk(node):
                if (isinstance(sub, ast.Constant)
                        and isinstance(sub.value, str)
                        and sub.value.startswith(
                            "INVALIDATION_COLUMN_MIRRORS_TRIGGER:")):
                    hosts.add(node.name)
        self.assertEqual(hosts, {"check_invalidation_independent"}, hosts)


class InvalidationColumnFlipHostTest(unittest.TestCase):
    """必须修 7:主判断的翻转指标 与 替代解释自带的「其翻转指标」必须分开。

    ---- 修前实测(先跑后抄)----
    reports/daily/2026-08-14.md 的 EUR 第 4 列抄回该节翻转指标、再把该节
    `翻转指标:` 改成 `反转指标:`(只此一处),生产命令打出:
      `JUDGEMENT_RING_CHECKED: 5/5` + `INVALIDATION_COLUMN_CHECKED: 5/5` + rc=0
    机制:`_flip_payloads` 把整节里所有含「翻转指标」四字的句子一起收进池子,
    不区分「本判断的翻转指标」与「替代解释自带的其翻转指标」。标签一改,
    本判断那条离池,池仍非空 → `checked += 1` 照走,回执于是宣称"与对应
    币种节翻转指标比过了",而那东西此刻并不存在。

    ---- 修法 ----
    取不到**主判断**那一条时按失败关闭并出声(`INVALIDATION_COLUMN_FLIP_HOST_MISSING`),
    且不计入分子。替代解释自带的那一条**仍留在比对池里** —— 把它抄进表格
    与抄主判断那条是同一类错,不因本轮而放行。
    """

    def one(self, cell, bodies, notes=None):
        return check_report.check_invalidation_independent(
            inval_pairs(cell, bodies=bodies),
            check_report.INVALIDATION_SCOPE_DAILY, notes=notes)

    def test_a_host_with_only_the_alternatives_flip_is_loud(self):
        v = self.one("比索一次都没有回到 60.75 一侧(时限:2026-08-27)",
                     [RING_BODY_ALT_FLIP_ONLY])
        self.assertTrue(
            any("INVALIDATION_COLUMN_FLIP_HOST_MISSING" in x for x in v), v)

    def test_that_host_is_not_counted_as_judged(self):
        notes = []
        self.one("比索一次都没有回到 60.75 一侧(时限:2026-08-27)",
                 [RING_BODY_ALT_FLIP_ONLY], notes=notes)
        self.assertRegex("\n".join(notes), r"独立性 0/1")

    def test_the_alternatives_flip_is_still_a_comparison_target(self):
        """替代解释那一条照旧参与比对 —— 抄它和抄主判断那条是同一类错。"""
        v = self.one("丁位升破 61.1", [RING_BODY_TWO_FLIPS])
        self.assertTrue(
            any("INVALIDATION_COLUMN_IS_FLIP_RESTATED" in x for x in v), v)

    def test_a_host_with_a_main_flip_is_counted(self):
        notes = []
        v = self.one("比索一次都没有回到 60.75 一侧(时限:2026-08-27)",
                     [RING_BODY_TWO_FLIPS], notes=notes)
        self.assertEqual(v, [], v)
        self.assertRegex("\n".join(notes), r"独立性 1/1")

    def test_relabelling_the_main_flip_does_not_turn_a_copied_column_green(self):
        """整条 CLI 路径:改两个字 + 抄翻转指标,退出码必须非 0。"""
        report = OVERVIEW_REPORT.replace(
            "| USD | 若 A 升破 60.843 → 关注甲(T+2) | 依据甲 | 甲位回落(T+2) |",
            "| USD | 若 A 升破 60.843 → 关注甲(T+2) | 依据甲 | 丁位升破 61.1 |")
        report = report.replace(
            "## 美元(USD)\n正文。",
            "## 美元(USD)\n**分歧与判断**:关键假设 60.843 未变。"
            "替代解释乙(其翻转指标:丁位升破 61.1)。反转指标:甲位回落(T+2)。")
        with tempfile.TemporaryDirectory() as tmp:
            argv, _ = daily_files(tmp, report_text=report,
                                  extra=("--mode", "daily"))
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = check_report.main(argv)
        out = buf.getvalue()
        self.assertIn("INVALIDATION_COLUMN_FLIP_HOST_MISSING", out)
        self.assertNotEqual(rc, 0, out)


class WeeklyLandingRowCoverageTest(unittest.TestCase):
    """必须修 8:周报侧丢整行,回执把 5 行的表印成「4/4」。

    ---- 修前实测(先跑后抄,reports/weekly/2026-W33.md)----
      BRL 第 5 列抄主线二翻转指标(对照)   rc=1  INVALIDATION_COLUMN_IS_FLIP_RESTATED
      同上 + 币种格写成 BRLX               rc=0  INVALIDATION_COLUMN_CHECKED: 4/4
      同上 + BRL 行少一格(短行)          rc=0  INVALIDATION_COLUMN_CHECKED: 4/4
      同上 + 主线归属 主线二→主线九        rc=0  INVALIDATION_COLUMN_CHECKED: 4/5
    分母是 `len(pairs)`,而 `continue` 掉的行两头都不进 —— 抄袭那一行被自己
    抹掉之后,回执把 4 行印成"全查过了"。日报侧同型事故的读数完全不同
    (`OVERVIEW_ROW_MISSING: 速览表缺少 1/5 …` + `4/5`),差别只在调用点怎么
    造 pairs。本轮把分母口径对齐日报侧:**应有的行集合**(五个币种)当分母,
    丢行点名出声。
    """

    def notes_for(self, report):
        notes = []
        v = check_report.check_weekly(report, notes=notes)
        return v, "\n".join(notes)

    def test_the_denominator_is_the_five_currencies(self):
        v, line = self.notes_for(
            weekly_landing("T+3 内比索一次都没有退回 60.75 一侧(时限:2026-08-27)"))
        self.assertRegex(line, r"独立性 1/5")

    def test_missing_rows_are_named_with_counts(self):
        v, line = self.notes_for(
            weekly_landing("T+3 内比索一次都没有退回 60.75 一侧(时限:2026-08-27)"))
        self.assertIn("WEEKLY_LANDING_ROW_MISSING", line)
        for c in ("USD", "EUR", "THB", "BRL"):
            self.assertIn(c, line)

    def test_a_broken_currency_cell_does_not_shrink_the_denominator(self):
        rep = weekly_landing(
            "T+3 内比索一次都没有退回 60.75 一侧(时限:2026-08-27)")
        rep = rep.replace("| PHP | 主线一 |", "| PHPX | 主线一 |")
        v, line = self.notes_for(rep)
        self.assertRegex(line, r"独立性 0/5")
        self.assertIn("PHP", line)

    def test_an_unknown_theme_attribution_is_a_violation(self):
        rep = weekly_landing(
            "T+3 内比索一次都没有退回 60.75 一侧(时限:2026-08-27)",
            belong="主线九")
        v, _ = self.notes_for(rep)
        self.assertTrue(
            any("WEEKLY_THEME_ATTRIBUTION_UNKNOWN" in x for x in v), v)

    def test_a_real_theme_attribution_passes(self):
        rep = weekly_landing(
            "T+3 内比索一次都没有退回 60.75 一侧(时限:2026-08-27)")
        v, _ = self.notes_for(rep)
        self.assertEqual(
            [x for x in v if "WEEKLY_THEME_ATTRIBUTION_UNKNOWN" in x], [])


class ThemeNamingSingleSourceTest(unittest.TestCase):
    """必须修 9:`theme_names` 的注释断言与代码相反,而且它是第二份拷贝。

    修前 `theme_names` 的 docstring 写「与 `check_weekly_judgement_ring` 的
    取名口径**同一处来源**,不另抄一份」,而后者根本不调用它 ——
    `check_weekly_judgement_ring` 里那一行 `re.split(r"[::]", heading, 1)`
    是第二份逐字拷贝。实测漂移后果:把 `theme_names` 那一份改成
    `h.strip() or h`,生产闸门打出 `INVALIDATION_COLUMN_CHECKED: 0/5` 而
    **rc=0 全绿**,只有单测拦得住。
    """

    def test_the_theme_naming_has_exactly_one_implementation(self):
        """段名判据(`[::]` 那条 split)只准出现在一个函数里。"""
        with open(check_report.__file__, encoding="utf-8") as f:
            tree = ast.parse(f.read())
        hosts = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            for sub in ast.walk(node):
                if (isinstance(sub, ast.Constant)
                        and isinstance(sub.value, str)
                        and sub.value == "[::]"):
                    hosts.add(node.name)
        self.assertEqual(hosts, {"theme_names"}, hosts)

    def test_the_ring_path_reads_the_names_from_theme_names(self):
        """行为断言(不是只看 AST):换掉 `theme_names`,判断环那条路径打出的
        段名必须跟着换 —— 不跟着换就说明它另有一份拷贝。"""
        broken = WEEKLY_RING.replace(
            "**替代解释**:承接厚度(它自己的翻转指标:下一次定盘次序翻过来)。\n", "")
        with mock.patch.object(
                check_report, "theme_names",
                lambda secs: [("段名哨兵", b)
                              for _, b in check_report.theme_subsections(secs)]):
            v = check_report.check_weekly(broken, DIGEST, RING_DAILY)
        self.assertTrue(any("JUDGEMENT_RING_INCOMPLETE" in x and "段名哨兵" in x
                            for x in v), v)


class InvalidationReceiptNamesTheRightColumnTest(unittest.TestCase):
    """回执与违规行里的**列名**必须是被查的那一列的真名。

    日报第 2 列叫「条件方向」,周报第 4 列叫「下周判断」;两侧共用同一个判定
    函数,列名若写死成日报那一个,周报的回执就在说一件不存在的事 ——
    「打印通过但守的不是它声称的东西」在本仓库是最贵的一类缺陷。
    """

    def test_the_weekly_receipt_names_the_weekly_trigger_column(self):
        notes = []
        check_report.check_weekly(
            weekly_landing("T+3 内比索一次都没有退回 60.75 一侧(时限:2026-08-27)"),
            notes=notes)
        line = [x for x in notes if "INVALIDATION_COLUMN_CHECKED" in x][0]
        self.assertIn(check_report.WEEKLY_COL_TRIGGER, line)
        self.assertNotIn(check_report.OVERVIEW_COL_TRIGGER, line)

    def test_the_daily_receipt_names_the_daily_trigger_column(self):
        notes = []
        check_report.check_invalidation_independent(
            inval_pairs("比索一次都没有回到 60.75 一侧(时限:2026-08-27)"),
            check_report.INVALIDATION_SCOPE_DAILY, notes=notes)
        line = [x for x in notes if "INVALIDATION_COLUMN_CHECKED" in x][0]
        self.assertIn(check_report.OVERVIEW_COL_TRIGGER, line)

    def test_the_weekly_mirror_violation_names_the_weekly_trigger_column(self):
        v = check_report.check_weekly(
            weekly_landing("比索一次都没有升破 60.9(T+3)"))
        line = [x for x in v
                if "INVALIDATION_COLUMN_MIRRORS_TRIGGER" in x][0]
        self.assertIn(check_report.WEEKLY_COL_TRIGGER, line)


def vintage_snap(rows, schema_version=1):
    """ring_snap 的宏观行可控版本:本组要的是 macro 行的 lag_months/period。"""
    snap = dict(SNAP)
    snap["macro"] = rows
    snap["derived"] = {"schema_version": schema_version,
                       "rates": {}, "real_rate": {}, "events": {}}
    return json.dumps(snap, ensure_ascii=False)


PH_CPI_LAGGED = {"economy": "PH", "indicator": "CPI 同比", "value": 6.362922,
                 "prev": 6.761006, "period": "2026-06", "lag_months": 2}


def vintage_check(ring, rows=None, notes=None):
    return check_report.check_daily(
        make_report(php_body=ring_body(ring)),
        vintage_snap([PH_CPI_LAGGED] if rows is None else rows),
        BRIEF, notes=notes)


class AssumptionVintageTest(unittest.TestCase):
    """`ASSUMPTION_VINTAGE_UNDISCLOSED` —— **披露检查**,不是新鲜度检查。

    它**判不了**"这个读数是不是过期了":快照里没有任何输入能回答"发布方有没有
    出新的一期"。实测(2026-08-19 全量历史)PH/TH/EA/BR 的 CPI 自 2026-08-11
    换 BIS 起 `lag_months` 恒为 2,按"该序列自己历史上的最小滞后"判,一条都
    标不出来 —— 而 PH 的 2026-07 读数 6.2 早在 2026-08-05 就已由 PSA 发布。
    真正的新鲜度判据必须等发布日历接进来(A1 步骤 3)。

    它能判的是**披露**:拿一个带滞后的读数当关键假设的锚点,却不写它的期号,
    读者无从知道那是两个月前的数。靶子取自实测 —— reports/daily/2026-08-12
    两条(PH/TH 政策利率)、2026-08-13 一条(PH CPI 6.362922),三条都没写期号。
    """

    def test_a_lagged_anchor_without_its_period_is_a_violation(self):
        ring = ("关键假设是 6.362922 这一档通胀仍主导定价;不成立时利差这条腿失效。"
                "替代解释:比索走弱是美元一端在统一定价"
                "(其翻转指标:泰铢同步升破 35.2)。"
                "翻转指标:参考价回落至 60.9 一侧(T+3)。")
        line = [x for x in vintage_check(ring)
                if x.startswith("ASSUMPTION_VINTAGE_UNDISCLOSED")]
        self.assertEqual(len(line), 1, line)
        self.assertIn("PHP", line[0])
        self.assertIn("6.362922", line[0])
        self.assertIn("2026-06", line[0])     # 处置要告诉作者该补哪个期号

    def test_the_same_anchor_with_its_period_passes(self):
        ring = ("关键假设是期 2026-06 的 6.362922 仍是最新可得读数;"
                "不成立时利差这条腿失效。"
                "替代解释:比索走弱是美元一端在统一定价"
                "(其翻转指标:泰铢同步升破 35.2)。"
                "翻转指标:参考价回落至 60.9 一侧(T+3)。")
        self.assertEqual([x for x in vintage_check(ring)
                          if x.startswith("ASSUMPTION_VINTAGE_UNDISCLOSED")], [])

    def test_a_zero_lag_reading_needs_no_period(self):
        """滞后 0 的读数就是当期值,写不写期号都不误导。"""
        row = dict(PH_CPI_LAGGED, lag_months=0)
        ring = ("关键假设是 6.362922 这一档通胀仍主导定价;不成立时利差这条腿失效。"
                "替代解释:比索走弱是美元一端在统一定价"
                "(其翻转指标:泰铢同步升破 35.2)。"
                "翻转指标:参考价回落至 60.9 一侧(T+3)。")
        self.assertEqual([x for x in vintage_check(ring, rows=[row])
                          if x.startswith("ASSUMPTION_VINTAGE_UNDISCLOSED")], [])

    def test_rows_without_lag_months_are_declared_with_a_count(self):
        """存量快照没有 lag_months:判不了,必须出声 —— 不出声就与"查过了、没问题"同形。"""
        row = dict(PH_CPI_LAGGED); row.pop("lag_months")
        ring = ("关键假设是 6.362922 这一档通胀仍主导定价;不成立时利差这条腿失效。"
                "替代解释:比索走弱是美元一端在统一定价"
                "(其翻转指标:泰铢同步升破 35.2)。"
                "翻转指标:参考价回落至 60.9 一侧(T+3)。")
        notes = []
        v = vintage_check(ring, rows=[row], notes=notes)
        self.assertEqual([x for x in v
                          if x.startswith("ASSUMPTION_VINTAGE_UNDISCLOSED")], [])
        line = [n for n in notes if n.startswith("ASSUMPTION_VINTAGE_SKIPPED")]
        self.assertEqual(len(line), 1, notes)
        self.assertIn("1", line[0])           # 带计数

    def test_a_positive_check_receipt_carries_counts(self):
        notes = []
        vintage_check(RING_OK, notes=notes)
        line = [n for n in notes if n.startswith("ASSUMPTION_VINTAGE_CHECKED")]
        self.assertEqual(len(line), 1, notes)

    def test_the_value_must_stand_alone_as_a_number(self):
        """1.0 不得被 61.0 里的子串命中 —— 边界判定,不是子串判定。"""
        row = {"economy": "PH", "indicator": "政策利率", "value": 1.0,
               "period": "2026-07-30", "lag_months": 1}
        ring = ("关键假设是参考价 61.09 仍在区间内;不成立时利差这条腿失效。"
                "替代解释:比索走弱是美元一端在统一定价"
                "(其翻转指标:泰铢同步升破 35.2)。"
                "翻转指标:参考价回落至 60.9 一侧(T+3)。")
        self.assertEqual([x for x in vintage_check(ring, rows=[row])
                          if x.startswith("ASSUMPTION_VINTAGE_UNDISCLOSED")], [])

    def test_only_the_assumption_clause_is_judged(self):
        """同一个数出现在传导环里不算 —— 本码判的是**锚点**的披露,不是全节。"""
        ring = ("关键假设是参考价 60.843 仍在区间内;不成立时利差这条腿失效。"
                "替代解释:6.362922 这一档通胀由本地因素定价"
                "(其翻转指标:泰铢同步升破 35.2)。"
                "翻转指标:参考价回落至 60.9 一侧(T+3)。")
        self.assertEqual([x for x in vintage_check(ring)
                          if x.startswith("ASSUMPTION_VINTAGE_UNDISCLOSED")], [])

    def test_another_economys_row_does_not_apply_to_this_section(self):
        """美国那行的值出现在比索节,归属问题由 NUMBER_WRONG_SECTION 管,不在本码。"""
        row = dict(PH_CPI_LAGGED, economy="US")
        ring = ("关键假设是 6.362922 这一档通胀仍主导定价;不成立时利差这条腿失效。"
                "替代解释:比索走弱是美元一端在统一定价"
                "(其翻转指标:泰铢同步升破 35.2)。"
                "翻转指标:参考价回落至 60.9 一侧(T+3)。")
        self.assertEqual([x for x in vintage_check(ring, rows=[row])
                          if x.startswith("ASSUMPTION_VINTAGE_UNDISCLOSED")], [])


OVERVIEW_ONE_ROW_REPORT = """# 外汇日报 2026-08-14

## 速览

| 币种 | 条件方向(时限) | 核心依据 | 失效条件 |
| --- | --- | --- | --- |
| USD | 甲 | 乙 | 丙 |
| BRL | 甲 | 乙 | 丙 |

## 美元(USD)
正文
"""


class KnownGateEscapeTest(unittest.TestCase):
    """`docs/known-gate-escapes.md` 登记的逃逸路径,逐条做成判据。

    这些不是推测:每一条都在 2026-08-16 用生产命令实测跑通过 rc=0。
    登记时的状态一律是「已知、本轮未修」;本类是"修了没有"的判据。
    """

    def one(self, cell, **kw):
        return check_report.check_invalidation_independent(
            inval_pairs(cell, **kw), check_report.INVALIDATION_SCOPE_DAILY,
            notes=kw.pop("notes", None))

    # ---- 逃逸 1:第 4 列整格写 T+99 ----
    def test_a_bare_deadline_is_vacuous(self):
        """四个字符换一格全绿。时限归时限轴管,剥掉之后这一格什么都没说。"""
        v = self.one("T+99")
        self.assertTrue(any("INVALIDATION_COLUMN_VACUOUS" in x for x in v), v)

    def test_a_bare_calendar_deadline_is_also_vacuous(self):
        v = self.one("2026-11-11")
        self.assertTrue(any("INVALIDATION_COLUMN_VACUOUS" in x for x in v), v)

    # ---- 逃逸 3:第 4 列 = 「无(时限:2026-11-11)」 ----
    def test_a_placeholder_with_a_deadline_tail_is_vacuous(self):
        """占位词表是**整串相等**判定,挂一个时限尾巴整串就不相等了。"""
        v = self.one("无(时限:2026-11-11)")
        self.assertTrue(any("INVALIDATION_COLUMN_VACUOUS" in x for x in v), v)

    def test_a_placeholder_with_a_bare_tplusn_tail_is_vacuous(self):
        v = self.one("暂无(T+99)")
        self.assertTrue(any("INVALIDATION_COLUMN_VACUOUS" in x for x in v), v)

    def test_a_real_cell_carrying_a_deadline_clause_still_passes(self):
        """剥时限是为了看清剩下什么,不是为了把带时限的格都判红 ——
        真实产物里五格全带时限尾巴,过度剥离会把它们一起打红。"""
        v = self.one("到 2026-09-10 的 ECB 决议为止,政策利率 2.25 一次都没有"
                     "变动过(时限:2026-09-10)")
        self.assertFalse(any("INVALIDATION_COLUMN_VACUOUS" in x for x in v), v)

    # ---- 逃逸 4:「其」与「翻转指标」之间插一个空格 ----
    def test_a_space_between_qi_and_the_label_still_counts_as_the_alt_one(self):
        """插一个空格,替代解释自带的那句就被算进"主判断自己的"池里,
        `FLIP_HOST_MISSING` 因此不触发,而回执转而宣称 5/5 都比过了。"""
        body = ("**分歧与判断**:关键假设甲。替代解释乙(其 翻转指标:丁位升破 61.1)。"
                "反转指标:丙位回落(T+2)。")
        v = self.one("到 2026-09-10 为止,戊位 99.9 一次都没有出现", bodies=(body,))
        self.assertTrue(
            any("INVALIDATION_COLUMN_FLIP_HOST_MISSING" in x for x in v), v)

    def test_a_fullwidth_space_does_not_get_past_it_either(self):
        body = ("**分歧与判断**:关键假设甲。替代解释乙(其　翻转指标:丁位升破 61.1)。"
                "反转指标:丙位回落(T+2)。")
        v = self.one("到 2026-09-10 为止,戊位 99.9 一次都没有出现", bodies=(body,))
        self.assertTrue(
            any("INVALIDATION_COLUMN_FLIP_HOST_MISSING" in x for x in v), v)

    def test_the_normal_form_is_unchanged(self):
        """没有插空格的写法必须照旧被认成替代解释自带的那一句。"""
        v = self.one("到 2026-09-10 为止,戊位 99.9 一次都没有出现",
                     bodies=(RING_BODY_TWO_FLIPS,))
        self.assertFalse(
            any("INVALIDATION_COLUMN_FLIP_HOST_MISSING" in x for x in v), v)

    # ---- 逃逸 6:丢一行,两个分数两套分母 ----
    def test_both_scores_use_the_same_denominator_when_a_row_is_missing(self):
        """同一次丢行,一个分母把它算进去、另一个算出去,读者分不出
        「查过 4 行还有 1 行没查」与「总共就 4 行全查过」。"""
        notes = []
        check_report.check_invalidation_independent(
            [("PHP", None, None, []),
             ("THB", "到 2026-09-10 为止,戊位 99.9 一次都没有出现",
              MIRROR_TRIGGER, [RING_BODY])],
            check_report.INVALIDATION_SCOPE_DAILY, notes=notes)
        line = [n for n in notes if "INVALIDATION_COLUMN_CHECKED" in n][0]
        self.assertIn("1/2", line)          # 独立性
        self.assertIn("自身判据 1/2", line)  # 同一个分母,不是 1/1

    def test_the_dropped_row_is_named_in_the_receipt(self):
        """没有名字的分数只说明"少了一行",说不出少的是哪一行。"""
        notes = []
        check_report.check_invalidation_independent(
            [("PHP", None, None, []),
             ("THB", "到 2026-09-10 为止,戊位 99.9 一次都没有出现",
              MIRROR_TRIGGER, [RING_BODY])],
            check_report.INVALIDATION_SCOPE_DAILY, notes=notes)
        line = [n for n in notes if "INVALIDATION_COLUMN_CHECKED" in n][0]
        self.assertIn("PHP", line)

    # ---- 逃逸 6 的另一半:丢行只出声、不改退出码 ----
    def test_a_covered_currency_without_an_overview_row_is_a_violation(self):
        """速览表少一行 = 一个币种的判断根本没发布。SKILL 写死"五币种五行、
        一行都不许少",而实测把 BRL 行的币种格写成 BRLX,生产命令 rc=0 ——
        `OVERVIEW_ROW_MISSING` 有出声,自动化那一侧照样放行。"""
        secs = check_report.sections(
            OVERVIEW_ONE_ROW_REPORT.replace("| BRL |", "| BRLX |"))
        v = check_report.check_overview_row_present(secs, {"USD", "BRL"})
        self.assertTrue(any("OVERVIEW_ROW_ABSENT" in x for x in v), v)
        self.assertTrue(any("BRL" in x for x in v), v)

    def test_a_currency_the_report_does_not_cover_is_not_charged_here(self):
        """报告压根没有该币种节时,负责出声的是 CURRENCY_MISSING;
        同一件事报两条码,读者会以为是两个问题。"""
        secs = check_report.sections(OVERVIEW_ONE_ROW_REPORT)
        v = check_report.check_overview_row_present(secs, {"USD"})
        self.assertEqual(v, [])

    def test_all_rows_present_is_silent(self):
        secs = check_report.sections(OVERVIEW_ONE_ROW_REPORT)
        self.assertEqual(
            check_report.check_overview_row_present(secs, {"USD", "BRL"}), [])

    def test_no_dropped_row_means_no_dropped_row_clause(self):
        """行齐全时不许印那句 —— 恒印一句"丢了 0 行"会把声明变成噪音。"""
        notes = []
        check_report.check_invalidation_independent(
            inval_pairs("到 2026-09-10 为止,戊位 99.9 一次都没有出现"),
            check_report.INVALIDATION_SCOPE_DAILY, notes=notes)
        line = [n for n in notes if "INVALIDATION_COLUMN_CHECKED" in n][0]
        self.assertNotIn("根本不存在", line)


class DecisionTriggerTruncatedDeadlineTest(unittest.TestCase):
    """`DECISION_TRIGGER_TRUNCATED_DEADLINE` —— 日志的 trigger 不许把时限截掉。

    ---- 实测形态(2026-08-19,11/11)----
    `DECISION_TRIGGER_NOT_SOURCED` 判的是「格 ⊇ trigger」,**包含**而非相等。
    包含就允许截断,而实测 11 条 `horizon: open` 的登记全是同一种截断:
    trigger 恰好砍在 `→ 关注…(T+N)` 之前,时限随之丢失,于是
    `claims._validate_horizon` 的「散文没写时限 → open」那一档当场成立。
    后果是这 11 条**永不到期**:复盘材料里恒为"未到期顺延",
    而报告已经把 `(T+3)` 印给读者看了。读者看到的保质期与机器判到期用的那个,
    是两套。

    ---- 为什么不改成"必须相等" ----
    SKILL 第 388 行说日志只登记触发那一半,格里还有「→ 关注<方向>」。
    要求相等会把每一条合规的都打红。判的是**时限这一件**:
    格里有时限串、trigger 里一个都没有 → 违规。
    """

    def one(self, cell, trigger, currency="USD"):
        report = OVERVIEW_REPORT.replace(
            "| USD | 若 A 升破 60.843 → 关注甲(T+2) |", "| USD | %s |" % cell)
        log = {("2026-08-10", currency): {"trigger": trigger}}
        return check_report.check_decision_trigger(
            check_report.sections(report), "2026-08-10", log)

    def test_a_trigger_that_drops_the_deadline_is_a_violation(self):
        v = self.one("若 A 升破 60.843 → 关注甲(T+2)", "若 A 升破 60.843")
        self.assertTrue(
            any("DECISION_TRIGGER_TRUNCATED_DEADLINE" in x for x in v), v)

    def test_the_dropped_deadline_is_named(self):
        """只说"截断了"不够 —— 要说截掉的是哪一个时限,否则回填时得自己再找。"""
        v = self.one("若 A 升破 60.843 → 关注甲(T+2)", "若 A 升破 60.843")
        self.assertTrue(any("T+2" in x for x in v), v)

    def test_a_calendar_deadline_counts_too(self):
        v = self.one("若 A 升破 60.843 → 关注甲(时限:2026-09-11)",
                     "若 A 升破 60.843")
        self.assertTrue(
            any("DECISION_TRIGGER_TRUNCATED_DEADLINE" in x for x in v), v)

    def test_carrying_the_deadline_passes(self):
        v = self.one("若 A 升破 60.843 → 关注甲(T+2)",
                     "若 A 升破 60.843 → 关注甲(T+2)")
        self.assertEqual(v, [])

    def test_a_cell_without_any_deadline_is_not_charged_here(self):
        """格里本来就没有时限时,这条码判不了 —— 那是「条件方向」列自身的事,
        不该借这条码顺手判红(同一件事两条码会被读成两个问题)。"""
        v = self.one("若 A 升破 60.843", "若 A 升破 60.843")
        self.assertEqual(v, [])

    def test_a_partial_deadline_still_counts_as_carried(self):
        """格里两个时限、trigger 带了其中一个 —— 时限没丢,不判红。
        要求"全都带上"会把合规写法打红:格里的第二个时限常在「关注」那半句。"""
        v = self.one("若 A 升破 60.843(T+2) → 关注甲(时限:2026-09-11)",
                     "若 A 升破 60.843(T+2)")
        self.assertEqual(v, [])

    def test_it_does_not_fire_when_the_trigger_is_not_sourced_at_all(self):
        """两条码不叠加:trigger 压根不是格的子串时,该报的是 NOT_SOURCED。
        叠一条截断码只会让读者以为有两处毛病。"""
        v = self.one("若 A 升破 60.843 → 关注甲(T+2)", "日志里另写了一版")
        self.assertTrue(any("DECISION_TRIGGER_NOT_SOURCED" in x for x in v), v)
        self.assertFalse(
            any("DECISION_TRIGGER_TRUNCATED_DEADLINE" in x for x in v), v)


class IsoDateFragmentTest(unittest.TestCase):
    """归属层剥「年-月」碎片时,不许先把整日期切碎。

    ---- 实测(2026-08-19)----
    `YEAR_MONTH_RE` 是 `\\d{4}-\\d{2}(?!\\d)`,而 `2026-09-16` 的后视字符是
    `-` 不是数字 —— 于是它先被削成 ` -16`,`DATE_RE` 再也认不出这是个日期,
    `numbers_in` 吐出一个裸的 `16`。日期里的"日"就这样变成了一个待归属的数。
    整日期在速览与摘要里是常态写法(「到 2026-09-16 的 FOMC 为止」),
    这个 `16` 一旦落在别的币种池里就是一条假红。

    修法:先剥整日期,再剥年-月碎片。两步顺序反过来就是上面那条缺陷。
    """

    def test_a_full_iso_date_leaves_no_day_number(self):
        got = check_report.attributable_numbers("到 2026-09-16 的 FOMC 为止")
        self.assertEqual(got, set(), got)

    def test_the_year_month_fragment_is_still_stripped(self):
        """既有行为不得回退:`参考月 2026-08` 仍不许留下 2026 与 08。"""
        got = check_report.attributable_numbers("美国 CPI 下一期(参考月 2026-08)")
        self.assertEqual(got, set(), got)

    def test_a_real_number_survives_both_strips(self):
        got = check_report.attributable_numbers("到 2026-09-16 为止,3.625 未变")
        self.assertEqual(got, {"3.625"}, got)

    def test_the_summary_layer_uses_it(self):
        """摘要归属层实测同一个顺序缺陷 —— 点名 USD 的一条写了「2026-09-16」,
        而 16 只出现在别的币种切片里时会被判成借了别人的数。"""
        v = map_check(summary=["- 美元:到 2026-09-16 的 FOMC 为止,不变。"])
        self.assertEqual(codes_of(v, "SUMMARY_NUMBER_WRONG_CURRENCY"), [], v)


class WeeklyThemeScopeTest(unittest.TestCase):
    """主线标题里的「(影响 …)」必须真的被读:比对池按它扩,不只按归属格。

    ---- 登记逃逸 5 的形态(2026-08-16 实测)----
    宿主段完全由「主线归属」格点名的段决定。把 BRL 行的第 5 列换成主线二的
    翻转指标原文,再把归属格从「主线二」改成「主线一」——**另一条真实存在、
    并且标题里同样点了 BRL 的主线** —— 比对池就换成了别人的翻转指标,
    抄袭那条码比不出来了(`IS_FLIP_RESTATED` 消失),回执仍印「独立性 5/5」。
    改归属格不是笔误,是把被查方的宿主选择权交给了被查方。

    ---- 修法 ----
    比对池 = 归属格点名的段 ∪ **标题的「影响」子句里点了本币种的段**。
    那个子句是 SKILL 模板里写死的(`### 主线一:<一句话标题>(影响 <币种列表>)`),
    修前**没有任何代码读它**。扩池之后,抄谁的都躲不掉:抄的那条主线只要
    自称影响本币种,就一定在池里。

    实测(reports/weekly/2026-W33.md):五行里只有 BRL 的池会变大
    (归属格只写「主线二」,而主线一的标题写着「影响 …BRL」),
    扩入的那一段与它的失效条件不重合 —— 真实产物零误伤。
    """

    def landing(self, cell, belong):
        return weekly_landing(cell, belong=belong).replace(
            "| PHP | ", "| THB | ", 1)

    def test_switching_attribution_no_longer_hides_a_copied_column(self):
        """归属格改挂主线一,而抄的是主线二的翻转指标 —— 主线二的标题
        点了 THB,所以它照样在池里。"""
        rep = self.landing("下一次定盘泰铢退回 35.2 之下", "主线一")
        v = check_report.check_weekly(rep)
        self.assertTrue(
            any("INVALIDATION_COLUMN_IS_FLIP_RESTATED" in x for x in v), v)

    def test_the_control_still_fires(self):
        rep = self.landing("下一次定盘泰铢退回 35.2 之下", "主线二")
        v = check_report.check_weekly(rep)
        self.assertTrue(
            any("INVALIDATION_COLUMN_IS_FLIP_RESTATED" in x for x in v), v)

    def test_a_theme_that_does_not_claim_this_currency_stays_out(self):
        """扩池只按「影响」子句,不是把所有主线都塞进来 —— 否则任何一行的
        失效条件都要躲开全部主线的翻转指标,合规写法会被大面积打红。"""
        rep = self.landing("下一次定盘比索退回 60.9 之下", "主线二")
        v = check_report.check_weekly(rep)
        self.assertFalse(
            any("INVALIDATION_COLUMN_IS_FLIP_RESTATED" in x for x in v), v)

    def test_a_title_without_the_scope_clause_is_declared(self):
        """标题没写「(影响 …)」时不能默默不扩池 —— 跳过必须带计数出声。"""
        rep = self.landing("戊位 99.9 一次都没有出现", "主线一").replace(
            "### 主线二:泰铢那条腿(影响 THB)", "### 主线二:泰铢那条腿")
        notes = []
        check_report.check_weekly(rep, notes=notes)
        line = "\n".join(notes)
        self.assertIn("WEEKLY_THEME_SCOPE_MISSING", line)
        self.assertIn("1/2", line)

    def test_widening_the_pool_does_not_swallow_the_attribution_code(self):
        """扩池之后 hosts 恒非空。`WEEKLY_THEME_ATTRIBUTION_UNKNOWN` 必须在
        扩池**之前**判,否则这条码会被自己的修法盖掉,
        而「归属写成主线九」照样静默通过。"""
        rep = self.landing("戊位 99.9 一次都没有出现", "主线九")
        v = check_report.check_weekly(rep)
        self.assertTrue(
            any("WEEKLY_THEME_ATTRIBUTION_UNKNOWN" in x for x in v), v)

    def test_all_titles_scoped_means_no_declaration(self):
        notes = []
        check_report.check_weekly(
            self.landing("戊位 99.9 一次都没有出现", "主线一"), notes=notes)
        self.assertNotIn("WEEKLY_THEME_SCOPE_MISSING", "\n".join(notes))


BIS_MACRO_ROW = {"economy": "PH", "indicator": "CPI 同比", "source": "bis",
                 "period": "2026-06", "value": 6.362922,
                 "series_id": "BIS/WS_LONG_CPI/PH", "lag_months": 2}


def bis_snap(rows):
    return json.dumps({"date": "2026-08-10", "rates": {}, "macro": rows,
                       "events": {}, "gaps": []}, ensure_ascii=False)


class BisAttributionTest(unittest.TestCase):
    """`BIS_ATTRIBUTION_MISSING` —— 复现了 BIS 的统计,报告必须署名。

    ---- 为什么是不变量而不是叮嘱(2026-08-21)----
    BIS 统计条款逐字:*"The use of the statistics is unrestricted, provided that:
    if the statistics are reproduced, **the BIS must be cited** in your
    publication or product as the source of the statistics ... No other use is
    permissible."* 它不是文风建议,是**许可的前置条件**。

    实测(2026-08-21,先跑后抄):`data/*.json` 十二天里 **12/12** 的快照含
    `source == "bis"` 的序列,而十二份日报里 **7/12 正文一次都没提过 BIS**
    (任何大小写);提到过的五份里有四份只是附录出处行里的小写 `bis`。
    也就是说这个条件**一直没满足**,而全部闸门一路绿灯。

    本仓对同类问题的既定处置是**消除**不是记录(dbnomics 那次是换源消除)。
    判据取整串子串包含 —— 与结论句、复盘句同规矩:**串由规则给死,报告只准抄**。
    """

    def check(self, report, rows=(BIS_MACRO_ROW,)):
        return check_report.check_bis_attribution(
            check_report.sections(report), json.loads(bis_snap(list(rows))))

    def test_a_report_reproducing_bis_series_must_carry_the_line(self):
        v = self.check("# 外汇日报 2026-08-10\n\n## 附录 C:数据缺漏与影响\n无\n")
        self.assertTrue(any("BIS_ATTRIBUTION_MISSING" in x for x in v), v)

    def test_the_fixed_line_satisfies_it(self):
        v = self.check("# 外汇日报 2026-08-10\n\n## 附录 D:数据来源声明\n"
                       "- 本报告的政策利率、CPI 同比与有效汇率取自 BIS。\n")
        self.assertEqual(v, [])

    def test_a_lowercase_mention_in_an_appendix_is_not_attribution(self):
        """附录出处行里的「来源 bis」是口径注,不是署名 ——
        条款要的是把 BIS 标成 the source of the statistics。"""
        v = self.check("# 外汇日报 2026-08-10\n\n## 附录 B:出处\n"
                       "- CPI 同比 最新 6.362922(来源 bis)\n")
        self.assertTrue(any("BIS_ATTRIBUTION_MISSING" in x for x in v), v)

    def test_a_snapshot_without_bis_rows_is_not_charged(self):
        """没复现 BIS 的统计就没有署名义务 —— 条件句的前件不成立时不许打红。"""
        row = dict(BIS_MACRO_ROW, source="psa", series_id="PSA/2M4ACP23/PH")
        v = self.check("# 外汇日报 2026-08-10\n", rows=(row,))
        self.assertEqual(v, [])

    def test_the_violation_names_how_many_bis_series_were_reproduced(self):
        """没有计数的违规等于没有证据:读者要能看出这份报告引了几条。"""
        rows = (BIS_MACRO_ROW,
                dict(BIS_MACRO_ROW, indicator="政策利率",
                     series_id="BIS/WS_CBPOL/PH"))
        v = self.check("# 外汇日报 2026-08-10\n", rows=rows)
        self.assertTrue(any("2" in x for x in v), v)

    def test_a_malformed_snapshot_is_not_charged(self):
        v = check_report.check_bis_attribution(
            check_report.sections("# 外汇日报 2026-08-10\n"), "不是 dict")
        self.assertEqual(v, [])
