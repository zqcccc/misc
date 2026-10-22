import { SITE_URL } from '@/lib/site'

export const AD_PROVIDER = {
  EZOIC: 'ezoic',
  ADSTERRA: 'adsterra',
  AADS: 'aads',
  DIRECT: 'direct',
} as const

export const AD_SLOT = {
  POST_TOP: 'post-top',
  POST_BOTTOM: 'post-bottom',
} as const

export type AdSlotId = (typeof AD_SLOT)[keyof typeof AD_SLOT]

type SizedUnit = { width: number; height: number }

// Adsterra 后台「Get code」里的 Banner 代码：key 是 atOptions.key，scriptSrc 是 invoke.js 的完整地址
export type AdsterraUnit = SizedUnit & { key: string; scriptSrc: string }

// A-Ads 后台广告单元代码里 iframe 的 src，选固定尺寸
export type AadsUnit = SizedUnit & { src: string }

export type AdSlotConfig =
  | { provider: typeof AD_PROVIDER.EZOIC; placeholderId: number }
  // units 可以放多个尺寸，运行时按容器宽度选最宽且放得下的一个
  | { provider: typeof AD_PROVIDER.ADSTERRA; units: AdsterraUnit[] }
  | { provider: typeof AD_PROVIDER.AADS; units: AadsUnit[] }
  // 直接卖给赞助商的广告位
  | {
      provider: typeof AD_PROVIDER.DIRECT
      sponsor: string
      href: string
      image: string
      alt: string
      width: number
      height: number
    }

// Ezoic 后台添加站点后改为 true：加载 Ezoic 脚本和同意管理平台(CMP)，ads.txt 改为重定向到 Ezoic 的 ads.txt 管理器
export const EZOIC_ENABLED = true
export const EZOIC_ADS_TXT_URL = `https://srv.adstxtmanager.com/19390/${new URL(SITE_URL).hostname}`

// 不启用 Ezoic 时 /ads.txt 输出的内容
export const ADS_TXT_LINES = [
  'google.com, pub-6426066570730708, DIRECT, f08c47fec0942fa0',
]

// 每个广告位填一个来源，null 表示不展示
export const AD_SLOTS: Record<AdSlotId, AdSlotConfig | null> = {
  [AD_SLOT.POST_TOP]: null,
  [AD_SLOT.POST_BOTTOM]: null,
}

const PROVIDER_NAME: Record<AdSlotConfig['provider'], string> = {
  [AD_PROVIDER.EZOIC]: 'Ezoic',
  [AD_PROVIDER.ADSTERRA]: 'Adsterra',
  [AD_PROVIDER.AADS]: 'A-Ads',
  [AD_PROVIDER.DIRECT]: '直接赞助',
}

for (const [slot, config] of Object.entries(AD_SLOTS)) {
  if (config?.provider === AD_PROVIDER.EZOIC && !EZOIC_ENABLED) {
    throw new Error(`广告位 ${slot} 使用 Ezoic，但 EZOIC_ENABLED 为 false`)
  }
  if (
    (config?.provider === AD_PROVIDER.ADSTERRA || config?.provider === AD_PROVIDER.AADS) &&
    config.units.length === 0
  ) {
    throw new Error(`广告位 ${slot} 没有配置任何尺寸`)
  }
}

// 隐私政策据此列出当前实际在用的第三方广告服务
export function getActiveAdProviders(): string[] {
  const providers = new Set<AdSlotConfig['provider']>()
  if (EZOIC_ENABLED) providers.add(AD_PROVIDER.EZOIC)
  for (const config of Object.values(AD_SLOTS)) {
    if (config && config.provider !== AD_PROVIDER.DIRECT) providers.add(config.provider)
  }
  return Array.from(providers, (provider) => PROVIDER_NAME[provider])
}

declare global {
  interface Window {
    ezstandalone?: {
      cmd: Array<() => void>
      showAds: (...ids: number[]) => void
      destroyPlaceholders: (...ids: number[]) => void
    }
  }
}
