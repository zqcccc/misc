import BlogLayout from './blogLayout'

export default BlogLayout

export const metadata = {
  title: {
    template: "%s | ZQC's Blog",
    default: "ZQC's Blog", // a default is required when creating a template
  },
  description: "welcome to ZQC's personal blog, nice to meet you",
  keywords: ['Next.js', 'React', 'JavaScript', 'blog', 'zqc', 'onlylike.work'],
}

export const viewport = {
  colorScheme: 'light dark',
}
