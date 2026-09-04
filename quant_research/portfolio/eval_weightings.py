import pandas as pd, numpy as np, pickle
S=pickle.load(open("/tmp/parks.pkl","rb")); names=list(S)
R=pd.DataFrame({k:v[0] for k,v in S.items()}).loc["2019-09-10":].dropna(how="all").fillna(0.0)

def iv(R, lookback=252, cap=None):
    vol=R.rolling(lookback).std()
    w=(1/vol).replace([np.inf,-np.inf],np.nan)
    w=w.div(w.sum(axis=1),axis=0)
    if cap:
        for _ in range(50):                    # 迭代封顶再归一
            w=w.clip(upper=cap); w=w.div(w.sum(axis=1),axis=0)
    return w.groupby(R.index.to_period("M")).transform("first").shift(1)

def st(r,label,ppy=252):
    r=r.dropna(); ann=r.mean()*ppy; vol=r.std()*np.sqrt(ppy)
    eq=(1+r).cumprod(); mdd=(eq/eq.cummax()-1).min()
    return f"{label:34s} {ann*100:7.2f}% {vol*100:7.2f}% {ann/vol:7.2f} {mdd*100:8.1f}%"

W=iv(R)
print("=== 风险平价实际给了谁权重（全窗口均值）===")
for k,v in W.mean().sort_values(ascending=False).items(): print(f"  {k:22s} {v*100:5.1f}%")
eff=1/ (W.mean()**2).sum()
print(f"  → 有效持仓数 {eff:.2f}（名义 8 条腿）")

C=R.corr()
ev=np.linalg.eigvalsh(C.values); ev=ev/ev.sum()
print(f"  → 相关矩阵的有效独立赌注数 exp(熵) = {np.exp(-(ev*np.log(ev)).sum()):.2f} / 8")

print(f"\n{'':34s} {'年化':>8s} {'波动':>8s} {'夏普':>7s} {'最大回撤':>9s}")
print(st(R.mean(axis=1),"等权 8 条腿"))
print(st((R*iv(R)).sum(axis=1).dropna(),"风险平价（无上限）"))
for cap in (0.25,0.35,0.5):
    w=iv(R,cap=cap); print(st((R*w).sum(axis=1).dropna(), f"风险平价（单腿封顶 {int(cap*100)}%）"))
# 把高度相关的 A股/港股一族先合成一条腿，再和其余并列
cluster=["H0002 A股低波+反转","H0022 A股质量","H0024 A股小市值","H0010 AH溢价","H0019 南向资金流"]
G=pd.DataFrame({"股票族":R[cluster].mean(axis=1),
                "资金费":R["H0003 资金费收割"],
                "FOMC":R["H0014 FOMC日"],
                "空VIX":R["H0021 做空VIX"]})
print(st(G.mean(axis=1),"先聚类再等权（4 条独立腿）"))
print(st((G*iv(G)).sum(axis=1).dropna(),"先聚类再风险平价"))
print(st(R["H0003 资金费收割"],"（参照）只买 H0003 资金费一条腿",365))
