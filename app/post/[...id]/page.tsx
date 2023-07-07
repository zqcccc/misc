import dayjs from 'dayjs'
import { getAllPostIds, getPostData, getPostMeta } from '../../api/post/lib'

import './style.css'
import Content from './content'
import ReactCusdis from './Cusdis'

export default async function Post(props: { params: { id: string[] } }) {
  const postData = await getPostData(props.params.id)
  const time = dayjs(postData.date)
  return (
    <article>
      <h1 className='my-1'>{postData.title}</h1>
      <time dateTime={time.toISOString()} className='block mb-4'>
        {time.format('YYYY-MM-DD')}
      </time>
      <Content>{postData.contentHtml}</Content>
      <ReactCusdis />
    </article>
  )
}

export async function generateStaticParams() {
  return await getAllPostIds()
  // const paths = await getAllPostIds()
  // return {
  //   paths,
  //   fallback: false,
  // }
}

export async function generateMetadata({ params }: any) {
  const postMeta = getPostMeta(params.id)
  return {
    title: postMeta.data.title || 'post',
  }
}
