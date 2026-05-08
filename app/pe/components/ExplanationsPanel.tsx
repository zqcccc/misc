'use client'

import { CompanyValuationCard } from '../types'

interface ExplanationsPanelProps {
  currentValuation: CompanyValuationCard | null
  dataLoading: boolean
}

const typeLabelMap: Record<string, string> = {
  profit: '利润',
  price: '股价',
  valuation: '估值',
  business: '业务',
}

const typeColorMap: Record<string, string> = {
  profit: 'text-emerald-600 dark:text-emerald-400',
  price: 'text-blue-600 dark:text-blue-400',
  valuation: 'text-violet-600 dark:text-violet-400',
  business: 'text-amber-600 dark:text-amber-400',
}

export function ExplanationsPanel({ currentValuation, dataLoading }: ExplanationsPanelProps) {
  const explanations = currentValuation?.explanations || []
  if (explanations.length === 0) return null

  return (
    <div className='rounded-xl bg-white p-4 shadow-sm dark:bg-[#111520]'>
      <div className='flex items-center justify-between gap-3'>
        <span className='text-xs font-medium text-gray-500 dark:text-gray-400'>分析报告</span>
        <span className='text-[10px] text-gray-400 dark:text-gray-600'>
          {explanations.length} 条
        </span>
      </div>

      <div className='mt-3 space-y-3'>
        {explanations.map((explanation, index) => (
          <div
            key={`${explanation.explanationType}-${explanation.title}-${index}`}
            className={`${index > 0 ? 'border-t border-gray-50 dark:border-white/[0.04] pt-3' : ''}`}
          >
            <div className='flex items-center justify-between gap-2'>
              <span className={`text-xs font-semibold ${typeColorMap[explanation.explanationType] || 'text-gray-600 dark:text-gray-400'}`}>
                {typeLabelMap[explanation.explanationType] || explanation.explanationType}
              </span>
              {explanation.confidence !== null && explanation.confidence !== undefined && (
                <span className='text-[10px] text-gray-400 dark:text-gray-600'>
                  置信度 {explanation.confidence}
                </span>
              )}
            </div>
            <div className='mt-1 text-[12px] font-medium text-gray-800 dark:text-gray-200'>
              {explanation.title}
            </div>
            <p className='mt-1 leading-5 text-[11px] text-gray-500 dark:text-gray-500'>
              {explanation.body}
            </p>
          </div>
        ))}
      </div>
    </div>
  )
}
