import { PrismaClient } from '@prisma/client'

const prisma = new PrismaClient()

// 基于搜索分析的利润质量判断
// isRecurring: true = 经常性利润（正常）, false = 非经常性利润（需调整）
const profitQualityData: Array<{
  symbol: string
  market: string
  title: string
  isRecurring: boolean
  explanationTitle: string
  explanationBody: string
  confidence: number
}> = [
  // ===== 正常（经常性利润）===== 
  {
    symbol: '00700.HK',
    market: 'hk',
    title: '腾讯控股',
    isRecurring: true,
    explanationTitle: '核心业务利润占比超90%',
    explanationBody: '2024年利润由游戏出海、AI驱动广告、金融科技等核心业务贡献，占比超90%。投资收益约180亿元（占比约10%），主要为上市公司分红和联营企业减亏，虽属非经常性但具有一定持续性。整体利润质量良好。',
    confidence: 85,
  },
  {
    symbol: '00941.HK',
    market: 'hk',
    title: '中国移动',
    isRecurring: true,
    explanationTitle: '扣非净利润占比约89%，利润结构稳健',
    explanationBody: '2024年归母净利润1383.73亿元，扣非净利润1227.15亿元，扣非占比约89%。非经常性损益主要来自政府补助等，金额相对可控。作为电信运营商，核心业务现金流稳定，利润质量较高。',
    confidence: 90,
  },
  {
    symbol: '00005.HK',
    market: 'hk',
    title: '汇丰控股',
    isRecurring: true,
    explanationTitle: '银行业务利润为主，含10亿美元重大项目收入',
    explanationBody: '2024年税前利润323亿美元，其中包含重大项目带来的10亿美元收入（约3%）。核心业务为财富管理、个人银行及环球银行，利息收益437亿美元。非经常性项目占比较低，利润质量整体正常。',
    confidence: 82,
  },
  {
    symbol: '000333',
    market: 'cn',
    title: '美的集团',
    isRecurring: true,
    explanationTitle: '扣非净利润357亿，核心经营利润占比93%',
    explanationBody: '2024年净利润385亿元，扣非净利润357.41亿元，扣非占比约93%。非经常性损益约27.6亿元，主要来自政府补助和资产处置。家电主业盈利稳定，利润质量正常。',
    confidence: 88,
  },
  {
    symbol: '300059',
    market: 'cn',
    title: '东方财富',
    isRecurring: true,
    explanationTitle: '扣非净利润占比96%，经纪业务利润为主',
    explanationBody: '2024年净利润96.10亿元，扣非净利润92.53亿元，扣非占比约96%。非经常性损益仅3.57亿元。作为互联网券商，利润主要来自经纪业务和基金销售，具有持续性。利润质量正常。',
    confidence: 90,
  },
  {
    symbol: '301358',
    market: 'cn',
    title: '湖南裕能',
    isRecurring: true,
    explanationTitle: '扣非净利润占比96%，磷酸铁锂主业利润',
    explanationBody: '2024年归母净利润5.94亿元，扣非净利润5.7亿元，扣非占比约96%。非经常性损益仅0.24亿元。公司主营磷酸铁锂正极材料，利润来自核心产品销售，虽受行业周期影响下滑，但利润质量正常。',
    confidence: 85,
  },
  {
    symbol: '603129',
    market: 'cn',
    title: '春风动力',
    isRecurring: true,
    explanationTitle: '全地形车/摩托车主业利润，增长稳健',
    explanationBody: '2024年前三季度净利润10.81亿元，同比增长34.87%。公司主营全地形车和摩托车，出口占比高。利润主要来自核心产品销售，非经常性损益影响较小。利润质量正常。',
    confidence: 82,
  },
  {
    symbol: '603408',
    market: 'cn',
    title: '建霖家居',
    isRecurring: true,
    explanationTitle: '扣非净利润占比96%，卫浴主业利润稳定',
    explanationBody: '2024年归母净利润4.82亿元，扣非净利润4.65亿元，扣非占比约96%。非经常性损益仅0.17亿元。公司主营卫浴、净水等家居产品，利润来自主营业务，质量正常。',
    confidence: 88,
  },
  {
    symbol: '600761',
    market: 'cn',
    title: '安徽合力',
    isRecurring: true,
    explanationTitle: '扣非净利润占比79%，叉车主业利润',
    explanationBody: '2024年归母净利润13.2亿元，扣非净利润10.4亿元，扣非占比约79%。非经常性损益约2.8亿元，主要来自政府补助。叉车主业盈利稳定，利润质量整体正常，但非经常性损益占比略高。',
    confidence: 78,
  },
  {
    symbol: '02269.HK',
    market: 'hk',
    title: '药明生物',
    isRecurring: true,
    explanationTitle: 'CDMO主业利润，非新冠收入同比增长13.1%',
    explanationBody: '2024年营收186.75亿元，净利润33.6亿元（同比下降1.3%）。非新冠收入同比增长13.1%，显示核心业务持续增长。利润主要来自生物药CDMO服务，非经常性损益影响较小。利润质量正常。',
    confidence: 82,
  },
  {
    symbol: '688100',
    market: 'cn',
    title: '威胜信息',
    isRecurring: true,
    explanationTitle: '扣非净利润占比97%，能源物联网主业',
    explanationBody: '2024年归母净利润6.31亿元，扣非净利润6.10亿元，扣非占比约97%。非经常性损益仅0.21亿元。公司主营能源物联网解决方案，利润来自核心业务收入，质量正常。',
    confidence: 90,
  },
  {
    symbol: 'DG',
    market: 'us',
    title: 'DOLLAR GENERAL CORP',
    isRecurring: true,
    explanationTitle: '折扣零售主业利润，现金流稳定',
    explanationBody: 'Dollar General为美国折扣零售连锁企业，利润主要来自商品销售。2024年业绩承压但核心业务稳定，非经常性损益影响较小。利润质量正常。',
    confidence: 80,
  },
  {
    symbol: 'JPM',
    market: 'us',
    title: 'JPMORGAN CHASE & CO',
    isRecurring: true,
    explanationTitle: '投行/零售银行主业利润，行业龙头',
    explanationBody: '摩根大通为全球最大银行之一，2024年Q4净利润140亿美元，同比增长50%。利润主要来自利息收入、投行业务和资产管理。虽受利率环境影响，但核心业务稳定，利润质量正常。',
    confidence: 85,
  },
  {
    symbol: '000973',
    market: 'cn',
    title: '佛塑科技',
    isRecurring: true,
    explanationTitle: '扣非净利润同比增长153%，主业改善明显',
    explanationBody: '2024年归母净利润1.20亿元（同比下降44%），但扣非净利润9657万元，同比增长153.48%。净利润下降主要因2023年有大额非经常性收益（资产处置等），2024年扣非利润实际大幅改善。利润质量正常。',
    confidence: 75,
  },
  {
    symbol: '000795',
    market: 'cn',
    title: '英洛华',
    isRecurring: true,
    explanationTitle: '扣非净利润占比86%，磁材主业利润',
    explanationBody: '2024年归母净利润2.48亿元，扣非净利润2.13亿元，扣非占比约86%。非经常性损益约0.35亿元。公司主营稀土磁材，利润来自核心产品销售，质量正常。',
    confidence: 80,
  },

  // ===== 需调整（非经常性利润）=====
  {
    symbol: '002154',
    market: 'cn',
    title: '报喜鸟',
    isRecurring: false,
    explanationTitle: '最近一季EPS异常，疑似一次性收入',
    explanationBody: '最近一季EPS(0.160)是前3季均值(0.039)的4.1倍，疑似一次性收入。2024年归母净利润4.95亿元，扣非净利润4.36亿元，扣非占比约88%。但季度利润分布极不均匀，Q4利润可能包含非经常性项目。利润质量需调整。',
    confidence: 72,
  },
  {
    symbol: '000100',
    market: 'cn',
    title: 'TCL科技',
    isRecurring: false,
    explanationTitle: '扣非净利润仅2.98亿，非经常性损益占比81%',
    explanationBody: '2024年归母净利润15.6亿元，但扣非净利润仅2.98亿元，同比下降70.78%。非经常性损益高达12.62亿元，占比81%。主要来自政府补助、资产处置等。面板主业盈利薄弱，利润质量需调整。',
    confidence: 85,
  },
  {
    symbol: '301308',
    market: 'cn',
    title: '江波龙',
    isRecurring: false,
    explanationTitle: '最近一季EPS是前3季均值的7.3倍，疑似一次性收入',
    explanationBody: '最近一季EPS(9.210)是前3季均值(1.260)的7.3倍，疑似一次性收入。2024年扣非净利润波动较大，虽同比扭亏，但Q4利润异常集中。存储行业周期性明显，且存在大额存货减值和股份支付费用。利润质量需调整。',
    confidence: 70,
  },
  {
    symbol: '688525',
    market: 'cn',
    title: '佰维存储',
    isRecurring: false,
    explanationTitle: '股份支付费用3.45亿，扣非净利润仅6697万',
    explanationBody: '2024年归母净利润1.61亿元，扣非净利润仅6697万元。公司承担了约3.45亿元的股份支付费用（非经常性）。若剔除股份支付，净利润约5.05-5.45亿元。此外Q4 EPS异常高（是前3季均值的8.1倍），疑似一次性收入。利润质量需调整。',
    confidence: 78,
  },
  {
    symbol: '01104.HK',
    market: 'hk',
    title: '亚太资源',
    isRecurring: false,
    explanationTitle: '净利率32.8%主因非经营性收益，扣非后实际亏损',
    explanationBody: '2024年ROE为10.56%，但净利率32.8%远高于2023年的-59%，主因非经营性收益。最近一季EPS(1.176)是前3季均值(0.073)的16.1倍，疑似一次性收入。EPS增长979%但股价仅涨140%，市场对增长存疑。利润质量需调整。',
    confidence: 82,
  },
  {
    symbol: '00688.HK',
    market: 'hk',
    title: '中国海外发展',
    isRecurring: false,
    explanationTitle: '房地产结算利润，近4季利润增速-40.2%',
    explanationBody: '2024年归母净利润156.4亿元，同比增长38.9%，但营收同比下降8.5%。房地产行业深度调整中，利润主要来自前期项目结算，可持续性存疑。近4季利润增速-40.2%，利润质量需调整。',
    confidence: 75,
  },
  {
    symbol: '00085.HK',
    market: 'hk',
    title: '中电华大科技',
    isRecurring: false,
    explanationTitle: '收入下降22.2%，利润下滑14.4%',
    explanationBody: '2024年度收入24.5亿港币下降22.2%，净利润5.88亿下降14.4%。集成电路设计业务（智能卡及安全芯片）面临价格和销售量双重压力。利润下滑幅度小于收入下滑，可能存在非经常性收益支撑。利润质量需调整。',
    confidence: 68,
  },
  {
    symbol: '02552.HK',
    market: 'hk',
    title: '华领医药-B',
    isRecurring: false,
    explanationTitle: '首次年度盈利依赖华堂宁销售，持续性待验证',
    explanationBody: '2024年首次实现年度盈利，税前盈利11.06亿元。但公司此前长期亏损，盈利主要来自降糖药华堂宁的销售收入（2.559亿元）和其他收入（1.168亿元）。作为创新药企业，单产品收入能否持续增长存疑。利润质量需调整。',
    confidence: 70,
  },
  {
    symbol: '600000',
    market: 'cn',
    title: '浦发银行',
    isRecurring: false,
    explanationTitle: '扣非净利润442亿，非经常性损益约10.5亿',
    explanationBody: '2024年归母净利润452.57亿元，扣非净利润442.07亿元，非经常性损益约10.5亿元。虽然扣非占比约98%，但银行业利润受利率下行和信用风险影响，且存在较大规模的投资收益。利润质量整体正常偏谨慎。',
    confidence: 72,
  },
]

async function main() {
  console.log('开始写入利润质量解释数据...\n')

  for (const item of profitQualityData) {
    // 查找公司
    const company = await prisma.company.findUnique({
      where: {
        market_symbol: {
          market: item.market,
          symbol: item.symbol,
        },
      },
    })

    if (!company) {
      console.log(`❌ 未找到公司: ${item.symbol} (${item.market})`)
      continue
    }

    // 查找最新估值快照
    const latestSnapshot = await prisma.companyValuationSnapshot.findFirst({
      where: { companyId: company.id },
      orderBy: [{ asOfDate: 'desc' }, { createdAt: 'desc' }],
    })

    // 先将该公司所有现有解释标记为非当前
    await prisma.companyValuationExplanation.updateMany({
      where: {
        companyId: company.id,
        explanationType: 'profit',
        isCurrent: true,
      },
      data: { isCurrent: false },
    })

    // 创建新的解释记录
    await prisma.companyValuationExplanation.create({
      data: {
        companyId: company.id,
        valuationSnapshotId: latestSnapshot?.id || null,
        explanationType: 'profit',
        title: item.explanationTitle,
        body: item.explanationBody,
        impactDirection: item.isRecurring ? 'positive' : 'negative',
        isRecurring: item.isRecurring,
        confidence: item.confidence,
        authorType: 'ai',
        isCurrent: true,
      },
    })

    const status = item.isRecurring ? '✅ 正常' : '⚠️ 需调整'
    console.log(`${status} ${item.symbol} - ${item.title}`)
    console.log(`   ${item.explanationTitle}`)
    console.log()
  }

  console.log('完成！')
}

main()
  .catch((error) => {
    console.error(error)
    process.exitCode = 1
  })
  .finally(async () => {
    await prisma.$disconnect()
  })
