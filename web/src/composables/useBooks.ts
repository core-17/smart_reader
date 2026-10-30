import { ref } from 'vue'

export interface BookItem {
  id: number
  title: string
  has_ocr: boolean
  ocr_status: 'not_started' | 'processing' | 'completed' | 'failed'
  ocr_error?: string | null
  has_rag: boolean
  rag_status: 'not_indexed' | 'indexing' | 'completed' | 'failed'
  rag_progress: number
  rag_error?: string | null
  is_public: boolean
  user_id: number | null
  is_mine: boolean
}

export function useBooks(getUserId: () => number | null) {
  const books = ref<BookItem[]>([])
  const activeBook = ref<BookItem | null>(null)
  const selectedVersion = ref<'raw' | 'ocr'>('raw')
  const pdfSourceUrl = ref<string | null>(null)
  const isUploading = ref(false)

  const fetchBooks = async () => {
    try {
      const uid = getUserId()
      const url = uid ? `/api/books?user_id=${uid}` : '/api/books'
      const res = await fetch(url)
      if (res.ok) {
        books.value = await res.json()
        if (activeBook.value) {
          const found = books.value.find((b) => b.id === activeBook.value?.id)
          if (found) activeBook.value = found
        }
      }
    } catch (err) {
      console.error('Не вдалося завантажити список книг:', err)
    }
  }

  const selectBook = (book: BookItem) => {
    activeBook.value = book
    selectedVersion.value = book.has_ocr ? 'ocr' : 'raw'
    loadPdf()
  }

  const toggleVersion = (ver: 'raw' | 'ocr') => {
    selectedVersion.value = ver
    loadPdf()
  }

  const loadPdf = () => {
    if (!activeBook.value) {
      pdfSourceUrl.value = null
      return
    }
    pdfSourceUrl.value = `/api/books/${activeBook.value.id}/pdf?version=${selectedVersion.value}&t=${Date.now()}`
  }

  const pollSingleBookStatus = (bookId: number) => {
    const timer = setInterval(async () => {
      try {
        const res = await fetch(`/api/books/${bookId}/status`)
        if (!res.ok) {
          clearInterval(timer)
          return
        }
        const data = await res.json()
        const target = books.value.find((b) => b.id === bookId)
        if (target) {
          target.ocr_status = data.ocr_status
          target.has_ocr = data.has_ocr
          target.ocr_error = data.ocr_error
        }
        if (activeBook.value?.id === bookId) {
          activeBook.value.ocr_status = data.ocr_status
          activeBook.value.has_ocr = data.has_ocr
          activeBook.value.ocr_error = data.ocr_error
        }
        if (data.ocr_status === 'completed' || data.ocr_status === 'failed') {
          clearInterval(timer)
          if (activeBook.value?.id === bookId && data.ocr_status === 'completed') {
            selectedVersion.value = 'ocr'
            loadPdf()
          }
        }
      } catch {
        clearInterval(timer)
      }
    }, 3000)
  }

  const pollRagStatus = (bookId: number) => {
    const timer = setInterval(async () => {
      try {
        const res = await fetch(`/api/books/${bookId}/rag/status`)
        if (!res.ok) {
          clearInterval(timer)
          return
        }
        const data = await res.json()
        const target = books.value.find((b) => b.id === bookId)
        if (target) {
          target.rag_status = data.rag_status
          target.rag_progress = data.rag_progress
          target.has_rag = data.has_rag
          target.rag_error = data.rag_error
        }
        if (activeBook.value?.id === bookId) {
          activeBook.value.rag_status = data.rag_status
          activeBook.value.rag_progress = data.rag_progress
          activeBook.value.has_rag = data.has_rag
          activeBook.value.rag_error = data.rag_error
        }
        if (data.rag_status === 'completed' || data.rag_status === 'failed') {
          clearInterval(timer)
        }
      } catch {
        clearInterval(timer)
      }
    }, 1500)
  }

  const triggerOcr = async (book: BookItem, lang: string) => {
    const formData = new FormData()
    formData.append('lang', lang)

    try {
      const res = await fetch(`/api/books/${book.id}/ocr`, {
        method: 'POST',
        body: formData,
      })
      if (res.ok) {
        book.ocr_status = 'processing'
        pollSingleBookStatus(book.id)
      }
    } catch {
      alert('Помилка виклику OCR')
    }
  }

  const triggerRagIndex = async (book: BookItem) => {
    try {
      const res = await fetch(`/api/books/${book.id}/rag/index`, {
        method: 'POST',
      })
      if (res.ok) {
        book.rag_status = 'indexing'
        book.rag_progress = 5
        pollRagStatus(book.id)
      } else {
        const err = await res.json()
        alert(err.detail || 'Не вдалося запустити індексацію RAG')
      }
    } catch {
      alert('Помилка запуску RAG-індексації')
    }
  }

  const uploadBook = async (file: File, isPublic: boolean) => {
    isUploading.value = true
    const formData = new FormData()
    formData.append('file', file)
    formData.append('is_public', String(isPublic))
    const uid = getUserId()
    if (uid) formData.append('user_id', String(uid))

    try {
      const res = await fetch('/api/books/upload', {
        method: 'POST',
        body: formData,
      })
      if (res.ok) {
        const data = await res.json()
        await fetchBooks()
        const created = books.value.find((b) => b.id === data.book.id)
        if (created) selectBook(created)
      }
    } catch {
      alert('Не вдалося завантажити PDF')
    } finally {
      isUploading.value = false
    }
  }

  const deleteBook = async (id: number) => {
    if (!confirm('Видалити цю книгу?')) return
    const res = await fetch(`/api/books/${id}`, { method: 'DELETE' })
    if (res.ok) {
      if (activeBook.value?.id === id) {
        activeBook.value = null
        pdfSourceUrl.value = null
      }
      await fetchBooks()
    }
  }

  return {
    books,
    activeBook,
    selectedVersion,
    pdfSourceUrl,
    isUploading,
    fetchBooks,
    selectBook,
    toggleVersion,
    triggerOcr,
    triggerRagIndex,
    uploadBook,
    deleteBook,
  }
}