import Link from 'next/link'

export default function FinancialNotice({
  title = '研究与数据说明',
}: {
  title?: string
}) {
  return (
    <aside className='financial-notice' aria-label={title}>
      <div>
        <strong>{title}</strong>
        <p>
          页面用于记录 c9cu 的个人研究过程，不构成投资建议、证券推荐或收益承诺。数据可能延迟、缺失或存在供应商差异；历史表现与回测不能保证未来结果。
        </p>
      </div>
      <Link href='/standards#financial'>方法与完整披露</Link>
    </aside>
  )
}
