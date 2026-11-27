'use client'

import React from 'react'
import { useScript } from './useScript'
import { useIsUseBrowser } from '../util'

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
// /cusdis.es.js 挂载的全局渲染入口；项目内没有该全局类型声明，在此统一声明。
declare global {
  interface Window {
    renderCusdis?: (element: HTMLElement | null) => void
  }
}

export function ReactCusdis(props: CusdisProps) {
  const divRef = React.useRef<HTMLDivElement>(null)
  const renderedRef = React.useRef(false)

  const host = props.attrs.host || 'https://cusdis.com'
  const langSrc = props.lang ? `${host}/js/widget/lang/${props.lang}.js` : ''
  const langStatus = useScript(langSrc)
  const coreStatus = useScript('/cusdis.es.js')

  React.useLayoutEffect(() => {
    if (renderedRef.current) return
    if (coreStatus !== 'ready') return
    // 语言包必须先于首次渲染就绪，否则挂件会以默认语言完成初始化。
    if (langSrc && langStatus === 'loading') return

    if (langStatus === 'error') {
      console.error(`[cusdis] 语言脚本加载失败，回退默认语言：${langSrc}`)
    }

    const render = window.renderCusdis

    if (typeof render !== 'function') {
      console.error('[cusdis] 脚本已就绪但 window.renderCusdis 不可用')
      return
    }

    renderedRef.current = true
    render(divRef.current)
  }, [coreStatus, langStatus, langSrc])

  if (coreStatus === 'error') {
    return (
      <p
        role='alert'
        style={{
          margin: '12px 0 0',
          color: 'var(--site-signal)',
          fontSize: 13,
          lineHeight: 1.6,
        }}
      >
        评论脚本加载失败，请稍后刷新页面重试。
      </p>
    )
  }

  return (
    <>
      {langStatus === 'error' && (
        <p
          role='status'
          style={{
            margin: '12px 0 0',
            color: 'var(--site-muted)',
            fontSize: 13,
            lineHeight: 1.6,
          }}
        >
          评论语言包加载失败，已回退默认语言。
        </p>
      )}
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
  const inBrowser = useIsUseBrowser()
  const [enabled, setEnabled] = React.useState(false)

  if (!inBrowser) return null

  return (
    <section className={props.className} aria-labelledby='comments-title'>
      <div className='article-comments-heading'>
        <div>
          <h2 id='comments-title'>评论</h2>
          <p>评论由 Cusdis 提供。只有你主动加载后，浏览器才会连接该第三方服务。</p>
        </div>
        {!enabled && (
          <button type='button' onClick={() => setEnabled(true)}>
            加载评论
          </button>
        )}
      </div>
      {enabled && (
        <ReactCusdis
          attrs={{
            host: 'https://cusdis.com',
            appId: '05e78cdc-13fc-404f-bab7-a4cc8e62a388',
            pageId: `${window.location.hostname}_${window.location.pathname}`,
            pageTitle: document.title,
            pageUrl: location.href,
            theme: document.documentElement.className as 'light' | 'dark' | 'auto',
          }}
          lang='zh-cn'
        />
      )}
    </section>
  )
}
export default WrapperCusdis
