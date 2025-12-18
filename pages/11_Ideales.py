import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from mplsoccer import Pitch
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode
import base64

import fitz  # PyMuPDF
import os
import glob

# =========================
# FONDO
# =========================
FONDO_PATH = "data/Captura de pantalla 2025-11-24 a las 16.52.04.png"


def get_image_base64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


fondo_base64 = get_image_base64(FONDO_PATH)

st.markdown(
    f"""
    <style>
    html, body, .stApp {{
        margin: 0;
        padding: 0;
        height: 100%;
        overscroll-behavior: none;
        background: transparent !important;
    }}

    .main .block-container {{
        position: relative;
        z-index: 2;
        background: transparent !important;
    }}

    .background-image-rating {{
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
    </style>

    <div class="background-image-rating"></div>
    """,
    unsafe_allow_html=True
)

# =========================
# ⚠️ PROTEGER CON LOGIN DE home.py
# =========================
if "logueado" in st.session_state and not st.session_state.logueado:
    st.error("Debes iniciar sesión en la página principal (home.py) para acceder a este panel.")
    st.stop()


ASSETS_DIR = "assets"  # carpeta donde guardas los PDFs


# ==========================================================
# FUNCIÓN: Buscar PDFs con formato 11_IDEALES_I_MES_I_AÑO.pdf
# ==========================================================
def listar_pdfs_11_ideales():
    """
    Busca PDFs tipo '11_IDEALES_I_MES_I_2025.pdf' en la carpeta assets
    y devuelve un dict {etiqueta bonita -> ruta_pdf}.
    """
    patron = os.path.join(ASSETS_DIR, "/Users/pelayoquiros/Desktop/Proyect/Grupo Orlegi/STREAMLIT/GrupoOrlegi/assets/11_IDEALES_I_OCTUBRE_I_2025.pdf")
    rutas = glob.glob(patron)

    pdfs = {}
    for ruta in rutas:
        nombre = os.path.basename(ruta)

        partes = nombre.split("_I_")  # ['11_IDEALES', 'OCTUBRE', '2025.pdf']
        if len(partes) != 3:
            continue

        mes = partes[1].capitalize()
        anio = partes[2].replace(".pdf", "")

        etiqueta = f"{mes} {anio}"  # ej.: Octubre 2025
        pdfs[etiqueta] = ruta

    pdfs_ordenados = dict(sorted(pdfs.items(), key=lambda x: x[0]))
    return pdfs_ordenados


# ==========================================================
# FUNCIÓN: Mostrar cada página del PDF como imagen (sin "Página X")
# ==========================================================
def mostrar_pdf_como_imagenes(pdf_path: str):
    abs_path = os.path.abspath(pdf_path)


    if not os.path.exists(pdf_path):
        st.error(f"❌ No se encontró el archivo en: {pdf_path}")
        return

    doc = fitz.open(pdf_path)



    for page in doc:
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # zoom x2
        img_bytes = pix.tobytes("png")
        st.image(img_bytes, use_container_width=True)


# ==========================================================
# PÁGINA PRINCIPAL
# ==========================================================
def app():
    st.title("11 Ideales — Selección por Mes")

    pdfs = listar_pdfs_11_ideales()

    if not pdfs:
        st.warning("No se han encontrado PDFs de '11 IDEALES' en la carpeta assets.")
        st.info("Asegúrate de guardar archivos como: 11_IDEALES_I_MES_I_2025.pdf")
        return

    etiquetas = list(pdfs.keys())

    seleccion = st.selectbox(
        "Selecciona el mes de 11 ideales que quieres ver:",
        options=etiquetas,
        index=len(etiquetas) - 1,
        key="select_11_ideales"
    )

    st.markdown(f"### Mostrando: **{seleccion}**")

    mostrar_pdf_como_imagenes(pdfs[seleccion])


if __name__ == "__main__":
    app()


