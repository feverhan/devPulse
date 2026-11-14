<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuth } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuth()

const password = ref('')
const loading = ref(false)

async function submit() {
  loading.value = true
  try {
    await auth.login(password.value)
    const redirect = (route.query.redirect as string) || '/dashboard'
    router.replace(redirect)
  } catch {
    password.value = ''
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-wrap">
    <form class="login-card" @submit.prevent="submit">
      <div class="login-brand">
        <span class="brand-mark">DP</span>
        <span class="login-title">
          研发脉冲
          <em class="login-sub">DEV PULSE</em>
        </span>
      </div>
      <el-input
        v-model="password"
        type="password"
        show-password
        placeholder="访问密码"
        size="large"
        autofocus
        @keyup.enter="submit"
      />
      <el-button
        type="primary"
        size="large"
        class="login-submit"
        style="width: 100%; margin-top: 14px"
        native-type="submit"
        :loading="loading"
      >
        登录
      </el-button>
    </form>
  </div>
</template>

<style scoped>
.login-submit {
  letter-spacing: 2px;
}
</style>