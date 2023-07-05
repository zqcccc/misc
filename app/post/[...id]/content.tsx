'use client'

import Image from 'next/image'
import { MDXRemote } from 'next-mdx-remote'
import Pre from './codeBlock'

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
  // code: ({ children, ...props }: any) =>
  //   (
  //     <code className='language-inline-code' {...props}>
  //       {children}
  //     </code>
  //   ),
}

const Content: React.FC<{ children: any }> = ({ children }) => {
  return <MDXRemote {...children} components={components} />
}

export default Content
