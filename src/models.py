from pydantic import BaseModel
from typing import Optional

class DetalleTramo(BaseModel):
    kwh: float
    precio_kwh: float
    total_eur: float

class DetallePotencia(BaseModel):
    potencia_kw: float
    dias: int
    precio_kw_dia: float
    total_eur: float

class FacturaLuz(BaseModel):
    # Identificación
    compania: str = "Naturgy"
    numero_factura: str
    fecha_emision: Optional[str] = None
    fecha_inicio: str
    fecha_fin: str
    dias_facturados: int
    cups: Optional[str] = None
    tarifa: Optional[str] = None
    
    # Consumo (Energía variable)
    consumo_punta: DetalleTramo
    consumo_llano: DetalleTramo
    consumo_valle: DetalleTramo
    consumo_total_kwh: float
    total_energia_eur: float
    
    # Potencia (Coste fijo)
    potencia_p1: DetallePotencia
    potencia_p2: DetallePotencia
    total_potencia_eur: float
    
    # Impuestos y conceptos regulados
    bono_social_eur: float
    impuesto_electricidad_eur: float
    alquiler_contador_eur: float
    base_imponible_eur: float
    iva_eur: float
    total_factura_eur: float
    
    # Picos máximos registrados en el contador en el último año
    potencia_max_demandada_p1: Optional[float] = None
    potencia_max_demandada_p2: Optional[float] = None
    
    # Métricas calculadas automáticamente
    @property
    def coste_diario(self) -> float:
        if self.dias_facturados > 0:
            return round(self.total_factura_eur / self.dias_facturados, 2)
        return 0.0

    @property
    def coste_medio_kwh(self) -> float:
        if self.consumo_total_kwh > 0:
            return round(self.total_factura_eur / self.consumo_total_kwh, 4)
        return 0.0

    @property
    def porcentaje_valle(self) -> float:
        if self.consumo_total_kwh > 0:
            return round((self.consumo_valle.kwh / self.consumo_total_kwh) * 100, 1)
        return 0.0