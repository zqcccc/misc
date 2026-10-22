'use client'

import { useEffect } from 'react'
import { usePathname } from 'next/navigation'

// App Router 客户端导航不会刷新页面，路由变化后要让 Ezoic 清理旧占位并重新扫描 DOM
export default function EzoicRouteHandler() {
  const pathname = usePathname()

  useEffect(() => {
    const ez = (window.ezstandalone ??= { cmd: [] } as unknown as NonNullable<
      Window['ezstandalone']
    >)
    ez.cmd ??= []
    ez.cmd.push(() => {
      window.ezstandalone!.destroyPlaceholders()
      requestAnimationFrame(() => window.ezstandalone!.showAds())
    })
  }, [pathname])

  return null
}
