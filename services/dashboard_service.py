import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal

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
from models.asistencia import AsistenciaEmergencia
from models.pago_factura import PagoFactura
from services.reporte_service import ReporteService

logger = logging.getLogger("siam.dashboard_service")


@dataclass
class DashboardData:
    total_clientes: int = 0
    total_vehiculos: int = 0
    total_servicios: int = 0
    total_facturas: int = 0
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
    por_cobrar: float = 0.0
    ticket_promedio: float = 0.0
    ot_retrasadas_count: int = 0
    tasa_completacion_citas: float = 0.0
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
    ingresos_por_metodo: list = field(default_factory=list)
    ot_por_mecanico: list = field(default_factory=list)
    ot_retrasadas: list = field(default_factory=list)
    ot_en_proceso: list = field(default_factory=list)
    asistencias_activas: list = field(default_factory=list)
    servicios_completados: int = 0
    proximas_citas: list = field(default_factory=list)


class DashboardService:

    @staticmethod
    def get_data() -> DashboardData:
        logger.debug("Obteniendo datos del dashboard")
        today = date.today()
        current_month = today.month
        current_year = today.year

        ingresos_hoy = ReporteService.ingresos(today, today)

        primer_dia_mes = date(current_year, current_month, 1)
        ultimo_dia_mes = date(
            current_year + (current_month // 12),
            (current_month % 12) + 1,
            1,
        ) - timedelta(days=1)
        ingresos_mes = ReporteService.ingresos(primer_dia_mes, ultimo_dia_mes)

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
            OrdenTrabajo.estado.in_(["recibido", "diagnostico", "esperando_repuestos", "en_reparacion", "pruebas"])
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

        por_cobrar = ReporteService.cartera()

        facturas_validadas = Factura.query.filter(Factura.estado != "anulado").all()
        total_facturado = float(sum((f.total for f in facturas_validadas), Decimal("0")))
        ticket_promedio = (
            total_facturado / len(facturas_validadas) if facturas_validadas else 0.0
        )

        ot_retrasadas = (
            OrdenTrabajo.query
            .filter(
                OrdenTrabajo.fecha_estimada_entrega.isnot(None),
                OrdenTrabajo.fecha_estimada_entrega < today,
                OrdenTrabajo.estado != "entregado",
            )
            .order_by(OrdenTrabajo.fecha_estimada_entrega.asc())
            .limit(5)
            .all()
        )
        ot_retrasadas_count = (
            OrdenTrabajo.query
            .filter(
                OrdenTrabajo.fecha_estimada_entrega.isnot(None),
                OrdenTrabajo.fecha_estimada_entrega < today,
                OrdenTrabajo.estado != "entregado",
            )
            .count()
        )

        total_citas = Cita.query.count()
        citas_completadas = Cita.query.filter(
            Cita.estado.in_(["entregada", "completado"])  # completado = valor legado
        ).count()
        tasa_completacion_citas = (
            (citas_completadas / total_citas * 100) if total_citas else 0.0
        )

        ingresos_por_metodo = ReporteService.ingresos_por_metodo()

        ot_por_mecanico_rows = (
            db.session.query(
                Mecanico.nombre,
                func.count(OrdenTrabajo.id).label("total"),
            )
            .join(OrdenTrabajo, Mecanico.id == OrdenTrabajo.mecanico_id)
            .filter(OrdenTrabajo.estado == "entregado")
            .group_by(Mecanico.id, Mecanico.nombre)
            .order_by(func.count(OrdenTrabajo.id).desc())
            .limit(5)
            .all()
        )
        ot_por_mecanico = [(row.nombre, int(row.total)) for row in ot_por_mecanico_rows]

        ot_en_proceso = (
            OrdenTrabajo.query
            .filter(
                OrdenTrabajo.estado.in_(
                    ["recibido", "diagnostico", "esperando_repuestos", "en_reparacion", "pruebas", "listo_entrega"]
                )
            )
            .order_by(OrdenTrabajo.created_at.asc())
            .limit(5)
            .all()
        )

        servicios_completados = OrdenTrabajo.query.filter(
            OrdenTrabajo.estado == "entregado"
        ).count()

        proximas_citas = (
            Cita.query
            .filter(Cita.fecha >= today, Cita.estado != "cancelado")
            .order_by(Cita.fecha.asc(), Cita.hora.asc())
            .limit(6)
            .all()
        )

        asistencias_activas = (
            AsistenciaEmergencia.query
            .filter(AsistenciaEmergencia.estado == "pendiente")
            .order_by(AsistenciaEmergencia.created_at.desc())
            .limit(6)
            .all()
        )

        data = DashboardData(
            total_clientes=Cliente.query.count(),
            total_vehiculos=Vehiculo.query.count(),
            total_servicios=Servicio.query.count(),
            total_facturas=Factura.query.count(),
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
            por_cobrar=por_cobrar,
            ticket_promedio=ticket_promedio,
            ot_retrasadas_count=ot_retrasadas_count,
            tasa_completacion_citas=tasa_completacion_citas,
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
            ingresos_por_metodo=ingresos_por_metodo,
            ot_por_mecanico=ot_por_mecanico,
            ot_retrasadas=ot_retrasadas,
            ot_en_proceso=ot_en_proceso,
            asistencias_activas=asistencias_activas,
            servicios_completados=servicios_completados,
            proximas_citas=proximas_citas,
        )

        logger.debug("Dashboard actualizado: %d clientes, $%.2f ingresos mes", data.total_clientes, data.ingresos_mes)
        return data

    @staticmethod
    def get_actividad(limit: int = 10) -> list[dict]:
        """Última actividad (clientes, citas, órdenes, facturas, pagos, asistencias)."""
        eventos: list[dict] = []

        for c in Cliente.query.order_by(Cliente.created_at.desc()).limit(limit).all():
            eventos.append({
                "tipo": "cliente",
                "icono": "user-plus",
                "texto": f"Nuevo cliente: {c.nombre}",
                "cuando": c.created_at.isoformat(sep=" ", timespec="seconds"),
            })

        for c in Cita.query.order_by(Cita.created_at.desc()).limit(limit).all():
            estados = {
                "pendiente": "pendiente",
                "confirmada": "confirmada",
                "en_revision": "en revisión",
                "en_reparacion": "en reparación",
                "lista": "lista",
                "entregada": "entregada",
            }
            eventos.append({
                "tipo": "cita",
                "icono": "calendar-check",
                "texto": f"Cita {estados.get(c.estado, c.estado)} para {c.cliente.nombre}",
                "cuando": c.created_at.isoformat(sep=" ", timespec="seconds"),
            })

        for o in OrdenTrabajo.query.order_by(OrdenTrabajo.created_at.desc()).limit(limit).all():
            eventos.append({
                "tipo": "orden",
                "icono": "wrench",
                "texto": f"OT #{o.id}: {o.estado_display}",
                "cuando": o.created_at.isoformat(sep=" ", timespec="seconds"),
            })

        for f in Factura.query.order_by(Factura.created_at.desc()).limit(limit).all():
            eventos.append({
                "tipo": "factura",
                "icono": "file-invoice-dollar",
                "texto": f"Factura #{f.id}: ${float(f.total):,.0f}",
                "cuando": f.created_at.isoformat(sep=" ", timespec="seconds"),
            })

        for p in PagoFactura.query.order_by(PagoFactura.created_at.desc()).limit(limit).all():
            eventos.append({
                "tipo": "pago",
                "icono": "money-bill-wave",
                "texto": f"Pago de ${float(p.monto):,.0f} ({p.metodo_pago_display})",
                "cuando": p.created_at.isoformat(sep=" ", timespec="seconds"),
            })

        for a in AsistenciaEmergencia.query.order_by(AsistenciaEmergencia.created_at.desc()).limit(limit).all():
            eventos.append({
                "tipo": "asistencia",
                "icono": "truck-fast",
                "texto": f"Asistencia en emergencia #{a.id}: {a.estado}",
                "cuando": a.created_at.isoformat(sep=" ", timespec="seconds"),
            })

        eventos.sort(key=lambda e: e["cuando"], reverse=True)
        return eventos[:limit]
