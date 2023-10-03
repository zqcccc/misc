'use client'

import { useNodesStore } from '@/store/node'
import { useSetState } from 'ahooks'
import { useEffect, useMemo, useRef } from 'react'
import { Base64 } from 'js-base64'
import { copy } from '../post/[...id]/helpers'

const emojiMap: Record<string, string> = {
  CN: '🇨🇳',
  HK: '🇭🇰',
  TW: '🇹🇼',
  US: '🇺🇸',
  JP: '🇯🇵',
  KR: '🇰🇷',
  SG: '🇸🇬',
  DE: '🇩🇪',
  FR: '🇫🇷',
  GB: '🇬🇧',
  CA: '🇨🇦',
  AU: '🇦🇺',
  SE: '🇸🇪',
}

export default function NodeConfig() {
  const NodesStore = useNodesStore()
  const [state, setState] = useSetState({
    input: '',
    unifyName: '',
    nodeList: [] as any[],
    willGetLoc: true,
  })
  useEffect(() => {
    if (state.nodeList.length) return
    setState({
      nodeList: NodesStore.nodesInput
        .split('\n')
        .map((item) => {
          try {
            const [protocol, base64Str] = item.split('://')
            const jsonStr = Base64.decode(base64Str)
            const obj = JSON.parse(jsonStr)
            const ipInfo = NodesStore.getIp(obj.add)
            obj.ps =
              ipInfo && !obj.ps.includes(ipInfo.countryCode)
                ? `${emojiMap[ipInfo.countryCode] || ''}${ipInfo.countryCode}-${
                    state.unifyName || obj.ps
                  }`
                : state.unifyName || obj.ps
            obj.path =
              !obj.path || obj.path.includes('?ed=2048')
                ? obj.path
                : `${obj.path}?ed=2048`
            return [protocol, obj]
          } catch (e) {
            return false
          }
        })
        .filter(Boolean),
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [NodesStore.nodesInput, NodesStore.nodeMap, state.unifyName])

  const output = useMemo(() => {
    return state.nodeList
      .map(([protocol, obj]) => {
        const base64Str = Base64.encode(JSON.stringify(obj))
        return `${protocol}://${base64Str}`
      })
      .join('\n')
  }, [state.nodeList])

  const isRequestingIp = useRef(false)
  const isRequestingHost = useRef(false)
  useEffect(() => {
    if (isRequestingIp.current || !state.nodeList.length || !state.willGetLoc)
      return
    const queryHosts: string[] = []
    const queryIps = state.nodeList
      .map(([protocol, obj]) => {
        if (!obj?.add) return
        if (NodesStore.getIp(obj.add)) return
        if (/[a-z]/i.test(obj.add)) {
          queryHosts.push(obj.add)
          return
        }
        if (/\d+\.\d+\.\d+\.\d+/.test(obj.add)) return `${obj.add}`
      })
      .filter(Boolean)
    if (queryIps.length) {
      isRequestingIp.current = true
      fetch('/api/ip', {
        method: 'POST',
        body: JSON.stringify(queryIps),
      })
        .then((res) => {
          res.json().then((data) => {
            Object.keys(data).forEach((ip) => {
              NodesStore.setIp(ip, data[ip])
            })
          })
        })
        .finally(() => {
          isRequestingIp.current = false
        })
    }
    if (queryHosts.length) {
      isRequestingHost.current = true
      Promise.all(
        queryHosts.map((host) => {
          fetch(`https://ip125.com/api/${host}?lang=zh`, {
            method: 'POST',
            body: JSON.stringify(queryHosts),
          }).then((res) => {
            res.json().then((data) => {
              NodesStore.setIp(host, data)
            })
          })
        })
      )
        .catch((res) => {
          console.log(
            '%c res: ',
            'font-size:12px;background-color: #A8978E;color:#fff;',
            res
          )
        })
        .finally(() => {
          isRequestingHost.current = false
        })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.nodeList])

  return (
    <main className='p-3'>
      <h2>Node Config input</h2>
      <label>
        <input
          type='checkbox'
          checked={state.willGetLoc}
          onChange={(e) => {
            setState({ willGetLoc: e.target.checked })
          }}
        />
        是否要获取ip地区信息
      </label>
      <textarea
        rows={10}
        className='w-full mt-2'
        placeholder='ss/ssr/vmess链接，多个链接每行一个'
        value={NodesStore.nodesInput}
        onChange={(e) => NodesStore.setNodesInput(e.target.value)}
      ></textarea>
      <input
        type='text'
        placeholder='统一改名'
        value={state.unifyName}
        onChange={(e) => setState({ unifyName: e.target.value })}
      />
      <div className='mt-3'>
        <h2>node list</h2>
        <div className='flex w-full flex-wrap'>
          {state.nodeList.map(([_, item], index) => {
            const keys = Object.keys(item)
            return (
              <div className='m-3' key={index}>
                <h3>item {item?.ps && `name:${item?.ps}`}</h3>
                {keys.map((key, keyIndex) => {
                  return (
                    <div key={keyIndex}>
                      <input
                        className='w-12'
                        value={key}
                        onChange={(e) => {
                          const nodeList = state.nodeList.concat()
                          const newItem = nodeList[index].concat()
                          const v = item[key]
                          delete item[key]
                          newItem[1] = Object.assign({}, item, {
                            [e.target.value]: v,
                          })
                          nodeList[index] = newItem
                          setState({ nodeList })
                        }}
                      />
                      <span> : </span>
                      <input
                        value={item[key]}
                        onChange={(e) => {
                          const nodeList = state.nodeList.concat()
                          const newItem = nodeList[index].concat()
                          newItem[1] = Object.assign({}, item, {
                            [key]: e.target.value,
                          })
                          nodeList[index] = newItem
                          setState({ nodeList })
                        }}
                      ></input>
                      <button
                        className='px-1 ml-1'
                        onClick={() => {
                          const nodeList = state.nodeList.concat()
                          const newItem = nodeList[index].concat()
                          newItem[1] = Object.assign({}, item)
                          nodeList[index] = newItem
                          delete nodeList[index][1][key]
                          setState({ nodeList })
                        }}
                      >
                        x
                      </button>
                    </div>
                  )
                })}
                <button
                  className='px-3 mt-1'
                  onClick={() => {
                    const nodeList = state.nodeList.concat()
                    const newItem = nodeList[index].concat()
                    newItem[1] = Object.assign({}, item, {
                      '': '',
                    })
                    nodeList[index] = newItem
                    setState({ nodeList })
                  }}
                >
                  +
                </button>
                <br />
                <button
                  className='px-2 mt-1'
                  onClick={() => {
                    const nodeList = state.nodeList.concat()
                    const newItem = nodeList[index].concat()
                    nodeList.splice(index + 1, 0, newItem)
                    setState({ nodeList })
                  }}
                >
                  duplicate this one
                </button>
                <br />
                <button
                  className='mt-1 px-2'
                  onClick={() => {
                    if (!window.confirm('delete this one?')) return
                    const nodeList = state.nodeList.concat()
                    nodeList.splice(index, 1)
                    setState({ nodeList })
                  }}
                >
                  delete this one
                </button>
              </div>
            )
          })}
        </div>
      </div>
      <div className='mt-3'>
        <h2>output configs</h2>
        <div className='mb-1'>
          <button
            className='p-2'
            onClick={() => {
              NodesStore.setNodesInput(output)
            }}
          >
            save(set to input)
          </button>
          <button
            className='p-2 ml-2'
            onClick={() => {
              copy(output)
            }}
          >
            copy
          </button>
        </div>
        <textarea
          readOnly
          value={output}
          rows={10}
          className='w-full'
        ></textarea>
      </div>
      <div className='mt-3'>
        <h2>output v2ray configs</h2>
        <div className='mb-1'>
          <button
            className='p-2'
            onClick={() => {
              copy(btoa(output))
            }}
          >
            copy
          </button>
        </div>
        <textarea
          readOnly
          value={btoa(output)}
          rows={10}
          className='w-full'
        ></textarea>
      </div>
      <div className='mt-3 pb-10'>
        <form
          onSubmit={(e) => {
            e.preventDefault()
            const gistId = (
              document.getElementById('gist-id') as HTMLInputElement
            ).value
            const githubToken = (
              document.getElementById('github-token') as HTMLInputElement
            ).value
            fetch(`https://api.github.com/gists/${gistId}`, {
              method: 'PATCH',
              headers: {
                Authorization: `token ${githubToken}`,
              },
              body: JSON.stringify({
                files: {
                  o: {
                    content: output,
                  },
                  b: {
                    content: btoa(output),
                  },
                },
              }),
            })
              .then((res) => {
                alert('更新成功')
                res.json().then((data) => {
                  console.log(data)
                })
              })
              .catch((err) => {
                alert(`更新失败: ${err.toString()}`)
              })
          }}
        >
          <div>
            <label htmlFor='gist-id'>github gist id: </label>
            <input
              id='gist-id'
              type='text'
              className='w-72'
              required
              value={NodesStore.gistId}
              onChange={(e) => NodesStore.setGistId(e.target.value)}
            />
          </div>
          <div>
            <label htmlFor='github-token'>github token: </label>
            <input
              id='github-token'
              type='text'
              className='w-96'
              required
              value={NodesStore.githubToken}
              onChange={(e) => NodesStore.setGithubToken(e.target.value)}
            />
          </div>
          <button
            type='submit'
            className='p-2 mt-2'
            onSubmit={(e) => {
              console.log(e)
            }}
          >
            save to github gist
          </button>
        </form>
      </div>
    </main>
  )
}
