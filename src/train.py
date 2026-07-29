import os
import pandas as pd
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer #metinleri,kelimeleri,tf-ıdf hesaplayarak sayısal matrisler dönüştürmek için
from sklearn.model_selection import train_test_split #veri setimizi egitim ve test olarak ikiye bölmek için
from sklearn.linear_model import LogisticRegression #e postanın phishing ve clean olma olasılığını hesaplayan sınıflandırma modelimiz
from sklearn.metrics import classification_report, confusion_matrix #eğitilen modelin ne kadar doğru çalıştığını , istatiksel raporu ölçmek için
from preprocess import clean_text
"""
train.py'ın tek işi: elindeki etiketli veriden (hangi mail phishing, hangi mail temiz) 
bir model üretmek ve o modeli diske kaydetmek. 
Yani bu dosya bir kere çalışır, "öğrenme" işini yapar, sonucu (phishing_model.pkl ve vectorizer.pkl) diske bırakır
ve görevi biter.
"""
# Dosya yolları
DATA_PATH = "data/phishing_email_dataset.csv" #daha düzenli olmasi için.
MODEL_DIR = "models" #2 dosya model olacağı için klasör yaptik. 

def train(): 
    print("1. Veri seti yükleniyor...")
    if not os.path.exists(DATA_PATH):
        print(f"Hata: {DATA_PATH} bulunamadı! Lütfen Kaggle CSV dosyasını bu konuma koy.")
        return

    df = pd.read_csv(DATA_PATH) #pandas dosyayı diskten okur, veri artik ramde dataframe seklinde.
    
    print(f"Toplam Veri Sayısı: {len(df)}")

    # Kolon adlarını kontrol et (text ve label olmalı)
    # Eğer kolon adları farklıysa burada düzenleme yapabilirsin
    text_col = 'text' if 'text' in df.columns else df.columns[0]
    label_col = 'label' if 'label' in df.columns else df.columns[1]

     # 'text' kolonundaki verileri temizle
    print("2. Metinler temizleniyor (Preprocessing)...")
    df['clean_text'] = df[text_col].apply(clean_text) 
    #pandasın bir sütundaki tüm satırlara belirtilen fonksiyonu sırayla uygulayan özel metodudur.
    #aslında normal for döngüsü ile de yapabilirdim ama apply okunabilirlik ve kod temizliği için kullandım.

    X = df['clean_text'] #modele girdi veriyoruz, tf-ıdf değerlerini.
    y = df[label_col] #tahmin etmeye calistigi sey. phishing mi değil mi  

    print("3. TF-IDF Özellik Çıkarımı yapılıyor...")
    vectorizer = TfidfVectorizer(max_features=5000, stop_words="english") #5000 olma sebebi en sık en önemli olanı tutmak.
    X_vec = vectorizer.fit_transform(X)

    print("4. Train / Test olarak ayrılıyor...")
    X_train, X_test, y_train, y_test = train_test_split(
        X_vec, y, test_size=0.2, random_state=42, stratify=y
    )

    print("5. Model eğitiliyor (Logistic Regression)...")
    model = LogisticRegression(max_iter=1000)
    model.fit(X_train, y_train)  #kelimelerin ağırlık atamaları yapılıyor.

    print("\n=== MODEL PERFORMANS RAPORU ===")
    y_pred = model.predict(X_test)
    print(classification_report(y_test, y_pred))

    # Modelleri kaydet
    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(model, os.path.join(MODEL_DIR, "phishing_model.pkl"))
    joblib.dump(vectorizer, os.path.join(MODEL_DIR, "vectorizer.pkl"))
    print(f"\nModel ve Vektörleştirici '{MODEL_DIR}/' klasörüne başarıyla kaydedildi!")

if __name__ == "__main__":
    train()