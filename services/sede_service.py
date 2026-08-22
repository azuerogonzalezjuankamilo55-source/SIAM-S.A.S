import json
import logging
from datetime import date, time
from typing import Any

from database.db import db
from models.sede import Sede
from models.configuracion_taller import ConfiguracionTaller

logger = logging.getLogger("siam.sedes")

SEDES_INICIALES = [
    {
        "nombre": "Sede Principal Soacha",
        "direccion": "Cra. 7 # 15-42, Soacha, Cundinamarca",
        "telefono": "+57 300 123 4567",
        "horario": "Lun-Vie 7:00 AM - 6:00 PM, Sáb 8:00 AM - 1:00 PM",
        "latitud": 4.5773,
        "longitud": -74.2148,
        "servicios": ["Mantenimiento general", "Diagnóstico", "Frenos", "Suspensión", "Motor", "Transmisión"],
    },
    {
        "nombre": "Sede Norte Bogotá",
        "direccion": "Av. Calle 80 # 92-40, Bogotá",
        "telefono": "+57 310 456 7890",
        "horario": "Lun-Vie 7:00 AM - 6:00 PM, Sáb 8:00 AM - 1:00 PM",
        "latitud": 4.7020,
        "longitud": -74.1038,
        "servicios": ["Diagnóstico", "Cambio de aceite", "Motos", "Frenos", "Alineación y balanceo"],
    },
    {
        "nombre": "Sede Sur Kennedy",
        "direccion": "Av. Boyacá # 39-10, Bogotá",
        "telefono": "+57 320 789 1234",
        "horario": "Lun-Sáb 7:30 AM - 6:00 PM",
        "latitud": 4.6266,
        "longitud": -74.1609,
        "servicios": ["Mantenimiento preventivo", "Repuestos", "Suspensión", "Electricidad automotriz"],
    },
    {
        "nombre": "Sede Occidente Fontibón",
        "direccion": "Cra. 100 # 17-35, Bogotá",
        "telefono": "+57 315 234 5678",
        "horario": "Lun-Vie 7:00 AM - 5:00 PM, Sáb 8:00 AM - 12:00 M",
        "latitud": 4.6683,
        "longitud": -74.1433,
        "servicios": ["Vehículos de carga", "Diagnóstico", "Frenos", "Aire acondicionado", "Asistencia"],
    },
]

ESTADOS_CITA_ACTIVOS = ("pendiente", "en_proceso")

# Ventana laboral por día de semana (0=lunes .. 6=domingo): (apertura, cierre).
# Coincide con el horario publicado de las sedes iniciales.
HORARIO_LABORAL = {
    0: (time(7, 0), time(18, 0)),
    1: (time(7, 0), time(18, 0)),
    2: (time(7, 0), time(18, 0)),
    3: (time(7, 0), time(18, 0)),
    4: (time(7, 0), time(18, 0)),
    5: (time(8, 0), time(13, 0)),
    6: None,
}


class SedeService:
    @staticmethod
    def seed_sedes() -> None:
        """Inserta las sedes por defecto si la tabla está vacía (idempotente)."""
        try:
            if Sede.query.count() > 0:
                return
        except Exception:
            return
        for datos in SEDES_INICIALES:
            db.session.add(
                Sede(
                    nombre=datos["nombre"],
                    direccion=datos.get("direccion"),
                    telefono=datos.get("telefono"),
                    horario=datos.get("horario"),
                    latitud=datos.get("latitud"),
                    longitud=datos.get("longitud"),
                    servicios=json.dumps(datos.get("servicios") or [], ensure_ascii=False),
                )
            )
        try:
            db.session.commit()
            logger.info("Sedes por defecto insertadas (%s)", len(SEDES_INICIALES))
        except Exception:
            db.session.rollback()

    @staticmethod
    def listar() -> list[dict[str, Any]]:
        SedeService.seed_sedes()
        try:
            sedes = Sede.query.filter_by(activo=True).order_by(Sede.id).all()
        except Exception:
            return [dict(s) for s in SEDES_INICIALES]
        return [SedeService.to_dict(s) for s in sedes]

    @staticmethod
    def to_dict(sede: Sede) -> dict[str, Any]:
        servicios: list[str] = []
        if sede.servicios:
            try:
                servicios = json.loads(sede.servicios)
            except (TypeError, ValueError):
                servicios = []
        return {
            "id": sede.id,
            "nombre": sede.nombre,
            "direccion": sede.direccion or "",
            "telefono": sede.telefono or "",
            "horario": sede.horario or "",
            "latitud": sede.latitud,
            "longitud": sede.longitud,
            "servicios": servicios,
        }

    @staticmethod
    def sede_ocupada(
        sede_id: int, fecha: date, hora: time, cita_excluida_id: int | None = None
    ) -> bool:
        """True si ya existe una cita activa en la misma sede/fecha/hora."""
        from models.cita import Cita

        query = Cita.query.filter(
            Cita.sede_id == sede_id,
            Cita.fecha == fecha,
            Cita.hora == hora,
            Cita.estado.in_(ESTADOS_CITA_ACTIVOS),
        )
        if cita_excluida_id:
            query = query.filter(Cita.id != cita_excluida_id)
        return query.first() is not None

    @staticmethod
    def horas_disponibles(
        sede_id: int | None, fecha: date, cita_excluida_id: int | None = None
    ) -> list[str]:
        """Slots libres ("HH:MM") para una sede/fecha según horario laboral,
        intervalo y anticipación configurados. Sin sede no hay filtro de
        ocupación (la cita queda sin sede)."""
        from datetime import datetime, timedelta

        ventana = HORARIO_LABORAL.get(fecha.weekday())
        if not ventana:
            return []
        try:
            config = ConfiguracionTaller.get_config()
            intervalo = int(config.citas_intervalo_min or 30)
            anticipacion_h = int(config.citas_min_anticipacion_horas or 0)
        except Exception:
            intervalo, anticipacion_h = 30, 0
        if intervalo <= 0:
            intervalo = 30

        inicio = datetime.combine(fecha, ventana[0])
        fin = datetime.combine(fecha, ventana[1])
        minimo = datetime.now() + timedelta(hours=anticipacion_h)

        horas: list[str] = []
        actual = inicio
        while actual < fin:
            libre = not sede_id or not SedeService.sede_ocupada(
                int(sede_id), fecha, actual.time(), cita_excluida_id
            )
            if libre and actual >= minimo:
                horas.append(actual.strftime("%H:%M"))
            actual += timedelta(minutes=intervalo)
        return horas
