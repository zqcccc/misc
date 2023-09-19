'use client'

import { useSetState } from 'ahooks'
import { useEffect } from 'react'
import { useWordStore } from './store'

export default function En() {
  const wordStore = useWordStore()
  const [state, setState] = useSetState({
    word: 'in vain',
    loadingWords: true,
    loadingDefinitions: false,
    definitions: [] as { entry: string; explain: string }[],
    wordList: [] as { uuid: string }[],
  })

  const appHeight = () => {
    const doc = document.documentElement
    doc.style.setProperty('--app-height', `${window.innerHeight}px`)
  }
  useEffect(() => {
    appHeight()
    window.addEventListener('resize', appHeight)
    ;(async () => {
      try {
        if (!document.cookie.includes('EudicWebSession'))
          await fetch(`/api/en/login`, {
            method: 'POST',
          })
        const res = await fetch('/api/en', { method: 'POST' }).then((res) =>
          res.json()
        )
        setState({
          word: 'in vain', //getARandomWord(res.data).uuid,
          wordList: res.data,
        })
      } catch (error) {
      } finally {
        setState({ loadingWords: false })
      }
    })()
    return () => {
      window.removeEventListener('resize', appHeight)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const search = () => {
    if (!state.word) return
    const result = wordStore.getWord(state.word)
    if (!result) {
      setState({ loadingDefinitions: true })
      fetch(`/api/en?w=${state.word}`)
        .then((res) => res.json())
        .then((json) => {
          console.log('json: ', json)
          setState({ definitions: json.data.entries })
          wordStore.saveWord(state.word, json.data.entries)
        })
        .finally(() => {
          setState({ loadingDefinitions: false })
        })
    } else {
      setState({ definitions: result })
    }
  }
  const getARandomWord = (list = state.wordList) => {
    const randomIndex = Math.floor(Math.random() * list.length)
    return list[randomIndex]
  }

  return (
    <main className='flex flex-col items-center justify-center min-h-[var(--app-height)]'>
      <h2>听学英语</h2>
      {state.loadingWords && 'is Loading words...'}
      <button
        className='my-3 p-2'
        disabled={state.wordList.length === 0}
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
      <button
        onClick={search}
        disabled={state.wordList.length === 0}
        className='mt-3 p-2'
      >
        show difinition
      </button>
      {state.loadingDefinitions && (
        <div className='mt-3'>is loading definitions...</div>
      )}
      {state.definitions.map((item) => (
        <div key={item.entry} className='mb-1'>
          <p className='text-center'>{item.entry}</p>
          <p className='px-5'>{item.explain}</p>
        </div>
      ))}
      <button
        className='mt-4 p-2'
        onClick={() => {
          window.open(
            `https://dictionary.cambridge.org/dictionary/english-chinese-simplified/${state.word
              .split(' ')
              .join('-')}?q=${state.word.split(' ').join('+')}`,
            '_blank'
          )
        }}
      >
        Cambridge
      </button>
      <button
        className='mt-4 p-2'
        onClick={() => {
          window.open(
            `https://www.collinsdictionary.com/zh/dictionary/english/${state.word
              .split(' ')
              .join('-')}`,
            '_blank'
          )
        }}
      >
        Collins
      </button>
    </main>
  )
}
