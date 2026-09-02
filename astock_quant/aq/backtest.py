"""组合回测引擎。

时序约定（防未来函数的核心）：
    t 日收盘 → 用 <= t 的数据算因子、定目标权重
    t+1 开盘 → 按目标权重成交，受涨跌停 / 停牌 / 现金约束
    t+1 收盘 → 按收盘价估值
即"信号 T、成交 T+1 开盘"。引擎内部只按日期正序推进，任何一天都拿不到
之后的数据；tests/test_no_lookahead.py 用"数据截断后重跑，历史净值必须逐点
相同"来机器验证这一点。

其他已建模的现实约束：
    - 停牌（当日无 K 线或成交量为 0）：不可买不可卖，持仓按上一有效价估值
    - 涨停开盘不可买、跌停开盘不可卖、一字板双向不可交易
    - 退市：最后一个交易日之后按最后收盘价清算（并计卖出成本）
    - 现金约束：买入总额不超过可用现金，超出部分按比例缩减
    - T+1：当日买入的股票当日不可卖出（引擎结构上不会产生同日双向交易）
    - 交易成本：佣金 + 过户费 + 滑点 + 印花税（印花税按历史税率表取值）
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import config, rules


@dataclass
class BacktestResult:
    equity: pd.Series
    ret: pd.Series
    turnover: pd.Series
    n_holdings: pd.Series
    cost: pd.Series
    cash_weight: pd.Series
    blocked_value: pd.Series = None      # 因低于最小成交额被跳过的委托金额
    intended_value: pd.Series = None     # 本应成交的委托金额
    holdings: dict = field(default_factory=dict)

    @property
    def blocked_frac(self) -> float:
        """被最小成交额阈值挡掉的委托占比。

        持仓只数太多、单只仓位小于阈值时，买卖会被静默跳过，回测就变成了
        "拿着不动"，换手率和业绩都失真。这个比例超过 5% 结论就不可信了 ——
        真实含义是"这个持仓宽度在这个资金量上根本下不了单"。
        """
        if self.blocked_value is None or self.intended_value is None:
            return 0.0
        tot = float(self.intended_value.sum())
        return float(self.blocked_value.sum() / tot) if tot > 0 else 0.0

    @property
    def nav(self) -> pd.Series:
        return self.equity / self.equity.iloc[0]


def _next_trading_day(dates: pd.DatetimeIndex, d: pd.Timestamp):
    pos = dates.searchsorted(d, side="right")
    return dates[pos] if pos < len(dates) else None


def run(panels: dict[str, pd.DataFrame],
        signals: pd.DataFrame,
        start: str | pd.Timestamp = None,
        end: str | pd.Timestamp = None,
        init_cash: float = 1e7,
        exec_price: str = "open",
        min_trade_frac: float = 5e-4,
        zero_cost: bool = False,
        keep_holdings: bool = False) -> BacktestResult:
    """signals: index=信号日(t)，columns=股票代码，值=目标权重（不足 1 的部分为现金）。"""
    close = panels["close"]
    dates = close.index
    start = pd.Timestamp(start) if start is not None else dates[0]
    end = pd.Timestamp(end) if end is not None else dates[-1]

    trade = rules.tradability(panels, price=exec_price)
    codes = list(close.columns)
    cidx = {c: i for i, c in enumerate(codes)}

    C = close.to_numpy(dtype=np.float64)
    P = (panels["open"] if exec_price == "open" else close).to_numpy(dtype=np.float64)
    CB = trade["can_buy"].to_numpy()
    CS = trade["can_sell"].to_numpy()

    valid = np.isfinite(C)
    # 每只股票最后一根有效 K 线的行号，用于识别退市
    last_row = np.where(valid.any(axis=0), valid.shape[0] - 1 - valid[::-1].argmax(axis=0), -1)

    # 信号日 -> 执行日（下一个交易日）
    exec_targets: dict[int, np.ndarray] = {}
    for sig_date, row in signals.iterrows():
        sig_date = pd.Timestamp(sig_date)
        ed = _next_trading_day(dates, sig_date)
        if ed is None or ed > end:
            continue
        w = np.zeros(len(codes))
        sub = row.dropna()
        for code, wt in sub.items():
            j = cidx.get(code)
            if j is not None and wt > 0:
                w[j] = float(wt)
        exec_targets[dates.get_loc(ed)] = w

    n = len(codes)
    shares = np.zeros(n)
    mark = np.zeros(n)          # 最近一个有效收盘价（估值用）
    cash = init_cash
    active_w = np.zeros(n)      # 当前目标权重
    pending = np.zeros(n, dtype=bool)   # 未成交的委托（涨跌停/停牌/现金不足）
    has_target = False

    i0 = dates.searchsorted(start, side="left")
    i1 = dates.searchsorted(end, side="right")
    out_dates, out_eq, out_to, out_nh, out_cost, out_cw = [], [], [], [], [], []
    out_blocked, out_intended = [], []
    holdings_log: dict = {}
    buy_rate = 0.0 if zero_cost else rules.buy_cost_rate()

    for i in range(i0, i1):
        d = dates[i]
        sell_rate = 0.0 if zero_cost else rules.sell_cost_rate(d)
        px_exec = P[i]
        px_close = C[i]
        day_cost = 0.0
        day_turnover = 0.0
        day_blocked = 0.0
        day_intended = 0.0

        # 1) 退市清算：最后一根 K 线之后，按最后有效价卖出
        dead = (shares > 0) & (last_row < i)
        if dead.any():
            proceeds = float((shares[dead] * mark[dead]).sum())
            day_cost += proceeds * sell_rate
            day_turnover += proceeds
            cash += proceeds * (1 - sell_rate)
            shares[dead] = 0.0

        # 2) 调仓：调仓日按新目标下单；非调仓日只补做上次被涨跌停/停牌/现金
        #    卡住的未完成委托（真实交易里也是顺延到下一个交易日继续挂单）
        do_rebalance = i in exec_targets
        if do_rebalance:
            active_w = exec_targets[i]
            has_target = True
        if has_target and (do_rebalance or pending.any()):
            px_val = np.where(np.isfinite(px_exec), px_exec, mark)  # 停牌按上一收盘估值
            cur_val = shares * px_val
            equity_open = cash + float(cur_val.sum())
            target_val = active_w * equity_open
            floor = max(min_trade_frac * equity_open, 1.0)
            attempt = np.ones(n, dtype=bool) if do_rebalance else pending.copy()
            tradable = np.isfinite(px_exec) & (px_exec > 0)
            gap = np.abs(target_val - cur_val)
            day_intended += float(gap[attempt].sum())
            day_blocked += float(gap[attempt & (gap <= floor) & (gap > 0)].sum())

            # 先卖
            diff = cur_val - target_val
            sell_mask = attempt & (diff > floor) & CS[i] & tradable & (shares > 0)
            if sell_mask.any():
                sell_val = np.minimum(diff[sell_mask], cur_val[sell_mask])
                shares[sell_mask] -= sell_val / px_exec[sell_mask]
                shares[shares < 1e-12] = 0.0
                gross = float(sell_val.sum())
                cash += gross * (1 - sell_rate)
                day_cost += gross * sell_rate
                day_turnover += gross

            # 再买（受现金约束，买不满的部分留到下一日继续）
            diff2 = target_val - shares * px_val
            buy_mask = attempt & (diff2 > floor) & CB[i] & tradable
            if buy_mask.any():
                buy_val = diff2 * buy_mask
                need = float(buy_val.sum()) * (1 + buy_rate)
                if need > cash:
                    buy_val = buy_val * (cash / need if need > 0 else 0.0)
                shares[buy_mask] += buy_val[buy_mask] / px_exec[buy_mask]
                gross = float(buy_val.sum())
                cash -= gross * (1 + buy_rate)
                day_cost += gross * buy_rate
                day_turnover += gross

            # 记录仍未完成的委托，下一交易日继续尝试
            resid = np.abs(shares * px_val - target_val)
            pending = attempt & (resid > floor)

        # 3) 收盘估值
        upd = np.isfinite(px_close)
        mark[upd] = px_close[upd]
        equity = cash + float((shares * mark).sum())

        out_dates.append(d)
        out_eq.append(equity)
        out_to.append(day_turnover / equity if equity > 0 else 0.0)
        out_nh.append(int((shares > 0).sum()))
        out_cost.append(day_cost / equity if equity > 0 else 0.0)
        out_cw.append(cash / equity if equity > 0 else 0.0)
        out_blocked.append(day_blocked)
        out_intended.append(day_intended)
        if keep_holdings and i in exec_targets:
            held = np.where(shares > 0)[0]
            holdings_log[d] = pd.Series(
                {codes[j]: shares[j] * mark[j] / equity for j in held}).sort_values(ascending=False)

    idx = pd.DatetimeIndex(out_dates)
    equity = pd.Series(out_eq, index=idx, name="equity")
    return BacktestResult(
        equity=equity,
        ret=equity.pct_change().fillna(0.0),
        turnover=pd.Series(out_to, index=idx),
        n_holdings=pd.Series(out_nh, index=idx),
        cost=pd.Series(out_cost, index=idx),
        cash_weight=pd.Series(out_cw, index=idx),
        blocked_value=pd.Series(out_blocked, index=idx),
        intended_value=pd.Series(out_intended, index=idx),
        holdings=holdings_log,
    )
