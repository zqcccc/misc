import { NextResponse } from 'next/server'
import { Prisma, PrismaClient, Share } from '@prisma/client'

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const id = searchParams.get('id')
  if (!id) return NextResponse.json({ id, msg: 'id required' })
  const prisma = new PrismaClient()
  try {
    const config = await prisma.lowCodeConfig.findUnique({
      where: { id: Number(id) },
    })
    return NextResponse.json(config)
  } catch (e) {
    console.log('error: ', e)
    return NextResponse.json({ error: e })
  } finally {
    await prisma.$disconnect()
  }
}

export async function POST(request: Request) {
  const body = await request.json()
  console.log('body: ', body)
  if (!body) return NextResponse.json({ msg: 'body required' })
  const prisma = new PrismaClient()
  try {
    body.json = JSON.stringify(body.json)
    const update = Object.assign({}, body)
    delete update.id
    const config = await prisma.lowCodeConfig.upsert({
      where: { id: Number(body.id) || -1 },
      create: update,
      update,
    })
    return NextResponse.json(config)
  } catch (e) {
    console.log('error: ', e)
    return NextResponse.json({ error: e })
  } finally {
    await prisma.$disconnect()
  }
}
