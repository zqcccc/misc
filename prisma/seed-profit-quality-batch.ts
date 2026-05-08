import { PrismaClient } from '@prisma/client'

const prisma = new PrismaClient()

// 批量搜索和分析后的人工整理数据
// 基于公开财报中的"扣非净利润"与"净利润"比例来判断
const profitQualityBatch: Array<{
  symbol: string
  market: string
  title: string
  isRecurring: boolean
  explanationTitle: string
  explanationBody: string
  confidence: number
}> = [
  // ===== A股公司 =====
  // 银行（需调整 - 投资收益占比高）
  { symbol: '601577', market: 'cn', title: '长沙银行', isRecurring: false, explanationTitle: '城商行，利润含投资收益', explanationBody: '城商行利润主要来自利息收入和投资收益，非经常性损益影响较小但需关注资产质量。利润质量整体正常偏谨慎。', confidence: 70 },
  { symbol: '601997', market: 'cn', title: '贵阳银行', isRecurring: false, explanationTitle: '城商行，利润含投资收益', explanationBody: '城商行利润主要来自利息收入和投资收益。需关注不良贷款率和区域经济风险。利润质量正常偏谨慎。', confidence: 70 },

  // 保险（需调整 - 投资收益占比高）
  { symbol: '01299.HK', market: 'hk', title: '友邦保险', isRecurring: true, explanationTitle: '寿险主业利润，新业务价值增长', explanationBody: '友邦保险专注亚太地区寿险业务，利润主要来自保费收入和投资回报。新业务价值增长强劲，利润质量正常。', confidence: 82 },

  // 媒体出版
  { symbol: '601900', market: 'cn', title: '南方传媒', isRecurring: true, explanationTitle: '出版发行业主利润，现金流稳定', explanationBody: '公司主营出版发行业务，利润主要来自教材教辅和一般图书销售。文化产业具有防御性特征，利润质量正常。', confidence: 80 },

  // 环保
  { symbol: '000544', market: 'cn', title: '中原环保', isRecurring: true, explanationTitle: '水务运营主业利润', explanationBody: '公司主营污水处理和环保运营，利润主要来自水费收入和运营服务。具有稳定现金流特征，利润质量正常。', confidence: 78 },

  // 制造业
  { symbol: '002801', market: 'cn', title: '微光股份', isRecurring: true, explanationTitle: '电机风机主业利润', explanationBody: '公司主营电机和风机业务，产品出口占比较高。利润主要来自制造业销售，非经常性损益影响较小，利润质量正常。', confidence: 78 },
  { symbol: '000726', market: 'cn', title: '鲁泰A', isRecurring: true, explanationTitle: '纺织出口主业利润', explanationBody: '公司主营高档面料出口，利润主要来自纺织制造业务。出口占比较高，盈利受汇率和贸易环境影响。利润质量正常。', confidence: 75 },
  { symbol: '600587', market: 'cn', title: '新华医疗', isRecurring: true, explanationTitle: '医疗器械主业利润', explanationBody: '公司主营医疗器械制造和销售，利润主要来自医疗设备业务。受益于医疗新基建，利润质量正常。', confidence: 78 },
  { symbol: '603025', market: 'cn', title: '大豪科技', isRecurring: true, explanationTitle: '缝制设备主业利润', explanationBody: '公司主营缝制设备电控系统，利润主要来自刺绣机、缝纫机电控产品。利润质量正常。', confidence: 75 },
  { symbol: '000589', market: 'cn', title: '贵州轮胎', isRecurring: true, explanationTitle: '轮胎制造主业利润', explanationBody: '公司主营轮胎制造，利润主要来自替换胎和配套胎销售。受益于原材料价格回落，利润质量改善中。', confidence: 72 },

  // 能源
  { symbol: '01898.HK', market: 'hk', title: '中煤能源', isRecurring: true, explanationTitle: '煤炭生产主业利润', explanationBody: '公司主营煤炭生产和销售，利润主要来自煤炭销售。煤价波动影响较大但核心业务稳定，利润质量正常。', confidence: 75 },
  { symbol: '601311', market: 'cn', title: '骆驼股份', isRecurring: true, explanationTitle: '汽车电池主业利润', explanationBody: '公司主营汽车铅酸电池，利润主要来自配套市场和替换市场。受益于汽车后市场增长，利润质量正常。', confidence: 76 },

  // 基建地产
  { symbol: '600502', market: 'cn', title: '安徽建工', isRecurring: true, explanationTitle: '建筑工程主业利润', explanationBody: '公司主营建筑工程，利润主要来自施工业务。房地产关联业务需关注，应收账款规模较大。利润质量正常偏谨慎。', confidence: 70 },

  // 旅游
  { symbol: '002033', market: 'cn', title: '丽江股份', isRecurring: true, explanationTitle: '旅游景区运营利润', explanationBody: '公司主营旅游景区和酒店运营，利润主要来自索道和演艺业务。旅游消费复苏带动利润增长，利润质量正常。', confidence: 78 },

  // 城建设计
  { symbol: '01599.HK', market: 'hk', title: '城建设计', isRecurring: true, explanationTitle: '城轨设计主业利润', explanationBody: '公司主营城市轨道交通设计咨询，利润主要来自设计服务。基建投资带动业务增长，利润质量正常。', confidence: 76 },

  // 房地产
  { symbol: '00884.HK', market: 'hk', title: '旭辉控股集团', isRecurring: false, explanationTitle: '房地产行业深度调整中', explanationBody: '旭辉控股为民营房地产开发商，当前行业深度调整，流动性压力较大。房地产结算利润可持续性存疑，利润质量需调整。', confidence: 65 },

  // 金融
  { symbol: '00662.HK', market: 'hk', title: '亚洲金融', isRecurring: true, explanationTitle: '保险及金融服务利润', explanationBody: '公司从事保险及金融服务业务，利润来自保险承保和投资收益。利润质量正常。', confidence: 72 },
  { symbol: '01712.HK', market: 'hk', title: '龙资源', isRecurring: true, explanationTitle: '黄金采矿主业利润', explanationBody: '公司主营黄金采矿业务，利润来自黄金销售。金价上涨带动利润增长，但具有周期性特征。利润质量正常。', confidence: 70 },

  // 航空
  { symbol: '000089', market: 'cn', title: '深圳机场', isRecurring: true, explanationTitle: '航空地面服务利润', explanationBody: '公司主营航空地面服务和航空性业务，利润主要来自航班收费和旅客服务费。航空出行复苏带动业绩增长，利润质量正常。', confidence: 76 },

  // 汽车
  { symbol: '601127', market: 'cn', title: '赛力斯', isRecurring: true, explanationTitle: '新能源车销售利润', explanationBody: '公司主营新能源汽车生产销售，与华为合作推出问界品牌。销量增长带动营收，但竞争激烈仍需关注盈利能力持续性。利润质量正常偏谨慎。', confidence: 68 },
]

async function main() {
  console.log('开始批量写入利润质量解释数据...\n')
  console.log(`本次将处理 ${profitQualityBatch.length} 家公司\n`)

  let successCount = 0
  let failCount = 0

  for (const item of profitQualityBatch) {
    try {
      const company = await prisma.company.findUnique({
        where: {
          market_symbol: {
            market: item.market,
            symbol: item.symbol,
          },
        },
      })

      if (!company) {
        console.log(`❌ 未找到: ${item.symbol}`)
        failCount++
        continue
      }

      const latestSnapshot = await prisma.companyValuationSnapshot.findFirst({
        where: { companyId: company.id },
        orderBy: [{ asOfDate: 'desc' }, { createdAt: 'desc' }],
      })

      await prisma.companyValuationExplanation.updateMany({
        where: {
          companyId: company.id,
          explanationType: 'profit',
          isCurrent: true,
        },
        data: { isCurrent: false },
      })

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

      const status = item.isRecurring ? '✅' : '⚠️'
      console.log(`${status} ${item.symbol} - ${item.title}`)
      successCount++
    } catch (error) {
      console.log(`❌ 错误 ${item.symbol}:`, error)
      failCount++
    }
  }

  console.log(`\n完成！成功: ${successCount}, 失败: ${failCount}`)
}

main()
  .catch((error) => {
    console.error(error)
    process.exitCode = 1
  })
  .finally(async () => {
    await prisma.$disconnect()
  })
