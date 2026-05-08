import * as assert from 'node:assert/strict'
import { resolveCompanySearchSymbol } from '../app/pe/utils'
import type { CompanyValuationCard } from '../app/pe/types'

const entries = [
  {
    symbol: '00700.HK',
    title: '腾讯控股',
    tags: ['游戏', '云'],
  },
  {
    symbol: 'AAPL',
    title: 'Apple',
    tags: ['consumer'],
  },
] as CompanyValuationCard[]

assert.equal(resolveCompanySearchSymbol('腾讯控股', entries), '00700.HK')
assert.equal(resolveCompanySearchSymbol('700', entries), '00700.HK')
assert.equal(resolveCompanySearchSymbol('aapl', entries), 'AAPL')
assert.equal(resolveCompanySearchSymbol('MSFT', entries), 'MSFT')
assert.equal(resolveCompanySearchSymbol('  9988.HK  ', entries), '9988.HK')
