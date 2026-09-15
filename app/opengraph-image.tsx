import { ImageResponse } from 'next/og'
import { SITE_DESCRIPTION, SITE_NAME, SITE_TITLE } from '@/lib/site'

// 全站默认分享图：首页、工具页以及任何没指定专属封面的页面都用它。
export const size = { width: 1200, height: 630 }
export const contentType = 'image/png'
export const alt = 'c9cu · 研究、工程与自用工具'

export default function Image() {
  return new ImageResponse(
    (
      <div
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          background: '#f5f7fa',
          padding: '72px',
          position: 'relative',
        }}
      >
        <div
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            height: '10px',
            background: '#075a9c',
          }}
        />

        <div
          style={{
            display: 'flex',
            fontSize: '26px',
            fontWeight: 750,
            color: '#075a9c',
            letterSpacing: '0.02em',
          }}
        >
          {SITE_NAME}
        </div>

        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '24px',
          }}
        >
          <div
            style={{
              display: 'flex',
              fontSize: '76px',
              fontWeight: 700,
              lineHeight: 1.1,
              letterSpacing: '-0.04em',
              color: '#151b26',
              fontFamily:
                'ui-serif, Iowan Old Style, Songti SC, STSong, Georgia, serif',
            }}
          >
            {SITE_TITLE}
          </div>
          <div
            style={{
              display: 'flex',
              fontSize: '30px',
              lineHeight: 1.5,
              color: '#5f6b7a',
              maxWidth: '900px',
            }}
          >
            {SITE_DESCRIPTION}
          </div>
        </div>

        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-end',
            fontSize: '24px',
            color: '#5f6b7a',
          }}
        >
          <div style={{ display: 'flex' }}>记录亲自做过的事，保留方法与局限</div>
          <div style={{ display: 'flex' }}>onlylike.work</div>
        </div>
      </div>
    ),
    size,
  )
}
