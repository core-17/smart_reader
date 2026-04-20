<script setup lang="ts">
import { ref, onMounted } from 'vue'
import Reader from './components/Reader.vue'
import Login from './components/Login.vue'
import Registration from './components/Registration.vue'

// Встановлюємо 'login' першим екраном
const currentView = ref<'login' | 'register' | 'reader'>('login')

onMounted(() => {
  const token = localStorage.getItem('auth_token')
  if (token) {
    currentView.value = 'reader'
  }
})

const handleLogout = () => {
  localStorage.removeItem('auth_token')
  currentView.value = 'login'
}
</script>

<template>
  <div class="app-container">
    <Login 
      v-if="currentView === 'login'" 
      @switchToRegister="currentView = 'register'"
      @loggedIn="currentView = 'reader'"
    />

    <Registration 
      v-else-if="currentView === 'register'" 
      @switchToLogin="currentView = 'login'"
    />

    <div v-else-if="currentView === 'reader'" class="reader-wrapper">
      <nav class="nav-bar">
        <span class="logo">Smart Reader</span>
        <button @click="handleLogout" class="logout-btn">Вийти</button>
      </nav>
      <Reader />
    </div>
  </div>
</template>

<style>
/* Базові стилі для всього додатку */
body { margin: 0; font-family: 'Inter', sans-serif; background: #f3f4f6; }
.app-container { min-height: 100vh; display: flex; flex-direction: column; }
.nav-bar { background: white; padding: 10px 20px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #e5e7eb; }
.logo { font-weight: bold; color: #2563eb; }
.logout-btn { background: #ef4444; color: white; border: none; padding: 6px 12px; border-radius: 6px; cursor: pointer; }
</style>