import logging
from dataclasses import dataclass, field
from datetime import date, datetime

from sqlalchemy import func, extract

from database.db import db
from models.cliente import Cliente
from models.vehiculo import Vehiculo
from models.cita import Cita
from models.factura import Factura, FacturaDetalle
from models.inventario import Inventario
from models.orden_trabajo import OrdenTrabajo
from models.servicio import Servicio
from models.mecanico import Mecanico

logger = logging.getLogger("siam.dashboard_service")


@dataclass
class DashboardData:
    total_clientes: int = 0
    total_vehiculos: int = 0
    total_mecanicos: int = 0
    citas_hoy: int = 0
    citas_pendientes: int = 0
    ordenes_activas: int = 0
    ordenes_listas: int = 0
    vehiculos_en_proceso: int = 0
    facturas_pendientes: int = 0
    facturas_hoy: int = 0
    inventario_bajo: int = 0
    ingresos_hoy: float = 0.0
    ingresos_mes: float = 0.0
    clientes_nuevos_mes: int = 0
    mecanico_top_nombre: str = ""
    mecanico_top_total: int = 0
    citas_recientes: list = field(default_factory=list)
    items_stock_bajo: list = field(default_factory=list)
    ultimas_facturas: list = field(default_factory=list)
    ingresos_mensuales: list = field(default_factory=list)
    servicios_mas_vendidos: list = field(default_factory=list)
    estado_ot_data: list = field(default_factory=list)
    citas_semana: list = field(default_factory=list)


class DashboardService:

    @staticmethod
    def get_data() -> DashboardData:
        logger.debug("Obteniendo datos del dashboard")
        today = date.today()
        current_month = today.month
        current_year = today.year

        ingresos_hoy = float(
            db.session.query(func.coalesce(func.sum(Factura.total), 0))
            .filter(
                Factura.estado.in_(["pagado", "parcial"]),
                func.date(Factura.created_at) == today,
            )
            .scalar() or 0
        )

        ingresos_mes = float(
            db.session.query(func.coalesce(func.sum(Factura.total), 0))
            .filter(
                Factura.estado.in_(["pagado", "parcial"]),
                extract("month", Factura.created_at) == current_month,
                extract("year", Factura.created_at) == current_year,
            )
            .scalar() or 0
        )

        citas_recientes = (
            Cita.query
            .order_by(Cita.fecha.desc(), Cita.hora.desc())
            .limit(5)
            .all()
        )

        items_bajo = (
            Inventario.query
            .filter(Inventario.cantidad <= Inventario.stock_minimo)
            .order_by(Inventario.cantidad.asc())
            .all()
        )

        ultimas_facturas = (
            Factura.query
            .order_by(Factura.created_at.desc())
            .limit(5)
            .all()
        )

        ordenes_activas = OrdenTrabajo.query.filter(
            OrdenTrabajo.estado.in_(["recibido", "diagnostico", "esperando_repuestos", "en_reparacion"])
        ).count()
        ordenes_listas = OrdenTrabajo.query.filter(OrdenTrabajo.estado == "listo_entrega").count()

        clientes_nuevos = Cliente.query.filter(
            extract("month", Cliente.created_at) == current_month,
            extract("year", Cliente.created_at) == current_year,
        ).count()

        top_mecanico = (
            db.session.query(Mecanico.nombre, func.count(OrdenTrabajo.id).label("total"))
            .join(OrdenTrabajo, Mecanico.id == OrdenTrabajo.mecanico_id)
            .filter(OrdenTrabajo.estado.in_(["entregado", "listo_entrega"]))
            .group_by(Mecanico.id, Mecanico.nombre)
            .order_by(func.count(OrdenTrabajo.id).desc())
            .first()
        )

        ingresos_por_mes = (
            db.session.query(
                extract("year", Factura.created_at).label("anio"),
                extract("month", Factura.created_at).label("mes"),
                func.sum(Factura.total).label("total"),
            )
            .filter(Factura.estado.in_(["pagado", "parcial"]))
            .group_by("anio", "mes")
            .order_by("anio", "mes")
            .all()
        )

        ingresos_mensuales = []
        for row in ingresos_por_mes:
            anio = int(row.anio)
            mes = int(row.mes)
            label = f"{mes:02d}/{anio}"
            ingresos_mensuales.append((label, float(row.total)))

        top_servicios = (
            db.session.query(
                Servicio.nombre,
                func.coalesce(func.sum(FacturaDetalle.cantidad), 0).label("total"),
            )
            .join(FacturaDetalle, Servicio.id == FacturaDetalle.servicio_id)
            .group_by(Servicio.id, Servicio.nombre)
            .order_by(func.coalesce(func.sum(FacturaDetalle.cantidad), 0).desc())
            .limit(5)
            .all()
        )
        servicios_mas_vendidos = [(row.nombre, int(row.total)) for row in top_servicios]

        estados_ot = (
            db.session.query(
                OrdenTrabajo.estado,
                func.count(OrdenTrabajo.id).label("total"),
            )
            .group_by(OrdenTrabajo.estado)
            .all()
        )
        estado_ot_data = [(row.estado, int(row.total)) for row in estados_ot]

        citas_semana = (
            db.session.query(
                func.date(Cita.fecha).label("dia"),
                func.count(Cita.id).label("total"),
            )
            .filter(Cita.fecha >= today)
            .group_by(func.date(Cita.fecha))
            .order_by(func.date(Cita.fecha))
            .limit(7)
            .all()
        )
        citas_semana_list = [(str(row.dia), int(row.total)) for row in citas_semana]

        data = DashboardData(
            total_clientes=Cliente.query.count(),
            total_vehiculos=Vehiculo.query.count(),
            total_mecanicos=Mecanico.query.count(),
            citas_hoy=Cita.query.filter(Cita.fecha == today).count(),
            citas_pendientes=Cita.query.filter(Cita.estado == "pendiente").count(),
            ordenes_activas=ordenes_activas,
            ordenes_listas=ordenes_listas,
            vehiculos_en_proceso=ordenes_activas,
            facturas_pendientes=Factura.query.filter(Factura.estado == "pendiente").count(),
            facturas_hoy=Factura.query.filter(func.date(Factura.created_at) == today).count(),
            inventario_bajo=len(items_bajo),
            ingresos_hoy=ingresos_hoy,
            ingresos_mes=ingresos_mes,
            clientes_nuevos_mes=clientes_nuevos,
            mecanico_top_nombre=top_mecanico.nombre if top_mecanico else "",
            mecanico_top_total=top_mecanico.total if top_mecanico else 0,
            citas_recientes=citas_recientes,
            items_stock_bajo=items_bajo,
            ultimas_facturas=ultimas_facturas,
            ingresos_mensuales=ingresos_mensuales,
            servicios_mas_vendidos=servicios_mas_vendidos,
            estado_ot_data=estado_ot_data,
            citas_semana=citas_semana_list,
        )

        logger.debug("Dashboard actualizado: %d clientes, $%.2f ingresos mes", data.total_clientes, data.ingresos_mes)
        return data
