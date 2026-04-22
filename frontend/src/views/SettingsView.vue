<template>
  <div v-if="!auth.isAuthenticated" class="empty-state">
    <div class="empty-state-icon">🔒</div>
    <div class="empty-state-title">{{ lang.t('login') }}</div>
    <div class="empty-state-text">{{ lang.t('login_to_fav') }}</div>
    <button class="btn btn-primary" @click="$router.push('/login')" style="margin-top:16px;">{{ lang.t('login') }}</button>
  </div>

  <div v-else>
    <div class="page-header">
      <h1 class="page-title">⚙️ {{ lang.t('settings_title') }}</h1>
      <p class="page-subtitle">{{ lang.t('settings_subtitle') }}</p>
    </div>

    <div class="settings-layout">
      <div class="settings-col">
        <div class="settings-section">
          <div class="settings-title">👤 {{ lang.t('profile') }}</div>
          <div style="display:flex,align-items:center;gap:16px;margin-bottom:16px;">
            <div class="nav-avatar" style="width:48px;height:48px;font-size:1.2rem;">
              {{ auth.user!.username[0].toUpperCase() }}
            </div>
            <div>
              <div style="font-weight:600;font-size:var(--font-md);">{{ auth.user!.username }}</div>
              <div style="color:var(--text-muted);font-size:var(--font-sm);">{{ auth.user!.email }}</div>
            </div>
          </div>
          <div style="margin-top:16px; border-top:1px solid rgba(128,128,128,0.1); padding-top:16px;">
            <label class="input-label" style="display:block;margin-bottom:8px;">{{ lang.t('start_tags') }}</label>
            <div style="display:flex;gap:8px;">
              <input type="text" class="input" v-model="defaultTags" :placeholder="lang.t('search_placeholder')" style="flex:1;">
              <button class="btn btn-secondary" @click="saveDefaultTags" :disabled="savingTags">{{ lang.t('save') }}</button>
            </div>
          </div>
        </div>

        <div class="settings-section">
          <div class="settings-title">🔑 {{ lang.t('api_keys_section') }}</div>
          <div style="display:flex;flex-direction:column;gap:12px;">
            <div>
              <label class="input-label" style="color:var(--danbooru);font-size:10px;">
                Danbooru (Login / API Key) <span v-if="statusFlags.danbooru" style="color:var(--success)">✅</span>
              </label>
              <div style="display:flex;gap:4px;">
                <input type="text" class="input btn-sm" v-model="keys.danbooru_login" placeholder="Login" style="width:80px;" autocomplete="off">
                <input type="password" class="input btn-sm" v-model="keys.danbooru_api_key" placeholder="Key" style="flex:1;" autocomplete="new-password">
              </div>
            </div>
            <div>
              <label class="input-label" style="color:var(--e621);font-size:10px;">
                e621 (Login / API Key) <span v-if="statusFlags.e621" style="color:var(--success)">✅</span>
              </label>
              <div style="display:flex;gap:4px;">
                <input type="text" class="input btn-sm" v-model="keys.e621_login" placeholder="Login" style="width:80px;" autocomplete="off">
                <input type="password" class="input btn-sm" v-model="keys.e621_api_key" placeholder="Key" style="flex:1;" autocomplete="new-password">
              </div>
            </div>
            <div>
              <label class="input-label" style="color:var(--rule34);font-size:10px;">
                Rule34 (User ID / API Key) <span v-if="statusFlags.rule34" style="color:var(--success)">✅</span>
              </label>
              <div style="display:flex;gap:4px;">
                <input type="text" class="input btn-sm" v-model="keys.rule34_user_id" placeholder="ID" style="width:80px;" autocomplete="off">
                <input type="password" class="input btn-sm" v-model="keys.rule34_api_key" placeholder="Key" style="flex:1;" autocomplete="new-password">
              </div>
            </div>

            <div style="margin-top:8px; border-top:1px solid rgba(128,128,128,0.1); padding-top:12px;">
              <div style="font-weight:600; font-size:12px; margin-bottom:8px;">⚙️ {{ lang.t('search_params') }}</div>
              <div style="display:flex; gap:12px;">
                <div style="flex:1;">
                  <label class="input-label" style="font-size:10px;">{{ lang.t('posts_limit') }}</label>
                  <input type="number" class="input btn-sm" v-model.number="keys.search_limit" min="10" max="100">
                </div>
                <div style="flex:1;">
                  <label class="input-label" style="font-size:10px;">{{ lang.t('search_interval') }}</label>
                  <input type="number" class="input btn-sm" v-model.number="keys.search_interval" min="0" max="10" step="0.1">
                </div>
              </div>
            </div>
            
            <button class="btn btn-primary btn-sm" @click="saveKeys" :disabled="savingKeys">{{ lang.t('save_settings') }}</button>
             <span v-if="keysConfiguredSites.length === 0" style="font-size:10px;color:var(--text-muted);margin-top:4px;">{{ lang.t('keys_not_set') }}</span>
             <span v-else style="font-size:10px;color:var(--text-muted);margin-top:4px;">
               {{ lang.t('keys_configured') }}
               <template v-for="(site, i) in keysConfiguredSites" :key="site">
                 <span :style="{ color: `var(--${site})` }">{{ site }}</span><template v-if="i < keysConfiguredSites.length - 1">, </template>
               </template>
             </span>
          </div>
        </div>

        <details class="settings-section privacy-details">
          <summary class="settings-title" style="cursor:pointer; list-style:none; display:flex; align-items:center; gap:8px;">
            <span>🛡️ {{ lang.t('privacy_title') }}</span>
            <span class="disclosure-arrow">▼</span>
          </summary>
          <div style="margin-top:16px; border-top:1px solid rgba(128,128,128,0.1); padding-top:16px;">
            <p style="font-size:var(--font-sm);color:var(--text-muted);margin-bottom:16px;">
              {{ lang.t('privacy_desc') }}
              <a href="#/privacy" style="color:var(--primary);">{{ lang.t('privacy_policy') }}</a>
            </p>
            
            <div class="privacy-control">
              <div class="control-label">
                <div style="font-weight:600; font-size:14px;">{{ lang.t('consent_label') }}</div>
                <div style="font-size:11px; color:var(--text-muted);">{{ lang.t('consent_subtext', 'Allow tracking likes and views to improve recommendations') }}</div>
              </div>
              <label class="switch">
                <input type="checkbox" v-model="dataConsent" @change="toggleConsent">
                <span class="slider round"></span>
              </label>
            </div>

            <div style="display:flex; justify-content:space-between; align-items:center; margin-top:20px; padding:12px; background:rgba(0,0,0,0.2); border-radius:8px;">
              <span style="font-size:var(--font-sm);color:var(--text-secondary);">
                {{ lang.t('events_collected') }}: <strong>{{ eventCount }}</strong>
              </span>
              <button class="btn btn-danger btn-sm" @click="deleteHistory" :disabled="deletingHistory">
                🗑️ {{ lang.t('delete_history') }}
              </button>
            </div>
          </div>
        </details>
      </div>

      <div class="settings-col">
        <!-- Mappings -->
        <div class="settings-section">
          <div class="settings-title">🏷️ {{ lang.t('manual_mappings') }}</div>
          <div class="mapping-add-card">
            <div class="mapping-grid">
              <div><label class="input-label" style="font-size:10px;">Unitag</label><input type="text" class="input btn-sm" v-model="mapForm.unitag"></div>
              <div><label class="input-label" style="font-size:10px;color:var(--danbooru);">Danbooru</label><input type="text" class="input btn-sm" v-model="mapForm.danbooru"></div>
              <div><label class="input-label" style="font-size:10px;color:var(--e621);">e621</label><input type="text" class="input btn-sm" v-model="mapForm.e621"></div>
              <div><label class="input-label" style="font-size:10px;color:var(--rule34);">Rule34</label><input type="text" class="input btn-sm" v-model="mapForm.rule34"></div>
            </div>
            <button class="btn btn-sm" :class="editingMappingId ? 'btn-secondary' : 'btn-primary'" @click="saveMapping" style="margin-top:12px;width:100%;">
              {{ editingMappingId ? lang.t('update_mapping') : lang.t('add_mapping') }}
            </button>
          </div>
          <div class="mapping-list hide-scrollbar">
             <div v-for="m in mappings" :key="m.id" class="mapping-row">
                 <div style="font-weight:600;">{{ m.unitag }}</div>
                 <div style="color:var(--text-secondary); overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">{{ m.danbooru_tags || 'off' }}</div>
                 <div style="color:var(--text-secondary); overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">{{ m.e621_tags || 'off' }}</div>
                 <div style="color:var(--text-secondary); overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">{{ m.rule34_tags || 'off' }}</div>
                 <div style="display:flex; gap:4px;">
                     <button class="btn btn-secondary btn-sm" @click="editMapping(m)" style="padding:2px 6px;">✏️</button>
                     <button class="btn btn-danger btn-sm" @click="deleteMapping(m.id)" style="padding:2px 6px;">✕</button>
                 </div>
             </div>
          </div>
        </div>

        <!-- Blacklist -->
        <div class="settings-section">
          <div class="settings-title">🚫 {{ lang.t('blacklist_title') }}</div>
          <div style="display:flex;gap:8px;margin-bottom:12px;">
            <input type="text" class="input" v-model="newRule" @keydown.enter="addRule" :placeholder="lang.t('search_placeholder')" style="flex:1;">
            <button class="btn btn-primary" @click="addRule">{{ lang.t('save') }}</button>
          </div>
          <div style="max-height:300px;overflow-y:auto;padding-right:4px;">
            <div v-for="r in rules" :key="r.id" class="blacklist-rule" :class="{ inactive: !r.is_active }">
              <button class="toggle-btn" :class="{ on: r.is_active }" @click="toggleRule(r)"></button>
              <span class="blacklist-rule-text">{{ r.rule_line }}</span>
              <button class="btn btn-danger btn-sm" @click="deleteRule(r.id)">✕</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useAuthStore } from '../stores/auth'
import { useToastStore } from '../stores/toast'
import { useLangStore } from '../stores/lang'
import {
  apiUpdateDefaultTags, apiGetApiKeysStatus, apiUpdateApiKeys,
  apiGetMappings, apiCreateMapping, apiUpdateMapping, apiDeleteMapping,
  apiGetBlacklist, apiAddBlacklistRule, apiUpdateBlacklistRule, apiDeleteBlacklistRule,
  apiDeleteHistory as apiDeleteHistoryFn, apiGetEventCount, apiUpdateConsent
} from '../api'
import type { TagMapping, BlacklistRule, ApiKeysStatus, ApiKeysUpdate } from '../types'

const auth = useAuthStore()
const toast = useToastStore()
const lang = useLangStore()

const statusFlags = ref({ danbooru: false, e621: false, rule34: false })
const defaultTags = ref('')
const savingTags = ref(false)

const keys = ref({
  danbooru_login: '', danbooru_api_key: '',
  e621_login: '', e621_api_key: '',
  rule34_user_id: '', rule34_api_key: '',
  search_limit: 40, search_interval: 0.0
})
const keysConfiguredSites = ref<string[]>([])
const savingKeys = ref(false)

const mappings = ref<TagMapping[]>([])
const editingMappingId = ref<number | null>(null)
const mapForm = ref({ unitag: '', danbooru: '', e621: '', rule34: '' })

const rules = ref<BlacklistRule[]>([])
const newRule = ref('')
const eventCount = ref(0)
const deletingHistory = ref(false)
const dataConsent = ref(false)

async function saveDefaultTags() {
  savingTags.value = true
  try {
    const res = await apiUpdateDefaultTags(defaultTags.value)
    auth.updateUser({ default_tags: res.default_tags })
    toast.show(lang.t('settings_saved'), 'success')
  } catch (e: any) {
    toast.show(e.message || e, 'error')
  } finally {
    savingTags.value = false
  }
}

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
    dataConsent.value = !!(status as any).data_consent
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

async function loadMappings() {
  try {
    const data = await apiGetMappings()
    mappings.value = data || []
  } catch(e) {}
}

async function saveMapping() {
  if (!mapForm.value.unitag) {
    toast.show('Unitag required', 'error')
    return
  }
  const payload = {
    unitag: mapForm.value.unitag,
    danbooru_tags: mapForm.value.danbooru,
    e621_tags: mapForm.value.e621,
    rule34_tags: mapForm.value.rule34
  }
  try {
    if (editingMappingId.value) {
      await apiUpdateMapping(editingMappingId.value, payload)
      toast.show(lang.t('mapping_saved'), 'success')
      editingMappingId.value = null
    } else {
      await apiCreateMapping(payload)
      toast.show(lang.t('mapping_created'), 'success')
    }
    mapForm.value = { unitag: '', danbooru: '', e621: '', rule34: '' }
    loadMappings()
  } catch(e: any) {
     toast.show(e.message || e, 'error')
  }
}

function editMapping(m: TagMapping) {
  editingMappingId.value = m.id
  mapForm.value = {
    unitag: m.unitag,
    danbooru: m.danbooru_tags || '',
    e621: m.e621_tags || '',
    rule34: m.rule34_tags || ''
  }
}

async function deleteMapping(id: number) {
  if (!confirm(lang.t('confirm_delete'))) return
  try {
    await apiDeleteMapping(id)
    toast.show(lang.t('mapping_deleted'), 'info')
    if (editingMappingId.value === id) {
      editingMappingId.value = null
      mapForm.value = { unitag: '', danbooru: '', e621: '', rule34: '' }
    }
    loadMappings()
  } catch(e: any) { toast.show(e.message || e, 'error') }
}

async function loadRules() {
  try {
    const data = await apiGetBlacklist()
    rules.value = data.rules || []
  } catch(e) {}
}

async function addRule() {
  const line = newRule.value.trim()
  if (!line) return
  try {
    await apiAddBlacklistRule(line)
    newRule.value = ''
    toast.show(lang.t('rule_added'), 'success')
    loadRules()
  } catch(e: any) { toast.show(e.message || e, 'error') }
}

async function toggleRule(r: BlacklistRule) {
  try {
    await apiUpdateBlacklistRule(r.id, { is_active: !r.is_active })
    r.is_active = !r.is_active
  } catch(e: any) { toast.show(e.message || e, 'error') }
}

async function deleteRule(id: number) {
  if (!confirm(lang.t('confirm_delete'))) return
  try {
    await apiDeleteBlacklistRule(id)
    rules.value = rules.value.filter(x => x.id !== id)
    toast.show(lang.t('rule_deleted'), 'info')
  } catch(e: any) { toast.show(e.message || e, 'error') }
}

onMounted(async () => {
  if (auth.isAuthenticated && auth.user) {
    defaultTags.value = auth.user.default_tags || ''
    loadKeysStatus()
    loadMappings()
    loadRules()
    loadEventCount()
  }
})

async function loadEventCount() {
  try {
    const data = await apiGetEventCount()
    eventCount.value = data.total || 0
  } catch {}
}

async function toggleConsent() {
  try {
    await apiUpdateConsent(dataConsent.value)
    toast.show(lang.t('settings_saved'), 'success')
  } catch {
    toast.show('Error', 'error')
  }
}

async function deleteHistory() {
  if (!confirm(lang.t('confirm_delete_history'))) return
  deletingHistory.value = true
  try {
    const result = await apiDeleteHistoryFn()
    eventCount.value = 0
    toast.show(lang.t('history_deleted').replace('{n}', String(result.deleted)), 'success')
  } catch (e: any) {
    toast.show(e.message || 'Error', 'error')
  } finally {
    deletingHistory.value = false
  }
}
</script>

<style scoped>
.settings-layout {
  display: grid;
  grid-template-columns: 1fr 1.5fr;
  gap: 24px;
}

.settings-col {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.mapping-add-card {
  background: var(--bg-card-hover);
  padding: 16px;
  border-radius: var(--border-radius-sm);
  margin-bottom: 16px;
}

.mapping-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  align-items: end;
}

.mapping-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 400px;
  overflow-y: auto;
  padding-right: 4px;
}

.mapping-row {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr 1fr auto;
  gap: 12px;
  align-items: center;
  background: var(--bg-input);
  padding: 10px 12px;
  border-radius: 8px;
  font-size: 13px;
  transition: background 0.2s;
}

.mapping-row:hover {
  background: var(--bg-tertiary);
}

.mapping-tag-val {
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 900px) {
  .settings-layout {
    grid-template-columns: 1fr;
    gap: 20px;
  }
  
  .mapping-grid {
    grid-template-columns: 1fr 1fr;
    gap: 12px;
  }
}

@media (max-width: 600px) {
  .mapping-grid {
    grid-template-columns: 1fr;
  }
  
  .mapping-row {
     grid-template-columns: 1fr 1fr;
     gap: 8px;
  }
  
  .mapping-row > div:last-child {
    grid-column: span 2;
    justify-content: flex-end;
  }
}

.hide-scrollbar::-webkit-scrollbar {
  width: 4px;
}
.hide-scrollbar::-webkit-scrollbar-thumb {
  background: var(--border-color);
  border-radius: 10px;
}

/* Privacy Toggle & Details */
.privacy-control {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  background: var(--bg-input);
  border-radius: 12px;
  border: 1px solid rgba(128,128,128,0.1);
}
.switch {
  position: relative;
  display: inline-block;
  width: 44px;
  height: 24px;
}
.switch input { opacity: 0; width: 0; height: 0; }
.slider {
  position: absolute;
  cursor: pointer;
  top: 0; left: 0; right: 0; bottom: 0;
  background-color: #333;
  transition: .4s;
}
.slider:before {
  position: absolute;
  content: "";
  height: 18px; width: 18px;
  left: 3px; bottom: 3px;
  background-color: white;
  transition: .4s;
}
input:checked + .slider { background-color: var(--primary); }
input:focus + .slider { box-shadow: 0 0 1px var(--primary); }
input:checked + .slider:before { transform: translateX(20px); }
.slider.round { border-radius: 34px; }
.slider.round:before { border-radius: 50%; }

.privacy-details summary::-webkit-details-marker { display: none; }
.privacy-details[open] .disclosure-arrow { transform: rotate(180deg); }
.disclosure-arrow { font-size: 10px; color: var(--text-muted); transition: transform 0.2s; }
</style>
