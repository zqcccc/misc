'use client'

import { useSyncExternalStore } from 'react'

type Theme = 'light' | 'dark'
const THEME_EVENT = 'c9cu-theme-change'

function readTheme(): Theme {
  if (document.documentElement.classList.contains('dark')) return 'dark'
  return 'light'
}

function subscribe(onChange: () => void) {
  window.addEventListener('storage', onChange)
  window.addEventListener(THEME_EVENT, onChange)
  return () => {
    window.removeEventListener('storage', onChange)
    window.removeEventListener(THEME_EVENT, onChange)
  }
}

export default function ThemeButton() {
  const theme = useSyncExternalStore(subscribe, readTheme, () => 'light')

  const toggleTheme = () => {
    const next = readTheme() === 'dark' ? 'light' : 'dark'
    document.documentElement.className = next
    localStorage.setItem('theme', next)
    window.dispatchEvent(new Event(THEME_EVENT))
  }

  return (
    <button
      type='button'
      className='site-icon-button'
      onClick={toggleTheme}
      aria-label={theme === 'dark' ? '切换到浅色模式' : '切换到深色模式'}
      title={theme === 'dark' ? '切换到浅色模式' : '切换到深色模式'}
    >
      {theme === 'dark' ? (
        <svg viewBox='0 0 24 24' aria-hidden='true'>
          <circle cx='12' cy='12' r='4' />
          <path d='M12 2v2M12 20v2M4.93 4.93l1.42 1.42M17.65 17.65l1.42 1.42M2 12h2M20 12h2M4.93 19.07l1.42-1.42M17.65 6.35l1.42-1.42' />
        </svg>
      ) : (
        <svg viewBox='0 0 24 24' aria-hidden='true'>
          <path d='M20.5 14.2A8.5 8.5 0 0 1 9.8 3.5 8.5 8.5 0 1 0 20.5 14.2Z' />
        </svg>
      )}
    </button>
  )
}
