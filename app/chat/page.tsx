'use client'

import { useMount } from 'ahooks'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

type Message = { role: string; content: string }

const Chat = () => {
  const [messages, setMessages] = useState<Message[]>([])
  const [key, setKey] = useState('')
  const [input, setInput] = useState('')
  const isKeyValid = useMemo(() => key.trim().length === 32, [key])

  useMount(() => {
    const key = localStorage.getItem('azure-key')
    if (key) setKey(key)
  })

  useEffect(() => {
    const onClick = (e: any) => {
      if (!isKeyValid && e.target.id !== 'key') alert('azure key is invalid')
    }
    if (!isKeyValid) {
      window.addEventListener('click', onClick)
      return () => {
        window.removeEventListener('click', onClick)
      }
    }
  }, [isKeyValid])

  const request = (msgs: Message[]) => {
    return fetch('/api/gpt', {
      method: 'POST',
      headers: {
        'api-key': key,
      },
      body: JSON.stringify({
        messages: msgs,
      }),
    })
      .then((res) => res.json())
      .then((json) => {
        console.log('json: ', json)
        setMessages((messages) =>
          messages.concat(json.choices.map((choice: any) => choice.message))
        )
      })
  }
  return (
    <main className='mx-auto my-0 max-w-5xl min-h-screen flex flex-col p-2 pb-5'>
      <h1 className='text-center'>ChatGPT</h1>
      {messages.map((message, index) => {
        return (
          <pre
            className={` w-fit max-w-[95%] whitespace-pre-wrap border rounded border-solid border-black mb-2 p-2 ${
              message.role === 'user' ? 'self-end' : ''
            }`}
            key={index}
          >
            {message.content}
          </pre>
        )
      })}
      <textarea
        disabled={!isKeyValid}
        className='m-0 w-full max-h-72 resize-none border rounded border-solid border-black p-2 focus:ring-0 focus-visible:ring-0 dark:bg-transparent'
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && input) {
            const nextMessages = messages.concat([
              { role: 'user', content: input },
            ])
            setMessages(nextMessages)
            request(nextMessages)
            setInput('')
          }
        }}
      />
      <div>
        azure openai key:{' '}
        <input
          id='key'
          type='text'
          value={key}
          onChange={(e) => {
            setKey(e.target.value)
            localStorage.setItem('azure-key', e.target.value)
          }}
        />
      </div>
    </main>
  )
}
export default Chat
