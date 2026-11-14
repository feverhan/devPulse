import { defineStore } from 'pinia'
import { ref } from 'vue'
import { setupApi } from '@/api'
import type { SetupStatus } from '@/api/types'
import { pinia } from './index'

export const useSetupStore = defineStore(
  'setup',
  () => {
    const status = ref<SetupStatus | null>(null)
    const loaded = ref(false)
    const loading = ref(false)

    async function load(force = false): Promise<SetupStatus | null> {
      if (loaded.value && !force) return status.value
      loading.value = true
      try {
        status.value = await setupApi.status()
      } catch {
        status.value = null
      } finally {
        loaded.value = true
        loading.value = false
      }
      return status.value
    }

    async function refresh(): Promise<SetupStatus | null> {
      loaded.value = false
      return load(true)
    }

    return { status, loaded, loading, load, refresh }
  },
)

export function useSetup() {
  return useSetupStore(pinia)
}