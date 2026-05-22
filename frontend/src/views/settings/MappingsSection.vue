<template>
  <div class="settings-section">
    <div class="settings-title">🏷️ {{ lang.t('manual_mappings') }}</div>
    <div class="mapping-add-card">
      <div class="mapping-grid">
        <div class="input-suggest-container">
          <label class="input-label">Unitag</label>
          <input type="text" class="input btn-sm" v-model="mapForm.unitag" @input="onSuggest('unitag', mapForm.unitag)" @blur="onBlur">
          <div v-if="activeField === 'unitag' && suggestions.length > 0" class="search-suggestions visible mapping-suggest">
            <div v-for="s in suggestions" :key="s.tag" class="search-suggestion-item" @mousedown.prevent="selectSuggest(s.tag)">
              <span style="flex:1">{{ s.tag }}</span>
            </div>
          </div>
        </div>
        
        <div class="input-suggest-container">
          <label class="input-label danbooru">Danbooru</label>
          <input type="text" class="input btn-sm" v-model="mapForm.danbooru" @input="onSuggest('danbooru', mapForm.danbooru)" @blur="onBlur">
          <div v-if="activeField === 'danbooru' && suggestions.length > 0" class="search-suggestions visible mapping-suggest">
            <div v-for="s in suggestions" :key="s.tag" class="search-suggestion-item" @mousedown.prevent="selectSuggest(s.tag)">
              <span style="flex:1">{{ s.tag }}</span>
              <span v-if="s.from_danbooru" class="suggestion-source danbooru">db</span>
            </div>
          </div>
        </div>

        <div class="input-suggest-container">
          <label class="input-label e621">e621</label>
          <input type="text" class="input btn-sm" v-model="mapForm.e621" @input="onSuggest('e621', mapForm.e621)" @blur="onBlur">
          <div v-if="activeField === 'e621' && suggestions.length > 0" class="search-suggestions visible mapping-suggest">
            <div v-for="s in suggestions" :key="s.tag" class="search-suggestion-item" @mousedown.prevent="selectSuggest(s.tag)">
              <span style="flex:1">{{ s.tag }}</span>
              <span v-if="s.from_e621" class="suggestion-source e621">e6</span>
            </div>
          </div>
        </div>

        <div class="input-suggest-container">
          <label class="input-label rule34">Rule34</label>
          <input type="text" class="input btn-sm" v-model="mapForm.rule34" @input="onSuggest('rule34', mapForm.rule34)" @blur="onBlur">
          <div v-if="activeField === 'rule34' && suggestions.length > 0" class="search-suggestions visible mapping-suggest">
            <div v-for="s in suggestions" :key="s.tag" class="search-suggestion-item" @mousedown.prevent="selectSuggest(s.tag)">
              <span style="flex:1">{{ s.tag }}</span>
              <span v-if="s.from_rule34" class="suggestion-source rule34">r34</span>
            </div>
          </div>
        </div>
      </div>
      <button class="btn btn-sm action-btn" :class="editingMappingId ? 'btn-secondary' : 'btn-primary'" @click="saveMapping">
        {{ editingMappingId ? lang.t('update_mapping') : lang.t('add_mapping') }}
      </button>
    </div>
    
    <div class="mapping-list hide-scrollbar">
      <div v-for="m in mappings" :key="m.id" class="mapping-row">
        <div class="mapping-unitag">{{ m.unitag }}</div>
        <div class="mapping-val danbooru">{{ m.danbooru_tags || 'off' }}</div>
        <div class="mapping-val e621">{{ m.e621_tags || 'off' }}</div>
        <div class="mapping-val rule34">{{ m.rule34_tags || 'off' }}</div>
        <div class="mapping-actions">
          <button class="btn btn-secondary btn-sm icon-btn" @click="editMapping(m)">✏️</button>
          <button class="btn btn-danger btn-sm icon-btn" @click="deleteMapping(m.id)">✕</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useToastStore } from '../../stores/toast'
import { useLangStore } from '../../stores/lang'
import { apiGetMappings, apiCreateMapping, apiUpdateMapping, apiDeleteMapping, apiSuggestTags } from '../../api'
import type { TagMapping } from '../../types'

const toast = useToastStore()
const lang = useLangStore()

const mappings = ref<TagMapping[]>([])
const editingMappingId = ref<number | null>(null)
const mapForm = ref({ unitag: '', danbooru: '', e621: '', rule34: '' })

const suggestions = ref<any[]>([])
const activeField = ref<string | null>(null)
let suggestTimeout: any = null

function onSuggest(field: string, val: string) {
  activeField.value = field
  clearTimeout(suggestTimeout)
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
    activeField.value = null
    suggestions.value = []
  }, 200)
}

function selectSuggest(tag: string) {
  if (activeField.value === 'unitag') mapForm.value.unitag = tag
  else if (activeField.value === 'danbooru') mapForm.value.danbooru = tag
  else if (activeField.value === 'e621') mapForm.value.e621 = tag
  else if (activeField.value === 'rule34') mapForm.value.rule34 = tag
  
  suggestions.value = []
  activeField.value = null
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

onMounted(() => {
  loadMappings()
})
</script>

<style scoped>
.mapping-add-card {
  background: var(--bg-card-hover);
  border: 1px solid var(--border-glass);
  padding: 16px;
  border-radius: var(--border-radius-sm);
  margin-bottom: 16px;
}
.mapping-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  align-items: end;
}
.input-suggest-container {
  position: relative;
}
.mapping-suggest {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  width: 100%;
  max-height: 200px;
  z-index: 10;
}
.input-label.danbooru { color: var(--danbooru); }
.input-label.e621 { color: var(--e621); }
.input-label.rule34 { color: var(--rule34); }
.action-btn {
  margin-top: 16px;
  width: 100%;
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
  grid-template-columns: 1.2fr 1fr 1fr 1fr auto;
  gap: 12px;
  align-items: center;
  background: var(--bg-card);
  border: 1px solid var(--border-glass);
  padding: 10px 14px;
  border-radius: 8px;
  font-size: 13px;
  transition: background 0.2s, border-color 0.2s;
}
.mapping-row:hover {
  background: var(--bg-card-hover);
  border-color: var(--border-glass-hover);
}
.mapping-unitag {
  font-weight: 700;
  color: var(--text-primary);
}
.mapping-val {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.mapping-val.danbooru { color: var(--danbooru); }
.mapping-val.e621 { color: var(--e621); }
.mapping-val.rule34 { color: var(--rule34); }
.mapping-actions {
  display: flex;
  gap: 6px;
}
.icon-btn {
  padding: 4px 8px;
  font-size: 12px;
}
.hide-scrollbar::-webkit-scrollbar {
  width: 4px;
}
.hide-scrollbar::-webkit-scrollbar-thumb {
  background: var(--border-glass-hover);
  border-radius: 10px;
}

@media (max-width: 900px) {
  .mapping-grid {
    grid-template-columns: 1fr 1fr;
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
  .mapping-row > .mapping-actions {
    grid-column: span 2;
    justify-content: flex-end;
  }
}
</style>
