import streamlit as st
import sys 
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
sys.path.insert(0, os.path.abspath("src"))
from agent import PhishingTriageAgent
import pandas as pd
import random
from datetime import datetime, timedelta

from src.agent import PhishingTriageAgent
import json 
import time

# ------------------------------------------------------------------
# SAYFA AYARLARI
# ------------------------------------------------------------------
st.set_page_config(
    page_title="Phishing Triage Agent | SOC Dashboard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ------------------------------------------------------------------
# KOYU / KURUMSAL TEMA (Demirören Medya Dashboard)
# ------------------------------------------------------------------
st.markdown(
    """
    <style>
    :root {
        --dm-bg: #0b0f19;
        --dm-panel: #121826;
        --dm-panel-alt: #161d2e;
        --dm-border: #23283a;
        --dm-red: #e63946;
        --dm-orange: #f4a259;
        --dm-green: #2ecc71;
        --dm-blue: #4c7cf0;
        --dm-text: #e6e9f0;
        --dm-subtext: #8a92a6;
    }

    .stApp {
        background-color: var(--dm-bg);
        color: var(--dm-text);
        font-family: 'Segoe UI', 'Inter', sans-serif;
    }

    section[data-testid="stSidebar"] {
        background-color: var(--dm-panel);
        border-right: 1px solid var(--dm-border);
    }

    h1, h2, h3, h4 {
        color: var(--dm-text) !important;
        font-weight: 700 !important;
    }

    .dm-header {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 6px 0 18px 0;
        border-bottom: 1px solid var(--dm-border);
        margin-bottom: 20px;
    }
    .dm-header .badge {
        background: var(--dm-red);
        color: white;
        font-size: 11px;
        font-weight: 700;
        padding: 3px 10px;
        border-radius: 20px;
        letter-spacing: 0.5px;
    }
    .dm-header .subtitle {
        color: var(--dm-subtext);
        font-size: 13px;
        margin-top: -6px;
    }

    /* Metrik kartları */
    .metric-card {
        background: linear-gradient(145deg, var(--dm-panel), var(--dm-panel-alt));
        border: 1px solid var(--dm-border);
        border-radius: 10px;
        padding: 18px 20px;
        height: 110px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }
    .metric-label {
        color: var(--dm-subtext);
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 0.6px;
    }
    .metric-value {
        font-size: 30px;
        font-weight: 800;
        line-height: 1.1;
    }
    .metric-sub {
        font-size: 12px;
        font-weight: 600;
    }

    .accent-red   { color: var(--dm-red); }
    .accent-green { color: var(--dm-green); }
    .accent-blue  { color: var(--dm-blue); }
    .accent-orange{ color: var(--dm-orange); }

    /* Sonuç kutusu */
    .result-box {
        border-radius: 10px;
        padding: 16px 18px;
        margin-top: 14px;
        border-left: 5px solid var(--dm-border);
        background: var(--dm-panel);
    }
    .result-box.critical { border-left-color: var(--dm-red); background: rgba(230,57,70,0.08); }
    .result-box.clean    { border-left-color: var(--dm-green); background: rgba(46,204,113,0.08); }

    .stButton>button {
        background-color: var(--dm-red);
        color: white;
        font-weight: 700;
        border: none;
        border-radius: 8px;
        padding: 10px 0;
        width: 100%;
    }
    .stButton>button:hover {
        background-color: #ff4c58;
        color: white;
    }

    div[data-testid="stTabs"] button[role="tab"] {
        color: var(--dm-subtext);
        font-weight: 600;
    }
    div[data-testid="stTabs"] button[aria-selected="true"] {
        color: var(--dm-text) !important;
        border-bottom: 2px solid var(--dm-red) !important;
    }

    .stDataFrame { border: 1px solid var(--dm-border); border-radius: 8px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ------------------------------------------------------------------
# AGENT'I YÜKLE (cache ile tek sefer)
# ------------------------------------------------------------------
@st.cache_resource
def load_agent():
    return PhishingTriageAgent()

agent = load_agent()



# Web panelinin 5 saniyede bir kendini canlı yenilemesi için:
from streamlit_autorefresh import st_autorefresh
st_autorefresh(interval=10000, key="datarefresh") # 10 saniyede bir canlı yeniler

def load_live_incidents():
    try:
        with open("incidents.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

# ------------------------------------------------------------------
# SESSION STATE — Olay geçmişi (Incidents)
# ------------------------------------------------------------------

    

if "incidents" not in st.session_state:
    st.session_state.incidents = load_live_incidents()

if "total_scanned" not in st.session_state:
    st.session_state.total_scanned = len(st.session_state.incidents)

# ------------------------------------------------------------------
# BAŞLIK
# ------------------------------------------------------------------
st.markdown(
    """
    <div class="dm-header">
        <div style="font-size:28px;">🛡️</div>
        <div>
            <div style="font-size:22px; font-weight:800;">Phishing Triage Agent</div>
            <div class="subtitle">SOC Incident Dashboard · Canlı Ortam</div>
        </div>
        <div style="flex:1;"></div>
        <div class="badge">LIVE</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ------------------------------------------------------------------
# ÜST METRİK KARTLARI
# ------------------------------------------------------------------
df_incidents = pd.DataFrame(st.session_state.incidents)
total_scanned = st.session_state.total_scanned
phishing_count = len(df_incidents[df_incidents["Karar"] == "PHISHING"]) if not df_incidents.empty else 0
clean_count = len(df_incidents[df_incidents["Karar"] == "CLEAN"]) if not df_incidents.empty else 0

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Toplam Taranan Mail</div>
            <div class="metric-value">{total_scanned}</div>
            <div class="metric-sub accent-blue">📥 Tüm zamanlar</div>
        </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Tespit Edilen Phishing</div>
            <div class="metric-value accent-red">{phishing_count}</div>
            <div class="metric-sub accent-red">🚨 CRITICAL / HIGH</div>
        </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Temiz Mailler</div>
            <div class="metric-value accent-green">{clean_count}</div>
            <div class="metric-sub accent-green">✅ Güvenli</div>
        </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown("""
        <div class="metric-card">
            <div class="metric-label">Sistem Durumu</div>
            <div class="metric-value accent-green">ONLINE</div>
            <div class="metric-sub accent-green">🟢 Agent aktif</div>
        </div>
    """, unsafe_allow_html=True)

st.write("")

# ------------------------------------------------------------------
# SIDEBAR — Manuel Analiz
# ------------------------------------------------------------------
with st.sidebar:
    st.markdown("### ✉️ Manuel E-Posta Analizi")
    st.caption("Analiz etmek istediğin mail içeriğini yapıştır.")

    email_body = st.text_area(
        "Mail İçeriği",
        height=260,
        placeholder="From: finance@sirket.com\nSubject: Acil Ödeme Talebi\n\nMerhaba, aşağıdaki linke tıklayarak...",
        label_visibility="collapsed",
    )

    analyze_clicked = st.button("🚨 E-Postayı Analiz Et")

    if analyze_clicked:
        if not email_body.strip():
            st.warning("Lütfen analiz edilecek bir mail içeriği girin.")
        else:
            with st.spinner("Agent analiz ediyor..."):
                report = agent.analyze_email(email_body)

            karar = report.get("Karar", "BİLİNMİYOR")
            risk = report.get("Risk Seviyesi", "BİLİNMİYOR")
            skor = report.get("Güven Skoru", "%0.00")

            box_class = "critical" if karar == "PHISHING" else "clean"
            icon = "🚨" if karar == "PHISHING" else "✅"

            st.markdown(f"""
                <div class="result-box {box_class}">
                    <div style="font-size:15px; font-weight:800;">{icon} {karar}</div>
                    <div style="margin-top:6px; font-size:13px; color:var(--dm-subtext);">
                        Risk Seviyesi: <b>{risk}</b><br>
                        Güven Skoru: <b>{skor}</b>
                    </div>
                </div>
            """, unsafe_allow_html=True)

            # Sonucu Incidents akışına ekle
            subject_line = next(
                (line.split(":", 1)[1].strip() for line in email_body.splitlines()
                 if line.lower().startswith("subject:")),
                "(Konu tespit edilemedi)"
            )
            sender_line = next(
                (line.split(":", 1)[1].strip() for line in email_body.splitlines()
                 if line.lower().startswith("from:")),
                "(Gönderen tespit edilemedi)"
            )

            st.session_state.incidents.insert(0, {
                "Zaman": datetime.now().strftime("%H:%M:%S"),
                "Gönderen": sender_line,
                "Konu": subject_line,
                "Karar": karar,
                "Risk Seviyesi": risk,
                "Güven Skoru": skor,
            })
            st.session_state.total_scanned += 1
            st.rerun()

    st.markdown("---")
    st.caption("Phishing Triage Agent v1.0 · Staj Projesi")

# ------------------------------------------------------------------
# ANA GÖVDE — TABS
# ------------------------------------------------------------------
tab1, tab2 = st.tabs(["📋 Incidents / Olay Akışı", "📊 Grafikler & Rapor"])

# ---------------- TAB 1: Incidents ----------------
with tab1:
    st.markdown("#### Son Tespit Edilen Olaylar")

    df_view = pd.DataFrame(st.session_state.incidents)

    if df_view.empty:
        st.info("Henüz kayıtlı bir olay yok.")
    else:
        def _highlight_risk(val):
            if "CRITICAL" in str(val) or "YÜKSEK" in str(val):
                return "color: #e63946; font-weight: 700;"
            elif "LOW" in str(val) or "DÜŞÜK" in str(val):
                return "color: #2ecc71; font-weight: 700;"
            return ""

        def _highlight_karar(val):
            if val == "PHISHING":
                return "color: #e63946; font-weight: 700;"
            elif val == "CLEAN":
                return "color: #2ecc71; font-weight: 700;"
            return ""

        styled = (
            df_view.style
            .applymap(_highlight_risk, subset=["Risk Seviyesi"])
            .applymap(_highlight_karar, subset=["Karar"])
        )
        st.dataframe(styled, use_container_width=True, height=380)

# ---------------- TAB 2: Grafikler & Rapor ----------------
with tab2:
    st.markdown("#### Genel Dağılım ve Skor Trendi")

    g1, g2 = st.columns(2)

    with g1:
        st.markdown("**Phishing / Clean Oranı**")
        dist_df = pd.DataFrame({
            "Kategori": ["PHISHING", "CLEAN"],
            "Adet": [phishing_count, clean_count],
        }).set_index("Kategori")
        st.bar_chart(dist_df, color="#e63946")

    with g2:
        st.markdown("**Güven Skoru Trendi (son olaylar)**")
        if not df_view.empty:
            scores = (
                df_view["Güven Skoru"]
                .astype(str)
                .str.replace("%", "", regex=False)
                .astype(float)
            )
            trend_df = pd.DataFrame({
                "Olay Sırası": range(1, len(scores) + 1),
                "Güven Skoru (%)": scores.values,
            }).set_index("Olay Sırası")
            st.line_chart(trend_df)
        else:
            st.info("Henüz veri yok.")

    st.markdown("---")
    st.caption(
        f"Rapor oluşturulma zamanı: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')} · "
        f"Toplam {total_scanned} mail tarandı."
    )
