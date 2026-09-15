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

      <section className='browser-tool-faq' aria-labelledby='compress-when-title'>
        <h2 id='compress-when-title'>什么时候该用它，什么时候不该</h2>
        <div>
          <h3>适合</h3>
          <p>
            网站或文章配图上传前压一压、把手机拍的一批照片压到能发邮件的体积、把一堆截图打包前先瘦身。也适合批量统一图片宽度——比如把一组宽度不一的配图全部限制到 1200px 以内。
          </p>
          <h3>不适合</h3>
          <p>
            已经压过一次的图再压收益很小，只会继续叠损失。要保留透明通道的图请注意：导出为 JPEG 会丢失透明，透明区域被填成背景色，请留在 PNG 或改用 WebP。另外它不做批量重命名、不做水印、不读取 RAW 格式。
          </p>
        </div>
      </section>

      <section className='browser-tool-faq' aria-labelledby='compress-params-title'>
        <h2 id='compress-params-title'>怎么压最有效：先缩尺寸，再降质量</h2>
        <div>
          <h3>为什么缩尺寸比降质量更管用</h3>
          <p>
            图片体积大致与像素数量的平方关系增长：宽度减半，像素数变成四分之一，体积往往也降到四分之一左右。而调低质量只是在已有的每个像素上丢弃细节，压到一定程度就会出现色块和噪点，画面先崩、体积却没小多少。所以<strong>先把尺寸压到实际需要的上限，再微调质量</strong>，通常能得到又小又干净的图。
          </p>
          <h3>两种尺寸模式的区别</h3>
          <p>
            <strong>按百分比缩放</strong>会对每张图等比缩小，适合一批尺寸相近的图统一瘦身。<strong>限制最大宽度</strong>只处理超过设定值的图，更窄的图保持原样——所以它<strong>不会把小图放大</strong>，适合尺寸参差不齐的一批图，也是配图场景的推荐做法。
          </p>
          <h3>质量滑块为什么有时是灰的</h3>
          <p>
            导出为 PNG 时质量选项不可用，因为 PNG 是无损格式，只按像素存储、不提供有损质量档位。想让 PNG 变小，请改用缩小尺寸，或导出为 WebP / JPEG。
          </p>
          <h3>格式怎么选</h3>
          <p>
            <strong>WebP</strong> 在同等观感下通常明显小于 JPEG，现代浏览器与主流 App 都支持，是网页配图的首选。<strong>JPEG</strong> 兼容性最好，适合照片，但不支持透明。<strong>PNG</strong> 无损并支持透明，只留给图标、文字截图和必须透明的图——照片存成 PNG 往往会大得离谱。
          </p>
          <p>
            质量一般从 80 起步：先看实际用途下够不够清晰，还嫌大就往 70 调，不建议低于 60。
          </p>
        </div>
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
