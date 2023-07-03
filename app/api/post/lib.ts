import fs from 'fs'
import path, { resolve } from 'path'
import matter, { GrayMatterFile } from 'gray-matter'
import { remark } from 'remark'
// import html from 'remark-html'
// import remarkParse from 'remark-parse'
import remarkGfm from 'remark-gfm'
import remarkRehype from 'remark-rehype'
// import rehypeSanitize from 'rehype-sanitize'
import rehypeStringify from 'rehype-stringify'
import rehypePrism from '@mapbox/rehype-prism'
import rehypePrettyCode from 'rehype-pretty-code'

const postsDirectory = path.join(process.cwd(), 'posts')

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
  const fileNames = fs.readdirSync(dirPath)
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
  return allPaths.map((filePath) => {
    return {
      id: path.relative(postsDirectory, filePath).split('.')[0].split('/'),
    }
  })
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
  return Promise.all(
    allPaths.map(async (filePath) => {
      return readFile(filePath).then((fileContent) => {
        const matterResult = matter(fileContent.toString())
        return {
          ...matterResult,
          path: path.relative(postsDirectory, filePath).split('.')[0],
        }
      })
    })
  )
}

export function getPostMeta(id: string[]) {
  id[id.length - 1] = decodeURIComponent(id[id.length - 1]) + '.md'
  const fullPath = path.join(postsDirectory, ...id)
  const fileContents = fs.readFileSync(fullPath, 'utf8')
  const matterResult = matter(fileContents) as GrayMatterFile<string> & {
    data: {
      title: string
      date: string
    }
  }
  return {
    id,
    ...matterResult,
  }
}

export async function getPostData(id: string[]) {
  const matterResult = getPostMeta(id)

  // Use remark to convert markdown into HTML string
  const processedContent = await remark()
    .use(remarkRehype)
    // .use(rehypePrism)
    .use(rehypePrettyCode, {
      // See Options section below.
    })
    .use(rehypeStringify)
    // .use(rehypeSanitize)
    .use(remarkGfm)
    .process(matterResult.content)
  const contentHtml = processedContent.toString()

  // Combine the data with the id and contentHtml
  return {
    id,
    contentHtml,
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
