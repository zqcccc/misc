'use client'

import { LoadState, ProfitLineData } from '../types'
import { Skeleton } from './Skeleton'

interface ChartPanelProps {
  data: ProfitLineData | null
  submittedSymbol: string
  alertCount: number
  dataLoading: boolean
  state: LoadState
  error: string
  chartNodeRef: React.RefObject<HTMLDivElement | null>
}

export function ChartPanel({
  data,
  submittedSymbol,
  alertCount,
  dataLoading,
  state,
  error,
  chartNodeRef,
}: ChartPanelProps) {
  return (
    <div className='rounded-xl bg-white shadow-sm dark:bg-[#0e1220] dark:shadow-none flex flex-col overflow-hidden relative p-5'>
      <div className='flex justify-between items-start mb-5'>
        <div>
          <h2 className='text-lg font-bold text-gray-900 dark:text-white'>
            {data ? `${data.symbol} · ${data.name}` : submittedSymbol}
          </h2>
          <p className='text-[11px] text-gray-400 mt-1 dark:text-gray-600'>
            {data?.ttmMethod === 'source-eps-ttm'
              ? 'TTM EPS 使用市场数据源提供值，线值随倍数实时更新'
              : '单季 EPS 滚动 4 季生成 TTM EPS，线值随倍数实时更新'}
          </p>
        </div>
        {dataLoading ? (
          <Skeleton className='h-5 w-28' />
        ) : (
          <div className={`text-xs font-semibold px-2.5 py-1 rounded-full ${
            alertCount > 0
              ? 'bg-rose-50 text-rose-600 dark:bg-rose-500/10 dark:text-rose-400'
              : 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400'
          }`}>
            {alertCount > 0 ? `${alertCount} 个季度低于利润线` : '无警示点'}
          </div>
        )}
      </div>

      <div className='relative h-[420px]'>
        <div ref={chartNodeRef} className='h-full w-full' />
        {state === 'loading' && (
          <div className='absolute inset-0 grid place-items-center bg-white/80 backdrop-blur-sm dark:bg-[#0b0f1a]/80'>
            <div className='flex items-center gap-3 text-sm text-gray-500 dark:text-gray-400'>
              <svg className='h-5 w-5 animate-spin' viewBox='0 0 24 24' fill='none'>
                <circle className='opacity-25' cx='12' cy='12' r='10' stroke='currentColor' strokeWidth='4' />
                <path className='opacity-75' fill='currentColor' d='M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z' />
              </svg>
              正在获取数据...
            </div>
          </div>
        )}
        {state === 'idle' && (
          <div className='absolute inset-0 grid place-items-center bg-white/60 backdrop-blur-sm dark:bg-[#0b0f1a]/60'>
            <span className='text-sm text-gray-400 dark:text-gray-600'>准备加载...</span>
          </div>
        )}
        {state === 'error' && (
          <div className='absolute inset-0 grid place-items-center bg-white px-6 text-center dark:bg-[#0b0f1a]'>
            <div>
              <div className='mx-auto w-10 h-10 rounded-full bg-rose-50 dark:bg-rose-500/10 flex items-center justify-center mb-3'>
                <svg className='w-5 h-5 text-rose-500' fill='none' stroke='currentColor' viewBox='0 0 24 24'>
                  <path strokeLinecap='round' strokeLinejoin='round' strokeWidth='2' d='M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z' />
                </svg>
              </div>
              <p className='text-base font-semibold text-rose-600 dark:text-rose-400'>无法绘制</p>
              <p className='mt-1.5 max-w-sm text-sm text-gray-500 dark:text-gray-500'>{error}</p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
