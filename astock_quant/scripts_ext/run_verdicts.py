"""第 2~4 关：对每个平台策略跑 quant-backtest-protocol 的四层证伪 + 逐年剔除。

不重写检验代码 —— 直接调 skill 里的 scripts/qbt.py report。
DSR 的 n_trials 用**本轮全部配置数**（15 个基线 + 21 组消融/敏感性），
而不是「这个策略只跑了一次所以 n=1」：本轮是在同一段样本外上筛 15 个策略，
多重检验的惩罚必须按整个搜索规模算，否则 DSR 会系统性偏高。

用法：python3 scripts_ext/run_verdicts.py
产物：verified/ext_trials.json、verified/<key>_verdict.json、verified/ext_verdicts.json
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402

from aq import config, datasource as ds, panel, universe, validate  # noqa: E402

VERIFIED = os.path.join(config.BASE_DIR, "verified")
QBT = os.path.expanduser("~/.claude/skills/quant-backtest-protocol/scripts/qbt.py")
PY311 = "/opt/homebrew/bin/python3.11"


def build_trials():
    """把本轮所有配置的夏普汇总成 trials（DSR 的输入）。"""
    summ = json.load(open(os.path.join(VERIFIED, "ext_summary.json")))["策略"]
    trials = [{"epoch": i, "params": {"策略": s["key"]},
               "train_sharpe": s["夏普"], "valid_sharpe": s["夏普"]}
              for i, s in enumerate(summ)]
    abl_path = os.path.join(VERIFIED, "ext_ablation.json")
    if os.path.exists(abl_path):
        for j, a in enumerate(json.load(open(abl_path))["消融与敏感性"]):
            trials.append({"epoch": len(trials), "params": {"配置": a["标签"]},
                           "train_sharpe": a["夏普"], "valid_sharpe": a["夏普"]})
    out = {"n_epochs": len(trials), "trials": trials}
    path = os.path.join(VERIFIED, "ext_trials.json")
    json.dump(out, open(path, "w"), ensure_ascii=False, indent=1)
    print(f"trials: {len(trials)} 组配置 -> {path}")
    return path


def per_strategy_trials(key):
    """只用「这个策略自己试过的配置」算一版 DSR，作为敏感性对照。

    与全局版的区别：全局版把 15 个策略 + 21 组消融当成一次搜索，
    试验间夏普方差很大（-1.41 ~ +1.64），纯运气基准被抬得很高，DSR 会非常保守；
    只算自己那几组时，方差小、惩罚轻。两个都报，并说明取哪个当结论。
    """
    prefix = key.split("_")[0]
    summ = json.load(open(os.path.join(VERIFIED, "ext_summary.json")))["策略"]
    trials = [{"epoch": 0, "params": {"策略": key},
               "train_sharpe": s["夏普"], "valid_sharpe": s["夏普"]}
              for s in summ if s["key"].startswith(prefix)]
    abl_path = os.path.join(VERIFIED, "ext_ablation.json")
    if os.path.exists(abl_path):
        for a in json.load(open(abl_path))["消融与敏感性"]:
            if a["标签"].startswith(prefix):
                trials.append({"epoch": len(trials), "params": {"配置": a["标签"]},
                               "train_sharpe": a["夏普"], "valid_sharpe": a["夏普"]})
    for i, t in enumerate(trials):
        t["epoch"] = i
    path = os.path.join(VERIFIED, f"_trials_{key}.json")
    json.dump({"n_epochs": max(len(trials), 1), "trials": trials}, open(path, "w"),
              ensure_ascii=False, indent=1)
    return path, len(trials)


def jackknife(key, ret, hs300, ew):
    return validate.year_jackknife(ret, {"沪深300": hs300, "小盘风格": ew - hs300})


def main():
    trials_path = build_trials()
    summ = json.load(open(os.path.join(VERIFIED, "ext_summary.json")))["策略"]
    bench = pd.read_csv(os.path.join(VERIFIED, "bench_ew_ext.csv"), parse_dates=["date"]) \
        .set_index("date")["ret"]
    hs = pd.read_csv(os.path.join(VERIFIED, "bench_hs300_ext.csv"), parse_dates=["date"]) \
        .set_index("date")["ret"]

    extra = {"s02_no_blackout": (10, 5), "s02_wide": (10, 5),
             "s03_blackout": (20, 20), "s03_wide": (20, 20)}
    jobs = [(s["key"], s["top_n"] or 150, s["freq"]) for s in summ]
    jobs += [(k, v[0], v[1]) for k, v in extra.items()
             if os.path.exists(os.path.join(VERIFIED, f"{k}_returns.csv"))]

    out = {}
    for key, n_long, hold in jobs:
        rpath = os.path.join(VERIFIED, f"{key}_returns.csv")
        if not os.path.exists(rpath):
            continue
        vpath = os.path.join(VERIFIED, f"{key}_verdict.json")
        cmd = [PY311, QBT, "report", "--returns", rpath,
               "--bench", os.path.join(VERIFIED, "bench_ew_ext.csv"),
               "--trials", trials_path,
               "--panel", os.path.join(VERIFIED, "universe_panel.csv"),
               "--market", "cn_stock", "--n-long", str(int(n_long)),
               "--hold", str(int(hold)), "--iters", "200", "--out", vpath]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0 or not os.path.exists(vpath):
            print(f"{key}: qbt 失败\n{r.stdout[-800:]}\n{r.stderr[-800:]}")
            continue
        v = json.load(open(vpath))
        ret = pd.read_csv(rpath, parse_dates=["date"]).set_index("date")["ret"]
        jk = jackknife(key, ret, hs.reindex(ret.index).fillna(0.0),
                       bench.reindex(ret.index).fillna(0.0))
        v["year_jackknife"] = jk
        tp, ntr = per_strategy_trials(key)
        d = subprocess.run([PY311, QBT, "dsr", "--returns", rpath, "--trials", tp,
                            "--market", "cn_stock"], capture_output=True, text=True)
        try:
            v["deflated_sharpe_self_only"] = json.loads(d.stdout[d.stdout.index("{"):])
        except Exception:
            v["deflated_sharpe_self_only"] = {"note": "解析失败", "raw": d.stdout[-300:]}
        v["deflated_sharpe_self_only"]["n_trials_self"] = ntr
        os.remove(tp)
        json.dump(v, open(vpath, "w"), ensure_ascii=False, indent=1)
        out[key] = v
        ab = v.get("alpha_beta", {})
        ds_ = v.get("deflated_sharpe", {})
        rp = v.get("random_portfolio", {})
        print(f"{key:26s} alpha {ab.get('ann_alpha', float('nan')):+.4f} "
              f"t={ab.get('alpha_t', float('nan')):5.2f}  DSR {ds_.get('DSR')}  "
              f"置换分位 {rp.get('percentile_vs_random')}  "
              f"DSR(自) {v['deflated_sharpe_self_only'].get('DSR')}  "
              f"逐年剔除最低t {jk.get('最低t')}  → {v.get('verdict', '')[:34]}", flush=True)

    json.dump(out, open(os.path.join(VERIFIED, "ext_verdicts.json"), "w"),
              ensure_ascii=False, indent=1)
    print(f"\n已写 {os.path.join(VERIFIED, 'ext_verdicts.json')}")


if __name__ == "__main__":
    main()
