<template>
  <div class="settings-section">
    <div class="settings-title">👤 {{ lang.t('profile') }}</div>
    <div class="profile-header">
      <div class="nav-avatar profile-avatar">
        {{ auth.user!.username[0].toUpperCase() }}
      </div>
      <div>
        <div class="profile-username">{{ auth.user!.username }}</div>
        <div class="profile-email">{{ auth.user!.email }}</div>
      </div>
    </div>
    <div class="profile-tags-wrapper">
      <label class="input-label">{{ lang.t('start_tags') }}</label>
      <div class="input-suggest-group">
        <input type="text" class="input" v-model="defaultTags" 
               @input="onSuggest" @blur="onBlur" 
               :placeholder="lang.t('search_placeholder')">
        <button class="btn btn-secondary" @click="saveDefaultTags" :disabled="savingTags">{{ lang.t('save') }}</button>
        <div v-if="showSuggestions && suggestions.length > 0" class="search-suggestions visible mapping-suggest">
          <div v-for="s in suggestions" :key="s.tag" class="search-suggestion-item" @mousedown.prevent="selectSuggest(s.tag)">
            <span style="flex:1">{{ s.tag }}</span>
            <span v-if="s.from_danbooru" class="suggestion-source danbooru">db</span>
            <span v-if="s.from_e621" class="suggestion-source e621">e6</span>
            <span v-if="s.from_rule34" class="suggestion-source rule34">r34</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useAuthStore } from '../../stores/auth'
import { useToastStore } from '../../stores/toast'
import { useLangStore } from '../../stores/lang'
import { apiUpdateDefaultTags, apiSuggestTags } from '../../api'

const auth = useAuthStore()
const toast = useToastStore()
const lang = useLangStore()

const defaultTags = ref('')
const savingTags = ref(false)
const suggestions = ref<any[]>([])
const showSuggestions = ref(false)
let suggestTimeout: any = null

function onSuggest() {
  showSuggestions.value = true
  clearTimeout(suggestTimeout)
  const val = defaultTags.value.trim().split(/\s+/).pop() || ''
  if (val.length < 2) {
    suggestions.value = []
    return
  }
  suggestTimeout = setTimeout(async () => {
    try {
      const data = await apiSuggestTags(val)
      suggestions.value = data.suggestions || []
    } catch {
      suggestions.value = []
    }
  }, 300)
}

function onBlur() {
  setTimeout(() => {
    showSuggestions.value = false
    suggestions.value = []
  }, 200)
}

function selectSuggest(tag: string) {
  const parts = defaultTags.value.split(/\s+/)
  parts.pop()
  parts.push(tag)
  defaultTags.value = parts.join(' ') + ' '
  suggestions.value = []
  showSuggestions.value = false
}

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

onMounted(() => {
  if (auth.user) {
    defaultTags.value = auth.user.default_tags || ''
  }
})
</script>

<style scoped>
.profile-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 20px;
}
.profile-avatar {
  width: 54px;
  height: 54px;
  font-size: 1.4rem;
  border: 1px solid var(--border-glass);
  box-shadow: var(--glow-shadow);
}
.profile-username {
  font-weight: 700;
  font-size: 16px;
  color: var(--text-primary);
}
.profile-email {
  color: var(--text-muted);
  font-size: 13px;
}
.profile-tags-wrapper {
  margin-top: 20px;
  border-top: 1px solid rgba(128,128,128,0.1);
  padding-top: 20px;
}
.input-suggest-group {
  display: flex;
  gap: 8px;
  position: relative;
}
.input-suggest-group .input {
  flex: 1;
}
.mapping-suggest {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  width: 100%;
  z-index: 10;
}
</style>
