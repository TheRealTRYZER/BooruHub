<template>
  <div class="settings-section">
    <div class="settings-title">🚫 {{ lang.t('blacklist_title') }}</div>
    <div class="input-suggest-group">
      <input type="text" class="input" v-model="newRule" 
             @input="onSuggest" @blur="onBlur" @keydown.enter="addRule" 
             :placeholder="lang.t('search_placeholder')">
      <button class="btn btn-primary" @click="addRule">{{ lang.t('save') }}</button>
      <div v-if="showSuggestions && suggestions.length > 0" class="search-suggestions visible mapping-suggest">
        <div v-for="s in suggestions" :key="s.tag" class="search-suggestion-item" @mousedown.prevent="selectSuggest(s.tag)">
          <span style="flex:1">{{ s.tag }}</span>
          <span v-if="s.from_danbooru" class="suggestion-source danbooru">db</span>
          <span v-if="s.from_e621" class="suggestion-source e621">e6</span>
          <span v-if="s.from_rule34" class="suggestion-source rule34">r34</span>
        </div>
      </div>
    </div>
    
    <div class="rules-list hide-scrollbar">
      <div v-for="r in rules" :key="r.id" class="blacklist-rule" :class="{ inactive: !r.is_active }">
        <button class="toggle-btn" :class="{ on: r.is_active }" @click="toggleRule(r)"></button>
        <span class="blacklist-rule-text">{{ r.rule_line }}</span>
        <button class="btn btn-danger btn-sm" @click="deleteRule(r.id)">✕</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useToastStore } from '../../stores/toast'
import { useLangStore } from '../../stores/lang'
import { apiGetBlacklist, apiAddBlacklistRule, apiUpdateBlacklistRule, apiDeleteBlacklistRule, apiSuggestTags } from '../../api'
import type { BlacklistRule } from '../../types'

const toast = useToastStore()
const lang = useLangStore()

const rules = ref<BlacklistRule[]>([])
const newRule = ref('')
const suggestions = ref<any[]>([])
const showSuggestions = ref(false)
let suggestTimeout: any = null

function onSuggest() {
  showSuggestions.value = true
  clearTimeout(suggestTimeout)
  const val = newRule.value.trim()
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
  newRule.value = tag
  suggestions.value = []
  showSuggestions.value = false
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

onMounted(() => {
  loadRules()
})
</script>

<style scoped>
.input-suggest-group {
  display: flex;
  gap: 8px;
  position: relative;
  margin-bottom: 16px;
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
.rules-list {
  max-height: 300px;
  overflow-y: auto;
  padding-right: 4px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.blacklist-rule {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  background: var(--bg-card);
  border: 1px solid var(--border-glass);
  border-radius: var(--border-radius-sm);
  transition: all 0.2s;
}
.blacklist-rule.inactive {
  opacity: 0.5;
}
.blacklist-rule-text {
  flex: 1;
  font-family: monospace;
  font-size: 13px;
  color: var(--text-primary);
}
.toggle-btn {
  width: 36px;
  height: 20px;
  border-radius: 10px;
  background: var(--bg-secondary);
  position: relative;
  transition: all 0.25s;
  padding: 0;
  border: 1px solid var(--border-glass);
}
.toggle-btn::after {
  content: '';
  position: absolute;
  top: 2px;
  left: 2px;
  width: 14px;
  height: 14px;
  background: var(--text-secondary);
  border-radius: 50%;
  transition: all 0.25s;
}
.toggle-btn.on {
  background: var(--success);
  border-color: var(--success);
}
.toggle-btn.on::after {
  background: #fff;
  left: calc(100% - 16px);
}
.hide-scrollbar::-webkit-scrollbar {
  width: 4px;
}
.hide-scrollbar::-webkit-scrollbar-thumb {
  background: var(--border-glass-hover);
  border-radius: 10px;
}
</style>
