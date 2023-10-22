'use client'

import { useNodesStore } from '@/store/node'
import { useSetState } from 'ahooks'
import { Button, Input, InputNumber, message } from 'antd'
import { Base64 } from 'js-base64'
import { useEffect, useMemo } from 'react'
import { getRandom } from '../utils'
import { VmessItemWithoutDrag } from '../vmessItem'
import { copy } from '@/app/post/[...id]/helpers'

const Pick = () => {
  const NodesStore = useNodesStore()
  const [state, setState] = useSetState({
    filterWord: '',
    filterNumber: 2,
    nodeList: [] as any[],
    willGetLoc: true,
    isSubmitting: false,
  })

  const getAll = () =>
    NodesStore.nodesInput
      .split('\n')
      .map((item) => {
        try {
          const [protocol, base64Str] = item.split('://')
          const jsonStr = Base64.decode(base64Str)
          const obj = JSON.parse(jsonStr)
          return [protocol, obj]
        } catch (e) {
          return false
        }
      })
      .filter(Boolean) as [string, any][]
  const showList = () => {
    setState({
      nodeList: getAll(),
    })
  }
  const filterHandle = () => {
    if (!state.filterWord || !state.filterNumber) return
    const list = getAll().filter((item) => {
      const [protocol, obj] = item
      const values = Object.values(obj) as string[]
      if (
        values.some(
          (i) =>
            i &&
            i.toString().toLowerCase().includes(state.filterWord.toLowerCase())
        )
      ) {
        return true
      }
      return false
    })
    setState({ nodeList: getRandom(list, state.filterNumber) })
  }
  useEffect(() => {
    if (state.nodeList.length) return
    showList()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [NodesStore.nodesInput])

  const output = useMemo(() => {
    return state.nodeList
      .map(([protocol, obj]) => {
        const base64Str = Base64.encode(JSON.stringify(obj))
        return `${protocol}://${base64Str}`
      })
      .join('\n')
  }, [state.nodeList])

  return (
    <div className='p-4'>
      <h1>Pick</h1>
      <Input.TextArea
        rows={12}
        value={NodesStore.nodesInput}
        onChange={(e) => {
          NodesStore.setNodesInput(e.target.value)
        }}
      />
      <div className='mt-2'>
        <span>过滤词：</span>
        <Input
          className='w-48'
          value={state.filterWord}
          onChange={(e) => setState({ filterWord: e.target.value })}
          onPressEnter={filterHandle}
        />
        <span className='ml-2'>过滤数量：</span>
        <InputNumber
          value={state.filterNumber}
          onChange={(e) => setState({ filterNumber: e || 0 })}
          onPressEnter={filterHandle}
        />
        <Button className='ml-2' onClick={filterHandle}>
          过滤
        </Button>
      </div>
      <div className='mt-2'>
        <div className='flex w-full flex-wrap'>
          {state.nodeList.map(([_, item], index) => (
            <VmessItemWithoutDrag
              key={index}
              item={item}
              index={index}
              onCopy={() => {
                copy(output.split('\n').filter(Boolean)[index])
              }}
            />
          ))}
        </div>
      </div>
      <div className='mt-2'>
        <span>Filter list：</span>
        <Input.TextArea rows={12} value={output} readOnly />
        <Button
          className='mt-2'
          onClick={() => {
            copy(output)
            message.info('已复制')
          }}
        >
          Copy
        </Button>
      </div>
    </div>
  )
}

export default Pick
