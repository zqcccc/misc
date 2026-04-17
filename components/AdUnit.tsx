'use client'

import { useEffect, useRef } from 'react'

const AD_CLIENT = 'ca-pub-6426066570730708'
const OBSERVER_ROOT_MARGIN = '200px'
const OBSERVER_THRESHOLD = 0

type AdUnitProps = {
  slot: string
  format?: string
  fullWidthResponsive?: boolean
  style?: React.CSSProperties
  className?: string
}

declare global {
  interface Window {
    adsbygoogle: unknown[]
  }
}

export default function AdUnit({
  slot,
  format = 'auto',
  fullWidthResponsive = true,
  style = { display: 'block' },
  className,
}: AdUnitProps) {
  const insRef = useRef<HTMLModElement | null>(null)

  useEffect(() => {
    const el = insRef.current
    if (!el) return

    let pushed = false
    const pushAd = () => {
      if (pushed) return
      pushed = true
      try {
        ;(window.adsbygoogle = window.adsbygoogle || []).push({})
      } catch (e) {}
    }

    if (typeof IntersectionObserver === 'undefined') {
      pushAd()
      return
    }

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            pushAd()
            observer.disconnect()
            break
          }
        }
      },
      { rootMargin: OBSERVER_ROOT_MARGIN, threshold: OBSERVER_THRESHOLD },
    )

    observer.observe(el)

    return () => {
      observer.disconnect()
    }
  }, [])

  return (
    <ins
      ref={insRef}
      className={`adsbygoogle ${className ?? ''}`}
      style={style}
      data-ad-client={AD_CLIENT}
      data-ad-slot={slot}
      data-ad-format={format}
      data-full-width-responsive={fullWidthResponsive.toString()}
    />
  )
}
