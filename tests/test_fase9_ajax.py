"""FASE 9 - Sin recargas de página: refresco AJAX del dashboard."""
from models import Usuario


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


class TestDashboardApiResumen:
    def test_api_resumen_requiere_login(self, client):
        resp = client.get("/dashboard/api/resumen")
        assert resp.status_code == 302
        assert "auth/login" in resp.headers.get("Location", "")

    def test_api_resumen_admin(self, client, db):
        _crear_usuario(db, "admin_ajax@test.com", "admin")
        _login(client, "admin_ajax@test.com")
        resp = client.get("/dashboard/api/resumen")
        assert resp.status_code == 200
        data = resp.get_json()
        for key in ["ingresos_hoy", "ingresos_mes", "por_cobrar", "ticket_promedio",
                    "citas_hoy", "ordenes_activas", "inventario_bajo",
                    "ot_retrasadas_count", "facturas_pendientes", "total_clientes",
                    "total_vehiculos", "total_servicios", "total_facturas", "total_mecanicos"]:
            assert key in data, f"falta clave {key}"

    def test_api_resumen_cliente_bloqueado(self, client, db):
        _crear_usuario(db, "cli_ajax@test.com", "cliente")
        _login(client, "cli_ajax@test.com")
        resp = client.get("/dashboard/api/resumen", follow_redirects=False)
        assert resp.status_code == 302
        assert "portal" in resp.headers.get("Location", "")

    def test_dashboard_tiene_atributos_de_refresco(self, client, db):
        _crear_usuario(db, "admin_ajax2@test.com", "admin")
        _login(client, "admin_ajax2@test.com")
        resp = client.get("/dashboard/")
        html = resp.data.decode("utf-8")
        assert "refrescarDashboard" in html
        assert 'data-refresh="ingresos_mes"' in html
        assert 'data-refresh="citas_hoy"' in html
        assert "Actualizar" in html


class TestDashboardApiActividad:
    def test_api_actividad_requiere_login(self, client):
        resp = client.get("/dashboard/api/actividad")
        assert resp.status_code == 302
        assert "auth/login" in resp.headers.get("Location", "")

    def test_api_actividad_admin(self, client, db):
        _crear_usuario(db, "admin_act@test.com", "admin")
        _login(client, "admin_act@test.com")
        resp = client.get("/dashboard/api/actividad")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "eventos" in data
        assert isinstance(data["eventos"], list)
        for evento in data["eventos"]:
            for key in ["tipo", "icono", "texto", "cuando"]:
                assert key in evento, f"falta clave {key}"

    def test_api_actividad_cliente_bloqueado(self, client, db):
        _crear_usuario(db, "cli_act@test.com", "cliente")
        _login(client, "cli_act@test.com")
        resp = client.get("/dashboard/api/actividad", follow_redirects=False)
        assert resp.status_code == 302
        assert "portal" in resp.headers.get("Location", "")

    def test_dashboard_muestra_seccion_actividad(self, client, db):
        _crear_usuario(db, "admin_act2@test.com", "admin")
        _login(client, "admin_act2@test.com")
        resp = client.get("/dashboard/")
        html = resp.data.decode("utf-8")
        assert "Actividad en tiempo real" in html
        assert 'id="actividadLista"' in html
        assert "cargarActividad" in html
