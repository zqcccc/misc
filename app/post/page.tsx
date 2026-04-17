import dayjs from 'dayjs'
import { Fragment } from 'react'
import Link from 'next/link'
import { getAllPost } from '../api/post/lib'

export const revalidate = 3600

const DATE_FORMAT = 'MMMM DD, YYYY'

export default async function Post() {
  const posts = await getAllPost()

  return (
    <main className='transition-all'>
      <ol className='list-none'>
        {posts.map((post, index) => {
          if (!post || Array.isArray(post))
            return <Fragment key={index}></Fragment>
          const time = dayjs(post.data.date).format(DATE_FORMAT)
          return (
            <li key={index} className='mt-8'>
              <Link
                className='block text-[#005b99] text-3xl mb-2 font-bold dark:text-[#f9e062]'
                href={'post/' + post.path}
                prefetch={false}
              >
                {post.data.title}
              </Link>
              <div className='mb-4 text-sm'>{time}</div>
              <div className='text-base'>{post.data.description}</div>
            </li>
          )
        })}
      </ol>
    </main>
  )
}
