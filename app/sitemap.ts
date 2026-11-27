import type { MetadataRoute } from 'next'
import { getAllPost } from './api/post/lib'
import { SITE_URL } from '@/lib/site'

// plusPosts is mounted at container runtime, so this route must not be frozen
// against the sample directory that exists while the image is built.
export const dynamic = 'force-dynamic'

const publicRoutes = [
  '',
  '/about',
  '/contact',
  '/standards',
  '/privacy',
  '/privacy/element-scroll-capture',
  '/advertise',
  '/tools',
  '/tools/merge-images',
  '/tools/compress-images',
  '/tools/element-scroll-capture',
  '/pe',
  '/etf-premium',
  '/ashare-strategy',
  '/smallcap-strategy',
]

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const posts = await getAllPost()

  return [
    ...publicRoutes.map((route) => ({
      url: `${SITE_URL}${route}`,
      changeFrequency: route === '' ? ('weekly' as const) : ('monthly' as const),
      priority: route === ''
        ? 1
        : ['/about', '/contact', '/standards', '/privacy', '/privacy/element-scroll-capture'].includes(route)
          ? 0.9
          : route.startsWith('/tools')
            ? 0.7
            : 0.8,
    })),
    ...posts.map((post) => {
      const candidate = new Date(String(post.data.updated || post.data.date || ''))
      const entry: MetadataRoute.Sitemap[number] = {
        url: `${SITE_URL}/post/${post.path
          .split('/')
          .map(encodeURIComponent)
          .join('/')}`,
        changeFrequency: 'yearly',
        priority: 0.72,
      }
      // Frontmatter 日期不可靠时省略 lastModified，不伪造更新时间。
      if (!Number.isNaN(candidate.getTime())) {
        entry.lastModified = candidate
      }
      return entry
    }),
  ]
}
