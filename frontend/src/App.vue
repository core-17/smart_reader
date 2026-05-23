<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import Reader from './components/Reader.vue'
import Login from './components/Login.vue'
import Registration from './components/Registration.vue'
import axios from 'axios'

const currentView = ref<'login' | 'register' | 'reader'>('login')
const isSettingsOpen = ref(false)
const isSidebarOpen = ref(true) // Стан бічної панелі
const isUserMenuOpen = ref(false) // Стан випадаючого меню користувача
const aiProvider = ref('local')
const userEmail = ref('')
const username = ref('')

// Декодування JWT
const extractUserFromToken = (token: string) => {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    userEmail.value = payload.sub || ''
    // Якщо в токені є username, можна витягнути (залежить від бекенда)
    // Поки що використовуємо email як ідентифікатор
    username.value = userEmail.value.split('@')[0]
  } catch (e) {
    console.error("Помилка декодування токена")
  }
}

onMounted(async () => {
  const token = localStorage.getItem('auth_token')
  if (token) {
    extractUserFromToken(token)
    currentView.value = 'reader'
    fetchSettings()
  }
  window.addEventListener('click', closeMenus)
})

onUnmounted(() => {
  window.removeEventListener('click', closeMenus)
})

// Закриття меню при кліку поза ними
const closeMenus = (e: MouseEvent) => {
  const target = e.target as HTMLElement
  if (!target.closest('.user-profile-area')) {
    isUserMenuOpen.value = false
  }
}

const fetchSettings = async () => {
  try {
    const res = await axios.get('http://localhost:8000/user/settings', {
      headers: { Authorization: `Bearer ${localStorage.getItem('auth_token')}` }
    })
    aiProvider.value = res.data.ai_provider
  } catch (e) {
    console.error("Помилка налаштувань:", e)
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
    console.error("Збереження не вдалося:", e)
  }
}

const handleLogout = () => {
  localStorage.removeItem('auth_token')
  userEmail.value = ''
  currentView.value = 'login'
  isUserMenuOpen.value = false
}

const handleLoginSuccess = () => {
  const token = localStorage.getItem('auth_token')
  if (token) extractUserFromToken(token)
  currentView.value = 'reader'
  fetchSettings()
}
</script>

<template>
  <div class="app-container">
    <Login v-if="currentView === 'login'" @switchToRegister="currentView = 'register'" @loggedIn="handleLoginSuccess" />
    <Registration v-else-if="currentView === 'register'" @switchToLogin="currentView = 'login'" />

    <div v-else-if="currentView === 'reader'" class="main-layout">
      
      <header class="top-header">
        <div class="header-left">
          <button @click="isSidebarOpen = !isSidebarOpen" class="menu-toggle-btn">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="3" y1="12" x2="21" y2="12"></line><line x1="3" y1="6" x2="21" y2="6"></line><line x1="3" y1="18" x2="21" y2="18"></line></svg>
          </button>
          <span class="logo">SMART<span class="accent">READER</span></span>
        </div>

        <div class="header-right">
          <div class="user-profile-area" @click.stop="isUserMenuOpen = !isUserMenuOpen">
            <span class="username">{{ username }}</span>
            <div class="user-avatar">{{ username[0]?.toUpperCase() }}</div>
            
            <div v-if="isUserMenuOpen" class="user-dropdown">
              <div class="dropdown-info">
                <p class="email-label">{{ userEmail }}</p>
              </div>
              <hr />
              <button @click="handleLogout" class="dropdown-item logout">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path><polyline points="16 17 21 12 16 7"></polyline><line x1="21" y1="12" x2="9" y2="12"></line></svg>
                Вийти
              </button>
            </div>
          </div>
        </div>
      </header>

      <div class="workspace">
        <aside :class="['side-panel', { 'is-closed': !isSidebarOpen }]">
          <div class="spacer"></div>
          
          <div class="bottom-actions">
            <button @click="isSettingsOpen = true" class="icon-btn" title="Налаштування AI">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>
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
            <label>AI провайдер:</label>
            <select :value="aiProvider" @change="updateProvider(($event.target as HTMLSelectElement).value)" class="ai-select">
              <option value="local">Локальний (Ollama)</option>
              <option value="cloud">Хмарний (Gemini)</option>
            </select>
          </div>
          <button @click="isSettingsOpen = false" class="close-modal-btn">Закрити</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style>
/* Reset */
html, body { margin: 0; padding: 0; height: 100vh; overflow: hidden; font-family: 'Inter', sans-serif; background: #f3f4f6; }

.app-container { height: 100vh; width: 100vw; }
.main-layout { display: flex; flex-direction: column; height: 100vh; }

/* HEADER */
.top-header {
  height: 56px; background: #1e293b; color: white;
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 16px; z-index: 100;
}
.header-left { display: flex; align-items: center; gap: 15px; }
.menu-toggle-btn {
  background: transparent; border: none; color: #94a3b8;
  cursor: pointer; display: flex; align-items: center; padding: 5px;
}
.menu-toggle-btn:hover { color: white; }
.menu-toggle-btn svg { width: 24px; height: 24px; }
.logo { font-weight: 800; font-size: 18px; letter-spacing: 0.5px; }
.logo .accent { color: #3b82f6; }

/* USER PROFILE & DROPDOWN */
.header-right { position: relative; }
.user-profile-area {
  display: flex; align-items: center; gap: 10px; cursor: pointer;
  padding: 4px 8px; border-radius: 20px; transition: background 0.2s;
}
.user-profile-area:hover { background: #334155; }
.username { font-size: 14px; font-weight: 500; color: #e2e8f0; }
.user-avatar {
  width: 32px; height: 32px; background: #3b82f6; border-radius: 50%;
  display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 14px;
}
.user-dropdown {
  position: absolute; top: 45px; right: 0; width: 200px;
  background: white; border-radius: 8px; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.2);
  padding: 8px 0; z-index: 200; border: 1px solid #e2e8f0;
}
.dropdown-info { padding: 8px 16px; }
.email-label { margin: 0; font-size: 12px; color: #64748b; word-break: break-all; }
.dropdown-item {
  width: 100%; padding: 10px 16px; border: none; background: transparent;
  display: flex; align-items: center; gap: 10px; cursor: pointer;
  font-size: 14px; color: #334155; transition: background 0.2s;
}
.dropdown-item:hover { background: #f1f5f9; }
.dropdown-item.logout { color: #ef4444; }
.dropdown-item svg { width: 16px; height: 16px; }
hr { border: 0; border-top: 1px solid #f1f5f9; margin: 4px 0; }

/* WORKSPACE */
.workspace { display: flex; flex: 1; min-height: 0; }

/* SIDEBAR */
.side-panel {
  width: 60px; background: white; border-right: 1px solid #e5e7eb;
  display: flex; flex-direction: column; padding: 10px 0;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
}
.side-panel.is-closed { width: 0; border-right: none; padding: 0; }
.spacer { flex: 1; }
.bottom-actions { display: flex; justify-content: center; padding-bottom: 10px; }

/* VIEWPORT */
.reader-viewport { flex: 1; min-width: 0; background: #cbd5e1; position: relative; }

/* ICONS & MODAL */
.icon-btn {
  width: 42px; height: 42px; border-radius: 8px; border: none;
  background: transparent; color: #64748b; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
}
.icon-btn:hover { background: #f1f5f9; color: #2563eb; }
.icon-btn svg { width: 22px; height: 22px; }

.modal-overlay {
  position: fixed; inset: 0; background: rgba(0, 0, 0, 0.4);
  display: flex; align-items: center; justify-content: center; z-index: 1000;
}
.settings-modal {
  background: white; padding: 24px; border-radius: 12px; width: 280px;
}
.settings-modal h3 { margin: 0 0 16px 0; font-size: 18px; }
.ai-select { width: 100%; padding: 8px; margin-top: 5px; border-radius: 6px; border: 1px solid #cbd5e1; }
.close-modal-btn {
  width: 100%; margin-top: 20px; padding: 10px; background: #2563eb;
  color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: 600;
}
</style>