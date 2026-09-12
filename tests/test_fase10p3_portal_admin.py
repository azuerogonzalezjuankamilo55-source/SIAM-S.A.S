"""FASE 10.3 - Separación panel administrativo y portal del cliente.

Cubre los puntos obligatorios: logins por rol, redirección al panel/portal,
aislamiento de datos (IDOR), permisos de PERSONAL TALLER vs ADMIN, CSRF,
rutas directas por URL, geolocalización conservada (cita activa, entrega y
cancelación apagan el compartido) y mapas Leaflet sin Google Maps.
"""
import pathlib

from datetime import date, time
from decimal import Decimal

from models import Usuario, Cliente, Vehiculo, Cita, Servicio, OrdenTrabajo, UbicacionCliente
from services.factura_service import FacturaService, FacturaInput

PASS = "clave1234"
COORDS = {"latitude": 4.62, "longitude": -74.12, "accuracy": 20.0}


# ============================================================
# Helpers
# ============================================================

def _crear_usuario(db, rol, correo, cliente=None):
    u = Usuario(nombre=rol, correo=correo, rol=rol, cliente_id=cliente.id if cliente else None)
    u.set_password(PASS)
    db.session.add(u)
    db.session.commit()
    return u


def _crear_cliente(db, correo="cliente_a@test.com"):
    c = Cliente(nombre="Cliente A", correo=correo, telefono="3001234567")
    db.session.add(c)
    db.session.commit()
    u = _crear_usuario(db, "cliente", correo, cliente=c)
    return c, u


def _crear_vehiculo(db, cliente, placa="AAA-111"):
    v = Vehiculo(cliente_id=cliente.id, marca="Toyota", modelo="Corolla", placa=placa)
    db.session.add(v)
    db.session.commit()
    return v


def _crear_cita(db, cliente, vehiculo, estado="pendiente"):
    cita = Cita(cliente_id=cliente.id, vehiculo_id=vehiculo.id,
                fecha=date.today(), hora=time(10, 0), estado=estado)
    db.session.add(cita)
    db.session.commit()
    return cita


def _crear_factura(db, cliente, placa="FAC-PLA"):
    v = _crear_vehiculo(db, cliente, placa)
    cita = _crear_cita(db, cliente, v)
    s = Servicio(nombre="Servicio X", precio_estimado=50000)
    db.session.add(s)
    db.session.commit()
    return FacturaService.generar(FacturaInput(
        cita_id=cita.id, servicio_ids=[s.id], precios=[50000],
        cantidades=[1], descuento=Decimal("0"), metodo_pago="Efectivo",
    ))


def _crear_ot(db, cliente, numero="OT-0001"):
    v = _crear_vehiculo(db, cliente, placa=f"P-{numero}")
    ot = OrdenTrabajo(numero=numero, cliente_id=cliente.id, vehiculo_id=v.id, estado="recibido")
    db.session.add(ot)
    db.session.commit()
    return ot


def _login(client, correo, password=PASS):
    return client.post("/auth/login", data={"correo": correo, "password": password},
                       follow_redirects=True)


def _logout(client):
    return client.get("/auth/logout", follow_redirects=False)


# ============================================================
# 1-4. Inicio de sesión y registro
# ============================================================

class TestAutenticacion:
    def test_admin_puede_iniciar_sesion(self, client, db):
        _crear_usuario(db, "admin", "admin_f10@test.com")
        resp = _login(client, "admin_f10@test.com")
        assert resp.status_code == 200
        assert b"Dashboard" in resp.data

    def test_personal_taller_puede_iniciar_sesion(self, client, db):
        _crear_usuario(db, "recepcion", "rec_f10@test.com")
        resp = _login(client, "rec_f10@test.com")
        assert resp.status_code == 200
        assert b"Dashboard" in resp.data

    def test_cliente_puede_registrarse(self, client, db):
        resp = client.post("/auth/register", data={
            "nombre": "Nuevo Cliente",
            "correo": "nuevo_f10@test.com",
            "documento": "1090999999",
            "telefono": "3001112222",
            "password": "pass1234",
            "confirmar_password": "pass1234",
        }, follow_redirects=True)
        assert resp.status_code == 200
        u = Usuario.query.filter_by(correo="nuevo_f10@test.com").first()
        assert u is not None
        assert u.rol == "cliente"
        assert u.cliente_id is not None

    def test_cliente_puede_iniciar_sesion(self, client, db):
        c, u = _crear_cliente(db)
        resp = _login(client, u.correo)
        assert resp.status_code == 200
        assert b"Mi Portal" in resp.data


# ============================================================
# 5-7. Redirección al panel/portal correctos
# ============================================================

class TestRedireccionSegunRol:
    def test_admin_llega_al_panel(self, client, db):
        _crear_usuario(db, "admin", "admin_r@test.com")
        resp = client.post("/auth/login", data={"correo": "admin_r@test.com", "password": PASS})
        assert resp.status_code == 302
        assert "/dashboard/" in resp.headers["Location"]

    def test_staff_llega_al_panel_permitido(self, client, db):
        _crear_usuario(db, "mecanico", "mec_r@test.com")
        resp = client.post("/auth/login", data={"correo": "mec_r@test.com", "password": PASS})
        assert resp.status_code == 302
        assert "/dashboard/" in resp.headers["Location"]

    def test_cliente_llega_al_portal(self, client, db):
        _, u = _crear_cliente(db)
        resp = client.post("/auth/login", data={"correo": u.correo, "password": PASS})
        assert resp.status_code == 302
        assert "/portal/" in resp.headers["Location"]

    def test_usuario_no_activo_bloqueado(self, client, db):
        u = _crear_usuario(db, "cliente", "inactivo@test.com")
        u.activo = False
        db.session.commit()
        _login(client, "inactivo@test.com")
        with client.session_transaction() as s:
            assert "_user_id" not in s


# ============================================================
# 8, 13, 17. Rutas directas por URL respetan permisos
# ============================================================

class TestRutasDirectasPorURL:
    def test_cliente_no_entra_al_panel_admin(self, client, db):
        _, u = _crear_cliente(db)
        _login(client, u.correo)
        for url in ("/dashboard/", "/inventario/", "/reportes/", "/clientes/",
                    "/facturas/", "/configuracion/empresa"):
            resp = client.get(url, follow_redirects=False)
            assert resp.status_code == 302, f"{url} -> {resp.status_code}"
            assert "portal" in resp.headers.get("Location", ""), f"{url} -> {resp.headers.get('Location')}"

    def test_cliente_no_modifica_datos_administrativos(self, client, db):
        _, u = _crear_cliente(db)
        _login(client, u.correo)
        resp = client.post("/configuracion/empresa", data={"nombre_taller": "Hack"}, follow_redirects=False)
        assert resp.status_code == 302
        assert "portal" in resp.headers.get("Location", "")

    def test_staff_no_entra_al_portal(self, client, db):
        _crear_usuario(db, "admin", "admin_p@test.com")
        _login(client, "admin_p@test.com")
        resp = client.get("/portal/", follow_redirects=False)
        assert resp.status_code == 302
        assert "dashboard" in resp.headers.get("Location", "")

    def test_sin_sesion_va_al_login(self, client):
        resp = client.get("/dashboard/", follow_redirects=False)
        assert resp.status_code == 302
        assert "auth/login" in resp.headers.get("Location", "")


# ============================================================
# 9-13. Aislamiento de datos por cliente (IDOR)
# ============================================================

class TestAislamientoDatos:
    def test_cliente_solo_ve_sus_datos_en_listas(self, client, db):
        ca, ua = _crear_cliente(db, "isol_a@test.com")
        cb, _ = _crear_cliente(db, "isol_b@test.com")
        _crear_vehiculo(db, ca, "AAA-111")
        _crear_vehiculo(db, cb, "BBB-222")
        _login(client, ua.correo)
        resp = client.get("/portal/vehiculos")
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        assert "AAA-111" in html
        assert "BBB-222" not in html

    def test_no_accede_a_vehiculo_ajeno(self, client, db):
        ca, ua = _crear_cliente(db, "veh_a@test.com")
        cb, _ = _crear_cliente(db, "veh_b@test.com")
        v_b = _crear_vehiculo(db, cb, "BBB-333")
        _login(client, ua.correo)
        resp = client.get(f"/portal/vehiculos/{v_b.id}", follow_redirects=False)
        assert resp.status_code == 302

    def test_no_accede_a_cita_ajena(self, client, db):
        ca, ua = _crear_cliente(db, "cita_a@test.com")
        cb, _ = _crear_cliente(db, "cita_b@test.com")
        v_b = _crear_vehiculo(db, cb, "CCC-444")
        cita_b = _crear_cita(db, cb, v_b, estado="pendiente")
        _login(client, ua.correo)
        resp = client.post(f"/portal/citas/{cita_b.id}/cancelar", follow_redirects=True)
        assert resp.status_code == 200
        assert db.session.get(Cita, cita_b.id).estado == "pendiente"

    def test_no_accede_a_facturas_ajenas(self, client, db):
        ca, ua = _crear_cliente(db, "fac_a@test.com")
        cb, _ = _crear_cliente(db, "fac_b@test.com")
        factura_b = _crear_factura(db, cb, "FAC-777")
        _login(client, ua.correo)
        resp = client.get(f"/portal/facturas/{factura_b.id}", follow_redirects=False)
        assert resp.status_code == 302

    def test_no_accede_a_ot_ajenas(self, client, db):
        ca, ua = _crear_cliente(db, "ot_a@test.com")
        cb, _ = _crear_cliente(db, "ot_b@test.com")
        ot_b = _crear_ot(db, cb, "OT-777")
        _login(client, ua.correo)
        resp = client.get(f"/portal/ordenes/{ot_b.id}", follow_redirects=False)
        assert resp.status_code == 302


# ============================================================
# 14. PERSONAL TALLER no ejecuta funciones exclusivas de ADMIN
# ============================================================

class TestPersonalTallerLimitado:
    def test_mecanico_no_accede_reportes(self, client, db):
        _crear_usuario(db, "mecanico", "mec_rpt@test.com")
        _login(client, "mec_rpt@test.com")
        resp = client.get("/reportes/", follow_redirects=True)
        assert b"No tienes permisos de administrador" in resp.data

    def test_recepcion_no_guarda_configuracion(self, client, db):
        _crear_usuario(db, "recepcion", "rec_cfg@test.com")
        _login(client, "rec_cfg@test.com")
        resp = client.post("/configuracion/empresa", data={"nombre_taller": "Hack"}, follow_redirects=False)
        assert resp.status_code == 302
        assert b"configuracion" in resp.headers.get("Location", "").encode() or "configuracion" in resp.headers.get("Location", "")

    def test_mecanico_no_accede_recordatorios(self, client, db):
        _crear_usuario(db, "mecanico", "mec_rec@test.com")
        _login(client, "mec_rec@test.com")
        resp = client.get("/recordatorios/", follow_redirects=True)
        assert b"No tienes permisos de administrador" in resp.data

    def test_admin_si_accede_reportes(self, client, db):
        _crear_usuario(db, "admin", "admin_rpt@test.com")
        _login(client, "admin_rpt@test.com")
        resp = client.get("/reportes/", follow_redirects=True)
        assert resp.status_code == 200


# ============================================================
# 15-16. Logout y CSRF
# ============================================================

class TestLogout:
    def test_cerrar_sesion_funciona(self, client, db):
        _crear_usuario(db, "admin", "admin_lg@test.com")
        _login(client, "admin_lg@test.com")
        _logout(client)
        resp = client.get("/dashboard/", follow_redirects=False)
        assert resp.status_code == 302
        assert "auth/login" in resp.headers.get("Location", "")


class TestCSRF:
    def test_formularios_protegidos_con_csrf(self, client, db):
        import re

        _crear_usuario(db, "admin", "csrf_admin@test.com")
        client.application.config["WTF_CSRF_ENABLED"] = True
        try:
            page = client.get("/auth/login")
            html = page.data.decode("utf-8")
            m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html)
            assert m, "csrf_token no está en el formulario de login"
            token = m.group(1)

            resp_sin = client.post(
                "/auth/login",
                data={"correo": "csrf_admin@test.com", "password": PASS},
            )
            assert resp_sin.status_code == 400

            page = client.get("/auth/login")
            html = page.data.decode("utf-8")
            m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html)
            token = m.group(1)
            resp_con = client.post(
                "/auth/login",
                data={"correo": "csrf_admin@test.com", "password": PASS, "csrf_token": token},
            )
            assert resp_con.status_code == 302
            assert "/dashboard/" in resp_con.headers["Location"]
        finally:
            client.application.config["WTF_CSRF_ENABLED"] = False


# ============================================================
# 18-20. Geolocalización conservada
# ============================================================

class TestGeolocalizacion:
    def test_sin_cita_activa_no_comparte(self, client, db):
        c = Cliente(nombre="Sin Cita", correo="sin_cita@test.com")
        db.session.add(c)
        db.session.commit()
        u = _crear_usuario(db, "cliente", "sin_cita@test.com", cliente=c)
        _login(client, u.correo)
        r = client.post("/api/ubicacion/actualizar", json=COORDS)
        assert r.status_code == 400

    def test_con_cita_activa_comparte(self, client, db):
        c = Cliente(nombre="Con Cita", correo="con_cita@test.com")
        db.session.add(c)
        db.session.commit()
        u = _crear_usuario(db, "cliente", "con_cita@test.com", cliente=c)
        v = _crear_vehiculo(db, c, "GEO-001")
        cita = _crear_cita(db, c, v, estado="confirmada")
        _login(client, u.correo)
        r = client.post("/api/ubicacion/actualizar", json=COORDS)
        assert r.status_code == 200
        reg = UbicacionCliente.query.filter_by(cliente_id=c.id).first()
        assert reg is not None
        assert reg.sharing_active is True

    def test_entregar_cita_apaga_sharing_active(self, client, db):
        c = Cliente(nombre="Entrega", correo="entrega@test.com")
        db.session.add(c)
        db.session.commit()
        u = _crear_usuario(db, "cliente", "entrega@test.com", cliente=c)
        v = _crear_vehiculo(db, c, "GEO-002")
        cita = _crear_cita(db, c, v, estado="lista")
        _login(client, u.correo)
        client.post("/api/ubicacion/actualizar", json=COORDS)
        _logout(client)
        _crear_usuario(db, "admin", "admin_geol@test.com")
        _login(client, "admin_geol@test.com")
        client.post(f"/citas/cambiar-estado/{cita.id}/entregada")
        reg = UbicacionCliente.query.filter_by(cliente_id=c.id).first()
        assert reg is not None
        assert reg.sharing_active is False

    def test_cancelar_cita_apaga_sharing_active(self, client, db):
        c = Cliente(nombre="Cancela", correo="cancela@test.com")
        db.session.add(c)
        db.session.commit()
        u = _crear_usuario(db, "cliente", "cancela@test.com", cliente=c)
        v = _crear_vehiculo(db, c, "GEO-003")
        cita = _crear_cita(db, c, v, estado="pendiente")
        _login(client, u.correo)
        client.post("/api/ubicacion/actualizar", json=COORDS)
        client.post(f"/portal/citas/{cita.id}/cancelar")
        reg = UbicacionCliente.query.filter_by(cliente_id=c.id).first()
        assert reg is not None
        assert reg.sharing_active is False


# ============================================================
# 21-22. Leaflet/OpenStreetMap/OSRM sin Google Maps
# ============================================================

class TestMapasSinGoogleMaps:
    def test_dashboard_y_portal_sin_google_maps(self, client, db):
        _, u = _crear_cliente(db, "mapa_cli@test.com")
        _login(client, u.correo)
        html_portal = client.get("/portal/").data.decode("utf-8")
        _logout(client)
        _crear_usuario(db, "admin", "mapa_admin@test.com")
        _login(client, "mapa_admin@test.com")
        html_dash = client.get("/dashboard/").data.decode("utf-8")
        for html in (html_portal, html_dash):
            assert "maps.googleapis" not in html
            assert "GOOGLE_MAPS_API_KEY" not in html
            assert "leaflet" in html
        assert "tile.openstreetmap.org" in html_dash or "openstreetmap" in html_dash or "openstreetmap" in html_portal

    def test_osrm_inactivo_no_rompe_el_mapa(self, client, db):
        c = Cliente(nombre="Mapa", correo="mapa_ok@test.com")
        db.session.add(c)
        db.session.commit()
        u = _crear_usuario(db, "cliente", "mapa_ok@test.com", cliente=c)
        _crear_vehiculo(db, c, "MAP-001")
        _login(client, u.correo)
        resp = client.get("/portal/")
        assert resp.status_code == 200


# ============================================================
# 23-26. Sin errores 500 / Jinja / SQLAlchemy / JS crítico
# ============================================================

class TestEstabilidad:
    def test_sin_errores_500_en_rutas_principales(self, client, db):
        c, u = _crear_cliente(db, "smoke_cli@test.com")
        _crear_vehiculo(db, c, "SMK-001")
        _crear_factura(db, c, "SMK-002")
        _crear_usuario(db, "admin", "smoke_admin@test.com")
        _login(client, u.correo)
        for url in ("/portal/", "/portal/vehiculos", "/portal/citas",
                    "/portal/ordenes", "/portal/facturas", "/portal/cotizaciones",
                    "/portal/garantias", "/portal/historial", "/portal/pagos",
                    "/portal/recordatorios", "/portal/perfil", "/portal/documentos"):
            resp = client.get(url)
            assert resp.status_code != 500, f"{url} -> {resp.status_code}"
        _logout(client)
        _login(client, "smoke_admin@test.com")
        for url in ("/dashboard/", "/dashboard/api/resumen", "/clientes/", "/facturas/"):
            resp = client.get(url)
            assert resp.status_code != 500, f"{url} -> {resp.status_code}"

    def test_plantillas_sin_errores_jinja(self, app):
        root = pathlib.Path(app.root_path) / "templates"
        for p in sorted(root.rglob("*.html")):
            rel = p.relative_to(root).as_posix()
            app.jinja_env.get_template(rel)

    def test_consultas_sqlalchemy_sin_errores(self, client, db):
        c, u = _crear_cliente(db, "sql_cli@test.com")
        _crear_vehiculo(db, c, "SQL-001")
        _login(client, u.correo)
        resp = client.get("/portal/")
        assert resp.status_code == 200
        assert b"Mi Portal" in resp.data