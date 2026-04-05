<template>
  <div class="reader-container">
    <div class="text-content" @mouseup="handleSelection" @touchend="handleSelection">
      <p>
        The developers used complex macros to obfuscate the C code, making reverse engineering nearly impossible. 
        This is a dummy text paragraph to test our text selection logic and DOM event handling.
      </p>
    </div>

    <div
      v-if="showPopup"
      class="popup"
      :style="{ top: popupPosition.y + 'px', left: popupPosition.x + 'px' }"
    >
      <div class="popup-header">
        <strong>{{ selectedWord }}</strong>
      </div>

      <div v-if="viewMode === 'initial'" class="button-group">
        <button class="btn-primary" @click="submitPayload">Переклад</button>
        <button class="btn-secondary" @click="viewMode = 'hypothesis'">Гіпотеза</button>
      </div>

      <div v-else class="popup-body">
        <input
          v-model="hypothesis"
          type="text"
          placeholder="Ваше припущення..."
          @keyup.enter="submitPayload"
          autoFocus
        />
        <button class="btn-primary" @click="submitPayload">ОК</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'

// Стейт видимості та позиції
const showPopup = ref(false)
const popupPosition = reactive({ x: 0, y: 0 })

// Стейт даних
const selectedWord = ref('')
const contextSentence = ref('')
const hypothesis = ref('')

// Стейт режиму: 'initial' (кнопки) або 'hypothesis' (інпут)
const viewMode = ref<'initial' | 'hypothesis'>('initial')

const handleSelection = () => {
  const selection = window.getSelection()
  
  if (!selection || selection.isCollapsed) {
    showPopup.value = false
    return
  }

  const text = selection.toString().trim()
  if (!text) return

  selectedWord.value = text
  contextSentence.value = selection.anchorNode?.parentElement?.innerText || ''

  // Скидаємо режим на початковий при кожному новому виділенні
  viewMode.ref = 'initial' 
  // У Composition API для ref використовуємо .value
  viewMode.value = 'initial'

  const range = selection.getRangeAt(0)
  const rect = range.getBoundingClientRect()

  popupPosition.x = rect.left + window.scrollX + (rect.width / 2) - 125
  popupPosition.y = rect.top + window.scrollY - 100

  showPopup.value = true
}

const submitPayload = () => {
  const payload = {
    word: selectedWord.value,
    context: contextSentence.value,
    hypothesis: hypothesis.value || null // Якщо гіпотези немає, шлемо null
  }

  console.log('Final DTO for Backend:', JSON.stringify(payload, null, 2))

  // Закриваємо поп-ап та очищуємо стейт
  showPopup.value = false
  hypothesis.value = ''
  window.getSelection()?.removeAllRanges()
}
</script>

<style scoped>
.reader-container {
  position: relative;
  max-width: 800px;
  margin: 40px auto;
  padding: 2rem;
  font-size: 1.2rem;
  line-height: 1.8;
  color: #2c3e50;
}

.popup {
  position: absolute;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1);
  z-index: 50;
  width: 260px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.button-group {
  display: flex;
  gap: 8px;
}

.popup-body {
  display: flex;
  gap: 8px;
}

input {
  flex: 1;
  padding: 8px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  font-size: 0.9rem;
}

.btn-primary {
  flex: 1;
  padding: 8px 12px;
  background: #3b82f6;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 500;
}

.btn-secondary {
  flex: 1;
  padding: 8px 12px;
  background: #f1f5f9;
  color: #475569;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  cursor: pointer;
}

.btn-primary:hover { background: #2563eb; }
.btn-secondary:hover { background: #e2e8f0; }
</style>