"""附录 A 生成器(scripts/appendix.py):锚点常量与附录块的唯一事实源。

守三件事,每件对应一个已点名的变异:
  ① 锚点字面量只在 appendix.py 里写一份(第二份拷贝必然漂移,与
     REVIEW_BLOCK_HEADING 同规格);
  ② 附录块**确定性**:同一输入逐字节相同(校验端要做整块逐字比对);
  ③ 纯函数 + 薄 CLI:导入期零副作用(校验端要 import 它)。
"""
import ast
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest

from scripts import appendix, check_report

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "scripts", "appendix.py")


def daily_snap():
    """一份覆盖全部分支的日报快照:结论句有/无、事件条目有/无/坏、
    official 键有/无/空、rates 条目有/无、双源偏差有/无、可疑标记有。"""
    return {
        "date": "2026-08-14",
        "rates": {
            "EUR": {"primary": 0.867, "deviation_pct": 0.014, "suspect": False},
            "PHP": {"primary": 61.325, "deviation_pct": 0.09, "suspect": False},
            "THB": {"primary": 33.13, "deviation_pct": None, "suspect": True},
            "BRL": {"primary": 5.1811, "deviation_pct": 0.291, "suspect": False},
        },
        "events": {
            "USD": {"articles": [{"seendate": "20260813T212449Z"},
                                 {"seendate": "20260812T173332Z"},
                                 {"seendate": "看不懂的时间戳"}],
                    "channel": "gnews",
                    "official": [{"published": "Wed, 29 Jul 2026 18:00:00 GMT"}]},
            "EUR": {"articles": [{"seendate": "20260813T111322Z"}],
                    "channel": "gnews", "official": []},
            "PHP": {"articles": []},
            "THB": {"articles": "oops"},
            "BRL": {"articles": [{"seendate": "20260812T110219Z"}],
                    "channel": "gdelt"},
        },
        "derived": {
            "schema_version": 3,
            "events": {
                "USD": {"events_verdict":
                        "当日采到 11 条(源返回的原始样本顶到其上限,滤后条数是下界)"},
                "EUR": {"events_verdict": "当日采到 1 条"},
                "PHP": {"events_verdict": "当日未采到事件"},
                "THB": {"events_verdict": None},
                "BRL": {"events_verdict": "当日采到 1 条"},
            },
            "rates": {"EUR": {"deviation_pct_prev": 0.093},
                      "PHP": {"deviation_pct_prev": None}},
        },
        "meta": {"caps": {"official_daily": 3}},
    }


DAILY_EXPECTED = "\n".join([
    "## 附录 A:采集口径与结论句(scripts/appendix.py 生成,勿手改)",
    "",
    "- USD 事件结论(逐字):当日采到 11 条(源返回的原始样本顶到其上限,滤后条数是下界)",
    "- EUR 事件结论(逐字):当日采到 1 条",
    "- PHP 事件结论(逐字):当日未采到事件",
    "- THB 事件结论(逐字):结论句不可得(快照未落结论句)",
    "- BRL 事件结论(逐字):当日采到 1 条",
    "- 采见日口径:USD 2026-08-12、2026-08-13、不可辨认 1 条;EUR 2026-08-13;"
    "PHP 无条目;THB 无事件条目;BRL 2026-08-12",
    "- 通道口径:USD gnews;EUR gnews;PHP 未记录(存量快照);THB 无事件条目;BRL gdelt",
    "- 公告口径:USD 1 条(发布日 2026-07-29);EUR 0 条;PHP 快照无 official 键;"
    "THB 快照无 official 键;BRL 快照无 official 键;当日公告上限 3 条",
    "- 双源偏差:USD 快照 rates 容器无该币种条目;EUR 0.014(前值 0.093);"
    "PHP 0.09(前值 null);THB null(前值 null);BRL 0.291(前值 null);可疑标记:THB",
])


def digest():
    return {
        "week": "2026-W33", "window_from": "2026-08-10", "window_to": "2026-08-14",
        "skipped": 0,
        "events": {
            "USD": {"articles_verdict": "区间内至少 29 条(1/5 天未采到)",
                    "official_verdict": "区间内未见公告,有无公告无法判定"},
            "EUR": {"articles_verdict": "区间内至少 19 条",
                    "official_verdict": "区间内至少 2 条"},
            "PHP": {"articles_verdict": "区间内至少 19 条", "official_verdict": None},
            "THB": {"articles_verdict": "区间内至少 9 条",
                    "official_verdict": "未接入或全区间采集失败,有无公告无法判定"},
            "BRL": {},
        },
        "rates": {
            "EUR": {"fixings_verdict": "区间内观测到 3 个不同价位"},
            "PHP": {"fixings_verdict": "区间内观测到 3 个不同价位"},
            "THB": {"fixings_verdict": None},
            "BRL": {"fixings_verdict": "区间内观测到 3 个不同价位"},
        },
    }


WEEKLY_EXPECTED = "\n".join([
    "## 附录 A:结论句逐字引用与观测口径(scripts/appendix.py 生成,勿手改)",
    "",
    "以下逐字引自周度聚合文件,一个字符未改。",
    "",
    "- USD 事件(逐字):区间内至少 29 条(1/5 天未采到)",
    "- USD 公告(逐字):区间内未见公告,有无公告无法判定",
    "- USD 定盘与区间(逐字):基准货币,聚合文件 rates 容器无该币种条目,无定盘结论句",
    "- EUR 事件(逐字):区间内至少 19 条",
    "- EUR 公告(逐字):区间内至少 2 条",
    "- EUR 定盘与区间(逐字):区间内观测到 3 个不同价位",
    "- PHP 事件(逐字):区间内至少 19 条",
    "- PHP 公告(逐字):结论句不可得(聚合文件未落结论句)",
    "- PHP 定盘与区间(逐字):区间内观测到 3 个不同价位",
    "- THB 事件(逐字):区间内至少 9 条",
    "- THB 公告(逐字):未接入或全区间采集失败,有无公告无法判定",
    "- THB 定盘与区间(逐字):结论句不可得(聚合文件未落结论句)",
    "- BRL 事件(逐字):结论句不可得(聚合文件未落结论句)",
    "- BRL 公告(逐字):结论句不可得(聚合文件未落结论句)",
    "- BRL 定盘与区间(逐字):区间内观测到 3 个不同价位",
    "- 口径差异:事件与公告结论句按区间累计条数计,定盘结论句按不同价位计,"
    "三档口径不可比,不得相加;覆盖区间 2026-08-10 至 2026-08-14,跳过 0 份。",
])


class AnchorIsTheSingleSourceTest(unittest.TestCase):
    """锚点是**产出方**的常量。第二份字面量拷贝必然漂移,而漂移后分界要么
    整个失效、要么整个错位,两种都静默 —— 与 REVIEW_BLOCK_HEADING 同规格。"""

    def test_anchor_constants_are_verbatim(self):
        self.assertEqual(appendix.APPENDIX_ANCHOR_DAILY,
                         "## 附录 A:采集口径与结论句(scripts/appendix.py 生成,勿手改)")
        self.assertEqual(appendix.APPENDIX_ANCHOR_WEEKLY,
                         "## 附录 A:结论句逐字引用与观测口径"
                         "(scripts/appendix.py 生成,勿手改)")

    def test_anchor_is_the_first_line_of_each_block(self):
        self.assertEqual(appendix.daily_appendix(daily_snap()).splitlines()[0],
                         appendix.APPENDIX_ANCHOR_DAILY)
        self.assertEqual(appendix.weekly_appendix(digest()).splitlines()[0],
                         appendix.APPENDIX_ANCHOR_WEEKLY)

    def test_no_second_copy_of_the_anchor_anywhere_under_scripts(self):
        """`scripts/` 下除 appendix.py 外,任何文件都不得再写一份锚点字面量
        (校验端只许 import)。第二份拷贝一出现,这条立刻红。"""
        others = []
        for dirpath, _, names in os.walk(os.path.join(ROOT, "scripts")):
            if "__pycache__" in dirpath:
                continue
            for name in sorted(names):
                if not name.endswith(".py") or name == "appendix.py":
                    continue
                path = os.path.join(dirpath, name)
                with open(path, encoding="utf-8") as f:
                    src = f.read()
                for anchor in (appendix.APPENDIX_ANCHOR_DAILY,
                               appendix.APPENDIX_ANCHOR_WEEKLY,
                               "scripts/appendix.py 生成,勿手改"):
                    if anchor in src:
                        others.append((path, anchor))
        self.assertEqual(others, [])

    def test_currency_order_is_mechanically_tied_to_the_checker(self):
        """两处各写一份币种表就会出现「附录按一个序、校验按另一个序」。"""
        self.assertEqual(list(appendix.CURRENCIES), check_report.CURRENCIES)


class DailyAppendixTest(unittest.TestCase):
    def test_block_is_verbatim(self):
        self.assertEqual(appendix.daily_appendix(daily_snap()), DAILY_EXPECTED)

    def test_events_verdict_is_quoted_character_for_character(self):
        snap = daily_snap()
        snap["derived"]["events"]["PHP"]["events_verdict"] = "当日采到 7 条(自造措辞)"
        self.assertIn("- PHP 事件结论(逐字):当日采到 7 条(自造措辞)",
                      appendix.daily_appendix(snap))

    def test_absent_verdict_is_not_invented(self):
        snap = daily_snap()
        del snap["derived"]["events"]["USD"]
        self.assertIn("- USD 事件结论(逐字):结论句不可得(快照未落结论句)",
                      appendix.daily_appendix(snap))

    def test_missing_deviation_is_null_not_zero(self):
        block = appendix.daily_appendix(daily_snap())
        self.assertIn("THB null(前值 null)", block)
        self.assertNotIn("THB 0(", block)

    def test_no_derived_container_still_produces_the_block(self):
        snap = daily_snap()
        del snap["derived"]
        block = appendix.daily_appendix(snap)
        self.assertEqual(block.splitlines()[0], appendix.APPENDIX_ANCHOR_DAILY)
        for c in appendix.CURRENCIES:
            self.assertIn("- %s 事件结论(逐字):结论句不可得(快照未落结论句)" % c,
                          block)

    def test_malformed_snapshot_does_not_raise(self):
        for bad in (None, [], "x", 7, {}, {"events": 7, "rates": "no", "derived": []}):
            with self.subTest(bad=bad):
                block = appendix.daily_appendix(bad)
                self.assertEqual(block.splitlines()[0], appendix.APPENDIX_ANCHOR_DAILY)

    def test_broken_official_key_is_not_reported_as_a_missing_key(self):
        """「没有这个键」与「键在但读不了」是两件事,合并会把缺陷说成常态。"""
        snap = daily_snap()
        snap["events"]["PHP"]["official"] = 7
        block = appendix.daily_appendix(snap)
        self.assertIn("PHP official 键结构不可读", block)
        self.assertNotIn("PHP 快照无 official 键", block)

    def test_impossible_seendate_is_unreadable_not_sliced(self):
        """20269999T000000Z 不是「2026-99-99」,是认不出。"""
        snap = daily_snap()
        snap["events"]["BRL"]["articles"] = [{"seendate": "20269999T000000Z"}]
        block = appendix.daily_appendix(snap)
        self.assertIn("BRL 不可辨认 1 条", block)
        self.assertNotIn("2026-99", block)

    def test_unknown_official_cap_is_declared_not_guessed(self):
        snap = daily_snap()
        snap["meta"] = {}
        self.assertIn(";当日公告上限不可知", appendix.daily_appendix(snap))


class WeeklyAppendixTest(unittest.TestCase):
    def test_block_is_verbatim(self):
        self.assertEqual(appendix.weekly_appendix(digest()), WEEKLY_EXPECTED)

    def test_fourteen_verdict_slots_are_all_present(self):
        """5 事件 + 5 公告 + 4 定盘 = 14 条结论句槽位,USD 的定盘槽写明理由。"""
        lines = appendix.weekly_appendix(digest()).splitlines()
        for c in appendix.CURRENCIES:
            for label in ("事件", "公告", "定盘与区间"):
                self.assertTrue(
                    any(ln.startswith("- %s %s(逐字):" % (c, label)) for ln in lines),
                    "缺 %s %s 槽位" % (c, label))

    def test_malformed_digest_does_not_raise(self):
        for bad in (None, [], "x", {}, {"events": 3, "rates": None}):
            with self.subTest(bad=bad):
                block = appendix.weekly_appendix(bad)
                self.assertEqual(block.splitlines()[0], appendix.APPENDIX_ANCHOR_WEEKLY)


class AppendixDeterminismTest(unittest.TestCase):
    """整块逐字比对是校验端的判据 —— 同一输入两次不同,那道闸门当场失效。"""

    def test_daily_block_is_byte_identical_across_calls(self):
        snap = daily_snap()
        self.assertEqual(appendix.daily_appendix(snap).encode("utf-8"),
                         appendix.daily_appendix(snap).encode("utf-8"))

    def test_weekly_block_is_byte_identical_across_calls(self):
        d = digest()
        self.assertEqual(appendix.weekly_appendix(d).encode("utf-8"),
                         appendix.weekly_appendix(d).encode("utf-8"))

    def test_key_insertion_order_does_not_change_the_block(self):
        """同内容、不同插入序的两份快照必须给出同一块 —— 否则「整块逐字」
        会在重跑采集后无故变红。"""
        snap = daily_snap()
        shuffled = copy.deepcopy(snap)
        for key in ("events", "rates"):
            shuffled[key] = {k: shuffled[key][k] for k in reversed(list(shuffled[key]))}
        shuffled["derived"]["events"] = {
            k: shuffled["derived"]["events"][k]
            for k in reversed(list(shuffled["derived"]["events"]))}
        self.assertEqual(appendix.daily_appendix(shuffled),
                         appendix.daily_appendix(snap))

    def test_seendates_are_sorted_regardless_of_article_order(self):
        snap = daily_snap()
        rev = copy.deepcopy(snap)
        rev["events"]["USD"]["articles"] = list(
            reversed(rev["events"]["USD"]["articles"]))
        self.assertEqual(appendix.daily_appendix(rev), appendix.daily_appendix(snap))

    def test_two_processes_with_different_hash_seeds_agree(self):
        """集合/字典迭代序泄漏进块时,同一份输入在两个进程里会给出不同的字节。
        单进程内比对看不见这一类(同进程哈希序稳定),必须跨进程比。"""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        outs = []
        for mode, payload in (("daily", daily_snap()), ("weekly", digest())):
            path = os.path.join(tmp.name, mode + ".json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
            for seed in ("0", "1", "2"):
                env = dict(os.environ, PYTHONHASHSEED=seed)
                r = subprocess.run([sys.executable, SCRIPT, "--mode", mode,
                                    "--input", path],
                                   capture_output=True, env=env)
                self.assertEqual(r.returncode, 0, r.stderr)
                outs.append((mode, seed, r.stdout))
            got = {o[2] for o in outs if o[0] == mode}
            self.assertEqual(len(got), 1, "同一输入跨进程给出了不同的块:%r" % (outs,))

    def test_block_has_no_trailing_newline_or_whitespace(self):
        for block in (appendix.daily_appendix(daily_snap()),
                      appendix.weekly_appendix(digest())):
            self.assertEqual(block, block.rstrip())
            for line in block.splitlines():
                self.assertEqual(line, line.rstrip())


class AppendixPurityTest(unittest.TestCase):
    """纯函数 + 薄 CLI:导入期不读写文件、不解析 argv —— 校验端要 import 它。"""

    def _module_ast(self):
        with open(SCRIPT, encoding="utf-8") as f:
            return ast.parse(f.read())

    def test_module_level_has_no_executable_statements(self):
        allowed = (ast.Import, ast.ImportFrom, ast.Assign, ast.AnnAssign,
                   ast.FunctionDef, ast.ClassDef)
        for node in self._module_ast().body:
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
                continue                      # docstring
            if isinstance(node, ast.If):      # 只允许 if __name__ == "__main__"
                self.assertEqual(ast.dump(node.test).count("__name__"), 1,
                                 "模块级 if 只允许 __main__ 守卫")
                continue
            self.assertIsInstance(node, allowed,
                                  "模块级出现可执行语句:%s" % ast.dump(node)[:80])

    def test_module_level_assignments_are_constant_literals(self):
        for node in self._module_ast().body:
            if isinstance(node, ast.Assign):
                self.assertIsInstance(
                    node.value, (ast.Constant, ast.Tuple, ast.List, ast.Dict,
                                 ast.JoinedStr, ast.BinOp),
                    "模块级常量不得由函数调用求值:%s" % ast.dump(node)[:80])

    def test_pure_functions_do_not_mutate_their_input(self):
        snap, d = daily_snap(), digest()
        before_snap, before_digest = copy.deepcopy(snap), copy.deepcopy(d)
        appendix.daily_appendix(snap)
        appendix.weekly_appendix(d)
        self.assertEqual(snap, before_snap)
        self.assertEqual(d, before_digest)

    def test_importing_the_module_touches_no_file_and_no_argv(self):
        code = ("import builtins, sys\n"
                "sys.argv = ['sentinel-argv']\n"
                "opened = []\n"
                "real = builtins.open\n"
                "builtins.open = lambda *a, **k: opened.append(a) or real(*a, **k)\n"
                "sys.path.insert(0, %r)\n"
                "import scripts.appendix as m\n"
                "builtins.open = real\n"
                "print(len(opened), sys.argv[0])\n" % ROOT)
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "0 sentinel-argv")


class AppendixCliTest(unittest.TestCase):
    """薄 CLI:stdout 就是纯函数的输出,退出码 0=正常 / 2=用法错误或输入不可读。"""

    def _write(self, payload):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, "in.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
        return path

    def _run(self, *argv):
        return subprocess.run([sys.executable, SCRIPT] + list(argv),
                              capture_output=True, text=True)

    def test_daily_stdout_is_the_block(self):
        r = self._run("--mode", "daily", "--input", self._write(daily_snap()))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, DAILY_EXPECTED + "\n")

    def test_weekly_stdout_is_the_block(self):
        r = self._run("--mode", "weekly", "--input", self._write(digest()))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, WEEKLY_EXPECTED + "\n")

    def test_missing_input_file_is_rc2(self):
        r = self._run("--mode", "daily", "--input", "/nonexistent/x.json")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "")
        self.assertTrue(r.stderr.strip())

    def test_unparsable_input_is_rc2(self):
        path = self._write(daily_snap())
        with open(path, "w", encoding="utf-8") as f:
            f.write("{not json")
        r = self._run("--mode", "daily", "--input", path)
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "")

    def test_positional_arguments_are_refused(self):
        """位置参数是本仓库栽过的静默放行路径(check_report weekly 那条)。"""
        r = self._run("--mode", "daily", "--input", self._write(daily_snap()), "extra")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "")

    def test_real_snapshot_runs(self):
        r = self._run("--mode", "daily", "--input",
                      os.path.join(ROOT, "data", "2026-08-14.json"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.startswith(appendix.APPENDIX_ANCHOR_DAILY))


if __name__ == "__main__":
    unittest.main()
