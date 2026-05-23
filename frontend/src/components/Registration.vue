<script setup lang="ts">
import { ref } from 'vue'
import axios from 'axios'

const emit = defineEmits(['switchToLogin'])
const username = ref('') // Нове поле
const email = ref('')
const password = ref('')
const error = ref('')
const isLoading = ref(false)

const onRegister = async () => {
  error.value = ''
  isLoading.value = true
  try {
    await axios.post('http://localhost:8000/auth/register', {
      username: username.value, // Додаємо у payload
      email: email.value,
      password: password.value
    })
    alert('Акаунт успішно створено!')
    emit('switchToLogin')
  } catch (err: any) {
    // Якщо бекенд повертає масив помилок валідації (422), показуємо першу, інакше detail
    if (err.response?.status === 422) {
       error.value = "Перевірте правильність введених даних."
    } else {
       error.value = err.response?.data?.detail || 'Помилка реєстрації'
    }
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <div class="auth-box">
    <div class="auth-card">
      <h2>Реєстрація</h2>
      <form @submit.prevent="onRegister">
        <div class="form-group">
          <label>Нікнейм</label>
          <input v-model="username" type="text" required placeholder="Придумайте нікнейм" />
        </div>
        <div class="form-group">
          <label>Email</label>
          <input v-model="email" type="email" required placeholder="Введіть email" />
        </div>
        <div class="form-group">
          <label>Пароль</label>
          <input v-model="password" type="password" required placeholder="Створіть пароль" />
        </div>
        <p v-if="error" class="err-text">{{ error }}</p>
        <button type="submit" :disabled="isLoading" class="submit-btn">
          {{ isLoading ? 'Створення...' : 'Створити акаунт' }}
        </button>
      </form>
      <p class="footer-text">
        Вже маєте акаунт? <a @click="emit('switchToLogin')">Увійти</a>
      </p>
    </div>
  </div>
</template>

<style scoped>
/* Стилі залишаються без змін */
.auth-box { height: 100vh; display: flex; align-items: center; justify-content: center; }
.auth-card { background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); width: 320px; }
.form-group { margin-bottom: 15px; display: flex; flex-direction: column; }
.form-group label { font-size: 14px; margin-bottom: 5px; color: #4b5563; }
.form-group input { padding: 10px; border: 1px solid #d1d5db; border-radius: 6px; }
.submit-btn { width: 100%; padding: 10px; background: #2563eb; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: 600; }
.err-text { color: #ef4444; font-size: 13px; margin-bottom: 10px; text-align: center; }
.footer-text { text-align: center; margin-top: 15px; font-size: 14px; }
.footer-text a { color: #2563eb; cursor: pointer; text-decoration: underline; }
</style>