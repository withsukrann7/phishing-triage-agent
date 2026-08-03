# 🛡️ Phishing Mail Triage Agent & SOC Web Portal

Bu proje, gelen e-postaları yapay zeka/makine öğrenmesi modelleriyle analiz ederek **Phishing (Oltalama)** saldırılarını otonom olarak tespit eden ve sonuçları **Microsoft Defender benzeri canlı bir Web Dashboard** üzerinde sunan bir güvenlik (SOC) tahlil sistemidir.

---

## 📁 Proje Dosya Yapısı ve Görevleri

| Dosya / Klasör | Açıklama |
| :--- | :--- |
| **`app.py`** | Tarayıcıda çalışan **Streamlit Web Paneli** (Defender temalı Incidents/Olay ekranı ve analiz grafikleri). |
| **`main.py`** | Servis döngüsü. Gmail kutusundan mailleri çeker, analiz ettirir ve canlı sonuçları web paneline aktarır. |
| **`src/agent.py`** | Eğitilmiş ML modellerini kullanarak mail metinlerini analiz eden ve risk/güven skorlarını üreten ana motor. |
| **`src/preprocess.py`** | Mail metinlerini (HTML, özel karakterler vb.) temizleyip modele hazır hale getiren ön işleme modülü. |
| **`src/email_listener.py`** | IMAP protokolü ile belirlenen e-posta kutusuna bağlanıp canlı mailleri yakalayan modül. |
| **`src/notifier.py`** | Yüksek riskli tehdit tespit edildiğinde bildirim fırlatan modül. |
| **`models/`** | Eğitilmiş makine öğrenmesi modellerinin (`.joblib` dosyaları) yer aldığı klasör. |
| **`.env`** | E-posta şifreleri ve sunucu konfigürasyon parametreleri. |
| **`requirements.txt`** | Projenin çalışması için gerekli tüm Python kütüphanelerinin listesi. |

---

## 🚀 Projeyi Çalıştırma 

### 1. Kütüphaneleri Yükleyin
`pip install -r requirements.txt`

### 2. Arka Plan Dinleyicisini Başlatın (Mail Çekici)
`python main.py`

### 3. Web Panelini Açın (SOC Portal)
`streamlit run app.py`

> Web Paneli varsayılan olarak `http://localhost:8501` adresinde açılır.