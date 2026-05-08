'use client'

import { CompanyValuationCard, PeriodType, PeriodStats } from '../types'
import { formatNumber } from '../utils'
import { Skeleton } from './Skeleton'

interface StatsPanelProps {
  dataLoading: boolean
  pePercentileAll: number | null
  pointCount: number
  currentValuation: CompanyValuationCard | null
  selectedPeriod: PeriodType
  setSelectedPeriod: (period: PeriodType) => void
  periodStats: PeriodStats | null
}

export function StatsPanel({
  dataLoading,
  pePercentileAll,
  pointCount,
  currentValuation,
  selectedPeriod,
  setSelectedPeriod,
  periodStats,
}: StatsPanelProps) {
  return (
    <>
      <div className='grid grid-cols-2 gap-3'>
        <div className='rounded-xl bg-white p-4 shadow-sm dark:bg-[#111520]'>
          <div className='flex items-center justify-between gap-3'>
            <span className='text-xs font-medium text-gray-500 dark:text-gray-400'>PE 历史百分位</span>
            {dataLoading ? (
              <Skeleton className='h-5 w-10' />
            ) : (
              <div
                className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
                  pePercentileAll === null
                    ? 'bg-gray-100 text-gray-400 dark:bg-[#1e2435] dark:text-gray-600'
                    : pePercentileAll <= 30
                      ? 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400'
                      : pePercentileAll >= 70
                        ? 'bg-rose-50 text-rose-600 dark:bg-rose-500/10 dark:text-rose-400'
                        : 'bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-400'
                }`}
              >
                {pePercentileAll === null
                  ? '-'
                  : pePercentileAll <= 30
                    ? '低估'
                    : pePercentileAll >= 70
                      ? '高估'
                      : '合理'}
              </div>
            )}
          </div>
          {dataLoading ? (
            <div className='mt-3'>
              <Skeleton className='h-8 w-16' />
            </div>
          ) : (
            <div className='mt-3'>
              <div className='flex items-baseline gap-2'>
                <span className='text-2xl font-bold text-gray-900 dark:text-white tabular-nums'>
                  {pePercentileAll === null ? '-' : `${pePercentileAll}%`}
                </span>
                <span className='text-[11px] text-gray-400 dark:text-gray-600'>
                  {pePercentileAll !== null && `${pointCount} 个季度`}
                </span>
              </div>
            </div>
          )}
        </div>

        <div className='rounded-xl bg-gradient-to-br from-blue-50 to-indigo-50 p-4 dark:from-blue-500/[0.06] dark:to-indigo-500/[0.04]'>
          <div className='flex items-center justify-between gap-3'>
            <span className='text-xs font-medium text-gray-600 dark:text-gray-400'>利润质量</span>
            {dataLoading ? (
              <Skeleton className='h-5 w-12' />
            ) : (
              <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
                currentValuation?.profitQuality === '正常'
                  ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400'
                  : currentValuation?.profitQuality === '需调整'
                    ? 'bg-rose-100 text-rose-700 dark:bg-rose-500/10 dark:text-rose-400'
                    : 'bg-amber-100 text-amber-700 dark:bg-amber-500/10 dark:text-amber-400'
              }`}>
                {currentValuation?.profitQuality || '待确认'}
              </span>
            )}
          </div>
          {dataLoading ? (
            <div className='mt-3'>
              <Skeleton className='h-4 w-2/3' />
            </div>
          ) : (
            <div className='mt-3'>
              <div className='text-[13px] font-semibold text-gray-800 mb-1 dark:text-gray-200'>
                {currentValuation?.primaryExplanation?.title || '暂无预测/股价解释'}
              </div>
              <p className='text-[11px] text-gray-500 leading-relaxed dark:text-gray-500 line-clamp-2'>
                {currentValuation?.primaryExplanation?.body ||
                  'AI 搜索任务导入解释后，会在这里说明当前股价估值判断是否由非经常性损益驱动。'}
              </p>
            </div>
          )}
        </div>
      </div>

      <div className='rounded-xl bg-white p-4 shadow-sm dark:bg-[#111520]'>
        <span className='text-xs font-medium text-gray-500 dark:text-gray-400'>历史平均 PE</span>

        <div className='mt-3 flex gap-1 rounded-lg bg-gray-100 p-0.5 dark:bg-[#141824]'>
          {([1, 3, 5, 'all'] as PeriodType[]).map((p) => (
            <button
              key={p}
              onClick={() => setSelectedPeriod(p)}
              className={`flex-1 rounded-md px-2 py-1.5 text-[11px] font-semibold transition-all bg-transparent border-0 cursor-pointer ${
                selectedPeriod === p
                  ? 'bg-white text-gray-900 shadow-sm dark:bg-[#1e2435] dark:text-white'
                  : 'text-gray-400 hover:text-gray-700 dark:text-gray-500 dark:hover:text-gray-300'
              }`}
            >
              {p === 'all' ? '全部' : `${p}年`}
            </button>
          ))}
        </div>

        {dataLoading ? (
          <div className='mt-4'>
            <div className='flex items-baseline gap-2'>
              <Skeleton className='h-8 w-16' />
              <Skeleton className='h-3 w-14' />
            </div>
            <div className='mt-3 grid grid-cols-2 gap-2'>
              <div className='rounded-lg bg-gray-50 px-3 py-2 dark:bg-[#0e1220]'>
                <Skeleton className='h-3 w-8' />
                <Skeleton className='mt-1 h-4 w-12' />
              </div>
              <div className='rounded-lg bg-gray-50 px-3 py-2 dark:bg-[#0e1220]'>
                <Skeleton className='h-3 w-8' />
                <Skeleton className='mt-1 h-4 w-12' />
              </div>
            </div>
          </div>
        ) : (
          <div className='mt-4'>
            <div className='flex items-baseline gap-2'>
              <span className='text-2xl font-bold text-gray-900 dark:text-white tabular-nums'>
                {periodStats?.avgPe === null ? '-' : formatNumber(periodStats?.avgPe)}
              </span>
              <span className='text-[11px] text-gray-400 dark:text-gray-600'>
                {periodStats && periodStats.count > 0 && `${periodStats.count} 个季度`}
              </span>
            </div>

            <div className='mt-3 grid grid-cols-2 gap-2 text-sm'>
              <div className='rounded-lg bg-gray-50 px-3 py-2 dark:bg-[#0e1220]'>
                <div className='text-[11px] text-gray-400 dark:text-gray-600'>最低</div>
                <div className='mt-0.5 font-bold text-emerald-600 dark:text-emerald-400 tabular-nums'>
                  {periodStats?.minPe === null ? '-' : formatNumber(periodStats?.minPe)}
                </div>
              </div>
              <div className='rounded-lg bg-gray-50 px-3 py-2 dark:bg-[#0e1220]'>
                <div className='text-[11px] text-gray-400 dark:text-gray-600'>最高</div>
                <div className='mt-0.5 font-bold text-rose-600 dark:text-rose-400 tabular-nums'>
                  {periodStats?.maxPe === null ? '-' : formatNumber(periodStats?.maxPe)}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </>
  )
}
