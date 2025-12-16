import streamlit as st
import pandas as pd
import os
import time
from datetime import datetime
import base64
from PIL import Image  # si luego no lo usas, lo puedes quitar


def get_image_base64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


FONDO_PATH = "data/Captura de pantalla 2025-11-24 a las 16.52.04.png"
LOGO_PATH  = "data/logo.png"

fondo_base64 = get_image_base64(FONDO_PATH)
logo_base64  = get_image_base64(LOGO_PATH)


# =========================
# ✅ CONFIGURAR PÁGINA (ancho completo)
# =========================
st.set_page_config(
    page_title="Grupo Orlegi - Panel",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =========================
# ✅ CSS GLOBAL (estilo consistente local/cloud)
# =========================
st.markdown(
    f"""
    <style>
    :root {{
        --orlegi-primary: #0b3c7c;
        --orlegi-primary-hover: #0f4f9c;
        --orlegi-dark: rgba(4, 18, 46, 0.88);
        --orlegi-card: rgba(6, 27, 70, 0.95);
        --orlegi-text: #ffffff;
    }}

    html, body, .stApp {{
        margin: 0;
        padding: 0;
        height: 100%;
        overscroll-behavior: none;
        color: var(--orlegi-text);
        font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
    }}

    /* Ocultar barra superior de Streamlit (Deploy, menú, etc.) */
    header[data-testid="stHeader"],
    .stApp header,
    [data-testid="stToolbar"] {{
        display: none !important;
        visibility: hidden !important;
        height: 0 !important;
    }}

    /* Quitar espacio superior que deja la cabecera */
    main.block-container {{
        padding-top: 0 !important;
        margin-top: 0 !important;
    }}

    /* Fondo general */
    .background-image {{
        position: fixed;
        top: 0;
        left: 0;
        height: 100%;
        width: 100%;
        background-image: url("data:image/png;base64,{fondo_base64}");
        background-size: cover;
        background-position: center;
        opacity: 0.40;
        z-index: 0;
    }}

    .main-content {{
        position: relative;
        z-index: 2;
    }}

    /* Caja / tarjetas */
    .login-box {{
        background-color: var(--orlegi-dark);
        border-radius: 1rem;
        box-shadow: 0px 0px 25px rgba(0,0,0,0.4);
    }}

    .orlegi-card {{
        background-color: var(--orlegi-card);
        color: var(--orlegi-text);
        border-radius: 16px;
        padding: 16px 20px;
    }}

    .orlegi-tag {{
        background-color: var(--orlegi-primary);
        color: white;
        padding: 4px 10px;
        border-radius: 999px;
        font-size: 12px;
        display: inline-block;
    }}

    /* Botones azules */
    div.stButton > button:first-child {{
        background-color: var(--orlegi-primary);
        color: white;
        border-radius: 8px;
        border: 1px solid var(--orlegi-primary);
    }}
    div.stButton > button:first-child:hover {{
        background-color: var(--orlegi-primary-hover);
        border-color: var(--orlegi-primary-hover);
    }}

    label, .stTextInput label, .stPasswordInput label {{
        color: white !important;
    }}
    </style>

    <div class="background-image"></div>
    """,
    unsafe_allow_html=True
)


# =========================
# ESTADO DE SESIÓN
# =========================
if "logueado" not in st.session_state:
    st.session_state.logueado = False
if "usuario_actual" not in st.session_state:
    st.session_state.usuario_actual = None


# Credenciales válidas (provisional)
USUARIOS_VALIDOS = {
    "admin": "1234",
    "Ruben.puerta": "Orlegi2025",
    "Pelayo.quiros": "Orlegi2025",
    "Israel.villaseñor": "Orlegi2025",
    "Jose.riestra": "Orlegi2025",
    "Gerardo": "Orlegi2025"
}



# -------------------------------
# 🔐 LOGIN (con fondo restaurado)
# -------------------------------
if not st.session_state.logueado:

    st.markdown(
        f"""
        <style>
        body, html, .stApp {{
            margin: 0;
            padding: 0;
            height: 100%;
            overscroll-behavior: none;
        }}

        /* Fondo del login */
        .background-image-login {{
            position: fixed;
            top: 0;
            left: 0;
            height: 100%;
            width: 100%;
            background-image: url("data:image/png;base64,{fondo_base64}");
            background-size: cover;
            background-position: center;
            opacity: 0.99;
            z-index: 0;
        }}

        /* Contenedor login */
        .login-container {{
            position: relative;
            z-index: 2;
        }}

        #MainMenu, footer {{
            visibility: hidden;
        }}

        /* Ocultamos sidebar mientras NO está logueado */
        [data-testid="stSidebar"],
        [data-testid="stSidebarNav"],
        [data-testid="stSidebarToggle"] {{
            display: none !important;
        }}

        .block-container {{
            display: flex;
            justify-content: center;
            align-items: center;
            height: 90vh;
            flex-direction: column;
        }}

        .login-box {{
            width: 100%;
            max-width: 420px;
            padding: 2rem;
            border-radius: 1rem;
            background-color: var(--orlegi-dark);
            box-shadow: 0px 0px 25px rgba(0,0,0,0.4);
        }}
        </style>

        <div class="background-image-login"></div>
        """,
        unsafe_allow_html=True
    )

    # ---- INTERFAZ DEL LOGIN ----
    with st.container():
        st.markdown('<div class="login-container">', unsafe_allow_html=True)

        st.markdown(
            f"""
            <div style="margin-bottom: 1.5rem; text-align:center;">
                <img src="data:image/png;base64,{logo_base64}"
                     style="width: 260px; border-radius: 10px;">
            </div>
            """,
            unsafe_allow_html=True
        )

        st.markdown(
            "<h4 style='text-align:center; color:white; margin-bottom: 1rem;'>Analytics / Scouting</h4>",
            unsafe_allow_html=True
        )

        usuario = st.text_input("Usuario")
        contrasena = st.text_input("Contraseña", type="password")

        if st.button("Acceder"):
            if usuario in USUARIOS_VALIDOS and USUARIOS_VALIDOS[usuario] == contrasena:
                st.session_state.logueado = True
                st.session_state.usuario_actual = usuario

                # 🚀 Redirigir correctamente
                st.switch_page("pages/Campogramas.py")
            else:
                st.error("❌ Usuario o contraseña incorrectos.")

    st.stop()


# =========================
# 🖼️ Logo superior (panel)
# =========================
st.markdown(
    f"""
    <div style="
        position: fixed;
        top: 30px;
        right: 30px;
        z-index: 1000;
    ">
        <img src="data:image/png;base64,{logo_base64}"
             alt="Logo Grupo Orlegi"
             style="width: 180px; border-radius: 6px;">
    </div>
    """,
    unsafe_allow_html=True
)
