import Image from 'next/image'
import { MDXRemote, MDXRemoteOptions } from 'next-mdx-remote-client/rsc'
import Pre from './codeBlock'
import { Suspense } from "react";
import rehypePrettyCode from 'rehype-pretty-code';
import remarkGfm from 'remark-gfm';
import React from 'react';

const ResponsiveImage: React.FC<any> = (props) => (
  <Image
    alt={props.alt}
    sizes='100vw'
    width='672'
    height='672'
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
        [
          rehypePrettyCode,
          {
            theme: 'one-dark-pro',
          },
        ],
      ],
      format: 'mdx',
    },
    parseFrontmatter: true,
    // scope: {
    //   readingTime: calculateSomeHow(source),
    // },
    vfileDataIntoScope: "toc", // <---------
  };

  return <Suspense fallback={<>Loading...</>}>
    {/* @ts-expect-error Server Component */}
    <MDXRemote
      source={source}
      options={options}
      components={components}
      onError={() => <>error</>}
    />
  </Suspense>
}

export default Content
