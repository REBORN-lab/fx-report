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
        """分母是区间日历天数,不是快照份数:08-09 根本没有快照,那天同样
        没被观测,必须计入未采到(第六轮 C11)。"""
        snaps = WEEK_SNAPS + [snap("2026-08-11", 60.75, "2026-08-10")]   # 无 events 键
        d, _ = wd.build(snaps, [], "2026-W33")
        e = d["events"]["PHP"]
        self.assertEqual(e["articles_sampled"], 22)     # 8+8+6
        self.assertEqual(e["days_with_data"], 3)
        self.assertEqual(e["days"], 5)                  # 08-07..08-11 五个日历日
        self.assertEqual(e["snapshots_loaded"], 4)      # 手上只有四份
        self.assertEqual(e["days_gdelt_failed"], 2)     # 08-09 缺快照 + 08-11 没采到

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
class RawCountCappingTest(unittest.TestCase):
    """采集层落盘前已按标题去重:只看去重后的长度会把"取满上限、其中有重复"
    读成"没取满",漏报截断。"""

    def test_capping_uses_pre_dedupe_count(self):
        s = snap("2026-08-11", 60.75, "2026-08-10", articles=6,
                 meta={"caps": {"gdelt_records": 8}})
        s["events"]["PHP"]["articles_raw_count"] = 8      # 取满 8,去重后剩 6
        e = wd.build([s], [], "2026-W33")[0]["events"]["PHP"]
        self.assertEqual(e["articles_sampled"], 6)
        self.assertEqual(e["articles_capped_days"], 1)

    def test_missing_raw_count_falls_back_to_length(self):
        s = snap("2026-08-11", 60.75, "2026-08-10", articles=8,
                 meta={"caps": {"gdelt_records": 8}})
        e = wd.build([s], [], "2026-W33")[0]["events"]["PHP"]
        self.assertEqual(e["articles_capped_days"], 1)

    def test_bad_raw_count_ignored(self):
        """守卫拆掉就能观察到差异:浮点会被当成有效上限比较,字符串会直接抛。"""
        for bad in (3.0, "3", -1, None, [3]):
            s = snap("2026-08-11", 60.75, "2026-08-10", articles=1,
                     meta={"caps": {"gdelt_records": 3}})
            s["events"]["PHP"]["articles_raw_count"] = bad
            e = wd.build([s], [], "2026-W33")[0]["events"]["PHP"]
            self.assertEqual(e["articles_capped_days"], 0, bad)   # 回退到 len=1
class VerdictInvariantTest(unittest.TestCase):
    """结论由脚本给出。不变量:只有全区间每天都采到、无截断、时间戳全部可解析时,
    才允许说「确实 0 条」;任何一处观测缺口一律退化成「无法判定」。
    前九次同型全部发生在把这个判断交给 LLM 的那一步。"""

    def _v(self, snaps):
        e = wd.build(snaps, [], "2026-W33")[0]["events"]["PHP"]
        return e["official_verdict"], e["articles_verdict"]

    def test_never_collected_is_undecidable(self):
        off, arts = self._v([snap("2026-08-10", 60.75, "2026-08-10")])
        self.assertIn("无法判定", off)
        self.assertIn("无法判定", arts)
        self.assertNotIn("确实", off)

    def test_full_coverage_empty_channel_is_a_real_zero(self):
        """每天都采到、每天都是空 → 这才是"确实没有"。"""
        snaps = [snap(d, 60.75, "2026-08-10", official=0,
                      meta={"caps": {"official_daily": 3}})
                 for d in ("2026-08-10", "2026-08-11")]
        off, _ = self._v(snaps)
        self.assertIn("确实 0 条", off)

    def test_coverage_gap_blocks_the_zero_claim(self):
        """只采到一天 → 即便那天为空,也不准说"确实没有"(第九次同型的路径)。"""
        snaps = [snap("2026-08-10", 60.75, "2026-08-10"),
                 snap("2026-08-11", 60.75, "2026-08-10", official=0,
                      meta={"caps": {"official_daily": 3}})]
        off, _ = self._v(snaps)
        self.assertNotIn("确实", off)
        self.assertIn("1/2 天未采到", off)
        self.assertIn("无法判定", off)

    def test_capping_blocks_the_zero_claim(self):
        """采满上限、且全部发布于区间外 → 被挤掉的更早条目不可知,不准说没有。"""
        snaps = [snap(d, 60.75, "2026-08-10", official=3,
                      published="Wed, 29 Jul 2026 15:00:00 -0400",
                      meta={"caps": {"official_daily": 3}})
                 for d in ("2026-08-10", "2026-08-11")]
        off, _ = self._v(snaps)
        self.assertNotIn("确实", off)
        self.assertIn("顶到当日采集上限", off)   # 措辞含上限值或「上限不唯一」
        self.assertIn("无法判定", off)

    def test_undated_blocks_the_zero_claim(self):
        snaps = [snap(d, 60.75, "2026-08-10", official=1, published="昨天",
                      meta={"caps": {"official_daily": 3}})
                 for d in ("2026-08-10", "2026-08-11")]
        off, _ = self._v(snaps)
        self.assertNotIn("确实", off)
        self.assertIn("时间戳无法解析", off)

    def test_positive_count_is_a_lower_bound_when_gaps_exist(self):
        snaps = [snap("2026-08-10", 60.75, "2026-08-10"),
                 snap("2026-08-11", 60.75, "2026-08-10", official=1,
                      published="Tue, 11 Aug 2026 09:00:00 +0000",
                      meta={"caps": {"official_daily": 3}})]
        off, _ = self._v(snaps)
        self.assertIn("至少 1 条", off)
        self.assertIn("1/2 天未采到", off)


class FallbackDaysTest(unittest.TestCase):
    """兜底是管道属性:当日 GDELT 没采到、而官方通道当日采到了东西。
    与那些公告的发布日无关——发布于 08-07 的公告 08-11 才采到,08-07 当天
    并没有任何兜底发生。"""

    def test_counted_when_official_covers_a_gdelt_outage(self):
        s = snap("2026-08-11", 60.75, "2026-08-10", official=1,
                 published="Tue, 11 Aug 2026 09:00:00 +0000")   # 无 articles
        e = wd.build([s], [], "2026-W33")[0]["events"]["PHP"]
        self.assertEqual(e["fallback_days"], 1)

    def test_publication_on_an_outage_day_is_not_fallback(self):
        """08-07 GDELT 失败、官方也没采到;那天发布的公告 08-11 才到手。"""
        snaps = [snap("2026-08-07", 60.867, "2026-08-07"),
                 snap("2026-08-11", 60.75, "2026-08-10", articles=3,
                      seendate="20260811T000000Z", official=1,
                      published="Fri, 07 Aug 2026 10:00:00 +0200")]
        e = wd.build(snaps, [], "2026-W33")[0]["events"]["PHP"]
        self.assertEqual(e["by_date"]["2026-08-07"]["official_published"], 1)
        self.assertEqual(e["by_date"]["2026-08-07"]["gdelt_collected"], False)
        self.assertEqual(e["fallback_days"], 0)      # 当天并没有兜底

    def test_empty_official_is_not_fallback(self):
        s = snap("2026-08-11", 60.75, "2026-08-10", official=0)
        self.assertEqual(wd.build([s], [], "2026-W33")[0]["events"]["PHP"]
                         ["fallback_days"], 0)


class ByDateNullTest(unittest.TestCase):
    """通道整个没采到时逐日表写 null;写 0 会和"确实没有"混为一谈,
    并与聚合量的 null 自相矛盾。"""

    def test_uncollected_channel_yields_null_per_day(self):
        s = snap("2026-08-11", 60.75, "2026-08-10")
        by = wd.build([s], [], "2026-W33")[0]["events"]["PHP"]["by_date"]
        self.assertIsNone(by["2026-08-11"]["articles_seen"])
        self.assertIsNone(by["2026-08-11"]["official_published"])

    def test_collected_channel_yields_counts(self):
        s = snap("2026-08-11", 60.75, "2026-08-10", articles=2,
                 seendate="20260811T000000Z")
        by = wd.build([s], [], "2026-W33")[0]["events"]["PHP"]["by_date"]
        self.assertEqual(by["2026-08-11"]["articles_seen"], 2)
        self.assertIsNone(by["2026-08-11"]["official_published"])


class SeenDateParsingTest(unittest.TestCase):
    def test_month_and_day_not_swapped(self):
        """月日互换在 20260811 上不可分辨,必须用月≠日的日期锁住。"""
        snaps = [snap("2026-08-07", 60.867, "2026-08-07"),
                 snap("2026-08-11", 60.75, "2026-08-10", articles=1,
                      seendate="20260807T120000Z")]
        e = wd.build(snaps, [], "2026-W33")[0]["events"]["PHP"]
        self.assertEqual(e["articles_in_window"], 1)
        self.assertEqual(e["by_date"]["2026-08-07"]["articles_seen"], 1)
        self.assertEqual(e["by_date"]["2026-08-11"]["articles_seen"], 0)

    def test_impossible_calendar_date_is_undated(self):
        s = snap("2026-08-11", 60.75, "2026-08-10", articles=1,
                 seendate="20260230T120000Z")
        e = wd.build([s], [], "2026-W33")[0]["events"]["PHP"]
        self.assertEqual(e["articles_undated"], 1)


class PublishedAccumulationTest(unittest.TestCase):
    def test_two_announcements_same_day_both_counted(self):
        s = snap("2026-08-11", 60.75, "2026-08-10")
        s["events"]["PHP"] = {"official": [
            {"issuer": "X", "title": "a", "published": "Tue, 11 Aug 2026 09:00:00 +0000"},
            {"issuer": "X", "title": "b", "published": "Tue, 11 Aug 2026 10:00:00 +0000"}]}
        e = wd.build([s], [], "2026-W33")[0]["events"]["PHP"]
        self.assertEqual(e["official_in_window"], 2)
        self.assertEqual(e["by_date"]["2026-08-11"]["official_published"], 2)


class EmptyGdeltDayTest(unittest.TestCase):
    def test_collected_but_zero_articles_is_not_a_failure(self):
        """采到了、确实 0 条 —— 不得计入 days_gdelt_failed。"""
        s = snap("2026-08-11", 60.75, "2026-08-10", articles=0)
        e = wd.build([s], [], "2026-W33")[0]["events"]["PHP"]
        self.assertEqual(e["days_with_data"], 1)
        self.assertEqual(e["days_gdelt_failed"], 0)
        self.assertEqual(e["articles_sampled"], 0)
        self.assertEqual(e["by_date"]["2026-08-11"]["gdelt_collected"], True)


class ArticleIdentityTest(unittest.TestCase):
    def test_url_used_when_title_missing(self):
        s = snap("2026-08-11", 60.75, "2026-08-10")
        s["events"]["PHP"] = {"articles": [
            {"url": "u1", "seendate": "20260811T000000Z"},
            {"url": "u1", "seendate": "20260811T000000Z"},
            {"url": "u2", "seendate": "20260811T000000Z"}]}
        e = wd.build([s], [], "2026-W33")[0]["events"]["PHP"]
        self.assertEqual(e["articles_sampled"], 3)
        self.assertEqual(e["articles_distinct"], 2)


class GdeltCapKeyTest(unittest.TestCase):
    def test_gdelt_reads_its_own_cap_key(self):
        """两个通道的键名串了就会拿 official 的上限判 GDELT。"""
        s = snap("2026-08-11", 60.75, "2026-08-10", articles=3,
                 meta={"caps": {"official_daily": 3, "gdelt_records": 8}})
        e = wd.build([s], [], "2026-W33")[0]["events"]["PHP"]
        self.assertEqual(e["articles_daily_cap"], 8)
        self.assertEqual(e["articles_capped_days"], 0)      # 3 < 8

    def test_official_ignores_raw_count_channel(self):
        """official 落盘不去重,raw_count 恒 None;串上 GDELT 的读数会误判触顶。"""
        s = snap("2026-08-11", 60.75, "2026-08-10", articles=8, official=1,
                 meta={"caps": {"official_daily": 3, "gdelt_records": 8}})
        s["events"]["PHP"]["articles_raw_count"] = 8
        e = wd.build([s], [], "2026-W33")[0]["events"]["PHP"]
        self.assertEqual(e["articles_capped_days"], 1)
        self.assertEqual(e["official_capped_days"], 0)      # 1 < 3
class PubDateParsingTest(unittest.TestCase):
    def test_non_str_published_is_undated(self):
        for bad in (7, ["Tue, 11 Aug 2026 09:00:00 +0000"], {"d": 1}, "", None):
            s = snap("2026-08-11", 60.75, "2026-08-10", official=1, published=bad)
            e = wd.build([s], [], "2026-W33")[0]["events"]["PHP"]
            self.assertEqual(e["official_undated"], 1, bad)

    def test_assorted_malformed_timestamps_do_not_crash(self):
        for bad in ("2026-08-11T09:00:00Z", "Mon, 32 Aug 2026 09:00:00 +0000",
                    "Tue, 11 Aug 99999999 09:00:00 +0000", "11 Aug", "+0000"):
            s = snap("2026-08-11", 60.75, "2026-08-10", official=1, published=bad)
            e = wd.build([s], [], "2026-W33")[0]["events"]["PHP"]
            self.assertEqual(e["official_in_window"], 0, bad)
class VerdictDomainTest(unittest.TestCase):
    """不变量必须陈述在**日历**这个定义域上。分母取"载入到的快照份数"时,
    整天缺采会同时缩小分子分母,missing 恒为 0,脚本于是对一个从未被观测的
    日子说出"全区间采集完整"(第六轮 C11,不变量被攻破的那条路)。"""

    def test_missing_calendar_day_blocks_the_zero_claim(self):
        # 08-07 与 08-11 采到且为空,08-08/09/10 三天根本没有快照
        snaps = [snap(d, 60.75, "2026-08-10", official=0,
                      meta={"caps": {"official_daily": 3}})
                 for d in ("2026-08-07", "2026-08-11")]
        e = wd.build(snaps, [], "2026-W33")[0]["events"]["PHP"]
        self.assertNotIn("确实", e["official_verdict"])
        self.assertIn("3/5 天未采到", e["official_verdict"])
        self.assertIn("无法判定", e["official_verdict"])

    def test_corrupt_snapshots_block_the_zero_claim(self):
        """坏快照的日期不可知,那几天同样没被观测。"""
        good = [snap(d, 60.75, "2026-08-10", official=0,
                     meta={"caps": {"official_daily": 3}})
                for d in ("2026-08-10", "2026-08-11")]
        e = wd.build([None, "junk"] + good, [], "2026-W33")[0]["events"]["PHP"]
        self.assertNotIn("确实", e["official_verdict"])
        self.assertIn("2 份快照损坏被跳过", e["official_verdict"])

    def test_contiguous_full_coverage_still_allows_the_zero_claim(self):
        """连续五天全采到、全为空 —— 这才是唯一允许说"确实 0 条"的形态。"""
        snaps = [snap(d, 60.75, "2026-08-10", official=0,
                      meta={"caps": {"official_daily": 3}})
                 for d in ("2026-08-07", "2026-08-08", "2026-08-09",
                           "2026-08-10", "2026-08-11")]
        e = wd.build(snaps, [], "2026-W33")[0]["events"]["PHP"]
        self.assertIn("确实 0 条", e["official_verdict"])

    def test_no_caveat_means_no_observation_gap(self):
        """总断言:verdict 含「确实」当且仅当三类观测缺口全部为零。
        逐个场景的用例挡不住"再开一条新路径",这条总断言才是不变量本身。"""
        cases = [
            # (snapshots, 是否应当允许"确实")
            ([snap(d, 60.75, "2026-08-10", official=0,
                   meta={"caps": {"official_daily": 3}})
              for d in ("2026-08-10", "2026-08-11")], True),
            ([snap("2026-08-07", 60.867, "2026-08-07", official=0,
                   meta={"caps": {"official_daily": 3}}),
              snap("2026-08-11", 60.75, "2026-08-10", official=0,
                   meta={"caps": {"official_daily": 3}})], False),   # 缺日历天
            ([snap(d, 60.75, "2026-08-10", official=1, published="昨天",
                   meta={"caps": {"official_daily": 3}})
              for d in ("2026-08-10", "2026-08-11")], False),        # undated
            ([snap(d, 60.75, "2026-08-10", official=3,
                   published="Wed, 29 Jul 2026 15:00:00 -0400",
                   meta={"caps": {"official_daily": 3}})
              for d in ("2026-08-10", "2026-08-11")], False),        # 触顶
        ]
        for snaps, allowed in cases:
            e = wd.build(snaps, [], "2026-W33")[0]["events"]["PHP"]
            v = e["official_verdict"]
            gaps = (e["days"] != e["days_official_collected"]
                    or bool(e["official_undated"]) or bool(e["official_capped_days"]))
            self.assertEqual("确实" in v, not gaps, v)
            self.assertEqual("确实" in v, allowed, v)
class FixingsVerdictTest(unittest.TestCase):
    """汇率通道也要有结论句。fixings 是 distinct_fixings 声明过的**下界**
    (定盘日未知时按同值合并,只会低估),周报写"全周仅 N 次定盘"就是把下界
    讲成市场事实(第六轮 C13)。"""

    def test_unknown_ref_dates_make_it_a_lower_bound(self):
        snaps = [snap(d, v, None) for d, v in
                 (("2026-08-10", 60.867), ("2026-08-11", 60.75))]
        r = wd.build(snaps, [], "2026-W33")[0]["rates"]["PHP"]
        self.assertIn("只多不少", r["fixings_verdict"])
        self.assertIn("2 次观测的定盘日未记录", r["fixings_verdict"])
        self.assertNotIn("仅", r["fixings_verdict"])

    def test_all_ref_dates_known_and_full_coverage_is_a_count(self):
        snaps = [snap("2026-08-10", 60.867, "2026-08-10"),
                 snap("2026-08-11", 60.75, "2026-08-11")]
        r = wd.build(snaps, [], "2026-W33")[0]["rates"]["PHP"]
        self.assertEqual(r["fixings_verdict"],
                         "区间内 2 次不同定盘(2026-08-10 至 2026-08-11)")

    def test_missing_calendar_day_is_disclosed(self):
        snaps = [snap("2026-08-07", 60.867, "2026-08-07"),
                 snap("2026-08-11", 60.75, "2026-08-11")]
        r = wd.build(snaps, [], "2026-W33")[0]["rates"]["PHP"]
        self.assertIn("3/5 天未采到", r["fixings_verdict"])
        self.assertIn("只多不少", r["fixings_verdict"])

    def test_corrupt_snapshots_disclosed(self):
        snaps = [None, snap("2026-08-10", 60.867, "2026-08-10"),
                 snap("2026-08-11", 60.75, "2026-08-11")]
        r = wd.build(snaps, [], "2026-W33")[0]["rates"]["PHP"]
        self.assertIn("1 份快照损坏被跳过", r["fixings_verdict"])


class ChannelSourceCappedTest(unittest.TestCase):
    """周度聚合器同样必须认采集层的权威布尔,而不是拿单一 cap_key 去比。"""

    def _snaps(self, entry):
        return [{"date": "2026-08-10", "rates": {}, "gaps": [],
                 "events": {"PHP": entry},
                 "meta": {"caps": {"gdelt_records": 8, "gnews_records": 99}}}]

    def test_capped_days_counts_authoritative_boolean(self):
        got = wd._events_one(self._snaps(
            {"articles": [{"title": "a", "seendate": "20260810T000000Z"}],
             "articles_raw_count": 8, "source_cap": 8, "source_capped": True,
             "channel": "gdelt"}), "PHP", "2026-08-10", "2026-08-10", 0)
        self.assertEqual(got["articles_capped_days"], 1)

    def test_false_boolean_not_counted_even_when_raw_exceeds_gdelt_cap(self):
        got = wd._events_one(self._snaps(
            {"articles": [{"title": "a", "seendate": "20260810T000000Z"}],
             "articles_raw_count": 50, "source_cap": 99, "source_capped": False,
             "channel": "gnews"}), "PHP", "2026-08-10", "2026-08-10", 0)
        self.assertEqual(got["articles_capped_days"], 0)

    def test_mixed_channel_caps_yield_null_daily_cap(self):
        """一周内两条通道各自的上限不同 → 不给单值,不取任一个充数。"""
        snaps = self._snaps({"articles": [{"title": "a", "seendate": "20260810T000000Z"}],
                             "articles_raw_count": 3, "source_cap": 99,
                             "source_capped": False, "channel": "gnews"})
        snaps.append({"date": "2026-08-11", "rates": {}, "gaps": [],
                      "events": {"PHP": {"articles": [{"title": "b",
                                                       "seendate": "20260811T000000Z"}],
                                         "articles_raw_count": 3, "source_cap": 8,
                                         "source_capped": False, "channel": "gdelt"}},
                      "meta": {"caps": {"gdelt_records": 8, "gnews_records": 99}}})
        got = wd._events_one(snaps, "PHP", "2026-08-10", "2026-08-11", 0)
        self.assertIsNone(got["articles_daily_cap"])

    def test_legacy_snapshot_without_boolean_uses_old_path(self):
        got = wd._events_one(self._snaps(
            {"articles": [{"title": "a", "seendate": "20260810T000000Z"}],
             "articles_raw_count": 8}), "PHP", "2026-08-10", "2026-08-10", 0)
        self.assertEqual(got["articles_capped_days"], 1)


class DroppedDayInvariantTest(unittest.TestCase):
    """第三轮审查的 Critical:第二轮的判据 `raw > 0 且 kept == 0` 只在整日归零时
    才响,而真实数据里绝大多数天 kept > 0 —— 整层滤除量因此退出了结论判定。

    不变量改成对**每个两数皆知的日子**成立:滤除条次 = raw - kept。
    这一条同时覆盖窗口层、时间戳层、白名单层,以及日后新增的任何一层,
    且不再要求"当日归零"这个恰好在真实数据里罕见的前提。
    """

    def _snaps(self, gf, days=7):
        return [{"date": "2026-08-%02d" % d, "rates": {}, "gaps": [],
                 "events": {"USD": {"articles": [], "articles_raw_count": 0,
                                    "source_cap": 8, "source_capped": False,
                                    "channel": "gdelt", "gnews_filter": dict(gf)}},
                 "meta": {"caps": {"gdelt_records": 8, "gnews_records": 99}}}
                for d in range(1, days + 1)]

    def _v(self, gf):
        return wd._events_one(self._snaps(gf), "USD",
                              "2026-08-01", "2026-08-07", 0)["articles_verdict"]

    def test_out_window_layer_blocks_zero_claim(self):
        """回填 3 天前:查询带 when:2d,窗口却是那一天 → 100 条全落窗口外、零 gap。

        capped 必须为 False:置 True 会让截断 caveat 先挡住"确实 0 条",
        用例就变成假绿——测的是截断披露,不是本不变量(变异 M27 实测抓到过)。"""
        v = self._v({"raw": 100, "undated": 0, "out_window": 100,
                     "offlist": 0, "kept": 0, "capped": False})
        self.assertNotIn("确实 0 条", v)

    def test_undated_layer_blocks_zero_claim(self):
        """源改了 pubDate 渲染格式 → 100 条全部时间戳不可解析。"""
        v = self._v({"raw": 100, "undated": 100, "out_window": 0,
                     "offlist": 0, "kept": 0, "capped": False})   # 同上,防假绿
        self.assertNotIn("确实 0 条", v)

    def test_offlist_layer_still_blocks_zero_claim(self):
        """capped 必须为 False —— 第三轮审查(F16)实测:带 capped: True 时
        挡住"确实 0 条"的是截断 caveat,把本不变量整段改成 `if False:` 该用例
        照样绿。断言也从 assertNotIn 升级成整句,使它只能被本不变量满足。"""
        v = self._v({"raw": 100, "undated": 0, "out_window": 0,
                     "offlist": 100, "kept": 0, "capped": False})
        self.assertNotIn("确实 0 条", v)
        self.assertIn("7 天抓到共 700 条次但无一可用", v)

    def test_mixed_layers_blocks_zero_claim(self):
        v = self._v({"raw": 99, "undated": 33, "out_window": 33,
                     "offlist": 33, "kept": 0, "capped": False})
        self.assertNotIn("确实 0 条", v)

    def test_genuinely_empty_source_still_allows_zero_claim(self):
        """主通道确实一条都没抓到(raw=0)→ 没有观测缺口,允许下结论。"""
        v = self._v({"raw": 0, "undated": 0, "out_window": 0,
                     "offlist": 0, "kept": 0, "capped": False})
        self.assertIn("确实 0 条", v)

    def test_cumulative_count_is_labelled_as_per_day_sum(self):
        """同一批条目每天数一遍,700 不是 700 条不同的新闻 —— 措辞必须说明是条次。

        断言整句而不是 assertIn("条次"):第三轮审查(F12)实测,把天数与条次数
        两个格式化参数对调后印出「700 天抓到共 7 条次」,510 用例全绿。"""
        v = self._v({"raw": 100, "undated": 0, "out_window": 0,
                     "offlist": 100, "kept": 0, "capped": False})
        self.assertIn("7 天抓到共 700 条次但无一可用", v)

    def test_day_and_item_counts_are_not_interchangeable(self):
        """两个数量级不同的用例:天数饱和成 1、两数对调、逐日累加写成计数,
        三类变异都只能被"天数与条次数各自正确"钉死。"""
        v = wd._events_one(self._snaps(
            {"raw": 50, "undated": 0, "out_window": 0, "offlist": 50,
             "kept": 0, "capped": False}, days=3), "USD",
            "2026-08-01", "2026-08-03", 0)["articles_verdict"]
        self.assertIn("3 天抓到共 150 条次但无一可用", v)

    def test_capped_counted_even_when_nothing_kept(self):
        """截断是「源返回了多少条」的属性,与最终留下几条无关。
        source_capped 的读取此前写在 `if items:` 里,空列表日整块跳过。

        fixture 里不放 gnews_filter.capped —— 第三轮审查(F11)实测:带着它时,
        capped_days 是由主通道那条「或」给出的,把 `if items:` 门装回去用例照样绿。
        条目自己 source_capped: True、上限 99,才是这条判据的靶点。"""
        snaps = [{"date": "2026-08-%02d" % d, "rates": {}, "gaps": [],
                  "events": {"USD": {"articles": [], "articles_raw_count": 99,
                                     "source_cap": 99, "source_capped": True,
                                     "channel": "gnews"}},
                  "meta": {"caps": {"gdelt_records": 8, "gnews_records": 99}}}
                 for d in (1, 2)]
        got = wd._events_one(snaps, "USD", "2026-08-01", "2026-08-02", 0)
        self.assertEqual(got["articles_capped_days"], 2)
        # 零条目日的 source_cap 也必须进 caps 集合,否则上限无从取值
        self.assertEqual(got["articles_daily_cap"], 99)


class PartialFilterDisclosureTest(unittest.TestCase):
    """第三轮 Critical(F7):第二轮把「offlist 无条件累加」换成「raw>0 且 kept==0」
    的不变量,反而丢掉了「部分被滤除」这一层。真实快照 data/2026-08-12.json 的
    BRL(raw=34、offlist=29、kept=5)由「无法判定」翻成「确实 0 条」。
    """

    def _snaps(self, gf, seendates, days=1):
        arts = [{"title": "t%d" % i, "url": "u%d" % i, "seendate": s}
                for i, s in enumerate(seendates)]
        return [{"date": "2026-08-%02d" % d, "rates": {}, "gaps": [],
                 "events": {"BRL": {"articles": list(arts),
                                    "articles_raw_count": len(arts),
                                    "source_cap": 99, "source_capped": False,
                                    "channel": "gnews", "gnews_filter": dict(gf)}},
                 "meta": {"caps": {"gdelt_records": 8, "gnews_records": 99}}}
                for d in range(12, 12 + days)]

    def test_partial_filtering_is_disclosed_even_when_items_kept(self):
        """kept > 0 的日子(真实数据里的绝大多数)滤除量必须仍进结论。"""
        got = wd._events_one(
            self._snaps({"raw": 34, "undated": 0, "out_window": 0,
                         "offlist": 29, "kept": 5, "capped": False},
                        ["20260812T120000Z"] * 5),
            "BRL", "2026-08-12", "2026-08-12", 0)
        self.assertEqual(got["articles_filtered_items"], 29)
        self.assertIn("1 天主通道抓到共 29 条次未通过逐层过滤", got["articles_verdict"])

    def test_kept_items_all_outside_window_is_not_confirmed_zero(self):
        """真实复现:5 条条目发布日全是 08-10/08-11,窗口是 08-12。

        本 fixture 上 filtered(29 条被滤)与窗口两条 caveat 都会响,靠
        assertIn 整句区分是哪一条 —— 只有窗口层能给出的那一路见同类的
        test_pure_gdelt_entry_outside_window(它根本没有 gnews_filter)。"""
        got = wd._events_one(
            self._snaps({"raw": 34, "undated": 0, "out_window": 0,
                         "offlist": 29, "kept": 5, "capped": False},
                        ["20260810T120000Z"] * 2 + ["20260811T120000Z"] * 3),
            "BRL", "2026-08-12", "2026-08-12", 0)
        self.assertEqual((got["articles_in_window"], got["articles_outside_window"]),
                         (0, 5))
        self.assertNotIn("确实 0 条", got["articles_verdict"])
        self.assertIn("另有 5 条发布于区间外", got["articles_verdict"])

    def test_pure_gdelt_entry_outside_window_is_not_confirmed_zero(self):
        """纯 GDELT 条目根本没有 gnews_filter —— 挂在主通道账上的不变量在结构上
        无法生效。判据必须陈述在 _channel 自己的窗口账上,才覆盖得到这一路。"""
        snaps = [{"date": "2026-08-09", "rates": {}, "gaps": [],
                  "events": {"USD": {"articles": [
                      {"title": "t%d" % i, "url": "u%d" % i,
                       "seendate": "20260808T120000Z"} for i in range(7)],
                      "articles_raw_count": 7}},
                  "meta": {"caps": {"gdelt_records": 8}}}]
        got = wd._events_one(snaps, "USD", "2026-08-09", "2026-08-09", 0)
        self.assertEqual(got["articles_capped_days"], 0)   # 7 < 8,截断没挡住它
        self.assertNotIn("确实 0 条", got["articles_verdict"])
        self.assertIn("另有 7 条发布于区间外", got["articles_verdict"])


class MainChannelCapDisclosureTest(unittest.TestCase):
    """第三轮(F2/F9/F13):截断改成「或」后,主通道的截断标记配上了补位通道的
    上限值 —— 结论句印「7 天顶到当日采集上限(8 条)」而当天只采到 3 条。
    两个事实必须各有各的上限。"""

    def _snaps(self, days=7):
        return [{"date": "2026-08-%02d" % d, "rates": {}, "gaps": [],
                 "events": {"USD": {"articles": [
                     {"title": "t%d" % d, "url": "u%d" % d,
                      "seendate": "202608%02dT120000Z" % d}],
                     "articles_raw_count": 3, "source_cap": 8,
                     "source_capped": False, "channel": "gdelt",
                     "gnews_filter": {"raw": 100, "undated": 0, "out_window": 0,
                                      "offlist": 100, "kept": 0, "capped": True}}},
                 "meta": {"caps": {"gdelt_records": 8, "gnews_records": 99}}}
                for d in range(1, days + 1)]

    def test_main_channel_cap_is_its_own_not_the_backfill_cap(self):
        got = wd._events_one(self._snaps(), "USD", "2026-08-01", "2026-08-07", 0)
        # 补位通道每天 3 条、上限 8,谁也没触顶
        self.assertEqual(got["articles_capped_days"], 0)
        self.assertEqual(got["articles_sample_capped_days"], 7)
        self.assertEqual(got["articles_sample_daily_cap"], 99)
        self.assertIn("7 天源返回的原始样本顶到其上限(99 条)", got["articles_verdict"])
        self.assertNotIn("顶到当日采集上限", got["articles_verdict"])
        # 第四轮 S10:两个字段此前零断言,可以互相顶替也可以各自恒 0
        self.assertEqual(got["articles_filtered_days"], 7)
        self.assertEqual(got["articles_filtered_blank_days"], 0)

    def test_pure_gnews_day_counts_one_truncation_not_two(self):
        """第四轮 S2/S4:纯 gnews 日 entry.source_capped 与 gnews_filter.capped
        由**同一个** raw>=99 算出。分别计数会把同一次截断记两遍,结论句把一件事
        说两遍;而 count_at_cap(落盘的 11 条)说明那 11 条并没有撞上限。"""
        snaps = [{"date": "2026-08-%02d" % d, "rates": {}, "gaps": [],
                  "events": {"USD": {
                      "articles": [{"title": "t%d-%d" % (d, i), "url": "u%d-%d" % (d, i),
                                    "seendate": "202608%02dT120000Z" % d}
                                   for i in range(11)],
                      "articles_raw_count": 100, "source_cap": 99,
                      "source_capped": True, "count_at_cap": False, "channel": "gnews",
                      "gnews_filter": {"raw": 100, "undated": 0, "out_window": 0,
                                       "offlist": 89, "kept": 11, "capped": True}}},
                  "meta": {"caps": {"gdelt_records": 8, "gnews_records": 99}}}
                 for d in range(1, 8)]
        got = wd._events_one(snaps, "USD", "2026-08-01", "2026-08-07", 0)
        self.assertEqual(got["articles_capped_days"], 0)         # 11 条没撞 99
        self.assertEqual(got["articles_sample_capped_days"], 7)  # 一次,不是两次
        self.assertEqual(got["articles_sample_daily_cap"], 99)
        self.assertNotIn("顶到当日采集上限", got["articles_verdict"])
        self.assertEqual(got["articles_verdict"].count("顶到其上限"), 1)

    def test_mixed_week_distinguishes_blank_days_from_backfilled(self):
        """第四轮 S7:0 < blank < filtered_days 这一形态此前零覆盖,于是
        `if blank == n_days:` 改成 `if blank > 0:`、`n_days - blank` 改成
        `n_days` 两条变异都存活。"""
        def day(d, n):
            return {"date": "2026-08-%02d" % d, "rates": {}, "gaps": [],
                    "events": {"USD": {
                        "articles": [{"title": "t%d-%d" % (d, i), "url": "u%d-%d" % (d, i),
                                      "seendate": "202608%02dT120000Z" % d}
                                     for i in range(n)],
                        "articles_raw_count": n, "source_cap": 8,
                        "source_capped": False, "count_at_cap": False,
                        "channel": "gdelt" if n else "gnews",
                        "gnews_filter": {"raw": 100, "undated": 0, "out_window": 0,
                                         "offlist": 100, "kept": 0, "capped": False}}},
                    "meta": {"caps": {"gdelt_records": 8, "gnews_records": 99}}}
        snaps = [day(d, 0) for d in range(1, 5)] + [day(d, 1) for d in range(5, 8)]
        got = wd._events_one(snaps, "USD", "2026-08-01", "2026-08-07", 0)
        self.assertEqual(got["articles_filtered_days"], 7)
        self.assertEqual(got["articles_filtered_blank_days"], 4)
        self.assertIn("7 天主通道抓到共 700 条次未通过逐层过滤(其中 3 天当日仍有条目可用)",
                      got["articles_verdict"])
        self.assertNotIn("无一可用", got["articles_verdict"])

    def test_backfilled_day_does_not_claim_nothing_usable(self):
        """当日由补位取得条目,句子不得同时出现「至少 N 条」与「无一可用」。"""
        v = wd._events_one(self._snaps(), "USD", "2026-08-01", "2026-08-07",
                           0)["articles_verdict"]
        self.assertIn("区间内至少", v)
        self.assertNotIn("无一可用", v)
        self.assertIn("其中 7 天当日仍有条目可用", v)


class LegacySnapshotCapParityTest(unittest.TestCase):
    """第三轮(F5):存量快照(GDELT 返回 8 个畸形元素 → articles=[] 而
    raw_count=8)在 derive 与 weekly_digest 两处曾给出相反答案 —— 日报写
    「已达上限,实际篇数只多不少」,同一天的周报写「无截断」。"""

    def test_empty_list_with_raw_count_is_capped_in_both(self):
        from scripts.collect import derive
        entry = {"articles": [], "articles_raw_count": 8}
        snap = {"date": "2026-08-12", "events": {"PHP": entry},
                "meta": {"caps": {"gdelt_records": 8}}}
        stats, _, _ = wd._channel([(snap, [], 8, entry)], "gdelt_records",
                                  wd.GDELT_DAILY_CAP, wd._seen_date,
                                  wd._article_key, "2026-08-12", "2026-08-12")
        self.assertIs(derive._count_capped(snap, "PHP"), True)
        self.assertEqual(stats["capped_days"], 1)

    def test_malformed_elements_are_not_disguised_as_duplicates(self):
        """第四轮 S5:非 dict 条目被 sampled 计入却不进任何窗口账,dup_dropped
        把它们说成"去重掉的重复"(周报 SKILL 让报告直接引这个数),结论照旧
        "确实 0 条"。基线与第三轮同型,属既有漏洞。"""
        snaps = [{"date": "2026-08-%02d" % d, "rates": {}, "gaps": [],
                  "events": {"USD": {"articles": ["junk", "junk", "junk"],
                                     "articles_raw_count": 3}},
                  "meta": {"caps": {"gdelt_records": 8}}} for d in range(1, 8)]
        got = wd._events_one(snaps, "USD", "2026-08-01", "2026-08-07", 0)
        self.assertEqual(got["articles_malformed_items"], 21)
        self.assertEqual(got["articles_dup_dropped"], 0)      # 不是 21
        self.assertNotIn("确实 0 条", got["articles_verdict"])
        self.assertIn("另有 21 条次落盘后结构不可识别", got["articles_verdict"])

    def test_collector_dropped_malformed_blocks_zero_claim(self):
        """第四轮 S1(Critical):源改版成 {"articles": ["<a>", ...]} 时采集层
        逐个跳过,落盘 articles=[] 而 raw_count=3、gaps 为空 —— 与"确实一条都
        没有"完全同形。丢弃量必须一路进结论。"""
        snaps = [{"date": "2026-08-%02d" % d, "rates": {}, "gaps": [],
                  "events": {"USD": {"articles": [], "articles_raw_count": 3,
                                     "source_cap": 8, "source_capped": False,
                                     "count_at_cap": False, "channel": "gdelt",
                                     "articles_dropped_malformed": 3}},
                  "meta": {"caps": {"gdelt_records": 8}}} for d in range(1, 8)]
        got = wd._events_one(snaps, "USD", "2026-08-01", "2026-08-07", 0)
        self.assertEqual(got["articles_malformed_dropped"], 21)
        self.assertNotIn("确实 0 条", got["articles_verdict"])
        self.assertIn("7 天共 21 条次结构不可识别被跳过", got["articles_verdict"])

    def test_sample_cap_assumption_does_not_taint_entry_cap(self):
        """第四轮 S6/S9:主通道上限的推定并进 cap_assumed_days,会给权威的条目级
        上限贴上"上限为推定"的假标注,还让一个"天数"超过它统计的天数。"""
        snaps = [{"date": "2026-08-%02d" % d, "rates": {}, "gaps": [],
                  "events": {"USD": {
                      "articles": [{"title": "t%d" % d, "url": "u%d" % d,
                                    "seendate": "202608%02dT120000Z" % d}],
                      "articles_raw_count": 100, "source_cap": 99,
                      "source_capped": True, "count_at_cap": False, "channel": "gnews",
                      "gnews_filter": {"raw": 100, "undated": 0, "out_window": 0,
                                       "offlist": 99, "kept": 1, "capped": True}}},
                  "meta": {"caps": {"gdelt_records": 8}}}      # 无 gnews_records
                 for d in range(1, 8)]
        got = wd._events_one(snaps, "USD", "2026-08-01", "2026-08-07", 0)
        self.assertEqual(got["articles_cap_assumed_days"], 0)         # 条目级上限是权威的
        self.assertEqual(got["articles_sample_cap_assumed_days"], 7)  # 推定的是主通道那份
        self.assertLessEqual(got["articles_cap_assumed_days"], got["days_with_data"])

    def test_window_caveat_also_shows_when_some_items_are_in_window(self):
        """第四轮 S11:两个覆盖这条 caveat 的用例 in_window 都是 0,于是
        `if outside_window:` 改成 `if outside_window and not in_window:` 存活。
        而真实数据(W33 的 EUR official)走的正是 in_window>0 这一支。"""
        def day(d, seen):
            return {"date": "2026-08-%02d" % d, "rates": {}, "gaps": [],
                    "events": {"USD": {"articles": [
                        {"title": "t%d" % d, "url": "u%d" % d, "seendate": seen}],
                        "articles_raw_count": 1, "source_cap": 8,
                        "source_capped": False, "count_at_cap": False,
                        "channel": "gdelt", "articles_dropped_malformed": 0}},
                    "meta": {"caps": {"gdelt_records": 8}}}
        snaps = [day(1, "20260701T120000Z"), day(2, "20260802T120000Z")]
        got = wd._events_one(snaps, "USD", "2026-08-01", "2026-08-07", 0)
        self.assertEqual((got["articles_in_window"], got["articles_outside_window"]), (1, 1))
        self.assertIn("区间内至少 1 条(", got["articles_verdict"])
        self.assertIn("另有 1 条发布于区间外", got["articles_verdict"])

    def test_official_channel_empty_days_unchanged(self):
        """official 一路(entry=None、raw_count=None)不得因这次放宽而改变:
        空列表日仍不进 caps、不计 cap_assumed_days。"""
        snap = {"date": "2026-08-12", "events": {}, "meta": {"caps": {}}}
        stats, _, _ = wd._channel([(snap, [], None, None)], "official_daily",
                                  wd.OFFICIAL_DAILY_CAP, wd._pub_date,
                                  wd._official_key, "2026-08-12", "2026-08-12")
        self.assertEqual((stats["capped_days"], stats["cap_assumed_days"]), (0, 0))
        self.assertIsNone(stats["daily_cap"])


if __name__ == "__main__":
    unittest.main()
