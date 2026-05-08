'use client'

import { ProfitLineData } from '../types'
import { currencyFormatter, formatNumber } from '../utils'
import { Skeleton } from './Skeleton'

interface ControlPanelProps {
  profitMultiple: number
  setProfitMultiple: (value: number) => void
  referenceMultiple: number
  setReferenceMultiple: (value: number) => void
  latestMarketPrice: number | null
  latestMarketDate: string | null
  currentPe: number | null
  dataLoading: boolean
  data: ProfitLineData | null
}

export function ControlPanel({
  profitMultiple,
  setProfitMultiple,
  referenceMultiple,
  setReferenceMultiple,
  latestMarketPrice,
  latestMarketDate,
  currentPe,
  dataLoading,
  data,
}: ControlPanelProps) {
  return (
    <aside className='flex flex-col gap-3 shrink-0 overflow-y-auto pr-1'>
      <div className='rounded-xl bg-white p-4 shadow-sm dark:bg-[#111520]'>
        <div className='flex items-center justify-between gap-3'>
          <label
            className='text-xs font-medium text-gray-500 dark:text-gray-400'
            htmlFor='profitMultiple'
          >
            利润线倍数
          </label>
          <span className='text-lg font-bold text-blue-600 dark:text-blue-400 tabular-nums'>
            {profitMultiple}x
          </span>
        </div>
        <input
          id='profitMultiple'
          className='mt-3 w-full h-1.5 rounded-full appearance-none cursor-pointer bg-gray-200 dark:bg-[#1e2435] accent-blue-500 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3.5 [&::-webkit-slider-thumb]:h-3.5 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-blue-500 [&::-webkit-slider-thumb]:shadow-sm [&::-moz-range-thumb]:w-3.5 [&::-moz-range-thumb]:h-3.5 [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:bg-blue-500 [&::-moz-range-thumb]:border-0'
          max='50'
          min='5'
          step='1'
          type='range'
          value={profitMultiple}
          onChange={(event) => setProfitMultiple(Number(event.target.value))}
        />
      </div>

      <div className='rounded-xl bg-white p-4 shadow-sm dark:bg-[#111520]'>
        <div className='flex items-center justify-between gap-3'>
          <label
            className='text-xs font-medium text-gray-500 dark:text-gray-400'
            htmlFor='referenceMultiple'
          >
            参考线倍数
          </label>
          <span className='text-lg font-bold text-emerald-600 dark:text-emerald-400 tabular-nums'>
            {referenceMultiple}x
          </span>
        </div>
        <input
          id='referenceMultiple'
          className='mt-3 w-full h-1.5 rounded-full appearance-none cursor-pointer bg-gray-200 dark:bg-[#1e2435] accent-emerald-500 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3.5 [&::-webkit-slider-thumb]:h-3.5 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-emerald-500 [&::-webkit-slider-thumb]:shadow-sm [&::-moz-range-thumb]:w-3.5 [&::-moz-range-thumb]:h-3.5 [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:bg-emerald-500 [&::-moz-range-thumb]:border-0'
          max='50'
          min='5'
          step='1'
          type='range'
          value={referenceMultiple}
          onChange={(event) =>
            setReferenceMultiple(Number(event.target.value))
          }
        />
      </div>

      <div className='grid grid-cols-2 gap-3'>
        <div className='rounded-xl bg-white p-4 shadow-sm dark:bg-[#111520]'>
          <div className='text-[11px] text-gray-400 dark:text-gray-600 mb-1'>最新价</div>
          {dataLoading ? (
            <Skeleton className='mt-2 h-7 w-20' />
          ) : (
            <>
              <div className='text-lg font-bold text-gray-900 dark:text-white tabular-nums'>
                {latestMarketPrice === null
                  ? '-'
                  : currencyFormatter.format(latestMarketPrice)}
              </div>
              <div className='text-[10px] text-gray-400 mt-0.5 dark:text-gray-600'>
                {latestMarketDate ? `截至 ${latestMarketDate}` : '-'}
              </div>
            </>
          )}
        </div>
        <div className='rounded-xl bg-white p-4 shadow-sm dark:bg-[#111520]'>
          <div className='text-[11px] text-gray-400 dark:text-gray-600 mb-1'>TTM PE</div>
          {dataLoading ? (
            <Skeleton className='mt-2 h-7 w-16' />
          ) : (
            <div className='text-lg font-bold text-gray-900 dark:text-white tabular-nums'>
              {formatNumber(currentPe)}
            </div>
          )}
        </div>
      </div>

      <div className='rounded-xl bg-white p-4 text-[11px] leading-5 text-gray-400 shadow-sm dark:bg-[#0e1220] dark:text-gray-600'>
        <p>
          数据源：{data?.sources.eps || 'SEC companyfacts'} /{' '}
          {data?.sources.price || 'Yahoo Finance chart'}
        </p>
        {data?.epsCurrency && data?.fxRate && (
          <p className='mt-0.5'>
            EPS 币种转换：{data.epsCurrency} → {data.currency}（汇率{' '}
            {data.fxRate.toFixed(4)}）
          </p>
        )}
        <p className='mt-0.5'>
          红色高亮点表示当季股价低于当前利润线倍数对应价格
        </p>
      </div>
    </aside>
  )
}
