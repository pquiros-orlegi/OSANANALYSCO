import streamlit as st
import base64
import sqlite3
from pathlib import Path
from werkzeug.security import generate_password_hash, check_password_hash

# =========================
# UTILIDADES IMÁGENES (robusto si falta el archivo)
# =========================
def get_image_base64(path: str) -> str | None:
    p = Path(path)
    if not p.exists():
        return None
    try:
        with open(p, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return None

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
# CSS (tu estética)
# =========================
bg_div = ""
bg_css = ""
if fondo_base64:
    bg_css = f"""
    .background-image {{
        position: fixed;
        inset: 0;
        background-image: url("data:image/png;base64,{fondo_base64}");
        background-size: cover;
        background-position: center;
        opacity: 0.4;
        z-index: 0;
    }}
    """
    bg_div = """<div class="background-image"></div>"""

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
        position: relative;
        z-index: 1; /* encima del fondo */
    }}

    {bg_css}

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

    {bg_div}
    """,
    unsafe_allow_html=True
)

# =========================
# BASE DE DATOS (SQLite)
# =========================
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = str(DATA_DIR / "usuarios.db")

def db_connect():
    # timeout ayuda en Cloud si hay locks breves
    return sqlite3.connect(DB_PATH, timeout=30)

def init_db():
    conn = db_connect()
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        rol TEXT DEFAULT 'user',
        forzar_cambio INTEGER DEFAULT 1
    )
    """)
    conn.commit()
    conn.close()

def crear_usuario_si_no_existe(usuario: str, password: str, rol: str = "user"):
    """
    Inserta solo si no existe. NO ocultamos errores reales.
    """
    usuario = normalizar_usuario(usuario)
    conn = db_connect()
    c = conn.cursor()
    try:
        c.execute(
            """INSERT INTO usuarios (usuario, password, rol, forzar_cambio)
               VALUES (?, ?, ?, 1)""",
            (usuario, generate_password_hash(password), rol)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        # usuario ya existe
        pass
    finally:
        conn.close()

def get_user(usuario: str):
    usuario = normalizar_usuario(usuario)
    conn = db_connect()
    c = conn.cursor()
    c.execute(
        "SELECT usuario, password, forzar_cambio, rol FROM usuarios WHERE usuario=?",
        (usuario,)
    )
    row = c.fetchone()
    conn.close()
    return row  # (usuario, password_hash, forzar_cambio, rol)

def verificar_login(usuario: str, password: str) -> bool:
    user = get_user(usuario)
    if user:
        return check_password_hash(user[1], password)
    return False

def debe_cambiar_password(usuario: str) -> bool:
    user = get_user(usuario)
    return bool(user) and int(user[2]) == 1

def cambiar_password(usuario: str, nueva: str):
    usuario = normalizar_usuario(usuario)
    conn = db_connect()
    c = conn.cursor()
    c.execute(
        """UPDATE usuarios
           SET password=?, forzar_cambio=0
           WHERE usuario=?""",
        (generate_password_hash(nueva), usuario)
    )
    conn.commit()
    conn.close()

def normalizar_usuario(usuario: str) -> str:
    # evita fallos por espacios/mayúsculas
    return (usuario or "").strip().lower()

def seed_usuarios_iniciales():
    """
    IMPORTANTE: solo sembrar si la tabla está vacía.
    Así NO dependes de reruns.
    """
    conn = db_connect()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM usuarios")
    n = c.fetchone()[0]
    conn.close()

    if n > 0:
        return

    usuarios = [
        "admin","rpuerta","pquiros","ivillaseñor",
        "jriestra","ggarcia","jmhernandez",
        "flobeiras","mromero"
    ]
    for u in usuarios:
        crear_usuario_si_no_existe(u, "Orlegi2025", "admin" if u == "admin" else "user")

init_db()
seed_usuarios_iniciales()

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

    if logo_base64:
        st.markdown(
            f"""
            <div style="text-align:center; margin-bottom:1.5rem;">
                <img src="data:image/png;base64,{logo_base64}" style="width:260px;">
            </div>
            """,
            unsafe_allow_html=True
        )

    usuario_raw = st.text_input("Usuario")
    contrasena = st.text_input("Contraseña", type="password")

    if st.button("Acceder"):
        usuario = normalizar_usuario(usuario_raw)
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
        u = st.session_state.usuario_actual
        if not verificar_login(u, actual):
            st.error("Contraseña actual incorrecta")
        elif nueva != confirmar:
            st.error("No coinciden")
        elif len(nueva) < 8:
            st.error("Mínimo 8 caracteres")
        else:
            cambiar_password(u, nueva)
            st.session_state.forzar_cambio = False
            st.success("Contraseña actualizada correctamente")
            st.rerun()

    st.stop()

# =========================
# PANEL NORMAL
# =========================
if logo_base64:
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
