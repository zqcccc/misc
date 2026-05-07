import Post from './post/page'
import BlogLayout from './post/blogLayout'

export const revalidate = 3600

export default function Home() {
  return (
    <BlogLayout>
      <Post />
    </BlogLayout>
  )
}
