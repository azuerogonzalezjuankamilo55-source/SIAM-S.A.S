"""FASE 10 - Gestión de asistencias para el personal (recomendación #1)."""
from models import Usuario, AsistenciaEmergencia


def _crear_usuario(db, correo, rol):
    u = Usuario(nombre=rol, correo=correo, rol=rol)
    u.set_password("clave1234")
    db.session.add(u)
    db.session.commit()
    return u


def _login(client, correo, password="clave1234"):
    return client.post("/auth/login", data={
        "correo": correo,
        "password": password,
    }, follow_redirects=True)


def _crear_asistencia(db, estado="pendiente", nombre="Cliente Aux"):
    a = AsistenciaEmergencia(
        cliente_nombre=nombre,
        telefono="3001112222",
        descripcion="Solicitud de grúa",
        latitud=4.7110, longitud=-74.0721,
        estado=estado,
    )
    db.session.add(a)
    db.session.commit()
    return a


class TestAcceso:
    def test_pagina_requiere_login(self, client):
        resp = client.get("/sedes/asistencias", follow_redirects=False)
        assert resp.status_code == 302
        assert "auth/login" in resp.headers.get("Location", "")

    def test_cliente_bloqueado(self, client, db):
        _crear_usuario(db, "cli_gest@test.com", "cliente")
        _login(client, "cli_gest@test.com")
        resp = client.get("/sedes/asistencias", follow_redirects=False)
        assert resp.status_code == 302
        assert "portal" in resp.headers.get("Location", "")

    def test_mecanico_accede(self, client, db):
        _crear_usuario(db, "mec_gest@test.com", "mecanico")
        _login(client, "mec_gest@test.com")
        resp = client.get("/sedes/asistencias")
        assert resp.status_code == 200
        assert b"Asistencias de Emergencia" in resp.data


class TestPanel:
    def test_admin_ve_solicitudes(self, client, db):
        _crear_usuario(db, "admin_gest@test.com", "admin")
        _crear_asistencia(db)
        _login(client, "admin_gest@test.com")
        resp = client.get("/sedes/asistencias")
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        assert "Cliente Aux" in html
        assert "Pendiente" in html

    def test_filtro_por_estado(self, client, db):
        _crear_usuario(db, "admin_gest2@test.com", "admin")
        _crear_asistencia(db, estado="pendiente", nombre="Pendiente X")
        _crear_asistencia(db, estado="atendido", nombre="Atendida Y")
        _login(client, "admin_gest2@test.com")
        resp = client.get("/sedes/asistencias?estado=atendido")
        html = resp.data.decode("utf-8")
        assert "Atendida Y" in html
        assert "Pendiente X" not in html


class TestCambiarEstado:
    def test_marcar_en_camino(self, client, db):
        _crear_usuario(db, "admin_gest3@test.com", "admin")
        a = _crear_asistencia(db)
        _login(client, "admin_gest3@test.com")
        resp = client.post(f"/sedes/asistencias/{a.id}/estado", json={"estado": "en_camino"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["estado"] == "en_camino"
        assert db.session.get(AsistenciaEmergencia, a.id).estado == "en_camino"

    def test_estado_invalido(self, client, db):
        _crear_usuario(db, "admin_gest4@test.com", "admin")
        a = _crear_asistencia(db)
        _login(client, "admin_gest4@test.com")
        resp = client.post(f"/sedes/asistencias/{a.id}/estado", json={"estado": "basura"})
        assert resp.status_code == 400

    def test_solicitud_finalizada_no_cambia(self, client, db):
        _crear_usuario(db, "admin_gest5@test.com", "admin")
        a = _crear_asistencia(db, estado="atendido")
        _login(client, "admin_gest5@test.com")
        resp = client.post(f"/sedes/asistencias/{a.id}/estado", json={"estado": "en_camino"})
        assert resp.status_code == 400
        assert db.session.get(AsistenciaEmergencia, a.id).estado == "atendido"

    def test_cliente_no_cambia_estado(self, client, db):
        _crear_usuario(db, "cli_gest2@test.com", "cliente")
        a = _crear_asistencia(db)
        _login(client, "cli_gest2@test.com")
        resp = client.post(f"/sedes/asistencias/{a.id}/estado", json={"estado": "atendido"})
        assert resp.status_code == 302
        assert "portal" in resp.headers.get("Location", "")
        assert db.session.get(AsistenciaEmergencia, a.id).estado == "pendiente"

    def test_asistencia_inexistente_404(self, client, db):
        _crear_usuario(db, "admin_gest6@test.com", "admin")
        _login(client, "admin_gest6@test.com")
        resp = client.post("/sedes/asistencias/99999/estado", json={"estado": "atendido"})
        assert resp.status_code == 404
