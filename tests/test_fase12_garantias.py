"""FASE 12 - Garantías: registro, generación desde OT/servicio y reclamaciones."""
from datetime import date, timedelta

import pytest

from models import Usuario, Cliente, Vehiculo, Servicio, OrdenTrabajo, Garantia
from services.garantia_service import GarantiaService, GarantiaError


def _crear_cliente(db, correo="cli_gar@test.com"):
    c = Cliente(nombre="Cliente Garantía", correo=correo, telefono="3000000003")
    db.session.add(c)
    db.session.commit()
    u = Usuario(nombre="Cliente Garantía", correo=correo, rol="cliente", cliente_id=c.id)
    u.set_password("clave1234")
    db.session.add(u)
    db.session.commit()
    return c, u


def _crear_staff(db, correo="admin_gar@test.com", rol="admin"):
    u = Usuario(nombre=rol, correo=correo, rol=rol)
    u.set_password("clave1234")
    db.session.add(u)
    db.session.commit()
    return u


def _crear_vehiculo(db, cliente, placa="GAR1"):
    v = Vehiculo(placa=placa, marca="Chevrolet", modelo="Spark", cliente_id=cliente.id)
    db.session.add(v)
    db.session.commit()
    return v


def _crear_ot(db, cliente, vehiculo, estado="entregado"):
    ot = OrdenTrabajo(
        numero=f"OT-G{cliente.id:04d}",
        cliente_id=cliente.id,
        vehiculo_id=vehiculo.id,
        diagnostico_inicial="Reparación",
        estado=estado,
    )
    db.session.add(ot)
    db.session.commit()
    return ot


def _login(client, correo, password="clave1234"):
    return client.post("/auth/login", data={"correo": correo, "password": password},
                       follow_redirects=True)


class TestGarantiaService:
    def test_crear_genera_codigo(self, app, db):
        with app.app_context():
            c, u = _crear_cliente(db, correo="cod@test.com")
            v = _crear_vehiculo(db, c, "GCOD")
            g1 = GarantiaService.crear(c.id, v.id, "Cubierta", 6)
            g2 = GarantiaService.crear(c.id, v.id, "Cubierta", 6)
            assert g1.codigo == "GAR-000001"
            assert g2.codigo == "GAR-000002"
            assert g1.estado == "activa"
            assert g1.fecha_fin >= date.today()

    def test_crear_para_ot_requiere_entregada(self, app, db):
        with app.app_context():
            c, u = _crear_cliente(db, correo="rec@test.com")
            v = _crear_vehiculo(db, c, "GREC")
            ot = _crear_ot(db, c, v, estado="recibido")
            with pytest.raises(GarantiaError):
                GarantiaService.crear_para_ot(ot.id)

    def test_crear_para_ot(self, app, db):
        with app.app_context():
            c, u = _crear_cliente(db, correo="otg@test.com")
            v = _crear_vehiculo(db, c, "GOT")
            ot = _crear_ot(db, c, v, estado="entregado")
            g = GarantiaService.crear_para_ot(ot.id, 3)
            assert g.orden_trabajo_id == ot.id
            assert g.cliente_id == c.id
            assert "GAR-" in g.codigo

    def test_no_duplica_garantia_de_ot(self, app, db):
        with app.app_context():
            c, u = _crear_cliente(db, correo="dup@test.com")
            v = _crear_vehiculo(db, c, "GDUP")
            ot = _crear_ot(db, c, v, estado="entregado")
            GarantiaService.crear_para_ot(ot.id, 3)
            with pytest.raises(GarantiaError):
                GarantiaService.crear_para_ot(ot.id, 3)

    def test_desde_servicio_con_garantia(self, app, db):
        with app.app_context():
            c, u = _crear_cliente(db, correo="svc@test.com")
            v = _crear_vehiculo(db, c, "GSVC")
            ot = _crear_ot(db, c, v, estado="entregado")
            s = Servicio(nombre="Pintura", precio_estimado=300000, garantia_meses=12)
            db.session.add(s)
            db.session.commit()
            g = GarantiaService.crear_desde_servicio(ot.id, s.id)
            assert g is not None
            assert g.servicio_id == s.id
            assert g.meses_validez == 12

    def test_desde_servicio_sin_garantia_devuelve_none(self, app, db):
        with app.app_context():
            c, u = _crear_cliente(db, correo="nosvc@test.com")
            v = _crear_vehiculo(db, c, "GNOS")
            ot = _crear_ot(db, c, v, estado="entregado")
            s = Servicio(nombre="Lavado", precio_estimado=20000)
            db.session.add(s)
            db.session.commit()
            assert GarantiaService.crear_desde_servicio(ot.id, s.id) is None

    def test_cambiar_estado_con_nota(self, app, db):
        with app.app_context():
            c, u = _crear_cliente(db, correo="nota@test.com")
            v = _crear_vehiculo(db, c, "GNOT")
            g = GarantiaService.crear(c.id, v.id, "Cubierta", 3)
            g = GarantiaService.cambiar_estado(g.id, "reclamada", nota="Se despinta")
            assert g.estado == "reclamada"
            assert g.nota_reclamacion == "Se despinta"

    def test_actualizar_estados_vencidas(self, app, db):
        with app.app_context():
            c, u = _crear_cliente(db, correo="ven@test.com")
            v = _crear_vehiculo(db, c, "GVEN")
            g = GarantiaService.crear(c.id, v.id, "Cubierta", 3)
            g.fecha_fin = date.today() - timedelta(days=1)
            db.session.commit()
            count = GarantiaService.actualizar_estados_vencidas()
            assert count == 1
            assert g.estado == "caducada"


class TestPaginasGarantiasStaff:
    def test_listar_y_crear(self, client, db):
        _crear_staff(db)
        c = Cliente(nombre="Cli", correo="gs@test.com")
        db.session.add(c)
        db.session.commit()
        v = _crear_vehiculo(db, c, "GSP")
        _login(client, "admin_gar@test.com")
        resp = client.get("/garantias/")
        assert resp.status_code == 200
        assert b"Garant" in resp.data
        resp = client.post("/garantias/crear", data={
            "cliente_id": c.id,
            "vehiculo_id": v.id,
            "servicio_id": 0,
            "meses_validez": 3,
            "descripcion": "Garantía de frenos",
        }, follow_redirects=True)
        assert resp.status_code == 200
        g = Garantia.query.first()
        assert g is not None
        assert g.codigo == "GAR-000001"

    def test_reclamar_desde_ver(self, client, db):
        _crear_staff(db)
        c = Cliente(nombre="Cli", correo="grc@test.com")
        db.session.add(c)
        db.session.commit()
        v = _crear_vehiculo(db, c, "GRCV")
        g = GarantiaService.crear(c.id, v.id, "Cubierta", 3)
        _login(client, "admin_gar@test.com")
        resp = client.post(f"/garantias/cambiar-estado/{g.id}/reclamada",
                           data={"nota": "Falla recurrente"}, follow_redirects=True)
        assert resp.status_code == 200
        assert g.estado == "reclamada"
        assert g.nota_reclamacion == "Falla recurrente"


class TestPortalGarantias:
    def test_cliente_ve_sus_garantias(self, client, db):
        c, u = _crear_cliente(db, correo="vis@test.com")
        v = _crear_vehiculo(db, c, "GVIS")
        g = GarantiaService.crear(c.id, v.id, "Cubierta", 3)
        _login(client, u.correo)
        resp = client.get("/portal/garantias")
        assert resp.status_code == 200
        assert g.codigo.encode() in resp.data

    def test_cliente_no_ve_garantias_ajenas(self, client, db):
        c1, u1 = _crear_cliente(db, correo="ga1@test.com")
        _, u2 = _crear_cliente(db, correo="ga2@test.com")
        v = _crear_vehiculo(db, c1, "GAJ1")
        g = GarantiaService.crear(c1.id, v.id, "Cubierta", 3)
        _login(client, u2.correo)
        resp = client.get("/portal/garantias")
        assert resp.status_code == 200
        assert g.codigo.encode() not in resp.data
