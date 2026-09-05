"""Offline data audit; never builds strategy returns or overwrites market caches.
Run with repository .venv/bin/python. Outputs are diagnostic, not verdicts.
"""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
AQ = ROOT / 'astock_quant'
S, E = '2017-01-03', '2026-09-04'
sources = {}

def read(path):
    sources[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    d = pd.read_csv(path).drop_duplicates('date').set_index('date').sort_index()
    return d

def native(path, key):
    sources[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    rows = json.loads(path.read_text())['data']['sh601398'][key]
    return pd.DataFrame([r[:6] for r in rows], columns=['date','open','close','high','low','volume']).set_index('date').astype(float)

out = {'purpose':'B0005 independent offline diagnosis, no strategy verdict', 'window':[S,E]}
h = native(HERE/'raw/sh601398_hfq_seg0_2026-09-04.json','hfqday')
r = native(HERE/'raw/sh601398_none_seg0_2026-09-04.json','day')
j = h[['close']].join(r[['close']],lsuffix='_h',rsuffix='_r').loc['2023-05-23':'2023-06-30']
train, test = j.iloc[:15], j.iloc[15:]
a,b = np.polyfit(train.close_r, train.close_h,1)
out['single_request_affine'] = {'a':a,'b':b,'train_n':len(train),'test_n':len(test),
    'test_max_price_residual':float((test.close_h-a*test.close_r-b).abs().max()),
    'train_max_price_residual':float((train.close_h-a*train.close_r-b).abs().max()),
    'note':'Disjoint subsequent dates; affine fit is diagnosis only, not a return reconstruction.'}
out['sample_cross_source'] = []
for code in ['sh601398','sh600519','sz000651','sh600000','sz000001']:
    h = read(AQ/f'data/kline_hfq/{code}.csv')
    r = read(AQ/f'data/kline_raw/{code}.csv')
    bs = read(AQ/f'data_bs/daily/{code[:2]}_{code[2:]}.csv')
    j = pd.concat({'hfq':h.close.pct_change(fill_method=None),'raw':r.close.pct_change(fill_method=None),
                   'bs':bs.pctChg/100,'trading':bs.tradestatus},axis=1).sort_index().loc[S:E].dropna()
    j=j[j.trading==1]
    out['sample_cross_source'].append({'code':code,'n':len(j),
        'hfq_vs_bs_median_abs_bp':float((j.hfq-j.bs).abs().median()*1e4),
        'raw_vs_bs_median_abs_bp':float((j.raw-j.bs).abs().median()*1e4),
        'hfq_disagreements_gt_1bp':int(((j.hfq-j.bs).abs()>1e-4).sum()),
        'raw_disagreements_gt_1bp':int(((j.raw-j.bs).abs()>1e-4).sum())})
out['etf_index'] = []
for etf,idx in [('sh510050','sh000016'),('sh510300','sh000300')]:
    er = read(HERE/f'raw/{etf}_raw.csv').close.pct_change(fill_method=None)
    eh = read(HERE/f'raw/{etf}_hfq.csv').close.pct_change(fill_method=None)
    ir = read(HERE/f'raw/{idx}_raw.csv').close.pct_change(fill_method=None)
    j=pd.concat({'raw':er,'hfq':eh,'index':ir},axis=1).sort_index().loc[S:E].dropna()
    out['etf_index'].append({'etf':etf,'index':idx,'n':len(j),
      'beta_raw_to_index':float(np.polyfit(j['index'],j.raw,1)[0]),
      'beta_hfq_to_index':float(np.polyfit(j['index'],j.hfq,1)[0]),
      'note':'Price-index diagnostic only; raw ETF excludes dividends and is not a replacement benchmark.'})

# Verify the actual old can_buy/can_sell masks, including their separate one-price bar guard.
# Restrict to mature non-ST main-board names, ordinary days with cross-source close agreement.
# Rounded exchange-style +/-10% prices are more specific than inferred affine returns.
tot = {k:0 for k in ['files','eligible_days','exact_up_open','exact_down_open',
                     'old_allows_buy_at_up','old_allows_sell_at_down',
                     'old_price_flag_misses_up','old_price_flag_misses_down']}
examples=[]
for i,p in enumerate(sorted((AQ/'data_bs/daily').glob('*.csv'))):
    code=p.stem.replace('_','')
    if not code.startswith(('sh600','sh601','sh603','sh605','sz000','sz001','sz002','sz003')):continue
    hp=AQ/f'data/kline_hfq/{code}.csv'; rp=AQ/f'data/kline_raw/{code}.csv'
    if not hp.exists() or not rp.exists():continue
    bs=read(p); h=read(hp); r=read(rp)
    j=r.add_prefix('r_').join(h.add_prefix('h_'),how='inner').join(bs.add_prefix('bs_'),how='inner')
    prev=j.r_close.shift(1); rh=j.h_close.pct_change(fill_method=None)
    ro=j.h_open/j.h_close.shift(1)-1
    old_st=rh.abs().rolling(60,min_periods=30).max().shift(1)<=.055
    old_lim=pd.Series(np.where(old_st,.05,.10),index=j.index)
    has=(j.h_volume>0)&j.h_close.notna()
    yizi=has&(j.h_high<=j.h_low*1.0001)
    old_up=ro>=(old_lim-.002);old_down=ro<=-(old_lim-.002)
    can_buy=has&~old_up&~(yizi&(ro>0))
    can_sell=has&~old_down&~(yizi&(ro<0))
    normal=((j.bs_pctChg/100-(j.r_close/prev-1)).abs()<1e-5)
    matching=(j.bs_close-j.r_close).abs()<.005
    age=pd.Series(np.arange(len(j)),index=j.index)>=250
    eligible=normal&matching&age&(j.bs_isST==0)&(j.bs_tradestatus==1)&(j.r_volume>0)&has
    eligible&=(j.index>=S)&(j.index<=E)
    up_px=np.floor(prev*1.1*100+.5+1e-9)/100
    dn_px=np.floor(prev*.9*100+.5+1e-9)/100
    up=eligible&((j.r_open-up_px).abs()<.0001)
    dn=eligible&((j.r_open-dn_px).abs()<.0001)
    tot['files']+=1;tot['eligible_days']+=int(eligible.sum())
    for key,mask in [('exact_up_open',up),('exact_down_open',dn),
                     ('old_allows_buy_at_up',up&can_buy),('old_allows_sell_at_down',dn&can_sell),
                     ('old_price_flag_misses_up',up&~old_up),('old_price_flag_misses_down',dn&~old_down)]:
        tot[key]+=int(mask.sum())
    if len(examples)<20:
        for t in j.index[up&can_buy][:2]:
            examples.append({'code':code,'date':t,'raw_prev':float(prev[t]),'raw_open':float(j.r_open[t]),
               'rounded_limit':float(up_px[t]),'hfq_open_change':float(ro[t]),'one_price_bar':bool(yizi[t])})
    if tot['files']%500==0:print('audited',tot['files'],flush=True)
out['limit_audit']={'counts':tot,'examples':examples,
  'limitations':['Main-board non-ST mature names only; cached cross-source ordinary days.',
    'Historical reference cache is not independently PIT-certified.',
    'Opening at limit does not prove an individual order could not fill; depth/queue evidence absent.',
    'Counts test rule consistency; they do not measure actual strategy blocked_frac or PnL impact.',
    'Earlier 72.6% claim used affine proxy and omitted final one-price-bar guard; do not inherit it.']}
(HERE/'audit_results.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False))
(HERE/'source_hashes.json').write_text(json.dumps(sources,indent=2))
print(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False))
