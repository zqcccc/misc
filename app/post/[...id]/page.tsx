import type { Metadata } from 'next'
import Link from 'next/link'
import { notFound } from 'next/navigation'
import { getAllPostIds, getPostData, getPostMeta } from '../../api/post/lib'
import Content from './content'
import ReactCusdis from './Cusdis'
import {
  formatPostDate,
  getPostCategory,
  isArchivedPost,
  isHistoricalPost,
  isPublicPost,
  SITE_CATEGORIES,
  SITE_DESCRIPTION,
  SITE_NAME,
  SITE_URL,
  stripDuplicateMarkdownTitle,
} from '@/lib/site'

export const dynamicParams = true

type PageProps = { params?: Promise<{ id?: string[] }> }

function getPath(id: string[]): string {
  return id.map((segment) => decodeURIComponent(segment)).join('/')
}

function getPostUrl(id: string[]): string {
  return `${SITE_URL}/post/${id.map(encodeURIComponent).join('/')}`
}

export default async function Post(props: PageProps) {
  const id = (await props.params)?.id
  if (!id?.length) notFound()

  const meta = getPostMeta(id)
  const postPath = getPath(id)
  if (!isPublicPost({ path: postPath, data: meta.data, source: meta.source })) notFound()

  const postData = await getPostData(id)
  const category = getPostCategory({ path: postPath, data: meta.data })
  const categoryLabel = SITE_CATEGORIES[category].label
  const historical = isHistoricalPost(postData.date)
  const archived = isArchivedPost({ path: postPath, data: meta.data, source: meta.source })
  const postUrl = getPostUrl(id)
  const published = new Date(postData.date)
  const publishedIso = Number.isNaN(published.getTime())
    ? undefined
    : published.toISOString()
  const updated = postData.updated ? new Date(postData.updated) : null
  const source = stripDuplicateMarkdownTitle(postData.content, postData.title)
  const isFinancial = category === 'research'

  const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'BlogPosting',
    headline: postData.title,
    description: postData.description || SITE_DESCRIPTION,
    mainEntityOfPage: postUrl,
    inLanguage: 'zh-Hans',
    datePublished: publishedIso,
    dateModified:
      updated && !Number.isNaN(updated.getTime())
        ? updated.toISOString()
        : undefined,
    author: {
      '@type': 'Person',
      name: SITE_NAME,
      url: `${SITE_URL}/about`,
    },
    publisher: {
      '@type': 'Person',
      name: SITE_NAME,
      url: `${SITE_URL}/about`,
    },
  }

  return (
    <article className='article-page'>
      <script
        type='application/ld+json'
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <header className='article-header'>
        <div className='article-context'>
          <Link href={`/#notes-${category}`}>{categoryLabel}</Link>
          <span aria-hidden='true'>/</span>
          <span>作者：<Link href='/about'>c9cu</Link></span>
        </div>
        <h1>{postData.title}</h1>
        {postData.description && (
          <p className='article-description'>{postData.description}</p>
        )}
        <div className='article-dates'>
          <time dateTime={publishedIso}>
            发布于 {formatPostDate(postData.date)}
          </time>
          {updated && !Number.isNaN(updated.getTime()) && (
            <time dateTime={updated.toISOString()}>
              最后验证 {formatPostDate(postData.updated)}
            </time>
          )}
          {historical && (
            <span className='article-status'>历史笔记，部分步骤可能已过时</span>
          )}
        </div>
      </header>

      {isFinancial && (
        <aside className='article-disclosure'>
          <strong>研究边界</strong>
          <p>
            本文记录个人研究过程，不构成投资建议或收益承诺。历史数据与回测不能保证未来结果；请结合数据截至日、方法局限和独立资料判断。
          </p>
          <Link href='/standards#financial'>查看完整披露</Link>
        </aside>
      )}

      {archived && (
        <aside className='article-archive-notice'>
          <strong>这是一份历史研究档案</strong>
          <p>相关实时监控与定时数据服务已经下线，文中的规则和历史结果保留作研究记录，不代表当前仍在运行。</p>
        </aside>
      )}

      <div className='article-prose'>
        <Content source={source} />
      </div>

      <footer className='article-footer'>
        <div>
          <strong>关于作者</strong>
          <p>c9cu 在这里记录亲自做过的研究、工程实践和自用工具，并尽量保留方法、证据与局限。</p>
        </div>
        <nav aria-label='文章相关链接'>
          <Link href='/about'>关于 c9cu</Link>
          <Link href='/contact'>报告错误</Link>
          <Link href='/standards'>内容原则</Link>
        </nav>
      </footer>

      <ReactCusdis className='article-comments' />
    </article>
  )
}

export async function generateStaticParams() {
  return await getAllPostIds()
}

export async function generateMetadata(props: PageProps): Promise<Metadata> {
  const id = (await props.params)?.id
  if (!id?.length) return { title: '文章不存在', robots: { index: false } }

  const postMeta = getPostMeta(id)
  const postPath = getPath(id)
  if (!isPublicPost({ path: postPath, data: postMeta.data, source: postMeta.source })) {
    return { title: '文章不存在', robots: { index: false, follow: false } }
  }

  const title = postMeta.data.title || '文章'
  const description = postMeta.data.description || SITE_DESCRIPTION
  const url = getPostUrl(id)
  const published = new Date(postMeta.data.date)
  const updated = postMeta.data.updated
    ? new Date(postMeta.data.updated)
    : undefined

  return {
    title,
    description,
    authors: [{ name: SITE_NAME, url: `${SITE_URL}/about` }],
    alternates: { canonical: url },
    openGraph: {
      type: 'article',
      title,
      description,
      url,
      authors: [SITE_NAME],
      publishedTime: Number.isNaN(published.getTime())
        ? undefined
        : published.toISOString(),
      modifiedTime:
        updated && !Number.isNaN(updated.getTime())
          ? updated.toISOString()
          : undefined,
    },
    twitter: {
      card: 'summary_large_image',
      title,
      description,
    },
  }
}
