import { PrismaClient } from '@prisma/client'
import { readFile } from 'fs/promises'
import { join } from 'path'
import { writeMarketAnalysisCrossMarket, type CrossMarketWriteInput } from '../lib/market-analysis'

const prisma = new PrismaClient()
const TMP_DIR = join(process.cwd(), 'tmp')

async function main() {
  console.log('开始导入美能能源分析数据...');
  
  const filePath = join(TMP_DIR, '001299-meineng-analysis.json');
  const content = await readFile(filePath, 'utf-8');
  const data = JSON.parse(content) as CrossMarketWriteInput;
  
  console.log('读取文件成功');
  
  // 使用writeMarketAnalysisCrossMarket函数来写入
  await writeMarketAnalysisCrossMarket(data);
  
  console.log('导入完成！');
}

main()
  .then(async () => {
    await prisma.$disconnect();
  })
  .catch(async (e) => {
    console.error(e);
    await prisma.$disconnect();
    process.exit(1);
  });
