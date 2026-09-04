import pandas as pd, numpy as np, os
ROOT="/Users/gongzhao/code/misc"
SRC = {
 "H0002 A股低波+反转":  ["astock_quant/verified/oos_returns.csv"],
 "H0003 资金费收割":     ["crypto_perp/ret_V0.csv"],
 "H0010 AH溢价":        ["quant_research/hk_stock/out/returns_long_only.csv"],
 "H0014 FOMC日":        ["us_stock/ret_w1.csv"],
 "H0019 南向资金流":     ["hk_southbound/out/h19_ret_trainvalid.csv","hk_southbound/out/h19_ret_test.csv"],
 "H0021 做空VIX":       ["quant_research/vol/data/qbt_v0_full.csv"],
 "H0022 A股质量":       ["quant_research/cn_stock/out/equity_primary.csv"],
 "H0024 A股小市值":     ["quant_research/cn_stock/out_h0024/equity_primary.csv"],
}
def load(paths):
    parts=[]
    for p in paths:
        f=os.path.join(ROOT,p)
        if not os.path.exists(f): return None, f"缺文件 {p}"
        d=pd.read_csv(f)
        col=[c for c in d.columns if c.lower() in ("ret","return","returns")]
        if not col: return None, f"{p} 没有 ret 列: {list(d.columns)}"
        d["date"]=pd.to_datetime(d[d.columns[0]], utc=True).dt.tz_localize(None).dt.normalize()
        parts.append(d.set_index("date")[col[0]].rename("ret"))
    s=pd.concat(parts).sort_index()
    return s[~s.index.duplicated(keep="last")], None

def stats(r, ppy=252):
    r=r.dropna()
    if len(r)<50: return None
    ann=r.mean()*ppy; vol=r.std()*np.sqrt(ppy)
    eq=(1+r).cumprod(); mdd=(eq/eq.cummax()-1).min()
    return dict(n=len(r), start=str(r.index[0].date()), end=str(r.index[-1].date()),
                ann=ann, vol=vol, sharpe=ann/vol if vol>0 else np.nan, mdd=mdd)

series={}
for name,paths in SRC.items():
    s,err=load(paths)
    if err: print(f"{name:22s} ❌ {err}"); continue
    ppy=365 if "资金费" in name else 252
    st=stats(s,ppy)
    series[name]=(s,ppy)
    print(f"{name:22s} {st['start']}~{st['end']} n={st['n']:5d} "
          f"年化{st['ann']*100:7.2f}% 波动{st['vol']*100:6.2f}% 夏普{st['sharpe']:6.2f} 回撤{st['mdd']*100:7.1f}%")
import pickle; pickle.dump({k:(v[0],v[1]) for k,v in series.items()}, open("/tmp/parks.pkl","wb"))
