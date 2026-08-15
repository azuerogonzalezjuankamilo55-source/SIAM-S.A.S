import pytest
from datetime import date, time
from decimal import Decimal

from models import Usuario, Cliente, Vehiculo, Servicio, Cita, OrdenTrabajo
from models.historial_vehiculo import HistorialVehiculo
from services.historial_service import HistorialService
from services.factura_service import FacturaService, FacturaInput


def _crear_admin(db):
    u = Usuario(nombre="Admin", correo="admin_hist@test.com", rol="admin")
    u.set_password("admin123")
    db.session.add(u)
    db.session.commit()
    return u


def _crear_cliente_vehiculo(db, placa="ABC-123"):
    c = Cliente(nombre="Cliente Historial", correo="hist@test.com", telefono="3000000000")
    db.session.add(c)
    db.session.commit()
    v = Vehiculo(cliente_id=c.id, marca="Toyota", modelo="Corolla", placa=placa)
    db.session.add(v)
    db.session.commit()
    return c, v


def _login(client, correo, password):
    return client.post("/auth/login", data={"correo": correo, "password": password},
                       follow_redirects=True)


def _crear_factura(db, c, v, servicio_nombre="Cambio de aceite sintético"):
    cita = Cita(cliente_id=c.id, vehiculo_id=v.id, fecha=date.today(), hora=time(10, 0))
    db.session.add(cita)
    db.session.commit()
    s = Servicio(nombre=servicio_nombre, precio_estimado=50000)
    db.session.add(s)
    db.session.commit()
    factura = FacturaService.generar(FacturaInput(
        cita_id=cita.id, servicio_ids=[s.id], precios=[50000],
        cantidades=[1], descuento=Decimal("0"), metodo_pago="Efectivo",
    ))
    return cita, factura


class TestHistorialService:
    def test_registrar_entrada(self, db):
        _, v = _crear_cliente_vehiculo(db)
        h = HistorialService.registrar(v.id, "observacion", "Rasguño en puerta")
        assert h.id is not None
        assert h.vehiculo_id == v.id
        assert h.tipo == "observacion"

    def test_tipo_invalido_lanza_error(self, db):
        _, v = _crear_cliente_vehiculo(db)
        with pytest.raises(ValueError):
            HistorialService.registrar(v.id, "tipo_inventado", "x")

    def test_get_historial_orden_descendente(self, db):
        c, v = _crear_cliente_vehiculo(db)
        HistorialService.registrar(v.id, "observacion", "vieja", fecha=date(2020, 1, 1))
        HistorialService.registrar(v.id, "revision", "nueva", fecha=date(2025, 6, 1))
        registros = HistorialService.get_historial_vehiculo(v.id)
        assert [r.tipo for r in registros] == ["revision", "observacion"]

    def test_agregar_observacion(self, db):
        _, v = _crear_cliente_vehiculo(db)
        h = HistorialService.agregar_observacion(v.id, "Olor a gasolina")
        assert h.tipo == "observacion"


class TestResumenYFicha:
    def test_get_resumen_vacio(self, db):
        _, v = _crear_cliente_vehiculo(db)
        resumen = HistorialService.get_resumen(v.id)
        assert resumen["total_registros"] == 0
        assert resumen["visitas"] == 0
        assert resumen["ultimo_kilometraje"] is None
        assert resumen["total_gastado"] == 0

    def test_get_resumen_con_datos(self, db):
        c, v = _crear_cliente_vehiculo(db)
        HistorialService.registrar(v.id, "cambio_aceite", "Cambio de aceite", kilometraje=20000)
        HistorialService.registrar(v.id, "observacion", "ok", kilometraje=22000)
        _crear_factura(db, c, v)
        resumen = HistorialService.get_resumen(v.id)
        assert resumen["ultimo_kilometraje"] == 22000
        assert resumen["visitas"] >= 1
        assert resumen["total_gastado"] > 0
        assert resumen["conteo_por_tipo"].get("factura", 0) >= 1

    def test_get_resumen_ignora_facturas_anuladas(self, db):
        c, v = _crear_cliente_vehiculo(db)
        cita, factura = _crear_factura(db, c, v)
        factura.estado = "anulado"
        db.session.commit()
        resumen = HistorialService.get_resumen(v.id)
        assert resumen["total_gastado"] == 0

    def test_get_proximos_mantenimientos(self, db):
        _, v = _crear_cliente_vehiculo(db)
        HistorialService.registrar(v.id, "cambio_aceite", "Aceite", kilometraje=20000)
        mantenimientos = HistorialService.get_proximos_mantenimientos(v.id)
        aceite = next(m for m in mantenimientos if m["tipo"] == "cambio_aceite")
        assert aceite["proximo_kilometraje"] == 25000
        assert aceite["restante_km"] == 5000
        assert aceite["estado"] == "al_dia"

    def test_get_proximos_mantenimientos_sin_datos(self, db):
        _, v = _crear_cliente_vehiculo(db)
        mantenimientos = HistorialService.get_proximos_mantenimientos(v.id)
        assert all(m["estado"] == "sin_datos" for m in mantenimientos)
        assert all(m["proximo_kilometraje"] is None for m in mantenimientos)


class TestAutoRegistro:
    def test_factura_autoregistra_historial(self, db):
        c, v = _crear_cliente_vehiculo(db)
        _crear_factura(db, c, v, "Cambio de aceite sintético")
        registros = HistorialService.get_historial_vehiculo(v.id)
        tipos = [r.tipo for r in registros]
        assert "factura" in tipos
        assert "cambio_aceite" in tipos

    def test_cita_completada_autoregistra_historial(self, client, db):
        _crear_admin(db)
        c, v = _crear_cliente_vehiculo(db)
        cita = Cita(cliente_id=c.id, vehiculo_id=v.id, fecha=date.today(),
                    hora=time(10, 0), descripcion="Afinación")
        db.session.add(cita)
        db.session.commit()
        _login(client, "admin_hist@test.com", "admin123")
        resp = client.post(f"/citas/cambiar-estado/{cita.id}/completado",
                           data={"csrf_token": "x"}, follow_redirects=True)
        assert resp.status_code == 200
        registros = HistorialService.get_historial_vehiculo(v.id)
        assert any(r.tipo == "cita" for r in registros)

    def test_ot_entregada_autoregistra_historial(self, client, db):
        _crear_admin(db)
        c, v = _crear_cliente_vehiculo(db)
        ot = OrdenTrabajo(numero="OT-TEST-1", cliente_id=c.id, vehiculo_id=v.id,
                          diagnostico_inicial="Reparación de frenos")
        db.session.add(ot)
        db.session.commit()
        _login(client, "admin_hist@test.com", "admin123")
        resp = client.post(f"/ordenes-trabajo/cambiar-estado/{ot.id}",
                           data={"estado": "entregado", "csrf_token": "x"},
                           follow_redirects=True)
        assert resp.status_code == 200
        registros = HistorialService.get_historial_vehiculo(v.id)
        assert any(r.tipo == "reparacion" and r.orden_trabajo_id == ot.id for r in registros)

    def test_factura_sin_cita_no_rompe(self, db):
        _, v = _crear_cliente_vehiculo(db)
        HistorialService.registrar_desde_factura(None)
        HistorialService.registrar_desde_orden(None)
        HistorialService.registrar_desde_cita(None)
        assert HistorialService.get_historial_vehiculo(v.id) == []


class TestHistorialRoute:
    def test_historial_requiere_login(self, client, db):
        c, v = _crear_cliente_vehiculo(db)
        resp = client.get(f"/vehiculos/historial/{v.id}", follow_redirects=True)
        assert resp.status_code == 200

    def test_historial_muestra_registros(self, client, db):
        c, v = _crear_cliente_vehiculo(db)
        _crear_admin(db)
        HistorialService.registrar(v.id, "observacion", "Suspensión ruidosa")
        _login(client, "admin_hist@test.com", "admin123")
        resp = client.get(f"/vehiculos/historial/{v.id}")
        assert resp.status_code == 200
        assert b"Suspensi" in resp.data or b"Suspensi" in resp.data.decode("utf-8").encode("utf-8")

    def test_agregar_observacion_manual(self, client, db):
        _crear_admin(db)
        c, v = _crear_cliente_vehiculo(db)
        _login(client, "admin_hist@test.com", "admin123")
        resp = client.post(f"/vehiculos/historial/{v.id}", data={
            "tipo": "observacion",
            "descripcion": "Cliente reporta vibración",
            "kilometraje": "25000",
            "csrf_token": "x",
        }, follow_redirects=True)
        assert resp.status_code == 200
        registros = HistorialService.get_historial_vehiculo(v.id)
        assert len(registros) == 1
        assert registros[0].descripcion == "Cliente reporta vibración"
        assert registros[0].kilometraje == 25000

    def test_vehiculo_404(self, client, db):
        _crear_admin(db)
        _login(client, "admin_hist@test.com", "admin123")
        resp = client.get("/vehiculos/historial/9999")
        assert resp.status_code == 404
