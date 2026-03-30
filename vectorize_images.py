import os
import numpy as np
import pickle
import tensorflow as tf
from tensorflow.keras.applications.mobilenet_v2 import MobileNetV2, preprocess_input
from tensorflow.keras.preprocessing import image

# 1. Загружаем предобученную модель БЕЗ последнего слоя (classification head)
# pooling='avg' превращает выход в плоский вектор из 1280 чисел
model = MobileNetV2(weights='imagenet', include_top=False, pooling='avg')

IMAGES_DIR = "images"
EMBEDDINGS_FILE = "embeddings.pkl"

def get_embedding(img_path):
    # Загружаем и подгоняем размер под стандарт нейросети (224x224)
    img = image.load_img(img_path, target_size=(224, 224))
    x = image.img_to_array(img)
    x = np.expand_dims(x, axis=0)
    x = preprocess_input(x)
    
    # Прогоняем через нейросеть
    features = model.predict(x, verbose=0)
    return features.flatten()

def main():
    image_embeddings = {}
    
    print("Начинаю сканирование папки images...")
    
    for filename in os.listdir(IMAGES_DIR):
        if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            path = os.path.join(IMAGES_DIR, filename)
            image_id = os.path.splitext(filename)[0]
            
            print(f"Обработка: {image_id}...")
            emb = get_embedding(path)
            image_embeddings[image_id] = emb

    # Сохраняем результат в файл, чтобы не пересчитывать каждый раз
    with open(EMBEDDINGS_FILE, 'wb') as f:
        pickle.dump(image_embeddings, f)
    
    print(f"\nГотово! Обработано {len(image_embeddings)} изображений.")
    print(f"Данные сохранены в {EMBEDDINGS_FILE}")

if __name__ == "__main__":
    main()