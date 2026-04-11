<template>
  <div class="auth-container">
    <div class="auth-card">
      <h1 class="auth-title">{{ lang.t('create_title') }}</h1>
      <p class="auth-subtitle">{{ lang.t('login_subtitle') }}</p>
      
      <form class="auth-form" @submit.prevent="submit">
        <div class="input-group">
          <label class="input-label">{{ lang.t('nav_feed') }}</label>
          <input type="text" class="input" v-model="username" placeholder="username" required minlength="3" autocomplete="username">
        </div>
        <div class="input-group">
          <label class="input-label">Email</label>
          <input type="email" class="input" v-model="email" placeholder="you@example.com" required autocomplete="email">
        </div>
        <div class="input-group">
          <label class="input-label">{{ lang.t('password') }}</label>
          <input type="password" class="input" v-model="password" :placeholder="lang.t('password')" required minlength="6" autocomplete="new-password">
        </div>
        
        <div v-show="errorMsg" style="color:var(--danger);font-size:var(--font-sm);">{{ errorMsg }}</div>
        
        <button type="submit" class="btn btn-primary" :disabled="loading">
          {{ loading ? lang.t('registering') : lang.t('register_btn') }}
        </button>
      </form>
      
      <div class="auth-switch">
        {{ lang.t('already_have') }} <a href="#" @click.prevent="$router.push('/login')">{{ lang.t('login') }}</a>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'
import { useToastStore } from '../stores/toast.js'
import { useLangStore } from '../stores/lang.js'

const router = useRouter()
const auth = useAuthStore()
const toast = useToastStore()
const lang = useLangStore()

const username = ref('')
const email = ref('')
const password = ref('')
const loading = ref(false)
const errorMsg = ref('')

async function submit() {
  errorMsg.value = ''
  if (!username.value || !email.value || !password.value) {
    errorMsg.value = lang.t('fill_fields')
    return
  }

  loading.value = true
  try {
    await auth.register(username.value, email.value, password.value)
    toast.show(lang.t('logged_in_msg'), 'success')
    router.push('/')
  } catch(e) {
    errorMsg.value = e.message
  } finally {
    loading.value = false
  }
}
</script>
