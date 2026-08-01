import logging
import re
from datetime import date
from decimal import Decimal

from database.db import db
from models.vehiculo import Vehiculo
from models.historial_vehiculo import HistorialVehiculo
from models.servicio import Servicio
from services.dashboard_service import DashboardService

logger = logging.getLogger("siam.inteligencia_service")


BASE_CONOCIMIENTO = [
    {
        "clave": "motor",
        "keywords": ["ruido", "taconea", "golpetea", "motor", "falla", "jalonea", "pierde fuerza"],
        "causas": [
            "Bujías o cables en mal estado",
            "Filtro de aire obstruido",
            "Falta de compresión o inyectores sucios",
        ],
        "servicios": ["motor", "bujia", "filtro", "mantenimiento"],
        "urgencia": "media",
    },
    {
        "clave": "frenos",
        "keywords": ["freno", "frenado", "pedal", "chillido", "rechina", "vibra al frenar"],
        "causas": [
            "Pastillas de freno desgastadas",
            "Discos rayados o deformados",
            "Líquido de frenos bajo o contaminado",
        ],
        "servicios": ["freno", "pastilla", "disco", "liquido de freno"],
        "urgencia": "alta",
    },
    {
        "clave": "vibracion",
        "keywords": ["vibra", "vibración", "vibracion", "tiembla", "volante tiembla"],
        "causas": [
            "Desbalanceo de llantas",
            "Alineación desajustada",
            "Suspensión o rótulas desgastadas",
        ],
        "servicios": ["balanceo", "alineacion", "suspension", "amortiguador"],
        "urgencia": "media",
    },
    {
        "clave": "aceite",
        "keywords": ["gotea", "fuga", "mancha", "aceite", "quema aceite"],
        "causas": [
            "Empaques o retenedores desgastados",
            "Cárter o tapón de drenaje con fuga",
            "Aceite vencido o nivel incorrecto",
        ],
        "servicios": ["aceite", "retenedor", "empaque"],
        "urgencia": "media",
    },
    {
        "clave": "bateria",
        "keywords": ["no prende", "no arranca", "bateria", "batería", "clic", "marcha", "luces debiles"],
        "causas": [
            "Batería descargada o en fin de vida útil",
            "Alternador sin carga suficiente",
            "Borne o cable de batería corroído",
        ],
        "servicios": ["bateria", "alternador", "electrico"],
        "urgencia": "alta",
    },
    {
        "clave": "temperatura",
        "keywords": ["calienta", "se calienta", "temperatura", "hierve", "refrigerante"],
        "causas": [
            "Nivel de refrigerante bajo o fuga",
            "Termostato atascado",
            "Radiador obstruido o bomba de agua fallando",
        ],
        "servicios": ["refrigerante", "termostato", "radiador", "bomba de agua"],
        "urgencia": "alta",
    },
    {
        "clave": "direccion",
        "keywords": ["direccion", "dirección", "volante", "dureza", "juega", "se va"],
        "causas": [
            "Alineación desajustada",
            "Fluido de dirección bajo",
            "Rótulas o terminales de dirección desgastadas",
        ],
        "servicios": ["alineacion", "direccion", "suspension"],
        "urgencia": "media",
    },
    {
        "clave": "suspension",
        "keywords": ["hueco", "amortiguador", "suspension", "suspensión", "rebota", "cruje"],
        "causas": [
            "Amortiguadores desgastados",
            "Bujes o rótulas dañados",
            "Resortes o bandas de suspensión en mal estado",
        ],
        "servicios": ["suspension", "amortiguador", "rotula"],
        "urgencia": "media",
    },
    {
        "clave": "humo",
        "keywords": ["humo", "echando humo", "azul", "blanco", "negro"],
        "causas": [
            "Humo azul: consumo de aceite (anillos o guías)",
            "Humo blanco: entrada de refrigerante a la cámara",
            "Humo negro: mezcla rica o filtro de aire sucio",
        ],
        "servicios": ["motor", "inyector", "filtro"],
        "urgencia": "alta",
    },
    {
        "clave": "llantas",
        "keywords": ["llanta", "neumatico", "neumático", "desgaste", "pincha", "presion"],
        "causas": [
            "Presión incorrecta o desgaste irregular",
            "Desalineación o desbalanceo",
            "Corte o daño en el costado del neumático",
        ],
        "servicios": ["llanta", "balanceo", "alineacion"],
        "urgencia": "media",
    },
]


class InteligenciaService:

    @staticmethod
    def _buscar_servicios(keywords: list[str]) -> list[dict]:
        encontrados = []
        for s in Servicio.query.filter_by(activo=True).order_by(Servicio.nombre).all():
            texto = f"{s.nombre} {s.descripcion or ''}".lower()
            if any(k in texto for k in keywords):
                encontrados.append({
                    "id": s.id,
                    "nombre": s.nombre,
                    "precio": float(s.precio_estimado) if s.precio_estimado else None,
                })
        return encontrados

    @staticmethod
    def diagnosticar(vehiculo_id: int | None, sintomas: str) -> dict:
        sintomas = (sintomas or "").strip()
        texto = sintomas.lower()

        if not texto:
            return {
                "sintomas": [],
                "causas": [],
                "servicios_sugeridos": [],
                "urgencia": "baja",
                "consejo": "Describe el síntoma del vehículo (ej: 'ruido en el motor', 'vibra al frenar').",
            }

        sintomas_encontrados = []
        causas = []
        servicios_keywords = []
        urgencia_max = "baja"

        for regla in BASE_CONOCIMIENTO:
            if any(re.search(rf"\b{re.escape(k)}\b", texto) for k in regla["keywords"]):
                sintomas_encontrados.append(regla["clave"])
                causas.extend(regla["causas"])
                servicios_keywords.extend(regla["servicios"])
                if regla["urgencia"] == "alta":
                    urgencia_max = "alta"
                elif regla["urgencia"] == "media" and urgencia_max != "alta":
                    urgencia_max = "media"

        if not sintomas_encontrados:
            return {
                "sintomas": [],
                "causas": [],
                "servicios_sugeridos": [],
                "urgencia": "baja",
                "consejo": "No reconocí el síntoma. Prueba con palabras como: ruido, frenos, vibración, "
                          "temperatura, batería, aceite, dirección, suspensión o llantas.",
            }

        vehiculo_info = None
        if vehiculo_id:
            vehiculo = db.session.get(Vehiculo, vehiculo_id)
            if vehiculo:
                vehiculo_info = {
                    "id": vehiculo.id,
                    "placa": vehiculo.placa,
                    "marca": vehiculo.marca,
                    "modelo": vehiculo.modelo,
                }

        return {
            "sintomas": sintomas_encontrados,
            "causas": causas,
            "servicios_sugeridos": InteligenciaService._buscar_servicios(servicios_keywords),
            "urgencia": urgencia_max,
            "vehiculo": vehiculo_info,
            "consejo": (
                "Te recomendamos agendar una cita para un diagnóstico. El diagnóstico inicial "
                "no tiene costo y permite confirmar la causa exacta."
                if urgencia_max != "alta" else
                "Síntoma con prioridad alta: evita circular y solicita una cita de revisión "
                "inmediata para evitar daños mayores."
            ),
        }

    @staticmethod
    def recomendar_mantenimiento(vehiculo_id: int) -> dict:
        vehiculo = db.session.get(Vehiculo, vehiculo_id)
        if not vehiculo:
            return {"vehiculo": None, "recomendaciones": [], "resumen": ""}

        hoy = date.today()
        registros = (
            HistorialVehiculo.query
            .filter_by(vehiculo_id=vehiculo.id)
            .order_by(HistorialVehiculo.fecha.desc())
            .all()
        )

        ultima_fecha_km: dict[str, tuple[date | None, int | None]] = {}
        for r in registros:
            clave = r.tipo
            if clave not in ultima_fecha_km:
                ultima_fecha_km[clave] = (r.fecha, r.kilometraje)

        kms_ultimo = max(
            (r.kilometraje for r in registros if r.kilometraje is not None), default=None
        )

        recomendaciones: list[dict] = []

        def _agregar(nombre, detalle, estado):
            recomendaciones.append({"nombre": nombre, "detalle": detalle, "estado": estado})

        ultimo_aceite = ultima_fecha_km.get("cambio_aceite")
        if ultimo_aceite and ultimo_aceite[0]:
            meses = (hoy - ultimo_aceite[0]).days / 30
            estado = "vencido" if meses > 6 else ("pendiente" if meses > 4 else "al_dia")
            detalle = f"Último cambio hace {int(meses)} meses"
            if kms_ultimo and ultimo_aceite[1] and kms_ultimo - ultimo_aceite[1] > 5000:
                estado = "vencido"
                detalle += f" · {kms_ultimo - ultimo_aceite[1]} km recorridos desde el cambio"
            _agregar("Cambio de aceite y filtro", detalle, estado)
        else:
            _agregar("Cambio de aceite y filtro", "Sin registro previo en el sistema", "sin_dato")

        for tipo, nombre, detalle in [
            ("cambio_frenos", "Revisión de frenos", "Pastillas, discos y líquido de frenos"),
            ("balanceo", "Balanceo de llantas", "Cada 10,000 km o si siente vibración"),
            ("alineacion", "Alineación", "Si el volante tiembla o el vehículo se va hacia un lado"),
            ("llantas", "Rotación de neumáticos", "Cada 10,000 km para desgaste parejo"),
            ("bateria", "Prueba de batería", "Recomendada cada año"),
        ]:
            registro = ultima_fecha_km.get(tipo)
            estado = "al_dia" if registro else "sin_dato"
            if registro and registro[0]:
                meses = (hoy - registro[0]).days / 30
                estado = "vencido" if meses > 12 else ("pendiente" if meses > 9 else "al_dia")
            _agregar(nombre, detalle, estado)

        resumen = (
            f"{vehiculo.marca} {vehiculo.modelo} · {vehiculo.placa}"
        )
        return {
            "vehiculo": {
                "id": vehiculo.id,
                "placa": vehiculo.placa,
                "marca": vehiculo.marca,
                "modelo": vehiculo.modelo,
            },
            "recomendaciones": recomendaciones,
            "resumen": resumen,
            "kms_ultimo": kms_ultimo,
        }

    @staticmethod
    def resumen_taller() -> str:
        data = DashboardService.get_data()
        partes = [
            f"El taller registra {data.total_clientes} clientes y {data.total_vehiculos} vehículos.",
            f"Ingresos de hoy: ${data.ingresos_hoy:,.0f} (mes: ${data.ingresos_mes:,.0f}).",
            f"Hay {data.citas_hoy} citas para hoy, {data.ordenes_activas} órdenes activas "
            f"y {data.ot_retrasadas_count} órdenes retrasadas.",
            f"Cuentas por cobrar: ${data.por_cobrar:,.0f} y ticket promedio de ${data.ticket_promedio:,.0f}.",
            f"{data.inventario_bajo} productos están por debajo del stock mínimo.",
        ]
        if data.mecanico_top_nombre:
            partes.append(
                f"El mecánico con más entregas es {data.mecanico_top_nombre} "
                f"({data.mecanico_top_total} OTs)."
            )
        return " ".join(partes)
