import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from src.parser_naturgy import extraer_factura_naturgy
from src.db import guardar_factura_en_db, obtener_facturas_de_db
from src.assets import LOGO_BASE64

# Configuración de la página
st.set_page_config(
    page_title="Control Facturas de Luz",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilos CSS personalizados
st.markdown("""
<style>
    /* Ocultar solo la barra de herramientas de la derecha (Share, Star, Fork, GitHub) */
    [data-testid="stToolbar"] {
        display: none !important;
    }
    
    /* Cabecera transparente que no tape el logo */
    header[data-testid="stHeader"] {
        background-color: transparent !important;
        pointer-events: none;
    }
    
    /* Mantener visible y clickable el botón para reabrir la barra lateral (>> chevron) */
    header[data-testid="stHeader"] button,
    [data-testid="stSidebarCollapsedControl"],
    [data-testid="collapsedControl"] {
        pointer-events: auto !important;
        display: block !important;
        visibility: visible !important;
        opacity: 1 !important;
        color: #ffffff !important;
    }

    /* Espaciado del contenedor principal */
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 3rem !important;
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

# Cargar facturas desde Supabase
facturas = obtener_facturas_de_db()

# ================= BARRA LATERAL: NAVEGACIÓN Y CONTROLES (100% FIJOS) =================
with st.sidebar:
    # 1. Cabecera con Logo en la barra lateral
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

    # 2. Menú de navegación principal (Siempre visible, nunca se mueve con el scroll)
    st.markdown("#### 📌 Secciones")
    seccion_activa = st.radio(
        "Elige la sección a consultar:",
        [
            "📊 Consulta del Mes",
            "📈 Hábitos y Evolución",
            "🔌 Diagnóstico de Potencia",
            "📋 Histórico Completo"
        ],
        index=0,
        label_visibility="collapsed"
    )
    
    st.markdown("---")

    # 3. Filtros y selección de mes
    st.markdown("#### 🔎 Período a Consultar")
    if facturas:
        opciones_dict = {
            f"📅 {f.fecha_inicio} al {f.fecha_fin} — {f.total_factura_eur:.2f} €": f
            for f in reversed(sorted(facturas, key=lambda x: x.fecha_inicio))
        }
        sel_label = st.selectbox(
            "Selecciona la factura:",
            list(opciones_dict.keys()),
            index=0,
            label_visibility="collapsed"
        )
        factura_sel = opciones_dict[sel_label]
        
        ver_con_impuestos = st.toggle(
            "🧾 Ver con Impuestos (IVA + Elec.)",
            value=True,
            help="Aplica el Impuesto Eléctrico (~5.11%) y el IVA (21%) a cada tramo para calcular el coste final real."
        )
    else:
        factura_sel = None
        ver_con_impuestos = True

    st.markdown("---")

    # 4. Subida de nuevas facturas
    st.markdown("#### 📥 Cargar Facturas")
    archivos_subidos = st.file_uploader(
        "Arrastra PDFs de Naturgy aquí",
        type=["pdf"],
        accept_multiple_files=True,
        label_visibility="collapsed"
    )
    if archivos_subidos:
        st.caption("🔍 Facturas cargadas listas para comprobación.")

    if facturas:
        st.caption(f"📁 **Total en BD:** `{len(facturas)} facturas registradas`")

# Si no hay facturas cargadas, mensaje de bienvenida
if not facturas:
    st.info("👈 Comienza subiendo tu factura en PDF desde el menú lateral izquierdo.")
    st.markdown("""
    ### ¿Qué podrás ver aquí?
    * **Resumen mensual:** Importe total, desglose de costes y coste medio por día y por kWh.
    * **Hábitos de consumo:** Cuánta energía consumes en horario Valle (el más económico) vs Llano y Punta.
    * **Diagnóstico de potencia:** Comprueba si estás pagando por potencia de más o si te conviene no tocarla.
    * **Histórico acumulado:** Si subes varias facturas, verás la evolución del gasto mes a mes.
    """)
    st.stop()

# ================= CÁLCULO EXACTO DE IMPUESTOS POR TRAMO =================
# Tasas oficiales de la factura de Naturgy sin redondear en cálculos intermedios:
# 1. Impuesto Especial sobre la Electricidad (IEE): 5.11269632%
# 2. Impuesto sobre el Valor Añadido (IVA): 21.0%
IMPUESTO_ELECTRICO = 0.0511269632
IVA = 0.21

# Multiplicador exacto de impuestos para energía y potencia: (1 + IEE) * (1 + IVA)
MULT_IMPUESTOS_ENERGIA = (1.0 + IMPUESTO_ELECTRICO) * (1.0 + IVA) # 1.271863625472
MULT_IVA_OTROS = 1.0 + IVA # 1.21 (Bono social y alquiler contador solo llevan IVA)

# --- PUNTA (P1) ---
kwh_p1 = float(factura_sel.consumo_punta.kwh)
precio_p1_base = float(factura_sel.consumo_punta.precio_kwh)
gasto_p1_base = kwh_p1 * precio_p1_base
precio_p1_final = precio_p1_base * MULT_IMPUESTOS_ENERGIA
gasto_p1_final = gasto_p1_base * MULT_IMPUESTOS_ENERGIA

# --- LLANO (P2) ---
kwh_p2 = float(factura_sel.consumo_llano.kwh)
precio_p2_base = float(factura_sel.consumo_llano.precio_kwh)
gasto_p2_base = kwh_p2 * precio_p2_base
precio_p2_final = precio_p2_base * MULT_IMPUESTOS_ENERGIA
gasto_p2_final = gasto_p2_base * MULT_IMPUESTOS_ENERGIA

# --- VALLE (P3) ---
kwh_p3 = float(factura_sel.consumo_valle.kwh)
precio_p3_base = float(factura_sel.consumo_valle.precio_kwh)
gasto_p3_base = kwh_p3 * precio_p3_base
precio_p3_final = precio_p3_base * MULT_IMPUESTOS_ENERGIA
gasto_p3_final = gasto_p3_base * MULT_IMPUESTOS_ENERGIA

# Porcentajes de consumo
pct_p1 = (kwh_p1 / factura_sel.consumo_total_kwh * 100.0) if factura_sel.consumo_total_kwh > 0 else 0.0
pct_p2 = (kwh_p2 / factura_sel.consumo_total_kwh * 100.0) if factura_sel.consumo_total_kwh > 0 else 0.0
pct_p3 = (kwh_p3 / factura_sel.consumo_total_kwh * 100.0) if factura_sel.consumo_total_kwh > 0 else 0.0

# Totales Energía
total_energia_base = gasto_p1_base + gasto_p2_base + gasto_p3_base
total_energia_final = gasto_p1_final + gasto_p2_final + gasto_p3_final

# Potencia fija (P1 + P2)
total_potencia_base = float(factura_sel.total_potencia_eur)
total_potencia_final = total_potencia_base * MULT_IMPUESTOS_ENERGIA

# Otros (Alquiler contador + Bono social)
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

# ================= COMPROBACIÓN PREVIA DE FACTURAS SUBIDAS =================
if archivos_subidos:
    with st.expander(f"🔍 Comprobación de datos leídos del PDF ({len(archivos_subidos)} archivo/s cargado/s)", expanded=True):
        st.info("💡 **Revisa los datos extraídos antes de guardar.** Comprueba que los importes, consumos y precios unitarios coinciden con tu factura de Naturgy. Cuando esté verificado, pulsa en el botón verde para guardarla definitivamente en Supabase.")
        
        for idx, archivo in enumerate(archivos_subidos):
            try:
                f_preview = extraer_factura_naturgy(archivo)
                st.markdown(f"### 📄 `{archivo.name}` — Factura Nº `{f_preview.numero_factura}`")
                
                col_p1, col_p2 = st.columns(2)
                with col_p1:
                    st.write(f"• **Período:** `{f_preview.fecha_inicio}` al `{f_preview.fecha_fin}` ({f_preview.dias_facturados} días)")
                    st.write(f"• **Tarifa:** {f_preview.tarifa}")
                    st.write(f"• **CUPS:** `{f_preview.cups or 'No detectado'}`")
                with col_p2:
                    st.write(f"• **Total Factura:** **`{f_preview.total_factura_eur:.2f} €`**")
                    st.write(f"• **Consumo Total:** **`{f_preview.consumo_total_kwh:.1f} kWh`**")
                    st.write(f"• **Potencias contratadas:** P1: `{f_preview.potencia_p1.potencia_kw:.2f} kW` | P2: `{f_preview.potencia_p2.potencia_kw:.2f} kW`")
                
                # Tabla de comprobación de tramos
                tramos_check = [
                    {
                        "Tramo": "🔴 Punta (P1)",
                        "Consumo (kWh)": f"{f_preview.consumo_punta.kwh:.1f} kWh",
                        "Precio (€/kWh)": f"{f_preview.consumo_punta.precio_kwh:.6f} €",
                        "Gasto Base (€)": f"{f_preview.consumo_punta.total_eur:.2f} €"
                    },
                    {
                        "Tramo": "🟠 Llano (P2)",
                        "Consumo (kWh)": f"{f_preview.consumo_llano.kwh:.1f} kWh",
                        "Precio (€/kWh)": f"{f_preview.consumo_llano.precio_kwh:.6f} €",
                        "Gasto Base (€)": f"{f_preview.consumo_llano.total_eur:.2f} €"
                    },
                    {
                        "Tramo": "🟢 Valle (P3)",
                        "Consumo (kWh)": f"{f_preview.consumo_valle.kwh:.1f} kWh",
                        "Precio (€/kWh)": f"{f_preview.consumo_valle.precio_kwh:.6f} €",
                        "Gasto Base (€)": f"{f_preview.consumo_valle.total_eur:.2f} €"
                    }
                ]
                st.dataframe(pd.DataFrame(tramos_check), use_container_width=True, hide_index=True)
                
                btn_col1, btn_col2 = st.columns([3, 4])
                with btn_col1:
                    if st.button(f"✅ Guardar en Base de Datos", key=f"btn_save_{idx}", type="primary"):
                        if guardar_factura_en_db(f_preview):
                            st.success(f"¡Factura {f_preview.numero_factura} guardada en Supabase con éxito!")
                            st.rerun()
                        else:
                            st.error("Error al guardar en Supabase.")
                st.markdown("---")
            except Exception as e:
                st.error(f"Error procesando el archivo {archivo.name}: {e}")

# ================= SECCIÓN 1: CONSULTA DEL MES =================
if seccion_activa == "📊 Consulta del Mes":
    # Tarjetas métricas superiores
    col1, col2, col3, col4 = st.columns(4)
    col1.metric(
        "Total Factura", 
        f"{factura_sel.total_factura_eur:.2f} €", 
        delta=f"{factura_sel.coste_diario:.2f} €/día", 
        delta_color="off"
    )
    col2.metric(
        "Consumo Total", 
        f"{factura_sel.consumo_total_kwh:.0f} kWh", 
        f"{kwh_p3:.0f} kWh en Valle ({pct_p3:.0f}%)"
    )
    col3.metric(
        "Precio Medio Real", 
        f"{factura_sel.coste_medio_kwh:.4f} €/kWh", 
        "Todo incluido (Fijo + Energía + IVA)"
    )
    col4.metric(
        "Gasto Energía", 
        f"{total_energia_final:.2f} €", 
        f"{total_energia_base:.2f} € sin imp.",
        delta_color="off"
    )
    
    st.divider()

    # Tarjetas de los 3 tramos (Mostrando ambos valores: sin y con impuestos)
    st.markdown("### ⚡ Consumo y Gasto por Tramo")
    col_t1, col_t2, col_t3 = st.columns(3)
    
    with col_t1:
        st.error(
            f"#### 🔴 Punta (P1)\n\n"
            f"**Consumo:** {kwh_p1:.1f} kWh ({pct_p1:.1f}%)\n\n"
            f"**Gasto:**\n"
            f"• Sin imp.: **{gasto_p1_base:.2f} €**\n"
            f"• Con imp.: **{gasto_p1_final:.2f} €**\n\n"
            f"**Precio:**\n"
            f"• Sin imp.: **{precio_p1_base:.4f} €/kWh**\n"
            f"• Con imp.: **{precio_p1_final:.4f} €/kWh**"
        )
                 
    with col_t2:
        st.warning(
            f"#### 🟠 Llano (P2)\n\n"
            f"**Consumo:** {kwh_p2:.1f} kWh ({pct_p2:.1f}%)\n\n"
            f"**Gasto:**\n"
            f"• Sin imp.: **{gasto_p2_base:.2f} €**\n"
            f"• Con imp.: **{gasto_p2_final:.2f} €**\n\n"
            f"**Precio:**\n"
            f"• Sin imp.: **{precio_p2_base:.4f} €/kWh**\n"
            f"• Con imp.: **{precio_p2_final:.4f} €/kWh**"
        )
                   
    with col_t3:
        st.success(
            f"#### 🟢 Valle (P3)\n\n"
            f"**Consumo:** {kwh_p3:.1f} kWh ({pct_p3:.1f}%)\n\n"
            f"**Gasto:**\n"
            f"• Sin imp.: **{gasto_p3_base:.2f} €**\n"
            f"• Con imp.: **{gasto_p3_final:.2f} €**\n\n"
            f"**Precio:**\n"
            f"• Sin imp.: **{precio_p3_base:.4f} €/kWh**\n"
            f"• Con imp.: **{precio_p3_final:.4f} €/kWh**"
        )

    # Tabla comparativa completa
    st.markdown("### 📋 Desglose Completo: Sin Impuestos vs Con Impuestos")
    datos_tabla = [
        {
            "Concepto": "🔴 Punta (P1)",
            "Consumo": f"{kwh_p1:.1f} kWh",
            "% del Mes": f"{pct_p1:.1f} %",
            "Precio sin Imp.": f"{precio_p1_base:.4f} €/kWh",
            "Precio Final con IVA": f"{precio_p1_final:.4f} €/kWh",
            "Gasto Sin Impuestos": f"{gasto_p1_base:.2f} €",
            "Gasto Final (Con Impuestos)": f"{gasto_p1_final:.2f} €"
        },
        {
            "Concepto": "🟠 Llano (P2)",
            "Consumo": f"{kwh_p2:.1f} kWh",
            "% del Mes": f"{pct_p2:.1f} %",
            "Precio sin Imp.": f"{precio_p2_base:.4f} €/kWh",
            "Precio Final con IVA": f"{precio_p2_final:.4f} €/kWh",
            "Gasto Sin Impuestos": f"{gasto_p2_base:.2f} €",
            "Gasto Final (Con Impuestos)": f"{gasto_p2_final:.2f} €"
        },
        {
            "Concepto": "🟢 Valle (P3)",
            "Consumo": f"{kwh_p3:.1f} kWh",
            "% del Mes": f"{pct_p3:.1f} %",
            "Precio sin Imp.": f"{precio_p3_base:.4f} €/kWh",
            "Precio Final con IVA": f"{precio_p3_final:.4f} €/kWh",
            "Gasto Sin Impuestos": f"{gasto_p3_base:.2f} €",
            "Gasto Final (Con Impuestos)": f"{gasto_p3_final:.2f} €"
        },
        {
            "Concepto": "⚡ TOTAL ENERGÍA",
            "Consumo": f"{factura_sel.consumo_total_kwh:.1f} kWh",
            "% del Mes": "100.0 %",
            "Precio sin Imp.": "-",
            "Precio Final con IVA": "-",
            "Gasto Sin Impuestos": f"{total_energia_base:.2f} €",
            "Gasto Final (Con Impuestos)": f"{total_energia_final:.2f} €"
        },
        {
            "Concepto": "🔌 Potencia Contratada (P1 + P2)",
            "Consumo": f"{factura_sel.potencia_p1.potencia_kw:.2f} kW",
            "% del Mes": "-",
            "Precio sin Imp.": "-",
            "Precio Final con IVA": "-",
            "Gasto Sin Impuestos": f"{total_potencia_base:.2f} €",
            "Gasto Final (Con Impuestos)": f"{total_potencia_final:.2f} €"
        },
        {
            "Concepto": "📦 Otros (Alquiler contador + Bono social)",
            "Consumo": "-",
            "% del Mes": "-",
            "Precio sin Imp.": "-",
            "Precio Final con IVA": "-",
            "Gasto Sin Impuestos": f"{otros_base:.2f} €",
            "Gasto Final (Con Impuestos)": f"{otros_final:.2f} €"
        },
        {
            "Concepto": "💶 TOTAL FACTURA",
            "Consumo": f"{factura_sel.consumo_total_kwh:.1f} kWh",
            "% del Mes": "-",
            "Precio sin Imp.": "-",
            "Precio Final con IVA": "-",
            "Gasto Sin Impuestos": f"{(total_energia_base + total_potencia_base + otros_base):.2f} €",
            "Gasto Final (Con Impuestos)": f"{factura_sel.total_factura_eur:.2f} €"
        }
    ]
    df_detalle = pd.DataFrame(datos_tabla)
    st.dataframe(df_detalle, use_container_width=True, hide_index=True)

    st.divider()

    # Gráficos del mes
    col_izq, col_der = st.columns([1, 1])
    
    with col_izq:
        modo_txt = "con Impuestos" if ver_con_impuestos else "sin Impuestos"
        st.markdown(f"#### 💶 Distribución del Gasto ({modo_txt})")
        if ver_con_impuestos:
            vals_costes = [total_energia_final, total_potencia_final, otros_final]
        else:
            vals_costes = [total_energia_base, total_potencia_base, otros_base]
            
        df_pie = pd.DataFrame({
            "Concepto": ["Energía", "Potencia Fija", "Otros (Contador/Bono)"],
            "Importe (€)": vals_costes
        })
        fig_pie = px.pie(
            df_pie, 
            values="Importe (€)", 
            names="Concepto", 
            hole=0.45,
            color_discrete_sequence=px.colors.qualitative.Safe
        )
        st.plotly_chart(fig_pie, use_container_width=True)
        
    with col_der:
        st.markdown(f"#### ⚡ Gasto por Tramo (€ {modo_txt})")
        if ver_con_impuestos:
            vals_tramos = [gasto_p1_final, gasto_p2_final, gasto_p3_final]
        else:
            vals_tramos = [gasto_p1_base, gasto_p2_base, gasto_p3_base]
            
        df_bars = pd.DataFrame({
            "Tramo": ["Punta (P1)", "Llano (P2)", "Valle (P3)"],
            "Gasto (€)": vals_tramos
        })
        fig_bars = px.bar(
            df_bars,
            x="Tramo",
            y="Gasto (€)",
            color="Tramo",
            text="Gasto (€)",
            color_discrete_map={"Punta (P1)": "#EF553B", "Llano (P2)": "#FFA15A", "Valle (P3)": "#00CC96"}
        )
        fig_bars.update_traces(texttemplate='%{text:.2f} €', textposition='outside')
        st.plotly_chart(fig_bars, use_container_width=True)

# ================= SECCIÓN 2: HÁBITOS Y EVOLUCIÓN =================
elif seccion_activa == "📈 Hábitos y Evolución":
    st.subheader(f"Análisis de Hábitos ({factura_sel.fecha_inicio} al {factura_sel.fecha_fin})")
    if pct_p3 >= 70:
        st.success(f"🌟 **¡Hábitos de consumo excelentes!** Concentráis el **{pct_p3:.1f}%** de vuestra energía en horario Valle (el tramo más económico a {precio_p3_final:.4f} €/kWh final). Esta tarifa os resulta sumamente rentable.")
    elif pct_p3 >= 50:
        st.info(f"👍 Buen aprovechamiento: el **{pct_p3:.1f}%** de vuestro consumo está en horario Valle.")
    else:
        st.warning(f"⚠️ Solo el **{pct_p3:.1f}%** de vuestro consumo es en Valle. Os convendría desplazar electrodomésticos de gran consumo a la noche o fines de semana.")

    if len(facturas) > 1:
        st.markdown("---")
        st.markdown("#### 📅 Evolución Histórica de Consumo y Gasto")
        hist_data = []
        for f in sorted(facturas, key=lambda x: x.fecha_inicio):
            hist_data.append({
                "Período": f"{f.fecha_inicio} al {f.fecha_fin}",
                "Factura (€)": f.total_factura_eur,
                "Consumo Total (kWh)": f.consumo_total_kwh,
                "Coste diario (€/día)": f.coste_diario,
                "Punta (kWh)": f.consumo_punta.kwh,
                "Llano (kWh)": f.consumo_llano.kwh,
                "Valle (kWh)": f.consumo_valle.kwh,
                "Coste/kWh (€)": f.coste_medio_kwh
            })
        df_hist = pd.DataFrame(hist_data)
        
        fig_evol = px.line(
            df_hist, 
            x="Período", 
            y=["Factura (€)", "Consumo Total (kWh)"], 
            markers=True, 
            title="Evolución Factura (€) vs Consumo Total (kWh)"
        )
        st.plotly_chart(fig_evol, use_container_width=True)

        st.markdown("#### ⚡ Reparto de Consumo Histórico por Tramos (kWh)")
        fig_tramos = px.bar(
            df_hist,
            x="Período",
            y=["Valle (kWh)", "Llano (kWh)", "Punta (kWh)"],
            title="Consumo por Tramos a lo largo de los meses",
            color_discrete_map={"Punta (kWh)": "#EF553B", "Llano (kWh)": "#FFA15A", "Valle (kWh)": "#00CC96"}
        )
        st.plotly_chart(fig_tramos, use_container_width=True)
    else:
        st.info("ℹ️ Sube más facturas en el menú lateral para ver la comparativa mes a mes.")

# ================= SECCIÓN 3: DIAGNÓSTICO DE POTENCIA =================
elif seccion_activa == "🔌 Diagnóstico de Potencia":
    st.subheader(f"🔌 Optimización de Potencia ({factura_sel.fecha_inicio} al {factura_sel.fecha_fin})")
    st.write("Comparativa entre la potencia contratada que pagas cada mes y el pico máximo real que demandaron tus electrodomésticos en el último año según el contador.")
    
    col_p1, col_p2 = st.columns(2)
    
    pot_cont_p1 = factura_sel.potencia_p1.potencia_kw
    pot_max_p1 = factura_sel.potencia_max_demandada_p1 or 0.0
    
    with col_p1:
        st.markdown("### Horario Punta (P1)")
        st.metric("Potencia Contratada", f"{pot_cont_p1:.2f} kW")
        st.metric("Pico Máximo Demandado", f"{pot_max_p1:.2f} kW")
        
        if pot_max_p1 > pot_cont_p1:
            st.error(f"⚠️ Has alcanzado un pico de **{pot_max_p1:.2f} kW**, superando los {pot_cont_p1:.2f} kW contratados. No te salta el contador porque fue un pico breve dentro de la curva de tolerancia, pero **NO debes bajar la potencia** contratada en P1.")
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
    tabla = []
    for f in sorted(facturas, key=lambda x: x.fecha_inicio):
        tabla.append({
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
            "Coste/kWh": f"{f.coste_medio_kwh:.4f} €"
        })
    df_tabla = pd.DataFrame(tabla)
    st.dataframe(df_tabla, use_container_width=True, hide_index=True)
