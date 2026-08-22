import pytest
from datetime import date, time, timedelta
from decimal import Decimal

from models import Usuario, Cliente, Vehiculo, Servicio, Cita, Mecanico, Recordatorio
from services.factura_service import FacturaService, FacturaInput


def _crear_admin(db):
    u = Usuario(nombre="Admin", correo="admin@test.com", rol="admin")
    u.set_password("admin123")
    db.session.add(u)
    db.session.commit()
    return u


def _crear_cliente(db, correo="cliente@test.com"):
    c = Cliente(nombre="Cliente Test", correo=correo, telefono="3001234567")
    db.session.add(c)
    db.session.commit()
    u = Usuario(nombre="Cliente Test", correo=correo, rol="cliente", cliente_id=c.id)
    u.set_password("clave1234")
    db.session.add(u)
    db.session.commit()
    return c, u


def _login(client, correo, password):
    return client.post("/auth/login", data={"correo": correo, "password": password},
                       follow_redirects=True)


class TestPortalAuth:
    def test_registro_crea_cliente(self, client, db):
        resp = client.post("/auth/register", data={
            "nombre": "Nuevo Cliente",
            "correo": "nuevo_cliente@test.com",
            "documento": "1090123456",
            "telefono": "3001234567",
            "password": "pass1234",
            "confirmar_password": "pass1234",
        }, follow_redirects=True)
        assert resp.status_code == 200
        u = Usuario.query.filter_by(correo="nuevo_cliente@test.com").first()
        assert u is not None
        assert u.rol == "cliente"
        assert u.cliente_id is not None

    def test_login_cliente_redirige_portal(self, client, db):
        _, u = _crear_cliente(db)
        resp = _login(client, u.correo, "clave1234")
        assert b"Mi Portal" in resp.data or b"Hola" in resp.data

    def test_login_admin_redirige_dashboard(self, client, db):
        _crear_admin(db)
        resp = _login(client, "admin@test.com", "admin123")
        assert b"Dashboard" in resp.data


class TestPortalDashboard:
    def test_portal_requiere_login(self, client):
        resp = client.get("/portal/", follow_redirects=True)
        assert resp.status_code == 200

    def test_portal_index(self, client, db):
        c, u = _crear_cliente(db)
        _login(client, u.correo, "clave1234")
        resp = client.get("/portal/")
        assert resp.status_code == 200
        assert "Hola" in resp.data.decode()

    def test_portal_vehiculos(self, client, db):
        c, u = _crear_cliente(db)
        v = Vehiculo(cliente_id=c.id, marca="Toyota", modelo="Corolla", placa="ABC-123")
        db.session.add(v)
        db.session.commit()
        _login(client, u.correo, "clave1234")
        resp = client.get("/portal/vehiculos")
        assert resp.status_code == 200
        assert b"ABC-123" in resp.data

    def test_portal_vehiculo_detalle(self, client, db):
        c, u = _crear_cliente(db)
        v = Vehiculo(cliente_id=c.id, marca="Toyota", modelo="Corolla", placa="ABC-123")
        db.session.add(v)
        db.session.commit()
        _login(client, u.correo, "clave1234")
        resp = client.get(f"/portal/vehiculos/{v.id}")
        assert resp.status_code == 200

    def test_portal_no_accede_vehiculo_ajeno(self, client, db):
        c, u = _crear_cliente(db)
        otro = Cliente(nombre="Otro", correo="otro@test.com")
        db.session.add(otro)
        db.session.commit()
        v = Vehiculo(cliente_id=otro.id, marca="Mazda", modelo="3", placa="ZZZ-999")
        db.session.add(v)
        db.session.commit()
        _login(client, u.correo, "clave1234")
        resp = client.get(f"/portal/vehiculos/{v.id}")
        assert resp.status_code == 302


class TestPortalCitas:
    def test_solicitar_cita(self, client, db):
        c, u = _crear_cliente(db)
        v = Vehiculo(cliente_id=c.id, marca="Toyota", modelo="Corolla", placa="ABC-123")
        db.session.add(v)
        db.session.commit()
        _login(client, u.correo, "clave1234")
        resp = client.get("/portal/citas/solicitar")
        assert resp.status_code == 200
        resp = client.post("/portal/citas/solicitar", data={
            "vehiculo_id": v.id,
            "sede_id": 1,
            "fecha": "2026-09-01",
            "hora": "10:00",
            "descripcion": "Ruido en motor",
        }, follow_redirects=True)
        assert resp.status_code == 200
        cita = Cita.query.filter_by(cliente_id=c.id).first()
        assert cita is not None
        assert cita.estado == "pendiente"

    def test_cancelar_cita(self, client, db):
        c, u = _crear_cliente(db)
        v = Vehiculo(cliente_id=c.id, marca="T", modelo="C", placa="X-1")
        db.session.add(v)
        db.session.commit()
        cita = Cita(cliente_id=c.id, vehiculo_id=v.id, fecha=date.today(), hora=time(10, 0), estado="pendiente")
        db.session.add(cita)
        db.session.commit()
        _login(client, u.correo, "clave1234")
        resp = client.post(f"/portal/citas/{cita.id}/cancelar", data={"csrf_token": "x"},
                           follow_redirects=True)
        assert resp.status_code == 200
        assert db.session.get(Cita, cita.id).estado == "cancelado"


class TestPortalFacturas:
    def test_facturas_visibles(self, client, db):
        c, u = _crear_cliente(db)
        v = Vehiculo(cliente_id=c.id, marca="T", modelo="C", placa="X-2")
        db.session.add(v)
        db.session.commit()
        cita = Cita(cliente_id=c.id, vehiculo_id=v.id, fecha=date.today(), hora=time(10, 0))
        db.session.add(cita)
        db.session.commit()
        s = Servicio(nombre="Aceite", precio_estimado=50000)
        db.session.add(s)
        db.session.commit()
        FacturaService.generar(FacturaInput(
            cita_id=cita.id, servicio_ids=[s.id], precios=[50000],
            cantidades=[1], descuento=Decimal("0"), metodo_pago="Efectivo",
        ))
        _login(client, u.correo, "clave1234")
        resp = client.get("/portal/facturas")
        assert resp.status_code == 200

    def test_no_accede_factura_ajena(self, client, db):
        c, u = _crear_cliente(db)
        otro = Cliente(nombre="Otro", correo="otro2@test.com")
        db.session.add(otro)
        db.session.commit()
        v = Vehiculo(cliente_id=otro.id, marca="T", modelo="C", placa="Y-1")
        db.session.add(v)
        db.session.commit()
        cita = Cita(cliente_id=otro.id, vehiculo_id=v.id, fecha=date.today(), hora=time(10, 0))
        db.session.add(cita)
        db.session.commit()
        s = Servicio(nombre="Aceite")
        db.session.add(s)
        db.session.commit()
        factura = FacturaService.generar(FacturaInput(
            cita_id=cita.id, servicio_ids=[s.id], precios=[50000],
            cantidades=[1], descuento=Decimal("0"), metodo_pago="Efectivo",
        ))
        _login(client, u.correo, "clave1234")
        resp = client.get(f"/portal/facturas/{factura.id}")
        assert resp.status_code == 302


class TestPortalFase7:
    def test_portal_muestra_recordatorios(self, client, db):
        c, u = _crear_cliente(db)
        v = Vehiculo(cliente_id=c.id, marca="Toyota", modelo="Corolla", placa="ABC-123")
        db.session.add(v)
        db.session.commit()
        r = Recordatorio(
            vehiculo_id=v.id, tipo="mantenimiento", servicio_mantenimiento="aceite",
            titulo="Cambio de aceite", fecha_programada=date.today() + timedelta(days=7),
            estado="pendiente",
        )
        db.session.add(r)
        db.session.commit()
        _login(client, u.correo, "clave1234")
        resp = client.get("/portal/")
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        assert "Mantenimientos próximos" in html
        assert "Cambio de aceite" in html

    def test_portal_muestra_boton_asistencia(self, client, db):
        c, u = _crear_cliente(db)
        _login(client, u.correo, "clave1234")
        resp = client.get("/portal/")
        assert b"Asistencia / Sedes" in resp.data

    def test_portal_sin_recordatorios(self, client, db):
        c, u = _crear_cliente(db)
        _login(client, u.correo, "clave1234")
        resp = client.get("/portal/")
        assert b"Sin mantenimientos programados" in resp.data

    def test_admin_no_accede_al_portal(self, client, db):
        _crear_admin(db)
        _login(client, "admin@test.com", "admin123")
        resp = client.get("/portal/", follow_redirects=False)
        assert resp.status_code == 302
        assert "dashboard" in resp.headers.get("Location", "")


class TestPortalPerfil:
    def test_perfil_update(self, client, db):
        c, u = _crear_cliente(db)
        _login(client, u.correo, "clave1234")
        resp = client.post("/portal/perfil", data={
            "nombre": "Cliente Actualizado",
            "telefono": "3119998888",
            "direccion": "Calle 1 # 2-3",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert db.session.get(Cliente, c.id).nombre == "Cliente Actualizado"

    def test_cambiar_password(self, client, db):
        c, u = _crear_cliente(db)
        _login(client, u.correo, "clave1234")
        resp = client.post("/portal/perfil/password", data={
            "password_actual": "clave1234",
            "nueva_password": "nuevaclav3",
            "confirmar": "nuevaclav3",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert u.check_password("nuevaclav3")
