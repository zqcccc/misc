# protocol · 从想法到可交易候选

## 1. 时间切分：滚动样本外优先

金融策略面对的是随时间变化的分布。默认使用 expanding/rolling walk-forward，而不是随机 KFold：

```text
fold 1  [ train ------ ][ valid ][ OOS ]
fold 2  [ train ------------ ][ valid ][ OOS ]
fold 3  [ train ------------------ ][ valid ][ OOS ]
```

- train 用于拟合；valid 用于有限选择；每个 fold 的 OOS 只使用此前已经确定的规则。
- 预测标签跨越多日/多根 bar 时，在 train/valid/OOS 边界使用 purge；信息或持仓持续影响后续样本时再加 embargo。
- 把所有 OOS fold 拼成唯一的日收益序列，用它做归因、路径和置换。不要拿 FULL 的成交去给 OOS 报告做 MC。
- 保留最终 sealed TEST 可以提高置信度，但不是强制中心。看过以后可以继续研究，只要诚实地把它降级为开发历史，并用新的时间前推或实时 paper trading 获取新证据。

## 2. 先锁死“角色、基准、死线”

每张卡先声明角色：

| 角色 | 主基准 | 主要成功条件 |
|---|---|---|
| alpha | 风险匹配的可实施基准；横截面默认同池等权 | 净 alpha 的统计与经济下界为正 |
| diversifier | 现有组合 | 固定权重加入后 OOS 风险收益改善 |
| hedge | 无对冲组合 + 预定义压力窗口 | 尾部损失下降且长期保费可接受 |
| execution | 原执行算法 | 同订单流和风险下成交成本下降 |

“低 beta、回撤更小”可能是好产品，但不是 alpha。它只有在分散器或对冲角色下、对现有组合确实有增量时才算有用。

## 3. 成交时序契约

每个策略必须提交 `execution_manifest.json`：

```json
{
  "information_time": "SPY t-1 close 16:00 America/New_York",
  "decision_time": "immediately after SPY t-1 close",
  "execution_time": "local market t open",
  "pnl_start": "local market t open",
  "pnl_end": "local market t close",
  "price_field": "official open with conservative slippage",
  "timezone": "exchange local, normalized to UTC",
  "pnl_start_not_before_execution": true,
  "validated": true
}
```

验收问题不是“代码有没有 shift(1)”，而是：

1. 该字段何时正式发布？
2. 信号计算完成时市场是否仍开放？
3. 回测成交价出现在信号之前还是之后？
4. 信号公布后剩余的收益是多少？
5. 若声称交易盘后/期货，是否真的使用该场所当时的报价与成本？

事件策略必须把公告计划时间和实际发布时间分开。跨市场策略必须把每个交易所的时区、休市和 DST 分开处理。

## 4. 搜索账本

任何可能影响最终选择的试验都记录：参数、资产池、窗口、过滤器、成本、目标函数、随机种子、结果和失败原因。

```json
{
  "research_family": "Hxxxx",
  "objective": "valid net alpha lower bound",
  "trials": [
    {
      "trial_id": 1,
      "parent": null,
      "change": "prior specification",
      "params": {"lookback": 20},
      "train_sharpe": 0.81,
      "valid_sharpe": 0.52,
      "status": "kept"
    }
  ]
}
```

- 允许根据失败原因继续迭代；有效研究本来就是循环。
- 不能把迭代后的赢家重新包装成“唯一事前假设”。整条 lineage 的尝试都计入 DSR 和活动级多重检验。
- 选相邻参数都成立的平台，不选一个尖锐峰值。
- 目标函数优先使用净收益的经济下界，例如 `valid_alpha - 2*SE - stressed_cost`，而不是裸 Sharpe argmax。

## 5. 数据 manifest

候选晋级时提交 `data_manifest.json`：

```json
{
  "sources": [
    {
      "provider": "official exchange/API",
      "url_or_query": "exact endpoint and parameters",
      "retrieved_at": "2026-09-04T00:00:00Z",
      "raw_file": "data_raw/source.csv",
      "sha256": "64 hex characters",
      "rows": 12345,
      "start": "2018-01-01",
      "end": "2026-09-03",
      "timezone": "UTC",
      "adjustment": "unadjusted / point-in-time corporate actions"
    }
  ]
}
```

原始层只追加不覆盖；清洗层记录代码版本。抽查时优先用官方一手源；同一聚合商重新下载只能排除本地损坏，不能算独立确认。

## 6. 成本与容量

第一轮可以用固定保守 bps 快速证伪，晋级时至少报告：

- 费用、买卖价差和滑点；
- 换手及成本占毛边际比例；
- 资金费、融资、借券和保证金；
- 停牌、涨跌停、深度不足、下架等 blocked fraction；
- 按目标资金规模/ADV participation 的冲击压力；
- 基准成本与策略成本是否公平。

毛边际若不到总成本的 2 倍，通常不值得精做。压力成本翻倍后经济下界为负，最多 PARK。

## 7. 最小可复现输出

每个可交易候选至少落这些文件：

```text
verified/Hxxxx/
├── verdict.json
├── execution_manifest.json
├── data_manifest.json
├── trials.json
├── oos_returns.csv
├── oos_benchmark.csv
├── daily_positions.csv
├── trades.csv
└── reproduce.txt
```

`daily_positions.csv` 和 `trades.csv` 必须能重建 `oos_returns.csv`。报告内所有统计层必须使用相同 OOS 起止日期。

