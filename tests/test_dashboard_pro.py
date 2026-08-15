import pytest
from datetime import date, time, timedelta
from decimal import Decimal

from models import (Usuario, Cliente, Vehiculo, Servicio, Cita, Mecanico,
                    OrdenTrabajo, Factura)
from services.factura_service import FacturaService, FacturaInput
from services.dashboard_service import DashboardService


def _crear_admin(db):
    u = Usuario(nombre="Admin", correo="admin_dash@test.com", rol="admin")
    u.set_password("admin123")
    db.session.add(u)
    db.session.commit()
    return u


def _crear_base(db):
    c = Cliente(nombre="Cliente Dash", correo="dash@test.com")
    db.session.add(c)
    db.session.commit()
    v = Vehiculo(cliente_id=c.id, marca="Toyota", modelo="Corolla", placa="DASH-1")
    db.session.add(v)
    db.session.commit()
    return c, v


def _crear_factura(db, c, v, estado, pago=False):
    cita = Cita(cliente_id=c.id, vehiculo_id=v.id, fecha=date.today(), hora=time(10, 0))
    db.session.add(cita)
    db.session.commit()
    s = Servicio(nombre="Cambio de aceite", precio_estimado=100000)
    db.session.add(s)
    db.session.commit()
    factura = FacturaService.generar(FacturaInput(
        cita_id=cita.id, servicio_ids=[s.id], precios=[100000],
        cantidades=[1], descuento=Decimal("0"), metodo_pago="Efectivo",
    ))
    if pago:
        FacturaService.registrar_pago(
            factura_id=factura.id, monto=Decimal("119000"),
            metodo_pago="Efectivo", usuario_id=1,
        )
    return factura


def _login(client):
    return client.post("/auth/login", data={"correo": "admin_dash@test.com", "password": "admin123"},
                       follow_redirects=True)


class TestDashboardService:
    def test_metricas_vacias(self, db):
        data = DashboardService.get_data()
        assert data.por_cobrar == 0.0
        assert data.ticket_promedio == 0.0
        assert data.ot_retrasadas_count == 0
        assert data.tasa_completacion_citas == 0.0

    def test_por_cobrar_y_ticket(self, db):
        c, v = _crear_base(db)
        _crear_factura(db, c, v, "pendiente")
        _crear_factura(db, c, v, "pagado", pago=True)
        data = DashboardService.get_data()
        assert data.por_cobrar == 119000.0
        assert data.ticket_promedio == 119000.0

    def test_ot_retrasadas(self, db):
        c, v = _crear_base(db)
        ot = OrdenTrabajo(numero="OT-DASH-1", cliente_id=c.id, vehiculo_id=v.id,
                          fecha_estimada_entrega=date.today() - timedelta(days=3),
                          estado="en_reparacion")
        db.session.add(ot)
        db.session.commit()
        data = DashboardService.get_data()
        assert data.ot_retrasadas_count == 1
        assert len(data.ot_retrasadas) == 1

    def test_tasa_completacion(self, db):
        c, v = _crear_base(db)
        for _ in range(3):
            cita = Cita(cliente_id=c.id, vehiculo_id=v.id,
                        fecha=date.today(), hora=time(9, 0), estado="completado")
            db.session.add(cita)
        db.session.commit()
        data = DashboardService.get_data()
        assert data.tasa_completacion_citas == 100.0

    def test_ingresos_por_metodo(self, db):
        c, v = _crear_base(db)
        _crear_factura(db, c, v, "pagado", pago=True)
        data = DashboardService.get_data()
        metodos = {m for m, _ in data.ingresos_por_metodo}
        assert "Efectivo" in metodos

    def test_ot_por_mecanico(self, db):
        c, v = _crear_base(db)
        m = Mecanico(nombre="Juan", especialidad="Motor", activo=True)
        db.session.add(m)
        db.session.commit()
        ot = OrdenTrabajo(numero="OT-DASH-2", cliente_id=c.id, vehiculo_id=v.id,
                          mecanico_id=m.id, estado="entregado")
        db.session.add(ot)
        db.session.commit()
        data = DashboardService.get_data()
        assert ("Juan", 1) in data.ot_por_mecanico


class TestDashboardRoutes:
    def test_dashboard_index(self, client, db):
        _crear_admin(db)
        _login(client)
        resp = client.get("/dashboard/")
        assert resp.status_code == 200
        assert b"Por Cobrar" in resp.data

    def test_api_resumen(self, client, db):
        _crear_admin(db)
        _login(client)
        resp = client.get("/dashboard/api/resumen")
        assert resp.status_code == 200
        assert "por_cobrar" in resp.json
        assert "ticket_promedio" in resp.json
        assert "ot_retrasadas_count" in resp.json
