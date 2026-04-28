'use client'

import { useSetState } from 'ahooks'
import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { copy } from '../post/[...id]/helpers'
import { formatRemainingTime } from './time'

const SHORT_URL_PATH_PREFIX = '/url'

const buildShortUrl = (key: string) =>
  `${window.location.origin}${SHORT_URL_PATH_PREFIX}/${key}`

export default function Shorter() {
  const [state, setState] = useSetState({
    url: '',
    duration: null as null | number,
    shortUrl: '',
    id: '',
    queryShortUrl: '',
    queryResult: '',
    queryRemainingTime: null as null | number,
  })
  const [defaultRedirectUrl, setDefaultRedirectUrl] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  useEffect(() => {
    fetch('/api/shorter/default')
      .then((res) => res.text())
      .then(setDefaultRedirectUrl)
    fetch('/api/standard', {
      method: 'POST',
    })
      .then((res) => res.text())
      .then(setBaseUrl)
  }, [])
  return (
    <main className='min-h-screen bg-[var(--bg)] px-4 py-6 text-foreground'>
      <div className='mx-auto max-w-3xl space-y-5'>
        <section className='rounded-lg border border-border bg-background p-4 shadow-sm dark:border-gray-700'>
          <div className='flex items-center gap-2 flex-wrap text-sm'>
            <div className='font-medium text-foreground'>base url:</div>
            {baseUrl && (
              <a
                href={baseUrl}
                target='_blank'
                rel='noreferrer'
                className='break-all text-blue-700 underline-offset-4 hover:underline dark:text-blue-300'
              >
                {baseUrl}
              </a>
            )}
            <Button
              variant='outline'
              size='sm'
              onClick={() => {
                if (!baseUrl) return
                copy(baseUrl)
                toast.success('copied', { description: baseUrl })
              }}
            >
              Copy
            </Button>
          </div>
          {defaultRedirectUrl && (
            <div className='mt-2 flex items-center gap-2 flex-wrap text-sm text-muted-foreground'>
              <div className='font-medium text-foreground'>
                default redirect:
              </div>
              <a
                href={defaultRedirectUrl}
                target='_blank'
                rel='noreferrer'
                className='break-all text-blue-700 underline-offset-4 hover:underline dark:text-blue-300'
              >
                {defaultRedirectUrl}
              </a>
              <Button
                variant='outline'
                size='sm'
                onClick={() => {
                  copy(defaultRedirectUrl)
                  toast.success('copied')
                }}
              >
                Copy
              </Button>
            </div>
          )}
        </section>

        <section className='rounded-lg border border-border bg-background p-4 shadow-sm dark:border-gray-700'>
          <h2 className='text-base font-semibold'>origin url</h2>
          <Input
            className='mt-2 bg-background'
            type='text'
            value={state.url}
            onChange={(e) => setState({ url: e.target.value })}
          />
          <div className='mt-3 flex gap-2 flex-wrap items-center text-sm'>
            <span className='font-medium'>last time(s)</span>
            <Input
              type='number'
              className='w-32 bg-background'
              value={state.duration ?? ''}
              onChange={(e) => {
                const v = e.target.value
                setState({ duration: v === '' ? null : Number(v) })
              }}
            />
            <Button
              variant='outline'
              onClick={() => {
                setState({
                  duration: (state.duration || 0) + 1 * 24 * 60 * 60,
                })
              }}
            >
              +1day
            </Button>
            <Button
              variant='outline'
              onClick={() => {
                setState({
                  duration: (state.duration || 0) + 30 * 24 * 60 * 60,
                })
              }}
            >
              +30day
            </Button>
            <Button
              variant='outline'
              onClick={() => {
                setState({
                  duration: (state.duration || 0) + 90 * 24 * 60 * 60,
                })
              }}
            >
              +3months
            </Button>
            <Button
              variant='outline'
              onClick={() => {
                setState({
                  duration: (state.duration || 0) - 30 * 24 * 60 * 60,
                })
              }}
            >
              -1months
            </Button>
            <Button
              variant='outline'
              onClick={() => {
                setState({ duration: null })
              }}
            >
              Reset
            </Button>
          </div>
          <Button
            variant='outline'
            className='mt-2'
            onClick={() => {
              fetch('/api/shorter', {
                method: 'POST',
                headers: {
                  'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                  url: state.url,
                  duration: state.duration,
                }),
              })
                .then((res) => res.text())
                .then((key) => setState({ shortUrl: buildShortUrl(key) }))
            }}
          >
            submit
          </Button>
          {state.shortUrl && (
            <p className='mt-3 flex items-center gap-2 flex-wrap text-sm'>
              <span className='break-all'>short url: {state.shortUrl}</span>
              <Button
                variant='outline'
                size='sm'
                onClick={() => {
                  copy(state.shortUrl)
                  toast.success('copied')
                }}
              >
                copy
              </Button>
            </p>
          )}
          <div className='mt-4 flex items-center gap-2 flex-wrap text-sm'>
            <span className='font-medium'>Update ID:</span>
            <Input
              className='w-48 bg-background'
              value={state.id}
              onChange={(e) => setState({ id: e.target.value })}
            />
            <Button
              variant='outline'
              onClick={() => {
                if (!state.id) {
                  toast.error('id is empty')
                  return
                }
                fetch('/api/shorter', {
                  method: 'PATCH',
                  headers: {
                    'Content-Type': 'application/json',
                  },
                  body: JSON.stringify({
                    id: state.id,
                    url: state.url,
                    duration: state.duration,
                  }),
                })
                  .then((res) => res.text())
                  .then((key) => setState({ shortUrl: buildShortUrl(key) }))
              }}
            >
              Update
            </Button>
          </div>
        </section>

        <section className='rounded-lg border border-border bg-background p-4 shadow-sm dark:border-gray-700'>
          <h2 className='text-base font-semibold'>query origin url</h2>
          <div className='flex mt-2 gap-2'>
            <Input
              className='flex-1 bg-background'
              value={state.queryShortUrl}
              onChange={(e) => setState({ queryShortUrl: e.target.value })}
            />
            <Button
              variant='outline'
              onClick={() => {
                const value = state.queryShortUrl.trim()
                const key =
                  value.replace(/\/+$/, '').split('/').pop() || value
                fetch(
                  `/api/shorter?key=${encodeURIComponent(key)}&format=json`,
                )
                  .then((res) => res.json())
                  .then((data: { url?: string; ttl?: number }) => {
                    setState({
                      queryResult: data.url || '',
                      queryRemainingTime:
                        typeof data.ttl === 'number' ? data.ttl : null,
                    })
                  })
              }}
            >
              query
            </Button>
          </div>
          <div className='mt-3 flex items-center gap-2 flex-wrap text-sm'>
            {state.queryResult && (
              <span className='break-all'>{state.queryResult}</span>
            )}
            {state.queryResult && (
              <Button
                variant='outline'
                size='sm'
                onClick={() => {
                  copy(state.queryResult)
                  toast.success('copied')
                }}
              >
                Copy
              </Button>
            )}
          </div>
          {state.queryResult && (
            <div className='mt-2 text-sm text-muted-foreground'>
              remaining time: {formatRemainingTime(state.queryRemainingTime)}
            </div>
          )}
        </section>
      </div>
    </main>
  )
}
