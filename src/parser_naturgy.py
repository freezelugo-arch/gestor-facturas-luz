import io
import re
from pathlib import Path
from typing import Optional, Union

import pdfplumber

try:
    from .models import DetallePotencia, DetalleTramo, FacturaLuz
except ImportError:
    from models import DetallePotencia, DetalleTramo, FacturaLuz


def _to_float(valor_str: str) -> float:
    """Convierte importes y números en formato español (coma decimal) a float."""
    if not valor_str:
        return 0.0
    limpio = valor_str.strip()
    if "." in limpio and "," in limpio:
        limpio = limpio.replace(".", "").replace(",", ".")
    elif "," in limpio:
        limpio = limpio.replace(",", ".")
    return float(limpio)


def fecha_es_a_iso(fecha_str: Optional[str]) -> Optional[str]:
    """Convierte 'DD/MM/YYYY' a 'YYYY-MM-DD' para ordenar correctamente en BD."""
    if not fecha_str:
        return None
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", fecha_str.strip())
    if not m:
        return fecha_str
    dia, mes, anio = m.groups()
    return f"{anio}-{mes}-{dia}"


def extraer_factura_naturgy(pdf_input: Union[str, Path, bytes, io.BytesIO]) -> FacturaLuz:
    """
    Lee un PDF de Naturgy y extrae todos sus datos estructurados.
    """
    texto_completo = ""
    with pdfplumber.open(pdf_input) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                texto_completo += t + "\n"

    # 1. Identificación básica
    num_factura = re.search(r"N\.\º\s*de\s*factura:\s*([A-Z0-9]+)", texto_completo)
    num_factura = num_factura.group(1) if num_factura else "DESCONOCIDO"

    fecha_emision = re.search(r"Fecha\s*de\s*emisión:\s*(\d{2}/\d{2}/\d{4})", texto_completo)
    fecha_emision = fecha_emision.group(1) if fecha_emision else None

    # Período: del 24/07/2026 al 24/08/2026
    periodo = re.search(
        r"Período\s*electricidad(?:\s*del)?\s*(\d{2}/\d{2}/\d{4})\s*al\s*(\d{2}/\d{2}/\d{4})",
        texto_completo,
    )
    f_inicio = periodo.group(1) if periodo else "01/01/2000"
    f_fin = periodo.group(2) if periodo else "01/01/2000"

    # Días exactos facturados
    dias_match = re.search(r"Término\s*potencia\s*P1.*?x\s*(\d+)\s*días", texto_completo)
    if not dias_match:
        dias_match = re.search(r"Contrato:.*?\n\s*(\d+)\s*días", texto_completo)
    dias_facturados = int(dias_match.group(1)) if dias_match else 30

    cups = re.search(r"Código\s*CUPS:\s*([A-Z0-9]+)", texto_completo)
    cups = cups.group(1) if cups else None

    # Tarifa limpia
    tarifa_match = re.search(r"(Tarifa\s+[\w\s]+?ECO)", texto_completo)
    if tarifa_match:
        tarifa = " ".join(tarifa_match.group(1).split())
    else:
        tarifa = "Tarifa Naturgy"

    # 2. Consumo por tramos (Punta, Llano, Valle)
    def extraer_tramo(nombre: str) -> DetalleTramo:
        patron = rf"Consumo\s*electricidad\s*{nombre}\s*([\d,.]+)\s*kWh\s*x\s*([\d,.]+)\s*€/kWh\s*([\d,.]+)\s*€"
        m = re.search(patron, texto_completo)
        if m:
            return DetalleTramo(
                kwh=_to_float(m.group(1)),
                precio_kwh=_to_float(m.group(2)),
                total_eur=_to_float(m.group(3)),
            )
        return DetalleTramo(kwh=0.0, precio_kwh=0.0, total_eur=0.0)

    punta = extraer_tramo("Punta")
    llano = extraer_tramo("Llano")
    valle = extraer_tramo("Valle")
    total_kwh = round(punta.kwh + llano.kwh + valle.kwh, 2)
    total_energia = round(punta.total_eur + llano.total_eur + valle.total_eur, 2)

    # 3. Término de potencia
    def extraer_potencia(periodo_p: str) -> DetallePotencia:
        patron = (
            rf"Término\s*potencia\s*{periodo_p}\s*([\d,.]+)\s*kW\s*x\s*(\d+)\s*días\s*x\s*"
            rf"([\d,.]+)\s*€/kW\s*día\s*([\d,.]+)\s*€"
        )
        m = re.search(patron, texto_completo)
        if m:
            return DetallePotencia(
                potencia_kw=_to_float(m.group(1)),
                dias=int(m.group(2)),
                precio_kw_dia=_to_float(m.group(3)),
                total_eur=_to_float(m.group(4)),
            )
        return DetallePotencia(potencia_kw=0.0, dias=dias_facturados, precio_kw_dia=0.0, total_eur=0.0)

    pot_p1 = extraer_potencia("P1")
    pot_p2 = extraer_potencia("P2")
    total_potencia = round(pot_p1.total_eur + pot_p2.total_eur, 2)

    # 4. Otros importes e impuestos
    bono = re.search(r"Financiación\s*de\s*Bono\s*Social.*?([\d,.]+)\s*€", texto_completo)
    bono_eur = _to_float(bono.group(1)) if bono else 0.0

    imp_elec = re.search(r"Impuesto\s*electricidad.*?%\s*([\d,.]+)\s*€", texto_completo)
    imp_elec_eur = _to_float(imp_elec.group(1)) if imp_elec else 0.0

    alquiler = re.search(r"Alquiler\s*de\s*contador.*?([\d,.]+)\s*€", texto_completo)
    alquiler_eur = _to_float(alquiler.group(1)) if alquiler else 0.0

    base = re.search(r"Total\s*base\s*imponible\s*([\d,.]+)\s*€", texto_completo)
    if not base:
        base = re.search(r"Total\s*electricidad\s*([\d,.]+)\s*€", texto_completo)
    base_eur = _to_float(base.group(1)) if base else 0.0

    iva = re.search(r"IVA\s*\(\d+%\).*?%\s*([\d,.]+)\s*€", texto_completo)
    iva_eur = _to_float(iva.group(1)) if iva else 0.0

    total = re.search(r"Total\s*a\s*pagar\s*([\d,.]+)\s*€", texto_completo)
    total_eur = _to_float(total.group(1)) if total else 0.0

    # 5. Potencias máximas demandadas
    pmax = re.search(
        r"máximas\s*demandadas.*?([\d,.]+)\s*kW\s*en\s*P1.*?([\d,.]+)\s*kW\s*en\s*P2",
        texto_completo,
    )
    pmax_p1 = _to_float(pmax.group(1)) if pmax else None
    pmax_p2 = _to_float(pmax.group(2)) if pmax else None

    return FacturaLuz(
        numero_factura=num_factura,
        fecha_emision=fecha_emision,
        fecha_inicio=f_inicio,
        fecha_fin=f_fin,
        dias_facturados=dias_facturados,
        cups=cups,
        tarifa=tarifa,
        consumo_punta=punta,
        consumo_llano=llano,
        consumo_valle=valle,
        consumo_total_kwh=total_kwh,
        total_energia_eur=total_energia,
        potencia_p1=pot_p1,
        potencia_p2=pot_p2,
        total_potencia_eur=total_potencia,
        bono_social_eur=bono_eur,
        impuesto_electricidad_eur=imp_elec_eur,
        alquiler_contador_eur=alquiler_eur,
        base_imponible_eur=base_eur,
        iva_eur=iva_eur,
        total_factura_eur=total_eur,
        potencia_max_demandada_p1=pmax_p1,
        potencia_max_demandada_p2=pmax_p2,
    )