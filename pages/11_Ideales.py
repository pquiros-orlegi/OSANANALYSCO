import streamlit as st
import base64
import fitz  # PyMuPDF
from pathlib import Path

# =========================
# RUTAS ROBUSTAS (tu script está en /pages)
# =========================
ROOT_DIR = Path(__file__).resolve().parents[1]  # sube de /pages a la raíz del proyecto
ASSETS_DIR = ROOT_DIR / "assets"
DATA_DIR = ROOT_DIR / "data"

FONDO_PATH = DATA_DIR / "Captura de pantalla 2025-11-24 a las 16.52.04.png"

# =========================
# FONDO
# =========================
def get_image_base64(path: Path) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

if FONDO_PATH.exists():
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
else:
    st.warning(f"⚠️ No encuentro el fondo en: {FONDO_PATH}")

# =========================
# LOGIN (si vienes de Inicio/home)
# =========================
if "logueado" in st.session_state and not st.session_state["logueado"]:
    st.error("Debes iniciar sesión en la página principal (Inicio/home) para acceder a este panel.")
    st.stop()

# ==========================================================
# FUNCIÓN: Buscar PDFs con formato 11_IDEALES_I_MES_I_AÑO.pdf
# ==========================================================
def listar_pdfs_11_ideales() -> dict:
    """
    Busca PDFs tipo '11_IDEALES_I_OCTUBRE_I_2025.pdf' en la carpeta assets
    y devuelve un dict {etiqueta bonita -> ruta_pdf}.
    """
    if not ASSETS_DIR.exists():
        return {}

    rutas = list(ASSETS_DIR.glob("11_IDEALES_I_*_I_*.pdf"))

    pdfs = {}
    for ruta in rutas:
        nombre = ruta.name  # ej: 11_IDEALES_I_OCTUBRE_I_2025.pdf
        partes = nombre.split("_I_")  # ['11_IDEALES', 'OCTUBRE', '2025.pdf']
        if len(partes) != 3:
            continue

        mes = partes[1].capitalize()
        anio = partes[2].replace(".pdf", "")

        etiqueta = f"{mes} {anio}"  # ej.: Octubre 2025
        pdfs[etiqueta] = str(ruta)

    # Orden alfabético por etiqueta (si prefieres por año/mes, te lo ordeno)
    return dict(sorted(pdfs.items(), key=lambda x: x[0]))

# ==========================================================
# FUNCIÓN: Mostrar cada página del PDF como imagen
# ==========================================================
def mostrar_pdf_como_imagenes(pdf_path: str):
    pdf_path = str(Path(pdf_path).resolve())

    if not Path(pdf_path).exists():
        st.error(f"❌ No se encontró el PDF en: {pdf_path}")
        return

    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        st.error(f"❌ Error abriendo PDF: {e}")
        return

    for page in doc:
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # zoom x2
        img_bytes = pix.tobytes("png")
        st.image(img_bytes, use_container_width=True)

# ==========================================================
# APP
# ==========================================================
def app():
    st.title("11 Ideales — Selección por Mes")

    pdfs = listar_pdfs_11_ideales()

    if not pdfs:
        st.warning("No se han encontrado PDFs de '11 IDEALES' en la carpeta assets.")
        st.info("Asegúrate de guardar archivos como: 11_IDEALES_I_MES_I_2025.pdf")
        st.write("ASSETS_DIR:", str(ASSETS_DIR))
        st.write("Existe ASSETS_DIR:", ASSETS_DIR.exists())
        st.write("PDFs en assets:", [p.name for p in ASSETS_DIR.glob("*.pdf")] if ASSETS_DIR.exists() else [])
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


