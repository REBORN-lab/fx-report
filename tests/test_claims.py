"""结构化观点(`claim`)的校验与判定。

这一层存在的理由是实测:2026-08-14 的决策日志 40 条里 33 条 verdict 是
「无法判定」,而它们绝大多数的诚实答案是「未到期」—— 一条写着 T+3 的观点
在**第二天**就被拿去判,判据还只是两次定盘的高低。两档在旧实现里是同一个
值,把"我们还没到该看的时候"伪装成了"我们看了但看不出来"。
"""
import unittest

from scripts import claims


def leg(**over):
    base = {"currency": "EUR", "field": "primary", "op": "gt",
            "threshold": "0.86693"}
    base.update(over)
    return base


def claim(**over):
    base = {"horizon": {"kind": "running_days", "n": 3, "quote": "T+3"},
            "legs": [leg()]}
    base.update(over)
    return base


def entry(**over):
    base = {"date": "2026-08-10", "currency": "EUR", "scenario": "s",
            "trigger": "T+3 内 USD/EUR 升破前一运行日读数 0.86693",
            "watch_direction": "up", "claim": claim()}
    base.update(over)
    return base


def eur_snap(primary, ref_date):
    return {"rates": {"EUR": {"primary": primary, "ref_date": ref_date}}}


class ValidateClaimTest(unittest.TestCase):
    """`validate_claim` 是 add 入口与校验器共用的一份判据。"""

    def test_wellformed_claim_has_no_problem(self):
        self.assertEqual(claims.validate_claim(claim(), entry()["trigger"]), [])

    def test_threshold_must_appear_verbatim_in_the_prose_trigger(self):
        """LLM 只准抄,不准算:阈值对不上散文就红。"""
        bad = claim(legs=[leg(threshold="0.86694")])
        problems = claims.validate_claim(bad, entry()["trigger"])
        self.assertTrue(any("THRESHOLD_NOT_SOURCED" in p for p in problems),
                        problems)

    def test_truncated_threshold_does_not_pass_as_a_substring(self):
        """`0.8669` 是散文里 `0.86693` 的前缀 —— 纯子串判据会放它过去,
        而判定用的是被截短的那个数,散文与判定从此各说各话。"""
        bad = claim(legs=[leg(threshold="0.8669")])
        problems = claims.validate_claim(bad, entry()["trigger"])
        self.assertTrue(any("THRESHOLD_NOT_SOURCED" in p for p in problems),
                        problems)

    def test_threshold_next_to_punctuation_is_still_sourced(self):
        ok = claim(horizon={"kind": "open", "quote": None},
                   legs=[leg(threshold="0.867")])
        self.assertEqual(
            claims.validate_claim(ok, "欧元参考价升破 5 运行日区间上沿 0.867"), [])

    def test_horizon_quote_must_appear_verbatim_in_the_prose_trigger(self):
        bad = claim(horizon={"kind": "running_days", "n": 3, "quote": "T+9"})
        problems = claims.validate_claim(bad, entry()["trigger"])
        self.assertTrue(any("HORIZON_NOT_SOURCED" in p for p in problems),
                        problems)

    def test_field_must_come_from_the_fixed_enum(self):
        problems = claims.validate_claim(claim(legs=[leg(field="close")]),
                                         entry()["trigger"])
        self.assertTrue(any("FIELD" in p for p in problems), problems)

    def test_op_must_come_from_the_fixed_enum(self):
        problems = claims.validate_claim(claim(legs=[leg(op="≈")]),
                                         entry()["trigger"])
        self.assertTrue(any("OP" in p for p in problems), problems)

    def test_unstructurable_claim_must_state_a_reason(self):
        bad = {"horizon": {"kind": "running_days", "n": 2, "quote": "T+2"},
               "legs": None}
        problems = claims.validate_claim(bad, "四盘在 T+2 内再次同侧移动")
        self.assertTrue(any("UNSTRUCTURABLE_REASON" in p for p in problems),
                        problems)

    def test_unstructurable_claim_with_reason_is_accepted(self):
        ok = {"horizon": {"kind": "running_days", "n": 2, "quote": "T+2"},
              "legs": None,
              "unstructurable_reason": "触发条件写「再次同侧移动」,未给出阈值"}
        self.assertEqual(claims.validate_claim(ok, "四盘在 T+2 内再次同侧移动"), [])

    def test_running_day_count_must_match_the_quoted_t_plus_n(self):
        """`quote` 写 T+3 而 `n` 填 9 —— 散文说三个运行日、判定按九个算。
        变异验证实跑出来的:这样一条当前能过校验,而它把时限凭空延长了。"""
        bad = claim(horizon={"kind": "running_days", "n": 9, "quote": "T+3"})
        problems = claims.validate_claim(bad, entry()["trigger"])
        self.assertTrue(any("CLAIM_HORIZON_N_MISMATCH" in p for p in problems),
                        problems)

    def test_matching_t_plus_n_is_accepted(self):
        ok = claim(horizon={"kind": "running_days", "n": 3, "quote": "T+3"})
        self.assertEqual(claims.validate_claim(ok, entry()["trigger"]), [])

    def test_quote_without_a_t_plus_n_is_left_to_the_author(self):
        """「在下一次定盘」这类措辞没有可比的数字 —— 不强判,由 n 自己表达。"""
        ok = claim(horizon={"kind": "running_days", "n": 1,
                            "quote": "在下一次定盘"})
        self.assertEqual(
            claims.validate_claim(ok, "欧元参考价在下一次定盘升破 0.86693"), [])

    def test_open_horizon_must_not_carry_a_quote(self):
        bad = claim(horizon={"kind": "open", "quote": "T+3"})
        problems = claims.validate_claim(bad, entry()["trigger"])
        self.assertTrue(any("HORIZON" in p for p in problems), problems)

    def test_absolute_date_horizon_is_accepted(self):
        ok = claim(horizon={"kind": "date", "on": "2026-09-11",
                            "quote": "时限:2026-09-11"})
        self.assertEqual(
            claims.validate_claim(ok, "欧元升破 0.86693(时限:2026-09-11)"), [])


class ResolveNotDueTest(unittest.TestCase):
    """本轮的主要收益:时限没到就说没到,不冒充「无法判定」。"""

    def test_one_running_day_into_a_three_day_horizon_is_not_due(self):
        r = claims.resolve_claim(entry(), [
            ("2026-08-10", eur_snap(0.86693, "2026-08-10")),
            ("2026-08-11", eur_snap(0.86600, "2026-08-11")),
        ])
        self.assertEqual(r.status, "未到期")

    def test_not_due_sentence_says_how_far_the_window_has_run(self):
        r = claims.resolve_claim(entry(), [
            ("2026-08-10", eur_snap(0.86693, "2026-08-10")),
            ("2026-08-11", eur_snap(0.86600, "2026-08-11")),
        ])
        self.assertIn("未到期", r.sentence)
        self.assertIn("T+3", r.sentence)

    def test_open_horizon_never_falls_due(self):
        e = entry(trigger="欧元参考价升破 5 运行日区间上沿 0.867",
                  claim={"horizon": {"kind": "open", "quote": None},
                         "legs": [leg(threshold="0.867")]})
        r = claims.resolve_claim(e, [
            ("2026-08-10", eur_snap(0.86000, "2026-08-10")),
            ("2026-08-11", eur_snap(0.86100, "2026-08-11")),
            ("2026-08-12", eur_snap(0.86200, "2026-08-12")),
            ("2026-08-13", eur_snap(0.86300, "2026-08-13")),
        ])
        self.assertEqual(r.status, "未到期")


class ResolveHitMissTest(unittest.TestCase):
    def test_threshold_crossed_inside_the_window_is_a_hit(self):
        r = claims.resolve_claim(entry(), [
            ("2026-08-10", eur_snap(0.86693, "2026-08-10")),
            ("2026-08-11", eur_snap(0.86800, "2026-08-11")),
        ])
        self.assertEqual(r.status, "命中")

    def test_hit_sentence_names_the_reading_that_crossed(self):
        r = claims.resolve_claim(entry(), [
            ("2026-08-10", eur_snap(0.86693, "2026-08-10")),
            ("2026-08-11", eur_snap(0.86800, "2026-08-11")),
        ])
        self.assertIn("0.868", r.sentence)
        self.assertIn("0.86693", r.sentence)

    def test_full_window_without_crossing_is_a_miss(self):
        r = claims.resolve_claim(entry(), [
            ("2026-08-10", eur_snap(0.86693, "2026-08-10")),
            ("2026-08-11", eur_snap(0.86600, "2026-08-11")),
            ("2026-08-12", eur_snap(0.86500, "2026-08-12")),
            ("2026-08-13", eur_snap(0.86400, "2026-08-13")),
        ])
        self.assertEqual(r.status, "未命中")

    def test_readings_after_the_window_closes_do_not_count(self):
        """T+3 的窗口只看前三个运行日 —— 第四天才升破不算命中。"""
        r = claims.resolve_claim(entry(), [
            ("2026-08-10", eur_snap(0.86693, "2026-08-10")),
            ("2026-08-11", eur_snap(0.86600, "2026-08-11")),
            ("2026-08-12", eur_snap(0.86500, "2026-08-12")),
            ("2026-08-13", eur_snap(0.86400, "2026-08-13")),
            ("2026-08-14", eur_snap(0.87000, "2026-08-14")),
        ])
        self.assertEqual(r.status, "未命中")


class SentenceStatesTheObservedRelationTest(unittest.TestCase):
    """依据句里的比较词必须是**实际观测到的关系**,不是观点声称的那个。

    实测出来的缺陷:时限改成 T+1 后这条观点判「未命中」,而依据句写的是
    「EUR 参考价 0.86655 高于 0.86693」—— 0.86655 并不高于 0.86693。措辞取自
    `op` 的标签,与是否成立无关,于是结论与依据当场打架。这一句要被逐字抄进
    正文,读者只会看到那半句假话。
    """

    def _one_day(self, primary, n=1):
        e = entry()
        e["claim"]["horizon"]["n"] = n
        return claims.resolve_claim(e, [
            ("2026-08-10", eur_snap(0.86693, "2026-08-10")),
            ("2026-08-11", eur_snap(primary, "2026-08-11")),
        ])

    def test_miss_sentence_does_not_claim_the_threshold_was_crossed(self):
        r = self._one_day(0.86655)
        self.assertEqual(r.status, "未命中")
        self.assertNotIn("0.86655 高于", r.sentence)

    def test_miss_sentence_states_the_relation_that_actually_held(self):
        r = self._one_day(0.86655)
        self.assertIn("0.86655 未高于 0.86693", r.sentence)

    def test_hit_sentence_still_states_the_positive_relation(self):
        r = self._one_day(0.86800)
        self.assertEqual(r.status, "命中")
        self.assertIn("0.868 高于 0.86693", r.sentence)

    def test_every_op_has_a_negated_label(self):
        for op in claims.OPS:
            self.assertIn(op, claims.OP_SPECS)
            held, not_held = claims.op_labels(op)
            self.assertTrue(held and not_held and held != not_held, op)


class ResolveUndecidableTest(unittest.TestCase):
    """第四档必须说清缺的是哪一次观测,不得只给结论。"""

    def test_window_elapsed_without_new_fixings_is_undecidable(self):
        r = claims.resolve_claim(entry(), [
            ("2026-08-10", eur_snap(0.86693, "2026-08-10")),
            ("2026-08-11", eur_snap(0.86693, "2026-08-10")),
            ("2026-08-12", eur_snap(0.86693, "2026-08-10")),
            ("2026-08-13", eur_snap(0.86693, "2026-08-10")),
        ])
        self.assertEqual(r.status, "无法判定")

    def test_undecidable_sentence_counts_the_missing_observations(self):
        r = claims.resolve_claim(entry(), [
            ("2026-08-10", eur_snap(0.86693, "2026-08-10")),
            ("2026-08-11", eur_snap(0.86600, "2026-08-11")),
            ("2026-08-12", eur_snap(0.86600, "2026-08-11")),
            ("2026-08-13", eur_snap(0.86600, "2026-08-11")),
        ])
        self.assertEqual(r.status, "无法判定")
        self.assertIn("窗口 3 个运行日只取到 1 次新定盘", r.sentence)
        self.assertIn("2026-08-11", r.sentence)

    def test_unstructurable_claim_is_undecidable_not_pending(self):
        e = entry(trigger="四盘在 T+2 内再次同侧移动",
                  claim={"horizon": {"kind": "running_days", "n": 2,
                                     "quote": "T+2"},
                         "legs": None,
                         "unstructurable_reason": "未给出阈值"})
        r = claims.resolve_claim(e, [("2026-08-10", eur_snap(0.8, "2026-08-10"))])
        self.assertEqual(r.status, "无法判定")
        self.assertIn("未给出阈值", r.sentence)


class ResolveIsCalendarFreeTest(unittest.TestCase):
    """运行日只由快照里的 ref_date 去重得出,脚本不查日历。"""

    def test_repeated_ref_date_is_not_a_running_day(self):
        r = claims.resolve_claim(entry(), [
            ("2026-08-10", eur_snap(0.86693, "2026-08-10")),
            ("2026-08-11", eur_snap(0.86693, "2026-08-10")),
        ])
        self.assertEqual(r.running_days, 0)

    def test_new_ref_date_is_one_running_day(self):
        r = claims.resolve_claim(entry(), [
            ("2026-08-10", eur_snap(0.86693, "2026-08-10")),
            ("2026-08-11", eur_snap(0.86700, "2026-08-11")),
        ])
        self.assertEqual(r.running_days, 1)

    def test_module_imports_no_calendar_machinery(self):
        import inspect
        src = inspect.getsource(claims)
        for banned in ("datetime", "calendar", "weekday", "holiday"):
            self.assertNotIn(banned, src)


class StatusesAreExhaustiveTest(unittest.TestCase):
    def test_four_statuses_exactly(self):
        self.assertEqual(claims.STATUSES,
                         ("未到期", "命中", "未命中", "无法判定"))


if __name__ == "__main__":
    unittest.main()
