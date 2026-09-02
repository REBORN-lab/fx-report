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
import re
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


class TrendPageTest(unittest.TestCase):
    """趋势页(artifact 的源文件)与序列的契约。

    页面之所以要**自包含**(数据内联、外部只有一处字体),是为了让它成为
    "一个文件就能搬走"的东西 —— 换账号发布、换机器打开都不必带数据文件。
    这里守两件会让搬走这件事悄悄失效的性质:内联那段仍是可解析的 JSON,
    以及它的键集与 `series_payload` 一致(页面读了却不存在的键只会在浏览器
    控制台里报错,没有任何测试会红)。
    """

    PAGE = os.path.join(ROOT, "reports", "trend", "fx-trend.html")

    def _page(self):
        with open(self.PAGE, encoding="utf-8") as f:
            return f.read()

    def _embedded(self, html, block_id="series"):
        head = '<script id="%s" type="application/json">' % block_id
        i = html.index(head) + len(head)
        return json.loads(html[i:html.index("</script>", i)])

    def test_both_embedded_blocks_parse(self):
        from scripts import trend_page
        html = self._page()
        for block in trend_page.BLOCKS:
            self._embedded(html, block)

    def test_embedded_keys_match_the_payload(self):
        page_keys = sorted(self._embedded(self._page()))
        payload = trend.series_payload([], [], [])
        self.assertEqual(page_keys, sorted(payload),
                         "页面内联的序列键集与 series_payload 不一致;"
                         "页面读一个不存在的键只会在浏览器控制台报错")

    def test_page_block_carries_what_the_page_reads(self):
        """页面读 page 块的哪些键,这里就钉哪些 —— 蒸馏产物改了字段名而页面
        没跟着改时,浏览器控制台里报错,而没有任何测试会红。"""
        page = self._embedded(self._page(), "page")
        # 2026-09-02:观点复盘节按用户要求下线,review_findings 随之出块 ——
        # 这张清单钉的是「页面读什么」,页面不读的键留在块里只会腐烂。
        for key in ("based_on", "prior", "week", "headline", "dek",
                    "points", "calls", "ahead", "caveat"):
            self.assertIn(key, page, key)
        for row in page["calls"]:
            for key in ("ccy", "watch", "trigger_level", "flip_level",
                        "horizon", "change_kind", "change_gist"):
                self.assertIn(key, row, key)

    def test_every_number_in_the_page_block_is_traceable(self):
        """蒸馏块里的每个数字 token 必须逐字出自它声称的源:蒸馏当期的日报、
        周报或序列 JSON。这是把仓库的 NUMBER_UNTRACEABLE 纪律搬到页面上 ——
        蒸馏是人做的,人会四舍五入、会把 0.85889 记成 0.8589,而那正是
        报告校验器天天在拦的东西。以后每次重新蒸馏,这条都会自动重查。"""
        from scripts import check_report
        page = self._embedded(self._page(), "page")
        sources = []
        for rel in ("reports/daily/%s.md" % page["based_on"],
                    "reports/weekly/%s.md" % page["week"]):
            path = os.path.join(ROOT, rel)
            self.assertTrue(os.path.exists(path), rel)
            with open(path, encoding="utf-8") as f:
                sources.append(f.read())
        sources.append(json.dumps(self._embedded(self._page(), "series"),
                                  ensure_ascii=False))
        allowed = set()
        for text in sources:
            allowed |= check_report.numbers_in(text)
        allowed |= check_report.ALLOWED_SMALL

        def texts(node):
            if isinstance(node, str):
                yield node
            elif isinstance(node, dict):
                for v in node.values():
                    yield from texts(v)
            elif isinstance(node, list):
                for v in node:
                    yield from texts(v)

        bad = sorted(set().union(*(check_report.numbers_in(t)
                                   for t in texts(page))) - allowed)
        self.assertEqual(bad, [],
                         "页面蒸馏块里有 %d 个数字不见于其声称的源:%s"
                         % (len(bad), bad))

    def test_rebuild_is_byte_stable(self):
        """同一份数据重嵌一次必须逐字节不变 —— 否则每次刷新都在 git 上
        制造噪声,"页面真的变了吗"就再也看不出来。"""
        from scripts import trend_page
        html = self._page()
        for block in trend_page.BLOCKS:
            html2 = trend_page.rebuild(html, block, self._embedded(html, block))
            self.assertEqual(html2, html, block)

    def test_rebuild_refuses_to_inline_a_closing_script_tag(self):
        from scripts import trend_page
        with self.assertRaises(ValueError):
            trend_page.rebuild(self._page(), "series", {"x": "</script>"})

    def test_rebuild_rejects_an_unknown_block(self):
        from scripts import trend_page
        with self.assertRaises(ValueError):
            trend_page.rebuild(self._page(), "nope", {})

    def test_the_page_is_self_contained_except_the_font_link(self):
        """外部引用只许有 Google Fonts 那一条。多一条外链,搬到别处就会
        遇到 CSP 拦截或静默回落,而两者在页面上都看不出来。"""
        html = self._page()
        for url in re.findall(r'(?:src|href)="(https?://[^"]+)"', html):
            self.assertTrue(url.startswith("https://fonts.googleapis.com/"),
                            "页面引了一个外部资源:%s" % url)
