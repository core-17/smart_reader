from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware  # <--- Додаємо імпорт
import uvicorn

from services.local_api import DictionaryPromptPayload, LocalAPIService
from services.cloud_api import CloudAPIService

app = FastAPI(
    title="Smart Reader API", 
    version="0.1.0",
    description="Backend-архітектура для обробки текстового контексту через ШІ"
)

# --- Налаштування CORS (Cross-Origin Resource Sharing) ---
# Це дозволить браузеру успішно проходити перевірку OPTIONS
app.add_middleware(
    CORSMiddleware,
    # Вкажіть URL вашого фронтенду (Vite зазвичай використовує 5173)
    # Для розробки можна використати ["*"], щоб дозволити з будь-якого порту
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"], 
    allow_credentials=True,
    allow_methods=["*"],  # Дозволяє всі методи: GET, POST, OPTIONS тощо
    allow_headers=["*"],  # Дозволяє будь-які заголовки (включаючи Content-Type)
)

local_ai_service = LocalAPIService()
cloud_ai_service = CloudAPIService()

@app.get("/health", tags=["System"])
async def health_check():
    return {"status": "ok", "message": "Backend is running flawlessly"}

@app.post("/ai/local/dictionary", tags=["AI Integration"])
async def local_dictionary_explain(payload: DictionaryPromptPayload):
    try:
        return await local_ai_service.explain_word(payload)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Внутрішня помилка сервера: {str(exc)}") from exc

@app.post("/ai/cloud/dictionary", tags=["AI Integration"])
async def cloud_dictionary_explain(payload: DictionaryPromptPayload):
    try:
        return await cloud_ai_service.explain_word(payload)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Внутрішня помилка сервера: {str(exc)}") from exc

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)