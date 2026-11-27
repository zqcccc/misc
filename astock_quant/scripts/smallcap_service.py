#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A股专属小微盘微利轮动策略计算与监控服务 (AShare-SmallCap-Quant)
===================================================================
功能:
1. 加载 A 股全市场因果面板 (无幸存者偏差后复权数据)
2. 运行小微盘模型在不同持仓只数 N in [3, 5, 6, 7, 8, 10, 15, 20, 30] 下的收益与极端下撤
3. 为常用实操配置 (7 只首推、8 只平衡、6 只、5 只、10 只、30 只) 分别生成最新持仓清单
4. 批量拉取腾讯最新实时行情快照 (现价、涨跌幅、流通市值)
5. 导出结构化 JSON 至 deliverables/smallcap_strategy.json
6. 崩溃报警支持: 接入 Telegram / 飞书 / 企业微信 自动告警推送
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import traceback
import urllib.request
from datetime import datetime
from typing import Any, Dict, List

import numpy as np
import pandas as pd

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
AQ_ROOT = os.path.dirname(CURRENT_DIR)
PROJECT_ROOT = os.path.dirname(AQ_ROOT)
sys.path.insert(0, AQ_ROOT)
sys.path.insert(0, PROJECT_ROOT)

from aq import adjust, backtest, config, factors, live_smallcap, metrics, panel, strategy, universe, validate

# 接入报警系统
try:
    from monitor.notifiers import notify_all
except Exception:
    notify_all = None

TRADING_DAYS = 244


class NotificationDeliveryError(RuntimeError):
    """需要投递通知但所有渠道均未成功 (未配置或发送失败)，游标不推进，
    供调度层 (非零退出码 / 守护循环捕获重试) 明确感知。"""


def send_alert(title: str, message: str, important: bool = True) -> bool:
    """发送统一告警通知至 Telegram / 飞书 / 企业微信 / macOS。

    返回真实投递结果，不吞错：
    - 至少一个已配置渠道明确返回成功 -> True
    - 通知模块不可用 / 未配置任何渠道 / 已配置渠道全部发送失败 -> False
    本函数自身不抛异常；调用方必须依据返回值决定后续动作
    （例如推进去重游标前先确认投递成功，否则以异常/非零状态上报调度）。
    """
    print(f"[ALERT] {title}\n{message}", file=sys.stderr, flush=True)
    if notify_all is None:
        print("[ALERT-ERR] monitor.notifiers 不可用，告警未投递", file=sys.stderr, flush=True)
        return False
    try:
        results = notify_all(title=title, message=message, important=important)
    except Exception as e:
        print(f"[ALERT-ERR] 发送告警通知失败: {e}", file=sys.stderr, flush=True)
        return False
    delivered = sorted(name for name, ok in (results or {}).items() if ok)
    if delivered:
        print(f"[ALERT] 告警已投递至渠道: {', '.join(delivered)}", flush=True)
        return True
    print(
        "[ALERT-ERR] 所有通知渠道均未成功投递 (未配置或发送失败)，告警未送达；"
        "请检查 monitor 下 feishu/telegram/wechat_work 配置与网络",
        file=sys.stderr,
        flush=True,
    )
    return False


def handle_uncaught_exception(exc_type, exc_value, exc_traceback):
    """进程级崩溃兜底告警"""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    err_text = f"【A股小微盘量化服务进程崩溃退出】\n时间: {datetime.now()}\n类型: {exc_type.__name__}\n详情: {exc_value}\n堆栈:\n{tb_str}"
    send_alert("🚨【A股小微盘量化服务崩溃退出】", err_text, important=True)
    sys.__excepthook__(exc_type, exc_value, exc_traceback)


def fetch_live_snapshots(codes: list[str]) -> dict[str, dict]:
    """批量获取股票的实时行情与流通市值 (来自腾讯行情免 Token 接口)"""
    info = {}
    if not codes:
        return info

    unique_codes = list(set(codes))
    chunk_size = 50
    for i in range(0, len(unique_codes), chunk_size):
        chunk = unique_codes[i : i + chunk_size]
        url = "http://qt.gtimg.cn/q=" + ",".join(chunk)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                text = resp.read().decode("gbk", errors="ignore")
            for line in text.strip().split(";"):
                if not line.strip():
                    continue
                parts = line.split("~")
                if len(parts) > 45:
                    quote = live_smallcap.parse_tencent_snapshot_parts(parts)
                    raw_code = quote["raw_code"]
                    prefix = "sh" if raw_code.startswith("6") or raw_code.startswith("9") else "sz" if raw_code.startswith("0") or raw_code.startswith("3") else "bj"
                    full_code = f"{prefix}{raw_code}"
                    
                    info[full_code] = {
                        key: value
                        for key, value in quote.items()
                        if key != "raw_code"
                    }
        except Exception as e:
            print(f"[WARN] 获取腾讯行情快照失败: {e}", file=sys.stderr)

    return info


def build_smallcap_deliverable(
    out_path: str = "deliverables/smallcap_strategy.json",
    init_cash: float = 10000000.0,
) -> dict:
    t0 = time.time()
    print("[AShare-SmallCap-Quant] 加载 A 股数据面板...", flush=True)
    panels = panel.load_panels()
    close = panels["close"]
    dates = close.index

    # 载入基准
    hs300 = panel.load_index("sh000300")["close"].reindex(dates).astype(float)
    hs300_ret = (hs300 / hs300.shift(1) - 1.0).fillna(0.0)

    # 股票名称字典
    meta_df = pd.read_csv(os.path.join(AQ_ROOT, "data", "meta.csv")).set_index("code")
    code_to_name = meta_df["name"].to_dict()

    # 复权唯一入口（seed/历史回测与线上增量服务共用）：研究面板的 close/open 已经是
    # baostock 对账过的重建复权价（build_panel 只收通过逐日对账的标的，宁缺毋滥），
    # 走 verified 路径；解不出复权的标的在对账阶段就被隔离，不会带着 raw 收益进来。
    adjustment = adjust.build_scoring_panels(
        close_verified=panels["close"],
        close_raw=panels["close_raw"],
        open_verified=panels.get("open"),
        open_raw=panels.get("open_raw"),
    )
    scoring_panels = dict(panels)
    scoring_panels["close"] = adjustment.close
    scoring_panels["open"] = adjustment.open

    print("[AShare-SmallCap-Quant] 计算小微盘因子复合打分 (小市值 + 5日反转 + 低特质波动)...", flush=True)
    fp = {k: v.astype(np.float32) for k, v in factors.build_all(scoring_panels).items()}
    inv_mask = universe.investable(scoring_panels, min_listed=250, exclude_st=True, liquidity_top_pct=1.0)
    ew_mkt = universe.equal_weight_benchmark(scoring_panels, inv_mask).fillna(0.0)
    small_style = ew_mkt - hs300_ret

    weights = {"liqsize20": 1.0, "rev5": 0.5, "ivol60": 0.5}
    score = strategy.composite(fp, weights, inv_mask)
    ranked_factors = {
        name: strategy.masked_rank_score(fp[name], inv_mask)
        for name in weights
    }
    # 调仓频率唯一来源：live_smallcap.REBALANCE_FREQUENCY（2026-09-08: 10 -> 20 月频）。
    rb_dates = strategy.rebalance_dates(
        dates, live_smallcap.REBALANCE_FREQUENCY, start="2019-01-02", end=dates[-1]
    )

    # 1. 灵敏度矩阵测试: N in [3, 5, 6, 7, 8, 10, 15, 20, 30]
    top_n_eval_list = [3, 5, 6, 7, 8, 10, 15, 20, 30]
    sensitivity_table = []
    # 各 N 的静态风险特征描述，刻意不含任何收益/回撤排名断言——
    # 排名类结论必须等回测跑完后由当期数据实算派生（见下方 claims 逻辑）。
    static_assessment = {
        3: "极脆弱·尾部腰斩风险高",
        5: "集中度偏高·踩踏下杀大",
        6: "爆发力强·踩踏下杀仍偏大",
        7: "默认实操档",
        8: "平衡档",
        10: "标准精选",
        15: "多头充分分散",
        20: "多头充分分散",
        30: "多头充分分散",
    }

    print("[AShare-SmallCap-Quant] 执行持仓只数敏感性测试对比...", flush=True)
    for n in top_n_eval_list:
        sig_n = strategy.top_n_signals_buffered(score, rb_dates, top_n=n, buffer_mult=2.0)
        res_n = backtest.run(panels, sig_n, start="2019-01-02", end=dates[-1], init_cash=init_cash)
        r_n = res_n.ret
        nav_n = res_n.equity / res_n.equity.iloc[0]
        years_n = len(r_n) / TRADING_DAYS
        cagr_n = float(nav_n.iloc[-1] ** (1.0 / years_n) - 1.0) * 100
        sharpe_n = float(r_n.mean() / (r_n.std() if r_n.std() > 0 else 1.0) * math.sqrt(TRADING_DAYS))
        dd_n = (nav_n - nav_n.cummax()) / nav_n.cummax()
        mdd_n = float(dd_n.min()) * 100
        crash_dd_n = dd_n.loc["2024-01-02":"2024-02-29"]
        crash_mdd_n = float(crash_dd_n.min()) * 100 if len(crash_dd_n) > 0 else 0.0
        turnover_n = float(res_n.turnover.mean() * TRADING_DAYS)
        reg_n = validate.alpha_beta(r_n, {"沪深300": hs300_ret.loc[r_n.index], "小盘风格": small_style.loc[r_n.index]})
        alpha_n = reg_n.get("年化alpha", 0.0) * 100
        alpha_t_n = reg_n.get("alpha_t(NW)", 0.0)
        mc_n = validate.block_bootstrap(r_n, iters=1500, block=10, seed=42)
        p5_n = mc_n.get("P5", 0.0)

        sensitivity_table.append({
            "N": n,
            "cagr_pct": round(cagr_n, 2),
            "daily_sharpe": round(sharpe_n, 3),
            "max_drawdown_pct": round(mdd_n, 2),
            "crash_2024_mdd_pct": round(crash_mdd_n, 2),
            "annual_turnover": round(turnover_n, 1),
            "alpha_annual_pct": round(alpha_n, 2),
            "alpha_t_nw": round(alpha_t_n, 2),
            "mc_p5": round(p5_n, 2),
            "assessment": static_assessment.get(n, "多头充分分散"),
        })

    # 排名类结论由当前 sensitivity 数据实算派生，禁止沿用历史硬编码：
    # 上一版把 N=7 硬编码为 is_top_cagr/「收益之王」，而 2026-09 数据里 N=15 的
    # CAGR 更高——过期断言会误导实操。平局取表中靠前的 N（确定性）。
    top_cagr_row = None
    mildest_dd_row = None
    for row in sensitivity_table:
        if top_cagr_row is None or row["cagr_pct"] > top_cagr_row["cagr_pct"]:
            top_cagr_row = row
        if mildest_dd_row is None or row["max_drawdown_pct"] > mildest_dd_row["max_drawdown_pct"]:
            mildest_dd_row = row
    top_cagr_n = top_cagr_row["N"] if top_cagr_row is not None else None
    mildest_dd_n = mildest_dd_row["N"] if mildest_dd_row is not None else None
    recommended_n = 7  # 默认展示配置（页签/推荐理由围绕它生成，但不冒充排名断言）
    for row in sensitivity_table:
        claims = []
        if row["N"] == top_cagr_n:
            claims.append(f"🔥本表年化最高（CAGR {row['cagr_pct']}%）")
        if row["N"] == mildest_dd_n:
            claims.append(f"全期回撤最浅（{row['max_drawdown_pct']}%）")
        row["assessment"] = (
            f"{row['assessment']}·{'·'.join(claims)}" if claims else row["assessment"]
        )
        row["is_top_cagr"] = (row["N"] == top_cagr_n)
        row["is_recommended"] = (row["N"] == recommended_n)

    # 2. 为 [7, 8, 6, 5, 10, 30] 分别生成完整的详情结构
    detailed_configs = [7, 8, 6, 5, 10, 30]
    config_outputs = {}

    needed_codes = set()
    signals_by_n = {}
    res_by_n = {}

    for n in detailed_configs:
        sig = strategy.top_n_signals_buffered(score, rb_dates, top_n=n, buffer_mult=2.0)
        res = backtest.run(panels, sig, start="2019-01-02", end=dates[-1], init_cash=init_cash, keep_holdings=True)
        signals_by_n[n] = sig
        res_by_n[n] = res

    # 快照只拉各配置最后一期缓冲后持仓（与回测末期信号同源）；旧版从原始分
    # Top100 拉取补满，没有滞后带状态，会偏离回测实际持仓。
    for n in detailed_configs:
        needed_codes.update(live_smallcap.signal_holdings_at(signals_by_n[n]))

    print(f"[AShare-SmallCap-Quant] 批量拉取 {len(needed_codes)} 只候选股票的实时行情快照...", flush=True)
    live_snaps = fetch_live_snapshots(list(needed_codes))
    latest_date_str = str(dates[-1].date())

    # 基准净值
    bm_nav = (1.0 + hs300_ret).cumprod()
    ew_nav = (1.0 + ew_mkt).cumprod()
    bm_dd = (bm_nav - bm_nav.cummax()) / bm_nav.cummax()

    for n in detailed_configs:
        sig = signals_by_n[n]
        res = res_by_n[n]
        nav = res.equity / res.equity.iloc[0]
        dd = (nav - nav.cummax()) / nav.cummax()
        r = res.ret
        years = len(r) / TRADING_DAYS

        cagr = float(nav.iloc[-1] ** (1.0 / years) - 1.0) * 100
        sharpe = float(r.mean() / (r.std() if r.std() > 0 else 1.0) * math.sqrt(TRADING_DAYS))
        mdd = float(dd.min()) * 100
        crash_mdd = float(dd.loc["2024-01-02":"2024-02-29"].min() * 100) if len(dd.loc["2024-01-02":"2024-02-29"]) > 0 else 0.0
        
        reg_style = validate.alpha_beta(r, {"沪深300": hs300_ret.loc[r.index], "小盘风格": small_style.loc[r.index]})

        # 最新持仓 = 最后一期缓冲后信号，与回测末期目标持仓严格同源。
        # ST 已在可投资池（universe.investable 的 infer_st_cap）剔除，不再按快照名
        # 二次截补——那会改变持仓集合，破坏 seed==回测末期信号的一致性。
        latest_rb_dt = sig.index[-1]
        signal_codes = live_smallcap.signal_holdings_at(sig)
        tot_eq = float(res.equity.iloc[-1])
        target_wt_val = round(100.0 / n, 2)

        holdings_list = []
        for code in signal_codes:
            base_name = code_to_name.get(code, code)
            snap = live_snaps.get(code, {})
            name = snap.get("name", base_name)
            px = snap.get("price", float(close.loc[dates[-1], code]))
            f_cap = snap.get("float_cap_billion", 0.0)
            t_cap = snap.get("total_cap_billion", 0.0)
            chg = snap.get("change_pct", 0.0)
            
            target_val = (1.0 / n) * tot_eq
            shares = int(target_val / (px * 100)) * 100 if px > 0 else 0
            f_score = float(score.loc[latest_rb_dt, code]) if (latest_rb_dt in score.index and code in score.columns) else 0.0

            holdings_list.append({
                "code": code,
                "display_code": code[2:],
                "name": name,
                "target_weight": target_wt_val,
                "price": round(px, 2),
                "change_pct": round(chg, 2),
                "quote_time": snap.get("quote_time", ""),
                "float_cap_billion": f_cap,
                "total_cap_billion": t_cap,
                "shares": shares,
                "market_val": round(shares * px, 2),
                "factor_score": round(f_score, 4),
                "factor_breakdown": live_smallcap.factor_breakdown_at(
                    {name: fp[name] for name in weights},
                    ranked_factors,
                    latest_rb_dt,
                    code,
                ),
            })

        holdings_list = sorted(holdings_list, key=lambda x: (x["float_cap_billion"] if x["float_cap_billion"] > 0 else 9999))

        current_period = live_smallcap.current_period_summary(
            close,
            [item["code"] for item in holdings_list],
            latest_rb_dt,
            dates[-1],
            close_raw=panels.get("close_raw"),
            open_panel=scoring_panels.get("open"),
            frequency=live_smallcap.REBALANCE_FREQUENCY,
            unresolved_events=adjustment.unresolved_events,
        )
        for item in holdings_list:
            period = current_period["returns_by_code"].get(item["code"], {})
            item["period_return_pct"] = period.get("return_pct")
            item["period_entry_price"] = period.get("entry_price")

        caps = [h["float_cap_billion"] for h in holdings_list if h["float_cap_billion"] > 0]
        cap_dist = {
            "under_20b": sum(1 for c in caps if c < 20.0),
            "between_20_30b": sum(1 for c in caps if 20.0 <= c < 30.0),
            "between_30_50b": sum(1 for c in caps if 30.0 <= c < 50.0),
            "above_50b": sum(1 for c in caps if c >= 50.0),
            "median_cap": round(float(np.median(caps)), 2) if caps else 0.0,
            "min_cap": round(float(min(caps)), 2) if caps else 0.0,
            "max_cap": round(float(max(caps)), 2) if caps else 0.0,
        }

        # 调仓历史 (近 6 期)
        rebalance_hist = []
        recent_rb = sig.index[-6:]
        prev = set()
        for r_dt in recent_rb:
            cur = set(sig.loc[r_dt].dropna().index)
            b_list = cur - prev
            s_list = prev - cur
            rebalance_hist.append({
                "rebalance_date": str(r_dt.date()),
                "holdings_count": len(cur),
                "bought": [{"code": c, "name": code_to_name.get(c, c)} for c in b_list],
                "sold": [{"code": c, "name": code_to_name.get(c, c)} for c in s_list],
                "turnover_pct": round(len(b_list) / len(cur) * 100, 1) if cur else 0.0,
            })
            prev = cur
        rebalance_hist.reverse()

        # 净值曲线抽样
        step = 2
        s_dates = nav.index[::step]
        if nav.index[-1] not in s_dates:
            s_dates = s_dates.append(pd.DatetimeIndex([nav.index[-1]]))

        curve = []
        for d in s_dates:
            curve.append({
                "date": str(d.date()),
                "strategy_nav": round(float(nav.loc[d]), 4),
                "hs300_nav": round(float(bm_nav.loc[d]), 4),
                "all_a_nav": round(float(ew_nav.loc[d]), 4),
                "strategy_drawdown": round(float(dd.loc[d] * 100), 2),
                "hs300_drawdown": round(float(bm_dd.loc[d] * 100), 2),
            })

        config_outputs[str(n)] = {
            "top_n": n,
            "target_weight_per_stock": round(100.0 / n, 2),
            "metrics": {
                "total_return_pct": round(float((nav.iloc[-1] - 1.0) * 100), 2),
                "cagr_pct": round(cagr, 2),
                "daily_sharpe": round(sharpe, 3),
                "max_drawdown_pct": round(mdd, 2),
                "crash_2024_mdd_pct": round(crash_mdd, 2),
                "annual_turnover": round(float(res.turnover.mean() * TRADING_DAYS), 1),
                "alpha_annual_pct": round(reg_style.get("年化alpha", 0.0) * 100, 2),
                "alpha_t_nw": round(reg_style.get("alpha_t(NW)", 0.0), 2),
                "beta_hs300": round(reg_style.get("beta_沪深300", 0.0), 2),
                "beta_small_style": round(reg_style.get("beta_小盘风格", 0.0), 2),
            },
            "cap_distribution": cap_dist,
            "current_period": current_period,
            "current_holdings": holdings_list,
            "rebalance_history": rebalance_hist,
            "equity_curve": curve,
        }

    # 推荐理由由当期 sensitivity 实算生成（含默认配置的实算数字与全表对比），
    # 不引用历史固定值。
    rec_row = next((row for row in sensitivity_table if row["N"] == recommended_n), None)
    if rec_row is None:
        recommendation_reason = (
            f"默认展示 N={recommended_n}（当前 sensitivity 数据未覆盖该配置，"
            "推荐理由待全量重算后生成）。"
        )
    else:
        top_note = (
            f"本表年化最高为 N={top_cagr_n}（CAGR {top_cagr_row['cagr_pct']}%）。"
            if top_cagr_n != recommended_n
            else "该配置即为本表年化最高。"
        )
        recommendation_reason = (
            f"由当前 sensitivity 数据实算：默认展示 N={recommended_n}，"
            f"年化 {rec_row['cagr_pct']}%、纯超额 Alpha {rec_row['alpha_annual_pct']}%"
            f"（NW t={rec_row['alpha_t_nw']}）、蒙卡 P5 极端尾部 {rec_row['mc_p5']}、"
            f"2024 初踩踏回撤 {rec_row['crash_2024_mdd_pct']}%、"
            f"年换手 {rec_row['annual_turnover']}x。{top_note}"
            "所有数字随每次全量重算更新，不引用历史固定值。"
        )

    # 主交付物结构
    deliverable = {
        "strategy_id": "ashare_joinquant_smallcap_micro",
        "strategy_name": "A股专属小微盘微利轮动策略 (A-Share SmallCap Rotation)",
        "platform": "聚宽 (JoinQuant) 顶流小微盘模型本土化严格复刻",
        "market": "A 股专属 (中国资本市场特有的小市值溢价与流动性补偿)",
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "latest_trading_date": latest_date_str,
        "latest_rebalance_date": str(signals_by_n[recommended_n].index[-1].date()),
        "recommended_n": recommended_n,
        "recommendation_reason": recommendation_reason,
        "rules": {
            "universe": "A 股全市场，剔除 ST、次新 (<250天)、停牌与一字板",
            "weights": "小盘规模 (1.0) + 短期反转 (0.5) + 低特质波动 (0.5)",
            "freq_days": live_smallcap.REBALANCE_FREQUENCY,
            "buffer_mult": 2.0,
            "execution": "T 日收盘定权重，T+1 日开盘撮合成交 (严格无未来函数)",
            "friction": "双边佣金万2.5 + 印花税(历史动态税率) + 滑点冲击 0.1%",
        },
        "factor_methodology": live_smallcap.factor_methodology(),
        "sensitivity_table": sensitivity_table,
        "configs": config_outputs,
    }

    target_abs = os.path.isabs(out_path) and out_path or os.path.join(PROJECT_ROOT, out_path)
    os.makedirs(os.path.dirname(target_abs), exist_ok=True)
    with open(target_abs, "w", encoding="utf-8") as f:
        json.dump(deliverable, f, ensure_ascii=False, indent=2)

    print(f"[AShare-SmallCap-Quant] 多配置交付物写入成功: {target_abs} (耗时: {time.time() - t0:.2f}s)", flush=True)
    return deliverable


def notify_rebalance_if_needed(deliverable: dict, force: bool = False) -> bool:
    """若当期存在股票调仓变动，自动向 Telegram / 飞书 / 企业微信 发送调仓通知。

    返回值契约:
    - True: 通知已成功投递，且 last_notified_rebalance 游标推进一次；
    - False: 当期无调仓变动 / 该调仓日已发送过，无需投递；
    - 抛出 NotificationDeliveryError: 需要投递但所有渠道失败（未配置或发送失败），
      游标不推进，由调度层（单次运行非零退出 / 守护循环捕获后告警并重试）感知。
    """
    cfg_7 = deliverable.get("configs", {}).get("7")
    if not cfg_7:
        return False

    rb_hist = cfg_7.get("rebalance_history", [])
    if not rb_hist:
        return False

    latest_rb = rb_hist[0]
    rb_date = latest_rb.get("rebalance_date")
    bought = latest_rb.get("bought", [])
    sold = latest_rb.get("sold", [])
    turnover = latest_rb.get("turnover_pct", 0.0)

    if not bought and not sold:
        print(f"[AShare-SmallCap-Quant] 当期 ({rb_date}) 经滞后带缓冲无标的变动，持仓保持稳定，无需发换仓通知", flush=True)
        return False

    cache_dir = os.getenv(
        "SMALLCAP_STATE_DIR",
        os.path.join(PROJECT_ROOT, "monitor", "caches", "ashare_smallcap"),
    )
    os.makedirs(cache_dir, exist_ok=True)
    stamp_file = os.path.join(cache_dir, "last_notified_rebalance.txt")

    if os.path.exists(stamp_file) and not force:
        try:
            with open(stamp_file, "r") as f:
                last_sent = f.read().strip()
            if last_sent == rb_date:
                print(f"[AShare-SmallCap-Quant] 调仓日 {rb_date} 已发送过通知，跳过重复推送", flush=True)
                return False
        except Exception:
            pass

    current_holdings = cfg_7.get("current_holdings", [])
    current_codes = {h["code"] for h in current_holdings}
    
    # 严格剔除 ST 后的调入清单 (必须在 current_holdings 中存在且无 ST)
    clean_bought = [b for b in bought if b["code"] in current_codes and "ST" not in b.get("name", "")]
    bought_clean_codes = {b["code"] for b in clean_bought}
    retained = [h for h in current_holdings if h["code"] not in bought_clean_codes]

    lines = [
        f"📅 信号触发日期: {rb_date} (收盘结算)",
        "⏰ 建议执行时机: 明早 09:15~09:20 集合竞价 或 09:35 开盘后",
        f"🔄 当期换手率: {turnover}% (7只组合 · 单只目标 14.3%)\n",
    ]

    if sold:
        lines.append("🔴【调出清仓】(建议卖出):")
        for s in sold:
            lines.append(f"  • {s['code'][2:]} {s['name']}")
        lines.append("")

    if clean_bought:
        lines.append("🟢【调入建仓】(建议买入):")
        for b in clean_bought:
            match_h = next((h for h in current_holdings if h["code"] == b["code"]), None)
            is_kcb = b["code"].startswith("sh688")
            board_desc = "科创板·≥200股起购" if is_kcb else "主板/创业板·整手"
            px_str = f"| 现价: ¥{match_h['price']}" if match_h else ""
            lines.append(f"  • {b['code'][2:]} {b['name']} ({board_desc}) {px_str}")
        lines.append("")

    if retained:
        names = "、".join([h["name"] for h in retained])
        lines.append(f"⚪【继续留仓】(无需操作):\n  {names}\n")

    lines.append("📊 查看看板持仓与实操建议股数:")
    lines.append("http://localhost:3011/smallcap-strategy")

    msg_body = "\n".join(lines)
    title = f"🔔【A股小微盘量化策略】调仓操作提醒 ({rb_date})"

    print(f"[AShare-SmallCap-Quant] 发送调仓通知推送:\n{msg_body}", flush=True)
    if not send_alert(title, msg_body, important=True):
        # 全部渠道未投递成功: 不推进去重游标，以明确异常让调度感知。
        raise NotificationDeliveryError(
            f"调仓通知 ({rb_date}) 所有通知渠道投递失败，last_notified_rebalance 游标未推进；"
            f"调度将重试，请检查 monitor 通知渠道配置与网络"
        )

    try:
        with open(stamp_file, "w") as f:
            f.write(rb_date)
    except Exception as e:
        # 通知已送达但游标写盘失败: 下次触发会对同一调仓日重复推送，如实告知。
        print(f"[WARN] 调仓通知已送达但写入时间戳失败 ({e})，下次触发可能重复推送", file=sys.stderr)

    return True


def run_daemon(out_path: str):
    """常驻守护进程：交易日 15:10 定时更新，调仓主动发通知，异常主动告警"""
    print("[AShare-SmallCap-Quant] 启动常驻守护模式，交易日 15:10 自动触发全量更新与调仓通知...", flush=True)
    last_run_date = None
    fail_count = 0
    while True:
        try:
            now = datetime.now()
            today_str = now.strftime("%Y-%m-%d")
            is_weekday = now.weekday() < 5
            is_after_close = (now.hour > 15) or (now.hour == 15 and now.minute >= 10)

            if is_weekday and is_after_close and (last_run_date != today_str):
                print(f"[AShare-SmallCap-Quant] 触发收盘定时生成 @ {now}", flush=True)
                deliverable = build_smallcap_deliverable(out_path)
                # 检测并推送调仓通知
                notify_rebalance_if_needed(deliverable)
                last_run_date = today_str
                fail_count = 0

            time.sleep(30)
        except Exception as e:
            fail_count += 1
            err_msg = f"A股小微盘量化计算异常 (连续失败 {fail_count} 次):\n错误: {e}\n{traceback.format_exc()}"
            print(f"[ERROR] {err_msg}", file=sys.stderr, flush=True)
            if fail_count <= 3:
                send_alert("🚨【A股小微盘量化服务定时异常】", err_msg, important=True)
            time.sleep(60)


def main():
    parser = argparse.ArgumentParser(description="A股小微盘量化持仓与监控服务")
    parser.add_argument("--once", action="store_true", help="单次生成交付物并退出")
    parser.add_argument("--daemon", action="store_true", help="常驻守护模式")
    parser.add_argument("--notify", action="store_true", help="检查最新一期是否有调仓并发送通知")
    parser.add_argument("--force-notify", action="store_true", help="强制发送当前最新一期的调仓通知(测试联调)")
    parser.add_argument("--out", default="deliverables/smallcap_strategy.json", help="输出路径")
    parser.add_argument("--no-notify", action="store_true",
                        help="只重算交付物，不发送调仓通知（重算历史口径时用，避免发出假调仓信号）")
    args = parser.parse_args()

    if args.no_notify:
        build_smallcap_deliverable(args.out)
        return

    # 单次运行模式: 投递失败以非零退出码上报调度，不走崩溃兜底告警
    # (通知失败不是进程崩溃，避免误导性的重复告警)。
    try:
        if args.force_notify or args.notify:
            target_abs = os.path.isabs(args.out) and args.out or os.path.join(PROJECT_ROOT, args.out)
            if not os.path.exists(target_abs):
                build_smallcap_deliverable(args.out)
            with open(target_abs, "r", encoding="utf-8") as f:
                d = json.load(f)
            notify_rebalance_if_needed(d, force=args.force_notify)
        elif args.daemon:
            run_daemon(args.out)
        else:
            deliverable = build_smallcap_deliverable(args.out)
            notify_rebalance_if_needed(deliverable)
    except NotificationDeliveryError as e:
        print(f"[AShare-SmallCap-Quant] 调仓通知投递失败，以非零状态退出供调度感知: {e}",
              file=sys.stderr, flush=True)
        sys.exit(2)


if __name__ == "__main__":
    sys.excepthook = handle_uncaught_exception
    main()
