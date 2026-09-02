"""
A股核心赛道龙头 Alpha 策略信号检测与飞书推送服务
======================================================
功能:
1. 每日 15:05 (或手动/定时) 检查 A 股最新日线行情
2. 执行三层漏斗与截面动量计算，判断是否发生调仓、止损或大盘避险切换
3. 若产生最新操作信号 (BUY / SELL / 全面避险空仓)，自动推送至飞书群机器人
4. 状态持久化至 scripts/ashare_quant/cache/signal_state.json，避免重复骚扰推送
5. 意外退出与异常崩溃主动报警机制 (sys.excepthook + 守护进程退出捕获)

用法:
  python scripts/ashare_quant/signal_service.py --check-now       # 立即检查并输出当前信号
  python scripts/ashare_quant/signal_service.py --test-notify     # 发送一条飞书测试通知
  python scripts/ashare_quant/signal_service.py --daemon          # 作为每日定时后台守护进程运行
"""

import os
import sys
import json
import time
import argparse
import traceback
from datetime import datetime
from typing import Tuple, List, Dict, Any
import numpy as np
import pandas as pd

# 项目根目录
HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(HERE))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scripts.ashare_quant.data_feed import (
    load_all_universe,
    UNIVERSE,
    BENCHMARK_SYMBOL,
    CACHE_DIR
)
from scripts.ashare_quant.strategy_v2 import RelativeStrengthAlphaStrategy
from monitor.notifiers import feishu

STATE_FILE = os.path.join(CACHE_DIR, "signal_state.json")


def global_exception_handler(exctype, value, tb):
    """
    全局未捕获异常崩溃告警：将详细堆栈直接推送到飞书！
    """
    if issubclass(exctype, KeyboardInterrupt):
        sys.__excepthook__(exctype, value, tb)
        return

    err_msg = "".join(traceback.format_exception(exctype, value, tb))
    print(f"\n[FATAL ERROR] 捕获到未处理异常:\n{err_msg}", file=sys.stderr)

    if feishu.is_configured():
        feishu.notify(
            title="A股策略信号服务严重异常崩溃",
            message=f"【服务崩溃报警】\n时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n异常类型: {exctype.__name__}\n\n堆栈详情:\n{err_msg[:1000]}",
            important=True
        )

    sys.__excepthook__(exctype, value, tb)


# 安装全局异常钩子
sys.excepthook = global_exception_handler


def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "last_check_date": None,
        "last_signal_date": None,
        "current_holdings": [],
        "regime_healthy": True,
        "last_notification": None,
    }


def save_state(state: dict):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def generate_current_signal(force_fetch: bool = False) -> dict:
    all_data = load_all_universe(force=force_fetch)
    bm_df = all_data[BENCHMARK_SYMBOL]
    latest_date = bm_df["date"].iloc[-1].strftime("%Y-%m-%d")

    strategy = RelativeStrengthAlphaStrategy(
        top_k=3,
        rebalance_interval_days=20,
        market_filter_ma=60,
        rs_window_fast=20,
        rs_window_slow=60,
        hysteresis_buffer=0.20,
        stop_loss_pct=0.10,
        trail_activation_pct=0.15,
        trail_pullback_pct=0.08,
        enable_market_filter=True,
    )

    healthy = strategy.is_market_healthy(bm_df)
    bm_close = bm_df["close"].iloc[-1]
    bm_ma60 = np.mean(bm_df["close"].values[-60:])
    bm_ma20 = np.mean(bm_df["close"].values[-20:])

    stock_scores = {}
    if healthy:
        for sym, df in all_data.items():
            if sym == BENCHMARK_SYMBOL:
                continue
            sc = strategy.calculate_rs_alpha(df, bm_df)
            if sc is not None and sc > 0:
                stock_scores[sym] = sc

    ranked_candidates = sorted(stock_scores.items(), key=lambda x: x[1], reverse=True)
    top_picks = [x[0] for x in ranked_candidates[:strategy.top_k]]

    picks_detail = []
    for sym in top_picks:
        df_s = all_data[sym]
        cur_p = float(df_s["close"].iloc[-1])
        ret20 = float(cur_p / df_s["close"].iloc[-20] - 1.0)
        ret60 = float(cur_p / df_s["close"].iloc[-60] - 1.0)
        picks_detail.append({
            "symbol": sym,
            "name": UNIVERSE.get(sym, sym),
            "close": cur_p,
            "score": round(stock_scores[sym], 2),
            "ret20": ret20,
            "ret60": ret60,
            "target_weight": round(1.0 / strategy.top_k, 2)
        })

    return {
        "date": latest_date,
        "regime_healthy": healthy,
        "benchmark_close": float(bm_close),
        "benchmark_ma20": float(bm_ma20),
        "benchmark_ma60": float(bm_ma60),
        "top_picks": top_picks,
        "picks_detail": picks_detail,
        "all_ranked_scores": [
            {"symbol": s, "name": UNIVERSE.get(s, s), "score": round(sc, 2)}
            for s, sc in ranked_candidates
        ]
    }


def format_feishu_message(sig: dict, prev_state: dict) -> Tuple[str, str, bool]:
    d = sig["date"]
    healthy = sig["regime_healthy"]
    bm_p = sig["benchmark_close"]
    bm_ma60 = sig["benchmark_ma60"]
    bm_ma20 = sig["benchmark_ma20"]

    prev_holdings = prev_state.get("current_holdings", [])
    cur_holdings = sig["top_picks"]

    was_healthy = prev_state.get("regime_healthy", True)
    regime_changed = (healthy != was_healthy)
    holdings_changed = (cur_holdings != prev_holdings)
    is_action_required = regime_changed or holdings_changed

    if not healthy:
        title = f"A股策略信号：大盘破位，强制空仓避险 (日期: {d})"
        msg = (
            f"【宏观风控触发】\n"
            f"• 沪深300ETF现价: {bm_p:.3f} | 60日生命线: {bm_ma60:.3f} | 20日均线: {bm_ma20:.3f}\n"
            f"• 判定: 大盘处于均线空头下行通道，系统一票否决所有个股买入。\n\n"
            f"【明日操作建议 (T+1 开盘)】\n"
            f"• 动作: 100% 保持现金空仓避险 (若有旧持仓建议逢高平仓或止损)\n"
            f"• 目标持仓: 0 只股票 | 现金比例 100%\n"
            f"• 风控理由: 规避系统性杀跌风险，等待大盘右侧拐点。"
        )
        return title, msg, is_action_required

    title = f"A股龙头策略信号：精选 {len(cur_holdings)} 只标的轮动 (日期: {d})"
    lines = [
        f"【市场状态】",
        f"• 沪深300ETF现价: {bm_p:.3f} (站稳 60日生命线 {bm_ma60:.3f} 之上)",
        f"• 大盘环境: 上升/震荡健康状态，允许进攻开仓\n",
        f"【最新精选 Top {len(cur_holdings)} 只核心赛道龙头】"
    ]

    for p in sig["picks_detail"]:
        lines.append(
            f"👉 {p['name']} ({p['symbol']})\n"
            f"   - 最新收盘价: ¥{p['close']:.2f}\n"
            f"   - 相对大盘超额得分: {p['score']} 分\n"
            f"   - 近20日/60日涨幅: {p['ret20']:+.1%} / {p['ret60']:+.1%}\n"
            f"   - 目标配置仓位: {p['target_weight']*100:.0f}%"
        )

    if len(cur_holdings) < 3:
        cash_pct = (3 - len(cur_holdings)) * 33.3
        lines.append(f"\n【现金留白】\n• 剩余现金储备: {cash_pct:.1f}% (宁缺毋滥，拒绝买入弱势标的)")

    lines.append(f"\n【交易执行提醒】")
    lines.append(f"• 严格无未来函数规则: 于次日 09:30 开盘集合竞价执行")
    lines.append(f"• 若个股一字涨停无法买入则放弃；持仓股跌破 MA20 严格止损。")

    return title, "\n".join(lines), is_action_required


def check_and_notify(force_fetch: bool = False, force_send: bool = False):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始检查 A 股策略最新信号...")
    state = load_state()
    sig = generate_current_signal(force_fetch=force_fetch)

    title, msg, is_action_required = format_feishu_message(sig, state)
    print(f"\n--- 生成信号预览 ---\n标题: {title}\n内容:\n{msg}\n-------------------")

    should_send = force_send or is_action_required

    if should_send:
        print("\n检测到状态变动或指令更新，正在推送至飞书群机器人...", flush=True)
        if feishu.is_configured():
            ok = feishu.notify(title, msg, important=is_action_required)
            if ok:
                print("✅ 飞书通知推送成功!")
            else:
                print("❌ 飞书推送失败，请检查 webhook 配置或网络状态。")
        else:
            print("⚠️ 飞书未配置 webhook (请检查 monitor/feishu_webhook.json)")

        state["last_signal_date"] = sig["date"]
        state["current_holdings"] = sig["top_picks"]
        state["regime_healthy"] = sig["regime_healthy"]
        state["last_notification"] = {
            "title": title,
            "timestamp": datetime.now().isoformat()
        }
        save_state(state)
    else:
        print("持仓与信号状态无变化，无需重复推送。")


def main():
    parser = argparse.ArgumentParser(description="A股核心赛道龙头 Alpha 策略信号检测与飞书通知服务")
    parser.add_argument("--check-now", action="store_true", help="立即运行一次信号检查并推送")
    parser.add_argument("--test-notify", action="store_true", help="强制发送测试通知给飞书")
    parser.add_argument("--daemon", action="store_true", help="启动每日收盘定时监测守护进程")
    args = parser.parse_args()

    if args.test_notify:
        print("发送测试消息至飞书...")
        ok = feishu.notify(
            title="A股量化策略监控接入测试",
            message=f"测试通知发送成功！\n系统时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n飞书 Webhook 联通正常。",
            important=False
        )
        print("发送结果:", "成功" if ok else "失败")
        return

    if args.check_now:
        check_and_notify(force_fetch=False, force_send=True)
        return

    if args.daemon:
        print("启动 A 股策略信号检测守护进程 (Daemon 模式)")
        print("监测规则: 每个 A 股交易日 15:05 自动执行信号计算与推送通知")
        try:
            while True:
                now = datetime.now()
                if now.weekday() < 5 and (now.hour == 15 and 5 <= now.minute <= 10):
                    state = load_state()
                    today_str = now.strftime("%Y-%m-%d")
                    if state.get("last_check_date") != today_str:
                        print(f"[{today_str} 15:05] 触发每日盘后信号检测...")
                        check_and_notify(force_fetch=True, force_send=False)
                        state["last_check_date"] = today_str
                        save_state(state)
                time.sleep(30)
        except Exception as e:
            if feishu.is_configured():
                feishu.notify(
                    title="A股策略守护进程异常中断退出",
                    message=f"【服务意外退出报警】\n时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n错误信息: {str(e)}\n\n守护循环意外终止，请登录服务器检查！",
                    important=True
                )
            raise

    check_and_notify(force_fetch=False, force_send=False)


if __name__ == "__main__":
    main()
