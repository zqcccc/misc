'use client'

import Image from 'next/image'
import Toggle from '@/components/Toggle'
import {
  Reducer,
  createContext,
  useCallback,
  useEffect,
  useReducer,
  useState,
} from 'react'
import Link from 'next/link'
import Drawer from './drawer'
import Menu from './menu'
import { useIsUseBrowser } from './util'
import './style.css'

const GlobalContext = createContext({})

type GlobalState = {
  theme: string | null
}
const reducer: Reducer<
  GlobalState,
  {
    type: string
    payload: string
  }
> = (state, action) => {
  switch (action.type) {
    case 'changeTheme': {
      return {
        ...state,
        theme: action.payload,
      }
    }
    default: {
      return { ...state }
    }
  }
}
export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const [globalState, dispatch] = useReducer(reducer, {
    theme: null,
  })
  const [showDrawer, setShowDrawer] = useState(false)
  const [theme, setTheme] = useState<string | null>(null)
  const isInBrowser = useIsUseBrowser()

  useEffect(() => {
    setTheme(window.__theme)
    dispatch({ type: 'changeTheme', payload: window.__theme })
    window.__onThemeChange = () => {
      setTheme(window.__theme)
      dispatch({ type: 'changeTheme', payload: window.__theme })
      // window.CUSDIS?.setTheme(window.__theme)
    }
  }, [])
  const toggleDrawerHandle = useCallback(() => setShowDrawer((v) => !v), [])

  return (
    <GlobalContext.Provider value={{ state: globalState, dispatch }}>
      <div className='my-0 mx-auto py-10 px-5 max-w-2xl'>
        <header className='flex justify-between items-center mb-12'>
          <Link href='/post'>
            <h1 className='cursor-pointer text-5xl font-black'>
              ZQC&apos;s Blog
            </h1>
          </Link>
          {theme !== null ? (
            <Toggle
              icons={{
                checked: (
                  <Image
                    src='/moon.png'
                    alt='moon Logo'
                    width={16}
                    height={16}
                    priority
                    style={{ pointerEvents: 'none' }}
                  />
                ),
                unchecked: (
                  <Image
                    src='/sun.png'
                    alt='sun Logo'
                    width={16}
                    height={16}
                    priority
                    style={{ pointerEvents: 'none' }}
                  />
                ),
              }}
              checked={theme === 'dark'}
              onChange={(e: any) =>
                window.__setPreferredTheme(e.target.checked ? 'dark' : 'light')
              }
            />
          ) : (
            <div style={{ height: '24px' }} />
          )}
        </header>
        {children}
      </div>
      {isInBrowser && (
        <Drawer visible={showDrawer} onClick={toggleDrawerHandle}>
          <Menu />
        </Drawer>
      )}
    </GlobalContext.Provider>
  )
}

declare global {
  interface Window {
    __theme: string
    __onThemeChange: (theme: string) => void
    __setPreferredTheme: (theme: string) => void
  }
}

;(function () {
  if (typeof window === 'undefined') return
  window.__onThemeChange = function () {}
  function setTheme(newTheme: string) {
    window.__theme = newTheme
    preferredTheme = newTheme
    document.documentElement.className = newTheme
    window.__onThemeChange(newTheme)
  }

  var preferredTheme
  try {
    preferredTheme = localStorage.getItem('theme')
  } catch (err) {}

  window.__setPreferredTheme = function (newTheme) {
    setTheme(newTheme)
    try {
      localStorage.setItem('theme', newTheme)
    } catch (err) {}
  }

  var darkQuery = window.matchMedia('(prefers-color-scheme: dark)')
  darkQuery.addListener(function (e) {
    window.__setPreferredTheme(e.matches ? 'dark' : 'light')
  })

  setTheme(preferredTheme || (darkQuery.matches ? 'dark' : 'light'))
})()
