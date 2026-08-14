"""fx-verdict-enforcement 变异电池 —— Design Doc §7 的 10 条靶点 + BOUND 一条
+ T8b 的 M12/M13/M14 + T8c 的 M15 + T9 的 M16-M25,共 25 条。

**T9 补的十条,补的是两次"修完就没人再打"的修复**(地板 15→25):
M16-M20 打本轮修掉的 weekly 静默放行路径(位置参数被接受却完全不读 +
`--digest` 缺席时结论句闸门与数字溯源整层不跑却打印通过);
M21-M25 打上一次修复(tasks §7 的复盘材料块豁免,已在 HEAD 里)——
那次只跑了一次性的 6/6 变异,**没有留下常驻靶点**,处境与本 change 早期
那些"修完就没人再打"的修复完全相同。靶点表因此第一次覆盖到
`split_brief_review_block` / `is_generated_review_line` 这两个函数。

在**仓库根目录**运行:python3 docs/superpowers/evidence/2026-08-13-fx-verdict-mutations.py

自带八道自检,每一条都来自实际事故:
1. **基线自检** —— 基线不绿就拒跑并非零退出。一次超时留下的变异体让
   「15/15 KILLED」全部为假杀。
2. **逐字节校验** —— 变异体应用后校验落盘内容与预期逐字节相同,还原后
   校验与原文逐字节相同,**`finally` 的兜底还原之后同样校验**。写坏或没写
   进去必须就地炸,不能悄悄跑完。
   **读写一律走二进制、比 bytes**(T8c 改):此前 read/write 是文本模式,
   通用换行会把 `\\r\\n` 读回 `\\n`,正好抵消写入时的翻译。
   实测(2026-08-13,T8c 工作树,靶点缩到 1 条的副本,下同):把**旧**电池的
   write 改成 `newline="\\r\\n"` → 电池 **rc=0**、「KILLED 1 / 执行 1 /
   登记 1」,**打印的 5 个文件指纹与干净跑逐字节相同**
   (check_report.py dcc3d861…、derive.py ed3b411b…,与 `sha256sum` 备份
   一字不差),而磁盘上 5 个文件全部变成 CRLF:
   29208→29744 / 19377→19775 / 2130→2170 / 17281→17540 / 9057→9201。
   **三道逐字节校验一道没响** —— 因为它们比的是解码后的文本,不是字节。
   同一份投毒打到**本文件**上:rc=1,第一道就炸
   「变异未逐字节落盘:scripts/check_report.py」。
   **三处都是显式判断 + raise,不是 assert**:`python3 -O` / `PYTHONOPTIMIZE=1`
   会把 assert 语句整条删掉,于是这几道护栏在优化模式下集体消失,电池照样
   打印满屏 KILLED 并退出 0 —— 而那正是它们存在的理由。
3. **STALE 硬失败** —— 靶点原文与源码不匹配(0 处或多处)时非零退出。
   归档电池曾在干净副本上只有 26/35,9 个陈旧靶点静默 PATCH-FAIL 却退出 0。
4. **最小条数地板** —— `EXPECTED_TARGETS` 是与 `len(M)` **无关**的常量。
   汇总行里的「登记」就是 `len(M)`,它不是独立事实源:实测删掉一部分靶点
   (`M = M[:2]`)三个数一起缩水、仍退出 0;把 M 清空则打印
   「KILLED 0 / 执行 0 / 登记 0」退出 0。地板让「靶点被删」在下一次跑时炸。
5. **源码指纹** —— 每次跑都打印被变异文件的 sha256、**电池自身的 sha256**、
   **`git rev-parse HEAD`**,以及 **`tests/` 目录的指纹**(T8d 补后两项)。
   靶点是照着某一版源码写的字面串,源码改了而靶点没跟上时 STALE 才会响;
   指纹让「这次跑的到底是不是那一版字节」在归档报告里可核对。本 change 内
   M3 就腐坏过一次(T6b 改 check_daily 后锚点 0 处匹配),是人工前置复验才
   发现的。电池自身此前**不打指纹** —— 针对电池的篡改连人读的线索都没有。
   (指纹现在取自**文件字节**;此前取的是解码后文本再编码,对无 BOM 的
   UTF-8 文件同值,所以历史指纹仍可比。)
   **T8d:`tests/` 此前一个指纹都没有,而真正执行杀伤的就是它。**
   5 个被变异文件的指纹只回答「被打的是哪一版字节」,不回答「开枪的是
   哪一版字节」—— 归档报告里的「KILLED n/n」全部来自 `tests/`。
6. **靶点指纹** —— 每条靶点打印 `sha256("\\0".join(name, path, old, new))[:8]`。
   第 4 道地板守的是 `len(M)`,**不是靶点身份**,对「等量替换」完全失明。
   实测:把 M14 从带 `SUPPRESS` 的隐藏开关弱化成不带 SUPPRESS 的可见开关
   (条数不变、名字不变),**修前**版本对这两份靶点表打印的内容完全一致
   (两次跑的启动段输出 diff 为空);加了靶点指纹后同一对照下 M14 的指纹
   变了,两条线索都在归档报告里肉眼可分。
   **T8c 两处修正,逐条实测(2026-08-13)**:
   ①此前 `target_fp` 收了 `path` 却在 `sha(name+old+new)` 里丢掉 ——
   把 M13 的 path 由周报 SKILL 换成日报 SKILL,旧写法两边都是 `dadf7445`
   (一字不差),而该锚点 `grep -c -F` 在两份 SKILL 里**各恰好 1 处**
   → 不会 STALE、靶点照常 KILLED,**周报侧那条指向从此不再被任何变异覆盖**;
   新写法 `a29db7da` vs `32283e0c`,分得开。
   ②此前无分隔符直接拼接,边界平移指纹不变:把 old 尾部一个字符挪到 new
   头部、把 name 尾部一个字符挪到 old 头部,旧写法两种都仍是 `dadf7445`;
   新写法分别是 `c2f9b25d` / `1b8302ad`。现在用 `\\0` 连接,path 也进摘要。
   **代价**:14 条靶点指纹与 T8b 及更早的归档报告全部对不上,这是预期的
   一次性断裂,不是腐坏。
   **注意:只打印、不比对** —— 把上一次的指纹记进仓库并自动比对是另一个
   设计决定,不在本轮范围。
7. **事实源在电池之外(T8c 新增)+ 跑前必须干净(T8d 补)** ——
   开跑前 `git status --porcelain` **必须为空**,否则拒跑并列出脏文件;
   开跑前与 `finally` 末尾各取一次,不相等就炸。
   **只比「前后相等」是不够的**(T8d 实证,不是对抗构造。跑在提交
   `3824b8c` 上,用的是 **acdd7de 版本的本文件**、靶点缩到 1 条的副本,
   本机无 `FRED_API_KEY`):把靶点换成一条**纯注释改写**(把
   `# ---- 违规处置文案:**唯一事实源在这里,SKILL 不再复述** ----`
   的强调号去掉,行为零影响)——
   - **干净树**:`SURVIVED / KILLED 0 / 执行 1 / 登记 1`、**rc=1**
     (证明该变异真的没有断言抓得住);
   - 在 `tests/test_check_report.py` 的既有方法
     `test_disposition_constants_are_frozen_verbatim` 里加**两行** sha256
     钉死(`import hashlib` + 一句 `assertEqual`;**不新增测试、不改测试数**)
     再跑**同一份**电池 → **rc=0**、`KILLED 1 / 执行 1 / 登记 1`、
     `BASELINE OK — Ran 686 tests`(与提交态同数)、5 个文件指纹
     **与干净态逐字节相同**(`check_report.py` 两次都是 `70fbdba2…`)、
     第 7 道**完全静默** —— 因为 ` M tests/test_check_report.py` 在 before
     与 after 里都在,两者相等。
   同一棵脏树上跑**本文件**:rc=1「工作树不干净,拒绝跑电池」并列出脏文件。
   **「先改测试、跑电池、再提交」是本仓库的正常工序**,顺序一颠倒,归档报告
   里的「KILLED n/n」就归属到一棵没人能复跑的树上。所以判据升级为
   **「跑前干净」+「跑前跑后相等」**,并把 HEAD 与 `tests/` 指纹一并入档。
   前面那些逐字节校验比的都是**电池自己内存里的 `orig`**,所以「把 `orig`
   本身读脏」这一类改动它们一道也不响。实测(2026-08-13,T8c 工作树,
   靶点缩到 1 条):把**旧**电池的备份读取改成 `orig[p] = f.read()[1:]`
   (一行)→ rc=0、「KILLED 1 / 执行 1 / 登记 1」、5 个文件各少 1 字节
   (29208→29207 / 19377→19376 / 2130→2129 / 17281→17280 / 9057→9056)、
   `git status` 5 个 M —— **三道逐字节校验没有一道响**。
   同一份投毒打到**本文件**上:rc=1,炸在
   「工作树与开跑前不一致(判据是 git,不是电池自己的内存快照)」,
   并把仓库外副本路径一起打出来。
   三种投毒逐条实测结果(投毒 → 旧电池 / 本文件):
   crlf-write → rc=0 静默 / rc=1 第 2 道;
   poison-head → rc=0 静默 / rc=1 第 7 道;
   变体 D(兜底那轮少写一个字符)→ rc=1 第 2 道 / rc=1 第 2 道
   (这一条 T8b 已经堵上,列在这里是为了说明第 7 道**不是**它的替代品:
   第 2 道拿 `orig` 比,`orig` 自己被读脏时只剩第 7 道)。
8. **仓库外原文副本(T8c 新增)** —— 开跑前把 5 份原文按时间戳落到仓库外,
   路径在启动段打印。`finally` 只在正常异常路径上执行:SIGKILL / 外部超时
   杀掉进程时它**不执行**,工作树停在被变异状态且没有任何提示
   (T8b 复验者跑到一半时 `git status` 正显示 `M scripts/check_report.py`)。
   被中断后照那个路径 `cp` 回来即可。

**子进程环境是白名单(T8c 改)**:此前是名字黑名单,只 `pop("PYTHONOPTIMIZE")`,
其余原样转发。实测(2026-08-13,T8c 工作树)
`FRED_API_KEY=dummy python3 -m unittest discover -s tests -t .` →
`Ran 686 tests` / **FAILED (failures=11)** / rc=1;黑名单版电池会原样转发这个
变量,于是基线自检立刻报「BASELINE 不干净,拒绝跑电池」。方向是 fail-closed、
不会造假 KILLED,但它意味着**旧版本里所有头条数字只在没有 FRED key 的机器
上可复现**。改白名单后实际传给子进程的键只有
`HOME / LANG / PATH / PYTHONDONTWRITEBYTECODE`(实测打印),
`FRED_API_KEY` / `FX_*` / `PYTHONOPTIMIZE` 一并落在外面,同一份白名单环境跑
全量仍是 `Ran 686 tests / OK / rc=0` —— 判决与调用者的环境解耦。

汇总行格式:KILLED k / 执行 n / 登记 m。三者不相等即非零退出 —— 但**三者
相等只是必要条件**:它们同源(登记=len(M)),一起变小时仍然相等,所以
「登记」的下界由第 4 道自检的常量单独钉,不由这一行自证;而「靶点还是不是
那几条」由第 6 道的指纹留痕,同样不由这一行自证。

---- 边界声明:「KILLED n/n」到底证明了什么(T8e,请逐字抄进验证报告)----

**1. 「KILLED n/n」只意味着「全量套件退出码非 0」。** 它**不检查是哪一层
杀的**,也**不检查生产 CLI 的行为是否真的变了**。实证(2026-08-13,T8d 自跑,
跑在提交 `3824b8c` 上,用的是靶点缩到 1 条的电池副本):一条**零行为影响的
纯注释改写**在干净树上 `SURVIVED / KILLED 0 / 执行 1 / 登记 1 / rc=1`;
把两行未提交的 sha256 钉死加进 `tests/` 里一个**既有**测试方法后,**同一条**
改写立刻 `KILLED 1 / 执行 1 / 登记 1 / rc=0`,而 `Ran 686 tests`(与提交态
同数)、5 个被变异文件的指纹**全部逐字节不变**。分子由 `tests/` 说了算,
它与「产品行为有没有被破坏」之间**没有必然联系**。

**2. 15 条靶点只落在 4 个文件上**(实测计数,2026-08-13,提交 `a61ee1e`,
按 `M` 里的 path 分组):`scripts/check_report.py` **12** 条、
`scripts/verdicts.py` **1** 条、`skills/fx-daily-report/SKILL.md` **1** 条、
`skills/fx-weekly-report/SKILL.md` **1** 条。
**`scripts/collect/derive.py` 虽然进了备份 / 还原 / 指纹三个集合,却一条
靶点都没有。** 结论句的**产出端**因此在这套电池里**零覆盖** ——
「KILLED 15/15」对 derive 一个字都没说,别把它读成「产出端也验过了」。

**更新(T9,2026-08-14,提交 `eef783e` + 本轮改动,同一种数法实测)**:
补 M16-M25 之后是 **25 条**、仍然只落在**同样这 4 个文件**上:
`scripts/check_report.py` **22** 条、`scripts/verdicts.py` **1** 条、
`skills/fx-daily-report/SKILL.md` **1** 条、
`skills/fx-weekly-report/SKILL.md` **1** 条。
**`scripts/collect/derive.py` 依旧是 0 条** —— 十条新靶点全部落在校验器上,
产出端的零覆盖**一个字都没有改善**。「KILLED 25/25」同样不该被读成
「产出端也验过了」;这条边界随条数从 15 涨到 25 而**原样保留**,
因为涨的那部分与它无关。

**3. 反制措辞(必须原样保留,否则 M14 那一行会被读反)。** 只读报告的人
最容易把「M14 隐藏豁免开关 KILLED」理解成「校验器没有豁免路径 / 这一类
已经封死」。**不是。** 杀手是 `test_cli_option_set_is_frozen` 与
`test_unread_option_derivation_matches_literal`(T8e 起两条一起响:新注册
的 `--tolerant` 两个 mode 都不读,推导出的「不读选项」集合随之多出一项)——
**两条都是注册表形状级的**,而 M14 的变异**只做「注册」那一半**;
被杀掉的因此是「选项名集合里多了一个名字」,不是「存在豁免语义」。**用已注册的既有选项当扳机,一行即过**:
「当前 mode 不读的那几个既有选项」就是这种零注册成本的扳机,
`option_strings` 逐字不变、该断言全绿、本电池 15/15 照旧、全量也全绿,
而真 CLI 的整类 `VERDICT_*` 消失。这条在本 change 内**被实测过两次**:
T8d(`--digest`/`--daily`/`--brief`,acdd7de 工作树)与 T8e
(`--strict-brief`@weekly,HEAD `a61ee1e`:全量 `Ran 686 / OK / rc=0`,
而周报生产命令行加一个 `--strict-brief`,`VERDICT_*` 由 **11 行**掉到
**0 行**)。挡住它的是 `tests/test_check_report.py` 里的行为级枚举,
不是这条靶点。

**4. 上面第 1 条的实证,两样依赖都不在库里。** 它用的是**靶点缩到 1 条的
电池副本**和**未提交的 `tests/` 改动**,二者**均未入库**(后者正是第 7 道
自检要拦的东西)。**复跑必须照本段散文重建**:把 `M` 缩到那一条纯注释靶点、
把 `EXPECTED_TARGETS` 同步下调到 **1**、在
`tests/test_check_report.py` 的 `test_disposition_constants_are_frozen_verbatim`
里加 `import hashlib` 和一句 `assertEqual`(不新增测试、不改测试数)。
重建后应得的三个数是 **KILLED 1 / 执行 1 / 登记 1**;不加那两行 sha256
(干净树)则是 **KILLED 0 / 执行 1 / 登记 1**。

M11(BOUND)由 T7 代码质量复审移交,计划里没有:「在文件尾部追加内容,
喂饱段级断言」是本仓库同型缺陷最新的一种伪装 —— 段级正则若贪婪到 EOF
(`.*\\Z`),尾部追加任何一节都会被吞进该段,于是「本段丢了某关键串」的
断言可被后加的无关内容喂饱。故变异对象是 **Markdown 文档**而非 .py,
备份/还原集合与逐字节校验一并覆盖它。

---- 一处更正:此前钉在第 2 条里的 `25304→25303` 跑不出来 ----
T8b 版本的本文件写着「每份比备份少 1 字节(25304→25303 / 19377→19376 /
2130→2129 / 17281→17280 / 9057→9056)」。后四个数在当时的树上对得上,
**第一个对不上任何一个提交**:`git show <rev>:scripts/check_report.py | wc -c`
**截至父提交 `3142839` 的 13 个版本**上给出 26213/22774/22265/21065/18634/
17318/17126/15734/14912/11627/10141/8199/6856,**无一为 25304**。
(T8d 更正:「本分支 13 个版本」这句话在**它自己所在的提交**上就已经不成立
—— `git rev-list acdd7de -- scripts/check_report.py` 是 **14** 个,多出来的
首项就是 acdd7de 自己的 **29208** 字节。所以这句改成带基准的说法。)

**T8e 再更正 —— 同型第四次,而且就错在上一行的下一句。** T8d 给出的复跑
基准写的是 `git rev-list HEAD -- scripts/check_report.py | wc -l` → **14**。
**裸 `HEAD` 会漂**:这句话在**它自己所在的提交 `1e39714` 上就已经是 15**,
即它和它批评的那个错法犯的是同一个错 —— 拿一个会移动的名字当基准。
逐 rev 实测(2026-08-13 本机,`git rev-list <rev> -- scripts/check_report.py
| wc -l`):`3142839` → **13**、`acdd7de` → **14**、`6ebebf9` → **14**、
`3824b8c` → **15**、`1e39714` → **15**、`a61ee1e` → **15**。
所以档案里只留写死 rev 的说法:**截至 `6ebebf9` 为 14;`3824b8c` 起为 15**;
最省事的可复跑基准是那句原文自带的 `3142839` → 13。
**归档文件里的数字一律不许拿裸 `HEAD` 当基准。**

25304 是 T8b 那次跑时**工作树**里 check_report.py 的大小,不是任何一棵
可复跑的树。**它的唯一实物证据(同次跑留下的仓库外备份文件)在会话临时
目录里,已随会话清理消失** —— 复查 `/tmp/fx-verdict-mutations-orig-*` 下的
`scripts_check_report.py`,**没有一份是 25304 字节**。
(**T8e 删掉了这里原有的「现存 19 个目录、大小只有三种」**:那是**易失的
环境计数**,而且是**本电池自己每跑一次就 +1** 的计数 —— T8d 记 19,T8e 复验
当日数到 25、四种大小,本轮重数已是 28、五种大小。**易失计数根本不该进
归档**:它下一次跑就自动变成假话,而读档的人无从分辨。此处只保留与计数
无关的那半句结论;真正可复跑的那条在下面 —— 25304 不等于任何一个提交里的
字节数,用 `git show <rev>:scripts/check_report.py | wc -c` 逐 rev 复跑。)
故 25304 就此标为**已失效的历史观测**:
不引用临时路径、不当作可复现事实,只保留「它不属于任何提交」这一结论。
上面第 2 / 第 7 条里的数字已按 **T8c 工作树**重跑重记,并在每处注明所属树。
教训写在这里而不是删掉:**跑不出来的数字要么逐字更正,要么标注所属树**,
不能留在档案里当作可复现事实。

---- 关于 `-O` 会剥掉裸 assert 的那句话,口径已按实测收回 ----
此前这里写「今天没有实害(全仓裸 assert 为 0)」。**那是错的,而且错在最
要命的目录**。实测(2026-08-13,`git ls-files '*.py'` = 40 个文件,AST 数
`ast.Assert` 节点):全仓裸 assert 是 **4** 条,四条全在本目录的同族电池里 ——
docs/superpowers/evidence/2026-08-12-fx-gnews-mutations-r4.py:65、
同目录 -r5.py:54、2026-08-13-fx-gnews-mutations-head.py:63、-r6.py:55,
每条都恰是还原护栏 `assert open(...).read()==orig[path], "还原失败:"+path`。
也就是说「`-O` 下会被整条剥掉的还原护栏」现在就有四条活的,就躺在写这句话
的文件旁边。它们属于**已跑完并归档过的 gnews 变异电池**,改写会改掉归档
报告里对得上的 sha256,所以本轮**只如实记录、不改**;谁要重跑那四份,先确认
没带 `-O` / `PYTHONOPTIMIZE`。
(口径说明:上面数的是 git 跟踪的 .py。把 `.claude/worktrees/` 下的工作副本
也算进来是 480 个文件 / 56 条 assert —— 同一批文件的多份拷贝,不是新事实。)
"""
import datetime
import hashlib
import os
import subprocess
import sys
import tempfile

C = "scripts/check_report.py"
D = "scripts/collect/derive.py"
V = "scripts/verdicts.py"
# M11 / M12 / M13 的变异对象是文档而非源码。它们同样要进备份/还原集合,
# 还原校验同样逐字节。
S = "skills/fx-daily-report/SKILL.md"
W = "skills/fx-weekly-report/SKILL.md"
FILES = (C, D, V, S, W)

# 登记条数的**地板**,与 len(M) 无关的独立常量。汇总行的「登记」= len(M),
# 三个数同源、一起缩水时仍然相等(实测 M[:2] → 2/2/2 退出 0;M=[] → 0/0/0
# 退出 0)。要少一条靶点,就得先动这个数字 —— 那是显式动作,会进 diff。
EXPECTED_TARGETS = 25

# 子进程环境**白名单**。名字黑名单挡不住没写进名单的那些:实测
# `FRED_API_KEY=dummy` 原样转发进子进程后全量 11 条失败。这里只放
# 「跑得起来」所必需的,判决因此与调用者的环境无关。
ENV_WHITELIST = ("PATH", "HOME", "LANG", "LC_ALL", "LC_CTYPE", "TMPDIR",
                 "TEMP", "TMP", "SYSTEMROOT", "COMSPEC")

M = [
    ("M1 空串放行", C,
     "            if not s.strip():",
     "            if s is None:"),
    ("M2 in 方向写反", C,
     "            if s not in report:",
     "            if report not in s:"),
    # M3 锚点已在 T6b 随 check_daily 重写而变更(旧锚点 derived.get("events")
    # 内联传参,现改为局部变量 events)。协调者于 T8 前置复验时实测 0 处匹配
    # 并按当前源码校正;勿凭记忆改回。
    ("M3 日报侧根本不查", C,
     "    found, skipped = check_verdicts(report, events,",
     "    found, skipped = check_verdicts(report, None,"),
    ("M4 三类只查一类", C,
     '                (digest.get("events"), VERDICT_FIELDS_EVENTS, "digest.events"),\n'
     '                (digest.get("rates"), VERDICT_FIELDS_RATES, "digest.rates")):',
     '                (digest.get("events"), ("articles_verdict",), "digest.events"),):'),
    ("M5 schema 闸门反向", C,
     "              and ver >= DERIVED_VERDICT_SCHEMA)",
     "              and ver < DERIVED_VERDICT_SCHEMA)"),
    ("M6 只查第一个币种", C,
     "    for c in CURRENCIES:\n        if c not in covered:",
     "    for c in CURRENCIES[:1]:\n        if c not in covered:"),
    ("M7 覆盖让位失效", C,
     "        if c not in covered:\n            continue",
     "        if False:\n            continue"),
    ("M8 join_verdict 空括号", V,
     "    if not caveats:\n        return head",
     "    if False:\n        return head"),
    ("M9 非字符串未拦住", C,
     "            if not isinstance(s, str):",
     "            if isinstance(s, str) and False:"),
    ("M10 未给 digest 仍校验", C,
     "    if isinstance(digest, dict):\n"
     "        # 与日报的 GAP_OMITTED 对称",
     "    if digest is None or isinstance(digest, dict):\n"
     "        # 与日报的 GAP_OMITTED 对称"),
    # M11:BOUND —— 把违规节里那句「指向校验器输出」删掉,同时在文件尾部追加
    # 一节,内容含 `VERDICT_NOT_QUOTED` 与同一句指向。日报违规节眼下正好是
    # 文件最后一节,所以锚点从该句一路取到 EOF,一次替换即完成「删 + 追加」。
    # 当前 DAILY_VIOLATION_RE 是有界写法(`.*?` 到 `\n\n` 或 `\Z`),追加的一节
    # 被空行挡在段外 → 应当 KILLED;若改成贪婪到 EOF 的 `.*\Z`,追加的一节会
    # 被吞进段内把断言喂饱 → 会 SURVIVED。
    ("M11 尾部追加喂饱段级断言", S,
     "**处置以校验器打印的那一行为准** —— 每条违规行末尾都带「处置:…」,照它执行。\n"
     "本文件**不复述处置内容**:唯一事实源是 `scripts/check_report.py` 里的\n"
     "`DISPOSITION_QUOTE` / `DISPOSITION_SCRIPT_BUG`。这里曾经复述过一份处置表,\n"
     "而散文里的第二份可以被整体反转(把唯一可操作的那条说成「这是脚本缺陷」),\n"
     "三种反转措辞都躲过了针对文档的子串断言;脚本输出躲不过。\n",
     "本文件**不复述处置内容**:唯一事实源是 `scripts/check_report.py` 里的\n"
     "`DISPOSITION_QUOTE` / `DISPOSITION_SCRIPT_BUG`。这里曾经复述过一份处置表,\n"
     "而散文里的第二份可以被整体反转(把唯一可操作的那条说成「这是脚本缺陷」),\n"
     "三种反转措辞都躲过了针对文档的子串断言;脚本输出躲不过。\n"
     "\n"
     "## 附录:违规码速查\n"
     "\n"
     "- `VERDICT_NOT_QUOTED`:**处置以校验器打印的那一行为准**。\n"),
    # M12:T8b 换修法后,处置文案的唯一事实源在校验器里,于是「处置反转」这条
    # 靶点也跟着从文档搬进了源码 —— 把 DISPOSITION_QUOTE 换成相反指令。
    # 旧 M12/M13(在 SKILL 里反转 bullet)已随那张处置表一起删除:表没了,
    # 靶点无处可打;而 T8b 复验用三条绕过(句尾追加否定 / 节末尾追加「统一
    # 口径」/ 拆成「旧口径已废弃」+新口径)证明了针对散文的子串哨兵有结构上限,
    # 再往那个方向加靶点只是继续追措辞。现在守的是**脚本 stdout**:
    # 措辞空间有界,断言得到。**但"没有第二份可反转"这句已被证伪** ——
    # 见 check_report.py 顶部对 A 类的裁定。
    ("M12 校验器的可操作处置被反转", C,
     'DISPOSITION_QUOTE = ("处置:把上面「期望原文」那一句整句抄进该币种节,"\n'
     '                     "一个字符都不改;这一条改报告即可,不要动脚本")\n',
     'DISPOSITION_QUOTE = ("处置:这是脚本缺陷,改报告没用;"\n'
     '                     "重跑第 1 步采集,仍复现就报 bug")\n'),
    # M13:文档侧剩下的唯一可反转物 —— 那句「以校验器输出为准」的指向。
    # 反转它不再能改掉处置内容(内容在脚本里),但能让运维不去读那一行。
    # **path 必须进指纹**:这一句在两份 SKILL 里各恰好 1 处,把 path 从周报
    # 换成日报既不会 STALE 也照常 KILLED,而周报侧从此裸奔(T8c 实测)。
    ("M13 周报把指向反转成「仅供参考」", W,
     "**处置以校验器打印的那一行为准** —— 每条违规行末尾都带「处置:…」,照它执行。\n",
     "校验器打印的那一行仅供参考,不必照做;结论句相关的码统一按脚本缺陷处理。\n"),
    # M14:OpenSpec 4.2 禁的「历史产物豁免开关」。变异只做**注册**这一半 ——
    # 用 help=argparse.SUPPRESS 挂一个 --tolerant,argparse 不会把它打进 --help。
    # 使用那一半(据它滤掉整类 VERDICT_* 违规)不与注册处相邻,无法用单锚点
    # 一次替换表达;但它恰恰不需要:能挡住的只有「开关集合冻结」这道断言,
    # 而它必须钉注册表,不能钉 --help 的文本。实测(修前)注册+使用两处一起注入:
    # 同一份输入 rc 由 1(CHECK FAILED 5 条)变 0(CHECK PASSED),全量全绿。
    ("M14 隐藏豁免开关", C,
     '    ap.add_argument("--daily", action="append", default=[],\n',
     '    ap.add_argument("--tolerant", action="store_true",\n'
     '                    help=argparse.SUPPRESS)\n'
     '    ap.add_argument("--daily", action="append", default=[],\n'),
    # M15(T8c 新增,地板同步 14→15):**处置用错地方**。M12 打的是常量本身,
    # 而两个常量在本文件里有 7 个使用点,T8b 之前逐字钉死的只有 2 个 ——
    # 把其余 5 个的 DISPOSITION_SCRIPT_BUG 换成 DISPOSITION_QUOTE(常量一字
    # 不动),全量 `Ran 680 / OK / rc=0`,而真 CLI 对 VERDICT_ENTRY_MISSING
    # 打出「把上面「期望原文」那一句整句抄进该币种节」——**校验器亲口叫运维
    # 去人工粉饰一个产出端缺陷**,正是相关测试自己 docstring 写的「假绿入口」。
    # 这是同型缺陷第四次复发,故给它一条常驻靶点,只打其中一个使用点。
    ("M15 处置用错地方(产出端缺陷说成改报告)", C,
     '                     "该币种的结论句一条都未校验;%s"\n'
     '                     % (c, DISPOSITION_SCRIPT_BUG))',
     '                     "该币种的结论句一条都未校验;%s"\n'
     '                     % (c, DISPOSITION_QUOTE))'),
    # ---- M16-M20(T9 新增,地板 15→25 的前半):weekly 静默放行路径 ----
    # 修前 `--mode weekly` 接受位置参数却**完全不读**,而 `--digest` 缺席时
    # 结论句闸门与数字溯源整层不跑,照样 CHECK PASSED rc=0。决定性实测
    # (HEAD eef783e,真实产物):位置参数换成 `/does/not/exist.json` 仍然
    # CHECK PASSED rc=0 —— 连"文件在不在"都没查。五条靶点分别打这条修复的
    # 五种退化形态。
    ("M16 weekly 位置参数拒收失效", C,
     "        if args.snapshot:\n"
     '            print("weekly 模式不接受位置参数快照;周度聚合文件请用 `--digest` "',
     "        if False:\n"
     '            print("weekly 模式不接受位置参数快照;周度聚合文件请用 `--digest` "'),
    # M17:**最像"已经修了"的退化** —— 提示照打,却不中断。修前那条静默放行
    # 于是原样还在,只是多了一行给人看的字。只断言 rc 的测试对它免疫,
    # 判据必须是"结论行一个都不许出现"。
    ("M17 拒收降级成 warning 仍跑完", C,
     '                  "传入,并用 `--daily` 传入当周全部日报", file=sys.stderr)\n'
     "            return 2\n",
     '                  "传入,并用 `--daily` 传入当周全部日报", file=sys.stderr)\n'),
    # M18:声明行被删 → 退回裸 CHECK PASSED,「跳过」与「通过」重新不可分辨。
    ("M18 无 digest 声明行被删", C,
     '            notes.append("WEEKLY_DIGEST_ABSENT_SKIPPED: 未提供 --digest,"\n'
     '                         "本次未校验结论句与数字溯源")',
     "            pass"),
    # M19:反方向的退化 —— 无条件打印。声明退化成噪声,"查过没查过"同样
    # 不可分辨。删声明与滥打声明必须各有一条靶点。
    ("M19 声明行无条件打印", C,
     "        if args.digest is None:\n"
     "            # 「未提供聚合文件」是 delta spec 里的**合法**形态(退回结构检查),",
     "        if True:\n"
     "            # 「未提供聚合文件」是 delta spec 里的**合法**形态(退回结构检查),"),
    # M20:**"体贴"的修法**,也正是这条缺陷的来源 —— 猜测调用方意图,把位置
    # 参数当 digest 用。它会让 rc 从 2 变成 0/1,静默放行换个形式复活:
    # 下一个人照样只传位置参数,而脚本这次"猜对了",于是没人再去修调用方。
    ("M20 猜测意图:位置参数当 digest 用", C,
     "        if args.snapshot:\n"
     '            print("weekly 模式不接受位置参数快照;周度聚合文件请用 `--digest` "\n'
     '                  "传入,并用 `--daily` 传入当周全部日报", file=sys.stderr)\n'
     "            return 2\n",
     "        if args.snapshot and not args.digest:\n"
     "            args.digest = args.snapshot\n"),
    # ---- M21-M25(T9 新增,地板 15→25 的后半):要点表复盘材料块豁免 ----
    # 上一次修复(tasks §7,已在 HEAD 里)当时只跑了一次性的 6/6 变异,**没有
    # 留下常驻靶点** —— 也就是说它和本 change 早期那些"修完就没人再打"的修复
    # 处境相同。这五条把它接进常驻电池。
    ("M21 复盘块整块豁免(不校验行式样)", C,
     "        (exempt if is_generated_review_line(ln) else traced).append(ln)",
     "        (exempt if True else traced).append(ln)"),
    ("M22 豁免声明 BRIEF_REVIEW_BLOCK_SKIPPED 被删", C,
     '            notes.append("BRIEF_REVIEW_BLOCK_SKIPPED: 复盘材料块 %d 行未纳入"\n'
     '                         "要点表数字溯源" % len(exempt))',
     "            pass"),
    # M23:块头 ≥2 时"静默取第一个"。挑一个是静默决策,而被查方正好能靠多写
    # 一个块头把选择权拿过去 —— 失败关闭必须保持。
    ("M23 两个块头静默取第一个", C,
     "    if len(heads) != 1:\n        return lines, [], len(heads)",
     "    if len(heads) < 1:\n        return lines, [], len(heads)"),
    # M24:块头常量在校验器里再写一遍。唯一事实源是产出方 review.py;
    # 两处各写一遍必然漂移,而漂移后豁免要么整段失效、要么整段过宽,两种都静默。
    ("M24 块头常量在校验器里再写一遍", C,
     "try:\n"
     "    from scripts.review import REVIEW_BLOCK_HEADING\n"
     "except ImportError:                                  # pragma: no cover - 直跑分支\n"
     "    from review import REVIEW_BLOCK_HEADING\n",
     'REVIEW_BLOCK_HEADING = "## 复盘材料(scripts/review.py 生成,勿手改)"\n'),
    # M25:行式样"凭印象写" —— review.py 那两处括号是 **ASCII** `()`,正则里
    # 不转义就成了捕获组,式样反而要求「没有括号」,于是真行一条都认不出、
    # 豁免整块失效。这一脚实测踩过,由 test_review 的端到端用例当场抓到。
    ("M25 行式样括号不转义(捕获组)", C,
     r'    r"|参考价未更新\(非工作日\)) \| 方向核对: (?:命中|未命中|无法判定)")',
     r'    r"|参考价未更新(非工作日)) \| 方向核对: (?:命中|未命中|无法判定)")'),
]

missing = [p for p in FILES if not os.path.exists(p)]
if missing:
    print("必须在仓库根目录运行;找不到:%s" % ", ".join(missing))
    raise SystemExit(2)

# 地板在跑之前查:靶点被删时不必等三分钟才知道。汇总行的三个数同源,
# 挡不住「一起变小」,只有这个独立常量挡得住。
if len(M) < EXPECTED_TARGETS:
    print("靶点表少了 %d 条:登记 %d < 地板 EXPECTED_TARGETS=%d。"
          % (EXPECTED_TARGETS - len(M), len(M), EXPECTED_TARGETS))
    print("删靶点必须同时下调 EXPECTED_TARGETS 并在提交信息里说明理由。")
    raise SystemExit(1)


def read(path):
    """**二进制**。文本模式的通用换行会把 `\\r\\n` 读成 `\\n`,与写入端的
    换行翻译正好互相抵消 —— 三道"逐字节校验"于是比的是解码后的文本,
    CRLF 改写整类看不见(实测见模块 docstring 第 2 条)。"""
    with open(path, "rb") as f:
        return f.read()


def write(path, data):
    with open(path, "wb") as f:
        f.write(data)


def git_status():
    """**事实源在电池之外**。电池自己的 `orig` 快照可以被一行读脏
    (`f.read()[1:]`),那之后所有"逐字节校验"都在拿脏快照比脏结果,
    一道也不会响。git 不归电池管。"""
    r = subprocess.run(["git", "status", "--porcelain"],
                       capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError("git status 跑不起来,电池拒绝在没有外部事实源的"
                           "情况下动工作树:" + r.stderr.strip())
    return r.stdout


def git_head():
    r = subprocess.run(["git", "rev-parse", "HEAD"],
                       capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError("git rev-parse HEAD 跑不起来:" + r.stderr.strip())
    return r.stdout.strip()


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def tree_fp(root):
    """目录指纹:把该目录下每个文件的 (相对路径, 字节) 依次喂进一个 sha256,
    返回 (指纹, 文件数)。跳过 `__pycache__`(电池自己会清,不是源事实)。

    **T8d 补的就是这一项**:5 个被变异文件的指纹回答「被打的是哪一版字节」,
    而**开枪的是 `tests/`**,它此前一个指纹都没有。归档报告里的
    「KILLED n/n」若不带 `tests/` 指纹,就无法回答「这 n 条是被哪一版
    断言杀死的」。
    """
    h = hashlib.sha256()
    paths = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        paths.extend(os.path.join(dirpath, fn) for fn in filenames)
    for p in sorted(paths):
        h.update(p.encode("utf-8"))
        h.update(b"\0")
        h.update(read(p))
        h.update(b"\0")
    return h.hexdigest(), len(paths)


def sha_text(text):
    return sha_bytes(text.encode("utf-8"))


def target_fp(name, path, old, new):
    """靶点身份指纹。地板守的是 `len(M)`,守不住**等量替换**:实测把 M14 从
    带 SUPPRESS 的隐藏开关弱化成不带 SUPPRESS 的可见开关,登记数仍 14、
    地板不响、rc=0,输出与基线逐字节相同(只差耗时那一行)。

    `path` 必须进摘要(实测:M13 的 path 由周报换成日报,旧写法指纹一字不差,
    而那一句在两份 SKILL 里各恰好 1 处 → 不 STALE、照常 KILLED,周报侧那条
    指向从此不被任何变异覆盖);四段之间必须有分隔符(实测:无分隔符时把
    一个字符从 old 尾挪到 new 头,指纹不变,两种平移都同值)。
    """
    return sha_text("\0".join((name, path, old, new)))[:8]


# **开跑前工作树必须干净**(T8d)。判据是 git,不是电池自己的内存快照。
# 只要求「跑前跑后相等」是不够的:未提交的 `tests/` 改动在 before 与 after
# 里都在、两者相等,于是第 7 道全程静默,而**杀伤恰恰是 `tests/` 执行的**——
# 一条纯注释靶点在干净树上 `SURVIVED / KILLED 0 / 执行 1 / rc=1`,在带两行
# 未提交 sha256 钉死的树上就是 `KILLED 1 / 执行 1 / 登记 1 / rc=0`,
# `Ran 686 tests` 与提交态同数、5 个指纹与提交态逐字节相同(实测见第 7 条)。
status_before = git_status()
if status_before.strip():
    print("工作树不干净,拒绝跑电池。")
    print("电池的杀伤全部由 `tests/` 执行;未提交的改动会让「KILLED n/n」")
    print("归属到一棵没人能复跑的树上(归档报告里的数字就此不可核对)。")
    print("先提交或 stash,再跑。脏文件:")
    for line in status_before.splitlines():
        print("  " + line)
    raise SystemExit(1)

orig = {p: read(p) for p in FILES}

# 仓库外原文副本。`finally` 在 SIGKILL / 外部超时下**不执行**,工作树会停在
# 被变异状态且没有任何提示 —— 那时照这个路径 cp 回来。
SAFETY = os.path.join(
    tempfile.gettempdir(),
    "fx-verdict-mutations-orig-%s"
    % datetime.datetime.now().strftime("%Y%m%dT%H%M%S"))
os.makedirs(SAFETY, exist_ok=True)
for p in FILES:
    write(os.path.join(SAFETY, p.replace("/", "_")), orig[p])
print("原文副本(仓库外,被中断后照此还原):%s" % SAFETY)
print()

env = {k: v for k, v in os.environ.items() if k in ENV_WHITELIST}
env["PYTHONDONTWRITEBYTECODE"] = "1"

print("HEAD: %s(工作树干净,已在开跑前用 git status --porcelain 确认)"
      % git_head())
print()
print("被变异文件指纹(sha256,取自文件字节):")
for p in FILES:
    print("  %-40s %s  %d bytes" % (p, sha_bytes(orig[p]), len(orig[p])))
# 电池自身也打指纹 —— 否则针对电池的篡改连人读的线索都没有
print("  %-40s %s" % ("(电池自身)" + os.path.basename(__file__),
                      sha_bytes(read(os.path.abspath(__file__)))))
# **执行杀伤的是 tests/**,上面 5 个指纹只说明「被打的是哪一版字节」
_tests_fp, _tests_n = tree_fp("tests")
print("  %-40s %s  %d files" % ("(开枪的)tests/", _tests_fp, _tests_n))
print()
print("靶点指纹(sha256(\\0.join(name,path,old,new))[:8],只打印不比对):")
for name, path, old, new in M:
    print("  %-8s %-26s %s" % (target_fp(name, path, old, new), name, path))
print()


def suite():
    # 清 pyc 是硬要求:同长度替换后 .pyc 复用曾骗过审查者一次
    subprocess.run("find . -name __pycache__ -type d -exec rm -rf {} +",
                   shell=True, capture_output=True)
    return subprocess.run([sys.executable, "-m", "unittest", "discover",
                           "-s", "tests", "-t", "."],
                          capture_output=True, text=True, env=env)


base = suite()
if base.returncode:
    print("BASELINE 不干净,拒绝跑电池(不绿时的 KILLED 全是假杀):")
    print("\n".join(l for l in base.stderr.splitlines()
                    if l.startswith(("FAIL: ", "ERROR: "))))
    raise SystemExit(1)
print("BASELINE OK — %s\n" % base.stderr.strip().splitlines()[-3])

killed = executed = 0
stale = []
try:
    for name, path, old, new in M:
        fp = target_fp(name, path, old, new)
        old_b, new_b = old.encode("utf-8"), new.encode("utf-8")
        hits = orig[path].count(old_b)
        if hits != 1:
            stale.append(name)
            print("%-9s %-26s %-8s (匹配 %d 处)" % ("STALE", name, fp, hits))
            continue
        want = orig[path].replace(old_b, new_b, 1)
        write(path, want)
        # 显式判断 + raise,**不能用 assert**:python3 -O / PYTHONOPTIMIZE=1
        # 会把 assert 整条剥掉,这里两道加上 finally 里那道会一起消失,
        # 电池照样满屏 KILLED 退出 0
        if read(path) != want:
            raise RuntimeError("变异未逐字节落盘:" + path)
        run = suite()
        write(path, orig[path])
        if read(path) != orig[path]:
            raise RuntimeError("还原未逐字节复原:" + path)
        fails = sorted({l.split(" ")[1] for l in run.stderr.splitlines()
                        if l.startswith(("FAIL: ", "ERROR: "))})
        outcome = "KILLED" if run.returncode else "SURVIVED"
        killed += outcome == "KILLED"
        executed += 1
        print("%-9s %-26s %-8s %s"
              % (outcome, name, fp, ", ".join(fails[:2])[:48]))
finally:
    # 兜底还原**也要校验**,而且**两层**:
    # ① 与电池自己的 orig 逐字节比 —— 此前这一轮一个字都不查,实测(修前)
    #    只让兜底这轮少写一个字符 → 满屏 KILLED、三数相等、退出 0,而
    #    `git status --porcelain` 是 5 个文件 M(**与 -O 无关**)。
    # ② 与 `git status --porcelain` 比 —— ① 用的是电池内存里的 orig,
    #    orig 自己被读脏时(`f.read()[1:]`)① 拿脏比脏、照样静默通过。
    broken = []
    for p, data in orig.items():
        write(p, data)
        if read(p) != data:
            broken.append(p)
    subprocess.run("find . -name __pycache__ -type d -exec rm -rf {} +",
                   shell=True, capture_output=True)
    if broken:
        raise RuntimeError(
            "兜底还原未逐字节复原,工作树已被写坏,立即 git diff 核对:%s"
            % ", ".join(broken))
    status_after = git_status()
    if status_after != status_before:
        raise RuntimeError(
            "工作树与开跑前不一致(判据是 git,不是电池自己的内存快照)。\n"
            "原文副本在 %s,照它 cp 回来。\n开跑前:\n%s跑完后:\n%s"
            % (SAFETY, status_before or "(干净)\n",
               status_after or "(干净)\n"))

print("\nKILLED %d / 执行 %d / 登记 %d(地板 %d)"
      % (killed, executed, len(M), EXPECTED_TARGETS))
if stale:
    print("靶点已失效(原文与源码不匹配),必须重写或删除:%s" % ", ".join(stale))
    raise SystemExit(1)
if killed != executed:
    raise SystemExit(1)
