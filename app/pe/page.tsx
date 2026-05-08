'use client'

import { useState, useCallback, useEffect, useMemo } from 'react'
import { PeriodType } from './types'
import {
  useProfitLineData,
  useValuationDetail,
  useValuationEntries,
  useChart,
  useChartOptions,
  useDerivedData,
  useFilteredEntries,
} from './hooks'
import {
  SearchHeader,
  CompanySidebar,
  ChartPanel,
  StatsPanel,
  ControlPanel,
  ExplanationsPanel,
} from './components'

export default function ProfitLinePage() {
  const [symbolInput, setSymbolInput] = useState('00700.HK')
  const [profitMultiple, setProfitMultiple] = useState(15)
  const [referenceMultiple, setReferenceMultiple] = useState(30)
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [filterQuality, setFilterQuality] = useState<'全部' | '正常' | '需调整' | '待确认'>('全部')

  const { submittedSymbol, data, state, error, fetchData } = useProfitLineData(symbolInput)
  const { valuationEntries, entriesLoading, entriesLoadingMore, totalCount, hasMore, fetchEntries, loadMore } = useValuationEntries()

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
    preparedPoints,
    latestMarketPrice,
    latestMarketDate,
    currentPe,
    alertCount,
    pePercentileAll,
    periodStats,
  } = useDerivedData(data, profitMultiple, selectedPeriod)

  const filteredEntries = useFilteredEntries(valuationEntries, searchQuery, filterQuality)

  useChartOptions(
    data,
    preparedPoints,
    profitMultiple,
    referenceMultiple,
    state,
    chartReady,
    chartRef,
  )

  const handleFetchData = useCallback(
    (symbol: string) => {
      fetchData(symbol)
    },
    [fetchData],
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

  useEffect(() => {
    const timer = window.setTimeout(() => fetchData('00700.HK'), 0)
    return () => window.clearTimeout(timer)
  }, [fetchData])

  const dataLoading = state === 'idle' || state === 'loading'

  return (
    <main className='bg-[#f4f6f9] text-gray-800 dark:bg-[#0b0f1a] dark:text-gray-100 transition-colors duration-300'>
      <section className='mx-auto flex w-full max-w-[1400px] flex-col gap-4 px-6 py-5'>
        <SearchHeader
          symbolInput={symbolInput}
          setSymbolInput={setSymbolInput}
          state={state}
          onSubmit={handleFetchData}
        />

        <div className='grid gap-5 lg:grid-cols-[280px_minmax(0,1fr)_320px]'>
          <CompanySidebar
            entries={filteredEntries}
            entriesLoading={entriesLoading}
            entriesLoadingMore={entriesLoadingMore}
            totalCount={totalCount}
            currentSymbol={data?.symbol}
            searchQuery={searchQuery}
            setSearchQuery={setSearchQuery}
            filterQuality={filterQuality}
            setFilterQuality={setFilterQuality}
            onSelect={handleSelectCompany}
            onLoadMore={loadMore}
            hasMore={hasMore}
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

            <StatsPanel
              dataLoading={dataLoading}
              pePercentileAll={pePercentileAll}
              pointCount={data?.points.filter((p) => p.ttmPe !== null).length || 0}
              currentValuation={currentValuation}
              selectedPeriod={selectedPeriod}
              setSelectedPeriod={setSelectedPeriod}
              periodStats={periodStats}
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
