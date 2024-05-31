import { NextRequest } from "next/server";

export const GET = async (req: NextRequest) => {
  const ip = req.headers.get('x-forwarded-for') || req.ip
  
  return new Response(JSON.stringify({ ip }))
}

export const POST = async (request: Request) => {
  const apiUrl = process.env.STANDARD_URL

  return new Response(`${apiUrl}`)
}
