import io
import pandas as pd
import plotly.express as px
import pypdfium2 as pdfium
import streamlit as st

try:
    from src.assets import LOGO_BASE64
    from src.db import guardar_factura_en_db, obtener_facturas_de_db
    from src.models import DetallePotencia, DetalleTramo, FacturaLuz
    from src.parser_naturgy import extraer_factura_naturgy
except ImportError:
    from assets import LOGO_BASE64
    from db import guardar_factura_en_db, obtener_facturas_de_db
    from models import DetallePotencia, DetalleTramo, FacturaLuz
    from parser_naturgy import extraer_factura_naturgy

# Configuración de la página
st.set_page_config(
    page_title="Control Facturas de Luz",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Estilos CSS personalizados
st.markdown("""
<style>
    /* Cabecera transparente y accesible */
    header[data-testid="stHeader"] {
        background-color: transparent !important;
        pointer-events: auto !important;
        z-index: 999 !important;
    }

    /* El toolbar debe estar visible para que el botón de abrir la barra lateral funcione */
    [data-testid="stToolbar"] {
        display: flex !important;
        visibility: visible !important;
        opacity: 1 !important;
    }

    /* Botón destacado para reabrir la barra lateral (>> chevron) */
    [data-testid="stExpandSidebarButton"],
    [data-testid="stSidebarCollapsedControl"],
    [data-testid="collapsedControl"],
    header[data-testid="stHeader"] button[aria-label*="sidebar" i],
    header[data-testid="stHeader"] button[aria-label*="Sidebar" i] {
        display: flex !important;
        visibility: visible !important;
        opacity: 1 !important;
        pointer-events: auto !important;
        background-color: #ff9800 !important;
        border: 1px solid #ffa726 !important;
        border-radius: 8px !important;
        padding: 5px 12px !important;
        margin: 6px 10px !important;
        box-shadow: 0 2px 10px rgba(255, 152, 0, 0.45) !important;
        cursor: pointer !important;
        z-index: 999999 !important;
    }

    /* Icono dentro del botón de reabrir menú lateral */
    [data-testid="stExpandSidebarButton"] svg,
    header[data-testid="stHeader"] button[aria-label*="sidebar" i] svg {
        fill: #111111 !important;
        color: #111111 !important;
        width: 22px !important;
        height: 22px !important;
    }

    /* Ocultar botones de deploy si existen en Streamlit Cloud */
    .stAppDeployButton,
    [data-testid="stHeaderActionElements"] {
        display: none !important;
    }

    /* Espaciado del contenedor principal para que nada choque con la cabecera */
    .block-container {
        padding-top: 3.5rem !important;
        padding-bottom: 3rem !important;
    }

    /* Compactar ligeramente los inputs dentro de formularios en horizontal */
    [data-testid="stForm"] [data-testid="stVerticalBlock"] {
        gap: 0.45rem !important;
    }

    /* Botón flotante para volver arriba al hacer scroll */
    .floating-top-btn {
        position: fixed;
        bottom: 24px;
        right: 24px;
        z-index: 9999;
        background-color: #ff9800;
        color: #111111 !important;
        width: 44px;
        height: 44px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 20px;
        font-weight: bold;
        text-decoration: none !important;
        box-shadow: 0 4px 14px rgba(0,0,0,0.45);
        transition: transform 0.2s ease;
    }
    .floating-top-btn:hover {
        transform: scale(1.1);
        background-color: #ffa726;
    }
</style>
<div id="top"></div>
<a href="#top" class="floating-top-btn" title="Volver arriba">⬆️</a>
""", unsafe_allow_html=True)


def _renderizar_paginas_pdf(pdf_bytes: bytes, scale: float = 2.0):
    pdf = pdfium.PdfDocument(pdf_bytes)
    try:
        return [pdf[i].render(scale=scale).to_pil() for i in range(len(pdf))]
    finally:
        pdf.close()


# Cargar facturas desde Supabase
facturas = obtener_facturas_de_db()

# ================= BARRA LATERAL: NAVEGACIÓN Y CONTROLES =================
with st.sidebar:
    st.markdown(f"""
    <div style="display: flex; align-items: center; gap: 12px; margin-top: -10px; margin-bottom: 15px;">
        <img src="data:image/jpeg;base64,{LOGO_BASE64}" style="width: 44px; height: 44px; border-radius: 10px; box-shadow: 0 4px 12px rgba(255, 152, 0, 0.4); object-fit: cover;">
        <div>
            <h3 style="margin: 0; font-size: 1.25rem; font-weight: 700; color: #ffffff; line-height: 1.1;">
                Control Facturas
            </h3>
            <span style="font-size: 0.78rem; color: #9aa0a6;">Naturgy Doméstico</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("#### 📌 Secciones")
    seccion_activa = st.radio(
        "Elige la sección a consultar:",
        [
            "📊 Consulta del Mes",
            "📈 Hábitos y Evolución",
            "🔌 Diagnóstico de Potencia",
            "📋 Histórico Completo",
        ],
        index=0,
        label_visibility="collapsed",
    )

    st.markdown("---")

    st.markdown("#### 🔎 Período a Consultar")
    if facturas:
        opciones_dict = {
            f"📅 {f.fecha_inicio} al {f.fecha_fin} — {f.total_factura_eur:.2f} €": f
            for f in reversed(facturas)
        }
        sel_label = st.selectbox(
            "Selecciona la factura:",
            list(opciones_dict.keys()),
            index=0,
            label_visibility="collapsed",
        )
        factura_sel = opciones_dict[sel_label]

        ver_con_impuestos = st.toggle(
            "🧾 Ver con Impuestos (IVA + Elec.)",
            value=True,
            help="Aplica el Impuesto Eléctrico (~5.11%) y el IVA (21%) a cada tramo para calcular el coste final real.",
        )
    else:
        factura_sel = None
        ver_con_impuestos = True

    st.markdown("---")

    st.markdown("#### 📥 Cargar Facturas")
    archivos_subidos = st.file_uploader(
        "Arrastra PDFs de Naturgy aquí",
        type=["pdf"],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )
    if archivos_subidos:
        st.caption("🔍 Facturas cargadas listas para comprobación.")

    if facturas:
        st.caption(f"📁 **Total en BD:** `{len(facturas)} facturas registradas`")

# Subida rápida también disponible cuando no hay facturas en BD
archivos_main = []
if not facturas:
    st.info("👈 Comienza subiendo tu factura en PDF desde el menú lateral izquierdo o desde aquí.")
    archivos_main = st.file_uploader(
        "Arrastra o selecciona tu factura PDF de Naturgy aquí:",
        type=["pdf"],
        accept_multiple_files=True,
        key="uploader_sin_facturas",
    )
    if not archivos_main:
        st.markdown("""
        ### ¿Qué podrás ver aquí?
        * **Resumen mensual:** Importe total, desglose de costes y coste medio por día y por kWh.
        * **Hábitos de consumo:** Cuánta energía consumes en horario Valle (el más económico) vs Llano y Punta.
        * **Diagnóstico de potencia:** Comprueba si estás pagando por potencia de más o si te conviene no tocarla.
        * **Histórico acumulado:** Si subes varias facturas, verás la evolución del gasto mes a mes.
        """)
        st.stop()

archivos_a_procesar = list(archivos_subidos or []) + list(archivos_main or [])

# ================= REVISIÓN PREVIA: PDF + FORMULARIO COMPACTO EN HORIZONTAL =================
if archivos_a_procesar:
    st.markdown("### 🔍 Revisión Previa antes de Guardar")
    col_info, col_modo = st.columns([2, 1])
    with col_info:
        st.caption("Comprueba los datos extraídos comparando con el PDF original antes de guardar en Supabase.")
    with col_modo:
        modo_vista = st.radio(
            "Disposición:",
            ["📱 Apilada (Ancho completo)", "🖥️ Lado a lado"],
            horizontal=True,
            label_visibility="collapsed",
        )

    for idx, archivo in enumerate(archivos_a_procesar):
        pdf_bytes = archivo.getvalue()
        cache_key = f"cache_pdf_{idx}_{archivo.name}_{len(pdf_bytes)}"

        if cache_key not in st.session_state:
            try:
                f_base = extraer_factura_naturgy(io.BytesIO(pdf_bytes))
                imgs_pdf = _renderizar_paginas_pdf(pdf_bytes, scale=2.0)
                st.session_state[cache_key] = (f_base, imgs_pdf, None)
            except Exception as e:
                st.session_state[cache_key] = (None, [], str(e))

        f_preview, paginas_pdf, err_msg = st.session_state[cache_key]

        with st.expander(
            f"📄 `{archivo.name}` — Factura Nº `{f_preview.numero_factura if f_preview else 'Error'}`",
            expanded=True,
        ):
            if err_msg or f_preview is None:
                st.error(f"Error procesando el archivo {archivo.name}: {err_msg}")
                continue

            if modo_vista == "🖥️ Lado a lado":
                zona_pdf, zona_form = st.columns([1.05, 1.15], gap="large")
                altura_visor = 680
            else:
                zona_pdf = st.container()
                zona_form = st.container()
                altura_visor = 430

            # --- VISOR DEL PDF ---
            with zona_pdf:
                c_tit_pdf, c_pag_pdf = st.columns([2, 1])
                with c_tit_pdf:
                    st.markdown("#### 📄 Documento Original")
                with c_pag_pdf:
                    opciones_pag = ["Todas las páginas (scroll)"] + [
                        f"Página {i}" for i in range(1, len(paginas_pdf) + 1)
                    ]
                    pag_sel = st.selectbox(
                        "Página a visualizar:",
                        opciones_pag,
                        index=0,
                        key=f"sel_pag_{idx}_{archivo.name}",
                        label_visibility="collapsed",
                    )

                with st.container(height=altura_visor):
                    if pag_sel == "Todas las páginas (scroll)":
                        for n_pag, img_pag in enumerate(paginas_pdf, start=1):
                            st.caption(f"Página {n_pag} de {len(paginas_pdf)}")
                            st.image(img_pag, use_container_width=True)
                    else:
                        n_pag = int(pag_sel.split()[-1])
                        st.caption(f"Página {n_pag} de {len(paginas_pdf)}")
                        st.image(paginas_pdf[n_pag - 1], use_container_width=True)

            # --- FORMULARIO EDITABLE COMPACTO (MÁS CAMPOS POR LÍNEA) ---
            with zona_form:
                st.markdown("#### ✏️ Datos Extraídos (Editables)")
                with st.form(key=f"form_editar_{idx}_{archivo.name}"):
                    # Fila 1: Identificación y fechas en una sola línea (6 columnas)
                    r1_1, r1_2, r1_3, r1_4, r1_5, r1_6 = st.columns([1.3, 1.6, 1, 1, 1, 0.7])
                    num_fac = r1_1.text_input("Nº Factura", value=f_preview.numero_factura)
                    cups_val = r1_2.text_input("CUPS", value=f_preview.cups or "")
                    f_emi = r1_3.text_input("Emisión", value=f_preview.fecha_emision or "")
                    f_ini = r1_4.text_input("Inicio", value=f_preview.fecha_inicio)
                    f_fin_val = r1_5.text_input("Fin", value=f_preview.fecha_fin)
                    dias_val = int(
                        r1_6.number_input("Días", value=int(f_preview.dias_facturados), min_value=1, step=1)
                    )

                    # Fila 2: Tarifa + Consumo Punta (kWh, €/kWh, €) en una sola línea (5 columnas)
                    r2_1, r2_2, r2_3, r2_4 = st.columns([1.8, 1, 1.1, 1])
                    tarifa_val = r2_1.text_input("Tarifa", value=f_preview.tarifa or "")
                    p_kwh = r2_2.number_input("🔴 Punta (kWh)", value=float(f_preview.consumo_punta.kwh), format="%.2f")
                    p_prec = r2_3.number_input("Precio Punta (€/kWh)", value=float(f_preview.consumo_punta.precio_kwh), format="%.6f")
                    p_eur = r2_4.number_input("Punta Base (€)", value=float(f_preview.consumo_punta.total_eur), format="%.2f")

                    # Fila 3: Consumo Llano + Consumo Valle en una sola línea (6 columnas)
                    r3_1, r3_2, r3_3, r3_4, r3_5, r3_6 = st.columns(6)
                    l_kwh = r3_1.number_input("🟠 Llano (kWh)", value=float(f_preview.consumo_llano.kwh), format="%.2f")
                    l_prec = r3_2.number_input("Precio Llano", value=float(f_preview.consumo_llano.precio_kwh), format="%.6f")
                    l_eur = r3_3.number_input("Llano Base (€)", value=float(f_preview.consumo_llano.total_eur), format="%.2f")
                    v_kwh = r3_4.number_input("🟢 Valle (kWh)", value=float(f_preview.consumo_valle.kwh), format="%.2f")
                    v_prec = r3_5.number_input("Precio Valle", value=float(f_preview.consumo_valle.precio_kwh), format="%.6f")
                    v_eur = r3_6.number_input("Valle Base (€)", value=float(f_preview.consumo_valle.total_eur), format="%.2f")

                    # Fila 4: Potencias contratadas, precios potencia, total potencia y picos máximos (6 columnas)
                    r4_1, r4_2, r4_3, r4_4, r4_5, r4_6 = st.columns(6)
                    pot1_kw = r4_1.number_input("Pot. P1 (kW)", value=float(f_preview.potencia_p1.potencia_kw), format="%.3f")
                    pot1_prec = r4_2.number_input("€/kW·día P1", value=float(f_preview.potencia_p1.precio_kw_dia), format="%.6f")
                    pot2_kw = r4_3.number_input("Pot. P2 (kW)", value=float(f_preview.potencia_p2.potencia_kw), format="%.3f")
                    pot2_prec = r4_4.number_input("€/kW·día P2", value=float(f_preview.potencia_p2.precio_kw_dia), format="%.6f")
                    tot_pot_eur = r4_5.number_input("Total Pot. (€)", value=float(f_preview.total_potencia_eur), format="%.2f")
                    pmax_p1_val = r4_6.number_input(
                        "Pico P1 (kW)",
                        value=float(f_preview.potencia_max_demandada_p1 or 0.0),
                        format="%.3f",
                    )

                    # Fila 5: Otros conceptos e importes finales en una sola línea (6 columnas)
                    r5_1, r5_2, r5_3, r5_4, r5_5, r5_6 = st.columns(6)
                    bono_val = r5_1.number_input("Bono Social (€)", value=float(f_preview.bono_social_eur), format="%.2f")
                    imp_el_val = r5_2.number_input("Imp. Elec. (€)", value=float(f_preview.impuesto_electricidad_eur), format="%.2f")
                    alq_val = r5_3.number_input("Alquiler (€)", value=float(f_preview.alquiler_contador_eur), format="%.2f")
                    base_val = r5_4.number_input("Base Imp. (€)", value=float(f_preview.base_imponible_eur), format="%.2f")
                    iva_val = r5_5.number_input("IVA (€)", value=float(f_preview.iva_eur), format="%.2f")
                    tot_fac_val = r5_6.number_input("TOTAL (€)", value=float(f_preview.total_factura_eur), format="%.2f")

                    guardar_btn = st.form_submit_button(
                        "✅ Confirmar y Guardar en Base de Datos",
                        type="primary",
                        use_container_width=True,
                    )

                    if guardar_btn:
                        tot_kwh_calc = round(float(p_kwh) + float(l_kwh) + float(v_kwh), 2)
                        tot_ene_calc = round(float(p_eur) + float(l_eur) + float(v_eur), 2)
                        pot1_tot_calc = (
                            round(float(pot1_kw) * dias_val * float(pot1_prec), 2)
                            if pot1_prec > 0
                            else float(f_preview.potencia_p1.total_eur)
                        )
                        pot2_tot_calc = (
                            round(float(pot2_kw) * dias_val * float(pot2_prec), 2)
                            if pot2_prec > 0
                            else float(f_preview.potencia_p2.total_eur)
                        )

                        factura_final = f_preview.model_copy(
                            update={
                                "numero_factura": num_fac.strip() or f_preview.numero_factura,
                                "cups": cups_val.strip() or None,
                                "fecha_emision": f_emi.strip() or None,
                                "fecha_inicio": f_ini.strip() or f_preview.fecha_inicio,
                                "fecha_fin": f_fin_val.strip() or f_preview.fecha_fin,
                                "dias_facturados": dias_val,
                                "tarifa": tarifa_val.strip() or None,
                                "consumo_punta": DetalleTramo(
                                    kwh=float(p_kwh),
                                    precio_kwh=float(p_prec),
                                    total_eur=float(p_eur),
                                ),
                                "consumo_llano": DetalleTramo(
                                    kwh=float(l_kwh),
                                    precio_kwh=float(l_prec),
                                    total_eur=float(l_eur),
                                ),
                                "consumo_valle": DetalleTramo(
                                    kwh=float(v_kwh),
                                    precio_kwh=float(v_prec),
                                    total_eur=float(v_eur),
                                ),
                                "consumo_total_kwh": tot_kwh_calc,
                                "total_energia_eur": tot_ene_calc,
                                "potencia_p1": DetallePotencia(
                                    potencia_kw=float(pot1_kw),
                                    dias=dias_val,
                                    precio_kw_dia=float(pot1_prec),
                                    total_eur=pot1_tot_calc,
                                ),
                                "potencia_p2": DetallePotencia(
                                    potencia_kw=float(pot2_kw),
                                    dias=dias_val,
                                    precio_kw_dia=float(pot2_prec),
                                    total_eur=pot2_tot_calc,
                                ),
                                "total_potencia_eur": float(tot_pot_eur),
                                "potencia_max_demandada_p1": float(pmax_p1_val) if pmax_p1_val > 0 else None,
                                "bono_social_eur": float(bono_val),
                                "impuesto_electricidad_eur": float(imp_el_val),
                                "alquiler_contador_eur": float(alq_val),
                                "base_imponible_eur": float(base_val),
                                "iva_eur": float(iva_val),
                                "total_factura_eur": float(tot_fac_val),
                            }
                        )

                        with st.spinner("Guardando en Supabase..."):
                            ok = guardar_factura_en_db(factura_final)

                        if ok:
                            st.success(f"¡Factura {factura_final.numero_factura} guardada en Supabase con éxito!")
                            st.rerun()
                        else:
                            st.error("Error al guardar en Supabase. Revisa `.env` y la conexión.")

if not factura_sel:
    st.stop()

# ================= CÁLCULO EXACTO DE IMPUESTOS POR TRAMO =================
IMPUESTO_ELECTRICO = 0.0511269632
IVA = 0.21
MULT_IMPUESTOS_ENERGIA = (1.0 + IMPUESTO_ELECTRICO) * (1.0 + IVA)
MULT_IVA_OTROS = 1.0 + IVA

kwh_p1 = float(factura_sel.consumo_punta.kwh)
precio_p1_base = float(factura_sel.consumo_punta.precio_kwh)
gasto_p1_base = kwh_p1 * precio_p1_base
precio_p1_final = precio_p1_base * MULT_IMPUESTOS_ENERGIA
gasto_p1_final = gasto_p1_base * MULT_IMPUESTOS_ENERGIA

kwh_p2 = float(factura_sel.consumo_llano.kwh)
precio_p2_base = float(factura_sel.consumo_llano.precio_kwh)
gasto_p2_base = kwh_p2 * precio_p2_base
precio_p2_final = precio_p2_base * MULT_IMPUESTOS_ENERGIA
gasto_p2_final = gasto_p2_base * MULT_IMPUESTOS_ENERGIA

kwh_p3 = float(factura_sel.consumo_valle.kwh)
precio_p3_base = float(factura_sel.consumo_valle.precio_kwh)
gasto_p3_base = kwh_p3 * precio_p3_base
precio_p3_final = precio_p3_base * MULT_IMPUESTOS_ENERGIA
gasto_p3_final = gasto_p3_base * MULT_IMPUESTOS_ENERGIA

pct_p1 = (kwh_p1 / factura_sel.consumo_total_kwh * 100.0) if factura_sel.consumo_total_kwh > 0 else 0.0
pct_p2 = (kwh_p2 / factura_sel.consumo_total_kwh * 100.0) if factura_sel.consumo_total_kwh > 0 else 0.0
pct_p3 = (kwh_p3 / factura_sel.consumo_total_kwh * 100.0) if factura_sel.consumo_total_kwh > 0 else 0.0

total_energia_base = gasto_p1_base + gasto_p2_base + gasto_p3_base
total_energia_final = gasto_p1_final + gasto_p2_final + gasto_p3_final

total_potencia_base = float(factura_sel.total_potencia_eur)
total_potencia_final = total_potencia_base * MULT_IMPUESTOS_ENERGIA

otros_base = float(factura_sel.bono_social_eur) + float(factura_sel.alquiler_contador_eur)
otros_final = otros_base * MULT_IVA_OTROS

# ================= CABECERA DE LA PÁGINA PRINCIPAL =================
st.markdown(f"""
<div style="display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 10px; margin-bottom: 18px;">
    <div style="display: flex; align-items: center; gap: 14px;">
        <img src="data:image/jpeg;base64,{LOGO_BASE64}" style="width: 44px; height: 44px; border-radius: 10px; box-shadow: 0 4px 15px rgba(255, 152, 0, 0.4); object-fit: cover;">
        <div>
            <h2 style="margin: 0; font-size: 1.45rem; font-weight: 700; color: #ffffff; line-height: 1.2;">
                {seccion_activa}
            </h2>
            <div style="font-size: 0.82rem; color: #9aa0a6; margin-top: 2px;">
                Período: <b style="color: #ff9800;">{factura_sel.fecha_inicio} al {factura_sel.fecha_fin}</b> ({factura_sel.dias_facturados} días) • Tarifa: <b>{factura_sel.tarifa}</b>
            </div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# ================= SECCIÓN 1: CONSULTA DEL MES =================
if seccion_activa == "📊 Consulta del Mes":
    col1, col2, col3, col4 = st.columns(4)
    col1.metric(
        "Total Factura",
        f"{factura_sel.total_factura_eur:.2f} €",
        delta=f"{factura_sel.coste_diario:.2f} €/día",
        delta_color="off",
    )
    col2.metric(
        "Consumo Total",
        f"{factura_sel.consumo_total_kwh:.0f} kWh",
        f"{kwh_p3:.0f} kWh en Valle ({pct_p3:.0f}%)",
    )
    col3.metric(
        "Precio Medio Real",
        f"{factura_sel.coste_medio_kwh:.4f} €/kWh",
        "Todo incluido (Fijo + Energía + IVA)",
    )
    col4.metric(
        "Gasto Energía",
        f"{total_energia_final:.2f} €",
        f"Base: {total_energia_base:.2f} €",
        delta_color="off",
    )

    st.divider()

    st.markdown("### ⚡ Consumo y Gasto por Tramo")
    st.caption("Importe final con impuestos (IVA + IEE) y tarifa base de contrato entre paréntesis.")
    col_t1, col_t2, col_t3 = st.columns(3)

    with col_t1:
        st.error(
            f"#### 🔴 Punta (P1)\n\n"
            f"**Consumo:** {kwh_p1:.1f} kWh ({pct_p1:.1f}%)\n\n"
            f"**Gasto:** **{gasto_p1_final:.2f} €** *(base: {gasto_p1_base:.2f} €)*\n\n"
            f"**Precio:** **{precio_p1_final:.4f} €/kWh** *(base: {precio_p1_base:.4f} €)*"
        )

    with col_t2:
        st.warning(
            f"#### 🟠 Llano (P2)\n\n"
            f"**Consumo:** {kwh_p2:.1f} kWh ({pct_p2:.1f}%)\n\n"
            f"**Gasto:** **{gasto_p2_final:.2f} €** *(base: {gasto_p2_base:.2f} €)*\n\n"
            f"**Precio:** **{precio_p2_final:.4f} €/kWh** *(base: {precio_p2_base:.4f} €)*"
        )

    with col_t3:
        st.success(
            f"#### 🟢 Valle (P3)\n\n"
            f"**Consumo:** {kwh_p3:.1f} kWh ({pct_p3:.1f}%)\n\n"
            f"**Gasto:** **{gasto_p3_final:.2f} €** *(base: {gasto_p3_base:.2f} €)*\n\n"
            f"**Precio:** **{precio_p3_final:.4f} €/kWh** *(base: {precio_p3_base:.4f} €)*"
        )

    st.markdown("### 📋 Desglose Completo: Sin Impuestos vs Con Impuestos")
    datos_tabla = [
        {
            "Concepto": "🔴 Punta (P1)",
            "Consumo": f"{kwh_p1:.1f} kWh",
            "% del Mes": f"{pct_p1:.1f} %",
            "Precio sin Imp.": f"{precio_p1_base:.4f} €/kWh",
            "Precio Final con IVA": f"{precio_p1_final:.4f} €/kWh",
            "Gasto Sin Impuestos": f"{gasto_p1_base:.2f} €",
            "Gasto Final (Con Impuestos)": f"{gasto_p1_final:.2f} €",
        },
        {
            "Concepto": "🟠 Llano (P2)",
            "Consumo": f"{kwh_p2:.1f} kWh",
            "% del Mes": f"{pct_p2:.1f} %",
            "Precio sin Imp.": f"{precio_p2_base:.4f} €/kWh",
            "Precio Final con IVA": f"{precio_p2_final:.4f} €/kWh",
            "Gasto Sin Impuestos": f"{gasto_p2_base:.2f} €",
            "Gasto Final (Con Impuestos)": f"{gasto_p2_final:.2f} €",
        },
        {
            "Concepto": "🟢 Valle (P3)",
            "Consumo": f"{kwh_p3:.1f} kWh",
            "% del Mes": f"{pct_p3:.1f} %",
            "Precio sin Imp.": f"{precio_p3_base:.4f} €/kWh",
            "Precio Final con IVA": f"{precio_p3_final:.4f} €/kWh",
            "Gasto Sin Impuestos": f"{gasto_p3_base:.2f} €",
            "Gasto Final (Con Impuestos)": f"{gasto_p3_final:.2f} €",
        },
        {
            "Concepto": "⚡ TOTAL ENERGÍA",
            "Consumo": f"{factura_sel.consumo_total_kwh:.1f} kWh",
            "% del Mes": "100.0 %",
            "Precio sin Imp.": "-",
            "Precio Final con IVA": "-",
            "Gasto Sin Impuestos": f"{total_energia_base:.2f} €",
            "Gasto Final (Con Impuestos)": f"{total_energia_final:.2f} €",
        },
        {
            "Concepto": "🔌 Potencia Contratada (P1 + P2)",
            "Consumo": f"{factura_sel.potencia_p1.potencia_kw:.2f} kW",
            "% del Mes": "-",
            "Precio sin Imp.": "-",
            "Precio Final con IVA": "-",
            "Gasto Sin Impuestos": f"{total_potencia_base:.2f} €",
            "Gasto Final (Con Impuestos)": f"{total_potencia_final:.2f} €",
        },
        {
            "Concepto": "📦 Otros (Alquiler contador + Bono social)",
            "Consumo": "-",
            "% del Mes": "-",
            "Precio sin Imp.": "-",
            "Precio Final con IVA": "-",
            "Gasto Sin Impuestos": f"{otros_base:.2f} €",
            "Gasto Final (Con Impuestos)": f"{otros_final:.2f} €",
        },
        {
            "Concepto": "💶 TOTAL FACTURA",
            "Consumo": f"{factura_sel.consumo_total_kwh:.1f} kWh",
            "% del Mes": "-",
            "Precio sin Imp.": "-",
            "Precio Final con IVA": "-",
            "Gasto Sin Impuestos": f"{(total_energia_base + total_potencia_base + otros_base):.2f} €",
            "Gasto Final (Con Impuestos)": f"{factura_sel.total_factura_eur:.2f} €",
        },
    ]
    st.dataframe(pd.DataFrame(datos_tabla), use_container_width=True, hide_index=True)

    st.divider()

    col_izq, col_der = st.columns([1, 1])

    with col_izq:
        modo_txt = "con Impuestos" if ver_con_impuestos else "sin Impuestos"
        st.markdown(f"#### 💶 Distribución del Gasto ({modo_txt})")
        vals_costes = (
            [total_energia_final, total_potencia_final, otros_final]
            if ver_con_impuestos
            else [total_energia_base, total_potencia_base, otros_base]
        )
        df_pie = pd.DataFrame({
            "Concepto": ["Energía", "Potencia Fija", "Otros (Contador/Bono)"],
            "Importe (€)": vals_costes,
        })
        fig_pie = px.pie(
            df_pie,
            values="Importe (€)",
            names="Concepto",
            hole=0.45,
            color_discrete_sequence=px.colors.qualitative.Safe,
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_der:
        st.markdown(f"#### ⚡ Gasto por Tramo (€ {modo_txt})")
        vals_tramos = (
            [gasto_p1_final, gasto_p2_final, gasto_p3_final]
            if ver_con_impuestos
            else [gasto_p1_base, gasto_p2_base, gasto_p3_base]
        )
        df_bars = pd.DataFrame({
            "Tramo": ["Punta (P1)", "Llano (P2)", "Valle (P3)"],
            "Gasto (€)": vals_tramos,
        })
        fig_bars = px.bar(
            df_bars,
            x="Tramo",
            y="Gasto (€)",
            color="Tramo",
            text="Gasto (€)",
            color_discrete_map={"Punta (P1)": "#EF553B", "Llano (P2)": "#FFA15A", "Valle (P3)": "#00CC96"},
        )
        fig_bars.update_traces(texttemplate="%{text:.2f} €", textposition="outside")
        st.plotly_chart(fig_bars, use_container_width=True)

# ================= SECCIÓN 2: HÁBITOS Y EVOLUCIÓN =================
elif seccion_activa == "📈 Hábitos y Evolución":
    st.subheader(f"Análisis de Hábitos ({factura_sel.fecha_inicio} al {factura_sel.fecha_fin})")
    if pct_p3 >= 70:
        st.success(
            f"🌟 **¡Hábitos de consumo excelentes!** Concentráis el **{pct_p3:.1f}%** "
            f"de vuestra energía en horario Valle (el tramo más económico a {precio_p3_final:.4f} €/kWh final)."
        )
    elif pct_p3 >= 50:
        st.info(f"👍 Buen aprovechamiento: el **{pct_p3:.1f}%** de vuestro consumo está en horario Valle.")
    else:
        st.warning(
            f"⚠️ Solo el **{pct_p3:.1f}%** de vuestro consumo es en Valle. "
            f"Os convendría desplazar electrodomésticos de gran consumo a la noche o fines de semana."
        )

    if len(facturas) > 1:
        st.markdown("---")
        st.markdown("#### 📅 Evolución Histórica de Consumo y Gasto")
        hist_data = [
            {
                "Período": f"{f.fecha_inicio} al {f.fecha_fin}",
                "Factura (€)": f.total_factura_eur,
                "Consumo Total (kWh)": f.consumo_total_kwh,
                "Coste diario (€/día)": f.coste_diario,
                "Punta (kWh)": f.consumo_punta.kwh,
                "Llano (kWh)": f.consumo_llano.kwh,
                "Valle (kWh)": f.consumo_valle.kwh,
                "Coste/kWh (€)": f.coste_medio_kwh,
            }
            for f in facturas
        ]
        df_hist = pd.DataFrame(hist_data)

        fig_evol = px.line(
            df_hist,
            x="Período",
            y=["Factura (€)", "Consumo Total (kWh)"],
            markers=True,
            title="Evolución Factura (€) vs Consumo Total (kWh)",
        )
        st.plotly_chart(fig_evol, use_container_width=True)

        st.markdown("#### ⚡ Reparto de Consumo Histórico por Tramos (kWh)")
        fig_tramos = px.bar(
            df_hist,
            x="Período",
            y=["Valle (kWh)", "Llano (kWh)", "Punta (kWh)"],
            title="Consumo por Tramos a lo largo de los meses",
            color_discrete_map={"Punta (kWh)": "#EF553B", "Llano (kWh)": "#FFA15A", "Valle (kWh)": "#00CC96"},
        )
        st.plotly_chart(fig_tramos, use_container_width=True)
    else:
        st.info("ℹ️ Sube más facturas en el menú lateral para ver la comparativa mes a mes.")

# ================= SECCIÓN 3: DIAGNÓSTICO DE POTENCIA =================
elif seccion_activa == "🔌 Diagnóstico de Potencia":
    st.subheader(f"🔌 Optimización de Potencia ({factura_sel.fecha_inicio} al {factura_sel.fecha_fin})")
    st.write(
        "Comparativa entre la potencia contratada que pagas cada mes y el pico máximo real "
        "que demandaron tus electrodomésticos en el último año según el contador."
    )

    col_p1, col_p2 = st.columns(2)

    pot_cont_p1 = factura_sel.potencia_p1.potencia_kw
    pot_max_p1 = factura_sel.potencia_max_demandada_p1 or 0.0

    with col_p1:
        st.markdown("### Horario Punta (P1)")
        st.metric("Potencia Contratada", f"{pot_cont_p1:.2f} kW")
        st.metric("Pico Máximo Demandado", f"{pot_max_p1:.2f} kW")

        if pot_max_p1 > pot_cont_p1:
            st.error(
                f"⚠️ Has alcanzado un pico de **{pot_max_p1:.2f} kW**, superando los {pot_cont_p1:.2f} kW "
                f"contratados. **NO debes bajar la potencia** contratada en P1."
            )
        elif pot_max_p1 > (pot_cont_p1 * 0.85):
            st.success("✅ Potencia muy bien ajustada. Estás aprovechando tu potencia sin riesgo de cortes.")
        else:
            ahorro = (pot_cont_p1 - pot_max_p1) * 365 * factura_sel.potencia_p1.precio_kw_dia * MULT_IMPUESTOS_ENERGIA
            st.warning(f"💡 Podrías reducir potencia y ahorrar aproximadamente **{ahorro:.2f} €/año** (con impuestos).")

    with col_p2:
        pot_cont_p2 = factura_sel.potencia_p2.potencia_kw
        pot_max_p2 = factura_sel.potencia_max_demandada_p2 or 0.0
        st.markdown("### Horario Valle (P2)")
        st.metric("Potencia Contratada", f"{pot_cont_p2:.2f} kW")
        st.metric("Pico Máximo Demandado", f"{pot_max_p2:.2f} kW")

        if pot_max_p2 > pot_cont_p2:
            st.error(f"⚠️ Has alcanzado un pico de **{pot_max_p2:.2f} kW** en valle. No reduzcas potencia en P2.")
        else:
            st.success("✅ Potencia en valle adecuada.")

# ================= SECCIÓN 4: HISTÓRICO COMPLETO =================
elif seccion_activa == "📋 Histórico Completo":
    st.subheader("📋 Registro Histórico de Facturas Analizadas")
    tabla = [
        {
            "Nº Factura": f.numero_factura,
            "Inicio": f.fecha_inicio,
            "Fin": f.fecha_fin,
            "Días": f.dias_facturados,
            "Total (€)": f"{f.total_factura_eur:.2f} €",
            "Consumo (kWh)": f"{f.consumo_total_kwh:.1f}",
            "Punta (kWh)": f"{f.consumo_punta.kwh:.1f}",
            "Llano (kWh)": f"{f.consumo_llano.kwh:.1f}",
            "Valle (kWh)": f"{f.consumo_valle.kwh:.1f}",
            "Coste/día": f"{f.coste_diario:.2f} €",
            "Coste/kWh": f"{f.coste_medio_kwh:.4f} €",
        }
        for f in facturas
    ]
    st.dataframe(pd.DataFrame(tabla), use_container_width=True, hide_index=True)