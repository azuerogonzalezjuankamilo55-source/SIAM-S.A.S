import logging
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import func, extract

from database.db import db
from models.cliente import Cliente
from models.vehiculo import Vehiculo
from models.cita import Cita
from models.factura import Factura, FacturaDetalle
from models.orden_trabajo import OrdenTrabajo
from models.pago_factura import PagoFactura
from models.historial_vehiculo import HistorialVehiculo
from models.recordatorio import Recordatorio

logger = logging.getLogger("siam.portal_service")


@dataclass
class PortalData:
    cliente: Cliente | None = None
    total_vehiculos: int = 0
    proximas_citas: list = field(default_factory=list)
    ordenes_activas: list = field(default_factory=list)
    facturas_pendientes: list = field(default_factory=list)
    historial_reciente: list = field(default_factory=list)
    proximos_recordatorios: list = field(default_factory=list)


class PortalService:

    @staticmethod
    def get_cliente_de_usuario(usuario) -> Cliente | None:
        if not usuario or not usuario.is_authenticated:
            return None
        if getattr(usuario, "cliente_id", None):
            return db.session.get(Cliente, usuario.cliente_id)
        if getattr(usuario, "cliente", None):
            return usuario.cliente
        if usuario.correo:
            cliente = Cliente.query.filter(
                db.func.lower(Cliente.correo) == usuario.correo.strip().lower()
            ).first()
            if cliente:
                usuario.cliente_id = cliente.id
                try:
                    db.session.commit()
                except Exception:
                    db.session.rollback()
                return cliente
        return None

    @staticmethod
    def get_data(cliente: Cliente) -> PortalData:
        data = PortalData(cliente=cliente)
        hoy = date.today()
        data.total_vehiculos = Vehiculo.query.filter_by(cliente_id=cliente.id).count()

        data.proximas_citas = (
            Cita.query
            .filter(
                Cita.cliente_id == cliente.id,
                Cita.fecha >= hoy,
                Cita.estado.in_(["pendiente", "en_proceso"]),
            )
            .order_by(Cita.fecha.asc(), Cita.hora.asc())
            .limit(5)
            .all()
        )

        data.ordenes_activas = (
            OrdenTrabajo.query
            .filter(
                OrdenTrabajo.cliente_id == cliente.id,
                OrdenTrabajo.estado.in_(["recibido", "diagnostico", "esperando_repuestos", "en_reparacion", "pruebas"]),
            )
            .order_by(OrdenTrabajo.created_at.desc())
            .limit(5)
            .all()
        )

        facturas_ids = [
            f.id for f in Factura.query
            .join(Cita, Cita.id == Factura.cita_id)
            .filter(Cita.cliente_id == cliente.id)
            .all()
        ]
        data.facturas_pendientes = (
            Factura.query
            .filter(
                Factura.id.in_(facturas_ids) if facturas_ids else False,
                Factura.estado.in_(["pendiente", "parcial"]),
            )
            .order_by(Factura.created_at.desc())
            .limit(5)
            .all()
        )

        data.historial_reciente = (
            HistorialVehiculo.query
            .join(Vehiculo, Vehiculo.id == HistorialVehiculo.vehiculo_id)
            .filter(Vehiculo.cliente_id == cliente.id)
            .order_by(HistorialVehiculo.fecha.desc(), HistorialVehiculo.created_at.desc())
            .limit(10)
            .all()
        )

        vehiculos_ids = [
            v.id for v in Vehiculo.query.filter_by(cliente_id=cliente.id).all()
        ]
        data.proximos_recordatorios = (
            Recordatorio.query
            .filter(
                Recordatorio.vehiculo_id.in_(vehiculos_ids) if vehiculos_ids else False,
                Recordatorio.estado.in_(["pendiente", "enviado"]),
            )
            .order_by(Recordatorio.fecha_programada.asc())
            .limit(5)
            .all()
        )

        logger.debug("Portal cliente %s: %d vehiculos, %d citas proximas",
                     cliente.id, data.total_vehiculos, len(data.proximas_citas))
        return data

    @staticmethod
    def get_vehiculos(cliente: Cliente) -> list[Vehiculo]:
        return Vehiculo.query.filter_by(cliente_id=cliente.id).order_by(Vehiculo.marca, Vehiculo.modelo).all()

    @staticmethod
    def get_vehiculo(cliente: Cliente, vehiculo_id: int) -> Vehiculo | None:
        return Vehiculo.query.filter_by(id=vehiculo_id, cliente_id=cliente.id).first()

    @staticmethod
    def get_facturas(cliente: Cliente) -> list[Factura]:
        return (
            Factura.query
            .join(Cita, Cita.id == Factura.cita_id)
            .filter(Cita.cliente_id == cliente.id)
            .order_by(Factura.created_at.desc())
            .all()
        )

    @staticmethod
    def get_factura(cliente: Cliente, factura_id: int) -> Factura | None:
        return (
            Factura.query
            .join(Cita, Cita.id == Factura.cita_id)
            .filter(Factura.id == factura_id, Cita.cliente_id == cliente.id)
            .first()
        )

    @staticmethod
    def get_pagos(cliente: Cliente) -> list[PagoFactura]:
        facturas_ids = [f.id for f in PortalService.get_facturas(cliente)]
        if not facturas_ids:
            return []
        return (
            PagoFactura.query
            .filter(PagoFactura.factura_id.in_(facturas_ids))
            .order_by(PagoFactura.created_at.desc())
            .all()
        )

    @staticmethod
    def get_ordenes(cliente: Cliente) -> list[OrdenTrabajo]:
        return (
            OrdenTrabajo.query
            .filter_by(cliente_id=cliente.id)
            .order_by(OrdenTrabajo.created_at.desc())
            .all()
        )

    @staticmethod
    def get_historial(cliente: Cliente) -> list[HistorialVehiculo]:
        return (
            HistorialVehiculo.query
            .join(Vehiculo, Vehiculo.id == HistorialVehiculo.vehiculo_id)
            .filter(Vehiculo.cliente_id == cliente.id)
            .order_by(HistorialVehiculo.fecha.desc(), HistorialVehiculo.created_at.desc())
            .all()
        )
