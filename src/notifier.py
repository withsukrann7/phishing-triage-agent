"""
notifier.py
-----------
Görevi: agent.py'nin ürettiği raporu alıp, risk yüksekse
        ilgili ekiplere bildirim göndermek.

İki kanal desteklenir:
  1. Microsoft Teams Webhook  → Kurumsal anlık bildirim kartı
  2. SMTP E-Posta             → Standart e-posta bildirimi

Her iki kanal da ayrı ayrı veya birlikte kullanılabilir.
Hangi kanalın aktif olduğu config (yapılandırma) ile belirlenir.
"""

import json         # Teams webhook payload'ı JSON formatında gönderilir
import smtplib      # Python standart SMTP kütüphanesi (e-posta göndermek için)
import logging
import urllib.request  # HTTP POST için; requests kütüphanesi yoksa standart alternatif
import urllib.error
from email.mime.text import MIMEText           # Düz metin e-posta gövdesi
from email.mime.multipart import MIMEMultipart # HTML + düz metin birlikte
from datetime import datetime

logger = logging.getLogger("Notifier")


# ===========================================================================
# BÖLÜM 1 – MICROSOFT TEAMS WEBHOOK BİLDİRİCİ
# ===========================================================================
class TeamsNotifier:
    """
    Microsoft Teams kanalına Adaptive Card formatında bildirim gönderir.

    Teams Webhook Nasıl Alınır?
      1. Teams'te ilgili kanala git (örn: #bilgi-guvenligi-alarmlari)
      2. Kanal adına sağ tıkla → "Connectors" → "Incoming Webhook"
      3. Oluşturulan URL'yi bu sınıfa ver.

    Neden Adaptive Card?
      Düz metin yerine başlık, renkli badge, buton gibi zengin içerik sunar.
      SOC analistinin ekranda hızlıca durumu görmesi için kritik.
    """

    def __init__(self, webhook_url: str):
        """
        webhook_url: Teams kanalından alınan Incoming Webhook adresi.
                     Örn: "https://demiroren.webhook.office.com/webhookb2/..."
                     Bu URL'yi .env dosyasında tutun, kaynak koduna YAZMAYIN.
        """
        if not webhook_url:
            raise ValueError("Teams webhook URL boş olamaz.")
        self.webhook_url = webhook_url

    # ------------------------------------------------------------------
    def send_alert(self, email_meta: dict, report: dict) -> bool:
        """
        Phishing tespiti yapılan e-posta için Teams'e bildirim kartı gönder.

        Parametreler:
            email_meta : {"from", "subject", "date", "id"} → E-posta kimlik bilgileri
            report     : agent.py'nin ürettiği analiz raporu dict'i

        Dönüş:
            True  → Gönderim başarılı
            False → Hata oluştu (loglara bak)
        """
        # Risk seviyesine göre kart rengi belirle
        # Teams'te themeColor hex değeri:
        #   Kırmızı (d13438) → Kritik  |  Sarı (f3a712) → Orta  |  Yeşil (107c10) → Düşük
        risk = report.get("Risk Seviyesi", "")
        if "YÜKSEK" in risk or "CRITICAL" in risk:
            theme_color = "d13438"   # Kırmızı
            severity_label = "🚨 KRİTİK"
        elif "ORTA" in risk or "MEDIUM" in risk:
            theme_color = "f3a712"   # Turuncu/Sarı
            severity_label = "⚠️ ORTA"
        else:
            theme_color = "107c10"   # Yeşil
            severity_label = "✅ DÜŞÜK"

        # Gerekçeleri düz metin listesine çevir
        reasons_text = "\n".join(
            f"• {r}" for r in report.get("Gerekçeler ve Tespitler", [])
        )

        # ------------------------------------------------------------------
        # Teams Adaptive Card payload'ı
        # MessageCard formatı → eski ama geniş uyumlu, Office 365 Connectors ile çalışır.
        # Daha modern alternatif: Adaptive Card v2 (ancak bazı kurumsal tenant'larda kısıtlı)
        # ------------------------------------------------------------------
        payload = {
            "@type": "MessageCard",
            "@context": "https://schema.org/extensions",
            "themeColor": theme_color,
            "summary": "Phishing Triage Agent Alarmı",
            "sections": [
                {
                    "activityTitle": f"**Phishing Triage Agent** | {severity_label}",
                    "activitySubtitle": f"Analiz Zamanı: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}",
                    "activityImage": "https://img.icons8.com/color/48/shield.png",
                    "facts": [
                        {"name": "📧 Gönderen",    "value": email_meta.get("from", "Bilinmiyor")},
                        {"name": "📌 Konu",        "value": email_meta.get("subject", "Yok")},
                        {"name": "⚖️ Karar",       "value": report.get("Karar", "-")},
                        {"name": "🎯 Güven Skoru", "value": report.get("Güven Skoru", "-")},
                        {"name": "🔥 Risk",        "value": report.get("Risk Seviyesi", "-")},
                        {"name": "🔍 Tespitler",   "value": reasons_text or "Detay yok"},
                    ],
                    "markdown": True
                }
            ],
            "potentialAction": [
                {
                    "@type": "OpenUri",
                    "name": "SOC Paneline Git",
                    "targets": [{"os": "default", "uri": "https://soc.demiroren.com.tr"}]
                }
            ]
        }

        return self._post_payload(payload)

    # ------------------------------------------------------------------
    def _post_payload(self, payload: dict) -> bool:
        """
        JSON payload'ı HTTP POST ile Teams webhook URL'sine gönderir.

        Neden requests değil urllib?
            requests kütüphanesi yüklü olmayabilir (minimal Docker imajları vb.).
            urllib Python standart kütüphanesinde gelir, kurulum gerektirmez.
            requests bağımlılığı requirements.txt'e eklendiyse o da kullanılabilir.
        """
        try:
            body = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                self.webhook_url,
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                status = response.status
                if status == 200:
                    logger.info("Teams bildirimi başarıyla gönderildi.")
                    return True
                else:
                    logger.warning(f"Teams webhook beklenmeyen yanıt: HTTP {status}")
                    return False

        except urllib.error.URLError as e:
            logger.error(f"Teams webhook bağlantı hatası: {e}")
            return False
        except Exception as e:
            logger.error(f"Teams bildirimi gönderilirken beklenmeyen hata: {e}")
            return False


# ===========================================================================
# BÖLÜM 2 – SMTP E-POSTA BİLDİRİCİ
# ===========================================================================
class EmailNotifier:
    """
    Phishing alarmı için SMTP üzerinden HTML e-posta bildirimi gönderir.

    Neden HTML e-posta?
        Düz metin daha taşınabilirdir ancak HTML ile renk, tablo, bold
        kullanarak SOC analistinin dikkatini kritik bilgilere çekebilirsin.

    Gmail için:
        host = "smtp.gmail.com", port = 587
        Uygulama Şifresi kullanılmalı (2FA açık hesaplarda zorunlu).

    Exchange / Office365 için:
        host = "smtp.office365.com", port = 587
    """

    def __init__(self, host: str, port: int, username: str, password: str, sender_email: str):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.sender_email = sender_email

    # ------------------------------------------------------------------
    def send_alert(self, email_meta: dict, report: dict, recipient: str) -> bool:
        """
        Alarm e-postasını gönderir.

        Parametreler:
            email_meta : Orijinal e-posta meta verisi
            report     : agent.py raporu
            recipient  : Bildirimin gideceği SOC e-posta adresi
        """
        subject = (
            f"[PHISHING ALARM] {report.get('Risk Seviyesi', 'RİSK')} | "
            f"{email_meta.get('subject', 'Konu Yok')[:50]}"
        )

        html_body = self._build_html(email_meta, report)
        plain_body = self._build_plain(email_meta, report)

        # MIMEMultipart("alternative") → İstemci HTML destekliyorsa HTML,
        # desteklemiyorsa plain text gösterir. RFC 2046 standardı.
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.sender_email
        msg["To"] = recipient

        # Sıra önemli: plain text önce eklenmeli (fallback), HTML sonra
        msg.attach(MIMEText(plain_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        try:
            # STARTTLS: 587 portunda başlar, sonra TLS'e yükseltilir.
            # Neden doğrudan SSL (465) değil?
            #   STARTTLS daha geniş kurumsal firewall uyumluluğuna sahip.
            with smtplib.SMTP(self.host, self.port, timeout=10) as server:
                server.ehlo()                       # Sunucuya kendini tanıt
                server.starttls()                   # Şifreli kanala geç
                server.ehlo()                       # TLS sonrası tekrar tanıt
                server.login(self.username, self.password)
                server.sendmail(self.sender_email, [recipient], msg.as_string())

            logger.info(f"Alarm e-postası gönderildi → {recipient}")
            return True

        except smtplib.SMTPAuthenticationError:
            logger.error("SMTP kimlik doğrulama hatası. Kullanıcı adı/şifreyi kontrol edin.")
            return False
        except smtplib.SMTPException as e:
            logger.error(f"SMTP hatası: {e}")
            return False
        except Exception as e:
            logger.error(f"E-posta gönderiminde beklenmeyen hata: {e}")
            return False

    # ------------------------------------------------------------------
    def _build_html(self, email_meta: dict, report: dict) -> str:
        """Bildirim e-postasının HTML versiyonunu oluşturur."""
        reasons_html = "".join(
            f"<li style='margin-bottom:6px'>{r}</li>"
            for r in report.get("Gerekçeler ve Tespitler", [])
        )

        risk = report.get("Risk Seviyesi", "")
        risk_color = "#d13438" if "YÜKSEK" in risk else "#107c10"

        return f"""
        <html><body style="font-family: Arial, sans-serif; margin:0; padding:20px; background:#f3f3f3;">
          <div style="max-width:600px; margin:auto; background:#fff; border-radius:8px;
                      border-left: 6px solid {risk_color}; padding:24px; box-shadow:0 2px 8px rgba(0,0,0,0.1)">

            <h2 style="color:{risk_color}; margin-top:0">
              🛡️ Phishing Triage Agent — Alarm Raporu
            </h2>

            <table style="width:100%; border-collapse:collapse; font-size:14px">
              <tr style="background:#f8f8f8">
                <td style="padding:8px 12px; font-weight:bold; width:35%">📧 Gönderen</td>
                <td style="padding:8px 12px">{email_meta.get("from", "-")}</td>
              </tr>
              <tr>
                <td style="padding:8px 12px; font-weight:bold">📌 Konu</td>
                <td style="padding:8px 12px">{email_meta.get("subject", "-")}</td>
              </tr>
              <tr style="background:#f8f8f8">
                <td style="padding:8px 12px; font-weight:bold">⚖️ Karar</td>
                <td style="padding:8px 12px; color:{risk_color}; font-weight:bold">
                  {report.get("Karar", "-")}
                </td>
              </tr>
              <tr>
                <td style="padding:8px 12px; font-weight:bold">🎯 Güven Skoru</td>
                <td style="padding:8px 12px">{report.get("Güven Skoru", "-")}</td>
              </tr>
              <tr style="background:#f8f8f8">
                <td style="padding:8px 12px; font-weight:bold">🔥 Risk Seviyesi</td>
                <td style="padding:8px 12px; color:{risk_color}; font-weight:bold">
                  {report.get("Risk Seviyesi", "-")}
                </td>
              </tr>
            </table>

            <h3 style="margin-top:20px; color:#333">🔍 Tespitler ve Gerekçeler</h3>
            <ul style="color:#555; padding-left:20px">{reasons_html}</ul>

            <hr style="border:none; border-top:1px solid #eee; margin:20px 0">
            <p style="font-size:12px; color:#999; text-align:center">
              Bu e-posta Demirören Medya Bilgi Güvenliği Phishing Triage Agent tarafından otomatik oluşturulmuştur.<br>
              Analiz zamanı: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}
            </p>
          </div>
        </body></html>
        """

    # ------------------------------------------------------------------
    def _build_plain(self, email_meta: dict, report: dict) -> str:
        """HTML desteklemeyen istemciler için düz metin versiyonu."""
        reasons = "\n".join(
            f"  - {r}" for r in report.get("Gerekçeler ve Tespitler", [])
        )
        return (
            f"=== PHISHING TRİAJ ALARM RAPORU ===\n"
            f"Gönderen    : {email_meta.get('from', '-')}\n"
            f"Konu        : {email_meta.get('subject', '-')}\n"
            f"Karar       : {report.get('Karar', '-')}\n"
            f"Güven Skoru : {report.get('Güven Skoru', '-')}\n"
            f"Risk        : {report.get('Risk Seviyesi', '-')}\n\n"
            f"Tespitler:\n{reasons}\n\n"
            f"Analiz: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n"
        )


# ===========================================================================
# BÖLÜM 3 – MOCK BİLDİRİCİ (Gerçek gönderim olmadan test için)
# ===========================================================================
class MockNotifier:
    """
    Gerçek Teams/SMTP bağlantısı olmadan bildirimleri terminale yazar.
    Geliştirme ve test ortamında kullanılır.
    """

    def __init__(self):
        logger.info("MockNotifier başlatıldı (Test Modu — gerçek bildirim gönderilmez).")

    def send_alert(self, email_meta: dict, report: dict, **kwargs) -> bool:
        """
        Alarm içeriğini terminale yazdırır.
        kwargs → recipient gibi parametreleri sessizce yutmak için.
        """
        logger.warning("=" * 60)
        logger.warning("[MOCK BİLDİRİM] Gerçek ortamda aşağıdaki alarm gönderilirdi:")
        logger.warning(f"  Gönderen    : {email_meta.get('from', '-')}")
        logger.warning(f"  Konu        : {email_meta.get('subject', '-')}")
        logger.warning(f"  Karar       : {report.get('Karar', '-')}")
        logger.warning(f"  Güven Skoru : {report.get('Güven Skoru', '-')}")
        logger.warning(f"  Risk        : {report.get('Risk Seviyesi', '-')}")
        logger.warning("=" * 60)
        return True


# ===========================================================================
# BÖLÜM 4 – FACTORY FONKSİYONU
# ===========================================================================
def get_notifier(channel: str = "mock", **kwargs):
    """
    Hangi bildirim kanalını kullanacağını belirleyen fabrika fonksiyonu.

    Parametreler:
        channel : "mock"   → Terminale yaz (test)
                  "teams"  → Microsoft Teams Webhook
                  "email"  → SMTP e-posta

        **kwargs : Seçilen kanala göre gerekli parametreler:
            teams → webhook_url
            email → host, port, username, password, sender_email

    Kullanım:
        # Test:
        notifier = get_notifier("mock")

        # Teams:
        notifier = get_notifier("teams", webhook_url=os.getenv("TEAMS_WEBHOOK_URL"))

        # E-posta:
        notifier = get_notifier(
            "email",
            host="smtp.office365.com", port=587,
            username="soc-agent@demiroren.com.tr",
            password=os.getenv("SMTP_PASSWORD"),
            sender_email="soc-agent@demiroren.com.tr"
        )
    """
    if channel == "mock":
        return MockNotifier()

    elif channel == "teams":
        webhook_url = kwargs.get("webhook_url", "")
        if not webhook_url:
            raise ValueError("Teams kanalı için 'webhook_url' parametresi zorunlu.")
        return TeamsNotifier(webhook_url=webhook_url)

    elif channel == "email":
        required = ["host", "port", "username", "password", "sender_email"]
        for key in required:
            if key not in kwargs:
                raise ValueError(f"E-posta kanalı için '{key}' parametresi zorunlu.")
        return EmailNotifier(**kwargs)

    else:
        raise ValueError(f"Geçersiz kanal: '{channel}'. 'mock', 'teams' veya 'email' kullanınız.")
