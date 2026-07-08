'use client'

import AdUnit from './AdUnit'

type AdBanner300x250Props = {
  /** AdSense 广告单元 ID（slot） */
  slot: string
  className?: string
}

/**
 * 300x250 标准 Banner 广告位（AdSense "Medium Rectangle"）。
 *
 * 设计说明：
 * - 复用项目既有 AdSense 管线（lib/ads + AdUnit），不引入任何未知第三方脚本。
 * - ADS_ENABLED=false 时整块不渲染（AdUnit 内部已处理），可一键开关。
 * - 带可见 "Advertisement" 标识，符合 AdSense / FTC 披露规范，且对屏幕阅读器友好。
 */
export default function AdBanner300x250({ slot, className }: AdBanner300x250Props) {
  return (
    <aside
      className={`ad-banner ad-banner--300x250 ${className ?? ''}`}
      role="region"
      aria-label="Advertisement"
    >
      <span className="ad-banner__label" aria-hidden="true">
        Advertisement
      </span>
      <AdUnit
        slot={slot}
        format="rectangle"
        fullWidthResponsive={false}
        style={{ display: 'block', width: 300, height: 250 }}
      />
    </aside>
  )
}
