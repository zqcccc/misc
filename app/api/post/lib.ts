import fs from 'fs'
import path from 'path'
import matter, { GrayMatterFile } from 'gray-matter'
// import { remark } from 'remark'
// import html from 'remark-html'
// import remarkParse from 'remark-parse'
import remarkGfm from 'remark-gfm'
// import remarkRehype from 'remark-rehype'
// import rehypeSanitize from 'rehype-sanitize'
// import rehypeStringify from 'rehype-stringify'
// import rehypePrism from '@mapbox/rehype-prism'
import rehypePrettyCode from 'rehype-pretty-code'
import { serialize } from 'next-mdx-remote/serialize'

const postsDirectory = path.join(process.cwd(), 'posts')

const plusDirectory = path.join(process.cwd(), 'plusPosts')

type Nested<T> = (T | null | Nested<T>)[] | T | null
type NestedString = Nested<string>

function readFile(
  filePath: string,
  callback?: (err: NodeJS.ErrnoException | null, data: Buffer) => void
) {
  return new Promise<Buffer>((resolve, reject) => {
    fs.readFile(filePath, {}, (err, data) => {
      if (err) reject(err)
      callback?.(err, data)
      resolve(data)
    })
  })
}

export async function getAllPostsPath(dirPath = postsDirectory) {
  let fileNames = fs.readdirSync(dirPath)
  const allPaths = await Promise.all(
    fileNames.map(async (fileName) => {
      const p = path.join(dirPath, fileName)
      return new Promise<NestedString>((resolve, reject) => {
        fs.stat(p, (err, stats) => {
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
  const allPaths = await getAllPostsPath()
  const linkPaths = allPaths.map((filePath) => {
    return {
      id: path.relative(postsDirectory, filePath).split('.')[0].split('/'),
    }
  })
  if (fs.existsSync(plusDirectory)) {
    const plusPaths = await getAllPostsPath(plusDirectory)
    linkPaths.push(
      ...plusPaths.map((filePath) => {
        return {
          id: path.relative(plusDirectory, filePath).split('.')[0].split('/'),
        }
      })
    )
    // allPaths.push(...(plusPaths))
  }
  return linkPaths
  // return allPaths.map((filePath) => {
  //   return {
  //     params: {
  //       id: path.relative(postsDirectory, filePath).split('.')[0].split('/'),
  //     },
  //   }
  // })
}

export async function getAllPost(dirPath = postsDirectory) {
  const allPaths = await getAllPostsPath()
  if (fs.existsSync(plusDirectory)) {
    allPaths.push(...(await getAllPostsPath(plusDirectory)))
  }
  const allPosts = await Promise.all(
    allPaths.map(async (filePath) => {
      return readFile(filePath).then((fileContent) => {
        const matterResult = matter(fileContent.toString())
        return {
          ...matterResult,
          path: filePath.includes(postsDirectory)
            ? path.relative(postsDirectory, filePath).split('.')[0]
            : path.relative(plusDirectory, filePath).split('.')[0],
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
  return allPosts
}

export function getPostMeta(id: string[]) {
  id[id.length - 1] = decodeURIComponent(id[id.length - 1]) + '.md'
  const path1 = path.join(postsDirectory, ...id)
  const path2 = path.join(plusDirectory, ...id)
  const fullPath = fs.existsSync(path1)
    ? path1
    : fs.existsSync(path2)
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
    }
  }
  const fileContents = fs.readFileSync(fullPath, 'utf8')
  const stat = fs.statSync(fullPath)
  const matterResult = matter(fileContents) as GrayMatterFile<string> & {
    data: {
      title: string
      date: string
    }
  }
  return {
    id,
    changeTime: stat.mtime,
    ...matterResult,
  }
}

export async function getPostData(id: string[]) {
  const matterResult = getPostMeta(id)

  // Use remark to convert markdown into HTML string
  // const processedContent = await remark()
  //   .use(remarkRehype)
  //   // .use(rehypePrism)
  //   .use(rehypePrettyCode, {
  //     theme: 'one-dark-pro',
  //   })
  //   .use(rehypeStringify)
  //   // .use(rehypeSanitize)
  //   .use(remarkGfm)
  //   .process(matterResult.content)
  const mdxSource = await serialize(matterResult.content, {
    mdxOptions: {
      remarkPlugins: [remarkGfm],
      rehypePlugins: [
        [
          rehypePrettyCode,
          {
            theme: 'one-dark-pro',
          },
        ],
      ],
      format: 'mdx',
    },
  })
  // console.log('mdxSource: ', mdxSource)
  // const contentHtml = processedContent.toString()
  const contentHtml = mdxSource

  // Combine the data with the id and contentHtml
  return {
    id,
    contentHtml,
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
