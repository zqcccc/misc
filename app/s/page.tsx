'use client'

import { useSetState } from 'ahooks'
import { copy } from '../post/[...id]/helpers'
import { Button, Input, InputNumber, message } from 'antd'

export default function Shorter() {
  const [state, setState] = useSetState({
    url: '',
    duration: null as null | number,
    shortUrl: '',
    id: '',
  })
  return (
    <main className='p-4'>
      <h2>origin url</h2>
      <Input
        type='text'
        className='w-full'
        value={state.url}
        onChange={(e) => setState({ url: e.target.value })}
      />
      <div className='mt-2'>
        last time(s)
        <InputNumber
          className='ml-2 w-32'
          value={state.duration}
          onChange={(e) => {
            setState({ duration: e })
          }}
        />
        <Button
          className='ml-2'
          onClick={() => {
            setState({ duration: (state.duration || 0) + 1 * 24 * 60 * 60 })
          }}
        >
          +1day
        </Button>
        <Button
          className='ml-2'
          onClick={() => {
            setState({ duration: (state.duration || 0) + 30 * 24 * 60 * 60 })
          }}
        >
          +30day
        </Button>
        <Button
          className='ml-2'
          onClick={() => {
            setState({ duration: (state.duration || 0) + 90 * 24 * 60 * 60 })
          }}
        >
          +3months
        </Button>
        <Button
          className='ml-2'
          onClick={() => {
            setState({ duration: (state.duration || 0) - 30 * 24 * 60 * 60 })
          }}
        >
          -1months
        </Button>
        <Button
          className='ml-2'
          onClick={() => {
            setState({ duration: null })
          }}
        >
          Reset
        </Button>
      </div>
      <Button
        className='mt-2'
        type='primary'
        onClick={() => {
          fetch('/api/shorter', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({ url: state.url, duration: state.duration }),
          })
            .then((res) => res.text())
            .then((url) => setState({ shortUrl: url }))
        }}
      >
        submit
      </Button>
      {state.shortUrl && (
        <p>
          short url: {state.shortUrl}
          <Button
            className='ml-2'
            onClick={() => {
              copy(state.shortUrl)
              message.success('copied')
            }}
          >
            copy
          </Button>
        </p>
      )}
      <div className='mt-2'>
        Update ID:
        <Input
          value={state.id}
          className='w-48 ml-2'
          onChange={(e) => setState({ id: e.target.value })}
        />
        <Button
          className='ml-2'
          type='primary'
          onClick={() => {
            if (!state.id) {
              message.error('id is empty')
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
              .then((url) => setState({ shortUrl: url }))
          }}
        >
          Update
        </Button>
      </div>
    </main>
  )
}
