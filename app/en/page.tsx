'use client'

import { useSetState } from 'ahooks'
import { useEffect } from 'react'

export default function En() {
  const [state, setState] = useSetState({
    word: '',
    // hasReadList: [],
    definitions: [] as { entry: string; explain: string }[],
    wordList: [] as { uuid: string }[],
  })

  useEffect(() => {
    ;(async () => {
      if (!document.cookie.includes('EudicWebSession'))
        await fetch(`/api/en/login`, {
          method: 'POST',
        })
      const res = await fetch('/api/en', { method: 'POST' }).then((res) =>
        res.json()
      )
      setState({
        word: getARandomWord(res.data).uuid,
        wordList: res.data,
      })
    })()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const search = () => {
    state.word &&
      fetch(`/api/en?w=${state.word}`)
        .then((res) => res.json())
        .then((json) => {
          console.log('json: ', json)
          setState({ definitions: json.data.entries })
        })
  }
  const getARandomWord = (list = state.wordList) => {
    const randomIndex = Math.floor(Math.random() * list.length)
    return list[randomIndex]
  }

  return (
    <main className='flex flex-col items-center justify-center min-h-screen'>
      <h2>听学英语</h2>
      <button
        className='my-3 p-2'
        onClick={() => {
          if (state.wordList) {
            setState({
              word: getARandomWord().uuid,
            })
          } else {
            alert('没有单词')
          }
        }}
      >
        random a word
      </button>
      <audio
        controls
        src={`https://dict.youdao.com/dictvoice?audio=${state.word}&type=2`}
      ></audio>
      <button onClick={search} className='mt-3 p-2'>
        show difinition
      </button>
      {state.definitions.map((item) => (
        <div key={item.entry} className='mb-1'>
          <p className='text-center'>{item.entry}</p>
          <p className='px-5'>{item.explain}</p>
        </div>
      ))}
    </main>
  )
}
