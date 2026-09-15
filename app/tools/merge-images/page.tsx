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

      <section className='browser-tool-faq' aria-labelledby='merge-when-title'>
        <h2 id='merge-when-title'>什么时候该用它，什么时候不该</h2>
        <div>
          <h3>适合</h3>
          <p>
            把一组截图、聊天记录分段、商品图或对比图拼成一张发出去——尤其是对方只看一张图、不想点开九宫格的时候。也适合把手机连拍的几张图拼成一张长图再存档。
          </p>
          <h3>不适合</h3>
          <p>
            需要保留透明通道、图层或原始分辨率的场合，导出成 PNG 之外的有损格式会丢信息。要做印刷、设计交付或需要二次编辑的图，请回到设计工具里排版，这里只负责快速拼出一张成品图。
          </p>
        </div>
      </section>

      <section className='browser-tool-faq' aria-labelledby='merge-params-title'>
        <h2 id='merge-params-title'>两个参数决定成败：尺寸基准与导出格式</h2>
        <div>
          <h3>「等宽 / 等高」里的基准怎么选</h3>
          <p>
            统一尺寸时，工具会按一个基准值缩放所有图片。选<strong>最大</strong>时，以这批图里最宽（纵向布局）或最高（横向布局）的那张为准，其余图被放大——画面整齐，但小图会变模糊，文件也更大。选<strong>最小</strong>时，以最窄或最矮的为准，其余图被缩小——文件最小，但大图会损失细节。
          </p>
          <p>
            两种都不合适时选<strong>自定义</strong>，直接填目标像素值。经验做法：如果图片最终要发到微信、小红书这类会被二次压缩的平台，按<strong>最小</strong>或填一个 1080 左右的值就够了，再高也只是在给平台省事；如果是存档或要看清文字截图，按<strong>最大</strong>更稳妥。
          </p>
          <p>
            选<strong>原始大小</strong>则不缩放，直接按每张图原尺寸拼接——横向拼接时高度可能参差不齐，纵向拼接时宽度可能不对齐。想要完全忠实于原图时用这个。
          </p>
          <h3>导出格式怎么选</h3>
          <p>
            <strong>PNG</strong> 无损、支持透明，适合文字截图、图标、需要透明的图。<strong>JPEG</strong> 有损但体积小，适合照片类内容，且不支持透明（透明区域会被填成背景色）。<strong>WebP</strong> 在同等画质下通常比 JPEG 更小，现代浏览器都支持，是发网页和 App 的优先选择。
          </p>
          <p>
            质量滑块只在导出 JPEG 或 WebP 时起作用，数值越高越接近原图、文件越大。一般 80–90 是画质与体积的平衡点；低于 70 时文字边缘和渐变区域容易出现明显色块。
          </p>
        </div>
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
