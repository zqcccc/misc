import pandas as pd, numpy as np, pickle, os
ROOT="/Users/gongzhao/code/misc"
S=pickle.load(open("/tmp/parks.pkl","rb"))
names=list(S)
df=pd.DataFrame({k:v[0] for k,v in S.items()})

# 统一到交易日：非交易日缺失按 0 收益处理（各腿自身的日历不同）
full=df.loc["2019-09-10":].copy()
full=full.dropna(how="all")
cov=full.notna().mean()
print("=== 各腿在合并窗口内的可用天数占比 ===")
for k,v in cov.items(): print(f"  {k:22s} {v*100:5.1f}%")
R=full.fillna(0.0)

print("\n=== 相关系数（重叠日，%） ===")
C=full.corr(min_periods=250)
print((C*100).round(0).fillna(0).astype(int).to_string())
off=C.where(~np.eye(len(C),dtype=bool)).stack()
print(f"\n平均两两相关 {off.mean()*100:.1f}%，最高 {off.max()*100:.1f}%（{off.idxmax()}）")

def stats(r, ppy=252, label=""):
    r=r.dropna()
    ann=r.mean()*ppy; vol=r.std()*np.sqrt(ppy)
    eq=(1+r).cumprod(); mdd=(eq/eq.cummax()-1).min()
    return dict(label=label, ann=ann, vol=vol, sharpe=ann/vol if vol else np.nan, mdd=mdd,
                calmar=ann/abs(mdd) if mdd else np.nan)

# 权重必须只用历史信息：252 日滚动波动率倒数，月末再平衡
def invvol_weights(R, lookback=252):
    vol=R.rolling(lookback).std()
    w=(1/vol).replace([np.inf,-np.inf],np.nan)
    w=w.where(R.notna().rolling(lookback).sum()>lookback*0.5)
    w=w.div(w.sum(axis=1),axis=0)
    month=R.index.to_period("M")
    w=w.groupby(month).transform("first")      # 月内不动
    return w.shift(1)                          # 用昨天为止的信息定今天的仓位

W=invvol_weights(R)
port_iv=(R*W).sum(axis=1).where(W.sum(axis=1)>0.99)
port_ew=R.mean(axis=1)

rows=[stats(R[c],365 if "资金费" in c else 252,c) for c in names]
rows.append(stats(port_ew,252,"◆ 等权组合"))
rows.append(stats(port_iv,252,"◆ 风险平价组合(PIT)"))

# 不含做空VIX 的版本：那条腿波动 70%、回撤 -92%，单独一条就能主导结果
noviх=[c for c in names if "VIX" not in c]
rows.append(stats(R[noviх].mean(axis=1),252,"◆ 等权(剔除做空VIX)"))
W2=invvol_weights(R[noviх]); p2=(R[noviх]*W2).sum(axis=1).where(W2.sum(axis=1)>0.99)
rows.append(stats(p2,252,"◆ 风险平价(剔除做空VIX)"))

spy=pd.read_csv(os.path.join(ROOT,"us_stock/data/spy_max.csv"))
spy["date"]=pd.to_datetime(spy[spy.columns[0]]).dt.normalize()
px=spy.set_index("date")["spy"]
spy_r=px.pct_change().reindex(R.index).fillna(0.0)
rows.append(stats(spy_r,252,"（对照）SPY 买入持有"))

print(f"\n=== 2019-09 ~ 2026-09 全窗口 ===")
print(f"{'':30s} {'年化':>8s} {'波动':>8s} {'夏普':>7s} {'最大回撤':>9s} {'年化/回撤':>9s}")
for r in rows:
    print(f"{r['label']:30s} {r['ann']*100:7.2f}% {r['vol']*100:7.2f}% {r['sharpe']:7.2f} {r['mdd']*100:8.1f}% {r['calmar']:9.2f}")

print("\n=== 2024-01 之后（多数卡的样本外段） ===")
R24=R.loc["2024-01-01":]; W24=invvol_weights(R).loc["2024-01-01":]
p24=(R24*W24).sum(axis=1).where(W24.sum(axis=1)>0.99)
rows24=[stats(R24[c],365 if "资金费" in c else 252,c) for c in names]
rows24.append(stats(p24,252,"◆ 风险平价组合(PIT)"))
W2b=invvol_weights(R[noviх]).loc["2024-01-01":]
rows24.append(stats((R24[noviх]*W2b).sum(axis=1).where(W2b.sum(axis=1)>0.99),252,"◆ 风险平价(剔除做空VIX)"))
rows24.append(stats(spy_r.loc["2024-01-01":],252,"（对照）SPY 买入持有"))
for r in rows24:
    print(f"{r['label']:30s} {r['ann']*100:7.2f}% {r['vol']*100:7.2f}% {r['sharpe']:7.2f} {r['mdd']*100:8.1f}% {r['calmar']:9.2f}")

b=np.polyfit(spy_r.reindex(port_iv.dropna().index).fillna(0), port_iv.dropna(), 1)[0]
print(f"\n风险平价组合对 SPY 的 beta：{b:.2f}")
