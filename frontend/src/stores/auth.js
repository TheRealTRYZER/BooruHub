import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { apiLogin, apiRegister } from '../api.js'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('booruhub_token') || null)
  const user = ref(JSON.parse(localStorage.getItem('booruhub_user') || 'null'))

  const isAuthenticated = computed(() => !!token.value)

  function setAuth(newToken, newUser) {
    token.value = newToken
    user.value = newUser
    localStorage.setItem('booruhub_token', newToken)
    localStorage.setItem('booruhub_user', JSON.stringify(newUser))
  }

  async function login(loginStr, password) {
    const data = await apiLogin(loginStr, password)
    setAuth(data.access_token, data.user)
    return data
  }

  async function register(username, email, password) {
    const data = await apiRegister(username, email, password)
    setAuth(data.access_token, data.user)
    return data
  }

  function logout() {
    token.value = null
    user.value = null
    localStorage.removeItem('booruhub_token')
    localStorage.removeItem('booruhub_user')
  }

  function updateUser(updates) {
    if (user.value) {
      user.value = { ...user.value, ...updates }
      localStorage.setItem('booruhub_user', JSON.stringify(user.value))
    }
  }

  return { token, user, isAuthenticated, login, register, logout, setAuth, updateUser }
})
