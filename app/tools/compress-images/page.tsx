import dynamic from 'next/dynamic';

export const metadata = {
  title: '在线图片压缩工具 | JPG/PNG/WEBP 压缩、尺寸缩放，本地处理',
  description:
    '免费在线图片压缩工具，支持 JPG/PNG/WEBP 格式转换、按百分比或最大宽度缩放尺寸、自定义质量。支持拖拽、点击、粘贴上传，多图批量压缩并打包 ZIP 下载，浏览器本地处理，安全高效。',
  keywords:
    '图片压缩,在线压缩,图片缩放,JPG压缩,PNG压缩,WEBP,图片工具,批量压缩,拖拽上传,web工具,image compress,tinyimg',
  openGraph: {
    title: '在线图片压缩工具',
    description: 'JPG/PNG/WEBP 压缩与尺寸缩放，拖拽粘贴上传，多图打包下载，浏览器本地处理。',
    url: 'https://onlylike.work/tools/compress-images',
    type: 'website',
  },
};

function ToolIntro() {
  return (
    <div className="mb-6">
      <h1 className="text-3xl font-bold mb-2 text-gray-900 dark:text-gray-100">在线图片压缩工具</h1>
      <p className="text-gray-600 dark:text-gray-300">
        支持 JPG / PNG / WEBP 格式转换、按百分比或最大宽度缩放尺寸、自定义图像质量。可拖拽、点击或粘贴上传，多图批量压缩并打包 ZIP 下载。
        <span className="font-semibold text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/30 px-1 rounded ml-1">
          全程浏览器本地处理，图片不上传服务器。
        </span>
      </p>
    </div>
  );
}

const CompressImagesClient = dynamic(() => import('./CompressImagesClient'));

export default function Page() {
  return (
    <div className="max-w-2xl mx-auto my-10 p-6 sm:p-8 rounded-2xl shadow-lg bg-white dark:bg-[#282c35] transition-colors">
      <ToolIntro />
      <CompressImagesClient />
    </div>
  );
}
