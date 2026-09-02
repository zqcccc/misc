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
  '/tools',
  '/tools/merge-images',
  '/tools/compress-images',
  '/pe',
  '/ashare-strategy',
  '/trhrp-backtest',
]

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const posts = await getAllPost()
  const now = new Date()

  return [
    ...publicRoutes.map((route) => ({
      url: `${SITE_URL}${route}`,
      lastModified: now,
      changeFrequency: route === '' ? ('weekly' as const) : ('monthly' as const),
      priority: route === '' ? 1 : route.startsWith('/tools') ? 0.7 : 0.8,
    })),
    ...posts.map((post) => {
      const candidate = new Date(String(post.data.updated || post.data.date || ''))
      return {
        url: `${SITE_URL}/post/${post.path
          .split('/')
          .map(encodeURIComponent)
          .join('/')}`,
        lastModified: Number.isNaN(candidate.getTime()) ? now : candidate,
        changeFrequency: 'yearly' as const,
        priority: 0.72,
      }
    }),
  ]
}
