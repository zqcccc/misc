import Link from 'next/link'

export default function NotFound() {
  return (
    <main className='not-found-page'>
      <p>404</p>
      <h1>这个页面不再公开，或者从未存在。</h1>
      <div>
        <p>如果你是从旧链接来到这里，相关内容可能因为重复、过期、未完成或合规风险退出了公开站点。</p>
        <Link href='/'>回到 c9cu 首页</Link>
      </div>
    </main>
  )
}
