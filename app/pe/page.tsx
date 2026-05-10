'use client'

import { useState, useCallback, useEffect, useMemo, useRef } from 'react'
import { PeriodType } from './types'
import {
  useProfitLineData,
  useValuationDetail,
  useValuationEntries,
  useChart,
  useChartOptions,
  useDividendChartOptions,
  useDerivedData,
} from './hooks'
import {
  CompanySidebar,
  ChartPanel,
  DividendChartPanel,
  StatsPanel,
  ControlPanel,
  ExplanationsPanel,
  NotePanel,
} from './components'
import { resolveCompanySearchSymbol } from './utils'

export default function ProfitLinePage() {
  const [symbolInput, setSymbolInput] = useState('00700.HK')
  const [profitMultiple, setProfitMultiple] = useState(15)
  const [referenceMultiple, setReferenceMultiple] = useState(30)
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [filterQuality, setFilterQuality] = useState<'全部' | '正常' | '需调整' | '待确认'>('全部')

  const searchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const handleSearchChange = useCallback((value: string) => {
    setSearchQuery(value)
    if (searchTimerRef.current) {
      clearTimeout(searchTimerRef.current)
    }
    searchTimerRef.current = setTimeout(() => {
      setDebouncedSearch(value)
    }, 300)
  }, [])

  const handleFilterChange = useCallback((value: '全部' | '正常' | '需调整' | '待确认') => {
    setFilterQuality(value)
  }, [])

  const { submittedSymbol, data, state, error, fetchData } = useProfitLineData(symbolInput)
  const { valuationEntries, entriesLoading, entriesLoadingMore, totalCount, hasMore, loadMore } = useValuationEntries(debouncedSearch, filterQuality)

  const selectedEntry = useMemo(() => {
    return (
      valuationEntries.find((e) => {
        if (e.symbol === symbolInput) return true
        const entryBase = e.symbol.replace(/\.(SH|SZ|HK)$/i, '')
        const inputBase = symbolInput.replace(/\.(SH|SZ|HK)$/i, '')
        return entryBase === inputBase
      }) || null
    )
  }, [valuationEntries, symbolInput])

  const { currentValuation, setCurrentValuation } = useValuationDetail(
    submittedSymbol,
    state,
    selectedEntry,
  )
  const { chartNode, chartRef, chartReady } = useChart()
  const {
    chartNode: dividendChartNode,
    chartRef: dividendChartRef,
    chartReady: dividendChartReady,
  } = useChart()

  const {
    preparedPoints,
    latestMarketPrice,
    latestMarketDate,
    currentPe,
    alertCount,
    pePercentileAll,
    periodStats,
  } = useDerivedData(data, profitMultiple, selectedPeriod)

  useChartOptions(
    data,
    preparedPoints,
    profitMultiple,
    referenceMultiple,
    state,
    chartReady,
    chartRef,
  )

  useDividendChartOptions(
    data,
    state,
    dividendChartReady,
    dividendChartRef,
  )

  const handleSelectCompany = useCallback(
    (symbol: string) => {
      setSymbolInput(symbol)
      const entry = valuationEntries.find((e) => e.symbol === symbol)
      if (entry) {
        setCurrentValuation(entry)
      }
      fetchData(symbol)
    },
    [fetchData, valuationEntries, setCurrentValuation],
  )

  const handleCompanySearchSubmit = useCallback(() => {
    const nextSymbol = resolveCompanySearchSymbol(searchQuery, valuationEntries)
    if (!nextSymbol) return

    setSymbolInput(nextSymbol)
    const entry = valuationEntries.find((e) => e.symbol === nextSymbol)
    if (entry) {
      setCurrentValuation(entry)
    }
    fetchData(nextSymbol)
  }, [fetchData, searchQuery, valuationEntries, setCurrentValuation])

  useEffect(() => {
    const timer = window.setTimeout(() => fetchData('00700.HK'), 0)
    return () => window.clearTimeout(timer)
  }, [fetchData])

  useEffect(() => {
    return () => {
      if (searchTimerRef.current) {
        clearTimeout(searchTimerRef.current)
      }
    }
  }, [])

  const dataLoading = state === 'idle' || state === 'loading'

  return (
    <main className='bg-[#f4f6f9] text-gray-800 dark:bg-[#0b0f1a] dark:text-gray-100 transition-colors duration-300'>
      <section className='mx-auto flex w-full max-w-[1400px] flex-col gap-4 px-6 py-5'>
        <header className='pb-4'>
          <p className='text-[10px] font-bold text-gray-500 tracking-[0.2em] uppercase dark:text-blue-400/80'>
            Profit Line Lab
          </p>
          <h1 className='mt-1 text-2xl font-bold leading-tight text-gray-900 tracking-tight dark:text-white'>
            利润线 vs 股价
          </h1>
        </header>

        <div className='grid gap-5 lg:grid-cols-[280px_minmax(0,1fr)_320px]'>
          <CompanySidebar
            entries={valuationEntries}
            entriesLoading={entriesLoading}
            entriesLoadingMore={entriesLoadingMore}
            totalCount={totalCount}
            currentSymbol={data?.symbol}
            searchQuery={searchQuery}
            setSearchQuery={handleSearchChange}
            filterQuality={filterQuality}
            setFilterQuality={handleFilterChange}
            onSelect={handleSelectCompany}
            onSearchSubmit={handleCompanySearchSubmit}
            onLoadMore={loadMore}
            hasMore={hasMore}
            searchLoading={state === 'loading'}
          />

          <div className='flex flex-col gap-5'>
            <ChartPanel
              data={data}
              submittedSymbol={submittedSymbol}
              alertCount={alertCount}
              dataLoading={dataLoading}
              state={state}
              error={error}
              chartNodeRef={chartNode}
            />

            <DividendChartPanel
              data={data}
              dataLoading={dataLoading}
              state={state}
              chartNodeRef={dividendChartNode}
            />

            <StatsPanel
              dataLoading={dataLoading}
              pePercentileAll={pePercentileAll}
              pointCount={data?.points.filter((p) => p.ttmPe !== null).length || 0}
              currentValuation={currentValuation}
              selectedPeriod={selectedPeriod}
              setSelectedPeriod={setSelectedPeriod}
              periodStats={periodStats}
            />

            <NotePanel
              currentValuation={currentValuation}
              dataLoading={dataLoading}
            />

            <ExplanationsPanel
              currentValuation={currentValuation}
              dataLoading={dataLoading}
            />
          </div>

          <ControlPanel
            profitMultiple={profitMultiple}
            setProfitMultiple={setProfitMultiple}
            referenceMultiple={referenceMultiple}
            setReferenceMultiple={setReferenceMultiple}
            latestMarketPrice={latestMarketPrice}
            latestMarketDate={latestMarketDate}
            currentPe={currentPe}
            dataLoading={dataLoading}
            data={data}
          />
        </div>
      </section>
    </main>
  )
}
