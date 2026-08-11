import json
import os
import re
import tempfile
import unittest
from datetime import date

from scripts.collect import calendar as calendar_mod
from tests.helpers import make_test_cfg


def write_cal(tmp, cal):
    path = os.path.join(tmp, "calendar-2026.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cal, f, ensure_ascii=False)
    return path


def write_raw(tmp, text):
    """写任意原始文本(损坏 JSON 测试用)。"""
    path = os.path.join(tmp, "calendar-2026.json")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


class CalendarTest(unittest.TestCase):
    def test_yesterday_meeting_hit(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_cal(tmp, {"valid_until": "2099-01-01", "events": [
                {"date": "2026-08-09", "bank": "BCB", "event": "COPOM 议息会议"},
                {"date": "2026-08-10", "bank": "Fed", "event": "FOMC 议息会议"},
                {"date": "2026-09-17", "bank": "BOT", "event": "MPC 议息会议"},
            ]})
            hits, gaps = calendar_mod.collect(make_test_cfg(calendar_path=path))
        self.assertEqual(gaps, [])
        self.assertEqual([(h["date"], h["bank"]) for h in hits],
                         [("2026-08-09", "BCB"), ("2026-08-10", "Fed")])

    def test_no_hits(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_cal(tmp, {"valid_until": "2099-01-01", "events": [
                {"date": "2026-12-09", "bank": "Fed", "event": "FOMC 议息会议"}]})
            hits, gaps = calendar_mod.collect(make_test_cfg(calendar_path=path))
        self.assertEqual((hits, gaps), ([], []))

    def test_expired_calendar_records_gap_but_still_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_cal(tmp, {"valid_until": "2026-01-01", "events": [
                {"date": "2026-08-09", "bank": "BSP", "event": "货币委员会议息"}]})
            hits, gaps = calendar_mod.collect(make_test_cfg(calendar_path=path))
        self.assertEqual(len(hits), 1)
        self.assertEqual(gaps[0]["source"], "calendar")
        self.assertIn("expired", gaps[0]["reason"])

    def test_missing_file_records_gap(self):
        hits, gaps = calendar_mod.collect(make_test_cfg(calendar_path="/nonexistent/c.json"))
        self.assertEqual(hits, [])
        self.assertEqual(gaps[0]["source"], "calendar")

    # ---- 以下为仓库约定补充测试:外部数据(磁盘年历 JSON)类型门 ----

    def test_corrupt_json_records_gap(self):
        """文件存在但内容非法 JSON → gap,绝不上抛(硬契约)。"""
        with tempfile.TemporaryDirectory() as tmp:
            path = write_raw(tmp, "{not valid json!!")
            hits, gaps = calendar_mod.collect(make_test_cfg(calendar_path=path))
        self.assertEqual(hits, [])
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0]["source"], "calendar")

    def test_top_level_not_dict_records_gap(self):
        """JSON 合法但顶层非 dict(list/str/int/null)→ gap + 空命中,不 AttributeError。"""
        for top in ([{"date": "2026-08-09"}], "just a string", 42, None):
            with self.subTest(top=top):
                with tempfile.TemporaryDirectory() as tmp:
                    path = write_cal(tmp, top)
                    hits, gaps = calendar_mod.collect(make_test_cfg(calendar_path=path))
                self.assertEqual(hits, [])
                self.assertEqual(len(gaps), 1)
                self.assertEqual(gaps[0]["source"], "calendar")
                self.assertIn("expected object", gaps[0]["reason"])

    def test_valid_until_missing_or_not_str_gap_but_still_matches(self):
        """valid_until 缺失或非 str(数字)→ 视为缺失记 gap(不 TypeError),命中判定仍执行。"""
        cases = [
            {"events": [{"date": "2026-08-09", "bank": "Fed", "event": "FOMC 议息会议"}]},
            {"valid_until": 20991231,
             "events": [{"date": "2026-08-09", "bank": "Fed", "event": "FOMC 议息会议"}]},
        ]
        for cal in cases:
            with self.subTest(valid_until=cal.get("valid_until")):
                with tempfile.TemporaryDirectory() as tmp:
                    path = write_cal(tmp, cal)
                    hits, gaps = calendar_mod.collect(make_test_cfg(calendar_path=path))
                self.assertEqual(len(hits), 1)
                self.assertEqual(gaps[0]["source"], "calendar")
                self.assertIn("valid_until", gaps[0]["reason"])

    def test_events_not_list_treated_as_empty(self):
        """events 非 list(dict)→ 视为空,不记 gap、不抛异常。"""
        with tempfile.TemporaryDirectory() as tmp:
            path = write_cal(tmp, {"valid_until": "2099-01-01",
                                   "events": {"oops": 1}})
            hits, gaps = calendar_mod.collect(make_test_cfg(calendar_path=path))
        self.assertEqual((hits, gaps), ([], []))

    def test_non_dict_event_elements_skipped(self):
        """events 元素非 dict(标量/None/list)→ 跳过,仅保留合法命中。"""
        with tempfile.TemporaryDirectory() as tmp:
            path = write_cal(tmp, {"valid_until": "2099-01-01", "events": [
                "junk-string", 42, None, ["2026-08-09"],
                {"date": "2026-08-09", "bank": "BCB", "event": "COPOM 议息会议"},
            ]})
            hits, gaps = calendar_mod.collect(make_test_cfg(calendar_path=path))
        self.assertEqual(gaps, [])
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["bank"], "BCB")

    def test_hit_element_missing_bank_or_event_skipped(self):
        """命中日期但缺 bank/event 键(或非 str)→ 跳过,不 KeyError、不记 gap。"""
        with tempfile.TemporaryDirectory() as tmp:
            path = write_cal(tmp, {"valid_until": "2099-01-01", "events": [
                {"date": "2026-08-09", "event": "缺 bank"},
                {"date": "2026-08-09", "bank": "BOT"},
                {"date": "2026-08-09", "bank": 42, "event": "bank 非 str"},
                {"date": "2026-08-10", "bank": "Fed", "event": "FOMC 议息会议"},
            ]})
            hits, gaps = calendar_mod.collect(make_test_cfg(calendar_path=path))
        self.assertEqual(gaps, [])
        self.assertEqual([(h["date"], h["bank"]) for h in hits],
                         [("2026-08-10", "Fed")])

    def test_unhashable_event_date_skipped(self):
        """date 非 str(list,unhashable)→ 跳过,不因 set 成员判断 TypeError。"""
        with tempfile.TemporaryDirectory() as tmp:
            path = write_cal(tmp, {"valid_until": "2099-01-01", "events": [
                {"date": ["2026-08-09"], "bank": "BCB", "event": "COPOM 议息会议"},
                {"date": None, "bank": "BOT", "event": "MPC 议息会议"},
            ]})
            hits, gaps = calendar_mod.collect(make_test_cfg(calendar_path=path))
        self.assertEqual((hits, gaps), ([], []))


if __name__ == "__main__":
    unittest.main()


class ShippedCalendarTest(unittest.TestCase):
    """随仓库分发的 state/calendar-2026.json 的完整性(数据文件也是产物)。"""

    CAL_PATH = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "state", "calendar-2026.json")
    DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

    def setUp(self):
        with open(self.CAL_PATH, encoding="utf-8") as f:
            self.cal = json.load(f)

    def test_every_event_has_wellformed_fields(self):
        for ev in self.cal["events"]:
            self.assertIsInstance(ev.get("date"), str, ev)
            self.assertRegex(ev["date"], self.DATE_RE, ev)
            date.fromisoformat(ev["date"])          # 非法日期(如 02-30)在此爆出
            self.assertIsInstance(ev.get("bank"), str, ev)
            self.assertTrue(ev["bank"].strip(), ev)
            self.assertIsInstance(ev.get("event"), str, ev)
            self.assertTrue(ev["event"].strip(), ev)

    def test_no_duplicate_date_event_pairs(self):
        keys = [(e["date"], e["event"]) for e in self.cal["events"]]
        self.assertEqual(len(keys), len(set(keys)))

    def test_events_within_validity(self):
        valid_until = self.cal["valid_until"]
        for ev in self.cal["events"]:
            self.assertLessEqual(ev["date"], valid_until, ev)

    def test_us_data_releases_present_and_matchable(self):
        """扩充后的统计发布条目必须能被 calendar.collect 命中(通用匹配,不需改代码)。"""
        cpi = [e for e in self.cal["events"] if "CPI 发布" in e["event"]]
        nfp = [e for e in self.cal["events"] if "非农" in e["event"]]
        self.assertGreaterEqual(len(cpi), 12)
        self.assertGreaterEqual(len(nfp), 12)
        hits, gaps = calendar_mod.collect(make_test_cfg(
            calendar_path=self.CAL_PATH, date="2026-08-12", yesterday="2026-08-11"))
        self.assertEqual(gaps, [])
        self.assertTrue(any("CPI 发布" in h["event"] and h["bank"] == "BLS" for h in hits),
                        hits)

    def test_sources_recorded_for_every_issuer(self):
        issuers = {e["bank"] for e in self.cal["events"]}
        documented = {s["bank"] for s in self.cal["sources"]}
        self.assertTrue(issuers <= documented, issuers - documented)

    def test_maintenance_documents_known_gaps(self):
        """未录入的四经济体必须在维护说明里显式记为缺口,不得静默省略。"""
        m = self.cal["maintenance"]
        for token in ("PSA", "IBGE", "403"):
            self.assertIn(token, m)
