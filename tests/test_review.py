import json
import os
import subprocess
import sys
import tempfile
import unittest

from scripts import check_report, claims, review

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "scripts", "review.py")


def setup_root(tmp, log_entries=None, snapshots=None, brief_date="2026-08-10"):
    for d in ("state", "data", "briefs"):
        os.makedirs(os.path.join(tmp, d), exist_ok=True)
    if log_entries is not None:
        with open(os.path.join(tmp, "state", "decision-log.jsonl"), "w",
                  encoding="utf-8") as f:
            for e in log_entries:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
    for date_str, snap in (snapshots or {}).items():
        with open(os.path.join(tmp, "data", date_str + ".json"), "w",
                  encoding="utf-8") as f:
            json.dump(snap, f)
    brief = os.path.join(tmp, "briefs", brief_date + "-brief.md")
    with open(brief, "w", encoding="utf-8") as f:
        f.write("# 要点表 %s\n" % brief_date)
    return brief


def run_review(tmp, date="2026-08-10"):
    return subprocess.run([sys.executable, SCRIPT, "--date", date, "--root", tmp],
                          capture_output=True, text=True)


# 归因词表:任何**解释原因**的说法都不许进「参考价未更新」那句话。「非工作日」
# 是原病灶,其余是同型替代 —— 必须被测试杀掉的变异里点名了「换成另一种原因断言」。
# 放在模块层是因为 tests/test_skill_docs.py 也要用同一份:词表分两份写,脚本与
# SKILL 两边就会各禁各的。
# **按名字导入这个元组,不要导入下面的 TestCase 类** —— 把 TestCase 导进另一个
# 测试模块,unittest discover 会在两个模块里各跑它一遍(实测总数由 824 虚涨到 834)。
UNCHANGED_REF_CAUSE_WORDS = ("非工作日", "非交易日", "休市", "假日", "节假日",
                             "周末", "停市", "停牌", "闭市", "不开盘")


def opinion(**over):
    """默认:观点日 08-09、时限 T+1、比索升破 60.2。"""
    base = {"date": "2026-08-09", "currency": "PHP", "scenario": "s",
            "trigger": "比索升破 60.2(T+1)", "watch_direction": "up",
            "claim": {"horizon": {"kind": "running_days", "n": 1,
                                  "quote": "T+1"},
                      "legs": [{"currency": "PHP", "field": "primary",
                                "op": "gt", "threshold": "60.2"}]},
            "review": {"status": None, "basis": None}}
    base.update(over)
    return base


def snap(php_primary, ref_date="2026-08-10"):
    return {"rates": {"PHP": {"primary": php_primary, "ref_date": ref_date}}}


class ReviewRunner(unittest.TestCase):
    def _run(self, entries, snapshots, date="2026-08-10"):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        brief = setup_root(tmp.name, entries, snapshots, brief_date=date)
        r = run_review(tmp.name, date)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(brief, encoding="utf-8") as f:
            text = f.read()
        log_path = os.path.join(tmp.name, "state", "decision-log.jsonl")
        log = []
        if os.path.exists(log_path):
            with open(log_path, encoding="utf-8") as f:
                log = [json.loads(l) for l in f if l.strip()]
        return text, log


class ReviewsByHorizonNotByLatestDateTest(ReviewRunner):
    """修前 `review.py` 写死 `target = prior_dates[-1]` —— 永远只复盘"上一个
    记过的日子",而速览表的触发条件写的是 (T+3)。于是一条三个运行日的观点
    第二天就被拿去判。这个类钉住:复盘的依据是**时限到没到**,不是日期新旧。
    """

    def test_two_opinion_dates_can_fall_due_on_the_same_day(self):
        older = opinion(date="2026-08-08", currency="PHP",
                        trigger="比索升破 60.2(T+2)",
                        claim={"horizon": {"kind": "running_days", "n": 2,
                                           "quote": "T+2"},
                               "legs": [{"currency": "PHP", "field": "primary",
                                         "op": "gt", "threshold": "60.2"}]})
        text, log = self._run(
            [older, opinion()],
            {"2026-08-08": snap(60.0, "2026-08-08"),
             "2026-08-09": snap(60.1, "2026-08-09"),
             "2026-08-10": snap(60.5, "2026-08-10")})
        self.assertIn("观点日 2026-08-08", text)
        self.assertIn("观点日 2026-08-09", text)
        self.assertEqual([e["review"]["status"] for e in log], ["命中", "命中"])

    def test_an_overdue_entry_is_still_picked_up_later(self):
        """已过期且尚未定论的条目,今天照样要复盘。"""
        stale = opinion(date="2026-08-08")
        text, log = self._run(
            [stale],
            {"2026-08-08": snap(60.0, "2026-08-08"),
             "2026-08-09": snap(60.5, "2026-08-09"),
             "2026-08-10": snap(60.9, "2026-08-10")})
        self.assertIn("观点日 2026-08-08", text)
        self.assertEqual(log[0]["review"]["status"], "命中")

    def test_a_horizon_that_has_not_run_out_is_not_reviewed(self):
        waiting = opinion(trigger="比索升破 60.2(T+3)",
                          claim={"horizon": {"kind": "running_days", "n": 3,
                                             "quote": "T+3"},
                                 "legs": [{"currency": "PHP",
                                           "field": "primary", "op": "gt",
                                           "threshold": "60.2"}]})
        text, log = self._run(
            [waiting],
            {"2026-08-09": snap(60.0, "2026-08-09"),
             "2026-08-10": snap(60.1, "2026-08-10")})
        # 不出**结论行** —— 时限没到就不该有结论
        self.assertNotIn("| 结论: ", text)
        # 记进日志:日志要能回答"这条现在什么状态",否则 stats 与周报的
        # 「未到期」栏永远是 0,拆出这一档等于白拆。
        self.assertEqual(log[0]["review"]["status"], "未到期")

    def test_pending_entries_are_listed_as_a_register_not_a_conclusion(self):
        """顺延登记行:它让要点表继续持有"还在观察的那几条"的原文。

        没有它,这些观点的情景与触发条件当天就从要点表消失,而报告的
        「本期相对上期的变化」节仍要引用它们的数 —— 实测 2026-08-13 的
        0.094 / 4.249 / 9.609 三个数因此被判 NUMBER_UNTRACEABLE。
        """
        waiting = opinion(trigger="比索升破 60.2(T+3)",
                          claim={"horizon": {"kind": "running_days", "n": 3,
                                             "quote": "T+3"},
                                 "legs": [{"currency": "PHP",
                                           "field": "primary", "op": "gt",
                                           "threshold": "60.2"}]})
        text, _ = self._run(
            [waiting],
            {"2026-08-09": snap(60.0, "2026-08-09"),
             "2026-08-10": snap(60.1, "2026-08-10")})
        self.assertIn("- 顺延 | PHP | 观点日 2026-08-09", text)
        self.assertIn("比索升破 60.2(T+3)", text)
        self.assertNotIn("| 结论: ", text)

    def test_a_pending_entry_is_re_examined_the_next_day(self):
        """「未到期」是会变的状态,不是定论 —— 明天时限到了就得重判。"""
        waiting = opinion(trigger="比索升破 60.2(T+2)",
                          claim={"horizon": {"kind": "running_days", "n": 2,
                                             "quote": "T+2"},
                                 "legs": [{"currency": "PHP",
                                           "field": "primary", "op": "gt",
                                           "threshold": "60.2"}]})
        snapshots = {"2026-08-09": snap(60.0, "2026-08-09"),
                     "2026-08-10": snap(60.1, "2026-08-10"),
                     "2026-08-11": snap(60.5, "2026-08-11")}
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        setup_root(tmp.name, [waiting], snapshots, brief_date="2026-08-10")
        with open(os.path.join(tmp.name, "briefs", "2026-08-11-brief.md"), "w",
                  encoding="utf-8") as f:
            f.write("# 要点表 2026-08-11\n")
        self.assertEqual(run_review(tmp.name, "2026-08-10").returncode, 0)
        self.assertEqual(run_review(tmp.name, "2026-08-11").returncode, 0)
        log_path = os.path.join(tmp.name, "state", "decision-log.jsonl")
        with open(log_path, encoding="utf-8") as f:
            log = [json.loads(l) for l in f if l.strip()]
        self.assertEqual(log[0]["review"]["status"], "命中")

    def test_a_concluded_entry_is_not_reviewed_twice(self):
        done = opinion()
        done["review"] = {"status": "命中", "basis": "b"}
        text, log = self._run(
            [done],
            {"2026-08-09": snap(60.0, "2026-08-09"),
             "2026-08-10": snap(60.5, "2026-08-10")})
        self.assertNotIn("复盘句: ", text)
        self.assertEqual(log[0]["review"], {"status": "命中", "basis": "b"})


class ReviewDeclaresItsCountsTest(ReviewRunner):
    """一条都没有时不得静默输出空节 —— 每处跳过/放行都要带计数的声明。"""

    def test_declaration_is_printed_when_nothing_falls_due(self):
        waiting = opinion(trigger="比索升破 60.2(T+3)",
                          claim={"horizon": {"kind": "running_days", "n": 3,
                                             "quote": "T+3"},
                                 "legs": [{"currency": "PHP",
                                           "field": "primary", "op": "gt",
                                           "threshold": "60.2"}]})
        text, _ = self._run(
            [waiting],
            {"2026-08-09": snap(60.0, "2026-08-09"),
             "2026-08-10": snap(60.1, "2026-08-10")})
        self.assertIn("到期复盘 0 条", text)
        self.assertIn("未到期 1 条顺延", text)

    def test_pending_status_is_not_treated_as_a_conclusion(self):
        """已定论的条目不再复盘,但「未到期」不算定论 —— 把它算成定论
        就等于把不利结果养到永远不判。"""
        waiting = opinion(trigger="比索升破 60.2(T+3)",
                          claim={"horizon": {"kind": "running_days", "n": 3,
                                             "quote": "T+3"},
                                 "legs": [{"currency": "PHP",
                                           "field": "primary", "op": "gt",
                                           "threshold": "60.2"}]})
        waiting["review"] = {"status": "未到期", "basis": "b"}
        text, _ = self._run(
            [waiting],
            {"2026-08-09": snap(60.0, "2026-08-09"),
             "2026-08-10": snap(60.1, "2026-08-10")})
        self.assertIn("未到期 1 条顺延", text)
        self.assertIn("已定论 0 条", text)

    def test_declaration_counts_entries_registered_before_the_schema(self):
        legacy = {"date": "2026-08-09", "currency": "THB", "scenario": "s",
                  "trigger": "t", "watch_direction": "up"}
        text, _ = self._run(
            [legacy, opinion()],
            {"2026-08-09": snap(60.0, "2026-08-09"),
             "2026-08-10": snap(60.5, "2026-08-10")})
        self.assertIn("结构化字段之前的历史观点 1 条", text)

    def test_declaration_is_printed_even_when_something_falls_due(self):
        text, _ = self._run(
            [opinion()],
            {"2026-08-09": snap(60.0, "2026-08-09"),
             "2026-08-10": snap(60.5, "2026-08-10")})
        self.assertIn("到期复盘 1 条", text)

    def test_first_run_no_log(self):
        text, _ = self._run(None, {"2026-08-10": snap(60.5)})
        self.assertIn("首次运行,无历史观点可复盘", text)


class ConclusionComesFromResolveClaimTest(ReviewRunner):
    """结论只能由 `claims.resolve_claim` 给出 —— 报告逐字引用的就是它那一句。"""

    def test_basis_recorded_in_the_log_is_the_resolver_sentence(self):
        entries = [opinion()]
        snapshots = {"2026-08-09": snap(60.0, "2026-08-09"),
                     "2026-08-10": snap(60.5, "2026-08-10")}
        text, log = self._run(entries, snapshots)
        expected = claims.resolve_claim(
            opinion(),
            [("2026-08-09", snapshots["2026-08-09"]),
             ("2026-08-10", snapshots["2026-08-10"])])
        self.assertEqual(log[0]["review"]["basis"], expected.sentence)
        self.assertIn(expected.sentence, text)

    def test_miss_is_recorded_when_the_window_closes_untriggered(self):
        _, log = self._run(
            [opinion()],
            {"2026-08-09": snap(60.0, "2026-08-09"),
             "2026-08-10": snap(60.1, "2026-08-10")})
        self.assertEqual(log[0]["review"]["status"], "未命中")

    def test_undecidable_only_when_the_observation_is_missing(self):
        _, log = self._run(
            [opinion()],
            {"2026-08-09": snap(60.0, "2026-08-09"),
             "2026-08-10": snap(60.0, "2026-08-09")})
        self.assertEqual(log[0]["review"]["status"], "无法判定")
        self.assertIn("只取到 0 次新定盘", log[0]["review"]["basis"])

    def test_no_status_word_is_produced_outside_the_four_buckets(self):
        _, log = self._run(
            [opinion()],
            {"2026-08-09": snap(60.0, "2026-08-09"),
             "2026-08-10": snap(60.5, "2026-08-10")})
        self.assertIn(log[0]["review"]["status"], claims.STATUSES)


class ReviewRobustnessTest(unittest.TestCase):
    """类型门与容错路径(仓库约定 1/2: isinstance 门 + 数值比较前排除 bool)。"""

    def _root(self, snapshots, raw_log_lines=None, date="2026-08-10"):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        brief = setup_root(tmp.name, None, snapshots, brief_date=date)
        if raw_log_lines is not None:
            log_path = os.path.join(tmp.name, "state", "decision-log.jsonl")
            with open(log_path, "w", encoding="utf-8") as f:
                for line in raw_log_lines:
                    f.write(line + "\n")
        return tmp.name, brief

    def _run_raw(self, snapshots, raw_log_lines, date="2026-08-10"):
        root, brief = self._root(snapshots, raw_log_lines, date)
        r = run_review(root, date)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(brief, encoding="utf-8") as f:
            text = f.read()
        log_path = os.path.join(root, "state", "decision-log.jsonl")
        log = []
        if os.path.exists(log_path):
            with open(log_path, encoding="utf-8") as f:
                log = [json.loads(l) for l in f if l.strip()]
        return text, log

    def test_bool_primary_treated_as_missing(self):
        _, log = self._run_raw(
            {"2026-08-09": snap(60.0, "2026-08-09"),
             "2026-08-10": snap(True, "2026-08-10")},
            [json.dumps(opinion(), ensure_ascii=False)])
        self.assertEqual(log[0]["review"]["status"], "无法判定")

    def test_nan_primary_undecidable(self):
        _, log = self._run_raw(
            {"2026-08-09": snap(60.0, "2026-08-09"),
             "2026-08-10": snap(float("nan"), "2026-08-10")},
            [json.dumps(opinion(), ensure_ascii=False)])
        self.assertEqual(log[0]["review"]["status"], "无法判定")

    def test_infinity_primary_undecidable(self):
        _, log = self._run_raw(
            {"2026-08-09": snap(60.0, "2026-08-09"),
             "2026-08-10": snap(float("inf"), "2026-08-10")},
            [json.dumps(opinion(), ensure_ascii=False)])
        self.assertEqual(log[0]["review"]["status"], "无法判定")

    def test_malformed_snapshot_shapes_undecidable(self):
        _, log = self._run_raw(
            {"2026-08-09": [1, 2, 3], "2026-08-10": {"rates": {"PHP": "60.5"}}},
            [json.dumps(opinion(), ensure_ascii=False)])
        self.assertEqual(log[0]["review"]["status"], "无法判定")

    def test_corrupt_log_lines_skipped(self):
        deep = "[" * 50000 + "]" * 50000
        _, log = self._run_raw(
            {"2026-08-09": snap(60.0, "2026-08-09"),
             "2026-08-10": snap(60.5, "2026-08-10")},
            ["{bad json", "7", deep, json.dumps(opinion(), ensure_ascii=False)])
        self.assertEqual(len(log), 1)
        self.assertEqual(log[0]["review"]["status"], "命中")

    def test_null_review_field_backfilled(self):
        _, log = self._run_raw(
            {"2026-08-09": snap(60.0, "2026-08-09"),
             "2026-08-10": snap(60.5, "2026-08-10")},
            [json.dumps(opinion(review=None), ensure_ascii=False)])
        self.assertEqual(log[0]["review"]["status"], "命中")

    def test_broken_claim_falls_into_the_fourth_bucket_without_crashing(self):
        _, log = self._run_raw(
            {"2026-08-09": snap(60.0, "2026-08-09"),
             "2026-08-10": snap(60.5, "2026-08-10")},
            [json.dumps(opinion(claim={"horizon": 7}), ensure_ascii=False)])
        self.assertEqual(log[0]["review"]["status"], "无法判定")

    def test_entries_without_str_date_ignored(self):
        no_date = {"currency": "PHP", "watch_direction": "up"}
        text, _ = self._run_raw(
            {"2026-08-10": snap(60.5)},
            [json.dumps(no_date, ensure_ascii=False),
             json.dumps(opinion(date=20260809), ensure_ascii=False)])
        self.assertIn("首次运行,无历史观点可复盘", text)

    def test_trigger_newline_flattened_in_brief(self):
        e = opinion(trigger="比索升破 60.2(T+1)\n- 伪列表")
        text, _ = self._run_raw(
            {"2026-08-09": snap(60.0, "2026-08-09"),
             "2026-08-10": snap(60.5, "2026-08-10")},
            [json.dumps(e, ensure_ascii=False)])
        self.assertIn("伪列表", text)
        self.assertNotIn("\n- 伪列表", text)

    def test_nothing_due_does_not_rewrite_log(self):
        done = opinion()
        done["review"] = {"status": "命中", "basis": "b"}
        raw_lines = ["{bad line kept", json.dumps(done, ensure_ascii=False)]
        root, brief = self._root(
            {"2026-08-09": snap(60.0, "2026-08-09"),
             "2026-08-10": snap(60.5, "2026-08-10")}, raw_lines)
        log_path = os.path.join(root, "state", "decision-log.jsonl")
        with open(log_path, encoding="utf-8") as f:
            before = f.read()
        r = run_review(root)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(log_path, encoding="utf-8") as f:
            self.assertEqual(f.read(), before)

    def test_missing_brief_fails(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        setup_root(tmp.name, None, {"2026-08-10": snap(60.5)})
        r = run_review(tmp.name, date="2026-08-11")
        self.assertEqual(r.returncode, 1)


class ReviewOutputIsRecognizedByCheckerTest(unittest.TestCase):
    """review.py 追加进要点表的**每一行**,校验器都必须认得出来。

    「要点表 ⊆ 快照」那一层会豁免这些行的数字溯源(它们属于观点日,不属于
    当日快照)。豁免的判据是「块头 + 行式样」,而块头与行式样是 review.py
    产出的 —— 两处一旦漂移,豁免要么失效(整块变红),要么反过来把手写行也
    豁免掉。这个类是两处之间**唯一的机械联系**:凭印象写的正则在这里立刻红。
    """

    def _appended(self, entries, snapshots, date="2026-08-10"):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        brief = setup_root(tmp.name, entries, snapshots, brief_date=date)
        with open(brief, encoding="utf-8") as f:
            before = f.read()
        r = run_review(tmp.name, date)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(brief, encoding="utf-8") as f:
            after = f.read()
        self.assertTrue(after.startswith(before), "review.py 改写了既有内容")
        return after[len(before):].splitlines()

    CASES = {
        "命中": ([opinion()], {"2026-08-09": snap(60.0, "2026-08-09"),
                               "2026-08-10": snap(60.5, "2026-08-10")}),
        "未命中": ([opinion()], {"2026-08-09": snap(60.0, "2026-08-09"),
                                 "2026-08-10": snap(60.1, "2026-08-10")}),
        "无法判定": ([opinion()], {"2026-08-09": snap(60.0, "2026-08-09"),
                                   "2026-08-10": snap(60.0, "2026-08-09")}),
        "未到期": ([opinion(trigger="比索升破 60.2(T+3)",
                            claim={"horizon": {"kind": "running_days", "n": 3,
                                               "quote": "T+3"},
                                   "legs": [{"currency": "PHP",
                                             "field": "primary", "op": "gt",
                                             "threshold": "60.2"}]})],
                    {"2026-08-09": snap(60.0, "2026-08-09"),
                     "2026-08-10": snap(60.1, "2026-08-10")}),
        "首次运行": (None, {"2026-08-10": snap(60.5)}),
    }

    def test_heading_emitted_matches_the_checker_constant(self):
        for label, (entries, snapshots) in self.CASES.items():
            with self.subTest(case=label):
                lines = self._appended(entries, snapshots)
                self.assertIn(check_report.REVIEW_BLOCK_HEADING, lines,
                              "review.py 的块头与校验器常量不一致:%r" % lines)

    def test_every_appended_line_is_exempted_by_the_checker(self):
        for label, (entries, snapshots) in self.CASES.items():
            with self.subTest(case=label):
                lines = self._appended(entries, snapshots)
                self.assertTrue(lines)
                for line in lines:
                    self.assertTrue(
                        check_report.is_generated_review_line(line),
                        "校验器认不出 review.py 生成的行:%r" % line)

    def test_pending_register_line_is_recognised(self):
        lines = self._appended(*self.CASES["未到期"])
        carriers = [ln for ln in lines if ln.startswith("- 顺延 |")]
        self.assertEqual(len(carriers), 1, lines)
        self.assertTrue(check_report.is_generated_review_line(carriers[0]),
                        carriers[0])

    def test_arbitrary_text_in_the_pending_register_is_not_exempted(self):
        forged = "- 顺延 | PHP | 观点日 2026-08-09 | 情景: s | 触发条件: t | 复盘句: 随便写"
        self.assertFalse(check_report.is_generated_review_line(forged), forged)

    def test_review_sentence_rides_inside_a_recognised_line(self):
        """复盘句是**加进既有行**的一个字段,不是新起一行 —— 新起一行会落到
        豁免式样之外,被当成 LLM 手写行照查(实测:那正是本仓库此前 4 条
        BRIEF_NUMBER_UNTRACEABLE 的成因)。"""
        lines = self._appended(*self.CASES["命中"])
        carriers = [ln for ln in lines if "复盘句: " in ln]
        self.assertEqual(len(carriers), 1, lines)
        self.assertTrue(check_report.is_generated_review_line(carriers[0]),
                        carriers[0])

    def test_arbitrary_text_in_the_sentence_segment_is_not_exempted(self):
        forged = ("- PHP | 观点日 2026-08-09 | 情景: s | 触发条件: t"
                  " | 复盘句: 随便写一句 | 结论: 命中")
        self.assertFalse(check_report.is_generated_review_line(forged), forged)


class ReviewSentenceStaysOutOfPlumbingVocabularyTest(unittest.TestCase):
    """复盘句要**逐字落进正文**,而正文位置闸门禁的正是管道语汇 ——
    脚本自己的产出不得触发它(自伤形态)。"""

    BANNED = ("快照", "采集", "字段", "JSON", "无公告", "无数据", "采集失败")

    def _sentences(self):
        base = {"rates": {"PHP": {"primary": 60.0, "ref_date": "2026-08-09"}}}
        cases = [
            [("2026-08-09", base), ("2026-08-10", snap(60.5, "2026-08-10"))],
            [("2026-08-09", base), ("2026-08-10", snap(60.1, "2026-08-10"))],
            [("2026-08-09", base), ("2026-08-10", snap(60.0, "2026-08-09"))],
            [("2026-08-09", base), ("2026-08-10", {"rates": {}})],
        ]
        return [claims.resolve_claim(opinion(), c).sentence for c in cases]

    def test_no_plumbing_word_in_any_sentence(self):
        for sentence in self._sentences():
            for word in self.BANNED:
                self.assertNotIn(word, sentence, sentence)

    def test_unchanged_ref_note_names_the_ref_date_and_nothing_else(self):
        self.assertEqual(claims.unchanged_ref_note("2026-08-07"),
                         "参考价未更新(仍为 2026-08-07 定盘)")

    def test_unchanged_ref_note_carries_whatever_ref_date_it_is_given(self):
        """带上那个日期是硬要求:读者据此自己判断,脚本不替他判断。"""
        for d in ("2026-08-07", "1999-12-31", "2026-08-12"):
            with self.subTest(ref_date=d):
                self.assertIn(d, claims.unchanged_ref_note(d))

    def test_unchanged_ref_note_asserts_no_cause(self):
        """修的缺陷:修前**无条件**写「参考价未更新(非工作日)」,而脚本从不
        查任何日程表。实测 2026-08-12 是周三、08-14 是周五,四个币种都不休市;
        这句假归因还经复盘节逐字引用流回了正文。"""
        for d in ("2026-08-07", "2026-08-14"):
            note = claims.unchanged_ref_note(d)
            for word in UNCHANGED_REF_CAUSE_WORDS:
                with self.subTest(ref_date=d, word=word):
                    self.assertNotIn(word, note,
                                     "这句话在断言原因:%r" % note)

    def test_checker_takes_the_note_wording_from_the_producer(self):
        """校验器不得手抄这句话 —— 手抄的正则实测漏过转义,式样反而要求
        「没有括号」。"""
        self.assertIs(check_report.unchanged_ref_note,
                      claims.unchanged_ref_note)


class ReviewModuleSurfaceTest(unittest.TestCase):
    def test_heading_is_owned_by_the_producer(self):
        self.assertIs(check_report.REVIEW_BLOCK_HEADING,
                      review.REVIEW_BLOCK_HEADING)

    def test_llm_written_direction_verdict_entry_points_are_gone(self):
        """`direction_outcome` 与 LLM 回填的 verdict 都不再是结论来源。"""
        self.assertFalse(hasattr(review, "direction_outcome"))
        self.assertFalse(hasattr(review, "direction_sentence"))


if __name__ == "__main__":
    unittest.main()
