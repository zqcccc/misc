import Link from 'next/link'

/**
 * 服务端渲染的「A 股策略信号与回测」说明。
 *
 * /ashare-strategy 主页面是 'use client'，全部内容等客户端拉 /api/ashare-strategy
 * 才出现，Googlebot 抓到的初始 HTML 只有约 996 字符，是站内最薄的页面，
 * 属于 AdSense「低价值内容」的典型特征。这段说明放在 layout（server
 * component）里静态输出，让搜索引擎能读到页面的真实用途与方法口径。
 */
export default function AShareStrategyGuide() {
  return (
    <section className='trust-page' aria-labelledby='ashare-guide-title'>
      <header>
        <h2 id='ashare-guide-title'>这个看板展示什么</h2>
      </header>

      <section>
        <h3>页面用途</h3>
        <p>
          这是一个 A 股核心赛道龙头相对强弱 Alpha 策略的信号看板。策略的持仓高度集中，通常只保留两到三只核心赛道龙头，其余以现金持有；当大盘判断为弱势时，直接空仓避险。
        </p>
        <p>
          页面每天盘后更新一次，展示三件事：今天策略给出的风险状态与目标持仓、历史调仓记录，以及全样本与样本外的回测结果。它记录的是一套固定规则跑出来的结果，不是我对明天涨跌的判断。
        </p>
      </section>

      <section>
        <h3>策略规则</h3>
        <ul>
          <li>
            <strong>选股范围。</strong>覆盖十余个核心赛道，每个赛道取龙头标的，不参与小市值博弈和题材炒作。
          </li>
          <li>
            <strong>相对强弱排序。</strong>在候选龙头里按相对强弱挑选排名最靠前的两到三只，谁强就持有谁。
          </li>
          <li>
            <strong>宏观避险过滤。</strong>当宽基指数跌破关键均线且均线下行时，判定为弱势防守期，清仓转现金，不做逆势加仓。
          </li>
          <li>
            <strong>低频调仓。</strong>月度级别的换手控制，避免高频轮动被交易成本和滑点吃掉收益。
          </li>
        </ul>
      </section>

      <section>
        <h3>回测口径</h3>
        <p>
          回测采用真实 T+1 撮合，并按历史真实摩擦计成本。为了检验收益是否只是承担了大盘 Beta，页面还参考 EP004 评测规范做了几项检验：用 CAPM 逐日回归剥离大盘影响、用除水夏普检验排除多重检验带来的运气成分、用蒙特卡洛波块重采样评估结果稳定性。
        </p>
        <p>
          页面会同时给出全样本与样本外两段结果。<strong>样本外才是值得看的</strong>——全样本表现好只能说明规则拟合了历史，样本外仍能成立才有参考价值。
        </p>
      </section>

      <section>
        <h3>怎么读这些数字</h3>
        <dl>
          <div>
            <dt>风险状态</dt>
            <dd>当前是否触发宏观避险过滤。触发时现金比例接近 100%，这是规则的一部分，不是故障。</dd>
          </div>
          <div>
            <dt>现金比例</dt>
            <dd>目标持仓中现金的占比。持仓集中意味着单只标的大幅波动会明显影响整体结果。</dd>
          </div>
          <div>
            <dt>策略收益 / 基准</dt>
            <dd>策略与沪深 300 等基准的同期对照。跑赢基准的幅度才是策略真正贡献的部分。</dd>
          </div>
          <div>
            <dt>最大回撤 (MDD)</dt>
            <dd>历史上从高点到低点的最大跌幅。看收益必须同时看这个数字，否则无法判断风险。</dd>
          </div>
          <div>
            <dt>盈亏比</dt>
            <dd>平均盈利与平均亏损之比。高胜率但盈亏比很低的策略，一次大亏就可能抹掉多次小赚。</dd>
          </div>
        </dl>
      </section>

      <section>
        <h3>局限与声明</h3>
        <ul>
          <li>回测基于历史数据，不能保证未来结果；样本外区间有限，结论可能随市场变化失效。</li>
          <li>持仓集中度高，单只标的的黑天鹅事件会显著影响组合，实际执行还可能遇到涨跌停、停牌与流动性限制。</li>
          <li>实盘存在回测未完全覆盖的成本，包括冲击成本、资金占用与税费。</li>
          <li>这里是个人研究记录，不构成投资建议、证券推荐或收益承诺。</li>
        </ul>
      </section>

      <nav className='trust-page-links' aria-label='相关页面'>
        <Link href='/post/ashare-leader-momentum-strategy'>策略完整推导与检验过程</Link>
        <Link href='/standards#financial'>金融研究完整声明</Link>
      </nav>
    </section>
  )
}
