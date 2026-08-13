"""第五轮修复的变异电池。跑前验基线全绿,每条还原后逐字比对(见 design §10.6)。"""
import subprocess, sys, os
E="scripts/collect/events.py"; D="scripts/collect/derive.py"; W="scripts/weekly_digest.py"
M=[
 ("M72 全丢时不记 gap", E, '        if dropped > 0 and not arts:', '        if False:'),
 ("M73 部分丢弃也记 gap", E, '        if dropped > 0 and not arts:', '        if dropped > 0:'),
 ("M74 derive 不读 dropped_malformed", D,
  '                "dropped_malformed": _dropped_malformed(payload, currency),', ''),
 ("M75 存量快照缺此账当成 0", W,
  "        elif isinstance(entry, dict):", "        elif False:"),
 ("M76 未触顶日的上限也进结论句", W,
  "                caps.add(own_cap)          # 条目自带上限即权威值\n                if flag:\n                    capped_caps.add(own_cap)",
  "                caps.add(own_cap)\n                capped_caps.add(own_cap)"),
 ("M77 结论句改用 daily_cap", W,
  '                          _cap_phrase(stats.get("capped_cap", stats["daily_cap"]))))',
  '                          _cap_phrase(stats["daily_cap"])))'),
 ("M78 sample 不再排除已披露的截断", W,
  "                and flag is not True:", "                and True:"),
 ("M79 GDELT count_at_cap 恒 False", E,
  '            "count_at_cap": known and raw_count >= MAX_RECORDS,', '            "count_at_cap": False,'),
 ("M80 gnews count_at_cap 边界 > ", E,
  '            "count_at_cap": (kept >= GNEWS_SOFT_CAP) if kept_known else None,',
  '            "count_at_cap": (kept > GNEWS_SOFT_CAP) if kept_known else None,'),
 ("M81 malformed 天数改 >= 0", W, "            if bad > 0:", "            if bad >= 0:"),
 ("M82 gnews dropped_malformed 恒 None", E,
  '            "articles_dropped_malformed": 0 if articles is not None else None,',
  '            "articles_dropped_malformed": None,'),
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
