'use client'

import React, { useCallback, useMemo, useRef, useState } from 'react'
// import Prism from 'prismjs'
import { copy } from './helpers'

const Pre = (props: any) => {
  // const className = props.children.props.className || ''

  // const highLightLine = useMemo(() => {
  //   const matches = className.match(
  //     /language-(?<lang>[^\{\}]+)(\{(?<high>(.+))\})?/
  //   )
  //   if (matches?.groups?.high) {
  //     return matches.groups.high.split(',').reduce((obj: any, cur: any) => {
  //       let [from, end] = cur.split('-')
  //       console.log('end: ', end)
  //       console.log('from: ', from)
  //       from = parseInt(from)
  //       end = parseInt(end ?? from)
  //       for (let i = from; i <= end; i++) {
  //         obj[i] = true
  //       }
  //       return obj
  //     }, {})
  //   } else {
  //     return {}
  //   }
  // }, [className])

  // const code = props.children.props.children.trim()
  const codeDom = useRef<HTMLDivElement>(null)

  const [copied, setCopied] = useState(false)

  const copyHandle = useCallback(() => {
    const code = codeDom.current?.querySelector('code')?.innerText
    console.log(
      '%c code: ',
      'font-size:12px;background-color: #3F7CFF;color:#fff;',
      code
    )
    if (code) {
      copy(code)
      setCopied(true)
      setTimeout(() => {
        setCopied(false)
      }, 3000)
    }
  }, [])

  return (
    <div className='code-block' ref={codeDom}>
      <button
        className={`gatsby-remark-prismjs-copy-button ${copied && 'copied'}`}
        onClick={copyHandle}
      >
        {copied ? 'Copied' : ' Copy '}
      </button>
      <pre {...props}>{props.children}</pre>
    </div>
  )
}

export default Pre
