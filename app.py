import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from src.parser_naturgy import extraer_factura_naturgy
from src.db import guardar_factura_en_db, obtener_facturas_de_db

# Configuración de la página (optimizada para PC y móvil)
st.set_page_config(
    page_title="Control Facturas de Luz",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Título y encabezado
st.title("⚡ Control y Análisis de Facturas de Luz")
st.caption("Gestiona tu gasto eléctrico doméstico de forma inteligente (PC y Móvil)")

# Barra lateral para subir archivos
with st.sidebar:
    st.header("📥 Cargar Facturas")
    archivos_subidos = st.file_uploader(
        "Sube uno o varios PDFs de Naturgy",
        type=["pdf"],
        accept_multiple_files=True
    )
    st.info("💡 Al subir facturas, se guardan automáticamente en tu base de datos en la nube.")

# Si el usuario sube archivos, se extraen y se guardan en Supabase
if archivos_subidos:
    guardadas_ok = 0
    for archivo in archivos_subidos:
        try:
            f = extraer_factura_naturgy(archivo)
            if guardar_factura_en_db(f):
                guardadas_ok += 1
        except Exception as e:
            st.error(f"Error procesando {archivo.name}: {e}")
    if guardadas_ok > 0:
        st.sidebar.success(f"✅ {guardadas_ok} factura(s) sincronizada(s) en Supabase.")

# Cargar todas las facturas desde Supabase
facturas = obtener_facturas_de_db()

# Si aún no hay conexión a Supabase pero se subieron en memoria:
if not facturas and archivos_subidos:
    for archivo in archivos_subidos:
        try:
            f = extraer_factura_naturgy(archivo)
            facturas.append(f)
        except Exception:
            pass

# Si no hay facturas cargadas, mostramos mensaje de bienvenida
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

# Contador de facturas en la barra lateral
st.sidebar.markdown(f"**Base de datos:** `{len(facturas)} facturas registradas`")

# Ordenar facturas por fecha de inicio (cronológico)
facturas.sort(key=lambda x: x.fecha_inicio)

# ================= SELECTOR DE PERÍODO / MES E IMPUESTOS =================
st.markdown("---")
col_sel, col_imp = st.columns([3, 2])

with col_sel:
    opciones_dict = {
        f"📅 {f.fecha_inicio} al {f.fecha_fin} — {f.total_factura_eur:.2f} € ({f.consumo_total_kwh:.0f} kWh)": f
        for f in reversed(facturas)
    }
    sel_label = st.selectbox(
        "🔎 Selecciona el mes / período que deseas consultar:",
        list(opciones_dict.keys()),
        index=0
    )
    factura_sel = opciones_dict[sel_label]

with col_imp:
    st.write("")
    ver_con_impuestos = st.toggle(
        "🧾 Ver importes con Impuestos (IVA + Elec.)",
        value=True,
        help="Aplica el Impuesto Especial de Electricidad (~5.11%) y el IVA (21%) proporcionales a cada tramo para saber el coste final real."
    )

# ================= CÁLCULO DE RATIOS Y FACTORES DE IMPUESTOS =================
base_energia_pot = factura_sel.total_energia_eur + factura_sel.total_potencia_eur
ratio_iee = (factura_sel.impuesto_electricidad_eur / base_energia_pot) if base_energia_pot > 0 else 0.0511269632
ratio_iva = (factura_sel.iva_eur / factura_sel.base_imponible_eur) if factura_sel.base_imponible_eur > 0 else 0.21

# Multiplicadores
mult_energia_pot = (1.0 + ratio_iee) * (1.0 + ratio_iva)
mult_otros = (1.0 + ratio_iva)

# Cálculos Punta (P1)
kwh_p1 = factura_sel.consumo_punta.kwh
pct_p1 = (kwh_p1 / factura_sel.consumo_total_kwh * 100) if factura_sel.consumo_total_kwh > 0 else 0.0
precio_p1_base = factura_sel.consumo_punta.precio_kwh
precio_p1_final = precio_p1_base * mult_energia_pot
gasto_p1_base = factura_sel.consumo_punta.total_eur
gasto_p1_final = gasto_p1_base * mult_energia_pot

# Cálculos Llano (P2)
kwh_p2 = factura_sel.consumo_llano.kwh
pct_p2 = (kwh_p2 / factura_sel.consumo_total_kwh * 100) if factura_sel.consumo_total_kwh > 0 else 0.0
precio_p2_base = factura_sel.consumo_llano.precio_kwh
precio_p2_final = precio_p2_base * mult_energia_pot
gasto_p2_base = factura_sel.consumo_llano.total_eur
gasto_p2_final = gasto_p2_base * mult_energia_pot

# Cálculos Valle (P3)
kwh_p3 = factura_sel.consumo_valle.kwh
pct_p3 = (kwh_p3 / factura_sel.consumo_total_kwh * 100) if factura_sel.consumo_total_kwh > 0 else 0.0
precio_p3_base = factura_sel.consumo_valle.precio_kwh
precio_p3_final = precio_p3_base * mult_energia_pot
gasto_p3_base = factura_sel.consumo_valle.total_eur
gasto_p3_final = gasto_p3_base * mult_energia_pot

# Totales energía, potencia y otros
total_energia_base = factura_sel.total_energia_eur
total_energia_final = gasto_p1_final + gasto_p2_final + gasto_p3_final

total_potencia_base = factura_sel.total_potencia_eur
total_potencia_final = total_potencia_base * mult_energia_pot

otros_base = factura_sel.bono_social_eur + factura_sel.alquiler_contador_eur
otros_final = otros_base * mult_otros

# Pestañas de navegación
tab_resumen, tab_graficos, tab_potencia, tab_historico = st.tabs([
    "📊 Consulta del Mes", 
    "📈 Hábitos y Evolución", 
    "🔌 Diagnóstico de Potencia", 
    "📋 Histórico Completo"
])

# ================= TAB 1: CONSULTA DEL MES =================
with tab_resumen:
    st.subheader(f"Período: {factura_sel.fecha_inicio} al {factura_sel.fecha_fin} ({factura_sel.dias_facturados} días)")
    st.caption(f"**Tarifa:** {factura_sel.tarifa} | **Factura Nº:** `{factura_sel.numero_factura}` | **CUPS:** `{factura_sel.cups or 'No detectado'}`")
    
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
        f"{(total_energia_final if ver_con_impuestos else total_energia_base):.2f} €", 
        f"{'Con Impuestos' if ver_con_impuestos else 'Sin Impuestos'}",
        delta_color="off"
    )
    
    st.divider()

    # Tarjetas rápidas de los 3 tramos
    st.markdown("### ⚡ Consumo y Gasto por Tramo")
    col_t1, col_t2, col_t3 = st.columns(3)
    
    with col_t1:
        gasto_p1 = gasto_p1_final if ver_con_impuestos else gasto_p1_base
        precio_p1 = precio_p1_final if ver_con_impuestos else precio_p1_base
        st.error(f"#### 🔴 Punta (P1)\n"
                 f"**Consumo:** {kwh_p1:.1f} kWh ({pct_p1:.1f}%)\n\n"
                 f"**Gasto:** **{gasto_p1:.2f} €**\n\n"
                 f"**Precio:** {precio_p1:.4f} €/kWh")
                 
    with col_t2:
        gasto_p2 = gasto_p2_final if ver_con_impuestos else gasto_p2_base
        precio_p2 = precio_p2_final if ver_con_impuestos else precio_p2_base
        st.warning(f"#### 🟠 Llano (P2)\n"
                   f"**Consumo:** {kwh_p2:.1f} kWh ({pct_p2:.1f}%)\n\n"
                   f"**Gasto:** **{gasto_p2:.2f} €**\n\n"
                   f"**Precio:** {precio_p2:.4f} €/kWh")
                   
    with col_t3:
        gasto_p3 = gasto_p3_final if ver_con_impuestos else gasto_p3_base
        precio_p3 = precio_p3_final if ver_con_impuestos else precio_p3_base
        st.success(f"#### 🟢 Valle (P3)\n"
                   f"**Consumo:** {kwh_p3:.1f} kWh ({pct_p3:.1f}%)\n\n"
                   f"**Gasto:** **{gasto_p3:.2f} €**\n\n"
                   f"**Precio:** {precio_p3:.4f} €/kWh")

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

# ================= TAB 2: HÁBITOS Y EVOLUCIÓN =================
with tab_graficos:
    st.subheader(f"Análisis de Hábitos ({factura_sel.fecha_inicio} a {factura_sel.fecha_fin})")
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
        for f in facturas:
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

# ================= TAB 3: DIAGNÓSTICO DE POTENCIA =================
with tab_potencia:
    st.subheader(f"🔌 Optimización de Potencia ({factura_sel.fecha_inicio} a {factura_sel.fecha_fin})")
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
            ahorro = (pot_cont_p1 - pot_max_p1) * 365 * factura_sel.potencia_p1.precio_kw_dia * mult_energia_pot
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

# ================= TAB 4: HISTÓRICO TABULAR =================
with tab_historico:
    st.subheader("📋 Registro de Facturas Analizadas")
    tabla = []
    for f in facturas:
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
