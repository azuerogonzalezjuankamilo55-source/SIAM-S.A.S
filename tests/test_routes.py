import pytest
from models import Usuario


def _crear_admin(db):
    u = Usuario(nombre="Admin", correo="admin@test.com", rol="admin")
    u.set_password("admin123")
    db.session.add(u)
    db.session.commit()
    return u


def _login(client, correo="admin@test.com", password="admin123"):
    return client.post("/auth/login", data={
        "correo": correo,
        "password": password,
    }, follow_redirects=True)


class TestAuthRoutes:
    def test_login_get(self, client):
        resp = client.get("/auth/login")
        assert resp.status_code == 200

    def test_login_post_exitoso(self, client, db):
        _crear_admin(db)
        resp = _login(client)
        assert resp.status_code == 200

    def test_login_post_fallido(self, client, db):
        _crear_admin(db)
        resp = client.post("/auth/login", data={
            "correo": "admin@test.com",
            "password": "mala",
        }, follow_redirects=True)
        assert resp.status_code == 200

    def test_register_get(self, client):
        resp = client.get("/auth/register")
        assert resp.status_code == 200

    def test_register_post(self, client, db):
        resp = client.post("/auth/register", data={
            "nombre": "Nuevo",
            "correo": "nuevo@test.com",
            "password": "pass1234",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert Usuario.query.filter_by(correo="nuevo@test.com").count() == 1


class TestDashboardRoutes:
    def test_dashboard_requiere_login(self, client):
        resp = client.get("/dashboard/", follow_redirects=True)
        assert resp.status_code == 200

    def test_dashboard_acceso(self, client, db):
        _crear_admin(db)
        _login(client)
        resp = client.get("/dashboard/")
        assert resp.status_code == 200


class TestClientesRoutes:
    def test_listar_requiere_login(self, client):
        resp = client.get("/clientes/", follow_redirects=True)
        assert resp.status_code == 200

    def test_crear_cliente(self, client, db):
        _crear_admin(db)
        _login(client)
        resp = client.post("/clientes/crear", data={
            "nombre": "Cliente Test",
            "telefono": "123456789",
            "correo": "cliente@test.com",
            "cedula": "ABC123",
        }, follow_redirects=True)
        assert resp.status_code == 200

    def test_listar_clientes(self, client, db):
        _crear_admin(db)
        _login(client)
        resp = client.get("/clientes/")
        assert resp.status_code == 200


class TestHealth:
    def test_health_endpoint(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json["status"] == "healthy"

    def test_root_redirect(self, client):
        resp = client.get("/", follow_redirects=True)
        assert resp.status_code in (200, 302)
