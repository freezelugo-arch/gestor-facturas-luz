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

# Ordenar facturas por fecha de inicio
facturas.sort(key=lambda x: x.fecha_inicio)

# Pestañas de navegación
tab_resumen, tab_graficos, tab_potencia, tab_historico = st.tabs([
    "📊 Última Factura", 
    "📈 Hábitos de Consumo", 
    "🔌 Diagnóstico de Potencia", 
    "📋 Histórico Completo"
])

# Tomamos la factura más reciente
ult = facturas[-1]

# ================= TAB 1: RESUMEN =================
with tab_resumen:
    st.subheader(f"Período: {ult.fecha_inicio} al {ult.fecha_fin} ({ult.dias_facturados} días)")
    st.write(f"**Tarifa:** {ult.tarifa} | **Factura Nº:** `{ult.numero_factura}` | **CUPS:** `{ult.cups or 'No detectado'}`")
    
    # Tarjetas métricas superiores
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Factura", f"{ult.total_factura_eur:.2f} €", delta=f"{ult.coste_diario:.2f} €/día", delta_color="off")
    col2.metric("Consumo Total", f"{ult.consumo_total_kwh:.0f} kWh", f"{ult.consumo_valle.kwh:.0f} kWh en Valle")
    col3.metric("Precio Medio Real", f"{ult.coste_medio_kwh:.4f} €/kWh", "Todo incluido")
    col4.metric("% en Horario Valle", f"{ult.porcentaje_valle:.1f} %", "Objetivo > 60%", delta_color="normal")
    
    st.divider()
    
    col_izq, col_der = st.columns([1, 1])
    
    with col_izq:
        st.markdown("#### 💶 Desglose de Costes")
        datos_costes = {
            "Concepto": ["Energía consumida", "Potencia (fijo)", "Impuestos (IVA + Elec.)", "Otros (Bono/Contador)"],
            "Importe (€)": [
                ult.total_energia_eur,
                ult.total_potencia_eur,
                round(ult.iva_eur + ult.impuesto_electricidad_eur, 2),
                round(ult.bono_social_eur + ult.alquiler_contador_eur, 2)
            ]
        }
        df_costes = pd.DataFrame(datos_costes)
        fig_costes = px.pie(
            df_costes, 
            values="Importe (€)", 
            names="Concepto", 
            hole=0.45,
            color_discrete_sequence=px.colors.qualitative.Safe
        )
        st.plotly_chart(fig_costes, use_container_width=True)
        
    with col_der:
        st.markdown("#### ⚡ Reparto de Consumo por Tramos")
        datos_kwh = {
            "Tramo": ["Punta (P1)", "Llano (P2)", "Valle (P3)"],
            "kWh": [ult.consumo_punta.kwh, ult.consumo_llano.kwh, ult.consumo_valle.kwh],
            "Precio (€/kWh)": [ult.consumo_punta.precio_kwh, ult.consumo_llano.precio_kwh, ult.consumo_valle.precio_kwh]
        }
        df_kwh = pd.DataFrame(datos_kwh)
        fig_kwh = px.bar(
            df_kwh, 
            x="Tramo", 
            y="kWh", 
            color="Tramo", 
            text="kWh",
            color_discrete_map={"Punta (P1)": "#EF553B", "Llano (P2)": "#FFA15A", "Valle (P3)": "#00CC96"}
        )
        fig_kwh.update_traces(textposition='outside')
        st.plotly_chart(fig_kwh, use_container_width=True)

# ================= TAB 2: HÁBITOS DE CONSUMO =================
with tab_graficos:
    st.subheader("Análisis de Eficiencia y Hábitos")
    if ult.porcentaje_valle >= 70:
        st.success(f"🌟 **¡Hábitos de consumo excelentes!** Concentráis el **{ult.porcentaje_valle}%** de vuestra energía en horario Valle (el tramo más económico a {ult.consumo_valle.precio_kwh:.4f} €/kWh). Esta tarifa os resulta muy rentable.")
    elif ult.porcentaje_valle >= 50:
        st.info(f"👍 Buen aprovechamiento: el {ult.porcentaje_valle}% de vuestro consumo está en horario Valle.")
    else:
        st.warning(f"⚠️ Solo el {ult.porcentaje_valle}% de vuestro consumo es en Valle. Os convendría desplazar electrodomésticos de gran consumo a la noche o fines de semana.")

    # Si se cargan 2 o más facturas, mostramos evolución
    if len(facturas) > 1:
        st.markdown("#### 📅 Evolución Histórica de Consumo y Gasto")
        hist_data = []
        for f in facturas:
            hist_data.append({
                "Período": f"{f.fecha_inicio} a {f.fecha_fin}",
                "Factura (€)": f.total_factura_eur,
                "Consumo (kWh)": f.consumo_total_kwh,
                "Coste diario (€)": f.coste_diario,
                "Punta (kWh)": f.consumo_punta.kwh,
                "Llano (kWh)": f.consumo_llano.kwh,
                "Valle (kWh)": f.consumo_valle.kwh,
            })
        df_hist = pd.DataFrame(hist_data)
        
        fig_evol = px.line(
            df_hist, 
            x="Período", 
            y=["Factura (€)", "Consumo (kWh)"], 
            markers=True, 
            title="Evolución Factura vs Consumo Total"
        )
        st.plotly_chart(fig_evol, use_container_width=True)
    else:
        st.info("ℹ️ Sube más facturas en el menú lateral para ver aquí la comparativa mes a mes.")

# ================= TAB 3: DIAGNÓSTICO DE POTENCIA =================
with tab_potencia:
    st.subheader("🔌 Optimización de Potencia Contratada")
    st.write("Comparativa entre la potencia contratada que pagas cada mes y el pico máximo real que demandaron tus electrodomésticos en el último año según el contador.")
    
    col_p1, col_p2 = st.columns(2)
    
    pot_cont_p1 = ult.potencia_p1.potencia_kw
    pot_max_p1 = ult.potencia_max_demandada_p1 or 0.0
    
    with col_p1:
        st.markdown("### Horario Punta (P1)")
        st.metric("Potencia Contratada", f"{pot_cont_p1:.2f} kW")
        st.metric("Pico Máximo Demandado", f"{pot_max_p1:.2f} kW")
        
        if pot_max_p1 > pot_cont_p1:
            st.error(f"⚠️ Has alcanzado un pico de **{pot_max_p1:.2f} kW**, superando los {pot_cont_p1:.2f} kW contratados. No te salta el contador porque fue un pico breve dentro de la curva de tolerancia, pero **NO debes bajar la potencia** contratada en P1.")
        elif pot_max_p1 > (pot_cont_p1 * 0.85):
            st.success("✅ Potencia muy bien ajustada. Estás aprovechando tu potencia sin riesgo de cortes.")
        else:
            ahorro = (pot_cont_p1 - pot_max_p1) * 365 * ult.potencia_p1.precio_kw_dia * 1.21
            st.warning(f"💡 Podrías reducir potencia y ahorrar aproximadamente **{ahorro:.2f} €/año**.")
            
    with col_p2:
        pot_cont_p2 = ult.potencia_p2.potencia_kw
        pot_max_p2 = ult.potencia_max_demandada_p2 or 0.0
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
    st.dataframe(df_tabla, use_container_width=True)