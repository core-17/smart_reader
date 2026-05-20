<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import VuePdfApp from 'vue3-pdf-app'
import 'vue3-pdf-app/dist/icons/main.css'
import axios from 'axios'

const pdfSource = ref('/sample.pdf')

// Popup and selection state
const selectedText = ref('')
const contextText = ref('')
const hypothesis = ref('')
const isPopupVisible = ref(false)
const popupStyle = ref({ top: '0px', left: '0px' })

// Request state
const isTranslating = ref(false)
const isSaving = ref(false)
const translationResult = ref<any>(null)
const saveStatus = ref('')

// Reset popup state
const closePopup = () => {
  isPopupVisible.value = false
  selectedText.value = ''
  contextText.value = ''
  hypothesis.value = ''
  translationResult.value = null
  saveStatus.value = ''
}

// Build auth header from token
const getAuthHeader = () => {
  const token = localStorage.getItem('auth_token')
  return { Authorization: `Bearer ${token}` }
}

const handleTextSelection = async () => {
  setTimeout(() => {
    const selection = window.getSelection()
    if (!selection || selection.rangeCount === 0) return

    const range = selection.getRangeAt(0)
    const fragment = range.cloneContents() 
    const textParts: string[] = [] 
    
    fragment.childNodes.forEach(node => {
      const text = node.textContent?.trim()
      if (text) textParts.push(text)
    })
    
    const cleanText = textParts.join(' ').trim()

    if (cleanText && cleanText.length > 0) {
      if (selectedText.value === cleanText && isPopupVisible.value) return
      
      closePopup()
      selectedText.value = cleanText

      // Context extraction (keep existing Reader.vue logic)
      let context = cleanText
      let currentNode = selection.anchorNode
      if (currentNode) {
        let container = currentNode.parentElement
        let depth = 0
        while (container && depth < 5) {
          if (container.classList?.contains('textLayer') || (container.textContent?.length || 0) > 100) break
          container = container.parentElement
          depth++
        }
        if (container?.textContent) {
          const fullText = container.textContent.replace(/\s+/g, ' ')
          const wordIndex = fullText.indexOf(cleanText)
          if (wordIndex !== -1) {
            let start = Math.max(0, wordIndex - 150)
            let end = Math.min(fullText.length, wordIndex + cleanText.length + 150)
            context = fullText.substring(start, end)
          }
        }
      }
      contextText.value = context

      const rect = range.getBoundingClientRect()
      popupStyle.value = {
        top: `${rect.bottom + window.scrollY + 10}px`,
        left: `${rect.left + window.scrollX + rect.width / 2}px`
      }
      isPopupVisible.value = true
    }
  }, 50)
}

const submitTranslation = async () => {
  if (!selectedText.value) return
  isTranslating.value = true
  
  const payload = {
    word: selectedText.value,
    context: contextText.value,
    hypothesis: hypothesis.value || null,
    word_lang: 'auto',
    translation_lang: 'uk', 
    explanation_lang: 'uk'
  }

  try {
    const response = await axios.post(
      'http://localhost:8000/ai/dictionary', 
      payload,
      { headers: getAuthHeader() }
    )
    translationResult.value = response.data
  } catch (error: any) {
    if (error.response?.status === 401) {
      alert('Сесія завершилась, будь ласка, авторизуйтесь знову.')
      localStorage.removeItem('auth_token')
      location.reload()
    }
    translationResult.value = { error: true, translation: 'Authorization or server error.' }
  } finally {
    isTranslating.value = false
  }
}

// Save to database (/dictionary/ endpoint)
const saveEntry = async () => {
  if (!translationResult.value) return
  isSaving.value = true
  
  try {
    await axios.post(
      'http://localhost:8000/dictionary/', 
      {
        word: selectedText.value,
        translation: translationResult.value.translation,
        context: contextText.value,
        notes: translationResult.value.contextual_meaning
      },
      { headers: getAuthHeader() }
    )
    saveStatus.value = 'Saved ✅'
  } catch (err) {
    saveStatus.value = 'Save failed ❌'
  } finally {
    isSaving.value = false
  }
}

const handleOutsideClick = (e: MouseEvent) => {
  const popupEl = document.querySelector('.selection-popup')
  if (isPopupVisible.value && popupEl && !popupEl.contains(e.target as Node)) {
    const selection = window.getSelection()
    if (!selection || selection.toString().trim().length === 0) closePopup()
  }
}

onMounted(() => {
  document.addEventListener('mouseup', handleTextSelection)
  document.addEventListener('mousedown', handleOutsideClick)
})

onBeforeUnmount(() => {
  document.removeEventListener('mouseup', handleTextSelection)
  document.removeEventListener('mousedown', handleOutsideClick)
})
</script>

<template>
  <div class="reader-container">
    <VuePdfApp :pdf="pdfSource" theme="light" :config="{ sidebarViewOnLoad: 1 }" />

    <div v-if="isPopupVisible" class="selection-popup" :style="popupStyle" @mousedown.stop>
      <div class="popup-header"><strong>{{ selectedText }}</strong></div>

      <div v-if="!translationResult && !isTranslating" class="popup-body">
        <input v-model="hypothesis" type="text" placeholder="Your hypothesis..." class="hypothesis-input" @keyup.enter="submitTranslation" />
        <button class="action-btn" @click="submitTranslation">Translate with AI</button>
      </div>

      <div v-else-if="isTranslating" class="popup-body loading">
        <span class="spinner"></span> Thinking...
      </div>

      <div v-else-if="translationResult" class="popup-body result">
        <template v-if="!translationResult.error">
          <div class="translation"><strong>Translation:</strong> {{ translationResult.translation }}</div>
          <div class="context-meaning"><strong>Explanation:</strong> {{ translationResult.contextual_meaning }}</div>
          
          <button v-if="!saveStatus" class="save-btn" @click="saveEntry" :disabled="isSaving">
            {{ isSaving ? 'Saving...' : 'Add to dictionary' }}
          </button>
          <div v-else class="status-msg">{{ saveStatus }}</div>
        </template>
        <div v-else class="error-text">{{ translationResult.translation }}</div>
        <button class="action-btn secondary" @click="closePopup">Close</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Надійна Flex-сітка без абсолютного позиціювання */
.reader-container {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
}

/* Змушуємо вбудований плагін розтягнутися */
:deep(.pdf-app) {
  flex: 1;
  width: 100% !important;
  height: 100% !important;
}

/* ==========================================
   ЖОРСТКЕ БЛОКУВАННЯ ПАНЕЛІ PDF.JS
   ========================================== */
/* Ховаємо кнопку "Гамбургер" (перемикач панелі) */
:deep(#sidebarToggle) {
  display: none !important;
}

/* Повністю ховаємо контейнер бокової панелі */
:deep(#sidebarContainer) {
  display: none !important;
  width: 0 !important;
}

/* Забороняємо головному контейнеру зсуватися вправо */
:deep(#outerContainer.sidebarOpen #mainContainer) {
  left: 0 !important;
  min-width: 100% !important;
  transition: none !important;
}

/* ==========================================
   СТИЛІ ПОП-АПУ ТА ІНШЕ
   ========================================== */
.selection-popup {
  position: absolute;
  transform: translateX(-50%);
  z-index: 9999;
  background: white;
  border-radius: 12px;
  width: 300px;
  box-shadow: 0 10px 30px rgba(0,0,0,0.15);
  border: 1px solid #e5e7eb;
}
.popup-header { background: #f9fafb; padding: 12px; border-bottom: 1px solid #eee; border-radius: 12px 12px 0 0; }
.popup-body { padding: 15px; display: flex; flex-direction: column; gap: 10px; }
.hypothesis-input { padding: 8px; border: 1px solid #ddd; border-radius: 6px; }
.action-btn { background: #2563eb; color: white; border: none; padding: 10px; border-radius: 6px; cursor: pointer; }
.action-btn.secondary { background: #f3f4f6; color: #666; margin-top: 5px; }
.save-btn { 
  background: #10b981; color: white; border: none; padding: 8px; 
  border-radius: 6px; cursor: pointer; margin-top: 10px; font-weight: bold;
}
.save-btn:disabled { opacity: 0.6; }
.status-msg { text-align: center; font-weight: bold; color: #059669; margin-top: 10px; }
.spinner { width: 16px; height: 16px; border: 2px solid #ccc; border-top-color: #2563eb; border-radius: 50%; animation: spin 1s linear infinite; display: inline-block; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>