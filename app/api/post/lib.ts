import fs from 'fs'
import path from 'path'
import { unstable_cache } from 'next/cache'
import matter, { GrayMatterFile } from 'gray-matter'
import { isPublicPost } from '@/lib/site'

// 文章根目录在运行时动态读取 (posts 由 next.config.js 的 outputFileTracingIncludes 打进
// 镜像, plusPosts 由容器运行时挂载), 构建期 NFT 无法静态追踪; 所有动态 fs/path 访问点
// 统一加 turbopackIgnore, 避免动态访问导致整仓追踪。
const postsDirectory = path.join(/* turbopackIgnore: true */ process.cwd(), 'posts')

const plusDirectory = path.join(/* turbopackIgnore: true */ process.cwd(), 'plusPosts')

const postDirectories = [postsDirectory, plusDirectory]

type Nested<T> = (T | null | Nested<T>)[] | T | null
type NestedString = Nested<string>

export type PostFrontmatter = {
  title: string
  date: string
  description?: string
  updated?: string
  category?: string
  published?: boolean
  draft?: boolean
  archived?: boolean
  cover?: string
}

function readFile(
  filePath: string,
  callback?: (err: NodeJS.ErrnoException | null, data: Buffer) => void
) {
  return new Promise<Buffer>((resolve, reject) => {
    fs.readFile(/* turbopackIgnore: true */ filePath, {}, (err, data) => {
      if (err) reject(err)
      callback?.(err, data)
      resolve(data)
    })
  })
}

export async function getAllPostsPath(dirPath = postsDirectory) {
  let fileNames = fs.readdirSync(/* turbopackIgnore: true */ dirPath)
  const allPaths = await Promise.all(
    fileNames.map(async (fileName) => {
      const p = path.join(/* turbopackIgnore: true */ dirPath, fileName)
      return new Promise<NestedString>((resolve, reject) => {
        fs.stat(/* turbopackIgnore: true */ p, (err, stats) => {
          if (err) {
            console.error(err)
            reject(err)
            return
          }
          if (stats.isFile()) {
            if (fileName.endsWith('.md')) {
              resolve(p)
            } else {
              resolve(null)
            }
          } else if (stats.isDirectory()) {
            resolve(getAllPostsPath(p))
          } else {
            resolve(null)
          }
        })
      })
    })
  )
  return flattenArray(allPaths).filter(Boolean) as string[]
}

export async function getAllPostIds() {
  const posts = await getAllPost()
  return posts.map((post) => ({ id: post.path.split('/') }))
}

export async function getAllPost(dirPath = postsDirectory) {
  const allPaths =
    dirPath === postsDirectory
      ? (
          await Promise.all(
            postDirectories
              .filter((directory) => fs.existsSync(/* turbopackIgnore: true */ directory))
              .map((directory) => getAllPostsPath(directory))
          )
        ).flat()
      : await getAllPostsPath(dirPath)
  const allPosts = await Promise.all(
    allPaths.map(async (filePath) => {
      return readFile(filePath).then((fileContent) => {
        const matterResult = matter(fileContent.toString())
        const sourceDirectory = postDirectories.find(
          (directory) =>
            filePath === directory || filePath.startsWith(directory + path.sep)
        )

        return {
          ...matterResult,
          source: sourceDirectory === plusDirectory ? ('plus' as const) : ('builtin' as const),
          path: path
            .relative(sourceDirectory || dirPath, filePath)
            .replace(/\.md$/, ''),
        }
      })
    })
  )
  allPosts.sort((a, b) => {
    if (a.data.date < b.data.date) {
      return 1
    } else {
      return -1
    }
  })
  return allPosts.filter((post) => isPublicPost(post))
}

export const getCachedAllPost = unstable_cache(
  () => getAllPost(),
  ['all-posts-v3'],
  { revalidate: 3600, tags: ['posts'] }
)

export function getPostMeta(id: string[]): {
  id: string[]
  changeTime: Date
  content: string
  data: PostFrontmatter
  source: 'builtin' | 'plus'
} {
  const fileId = [...id]
  fileId[fileId.length - 1] =
    decodeURIComponent(fileId[fileId.length - 1]) + '.md'
  const path1 = path.join(/* turbopackIgnore: true */ postsDirectory, ...fileId)
  const path2 = path.join(/* turbopackIgnore: true */ plusDirectory, ...fileId)
  const fullPath = fs.existsSync(/* turbopackIgnore: true */ path1)
    ? path1
    : fs.existsSync(/* turbopackIgnore: true */ path2)
    ? path2
    : ''
  if (!fullPath) {
    return {
      id,
      changeTime: new Date(),
      content: '404',
      data: {
        title: '',
        date: '',
      },
      source: 'builtin',
    }
  }
  const fileContents = fs.readFileSync(/* turbopackIgnore: true */ fullPath, 'utf8')
  const stat = fs.statSync(/* turbopackIgnore: true */ fullPath)
  const matterResult = matter(fileContents) as GrayMatterFile<string> & {
    data: PostFrontmatter
  }
  return {
    id,
    changeTime: stat.mtime,
    source: fullPath === path2 ? 'plus' : 'builtin',
    ...matterResult,
  }
}

export async function getPostData(id: string[]) {
  const matterResult = getPostMeta(id)
  return {
    id,
    content: matterResult.content,
    changeTime: matterResult.changeTime,
    ...matterResult.data,
  }
}

function flattenArray<T>(arr: (T[] | T)[]): T[] {
  let flattened: T[] = []

  for (let i = 0; i < arr.length; i++) {
    const item = arr[i]
    if (Array.isArray(item)) {
      flattened = flattened.concat(flattenArray(item))
    } else {
      flattened.push(item)
    }
  }

  return flattened
}
