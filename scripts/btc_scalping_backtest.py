"""
BTC 5分钟 剥头皮策略回测 (向量化版)
====================================
三个子策略根据市场状态自动切换:
  A. 震荡区间 (Range) —— 赌突破失败，高抛低吸
  B. 强趋势 (Strong Trend) —— 顺势追单
  C. 弱趋势 (Weak Trend) —— 顺势等回调

风控:
  - 手续费 + 滑点
  - 硬性止损/止盈
  - 禁止逆势剥头皮
  - 禁止马丁格尔
"""

import ccxt
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import os
import json
import time
import warnings
warnings.filterwarnings("ignore")

plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "SimHei", "PingFang SC"]
plt.rcParams["axes.unicode_minus"] = False

# ============================================================
# 全局参数
# ============================================================
SYMBOL = "BTC/USDT"
TIMEFRAME = "5m"
COMMISSION_RATE = 0.0004       # 单边手续费 0.04% (maker taker 平均)
SLIPPAGE_RATE = 0.0001         # 单边滑点 0.01%
TOTAL_FRICTION = (COMMISSION_RATE + SLIPPAGE_RATE) * 2  # 开平仓双边

# 止盈止损 (以百分比计)
TP_PCT = 0.003    # 止盈 0.3%
SL_PCT = 0.006    # 止损 0.6%  (盈亏比 1:2)

# 市场状态识别参数
RANGE_LOOKBACK = 20            # 震荡判定回看K线数
TREND_LOOKBACK = 10            # 趋势判定回看K线数
EMA_FAST = 8                   # 快速EMA
EMA_SLOW = 21                  # 慢速EMA

# 强趋势阈值
STRONG_TREND_BODY_RATIO = 0.7  # K线实体/振幅 > 70% 视为趋势K线
STRONG_TREND_MIN_COUNT = 3     # 连续同方向趋势K线数量

# 震荡区间参数
RANGE_OVERLAP_RATIO = 0.6      # K线重叠比例 > 60% 视为震荡

# 弱趋势参数
DOJI_BODY_RATIO = 0.3          # 实体/振幅 < 30% 视为十字星

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_cache_btc_scalp")
os.makedirs(CACHE_DIR, exist_ok=True)

INITIAL_CAPITAL = 10000.0      # 初始资金 USDT
POSITION_SIZE_PCT = 1.0        # 每次满仓


# ============================================================
# 数据获取
# ============================================================
def fetch_ohlcv(symbol=SYMBOL, timeframe=TIMEFRAME, days=365):
    """从 Binance 获取K线数据，自动分页"""
    cache_path = os.path.join(CACHE_DIR, f"ohlcv_{symbol.replace('/', '_')}_{timeframe}_{days}d.csv")
    if os.path.exists(cache_path):
        df = pd.read_csv(cache_path, parse_dates=["timestamp"])
        print(f"  从缓存加载 {len(df)} 根K线")
        return df

    print(f"  正在从交易所获取 {symbol} {timeframe} K线数据 ({days}天)...")
    exchange = ccxt.binance({"enableRateLimit": True})

    since = exchange.parse8601((datetime.utcnow() - timedelta(days=days)).isoformat())
    all_data = []
    limit = 1000

    while True:
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)
        except Exception as e:
            print(f"    获取出错: {e}, 等待重试...")
            time.sleep(5)
            continue

        if not ohlcv:
            break
        all_data.extend(ohlcv)
        since = ohlcv[-1][0] + 1
        print(f"    已获取 {len(all_data)} 根K线...")
        time.sleep(0.5)

        if len(ohlcv) < limit:
            break

    df = pd.DataFrame(all_data, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df = df.drop_duplicates(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)

    df.to_csv(cache_path, index=False)
    print(f"  共获取 {len(df)} 根K线，已缓存")
    return df


# ============================================================
# 技术指标计算 (全向量化)
# ============================================================
def compute_indicators(df):
    """计算所有需要的技术指标 —— 纯向量化"""
    df = df.copy()

    # EMA
    df["ema_fast"] = df["close"].ewm(span=EMA_FAST, adjust=False).mean()
    df["ema_slow"] = df["close"].ewm(span=EMA_SLOW, adjust=False).mean()

    # K线形态特征
    df["body"] = (df["close"] - df["open"]).abs()
    df["range"] = df["high"] - df["low"]
    df["body_ratio"] = np.where(df["range"] > 0, df["body"] / df["range"], 0.0)
    df["is_bullish"] = (df["close"] > df["open"]).astype(np.int8)
    df["is_bearish"] = (df["close"] < df["open"]).astype(np.int8)

    # 收盘位置 (0=最低, 1=最高)
    df["close_position"] = np.where(
        df["range"] > 0,
        (df["close"] - df["low"]) / df["range"],
        0.5,
    )

    # 是否为趋势K线 / 十字星
    df["is_trend_bar"] = (df["body_ratio"] > STRONG_TREND_BODY_RATIO).astype(np.int8)
    df["is_doji"] = (df["body_ratio"] < DOJI_BODY_RATIO).astype(np.int8)

    # ---- 向量化重叠度 ----
    print("    计算K线重叠度...")
    df["overlap_ratio"] = _overlap_ratio_vectorized(
        df["high"].values, df["low"].values, RANGE_LOOKBACK
    )

    # ---- 向量化连续趋势K线计数 ----
    print("    计算连续趋势K线...")
    bull_trend = (df["is_bullish"].values == 1) & (df["is_trend_bar"].values == 1)
    bear_trend = (df["is_bearish"].values == 1) & (df["is_trend_bar"].values == 1)
    df["bull_streak"] = _streak_count(bull_trend)
    df["bear_streak"] = _streak_count(bear_trend)

    # ---- 向量化市场状态 ----
    print("    分类市场状态...")
    df["market_state"] = _classify_market_state_vec(df)

    # ---- 向量化区间高低点 (用于策略A) ----
    df["range_high"] = df["high"].rolling(RANGE_LOOKBACK, min_periods=RANGE_LOOKBACK).max()
    df["range_low"] = df["low"].rolling(RANGE_LOOKBACK, min_periods=RANGE_LOOKBACK).min()
    df["range_size"] = df["range_high"] - df["range_low"]

    return df


def _overlap_ratio_vectorized(highs, lows, lookback):
    """
    向量化计算相邻K线重叠度的滚动平均。
    相邻两根K线的重叠 = max(0, min(h1,h2) - max(l1,l2)) / (max(h1,h2) - min(l1,l2))
    然后取 lookback 窗口的滚动平均。
    """
    n = len(highs)
    # 先算每对相邻K线的 pairwise overlap
    prev_h = highs[:-1]
    curr_h = highs[1:]
    prev_l = lows[:-1]
    curr_l = lows[1:]

    overlap_top = np.minimum(prev_h, curr_h)
    overlap_bot = np.maximum(prev_l, curr_l)
    total_range = np.maximum(prev_h, curr_h) - np.minimum(prev_l, curr_l)

    pair_overlap = np.where(
        total_range > 0,
        np.maximum(0, overlap_top - overlap_bot) / total_range,
        0.0,
    )
    # pair_overlap[i] = overlap between bar i and bar i+1, length = n-1

    # 对 pair_overlap 做 rolling mean, window = lookback-1
    # 结果对齐到 bar index: overlap_ratio[i] = mean of pair_overlap[i-lookback+1 : i]
    cumsum = np.concatenate([[0.0], np.cumsum(pair_overlap)])
    window = lookback - 1
    result = np.zeros(n)
    for_start = window  # pair_overlap index
    # result[i] for i >= lookback: mean of pair_overlap[i-lookback .. i-1]
    # pair_overlap index maps: pair_overlap[k] = overlap(bar k, bar k+1)
    # We want lookback-1 pairs ending at bar i-1: pair_overlap[i-lookback .. i-2]
    # = cumsum[i-1] - cumsum[i-lookback]  (pair_overlap is 0-indexed, cumsum shifted by 1)
    idx = np.arange(lookback, n)
    result[idx] = (cumsum[idx - 1] - cumsum[idx - lookback]) / window

    return result


def _streak_count(condition_arr):
    """
    计算布尔数组中连续 True 的当前长度。
    例如 [F,T,T,T,F,T] -> [0,1,2,3,0,1]
    """
    n = len(condition_arr)
    streaks = np.zeros(n, dtype=np.int32)
    if n == 0:
        return streaks
    streaks[0] = int(condition_arr[0])
    for i in range(1, n):
        if condition_arr[i]:
            streaks[i] = streaks[i - 1] + 1
        else:
            streaks[i] = 0
    return streaks


def _classify_market_state_vec(df):
    """向量化市场状态分类"""
    n = len(df)
    states = np.full(n, 4, dtype=np.int8)  # 0=strong_up,1=strong_down,2=weak_up,3=weak_down,4=range

    ema_pct = (df["ema_fast"].values - df["ema_slow"].values) / np.where(
        df["ema_slow"].values > 0, df["ema_slow"].values, 1.0
    )
    overlap = df["overlap_ratio"].values
    bull_streak = df["bull_streak"].values
    bear_streak = df["bear_streak"].values

    start = max(RANGE_LOOKBACK, TREND_LOOKBACK)
    idx = np.arange(start, n)

    strong_up = (bull_streak[idx] >= STRONG_TREND_MIN_COUNT) & (overlap[idx] < 0.4)
    strong_down = (bear_streak[idx] >= STRONG_TREND_MIN_COUNT) & (overlap[idx] < 0.4)
    is_range = overlap[idx] > RANGE_OVERLAP_RATIO
    weak_up = ema_pct[idx] > 0.0005
    weak_down = ema_pct[idx] < -0.0005

    # 优先级: strong > range > weak > default(range)
    states[idx] = 4  # default range
    states[idx[weak_down]] = 3
    states[idx[weak_up]] = 2
    states[idx[is_range]] = 4
    states[idx[strong_down]] = 1
    states[idx[strong_up]] = 0

    state_map = {0: "strong_up", 1: "strong_down", 2: "weak_up", 3: "weak_down", 4: "range"}
    return pd.Series(states).map(state_map).values


# ============================================================
# 策略信号生成 (向量化)
# ============================================================
def generate_signals(df):
    """向量化生成交易信号"""
    df = df.copy()
    n = len(df)
    signals = np.zeros(n, dtype=np.int8)
    strategy_names = np.full(n, "", dtype=object)

    state = df["market_state"].values
    close = df["close"].values
    high = df["high"].values
    low = df["low"].values
    is_bullish = df["is_bullish"].values
    is_bearish = df["is_bearish"].values
    body_ratio = df["body_ratio"].values
    close_pos = df["close_position"].values
    is_doji = df["is_doji"].values
    range_high = df["range_high"].values
    range_low = df["range_low"].values
    range_size = df["range_size"].values

    start = max(RANGE_LOOKBACK, TREND_LOOKBACK) + 1

    # ------ 策略 A: 震荡区间 ------
    idx_range = np.where((np.arange(n) >= start) & (state == "range"))[0]
    if len(idx_range) > 0:
        rh = range_high[idx_range]
        rl = range_low[idx_range]
        rs = range_size[idx_range]
        valid = rs > 0

        upper_thresh = rh - rs * 0.05
        lower_thresh = rl + rs * 0.05

        prev_close = close[idx_range - 1]
        curr_close = close[idx_range]

        # 上沿做空: prev_close 靠近上沿 & curr_close 回落
        short_cond = valid & (prev_close > upper_thresh) & (curr_close < rh)
        # 下沿做多: prev_close 靠近下沿 & curr_close 反弹
        long_cond = valid & (prev_close < lower_thresh) & (curr_close > rl)

        signals[idx_range[short_cond]] = -1
        strategy_names[idx_range[short_cond]] = "A_Range"
        # long 不覆盖已有 short (同一 bar 不会同时满足)
        signals[idx_range[long_cond]] = 1
        strategy_names[idx_range[long_cond]] = "A_Range"

    # ------ 策略 B: 强趋势 ------
    idx_su = np.where((np.arange(n) >= start) & (state == "strong_up"))[0]
    if len(idx_su) > 0:
        cond = (is_bullish[idx_su] == 1) & (body_ratio[idx_su] > 0.5) & (close_pos[idx_su] > 0.6)
        signals[idx_su[cond]] = 1
        strategy_names[idx_su[cond]] = "B_StrongTrend"

    idx_sd = np.where((np.arange(n) >= start) & (state == "strong_down"))[0]
    if len(idx_sd) > 0:
        cond = (is_bearish[idx_sd] == 1) & (body_ratio[idx_sd] > 0.5) & (close_pos[idx_sd] < 0.4)
        signals[idx_sd[cond]] = -1
        strategy_names[idx_sd[cond]] = "B_StrongTrend"

    # ------ 策略 C: 弱趋势 ------
    idx_wu = np.where((np.arange(n) >= start) & (state == "weak_up"))[0]
    if len(idx_wu) > 0:
        prev_doji_or_bear = (is_doji[idx_wu - 1] == 1) | (is_bearish[idx_wu - 1] == 1)
        curr_bull = is_bullish[idx_wu] == 1
        close_ok = (close[idx_wu] > low[idx_wu - 1]) & (low[idx_wu] <= low[idx_wu - 1] * 1.001)
        cond = prev_doji_or_bear & curr_bull & close_ok
        signals[idx_wu[cond]] = 1
        strategy_names[idx_wu[cond]] = "C_WeakTrend"

    idx_wd = np.where((np.arange(n) >= start) & (state == "weak_down"))[0]
    if len(idx_wd) > 0:
        prev_doji_or_bull = (is_doji[idx_wd - 1] == 1) | (is_bullish[idx_wd - 1] == 1)
        curr_bear = is_bearish[idx_wd] == 1
        close_ok = (close[idx_wd] < high[idx_wd - 1]) & (high[idx_wd] >= high[idx_wd - 1] * 0.999)
        cond = prev_doji_or_bull & curr_bear & close_ok
        signals[idx_wd[cond]] = -1
        strategy_names[idx_wd[cond]] = "C_WeakTrend"

    df["signal"] = signals
    df["strategy_name"] = strategy_names
    return df


# ============================================================
# 回测引擎
# ============================================================
class BacktestEngine:
    def __init__(self, df, initial_capital=INITIAL_CAPITAL):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.position = 0          # 1=多, -1=空, 0=无
        self.entry_price = 0.0
        self.entry_idx = 0
        self.entry_strategy = ""
        self.trades = []

        # 预提取 numpy 数组，避免 iloc 开销
        self.timestamps = df["timestamp"].values
        self.opens = df["open"].values.astype(np.float64)
        self.highs = df["high"].values.astype(np.float64)
        self.lows = df["low"].values.astype(np.float64)
        self.closes = df["close"].values.astype(np.float64)
        self.signals = df["signal"].values
        self.strat_names = df["strategy_name"].values
        self.n = len(df)

    def run(self):
        print("  开始回测...")
        # 每隔一段记录净值 (全部记录太大，每10根记一次)
        equity_ts = []
        equity_vals = []
        sample_rate = 10

        for i in range(self.n):
            # 先检查止盈止损
            if self.position != 0:
                self._check_exit(i)

            # 如果无仓位，检查信号开仓
            if self.position == 0 and self.signals[i] != 0:
                self._open_position(i)

            # 每 sample_rate 根K线记录一次净值
            if i % sample_rate == 0:
                equity = self.capital
                if self.position != 0:
                    unrealized = self.position * (self.closes[i] - self.entry_price) / self.entry_price
                    equity = self.capital * (1 + unrealized * POSITION_SIZE_PCT)
                equity_ts.append(self.timestamps[i])
                equity_vals.append(equity)

        # 强制平仓
        if self.position != 0:
            self._close_position_at_price(self.closes[-1], self.n - 1, "end_of_backtest")

        # 最后一个净值点
        equity_ts.append(self.timestamps[-1])
        equity_vals.append(self.capital)

        equity_df = pd.DataFrame({"timestamp": equity_ts, "equity": equity_vals})
        return self._compute_stats(equity_df)

    def _open_position(self, idx):
        self.position = int(self.signals[idx])
        self.entry_price = self.closes[idx]
        self.entry_idx = idx
        self.entry_strategy = self.strat_names[idx]

    def _check_exit(self, idx):
        h = self.highs[idx]
        l = self.lows[idx]

        if self.position == 1:  # 多仓
            loss_pct = (self.entry_price - l) / self.entry_price
            gain_pct = (h - self.entry_price) / self.entry_price
            if loss_pct >= SL_PCT:
                self._close_position_at_price(self.entry_price * (1 - SL_PCT), idx, "stop_loss")
            elif gain_pct >= TP_PCT:
                self._close_position_at_price(self.entry_price * (1 + TP_PCT), idx, "take_profit")
        else:  # 空仓
            loss_pct = (h - self.entry_price) / self.entry_price
            gain_pct = (self.entry_price - l) / self.entry_price
            if loss_pct >= SL_PCT:
                self._close_position_at_price(self.entry_price * (1 + SL_PCT), idx, "stop_loss")
            elif gain_pct >= TP_PCT:
                self._close_position_at_price(self.entry_price * (1 - TP_PCT), idx, "take_profit")

    def _close_position_at_price(self, exit_price, idx, reason):
        if self.position == 1:
            gross_pnl = (exit_price - self.entry_price) / self.entry_price
        else:
            gross_pnl = (self.entry_price - exit_price) / self.entry_price

        net_pnl = gross_pnl - TOTAL_FRICTION
        self.capital += self.capital * net_pnl * POSITION_SIZE_PCT

        self.trades.append((
            self.timestamps[self.entry_idx],  # entry_time
            self.timestamps[idx],              # exit_time
            1 if self.position == 1 else -1,   # direction
            self.entry_price,
            exit_price,
            gross_pnl,
            net_pnl,
            self.capital,
            reason,
            self.entry_strategy,
            idx - self.entry_idx,
        ))
        self.position = 0
        self.entry_price = 0.0

    def _compute_stats(self, equity_df):
        if not self.trades:
            return {"error": "没有产生任何交易"}

        trades_df = pd.DataFrame(self.trades, columns=[
            "entry_time", "exit_time", "direction", "entry_price", "exit_price",
            "gross_pnl_pct", "net_pnl_pct", "capital_after", "reason", "strategy", "hold_bars",
        ])
        trades_df["direction_str"] = np.where(trades_df["direction"] == 1, "LONG", "SHORT")

        total_trades = len(trades_df)
        winning = trades_df[trades_df["net_pnl_pct"] > 0]
        losing = trades_df[trades_df["net_pnl_pct"] <= 0]
        win_rate = len(winning) / total_trades

        total_return = (self.capital / self.initial_capital) - 1
        avg_pnl = trades_df["net_pnl_pct"].mean()
        avg_win = winning["net_pnl_pct"].mean() if len(winning) > 0 else 0
        avg_loss = losing["net_pnl_pct"].mean() if len(losing) > 0 else 0

        # 最大回撤
        eq = equity_df["equity"].values
        running_max = np.maximum.accumulate(eq)
        drawdown = (eq - running_max) / running_max
        max_dd = drawdown.min()

        # 夏普
        if len(eq) > 1:
            rets = np.diff(eq) / eq[:-1]
            bars_per_year = 365 * 24 * 12
            sharpe = (np.mean(rets) / np.std(rets) * np.sqrt(bars_per_year)) if np.std(rets) > 0 else 0
        else:
            sharpe = 0

        # Profit Factor
        loss_sum = losing["net_pnl_pct"].sum()
        profit_factor = abs(winning["net_pnl_pct"].sum() / loss_sum) if loss_sum != 0 else float("inf")

        # 按策略分组
        strategy_stats = {}
        for name, group in trades_df.groupby("strategy"):
            sw = group[group["net_pnl_pct"] > 0]
            sl = group[group["net_pnl_pct"] <= 0]
            strategy_stats[name] = {
                "trades": len(group),
                "win_rate": len(sw) / len(group) if len(group) > 0 else 0,
                "avg_pnl": group["net_pnl_pct"].mean(),
                "total_pnl": group["net_pnl_pct"].sum(),
                "avg_win": sw["net_pnl_pct"].mean() if len(sw) > 0 else 0,
                "avg_loss": sl["net_pnl_pct"].mean() if len(sl) > 0 else 0,
                "best_trade": group["net_pnl_pct"].max(),
                "worst_trade": group["net_pnl_pct"].min(),
            }

        # 按月统计
        trades_df["month"] = pd.to_datetime(trades_df["entry_time"]).dt.to_period("M")
        monthly_stats = trades_df.groupby("month").agg(
            trades=("net_pnl_pct", "count"),
            total_pnl=("net_pnl_pct", "sum"),
            win_rate=("net_pnl_pct", lambda x: (x > 0).mean()),
        ).to_dict("index")

        avg_hold = trades_df["hold_bars"].mean()
        median_hold = trades_df["hold_bars"].median()

        return {
            "total_trades": total_trades,
            "win_rate": win_rate,
            "total_return": total_return,
            "avg_pnl": avg_pnl,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "max_drawdown": max_dd,
            "sharpe_ratio": sharpe,
            "profit_factor": profit_factor,
            "final_capital": self.capital,
            "avg_hold_bars": avg_hold,
            "median_hold_bars": median_hold,
            "strategy_stats": strategy_stats,
            "monthly_stats": {str(k): v for k, v in monthly_stats.items()},
            "trades_df": trades_df,
            "equity_df": equity_df,
        }


# ============================================================
# 报告输出
# ============================================================
def print_report(stats):
    if "error" in stats:
        print(f"\n  ❌ {stats['error']}")
        return

    print("\n" + "=" * 70)
    print("  📊 BTC 5分钟 剥头皮策略回测报告")
    print("=" * 70)

    print(f"\n  ── 整体表现 ─────────────────────────────────")
    print(f"  总交易次数:     {stats['total_trades']}")
    print(f"  胜率:           {stats['win_rate']:.1%}")
    print(f"  总收益率:       {stats['total_return']:.2%}")
    print(f"  最终资金:       ${stats['final_capital']:,.2f}")
    print(f"  最大回撤:       {stats['max_drawdown']:.2%}")
    print(f"  夏普比率:       {stats['sharpe_ratio']:.2f}")
    print(f"  盈亏比 (PF):    {stats['profit_factor']:.2f}")
    print(f"  平均每笔收益:   {stats['avg_pnl']:.4%}")
    print(f"  平均盈利笔:     {stats['avg_win']:.4%}")
    print(f"  平均亏损笔:     {stats['avg_loss']:.4%}")
    print(f"  平均持仓:       {stats['avg_hold_bars']:.1f} 根K线 ({stats['avg_hold_bars'] * 5:.0f} 分钟)")
    print(f"  中位持仓:       {stats['median_hold_bars']:.0f} 根K线 ({stats['median_hold_bars'] * 5:.0f} 分钟)")

    print(f"\n  ── 各策略表现 ───────────────────────────────")
    print(f"  {'策略':<16}{'交易数':>8}{'胜率':>8}{'平均盈亏':>10}{'总盈亏':>10}{'最佳':>10}{'最差':>10}")
    print("  " + "-" * 72)
    for name, s in stats["strategy_stats"].items():
        print(f"  {name:<16}{s['trades']:>8}{s['win_rate']:>7.1%}{s['avg_pnl']:>10.4%}{s['total_pnl']:>10.4%}{s['best_trade']:>10.4%}{s['worst_trade']:>10.4%}")

    print(f"\n  ── 月度表现 ─────────────────────────────────")
    print(f"  {'月份':<12}{'交易数':>8}{'总盈亏':>10}{'胜率':>8}")
    print("  " + "-" * 40)
    for month, m in sorted(stats["monthly_stats"].items()):
        print(f"  {month:<12}{m['trades']:>8}{m['total_pnl']:>10.4%}{m['win_rate']:>7.1%}")

    # 关键观察
    print(f"\n  ── 关键发现 ─────────────────────────────────")
    if stats["win_rate"] < 0.7:
        print(f"  ⚠️  胜率 {stats['win_rate']:.1%} 低于70%阈值，剥头皮策略在该盈亏比下难以盈利")
    if stats["win_rate"] >= 0.8:
        print(f"  ✅ 胜率 {stats['win_rate']:.1%} 达到80%以上，具备长期盈利基础")
    if stats["max_drawdown"] < -0.1:
        print(f"  ⚠️  最大回撤 {stats['max_drawdown']:.1%} 超过10%，风控需加强")
    if stats["profit_factor"] > 1.5:
        print(f"  ✅ 盈亏比 {stats['profit_factor']:.2f} 较好")
    elif stats["profit_factor"] < 1.0:
        print(f"  ❌ 盈亏比 {stats['profit_factor']:.2f} < 1，策略亏损")

    # 手续费影响分析
    trades_df = stats["trades_df"]
    gross_total = trades_df["gross_pnl_pct"].sum()
    net_total = trades_df["net_pnl_pct"].sum()
    friction = gross_total - net_total
    print(f"\n  ── 摩擦成本分析 ─────────────────────────────")
    print(f"  毛利润总和:     {gross_total:.4%}")
    print(f"  净利润总和:     {net_total:.4%}")
    print(f"  摩擦成本总和:   {friction:.4%} (手续费+滑点)")
    if gross_total != 0:
        print(f"  摩擦占毛利比:   {friction / abs(gross_total):.1%}")


def plot_report(stats, save_dir):
    """绘制回测报告图表"""
    if "error" in stats:
        return None

    equity_df = stats["equity_df"]
    trades_df = stats["trades_df"]

    fig, axes = plt.subplots(4, 1, figsize=(16, 16),
                             gridspec_kw={"height_ratios": [3, 1.5, 1.5, 1.5]})

    # 1. 净值曲线
    ax1 = axes[0]
    ts = pd.to_datetime(equity_df["timestamp"])
    ax1.plot(ts, equity_df["equity"], color="#2196F3", linewidth=1, label="策略净值")
    ax1.axhline(y=INITIAL_CAPITAL, color="gray", linestyle="--", alpha=0.5, label="初始资金")
    ax1.set_title(
        f"BTC 5分钟剥头皮策略  |  收益 {stats['total_return']:.1%}  "
        f"胜率 {stats['win_rate']:.1%}  最大回撤 {stats['max_drawdown']:.1%}  "
        f"夏普 {stats['sharpe_ratio']:.2f}  交易 {stats['total_trades']}次",
        fontsize=13, fontweight="bold",
    )
    ax1.set_ylabel("资金 (USDT)")
    ax1.legend(fontsize=10)
    ax1.grid(True, alpha=0.3)

    # 2. 回撤
    ax2 = axes[1]
    eq = equity_df["equity"].values
    rm = np.maximum.accumulate(eq)
    dd = (eq - rm) / rm
    ax2.fill_between(ts, dd, 0, color="red", alpha=0.4)
    ax2.set_title("回撤", fontsize=11)
    ax2.set_ylabel("回撤比例")
    ax2.grid(True, alpha=0.3)

    # 3. 每笔交易盈亏
    ax3 = axes[2]
    colors = ["#4CAF50" if p > 0 else "#F44336" for p in trades_df["net_pnl_pct"]]
    ax3.bar(range(len(trades_df)), trades_df["net_pnl_pct"] * 100,
            color=colors, alpha=0.7, width=1)
    ax3.axhline(y=0, color="black", linewidth=0.5)
    ax3.set_title("每笔交易盈亏 (%)", fontsize=11)
    ax3.set_ylabel("盈亏 %")
    ax3.set_xlabel("交易序号")
    ax3.grid(True, alpha=0.3, axis="y")

    # 4. 各策略对比
    ax4 = axes[3]
    strats = list(stats["strategy_stats"].keys())
    if strats:
        x = np.arange(len(strats))
        tc = [stats["strategy_stats"][s]["trades"] for s in strats]
        wr = [stats["strategy_stats"][s]["win_rate"] * 100 for s in strats]

        ax4.bar(x - 0.2, tc, 0.35, label="交易数", color="#2196F3", alpha=0.7)
        ax4t = ax4.twinx()
        ax4t.bar(x + 0.2, wr, 0.35, label="胜率%", color="#FF9800", alpha=0.7)

        ax4.set_xticks(x)
        ax4.set_xticklabels([s.replace("_", "\n") for s in strats])
        ax4.set_ylabel("交易数")
        ax4t.set_ylabel("胜率 (%)")
        ax4.set_title("各策略对比", fontsize=11)
        ax4.legend(loc="upper left")
        ax4t.legend(loc="upper right")
        ax4.grid(True, alpha=0.3, axis="y")

    plt.tight_layout()
    out_path = os.path.join(save_dir, "btc_scalping_backtest.png")
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\n  📈 图表已保存: {out_path}")
    return out_path


# ============================================================
# 主流程
# ============================================================
def main():
    print("=" * 70)
    print("  BTC 5分钟 剥头皮策略回测")
    print("=" * 70)
    print(f"  交易对:         {SYMBOL}")
    print(f"  K线周期:        {TIMEFRAME}")
    print(f"  止盈:           {TP_PCT:.2%}")
    print(f"  止损:           {SL_PCT:.2%}")
    print(f"  盈亏比:         1:{SL_PCT/TP_PCT:.0f}")
    print(f"  手续费(单边):   {COMMISSION_RATE:.4%}")
    print(f"  滑点(单边):     {SLIPPAGE_RATE:.4%}")
    print(f"  总摩擦(双边):   {TOTAL_FRICTION:.4%}")
    print(f"  初始资金:       ${INITIAL_CAPITAL:,.0f}")
    print("=" * 70)

    # 获取数据
    df = fetch_ohlcv(days=365)

    # 计算指标
    print("\n  计算技术指标...")
    df = compute_indicators(df)

    # 统计市场状态分布
    state_counts = pd.Series(df["market_state"]).value_counts()
    print(f"\n  市场状态分布:")
    for state, count in state_counts.items():
        print(f"    {state:<14} {count:>6} ({count/len(df):.1%})")

    # 生成信号
    print("\n  生成交易信号...")
    df = generate_signals(df)
    signal_counts = df[df["signal"] != 0]["strategy_name"].value_counts()
    print(f"  信号分布:")
    for name, count in signal_counts.items():
        print(f"    {name:<16} {count:>6} 次")

    # 回测
    engine = BacktestEngine(df)
    stats = engine.run()

    # 输出报告
    print_report(stats)

    # 绘图
    plot_report(stats, CACHE_DIR)

    # 保存JSON结果
    if "error" not in stats:
        result_json = {
            "strategy": "BTC 5min Scalping",
            "params": {
                "tp": TP_PCT, "sl": SL_PCT,
                "commission": COMMISSION_RATE, "slippage": SLIPPAGE_RATE,
                "ema_fast": EMA_FAST, "ema_slow": EMA_SLOW,
            },
            "results": {
                "total_trades": stats["total_trades"],
                "win_rate": f"{stats['win_rate']:.2%}",
                "total_return": f"{stats['total_return']:.2%}",
                "max_drawdown": f"{stats['max_drawdown']:.2%}",
                "sharpe_ratio": f"{stats['sharpe_ratio']:.2f}",
                "profit_factor": f"{stats['profit_factor']:.2f}",
                "final_capital": f"${stats['final_capital']:,.2f}",
            },
            "strategy_stats": {
                k: {kk: f"{vv:.4%}" if isinstance(vv, float) else vv for kk, vv in v.items()}
                for k, v in stats["strategy_stats"].items()
            },
            "monthly_stats": {
                k: {kk: f"{vv:.4%}" if isinstance(vv, float) else vv for kk, vv in v.items()}
                for k, v in stats["monthly_stats"].items()
            },
        }
        result_path = os.path.join(CACHE_DIR, "backtest_result.json")
        with open(result_path, "w") as f:
            json.dump(result_json, f, ensure_ascii=False, indent=2)
        print(f"  📄 结果已保存: {result_path}")

    return stats


if __name__ == "__main__":
    main()
