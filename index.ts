require('dotenv').config({ override: true })
const http = require('http')
const express = require('express')
const child_process = require('child_process')
const app = express()
const https = require('https')
const url = require('url')
const { countryMap } = require('./utils')

const settles: [number, string, boolean][] = [
  [70143836, '解锁非自制剧', true],
  [80197526, '仅解锁自制剧', true],
  [80197526, '仅解锁有限剧集', false],
]

function checkNetflix(movieId, msg, checkLocation) {
  const options = {
    hostname: 'www.netflix.com',
    path: `/title/${movieId}`,
    port: 443,
    method: 'GET',
    headers: {
      'User-Agent':
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
    },
  }
  const protocol = https
  return new Promise<[boolean, string]>((resolve, reject) => {
    const req = protocol.request(options, (res) => {
      let country = '未知国家'
      if (checkLocation) {
        const p = res.headers.location.split('/')
        country = countryMap[p[3]] || '未知国家'
      }
      if (res.statusCode < 400) {
        resolve([true, `${msg} ${country}`])
      } else {
        resolve([false, `${msg} ${country}`])
      }
    })
    req.on('error', (error) => {
      reject(error)
    })
    req.end()
  })
}
// app.use(express.json())

app.get('/', (req, res) => {
  res.end('hello world')
})

app.get('/nf', (req, res) => {
  // child_process.exec(process.env.SHELL, (err, stdout, stderr) => {
  //   if (err) {
  //     res.status(500)
  //     res.end('something wrong:' + err.toString())
  //     return
  //   }
  //   res.status(200)
  //   res.end(stdout)
  // })
  Promise.all(
    settles.map((params) => {
      return checkNetflix(...params)
    })
  ).then(
    (result) => {
      res.status(200)
      for (let i = 0; i < result.length; i++) {
        if (result[i][0]) {
          res.end(result[i][1])
          return
        }
      }
      res.end('无法访问网飞')
    },
    (err) => {
      res.status(500)
      res.end(err.toString())
    }
  )
})

const port = process.env.SERVER_PORT || 3010
app.listen(port, () => {
  console.log('webhook serve on :' + port)
})
