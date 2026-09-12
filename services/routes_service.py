"""Cálculo de rutas con OSRM (Open Source Routing Machine) público.

SIAM ya no usa Google Routes API. La ruta taller -> cliente se consulta al
servidor público de OSRM (router.project-osrm.org por defecto; configurable
con OSRM_BASE_URL si el despliegue usa una instancia propia).

El servicio nunca falla hacia arriba: si OSRM no está disponible, devuelve
"ok": False y el panel solo muestra los marcadores (la interfaz no se rompe).
Los datos de la geometría se devuelven como GeoJSON LineString para dibujarse
con Leaflet.
"""
import json
import logging
import os
import time
from typing import Any
from urllib.request import Request, urlopen

from flask import current_app, has_app_context

logger = logging.getLogger("siam.routes_service")

_TIMEOUT_SECONDS = 6
_CACHE_TTL_SECONDS = 45
# Segundos de caché para evitar llamadas repetidas por cada cliente en cada
# polling del panel del taller. La precisión sigue siendo buena y no satura
# el servidor público de OSRM (su política pide un uso responsable).

_profile = "driving"
_cache: dict[tuple[float, ...], tuple[float, dict[str, Any]]] = {}


class RoutesService:
    """Wrapper server-side de OSRM (distancias/duraciones reales por carretera).

    La clave no existe (no se necesitan API keys): el navegador nunca hace
    llamadas a OSRM, solo el servidor.
    """

    TRAVEL_MODE_DRIVE = "DRIVE"  # compatibilidad con consumidores existentes

    @staticmethod
    def base_url() -> str:
        url = ""
        if has_app_context():
            url = current_app.config.get("OSRM_BASE_URL") or ""
        if not url:
            url = os.getenv("OSRM_BASE_URL", "")
        return str(url).strip().rstrip("/")

    @staticmethod
    def _cache_key(origin: tuple[float, float], destination: tuple[float, float]):
        return (
            round(origin[0], 4),
            round(origin[1], 4),
            round(destination[0], 4),
            round(destination[1], 4),
        )

    @classmethod
    def distancia_y_duracion(
        cls,
        origin: tuple[float, float],
        destination: tuple[float, float],
        travel_mode: str = TRAVEL_MODE_DRIVE,
    ) -> dict[str, Any]:
        """Retorna {"ok": True, "distance_m", "duration_s", "geometry"} o un
        dict de error. En ningún caso lanza excepción."""
        key = cls._cache_key(origin, destination)
        now = time.monotonic()
        cached = _cache.get(key)
        if cached and now - cached[0] < _CACHE_TTL_SECONDS:
            return cached[1]

        result = cls._compute(origin, destination)
        _cache[key] = (now, result)
        return result

    @classmethod
    def _compute(
        cls,
        origin: tuple[float, float],
        destination: tuple[float, float],
    ) -> dict[str, Any]:
        base = cls.base_url()
        if not base:
            logger.debug("OSRM_BASE_URL no configurada; ruta no disponible.")
            return {"ok": False, "error": "sin_osrm_configurado"}

        url = (
            f"{base}/route/v1/{_profile}/"
            f"{origin[1]},{origin[0]};{destination[1]},{destination[0]}"
            "?overview=full&steps=false&alternatives=false&geometries=geojson"
        )
        req = Request(url, headers={"Accept": "application/json"}, method="GET")
        try:
            with urlopen(req, timeout=_TIMEOUT_SECONDS) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:  # noqa: BLE001 - OSRM no debe romper el panel
            logger.warning("Error llamando a OSRM: %s", e)
            return {"ok": False, "error": "error_api_rutas"}

        routes = data.get("routes") or []
        if not routes:
            logger.debug("Sin ruta válida %s -> %s", origin, destination)
            return {"ok": False, "error": "sin_ruta"}

        geometry = (routes[0].get("geometry") or {}).get("coordinates") or []
        coordinates = [
            (float(pair[0]), float(pair[1]))
            for pair in geometry
            if len(pair) >= 2
        ]

        return {
            "ok": True,
            "distance_m": int(routes[0].get("distance", 0) or 0),
            "duration_s": int(routes[0].get("duration", 0) or 0),
            "travel_mode": _profile,
            "geometry": coordinates,  # pares (lng, lat) tal cual OSRM GeoJSON
        }