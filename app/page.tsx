import Post from './post/page'
import BlogLayout from './post/blogLayout'

export const dynamic = 'force-dynamic'

export default function Home() {
  return (
    <BlogLayout>
      <Post />
    </BlogLayout>
  )
}
