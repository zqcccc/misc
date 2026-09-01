'use client'

import Script from 'next/script'
import { useSyncExternalStore } from 'react'

const CONSENT_KEY = 'c9cu-analytics-consent'
const CONSENT_EVENT = 'c9cu-consent-change'
type Decision = 'granted' | 'denied' | null

function readDecision(): Decision {
  const stored = localStorage.getItem(CONSENT_KEY)
  return stored === 'granted' ? 'granted' : stored === 'denied' ? 'denied' : null
}

function subscribe(onChange: () => void) {
  window.addEventListener('storage', onChange)
  window.addEventListener(CONSENT_EVENT, onChange)
  return () => {
    window.removeEventListener('storage', onChange)
    window.removeEventListener(CONSENT_EVENT, onChange)
  }
}

export default function AnalyticsConsent() {
  const decision = useSyncExternalStore<Decision | 'pending'>(
    subscribe,
    readDecision,
    () => 'pending',
  )

  const choose = (next: 'granted' | 'denied') => {
    localStorage.setItem(CONSENT_KEY, next)
    window.dispatchEvent(new Event(CONSENT_EVENT))
  }

  return (
    <>
      {decision === 'granted' && (
        <>
          <Script
            src='https://www.googletagmanager.com/gtag/js?id=G-4DLMMFXJMP'
            strategy='afterInteractive'
          />
          <Script id='google-analytics' strategy='afterInteractive'>
            {`
              window.dataLayer = window.dataLayer || [];
              function gtag(){dataLayer.push(arguments);}
              gtag('js', new Date());
              gtag('config', 'G-4DLMMFXJMP', { anonymize_ip: true });
            `}
          </Script>
        </>
      )}
      {decision === null && (
        <section className='consent-panel' aria-label='统计偏好'>
          <div>
            <strong>是否允许匿名访问统计？</strong>
            <p>
              只有你同意后才会加载 Google Analytics。拒绝不会影响网站功能。
              <a href='/privacy#analytics'>了解详情</a>
            </p>
          </div>
          <div className='consent-actions'>
            <button type='button' onClick={() => choose('denied')}>
              仅必要功能
            </button>
            <button
              type='button'
              className='consent-primary'
              onClick={() => choose('granted')}
            >
              允许匿名统计
            </button>
          </div>
        </section>
      )}
    </>
  )
}
