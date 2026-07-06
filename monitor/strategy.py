"""
策略核心 - 纯函数式, 不读配置文件、不发通知、不写状态.
输入: cfg (dict, 来自 strategies.json 一条记录) + 已收盘 DataFrame, 输出状态/场景.
所有 K 线形态止盈信号与 step1-3/step6 研究口径一致 (来自 xag_monitor.py 的 _compute_top_signals).
"""
import json
import numpy as np
import pandas as pd


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

    has_top_signals = "top_long_exit" in df_closed.columns
    start = max(ema_span * 2, atr_span + 2)
    for i in range(start, n):
        r = df_closed.iloc[i]
        if tp_enabled and position != 0 and pos_size > 0.01 and (i - last_tp_idx) >= cool_bars:
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

    if cfg.get("tp_enabled", True) and float(cfg.get("part_ratio", 0.15)) > 0:
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
        lines.append(f"  止盈: {cfg.get('tp_type')} 比例{float(cfg['part_ratio'])*100:.0f}% 冷却{int(cfg.get('cool_bars',20))}根")
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
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    minutes = tf_minutes(timeframe)
    minute = now.minute
    next_mark = (minute // minutes + 1) * minutes
    if next_mark >= 60:
        next_time = now.replace(minute=next_mark - 60, second=0, microsecond=0) + timedelta(hours=1)
    else:
        next_time = now.replace(minute=next_mark, second=0, microsecond=0)
    return (next_time - now).total_seconds() + 5
