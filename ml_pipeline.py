import sqlite3
import pandas as pd

DB_FILE = "dataset.db"

def load_and_prepare_data():
    # 1. Подключаемся к базе данных
    conn = sqlite3.connect(DB_FILE)
    
    # 2. Выгружаем всю таблицу в Pandas DataFrame одним мощным SQL-запросом
    df = pd.read_sql_query("SELECT user_id, image_id, action FROM swipes", conn)
    conn.close()
    
    if df.empty:
        print("База данных пока пуста!")
        return
        
    print("--- Сырые данные (Первые 5 строк) ---")
    print(df.head(), "\n")
    
    # 3. Превращаем текстовые 'like'/'dislike' в числа для нейросети
    # like = 1, dislike = 0
    df['score'] = df['action'].map({'like': 1, 'dislike': 0})
    
    # 4. Строим сводную таблицу (User-Item Matrix)
    # Если юзер лайкнул картинку несколько раз, берем максимальную оценку
    user_item_matrix = df.pivot_table(
        index='user_id', 
        columns='image_id', 
        values='score', 
        aggfunc='max'
    ).fillna(0) # Заполняем нулями те картинки, которые юзер еще не видел
    
    print("--- Матрица предпочтений (Готова для TensorFlow) ---")
    print(user_item_matrix)

# Запускаем скрипт
if __name__ == "__main__":
    load_and_prepare_data()