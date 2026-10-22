'use client'

import { useEffect, useRef, useState } from 'react'
import {
  AD_PROVIDER,
  AD_SLOTS,
  type AadsUnit,
  type AdSlotId,
  type AdsterraUnit,
} from '@/lib/ads'

const AD_LABEL = '广告'
const SPONSOR_LABEL = '赞助'

// 把命令放进 Ezoic 的队列，脚本加载完成后按顺序执行
function runEzoic(fn: () => void) {
  const ez = (window.ezstandalone ??= { cmd: [] } as unknown as NonNullable<
    Window['ezstandalone']
  >)
  ez.cmd ??= []
  ez.cmd.push(fn)
}

function EzoicPlaceholder({ id }: { id: number }) {
  // 客户端路由切换时组件会卸载再挂载，每次都要让 Ezoic 重新扫描占位元素。
  // showAds 在 hydrate 之后才执行，Ezoic 插入的内容不会和服务端 HTML 冲突
  useEffect(() => {
    runEzoic(() => window.ezstandalone!.showAds(id))
    return () => runEzoic(() => window.ezstandalone!.destroyPlaceholders(id))
  }, [id])

  return <div id={`ezoic-pub-ad-placeholder-${id}`} />
}

// 按容器宽度选最宽且放得下的尺寸，手机上就不会出现横向溢出
function useFittingUnit<T extends { width: number }>(units: T[]) {
  const ref = useRef<HTMLDivElement>(null)
  const [unit, setUnit] = useState<T | null>(null)

  useEffect(() => {
    const available = ref.current!.clientWidth
    const sorted = [...units].sort((a, b) => b.width - a.width)
    setUnit(sorted.find((item) => item.width <= available) ?? null)
  }, [units])

  return { ref, unit }
}

// atOptions 是全局变量，同一页面放多个 Adsterra 横幅会互相覆盖，所以每个横幅放进独立的 srcdoc iframe
function adsterraDocument(unit: AdsterraUnit): string {
  const options = JSON.stringify({
    key: unit.key,
    format: 'iframe',
    height: unit.height,
    width: unit.width,
    params: {},
  })
  return `<!doctype html><html><head><style>html,body{margin:0;padding:0;overflow:hidden;background:transparent}</style></head><body><script>atOptions=${options}</script><script src="${unit.scriptSrc}"></script></body></html>`
}

function AdsterraBanner({ units }: { units: AdsterraUnit[] }) {
  const { ref, unit } = useFittingUnit(units)
  return (
    <div ref={ref} className='ad-slot-frame'>
      {unit && (
        <iframe
          title={AD_LABEL}
          srcDoc={adsterraDocument(unit)}
          width={unit.width}
          height={unit.height}
          scrolling='no'
        />
      )}
    </div>
  )
}

function AadsBanner({ units }: { units: AadsUnit[] }) {
  const { ref, unit } = useFittingUnit(units)
  return (
    <div ref={ref} className='ad-slot-frame'>
      {unit && (
        <iframe
          title={AD_LABEL}
          src={unit.src}
          width={unit.width}
          height={unit.height}
          scrolling='no'
        />
      )}
    </div>
  )
}

export default function AdSlot({ slot }: { slot: AdSlotId }) {
  const config = AD_SLOTS[slot]
  if (!config) return null

  if (config.provider === AD_PROVIDER.DIRECT) {
    return (
      <aside className='ad-slot' aria-label={SPONSOR_LABEL}>
        <span className='ad-slot-label'>{SPONSOR_LABEL} · {config.sponsor}</span>
        <a
          className='ad-slot-frame'
          href={config.href}
          target='_blank'
          rel='sponsored noopener'
        >
          {/* 赞助商素材按原尺寸展示，不走 next/image 的优化和远程域名白名单 */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={config.image}
            alt={config.alt}
            width={config.width}
            height={config.height}
          />
        </a>
      </aside>
    )
  }

  return (
    <aside className='ad-slot' aria-label={AD_LABEL}>
      <span className='ad-slot-label'>{AD_LABEL}</span>
      {config.provider === AD_PROVIDER.EZOIC && (
        <EzoicPlaceholder id={config.placeholderId} />
      )}
      {config.provider === AD_PROVIDER.ADSTERRA && (
        <AdsterraBanner units={config.units} />
      )}
      {config.provider === AD_PROVIDER.AADS && <AadsBanner units={config.units} />}
    </aside>
  )
}
