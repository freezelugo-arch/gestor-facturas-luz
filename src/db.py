import os
from datetime import datetime
from typing import List, Optional

from dotenv import load_dotenv
from supabase import Client, create_client

try:
    from .models import DetallePotencia, DetalleTramo, FacturaLuz
except ImportError:
    from models import DetallePotencia, DetalleTramo, FacturaLuz

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")


def get_supabase_client() -> Optional[Client]:
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    try:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"Error conectando a Supabase: {e}")
        return None


def _clave_orden_fecha(fecha_str: Optional[str]) -> tuple:
    """Devuelve una clave cronológica tanto para 'DD/MM/YYYY' como para 'YYYY-MM-DD'."""
    if not fecha_str:
        return (0, 0, 0)
    s = fecha_str.strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s, fmt)
            return (dt.year, dt.month, dt.day)
        except ValueError:
            continue
    return (0, 0, 0)


def guardar_factura_en_db(factura: FacturaLuz) -> bool:
    """Guarda o actualiza una factura en la base de datos Supabase."""
    client = get_supabase_client()
    if not client:
        return False

    registro = {
        "numero_factura": factura.numero_factura,
        "compania": factura.compania,
        "fecha_emision": factura.fecha_emision,
        "fecha_inicio": factura.fecha_inicio,
        "fecha_fin": factura.fecha_fin,
        "dias_facturados": factura.dias_facturados,
        "cups": factura.cups,
        "tarifa": factura.tarifa,
        "consumo_total_kwh": factura.consumo_total_kwh,
        "total_energia_eur": factura.total_energia_eur,
        "consumo_punta_kwh": factura.consumo_punta.kwh,
        "consumo_punta_eur": factura.consumo_punta.total_eur,
        "precio_punta_eur_kwh": factura.consumo_punta.precio_kwh,
        "consumo_llano_kwh": factura.consumo_llano.kwh,
        "consumo_llano_eur": factura.consumo_llano.total_eur,
        "precio_llano_eur_kwh": factura.consumo_llano.precio_kwh,
        "consumo_valle_kwh": factura.consumo_valle.kwh,
        "consumo_valle_eur": factura.consumo_valle.total_eur,
        "precio_valle_eur_kwh": factura.consumo_valle.precio_kwh,
        "potencia_p1_kw": factura.potencia_p1.potencia_kw,
        "precio_pot_p1_dia": factura.potencia_p1.precio_kw_dia,
        "potencia_p2_kw": factura.potencia_p2.potencia_kw,
        "precio_pot_p2_dia": factura.potencia_p2.precio_kw_dia,
        "total_potencia_eur": factura.total_potencia_eur,
        "potencia_max_p1": factura.potencia_max_demandada_p1,
        "potencia_max_p2": factura.potencia_max_demandada_p2,
        "bono_social_eur": factura.bono_social_eur,
        "impuesto_elec_eur": factura.impuesto_electricidad_eur,
        "alquiler_contador_eur": factura.alquiler_contador_eur,
        "base_imponible_eur": factura.base_imponible_eur,
        "iva_eur": factura.iva_eur,
        "total_factura_eur": factura.total_factura_eur,
    }

    try:
        client.table("facturas").upsert(registro, on_conflict="numero_factura").execute()
        return True
    except Exception as e:
        try:
            reg_compat = {k: v for k, v in registro.items() if not k.startswith("precio_")}
            client.table("facturas").upsert(reg_compat, on_conflict="numero_factura").execute()
            return True
        except Exception as e2:
            print(f"Error guardando factura: {e2}")
        print(f"Error guardando factura {factura.numero_factura}: {e}")
        return False


def obtener_facturas_de_db() -> List[FacturaLuz]:
    """Recupera todas las facturas guardadas en Supabase ordenadas cronológicamente."""
    client = get_supabase_client()
    if not client:
        return []

    try:
        res = client.table("facturas").select("*").execute()
        filas = res.data or []
        filas.sort(key=lambda x: _clave_orden_fecha(x.get("fecha_inicio")))
        facturas = []
        for r in filas:
            kwh_p = float(r.get("consumo_punta_kwh") or 0.0)
            eur_p = float(r.get("consumo_punta_eur") or 0.0)
            p_unit = float(r.get("precio_punta_eur_kwh") or 0.0)
            if p_unit == 0.0 and kwh_p > 0:
                p_unit = round(eur_p / kwh_p, 6)

            kwh_l = float(r.get("consumo_llano_kwh") or 0.0)
            eur_l = float(r.get("consumo_llano_eur") or 0.0)
            l_unit = float(r.get("precio_llano_eur_kwh") or 0.0)
            if l_unit == 0.0 and kwh_l > 0:
                l_unit = round(eur_l / kwh_l, 6)

            kwh_v = float(r.get("consumo_valle_kwh") or 0.0)
            eur_v = float(r.get("consumo_valle_eur") or 0.0)
            v_unit = float(r.get("precio_valle_eur_kwh") or 0.0)
            if v_unit == 0.0 and kwh_v > 0:
                v_unit = round(eur_v / kwh_v, 6)

            dias = int(r.get("dias_facturados") or 1)
            pot1 = float(r.get("potencia_p1_kw") or 0.0)
            pot1_dia = float(r.get("precio_pot_p1_dia") or 0.0)
            pot2 = float(r.get("potencia_p2_kw") or 0.0)
            pot2_dia = float(r.get("precio_pot_p2_dia") or 0.0)
            tot_pot = float(r.get("total_potencia_eur") or 0.0)

            eur_pot1 = round(pot1 * dias * pot1_dia, 2) if pot1_dia > 0 else 0.0
            eur_pot2 = round(pot2 * dias * pot2_dia, 2) if pot2_dia > 0 else 0.0
            if eur_pot1 == 0.0 and eur_pot2 == 0.0 and tot_pot > 0.0:
                eur_pot1 = round(tot_pot / 2.0, 2)
                eur_pot2 = round(tot_pot - eur_pot1, 2)

            f = FacturaLuz(
                compania=r.get("compania") or "Naturgy",
                numero_factura=r.get("numero_factura"),
                fecha_emision=r.get("fecha_emision"),
                fecha_inicio=r.get("fecha_inicio"),
                fecha_fin=r.get("fecha_fin"),
                dias_facturados=dias,
                cups=r.get("cups"),
                tarifa=r.get("tarifa"),
                consumo_punta=DetalleTramo(kwh=kwh_p, precio_kwh=p_unit, total_eur=eur_p),
                consumo_llano=DetalleTramo(kwh=kwh_l, precio_kwh=l_unit, total_eur=eur_l),
                consumo_valle=DetalleTramo(kwh=kwh_v, precio_kwh=v_unit, total_eur=eur_v),
                consumo_total_kwh=float(r.get("consumo_total_kwh") or 0.0),
                total_energia_eur=float(r.get("total_energia_eur") or 0.0),
                potencia_p1=DetallePotencia(
                    potencia_kw=pot1, dias=dias, precio_kw_dia=pot1_dia, total_eur=eur_pot1
                ),
                potencia_p2=DetallePotencia(
                    potencia_kw=pot2, dias=dias, precio_kw_dia=pot2_dia, total_eur=eur_pot2
                ),
                total_potencia_eur=tot_pot,
                bono_social_eur=float(r.get("bono_social_eur") or 0.0),
                impuesto_electricidad_eur=float(r.get("impuesto_elec_eur") or 0.0),
                alquiler_contador_eur=float(r.get("alquiler_contador_eur") or 0.0),
                base_imponible_eur=float(r.get("base_imponible_eur") or 0.0),
                iva_eur=float(r.get("iva_eur") or 0.0),
                total_factura_eur=float(r.get("total_factura_eur") or 0.0),
                potencia_max_demandada_p1=(
                    float(r.get("potencia_max_p1")) if r.get("potencia_max_p1") is not None else None
                ),
                potencia_max_demandada_p2=(
                    float(r.get("potencia_max_p2")) if r.get("potencia_max_p2") is not None else None
                ),
            )
            facturas.append(f)
        return facturas
    except Exception as e:
        print(f"Error obteniendo facturas de Supabase: {e}")
        return []