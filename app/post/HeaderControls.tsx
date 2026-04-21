'use client'

import Toggle from '@/components/Toggle'
import { useCallback, useState } from 'react'
import Drawer from './drawer'
import Menu from './menu'
import { useIsUseBrowser } from './util'

const THEME_LIGHT = 'light'
const THEME_DARK = 'dark'
const THEME_STORAGE_KEY = 'theme'

type Theme = typeof THEME_LIGHT | typeof THEME_DARK

const ICON_SIZE = 16
const MOON_COLOR = '#f5f5f5'
const SUN_COLOR = '#facc15'

const MoonIcon = () => (
  <svg
    xmlns='http://www.w3.org/2000/svg'
    width={ICON_SIZE}
    height={ICON_SIZE}
    viewBox='0 0 24 24'
    fill={MOON_COLOR}
    aria-hidden='true'
    style={{ pointerEvents: 'none' }}
  >
    <path d='M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79Z' />
  </svg>
)

const SunIcon = () => (
  <svg
    xmlns='http://www.w3.org/2000/svg'
    width={ICON_SIZE}
    height={ICON_SIZE}
    viewBox='0 0 24 24'
    fill='none'
    stroke={SUN_COLOR}
    strokeWidth='2'
    strokeLinecap='round'
    strokeLinejoin='round'
    aria-hidden='true'
    style={{ pointerEvents: 'none' }}
  >
    <circle cx='12' cy='12' r='4' />
    <path d='M12 2v2' />
    <path d='M12 20v2' />
    <path d='m4.93 4.93 1.41 1.41' />
    <path d='m17.66 17.66 1.41 1.41' />
    <path d='M2 12h2' />
    <path d='M20 12h2' />
    <path d='m4.93 19.07 1.41-1.41' />
    <path d='m17.66 6.34 1.41-1.41' />
  </svg>
)

const readInitialTheme = (): Theme | null => {
  if (typeof document === 'undefined') return null
  const className = document.documentElement.className
  if (className === THEME_DARK) return THEME_DARK
  if (className === THEME_LIGHT) return THEME_LIGHT
  return null
}

export default function HeaderControls() {
  const [theme, setThemeState] = useState<Theme | null>(null)
  const [showDrawer, setShowDrawer] = useState(false)
  const isInBrowser = useIsUseBrowser()
  const resolvedTheme = isInBrowser ? (theme ?? readInitialTheme()) : null

  const applyTheme = useCallback((next: Theme) => {
    document.documentElement.className = next
    try {
      localStorage.setItem(THEME_STORAGE_KEY, next)
    } catch (err) {}
    setThemeState(next)
  }, [])

  const toggleDrawerHandle = useCallback(() => setShowDrawer((v) => !v), [])

  return (
    <>
      {resolvedTheme !== null ? (
        <Toggle
          icons={{
            checked: <MoonIcon />,
            unchecked: <SunIcon />,
          }}
          checked={resolvedTheme === THEME_DARK}
          onChange={(e: any) =>
            applyTheme(e.target.checked ? THEME_DARK : THEME_LIGHT)
          }
        />
      ) : (
        <div style={{ height: '24px' }} />
      )}
      {isInBrowser && (
        <Drawer visible={showDrawer} onClick={toggleDrawerHandle}>
          <Menu />
        </Drawer>
      )}
    </>
  )
}
