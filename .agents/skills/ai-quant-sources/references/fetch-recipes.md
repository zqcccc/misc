# 抓取配方

联网操作遵循 `web-access` skill 的规则。下面的端点均在 2026-09-02 实测过状态码，
标注了当时的结果——当作「可能有效的提示」，失败就按 web-access 的通用流程回退到 CDP。

## 状态速查

| 源 | 方式 | 实测 |
|---|---|---|
| Quantocracy | RSS `https://quantocracy.com/feed/` | ✅ 200，条目即每日 Quant Mashup。**UA 必须是裸 `Mozilla/5.0`**，带括号说明或 `curl/*` 一律 400 |
| Quantocracy 分类 feed | `/category/quant-mashup/feed/` | ❌ 404，别用，用主 feed |
| arXiv | 官方 API `http://export.arxiv.org/api/query` | ✅ 200 |
| HF Daily Papers | `https://huggingface.co/api/daily_papers?limit=N` | ✅ 200 JSON |
| Alpha Architect | RSS `https://alphaarchitect.com/feed/` | ✅ 200 |
| ML-Quant | RSS `https://blog.ml-quant.com/feed` | ✅ 200（但更新已放缓到月级，短窗口扫描常为空，正常） |
| Quantitativo | RSS `https://www.quantitativo.com/feed` | ✅ 200 |
| Reddit `www.` 的 `.json` | — | ❌ 403 |
| Reddit `.rss` | — | ❌ 403 |
| Reddit `old.reddit.com/*.json` | curl + 自定义 UA | ⚠️ 时好时坏：UA 必须是带说明的自定义串（裸 `Mozilla/5.0` 被 403），且经常返回 **200 + 反爬过渡页**而不是 JSON。不稳定，优先走 CDP |
| The Batch | `deeplearning.ai/the-batch/feed/` | ❌ 404，走 WebFetch/CDP |
| Import AI | substack feed | ❌ 连接失败，走 WebFetch/CDP |
| AlphaSignal | 无公开 feed | 走 WebFetch/CDP |

UA 是这批站点最常见的失败原因，且两边要求相反：quantocracy 只认裸 `Mozilla/5.0`，
old.reddit 恰好相反、只认带说明的自定义 UA。其余源两种都能过。

---

## 具体命令

### Quantocracy 每日精选

```bash
curl -sL -A "Mozilla/5.0" "https://quantocracy.com/feed/"
```
每个 item 是一期 Mashup，正文（`content:encoded`）里是当天几十条外链，
外链才是真正要读的东西——从正文里抽 `<a href>` 再筛。

### arXiv

```bash
curl -sL "http://export.arxiv.org/api/query?search_query=cat:q-fin.TR&start=0&max_results=30&sortBy=submittedDate&sortOrder=descending"
```
- 多分类：`search_query=cat:q-fin.TR+OR+cat:q-fin.PM`
- 关键词 + 分类：`search_query=cat:cs.LG+AND+all:%22trading%22`
- 全文找某个想法有没有人做过：`search_query=all:%22<关键词>%22`
- 拿到 PDF 后走 `r.jina.ai/<arxiv-abs-url>` 转 Markdown 再读，省 token

### HuggingFace Daily Papers

```bash
curl -sL "https://huggingface.co/api/daily_papers?limit=30"
```
JSON 里每条有 `paper.title` / `paper.summary` / `paper.upvotes` / `paper.id`（= arXiv id）。

### Alpha Architect / ML-Quant / Quantitativo

```bash
curl -sL -A "Mozilla/5.0" "https://alphaarchitect.com/feed/"
curl -sL "https://blog.ml-quant.com/feed"
curl -sL "https://www.quantitativo.com/feed"
```

### Reddit

```bash
curl -sL -A "quant-source-scan/1.0 (research script)" \
  "https://old.reddit.com/r/algotrading/top.json?t=week&limit=25"
curl -sL -A "quant-source-scan/1.0 (research script)" \
  "https://old.reddit.com/r/algotrading/search.json?q=<关键词>&restrict_sr=1&sort=top&t=all&limit=25"
```
两个坑：`www.reddit.com` 一律 403，必须用 `old.reddit.com`；UA 要带说明，裸 `Mozilla/5.0` 也是 403。
即便都对了，**Reddit 也常返回 200 + 一张 "Welcome to Reddit" 过渡页**而不是 JSON——
这时脚本层没法绕，直接走 web-access 的 CDP 模式打开 subreddit 页面读。
scan.py 检测到非 JSON 会明确报这一条，不要在它上面反复重试。

### GitHub 找实现

```bash
curl -s "https://api.github.com/search/repositories?q=<关键词>+language:python&sort=stars&order=desc&per_page=15"
curl -s "https://api.github.com/repos/<owner>/<repo>/issues?state=all&labels=bug&per_page=30"
```
第二条是**找失效证据**用的：issue 区常有"跑不出论文里的结果"的讨论。

### 无 feed 的（The Batch / AlphaSignal / Import AI）

WebFetch 拉页面并让小模型提要点，或者 `r.jina.ai/<url>` 转 Markdown。
需要登录态的（订阅制内容）走 web-access 的 CDP 模式。

---

## 一次性全量扫描

```bash
python3 ~/.workbuddy/skills/ai-quant-sources/scripts/scan.py --days 14
```

参数：
- `--days N`：只保留 N 天内的条目（默认 14）
- `--sources quantocracy,arxiv,hf,alphaarchitect,mlquant,quantitativo,reddit`：只扫指定源
- `--arxiv-cats q-fin.TR,q-fin.PM,cs.LG`：覆盖默认分类
- `--query "<关键词>"`：定向模式，标题/摘要含关键词才输出，同时对 arXiv 走全文检索
- `--limit N`：每个源最多输出多少条（默认 20）
- `--json`：输出 JSON 而非表格

脚本只用 Python 标准库，无依赖；单个源失败不影响其他源，会在末尾列出失败原因。
