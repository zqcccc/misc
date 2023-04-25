import { PrismaClient } from '@prisma/client'

const prisma = new PrismaClient()

async function main() {
  // ... you will write your Prisma Client queries here

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

  // read json and write to database
  // const json = require('../stock_list.json')
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

  console.log('hello world')

  // const user = await prisma.share.create({
  //   data: {

  //   }
  // })
  // console.log(user)
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
