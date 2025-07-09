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
    <div className="max-w-2xl mx-auto my-10 p-8 bg-white rounded-xl shadow-lg">
      <h1 className="text-3xl font-bold mb-6">在线工具集合</h1>
      <p className="text-gray-600 mb-8">收录多种实用的在线工具，全部免费、无需下载，浏览器本地处理，安全高效。</p>
      <div className="grid gap-6">
        {tools.map(tool => (
          <a
            key={tool.href}
            href={tool.href}
            className="flex items-center gap-4 p-5 bg-gray-50 rounded-lg border border-gray-200 hover:shadow transition"
          >
            <span className="text-3xl">{tool.icon}</span>
            <div>
              <div className="font-semibold text-lg">{tool.name}</div>
              <div className="text-gray-500 text-sm">{tool.desc}</div>
            </div>
          </a>
        ))}
      </div>
    </div>
  );
} 