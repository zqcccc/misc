export const metadata = {
  title: '在线工具集合 | 图片合并、格式转换等免费工具',
  description: '收录多种实用的在线工具，如图片合并、格式转换等，全部免费、无需下载，浏览器本地处理，安全高效。',
  keywords: '在线工具,图片合并,格式转换,web工具,免费工具,merge images,tools',
};

const tools = [
  {
    name: '图片合并工具',
    desc: '支持多图上传、顺序调整、横/纵向拼接、格式与质量选择。',
    href: '/tools/merge-images',
    icon: '🖼️',
  },
  // 以后可继续添加更多工具
];

export default function ToolsHome() {
  return (
    <div className="max-w-2xl mx-auto my-10 p-8 rounded-xl shadow-lg bg-white dark:bg-[#282c35] transition-colors">
      <h1 className="text-3xl font-bold mb-6 text-gray-900 dark:text-gray-100">在线工具集合</h1>
      <p className="text-gray-600 dark:text-gray-300 mb-8">收录多种实用的在线工具，全部免费、无需下载，浏览器本地处理，安全高效。</p>
      <div className="grid gap-6">
        {tools.map(tool => (
          <a
            key={tool.href}
            href={tool.href}
            className="flex items-center gap-4 p-5 rounded-lg border border-gray-300 dark:border-gray-700 bg-gray-50 hover:bg-blue-50 dark:bg-[#363c48] dark:hover:bg-[#444b5a] hover:shadow transition"
          >
            <span className="text-3xl">{tool.icon}</span>
            <div>
              <div className="font-semibold text-lg text-gray-900 dark:text-gray-100">{tool.name}</div>
              <div className="text-gray-600 dark:text-gray-400 text-sm">{tool.desc}</div>
            </div>
          </a>
        ))}
      </div>
    </div>
  );
} 