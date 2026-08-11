"""周度聚合器(delta spec: 聚合器正常产出 / 全周参考价未更新 / 缺天与坏快照)。"""
import unittest

from scripts import weekly_digest as wd


def snap(date, php=None, ref=None, articles=None, gaps=None, official=None,
         published=None, meta=None, seendate=None):
    s = {"date": date, "rates": {}, "events": {}, "gaps": gaps or []}
    if php is not None:
        s["rates"]["PHP"] = {"primary": php, "ref_date": ref}
    if articles is not None:
        s["events"].setdefault("PHP", {})["articles"] = [
            {"title": "t%d" % i, "seendate": seendate} for i in range(articles)]
    if official is not None:
        s["events"].setdefault("PHP", {})["official"] = [
            {"title": "o%d" % i, "issuer": "X", "published": published}
            for i in range(official)]
    if meta is not None:
        s["meta"] = meta
    return s


WEEK_SNAPS = [
    snap("2026-08-07", 60.867, "2026-08-07", articles=8),
    snap("2026-08-08", 60.867, "2026-08-07", articles=8),   # 周末,同一次定盘
    snap("2026-08-10", 60.75, "2026-08-10", articles=6,
         gaps=[{"source": "gdelt", "scope": "BRL", "reason": "429"}]),
]


class RatesTest(unittest.TestCase):
    def test_week_change_uses_first_and_last_distinct_fixing(self):
        d, _ = wd.build(WEEK_SNAPS, [], "2026-W33")
        r = d["rates"]["PHP"]
        self.assertEqual(r["first_ref_date"], "2026-08-07")
        self.assertEqual(r["last_ref_date"], "2026-08-10")
        self.assertEqual(r["fixings"], 2)                 # 周末那份是同一次定盘
        self.assertEqual(r["chg_pct_week"], round((60.75 - 60.867) / 60.867 * 100, 3))

    def test_range_over_distinct_fixings(self):
        d, _ = wd.build(WEEK_SNAPS, [], "2026-W33")
        r = d["rates"]["PHP"]
        self.assertEqual(r["range_low"], 60.75)
        self.assertEqual(r["range_high"], 60.867)

    def test_single_fixing_all_week_yields_null_change(self):
        """全周没有新定盘 → 周涨跌为 null,不得算 0%。"""
        snaps = [snap("2026-08-08", 60.75, "2026-08-07"),
                 snap("2026-08-09", 60.75, "2026-08-07")]
        d, _ = wd.build(snaps, [], "2026-W33")
        r = d["rates"]["PHP"]
        self.assertIsNone(r["chg_pct_week"])
        self.assertEqual(r["fixings"], 1)

    def test_bool_and_nonfinite_rejected(self):
        for bad in (True, "60.7", float("nan"), None):
            snaps = [snap("2026-08-07", bad, "2026-08-07"),
                     snap("2026-08-10", 60.75, "2026-08-10")]
            d, _ = wd.build(snaps, [], "2026-W33")
            self.assertIsNone(d["rates"]["PHP"]["chg_pct_week"], bad)

    def test_missing_ref_dates_fall_back_to_value_dedupe(self):
        """存量快照无 ref_date:同值视为同一次定盘(与 derive 同法)。"""
        snaps = [snap("2026-08-07", 60.867), snap("2026-08-08", 60.867),
                 snap("2026-08-10", 60.75)]
        d, _ = wd.build(snaps, [], "2026-W33")
        self.assertEqual(d["rates"]["PHP"]["fixings"], 2)


class EventsAndGapsTest(unittest.TestCase):
    def test_event_totals_and_failure_days(self):
        snaps = WEEK_SNAPS + [snap("2026-08-11", 60.75, "2026-08-10")]   # 无 events 键
        d, _ = wd.build(snaps, [], "2026-W33")
        e = d["events"]["PHP"]
        self.assertEqual(e["articles_sampled"], 22)     # 8+8+6
        self.assertEqual(e["days_with_data"], 3)
        self.assertEqual(e["days_gdelt_failed"], 1)   # 最后一天没采到

    def test_official_counted_separately_from_articles(self):
        """两个通道口径不同,不得相加;GDELT 挂了但 RSS 成功的那天也要可见。"""
        snaps = [snap("2026-08-10", 60.75, "2026-08-10", articles=6, official=2),
                 snap("2026-08-11", 60.75, "2026-08-10", official=3)]   # GDELT 挂
        d, _ = wd.build(snaps, [], "2026-W33")
        e = d["events"]["PHP"]
        self.assertEqual(e["articles_sampled"], 6)
        self.assertEqual(e["official_sampled"], 5)
        self.assertEqual(e["days_gdelt_failed"], 1)
        self.assertEqual(e["days_with_official"], 2)

    def test_official_null_when_never_collected(self):
        d, _ = wd.build([snap("2026-08-10", 60.75, "2026-08-10", articles=6)],
                        [], "2026-W33")
        self.assertIsNone(d["events"]["PHP"]["official_sampled"])

    def test_gaps_counted_by_source(self):
        d, _ = wd.build(WEEK_SNAPS, [], "2026-W33")
        self.assertEqual(d["gaps_by_source"], {"gdelt": 1})

    def test_no_events_at_all_yields_null_total(self):
        """全周一条都没采到 → null,不是 0(0 会被读成"确实没有新闻")。"""
        d, _ = wd.build([snap("2026-08-10", 60.75, "2026-08-10")], [], "2026-W33")
        self.assertIsNone(d["events"]["PHP"]["articles_sampled"])


class VerdictTest(unittest.TestCase):
    LOG = [
        {"date": "2026-08-07", "currency": "PHP", "review": {"verdict": "命中"}},
        {"date": "2026-08-08", "currency": "PHP", "review": {"verdict": "无法判定"}},
        {"date": "2026-08-09", "currency": "PHP", "review": {"verdict": None}},  # 当天无快照
        {"date": "2026-07-01", "currency": "PHP", "review": {"verdict": "命中"}},  # 窗口外
        "junk",
    ]

    def test_counts_within_window_only(self):
        """按覆盖区间过滤:08-09 当天无快照但有观点,仍须计入(精确匹配会漏掉它)。"""
        d, _ = wd.build(WEEK_SNAPS, self.LOG, "2026-W33")
        self.assertEqual(d["verdicts"], {"命中": 1, "未命中": 0,
                                         "无法判定": 1, "未判定": 1})

    def test_entries_outside_window_excluded(self):
        d, _ = wd.build(WEEK_SNAPS, self.LOG, "2026-W33")
        self.assertEqual(d["verdicts"]["命中"], 1)      # 07-01 那条在窗口外

    def test_empty_log(self):
        d, _ = wd.build(WEEK_SNAPS, [], "2026-W33")
        self.assertEqual(sum(d["verdicts"].values()), 0)


class VerdictAvailabilityTest(unittest.TestCase):
    """日志不可用 ≠ 本周没有观点(delta spec 的 null 约定)。"""

    def test_unavailable_log_yields_null_not_zeros(self):
        d, problems = wd.build(WEEK_SNAPS, None, "2026-W33")
        self.assertIsNone(d["verdicts"])
        self.assertTrue(any("decision log unavailable" in p for p in problems))

    def test_empty_log_yields_zeros(self):
        d, problems = wd.build(WEEK_SNAPS, [], "2026-W33")
        self.assertEqual(sum(d["verdicts"].values()), 0)
        self.assertEqual(problems, [])

    def test_malformed_verdicts_do_not_crash_or_pollute(self):
        log = [{"date": "2026-08-07", "review": {"verdict": ["命中"]}},   # unhashable
               {"date": "2026-08-08", "review": {"verdict": "部分命中"}},  # 表外
               {"date": "2026-08-10", "review": {"verdict": 7}}]
        d, _ = wd.build(WEEK_SNAPS, log, "2026-W33")
        self.assertEqual(sorted(d["verdicts"]), sorted(wd.VERDICTS))
        self.assertEqual(d["verdicts"]["未判定"], 3)


class SnapshotOrderingTest(unittest.TestCase):
    def test_build_sorts_by_date(self):
        """首末取值依赖时间序,不能只靠调用方保证。"""
        snaps = [snap("2026-08-10", 60.75, "2026-08-10"),
                 snap("2026-08-07", 60.867, "2026-08-07")]
        d, _ = wd.build(snaps, [], "2026-W33")
        r = d["rates"]["PHP"]
        self.assertEqual(r["first_ref_date"], "2026-08-07")
        self.assertEqual(r["chg_pct_week"], round((60.75 - 60.867) / 60.867 * 100, 3))


class RobustnessTest(unittest.TestCase):
    def test_bad_snapshots_skipped_and_reported(self):
        d, problems = wd.build(["junk", None, 42] + WEEK_SNAPS, [], "2026-W33")
        self.assertEqual(len(problems), 3)
        self.assertEqual(d["skipped"], 3)          # 可见而非静默
        self.assertIn("PHP", d["rates"])

    def test_no_snapshots_at_all(self):
        d, problems = wd.build([], [], "2026-W33")
        self.assertEqual(d["rates"], {})
        self.assertEqual(d["generated_from"], [])
        self.assertEqual(problems, [])

    def test_generated_from_lists_source_dates(self):
        d, _ = wd.build(WEEK_SNAPS, [], "2026-W33")
        self.assertEqual(d["generated_from"],
                         ["2026-08-07", "2026-08-08", "2026-08-10"])



class CrossGenerationFixingTest(unittest.TestCase):
    """快照 schema 换代:同一次定盘一份有 ref_date、一份没有,不得算两次 ——
    算两次会让"没有新定盘"变成"0.0% 周涨跌"和虚高的定盘次数(管道状态被
    呈现成市场事实,本序列第三次同型缺陷)。"""

    def test_same_fixing_across_schema_generations(self):
        snaps = [snap("2026-08-10", 60.75, None),                 # 存量代
                 snap("2026-08-11", 60.75, "2026-08-10")]         # 新代,同一次定盘
        d, _ = wd.build(snaps, [], "2026-W33")
        r = d["rates"]["PHP"]
        self.assertEqual(r["fixings"], 1)
        self.assertIsNone(r["chg_pct_week"])       # 没有新定盘 → 不是 0.0%

    def test_real_two_fixings_with_equal_price_not_merged(self):
        """两个已知且不同的定盘日恰好同价 → 必须算两次(去重不得按值合并)。"""
        snaps = [snap("2026-08-07", 60.75, "2026-08-07"),
                 snap("2026-08-10", 60.75, "2026-08-10")]
        d, _ = wd.build(snaps, [], "2026-W33")
        r = d["rates"]["PHP"]
        self.assertEqual(r["fixings"], 2)
        self.assertEqual(r["chg_pct_week"], 0.0)   # 真实的两次定盘持平

    def test_mixed_generation_week_counts_actual_fixings(self):
        """本仓库真实形态:三份存量 + 一份新代,实际只有两个价。"""
        snaps = [snap("2026-08-07", 60.867, None), snap("2026-08-08", 60.867, None),
                 snap("2026-08-10", 60.75, None), snap("2026-08-11", 60.75, "2026-08-10")]
        d, _ = wd.build(snaps, [], "2026-W33")
        r = d["rates"]["PHP"]
        self.assertEqual(r["fixings"], 2)
        self.assertEqual(r["chg_pct_week"], round((60.75 - 60.867) / 60.867 * 100, 3))


class GapAccumulationTest(unittest.TestCase):
    """gaps_by_source 的累加语义(真实周报头条引用它,原先零测试覆盖)。"""

    def test_counts_accumulate_across_days_and_sources(self):
        snaps = [
            snap("2026-08-07", 60.8, "2026-08-07", gaps=[
                {"source": "gdelt", "scope": "PHP", "reason": "429"},
                {"source": "gdelt", "scope": "THB", "reason": "429"},
                {"source": "dbnomics", "scope": "X", "reason": "timeout"}]),
            snap("2026-08-10", 60.75, "2026-08-10", gaps=[
                {"source": "gdelt", "scope": "BRL", "reason": "429"}]),
        ]
        d, _ = wd.build(snaps, [], "2026-W33")
        self.assertEqual(d["gaps_by_source"], {"gdelt": 3, "dbnomics": 1})

    def test_malformed_gap_entries_skipped(self):
        snaps = [snap("2026-08-10", 60.75, "2026-08-10",
                      gaps=["junk", {"scope": "no-source"}, {"source": 42},
                            {"source": "gdelt", "scope": "PHP", "reason": "429"}])]
        d, _ = wd.build(snaps, [], "2026-W33")
        self.assertEqual(d["gaps_by_source"], {"gdelt": 1})


class CliTest(unittest.TestCase):
    """SKILL 与 README 教的是直接跑脚本;import 式测试看不见 sys.path 问题。"""

    def test_runs_as_a_script(self):
        import subprocess, sys, tempfile, os, json as _json
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        script = os.path.join(root, "scripts", "weekly_digest.py")
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "data"))
            with open(os.path.join(tmp, "data", "2026-08-10.json"), "w",
                      encoding="utf-8") as f:
                _json.dump(snap("2026-08-10", 60.75, "2026-08-10"), f)
            r = subprocess.run([sys.executable, script, "--week", "2026-W33",
                                "--root", tmp], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("digest:", r.stdout)

    def test_rejects_bad_week_and_days(self):
        import subprocess, sys, os
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        script = os.path.join(root, "scripts", "weekly_digest.py")
        for argv in (["--week", "a/b"], ["--week", "2026-W33", "--days", "0"]):
            r = subprocess.run([sys.executable, script] + argv,
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 2, argv)


class OfficialDisclosureTest(unittest.TestCase):
    """official 是被每日上限截断的样本,数字必须随截断与覆盖天数一起给 ——
    否则"一天采到 3 条(上限)"会被读成"本周共 3 条公告"。"""

    def test_capped_days_and_coverage_reported(self):
        cap = wd.OFFICIAL_DAILY_CAP
        snaps = [snap("2026-08-10", 60.75, "2026-08-10", articles=6),
                 snap("2026-08-11", 60.75, "2026-08-10", official=cap)]
        d, _ = wd.build(snaps, [], "2026-W33")
        e = d["events"]["PHP"]
        self.assertEqual(e["official_sampled"], cap)
        self.assertEqual(e["official_capped_days"], 1)   # 顶到上限 → "至少这么多"
        self.assertEqual(e["days_with_official"], 1)
        self.assertEqual(e["days"], 2)
        self.assertEqual(e["official_daily_cap"], cap)

    def test_uncapped_day_not_marked(self):
        snaps = [snap("2026-08-10", 60.75, "2026-08-10", official=1)]
        d, _ = wd.build(snaps, [], "2026-W33")
        self.assertEqual(d["events"]["PHP"]["official_capped_days"], 0)


class SkippedSemanticsTest(unittest.TestCase):
    """skipped 是"被跳过的坏快照数",不得被日志 problem 污染。"""

    def test_log_unavailable_does_not_inflate_skipped(self):
        d, problems = wd.build(WEEK_SNAPS, None, "2026-W33")
        self.assertEqual(d["skipped"], 0)
        self.assertEqual(len(problems), 1)

    def test_bad_snapshot_and_bad_log_counted_separately(self):
        d, problems = wd.build(["junk"] + WEEK_SNAPS, None, "2026-W33")
        self.assertEqual(d["skipped"], 1)
        self.assertEqual(len(problems), 2)


class UndatedSnapshotTest(unittest.TestCase):
    """无日期的快照排序键退化为空串,会排到所有真实日期之前冒充"周首价"。"""

    def test_undated_snapshot_excluded_and_reported(self):
        bad = {"rates": {"PHP": {"primary": 99.0, "ref_date": "rX"}},
               "events": {}, "gaps": []}
        d, problems = wd.build([bad] + WEEK_SNAPS, [], "2026-W33")
        r = d["rates"]["PHP"]
        self.assertEqual(r["range_high"], 60.867)       # 99.0 不得进区间
        self.assertEqual(r["first_ref_date"], "2026-08-07")
        self.assertEqual(d["skipped"], 1)
        self.assertTrue(any("without str date" in p for p in problems))

    def test_nonstring_date_also_excluded(self):
        bad = {"date": 123, "rates": {"PHP": {"primary": 1.0}}, "events": {}, "gaps": []}
        d, _ = wd.build([bad] + WEEK_SNAPS, [], "2026-W33")
        self.assertEqual(d["rates"]["PHP"]["range_low"], 60.75)


class VerdictDetailTest(unittest.TestCase):
    def test_details_provide_script_source_for_the_breakdown(self):
        log = [{"date": "2026-08-10", "currency": "PHP", "review": {"verdict": "命中"}},
               {"date": "2026-08-07", "currency": "EUR", "review": {"verdict": None}}]
        d, _ = wd.build(WEEK_SNAPS, log, "2026-W33")
        self.assertEqual(d["verdict_details"],
                         [{"date": "2026-08-07", "currency": "EUR", "verdict": "未判定"},
                          {"date": "2026-08-10", "currency": "PHP", "verdict": "命中"}])

    def test_details_null_when_log_unavailable(self):
        d, _ = wd.build(WEEK_SNAPS, None, "2026-W33")
        self.assertIsNone(d["verdict_details"])


class RefUpgradeTest(unittest.TestCase):
    """合并时保留已知定盘日,否则 first/last 全变 null(信息倒退);
    升级同时收敛 same_fixing 的非传递性。"""

    def test_known_ref_survives_merge_with_unknown(self):
        snaps = [snap("2026-08-10", 60.75, None),
                 snap("2026-08-11", 60.75, "2026-08-10")]
        d, _ = wd.build(snaps, [], "2026-W33")
        self.assertEqual(d["rates"]["PHP"]["first_ref_date"], "2026-08-10")

    def test_upgrade_lets_later_distinct_ref_be_recognised(self):
        """A(未知,V) 吸收 B(r1,V) 升级为 r1 后,C(r2,V) 是不同定盘,应算两次。"""
        snaps = [snap("2026-08-07", 60.75, None),
                 snap("2026-08-08", 60.75, "2026-08-07"),
                 snap("2026-08-10", 60.75, "2026-08-10")]
        d, _ = wd.build(snaps, [], "2026-W33")
        self.assertEqual(d["rates"]["PHP"]["fixings"], 2)


class SnapshotFileFilterTest(unittest.TestCase):
    """I3 的文件名/未来日期过滤此前零测试(变异存活):补 CLI 级用例。"""

    def test_cli_ignores_non_snapshot_and_future_files(self):
        import json as _json
        import os
        import subprocess
        import sys
        import tempfile
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        script = os.path.join(root, "scripts", "weekly_digest.py")
        with tempfile.TemporaryDirectory() as tmp:
            data = os.path.join(tmp, "data")
            os.makedirs(data)
            files = {"2026-08-10.json": snap("2026-08-10", 60.75, "2026-08-10"),
                     "zz-scratch-notes.json": snap("2026-08-10", 999.0, "rX"),
                     "9999-01-01.json": snap("9999-01-01", 1.0, "rY"),
                     "2026-08-09.json.bak.json": snap("2026-08-09", 500.0, "rZ")}
            for name, body in files.items():
                with open(os.path.join(data, name), "w", encoding="utf-8") as f:
                    _json.dump(body, f)
            r = subprocess.run([sys.executable, script, "--week", "2026-W33",
                                "--root", tmp], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            with open(os.path.join(tmp, "state", "weekly-digest-2026-W33.json"),
                      encoding="utf-8") as f:
                d = _json.load(f)
        self.assertEqual(d["generated_from"], ["2026-08-10"])
        self.assertEqual(d["rates"]["PHP"]["range_high"], 60.75)   # 999/500/1 全部未进
class OfficialWindowTest(unittest.TestCase):
    """RSS 只给"最新 N 条"、不按发布日过滤:2026-08-11 实测抓到的三条 Fed 公告
    全部发布于 7 月。把 sampled 当"本周公告数"是第五次同型事故。"""

    def test_published_before_window_is_not_this_week(self):
        s = snap("2026-08-11", 60.75, "2026-08-10", official=3,
                 published="Wed, 29 Jul 2026 15:00:00 -0400")
        e = wd.build([s], [], "2026-W33")[0]["events"]["PHP"]
        self.assertEqual(e["official_in_window"], 0)        # 本周该发行方 0 条
        self.assertEqual(e["official_outside_window"], 3)
        self.assertEqual(e["official_sampled"], 3)          # 原始样本仍是 3

    def test_published_inside_window_counted(self):
        snaps = [snap("2026-08-10", 60.75, "2026-08-10"),
                 snap("2026-08-11", 60.75, "2026-08-10", official=1,
                      published="Mon, 10 Aug 2026 09:00:00 +0200")]
        e = wd.build(snaps, [], "2026-W33")[0]["events"]["PHP"]
        self.assertEqual(e["official_in_window"], 1)
        self.assertEqual(e["official_outside_window"], 0)

    def test_same_announcement_collected_daily_counted_once(self):
        """同一条公告连采五日:sampled 按天累加,in_window 必须只算一次。"""
        pub = "Fri, 07 Aug 2026 10:00:00 +0200"
        snaps = [snap(d_, 60.75, "2026-08-07", official=1, published=pub)
                 for d_ in ("2026-08-07", "2026-08-08", "2026-08-09",
                            "2026-08-10", "2026-08-11")]
        e = wd.build(snaps, [], "2026-W33")[0]["events"]["PHP"]
        self.assertEqual(e["official_sampled"], 5)
        self.assertEqual(e["official_in_window"], 1)

    def test_unparseable_published_is_undated_not_in_window(self):
        s = snap("2026-08-11", 60.75, "2026-08-10", official=1, published="昨天")
        e = wd.build([s], [], "2026-W33")[0]["events"]["PHP"]
        self.assertEqual(e["official_undated"], 1)
        self.assertEqual(e["official_in_window"], 0)


class OfficialCollectionSemanticsTest(unittest.TestCase):
    """采到 ≠ 有内容:把"央行本周没发公告"写成"我们没采到"是同型事故的反向。"""

    def test_empty_official_counts_as_collected(self):
        snaps = [snap("2026-08-10", 60.75, "2026-08-10", official=0),
                 snap("2026-08-11", 60.75, "2026-08-10", official=0)]
        e = wd.build(snaps, [], "2026-W33")[0]["events"]["PHP"]
        self.assertEqual(e["days_official_collected"], 2)   # 管道通
        self.assertEqual(e["days_with_official"], 0)        # 央行确实没发
        self.assertEqual(e["official_in_window"], 0)        # 0,不是 null
        self.assertEqual(e["official_sampled"], 0)

    def test_never_collected_yields_null_not_zero(self):
        e = wd.build([snap("2026-08-10", 60.75, "2026-08-10")],
                     [], "2026-W33")[0]["events"]["PHP"]
        self.assertEqual(e["days_official_collected"], 0)
        self.assertIsNone(e["official_in_window"])
        self.assertIsNone(e["official_sampled"])


class CapProvenanceTest(unittest.TestCase):
    """上限随快照落盘;拿当前常量判旧快照会静默错判"是否触顶"。"""

    def test_cap_read_from_snapshot_meta(self):
        s = snap("2026-08-11", 60.75, "2026-08-10", official=2,
                 meta={"caps": {"official_daily": 2, "gdelt_records": 8}})
        e = wd.build([s], [], "2026-W33")[0]["events"]["PHP"]
        self.assertEqual(e["official_daily_cap"], 2)
        self.assertEqual(e["official_capped_days"], 1)
        self.assertEqual(e["official_cap_assumed_days"], 0)

    def test_missing_meta_marks_cap_assumed(self):
        s = snap("2026-08-11", 60.75, "2026-08-10", official=1)
        e = wd.build([s], [], "2026-W33")[0]["events"]["PHP"]
        self.assertEqual(e["official_cap_assumed_days"], 1)
        self.assertEqual(e["official_daily_cap"], wd.OFFICIAL_DAILY_CAP)

    def test_cap_changed_midweek_yields_null_not_a_pick(self):
        snaps = [snap("2026-08-10", 60.75, "2026-08-10", official=1,
                      meta={"caps": {"official_daily": 3}}),
                 snap("2026-08-11", 60.75, "2026-08-10", official=1,
                      meta={"caps": {"official_daily": 5}})]
        e = wd.build(snaps, [], "2026-W33")[0]["events"]["PHP"]
        self.assertIsNone(e["official_daily_cap"])


class ArticlesDisclosureTest(unittest.TestCase):
    """GDELT 与官方通道同等披露:它同样按上限截断,且 48h 查询窗令相邻两日
    重叠约 24h,同一条新闻会被数两遍。"""

    def test_capped_days_reported_for_gdelt(self):
        cap = wd.GDELT_DAILY_CAP
        snaps = [snap("2026-08-10", 60.75, "2026-08-10", articles=cap),
                 snap("2026-08-11", 60.75, "2026-08-10", articles=1)]
        e = wd.build(snaps, [], "2026-W33")[0]["events"]["PHP"]
        self.assertEqual(e["articles_capped_days"], 1)
        self.assertEqual(e["articles_daily_cap"], cap)

    def test_titles_repeated_across_days_deduped(self):
        snaps = [snap("2026-08-10", 60.75, "2026-08-10", articles=3),
                 snap("2026-08-11", 60.75, "2026-08-10", articles=3)]
        e = wd.build(snaps, [], "2026-W33")[0]["events"]["PHP"]
        self.assertEqual(e["articles_sampled"], 6)        # 原始按天累加
        self.assertEqual(e["articles_distinct"], 3)     # 跨日去重后


class ByDateTest(unittest.TestCase):
    """逐日交叉表。official_sampled 是管道读数(当天 RSS 回了几条,含旧公告),
    official_published 才是市场事实(发布日为当天的去重条数)。判"限流日兜底"
    只准用后者 —— 用前者就是把"当天回了三条七月旧公告"读成"当天央行发了三条"。"""

    def test_failed_gdelt_day_marked_not_collected(self):
        snaps = [snap("2026-08-10", 60.75, "2026-08-10", articles=4),
                 snap("2026-08-11", 60.75, "2026-08-10", official=2)]
        by = wd.build(snaps, [], "2026-W33")[0]["events"]["PHP"]["by_date"]
        self.assertEqual(by["2026-08-10"]["gdelt_collected"], True)
        self.assertEqual(by["2026-08-10"]["articles_sampled"], 4)
        self.assertEqual(by["2026-08-10"]["official_collected"], False)
        self.assertIsNone(by["2026-08-10"]["official_sampled"])
        self.assertEqual(by["2026-08-11"]["gdelt_collected"], False)
        self.assertIsNone(by["2026-08-11"]["articles_sampled"])
        self.assertEqual(by["2026-08-11"]["official_collected"], True)

    def test_stale_items_do_not_inflate_official_published(self):
        """当天回了三条上月公告:sampled 是 3,published 必须是 0。"""
        s = snap("2026-08-11", 60.75, "2026-08-10", official=3,
                 published="Wed, 29 Jul 2026 15:00:00 -0400")
        by = wd.build([s], [], "2026-W33")[0]["events"]["PHP"]["by_date"]
        self.assertEqual(by["2026-08-11"]["official_sampled"], 3)
        self.assertEqual(by["2026-08-11"]["official_published"], 0)

    def test_published_attributed_to_publication_day_not_collection_day(self):
        """08-07 发布、08-11 才采到:published 记在 08-07,不是 08-11。"""
        snaps = [snap("2026-08-07", 60.867, "2026-08-07"),
                 snap("2026-08-11", 60.75, "2026-08-10", official=1,
                      published="Fri, 07 Aug 2026 10:00:00 +0200")]
        by = wd.build(snaps, [], "2026-W33")[0]["events"]["PHP"]["by_date"]
        self.assertEqual(by["2026-08-07"]["official_published"], 1)
        self.assertIsNone(by["2026-08-07"]["official_sampled"])
        self.assertEqual(by["2026-08-11"]["official_published"], 0)
        self.assertEqual(by["2026-08-11"]["official_sampled"], 1)


class VerdictDetailGuardTest(unittest.TestCase):
    """明细行的守卫必须与 _verdicts 同规格,否则明细与计数会互相矛盾。"""

    def _run(self, entries):
        d, _ = wd.build(WEEK_SNAPS, entries, "2026-W33")
        return d["verdict_details"], d["verdicts"]

    def test_out_of_vocabulary_verdict_normalised(self):
        det, counts = self._run([{"date": "2026-08-08", "currency": "PHP",
                                  "review": {"verdict": "大致命中"}}])
        self.assertEqual([r["verdict"] for r in det], ["未判定"])
        self.assertEqual(counts["未判定"], 1)

    def test_entry_outside_coverage_window_excluded(self):
        det, counts = self._run([{"date": "2026-07-01", "currency": "PHP",
                                  "review": {"verdict": "命中"}}])
        self.assertEqual(det, [])
        self.assertEqual(sum(counts.values()), 0)   # 明细条数 == 计数之和

    def test_non_str_currency_does_not_crash_sort(self):
        det, _ = self._run([{"date": "2026-08-08", "currency": {"x": 1},
                             "review": {"verdict": "命中"}},
                            {"date": "2026-08-08", "currency": "PHP",
                             "review": {"verdict": "命中"}}])
        self.assertEqual(len(det), 2)
        self.assertIsNone(det[0]["currency"])
class ChannelSymmetryTest(unittest.TestCase):
    """两个通道共用一份实现:GDELT 也按 seendate 过滤窗口、也披露截断,
    否则又会出现"official 有披露、GDELT 没有"的不对称(第三轮 I10)。"""

    def test_articles_outside_window_excluded_from_in_window(self):
        snaps = [snap("2026-08-10", 60.75, "2026-08-10", articles=1,
                      seendate="20260701T120000Z"),
                 snap("2026-08-11", 60.75, "2026-08-10")]
        e = wd.build(snaps, [], "2026-W33")[0]["events"]["PHP"]
        self.assertEqual(e["articles_sampled"], 1)
        self.assertEqual(e["articles_in_window"], 0)
        self.assertEqual(e["articles_outside_window"], 1)

    def test_articles_without_seendate_are_undated(self):
        e = wd.build([snap("2026-08-11", 60.75, "2026-08-10", articles=2)],
                     [], "2026-W33")[0]["events"]["PHP"]
        self.assertEqual(e["articles_undated"], 2)
        self.assertEqual(e["articles_in_window"], 0)

    def test_malformed_seendate_is_undated_not_crash(self):
        for raw in ("", "20260231T120000Z", "2026-08-09", "9999", 7, None):
            e = wd.build([snap("2026-08-11", 60.75, "2026-08-10", articles=1,
                               seendate=raw)], [], "2026-W33")[0]["events"]["PHP"]
            self.assertEqual(e["articles_undated"], 1, raw)

    def test_dup_dropped_given_so_report_never_subtracts(self):
        """LLM 禁算:差值必须由脚本给出,不能让报告自己减。"""
        snaps = [snap("2026-08-10", 60.75, "2026-08-10", articles=3,
                      seendate="20260810T120000Z"),
                 snap("2026-08-11", 60.75, "2026-08-10", articles=3,
                      seendate="20260810T120000Z")]
        e = wd.build(snaps, [], "2026-W33")[0]["events"]["PHP"]
        self.assertEqual(e["articles_sampled"], 6)
        self.assertEqual(e["articles_distinct"], 3)
        self.assertEqual(e["articles_dup_dropped"], 3)

    def test_never_collected_channel_is_null_across_all_counts(self):
        """0 会被读成"确实没有";没采到的通道每一项都必须是 null。"""
        e = wd.build([snap("2026-08-10", 60.75, "2026-08-10")],
                     [], "2026-W33")[0]["events"]["PHP"]
        for k in ("articles_sampled", "articles_distinct", "articles_dup_dropped",
                  "articles_in_window", "articles_outside_window", "articles_undated",
                  "official_sampled", "official_distinct", "official_dup_dropped",
                  "official_in_window", "official_outside_window", "official_undated"):
            self.assertIsNone(e[k], k)


class WindowBoundaryTest(unittest.TestCase):
    """覆盖区间是闭区间;两端各错一天都会把窗内公告判成窗外(或反过来)。"""

    def _one(self, pub):
        snaps = [snap("2026-08-07", 60.867, "2026-08-07"),
                 snap("2026-08-11", 60.75, "2026-08-10", official=1, published=pub)]
        return wd.build(snaps, [], "2026-W33")[0]["events"]["PHP"]

    def test_lower_bound_inclusive(self):
        e = self._one("Fri, 07 Aug 2026 00:30:00 +0000")
        self.assertEqual(e["official_in_window"], 1)

    def test_just_before_lower_bound_excluded(self):
        e = self._one("Thu, 06 Aug 2026 23:30:00 +0000")
        self.assertEqual(e["official_in_window"], 0)
        self.assertEqual(e["official_outside_window"], 1)

    def test_upper_bound_inclusive(self):
        e = self._one("Tue, 11 Aug 2026 23:00:00 +0000")
        self.assertEqual(e["official_in_window"], 1)

    def test_after_upper_bound_excluded(self):
        """回填/时区可以让发布日晚于最后一份快照日。"""
        e = self._one("Wed, 12 Aug 2026 01:00:00 +0000")
        self.assertEqual(e["official_in_window"], 0)
        self.assertEqual(e["official_outside_window"], 1)

    def test_window_bounds_recorded_in_digest(self):
        d, _ = wd.build(WEEK_SNAPS, [], "2026-W33")
        self.assertEqual(d["window_from"], "2026-08-07")
        self.assertEqual(d["window_to"], "2026-08-10")


class OfficialIdentityTest(unittest.TestCase):
    def test_same_item_with_reformatted_timestamp_counted_once(self):
        """身份键不含 pubDate:RSS 改一次时间戳渲染不应让同一条公告变两条。"""
        snaps = [snap("2026-08-10", 60.75, "2026-08-10", official=1,
                      published="Mon, 10 Aug 2026 10:00:00 +0200"),
                 snap("2026-08-11", 60.75, "2026-08-10", official=1,
                      published="Mon, 10 Aug 2026 08:00:00 GMT")]
        e = wd.build(snaps, [], "2026-W33")[0]["events"]["PHP"]
        self.assertEqual(e["official_sampled"], 2)
        self.assertEqual(e["official_distinct"], 1)
        self.assertEqual(e["official_in_window"], 1)


class CapGuardTest(unittest.TestCase):
    """坏的 cap 会伪造"触顶":bool 是 int 的子类,0 会让任何条数都算触顶。"""

    def _capped(self, cap_value):
        s = snap("2026-08-11", 60.75, "2026-08-10", official=1,
                 meta={"caps": {"official_daily": cap_value}})
        return wd.build([s], [], "2026-W33")[0]["events"]["PHP"]

    def test_bool_cap_rejected_and_marked_assumed(self):
        e = self._capped(True)          # True == 1,不排除就会判成触顶
        self.assertEqual(e["official_cap_assumed_days"], 1)
        self.assertEqual(e["official_daily_cap"], wd.OFFICIAL_DAILY_CAP)
        self.assertEqual(e["official_capped_days"], 0)

    def test_non_positive_cap_rejected(self):
        for bad in (0, -1):
            e = self._capped(bad)
            self.assertEqual(e["official_cap_assumed_days"], 1, bad)
            self.assertEqual(e["official_capped_days"], 0, bad)

    def test_articles_cap_assumed_counted_too(self):
        e = wd.build([snap("2026-08-11", 60.75, "2026-08-10", articles=1)],
                     [], "2026-W33")[0]["events"]["PHP"]
        self.assertEqual(e["articles_cap_assumed_days"], 1)
        self.assertEqual(e["articles_daily_cap"], wd.GDELT_DAILY_CAP)


class MalformedEventsTest(unittest.TestCase):
    """外部持久化数据可能损坏:任何形态都不得让 build() 抛异常。"""

    def test_non_dict_items_skipped(self):
        s = snap("2026-08-11", 60.75, "2026-08-10")
        s["events"]["PHP"] = {"articles": ["junk", 7, None, {"title": "ok"}],
                              "official": [{"title": "o"}, "junk"]}
        e = wd.build([s], [], "2026-W33")[0]["events"]["PHP"]
        self.assertEqual(e["articles_sampled"], 4)      # 原始条数照数
        self.assertEqual(e["articles_distinct"], 1)     # 只有 dict 进身份判定
        self.assertEqual(e["official_distinct"], 1)

    def test_unhashable_identity_members_do_not_crash(self):
        s = snap("2026-08-11", 60.75, "2026-08-10")
        s["events"]["PHP"] = {"official": [{"issuer": {"a": 1}, "title": ["x"]},
                                           {"issuer": {"a": 1}, "title": ["x"]}]}
        e = wd.build([s], [], "2026-W33")[0]["events"]["PHP"]
        self.assertEqual(e["official_distinct"], 2)     # 无从判重 → 各算一条

    def test_non_list_channel_treated_as_not_collected(self):
        s = snap("2026-08-11", 60.75, "2026-08-10")
        s["events"]["PHP"] = {"articles": {"n": 1}, "official": "3"}
        e = wd.build([s], [], "2026-W33")[0]["events"]["PHP"]
        self.assertEqual(e["days_with_data"], 0)
        self.assertEqual(e["days_official_collected"], 0)
        self.assertIsNone(e["articles_sampled"])

    def test_bad_meta_shapes_fall_back_to_assumed_cap(self):
        for bad in ([], "x", {"caps": "x"}, {"caps": {"official_daily": "3"}}):
            s = snap("2026-08-11", 60.75, "2026-08-10", official=1, meta=bad)
            e = wd.build([s], [], "2026-W33")[0]["events"]["PHP"]
            self.assertEqual(e["official_cap_assumed_days"], 1, bad)

if __name__ == "__main__":
    unittest.main()
