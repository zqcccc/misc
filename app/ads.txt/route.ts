import { ADS_TXT_LINES, EZOIC_ADS_TXT_URL, EZOIC_ENABLED } from '@/lib/ads'

// 启用 Ezoic 后由它的 ads.txt 管理器维护卖方列表，其他广告联盟要求的条目也在 Ezoic 后台添加
export function GET() {
  if (EZOIC_ENABLED) return Response.redirect(EZOIC_ADS_TXT_URL, 301)
  return new Response(`${ADS_TXT_LINES.join('\n')}\n`, {
    headers: { 'Content-Type': 'text/plain; charset=utf-8' },
  })
}
