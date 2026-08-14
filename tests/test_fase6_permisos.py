"""FASE 6 - Permisos por rol: clientes bloqueados de los módulos administrativos."""
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


MODULOS_STAFF = [
    ("/dashboard/", "dashboard"),
    ("/clientes/", "clientes"),
    ("/vehiculos/", "vehiculos"),
    ("/servicios/", "servicios"),
    ("/citas/", "citas"),
    ("/mecanicos/", "mecanicos"),
    ("/inventario/", "inventario"),
    ("/ordenes-trabajo/", "ordenes"),
    ("/facturas/", "facturas"),
    ("/reportes/", "reportes"),
    ("/recordatorios/", "recordatorios"),
    ("/ia/", "ia"),
]


class TestClienteBloqueado:
    def test_cliente_no_accede_a_modulos_admin(self, client, db):
        _crear_usuario(db, "cliente_perm@test.com", "cliente")
        _login(client, "cliente_perm@test.com")
        for url, _ in MODULOS_STAFF:
            resp = client.get(url, follow_redirects=False)
            assert resp.status_code in (302, 403), f"{url} -> {resp.status_code}"
            if resp.status_code == 302:
                assert "portal" in resp.headers.get("Location", ""), f"{url} redirige a {resp.headers.get('Location')}"

    def test_cliente_bloqueado_sigue_vendo_401_en_api(self, client, db):
        resp = client.get("/api/asistencia")
        assert resp.status_code in (401, 302)

    def test_cliente_si_puede_usar_su_portal(self, client, db):
        _crear_usuario(db, "cliente_perm2@test.com", "cliente")
        _login(client, "cliente_perm2@test.com")
        resp = client.get("/portal/", follow_redirects=True)
        assert resp.status_code == 200

    def test_cliente_si_puede_usar_sedes(self, client, db):
        _crear_usuario(db, "cliente_perm3@test.com", "cliente")
        _login(client, "cliente_perm3@test.com")
        resp = client.get("/sedes/")
        assert resp.status_code == 200

    def test_cliente_si_puede_usar_asistente(self, client, db):
        _crear_usuario(db, "cliente_perm4@test.com", "cliente")
        _login(client, "cliente_perm4@test.com")
        resp = client.get("/asistente/")
        assert resp.status_code == 200


class TestAccesoStaff:
    def test_admin_accede_a_modulos(self, client, db):
        _crear_usuario(db, "admin_perm@test.com", "admin")
        _login(client, "admin_perm@test.com")
        for url, _ in MODULOS_STAFF:
            resp = client.get(url)
            assert resp.status_code == 200, f"{url} -> {resp.status_code}"

    def test_mecanico_accede_a_modulos_habilitados(self, client, db):
        _crear_usuario(db, "mec_perm@test.com", "mecanico")
        _login(client, "mec_perm@test.com")
        for url, _ in [("/dashboard/", "d"), ("/ordenes-trabajo/", "o"), ("/vehiculos/", "v")]:
            resp = client.get(url)
            assert resp.status_code == 200, f"{url} -> {resp.status_code}"

    def test_recepcion_no_accede_a_reportes_solo_admin(self, client, db):
        _crear_usuario(db, "rec_perm@test.com", "recepcion")
        _login(client, "rec_perm@test.com")
        resp = client.get("/reportes/", follow_redirects=True)
        assert resp.status_code == 200
        assert "No tienes permisos de administrador" in resp.data.decode("utf-8")

    def test_sin_sesion_redirige_a_login(self, client):
        for url, _ in MODULOS_STAFF:
            resp = client.get(url, follow_redirects=False)
            assert resp.status_code == 302, f"{url} -> {resp.status_code}"
            assert "auth/login" in resp.headers.get("Location", ""), f"{url} -> {resp.headers.get('Location')}"
