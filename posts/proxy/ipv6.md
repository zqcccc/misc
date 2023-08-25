---
title: 多 ipv6 出口代理
date: "2023-08-19"
description: "一机实现多 ipv6 出口"
---

一般一个机器只有一个 ipv4 出口，一些网站会对流量来的 ip 来源要求比较多，ipv4 的资源比较紧缺，一个能看 Netflix 的 ip 少之又少，花钱买 dns 服务一年也要一百多，秉着能省就省的原则，v6 的 ip 多，这里提到解锁的 ipv6 还支持 Netflix，又是能省下一笔不小的支出了

教程源自不良林https://www.youtube.com/watch?v=kKb0iNZwb9g&t=6s

做文字记录来方便后续的再操作

分发 ipv6 隧道的网站 https://www.tunnelbroker.net/login.php

临时邮箱 http://24mail.chacuo.net/zhtw

身份生成注册可用 https://www.shenfendaquan.com/Index/index/custom_result

TunnelBroker 添加了 ipv4 后，`Example Configurations` 里的 `Linux (netplan 0.103+)` 适用于 Ubuntu 22（反正我用的这个），其实分配的 ip 是一个 ip 段，ip 特别多，默认就写了一个 `address`，可以再手工加一些，然后把配置写到 `/etc/netplan/he-ipv6.yaml` 里

```yaml
network:
  version: 2
  tunnels:
    he-ipv6:
      mode: sit
      remote: xxx.xxx.xxx.xxx
      local: xxx.xxx.xxx.xxx
      addresses:
        - "xxxx:xxx:xx:xxx::2/64"
        - "xxxx:xxx:xx:xxx::3/64"
      routes:
        - to: default
          via: "xxxx:xxx:xx:xxx::1"
```

然后执行 `netplan apply` 让配置生效，`ip a` 查看网卡情况

工具网站 https://www.bulianglin.com/archives/ipv6.html 主要是生成添加 ip 的脚本和替换代理端口，注意要写网卡的名字对上机器里的名字，如果是按照前面的操作的话，这里的网卡应该会叫 `he-ipv6`

```bash
# 配置socks5代理
bash <(curl -fsSLk https://raw.githubusercontent.com/bulianglin/demo/main/xrayL.sh) socks
# 配置vmess+ws代理
bash <(curl -fsSLk https://raw.githubusercontent.com/bulianglin/demo/main/xrayL.sh) vmess
```

检查落地 ip 网站 https://limit.888005.xyz/ 

上面的代称方式都是直连，这种方式的问题就是如果你的机器直连线路比较拉胯的话，还是很影响使用的，可以尝试前置代理或者修改 v2ray outbound 指向刚刚的这些端口

我用的是 x-ui 搭建的，所以修改模板就可以了，就是修改 outbound 里的 tag 为 netflix_proxy 的配置就行了，关于修改成怎样，你可以在你的客户端里的配置里找找，以 v2rayN 为例，先选好要使用的节点配置，然后打开 v2rayN （v6版本）的文件夹，就在它的文件夹下的 `guiConfigs/config.json` 里，它也是一个 outbound 配置

```json
        {
            "tag": "netflix_proxy",
            "protocol": "vmess",
            "settings": {
                "vnext": [
                    {
                        "address": "xxx.xxx.xx.x",
                        "port": 54321,
                        "users": [
                            {
                                "id": "12345678-1234-1234-1234-123456789012",
                                "alterId": 0,
                                "email": "t@t.tt",
                                "security": "auto"
                            }
                        ]
                    }
                ]
            },
            "streamSettings": {
                "network": "ws",
                "wsSettings": {
                    "path": "/asdf",
                    "headers": {}
                }
            },
            "mux": {
                "enabled": false,
                "concurrency": -1
            }
        }
```

可能 tag 对不上，要修改好 tag 对上那个分流规则

```json
{
    "api": {
        "services": [
            "HandlerService",
            "LoggerService",
            "StatsService"
        ],
        "tag": "api"
    },
    "inbounds": [
        {
            "listen": "127.0.0.1",
            "port": 62789,
            "protocol": "dokodemo-door",
            "settings": {
                "address": "127.0.0.1"
            },
            "tag": "api"
        }
    ],
    "outbounds": [
        {
            "protocol": "freedom",
            "settings": {}
        },
        {
            "tag": "netflix_proxy",
            "protocol": "vmess",
            "settings": {
                "vnext": [
                    {
                        "address": "xxx.xxx.xx.x",
                        "port": 54321,
                        "users": [
                            {
                                "id": "12345678-1234-1234-1234-123456789012",
                                "alterId": 0,
                                "email": "t@t.tt",
                                "security": "auto"
                            }
                        ]
                    }
                ]
            },
            "streamSettings": {
                "network": "ws",
                "wsSettings": {
                    "path": "/asdf",
                    "headers": {}
                }
            },
            "mux": {
                "enabled": false,
                "concurrency": -1
            }
        },
        {
            "protocol": "blackhole",
            "settings": {},
            "tag": "blocked"
        }
    ],
    "policy": {
        "system": {
            "statsInboundDownlink": true,
            "statsInboundUplink": true
        }
    },
    "routing": {
        "rules": [
            {
                "type": "field",
                "outboundTag": "netflix_proxy",
                "domain": [
                    "geosite:netflix",
                    "geosite:disney"
                ]
            },
            {
                "inboundTag": [
                    "api"
                ],
                "outboundTag": "api",
                "type": "field"
            },
            {
                "ip": [
                    "geoip:private"
                ],
                "outboundTag": "blocked",
                "type": "field"
            },
            {
                "outboundTag": "blocked",
                "protocol": [
                    "bittorrent"
                ],
                "type": "field"
            }
        ]
    },
    "stats": {}
}
```

这里把 Netflix 和 Disney 的流量都分给了我们刚刚创建的 ipv6 出口的服务，到这里就大功告成了，你可以用你的前置的代理加速你的节点，还能有流媒体的解锁，其他流量走正常的你的节点，算是一个不错的解决方案

