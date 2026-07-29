import os #işletim sistemi ile konuşmamızı sağlayan kütüphane. model dosyalarımız diskte fiziksel olarak duruyor mu değil mi öğreneceğiz.
import re #düzenli ifadeleri çağırır, güvenlik süzgeci için 
import joblib #diskte binary formatta saklanan modelleri okuyup belleğe yükleyen kütüphaneyi çağırır.
from preprocess import clean_text

# Model ve Vectorizer yolları
MODEL_PATH = "models/phishing_model.pkl" # sabit değişkenlere attık
VECTORIZER_PATH = "models/vectorizer.pkl"

class PhishingTriageAgent: 
    def __init__(self): #yapıcı metotdur. otomatik olarak çalışıcak. 
        print("🤖 Phishing Triage Agent başlatılıyor...")
        if not os.path.exists(MODEL_PATH) or not os.path.exists(VECTORIZER_PATH):
            raise FileNotFoundError("Model veya Vectorizer dosyası bulunamadı! Önce 'python src/train.py' çalıştırın.")
        
        self.model = joblib.load(MODEL_PATH) 
        self.vectorizer = joblib.load(VECTORIZER_PATH)
        print("✅ Model ve Vektörleştirici başarıyla yüklendi!\n")
        """
        bu satırlar diskteki .pkl dosyalarını okurlar , python nesnesine çevirir 
        ve sınıfın kendi değişkenlerine self.model ve self.vectorizer atayarak ram'e sabitler.
        vectorizer : metin kelimelerini sayılara çeviren tercümandır.
        model : o sayıları inceleyip risk puanı veren hakimdir.
        """

    def analyze_email(self, email_body):
        """
        Gelen e-posta gövdesini analiz eder, sınıflandırır ve gerekçelendirir.
        """
        # 1. Metni ön işlemeden geçir
        cleaned = clean_text(email_body)
        
        # 2. Vektörleştir ve Tahmin Et
        features = self.vectorizer.transform([cleaned]) 
        prediction = self.model.predict(features)[0]
        probabilities = self.model.predict_proba(features)[0]
        
        confidence = max(probabilities) * 100
        verdict = "PHISHING (Oltalama Saldırısı)" if prediction == 1 else "CLEAN (Güvenli E-Posta)"
        
        # 3. Kural Tabanlı Tehdit / Risk Tespiti (Gerekçelendirme Katmanı)
        reasons = []
        
        # URL Kontrolü
        urls = re.findall(r"http\S+|www\.\S+", email_body)
        if urls:
            reasons.append(f"🔗 Metin içerisinde {len(urls)} adet bağlantı (URL) tespit edildi.")
            
        # Aciliyet / Tehdit Sözcükleri
        urgency_words = ["urgent", "immediately", "account suspended", "verify your account", 
                         "acil", "hesabınız kısıtlandı", "şifre yenileme", "güvenlik uyarısı", "click here"]
        detected_words = [word for word in urgency_words if word in email_body.lower()]
        if detected_words:
            reasons.append(f"⚠️ Şüpheli / Aciliyet belirten ifadeler bulundu: {', '.join(detected_words)}")
            
        if not reasons and prediction == 0:
            reasons.append("✅ E-posta içeriğinde belirgin bir sosyal mühendislik veya zararlı bağlantı izine rastlanmadı.")

        # 4. Agent Çıktı Raporunu Oluştur
        report = {
            "Karar": verdict,
            "Güven Skoru": f"%{confidence:.2f}",
            "Risk Seviyesi": "YÜKSEK (CRITICAL)" if prediction == 1 else "DÜŞÜK (LOW)",
            "Gerekçeler ve Tespitler": reasons
        }
        
        return report

# --- AGENT TEST ALANI ---
if __name__ == "__main__":
    agent = PhishingTriageAgent()
    
    # Test 1: Sahte Phishing Maili Örneği
    sample_phishing = """
    URGENT: Dear customer, your account has been temporarily suspended due to suspicious activity. 
    Please click here immediately to verify your identity: http://secure-login-update.com/login
    Otherwise, your account will be closed permanently within 24 hours.
    """
    
    # Test 2: Temiz Şirket Maili Örneği
    sample_clean = """
    Hi team, just a quick reminder about our weekly sync meeting tomorrow at 10 AM. 
    Please make sure to update your project status before the meeting. Best regards, Sarah.
    """
    
    print("--------------------------------------------------")
    print("📩 TEST 1 ANALİZ EDİLİYOR (Şüpheli Mail):")
    res1 = agent.analyze_email(sample_phishing)
    for k, v in res1.items():
        print(f"  • {k}: {v}")
        
    print("\n--------------------------------------------------")
    print("📩 TEST 2 ANALİZ EDİLİYOR (Normal Mail):")
    res2 = agent.analyze_email(sample_clean)
    for k, v in res2.items():
        print(f"  • {k}: {v}")