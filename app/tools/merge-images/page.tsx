import type { Metadata } from 'next'
import dynamic from 'next/dynamic'
import Link from 'next/link'

export const metadata: Metadata = {
  title: '图片合并工具',
  description:
    '在浏览器本地完成多图排序、横向或纵向拼接，并导出 PNG、JPEG 或 WebP；图片不会上传服务器。',
  alternates: { canonical: '/tools/merge-images' },
  openGraph: {
    title: '图片合并工具 · c9cu',
    description: '多图排序与拼接，全程在当前浏览器本地处理。',
    url: '/tools/merge-images',
    type: 'website',
  },
}

const MergeImagesClient = dynamic(() => import('./MergeImagesClient'))

export default function Page() {
  return (
    <main className='browser-tool-page'>
      <header>
        <h1>图片合并</h1>
        <p>上传多张图片，调整顺序后按横向或纵向拼接。你可以统一宽度或高度，并导出 PNG、JPEG 或 WebP。</p>
        <strong>图片只在当前浏览器中处理，不会上传到本站服务器。</strong>
      </header>

      <section className='browser-tool-workspace' aria-label='图片合并操作区'>
        <MergeImagesClient />
      </section>

      <section className='browser-tool-guide' aria-labelledby='merge-guide-title'>
        <h2 id='merge-guide-title'>怎么用</h2>
        <ol>
          <li><strong>选择图片。</strong><span>支持一次加入多张图片；敏感图片也不会离开你的设备。</span></li>
          <li><strong>调整布局。</strong><span>拖动排序，选择横向或纵向，并决定是否统一尺寸。</span></li>
          <li><strong>导出结果。</strong><span>按用途选择格式和质量，再下载生成的图片。</span></li>
        </ol>
      </section>

      <section className='browser-tool-faq' aria-labelledby='merge-faq-title'>
        <h2 id='merge-faq-title'>使用边界</h2>
        <div>
          <h3>为什么大图可能失败？</h3>
          <p>合并过程会占用设备内存。图片很多或分辨率很高时，浏览器可能因为内存不足中止；可先压缩或分批合并。</p>
          <h3>页面会保存图片吗？</h3>
          <p>不会。刷新或关闭页面后，当前操作状态可能丢失，请及时下载结果。</p>
        </div>
      </section>

      <nav className='browser-tool-related' aria-label='相关链接'>
        <Link href='/tools/compress-images'>先压缩图片</Link>
        <Link href='/privacy'>查看隐私说明</Link>
        <Link href='/tools'>返回全部工具</Link>
      </nav>
    </main>
  )
}
