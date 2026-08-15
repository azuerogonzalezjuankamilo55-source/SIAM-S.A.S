"""FASE 4 - Estado "En Pruebas" en órdenes de trabajo + progreso visual."""
from models import Usuario, Cliente, Vehiculo, OrdenTrabajo
from models.orden_trabajo import ESTADOS_OT
from models.orden_trabajo_historial import OrdenTrabajoHistorial


def _crear_staff(db, rol="admin"):
    u = Usuario(nombre=rol, correo=f"{rol}@test.com", rol=rol)
    u.set_password("clave1234")
    db.session.add(u)
    db.session.commit()
    return u


def _login(client, correo):
    return client.post("/auth/login", data={"correo": correo, "password": "clave1234"},
                       follow_redirects=True)


def _crear_ot(db, estado="recibido"):
    c = Cliente(nombre="Cliente OT")
    db.session.add(c)
    db.session.commit()
    v = Vehiculo(placa="OT-1", marca="Mazda", modelo="3", cliente_id=c.id)
    db.session.add(v)
    db.session.commit()
    ot = OrdenTrabajo(numero="OT-TEST-001", cliente_id=c.id, vehiculo_id=v.id, estado=estado)
    db.session.add(ot)
    db.session.commit()
    return c, v, ot


class TestEstados:
    def test_estados_incluye_pruebas(self):
        assert "pruebas" in ESTADOS_OT
        assert ESTADOS_OT.index("en_reparacion") < ESTADOS_OT.index("pruebas") < ESTADOS_OT.index("listo_entrega")

    def test_estado_display(self, app, db):
        with app.app_context():
            c, v, ot = _crear_ot(db, estado="pruebas")
            assert ot.estado_display == "En Pruebas"


class TestFlujoCambioEstado:
    def test_cambiar_a_pruebas(self, client, db):
        _crear_staff(db)
        c, v, ot = _crear_ot(db, estado="en_reparacion")
        _login(client, "admin@test.com")
        resp = client.post(f"/ordenes-trabajo/cambiar-estado/{ot.id}", data={
            "estado": "pruebas",
            "observacion": "Revisión final y prueba de ruta",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert db.session.get(OrdenTrabajo, ot.id).estado == "pruebas"
        hist = OrdenTrabajoHistorial.query.filter_by(orden_trabajo_id=ot.id).first()
        assert hist is not None
        assert hist.estado_nuevo == "pruebas"
        assert hist.estado_anterior == "en_reparacion"

    def test_pruebas_a_listo_entrega(self, client, db):
        _crear_staff(db)
        c, v, ot = _crear_ot(db, estado="pruebas")
        _login(client, "admin@test.com")
        client.post(f"/ordenes-trabajo/cambiar-estado/{ot.id}", data={"estado": "listo_entrega"})
        assert db.session.get(OrdenTrabajo, ot.id).estado == "listo_entrega"

    def test_estado_invalido_rechazado(self, client, db):
        _crear_staff(db)
        c, v, ot = _crear_ot(db)
        _login(client, "admin@test.com")
        resp = client.post(f"/ordenes-trabajo/cambiar-estado/{ot.id}", data={"estado": "basura"},
                           follow_redirects=True)
        assert resp.status_code == 200
        assert db.session.get(OrdenTrabajo, ot.id).estado == "recibido"


class TestDashboard:
    def test_ot_en_pruebas_cuenta_como_activa(self, app, db):
        from services.dashboard_service import DashboardService
        with app.app_context():
            _crear_staff(db)
            c, v, ot = _crear_ot(db, estado="pruebas")
            data = DashboardService.get_data()
            assert data.ordenes_activas >= 1

    def test_ot_pruebas_visible_en_portal(self, client, db):
        c, v, ot = _crear_ot(db, estado="pruebas")
        u = Usuario(nombre="Cli", correo="pc@test.com", rol="cliente", cliente_id=c.id)
        u.set_password("clave1234")
        db.session.add(u)
        db.session.commit()
        _login(client, "pc@test.com")
        resp = client.get("/portal/")
        assert resp.status_code == 200
        assert b"En Pruebas" in resp.data
        resp2 = client.get(f"/portal/ordenes/{ot.id}")
        assert resp2.status_code == 200
        assert b"En Pruebas" in resp2.data
