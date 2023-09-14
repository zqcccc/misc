import { NextResponse } from 'next/server'

export async function POST(request: Request) {
  const username = process.env.EUDIC_USERNAME
  const password = process.env.EUDIC_PASSWORD
  if (!username || !password) {
    return NextResponse.json({ msg: 'error config in server' })
  }
  const form = new FormData()
  form.append('UserName', username)
  form.append('Password', password)
  const res = await fetch(`https://dict.eudic.net/Account/Login`, {
    method: 'POST',
    body: form,
    redirect: 'manual',
    next: { revalidate: 300 },
  })

  const cookies = res.headers.getSetCookie()
  if (cookies && cookies.length) {
    const sessionCookie = cookies.find((i) => i.includes('EudicWebSession'))
    if (sessionCookie) {
      const newCookie = sessionCookie
        // .split('=')[1]
        .split(';')
        .filter((i) => !i.includes('domain'))
        .join(';')
      let response = new Response()
      // Set a cookie to hide the banner
      response.headers.set('Set-Cookie', newCookie)
      return response
    }
  }
  return NextResponse.json({ msg: 'login fail' })
}
