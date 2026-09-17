# 信息源全清单

图例：⭐ EP006 作者自用 ｜ 🅠 量化侧 ｜ 🅐 AI 侧
「什么时候用」一列是本 skill 补的检索定位，原清单只到「说明」。

---

## 1 · 网站与论坛

### 网站

| 站点 | 侧 | 说明 | 什么时候用 |
|---|---|---|---|
| ⭐ [Quantocracy](https://quantocracy.com/) | 🅠 | 量化博客聚合站，每日精选栏目 **Quant Mashup**，收录约一百个量化博客的更新，宁缺毋滥 | **默认第一站**。开放式探索、定向验证都从这里起步；RSS 可直接拉 |
| ⭐ [HF Daily Papers](https://huggingface.co/papers) | 🅐 | AI 论文每日精选，带热度排序 | 追方法论层面的新东西（新架构、新训练法），不是找策略 |

### 论坛

| 版块 | 侧 | 看什么 | 什么时候用 |
|---|---|---|---|
| [r/quant](https://www.reddit.com/r/quant/) | 🅠 | 偏机构与职业话题 | 了解机构口径、行业惯例；不是找策略的地方 |
| [r/algotrading](https://www.reddit.com/r/algotrading/) | 🅠 | 散户实操与踩坑 | **找负面证据的最佳来源**：某想法为什么在实盘失效 |
| [r/MachineLearning](https://www.reddit.com/r/MachineLearning/) | 🅐 | AI 研究动态 | 论文的社区评议，比论文本身诚实 |

### YouTube

量化：

| 频道 | 说明 |
|---|---|
| [Dimitri Bianco](https://www.youtube.com/@DimitriBianco) | 量化职业路径与模型风险管理，作者有银行模型验证背景 |
| [Coding Jesus](https://www.youtube.com/@CodingJesus) | 量化开发方向：低延迟、底层实现、求职面试 |

AI：

| 频道 | 说明 |
|---|---|
| [Yannic Kilcher](https://www.youtube.com/@YannicKilcher) | 逐篇精读 AI 论文，更新快 |
| [Two Minute Papers](https://www.youtube.com/@TwoMinutePapers) | 短视频速览研究成果，偏效果演示 |
| [Andrej Karpathy](https://www.youtube.com/@AndrejKarpathy) | 从零实现的深度技术教程 |

> 看英文视频吃力：[Language Reactor](https://www.languagereactor.com/) 双语字幕 + 逐句回听。

---

## 2 · 论文

| 来源 | 侧 | 说明 | 什么时候用 |
|---|---|---|---|
| [arXiv q-fin](https://arxiv.org/list/q-fin/recent) | 🅠 | 量化金融预印本，金融侧新成果首发地 | 找因子、微观结构、组合优化 |
| ⭐ [arXiv cs.LG](https://arxiv.org/list/cs.LG/recent) / [cs.CL](https://arxiv.org/list/cs.CL/recent) | 🅐 | **相当一部分 AI 量化论文发在这里，而不是 q-fin 下** | 找 LLM/时序模型用在交易上的做法。只看 q-fin 会系统性漏掉 |
| ⭐ [Alpha Architect](https://alphaarchitect.com/blog/) | 🅠 | 学术论文的实证解读，关注策略在实盘中站不站得住 | **定向验证的关键一站**：一个想法有没有被独立复现、结论正负 |
| [AQR](https://www.aqr.com/Insights/Research) · [Robeco](https://www.robeco.com/en-int/insights) | 🅠 | 资管机构公开研究与白皮书，免费 | 大类资产、风格因子的长周期证据 |

arXiv 常用分类：`q-fin.TR`（交易与市场微观结构）、`q-fin.PM`（组合管理）、
`q-fin.ST`（统计金融）、`q-fin.CP`（计算金融）、`cs.LG`、`cs.CL`。

---

## 3 · 开源项目

| 项目 | 说明 | 什么时候用 |
|---|---|---|
| ⭐ [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) | LLM 多智能体交易框架，分析师/交易员/风控分角色协作 | 想让 LLM 参与决策链时的参考实现 |
| ⭐ [microsoft/qlib](https://github.com/microsoft/qlib) | 微软的 AI 量化平台，数据处理→训练→回测→组合优化→订单执行，**原生支持 A 股** | A 股多因子研究的默认基础设施；也可只借它的数据层和回测口径 |
| ⭐ [microsoft/RD-Agent](https://github.com/microsoft/RD-Agent) | qlib 的配套项目，把量化研发流程自动化 | 想做因子自动挖掘/自动实验循环时先看它怎么设计的 |

---

## 4 · Newsletter

| Newsletter | 侧 | 说明 |
|---|---|---|
| [Quantocracy 邮件版](https://quantocracy.com/) | 🅠 | 同名网站的每日邮件版 |
| ⭐ [ML & Quant Finance](https://blog.ml-quant.com/) | 🅠🅐 | 机器学习 × 量化的精选链接，Derek Snow，约 1.1 万订阅（原为周更，2026 年起已放缓到月级） |
| [Quantitativo](https://www.quantitativo.com/) | 🅠 | 量化策略与研究想法 |
| [Import AI](https://importai.substack.com/) | 🅐 | AI 研究周报，Jack Clark，重观点而非新闻搬运 |
| ⭐ [The Batch](https://www.deeplearning.ai/the-batch/) | 🅐 | DeepLearning.AI 出品，技术解读扎实，常附数学与代码 |
| ⭐⭐ [AlphaSignal](https://alphasignal.ai/) | 🅐 | AI 工程向周报，GitHub 趋势仓库、新模型与新工具，30 万+ 订阅 |

> 订阅建议：单独建一个邮箱标签和过滤器，让它们自动归到一处，别混进主收件箱。

---

## 5 · AI 工具

| 工具 | 说明 |
|---|---|
| ⭐ [Chatbox AI](https://chatboxai.app/) | 跨平台 AI 客户端，整篇论文/长文丢进去做翻译、摘要和追问（EP006 作者的邀请码 `R7JUXQBJ`） |
| ⭐ [Claude Code](https://claude.com/claude-code) | 终端编程 agent，能读整个代码库。拆开源项目、照论文复现代码 |
| [Codex](https://chatgpt.com/codex) | OpenAI 的编程 agent，CLI / 桌面 / IDE / 网页端 |

---

## 本地已有的配套 skill

| skill | 衔接点 |
|---|---|
| `quant-backtest-protocol` | 检索出的假设 → 三段切分 + 四层证伪的验收 |
| `ema-trend-reversal-research` | 具体到 EMA 趋势策略的多品种研究框架 |
| `web-access` | 所有联网抓取的执行规则（CDP / 登录态 / 反爬） |
