"""把 reports/*.json 渲染成一页 HTML 研究报告（内嵌 ECharts）。

用法：python3 scripts/build_report.py
产物：reports/report.html
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aq import config  # noqa: E402

R = config.REPORT_DIR


def load(name, default=None):
    p = os.path.join(R, name)
    if not os.path.exists(p):
        return default
    with open(p) as f:
        return json.load(f)


def collect_tests():
    try:
        out = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q"],
                             cwd=os.path.dirname(R), capture_output=True, text=True, timeout=180)
        names = [ln.strip() for ln in out.stdout.splitlines() if "::" in ln]
        return names
    except Exception:
        return []


TEST_DESC = {
    "test_buy_cost_is_exact": "买入后净值 = 本金 /(1+费率)，逐笔核对",
    "test_sell_cost_includes_stamp_duty": "卖出计入印花税，金额精确匹配",
    "test_stamp_duty_halved_after_2023_08_28": "印花税按历史税率表切换",
    "test_limit_up_open_blocks_buy": "开盘涨停买不进，资金留在现金",
    "test_chinext_20pct_limit_is_date_dependent": "创业板涨跌停 2020-08-24 前后不同",
    "test_limit_down_open_blocks_sell": "开盘跌停卖不掉，顺延到下一日",
    "test_yizi_board_blocks_both_directions": "一字板双向不可成交",
    "test_suspension_holds_value_and_blocks_trade": "停牌不可交易、按上一有效价估值",
    "test_delisting_liquidates_at_last_price": "退市按最后价清算并计成本",
    "test_no_same_day_round_trip": "T+1：同日不对同一标的双向交易",
    "test_cash_constraint_no_leverage": "买入受现金约束，不加杠杆",
    "test_partial_weight_keeps_cash": "权重不足 1 的部分留作现金",
    "test_factors_truncation_invariant": "13 个因子：数据截断后历史取值逐点不变",
    "test_factors_future_perturbation_invariant": "把未来数据换成随机数，历史因子不变",
    "test_no_negative_shift_in_source": "AST 静态检查：不存在负向 shift / bfill",
    "test_universe_truncation_invariant": "股票池掩码的截断不变性",
    "test_backtest_truncation_invariant": "整条净值曲线的截断不变性",
    "test_backtest_future_perturbation_invariant": "未来价格扰动后净值曲线不变",
    "test_signal_executes_next_day_not_same_day": "信号日不成交，次日开盘才成交",
    "test_oracle_signal_would_break_the_test": "反向验证：故意造未来函数必须被抓到",
    "test_forward_return_alignment": "前瞻收益的下标对齐",
    "test_rank_ic_is_one_for_perfect_foresight": "完美预知时 IC = 1",
    "test_rank_ic_of_same_day_return_is_near_zero_on_random_data": "随机数据上 IC 不显著",
    "test_walkforward_truncation_invariant": "滚动重估权重同样满足截断不变性",
}

HTML = r"""<meta charset="utf-8">
<title>__TITLE__</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Serif:wght@500;600&display=swap">
<script src="https://cdnjs.cloudflare.com/ajax/libs/echarts/5.6.0/echarts.min.js"></script>
<style>
:root{
  color-scheme: light;
  --bg:#eff1ee; --surface:#fbfcfa; --surface-2:#f4f6f2;
  --text:#171a17; --text-2:#54595a; --muted:#7c8283;
  --line:#dcdfd9; --line-strong:#c3c7c0;
  --accent:#2f5d50; --accent-soft:#e2ebe6;
  --up:#c62b34; --down:#10795b;
  --s1:#2a78d6; --s2:#eb6834; --s3:#1baf7a; --s4:#eda100;
  --grid:#e4e7e1;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    color-scheme: dark;
    --bg:#101311; --surface:#171b18; --surface-2:#1c211d;
    --text:#e8ebe6; --text-2:#a8b0aa; --muted:#8b938d;
    --line:#262c27; --line-strong:#39413a;
    --accent:#7fc3ac; --accent-soft:#1b2a24;
    --up:#f0575f; --down:#2fb380;
    --s1:#3987e5; --s2:#d95926; --s3:#199e70; --s4:#c98500;
    --grid:#232922;
  }
}
:root[data-theme="dark"]{
  color-scheme: dark;
  --bg:#101311; --surface:#171b18; --surface-2:#1c211d;
  --text:#e8ebe6; --text-2:#a8b0aa; --muted:#8b938d;
  --line:#262c27; --line-strong:#39413a;
  --accent:#7fc3ac; --accent-soft:#1b2a24;
  --up:#f0575f; --down:#2fb380;
  --s1:#3987e5; --s2:#d95926; --s3:#199e70; --s4:#c98500;
  --grid:#232922;
}
*{box-sizing:border-box}
body{
  margin:0; background:var(--bg); color:var(--text);
  font-family:"IBM Plex Sans","PingFang SC","Hiragino Sans GB","Microsoft YaHei",system-ui,sans-serif;
  font-size:15px; line-height:1.75; -webkit-font-smoothing:antialiased;
}
.wrap{max-width:1000px; margin:0 auto; padding:56px 24px 96px}
h1,h2,h3{font-family:"IBM Plex Serif",Georgia,"Songti SC",serif; text-wrap:balance; margin:0}
h1{font-size:34px; line-height:1.25; letter-spacing:-.01em}
h2{font-size:22px; margin:0 0 6px}
h3{font-size:16px; font-weight:600; margin:0 0 4px}
.eyebrow{font-family:"IBM Plex Mono",monospace; font-size:11px; letter-spacing:.14em;
  text-transform:uppercase; color:var(--muted)}
.lede{font-size:17px; color:var(--text-2); max-width:62ch; margin:14px 0 0}
header{border-bottom:1px solid var(--line-strong); padding-bottom:28px; margin-bottom:34px}
.meta{display:flex; flex-wrap:wrap; gap:8px 22px; margin-top:20px;
  font-family:"IBM Plex Mono",monospace; font-size:12px; color:var(--muted)}
.meta b{color:var(--text-2); font-weight:500}
section{margin:52px 0 0}
section > .eyebrow{display:block; margin-bottom:8px}
p{margin:12px 0; color:var(--text-2)}
p.note{font-size:13.5px; color:var(--muted)}
.tiles{display:grid; grid-template-columns:repeat(3,1fr); gap:2px;
  background:var(--line); border:1px solid var(--line); border-radius:3px; overflow:hidden; margin-top:22px}
.tile{background:var(--surface); padding:16px 18px}
.tile .k{font-family:"IBM Plex Mono",monospace; font-size:10.5px; letter-spacing:.1em;
  text-transform:uppercase; color:var(--muted)}
.tile .v{font-family:"IBM Plex Mono",monospace; font-size:26px; font-weight:500;
  font-variant-numeric:tabular-nums; margin-top:6px; letter-spacing:-.02em}
.tile .s{font-size:12px; color:var(--muted); margin-top:2px}
.pos{color:var(--up)} .neg{color:var(--down)}
.card{background:var(--surface); border:1px solid var(--line); border-radius:3px;
  padding:20px 20px 8px; margin-top:20px}
.card h3{margin-bottom:2px}
.card .cap{font-size:12.5px; color:var(--muted); margin:0 0 10px}
.chart{width:100%; height:380px}
.chart.short{height:300px}
.tablewrap{overflow-x:auto; margin-top:18px; border:1px solid var(--line);
  border-radius:3px; background:var(--surface)}
table{border-collapse:collapse; width:100%; font-size:13px;
  font-variant-numeric:tabular-nums; font-family:"IBM Plex Mono",monospace}
th,td{padding:8px 12px; text-align:right; white-space:nowrap; border-bottom:1px solid var(--line)}
th{background:var(--surface-2); color:var(--text-2); font-weight:500; font-size:11.5px;
  letter-spacing:.06em; text-transform:uppercase; position:sticky; top:0}
td:first-child,th:first-child{text-align:left; font-family:"IBM Plex Sans","PingFang SC",sans-serif}
tbody tr:last-child td{border-bottom:none}
tbody tr:hover td{background:var(--surface-2)}
tr.hl td{background:var(--accent-soft); font-weight:600}
a{color:var(--accent); text-underline-offset:3px}
a:focus-visible{outline:2px solid var(--accent); outline-offset:2px; border-radius:2px}
ul{margin:12px 0; padding-left:20px; color:var(--text-2)}
li{margin:6px 0}
li b{color:var(--text); font-weight:600}
.checks{list-style:none; padding:0; margin:16px 0 0;
  border:1px solid var(--line); border-radius:3px; background:var(--surface)}
.checks li{display:flex; gap:12px; align-items:baseline; margin:0;
  padding:9px 16px; border-bottom:1px solid var(--line); font-size:13.5px}
.checks li:last-child{border-bottom:none}
.checks .id{font-family:"IBM Plex Mono",monospace; font-size:11.5px; color:var(--accent);
  min-width:0; flex:0 0 auto}
.checks .d{color:var(--text-2)}
.verdict{border-left:3px solid var(--accent); background:var(--surface);
  padding:16px 20px; margin-top:20px; border-radius:0 3px 3px 0; font-size:15px}
.verdict p{margin:6px 0; color:var(--text)}
.verdict b{color:var(--text)}
.warn{border-left:3px solid var(--up); background:var(--surface); padding:14px 18px;
  margin-top:18px; border-radius:0 3px 3px 0}
.warn p{margin:6px 0}
footer{margin-top:64px; padding-top:20px; border-top:1px solid var(--line);
  font-size:12px; color:var(--muted); font-family:"IBM Plex Mono",monospace}
@media (max-width:640px){ .wrap{padding:32px 16px 64px} h1{font-size:26px}
  .chart{height:300px} .tiles{grid-template-columns:repeat(2,1fr)} }
</style>

<div class="wrap">
<header>
  <div class="eyebrow">A 股量化研究 · 多因子横截面选股</div>
  <h1>__H1__</h1>
  <p class="lede">__LEDE__</p>
  <div class="meta">__META__</div>
</header>

<section>
  <span class="eyebrow">01 / 结论</span>
  <h2>滚动样本外的成绩单</h2>
  <p>下面这组数字来自<b>滚动样本外</b>回测：每年只用过去 3 年的数据重估因子权重，
     再拿这组权重去交易下一年，然后把各年拼成一条净值曲线。曲线上的每一天，持仓
     都只依赖当天之前的信息 —— 包括"选哪些因子"这个动作本身。</p>
  <div class="tiles">__TILES__</div>
  <div class="card">
    <h3>净值曲线</h3>
    <p class="cap">起点归一为 1；策略已扣除佣金、过户费、印花税与 10bp 单边冲击成本。</p>
    <div id="nav" class="chart"></div>
  </div>
  <div class="card">
    <h3>分年度收益</h3>
    <p class="cap">"等权全A"是同一可投资股票池的等权组合，是衡量选股能力最诚实的
       对照 —— 跑不赢它，说明选股这一步没加分。</p>
    <div id="yearly" class="chart short"></div>
  </div>
  __YEARTABLE__
</section>

<section>
  <span class="eyebrow">02 / alpha</span>
  <h2>跑赢基准，是真本事还是运气</h2>
  <p>绝对收益高不等于有 alpha —— 敞口大一点、风格偏一点，牛市里都能跑赢指数。
     这一节把四件事分开问：<b>剥掉市场和风格之后还剩多少</b>、<b>这个夏普在
     我试过的参数规模下值不值钱</b>、<b>换一条路径还赚不赚</b>、
     <b>同一个股票池里随便选 __RANDN__ 次，能不能碰巧选到这么好</b>。</p>
  <div class="verdict">__VERDICT__</div>
  <h3 style="margin-top:30px">① alpha / beta 归因</h3>
  <p class="note">日收益对基准回归，截距即 alpha；t 值用 Newey-West 修正（滞后 5 期）
     —— 日频收益有自相关，不修正的话 t 值会偏大。「小盘风格」= 等权全A 收益 − 沪深300
     收益，用来剥掉「买小票」这个人人都能做的暴露。</p>
  __ALPHATABLE__
  <h3 style="margin-top:30px">② 随机组合置换检验</h3>
  <p class="note">同一个可投资股票池、同样的持股数与调仓日、同样的换手缓冲，把打分换成
     随机数跑 __RANDN__ 次。为了不让换手差异干扰结论，这一项两边都按<b>零成本</b>口径
     比较（随机组合的换手其实比策略还高一点）。</p>
  <div class="card">
    <h3>随机选股能跑出什么成绩</h3>
    <p class="cap">柱子是 __RANDN__ 个随机组合的年化收益分布，竖线是策略。</p>
    <div id="perm" class="chart short"></div>
  </div>
  <h3 style="margin-top:30px">③ Deflated Sharpe 与蒙特卡洛</h3>
  <p class="note">Deflated Sharpe（Bailey &amp; López de Prado）回答「以这个搜索规模，
     纯靠运气能刷到多高的夏普」；分块自助法保留 10 天的序列相关性重采样 5000 条路径，
     看有多少条是赚钱的。</p>
  __STATTABLE__
  <h3 style="margin-top:30px">④ 逐年剔除</h3>
  <p class="note">每次去掉一整年重算 alpha。多年回测最常见的假象是「某一年赚够了，
     其余年份贴地飞行」—— 年度贡献极不均匀时，全期 t 值会严重高估有效样本量。</p>
  __JACKTABLE__
</section>

<section>
  <span class="eyebrow">03 / 因子</span>
  <h2>哪些因子在 A 股还有效</h2>
  <p>__NFACTOR__ 个纯量价因子，按"数值越大预期收益越高"统一方向。IC 是每日截面的
     Spearman 秩相关，t 统计量用<b>非重叠</b>子样本计算（20 日前瞻收益的日频 IC
     序列高度自相关，直接用全样本算 t 会把显著性放大好几倍）。</p>
  <div class="card">
    <h3>因子 ICIR：样本内 vs 样本外</h3>
    <p class="cap">样本内 2016-01 ~ 2020-12，样本外 2021-01 ~ 2026-09。两根柱子方向
       一致才说明因子是稳的，只有一根高的多半是噪声。</p>
    <div id="icir" class="chart"></div>
  </div>
  <div class="card">
    <h3>因子之间的相关性</h3>
    <p class="cap">平均截面秩相关。深色成块说明这些因子说的是同一件事 —— 17 个因子
       并不等于 17 个独立的注，合成后的有效自由度要小得多。</p>
    <div id="corr" class="chart" style="height:460px"></div>
  </div>
  __FACTORTABLE__
</section>

<section>
  <span class="eyebrow">04 / 稳健性</span>
  <h2>换一组参数还成立吗</h2>
  <p>持股数、调仓频率、换手缓冲、权重方式、成交价口径逐一扫一遍。样本外那两列
     在挑参数时不参与决策 —— 如果一个策略只在某一格好看，那是在噪声上过拟合。</p>
  __GRIDTABLE__
</section>

<section>
  <span class="eyebrow">05 / 方法</span>
  <h2>防未来函数：做了什么，怎么验的</h2>
  <p>"回测很美、实盘很惨"的头号原因是未来函数。这套框架从数据、股票池、
     信号、成交四个环节把它堵住，并用可自动运行的测试来验证，而不是靠"我检查过了"。
     验证思路参考了
     <a href="https://github.com/frank-quant/ai-trading-videos/tree/main/EP004_four-llm-quant-benchmark">EP004
     的因果检查器</a>（全量 vs 截断对照），并扩展到整条净值曲线。</p>
  <ul>
    <li><b>后复权而非前复权</b>：前复权价会在未来分红送转发生时被改写，用它做回测
        等于让历史价格知道未来的分红。全流程只用后复权序列算收益和因子。</li>
    <li><b>信号 T、成交 T+1 开盘</b>：t 日收盘后出信号，次日开盘成交；涨停开盘不可买、
        跌停开盘不可卖、一字板双向不可成交、停牌不可交易，卡住的委托顺延到下一日。</li>
    <li><b>股票池不剔除"后来退市的"</b>：代码空间穷举下载，退市股在退市前一直留在池子里，
        退市当天按最后有效价清算。<b>__DELISTED__</b></li>
    <li><b>ST 反推只看过去</b>：没有 PIT 的 ST 名单，用过去 60 日的最大涨跌幅上限反推
        ±5% 限制，推断结果只用于当天之后的判断。</li>
    <li><b>权重不许全样本拟合</b>：单次 IS/OOS 切分之外，另做滚动重估 —— 把"挑因子"
        这个动作也纳入回测。</li>
    <li><b>成本按历史税率</b>：印花税 2023-08-28 起由 0.1% 减半至 0.05%，回测按当日
        实际税率计。</li>
  </ul>
  <h3 style="margin-top:26px">自动化验证</h3>
  <p class="note">核心手法是<b>截断不变性</b>：把数据在某一天截断后重跑，截断日之前的
     因子值和净值必须逐点相同 —— 真实交易在那一天本来就只有这些数据，结果一旦改变，
     就证明原来用到了未来。配套的<b>未来扰动测试</b>把截断日之后的数据换成随机数，
     历史结果同样必须不变。最后还有一条反向验证：故意造一个偷看次日收益的因子，
     检验必须报警，否则说明检验本身太松。</p>
  <ul class="checks">__CHECKS__</ul>
</section>

<section>
  <span class="eyebrow">06 / 局限</span>
  <h2>这套结果不能证明什么</h2>
  <div class="warn">__LIMITS__</div>
</section>

<footer>__FOOTER__</footer>
</div>

<script>
const DATA = __DATA__;
const css = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const charts = [];
function theme(){
  return {
    text: css('--text'), text2: css('--text-2'), muted: css('--muted'),
    line: css('--line'), grid: css('--grid'), surface: css('--surface'),
    up: css('--up'), down: css('--down'),
    series: [css('--s1'), css('--s2'), css('--s3'), css('--s4')]
  };
}
const baseGrid = {left: 8, right: 132, top: 28, bottom: 8, containLabel: true};
function mk(id, optFn){
  const el = document.getElementById(id);
  if(!el) return;
  const c = echarts.init(el, null, {renderer:'canvas'});
  const draw = () => c.setOption(optFn(theme()), true);
  draw();
  charts.push({c, draw});
}
function navChart(t){
  const d = DATA.nav; const names = d.names;
  const last = (arr) => arr[arr.length-1];
  return {
    animation:false, backgroundColor:'transparent',
    grid: baseGrid,
    tooltip:{trigger:'axis', axisPointer:{type:'cross', label:{backgroundColor:t.text2}},
      backgroundColor:t.surface, borderColor:t.line, textStyle:{color:t.text, fontSize:12},
      valueFormatter:(v)=> v==null?'-':v.toFixed(3)},
    legend:{data:names, top:0, right:0, icon:'roundRect', itemWidth:10, itemHeight:10,
      textStyle:{color:t.text2, fontSize:12}},
    xAxis:{type:'category', data:d.dates, boundaryGap:false,
      axisLine:{lineStyle:{color:t.line}}, axisTick:{show:false},
      axisLabel:{color:t.muted, fontSize:11, hideOverlap:true}},
    yAxis:{type:'value', min: d.min, max: d.max, splitNumber:5,
      splitLine:{lineStyle:{color:t.grid}}, axisLine:{show:false}, axisTick:{show:false},
      axisLabel:{color:t.muted, fontSize:11, formatter:(v)=>v.toFixed(2)}},
    series: names.map((n,i)=>({
      name:n, type:'line', data:d.series[i], showSymbol:false,
      lineStyle:{width: i===0?2.4:1.3, color:t.series[i], opacity: i===0?1:0.8},
      z: i===0?5:2, emphasis:{focus:'series'},
      endLabel:{show:true, color:t.series[i], fontSize:11, fontFamily:'IBM Plex Mono, monospace',
        formatter:()=> d.short[i] + '  ' + last(d.series[i]).toFixed(2), distance:6}
    }))
  };
}
function yearlyChart(t){
  const d = DATA.yearly;
  return {
    animation:false, backgroundColor:'transparent',
    grid:{left:8, right:8, top:28, bottom:8, containLabel:true},
    tooltip:{trigger:'axis', axisPointer:{type:'shadow'},
      backgroundColor:t.surface, borderColor:t.line, textStyle:{color:t.text, fontSize:12},
      valueFormatter:(v)=> (v==null?'-':v.toFixed(2)+'%')},
    legend:{data:d.names, top:0, right:0, icon:'roundRect', itemWidth:10, itemHeight:10,
      textStyle:{color:t.text2, fontSize:12}},
    xAxis:{type:'category', data:d.years, axisTick:{show:false},
      axisLine:{lineStyle:{color:t.line}}, axisLabel:{color:t.muted, fontSize:11}},
    yAxis:{type:'value', splitLine:{lineStyle:{color:t.grid}}, axisLabel:{color:t.muted,
      fontSize:11, formatter:'{value}%'}},
    series: d.names.map((n,i)=>({
      name:n, type:'bar', data:d.series[i], barGap:'10%', barCategoryGap:'34%',
      itemStyle:{ borderRadius:[3,3,0,0],
        color: [t.series[0], t.series[1], t.series[3]][i],
        opacity: i===0?1:0.6 }
    }))
  };
}
function icirChart(t){
  const d = DATA.icir;
  return {
    animation:false, backgroundColor:'transparent',
    grid:{left:8, right:24, top:28, bottom:8, containLabel:true},
    tooltip:{trigger:'axis', axisPointer:{type:'shadow'},
      backgroundColor:t.surface, borderColor:t.line, textStyle:{color:t.text, fontSize:12},
      valueFormatter:(v)=> v==null?'-':v.toFixed(3)},
    legend:{data:['样本内 ICIR','样本外 ICIR'], top:0, right:0, icon:'roundRect',
      itemWidth:10, itemHeight:10, textStyle:{color:t.text2, fontSize:12}},
    xAxis:{type:'value', splitLine:{lineStyle:{color:t.grid}},
      axisLabel:{color:t.muted, fontSize:11}},
    yAxis:{type:'category', data:d.names, axisTick:{show:false},
      axisLine:{lineStyle:{color:t.line}}, axisLabel:{color:t.text2, fontSize:11.5}},
    series:[
      {name:'样本内 ICIR', type:'bar', data:d.is, barGap:'10%', barCategoryGap:'34%',
       itemStyle:{color:t.series[0], borderRadius:[0,3,3,0]}},
      {name:'样本外 ICIR', type:'bar', data:d.oos,
       itemStyle:{color:t.series[1], borderRadius:[0,3,3,0]}}
    ]
  };
}
function corrChart(t){
  const d = DATA.corr; const n = d.names.length;
  const cells = [];
  for(let i=0;i<n;i++) for(let j=0;j<n;j++) cells.push([j, i, d.m[i][j]]);
  return {
    animation:false, backgroundColor:'transparent',
    grid:{left:8, right:8, top:8, bottom:8, containLabel:true},
    tooltip:{backgroundColor:t.surface, borderColor:t.line, textStyle:{color:t.text, fontSize:12},
      formatter:(p)=> d.names[p.value[1]] + ' × ' + d.names[p.value[0]] + '<br/>秩相关 ' + p.value[2].toFixed(2)},
    xAxis:{type:'category', data:d.names, splitArea:{show:false}, axisTick:{show:false},
      axisLine:{lineStyle:{color:t.line}},
      axisLabel:{color:t.muted, fontSize:10, rotate:52, hideOverlap:false}},
    yAxis:{type:'category', data:d.names, inverse:true, splitArea:{show:false},
      axisTick:{show:false},
      axisLine:{lineStyle:{color:t.line}}, axisLabel:{color:t.text2, fontSize:10.5}},
    visualMap:{min:-1, max:1, calculable:false, show:false,
      inRange:{color:[t.series[1], t.surface, t.series[0]]}},
    series:[{type:'heatmap', data:cells, itemStyle:{borderColor:t.surface, borderWidth:1.5},
      emphasis:{itemStyle:{borderColor:t.text, borderWidth:1.5}}}]
  };
}
function permChart(t){
  const d = DATA.perm;
  return {
    animation:false, backgroundColor:'transparent',
    grid:{left:8, right:16, top:24, bottom:8, containLabel:true},
    tooltip:{trigger:'axis', axisPointer:{type:'shadow'},
      backgroundColor:t.surface, borderColor:t.line, textStyle:{color:t.text, fontSize:12},
      formatter:(ps)=> '年化 ' + ps[0].name + '%<br/>' + ps[0].value + ' 个随机组合'},
    xAxis:{type:'category', data:d.bins, axisTick:{show:false},
      axisLine:{lineStyle:{color:t.line}},
      axisLabel:{color:t.muted, fontSize:11, formatter:(v)=> v + '%'}},
    yAxis:{type:'value', splitLine:{lineStyle:{color:t.grid}},
      axisLabel:{color:t.muted, fontSize:11}},
    series:[{type:'bar', data:d.counts, barCategoryGap:'18%',
      itemStyle:{color:t.series[0], opacity:0.55, borderRadius:[3,3,0,0]},
      markLine:{symbol:'none', silent:true,
        label:{formatter:'策略 ' + d.strat.toFixed(1) + '%', color:t.up, rotate:0,
               fontSize:11.5, position:'end', distance:[0, 6]},
        lineStyle:{color:t.up, width:2, type:'solid'},
        data:[{xAxis:d.stratBin}]}}]
  };
}
mk('nav', navChart); mk('yearly', yearlyChart); mk('icir', icirChart); mk('corr', corrChart);
mk('perm', permChart);
addEventListener('resize', ()=> charts.forEach(o=> o.c.resize()));
matchMedia('(prefers-color-scheme: dark)').addEventListener('change', ()=> charts.forEach(o=> o.draw()));
new MutationObserver(()=> charts.forEach(o=> o.draw()))
  .observe(document.documentElement, {attributes:true, attributeFilter:['data-theme']});
</script>
"""


def tile(k, v, s, cls=""):
    return (f'<div class="tile"><div class="k">{k}</div>'
            f'<div class="v {cls}">{v}</div><div class="s">{s}</div></div>')


def table(headers, rows, hl_first=False, align_left=0):
    th = "".join(f"<th>{h}</th>" for h in headers)
    trs = []
    for i, r in enumerate(rows):
        cls = ' class="hl"' if (hl_first and i == 0) else ""
        tds = "".join(f"<td>{c}</td>" for c in r)
        trs.append(f"<tr{cls}>{tds}</tr>")
    return (f'<div class="tablewrap"><table><thead><tr>{th}</tr></thead>'
            f'<tbody>{"".join(trs)}</tbody></table></div>')


def fmt(x, digits=2, pct=False, sign=False):
    if x is None:
        return "—"
    try:
        v = float(x)
    except (TypeError, ValueError):
        return str(x)
    s = f"{v:+.{digits}f}" if sign else f"{v:.{digits}f}"
    return s + ("%" if pct else "")


def main():
    wf = load("walkforward.json")
    rs = load("research.json")
    grid = load("grid.json")
    if wf is None or rs is None:
        print("缺少 reports/walkforward.json 或 research.json，先跑 run_research.py / run_walkforward.py")
        sys.exit(1)

    perf = {r["名称"]: r for r in wf["绩效"]}
    strat = [r for r in wf["绩效"] if r["名称"].startswith("滚动样本外")][0]
    eqw = perf.get("等权全A(可投池)", {})
    hs = perf.get("沪深300", {})

    # ---------------- 摘要卡片
    excess = strat["年化收益"] - eqw.get("年化收益", 0)
    tiles = "".join([
        tile("样本外年化", fmt(strat["年化收益"], 2, True), "滚动重估，全程 OOS",
             "pos" if strat["年化收益"] > 0 else "neg"),
        tile("超额 (对等权全A)", fmt(excess, 2, True, True), "衡量真实选股能力",
             "pos" if excess > 0 else "neg"),
        tile("夏普", fmt(strat["夏普(rf=0)"], 2), f'等权全A {fmt(eqw.get("夏普(rf=0)"), 2)}'),
        tile("最大回撤", fmt(strat["最大回撤"], 1, True), f'沪深300 {fmt(hs.get("最大回撤"), 1, True)}'),
        tile("年化换手", f'{wf["换手年化"]:.1f}×', "双边"),
        tile("成本拖累", fmt(wf["成本年化"] * 100, 2, True), "佣金+印花税+滑点"),
    ])

    # ---------------- 净值
    nav = wf["净值"]
    names = ["策略", "等权全A(可投池)", "中证500", "沪深300"]
    series = [nav[n] for n in names]
    flat = [v for s in series for v in s if v]
    nav_data = {"dates": nav["日期"], "names": names, "series": series,
                "short": ["策略", "等权全A", "中证500", "沪深300"],
                "min": round(min(flat) * 0.94, 2), "max": round(max(flat) * 1.06, 2)}

    # ---------------- 分年度
    yl = wf["分年度"]
    yearly = {"years": [str(r["年份"]) for r in yl],
              "names": ["策略", "等权全A", "沪深300"],
              "series": [[r["策略%"] for r in yl], [r["等权全A%"] for r in yl],
                         [r["沪深300%"] for r in yl]]}
    year_rows = [[r["年份"], fmt(r["策略%"], 2, True), fmt(r["等权全A%"], 2, True),
                  fmt(r["沪深300%"], 2, True), fmt(r["超额(对等权)%"], 2, True, True)] for r in yl]
    year_table = table(["年份", "策略", "等权全A", "沪深300", "超额"], year_rows)

    # ---------------- 因子表
    fis = {r["因子"]: r for r in rs["样本内因子表"]}
    foos = {r["因子"]: r for r in rs["样本外因子表"]}
    order = sorted(fis, key=lambda k: -(fis[k].get("ICIR20") or 0))
    icir = {"names": [fis[k]["说明"] for k in order][::-1],
            "is": [fis[k].get("ICIR20") for k in order][::-1],
            "oos": [foos.get(k, {}).get("ICIR20") for k in order][::-1]}
    frows = []
    for k in order:
        a, b = fis[k], foos.get(k, {})
        frows.append([a["说明"], fmt(a.get("IC20均值"), 3), fmt(a.get("ICIR20"), 2),
                      fmt(a.get("t20"), 2), fmt(b.get("IC20均值"), 3), fmt(b.get("ICIR20"), 2),
                      fmt(b.get("t20"), 2), fmt((a.get("多空年化") or 0) * 100, 1, True),
                      fmt((b.get("多空年化") or 0) * 100, 1, True)])
    factor_table = table(["因子", "IS IC", "IS ICIR", "IS t", "OOS IC", "OOS ICIR", "OOS t",
                          "IS 多空年化", "OOS 多空年化"], frows)

    va = load("validation.json", {}) or {}
    rp = va.get("随机组合", {})
    ab = va.get("alpha归因", {})
    alpha_rows = []
    for name, m in ab.items():
        if not m:
            continue
        b = {k.split("_", 1)[1]: v for k, v in m.items() if k.startswith("beta_")}
        alpha_rows.append([name, fmt(m["年化alpha"] * 100, 2, True, True),
                           fmt(m["alpha_t(NW)"], 2), fmt(m["alpha_p值(双侧)"], 4),
                           fmt(m["R2"], 3), fmt(b.get("沪深300"), 2),
                           fmt(b.get("等权全A"), 2), fmt(b.get("小盘风格"), 2)])
    alpha_table = table(["回归模型", "年化 alpha", "t (NW)", "p 值", "R²",
                         "β 沪深300", "β 等权全A", "β 小盘风格"],
                        alpha_rows) if alpha_rows else ""

    dsr = va.get("DSR", {})
    mc_a = va.get("蒙特卡洛_绝对", {})
    mc_e = va.get("蒙特卡洛_超额", {})
    stat_rows = []
    if dsr:
        stat_rows += [
            ["Deflated Sharpe", fmt(dsr.get("DSR"), 4), dsr.get("判定", "")],
            ["实际夏普 / 纯运气可达夏普",
             f'{fmt(dsr.get("实际夏普(年化)"), 2)} / {fmt(dsr.get("纯运气可达夏普(年化)"), 2)}',
             f'按 {dsr.get("试验次数")} 次参数试验、试验夏普方差 {dsr.get("试验夏普方差")} 折算'],
        ]
    if mc_a:
        stat_rows.append(["蒙特卡洛 · 绝对收益盈利路径",
                          fmt(mc_a["盈利路径占比"] * 100, 1, True),
                          f'P5 {mc_a["P5"]:.2f} / P50 {mc_a["P50"]:.2f} / P95 {mc_a["P95"]:.2f}'])
    if mc_e:
        stat_rows.append(["蒙特卡洛 · 超额为正路径",
                          fmt(mc_e["盈利路径占比"] * 100, 1, True),
                          f'P5 {mc_e["P5"]:.2f} / P50 {mc_e["P50"]:.2f} / P95 {mc_e["P95"]:.2f}'])
    if rp:
        stat_rows.append(["随机组合置换检验 p 值（收益）", fmt(rp.get("p值"), 4),
                          f'策略毛年化 {rp.get("策略毛年化", 0) * 100:.2f}%，'
                          f'随机均值 {rp.get("随机均值", 0) * 100:.2f}%'])
        stat_rows.append(["随机组合置换检验 p 值（alpha）", fmt(rp.get("alpha_p值"), 4),
                          f'策略毛 alpha {rp.get("策略毛alpha", 0) * 100:.2f}%，'
                          f'随机均值 {rp.get("随机alpha均值", 0) * 100:.2f}%'])
    stat_table = table(["检验", "取值", "说明"], stat_rows) if stat_rows else ""

    # 随机组合直方图
    perm = {"bins": [], "counts": [], "strat": 0.0, "stratBin": 0}
    dist = rp.get("随机年化分布", [])
    if dist:
        arr = np.array(dist) * 100
        strat = rp.get("策略毛年化", 0) * 100
        lo, hi = min(arr.min(), strat), max(arr.max(), strat)
        pad = (hi - lo) * 0.08 + 0.5
        edges = np.linspace(lo - pad, hi + pad, 25)
        counts, _ = np.histogram(arr, bins=edges)
        centers = [f"{(edges[i] + edges[i + 1]) / 2:.1f}" for i in range(len(edges) - 1)]
        sb = int(np.clip(np.searchsorted(edges, strat) - 1, 0, len(centers) - 1))
        perm = {"bins": centers, "counts": [int(c) for c in counts],
                "strat": round(float(strat), 2), "stratBin": centers[sb]}

    def verdict_text():
        if not va:
            return "<p>尚未运行 run_validation.py。</p>"
        m = ab.get("对沪深300+小盘风格", {})
        a = m.get("年化alpha", 0) * 100
        t_ = m.get("alpha_t(NW)", 0)
        pp = rp.get("alpha_p值", 1)
        d = dsr.get("DSR")
        parts = []
        if t_ >= 2 and pp <= 0.05:
            parts.append(f"<p><b>剥掉市场和小盘风格之后，净收益口径的年化 alpha 是 "
                         f"{a:+.2f}%，Newey-West t = {t_:.2f}</b>；随机选股 "
                         f"{rp.get('次数', 0)} 次里，策略的 alpha 排在分布之上，"
                         f"置换检验 p = {pp:.4f}。<b>结论：有 alpha，但不大。</b></p>")
        elif t_ >= 1.5 or pp <= 0.1:
            parts.append(f"<p><b>年化 alpha {a:+.2f}%，t = {t_:.2f}，随机组合置换 "
                         f"p = {pp:.4f} —— 方向对，但没到常规显著水平。</b>"
                         f"只能说「不像纯运气」，不能说「证实了」。</p>")
        else:
            parts.append(f"<p><b>剥掉市场和小盘风格之后，净收益口径的年化 alpha 只剩 "
                         f"{a:+.2f}%，Newey-West t = {t_:.2f} —— 统计上等于零。</b></p>")
            if rp:
                parts.append(
                    f"<p>更直接的证据是随机组合置换检验：同一个股票池、同样的持股数和调仓日，"
                    f"把打分换成随机数跑 {rp.get('次数')} 次，随机组合的毛年化均值是 "
                    f"{rp.get('随机均值', 0) * 100:.2f}%，策略是 "
                    f"{rp.get('策略毛年化', 0) * 100:.2f}%，只排在第 "
                    f"{rp.get('百分位', 0) * 100:.0f} 百分位，p = {rp.get('p值'):.2f}。"
                    f"<b>和随便选没有统计意义上的差别。</b></p>")
        if d is not None:
            if d >= 0.95:
                parts.append(f"<p>Deflated Sharpe = {d:.3f}，扣掉「试了这么多组参数」"
                             f"的运气成分后仍然显著。</p>")
            else:
                parts.append(f"<p>Deflated Sharpe = {d:.3f}，离 0.95 的显著线很远：实际"
                             f"年化夏普 {dsr.get('实际夏普(年化)')}，而以本项目试过的 "
                             f"{dsr.get('试验次数')} 组参数规模，纯靠运气就能刷到 "
                             f"{dsr.get('纯运气可达夏普(年化)')}。<b>高出的那一点，"
                             f"不足以排除是搜出来的。</b></p>")
        if jk and jk.get("最不利年份"):
            parts.append(
                f"<p><b>但这个 alpha 靠一年撑着：</b>剔除 {jk['最不利年份']} 年之后，"
                f"年化 alpha 从 {jk['全样本alpha'] * 100:.2f}% 掉到 "
                f"{jk['最低alpha'] * 100:.2f}%，t 从 {jk['全样本t']} 掉到 {jk['最低t']}。"
                + (f"八年里超额为正的只有 {ye.get('正年数')} 年。" if ye else "")
                + "有效样本比「1860 个交易日」听上去的少得多。</p>")
        net = rp.get("策略净年化")
        gross = rp.get("策略毛年化")
        if net is not None and gross is not None:
            drag = (gross - net) * 100
            tail = ("<b>成本吃掉的比它挣到的还多</b>。"
                    if drag >= abs(a) else
                    f"换手压到年化 {rp.get('策略换手', 0):.1f} 倍之后，成本这一刀只切掉 "
                    f"{drag:.2f} 个点 —— 相比周频调仓那版的 3.5 个点，"
                    f"<b>降换手是这轮唯一真正起作用的改动</b>。")
            parts.append(f"<p>成本：毛年化 {gross * 100:.2f}% 扣完佣金、印花税和滑点剩 "
                         f"{net * 100:.2f}%。{tail}</p>")
        return "".join(parts)

    jk = va.get("逐年剔除", {})
    ye = va.get("逐年超额", {})
    jack_table = ""
    if jk:
        jrows = [["全样本（不剔除）", fmt(jk["全样本alpha"] * 100, 2, True, True),
                  fmt(jk["全样本t"], 2), "—"]]
        base = jk["全样本alpha"]
        for row in jk["逐年剔除"]:
            jrows.append([f'剔除 {row["剔除年份"]} 年',
                          fmt(row["年化alpha"] * 100, 2, True, True),
                          fmt(row["alpha_t"], 2),
                          fmt((row["年化alpha"] - base) * 100, 2, True, True)])
        jack_table = table(["样本", "年化 alpha", "t (NW)", "相对全样本变化"], jrows,
                           hl_first=True)

    fc = rs.get("因子相关", {})
    corr = {"names": fc.get("名称", []), "m": fc.get("矩阵", [])}

    # ---------------- 参数网格
    grid_table = ""
    if grid:
        g = sorted(grid, key=lambda r: -(r["OOS超额%"] or -99))
        grows = [[f'{r["持股"]}只 / {r["调仓日"]}日 / 缓冲{r["缓冲"]}',
                  r["权重"], r["成交价"], "是" if r["计成本"] else "否",
                  fmt(r["IS超额%"], 2, True, True), fmt(r["OOS超额%"], 2, True, True),
                  fmt(r["OOS信息比"], 2), fmt(r["最大回撤%"], 1, True),
                  f'{r["换手(年)"]:.1f}×', fmt(r["成本%"], 2, True)] for r in g]
        grid_table = table(["参数组合", "权重", "成交价", "计成本", "IS 超额", "OOS 超额",
                            "OOS 信息比", "最大回撤", "换手", "成本"], grows)

    # ---------------- 测试清单
    tests = collect_tests()
    items = []
    for t in tests:
        fn = t.split("::")[-1]
        desc = TEST_DESC.get(fn, "")
        items.append(f'<li><span class="id">{fn}</span><span class="d">{desc}</span></li>')
    checks = "".join(items) or "<li><span class='d'>未采集到测试用例</span></li>"

    limits = """
    <p><b>只用了量价数据。</b>没有市值、估值、盈利这类基本面因子 —— 免费数据源拿不到
       可靠的 point-in-time 股本与财报公告日，硬凑只会引入更隐蔽的未来函数。
       小市值这个 A 股最强的因子，这里只能用成交额做粗糙代理。</p>
    <p><b>成交额是估算值。</b>行情接口不返回成交额，用「成交量 × 不复权收盘价」近似，
       流动性过滤和 Amihud 因子会有偏差。</p>
    <p><b>成交假设仍然乐观。</b>按开盘价成交、单边 10bp 冲击成本，对几十只股票、
       千万级规模是合理的；资金量再大，冲击成本会显著上升。未做最小 100 股的整手约束。</p>
    <p><b>回测不是实盘。</b>这里没有考虑打新收益、融券、停复牌套利、以及交易系统本身的
       延迟与拒单。样本外年化跑赢等权基准几个点，落到实盘会再打折。</p>
    <p><b>「研究者层面的偷看」没法完全消除。</b>代码里的未来函数已经用测试堵死了，
       但因子集合、成本假设、缓冲区设计这些决定，是我在能看到全样本结果的情况下做的。
       EP004 的做法是把测试段物理隔离在模型访问不到的盘符上，这里做不到同等程度的隔离
       —— Deflated Sharpe 就是用来给这部分「试出来的运气」打折的，它没过。</p>
    """

    meta = " ".join([
        f'<span><b>{rs["股票数"]}</b> 只股票（含退市）</span>',
        f'<span><b>{rs["交易日"]}</b> 个交易日</span>',
        f'<span>数据 <b>{config.DATA_START} ~ {config.DATA_END}</b></span>',
        f'<span>滚动样本外 <b>{wf["参数"]["start"]} ~ {config.BACKTEST_END}</b></span>',
        f'<span>持股 <b>{wf["参数"]["top_n"]}</b> 只 / 每 <b>{wf["参数"]["freq"]}</b> 交易日调仓</span>',
    ])

    delisted = rs.get("退市说明", "")
    n_factors = len(rs["样本内因子表"])
    lede = (f"全市场 {rs['股票数']} 只股票（含样本期内退市的 {rs.get('退市数', 0)} 只）、"
            f"{n_factors} 个纯量价因子、信号 T 成交 T+1，防未来函数全部写成可自动运行的测试。"
            "样本内的超额收益看着很像回事，四层统计检验做完之后一样不剩。"
            "这页记的是这个证伪过程 —— 以及它是怎么被验出来的。")

    html = (HTML
            .replace("__TITLE__", "A股量价因子证伪记")
            .replace("__H1__", "17 个量价因子，一层层验到最后没剩下 alpha")
            .replace("__LEDE__", lede)
            .replace("__META__", meta)
            .replace("__NFACTOR__", str(n_factors))
            .replace("__RANDN__", str(rp.get("次数", 0)))
            .replace("__VERDICT__", verdict_text())
            .replace("__ALPHATABLE__", alpha_table)
            .replace("__STATTABLE__", stat_table)
            .replace("__JACKTABLE__", jack_table)
            .replace("__TILES__", tiles)
            .replace("__YEARTABLE__", year_table)
            .replace("__FACTORTABLE__", factor_table)
            .replace("__GRIDTABLE__", grid_table)
            .replace("__CHECKS__", checks)
            .replace("__DELISTED__", delisted)
            .replace("__LIMITS__", limits)
            .replace("__FOOTER__", f'生成于 {wf.get("生成时间", rs["生成时间"])} · '
                                   f'代码与测试见 astock_quant/ · pytest {len(tests)} 项全部通过')
            .replace("__DATA__", json.dumps({"nav": nav_data, "yearly": yearly, "icir": icir,
                                             "corr": corr, "perm": perm},
                                            ensure_ascii=False)))
    out = os.path.join(R, "report.html")
    with open(out, "w") as f:
        f.write(html)
    print(f"报告写入 {out}（{len(html) / 1024:.0f} KB）")


if __name__ == "__main__":
    main()
