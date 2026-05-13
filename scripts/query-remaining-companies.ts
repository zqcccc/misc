import { PrismaClient, Prisma } from '@prisma/client';

const prisma = new PrismaClient();

async function main() {
  try {
    // 查询可见但没有已发布深度分析的公司
    const companies = await prisma.$queryRaw<Array<{market: string, symbol: string, name: string}>>`
      SELECT c.market, c.symbol, c.name
      FROM "Company" c
      LEFT JOIN "CompanyExploration" ce ON c.id = ce."companyId" AND ce.visibility = 'published'
      WHERE c.visible = true 
        AND ce.id IS NULL
      ORDER BY c.market, c.symbol
    `;

    console.log(`剩余待分析公司总数: ${companies.length}`);
    console.log('\n按市场分布:');
    
    const byMarket = companies.reduce((acc, c) => {
      acc[c.market] = (acc[c.market] || 0) + 1;
      return acc;
    }, {} as Record<string, number>);
    
    console.log(byMarket);
    
    console.log('\n待分析公司列表:');
    companies.forEach(c => {
      console.log(`${c.market}:${c.symbol} - ${c.name}`);
    });
    
    // 优先推荐美股大盘股
    const usLargeCap = companies.filter(c => 
      c.market === 'us' && 
      ['JPM', 'META', 'AMZN', 'GOOGL', 'TSLA', 'BRK.B', 'V', 'JNJ', 'WMT', 'PG'].includes(c.symbol)
    );
    
    if (usLargeCap.length > 0) {
      console.log('\n优先推荐分析（美股大盘股）:');
      usLargeCap.forEach(c => {
        console.log(`${c.market}:${c.symbol} - ${c.name}`);
      });
    }
    
    // 返回第一家公司供自动化使用
    if (companies.length > 0) {
      // 优先选择美股大盘股
      const target = usLargeCap[0] || companies[0];
      console.log(`\n=== 建议分析公司 ===`);
      console.log(`市场: ${target.market}`);
      console.log(`代码: ${target.symbol}`);
      console.log(`名称: ${target.name}`);
    }
    
  } catch (error) {
    console.error('查询失败:', error);
  } finally {
    await prisma.$disconnect();
  }
}

main();
