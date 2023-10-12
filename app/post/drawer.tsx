'use client'

import * as React from 'react'
import ReactDOM from 'react-dom'

import './drawer.css'

const getContentStyle = ({
  visible,
  placement = 'left',
  width = 256,
  height = 256,
  duration = '.3s',
  ease = 'cubic-bezier(0.78, 0.14, 0.15, 0.86)',
}: any) => {
  const styles: any = {
    transition: `transform ${duration} ${ease}`,
  }
  if (placement === 'left' || placement === 'right') {
    styles.transform = `translateX(${
      placement === 'left' && visible ? '0' : '-100%'
    })`
    styles.width = width
  }
  if (placement === 'top' || placement === 'bottom') {
    // styles.transform = `translateY(${placement === 'top' ? 'height' : -height}px)`
    // styles.height = height
  }
  return styles
}
const getMaskStyle = ({ visible, maskStyle = {} }: any) => {
  return Object.assign(
    {
      height: visible ? '100%' : undefined,
    },
    maskStyle
  )
}
const getDrawStyle = ({ visible }: any) => {
  return {
    width: visible ? '100%' : undefined,
  }
}
const Drawer = (props: any) => {
  const {
    visible = false,
    showMask = true,
    prefixCls = 'drawer',
    maskClosable = true,
    onClose = (_: any) => _,
    children,
    onClick,
    placement = 'left',
  } = props

  return ReactDOM.createPortal(
    <div
      className={`drawer drawer-wrapper drawer-${placement} ${
        visible ? 'drawer-open' : ''
      }`}
      style={getDrawStyle({ visible })}
    >
      {showMask && (
        <div
          className={`drawer-mask`}
          onClick={maskClosable ? onClick : undefined}
          style={getMaskStyle(props)}
        />
      )}
      <div className='drawer-content-wrapper' style={getContentStyle(props)}>
        <div className={`drawer-content`}>{children}</div>
        <div className='drawer-handler' onClick={onClick}>
          <i className='drawer-handle-icon'></i>
        </div>
      </div>
    </div>,
    document.body
  )
}

export default Drawer
