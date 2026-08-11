import json
import os
import subprocess
import sys
import tempfile
import unittest

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
