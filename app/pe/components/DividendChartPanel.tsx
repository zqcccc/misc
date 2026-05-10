'use client'

import { LoadState, ProfitLineData } from '../types'
import { buildDividendChartSource } from '../chart-data'
import { Skeleton } from './Skeleton'

interface DividendChartPanelProps {
  data: ProfitLineData | null
  dataLoading: boolean
  state: LoadState
  chartNodeRef: React.RefObject<HTMLDivElement | null>
}

export function DividendChartPanel({
  data,
  dataLoading,
  state,
  chartNodeRef,
}: DividendChartPanelProps) {
  const dividendYears = buildDividendChartSource(data?.dividends).length

  return (
    <div className='rounded-xl bg-white shadow-sm dark:bg-[#0e1220] dark:shadow-none flex flex-col overflow-hidden relative p-5'>
      <div className='flex justify-between items-start mb-4'>
        <div>
          <h2 className='text-lg font-bold text-gray-900 dark:text-white'>历史分红</h2>
          <p className='text-[11px] text-gray-500 mt-1 dark:text-gray-500'>
            按年度汇总每股现金分红，来源为行情历史事件
          </p>
        </div>
        {dataLoading ? (
          <Skeleton className='h-5 w-24' />
        ) : (
          <div className='rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400'>
            {dividendYears > 0 ? `${dividendYears} 年记录` : '暂无记录'}
          </div>
        )}
      </div>

      <div className='relative h-[280px]'>
        <div ref={chartNodeRef} className='h-full w-full' />
        {state === 'loading' && (
          <div className='absolute inset-0 grid place-items-center bg-white/80 backdrop-blur-sm dark:bg-[#0b0f1a]/80'>
            <div className='flex items-center gap-3 text-sm text-gray-600 dark:text-gray-300'>
              <svg className='h-5 w-5 animate-spin' viewBox='0 0 24 24' fill='none'>
                <circle className='opacity-25' cx='12' cy='12' r='10' stroke='currentColor' strokeWidth='4' />
                <path className='opacity-75' fill='currentColor' d='M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z' />
              </svg>
              正在获取分红...
            </div>
          </div>
        )}
        {state === 'ready' && dividendYears === 0 && (
          <div className='absolute inset-0 grid place-items-center bg-white/70 px-6 text-center backdrop-blur-sm dark:bg-[#0b0f1a]/70'>
            <span className='text-sm text-gray-500 dark:text-gray-500'>当前数据源没有返回历史分红记录</span>
          </div>
        )}
      </div>
    </div>
  )
}
