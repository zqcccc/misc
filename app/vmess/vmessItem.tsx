import { ChangeEvent, useRef } from 'react'
import type { Identifier, XYCoord } from 'dnd-core'
import { useDrag, useDrop } from 'react-dnd'

type VmessItemProps = {
  item: any
  index: number
  onKeyChange: (key: string) => (e: ChangeEvent<HTMLInputElement>) => void
  onValueChange: (key: string) => (e: ChangeEvent<HTMLInputElement>) => void
  onCopy: () => void
  onAddField: () => void
  onDeleteField: (key: string) => () => void
  onDuplicate: () => void
  onDelete: () => void
  moveItem: (dragIndex: number, hoverIndex: number) => void
  moveToLast: (index: number) => void
}

interface DragItem {
  index: number
  id: string
  type: string
}

const VmessItem = (props: VmessItemProps) => {
  const {
    item,
    index,
    onKeyChange,
    onValueChange,
    onCopy,
    onAddField,
    onDeleteField,
    onDuplicate,
    onDelete,
    moveItem,
    moveToLast,
  } = props
  const ref = useRef<HTMLDivElement>(null)
  const moveRef = useRef<HTMLDivElement>(null)
  const keys = Object.keys(item)
  const id = `${Object.values(item).join(',')}_${index}`
  const [{ handlerId }, drop] = useDrop<
    DragItem,
    void,
    { handlerId: Identifier | null }
  >({
    accept: 'Vmess',
    collect(monitor) {
      return {
        handlerId: monitor.getHandlerId(),
      }
    },
    hover(item: DragItem, monitor) {
      if (!ref.current) {
        return
      }
      const dragIndex = item.index
      const hoverIndex = index

      // Don't replace items with themselves
      if (dragIndex === hoverIndex) {
        return
      }

      // Determine rectangle on screen
      // const hoverBoundingRect = ref.current?.getBoundingClientRect()

      // Get vertical middle
      // const hoverMiddleY =
      // (hoverBoundingRect.bottom - hoverBoundingRect.top) / 2

      // Determine mouse position
      // const clientOffset = monitor.getClientOffset()

      // Get pixels to the top
      // const hoverClientY = (clientOffset as XYCoord).y - hoverBoundingRect.top

      // Only perform the move when the mouse has crossed half of the items height
      // When dragging downwards, only move when the cursor is below 50%
      // When dragging upwards, only move when the cursor is above 50%

      // Dragging downwards
      // if (dragIndex < hoverIndex && hoverClientY < hoverMiddleY) {
      //   return
      // }

      // // Dragging upwards
      // if (dragIndex > hoverIndex && hoverClientY > hoverMiddleY) {
      //   return
      // }

      // Time to actually perform the action
      moveItem(dragIndex, hoverIndex)

      // Note: we're mutating the monitor item here!
      // Generally it's better to avoid mutations,
      // but it's good here for the sake of performance
      // to avoid expensive index searches.
      item.index = hoverIndex
    },
  })

  const [{ isDragging }, drag] = useDrag({
    type: 'Vmess',
    item: () => {
      return { id, index }
    },
    collect: (monitor: any) => ({
      isDragging: monitor.isDragging(),
    }),
  })
  drag(drop(ref))
  return (
    <div
      className={`m-3 max-w-[250px] ${isDragging ? 'border' : ''}`}
      ref={ref}
      data-handler-id={handlerId}
    >
      <h3>
        No.{index} {item?.ps && `name:${item?.ps}`}
      </h3>
      {keys.map((key, keyIndex) => {
        return (
          <div key={keyIndex}>
            <input className='w-12' value={key} onChange={onKeyChange(key)} />
            <span> : </span>
            <input value={item[key]} onChange={onValueChange(key)}></input>
            <button className='px-1 ml-1' onClick={onDeleteField(key)}>
              x
            </button>
          </div>
        )
      })}
      <div className='flex'>
        <div className='mr-3'>
          <button className='px-3 mt-1' onClick={onAddField}>
            +
          </button>
          <button className='px-3 mt-1 ml-1' onClick={onCopy}>
            copy
          </button>
          <br />
          <button className='px-2 mt-1' onClick={onDuplicate}>
            duplicate this one
          </button>
          <br />
          <button className='mt-1 px-2' onClick={onDelete}>
            delete this one
          </button>
          <br />
          <button className='mt-1 px-2' onClick={() => moveItem(index, 0)}>
            move to fist one
          </button>
          <br />
          <button className='mt-1 px-2' onClick={() => moveToLast(index)}>
            move to last one
          </button>
        </div>
      </div>
    </div>
  )
}

export default VmessItem
