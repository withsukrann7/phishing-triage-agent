# 🛡️ Phishing Mail Triage Agent & SOC Web Portal

Bu proje, gelen e-postaları yapay zeka/makine öğrenmesi modelleriyle analiz ederek **Phishing (Oltalama)** saldırılarını otonom olarak tespit eden ve sonuçları **Microsoft Defender benzeri canlı bir Web Dashboard** üzerinde sunan bir güvenlik (SOC) tahlil sistemidir.

---

## 📁 Proje Dosya Yapısı ve Görevleri

| Dosya / Klasör | Açıklama |
| :--- | :--- |
| **`app.py`** | Tarayıcıda çalışan **Streamlit Web Paneli** (Defender temalı Incidents/Olay ekranı ve analiz grafikleri). |
| **`main.py`** | Servis döngüsü. Gmail kutusundan mailleri çeker, analiz ettirir ve canlı sonuçları web paneline aktarır. |
| **`src/agent.py`** | Eğitilmiş ML modellerini kullanarak mail metinlerini analiz eden ve risk/güven skorlarını üreten ana motor. |
| **`src/preprocess.py`** | Mail metinlerini (HTML, özel karakterler, stop-words vb.) temizleyip modele hazır hale getiren ön işleme modülü. |
| **`src/email_listener.py`** | IMAP protokolü ile belirlenen e-posta kutusuna bağlanıp canlı mailleri yakalayan modül. |
| **`src/notifier.py`** | Yüksek riskli tehdit tespit edildiğinde MS Teams / Webhook kanallarına otomatik alarm kartı fırlatan bildirim modülü. |
| **`models/`** | Eğitilmiş makine öğrenmesi modellerinin (`.joblib` dosyaları) ve vektörleştiricilerin yer aldığı klasör. |
| **`.env`** | E-posta şifreleri, IMAP/SMTP sunucu bilgileri ve API webhook URL gibi hassas konfigürasyon parametreleri. |
| **`requirements.txt`** | Projenin çalışması için gerekli tüm Python kütüphanelerinin listesi. |

---

## 🚀 Hızlı Başlangıç

### 1. Kütüphaneleri Yükleyin
```bash
pip install -r requirements.txt