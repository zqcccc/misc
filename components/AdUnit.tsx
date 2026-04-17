'use client'

import { useEffect } from 'react'

const AD_CLIENT = 'ca-pub-6426066570730708'

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
  useEffect(() => {
    try {
      ;(window.adsbygoogle = window.adsbygoogle || []).push({})
    } catch (e) {}
  }, [])

  return (
    <ins
      className={`adsbygoogle ${className ?? ''}`}
      style={style}
      data-ad-client={AD_CLIENT}
      data-ad-slot={slot}
      data-ad-format={format}
      data-full-width-responsive={fullWidthResponsive.toString()}
    />
  )
}
