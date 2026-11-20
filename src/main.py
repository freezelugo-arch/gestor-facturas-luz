import sys
from pathlib import Path
from parser_naturgy import extraer_factura_naturgy

def main():
    carpeta_facturas = Path("facturas")
    
    if not carpeta_facturas.exists():
        carpeta_facturas.mkdir(parents=True, exist_ok=True)
        
    archivos_pdf = list(carpeta_facturas.glob("*.pdf"))

    if not archivos_pdf:
        print("⚠️ No se encontraron archivos .pdf dentro de la carpeta 'facturas/'.")
        print("Copia tu factura dentro de la carpeta 'facturas/' y vuelve a ejecutar.")
        return

    for ruta_pdf in archivos_pdf:
        print("\n" + "=" * 55)
        print(f"📄 Procesando: {ruta_pdf.name}")
        print("=" * 55)
        
        try:
            factura = extraer_factura_naturgy(ruta_pdf)
            
            print(f"Número de Factura: {factura.numero_factura}")
            print(f"Período:           {factura.fecha_inicio} al {factura.fecha_fin} ({factura.dias_facturados} días)")
            print(f"Tarifa:            {factura.tarifa}")
            print(f"CUPS:              {factura.cups}")
            print("-" * 55)
            print(f"⚡ Consumo Total:   {factura.consumo_total_kwh} kWh ({factura.total_energia_eur} €)")
            print(f"   • Punta (P1):   {factura.consumo_punta.kwh} kWh ({factura.consumo_punta.total_eur} €)")
            print(f"   • Llano (P2):   {factura.consumo_llano.kwh} kWh ({factura.consumo_llano.total_eur} €)")
            print(f"   • Valle (P3):   {factura.consumo_valle.kwh} kWh ({factura.consumo_valle.total_eur} €) -> {factura.porcentaje_valle}% del consumo")
            print("-" * 55)
            print(f"🔌 Potencia P1/P2:  {factura.potencia_p1.potencia_kw} kW / {factura.potencia_p2.potencia_kw} kW ({factura.total_potencia_eur} €)")
            print(f"📊 Picos demanda:   P1: {factura.potencia_max_demandada_p1} kW | P2: {factura.potencia_max_demandada_p2} kW")
            print("-" * 55)
            print(f"💶 TOTAL FACTURA:   {factura.total_factura_eur} €")
            print(f"   • Coste diario:  {factura.coste_diario} €/día")
            print(f"   • Coste kWh:     {factura.coste_medio_kwh} €/kWh")
            
        except Exception as e:
            print(f"❌ Error al procesar {ruta_pdf.name}: {e}")

if __name__ == "__main__":
    main()