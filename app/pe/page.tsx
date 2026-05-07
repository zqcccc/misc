'use client'

import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react'

type ProfitPoint = {
  date: string
  quarter: string
  eps: number
  ttmEps: number | null
  price: number | null
  ttmPe: number | null
}

type ProfitLineData = {
  symbol: string
  name: string
  market?: 'us' | 'cn' | 'hk'
  currency: string
  points: ProfitPoint[]
  sources: {
    eps: string
    price: string
  }
  ttmMethod?: 'quarterly-rollup' | 'source-eps-ttm'
}

type ValuationExplanation = {
  explanationType: string
  title: string
  body: string
  impactDirection?: string | null
  isRecurring?: boolean | null
  confidence?: number | null
}

type CompanyValuationCard = {
  id: string
  symbol: string
  market: string
  title: string
  currency: string | null
  entryType: string
  entryNote: string | null
  metrics: {
    asOfDate: string | null
    price: number | null
    ttmEps: number | null
    ttmPe: number | null
    profitLinePrice: number | null
    referenceLinePrice: number | null
    upsideToProfitLine: number | null
    upsideToReferenceLine: number | null
  }
  exploration: {
    summary: string | null
    thesis: string | null
    score: number | null
  }
  tags: string[]
  profitQuality: '正常' | '需调整' | '待确认'
  primaryExplanation: ValuationExplanation | null
  explanations: ValuationExplanation[]
}

type CompanyValuationPayload = {
  entries: CompanyValuationCard[]
  current: CompanyValuationCard | null
}

type LoadState = 'idle' | 'loading' | 'ready' | 'error'

const currencyFormatter = new Intl.NumberFormat('en-US', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

function formatNumber(value: number | null | undefined, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) return '-'
  return value.toFixed(digits)
}

function pct(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return '-'
  return `${value >= 0 ? '+' : ''}${value.toFixed(1)}%`
}

function qualityColor(value: CompanyValuationCard['profitQuality'] | undefined) {
  if (value === '需调整') return 'text-[#dc2626]'
  if (value === '正常') return 'text-[#16a34a]'
  return 'text-[#8a4b20]'
}

function getPreparedPoints(data: ProfitLineData | null, profitMultiple: number) {
  if (!data) return []
  return data.points.map((point) => {
    const profitLine =
      point.ttmEps === null ? null : Number((point.ttmEps * profitMultiple).toFixed(2))
    const deviation =
      point.price !== null && profitLine !== null && profitLine !== 0
        ? ((point.price - profitLine) / profitLine) * 100
        : null

    return {
      ...point,
      profitLine,
      deviation,
      alert: point.price !== null && profitLine !== null && point.price < profitLine,
    }
  })
}

function calculatePePercentile(points: ProfitPoint[], currentPe: number | null): number | null {
  if (currentPe === null || points.length === 0) return null

  // 获取所有有效的 TTM PE 值
  const validPes = points
    .map((p) => p.ttmPe)
    .filter((pe): pe is number => pe !== null && !Number.isNaN(pe))

  if (validPes.length === 0) return null

  // 计算百分位：小于等于当前值的占比
  const countLessOrEqual = validPes.filter((pe) => pe <= currentPe).length
  return Number(((countLessOrEqual / validPes.length) * 100).toFixed(1))
}

type PeriodType = 1 | 3 | 5 | 'all'

interface PeriodStats {
  period: PeriodType
  label: string
  avgPe: number | null
  minPe: number | null
  maxPe: number | null
  count: number
}

function calculatePeriodStats(points: ProfitPoint[], period: PeriodType): PeriodStats {
  const now = new Date()
  const cutoffDate = period === 'all'
    ? new Date(0)
    : new Date(now.getFullYear() - period, now.getMonth(), now.getDate())

  const filteredPoints = points.filter((p) => {
    if (p.ttmPe === null || Number.isNaN(p.ttmPe)) return false
    const pointDate = new Date(p.date)
    return pointDate >= cutoffDate
  })

  const validPes = filteredPoints.map((p) => p.ttmPe as number)

  if (validPes.length === 0) {
    return {
      period,
      label: period === 'all' ? '全部' : `过去${period}年`,
      avgPe: null,
      minPe: null,
      maxPe: null,
      count: 0,
    }
  }

  const avgPe = validPes.reduce((sum, pe) => sum + pe, 0) / validPes.length
  const minPe = Math.min(...validPes)
  const maxPe = Math.max(...validPes)

  return {
    period,
    label: period === 'all' ? '全部' : `过去${period}年`,
    avgPe: Number(avgPe.toFixed(2)),
    minPe: Number(minPe.toFixed(2)),
    maxPe: Number(maxPe.toFixed(2)),
    count: validPes.length,
  }
}

export default function ProfitLinePage() {
  const [symbolInput, setSymbolInput] = useState('00700.HK')
  const [submittedSymbol, setSubmittedSymbol] = useState('00700.HK')
  const [profitMultiple, setProfitMultiple] = useState(15)
  const [referenceMultiple, setReferenceMultiple] = useState(30)
  const [data, setData] = useState<ProfitLineData | null>(null)
  const [valuationEntries, setValuationEntries] = useState<CompanyValuationCard[]>([])
  const [currentValuation, setCurrentValuation] = useState<CompanyValuationCard | null>(null)
  const [state, setState] = useState<LoadState>('idle')
  const [error, setError] = useState('')
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>('all')
  const chartNode = useRef<HTMLDivElement | null>(null)
  const chartRef = useRef<any>(null)

  const preparedPoints = useMemo(
    () => getPreparedPoints(data, profitMultiple),
    [data, profitMultiple],
  )

  const latest = [...preparedPoints]
    .reverse()
    .find((point) => point.price !== null && point.ttmEps !== null)
  const alertCount = preparedPoints.filter((point) => point.alert).length

  const pePercentile = useMemo(() => {
    if (!data || !latest?.ttmPe) return null
    return calculatePePercentile(data.points, latest.ttmPe)
  }, [data, latest])

  const periodStats = useMemo(() => {
    if (!data) return null
    return calculatePeriodStats(data.points, selectedPeriod)
  }, [data, selectedPeriod])

  const allPeriodStats = useMemo(() => {
    if (!data) return []
    const periods: PeriodType[] = [1, 3, 5, 'all']
    return periods.map((p) => calculatePeriodStats(data.points, p))
  }, [data])

  const fetchData = useCallback(async (symbol: string) => {
    const cleanSymbol = symbol.trim().toUpperCase()
    if (!cleanSymbol) return

    setState('loading')
    setError('')
    setSubmittedSymbol(cleanSymbol)

    try {
      const valuationRequest = fetch(
        `/api/company-valuation?symbol=${encodeURIComponent(cleanSymbol)}`,
        { cache: 'no-store' },
      )
        .then(async (response) => {
          if (!response.ok) return null
          return (await response.json()) as CompanyValuationPayload
        })
        .catch(() => null)
      const response = await fetch(
        `/api/profit-line?symbol=${encodeURIComponent(cleanSymbol)}`,
        { cache: 'no-store' },
      )
      const payload = await response.json()

      if (!response.ok) {
        throw new Error(payload?.message || '数据获取失败')
      }

      setData(payload)
      const valuationPayload = await valuationRequest
      setValuationEntries(valuationPayload?.entries || [])
      setCurrentValuation(valuationPayload?.current || null)
      setState('ready')
    } catch (requestError) {
      setData(null)
      setCurrentValuation(null)
      setState('error')
      setError(
        requestError instanceof Error ? requestError.message : '数据获取失败',
      )
    }
  }, [])

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    fetchData(symbolInput)
  }

  useEffect(() => {
    const timer = window.setTimeout(() => fetchData('00700.HK'), 0)
    return () => window.clearTimeout(timer)
  }, [fetchData])

  useEffect(() => {
    let disposed = false
    let resizeChart = () => {}

    import('echarts').then((echarts) => {
      if (disposed || !chartNode.current) return
      chartRef.current = echarts.init(chartNode.current, undefined, {
        renderer: 'canvas',
      })
      resizeChart = () => chartRef.current?.resize()
      window.addEventListener('resize', resizeChart)
      resizeChart()
    })

    return () => {
      disposed = true
      window.removeEventListener('resize', resizeChart)
      chartRef.current?.dispose?.()
      chartRef.current = null
    }
  }, [])

  useEffect(() => {
    if (!chartRef.current) return

    const source = preparedPoints.map((point) => ({
      ...point,
      referenceLine:
        point.ttmEps === null
          ? null
          : Number((point.ttmEps * referenceMultiple).toFixed(2)),
    }))
    const visible = source.filter(
      (point) => point.price !== null && point.ttmEps !== null,
    )

    chartRef.current.setOption(
      {
        animationDuration: 360,
        color: ['#2563eb', '#dc2626', '#16a34a', '#ef4444'],
        backgroundColor: 'transparent',
        grid: {
          top: 42,
          right: 44,
          bottom: 58,
          left: 54,
          containLabel: true,
        },
        tooltip: {
          trigger: 'axis',
          axisPointer: {
            type: 'cross',
          },
          borderColor: '#d7d2c5',
          backgroundColor: 'rgba(255, 252, 244, 0.96)',
          textStyle: {
            color: '#2d2a25',
          },
          formatter(params: any[]) {
            const item = source[params?.[0]?.dataIndex]
            if (!item) return ''
            const pointPercentile = calculatePePercentile(data?.points || [], item.ttmPe)
            const percentileText = pointPercentile === null ? '-' : `${pointPercentile}%`
            const percentileColor = pointPercentile === null
              ? '#9ca3af'
              : pointPercentile <= 30
                ? '#16a34a'
                : pointPercentile >= 70
                  ? '#dc2626'
                  : '#8a4b20'
            return [
              `<strong>${item.quarter}</strong>`,
              `股价：${item.price === null ? '-' : currencyFormatter.format(item.price)}`,
              `TTM EPS：${formatNumber(item.ttmEps)}`,
              `TTM PE：${formatNumber(item.ttmPe)}`,
              `PE 历史百分位：<span style="color:${percentileColor};font-weight:600">${percentileText}</span>`,
              `利润线偏差：${pct(item.deviation)}`,
            ].join('<br/>')
          },
        },
        legend: {
          top: 6,
          right: 12,
          itemGap: 18,
          textStyle: {
            color: '#5b564b',
          },
        },
        xAxis: {
          type: 'category',
          data: source.map((point) => point.quarter),
          boundaryGap: false,
          axisLine: {
            lineStyle: {
              color: '#c9c1b3',
            },
          },
          axisLabel: {
            color: '#675f52',
            hideOverlap: true,
          },
        },
        yAxis: {
          type: 'value',
          name: data?.currency || 'USD',
          nameTextStyle: {
            color: '#675f52',
          },
          axisLabel: {
            color: '#675f52',
          },
          splitLine: {
            lineStyle: {
              color: '#e7dfcf',
            },
          },
        },
        dataZoom: [
          {
            type: 'inside',
            start: 40,
            end: 100,
          },
          {
            type: 'slider',
            height: 18,
            bottom: 16,
            borderColor: '#d7d0c3',
            fillerColor: 'rgba(37, 99, 235, 0.12)',
            handleStyle: {
              color: '#2563eb',
            },
          },
        ],
        series: [
          {
            name: '股价',
            type: 'line',
            smooth: false,
            showSymbol: true,
            symbolSize: 6,
            data: source.map((point) => point.price),
            lineStyle: {
              width: 3,
              color: '#2563eb',
            },
            itemStyle: {
              color: '#2563eb',
            },
          },
          {
            name: `${profitMultiple}x 利润线`,
            type: 'line',
            smooth: false,
            showSymbol: false,
            data: source.map((point) => point.profitLine),
            lineStyle: {
              width: 2,
              type: 'dashed',
              color: '#dc2626',
            },
          },
          {
            name: `${referenceMultiple}x 参考线`,
            type: 'line',
            smooth: false,
            showSymbol: false,
            data: source.map((point) => point.referenceLine),
            lineStyle: {
              width: 2,
              type: 'dashed',
              color: '#16a34a',
            },
          },
          {
            name: '低于利润线',
            type: 'scatter',
            symbolSize: 12,
            data: source.map((point) => (point.alert ? point.price : null)),
            itemStyle: {
              color: '#ef4444',
              borderColor: '#7f1d1d',
              borderWidth: 2,
            },
            tooltip: {
              show: false,
            },
          },
        ],
      },
      true,
    )

    if (visible.length === 0 && state === 'ready') {
      chartRef.current.clear()
    }
  }, [
    data?.currency,
    data?.points,
    preparedPoints,
    profitMultiple,
    referenceMultiple,
    state,
  ])

  return (
    <main className='min-h-screen bg-[#f8f3e9] text-[#28241d]'>
      <section className='mx-auto flex min-h-screen w-full max-w-7xl flex-col gap-5 px-4 py-5 sm:px-6 lg:px-8'>
        <div className='flex flex-col gap-4 border-b border-[#d8cfbd] pb-5 lg:flex-row lg:items-end lg:justify-between'>
          <div>
            <p className='text-sm font-semibold uppercase tracking-[0.18em] text-[#8a4b20]'>
              Profit Line Lab
            </p>
            <h1 className='mt-2 text-3xl font-bold leading-tight text-[#211d18] sm:text-4xl'>
              利润线 vs 股价
            </h1>
          </div>

          <form
            className='flex w-full flex-col gap-3 sm:flex-row lg:w-auto'
            onSubmit={handleSubmit}
          >
            <label className='flex min-w-0 flex-1 flex-col gap-1 text-sm font-medium text-[#51493d] lg:w-64'>
              股票代码
              <input
                className='h-11 rounded-md border border-[#cfc5b3] bg-[#fffaf1] px-3 text-base font-semibold uppercase text-[#211d18] outline-none transition focus:border-[#2563eb] focus:ring-2 focus:ring-[#2563eb]/20'
                value={symbolInput}
                onChange={(event) => setSymbolInput(event.target.value)}
                placeholder='AAPL / 600519 / 00700'
              />
            </label>
            <button
              className='h-11 rounded-md bg-[#1f2937] px-5 text-sm font-bold text-[#fffaf1] transition hover:bg-[#111827] disabled:cursor-not-allowed disabled:opacity-60 sm:self-end'
              disabled={state === 'loading'}
              type='submit'
            >
              {state === 'loading' ? '获取中' : '绘制'}
            </button>
          </form>
        </div>

        <div className='grid gap-3 lg:grid-cols-[240px_minmax(0,1fr)_320px]'>
          <nav className='rounded-md border border-[#d8cfbd] bg-[#fffaf1] p-3 lg:max-h-[calc(100vh-140px)] lg:overflow-auto'>
            <div className='mb-3 flex items-center justify-between gap-2'>
              <h2 className='text-sm font-black text-[#211d18]'>公司入口</h2>
              <span className='rounded bg-[#f0ebe0] px-2 py-1 text-xs font-bold text-[#8a4b20]'>
                {valuationEntries.length}
              </span>
            </div>

            {valuationEntries.length === 0 ? (
              <div className='rounded bg-[#f0ebe0] px-3 py-4 text-sm leading-6 text-[#706758]'>
                暂无 AI 探索结果。后续定时任务写入数据库后会显示在这里。
              </div>
            ) : (
              <div className='space-y-2'>
                {valuationEntries.map((entry) => {
                  const active =
                    entry.symbol === currentValuation?.symbol ||
                    entry.symbol === data?.symbol

                  return (
                    <button
                      key={entry.id}
                      className={`w-full rounded-md border px-3 py-3 text-left transition ${
                        active
                          ? 'border-[#2563eb] bg-[#eff6ff]'
                          : 'border-[#e3d9c8] bg-[#fffaf1] hover:border-[#c7bca8]'
                      }`}
                      type='button'
                      onClick={() => {
                        setSymbolInput(entry.symbol)
                        fetchData(entry.symbol)
                      }}
                    >
                      <div className='flex items-start justify-between gap-2'>
                        <div className='min-w-0'>
                          <div className='truncate text-sm font-black text-[#211d18]'>
                            {entry.title}
                          </div>
                          <div className='mt-1 text-xs font-semibold text-[#706758]'>
                            {entry.symbol}
                          </div>
                        </div>
                        <span className={`shrink-0 text-xs font-black ${qualityColor(entry.profitQuality)}`}>
                          {entry.profitQuality}
                        </span>
                      </div>
                      <div className='mt-2 flex items-center justify-between text-xs text-[#706758]'>
                        <span>PE {formatNumber(entry.metrics.ttmPe)}</span>
                        <span>{entry.exploration.score === null ? '-' : entry.exploration.score}</span>
                      </div>
                    </button>
                  )
                })}
              </div>
            )}
          </nav>

          <div className='min-h-[560px] rounded-md border border-[#d8cfbd] bg-[#fffaf1]'>
            <div className='flex flex-col gap-1 border-b border-[#e3d9c8] px-4 py-3 sm:flex-row sm:items-center sm:justify-between'>
              <div>
                <h2 className='text-lg font-bold'>
                  {data ? `${data.symbol} · ${data.name}` : submittedSymbol}
                </h2>
                <p className='text-sm text-[#706758]'>
                  {data?.ttmMethod === 'source-eps-ttm'
                    ? 'TTM EPS 使用市场数据源提供值，线值随倍数实时更新。'
                    : '单季 EPS 滚动 4 季生成 TTM EPS，线值随倍数实时更新。'}
                </p>
              </div>
              <div className='text-sm font-semibold text-[#8a4b20]'>
                {alertCount > 0 ? `${alertCount} 个季度低于利润线` : '无警示点'}
              </div>
            </div>

            <div className='relative h-[500px]'>
              <div ref={chartNode} className='h-full w-full' />
              {state === 'loading' && (
                <div className='absolute inset-0 grid place-items-center bg-[#fffaf1]/80 text-sm font-semibold text-[#51493d]'>
                  正在获取季度 EPS 与股价...
                </div>
              )}
              {state === 'error' && (
                <div className='absolute inset-0 grid place-items-center bg-[#fffaf1] px-6 text-center'>
                  <div>
                    <p className='text-lg font-bold text-[#991b1b]'>无法绘制</p>
                    <p className='mt-2 max-w-md text-sm text-[#675f52]'>{error}</p>
                  </div>
                </div>
              )}
            </div>
          </div>

          <aside className='flex flex-col gap-3'>
            <div className='rounded-md border border-[#d8cfbd] bg-[#fffaf1] p-4'>
              <div className='flex items-center justify-between gap-3'>
                <label
                  className='text-sm font-bold text-[#3a332b]'
                  htmlFor='profitMultiple'
                >
                  利润线倍数
                </label>
                <span className='tabular-nums text-xl font-black text-[#dc2626]'>
                  {profitMultiple}x
                </span>
              </div>
              <input
                id='profitMultiple'
                className='mt-4 w-full accent-[#dc2626]'
                max='50'
                min='5'
                step='1'
                type='range'
                value={profitMultiple}
                onChange={(event) => setProfitMultiple(Number(event.target.value))}
              />
            </div>

            <div className='rounded-md border border-[#d8cfbd] bg-[#fffaf1] p-4'>
              <div className='flex items-center justify-between gap-3'>
                <label
                  className='text-sm font-bold text-[#3a332b]'
                  htmlFor='referenceMultiple'
                >
                  参考线倍数
                </label>
                <span className='tabular-nums text-xl font-black text-[#16a34a]'>
                  {referenceMultiple}x
                </span>
              </div>
              <input
                id='referenceMultiple'
                className='mt-4 w-full accent-[#16a34a]'
                max='50'
                min='5'
                step='1'
                type='range'
                value={referenceMultiple}
                onChange={(event) =>
                  setReferenceMultiple(Number(event.target.value))
                }
              />
            </div>

            <div className='grid grid-cols-2 gap-3'>
              <div className='rounded-md border border-[#d8cfbd] bg-[#fffaf1] p-4'>
                <div className='text-xs font-bold uppercase tracking-[0.12em] text-[#8a4b20]'>
                  最新股价
                </div>
                <div className='mt-2 text-2xl font-black tabular-nums'>
                  {latest?.price === undefined
                    ? '-'
                    : currencyFormatter.format(latest.price || 0)}
                </div>
              </div>
              <div className='rounded-md border border-[#d8cfbd] bg-[#fffaf1] p-4'>
                <div className='text-xs font-bold uppercase tracking-[0.12em] text-[#8a4b20]'>
                  TTM PE
                </div>
                <div className='mt-2 text-2xl font-black tabular-nums'>
                  {formatNumber(latest?.ttmPe)}
                </div>
              </div>
            </div>

            <div className='rounded-md border border-[#d8cfbd] bg-[#fffaf1] p-4'>
              <div className='flex items-center justify-between gap-3'>
                <div className='text-xs font-bold uppercase tracking-[0.12em] text-[#8a4b20]'>
                  PE 历史百分位
                </div>
                <div
                  className={`text-sm font-semibold ${
                    pePercentile === null
                      ? 'text-[#9ca3af]'
                      : pePercentile <= 30
                        ? 'text-[#16a34a]'
                        : pePercentile >= 70
                          ? 'text-[#dc2626]'
                          : 'text-[#8a4b20]'
                  }`}
                >
                  {pePercentile === null
                    ? '-'
                    : pePercentile <= 30
                      ? '低估'
                      : pePercentile >= 70
                        ? '高估'
                        : '合理'}
                </div>
              </div>
              <div className='mt-2'>
                <div className='flex items-baseline gap-1'>
                  <span className='text-3xl font-black tabular-nums text-[#211d18]'>
                    {pePercentile === null ? '-' : `${pePercentile}%`}
                  </span>
                  <span className='text-sm text-[#706758]'>
                    {pePercentile !== null && `(${data?.points.filter((p) => p.ttmPe !== null).length || 0} 个季度)`}
                  </span>
                </div>
                <div className='mt-2 h-2 w-full rounded-full bg-[#e7dfcf] overflow-hidden'>
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${
                      pePercentile === null
                        ? 'bg-[#9ca3af]'
                        : pePercentile <= 30
                          ? 'bg-[#16a34a]'
                          : pePercentile >= 70
                            ? 'bg-[#dc2626]'
                            : 'bg-[#8a4b20]'
                    }`}
                    style={{
                      width: pePercentile === null ? '0%' : `${pePercentile}%`,
                    }}
                  />
                </div>
                <div className='mt-1 flex justify-between text-xs text-[#9ca3af]'>
                  <span>0%</span>
                  <span>50%</span>
                  <span>100%</span>
                </div>
              </div>
            </div>

            <div className='rounded-md border border-[#d8cfbd] bg-[#fffaf1] p-4'>
              <div className='flex items-center justify-between gap-3'>
                <div className='text-xs font-bold uppercase tracking-[0.12em] text-[#8a4b20]'>
                  利润质量
                </div>
                <div className={`text-sm font-black ${qualityColor(currentValuation?.profitQuality)}`}>
                  {currentValuation?.profitQuality || '待确认'}
                </div>
              </div>

              <div className='mt-3 rounded bg-[#f0ebe0] px-3 py-3'>
                <div className='text-sm font-bold text-[#211d18]'>
                  {currentValuation?.primaryExplanation?.title || '暂无利润/股价解释'}
                </div>
                <p className='mt-2 text-sm leading-6 text-[#5d5548]'>
                  {currentValuation?.primaryExplanation?.body ||
                    'AI 探索任务写入解释后，会在这里说明当前股价或利润是否由非经常性因素驱动。'}
                </p>
              </div>

              {currentValuation?.explanations.length ? (
                <div className='mt-3 space-y-2'>
                  {currentValuation.explanations.slice(0, 3).map((explanation) => (
                    <div
                      key={`${explanation.explanationType}-${explanation.title}`}
                      className='border-t border-[#e7dfcf] pt-2 text-sm'
                    >
                      <div className='flex items-center justify-between gap-2'>
                        <span className='font-bold text-[#3a332b]'>
                          {explanation.explanationType === 'profit'
                            ? '利润'
                            : explanation.explanationType === 'price'
                              ? '股价'
                              : '估值'}
                        </span>
                        <span className='text-xs text-[#706758]'>
                          置信度 {explanation.confidence ?? '-'}
                        </span>
                      </div>
                      <p className='mt-1 line-clamp-2 leading-6 text-[#5d5548]'>
                        {explanation.body}
                      </p>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>

            <div className='rounded-md border border-[#d8cfbd] bg-[#fffaf1] p-4'>
              <div className='text-xs font-bold uppercase tracking-[0.12em] text-[#8a4b20]'>
                历史平均 PE
              </div>

              <div className='mt-3 flex gap-1 rounded-md bg-[#e7dfcf] p-1'>
                {([1, 3, 5, 'all'] as PeriodType[]).map((p) => (
                  <button
                    key={p}
                    onClick={() => setSelectedPeriod(p)}
                    className={`flex-1 rounded px-2 py-1 text-xs font-semibold transition ${
                      selectedPeriod === p
                        ? 'bg-[#fffaf1] text-[#211d18] shadow-sm'
                        : 'text-[#706758] hover:text-[#211d18]'
                    }`}
                  >
                    {p === 'all' ? '全部' : `${p}年`}
                  </button>
                ))}
              </div>

              <div className='mt-4'>
                <div className='flex items-baseline gap-2'>
                  <span className='text-3xl font-black tabular-nums text-[#211d18]'>
                    {periodStats?.avgPe === null ? '-' : formatNumber(periodStats?.avgPe)}
                  </span>
                  <span className='text-sm text-[#706758]'>
                    {periodStats && periodStats.count > 0 && `(${periodStats.count} 个季度)`}
                  </span>
                </div>

                <div className='mt-3 grid grid-cols-2 gap-3 text-sm'>
                  <div className='rounded bg-[#f0ebe0] px-3 py-2'>
                    <div className='text-xs text-[#9ca3af]'>最低</div>
                    <div className='mt-1 font-bold text-[#16a34a]'>
                      {periodStats?.minPe === null ? '-' : formatNumber(periodStats?.minPe)}
                    </div>
                  </div>
                  <div className='rounded bg-[#f0ebe0] px-3 py-2'>
                    <div className='text-xs text-[#9ca3af]'>最高</div>
                    <div className='mt-1 font-bold text-[#dc2626]'>
                      {periodStats?.maxPe === null ? '-' : formatNumber(periodStats?.maxPe)}
                    </div>
                  </div>
                </div>
              </div>

              <div className='mt-4 border-t border-[#e7dfcf] pt-3'>
                <div className='text-xs text-[#9ca3af] mb-2'>各时段对比</div>
                <div className='space-y-1.5'>
                  {allPeriodStats.map((stats) => (
                    <div key={stats.period} className='flex items-center justify-between text-sm'>
                      <span className='text-[#706758]'>{stats.label}</span>
                      <span className={`font-semibold tabular-nums ${
                        stats.avgPe === null
                          ? 'text-[#9ca3af]'
                          : stats.avgPe < (periodStats?.avgPe || 0)
                            ? 'text-[#16a34a]'
                            : stats.avgPe > (periodStats?.avgPe || 0)
                              ? 'text-[#dc2626]'
                              : 'text-[#211d18]'
                      }`}>
                        {stats.avgPe === null ? '-' : formatNumber(stats.avgPe)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className='rounded-md border border-[#d8cfbd] bg-[#fffaf1] p-4 text-sm leading-6 text-[#5d5548]'>
              <p>
                数据源：{data?.sources.eps || 'SEC companyfacts'} /{' '}
                {data?.sources.price || 'Yahoo Finance chart'}。
              </p>
              <p className='mt-2'>
                红色高亮点表示当季股价低于当前利润线倍数对应价格。
              </p>
            </div>
          </aside>
        </div>
      </section>
    </main>
  )
}
