'use client'

import { useEffect, useState } from 'react'

export default function Btc15mMinimalPage() {
  const [state, setState] = useState<'idle' | 'fetching' | 'done' | 'error'>('idle')
  const [data, setData] = useState<any>(null)
  const [err, setErr] = useState('')
  const [elapsedMs, setElapsedMs] = useState(0)

  useEffect(() => {
    let cancelled = false
    const t0 = performance.now()
    ;(async () => {
      setState('fetching')
      try {
        const r = await fetch('/api/ema-btc-15m', { cache: 'no-store' })
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        const j = await r.json()
        if (cancelled) return
        setData(j)
        setState('done')
        setElapsedMs(performance.now() - t0)
      } catch (e) {
        if (cancelled) return
        setErr(e instanceof Error ? e.message : 'unknown')
        setState('error')
      }
    })()
    return () => { cancelled = true }
  }, [])

  return (
    <div className="max-w-4xl mx-auto my-10 p-8">
      <h1 className="text-2xl mb-4">BTC 15m · 最小验证版</h1>
      {!data && state === 'idle' && <div>等待 mount...</div>}
      {!data && state === 'fetching' && <div>FETCH 中 (loading ~4MB JSON)...</div>}
      {state === 'error' && <div className="text-rose-600 mb-4">错误: {err}</div>}
      {data && state === 'done' && (
        <div className="space-y-4">
          <div className="p-3 rounded bg-emerald-50 dark:bg-emerald-950/30 text-emerald-700 dark:text-emerald-300">
            ✓ 加载完成, 耗时 {elapsedMs.toFixed(0)}ms ({(elapsedMs / 1000).toFixed(2)}s)
          </div>
          <div className="text-sm">
            <div>generated_at: {data.generated_at ?? '-'}</div>
            <div>instruments 数: <b className="text-purple-600">{data.instruments?.length ?? 0}</b></div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="bg-gray-100 dark:bg-gray-800">
                  <th className="border p-2 text-left">配置</th>
                  <th className="border p-2 text-right">净收益</th>
                  <th className="border p-2 text-right">买入持有</th>
                  <th className="border p-2 text-right">交易次数</th>
                  <th className="border p-2 text-right">回撤</th>
                  <th className="border p-2 text-right">胜率</th>
                  <th className="border p-2 text-right">price pts</th>
                </tr>
              </thead>
              <tbody>
                {data.instruments?.map((inst: any) => {
                  const s = inst.stats
                  return (
                    <tr key={inst.name}>
                      <td className="border p-2">{inst.name}</td>
                      <td className="border p-2 text-right font-mono text-emerald-600">{(s.strategy_return * 100).toFixed(2)}%</td>
                      <td className="border p-2 text-right font-mono">{(s.hold_return * 100).toFixed(2)}%</td>
                      <td className="border p-2 text-right">{s.reversals}</td>
                      <td className="border p-2 text-right text-rose-600">{(s.max_drawdown * 100).toFixed(2)}%</td>
                      <td className="border p-2 text-right">{(s.win_rate * 100).toFixed(1)}%</td>
                      <td className="border p-2 text-right">{inst.series?.price?.length ?? 0}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <div className="text-xs text-gray-500">
            如果你能看到这个表, 说明 fetch + React hydrate + 状态更新全部正常.<br/>
            下一步是加 echarts 渲染. 之前如果一直卡在"加载 BTC 15m 研究数据中...",
            几乎都是因为 18MB JSON 加载+解析+echarts 3万点双 grid 渲染慢导致 UI 主线程冻结.
          </div>
        </div>
      )}
    </div>
  )
}
