import { useState, useEffect } from 'react'

export const useIsUseBrowser = () => {
  const [isInBrowser, setIsInBrowser] = useState(false)
  useEffect(() => {
    setIsInBrowser(true)
  }, [])
  return isInBrowser
}
