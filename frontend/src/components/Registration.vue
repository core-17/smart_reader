<script setup lang="ts">
import { ref } from 'vue'
import axios from 'axios'

const emit = defineEmits(['switchToLogin'])
const username = ref('') // New field
const email = ref('')
const password = ref('')
const error = ref('')
const isLoading = ref(false)

const onRegister = async () => {
  error.value = ''
  isLoading.value = true
  try {
    await axios.post(`${API_URL}/auth/register`, {
      username: username.value, // Include username in payload
      email: email.value,
      password: password.value
    })
    alert('Account successfully created!')
    emit('switchToLogin')
  } catch (err: any) {
     // If backend returns validation errors (422), show a generic hint or detail
     if (err.response?.status === 422) {
       error.value = "Please check the provided data."
     } else {
       error.value = err.response?.data?.detail || 'Registration error'
     }
  } finally {
    isLoading.value = false
  }
}
import { API_URL } from '../config'

</script>

<template>
  <div class="auth-box">
    <div class="auth-card">
      <h2>Register</h2>
      <form @submit.prevent="onRegister">
        <div class="form-group">
          <label>Username</label>
          <input v-model="username" type="text" required placeholder="Choose a username" />
        </div>
        <div class="form-group">
          <label>Email</label>
          <input v-model="email" type="email" required placeholder="Enter your email" />
        </div>
        <div class="form-group">
          <label>Password</label>
          <input v-model="password" type="password" required placeholder="Create a password" />
        </div>
        <p v-if="error" class="err-text">{{ error }}</p>
          <button type="submit" :disabled="isLoading" class="submit-btn">
          {{ isLoading ? 'Creating...' : 'Create account' }}
        </button>
      </form>
      <p class="footer-text">
        Already have an account? <a @click="emit('switchToLogin')">Sign in</a>
      </p>
    </div>
  </div>
</template>

<style scoped>
/* Styles unchanged */
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