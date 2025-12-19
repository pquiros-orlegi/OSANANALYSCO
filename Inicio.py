import streamlit as st
import base64
import sqlite3
from pathlib import Path
from werkzeug.security import generate_password_hash, check_password_hash

# =========================
# UTILIDADES IMÁGENES
# =========================
def get_image_base64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

FONDO_PATH = "data/Captura de pantalla 2025-11-24 a las 16.52.04.png"
LOGO_PATH  = "data/logo.png"

fondo_base64 = get_image_base64(FONDO_PATH)
logo_base64  = get_image_base64(LOGO_PATH)

# =========================
# CONFIG STREAMLIT
# =========================
st.set_page_config(
    page_title="Grupo Orlegi - Panel",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =========================
# CSS (TU ESTÉTICA, IGUAL)
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
        height: 100%;
        color: var(--orlegi-text);
        font-family: ui-sans-serif, system-ui;
    }}

    header, footer {{
        display: none !important;
    }}

    main.block-container {{
        padding-top: 0 !important;
    }}

    .background-image {{
        position: fixed;
        inset: 0;
        background-image: url("data:image/png;base64,{fondo_base64}");
        background-size: cover;
        background-position: center;
        opacity: 0.4;
        z-index: 0;
    }}

    .login-box {{
        background-color: var(--orlegi-dark);
        border-radius: 1rem;
        box-shadow: 0 0 25px rgba(0,0,0,.4);
        padding: 2rem;
        max-width: 420px;
        margin: auto;
    }}

    div.stButton > button:first-child {{
        background-color: var(--orlegi-primary);
        color: white;
        border-radius: 8px;
        border: 1px solid var(--orlegi-primary);
    }}

    div.stButton > button:first-child:hover {{
        background-color: var(--orlegi-primary-hover);
    }}

    label {{
        color: white !important;
    }}
    </style>

    <div class="background-image"></div>
    """,
    unsafe_allow_html=True
)

# =========================
# BASE DE DATOS
# =========================
DB_PATH = "data/usuarios.db"
Path("data").mkdir(exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario TEXT UNIQUE,
        password TEXT,
        rol TEXT DEFAULT 'user',
        forzar_cambio INTEGER DEFAULT 1
    )
    """)
    conn.commit()
    conn.close()

def crear_usuario(usuario, password, rol="user"):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute(
            """INSERT INTO usuarios (usuario, password, rol, forzar_cambio)
               VALUES (?, ?, ?, 1)""",
            (usuario, generate_password_hash(password), rol)
        )
        conn.commit()
    except:
        pass
    conn.close()

def get_user(usuario):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT usuario, password, forzar_cambio FROM usuarios WHERE usuario=?",
        (usuario,)
    )
    row = c.fetchone()
    conn.close()
    return row

def verificar_login(usuario, password):
    user = get_user(usuario)
    if user:
        return check_password_hash(user[1], password)
    return False

def debe_cambiar_password(usuario):
    user = get_user(usuario)
    return user and user[2] == 1

def cambiar_password(usuario, nueva):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """UPDATE usuarios
           SET password=?, forzar_cambio=0
           WHERE usuario=?""",
        (generate_password_hash(nueva), usuario)
    )
    conn.commit()
    conn.close()

init_db()

# =========================
# USUARIOS INICIALES
# =========================
usuarios = [
    "admin","rpuerta","pquiros","ivillaseñor",
    "jriestra","ggarcia","jmhernandez",
    "flobeiras","mromero"
]

for u in usuarios:
    crear_usuario(u, "Orlegi2025", "admin" if u == "admin" else "user")

# =========================
# SESSION STATE
# =========================
if "logueado" not in st.session_state:
    st.session_state.logueado = False
if "usuario_actual" not in st.session_state:
    st.session_state.usuario_actual = None
if "forzar_cambio" not in st.session_state:
    st.session_state.forzar_cambio = False

# =========================
# LOGIN
# =========================
if not st.session_state.logueado:

    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] { display: none !important; }
        .block-container {
            display: flex;
            justify-content: center;
            align-items: center;
            height: 90vh;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    st.markdown(
        f"""
        <div style="text-align:center; margin-bottom:1.5rem;">
            <img src="data:image/png;base64,{logo_base64}" style="width:260px;">
        </div>
        """,
        unsafe_allow_html=True
    )

    usuario = st.text_input("Usuario")
    contrasena = st.text_input("Contraseña", type="password")

    if st.button("Acceder"):
        if verificar_login(usuario, contrasena):
            st.session_state.logueado = True
            st.session_state.usuario_actual = usuario
            st.session_state.forzar_cambio = debe_cambiar_password(usuario)
            st.rerun()
        else:
            st.error("❌ Usuario o contraseña incorrectos")

    st.stop()

# =========================
# FORZAR CAMBIO PRIMER LOGIN
# =========================
if st.session_state.forzar_cambio:
    st.warning("⚠️ Debes cambiar tu contraseña antes de continuar")

    actual = st.text_input("Contraseña actual", type="password")
    nueva = st.text_input("Nueva contraseña", type="password")
    confirmar = st.text_input("Confirmar nueva contraseña", type="password")

    if st.button("Guardar nueva contraseña"):
        if not verificar_login(st.session_state.usuario_actual, actual):
            st.error("Contraseña actual incorrecta")
        elif nueva != confirmar:
            st.error("No coinciden")
        elif len(nueva) < 8:
            st.error("Mínimo 8 caracteres")
        else:
            cambiar_password(st.session_state.usuario_actual, nueva)
            st.session_state.forzar_cambio = False
            st.success("Contraseña actualizada correctamente")
            st.rerun()

    st.stop()

# =========================
# PANEL NORMAL
# =========================
st.markdown(
    f"""
    <div style="position:fixed; top:30px; right:30px; z-index:1000;">
        <img src="data:image/png;base64,{logo_base64}" style="width:180px;">
    </div>
    """,
    unsafe_allow_html=True
)

st.success(f"Bienvenido {st.session_state.usuario_actual}")

if st.sidebar.button("🚪 Cerrar sesión"):
    st.session_state.logueado = False
    st.session_state.usuario_actual = None
    st.session_state.forzar_cambio = False
    st.rerun()

