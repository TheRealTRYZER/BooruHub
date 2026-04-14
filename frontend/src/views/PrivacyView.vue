<template>
  <div class="privacy-page">
    <div class="page-header">
      <h1 class="page-title">🛡️ {{ lang.t('privacy_title') }}</h1>
      <p class="page-subtitle">{{ lang.t('privacy_subtitle') }}</p>
    </div>

    <div class="privacy-content">
      <section class="privacy-section">
        <h2>{{ lang.t('privacy_what_title') }}</h2>
        <p>{{ lang.t('privacy_what_text') }}</p>
        <ul>
          <li><strong>Impressions</strong> — {{ lang.t('privacy_impression_desc') }}</li>
          <li><strong>Views</strong> — {{ lang.t('privacy_view_desc') }}</li>
          <li><strong>Likes</strong> — {{ lang.t('privacy_like_desc') }}</li>
          <li><strong>Favourites</strong> — {{ lang.t('privacy_fav_desc') }}</li>
          <li><strong>Searches</strong> — {{ lang.t('privacy_search_desc') }}</li>
        </ul>
      </section>

      <section class="privacy-section">
        <h2>{{ lang.t('privacy_why_title') }}</h2>
        <p>{{ lang.t('privacy_why_text') }}</p>
      </section>

      <section class="privacy-section">
        <h2>{{ lang.t('privacy_retention_title') }}</h2>
        <p>{{ lang.t('privacy_retention_text') }}</p>
      </section>

      <section class="privacy-section">
        <h2>{{ lang.t('privacy_rights_title') }}</h2>
        <p>{{ lang.t('privacy_rights_text') }}</p>
        <ul>
          <li>{{ lang.t('privacy_right_access') }}</li>
          <li>{{ lang.t('privacy_right_delete') }}</li>
          <li>{{ lang.t('privacy_right_withdraw') }}</li>
        </ul>
      </section>

      <section class="privacy-section">
        <h2>{{ lang.t('privacy_sharing_title') }}</h2>
        <p>{{ lang.t('privacy_sharing_text') }}</p>
      </section>

      <div style="margin-top:32px;text-align:center;">
        <button class="btn btn-secondary" @click="$router.push('/')">{{ lang.t('back_to_feed') }}</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useLangStore } from '../stores/lang'
const lang = useLangStore()
</script>

<style scoped>
.privacy-page {
  max-width: 720px;
  margin: 0 auto;
  padding: 24px 16px;
}

.privacy-content {
  background: var(--bg-card);
  border-radius: var(--border-radius);
  padding: 32px;
  border: 1px solid var(--border-color);
}

.privacy-section {
  margin-bottom: 28px;
}

.privacy-section h2 {
  font-size: 1.1rem;
  color: var(--text-primary);
  margin-bottom: 8px;
}

.privacy-section p {
  color: var(--text-secondary);
  line-height: 1.6;
  font-size: var(--font-sm);
}

.privacy-section ul {
  margin-top: 8px;
  padding-left: 20px;
  color: var(--text-secondary);
  font-size: var(--font-sm);
  line-height: 1.8;
}

.privacy-section ul li strong {
  color: var(--text-primary);
}
</style>
