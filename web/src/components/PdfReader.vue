<script setup lang="ts">
import { ref } from 'vue'
import VuePdfEmbed from 'vue-pdf-embed'
import 'vue-pdf-embed/dist/styles/annotationLayer.css'
import 'vue-pdf-embed/dist/styles/textLayer.css'

// Порожній префікс: запити йдуть на /api/... через Nginx на 80 порту
const API_BASE = ''

const pdfSource = ref<string | null>(null)
const rawFile = ref<File | null>(null)
const ocrLang = ref<'ukr+eng' | 'eng' | 'ukr'>('ukr+eng')
const isOcrLoading = ref(false)
const isAiLoading = ref(false)

const selectedText = ref('')
const lastAction = ref<'translate' | 'explain' | 'vocabulary'>('translate')
const fromDb = ref<boolean | null>(null)
const popupPosition = ref({ x: 0, y: 0, visible: false })
const backendResponse = ref<string | null>(null)

const onFileChange = (e: Event) => {
  const target = e.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) return

  rawFile.value = file
  pdfSource.value = URL.createObjectURL(file)
}

const runOcrOnPdf = async () => {
  if (!rawFile.value) return
  isOcrLoading.value = true

  try {
    const formData = new FormData()
    formData.append('file', rawFile.value)
    formData.append('lang', ocrLang.value)

    const res = await fetch(`${API_BASE}/api/pdf/process-ocr`, {
      method: 'POST',
      body: formData,
    })

    if (!res.ok) throw new Error('Помилка OCR на сервері')

    const processedBlob = await res.blob()
    pdfSource.value = URL.createObjectURL(processedBlob)
  } catch (err) {
    console.error(err)
    alert('Не вдалося виконати OCR')
  } finally {
    isOcrLoading.value = false
  }
}

const handleMouseUp = () => {
  const selection = window.getSelection()
  const text = selection ? selection.toString().trim() : ''

  if (text.length > 0 && selection && selection.rangeCount > 0) {
    selectedText.value = text
    const range = selection.getRangeAt(0)
    const rect = range.getBoundingClientRect()

    popupPosition.value = {
      x: rect.left + rect.width / 2,
      y: Math.max(10, rect.top - 48),
      visible: true,
    }
  } else {
    popupPosition.value.visible = false
  }
}

const sendTextToBackend = async (
  action: 'translate' | 'explain' | 'vocabulary',
  forceRefresh = false
) => {
  if (!selectedText.value) return
  lastAction.value = action
  popupPosition.value.visible = false
  isAiLoading.value = true
  backendResponse.value = 'Запит обробляється...'

  try {
    const res = await fetch(`${API_BASE}/api/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text: selectedText.value,
        action: action,
        force_refresh: forceRefresh,
      }),
    })
    const data = await res.json()
    backendResponse.value = data.result
    fromDb.value = data.from_db
  } catch (err) {
    console.error(err)
    backendResponse.value = 'Помилка зв’язку з сервером'
  } finally {
    isAiLoading.value = false
  }
}
</script>

<template>
  <div class="reader-layout">
    <div class="pdf-section">
      <div class="toolbar">
        <input type="file" accept="application/pdf" @change="onFileChange" />

        <div v-if="rawFile" class="ocr-controls">
          <select v-model="ocrLang" class="lang-select" :disabled="isOcrLoading">
            <option value="ukr+eng">🇺🇦 + 🇬🇧 Укр + Англ</option>
            <option value="eng">🇬🇧 Тільки Англійська</option>
            <option value="ukr">🇺🇦 Тільки Українська</option>
          </select>

          <button class="ocr-btn" :disabled="isOcrLoading" @click="runOcrOnPdf">
            {{ isOcrLoading ? '⏳ OCR у процесі...' : '🔍 Зробити OCR' }}
          </button>
        </div>
      </div>

      <div class="pdf-container" @mouseup="handleMouseUp">
        <VuePdfEmbed
          v-if="pdfSource"
          :source="pdfSource"
          :width="750"
          text-layer
          annotation-layer
        />
        <p v-else class="placeholder">Завантажте PDF-файл, щоб почати читання</p>
      </div>

      <div
        v-if="popupPosition.visible"
        class="selection-popup"
        :style="{ top: `${popupPosition.y}px`, left: `${popupPosition.x}px` }"
        @mousedown.stop
      >
        <button @click="sendTextToBackend('translate')">🌐 Перекласти</button>
        <button @click="sendTextToBackend('explain')">💡 Пояснити</button>
        <button @click="sendTextToBackend('vocabulary')">🗂 У словник</button>
      </div>
    </div>

    <div class="sidebar-section">
      <h3>Виділений фрагмент:</h3>
      <div class="selected-box">
        {{ selectedText || 'Виділіть будь-яке слово або речення в PDF...' }}
      </div>

      <div class="response-header">
        <h3>Відповідь ШІ:</h3>
        <span v-if="fromDb !== null" class="badge" :class="fromDb ? 'cached' : 'fresh'">
          {{ fromDb ? '⚡ Взято з БД (JSONB)' : '🤖 Нова генерація ШІ' }}
        </span>
      </div>

      <div class="response-box" :class="{ loading: isAiLoading }">
        {{ backendResponse || 'Тут з’явиться переклад або пояснення...' }}
      </div>

      <button
        v-if="backendResponse && !isAiLoading"
        class="refresh-btn"
        @click="sendTextToBackend(lastAction, true)"
      >
        🔄 Запитати ШІ повторно (оновити запис у БД)
      </button>
    </div>
  </div>
</template>

<style scoped>
.reader-layout {
  display: grid;
  grid-template-columns: 1.5fr 1fr;
  gap: 20px;
  width: 100vw;
  height: 100vh;
  padding: 16px;
  box-sizing: border-box;
}

.pdf-section {
  display: flex;
  flex-direction: column;
  border: 1px solid #333;
  border-radius: 8px;
  overflow: hidden;
  background: #2b2b2b;
  position: relative;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  background: #fff;
  color: #181818;
  border-bottom: 1px solid #ddd;
}

.ocr-controls {
  display: flex;
  align-items: center;
  gap: 8px;
}

.lang-select {
  padding: 6px 10px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  background: #f8fafc;
  color: #1e293b;
  font-size: 13px;
}

.ocr-btn {
  white-space: nowrap;
  padding: 6px 14px;
  background: #2563eb;
  color: #fff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 500;
}

.pdf-container {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.placeholder {
  color: #aaa;
  margin-top: 100px;
}

.selection-popup {
  position: fixed;
  z-index: 9999;
  background: #181825;
  padding: 6px;
  border-radius: 6px;
  display: flex;
  gap: 6px;
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.35);
  transform: translateX(-50%);
}

.selection-popup button {
  background: #313244;
  color: #fff;
  border: none;
  padding: 6px 10px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
}

.sidebar-section {
  border: 1px solid #ddd;
  border-radius: 8px;
  padding: 16px;
  background: #fff;
  color: #181818;
  overflow-y: auto;
}

.sidebar-section h3 {
  color: #111827;
  font-weight: 600;
  margin-bottom: 8px;
}

.response-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.badge {
  font-size: 12px;
  padding: 3px 8px;
  border-radius: 12px;
  font-weight: 600;
}

.badge.cached {
  background: #dcfce7;
  color: #166534;
}

.badge.fresh {
  background: #dbeafe;
  color: #1e40af;
}

.selected-box, .response-box {
  background: #f9f9fb;
  border: 1px solid #e2e2e8;
  padding: 12px;
  border-radius: 6px;
  min-height: 80px;
  margin-bottom: 16px;
  white-space: pre-wrap;
  color: #222;
}

.refresh-btn {
  width: 100%;
  padding: 8px 12px;
  background: #f1f5f9;
  color: #334155;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 500;
}

.refresh-btn:hover {
  background: #e2e8f0;
}
</style>
