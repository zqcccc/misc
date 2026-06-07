import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

SYMBOL = "BTC/USDT"
TIMEFRAME = "5m"
DAYS = 365
INITIAL_CAPITAL = 10_000.0
COMMISSION_RATE = 0.0004
SLIPPAGE_RATE = 0.0001
TOTAL_FRICTION = (COMMISSION_RATE + SLIPPAGE_RATE) * 2
RISK_PER_TRADE = 0.008
MAX_POSITION_SIZE = 0.25
MAX_TOTAL_POSITION_SIZE = 0.25
MAX_OPEN_POSITIONS = 1
MIN_POSITION_SIZE = 0.05
MIN_STOP_PCT = 0.0025
WARMUP_BARS = 120
EMA_FAST = 20
EMA_SLOW = 50
ATR_WINDOW = 14
ATR_AVG_WINDOW = 72
RANGE_LOOKBACK = 48
VOLUME_WINDOW = 48
OVERLAP_LOOKBACK = 20
IMPULSE_LOOKBACK = 8
CHANNEL_MEMORY_LOOKBACK = 18
BREAKOUT_BODY_RATIO = 0.55
BREAKOUT_CLOSE_UP = 0.70
BREAKOUT_CLOSE_DOWN = 0.30
BREAKOUT_VOLUME_MULT = 1.05
RANGE_OVERLAP_THRESHOLD = 0.58
TREND_SLOPE_THRESHOLD = 0.0007
TIGHT_MAX_PULLBACK_ATR = 1.5
BROAD_PULLBACK_ATR = 2.2
BROAD_TO_RANGE_BARS = 30
MIN_BARS_BETWEEN_SIGNALS = 12
FALSE_BREAKOUT_ATR = 0.15
STATE_RANGE = "trading_range"
STATE_BREAKOUT_UP = "breakout_up"
STATE_BREAKOUT_DOWN = "breakout_down"
STATE_TIGHT_UP = "tight_channel_up"
STATE_TIGHT_DOWN = "tight_channel_down"
STATE_BROAD_UP = "broad_channel_up"
STATE_BROAD_DOWN = "broad_channel_down"
STRATEGY_BREAKOUT = "A_Breakout"
STRATEGY_TIGHT = "B_TightChannel"
STRATEGY_BROAD = "C_BroadChannel"
STRATEGY_RANGE = "D_TradingRange"
ALLOW_RANGE_LONG = False
ALLOW_RANGE_SHORT = False
ALLOW_BREAKOUT_UP = False
ALLOW_BREAKOUT_DOWN = True
ALLOW_TIGHT_CHANNEL = False
ALLOW_BROAD_CHANNEL = False
EXIT_STOP = "stop_loss"
EXIT_TARGET = "take_profit"
EXIT_TRAIL = "trailing_stop"
EXIT_CYCLE_SHIFT = "cycle_shift"
EXIT_END = "end_of_backtest"
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_cache_btc_scalp")
CACHE_PATH = os.path.join(CACHE_DIR, f"ohlcv_{SYMBOL.replace('/', '_')}_{TIMEFRAME}_{DAYS}d.csv")
RESULT_JSON_PATH = os.path.join(CACHE_DIR, "btc_market_cycle_state_result.json")
TRADES_CSV_PATH = os.path.join(CACHE_DIR, "btc_market_cycle_state_trades.csv")


@dataclass
class CycleDecision:
    signal: int = 0
    strategy: str = ""
    stop_price: float = np.nan
    target_price: float = np.nan
    state: str = STATE_RANGE
    transition: str = ""


@dataclass
class CycleMemory:
    state: str = STATE_RANGE
    direction: int = 0
    bars_in_state: int = 0
    impulse_start_price: float = np.nan
    impulse_extreme: float = np.nan
    channel_high: float = np.nan
    channel_low: float = np.nan
    major_low: float = np.nan
    major_high: float = np.nan
    range_high: float = np.nan
    range_low: float = np.nan
    pullback_extreme: float = np.nan
    pullback_bars: int = 0
    resumed_pullback: bool = False
    resumed_pullback_extreme: float = np.nan
    failed_reversal_seen: bool = False
    last_signal_idx: int = -10_000
    last_transition_idx: int = 0


@dataclass
class Position:
    direction: int
    entry_idx: int
    entry_time: object
    entry_price: float
    stop_price: float
    target_price: float
    size_pct: float
    risk_distance_pct: float
    state: str
    strategy: str
    best_price: float
    major_stop_anchor: float


def fetch_ohlcv():
    os.makedirs(CACHE_DIR, exist_ok=True)
    if os.path.exists(CACHE_PATH):
        df = pd.read_csv(CACHE_PATH, parse_dates=["timestamp"])
        print(f"从缓存加载 {len(df)} 根K线: {CACHE_PATH}")
        return df

    import ccxt

    print(f"正在从交易所获取 {SYMBOL} {TIMEFRAME} K线数据 ({DAYS}天)")
    exchange = ccxt.binance({"enableRateLimit": True})
    since = exchange.parse8601((datetime.utcnow() - timedelta(days=DAYS)).isoformat())
    all_data = []
    limit = 1000

    while True:
        try:
            ohlcv = exchange.fetch_ohlcv(SYMBOL, TIMEFRAME, since=since, limit=limit)
        except Exception as exc:
            print(f"获取出错: {exc}，5秒后重试")
            time.sleep(5)
            continue

        if not ohlcv:
            break
        all_data.extend(ohlcv)
        since = ohlcv[-1][0] + 1
        print(f"已获取 {len(all_data)} 根K线")
        time.sleep(0.5)
        if len(ohlcv) < limit:
            break

    df = pd.DataFrame(all_data, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df = df.drop_duplicates(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
    df.to_csv(CACHE_PATH, index=False)
    print(f"共获取 {len(df)} 根K线并写入缓存")
    return df


def compute_indicators(df):
    df = df.copy()
    df["ema_fast"] = df["close"].ewm(span=EMA_FAST, adjust=False).mean()
    df["ema_slow"] = df["close"].ewm(span=EMA_SLOW, adjust=False).mean()
    df["ema_slope"] = df["ema_slow"].pct_change(CHANNEL_MEMORY_LOOKBACK)
    df["body"] = (df["close"] - df["open"]).abs()
    df["bar_range"] = df["high"] - df["low"]
    df["body_ratio"] = np.where(df["bar_range"] > 0, df["body"] / df["bar_range"], 0.0)
    df["close_position"] = np.where(df["bar_range"] > 0, (df["close"] - df["low"]) / df["bar_range"], 0.5)
    df["prev_close"] = df["close"].shift(1)
    df["true_range"] = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["prev_close"]).abs(),
        (df["low"] - df["prev_close"]).abs(),
    ], axis=1).max(axis=1)
    df["atr"] = df["true_range"].ewm(span=ATR_WINDOW, adjust=False).mean()
    df["atr_pct"] = df["atr"] / df["close"]
    df["atr_pct_avg"] = df["atr_pct"].rolling(ATR_AVG_WINDOW, min_periods=ATR_AVG_WINDOW).mean()
    df["volume_ma"] = df["volume"].rolling(VOLUME_WINDOW, min_periods=VOLUME_WINDOW).mean()
    df["range_high"] = df["high"].rolling(RANGE_LOOKBACK, min_periods=RANGE_LOOKBACK).max().shift(1)
    df["range_low"] = df["low"].rolling(RANGE_LOOKBACK, min_periods=RANGE_LOOKBACK).min().shift(1)
    df["range_size"] = df["range_high"] - df["range_low"]
    df["range_position"] = np.where(df["range_size"] > 0, (df["close"] - df["range_low"]) / df["range_size"], 0.5)
    df["overlap_ratio"] = overlap_ratio(df["high"].to_numpy(), df["low"].to_numpy(), OVERLAP_LOOKBACK)
    return df


def overlap_ratio(highs, lows, lookback):
    result = np.zeros(len(highs))
    if len(highs) <= lookback:
        return result
    prev_high = highs[:-1]
    curr_high = highs[1:]
    prev_low = lows[:-1]
    curr_low = lows[1:]
    overlap_top = np.minimum(prev_high, curr_high)
    overlap_bottom = np.maximum(prev_low, curr_low)
    total_range = np.maximum(prev_high, curr_high) - np.minimum(prev_low, curr_low)
    pair_overlap = np.where(total_range > 0, np.maximum(0, overlap_top - overlap_bottom) / total_range, 0.0)
    cumsum = np.concatenate([[0.0], np.cumsum(pair_overlap)])
    idx = np.arange(lookback, len(highs))
    result[idx] = (cumsum[idx - 1] - cumsum[idx - lookback]) / (lookback - 1)
    return result


class MarketCycleStateMachine:
    def __init__(self, df):
        self.df = df
        self.memory = CycleMemory()
        self.states = np.full(len(df), STATE_RANGE, dtype=object)
        self.transitions = np.full(len(df), "", dtype=object)

    def update(self, i):
        if i < WARMUP_BARS or not np.isfinite(self.df.at[i, "atr"]):
            self.states[i] = self.memory.state
            return CycleDecision(state=self.memory.state)

        decision = CycleDecision(state=self.memory.state)
        self.memory.bars_in_state += 1
        self.refresh_range_memory(i)
        self.update_cycle_memory(i)

        opposite_breakout = self.detect_breakout(i, allow_any_state=True)
        if self.memory.state != STATE_RANGE and opposite_breakout != 0 and opposite_breakout != self.memory.direction:
            decision = self.enter_breakout(i, opposite_breakout, "opposite_breakout")
        elif self.memory.state == STATE_RANGE:
            decision = self.handle_range(i)
        elif self.memory.state in (STATE_BREAKOUT_UP, STATE_BREAKOUT_DOWN):
            decision = self.handle_breakout(i)
        elif self.memory.state in (STATE_TIGHT_UP, STATE_TIGHT_DOWN):
            decision = self.handle_tight_channel(i)
        elif self.memory.state in (STATE_BROAD_UP, STATE_BROAD_DOWN):
            decision = self.handle_broad_channel(i)

        self.states[i] = self.memory.state
        self.transitions[i] = decision.transition
        decision.state = self.memory.state
        return decision

    def refresh_range_memory(self, i):
        range_high = self.df.at[i, "range_high"]
        range_low = self.df.at[i, "range_low"]
        if self.memory.state == STATE_RANGE and np.isfinite(range_high) and np.isfinite(range_low):
            self.memory.range_high = range_high
            self.memory.range_low = range_low

    def update_cycle_memory(self, i):
        high = self.df.at[i, "high"]
        low = self.df.at[i, "low"]
        close = self.df.at[i, "close"]
        direction = self.memory.direction

        self.memory.resumed_pullback = False
        self.memory.resumed_pullback_extreme = np.nan

        if self.memory.state == STATE_RANGE:
            return

        if direction == 1:
            self.memory.channel_high = high if not np.isfinite(self.memory.channel_high) else max(self.memory.channel_high, high)
            self.memory.channel_low = low if not np.isfinite(self.memory.channel_low) else min(self.memory.channel_low, low)
            self.memory.impulse_extreme = high if not np.isfinite(self.memory.impulse_extreme) else max(self.memory.impulse_extreme, high)
            if close < self.df.at[i, "ema_fast"]:
                self.memory.pullback_bars += 1
                self.memory.pullback_extreme = low if not np.isfinite(self.memory.pullback_extreme) else min(self.memory.pullback_extreme, low)
            elif self.memory.pullback_bars > 0:
                self.memory.resumed_pullback = True
                self.memory.resumed_pullback_extreme = self.memory.pullback_extreme
                if high >= self.memory.channel_high and np.isfinite(self.memory.pullback_extreme):
                    self.memory.major_low = self.pullback_anchor(self.memory.major_low, self.memory.pullback_extreme, direction)
                self.memory.pullback_bars = 0
                self.memory.pullback_extreme = np.nan
        elif direction == -1:
            self.memory.channel_high = high if not np.isfinite(self.memory.channel_high) else max(self.memory.channel_high, high)
            self.memory.channel_low = low if not np.isfinite(self.memory.channel_low) else min(self.memory.channel_low, low)
            self.memory.impulse_extreme = low if not np.isfinite(self.memory.impulse_extreme) else min(self.memory.impulse_extreme, low)
            if close > self.df.at[i, "ema_fast"]:
                self.memory.pullback_bars += 1
                self.memory.pullback_extreme = high if not np.isfinite(self.memory.pullback_extreme) else max(self.memory.pullback_extreme, high)
            elif self.memory.pullback_bars > 0:
                self.memory.resumed_pullback = True
                self.memory.resumed_pullback_extreme = self.memory.pullback_extreme
                if low <= self.memory.channel_low and np.isfinite(self.memory.pullback_extreme):
                    self.memory.major_high = self.pullback_anchor(self.memory.major_high, self.memory.pullback_extreme, direction)
                self.memory.pullback_bars = 0
                self.memory.pullback_extreme = np.nan

    def pullback_anchor(self, current_anchor, pullback_extreme, direction):
        if not np.isfinite(current_anchor):
            return pullback_extreme
        if direction == 1:
            return max(current_anchor, pullback_extreme)
        return min(current_anchor, pullback_extreme)

    def handle_range(self, i):
        breakout_direction = self.detect_breakout(i, allow_any_state=False)
        if breakout_direction != 0:
            return self.enter_breakout(i, breakout_direction, "range_breakout")
        return self.detect_false_breakout(i)

    def handle_breakout(self, i):
        direction = self.memory.direction
        if self.breakout_failed(i):
            self.enter_range(i, "breakout_failed")
            return CycleDecision(state=self.memory.state, transition="breakout_failed")

        if self.memory.bars_in_state >= 3 and self.tight_channel_confirmed(i):
            self.enter_channel(i, tight=True, transition="breakout_to_tight")
            return CycleDecision(state=self.memory.state, transition="breakout_to_tight")

        if self.can_signal(i):
            self.memory.last_signal_idx = i
            return self.build_breakout_decision(i, direction)
        return CycleDecision(state=self.memory.state)

    def handle_tight_channel(self, i):
        direction = self.memory.direction
        if self.first_failed_reversal(i, direction) and i - self.memory.last_signal_idx >= 2:
            self.memory.failed_reversal_seen = True
            self.memory.last_signal_idx = i
            return self.build_tight_decision(i, direction)

        if self.tight_channel_broke(i):
            self.enter_channel(i, tight=False, transition="tight_to_broad")
            return CycleDecision(state=self.memory.state, transition="tight_to_broad")

        if self.trend_invalidated(i):
            self.enter_range(i, "tight_to_range")
            return CycleDecision(state=self.memory.state, transition="tight_to_range")

        return CycleDecision(state=self.memory.state)

    def handle_broad_channel(self, i):
        if self.trend_invalidated(i) or self.broad_channel_exhausted(i):
            self.enter_range(i, "broad_to_range")
            return CycleDecision(state=self.memory.state, transition="broad_to_range")

        direction = self.memory.direction
        if self.broad_pullback_resumed(i, direction) and self.can_signal(i):
            self.memory.last_signal_idx = i
            return self.build_broad_decision(i, direction)
        return CycleDecision(state=self.memory.state)

    def detect_breakout(self, i, allow_any_state):
        range_high = self.memory.range_high if np.isfinite(self.memory.range_high) else self.df.at[i, "range_high"]
        range_low = self.memory.range_low if np.isfinite(self.memory.range_low) else self.df.at[i, "range_low"]
        if not np.isfinite(range_high) or not np.isfinite(range_low):
            return 0

        close = self.df.at[i, "close"]
        volume = self.df.at[i, "volume"]
        volume_ma = self.df.at[i, "volume_ma"]
        body_ratio = self.df.at[i, "body_ratio"]
        close_position = self.df.at[i, "close_position"]
        atr_pct = self.df.at[i, "atr_pct"]
        atr_pct_avg = self.df.at[i, "atr_pct_avg"]
        ema_fast = self.df.at[i, "ema_fast"]
        ema_slow = self.df.at[i, "ema_slow"]
        ema_slope = self.df.at[i, "ema_slope"]
        vol_ok = np.isfinite(volume_ma) and volume >= volume_ma * BREAKOUT_VOLUME_MULT
        atr_ok = np.isfinite(atr_pct_avg) and atr_pct >= atr_pct_avg * 0.9
        strong_up = close > range_high and body_ratio >= BREAKOUT_BODY_RATIO and close_position >= BREAKOUT_CLOSE_UP
        strong_down = close < range_low and body_ratio >= BREAKOUT_BODY_RATIO and close_position <= BREAKOUT_CLOSE_DOWN

        if not allow_any_state and self.memory.state != STATE_RANGE:
            return 0
        if strong_up and vol_ok and atr_ok and ema_slope >= -TREND_SLOPE_THRESHOLD:
            return 1
        if strong_down and vol_ok and atr_ok and ema_fast < ema_slow and close < ema_slow and ema_slope <= TREND_SLOPE_THRESHOLD:
            return -1
        return 0

    def enter_breakout(self, i, direction, transition):
        atr = self.df.at[i, "atr"]
        start = max(0, i - IMPULSE_LOOKBACK)
        if direction == 1:
            impulse_start = min(self.df["low"].iloc[start:i + 1].min(), self.memory.range_low)
            extreme = self.df.at[i, "high"]
            state = STATE_BREAKOUT_UP
        else:
            impulse_start = max(self.df["high"].iloc[start:i + 1].max(), self.memory.range_high)
            extreme = self.df.at[i, "low"]
            state = STATE_BREAKOUT_DOWN

        self.memory.state = state
        self.memory.direction = direction
        self.memory.bars_in_state = 0
        self.memory.impulse_start_price = impulse_start
        self.memory.impulse_extreme = extreme
        self.memory.channel_high = self.df.at[i, "high"]
        self.memory.channel_low = self.df.at[i, "low"]
        self.memory.major_low = impulse_start if direction == 1 else np.nan
        self.memory.major_high = impulse_start if direction == -1 else np.nan
        self.memory.pullback_extreme = np.nan
        self.memory.pullback_bars = 0
        self.memory.resumed_pullback = False
        self.memory.resumed_pullback_extreme = np.nan
        self.memory.failed_reversal_seen = False
        self.memory.last_transition_idx = i
        decision = self.build_breakout_decision(i, direction)
        decision.transition = transition
        self.memory.last_signal_idx = i
        return decision

    def enter_channel(self, i, tight, transition):
        direction = self.memory.direction
        if tight:
            self.memory.state = STATE_TIGHT_UP if direction == 1 else STATE_TIGHT_DOWN
        else:
            self.memory.state = STATE_BROAD_UP if direction == 1 else STATE_BROAD_DOWN
        self.memory.bars_in_state = 0
        self.memory.failed_reversal_seen = False
        self.memory.last_transition_idx = i

    def enter_range(self, i, transition):
        self.memory.state = STATE_RANGE
        self.memory.direction = 0
        self.memory.bars_in_state = 0
        self.memory.range_high = self.df.at[i, "range_high"]
        self.memory.range_low = self.df.at[i, "range_low"]
        self.memory.impulse_start_price = np.nan
        self.memory.impulse_extreme = np.nan
        self.memory.channel_high = np.nan
        self.memory.channel_low = np.nan
        self.memory.major_low = np.nan
        self.memory.major_high = np.nan
        self.memory.pullback_extreme = np.nan
        self.memory.pullback_bars = 0
        self.memory.resumed_pullback = False
        self.memory.resumed_pullback_extreme = np.nan
        self.memory.failed_reversal_seen = False
        self.memory.last_transition_idx = i

    def build_breakout_decision(self, i, direction):
        entry = self.df.at[i, "close"]
        atr = self.df.at[i, "atr"]
        if direction == 1:
            stop = self.memory.impulse_start_price - atr * 0.2
            target = entry + max(entry - stop, atr) * 3.0
        else:
            stop = self.memory.impulse_start_price + atr * 0.2
            target = entry - max(stop - entry, atr) * 3.0
        return self.validated_decision(i, direction, STRATEGY_BREAKOUT, stop, target)

    def build_tight_decision(self, i, direction):
        entry = self.df.at[i, "close"]
        atr = self.df.at[i, "atr"]
        if direction == 1:
            pullback_extreme = self.memory.resumed_pullback_extreme if np.isfinite(self.memory.resumed_pullback_extreme) else self.df.at[i, "low"]
            stop = min(self.df.at[i, "low"], pullback_extreme) - atr * 0.4
            target = entry + max(entry - stop, atr) * 2.2
        else:
            pullback_extreme = self.memory.resumed_pullback_extreme if np.isfinite(self.memory.resumed_pullback_extreme) else self.df.at[i, "high"]
            stop = max(self.df.at[i, "high"], pullback_extreme) + atr * 0.4
            target = entry - max(stop - entry, atr) * 2.2
        return self.validated_decision(i, direction, STRATEGY_TIGHT, stop, target)

    def build_broad_decision(self, i, direction):
        entry = self.df.at[i, "close"]
        atr = self.df.at[i, "atr"]
        if direction == 1:
            anchor = self.memory.major_low if np.isfinite(self.memory.major_low) else self.memory.channel_low
            stop = anchor - atr * 0.35
            target = self.memory.channel_high if np.isfinite(self.memory.channel_high) and self.memory.channel_high > entry else entry + max(entry - stop, atr) * 1.8
        else:
            anchor = self.memory.major_high if np.isfinite(self.memory.major_high) else self.memory.channel_high
            stop = anchor + atr * 0.35
            target = self.memory.channel_low if np.isfinite(self.memory.channel_low) and self.memory.channel_low < entry else entry - max(stop - entry, atr) * 1.8
        return self.validated_decision(i, direction, STRATEGY_BROAD, stop, target)

    def detect_false_breakout(self, i):
        range_high = self.memory.range_high
        range_low = self.memory.range_low
        if not np.isfinite(range_high) or not np.isfinite(range_low):
            return CycleDecision(state=self.memory.state)

        atr = self.df.at[i, "atr"]
        open_ = self.df.at[i, "open"]
        high = self.df.at[i, "high"]
        low = self.df.at[i, "low"]
        close = self.df.at[i, "close"]
        if high > range_high + atr * FALSE_BREAKOUT_ATR and close < range_high and close < open_ and self.can_signal(i):
            self.memory.last_signal_idx = i
            stop = high + atr * 0.35
            target = range_low + (range_high - range_low) * 0.2
            return self.validated_decision(i, -1, STRATEGY_RANGE, stop, target)
        if low < range_low - atr * FALSE_BREAKOUT_ATR and close > range_low and close > open_ and self.can_signal(i):
            self.memory.last_signal_idx = i
            stop = low - atr * 0.35
            target = range_high - (range_high - range_low) * 0.2
            return self.validated_decision(i, 1, STRATEGY_RANGE, stop, target)
        return CycleDecision(state=self.memory.state)

    def validated_decision(self, i, direction, strategy, stop, target):
        entry = self.df.at[i, "close"]
        if not signal_allowed(strategy, direction):
            return CycleDecision(state=self.memory.state)
        if not np.isfinite(stop) or not np.isfinite(target):
            return CycleDecision(state=self.memory.state)
        if direction == 1 and stop < entry < target:
            return CycleDecision(direction, strategy, stop, target, self.memory.state)
        if direction == -1 and target < entry < stop:
            return CycleDecision(direction, strategy, stop, target, self.memory.state)
        return CycleDecision(state=self.memory.state)

    def breakout_failed(self, i):
        if self.memory.bars_in_state < 2:
            return False
        close = self.df.at[i, "close"]
        if self.memory.direction == 1:
            return np.isfinite(self.memory.range_high) and close < self.memory.range_high
        return np.isfinite(self.memory.range_low) and close > self.memory.range_low

    def tight_channel_confirmed(self, i):
        start = max(0, i - min(CHANNEL_MEMORY_LOOKBACK, self.memory.bars_in_state + 1))
        closes = self.df["close"].iloc[start:i + 1]
        ema_fast = self.df["ema_fast"].iloc[start:i + 1]
        if self.memory.direction == 1:
            return (closes > ema_fast).mean() >= 0.70
        return (closes < ema_fast).mean() >= 0.70

    def tight_channel_broke(self, i):
        if self.memory.bars_in_state < 4:
            return False
        atr = self.df.at[i, "atr"]
        close = self.df.at[i, "close"]
        if self.memory.direction == 1:
            pullback = self.memory.channel_high - self.df.at[i, "low"]
            return pullback > atr * BROAD_PULLBACK_ATR or self.memory.pullback_bars >= 4
        pullback = self.df.at[i, "high"] - self.memory.channel_low
        return pullback > atr * BROAD_PULLBACK_ATR or self.memory.pullback_bars >= 4

    def trend_invalidated(self, i):
        close = self.df.at[i, "close"]
        ema_slow = self.df.at[i, "ema_slow"]
        overlap = self.df.at[i, "overlap_ratio"]
        if self.memory.direction == 1:
            return close < ema_slow and overlap >= RANGE_OVERLAP_THRESHOLD
        return close > ema_slow and overlap >= RANGE_OVERLAP_THRESHOLD

    def broad_channel_exhausted(self, i):
        return self.memory.bars_in_state > BROAD_TO_RANGE_BARS and self.df.at[i, "overlap_ratio"] >= RANGE_OVERLAP_THRESHOLD

    def first_failed_reversal(self, i, direction):
        if self.memory.failed_reversal_seen:
            return False
        close = self.df.at[i, "close"]
        open_ = self.df.at[i, "open"]
        low = self.df.at[i, "low"]
        high = self.df.at[i, "high"]
        ema_fast = self.df.at[i, "ema_fast"]
        prev_close = self.df.at[i - 1, "close"]
        atr = self.df.at[i, "atr"]
        if direction == 1:
            pullback_extreme = self.memory.resumed_pullback_extreme if self.memory.resumed_pullback else low
            shallow = self.memory.channel_high - pullback_extreme <= atr * TIGHT_MAX_PULLBACK_ATR
            touched = low <= ema_fast * 1.001 or self.memory.resumed_pullback
            return shallow and touched and close > open_ and close > prev_close and close > ema_fast
        pullback_extreme = self.memory.resumed_pullback_extreme if self.memory.resumed_pullback else high
        shallow = pullback_extreme - self.memory.channel_low <= atr * TIGHT_MAX_PULLBACK_ATR
        touched = high >= ema_fast * 0.999 or self.memory.resumed_pullback
        return shallow and touched and close < open_ and close < prev_close and close < ema_fast

    def broad_pullback_resumed(self, i, direction):
        if not self.memory.resumed_pullback:
            return False
        close = self.df.at[i, "close"]
        open_ = self.df.at[i, "open"]
        atr = self.df.at[i, "atr"]
        if direction == 1:
            deep_enough = self.memory.channel_high - self.memory.resumed_pullback_extreme >= atr * BROAD_PULLBACK_ATR
            return deep_enough and close > open_ and close > self.df.at[i, "ema_fast"]
        deep_enough = self.memory.resumed_pullback_extreme - self.memory.channel_low >= atr * BROAD_PULLBACK_ATR
        return deep_enough and close < open_ and close < self.df.at[i, "ema_fast"]

    def can_signal(self, i):
        return i - self.memory.last_signal_idx >= MIN_BARS_BETWEEN_SIGNALS


def signal_allowed(strategy, direction):
    if strategy == STRATEGY_RANGE:
        return (direction == 1 and ALLOW_RANGE_LONG) or (direction == -1 and ALLOW_RANGE_SHORT)
    if strategy == STRATEGY_BREAKOUT:
        return (direction == 1 and ALLOW_BREAKOUT_UP) or (direction == -1 and ALLOW_BREAKOUT_DOWN)
    if strategy == STRATEGY_TIGHT:
        return ALLOW_TIGHT_CHANNEL
    if strategy == STRATEGY_BROAD:
        return ALLOW_BROAD_CHANNEL
    return False


class MarketCycleBacktester:
    def __init__(self, df):
        self.df = df
        self.state_machine = MarketCycleStateMachine(df)
        self.initial_capital = INITIAL_CAPITAL
        self.capital = INITIAL_CAPITAL
        self.positions = []
        self.trades = []
        self.equity_rows = []
        self.state_rows = []
        self.timestamps = df["timestamp"].to_numpy()
        self.high = df["high"].to_numpy(dtype=float)
        self.low = df["low"].to_numpy(dtype=float)
        self.close = df["close"].to_numpy(dtype=float)
        self.atr = df["atr"].to_numpy(dtype=float)

    def run(self):
        print("开始市场周期状态机回测")
        for i in range(len(self.df)):
            decision = self.state_machine.update(i)
            for pos in list(self.positions):
                self.update_trailing_stop(pos, i)
                self.check_exit(pos, i, decision)
            if decision.signal != 0 and self.can_open_position(decision, i):
                self.open_position(i, decision)
            self.record_equity(i)
            self.state_rows.append({"timestamp": self.timestamps[i], "cycle_state": decision.state, "transition": decision.transition})

        had_positions = bool(self.positions)
        for pos in list(self.positions):
            self.close_position(pos, len(self.df) - 1, self.close[-1], EXIT_END)
        if had_positions:
            self.record_equity(len(self.df) - 1)

        self.df["cycle_state"] = self.state_machine.states
        self.df["cycle_transition"] = self.state_machine.transitions
        return self.compute_stats()

    def can_open_position(self, decision, i):
        current_size = sum(pos.size_pct for pos in self.positions)
        remaining_size = MAX_TOTAL_POSITION_SIZE - current_size
        if remaining_size < MIN_POSITION_SIZE:
            return False
        if not self.positions:
            return True
        if any(pos.direction != decision.signal for pos in self.positions):
            return False
        if len(self.positions) >= MAX_OPEN_POSITIONS:
            return False
        return decision.strategy == STRATEGY_TIGHT

    def position_size(self, entry, stop):
        risk_distance_pct = max(abs(entry - stop) / entry, MIN_STOP_PCT)
        return min(MAX_POSITION_SIZE, max(MIN_POSITION_SIZE, RISK_PER_TRADE / risk_distance_pct))

    def open_position(self, i, decision):
        entry = self.close[i]
        risk_distance_pct = max(abs(entry - decision.stop_price) / entry, MIN_STOP_PCT)
        remaining_size = MAX_TOTAL_POSITION_SIZE - sum(pos.size_pct for pos in self.positions)
        size_pct = min(self.position_size(entry, decision.stop_price), remaining_size)
        self.positions.append(Position(
            direction=int(decision.signal),
            entry_idx=i,
            entry_time=self.timestamps[i],
            entry_price=entry,
            stop_price=decision.stop_price,
            target_price=decision.target_price,
            size_pct=size_pct,
            risk_distance_pct=risk_distance_pct,
            state=decision.state,
            strategy=decision.strategy,
            best_price=entry,
            major_stop_anchor=decision.stop_price,
        ))

    def update_trailing_stop(self, pos, i):
        memory = self.state_machine.memory

        if pos.direction == 1:
            pos.best_price = max(pos.best_price, self.high[i])
            if pos.strategy == STRATEGY_BROAD and np.isfinite(memory.major_low):
                pos.stop_price = max(pos.stop_price, memory.major_low - self.atr[i] * 0.35)
            elif pos.strategy in (STRATEGY_BREAKOUT, STRATEGY_TIGHT):
                open_r = (pos.best_price - pos.entry_price) / max(pos.entry_price - pos.major_stop_anchor, pos.entry_price * MIN_STOP_PCT)
                if open_r >= 1.5:
                    pos.stop_price = max(pos.stop_price, pos.entry_price)
        else:
            pos.best_price = min(pos.best_price, self.low[i])
            if pos.strategy == STRATEGY_BROAD and np.isfinite(memory.major_high):
                pos.stop_price = min(pos.stop_price, memory.major_high + self.atr[i] * 0.35)
            elif pos.strategy in (STRATEGY_BREAKOUT, STRATEGY_TIGHT):
                open_r = (pos.entry_price - pos.best_price) / max(pos.major_stop_anchor - pos.entry_price, pos.entry_price * MIN_STOP_PCT)
                if open_r >= 1.5:
                    pos.stop_price = min(pos.stop_price, pos.entry_price)

    def check_exit(self, pos, i, decision):
        if pos.direction == 1:
            if self.low[i] <= pos.stop_price:
                self.close_position(pos, i, pos.stop_price, EXIT_STOP if pos.stop_price <= pos.entry_price else EXIT_TRAIL)
            elif self.high[i] >= pos.target_price:
                self.close_position(pos, i, pos.target_price, EXIT_TARGET)
            elif self.position_cycle_invalid(pos, decision.state):
                self.close_position(pos, i, self.close[i], EXIT_CYCLE_SHIFT)
        else:
            if self.high[i] >= pos.stop_price:
                self.close_position(pos, i, pos.stop_price, EXIT_STOP if pos.stop_price >= pos.entry_price else EXIT_TRAIL)
            elif self.low[i] <= pos.target_price:
                self.close_position(pos, i, pos.target_price, EXIT_TARGET)
            elif self.position_cycle_invalid(pos, decision.state):
                self.close_position(pos, i, self.close[i], EXIT_CYCLE_SHIFT)

    def position_cycle_invalid(self, pos, state):
        if pos.strategy == STRATEGY_RANGE:
            return state in (STATE_BREAKOUT_UP, STATE_BREAKOUT_DOWN)
        if pos.direction == 1:
            return state in (STATE_BREAKOUT_DOWN, STATE_TIGHT_DOWN, STATE_BROAD_DOWN, STATE_RANGE)
        return state in (STATE_BREAKOUT_UP, STATE_TIGHT_UP, STATE_BROAD_UP, STATE_RANGE)

    def close_position(self, pos, i, exit_price, reason):
        gross_pnl_pct = pos.direction * (exit_price - pos.entry_price) / pos.entry_price
        net_pnl_pct = gross_pnl_pct - TOTAL_FRICTION
        capital_before = self.capital
        self.capital = self.capital * (1 + net_pnl_pct * pos.size_pct)
        self.trades.append({
            "entry_time": pos.entry_time,
            "exit_time": self.timestamps[i],
            "state": pos.state,
            "strategy": pos.strategy,
            "direction": "LONG" if pos.direction == 1 else "SHORT",
            "entry_price": pos.entry_price,
            "exit_price": exit_price,
            "initial_stop": pos.major_stop_anchor,
            "final_stop": pos.stop_price,
            "target_price": pos.target_price,
            "size_pct": pos.size_pct,
            "risk_distance_pct": pos.risk_distance_pct,
            "gross_pnl_pct": gross_pnl_pct,
            "net_pnl_pct": net_pnl_pct,
            "capital_before": capital_before,
            "capital_after": self.capital,
            "reason": reason,
            "hold_bars": i - pos.entry_idx,
        })
        self.positions.remove(pos)

    def record_equity(self, i):
        equity = self.capital
        if self.positions:
            unrealized = 0.0
            for pos in self.positions:
                unrealized_pct = pos.direction * (self.close[i] - pos.entry_price) / pos.entry_price
                unrealized += unrealized_pct * pos.size_pct
            equity = self.capital * (1 + unrealized)
        self.equity_rows.append({"timestamp": self.timestamps[i], "equity": equity})

    def compute_stats(self):
        trades_df = pd.DataFrame(self.trades)
        equity_df = pd.DataFrame(self.equity_rows)
        state_df = pd.DataFrame(self.state_rows)
        if trades_df.empty:
            return {"error": "没有产生任何交易", "equity_df": equity_df, "trades_df": trades_df, "state_df": state_df}

        wins = trades_df[trades_df["net_pnl_pct"] > 0]
        losses = trades_df[trades_df["net_pnl_pct"] <= 0]
        equity = equity_df["equity"].to_numpy()
        running_max = np.maximum.accumulate(equity)
        drawdown = (equity - running_max) / running_max
        equity_returns = np.diff(equity) / equity[:-1]
        sharpe = 0.0
        if len(equity_returns) > 1 and np.std(equity_returns) > 0:
            sharpe = np.mean(equity_returns) / np.std(equity_returns) * np.sqrt(365 * 24 * 12)
        profit_factor = float("inf") if losses["net_pnl_pct"].sum() == 0 else abs(wins["net_pnl_pct"].sum() / losses["net_pnl_pct"].sum())
        buy_hold_return = self.close[-1] / self.close[0] - 1
        trades_df["month"] = pd.to_datetime(trades_df["entry_time"]).dt.to_period("M").astype(str)

        return {
            "total_trades": len(trades_df),
            "win_rate": len(wins) / len(trades_df),
            "total_return": self.capital / self.initial_capital - 1,
            "buy_hold_return": buy_hold_return,
            "alpha_vs_buy_hold": self.capital / self.initial_capital - 1 - buy_hold_return,
            "final_capital": self.capital,
            "max_drawdown": drawdown.min(),
            "sharpe_ratio": sharpe,
            "profit_factor": profit_factor,
            "avg_net_pnl": trades_df["net_pnl_pct"].mean(),
            "avg_gross_pnl": trades_df["gross_pnl_pct"].mean(),
            "avg_size_pct": trades_df["size_pct"].mean(),
            "avg_hold_bars": trades_df["hold_bars"].mean(),
            "median_hold_bars": trades_df["hold_bars"].median(),
            "cycle_stats": summarize_group(trades_df, "state"),
            "strategy_stats": summarize_group(trades_df, "strategy"),
            "monthly_stats": summarize_group(trades_df, "month"),
            "exit_stats": trades_df["reason"].value_counts().to_dict(),
            "state_distribution": state_df["cycle_state"].value_counts().to_dict(),
            "transition_distribution": state_df[state_df["transition"] != ""]["transition"].value_counts().to_dict(),
            "trades_df": trades_df,
            "equity_df": equity_df,
            "state_df": state_df,
        }


def summarize_group(trades_df, column):
    stats = {}
    for name, group in trades_df.groupby(column):
        wins = group[group["net_pnl_pct"] > 0]
        losses = group[group["net_pnl_pct"] <= 0]
        loss_sum = losses["net_pnl_pct"].sum()
        stats[str(name)] = {
            "trades": int(len(group)),
            "win_rate": float(len(wins) / len(group)) if len(group) else 0.0,
            "avg_net_pnl": float(group["net_pnl_pct"].mean()),
            "sum_net_pnl": float(group["net_pnl_pct"].sum()),
            "avg_size_pct": float(group["size_pct"].mean()),
            "profit_factor": float("inf") if loss_sum == 0 else float(abs(wins["net_pnl_pct"].sum() / loss_sum)),
        }
    return stats


def print_report(df, stats):
    print("\n" + "=" * 80)
    print("BTC 5m 市场周期持久状态机策略回测")
    print("=" * 80)
    print(f"数据范围: {df['timestamp'].iloc[0]} 至 {df['timestamp'].iloc[-1]}，K线数 {len(df)}")
    print(f"初始资金: ${INITIAL_CAPITAL:,.2f}")
    print(f"单笔风险预算: {RISK_PER_TRADE:.2%}，最大名义仓位: {MAX_POSITION_SIZE:.1f}x")
    print(f"双边摩擦成本: {TOTAL_FRICTION:.2%}")

    if "error" in stats:
        print(stats["error"])
        return

    print("\n状态分布")
    for state, count in stats["state_distribution"].items():
        print(f"  {state:<22} {count:>8} ({count / len(df):.2%})")

    print("\n状态切换")
    for transition, count in stats["transition_distribution"].items():
        print(f"  {transition:<22} {count:>8}")

    print("\n整体表现")
    print(f"总交易次数: {stats['total_trades']}")
    print(f"胜率: {stats['win_rate']:.2%}")
    print(f"总收益率: {stats['total_return']:.2%}")
    print(f"BTC 买入持有收益: {stats['buy_hold_return']:.2%}")
    print(f"相对买入持有 Alpha: {stats['alpha_vs_buy_hold']:.2%}")
    print(f"最终资金: ${stats['final_capital']:,.2f}")
    print(f"最大回撤: {stats['max_drawdown']:.2%}")
    print(f"Sharpe: {stats['sharpe_ratio']:.2f}")
    print(f"Profit Factor: {stats['profit_factor']:.2f}")
    print(f"平均每笔净收益: {stats['avg_net_pnl']:.4%}")
    print(f"平均名义仓位: {stats['avg_size_pct']:.2f}x")
    print(f"平均持仓: {stats['avg_hold_bars']:.1f} 根K线 ({stats['avg_hold_bars'] * 5:.0f} 分钟)")
    print(f"中位持仓: {stats['median_hold_bars']:.0f} 根K线 ({stats['median_hold_bars'] * 5:.0f} 分钟)")

    print_table("按周期表现", stats["cycle_stats"])
    print_table("按策略表现", stats["strategy_stats"])
    print_table("按月表现", stats["monthly_stats"])

    print("\n退出原因")
    for reason, count in stats["exit_stats"].items():
        print(f"  {reason:<18} {count:>6}")

    conclusion = "赚钱" if stats["total_return"] > 0 else "不赚钱"
    print(f"\n结论: 过去一年该市场周期持久状态机策略回测结果为{conclusion}。")


def print_table(title, rows):
    print(f"\n{title}")
    print(f"  {'名称':<24}{'交易数':>8}{'胜率':>10}{'平均净收益':>14}{'净收益和':>12}{'平均仓位':>12}{'PF':>8}")
    for name, row in rows.items():
        print(
            f"  {name:<24}{row['trades']:>8}"
            f"{row['win_rate']:>10.2%}"
            f"{row['avg_net_pnl']:>14.4%}"
            f"{row['sum_net_pnl']:>12.2%}"
            f"{row['avg_size_pct']:>12.2f}"
            f"{row['profit_factor']:>8.2f}"
        )


def save_results(stats):
    if "error" in stats:
        return
    trades_df = stats["trades_df"].copy()
    trades_df.to_csv(TRADES_CSV_PATH, index=False)
    json_payload = {
        "strategy": "BTC 5m Persistent Market Cycle State Machine",
        "params": {
            "risk_per_trade": RISK_PER_TRADE,
            "max_position_size": MAX_POSITION_SIZE,
            "commission_rate": COMMISSION_RATE,
            "slippage_rate": SLIPPAGE_RATE,
            "days": DAYS,
            "timeframe": TIMEFRAME,
            "allow_range_long": ALLOW_RANGE_LONG,
            "allow_range_short": ALLOW_RANGE_SHORT,
            "allow_breakout_up": ALLOW_BREAKOUT_UP,
            "allow_breakout_down": ALLOW_BREAKOUT_DOWN,
            "allow_tight_channel": ALLOW_TIGHT_CHANNEL,
            "allow_broad_channel": ALLOW_BROAD_CHANNEL,
        },
        "results": {
            "total_trades": stats["total_trades"],
            "win_rate": stats["win_rate"],
            "total_return": stats["total_return"],
            "buy_hold_return": stats["buy_hold_return"],
            "alpha_vs_buy_hold": stats["alpha_vs_buy_hold"],
            "final_capital": stats["final_capital"],
            "max_drawdown": stats["max_drawdown"],
            "sharpe_ratio": stats["sharpe_ratio"],
            "profit_factor": stats["profit_factor"],
        },
        "state_distribution": stats["state_distribution"],
        "transition_distribution": stats["transition_distribution"],
        "cycle_stats": stats["cycle_stats"],
        "strategy_stats": stats["strategy_stats"],
        "monthly_stats": stats["monthly_stats"],
        "exit_stats": stats["exit_stats"],
    }
    with open(RESULT_JSON_PATH, "w", encoding="utf-8") as fp:
        json.dump(json_payload, fp, ensure_ascii=False, indent=2)
    print(f"\n结果已保存: {RESULT_JSON_PATH}")
    print(f"交易明细已保存: {TRADES_CSV_PATH}")


def main():
    df = fetch_ohlcv()
    df = compute_indicators(df)
    stats = MarketCycleBacktester(df).run()
    print_report(df, stats)
    save_results(stats)
    return stats


if __name__ == "__main__":
    main()
