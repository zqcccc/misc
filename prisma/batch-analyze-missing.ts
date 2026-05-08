/**
 * 批量为所有短格式 exploration 重新生成专业金融分析师级别的深度分析
 * 基于最新的 CompanyValuationSnapshot 数据，模拟真实分析师视角
 */

import { PrismaClient } from '@prisma/client'

const prisma = new PrismaClient()

type ImpactDirection = 'positive' | 'neutral' | 'negative'

interface CompanyData {
  id: string
  symbol: string
  market: string
  name: string
  sector: string | null
  industry: string | null
  pe: number | null
  price: number | null
  profitLine: number | null
  referenceLine: number | null
  upside: number | null
  refUpside: number | null
  eps: number | null
  profitQualityScore: number | null
  profitQualitySummary: string | null
  marketCap: number | null
  explorationId: string
  currentScore: number | null
  currentSummary: string | null
}

// ===== 行业知识库 =====

const INDUSTRY_INSIGHTS: Record<string, {
  characteristics: string
  keyMetrics: string
  cyclePhase: string
  policyEnv: string
  competitiveLandscape: string
}> = {
  '银行': {
    characteristics: '高杠杆、强周期、受利率和监管政策影响大',
    keyMetrics: '净息差(NIM)、不良贷款率、拨备覆盖率、ROE',
    cyclePhase: '当前处于利率下行周期，净息差承压，但资产质量整体稳健',
    policyEnv: '货币政策宽松，信贷投放力度加大，支持实体经济',
    competitiveLandscape: '国有大行主导，股份制银行差异化竞争，城商行深耕本地',
  },
  '保险': {
    characteristics: '长期负债经营、投资收益敏感、受利率和资本市场波动影响大',
    keyMetrics: '内含价值(EV)、新业务价值(VNB)、综合成本率、投资收益率',
    cyclePhase: '寿险转型阵痛期，代理人渠道改革深化，财险竞争加剧',
    policyEnv: '监管趋严，产品定价利率下调，防范利差损风险',
    competitiveLandscape: '头部险企集中度高，中小险企寻求差异化',
  },
  '白酒': {
    characteristics: '高毛利、强品牌、库存增值、消费属性强',
    keyMetrics: '批价/零售价、渠道库存、动销率、毛利率',
    cyclePhase: '高端白酒需求刚性，次高端竞争激烈，区域酒分化',
    policyEnv: '消费复苏缓慢，商务宴请受限，但宴席市场回暖',
    competitiveLandscape: '茅台一家独大，五粮液、老窖紧随其后，酱酒降温',
  },
  '医药': {
    characteristics: '研发驱动、政策敏感、需求刚性、长周期',
    keyMetrics: '研发投入占比、管线进度、医保谈判价格、销售额',
    cyclePhase: '创新药出海加速，仿制药集采常态化，CXO受融资环境拖累',
    policyEnv: '集采扩面、医保控费、鼓励创新药研发',
    competitiveLandscape: '创新药企融资困难，头部CXO全球化布局',
  },
  '半导体': {
    characteristics: '高资本开支、技术迭代快、周期性强、地缘政治敏感',
    keyMetrics: '产能利用率、晶圆价格、先进制程占比、客户集中度',
    cyclePhase: '周期底部回升，AI芯片需求旺盛，消费电子复苏缓慢',
    policyEnv: '国产替代加速，大基金三期落地，但设备出口管制收紧',
    competitiveLandscape: '设备材料国产化率低，设计端竞争激烈',
  },
  '新能源': {
    characteristics: '高成长、高资本开支、技术路线多变、政策依赖',
    keyMetrics: '装机量/出货量、毛利率、产能利用率、技术路线占比',
    cyclePhase: '光伏产能过剩，价格战激烈；锂电中游去库存；风电招标回暖',
    policyEnv: '双碳目标坚定，但补贴退坡，市场化竞争加剧',
    competitiveLandscape: '各环节龙头集中，二线厂商生存困难',
  },
  '地产': {
    characteristics: '高杠杆、强周期、政策敏感、区域分化',
    keyMetrics: '销售额、去化率、融资成本、土储质量',
    cyclePhase: '行业深度调整，销售低迷，融资困难，出清加速',
    policyEnv: '需求端政策放松，但供给端风险尚未完全化解',
    competitiveLandscape: '国央企主导，民企收缩，行业集中度提升',
  },
  '建筑': {
    characteristics: '订单驱动、低毛利、高应收、政策依赖',
    keyMetrics: '新签订单、毛利率、应收账款周转、现金流',
    cyclePhase: '基建投资托底，房建拖累，海外订单增长',
    policyEnv: '专项债发力，城中村改造推进，但地方财政承压',
    competitiveLandscape: '央企主导，地方国企跟随，民企边缘化',
  },
  '消费': {
    characteristics: '需求驱动、品牌溢价、渠道为王、受经济周期影响',
    keyMetrics: '同店增长、客单价、毛利率、渠道渗透率',
    cyclePhase: '消费分级明显，性价比消费崛起，高端消费韧性',
    policyEnv: '促消费政策频出，但居民收入增长放缓',
    competitiveLandscape: '国产品牌崛起，外资品牌承压，线上渠道集中',
  },
  '汽车': {
    characteristics: '资本密集、技术密集、供应链长、受政策和消费双重影响',
    keyMetrics: '销量、市占率、毛利率、智能化配置率',
    cyclePhase: '新能源渗透率提升，价格战激烈，智能化竞赛',
    policyEnv: '以旧换新补贴，新能源购置税优惠延续',
    competitiveLandscape: '比亚迪领跑，新势力分化，合资份额下滑',
  },
  '煤炭': {
    characteristics: '强周期、高现金流、政策调控、供需错配',
    keyMetrics: '煤价、产量、成本、长协占比',
    cyclePhase: '供需偏紧，煤价高位震荡，但新能源替代加速',
    policyEnv: '保供稳价，长协比例提升，限制煤价大幅波动',
    competitiveLandscape: '央企主导，地方国企跟随，行业集中度高',
  },
  '钢铁': {
    characteristics: '强周期、高能耗、产能过剩、环保压力大',
    keyMetrics: '钢价、吨钢毛利、产能利用率、铁矿石成本',
    cyclePhase: '需求疲软，产能过剩，盈利低位徘徊',
    policyEnv: '粗钢产量压减，环保限产，产能置换',
    competitiveLandscape: '宝武系主导，行业整合加速',
  },
  '化工': {
    characteristics: '中游制造、原材料成本敏感、周期性强、环保约束',
    keyMetrics: '产品价格价差、产能利用率、原材料成本占比',
    cyclePhase: '部分子行业触底回升，但整体需求偏弱',
    policyEnv: '安全生产趋严，环保督察常态化',
    competitiveLandscape: '龙头规模优势显现，中小企业出清',
  },
  '电力': {
    characteristics: '公用事业属性、受煤价和电价双重影响、现金流稳定',
    keyMetrics: '利用小时数、上网电价、煤价、绿电占比',
    cyclePhase: '火电盈利修复，新能源装机高增',
    policyEnv: '电价市场化改革，绿电交易推进',
    competitiveLandscape: '五大发电集团主导，新能源运营商崛起',
  },
  '交运': {
    characteristics: '基础设施属性、受经济活动和油价影响、重资产',
    keyMetrics: '吞吐量/周转量、运价、燃油成本、产能利用率',
    cyclePhase: '航空复苏，航运高位回落，快递价格战趋缓',
    policyEnv: '物流降本增效，国际航线恢复',
    competitiveLandscape: '航空三大航主导，快递头部集中',
  },
  '传媒': {
    characteristics: '内容为王、流量驱动、政策敏感、变现模式多变',
    keyMetrics: 'DAU/MAU、ARPU、广告收入、内容成本',
    cyclePhase: '游戏版号常态化，短剧爆发，AI应用探索',
    policyEnv: '内容监管趋严，但游戏产业获政策支持',
    competitiveLandscape: '互联网平台集中，内容公司分化',
  },
  '机械': {
    characteristics: '制造业中游、受下游投资驱动、技术升级',
    keyMetrics: '订单增速、毛利率、出口占比、研发投入',
    cyclePhase: '工程机械国内筑底，出口放缓；高端制造进口替代',
    policyEnv: '设备更新政策，高端制造扶持',
    competitiveLandscape: '三一、中联等龙头主导，细分领域专精特新',
  },
  '电子': {
    characteristics: '技术密集、供应链全球化、消费驱动',
    keyMetrics: '出货量、ASP、毛利率、库存周转',
    cyclePhase: '消费电子复苏缓慢，AI终端创新',
    policyEnv: '消费电子补贴，产业链国产化',
    competitiveLandscape: '苹果链集中，安卓链分散',
  },
  '计算机': {
    characteristics: '软件服务、项目制、人力密集、技术迭代快',
    keyMetrics: '合同金额、毛利率、人效、回款周期',
    cyclePhase: '信创推进，AI应用落地，但政府IT支出承压',
    policyEnv: '数字经济、信创、数据要素政策',
    competitiveLandscape: '华为系崛起，传统厂商转型',
  },
  '通信': {
    characteristics: '基础设施、资本密集、运营商主导、技术升级',
    keyMetrics: 'ARPU、5G渗透率、资本开支、云计算收入',
    cyclePhase: '5G建设放缓，算力网络布局，云计算增长',
    policyEnv: '数字中国，算力基础设施',
    competitiveLandscape: '三大运营商垄断，设备商华为中兴主导',
  },
  '有色金属': {
    characteristics: '强周期、全球定价、受供需和美元影响',
    keyMetrics: '金属价格、产量、成本、库存',
    cyclePhase: '铜铝价格高位，锂钴触底，稀土稳定',
    policyEnv: '战略资源保护，绿色冶炼',
    competitiveLandscape: '央企主导，海外资源布局',
  },
  '石油石化': {
    characteristics: '全球定价、资本密集、上下游一体化',
    keyMetrics: '油价、炼油毛利、化工品价差、产量',
    cyclePhase: '油价中高位震荡，炼化盈利分化',
    policyEnv: '能源安全，增储上产',
    competitiveLandscape: '三桶油主导，民营炼化崛起',
  },
  '农业': {
    characteristics: '弱周期、政策保护、受天气影响、消费升级',
    keyMetrics: '猪价/粮价、出栏量、成本、存栏',
    cyclePhase: '猪周期底部回升，种业振兴',
    policyEnv: '粮食安全，种业振兴，养殖规范化',
    competitiveLandscape: '养殖龙头集中，种业待突破',
  },
  '纺织': {
    characteristics: '劳动密集、出口导向、品牌升级',
    keyMetrics: '订单量、毛利率、汇率影响、产能转移',
    cyclePhase: '出口承压，内需分化，品牌转型',
    policyEnv: '出口退税，内需刺激',
    competitiveLandscape: '代工向品牌转型，东南亚竞争',
  },
  '建材': {
    characteristics: '地产下游、强周期、高能耗、区域性强',
    keyMetrics: '水泥价格、玻璃价格、产能利用率、应收账款',
    cyclePhase: '需求低迷，产能过剩，盈利承压',
    policyEnv: '错峰生产，环保限产',
    competitiveLandscape: '海螺、中国建材主导',
  },
  '家电': {
    characteristics: '制造业、消费属性、出口占比高、技术升级',
    keyMetrics: '销量、均价、毛利率、海外收入占比',
    cyclePhase: '内销复苏缓慢，出口增长，智能化升级',
    policyEnv: '以旧换新，绿色智能家电',
    competitiveLandscape: '美的、格力、海尔三足鼎立',
  },
  '食品饮料': {
    characteristics: '必选消费、品牌溢价、渠道为王',
    keyMetrics: '营收增速、毛利率、渠道库存、新品贡献',
    cyclePhase: '调味品复苏，乳制品承压，零食渠道变革',
    policyEnv: '消费促进，食品安全监管',
    competitiveLandscape: '龙头集中，新品牌通过新渠道崛起',
  },
  '轻工': {
    characteristics: '制造业、出口导向、消费升级',
    keyMetrics: '订单、毛利率、汇率、原材料成本',
    cyclePhase: '出口分化，内需疲软，造纸周期底部',
    policyEnv: '出口支持，内需刺激',
    competitiveLandscape: '细分龙头集中，代工转型品牌',
  },
  '军工': {
    characteristics: '订单驱动、高壁垒、长周期、政策敏感',
    keyMetrics: '订单增速、毛利率、研发投入、交付进度',
    cyclePhase: '十四五订单放量，但回款放缓',
    policyEnv: '国防预算增长，装备现代化',
    competitiveLandscape: '央企军工集团主导，民参军受限',
  },
  '环保': {
    characteristics: '政策驱动、项目制、回款慢、现金流差',
    keyMetrics: '订单、毛利率、应收账款、现金流',
    cyclePhase: '传统环保增速放缓，双碳新业务兴起',
    policyEnv: '双碳目标，环保督察',
    competitiveLandscape: '国企主导，民企出清',
  },
  '教育': {
    characteristics: '政策敏感、刚需属性、预收款模式',
    keyMetrics: '招生人数、学费、毛利率、政策合规',
    cyclePhase: 'K12教培转型，职业教育兴起',
    policyEnv: '双减持续，职业教育鼓励',
    competitiveLandscape: '新东方、好未来转型，中公困境',
  },
  '零售': {
    characteristics: '渠道为王、受消费影响大、线上线下融合',
    keyMetrics: '同店增长、坪效、毛利率、线上占比',
    cyclePhase: '线下复苏缓慢，折扣店兴起',
    policyEnv: '促消费，支持实体零售',
    competitiveLandscape: '电商主导，线下转型',
  },
  '物流': {
    characteristics: '基础设施、规模效应、受电商影响',
    keyMetrics: '件量、单票收入、毛利率、时效',
    cyclePhase: '快递价格战趋缓，快运整合',
    policyEnv: '物流降本增效',
    competitiveLandscape: '顺丰、通达系主导',
  },
  '酒店': {
    characteristics: '服务业、受出行影响、轻资产转型',
    keyMetrics: 'RevPAR、入住率、ADR、开店速度',
    cyclePhase: '商旅复苏，休闲游强劲',
    policyEnv: '文旅消费促进',
    competitiveLandscape: '华住、锦江、首旅三强',
  },
  '旅游': {
    characteristics: '服务业、受假期影响、季节性强',
    keyMetrics: '客流、客单价、毛利率、复购率',
    cyclePhase: '报复性出游后回归常态',
    policyEnv: '文旅融合，带薪休假',
    competitiveLandscape: 'OTA集中，景区分散',
  },
  '游戏': {
    characteristics: '内容驱动、爆款依赖、出海增长',
    keyMetrics: 'DAU、ARPU、流水、版号',
    cyclePhase: '版号常态化，AI游戏探索',
    policyEnv: '版号发放，未成年人保护',
    competitiveLandscape: '腾讯、网易主导，米哈游崛起',
  },
  '互联网': {
    characteristics: '平台经济、流量为王、变现多元',
    keyMetrics: 'DAU、ARPU、广告收入、云收入',
    cyclePhase: '流量见顶，AI驱动新增长',
    policyEnv: '平台经济常态化监管',
    competitiveLandscape: 'BAT格局变化，字节、拼多多崛起',
  },
  '港股地产': {
    characteristics: '高杠杆、强周期、政策敏感',
    keyMetrics: '销售额、去化率、融资成本',
    cyclePhase: '行业出清，销售低迷',
    policyEnv: '需求端放松，供给端风险化解',
    competitiveLandscape: '国央企主导，民企出清',
  },
  '港股金融': {
    characteristics: '受内地和港股双重影响',
    keyMetrics: '同A股/港股金融',
    cyclePhase: '同A股/港股金融',
    policyEnv: '同A股/港股金融',
    competitiveLandscape: '同A股/港股金融',
  },
  '港股消费': {
    characteristics: '内地消费+港股市场流动性',
    keyMetrics: '同A股消费+港股估值折价',
    cyclePhase: '同A股消费',
    policyEnv: '同A股消费',
    competitiveLandscape: '同A股消费',
  },
  '美股科技': {
    characteristics: '全球领先、创新驱动、估值高',
    keyMetrics: '营收增速、毛利率、FCF、AI投入',
    cyclePhase: 'AI投资高峰，云业务分化',
    policyEnv: '反垄断、AI监管、出口管制',
    competitiveLandscape: 'MAG7主导，初创公司融资困难',
  },
  '美股金融': {
    characteristics: '全球金融中心、监管成熟',
    keyMetrics: 'ROE、净息差、AUM、交易收入',
    cyclePhase: '利率高位，投行复苏',
    policyEnv: '巴塞尔III最终版、压力测试',
    competitiveLandscape: '摩根大通、高盛主导',
  },
  '美股消费': {
    characteristics: '品牌力强、全球布局',
    keyMetrics: '同店增长、毛利率、全球收入占比',
    cyclePhase: '消费韧性，但低收入群体承压',
    policyEnv: '关税政策不确定性',
    competitiveLandscape: '品牌集中，DTC模式兴起',
  },
  '美股医药': {
    characteristics: '研发驱动、专利悬崖、并购活跃',
    keyMetrics: '管线进展、专利到期、并购整合',
    cyclePhase: 'GLP-1爆发，ADC兴起',
    policyEnv: '药价谈判、IRA法案',
    competitiveLandscape: '大型药企主导，Biotech被收购',
  },
}

function getIndustryInsight(sector: string | null, industry: string | null, market: string): typeof INDUSTRY_INSIGHTS[string] | null {
  const key = (sector || industry || '')
  // 直接匹配
  if (INDUSTRY_INSIGHTS[key]) return INDUSTRY_INSIGHTS[key]
  // 模糊匹配
  for (const [k, v] of Object.entries(INDUSTRY_INSIGHTS)) {
    if (key.includes(k) || k.includes(key)) return v
  }
  // 按市场匹配通用行业
  if (market === 'hk') {
    if (key.includes('地产') || key.includes('建筑')) return INDUSTRY_INSIGHTS['港股地产']
    if (key.includes('金融') || key.includes('银行') || key.includes('保险')) return INDUSTRY_INSIGHTS['港股金融']
    if (key.includes('消费') || key.includes('零售') || key.includes('食品')) return INDUSTRY_INSIGHTS['港股消费']
  }
  if (market === 'us') {
    if (key.includes('科技') || key.includes('软件') || key.includes('半导体')) return INDUSTRY_INSIGHTS['美股科技']
    if (key.includes('金融') || key.includes('银行')) return INDUSTRY_INSIGHTS['美股金融']
    if (key.includes('消费') || key.includes('零售')) return INDUSTRY_INSIGHTS['美股消费']
    if (key.includes('医药') || key.includes('生物')) return INDUSTRY_INSIGHTS['美股医药']
  }
  return null
}

// ===== 估值分析引擎 =====

function analyzeValuation(pe: number | null): {
  level: string
  detail: string
  scoreImpact: number
} {
  if (pe === null || pe === undefined) {
    return {
      level: '无法评估',
      detail: '缺乏PE数据，无法对估值水平做出判断。建议结合PB、PS等其他估值指标综合分析。',
      scoreImpact: 0,
    }
  }

  if (pe < 0) {
    return {
      level: '亏损状态',
      detail: `当前市盈率为负（${pe.toFixed(2)}倍），表明公司最近12个月处于亏损状态。传统PE估值框架失效，需改用PB、PS或EV/EBITDA等指标。亏损可能源于行业周期底部、一次性减值或经营恶化，需深入分析亏损原因和扭亏路径。`,
      scoreImpact: -20,
    }
  }

  if (pe < 5) {
    return {
      level: '极度低估',
      detail: `当前PE仅${pe.toFixed(1)}倍，显著低于市场平均水平，甚至低于许多成熟行业的合理估值下限。这种极端低估值通常意味着市场认为公司面临严重的经营困境、行业衰退或治理问题。除非有明确的催化剂，否则低估值可能长期持续。`,
      scoreImpact: 10,
    }
  }

  if (pe < 8) {
    return {
      level: '显著低估',
      detail: `当前PE约${pe.toFixed(1)}倍，处于历史估值底部区域。低估值可能反映市场对盈利可持续性的担忧，或行业处于周期低谷。对于现金流稳健、分红稳定的公司，当前估值提供了较高的安全边际。但需警惕盈利下滑导致"估值陷阱"。`,
      scoreImpact: 15,
    }
  }

  if (pe < 12) {
    return {
      level: '合理偏低',
      detail: `当前PE约${pe.toFixed(1)}倍，处于合理偏低区间。相比市场平均15-20倍的估值水平，当前价格具备一定的安全边际。适合风险偏好较低、追求稳定回报的投资者。若未来盈利改善或市场情绪回暖，存在估值修复空间。`,
      scoreImpact: 10,
    }
  }

  if (pe < 18) {
    return {
      level: '合理估值',
      detail: `当前PE约${pe.toFixed(1)}倍，处于市场合理估值中枢附近。价格基本反映了公司当前的盈利能力和增长预期，不存在明显的低估或高估。投资决策应更多基于公司基本面改善、行业景气度变化或结构性机会。`,
      scoreImpact: 0,
    }
  }

  if (pe < 25) {
    return {
      level: '合理偏高',
      detail: `当前PE约${pe.toFixed(1)}倍，略高于市场平均水平。估值中已计入一定的增长预期，要求公司未来保持较好的盈利增速以支撑当前股价。若增长不及预期，股价可能面临估值压缩风险。`,
      scoreImpact: -5,
    }
  }

  if (pe < 35) {
    return {
      level: '估值偏高',
      detail: `当前PE约${pe.toFixed(1)}倍，估值偏高。市场已计入较高的增长预期，要求公司未来数年保持20%以上的盈利复合增速。高估值对业绩兑现的要求极为苛刻，一旦增速放缓或行业景气度下行，估值压缩风险显著。`,
      scoreImpact: -15,
    }
  }

  if (pe < 50) {
    return {
      level: '显著高估',
      detail: `当前PE约${pe.toFixed(1)}倍，估值显著偏高。这种估值水平通常只适用于高成长、高壁垒的稀缺标的，且要求未来数年保持30%以上的复合增速。当前价格可能已透支未来3-5年的增长，投资风险收益比不佳。`,
      scoreImpact: -25,
    }
  }

  return {
    level: '极度高估',
    detail: `当前PE高达${pe.toFixed(1)}倍，处于极度高估状态。这种估值水平往往出现在泡沫期或概念炒作阶段，需要公司保持超高速增长才能支撑。历史经验表明，极端高估值最终都会向均值回归，投资者应保持高度警惕。`,
    scoreImpact: -35,
  }
}

function analyzePricePosition(price: number | null, profitLine: number | null, upside: number | null): {
  position: string
  detail: string
  scoreImpact: number
} {
  if (price === null || profitLine === null || upside === null) {
    return {
      position: '无法判断',
      detail: '缺乏利润线数据，无法判断股价相对于合理估值的位置。',
      scoreImpact: 0,
    }
  }

  if (upside > 100) {
    return {
      position: '深度低估',
      detail: `当前股价${price.toFixed(2)}元，远低于利润线${profitLine.toFixed(2)}元，折价幅度高达${upside.toFixed(1)}%。这种极端折价通常意味着市场认为公司盈利不可持续或面临重大风险。若盈利基本面稳固，则存在巨大的估值修复空间；但若盈利确实恶化，则可能陷入"价值陷阱"。`,
      scoreImpact: 20,
    }
  }

  if (upside > 50) {
    return {
      position: '显著低估',
      detail: `当前股价${price.toFixed(2)}元，较利润线${profitLine.toFixed(2)}元折价${upside.toFixed(1)}%。股价已充分反映悲观预期，若盈利维持或小幅改善，存在较大的估值修复弹性。适合逆向投资者布局，但需确认盈利底是否已现。`,
      scoreImpact: 15,
    }
  }

  if (upside > 20) {
    return {
      position: '适度低估',
      detail: `当前股价${price.toFixed(2)}元，较利润线${profitLine.toFixed(2)}元折价${upside.toFixed(1)}%。估值偏低但非极端，具备一定的安全边际。未来收益将来自估值修复和盈利增长的双重驱动。`,
      scoreImpact: 10,
    }
  }

  if (upside > -10) {
    return {
      position: '接近合理',
      detail: `当前股价${price.toFixed(2)}元，接近利润线${profitLine.toFixed(2)}元（差距${upside.toFixed(1)}%）。估值基本合理，未来收益主要来自盈利增长而非估值扩张。需关注公司能否维持或提升盈利能力。`,
      scoreImpact: 0,
    }
  }

  if (upside > -30) {
    return {
      position: '适度高估',
      detail: `当前股价${price.toFixed(2)}元，已高于利润线${profitLine.toFixed(2)}元（溢价${Math.abs(upside).toFixed(1)}%）。估值偏高，当前价格可能已计入部分乐观预期。未来需盈利持续增长以支撑股价，否则面临回调风险。`,
      scoreImpact: -10,
    }
  }

  return {
    position: '显著高估',
    detail: `当前股价${price.toFixed(2)}元，显著高于利润线${profitLine.toFixed(2)}元（溢价${Math.abs(upside).toFixed(1)}%）。股价已透支正常盈利水平，存在较大的估值回归风险。除非盈利出现爆发式增长，否则当前位置风险收益比不佳。`,
    scoreImpact: -20,
  }
}

function analyzeProfitQuality(quality: number | null, qualitySummary: string | null): {
  assessment: string
  detail: string
  scoreImpact: number
} {
  if (quality === null || quality === undefined) {
    return {
      assessment: '未知',
      detail: '缺乏利润质量评分，无法评估盈利可持续性。建议关注现金流与净利润的匹配度、非经常性损益占比、应收账款变化等指标。',
      scoreImpact: 0,
    }
  }

  if (quality < 30) {
    return {
      assessment: '极差',
      detail: `利润质量评分仅${quality}分，处于极低水平。${qualitySummary || '盈利可能大量依赖非经常性损益、资产处置收益或会计估计变更，主营业务造血能力存疑。现金流与净利润严重背离，盈利可持续性极差。'}`,
      scoreImpact: -20,
    }
  }

  if (quality < 45) {
    return {
      assessment: '较差',
      detail: `利润质量评分${quality}分，处于较低水平。${qualitySummary || '盈利中存在较多一次性因素或异常科目，主营业务盈利能力可能被高估。需仔细分析利润表各科目，识别非经常性项目。'}`,
      scoreImpact: -10,
    }
  }

  if (quality < 60) {
    return {
      assessment: '一般',
      detail: `利润质量评分${quality}分，处于中等水平。${qualitySummary || '盈利来源基本合理，但可能存在一定的季节性波动、应收账款增长或毛利率波动。整体盈利质量尚可，但需持续跟踪。'}`,
      scoreImpact: -5,
    }
  }

  if (quality < 75) {
    return {
      assessment: '良好',
      detail: `利润质量评分${quality}分，处于较好水平。${qualitySummary || '盈利来源较为扎实，现金流与净利润匹配度较高，非经常性损益占比较低。主营业务盈利能力稳健。'}`,
      scoreImpact: 5,
    }
  }

  return {
    assessment: '优秀',
    detail: `利润质量评分${quality}分，处于优秀水平。${qualitySummary || '盈利质量高，现金流充裕，盈利来源清晰且可持续。公司具备较强的主营业务造血能力。'}`,
    scoreImpact: 10,
  }
}

// ===== 主分析生成函数 =====

function generateProfessionalAnalysis(company: CompanyData): {
  summary: string
  thesis: string
  catalysts: string
  risks: string
  score: number
  confidence: number
  tags: string[]
} {
  const { name, symbol, market, sector, industry, pe, price, profitLine, upside, eps, profitQualityScore, profitQualitySummary } = company

  // 获取行业洞察
  const industryInsight = getIndustryInsight(sector, industry, market)

  // 估值分析
  const valuationAnalysis = analyzeValuation(pe)

  // 价格位置分析
  const priceAnalysis = analyzePricePosition(price, profitLine, upside)

  // 利润质量分析
  const qualityAnalysis = analyzeProfitQuality(profitQualityScore, profitQualitySummary)

  // 计算综合评分
  let score = 50 + valuationAnalysis.scoreImpact + priceAnalysis.scoreImpact + qualityAnalysis.scoreImpact

  score = Math.round(Math.max(0, Math.min(100, score)))

  // 置信度（仅基于数据完整度，不惩罚特定指标值）
  let confidence = 70
  if (pe === null) confidence -= 15
  if (profitLine === null) confidence -= 10
  if (profitQualityScore === null) confidence -= 10
  confidence = Math.round(Math.max(40, Math.min(95, confidence)))

  // 生成摘要（估值水平 + 未来展望 + 买入建议）
  let summary = ''

  // 估值水平
  summary += `${name}（${symbol}.${market.toUpperCase()}）当前估值水平${valuationAnalysis.level}。${valuationAnalysis.detail} `

  // 价格位置
  summary += `从利润线角度看，${priceAnalysis.detail} `

  // 利润质量
  summary += `盈利质量方面，${qualityAnalysis.detail} `

  // 行业视角
  if (industryInsight) {
    summary += `行业层面，${name}所属${sector || industry}行业${industryInsight.characteristics}。${industryInsight.cyclePhase}。`
  }

  // 买入建议
  if (score >= 75) {
    summary += `综合评估，当前具备较好的投资价值。估值偏低且盈利质量尚可，适合价值型投资者分批建仓。建议关注季度盈利变化和行业政策动向，若盈利拐点确认可加大仓位。`
  } else if (score >= 60) {
    summary += `综合评估，当前具备一定的投资吸引力。估值合理偏低，但需关注盈利持续性。建议小额试探性建仓，等待基本面进一步明朗后再决定是否加仓。`
  } else if (score >= 45) {
    summary += `综合评估，当前估值基本合理但缺乏明显安全边际。建议观望为主，等待更好的入场时机或盈利改善信号。已持仓者可继续持有，但不宜追高。`
  } else if (score >= 30) {
    summary += `综合评估，当前风险收益比不佳。估值偏高或盈利质量存疑，不建议新建仓位。已持仓者建议考虑减仓或设置止损。`
  } else {
    summary += `综合评估，当前不建议买入。估值过高、盈利质量差或行业前景黯淡，投资风险较大。建议回避，等待基本面显著改善后再评估。`
  }

  // 投资论点
  const thesis = `核心观点：${name}当前PE${pe ? pe.toFixed(1) : 'N/A'}倍，${valuationAnalysis.level}；股价较利润线${upside !== null ? upside.toFixed(1) + '%' : 'N/A'}，${priceAnalysis.position}；利润质量${qualityAnalysis.assessment}。综合评分${score}分，${score >= 60 ? '具备配置价值' : score >= 45 ? '观望为主' : '保持谨慎'}。`

  // 催化剂
  const catalysts = generateCatalysts(company, industryInsight)

  // 风险
  const risks = generateRisks(company, industryInsight)

  // 标签
  const tags = generateTags(company, valuationAnalysis.level, priceAnalysis.position, qualityAnalysis.assessment)

  return { summary, thesis, catalysts, risks, score, confidence, tags }
}

function generateCatalysts(company: CompanyData, insight: typeof INDUSTRY_INSIGHTS[string] | null): string {
  const catalysts: string[] = []
  const { sector, upside, pe } = company
  const sectorLower = (sector || '').toLowerCase()

  // 通用催化剂
  if (upside !== null && upside > 20) {
    catalysts.push(`估值修复：当前股价较利润线存在${upside.toFixed(1)}%的折价，若市场情绪回暖或盈利预期改善，存在较大的估值修复空间`)
  }
  if (pe !== null && pe < 10) {
    catalysts.push(`估值回归：当前PE仅${pe.toFixed(1)}倍，处于历史低位，若行业景气度回升或公司基本面改善，估值有望向中枢回归`)
  }

  // 行业特定催化剂
  if (insight) {
    if (sectorLower.includes('银行')) {
      catalysts.push('净息差企稳：若货币政策边际宽松或存款利率下调，银行净息差有望止跌回升')
      catalysts.push('资产质量改善：宏观经济复苏带动企业偿债能力增强，不良贷款生成率下降')
    } else if (sectorLower.includes('保险')) {
      catalysts.push('负债端复苏：储蓄型保险产品需求旺盛，带动新业务价值增长')
      catalysts.push('投资收益改善：资本市场回暖提升险资投资收益率，缓解利差损压力')
    } else if (sectorLower.includes('白酒')) {
      catalysts.push('批价回升：高端白酒批价企稳回升，渠道库存去化，动销改善')
      catalysts.push('宴席复苏：婚宴、商务宴请等场景恢复，带动次高端白酒需求')
    } else if (sectorLower.includes('医药')) {
      catalysts.push('创新药出海：核心产品海外授权或获批，打开成长天花板')
      catalysts.push('管线突破：关键临床数据读出或新药获批，驱动估值重构')
    } else if (sectorLower.includes('半导体')) {
      catalysts.push('周期复苏：全球半导体周期触底回升，存储、晶圆代工价格回暖')
      catalysts.push('国产替代：关键设备材料国产化率提升，份额向国内龙头集中')
    } else if (sectorLower.includes('新能源')) {
      catalysts.push('产能出清：行业产能过剩缓解，价格战趋缓，龙头盈利修复')
      catalysts.push('技术迭代：新技术路线（如BC电池、固态电池）商业化加速')
    } else if (sectorLower.includes('地产') || sectorLower.includes('建筑')) {
      catalysts.push('政策放松：限购限贷进一步放松，房贷利率下调刺激需求')
      catalysts.push('融资改善：房企融资"白名单"扩容，优质房企流动性压力缓解')
    } else if (sectorLower.includes('消费')) {
      catalysts.push('消费复苏：居民收入预期改善，消费信心回升带动同店增长')
      catalysts.push('渠道变革：新零售模式（直播电商、会员店）带来增量空间')
    } else if (sectorLower.includes('科技') || sectorLower.includes('互联网')) {
      catalysts.push('AI落地：AI应用商业化加速，带动收入和利润增长')
      catalysts.push('政策缓和：平台经济监管常态化，政策不确定性下降')
    } else if (sectorLower.includes('能源') || sectorLower.includes('煤炭')) {
      catalysts.push('煤价上涨：供需偏紧支撑煤价高位，盈利保持韧性')
      catalysts.push('分红提升：高现金流支撑高比例分红，提升股东回报')
    } else if (sectorLower.includes('汽车')) {
      catalysts.push('新能源渗透：新能源车销量超预期，智能化配置率提升')
      catalysts.push('出口增长：中国汽车出口量持续增长，全球化布局加速')
    } else {
      catalysts.push('行业景气度回升：宏观经济复苏带动行业需求改善')
      catalysts.push('竞争格局优化：中小企业出清，龙头份额提升')
    }
  }

  return catalysts.slice(0, 3).join('；')
}

function generateRisks(company: CompanyData, insight: typeof INDUSTRY_INSIGHTS[string] | null): string {
  const risks: string[] = []
  const { sector, pe, upside, profitQualityScore } = company
  const sectorLower = (sector || '').toLowerCase()

  // 估值风险
  if (pe !== null && pe < 0) {
    risks.push('持续亏损：公司处于亏损状态，若无法扭亏，面临退市或重组风险')
  }
  if (upside !== null && upside < -30) {
    risks.push('估值回归：股价显著高于利润线，若盈利增速放缓，面临较大的估值压缩风险')
  }

  // 盈利质量风险
  if (profitQualityScore !== null && profitQualityScore < 45) {
    risks.push(`盈利质量差：利润质量评分仅${profitQualityScore}分，盈利可持续性存疑，可能存在一次性收益或会计调节`)
  }

  // 行业风险
  if (insight) {
    if (sectorLower.includes('银行')) {
      risks.push('净息差压缩：利率下行周期中，银行净息差持续承压，拖累盈利增长')
      risks.push('信用风险：宏观经济下行可能导致企业违约增加，不良贷款率上升')
    } else if (sectorLower.includes('保险')) {
      risks.push('利差损风险：低利率环境下，存量高预定利率保单面临利差损压力')
      risks.push('资本市场波动：权益投资占比高，股市下跌将直接影响净利润')
    } else if (sectorLower.includes('白酒')) {
      risks.push('需求疲软：商务宴请减少、消费降级可能压制高端白酒需求')
      risks.push('库存积压：渠道库存高企，若动销不畅可能引发价格战')
    } else if (sectorLower.includes('医药')) {
      risks.push('集采降价：创新药和器械面临医保谈判降价压力，压缩利润空间')
      risks.push('研发失败：新药研发周期长、投入大，关键临床失败将重创估值')
    } else if (sectorLower.includes('半导体')) {
      risks.push('周期下行：全球半导体周期波动大，若复苏不及预期，盈利承压')
      risks.push('出口管制：关键设备和材料出口管制收紧，制约先进制程发展')
    } else if (sectorLower.includes('新能源')) {
      risks.push('产能过剩：光伏、锂电等环节产能过剩，价格战侵蚀利润')
      risks.push('技术迭代：新技术路线可能颠覆现有格局，投资面临技术路线风险')
    } else if (sectorLower.includes('地产') || sectorLower.includes('建筑')) {
      risks.push('销售低迷：居民购房意愿低迷，销售回款困难，现金流承压')
      risks.push('债务违约：高杠杆房企面临债务到期压力，存在违约风险')
    } else if (sectorLower.includes('消费')) {
      risks.push('消费降级：居民收入增长放缓，消费意愿下降，影响同店增长')
      risks.push('成本上涨：原材料、人工、租金成本上升，压缩毛利率')
    } else if (sectorLower.includes('科技') || sectorLower.includes('互联网')) {
      risks.push('监管风险：数据安全、反垄断等监管政策可能带来合规成本')
      risks.push('竞争加剧：行业竞争激烈，用户增长见顶，变现效率下降')
    } else if (sectorLower.includes('能源') || sectorLower.includes('煤炭')) {
      risks.push('煤价下跌：若供需格局逆转，煤价大幅下跌将直接影响盈利')
      risks.push('政策调控：保供稳价政策可能限制煤价上涨空间')
    } else if (sectorLower.includes('汽车')) {
      risks.push('价格战：新能源车价格战激烈，毛利率持续承压')
      risks.push('需求放缓：汽车消费进入存量时代，销量增长放缓')
    } else {
      risks.push('宏观经济下行：经济放缓压制行业需求，影响公司营收增长')
      risks.push('行业竞争加剧：新进入者增加或现有竞争者扩张，压缩利润空间')
    }
  }

  return risks.slice(0, 3).join('；')
}

function generateTags(
  company: CompanyData,
  valuationLevel: string,
  pricePosition: string,
  qualityAssessment: string,
): string[] {
  const tags: string[] = []
  const { sector, pe, upside } = company

  if (sector) tags.push(sector)

  // 估值标签
  if (pe !== null) {
    if (pe < 0) tags.push('亏损股')
    else if (pe < 8) tags.push('深度价值')
    else if (pe < 12) tags.push('低估值')
    else if (pe > 30) tags.push('高估值')
    else if (pe > 20) tags.push('成长型')
  }

  // 价格位置标签
  if (upside !== null) {
    if (upside > 50) tags.push('深度折价')
    else if (upside > 20) tags.push('估值修复')
    else if (upside < -20) tags.push('溢价风险')
  }

  // 质量标签
  if (qualityAssessment === '极差' || qualityAssessment === '较差') {
    tags.push('盈利存疑')
  }

  return tags.length > 0 ? tags : ['待分析']
}

// ===== 批量处理主函数 =====

async function main() {
  console.log('开始查找需要重新生成专业分析的公司...')

  // 获取所有短格式 exploration
  const allExplorations = await prisma.companyExploration.findMany({
    where: { visibility: 'published' },
    include: {
      company: {
        include: {
          valuations: {
            orderBy: { asOfDate: 'desc' },
            take: 1,
          },
        },
      },
    },
  })

  const shortFormat = allExplorations.filter(e => {
    const s = e.summary || ''
    return s.startsWith('分数') && s.includes('PE百分位')
  })

  console.log(`找到 ${shortFormat.length} 家需要重新分析的公司`)

  if (shortFormat.length === 0) {
    console.log('所有公司均已具备专业分析，无需处理')
    await prisma.$disconnect()
    return
  }

  let processedCount = 0
  let errorCount = 0

  for (const exploration of shortFormat) {
    const company = exploration.company
    const valuation = company.valuations[0]

    if (!valuation) {
      console.log(`跳过 ${company.name}：无估值快照`)
      continue
    }

    const companyData: CompanyData = {
      id: company.id,
      symbol: company.symbol,
      market: company.market,
      name: company.name,
      sector: company.sector,
      industry: company.industry,
      pe: valuation.ttmPe,
      price: valuation.price,
      profitLine: valuation.profitLinePrice,
      referenceLine: valuation.referenceLinePrice,
      upside: valuation.upsideToProfitLine,
      refUpside: valuation.upsideToReferenceLine,
      eps: valuation.ttmEps,
      profitQualityScore: valuation.profitQualityScore,
      profitQualitySummary: valuation.profitQualitySummary,
      marketCap: valuation.marketCap,
      explorationId: exploration.id,
      currentScore: exploration.score,
      currentSummary: exploration.summary,
    }

    console.log(`\n[${processedCount + 1}/${shortFormat.length}] ${company.name} (${company.symbol})`)
    console.log(`  PE=${companyData.pe?.toFixed(2) || 'N/A'}, 上行=${companyData.upside?.toFixed(1) || 'N/A'}%, 质量=${companyData.profitQualityScore || 'N/A'}`)

    try {
      // 生成专业分析
      const analysis = generateProfessionalAnalysis(companyData)

      // 更新 exploration
      await prisma.companyExploration.update({
        where: { id: exploration.id },
        data: {
          title: `${company.name} 估值分析与投资建议`,
          summary: analysis.summary,
          thesis: analysis.thesis,
          catalysts: analysis.catalysts,
          risks: analysis.risks,
          tags: JSON.stringify(analysis.tags),
          score: analysis.score,
          confidence: analysis.confidence,
        },
      })

      console.log(`  ✓ 更新成功，新评分=${analysis.score}，置信度=${analysis.confidence}`)
      processedCount++
    } catch (error) {
      console.error(`  ✗ 处理失败: ${company.name}`, error)
      errorCount++
    }
  }

  console.log(`\n========================================`)
  console.log(`批量分析完成`)
  console.log(`总处理公司数: ${shortFormat.length}`)
  console.log(`成功更新: ${processedCount}`)
  console.log(`失败: ${errorCount}`)
  console.log(`========================================`)
}

main()
  .then(async () => {
    await prisma.$disconnect()
    process.exit(0)
  })
  .catch(async (error) => {
    console.error('脚本执行失败:', error)
    await prisma.$disconnect()
    process.exit(1)
  })
