# monitor/ — EMA 趋势反手策略统一监控

一个入口、一份配置、一套 daemon 实现，统一管理所有品种的 EMA 趋势反手策略实时监控。

## 为什么有这个目录

之前监控代码散落在至少两处：

- `eth_sol_bnb_15m/monitor/monitor_daemon.py` — 加密 4 币种通用版（ETH/SOL/BNB/BTC），靠 `start_all.sh` 拉 4 个进程
- `scripts/xag_monitor_daemon.py` + `scripts/xag_monitor.py` — XAG/INTC/CL/MSFT/SOXL/DRAM/SKHYNIX/XAU 等 TradFi perp

两份代码有大量重复逻辑（指标计算、K 线对齐、通知、状态格式化），且各自维护一份"最优配置"硬编码常量；要加一个品种或改一个参数要改三处。本目录把它们合并为一份，配置抽到 `strategies.json`，调用入口只有一个 `monitor.py`。

旧的 `eth_sol_bnb_15m/monitor/`、`scripts/xag_monitor_daemon.py` **保留在原位**（git 历史不丢），但已标记为 deprecated，实际只用本目录。

## 目录结构

```
monitor/
├── monitor.py            # ★ 唯一 CLI 入口 (list/start/stop/restart/status/logs/show/run)
├── strategies.json        # ★ 唯一配置源 (所有品种的 EMA/cb/bp/tp 参数都在这里)
├── telegram_config.json   # telegram bot 配置 (统一一份, 不必每品种一份)
├── daemon.py             # 单品种 daemon 主循环 (被 monitor.py 作为子进程拉起)
├── strategy.py           # 策略纯函数: 指标/K线形态/infer_position/snapshot/scenarios
├── datasources/
│   ├── __init__.py       # adapter 注册表
│   ├── ccxt_perp.py      # Binance USDT-M 永续
│   └── yfinance.py       # A股/美股/贵金属现货 (扩展用)
├── notifiers/
│   ├── __init__.py       # notify_all 统一发送
│   ├── macos.py          # macOS 通知中心
│   └── telegram.py       # Telegram Bot
├── caches/<name>/        # 每品种独立目录: daemon.pid / state.json / monitor.log / stdout.log
└── README.md
```

## 使用

```bash
cd /Users/gongzhao/code/misc/monitor

# 1. 看所有已配置的品种
python monitor.py list

# 2. 启动 daemon
python monitor.py start ETH,SOL                    # 几个
python monitor.py start --all                      # 全部 (12 个)
python monitor.py start ETH --foreground            # 前台跑 (调试用)
python monitor.py start ETH --foreground --dry-run  # 只跑一轮就退出

# 3. 看运行状态 (含 daemon 进程 + 各品种持仓/价格/浮盈)
python monitor.py status

# 4. 看某个品种最近日志或 state
python monitor.py logs ETH -n 50
python monitor.py show ETH

# 5. 停 / 重启
python monitor.py stop ETH
python monitor.py stop --all
python monitor.py restart ETH,SOL

# 6. 临时覆盖参数前台跑 (不改 strategies.json, 用于调试新参数)
python monitor.py run ETH --ema 2000 --bp 0.005
```

## 加一个新通知通道

每个通道是一个 `notifiers/<name>.py`，实现 `notify(title, message, important=True, **kw) -> bool` 和 `is_configured() -> bool` 两个函数即可。在 `notifiers/__init__.py` 的 `REGISTRY` 注册新名字，daemon 自动同时推送到这个通道，不改 daemon 代码。

已内置：

| 通道 | 配置 | 适合场景 |
|---|---|---|
| `macos` | 无 | 本机桌面弹窗 + 声音（仅 macOS） |
| `telegram` | `monitor/telegram_config.json`（一份统一用） | 国外网络下推送 |
| `wechat_work` | `monitor/wechat_webhook.json` **或** 环境变量 `MONITOR_WECHAT_WEBHOOK` 指向同结构 json | **国内主力**：不需要 VPN，企业微信群机器人 |

### 配置企业微信群机器人（推荐国内主推送）

1. 企业微信群里点群机器人 -> 添加 -> 拿到一个 webhook URL，形如：
   `https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxxxxxxx`
2. 写入 `monitor/wechat_webhook.json`：
   ```json
   {"webhook_url": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxxxxxxx"}
   ```
3. 验证：
   ```bash
   python monitor.py notify "测试" "hello"
   ```
   输出里 `wechat_work: ✓` 表示配置生效。
4. 后续 daemon 启动时日志会显示 `通知: macOS=on, Telegram=on, 企业微信=on`，反手 / 止盈信号同时发到这三个通道。

企业微信群机器人限频：每分钟 20 条 → 同一群。监控信号一天通常几次反手，远低于限频。

### 手动测试通知

```bash
python monitor.py notify "测试" "hello from monitor"   # 发到所有已配置通道
python monitor.py notify "测试" "hello" --quiet         # 非重要样式 (不闪红)
```

只需在 `strategies.json` 的 `strategies` 数组追加一条：

```json
{
  "name": "AAPL",
  "symbol": "AAPL",
  "display_name": "Apple",
  "timeframe": "15m",
  "ema_span": 200,
  "confirm_bars": 5,
  "cb_float": 0,
  "breakout_pct": 0.004,
  "data_source": "yfinance",
  "tp_enabled": false,
  "tp_type": "none",
  "tp_params": "",
  "rsi_over": 80, "rsi_under": 20, "rsi_span": 14, "atr_span": 14,
  "part_ratio": 0.15, "cool_bars": 20, "tp_max_times": -1,
  "history_bars": 1500, "priority": 99,
  "sample_note": "新增样本", "source": "..."
}
```

然后：

```bash
python monitor.py list          # 验证加进去了
python monitor.py start AAPL   # 启动 (自动建 caches/AAPL/)
python monitor.py logs AAPL     # 看日志
```

如果新品种需要新数据源（如a股 tushare），在 `datasources/` 下加一个 `tushare.py` 实现 `fetch_recent(symbol, timeframe, limit, **kw)`，在 `datasources/__init__.py` 的 `REGISTRY` 注册新名字，配置里写 `"data_source": "tushare"` 即可。核心 daemon 与 strategy 完全不用改。

## 加一种新的止盈形态

在 `strategy.py` 的 `_compute_top_signals` 函数里加一个 `elif tp_type == "<你的形态名>":` 分支，设置 `top_long`/`top_short` 两个布尔数组（记得带 `at_high`/`at_low` 过滤），并在 `_tp_metric_label` 加一行返回显示文案。配置里写 `"tp_type": "<你的形态名>"` 即可。

已实现的 9 种（与 `scripts/xag_monitor.py` 研究口径一致）：

| tp_type | 描述 | 备注 |
|---|---|---|
| `rsi` | RSI 超买/超卖 | 历史基线 |
| `long_upper_wick` | A5 长上影线 | `tp_params: {"n_atr": 1.5}` |
| `bearish_engulfing` | A2 看跌吞没 | |
| `dark_cloud_cover` | A4 乌云盖顶 | XAG 基线最优 |
| `evening_star` | A3 黄昏之星 | |
| `shooting_star` | A1 流星线 | `tp_params: {"wick_body_ratio": 2.0}` |
| `outside_bar_reversal` | D2 外包日反转 | 杠杆ETF专属 |
| `failed_breakout` | D1 假突破 | `tp_params: {"n_brk": 20}` |
| `none` | 不止盈（纯反手） | step6.5 验证趋势策略不该早止盈 |

## 环境变量

| 变量 | 默认 | 作用 |
|---|---|---|
| `MONITOR_PY` | 当前解释器 | daemon 子进程用哪个 python |
| `MONITOR_TELEGRAM_CONFIG` | `monitor/telegram_config.json` | telegram 配置文件路径 |
| `MONITOR_DRY_RUN` | - | 设为 1 时 daemon 跑完首轮快照即退出 |

## Daemon 进程模型

一品种一进程：`monitor.py start --all` 拉起 N 个独立的 daemon.py 子进程，每个进程通过 `caches/<name>/daemon.pid` 记录 PID。一个崩了不连累别的；出错从日志 `caches/<name>/monitor.log` 看。信号检测对齐 K 线收盘后 5 秒，主循环无变化时每 5 根写一次心跳日志。

## 配置迁移

旧目录的 telegram_config 已迁移到 `monitor/telegram_config.json`（一份统一用作所有品种）。其他 cache 目录保留在原位（不影响本目录运行）。如要保留旧 daemon 在跑也可，但会和新 daemon 重复推送通知，建议统一切到本目录。
