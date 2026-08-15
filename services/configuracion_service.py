import json
import logging
import os
import re
from typing import Any

from flask import current_app
from sqlalchemy import text

from database.commit import safe_commit
from database.db import db
from models.configuracion_taller import ConfiguracionTaller

logger = logging.getLogger("siam.configuracion")

HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})$")

DEFAULT_COLORES = {
    "color_primario": "#2563EB",
    "color_primario_fuerte": "#1D4ED8",
    "color_primario_soft": "#DBEAFE",
    "color_acento": "#0F766E",
}

PREGUNTAS_SUGERIDAS_DEFAULT = [
    "¿Cuál es el horario de atención?",
    "¿Dónde están sus sedes?",
    "¿Cómo agendo una cita?",
    "¿Qué métodos de pago aceptan?",
]


def validar_hex(valor: str | None) -> str | None:
    """Devuelve el HEX normalizado o None si es inválido."""
    if not valor:
        return None
    valor = valor.strip()
    if not valor.startswith("#"):
        valor = "#" + valor
    if HEX_RE.match(valor):
        return valor.upper()
    return None


class ConfiguracionService:
    SECCIONES = [
        "empresa",
        "sedes",
        "apariencia",
        "citas",
        "notificaciones",
        "archivos",
        "ia",
        "seguridad",
        "sistema",
    ]

    @staticmethod
    def aplicar(config: ConfiguracionTaller, seccion: str, datos: dict[str, Any]) -> None:
        """Aplica los campos de una sección a la configuración y hace commit con rollback."""
        campos = {
            "empresa": [
                "nombre_taller", "nit", "ciudad", "direccion", "telefono", "whatsapp",
                "email", "sitio_web", "facebook", "instagram", "twitter", "linkedin",
                "regimen", "prefijo_factura", "resolucion_dian", "iva_porcentaje",
            ],
            "apariencia": ["color_primario", "color_primario_fuerte", "color_primario_soft", "color_acento"],
            "citas": ["citas_intervalo_min", "citas_min_anticipacion_horas", "citas_cancelar_limite_horas"],
            "notificaciones": ["notif_email", "notif_sms", "notif_whatsapp", "notif_recordatorio_dias"],
            "ia": [
                "ia_activado", "ia_nombre", "ia_tono", "ia_mensaje_bienvenida",
                "ia_preguntas_sugeridas", "ia_contacto", "ia_mensaje_emergencia",
            ],
        }
        permitidos = campos.get(seccion, [])
        if seccion == "apariencia":
            datos = ConfiguracionService._validar_colores(datos)
        for campo in permitidos:
            if campo not in datos:
                continue
            valor = datos[campo]
            if campo == "ia_preguntas_sugeridas" and isinstance(valor, str):
                valor = ConfiguracionService.serializar_preguntas(valor)
            setattr(config, campo, valor)
        safe_commit()
        logger.info("Configuración actualizada (sección %s)", seccion)

    @staticmethod
    def _validar_colores(datos: dict[str, Any]) -> dict[str, Any]:
        limpio: dict[str, Any] = {}
        for campo in ("color_primario", "color_primario_fuerte", "color_primario_soft", "color_acento"):
            valor = validar_hex(datos.get(campo))
            limpio[campo] = valor or DEFAULT_COLORES.get(campo)
        return limpio

    @staticmethod
    def css_vars(config: ConfiguracionTaller | None) -> dict[str, str]:
        """Variables CSS de apariencia a inyectar en base.html (siempre HEX válidos)."""
        fuente = config
        if fuente is None:
            fuente = ConfiguracionTaller.query.first()
        primario = validar_hex(getattr(fuente, "color_primario", None)) or DEFAULT_COLORES["color_primario"]
        fuerte = validar_hex(getattr(fuente, "color_primario_fuerte", None)) or DEFAULT_COLORES["color_primario_fuerte"]
        soft = validar_hex(getattr(fuente, "color_primario_soft", None)) or DEFAULT_COLORES["color_primario_soft"]
        acento = validar_hex(getattr(fuente, "color_acento", None)) or DEFAULT_COLORES["color_acento"]
        return {
            "--siam-primary": primario,
            "--siam-primary-strong": fuerte,
            "--siam-primary-soft": soft,
            "--siam-accent": acento,
            "--siam-gradient": f"linear-gradient(135deg, {primario}, {fuerte})",
        }

    # ---------- Preguntas sugeridas del asistente ----------

    @staticmethod
    def preguntas(config: ConfiguracionTaller | None) -> list[str]:
        valor = getattr(config, "ia_preguntas_sugeridas", None) if config else None
        if valor:
            try:
                lista = json.loads(valor)
                if isinstance(lista, list):
                    return [str(p) for p in lista if str(p).strip()]
            except (TypeError, ValueError):
                pass
        return list(PREGUNTAS_SUGERIDAS_DEFAULT)

    @staticmethod
    def serializar_preguntas(texto: str) -> str:
        """Convierte texto (una por línea) en JSON."""
        lista = [ln.strip() for ln in texto.replace("\r\n", "\n").split("\n") if ln.strip()]
        return json.dumps(lista, ensure_ascii=False)

    @staticmethod
    def hora_en_intervalo(hora: Any, intervalo_min: int | None) -> bool:
        """Valida que la hora de una cita se alinee a la grilla configurada."""
        if not intervalo_min or intervalo_min <= 0:
            return True
        return hora is not None and hora.minute % intervalo_min == 0

    # ---------- Estado del sistema ----------

    @staticmethod
    def estado_sistema() -> list[dict[str, Any]]:
        """Chequeos para el botón 'Comprobar sistema'. Nunca expone secretos."""
        resultados: list[dict[str, Any]] = []
        try:
            db.session.execute(text("SELECT 1"))
            db_ok = True
        except Exception:
            db_ok = False
        resultados.append({
            "nombre": "Base de datos",
            "estado": "verde" if db_ok else "rojo",
            "detalle": "Conexión correcta" if db_ok else "No se pudo conectar",
        })

        try:
            ConfiguracionTaller.query.first()
            config_ok = True
        except Exception:
            config_ok = False
        resultados.append({
            "nombre": "Configuración del taller",
            "estado": "verde" if config_ok else "amarillo",
            "detalle": "Accesible" if config_ok else "No se pudo leer la configuración",
        })

        subidas = None
        try:
            ruta = current_app.root_path
            subidas = os.path.join(ruta, "static", "uploads")
            if not os.path.isdir(subidas):
                os.makedirs(subidas, exist_ok=True)
            escribible = os.access(subidas, os.W_OK)
        except Exception:
            escribible = False
        resultados.append({
            "nombre": "Carpeta de archivos",
            "estado": "verde" if escribible else "amarillo",
            "detalle": "Almacenamiento local disponible. En Render es efímero." if escribible else "No escribible (en Render el almacenamiento es efímero)",
        })

        return resultados

    @staticmethod
    def datos_sistema() -> dict[str, Any]:
        """Datos de la sección Sistema (versión, entorno, BD). Sin secretos."""
        try:
            db.session.execute(text("SELECT 1"))
            bd_estado = "conectado"
        except Exception:
            bd_estado = "no disponible"
        return {
            "app": "SIAM",
            "version": "2.0.0",
            "entorno": current_app.config.get("ENV", "development") or "development",
            "debug": current_app.debug,
            "bd_estado": bd_estado,
            "migracion": ConfiguracionService.migracion_actual(),
        }

    @staticmethod
    def migracion_actual() -> str | None:
        try:
            row = db.session.execute(text("SELECT version_num FROM alembic_version")).first()
            return row[0] if row else None
        except Exception:
            return None

    @staticmethod
    def datos_seguridad() -> dict[str, Any]:
        """Datos de la sección Seguridad. NUNCA incluye SECRET_KEY, DATABASE_URL, tokens ni contraseñas."""
        session_lifetime = current_app.config.get("PERMANENT_SESSION_LIFETIME")
        if session_lifetime is not None and hasattr(session_lifetime, "total_seconds"):
            session_lifetime = int(session_lifetime.total_seconds() // 3600)
        else:
            session_lifetime = 8
        return {
            "csrf_habilitado": bool(current_app.config.get("WTF_CSRF_ENABLED", True)),
            "csrf_tiempo": current_app.config.get("WTF_CSRF_TIME_LIMIT"),
            "csrf_limite": "1 hora" if current_app.config.get("WTF_CSRF_TIME_LIMIT") else "ilimitado",
            "sesion_timeout": session_lifetime,
            "ratelimit_habilitado": bool(current_app.config.get("RATELIMIT_ENABLED", False)),
            "ratelimit_limite": current_app.config.get("RATELIMIT_DEFAULT", ""),
            "roles": ["admin", "recepcion", "mecanico", "cliente"],
        }
