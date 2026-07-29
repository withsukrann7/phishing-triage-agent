"""
email_listener.py
-----------------
Görevi: Bir e-posta kutusundan okunmamış mailleri çekip
        agent.py'nin anlayacağı sözlük (dict) formatında listelemek.

İki mod vardır:
  1. MOCK MOD   → Gerçek sunucuya gerek yok. Test için sahte mailler üretir.
  2. IMAP MOD   → Gerçek kurumsal posta sunucusuna (Gmail, Exchange, vb.) SSL ile bağlanır.

Staj sürecinde MOCK mod kullanılır; yetki alındığında
sadece fetch_emails() çağrısı IMAP versiyonuyla değiştirilir.
Agent katmanına (agent.py) hiçbir dokunuş gerekmez.
"""

import imaplib      # Python standart kütüphanesi – IMAP4 protokolü
import email        # Python standart kütüphanesi – Ham MIME mesajını parse eder
import email.header # Konu başlığındaki encoding'i (UTF-8, base64 vb.) çözer
import logging      # print() yerine; log seviyesi (INFO/WARNING/ERROR) belirtilebilir
from datetime import datetime  # Zaman damgası için

# ---------------------------------------------------------------------------
# LOGGING KURULUMU
# ---------------------------------------------------------------------------
# Neden print() değil?
#   print() canlı sistemde her şeyi ekrana basar, filtreleyemezsin.
#   logging ile seviyeye göre filtre, dosyaya yaz, ağa gönder gibi esneklikler kazanırsın.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("EmailListener")


# ===========================================================================
# BÖLÜM 1 – GERÇEK IMAP BAĞLANTISI
# ===========================================================================
class IMAPEmailListener:
    """
    Gerçek bir IMAP sunucusuna bağlanır ve okunmamış e-postaları çeker.

    Kullanım:
        listener = IMAPEmailListener(
            host="imap.gmail.com",
            port=993,
            username="soc@demiroren.com.tr",
            password="APP_PASSWORD_BURAYA",
            mailbox="INBOX"
        )
        emails = listener.fetch_unread_emails()

    Dikkat:
        - Gmail için "Uygulama Şifresi" (App Password) kullanılmalı,
          normal hesap şifresi değil. (Google hesabı 2FA açıkken gerekli)
        - Exchange / Office365 için:
            host = "outlook.office365.com"
            port = 993
        - Şifreyi asla kaynak koduna gömmeyiniz → .env dosyası veya
          şirket Secret Manager kullanınız.
    """

    def __init__(self, host: str, port: int, username: str, password: str, mailbox: str = "INBOX"):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.mailbox = mailbox
        self._connection = None   # İleride imaplib.IMAP4_SSL nesnesi olacak

    # ------------------------------------------------------------------
    def connect(self):
        """Sunucuya SSL üzerinden bağlan ve kimlik doğrulaması yap."""
        try:
            logger.info(f"IMAP sunucusuna bağlanılıyor: {self.host}:{self.port}")
            # IMAP4_SSL → port 993 üzerinde TLS/SSL şifreli bağlantı açar.
            # Neden SSL? Şirkette e-posta trafiği açık (plaintext) gönderilemez,
            # şifrelemek zorunlu.
            self._connection = imaplib.IMAP4_SSL(self.host, self.port)
            self._connection.login(self.username, self.password)
            logger.info("Kimlik doğrulaması başarılı.")
        except imaplib.IMAP4.error as e:
            # IMAP protokolü hataları (yanlış şifre, sunucu reddi vb.)
            logger.error(f"IMAP bağlantı hatası: {e}")
            raise

    # ------------------------------------------------------------------
    def disconnect(self):
        """Bağlantıyı düzgün kapat. (Sunucu tarafında oturum bırakma)"""
        if self._connection:
            try:
                self._connection.logout()
                logger.info("IMAP bağlantısı kapatıldı.")
            except Exception:
                pass  # Kapatma sırasında oluşan hataları yut; zaten işimiz bitti.

    # ------------------------------------------------------------------
    def fetch_unread_emails(self, max_count: int = 10) -> list[dict]:
        """
        Seçili posta kutusundaki okunmamış e-postaları çekip liste döndürür.

        Her eleman bir dict:
        {
            "id"      : str  – IMAP UID (sunucu tarafındaki benzersiz kimlik)
            "from"    : str  – Gönderen adresi
            "subject" : str  – Konu başlığı
            "body"    : str  – Düz metin gövdesi
            "date"    : str  – Tarih damgası
        }

        max_count: En fazla kaç mail çekilsin (rate limiting ve sunucu yükü için)
        """
        emails = []

        try:
            # Posta kutusunu seç (INBOX, Junk vb.)
            # "readonly=False" → UNSEEN bayraklarını güncelleyebiliriz
            # Neden readonly değil? "SEEN" bayrağını set etmemiz için yazma yetkisi lazım.
            # Yoksa her döngüde aynı maili tekrar çekeriz.
            self._connection.select(self.mailbox, readonly=False)

            # UNSEEN (okunmamış) e-postaların UID listesini al
            # Dönüş: ("OK", [b"1 2 3 4 5"]) formatında
            status, messages = self._connection.search(None, "UNSEEN")

            if status != "OK":
                logger.warning("Posta kutusunda arama başarısız.")
                return []

            # b"1 2 3 7 9" → ["1", "2", "3", "7", "9"] → son max_count kadarını al
            mail_ids = messages[0].split()
            mail_ids = mail_ids[-max_count:]   # En yeniden başla (son gelenler)

            logger.info(f"{len(mail_ids)} adet okunmamış e-posta bulundu.")

            for mail_id in mail_ids:
                # RFC822 → Mailin tamamını (header + body) ham MIME formatında çek
                status, msg_data = self._connection.fetch(mail_id, "(RFC822)")
                if status != "OK":
                    continue

                # Ham byte verisini Python email nesnesine dönüştür
                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)

                parsed = self._parse_message(msg, mail_id.decode())
                emails.append(parsed)

        except Exception as e:
            logger.error(f"E-posta çekilirken hata: {e}")

        return emails

    # ------------------------------------------------------------------
    def _parse_message(self, msg, mail_id: str) -> dict:
        """
        Ham imaplib mesajını temiz bir dict'e çevirir.
        Bu 'private' metod (başındaki _ işareti → dışarıdan çağrılması önerilmez).
        """
        # --- Konu Başlığı ---
        # E-posta başlıkları bazen base64 veya quoted-printable encoding'de gelir.
        # decode_header() bunu çözer; make_header() Python string'ine çevirir.
        raw_subject = msg.get("Subject", "(Konu Yok)")
        subject = str(email.header.make_header(email.header.decode_header(raw_subject)))

        # --- Gönderen ---
        sender = msg.get("From", "(Bilinmiyor)")

        # --- Tarih ---
        date_str = msg.get("Date", str(datetime.now()))

        # --- Gövde (Body) ---
        body = ""
        if msg.is_multipart():
            # Multipart → HTML + plain text + ekler gibi birden fazla parça var
            # Biz sadece text/plain parçasını istiyoruz
            for part in msg.walk():
                content_type = part.get_content_type()
                disposition = str(part.get("Content-Disposition", ""))

                # Ekler (attachment) değil, gövde metnini iste
                if content_type == "text/plain" and "attachment" not in disposition:
                    charset = part.get_content_charset() or "utf-8"
                    body = part.get_payload(decode=True).decode(charset, errors="replace")
                    break
        else:
            # Tek parçalı mesaj
            charset = msg.get_content_charset() or "utf-8"
            body = msg.get_payload(decode=True).decode(charset, errors="replace")

        return {
            "id": mail_id,
            "from": sender,
            "subject": subject,
            "body": body,
            "date": date_str
        }


# ===========================================================================
# BÖLÜM 2 – MOCK (SAHTE) E-POSTA ÜRETİCİ
# ===========================================================================
# Neden Mock?
#   Gerçek IMAP yetkisi olmadan sistemi uçtan uca test edebilmek için.
#   Mock, gerçek sınıfla AYNI arayüzü (fetch_unread_emails → list[dict]) döndürür.
#   Bu sayede main.py hangi kaynaktan geldiğini umursamaz; sadece listeye bakar.
#   Bu tasarım prensibine "Duck Typing" veya daha resmi adıyla "Dependency Injection" denir.

MOCK_EMAILS = [
    {
        "id": "mock-001",
        "from": "security-alert@paypa1.com",       # Dikkat: 'l' yerine '1' (typosquatting)
        "subject": "URGENT: Your account has been suspended",
        "body": (
            "Dear valued customer,\n\n"
            "Your PayPal account has been temporarily suspended due to suspicious activity.\n"
            "Please click here immediately to verify your identity: "
            "http://secure-paypal-login.xyz/verify\n\n"
            "Failure to do so will result in permanent account closure within 24 hours.\n\n"
            "PayPal Security Team"
        ),
        "date": "2025-07-28 09:14:00"
    },
    {
        "id": "mock-002",
        "from": "sarah.johnson@demiroren.com.tr",
        "subject": "Haftalık Senkronizasyon Toplantısı Hatırlatması",
        "body": (
            "Merhaba ekip,\n\n"
            "Yarın saat 10:00'daki haftalık senkronizasyon toplantımızı hatırlatmak istedim.\n"
            "Lütfen toplantı öncesinde proje durumunuzu güncelleyiniz.\n\n"
            "İyi çalışmalar,\nSarah"
        ),
        "date": "2025-07-28 08:45:00"
    },
    {
        "id": "mock-003",
        "from": "it-support@micros0ft-helpdesk.net",   # Sahte domain
        "subject": "Action Required: Verify your Microsoft 365 account",
        "body": (
            "Dear User,\n\n"
            "We have detected unusual sign-in activity on your Microsoft 365 account.\n"
            "To secure your account, please verify your credentials immediately:\n"
            "www.microsoft-365-verify.net/login\n\n"
            "If you do not verify within 12 hours, your account will be locked.\n\n"
            "Microsoft IT Support"
        ),
        "date": "2025-07-28 11:02:00"
    },
    {
        "id": "mock-004",
        "from": "hr@demiroren.com.tr",
        "subject": "Temmuz Ayı Bordro Bildirimi",
        "body": (
            "Sayın Çalışanımız,\n\n"
            "Temmuz 2025 dönemi maaşınız hesabınıza yatırılmıştır.\n"
            "Detaylar için İK portalımıza giriş yapabilirsiniz.\n\n"
            "Saygılarımızla,\nDemirören Medya İnsan Kaynakları"
        ),
        "date": "2025-07-28 12:00:00"
    },
]


class MockEmailListener:
    """
    Gerçek IMAP bağlantısı olmadan test için sahte e-postalar döndürür.
    IMAPEmailListener ile aynı arayüzü paylaşır → main.py değişmez.
    """

    def __init__(self):
        logger.info("MockEmailListener başlatıldı (Test Modu).")

    def connect(self):
        """Mock: Bağlantı simülasyonu."""
        logger.info("[MOCK] E-posta sunucusuna 'bağlanıldı' (simülasyon).")

    def disconnect(self):
        """Mock: Bağlantı kesme simülasyonu."""
        logger.info("[MOCK] E-posta sunucusu bağlantısı 'kesildi' (simülasyon).")

    def fetch_unread_emails(self, max_count: int = 10) -> list[dict]:
        """
        Sabit MOCK_EMAILS listesini döndürür.
        Gerçek sistemde bu liste her 30 saniyede yeni e-postalar içerebilirdi.
        """
        logger.info(f"[MOCK] {len(MOCK_EMAILS)} adet simüle e-posta döndürülüyor.")
        return MOCK_EMAILS[:max_count]


# ===========================================================================
# BÖLÜM 3 – FACTORY FONKSİYONU
# ===========================================================================
def get_email_listener(mode: str = "mock", **kwargs):
    """
    Hangi dinleyiciyi kullanacağını belirleyen fabrika fonksiyonu.

    Parametreler:
        mode    : "mock" → MockEmailListener
                  "imap" → IMAPEmailListener (kwargs ile bağlantı bilgileri verilmeli)
        **kwargs: IMAPEmailListener için host, port, username, password

    Kullanım:
        # Test ortamı:
        listener = get_email_listener("mock")

        # Canlı ortam:
        listener = get_email_listener(
            "imap",
            host="outlook.office365.com",
            port=993,
            username="soc@demiroren.com.tr",
            password=os.getenv("EMAIL_PASSWORD")
        )
    """
    if mode == "mock":
        return MockEmailListener()
    elif mode == "imap":
        required = ["host", "port", "username", "password"]
        for key in required:
            if key not in kwargs:
                raise ValueError(f"IMAP modu için '{key}' parametresi zorunlu.")
        return IMAPEmailListener(**kwargs)
    else:
        raise ValueError(f"Geçersiz mod: '{mode}'. 'mock' veya 'imap' kullanınız.")
