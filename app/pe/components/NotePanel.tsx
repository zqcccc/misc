'use client'

import { CompanyValuationCard } from '../types'
import { Skeleton } from './Skeleton'

interface NotePanelProps {
  currentValuation: CompanyValuationCard | null
  dataLoading: boolean
}

export function NotePanel({ currentValuation, dataLoading }: NotePanelProps) {
  const entryNote = currentValuation?.entryNote

  if (!entryNote && !dataLoading) return null

  return (
    <div className='rounded-xl bg-white p-4 shadow-sm dark:bg-[#111520]'>
      <div className='flex items-center justify-between gap-3'>
        <span className='text-xs font-medium text-gray-600 dark:text-gray-300'>公司备注</span>
        {currentValuation?.entryType && (
          <span className='text-[10px] text-gray-500 dark:text-gray-500'>
            {currentValuation.entryType === 'discovered' ? 'AI 发现' : '手动添加'}
          </span>
        )}
      </div>

      {dataLoading ? (
        <div className='mt-3 space-y-2'>
          <Skeleton className='h-3 w-full' />
          <Skeleton className='h-3 w-3/4' />
        </div>
      ) : (
        <p className='mt-3 text-[11px] leading-5 text-gray-600 dark:text-gray-300 whitespace-pre-wrap'>
          {entryNote}
        </p>
      )}
    </div>
  )
}
