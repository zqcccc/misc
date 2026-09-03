# quant_research —— 多 agent 共享的量化探索台账

解决一个具体问题：**多个 agent 反复探索同一个已经死掉的方向。**

项目里原本有两个 skill —— `ai-quant-sources`（去哪找想法）和 `quant-backtest-protocol`（怎么证伪）——
中间缺的是「谁在探什么、什么已经探死了」的共享记忆。本目录就是这层。

## 结构

```
quant_research/
├── PROMPT.md        ★ 母提示词，开放式、不限市场，任何 agent 直接照它执行
├── KNOWLEDGE.md     ★ 已固化结论（含负面结论），开工第一件事就是读完
├── REGISTRY.md      索引表，由 ./qr index 自动生成，不要手改
├── qr               台账 CLI（覆盖盘点 / 查重 / 占坑 / 记录 / 裁决）
├── hypotheses/      一个假设一张卡，从占坑到裁决的全过程都在卡里
├── markets/         市场年鉴：每个市场的成本、可交易性、数据陷阱、基准、已知的坑
│                    进新市场先照 _TEMPLATE.md 建一份，这是入场券
├── locks/           占坑锁（目录锁，mkdir 原子操作，天然防并发撞车）
└── templates/       假设卡模板
```

## 给 agent 的一句话启动语

```
读 quant_research/PROMPT.md 并严格照它执行。本轮预算：<N 个假设>；我的 agent 名：<name>
```

**不写方向、不写市场就是完全开放**——agent 会先跑 `./qr coverage` 看地图上哪里还是白的，
按硬性配额撒出至少 12 个跨市场、跨颗粒度、跨机理族的候选，打分后才收敛。
要限定范围再补 `方向：<...>` / `市场：<...>`。多个 agent 可同时跑。

## 常用命令

```bash
cd quant_research
./qr coverage                               # 覆盖盘点：哪些市场/机理族还是零覆盖
./qr search 反转 reversal 短期反转          # 去重闸：有命中退出码 1
./qr claim "一句话假设" --market cn_stock --freq d1 --family reversal --tags a,b --agent alice
./qr note H0003 "跑完因果闸，max diff = 0"
./qr verdict H0003 FAIL "毛 alpha 3.79% 打不过 0.35% 双边成本，净 alpha 归零"
./qr list running
./qr stale 6                                # 找 6h 没更新的僵尸占坑
./qr index                                  # 重建 REGISTRY.md
```

## 并发规则（多 agent 的全部约定就这四条）

1. **先盘覆盖、再查重、后占坑**：`qr search` 无命中，或读完命中卡确认机理/口径不同，才可 `qr claim`。
2. **一次占一个坑**，做完再占下一个，别批量圈地。
3. **只写自己的 ID**：别人活跃占坑（`locks/<ID>/owner` 存在）的卡片一律只读。
4. **僵尸接管**：`qr stale` 列出的 >6h 无更新占坑可以接管，接管前先 `qr note` 留痕。

ID 分配靠 `mkdir` 的原子性，两个 agent 同时 claim 也不会拿到同一个号；
`locks/<ID>/` 目录永不删除（它是号段登记），只删里面的 `owner` 文件（它才是活跃锁）。

## 台账位置：跨 worktree 单例

`qr` 会把台账根目录解析到**主检出**的 `quant_research/`（通过 `git --git-common-dir` 推出），
所以在任何 worktree 里跑 `./qr` 读写的都是同一份台账，不会因为分支不同而各记各的。
`./qr home` 打印当前根目录；`QR_HOME=<路径>` 可覆盖。

> 主检出还没有这个目录时（比如本分支尚未合并），`qr` 会退回用脚本自身所在目录，
> 合并到主干后自动切换到共享单例。
