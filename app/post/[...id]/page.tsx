import dayjs from 'dayjs'
import { getAllPostIds, getPostData, getPostMeta } from '../../api/post/lib'

import Content from './content'
import ReactCusdis from './Cusdis'

export const dynamicParams = true

export default async function Post(props: { params?: Promise<{ id?: string[] }> }) {
  if (!(await props.params)?.id) return <>not found</>
  const postData = await getPostData((await props.params)?.id || [])
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
      <Content source={postData.content} />
      <ReactCusdis className='mt-12' />
    </article>
  )
}

export async function generateStaticParams() {
  return await getAllPostIds()
}

export async function generateMetadata(props: any) {
  const params = await props.params;
  const postMeta = getPostMeta(params.id)
  return {
    title: postMeta.data.title || 'post',
  }
}
