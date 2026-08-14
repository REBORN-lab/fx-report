import ast
import json
import os
import subprocess
import sys
import tempfile
import unittest

from scripts import log_decision

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "scripts", "log_decision.py")


def run_cmd(args, stdin_text=None):
    return subprocess.run([sys.executable, SCRIPT] + args, input=stdin_text,
                          capture_output=True, text=True)


def read_log(root):
    path = os.path.join(root, "state", "decision-log.jsonl")
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


CLAIM = {"horizon": {"kind": "running_days", "n": 2, "quote": "T+2"},
         "legs": [{"currency": "PHP", "field": "primary", "op": "gt",
                   "threshold": "61.178"}]}
ENTRY = {"date": "2026-08-10", "currency": "PHP",
         "scenario": "BSP 鸽派信号推动宽松预期",
         "trigger": "比索升破 61.178 → 关注比索走弱(T+2)",
         "watch_direction": "up", "claim": CLAIM}
EMPTY = {"status": None, "basis": None}


class AddTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.makedirs(os.path.join(self.tmp.name, "state"))
        self.addCleanup(self.tmp.cleanup)
        self.log_path = os.path.join(self.tmp.name, "state", "decision-log.jsonl")

    def test_add_appends_with_empty_review(self):
        r = run_cmd(["add", "--root", self.tmp.name], json.dumps([ENTRY]))
        self.assertEqual(r.returncode, 0, r.stderr)
        log = read_log(self.tmp.name)
        self.assertEqual(log[0]["currency"], "PHP")
        self.assertEqual(log[0]["review"], EMPTY)

    def test_add_keeps_the_structured_claim(self):
        run_cmd(["add", "--root", self.tmp.name], json.dumps([ENTRY]))
        self.assertEqual(read_log(self.tmp.name)[0]["claim"], CLAIM)

    def test_add_requires_a_claim(self):
        bad = {k: v for k, v in ENTRY.items() if k != "claim"}
        r = run_cmd(["add", "--root", self.tmp.name], json.dumps([bad]))
        self.assertEqual(r.returncode, 2)
        self.assertIn("claim", r.stderr)

    def test_add_rejects_a_threshold_absent_from_the_prose(self):
        """LLM 只准抄:结构化阈值必须逐字出现在散文 trigger 里。"""
        bad = json.loads(json.dumps(ENTRY))
        bad["claim"]["legs"][0]["threshold"] = "61.9"
        r = run_cmd(["add", "--root", self.tmp.name], json.dumps([bad]))
        self.assertEqual(r.returncode, 2)
        self.assertIn("CLAIM_THRESHOLD_NOT_SOURCED", r.stderr)
        self.assertFalse(os.path.exists(self.log_path))

    def test_add_rejects_a_field_outside_the_enum(self):
        bad = json.loads(json.dumps(ENTRY))
        bad["claim"]["legs"][0]["field"] = "close"
        r = run_cmd(["add", "--root", self.tmp.name], json.dumps([bad]))
        self.assertEqual(r.returncode, 2)
        self.assertIn("CLAIM_FIELD_UNKNOWN", r.stderr)

    def test_add_rejects_unstructurable_claim_without_a_reason(self):
        bad = json.loads(json.dumps(ENTRY))
        bad["claim"] = {"horizon": {"kind": "running_days", "n": 2,
                                    "quote": "T+2"}, "legs": None}
        r = run_cmd(["add", "--root", self.tmp.name], json.dumps([bad]))
        self.assertEqual(r.returncode, 2)
        self.assertIn("CLAIM_UNSTRUCTURABLE_REASON_MISSING", r.stderr)

    def test_add_accepts_unstructurable_claim_with_a_reason(self):
        ok = json.loads(json.dumps(ENTRY))
        ok["claim"] = {"horizon": {"kind": "running_days", "n": 2,
                                   "quote": "T+2"}, "legs": None,
                       "unstructurable_reason": "散文未给出阈值"}
        r = run_cmd(["add", "--root", self.tmp.name], json.dumps([ok]))
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_add_rejects_missing_field(self):
        bad = {k: v for k, v in ENTRY.items() if k != "trigger"}
        r = run_cmd(["add", "--root", self.tmp.name], json.dumps([bad]))
        self.assertEqual(r.returncode, 2)

    def test_add_allows_null_watch_direction_for_usd(self):
        usd = dict(ENTRY, currency="USD", watch_direction=None)
        r = run_cmd(["add", "--root", self.tmp.name], json.dumps([usd]))
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_add_rejects_non_dict_item(self):
        r = run_cmd(["add", "--root", self.tmp.name], json.dumps(["scalar"]))
        self.assertEqual(r.returncode, 2)
        self.assertIn("非 dict", r.stderr)
        self.assertFalse(os.path.exists(self.log_path))

    def test_add_rejects_non_list_stdin(self):
        r = run_cmd(["add", "--root", self.tmp.name], json.dumps(ENTRY))
        self.assertEqual(r.returncode, 2)
        self.assertIn("JSON 数组", r.stderr)

    def test_add_rejects_invalid_watch_direction(self):
        bad = dict(ENTRY, watch_direction="sideways")
        r = run_cmd(["add", "--root", self.tmp.name], json.dumps([bad]))
        self.assertEqual(r.returncode, 2)
        self.assertIn("watch_direction", r.stderr)

    def test_add_rejects_int_date(self):
        bad = dict(ENTRY, date=20260810)
        r = run_cmd(["add", "--root", self.tmp.name], json.dumps([bad]))
        self.assertEqual(r.returncode, 2)
        self.assertIn("date", r.stderr)
        self.assertFalse(os.path.exists(self.log_path))

    def test_add_rejects_non_iso_date_string(self):
        bad = dict(ENTRY, date="2026/08/10")
        r = run_cmd(["add", "--root", self.tmp.name], json.dumps([bad]))
        self.assertEqual(r.returncode, 2)
        self.assertIn("date", r.stderr)

    def test_add_rejects_non_str_currency(self):
        bad = dict(ENTRY, currency=123)
        r = run_cmd(["add", "--root", self.tmp.name], json.dumps([bad]))
        self.assertEqual(r.returncode, 2)
        self.assertIn("currency", r.stderr)


class SetReviewIsGoneTest(unittest.TestCase):
    """结论只能由 `claims.resolve_claim` 给出 —— LLM 从此**没有语法**写结论。

    prompt 禁令堵不住(本仓库 13 次同型缺陷的根因),所以入口物理删除。
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.makedirs(os.path.join(self.tmp.name, "state"))
        self.addCleanup(self.tmp.cleanup)

    def test_set_review_subcommand_is_rejected(self):
        run_cmd(["add", "--root", self.tmp.name], json.dumps([ENTRY]))
        r = run_cmd(["set-review", "--root", self.tmp.name,
                     "--date", "2026-08-10", "--currency", "PHP",
                     "--judgement", "j", "--verdict", "命中"])
        self.assertEqual(r.returncode, 2)
        self.assertIn("该子命令已删除", r.stderr)
        self.assertEqual(read_log(self.tmp.name)[0]["review"], EMPTY)

    def test_subcommand_table_is_frozen(self):
        """参数表冻结:读 `parser._actions` 而不是 `--help`,以覆盖
        `argparse.SUPPRESS` 隐藏项。多长出一个能表达结论的入口即红。"""
        self.assertEqual(sorted(log_decision.subcommand_names()),
                         ["add", "amend-trigger", "migrate-review",
                          "set-claim", "stats"])

    def test_no_option_can_express_a_verdict(self):
        for name, options in sorted(log_decision.option_names().items()):
            for opt in options:
                self.assertNotIn("verdict", opt, "%s %s" % (name, opt))
                self.assertNotIn("status", opt, "%s %s" % (name, opt))
                self.assertNotIn("judgement", opt, "%s %s" % (name, opt))

    def test_parser_takes_no_positional_arguments(self):
        for name, options in sorted(log_decision.option_names().items()):
            for opt in options:
                self.assertTrue(opt.startswith("--"), "%s %s" % (name, opt))

    def test_source_never_calls_parse_known_args(self):
        """`parse_known_args` 会静默吞掉未知参数,等于给未来的结论入参留门。"""
        import inspect
        tree = ast.parse(inspect.getsource(log_decision))
        called = {n.func.attr for n in ast.walk(tree)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
        self.assertNotIn("parse_known_args", called)

    def test_no_write_path_assigns_a_status_outside_the_resolver(self):
        """全仓只有 `review.py` 能写 `review.status`,而它的值只来自
        `resolve_claim`。log_decision 这一侧只准写 None。"""
        import inspect
        tree = ast.parse(inspect.getsource(log_decision))
        for node in ast.walk(tree):
            if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant) \
                    and node.slice.value == "status":
                self.assertIsInstance(node.ctx, ast.Load,
                                      "log_decision 不得给 status 赋值")


class MigrateReviewTest(unittest.TestCase):
    """旧的 `trigger_judgement` **不得静默丢弃**:它已逐字发布在
    `reports/daily/2026-08-12.md` 的复盘节里,直接删会让那段发布过的判词
    失去对象 —— 与 `trigger_superseded` 同一条非破坏原则。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.makedirs(os.path.join(self.tmp.name, "state"))
        self.addCleanup(self.tmp.cleanup)
        self.log_path = os.path.join(self.tmp.name, "state", "decision-log.jsonl")

    def _write(self, entries):
        with open(self.log_path, "w", encoding="utf-8") as f:
            for e in entries:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")

    def _legacy(self, **over):
        e = dict(ENTRY)
        e["review"] = {"direction_outcome": "命中",
                       "trigger_judgement": "当时的判词", "verdict": "无法判定"}
        e.update(over)
        return e

    def test_legacy_review_is_moved_not_dropped(self):
        self._write([self._legacy()])
        r = run_cmd(["migrate-review", "--root", self.tmp.name])
        self.assertEqual(r.returncode, 0, r.stderr)
        e = read_log(self.tmp.name)[0]
        self.assertEqual(e["review_superseded"]["trigger_judgement"], "当时的判词")
        self.assertEqual(e["review_superseded"]["verdict"], "无法判定")

    def test_new_review_field_starts_empty(self):
        self._write([self._legacy()])
        run_cmd(["migrate-review", "--root", self.tmp.name])
        self.assertEqual(read_log(self.tmp.name)[0]["review"], EMPTY)

    def test_migration_prints_counts(self):
        self._write([self._legacy(), self._legacy(currency="THB")])
        r = run_cmd(["migrate-review", "--root", self.tmp.name])
        self.assertIn("2", r.stdout)

    def test_migration_is_idempotent_and_keeps_the_first_snapshot(self):
        self._write([self._legacy()])
        run_cmd(["migrate-review", "--root", self.tmp.name])
        run_cmd(["migrate-review", "--root", self.tmp.name])
        e = read_log(self.tmp.name)[0]
        self.assertEqual(e["review_superseded"]["trigger_judgement"], "当时的判词")
        self.assertEqual(e["review"], EMPTY)


class SetClaimTest(unittest.TestCase):
    """既有条目补结构化字段的唯一写入口(SKILL 禁止直接编辑 jsonl)。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.makedirs(os.path.join(self.tmp.name, "state"))
        self.addCleanup(self.tmp.cleanup)
        self.log_path = os.path.join(self.tmp.name, "state", "decision-log.jsonl")
        legacy = {k: v for k, v in ENTRY.items() if k != "claim"}
        legacy["review"] = dict(EMPTY)
        with open(self.log_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(legacy, ensure_ascii=False) + "\n")

    def test_set_claim_backfills(self):
        r = run_cmd(["set-claim", "--root", self.tmp.name,
                     "--date", "2026-08-10", "--currency", "PHP"],
                    json.dumps(CLAIM))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(read_log(self.tmp.name)[0]["claim"], CLAIM)

    def test_set_claim_validates_against_the_prose_trigger(self):
        bad = json.loads(json.dumps(CLAIM))
        bad["legs"][0]["threshold"] = "99.9"
        r = run_cmd(["set-claim", "--root", self.tmp.name,
                     "--date", "2026-08-10", "--currency", "PHP"],
                    json.dumps(bad))
        self.assertEqual(r.returncode, 2)
        self.assertIn("CLAIM_THRESHOLD_NOT_SOURCED", r.stderr)
        self.assertNotIn("claim", read_log(self.tmp.name)[0])

    def test_set_claim_unknown_entry_is_an_error(self):
        r = run_cmd(["set-claim", "--root", self.tmp.name,
                     "--date", "2026-08-10", "--currency", "THB"],
                    json.dumps(CLAIM))
        self.assertEqual(r.returncode, 2)


class StatsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.makedirs(os.path.join(self.tmp.name, "state"))
        self.addCleanup(self.tmp.cleanup)
        self.log_path = os.path.join(self.tmp.name, "state", "decision-log.jsonl")

    def _write_raw(self, lines):
        with open(self.log_path, "w", encoding="utf-8") as f:
            for line in lines:
                f.write(line + "\n")

    def _with_status(self, status, **over):
        e = dict(ENTRY)
        e["review"] = {"status": status, "basis": "b"}
        e.update(over)
        return e

    def test_stats_counts_the_four_buckets_plus_unreviewed(self):
        self._write_raw([json.dumps(self._with_status("命中"), ensure_ascii=False),
                         json.dumps(self._with_status("未到期", currency="THB"),
                                    ensure_ascii=False),
                         json.dumps(dict(ENTRY, currency="BRL",
                                         review=dict(EMPTY)),
                                    ensure_ascii=False)])
        r = run_cmd(["stats", "--root", self.tmp.name,
                     "--from", "2026-08-04", "--to", "2026-08-10"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("命中 1 / 未命中 0 / 无法判定 0 / 未到期 1 / 未复盘 1",
                      r.stdout)

    def test_pending_is_not_folded_into_unreviewed(self):
        """「还没到该看的时候」与「压根没复盘」必须分栏 —— 合栏正是读者
        看不清的老毛病换个地方复发。"""
        self._write_raw([json.dumps(self._with_status("未到期"),
                                    ensure_ascii=False)])
        r = run_cmd(["stats", "--root", self.tmp.name,
                     "--from", "2026-08-04", "--to", "2026-08-10"])
        self.assertIn("未到期 1 / 未复盘 0", r.stdout)

    def test_stats_tolerates_corrupt_lines_and_null_review(self):
        e = dict(ENTRY)
        e["review"] = None
        deep = "[" * 50000 + "]" * 50000
        self._write_raw(["{bad", "[1, 2]", deep,
                         json.dumps(e, ensure_ascii=False)])
        r = run_cmd(["stats", "--root", self.tmp.name,
                     "--from", "2026-08-04", "--to", "2026-08-10"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("未复盘 1", r.stdout)

    def test_stats_counts_unhashable_status_as_unreviewed(self):
        e = dict(ENTRY)
        e["review"] = {"status": [1], "basis": None}
        self._write_raw([json.dumps(e, ensure_ascii=False)])
        r = run_cmd(["stats", "--root", self.tmp.name,
                     "--from", "2026-08-04", "--to", "2026-08-10"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("未复盘 1", r.stdout)

    def test_stats_skips_entries_with_non_str_date(self):
        self._write_raw([json.dumps({"currency": "THB", "review": None},
                                    ensure_ascii=False),
                         json.dumps(dict(ENTRY, date=20260810,
                                         review=dict(EMPTY)),
                                    ensure_ascii=False),
                         json.dumps(dict(ENTRY, review=dict(EMPTY)),
                                    ensure_ascii=False)])
        r = run_cmd(["stats", "--root", self.tmp.name,
                     "--from", "2026-08-04", "--to", "2026-08-10"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("未复盘 1", r.stdout)


class AmendTriggerTest(unittest.TestCase):
    """`amend-trigger`:把**已登记**条目的 trigger 改成速览表那一格的原文。
    表是源、日志是抄件;旧值搬进 `trigger_superseded`,不丢。"""

    def test_amend_replaces_the_trigger(self):
        with tempfile.TemporaryDirectory() as root:
            run_cmd(["add", "--root", root], json.dumps([ENTRY]))
            r = run_cmd(["amend-trigger", "--root", root, "--date", "2026-08-10",
                         "--currency", "PHP", "--trigger", "比索升破 61.178(T+2)"])
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(read_log(root)[0]["trigger"], "比索升破 61.178(T+2)")

    def test_amend_keeps_the_superseded_value(self):
        with tempfile.TemporaryDirectory() as root:
            run_cmd(["add", "--root", root], json.dumps([ENTRY]))
            run_cmd(["amend-trigger", "--root", root, "--date", "2026-08-10",
                     "--currency", "PHP", "--trigger", "比索升破 61.178 的新一版(T+2)"])
            self.assertEqual(read_log(root)[0]["trigger_superseded"],
                             ENTRY["trigger"])

    def test_amend_rejects_a_trigger_that_orphans_the_claim(self):
        """改了散文却让结构化阈值失去出处 —— 那正是「同源同字」要防的事。"""
        with tempfile.TemporaryDirectory() as root:
            run_cmd(["add", "--root", root], json.dumps([ENTRY]))
            r = run_cmd(["amend-trigger", "--root", root, "--date", "2026-08-10",
                         "--currency", "PHP", "--trigger", "比索走弱(T+2)"])
            self.assertEqual(r.returncode, 2)
            self.assertIn("CLAIM_THRESHOLD_NOT_SOURCED", r.stderr)
            self.assertEqual(read_log(root)[0]["trigger"], ENTRY["trigger"])

    def test_unknown_entry_is_an_error_not_a_silent_noop(self):
        with tempfile.TemporaryDirectory() as root:
            run_cmd(["add", "--root", root], json.dumps([ENTRY]))
            r = run_cmd(["amend-trigger", "--root", root, "--date", "2026-08-99",
                         "--currency", "PHP", "--trigger", "比索升破 61.178 新版(T+2)"])
            self.assertEqual(r.returncode, 2)

    def test_amending_twice_keeps_the_original_not_the_intermediate(self):
        with tempfile.TemporaryDirectory() as root:
            run_cmd(["add", "--root", root], json.dumps([ENTRY]))
            for t in ("比索升破 61.178 第二版(T+2)", "比索升破 61.178 第三版(T+2)"):
                run_cmd(["amend-trigger", "--root", root, "--date", "2026-08-10",
                         "--currency", "PHP", "--trigger", t])
            e = read_log(root)[0]
            self.assertEqual(e["trigger"], "比索升破 61.178 第三版(T+2)")
            self.assertEqual(e["trigger_superseded"], ENTRY["trigger"])


if __name__ == "__main__":
    unittest.main()
