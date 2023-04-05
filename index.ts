require('dotenv').config({ override: true })
const http = require('http')
const express = require('express')
const child_process = require('child_process')
const app = express()

// app.use(express.json())

app.get('/', (req, res) => {
  res.end('hello world')
})

app.get('/nf', (req, res) => {
  child_process.exec(process.env.SHELL, (err, stdout, stderr) => {
    if (err) {
      res.status(500)
      res.end('something wrong:' + err.toString())
      return
    }
    res.status(200)
    res.end(stdout)
  })
})

const port = process.env.SERVER_PORT || 3010
app.listen(port, () => {
  console.log('webhook serve on :' + port)
})
