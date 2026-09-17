---
name: ai-quant-sources
description: AI 量化的一手信息源地图与检索流程——Quantocracy / arXiv(q-fin·cs.LG·cs.CL) / Alpha Architect / HuggingFace Daily Papers / qlib·RD-Agent·TradingAgents / ML-Quant·AlphaSignal 等，配可直接跑的抓取脚本。任何要探索量化策略方向、找新的因子或策略灵感、调研某个想法有没有人做过或做砸过、追踪 AI×量化最新进展、找可复现的开源项目或论文、问"最近量化圈有什么新东西"时使用；也用于在动手写策略前先做一轮"别人踩过的坑"检索。触发词：找策略、策略灵感、量化调研、有什么新思路、因子挖掘方向、论文复现、开源量化框架、最新进展、信息源、Quantocracy、arXiv、qlib、TradingAgents。找到候选后交接给 quant-backtest-protocol 做验收。
---

# AI 量化信息源 · 从「拍脑袋想策略」切换到「从源头捞策略」

清单出处：`frank-quant/ai-trading-videos` 的 EP006《用 AI 做量化交易，一定要开眼看世界》。
本 skill 把那份清单变成**可执行的检索流程**：源在哪、怎么拉、拉回来怎么筛、筛完交给谁。

**默认立场：任何策略想法在写第一行回测代码之前，先跑一轮源检索。**
理由很简单——公开可得的策略想法，绝大多数已经被人做过并公开写过成败。
自己从零想一个，通常只是重新发明一个已知会失效的东西，而且不知道它为什么失效。

---

## 铁律

1. **先检索，后建模。**用户说"我想试试 XX 策略"时，第一步不是写代码，是去
   Quantocracy + arXiv + Alpha Architect 搜这个想法。找到别人的结论再决定做不做。
2. **一手来源优先。**论文读 arXiv 原文，不读转述；开源项目读代码，不读 README 的宣传语；
   实证结论读 Alpha Architect 的复现，不读社媒截图。二手信息只用来**定位**一手来源。
3. **区分 🅠 量化侧和 🅐 AI 侧。**很大一部分 AI 量化论文发在 cs.LG / cs.CL 而不是 q-fin，
   只盯 q-fin 会系统性漏掉方法论层面的新东西。
4. **检索结果不等于策略。**任何从源里捞到的想法，只是一个**待证伪的假设**，
   必须走 `quant-backtest-protocol` 的三段切分 + 四层证伪，不许直接采信论文里的夏普。
5. **论文的回测默认不可信。**已发表 ≠ 样本外有效。看论文先看四件事：
   数据区间到哪年（有没有覆盖它发表后的时段）、成本假设、宇宙怎么选的、有没有开源代码。
   四件事缺两件以上的，当灵感看，不当证据看。

---

## 五个模块的分工

| 模块 | 回答的问题 | 首选 |
|---|---|---|
| 网站/论坛 | 「圈子里最近在聊什么」 | **Quantocracy**（每日 Quant Mashup，约百个量化博客的精选） |
| 论文 | 「这个想法的原始出处和实证结论」 | arXiv q-fin + cs.LG/cs.CL；**Alpha Architect** 看实盘站不站得住 |
| 开源项目 | 「能 clone 下来拆开看的实现」 | **qlib**（A 股原生）/ RD-Agent / TradingAgents |
| Newsletter | 「替我把上面三块读完」 | ML-Quant（🅠🅐）/ AlphaSignal（🅐）/ The Batch（🅐） |
| AI 工具 | 「把这些读下去、跑起来」 | Claude Code 拆代码复现；Chatbox 读长论文 |

完整清单（含每条的适用场景与 ⭐ 标记）→ `references/sources.md`

---

## 三条标准路线

### 路线 A · 「我想找新的策略方向」（开放式探索）

```bash
python3 ~/.workbuddy/skills/ai-quant-sources/scripts/scan.py --days 14
```

一次拉全：Quantocracy 每日精选 + arXiv q-fin/cs.LG 近期 + Alpha Architect + HF Daily Papers。
输出标题 + 链接 + 日期，**先只读标题做粗筛**，选出 5~10 条再展开读正文。

粗筛的三个问题（任一为否就丢弃）：
- 它的**数据机理与可拓展性**：该策略原生需要什么资产类别、时间颗粒度（Tick/15m/1h/1d）与特定维度？我们能否通过公开 API（CCXT / Futu / yfinance / Akshare / 链上 / 研报源）**主动获取并按需拓展该数据集**？严禁以本地已有缓存为上限设限，严禁因暂无现成数据而轻率否定高价值假设，更严禁把策略强行削足适履塞进不匹配的本地缓存里。
- 它的**换手率**在我的成本假设下还剩利润吗？
- 它是**结构性理由**（风险溢价/微观结构/行为偏差）还是纯数据挖掘？后者优先级低。

### 路线 B · 「这个想法有没有人做过 / 做砸过」（定向验证）

按顺序，命中即停：
1. `site:quantocracy.com <关键词>` —— 量化博客圈有没有写过
2. arXiv 全文检索 `<关键词> + (trading|portfolio|factor)`
3. `site:alphaarchitect.com <关键词>` —— 有没有独立复现，结论是正是负
4. `r/algotrading` 搜同名策略 —— 散户实操踩坑，负面信息密度最高
5. GitHub 搜实现 —— 有 star 的实现通常伴随 issue 区的失效讨论

**重点是找负面证据。**只找到吹的、找不到骂的，说明检索还没做完。

### 路线 C · 「复现一篇论文 / 拆一个开源项目」

1. arXiv 拿原文 PDF；有 GitHub 就先 clone 代码，代码是比正文更诚实的一手来源
2. 用 Claude Code 通读仓库，重点看：数据切分在哪、成本在哪、有没有用到未来信息
3. 复现产出的策略，直接进 `quant-backtest-protocol` 的流程，**不复用论文的回测口径**

---

## 抓取方式

联网一律走 `web-access` skill 的规则。已验证可用的端点和命令见
`references/fetch-recipes.md`，要点：

- **Quantocracy / Alpha Architect / ML-Quant / Quantitativo**：RSS 直接 curl（Quantocracy 的 UA 必须是裸 `Mozilla/5.0`，否则 400）
- **arXiv**：官方 API（`export.arxiv.org/api/query`），支持按分类和日期排序
- **HuggingFace Daily Papers**：`huggingface.co/api/daily_papers`，返回 JSON 带热度
- **Reddit**：`www.reddit.com` 的 `.json` 一律 403；`old.reddit.com/r/<sub>/top.json` 配自定义 UA 时好时坏，失败就走 CDP
- **The Batch / AlphaSignal / Import AI**：无稳定 RSS，走 WebFetch 或 CDP
- **长论文**：`r.jina.ai/<url>` 转 Markdown 再读，省 token

---

## 交接

检索的终点不是"找到了几篇论文"，而是**一条写得出回测配置与数据拉取需求的假设**：

> 标的池与频率需求 = ？（需主动拉取哪些资产、15m/1h/1d？是否需拓展更大样本池测试泛化） ｜ 信号 = ？（数据源、计算方式）｜ 持有期 = ？ ｜ 成本假设 = ？
> ｜ 来源证据 = ？（链接）｜ 已知的失效条件 = ？

凑齐这六项，由 AI / 研究员主导发起按需数据拉取并调 `quant-backtest-protocol` 开跑。凑不齐的，回去继续检索。

---

*信息源清单归 EP006 原作者所有，仅用于技术学习与研究，不构成投资建议。*
