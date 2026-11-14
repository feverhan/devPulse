import { defineStore } from 'pinia'
import { ref } from 'vue'
import http from '@/api/client'
import { pinia } from './index'

export const useAuthStore = defineStore(
  'auth',
  () => {
    const passwordRequired = ref(false)
    const authenticated = ref(false)
    const checked = ref(false)

    async function check() {
      try {
        const { data } = await http.get<{ authenticated: boolean; password_required: boolean }>('/auth/me')
        passwordRequired.value = data.password_required
        authenticated.value = data.authenticated
      } catch {
        passwordRequired.value = false
        authenticated.value = true
      } finally {
        checked.value = true
      }
    }

    async function login(password: string) {
      const { data } = await http.post<{ ok: boolean; password_required: boolean }>('/auth/login', { password })
      passwordRequired.value = data.password_required
      authenticated.value = true
      checked.value = true
    }

    async function logout() {
      await http.post('/auth/logout')
      authenticated.value = false
    }

    return { passwordRequired, authenticated, checked, check, login, logout }
  },
)

export function useAuth() {
  return useAuthStore(pinia)
}