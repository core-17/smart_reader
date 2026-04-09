<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import VuePdfApp from 'vue3-pdf-app'
import 'vue3-pdf-app/dist/icons/main.css'
import axios from 'axios'

const pdfSource = ref('/sample.pdf')

// Стан поп-апу та даних
const selectedText = ref('')
const contextText = ref('')
const hypothesis = ref('')
const isPopupVisible = ref(false)
const popupStyle = ref({ top: '0px', left: '0px' })

// Стан запиту
const isTranslating = ref(false)
const translationResult = ref<any>(null)

// Очищення стану при закритті поп-апу
const closePopup = () => {
  isPopupVisible.value = false
  selectedText.value = ''
  contextText.value = ''
  hypothesis.value = ''
  translationResult.value = null
}

const handleTextSelection = async () => {
  setTimeout(() => {
    const selection = window.getSelection()
    
    if (!selection || selection.rangeCount === 0) return;

// --- НОВИЙ АЛГОРИТМ ВИТЯГУВАННЯ ТЕКСТУ З ПРОБІЛАМИ ---
    const range = selection.getRangeAt(0)
    const fragment = range.cloneContents() 
    
    // Вказуємо, що це масив рядків
    const textParts: string[] = [] 
    
    fragment.childNodes.forEach(node => {
      const text = node.textContent?.trim()
      if (text) {
        textParts.push(text)
      }
    })
    
    const cleanText = textParts.join(' ').trim()

    // -----------------------------------------------------

    if (cleanText && cleanText.length > 0) {
      if (selectedText.value === cleanText && isPopupVisible.value) return;
      
      closePopup()
      selectedText.value = cleanText

      // ШУКАЄМО КОНТЕКСТ СТОРІНКИ PDF (залишається як було)
      let context = cleanText
      let currentNode = selection.anchorNode

      if (currentNode) {
        let container = currentNode.parentElement
        
        let depth = 0;
        while (container && depth < 5) {
          if (
            (container.classList && container.classList.contains('textLayer')) || 
            (container.textContent && container.textContent.length > 100)
          ) {
            break;
          }
          container = container.parentElement
          depth++;
        }

        if (container && container.textContent) {
          // Вказуємо, що це масив рядків
          const extractedContext: string[] = []; 
          
          container.childNodes.forEach(node => {
             const t = node.textContent?.trim();
             if(t) extractedContext.push(t);
          });
          let fullText = extractedContext.join(' ');
          
          let wordIndex = fullText.indexOf(cleanText)
          
          if (wordIndex !== -1) {
            let start = Math.max(0, wordIndex - 200)
            let end = Math.min(fullText.length, wordIndex + cleanText.length + 200)
            context = fullText.substring(start, end)
            
            if (start > 0) context = '...' + context
            if (end < fullText.length) context = context + '...'
          } else {
            context = fullText.substring(0, 400) + '...'
          }
        }
      }

      contextText.value = context.length > cleanText.length ? context : cleanText

      const rect = range.getBoundingClientRect()

      popupStyle.value = {
        top: `${rect.bottom + 10}px`,
        left: `${rect.left + rect.width / 2}px`
      }
      
      isPopupVisible.value = true
    }
  }, 50)
}
// Функція взаємодії з FastAPI
const submitTranslation = async () => {
  if (!selectedText.value) return

  isTranslating.value = true
  translationResult.value = null

  // Формуємо об'єкт запиту (Payload)
  const payload = {
    word: selectedText.value,
    context: contextText.value,
    hypothesis: hypothesis.value || null,
    word_lang: 'auto',
    translation_lang: 'uk',
    explanation_lang: 'uk'
  }

  // ВИВІД У КОНСОЛЬ: Що ми надсилаємо
  console.log('🚀 [FRONTEND] Надсилаємо запит на Backend:', payload)

  try {
    const response = await axios.post('http://localhost:8000/ai/local/dictionary', payload)
    
    // ВИВІД У КОНСОЛЬ: Що ми отримали
    console.log('✅ [BACKEND] Отримано відповідь:', response.data)
    
    translationResult.value = response.data
  } catch (error: any) {
    // ВИВІД У КОНСОЛЬ: Помилка
    console.error('❌ [API ERROR]:', error.response?.data || error.message)
    
    translationResult.value = { 
      error: true, 
      translation: 'Помилка підключення до сервера або ШІ.' 
    }
  } finally {
    isTranslating.value = false
  }
}
// Закриття поп-апу при кліку поза ним
const handleOutsideClick = (e: MouseEvent) => {
  const popupEl = document.querySelector('.selection-popup')
  if (isPopupVisible.value && popupEl && !popupEl.contains(e.target as Node)) {
    // Перевіряємо, чи клік не призвів до нового виділення
    const selection = window.getSelection()
    if (!selection || selection.toString().trim().length === 0) {
      closePopup()
    }
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
    <VuePdfApp 
      :pdf="pdfSource" 
      theme="light" 
    />

    <div 
      v-if="isPopupVisible" 
      class="selection-popup" 
      :style="popupStyle"
      @mousedown.stop >
      <div class="popup-header">
        <strong>{{ selectedText }}</strong>
      </div>

      <div v-if="!translationResult && !isTranslating" class="popup-body">
        <input 
          v-model="hypothesis" 
          type="text" 
          placeholder="Ваше припущення (необов'язково)" 
          class="hypothesis-input"
          @keyup.enter="submitTranslation"
        />
        <button class="action-btn" @click="submitTranslation">
          Перекласти
        </button>
      </div>

      <div v-else-if="isTranslating" class="popup-body loading">
        <span class="spinner"></span> Запит до ШІ...
      </div>

      <div v-else-if="translationResult" class="popup-body result">
        <div v-if="translationResult.error" class="error-text">
          {{ translationResult.translation }}
        </div>
        <template v-else>
          <div class="translation"><strong>Переклад:</strong> {{ translationResult.translation }}</div>
          <div class="context"><strong>Контекст:</strong> {{ translationResult.contextual_meaning }}</div>
          
          <div v-if="translationResult.hypothesis_feedback" 
               class="feedback" 
               :class="{ 'correct': translationResult.hypothesis_feedback.is_correct }">
            <strong>Фідбек:</strong> {{ translationResult.hypothesis_feedback.explanation }}
          </div>
        </template>
        <button class="action-btn secondary" @click="closePopup">Закрити</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.reader-container {
  width: 100vw;
  height: 100vh;
  position: relative;
}

/* Оновлені стилі поп-апу як "картки" */
.selection-popup {
  position: fixed;
  transform: translateX(-50%);
  z-index: 9999;
  background: white;
  border-radius: 8px;
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.2);
  width: 320px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid #e5e7eb;
}

/* Хвостик вгорі (бо тепер поп-ап під текстом) */
.selection-popup::before {
  content: '';
  position: absolute;
  bottom: 100%;
  left: 50%;
  transform: translateX(-50%);
  border-width: 8px;
  border-style: solid;
  border-color: transparent transparent white transparent;
}

.popup-header {
  background: #f3f4f6;
  padding: 10px 15px;
  font-size: 14px;
  border-bottom: 1px solid #e5e7eb;
  color: #1f2937;
  /* Виправлено для фраз: текст переноситься нормально */
  white-space: normal; 
  word-break: break-word;
}

.popup-body {
  padding: 15px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.hypothesis-input {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 14px;
  outline: none;
  box-sizing: border-box;
}

.hypothesis-input:focus {
  border-color: #3b82f6;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
}

.action-btn {
  background: #2563eb;
  color: white;
  border: none;
  padding: 8px;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 500;
  transition: background 0.2s;
}

.action-btn:hover { background: #1d4ed8; }
.action-btn.secondary { background: #f3f4f6; color: #4b5563; margin-top: 10px; }
.action-btn.secondary:hover { background: #e5e7eb; }

.result {
  font-size: 13px;
  line-height: 1.5;
  color: #374151;
}

.feedback {
  margin-top: 8px;
  padding: 8px;
  background: #fef2f2;
  border-left: 4px solid #ef4444;
  border-radius: 4px;
}
.feedback.correct {
  background: #f0fdf4;
  border-color: #22c55e;
}

.loading {
  align-items: center;
  color: #6b7280;
  font-size: 14px;
}

.spinner {
  width: 20px;
  height: 20px;
  border: 2px solid #e5e7eb;
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }
</style>