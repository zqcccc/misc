---
title: warp 设置
date: "2023-10-27"
description: "为一些特殊网站设置 warp 分流"
---

cloudflare 真的可谓是一家伟大的公司，那么多免费的服务还能稳定地服务，warp 是 cloudflare 官方的 vpn，刚出来的时候因为没有被滥用所以 ip 显得相对“纯净”，这对访问解锁的网飞和 ChatGPT 都是很有用的，当然现在有点被滥用，不过用来访问 ChatGPT 还是可以的。

开始设置前需要有个 cloudflare 账号，并设置 zero trust，都是免费的，网上教程很多，不多说了。对于我们的电脑还有手机端都是用它们默认的全局模式，没啥好说的，我们要的是可以想用才用的分流的模式。

首先登录到 zero trust 也是它们的 team 版本，他会弹出一个网页让我们登录，在最后输入验证码的时候打开浏览器的开发者工具的网络面板，登录成功后会有个 `com.cloudflare.warp://你的team名.cloudflareaccess.com/auth?token=<JWT token>` 的跳转 app 的请求

有两种方式来使用 warp，一种是 wireguard，可能相对简单，一种是官方客户端，会麻烦点而且没有 arm 端。不过最终效果感觉都是一样的。

## wireguard

生成 wireguard 的话就是接下来到 https://replit.com/@misaka-blog/warpgo-profile-generator （感谢 misaka 的脚本），点 `run` ，选 Teams，**仅复制 token** 到里面，就可以生成配置，最后我们再根据生成的配置去添加 xray 的 outbound

```json

{
    "tag": "WARP_out",
    "protocol": "wireguard",
    "settings": {
        "secretKey": "YFYOAdbw1bKTHlNNi+aEjBM3BO7unuFC5rOkMRAz9XY=", // 粘贴你的 "private_key" 值
        "address": [
            "172.16.0.2/32",
            "2606:4700:110:8a36:df92:102a:9602:fa18/128" // 替换掉自己配置文件的 IPv6 地址
        ],
        "peers": [
            {
                "publicKey": "bmXOC+F1FxEMF9dyiK2H5/1SUtzH0JuVo51h2wPfgyo=",
                "allowedIPs": [
                    "0.0.0.0/0",
                    "::/0"
                ],
                "endpoint": "engage.cloudflareclient.com:2408"
            }
        ],
        "mtu": 1280
    }
}
```

修改上面有注释的地方，在 routing 里添加相应的规则就行了。

```json
{
  "type": "field",
  "outboundTag": "WARP_out",
  "domain": [
    "geosite:openai",
    "domain:sentry.io",
    "ip.gs"
  ]
}
```

去访问 https://ip.gs，如果是 cloudflare 的 ip 就是成功了

## 官方客户端

用官方 linux 客户端（只支持x86），先安装好，安装指引https://pkg.cloudflareclient.com/

复制前面登录后跳转 app 的**整个链接**（注意这个链接的有效期是比较短，如果失效了刷新一下那个登录页面，会生成新的链接）

```bash
warp-cli teams-enroll-tokens "<跳转的整个链接>"
```

查看设置

```bash
warp-cli settings
```

Zero trust 的账号会发现 Mode 可能不是 WarpProxy，也是不能直接更改的，那是因为使用团队账号是要到 Zero trust 官网那里去修改的。

登录到 Zero trust 官网 https://one.dash.cloudflare.com，进入 “Settings”，“WARP Client”，“Create profile”，名字随便取，“Build an expression” 里面，选个 "User email"，"matches"，"「刚刚你登录的邮箱」"，

然后到 Service mode 里选择 **Proxy mode**，并设置端口（用默认的 40000 也行），滚到最下面点击 “Create profile” 创建。

过一会，到 linux 上去看会发现客户端的 `Mode: WarpProxy on port 40000` 就是设置成功了，再去添加 xray 的 outbound

```json
{
  "tag": "socks5-warp",
  "protocol": "socks",
  "settings": {
    "servers": [
      {
        "address": "127.0.0.1",
        "port": 40000
      }
    ]
  }
}
```

在 routing 里添加相应的规则

```json
{
  "type": "field",
  "outboundTag": "socks5-warp",
  "domain": [
    "geosite:openai",
    "domain:sentry.io",
    "ip.gs"
  ]
}
```

去访问 https://ip.gs，如果是 cloudflare 的 ip 就是成功了
