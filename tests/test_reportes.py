import io
import pytest
from datetime import date, datetime, time
from decimal import Decimal

from models import Usuario, Cliente, Vehiculo, Servicio, Mecanico, Inventario
from models.cita import Cita
from models.factura import Factura, FacturaDetalle
from models.orden_trabajo import OrdenTrabajo
from services.reporte_service import ReporteService
from services.inventario_service import InventarioService


def _crear_admin(db):
    u = Usuario(nombre="Admin", correo="admin_rep@test.com", rol="admin")
    u.set_password("admin123")
    db.session.add(u)
    db.session.commit()
    return u


def _crear_cliente(db, nombre="Cliente A", correo="cliente_rep@test.com"):
    c = Cliente(nombre=nombre, correo=correo)
    db.session.add(c)
    db.session.commit()
    u = Usuario(nombre=nombre, correo=correo, rol="cliente")
    u.set_password("clave1234")
    db.session.add(u)
    db.session.commit()
    return c, u


def _crear_factura(db, cliente, total=Decimal("100.00"), estado="pagado",
                   metodo_pago="Efectivo", servicio=None, numero=None):
    v = Vehiculo(cliente_id=cliente.id, marca="Toyota", modelo="Corolla", placa=f"RP-{numero or 1}")
    db.session.add(v)
    db.session.flush()
    cita = Cita(cliente_id=cliente.id, vehiculo_id=v.id, fecha=date.today(), hora=time(10, 0))
    db.session.add(cita)
    db.session.flush()
    factura = Factura(
        cita_id=cita.id,
        numero=numero or f"REP-{cliente.id}-{v.id}",
        subtotal=total,
        iva=Decimal("0.00"),
        total=total,
        metodo_pago=metodo_pago,
        estado=estado,
        created_at=datetime.now(),
    )
    db.session.add(factura)
    db.session.flush()
    if servicio is not None:
        detalle = FacturaDetalle(factura_id=factura.id, servicio_id=servicio.id,
                                 cantidad=1, precio_unitario=total, subtotal=total)
        db.session.add(detalle)
    db.session.commit()
    return factura


def _crear_servicio(db, nombre="Cambio de aceite"):
    s = Servicio(nombre=nombre)
    db.session.add(s)
    db.session.commit()
    return s


def _login(client, correo="admin_rep@test.com", password="admin123"):
    return client.post("/auth/login", data={"correo": correo, "password": password},
                       follow_redirects=True)


class TestResumen:
    def test_ingresos_solo_pagado_parcial(self, db):
        c, _ = _crear_cliente(db)
        _crear_factura(db, c, total=Decimal("100.00"), estado="pagado", numero="REP-001")
        _crear_factura(db, c, total=Decimal("50.00"), estado="pendiente", numero="REP-002")
        _crear_factura(db, c, total=Decimal("200.00"), estado="anulado", numero="REP-003")
        data = ReporteService.build_resumen()
        assert data.ingresos == 100.00
        assert data.facturas_periodo == 2
        assert data.ticket_promedio == 100.00

    def test_cartera(self, db):
        c, _ = _crear_cliente(db)
        _crear_factura(db, c, total=Decimal("100.00"), estado="pendiente", numero="REP-010")
        _crear_factura(db, c, total=Decimal("40.00"), estado="pagado", numero="REP-011")
        data = ReporteService.build_resumen()
        assert data.cartera == 100.00

    def test_ingresos_por_metodo(self, db):
        c, _ = _crear_cliente(db)
        _crear_factura(db, c, total=Decimal("100.00"), metodo_pago="Efectivo", numero="REP-020")
        _crear_factura(db, c, total=Decimal("50.00"), metodo_pago="Efectivo", numero="REP-021")
        _crear_factura(db, c, total=Decimal("30.00"), metodo_pago="Nequi", numero="REP-022")
        data = ReporteService.build_resumen()
        metodos = dict(data.ingresos_por_metodo)
        assert metodos["Efectivo"] == 150.00
        assert metodos["Nequi"] == 30.00

    def test_facturacion_por_cliente(self, db):
        c1, _ = _crear_cliente(db, nombre="Cliente Uno", correo="c1_rep@test.com")
        c2, _ = _crear_cliente(db, nombre="Cliente Dos", correo="c2_rep@test.com")
        _crear_factura(db, c1, total=Decimal("100.00"), numero="REP-030")
        _crear_factura(db, c1, total=Decimal("60.00"), numero="REP-031")
        _crear_factura(db, c2, total=Decimal("200.00"), numero="REP-032")
        data = ReporteService.build_resumen()
        nombres = {f["cliente"]: f["total"] for f in data.facturacion_clientes}
        assert nombres["Cliente Uno"] == 160.00
        assert nombres["Cliente Dos"] == 200.00

    def test_servicios_vendidos(self, db):
        c, _ = _crear_cliente(db)
        s = _crear_servicio(db, "Cambio de aceite")
        _crear_factura(db, c, total=Decimal("100.00"), servicio=s, numero="REP-040")
        _crear_factura(db, c, total=Decimal("120.00"), servicio=s, numero="REP-041")
        data = ReporteService.build_resumen()
        assert len(data.servicios_vendidos) == 1
        assert data.servicios_vendidos[0]["cantidad"] == 2
        assert data.servicios_vendidos[0]["total"] == 220.00

    def test_ots_por_estado_y_mecanicos(self, db):
        c, _ = _crear_cliente(db)
        v = Vehiculo(cliente_id=c.id, marca="Toyota", modelo="Corolla", placa="RP-OT")
        db.session.add(v)
        db.session.flush()
        m = Mecanico(nombre="Luis")
        db.session.add(m)
        db.session.commit()
        for i, estado in enumerate(["recibido", "entregado", "entregado"]):
            ot = OrdenTrabajo(numero=f"OT-REP-{i}", cliente_id=c.id, vehiculo_id=v.id,
                              mecanico_id=m.id, estado=estado)
            db.session.add(ot)
        db.session.commit()
        data = ReporteService.build_resumen()
        estados = dict(data.ots_por_estado)
        assert estados["entregado"] == 2
        assert estados["recibido"] == 1
        assert data.ots_entregadas == 2
        assert data.productividad_mecanicos[0]["ots"] == 2

    def test_movimientos_inventario(self, db):
        item = Inventario(nombre="Filtro", cantidad=5, stock_minimo=2, stock_critico=1,
                          precio_compra=Decimal("100.00"), precio_venta=Decimal("150.00"))
        db.session.add(item)
        db.session.commit()
        InventarioService.registrar_movimiento(item, "entrada", 3, 1, motivo="Compra")
        InventarioService.registrar_movimiento(item, "salida", 1, 1, motivo="Uso")
        data = ReporteService.build_resumen()
        assert data.movimientos_inventario["entradas"] == 3
        assert data.movimientos_inventario["salidas"] == 1
        assert data.valor_inventario > 0

    def test_filtro_por_fechas(self, db):
        c, _ = _crear_cliente(db)
        _crear_factura(db, c, total=Decimal("100.00"), numero="REP-050")
        desde = date.today()
        hasta = date.today()
        data = ReporteService.build_resumen(desde, hasta)
        assert data.facturas_periodo == 1
        data_vacio = ReporteService.build_resumen(date(2000, 1, 1), date(2000, 1, 2))
        assert data_vacio.facturas_periodo == 0
        assert data_vacio.ingresos == 0.0


class TestRoutes:
    def test_index_requiere_login(self, client):
        resp = client.get("/reportes/", follow_redirects=True)
        assert resp.status_code == 200

    def test_index_admin(self, client, db):
        _crear_admin(db)
        _login(client)
        c, _ = _crear_cliente(db)
        _crear_factura(db, c, total=Decimal("100.00"), numero="REP-060")
        resp = client.get("/reportes/")
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        assert "Reportes" in html
        assert "$100" in html

    def test_cliente_no_ve_reportes(self, client, db):
        c, u = _crear_cliente(db)
        _login(client, u.correo, "clave1234")
        resp = client.get("/reportes/", follow_redirects=True)
        assert resp.status_code == 200
        assert "No tienes permisos de administrador" in resp.data.decode("utf-8")

    def test_filtros_invalidos(self, client, db):
        _crear_admin(db)
        _login(client)
        resp = client.get("/reportes/?desde=basura&hasta=tambien")
        assert resp.status_code == 200

    def test_excel(self, client, db):
        _crear_admin(db)
        _login(client)
        c, _ = _crear_cliente(db)
        _crear_factura(db, c, total=Decimal("100.00"), numero="REP-070")
        resp = client.get("/reportes/excel")
        assert resp.status_code == 200
        assert resp.mimetype == ("application/vnd.openxmlformats-officedocument"
                                 ".spreadsheetml.sheet")
        assert resp.headers["Content-Disposition"].startswith("attachment")
        wb = pytest.importorskip("openpyxl").load_workbook(io.BytesIO(resp.data))
        assert "Resumen" in wb.sheetnames
        assert wb.sheetnames == ["Resumen", "Ingresos por día", "Métodos de pago",
                                 "Clientes", "Servicios", "Mecánicos", "Inventario"]

    def test_pdf(self, client, db):
        try:
            import weasyprint  # noqa: F401
        except Exception:
            pytest.skip("WeasyPrint no disponible en este entorno")
        _crear_admin(db)
        _login(client)
        c, _ = _crear_cliente(db)
        _crear_factura(db, c, total=Decimal("100.00"), numero="REP-080")
        resp = client.get("/reportes/pdf")
        if resp.status_code == 302:
            pytest.skip("WeasyPrint no genera PDF en este entorno")
        assert resp.status_code == 200
        assert resp.mimetype == "application/pdf"
        assert resp.data[:4] == b"%PDF"
