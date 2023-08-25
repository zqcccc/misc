import { NextResponse } from 'next/server'
import IPinfoWrapper, { BatchResponse } from 'node-ipinfo'

const ipinfoWrapper = new IPinfoWrapper(process.env.IPINFO_TOKEN || '')

export async function POST(request: Request) {
  const body = await request.json()
  console.log('body: ', body)
  if (!body) return NextResponse.json({ msg: 'body required' })
  const res = await ipinfoWrapper
    .getBatch(body)
    .then((response: BatchResponse) => {
      console.log(response)
      return response
    })
  return NextResponse.json(res)
}
