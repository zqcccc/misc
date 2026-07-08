'use client'

import { useEffect, useState } from 'react'

// 本次会话内是否已关闭提示，避免每次路由切换都打扰用户
const STORAGE_KEY = 'aab_notice_dismissed'

export default function AntiAdblockNotice() {
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    let dismissed = false
    try {
      dismissed = sessionStorage.getItem(STORAGE_KEY) === '1'
    } catch {
      // sessionStorage 不可用时（隐私模式等）当作未关闭，正常检测
    }
    if (dismissed) return

    // bait 元素法：主流广告拦截器会隐藏/折叠含 'ads' 类名的元素，
    // 借此判断是否被拦截，无需加载任何第三方脚本。
    const bait = document.createElement('div')
    bait.className = 'adsbox ad-placeholder ad-banner'
    bait.setAttribute('aria-hidden', 'true')
    bait.style.cssText =
      'position:absolute;left:-9999px;top:-9999px;height:10px;width:10px;'
    document.body.appendChild(bait)

    const timer = window.setTimeout(() => {
      let blocked = false
      try {
        const style = getComputedStyle(bait)
        blocked =
          bait.offsetParent === null ||
          bait.clientHeight === 0 ||
          style.display === 'none' ||
          style.visibility === 'hidden'
      } catch {
        // 读取样式出错则不提示，避免误报
      }
      if (bait.parentNode) bait.parentNode.removeChild(bait)

      let stillDismissed = false
      try {
        stillDismissed = sessionStorage.getItem(STORAGE_KEY) === '1'
      } catch {}
      if (blocked && !stillDismissed) setVisible(true)
    }, 300)

    return () => window.clearTimeout(timer)
  }, [])

  const dismiss = () => {
    try {
      sessionStorage.setItem(STORAGE_KEY, '1')
    } catch {}
    setVisible(false)
  }

  if (!visible) return null

  return (
    <div className='aab-notice' role='dialog' aria-label='广告拦截提示'>
      <div className='aab-notice__icon' aria-hidden='true'>
        📢
      </div>
      <div className='aab-notice__text'>
        <strong>网站靠广告维持运转</strong>
        <span>
          我们检测到您开启了广告拦截插件。如果本站内容对您有帮助，欢迎将本站加入白名单，您的支持是我们持续创作的动力
          🙏
        </span>
      </div>
      <button
        type='button'
        className='aab-notice__close'
        onClick={dismiss}
        aria-label='关闭提示'
      >
        ×
      </button>
    </div>
  )
}
