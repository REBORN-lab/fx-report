"""对应 HEAD 的变异电池:第七轮新靶点 + 前几轮仍成立者按当前代码重述。
前三份归档件里有 9 条靶点的原文已被后续轮次改写,在干净副本上会 STALE 并非零退出。"""
import subprocess, sys, os
E="scripts/collect/events.py"; D="scripts/collect/derive.py"; W="scripts/weekly_digest.py"
M=[
 # --- 第七轮修复 ---
 ("N1 count_at_cap 用去重前长度(GDELT)", E,
  '            "count_at_cap": len(landed) >= MAX_RECORDS,', '            "count_at_cap": len(arts) >= MAX_RECORDS,'),
 ("N2 count_at_cap 用 kept(gnews)", E,
  '            "count_at_cap": (landed >= GNEWS_SOFT_CAP) if landed is not None else None,',
  '            "count_at_cap": (counts.get("kept") >= GNEWS_SOFT_CAP) if isinstance(counts, dict) and isinstance(counts.get("kept"), int) else None,'),
 ("N3 主通道跑失败不记账", W,
  '        if isinstance(entry, dict) and "gnews_filter" in entry and gf is None:\n            main_failed_days += 1',
  '        if False:\n            main_failed_days += 1'),
 ("N4 有意停用被误记成跑失败", W,
  '        if isinstance(entry, dict) and "gnews_filter" in entry and gf is None:',
  '        if isinstance(entry, dict) and gf is None:'),
 ("N5 derive 不落 main_sample_capped", D,
  '                "main_sample_capped": _main_sample_capped(payload, currency),', ''),
 ("N6 main_sample_capped 按键在与否判", D,
  '    flag = gf.get("capped")\n    return flag if isinstance(flag, bool) else None\n\n\ndef _events_derived',
  '    return True\n\n\ndef _events_derived'),
 ("N7 不过滤通道仍说「滤除」", W,
  '已采到的条数是下界"', '滤除后的条数是下界"'),
 # --- 前几轮仍成立、按当前代码重述 ---
 ("N8 聚合器不累加丢弃量(原 M54)", W,
  "                malformed_days += 1\n                malformed_items += bad", "                pass"),
 ("N9 capped 退回读 source_capped(原 M57)", E,
  "    flag = entry.get(\"count_at_cap\")\n    if isinstance(flag, bool):\n        return flag\n", ""),
 ("N10 derive 不用共享谓词(原 M69)", D,
  "    return events_mod.landed_count_capped(entry, caps)",
  "    a = entry.get(\"source_capped\")\n    return a if isinstance(a, bool) else None"),
 ("N11 sample own 分支整支删除(原 S9)", W,
  "        if own_flag is True and flag is not True:", "        if False:"),
 ("N12 own 分支不记上限(原 M90)", W,
  "                today_caps.add(own_cap)", "                pass"),
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
