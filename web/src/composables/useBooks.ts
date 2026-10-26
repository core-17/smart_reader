import { ref } from 'vue'

export interface BookItem {
  id: number
  title: string
  has_ocr: boolean
  ocr_status: 'not_started' | 'processing' | 'completed' | 'failed'
  ocr_error?: string | null
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

  // 1. Завантаження викликається тільки при старті або після конкретних дій
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

  // 2. Локальний таймер для конкретної книги: зупиняється, щойно OCR готовий
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
        // Запускаємо відстеження тільки для цієї книги
        pollSingleBookStatus(book.id)
      }
    } catch (err) {
      alert('Помилка виклику OCR')
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
    uploadBook,
    deleteBook,
  }
}