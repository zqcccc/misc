'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import type { OverviewPayload, MarketResult, RangeStats } from './types'
import {
  buildMainOption,
  buildWeightOption,
  resolveRange,
  computeRangeStats,
} from './chart-options'

export type LoadState = 'idle' | 'loading' | 'ready' | 'error'

/**
 * 拉取 /api/trhrp-backtest 概览(轻量, 不含 timeseries)。
 * 每 autoRefreshMs 自动刷新一次, 让页面跟上脚本重新生成的 _all.json。
 */
export function useOverview(autoRefreshMs = 60_000): {
  data: OverviewPayload | null
  state: LoadState
  error: string
  generatedAt: string | null
  refresh: () => void
} {
  const [data, setData] = useState<OverviewPayload | null>(null)
  const [state, setState] = useState<LoadState>('idle')
  const [error, setError] = useState('')
  const [generatedAt, setGeneratedAt] = useState<string | null>(null)

  const fetchData = useCallback(async () => {
    if (state !== 'ready') setState('loading')
    try {
      const resp = await fetch('/api/trhrp-backtest', { cache: 'no-store' })
      const payload = await resp.json()
      if (!resp.ok) {
        throw new Error(payload?.message || `HTTP ${resp.status}`)
      }
      setData(payload as OverviewPayload)
      setGeneratedAt(
        resp.headers.get('x-generated-at') || payload.generated_at,
      )
      setState('ready')
      setError('')
    } catch (err) {
      setState('error')
      setError(err instanceof Error ? err.message : '数据获取失败')
    }
  }, [state])

  useEffect(() => {
    fetchData()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (autoRefreshMs <= 0) return
    const timer = setInterval(() => fetchData(), autoRefreshMs)
    return () => clearInterval(timer)
  }, [autoRefreshMs, fetchData])

  return { data, state, error, generatedAt, refresh: fetchData }
}

// 单标的结果按 (label@generatedAt) 缓存, 切回已看过的标的无需重新请求
const resultCache = new Map<string, MarketResult>()

/** 按需加载单标的完整结果(含 timeseries), key 随 generatedAt 失效 */
export function useMarketResult(label: string | null, generatedAt: string | null) {
  const [result, setResult] = useState<MarketResult | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!label) return
    const key = `${label}@${generatedAt}`
    const cached = resultCache.get(key)
    if (cached) {
      setResult(cached)
      return
    }
    let cancelled = false
    setLoading(true)
    fetch(`/api/trhrp-backtest?market=${encodeURIComponent(label)}`, {
      cache: 'no-store',
    })
      .then((r) => r.json())
      .then((d) => {
        if (cancelled) return
        if (d && d.meta) {
          resultCache.set(key, d as MarketResult)
          setResult(d as MarketResult)
        }
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [label, generatedAt])

  return { result, loading }
}

/**
 * 初始化并联动主图 + 仓位子图两张 ECharts。
 * - 在 result 变化时重设 option
 * - echarts.connect 使两者 dataZoom 同步缩放
 * - 主图 dataZoom 事件 -> 计算区间统计 -> onRange
 */
export function useConnectedCharts(
  mainRef: React.RefObject<HTMLDivElement | null>,
  weightRef: React.RefObject<HTMLDivElement | null>,
  result: MarketResult | null,
  regimeCn: Record<string, string>,
  onRange: (r: RangeStats | null) => void,
) {
  const mainChartRef = useRef<any>(null)
  const weightChartRef = useRef<any>(null)
  const echartsRef = useRef<any>(null)
  const [ready, setReady] = useState(false)

  // 用 ref 持有最新的回调与 result, 避免重复绑定事件
  const onRangeRef = useRef(onRange)
  onRangeRef.current = onRange
  const resultRef = useRef(result)
  resultRef.current = result

  useEffect(() => {
    let disposed = false
    let main: any
    let weight: any
    let onResize = () => {}

    import('echarts').then((ec) => {
      if (disposed || !mainRef.current || !weightRef.current) return
      echartsRef.current = ec
      main = ec.init(mainRef.current)
      weight = ec.init(weightRef.current)
      mainChartRef.current = main
      weightChartRef.current = weight

      main.on('dataZoom', () => {
        const r = resultRef.current
        if (!r) return
        const dz = main.getOption().dataZoom
        const [sv, ev] = resolveRange(dz, r.timeseries)
        onRangeRef.current(computeRangeStats(r.timeseries, sv, ev))
      })

      onResize = () => {
        main?.resize()
        weight?.resize()
      }
      window.addEventListener('resize', onResize)
      setReady(true)
    })

    return () => {
      disposed = true
      window.removeEventListener('resize', onResize)
      main?.dispose?.()
      weight?.dispose?.()
      mainChartRef.current = null
      weightChartRef.current = null
      setReady(false)
    }
    // 仅初始化一次
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!ready || !mainChartRef.current || !weightChartRef.current || !result) {
      return
    }
    mainChartRef.current.setOption(buildMainOption(result, regimeCn), {
      notMerge: true,
    })
    weightChartRef.current.setOption(buildWeightOption(result, regimeCn), {
      notMerge: true,
    })
    const ec = echartsRef.current
    if (ec) {
      try {
        ec.connect([mainChartRef.current, weightChartRef.current])
      } catch {
        /* ignore */
      }
    }
    // 初次渲染后计算默认(全量)区间统计
    const dz = mainChartRef.current.getOption().dataZoom
    const [sv, ev] = resolveRange(dz, result.timeseries)
    onRangeRef.current(computeRangeStats(result.timeseries, sv, ev))
  }, [ready, result, regimeCn])
}
