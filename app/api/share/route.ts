import { NextResponse } from 'next/server'
import { Prisma, PrismaClient, Share } from '@prisma/client'

const prisma = new PrismaClient()

function transformToResponse(json: Share | null):
  | (Omit<Share, 'date' | 'price' | 'pe'> & {
      date: string[]
      price: string[]
      pe: string[]
    })
  | null {
  if (!json) return json
  return {
    id: json.id,
    name: json.name,
    date: json?.date.split(','),
    price: json?.price.split(','),
    pe: json?.pe.split(','),
    createdAt: json.createdAt,
    updatedAt: json.updatedAt,
  }
}
function transformToDatabase(json: any): Prisma.ShareCreateInput {
  if (!json) return json
  return {
    id: json.id,
    name: json.name,
    date: json?.date.join(','),
    price: json?.price.join(','),
    pe: (json?.pe || json?.pe_ttm)?.join(','),
    // createAt: json.createAt,
    // updateAt: json.updateAt,
  }
}
function getShare(id: string) {
  return prisma.share
    .findUnique({
      where: { id: id },
    })
    .then((json) => {
      // console.log('json: ', json)
      return transformToResponse(json)
    })
}
function saveShare(data: any) {
  return prisma.share.upsert({
    where: {
      id: data.id,
    },
    create: transformToDatabase(data),
    update: transformToDatabase(data),
  })
}
// /api/share
export async function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const id = searchParams.get('id')
  // https://eniu.com/chart/pea/sh600519/t/all
  if (!id) return NextResponse.json({ id, msg: 'id required' })

  try {
    const json = await getShare(id)

    if (json) {
      const today = new Date()
      today.setHours(0, 0, 0, 0)
      if (json.updatedAt >= today) {
        console.log('directly return', json.id)
        // directly return the json when the updatedAt is today
        return NextResponse.json(json)
      }
    }

    const [res, hasSavedShareInfo] = await Promise.all([
      fetch(`https://eniu.com/chart/pea/${id}/t/all`),
      prisma.shareInfo.findUnique({
        where: {
          id,
        },
      }),
    ])
    const newJson = await res.json()
    // console.log('newJson: ', newJson)

    if (newJson) {
      const newShare = await saveShare({
        ...newJson,
        id,
        name: hasSavedShareInfo?.name || 'unknown share',
      })
      return NextResponse.json(transformToResponse(newShare))
    }
  } catch (error) {
    console.log('error: ', error)
    return NextResponse.json(error)
  } finally {
    await prisma.$disconnect()
  }

  // return NextResponse.json({ id, msg: 'not found' })
}