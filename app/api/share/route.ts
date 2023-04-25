import { NextResponse } from 'next/server'
import { PrismaClient } from '@prisma/client'

const prisma = new PrismaClient()

function transformToResponse(json: any) {
  if (!json) return json
  return {
    id: json.id,
    name: json.name,
    date: json?.date.split(','),
    price: json?.price.split(','),
    pe: json?.pe.split(','),
  }
}
function transformToDatabase(json: any) {
  if (!json) return json
  return {
    id: json.id,
    name: json.name,
    date: json?.date.join(','),
    price: json?.price.join(','),
    pe: (json?.pe || json?.pe_ttm)?.join(','),
  }
}
function getShare(id: string) {
  return prisma.share
    .findUnique({
      where: { id: id },
    })
    .then((json) => {
      console.log('json: ', json)
      return transformToResponse(json)
    })
}
function saveShare(data: any) {
  return prisma.share.create({
    data: transformToDatabase(data),
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
      return NextResponse.json(json)
    } else {
      const [res, hasSavedShareInfo] = await Promise.all([
        fetch(`https://eniu.com/chart/pea/${id}/t/all`),
        prisma.shareInfo.findUnique({
          where: {
            id,
          },
        }),
      ])
      const json = await res.json()
      // console.log('json: ', json)

      if (json) {
        const newShare = await saveShare({
          ...json,
          id,
          name: hasSavedShareInfo?.name || 'unknown share',
        })
        return NextResponse.json(transformToResponse(newShare))
      }
    }
  } catch (error) {
    console.log('error: ', error)
    return NextResponse.json(error)
  } finally {
    await prisma.$disconnect()
  }

  // return NextResponse.json({ id, msg: 'not found' })
}
