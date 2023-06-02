// function a(t) {
//   var n = t.volumn.split(",")
//     , r = t.price.split(",")
//     , s = t.priceFactor
//     , o = t.dates.split(",")
//     , u = t.sortYear
//     , a = o.length
//     , f = {};
//   f.totalKlineNum = t.total,
//     f.firstDate = t.start,
//     f.issuePrice = t.issuePrice,
//     f.isGetTotalData = !1,
//     f.name = t.name,
//     f.sortYear = t.sortYear,
//     f.priceFactor = t.priceFactor;
//   if (t.total == 0)
//     return f.dataArray = [],
//       f;
//   var l = [], c, h, p = ["i", "o", "a", "c"], d = 0, v = "", m = 0, g = [];
//   for (var y = 0; y < u.length; y++)
//     g.push([u[y][0], m]),
//       m += u[y][1];
//   g.push(["", Infinity]);
//   for (var b = 0; b < a; b++) {
//     l[b] = {},
//       b === 0 ? (v = g[d][0],
//         l[b].t = v + o[b],
//         f.isGetTotalData = f.firstDate == l[b].t ? !0 : !1) : b < g[d + 1][1] ? l[b].t = v + o[b] : b >= g[d + 1][1] && (++d,
//           v = g[d][0],
//           l[b].t = v + o[b]),
//       l[b].n = parseInt(n[b]);
//     for (var w = 0; w < 4; w++)
//       l[b].i ? l[b][p[w]] = r[4 * b + w] / s + l[b].i : l[b][p[w]] = r[4 * b + w] / s;
//     l[b].s = i(l[b], l[b - 1]),
//       b === 0 ? l[b].yc = l[b].o : l[b].yc = l[b - 1].c
//   }
//   return f.isGetTotalData && (l[0].yc = parseFloat(f.issuePrice)),
//     f.dataArray = l,
//     f
// }
// a(require("./node_module/data.json"))

function calculateStatus(currentKline, previousKline) {
  if (!previousKline) {
    return 'Initial'
  }

  if (
    currentKline.close > currentKline.open &&
    previousKline.close > previousKline.open
  ) {
    return 'Rising'
  }

  if (
    currentKline.close < currentKline.open &&
    previousKline.close < previousKline.open
  ) {
    return 'Falling'
  }

  return 'Unchanged'
}

function processData(data) {
  const volumes = data.volumn.split(',')
  const prices = data.price.split(',')
  const priceFactor = data.priceFactor
  const dates = data.dates.split(',')
  const sortYears = data.sortYear
  const numDates = dates.length

  const result = {
    totalKlineNum: data.total,
    firstDate: data.start,
    issuePrice: data.issuePrice,
    isGetTotalData: false,
    name: data.name,
    sortYear: data.sortYear,
    priceFactor: data.priceFactor,
    dataArray: [],
  }

  if (data.total === 0) {
    return result
  }

  const klines = []
  let sortIndex = 0
  let currentSort = ''
  let dataIndex = 0
  const sortRanges = []

  for (let i = 0; i < sortYears.length; i++) {
    sortRanges.push([sortYears[i][0], dataIndex])
    dataIndex += sortYears[i][1]
  }
  sortRanges.push(['', Infinity])

  for (let j = 0; j < numDates; j++) {
    const kline = {}

    if (j === 0) {
      currentSort = sortRanges[sortIndex][0]
      kline.time = currentSort + dates[j]
      result.isGetTotalData = result.firstDate === kline.time
    } else if (j < sortRanges[sortIndex + 1][1]) {
      kline.time = currentSort + dates[j]
    } else {
      sortIndex++
      currentSort = sortRanges[sortIndex][0]
      kline.time = currentSort + dates[j]
    }

    kline.volume = parseInt(volumes[j])

    for (let k = 0; k < 4; k++) {
      if (kline.init) {
        kline[['init', 'open', 'average', 'close'][k]] =
          prices[4 * j + k] / priceFactor + kline.init
      } else {
        kline[['init', 'open', 'average', 'close'][k]] =
          prices[4 * j + k] / priceFactor
      }
    }

    kline.status = calculateStatus(kline, klines[j - 1])
    kline.yesterdayClose = j === 0 ? kline.open : klines[j - 1].close

    klines[j] = kline
  }

  if (result.isGetTotalData) {
    klines[0].yesterdayClose = parseFloat(result.issuePrice)
  }

  result.dataArray = klines

  return result
}

// 数据来源 https://d.10jqka.com.cn/v6/line/hk_HK0700/02/all.js
const result = processData(require('../node_modules/data.json'))
