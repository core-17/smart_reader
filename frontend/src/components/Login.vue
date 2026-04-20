<script setup lang="ts">
import { ref } from 'vue'
import axios from 'axios'

const emit = defineEmits(['switchToRegister', 'loggedIn'])
const email = ref('')
const password = ref('')
const error = ref('')
const isLoading = ref(false)

const onLogin = async () => {
  error.value = ''
  isLoading.value = true
  
  const formData = new FormData()
  formData.append('username', email.value)
  formData.append('password', password.value)

  try {
    const response = await axios.post('http://localhost:8000/auth/login', formData)
    localStorage.setItem('auth_token', response.data.access_token)
    emit('loggedIn')
  } catch (err: any) {
    error.value = 'Невірний логін або пароль'
    console.error(err)
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <div class="auth-box">
    <div class="auth-card">
      <h2>Вхід</h2>
      <form @submit.prevent="onLogin">
        <div class="form-group">
          <label>Email</label>
          <input v-model="email" type="email" required placeholder="Введіть email" />
        </div>
        <div class="form-group">
          <label>Пароль</label>
          <input v-model="password" type="password" required placeholder="Введіть пароль" />
        </div>
        <p v-if="error" class="err-text">{{ error }}</p>
        <button type="submit" :disabled="isLoading" class="submit-btn">
          {{ isLoading ? 'Вхід...' : 'Увійти' }}
        </button>
      </form>
      <p class="footer-text">
        Немає акаунта? <a @click="emit('switchToRegister')">Створити акаунт</a>
      </p>
    </div>
  </div>
</template>

<style scoped>
.auth-box { height: 100vh; display: flex; align-items: center; justify-content: center; }
.auth-card { background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); width: 320px; }
.form-group { margin-bottom: 15px; display: flex; flex-direction: column; }
.form-group label { font-size: 14px; margin-bottom: 5px; color: #4b5563; }
.form-group input { padding: 10px; border: 1px solid #d1d5db; border-radius: 6px; outline: none; }
.form-group input:focus { border-color: #2563eb; }
.submit-btn { width: 100%; padding: 10px; background: #2563eb; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: 600; }
.submit-btn:disabled { background: #93c5fd; }
.err-text { color: #ef4444; font-size: 13px; margin-bottom: 10px; }
.footer-text { text-align: center; margin-top: 15px; font-size: 14px; }
.footer-text a { color: #2563eb; cursor: pointer; text-decoration: underline; }
</style>