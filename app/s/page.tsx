'use client'

import { useSetState } from 'ahooks'
import { copy } from '../post/[...id]/helpers'

export default function Shorter() {
  const [state, setState] = useSetState({
    url: '',
    shortUrl: '',
  })
  return (
    <main className='p-4'>
      <h2>origin url</h2>
      <input
        type='text'
        className='w-full'
        value={state.url}
        onChange={(e) => setState({ url: e.target.value })}
      />
      <button
        onClick={() => {
          fetch('/api/shorter', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({ url: state.url }),
          })
            .then((res) => res.text())
            .then((url) => setState({ shortUrl: url }))
        }}
      >
        submit
      </button>
      {state.shortUrl && (
        <p>
          short url: {state.shortUrl}
          <button onClick={() => copy(state.shortUrl)}>copy</button>
        </p>
      )}
    </main>
  )
}
