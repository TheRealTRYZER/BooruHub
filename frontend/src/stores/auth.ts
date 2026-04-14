import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { apiLogin, apiRegister, apiClearCache } from '../api'
import type { User } from '../types'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('booruhub_token') || null)
  const user = ref<User | null>((() => {
    try {
      return JSON.parse(localStorage.getItem('booruhub_user') || 'null')
    } catch {
      return null
    }
  })())

  const isAuthenticated = computed(() => !!token.value)

  function setAuth(newToken: string, newUser: User) {
    token.value = newToken
    user.value = newUser
    localStorage.setItem('booruhub_token', newToken)
    localStorage.setItem('booruhub_user', JSON.stringify(newUser))
  }

  async function login(loginStr: string, password: string) {
    const data = await apiLogin(loginStr, password)
    setAuth(data.access_token, data.user)
    return data
  }

  async function register(username: string, email: string, password: string, dataConsent = false) {
    const data = await apiRegister(username, email, password, dataConsent)
    setAuth(data.access_token, data.user)
    return data
  }

  function logout() {
    token.value = null
    user.value = null
    localStorage.removeItem('booruhub_token')
    localStorage.removeItem('booruhub_user')
    apiClearCache()
  }

  function updateUser(updates: Partial<User>) {
    if (user.value) {
      user.value = { ...user.value, ...updates }
      localStorage.setItem('booruhub_user', JSON.stringify(user.value))
    }
  }

  return { token, user, isAuthenticated, login, register, logout, setAuth, updateUser }
})
