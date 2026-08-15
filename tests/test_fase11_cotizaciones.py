"""FASE 11 - Cotizaciones: presupuesto, items, aprobación del cliente y conversión a OT."""
from decimal import Decimal

import pytest

from models import Usuario, Cliente, Vehiculo, Servicio, Notificacion
from services.cotizacion_service import CotizacionService, CotizacionError


def _crear_cliente(db, correo="cli_cot@test.com"):
    c = Cliente(nombre="Cliente Cotización", correo=correo, telefono="3000000002")
    db.session.add(c)
    db.session.commit()
    u = Usuario(nombre="Cliente Cotización", correo=correo, rol="cliente", cliente_id=c.id)
    u.set_password("clave1234")
    db.session.add(u)
    db.session.commit()
    return c, u


def _crear_staff(db, correo="admin_cot@test.com", rol="admin"):
    u = Usuario(nombre=rol, correo=correo, rol=rol)
    u.set_password("clave1234")
    db.session.add(u)
    db.session.commit()
    return u


def _crear_vehiculo(db, cliente, placa="COT1"):
    v = Vehiculo(placa=placa, marca="Mazda", modelo="3", cliente_id=cliente.id)
    db.session.add(v)
    db.session.commit()
    return v


def _crear_servicio(db, nombre="Cambio de aceite", precio=100000):
    s = Servicio(nombre=nombre, precio_estimado=precio, activo=True)
    db.session.add(s)
    db.session.commit()
    return s


def _login(client, correo, password="clave1234"):
    return client.post("/auth/login", data={"correo": correo, "password": password},
                       follow_redirects=True)


class TestCotizacionService:
    def test_crear_genera_numero_secuencial(self, app, db):
        with app.app_context():
            c, u = _crear_cliente(db, correo="num1@test.com")
            v = _crear_vehiculo(db, c, "NUM1")
            c1 = CotizacionService.crear(c.id, v.id)
            c2 = CotizacionService.crear(c.id, v.id)
            assert c1.numero == "COT-000001"
            assert c2.numero == "COT-000002"
            assert c1.estado == "pendiente"
            assert c1.total == Decimal("0.00")

    def test_agregar_item_calcula_totales(self, app, db):
        with app.app_context():
            c, u = _crear_cliente(db, correo="tot@test.com")
            v = _crear_vehiculo(db, c, "TOT1")
            s = _crear_servicio(db, precio=100000)
            cot = CotizacionService.crear(c.id, v.id)
            CotizacionService.agregar_item(cot.id, s.id, cantidad=2)
            assert cot.subtotal == Decimal("200000.00")
            assert cot.iva == Decimal("38000.00")
            assert cot.total == Decimal("238000.00")

    def test_agregar_item_libre(self, app, db):
        with app.app_context():
            c, u = _crear_cliente(db, correo="libre@test.com")
            v = _crear_vehiculo(db, c, "LIB1")
            cot = CotizacionService.crear(c.id, v.id)
            CotizacionService.agregar_item_libre(cot.id, "Mano de obra", 3, Decimal("50000"))
            assert cot.total == Decimal("178500.00")

    def test_cambiar_estado_rechaza_estado_invalido(self, app, db):
        with app.app_context():
            c, u = _crear_cliente(db, correo="inv@test.com")
            v = _crear_vehiculo(db, c, "INV1")
            cot = CotizacionService.crear(c.id, v.id)
            with pytest.raises(CotizacionError):
                CotizacionService.cambiar_estado(cot.id, "fantasma")

    def test_convertir_requiere_aprobada(self, app, db):
        with app.app_context():
            c, u = _crear_cliente(db, correo="conv@test.com")
            v = _crear_vehiculo(db, c, "CV1")
            s = _crear_servicio(db, precio=80000)
            cot = CotizacionService.crear(c.id, v.id)
            CotizacionService.agregar_item(cot.id, s.id)
            with pytest.raises(CotizacionError):
                CotizacionService.convertir_a_ot(cot.id)

    def test_convertir_a_ot_tras_aprobacion(self, app, db):
        with app.app_context():
            c, u = _crear_cliente(db, correo="conv2@test.com")
            v = _crear_vehiculo(db, c, "CV2")
            s = _crear_servicio(db, precio=80000)
            cot = CotizacionService.crear(c.id, v.id)
            CotizacionService.agregar_item(cot.id, s.id)
            CotizacionService.cambiar_estado(cot.id, "aprobada")
            ot = CotizacionService.convertir_a_ot(cot.id)
            assert ot.numero.startswith("OT-")
            assert ot.cliente_id == c.id
            assert ot.vehiculo_id == v.id
            assert len(ot.items) == 1
            assert cot.estado == "convertida"
            assert cot.orden_trabajo_id == ot.id


class TestPaginasCotizacionesStaff:
    def test_crear_y_ver(self, client, db):
        _crear_staff(db)
        c = Cliente(nombre="Cli", correo="s@test.com")
        db.session.add(c)
        db.session.commit()
        v = _crear_vehiculo(db, c, "S01")
        _login(client, "admin_cot@test.com")
        resp = client.post("/cotizaciones/crear", data={
            "cliente_id": c.id,
            "vehiculo_id": v.id,
            "sede_id": 0,
            "validez_dias": 15,
            "descripcion": "Frenos y suspensión",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b"COT-000001" in resp.data

    def test_listar(self, client, db):
        _crear_staff(db)
        _login(client, "admin_cot@test.com")
        resp = client.get("/cotizaciones/")
        assert resp.status_code == 200
        assert b"Cotizaciones" in resp.data

    def test_agregar_item_desde_servicio(self, client, db):
        _crear_staff(db)
        c = Cliente(nombre="Cli", correo="it@test.com")
        db.session.add(c)
        db.session.commit()
        v = _crear_vehiculo(db, c, "IT1")
        s = _crear_servicio(db, precio=100000)
        cot = CotizacionService.crear(c.id, v.id)
        _login(client, "admin_cot@test.com")
        resp = client.post(f"/cotizaciones/items/agregar/{cot.id}", data={
            "servicio_id": s.id, "cantidad": 1,
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert len(cot.items) == 1
        assert cot.total == Decimal("119000.00")

    def test_enviar_notifica_al_cliente(self, client, db):
        _crear_staff(db)
        c, u = _crear_cliente(db, correo="env@test.com")
        v = _crear_vehiculo(db, c, "ENV1")
        s = _crear_servicio(db, precio=100000)
        cot = CotizacionService.crear(c.id, v.id)
        CotizacionService.agregar_item(cot.id, s.id)
        _login(client, "admin_cot@test.com")
        resp = client.post(f"/cotizaciones/enviar/{cot.id}", follow_redirects=True)
        assert resp.status_code == 200
        notif = Notificacion.query.filter_by(usuario_id=u.id).first()
        assert notif is not None
        assert "cotizaci" in (notif.titulo or "").lower() or "cotizaci" in (notif.mensaje or "").lower()

    def test_eliminar_item(self, client, db):
        _crear_staff(db)
        c = Cliente(nombre="Cli", correo="el@test.com")
        db.session.add(c)
        db.session.commit()
        v = _crear_vehiculo(db, c, "EL1")
        s = _crear_servicio(db, precio=100000)
        cot = CotizacionService.crear(c.id, v.id)
        item = CotizacionService.agregar_item(cot.id, s.id)
        _login(client, "admin_cot@test.com")
        client.post(f"/cotizaciones/items/eliminar/{item.id}", follow_redirects=True)
        assert len(cot.items) == 0
        assert cot.total == Decimal("0.00")

    def test_staff_sin_permiso_redirige(self, client, db):
        _crear_staff(db, correo="cli_role@test.com", rol="cliente")
        _login(client, "cli_role@test.com")
        resp = client.get("/cotizaciones/", follow_redirects=True)
        assert resp.status_code == 200
        assert b"Mi Portal" in resp.data or b"SIAM" in resp.data


class TestFlujoClienteCotizacion:
    def test_cliente_ve_sus_cotizaciones(self, client, db):
        c, u = _crear_cliente(db, correo="vis@test.com")
        v = _crear_vehiculo(db, c, "VIS1")
        s = _crear_servicio(db, precio=100000)
        cot = CotizacionService.crear(c.id, v.id)
        CotizacionService.agregar_item(cot.id, s.id)
        _login(client, u.correo)
        resp = client.get("/portal/cotizaciones")
        assert resp.status_code == 200
        assert cot.numero.encode() in resp.data

    def test_cliente_aprueba_cotizacion(self, client, db):
        c, u = _crear_cliente(db, correo="apr@test.com")
        v = _crear_vehiculo(db, c, "APR1")
        s = _crear_servicio(db, precio=100000)
        cot = CotizacionService.crear(c.id, v.id)
        CotizacionService.agregar_item(cot.id, s.id)
        _login(client, u.correo)
        resp = client.post(
            f"/portal/cotizaciones/{cot.id}/responder/aprobada", follow_redirects=True
        )
        assert resp.status_code == 200
        assert cot.estado == "aprobada"

    def test_cliente_rechaza_cotizacion(self, client, db):
        c, u = _crear_cliente(db, correo="rech@test.com")
        v = _crear_vehiculo(db, c, "RCH1")
        cot = CotizacionService.crear(c.id, v.id)
        _login(client, u.correo)
        resp = client.post(
            f"/portal/cotizaciones/{cot.id}/responder/rechazada", follow_redirects=True
        )
        assert resp.status_code == 200
        assert cot.estado == "rechazada"

    def test_cliente_no_responde_cotizacion_ajena(self, client, db):
        c1, u1 = _crear_cliente(db, correo="aj1@test.com")
        _, u2 = _crear_cliente(db, correo="aj2@test.com")
        v = _crear_vehiculo(db, c1, "AJ1")
        cot = CotizacionService.crear(c1.id, v.id)
        _login(client, u2.correo)
        resp = client.get(f"/portal/cotizaciones/{cot.id}", follow_redirects=True)
        assert cot.estado == "pendiente"
        assert resp.status_code == 200

    def test_convertir_desde_staff(self, client, db):
        _crear_staff(db)
        c, u = _crear_cliente(db, correo="cvs@test.com")
        v = _crear_vehiculo(db, c, "CVS1")
        s = _crear_servicio(db, precio=90000)
        cot = CotizacionService.crear(c.id, v.id)
        CotizacionService.agregar_item(cot.id, s.id)
        CotizacionService.cambiar_estado(cot.id, "aprobada")
        _login(client, "admin_cot@test.com")
        resp = client.post(f"/cotizaciones/convertir-ot/{cot.id}", follow_redirects=True)
        assert resp.status_code == 200
        assert cot.estado == "convertida"
        assert cot.orden_trabajo_id is not None
        from models import OrdenTrabajo
        ot = db.session.get(OrdenTrabajo, cot.orden_trabajo_id)
        assert ot is not None and len(ot.items) == 1
