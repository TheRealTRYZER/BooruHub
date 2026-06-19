import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from '../../stores/auth'

// Mock api methods
vi.mock('../../api', () => {
  return {
    apiLogin: vi.fn(() => Promise.resolve({
      access_token: 'new-access-token',
      refresh_token: 'new-refresh-token',
      token_type: 'bearer',
      user: { id: 1, username: 'testuser', email: 'test@example.com', default_tags: '' }
    })),
    apiRegister: vi.fn(() => Promise.resolve({
      access_token: 'reg-access-token',
      refresh_token: 'reg-refresh-token',
      token_type: 'bearer',
      user: { id: 2, username: 'reguser', email: 'reg@example.com', default_tags: '' }
    })),
    apiLogout: vi.fn(() => Promise.resolve({ ok: true })),
    apiClearCache: vi.fn(),
    registerAuthFailureCallback: vi.fn(),
  }
})

import { apiLogin, apiRegister, apiLogout, apiClearCache } from '../../api'

describe('Auth Store', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('should initialize with null state when localStorage is empty', () => {
    const store = useAuthStore()
    expect(store.user).toBeNull()
    expect(store.isAuthenticated).toBe(false)
  })

  it('should initialize with state from localStorage if present', () => {
    localStorage.setItem('booruhub_user', JSON.stringify({ id: 99, username: 'storeduser' }))

    const store = useAuthStore()
    expect(store.user).toEqual({ id: 99, username: 'storeduser' })
    expect(store.isAuthenticated).toBe(true)
  })

  it('should handle login and persist user', async () => {
    const store = useAuthStore()
    await store.login('testuser', 'password123')

    expect(apiLogin).toHaveBeenCalledWith('testuser', 'password123')
    expect(store.user?.username).toBe('testuser')
    expect(JSON.parse(localStorage.getItem('booruhub_user') || 'null')).toEqual({ id: 1, username: 'testuser', email: 'test@example.com', default_tags: '' })
  })

  it('should handle register and persist user', async () => {
    const store = useAuthStore()
    await store.register('reguser', 'reg@example.com', 'password123', true)

    expect(apiRegister).toHaveBeenCalledWith('reguser', 'reg@example.com', 'password123', true)
    expect(store.user?.username).toBe('reguser')
    expect(JSON.parse(localStorage.getItem('booruhub_user') || 'null')).toEqual({ id: 2, username: 'reguser', email: 'reg@example.com', default_tags: '' })
  })

  it('should handle logout, call backend logout API, and clear local state', async () => {
    localStorage.setItem('booruhub_user', JSON.stringify({ id: 99, username: 'storeduser' }))

    const store = useAuthStore()
    expect(store.isAuthenticated).toBe(true)

    await store.logout()

    expect(apiLogout).toHaveBeenCalled()
    expect(apiClearCache).toHaveBeenCalled()
    expect(store.user).toBeNull()
    expect(localStorage.getItem('booruhub_user')).toBeNull()
  })
})
