import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useFeedStore = defineStore('feed', () => {
  const tags = ref('')
  const siteTags = ref({ danbooru: '', e621: '', rule34: '' })
  const ratios = ref({ danbooru: 1, e621: 1, rule34: 1 })
  const isSplit = ref(false)
  const sites = ref(['danbooru', 'e621', 'rule34'])

  // Cached feed state for back navigation
  const posts = ref([])
  const page = ref(1)
  const hasMore = ref(true)
  const lastSearchSignature = ref('')

  function toggleSite(site) {
    if (sites.value.includes(site)) {
      if (sites.value.length > 1) {
        sites.value = sites.value.filter(s => s !== site)
      }
    } else {
      sites.value = [...sites.value, site]
    }
  }

  function toggleSplit() {
    isSplit.value = !isSplit.value
  }

  function resetFeed() {
    posts.value = []
    page.value = 1
    hasMore.value = true
  }

  return { 
    tags, siteTags, ratios, isSplit, sites, 
    posts, page, hasMore, lastSearchSignature,
    toggleSite, toggleSplit, resetFeed 
  }
})
