# 任务：从国内量化平台捞策略，扔进已有框架重跑并证伪

## 一句话

去聚宽 / 果仁 / 米筐这些平台找一批**公开的 A 股选股策略**，把它们的**规则**（不是代码、
不是收益率）提取出来，用 `/Users/gongzhao/code/misc/astock_quant/` 里已有的回测框架
重新实现和回测，然后按 `quant-backtest-protocol` 做四层证伪，最后告诉我**哪些是真的**。

**默认立场：平台上贴出来的净值曲线，一条都不信。** 那些数字里普遍混着前复权、
幸存者偏差、涨跌停照买、成本按 0 算、以及在同一段数据上反复调参。你的产出不是
"复现了它的收益率"，而是"它在干净口径下还剩多少"。

---

## 一、先看已有资产，别重造

框架在 `/Users/gongzhao/code/misc/astock_quant/`，**数据已经下好了**（约 1.3G）：

- `data/panel/*.parquet` — 宽表面板，2836 个交易日 × 5282 只股票，2015-01 ~ 2026-09，
  **含 255 只样本期内退市的股票**（无幸存者偏差）。字段：open/high/low/close（后复权）、
  volume（已统一成「手」）、amount（估算成交额）、close_raw（不复权收盘）。
- `data/kline_hfq/`、`data/kline_raw/` — 5477 只个股原始 CSV，腾讯行情。
- 读数据：`from aq import panel; p = panel.load_panels()`

先跑 `python3 -m pytest tests/ -q`（41 项应全过），再读 `README.md`——里面有踩坑记录，
**读完能省你半天**。核心接口：

```python
from aq import panel, universe, factors, strategy, backtest, walkforward, validate, metrics

p     = panel.load_panels()                    # dict[str, DataFrame]  date × code
mask  = universe.investable(p)                 # PIT 可投池（上市满250日/未停牌/成交额/疑似ST）
fp    = factors.build_all(p)                   # 17 个现成的量价因子
score = strategy.composite(fp, {"rev20":0.5,"vol60":0.5}, mask)     # 你的打分放这里
rb    = strategy.rebalance_dates(p["close"].index, freq=20, start="2016-01-04")
sig   = strategy.top_n_signals_buffered(score, rb, top_n=300, buffer_mult=3)
res   = backtest.run(p, sig, start="2019-01-02", end="2026-09-01")
# res: equity / ret / turnover / n_holdings / cost / cash_weight / blocked_frac
```

引擎已建模：**信号 T、成交 T+1 开盘**、涨停开盘不可买、跌停开盘不可卖、一字板双向
不可成交、停牌不可交易且按上一有效价估值、退市按最后价清算、T+1、现金约束、
未成交委托顺延、印花税按历史税率（2023-08-28 减半）。成本：佣金万 2.5 + 过户费
十万分之一 + 滑点单边 10bp + 印花税卖出单边。**成本是输入不是参数，不许调。**

后台跑长任务用 `/opt/homebrew/bin/python3.11` 绝对路径（`python3` 在非交互 shell 里
是 3.14，没装 pyarrow，读 parquet 会直接报错），并且用 run_in_background 而不是
`nohup ... &` 后接 sleep（会被工具超时连带杀掉）。

---

## 二、去哪找，找什么

| 平台 | 拿什么 | 注意 |
|---|---|---|
| **聚宽 JoinQuant** 策略广场 / 社区帖 | Python 源码，规则最清楚 | 多数用 `get_price(fq='pre')` 前复权 —— 直接就是坑 |
| **果仁网 Guorn** 策略排行 | 无代码配置：因子 + 排序 + 调仓周期 + 过滤条件 | 规则最容易翻译；但排行榜天然是幸存者筛选的结果 |
| **米筐 RiceQuant** | Python 源码 | 同聚宽 |
| **掘金量化 / 优矿 / 天软** 社区 | 源码或研报复现 | 优矿受限，能拿到多少算多少 |
| **雪球 / 集思录 / 知乎专栏** 的策略贴 | 规则描述 | 常缺关键细节，缺什么就明确标注「原文未说明，我假设 X」 |
| **券商金工研报**（如果能拿到） | 因子定义最规范 | 优先级最高，因子定义可直接抄 |

**找什么样的**（按优先级）：

1. **纯量价 / 纯规则、不依赖财务数据的选股策略** —— 本框架能直接跑，无需额外数据。
2. **依赖低频财务数据的**（ROE、PB、股息率、净利润增速等）—— 数据得另找，
   而且**必须用公告日而不是报告期对齐**，否则就是未来函数。拿不到 PIT 公告日就
   明确写「因缺少 PIT 财报数据，本策略无法验证」，不要凑合。
3. **择时 / 仓位控制类** —— 本框架是满仓选股引擎，需要扩展，先记下来别急着做。
4. 明确**跳过**：高频/日内、可转债、期货、需要 Level-2 或分钟数据的。

目标：**捞 8~15 个能跑的策略**，覆盖不同家族（反转、动量、低波、质量、小市值、
量价背离、北向资金、龙虎榜……）。宁可少而准。

联网用本环境的 `web-access` skill。**平台登录墙**：能读公开页就读公开页；
需要账号才能看的内容，不要尝试绕过，直接记录「需登录，未取到」并换下一个。

---

## 三、怎么翻译

对每个策略，产出一份 **规则卡**（先写卡，再写代码）：

```yaml
名称: 低波+反转双因子
出处: https://... （平台/作者/发布时间）
原文声称: 年化 38%，最大回撤 12%，回测区间 2015-2023
股票池: 全A，剔除ST、剔除上市不足60日、剔除停牌
打分: 60日波动率升序排名 * 0.5 + 20日涨跌幅升序排名 * 0.5
持仓: 打分最高的 20 只，等权
调仓: 每 5 个交易日
卖出: 全部换仓（无个股止损）
原文未说明、我的假设:
  - 成交价：原文未说，我按 T+1 开盘
  - 涨跌停：原文未处理，我按开盘涨停不可买
数据需求: 仅量价（本框架可直接跑）
```

然后实现成一个函数，放在 `strategies_ext/<名字>.py`：

```python
def score(panels, mask):
    """返回 DataFrame(date × code)：数值越大越该买，池外为 NaN。
    铁律：只能用 <= 当日收盘的数据。禁止 shift(负数) / bfill / 全样本标准化。"""
```

**规则要照抄，不要「顺手优化」。** 你的任务是检验它，不是改进它。原文有明显缺陷
（比如没说涨跌停怎么办）就用框架默认的保守处理，并在规则卡里写清楚是你补的。

---

## 四、验收：调用 `quant-backtest-protocol` skill

**不要重新手写检验代码**，skill 里 `scripts/qbt.py` 和 `scripts/causality_check.py`
都是现成的。对每个策略按顺序做：

**第 0 关 · 因果闸（不过就作废，别往下走）**

```bash
python3 ~/.claude/skills/quant-backtest-protocol/scripts/causality_check.py \
  --mode panel --fn strategies_ext/<名字>.py:panel_signal \
  --data-dir verified/causal_data --glob "*.csv" --points 10
```
横截面策略**必须** `--mode panel`。参考 `verified/panel_adapter.py` 写适配器。
本框架自带的 `tests/test_no_lookahead.py` 是更强的补充（整条净值曲线的截断不变性），
新策略也应该被它覆盖 —— 往 `_pipeline()` 里挂上你的 score 函数即可。

**第 1 关 · 干净口径回测**：`backtest.run(...)`，滚动样本外 2019-01 ~ 2026-09。
**基准不是沪深300，是 `universe.equal_weight_benchmark(p, mask)`（同一可投池的等权组合）**
—— 跑不赢它说明选股这一步没加分。同时报沪深300 / 中证500 作为"不选股就买指数"的对照。

**第 2~4 关 · 四层证伪**：

```bash
python3 ~/.claude/skills/quant-backtest-protocol/scripts/qbt.py report \
  --returns verified/<名字>_returns.csv --bench verified/bench_ew.csv \
  --trials verified/<名字>_trials.json --panel verified/universe_panel.csv \
  --market cn_stock --n-long <持股数> --hold <调仓周期> --iters 200 \
  --out verified/<名字>_verdict.json
```

判读线：alpha ≤ 0 作废 / DSR < 0.90 不显著 / prob(profit) < 10% 作废 / 置换分位 < 95% 作废。
另外补一条 **逐年剔除**（`scripts/run_jackknife.py`）：每次去掉一整年重算 alpha，
看是不是靠某一年撑着 —— 我这轮的教训就是超额有一大半来自 2024 一年。

**参数别搜。** 用原文给的参数跑。真要看敏感性，扫一个小网格并把**所有**试验轮数
记进 trials json（DSR 要用），不要挑最好那组当结论。

---

## 五、已知的坑（直接抄，别自己再踩一遍）

1. **前复权是未来函数**。前复权价会在未来分红送转发生时被改写。全流程只用后复权。
   平台代码里看到 `fq='pre'` / `adjust='qfq'`，先在规则卡里标红。
2. **幸存者偏差**。用"当前上市列表"做股票池会天然剔除所有退市公司。本框架的池子是
   代码空间穷举来的，含退市股 —— 别自己改回去。
3. **科创板成交量单位是「股」不是「手」**，比其他板块大 100 倍。框架已在
   `panel.build_panel` 里折算，你若另外取数要自己处理。
4. **脏数据**：连续交易日 |涨跌幅| > 25% 的记录（A 股有涨跌停，不可能）几乎都是复权
   因子出错或退市整理期数据，一根就能把等权组合净值打穿。框架已自动截断。
5. **调仓日权重要先补 0 再 ffill**。直接 ffill 会让上期选中、本期落选的股票把旧权重
   一路带下去，权重和能滚到 6 倍。看 `quicktest.daily_weights` 和它的测试。
6. **最小成交额阈值**：引擎跳过小于总资产 0.05% 的委托。持仓上千只时单只低于这个数，
   买卖会被**静默跳过**，回测悄悄变成"拿着不动"。这个阈值是**相对**总资产的，加资金没用。
   跑完必查 `res.blocked_frac`，**超过 5% 结论作废**。
7. **Rank IC 高 ≠ 能赚钱**。我这轮有个因子 ICIR 1.02、t=7.92，等权组合的净超额是 0。
   IC 衡量排序，等权组合赚的是均值，A 股收益右偏，两者能同时成立还互相矛盾。
   **一律以 `backtest.run` 的净值为准，IC 只用于初筛。**
8. **成本门槛可以直接算**：A 股双边约 0.35%。年化换手 20 倍 = 每年白交 3.5%。
   **周频以上调仓、毛 alpha 不到 4% 的策略，可以直接判死。**
9. **回测里超预期的好结果，默认当 bug 线索处理，不是发现。** 我这轮三个 bug
   （权重滚 6 倍、委托被静默跳过、科创板单位）全是因为"数字太好看"才查出来的。

---

## 六、交付

1. `strategies_ext/` — 每个策略一个 py + 一张规则卡（md）
2. `verified/<名字>_verdict.json` — skill 脚本出的裁决
3. 一份汇总表，每行一个策略：
   `名称 | 出处 | 原文声称年化 | 干净口径年化 | 对等权超额 | alpha & NW t | DSR | 置换分位 | 逐年剔除最低t | 换手 | 成本 | blocked_frac | 裁决`
4. 一段结论，按这个格式写（有数、有归因、有证伪、有可执行判断）：

> 样本外 2019-01~2026-09：年化 X%、夏普 Y、最大回撤 Z%；对可投池等权超额 A%/年，
> β_沪深300 B、净收益年化 alpha C%（NW t=D）；置换分位 E%、DSR F、
> 剔除最不利年份后 alpha 降至 G%。**结论：……不具备/具备上仓位条件。**

5. 最后回答我三个问题：
   - **有没有一个策略在干净口径下 alpha 显著（t ≥ 2）且 DSR ≥ 0.90？**
   - **平台声称的收益率和干净口径差了多少？差距主要来自哪个环节**
     （前复权 / 幸存者偏差 / 成本 / 涨跌停 / 参数拟合）？
   - **有没有哪一类因子是我这轮 17 个量价因子没覆盖、且和它们不相关的？**
     （我这边 17 个因子相关性极高，有效自由度只有 2~3 个，最缺正交信息源。）

**没跑完证伪，就别下"这策略能用"的结论。**
