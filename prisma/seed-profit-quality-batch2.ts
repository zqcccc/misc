import { PrismaClient } from '@prisma/client'

const prisma = new PrismaClient()

// 批量处理数据 - 基于行业特征和公开财报
const profitQualityBatch2: Array<{
  symbol: string
  market: string
  title: string
  isRecurring: boolean
  explanationTitle: string
  explanationBody: string
  confidence: number
}> = [
  // 家电
  { symbol: '000651', market: 'cn', title: '格力电器', isRecurring: true, explanationTitle: '空调主业利润，扣非占比约94%', explanationBody: '2024年归母净利润321.8亿元，扣非后归母净利润约301亿元，扣非占比约94%。非经常性损益主要来自资产处置和投资收益。空调主业盈利稳定，利润质量正常。', confidence: 85 },
  
  // 电信
  { symbol: '00762', market: 'hk', title: '中国联通', isRecurring: true, explanationTitle: '电信运营主业利润，Q4扣非亏损需关注', explanationBody: '2024年归母净利润90.3亿元，扣非净利润66.99亿元。虽然全年利润正增长，但Q4单季扣非净利罕见亏损，且扣非同比下降10.6%。电信主业利润质量正常偏谨慎。', confidence: 72 },
  { symbol: '600050', market: 'cn', title: '中国联通', isRecurring: true, explanationTitle: '电信运营主业利润，Q4扣非亏损需关注', explanationBody: '2024年归母净利润90.3亿元，扣非净利润66.99亿元。虽然全年利润正增长，但Q4单季扣非净利罕见亏损。电信主业利润质量正常偏谨慎。', confidence: 72 },
  
  // 建筑
  { symbol: '601668', market: 'cn', title: '中国建筑', isRecurring: true, explanationTitle: '建筑地产主业利润，受地产调整影响', explanationBody: '2024年归母净利润461.87亿元，同比下降14.9%。受房地产行业调整影响，但建筑主业仍稳定。利润质量正常偏谨慎。', confidence: 72 },
  
  // 银行
  { symbol: '002958', market: 'cn', title: '青农商行', isRecurring: false, explanationTitle: '农商行，利润含投资收益', explanationBody: '农商行利润主要来自利息收入。需关注区域资产质量和不良贷款率。利润质量正常偏谨慎。', confidence: 68 },
  { symbol: '002936', market: 'cn', title: '郑州银行', isRecurring: false, explanationTitle: '城商行，利润含投资收益', explanationBody: '城商行利润主要来自利息收入和投资收益。需关注区域资产质量和不良贷款率。利润质量正常偏谨慎。', confidence: 68 },
  { symbol: '601818', market: 'cn', title: '光大银行', isRecurring: false, explanationTitle: '股份制银行，利润含投资收益', explanationBody: '股份制银行利润主要来自利息收入和投资收益。需关注资产质量和利率风险。利润质量正常偏谨慎。', confidence: 70 },
  { symbol: '601166', market: 'cn', title: '兴业银行', isRecurring: false, explanationTitle: '股份制银行，利润含投资收益', explanationBody: '股份制银行利润主要来自利息收入和投资收益。需关注资产质量和利率风险。利润质量正常偏谨慎。', confidence: 70 },
  { symbol: '601601', market: 'cn', title: '新华保险', isRecurring: true, explanationTitle: '寿险主业利润', explanationBody: '新华保险主营寿险业务，利润主要来自保费收入和投资回报。需关注代理人队伍和投资波动。利润质量正常。', confidence: 75 },
  { symbol: '01336', market: 'hk', title: '新华保险', isRecurring: true, explanationTitle: '寿险主业利润', explanationBody: '新华保险主营寿险业务，利润主要来自保费收入和投资回报。需关注代理人队伍和投资波动。利润质量正常。', confidence: 75 },
  
  // 保险
  { symbol: '02628', market: 'hk', title: '中国人寿', isRecurring: true, explanationTitle: '寿险主业利润，收益率波动', explanationBody: '中国人寿主营寿险，利润来自保费收入和投资收益。2024年受资本市场波动影响，投资收益有所下降。利润质量正常。', confidence: 76 },
  { symbol: '02318', market: 'hk', title: '中国平安', isRecurring: true, explanationTitle: '寿险+银行+投资综合利润', explanationBody: '中国平安为综合金融集团，利润来自寿险、银行及投资业务。综合金融模式分散风险，利润质量正常。', confidence: 78 },
  { symbol: '601318', market: 'cn', title: '中国平安', isRecurring: true, explanationTitle: '寿险+银行+投资综合利润', explanationBody: '中国平安为综合金融集团，利润来自寿险、银行及投资业务。综合金融模式分散风险，利润质量正常。', confidence: 78 },
  { symbol: '00966', market: 'hk', title: '中国太平', isRecurring: true, explanationTitle: '寿险主业利润', explanationBody: '中国太平主营寿险业务，利润来自保费收入和投资收益。利润质量正常。', confidence: 75 },
  
  // 证券
  { symbol: '600030', market: 'cn', title: '中信证券', isRecurring: true, explanationTitle: '券商主业利润，受市场波动影响', explanationBody: '中信证券为券商龙头，利润来自经纪、投行和资管业务。2024年受市场成交萎缩影响，但龙头地位稳固。利润质量正常。', confidence: 78 },
  { symbol: '601688', market: 'cn', title: '华泰证券', isRecurring: true, explanationTitle: '券商主业利润，受市场波动影响', explanationBody: '华泰证券为头部券商，利润来自经纪、投行和资管业务。财富管理转型持续推进。利润质量正常。', confidence: 76 },
  { symbol: '000776', market: 'cn', title: '广发证券', isRecurring: true, explanationTitle: '券商主业利润，受市场波动影响', explanationBody: '广发证券为头部券商，利润来自经纪、投行和资管业务。易方达基金贡献投资收益。利润质量正常。', confidence: 76 },
  { symbol: '000783', market: 'cn', title: '长江证券', isRecurring: true, explanationTitle: '券商主业利润', explanationBody: '长江证券为区域券商，利润来自经纪和投行业务。利润质量正常。', confidence: 72 },
  
  // 白酒
  { symbol: '600519', market: 'cn', title: '贵州茅台', isRecurring: true, explanationTitle: '高端白酒主业利润，现金流极佳', explanationBody: '贵州茅台主营高端白酒，利润主要来自茅台酒销售。预收账款充足，现金流极佳。利润质量极佳。', confidence: 92 },
  { symbol: '000568', market: 'cn', title: '泸州老窖', isRecurring: true, explanationTitle: '高端白酒主业利润', explanationBody: '泸州老窖主营高端白酒，利润来自酒类销售。品牌力强，利润质量正常。', confidence: 85 },
  { symbol: '600809', market: 'cn', title: '山西汾酒', isRecurring: true, explanationTitle: '清香白酒主业利润', explanationBody: '山西汾酒主营清香型白酒，利润来自酒类销售。省外扩张持续，增长态势良好。利润质量正常。', confidence: 82 },
  { symbol: '600600', market: 'cn', title: '青岛啤酒', isRecurring: true, explanationTitle: '啤酒主业利润', explanationBody: '青岛啤酒主营啤酒销售，利润来自产品销售。高端化战略持续推进。利润质量正常。', confidence: 80 },
  { symbol: '600132', market: 'cn', title: '重庆啤酒', isRecurring: true, explanationTitle: '啤酒主业利润', explanationBody: '重庆啤酒主营啤酒销售，利润来自产品销售。乌苏啤酒全国化扩张中。利润质量正常。', confidence: 78 },
  
  // 食品
  { symbol: '002216', market: 'cn', title: '三全食品', isRecurring: true, explanationTitle: '速冻食品主业利润', explanationBody: '三全食品主营速冻食品，利润来自产品销售。餐饮渠道持续开拓。利润质量正常。', confidence: 78 },
  { symbol: '002959', market: 'cn', title: '小熊电器', isRecurring: true, explanationTitle: '小家电主业利润', explanationBody: '小熊电器主营创意小家电，利润来自产品销售。电商渠道优势明显。利润质量正常。', confidence: 76 },
  { symbol: '603345', market: 'cn', title: '安井食品', isRecurring: true, explanationTitle: '速冻食品主业利润', explanationBody: '安井食品主营速冻火锅料和预制菜，利润来自产品销售。行业龙头地位稳固。利润质量正常。', confidence: 82 },
  { symbol: '603317', market: 'cn', title: '天味食品', isRecurring: true, explanationTitle: '复合调味品主业利润', explanationBody: '天味食品主营火锅底料和川菜调料，利润来自产品销售。大单品策略成效显著。利润质量正常。', confidence: 78 },
  
  // 乳品
  { symbol: '600887', market: 'cn', title: '伊利股份', isRecurring: true, explanationTitle: '乳制品主业利润', explanationBody: '伊利股份主营乳制品，利润来自产品销售。原奶价格下行改善毛利率。利润质量正常。', confidence: 82 },
  
  // 农业养殖
  { symbol: '002299', market: 'cn', title: '圣农发展', isRecurring: true, explanationTitle: '白羽肉鸡养殖主业利润', explanationBody: '圣农发展主营白羽肉鸡养殖和加工，利润来自鸡肉销售。养殖周期波动影响盈利。利润质量正常。', confidence: 72 },
  
  // 互联网科技
  { symbol: '09988', market: 'hk', title: '阿里巴巴-W', isRecurring: true, explanationTitle: '电商云计算主业利润', explanationBody: '阿里巴巴主营电商和云计算，利润来自核心商业和云业务。电商竞争加剧但龙头地位稳固。利润质量正常。', confidence: 80 },
  { symbol: '01024', market: 'hk', title: '快手-W', isRecurring: true, explanationTitle: '短视频电商主业利润', explanationBody: '快手主营短视频和直播电商，利润来自广告和电商佣金。盈利能力持续改善。利润质量正常。', confidence: 72 },
  { symbol: '03660', market: 'hk', title: '奇富科技-S', isRecurring: true, explanationTitle: '金融科技主业利润', explanationBody: '奇富科技主营金融科技服务，利润来自助贷业务。利润质量正常。', confidence: 70 },
  { symbol: '09890', market: 'hk', title: '贪玩', isRecurring: true, explanationTitle: '游戏主业利润', explanationBody: '贪玩从事游戏研发和运营，利润来自游戏收入。利润质量正常。', confidence: 68 },
  { symbol: '03700', market: 'hk', title: '映宇宙', isRecurring: true, explanationTitle: '直播社交主业利润', explanationBody: '映宇宙主营直播社交业务，利润来自直播打赏和社交。利润质量正常。', confidence: 68 },
  
  // 美国科技股
  { symbol: 'MSFT', market: 'us', title: 'MICROSOFT CORP', isRecurring: true, explanationTitle: '软件云服务主业利润', explanationBody: '微软主营软件和云服务，利润来自Windows、Office和Azure云。全球科技龙头，利润质量极佳。', confidence: 92 },
  { symbol: 'META', market: 'us', title: 'Meta Platforms, Inc.', isRecurring: true, explanationTitle: '社交广告主业利润', explanationBody: 'Meta主营社交网络和广告，利润主要来自Facebook和Instagram广告。AI投资加大但广告业务强劲。利润质量正常。', confidence: 85 },
  { symbol: 'AMZN', market: 'us', title: 'AMAZON COM INC', isRecurring: true, explanationTitle: '电商云服务主业利润', explanationBody: '亚马逊主营电商和AWS云服务，利润来自零售和云业务。AWS利润丰厚，电商竞争激烈但规模优势明显。利润质量正常。', confidence: 85 },
  { symbol: 'GOOGL', market: 'us', title: 'Alphabet Inc.', isRecurring: true, explanationTitle: '搜索广告云服务主业利润', explanationBody: '谷歌主营搜索广告和云服务，利润来自Google Ads和Google Cloud。AI投入加大但搜索广告依然强劲。利润质量极佳。', confidence: 90 },
  { symbol: 'CRM', market: 'us', title: 'Salesforce, Inc.', isRecurring: true, explanationTitle: 'SaaS云服务主业利润', explanationBody: 'Salesforce主营企业SaaS服务，利润来自订阅收入。利润率持续改善。利润质量正常。', confidence: 82 },
  { symbol: 'ADBE', market: 'us', title: 'ADOBE INC.', isRecurring: true, explanationTitle: '创意软件订阅主业利润', explanationBody: 'Adobe主营创意软件订阅，利润来自订阅收入。AI功能推动增长。利润质量极佳。', confidence: 88 },
  { symbol: 'NFLX', market: 'us', title: 'NETFLIX INC', isRecurring: true, explanationTitle: '流媒体订阅主业利润', explanationBody: 'Netflix主营流媒体订阅，利润来自会员订阅费。用户增长和提价并举。利润质量正常。', confidence: 80 },
  
  // 半导体
  { symbol: 'QCOM', market: 'us', title: 'QUALCOMM INC/DE', isRecurring: true, explanationTitle: '芯片设计主业利润', explanationBody: '高通主营手机芯片设计，利润来自专利授权和芯片销售。AI手机驱动增长。利润质量正常。', confidence: 78 },
  { symbol: 'MU', market: 'us', title: 'MICRON TECHNOLOGY INC', isRecurring: true, explanationTitle: '存储芯片主业利润', explanationBody: '美光科技主营存储芯片，利润来自DRAM和NAND销售。存储周期上行驱动盈利。利润质量正常。', confidence: 72 },
  { symbol: '688002', market: 'cn', title: '睿创微纳', isRecurring: true, explanationTitle: '红外热成像主业利润', explanationBody: '睿创微纳主营红外热成像设备，利润来自产品销售。军品订单稳定。利润质量正常。', confidence: 78 },
  { symbol: '000725', market: 'cn', title: '京东方A', isRecurring: true, explanationTitle: '面板制造主业利润', explanationBody: '京东方A主营显示面板，利润来自面板销售。行业周期波动大，但已实现盈利。利润质量正常偏谨慎。', confidence: 70 },
  { symbol: '688111', market: 'cn', title: '金山办公', isRecurring: true, explanationTitle: '办公软件订阅主业利润', explanationBody: '金山办公主营WPS办公软件，利润来自订阅收入。信创需求和订阅转化持续。利润质量正常。', confidence: 82 },
  { symbol: '603259', market: 'cn', title: '药明康德', isRecurring: true, explanationTitle: 'CXO医药外包主业利润', explanationBody: '药明康德主营医药CXO服务，利润来自临床前和临床研究服务。行业龙头地位稳固。利润质量正常。', confidence: 80 },
  
  // 电力能源
  { symbol: '600011', market: 'cn', title: '华能国际', isRecurring: true, explanationTitle: '火电主业利润，煤价下行改善', explanationBody: '华能国际主营火电，利润来自电力销售。煤价下行改善盈利，新能源转型中。利润质量正常偏周期。', confidence: 72 },
  { symbol: '601918', market: 'cn', title: '新集能源', isRecurring: true, explanationTitle: '煤电一体化主业利润', explanationBody: '新集能源主营煤炭和电力生产，利润来自煤炭销售和发电。煤电一体化抗周期能力强。利润质量正常。', confidence: 75 },
  { symbol: '002128', market: 'cn', title: '电投能源', isRecurring: true, explanationTitle: '煤电铝主业利润', explanationBody: '电投能源主营煤炭、电力和电解铝，利润来自产品销售。一体化运营降低风险。利润质量正常。', confidence: 74 },
  { symbol: '601958', market: 'cn', title: '金钼股份', isRecurring: true, explanationTitle: '钼矿采选主业利润', explanationBody: '金钼股份主营钼矿采选，利润来自钼产品销售。行业龙头地位稳固。利润质量正常。', confidence: 75 },
  { symbol: '600489', market: 'cn', title: '中金黄金', isRecurring: true, explanationTitle: '黄金采矿冶炼主业利润', explanationBody: '中金黄金主营黄金采选和冶炼，利润来自黄金销售。金价上涨带动盈利。利润质量正常。', confidence: 76 },
  { symbol: '601069', market: 'cn', title: '西部黄金', isRecurring: true, explanationTitle: '黄金采矿主业利润', explanationBody: '西部黄金主营黄金采选，利润来自黄金销售。金价上涨带动盈利。利润质量正常。', confidence: 72 },
  { symbol: '600583', market: 'cn', title: '海油工程', isRecurring: true, explanationTitle: '海洋油气工程主业利润', explanationBody: '海油工程主营海洋油气工程，利润来自工程服务。中海油订单稳定。利润质量正常。', confidence: 76 },
  { symbol: '600968', market: 'cn', title: '海油发展', isRecurring: true, explanationTitle: '海洋油气服务主业利润', explanationBody: '海油发展主营海洋油气服务，利润来自服务收入。中海油关联交易稳定。利润质量正常。', confidence: 74 },
  { symbol: '00883', market: 'hk', title: '中国海洋石油', isRecurring: true, explanationTitle: '油气开采主业利润', explanationBody: '中国海洋石油主营海上油气开采，利润来自油气销售。成本控制优秀，桶油成本低。利润质量极佳。', confidence: 88 },
  { symbol: '601808', market: 'cn', title: '中海油服', isRecurring: true, explanationTitle: '油田服务主业利润', explanationBody: '中海油服主营油田技术服务，利润来自服务作业。油气资本支出稳定。利润质量正常。', confidence: 76 },
  
  // 煤炭
  { symbol: '000983', market: 'cn', title: '山西焦煤', isRecurring: true, explanationTitle: '焦煤开采主业利润', explanationBody: '山西焦煤主营焦煤开采，利润来自煤炭销售。焦煤价格波动影响盈利。利润质量正常。', confidence: 72 },
  
  // 制造
  { symbol: '600019', market: 'cn', title: '宝钢股份', isRecurring: true, explanationTitle: '钢铁制造主业利润', explanationBody: '宝钢股份主营钢铁制造，利润来自钢材销售。行业龙头，成本优势明显。利润质量正常偏周期。', confidence: 75 },
  { symbol: '600150', market: 'cn', title: '中国船舶', isRecurring: true, explanationTitle: '造船主业利润，订单饱满', explanationBody: '中国船舶主营造船，利润来自船舶订单。LNG船和集装箱船订单饱满。利润质量改善中。', confidence: 72 },
  { symbol: '601766', market: 'cn', title: '中国中车', isRecurring: true, explanationTitle: '轨交装备主业利润', explanationBody: '中国中车主营轨道交通装备，利润来自装备销售。铁路投资稳定。利润质量正常。', confidence: 76 },
  { symbol: '002032', market: 'cn', title: '苏泊尔', isRecurring: true, explanationTitle: '小家电主业利润', explanationBody: '苏泊尔主营厨房小家电，利润来自产品销售。 SEB集团订单转移持续。利润质量正常。', confidence: 78 },
  { symbol: '000550', market: 'cn', title: '江铃汽车', isRecurring: true, explanationTitle: '汽车制造主业利润', explanationBody: '江铃汽车主营轻型商用车，利润来自汽车销售。出口增长强劲。利润质量正常。', confidence: 72 },
  { symbol: '600166', market: 'cn', title: '福田汽车', isRecurring: true, explanationTitle: '汽车制造主业利润', explanationBody: '福田汽车主营商用车，利润来自汽车销售。出口业务增长。利润质量正常偏谨慎。', confidence: 68 },
  { symbol: '601686', market: 'cn', title: '友发集团', isRecurring: true, explanationTitle: '钢管制造主业利润', explanationBody: '友发集团主营焊接钢管，利润来自产品销售。行业龙头地位稳固。利润质量正常。', confidence: 74 },
  { symbol: '601058', market: 'cn', title: '赛轮轮胎', isRecurring: true, explanationTitle: '轮胎制造主业利润', explanationBody: '赛轮轮胎主营轮胎制造，利润来自产品销售。液体黄金轮胎推向市场。利润质量正常。', confidence: 75 },
  
  // 房地产
  { symbol: '02007', market: 'hk', title: '碧桂园', isRecurring: false, explanationTitle: '房地产行业深度调整中', explanationBody: '碧桂园为房地产开发商，当前行业深度调整，流动性压力较大。房地产结算利润可持续性存疑。利润质量需调整。', confidence: 60 },
  { symbol: '00813', market: 'hk', title: '世茂集团', isRecurring: false, explanationTitle: '房地产行业深度调整中', explanationBody: '世茂集团为房地产开发商，当前行业深度调整，流动性压力较大。房地产结算利润可持续性存疑。利润质量需调整。', confidence: 60 },
  
  // 航空
  { symbol: '00293', market: 'hk', title: '国泰航空', isRecurring: true, explanationTitle: '航空客运主业利润', explanationBody: '国泰航空主营航空客运，利润来自机票销售。出行需求复苏带动盈利改善。利润质量正常。', confidence: 70 },
  { symbol: '601021', market: 'cn', title: '春秋航空', isRecurring: true, explanationTitle: '低成本航空主业利润', explanationBody: '春秋航空主营低成本航空，利润来自机票销售。低成本模式优势明显。利润质量正常。', confidence: 78 },
  
  // 港口航运
  { symbol: '600018', market: 'cn', title: '上港集团', isRecurring: true, explanationTitle: '港口物流主业利润', explanationBody: '上港集团主营港口物流，利润来自装卸和物流服务。集装箱吞吐量稳定。利润质量正常。', confidence: 80 },
  { symbol: '600717', market: 'cn', title: '天津港', isRecurring: true, explanationTitle: '港口物流主业利润', explanationBody: '天津港主营港口物流，利润来自装卸服务。吞吐量稳定。利润质量正常。', confidence: 76 },
  { symbol: '601919', market: 'cn', title: '中远海控', isRecurring: true, explanationTitle: '集装箱航运主业利润', explanationBody: '中远海控主营集装箱航运，利润来自运费收入。运价周期波动大，但龙头地位稳固。利润质量正常偏周期。', confidence: 72 },
  
  // 航空机场
  { symbol: '600258', market: 'cn', title: '首旅酒店', isRecurring: true, explanationTitle: '酒店运营主业利润', explanationBody: '首旅酒店主营酒店运营，利润来自住宿和餐饮服务。旅游复苏带动入住率提升。利润质量正常。', confidence: 74 },
  { symbol: '600754', market: 'cn', title: '锦江酒店', isRecurring: true, explanationTitle: '酒店运营主业利润', explanationBody: '锦江酒店主营酒店运营，利润来自住宿服务。规模优势明显。利润质量正常。', confidence: 74 },
  
  // 医药
  { symbol: '000848', market: 'cn', title: '承德露露', isRecurring: true, explanationTitle: '植物蛋白饮料主业利润', explanationBody: '承德露露主营杏仁露饮料，利润来自产品销售。礼品渠道稳定。利润质量正常。', confidence: 76 },
  { symbol: '600211', market: 'cn', title: '西藏药业', isRecurring: true, explanationTitle: '医药制造主业利润', explanationBody: '西藏药业主营医药制造，利润来自药品销售。产品竞争力强。利润质量正常。', confidence: 75 },
  { symbol: '300119', market: 'cn', title: '瑞普生物', isRecurring: true, explanationTitle: '动保疫苗主业利润', explanationBody: '瑞普生物主营动物疫苗，利润来自产品销售。养殖规模化带动需求。利润质量正常。', confidence: 76 },
  { symbol: '002758', market: 'cn', title: '浙农股份', isRecurring: true, explanationTitle: '农资医药分销主业利润', explanationBody: '浙农股份主营农资和医药分销，利润来自产品销售。利润质量正常。', confidence: 70 },
  { symbol: '600062', market: 'cn', title: '华润双鹤', isRecurring: true, explanationTitle: '医药制造主业利润', explanationBody: '华润双鹤主营医药制造，利润来自药品销售。心血管和输液产品稳定。利润质量正常。', confidence: 76 },
  { symbol: '600713', market: 'cn', title: '南京医药', isRecurring: true, explanationTitle: '医药分销主业利润', explanationBody: '南京医药主营医药分销，利润来自配送服务。规模优势明显。利润质量正常。', confidence: 72 },
  { symbol: '601319', market: 'cn', title: '中国人保', isRecurring: true, explanationTitle: '财险主业利润', explanationBody: '中国人保主营财险和寿险，利润来自保费收入和投资收益。财险龙头地位稳固。利润质量正常。', confidence: 78 },
  { symbol: '01398', market: 'hk', title: '工商银行', isRecurring: false, explanationTitle: '国有大行，利润含投资收益', explanationBody: '工商银行是全球最大银行，利润来自利息收入和投资收益。资产质量稳健。利润质量正常。', confidence: 78 },
  { symbol: '00939', market: 'hk', title: '建设银行', isRecurring: false, explanationTitle: '国有大行，利润含投资收益', explanationBody: '建设银行是全球大型银行，利润来自利息收入和投资收益。资产质量稳健。利润质量正常。', confidence: 78 },
  { symbol: '00388', market: 'hk', title: '香港交易所', isRecurring: true, explanationTitle: '交易所主业利润', explanationBody: '港交所主营证券交易和结算，利润来自交易费和上市费。成交量波动影响盈利。利润质量正常。', confidence: 82 },
  { symbol: '00066', market: 'hk', title: '港铁公司', isRecurring: true, explanationTitle: '地铁运营+物业主业利润', explanationBody: '港铁公司主营地铁运营和物业发展，利润来自票价和物业收入。垄断优势明显。利润质量极佳。', confidence: 88 },
]

async function main() {
  console.log('开始批量写入利润质量解释数据（第二批）...\n')
  console.log(`本次将处理 ${profitQualityBatch2.length} 家公司\n`)

  let successCount = 0
  let failCount = 0

  for (const item of profitQualityBatch2) {
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
