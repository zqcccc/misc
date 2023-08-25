'use client'

import { useSetState } from 'ahooks'
import { Base64 } from 'js-base64'

export default function Preferential() {
  const [state, setState] = useSetState({
    input: '',
    ips: [] as string[],
    name: '',
    output: '',
  })

  return (
    <main className='m-3'>
      <h2>优选节点替换</h2>
      <div className='mt-3'>
        <h2>原始节点</h2>
        <textarea
          rows={5}
          className='w-full'
          value={state.input}
          onChange={(e) => setState({ input: e.target.value })}
        ></textarea>
      </div>
      <div className='mt-3'>
        <h2>写入 ip 或域名</h2>
        <textarea
          rows={10}
          className='w-full'
          placeholder='一行一个，自动去重'
          value={state.ips.join('\n')}
          onChange={(e) => {
            const ips = e.target.value
              .split('\n')
              .filter(
                (item, index, list) => item && list.indexOf(item) === index
              )
            setState({ ips })
          }}
        ></textarea>
        <button
          onClick={() => {
            try {
              const [protocol, base64Str] = state.input.split('://')
              const config = JSON.parse(Base64.decode(base64Str))
              const newConfigs = state.ips.map((ip) => {
                return `${protocol}://${Base64.encode(
                  JSON.stringify(
                    Object.assign({}, config, {
                      add: ip,
                      host: config.add,
                      port: '443',
                    })
                  )
                )}`
              })
              setState({ output: newConfigs.join('\n') })
            } catch (error) {
              console.log(
                '%c error: ',
                'font-size:12px;background-color: #9E9689;color:#fff;',
                error
              )
              alert('检查你的输入')
            }
          }}
        >
          替换
        </button>
        <textarea
          className='mt-3 w-full'
          rows={10}
          value={state.output}
          readOnly
        ></textarea>
      </div>
    </main>
  )
}
