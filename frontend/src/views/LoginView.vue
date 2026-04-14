<template>
  <div class="auth-container">
    <div class="auth-card">
      <h1 class="auth-title">{{ lang.t('welcome') }}</h1>
      <p class="auth-subtitle">{{ lang.t('login_subtitle') }}</p>
      
      <form class="auth-form" @submit.prevent="submit">
        <div class="input-group">
          <label class="input-label">{{ lang.t('username_email') }}</label>
          <input type="text" class="input" v-model="loginStr" :placeholder="lang.t('username_email')" required autocomplete="username">
        </div>
        <div class="input-group">
          <label class="input-label">{{ lang.t('password') }}</label>
          <input type="password" class="input" v-model="password" placeholder="••••••••" required autocomplete="current-password">
        </div>
        
        <div v-show="errorMsg" style="color:var(--danger);font-size:var(--font-sm);">{{ errorMsg }}</div>
        
        <button type="submit" class="btn btn-primary" :disabled="loading">
          {{ loading ? lang.t('signing_in') : lang.t('login') }}
        </button>
      </form>
      
      <div class="auth-switch">
        {{ lang.t('no_account') }} <a href="#" @click.prevent="$router.push('/register')">{{ lang.t('create_account') }}</a>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useToastStore } from '../stores/toast'
import { useLangStore } from '../stores/lang'

const router = useRouter()
const auth = useAuthStore()
const toast = useToastStore()
const lang = useLangStore()

const loginStr = ref('')
const password = ref('')
const loading = ref(false)
const errorMsg = ref('')

async function submit() {
  errorMsg.value = ''
  if (!loginStr.value || !password.value) {
    errorMsg.value = lang.t('fill_fields')
    return
  }

  loading.value = true
  try {
    await auth.login(loginStr.value, password.value)
    toast.show(lang.t('logged_in_msg'), 'success')
    router.push('/')
  } catch(e: any) {
    errorMsg.value = e.message || String(e)
  } finally {
    loading.value = false
  }
}
</script>
