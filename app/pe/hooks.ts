'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  ProfitLineData,
  CompanyValuationCard,
  CompanyValuationListPayload,
  CompanyValuationDetailPayload,
  LoadState,
  PeriodType,
} from './types'
import { getPreparedPoints, calculatePePercentile, calculatePeriodStats } from './calculations'
import { buildChartSource } from './chart-data'

export function useProfitLineData(symbolInput: string) {
  const [submittedSymbol, setSubmittedSymbol] = useState('00700.HK')
  const [data, setData] = useState<ProfitLineData | null>(null)
  const [state, setState] = useState<LoadState>('idle')
  const [error, setError] = useState('')

  const fetchData = useCallback(
    async (symbol: string) => {
      const cleanSymbol = symbol.trim().toUpperCase()
      if (!cleanSymbol) return

      setState('loading')
      setError('')
      setSubmittedSymbol(cleanSymbol)

      try {
        const response = await fetch(
          `/api/profit-line?symbol=${encodeURIComponent(cleanSymbol)}`,
          { cache: 'no-store' },
        )
        const payload = await response.json()

        if (!response.ok) {
          throw new Error(payload?.message || '数据获取失败')
        }

        setData(payload)
        setState('ready')
      } catch (requestError) {
        setData(null)
        setState('error')
        setError(
          requestError instanceof Error ? requestError.message : '数据获取失败',
        )
      }
    },
    [],
  )

  return { submittedSymbol, data, state, error, fetchData }
}

export function useValuationDetail(
  symbol: string,
  state: LoadState,
  initialValuation?: CompanyValuationCard | null,
) {
  const [currentValuation, setCurrentValuation] = useState<CompanyValuationCard | null>(
    initialValuation ?? null,
  )

  const lastLoadedSymbolRef = useRef<string>('')

  useEffect(() => {
    if (state !== 'loading') return

    const cleanSymbol = symbol.trim().toUpperCase()
    if (!cleanSymbol) return

    fetch(`/api/company-valuation/${encodeURIComponent(cleanSymbol)}`, { cache: 'no-store' })
      .then(async (response) => {
        if (!response.ok) return null
        return (await response.json()) as CompanyValuationDetailPayload
      })
      .then((payload) => {
        if (payload?.current) {
          setCurrentValuation(payload.current)
          lastLoadedSymbolRef.current = cleanSymbol
        }
      })
      .catch(() => {
        // 静默失败，保留已有数据
      })
  }, [symbol, state])

  return { currentValuation, setCurrentValuation }
}

export function useValuationEntries() {
  const [valuationEntries, setValuationEntries] = useState<CompanyValuationCard[]>([])
  const [entriesLoading, setEntriesLoading] = useState(true)
  const [entriesLoadingMore, setEntriesLoadingMore] = useState(false)
  const [totalCount, setTotalCount] = useState(0)
  const [hasMore, setHasMore] = useState(true)
  const [currentPage, setCurrentPage] = useState(1)
  const loadingRef = useRef(false)

  const loadPage = useCallback(async (page: number, append = false) => {
    if (loadingRef.current) return
    loadingRef.current = true

    if (page === 1) {
      setEntriesLoading(true)
    } else {
      setEntriesLoadingMore(true)
    }

    try {
      const response = await fetch(`/api/company-valuation?page=${page}`, {
        cache: 'no-store',
      })
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }
      const payload = (await response.json()) as CompanyValuationListPayload

      setValuationEntries((prev) => {
        if (!append) return payload.entries || []
        const existingIds = new Set(prev.map((e) => e.id))
        const newEntries = (payload.entries || []).filter((e) => !existingIds.has(e.id))
        return [...prev, ...newEntries]
      })
      setTotalCount(payload.total || 0)
      setHasMore(payload.hasMore || false)
      setCurrentPage(payload.page || page)
    } catch {
      // 列表加载失败不阻塞主流程
    } finally {
      loadingRef.current = false
      if (page === 1) {
        setEntriesLoading(false)
      } else {
        setEntriesLoadingMore(false)
      }
    }
  }, [])

  useEffect(() => {
    let cancelled = false

    async function load() {
      setEntriesLoading(true)
      try {
        const response = await fetch('/api/company-valuation?page=1', {
          cache: 'no-store',
        })
        if (!response.ok) return
        const payload = (await response.json()) as CompanyValuationListPayload
        if (!cancelled) {
          setValuationEntries(payload.entries || [])
          setTotalCount(payload.total || 0)
          setHasMore(payload.hasMore || false)
          setCurrentPage(payload.page || 1)
        }
      } catch {
        // 列表加载失败不阻塞主流程
      } finally {
        if (!cancelled) {
          setEntriesLoading(false)
        }
      }
    }

    load()
    return () => {
      cancelled = true
    }
  }, [])

  const fetchEntries = useCallback(async () => {
    await loadPage(1, false)
  }, [loadPage])

  const loadMore = useCallback(async () => {
    if (entriesLoadingMore || !hasMore) return
    await loadPage(currentPage + 1, true)
  }, [loadPage, currentPage, entriesLoadingMore, hasMore])

  return { valuationEntries, entriesLoading, entriesLoadingMore, totalCount, hasMore, fetchEntries, loadMore }
}

export function useChart() {
  const chartNode = useRef<HTMLDivElement | null>(null)
  const chartRef = useRef<any>(null)
  const [chartReady, setChartReady] = useState(false)

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
      setChartReady(true)
    })

    return () => {
      disposed = true
      window.removeEventListener('resize', resizeChart)
      chartRef.current?.dispose?.()
      chartRef.current = null
      setChartReady(false)
    }
  }, [])

  return { chartNode, chartRef, chartReady }
}

export function useChartOptions(
  data: ProfitLineData | null,
  preparedPoints: ReturnType<typeof getPreparedPoints>,
  profitMultiple: number,
  referenceMultiple: number,
  state: LoadState,
  chartReady: boolean,
  chartRef: React.MutableRefObject<any>,
) {
  useEffect(() => {
    if (!chartRef.current) return

    const isDark = document.documentElement.classList.contains('dark')

    const source = buildChartSource(
      preparedPoints,
      data?.latestPrice,
      profitMultiple,
      referenceMultiple,
    )
    const visible = source.filter(
      (point) => point.price !== null && point.ttmEps !== null,
    )

    const axisLabelColor = isDark ? '#64748b' : '#94a3b8'
    const splitLineColor = isDark ? 'rgba(255,255,255,0.04)' : '#f1f5f9'
    const axisLineColor = isDark ? 'rgba(255,255,255,0.06)' : '#e2e8f0'
    const legendColor = isDark ? '#94a3b8' : '#64748b'
    const tooltipBg = isDark ? 'rgba(15, 23, 42, 0.95)' : 'rgba(255, 255, 255, 0.98)'
    const tooltipBorder = isDark ? 'rgba(255,255,255,0.08)' : '#e2e8f0'
    const tooltipText = isDark ? '#e2e8f0' : '#1e293b'
    const dataZoomBorder = isDark ? 'rgba(255,255,255,0.06)' : '#e2e8f0'
    const dataZoomFiller = isDark ? 'rgba(59, 130, 246, 0.15)' : 'rgba(59, 130, 246, 0.1)'
    const dataZoomHandle = isDark ? '#3b82f6' : '#3b82f6'

    chartRef.current.setOption(
      {
        animationDuration: 360,
        color: isDark
          ? ['#60a5fa', '#f87171', '#4ade80', '#fbbf24', '#f87171']
          : ['#3b82f6', '#ef4444', '#22c55e', '#f59e0b', '#ef4444'],
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
            crossStyle: {
              color: isDark ? '#6b7280' : '#9ca3af',
            },
          },
          borderColor: tooltipBorder,
          backgroundColor: tooltipBg,
          textStyle: {
            color: tooltipText,
          },
          formatter(params: any[]) {
            const item = source[params?.[0]?.dataIndex]
            if (!item) return ''
            const pointPercentileAll = calculatePePercentile(data?.points || [], item.ttmPe, 'all')
            const pointPercentile3Y = calculatePePercentile(data?.points || [], item.ttmPe, 3)
            const pointPercentile5Y = calculatePePercentile(data?.points || [], item.ttmPe, 5)
            const getPercentileColor = (val: number | null) => {
              if (val === null) return isDark ? '#64748b' : '#94a3b8'
              if (val <= 30) return isDark ? '#4ade80' : '#22c55e'
              if (val >= 70) return isDark ? '#f87171' : '#ef4444'
              return isDark ? '#fbbf24' : '#d97706'
            }
            const getPercentileText = (val: number | null) => val === null ? '-' : `${val}%`
            return [
              `<strong>${item.quarter}</strong>`,
              `股价：${item.price === null ? '-' : new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(item.price)}`,
              `TTM EPS：${item.ttmEps === null || item.ttmEps === undefined || Number.isNaN(item.ttmEps) ? '-' : item.ttmEps.toFixed(2)}`,
              item.epsSourceQuarter ? `TTM EPS 来源：${item.epsSourceQuarter}` : null,
              `TTM PE：${item.ttmPe === null || item.ttmPe === undefined || Number.isNaN(item.ttmPe) ? '-' : item.ttmPe.toFixed(2)}${item.isLatestPrice ? '（按最新价重算）' : ''}`,
              `PE 历史百分位（全部）：<span style="color:${getPercentileColor(pointPercentileAll)};font-weight:600">${getPercentileText(pointPercentileAll)}</span>`,
              ...(pointPercentile3Y !== null ? [`PE 历史百分位（3年）：<span style="color:${getPercentileColor(pointPercentile3Y)};font-weight:600">${getPercentileText(pointPercentile3Y)}</span>`] : []),
              ...(pointPercentile5Y !== null ? [`PE 历史百分位（5年）：<span style="color:${getPercentileColor(pointPercentile5Y)};font-weight:600">${getPercentileText(pointPercentile5Y)}</span>`] : []),
              `利润线偏差：${item.deviation === null || item.deviation === undefined || Number.isNaN(item.deviation) ? '-' : `${item.deviation >= 0 ? '+' : ''}${item.deviation.toFixed(1)}%`}`,
            ].filter(Boolean).join('<br/>')
          },
        },
        legend: {
          top: 6,
          right: 12,
          itemGap: 18,
          textStyle: {
            color: legendColor,
          },
        },
        xAxis: {
          type: 'category',
          data: source.map((point) => point.displayLabel),
          boundaryGap: false,
          axisLine: {
            lineStyle: {
              color: axisLineColor,
            },
          },
          axisLabel: {
            color: axisLabelColor,
            hideOverlap: true,
          },
        },
        yAxis: {
          type: 'value',
          name: data?.currency || 'USD',
          nameTextStyle: {
            color: axisLabelColor,
          },
          axisLabel: {
            color: axisLabelColor,
          },
          splitLine: {
            lineStyle: {
              color: splitLineColor,
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
            borderColor: dataZoomBorder,
            fillerColor: dataZoomFiller,
            handleStyle: {
              color: dataZoomHandle,
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
              width: 2.5,
              color: isDark ? '#60a5fa' : '#3b82f6',
            },
            itemStyle: {
              color: isDark ? '#60a5fa' : '#3b82f6',
            },
          },
          {
            name: `${profitMultiple}x 利润线`,
            type: 'line',
            smooth: false,
            showSymbol: false,
            data: source.map((point) => point.profitLine),
            lineStyle: {
              width: 1.5,
              type: 'dashed',
              color: isDark ? '#f87171' : '#ef4444',
            },
          },
          {
            name: `${referenceMultiple}x 参考线`,
            type: 'line',
            smooth: false,
            showSymbol: false,
            data: source.map((point) => point.referenceLine),
            lineStyle: {
              width: 1.5,
              type: 'dashed',
              color: isDark ? '#4ade80' : '#22c55e',
            },
          },
          {
            name: '低于利润线',
            type: 'scatter',
            symbolSize: 12,
            data: source.map((point) => (point.alert ? point.price : null)),
            itemStyle: {
              color: isDark ? '#f87171' : '#ef4444',
              borderColor: isDark ? '#b91c1c' : '#991b1b',
              borderWidth: 1.5,
            },
            tooltip: {
              show: false,
            },
          },
          {
            name: '最新价',
            type: 'scatter',
            symbolSize: 14,
            data: source.map((point) => (point.isLatestPrice ? point.price : null)),
            itemStyle: {
              color: isDark ? '#fbbf24' : '#f59e0b',
              borderColor: isDark ? '#fde68a' : '#92400e',
              borderWidth: 1.5,
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
    chartReady,
    data?.currency,
    data?.latestPrice,
    data?.points,
    preparedPoints,
    profitMultiple,
    referenceMultiple,
    state,
    chartRef,
  ])
}

export function useDerivedData(
  data: ProfitLineData | null,
  profitMultiple: number,
  selectedPeriod: PeriodType,
) {
  const preparedPoints = useMemo(
    () => getPreparedPoints(data, profitMultiple),
    [data, profitMultiple],
  )

  const latestQuarterPoint = useMemo(
    () => [...preparedPoints]
      .reverse()
      .find((point) => point.price !== null && point.ttmEps !== null),
    [preparedPoints],
  )

  const latestMarketPrice = data?.latestPrice?.price ?? latestQuarterPoint?.price ?? null
  const latestMarketDate = data?.latestPrice?.date ?? latestQuarterPoint?.date ?? null

  const currentPe = useMemo(() => {
    if (
      latestMarketPrice !== null &&
      latestQuarterPoint?.ttmEps !== null &&
      latestQuarterPoint?.ttmEps !== undefined &&
      latestQuarterPoint.ttmEps > 0
    ) {
      return Number((latestMarketPrice / latestQuarterPoint.ttmEps).toFixed(2))
    }
    return latestQuarterPoint?.ttmPe ?? null
  }, [latestMarketPrice, latestQuarterPoint])

  const alertCount = useMemo(
    () => preparedPoints.filter((point) => point.alert).length,
    [preparedPoints],
  )

  const pePercentileAll = useMemo(() => {
    if (!data || currentPe === null) return null
    return calculatePePercentile(data.points, currentPe, 'all')
  }, [currentPe, data])

  const pePercentile3Y = useMemo(() => {
    if (!data || currentPe === null) return null
    return calculatePePercentile(data.points, currentPe, 3)
  }, [currentPe, data])

  const pePercentile5Y = useMemo(() => {
    if (!data || currentPe === null) return null
    return calculatePePercentile(data.points, currentPe, 5)
  }, [currentPe, data])

  const periodStats = useMemo(() => {
    if (!data) return null
    return calculatePeriodStats(data.points, selectedPeriod)
  }, [data, selectedPeriod])

  const allPeriodStats = useMemo(() => {
    if (!data) return []
    const periods: PeriodType[] = [1, 3, 5, 'all']
    return periods.map((p) => calculatePeriodStats(data.points, p))
  }, [data])

  return {
    preparedPoints,
    latestQuarterPoint,
    latestMarketPrice,
    latestMarketDate,
    currentPe,
    alertCount,
    pePercentileAll,
    pePercentile3Y,
    pePercentile5Y,
    periodStats,
    allPeriodStats,
  }
}

export function useFilteredEntries(
  valuationEntries: CompanyValuationCard[],
  searchQuery: string,
  filterQuality: '全部' | CompanyValuationCard['profitQuality'],
) {
  return useMemo(() => {
    return valuationEntries.filter((entry) => {
      if (filterQuality !== '全部' && entry.profitQuality !== filterQuality) {
        return false
      }
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase().trim()
        const matchTitle = entry.title.toLowerCase().includes(query)
        const matchSymbol = entry.symbol.toLowerCase().includes(query)
        const matchTags = entry.tags.some((tag) => tag.toLowerCase().includes(query))
        if (!matchTitle && !matchSymbol && !matchTags) {
          return false
        }
      }
      return true
    })
  }, [valuationEntries, filterQuality, searchQuery])
}
