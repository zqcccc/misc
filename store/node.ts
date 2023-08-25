import { create } from 'zustand'
import { StorageValue, persist } from 'zustand/middleware'

export interface NodesStore {
  nodesInput: string
  nodeMap: Record<string, any>
  getIp: (ip: string) => any
  setIp: (ip: string, value: any) => void
  setNodesInput: (nodesInput: string) => void
}

export const useNodesStore = create<NodesStore>()(
  persist(
    (set, get) => ({
      nodesInput: '',
      nodeMap: {},
      getIp: (ip: string) => get().nodeMap[ip],
      setIp: (ip: string, value: any) =>
        set({ nodeMap: { ...get().nodeMap, [ip]: value } }),
      setNodesInput: (nodesInput: string) => set({ nodesInput }),
    }),
    {
      name: 'node-storage',
    }
  )
)
