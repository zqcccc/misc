import dynamic from 'next/dynamic';

export const metadata = {
  title: '在线图片合并工具 | 支持多图拼接、顺序调整、格式与质量选择',
  description: '免费在线图片合并工具，支持多图上传、横向/纵向拼接、等宽/等高、顺序拖拽、导出PNG/JPEG/WebP格式及自定义图片质量，简单易用，安全高效。',
  keywords: '图片合并,在线拼图,图片拼接,图片工具,图片格式转换,图片压缩,图片质量,web工具,merge images,online tool',
  openGraph: {
    title: '在线图片合并工具',
    description: '支持多图上传、顺序调整、横向/纵向拼接、格式与质量选择，简单易用，安全高效。',
    url: 'https://onlylike.work/tools/merge-images',
    type: 'website',
    images: [
      {
        url: 'https://onlylike.work/public/merge-images-og.png',
        width: 1200,
        height: 630,
        alt: '在线图片合并工具',
      },
    ],
  },
};

function ToolIntro() {
  return (
    <div className="mb-8">
      <h1 className="text-3xl font-bold mb-2 text-gray-900 dark:text-gray-100">在线图片合并工具</h1>
      <p className="text-gray-600 dark:text-gray-300">
        免费在线图片拼接工具，支持多图上传、顺序拖拽调整、横向/纵向排列、等宽/等高、导出PNG/JPEG/WebP格式及自定义图片质量。
        <span className="font-semibold text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/30 px-1 rounded ml-1">无需下载，浏览器本地处理，安全高效。</span>
      </p>
    </div>
  );
}

const MergeImagesClient = dynamic(() => import('./MergeImagesClient'));

export default function Page() {
  return (
    <div className="max-w-2xl mx-auto my-10 p-8 rounded-xl shadow-lg bg-white dark:bg-[#282c35] transition-colors">
      <ToolIntro />
      <MergeImagesClient />
    </div>
  );
}
