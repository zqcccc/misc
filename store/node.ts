import { create } from 'zustand'
import { StorageValue, persist } from 'zustand/middleware'

export interface NodesStore {
  nodesInput: string
  gistId: string
  githubToken: string
  nodeMap: Record<string, any>
  getIp: (ip: string) => any
  setIp: (ip: string, value: any) => void
  setNodesInput: (nodesInput: string) => void
  setGistId: (gistId: string) => void
  setGithubToken: (githubToken: string) => void
}

export const useNodesStore = create<NodesStore>()(
  persist(
    (set, get) => ({
      nodesInput: '',
      gistId: '',
      githubToken: '',
      nodeMap: {},
      setGistId: (gistId: string) => set({ gistId }),
      setGithubToken: (githubToken: string) => set({ githubToken }),
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
