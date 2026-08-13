# 验证报告:fx-gnews-event-channel

- change:`fx-gnews-event-channel`
- 分支:`feature/20260812/fx-gnews-event-channel`
- base-ref:`5e1bba91b507fc6b1182ed44f14053e8e55b7ff2`
- verify_mode:full(21 任务 / 1 capability / 27 变更文件)
- 验证日期:2026-08-13

## 1. 变更内容

事件通道由 GDELT-only 改为 **Google News RSS 主通道 + 域名白名单相关性闸门 +
GDELT 空洞补位**。核心在 `scripts/collect/events.py`;新增 `config/news_sources.json`
(38 个域名);下游 `scripts/collect/derive.py` 与 `scripts/weekly_digest.py` 改为
读取采集层算好的截断/过滤账,并在跨通道时拒绝给出差值。

## 2. 数字纪律声明

本报告中每个计数均由下方 `sc-evidence` 块**现场执行**产生,脚本自跑自捕获并对
输出签发哈希。以下两条为本次开发过程中写下后被实测证伪、按仓库硬规则逐字更正
入档的记录,一并保留:

1. **第四轮首次变异电池报「15/15 KILLED」是假杀。** 首轮运行超时被 SIGTERM 打断,
   `derive.py` 里留下一个变异体,而我只 grep 了 `weekly_digest.py` 就判定还原干净。
   整场电池每个变异体都被那条无关的红用例杀掉。给脚本加基线自检(基线不绿即拒跑)
   与逐条还原逐字比对后重跑,杀手才换成各自的靶点用例。
2. **第六轮记的「归档电池全部 KILLED」经第七轮实测为 26/35。** 三份归档件里有
   9 条靶点的原文已被后续轮次改写,脚本只打印一行 PATCH-FAIL 后继续、退出码仍为 0。
   已把 PATCH-FAIL 升级为 STALE 硬失败(非零退出),摘要行改为区分「登记/执行」,
   并新增对应 HEAD 的电池。design §13.5 的措辞与数字已全部更正。

## 3. 验证证据(现场执行)

### 3.1 全量测试
```sc-evidence
$ env PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -t .
exit: 0
.......................................--daily 需与 --digest 同用(单独给日报不会启用数字溯源)
.周度聚合文件无法解析: Expecting value: line 1 column 1 (char 0)
.周度聚合文件无法解析: Expecting value: line 1 column 1 (char 0)
..周度聚合文件结构不符(需含 week 与 generated_from)
周度聚合文件结构不符(需含 week 与 generated_from)
...............................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................
----------------------------------------------------------------------
Ran 554 tests in 12.868s

OK
CHECK PASSED
CHECK PASSED
CHECK FAILED (1):
 - SECTION_MISSING: 缺少币种节 THB
snapshot: /tmp/tmp09e_rv4r/data/2026-08-10.json
gaps: 2
  - [frankfurter/all] URLError: <urlopen error [Errno 111] Connection refused>
  - [exchange-api/all] URLError: <urlopen error [Errno 111] Connection refused>
snapshot: /tmp/tmpujaez5me/data/2026-08-10.json
gaps: 1
  - [calendar/all] calendar expired (valid_until=2026-01-01), 请按 README 年历维护说明更新
snapshot: /tmp/tmpddj73jj1/data/2026-08-10.json
gaps: 1
  - [dbnomics/X] URLError: <urlopen error [Errno 111] Connection refused>
snapshot: /tmp/tmp9zqq2hv8/data/2026-08-10.json
gaps: 1
  - [exchange-api/all] URLError: <urlopen error [Errno 111] Connection refused>
snapshot: /tmp/tmpyrsci60m/data/2026-08-10.json
gaps: 1
  - [frankfurter/all] URLError: <urlopen error [Errno 111] Connection refused>
snapshot: /tmp/tmp89pwu6ct/data/2026-08-10.json
gaps: 5
  - [gdelt/THB] URLError: <urlopen error [Errno 111] Connection refused>
  - [gdelt/BRL] URLError: <urlopen error [Errno 111] Connection refused>
  - [gdelt/USD] URLError: <urlopen error [Errno 111] Connection refused>
  - [gdelt/EUR] URLError: <urlopen error [Errno 111] Connection refused>
  - [gdelt/PHP] URLError: <urlopen error [Errno 111] Connection refused>
snapshot: /tmp/tmpvhigmur7/data/2026-08-10.json
gaps: 1
  - [derive/all] internal error RuntimeError: boom
snapshot: /tmp/tmpu_2ypfgp/data/2026-08-10.json
gaps: 0
snapshot: /tmp/tmphcseal_g/data/2026-08-10.json
gaps: 0
snapshot: /tmp/tmpnc1gvlph/data/2026-08-10.json
gaps: 5
  - [gdelt/THB] HTTPError: HTTP Error 404: Not Found
  - [gdelt/BRL] HTTPError: HTTP Error 404: Not Found
  - [gdelt/USD] HTTPError: HTTP Error 404: Not Found
  - [gdelt/EUR] HTTPError: HTTP Error 404: Not Found
  - [gdelt/PHP] HTTPError: HTTP Error 404: Not Found
snapshot: /tmp/tmpxxl7vyus/data/2026-08-10.json
gaps: 0
snapshot: /tmp/tmpbakap6ys/data/2026-08-10.json
gaps: 5
  - [gdelt/THB] HTTPError: HTTP Error 404: Not Found
  - [gdelt/BRL] HTTPError: HTTP Error 404: Not Found
  - [gdelt/USD] HTTPError: HTTP Error 404: Not Found
  - [gdelt/EUR] HTTPError: HTTP Error 404: Not Found
  - [gdelt/PHP] HTTPError: HTTP Error 404: Not Found
snapshot: /tmp/tmpallc9lj_/data/2026-08-10.json
gaps: 0
snapshot: /tmp/tmpb84kbjqo/data/2026-08-10.json
gaps: 1
  - [snapshot/prev] corrupt prev snapshot 2026-08-09: JSONDecodeError: Expecting property name enclosed in double quotes: line 1 column 2 (char 1)
snapshot: /tmp/tmpbuvgfwr7/data/2026-08-10.json
gaps: 1
  - [snapshot/prev] corrupt prev snapshot 2026-08-09: RecursionError: maximum recursion depth exceeded while decoding a JSON array from a unicode string
snapshot: /tmp/tmp8jhs8tuw/data/2026-08-10.json
gaps: 1
  - [macro/all] internal error RuntimeError: boom
snapshot: /tmp/tmpd6fqc5br/data/2026-08-10.json
gaps: 1
  - [dbnomics/X] URLError: <urlopen error [Errno 111] Connection refused>
snapshot: /tmp/tmpkj0ubo16/data/2026-08-10.json
gaps: 0
snapshot: /tmp/tmpklbg57op/data/2026-08-10.json
gaps: 1
  - [snapshot/prev] corrupt prev snapshot 2026-08-09: top-level list, expected dict
sc-evidence: sha256:93c4fdae9afc55c894dc7765a9d42b66dd712d43dd66190066646bd9435961ab kind:automated
```

### 3.2 变异电池(对应 HEAD;脚本自带基线自检与 STALE 硬失败)
```sc-evidence
$ python3 docs/superpowers/evidence/2026-08-13-fx-gnews-mutations-head.py
exit: 0
BASELINE OK

KILLED    N1 count_at_cap 用去重前长度(GDELT)      test_count_at_cap_excludes_deduped_duplicates
KILLED    N2 count_at_cap 用 kept(gnews)      test_count_at_cap_and_source_capped_split_on_gnews
KILLED    N3 主通道跑失败不记账                       test_main_channel_failure_blocks_the_zero_claim
KILLED    N4 有意停用被误记成跑失败                     test_disabled_main_channel_is_not_a_failure
KILLED    N5 derive 不落 main_sample_capped    test_main_sample_capped_is_not_key_presence, test_sample_c
KILLED    N6 main_sample_capped 按键在与否判       test_main_sample_capped_is_not_key_presence
KILLED    N7 不过滤通道仍说「滤除」                     test_landed_below_cap_is_not_a_count_truncation
KILLED    N8 聚合器不累加丢弃量(原 M54)                test_collector_dropped_malformed_blocks_zero_claim, test_m
KILLED    N9 capped 退回读 source_capped(原 M57) test_count_capped_follows_count_at_cap_downstream, test_la
KILLED    N10 derive 不用共享谓词(原 M69)           test_capped_flag_set_on_both_sides, test_count_capped_foll
KILLED    N11 sample own 分支整支删除(原 S9)        test_landed_below_cap_is_not_a_count_truncation
KILLED    N12 own 分支不记上限(原 M90)              test_landed_below_cap_is_not_a_count_truncation

本轮 KILLED 12 / 执行 12 / 登记 12
sc-evidence: sha256:8214c70f94c1436919cd351298ffd2e3bee7630a7b739d9201903834dda09635 kind:automated
```

### 3.3 日报校验器(真实快照 + 真实报告,含 --strict-brief)
```sc-evidence
$ python3 scripts/check_report.py reports/daily/2026-08-12.md data/2026-08-12.json --brief briefs/2026-08-12-brief.md --mode daily --strict-brief
exit: 0
CHECK PASSED
sc-evidence: sha256:59a49e69901608e3aad01f22352c146e51d2855321b872c456c8ae8e1586418a kind:automated
```

### 3.4 周报校验器(既有交付产物未因本变更失效)
```sc-evidence
$ python3 scripts/check_report.py reports/weekly/2026-W33.md state/weekly-digest-2026-W33.json --mode weekly
exit: 0
CHECK PASSED
sc-evidence: sha256:19261f55e66381cf16325e5d0c1bd520848a1469c21e80a96c34604e7f04c6f7 kind:automated
```

### 3.5 真实快照的采集完整性(零 gap、五币种经主通道)
```sc-evidence
$ python3 -c $'\nimport json\nd=json.load(open(\'data/2026-08-12.json\'))\nprint(\'gaps:\', d[\'gaps\'])\nfor c in (\'USD\',\'EUR\',\'PHP\',\'THB\',\'BRL\'):\n    e=d[\'events\'][c]\n    print(\'%s channel=%s articles=%d raw=%s attributable_absent=%s\' % (\n        c, e[\'channel\'], len(e[\'articles\']), e[\'articles_raw_count\'],\n        e[\'attributable_source_absent\']))\n'
exit: 0
gaps: []
USD channel=gnews articles=11 raw=100 attributable_absent=False
EUR channel=gnews articles=1 raw=38 attributable_absent=False
PHP channel=gnews articles=12 raw=33 attributable_absent=False
THB channel=gnews articles=7 raw=29 attributable_absent=False
BRL channel=gnews articles=5 raw=34 attributable_absent=False
sc-evidence: sha256:5dfcd7167b5633882dd46e7d52330da76274e5aac4c6c39d68f9d18f08ef2eb1 kind:automated
```

### 3.6 delta spec 场景覆盖(36 个场景逐条映射到用例并实跑)

映射表落盘于 `docs/superpowers/evidence/2026-08-13-fx-gnews-scenario-map.py`,可复跑。

```sc-evidence
$ python3 -c $'\nimport subprocess,sys,os\nsys.path.insert(0,\'docs/superpowers/evidence\')\nimport importlib.util\nspec=importlib.util.spec_from_file_location(\'m\',\'docs/superpowers/evidence/2026-08-13-fx-gnews-scenario-map.py\')\nm=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)\nimport re\nscen=[l.split(\':\',1)[1].strip() for l in open(\'openspec/changes/fx-gnews-event-channel/specs/fx-data-collection/spec.md\',encoding=\'utf-8\') if l.startswith(\'#### Scenario:\')]\nmissing=[s for s in scen if s not in m.MAP]\nprint(\'spec 场景数:\', len(scen))\nprint(\'已映射场景数:\', len(m.MAP))\nprint(\'未映射场景:\', missing if missing else \'无\')\ntests=sorted({t for v in m.MAP.values() for t in v})\nprint(\'涉及用例数:\', len(tests))\np=subprocess.run([sys.executable,\'-m\',\'unittest\']+tests,capture_output=True,text=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE=\'1\'))\nprint([l for l in p.stderr.splitlines() if l.startswith((\'Ran \',\'OK\',\'FAILED\'))])\nsys.exit(p.returncode)\n'
exit: 0
spec 场景数: 36
已映射场景数: 36
未映射场景: 无
涉及用例数: 48
['Ran 48 tests in 1.226s', 'OK']
sc-evidence: sha256:b76ba4c36d02ff09e76c08192b5d0ea53843b81e228f61f5bddcf9b1d514ba8f kind:automated
```

## 4. 完整验证结论(openspec-verify-change 三维)

| 维度 | 结果 |
|------|------|
| Completeness | 21/21 OpenSpec 任务 `[x]`;56/56 plan 步骤 `[x]`;36/36 delta spec 场景有实现与用例 |
| Correctness | 554 测试通过 exit 0;36 场景对应 48 条用例实跑 OK;HEAD 变异电池 12/12 exit 0 |
| Coherence | 实现符合 design.md 的 D1–D6;Design Doc §1–7 为原设计,§8–13 逐轮记录七次审查的修正,与 delta spec 的增补一一对应 |

### CRITICAL

无。

### WARNING

无。七轮审查共 106 条发现全部处理完毕(其中 10 条经两名独立复核者证伪推翻,
理由与实跑证据记入 Design Doc §11.4、§13 与本轮记录)。

### SUGGESTION

1. `tests/test_weekly_digest.py` 的 `LegacySnapshotCapParityTest` 类中混入了四条
   与「存量快照上限一致性」无关的用例(补位日双截断、主通道跑失败、纯 GDELT 单次
   披露、未触顶日不稀释上限)。类名因此有误导性,建议后续拆分。不影响正确性。
2. 结论句在缺口较多的区间会变长(真实 W33 的 USD 含 5 条 caveat)。每条都为真且
   与判定相关,但可读性偏低。其中「N 天的不可识别条数不可知(存量快照无此账)」
   会随新快照落盘自然消失。

## 5. 已知遗留(不在本变更范围,已立项)

1. **`scripts/check_report.py` 从不校验报告是否逐字引用脚本算出的 verdict**
   ——实测:周报写「区间内至少 15 条(3/5 天未采到)」而 digest 为「至少 26 条
   (3/6 天未采到)」,`CHECK PASSED`,因为 15 与 5 作为无关数字出现在 digest
   别处(数字白名单是无序词袋)。本变更建立的全部结论句因此没有强制力。
2. **数值精度未在采集层统一**:`macro.py:291` 的 `_yoy` 已 `round(..., 3)`,而
   BIS 路径直取 CSV 的 `OBS_VALUE`,同一个「CPI 同比」落盘 10 位小数并原样进入
   中文正文。实测 BIS CPI 100% 超过 3 位、dbnomics 经常账户 80%。
3. **被白名单滤除的域名未落盘**:只有计数。实测 2026-08-12 一天滤掉 198 条
   (USD 89 / EUR 37 / PHP 21 / THB 22 / BRL 29),调整白名单时无从知道漏了谁。
4. `reports/daily/2026-08-11.md` 的 `GAP_OMITTED: 缺漏节未提及 gdelt/THB`
   ——本变更之前的既有状态(相关三个文件本变更一行未碰)。
5. 落盘产物由当日代码生成,代码修复不回溯,且没有重算入口(本次为展示当前质量,
   已就地重算 `data/2026-08-12.json` 的 `derived` 计算节并在 commit 中披露)。

## 6. 安全性

- 全链路零 API key:本变更新增的两个端点(`gnews_rss_url`)与白名单文件均无鉴权
- Python 标准库 only,无新增依赖
- 无硬编码密钥;采集层异常一律转 gap,绝不向上抛
