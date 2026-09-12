"""FASE 10.2 - Migración de Google Maps a Leaflet + OpenStreetMap + OSRM.

Cubre: servicio OSRM (éxito / caído / sin configurar), geometría de ruta en
clientes-en-camino, conquistas sin OSRM (mapa sigue funcionando), plantillas
sin referencias a Google, y regresión de permisos.
"""
import json
from datetime import date, time
from unittest.mock import patch

import pytest

from models import Cliente, Usuario, Vehiculo, Cita, UbicacionCliente
from services.routes_service import RoutesService

COORDS = {"latitude": 4.62, "longitude": -74.12, "accuracy": 20.0}

OSRM_OK = {
    "code": "Ok",
    "routes": [{
        "distance": 5234.5,
        "duration": 781.2,
        "geometry": {
            "type": "LineString",
            "coordinates": [[-74.2390573, 4.5712283], [-74.16, 4.60], [-74.12, 4.62]],
        },
    }],
}


@pytest.fixture(autouse=True)
def _limpiar_cache_osrm():
    import services.routes_service as rs
    rs._cache.clear()
    yield
    rs._cache.clear()


def _crear_cliente(db, correo="cli_osrm@test.com", placa="OSR-001", estado="confirmada"):
    c = Cliente(nombre="Cliente OSRM", correo=correo, telefono="3007654321")
    db.session.add(c)
    db.session.flush()
    u = Usuario(nombre="Cliente OSRM", correo=correo, rol="cliente", cliente_id=c.id)
    u.set_password("clave1234")
    db.session.add(u)
    v = Vehiculo(cliente_id=c.id, marca="Renault", modelo="Logan", placa=placa)
    db.session.add(v)
    db.session.flush()
    cita = Cita(cliente_id=c.id, vehiculo_id=v.id,
                fecha=date.today(), hora=time(10, 0), estado=estado)
    db.session.add(cita)
    db.session.commit()
    return c, u, v, cita


def _crear_admin(db, correo="admin_osrm@test.com"):
    u = Usuario(nombre="Admin OSRM", correo=correo, rol="admin")
    u.set_password("clave1234")
    db.session.add(u)
    db.session.commit()
    return u


def _login(client, correo="cli_osrm@test.com", clave="clave1234"):
    return client.post("/auth/login", data={"correo": correo, "password": clave},
                       follow_redirects=True)


class _Respuesta:
    status = 200

    def __init__(self, data):
        self._data = data

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return json.dumps(self._data).encode("utf-8")


class TestRoutesServiceOSRM:

    def test_osrm_desconfigurado_sin_red(self, app):
        with app.app_context():
            ruta = RoutesService.distancia_y_duracion((4.5712283, -74.2390573), (4.62, -74.12))
        assert ruta["ok"] is False
        assert ruta["error"] == "sin_osrm_configurado"

    def test_osrm_ok_devuelve_distancia_duracion_geometria(self, app):
        with patch("services.routes_service.urlopen", return_value=_Respuesta(OSRM_OK)):
            with app.app_context():
                app.config["OSRM_BASE_URL"] = "https://router.project-osrm.org"
                ruta = RoutesService.distancia_y_duracion((4.57, -74.23), (4.62, -74.12))
        assert ruta["ok"] is True
        assert ruta["distance_m"] == 5234
        assert ruta["duration_s"] == 781
        assert len(ruta["geometry"]) == 3
        assert ruta["geometry"][0] == (-74.2390573, 4.5712283)

    def test_osrm_sin_rutas(self, app):
        with patch("services.routes_service.urlopen", return_value=_Respuesta({"code": "Ok", "routes": []})):
            with app.app_context():
                app.config["OSRM_BASE_URL"] = "https://router.project-osrm.org"
                ruta = RoutesService.distancia_y_duracion((4.57, -74.23), (4.62, -74.12))
        assert ruta["ok"] is False
        assert ruta["error"] == "sin_ruta"

    def test_osrm_caido_no_lanza(self, app):
        with patch("services.routes_service.urlopen", side_effect=OSError("sin red")):
            with app.app_context():
                app.config["OSRM_BASE_URL"] = "https://router.project-osrm.org"
                ruta = RoutesService.distancia_y_duracion((4.57, -74.23), (4.62, -74.12))
        assert ruta["ok"] is False
        assert ruta["error"] == "error_api_rutas"

    def test_cache_devuelve_mismo_resultado(self, app):
        with patch("services.routes_service.urlopen", return_value=_Respuesta(OSRM_OK)) as mock:
            with app.app_context():
                app.config["OSRM_BASE_URL"] = "https://router.project-osrm.org"
                primera = RoutesService.distancia_y_duracion((4.57, -74.23), (4.62, -74.12))
                segunda = RoutesService.distancia_y_duracion((4.57, -74.23), (4.62, -74.12))
        assert primera["ok"] is True and segunda["ok"] is True
        assert mock.call_count == 1


class TestClientesEnCaminoConOSRM:

    def test_incluye_geometria_de_ruta(self, client, db):
        _crear_cliente(db)
        _login(client)
        client.post("/api/ubicacion/actualizar", json=COORDS)
        client.get("/auth/logout")

        _crear_admin(db)
        _login(client, correo="admin_osrm@test.com")
        client.application.config["OSRM_BASE_URL"] = "https://router.project-osrm.org"
        with patch("services.routes_service.urlopen", return_value=_Respuesta(OSRM_OK)):
            r = client.get("/api/admin/clientes-en-camino")
        assert r.status_code == 200
        c1 = r.get_json()["clientes"][0]
        assert c1["ruta_ok"] is True
        assert c1["distancia_m"] == 5234
        assert c1["duracion_s"] == 781
        assert len(c1["ruta_geometria"]) == 3
        primero = c1["ruta_geometria"][0]
        assert primero["lat"] == pytest.approx(4.5712283)
        assert primero["lng"] == pytest.approx(-74.2390573)

    def test_osrm_caido_no_rompe_api(self, client, db):
        _crear_cliente(db)
        _login(client)
        client.post("/api/ubicacion/actualizar", json=COORDS)
        client.get("/auth/logout")

        _crear_admin(db)
        _login(client, correo="admin_osrm@test.com")
        client.application.config["OSRM_BASE_URL"] = "https://router.project-osrm.org"
        with patch("services.routes_service.urlopen", side_effect=OSError("caido")):
            r = client.get("/api/admin/clientes-en-camino")
        assert r.status_code == 200
        data = r.get_json()
        assert data["success"] is True
        assert len(data["clientes"]) == 1
        c1 = data["clientes"][0]
        assert c1["ruta_ok"] is False
        assert c1["ruta_error"] == "error_api_rutas"
        assert c1["ruta_geometria"] == []


class TestPlantillasSinGoogle:

    def test_portal_sin_google_y_con_leaflet(self, client, db):
        _crear_cliente(db)
        _login(client)
        r = client.get("/portal/")
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        assert "maps.googleapis.com" not in html
        assert "google.maps" not in html
        assert "GOOGLE_MAPS_API_KEY" not in html
        assert "leaflet@1.9.4/dist/leaflet" in html
        assert "tile.openstreetmap.org" in html
        assert "OpenStreetMap" in html
        assert 'id="mapaMiUbicacion"' in html

    def test_dashboard_sin_google_y_con_leaflet(self, client, db):
        _crear_admin(db)
        _login(client, correo="admin_osrm@test.com")
        r = client.get("/dashboard/")
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        assert "maps.googleapis.com" not in html
        assert "google.maps" not in html
        assert "GOOGLE_MAPS_API_KEY" not in html
        assert "leaflet@1.9.4/dist/leaflet" in html
        assert "tile.openstreetmap.org" in html
        assert "OpenStreetMap" in html
        assert 'id="mapaClientesCamino"' in html
        assert "avisoRutasCamino" in html


class TestRegresionPermisos:

    def test_cliente_sin_acceso_al_panel(self, client, db):
        _crear_cliente(db)
        _login(client)
        r = client.get("/dashboard/", follow_redirects=False)
        assert r.status_code in (302, 403)

    def test_cliente_sin_acceso_a_clientes_en_camino(self, client, db):
        _crear_cliente(db)
        _login(client)
        r = client.get("/api/admin/clientes-en-camino")
        assert r.status_code in (302, 403)

    def test_staff_ve_clientes_en_camino(self, client, db):
        _crear_cliente(db)
        _crear_admin(db)
        _login(client, correo="admin_osrm@test.com")
        r = client.get("/api/admin/clientes-en-camino")
        assert r.status_code == 200

    def test_coordenadas_invalidas_rechazadas(self, client, db):
        _crear_cliente(db)
        _login(client)
        r = client.post("/api/ubicacion/actualizar",
                        json={"latitude": 91, "longitude": -74.12})
        assert r.status_code == 400
        r2 = client.post("/api/ubicacion/actualizar",
                         json={"latitude": 4.6, "longitude": -200})
        assert r2.status_code == 400