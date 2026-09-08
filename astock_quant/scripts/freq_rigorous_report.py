#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 smallcap_freq_rigorous.json 渲染成单页 HTML 报告（ECharts）。"""
from __future__ import annotations

import json
import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
AQ_ROOT = os.path.dirname(CURRENT_DIR)
PROJECT_ROOT = os.path.dirname(AQ_ROOT)

SRC = os.path.join(PROJECT_ROOT, "deliverables", "smallcap_freq_rigorous.json")
GATE = os.path.join(PROJECT_ROOT, "deliverables", "smallcap_freq_gate.json")
ATTRIB = os.path.join(PROJECT_ROOT, "deliverables", "smallcap_freq_attrib.json")
AB = os.path.join(PROJECT_ROOT, "deliverables", "smallcap_freq_ab.json")
OUT = os.path.join(PROJECT_ROOT, "deliverables", "smallcap_freq_rigorous.html")


def load():
    with open(SRC, encoding="utf-8") as f:
        d = json.load(f)
    if os.path.exists(GATE):
        with open(GATE, encoding="utf-8") as f:
            d["gate"] = json.load(f)
    if os.path.exists(ATTRIB):
        with open(ATTRIB, encoding="utf-8") as f:
            d["attrib"] = json.load(f)
    if os.path.exists(AB):
        with open(AB, encoding="utf-8") as f:
            d["ab"] = json.load(f)
    return d


def esc(x):
    return (str(x).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def build(d: dict) -> str:
    ic = d["ic_decay"]
    grid = d["grid_train_valid"]
    blind = d["test_blind"]
    sel = d["selected_freq"]
    fals = d["falsification"]
    rob = d["robustness"]

    freqs = [g["freq"] for g in grid]
    tr_cagr = [g["TRAIN"]["年化%"] for g in grid]
    va_cagr = [g["VALID"]["年化%"] for g in grid]
    tr_sr = [g["TRAIN"]["夏普"] for g in grid]
    va_sr = [g["VALID"]["夏普"] for g in grid]
    te_cagr = [blind[str(f)]["年化%"] for f in freqs]
    te_sr = [blind[str(f)]["夏普"] for f in freqs]
    te_gross = [blind[str(f)]["毛年化%"] for f in freqs]
    te_cost = [blind[str(f)]["成本%"] for f in freqs]
    te_to = [blind[str(f)]["换手x"] for f in freqs]
    te_ex = [blind[str(f)]["超额等权%"] for f in freqs]
    churn = [g["每次变动只数"] for g in grid]

    ic_h = [r["持有期h"] for r in ic]
    ic_mean = [r["IC均值"] for r in ic]
    ic_ir = [r["ICIR"] for r in ic]

    # 表格行
    rows = []
    for g in grid:
        b = blind[str(g["freq"])]
        best_mark = " ◀ 目标函数选出" if g["freq"] == sel else ""
        online_mark = " ⬅ 线上" if g["freq"] == 10 else ""
        rows.append(f"""<tr class="{'hl' if g['freq'] == sel else ''}">
<td class="num">{g['freq']}{best_mark}{online_mark}</td>
<td class="num">{g['调仓次数']}</td>
<td class="num">{g['每次变动只数']}</td>
<td class="num {'neg' if tr_cagr[freqs.index(g['freq'])] < 0 else ''}">{g['TRAIN']['年化%']}</td>
<td class="num">{g['TRAIN']['夏普']}</td>
<td class="num {'neg' if va_cagr[freqs.index(g['freq'])] < 0 else ''}">{g['VALID']['年化%']}</td>
<td class="num">{g['VALID']['夏普']}</td>
<td class="num">{g['VALID']['回撤%']}</td>
<td class="num">{g['loss']}</td>
<td class="num {'neg' if b['年化%'] < 0 else ''}">{b['年化%']}</td>
<td class="num">{b['夏普']}</td>
<td class="num">{b['回撤%']}</td>
<td class="num">{b['毛年化%']}</td>
<td class="num">{b['成本%']}</td>
<td class="num">{b['换手x']}</td>
<td class="num">{b['超额等权%']}</td>
</tr>""")

    g1 = fals["闸1因果"]
    g2 = fals["闸2归因"]
    g3 = fals["闸3DSR"]
    g4 = fals["闸4运气"]

    gate = d.get("gate", {})
    gc = gate.get("因果闸", {})
    gp = gate.get("置换", [])
    if gp:
        p_freq = [r["freq"] for r in gp]
        p_real = [r["真实年化%"] for r in gp]
        p_rand = [r["随机均值%"] for r in gp]
        p_p95 = [r["随机P95%"] for r in gp]
        p_frac = [r["真实分位"] for r in gp]
    else:
        p_freq = p_real = p_rand = p_p95 = p_frac = []

    gate1_row = f"""<tr><td>① 因果闸</td><td>历史前缀重算 + 未来数据投毒（逐位比对）</td>
<td>截断于 {esc(gc.get('截断点','-'))}，重算后 {esc(gc.get('比对调仓日数','-'))} 个调仓日持仓逐位比对，max|diff| = <b>{esc(gc.get('前缀重算_max_abs_diff','-'))}</b>；把截断点之后的价格乘 0.01~50 倍投毒，max|diff| = <b>{esc(gc.get('未来投毒_max_abs_diff','-'))}</b></td>
<td>{('<span class="ok">PASS — 无未来函数</span>' if gc.get('前缀重算_判定') == 'PASS' and gc.get('未来投毒_判定') == 'PASS' else '<span class="bad">FAIL</span>')}</td></tr>"""

    at = d.get("attrib", {})
    at_cases = at.get("cases", [])
    at_bench = ["沪深300", "可投资宇宙等权", "全市场等权", "双因子"]
    at_freqs = [c["freq"] for c in at_cases]
    at_t = {b: [c[b]["alpha_t(NW)"] for c in at_cases] for b in at_bench}
    at_a = {b: [c[b]["年化alpha%"] for c in at_cases] for b in at_bench}

    at_rows = "".join(
        "<tr><td class='num'>" + str(c["freq"]) + "</td><td class='num'>" + str(c["TEST调仓次数"]) + "</td>" +
        "".join(
            f"<td class='num'>{c[b]['年化alpha%']}</td><td class='num'>{c[b]['alpha_t(NW)']}</td>"
            f"<td class='num'>{c[b]['p值']}</td><td class='num'>{c[b].get('beta', c[b].get('beta_可投资宇宙等权'))}</td>"
            for b in at_bench) +
        f"<td>{'<span class=ok>显著</span>' if abs(c['可投资宇宙等权']['alpha_t(NW)']) >= 1.96 else '<span class=bad>不显著</span>'}</td></tr>"
        for c in at_cases)

    at_note = "".join(f"<dt>{esc(k)}</dt><dd>{esc(v)}</dd>" for k, v in at.get("基准说明", {}).items())

    # ---- A/B 诊断
    ab = d.get("ab", {})
    ra = ab.get("A_流动性门槛", [])
    rb_ = ab.get("B_滞后带", [])
    dg = ab.get("B_诊断_抖动来源", [])

    a_pct = sorted({r["liq_top_pct"] for r in ra})
    a_byf = {}
    for f_ in sorted({r["freq"] for r in ra}):
        a_byf[f_] = [next(r for r in ra if r["liq_top_pct"] == p and r["freq"] == f_)["TEST"]["年化%"]
                     for p in a_pct]
    a_pool = [next(r for r in ra if r["liq_top_pct"] == p and r["freq"] == 10)["池内股票中位数"]
              for p in a_pct]
    a_rows = "".join(
        f"<tr><td class='num'>{r['liq_top_pct']}</td><td class='num'>{r['freq']}</td>"
        f"<td class='num'>{r['池内股票中位数']}</td><td class='num'>{r['每期变动只数']}</td>"
        f"<td class='num'>{r['TRAIN']['年化%']}</td><td class='num'>{r['VALID']['年化%']}</td>"
        f"<td class='num strong'>{r['TEST']['年化%']}</td><td class='num'>{r['TEST']['夏普']}</td>"
        f"<td class='num'>{r['TEST']['回撤%']}</td><td class='num'>{r['TEST']['毛年化%']}</td>"
        f"<td class='num'>{r['TEST']['换手x']}</td><td class='num'>{r['TEST']['成本%']}</td></tr>"
        for r in ra)

    b_buf = sorted({r["buffer"] for r in rb_})
    b_churn = {f_: [next(r for r in rb_ if r["buffer"] == b and r["freq"] == f_)["每期变动只数"]
                    for b in b_buf] for f_ in sorted({r["freq"] for r in rb_})}
    b_cagr = {f_: [next(r for r in rb_ if r["buffer"] == b and r["freq"] == f_)["TEST"]["年化%"]
                   for b in b_buf] for f_ in sorted({r["freq"] for r in rb_})}
    b_to = {f_: [next(r for r in rb_ if r["buffer"] == b and r["freq"] == f_)["TEST"]["换手x"]
                 for b in b_buf] for f_ in sorted({r["freq"] for r in rb_})}
    b_rows = "".join(
        f"<tr><td class='num'>{r['buffer']}</td><td class='num'>{r['保留名次']}</td>"
        f"<td class='num'>{r['freq']}</td><td class='num strong'>{r['每期变动只数']}</td>"
        f"<td class='num'>{r['TRAIN']['年化%']}</td><td class='num'>{r['VALID']['年化%']}</td>"
        f"<td class='num strong'>{r['TEST']['年化%']}</td><td class='num'>{r['TEST']['夏普']}</td>"
        f"<td class='num'>{r['TEST']['回撤%']}</td><td class='num'>{r['TEST']['换手x']}</td>"
        f"<td class='num'>{r['TEST']['成本%']}</td></tr>"
        for r in rb_)
    dg_rows = "".join(
        f"<tr><td>{esc(r['口径'])}</td><td class='num'>{r['每期变动只数']}</td>"
        f"<td class='num'>{r['相邻调仓日排名自相关']}</td></tr>" for r in dg)

    g2_row = f"""<tr><td>② 归因</td><td>对标准可交易基准回归，NW(5) 修正（详见下节）</td>
<td>vs <b>可投资宇宙等权</b>：年化 alpha {at_cases[1]['可投资宇宙等权']['年化alpha%'] if len(at_cases) > 1 else '-'}%，t(NW)={at_cases[1]['可投资宇宙等权']['alpha_t(NW)'] if len(at_cases) > 1 else '-'}，p={at_cases[1]['可投资宇宙等权']['p值'] if len(at_cases) > 1 else '-'}，beta={at_cases[1]['可投资宇宙等权']['beta'] if len(at_cases) > 1 else '-'}<br>
vs <b>沪深300</b>：年化 alpha {at_cases[1]['沪深300']['年化alpha%'] if len(at_cases) > 1 else '-'}%，t(NW)={at_cases[1]['沪深300']['alpha_t(NW)'] if len(at_cases) > 1 else '-'}，p={at_cases[1]['沪深300']['p值'] if len(at_cases) > 1 else '-'}</td>
<td>{('<span class="ok">显著</span>' if at_cases and abs(at_cases[1]['可投资宇宙等权']['alpha_t(NW)']) >= 1.96 else '<span class="bad">不显著 — 收益主要来自 beta</span>') if len(at_cases) > 1 else '-'}</td></tr>""" if at_cases else ""

    perm_rows = "".join(
        f"<tr><td class='num'>{r['freq']}</td><td class='num'>{r['TEST调仓次数']}</td>"
        f"<td class='num strong'>{r['真实年化%']}</td><td class='num'>{r['随机均值%']}</td>"
        f"<td class='num'>{r['随机P95%']}</td><td class='num'>{r['真实-随机均值_pp']:+}</td>"
        f"<td class='num'>{r['真实分位']}</td><td class='num'>{r['置换p值']}</td>"
        f"<td>{'<span class=ok>显著</span>' if r['置换p值'] <= 0.05 else '<span class=bad>不显著</span>'}</td></tr>"
        for r in gp)

    rob_rows = "".join(
        f"<tr><td class='num'>{r['N']}</td><td class='num'>{r['buffer']}</td>"
        f"<td class='num strong'>{r['最优freq']}</td></tr>" for r in rob)

    rob_dist = "".join(
        f"<tr><td class='num'>N={r['N']} buffer={r['buffer']}</td>" +
        "".join(f"<td class='num'>{v}</td>" for v in r["各freq_VALID夏普"].values()) +
        "</tr>" for r in rob)
    rob_head = "".join(f"<th>{f}</th>" for f in freqs)

    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>小微盘策略 · 调仓频率严谨研究</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
<style>
:root{{--bg:#f7f8fa;--card:#fff;--bd:#e5e7eb;--tx:#1f2328;--mut:#6b7280;--pos:#d93025;--neg:#0f9960;--acc:#2563eb}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--tx);font:14px/1.6 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif}}
.wrap{{max-width:1240px;margin:0 auto;padding:28px 20px 80px}}
h1{{font-size:24px;margin:0 0 6px}}
h2{{font-size:18px;margin:34px 0 12px;padding-left:10px;border-left:4px solid var(--acc)}}
.sub{{color:var(--mut);font-size:13px;margin-bottom:20px}}
.card{{background:var(--card);border:1px solid var(--bd);border-radius:10px;padding:18px 20px;margin-bottom:16px}}
.concl{{border-left:4px solid var(--acc);background:#eff6ff}}
.concl b{{color:var(--acc)}}
.chart{{height:340px}}
table{{width:100%;border-collapse:collapse;font-size:12.5px}}
th,td{{border:1px solid var(--bd);padding:6px 8px;text-align:left}}
th{{background:#f3f4f6;font-weight:600;white-space:nowrap}}
td.num{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}}
tr.hl td{{background:#fffbeb}}
.neg{{color:var(--neg)}}
.strong{{font-weight:700;color:var(--acc)}}
.kv{{display:grid;grid-template-columns:auto 1fr;gap:4px 14px;font-size:13px}}
.kv dt{{color:var(--mut);white-space:nowrap}}
.kv dd{{margin:0}}
.pill{{display:inline-block;padding:1px 8px;border-radius:10px;font-size:12px;border:1px solid var(--bd);background:#f9fafb}}
.ok{{color:var(--neg)}} .bad{{color:var(--pos)}}
.note{{font-size:12.5px;color:var(--mut);margin-top:8px}}
</style></head><body><div class="wrap">

<h1>线上小微盘策略 · 调仓频率严谨研究</h1>
<div class="sub">策略 <code>ashare_joinquant_smallcap_micro</code> · 唯一自由度 = 调仓频率 · 三段切分 + TEST 物理隔离 + 四层证伪 · 生成于 {esc(d['meta']['生成时间'])}</div>

<div class="card concl">
<b>结论先行</b>
<ol style="margin:8px 0 0 20px;padding:0">
<li>线上的「每 10 个交易日」<b>不是搜出来的，是沿用的模板默认值</b>。它在回测里既不是收益最高，也不是夏普最高。</li>
<li>频率是这个策略的<b>生死参数</b>：低于 7 个交易日，成本与排名噪声把年化打到负数；7 天以上才转正。</li>
<li>锁死目标函数在 TRAIN/VALID 上选出的是 <b>freq={sel}</b>；揭盲后 TEST 段 {sel} 与 10 的差距是 <b>{round(te_cagr[freqs.index(sel)] - te_cagr[freqs.index(10)], 2)} pp 年化</b>。</li>
<li>机理上，这个合成信号<b>不衰减</b>（IC 随持有期单调升到 h≈90 才饱和），所以「频繁调仓没有新信息，只有新成本」——这正是低频占优的原因。</li>
<li><b>但换成能直接买的标准基准后，alpha 基本消失了。</b>对可投资宇宙等权：freq=10 的 alpha 只有 3.06%/年（t=0.30），freq=20 是 8.46%/年（t=0.77，p=0.44）——都<b>不显著</b>。唯一过线的是 freq=60（24.05%/年，t=2.50，p=0.012），但它在 TEST 只调仓 11 次、且是从 12 个频率里挑出来的，折减后 p≈0.14。</li>
</ol>
</div>

<div class="card">
<h2 style="margin-top:0">L0 · 口径冻结（除频率外全部锁死为线上生产值）</h2>
<dl class="kv">
{''.join(f'<dt>{esc(k)}</dt><dd>{esc(v)}</dd>' for k, v in d['meta']['口径冻结'].items())}
<dt>切分</dt><dd>TRAIN {esc(d['meta']['切分']['TRAIN'][0])}~{esc(d['meta']['切分']['TRAIN'][1])} ｜ VALID {esc(d['meta']['切分']['VALID'][0])}~{esc(d['meta']['切分']['VALID'][1])} ｜ TEST {esc(d['meta']['切分']['TEST'][0])}~{esc(d['meta']['切分']['TEST'][1])}（物理隔离）</dd>
<dt>目标函数</dt><dd>{esc(d['meta']['目标函数'])}</dd>
<dt>频率网格</dt><dd>{esc(d['meta']['频率网格'])}</dd>
</dl>
</div>

<h2>L1 · 机理：信号信息随持有期怎么衰减</h2>
<div class="card">
<div id="c_ic" class="chart"></div>
<div class="note">Rank IC = 合成信号与「T+1 开盘建仓、持有 h 天」收益的横截面秩相关。IC<b>不随 h 衰减、反而上升</b>，说明这个信号是<b>慢变量</b>（小盘规模 + 低特质波动是慢信号，5 日反转占比只有 0.5/(1+0.5+0.5)=25%）。
慢信号 → 早调仓换不来新信息，只带来换手成本。这是「低频优于高频」的机理根因。</div>
</div>

<h2>L2 · 频率 × 三段绩效</h2>
<div class="card">
<div id="c_cagr" class="chart"></div>
</div>
<div class="card">
<div id="c_sr" class="chart"></div>
</div>

<h2>L3 · 成本分解：高频到底亏在哪</h2>
<div class="card">
<div id="c_cost" class="chart"></div>
<div class="note">TEST 段（揭盲后）毛收益 − 成本 = 净收益。频率越高，毛收益几乎不涨甚至下降，成本却线性放大。</div>
</div>
<div class="card">
<div id="c_turn" class="chart"></div>
<div class="note">N=7，buffer=2.0（前 14 名不卖）。但每次调仓仍变动约 13 只 ≈ <b>几乎全换</b>，说明 buffer 没兜住排名抖动（rev5 项让综合排名每天都在跳）。
调仓次数 × 近乎全换 = 换手随频率线性放大。</div>
</div>

<h2>全网格明细</h2>
<div class="card" style="overflow-x:auto">
<table>
<thead><tr>
<th>频率<br>(交易日)</th><th>调仓<br>次数</th><th>每期<br>变动只数</th>
<th>TRAIN<br>年化%</th><th>TRAIN<br>夏普</th>
<th>VALID<br>年化%</th><th>VALID<br>夏普</th><th>VALID<br>回撤%</th><th>loss</th>
<th>TEST<br>年化%</th><th>TEST<br>夏普</th><th>TEST<br>回撤%</th><th>TEST<br>毛年化%</th><th>TEST<br>成本%</th><th>TEST<br>换手x</th><th>TEST<br>超额等权%</th>
</tr></thead>
<tbody>{''.join(rows)}</tbody>
</table>
<div class="note">loss = −(valid_sr − 0.5·max(0, train_sr − valid_sr))，越小越好；该式只用于 TRAIN/VALID 选频，TEST 列是<b>揭盲后</b>展示，不参与选择。</div>
</div>

<h2>L5 · 四层证伪（TEST 段，freq={sel}）</h2>
<div class="card">
<table>
<thead><tr><th>层</th><th>检验</th><th>结果</th><th>判定</th></tr></thead>
<tbody>
{gate1_row}
{g2_row}
<tr><td>③ 抗运气</td><td>Deflated Sharpe（试错次数={g3.get('试验次数')}）</td>
<td>实际夏普 {g3.get('实际夏普(年化)')} ｜ 纯运气可达 {g3.get('纯运气可达夏普(年化)')} ｜ DSR={g3.get('DSR')}</td>
<td>{esc(g3.get('判定',''))}</td></tr>
<tr><td>④ 运气/置换</td><td>分块自助 5000 次 + 随机组合置换 {g4['置换次数']} 次</td>
<td>盈利路径占比 {g4['分块自助'].get('盈利路径占比')} ｜ P5={g4['分块自助'].get('P5')} ｜ 真实 {g4['真实年化%']}% vs 随机均值 {g4['随机组合_均值%']}%（P95 {g4['随机组合_P95%']}%）｜ 分位 {g4['真实分位']} ｜ p={g4['置换p值']}</td>
<td>{'<span class="ok">不是随机运气</span>' if g4['置换p值'] <= 0.05 else '<span class="bad">无法排除随机运气</span>'}</td></tr>
</tbody></table>
<div class="note">置换检验控制住股票池、持股数、调仓日，只把「打分」换成随机数——这是选股 alpha 最直接的证据。</div>
</div>

<h2>关键一问：低频更好，是选股能力变强了，还是只是少交了手续费？</h2>
<div class="card">
<div id="c_perm" class="chart"></div>
<div class="note">对照组的构造：同一个股票池、同样的持股数 N=7、同样的调仓日、同样的交易成本，只把「打分」换成<b>随机数</b>。
它控住了市场、风格、调仓节奏，剩下的差异才是选股能力。</div>
</div>
<div class="card" style="overflow-x:auto">
<table>
<thead><tr><th>频率</th><th>TEST<br>调仓次数</th><th>真实<br>年化%</th><th>随机组合<br>均值%</th><th>随机组合<br>P95%</th><th>真实−随机<br>pp</th><th>真实<br>分位</th><th>置换<br>p 值</th><th>判定</th></tr></thead>
<tbody>{perm_rows}</tbody>
</table>
<div class="note">若「真实 − 随机」在各频率上都是小数字、p 值都 &gt; 0.05，说明频率调得再准也修不好 alpha —— 收益主要是微盘 beta，不是选股。</div>
</div>

<h2>beta 归因（重做）：只用最广为人知 / 能直接买的基准</h2>
<div class="card">
<dl class="kv">{at_note}</dl>
<div class="note" style="margin-top:10px">
<b>为什么重做。</b>第一版把「全A等权 − 沪深300」这个自制残差因子当作第二解释变量，等于把大部分收益记在一个无法理解、也无法直接交易的合成因子账上——那是在给 alpha 打掩护。
这一版只认三类能直接买、或在业内通用的基准。横截面选股策略真正诚实的对照是<b>可投资宇宙等权</b>：你能在同一批股票里随机挑，随机挑能拿到的收益就不算你的 alpha。
</div>
</div>
<div class="card">
<div id="c_attrib" class="chart"></div>
</div>
<div class="card" style="overflow-x:auto">
<table>
<thead><tr><th rowspan="2">频率</th><th rowspan="2">TEST<br>调仓次数</th>
<th colspan="4">沪深300</th><th colspan="4">可投资宇宙等权</th><th colspan="4">全市场等权</th><th colspan="4">沪深300+宇宙等权</th><th rowspan="2">判定</th></tr>
<tr>{''.join(f'<th>alpha%</th><th>t(NW)</th><th>p</th><th>beta</th>' for _ in at_bench)}</tr></thead>
<tbody>{at_rows}</tbody>
</table>
<div class="note">判定以「可投资宇宙等权」为准（|t| ≥ 1.96 才显著）。双因子列里的 beta 取「可投资宇宙等权」的 beta。</div>
</div>

<h2>L6 · 稳健性：换 N / 换 buffer，最优频率还稳吗</h2>
<div class="card">
<table style="max-width:420px"><thead><tr><th>N</th><th>buffer</th><th>最优 freq</th></tr></thead>
<tbody>{rob_rows}</tbody></table>
<div class="note" style="margin-top:14px">各配置下 VALID 夏普随频率的分布：</div>
<div style="overflow-x:auto;margin-top:8px">
<table><thead><tr><th>配置</th>{rob_head}</tr></thead><tbody>{rob_dist}</tbody></table>
</div>
</div>

<h2>A/B · 剔不剔「最不活跃的 20%」？</h2>
<div class="card">
<div id="c_liq" class="chart"></div>
<div class="note"><code>liquidity_top_pct</code> 按过去 20 日均成交额排序，只保留前 X%。<b>0.80 = 剔掉最不活跃 20%（库默认），1.0 = 不剔（线上生产值）。</b>
小微盘策略的超额本来就来自最冷清的那批票，所以这个参数不是技术细节，它可能直接决定策略有没有收益。</div>
</div>
<div class="card" style="overflow-x:auto">
<table>
<thead><tr><th>liq_top_pct</th><th>freq</th><th>池内股票<br>中位数</th><th>每期<br>变动只数</th>
<th>TRAIN<br>年化%</th><th>VALID<br>年化%</th><th>TEST<br>年化%</th><th>TEST<br>夏普</th><th>TEST<br>回撤%</th><th>TEST<br>毛年化%</th><th>TEST<br>换手x</th><th>TEST<br>成本%</th></tr></thead>
<tbody>{a_rows}</tbody>
</table>
</div>
<div class="card concl">
<b>这个参数的影响有多大：巨大，但完全不可信</b>
<ul style="margin:6px 0 0 20px;padding:0">
<li><b>量级</b>：freq=10 时，TEST 年化从 pct=1.0 的 14.58% 跳到 pct=0.8 的 <b>35.32%</b>，20pp+。剔掉最不活跃 20% <b>不是</b>让策略变差，反而是变好——我先前"微盘超额来自最冷清那批"的假设是错的。</li>
<li><b>但方向乱跳</b>：pct 从 0.6→1.0 走一遍，freq=10 的 TEST 年化是 <b>33.40 / 3.71 / 35.32 / 29.73 / 14.58</b>。0.6 到 0.7 一步掉 30pp，0.7 到 0.8 又涨回来 32pp。这不是一条有意义的曲线，这是噪声。</li>
<li><b>三段互相打架</b>：TRAIN/VALID 支持 1.0（freq=20：VALID 21.06% vs pct=0.8 的 −5.47%），TEST 却支持 0.8（42.85% vs 20.71%）。同一个参数，在两个区间给出相反的最优值。</li>
<li style="margin-top:6px"><b>真正的信息在这里</b>：一个与信号逻辑无关的池子筛选参数，就能让年化摆动 ±20~30pp。
这说明<b>本策略的回测数字对参数极度敏感</b>——那么 freq=60 的 39.71%、freq=30 的 27.10%，和 pct=0.8 的 42.85% 属于同一类东西：<b>单点估计，不可信</b>。这也是不建议直接跳到季频的最强理由。</li>
</ul>
</div>

<h2>A/B · 滞后带 buffer：调到真正生效，比不缓冲强多少</h2>
<div class="card">
<div id="c_buf" class="chart"></div>
<div class="note">buffer=1.0 就是<b>不缓冲</b>（每期严格取分数最高的 N 只）；buffer=k 表示已持仓只要还在前 k×N 名就不卖。
线上是 2.0（前 14 名保留），但实测每期仍变动约 13 只 ≈ 全换 —— 缓冲区没兜住。</div>
</div>
<div class="card" style="overflow-x:auto">
<table>
<thead><tr><th>buffer</th><th>保留名次</th><th>freq</th><th>每期<br>变动只数</th>
<th>TRAIN<br>年化%</th><th>VALID<br>年化%</th><th>TEST<br>年化%</th><th>TEST<br>夏普</th><th>TEST<br>回撤%</th><th>TEST<br>换手x</th><th>TEST<br>成本%</th></tr></thead>
<tbody>{b_rows}</tbody>
</table>
</div>
<div class="card">
<b>为什么 2.0 的缓冲区兜不住？排名抖动来自谁</b>
<div style="overflow-x:auto;margin-top:8px">
<table><thead><tr><th>口径</th><th>每期变动只数</th><th>相邻调仓日排名自相关</th></tr></thead>
<tbody>{dg_rows}</tbody></table>
</div>
<div class="note">排名自相关越低 = 分数排名在调仓日之间跳得越厉害。若去掉 rev5 后自相关明显上升、变动只数明显下降，就坐实了 rev5 是抖动源。</div>
</div>
<div class="card concl">
<b>调到真正生效的值，比不缓冲强多少：几乎没区别</b>
<ul style="margin:6px 0 0 20px;padding:0">
<li><b>数字</b>（freq=20）：buffer 从 1.0（不缓冲）拉到 6.0（前 42 名保留），每期变动只数 13.72 → <b>12.80</b>（只降 7%），年换手 24.2x → <b>21.9x</b>（只降 9.5%），TEST 年化 21.99% → 22.60%（+0.6pp），成本 3.65% → 3.29%。
换句话说：<b>缓冲区开到最大也只省下不到 10% 的换手</b>，收益几乎不动。</li>
<li><b>根因不是 buffer 太小，是选得太极端。</b>N=7 / 池内 2600 只 = <b>万里挑三</b>。相邻调仓日全池排名自相关 0.820 看着不低，但那是被两千多只中尾部股票撑起来的；头部 Top-7 只占 0.27%，整体相关性和它基本无关——<b>头部每次都在换血</b>。</li>
<li><b>rev5 只背一部分锅。</b>去掉 rev5 后自相关 0.82 → 0.922、变动只数 12.95 → 10.07（降 22%）。有改善，但 10.07 只仍是「近似全换」，剩下的抖动来自头部截断本身。</li>
<li style="margin-top:6px"><b>想真正降换手，别调 buffer，改这两处</b>：① <b>加大 N</b>（N=30 时是前 1.2% 而非前 0.27%，头部会稳得多，buffer 才有用武之地）；② <b>平滑分数</b>（对 composite score 取 5~10 日移动平均再排名，直接把排名噪声滤掉）。这两个都是新参数，要动就得重走完整搜索 + 隔离流程。</li>
</ul>
</div>

<h2>回答：为什么是两周？以及该不该改</h2>
<div class="card concl">
<p><b>① 为什么是两周（10 个交易日）</b></p>
<ol style="margin:6px 0 0 20px;padding:0">
<li><b>历史原因 &gt; 研究原因。</b>这个策略是「聚宽顶流小微盘模型」的本土化复刻，聚宽社区模板的标准设定就是双周轮动，freq=10 是跟着模板进来的。本项目此前只做过 <b>N 的敏感度</b>（3/5/6/7/8/10/15/20/30，见线上 sensitivity_table），<b>从没做过频率敏感度</b>——所以「两周」不是一个被验证过的选择。</li>
<li><b>它落在「能活」的区间，但不在好的位置。</b>频率 ≤7 天时成本吃光收益（TEST 段 freq=5 只剩 4.78%，freq=1 是 −15.92%），7 天以上才转正。10 天是刚过生死线的保守位置。</li>
<li><b>实操上确实友好。</b>双周 = 一年约 25 次调仓，手工跟单可行。</li>
</ol>

<p style="margin-top:14px"><b>② 机理：这个信号根本不衰减，两周调仓是在白白交手续费</b></p>
<p style="margin:6px 0 0">Rank IC 随持有期<b>单调上升</b>，到 h≈60~90 个交易日才饱和（IC 0.155 / ICIR 1.15），h=5 时 IC 只有 0.082 —— 不到峰值的 60%。
合成信号里 rev5（5 日反转）权重只占 25%，主体是 liqsize20（小盘规模）和 ivol60（低特质波动），这两个都是<b>慢变量</b>。
慢信号 ⇒ 提前调仓换不来新信息，只换来换手和成本。这是低频占优的根因，不是数据巧合。</p>

<p style="margin-top:14px"><b>③ 该不该改：改，但只改到月频，不要一步跳到季频</b></p>
<ul style="margin:6px 0 0 20px;padding:0">
<li><b>改到 20（月频）是稳的，但别指望它增厚 alpha。</b>它是锁死目标函数在 TRAIN/VALID 上唯一选出的频率；揭盲后 TEST 年化 {te_cagr[freqs.index(10)]}% → {te_cagr[freqs.index(20)]}%，夏普 0.450 → 0.623，回撤 −41.17% → −35.10%，年换手 44.8x → 23.7x（成本 6.76% → 3.57%），一年调仓 25 → 12 次。
但换成标准基准后，freq=20 对可投资宇宙等权的 alpha 是 8.46%/年、t(NW)=0.77、p=0.44 —— <b>不显著</b>。所以这次改动的价值是<b>少交手续费、少做无意义的换手</b>，不是选股变强了。</li>
<li><b>60（季频）是唯一「两个独立检验都过线」的频率，但仍不足以直接上线。</b>
对可投资宇宙等权的 alpha 24.05%/年、<b>t(NW)=2.50、p=0.012</b>；置换检验分位 98%、p=0.025。两条互不相关的证据同时指向它，这比单纯年化高有分量得多。
可是：TEST 段它<b>只调仓 11 次</b>；整个研究扫了 12 个频率，Bonferroni 折减后 p ≈ 0.14 → 又不显著了；TRAIN/VALID 的目标函数也没选它。</li>
<li><b>30（一个半月）是折中候选</b>：TEST 年化 27.10%、夏普 0.958、回撤 −24.18%、归因 t=1.58（p=0.115）、置换分位 0.91（p=0.095）——两个检验都卡在边缘，方向一致但都没过线。</li>
</ul>
<p style="margin:10px 0 0"><b>落地建议：freq 10 → 20 直接改；同时把 60 开一路纸面跟踪。</b>20 是三段切分 + 稳健性网格下唯一站得住的改动；60 是唯一在标准基准下有显著 alpha 迹象的频率，值得用未来 12~24 个月的实盘样本去验证，而不是现在就压上去。</p>

<p style="margin-top:14px"><b>④ 比频率更该改的：buffer 根本没生效</b></p>
<p style="margin:6px 0 0">N=7、buffer=2.0 意味着前 14 名不卖。但实测每次调仓变动 <b>约 13 只</b>（≈ 持仓 7 只全进全出），滞后带形同虚设——rev5 让综合排名每天都在跳，14 名的缓冲区兜不住。
加大 buffer（3.0~4.0）或降低 rev5 权重，能同时拿到「更少换手 + 不损失打分」，这个收益比调频率更确定。</p>

<p style="margin-top:14px"><b>⑤ 一句话</b></p>
<p style="margin:6px 0 0">两周是模板默认值，不是研究结论；这个信号是慢信号，两周太频繁了。放到 <b>20 个交易日（月频）</b>是本研究唯一在三段切分 + 揭盲 + 稳健性网格下都站得住的改动——它的作用是<b>省钱</b>，不是变聪明：换成标准可交易基准后，这条策略在月频下的选股 alpha 仍然统计上不显著，收益大头是微盘 beta。</p>
</div>

<script>
var F = {json.dumps(freqs)};
function mk(id, opt){{var el=document.getElementById(id);var c=echarts.init(el);c.setOption(opt);window.addEventListener('resize',function(){{c.resize()}});}}
var AX = {{type:'category',data:F,name:'调仓频率(交易日)',nameLocation:'middle',nameGap:28}};
var GRID = {{left:60,right:30,top:50,bottom:50}};

mk('c_ic', {{
  tooltip:{{trigger:'axis'}},legend:{{top:0}},grid:GRID,
  xAxis:{{type:'category',data:{json.dumps(ic_h)},name:'持有期 h(交易日)',nameLocation:'middle',nameGap:28}},
  yAxis:[{{type:'value',name:'IC 均值'}},{{type:'value',name:'ICIR'}}],
  series:[
    {{name:'IC 均值',type:'line',data:{json.dumps(ic_mean)},smooth:true,itemStyle:{{color:'#2563eb'}},lineStyle:{{color:'#2563eb',width:3}},symbolSize:6}},
    {{name:'ICIR',type:'line',yAxisIndex:1,data:{json.dumps(ic_ir)},smooth:true,itemStyle:{{color:'#d93025'}},lineStyle:{{color:'#d93025',width:2}},symbolSize:5}}
  ]
}});

mk('c_cagr', {{
  tooltip:{{trigger:'axis'}},legend:{{top:0}},grid:GRID,
  xAxis:AX, yAxis:{{type:'value',name:'年化收益 %'}},
  series:[
    {{name:'TRAIN 2016-2021',type:'line',data:{json.dumps(tr_cagr)},itemStyle:{{color:'#9ca3af'}},lineStyle:{{color:'#9ca3af'}},symbolSize:5}},
    {{name:'VALID 2022-2023',type:'line',data:{json.dumps(va_cagr)},itemStyle:{{color:'#2563eb'}},lineStyle:{{color:'#2563eb',width:2}},symbolSize:6}},
    {{name:'TEST 2024-2026（揭盲）',type:'line',data:{json.dumps(te_cagr)},itemStyle:{{color:'#0f9960'}},lineStyle:{{color:'#0f9960',width:3}},symbolSize:7}},
    {{name:'0 线',type:'line',data:new Array(F.length).fill(0),lineStyle:{{color:'#d1d5db',type:'dashed'}},symbol:'none',silent:true}}
  ]
}});

mk('c_sr', {{
  tooltip:{{trigger:'axis'}},legend:{{top:0}},grid:GRID,
  xAxis:AX, yAxis:{{type:'value',name:'夏普'}},
  series:[
    {{name:'TRAIN',type:'line',data:{json.dumps(tr_sr)},itemStyle:{{color:'#9ca3af'}},lineStyle:{{color:'#9ca3af'}},symbolSize:5}},
    {{name:'VALID',type:'line',data:{json.dumps(va_sr)},itemStyle:{{color:'#2563eb'}},lineStyle:{{color:'#2563eb',width:2}},symbolSize:6}},
    {{name:'TEST（揭盲）',type:'line',data:{json.dumps(te_sr)},itemStyle:{{color:'#0f9960'}},lineStyle:{{color:'#0f9960',width:3}},symbolSize:7}}
  ]
}});

mk('c_cost', {{
  tooltip:{{trigger:'axis'}},legend:{{top:0}},grid:GRID,
  xAxis:AX, yAxis:{{type:'value',name:'% / 年'}},
  series:[
    {{name:'毛年化 %',type:'bar',data:{json.dumps(te_gross)},itemStyle:{{color:'#93c5fd'}}}},
    {{name:'成本（拖累）%',type:'bar',data:{json.dumps([-c for c in te_cost])},itemStyle:{{color:'#d93025'}}}},
    {{name:'净年化 %',type:'line',data:{json.dumps(te_cagr)},itemStyle:{{color:'#0f9960'}},lineStyle:{{color:'#0f9960',width:3}},symbolSize:7}}
  ]
}});

mk('c_perm', {{
  tooltip:{{trigger:'axis'}},legend:{{top:0}},grid:GRID,
  xAxis:{{type:'category',data:{json.dumps(p_freq)},name:'调仓频率(交易日)',nameLocation:'middle',nameGap:28}},
  yAxis:[{{type:'value',name:'TEST 年化 %'}},{{type:'value',name:'分位',min:0,max:1}}],
  series:[
    {{name:'真实策略',type:'bar',data:{json.dumps(p_real)},itemStyle:{{color:'#0f9960'}}}},
    {{name:'随机组合均值',type:'bar',data:{json.dumps(p_rand)},itemStyle:{{color:'#d1d5db'}}}},
    {{name:'随机组合 P95',type:'line',data:{json.dumps(p_p95)},itemStyle:{{color:'#d93025'}},lineStyle:{{color:'#d93025',type:'dashed',width:2}},symbolSize:6}},
    {{name:'真实所处分位(右轴)',type:'line',yAxisIndex:1,data:{json.dumps(p_frac)},itemStyle:{{color:'#7c3aed'}},lineStyle:{{color:'#7c3aed',width:2}},symbolSize:6}}
  ]
}});

mk('c_attrib', {{
  tooltip:{{trigger:'axis'}},legend:{{top:0}},grid:GRID,
  xAxis:{{type:'category',data:{json.dumps(at_freqs)},name:'调仓频率(交易日)',nameLocation:'middle',nameGap:28}},
  yAxis:{{type:'value',name:'alpha 的 t 值 (NW)'}},
  series:[
    {{name:'vs 沪深300',type:'line',data:{json.dumps(at_t['沪深300'])},itemStyle:{{color:'#2563eb'}},lineStyle:{{color:'#2563eb',width:2}},symbolSize:6}},
    {{name:'vs 可投资宇宙等权',type:'line',data:{json.dumps(at_t['可投资宇宙等权'])},itemStyle:{{color:'#0f9960'}},lineStyle:{{color:'#0f9960',width:3}},symbolSize:7}},
    {{name:'vs 全市场等权',type:'line',data:{json.dumps(at_t['全市场等权'])},itemStyle:{{color:'#f59e0b'}},lineStyle:{{color:'#f59e0b',width:2}},symbolSize:6}},
    {{name:'vs 沪深300+宇宙等权',type:'line',data:{json.dumps(at_t['双因子'])},itemStyle:{{color:'#7c3aed'}},lineStyle:{{color:'#7c3aed',width:2}},symbolSize:6}},
    {{name:'t=1.96 显著线',type:'line',data:new Array({json.dumps(at_freqs)}.length).fill(1.96),lineStyle:{{color:'#d93025',type:'dashed'}},symbol:'none',silent:true}},
    {{name:'t=0',type:'line',data:new Array({json.dumps(at_freqs)}.length).fill(0),lineStyle:{{color:'#d1d5db',type:'dashed'}},symbol:'none',silent:true}}
  ]
}});

mk('c_liq', {{
  tooltip:{{trigger:'axis'}},legend:{{top:0}},grid:GRID,
  xAxis:{{type:'category',data:{json.dumps(a_pct)},name:'liq_top_pct（保留前 X%）',nameLocation:'middle',nameGap:28}},
  yAxis:[{{type:'value',name:'TEST 年化 %'}},{{type:'value',name:'池内股票数'}}],
  series:[
    {{name:'freq=10 年化%',type:'bar',data:{json.dumps(a_byf.get(10, []))},itemStyle:{{color:'#93c5fd'}}}},
    {{name:'freq=20 年化%',type:'bar',data:{json.dumps(a_byf.get(20, []))},itemStyle:{{color:'#34d399'}}}},
    {{name:'freq=60 年化%',type:'bar',data:{json.dumps(a_byf.get(60, []))},itemStyle:{{color:'#0f9960'}}}},
    {{name:'池内股票中位数',type:'line',yAxisIndex:1,data:{json.dumps(a_pool)},itemStyle:{{color:'#d93025'}},lineStyle:{{color:'#d93025',width:2}},symbolSize:6}}
  ]
}});

mk('c_buf', {{
  tooltip:{{trigger:'axis'}},legend:{{top:0}},grid:GRID,
  xAxis:{{type:'category',data:{json.dumps(b_buf)},name:'buffer（1.0 = 不缓冲）',nameLocation:'middle',nameGap:28}},
  yAxis:[{{type:'value',name:'每期变动只数'}},{{type:'value',name:'TEST 年化 %'}}],
  series:[
    {{name:'变动只数 freq=10',type:'line',data:{json.dumps(b_churn.get(10, []))},itemStyle:{{color:'#2563eb'}},lineStyle:{{color:'#2563eb',width:2}},symbolSize:6}},
    {{name:'变动只数 freq=20',type:'line',data:{json.dumps(b_churn.get(20, []))},itemStyle:{{color:'#7c3aed'}},lineStyle:{{color:'#7c3aed',width:2}},symbolSize:6}},
    {{name:'TEST 年化% freq=10',type:'bar',yAxisIndex:1,data:{json.dumps(b_cagr.get(10, []))},itemStyle:{{color:'#bfdbfe'}}}},
    {{name:'TEST 年化% freq=20',type:'bar',yAxisIndex:1,data:{json.dumps(b_cagr.get(20, []))},itemStyle:{{color:'#6ee7b7'}}}}
  ]
}});

mk('c_turn', {{
  tooltip:{{trigger:'axis'}},legend:{{top:0}},grid:GRID,
  xAxis:AX,
  yAxis:[{{type:'value',name:'年换手 x'}},{{type:'value',name:'每期变动只数'}}],
  series:[
    {{name:'年换手 x',type:'bar',data:{json.dumps(te_to)},itemStyle:{{color:'#fbbf24'}}}},
    {{name:'每期变动只数（N=7）',type:'line',yAxisIndex:1,data:{json.dumps(churn)},itemStyle:{{color:'#7c3aed'}},lineStyle:{{color:'#7c3aed',width:2}},symbolSize:6}}
  ]
}});
</script>
</div></body></html>"""


def main():
    d = load()
    html = build(d)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print("报告已写入", OUT)


if __name__ == "__main__":
    main()
