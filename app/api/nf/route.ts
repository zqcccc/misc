import { NextResponse } from 'next/server'
import { countryMap } from './utils'

const settles: [number, string][] = [
  [70143836, '解锁非自制剧'],
  [80197526, '解锁自制剧'],
  [80018499, '解锁少量剧集'],
]

function checkNetflix(movieId: number, msg: string) {
  return new Promise<[boolean, string]>((resolve, reject) => {
    const url = `https://www.netflix.com/title/${movieId}`
    console.log('checkNetflix url:', url)
    fetch(url, {
      // next: { revalidate: 5 },
      cache: 'no-store',
      headers: {
        'User-Agent':
          'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
      },
      redirect: 'manual',
    }).then(
      (res) => {
        let country = '未知国家'
        const headers = res.headers.get('location')
        // console.log('%c res.status: ', 'font-size:12px;background-color: #33A5FF;color:#fff;', res.status)
        if (headers) {
          const p = headers.split('/')
          country = countryMap[p[3]] || '未知国家：' + p[3]
        }
        if (res.status < 400) {
          resolve([true, `${msg} ${country}`])
        } else {
          resolve([false, `不${msg}`])
        }
      },
      (error) => {
        console.log('request error: ', error)
        resolve([false, `不${msg}, 网络错误，可能是无法访问Netflix`])
        // reject(error)
      }
    )
  })
}

export const GET = async () => {
  return NextResponse.json<[boolean, string][]>(
    await Promise.all(
      settles.map((params) => {
        return checkNetflix(...params)
      })
    )
  )
}

export const dynamic = "force-dynamic"