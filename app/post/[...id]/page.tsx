import dayjs from 'dayjs'
import { getAllPostIds, getPostData, getPostMeta } from '../../api/post/lib'

import Content from './content'
import ReactCusdis from './Cusdis'

export default async function Post(props: { params?: { id?: string[] } }) {
  console.log('%c props: ', 'font-size:12px;background-color: #B03734;color:#fff;', props)
  if (!props.params?.id) return <>not found</>
  const postData = await getPostData(props.params.id)
  console.log('postData.date: ', postData.date)
  const time = dayjs(postData.date || undefined)
  const changeTime = dayjs(postData.changeTime)
  const createTimeStr = time.format('YYYY-MM-DD')
  // const changeTimeStr = changeTime.format('YYYY-MM-DD')
  return (
    <article>
      <h1 className='my-1'>{postData.title}</h1>
      <div className='flex'>
        <time dateTime={time.toISOString()} className='block mb-4'>
          {createTimeStr}
        </time>
        {/* {createTimeStr !== changeTimeStr && (
          <div className='ml-3'>
            <time dateTime={changeTime.toISOString()} className='block mb-4'>
              修改于{changeTimeStr}
            </time>
          </div>
        )} */}
      </div>
      <Content source={postData.contentHtml} />
      <ReactCusdis />
    </article>
  )
}

export async function generateStaticParams() {
  // return await getAllPostIds()
  const paths = await getAllPostIds()
  console.log('paths: ', paths)
  return paths
}

export async function generateMetadata({ params }: any) {
  const postMeta = getPostMeta(params.id)
  return {
    title: postMeta.data.title || 'post',
  }
}
