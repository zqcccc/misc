'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import type { OverviewPayload } from './types'

export type LoadState = 'idle' | 'loading' | 'ready' | 'error'

interface UseOverviewResult {
  data: OverviewPayload | null
  state: LoadState
  error: string
  generatedAt: string | null
  refresh: () => void
}

/**
 * 拉取 /api/ema-backtest 概览数据. 每 30s 自动刷新一次, 让 "当前持仓" 标记
 * 跟上 daemon 每 15m 写入的 state_*.json.
 */
export function useOverview(autoRefreshMs = 30_000): UseOverviewResult {
  const [data, setData] = useState<OverviewPayload | null>(null)
  const [state, setState] = useState<LoadState>('idle')
  const [error, setError] = useState('')
  const [generatedAt, setGeneratedAt] = useState<string | null>(null)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const fetchData = useCallback(async () => {
    if (state !== 'ready') setState('loading')
    try {
      const resp = await fetch('/api/ema-backtest', { cache: 'no-store' })
      const payload = await resp.json()
      if (!resp.ok) {
        throw new Error(payload?.message || `HTTP ${resp.status}`)
      }
      setData(payload as OverviewPayload)
      setGeneratedAt(resp.headers.get('x-overview-generated') || payload.generated_at)
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
    timerRef.current = setInterval(() => {
      fetchData()
    }, autoRefreshMs)
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [autoRefreshMs, fetchData])

  return {
    data,
    state,
    error,
    generatedAt,
    refresh: fetchData,
  }
}

/**
 * echarts 懒加载 hook (与 app/pe/hooks.ts 的 useChart 同款, 简化版).
 */
export function useChart() {
  const chartNode = useRef<HTMLDivElement | null>(null)
  const chartRef = useRef<any>(null)
  const [chartReady, setChartReady] = useState(false)

  useEffect(() => {
    let disposed = false
    let resizeFn = () => {}

    import('echarts').then((echarts) => {
      if (disposed || !chartNode.current) return
      chartRef.current = echarts.init(chartNode.current, undefined, {
        renderer: 'canvas',
      })
      resizeFn = () => chartRef.current?.resize()
      window.addEventListener('resize', resizeFn)
      resizeFn()
      setChartReady(true)
    })

    return () => {
      disposed = true
      window.removeEventListener('resize', resizeFn)
      chartRef.current?.dispose?.()
      chartRef.current = null
      setChartReady(false)
    }
  }, [])

  return { chartNode, chartRef, chartReady }
}
