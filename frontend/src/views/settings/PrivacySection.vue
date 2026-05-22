<template>
  <div class="settings-section privacy-card">
    <div class="settings-title">🛡️ {{ lang.t('privacy_title') }}</div>
    <div class="privacy-content">
      <p class="privacy-description">
        {{ lang.t('privacy_desc') }}
        <a href="#/privacy" class="privacy-link">{{ lang.t('privacy_policy') }}</a>
      </p>
      
      <div class="privacy-control">
        <div class="control-label">
          <div class="consent-title">{{ lang.t('consent_label') }}</div>
          <div class="consent-subtext">{{ lang.t('consent_subtext') }}</div>
        </div>
        <label class="switch">
          <input type="checkbox" v-model="dataConsent" @change="toggleConsent">
          <span class="slider round"></span>
        </label>
      </div>

      <div class="history-management">
        <span class="history-stats">
          {{ lang.t('events_collected') }}: <strong>{{ eventCount }}</strong>
        </span>
        <button class="btn btn-danger btn-sm" @click="deleteHistory" :disabled="deletingHistory">
          🗑️ {{ lang.t('delete_history') }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useToastStore } from '../../stores/toast'
import { useLangStore } from '../../stores/lang'
import { apiGetApiKeysStatus, apiDeleteHistory, apiGetEventCount, apiUpdateConsent } from '../../api'

const toast = useToastStore()
const lang = useLangStore()

const eventCount = ref(0)
const deletingHistory = ref(false)
const dataConsent = ref(false)

async function loadPrivacyStatus() {
  try {
    const status = await apiGetApiKeysStatus()
    dataConsent.value = !!(status as any).data_consent
  } catch {}
}

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
    const result = await apiDeleteHistory()
    eventCount.value = 0
    toast.show(lang.t('history_deleted').replace('{n}', String(result.deleted)), 'success')
  } catch (e: any) {
    toast.show(e.message || 'Error', 'error')
  } finally {
    deletingHistory.value = false
  }
}

onMounted(() => {
  loadPrivacyStatus()
  loadEventCount()
})
</script>

<style scoped>
.privacy-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.privacy-description {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
  margin: 0;
}
.privacy-link {
  color: var(--accent);
  text-decoration: underline;
  font-weight: 500;
}
.privacy-control {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px;
  background: var(--bg-card);
  border-radius: var(--border-radius-sm);
  border: 1px solid var(--border-glass);
}
.control-label {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.consent-title {
  font-weight: 700;
  font-size: 14px;
  color: var(--text-primary);
}
.consent-subtext {
  font-size: 11px;
  color: var(--text-muted);
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
  background-color: var(--bg-secondary);
  border: 1px solid var(--border-glass);
  transition: .3s;
}
.slider:before {
  position: absolute;
  content: "";
  height: 16px; width: 16px;
  left: 3px; bottom: 3px;
  background-color: var(--text-secondary);
  transition: .3s;
}
input:checked + .slider {
  background-color: var(--accent);
  border-color: var(--accent);
}
input:checked + .slider:before {
  background-color: #fff;
  transform: translateX(20px);
}
.slider.round { border-radius: 34px; }
.slider.round:before { border-radius: 50%; }

.history-management {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  background: rgba(0, 0, 0, 0.15);
  border-radius: var(--border-radius-sm);
  border: 1px solid var(--border-glass);
}
.history-stats {
  font-size: 13px;
  color: var(--text-secondary);
}
</style>
