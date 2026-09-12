"""Tests for stability audit fixes."""
import pytest
from models import Usuario
from database.commit import safe_commit, json_success, json_error


def _crear_admin(db):
    u = Usuario(nombre="Admin", correo="admin@test.com", rol="admin")
    u.set_password("admin123")
    db.session.add(u)
    safe_commit()
    return u


def _login(client, correo="admin@test.com", password="admin123"):
    return client.post("/auth/login", data={
        "correo": correo,
        "password": password,
    }, follow_redirects=True)


class TestSecurityFixes:
    """Verify security fixes from stability audit."""

    def test_citas_cambiar_estado_rejects_get(self, client, db):
        """CITAS-2: cambiar_estado must reject GET (should be POST only)."""
        _crear_admin(db)
        _login(client)
        resp = client.get("/citas/cambiar-estado/1/completado", follow_redirects=True)
        assert resp.status_code in (405,), f"Expected 405, got {resp.status_code}"

    def test_dashboard_api_resumen_endpoint(self, client, db):
        """DASH-1: /dashboard/api/resumen must exist and return valid JSON."""
        _crear_admin(db)
        _login(client)
        resp = client.get("/dashboard/api/resumen")
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, dict)
        assert "total_clientes" in data
        assert "ingresos_hoy" in data


class TestCommitHelpers:
    """Verify safe_commit and json helpers."""

    def test_json_success_structure(self):
        resp = json_success({"id": 1}, "OK")
        data = resp.get_json()
        assert data["success"] is True
        assert data["message"] == "OK"
        assert data["id"] == 1

    def test_json_error_structure(self):
        resp, code = json_error("Error", 400)
        data = resp.get_json()
        assert data["success"] is False
        assert data["error"] == "Error"
        assert code == 400

    def test_dead_code_removed(self):
        """Dead code functions flash_or_json and handle_form_error must not exist."""
        import database.commit as mod
        assert not hasattr(mod, "flash_or_json")
        assert not hasattr(mod, "handle_form_error")


class TestErrorHandlers:
    """Test error page rendering."""

    def test_404_page(self, client):
        resp = client.get("/ruta-que-no-existe-xyz")
        assert resp.status_code == 404

    def test_health_endpoint(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "healthy"

    def test_root_landing(self, client):
        resp = client.get("/")
        assert resp.status_code in (200, 302)


class TestRouteAccessibility:
    """Test all main routes are accessible after login."""

    def test_all_get_routes_authenticated(self, client, db):
        _crear_admin(db)
        _login(client)

        routes = [
            "/dashboard/",
            "/clientes/",
            "/clientes/crear",
            "/vehiculos/",
            "/vehiculos/crear",
            "/servicios/",
            "/servicios/crear",
            "/mecanicos/",
            "/mecanicos/crear",
            "/citas/",
            "/citas/crear",
            "/ordenes-trabajo/",
            "/ordenes-trabajo/crear",
            "/facturas/",
            "/facturas/configuracion",
            "/inventario/",
            "/inventario/crear",
            "/inventario/alertas",
            "/inventario/categorias",
            "/inventario/categorias/crear",
            "/sedes/",
            "/sedes/api",
            "/asistente/",
        ]
        errors = []
        for url in routes:
            resp = client.get(url, follow_redirects=True)
            if resp.status_code not in (200, 302):
                errors.append(f"GET {url} -> {resp.status_code}")
        assert not errors, f"Route errors: {errors}"

    def test_public_routes_no_login(self, client):
        routes = [
            "/",
            "/health",
            "/auth/login",
            "/auth/register",
            "/sedes/",
            "/sedes/api",
            "/robots.txt",
            "/sitemap.xml",
        ]
        errors = []
        for url in routes:
            resp = client.get(url)
            if resp.status_code not in (200, 302):
                errors.append(f"GET {url} -> {resp.status_code}")
        assert not errors, f"Public route errors: {errors}"
