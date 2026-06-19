import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { apiLogin, apiRegister, apiClearCache, apiLogout, registerAuthFailureCallback } from '../api'
import { apiClearEventLoggerState } from '../composables/useEventLogger'
import type { User } from '../types'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>((() => {
    try {
      return JSON.parse(localStorage.getItem('booruhub_user') || 'null')
    } catch {
      return null
    }
  })())

  const isAuthenticated = computed(() => !!user.value)

  function setAuth(newUser: User) {
    user.value = newUser
    localStorage.setItem('booruhub_user', JSON.stringify(newUser))
  }

  async function login(loginStr: string, password: string) {
    const data = await apiLogin(loginStr, password)
    setAuth(data.user)
    return data
  }

  async function register(username: string, email: string, password: string, dataConsent = false) {
    const data = await apiRegister(username, email, password, dataConsent)
    setAuth(data.user)
    return data
  }

  async function logout() {
    try {
      await apiLogout()
    } catch (e) {
      console.error('Logout request failed:', e)
    }
    user.value = null
    localStorage.removeItem('booruhub_user')
    apiClearCache()
    apiClearEventLoggerState()
  }

  function updateUser(updates: Partial<User>) {
    if (user.value) {
      user.value = { ...user.value, ...updates }
      localStorage.setItem('booruhub_user', JSON.stringify(user.value))
    }
  }

  // Register token refresh failure callback to reset store state cleanly
  registerAuthFailureCallback(() => {
    user.value = null
    localStorage.removeItem('booruhub_user')
    apiClearEventLoggerState()
  })

  return { user, isAuthenticated, login, register, logout, setAuth, updateUser }
})
