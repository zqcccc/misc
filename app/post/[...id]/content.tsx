import Image from 'next/image'
import { MDXRemote, MDXRemoteOptions } from 'next-mdx-remote-client/rsc'
import Pre from './codeBlock'
import rehypePrettyCode from 'rehype-pretty-code';
import remarkGfm from 'remark-gfm';
import React from 'react';

// NOTE: 不要用 <Suspense> 包 MDXRemote —— 否则 SSR 初次 HTML 只输出
// fallback（"Loading..."），正文要等客户端 hydrate 才填进去，Googlebot
// 抓到的就是空白 / Loading，直接导致 AdSense 判定「低价值内容」。
// MDXRemote 本身是 async server component，保留 await 语义就够了：SSR 会
// 在流式响应里 await 出正文并写到 HTML 里。

const ResponsiveImage: React.FC<any> = (props) => (
  <Image
    alt={props.alt}
    sizes='100vw'
    width={672}
    height={672}
    style={{ width: '100%', height: 'auto' }}
    {...props}
  />
)

const components = {
  img: ResponsiveImage,
  pre: Pre,
  code: ({ children, ...props }: any) => (
    <code className='language-inline-code' {...props}>
      {children}
    </code>
  ),
}

const Content = async ({ source }: { source: string }) => {
  const options: MDXRemoteOptions = {
    mdxOptions: {
      remarkPlugins: [remarkGfm],
      rehypePlugins: [
        // rehype-pretty-code@0.10.1 依赖 vfile@5，但 next-mdx-remote-client@2
        // 依赖 vfile@6，运行时无冲突、TS 类型互相不兼容。这里用 as unknown as any
        // 绕过联合类型不兼容，保留插件本身。升级时去掉。
        [
          rehypePrettyCode as unknown as any,
          {
            theme: 'one-dark-pro',
          },
        ],
      ] as unknown as any,
      format: 'mdx',
    },
    parseFrontmatter: true,
    // scope: {
    //   readingTime: calculateSomeHow(source),
    // },
    vfileDataIntoScope: "toc", // <---------
  };

  return <MDXRemote
      source={source}
      options={options}
      components={components}
      onError={() => <>error</>}
    />
}

export default Content
