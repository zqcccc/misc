"""
策略核心 - 纯函数式, 不读配置文件、不发通知、不写状态.
输入: cfg (dict, 来自 strategies.json 一条记录) + 已收盘 DataFrame, 输出状态/场景.
所有 K 线形态止盈信号与 step1-3/step6 研究口径一致 (来自 xag_monitor.py 的 _compute_top_signals).
"""
import json
import math
import numpy as np
import pandas as pd


TP_SIDE_LONG_ONLY = "long_only"
TP_SIDE_SHORT_ONLY = "short_only"
TP_SIDE_BOTH = "both"
TP_SIDE_VALUES = (TP_SIDE_LONG_ONLY, TP_SIDE_SHORT_ONLY, TP_SIDE_BOTH)


def tp_side_of(cfg):
    """从 cfg 取 tp_side 字段, 默认 'both'. 非法值回退 to both."""
    s = (cfg or {}).get("tp_side", TP_SIDE_BOTH)
    return s if s in TP_SIDE_VALUES else TP_SIDE_BOTH


def tp_side_matches(position, side):
    """根据 tp_side 决定是否对当前持仓方向触发止盈.

    position: 1 (多头持仓) / -1 (做空持仓) / 0
    side: 'both' / 'long_only' / 'short_only'
    """
    if side == TP_SIDE_LONG_ONLY:
        return position == 1
    if side == TP_SIDE_SHORT_ONLY:
        return position == -1
    return position != 0


def compute_indicators(df, cfg):
    """计算 EMA/ATR/RSI/偏离/确认计数 + K 线形态止盈信号列 (top_long_exit/top_short_exit)."""
    df = df.copy()
    ema_span = int(cfg["ema_span"])
    df["ema"] = df["close"].ewm(span=ema_span, adjust=False).mean()

    prev_close = df["close"].shift(1).fillna(df["close"])
    tr = np.maximum(df["high"] - df["low"],
                    np.maximum(np.abs(df["high"] - prev_close),
                               np.abs(df["low"] - prev_close)))
    atr_span = int(cfg.get("atr_span", 14))
    df["atr"] = tr.ewm(span=atr_span, adjust=False).mean()

    rsi_span = int(cfg.get("rsi_span", 14))
    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(span=rsi_span, adjust=False).mean()
    avg_loss = loss.ewm(span=rsi_span, adjust=False).mean().replace(0, np.nan)
    rs = avg_gain / avg_loss
    df["rsi"] = (100 - 100 / (1 + rs)).fillna(50)

    df["dev_pct"] = (df["close"] - df["ema"]) / df["ema"]

    bp = float(cfg["breakout_pct"])
    bull = (df["close"] > df["ema"]) & (df["dev_pct"] > bp)
    bear = (df["close"] < df["ema"]) & (df["dev_pct"] < -bp)

    cb_float = float(cfg.get("cb_float", 0) or 0)
    confirm_bars = int(cfg["confirm_bars"])
    df["bull_streak"] = 0.0
    df["bear_streak"] = 0.0
    bs = 0.0
    br = 0.0
    if cb_float > 0:
        w = float(np.exp(-1.0 / max(cb_float, 0.1)))
        cb_threshold = cb_float * 0.95
        for i in range(len(df)):
            if bool(bull.iloc[i]):
                bs = bs + 1.0
            else:
                bs = bs * w
            if bool(bear.iloc[i]):
                br = br + 1.0
            else:
                br = br * w
            df.loc[i, "bull_streak"] = bs
            df.loc[i, "bear_streak"] = br
    else:
        cb_threshold = float(confirm_bars)
        for i in range(len(df)):
            if bool(bull.iloc[i]):
                bs += 1
            else:
                bs = 0
            if bool(bear.iloc[i]):
                br += 1
            else:
                br = 0
            df.loc[i, "bull_streak"] = float(bs)
            df.loc[i, "bear_streak"] = float(br)

    df["long_ready"] = df["bull_streak"] >= cb_threshold
    df["short_ready"] = df["bear_streak"] >= cb_threshold

    _compute_top_signals(df, cfg)
    return df, cb_threshold


def _compute_top_signals(df, cfg):
    """根据 cfg['tp_type'] 添加 top_long_exit / top_short_exit 两列 (bool).
    tp_enabled=False 时两列全 False. 所有信号需 at_high/at_low 过滤."""
    n = len(df)
    if n == 0:
        df["top_long_exit"] = False
        df["top_short_exit"] = False
        return

    close = df["close"].values
    open_ = df["open"].values
    high = df["high"].values
    low = df["low"].values
    body = np.abs(close - open_)
    body_safe = np.where(body > 1e-9, body, 1e-9)
    upper_wick = high - np.maximum(close, open_)
    lower_wick = np.minimum(close, open_) - low
    atr = df["atr"].values if "atr" in df.columns else np.ones(n)
    atr = np.where(atr > 0, atr, 1.0)

    high_window = 20
    rolling_max_close = pd.Series(close).rolling(high_window, min_periods=1).max().values
    rolling_min_close = pd.Series(close).rolling(high_window, min_periods=1).min().values
    at_high = close >= rolling_max_close * 0.995
    at_low = close <= rolling_min_close * 1.005

    params = {}
    if cfg.get("tp_params"):
        try:
            params = json.loads(cfg["tp_params"])
        except Exception:
            params = {}

    top_long = np.zeros(n, dtype=bool)
    top_short = np.zeros(n, dtype=bool)

    if not cfg.get("tp_enabled", True):
        pass
    else:
        tp_type = (cfg.get("tp_type") or "rsi")
        if tp_type == "rsi":
            rsi = df["rsi"].values if "rsi" in df.columns else np.full(n, 50.0)
            top_long = (rsi > cfg.get("rsi_over", 80)) & at_high
            top_short = (rsi < cfg.get("rsi_under", 20)) & at_low
        elif tp_type == "long_upper_wick":
            n_atr = params.get("n_atr", 1.5)
            long_upper = (upper_wick > n_atr * atr) & (upper_wick > 2 * body_safe)
            top_long = long_upper & at_high
            long_lower = (lower_wick > n_atr * atr) & (lower_wick > 2 * body_safe)
            top_short = long_lower & at_low
        elif tp_type == "bearish_engulfing":
            prior_green = np.zeros(n, dtype=bool)
            prior_green[1:] = close[:-1] > open_[:-1]
            current_red = close < open_
            engulfs = np.zeros(n, dtype=bool)
            engulfs[1:] = (open_[1:] > close[:-1]) & (close[1:] < open_[:-1])
            top_long = prior_green & current_red & engulfs & at_high
            prior_red = np.zeros(n, dtype=bool)
            prior_red[1:] = close[:-1] < open_[:-1]
            current_green = close > open_
            bull_engulfs = np.zeros(n, dtype=bool)
            bull_engulfs[1:] = (open_[1:] < close[:-1]) & (close[1:] > open_[:-1])
            top_short = prior_red & current_green & bull_engulfs & at_low
        elif tp_type == "dark_cloud_cover":
            prior_green = np.zeros(n, dtype=bool)
            prior_green[1:] = close[:-1] > open_[:-1]
            prior_mid = np.zeros(n)
            prior_mid[1:] = (close[:-1] + open_[:-1]) / 2
            prior_high_arr = np.zeros(n)
            prior_high_arr[1:] = high[:-1]
            prior_low_arr = np.zeros(n)
            prior_low_arr[1:] = low[:-1]
            current_red = close < open_
            opens_above = np.zeros(n, dtype=bool)
            opens_above[1:] = open_[1:] > prior_high_arr[:-1]
            closes_below_mid = np.zeros(n, dtype=bool)
            closes_below_mid[1:] = close[1:] < prior_mid[:-1]
            top_long = prior_green & current_red & opens_above & closes_below_mid & at_high
            prior_red = np.zeros(n, dtype=bool)
            prior_red[1:] = close[:-1] < open_[:-1]
            current_green = close > open_
            opens_below = np.zeros(n, dtype=bool)
            opens_below[1:] = open_[1:] < prior_low_arr[:-1]
            closes_above_mid = np.zeros(n, dtype=bool)
            closes_above_mid[1:] = close[1:] > prior_mid[:-1]
            top_short = prior_red & current_green & opens_below & closes_above_mid & at_low
        elif tp_type == "evening_star":
            body_avg = pd.Series(body).rolling(10, min_periods=1).mean().values
            big1 = np.zeros(n, dtype=bool)
            big1[2:] = (close[:-2] > open_[:-2]) & (body[:-2] > body_avg[:-2] * 1.2)
            small2 = np.zeros(n, dtype=bool)
            small2[2:] = body[1:-1] < body_avg[1:-1] * 0.6
            big3_red = np.zeros(n, dtype=bool)
            big3_red[2:] = (close[2:] < open_[2:]) & (body[2:] > body_avg[2:] * 1.2) & \
                           (close[2:] < (close[:-2] + open_[:-2]) / 2)
            top_long = big1 & small2 & big3_red & at_high
            big1_red = np.zeros(n, dtype=bool)
            big1_red[2:] = (close[:-2] < open_[:-2]) & (body[:-2] > body_avg[:-2] * 1.2)
            big3_green = np.zeros(n, dtype=bool)
            big3_green[2:] = (close[2:] > open_[2:]) & (body[2:] > body_avg[2:] * 1.2) & \
                            (close[2:] > (close[:-2] + open_[:-2]) / 2)
            top_short = big1_red & small2 & big3_green & at_low
        elif tp_type == "shooting_star":
            ratio = params.get("wick_body_ratio", 2.0)
            is_star = (upper_wick > ratio * body_safe) & (upper_wick > lower_wick * 2) & (close < open_)
            top_long = is_star & at_high
            inverted = (lower_wick > ratio * body_safe) & (lower_wick > upper_wick * 2) & (close > open_)
            top_short = inverted & at_low
        elif tp_type == "outside_bar_reversal":
            outside = np.zeros(n, dtype=bool)
            outside[1:] = (high[1:] > high[:-1]) & (low[1:] < low[:-1])
            closes_lower = np.zeros(n, dtype=bool)
            closes_lower[1:] = close[1:] < (high[1:] + low[1:]) / 2
            top_long = outside & closes_lower & at_high
            closes_upper = np.zeros(n, dtype=bool)
            closes_upper[1:] = close[1:] > (high[1:] + low[1:]) / 2
            top_short = outside & closes_upper & at_low
        elif tp_type == "failed_breakout":
            n_brk = params.get("n_brk", 20)
            prior_high = pd.Series(high).rolling(n_brk, min_periods=1).max().shift(1).values
            prior_low = pd.Series(low).rolling(n_brk, min_periods=1).min().shift(1).values
            broke_above = high > prior_high
            closed_below = close < prior_high
            top_long = broke_above & closed_below & at_high
            broke_below = low < prior_low
            closed_above = close > prior_low
            top_short = broke_below & closed_above & at_low
        elif tp_type == "zscore":
            # TRHRP 启发: 价格长期均值极端偏离时部分止盈.
            # 多头: z >= sell_z 视为已偏贵 -> top_long_exit (需 at_high 过滤避免低位误触)
            # 做空: z <= buy_z 视为已偏贱 -> top_short_exit (需 at_low 过滤避免高位误触)
            z_window = int(params.get("window", 252))
            z_sell = float(params.get("sell_z", 1.5))
            z_buy = float(params.get("buy_z", -1.5))
            log_price = np.log(np.where(close > 0, close, np.nan))
            s = pd.Series(log_price)
            mean_z = s.rolling(z_window, min_periods=max(20, z_window // 4)).mean()
            std_z = s.rolling(z_window, min_periods=max(20, z_window // 4)).std()
            z = (s - mean_z) / std_z.replace(0.0, np.nan)
            z = z.replace([np.inf, -np.inf], np.nan).fillna(0.0).values
            top_long = (z >= z_sell) & at_high
            top_short = (z <= z_buy) & at_low
        elif tp_type == "none":
            pass
        else:
            pass

    df["top_long_exit"] = top_long
    df["top_short_exit"] = top_short


def infer_position(df_closed, cfg):
    """基于已收盘 K 线回放策略, 推断当前应持仓方向."""
    n = len(df_closed)
    position = 0
    pos_size = 0.0
    entry_price = 0.0
    entry_idx = 0
    last_tp_idx = -10**9
    tp_count_this = 0

    ema_span = int(cfg["ema_span"])
    atr_span = int(cfg.get("atr_span", 14))
    cool_bars = int(cfg.get("cool_bars", 20))
    part_ratio = float(cfg.get("part_ratio", 0.15))
    tp_max_times = int(cfg.get("tp_max_times", -1))
    tp_enabled = bool(cfg.get("tp_enabled", True))
    tp_side = tp_side_of(cfg)

    has_top_signals = "top_long_exit" in df_closed.columns
    start = max(ema_span * 2, atr_span + 2)
    for i in range(start, n):
        r = df_closed.iloc[i]
        if tp_enabled and tp_side_matches(position, tp_side) and pos_size > 0.01 and (i - last_tp_idx) >= cool_bars:
            triggered = False
            if has_top_signals:
                if position == 1 and bool(r["top_long_exit"]):
                    triggered = True
                elif position == -1 and bool(r["top_short_exit"]):
                    triggered = True
            if triggered and (tp_max_times < 0 or tp_count_this < tp_max_times):
                pos_size *= (1 - part_ratio)
                last_tp_idx = i
                tp_count_this += 1

        target = position
        if bool(r["long_ready"]) and not bool(r["short_ready"]):
            target = 1
        elif bool(r["short_ready"]) and not bool(r["long_ready"]):
            target = -1
        if position == 0:
            if target != 0:
                position = target
                pos_size = 1.0
                entry_price = float(r["close"])
                entry_idx = i
                tp_count_this = 0
        else:
            if target != position and target != 0:
                position = target
                pos_size = 1.0
                entry_price = float(r["close"])
                entry_idx = i
                tp_count_this = 0

    return {
        "position": int(position),
        "pos_size": float(pos_size),
        "entry_price": float(entry_price),
        "entry_idx": int(entry_idx),
        "entry_time": df_closed.iloc[entry_idx]["timestamp"].isoformat() if entry_idx > 0 else None,
        "last_tp_idx": int(last_tp_idx),
        "tp_count_this_trade": int(tp_count_this),
    }


def replay_actions(df_closed, cfg, max_actions=None):
    """同 infer_position 一致的回放口径, 但额外返回每个"开仓/反手/止盈"动作的轨迹列表.

    用于 daemon 启动时重建真实操作历史 (写到 actions.log JSONL), 替代"推断开仓"语义.
    返回 list[dict]: {"kind": "开仓"|"反手"|"止盈", "time": iso, "price": float,
                      "pos": int(动作后方向), "pos_size": float(动作后仓位), "idx": int,
                      "tp_count_this_trade": int, "descr": str}

    max_actions: 只保留最后 N 个动作 (None=全保留). 用于 actions.log 不无限膨胀.
    """
    actions = []
    n = len(df_closed)
    if n == 0:
        return actions
    ema_span = int(cfg["ema_span"])
    atr_span = int(cfg.get("atr_span", 14))
    cool_bars = int(cfg.get("cool_bars", 20))
    part_ratio = float(cfg.get("part_ratio", 0.15))
    tp_max_times = int(cfg.get("tp_max_times", -1))
    tp_enabled = bool(cfg.get("tp_enabled", True))
    tp_side = tp_side_of(cfg)
    has_top_signals = "top_long_exit" in df_closed.columns
    start = max(ema_span * 2, atr_span + 2)
    position = 0
    pos_size = 0.0
    entry_price = 0.0
    entry_idx = 0
    last_tp_idx = -10**9
    tp_count_this = 0
    dir_map = {1: "做多", -1: "做空", 0: "空仓"}

    def _emit(kind, idx, after_pos, after_size, after_tp_count, extra=""):
        ts = df_closed.iloc[idx]["timestamp"].isoformat()
        actions.append({
            "kind": kind,
            "time": ts,
            "price": float(df_closed.iloc[idx]["close"]),
            "pos": int(after_pos),
            "pos_size": float(after_size),
            "idx": int(idx),
            "tp_count_this_trade": int(after_tp_count),
            "descr": extra or None,
        })

    for i in range(start, n):
        r = df_closed.iloc[i]
        if tp_enabled and tp_side_matches(position, tp_side) and pos_size > 0.01 and (i - last_tp_idx) >= cool_bars:
            triggered = False
            if has_top_signals:
                if position == 1 and bool(r["top_long_exit"]):
                    triggered = True
                elif position == -1 and bool(r["top_short_exit"]):
                    triggered = True
            if triggered and (tp_max_times < 0 or tp_count_this < tp_max_times):
                pos_size *= (1 - part_ratio)
                last_tp_idx = i
                tp_count_this += 1
                _emit("止盈", i, position, pos_size, tp_count_this,
                      extra=f"{dir_map[position]}止盈: 减仓 → {pos_size*100:.0f}% @ {float(r['close']):.4g}")

        target = position
        if bool(r["long_ready"]) and not bool(r["short_ready"]):
            target = 1
        elif bool(r["short_ready"]) and not bool(r["long_ready"]):
            target = -1
        if position == 0:
            if target != 0:
                position = target
                pos_size = 1.0
                entry_price = float(r["close"])
                entry_idx = i
                tp_count_this = 0
                _emit("开仓", i, position, pos_size, tp_count_this,
                      extra=f"开仓{dir_map[position]} @ {entry_price:.4g}")
        else:
            if target != position and target != 0:
                prev = position
                position = target
                pos_size = 1.0
                entry_price = float(r["close"])
                entry_idx = i
                tp_count_this = 0
                _emit("反手", i, position, pos_size, tp_count_this,
                      extra=f"反手 {dir_map[prev]} → {dir_map[position]} @ {entry_price:.4g}")

    if max_actions is not None and max_actions > 0 and len(actions) > max_actions:
        actions = actions[-max_actions:]
    return actions


def snapshot(df_closed, pos, live_price, cfg):
    """生成状态快照 dict (含止盈冷却信息)."""
    last = df_closed.iloc[-1]
    dir_map = {1: "做多", -1: "做空", 0: "空仓"}
    unreal = 0.0
    if pos["position"] != 0 and pos["entry_price"] > 0:
        unreal = pos["position"] * (live_price - pos["entry_price"]) / pos["entry_price"]
    cool_bars = int(cfg.get("cool_bars", 20))
    bars_since_tp = len(df_closed) - 1 - pos["last_tp_idx"]
    cool_left = max(0, cool_bars - bars_since_tp)

    # 若启用 zscore 止盈, 现场基于 df_closed 算当前 z (供 snapshot 与 build_scenarios 共享).
    price_zscore = None
    if (cfg.get("tp_enabled", True)) and (cfg.get("tp_type") == "zscore"):
        try:
            params = json.loads(cfg.get("tp_params") or "{}")
        except Exception:
            params = {}
        z_window = int(params.get("window", 252))
        close_arr = df_closed["close"].values.astype(float)
        log_p = np.log(np.where(close_arr > 0, close_arr, np.nan))
        sser = pd.Series(log_p)
        mean_z = sser.rolling(z_window, min_periods=max(20, z_window // 4)).mean()
        std_z = sser.rolling(z_window, min_periods=max(20, z_window // 4)).std()
        z_series = (sser - mean_z) / std_z.replace(0.0, np.nan)
        z_series = z_series.replace([np.inf, -np.inf], np.nan).fillna(0.0)
        live_log = float(np.log(max(live_price, 1e-12)))
        live_z = float((live_log - mean_z.iloc[-1]) / std_z.iloc[-1]) if std_z.iloc[-1] and std_z.iloc[-1] > 0 else 0.0
        price_zscore = live_z if math.isfinite(live_z) else None

    from datetime import datetime, timezone
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "last_closed": last["timestamp"].isoformat(),
        "close": float(last["close"]),
        "live_price": float(live_price),
        "ema": float(last["ema"]),
        "rsi": float(last["rsi"]),
        "atr": float(last["atr"]),
        "dev_pct": float(last["dev_pct"]),
        "price_zscore": price_zscore,
        "position": int(pos["position"]),
        "position_str": dir_map[pos["position"]],
        "pos_size": float(pos["pos_size"]),
        "entry_price": float(pos["entry_price"]),
        "entry_time": df_closed.iloc[pos["entry_idx"]]["timestamp"].isoformat() if pos["entry_idx"] > 0 else None,
        "tp_count_this_trade": int(pos["tp_count_this_trade"]),
        "bull_streak": float(last["bull_streak"]),
        "bear_streak": float(last["bear_streak"]),
        "unreal_pct": float(unreal),
        "bars_since_tp": int(bars_since_tp),
        "cool_left": int(cool_left),
        "cool_passed": cool_left == 0,
        "extreme_long": bool(last["top_long_exit"]) if "top_long_exit" in last else False,
        "extreme_short": bool(last["top_short_exit"]) if "top_short_exit" in last else False,
    }


def _need_str(streak, cfg, cb_threshold):
    cb_float = float(cfg.get("cb_float", 0) or 0)
    if cb_float > 0:
        cur = float(streak)
        if cur >= cb_threshold:
            return "已就绪"
        target = cb_threshold - cur
        if target <= 1:
            return "1根"
        w = float(np.exp(-1.0 / max(cb_float, 0.1)))
        n, acc = 0, 0.0
        while acc < target:
            acc += w ** n
            n += 1
            if n > 200:
                break
        return f"约{max(n, 1)}根(连续满足)"
    cb_int = int(cfg["confirm_bars"])
    return f"{max(0, cb_int - int(streak))}根"


def _cb_label(cfg, cb_threshold):
    cb_float = float(cfg.get("cb_float", 0) or 0)
    if cb_float > 0:
        return f"score≥{cb_threshold:.2f} (cb={cb_float:.2f}, EWM连续化)"
    return f"连续{int(cfg['confirm_bars'])}根"


def _tp_metric_label(s, cfg):
    """根据 tp_type 返回 (当前指标名, 当前值, 多阈值/标签, 空阈值/标签)."""
    tp_type = cfg.get("tp_type") or "rsi"
    bp = float(cfg["breakout_pct"])
    if tp_type == "rsi":
        rsi_over = cfg.get("rsi_over", 80)
        rsi_under = cfg.get("rsi_under", 20)
        return ("RSI", float(s["rsi"]), rsi_over, f"RSI>{rsi_over}超买", rsi_under, f"RSI<{rsi_under}超卖")
    if tp_type == "long_upper_wick":
        return ("A5长上影", None, None, "上影>1.5ATR (高点)", None, "下影>1.5ATR (低点)")
    if tp_type == "outside_bar_reversal":
        return ("D2外包日", None, None, "外包收下半 (高点)", None, "外包收上半 (低点)")
    if tp_type == "dark_cloud_cover":
        return ("A4乌云盖顶", None, None, "乌云盖顶形态 (高点)", None, "刺穿线 (低点)")
    if tp_type == "bearish_engulfing":
        return ("A2看跌吞没", None, None, "看跌吞没 (高点)", None, "看涨吞没 (低点)")
    if tp_type == "evening_star":
        return ("A3黄昏之星", None, None, "黄昏之星 (高点)", None, "晨星 (低点)")
    if tp_type == "shooting_star":
        return ("A1流星线", None, None, "流星线 (高点)", None, "倒锤 (低点)")
    if tp_type == "failed_breakout":
        return ("D1假突破", None, None, "假突破 (高点)", None, "假跌破 (低点)")
    if tp_type == "zscore":
        params = {}
        try:
            params = json.loads(cfg.get("tp_params") or "{}")
        except Exception:
            params = {}
        z_sell = float(params.get("sell_z", 1.5))
        z_buy = float(params.get("buy_z", -1.5))
        # 当前 z-score 在 snapshot 里实时算 (snapshot 字段 price_zscore),
        # 由本函数的调用方 build_scenarios 内从 s 字典传入 _tp_metric_label 后再使用.
        cur_z = s.get("price_zscore")
        cur_z_f = float(cur_z) if isinstance(cur_z, (int, float)) and math.isfinite(float(cur_z)) else None
        return ("Z分位", cur_z_f, z_sell, f"z≥{z_sell:.2f}σ 偏贵 (高点)", z_buy,
                f"z≤{z_buy:.2f}σ 偏贱 (低点)")
    return (None, None, None, "止盈未启用", None, "止盈未启用")


def build_scenarios(s, cfg, cb_threshold):
    """生成"下一步可触发场景"说明. 返回 (短摘要, 详细列表)."""
    short_parts = []
    details = []
    cb_label = _cb_label(cfg, cb_threshold)
    bp = float(cfg["breakout_pct"])
    need_str_fn = lambda streak: _need_str(streak, cfg, cb_threshold)

    if s["position"] == 0:
        if s["bull_streak"] >= cb_threshold:
            short_parts.append("✅可开多")
            details.append(f"🔵 开多: 多头确认已就绪 (bull_score={s['bull_streak']:.2f}≥{cb_threshold:.2f})")
        elif s["bear_streak"] >= cb_threshold:
            short_parts.append("✅可开空")
            details.append(f"🔴 开空: 空头确认已就绪 (bear_score={s['bear_streak']:.2f}≥{cb_threshold:.2f})")
        else:
            need_bull = need_str_fn(s["bull_streak"])
            need_bear = need_str_fn(s["bear_streak"])
            short_parts.append(f"等信号(多需{need_bull}/空需{need_bear})")
            details.append(f"🔵 开多: 需{cb_label} 收盘>EMA且偏离>{bp*100}% (当前bull_score={s['bull_streak']:.2f}, 还需{need_bull})")
            details.append(f"🔴 开空: 需{cb_label} 收盘<EMA且偏离<-{bp*100}% (当前bear_score={s['bear_streak']:.2f}, 还需{need_bear})")
        return " | ".join(short_parts), details

    metric_name, cur_metric, thr_long, label_long, thr_short, label_short = _tp_metric_label(s, cfg)
    tp_side = tp_side_of(cfg)
    side_active = tp_side_matches(s["position"], tp_side)

    if cfg.get("tp_enabled", True) and float(cfg.get("part_ratio", 0.15)) > 0:
        if not side_active:
            side_hint = {"long_only": "(仅多头止盈, 当前做空不启用)", "short_only": "(仅做空止盈, 当前做多不启用)"}.get(tp_side, "")
            details.append(f"🟠 止盈: 当前 cfg tp_side={tp_side} → 本仓不触发止盈 {side_hint}".strip())
        else:
            triggered_now = (s["position"] == 1 and s.get("extreme_long", False)) or \
                            (s["position"] == -1 and s.get("extreme_short", False))
            if triggered_now:
                if s["cool_passed"]:
                    short_parts.append("⚠️止盈可触发")
                    details.append(f"🟠 止盈(可触发): {metric_name} 触发 → 平{s['pos_size']*float(cfg['part_ratio'])*100:.0f}%仓位 ({s['pos_size']*100:.0f}%→{s['pos_size']*(1-float(cfg['part_ratio']))*100:.0f}%)")
                else:
                    short_parts.append(f"止盈信号在(冷却{s['cool_left']}根)")
                    details.append(f"🟠 止盈(冷却中): {metric_name} 触发但冷却还剩{s['cool_left']}根")
            else:
                cur_str = f"{cur_metric:.1f}" if cur_metric is not None else "-"
                if s["position"] == 1:
                    gap = abs(cur_metric - thr_long) if cur_metric is not None and thr_long is not None else 0
                    cool_str = "已过冷却" if s["cool_passed"] else f"冷却剩{s['cool_left']}根"
                    short_parts.append(f"止盈待{label_long}(差{gap:.0f},{cool_str})")
                    details.append(f"🟠 止盈: 需{label_long} (当前{cur_str}, 差{gap:.1f}, {cool_str}) → 触发后平{float(cfg['part_ratio'])*100:.0f}%仓位")
                else:
                    gap = abs(cur_metric - thr_short) if cur_metric is not None and thr_short is not None else 0
                    cool_str = "已过冷却" if s["cool_passed"] else f"冷却剩{s['cool_left']}根"
                    short_parts.append(f"止盈待{label_short}(差{gap:.0f},{cool_str})")
                    details.append(f"🟠 止盈: 需{label_short} (当前{cur_str}, 差{gap:.1f}, {cool_str}) → 触发后平{float(cfg['part_ratio'])*100:.0f}%仓位")

    if s["position"] == 1:
        reversal_price = s["ema"] * (1 - bp)
        streak = s["bear_streak"]
        need = need_str_fn(streak)
        price_diff_pct = abs(s["live_price"] - reversal_price) / max(s["live_price"], 1e-9) * 100
        short_parts.append(f"反手需收盘<{reversal_price:.4g}(跌{price_diff_pct:.2f}%,需{need})")
        details.append(f"🟢 反手做空: 需{cb_label} 收盘<{reversal_price:.4g} (EMA×{1-bp:.4f}, 当前{s['live_price']:.4g}需跌{price_diff_pct:.2f}%, bear_score={streak:.2f}还需{need})")
    else:
        reversal_price = s["ema"] * (1 + bp)
        streak = s["bull_streak"]
        need = need_str_fn(streak)
        price_diff_pct = abs(s["live_price"] - reversal_price) / max(s["live_price"], 1e-9) * 100
        short_parts.append(f"反手需收盘>{reversal_price:.4g}(涨{price_diff_pct:.2f}%,需{need})")
        details.append(f"🟢 反手做多: 需{cb_label} 收盘>{reversal_price:.4g} (EMA×{1+bp:.4f}, 当前{s['live_price']:.4g}需涨{price_diff_pct:.2f}%, bull_score={streak:.2f}还需{need})")

    return " | ".join(short_parts), details


def format_snapshot(s, cfg, cb_threshold, changes=None):
    lines = []
    sym = cfg.get("symbol", "?")
    name = cfg.get("name", sym)
    tf = cfg.get("timeframe", "15m")
    lines.append("=" * 60)
    lines.append(f"  [{name}] {sym} 反手策略  {s['timestamp'][:19].replace('T',' ')} UTC  ({tf})")
    lines.append("=" * 60)
    lines.append(f"  最新收盘: {s['last_closed'][:16].replace('T',' ')}")
    lines.append(f"  实时价格: {s['live_price']:.4g}  (收盘 {s['close']:.4g})")
    lines.append(f"  EMA{cfg['ema_span']}: {s['ema']:.4g}  (偏离 {s['dev_pct']*100:+.2f}%)")
    lines.append(f"  RSI{cfg.get('rsi_span',14)}: {s['rsi']:.1f}")
    if cfg.get("tp_enabled", True) and (cfg.get("tp_type") not in (None, "none")):
        side = (cfg.get("tp_side") or "both")
        lines.append(f"  止盈: {cfg.get('tp_type')} 比例{float(cfg['part_ratio'])*100:.0f}% 冷却{int(cfg.get('cool_bars',20))}根 side={side}")
    lines.append("-" * 60)
    pos_emoji = {1: "🟢", -1: "🔴", 0: "⚪"}
    lines.append(f"  持仓: {pos_emoji[s['position']]} {s['position_str']}  仓位 {s['pos_size']*100:.0f}%")
    if s["position"] != 0:
        lines.append(f"  开仓: {s['entry_time'][:16].replace('T',' ') if s['entry_time'] else '-'} @ {s['entry_price']:.4g}")
        lines.append(f"  浮盈: {s['unreal_pct']*100:+.2f}%  本仓止盈: {s['tp_count_this_trade']} 次")
    lines.append("-" * 60)
    lines.append("  📍 下一步可触发场景:")
    _, details = build_scenarios(s, cfg, cb_threshold)
    for d in details:
        lines.append(f"  {d}")
    if changes:
        lines.append("-" * 60)
        for c in changes:
            lines.append(f"  🚨 {c}")
    lines.append("=" * 60)
    return "\n".join(lines)


def heartbeat_line(s, cfg, cb_threshold):
    scenario_short, _ = build_scenarios(s, cfg, cb_threshold)
    return (f"[{cfg.get('name','?')}] [{s['last_closed'][:16]}] "
            f"{s['position_str']}{s['pos_size']*100:.0f}% "
            f"价{s['live_price']:.4g} RSI{s['rsi']:.1f} "
            f"浮盈{s['unreal_pct']*100:+.2f}% | {scenario_short}")


def notify_message(s, cfg, cb_threshold, changes):
    scenario_short, _ = build_scenarios(s, cfg, cb_threshold)
    change_str = " | ".join(changes) if changes else "状态更新"
    return (f"{cfg.get('name','?')}: {change_str}\n"
            f"现价{s['live_price']:.4g} 浮盈{s['unreal_pct']*100:+.2f}%\n"
            f"下一步: {scenario_short}")


def detect_changes(prev, cur):
    changes = []
    if prev is None:
        return changes
    if prev["position"] != cur["position"]:
        dir_map = {1: "做多", -1: "做空", 0: "空仓"}
        changes.append(f"反手信号: {dir_map[prev['position']]} → {dir_map[cur['position']]} @ {cur['close']:.4g}")
    if abs(prev["pos_size"] - cur["pos_size"]) > 0.01:
        if cur["pos_size"] < prev["pos_size"]:
            changes.append(f"止盈触发: 仓位 {prev['pos_size']*100:.0f}% → {cur['pos_size']*100:.0f}% @ {cur['close']:.4g}")
        else:
            changes.append(f"仓位变化: {prev['pos_size']*100:.0f}% → {cur['pos_size']*100:.0f}% (新开仓)")
    return changes


_TF_MINUTES = {"15m": 15, "5m": 5, "1m": 1, "30m": 30, "1h": 60, "4h": 240, "1d": 1440}


def tf_minutes(timeframe):
    return _TF_MINUTES.get(timeframe, 15)


def next_close_seconds(timeframe):
    """返回距下一次 K 线收盘的秒数.
    支持 1m/5m/15m/30m/1h (下个收盘对齐到分钟); 4h/1d 对齐到 UTC 0 点下一日 +5s.
    """
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    minutes = tf_minutes(timeframe)
    if minutes >= 60:
        # 1h/4h/1d: 对齐到 UTC 整小时/日 (按 minutes 整数倍), 找下个收盘边界
        # 处理大于 60 分钟的级别: 用 total_minutes 对齐
        cur_total_min = now.hour * 60 + now.minute
        next_total = (cur_total_min // minutes + 1) * minutes
        if next_total >= 24 * 60:
            # 跨日, 转换到次日 0 点起
            next_time = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            next_time = next_time + timedelta(minutes=(next_total - 24 * 60))
        else:
            next_time = now.replace(hour=next_total // 60, minute=next_total % 60,
                                     second=0, microsecond=0)
        return (next_time - now).total_seconds() + 5
    # 分钟级 (1m/5m/15m/30m)
    minute = now.minute
    next_mark = (minute // minutes + 1) * minutes
    if next_mark >= 60:
        next_time = now.replace(minute=next_mark - 60, second=0, microsecond=0) + timedelta(hours=1)
    else:
        next_time = now.replace(minute=next_mark, second=0, microsecond=0)
    return (next_time - now).total_seconds() + 5


# ============================================================
# 盘中实时探针 (live_probe): 用实时报价在"未收盘虚拟根"上预演一次
# ============================================================
def live_probe(df_closed, live_price, cfg, now_ts=None):
    """把当前未收盘__K 线__用 live_price 虚拟填充, 跑一遍 compute_indicators +
    infer_position + snapshot, 返回线上推断的 snapshot.

    用途: daemon 在盘中, 每隔 N 秒用实时报价"如果现在就走" -> 当前会是什么信号.
    与收盘后正式 snapshot 区别:
      - timestamp 标记为虚拟根时间 (下个收盘点的时间)
      - close = live_price (不是已收根 close)
      - 信号 long_ready/short_ready 用虚拟根 bull/bear_streak 推算
    """
    from datetime import datetime, timezone, timedelta
    if now_ts is None:
        now_ts = datetime.now(timezone.utc)
    tf_min = tf_minutes(cfg.get("timeframe", "15m"))
    # 虚拟根时间 = 下一个完整收盘时间 (UTC)
    delta = tf_min - (int(now_ts.minute) % tf_min)
    if delta == 0:
        delta = tf_min
    virtual_ts = (now_ts.replace(second=0, microsecond=0) + timedelta(minutes=delta)
                  - timedelta(minutes=tf_min))

    # 拷贝 df_closed 追加一行虚拟根
    df_v = df_closed.copy()
    last_row = df_v.iloc[-1].to_dict()
    new_row = dict(last_row)
    new_row["timestamp"] = virtual_ts
    # OHLC 虚拟根: open=前收 high=max(low, live) low=min(open, live) close=live
    new_row["open"] = float(df_closed.iloc[-1]["close"])
    new_row["close"] = float(live_price)
    new_row["high"] = max(float(new_row["open"]), float(live_price))
    new_row["low"] = min(float(new_row["open"]), float(live_price))
    new_row["volume"] = 0.0
    import pandas as _pd
    df_v = _pd.concat([df_v, _pd.DataFrame([new_row])], ignore_index=True)

    df_v, cb_threshold = compute_indicators(df_v, cfg)
    pos = infer_position(df_v, cfg)
    snap = snapshot(df_v, pos, live_price, cfg)
    # 覆盖 snapshot 的 last_closed 为虚拟根时间, 让上游能区分
    snap["is_virtual_probe"] = True
    snap["virtual_root_time"] = virtual_ts.isoformat()
    snap["bull_streak"] = float(df_v.iloc[-1]["bull_streak"])
    snap["bear_streak"] = float(df_v.iloc[-1]["bear_streak"])
    snap["ema"] = float(df_v.iloc[-1]["ema"])
    snap["atr"] = float(df_v.iloc[-1]["atr"])
    snap["dev_pct"] = float(df_v.iloc[-1]["dev_pct"])
    snap["rsi"] = float(df_v.iloc[-1]["rsi"])
    snap["extreme_long"] = bool(df_v.iloc[-1]["top_long_exit"]) if "top_long_exit" in df_v.columns else False
    snap["extreme_short"] = bool(df_v.iloc[-1]["top_short_exit"]) if "top_short_exit" in df_v.columns else False
    return snap


def probe_change_summary(prev_state, probe_state):
    """对比上一探针 snapshot 与新探针, 返回如果有变化则变化文字 (list[str]); 否则 []."""
    if prev_state is None or not prev_state.get("is_virtual_probe", False):
        return []
    if not probe_state.get("is_virtual_probe", False):
        return []
    out = []
    if prev_state["position"] != probe_state["position"]:
        dir_map = {1: "做多", -1: "做空", 0: "空仓"}
        out.append(f"[盘中预演] 临反手: {dir_map[prev_state['position']]} → {dir_map[probe_state['position']]} @ {probe_state['live_price']:.4g}")
    if abs(prev_state["pos_size"] - probe_state["pos_size"]) > 0.01:
        if probe_state["pos_size"] < prev_state["pos_size"]:
            out.append(f"[盘中预演] 临止盈: 仓位 {prev_state['pos_size']*100:.0f}% → {probe_state['pos_size']*100:.0f}% @ {probe_state['live_price']:.4g}")
    return out
