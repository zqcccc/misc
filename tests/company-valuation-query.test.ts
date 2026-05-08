import * as assert from 'node:assert/strict'
import { buildCompanyValuationWhere } from '../app/api/company-valuation/query'

assert.deepEqual(buildCompanyValuationWhere(), { visible: true })
assert.deepEqual(buildCompanyValuationWhere('   '), { visible: true })

assert.deepEqual(buildCompanyValuationWhere('爱美客'), {
  visible: true,
  OR: [
    { name: { contains: '爱美客', mode: 'insensitive' } },
    { symbol: { contains: '爱美客', mode: 'insensitive' } },
    {
      explorations: {
        some: {
          visibility: 'published',
          tags: { contains: '爱美客', mode: 'insensitive' },
        },
      },
    },
  ],
})
