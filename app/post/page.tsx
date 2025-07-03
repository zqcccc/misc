import dayjs from 'dayjs'
import { getAllPost } from '../api/post/lib'
import { Fragment } from 'react'
import Link from 'next/link'
import { headers } from 'next/headers'
// import { useState } from 'react'

// export const metadata = {
//   title: 'All posts',
// }

export default async function Post() {
  const res =  await headers() // trigger dynamic import all post
  console.log('headers res: ', res)
  // const start = new Date().getTime()
  // const res = await fetch('/api/post').then((res) => res.text())
  // console.log('%c res: ', 'font-size:12px;background-color: #4b4b4b;color:#fff;', res)
  const posts = await getAllPost()
  console.log('posts: ', posts.map((post) => post.data.title))
  // const end = new Date().getTime()
  // const diffInMilliseconds = Math.abs(end - start)
  // console.log('%c diffInMilliseconds: ', 'font-size:12px;background-color: #CECAC1;color:#fff;', diffInMilliseconds)
  // console.log(
  //   '%c posts: ',
  //   'font-size:12px;background-color: #5A4E52;color:#fff;',
  //   posts
  // )

  return (
    <main className='transition-all'>
      <ol className='list-none'>
        {posts.map((post, index) => {
          if (!post || Array.isArray(post))
            return <Fragment key={index}></Fragment>
          const time = dayjs(post.data.date).format('MMMM DD, YYYY')
          return (
            <li key={index} className='mt-8'>
              <Link className='block text-[#005b99] text-3xl mb-2 font-bold dark:text-[#f9e062]' href={'post/' + post.path} prefetch={false}>
                {post.data.title}
              </Link>
              <div className='mb-4 text-sm'>{time}</div>
              <div className='text-base'>
                {post.data.description}
              </div>
            </li>
          )
        })}
      </ol>
    </main>
  )
}
