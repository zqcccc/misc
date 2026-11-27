import { NextResponse } from 'next/server'
import { checkNetflixStatus } from './utils'

export const GET = async () => {
  return NextResponse.json<[boolean, string][]>(await checkNetflixStatus())
}

export const dynamic = "force-dynamic"