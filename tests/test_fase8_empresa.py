"""FASE 8 - Experiencia empresarial: dashboard muestra asistencias de emergencia activas."""
from models import Usuario, AsistenciaEmergencia


def _crear_admin(db):
    u = Usuario(nombre="Admin", correo="admin_empresa@test.com", rol="admin")
    u.set_password("admin123")
    db.session.add(u)
    db.session.commit()
    return u


def _login_admin(client):
    return client.post("/auth/login", data={
        "correo": "admin_empresa@test.com",
        "password": "admin123",
    }, follow_redirects=True)


class TestDashboardAsistencias:
    def test_dashboard_muestra_asistencias_activas(self, client, db):
        _crear_admin(db)
        a = AsistenciaEmergencia(
            cliente_nombre="Cliente Varado",
            telefono="3001234567",
            descripcion="Necesito grúa en la autopista",
            latitud=4.7, longitud=-74.07,
            estado="pendiente",
        )
        db.session.add(a)
        db.session.commit()
        _login_admin(client)
        resp = client.get("/dashboard/")
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        assert "Asistencias de Emergencia Activas" in html
        assert "Cliente Varado" in html

    def test_dashboard_oculta_panel_sin_asistencias(self, client, db):
        _crear_admin(db)
        _login_admin(client)
        resp = client.get("/dashboard/")
        html = resp.data.decode("utf-8")
        assert "Asistencias de Emergencia Activas" not in html

    def test_dashboard_no_muestra_asistencias_canceladas(self, client, db):
        _crear_admin(db)
        a = AsistenciaEmergencia(
            cliente_nombre="Ya Resuelto",
            telefono="3009998888",
            descripcion="Cancelado",
            latitud=4.7, longitud=-74.07,
            estado="cancelado",
        )
        db.session.add(a)
        db.session.commit()
        _login_admin(client)
        resp = client.get("/dashboard/")
        html = resp.data.decode("utf-8")
        assert "Ya Resuelto" not in html
