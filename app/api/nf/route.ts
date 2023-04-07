import { countryMap } from './utils'

const settles: [number, string, boolean][] = [
  [70143836, '解锁非自制剧', true],
  [80197526, '解锁自制剧', true],
  [80197526, '解锁少量剧集', true],
]

function checkNetflix(movieId: number, msg: string, checkLocation: boolean) {
  return new Promise<[boolean, string]>((resolve, reject) => {
    fetch(`https://www.netflix.com/title/${movieId}`, {
      // next: { revalidate: 5 },
      cache: 'no-store',
      headers: {
        'User-Agent':
          'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
      },
      redirect: 'manual',
    }).then(
      (res) => {
        let country = '未知国家'
        const headers = res.headers.get('location')
        // console.log('%c res.status: ', 'font-size:12px;background-color: #33A5FF;color:#fff;', res.status)
        if (checkLocation && headers) {
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
        reject(error)
      }
    )
  })
}

export const GET = async () => {
  return Promise.all(
    settles.map((params) => {
      return checkNetflix(...params)
    })
  )
}
