'use client'

import { FormEvent } from 'react'
import { LoadState } from '../types'

interface SearchHeaderProps {
  symbolInput: string
  setSymbolInput: (value: string) => void
  state: LoadState
  onSubmit: (symbol: string) => void
}

export function SearchHeader({ symbolInput, setSymbolInput, state, onSubmit }: SearchHeaderProps) {
  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    onSubmit(symbolInput)
  }

  return (
    <header className='flex flex-col gap-4 pb-4 lg:flex-row lg:items-end lg:justify-between'>
      <div>
        <p className='text-[10px] font-bold text-gray-400 tracking-[0.2em] uppercase dark:text-blue-400/60'>
          Profit Line Lab
        </p>
        <h1 className='mt-1 text-2xl font-bold leading-tight text-gray-900 tracking-tight dark:text-white'>
          利润线 vs 股价
        </h1>
      </div>

      <form
        className='flex w-full flex-col gap-3 sm:flex-row lg:w-auto'
        onSubmit={handleSubmit}
      >
        <div className='relative lg:w-[280px]'>
          <svg className='absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 dark:text-gray-500' fill='none' stroke='currentColor' viewBox='0 0 24 24'>
            <path d='M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z' strokeLinecap='round' strokeLinejoin='round' strokeWidth='2' />
          </svg>
          <input
            className='h-10 w-full rounded-lg bg-gray-50 pl-10 pr-4 text-sm font-medium uppercase text-gray-900 outline-none transition placeholder-gray-400 focus:bg-white focus:ring-2 focus:ring-blue-500/20 dark:bg-[#141824] dark:text-gray-100 dark:placeholder-gray-600 dark:focus:bg-[#1a1f2e] dark:focus:ring-blue-500/10'
            value={symbolInput}
            onChange={(event) => setSymbolInput(event.target.value)}
            placeholder='搜索代码'
          />
        </div>
        <button
          className='group h-10 rounded-lg border-0 bg-blue-600 px-5 text-sm font-medium text-white transition hover:bg-blue-500 active:scale-[0.97] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/40 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-blue-600 dark:hover:bg-blue-500 dark:shadow-lg dark:shadow-blue-600/20 sm:self-end'
          disabled={state === 'loading'}
          type='submit'
        >
          <span className='inline-flex items-center gap-2'>
            {state === 'loading' ? (
              <svg className='h-4 w-4 animate-spin' viewBox='0 0 24 24' fill='none'>
                <circle className='opacity-25' cx='12' cy='12' r='10' stroke='currentColor' strokeWidth='4' />
                <path className='opacity-75' fill='currentColor' d='M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z' />
              </svg>
            ) : (
              <svg className='h-4 w-4' fill='none' stroke='currentColor' viewBox='0 0 24 24'>
                <path d='M7 11l5-5m0 0l5 5m-5-5v12' strokeLinecap='round' strokeLinejoin='round' strokeWidth='2' />
              </svg>
            )}
            {state === 'loading' ? '获取中' : '绘制'}
          </span>
        </button>
      </form>
    </header>
  )
}
