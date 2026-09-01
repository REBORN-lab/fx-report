"""`scripts/trend.py` 的性质测试。

守的是三件事,每件对应一个真实的失败模式:
1. **确定性** —— 校验端的判据是「报告逐字包含整块」,块本身抖一下,
   那道闸门当场变成噪声(与 tests/test_appendix.py 同一条理由)。
2. **不做跨口径比较** —— 实际利率的分母是 CPI,而本仓 2026-08-11 换过
   CPI 口径;窗口两端相减得到的"上移/下移"里混着口径差,印成趋势就是
   把管道状态叙述成市场事实(SKILL 禁令 5)。
3. **定盘序列按 ref_date 去重** —— 周一那份快照报的是上周五的定盘,
   按快照日排会把同一次定盘数成两次,"连续 N 次"随之虚高。
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts import trend                                          # noqa: E402
from scripts.appendix import num_text                              # noqa: E402
from scripts.weekly_digest import VERDICTS                         # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def snap(date, ref, eur, low=None, high=None, real=None):
    return date, {
        "date": date,
        "rates": {"EUR": {"primary": eur, "ref_date": ref}},
        "derived": {"rates": {"EUR": {"range_5d_low": low,
                                      "range_5d_high": high}},
                    "real_rate": {"US": {"value": real}} if real is not None
                    else {}},
    }


class FixingSeriesTest(unittest.TestCase):
    def test_same_ref_date_across_two_snapshots_counts_once(self):
        """周一那份快照报的仍是上周五的定盘 —— 数成两次会让 run 虚高一档。"""
        snaps = [snap("2026-08-28", "2026-08-27", 0.855),
                 snap("2026-08-29", "2026-08-28", 0.856),
                 snap("2026-09-01", "2026-08-28", 0.856)]
        self.assertEqual(trend.fixing_series(snaps, "EUR"),
                         [("2026-08-27", 0.855), ("2026-08-28", 0.856)])

    def test_later_snapshot_wins_for_the_same_ref_date(self):
        snaps = [snap("2026-08-28", "2026-08-27", 0.855),
                 snap("2026-08-29", "2026-08-27", 0.857)]
        self.assertEqual(trend.fixing_series(snaps, "EUR"),
                         [("2026-08-27", 0.857)])

    def test_missing_or_non_numeric_primary_is_skipped(self):
        snaps = [snap("2026-08-28", "2026-08-27", None),
                 snap("2026-08-29", "2026-08-28", True),
                 snap("2026-09-01", "2026-08-31", 0.86)]
        self.assertEqual(trend.fixing_series(snaps, "EUR"),
                         [("2026-08-31", 0.86)])


class TrailingRunTest(unittest.TestCase):
    def test_run_counts_only_the_trailing_same_direction_moves(self):
        series = [("a", 1.0), ("b", 0.9), ("c", 1.0), ("d", 1.1), ("e", 1.2)]
        self.assertEqual(trend.trailing_run(series), (3, "weak"))

    def test_downward_run(self):
        series = [("a", 1.2), ("b", 1.1), ("c", 1.0)]
        self.assertEqual(trend.trailing_run(series), (2, "strong"))

    def test_a_single_point_has_no_run(self):
        self.assertEqual(trend.trailing_run([("a", 1.0)]), (0, "flat"))

    def test_equal_readings_are_flat_not_a_direction(self):
        self.assertEqual(trend.trailing_run([("a", 1.0), ("b", 1.0)]),
                         (1, "flat"))


class RealRateIsNeverComparedAcrossVintagesTest(unittest.TestCase):
    """本类守的是**不做**某件事,所以断言写成"输出里不出现那种措辞"。

    靶子取自实测:窗口起点(2026-08-07 那批快照)的美国实际利率是换源前的
    口径,与今天的 0.26 之间隔着一次 CPI 口径切换。把两端相减写成"下移"
    就是把口径差印成了行情。
    """

    def test_unchanged_run_counts_trailing_equal_readings(self):
        series = [("d1", 1.0), ("d2", 0.5), ("d3", 0.5), ("d4", 0.5)]
        self.assertEqual(trend._unchanged_run(series), 3)

    def test_the_line_reports_a_run_not_a_move(self):
        snaps = [snap("2026-08-07", "2026-08-06", 0.85, real=1.67),
                 snap("2026-08-11", "2026-08-10", 0.85, real=0.26),
                 snap("2026-09-01", "2026-08-31", 0.86, real=0.26)]
        line = trend._real_rate_line(snaps, "zh")
        self.assertIn("连续 2 份读数未变", line)
        for banned in ("下移", "上移", "1.67"):
            self.assertNotIn(banned, line,
                             "实际利率这一行做了跨口径比较:%s" % line)


class BlockIsDeterministicTest(unittest.TestCase):
    """同一输入两次生成必须逐字节相同,且首行恰是产出方拥有的锚点。"""

    def _snaps(self):
        return [snap("2026-08-28", "2026-08-27", 0.855, 0.85, 0.86, 0.26),
                snap("2026-09-01", "2026-08-31", 0.862, 0.85, 0.862, 0.26)]

    def test_daily_block_is_byte_identical_across_runs(self):
        a = trend.daily_trend(self._snaps(), [], "2026-09-01")
        b = trend.daily_trend(self._snaps(), [], "2026-09-01")
        self.assertEqual(a, b)

    def test_first_line_is_the_anchor(self):
        block = trend.daily_trend(self._snaps(), [], "2026-09-01")
        self.assertEqual(block.splitlines()[0], trend.TREND_ANCHOR)
        en = trend.daily_trend(self._snaps(), [], "2026-09-01", lang="en")
        self.assertEqual(en.splitlines()[0], trend.TREND_ANCHOR_EN)

    def test_numbers_go_through_the_one_formatter(self):
        """0.862 必须印成 `appendix.num_text` 印出来的样子。附录块与趋势块
        印在同一份报告里,同一个数印成两样是读者最先怀疑数据出错的地方。"""
        block = trend.daily_trend(self._snaps(), [], "2026-09-01")
        self.assertIn(num_text(0.862), block)

    def test_verdict_buckets_come_from_the_digest_vocabulary(self):
        """四档 + 未复盘的档名只有一个事实源;手抄一份的话,改名时这里不红,
        而报告会继续印旧档名。"""
        rows = [{"date": "2026-08-29", "review": {"status": "命中"}},
                {"date": "2026-08-29"}]
        counts = trend.verdict_counts(rows)
        self.assertEqual(sorted(counts), sorted(VERDICTS))
        self.assertEqual(counts["命中"], 1)
        self.assertEqual(counts["未复盘"], 1)


class LoadSnapshotsTest(unittest.TestCase):
    def test_corrupt_file_is_skipped_and_reported(self):
        """跳过而不出声,会让"连续 N 次"少算一截 —— 少算与"确实没走那么久"
        在输出上完全同形。"""
        with tempfile.TemporaryDirectory() as t:
            with open(os.path.join(t, "2026-08-28.json"), "w") as f:
                f.write("{ not json")
            with open(os.path.join(t, "2026-08-29.json"), "w") as f:
                json.dump({"date": "2026-08-29"}, f)
            good, skipped = trend.load_snapshots(t)
            self.assertEqual([d for d, _ in good], ["2026-08-29"])
            self.assertEqual(len(skipped), 1)
            self.assertIn("2026-08-28.json", skipped[0])

    def test_upto_excludes_later_dates(self):
        with tempfile.TemporaryDirectory() as t:
            for d in ("2026-08-28", "2026-08-29", "2026-09-01"):
                with open(os.path.join(t, d + ".json"), "w") as f:
                    json.dump({"date": d}, f)
            good, _ = trend.load_snapshots(t, upto="2026-08-29")
            self.assertEqual([d for d, _ in good],
                             ["2026-08-28", "2026-08-29"])


class CliTest(unittest.TestCase):
    def _run(self, *argv):
        return subprocess.run(
            [sys.executable, "scripts/trend.py"] + list(argv), cwd=ROOT,
            capture_output=True, text=True,
            env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))

    def test_daily_without_date_is_rc2(self):
        self.assertEqual(self._run("--mode", "daily").returncode, 2)

    def test_weekly_without_week_is_rc2(self):
        self.assertEqual(self._run("--mode", "weekly").returncode, 2)

    def test_malformed_week_is_rc2(self):
        r = self._run("--mode", "weekly", "--week", "2026-08")
        self.assertEqual(r.returncode, 2, r.stderr)

    def test_daily_stdout_starts_with_the_anchor(self):
        r = self._run("--mode", "daily", "--date", "2026-09-01")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.startswith(trend.TREND_ANCHOR), r.stdout[:80])

    def test_series_mode_emits_parsable_json(self):
        r = self._run("--mode", "series", "--date", "2026-09-01")
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        for key in ("fixings", "real_rate", "runs", "verdict_totals",
                    "weekly", "generated_from"):
            self.assertIn(key, payload)


if __name__ == "__main__":
    unittest.main()
