import Post from './post/page'
import BlogLayout from './post/blogLayout'
import SandboxedAd from '@/components/SandboxedAd'

export const dynamic = 'force-dynamic'

export default function Home() {
  return (
    <BlogLayout>
      <div className="mb-10 w-full">
        <SandboxedAd />
      </div>
      <Post />
    </BlogLayout>
  )
}
