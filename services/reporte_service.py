import logging
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import func

from database.db import db
from models.cliente import Cliente
from models.cita import Cita
from models.factura import Factura, FacturaDetalle
from models.orden_trabajo import OrdenTrabajo
from models.mecanico import Mecanico
from models.servicio import Servicio
from models.movimiento_inventario import MovimientoInventario
from models.inventario import Inventario
from services.inventario_service import InventarioService

logger = logging.getLogger("siam.reporte_service")


@dataclass
class ReporteData:
    desde: date | None = None
    hasta: date | None = None
    facturas_periodo: int = 0
    ingresos: float = 0.0
    cartera: float = 0.0
    ticket_promedio: float = 0.0
    ots_entregadas: int = 0
    ingresos_por_dia: list = field(default_factory=list)
    ingresos_por_metodo: list = field(default_factory=list)
    facturacion_clientes: list = field(default_factory=list)
    servicios_vendidos: list = field(default_factory=list)
    ots_por_estado: list = field(default_factory=list)
    productividad_mecanicos: list = field(default_factory=list)
    movimientos_inventario: dict = field(default_factory=dict)
    valor_inventario: float = 0.0


class ReporteService:

    @staticmethod
    def _rango(desde: date | None, hasta: date | None) -> tuple[date | None, date | None]:
        return desde, hasta

    @staticmethod
    def _facturas_filtradas(desde: date | None, hasta: date | None):
        q = Factura.query.filter(Factura.estado != "anulado")
        if desde:
            q = q.filter(func.date(Factura.created_at) >= desde)
        if hasta:
            q = q.filter(func.date(Factura.created_at) <= hasta)
        return q

    @staticmethod
    def ingresos(desde: date | None = None, hasta: date | None = None) -> float:
        """Suma de facturas pagadas/parciales (ingresos reconocidos)."""
        facturas = ReporteService._facturas_filtradas(desde, hasta).all()
        validas = [f for f in facturas if f.estado in ("pagado", "parcial")]
        return float(sum((f.total for f in validas), Decimal("0")))

    @staticmethod
    def cartera() -> float:
        """Cuentas por cobrar actuales (pendiente + parcial)."""
        pendientes = Factura.query.filter(Factura.estado.in_(["pendiente", "parcial"])).all()
        return float(sum((f.saldo_pendiente for f in pendientes), Decimal("0")))

    @staticmethod
    def ingresos_por_metodo(desde: date | None = None, hasta: date | None = None) -> list:
        """Ingresos reconocidos agrupados por método de pago."""
        q = db.session.query(
            Factura.metodo_pago,
            func.coalesce(func.sum(Factura.total), 0).label("total"),
        ).filter(Factura.estado.in_(["pagado", "parcial"]), Factura.metodo_pago.isnot(None))
        if desde:
            q = q.filter(func.date(Factura.created_at) >= desde)
        if hasta:
            q = q.filter(func.date(Factura.created_at) <= hasta)
        return [
            (row.metodo_pago, float(row.total))
            for row in q.group_by(Factura.metodo_pago).order_by(func.sum(Factura.total).desc()).all()
        ]

    @staticmethod
    def build_resumen(desde: date | None = None, hasta: date | None = None) -> ReporteData:
        data = ReporteData(desde=desde, hasta=hasta)
        facturas = ReporteService._facturas_filtradas(desde, hasta).all()

        facturas_validas = [f for f in facturas if f.estado in ("pagado", "parcial")]
        data.facturas_periodo = len(facturas)
        data.ingresos = ReporteService.ingresos(desde, hasta)
        data.ots_entregadas = OrdenTrabajo.query.filter(OrdenTrabajo.estado == "entregado").count()
        data.ticket_promedio = data.ingresos / len(facturas_validas) if facturas_validas else 0.0

        data.cartera = ReporteService.cartera()

        d, h = ReporteService._rango(desde, hasta)
        q = db.session.query(
            func.date(Factura.created_at).label("dia"),
            func.sum(Factura.total).label("total"),
        ).filter(Factura.estado.in_(["pagado", "parcial"]))
        if d:
            q = q.filter(func.date(Factura.created_at) >= d)
        if h:
            q = q.filter(func.date(Factura.created_at) <= h)
        data.ingresos_por_dia = [
            (str(row.dia), float(row.total))
            for row in q.group_by(func.date(Factura.created_at)).order_by(func.date(Factura.created_at)).all()
        ]

        data.ingresos_por_metodo = ReporteService.ingresos_por_metodo(d, h)

        q_clientes = db.session.query(
            Cliente.nombre,
            func.count(Factura.id).label("n_facturas"),
            func.coalesce(func.sum(Factura.total), 0).label("total"),
        ).join(Cita, Cita.id == Factura.cita_id).join(Cliente, Cliente.id == Cita.cliente_id)
        q_clientes = q_clientes.filter(Factura.estado != "anulado")
        if d:
            q_clientes = q_clientes.filter(func.date(Factura.created_at) >= d)
        if h:
            q_clientes = q_clientes.filter(func.date(Factura.created_at) <= h)
        data.facturacion_clientes = [
            {"cliente": row.nombre, "facturas": int(row.n_facturas), "total": float(row.total)}
            for row in q_clientes.group_by(Cliente.id, Cliente.nombre)
            .order_by(func.sum(Factura.total).desc()).limit(10).all()
        ]

        q_servicios = db.session.query(
            Servicio.nombre,
            func.coalesce(func.sum(FacturaDetalle.cantidad), 0).label("cantidad"),
            func.coalesce(func.sum(FacturaDetalle.subtotal), 0).label("total"),
        ).join(FacturaDetalle, Servicio.id == FacturaDetalle.servicio_id)
        q_servicios = q_servicios.join(Factura, Factura.id == FacturaDetalle.factura_id)
        q_servicios = q_servicios.filter(Factura.estado != "anulado")
        if d:
            q_servicios = q_servicios.filter(func.date(Factura.created_at) >= d)
        if h:
            q_servicios = q_servicios.filter(func.date(Factura.created_at) <= h)
        data.servicios_vendidos = [
            {"servicio": row.nombre, "cantidad": int(row.cantidad), "total": float(row.total)}
            for row in q_servicios.group_by(Servicio.id, Servicio.nombre)
            .order_by(func.sum(FacturaDetalle.cantidad).desc()).limit(10).all()
        ]

        estados_ot = (
            db.session.query(OrdenTrabajo.estado, func.count(OrdenTrabajo.id).label("total"))
            .group_by(OrdenTrabajo.estado)
            .all()
        )
        data.ots_por_estado = [(row.estado, int(row.total)) for row in estados_ot]

        q_mecanicos = (
            db.session.query(
                Mecanico.nombre,
                func.count(OrdenTrabajo.id).label("total"),
            )
            .join(OrdenTrabajo, Mecanico.id == OrdenTrabajo.mecanico_id)
            .filter(OrdenTrabajo.estado == "entregado")
            .group_by(Mecanico.id, Mecanico.nombre)
            .order_by(func.count(OrdenTrabajo.id).desc())
            .limit(10)
            .all()
        )
        data.productividad_mecanicos = [
            {"mecanico": row.nombre, "ots": int(row.total)} for row in q_mecanicos
        ]

        q_mov = db.session.query(
            MovimientoInventario.tipo,
            func.coalesce(func.sum(MovimientoInventario.cantidad), 0).label("cantidad"),
        )
        if d:
            q_mov = q_mov.filter(func.date(MovimientoInventario.created_at) >= d)
        if h:
            q_mov = q_mov.filter(func.date(MovimientoInventario.created_at) <= h)
        movs = {row.tipo: int(row.cantidad) for row in q_mov.group_by(MovimientoInventario.tipo).all()}
        data.movimientos_inventario = {
            "entradas": movs.get("entrada", 0),
            "salidas": movs.get("salida", 0),
            "ajustes": movs.get("ajuste", 0),
            "bajas": movs.get("baja", 0),
        }
        data.valor_inventario = InventarioService.valorizacion()["total_valor"]

        logger.debug("Reporte %s - %s: %d facturas, $%.2f",
                     desde, hasta, data.facturas_periodo, data.ingresos)
        return data
