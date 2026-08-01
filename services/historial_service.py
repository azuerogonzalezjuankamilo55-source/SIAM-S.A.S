import logging
from datetime import date
from typing import TYPE_CHECKING

from database.db import db
from models.historial_vehiculo import HistorialVehiculo

if TYPE_CHECKING:
    from models.factura import Factura
    from models.orden_trabajo import OrdenTrabajo
    from models.cita import Cita

logger = logging.getLogger("siam.historial_service")

TIPOS = [
    "cita", "reparacion", "mantenimiento", "cambio_aceite", "cambio_frenos",
    "alineacion", "balanceo", "llantas", "bateria", "revision",
    "factura", "fotografia", "observacion", "diagnostico",
]

# Palabras clave: (clave, tipo historial)
KEYWORD_MAP = [
    ("aceite", "cambio_aceite"),
    ("freno", "cambio_frenos"),
    ("aline", "alineacion"),
    ("balance", "balanceo"),
    ("llanta", "llantas"),
    ("neumatic", "llantas"),
    ("bateria", "bateria"),
    ("revision", "revision"),
    ("revisar", "revision"),
    ("diagnost", "diagnostico"),
    ("reparac", "reparacion"),
    ("mantenim", "mantenimiento"),
]


class HistorialService:

    @staticmethod
    def registrar(
        vehiculo_id: int,
        tipo: str,
        descripcion: str | None = None,
        fecha: date | None = None,
        kilometraje: int | None = None,
        foto_path: str | None = None,
        cita_id: int | None = None,
        factura_id: int | None = None,
        orden_trabajo_id: int | None = None,
        creado_por: int | None = None,
    ) -> HistorialVehiculo:
        if tipo not in TIPOS:
            raise ValueError(f"Tipo de historial inválido: {tipo}")

        entrada = HistorialVehiculo(
            vehiculo_id=vehiculo_id,
            tipo=tipo,
            descripcion=descripcion,
            fecha=fecha or date.today(),
            kilometraje=kilometraje,
            foto_path=foto_path,
            cita_id=cita_id,
            factura_id=factura_id,
            orden_trabajo_id=orden_trabajo_id,
            creado_por=creado_por,
        )
        db.session.add(entrada)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
        logger.debug("Historial %s registrado para vehículo %s", tipo, vehiculo_id)
        return entrada

    @staticmethod
    def _tipo_para_servicio(nombre: str, categoria: str | None = None) -> str:
        texto = f"{nombre} {categoria or ''}".lower()
        for clave, tipo in KEYWORD_MAP:
            if clave in texto:
                return tipo
        return "mantenimiento"

    @staticmethod
    def registrar_desde_factura(factura: "Factura", creado_por: int | None = None) -> None:
        if not factura or not factura.cita:
            return
        vehiculo_id = factura.cita.vehiculo_id
        detalle_texto = []
        for detalle in factura.detalles:
            servicio = detalle.servicio
            if not servicio:
                continue
            tipo = HistorialService._tipo_para_servicio(servicio.nombre, servicio.categoria)
            detalle_texto.append(
                f"{servicio.nombre} (x{detalle.cantidad})"
            )
            HistorialService.registrar(
                vehiculo_id=vehiculo_id,
                tipo=tipo,
                descripcion=f"{servicio.nombre} — factura {factura.numero}",
                fecha=factura.created_at.date() if factura.created_at else date.today(),
                factura_id=factura.id,
                cita_id=factura.cita_id,
                creado_por=creado_por,
            )
        if detalle_texto:
            HistorialService.registrar(
                vehiculo_id=vehiculo_id,
                tipo="factura",
                descripcion=(
                    f"Factura {factura.numero} por ${float(factura.total):,.0f}: "
                    + ", ".join(detalle_texto)
                ),
                fecha=factura.created_at.date() if factura.created_at else date.today(),
                factura_id=factura.id,
                cita_id=factura.cita_id,
                creado_por=creado_por,
            )

    @staticmethod
    def registrar_desde_orden(orden: "OrdenTrabajo", creado_por: int | None = None) -> None:
        if not orden:
            return
        vehiculo_id = orden.vehiculo_id
        tipo = "reparacion"
        descripcion = f"Orden {orden.numero}"
        if orden.diagnostico_inicial:
            descripcion += f": {orden.diagnostico_inicial}"
        HistorialService.registrar(
            vehiculo_id=vehiculo_id,
            tipo=tipo,
            descripcion=descripcion,
            fecha=orden.fecha_ingreso,
            orden_trabajo_id=orden.id,
            creado_por=creado_por,
        )

    @staticmethod
    def registrar_desde_cita(cita: "Cita", creado_por: int | None = None) -> None:
        if not cita:
            return
        HistorialService.registrar(
            vehiculo_id=cita.vehiculo_id,
            tipo="cita",
            descripcion=cita.descripcion or f"Cita atendida el {cita.fecha}",
            fecha=cita.fecha,
            cita_id=cita.id,
            creado_por=creado_por,
        )

    @staticmethod
    def get_historial_vehiculo(vehiculo_id: int) -> list[HistorialVehiculo]:
        return (
            HistorialVehiculo.query
            .filter_by(vehiculo_id=vehiculo_id)
            .order_by(HistorialVehiculo.fecha.desc(), HistorialVehiculo.created_at.desc())
            .all()
        )

    @staticmethod
    def agregar_observacion(
        vehiculo_id: int, descripcion: str, creado_por: int | None = None
    ) -> HistorialVehiculo:
        return HistorialService.registrar(
            vehiculo_id=vehiculo_id,
            tipo="observacion",
            descripcion=descripcion,
            creado_por=creado_por,
        )
