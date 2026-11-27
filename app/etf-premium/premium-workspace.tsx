'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { ECharts } from 'echarts'
import {
  filterRows,
  formatAmountCny,
  formatPrice,
  formatSignedPercent,
  type EtfPremiumRow,
  type SortKey,
} from '@/lib/etf-premium'

type SnapshotRow = EtfPremiumRow & { isStaleQuote: boolean }

type SnapshotResponse = {
  ok: true
  generatedAt: string
  quoteSource: 'eastmoney' | 'tencent'
  quoteSourceNote: string | null
  universe: { navDate: string | null; etfCount: number; excludedNonEtf: number; excludedOther: number }
  counts: {
    crossBorder: number
    qdii: number
    connect: number
    withPremium: number
    missingIopv: number
    ungrouped: number
  }
  groups: Array<{ key: string; label: string; market: string; count: number }>
  latestQuoteDate: string | null
  rows: SnapshotRow[]
}

type ApiErrorPayload = { ok: false; stage: string; message: string }

type DetailResponse = {
  ok: true
  code: string
  name: string | null
  mechanism: 'qdii' | 'connect' | null
  fund: {
    fullName: string | null
    ftype: string | null
    purchaseStatus: string | null
    redeemStatus: string | null
    navLatest: number | null
    shortName?: string | null
  }
  history: {
    priceSource: 'eastmoney' | 'tencent'
    series: Array<{ date: string; close: number; nav: number; premiumPct: number }>
    firstDate: string | null
    lastDate: string | null
    navLastDate: string | null
    navLagDays: number | null
    navLagNote: string | null
  }
  notes: string[]
}

const SORT_OPTIONS: Array<{ value: SortKey; label: string }> = [
  { value: 'premium_desc', label: '溢价率 从高到低' },
  { value: 'premium_asc', label: '溢价率 从低到高' },
  { value: 'premium_abs_desc', label: '绝对溢价 从大到小' },
  { value: 'amount_desc', label: '成交额 从大到小' },
  { value: 'code_asc', label: '按代码' },
]

const THRESHOLD_OPTIONS = [0, 2, 5, 10]
const RANGE_OPTIONS = [90, 180, 365]

async function readJson(response: Response): Promise<SnapshotResponse | DetailResponse | ApiErrorPayload> {
  try {
    return await response.json()
  } catch {
    return { ok: false, stage: 'network', message: `响应不是合法 JSON（HTTP ${response.status}）` }
  }
}

function isApiError(payload: SnapshotResponse | DetailResponse | ApiErrorPayload): payload is ApiErrorPayload {
  return payload.ok === false
}

/** 空行占位：避免每次渲染生成新数组引用打断 useMemo。 */
const EMPTY_ROWS: SnapshotRow[] = []

/** 深浅主题跟随 html class（globals.css 的 .dark），图表颜色随之重绘。 */

function useThemeFlag(): 'light' | 'dark' {
  const [theme, setTheme] = useState<'light' | 'dark'>('light')
  useEffect(() => {
    const root = document.documentElement
    const update = () => setTheme(root.classList.contains('dark') ? 'dark' : 'light')
    update()
    const observer = new MutationObserver(update)
    observer.observe(root, { attributes: true, attributeFilter: ['class'] })
    return () => observer.disconnect()
  }, [])
  return theme
}

/** ECharts tooltip 回调的最小字段面，避免引入 any。 */
type TooltipParam = {
  marker: string
  seriesName: string
  value: unknown
  axisValueLabel?: string
}

function PremiumChart({ series, theme }: { series: DetailResponse['history']['series']; theme: 'light' | 'dark' }) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<ECharts | null>(null)

  useEffect(() => {
    let cancelled = false
    import('echarts').then((echarts) => {
      if (cancelled || !containerRef.current) return
      const styles = getComputedStyle(document.documentElement)
      const cssVar = (name: string, fallback: string) => styles.getPropertyValue(name).trim() || fallback
      const ink = cssVar('--site-ink', '#151b26')
      const muted = cssVar('--site-muted', '#5f6b7a')
      const line = cssVar('--site-line', '#d8dee7')
      const link = cssVar('--site-link', '#075a9c')
      const signal = cssVar('--site-signal', '#b98200')

      if (!chartRef.current) {
        chartRef.current = echarts.init(containerRef.current)
      }
      chartRef.current.setOption(
        {
          animationDuration: 400,
          color: [link, muted, signal],
          grid: { left: 10, right: 14, top: 34, bottom: 48, containLabel: true },
          legend: { top: 0, textStyle: { color: muted, fontSize: 12 } },
          tooltip: {
            trigger: 'axis',
            backgroundColor: cssVar('--site-panel', '#ffffff'),
            formatter: (params: TooltipParam[]) => {
              if (!params.length) return ''
              const rows = params
                .map((item) => {
                  const value = Array.isArray(item.value) ? item.value[1] : item.value
                  const suffix = item.seriesName === '溢价率' ? '%' : ''
                  const digits = item.seriesName === '溢价率' ? 2 : 3
                  return `<div>${item.marker} ${item.seriesName} ${Number(value).toFixed(digits)}${suffix}</div>`
                })
                .join('')
              return `<div>${params[0].axisValueLabel ?? ''}</div>${rows}`
            },
          },
          xAxis: {
            type: 'time',
            axisLine: { lineStyle: { color: line } },
            axisLabel: { color: muted, formatter: '{MM}-{dd}' },
            splitLine: { show: false },
          },
          yAxis: [
            {
              type: 'value',
              scale: true,
              axisLabel: { color: muted, formatter: '{value}%' },
              splitLine: { lineStyle: { color: line, opacity: 0.55 } },
            },
            {
              type: 'value',
              scale: true,
              axisLabel: { color: muted, fontSize: 11 },
              splitLine: { show: false },
            },
          ],
          dataZoom: [
            { type: 'inside' },
            { type: 'slider', height: 18, bottom: 8, borderColor: line, textStyle: { color: muted } },
          ],
          series: [
            {
              name: '溢价率',
              type: 'line',
              yAxisIndex: 0,
              showSymbol: false,
              data: series.map((point) => [point.date, Number(point.premiumPct.toFixed(2))]),
              lineStyle: { width: 2, color: link },
              itemStyle: { color: link },
              markLine: {
                silent: true,
                symbol: 'none',
                label: { show: false },
                lineStyle: { color: muted, type: 'dashed', width: 1 },
                data: [{ yAxis: 0 }],
              },
            },
            {
              name: '收盘价',
              type: 'line',
              yAxisIndex: 1,
              showSymbol: false,
              data: series.map((point) => [point.date, point.close]),
              lineStyle: { width: 1, color: muted },
              itemStyle: { color: muted },
            },
            {
              name: '单位净值',
              type: 'line',
              yAxisIndex: 1,
              showSymbol: false,
              data: series.map((point) => [point.date, point.nav]),
              lineStyle: { width: 1, color: signal },
              itemStyle: { color: signal },
            },
          ],
        },
        true,
      )
      chartRef.current.resize()
    })
    return () => {
      cancelled = true
    }
  }, [series, theme])

  useEffect(() => {
    const onResize = () => chartRef.current?.resize()
    window.addEventListener('resize', onResize)
    return () => {
      window.removeEventListener('resize', onResize)
      chartRef.current?.dispose()
      chartRef.current = null
    }
  }, [])

  return <div className='etf-premium-chart' ref={containerRef} role='img' aria-label='历史溢价率与收盘价、单位净值折线图' />
}

function DetailPanel({
  code,
  snapshotRow,
  onClose,
  theme,
}: {
  code: string
  snapshotRow: SnapshotRow | undefined
  onClose: () => void
  theme: 'light' | 'dark'
}) {
  const [detail, setDetail] = useState<DetailResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [days, setDays] = useState(180)

  useEffect(() => {
    const controller = new AbortController()
    fetch(`/api/etf-premium/detail?code=${code}&days=${days}`, { signal: controller.signal })
      .then((response) => readJson(response))
      .then((payload) => {
        if (controller.signal.aborted) return
        if (isApiError(payload)) {
          setError(payload.message)
        } else if ('history' in payload) {
          setDetail(payload)
        } else {
          setError('详情数据结构异常')
        }
        setLoading(false)
      })
      .catch((err) => {
        if (controller.signal.aborted) return
        setError(err instanceof Error ? err.message : String(err))
        setLoading(false)
      })
    return () => controller.abort()
  }, [code, days])

  /** 区间切换在事件处理器内同步重置状态；code 变化由父级 key 重挂载处理。 */
  const changeDays = (option: number) => {
    if (option === days) return
    setDays(option)
    setLoading(true)
    setError(null)
    setDetail(null)
  }

  const mechanismText = detail?.mechanism ? (detail.mechanism === 'qdii' ? 'QDII' : '港股通') : snapshotRow?.mechanismLabel
  const indexLabel = snapshotRow?.indexLabel

  return (
    <section
      id='etf-premium-detail'
      className='etf-premium-detail'
      aria-label={`历史溢价详情：${snapshotRow?.name ?? code}`}
    >
      <div className='etf-premium-detail-head'>
        <h3>{detail?.name ?? snapshotRow?.name ?? code}</h3>
        <span className='etf-premium-chip'>{code}</span>
        {mechanismText && <span className='etf-premium-chip'>{mechanismText}</span>}
        {indexLabel && <span className='etf-premium-chip'>{indexLabel}</span>}
        <button type='button' className='etf-premium-detail-close' onClick={onClose}>
          关闭
        </button>
      </div>

      {loading && (
        <p className='etf-premium-meta'>正在重建该标的的历史溢价序列，需要拉取日线与逐页净值…</p>
      )}
      {!loading && error && (
        <div className='etf-premium-state is-error'>
          <strong>历史溢价序列不可用</strong>
          {error}
        </div>
      )}
      {!loading && detail && (
        <>
          <p className='etf-premium-detail-facts'>
            {detail.fund.fullName && (
              <>
                基金全名：{detail.fund.fullName}
                <br />
              </>
            )}
            {detail.fund.ftype && (
              <>
                上游类型：{detail.fund.ftype} ·{' '}
              </>
            )}
            申购状态：{detail.fund.purchaseStatus ?? '未知'} · 赎回状态：{detail.fund.redeemStatus ?? '未知'} ·
            最新单位净值：{formatPrice(detail.fund.navLatest)}（披露于 {detail.history.navLastDate ?? '未知'}）
            <br />
            序列区间：{detail.history.firstDate} ~ {detail.history.lastDate}（{detail.history.series.length} 个交易日）·
            价格来源：{detail.history.priceSource === 'eastmoney' ? '东方财富' : '腾讯'} · 净值来源：天天基金
            {detail.history.navLagNote && (
              <>
                <br />
                {detail.history.navLagNote}
              </>
            )}
          </p>

          <div className='etf-premium-detail-range' role='group' aria-label='历史区间'>
            {RANGE_OPTIONS.map((option) => (
              <button
                key={option}
                type='button'
                aria-pressed={days === option}
                onClick={() => changeDays(option)}
              >
                近 {option} 天
              </button>
            ))}
          </div>

          <PremiumChart series={detail.history.series} theme={theme} />

          <ul className='etf-premium-detail-notes'>
            {detail.notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </>
      )}
    </section>
  )
}

export default function PremiumWorkspace() {
  const [snapshot, setSnapshot] = useState<SnapshotResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [query, setQuery] = useState('')
  const [groupKey, setGroupKey] = useState('all')
  const [minAbsPremium, setMinAbsPremium] = useState(0)
  const [sort, setSort] = useState<SortKey>('premium_desc')
  const [selectedCode, setSelectedCode] = useState<string | null>(null)
  const theme = useThemeFlag()

  const load = useCallback(async (refresh: boolean) => {
    try {
      const response = await fetch(`/api/etf-premium${refresh ? '?refresh=1' : ''}`)
      const payload = await readJson(response)
      if (isApiError(payload)) {
        setError(payload.message)
        if (!refresh) setSnapshot(null)
      } else if ('rows' in payload) {
        setSnapshot(payload)
      } else {
        setError('快照数据结构异常')
        if (!refresh) setSnapshot(null)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      if (!refresh) setSnapshot(null)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    fetch('/api/etf-premium', { signal: controller.signal })
      .then(readJson)
      .then((payload) => {
        if (controller.signal.aborted) return
        if (isApiError(payload)) {
          setError(payload.message)
          setSnapshot(null)
        } else if ('rows' in payload) {
          setSnapshot(payload)
        } else {
          setError('快照数据结构异常')
          setSnapshot(null)
        }
      })
      .catch((err) => {
        if (controller.signal.aborted) return
        setError(err instanceof Error ? err.message : String(err))
        setSnapshot(null)
      })
      .finally(() => {
        if (controller.signal.aborted) return
        setLoading(false)
        setRefreshing(false)
      })
    return () => controller.abort()
  }, [])

  const rows = snapshot?.rows ?? EMPTY_ROWS
  const visibleRows = useMemo(
    () => filterRows(rows, { query, groupKey, minAbsPremium: minAbsPremium || null, sort }),
    [rows, query, groupKey, minAbsPremium, sort],
  )

  const generatedAtText = snapshot
    ? new Date(snapshot.generatedAt).toLocaleTimeString('zh-Hans', { hour12: false })
    : null
  const selectedRow = snapshot?.rows.find((row) => row.code === selectedCode)

  return (
    <section className='etf-premium-section' aria-labelledby='etf-workspace'>
      <h2 id='etf-workspace'>实时快照</h2>

      {loading && !snapshot && (
        <div className='etf-premium-state' aria-busy='true'>
          <strong>正在加载跨境 ETF 快照</strong>
          正在拉取场内基金名单与批量行情，通常需要几秒钟；失败时这里会给出具体原因。
        </div>
      )}

      {!loading && error && !snapshot && (
        <div className='etf-premium-state is-error' role='alert'>
          <strong>快照获取失败</strong>
          {error}
          <div style={{ marginTop: 12 }}>
            <button type='button' className='etf-btn-primary' style={{ height: 38, padding: '0 16px', borderRadius: 9, border: '1px solid var(--site-link)', background: 'var(--site-link)', color: '#fff', cursor: 'pointer' }} onClick={() => { setError(null); setLoading(true); void load(false) }}>
              重试
            </button>
          </div>
        </div>
      )}

      {snapshot && (
        <>
          <div className='etf-premium-toolbar'>
            <input
              type='search'
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder='搜索名称或代码'
              aria-label='按名称或代码搜索'
            />
            <select
              value={groupKey}
              onChange={(event) => setGroupKey(event.target.value)}
              aria-label='按跟踪指数筛选'
            >
              <option value='all'>全部指数分组</option>
              {snapshot.groups.map((group) => (
                <option key={group.key} value={group.key}>
                  {group.label}（{group.count}）
                </option>
              ))}
            </select>
            <select
              value={minAbsPremium}
              onChange={(event) => setMinAbsPremium(Number(event.target.value))}
              aria-label='按绝对溢价阈值筛选'
            >
              {THRESHOLD_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option === 0 ? '不限溢价幅度' : `|溢价| ≥ ${option}%`}
                </option>
              ))}
            </select>
            <select
              value={sort}
              onChange={(event) => setSort(event.target.value as SortKey)}
              aria-label='选择排序方式'
            >
              {SORT_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <button
              type='button'
              className='etf-btn-primary'
              disabled={refreshing}
              onClick={() => { setRefreshing(true); setError(null); void load(true) }}
            >
              {refreshing ? '刷新中…' : '手动刷新'}
            </button>
          </div>

          <p className='etf-premium-meta'>
            共 {snapshot.counts.crossBorder} 只跨境 ETF（QDII {snapshot.counts.qdii} · 港股通{' '}
            {snapshot.counts.connect}）· 可计算溢价 {snapshot.counts.withPremium} 只 · IOPV 缺失{' '}
            {snapshot.counts.missingIopv} 只 · 未分组 {snapshot.counts.ungrouped} 只 · 行情来源：
            {snapshot.quoteSource === 'eastmoney' ? '东方财富' : '腾讯公开行情'} · 行情日期：
            {snapshot.latestQuoteDate ?? '未知'} · 快照生成于 {generatedAtText}（服务端缓存 60 秒）
            {snapshot.quoteSourceNote && (
              <>
                <br />
                {snapshot.quoteSourceNote}
              </>
            )}
          </p>

          {error && (
            <p className='etf-premium-meta' role='alert'>
              刷新失败：{error}。正在显示上一次成功获取的快照，可再次点击手动刷新。
            </p>
          )}

          {visibleRows.length === 0 ? (
            <div className='etf-premium-state'>
              <strong>没有符合筛选条件的标的</strong>
              调整搜索词、指数分组或溢价阈值后再试。
            </div>
          ) : (
            <div className='etf-premium-tablewrap'>
              <table className='etf-premium-table'>
                <thead>
                  <tr>
                    <th scope='col'>名称 / 代码</th>
                    <th scope='col'>机制</th>
                    <th scope='col'>跟踪指数分组</th>
                    <th scope='col' className='num'>
                      最新价
                    </th>
                    <th scope='col' className='num'>
                      IOPV
                    </th>
                    <th scope='col' className='num'>
                      溢价率
                    </th>
                    <th scope='col' className='num'>
                      成交额
                    </th>
                    <th scope='col'>行情时间</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleRows.map((row) => (
                    <tr key={row.code}>
                      <td>
                        <button
                          type='button'
                          className='etf-premium-name-btn'
                          aria-expanded={selectedCode === row.code}
                          aria-controls='etf-premium-detail'
                          onClick={() => setSelectedCode(selectedCode === row.code ? null : row.code)}
                        >
                          {row.name}
                          <span className='etf-premium-code'>{row.code}</span>
                        </button>
                      </td>
                      <td>{row.mechanismLabel}</td>
                      <td>
                        {row.indexLabel ?? '未分组'}
                        {row.isLowestPremiumInGroup && (
                          <span className='etf-premium-low' title='同组内溢价率最低的载体'>
                            组内低溢价
                          </span>
                        )}
                      </td>
                      <td className='num'>{formatPrice(row.price)}</td>
                      <td className='num'>
                        {row.iopv == null ? (
                          <span className='missing' title={row.missing.join('；')}>
                            —
                          </span>
                        ) : (
                          formatPrice(row.iopv)
                        )}
                      </td>
                      <td
                        className={`num ${
                          row.premiumPct == null ? '' : row.premiumPct > 0 ? 'etf-premium-premium pos' : row.premiumPct < 0 ? 'etf-premium-premium neg' : ''
                        }`}
                        title={row.missing.join('；') || undefined}
                      >
                        {row.premiumPct == null ? <span className='missing'>—</span> : formatSignedPercent(row.premiumPct)}
                      </td>
                      <td className='num'>{formatAmountCny(row.amountCny)}</td>
                      <td>
                        {row.quoteTimeText ?? '—'}
                        {row.isStaleQuote && (
                          <span className='etf-premium-stale' title='行情时间落后于本次快照里的最新行情'>
                            （非最新）
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <p className='etf-premium-legend'>
            “—”表示该字段上游缺失或无效（把指针悬停在单元格上可见原因），不是 0。溢价率 =（场内价 − IOPV）÷
            IOPV；点击名称查看按当日收盘价与当日单位净值重建的历史溢价序列及其披露滞后说明。
          </p>

          {selectedCode && (
            <DetailPanel
              key={selectedCode}
              code={selectedCode}
              snapshotRow={selectedRow}
              onClose={() => setSelectedCode(null)}
              theme={theme}
            />
          )}
        </>
      )}
    </section>
  )
}
