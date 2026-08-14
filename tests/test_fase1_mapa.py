"""FASE 1 - Mapa y ubicación: pruebas de /sedes, /api/ubicacion y /api/asistencia."""
from models import Usuario, AsistenciaEmergencia


def _crear_cliente(db, correo="cliente_mapa@test.com"):
    u = Usuario(nombre="Cliente Mapa", correo=correo, rol="cliente")
    u.set_password("clave1234")
    db.session.add(u)
    db.session.commit()
    return u


def _login(client, correo="cliente_mapa@test.com", password="clave1234"):
    return client.post("/auth/login", data={
        "correo": correo,
        "password": password,
    }, follow_redirects=True)


class TestSedes:
    def test_pagina_sedes_publica(self, client):
        resp = client.get("/sedes/")
        assert resp.status_code == 200
        assert b"Sedes y Asistencia" in resp.data or b"Sede" in resp.data

    def test_api_sedes_devuelve_lista(self, client):
        resp = client.get("/sedes/api")
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert "latitud" in data[0]
        assert "longitud" in data[0]

    def test_sedes_tienen_datos_completos(self, client):
        resp = client.get("/sedes/api")
        for sede in resp.get_json():
            assert sede.get("nombre")
            assert sede.get("direccion")
            assert sede.get("telefono")
            assert sede.get("horario")
            assert sede.get("latitud") is not None
            assert sede.get("longitud") is not None
            assert isinstance(sede.get("servicios"), list)


class TestApiUbicacion:
    def test_ubicacion_requiere_login(self, client):
        resp = client.post("/api/ubicacion", json={
            "latitude": 4.7110, "longitude": -74.0721,
        })
        assert resp.status_code in (401, 302)

    def test_ubicacion_crea_asistencia(self, client, db):
        _crear_cliente(db)
        _login(client)
        resp = client.post("/api/ubicacion", json={
            "latitude": 4.7110,
            "longitude": -74.0721,
            "accuracy": 25.0,
            "descripcion": "Prueba de ubicación",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["estado"] == "pendiente"

        from database.db import db as _db
        asistencia = _db.session.get(AsistenciaEmergencia, data["id"])
        assert asistencia is not None
        assert asistencia.latitud == 4.7110
        assert asistencia.longitud == -74.0721
        assert asistencia.precision_metros == 25.0
        assert asistencia.estado == "pendiente"
        assert asistencia.created_at is not None

    def test_ubicacion_sin_coordenadas(self, client, db):
        _crear_cliente(db)
        _login(client)
        resp = client.post("/api/ubicacion", json={"descripcion": "sin coord"})
        assert resp.status_code == 400

    def test_ubicacion_datos_invalidos(self, client, db):
        _crear_cliente(db)
        _login(client)
        resp = client.post("/api/ubicacion", data="no json", content_type="text/plain")
        assert resp.status_code == 400


class TestApiAsistencia:
    def test_asistencia_crear_y_listar(self, client, db):
        u = _crear_cliente(db)
        _login(client)
        resp = client.post("/api/asistencia", json={
            "descripcion": "Me quedé varado en la autopista",
            "latitude": 4.7000,
            "longitude": -74.0800,
            "accuracy": 30.0,
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True

        resp_list = client.get("/api/asistencia")
        assert resp_list.status_code == 200
        items = resp_list.get_json()
        assert len(items) >= 1
        assert items[0]["descripcion"] == "Me quedé varado en la autopista"
        assert items[0]["estado"] == "pendiente"

    def test_cancelar_asistencia(self, client, db):
        u = _crear_cliente(db)
        _login(client)
        resp = client.post("/api/ubicacion", json={
            "latitude": 4.7110, "longitude": -74.0721,
        })
        asistencia_id = resp.get_json()["id"]

        resp_cancel = client.post(f"/api/asistencia/{asistencia_id}/cancelar")
        assert resp_cancel.status_code == 200
        assert resp_cancel.get_json()["estado"] == "cancelado"

    def test_cancelar_asistencia_ajena(self, client, db):
        u1 = _crear_cliente(db)
        u2 = _crear_cliente(db, correo="otro_mapa@test.com")
        _login(client, correo="otro_mapa@test.com")

        from database.db import db as _db
        a = AsistenciaEmergencia(usuario_id=u1.id, latitud=4.7, longitud=-74.07)
        _db.session.add(a)
        _db.session.commit()

        resp = client.post(f"/api/asistencia/{a.id}/cancelar")
        assert resp.status_code in (404, 500)
