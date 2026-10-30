<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import VuePdfEmbed from 'vue-pdf-embed'
import 'vue-pdf-embed/dist/styles/annotationLayer.css'
import 'vue-pdf-embed/dist/styles/textLayer.css'
import '@/assets/reader.css'

import { useBooks, type BookItem } from '@/composables/useBooks'
import AuthModal from './AuthModal.vue'

interface CurrentUser {
  id: number
  username: string
  email: string
}

interface LexiconHistoryItem {
  id: string
  bookId: number | null
  bookTitle: string
  text: string
  action: 'translate' | 'explain' | 'vocabulary'
  result: string
  fromDb: boolean
  createdAt: string
}

interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  pages?: number[]
  createdAt: string
}

interface ChatSession {
  id: string
  bookId: number
  title: string
  createdAt: string
  messages: ChatMessage[]
}

const currentUser = ref<CurrentUser | null>(null)
const makePublicOnUpload = ref(false)
const ocrLang = ref<'ukr+eng' | 'eng' | 'ukr'>('ukr+eng')
const ragTopK = ref<number>(5)
const maxPreferredPdfWidth = ref<number>(920)

// Стани панелей та меню
const isBooksDrawerOpen = ref(false)
const isAiPanelOpen = ref(true)
const isAccountMenuOpen = ref(false)
const isSettingsModalOpen = ref(false)
const activeAiTab = ref<'analyze' | 'history' | 'chat'>('analyze')

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
  triggerRagIndex,
  uploadBook,
  deleteBook,
} = useBooks(() => currentUser.value?.id ?? null)

// --- АДАПТИВНЕ МАСШТАБУВАННЯ PDF ---
const pdfViewportRef = ref<HTMLElement | null>(null)
const pdfContainer = ref<HTMLElement | null>(null)
const computedPdfWidth = ref<number>(750)
let resizeObserver: ResizeObserver | null = null

const updatePdfDimensions = () => {
  if (!pdfViewportRef.value) return
  const availableWidth = pdfViewportRef.value.clientWidth - 32 // 16px відступи з обох боків
  if (availableWidth > 240) {
    computedPdfWidth.value = Math.min(maxPreferredPdfWidth.value, availableWidth)
  }
}

watch([isBooksDrawerOpen, isAiPanelOpen, maxPreferredPdfWidth], () => {
  setTimeout(updatePdfDimensions, 220)
})

// --- ІСТОРІЯ СЛІВ ТА ВИРАЗІВ ---
const lexiconHistory = ref<LexiconHistoryItem[]>([])

const loadHistoryFromStorage = () => {
  if (!currentUser.value) return
  const raw = localStorage.getItem(`sr_lexicon_${currentUser.value.id}`)
  if (raw) {
    try {
      lexiconHistory.value = JSON.parse(raw)
    } catch {
      lexiconHistory.value = []
    }
  }
}

const saveHistoryToStorage = () => {
  if (!currentUser.value) return
  localStorage.setItem(
    `sr_lexicon_${currentUser.value.id}`,
    JSON.stringify(lexiconHistory.value.slice(0, 150))
  )
}

// --- ЧАТИ ПО КНИГАХ (RAG) ---
const allBookChats = ref<Record<number, ChatSession[]>>({})
const activeChatId = ref<string | null>(null)
const chatQuestion = ref('')
const isRagStreaming = ref(false)
const ragStageText = ref('')
const chatScrollRef = ref<HTMLElement | null>(null)

const loadChatsFromStorage = () => {
  if (!currentUser.value) return
  const raw = localStorage.getItem(`sr_chats_${currentUser.value.id}`)
  if (raw) {
    try {
      allBookChats.value = JSON.parse(raw)
    } catch {
      allBookChats.value = {}
    }
  }
}

const saveChatsToStorage = () => {
  if (!currentUser.value) return
  localStorage.setItem(`sr_chats_${currentUser.value.id}`, JSON.stringify(allBookChats.value))
}

const currentBookChats = computed<ChatSession[]>(() => {
  if (!activeBook.value) return []
  return allBookChats.value[activeBook.value.id] ?? []
})

const activeChatSession = computed<ChatSession | null>(() => {
  if (!activeBook.value) return null
  const list = currentBookChats.value
  return list.find((c) => c.id === activeChatId.value) ?? list[0] ?? null
})

const createNewChatSession = (bookId?: number) => {
  const targetBookId = bookId ?? activeBook.value?.id
  if (!targetBookId) return

  const list = allBookChats.value[targetBookId] ?? []
  const newSession: ChatSession = {
    id: `chat_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
    bookId: targetBookId,
    title: `Чат #${list.length + 1} (${new Date().toLocaleTimeString('uk-UA', { hour: '2-digit', minute: '2-digit' })})`,
    createdAt: new Date().toISOString(),
    messages: [],
  }

  allBookChats.value[targetBookId] = [newSession, ...list]
  activeChatId.value = newSession.id
  saveChatsToStorage()
}

const deleteChatSession = (sessionId: string) => {
  if (!activeBook.value) return
  const bid = activeBook.value.id
  const filtered = (allBookChats.value[bid] ?? []).filter((c) => c.id !== sessionId)
  allBookChats.value[bid] = filtered
  if (activeChatId.value === sessionId) {
    activeChatId.value = filtered[0]?.id ?? null
  }
  saveChatsToStorage()
}

watch(activeBook, (newBook) => {
  if (!newBook) {
    activeChatId.value = null
    return
  }
  const existing = allBookChats.value[newBook.id] ?? []
  if (existing.length === 0) {
    createNewChatSession(newBook.id)
  } else {
    activeChatId.value = existing[0].id
  }
})

const scrollToChatBottom = () => {
  nextTick(() => {
    if (chatScrollRef.value) {
      chatScrollRef.value.scrollTop = chatScrollRef.value.scrollHeight
    }
  })
}

const askBookQuestion = async () => {
  if (!activeBook.value || !chatQuestion.value.trim() || isRagStreaming.value) return
  const questionText = chatQuestion.value.trim()
  chatQuestion.value = ''

  if (!activeChatSession.value) {
    createNewChatSession(activeBook.value.id)
  }
  const session = activeChatSession.value!

  // Оновлюємо заголовок чату за першим питанням
  if (session.messages.length === 0) {
    session.title = questionText.length > 32 ? questionText.slice(0, 32) + '…' : questionText
  }

  session.messages.push({
    id: `u_${Date.now()}`,
    role: 'user',
    content: questionText,
    createdAt: new Date().toLocaleTimeString('uk-UA', { hour: '2-digit', minute: '2-digit' }),
  })

  const assistantMsg: ChatMessage = {
    id: `a_${Date.now() + 1}`,
    role: 'assistant',
    content: '',
    pages: [],
    createdAt: new Date().toLocaleTimeString('uk-UA', { hour: '2-digit', minute: '2-digit' }),
  }
  session.messages.push(assistantMsg)
  const reactiveAssistantMsg = session.messages[session.messages.length - 1]

  isRagStreaming.value = true
  ragStageText.value = 'Готуємо запит до ШІ...'
  scrollToChatBottom()

  try {
    const res = await fetch(`/api/books/${activeBook.value.id}/rag/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question: questionText,
        top_k: ragTopK.value,
        stream: true,
      }),
    })

    if (!res.ok || !res.body) {
      const errData = await res.json().catch(() => ({}))
      throw new Error(errData.detail || 'Помилка отримання відповіді від RAG')
    }

    const reader = res.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''

    while (true) {
      const { value, done } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const parts = buffer.split('\n\n')
      buffer = parts.pop() ?? ''

      for (const part of parts) {
        const line = part.trim()
        if (!line.startsWith('data:')) continue
        const jsonStr = line.replace(/^data:\s*/, '')
        try {
          const event = JSON.parse(jsonStr)
          if (event.stage === 'embedding_query') {
            ragStageText.value = event.message || 'Аналізуємо запитання...'
          } else if (event.stage === 'chunks_found') {
            ragStageText.value = event.message || 'Знайдено контекст, генеруємо...'
            reactiveAssistantMsg.pages = event.pages || []
          } else if (event.stage === 'generating') {
            ragStageText.value = 'ШІ пише відповідь...'
            reactiveAssistantMsg.content += event.token || ''
            scrollToChatBottom()
          } else if (event.stage === 'done') {
            if (!reactiveAssistantMsg.content && event.answer) {
              reactiveAssistantMsg.content = event.answer
            }
            if (event.pages) reactiveAssistantMsg.pages = event.pages
          } else if (event.stage === 'error') {
            reactiveAssistantMsg.content = `⚠️ ${event.message}`
          }
        } catch {
          // Ігноруємо неповні пакети
        }
      }
    }
  } catch (err: any) {
    reactiveAssistantMsg.content = `⚠️ Помилка: ${err.message || 'Не вдалося звернутися до ШІ'}`
  } finally {
    isRagStreaming.value = false
    ragStageText.value = ''
    saveChatsToStorage()
    scrollToChatBottom()
  }
}

// --- АВТОРИЗАЦІЯ ТА ЖИТТЄВИЙ ЦИКЛ ---
onMounted(() => {
  const saved = localStorage.getItem('smart_reader_user')
  if (saved) {
    try {
      currentUser.value = JSON.parse(saved)
      loadHistoryFromStorage()
      loadChatsFromStorage()
      fetchBooks()
    } catch {
      localStorage.removeItem('smart_reader_user')
    }
  }

  document.addEventListener('mouseup', onDocumentMouseUp)
  document.addEventListener('click', onGlobalClick)

  nextTick(() => {
    if (pdfViewportRef.value) {
      resizeObserver = new ResizeObserver(() => updatePdfDimensions())
      resizeObserver.observe(pdfViewportRef.value)
      updatePdfDimensions()
    }
  })
})

onUnmounted(() => {
  document.removeEventListener('mouseup', onDocumentMouseUp)
  document.removeEventListener('click', onGlobalClick)
  resizeObserver?.disconnect()
})

watch(currentUser, (val) => {
  if (val) {
    nextTick(() => {
      if (pdfViewportRef.value) {
        resizeObserver?.disconnect()
        resizeObserver = new ResizeObserver(() => updatePdfDimensions())
        resizeObserver.observe(pdfViewportRef.value)
        updatePdfDimensions()
      }
    })
  }
})

const onAuthSuccess = (user: CurrentUser) => {
  currentUser.value = user
  localStorage.setItem('smart_reader_user', JSON.stringify(user))
  loadHistoryFromStorage()
  loadChatsFromStorage()
  fetchBooks()
}

const logout = () => {
  isAccountMenuOpen.value = false
  currentUser.value = null
  localStorage.removeItem('smart_reader_user')
}

const handleSelectBook = (book: BookItem) => {
  selectBook(book)
  isBooksDrawerOpen.value = false
}

const onFileChange = (e: Event) => {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (file) {
    uploadBook(file, makePublicOnUpload.value)
    ;(e.target as HTMLInputElement).value = ''
  }
}

// Закриття меню акаунта при кліку поза ним
const onGlobalClick = (e: MouseEvent) => {
  const target = e.target as HTMLElement | null
  if (!target?.closest('.account-menu-wrapper')) {
    isAccountMenuOpen.value = false
  }
}

// --- ВИДІЛЕННЯ ТЕКСТУ ТІЛЬКИ ВСЕРЕДИНІ КНИГИ ---
const selectedText = ref('')
const popup = ref({ x: 0, y: 0, visible: false })
const isAiLoading = ref(false)
const backendResponse = ref<string | null>(null)
const fromDb = ref<boolean | null>(null)
const lastAction = ref<'translate' | 'explain' | 'vocabulary'>('translate')

const onDocumentMouseUp = (e: MouseEvent) => {
  const target = e.target as Element | null
  if (target?.closest?.('.selection-popup')) return

  const selection = window.getSelection()
  const text = selection?.toString().trim() ?? ''

  // Перевіряємо, щоб виділення починалося і закінчувалося суворо всередині контейнера PDF книги
  const isInsideBook =
    pdfContainer.value &&
    selection?.anchorNode &&
    selection?.focusNode &&
    pdfContainer.value.contains(selection.anchorNode) &&
    pdfContainer.value.contains(selection.focusNode)

  if (!text || !isInsideBook) {
    popup.value.visible = false
    return
  }

  selectedText.value = text
  const rect = selection!.getRangeAt(0).getBoundingClientRect()
  popup.value = {
    x: Math.min(window.innerWidth - 160, Math.max(160, rect.left + rect.width / 2)),
    y: Math.max(60, rect.top - 48),
    visible: true,
  }
}

const sendTextToBackend = async (
  action: 'translate' | 'explain' | 'vocabulary',
  forceRefresh = false
) => {
  if (!selectedText.value) return
  lastAction.value = action
  popup.value.visible = false
  isAiPanelOpen.value = true
  activeAiTab.value = 'analyze'
  isAiLoading.value = true

  try {
    const res = await fetch('/api/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text: selectedText.value,
        action,
        force_refresh: forceRefresh,
      }),
    })
    const data = await res.json()
    backendResponse.value = data.result
    fromDb.value = data.from_db

    // Додаємо запис в історію запитів
    const entry: LexiconHistoryItem = {
      id: `lex_${Date.now()}`,
      bookId: activeBook.value?.id ?? null,
      bookTitle: activeBook.value?.title ?? 'Загальне',
      text: selectedText.value,
      action,
      result: data.result,
      fromDb: Boolean(data.from_db),
      createdAt: new Date().toLocaleTimeString('uk-UA', { hour: '2-digit', minute: '2-digit' }),
    }
    lexiconHistory.value = [
      entry,
      ...lexiconHistory.value.filter(
        (item) => !(item.text.toLowerCase() === entry.text.toLowerCase() && item.action === action)
      ),
    ]
    saveHistoryToStorage()
  } finally {
    isAiLoading.value = false
  }
}

const openHistoryItem = (item: LexiconHistoryItem) => {
  selectedText.value = item.text
  backendResponse.value = item.result
  fromDb.value = item.fromDb
  lastAction.value = item.action
  activeAiTab.value = 'analyze'
}

const clearLexiconHistory = () => {
  if (!confirm('Очистити всю історію розібраних слів?')) return
  lexiconHistory.value = []
  saveHistoryToStorage()
}

const actionLabel = (action: 'translate' | 'explain' | 'vocabulary') => {
  if (action === 'translate') return '🌐 Переклад'
  if (action === 'explain') return '💡 Пояснення'
  return '🗂 Словник'
}
</script>

<template>
  <AuthModal v-if="!currentUser" @success="onAuthSuccess" />

  <div v-else class="app-shell">
    <!-- 1. ВЕРХНІЙ ГОЛОВНИЙ ХЕДЕР -->
    <header class="top-navbar">
      <div class="navbar-left">
        <button
          class="books-drawer-btn"
          :class="{ active: isBooksDrawerOpen }"
          @click="isBooksDrawerOpen = !isBooksDrawerOpen"
        >
          <span class="burger-icon">☰</span>
          <span>Книги</span>
          <span class="books-count-pill">{{ books.length }}</span>
        </button>

        <div class="brand-title">
          <span class="brand-logo">📖</span>
          <span class="brand-text">Smart Reader</span>
        </div>
      </div>

      <div class="navbar-center">
        <span v-if="activeBook" class="current-book-pill" :title="activeBook.title">
          📄 {{ activeBook.title }}
        </span>
        <span v-else class="current-book-pill muted">Книгу не обрано</span>
      </div>

      <div class="navbar-right">
        <div class="account-menu-wrapper">
          <button
            class="avatar-circle"
            :title="currentUser.username"
            @click.stop="isAccountMenuOpen = !isAccountMenuOpen"
          >
            {{ currentUser.username.charAt(0).toUpperCase() }}
          </button>

          <div v-if="isAccountMenuOpen" class="account-dropdown">
            <div class="account-dropdown-header">
              <strong>{{ currentUser.username }}</strong>
              <span>{{ currentUser.email }}</span>
            </div>
            <div class="dropdown-divider"></div>
            <button
              class="dropdown-item"
              @click="isSettingsModalOpen = true; isAccountMenuOpen = false"
            >
              ⚙️ Налаштування
            </button>
            <button class="dropdown-item danger" @click="logout">
              🚪 Вийти
            </button>
          </div>
        </div>
      </div>
    </header>

    <!-- 2. НИЖНІЙ ПІД-ХЕДЕР (КЕРУВАННЯ КНИГОЮ ТА ПАНЕЛЛЮ ШІ) -->
    <div class="sub-header">
      <div class="sub-header-left">
        <template v-if="activeBook">
          <div class="version-toggle">
            <button
              :class="{ active: selectedVersion === 'raw' }"
              @click="toggleVersion('raw')"
            >
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

          <!-- Кнопка OCR -->
          <button
            v-if="!activeBook.has_ocr"
            class="sub-action-btn"
            :disabled="activeBook.ocr_status === 'processing'"
            @click="triggerOcr(activeBook, ocrLang)"
          >
            {{ activeBook.ocr_status === 'processing' ? '⏳ OCR виконується...' : '🔍 Запустити OCR' }}
          </button>

          <!-- Кнопка та статус RAG -->
          <button
            v-if="activeBook.rag_status !== 'completed'"
            class="sub-action-btn rag-btn"
            :disabled="activeBook.rag_status === 'indexing'"
            @click="triggerRagIndex(activeBook)"
          >
            <template v-if="activeBook.rag_status === 'indexing'">
              ⏳ Індексація RAG: {{ activeBook.rag_progress || 0 }}%
            </template>
            <template v-else>
              🧠 Індексувати для RAG
            </template>
          </button>
          <span v-else class="rag-ready-badge">
            ✅ RAG активний
          </span>
        </template>
      </div>

      <div class="sub-header-right">
        <button
          class="toggle-ai-btn"
          :class="{ active: isAiPanelOpen }"
          @click="isAiPanelOpen = !isAiPanelOpen"
        >
          🤖 {{ isAiPanelOpen ? 'Сховати ШІ' : 'Панель ШІ' }}
        </button>
      </div>
    </div>

    <!-- 3. РОБОЧА ОБЛАСТЬ (ВИЇЗНЕ МЕНЮ КНИГ + PDF + ПАНЕЛЬ ШІ) -->
    <div class="workspace-body">
      <!-- Виїзна панель списку книг -->
      <div
        v-if="isBooksDrawerOpen"
        class="drawer-backdrop"
        @click="isBooksDrawerOpen = false"
      ></div>

      <aside class="books-drawer" :class="{ open: isBooksDrawerOpen }">
        <div class="drawer-header">
          <h3>📚 Бібліотека книг</h3>
          <button class="close-icon-btn" @click="isBooksDrawerOpen = false">✕</button>
        </div>

        <div class="drawer-upload-bar">
          <label class="public-checkbox">
            <input v-model="makePublicOnUpload" type="checkbox" />
            <span>Публічна</span>
          </label>
          <label class="upload-btn">
            {{ isUploading ? '⏳ Завантаження...' : '➕ Додати PDF' }}
            <input
              type="file"
              accept="application/pdf"
              :disabled="isUploading"
              @change="onFileChange"
            />
          </label>
        </div>

        <div class="books-list">
          <div
            v-for="b in books"
            :key="b.id"
            class="book-card"
            :class="{ active: activeBook?.id === b.id }"
            @click="handleSelectBook(b)"
          >
            <div class="book-info">
              <span class="book-title" :title="b.title">📄 {{ b.title }}</span>
              <div class="book-tags">
                <span class="access-tag" :class="{ public: b.is_public }">
                  {{ b.is_public ? '🌐 Публічна' : '🔒 Приватна' }}
                </span>
                <span v-if="b.has_ocr" class="status-pill ocr">OCR</span>
                <span v-if="b.rag_status === 'completed'" class="status-pill rag">RAG</span>
              </div>
            </div>

            <div class="book-actions" @click.stop>
              <button
                v-if="b.is_mine"
                class="mini-btn delete"
                title="Видалити книгу"
                @click="deleteBook(b.id)"
              >
                🗑
              </button>
            </div>
          </div>
          <p v-if="books.length === 0" class="empty-hint">
            Бібліотека порожня. Додайте свій перший PDF-файл!
          </p>
        </div>
      </aside>

      <!-- ЦЕНТРАЛЬНА ОБЛАСТЬ ЧИТАННЯ КНИГИ -->
      <section ref="pdfViewportRef" class="pdf-viewport">
        <div ref="pdfContainer" class="pdf-container">
          <VuePdfEmbed
            v-if="pdfSourceUrl"
            :key="pdfSourceUrl"
            :source="pdfSourceUrl"
            :width="computedPdfWidth"
            text-layer
            annotation-layer
          />
          <div v-else class="empty-reader-state">
            <div class="empty-reader-card">
              <span class="empty-icon">📚</span>
              <h3>Оберіть книгу для читання</h3>
              <p>Натисніть кнопку «☰ Книги» у лівому верхньому кутку, щоб відкрити бібліотеку або завантажити новий PDF.</p>
              <button class="primary-btn" @click="isBooksDrawerOpen = true">
                Відкрити бібліотеку
              </button>
            </div>
          </div>
        </div>

        <!-- Спливаюче меню дій ШІ (тільки для тексту книги) -->
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

      <!-- ПРАВА ПАНЕЛЬ ШІ (МОЖНА ПРИХОВАТИ) -->
      <aside v-show="isAiPanelOpen" class="ai-sidebar">
        <div class="ai-tabs">
          <button
            :class="{ active: activeAiTab === 'analyze' }"
            @click="activeAiTab = 'analyze'"
          >
            🔍 Розбір
          </button>
          <button
            :class="{ active: activeAiTab === 'history' }"
            @click="activeAiTab = 'history'"
          >
            📜 Історія ({{ lexiconHistory.length }})
          </button>
          <button
            :class="{ active: activeAiTab === 'chat' }"
            @click="activeAiTab = 'chat'"
          >
            💬 Чат книги
          </button>
        </div>

        <!-- ВКЛАДКА 1: РОЗБІР ФРАГМЕНТА -->
        <div v-if="activeAiTab === 'analyze'" class="ai-tab-body">
          <div class="section-label">Виділений фрагмент у книзі:</div>
          <div class="selected-box">
            {{ selectedText || 'Виділіть слово або речення прямо на сторінці PDF-книги...' }}
          </div>

          <div v-if="selectedText" class="quick-action-row">
            <button
              :class="{ active: lastAction === 'translate' }"
              :disabled="isAiLoading"
              @click="sendTextToBackend('translate')"
            >
              🌐 Переклад
            </button>
            <button
              :class="{ active: lastAction === 'explain' }"
              :disabled="isAiLoading"
              @click="sendTextToBackend('explain')"
            >
              💡 Пояснити
            </button>
            <button
              :class="{ active: lastAction === 'vocabulary' }"
              :disabled="isAiLoading"
              @click="sendTextToBackend('vocabulary')"
            >
              🗂 Словник
            </button>
          </div>

          <div class="response-header">
            <span class="section-label">Відповідь ШІ:</span>
            <span v-if="fromDb !== null && !isAiLoading" class="badge" :class="fromDb ? 'cached' : 'fresh'">
              {{ fromDb ? '⚡ З кешу БД' : '🤖 Нова генерація' }}
            </span>
          </div>

          <!-- Анімація роботи ШІ під час аналізу -->
          <div v-if="isAiLoading" class="ai-working-card">
            <div class="ai-pulse-orb"></div>
            <div class="ai-working-info">
              <strong>ШІ аналізує фрагмент...</strong>
              <span>Формуємо контекстне пояснення через модель Ollama</span>
              <div class="ai-wave-bars">
                <span></span><span></span><span></span><span></span>
              </div>
            </div>
          </div>

          <div v-else class="response-box">
            {{ backendResponse || 'Тут з’явиться детальний розбір обраного фрагмента...' }}
          </div>

          <button
            v-if="backendResponse && !isAiLoading"
            class="refresh-btn"
            @click="sendTextToBackend(lastAction, true)"
          >
            🔄 Згенерувати заново через ШІ
          </button>
        </div>

        <!-- ВКЛАДКА 2: ІСТОРІЯ ЗАПИТІВ (СЛІВ ТА ВИРАЗІВ) -->
        <div v-else-if="activeAiTab === 'history'" class="ai-tab-body">
          <div class="history-top-bar">
            <span class="section-label">Розібрані слова та вирази:</span>
            <button
              v-if="lexiconHistory.length > 0"
              class="text-danger-btn"
              @click="clearLexiconHistory"
            >
              Очистити
            </button>
          </div>

          <div v-if="lexiconHistory.length === 0" class="empty-hint">
            Історія порожня. Виділіть будь-яке слово або речення в книзі, щоб перекласти або пояснити його.
          </div>

          <div v-else class="history-list">
            <div
              v-for="item in lexiconHistory"
              :key="item.id"
              class="history-card"
              @click="openHistoryItem(item)"
            >
              <div class="history-card-top">
                <span class="history-action-tag">{{ actionLabel(item.action) }}</span>
                <span class="history-time">{{ item.createdAt }}</span>
              </div>
              <div class="history-phrase">{{ item.text }}</div>
              <div class="history-preview">{{ item.result }}</div>
            </div>
          </div>
        </div>

        <!-- ВКЛАДКА 3: RAG-ЧАТ ПО КНИЗІ -->
        <div v-else-if="activeAiTab === 'chat'" class="ai-tab-body chat-tab-body">
          <div v-if="!activeBook" class="empty-hint">
            Спочатку оберіть книгу в бібліотеці, щоб почати чат по її змісту.
          </div>

          <template v-else>
            <!-- Панель керування сесіями чатів книги -->
            <div class="chat-sessions-bar">
              <select
                v-model="activeChatId"
                class="chat-session-select"
                title="Оберіть збережений чат"
              >
                <option v-for="c in currentBookChats" :key="c.id" :value="c.id">
                  💬 {{ c.title }} ({{ c.messages.length }})
                </option>
              </select>

              <button
                class="new-chat-btn"
                title="Створити новий чат (поточний збережеться)"
                @click="createNewChatSession(activeBook.id)"
              >
                ➕ Новий
              </button>

              <button
                v-if="activeChatSession && currentBookChats.length > 1"
                class="delete-chat-btn"
                title="Видалити цей чат"
                @click="deleteChatSession(activeChatSession.id)"
              >
                🗑
              </button>
            </div>

            <!-- Якщо книга ще не проіндексована для RAG -->
            <div v-if="activeBook.rag_status !== 'completed'" class="rag-setup-box">
              <h4>🧠 Книга ще не проіндексована для RAG</h4>
              <p>
                Щоб ставити запитання по змісту книги та отримувати точні відповіді з посиланнями на сторінки, запустіть індексацію.
              </p>
              <div v-if="activeBook.rag_status === 'indexing'" class="rag-progress-wrap">
                <div class="rag-progress-bar">
                  <div
                    class="rag-progress-fill"
                    :style="{ width: `${activeBook.rag_progress || 5}%` }"
                  ></div>
                </div>
                <span>Векторизація тексту: {{ activeBook.rag_progress || 5 }}%</span>
              </div>
              <button
                v-else
                class="primary-btn"
                @click="triggerRagIndex(activeBook)"
              >
                🚀 Проіндексувати книгу зараз
              </button>
            </div>

            <!-- Вікно повідомлень чату -->
            <div ref="chatScrollRef" class="chat-messages-area">
              <div
                v-if="!activeChatSession || activeChatSession.messages.length === 0"
                class="chat-empty-prompt"
              >
                <p>Запитайте будь-що за змістом книги <strong>«{{ activeBook.title }}»</strong>.</p>
                <span>Усі попередні чати автоматично зберігаються у випадаючому списку зверху.</span>
              </div>

              <template v-else>
                <div
                  v-for="msg in activeChatSession.messages"
                  :key="msg.id"
                  class="chat-bubble"
                  :class="msg.role"
                >
                  <div class="chat-bubble-meta">
                    <strong>{{ msg.role === 'user' ? 'Ви' : '🤖 ШІ-Асистент' }}</strong>
                    <span>{{ msg.createdAt }}</span>
                  </div>
                  <div class="chat-bubble-text">
                    {{ msg.content || (isRagStreaming && msg.role === 'assistant' ? '...' : '') }}
                  </div>
                  <div v-if="msg.pages && msg.pages.length > 0" class="chat-sources">
                    📑 Джерела: стор. {{ msg.pages.join(', ') }}
                  </div>
                </div>
              </template>

              <!-- Анімований індикатор живої роботи ШІ в чаті -->
              <div v-if="isRagStreaming" class="ai-working-card compact">
                <div class="ai-pulse-orb"></div>
                <div class="ai-working-info">
                  <strong>{{ ragStageText || 'ШІ обробляє запит...' }}</strong>
                  <div class="ai-wave-bars">
                    <span></span><span></span><span></span><span></span>
                  </div>
                </div>
              </div>
            </div>

            <!-- Поле вводу запитання -->
            <form class="chat-input-row" @submit.prevent="askBookQuestion">
              <input
                v-model="chatQuestion"
                type="text"
                placeholder="Поставте запитання по книзі..."
                :disabled="activeBook.rag_status !== 'completed' || isRagStreaming"
              />
              <button
                type="submit"
                :disabled="activeBook.rag_status !== 'completed' || isRagStreaming || !chatQuestion.trim()"
              >
                ➤
              </button>
            </form>
          </template>
        </div>
      </aside>
    </div>

    <!-- 4. МОДАЛЬНЕ ВІКНО НАЛАШТУВАНЬ -->
    <div v-if="isSettingsModalOpen" class="modal-backdrop" @click.self="isSettingsModalOpen = false">
      <div class="settings-modal">
        <div class="settings-header">
          <h3>⚙️ Налаштування читача</h3>
          <button class="close-icon-btn" @click="isSettingsModalOpen = false">✕</button>
        </div>

        <div class="settings-body">
          <div class="setting-field">
            <label>Максимальна ширина сторінки книги (px)</label>
            <input
              v-model.number="maxPreferredPdfWidth"
              type="range"
              min="550"
              max="1400"
              step="25"
            />
            <span>{{ maxPreferredPdfWidth }} px (адаптивно звужується під вікно браузера)</span>
          </div>

          <div class="setting-field">
            <label>Мова розпізнавання OCR за замовчуванням</label>
            <select v-model="ocrLang">
              <option value="ukr+eng">🇺🇦 + 🇬🇧 Українська та Англійська</option>
              <option value="ukr">🇺🇦 Тільки Українська</option>
              <option value="eng">🇬🇧 Тільки Англійська</option>
            </select>
          </div>

          <div class="setting-field">
            <label>Кількість фрагментів контексту для RAG (Top-K)</label>
            <input v-model.number="ragTopK" type="number" min="2" max="12" />
          </div>
        </div>

        <div class="settings-footer">
          <button class="primary-btn" @click="isSettingsModalOpen = false">Зберегти та закрити</button>
        </div>
      </div>
    </div>
  </div>
</template>