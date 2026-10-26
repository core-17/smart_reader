<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import VuePdfEmbed from 'vue-pdf-embed'
import 'vue-pdf-embed/dist/styles/annotationLayer.css'
import 'vue-pdf-embed/dist/styles/textLayer.css'
import '@/assets/reader.css'

import { useBooks } from '@/composables/useBooks'
import AuthModal from './AuthModal.vue'

interface CurrentUser {
  id: number
  username: string
  email: string
}

const currentUser = ref<CurrentUser | null>(null)
const makePublicOnUpload = ref(false)
const ocrLang = ref<'ukr+eng' | 'eng' | 'ukr'>('ukr+eng')

const {
  books,
  activeBook,
  selectedVersion,
  pdfSourceUrl,
  isUploading,
  fetchBooks,
  selectBook,
  toggleVersion,
  triggerOcr,
  uploadBook,
  deleteBook,
} = useBooks(() => currentUser.value?.id ?? null)

// Перевірка сесії при старті
onMounted(() => {
  const saved = localStorage.getItem('smart_reader_user')
  if (saved) {
    try {
      currentUser.value = JSON.parse(saved)
      fetchBooks()
    } catch {
      localStorage.removeItem('smart_reader_user')
    }
  }
})

const onAuthSuccess = (user: CurrentUser) => {
  currentUser.value = user
  localStorage.setItem('smart_reader_user', JSON.stringify(user))
  fetchBooks()
}

const logout = () => {
  currentUser.value = null
  localStorage.removeItem('smart_reader_user')
}

const onFileChange = (e: Event) => {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (file) {
    uploadBook(file, makePublicOnUpload.value)
    ;(e.target as HTMLInputElement).value = ''
  }
}

// Виділення тексту та взаємодія з ШІ
const selectedText = ref('')
const popup = ref({ x: 0, y: 0, visible: false })
const pdfContainer = ref<HTMLElement | null>(null)
const isAiLoading = ref(false)
const backendResponse = ref<string | null>(null)
const fromDb = ref<boolean | null>(null)
const lastAction = ref<'translate' | 'explain' | 'vocabulary'>('translate')

const onDocumentMouseUp = (e: MouseEvent) => {
  if ((e.target as Element | null)?.closest?.('.selection-popup')) return
  const selection = window.getSelection()
  const text = selection?.toString().trim() ?? ''
  if (!text || !pdfContainer.value) {
    popup.value.visible = false
    return
  }
  selectedText.value = text
  const rect = selection!.getRangeAt(0).getBoundingClientRect()
  popup.value = {
    x: rect.left + rect.width / 2,
    y: Math.max(10, rect.top - 48),
    visible: true,
  }
}

const sendTextToBackend = async (action: 'translate' | 'explain' | 'vocabulary', forceRefresh = false) => {
  if (!selectedText.value) return
  lastAction.value = action
  popup.value.visible = false
  isAiLoading.value = true

  try {
    const res = await fetch('/api/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: selectedText.value, action, force_refresh: forceRefresh }),
    })
    const data = await res.json()
    backendResponse.value = data.result
    fromDb.value = data.from_db
  } finally {
    isAiLoading.value = false
  }
}

onMounted(() => {
  document.addEventListener('mouseup', onDocumentMouseUp)
})
onUnmounted(() => {
  document.removeEventListener('mouseup', onDocumentMouseUp)
})
</script>

<template>
  <!-- Стіна входу: якщо користувач не залогінений, додаток повністю заблокований -->
  <AuthModal
    v-if="!currentUser"
    @success="onAuthSuccess"
  />

  <!-- Головний інтерфейс (доступний тільки після входу) -->
  <div v-else class="reader-layout">
    <!-- 1. Бічна панель: Бібліотека -->
    <aside class="sidebar-books">
      <div class="auth-header">
        <span class="user-tag">👤 {{ currentUser.username }}</span>
        <button class="auth-btn" @click="logout">Вийти</button>
      </div>

      <div class="library-header">
        <h3>📚 Книги</h3>
        <div class="upload-box">
          <label style="font-size: 11px; display: flex; align-items: center; gap: 4px; cursor: pointer;">
            <input v-model="makePublicOnUpload" type="checkbox" /> Паблік
          </label>
          <label class="upload-btn">
            {{ isUploading ? '⏳' : '➕ Додати' }}
            <input type="file" accept="application/pdf" :disabled="isUploading" @change="onFileChange" />
          </label>
        </div>
      </div>

      <div class="books-list">
        <div
          v-for="b in books"
          :key="b.id"
          class="book-card"
          :class="{ active: activeBook?.id === b.id }"
          @click="selectBook(b)"
        >
          <div class="book-info">
            <span class="book-title" :title="b.title">📄 {{ b.title }}</span>
            <div class="book-tags">
              <span class="access-tag" :class="{ public: b.is_public }">
                {{ b.is_public ? '🌐 Публічна' : '🔒 Приватна' }}
              </span>
              <span class="ocr-status-tag" :class="b.ocr_status">
                {{ b.ocr_status === 'completed' ? '✅ OCR' : b.ocr_status === 'processing' ? '⏳ OCR...' : '' }}
              </span>
            </div>
          </div>

          <div class="book-actions" @click.stop>
            <button
              v-if="b.is_mine && !b.has_ocr && b.ocr_status !== 'processing'"
              class="mini-btn"
              @click="triggerOcr(b, ocrLang)"
            >
              OCR
            </button>
            <button v-if="b.is_mine" class="mini-btn delete" @click="deleteBook(b.id)">🗑</button>
          </div>
        </div>
        <p v-if="books.length === 0" class="placeholder-small">Книг немає. Завантажте свій перший PDF!</p>
      </div>
    </aside>

    <!-- 2. Центральна область PDF -->
    <section class="pdf-section">
      <div class="toolbar">
        <div v-if="activeBook" class="toolbar-book-meta">
          <strong>{{ activeBook.title }}</strong>
          <div class="version-toggle">
            <button :class="{ active: selectedVersion === 'raw' }" @click="toggleVersion('raw')">
              Оригінал
            </button>
            <button
              :class="{ active: selectedVersion === 'ocr' }"
              :disabled="!activeBook.has_ocr"
              @click="toggleVersion('ocr')"
            >
              OCR
            </button>
          </div>
        </div>

        <div v-if="activeBook && !activeBook.has_ocr" class="ocr-action-bar">
          <select v-model="ocrLang" class="lang-select">
            <option value="ukr+eng">🇺🇦+🇬🇧 Укр+Англ</option>
            <option value="eng">🇬🇧 Англ</option>
            <option value="ukr">🇺🇦 Укр</option>
          </select>
          <button
            class="ocr-btn"
            :disabled="activeBook.ocr_status === 'processing'"
            @click="triggerOcr(activeBook, ocrLang)"
          >
            {{ activeBook.ocr_status === 'processing' ? '⏳ OCR у процесі...' : '🚀 Запустити OCR' }}
          </button>
        </div>
      </div>

      <div ref="pdfContainer" class="pdf-container">
        <VuePdfEmbed
          v-if="pdfSourceUrl"
          :key="pdfSourceUrl"
          :source="pdfSourceUrl"
          :width="750"
          text-layer
          annotation-layer
        />
        <div v-else class="placeholder">Оберіть книгу з лівої панелі</div>
      </div>

      <div
        v-if="popup.visible"
        class="selection-popup"
        :style="{ top: `${popup.y}px`, left: `${popup.x}px` }"
        @mousedown.stop
      >
        <button @click="sendTextToBackend('translate')">🌐 Перекласти</button>
        <button @click="sendTextToBackend('explain')">💡 Пояснити</button>
        <button @click="sendTextToBackend('vocabulary')">🗂 У словник</button>
      </div>
    </section>

    <!-- 3. Панель аналізу -->
    <aside class="sidebar-analysis">
      <h3>Виділений фрагмент:</h3>
      <div class="selected-box">{{ selectedText || 'Виділіть фрагмент у книзі...' }}</div>

      <div class="response-header">
        <h3>Відповідь ШІ:</h3>
        <span v-if="fromDb !== null" class="badge" :class="fromDb ? 'cached' : 'fresh'">
          {{ fromDb ? '⚡ З бази даних' : '🤖 Нова генерація' }}
        </span>
      </div>

      <div class="response-box" :class="{ loading: isAiLoading }">
        {{ isAiLoading ? 'Обробка...' : backendResponse || 'Тут з’явиться розбір...' }}
      </div>

      <button
        v-if="backendResponse && !isAiLoading"
        class="refresh-btn"
        @click="sendTextToBackend(lastAction, true)"
      >
        🔄 Оновити через ШІ
      </button>
    </aside>
  </div>
</template>