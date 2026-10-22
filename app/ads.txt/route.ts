import { ADS_TXT_LINES, EZOIC_ADS_TXT_URL, EZOIC_ENABLED } from '@/lib/ads'

const EZOIC_ADS_TXT_REVALIDATE_SECONDS = 3600
const HTTP_NOT_FOUND = 404

// 启用 Ezoic 后，卖方列表由 Ezoic 的 ads.txt 管理器维护，但该管理器是 Ezoic 共用账号，
// 站点审核通过前无法在其中添加自有条目，且审核期间它对本站返回 404（尚无列表）。
// 这里拉取 Ezoic 列表，再合并 ADS_TXT_LINES，保证 AdSense 的卖方条目始终存在
async function fetchEzoicLines(): Promise<string[]> {
  const res = await fetch(EZOIC_ADS_TXT_URL, {
    next: { revalidate: EZOIC_ADS_TXT_REVALIDATE_SECONDS },
  })
  if (res.status === HTTP_NOT_FOUND) return []
  if (!res.ok) throw new Error(`拉取 Ezoic ads.txt 失败: ${res.status}`)
  const text = await res.text()
  return text.split(/\r?\n/).map((line: string) => line.trim()).filter(Boolean)
}

export async function GET() {
  const lines = EZOIC_ENABLED
    ? Array.from(new Set([...ADS_TXT_LINES, ...(await fetchEzoicLines())]))
    : ADS_TXT_LINES
  return new Response(`${lines.join('\n')}\n`, {
    headers: { 'Content-Type': 'text/plain; charset=utf-8' },
  })
}
