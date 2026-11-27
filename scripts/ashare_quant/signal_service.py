"""
A股核心赛道龙头 Alpha 策略信号检测与飞书推送服务
======================================================
功能:
1. 每日 15:05 (或手动/定时) 读取回测交付物 deliverables/ashare_strategy_backtest.json 的
   最终持仓 (full_sample_top3.recent_positions[-1]) 与对应风险状态。
   通知与前端页面 (app/ashare-strategy) 消费同一份回测交付物, 同源同持仓,
   不再每日独立计算 Top-3, 不产生第二套持仓。
2. 一致性校验 fail-closed: 回测交付物缺失/缺字段/结构损坏, 或交付物最终持仓日
   与本地行情缓存最新交易日不一致时, 不推送、不推进任何游标, 并以明确报错提示
   先刷新数据、重跑 backtest_runner.py。
3. 状态持久化至 scripts/ashare_quant/cache/signal_state.json: 只保存通知游标
   (last_signal_date 等), 不保存持仓; 通知送达成功才推进游标。
   持仓/风险状态变化检测与"上次已通知数据日"的快照对齐: 该快照直接从同一份
   交付物的 recent_positions 中按游标日期取回, 全程单一数据源。
4. 意外退出与异常崩溃主动报警机制 (sys.excepthook + 守护进程退出捕获)

运行链路 (信号服务要求交付物与行情缓存同日):
  python scripts/ashare_quant/refresh_all_data.py             # 刷新行情缓存
  python scripts/ashare_quant/backtest_runner.py              # 重算交付物 (含最终持仓与风险状态)
  python scripts/ashare_quant/signal_service.py --check-now   # 读取交付物最终持仓并按需推送

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
from typing import Any, Dict, Optional, Tuple
import numpy as np

# 项目根目录
HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(HERE))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scripts.ashare_quant.data_feed import (
    fetch_symbol_daily,
    UNIVERSE,
    BENCHMARK_SYMBOL,
    CACHE_DIR
)
from monitor.notifiers import feishu

STATE_FILE = os.path.join(CACHE_DIR, "signal_state.json")
BACKTEST_JSON = os.path.join(PROJECT_ROOT, "deliverables", "ashare_strategy_backtest.json")

# 通知文案展示所需的大盘均线窗口
_BM_MA_WINDOW = 60


class SignalDataError(RuntimeError):
    """信号数据源不可用或不一致: 一律 fail-closed, 不推送、不推进游标。"""


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
        "last_notification": None,
    }


def save_state(state: dict):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def _validate_holdings(holdings: Any, date: str) -> None:
    if not isinstance(holdings, list):
        raise SignalDataError(f"{date} 最终持仓 holdings 不是列表: {type(holdings).__name__}")
    for h in holdings:
        if (
            not isinstance(h, dict)
            or not h.get("symbol")
            or "shares" not in h
            or "price" not in h
            or "weight" not in h
        ):
            raise SignalDataError(f"{date} 持仓条目缺少 symbol/shares/price/weight 字段: {h!r}")


def load_final_backtest_position(path: str = BACKTEST_JSON) -> Dict[str, Any]:
    """读取回测交付物的最终持仓与风险状态 (与策略页面同源)。

    返回字段:
    - date: 最终持仓数据日
    - holdings / cash_weight / regime_healthy: 最终持仓快照与风险状态
    - position_history: {数据日: {"symbols": [...], "regime_healthy": bool|None}}
      由 recent_positions 全部条目构成, 供变化检测按通知游标取回上次已通知快照;
      旧条目缺 regime_healthy 时记为 None (按"可能变化"处理, 宁可多推送不漏报)。

    缺文件 / JSON 损坏 / recent_positions 为空 / 缺 date、holdings、cash_weight、
    regime_healthy 任一字段时抛出 SignalDataError, 由调用方 fail-closed。
    """
    if not os.path.exists(path):
        raise SignalDataError(
            f"回测交付物不存在: {path}。请先运行 scripts/ashare_quant/backtest_runner.py 生成。"
        )
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        recent = payload["full_sample_top3"]["recent_positions"]
        entry = recent[-1]
        date = entry["date"]
        holdings = entry["holdings"]
        cash_weight = entry["cash_weight"]
        regime_healthy = entry["regime_healthy"]
    except SignalDataError:
        raise
    except (KeyError, IndexError, TypeError, ValueError) as e:
        raise SignalDataError(
            f"回测交付物 {path} 缺字段或结构损坏 ({e.__class__.__name__}: {e})。"
            "旧版交付物缺少 regime_healthy 字段也会报此错, 请重跑 backtest_runner.py。"
        ) from e

    if not isinstance(date, str) or not date:
        raise SignalDataError(f"回测交付物最终持仓 date 字段无效: {date!r}")
    if not isinstance(regime_healthy, bool):
        raise SignalDataError(f"{date} regime_healthy 不是布尔值: {regime_healthy!r}")
    _validate_holdings(holdings, date)
    try:
        cash_weight = float(cash_weight)
    except (TypeError, ValueError) as e:
        raise SignalDataError(f"{date} cash_weight 不是数值: {cash_weight!r}") from e

    position_history: Dict[str, Dict[str, Any]] = {}
    for item in recent:
        if not isinstance(item, dict) or not isinstance(item.get("date"), str):
            continue
        if not isinstance(item.get("holdings"), list):
            continue
        syms = [h.get("symbol") for h in item["holdings"]
                if isinstance(h, dict) and h.get("symbol")]
        rg = item.get("regime_healthy")
        position_history[item["date"]] = {
            "symbols": syms,
            "regime_healthy": rg if isinstance(rg, bool) else None,
        }

    return {
        "date": date,
        "holdings": holdings,
        "cash_weight": cash_weight,
        "regime_healthy": regime_healthy,
        "position_history": position_history,
    }


def validate_signal_date_consistency(deliverable_date: str, benchmark_latest_date: str) -> None:
    """数据日一致性校验 (纯函数): 交付物最终持仓日必须与行情缓存最新交易日一致,
    否则 fail-closed, 拒绝用与行情不同步的持仓生成信号。"""
    if deliverable_date != benchmark_latest_date:
        raise SignalDataError(
            f"数据日不一致: 回测交付物最终持仓日 {deliverable_date} != 行情缓存最新交易日 {benchmark_latest_date}。"
            "请先运行 refresh_all_data.py 刷新行情, 再运行 backtest_runner.py 重算交付物, 之后重试信号服务。"
        )


def generate_current_signal(force_fetch: bool = False, backtest_path: str = BACKTEST_JSON) -> dict:
    """从回测交付物生成当前信号: 持仓与风险状态取自 recent_positions[-1]。

    行情缓存只用于: 校验数据日一致性 (不一致直接 fail-closed) 与大盘展示指标。
    """
    pos = load_final_backtest_position(backtest_path)

    bm_df = fetch_symbol_daily(BENCHMARK_SYMBOL, force=force_fetch)
    if bm_df is None or bm_df.empty:
        raise SignalDataError(f"基准行情 {BENCHMARK_SYMBOL} 无数据, 无法生成信号")
    if len(bm_df) < _BM_MA_WINDOW:
        raise SignalDataError(
            f"基准行情 {BENCHMARK_SYMBOL} 不足 {_BM_MA_WINDOW} 根K线, 无法计算展示均线"
        )
    latest_date = bm_df["date"].iloc[-1].strftime("%Y-%m-%d")
    validate_signal_date_consistency(pos["date"], latest_date)

    closes = bm_df["close"].to_numpy(dtype=float)
    holdings_detail = []
    for h in pos["holdings"]:
        sym = h["symbol"]
        holdings_detail.append({
            "symbol": sym,
            "name": h.get("name") or UNIVERSE.get(sym, sym),
            "shares": int(h["shares"]),
            "price": float(h["price"]),
            "weight": float(h["weight"]),
        })

    return {
        "date": pos["date"],
        "regime_healthy": pos["regime_healthy"],
        "benchmark_close": float(closes[-1]),
        "benchmark_ma20": float(np.mean(closes[-20:])),
        "benchmark_ma60": float(np.mean(closes[-_BM_MA_WINDOW:])),
        "top_picks": [h["symbol"] for h in pos["holdings"]],
        "picks_detail": holdings_detail,
        "cash_weight": pos["cash_weight"],
        "position_history": pos["position_history"],
    }


def format_feishu_message(sig: dict, prev_state: dict) -> Tuple[str, str, bool]:
    d = sig["date"]
    healthy = sig["regime_healthy"]
    bm_p = sig["benchmark_close"]
    bm_ma60 = sig["benchmark_ma60"]
    bm_ma20 = sig["benchmark_ma20"]

    # 变化检测: 与"上次已通知数据日"的同源快照对齐 (从交付物 recent_positions 按游标取回),
    # 状态文件只保存游标; 游标缺失或其日期不在快照窗口内时按"发生变化"处理, 宁可多推送不漏报。
    cursor_date = prev_state.get("last_signal_date")
    already_notified = (cursor_date == d)
    if already_notified:
        is_action_required = False
    else:
        prev = sig["position_history"].get(cursor_date) if cursor_date else None
        if prev is None:
            holdings_changed = True
            regime_changed = True
        else:
            holdings_changed = (sig["top_picks"] != prev["symbols"])
            prev_regime = prev["regime_healthy"]
            regime_changed = (prev_regime is None) or (prev_regime != healthy)
        is_action_required = holdings_changed or regime_changed

    if not healthy:
        title = f"A股策略信号：大盘破位，强制空仓避险 (日期: {d})"
        lines = [
            f"【宏观风控触发】",
            f"• 沪深300ETF现价: {bm_p:.3f} | 60日生命线: {bm_ma60:.3f} | 20日均线: {bm_ma20:.3f}",
            f"• 判定: 大盘处于均线空头下行通道，系统一票否决所有个股买入。",
        ]
        if sig["picks_detail"]:
            lines.append(f"\n【回测当前仍持有的仓位 (待调仓/止损处置)】")
            for p in sig["picks_detail"]:
                lines.append(f"👉 {p['name']} ({p['symbol']}) | {p['shares']:,} 股 | 仓位 {p['weight']*100:.1f}%")
            lines.append(f"\n• 处置: 逢高平仓或按风控规则止损, 向目标空仓状态收敛。")
        else:
            lines.append(
                f"\n【明日操作建议 (T+1 开盘)】\n"
                f"• 动作: 100% 保持现金空仓避险\n"
                f"• 目标持仓: 0 只股票 | 现金比例 {sig['cash_weight']*100:.1f}%\n"
                f"• 风控理由: 规避系统性杀跌风险，等待大盘右侧拐点。"
            )
        return title, "\n".join(lines), is_action_required

    title = f"A股龙头策略信号：精选 {len(sig['top_picks'])} 只标的轮动 (日期: {d})"
    lines = [
        f"【市场状态】",
        f"• 沪深300ETF现价: {bm_p:.3f} | 60日生命线: {bm_ma60:.3f} | 20日均线: {bm_ma20:.3f}",
        f"• 大盘环境: 上升/震荡健康状态，允许进攻开仓\n",
        f"【回测最终持仓 (与策略页面同源, 数据日: {d})】"
    ]

    for p in sig["picks_detail"]:
        lines.append(
            f"👉 {p['name']} ({p['symbol']})\n"
            f"   - 持仓股数: {p['shares']:,} 股 | 数据日收盘价: ¥{p['price']:.2f}\n"
            f"   - 目标配置仓位: {p['weight']*100:.1f}%"
        )

    cash_pct = sig["cash_weight"] * 100.0
    if sig["top_picks"]:
        lines.append(f"\n【现金留白】\n• 当前现金比例: {cash_pct:.1f}% (宁缺毋滥，拒绝买入弱势标的)")
    else:
        lines.append(
            f"\n【空仓说明】\n"
            f"• 大盘环境合格但回测最终快照无持仓 (候选不足或持仓已全部止损), 现金比例 {cash_pct:.1f}%。"
        )

    lines.append(f"\n【交易执行提醒】")
    lines.append(f"• 持仓来自最近一次成功回测的最终快照, 严格无未来函数: 于次日 09:30 开盘集合竞价执行")
    lines.append(f"• 若个股一字涨停无法买入则放弃；持仓股跌破 MA20 严格止损。")

    return title, "\n".join(lines), is_action_required


def check_and_notify(force_fetch: bool = False, force_send: bool = False) -> bool:
    """检查回测交付物最新最终持仓并按需推送飞书。

    返回值契约:
    - True: 数据日与游标一致无需推送, 或至少一个已配置渠道明确送达且
      last_signal_date 游标推进一次。
    - False: 数据源 fail-closed (交付物缺失/缺字段/数据日不一致), 或需要推送但
      渠道未配置或全部发送失败; 游标一律不推进, 本次信号不被吞掉,
      由调用方以非零退出码或守护循环重试感知。
    """
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始检查 A 股策略最新信号...")
    state = load_state()

    try:
        sig = generate_current_signal(force_fetch=force_fetch)
    except SignalDataError as e:
        print(f"❌ 信号数据源 fail-closed: {e}", file=sys.stderr, flush=True)
        return False

    title, msg, is_action_required = format_feishu_message(sig, state)
    print(f"\n--- 生成信号预览 ---\n标题: {title}\n内容:\n{msg}\n-------------------")

    should_send = force_send or is_action_required

    if not should_send:
        print("数据日与持仓状态无变化，无需重复推送。")
        return True

    print("\n检测到状态变动或指令更新，正在推送至飞书群机器人...", flush=True)
    delivered = False
    if feishu.is_configured():
        ok = feishu.notify(title, msg, important=is_action_required)
        if ok:
            print("✅ 飞书通知推送成功!")
            delivered = True
        else:
            print("❌ 飞书推送失败，请检查 webhook 配置或网络状态。", file=sys.stderr)
    else:
        print("⚠️ 飞书未配置 webhook (请检查 monitor/feishu_webhook.json)", file=sys.stderr)

    if not delivered:
        # 渠道未配置或全部失败: 通知游标不推进, 失败重试仍基于旧游标重新做差量判断。
        print("❌ 通知未送达任何渠道，last_signal_date 游标未推进，本次按失败处理。",
              file=sys.stderr, flush=True)
        return False

    state["last_signal_date"] = sig["date"]
    # 清理旧版状态中的第二套持仓, 状态文件只保留游标
    state.pop("current_holdings", None)
    state.pop("regime_healthy", None)
    state["last_notification"] = {
        "title": title,
        "timestamp": datetime.now().isoformat()
    }
    save_state(state)
    return True


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
        if not check_and_notify(force_fetch=False, force_send=True):
            sys.exit(2)
        return

    if args.daemon:
        print("启动 A 股策略信号检测守护进程 (Daemon 模式)")
        print("监测规则: 每个 A 股交易日 15:05 自动执行信号检查与推送通知 (依赖最新回测交付物)")
        try:
            while True:
                now = datetime.now()
                if now.weekday() < 5 and (now.hour == 15 and 5 <= now.minute <= 10):
                    state = load_state()
                    today_str = now.strftime("%Y-%m-%d")
                    if state.get("last_check_date") != today_str:
                        print(f"[{today_str} 15:05] 触发每日盘后信号检测...")
                        if check_and_notify(force_fetch=True, force_send=False):
                            # 重新加载，避免用本轮循环触发前的旧副本覆盖
                            # check_and_notify 刚写入的通知游标（否则成功推送也会被回滚）。
                            state = load_state()
                            state["last_check_date"] = today_str
                            save_state(state)
                        else:
                            print("通知未送达或数据源 fail-closed，last_check_date 不写入；将在本窗口内重试。",
                                  file=sys.stderr, flush=True)
                time.sleep(30)
        except Exception as e:
            if feishu.is_configured():
                feishu.notify(
                    title="A股策略守护进程异常中断退出",
                    message=f"【服务意外退出报警】\n时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n错误信息: {str(e)}\n\n守护循环意外终止，请登录服务器检查！",
                    important=True
                )
            raise

    if not check_and_notify(force_fetch=False, force_send=False):
        sys.exit(2)


if __name__ == "__main__":
    main()
