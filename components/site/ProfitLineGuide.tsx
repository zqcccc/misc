import Link from 'next/link'

/**
 * 服务端渲染的「利润线与估值」说明。
 *
 * /pe 主页面是 'use client'，所有内容都要等客户端拉到 /api/profit-line
 * 才有，Googlebot 抓到的初始 HTML 几乎是空壳（实测约 1713 字符），属于
 * AdSense「低价值内容」的典型特征。这段说明放在 layout（server component）
 * 里静态输出，让搜索引擎能读到页面的真实用途与数据口径。
 */
const metrics = [
  {
    term: '利润线',
    detail:
      'TTM EPS × 你设定的倍数。TTM EPS 是最近四个季度每股收益的滚动合计，用它替代单一年度 EPS，能避免季节性和一次性损益造成的失真。',
  },
  {
    term: '偏离度',
    detail:
      '(股价 − 利润线) ÷ 利润线，用百分比表示股价相对利润线的位置。为正说明股价在利润线上方，为负说明已跌破。',
  },
  {
    term: 'TTM PE',
    detail:
      '股价 ÷ TTM EPS。页面还会给出当前 PE 在所选时间段内的历史分位数，用来判断估值处在自身历史的什么位置。',
  },
  {
    term: '利润线提醒',
    detail:
      '当股价低于利润线时标记为提醒状态。它只说明价格与利润的关系发生了变化，不表示应该买入或卖出。',
  },
]

export default function ProfitLineGuide() {
  return (
    <section className='trust-page' aria-labelledby='profit-line-guide-title'>
      <header>
        <h2 id='profit-line-guide-title'>利润线说明</h2>
      </header>

      <section>
        <h3>页面用途</h3>
        <p>
          页面把股价和利润放进同一条时间轴：股价是一条线，由利润推出来的「利润线」是另一条线，两条线的差距就是偏离度。
        </p>
        <p>
          股价的涨跌可以拆成两部分：利润的变化，和市场给的倍数的变化。前者是基本面，后者是情绪。
        </p>
      </section>

      <section>
        <h3>指标怎么算</h3>
        <dl>
          {metrics.map((item) => (
            <div key={item.term}>
              <dt>{item.term}</dt>
              <dd>{item.detail}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section>
        <h3>倍数该怎么设</h3>
        <p>
          利润线的倍数由你设定，代表你对这家公司「合理定价」的假设。常见的做法是先用公司自身历史 PE 的中位数做起点，再结合行业水平和利润增速调整。
        </p>
        <p>
          页面默认提供一条参考线，可以同时看两个倍数下的结果。多换几个倍数，看结论会不会翻转；只在很窄的倍数区间内才成立的结论不可靠。
        </p>
      </section>

      <section>
        <h3>数据边界</h3>
        <ul>
          <li>
            数据来源包括财报 EPS、市场行情和分红记录，不同市场的披露节奏和口径不一致，页面会标注当前标的的数据来源。
          </li>
          <li>
            TTM EPS 有滚动合计和数据源直接提供两种算法，结果可能有差异；跨市场标的还涉及汇率折算。
          </li>
          <li>
            财报有滞后，最近一期的利润可能尚未反映最新经营变化。
          </li>
          <li>
            跌破利润线不等于低估，远超利润线也不等于高估。
          </li>
        </ul>
      </section>

      <nav className='trust-page-links' aria-label='相关页面'>
        <Link href='/tools'>返回全部工具</Link>
      </nav>
    </section>
  )
}
