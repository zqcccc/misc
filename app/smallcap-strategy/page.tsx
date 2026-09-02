'use client'

import React, { useEffect, useMemo, useRef, useState } from 'react'

function fmtPct(v: number | undefined | null, digits = 2): string {
  if (v == null || Number.isNaN(v)) return '-'
  const sign = v > 0 ? '+' : ''
  return `${sign}${v.toFixed(digits)}%`
}

function fmtNum(v: number | undefined | null, digits = 2): string {
  if (v == null || Number.isNaN(v)) return '-'
  return v.toFixed(digits)
}

/**
 * 根据不同板块真实交易规则计算建议股数
 * - 主板 (60/00) & 创业板 (30): 单笔委托必须是 100 股 (1手) 整数倍
 * - 科创板 (688): 单笔委托起购不小于 200 股，超过 200 股后可以以 1 股为单位递增
 */
function getBoardExecution(code: string, targetValYuan: number, price: number, roundToHundredForKcb = false) {
  if (price <= 0) return { shares: 0, label: '-', sub: '', isKcb: false }
  
  const isKcb = code.startsWith('sh688') || code.startsWith('688')
  
  if (isKcb) {
    if (roundToHundredForKcb) {
      // 若选择整百股
      const hands = Math.floor(targetValYuan / (price * 100))
      const shares = hands * 100
      if (shares < 200) {
        return { shares: 0, label: '不足200股起购', sub: '科创板门槛≥200股', isKcb: true }
      }
      return {
        shares,
        label: `${shares.toLocaleString()} 股 (${hands} 手)`,
        sub: '科创板·整百股委托',
        isKcb: true,
      }
    } else {
      // 科创板精准规则：>=200股起，1股递增
      const exactShares = Math.floor(targetValYuan / price)
      if (exactShares < 200) {
        return { shares: 0, label: '不足200股起购', sub: '科创板门槛≥200股', isKcb: true }
      }
      return {
        shares: exactShares,
        label: `${exactShares.toLocaleString()} 股`,
        sub: '科创板·1股递增规则',
        isKcb: true,
      }
    }
  } else {
    // 主板与创业板：整百股 (1手)
    const hands = Math.floor(targetValYuan / (price * 100))
    const shares = hands * 100
    if (shares < 100) {
      return { shares: 0, label: '不足1手 (100股)', sub: '主板/创业板门槛', isKcb: false }
    }
    return {
      shares,
      label: `${hands} 手 (${shares.toLocaleString()} 股)`,
      sub: '整手 (100股整数倍)',
      isKcb: false,
    }
  }
}

export default function SmallCapStrategyPage() {
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  
  // 选中的持仓只数配置: 默认打开推荐 7 只组合 (收益之王)
  const [activeN, setActiveN] = useState<'8' | '7' | '6' | '5' | '10' | '30'>('7')
  
  // 自定义实操本金（万元），默认 50 万元
  const [capitalWan, setCapitalWan] = useState<number>(50)

  // 科创板是否取整百股 (方便部分交易软件委托)
  const [roundKcbHundred, setRoundKcbHundred] = useState(false)

  const [searchKey, setSearchKey] = useState('')
  const [sortField, setSortField] = useState<'float_cap_billion' | 'price' | 'change_pct' | 'factor_score'>('float_cap_billion')
  const [sortAsc, setSortAsc] = useState(true)

  const equityChartRef = useRef<HTMLDivElement>(null)
  const drawdownChartRef = useRef<HTMLDivElement>(null)
  const capChartRef = useRef<HTMLDivElement>(null)
  const chartInstance1 = useRef<any>(null)
  const chartInstance2 = useRef<any>(null)
  const chartInstance3 = useRef<any>(null)

  useEffect(() => {
    fetch('/api/smallcap-strategy')
      .then((res) => res.json())
      .then((json) => {
        if (json.success) {
          setData(json.data)
        } else {
          setError(json.error || '获取数据失败')
        }
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  // 当前选中配置的数据
  const curConfig = useMemo(() => {
    if (!data || !data.configs) return null
    return data.configs[activeN] || data.configs['8'] || data.configs['30']
  }, [data, activeN])

  // 渲染 ECharts
  useEffect(() => {
    if (!curConfig || !curConfig.equity_curve) return

    const curve = curConfig.equity_curve
    const dates = curve.map((c: any) => c.date)
    const stratNav = curve.map((c: any) => c.strategy_nav)
    const hs300Nav = curve.map((c: any) => c.hs300_nav)
    const allANav = curve.map((c: any) => c.all_a_nav)
    const stratDD = curve.map((c: any) => c.strategy_drawdown)
    const hs300DD = curve.map((c: any) => c.hs300_drawdown)

    import('echarts').then((echarts) => {
      // 1. 净值曲线
      if (equityChartRef.current) {
        if (!chartInstance1.current) {
          chartInstance1.current = echarts.init(equityChartRef.current)
        }
        const option1 = {
          title: {
            text: `累计净值走势 (持仓 ${activeN} 只配置 | 2019 ~ 2026 最新)`,
            textStyle: { fontSize: 13, fontWeight: 'bold' },
            left: 10,
          },
          tooltip: {
            trigger: 'axis',
            formatter: (params: any[]) => {
              if (!params.length) return ''
              let tip = `<div class="font-medium mb-1">${params[0].axisValue}</div>`
              params.forEach((p) => {
                tip += `<div class="flex items-center justify-between gap-4 text-xs">
                  <span>${p.marker} ${p.seriesName}</span>
                  <span class="font-semibold">${p.value}</span>
                </div>`
              })
              return tip
            },
          },
          legend: { data: [`小微盘(${activeN}只)`, '全A等权基准', '沪深300ETF'], top: 10, right: 20 },
          grid: { left: '3%', right: '4%', bottom: '15%', top: '15%', containLabel: true },
          xAxis: { type: 'category', data: dates, boundaryGap: false },
          yAxis: {
            type: 'value',
            scale: true,
            axisLabel: { formatter: '{value}' },
            splitLine: { lineStyle: { type: 'dashed', opacity: 0.2 } },
          },
          dataZoom: [{ type: 'inside' }, { type: 'slider', bottom: '2%' }],
          series: [
            {
              name: `小微盘(${activeN}只)`,
              type: 'line',
              data: stratNav,
              smooth: true,
              showSymbol: false,
              lineStyle: { color: '#f59e0b', width: 2.5 },
              itemStyle: { color: '#f59e0b' },
            },
            {
              name: '全A等权基准',
              type: 'line',
              data: allANav,
              smooth: true,
              showSymbol: false,
              lineStyle: { color: '#38bdf8', width: 1.5, type: 'dashed' },
              itemStyle: { color: '#38bdf8' },
            },
            {
              name: '沪深300ETF',
              type: 'line',
              data: hs300Nav,
              smooth: true,
              showSymbol: false,
              lineStyle: { color: '#94a3b8', width: 1.5, type: 'dashed' },
              itemStyle: { color: '#94a3b8' },
            },
          ],
        }
        chartInstance1.current.setOption(option1)
      }

      // 2. 水下回撤
      if (drawdownChartRef.current) {
        if (!chartInstance2.current) {
          chartInstance2.current = echarts.init(drawdownChartRef.current)
        }
        const option2 = {
          title: {
            text: `动态水下回撤 % (持仓 ${activeN} 只配置 | 标红为 2024 初踩踏)`,
            textStyle: { fontSize: 13, fontWeight: 'bold' },
            left: 10,
          },
          tooltip: {
            trigger: 'axis',
            formatter: (params: any[]) => {
              if (!params.length) return ''
              let tip = `<div class="font-medium mb-1">${params[0].axisValue}</div>`
              params.forEach((p) => {
                tip += `<div class="flex items-center justify-between gap-4 text-xs">
                  <span>${p.marker} ${p.seriesName}</span>
                  <span class="font-semibold">${p.value}%</span>
                </div>`
              })
              return tip
            },
          },
          legend: { data: ['小微盘回撤', '沪深300回撤'], top: 10, right: 20 },
          grid: { left: '3%', right: '4%', bottom: '15%', top: '18%', containLabel: true },
          xAxis: { type: 'category', data: dates, boundaryGap: false },
          yAxis: {
            type: 'value',
            max: 0,
            axisLabel: { formatter: '{value}%' },
            splitLine: { lineStyle: { type: 'dashed', opacity: 0.2 } },
          },
          dataZoom: [{ type: 'inside' }, { type: 'slider', bottom: '2%' }],
          series: [
            {
              name: '小微盘回撤',
              type: 'line',
              data: stratDD,
              areaStyle: { color: 'rgba(245, 158, 11, 0.25)' },
              lineStyle: { color: '#f59e0b', width: 1.5 },
              showSymbol: false,
              markArea: {
                itemStyle: { color: 'rgba(239, 68, 68, 0.15)' },
                data: [
                  [
                    { name: '2024初微盘踩踏雪崩', xAxis: '2024-01-02' },
                    { xAxis: '2024-02-28' },
                  ],
                ],
              },
            },
            {
              name: '沪深300回撤',
              type: 'line',
              data: hs300DD,
              areaStyle: { color: 'rgba(148, 163, 184, 0.15)' },
              lineStyle: { color: '#94a3b8', width: 1.2, type: 'dashed' },
              showSymbol: false,
            },
          ],
        }
        chartInstance2.current.setOption(option2)
      }

      // 3. 市值分布柱状图
      if (capChartRef.current && curConfig.cap_distribution) {
        if (!chartInstance3.current) {
          chartInstance3.current = echarts.init(capChartRef.current)
        }
        const cap = curConfig.cap_distribution
        const option3 = {
          title: { text: `当前持仓流通市值分布 (${activeN}只标的)`, textStyle: { fontSize: 13, fontWeight: 'bold' }, left: 10 },
          tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
          grid: { left: '3%', right: '4%', bottom: '10%', top: '20%', containLabel: true },
          xAxis: {
            type: 'category',
            data: ['< 20亿', '20 ~ 30亿', '30 ~ 50亿', '≥ 50亿'],
          },
          yAxis: { type: 'value', minInterval: 1, splitLine: { lineStyle: { type: 'dashed', opacity: 0.2 } } },
          series: [
            {
              name: '持股只数',
              type: 'bar',
              data: [cap.under_20b, cap.between_20_30b, cap.between_30_50b, cap.above_50b],
              barWidth: '40%',
              itemStyle: {
                color: (params: any) => {
                  const colors = ['#10b981', '#f59e0b', '#3b82f6', '#8b5cf6']
                  return colors[params.dataIndex % colors.length]
                },
                borderRadius: [4, 4, 0, 0],
              },
            },
          ],
        }
        chartInstance3.current.setOption(option3)
      }
    })

    const handleResize = () => {
      chartInstance1.current?.resize()
      chartInstance2.current?.resize()
      chartInstance3.current?.resize()
    }
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [curConfig, activeN])

  // 排序与搜索持仓
  const filteredHoldings = useMemo(() => {
    if (!curConfig || !curConfig.current_holdings) return []
    let list = [...curConfig.current_holdings]
    if (searchKey.trim()) {
      const q = searchKey.trim().toLowerCase()
      list = list.filter(
        (h) =>
          h.name.toLowerCase().includes(q) ||
          h.code.toLowerCase().includes(q) ||
          h.display_code.includes(q)
      )
    }
    list.sort((a, b) => {
      const va = a[sortField] || 0
      const vb = b[sortField] || 0
      return sortAsc ? va - vb : vb - va
    })
    return list
  }, [curConfig, searchKey, sortField, sortAsc])

  const handleSort = (field: typeof sortField) => {
    if (sortField === field) {
      setSortAsc(!sortAsc)
    } else {
      setSortField(field)
      setSortAsc(true)
    }
  }

  if (loading) {
    return (
      <div className="flex h-96 items-center justify-center text-gray-500">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-amber-500 mr-3"></div>
        正在加载聚宽小微盘策略多持仓配置与实操回测指标...
      </div>
    )
  }

  if (error || !data || !curConfig) {
    return (
      <div className="p-8 max-w-4xl mx-auto text-rose-500 bg-rose-50 rounded-xl border border-rose-200">
        加载失败: {error || '暂无小微盘策略数据'}
      </div>
    )
  }

  const m = curConfig.metrics || {}
  const cap = curConfig.cap_distribution || {}
  const holdings = curConfig.current_holdings || []
  const rbHistory = curConfig.rebalance_history || []
  const sensitivity = data.sensitivity_table || []

  // 当前模拟总资金 (元)
  const totalCapitalYuan = (capitalWan || 50) * 10000

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 space-y-8 font-sans">
      {/* 头部标题与严谨因果声明 */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b pb-6 dark:border-gray-800">
        <div>
          <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full text-xs font-medium bg-amber-50 text-amber-800 dark:bg-amber-950/50 dark:text-amber-300 mb-2 border border-amber-200 dark:border-amber-800">
            <span>⚡ 聚宽 (JoinQuant) 顶流小市值微利轮动</span>
            <span>•</span>
            <span>实操持仓宽度实测</span>
            <span>•</span>
            <span>严格 T+1 撮合</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-gray-900 dark:text-gray-100 flex items-center gap-2">
            <span>📦</span> {data.strategy_name}
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            小市值规模 (1.0) + 短期反转防追高 (0.5) + 低特质波动 (0.5) | 最新调仓日: <span className="font-semibold text-gray-800 dark:text-gray-200">{data.latest_rebalance_date}</span>
          </p>
        </div>

        {/* 核心持仓数量切换 Tab */}
        <div className="flex flex-col items-start md:items-end gap-1.5">
          <div className="text-xs font-semibold text-gray-500 dark:text-gray-400">选择实操持仓只数:</div>
          <div className="flex flex-wrap bg-gray-100 dark:bg-gray-800 p-1 rounded-lg gap-1">
            <button
              onClick={() => setActiveN('7')}
              className={`px-2.5 py-1.5 text-xs font-bold rounded-md transition flex items-center gap-1 ${
                activeN === '7'
                  ? 'bg-amber-500 text-white shadow-sm'
                  : 'text-gray-600 dark:text-gray-300 hover:text-gray-900'
              }`}
            >
              <span>⭐ 7 只</span>
              <span className="text-[10px] font-normal opacity-90">(首推·收益最高)</span>
            </button>
            <button
              onClick={() => setActiveN('8')}
              className={`px-2.5 py-1.5 text-xs font-medium rounded-md transition flex items-center gap-1 ${
                activeN === '8'
                  ? 'bg-amber-500 text-white shadow-sm'
                  : 'text-gray-600 dark:text-gray-300 hover:text-gray-900'
              }`}
            >
              <span>8 只</span>
              <span className="text-[10px] opacity-75">(回撤平衡)</span>
            </button>
            <button
              onClick={() => setActiveN('6')}
              className={`px-2.5 py-1.5 text-xs font-medium rounded-md transition ${
                activeN === '6'
                  ? 'bg-amber-500 text-white shadow-sm'
                  : 'text-gray-600 dark:text-gray-300 hover:text-gray-900'
              }`}
            >
              6 只
            </button>
            <button
              onClick={() => setActiveN('5')}
              className={`px-2.5 py-1.5 text-xs font-medium rounded-md transition flex items-center gap-1 ${
                activeN === '5'
                  ? 'bg-amber-500 text-white shadow-sm'
                  : 'text-gray-600 dark:text-gray-300 hover:text-gray-900'
              }`}
            >
              <span>5 只</span>
              <span className="text-[10px] opacity-75">(高集中)</span>
            </button>
            <button
              onClick={() => setActiveN('10')}
              className={`px-2.5 py-1.5 text-xs font-medium rounded-md transition ${
                activeN === '10'
                  ? 'bg-amber-500 text-white shadow-sm'
                  : 'text-gray-600 dark:text-gray-300 hover:text-gray-900'
              }`}
            >
              10 只
            </button>
            <button
              onClick={() => setActiveN('30')}
              className={`px-2.5 py-1.5 text-xs font-medium rounded-md transition ${
                activeN === '30'
                  ? 'bg-amber-500 text-white shadow-sm'
                  : 'text-gray-600 dark:text-gray-300 hover:text-gray-900'
              }`}
            >
              30 只
            </button>
          </div>
        </div>
      </div>

      {/* 核心指标卡片矩阵 (根据选中 N 动态展示) */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <div className="p-4 rounded-xl border bg-white dark:bg-gray-900/60 dark:border-gray-800 shadow-sm">
          <div className="text-xs text-gray-500 dark:text-gray-400">年化收益 (CAGR)</div>
          <div className="text-xl font-bold text-amber-600 dark:text-amber-400 mt-1">
            {fmtPct(m.cagr_pct)}
          </div>
          <div className="text-xs text-gray-400 mt-1">总收益: {fmtPct(m.total_return_pct)}</div>
        </div>

        <div className="p-4 rounded-xl border bg-white dark:bg-gray-900/60 dark:border-gray-800 shadow-sm">
          <div className="text-xs text-gray-500 dark:text-gray-400">日夏普比率 (Rf=2%)</div>
          <div className="text-xl font-bold text-indigo-600 dark:text-indigo-400 mt-1">
            {fmtNum(m.daily_sharpe)}
          </div>
          <div className="text-xs text-gray-400 mt-1">日资金曲线年化</div>
        </div>

        <div className="p-4 rounded-xl border bg-white dark:bg-gray-900/60 dark:border-gray-800 shadow-sm">
          <div className="text-xs text-gray-500 dark:text-gray-400">全期最大回撤</div>
          <div className="text-xl font-bold text-rose-600 dark:text-rose-400 mt-1">
            {fmtPct(m.max_drawdown_pct)}
          </div>
          <div className="text-xs text-gray-400 mt-1">历史最深下潜</div>
        </div>

        <div className="p-4 rounded-xl border border-rose-200 dark:border-rose-900/40 bg-rose-50/30 dark:bg-rose-950/10 shadow-sm">
          <div className="text-xs text-rose-700 dark:text-rose-400 font-medium">⚠️ 2024初踩踏期回撤</div>
          <div className="text-xl font-bold text-rose-600 dark:text-rose-400 mt-1">
            {fmtPct(m.crash_2024_mdd_pct)}
          </div>
          <div className="text-xs text-rose-500/80 mt-1">微盘流动性极端挤兑</div>
        </div>

        <div className="p-4 rounded-xl border bg-white dark:bg-gray-900/60 dark:border-gray-800 shadow-sm">
          <div className="text-xs text-gray-500 dark:text-gray-400">年化超额 Alpha</div>
          <div className="text-xl font-bold text-emerald-600 dark:text-emerald-400 mt-1">
            {fmtPct(m.alpha_annual_pct)}
          </div>
          <div className="text-xs text-gray-400 mt-1">NW t = {fmtNum(m.alpha_t_nw)}</div>
        </div>

        <div className="p-4 rounded-xl border bg-white dark:bg-gray-900/60 dark:border-gray-800 shadow-sm">
          <div className="text-xs text-gray-500 dark:text-gray-400">单只目标仓位</div>
          <div className="text-xl font-bold text-sky-600 dark:text-sky-400 mt-1">
            {curConfig.target_weight_per_stock}%
          </div>
          <div className="text-xs text-gray-400 mt-1">年化换手: {fmtNum(m.annual_turnover, 1)}x</div>
        </div>
      </div>

      {/* 专设模块：持仓数量灵敏度与实操选型矩阵 (已完整包含 6 和 7) */}
      <div className="rounded-xl border bg-white dark:bg-gray-900/60 dark:border-gray-800 shadow-sm p-5 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b pb-3 dark:border-gray-800">
          <div>
            <h2 className="text-base font-bold text-gray-900 dark:text-gray-100 flex items-center gap-2">
              <span>🔬</span> 持仓数量 N 敏感性对比与实操选型矩阵 (严谨回测)
            </h2>
            <p className="text-xs text-gray-500 mt-0.5">
              回测覆盖 2019-2026 全时段，内生印花税、佣金与滑点，特别考核 2024 年初极端踩踏抗击力（点击任意行可直接切换看板）
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs px-2.5 py-1 rounded bg-amber-50 text-amber-700 dark:bg-amber-950 dark:text-amber-300 font-medium">
              推荐配置: ⭐ 7 只 (默认首推·全场收益最高) 或 8 只 (防守回撤最佳)
            </span>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-xs text-left">
            <thead className="bg-gray-50 dark:bg-gray-800/60 text-gray-500 dark:text-gray-400 border-y dark:border-gray-800">
              <tr>
                <th className="py-2.5 px-3">持仓只数 (N)</th>
                <th className="py-2.5 px-3">单只仓位</th>
                <th className="py-2.5 px-3">年化收益 (CAGR)</th>
                <th className="py-2.5 px-3">日夏普比率</th>
                <th className="py-2.5 px-3">全期最大回撤</th>
                <th className="py-2.5 px-3">2024初踩踏回撤</th>
                <th className="py-2.5 px-3">年化换手率</th>
                <th className="py-2.5 px-3">纯 Alpha (NW t)</th>
                <th className="py-2.5 px-3">蒙卡P5极端尾部</th>
                <th className="py-2.5 px-3">综合实操评价</th>
              </tr>
            </thead>
            <tbody className="divide-y dark:divide-gray-800/60">
              {sensitivity.map((row: any) => {
                const isCurrent = row.N === Number(activeN)
                const isRec = row.is_recommended
                const isTop = row.is_top_cagr
                const isClickable = ['5', '6', '7', '8', '10', '30'].includes(String(row.N))
                return (
                  <tr
                    key={row.N}
                    onClick={() => {
                      if (isClickable) {
                        setActiveN(String(row.N) as any)
                      }
                    }}
                    className={`transition-colors ${isClickable ? 'cursor-pointer' : 'cursor-default'} ${
                      isCurrent
                        ? 'bg-amber-50 dark:bg-amber-950/30 font-semibold'
                        : 'hover:bg-gray-50 dark:hover:bg-gray-800/40'
                    }`}
                  >
                    <td className="py-2.5 px-3 font-mono flex items-center gap-1.5">
                      {isRec ? (
                        <span className="text-amber-500">★</span>
                      ) : isTop ? (
                        <span className="text-emerald-500">🔥</span>
                      ) : null}
                      <span>{row.N} 只</span>
                      {isRec && (
                        <span className="text-[10px] px-1 py-0.2 rounded bg-amber-100 text-amber-800 dark:bg-amber-900/60 dark:text-amber-300 font-normal">
                          推荐平衡
                        </span>
                      )}
                      {isTop && (
                        <span className="text-[10px] px-1 py-0.2 rounded bg-emerald-100 text-emerald-800 dark:bg-emerald-900/60 dark:text-emerald-300 font-normal">
                          收益最高
                        </span>
                      )}
                    </td>
                    <td className="py-2.5 px-3 font-mono text-gray-500">
                      {(100.0 / row.N).toFixed(1)}%
                    </td>
                    <td className={`py-2.5 px-3 font-mono ${isTop ? 'text-emerald-600 dark:text-emerald-400 font-bold' : 'text-amber-600 dark:text-amber-400'}`}>
                      {fmtPct(row.cagr_pct)}
                    </td>
                    <td className="py-2.5 px-3 font-mono text-indigo-600 dark:text-indigo-400">
                      {fmtNum(row.daily_sharpe)}
                    </td>
                    <td className="py-2.5 px-3 font-mono text-rose-600 dark:text-rose-400">
                      {fmtPct(row.max_drawdown_pct)}
                    </td>
                    <td className="py-2.5 px-3 font-mono font-bold text-rose-700 dark:text-rose-300">
                      {fmtPct(row.crash_2024_mdd_pct)}
                    </td>
                    <td className="py-2.5 px-3 font-mono text-gray-500">
                      {fmtNum(row.annual_turnover, 1)}x
                    </td>
                    <td className="py-2.5 px-3 font-mono text-emerald-600 dark:text-emerald-400">
                      {fmtPct(row.alpha_annual_pct)} (t={fmtNum(row.alpha_t_nw)})
                    </td>
                    <td className="py-2.5 px-3 font-mono">
                      <span className={row.mc_p5 >= 1.0 ? 'text-emerald-600 font-bold' : 'text-rose-600'}>
                        {fmtNum(row.mc_p5)}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-gray-600 dark:text-gray-300">
                      {row.assessment}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>

        {/* 选型依据说明 */}
        <div className="p-3.5 rounded-lg bg-amber-50/50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-900/40 text-xs text-amber-900 dark:text-amber-200 leading-relaxed space-y-1.5">
          <div className="font-bold flex items-center gap-1.5">
            <span>💡</span> 实操选型建议：6 只、7 只 还是 8 只？
          </div>
          <div>
            • <strong>如果您最看重绝对年化收益与爆发力</strong>：选 <strong>7 只 (N=7)</strong>。年化复合收益达 <strong>21.01%</strong> 为全场最高峰，纯 Alpha 达 10.32% (NW t=1.79)，蒙卡 P5 达 1.12；
          </div>
          <div>
            • <strong>如果您更看重在极端黑天鹅行情下的回撤控制</strong>：选 <strong>8 只 (N=8)</strong>。年化收益保持 20.65% 的同时，将 2024 年初极端踩踏回撤从 7 只的 -47.43% 进一步压低至 <strong>-44.61%</strong>，夏普最高 (0.831)；
          </div>
          <div>
            • <strong>6 只 (N=6)</strong> 虽然年化高达 20.99%，但 2024 初踩踏下杀达 <strong>-49.44%</strong>（全期回撤 -52.04%），性价比略逊于 7 只。
          </div>
        </div>
      </div>

      {/* 专设模块：实盘调仓时机与交易执行指南 */}
      <div className="rounded-xl border border-indigo-100 dark:border-indigo-900/40 bg-indigo-50/30 dark:bg-indigo-950/10 p-5 space-y-3">
        <div className="flex items-center gap-2 border-b pb-2 border-indigo-100 dark:border-indigo-900/40">
          <span className="text-base font-bold text-indigo-950 dark:text-indigo-200">
            ⏰ 实操指南：这个调仓到底是什么时候操作？怎么执行？
          </span>
          <span className="text-xs px-2 py-0.5 rounded bg-indigo-100 dark:bg-indigo-900/60 text-indigo-700 dark:text-indigo-300">
            双周轮动 · 极低换手
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs text-gray-700 dark:text-gray-300 leading-relaxed">
          <div className="p-3.5 bg-white dark:bg-gray-900 rounded-lg border dark:border-gray-800 space-y-1.5">
            <div className="font-bold text-amber-700 dark:text-amber-300 flex items-center gap-1.5">
              <span>方案 A (最贴合回测)：T+1 日早盘集合竞价 (09:15 ~ 09:25)</span>
            </div>
            <div>
              1. <strong>T 日收盘后 (15:10)</strong>：系统自动根据收盘 K 线计算完成，生成最新持仓。若有调仓提示，您可在晚上或早晨看好买卖清单；
            </div>
            <div>
              2. <strong>T+1 日早盘 09:15~09:25</strong>：在交易软件中直接挂出<strong>集合竞价委托</strong>（调出的股票挂跌停价卖出，调入的股票挂涨停价买入）；
            </div>
            <div>
              3. <strong>09:25 统一成交</strong>：沪深撮合机制保证买卖全部以<strong>当日唯一起始开盘价 (Open)</strong> 成交，与回测假定 100% 吻合！
            </div>
          </div>

          <div className="p-3.5 bg-white dark:bg-gray-900 rounded-lg border dark:border-gray-800 space-y-1.5">
            <div className="font-bold text-emerald-700 dark:text-emerald-300 flex items-center gap-1.5">
              <span>方案 B (最稳健从容)：T+1 日开盘后分批 (09:35 ~ 09:45)</span>
            </div>
            <div>
              1. <strong>避开开盘前 5 分钟波动</strong>：09:30~09:35 小微盘股容易受情绪脉冲影响，建议等待 5 分钟盘面平稳；
            </div>
            <div>
              2. <strong>先卖后买</strong>：09:35 先按买一价将调出标的卖出，资金实时可用；
            </div>
            <div>
              3. <strong>再买入调入标的</strong>：对照下方表格里的<strong>建议股数/手数</strong>挂单买入。因有 2.0x 滞后带缓冲，双周调仓通常<strong>平均每次只变动 1~2 只股票</strong>，其余继续持有不动，手动极轻松！
            </div>
          </div>
        </div>
      </div>

      {/* 图表展示区：净值与水下回撤 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="p-4 rounded-xl border bg-white dark:bg-gray-900/60 dark:border-gray-800 shadow-sm">
          <div ref={equityChartRef} className="w-full h-80" />
        </div>
        <div className="p-4 rounded-xl border bg-white dark:bg-gray-900/60 dark:border-gray-800 shadow-sm">
          <div ref={drawdownChartRef} className="w-full h-80" />
        </div>
      </div>

      {/* 核心板块：当前持仓明细表 (已精准适配科创板≥200股起购/1股递增规则) */}
      <div className="rounded-xl border bg-white dark:bg-gray-900/60 dark:border-gray-800 shadow-sm p-5 space-y-4">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <h2 className="text-lg font-bold text-gray-900 dark:text-gray-100 flex items-center gap-2">
              <span>📋</span> 当前持仓明细 ({activeN} 只实操组合)
            </h2>
            <p className="text-xs text-gray-500 mt-0.5">
              单只目标仓位: {curConfig.target_weight_per_stock}% | 流通市值范围: {cap.min_cap} 亿 ~ {cap.max_cap} 亿 (中位数: {cap.median_cap} 亿)
            </p>
          </div>

          {/* 自定义实操本金输入与快捷按钮 */}
          <div className="flex flex-wrap items-center gap-2 bg-gray-50 dark:bg-gray-800/80 p-2 rounded-xl border dark:border-gray-700">
            <span className="text-xs font-semibold text-gray-600 dark:text-gray-300 whitespace-nowrap">
              💰 我的实操本金:
            </span>
            <div className="flex items-center gap-1">
              <input
                type="number"
                min="1"
                step="5"
                value={capitalWan}
                onChange={(e) => setCapitalWan(Math.max(1, Number(e.target.value) || 0))}
                className="text-xs font-bold font-mono px-2 py-1 rounded border dark:border-gray-700 bg-white dark:bg-gray-900 text-amber-600 w-16 text-right focus:outline-none focus:ring-1 focus:ring-amber-500"
              />
              <span className="text-xs text-gray-500">万元</span>
            </div>
            <div className="flex gap-1 ml-1">
              {[10, 20, 50, 100].map((w) => (
                <button
                  key={w}
                  onClick={() => setCapitalWan(w)}
                  className={`text-[11px] px-1.5 py-0.5 rounded border transition ${
                    capitalWan === w
                      ? 'bg-amber-500 text-white border-amber-600 font-bold'
                      : 'bg-white dark:bg-gray-900 text-gray-500 dark:text-gray-400 hover:text-gray-900 border-gray-200 dark:border-gray-700'
                  }`}
                >
                  {w}万
                </button>
              ))}
            </div>

            {/* 科创板整百股切换开关 */}
            <label className="flex items-center gap-1 text-[11px] text-gray-500 ml-2 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={roundKcbHundred}
                onChange={(e) => setRoundKcbHundred(e.target.checked)}
                className="rounded border-gray-300 text-amber-600 focus:ring-amber-500 h-3.5 w-3.5"
              />
              <span>科创板按整百股买</span>
            </label>
          </div>
        </div>

        {/* 科创板与主板交易规则精准说明框 */}
        <div className="p-3 rounded-lg bg-sky-50/60 dark:bg-sky-950/20 border border-sky-100 dark:border-sky-900/40 text-xs text-sky-950 dark:text-sky-200 space-y-1 leading-relaxed">
          <div className="font-bold flex items-center gap-1">
            <span>⚖️</span> A 股各板块真实买入规则已自动适配：
          </div>
          <div>
            1. <strong>主板 (60/00开头) & 创业板 (30开头)</strong>：单笔买入必须是 <strong>100 股 (1 手) 的整数倍</strong>；
          </div>
          <div>
            2. <strong>科创板 (688开头) 特别规定</strong>：上交所规定单笔申报<strong>起购不小于 200 股，超过 200 股后可以以 1 股为单位递增</strong>（例如 201 股、327 股均合规有效）。表格中已自动为您按此规则精确折算！
          </div>
        </div>

        {/* 过滤条 */}
        <div className="flex items-center justify-between gap-3 pt-1">
          <div className="relative">
            <input
              type="text"
              placeholder="搜索代码或名称..."
              value={searchKey}
              onChange={(e) => setSearchKey(e.target.value)}
              className="text-xs px-3 py-1.5 rounded-lg border dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-gray-100 w-48 focus:outline-none focus:ring-1 focus:ring-amber-500"
            />
            {searchKey && (
              <button
                onClick={() => setSearchKey('')}
                className="absolute right-2 top-1.5 text-gray-400 hover:text-gray-600 text-xs"
              >
                ✕
              </button>
            )}
          </div>
          <span className="text-xs text-gray-400">共 {filteredHoldings.length} 只标的</span>
        </div>

        {/* 表格容器 */}
        <div className="overflow-x-auto">
          <table className="w-full text-xs text-left">
            <thead className="bg-gray-50 dark:bg-gray-800/60 text-gray-500 dark:text-gray-400 border-y dark:border-gray-800">
              <tr>
                <th className="py-2.5 px-3">#</th>
                <th className="py-2.5 px-3">代码 / 板块 / 名称</th>
                <th
                  onClick={() => handleSort('price')}
                  className="py-2.5 px-3 cursor-pointer hover:text-amber-600"
                >
                  现价 {sortField === 'price' && (sortAsc ? '↑' : '↓')}
                </th>
                <th
                  onClick={() => handleSort('change_pct')}
                  className="py-2.5 px-3 cursor-pointer hover:text-amber-600"
                >
                  今日涨跌 {sortField === 'change_pct' && (sortAsc ? '↑' : '↓')}
                </th>
                <th
                  onClick={() => handleSort('float_cap_billion')}
                  className="py-2.5 px-3 cursor-pointer hover:text-amber-600"
                >
                  流通市值 (亿) {sortField === 'float_cap_billion' && (sortAsc ? '↑' : '↓')}
                </th>
                <th className="py-2.5 px-3">目标占比</th>
                <th className="py-2.5 px-3 bg-amber-50/60 dark:bg-amber-950/20 text-amber-800 dark:text-amber-300 font-bold">
                  建议委托买入 (已适配板块规则)
                </th>
                <th className="py-2.5 px-3">预估建仓金额</th>
                <th
                  onClick={() => handleSort('factor_score')}
                  className="py-2.5 px-3 cursor-pointer hover:text-amber-600"
                >
                  因子得分 {sortField === 'factor_score' && (sortAsc ? '↑' : '↓')}
                </th>
              </tr>
            </thead>
            <tbody className="divide-y dark:divide-gray-800/60">
              {filteredHoldings.map((h: any, idx: number) => {
                const isPositive = (h.change_pct || 0) > 0
                const isNegative = (h.change_pct || 0) < 0
                
                // 动态计算在用户真实资金规模下的买入股数（科创板 vs 主板/创业板精准规则）
                const targetValYuan = totalCapitalYuan * (h.target_weight / 100)
                const px = h.price > 0 ? h.price : 1.0
                const boardExec = getBoardExecution(h.code, targetValYuan, px, roundKcbHundred)
                const actualCost = boardExec.shares * px

                return (
                  <tr
                    key={h.code}
                    className="hover:bg-amber-50/30 dark:hover:bg-amber-950/20 transition-colors"
                  >
                    <td className="py-2.5 px-3 text-gray-400 font-mono">{idx + 1}</td>
                    <td className="py-2.5 px-3">
                      <div className="font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-1.5">
                        <span>{h.name}</span>
                        <span className="text-[10px] font-mono px-1 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-500">
                          {h.display_code}
                        </span>
                        {boardExec.isKcb && (
                          <span className="text-[9px] px-1 py-0.2 rounded bg-indigo-50 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800">
                            科创板
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="py-2.5 px-3 font-mono font-medium text-gray-800 dark:text-gray-200">
                      ¥{fmtNum(h.price)}
                    </td>
                    <td
                      className={`py-2.5 px-3 font-mono font-semibold ${
                        isPositive
                          ? 'text-rose-600 dark:text-rose-400'
                          : isNegative
                          ? 'text-emerald-600 dark:text-emerald-400'
                          : 'text-gray-500'
                      }`}
                    >
                      {fmtPct(h.change_pct)}
                    </td>
                    <td className="py-2.5 px-3 font-mono">
                      <span className="font-bold text-amber-700 dark:text-amber-300">
                        {fmtNum(h.float_cap_billion, 2)}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 font-mono font-semibold text-sky-600 dark:text-sky-400">
                      {fmtNum(h.target_weight, 2)}%
                    </td>
                    <td className="py-2.5 px-3 font-mono bg-amber-50/30 dark:bg-amber-950/10">
                      {boardExec.shares > 0 ? (
                        <div>
                          <div className="font-bold text-amber-800 dark:text-amber-200">
                            {boardExec.label}
                          </div>
                          <div className="text-[10px] text-gray-400">
                            {boardExec.sub}
                          </div>
                        </div>
                      ) : (
                        <span className="text-gray-400">{boardExec.label}</span>
                      )}
                    </td>
                    <td className="py-2.5 px-3 font-mono text-gray-700 dark:text-gray-300">
                      ¥{Math.round(actualCost).toLocaleString()}
                    </td>
                    <td className="py-2.5 px-3 font-mono text-gray-500">
                      {fmtNum(h.factor_score, 4)}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* 底部辅助卡片：市值分布与调仓历史 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 市值分布柱状图 */}
        <div className="p-4 rounded-xl border bg-white dark:bg-gray-900/60 dark:border-gray-800 shadow-sm">
          <div ref={capChartRef} className="w-full h-72" />
        </div>

        {/* 调仓换手历史 */}
        <div className="p-4 rounded-xl border bg-white dark:bg-gray-900/60 dark:border-gray-800 shadow-sm space-y-3">
          <h3 className="text-sm font-bold text-gray-900 dark:text-gray-100 flex items-center gap-2">
            <span>🔄</span> 调仓换手流水 (持仓 {activeN} 只近期变动)
          </h3>
          <div className="space-y-2.5 max-h-64 overflow-y-auto pr-1">
            {rbHistory.map((rb: any, i: number) => (
              <div
                key={i}
                className="p-3 rounded-lg bg-gray-50 dark:bg-gray-800/50 border dark:border-gray-700 text-xs space-y-1.5"
              >
                <div className="flex items-center justify-between">
                  <span className="font-bold text-gray-800 dark:text-gray-200">
                    📅 调仓日: {rb.rebalance_date}
                  </span>
                  <span className="px-1.5 py-0.5 rounded bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-300 font-mono">
                    当期换手率: {rb.turnover_pct}%
                  </span>
                </div>
                {rb.bought && rb.bought.length > 0 && (
                  <div className="text-emerald-700 dark:text-emerald-400 flex items-start gap-1">
                    <span className="font-semibold min-w-10">调入:</span>
                    <span className="flex flex-wrap gap-1">
                      {rb.bought.map((b: any) => (
                        <span
                          key={b.code}
                          className="px-1 py-0.2 bg-emerald-50 dark:bg-emerald-950/40 rounded border border-emerald-200 dark:border-emerald-800"
                        >
                          {b.name}
                        </span>
                      ))}
                    </span>
                  </div>
                )}
                {rb.sold && rb.sold.length > 0 && (
                  <div className="text-rose-700 dark:text-rose-400 flex items-start gap-1">
                    <span className="font-semibold min-w-10">调出:</span>
                    <span className="flex flex-wrap gap-1">
                      {rb.sold.map((s: any) => (
                        <span
                          key={s.code}
                          className="px-1 py-0.2 bg-rose-50 dark:bg-rose-950/40 rounded border border-rose-200 dark:border-rose-800"
                        >
                          {s.name}
                        </span>
                      ))}
                    </span>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
