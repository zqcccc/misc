# verified/ —— 假设卡产物归档索引

每张卡一个目录，`Hxxxx/manifest.json` 是**唯一权威映射**：哪条序列/哪份报告是这张卡 §7 数字的出处、
哪些是变体或旧口径（`superseded`）、重算与卡片对不对得上（`discrepancies`）、缺什么（`missing`）。
小文件（收益/基准 csv、裁决 json）已复制进各卡目录；大文件（面板 parquet、行情缓存）只记路径 + sha256 + 行数。

生成方式：归档时逐张读卡 §6/§7 → 定位产物 → 用序列重算年化/夏普/回撤与卡片对账。**没有重跑任何回测，没有改任何 §7 数字或裁决。**

## 怎么用

```python
import json, pandas as pd
m = json.load(open("verified/H0019/manifest.json"))
r = pd.read_csv(m["authoritative"]["returns_trainvalid"]["path"], index_col=0, parse_dates=True)["ret"]
```
下表只列每张卡的**主**序列；判读段是哪一段（有的卡以 TRAIN+VALID 判读、有的以 TEST 揭盲一次判读）写在 manifest 里对应条目的 `note`。

引用任何数字前先读该卡的 `discrepancies` —— 各卡的年化/夏普/回撤口径**不统一**，见文末。

## PARK —— 有东西但还不能用（8 张）

| 卡 | 标题 | 权威收益序列（主）＋TEST=另有 TEST 段 | 窗口 | n | 状态 |
|---|---|---|---|---|---|
| [H0002](H0002/manifest.json) | A股 低波+反转 小微盘多因子 | `astock_quant/verified/oos_returns.csv` | 2019-01-02~2026-09-01 | 1860 | ✔ |
| [H0003](H0003/manifest.json) | Binance BTC/ETH 资金费 delta 中性收割 | `crypto_perp/ret_V0.csv` | 2019-09-10~2026-09-03 | 2551 | 缺 1 |
| [H0010](H0010/manifest.json) | 恒生 AH 溢价 H 股折价均值回复 | `quant_research/hk_stock/out/returns_long_only.csv` | 2015-01-05~2026-08-28 | 2750 | 缺 1 |
| [H0014](H0014/manifest.json) | SPY FOMC 公告日溢价 | `us_stock/ret_w1.csv` | 1994-01-03~2026-09-02 | 8222 | 缺 2 |
| [H0019](H0019/manifest.json) | 港股通南向净买入 20 日 z-score 择时 2800 | `hk_southbound/out/h19_ret_trainvalid.csv` ＋TEST | 2016-01-21~2023-12-29 | 1807 | ✔ |
| [H0021](H0021/manifest.json) | 做空 VIX 期货 30 天恒定到期 | `quant_research/vol/data/qbt_v0_full.csv` ＋TEST | 2011-01-05~2026-09-02 | 3938 | ✔ |
| [H0022](H0022/manifest.json) | A股质量因子（ROE+稳定性+经营现金流） | `quant_research/cn_stock/out/equity_primary.csv` | 2016-01-04~2026-09-01 | 2591 | ✔ |
| [H0024](H0024/manifest.json) | A股流通市值最小 20% 纯多 | `quant_research/cn_stock/out_h0024/equity_primary.csv` | 2016-01-04~2026-09-01 | 2591 | ✔ |

## FAIL —— 这条路死了（22 张）

| 卡 | 标题 | 权威收益序列（主）＋TEST=另有 TEST 段 | 窗口 | n | 状态 |
|---|---|---|---|---|---|
| [H0001](H0001/manifest.json) | A股中期动量（60/120日、52周新高） | `—` |  | — | ⚠ 无序列 |
| [H0004](H0004/manifest.json) | HYG/IEF 信用风险偏好择时 SPY | `us_equity_timing/out/ret_trainvalid.csv` ＋TEST | 2007-08-30~2019-12-31 | 3106 | ✔ |
| [H0005](H0005/manifest.json) | VIX/VIX3M 期限结构择时 SPY | `us_stock/ret_full.csv` ＋TEST | 2006-07-17~2026-07-17 | 5032 | 缺 1 |
| [H0006](H0006/manifest.json) | 天然气 UNG 冬强夏弱日历 | `futures/ret_full.csv` ＋TEST | 2007-04-18~2026-09-02 | 4876 | 缺 1 |
| [H0007](H0007/manifest.json) | Binance 永续新上市负漂移做空 | `crypto_perp/out/ret_trainvalid.csv` ＋TEST | 2020-01-08~2025-01-30 | 1850 | ✔ |
| [H0008](H0008/manifest.json) | Cochrane-Piazzesi 因子久期倾斜 | `rates/data/h0008_main_ret.csv` ＋TEST | 2007-07-03~2026-09-02 | 4823 | 缺 1 |
| [H0009](H0009/manifest.json) | 跨市场 lead-lag（美股→亚欧时区传导） | `—` |  | — | ⛔ 全部作废 |
| [H0011](H0011/manifest.json) | Binance 永续 15m 短期均值回归 | `quant_research/crypto_perp/reversal_h0011/out/returns_taker_5bp.csv` | 2020-09-14~2026-08-31 | 2173 | ✔ |
| [H0012](H0012/manifest.json) | Binance 现货 3 日横截面反转 | `crypto_spot/out/ret_trainvalid.csv` ＋TEST | 2017-12-20~2023-12-31 | 2203 | ✔ |
| [H0013](H0013/manifest.json) | 商品期货隔夜→日内横截面反转 | `—` |  | — | ⚠ 无序列 |
| [H0015](H0015/manifest.json) | G10 利差 carry 多空 | `fx/ret_main.csv` | 2004-01-01~2026-03-31 | 5789 | 缺 2 |
| [H0016](H0016/manifest.json) | Henry Hub EIA 库存公告日溢价 | `quant_research/commodity/event_h0016/returns_full.csv` ＋TEST | 2007-04-18~2026-09-02 | 4876 | ✔ |
| [H0017](H0017/manifest.json) | 港股通南向持股占比 5 日变化选股 | `hk_southbound/out/ret_trainvalid.csv` ＋TEST | 2024-09-30~2025-12-31 | 309 | ✔ |
| [H0018](H0018/manifest.json) | G10 汇率 12-1 月动量 | `—` |  | — | ⚠ 无序列 |
| [H0020](H0020/manifest.json) | 9 只 Select Sector SPDR 的 HRP | `quant_research/us_stock/hrp_h0020/artifacts/test_returns.csv` | 2021-01-04~2026-09-02 | 1423 | ✔ |
| [H0023](H0023/manifest.json) | COT 商业套保压力横截面 | `futures/data/cot/out/is_returns.csv` ＋TEST | 2011-10-03~2021-12-31 | 2580 | 缺 1 |
| [H0025](H0025/manifest.json) | Binance 永续资金费率横截面多空 | `crypto_perp/h0025/out/strat_full.csv` ＋TEST | 2020-01-02~2026-08-31 | 2434 | ✔ |
| [H0026](H0026/manifest.json) | 发达市场（非美）经营盈利能力最高组 | `quant_research/multi/profitability_h0026/artifacts/test_returns.csv` | 2015-01-01~2026-07-31 | 3022 | ✔ |
| [H0027](H0027/manifest.json) | 拍卖需求随机森林选债 ETF | `quant_research/rates/auction_ml_h0027/out/valid_strategy.csv` | 2019-01-02~2021-12-31 | 757 | 缺 3 |
| [H0028](H0028/manifest.json) | A股 20 日累计隔夜收益反转 | `quant_research/cn_stock/out_h0028/equity_primary.csv` | 2016-01-04~2026-09-01 | 2591 | ✔ |
| [H0029](H0029/manifest.json) | Binance 永续 21:00-23:00 UTC 时段多头 | `crypto_perp/h0029/results/strategy_full.csv` ＋TEST | 2020-01-02~2026-08-31 | 2434 | 缺 2 |
| [H0030](H0030/manifest.json) | 8 张 PARK 风险平价合成组合 | `—` |  | — | ⚠ 无序列 |

## 需要特别注意的几张

- **H0013** —— `authoritative` 为空，**结论已无法复现**。§7b 的全部数字只在卡片文字里；`futures/verified/` 是空目录，`run_h0013.py` / `falsify_h0013.py` 已不在仓库。只剩输入面板 `futures/data/panel13/`（已记 sha）。
- **H0018** —— 证伪脚本只写 json 不导序列，没有收益曲线，无法接入任何组合层研究。
- **H0001** —— 纯 IC 检验，本来就没有组合回测；mom60 / mom120 的样本外 ICIR 无对应产物。
- **H0030** —— 组合层研究，只有汇总表 `weightings.txt` / `overlap.txt`，没有落盘组合收益序列。
- **H0004** —— 卡片 §7 第 1 行的 TRAIN+VALID 列与 TEST 列不是同一口径（算术年化+钱包回撤 vs 复利年化+复利回撤），不能横向比。
- **H0008** —— 收益序列比卡片声明的 FULL 窗口早 5 个月（2007-07 vs 2007-12），直接重算年化会偏高。
- **H0009 —— 最该警惕的一张，产物全部作废。** §7 是一张四层全绿的 PASS 表（净年化 24.3%/夏普 3.04/alpha 18.9% t=8.58/置换分位 100%），§8 正文至今写着「裁决：PASS」；但 frontmatter 是 **FAIL**，因为同日 07:52Z 的成交时点复核发现：SPY 信号在亚洲/欧洲前收之后才产生，旧回测却把完整「前收→今收」记成策略收益，按可执行的「今开→今收」重算是 **年化 −6.85%、夏普 −1.31、超额 −7.77%**。`multi/out/` 里的东西全是被推翻那次跑的（mtime 00:27~00:36Z，紧接 PASS 日志），修正后的序列**全仓不存在**。所以 `authoritative` 留空、全部序列进 `superseded`，卡目录里也不放副本——防止有人直接取到那条漂亮但错误的曲线。
- **H0027** —— 没有 TEST 产物是**正确状态**：第 1 层即证伪，按协议停止，TEST 从未揭盲。

## 归档时怎么发现 H0009 那类问题的

用序列重算去和 §7 对账，**抓不出 H0009 这种错**——它的年化、回撤、alpha 三个数都和产物对得上，
只有夏普差一点。口径错误发生在产物之外，产物本身是自洽的。

真正抓出来的办法是**比对产物 mtime 与探索日志末条的时间**：产物停在 00:36Z，而日志在 07:52Z
还有一条推翻性的复核结论——中间那 7 小时里没有任何文件被写过，说明推翻方没留下产物，
而目录里剩下的全是被推翻的那一版。

30 张卡都跑过这个检查：除 H0009 外，其余卡的日志末条都在产物之后几分钟内，
或是 08:55Z 那批只重标 `research_role`、不改数字的审计（H0003/H0019/H0021/H0024，
frontmatter 角色已同步）。H0001/H0002 的日志晚 33 小时是因为台账晚于研究本身建卡，属正常。

## 口径不统一（对账时的主要坑）

卡片 §7 的『年化』和『夏普』各卡取法不同，manifest 的 `recomputed` 里都同时给了几种，`discrepancies` 写明该卡用的是哪种：

| 口径 | 用它的卡 |
|---|---|
| 日历年复利 CAGR | H0002 H0016 H0022 H0024 H0028 |
| 252 日复利 CAGR | H0010 H0017 H0019 H0020 H0026 |
| 算术年化（均值×周期数） | H0003 H0005 H0006 H0014 H0015 H0021 H0023 H0025 |
| 夏普分子 | 各卡不一：有的用上面的 CAGR，有的固定用算术年化（H0007 H0019 的 json 里两者混用） |
| 最大回撤 | 复利净值回撤 vs qbt 的『日收益加总钱包』回撤，两者可差一倍（H0010 −50.6% vs −40.2%；H0021 −91.7% vs −75.2%） |
| 超额收益 | H0022/H0024/H0028 是**逐日超额序列复利年化**，不是两条 CAGR 相减（差 1 个百分点以上） |

另有一条实操坑：`quant_research/cn_stock/out*/bench_ew.csv` 比策略序列**长 245 天**（2015-01-05 起 vs 2016-01-04 起），算超额前必须先 `reindex` 对齐。

## 目录归属（同一目录住着多张卡）

| 目录 | 归属 |
|---|---|
| `crypto_perp/` | 根目录 `ret_V*.csv` = H0003；`out/` = H0007；`h0025/` = H0025；`h0029/` = H0029 |
| `futures/` | `ret_*.csv` / `bench_ung_*` = H0006；`strategy_h0013*.py` / `data/panel13/` = H0013；`cot_*` / `data/cot/` = H0023 |
| `us_stock/` | `ret_full/ret_test/bench_spy_full/bench_spy_test` = H0005；`ret_w1/ret_w2/bench_spy` = H0014 |
| `hk_southbound/out/` | 带 `h19_` 前缀 = H0019；不带前缀 = H0017 |
| `fx/` | `ret_main.csv` / `bench_zero.csv` = H0015；H0018 只有代码，产物仅一个 json |
| `quant_research/cn_stock/` | `out/` = H0022；`out_h0024/` = H0024；`out_h0028/` = H0028 |
| `rates/` vs `quant_research/rates/auction_ml_h0027/` | 前者 = H0008，后者 = H0027 |
| `astock_quant/verified/` | `oos_returns.csv` 等 = H0002；`ext_*` / `s0*_*` 属另一条平台审计课题线，**不是** H0002 的产物 |

