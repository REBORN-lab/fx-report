import json
import os
import subprocess
import sys
import tempfile
import unittest

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "scripts", "log_decision.py")


def run_cmd(args, stdin_text=None):
    return subprocess.run([sys.executable, SCRIPT] + args, input=stdin_text,
                          capture_output=True, text=True)


def read_log(root):
    path = os.path.join(root, "state", "decision-log.jsonl")
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


ENTRY = {"date": "2026-08-10", "currency": "PHP",
         "scenario": "BSP 鸽派信号推动宽松预期",
         "trigger": "BSP 官员再释降息信号", "watch_direction": "up"}


class LogDecisionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.makedirs(os.path.join(self.tmp.name, "state"))

    def tearDown(self):
        self.tmp.cleanup()

    def test_add_appends_with_empty_review(self):
        r = run_cmd(["add", "--root", self.tmp.name], json.dumps([ENTRY]))
        self.assertEqual(r.returncode, 0, r.stderr)
        log = read_log(self.tmp.name)
        self.assertEqual(log[0]["currency"], "PHP")
        self.assertEqual(log[0]["review"],
                         {"direction_outcome": None, "trigger_judgement": None, "verdict": None})

    def test_add_rejects_missing_field(self):
        bad = {k: v for k, v in ENTRY.items() if k != "trigger"}
        r = run_cmd(["add", "--root", self.tmp.name], json.dumps([bad]))
        self.assertEqual(r.returncode, 2)

    def test_add_allows_null_watch_direction_for_usd(self):
        usd = dict(ENTRY, currency="USD", watch_direction=None)
        r = run_cmd(["add", "--root", self.tmp.name], json.dumps([usd]))
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_set_review_fills_judgement_and_verdict(self):
        run_cmd(["add", "--root", self.tmp.name], json.dumps([ENTRY]))
        r = run_cmd(["set-review", "--root", self.tmp.name, "--date", "2026-08-10",
                     "--currency", "PHP", "--judgement", "快照事件含 BSP 降息报道",
                     "--verdict", "命中"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(read_log(self.tmp.name)[0]["review"]["verdict"], "命中")

    def test_set_review_unknown_entry_fails(self):
        r = run_cmd(["set-review", "--root", self.tmp.name, "--date", "2026-08-10",
                     "--currency", "THB", "--judgement", "x", "--verdict", "命中"])
        self.assertEqual(r.returncode, 2)

    def test_stats_counts_by_command(self):
        run_cmd(["add", "--root", self.tmp.name],
                json.dumps([ENTRY, dict(ENTRY, currency="THB")]))
        run_cmd(["set-review", "--root", self.tmp.name, "--date", "2026-08-10",
                 "--currency", "PHP", "--judgement", "j", "--verdict", "命中"])
        r = run_cmd(["stats", "--root", self.tmp.name,
                     "--from", "2026-08-04", "--to", "2026-08-10"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("命中 1 / 未命中 0 / 无法判定 0 / 未判定 1", r.stdout)


class LogDecisionTypeGateTest(unittest.TestCase):
    """类型门补充用例(仓库约定 1: 外部数据成员访问前必须过 isinstance 门)。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.makedirs(os.path.join(self.tmp.name, "state"))
        self.log_path = os.path.join(self.tmp.name, "state", "decision-log.jsonl")

    def tearDown(self):
        self.tmp.cleanup()

    def _write_raw(self, lines):
        with open(self.log_path, "w", encoding="utf-8") as f:
            for line in lines:
                f.write(line + "\n")

    def test_add_rejects_non_dict_item(self):
        # 输入校验路径: 数组元素为标量 → 报错优于跳过, rc=2
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

    def test_set_review_skips_corrupt_lines(self):
        # 容错路径: 外部损坏的坏 JSON 行 / 非 dict 行跳过并继续
        entry = dict(ENTRY)
        entry["review"] = {"direction_outcome": None, "trigger_judgement": None,
                           "verdict": None}
        self._write_raw(["{not json", "42",
                         json.dumps(entry, ensure_ascii=False)])
        r = run_cmd(["set-review", "--root", self.tmp.name, "--date", "2026-08-10",
                     "--currency", "PHP", "--judgement", "j", "--verdict", "命中"])
        self.assertEqual(r.returncode, 0, r.stderr)
        log = read_log(self.tmp.name)
        self.assertEqual(len(log), 1)
        self.assertEqual(log[0]["review"]["verdict"], "命中")

    def test_set_review_handles_null_review_field(self):
        # e["review"] 为 None(外部损坏)时不得崩溃, 视为未判定可回填
        entry = dict(ENTRY)
        entry["review"] = None
        self._write_raw([json.dumps(entry, ensure_ascii=False)])
        r = run_cmd(["set-review", "--root", self.tmp.name, "--date", "2026-08-10",
                     "--currency", "PHP", "--judgement", "j", "--verdict", "未命中"])
        self.assertEqual(r.returncode, 0, r.stderr)
        log = read_log(self.tmp.name)
        self.assertEqual(log[0]["review"]["verdict"], "未命中")
        self.assertIsNone(log[0]["review"]["direction_outcome"])

    def test_set_review_rejects_invalid_verdict(self):
        run_cmd(["add", "--root", self.tmp.name], json.dumps([ENTRY]))
        r = run_cmd(["set-review", "--root", self.tmp.name, "--date", "2026-08-10",
                     "--currency", "PHP", "--judgement", "j", "--verdict", "大概命中"])
        self.assertEqual(r.returncode, 2)
        self.assertIn("verdict", r.stderr)

    def test_stats_tolerates_corrupt_lines_and_null_review(self):
        entry = dict(ENTRY)
        entry["review"] = None
        deep = "[" * 50000 + "]" * 50000  # 深嵌套 → json.loads RecursionError
        self._write_raw(["{bad", "[1, 2]", deep,
                         json.dumps(entry, ensure_ascii=False)])
        r = run_cmd(["stats", "--root", self.tmp.name,
                     "--from", "2026-08-04", "--to", "2026-08-10"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("命中 0 / 未命中 0 / 无法判定 0 / 未判定 1", r.stdout)

    def test_stats_counts_unhashable_verdict_as_unjudged(self):
        # 复审反馈1: verdict 为 list(不可哈希)时 stats 不得崩溃, 该条计入"未判定"
        entry = dict(ENTRY)
        entry["review"] = {"direction_outcome": None, "trigger_judgement": None,
                           "verdict": [1]}
        self._write_raw([json.dumps(entry, ensure_ascii=False)])
        r = run_cmd(["stats", "--root", self.tmp.name,
                     "--from", "2026-08-04", "--to", "2026-08-10"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("命中 0 / 未命中 0 / 无法判定 0 / 未判定 1", r.stdout)

    def test_add_rejects_int_date(self):
        # 复审反馈2: date 值须为 str, int 入库会令 set-review 永不匹配 → 报错优于跳过
        bad = dict(ENTRY, date=20260810)
        r = run_cmd(["add", "--root", self.tmp.name], json.dumps([bad]))
        self.assertEqual(r.returncode, 2)
        self.assertIn("date", r.stderr)
        self.assertFalse(os.path.exists(self.log_path))

    def test_add_rejects_non_iso_date_string(self):
        # 复审反馈2: date 须过 datetime.date.fromisoformat 格式门
        bad = dict(ENTRY, date="2026/08/10")
        r = run_cmd(["add", "--root", self.tmp.name], json.dumps([bad]))
        self.assertEqual(r.returncode, 2)
        self.assertIn("date", r.stderr)

    def test_add_rejects_non_str_currency(self):
        # 复审反馈2: currency 值须为 str
        bad = dict(ENTRY, currency=123)
        r = run_cmd(["add", "--root", self.tmp.name], json.dumps([bad]))
        self.assertEqual(r.returncode, 2)
        self.assertIn("currency", r.stderr)

    def test_stats_skips_entries_with_non_str_date(self):
        entry = dict(ENTRY)
        entry["review"] = {"direction_outcome": None, "trigger_judgement": None,
                           "verdict": None}
        no_date = {"currency": "THB", "review": None}
        int_date = dict(entry, date=20260810)
        self._write_raw([json.dumps(no_date, ensure_ascii=False),
                         json.dumps(int_date, ensure_ascii=False),
                         json.dumps(entry, ensure_ascii=False)])
        r = run_cmd(["stats", "--root", self.tmp.name,
                     "--from", "2026-08-04", "--to", "2026-08-10"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("命中 0 / 未命中 0 / 无法判定 0 / 未判定 1", r.stdout)


class AmendTriggerTest(unittest.TestCase):
    """`amend-trigger`:把**已登记**条目的 trigger 改成速览表那一格的原文。

    ---- 为什么需要这条子命令(本轮实测)----
    `skills/fx-daily-report/SKILL.md:387` 写明日志由速览表「条件方向」整理
    而来 —— **表是源、日志是抄件**。改了表没回写时两者漂移,而
    `check_report.py` 新增的 `DECISION_TRIGGER_NOT_SOURCED` 会把它打红。
    实测:2026-08-10 与 2026-08-11 各五条正处在这个状态(共 10 条)。
    修法只能走脚本 —— SKILL 第 386 行写着「经脚本代笔,**禁止直接编辑
    jsonl**」,而既有三个子命令(add / set-review / stats)都改不了 trigger。

    ---- 非破坏:旧值搬到 `trigger_superseded`,不丢 ----
    这些条目的 `review.trigger_judgement` 是**对着旧 trigger 写的**,而且
    已经逐字发布在下游日报里(reports/daily/2026-08-12.md 的复盘节原样引了
    2026-08-11 五条的判词)。直接覆盖会让那段判词失去它评判的对象 ——
    记录对不上了,却没有任何地方说得清为什么。
    所以旧值**留在条目里**:契约(trigger 与速览表同源同字)得到修复,
    审计链(判词当时在评判哪一句)同时保住。
    """

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
                     "--currency", "PHP", "--trigger", "新的一版"])
            self.assertEqual(read_log(root)[0]["trigger_superseded"],
                             ENTRY["trigger"])

    def test_amend_does_not_touch_the_review(self):
        """判词与 verdict 一个字都不改 —— 那是当时做出的判断,不是本次要修的
        契约。改它等于事后重写一条已发布的历史记录。"""
        with tempfile.TemporaryDirectory() as root:
            run_cmd(["add", "--root", root], json.dumps([ENTRY]))
            run_cmd(["set-review", "--root", root, "--date", "2026-08-10",
                     "--currency", "PHP", "--judgement", "当时的判词",
                     "--verdict", "无法判定"])
            run_cmd(["amend-trigger", "--root", root, "--date", "2026-08-10",
                     "--currency", "PHP", "--trigger", "新的一版"])
            rev = read_log(root)[0]["review"]
            self.assertEqual(rev["trigger_judgement"], "当时的判词")
            self.assertEqual(rev["verdict"], "无法判定")

    def test_unknown_entry_is_an_error_not_a_silent_noop(self):
        with tempfile.TemporaryDirectory() as root:
            run_cmd(["add", "--root", root], json.dumps([ENTRY]))
            r = run_cmd(["amend-trigger", "--root", root, "--date", "2026-08-99",
                         "--currency", "PHP", "--trigger", "新的一版"])
            self.assertEqual(r.returncode, 2)

    def test_amending_twice_keeps_the_original_not_the_intermediate(self):
        """再改一次时 `trigger_superseded` 仍是**最初**那一版 —— 它记的是
        "这条判词当时在评判哪一句",不是"上一次改之前是什么"。"""
        with tempfile.TemporaryDirectory() as root:
            run_cmd(["add", "--root", root], json.dumps([ENTRY]))
            for t in ("第二版", "第三版"):
                run_cmd(["amend-trigger", "--root", root, "--date", "2026-08-10",
                         "--currency", "PHP", "--trigger", t])
            e = read_log(root)[0]
            self.assertEqual(e["trigger"], "第三版")
            self.assertEqual(e["trigger_superseded"], ENTRY["trigger"])


if __name__ == "__main__":
    unittest.main()
