'use client'

import { useEffect, useState } from 'react'

export default function TestPage() {
  const [phase, setPhase] = useState<'idle' | 'fetching' | 'parsing' | 'done' | 'error'>('idle')
  const [size, setSize] = useState(0)
  const [elapsed, setElapsed] = useState(0)
  const [err, setErr] = useState('')
  const [nInst, setNInst] = useState(0)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      const t0 = performance.now()
      try {
        setPhase('fetching')
        const resp = await fetch('/api/ema-btc-15m', { cache: 'no-store' })
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
        // 流式读取字节数
        const reader = resp.body?.getReader()
        if (reader) {
          let recv = 0
          // eslint-disable-next-line no-constant-condition
          while (true) {
            const { done, value } = await reader.read()
            if (done) break
            if (cancelled) return
            recv += value?.length ?? 0
            setSize(recv)
            setElapsed((performance.now() - t0) / 1000)
          }
        }
        setPhase('parsing')
        const text = await resp.text()
        const data = JSON.parse(text)
        if (cancelled) return
        setNInst(data.instruments?.length ?? 0)
        setElapsed((performance.now() - t0) / 1000)
        setPhase('done')
      } catch (e) {
        setErr(e instanceof Error ? e.message : 'unknown')
        setPhase('error')
      }
    })()
    return () => { cancelled = true }
  }, [])

  return (
    <div className="max-w-3xl mx-auto my-10 p-8">
      <h1 className="text-2xl mb-4">Fetch 诊断</h1>
      <div className="space-y-2 text-sm">
        <div>阶段: <b>{phase}</b></div>
        <div>已下载: {(size / 1_000_000).toFixed(2)} MB</div>
        <div>耗时: {elapsed.toFixed(2)} s</div>
        <div>instruments 数: {nInst}</div>
        {err && <div className="text-rose-600">错误: {err}</div>}
      </div>
    </div>
  )
}
