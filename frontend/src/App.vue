<script setup lang="ts">
import { ref, onMounted } from 'vue'
import Reader from './components/Reader.vue'
import Login from './components/Login.vue'
import Registration from './components/Registration.vue'
import axios from 'axios'

<<<<<<< HEAD
// Set 'login' as the initial screen
=======
>>>>>>> a90816d (update backund and fix ui issues, also remove cloud api and add new model for local ai)
const currentView = ref<'login' | 'register' | 'reader'>('login')
const isSettingsOpen = ref(false)
const aiProvider = ref('local')
const userEmail = ref('user@example.com') // Можна динамічно брати з токена/БД

onMounted(async () => {
  const token = localStorage.getItem('auth_token')
  if (token) {
    currentView.value = 'reader'
    fetchSettings()
  }
})

const fetchSettings = async () => {
  try {
    const res = await axios.get('http://localhost:8000/user/settings', {
      headers: { Authorization: `Bearer ${localStorage.getItem('auth_token')}` }
    })
    aiProvider.value = res.data.ai_provider
  } catch (e) {
    console.error("Помилка завантаження налаштувань ШІ:", e)
  }
}

const updateProvider = async (provider: string) => {
  aiProvider.value = provider
  try {
    await axios.put('http://localhost:8000/user/settings', 
      { ai_provider: provider },
      { headers: { Authorization: `Bearer ${localStorage.getItem('auth_token')}` } }
    )
  } catch (e) {
    console.error("Не вдалося зберегти налаштування:", e)
  }
}

const handleLogout = () => {
  localStorage.removeItem('auth_token')
  currentView.value = 'login'
}

const handleLoginSuccess = () => {
  currentView.value = 'reader'
  fetchSettings()
}
</script>

<template>
  <div class="app-container">
    <Login 
      v-if="currentView === 'login'" 
      @switchToRegister="currentView = 'register'"
      @loggedIn="handleLoginSuccess"
    />

    <Registration 
      v-else-if="currentView === 'register'" 
      @switchToLogin="currentView = 'login'"
    />

<<<<<<< HEAD
    <div v-else-if="currentView === 'reader'" class="reader-wrapper">
      <nav class="nav-bar">
        <span class="logo">Smart Reader</span>
        <button @click="handleLogout" class="logout-btn">Log Out</button>
      </nav>
      <Reader />
=======
    <div v-else-if="currentView === 'reader'" class="main-layout">
      <header class="top-header">
        <span class="logo">SMART<span class="accent">READER</span></span>
        <span class="user-email">{{ userEmail }}</span>
      </header>

      <div class="workspace">
        <aside class="side-panel">
          <div class="top-actions">
            <button @click="isSettingsOpen = true" class="icon-btn" title="Налаштування AI">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="3"></circle>
                <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
              </svg>
            </button>
          </div>
          
          <div class="bottom-actions">
            <button @click="handleLogout" class="icon-btn logout" title="Вийти з аккаунта">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
                <polyline points="16 17 21 12 16 7"></polyline>
                <line x1="21" y1="12" x2="9" y2="12"></line>
              </svg>
            </button>
          </div>
        </aside>

        <main class="reader-viewport">
          <Reader />
        </main>
      </div>

      <div v-if="isSettingsOpen" class="modal-overlay" @click.self="isSettingsOpen = false">
        <div class="settings-modal">
          <h3>Налаштування системи</h3>
          <div class="form-group">
            <label>Оберіть AI провайдера:</label>
            <select :value="aiProvider" @change="updateProvider(($event.target as HTMLSelectElement).value)" class="ai-select">
              <option value="local">Локальний ШІ (Ollama / Llama 3.1)</option>
              <option value="cloud">Хмарний ШІ (Google Gemini)</option>
            </select>
          </div>
          <button @click="isSettingsOpen = false" class="close-modal-btn">Зберегти налаштування</button>
        </div>
      </div>
>>>>>>> a90816d (update backund and fix ui issues, also remove cloud api and add new model for local ai)
    </div>
  </div>
</template>

<style>
<<<<<<< HEAD
/* Base styles for the whole app */
body { margin: 0; font-family: 'Inter', sans-serif; background: #f3f4f6; }
.app-container { min-height: 100vh; display: flex; flex-direction: column; }
.nav-bar { background: white; padding: 10px 20px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #e5e7eb; }
.logo { font-weight: bold; color: #2563eb; }
.logout-btn { background: #ef4444; color: white; border: none; padding: 6px 12px; border-radius: 6px; cursor: pointer; }
=======
/* Глобальне скидання стилів для запобігання скролу вікна */
html, body {
  margin: 0;
  padding: 0;
  height: 100vh;
  width: 100vw;
  overflow: hidden;
  font-family: 'Inter', sans-serif;
  background: #f3f4f6;
}

.app-container {
  width: 100vw;
  height: 100vh;
  overflow: hidden;
}

/* Наша головна сітка додатку */
/* Наша головна сітка додатку */
.main-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  width: 100%; /* Замість 100vw, щоб уникнути конфліктів зі скролбарами */
}

/* Хедер */
.top-header {
  height: 60px;
  background: #1e293b;
  color: white;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  box-sizing: border-box;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  z-index: 10;
}
.logo { font-weight: 800; font-size: 20px; letter-spacing: 1px; color: #ffffff; }
.logo .accent { color: #3b82f6; }
.user-email { font-size: 14px; color: #94a3b8; }

/* Нижня зона під хедером */
.workspace {
  display: flex;
  flex: 1; /* Автоматично забирає всю висоту під хедером */
  min-height: 0; /* КРИТИЧНО ВАЖЛИВО: дозволяє контейнеру стискатися по вертикалі */
  width: 100%;
}
/* Сайдбар з іконками */
.side-panel {
  width: 60px;
  background: #ffffff;
  border-right: 1px solid #e5e7eb;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  align-items: center;
  padding: 15px 0;
  box-sizing: border-box;
  z-index: 5;
}

/* Сама область рідера */
.reader-viewport {
  flex: 1; /* Забирає весь залишок ширини після бокової панелі */
  min-width: 0; /* КРИТИЧНО ВАЖЛИВО: дозволяє контейнеру стискатися по горизонталі */
  height: 100%;
  background: #cbd5e1;
  position: relative;
}
/* Кнопки-іконки */
.icon-btn {
  width: 42px;
  height: 42px;
  border-radius: 8px;
  border: none;
  background: transparent;
  color: #64748b;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}
.icon-btn:hover { background: #f1f5f9; color: #2563eb; }
.icon-btn svg { width: 22px; height: 22px; }
.icon-btn.logout:hover { color: #ef4444; background: #fee2e2; }

/* Модальне вікно */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 99999;
}
.settings-modal {
  background: white;
  padding: 25px;
  border-radius: 12px;
  width: 320px;
  box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1);
}
.settings-modal h3 { margin-top: 0; color: #1e293b; margin-bottom: 20px; }
.ai-select {
  width: 100%;
  padding: 10px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  background: white;
  outline: none;
  font-size: 14px;
}
.close-modal-btn {
  width: 100%;
  padding: 10px;
  background: #2563eb;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 600;
  margin-top: 20px;
}
.close-modal-btn:hover { background: #1d4ed8; }
>>>>>>> a90816d (update backund and fix ui issues, also remove cloud api and add new model for local ai)
</style>