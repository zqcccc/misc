require('dotenv').config({ override: true });
var http = require('http');
var express = require('express');
var child_process = require('child_process');
var app = express();
var https = require('https');
var url = require('url');
var countryMap = require('./utils').countryMap;
var settles = [
    [70143836, '解锁非自制剧', true],
    [80197526, '仅解锁自制剧', true],
    [80197526, '仅解锁有限剧集', false],
];
function checkNetflix(movieId, msg, checkLocation) {
    var options = {
        hostname: 'www.netflix.com',
        path: "/title/".concat(movieId),
        port: 443,
        method: 'GET',
        headers: {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
        }
    };
    var protocol = https;
    return new Promise(function (resolve, reject) {
        var req = protocol.request(options, function (res) {
            var country = '未知国家';
            if (checkLocation) {
                var p = res.headers.location.split('/');
                country = countryMap[p[3]] || '未知国家';
            }
            if (res.statusCode < 400) {
                resolve([true, "".concat(msg, " ").concat(country)]);
            }
            else {
                resolve([false, "".concat(msg, " ").concat(country)]);
            }
        });
        req.on('error', function (error) {
            reject(error);
        });
        req.end();
    });
}
// app.use(express.json())
app.get('/', function (req, res) {
    res.end('hello world');
});
app.get('/nf', function (req, res) {
    // child_process.exec(process.env.SHELL, (err, stdout, stderr) => {
    //   if (err) {
    //     res.status(500)
    //     res.end('something wrong:' + err.toString())
    //     return
    //   }
    //   res.status(200)
    //   res.end(stdout)
    // })
    Promise.all(settles.map(function (params) {
        return checkNetflix.apply(void 0, params);
    })).then(function (result) {
        res.status(200);
        for (var i = 0; i < result.length; i++) {
            if (result[i][0]) {
                res.end(result[i][1]);
                return;
            }
        }
        res.end('无法访问网飞');
    }, function (err) {
        res.status(500);
        res.end(err.toString());
    });
});
var port = process.env.SERVER_PORT || 3010;
app.listen(port, function () {
    console.log('webhook serve on :' + port);
});
