import os
import random
import sqlite3
import pickle
import numpy as np # Новая библиотека для математики векторов
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

IMAGES_DIR = "images"
DB_FILE = "dataset.db"
EMBEDDINGS_FILE = "embeddings.pkl"

if not os.path.exists(IMAGES_DIR):
    os.makedirs(IMAGES_DIR)

app.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")

class SwipeAction(BaseModel):
    user_id: str
    image_id: str
    action: str

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS swipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            user_id TEXT,
            image_id TEXT,
            action TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- ЗАГРУЗКА МОЗГА (Эмбеддингов) ---
image_embeddings = {}
if os.path.exists(EMBEDDINGS_FILE):
    print("Загрузка нейросетевых эмбеддингов...")
    with open(EMBEDDINGS_FILE, "rb") as f:
        image_embeddings = pickle.load(f)
else:
    print("ВНИМАНИЕ: Файл embeddings.pkl не найден. ИИ будет давать случайные рекомендации.")

def get_all_designs():
    designs = []
    for filename in os.listdir(IMAGES_DIR):
        if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            image_id = os.path.splitext(filename)[0]
            designs.append({
                "id": image_id,
                "url": f"http://127.0.0.1:8000/images/{filename}"
            })
    return designs

# Математическая функция для сравнения векторов
def cosine_similarity(v1, v2):
    if np.linalg.norm(v1) == 0 or np.linalg.norm(v2) == 0:
        return 0.0
    return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))

@app.get("/next-design")
def get_next_design(user_id: str):
    seen_image_ids = set()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT image_id FROM swipes WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    
    for row in rows:
        seen_image_ids.add(row[0])
        
    all_designs = get_all_designs()
    available_designs = [d for d in all_designs if d["id"] not in seen_image_ids]
    
    if not available_designs:
        return {"image_id": "none", "image_url": "https://placehold.co/300x400/000000/FFFFFF?text=No+More+Designs"}
        
    random_design = random.choice(available_designs)
    return {"image_id": random_design["id"], "image_url": random_design["url"]}

@app.post("/swipe")
def save_swipe(swipe: SwipeAction):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO swipes (timestamp, user_id, image_id, action) VALUES (?, ?, ?, ?)",
        (now, swipe.user_id, swipe.image_id, swipe.action)
    )
    conn.commit()
    conn.close()
    print(f"--> Saved to DB: {swipe.user_id} swiped '{swipe.action}' on '{swipe.image_id}'")
    return {"status": "success", "recorded_action": swipe.action}

@app.get("/picks")
def get_picks(user_id: str, limit: int = 5):
    # 1. Достаем историю свайпов юзера
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT image_id, action FROM swipes WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    
    seen_ids = set()
    liked_ids = []
    disliked_ids = [] # НОВОЕ: Теперь мы собираем и дизлайки
    
    for row in rows:
        img_id, action = row[0], row[1]
        seen_ids.add(img_id)
        if action == 'like':
            liked_ids.append(img_id)
        elif action == 'dislike':
            disliked_ids.append(img_id)
            
    all_designs = get_all_designs()
    unseen_designs = [d for d in all_designs if d["id"] not in seen_ids]
    
    safe_limit = min(limit, len(unseen_designs))
    if not image_embeddings or safe_limit == 0:
        return {"user_id": user_id, "message": "No picks available", "picks": []}
        
    # 2. Достаем векторы для лайков и дизлайков
    liked_vectors = [image_embeddings[img_id] for img_id in liked_ids if img_id in image_embeddings]
    disliked_vectors = [image_embeddings[img_id] for img_id in disliked_ids if img_id in image_embeddings]
    
    # Проверка на "Холодный старт"
    if not liked_vectors and not disliked_vectors:
        return {"user_id": user_id, "message": "Cold Start picks", "picks": random.sample(unseen_designs, safe_limit)}
        
    # 3. Вычисляем средние векторы (центры масс)
    # Если лайков еще нет, создаем пустой вектор из нулей (размерность MobileNetV2 = 1280)
    mean_likes = np.mean(liked_vectors, axis=0) if liked_vectors else np.zeros(1280)
    mean_dislikes = np.mean(disliked_vectors, axis=0) if disliked_vectors else np.zeros(1280)
    
    # ФИНАЛЬНЫЙ БОСС: Векторное вычитание!
    # Мы берем лайки и отнимаем от них дизлайки с весом 0.5 (штраф)
    user_profile_vector = mean_likes - (0.5 * mean_dislikes)
    
    # 4. Оцениваем все невиданные картинки
    scored_designs = []
    for design in unseen_designs:
        img_id = design["id"]
        if img_id in image_embeddings:
            sim = cosine_similarity(user_profile_vector, image_embeddings[img_id])
            scored_designs.append((sim, design))
            
    # 5. Сортируем и выдаем топ
    scored_designs.sort(key=lambda x: x[0], reverse=True)
    top_picks = [item[1] for item in scored_designs[:safe_limit]]
    
    return {
        "user_id": user_id,
        "message": "Advanced AI picks (Likes - Dislikes Penalty)",
        "picks": top_picks
    }

    # ... (весь предыдущий код остается выше) ...

# --- API ДЛЯ СТРАНИЦЫ "ПРОФИЛЬ" ---
@app.get("/profile-stats")
def get_profile_stats(user_id: str):
    """
    Возвращает статистику пользователя для страницы профиля.
    Использует SQL GROUP BY для быстрого подсчета лайков и дизлайков.
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Считаем количество каждого действия для конкретного юзера
    cursor.execute(
        "SELECT action, COUNT(*) FROM swipes WHERE user_id = ? GROUP BY action", 
        (user_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    
    # Формируем словарь со статистикой
    stats = {"like": 0, "dislike": 0}
    for row in rows:
        action_type = row[0]
        count = row[1]
        stats[action_type] = count
        
    total_swipes = stats["like"] + stats["dislike"]
    
    return {
        "user_id": user_id,
        "total_swipes": total_swipes,
        "likes": stats["like"],
        "dislikes": stats["dislike"]
    }

# --- API ДЛЯ ФУНКЦИИ СБРОСА (RESET) ---
@app.post("/reset-history")
def reset_user_history(user_id: str):
    """
    Удаляет все свайпы конкретного пользователя из базы данных.
    Это позволит начать обучение ИИ с чистого листа.
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Удаляем только строки этого пользователя
    cursor.execute("DELETE FROM swipes WHERE user_id = ?", (user_id,))
    conn.commit()
    deleted_rows = cursor.rowcount # Смотрим, сколько строк было удалено
    conn.close()
    
    print(f"--> Database Reset: Deleted {deleted_rows} swipes for user '{user_id}'")
    
    return {
        "status": "success", 
        "message": f"History cleared. Deleted {deleted_rows} records.",
        "user_id": user_id
    }

# ... (весь предыдущий код остается выше) ...

# --- API ДЛЯ СТРАНИЦЫ "ПРОФИЛЬ" ---
@app.get("/profile-stats")
def get_profile_stats(user_id: str):
    """
    Возвращает статистику пользователя для страницы профиля.
    Использует SQL GROUP BY для быстрого подсчета лайков и дизлайков.
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Считаем количество каждого действия для конкретного юзера
    cursor.execute(
        "SELECT action, COUNT(*) FROM swipes WHERE user_id = ? GROUP BY action", 
        (user_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    
    # Формируем словарь со статистикой
    stats = {"like": 0, "dislike": 0}
    for row in rows:
        action_type = row[0]
        count = row[1]
        stats[action_type] = count
        
    total_swipes = stats["like"] + stats["dislike"]
    
    return {
        "user_id": user_id,
        "total_swipes": total_swipes,
        "likes": stats["like"],
        "dislikes": stats["dislike"]
    }

# --- API ДЛЯ ФУНКЦИИ СБРОСА (RESET) ---
@app.post("/reset-history")
def reset_user_history(user_id: str):
    """
    Удаляет все свайпы конкретного пользователя из базы данных.
    Это позволит начать обучение ИИ с чистого листа.
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Удаляем только строки этого пользователя
    cursor.execute("DELETE FROM swipes WHERE user_id = ?", (user_id,))
    conn.commit()
    deleted_rows = cursor.rowcount # Смотрим, сколько строк было удалено
    conn.close()
    
    print(f"--> Database Reset: Deleted {deleted_rows} swipes for user '{user_id}'")
    
    return {
        "status": "success", 
        "message": f"History cleared. Deleted {deleted_rows} records.",
        "user_id": user_id
    }