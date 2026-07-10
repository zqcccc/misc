'use client'

import { useCallback, useEffect, useRef, useState } from 'react'

/** 跟随 <html class="dark"> 的主题开关, 用 MutationObserver 实时响应切换 */
function useIsDark(): boolean {
  const [dark, setDark] = useState(() =>
    typeof document !== 'undefined'
      ? document.documentElement.classList.contains('dark')
      : false,
  )
  useEffect(() => {
    const update = () =>
      setDark(document.documentElement.classList.contains('dark'))
    update()
    const ob = new MutationObserver(update)
    ob.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['class'],
    })
    return () => ob.disconnect()
  }, [])
  return dark
}
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
// 简单 LRU: 超过上限时删最早插入的条目 (利用 Map 的插入顺序)
const RESULT_CACHE_MAX = 50
const resultCache = new Map<string, MarketResult>()
function cacheResult(key: string, val: MarketResult) {
  if (resultCache.has(key)) {
    // 命中后先删再插, 让它变成"最近使用"排到末尾
    resultCache.delete(key)
  } else if (resultCache.size >= RESULT_CACHE_MAX) {
    // 超上限: 删最早 (Map 迭代顺序 = 插入顺序, 第一个即最久未用)
    const oldest = resultCache.keys().next().value
    if (oldest !== undefined) resultCache.delete(oldest)
  }
  resultCache.set(key, val)
}

/** 按需加载单标的完整结果(含 timeseries), key 随 generatedAt 失效 */
export function useMarketResult(label: string | null, generatedAt: string | null) {
  const [result, setResult] = useState<MarketResult | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!label) return
    const key = `${label}@${generatedAt}`
    const cached = resultCache.get(key)
    if (cached) {
      // 命中: 删后重插, 把它挪到末尾表示最近使用 (LRU)
      resultCache.delete(key)
      resultCache.set(key, cached)
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
          cacheResult(key, d as MarketResult)
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
  // 记录上次渲染的标的 label, 用于区分"切换标的(应重置 zoom)"和"同标的自动刷新(应保留 zoom)"
  const lastLabelRef = useRef<string | null>(null)

  const dark = useIsDark()

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

    // 同标的自动刷新时, 保留用户当前 dataZoom 的百分比区间,
    // 避免 60s 轮询把用户选好的时间段重置回全量。
    // 切换标的时(lastLabel 不同)则正常重置为全量。
    const isSameSymbol = lastLabelRef.current === result.meta.label
    lastLabelRef.current = result.meta.label

    let savedStart: number | undefined
    let savedEnd: number | undefined
    if (isSameSymbol) {
      try {
        const opt = mainChartRef.current.getOption()
        const dzArr = Array.isArray(opt?.dataZoom) ? opt.dataZoom : []
        const dz: any = dzArr.find(
          (d: any) => typeof d?.start === 'number' && typeof d?.end === 'number',
        )
        if (dz) {
          savedStart = dz.start
          savedEnd = dz.end
        }
      } catch {
        /* ignore */
      }
    }

    const mainOption = buildMainOption(result, regimeCn, dark)
    const weightOption = buildWeightOption(result, regimeCn, dark)

    if (savedStart != null && savedEnd != null) {
      // 用百分比而非 startValue/endValue: 数据新增 bar 后百分比位置自适应
      mainOption.dataZoom = (mainOption.dataZoom || []).map((dz: any) => ({
        ...dz,
        start: savedStart,
        end: savedEnd,
      }))
      weightOption.dataZoom = (weightOption.dataZoom || []).map((dz: any) => ({
        ...dz,
        start: savedStart,
        end: savedEnd,
      }))
    }

    mainChartRef.current.setOption(mainOption, { notMerge: true })
    weightChartRef.current.setOption(weightOption, { notMerge: true })

    const ec = echartsRef.current
    if (ec) {
      try {
        ec.connect([mainChartRef.current, weightChartRef.current])
      } catch {
        /* ignore */
      }
    }
    // setOption 后读取实际 dataZoom 状态计算区间统计(保留了 zoom 则用 zoom, 否则全量)
    const dz = mainChartRef.current.getOption().dataZoom
    const [sv, ev] = resolveRange(dz, result.timeseries)
    onRangeRef.current(computeRangeStats(result.timeseries, sv, ev))
  }, [ready, result, regimeCn, dark])
}
