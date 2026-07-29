"""
main.py
-------
Görevi: Tüm sistemi ayağa kaldıran orkestratör.
        Bir arka plan servisi gibi çalışır:
          1. E-posta dinleyiciyi başlat
          2. Belirli aralıklarla yeni mailleri çek
          3. Her maili agent.py ile analiz et
          4. Yüksek riskli maillerde notifier'ı tetikle
          5. Dur → Bekle → Tekrar et (servis döngüsü)

Bağımlılık grafiği:
  main.py
    ├── email_listener.py  (mailleri çeker)
    ├── agent.py           (analiz eder)
    └── notifier.py        (alarm gönderir)

agent.py hiçbir şeyden haberdar değil → sadece metni alır, raporu döndürür.
Bu "separation of concerns" (sorumlulukların ayrılması) prensibinin uygulamasıdır.
"""
from dotenv import load_dotenv
import os

# .env dosyasını zorla oku (varsayılan değerlerin üzerine yaz)
load_dotenv(override=True)

import time
import logging
import os
import sys


# Neden sys.path.insert?
#   Bu dosya projenin kök dizininde (phishing-triage-agent/) duruyor.
#   Diğer modüller src/ içinde. Python import sistemi src/ klasörünü
#   otomatik görmeyebilir; bu satır onu Python yoluna ekler.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from agent import PhishingTriageAgent          # Analiz motoru
from email_listener import get_email_listener  # E-posta çekici
from notifier import get_notifier              # Alarm göndericisi

# ---------------------------------------------------------------------------
# LOGGING KURULUMU
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),                        # Terminale yaz
        logging.FileHandler("phishing_triage.log",      # Dosyaya da yaz
                            encoding="utf-8")
    ]
)
logger = logging.getLogger("Main")


# ---------------------------------------------------------------------------
# KONFİGÜRASYON
# ---------------------------------------------------------------------------
# Neden sabit değerler yerine os.getenv()?
#   Şifre, token, URL gibi hassas bilgiler kaynak koduna yazılmaz.
#   .env dosyası veya sunucu ortam değişkeni olarak tanımlanır.
#   Böylece git'e push edilse bile gizli bilgi sızmaz.
#
#   Yerel test için: .env dosyası oluştur ve içine yaz:
#       LISTENER_MODE=mock
#       NOTIFIER_CHANNEL=mock
#       POLL_INTERVAL=30

CONFIG = {
    # -----------------------------------------------------
    # E-POSTA DİNLEYİCİ
    # "mock" → Test | "imap" → Canlı
    # -----------------------------------------------------
    "listener_mode": os.getenv("LISTENER_MODE", "imap"),

    # IMAP ayarları (sadece listener_mode="imap" iken gerekli)
    "imap_host":     os.getenv("IMAP_SERVER", "imap.gmail.com"),
    "imap_port":     int(os.getenv("IMAP_PORT", "993")),
    "imap_username": os.getenv("IMAP_USER", ""),
    "imap_password": os.getenv("IMAP_PASSWORD", ""),

    # -----------------------------------------------------
    # BİLDİRİM KANALI
    # "mock" → Terminal | "teams" → MS Teams | "email" → SMTP
    # -----------------------------------------------------
    "notifier_channel": os.getenv("NOTIFIER_CHANNEL", "mock"),

    # Teams ayarları (notifier_channel="teams" iken gerekli)
    "teams_webhook_url": os.getenv("TEAMS_WEBHOOK_URL", ""),

    # SMTP ayarları (notifier_channel="email" iken gerekli)
    "smtp_host":         os.getenv("SMTP_HOST", "smtp.office365.com"),
    "smtp_port":         int(os.getenv("SMTP_PORT", "587")),
    "smtp_username":     os.getenv("SMTP_USERNAME", ""),
    "smtp_password":     os.getenv("SMTP_PASSWORD", ""),
    "smtp_sender":       os.getenv("SMTP_SENDER", ""),
    "alert_recipient":   os.getenv("ALERT_RECIPIENT", "soc@demiroren.com.tr"),

    # -----------------------------------------------------
    # DÖNGÜ AYARLARI
    # -----------------------------------------------------
    # Kaç saniyede bir posta kutusu kontrol edilsin?
    # Çok sık → IMAP sunucusu rate-limit uygulayabilir
    # Çok seyrek → Gerçek zamanlı tepki gecikmesi olur
    # Kurumsal ortamda 30–60 saniye makul.
    "poll_interval": int(os.getenv("POLL_INTERVAL", "30")),

    # Risk eşiği: Bu seviyenin üzerindeki tespitler bildirim tetikler
    # Aşağıdaki kontrolde "YÜKSEK" string'i aranır; gerekirse değiştirilebilir.
    "alert_on_risk": "YÜKSEK",

    # Tek çevrimde en fazla kaç mail işlensin?
    "max_emails_per_cycle": int(os.getenv("MAX_EMAILS_PER_CYCLE", "10")),
}


# ---------------------------------------------------------------------------
# YARDIMCI: NOTIFIER BAŞLATMA
# ---------------------------------------------------------------------------
def build_notifier(config: dict):
    """Config'e göre doğru notifier nesnesini oluşturur."""
    channel = config["notifier_channel"]

    if channel == "mock":
        return get_notifier("mock")

    elif channel == "teams":
        return get_notifier("teams", webhook_url=config["teams_webhook_url"])

    elif channel == "email":
        return get_notifier(
            "email",
            host=config["smtp_host"],
            port=config["smtp_port"],
            username=config["smtp_username"],
            password=config["smtp_password"],
            sender_email=config["smtp_sender"]
        )

    else:
        logger.warning(f"Bilinmeyen notifier kanalı '{channel}'. Mock kullanılacak.")
        return get_notifier("mock")


# ---------------------------------------------------------------------------
# YARDIMCI: LISTENER BAŞLATMA
# ---------------------------------------------------------------------------
def build_listener(config: dict):
    """Config'e göre doğru email listener nesnesini oluşturur."""
    mode = config["listener_mode"]

    if mode == "mock":
        return get_email_listener("mock")

    elif mode == "imap":
        return get_email_listener(
            "imap",
            host=config["imap_host"],
            port=config["imap_port"],
            username=config["imap_username"],
            password=config["imap_password"]
        )

    else:
        logger.warning(f"Bilinmeyen listener modu '{mode}'. Mock kullanılacak.")
        return get_email_listener("mock")


# ---------------------------------------------------------------------------
# TEMEL FONKSİYON: TEK BİR E-POSTA İŞLE
# ---------------------------------------------------------------------------
def process_single_email(email_data: dict, agent: PhishingTriageAgent,
                          notifier, config: dict) -> dict:
    """
    Tek bir e-posta için tüm pipeline'ı çalıştırır:
      1. agent.py ile analiz et
      2. Yüksek riskse notifier'ı tetikle
      3. Sonucu döndür

    Parametreler:
        email_data : email_listener'dan gelen tek mail dict'i
        agent      : Hazır PhishingTriageAgent nesnesi (kez yüklendi, tekrar kullanılıyor)
        notifier   : Hazır notifier nesnesi
        config     : Genel yapılandırma

    Dönüş: agent raporu (dict)
    """
    email_body = email_data.get("body", "")
    subject    = email_data.get("subject", "(Konu Yok)")
    sender     = email_data.get("from", "(Bilinmiyor)")

    logger.info(f"📨 Analiz ediliyor | Gönderen: {sender} | Konu: {subject[:50]}")

    # Agent analizi (agent.py hiçbir şey bilmiyor — sadece body'yi alıyor)
    report = agent.analyze_email(email_body)

    risk_level = report.get("Risk Seviyesi", "")
    decision   = report.get("Karar", "")
    confidence = report.get("Güven Skoru", "")

    logger.info(f"  → Karar: {decision} | Risk: {risk_level} | Güven: {confidence}")

    # Yüksek riskli ise bildirim gönder
    if config["alert_on_risk"] in risk_level:
        logger.warning(f"  🚨 YÜKSEK RİSK TESPİT EDİLDİ — Bildirim gönderiliyor...")

        # Notifier'a hem e-posta meta verisini hem de raporu gönderiyoruz
        # (Teams kartında "kimden geldi, konu ne" göstermek için meta lazım)
        success = notifier.send_alert(
            email_meta=email_data,
            report=report,
            recipient=config.get("alert_recipient", "")   # Email kanalı için
        )

        if success:
            logger.info("  ✅ Bildirim başarıyla gönderildi.")
        else:
            logger.error("  ❌ Bildirim gönderilemedi! Log detaylarını inceleyin.")
    else:
        logger.info(f"  ✅ Düşük risk — bildirim gerekmedi.")

    return report


# ---------------------------------------------------------------------------
# ANA SERVİS DÖNGÜSÜ
# ---------------------------------------------------------------------------
def run_service(config: dict):
    """
    Sistemin ana döngüsü. Sonsuza kadar (veya Ctrl+C'ye kadar) çalışır.

    Döngü akışı:
      BAŞLAT → Modeli Yükle → Döngüye Gir
        ├── Bağlan
        ├── Mailleri Çek
        ├── Her mail için process_single_email()
        ├── Bağlantıyı Kes
        └── poll_interval saniye bekle → Tekrar
    """
    logger.info("=" * 60)
    logger.info("🛡️  Demirören Medya — Phishing Triage Agent Servisi")
    logger.info("=" * 60)
    logger.info(f"Dinleyici Modu : {config['listener_mode'].upper()}")
    logger.info(f"Bildirim Kanalı: {config['notifier_channel'].upper()}")
    logger.info(f"Kontrol Aralığı: {config['poll_interval']} saniye")
    logger.info("=" * 60)

    # ------------------------------------------------------------------
    # AGENT'I BİR KEZ YÜKLE
    # ------------------------------------------------------------------
    # Neden döngünün dışında?
    #   joblib.load() her çağrıda modeli diskten RAM'e yükler.
    #   30 saniyede bir model yüklesek; büyük modellerde yavaşlık, gereksiz I/O.
    #   Bir kez yükle, sürekli kullan → verimli tasarım.
    try:
        agent = PhishingTriageAgent()
    except FileNotFoundError as e:
        logger.critical(f"Model yüklenemedi: {e}")
        logger.critical("Önce 'python src/train.py' çalıştırarak modeli oluşturun!")
        sys.exit(1)   # Anlamsız bir state'te çalışmak yerine dur.

    # ------------------------------------------------------------------
    # BİLDİRİCİYİ HAZIRLA
    # ------------------------------------------------------------------
    try:
        notifier = build_notifier(config)
    except ValueError as e:
        logger.critical(f"Notifier yapılandırma hatası: {e}")
        sys.exit(1)

    # ------------------------------------------------------------------
    # SERVİS DÖNGÜSÜ
    # ------------------------------------------------------------------
    logger.info("🟢 Servis çalışıyor. Durdurmak için Ctrl+C kullanın.\n")

    cycle = 0

    while True:   # Sonsuz döngü → servis mantığı
        cycle += 1
        logger.info(f"--- Çevrim #{cycle} başlıyor ---")

        # Her çevrimde yeni bir listener bağlantısı aç
        # Neden her seferinde?
        #   IMAP sunucuları uzun süreli bağlantıları timeout ile düşürür.
        #   Her döngüde taze bağlantı açmak daha sağlamlı (robust) bir tasarım.
        listener = build_listener(config)

        try:
            listener.connect()
            
            emails = listener.fetch_unread_emails(
                max_count=config["max_emails_per_cycle"]
            )

            if not emails:
                logger.info("Yeni e-posta bulunamadı.")
            else:
                logger.info(f"{len(emails)} yeni e-posta işlenecek.")

                # Her e-postayı sırayla işle
                for i, email_data in enumerate(emails, start=1):
                    logger.info(f"\n[{i}/{len(emails)}]")
                    try:
                        process_single_email(email_data, agent, notifier, config)
                    except Exception as e:
                        # Tek mail hata verse tüm döngü durmasın
                        logger.error(f"E-posta işlenirken hata (ID: {email_data.get('id', '?')}): {e}")
                        continue

        except Exception as e:
            # Bağlantı veya çekme hatası → döngüyü kır değil, uyar ve devam et
            logger.error(f"Çevrim #{cycle} sırasında hata: {e}")

        finally:
            # finally bloğu: hata olsa da olmasa da çalışır.
            # Neden? Bağlantı her koşulda kapatılmalı (resource leak önleme)
            listener.disconnect()

        logger.info(f"--- Çevrim #{cycle} tamamlandı. {config['poll_interval']}s bekleniyor ---\n")

        # Belirtilen süre kadar bekle (CPU meşgul etme, sadece uyu)
        # time.sleep() bu süre boyunca thread'i bloke eder.
        # Daha gelişmiş mimaride asyncio veya threading kullanılabilir.
        try:
            time.sleep(config["poll_interval"])
        except KeyboardInterrupt:
            # Ctrl+C sleep sırasında basılırsa da yakalanmalı
            raise


# ---------------------------------------------------------------------------
# GİRİŞ NOKTASI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    """
    if __name__ == "__main__" neden var?
        Bu dosya hem direkt çalıştırılabilir (python main.py)
        hem de başka bir modül tarafından import edilebilir.
        Import edildiğinde run_service() otomatik çalışmamalı —
        bu blok bunu önler.
        
    Ctrl+C (KeyboardInterrupt) yakalaması
        Kullanıcı servisi durdurmak istediğinde Python KeyboardInterrupt
        fırlatır. Biz bunu yakalayıp temiz çıkış mesajı veriyoruz
        (panik traceback yerine).
    """
    try:
        run_service(CONFIG)
    except KeyboardInterrupt:
        logger.info("\n🔴 Servis kullanıcı tarafından durduruldu. Görüşürüz.")
        sys.exit(0)
