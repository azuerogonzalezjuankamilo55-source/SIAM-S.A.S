import logging
import os
from datetime import datetime, timezone
from typing import Any

from database.db import db
from models.cita import Cita
from models.cliente import Cliente
from models.servicio import Servicio
from models.ubicacion_cliente import UbicacionCliente
from models.vehiculo import Vehiculo
from services.routes_service import RoutesService

logger = logging.getLogger("siam.ubicacion_service")

# Estados de cita donde el cliente puede estar "en camino" al taller.
# Entregadas y canceladas dejan de contar como viaje activo.
ESTADOS_CITA_ACTIVOS = (
    "pendiente",
    "confirmada",
    "en_revision",
    "en_reparacion",
    "lista",
)

ETIQUETAS_ESTADO = {
    "pendiente": "Pendiente",
    "confirmada": "Confirmada",
    "en_revision": "En revisión",
    "en_reparacion": "En reparación",
    "lista": "Lista",
}


class UbicacionError(Exception):
    """Error de dominio de geolocalización (mensaje seguro para el cliente)."""


class UbicacionService:

    @staticmethod
    def taller() -> dict[str, Any]:
        return {
            "nombre": "SIAM Taller",
            "address": os.getenv(
                "WORKSHOP_ADDRESS",
                "Cl. 26 Sur #3c Sur10 No 5B, Soacha, Cundinamarca, Colombia",
            ),
            "latitude": float(os.getenv("WORKSHOP_LATITUDE", "4.5712283")),
            "longitude": float(os.getenv("WORKSHOP_LONGITUDE", "-74.2390573")),
        }

    @staticmethod
    def cita_activa_del_cliente(cliente_id: int) -> Cita | None:
        return (
            Cita.query.filter(
                Cita.cliente_id == cliente_id,
                Cita.estado.in_(ESTADOS_CITA_ACTIVOS),
            )
            .order_by(Cita.fecha.desc(), Cita.hora.desc(), Cita.id.desc())
            .first()
        )

    @staticmethod
    def compartido_del_cliente(cliente_id: int) -> list[UbicacionCliente]:
        return (
            UbicacionCliente.query.filter_by(
                cliente_id=cliente_id, sharing_active=True
            )
            .order_by(UbicacionCliente.updated_at.desc())
            .all()
        )

    @staticmethod
    def actualizar(
        cliente_id: int,
        cita_id: int | None,
        latitude: float,
        longitude: float,
        accuracy: float | None,
    ) -> UbicacionCliente:
        """Guarda/actualiza la ubicación del cliente asociada a una cita activa."""
        if cita_id:
            cita = Cita.query.filter_by(id=cita_id, cliente_id=cliente_id).first()
        else:
            cita = UbicacionService.cita_activa_del_cliente(cliente_id)

        if cita is None or cita.estado not in ESTADOS_CITA_ACTIVOS:
            raise UbicacionError(
                "No tienes una cita activa para compartir tu ubicación."
            )

        registro = UbicacionCliente.query.filter_by(
            cliente_id=cliente_id, cita_id=cita.id
        ).first()
        if registro is None:
            registro = UbicacionCliente(
                cliente_id=cliente_id, cita_id=cita.id, sharing_active=True
            )
            db.session.add(registro)
        registro.latitude = latitude
        registro.longitude = longitude
        registro.accuracy = accuracy
        registro.sharing_active = True

        logger.debug(
            "Ubicación cliente %s actualizada (cita %s)", cliente_id, cita.id
        )
        return registro

    @staticmethod
    def detener(cliente_id: int, cita_id: int | None = None) -> int:
        """Detiene el intercambio de ubicación. Retorna cuántos registros se apagaron."""
        query = UbicacionCliente.query.filter_by(
            cliente_id=cliente_id, sharing_active=True
        )
        if cita_id:
            query = query.filter_by(cita_id=cita_id)
        activos = query.all()
        for r in activos:
            r.sharing_active = False
        return len(activos)

    @staticmethod
    def estado_para_portal(cliente: Cliente) -> dict[str, Any]:
        """Estado que el portal del cliente necesita para renderizar su sección."""
        taller = UbicacionService.taller()
        cita = UbicacionService.cita_activa_del_cliente(cliente.id)
        compartidas = UbicacionService.compartido_del_cliente(cliente.id)

        activas = [
            {
                "cita_id": r.cita_id,
                "latitude": r.latitude,
                "longitude": r.longitude,
                "accuracy": r.accuracy,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in compartidas
        ]

        return {
            "taller": taller,
            "tiene_cita_activa": cita is not None,
            "cita": {
                "id": cita.id,
                "fecha": cita.fecha.isoformat() if cita.fecha else None,
                "hora": cita.hora.strftime("%H:%M") if cita.hora else None,
                "estado": cita.estado,
                "estado_etiqueta": ETIQUETAS_ESTADO.get(cita.estado, cita.estado),
            }
            if cita
            else None,
            "compartiendo": bool(activas),
            "ubicaciones_activas": activas,
        }

    @staticmethod
    def cliente_en_camino(cliente_id: int) -> UbicacionCliente | None:
        return (
            UbicacionCliente.query.filter_by(
                cliente_id=cliente_id, sharing_active=True
            )
            .order_by(UbicacionCliente.updated_at.desc())
            .first()
        )

    @staticmethod
    def clientes_en_camino() -> dict[str, Any]:
        """Datos para el mapa del staff (dashboard)."""
        taller = UbicacionService.taller()
        registros = (
            UbicacionCliente.query.filter(UbicacionCliente.sharing_active.is_(True))
            .order_by(UbicacionCliente.updated_at.desc())
            .all()
        )

        clientes: list[dict[str, Any]] = []
        for r in registros:
            cita = r.cita if r.cita_id else None
            if cita is None or cita.estado not in ESTADOS_CITA_ACTIVOS:
                continue

            cliente = r.cliente if r.cliente_id else None
            vehiculo = db.session.get(Vehiculo, cita.vehiculo_id) if cita.vehiculo_id else None
            servicio = db.session.get(Servicio, cita.servicio_id) if cita.servicio_id else None

            ruta = RoutesService.distancia_y_duracion(
                (taller["latitude"], taller["longitude"]),
                (r.latitude, r.longitude),
            )
            duracion_s = ruta.get("duration_s", 0)
            eta_fecha = None
            if ruta.get("ok"):
                eta_fecha = datetime.now(timezone.utc).timestamp() + duracion_s

            geometria = ruta.get("geometry") or []
            geometria_latlng = [
                {"lat": pair[1], "lng": pair[0]}
                for pair in geometria
                if len(pair) >= 2
            ]

            clientes.append(
                {
                    "cliente_id": cliente.id if cliente else None,
                    "cliente_nombre": cliente.nombre if cliente else "Cliente",
                    "telefono": cliente.telefono if cliente else None,
                    "cita_id": cita.id,
                    "cita_fecha": cita.fecha.isoformat() if cita.fecha else None,
                    "cita_hora": cita.hora.strftime("%H:%M") if cita.hora else None,
                    "cita_estado": cita.estado,
                    "cita_estado_etiqueta": ETIQUETAS_ESTADO.get(
                        cita.estado, cita.estado.replace("_", " ").title()
                    ),
                    "vehiculo_marca": vehiculo.marca if vehiculo else None,
                    "vehiculo_modelo": vehiculo.modelo if vehiculo else None,
                    "vehiculo_placa": vehiculo.placa if vehiculo else None,
                    "servicio_nombre": servicio.nombre if servicio else None,
                    "latitude": r.latitude,
                    "longitude": r.longitude,
                    "accuracy": r.accuracy,
                    "updated_at": r.updated_at.strftime("%Y-%m-%dT%H:%M:%SZ")
                    if r.updated_at
                    else None,
                    "distancia_m": int(ruta.get("distance_m", 0)) if ruta.get("ok") else None,
                    "duracion_s": duracion_s if ruta.get("ok") else None,
                    "eta_epoch": eta_fecha if ruta.get("ok") else None,
                    "ruta_ok": ruta.get("ok", False),
                    "ruta_error": ruta.get("error") if not ruta.get("ok") else None,
                    "ruta_geometria": geometria_latlng if ruta.get("ok") else [],
                }
            )

        return {"taller": taller, "clientes": clientes}