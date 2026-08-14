import json
import os
import subprocess
import sys
import tempfile
import unittest

from scripts import check_report, review, verdicts

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "scripts", "review.py")


def setup_root(tmp, log_entries=None, snapshots=None, brief_date="2026-08-10"):
    for d in ("state", "data", "briefs"):
        os.makedirs(os.path.join(tmp, d), exist_ok=True)
    if log_entries is not None:
        with open(os.path.join(tmp, "state", "decision-log.jsonl"), "w", encoding="utf-8") as f:
            for e in log_entries:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
    for date_str, snap in (snapshots or {}).items():
        with open(os.path.join(tmp, "data", date_str + ".json"), "w", encoding="utf-8") as f:
            json.dump(snap, f)
    brief = os.path.join(tmp, "briefs", brief_date + "-brief.md")
    with open(brief, "w", encoding="utf-8") as f:
        f.write("# 要点表 %s\n" % brief_date)
    return brief


def run_review(tmp, date="2026-08-10"):
    return subprocess.run([sys.executable, SCRIPT, "--date", date, "--root", tmp],
                          capture_output=True, text=True)


def opinion(**over):
    base = {"date": "2026-08-09", "currency": "PHP", "scenario": "s", "trigger": "t",
            "watch_direction": "up",
            "review": {"direction_outcome": None, "trigger_judgement": None, "verdict": None}}
    base.update(over)
    return base


def snap(php_primary):
    return {"rates": {"PHP": {"primary": php_primary}}}


class ReviewTest(unittest.TestCase):
    def _run(self, entries, snapshots):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        brief = setup_root(tmp.name, entries, snapshots)
        r = run_review(tmp.name)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(brief, encoding="utf-8") as f:
            text = f.read()
        log_path = os.path.join(tmp.name, "state", "decision-log.jsonl")
        log = []
        if os.path.exists(log_path):
            with open(log_path, encoding="utf-8") as f:
                log = [json.loads(l) for l in f if l.strip()]
        return text, log

    def test_direction_hit(self):
        text, log = self._run([opinion()],
                              {"2026-08-09": snap(60.0), "2026-08-10": snap(60.5)})
        self.assertIn("方向核对: 命中", text)
        self.assertEqual(log[0]["review"]["direction_outcome"], "命中")

    def test_direction_miss(self):
        text, log = self._run([opinion(watch_direction="down")],
                              {"2026-08-09": snap(60.0), "2026-08-10": snap(60.5)})
        self.assertIn("方向核对: 未命中", text)
        self.assertEqual(log[0]["review"]["direction_outcome"], "未命中")

    def test_missing_rate_undecidable(self):
        text, log = self._run([opinion()],
                              {"2026-08-09": snap(60.0), "2026-08-10": snap(None)})
        self.assertIn("无法判定", text)
        self.assertEqual(log[0]["review"]["direction_outcome"], "无法判定")

    def test_no_pending_opinions_yesterday(self):
        reviewed = opinion()
        reviewed["review"]["direction_outcome"] = "命中"
        text, _ = self._run([reviewed],
                            {"2026-08-09": snap(60.0), "2026-08-10": snap(60.5)})
        self.assertIn("无未复盘观点", text)

    def test_first_run_no_log(self):
        text, _ = self._run(None, {"2026-08-10": snap(60.5)})
        self.assertIn("首次运行,无历史观点可复盘", text)


class ReviewTypeGateTest(unittest.TestCase):
    """类型门补充用例(仓库约定 1/2: isinstance 门 + 数值比较前排除 bool)。"""

    def _root(self, snapshots, raw_log_lines=None):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        brief = setup_root(tmp.name, None, snapshots)
        if raw_log_lines is not None:
            log_path = os.path.join(tmp.name, "state", "decision-log.jsonl")
            with open(log_path, "w", encoding="utf-8") as f:
                for line in raw_log_lines:
                    f.write(line + "\n")
        return tmp.name, brief

    def _run_raw(self, snapshots, raw_log_lines):
        root, brief = self._root(snapshots, raw_log_lines)
        r = run_review(root)
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
        # 约定 2: primary 为 bool(脏快照)→ rate_of 视为 None → 无法判定
        text, log = self._run_raw(
            {"2026-08-09": snap(60.0), "2026-08-10": snap(True)},
            [json.dumps(opinion(), ensure_ascii=False)])
        self.assertIn("方向核对: 无法判定", text)
        self.assertEqual(log[0]["review"]["direction_outcome"], "无法判定")

    def test_malformed_snapshot_shapes_undecidable(self):
        # snap 非 dict / rates 非 dict / entry 非 dict → rate_of 返回 None
        text, log = self._run_raw(
            {"2026-08-09": [1, 2, 3], "2026-08-10": {"rates": {"PHP": "60.5"}}},
            [json.dumps(opinion(), ensure_ascii=False)])
        self.assertIn("方向核对: 无法判定", text)
        self.assertEqual(log[0]["review"]["direction_outcome"], "无法判定")

    def test_corrupt_log_lines_skipped(self):
        # 坏 JSON 行 / 非 dict 行 / 深嵌套 RecursionError 行跳过, 有效观点照常复盘
        deep = "[" * 50000 + "]" * 50000
        text, log = self._run_raw(
            {"2026-08-09": snap(60.0), "2026-08-10": snap(60.5)},
            ["{bad json", "7", deep, json.dumps(opinion(), ensure_ascii=False)])
        self.assertIn("方向核对: 命中", text)
        self.assertEqual(len(log), 1)
        self.assertEqual(log[0]["review"]["direction_outcome"], "命中")

    def test_null_review_field_backfilled(self):
        # review 为 None(外部损坏)→ 视为待复盘, 回填不崩溃
        broken = opinion(review=None)
        text, log = self._run_raw(
            {"2026-08-09": snap(60.0), "2026-08-10": snap(60.5)},
            [json.dumps(broken, ensure_ascii=False)])
        self.assertIn("方向核对: 命中", text)
        self.assertEqual(log[0]["review"]["direction_outcome"], "命中")

    def test_entries_without_str_date_ignored(self):
        # 缺 date / date 非 str 的行在 prior_dates 与 pending 中均被跳过
        no_date = {"currency": "PHP", "watch_direction": "up"}
        int_date = opinion(date=20260809)
        text, _ = self._run_raw(
            {"2026-08-10": snap(60.5)},
            [json.dumps(no_date, ensure_ascii=False),
             json.dumps(int_date, ensure_ascii=False)])
        self.assertIn("首次运行,无历史观点可复盘", text)

    def test_trigger_newline_flattened_in_brief(self):
        # 复审反馈3: trigger 含换行须扁平化为单行, 不得在 brief 注入伪列表行
        entry = opinion(trigger="t\n- 伪列表")
        text, _ = self._run_raw(
            {"2026-08-09": snap(60.0), "2026-08-10": snap(60.5)},
            [json.dumps(entry, ensure_ascii=False)])
        self.assertIn("伪列表", text)
        self.assertNotIn("\n- 伪列表", text)

    def test_nan_primary_undecidable(self):
        # 复审反馈4: primary=NaN 非有限值 → rate_of None → 无法判定(而非"未命中")
        text, log = self._run_raw(
            {"2026-08-09": snap(60.0), "2026-08-10": snap(float("nan"))},
            [json.dumps(opinion(), ensure_ascii=False)])
        self.assertIn("方向核对: 无法判定", text)
        self.assertEqual(log[0]["review"]["direction_outcome"], "无法判定")

    def test_infinity_primary_undecidable(self):
        # 复审反馈4: primary=Infinity 非有限值 → 无法判定(而非"命中")
        text, log = self._run_raw(
            {"2026-08-09": snap(60.0), "2026-08-10": snap(float("inf"))},
            [json.dumps(opinion(), ensure_ascii=False)])
        self.assertIn("方向核对: 无法判定", text)
        self.assertEqual(log[0]["review"]["direction_outcome"], "无法判定")

    def test_no_pending_does_not_rewrite_log(self):
        # 复审反馈5: 无 pending 时不得整文件重写(注入坏行验证其未被清洗)
        reviewed = opinion()
        reviewed["review"]["direction_outcome"] = "命中"
        raw_lines = ["{bad line kept", json.dumps(reviewed, ensure_ascii=False)]
        root, brief = self._root(
            {"2026-08-09": snap(60.0), "2026-08-10": snap(60.5)}, raw_lines)
        log_path = os.path.join(root, "state", "decision-log.jsonl")
        with open(log_path, encoding="utf-8") as f:
            before = f.read()
        r = run_review(root)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(brief, encoding="utf-8") as f:
            text = f.read()
        self.assertIn("无未复盘观点", text)
        with open(log_path, encoding="utf-8") as f:
            after = f.read()
        self.assertEqual(after, before)

    def test_missing_brief_fails(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        setup_root(tmp.name, None, {"2026-08-10": snap(60.5)})
        r = run_review(tmp.name, date="2026-08-11")  # 该日要点表不存在
        self.assertEqual(r.returncode, 1)


if __name__ == "__main__":
    unittest.main()


def snap_ref(php_primary, ref_date):
    return {"rates": {"PHP": {"primary": php_primary, "ref_date": ref_date}}}


def _reviewed_opinion():
    """已复盘过的观点 → pending 为空 → review.py 走「无未复盘观点」那一行。"""
    e = opinion()
    e["review"]["direction_outcome"] = "命中"
    return e


class RefDateBranchTest(ReviewTest):
    """参考价定盘日期三分支(delta spec: 参考价未更新 / 参考日期缺失退回旧行为)。"""

    def test_ref_date_unchanged_reports_no_fixing(self):
        text, log = self._run(
            [opinion()],
            {"2026-08-09": snap_ref(60.75, "2026-08-07"),
             "2026-08-10": snap_ref(60.75, "2026-08-07")})
        self.assertIn("参考价未更新(非工作日)", text)
        # 不得表述为价格持平的市场观察
        self.assertNotIn("方向核对: 命中", text)
        self.assertEqual(log[0]["review"]["direction_outcome"], "无法判定")

    def test_ref_date_changed_uses_normal_comparison(self):
        text, log = self._run(
            [opinion()],
            {"2026-08-09": snap_ref(60.0, "2026-08-07"),
             "2026-08-10": snap_ref(60.5, "2026-08-10")})
        self.assertNotIn("参考价未更新", text)
        self.assertIn("方向核对: 命中", text)
        self.assertEqual(log[0]["review"]["direction_outcome"], "命中")

    def test_legacy_snapshot_without_ref_date_keeps_old_behaviour(self):
        text, log = self._run([opinion()],
                              {"2026-08-09": snap(60.0), "2026-08-10": snap(60.5)})
        self.assertNotIn("参考价未更新", text)
        self.assertIn("方向核对: 命中", text)

    def test_one_side_missing_ref_date_keeps_old_behaviour(self):
        text, _ = self._run(
            [opinion()],
            {"2026-08-09": snap(60.75), "2026-08-10": snap_ref(60.75, "2026-08-10")})
        self.assertNotIn("参考价未更新", text)
        self.assertIn("方向核对: 无法判定", text)   # 数值相等 → 旧逻辑给无法判定


class ReviewOutputIsRecognizedByCheckerTest(unittest.TestCase):
    """review.py 追加进要点表的**每一行**,校验器都必须认得出来。

    `--strict-brief` 会豁免这些行的数字溯源(它们属于观点日,不属于当日快照)。
    豁免的判据是「块头 + 行式样」,而块头与行式样是 review.py 产出的 ——
    两处一旦漂移,豁免要么失效(整块变红,就是本次修的那个缺陷复发),要么
    反过来把手写行也豁免掉。这个类是两处之间**唯一的机械联系**:凭印象写的
    正则在这里会立刻红。"""

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
        "命中": ([opinion()], {"2026-08-09": snap(60.0), "2026-08-10": snap(60.5)}),
        "未命中": ([opinion(watch_direction="down")],
                   {"2026-08-09": snap(60.0), "2026-08-10": snap(60.5)}),
        "汇率 None": ([opinion(watch_direction=None)],
                      {"2026-08-09": snap(None), "2026-08-10": snap(None)}),
        "参考价未更新": ([opinion()],
                         {"2026-08-09": snap_ref(60.75, "2026-08-07"),
                          "2026-08-10": snap_ref(60.75, "2026-08-07")}),
        "无未复盘观点": ([_reviewed_opinion()],
                         {"2026-08-09": snap(60.0), "2026-08-10": snap(60.5)}),
        "首次运行": (None, {"2026-08-10": snap(60.5)}),
    }

    def test_heading_emitted_matches_the_checker_constant(self):
        for label, (entries, snapshots) in self.CASES.items():
            with self.subTest(case=label):
                lines = self._appended(entries, snapshots)
                self.assertIn(check_report.REVIEW_BLOCK_HEADING, lines,
                              "review.py 的块头与校验器常量不一致:%r" % lines)

    def test_direction_sentence_rides_inside_a_recognised_line(self):
        """方向核对句是**加进既有行**的一个字段,不是新起一行 —— 新起一行会
        落到豁免式样之外,被 --strict-brief 当成 LLM 手写行照查(实测:那正是
        本仓库此前 4 条 BRIEF_NUMBER_UNTRACEABLE 的成因)。"""
        lines = self._appended(*self.CASES["命中"])
        carriers = [ln for ln in lines if "方向核对句: " in ln]
        self.assertEqual(len(carriers), 1, lines)
        self.assertTrue(check_report.is_generated_review_line(carriers[0]),
                        carriers[0])

    def test_every_appended_line_is_exempted_by_the_checker(self):
        for label, (entries, snapshots) in self.CASES.items():
            with self.subTest(case=label):
                lines = self._appended(entries, snapshots)
                self.assertTrue(lines)
                for line in lines:
                    self.assertTrue(
                        check_report.is_generated_review_line(line),
                        "校验器认不出 review.py 生成的行:%r" % line)


class DirectionSentenceTest(unittest.TestCase):
    """方向核对给出的那一句,必须经 `scripts/verdicts.join_verdict` 拼装。

    存在理由(设计 §8 阶段 1 末尾那件"小事"):`direction_outcome` 是脚本机械
    算出的结论,实测**零个下游消费者** —— 它只以"方向核对: X"三个字躺在要点
    表里,而流向读者的那个 verdict 是 LLM 自己写的。给它接上第一个消费者:
    脚本拼出**完整的一句**,报告逐字引用整句。

    句子必须**经共享拼装口**产出:自己拼会在分隔符(全角顿号)、括号(ASCII)
    与"没有 caveat 时不得拼出空括号"三处各漂一次,而这三处正是逐字引用检查
    的比对对象 —— 漂了以后报告与要点表两处的同一句话不再相等。
    """

    HEAD_CASE = dict(date="2026-08-09", currency="PHP", outcome="命中",
                     watch_direction="up", prev_rate=60.0, today_rate=60.5,
                     fixing_unchanged=False)

    def test_assembler_is_the_shared_one(self):
        self.assertIs(review.join_verdict, verdicts.join_verdict)

    def test_sentence_is_verbatim(self):
        self.assertEqual(
            review.direction_sentence(**self.HEAD_CASE),
            "2026-08-09 PHP 方向核对:命中(关注方向 up、观点日读数 60.0、"
            "当日读数 60.5)")

    def test_sentence_equals_what_the_shared_assembler_would_give(self):
        """措辞可以改,拼装口不可以绕 —— 这条断言只钉"经过 join_verdict"。"""
        self.assertEqual(
            review.direction_sentence(**self.HEAD_CASE),
            verdicts.join_verdict("2026-08-09 PHP 方向核对:命中",
                                  ["关注方向 up", "观点日读数 60.0",
                                   "当日读数 60.5"]))

    def test_bypassing_the_assembler_is_detectable(self):
        """自己用 % 或 join 拼的实现在这里必红:补丁换掉 join_verdict 之后,
        句子必须跟着变。"""
        original = review.join_verdict
        self.addCleanup(setattr, review, "join_verdict", original)
        review.join_verdict = lambda head, caveats: "SENTINEL<%s|%s>" % (
            head, ",".join(caveats))
        got = review.direction_sentence(**self.HEAD_CASE)
        self.assertTrue(got.startswith("SENTINEL<"), got)
        self.assertIn("2026-08-09 PHP 方向核对:命中", got)

    def test_fixing_unchanged_replaces_the_two_readings(self):
        case = dict(self.HEAD_CASE, fixing_unchanged=True, outcome="无法判定",
                    prev_rate=60.75, today_rate=60.75)
        self.assertEqual(review.direction_sentence(**case),
                         "2026-08-09 PHP 方向核对:无法判定(关注方向 up、"
                         "参考价未更新(非工作日))")

    def test_missing_readings_are_declared_not_printed_as_none(self):
        case = dict(self.HEAD_CASE, outcome="无法判定", prev_rate=60.0,
                    today_rate=None)
        got = review.direction_sentence(**case)
        self.assertIn("当日无读数", got)
        self.assertNotIn("None", got)

    def test_unrecorded_watch_direction_is_normalised(self):
        """`watch_direction` 是 LLM 文本。原样插进句子会把任意字符(含竖线、
        伪造的字段名)带进这条要被逐字引用的话 —— 只认 up/down 两个值。"""
        for bad in (None, "", "上", "up | 关注方向: down", 7, True):
            with self.subTest(bad=bad):
                got = review.direction_sentence(
                    **dict(self.HEAD_CASE, watch_direction=bad))
                self.assertIn("关注方向未记录", got)
                self.assertEqual(len(got.splitlines()), 1)
                self.assertNotIn("|", got)

    def test_sentence_carries_no_plumbing_word_and_no_field_name(self):
        """这句话要被逐字抄进正文复盘节。它自己带管道语汇或快照字段名的话,
        正文位置闸门会把脚本自己的产出判成违规(自伤形态)。"""
        got = review.direction_sentence(**self.HEAD_CASE)
        for word in ("快照", "primary", "derived", "null", "缺漏", "条目",
                     "采集失败", "不可得", "通道", ".json", "#rates"):
            self.assertNotIn(word, got, word)

    def test_sentence_reaches_the_brief_verbatim(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        brief = setup_root(tmp.name, [opinion()],
                           {"2026-08-09": snap(60.0), "2026-08-10": snap(60.5)})
        r = run_review(tmp.name)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(brief, encoding="utf-8") as f:
            text = f.read()
        self.assertIn(review.direction_sentence(**self.HEAD_CASE), text)

    def test_sentence_covers_every_pending_opinion(self):
        entries = [opinion(currency="PHP"), opinion(currency="THB")]
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        brief = setup_root(tmp.name, entries,
                           {"2026-08-09": {"rates": {"PHP": {"primary": 60.0},
                                                     "THB": {"primary": 33.0}}},
                            "2026-08-10": {"rates": {"PHP": {"primary": 60.5},
                                                     "THB": {"primary": 33.5}}}})
        self.assertEqual(run_review(tmp.name).returncode, 0)
        with open(brief, encoding="utf-8") as f:
            text = f.read()
        self.assertEqual(text.count("方向核对句: "), 2, text)
        for c in ("PHP", "THB"):
            self.assertIn("2026-08-09 %s 方向核对:命中" % c, text)

    def test_outcome_in_the_sentence_is_the_one_the_script_computed(self):
        """句子里的结论词与回填进日志的那个必须同源同字,不得各算一次。"""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        brief = setup_root(tmp.name, [opinion(watch_direction="down")],
                           {"2026-08-09": snap(60.0), "2026-08-10": snap(60.5)})
        self.assertEqual(run_review(tmp.name).returncode, 0)
        with open(brief, encoding="utf-8") as f:
            text = f.read()
        with open(os.path.join(tmp.name, "state", "decision-log.jsonl"),
                  encoding="utf-8") as f:
            logged = json.loads(f.readline())["review"]["direction_outcome"]
        self.assertEqual(logged, "未命中")
        self.assertIn("2026-08-09 PHP 方向核对:未命中", text)
