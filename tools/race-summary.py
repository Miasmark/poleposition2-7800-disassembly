import re,sys
for fn in sys.argv[1:]:
    print("==",fn.split("/")[-1]); last=None
    for ln in open(fn):
        if not ln.startswith("V "): continue
        d=dict(re.findall(r"(\w+)=(\S+)",ln)); f=int(ln.split()[1][1:])
        if f<5400: continue
        clk0 = d["clock"]=="00"
        k=(d["st"],d["park"],d["rst"],clk0,d["p2lapn"],d["A7"])
        if k!=last:
            print(f"f{f} st={d['st']} A7={d['A7']} clk={d['clock']} p1lap={d['p1lap']} | p2lapn={d['p2lapn']} p2clk={d['p2clk']} rst={d['rst']} park={d['park']} s1={d['p1score']} s2={d['p2score']}")
        last=k
