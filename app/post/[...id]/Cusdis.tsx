'use client'

import React from 'react'
import { useScript } from './useScript'
import { useState } from 'react'

type CusdisProps = {
  attrs: {
    host: string
    appId: string
    pageId: string
    pageTitle?: string
    pageUrl?: string
    theme?: 'light' | 'dark' | 'auto'
  }
  lang?: string
  style?: React.CSSProperties
  className?: string
}
export function ReactCusdis(props: CusdisProps) {
  const divRef = React.useRef<HTMLDivElement>(null)

  const host = props.attrs.host || 'https://cusdis.com'

  useScript(props.lang ? `${host}/js/widget/lang/${props.lang}.js` : '')
  useScript(`/cusdis.es.js`)
  React.useLayoutEffect(() => {
    // @ts-expect-error
    const render = window.renderCusdis

    if (render) {
      render(divRef.current)
    }
  }, [
    props.attrs.appId,
    props.attrs.host,
    props.attrs.pageId,
    props.attrs.pageTitle,
    props.attrs.pageUrl,
    props.lang,
  ])

  return (
    <>
      <div
        id='cusdis_thread'
        data-host={host}
        data-page-id={props.attrs.pageId}
        data-app-id={props.attrs.appId}
        data-page-title={props.attrs.pageTitle}
        data-page-url={props.attrs.pageUrl}
        data-theme={props.attrs.theme}
        style={props.style}
        className={props.className}
        ref={divRef}
      ></div>
    </>
  )
}

function WrapperCusdis(props: Partial<CusdisProps>) {
  const [inBrowser, setInBrowser] = useState(false)
  React.useEffect(() => {
    setInBrowser(true)
  }, [])

  return inBrowser ? (
    <ReactCusdis
      attrs={{
        host: 'https://cusdis.com',
        appId: '05e78cdc-13fc-404f-bab7-a4cc8e62a388',
        pageId: `${window.location.hostname}_${window.location.pathname}`,
        pageTitle: document.title,
        pageUrl: location.href,
        theme: window.__theme as 'light' | 'dark' | 'auto',
      }}
      lang='zh-cn'
      className={props.className}
    />
  ) : null
}
export default WrapperCusdis
