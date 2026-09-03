import type { Metadata } from 'next'
import Image from 'next/image'
import Link from 'next/link'

const CHROME_STORE_URL =
  'https://chromewebstore.google.com/detail/%E5%85%83%E7%B4%A0%E6%BB%9A%E5%8A%A8%E6%88%AA%E5%9B%BE-element-scroll-cap/pcncjnflpclidkccdkkeljcobkcomefa'

export const metadata: Metadata = {
  title: '元素滚动截图 · Element Scroll Capture (Chrome 扩展)',
  description:
    '选定页面中任意带滚动条的局部容器（后台表格、聊天记录、代码框），自动逐屏滚动并无缝拼接成高清长图。纯前端 Manifest V3 架构，图像仅在本地内存与 IndexedDB 处理，不上传服务器。',
  alternates: { canonical: '/tools/element-scroll-capture' },
  openGraph: {
    title: '元素滚动截图 · Element Scroll Capture',
    description:
      '选定任意内部滚动元素，自动逐屏滚动拼接为完整长图。纯本地处理，零数据收集。',
    url: '/tools/element-scroll-capture',
    type: 'website',
  },
}

const screenshots = [
  {
    src: '/images/element-scroll-capture/preview-1.png',
    title: '选定局部滚动容器',
    caption: '光标悬停自动高亮带有滚动条的元素（表格、代码框、聊天面板），点击即锁定目标。',
  },
  {
    src: '/images/element-scroll-capture/preview-2.png',
    title: '自定义参数面板',
    caption: '自由配置滚动等待间隔、重叠容错、输出格式（PNG/JPEG）及图片尺寸上限。',
  },
  {
    src: '/images/element-scroll-capture/preview-3.png',
    title: '自动步进与拼接',
    caption: '扩展平滑驱动容器向下滚动，实时显示捕获进度，随时可暂停或中止。',
  },
  {
    src: '/images/element-scroll-capture/preview-4.png',
    title: '本地历史管理',
    caption: '结果暂存于本地 IndexedDB，保留最近 5 张便于反复查看，用完即删。',
  },
  {
    src: '/images/element-scroll-capture/preview-5.png',
    title: '超长完整长图导出',
    caption: '支持新标签页大图全屏缩放检查，提供一键下载与快速复制到剪贴板。',
  },
]

const features = [
  {
    tag: '精准锁定',
    title: '内部容器级滚动截取',
    desc: '常规长截图工具只认 window/body；本扩展通过 DOM 树递归检索，无论嵌套多少层 div，只要存在 overflow 滚动条均可精准选中截取。',
  },
  {
    tag: '智能规避',
    title: '浮动元素防重复遮挡',
    desc: '针对现代 Web 应用常见的 fixed / sticky 吸顶表头或悬浮按钮，支持滚动时智能处理，杜绝拼接长图中反复出现横条或残影。',
  },
  {
    tag: '隐私承诺',
    title: '100% 本地处理，零网络请求',
    desc: '基于 Manifest V3 标准，无需常驻后台。仅在主动点击时获取 activeTab 视口，拼接运算全在本地 Canvas 完成，无任何后端与遥测数据。',
  },
  {
    tag: '灵活导出',
    title: '轻量高效，参数自由调节',
    desc: '扩展安装包仅 40KB，支持根据网速调节滚动等待时间以保证懒加载图片完全渲染，支持导出高保真 PNG 或紧凑 JPEG。',
  },
]

export default function ElementScrollCapturePage() {
  return (
    <main className='browser-tool-page'>
      <header>
        <div className='flex items-center gap-4 mb-4'>
          <Image
            src='/images/element-scroll-capture/icon.png'
            alt='元素滚动截图产品徽标'
            width={64}
            height={64}
            className='rounded-xl border border-[var(--site-line)] bg-white p-1 shadow-sm'
            priority
          />
          <div>
            <div className='flex flex-wrap items-center gap-2'>
              <span className='tools-index-kind'>Chrome 扩展 · MV3</span>
              <span className='text-xs px-2 py-0.5 rounded bg-[color-mix(in_srgb,var(--site-signal)_14%,transparent)] text-[var(--site-signal)] font-mono font-bold'>
                v0.2.0
              </span>
              <span className='text-xs text-[var(--site-muted)]'>本地纯算 · 40KB</span>
            </div>
            <p className='text-xs text-[var(--site-muted)] mt-1'>适用于 Chrome、Edge、Brave、Arc 等 Chromium 浏览器</p>
          </div>
        </div>

        <h1>元素滚动截图</h1>
        <p className='text-lg font-mono text-[var(--site-muted)] !mt-1 !mb-4'>
          Element Scroll Capture
        </p>

        <p>
          选定页面中任意带滚动条的内部元素，自动逐屏滚动并拼接成一张完整长图。专门解决常规长截图截不全后台数据表格、聊天记录、侧边栏抽屉与代码框的痛点。
        </p>

        <div className='mt-6 flex flex-wrap items-center gap-4'>
          <a
            href={CHROME_STORE_URL}
            target='_blank'
            rel='noopener noreferrer'
            className='inline-flex items-center justify-center gap-2 rounded-lg bg-[var(--site-link)] px-5 py-3 text-sm font-bold text-white shadow-sm transition hover:opacity-90'
          >
            <svg
              className='h-4 w-4 fill-current'
              viewBox='0 0 24 24'
              aria-hidden='true'
            >
              <path d='M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.4z' />
            </svg>
            前往 Chrome 应用商店安装
            <span aria-hidden='true'>↗</span>
          </a>

          <Link
            href='/privacy/element-scroll-capture'
            className='inline-flex items-center justify-center rounded-lg border border-[var(--site-line)] bg-[var(--site-panel)] px-4 py-3 text-sm font-semibold text-[var(--site-ink)] transition hover:border-[var(--site-link)] hover:text-[var(--site-link)]'
          >
            查看隐私政策
          </Link>
        </div>

        <strong>
          本扩展不发起任何网络请求，没有远程脚本与后端服务器，截图与偏好配置仅在本地设备处理。
        </strong>
      </header>

      {/* 工作区：痛点剖析、核心特性与实机图集 */}
      <section className='browser-tool-workspace' aria-label='功能详解与截图预览'>
        {/* 痛点对比 */}
        <div className='mb-10 rounded-xl border border-[var(--site-line)] bg-[color-mix(in_srgb,var(--site-panel)_70%,var(--site-paper))] p-6'>
          <h2 className='text-lg font-bold text-[var(--site-ink)] mb-3'>
            为什么常规长截图总是截不全？
          </h2>
          <div className='grid gap-6 md:grid-cols-2 text-sm leading-relaxed text-[var(--site-muted)]'>
            <div className='rounded-lg border border-[var(--site-line)] bg-[var(--site-panel)] p-4'>
              <div className='font-bold text-[var(--site-signal)] mb-2 flex items-center gap-1.5'>
                <span>✕</span> 常规截图工具的痛点
              </div>
              <ul className='space-y-1.5 list-disc list-inside'>
                <li>只针对整个 <code>window</code> 或全局页面滚屏。</li>
                <li>遇到后台表格、聊天弹窗等局部滚动区域，只能截到当前显示的第一屏。</li>
                <li>自动滚动容易导致吸顶导航、悬浮工具栏在拼接图中反复出现并遮挡内容。</li>
              </ul>
            </div>
            <div className='rounded-lg border border-[color-mix(in_srgb,var(--site-link)_40%,var(--site-line))] bg-[var(--site-panel)] p-4'>
              <div className='font-bold text-[var(--site-link)] mb-2 flex items-center gap-1.5'>
                <span>✓</span> 元素滚动截图的解法
              </div>
              <ul className='space-y-1.5 list-disc list-inside'>
                <li>光标直接锁定需要截取的特定容器，不受页面其他区域干扰。</li>
                <li>程序驱动该容器自身精准向下滚动，逐屏捕获并自动无损拼合。</li>
                <li>智能识别 fixed 与 sticky 元素，消除长图重叠残影。</li>
              </ul>
            </div>
          </div>
        </div>

        {/* 核心特性网格 */}
        <div className='mb-12'>
          <h2 className='text-xl font-bold text-[var(--site-ink)] mb-6'>
            核心特性
          </h2>
          <div className='grid gap-5 sm:grid-cols-2'>
            {features.map((item) => (
              <div
                key={item.title}
                className='rounded-xl border border-[var(--site-line)] bg-[var(--site-panel)] p-5 flex flex-col justify-between'
              >
                <div>
                  <span className='inline-block text-[11px] font-mono font-bold tracking-wider uppercase text-[var(--site-link)] mb-2'>
                    {item.tag}
                  </span>
                  <h3 className='text-base font-bold text-[var(--site-ink)] mb-2'>
                    {item.title}
                  </h3>
                  <p className='text-sm leading-relaxed text-[var(--site-muted)]'>
                    {item.desc}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* 界面截图画廊 */}
        <div>
          <div className='flex items-baseline justify-between mb-6'>
            <h2 className='text-xl font-bold text-[var(--site-ink)]'>
              运行界面实测
            </h2>
            <span className='text-xs text-[var(--site-muted)]'>
              真实扩展运行捕获（5 阶段流程）
            </span>
          </div>

          <div className='grid gap-6 sm:grid-cols-2 lg:grid-cols-3'>
            {screenshots.map((shot, idx) => (
              <figure
                key={shot.title}
                className={`flex flex-col rounded-xl border border-[var(--site-line)] bg-[var(--site-panel)] overflow-hidden ${
                  idx === 4 ? 'sm:col-span-2 lg:col-span-1' : ''
                }`}
              >
                <div className='relative aspect-[440/280] w-full bg-slate-900/5 dark:bg-slate-100/5 flex items-center justify-center p-2'>
                  <Image
                    src={shot.src}
                    alt={shot.title}
                    width={440}
                    height={280}
                    className='rounded-lg object-contain w-full h-full shadow-sm'
                  />
                </div>
                <figcaption className='p-4 border-t border-[var(--site-line)] flex-1 flex flex-col justify-between'>
                  <div>
                    <h3 className='text-sm font-bold text-[var(--site-ink)] mb-1'>
                      {idx + 1}. {shot.title}
                    </h3>
                    <p className='text-xs text-[var(--site-muted)] leading-relaxed'>
                      {shot.caption}
                    </p>
                  </div>
                </figcaption>
              </figure>
            ))}
          </div>
        </div>
      </section>

      {/* 使用指南 */}
      <section className='browser-tool-guide' aria-labelledby='extension-guide-title'>
        <h2 id='extension-guide-title'>如何使用</h2>
        <ol>
          <li>
            <strong>1. 安装与固定</strong>
            <span>
              在{' '}
              <a
                href={CHROME_STORE_URL}
                target='_blank'
                rel='noopener noreferrer'
                className='text-[var(--site-link)] underline'
              >
                Chrome 应用商店
              </a>{' '}
              点击“添加至 Chrome”，建议在浏览器右上角将扩展图标固定在工具栏。
            </span>
          </li>
          <li>
            <strong>2. 选定目标容器</strong>
            <span>
              在任意包含滚动内容的页面点击扩展图标，鼠标移动到包含滚动条的目标元素（例如表格、代码框或聊天流），页面会出现高亮提示框，单击完成选定。
            </span>
          </li>
          <li>
            <strong>3. 自动步进滚动</strong>
            <span>
              扩展将自动接管该容器并匀速逐屏向下滚动截图。若页面包含懒加载，可在设置中适当增加滚动等待时间以保障完全加载。
            </span>
          </li>
          <li>
            <strong>4. 预览与一键导出</strong>
            <span>
              捕获完成后自动打开结果页，支持全尺寸长图清晰度核对，可一键下载为 PNG 或 JPEG，或直接复制图片到系统剪贴板。
            </span>
          </li>
        </ol>
      </section>

      {/* 边界与常见问题 */}
      <section className='browser-tool-faq' aria-labelledby='extension-faq-title'>
        <h2 id='extension-faq-title'>设计与隐私边界</h2>
        <div>
          <h3>为什么不设计成全自动整页推断？</h3>
          <p>
            复杂的前端后台、文档系统（如 Notion、飞书、微信读书、各云平台控制台）往往由多层嵌套的 <code>flex</code> 或 <code>grid</code> 布局构成，存在多个平行的滚动区域。由用户主动点击指定目标容器，能够确保截取结果 100% 符合预期，杜绝误判。
          </p>

          <h3>扩展申请了哪些权限？会不会泄露网页隐私？</h3>
          <p>
            扩展仅申请了 <code>activeTab</code>、<code>scripting</code>、<code>storage</code> 和 <code>downloads</code> 四项最小权限。扩展没有常驻脚本，只有在你主动点击扩展时才对当前标签页生效；所有画面在内存 Canvas 中拼接，绝不向任何远程服务器回传数据。详情可参阅
            <Link href='/privacy/element-scroll-capture' className='text-[var(--site-link)] underline ml-1'>
              隐私政策声明
            </Link>。
          </p>

          <h3>生成的长图存储在哪里？</h3>
          <p>
            拼接好的图片仅保存在浏览器本地的 IndexedDB 中，用于在结果页面预览和再次下载。最多仅保留最近 5 张记录，超出后自动循环覆盖，不会长期占用磁盘空间。
          </p>

          <h3>支持哪些浏览器？</h3>
          <p>
            所有基于 Chromium 内核的现代浏览器均可完美安装和使用，包括 Google Chrome、Microsoft Edge、Brave、Arc、Vivaldi 以及各类国内双核浏览器。
          </p>
        </div>
      </section>

      {/* 底部导航 */}
      <nav className='browser-tool-related' aria-label='相关链接'>
        <a
          href={CHROME_STORE_URL}
          target='_blank'
          rel='noopener noreferrer'
          className='inline-flex items-center gap-1 font-bold text-[var(--site-link)]'
        >
          在 Chrome 应用商店安装 ↗
        </a>
        <Link href='/privacy/element-scroll-capture'>隐私政策</Link>
        <Link href='/tools/merge-images'>图片合并工具</Link>
        <Link href='/tools/compress-images'>图片压缩工具</Link>
        <Link href='/tools'>返回全部工具</Link>
      </nav>
    </main>
  )
}
