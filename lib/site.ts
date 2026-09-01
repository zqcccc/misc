export const SITE_NAME = 'c9cu'
export const SITE_URL = 'https://onlylike.work'
export const SITE_EMAIL = 'zhao172232502@gmail.com'
export const SITE_TITLE = 'c9cu · 研究、工程与自用工具'
export const SITE_DESCRIPTION =
  'c9cu 的个人网站：记录亲自做过的投资研究、工程实践和自用工具，并说明方法、证据与局限。'

type PostLike = {
  path: string
  data: Record<string, unknown>
  source?: 'builtin' | 'plus'
}

const HIDDEN_POST_PATHS = new Set([
  'cloudflare/warp',
  'cursor/ycursor',
  'dns/解锁网飞',
  'gatsby/index',
  'k8s/practice',
  'proxy/ipv6',
  'proxy/naive',
  'reg/index',
  'v-machine/hyper-v-openwrt',
  'vps/recommend',
  'webpack/index',
])

const HIDDEN_POST_PREFIXES = ['proxy/', 'dns/']

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
