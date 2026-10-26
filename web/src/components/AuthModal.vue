<script setup lang="ts">
import { ref } from 'vue'
import '@/assets/auth.css'

const emit = defineEmits(['success'])

const isLoginMode = ref(true)
const identifier = ref('')
const username = ref('')
const email = ref('')
const password = ref('')
const errorMsg = ref('')
const isLoading = ref(false)

const formatError = (detail: any): string => {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail.map((err) => err.msg || err.message || JSON.stringify(err)).join(', ')
  }
  if (typeof detail === 'object' && detail !== null) {
    return detail.msg || JSON.stringify(detail)
  }
  return 'Помилка валідації'
}

const handleSubmit = async () => {
  errorMsg.value = ''
  isLoading.value = true

  try {
    const url = isLoginMode.value ? '/api/auth/login' : '/api/auth/register'
    const payload = isLoginMode.value
      ? { identifier: identifier.value.trim(), password: password.value }
      : { 
          username: username.value.trim(), 
          email: email.value.trim(), 
          password: password.value 
        }

    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })

    const data = await res.json()
    if (!res.ok) {
      throw new Error(formatError(data.detail))
    }

    emit('success', data.user)
  } catch (err: any) {
    errorMsg.value = err.message || 'Сталася невідома помилка'
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <div class="login-wall-overlay">
    <div class="login-card">
      <div class="login-card-header">
        <h2>📖 Smart Reader</h2>
        <p>{{ isLoginMode ? 'Вхід у систему' : 'Створення нового акаунту' }}</p>
      </div>

      <p v-if="errorMsg" class="auth-error-badge">{{ errorMsg }}</p>

      <form class="auth-form" @submit.prevent="handleSubmit">
        <template v-if="isLoginMode">
          <div class="input-group">
            <label>Нікнейм або Email</label>
            <input
              v-model="identifier"
              type="text"
              placeholder="Введіть нікнейм або пошту"
              required
            />
          </div>
        </template>
        <template v-else>
          <div class="input-group">
            <label>Нікнейм</label>
            <input
              v-model="username"
              type="text"
              placeholder="Наприклад: alex_reader"
              minlength="3"
              maxlength="64"
              required
            />
          </div>
          <div class="input-group">
            <label>Email</label>
            <input
              v-model="email"
              type="email"
              placeholder="user@example.com"
              required
            />
          </div>
        </template>

        <div class="input-group">
          <label>Пароль</label>
          <input
            v-model="password"
            type="password"
            placeholder="Мінімум 6 символів"
            minlength="6"
            required
          />
        </div>

        <button type="submit" class="submit-btn" :disabled="isLoading">
          {{ isLoading ? 'Перевірка...' : (isLoginMode ? 'Увійти' : 'Зареєструватися') }}
        </button>
      </form>

      <div class="toggle-mode">
        <button
          type="button"
          class="link-btn"
          @click="isLoginMode = !isLoginMode; errorMsg = ''"
        >
          {{ isLoginMode ? 'Немає акаунту? Зареєструватися' : 'Вже маєте акаунт? Увійти' }}
        </button>
      </div>
    </div>
  </div>
</template>