"""第四轮修复的变异电池。跑前验基线全绿,每条还原后逐字比对(见 design §10.6)。"""
import subprocess, sys, os
E="scripts/collect/events.py"; D="scripts/collect/derive.py"; W="scripts/weekly_digest.py"
M=[
 ("M52 采集层丢弃量不落盘", E,
  '            "articles_dropped_malformed": dropped,', '            "articles_dropped_malformed": 0,'),
 ("M53 _fetch 不数丢弃量", E,
  "            dropped += 1        # 非 dict 元素 → 跳过,但要计入原始条数", "            pass"),
 ("M54 聚合器不累加丢弃量", W,
  "            malformed_days += 1\n            malformed_items += bad", "            pass"),
 ("M55 落盘后畸形条目不单列", W,
  "                malformed += 1\n                continue", "                continue"),
 ("M56 dup_dropped 仍把丢弃当重复", W,
  '        "dup_dropped": (sampled - malformed - distinct) if got else None,',
  '        "dup_dropped": (sampled - distinct) if got else None,'),
 ("M57 capped 退回读 source_capped", W,
  '        flag = entry.get("count_at_cap") if isinstance(entry, dict) else None\n        if not isinstance(flag, bool) and isinstance(entry, dict):\n            flag = entry.get("source_capped")   # 存量快照只产自不过滤的 GDELT',
  '        flag = entry.get("source_capped") if isinstance(entry, dict) else None'),
 ("M58 sample 两个来源分别累加", W,
  '        if own_flag is True or (isinstance(gf, dict) and gf.get("capped") is True):\n            sample_capped += 1',
  '        if own_flag is True:\n            sample_capped += 1\n        if isinstance(gf, dict) and gf.get("capped") is True:\n            sample_capped += 1\n        if own_flag is None:\n            sample_capped += 1'),
 ("M59 derive 不读 count_at_cap", D,
  '    authoritative = entry.get("count_at_cap")\n    if isinstance(authoritative, bool):\n        return authoritative\n', ""),
 ("M60 gnews count_at_cap 用 raw 而非 kept", E,
  '            "count_at_cap": (kept >= GNEWS_SOFT_CAP) if kept_known else None,',
  '            "count_at_cap": (raw_count >= GNEWS_SOFT_CAP) if known else None,'),
 ("M61 _sample_capped 只读 gnews_filter", D,
  '    flags = []\n    own = entry.get("source_capped")\n    if isinstance(own, bool):\n        flags.append(own)\n', "    flags = []\n"),
 ("M62 主通道上限推定并回 cap_assumed", W,
  "            sample_assumed += 1 if m_assumed else 0", "            assumed += 1 if m_assumed else 0"),
 ("M63 blank 分支判据放宽", W, "        if blank == n_days:", "        if blank > 0:"),
 ("M64 仍有条目天数写成总天数", W,
  '                           "当日仍有条目可用)" % (n_days, n_items, n_days - blank))',
  '                           "当日仍有条目可用)" % (n_days, n_items, n_days))'),
 ("M65 窗口 caveat 只在 in_window==0 出", W,
  '    if stats["outside_window"]:', '    if stats["outside_window"] and not stats["in_window"]:'),
 ("M66 sample_capped 不进 derive 输出", D,
  '                "sample_capped": _sample_capped(payload, currency),', ""),
]
orig={p:open(p,encoding="utf-8").read() for p in (E,D,W)}
env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"); k=0; n=0; stale=[]

def suite():
    subprocess.run("find . -name __pycache__ -type d -exec rm -rf {} +",shell=True,capture_output=True)
    return subprocess.run([sys.executable,"-m","unittest","discover","-s","tests","-t","."],
                          capture_output=True,text=True,env=env)

b=suite()
if b.returncode:
    print("BASELINE 不干净,拒绝跑电池:")
    print("\n".join(l for l in b.stderr.splitlines() if l.startswith(("FAIL: ","ERROR: "))))
    raise SystemExit(1)
print("BASELINE OK\n")
try:
    for name,path,old,new in M:
        c=orig[path].count(old)
        if c!=1:
            # 靶点原文已被后续轮次改写 → **硬失败**。只打印一行继续,会让
            # "全部 KILLED"在干净副本上根本复现不出来,而退出码仍是 0
            stale.append(name)
            print("%-9s %-34s (匹配 %d 处)"%("STALE",name,c)); continue
        open(path,"w",encoding="utf-8").write(orig[path].replace(old,new,1))
        p=suite()
        open(path,"w",encoding="utf-8").write(orig[path])
        assert open(path,encoding="utf-8").read()==orig[path], "还原失败:"+path
        fails=sorted({l.split(" ")[1] for l in p.stderr.splitlines() if l.startswith(("FAIL: ","ERROR: "))})
        v="KILLED" if p.returncode else "SURVIVED"; k+= v=="KILLED"; n+=1
        print("%-9s %-34s %s"%(v,name,", ".join(fails[:2])[:58]))
finally:
    for p_,s_ in orig.items(): open(p_,"w",encoding="utf-8").write(s_)
    subprocess.run("find . -name __pycache__ -type d -exec rm -rf {} +",shell=True,capture_output=True)
print("\n本轮 KILLED %d / 执行 %d / 登记 %d"%(k,n,len(M)))
if stale:
    print("靶点已失效(原文被后续轮次改写),须重写或删除:%s"%", ".join(stale))
    raise SystemExit(1)
if k!=n:
    raise SystemExit(1)
