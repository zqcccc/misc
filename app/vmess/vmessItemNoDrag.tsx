import { ChangeEvent, useRef } from 'react'

type VmessItemNoDragProps = {
  item: any
  index: number
  onKeyChange?: (key: string) => (e: ChangeEvent<HTMLInputElement>) => void
  onValueChange?: (key: string) => (e: ChangeEvent<HTMLInputElement>) => void
  onCopy?: () => void
  onAddField?: () => void
  onDeleteField?: (key: string) => () => void
  onDuplicate?: () => void
  onDelete?: () => void
}

export const VmessItemWithoutDrag = (props: VmessItemNoDragProps) => {
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
  } = props
  const ref = useRef<HTMLDivElement>(null)
  const keys = Object.keys(item)
  return (
    <div className={`m-3 max-w-[250px]`} ref={ref}>
      <h3>
        No.{index} {item?.ps && `name:${item?.ps}`}
      </h3>
      {keys.map((key, keyIndex) => {
        return (
          <div key={keyIndex}>
            {onKeyChange ? (
              <input className='w-12' value={key} onChange={onKeyChange(key)} />
            ) : (
              <span>{key}</span>
            )}
            <span> : </span>
            {onValueChange ? (
              <input value={item[key]} onChange={onValueChange(key)}></input>
            ) : (
              <span>{item[key]}</span>
            )}
            {onDeleteField && (
              <button className='px-1 ml-1' onClick={onDeleteField?.(key)}>
                x
              </button>
            )}
          </div>
        )
      })}
      <div className='flex'>
        <div className='mr-3'>
          {onAddField && (
            <button className='px-3 mt-1' onClick={onAddField}>
              +
            </button>
          )}
          {onCopy && (
            <>
              <button className='px-3 mt-1 ml-1' onClick={onCopy}>
                copy
              </button>
            </>
          )}
          {onDuplicate && (
            <>
              <br />
              <button className='px-2 mt-1' onClick={onDuplicate}>
                duplicate this one
              </button>
            </>
          )}
          {onDelete && (
            <>
              <br />
              <button className='mt-1 px-2' onClick={onDelete}>
                delete this one
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

export default VmessItemWithoutDrag
