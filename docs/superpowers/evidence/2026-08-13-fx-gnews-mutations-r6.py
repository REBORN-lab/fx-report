"""第四轮修复的变异电池。跑前验基线全绿,每条还原后逐字比对(见 design §10.6)。"""
import subprocess, sys, os
E="scripts/collect/events.py"; D="scripts/collect/derive.py"; W="scripts/weekly_digest.py"
M=[
 ("M83 退回第五轮的合并抑制", W,
  "        if own_flag is True and flag is not True:",
  "        if (own_flag is True or (isinstance(gf, dict) and gf.get(\"capped\") is True)) and flag is not True:"),
 ("M84 own 分支丢掉抑制条件", W,
  "        if own_flag is True and flag is not True:", "        if own_flag is True:"),
 ("M85 主通道截断也被 flag 吞掉", W,
  '        if isinstance(gf, dict) and gf.get("capped") is True:\n            # 主通道那次截断**独立成立**',
  '        if isinstance(gf, dict) and gf.get("capped") is True and flag is not True:\n            # 主通道那次截断**独立成立**'),
 ("M86 count_at_cap 用 raw_count", E,
  '            "count_at_cap": len(arts) >= MAX_RECORDS,',
  '            "count_at_cap": known and raw_count >= MAX_RECORDS,'),
 ("M87 derive dropped_malformed 恒 None", D,
  "    n = entry.get(\"articles_dropped_malformed\")\n    return n if isinstance(n, int) and not isinstance(n, bool) else None",
  "    n = entry.get(\"articles_dropped_malformed\")\n    return None"),
 ("M88 derive 放行 bool", D,
  "    return n if isinstance(n, int) and not isinstance(n, bool) else None",
  "    return n if isinstance(n, int) else None"),
 ("M89 存量/official 分支不记上限", W,
  "                if n >= cap:\n                    capped_caps.add(cap)\n                    capped += 1",
  "                if n >= cap:\n                    capped += 1"),
 ("M90 条目自带上限不进结论句", W,
  "                if flag:\n                    capped_caps.add(own_cap)", "                if flag:\n                    pass"),
 ("M91 gap 判据丢掉 dropped>0", E,
  "        if dropped > 0 and not arts:", "        if not arts:"),
]
orig={p:open(p,encoding="utf-8").read() for p in (E,D,W)}
env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"); k=0

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
            print("%-9s %-34s (匹配 %d 处)"%("PATCH-FAIL",name,c)); continue
        open(path,"w",encoding="utf-8").write(orig[path].replace(old,new,1))
        p=suite()
        open(path,"w",encoding="utf-8").write(orig[path])
        assert open(path,encoding="utf-8").read()==orig[path], "还原失败:"+path
        fails=sorted({l.split(" ")[1] for l in p.stderr.splitlines() if l.startswith(("FAIL: ","ERROR: "))})
        v="KILLED" if p.returncode else "SURVIVED"; k+= v=="KILLED"
        print("%-9s %-34s %s"%(v,name,", ".join(fails[:2])[:58]))
finally:
    for p_,s_ in orig.items(): open(p_,"w",encoding="utf-8").write(s_)
    subprocess.run("find . -name __pycache__ -type d -exec rm -rf {} +",shell=True,capture_output=True)
print("\n本轮 KILLED %d / %d"%(k,len(M)))
