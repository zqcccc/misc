'use client'
import { ReactNode } from 'react'
import { DndProvider } from 'react-dnd'
import { HTML5Backend } from 'react-dnd-html5-backend'

type DndWrapperProps = {
  children: ReactNode
}

export default function VmessDndWrapper({ children }: DndWrapperProps) {
  return <DndProvider backend={HTML5Backend}>{children}</DndProvider>
}
