<template>
  <div class="guides-view">
    <div class="page-header">
      <h1 class="page-title">{{ lang.t('guides_title') }}</h1>
      <p class="page-subtitle">{{ lang.t('guides_subtitle') }}</p>
    </div>

    <div class="tabs-container">
      <div class="tabs-header">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          class="tab-button"
          :class="{ active: activeTab === tab.id }"
          @click="activeTab = tab.id"
        >
          <span class="tab-label">{{ lang.t(tab.labelKey) }}</span>
        </button>
      </div>

      <div class="tabs-content">
        <!-- Tags Guide -->
        <div v-show="activeTab === 'tags'" class="tab-content" transition="fade">
          <template v-if="lang.locale === 'ru'">
            <h2>Гайд по тегам</h2>
            <section class="guide-section">
              <h3>Как искать</h3>
              <p>Вводите теги в строке поиска через пробел. BooruHub автоматически конвертирует их для каждого сайта в соответствии с вашим маппингом.</p>
              <div class="info-box warning">
                <strong>Danbooru:</strong> Базовые аккаунты ограничены <code>2 тегами</code> в запросе. Если вы вводите больше — первые 2 тега используются для запроса к API Danbooru, а остальные фильтруются приложением локально.
              </div>
            </section>
            
            <section class="guide-section">
              <h3>Исключение тегов</h3>
              <p>Добавьте оператор тире <code>-</code> перед тегом, чтобы исключить его из результатов поиска:</p>
              <div class="code-block"><code>cat_ears -gore</code></div>
              <p class="text-muted">Этот запрос найдёт посты с кошачьими ушами, строго исключив те, которые содержат 'gore'.</p>
            </section>

            <section class="guide-section">
              <h3>Полезные теги</h3>
              <table class="info-table">
                <thead><tr><th>Тег</th><th>Описание</th></tr></thead>
                <tbody>
                  <tr><td><code>rating:general</code></td><td>Исключает откровенный контент (SFW)</td></tr>
                  <tr><td><code>rating:explicit</code></td><td>Только откровенный контент (NSFW)</td></tr>
                  <tr><td><code>order:score</code></td><td>Сортировка результатов по оценкам</td></tr>
                  <tr><td><code>order:date</code></td><td>Сортировка по дате добавления (по умолчанию)</td></tr>
                  <tr><td><code>order:hot</code></td><td>Сортировка по набирающим популярность</td></tr>
                </tbody>
              </table>
            </section>
          </template>
          <template v-else>
            <h2>Tags Guide</h2>
            <section class="guide-section">
              <h3>How to search</h3>
              <p>Enter tags in the search bar separated by spaces. BooruHub automatically converts them for each site according to your mappings.</p>
              <div class="info-box warning">
                <strong>Danbooru:</strong> Basic accounts are limited to <code>2 tags</code> per query. If you enter more, the first two are used for the Danbooru API, and the rest are filtered locally.
              </div>
            </section>

            <section class="guide-section">
              <h3>Excluding Tags</h3>
              <p>Add a dash operator <code>-</code> before a tag to exclude it from search results:</p>
              <div class="code-block"><code>cat_ears -gore</code></div>
              <p class="text-muted">This query will find posts with cat ears while strictly excluding those containing 'gore'.</p>
            </section>

            <section class="guide-section">
              <h3>Useful Tags</h3>
              <table class="info-table">
                <thead><tr><th>Tag</th><th>Description</th></tr></thead>
                <tbody>
                  <tr><td><code>rating:general</code></td><td>Excludes adult content (SFW)</td></tr>
                  <tr><td><code>rating:explicit</code></td><td>Only adult content (NSFW)</td></tr>
                  <tr><td><code>order:score</code></td><td>Sort results by score</td></tr>
                  <tr><td><code>order:date</code></td><td>Sort results by date added (default)</td></tr>
                  <tr><td><code>order:hot</code></td><td>Sort results by hot</td></tr>
                </tbody>
              </table>
            </section>
          </template>
        </div>

        <!-- API Guide -->
        <div v-show="activeTab === 'api'" class="tab-content">
          <template v-if="lang.locale === 'ru'">
            <h2>Настройка API</h2>
            <p class="section-desc">Доступ к API позволяет увеличить лимит запросов и получать доступ к контенту, скрытому для гостей.</p>
            
            <div class="info-box highlight" style="margin-bottom:24px;">
              <strong>🔐 Безопасность:</strong> Все ваши API-ключи хранятся в <strong>зашифрованном виде</strong> (AES-256) на стороне сервера. Мы никогда не передаем их третьим лицам и используем только для авторизации ваших запросов к Booru.
            </div>

            <div class="step-card">
              <div class="step-number">1</div>
              <div class="step-content">
                <h3>Регистрация</h3>
                <p>Зарегистрируйтесь на нужном сайте (например, Danbooru, e621, Rule34).</p>
              </div>
            </div>
            <div class="step-card">
              <div class="step-number">2</div>
              <div class="step-content">
                <h3>Получение ключа</h3>
                <p>Найдите раздел API в настройках профиля на сайте и сгенерируйте API-ключ.</p>
              </div>
            </div>
            <div class="step-card">
              <div class="step-number">3</div>
              <div class="step-content">
                <h3>Настройка в BooruHub</h3>
                <p>Вставьте ваши данные в разделе <strong>Настройки → API Ключи</strong>.</p>
              </div>
            </div>
          </template>
          <template v-else>
            <h2>API Configuration</h2>
            <p class="section-desc">API access allows increasing request limits and accessing content hidden from guests.</p>

            <div class="info-box highlight" style="margin-bottom:24px;">
              <strong>🔐 Security:</strong> All your API keys are stored in <strong>encrypted format</strong> (AES-256) on the server side. We never share them and only use them for authenticating your requests to Booru sites.
            </div>

            <div class="step-card">
              <div class="step-number">1</div>
              <div class="step-content">
                <h3>Registration</h3>
                <p>Register on the required site (e.g., Danbooru, e621, Rule34).</p>
              </div>
            </div>
            <div class="step-card">
              <div class="step-number">2</div>
              <div class="step-content">
                <h3>Getting the Key</h3>
                <p>Find the API section in your profile settings on the site and generate an API key.</p>
              </div>
            </div>
            <div class="step-card">
              <div class="step-number">3</div>
              <div class="step-content">
                <h3>Setting up in BooruHub</h3>
                <p>Paste your data in the <strong>Settings → API Keys</strong> section.</p>
              </div>
            </div>
          </template>
        </div>

        <!-- Blacklist Guide -->
        <div v-show="activeTab === 'blacklist'" class="tab-content">
          <template v-if="lang.locale === 'ru'">
            <h2>Черный список (Blacklist)</h2>
            <p class="section-desc">Blacklist позволяет навсегда скрыть посты с нежелательным контентом. Каждая строка — это отдельное <strong>правило</strong>. Пост будет скрыт, если он соответствует хотя бы одной строке.</p>
            
            <section class="guide-section">
              <h3>1. Логика «И» (AND)</h3>
              <p>Если написать несколько тегов через пробел, пост скроется только при наличии <strong>всех</strong> указанных тегов.</p>
              <div class="code-block"><code>gore blood</code></div>
              <p class="text-muted">Этот пример скроет посты, где есть одновременно и 'gore', и 'blood'. Если в посте только один из них — он останется.</p>
            </section>

            <section class="guide-section">
              <h3>2. Логика «ИЛИ» (OR)</h3>
              <p>Префикс <code>~</code> перед тегом означает, что пост скроется, если в нем есть <strong>хотя бы один</strong> из них.</p>
              <div class="code-block"><code>~dog ~cat ~fox</code></div>
              <p class="text-muted">Скроет пост, если там есть либо собака, либо кошка, либо лиса.</p>
            </section>

            <section class="guide-section">
              <h3>3. Исключения внутри правила</h3>
              <p>Префикс <code>-</code> отменяет действие <strong>текущей строки</strong>, если в посте найден этот тег.</p>
              <div class="code-block"><code>animal -dog</code></div>
              <p class="text-muted">Скроет всех животных, КРОМЕ собак. Собаки будут показаны, даже если у них есть тег 'animal'.</p>
            </section>

            <section class="guide-section">
              <h3>4. Фильтры рейтинга и очков</h3>
              <p>Вы можете использовать мета-теги для более тонкой настройки.</p>
              <table class="info-table">
                <thead><tr><th>Пример</th><th>Действие</th></tr></thead>
                <tbody>
                  <tr><td><code>rating:explicit</code></td><td>Скрывает весь NSFW контент</td></tr>
                  <tr><td><code>score:<100</code></td><td>Скрывает посты с рейтингом меньше 100</td></tr>
                  <tr><td><code>rating:q score:<20</code></td><td>Скрывает 'Questionable' посты, если у них мало очков</td></tr>
                </tbody>
              </table>
            </section>
          </template>
          <template v-else>
            <h2>Blacklist Guide</h2>
            <p class="section-desc">The Blacklist allows you to hide posts with unwanted content. Each line is a separate <strong>rule</strong>. A post is hidden if it matches at least one line.</p>

            <section class="guide-section">
              <h3>1. AND Logic</h3>
              <p>Multiple tags on one line mean the post will be hidden only if it has <strong>all</strong> of them.</p>
              <div class="code-block"><code>gore blood</code></div>
              <p class="text-muted">This example hides posts that have both 'gore' and 'blood'. If only one is present, the post stays.</p>
            </section>

            <section class="guide-section">
              <h3>2. OR Logic</h3>
              <p>The <code>~</code> prefix means the post will be hidden if it has <strong>at least one</strong> of these tags.</p>
              <div class="code-block"><code>~dog ~cat ~fox</code></div>
              <p class="text-muted">Hides the post if it contains a dog, a cat, or a fox.</p>
            </section>

            <section class="guide-section">
              <h3>3. Exclusions within a rule</h3>
              <p>The <code>-</code> prefix cancels the <strong>current rule</strong> if the tag is found.</p>
              <div class="code-block"><code>animal -dog</code></div>
              <p class="text-muted">Hides all animals EXCEPT dogs. Dogs will be shown even if they have the 'animal' tag.</p>
            </section>

            <section class="guide-section">
              <h3>4. Rating and Score Filters</h3>
              <p>Use meta-tags for fine-grained filtering.</p>
              <table class="info-table">
                <thead><tr><th>Example</th><th>Effect</th></tr></thead>
                <tbody>
                  <tr><td><code>rating:explicit</code></td><td>Hides all NSFW content</td></tr>
                  <tr><td><code>score:<100</code></td><td>Hides posts with a score less than 100</td></tr>
                  <tr><td><code>rating:q score:<20</code></td><td>Hides 'Questionable' posts with low scores</td></tr>
                </tbody>
              </table>
            </section>
          </template>
        </div>

        <!-- Mapping Guide -->
        <div v-show="activeTab === 'mapping'" class="tab-content">
          <template v-if="lang.locale === 'ru'">
            <h2>Маппинг тегов</h2>
            <p>Система синонимов, позволяющая создать <strong>Универсальный тег (Unitag)</strong>.</p>
            <div class="code-block">
              <pre>Unitag:   miku
Danbooru: hatsune_miku
e621:     miku</pre>
            </div>
            <p>Теперь введя <code>miku</code>, вы получите правильные результаты со всех сайтов.</p>
          </template>
          <template v-else>
            <h2>Tag Mapping</h2>
            <p>Synonym system that allows creating a <strong>Universal tag (Unitag)</strong>.</p>
            <div class="code-block">
              <pre>Unitag:   miku
Danbooru: hatsune_miku
e621:     miku</pre>
            </div>
            <p>Now by entering <code>miku</code>, you will get correct results from all sites.</p>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useLangStore } from '../stores/lang.js'

const lang = useLangStore()
const tabs = [
  { id: 'tags', labelKey: 'tab_tags' },
  { id: 'api', labelKey: 'tab_api' },
  { id: 'blacklist', labelKey: 'tab_blacklist' },
  { id: 'mapping', labelKey: 'tab_mapping' },
]

const activeTab = ref('tags')
</script>

<style scoped>
.guides-view { padding: 32px 24px; max-width: 900px; margin: 0 auto; color: var(--text-primary); }
.page-header { margin-bottom: 32px; text-align: center; }
.page-title { font-size: 32px; font-weight: 800; margin-bottom: 12px; }
.page-subtitle { color: var(--text-secondary); max-width: 600px; margin: 0 auto; }
.tabs-container { background: var(--bg-secondary); border-radius: 16px; overflow: hidden; border: 1px solid var(--border-color); }
.tabs-header { display: flex; background: var(--bg-tertiary); border-bottom: 1px solid var(--border-color); }
.tab-button { flex: 1; padding: 18px 16px; border: none; background: transparent; color: var(--text-secondary); font-size: 15px; font-weight: 600; cursor: pointer; transition: all 0.3s; }
.tab-button.active { color: var(--primary-color); background: rgba(255, 255, 255, 0.02); border-bottom: 3px solid var(--primary-color); }
.tabs-content { padding: 40px; }
.guide-section { margin-bottom: 32px; }
.guide-section h3 { font-size: 18px; color: var(--primary-color); margin-bottom: 16px; }
.info-box { padding: 16px 20px; border-radius: 10px; margin-top: 16px; font-size: 14px; line-height: 1.6; }
.info-box.warning { background: rgba(243, 156, 18, 0.1); border-left: 4px solid #f39c12; }
.info-box.highlight { background: rgba(144, 99, 245, 0.1); border-left: 4px solid var(--primary-color); }
.code-block { background: #1a1a1a; padding: 16px; border-radius: 8px; margin: 12px 0; font-family: monospace; }
.info-table { width: 100%; border-collapse: collapse; margin: 16px 0; }
.info-table th, .info-table td { padding: 12px; text-align: left; border-bottom: 1px solid var(--border-color); font-size: 14px; }
.step-card { display: flex; gap: 20px; margin-bottom: 24px; padding: 20px; background: var(--bg-tertiary); border-radius: 12px; }
.step-number { width: 40px; height: 40px; border-radius: 50%; background: var(--primary-color); color: white; display: flex; align-items: center; justify-content: center; font-weight: 700; flex-shrink: 0; }
.styled-list { list-style: none; padding: 0; }
.styled-list li { margin-bottom: 8px; padding-left: 20px; position: relative; }
.styled-list li::before { content: "•"; position: absolute; left: 0; color: var(--primary-color); font-weight: bold; }
</style>
