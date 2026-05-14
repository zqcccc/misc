import { PrismaClient } from '@prisma/client'
import { rebuildCompanyValuationSummaries } from '../app/api/company-valuation/summary-store'

const prisma = new PrismaClient()

async function main() {
  const count = await rebuildCompanyValuationSummaries(prisma)
  console.log(`Rebuilt ${count} company valuation summaries`)
}

main()
  .catch((error) => {
    console.error(error)
    process.exitCode = 1
  })
  .finally(async () => {
    await prisma.$disconnect()
  })
