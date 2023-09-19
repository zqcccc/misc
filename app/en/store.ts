import { create } from 'zustand'
import { StorageValue, persist } from 'zustand/middleware'

export interface WordStore {
  wordMap: Record<string, any>
  getWord: (ip: string) => any
  saveWord: (ip: string, value: any) => void
}

export const useWordStore = create<WordStore>()(
  persist(
    (set, get) => ({
      wordMap: {},
      getWord: (word: string) => get().wordMap[word],
      saveWord: (word: string, value: any) =>
        set({ wordMap: { ...get().wordMap, [word]: value } }),
    }),
    {
      name: 'learning-english-storage',
    }
  )
)
