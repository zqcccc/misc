'use client'

import { useRef, useCallback, useState } from 'react'
import { CompanyValuationCard } from '../types'
import { formatNumber, qualityColor } from '../utils'
import { Skeleton } from './Skeleton'

interface CompanySidebarProps {
  entries: CompanyValuationCard[]
  entriesLoading: boolean
  entriesLoadingMore: boolean
  totalCount: number
  currentSymbol: string | undefined
  searchQuery: string
  setSearchQuery: (value: string) => void
  filterQuality: '全部' | CompanyValuationCard['profitQuality']
  setFilterQuality: (value: '全部' | CompanyValuationCard['profitQuality']) => void
  onSelect: (symbol: string) => void
  onLoadMore: () => void
  hasMore: boolean
}

const avatarColors = ['#6366f1', '#8b5cf6', '#ec4899', '#f59e0b', '#10b981', '#06b6d4', '#f97316', '#ef4444']

function LoadingSpinner() {
  return (
    <div className='py-3 flex justify-center items-center gap-2'>
      <div className='w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin' />
      <span className='text-[11px] text-gray-400 dark:text-gray-500'>加载中...</span>
    </div>
  )
}

export function CompanySidebar({
  entries,
  entriesLoading,
  entriesLoadingMore,
  totalCount,
  currentSymbol,
  searchQuery,
  setSearchQuery,
  filterQuality,
  setFilterQuality,
  onSelect,
  onLoadMore,
  hasMore,
}: CompanySidebarProps) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const [loadError, setLoadError] = useState(false)

  const handleScroll = useCallback(() => {
    const container = scrollRef.current
    if (!container || entriesLoading || entriesLoadingMore || !hasMore || loadError) return

    const { scrollTop, scrollHeight, clientHeight } = container
    if (scrollTop + clientHeight >= scrollHeight - 100) {
      setLoadError(false)
      onLoadMore()
    }
  }, [entriesLoading, entriesLoadingMore, hasMore, loadError, onLoadMore])

  const handleRetry = useCallback(() => {
    setLoadError(false)
    onLoadMore()
  }, [onLoadMore])

  return (
    <nav className='rounded-xl bg-white shadow-sm dark:bg-[#111520] dark:shadow-none overflow-hidden lg:max-h-[calc(100vh-140px)] flex flex-col'>
      <div className='px-3 py-3 border-b border-gray-50 dark:border-white/[0.04] space-y-2 shrink-0'>
        <div className='flex items-center justify-between'>
          <h2 className='text-xs font-semibold text-gray-500 uppercase tracking-wider dark:text-gray-400'>公司</h2>
          {entriesLoading ? (
            <Skeleton className='h-5 w-8' />
          ) : (
            <span className='bg-gray-100 text-gray-500 text-[10px] px-1.5 py-0.5 rounded font-semibold dark:bg-white/[0.06] dark:text-gray-500'>
              {entries.length}/{totalCount}
            </span>
          )}
        </div>
        <div className='relative'>
          <svg className='absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400 dark:text-gray-600' fill='none' stroke='currentColor' viewBox='0 0 24 24'>
            <path d='M21 21l-4.35-4.35M17 11A6 6 0 115 11a6 6 0 0112 0z' strokeLinecap='round' strokeLinejoin='round' strokeWidth='2' />
          </svg>
          <input
            className='w-full h-8 pl-8 pr-3 text-[11px] rounded-md bg-gray-50 border-0 outline-none focus:bg-white focus:ring-1 focus:ring-blue-500/30 dark:bg-[#141824] dark:text-gray-300 dark:placeholder-gray-600 dark:focus:bg-[#1a1f2e] transition'
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder='搜索公司、代码、标签'
          />
        </div>
        <select
          className='w-full h-8 pl-2 pr-7 text-[11px] rounded-md bg-gray-50 border-0 outline-none appearance-none cursor-pointer dark:bg-[#141824] dark:text-gray-300 transition'
          value={filterQuality}
          onChange={(e) => setFilterQuality(e.target.value as typeof filterQuality)}
          style={{
            backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 24 24' stroke='%239ca3af'%3E%3Cpath stroke-linecap='round' stroke-linejoin='round' stroke-width='2' d='M19 9l-7 7-7-7'/%3E%3C/svg%3E")`,
            backgroundRepeat: 'no-repeat',
            backgroundPosition: 'right 6px center',
            backgroundSize: '14px',
          }}
        >
          <option value='全部'>全部质量</option>
          <option value='正常'>正常</option>
          <option value='待确认'>待确认</option>
          <option value='需调整'>需调整</option>
        </select>
      </div>

      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className='p-1.5 space-y-1 overflow-y-auto flex-1'
        style={{ maxHeight: 'calc(100vh - 260px)' }}
      >
        {entriesLoading ? (
          <div className='space-y-0.5'>
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className='p-3 rounded-lg'>
                <div className='flex items-start justify-between gap-2'>
                  <div className='min-w-0 flex-1'>
                    <Skeleton className='h-4 w-3/4' />
                    <Skeleton className='mt-1.5 h-3 w-1/2' />
                  </div>
                  <Skeleton className='h-3 w-8' />
                </div>
                <div className='mt-1.5 flex items-center justify-between'>
                  <Skeleton className='h-3 w-12' />
                  <Skeleton className='h-3 w-6' />
                </div>
              </div>
            ))}
          </div>
        ) : entries.length === 0 ? (
          <div className='px-3 py-6 text-sm leading-6 text-gray-400 dark:text-gray-600 text-center'>
            {totalCount === 0 ? '暂无数据' : '无匹配结果'}
          </div>
        ) : (
          <div className='space-y-0.5'>
            {entries.map((entry) => {
              const active = entry.symbol === currentSymbol
              const colorIndex = entry.title.charCodeAt(0) % avatarColors.length
              const avatarChar = entry.title.charAt(0)

              return (
                <button
                  key={entry.id}
                  className={`w-full flex flex-col px-3 py-2.5 rounded-lg cursor-pointer transition-all duration-150 bg-transparent border-0 text-left ${
                    active
                      ? 'bg-blue-50 dark:bg-[#141824]'
                      : 'hover:bg-gray-50 dark:hover:bg-white/[0.02]'
                  }`}
                  type='button'
                  onClick={() => onSelect(entry.symbol)}
                >
                  <div className='flex items-center justify-between w-full'>
                    <div className='flex items-center gap-3 min-w-0 flex-1'>
                      <div className='w-7 h-7 rounded-md text-white flex items-center justify-center text-[11px] font-semibold shrink-0' style={{ backgroundColor: avatarColors[colorIndex] }}>
                        {avatarChar}
                      </div>
                      <div className='min-w-0'>
                        <div className={`truncate overflow-hidden text-ellipsis whitespace-nowrap text-[13px] font-medium ${
                          active
                            ? 'text-gray-900 dark:text-white'
                            : 'text-gray-700 dark:text-gray-300'
                        }`}>
                          {entry.title}
                        </div>
                        <div className='flex items-center gap-2 mt-0.5'>
                          <span className='text-[11px] text-gray-400 dark:text-gray-600'>
                            {entry.symbol}
                          </span>
                          <span className='text-[11px] text-gray-400 dark:text-gray-600'>
                            PE {formatNumber(entry.metrics.ttmPe)}
                          </span>
                        </div>
                      </div>
                    </div>
                    <div className='text-right flex flex-col items-end gap-1 shrink-0 ml-2'>
                      <span className={`text-[10px] font-semibold ${qualityColor(entry.profitQuality)}`}>
                        {entry.profitQuality}
                      </span>
                      <span className='text-xs font-semibold text-gray-600 dark:text-gray-400 tabular-nums'>
                        {entry.exploration.score === null ? '-' : entry.exploration.score}
                      </span>
                    </div>
                  </div>
                  {entry.entryNote && (
                    <div className='mt-1.5 ml-10 text-[10px] text-gray-400 dark:text-gray-500 line-clamp-1'>
                      {entry.entryNote}
                    </div>
                  )}
                </button>
              )
            })}
            {entriesLoadingMore && <LoadingSpinner />}
            {loadError && (
              <div className='py-3 text-center'>
                <span className='text-[11px] text-red-400 dark:text-red-500'>加载失败，</span>
                <button
                  type='button'
                  className='text-[11px] text-blue-500 hover:text-blue-600 underline'
                  onClick={handleRetry}
                >
                  点击重试
                </button>
              </div>
            )}
            {!hasMore && entries.length > 0 && !entriesLoadingMore && (
              <div className='py-3 text-center text-[11px] text-gray-400 dark:text-gray-600'>
                已加载全部 {totalCount} 条
              </div>
            )}
          </div>
        )}
      </div>
    </nav>
  )
}
