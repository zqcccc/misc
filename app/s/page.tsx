'use client'

import { useSetState } from 'ahooks'
import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { copy } from '../post/[...id]/helpers'

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
    <main className='p-4'>
      <div className='flex items-center gap-2 flex-wrap'>
        <div>base url:</div>
        {baseUrl && (
          <a
            href={baseUrl}
            target='_blank'
            rel='noreferrer'
            className='break-all'
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
        <div className='mt-2 flex items-center gap-2 flex-wrap text-sm'>
          <div>default redirect:</div>
          <a
            href={defaultRedirectUrl}
            target='_blank'
            rel='noreferrer'
            className='break-all'
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
      <h2 className='mt-4'>origin url</h2>
      <Input
        type='text'
        value={state.url}
        onChange={(e) => setState({ url: e.target.value })}
      />
      <div className='mt-2 flex gap-2 flex-wrap items-center'>
        last time(s)
        <Input
          type='number'
          className='w-32'
          value={state.duration ?? ''}
          onChange={(e) => {
            const v = e.target.value
            setState({ duration: v === '' ? null : Number(v) })
          }}
        />
        <Button
          variant='outline'
          onClick={() => {
            setState({ duration: (state.duration || 0) + 1 * 24 * 60 * 60 })
          }}
        >
          +1day
        </Button>
        <Button
          variant='outline'
          onClick={() => {
            setState({ duration: (state.duration || 0) + 30 * 24 * 60 * 60 })
          }}
        >
          +30day
        </Button>
        <Button
          variant='outline'
          onClick={() => {
            setState({ duration: (state.duration || 0) + 90 * 24 * 60 * 60 })
          }}
        >
          +3months
        </Button>
        <Button
          variant='outline'
          onClick={() => {
            setState({ duration: (state.duration || 0) - 30 * 24 * 60 * 60 })
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
        className='mt-2'
        onClick={() => {
          fetch('/api/shorter', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({ url: state.url, duration: state.duration }),
          })
            .then((res) => res.text())
            .then((key) => setState({ shortUrl: buildShortUrl(key) }))
        }}
      >
        submit
      </Button>
      {state.shortUrl && (
        <p className='mt-2 flex items-center gap-2 flex-wrap'>
          <span>short url: {state.shortUrl}</span>
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
      <div className='mt-2 flex items-center gap-2 flex-wrap'>
        Update ID:
        <Input
          className='w-48'
          value={state.id}
          onChange={(e) => setState({ id: e.target.value })}
        />
        <Button
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

      <div className='mt-5'>
        <div>-------------</div>
        query origin url:
        <div className='flex mt-2 gap-2'>
          <Input
            className='flex-1'
            value={state.queryShortUrl}
            onChange={(e) => setState({ queryShortUrl: e.target.value })}
          />
          <Button
            variant='outline'
            onClick={() => {
              const key =
                state.queryShortUrl.split('/').pop() || state.queryShortUrl
              fetch(`/api/shorter?key=${key}`)
                .then((res) => res.text())
                .then((url) => {
                  setState({ queryResult: url })
                })
            }}
          >
            query
          </Button>
        </div>
        <div className='mt-2 flex items-center gap-2 flex-wrap'>
          <span>{state.queryResult}</span>
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
      </div>
    </main>
  )
}
