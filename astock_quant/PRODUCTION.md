# A股小微盘 ARM1 正式数据管线

## 运行模型

生产服务不再加载十年研究面板，也不重跑历史回测。ARM1 持久化最近 400 个交易日的：

- 复权收盘价 `close`、复权开盘价 `open`
- 不复权收盘价 `close_raw`、不复权开盘价 `open_raw`
- 估算成交额 `amount`
- 上一期持仓、调仓相位（含 `rebalance_frequency` 字段）和通知去重状态

每天收盘后从腾讯 `fqkline` 拉取最近 8 根日线（周一 20 根）；长时间停更时按缓存缺口扩窗，
上限 400 根，staging 按抓取根数隔离，避免复用旧的小窗口断点。合并后使用上证指数的真实
交易日序列校验连续性，缺口任意一天都拒绝发布，再处理晚到和修订。
只计算 `liqsize20 + rev5 + ivol60`，调仓周期为 20 个交易日（`REBALANCE_FREQUENCY`）；
旧的 10 日状态会在它既有的下一调仓日一次性迁移到 20 日。复权统一走
`aq.adjust.build_scoring_panels`（与研究/seed 管线同一入口）；近期公司行动解不出复权的
个股，相关因子在事件窗口内被标无效排除，不退回 raw 收益。本期收益优先用 T+1 开盘价，
缺 open 时给出 `entry_basis_degraded` 降级标记。

行情覆盖率低于上一交易日的 95% 时拒绝发布，保留上一份有效信号并告警。五个 Parquet
先写入新 generation，全部成功后才原子切换 `current.json`；只保留最近两代用于故障恢复。

## 首次灌种（推荐）

本地已有完整研究面板时，先生成约 33MB 的滚动种子：

```bash
.venv/bin/python astock_quant/scripts/bootstrap_live_cache.py \
  --out-dir runtime/ashare-smallcap/market
```

将整个目录传到 ARM1 项目目录：

```bash
rsync -az runtime/ashare-smallcap/ arm1:/home/ubuntu/code/misc/runtime/ashare-smallcap/
```

如果不传种子，服务也会从已提交的 `meta.csv` 自动抓取最近 400 根日线完成初始化；
抓取结果逐股写入 `/data/market/staging/`，容器重启后会断点续跑，但首次完成时间明显更长。

## 部署

```bash
cd /home/ubuntu/code/misc
docker compose up -d --build --remove-orphans
```

宿主机 `./runtime/ashare-smallcap` 挂载为容器 `/data`，重新 build、删除容器和普通
`docker compose down` 都不会删除行情缓存。不要执行 `docker compose down -v` 后再手工清理
`runtime/ashare-smallcap`。

共享卷首次为空时，[run.sh](../docker/ashare-smallcap-quant/run.sh) 会从镜像的
`/app/bundle_deliverables/` 初始化 `smallcap_strategy.json`，随后启动增量服务。

## 验证

```bash
docker compose logs -f ashare-smallcap-quant
curl -fsS http://localhost:3010/api/smallcap-strategy
```

API 返回的 `data.runtime` 应满足：

- `mode = incremental`
- `status = healthy`
- `validation.coverage >= 0.95`
- `latest_trading_date` 等于腾讯上证指数接口的最新交易日

服务每月批量扫描一次沪深代码空间，发现新上市股票后自动回补滚动历史。新股仍需满足
上市 250 个交易日才会进入可投资池。
