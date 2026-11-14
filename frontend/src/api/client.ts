import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router'

const http = axios.create({
  baseURL: '/api',
  timeout: 120000,
  withCredentials: true,
})

http.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error?.response?.status
    const detail = error?.response?.data?.detail
    if (status === 401) {
      const current = router.currentRoute.value
      if (current.name !== 'login') {
        router.replace({ name: 'login', query: { redirect: current.fullPath } })
      }
    } else if (typeof detail === 'string' && detail) {
      ElMessage.error(detail)
    } else if (error?.message) {
      ElMessage.error(error.message)
    }
    return Promise.reject(error)
  },
)

export default http