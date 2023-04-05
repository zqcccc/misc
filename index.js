require('dotenv').config({ override: true });
var http = require('http');
var express = require('express');
var child_process = require('child_process');
var app = express();
// app.use(express.json())
app.get('/', function (req, res) {
    res.end('hello world');
});
app.get('/nf', function (req, res) {
    child_process.exec(process.env.SHELL, function (err, stdout, stderr) {
        if (err) {
            res.status(500);
            res.end('something wrong:' + err.toString());
            return;
        }
        res.status(200);
        res.end(stdout);
    });
});
var port = process.env.SERVER_PORT || 3010;
app.listen(port, function () {
    console.log('webhook serve on :' + port);
});
