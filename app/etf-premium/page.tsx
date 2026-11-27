import PremiumWorkspace from './premium-workspace'

/**
 * 服务端输出的方法与口径说明：搜索引擎和不执行 JS 的访客读到的是完整正文，
 * 交互表格（客户端组件）只承担数据部分。
 */
export default function EtfPremiumPage() {
  return (
    <main>
      <header className='etf-premium-head'>
        <h1>跨境 ETF 溢价监控</h1>
        <p>
          同一份海外指数敞口，场内可能有 QDII 与港股通两种载体，价格相对 IOPV
          实时估值的偏离就是溢价。本页用统一公式计算全部标的的溢价率、按核对过的跟踪指数分组，并标出同组里溢价更低的载体；溢价高不等于看空海外指数，更多时候反映的是申购额度与通道差异。
        </p>
      </header>
      <PremiumWorkspace />

      <section className='etf-premium-section' aria-labelledby='etf-data-source'>
        <h2 id='etf-data-source'>数据来源与刷新</h2>
        <ul>
          <li>
            <strong>名单与基金类型：</strong>
            天天基金「场内交易基金」页（cnjy_dwjz.html）的全量列表，「类型」列标注
            指数型-海外股票 的按 QDII 处理；名单外的场内基金不纳入。
          </li>
          <li>
            <strong>行情与 IOPV：</strong>
            优先东方财富行情接口（与 AKShare fund_etf_spot_em 同源）；东财行情不可用时改用腾讯公开行情接口，两边的
            IOPV 与单位净值字段已交叉核对一致，页面会标注当前实际来源。
          </li>
          <li>
            <strong>历史净值与申赎状态：</strong>
            天天基金历史净值接口（api.fund.eastmoney.com/f10/lsjz），申购/赎回状态取自同接口最新披露。
          </li>
          <li>
            <strong>刷新方式：</strong>
            快照在服务端缓存 60 秒，表格上方可手动刷新；接口不缓存历史数据之外的结果，也不做任何模拟回填。
          </li>
        </ul>
      </section>

      <section className='etf-premium-section' aria-labelledby='etf-formula'>
        <h2 id='etf-formula'>溢价率怎么算</h2>
        <p>
          <code>溢价率 = (场内最新价 − IOPV) ÷ IOPV × 100%</code>
          ，正值代表溢价、负值代表折价。IOPV
          是基金管理人盘中发布的参考净值，缺失时该行直接显示缺失而不是 0；行情接口自带的「基金折价率」列符号口径（折价为正）与本页相反且无法在服务端验证，因此不使用，全部溢价都按上面的公式重算。
        </p>
        <p>
          表格里的行情时间来自行情源自身的时间戳；个别标的停牌或未更新时，时间会落后于当日最新行情并以琥珀色标出。
        </p>
      </section>

      <section className='etf-premium-section' aria-labelledby='etf-grouping'>
        <h2 id='etf-grouping'>分组与“同组低溢价”</h2>
        <ul>
          <li>
            分组依据是逐只核对过的基金全名（FundMNBaseInfo 完整档案，共 193 只，核对日期
            2026-11-24）：跟踪指数表述完全一致才并入同组，例如恒生科技 9 只、纳斯达克100 12 只。
          </li>
          <li>
            口径存疑的组合不合并：如“恒指港股通”与恒生指数保持两个独立组。名单外的新基金一律归入
            <strong>未分组</strong>，不按名称猜测。
          </li>
          <li>
            同组内至少两只标的能计算溢价时，溢价率最低的那只标注
            <strong>组内低溢价</strong>
            ——同样的指数敞口，它是当前通道里相对便宜的载体；这是排序结果，不是买入建议。
          </li>
        </ul>
      </section>

      <section className='etf-premium-section' aria-labelledby='etf-limits'>
        <h2 id='etf-limits'>适用范围与 QDII 限购风险</h2>
        <ul>
          <li>
            高溢价<strong>不等于</strong>看空海外指数：QDII 外汇额度受限、基金暂停或限制申购时，套利盘无法通过申购平抑溢价，溢价可以长期存在甚至持续扩大；港股通产品没有 QDII 额度约束，溢价通常小得多。
          </li>
          <li>
            点击标的后可见的“历史溢价序列”由当日收盘价与当日单位净值重建。单位净值在收盘后才最终确定，QDII 通常 T+1 至 T+2 披露，因此该序列是<strong>披露口径的事后记录</strong>，不能当作盘中可实时套利的信号。
          </li>
          <li>
            场内 LOF（501/502/16 开头）不在本页范围；货币与债券 ETF、境内指数 ETF 会被名单类型直接排除。
          </li>
          <li>
            数据可能有延迟、缺失或接口变更导致的失败，页面对这些状态都会如实显示；上游接口属于公开非官方接口，结构变化时本页会报错而不是给出假数据。
          </li>
        </ul>
      </section>

      <section className='etf-premium-section' aria-labelledby='etf-disclaimer'>
        <h2 id='etf-disclaimer'>非投资建议</h2>
        <p>
          本页是个人研究工具，展示的是公开数据的计算结果，不构成任何投资建议、交易推荐或收益承诺。溢价收敛可能迟到也可能不发生，追高溢价份额的代价请自行评估；页面底部附方法与完整披露。
        </p>
      </section>

    </main>
  )
}
