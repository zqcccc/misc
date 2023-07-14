import { PrismaClient } from '@prisma/client'

const prisma = new PrismaClient()

async function main() {
  // ... you will write your Prisma Client queries here

  const json = await prisma.lowCodeConfig.create({
    data: {
      json: '{"name": "123"}',
    }
  })
  
  // const user = await prisma.share.create({
  //   data: {
  //     id: '123',
  //     name: 'Alice',
  //     date: '213',
  //     pe: '123',
  //     price: 'price',
  //   },
  // })
  // const json = await (
  //   await fetch('https://eniu.com/static/data/stock_list.json')
  // ).json()

  /**
   * read json and write to database
   */
  // const json = require('../node_modules/list.json')
  // json.reduce(async (p: any, element: any) => {
  //   await p
  //   console.log('element: ', element)
  //   const existingShare = await prisma.shareInfo.findUnique({
  //     where: {
  //       id: element.stock_id,
  //     },
  //   });
  //   if(existingShare) {
  //     const updatedShareInfo = await prisma.shareInfo.update({
  //       where: {
  //         id: existingShare.id,
  //       },
  //       data: {
  //         id: element.stock_id,
  //         stock_number: element.stock_number,
  //         name: element.stock_name,
  //         stock_abbr: element.stock_abbr,
  //         stock_pinyin: element.stock_pinyin,
  //       },
  //     });
  //   } else {
  //     const share = await prisma.shareInfo.create({
  //       data: {
  //         id: element.stock_id,
  //         stock_number: element.stock_number,
  //         name: element.stock_name,
  //         stock_abbr: element.stock_abbr,
  //         stock_pinyin: element.stock_pinyin,
  //       },
  //     })
  //   }
  // }, Promise.resolve())

  // console.log('hello world')

  // const user = await prisma.share.create({
  //   data: {

  //   }
  // })
  // console.log(user)

  /**
   * give an id and find its share and update it when the updateAt is older than 1 day
   */
  // const share = await prisma.share.findUnique({
  //   where: {
  //     id: 'sh600519',
  //   },
  // })
  // console.log('share: ', share)
  // share?.updatedAt
  // const today = new Date();
  // today.setHours(0, 0, 0, 0)
  // console.log('today: ', today)

  // share?.updatedAt && console.log('share?.updatedAt > today: ', share?.updatedAt > today)

  // const share2 = await prisma.share.upsert({
  //   where: {
  //     id: 'sh600519',
  //   },
  //   update: {
  //     name: '茅台222',
  //   },
  //   create: {
  //     id: 'sh600519',
  //     name: '贵州茅台',
  //     date: share?.date || '',
  //     price: share?.price || '',
  //     pe: share?.pe || '',
  //   },
  // })

  // console.log('share2: ', share2.name)

  /**
   * remove duplicate data
   */
  // const shares = await prisma.share.findMany()
  // // console.log('shares: ', shares)
  // shares.forEach(async (share) => {
  //   console.log('share: ', share.name)
  //   const dates = share.date.split(',')
  //   const pes = share.pe.split(',')
  //   const prices = share.price.split(',')

  //   // 去重的数组
  //   var uniqueArray = new Set(dates)

  //   // 获取需要删除的索引
  //   var indexesToRemove: number[] = []
  //   dates.forEach(function (item, index) {
  //     if (!uniqueArray.has(item)) {
  //       indexesToRemove.push(index)
  //     } else {
  //       uniqueArray.delete(item)
  //     }
  //   })

  //   // 删除索引对应的元素
  //   indexesToRemove.reverse().forEach(function (index) {
  //     dates.splice(index, 1)
  //     pes.splice(index, 1)
  //     prices.splice(index, 1)
  //     // console.log(`dates.splice(${index}, 1): `, dates.splice(index, 1))
  //     // console.log(`pes.splice(${index}, 1): `, pes.splice(index, 1))
  //     // console.log(`prices.splice(${index}, 1): `, prices.splice(index, 1))
  //   })

  //   console.log(dates[dates.length - 1])
  // console.log(pes.length)
  // console.log(prices.length)

  // await prisma.share.upsert({
  //   where: {
  //     id: share.id,
  //   },
  //   update: {
  //     name: share.name,
  //     date: dates.join(','),
  //     price: prices.join(','),
  //     pe: pes.join(','),
  //   },
  //   create: {
  //     id: share.id,
  //     name: share.name,
  //     date: dates.join(','),
  //     price: prices.join(','),
  //     pe: pes.join(','),
  //   },
  // })
  // })

  // async function getHistoricalEPS(symbol: string) {
  //   const apiKey = 'W5JHITOXP2PFQFQ0' // 在 Alpha Vantage 注册并获取 API 密钥

  //   try {
  //     const response = await fetch(
  //       `https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol=${'APPLE'}&apikey=${apiKey}`
  //     ).then((res) => res.json())

  //     console.log('response: ', response)
  //     // 提取历史市盈率数据
  //     // const peRatio = response.data['Global Quote']['PERatio']

  //     // console.log(`腾讯（0700.HK）的历史市盈率：${peRatio}`)
  //   } catch (error) {
  //     console.error('获取历史市盈率数据时发生错误：', error)
  //   }
  // }

  // getHistoricalEPS('0700.HK')

}

main()
  .then(async () => {
    await prisma.$disconnect()
  })
  .catch(async (e) => {
    console.error(e)
    await prisma.$disconnect()
    process.exit(1)
  })
