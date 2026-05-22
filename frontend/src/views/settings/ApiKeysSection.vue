<template>
  <div class="settings-section">
    <div class="settings-title">🔑 {{ lang.t('api_keys_section') }}</div>
    <div class="api-keys-list">
      <div>
        <label class="input-label site-label danbooru">
          Danbooru (Login / API Key) <span v-if="statusFlags.danbooru" class="status-indicator">✅</span>
        </label>
        <div class="credential-fields">
          <input type="text" class="input input-login" v-model="keys.danbooru_login" placeholder="Login" autocomplete="off">
          <input type="password" class="input input-key" v-model="keys.danbooru_api_key" placeholder="Key" autocomplete="new-password">
        </div>
      </div>
      
      <div>
        <label class="input-label site-label e621">
          e621 (Login / API Key) <span v-if="statusFlags.e621" class="status-indicator">✅</span>
        </label>
        <div class="credential-fields">
          <input type="text" class="input input-login" v-model="keys.e621_login" placeholder="Login" autocomplete="off">
          <input type="password" class="input input-key" v-model="keys.e621_api_key" placeholder="Key" autocomplete="new-password">
        </div>
      </div>

      <div>
        <label class="input-label site-label rule34">
          Rule34 (User ID / API Key) <span v-if="statusFlags.rule34" class="status-indicator">✅</span>
        </label>
        <div class="credential-fields">
          <input type="text" class="input input-login" v-model="keys.rule34_user_id" placeholder="ID" autocomplete="off">
          <input type="password" class="input input-key" v-model="keys.rule34_api_key" placeholder="Key" autocomplete="new-password">
        </div>
      </div>

      <div class="search-params-section">
        <div class="section-subtitle">⚙️ {{ lang.t('search_params') }}</div>
        <div class="params-row">
          <div class="param-col">
            <label class="input-label">{{ lang.t('posts_limit') }}</label>
            <input type="number" class="input" v-model.number="keys.search_limit" min="10" max="100">
          </div>
          <div class="param-col">
            <label class="input-label">{{ lang.t('search_interval') }}</label>
            <input type="number" class="input" v-model.number="keys.search_interval" min="0" max="10" step="0.1">
          </div>
        </div>
      </div>
      
      <button class="btn btn-primary" @click="saveKeys" :disabled="savingKeys">{{ lang.t('save_settings') }}</button>
      
      <div class="keys-configured-text">
        <span v-if="keysConfiguredSites.length === 0">{{ lang.t('keys_not_set') }}</span>
        <span v-else>
          {{ lang.t('keys_configured') }}
          <template v-for="(site, i) in keysConfiguredSites" :key="site">
            <span class="configured-site" :class="site">{{ site }}</span>
            <template v-if="i < keysConfiguredSites.length - 1">, </template>
          </template>
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useToastStore } from '../../stores/toast'
import { useLangStore } from '../../stores/lang'
import { apiGetApiKeysStatus, apiUpdateApiKeys } from '../../api'
import type { ApiKeysStatus, ApiKeysUpdate } from '../../types'

const toast = useToastStore()
const lang = useLangStore()

const statusFlags = ref({ danbooru: false, e621: false, rule34: false })
const keysConfiguredSites = ref<string[]>([])
const savingKeys = ref(false)

const keys = ref({
  danbooru_login: '', danbooru_api_key: '',
  e621_login: '', e621_api_key: '',
  rule34_user_id: '', rule34_api_key: '',
  search_limit: 40, search_interval: 0.0
})

async function loadKeysStatus() {
  try {
    const status: ApiKeysStatus = await apiGetApiKeysStatus()
    const s: string[] = []
    if (status.danbooru) s.push('danbooru')
    if (status.e621) s.push('e621')
    if (status.rule34) s.push('rule34')
    
    keysConfiguredSites.value = s
    
    if (status.search_limit) keys.value.search_limit = status.search_limit
    if (status.search_interval !== undefined && status.search_interval !== null) keys.value.search_interval = status.search_interval
    
    keys.value.danbooru_login = status.danbooru_login || ''
    keys.value.e621_login = status.e621_login || ''
    keys.value.rule34_user_id = status.rule34_user_id || ''
    
    statusFlags.value.danbooru = status.danbooru
    statusFlags.value.e621 = status.e621
    statusFlags.value.rule34 = status.rule34
  } catch (e) {
    keysConfiguredSites.value = []
  }
}

async function saveKeys() {
  savingKeys.value = true
  const data: ApiKeysUpdate = { ...keys.value }
  
  if(!data.danbooru_api_key) delete data.danbooru_api_key
  if(!data.e621_api_key) delete data.e621_api_key
  if(!data.rule34_api_key) delete data.rule34_api_key

  try {
    await apiUpdateApiKeys(data)
    toast.show(lang.t('settings_saved'), 'success')
    keys.value.danbooru_api_key = ''
    keys.value.e621_api_key = ''
    keys.value.rule34_api_key = ''
    await loadKeysStatus()
  } catch(e: any) {
    toast.show(e.message || e, 'error')
  } finally {
    savingKeys.value = false
  }
}

onMounted(() => {
  loadKeysStatus()
})
</script>

<style scoped>
.api-keys-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.site-label {
  font-size: 11px;
  font-weight: 700;
  display: flex;
  align-items: center;
  gap: 6px;
  text-transform: uppercase;
}
.site-label.danbooru { color: var(--danbooru); }
.site-label.e621 { color: var(--e621); }
.site-label.rule34 { color: var(--rule34); }
.status-indicator {
  color: var(--success);
  font-size: 12px;
}
.credential-fields {
  display: flex;
  gap: 8px;
  margin-top: 4px;
}
.input-login {
  width: 100px;
}
.input-key {
  flex: 1;
}
.search-params-section {
  margin-top: 8px;
  border-top: 1px solid rgba(128,128,128,0.1);
  padding-top: 16px;
}
.section-subtitle {
  font-weight: 700;
  font-size: 13px;
  margin-bottom: 12px;
  color: var(--text-primary);
}
.params-row {
  display: flex;
  gap: 16px;
  margin-bottom: 8px;
}
.param-col {
  flex: 1;
}
.keys-configured-text {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 4px;
}
.configured-site {
  font-weight: 700;
  text-transform: capitalize;
}
.configured-site.danbooru { color: var(--danbooru); }
.configured-site.e621 { color: var(--e621); }
.configured-site.rule34 { color: var(--rule34); }
</style>
