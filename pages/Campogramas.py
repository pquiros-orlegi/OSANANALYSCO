import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from mplsoccer import Pitch
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode
import base64
from matplotlib.patches import FancyBboxPatch, Rectangle


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
        background: transparent !important;  /* 👈 que no tape la imagen */
    }}

    /* Contenedor principal del contenido */
    .main .block-container {{
        position: relative;
        z-index: 2;               /* por encima del fondo */
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
        opacity: 0.99;            /* igual que el login; sube a 0.2 si lo quieres más fuerte */
        z-index: 0;               /* detrás del contenido, pero visible */
    }}
    </style>

    <div class="background-image-rating"></div>
    """,
    unsafe_allow_html=True
)

# =========================
# ⚠️ (OPCIONAL) PROTEGER CON LOGIN DE home.py
# =========================
if "logueado" in st.session_state and not st.session_state.logueado:
    st.error("Debes iniciar sesión en la página principal (home.py) para acceder a este panel.")
    st.stop()



import os
import zipfile
import pandas as pd
import streamlit as st

# =========================
# CARGA AUTOMÁTICA DEL DATASET (desde 4 ZIP)
# =========================
@st.cache_data
def load_data():
    base_dir = "data"  # carpeta dentro de tu repo / proyecto
    zip_files = [
        "noviembre_2025_temporada_2022.zip",
        "noviembre_2025_temporada_2023.zip",
        "noviembre_2025_temporada_2024.zip",
        "noviembre_2025_temporada_2025.zip",
    ]

    dfs = []

    for zname in zip_files:
        zpath = os.path.join(base_dir, zname)

        # Leer el primer CSV que haya dentro del zip (sin extraer a disco)
        with zipfile.ZipFile(zpath, "r") as z:
            csv_names = [n for n in z.namelist() if n.lower().endswith(".csv")]
            if not csv_names:
                raise ValueError(f"El zip {zname} no contiene ningún CSV")
            csv_inside = csv_names[0]

            with z.open(csv_inside) as f:
                df_part = pd.read_csv(
                    f,
                    sep=None,
                    engine="python",
                    encoding="utf-8-sig"
                )
                dfs.append(df_part)

    df = pd.concat(dfs, ignore_index=True)

    # Normalizamos Fin de contrato a string SIEMPRE
    if "Fin de contrato" in df.columns:
        df["Fin de contrato"] = df["Fin de contrato"].astype(str)

    return df



# =========================
# LISTA GLOBAL DE TODAS LAS COLUMNAS DE SCORE (PERCENTILES)
# =========================
COLUMNAS_SCORE = [
    # Porteros
    "Score GK Portero",
    "Score GK Atajador",
    "Score GK Juego de Pies",
    "Score GK Total",
    # Laterales
    "Score Lateral Genérico",
    "Score Lateral Defensivo",
    "Score Lateral Ofensivo",
    "Score Lateral Total",
    # Centrales
    "Score Central Genérico",
    "Score Central Defensivo",
    "Score Central Combinativo",
    "Score Central Total",
    # MCs
    "Score MC Genérico",
    "Score MC Contención",
    "Score MC Box-to-Box",
    "Score MC Ofensivo",
    # Extremos
    "Score Extremo Genérico",
    "Score Extremo Wide Out",
    "Score Extremo Incorporación",
    "Score Extremo Combinativo",
    "Score Extremos Total",
    # Delanteros
    "Score Delantero",
    "Score 9",
    "Score Segundo Delantero",
    "Score Total",
]

# =========================
# LISTAS DE SCORES POR ROL (para percentiles por posición)
# =========================
SCORES_GK = [
    "Score GK Portero",
    "Score GK Atajador",
    "Score GK Juego de Pies",
    "Score GK Total",
]

SCORES_LATERAL = [
    "Score Lateral Genérico",
    "Score Lateral Defensivo",
    "Score Lateral Ofensivo",
    "Score Lateral Total",
]

SCORES_CENTRAL = [
    "Score Central Genérico",
    "Score Central Defensivo",
    "Score Central Combinativo",
    "Score Central Total",
]

SCORES_MC = [
    "Score MC Genérico",
    "Score MC Contención",
    "Score MC Box-to-Box",
    "Score MC Ofensivo",
]

SCORES_EXTREMO = [
    "Score Extremo Genérico",
    "Score Extremo Wide Out",
    "Score Extremo Incorporación",
    "Score Extremo Combinativo",
    "Score Extremos Total",
]

SCORES_DELANTERO = [
    "Score Delantero",
    "Score 9",
    "Score Segundo Delantero",
    "Score Total",
]


# =========================
# MATCH ROBUSTO DE POSICIONES
# =========================
def match_posicion(valor, codigos_validos):
    """
    Devuelve True si algún token de la cadena coincide o empieza por
    alguno de los códigos (POR, GK, etc.).
    Ejemplos válidos: "POR", "POR1", "GK", "GK2", "POR / DFC".
    """
    if pd.isna(valor):
        return False
    text = str(valor).upper()
    for sep in ["/", "-", ",", "|", ";"]:
        text = text.replace(sep, " ")
    tokens = [t.strip() for t in text.split() if t.strip()]
    for tok in tokens:
        for cod in codigos_validos:
            if tok == cod or tok.startswith(cod):
                return True
    return False


# =========================
# HELPER: CONVERTIR SCORES A PERCENTILES POR RANK (0-100, PASOS DE 5)
#  👉 CREA COLUMNAS NUEVAS: "Percentil {Score ...}"
#  👉 NO USA MINUTOS, SOLO RANK DENTRO DEL SUBSET QUE LE PASES
# =========================
def aplicar_percentiles(df: pd.DataFrame, columnas, step: int = 5) -> pd.DataFrame:
    """
    Crea columnas nuevas de percentil para cada columna en `columnas`.

    - Percentil basado en rank (el mejor valor del subset siempre tiene 100).
    - Se discretiza en saltos de `step` (por defecto 5): 0, 5, 10, ..., 100.
    - No usa minutos ni filtros adicionales; eso se hace fuera.
    """
    df = df.copy()

    for col in columnas:
        if col not in df.columns:
            continue

        serie = pd.to_numeric(df[col], errors="coerce")
        if serie.dropna().empty:
            continue

        new_col = f"Percentil {col}"

        # rank percentil 0-100 dentro del subset
        pct = (serie.rank(pct=True) * 100).round()

        # discretización en saltos de `step`
        bucket = (pct // step) * step
        df[new_col] = bucket.clip(0, 100).astype("Int64")

    return df


# =========================
# JS PARA COLOREAR CELDAS DE SCORE (>=85 VERDE) - GENERALES
# =========================
CELLSTYLE_SCORE_JS = JsCode("""
function(params) {
  const baseStyle = {
    backgroundColor: '#09202E',
    color: 'white',
    textAlign: 'center',
    verticalAlign: 'middle',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    border: '1px solid #ffffff22',
    padding: '0px',
    fontSize: '10px'
  };
  if (params.value >= 85) {
    return {
      backgroundColor: '#90EE90',
      color: 'black',
      textAlign: 'center',
      verticalAlign: 'middle',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      border: '1px solid #ffffff22',
      padding: '0px',
      fontSize: '10px'
    };
  }
  return baseStyle;
}
""")


# =========================
# ESTILOS ESPECIALES SCORE GK (>= 85) CON COLOR DEL GRUPO
# =========================
CELLSTYLE_SCORE_GK_PORTERO_JS = JsCode("""
function(params) {
  const baseStyle = {
    backgroundColor: '#09202E',
    color: 'white',
    textAlign: 'center',
    verticalAlign: 'middle',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    border: '1px solid #ffffff22',
    padding: '0px',
    fontSize: '10px'
  };
  if (params.value >= 85) {
    return {
      backgroundColor: 'rgb(80,90,255)',
      color: 'white',
      textAlign: 'center',
      verticalAlign: 'middle',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      border: '1px solid #ffffff22',
      padding: '0px',
      fontSize: '10px'
    };
  }
  return baseStyle;
}
""")

CELLSTYLE_SCORE_GK_ATAJADOR_JS = JsCode("""
function(params) {
  const baseStyle = {
    backgroundColor: '#09202E',
    color: 'white',
    textAlign: 'center',
    verticalAlign: 'middle',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    border: '1px solid #ffffff22',
    padding: '0px',
    fontSize: '10px'
  };
  if (params.value >= 85) {
    return {
      backgroundColor: 'rgb(255,50,0)',
      color: 'white',
      textAlign: 'center',
      verticalAlign: 'middle',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      border: '1px solid #ffffff22',
      padding: '0px',
      fontSize: '10px'
    };
  }
  return baseStyle;
}
""")

CELLSTYLE_SCORE_GK_PIES_JS = JsCode("""
function(params) {
  const baseStyle = {
    backgroundColor: '#09202E',
    color: 'white',
    textAlign: 'center',
    verticalAlign: 'middle',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    border: '1px solid #ffffff22',
    padding: '0px',
    fontSize: '10px'
  };
  if (params.value >= 85) {
    return {
      backgroundColor: 'rgb(50,255,50)',
      color: 'white',
      textAlign: 'center',
      verticalAlign: 'middle',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      border: '1px solid #ffffff22',
      padding: '0px',
      fontSize: '10px'
    };
  }
  return baseStyle;
}
""")


# =========================
# ESTILOS ESPECIALES SCORE LATERALES (>= 85)
# =========================
CELLSTYLE_SCORE_LAT_GENERICO_JS = JsCode("""
function(params) {
  const baseStyle = {
    backgroundColor: '#09202E',
    color: 'white',
    textAlign: 'center',
    verticalAlign: 'middle',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    border: '1px solid #ffffff22',
    padding: '0px',
    fontSize: '10px'
  };
  if (params.value >= 85) {
    return {
      backgroundColor: 'rgb(80,90,255)',
      color: 'white',
      textAlign: 'center',
      verticalAlign: 'middle',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      border: '1px solid #ffffff22',
      padding: '0px',
      fontSize: '10px'
    };
  }
  return baseStyle;
}
""")

CELLSTYLE_SCORE_LAT_DEFENSIVO_JS = JsCode("""
function(params) {
  const baseStyle = {
    backgroundColor: '#09202E',
    color: 'white',
    textAlign: 'center',
    verticalAlign: 'middle',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    border: '1px solid #ffffff22',
    padding: '0px',
    fontSize: '10px'
  };
  if (params.value >= 85) {
    return {
      backgroundColor: 'rgb(255,50,0)',
      color: 'white',
      textAlign: 'center',
      verticalAlign: 'middle',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      border: '1px solid #ffffff22',
      padding: '0px',
      fontSize: '10px'
    };
  }
  return baseStyle;
}
""")

CELLSTYLE_SCORE_LAT_OFENSIVO_JS = JsCode("""
function(params) {
  const baseStyle = {
    backgroundColor: '#09202E',
    color: 'white',
    textAlign: 'center',
    verticalAlign: 'middle',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    border: '1px solid #ffffff22',
    padding: '0px',
    fontSize: '10px'
  };
  if (params.value >= 85) {
    return {
      backgroundColor: 'rgb(50,255,50)',
      color: 'white',
      textAlign: 'center',
      verticalAlign: 'middle',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      border: '1px solid #ffffff22',
      padding: '0px',
      fontSize: '10px'
    };
  }
  return baseStyle;
}
""")


# =========================
# ESTILOS ESPECIALES SCORE DFC (>= 85)
# =========================
CELLSTYLE_SCORE_DFC_GENERICO_JS = JsCode("""
function(params) {
  const baseStyle = {
    backgroundColor: '#09202E',
    color: 'white',
    textAlign: 'center',
    verticalAlign: 'middle',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    border: '1px solid #ffffff22',
    padding: '0px',
    fontSize: '10px'
  };
  if (params.value >= 85) {
    return {
      backgroundColor: 'rgb(80,90,255)',
      color: 'white',
      textAlign: 'center',
      verticalAlign: 'middle',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      border: '1px solid #ffffff22',
      padding: '0px',
      fontSize: '10px'
    };
  }
  return baseStyle;
}
""")

CELLSTYLE_SCORE_DFC_DEFENSIVO_JS = JsCode("""
function(params) {
  const baseStyle = {
    backgroundColor: '#09202E',
    color: 'white',
    textAlign: 'center',
    verticalAlign: 'middle',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    border: '1px solid #ffffff22',
    padding: '0px',
    fontSize: '10px'
  };
  if (params.value >= 85) {
    return {
      backgroundColor: 'rgb(255,50,0)',
      color: 'white',
      textAlign: 'center',
      verticalAlign: 'middle',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      border: '1px solid #ffffff22',
      padding: '0px',
      fontSize: '10px'
    };
  }
  return baseStyle;
}
""")

CELLSTYLE_SCORE_DFC_COMBINATIVO_JS = JsCode("""
function(params) {
  const baseStyle = {
    backgroundColor: '#09202E',
    color: 'white',
    textAlign: 'center',
    verticalAlign: 'middle',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    border: '1px solid #ffffff22',
    padding: '0px',
    fontSize: '10px'
  };
  if (params.value >= 85) {
    return {
      backgroundColor: 'rgb(50,255,50)',
      color: 'white',
      textAlign: 'center',
      verticalAlign: 'middle',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      border: '1px solid #ffffff22',
      padding: '0px',
      fontSize: '10px'
    };
  }
  return baseStyle;
}
""")


# =========================
# ESTILOS ESPECIALES SCORE MC (>= 85)
# =========================
CELLSTYLE_SCORE_MC_GENERICO_JS = JsCode("""
function(params) {
  const baseStyle = {
    backgroundColor: '#09202E',
    color: 'white',
    textAlign: 'center',
    verticalAlign: 'middle',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    border: '1px solid #ffffff22',
    padding: '0px',
    fontSize: '10px'
  };
  if (params.value >= 85) {
    return {
      backgroundColor: 'rgb(80,90,255)',
      color: 'white',
      textAlign: 'center',
      verticalAlign: 'middle',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      border: '1px solid #ffffff22',
      padding: '0px',
      fontSize: '10px'
    };
  }
  return baseStyle;
}
""")

CELLSTYLE_SCORE_MC_CONTENCION_JS = JsCode("""
function(params) {
  const baseStyle = {
    backgroundColor: '#09202E',
    color: 'white',
    textAlign: 'center',
    verticalAlign: 'middle',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    border: '1px solid #ffffff22',
    padding: '0px',
    fontSize: '10px'
  };
  if (params.value >= 85) {
    return {
      backgroundColor: 'rgb(255,50,0)',
      color: 'white',
      textAlign: 'center',
      verticalAlign: 'middle',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      border: '1px solid #ffffff22',
      padding: '0px',
      fontSize: '10px'
    };
  }
  return baseStyle;
}
""")

CELLSTYLE_SCORE_MC_OFENSIVO_JS = JsCode("""
function(params) {
  const baseStyle = {
    backgroundColor: '#09202E',
    color: 'white',
    textAlign: 'center',
    verticalAlign: 'middle',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    border: '1px solid #ffffff22',
    padding: '0px',
    fontSize: '10px'
  };
  if (params.value >= 85) {
    return {
      backgroundColor: 'rgb(50,255,50)',
      color: 'white',
      textAlign: 'center',
      verticalAlign: 'middle',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      border: '1px solid #ffffff22',
      padding: '0px',
      fontSize: '10px'
    };
  }
  return baseStyle;
}
""")

CELLSTYLE_SCORE_MC_B2B_JS = JsCode("""
function(params) {
  const baseStyle = {
    backgroundColor: '#09202E',
    color: 'white',
    textAlign: 'center',
    verticalAlign: 'middle',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    border: '1px solid #ffffff22',
    padding: '0px',
    fontSize: '10px'
  };
  if (params.value >= 85) {
    return {
      backgroundColor: 'rgb(180,90,255)',
      color: 'white',
      textAlign: 'center',
      verticalAlign: 'middle',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      border: '1px solid #ffffff22',
      padding: '0px',
      fontSize: '10px'
    };
  }
  return baseStyle;
}
""")


# =========================
# ESTILOS ESPECIALES SCORE EXTREMOS (>= 85)
# =========================
CELLSTYLE_SCORE_EXT_GENERICO_JS = JsCode("""
function(params) {
  const baseStyle = {
    backgroundColor: '#09202E',
    color: 'white',
    textAlign: 'center',
    verticalAlign: 'middle',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    border: '1px solid #ffffff22',
    padding: '0px',
    fontSize: '10px'
  };
  if (params.value >= 85) {
    return {
      backgroundColor: 'rgb(80,90,255)',
      color: 'white',
      textAlign: 'center',
      verticalAlign: 'middle',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      border: '1px solid #ffffff22',
      padding: '0px',
      fontSize: '10px'
    };
  }
  return baseStyle;
}
""")

CELLSTYLE_SCORE_EXT_WIDEOUT_JS = JsCode("""
function(params) {
  const baseStyle = {
    backgroundColor: '#09202E',
    color: 'white',
    textAlign: 'center',
    verticalAlign: 'middle',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    border: '1px solid #ffffff22',
    padding: '0px',
    fontSize: '10px'
  };
  if (params.value >= 85) {
    return {
      backgroundColor: 'rgb(50,255,50)',
      color: 'white',
      textAlign: 'center',
      verticalAlign: 'middle',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      border: '1px solid #ffffff22',
      padding: '0px',
      fontSize: '10px'
    };
  }
  return baseStyle;
}
""")

CELLSTYLE_SCORE_EXT_INCORPORACION_JS = JsCode("""
function(params) {
  const baseStyle = {
    backgroundColor: '#09202E',
    color: 'white',
    textAlign: 'center',
    verticalAlign: 'middle',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    border: '1px solid #ffffff22',
    padding: '0px',
    fontSize: '10px'
  };
  if (params.value >= 85) {
    return {
      backgroundColor: 'rgb(255,50,0)',
      color: 'white',
      textAlign: 'center',
      verticalAlign: 'middle',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      border: '1px solid #ffffff22',
      padding: '0px',
      fontSize: '10px'
    };
  }
  return baseStyle;
}
""")

CELLSTYLE_SCORE_EXT_COMBINATIVO_JS = JsCode("""
function(params) {
  const baseStyle = {
    backgroundColor: '#09202E',
    color: 'white',
    textAlign: 'center',
    verticalAlign: 'middle',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    border: '1px solid #ffffff22',
    padding: '0px',
    fontSize: '10px'
  };
  if (params.value >= 85) {
    return {
      backgroundColor: 'rgb(180,90,255)',
      color: 'white',
      textAlign: 'center',
      verticalAlign: 'middle',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      border: '1px solid #ffffff22',
      padding: '0px',
      fontSize: '10px'
    };
  }
  return baseStyle;
}
""")


# =========================
# ESTILOS ESPECIALES SCORE DELANTEROS (>= 85)
# =========================
CELLSTYLE_SCORE_DEL_DELANTERO_JS = JsCode("""
function(params) {
  const baseStyle = {
    backgroundColor: '#09202E',
    color: 'white',
    textAlign: 'center',
    verticalAlign: 'middle',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    border: '1px solid #ffffff22',
    padding: '0px',
    fontSize: '10px'
  };
  if (params.value >= 85) {
    return {
      backgroundColor: 'rgb(80,90,255)',
      color: 'white',
      textAlign: 'center',
      verticalAlign: 'middle',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      border: '1px solid #ffffff22',
      padding: '0px',
      fontSize: '10px'
    };
  }
  return baseStyle;
}
""")

CELLSTYLE_SCORE_DEL_9_JS = JsCode("""
function(params) {
  const baseStyle = {
    backgroundColor: '#09202E',
    color: 'white',
    textAlign: 'center',
    verticalAlign: 'middle',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    border: '1px solid #ffffff22',
    padding: '0px',
    fontSize: '10px'
  };
  if (params.value >= 85) {
    return {
      backgroundColor: 'rgb(255,50,0)',
      color: 'white',
      textAlign: 'center',
      verticalAlign: 'middle',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      border: '1px solid #ffffff22',
      padding: '0px',
      fontSize: '10px'
    };
  }
  return baseStyle;
}
""")

CELLSTYLE_SCORE_DEL_SEGUNDO_JS = JsCode("""
function(params) {
  const baseStyle = {
    backgroundColor: '#09202E',
    color: 'white',
    textAlign: 'center',
    verticalAlign: 'middle',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    border: '1px solid #ffffff22',
    padding: '0px',
    fontSize: '10px'
  };
  if (params.value >= 85) {
    return {
      backgroundColor: 'rgb(50,255,50)',
      color: 'white',
      textAlign: 'center',
      verticalAlign: 'middle',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      border: '1px solid #ffffff22',
      padding: '0px',
      fontSize: '10px'
    };
  }
  return baseStyle;
}
""")


# =========================
# HELPER: CREAR JS DEGRADADO POR COLUMNA (TIPO CMAP)
# =========================
def crear_cmap_js(cmap: str, vmin: float, vmax: float, invert: bool = False) -> JsCode:
    inv = "true" if invert else "false"
    return JsCode(f"""
function(params) {{
    const baseStyle = {{
        backgroundColor: '#09202E',
        color: 'white',
        textAlign: 'center',
        verticalAlign: 'middle',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        border: '1px solid #ffffff22',
        padding: '0px',
        fontSize: '10px'
    }};
    if (params.value == null || isNaN(params.value)) return baseStyle;

    var v = Number(params.value);
    var min = {vmin};
    var max = {vmax};
    if (max === min) return baseStyle;

    var t = (v - min) / (max - min);
    if (t < 0) t = 0;
    if (t > 1) t = 1;

    if ({inv}) {{
        t = 1 - t;   // 👈 invierte el gradiente
    }}

    var r, g, b;
    if ("{cmap}" === "Blues") {{
        var light = 230 - Math.round(t * 150);
        r = light; g = light + 10; b = 255;
    }} else if ("{cmap}" === "Reds") {{
        r = 255; g = 230 - Math.round(t * 180); b = g;
    }} else if ("{cmap}" === "Oranges") {{
        r = 255; g = 200 - Math.round(t * 150); b = 0;
    }} else if ("{cmap}" === "Greens") {{
        g = 255; r = 230 - Math.round(t * 180); b = r;
    }} else if ("{cmap}" === "Purples") {{
        r = 230 - Math.round(t * 80);
        g = 220 - Math.round(t * 160);
        b = 255;
    }} else {{
        return baseStyle;
    }}

    var bg = 'rgb(' + r + ',' + g + ',' + b + ')';
    return {{
        backgroundColor: bg,
        color: 'black',
        textAlign: 'center',
        verticalAlign: 'middle',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        border: '1px solid #ffffff22',
        padding: '0px',
        fontSize: '10px'
    }};
}}
""")


import re

def limpiar_header(colname: str) -> str:
    return re.sub(r"\s*\(.*?\)", "", str(colname)).strip()






# =========================
# HELPER: MOSTRAR TABLA CON AgGrid
# =========================
def mostrar_tabla_aggrid(df_tabla: pd.DataFrame, key: str, df_base: pd.DataFrame = None):
    """
    Todas las columnas a 200px (estable local/web) manteniendo TODOS los gradientes y estilos.
    """
    tabla = df_tabla.copy()

    # 🔢 métricas con paréntesis → 2 decimales
    for col in tabla.columns:
        if "(" in col and ")" in col:
            tabla[col] = pd.to_numeric(tabla[col], errors="coerce").round(2)

    if df_base is None:
        df_base = tabla

    # --- Jugador primero ---
    if "Jugador" in tabla.columns:
        cols = ["Jugador"] + [c for c in tabla.columns if c != "Jugador"]
        tabla = tabla[cols]

    if "Minutos jugados" in tabla.columns:
        tabla["Minutos jugados"] = pd.to_numeric(
            tabla["Minutos jugados"], errors="coerce"
        ).astype("Int64")

    gb = GridOptionsBuilder.from_dataframe(
        tabla,
        enableRowGroup=True,
        enableValue=True,
        enablePivot=True
    )
    

    # ✅ Estilos base (los tuyos)
    base_cell_style = {
        'backgroundColor': '#09202E',
        'color': 'white',
        'textAlign': 'center',
        'verticalAlign': 'middle',
        'border': '1px solid #ffffff22',
        'padding': '0px',
        'fontSize': '10px'
    }
    base_header_style = {
        'backgroundColor': '#09202E',
        'color': 'white',
        'fontWeight': 'bold',
        'borderBottom': '1px solid #ffffff22',
        'fontSize': '11px',
        'padding': '0px',
        'textAlign': 'center',
        'verticalAlign': 'middle'
    }

    # ✅ TODAS las columnas a 200px (y que no cambien)
    gb.configure_default_column(
        wrapText=False,
        autoHeight=False,
        resizable=True,
        sortable=True,
        filter=True,
        width=200,
        minWidth=200,
        maxWidth=200,
        cellStyle=base_cell_style,
        headerStyle=base_header_style
    )

    # Fijar Jugador a la izquierda (también 200px)
    if "Jugador" in tabla.columns:
        gb.configure_column(
            "Jugador",
            pinned="left",
            lockPinned=True,
            width=200,
            minWidth=200,
            maxWidth=200
        )

    # Grid options estables (sin autosize)
    gb.configure_grid_options(
        suppressSizeToFit=True,
        suppressColumnVirtualisation=False,
        alwaysShowHorizontalScroll=True
    )

    # =========================
    # ✅ FIX: NEGATIVOS (menos = mejor) -> invert=True
    # =========================
    NEGATIVE_TOKENS = [
        "PÉRDIDAS", "PERDIDAS",
        "ACCIONES FALLIDAS",
        "FALLIDAS",
    ]

    def is_negative_metric(colname: str) -> bool:
        up = str(colname).upper()
        return any(tok in up for tok in NEGATIVE_TOKENS)

    # ====== Tus coloreados (igual que antes) ======
    cols_percentil_score = [c for c in tabla.columns if c.startswith("Percentil Score ")]
    for col in cols_percentil_score:
        gb.configure_column(col, cellStyle=CELLSTYLE_SCORE_JS)

    # ----- PORTEROS -----
    if key == "tabla_porteros":
        if "Percentil Score GK Portero" in tabla.columns:
            gb.configure_column("Percentil Score GK Portero", cellStyle=CELLSTYLE_SCORE_GK_PORTERO_JS)
        if "Percentil Score GK Atajador" in tabla.columns:
            gb.configure_column("Percentil Score GK Atajador", cellStyle=CELLSTYLE_SCORE_GK_ATAJADOR_JS)
        if "Percentil Score GK Juego de Pies" in tabla.columns:
            gb.configure_column("Percentil Score GK Juego de Pies", cellStyle=CELLSTYLE_SCORE_GK_PIES_JS)

        cols_portero = [c for c in tabla.columns if "(GK_PORTERO)" in c]
        for col in cols_portero:
            s = pd.to_numeric(df_base[col], errors="coerce")
            if not s.dropna().empty:
                gb.configure_column(col, cellStyle=crear_cmap_js("Blues", float(s.min()), float(s.max())))

        cols_ataj = [c for c in tabla.columns if "(GK_ATAJADOR)" in c]
        for col in cols_ataj:
            s = pd.to_numeric(df_base[col], errors="coerce")
            if not s.dropna().empty:
                gb.configure_column(col, cellStyle=crear_cmap_js("Oranges", float(s.min()), float(s.max())))

        cols_pies = [c for c in tabla.columns if "(GK_PIES)" in c]
        for col in cols_pies:
            s = pd.to_numeric(df_base[col], errors="coerce")
            if s.dropna().empty:
                continue
            vmin, vmax = float(s.min()), float(s.max())

            # ✅ aquí estaba el bug: "Greens_inv" -> invert=True
            if is_negative_metric(col):
                gb.configure_column(col, cellStyle=crear_cmap_js("Greens", vmin, vmax, invert=True))
            else:
                gb.configure_column(col, cellStyle=crear_cmap_js("Greens", vmin, vmax))

    # ----- LATERALES -----
    if key in ["tabla_laterales_izq", "tabla_laterales_der"]:
        if "Percentil Score Lateral Genérico" in tabla.columns:
            gb.configure_column("Percentil Score Lateral Genérico", cellStyle=CELLSTYLE_SCORE_LAT_GENERICO_JS)
        if "Percentil Score Lateral Defensivo" in tabla.columns:
            gb.configure_column("Percentil Score Lateral Defensivo", cellStyle=CELLSTYLE_SCORE_LAT_DEFENSIVO_JS)
        if "Percentil Score Lateral Ofensivo" in tabla.columns:
            gb.configure_column("Percentil Score Lateral Ofensivo", cellStyle=CELLSTYLE_SCORE_LAT_OFENSIVO_JS)

        cols_lat_gen = [c for c in tabla.columns if "(LAT_GENERICO)" in c]
        for col in cols_lat_gen:
            s = pd.to_numeric(df_base[col], errors="coerce")
            if not s.dropna().empty:
                gb.configure_column(col, cellStyle=crear_cmap_js("Blues", float(s.min()), float(s.max())))

        cols_lat_def = [c for c in tabla.columns if "(LAT_DEFENSIVO)" in c]
        for col in cols_lat_def:
            s = pd.to_numeric(df_base[col], errors="coerce")
            if not s.dropna().empty:
                gb.configure_column(col, cellStyle=crear_cmap_js("Reds", float(s.min()), float(s.max())))

        cols_lat_of = [c for c in tabla.columns if "(LAT_OFENSIVO)" in c]
        for col in cols_lat_of:
            s = pd.to_numeric(df_base[col], errors="coerce")
            if s.dropna().empty:
                continue
            vmin, vmax = float(s.min()), float(s.max())

            # ✅ bug fix aquí también
            if is_negative_metric(col):
                gb.configure_column(col, cellStyle=crear_cmap_js("Greens", vmin, vmax, invert=True))
            else:
                gb.configure_column(col, cellStyle=crear_cmap_js("Greens", vmin, vmax))

    # ----- DFC -----
    if key in ["tabla_dfc_izq", "tabla_dfc_der"]:
        if "Percentil Score Central Genérico" in tabla.columns:
            gb.configure_column("Percentil Score Central Genérico", cellStyle=CELLSTYLE_SCORE_DFC_GENERICO_JS)
        if "Percentil Score Central Defensivo" in tabla.columns:
            gb.configure_column("Percentil Score Central Defensivo", cellStyle=CELLSTYLE_SCORE_DFC_DEFENSIVO_JS)
        if "Percentil Score Central Combinativo" in tabla.columns:
            gb.configure_column("Percentil Score Central Combinativo", cellStyle=CELLSTYLE_SCORE_DFC_COMBINATIVO_JS)

        cols_dfc_gen = [c for c in tabla.columns if "(DFC_GENERICO)" in c]
        for col in cols_dfc_gen:
            s = pd.to_numeric(df_base[col], errors="coerce")
            if not s.dropna().empty:
                gb.configure_column(col, cellStyle=crear_cmap_js("Blues", float(s.min()), float(s.max())))

        cols_dfc_def = [c for c in tabla.columns if "(DFC_DEFENSIVO)" in c]
        for col in cols_dfc_def:
            s = pd.to_numeric(df_base[col], errors="coerce")
            if not s.dropna().empty:
                gb.configure_column(col, cellStyle=crear_cmap_js("Reds", float(s.min()), float(s.max())))

        cols_dfc_comb = [c for c in tabla.columns if "(DFC_COMBINATIVO)" in c]
        for col in cols_dfc_comb:
            s = pd.to_numeric(df_base[col], errors="coerce")
            if s.dropna().empty:
                continue
            vmin, vmax = float(s.min()), float(s.max())

            # ✅ bug fix aquí también
            if is_negative_metric(col):
                gb.configure_column(col, cellStyle=crear_cmap_js("Greens", vmin, vmax, invert=True))
            else:
                gb.configure_column(col, cellStyle=crear_cmap_js("Greens", vmin, vmax))

    # ----- MC -----
    if key in ["tabla_mc_contencion", "tabla_mc_box", "tabla_mc_ofensivo"]:
        if "Percentil Score MC Genérico" in tabla.columns:
            gb.configure_column("Percentil Score MC Genérico", cellStyle=CELLSTYLE_SCORE_MC_GENERICO_JS)
        if "Percentil Score MC Contención" in tabla.columns:
            gb.configure_column("Percentil Score MC Contención", cellStyle=CELLSTYLE_SCORE_MC_CONTENCION_JS)
        if "Percentil Score MC Ofensivo" in tabla.columns:
            gb.configure_column("Percentil Score MC Ofensivo", cellStyle=CELLSTYLE_SCORE_MC_OFENSIVO_JS)
        if "Percentil Score MC Box-to-Box" in tabla.columns:
            gb.configure_column("Percentil Score MC Box-to-Box", cellStyle=CELLSTYLE_SCORE_MC_B2B_JS)

        cols_mc_gen = [c for c in tabla.columns if "(MC_GENERICO)" in c]
        for col in cols_mc_gen:
            s = pd.to_numeric(df_base[col], errors="coerce")
            if not s.dropna().empty:
                gb.configure_column(col, cellStyle=crear_cmap_js("Blues", float(s.min()), float(s.max())))

        cols_mc_cont = [c for c in tabla.columns if "(MC_CONTENCION)" in c]
        for col in cols_mc_cont:
            s = pd.to_numeric(df_base[col], errors="coerce")
            if not s.dropna().empty:
                gb.configure_column(col, cellStyle=crear_cmap_js("Reds", float(s.min()), float(s.max())))

        cols_mc_of = [c for c in tabla.columns if "(MC_OFENSIVO)" in c]
        for col in cols_mc_of:
            s = pd.to_numeric(df_base[col], errors="coerce")
            if not s.dropna().empty:
                gb.configure_column(col, cellStyle=crear_cmap_js("Greens", float(s.min()), float(s.max())))

        cols_mc_b2b = [c for c in tabla.columns if "(MC_B2B)" in c]
        for col in cols_mc_b2b:
            s = pd.to_numeric(df_base[col], errors="coerce")
            if not s.dropna().empty:
                gb.configure_column(col, cellStyle=crear_cmap_js("Purples", float(s.min()), float(s.max())))

    # ----- EXTREMOS -----
    if key in ["tabla_extremos_izq", "tabla_extremos_der"]:
        if "Percentil Score Extremo Genérico" in tabla.columns:
            gb.configure_column("Percentil Score Extremo Genérico", cellStyle=CELLSTYLE_SCORE_EXT_GENERICO_JS)
        if "Percentil Score Extremo Wide Out" in tabla.columns:
            gb.configure_column("Percentil Score Extremo Wide Out", cellStyle=CELLSTYLE_SCORE_EXT_WIDEOUT_JS)
        if "Percentil Score Extremo Incorporación" in tabla.columns:
            gb.configure_column("Percentil Score Extremo Incorporación", cellStyle=CELLSTYLE_SCORE_EXT_INCORPORACION_JS)
        if "Percentil Score Extremo Combinativo" in tabla.columns:
            gb.configure_column("Percentil Score Extremo Combinativo", cellStyle=CELLSTYLE_SCORE_EXT_COMBINATIVO_JS)

        cols_ext_gen = [c for c in tabla.columns if "(EXT_GENERICO)" in c]
        for col in cols_ext_gen:
            s = pd.to_numeric(df_base[col], errors="coerce")
            if not s.dropna().empty:
                gb.configure_column(col, cellStyle=crear_cmap_js("Blues", float(s.min()), float(s.max())))

        cols_ext_w = [c for c in tabla.columns if "(EXT_WIDEOUT)" in c]
        for col in cols_ext_w:
            s = pd.to_numeric(df_base[col], errors="coerce")
            if not s.dropna().empty:
                gb.configure_column(col, cellStyle=crear_cmap_js("Greens", float(s.min()), float(s.max())))

        cols_ext_inc = [c for c in tabla.columns if "(EXT_INCORPORACION)" in c]
        for col in cols_ext_inc:
            s = pd.to_numeric(df_base[col], errors="coerce")
            if not s.dropna().empty:
                gb.configure_column(col, cellStyle=crear_cmap_js("Reds", float(s.min()), float(s.max())))

        cols_ext_comb = [c for c in tabla.columns if "(EXT_COMBINATIVO)" in c]
        for col in cols_ext_comb:
            s = pd.to_numeric(df_base[col], errors="coerce")
            if not s.dropna().empty:
                gb.configure_column(col, cellStyle=crear_cmap_js("Purples", float(s.min()), float(s.max())))

    # ----- DELANTEROS -----
    if key == "tabla_delanteros":
        if "Percentil Score Delantero" in tabla.columns:
            gb.configure_column("Percentil Score Delantero", cellStyle=CELLSTYLE_SCORE_DEL_DELANTERO_JS)
        if "Percentil Score 9" in tabla.columns:
            gb.configure_column("Percentil Score 9", cellStyle=CELLSTYLE_SCORE_DEL_9_JS)
        if "Percentil Score Segundo Delantero" in tabla.columns:
            gb.configure_column("Percentil Score Segundo Delantero", cellStyle=CELLSTYLE_SCORE_DEL_SEGUNDO_JS)

        cols_del = [c for c in tabla.columns if "(DEL_DELANTERO)" in c]
        for col in cols_del:
            s = pd.to_numeric(df_base[col], errors="coerce")
            if not s.dropna().empty:
                gb.configure_column(col, cellStyle=crear_cmap_js("Blues", float(s.min()), float(s.max())))

    cols_del9 = [c for c in tabla.columns if "(DEL_9)" in c]
    inv_del9_tokens = ["xG por Goles sin Penaltis"]
    for col in cols_del9:
        s = pd.to_numeric(df_base[col], errors="coerce")
        if s.dropna().empty:
            continue
        vmin, vmax = float(s.min()), float(s.max())
        if any(tok in col for tok in inv_del9_tokens):
            gb.configure_column(col, cellStyle=crear_cmap_js("Reds", vmin, vmax, invert=True))
        else:
            gb.configure_column(col, cellStyle=crear_cmap_js("Reds", vmin, vmax))

    grid_options = gb.build()

        # =========================
    # Limpieza de headers (quitar lo que hay entre paréntesis)
    # =========================
    for coldef in grid_options.get("columnDefs", []):
        field = coldef.get("field")
        if field:
            coldef["headerName"] = limpiar_header(field)


    # ❌ NO autosize (porque queremos 200 fijo)
    num_rows = len(tabla)
    grid_height = 60 + 30 * min(num_rows, 10)

    AgGrid(
        tabla,
        gridOptions=grid_options,
        theme="streamlit",
        fit_columns_on_grid_load=False,
        allow_unsafe_jscode=True,
        enable_enterprise_modules=False,
        reload_data=False,
        update_mode='NO_UPDATE',
        data_return_mode='AS_INPUT',
        domLayout='normal',
        height=grid_height,
        key=key,
        custom_css={
            ".ag-root-wrapper": {
                "border": "none !important",
                "max-width": "100% !important",
                "margin": "0 auto",
                "overflow-x": "auto !important",
                "overflow-y": "auto !important"
            },
            ".ag-cell, .ag-header-cell-label": {
                "display": "flex !important",
                "align-items": "center !important",
                "justify-content": "center !important",
            },
            ".ag-theme-streamlit, .ag-root, .ag-cell, .ag-header-cell": {
                "font-family": "Arial, sans-serif !important"
            },
            ".ag-header-cell-label": {
                "white-space": "nowrap !important"
            },
            ".ag-cell": {
                "white-space": "nowrap !important",
                "line-height": "12px !important"
            },
            ".ag-theme-streamlit": {
                "width": "100% !important"
            }
        }
    )


import re

def limpiar_header(colname: str) -> str:
    """
    Elimina todo lo que esté entre paréntesis y limpia espacios.
    Ej: "% Pases (GK_PORTERO)" -> "% Pases"
    """
    return re.sub(r"\s*\(.*?\)", "", colname).strip()




# =========================
# HELPERS DE RANKING
# =========================
def rankings_defensivos(df_filtrado: pd.DataFrame):
    # helper: ordena priorizando el SCORE bruto;
    # si no existe, usa el percentil como backup.
    def sort_by_score(df_pos, score_col_name):
        if score_col_name in df_pos.columns:
            return df_pos.sort_values(score_col_name, ascending=False).copy()
        else:
            pct_col = f"Percentil {score_col_name}"
            if pct_col in df_pos.columns:
                return df_pos.sort_values(pct_col, ascending=False).copy()
            return df_pos.copy()

    # PORTEROS
    df_por = df_filtrado[
        df_filtrado["Pos"].apply(
            lambda v: match_posicion(v, {"POR", "GK", "PORTERO", "GOALKEEPER"})
        )
    ].copy()
    df_por = sort_by_score(df_por, "Score GK Total")

    # LATERAL IZQUIERDO
    df_li = df_filtrado[
        df_filtrado["Pos"].apply(lambda v: match_posicion(v, {"LI", "CAI"}))
    ].copy()
    df_li = sort_by_score(df_li, "Score Lateral Total")

    # DFC (pool común)
    df_dfc_pool = df_filtrado[
        df_filtrado["Pos"].apply(lambda v: match_posicion(v, {"DFC"}))
    ].copy()
    df_dfc_pool = sort_by_score(df_dfc_pool, "Score Central Total")

    # mismo split que tenías antes: uno sí, uno no
    df_dfc_der = df_dfc_pool.iloc[0::2].copy()
    df_dfc_izq = df_dfc_pool.iloc[1::2].copy()

    # LATERAL DERECHO
    df_ld = df_filtrado[
        df_filtrado["Pos"].apply(lambda v: match_posicion(v, {"LD", "CAD"}))
    ].copy()
    df_ld = sort_by_score(df_ld, "Score Lateral Total")

    # MC (pool para los 3 roles)
    df_mc_pool = df_filtrado[
        df_filtrado["Pos"].apply(lambda v: match_posicion(v, {"MCD", "MC", "MCO"}))
    ].copy()

    df_mc_contencion = sort_by_score(df_mc_pool.copy(), "Score MC Contención")
    df_mc_b2b       = sort_by_score(df_mc_pool.copy(), "Score MC Box-to-Box")
    df_mc_ofensivo  = sort_by_score(df_mc_pool.copy(), "Score MC Ofensivo")

    # EXTREMOS
    df_ei = df_filtrado[
        df_filtrado["Pos"].apply(lambda v: match_posicion(v, {"EI", "MI"}))
    ].copy()
    df_ei = sort_by_score(df_ei, "Score Extremos Total")

    df_ed = df_filtrado[
        df_filtrado["Pos"].apply(lambda v: match_posicion(v, {"ED", "MD"}))
    ].copy()
    df_ed = sort_by_score(df_ed, "Score Extremos Total")

    # DELANTEROS
    df_dc = df_filtrado[
        df_filtrado["Pos"].apply(lambda v: match_posicion(v, {"DC", "SDI", "SDD"}))
    ].copy()
    df_dc = sort_by_score(df_dc, "Score 9")

    rankings = {
        "Portero": df_por,
        "Lateral izquierdo": df_li,
        "DFC Izquierdo": df_dfc_izq,
        "DFC Derecho": df_dfc_der,
        "Lateral derecho": df_ld,
        "MC Contención": df_mc_contencion,
        "MC Box to Box": df_mc_b2b,
        "MC Ofensivo": df_mc_ofensivo,
        "Extremo Izquierdo": df_ei,
        "Extremo Derecho": df_ed,
        "Delantero": df_dc,
    }

    # este dict lo usas en otros sitios → lo dejo igual
    score_cols = {
        "Portero": "Score GK Total",
        "Lateral izquierdo": "Score Lateral Total",
        "DFC Izquierdo": "Score Central Total",
        "DFC Derecho": "Score Central Total",
        "Lateral derecho": "Score Lateral Total",
        "MC Contención": "Score MC Contención",
        "MC Box to Box": "Score MC Box-to-Box",
        "MC Ofensivo": "Score MC Ofensivo",
        "Extremo Izquierdo": "Score Extremos Total",
        "Extremo Derecho": "Score Extremos Total",
        "Delantero": "Score 9",
    }

    return rankings, score_cols



# =========================
# HELPER: CONSTRUIR POOL DE PERCENTILES (POR ROL)
# =========================
def construir_pool_percentiles(df, temporada_sel, categoria_sel, liga_sel):
    """
    Devuelve df_pool: jugadores de esa temporada / liga / categoría,
    con COLUMNAS_SCORE convertidos a percentiles (0-100, saltos de 5),
    pero calculados **por rol/posición**.

    Ejemplo:
      - Score GK Portero → percentil solo entre porteros.
      - Score 9 / Score Segundo Delantero → solo entre delanteros (DC/SDI/SDD).
    """
    df_scope = df.copy()

    if temporada_sel:
        df_scope = df_scope[df_scope["Temporada"] == temporada_sel]

    if categoria_sel:
        df_scope = df_scope[df_scope["Categoría_Liga"].isin(categoria_sel)]

    if liga_sel:
        df_scope = df_scope[df_scope["Nombre_Liga"].isin(liga_sel)]

    if df_scope.empty:
        return pd.DataFrame()

    # Base sin percentiles todavía
    df_pool = df_scope.copy()

    # Helper: aplicar percentiles a un subconjunto (máscara) y
    # copiar solo las columnas "Percentil ..." a df_pool
    def aplicar_en_subset(mask, score_cols):
        if not mask.any():
            return
        sub = df_scope[mask].copy()
        sub_pct = aplicar_percentiles(sub, score_cols, step=5)
        pct_cols = [c for c in sub_pct.columns if c.startswith("Percentil ")]
        if not pct_cols:
            return
        df_pool.loc[mask, pct_cols] = sub_pct[pct_cols]

    # ---- PORTEROS ----
    mask_gk = df_scope["Pos"].apply(
        lambda v: match_posicion(v, {"POR", "GK", "PORTERO", "GOALKEEPER"})
    )
    aplicar_en_subset(mask_gk, SCORES_GK)

    # ---- LATERALES (LI / LD / CAI / CAD) ----
    mask_lat = df_scope["Pos"].apply(
        lambda v: match_posicion(v, {"LI", "LD", "CAI", "CAD"})
    )
    aplicar_en_subset(mask_lat, SCORES_LATERAL)

    # ---- CENTRALES (DFC) ----
    mask_dfc = df_scope["Pos"].apply(
        lambda v: match_posicion(v, {"DFC"})
    )
    aplicar_en_subset(mask_dfc, SCORES_CENTRAL)

    # ---- MC (MCD / MC / MCO) ----
    mask_mc = df_scope["Pos"].apply(
        lambda v: match_posicion(v, {"MCD", "MC", "MCO"})
    )
    aplicar_en_subset(mask_mc, SCORES_MC)

    # ---- EXTREMOS (EI / MI / ED / MD) ----
    mask_ext = df_scope["Pos"].apply(
        lambda v: match_posicion(v, {"EI", "MI", "ED", "MD"})
    )
    aplicar_en_subset(mask_ext, SCORES_EXTREMO)

    # ---- DELANTEROS (DC / SDI / SDD) ----
    mask_del = df_scope["Pos"].apply(
        lambda v: match_posicion(v, {"DC", "SDI", "SDD"})
    )
    aplicar_en_subset(mask_del, SCORES_DELANTERO)

    return df_pool
def _pct_border_color(pct):
    if pct is None:
        return "#999999"
    try:
        p = float(pct)
    except:
        return "#999999"

    if p >= 80:
        return "#2aa84a"   # verde
    if p >= 50:
        return "#f2c200"   # amarillo
    return "#d7263d"       # rojo

def truncate_text(txt, max_chars: int):
    """
    Corta el texto para que NO se desborde.
    Ej: "Aaron Yaakobishvili" -> "Aaron Yaakob..."
    """
    if txt is None:
        return ""
    s = str(txt).strip()
    if len(s) <= max_chars:
        return s
    # deja hueco para "..."
    return s[: max(0, max_chars - 3)].rstrip() + "..."



def draw_position_table(
    ax, x, y, title, rows,
    width=30,
    row_h=3.6,
    pct_w=5.0,
    pad=0.55,
    title_gap=2.0,
):
    """
    rows = [(jugador, equipo, minutos, percentil), ...]
    """
    n = len(rows)
    if n == 0:
        return

    total_h = n * row_h

    # --- TÍTULO ARRIBA ---
    card_x = x - width / 2
    title_box = FancyBboxPatch(
        (card_x, y + total_h/2 + title_gap - 1.3),
        width,
        2.4,
        boxstyle="round,pad=0.25,rounding_size=0.9",
        linewidth=1.2,
        edgecolor="#0e2841",
        facecolor="#0e2841",
        zorder=1000,
        clip_on=False
    )
    ax.add_patch(title_box)

    ax.text(
        x,
        y + total_h/2 + title_gap,
        str(title).upper(),
        ha="center",
        va="center",
        fontsize=8.1,   # 👈 MÁS PEQUEÑO
        fontweight="bold",
        color="white",
        zorder=1001,
        clip_on=False
    )

    # --- TARJETA BASE ---
    card = FancyBboxPatch(
        (x - width/2, y - total_h/2),
        width, total_h,
        boxstyle="round,pad=0.28,rounding_size=1.0",
        linewidth=0.9,
        edgecolor="#00000022",
        facecolor="white",
        alpha=0.99,
        zorder=999,
        clip_on=False
    )
    ax.add_patch(card)

    # ===== Columnas: Jugador | Equipo | Minutos | Percentil =====
    x_left = x - width/2
    x_right = x + width/2

    mins_w = 7.0
    x_pct_left = x_right - pct_w
    x_mins_left = x_pct_left - mins_w
    x_team_right = x_mins_left

    # Separadores verticales
    for x_sep in [x_team_right, x_mins_left, x_pct_left]:
        ax.plot(
            [x_sep, x_sep],
            [y - total_h/2, y + total_h/2],
            color="#00000022",
            linewidth=1,
            zorder=1001,
            clip_on=False
        )

    # Filas
    top_y = y + total_h/2
    for i, (jug, eq, mins, pct) in enumerate(rows):
        y_row_bottom = top_y - (i + 1) * row_h
        y_row_center = y_row_bottom + row_h / 2

        # Separador horizontal
        ax.plot(
            [x_left, x_right],
            [y_row_bottom, y_row_bottom],
            color="#00000022",
            linewidth=1,
            zorder=1001,
            clip_on=False
        )

        # Jugador
        ax.text(
            x_left + pad,
            y_row_center,
            truncate_text(jug, 14),
            ha="left",
            va="center",
            fontsize=6.2,   # 👈 MÁS PEQUEÑO
            fontweight="bold",
            color="#111",
            zorder=1002,
            clip_on=False
        )

        # Equipo
        ax.text(
            x_team_right - pad,
            y_row_center,
            truncate_text(eq, 14),
            ha="right",
            va="center",
            fontsize=5.8,   # 👈 MÁS PEQUEÑO
            color="#111",
            zorder=1002,
            clip_on=False
        )

        # Minutos
        mins_txt = ""
        if mins is not None and mins != "" and pd.notna(mins):
            try:
                mins_txt = f"{int(mins)}"
            except:
                mins_txt = str(mins)

        ax.text(
            (x_mins_left + x_pct_left) / 2,
            y_row_center,
            mins_txt,
            ha="center",
            va="center",
            fontsize=5.8,   # 👈 MÁS PEQUEÑO
            color="#111",
            zorder=1002,
            clip_on=False
        )

        # Percentil
        border = _pct_border_color(pct)
        badge = FancyBboxPatch(
            (x_pct_left + 0.55, y_row_bottom + 0.55),
            pct_w - 1.10,
            row_h - 1.10,
            boxstyle="round,pad=0.12,rounding_size=0.55",
            linewidth=2.0,
            edgecolor=border,
            facecolor="white",
            zorder=1003,
            clip_on=False
        )
        ax.add_patch(badge)

        ax.text(
            x_pct_left + pct_w / 2,
            y_row_center,
            "" if pct is None else str(int(pct)),
            ha="center",
            va="center",
            fontsize=7.0,   # 👈 MÁS PEQUEÑO
            fontweight="bold",
            color="#111",
            zorder=1004,
            clip_on=False
        )






def dibujar_campograma_defensivo(rankings, score_cols, temporada, liga_str):

    pitch = Pitch(
        pitch_type="statsbomb",
        pitch_color="#d0f0c0",
        line_color="black"
    )
    fig, ax = pitch.draw(figsize=(12, 8))
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    fig.patch.set_alpha(0)

    # ✅ MÁRGENES EXTRA para que NO SE CORTE nada
    # statsbomb suele ser x: 0-120, y:0-80
    ax.set_xlim(-6, 126)
    ax.set_ylim(-6, 86)

    posiciones_campo = {
        "Portero": (5, 40),
        "Lateral izquierdo": (25, 75),
        "DFC Izquierdo": (25, 55),
        "DFC Derecho": (25, 25),
        "Lateral derecho": (25, 2),
        "MC Contención": (60, 20),
        "MC Box to Box": (60, 60),
        "MC Ofensivo": (75, 40),
        "Extremo Izquierdo": (100, 75),
        "Delantero": (110, 40),
        "Extremo Derecho": (100, 2),
    }

    if all(df_pos.empty for df_pos in rankings.values()):
        ax.set_title(
            f"Sin datos (alineación completa) — {temporada} | {liga_str}",
            fontsize=14,
            fontweight="bold",
            color="white",
        )
        return fig

    for pos_nombre, df_pos in rankings.items():
        if df_pos.empty or pos_nombre not in posiciones_campo:
            continue

        x, y = posiciones_campo[pos_nombre]

        score_col = score_cols.get(pos_nombre)
        pct_col = f"Percentil {score_col}" if score_col else None

        top_df = df_pos.head(3)

        rows = []
        for _, r in top_df.iterrows():
            jugador = r.get("Jugador", "")
            equipo = r.get("Equipo", "")
            mins = r.get("Minutos jugados", None)

            pct = None
            if pct_col and pct_col in top_df.columns:
                val = r.get(pct_col, None)
                if pd.notna(val):
                    pct = int(val)

            rows.append((jugador, equipo, mins, pct))


        # ✅ Caja pequeña + título arriba
        draw_position_table(
            ax=ax,
            x=x, y=y,
            title=pos_nombre,
            rows=rows,
            width=30,     # 👈 más pequeña
            row_h=3.6,    # 👈 más compacta
            pct_w=5.0
        )

    ax.set_title(
        f"Alineación completa — {temporada} | {liga_str}",
        fontsize=14,
        fontweight="bold",
        color="white"
    )

    return fig




# =========================
# FUNCIÓN PRINCIPAL
# =========================
def app():
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 0.5rem;
            padding-bottom: 0.5rem;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    st.header("Campogramas y Rankings por Posición")

    df = load_data()

    # ====== SIDEBAR FILTROS ======
    st.sidebar.subheader("Filtros")

    # === Temporada (por defecto 2025) ===
    temporadas = sorted(df["Temporada"].dropna().unique())
    default_index = 0
    for i, t in enumerate(temporadas):
        if str(t) == "2025":
            default_index = i
            break

    temporada_sel = st.sidebar.selectbox("Temporada", temporadas, index=default_index)

    # ========= Selección Categoría_Liga (afecta a percentiles) =========
    if "Categoría_Liga" in df.columns and df["Categoría_Liga"].notna().any():
        opciones_categoria = sorted(df[df["Temporada"] == temporada_sel]["Categoría_Liga"].dropna().unique())
        categoria_sel = st.sidebar.multiselect(
            "Categoría de Liga",
            options=opciones_categoria,
            default=[]
        )
    else:
        categoria_sel = []

    # ========= Selección Liga / Competición (afecta a percentiles) =========
    if "Nombre_Liga" in df.columns and df["Nombre_Liga"].notna().any():
        opciones_liga = sorted(df[df["Temporada"] == temporada_sel]["Nombre_Liga"].dropna().unique())

        default_ligas = []
        for liga_nombre in opciones_liga:
            nombre_upper = str(liga_nombre).upper()
            if "LA LIGA" in nombre_upper or "LALIGA" in nombre_upper:
                default_ligas = [liga_nombre]
                break
        if not default_ligas and len(opciones_liga) > 0:
            default_ligas = [opciones_liga[0]]

        liga_sel = st.sidebar.multiselect(
            "Liga / Competición",
            options=opciones_liga,
            default=default_ligas
        )
    else:
        liga_sel = []

    # ======= POOL DE PERCENTILES (df_pool en session_state) =======
    if "df_pool_percentiles" not in st.session_state:
        df_pool = construir_pool_percentiles(df, temporada_sel, categoria_sel, liga_sel)
        st.session_state["df_pool_percentiles"] = df_pool
        st.session_state["pool_info"] = {
            "temporada": temporada_sel,
            "categoria": categoria_sel,
            "liga": liga_sel,
            "n_jugadores": len(df_pool),
        }

    if st.sidebar.button("Aplicar Percentiles"):
        df_pool = construir_pool_percentiles(df, temporada_sel, categoria_sel, liga_sel)
        st.session_state["df_pool_percentiles"] = df_pool
        st.session_state["pool_info"] = {
            "temporada": temporada_sel,
            "categoria": categoria_sel,
            "liga": liga_sel,
            "n_jugadores": len(df_pool),
        }

    df_pool = st.session_state.get("df_pool_percentiles", pd.DataFrame())
    pool_info = st.session_state.get("pool_info", {})

    if df_pool.empty:
        st.warning("No hay datos para esa combinación de Temporada / Categoría / Liga.")
        return

    # ========= Sliders de segmentación (NO afectan al cálculo de percentiles) =========
    # Rango de minutos sobre df_pool (que YA está percentilizado)
    min_minutos = int(df_pool["Minutos jugados"].min())
    max_minutos = int(df_pool["Minutos jugados"].max())

    # Inicializamos en session_state si no existe
    if "filtro_minutos" not in st.session_state:
        st.session_state["filtro_minutos"] = (min_minutos, max_minutos)

    minutos_min_sel, minutos_max_sel = st.sidebar.slider(
        "Minutos",
        min_value=min_minutos,
        max_value=max_minutos,
        step=90,
        key="filtro_minutos"
    )

    # Edad
    if "Edad" in df_pool.columns and df_pool["Edad"].notna().any():
        min_edad = int(df_pool["Edad"].min())
        max_edad = int(df_pool["Edad"].max())

        if "filtro_edad" not in st.session_state:
            st.session_state["filtro_edad"] = (min_edad, max_edad)

        edad_min_sel, edad_max_sel = st.sidebar.slider(
            "Edad",
            min_value=min_edad,
            max_value=max_edad,
            step=1,
            format="%d",
            key="filtro_edad"
        )
    else:
        min_edad, max_edad = None, None
        edad_min_sel, edad_max_sel = None, None

    # Valor mercado
    if "Valor_Mercado" in df_pool.columns and df_pool["Valor_Mercado"].notna().any():
        min_valor = int(df_pool["Valor_Mercado"].min())
        max_valor = int(df_pool["Valor_Mercado"].max())

        if "filtro_valor" not in st.session_state:
            st.session_state["filtro_valor"] = (min_valor, max_valor)

        valor_min_sel, valor_max_sel = st.sidebar.slider(
            "Valor de Mercado ",
            min_value=min_valor,
            max_value=max_valor,
            step=100,
            format="%d",
            key="filtro_valor"
        )
    else:
        min_valor, max_valor = None, None
        valor_min_sel, valor_max_sel = None, None

    # Nacionalidad
    if "Nacionalidad" in df_pool.columns and df_pool["Nacionalidad"].notna().any():
        opciones_nacionalidad = sorted(df_pool["Nacionalidad"].dropna().unique())

        if "filtro_nacionalidad" not in st.session_state:
            st.session_state["filtro_nacionalidad"] = []

        nacionalidad_sel = st.sidebar.multiselect(
            "Nacionalidad",
            options=opciones_nacionalidad,
            key="filtro_nacionalidad"
        )
    else:
        opciones_nacionalidad = []
        nacionalidad_sel = []

    # =========================
    # Equipo
    # =========================
    if "Equipo" in df_pool.columns and df_pool["Equipo"].notna().any():
        opciones_equipo = sorted(df_pool["Equipo"].dropna().unique())

        if "filtro_equipo" not in st.session_state:
            st.session_state["filtro_equipo"] = []

        equipo_sel = st.sidebar.multiselect(
            "Equipo",
            options=opciones_equipo,
            key="filtro_equipo"
        )
    else:
        opciones_equipo = []
        equipo_sel = []


    # ===== Función de callback para resetear filtros de segmentación =====
    def reset_segmentacion():
        # Minutos
        if "Minutos jugados" in df_pool.columns:
            min_m = int(df_pool["Minutos jugados"].min())
            max_m = int(df_pool["Minutos jugados"].max())
            st.session_state["filtro_minutos"] = (min_m, max_m)

        # Edad
        if "Edad" in df_pool.columns and df_pool["Edad"].notna().any():
            min_e = int(df_pool["Edad"].min())
            max_e = int(df_pool["Edad"].max())
            st.session_state["filtro_edad"] = (min_e, max_e)

        # Valor de mercado
        if "Valor_Mercado" in df_pool.columns and df_pool["Valor_Mercado"].notna().any():
            min_v = int(df_pool["Valor_Mercado"].min())
            max_v = int(df_pool["Valor_Mercado"].max())
            st.session_state["filtro_valor"] = (min_v, max_v)

        # Nacionalidad
        if "filtro_nacionalidad" in st.session_state:
            st.session_state["filtro_nacionalidad"] = []

                # Equipo
        if "filtro_equipo" in st.session_state:
            st.session_state["filtro_equipo"] = []


        # Fin de contrato
        if "Fin de contrato" in df_pool.columns and df_pool["Fin de contrato"].notna().any():
            fc_key = f"fin_contrato_{temporada_sel}_{hash(tuple(categoria_sel))}_{hash(tuple(liga_sel))}"
            if fc_key in st.session_state:
                st.session_state[fc_key] = []

    # Fin de contrato (sobre pool)
    if "Fin de contrato" in df_pool.columns and df_pool["Fin de contrato"].notna().any():
        opciones_fin_contrato = sorted(df_pool["Fin de contrato"].dropna().unique())

        fin_contrato_key = f"fin_contrato_{temporada_sel}_{hash(tuple(categoria_sel))}_{hash(tuple(liga_sel))}"

        if fin_contrato_key not in st.session_state:
            st.session_state[fin_contrato_key] = []

        fin_contrato_sel = st.sidebar.multiselect(
            "Fin de Contrato",
            options=opciones_fin_contrato,
            key=fin_contrato_key
        )

        fin_contrato_sel = [str(x) for x in fin_contrato_sel]
    else:
        opciones_fin_contrato = []
        fin_contrato_key = None
        fin_contrato_sel = []

    # 🔁 Botón en el sidebar, debajo de "Fin de contrato"
    st.sidebar.button(
        "🔁 Filtros",
        on_click=reset_segmentacion
    )

    # ====== SEGMENTACIÓN FINAL (NO recalcula percentiles) ======
    df_filtrado = df_pool.copy()

    df_filtrado = df_filtrado[
        (df_filtrado["Minutos jugados"] >= minutos_min_sel) &
        (df_filtrado["Minutos jugados"] <= minutos_max_sel)
    ]

    if edad_min_sel is not None:
        df_filtrado = df_filtrado[
            df_filtrado["Edad"].isna() |
            df_filtrado["Edad"].between(edad_min_sel, edad_max_sel)
        ]

    if valor_min_sel is not None:
        df_filtrado = df_filtrado[
            df_filtrado["Valor_Mercado"].isna() |
            df_filtrado["Valor_Mercado"].between(valor_min_sel, valor_max_sel)
        ]

    if fin_contrato_sel:
        df_filtrado = df_filtrado[
            df_filtrado["Fin de contrato"].isin(fin_contrato_sel)
        ]

    if nacionalidad_sel:
        df_filtrado = df_filtrado[
            df_filtrado["Nacionalidad"].isin(nacionalidad_sel)
        ]

        # Filtro por Equipo
    if equipo_sel:
        df_filtrado = df_filtrado[
            df_filtrado["Equipo"].isin(equipo_sel)
        ]



    if pool_info.get("liga"):
        liga_str = ", ".join(pool_info["liga"])
    else:
        liga_str = "Todas las ligas (pool temporada)"


    if df_filtrado.empty:
        st.warning("No hay datos tras segmentar por Minutos / Edad / Valor / Contrato.")
        return

    # ===== Rankings y 11 ideal =====
    rankings, score_cols = rankings_defensivos(df_filtrado)

    with st.expander("Recuento de jugadores por posición"):
        for k, v in rankings.items():
            st.write(f"{k}: {len(v)} jugadores")

    fig = dibujar_campograma_defensivo(rankings, score_cols, pool_info.get("temporada", temporada_sel), liga_str)
    st.pyplot(fig, use_container_width=True)

    # =========================
    # DETALLE POR POSICIÓN
    # =========================
    st.subheader("Listas por posición")

    # ===== PORTEROS =====
    columnas_gk = [
        "Temporada","Nombre_Liga","Jugador","Pos","Equipo","Categoría_Liga",
        "Edad","Nacionalidad","Altura","Valor_Mercado","Pie bueno",
        "Minutos jugados","Fin de contrato",

        "Score GK Portero",
        "Percentil Score GK Portero",
        "Score GK Atajador",
        "Percentil Score GK Atajador",
        "Score GK Juego de Pies",
        "Percentil Score GK Juego de Pies",
        "Score GK Total",
        "Percentil Score GK Total",

       'Goles Evitados (GK_PORTERO)', 'xG Recibidos por Gol (GK_PORTERO)',
       'Remates por Gol (GK_PORTERO)', '% Paradas (GK_PORTERO)',
       'Precisión en Centros (GK_PORTERO)', '% Pases con la Mano (GK_PORTERO)',
       'Distancia Media de Pases (GK_PORTERO)',
       '% Paradas Dentro del Área (GK_PORTERO)', '% Pases (GK_PORTERO)',
       '% Paradas Dentro del Área (GK_ATAJADOR)',
       '% Paradas Fuera del Área (GK_ATAJADOR)',
       'xG Parados / xG Recibidos (GK_ATAJADOR)',
       'Remates por Gol (GK_ATAJADOR)', 'xG Recibidos por Gol (GK_ATAJADOR)',
       '% Paradas (GK_ATAJADOR)', 'Goles Evitados (GK_ATAJADOR)',
       '% Pases en Campo Propio (GK_PIES)',
       'Acciones Fallidas en Campo Propio (GK_PIES)', 'Toques (GK_PIES)',
       'Progresión de Balón (GK_PIES)', 'xT Pases (GK_PIES)',
       'Pérdidas de Balón (GK_PIES)',
    ]
    st.subheader("Porteros")
    cols_exist = [c for c in columnas_gk if c in rankings["Portero"].columns]
    if cols_exist:
        if rankings["Portero"].empty:
            tabla_gk = pd.DataFrame(columns=cols_exist)
        else:
            tabla_gk = rankings["Portero"][cols_exist].head(10)

            
        mostrar_tabla_aggrid(tabla_gk, key="tabla_porteros", df_base=rankings["Portero"])
    else:
        st.write("No hay columnas de porteros disponibles en el dataset.")

    # ===== LATERALES =====
    columnas_laterales = [
        "Temporada","Nombre_Liga","Jugador","Pos","Equipo","Categoría_Liga",
        "Edad","Nacionalidad","Altura","Valor_Mercado","Pie bueno",
        "Minutos jugados","Fin de contrato",

        "Score Lateral Genérico",
        "Percentil Score Lateral Genérico",
        "Score Lateral Defensivo",
        "Percentil Score Lateral Defensivo",
        "Score Lateral Ofensivo",
        "Percentil Score Lateral Ofensivo",
        "Score Lateral Total",
        "Percentil Score Lateral Total",

        'Tackles/Fue Regateado (LAT_GENERICO)',
       'Intercepciones (LAT_GENERICO)', 'Recuperaciones (LAT_GENERICO)',
       'Presión Individual (LAT_GENERICO)',
       'Centros Completados (LAT_GENERICO)', 'Centros (LAT_GENERICO)',
       'Pérdidas Peligrosas (LAT_GENERICO)',
       'Acciones Fallidas en Campo Propio (LAT_GENERICO)',
       'xT en Juego (LAT_GENERICO)', 'Tackles con Éxito (LAT_DEFENSIVO)',
       'Tackles/Fue Regateado (LAT_DEFENSIVO)',
       '% Duelos por Bajo (LAT_DEFENSIVO)', 'Intercepciones (LAT_DEFENSIVO)',
       'Centros Interceptados (LAT_DEFENSIVO)',
       'Presión Individual (LAT_DEFENSIVO)',
       'Duelos Aéreos Defensivos Ganados (LAT_DEFENSIVO)',
       '% Duelos Aéreos Ganados (LAT_DEFENSIVO)', 'Profundidad (LAT_OFENSIVO)',
       'Profundidad en el Último ⅓ (LAT_OFENSIVO)', 'Centros (LAT_OFENSIVO)',
       'Peligro Esperado (xT) (LAT_OFENSIVO)',
       'Remates Fuera del Área (LAT_OFENSIVO)',
       'Regates Intentados (LAT_OFENSIVO)',
       '% Regates Completados (LAT_OFENSIVO)',
       'Acciones Fallidas en Campo Propio (LAT_OFENSIVO)',
       'xA de Centros (LAT_OFENSIVO)', 'Asistencias (LAT_OFENSIVO)',
    ]

    st.subheader("Laterales Izquierdos")
    cols_exist = [c for c in columnas_laterales if c in rankings["Lateral izquierdo"].columns]
    if cols_exist:
        if rankings["Lateral izquierdo"].empty:
            tabla_li = pd.DataFrame(columns=cols_exist)
        else:
            tabla_li = rankings["Lateral izquierdo"][cols_exist].head(10)
        mostrar_tabla_aggrid(tabla_li, key="tabla_laterales_izq", df_base=rankings["Lateral izquierdo"])
    else:
        st.write("No hay columnas de laterales izquierdos disponibles en el dataset.")

    st.subheader("Laterales Derechos")
    cols_exist = [c for c in columnas_laterales if c in rankings["Lateral derecho"].columns]
    if cols_exist:
        if rankings["Lateral derecho"].empty:
            tabla_ld = pd.DataFrame(columns=cols_exist)
        else:
            tabla_ld = rankings["Lateral derecho"][cols_exist].head(10)
        mostrar_tabla_aggrid(tabla_ld, key="tabla_laterales_der", df_base=rankings["Lateral derecho"])
    else:
        st.write("No hay columnas de laterales derechos disponibles en el dataset.")

    # ===== DEFENSAS CENTRALES =====
    columnas_dfc = [
        "Temporada","Nombre_Liga","Jugador","Pos","Equipo","Categoría_Liga",
        "Edad","Nacionalidad","Altura","Valor_Mercado","Pie bueno",
        "Minutos jugados","Fin de contrato",

        "Score Central Genérico",
        "Percentil Score Central Genérico",
        "Score Central Defensivo",
        "Percentil Score Central Defensivo",
        "Score Central Combinativo",
        "Percentil Score Central Combinativo",
        "Score Central Total",
        "Percentil Score Central Total",

        'Tackles/Fue Regateado (DFC_GENERICO)',
       'Intercepciones (DFC_GENERICO)', 'Recuperaciones (DFC_GENERICO)',
       '% Duelos Defensivos (DFC_GENERICO)',
       'Duelos Defensivos (DFC_GENERICO)', 'Presión Individual (DFC_GENERICO)',
       'Duelos Aéreos (DFC_GENERICO)', 'Pérdidas Peligrosas (DFC_GENERICO)',
       'Pases Progresivos Completados (DFC_GENERICO)',
       'Progresión de Balón con Conducción (DFC_GENERICO)',
       'Acciones Fallidas en Campo Propio (DFC_GENERICO)',
       '% Duelos por Bajo (DFC_DEFENSIVO)',
       'Tackles/Fue Regateado ⅓ (DFC_DEFENSIVO)',
       'Tackles/Fue Regateado (DFC_DEFENSIVO)',
       'Intercepciones (DFC_DEFENSIVO)', 'Despejes (DFC_DEFENSIVO)',
       'Duelos Aéreos Defensivos Ganados (DFC_DEFENSIVO)',
       'Duelos Aéreos (DFC_DEFENSIVO)',
       'Pases Progresivos Completados (DFC_COMBINATIVO)',
       'xT Pases (DFC_COMBINATIVO)',
       '% Pases Adelante Completados (DFC_COMBINATIVO)',
       'Progreso Medio de Conducciones (DFC_COMBINATIVO)',
       'Pérdidas de Balón (DFC_COMBINATIVO)',
       'Acciones Fallidas en Campo Propio (DFC_COMBINATIVO)',
    ]

    st.subheader("Defensas Centrales Izquierdos")
    cols_exist = [c for c in columnas_dfc if c in rankings["DFC Izquierdo"].columns]
    if cols_exist:
        if rankings["DFC Izquierdo"].empty:
            tabla_dfc_izq = pd.DataFrame(columns=cols_exist)
        else:
            tabla_dfc_izq = rankings["DFC Izquierdo"][cols_exist].head(10)
        mostrar_tabla_aggrid(tabla_dfc_izq, key="tabla_dfc_izq", df_base=rankings["DFC Izquierdo"])
    else:
        st.write("No hay columnas de DFC Izquierdo disponibles en el dataset.")

    st.subheader("Defensas Centrales Derechos")
    cols_exist = [c for c in columnas_dfc if c in rankings["DFC Derecho"].columns]
    if cols_exist:
        if rankings["DFC Derecho"].empty:
            tabla_dfc_der = pd.DataFrame(columns=cols_exist)
        else:
            tabla_dfc_der = rankings["DFC Derecho"][cols_exist].head(10)
        mostrar_tabla_aggrid(tabla_dfc_der, key="tabla_dfc_der", df_base=rankings["DFC Derecho"])
    else:
        st.write("No hay columnas de DFC Derecho disponibles en el dataset.")

    # ===== MC CONTENCIÓN =====
    columnas_mc_contencion = [
        "Temporada","Nombre_Liga","Jugador","Pos","Equipo","Categoría_Liga",
        "Edad","Nacionalidad","Altura","Valor_Mercado","Pie bueno",
        "Minutos jugados","Fin de contrato",

        "Score MC Genérico",
        "Percentil Score MC Genérico",
        "Score MC Contención",
        "Percentil Score MC Contención",
        "Score MC Ofensivo",
        "Percentil Score MC Ofensivo",
        "Score MC Box-to-Box",
        "Percentil Score MC Box-to-Box",

        "% Pases (MC_GENERICO)",
        "Tackles/Fue Regateado Último ⅓ (MC_GENERICO)",
        "Intercepciones (MC_GENERICO)",
        "Recuperaciones (MC_GENERICO)",
        "Presión Individual (MC_GENERICO)",
        "% Pases en Campo Contrario (MC_GENERICO)",
        "% Pases en Campo Propio (MC_GENERICO)",
        "Progresión de Balón (MC_GENERICO)",
        "Entradas al Área (MC_GENERICO)",
        "Participación xG Último ⅓ (MC_GENERICO)",
        "Conducciones Progresivas (MC_GENERICO)",
        "Eficiencia Aérea (MC_GENERICO)",
        "Pases Progresivos Recibidos en Campo Rival (MC_GENERICO)",

        "Duelos Defensivos (MC_CONTENCION)",
        "Tackles/Fue Regateado (MC_CONTENCION)",
        "Intercepciones (MC_CONTENCION)",
        "Recuperaciones (MC_CONTENCION)",
        "Duelos Aéreos Defensivos Ganados (MC_CONTENCION)",
        "% Duelos Aéreos Defensivos (MC_CONTENCION)",
        "% Pases (MC_CONTENCION)",
        "% Retención del Balón (MC_CONTENCION)",
        "Pases Progresivos Completados (MC_CONTENCION)",
        "% Pases Adelante Completados (MC_CONTENCION)",

        "xA en Jugada (MC_OFENSIVO)",
        "Peligro Esperado (xT) (MC_OFENSIVO)",
        "Remates (MC_OFENSIVO)",
        "Secuencia acabada en tiro (MC_OFENSIVO)",
        "xG/90 (MC_OFENSIVO)",
        "xG a Puerta (MC_OFENSIVO)",
        "Goles sin Penaltis (MC_OFENSIVO)",
        "Pases en Profundidad (MC_OFENSIVO)",
        "Entradas al Área (MC_OFENSIVO)",

        "Pases a Campo Contrario (MC_B2B)",
        "Pases Progresivos Recibidos en Campo Rival (MC_B2B)",
        "xG/90 (MC_B2B)",
        "Remates Fuera del Área (MC_B2B)",
        "Contribución Goleadora (MC_B2B)",
        "xT en Juego (MC_B2B)",
        "Profundidad en el Último ⅓ (MC_B2B)",
        "Conducciones Progresivas (MC_B2B)",
        "Profundidad (MC_B2B)",
    ]

    st.subheader("MC Contención")
    cols_exist = [c for c in columnas_mc_contencion if c in rankings["MC Contención"].columns]
    if cols_exist:
        if rankings["MC Contención"].empty:
            tabla_mc_con = pd.DataFrame(columns=cols_exist)
        else:
            tabla_mc_con = rankings["MC Contención"][cols_exist].head(10)
        mostrar_tabla_aggrid(tabla_mc_con, key="tabla_mc_contencion", df_base=rankings["MC Contención"])
    else:
        st.write("No hay columnas de MC Contención disponibles en el dataset.")

    # ===== MC BOX TO BOX =====
    columnas_mc_box = [
    "Temporada","Nombre_Liga","Jugador","Pos","Equipo","Categoría_Liga",
    "Edad","Nacionalidad","Altura","Valor_Mercado","Pie bueno",
    "Minutos jugados","Fin de contrato",

    "Score MC Genérico",
    "Percentil Score MC Genérico",
    "Score MC Contención",
    "Percentil Score MC Contención",
    "Score MC Ofensivo",
    "Percentil Score MC Ofensivo",
    "Score MC Box-to-Box",
    "Percentil Score MC Box-to-Box",

    "% Pases (MC_GENERICO)",
    "Tackles/Fue Regateado Último ⅓ (MC_GENERICO)",
    "Intercepciones (MC_GENERICO)",
    "Recuperaciones (MC_GENERICO)",
    "Presión Individual (MC_GENERICO)",
    "% Pases en Campo Contrario (MC_GENERICO)",
    "% Pases en Campo Propio (MC_GENERICO)",
    "Progresión de Balón (MC_GENERICO)",
    "Entradas al Área (MC_GENERICO)",
    "Participación xG Último ⅓ (MC_GENERICO)",
    "Conducciones Progresivas (MC_GENERICO)",
    "Eficiencia Aérea (MC_GENERICO)",
    "Pases Progresivos Recibidos en Campo Rival (MC_GENERICO)",

    "Duelos Defensivos (MC_CONTENCION)",
    "Tackles/Fue Regateado (MC_CONTENCION)",
    "Intercepciones (MC_CONTENCION)",
    "Recuperaciones (MC_CONTENCION)",
    "Duelos Aéreos Defensivos Ganados (MC_CONTENCION)",
    "% Duelos Aéreos Defensivos (MC_CONTENCION)",
    "% Pases (MC_CONTENCION)",
    "% Retención del Balón (MC_CONTENCION)",
    "Pases Progresivos Completados (MC_CONTENCION)",
    "% Pases Adelante Completados (MC_CONTENCION)",

    "xA en Jugada (MC_OFENSIVO)",
    "Peligro Esperado (xT) (MC_OFENSIVO)",
    "Remates (MC_OFENSIVO)",
    "Secuencia acabada en tiro (MC_OFENSIVO)",
    "xG/90 (MC_OFENSIVO)",
    "xG a Puerta (MC_OFENSIVO)",
    "Goles sin Penaltis (MC_OFENSIVO)",
    "Pases en Profundidad (MC_OFENSIVO)",
    "Entradas al Área (MC_OFENSIVO)",

    "Pases a Campo Contrario (MC_B2B)",
    "Pases Progresivos Recibidos en Campo Rival (MC_B2B)",
    "xG/90 (MC_B2B)",
    "Remates Fuera del Área (MC_B2B)",
    "Contribución Goleadora (MC_B2B)",
    "xT en Juego (MC_B2B)",
    "Profundidad en el Último ⅓ (MC_B2B)",
    "Conducciones Progresivas (MC_B2B)",
    "Profundidad (MC_B2B)",
]


    st.subheader("MC Box to Box")
    cols_exist = [c for c in columnas_mc_box if c in rankings["MC Box to Box"].columns]
    if cols_exist:
        if rankings["MC Box to Box"].empty:
            tabla_mc_box = pd.DataFrame(columns=cols_exist)
        else:
            tabla_mc_box = rankings["MC Box to Box"][cols_exist].head(10)
        mostrar_tabla_aggrid(tabla_mc_box, key="tabla_mc_box", df_base=rankings["MC Box to Box"])
    else:
        st.write("No hay columnas de MC Box to Box disponibles en el dataset.")

    # ===== MC OFENSIVO =====
    columnas_mc_ofensivo = [
    "Temporada","Nombre_Liga","Jugador","Pos","Equipo","Categoría_Liga",
    "Edad","Nacionalidad","Altura","Valor_Mercado","Pie bueno",
    "Minutos jugados","Fin de contrato",

    "Score MC Genérico",
    "Percentil Score MC Genérico",
    "Score MC Contención",
    "Percentil Score MC Contención",
    "Score MC Ofensivo",
    "Percentil Score MC Ofensivo",
    "Score MC Box-to-Box",
    "Percentil Score MC Box-to-Box",

    "% Pases (MC_GENERICO)",
    "Tackles/Fue Regateado Último ⅓ (MC_GENERICO)",
    "Intercepciones (MC_GENERICO)",
    "Recuperaciones (MC_GENERICO)",
    "Presión Individual (MC_GENERICO)",
    "% Pases en Campo Contrario (MC_GENERICO)",
    "% Pases en Campo Propio (MC_GENERICO)",
    "Progresión de Balón (MC_GENERICO)",
    "Entradas al Área (MC_GENERICO)",
    "Participación xG Último ⅓ (MC_GENERICO)",
    "Conducciones Progresivas (MC_GENERICO)",
    "Eficiencia Aérea (MC_GENERICO)",
    "Pases Progresivos Recibidos en Campo Rival (MC_GENERICO)",

    "Duelos Defensivos (MC_CONTENCION)",
    "Tackles/Fue Regateado (MC_CONTENCION)",
    "Intercepciones (MC_CONTENCION)",
    "Recuperaciones (MC_CONTENCION)",
    "Duelos Aéreos Defensivos Ganados (MC_CONTENCION)",
    "% Duelos Aéreos Defensivos (MC_CONTENCION)",
    "% Pases (MC_CONTENCION)",
    "% Retención del Balón (MC_CONTENCION)",
    "Pases Progresivos Completados (MC_CONTENCION)",
    "% Pases Adelante Completados (MC_CONTENCION)",

    "xA en Jugada (MC_OFENSIVO)",
    "Peligro Esperado (xT) (MC_OFENSIVO)",
    "Remates (MC_OFENSIVO)",
    "Secuencia acabada en tiro (MC_OFENSIVO)",
    "xG/90 (MC_OFENSIVO)",
    "xG a Puerta (MC_OFENSIVO)",
    "Goles sin Penaltis (MC_OFENSIVO)",
    "Pases en Profundidad (MC_OFENSIVO)",
    "Entradas al Área (MC_OFENSIVO)",

    "Pases a Campo Contrario (MC_B2B)",
    "Pases Progresivos Recibidos en Campo Rival (MC_B2B)",
    "xG/90 (MC_B2B)",
    "Remates Fuera del Área (MC_B2B)",
    "Contribución Goleadora (MC_B2B)",
    "xT en Juego (MC_B2B)",
    "Profundidad en el Último ⅓ (MC_B2B)",
    "Conducciones Progresivas (MC_B2B)",
    "Profundidad (MC_B2B)",
]


    st.subheader("MC Ofensivo")
    cols_exist = [c for c in columnas_mc_ofensivo if c in rankings["MC Ofensivo"].columns]
    if cols_exist:
        if rankings["MC Ofensivo"].empty:
            tabla_mc_of = pd.DataFrame(columns=cols_exist)
        else:
            tabla_mc_of = rankings["MC Ofensivo"][cols_exist].head(10)
        mostrar_tabla_aggrid(tabla_mc_of, key="tabla_mc_ofensivo", df_base=rankings["MC Ofensivo"])
    else:
        st.write("No hay columnas de MC Ofensivo disponibles en el dataset.")

    # ===== EXTREMOS =====
    columnas_extremos = [
        "Temporada","Nombre_Liga","Jugador","Pos","Equipo","Categoría_Liga",
        "Edad","Nacionalidad","Altura","Valor_Mercado","Pie bueno",
        "Minutos jugados","Fin de contrato",

        "Score Extremo Genérico",
        "Percentil Score Extremo Genérico",
        "Score Extremo Wide Out",
        "Percentil Score Extremo Wide Out",
        "Score Extremo Incorporación",
        "Percentil Score Extremo Incorporación",
        "Score Extremo Combinativo",
        "Percentil Score Extremo Combinativo",
        "Score Extremos Total",
        "Percentil Score Extremos Total",

        "Acciones Agresivas (EXT_GENERICO)",
        "Duelos Defensivos (EXT_GENERICO)",
        "Presión Individual (EXT_GENERICO)",
        "xG/90 (EXT_GENERICO)",
        "Centros (EXT_GENERICO)",
        "% Centros Completados (EXT_GENERICO)",
        "Contribución Goleadora (EXT_GENERICO)",
        "Asistencias Esperadas (EXT_GENERICO)",
        "Peligro Esperado (xT) (EXT_GENERICO)",
        "Regates Completados Campo Contrario (EXT_GENERICO)",
        "% Regates Completados Último ⅓ (EXT_GENERICO)",
        "Profundidad (EXT_GENERICO)",

        "Participación xG Último ⅓ (EXT_WIDEOUT)",
        "Profundidad (EXT_WIDEOUT)",
        "Conducción y Ocasión (EXT_WIDEOUT)",
        "Toques (EXT_WIDEOUT)",
        "xA de Centros (EXT_WIDEOUT)",
        "xT Regates (EXT_WIDEOUT)",
        "Regates Intentados Último ⅓ (EXT_WIDEOUT)",
        "% Regates Completados Último ⅓ (EXT_WIDEOUT)",

        "Goles sin Penaltis (EXT_INCORPORACION)",
        "Finalización (EXT_INCORPORACION)",
        "xG por Remate (EXT_INCORPORACION)",
        "Toques en Área Rival (EXT_INCORPORACION)",
        "Remates a Puerta (EXT_INCORPORACION)",
        "Fueras de Juego (EXT_INCORPORACION)",
        "% Toques de Balón en el Área Rival en su Equipo (EXT_INCORPORACION)",
        "Profundidad (EXT_INCORPORACION)",

        "xT Pases por 100 Pases (EXT_COMBINATIVO)",
        "xT en Juego (EXT_COMBINATIVO)",
        "Progresión de Balón (EXT_COMBINATIVO)",
        "Asistencias Esperadas (EXT_COMBINATIVO)",
        "Contribución Goleadora (EXT_COMBINATIVO)",
        "Ocasiones Creadas (EXT_COMBINATIVO)",
    ]


    st.subheader("Extremos Izquierdos")
    cols_exist = [c for c in columnas_extremos if c in rankings["Extremo Izquierdo"].columns]
    if cols_exist:
        if rankings["Extremo Izquierdo"].empty:
            tabla_ei = pd.DataFrame(columns=cols_exist)
        else:
            tabla_ei = rankings["Extremo Izquierdo"][cols_exist].head(10)
        mostrar_tabla_aggrid(tabla_ei, key="tabla_extremos_izq", df_base=rankings["Extremo Izquierdo"])
    else:
        st.write("No hay columnas de Extremos Izquierdos disponibles en el dataset.")

    st.subheader("Extremos Derechos")
    cols_exist = [c for c in columnas_extremos if c in rankings["Extremo Derecho"].columns]
    if cols_exist:
        if rankings["Extremo Derecho"].empty:
            tabla_ed = pd.DataFrame(columns=cols_exist)
        else:
            tabla_ed = rankings["Extremo Derecho"][cols_exist].head(10)
        mostrar_tabla_aggrid(tabla_ed, key="tabla_extremos_der", df_base=rankings["Extremo Derecho"])
    else:
        st.write("No hay columnas de Extremos Derechos disponibles en el dataset.")

    # ===== DELANTEROS =====
    columnas_delantero = [
        "Temporada","Nombre_Liga","Jugador","Pos","Equipo","Categoría_Liga",
        "Edad","Nacionalidad","Altura","Valor_Mercado","Pie bueno",
        "Minutos jugados","Fin de contrato",

        "Score Delantero",
        "Percentil Score Delantero",
        "Score 9",
        "Percentil Score 9",
        "Score Segundo Delantero",
        "Percentil Score Segundo Delantero",
        "Score Total",
        "Percentil Score Total",

       'Goles sin Penaltis (DEL_DELANTERO)', 'Remates (DEL_DELANTERO)',
       'xG por Remate (DEL_DELANTERO)', '% Remates a Puerta (DEL_DELANTERO)',
       'xG/90 (DEL_DELANTERO)', 'Pérdidas de Balón (DEL_DELANTERO)',
       '% Retención del Balón en Campo Rival (DEL_DELANTERO)',
       'Toques (DEL_DELANTERO)', '% Regates Completados (DEL_DELANTERO)',
       'Peligro Esperado (xT) (DEL_DELANTERO)',
       '% Duelos Aéreos Ganados Campo Rival (DEL_DELANTERO)',
       'Distancia Media de Conducción (DEL_DELANTERO)',
       'Presión Individual Campo Rival (DEL_DELANTERO)',
       '% Duelos Aéreos Ganados Campo Rival (DEL_9)',
       'Duelos Aéreos Totales Campo Rival (DEL_9)',
       'xG por Goles sin Penaltis (DEL_9)', 'xG/90 (DEL_9)',
       'Pases Largos Recibidos (DEL_9)',
       'Pases Progresivos Recibidos en el Área (DEL_9)',
       'Participación xG (DEL_9)',
       '% Retención del Balón en Campo Rival (DEL_9)',
       'xT en Juego (DEL_SEGUNDO)', 'Asistencias Esperadas (DEL_SEGUNDO)',
       '% Pases en Juego en el Área Rival en su Equipo (DEL_SEGUNDO)',
       'Pases Completados al Área en Juego (DEL_SEGUNDO)',
       'Conducciones Progresivas (DEL_SEGUNDO)',
       'Conducción y Tiro (DEL_SEGUNDO)',
       'Progreso Medio de Conducciones (DEL_SEGUNDO)',
    ]

    st.subheader("Delanteros")
    cols_exist = [c for c in columnas_delantero if c in rankings["Delantero"].columns]
    if cols_exist:
        if rankings["Delantero"].empty:
            tabla_del = pd.DataFrame(columns=cols_exist)
        else:
            tabla_del = rankings["Delantero"][cols_exist].head(10)
        mostrar_tabla_aggrid(tabla_del, key="tabla_delanteros", df_base=rankings["Delantero"])
    else:
        st.write("No hay columnas de Delanteros disponibles en el dataset.")



# Llamada a la app de Streamlit
app()

