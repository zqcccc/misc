import type { Metadata } from 'next'
import dynamic from 'next/dynamic'
import Link from 'next/link'

export const metadata: Metadata = {
  title: '图片压缩工具',
  description:
    '在浏览器本地批量压缩、缩放和转换 JPG、PNG、WebP，支持 ZIP 下载；图片不会上传服务器。',
  alternates: { canonical: '/tools/compress-images' },
  openGraph: {
    title: '图片压缩工具 · c9cu',
    description: '批量缩放与格式转换，全程在当前浏览器本地处理。',
    url: '/tools/compress-images',
    type: 'website',
  },
}

const CompressImagesClient = dynamic(() => import('./CompressImagesClient'))

export default function Page() {
  return (
    <main className='browser-tool-page'>
      <header>
        <h1>图片压缩</h1>
        <p>批量调整 JPG、PNG、WebP 的尺寸、格式和质量。可以拖入、选择或粘贴图片，再分别下载或打包成 ZIP。</p>
        <strong>图片只在当前浏览器中处理，不会上传到本站服务器。</strong>
      </header>

      <section className='browser-tool-workspace' aria-label='图片压缩操作区'>
        <CompressImagesClient />
      </section>

      <section className='browser-tool-guide' aria-labelledby='compress-guide-title'>
        <h2 id='compress-guide-title'>怎么用</h2>
        <ol>
          <li><strong>加入图片。</strong><span>可拖放、点击选择或直接粘贴，多张图片会逐项处理。</span></li>
          <li><strong>设置目标。</strong><span>选择尺寸、格式和质量；降低尺寸通常比一味降低质量更有效。</span></li>
          <li><strong>检查并下载。</strong><span>对比输出体积，单独下载或打包为 ZIP。</span></li>
        </ol>
      </section>

      <section className='browser-tool-faq' aria-labelledby='compress-faq-title'>
        <h2 id='compress-faq-title'>使用边界</h2>
        <div>
          <h3>PNG 为什么可能压不小？</h3>
          <p>PNG 是无损格式，照片类内容转为 WebP 或 JPEG 通常更省空间；图标、透明图和文字截图则更适合保留 PNG。</p>
          <h3>压缩是否会损失画质？</h3>
          <p>缩小尺寸或降低有损格式质量都会减少细节。建议先用默认值导出，查看实际用途下是否清晰。</p>
        </div>
      </section>

      <nav className='browser-tool-related' aria-label='相关链接'>
        <Link href='/tools/merge-images'>合并图片</Link>
        <Link href='/privacy'>查看隐私说明</Link>
        <Link href='/tools'>返回全部工具</Link>
      </nav>
    </main>
  )
}
