/**
 * 元素滚动截图（Element Scroll Capture）Chrome 扩展隐私政策
 * 纯静态服务端组件：不引入任何客户端 JS、外部字体、图片或统计脚本。
 */

const EFFECTIVE_DATE = '2026-08-23'
const EXTENSION_NAME_ZH = '元素滚动截图'
const EXTENSION_NAME_EN = 'Element Scroll Capture'
const CONTACT_EMAIL = 'c9cu@qq.com'
const EN_ANCHOR_ID = 'english'
const ZH_ANCHOR_ID = 'chinese'

type Section = {
  title: string
  paragraphs?: string[]
  bullets?: string[]
  terms?: { term: string; desc: string }[]
}

const SECTIONS_ZH: Section[] = [
  {
    title: '一、本扩展是什么',
    paragraphs: [
      `${EXTENSION_NAME_ZH}（${EXTENSION_NAME_EN}）是一款 Chrome 扩展（Manifest V3）。它让你选定当前网页中的某个可滚动区域（或整个页面），自动逐屏滚动，并把每一屏拼接成一张完整的长截图，供你保存到本地。`,
      '它主要用于解决常规整页截图拍不全内部滚动容器的问题，例如聊天记录区、后台表格主体、侧边栏、代码框。',
    ],
  },
  {
    title: '二、数据收集',
    bullets: [
      '本扩展不收集、不上传、不存储任何个人信息。',
      '本扩展不发起任何网络请求，没有后端服务器，开发者没有任何可以接收数据的通道。',
      '本扩展不包含任何分析、统计、追踪或广告 SDK。',
      '本扩展不使用远程代码，所有脚本均打包在扩展内。',
    ],
  },
  {
    title: '三、本地存储',
    paragraphs: ['本扩展在你的设备上只存储以下两项内容，除此之外没有其他存储：'],
    terms: [
      {
        term: '1. 截图图像',
        desc: '拼接完成的图片存放在浏览器本地的 IndexedDB 中，仅供结果页预览和保存使用，只保留最近 5 张，超出后自动删除。图片不会离开你的设备。',
      },
      {
        term: '2. 偏好设置',
        desc: '通过 chrome.storage.sync 保存你自己的设置项：每格截图间隔、滚动后等待时间、输出格式（PNG/JPEG）、图片尺寸上限、是否隐藏悬浮元素、是否自动下载。这些设置会通过 Chrome 自带的账号同步机制在你自己的设备之间同步，该过程由 Chrome 和你自己的 Google 账号完成，开发者无法访问。',
      },
    ],
  },
  {
    title: '四、网页内容的处理',
    bullets: [
      '本扩展会读取你主动选定的那个页面区域的画面，用于生成截图。这个过程完全在你本地的浏览器内完成，画面数据不会被发送到任何地方。',
      '本扩展只在你主动点击扩展图标或按下快捷键之后，才对当前这一个标签页生效；它不会在后台运行，也不会在你未主动触发时读取任何页面。',
    ],
  },
  {
    title: '五、权限说明',
    paragraphs: ['本扩展申请的每一项权限及其用途如下：'],
    terms: [
      {
        term: 'activeTab',
        desc: '获取当前标签页可视区域的画面，这是截图的唯一图像来源。仅在你主动触发后对当前标签页生效，标签页导航后失效。',
      },
      {
        term: 'scripting',
        desc: '把扩展自带的本地脚本注入当前标签页，用于探测可滚动元素、控制滚动、测量元素几何位置。本扩展刻意没有声明常驻 content_scripts，就是为了避免在你不使用时在所有网页上运行。',
      },
      {
        term: 'storage',
        desc: '仅用于保存上述偏好设置。',
      },
      {
        term: 'downloads',
        desc: '把你生成的截图保存到本地下载文件夹，仅用于你本次主动生成的文件，不读取也不修改任何已有下载记录。',
      },
    ],
  },
  {
    title: '六、数据共享',
    paragraphs: [
      '本扩展不向任何第三方出售、转让或披露任何数据——因为根本不存在被收集的数据。',
    ],
  },
  {
    title: '七、与 Chrome 应用商店声明一致的承诺',
    bullets: [
      '不收集任何用户数据。',
      '不使用远程代码。',
      '不出售或转让数据给第三方。',
      '不将数据用于与本扩展单一用途无关的目的。',
      '不将数据用于判定信用度或用于贷款审批。',
    ],
  },
  {
    title: '八、儿童隐私',
    paragraphs: [
      '本扩展不面向 13 岁以下儿童，也不收集任何与年龄相关的信息。',
    ],
  },
  {
    title: '九、政策变更',
    paragraphs: ['如本政策有变更，我们会更新本页内容并修改页面顶部的生效日期。'],
  },
  {
    title: '十、联系方式',
    paragraphs: [`如对本隐私政策有任何疑问，请联系：${CONTACT_EMAIL}`],
  },
]

const SECTIONS_EN: Section[] = [
  {
    title: '1. What this extension is',
    paragraphs: [
      `${EXTENSION_NAME_EN} (${EXTENSION_NAME_ZH}) is a Chrome extension (Manifest V3). It lets you pick a scrollable area of the current web page (or the whole page), scrolls through it screen by screen automatically, and stitches every screen into one complete long screenshot that you can save to your device.`,
      'Its main purpose is to capture inner scrollable containers that ordinary full-page screenshots cannot capture completely, such as chat history panes, admin table bodies, sidebars, and code boxes.',
    ],
  },
  {
    title: '2. Data collection',
    bullets: [
      'This extension does not collect, upload, or store any personal information.',
      'This extension makes no network requests. There is no backend server, and the developer has no channel through which any data could be received.',
      'This extension contains no analytics, statistics, tracking, or advertising SDKs.',
      'This extension uses no remote code. All scripts are bundled inside the extension package.',
    ],
  },
  {
    title: '3. Local storage',
    paragraphs: [
      'This extension stores only the following two things on your device, and nothing else:',
    ],
    terms: [
      {
        term: '1. Screenshot images',
        desc: 'The stitched image is stored in the browser’s local IndexedDB, used only for previewing and saving on the result page. Only the 5 most recent images are kept; older ones are deleted automatically. Images never leave your device.',
      },
      {
        term: '2. Preference settings',
        desc: 'Your own settings are saved via chrome.storage.sync: the interval between each captured frame, the wait time after each scroll, the output format (PNG/JPEG), the maximum image size, whether to hide floating elements, and whether to download automatically. These settings are synced between your own devices through Chrome’s built-in account sync. That process is carried out by Chrome and your own Google account; the developer cannot access it.',
      },
    ],
  },
  {
    title: '4. Handling of web page content',
    bullets: [
      'This extension reads the visual content of the page area you actively select, in order to generate the screenshot. This happens entirely inside your local browser, and the image data is not sent anywhere.',
      'This extension takes effect only on the current tab, and only after you actively click the extension icon or press the keyboard shortcut. It does not run in the background, and it does not read any page unless you actively trigger it.',
    ],
  },
  {
    title: '5. Permissions',
    paragraphs: ['Every permission requested by this extension, and why it is needed:'],
    terms: [
      {
        term: 'activeTab',
        desc: 'Captures the visible area of the current tab, which is the only image source for the screenshot. It applies to the current tab only after you actively trigger the extension, and expires once the tab navigates.',
      },
      {
        term: 'scripting',
        desc: 'Injects the extension’s own bundled local scripts into the current tab to detect scrollable elements, control scrolling, and measure element geometry. This extension deliberately declares no persistent content_scripts, precisely so that it does not run on every web page when you are not using it.',
      },
      {
        term: 'storage',
        desc: 'Used only to save the preference settings described above.',
      },
      {
        term: 'downloads',
        desc: 'Saves the screenshot you generated to your local downloads folder. It is used only for the file you actively generated in that session, and it neither reads nor modifies any existing download records.',
      },
    ],
  },
  {
    title: '6. Data sharing',
    paragraphs: [
      'This extension does not sell, transfer, or disclose any data to any third party — because no data is collected in the first place.',
    ],
  },
  {
    title: '7. Consistency with the Chrome Web Store declarations',
    bullets: [
      'No user data is collected.',
      'No remote code is used.',
      'Data is not sold or transferred to third parties.',
      'Data is not used for purposes unrelated to the extension’s single purpose.',
      'Data is not used to determine creditworthiness or for lending purposes.',
    ],
  },
  {
    title: '8. Children’s privacy',
    paragraphs: [
      'This extension is not directed at children under 13, and it collects no age-related information.',
    ],
  },
  {
    title: '9. Changes to this policy',
    paragraphs: [
      'If this policy changes, we will update this page and revise the effective date shown at the top.',
    ],
  },
  {
    title: '10. Contact',
    paragraphs: [
      `If you have any questions about this privacy policy, please contact: ${CONTACT_EMAIL}`,
    ],
  },
]

export const metadata = {
  title: '元素滚动截图（Element Scroll Capture）隐私政策 | Privacy Policy',
  description:
    '元素滚动截图（Element Scroll Capture）Chrome 扩展隐私政策：不收集任何个人信息、不发起网络请求、不使用远程代码，截图与设置仅保存在本地。Privacy policy for the Element Scroll Capture Chrome extension.',
}

function SectionList({ sections }: { sections: Section[] }) {
  return (
    <>
      {sections.map(section => (
        <section key={section.title} className='mt-10'>
          <h2 className='text-xl font-semibold text-gray-900 dark:text-gray-100'>
            {section.title}
          </h2>
          {section.paragraphs?.map(text => (
            <p
              key={text}
              className='mt-3 leading-7 text-gray-700 dark:text-gray-300'
            >
              {text}
            </p>
          ))}
          {section.bullets && (
            <ul className='mt-3 list-disc space-y-2 pl-5 leading-7 text-gray-700 dark:text-gray-300'>
              {section.bullets.map(text => (
                <li key={text}>{text}</li>
              ))}
            </ul>
          )}
          {section.terms && (
            <dl className='mt-3 space-y-4'>
              {section.terms.map(item => (
                <div
                  key={item.term}
                  className='rounded-lg border border-gray-200 bg-gray-50 p-4 dark:border-gray-700 dark:bg-[#363c48]'
                >
                  <dt className='font-semibold text-gray-900 dark:text-gray-100'>
                    {item.term}
                  </dt>
                  <dd className='mt-1 leading-7 text-gray-700 dark:text-gray-300'>
                    {item.desc}
                  </dd>
                </div>
              ))}
            </dl>
          )}
        </section>
      ))}
    </>
  )
}

export default function ElementScrollCapturePrivacyPage() {
  return (
    <main className='mx-auto my-10 max-w-3xl px-6 pb-16'>
      <article id={ZH_ANCHOR_ID}>
        <header className='border-b border-gray-200 pb-6 dark:border-gray-700'>
          <h1 className='text-3xl font-bold text-gray-900 dark:text-gray-100'>
            {EXTENSION_NAME_ZH}（{EXTENSION_NAME_EN}）隐私政策
          </h1>
          <p className='mt-3 text-sm text-gray-600 dark:text-gray-400'>
            生效日期：{EFFECTIVE_DATE}
          </p>
          <p className='mt-1 text-sm text-gray-600 dark:text-gray-400'>
            本页为 Chrome 扩展「{EXTENSION_NAME_ZH}」的隐私政策。
            <a
              href={`#${EN_ANCHOR_ID}`}
              className='ml-1 underline underline-offset-2 hover:text-gray-900 dark:hover:text-gray-100'
            >
              English version below
            </a>
          </p>
        </header>
        <SectionList sections={SECTIONS_ZH} />
      </article>

      <hr className='mt-16 border-gray-200 dark:border-gray-700' />

      <article id={EN_ANCHOR_ID} className='mt-16'>
        <header className='border-b border-gray-200 pb-6 dark:border-gray-700'>
          <h1 className='text-3xl font-bold text-gray-900 dark:text-gray-100'>
            Privacy Policy for {EXTENSION_NAME_EN} ({EXTENSION_NAME_ZH})
          </h1>
          <p className='mt-3 text-sm text-gray-600 dark:text-gray-400'>
            Effective date: {EFFECTIVE_DATE}
          </p>
          <p className='mt-1 text-sm text-gray-600 dark:text-gray-400'>
            This is the privacy policy of the Chrome extension
            {` “${EXTENSION_NAME_EN}”`}. It is an equivalent translation
            of the Chinese version above.
          </p>
        </header>
        <SectionList sections={SECTIONS_EN} />
      </article>
    </main>
  )
}
