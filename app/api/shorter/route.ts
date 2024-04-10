export const GET = async (req: Request) => {
  const { searchParams } = new URL(req.url)
  const apiUrl = process.env.REMOTE_API
  const res = await fetch(`${apiUrl}/url?key=${searchParams.get('key')}`)
  const url = await res.text()
  console.log('url: ', url)
  return new Response(
    url
  )
}

export const POST = async (request: Request) => {
  const apiUrl = process.env.REMOTE_API
  const res = await fetch(`${apiUrl}/url`, {
    method: 'POST',
    body: request.body,
    headers: {
      'Content-Type': request.headers.get('Content-Type') || 'application/json',
    },
    // @ts-ignore
    duplex: 'half',
    cache: 'no-store',
  })
  const key = await res.text()

  return new Response(`${process.env.SHORTENER_PREFIX}/url/${key}`)
}

export const PATCH = async (request: Request) => {
  const apiUrl = process.env.REMOTE_API
  const res = await fetch(`${apiUrl}/url`, {
    method: 'PATCH',
    body: request.body,
    headers: {
      'Content-Type': request.headers.get('Content-Type') || 'application/json',
    },
    // @ts-ignore
    duplex: 'half',
    cache: 'no-store',
  })
  const key = await res.text()

  return new Response(`${process.env.SHORTENER_PREFIX}/url/${key}`)
}
