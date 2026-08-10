import json
import os
import tempfile
import unittest

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
