import logging
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Any

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

# Intervalos sugeridos de mantenimiento preventivo por kilometraje (km).
INTERVALOS_MANTENIMIENTO: dict[str, dict[str, Any]] = {
    "cambio_aceite": {"label": "Cambio de aceite y filtro", "intervalo_km": 5000},
    "cambio_frenos": {"label": "Revisión de frenos", "intervalo_km": 15000},
    "balanceo": {"label": "Balanceo de llantas", "intervalo_km": 10000},
    "alineacion": {"label": "Alineación", "intervalo_km": 10000},
    "llantas": {"label": "Rotación de neumáticos", "intervalo_km": 40000},
    "bateria": {"label": "Prueba de batería", "intervalo_km": 30000},
}


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

    @staticmethod
    def get_resumen(vehiculo_id: int) -> dict[str, Any]:
        """Ficha técnica del vehículo: resumen de actividad, gasto y estado."""
        registros = HistorialService.get_historial_vehiculo(vehiculo_id)

        conteo: dict[str, int] = {}
        for r in registros:
            conteo[r.tipo] = conteo.get(r.tipo, 0) + 1

        ultimo_kilometraje = max(
            (r.kilometraje for r in registros if r.kilometraje), default=None
        )

        total_gastado: Decimal = Decimal("0")
        try:
            from models.factura import Factura
            from models.cita import Cita

            total_gastado = db.session.query(
                db.func.coalesce(db.func.sum(Factura.total), 0)
            ).join(Cita, Cita.id == Factura.cita_id).filter(
                Cita.vehiculo_id == vehiculo_id,
                Factura.estado != "anulado",
            ).scalar() or Decimal("0")
        except Exception:
            logger.warning("No se pudo calcular total gastado del vehículo %s", vehiculo_id, exc_info=True)

        visitas = conteo.get("factura", 0) + conteo.get("cita", 0)
        ultimo = registros[0] if registros else None

        return {
            "total_registros": len(registros),
            "visitas": visitas,
            "ultimo_kilometraje": ultimo_kilometraje,
            "ultimo_servicio": ultimo.tipo if ultimo else None,
            "ultimo_servicio_label": ultimo.tipo_label if ultimo else None,
            "ultimo_servicio_fecha": ultimo.fecha if ultimo else None,
            "total_gastado": total_gastado,
            "conteo_por_tipo": conteo,
        }

    @staticmethod
    def get_proximos_mantenimientos(vehiculo_id: int) -> list[dict[str, Any]]:
        """Sugerencias de mantenimiento preventivo según kilometraje y última vez."""
        registros = HistorialService.get_historial_vehiculo(vehiculo_id)
        ultimo_km = max(
            (r.kilometraje for r in registros if r.kilometraje), default=None
        )

        ultimo_por_tipo: dict[str, HistorialVehiculo] = {}
        for r in registros:
            if r.tipo in INTERVALOS_MANTENIMIENTO and r.tipo not in ultimo_por_tipo:
                ultimo_por_tipo[r.tipo] = r

        resultado: list[dict[str, Any]] = []
        for tipo, cfg in INTERVALOS_MANTENIMIENTO.items():
            ultimo = ultimo_por_tipo.get(tipo)
            km_base = ultimo.kilometraje if ultimo and ultimo.kilometraje else ultimo_km
            proximo = km_base + cfg["intervalo_km"] if km_base is not None else None
            restante = proximo - ultimo_km if (proximo is not None and ultimo_km is not None) else None

            if restante is None:
                estado = "sin_datos"
            elif restante <= 500:
                estado = "urgente"
            elif restante <= 1500:
                estado = "proximo"
            else:
                estado = "al_dia"

            resultado.append({
                "tipo": tipo,
                "label": cfg["label"],
                "ultima_fecha": ultimo.fecha if ultimo else None,
                "ultimo_kilometraje": km_base,
                "proximo_kilometraje": proximo,
                "restante_km": restante,
                "estado": estado,
            })
        return resultado
