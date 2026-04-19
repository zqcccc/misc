'use client'

import { useNodesStore } from '@/store/node'
import { useSetState } from 'ahooks'
import { useEffect, useMemo } from 'react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { getRandom, parseNodeLines, serializeNodeLines } from '../utils'
import { VmessItemWithoutDrag } from '../vmessItemNoDrag'
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

  const getAll = () => parseNodeLines(NodesStore.nodesInput)
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
    return serializeNodeLines(state.nodeList)
  }, [state.nodeList])

  return (
    <div className='p-4'>
      <h1>Pick</h1>
      <Textarea
        rows={12}
        value={NodesStore.nodesInput}
        onChange={(e) => {
          NodesStore.setNodesInput(e.target.value)
        }}
      />
      <div className='mt-2 flex items-center gap-2 flex-wrap'>
        <span>过滤词：</span>
        <Input
          type='text'
          className='w-48'
          value={state.filterWord}
          onChange={(e) => setState({ filterWord: e.target.value })}
          onKeyDown={(e) => {
            if (e.key === 'Enter') filterHandle()
          }}
        />
        <span>过滤数量：</span>
        <Input
          type='number'
          className='w-24'
          value={state.filterNumber}
          onChange={(e) => setState({ filterNumber: Number(e.target.value) || 0 })}
          onKeyDown={(e) => {
            if (e.key === 'Enter') filterHandle()
          }}
        />
        <Button variant='outline' onClick={filterHandle}>
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
        <Textarea rows={12} value={output} readOnly />
        <Button
          variant='outline'
          className='mt-2'
          onClick={() => {
            copy(output)
            toast.info('已复制')
          }}
        >
          Copy
        </Button>
      </div>
    </div>
  )
}

export default Pick
