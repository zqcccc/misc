export const SITE_NAME = 'c9cu'
export const SITE_URL = 'https://onlylike.work'
export const SITE_EMAIL = 'zhao172232502@gmail.com'
export const SITE_TITLE = 'c9cu · 研究、工程与自用工具'
export const SITE_DESCRIPTION =
  'c9cu 的个人网站：记录亲自做过的投资研究、工程实践和自用工具，并说明方法、证据与局限。'

// 站点默认分享图。分享卡片(含 X/Twitter)封面靠 og:image / twitter:image 标签决定，
// 文章没在 frontmatter 里写 cover 时统一回落到这张。
export const SITE_OG_IMAGE = '/og-default.png'

/**
 * 解析一篇文章的分享封面。
 *
 * 优先级：frontmatter 的 cover > 站点默认图。
 * 站内绝对路径与完整 URL 都接受，缺协议头的会补成绝对地址，
 * 因为 og:image 必须是绝对 URL，社交平台抓不到相对路径。
 */
export function resolvePostCover(
  cover: unknown,
): { url: string; alt?: string } | null {
  const value = String(cover ?? '').trim()
  if (!value) return null

  const url = value.startsWith('http') ? value : `${SITE_URL}${value.startsWith('/') ? '' : '/'}${value}`
  return { url }
}

type PostLike = {
  path: string
  data: Record<string, unknown>
  source?: 'builtin' | 'plus'
}

const HIDDEN_POST_PATHS = new Set([
  'vps/recommend',
])

const HIDDEN_POST_PREFIXES = ['proxy/', 'dns/']

/**
 * 按合规风险屏蔽的文章（对所有来源生效，包括 plus 目录）。
 *
 * 这几篇讲的是更换机器码重置软件试用状态、以及搭建代理访问受限站点，
 * 属于 Google AdSense 计划政策里的高风险类别——这类内容的杀伤力远大于
 * 「内容偏薄」，只要站内还能被抓到，审核基本不可能通过。站内的
 * /standards 早就写明这类内容不应留在公开文章系统与站点地图里。
 *
 * 这里只做下架（导航 / 站点地图 / 列表不再出现，直接访问返回 404），
 * 不从磁盘删除，需要恢复时把这个集合改回去即可。
 */
const COMPLIANCE_BLOCKED_PATHS = new Set([
  // 更换机器码重置 cursor 试用状态 —— 协助绕过付费限制
  'cursor/ycursor',
  // 用 warp 分流访问 Netflix / ChatGPT —— 代理翻墙
  'cloudflare/warp',
  // 旁路由透明代理给 PS5 等设备访问 Netflix —— 代理翻墙
  'v-machine/hyper-v-openwrt',
])

export function normalizePostPath(value: string): string {
  try {
    return decodeURIComponent(value).replace(/^\/+|\/+$/g, '')
  } catch {
    return value.replace(/^\/+|\/+$/g, '')
  }
}

export function isPublicPost(post: PostLike): boolean {
  const postPath = normalizePostPath(post.path)
  const title = String(post.data.title || '')

  if (post.data.published === false || post.data.draft === true) return false
  if (post.data.archived === true) return false
  if (!title) return false

  // Production mounts an independently managed plusPosts directory over the
  // sample folder in the image. Its articles must be governed by their own
  // frontmatter, not by rules written for the repository's legacy posts.
  if (post.source === 'plus') return true

  if (HIDDEN_POST_PATHS.has(postPath)) return false
  if (HIDDEN_POST_PREFIXES.some((prefix) => postPath.startsWith(prefix))) {
    return false
  }

  return true
}

export type SiteCategory = 'research' | 'engineering' | 'reflection'

export const SITE_CATEGORIES: Record<
  SiteCategory,
  { label: string; description: string }
> = {
  research: {
    label: '研究',
    description: '投资、估值与策略实验，保留数据口径和方法局限。',
  },
  engineering: {
    label: '工程',
    description: '来自真实项目的实现记录、踩坑和可复现步骤。',
  },
  reflection: {
    label: '记录',
    description: '个人观察、年度回顾，以及对工具变化的判断。',
  },
}

export function getPostCategory(post: PostLike): SiteCategory {
  const explicit = String(post.data.category || '')
  if (explicit in SITE_CATEGORIES) return explicit as SiteCategory

  const postPath = normalizePostPath(post.path)
  const title = String(post.data.title || '')
  if (
    postPath.startsWith('trhrp') ||
    postPath.startsWith('etf/') ||
    /策略|估值|投资|现金流|回测/.test(title)
  ) {
    return 'research'
  }
  if (postPath.startsWith('ai/') || /总结|回顾|观察/.test(title)) {
    return 'reflection'
  }
  return 'engineering'
}

export function formatPostDate(value: unknown): string {
  const date = new Date(String(value || ''))
  if (Number.isNaN(date.getTime())) return ''
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(date)
}

export function isHistoricalPost(value: unknown): boolean {
  const date = new Date(String(value || ''))
  if (Number.isNaN(date.getTime())) return false
  const threeYears = 1000 * 60 * 60 * 24 * 365 * 3
  return Date.now() - date.getTime() > threeYears
}

export function isArchivedPost(post: PostLike): boolean {
  return post.data.archived === true
}

export function stripDuplicateMarkdownTitle(
  source: string,
  title: string,
): string {
  const normalizedTitle = title.trim().replace(/\s+/g, ' ')
  const match = source.match(/^\s*#\s+(.+?)\s*(?:\n|$)/)
  if (!match) return source
  const markdownTitle = match[1].trim().replace(/\s+/g, ' ')
  return markdownTitle === normalizedTitle ? source.slice(match[0].length) : source
}
