import io
import pytest
from datetime import date
from decimal import Decimal

from PIL import Image

from models import Usuario, Cliente, Vehiculo, OrdenTrabajo, Inventario, MovimientoInventario
from models.orden_trabajo_item import OrdenTrabajoItem
from models.orden_trabajo_foto import OrdenTrabajoFoto
from models.orden_trabajo_repuesto import OrdenTrabajoRepuesto
from models.historial_vehiculo import HistorialVehiculo
from services.orden_trabajo_service import OrdenTrabajoService
from exceptions import BusinessRuleException, NotFoundException


def _imagen_bytes(fmt: str = "JPEG") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (200, 30, 30)).save(buf, fmt)
    return buf.getvalue()


def _crear_admin(db):
    u = Usuario(nombre="Admin", correo="admin_otp@test.com", rol="admin")
    u.set_password("admin123")
    db.session.add(u)
    db.session.commit()
    return u


def _crear_ot(db):
    c = Cliente(nombre="Cliente OT", correo="ot@test.com")
    db.session.add(c)
    db.session.commit()
    v = Vehiculo(cliente_id=c.id, marca="Toyota", modelo="Corolla", placa="OT-123")
    db.session.add(v)
    db.session.commit()
    ot = OrdenTrabajo(numero="OT-PROF-1", cliente_id=c.id, vehiculo_id=v.id)
    db.session.add(ot)
    db.session.commit()
    return c, v, ot


def _crear_inventario(db, nombre="Filtro de aceite", cantidad=10):
    inv = Inventario(nombre=nombre, cantidad=cantidad, precio_venta=Decimal("15000"))
    db.session.add(inv)
    db.session.commit()
    return inv


def _login(client, correo, password):
    return client.post("/auth/login", data={"correo": correo, "password": password},
                       follow_redirects=True)


class FakeFile:
    def __init__(self, filename, content=b"data"):
        self.filename = filename
        self.content_length = len(content)
        self._stream = io.BytesIO(content)

    def read(self, size=-1):
        return self._stream.read(size)

    def seek(self, pos):
        return self._stream.seek(pos)

    def tell(self):
        return self._stream.tell()

    def save(self, path):
        self._stream.seek(0)
        with open(path, "wb") as f:
            f.write(self._stream.read())


class TestChecklist:
    def test_agregar_item(self, db):
        _, _, ot = _crear_ot(db)
        item = OrdenTrabajoService.agregar_item(ot.id, "Cambiar aceite", 30)
        assert item.id is not None
        assert item.tiempo_minutos == 30
        assert ot.items_completados == 0
        assert ot.tiempo_total_minutos == 30

    def test_agregar_item_sin_descripcion(self, db):
        _, _, ot = _crear_ot(db)
        with pytest.raises(BusinessRuleException):
            OrdenTrabajoService.agregar_item(ot.id, "   ")

    def test_toggle_item(self, db):
        _, _, ot = _crear_ot(db)
        item = OrdenTrabajoService.agregar_item(ot.id, "Tarea", 10)
        OrdenTrabajoService.toggle_item(item.id)
        assert db.session.get(OrdenTrabajoItem, item.id).completado is True
        assert ot.items_completados == 1

    def test_actualizar_item(self, db):
        _, _, ot = _crear_ot(db)
        item = OrdenTrabajoService.agregar_item(ot.id, "Tarea", 10)
        OrdenTrabajoService.actualizar_item(item.id, "Tarea nueva", 45)
        item = db.session.get(OrdenTrabajoItem, item.id)
        assert item.descripcion == "Tarea nueva"
        assert item.tiempo_minutos == 45

    def test_eliminar_item(self, db):
        _, _, ot = _crear_ot(db)
        item = OrdenTrabajoService.agregar_item(ot.id, "Tarea")
        OrdenTrabajoService.eliminar_item(item.id)
        assert db.session.get(OrdenTrabajoItem, item.id) is None


class TestRepuestos:
    def test_agregar_repuesto_descuenta_stock(self, db):
        _, _, ot = _crear_ot(db)
        inv = _crear_inventario(db, cantidad=10)
        rep = OrdenTrabajoService.agregar_repuesto(
            ot.id, inv.id, 2, Decimal("15000"), nota="Filtro",
        )
        assert rep.subtotal == Decimal("30000.00")
        assert db.session.get(Inventario, inv.id).cantidad == 8
        mov = MovimientoInventario.query.filter_by(inventario_id=inv.id).first()
        assert mov.tipo == "salida"
        assert mov.referencia == "OT-PROF-1"
        assert ot.total_repuestos == Decimal("30000.00")

    def test_stock_insuficiente(self, db):
        _, _, ot = _crear_ot(db)
        inv = _crear_inventario(db, cantidad=1)
        with pytest.raises(BusinessRuleException):
            OrdenTrabajoService.agregar_repuesto(ot.id, inv.id, 5, Decimal("10000"))

    def test_eliminar_repuesto_devuelve_stock(self, db):
        _, _, ot = _crear_ot(db)
        inv = _crear_inventario(db, cantidad=10)
        rep = OrdenTrabajoService.agregar_repuesto(ot.id, inv.id, 2, Decimal("15000"))
        OrdenTrabajoService.eliminar_repuesto(rep.id)
        assert db.session.get(Inventario, inv.id).cantidad == 10
        assert db.session.get(OrdenTrabajoRepuesto, rep.id) is None


class TestFotos:
    def test_guardar_foto_ok(self, app, db):
        _, _, ot = _crear_ot(db)
        foto = OrdenTrabajoService.guardar_foto(
            ot.id, FakeFile("foto.jpg", _imagen_bytes("JPEG")), "Antes",
            upload_root=app.root_path,
        )
        assert foto.path.startswith("/static/uploads/ot/")
        assert foto.path.endswith(".jpg")
        assert db.session.get(OrdenTrabajoFoto, foto.id) is not None

    def test_guardar_foto_extension_invalida(self, app, db):
        _, _, ot = _crear_ot(db)
        with pytest.raises(BusinessRuleException):
            OrdenTrabajoService.guardar_foto(
                ot.id, FakeFile("documento.txt"), "bad", upload_root=app.root_path,
            )

    def test_guardar_foto_contenido_no_imagen(self, app, db):
        _, _, ot = _crear_ot(db)
        with pytest.raises(BusinessRuleException):
            OrdenTrabajoService.guardar_foto(
                ot.id, FakeFile("foto.jpg", b"no soy una imagen"), "bad",
                upload_root=app.root_path,
            )


class TestFirmasYEntrega:
    def test_guardar_firma(self, app, db):
        _, _, ot = _crear_ot(db)
        OrdenTrabajoService.guardar_firma(
            ot.id, "mecanico", FakeFile("firma.png", _imagen_bytes("PNG")),
            upload_root=app.root_path,
        )
        ot = db.session.get(OrdenTrabajo, ot.id)
        assert ot.firma_mecanico_path.startswith("/static/uploads/firmas/")

    def test_entregar_registra_historial_vehiculo(self, db):
        _, _, ot = _crear_ot(db)
        OrdenTrabajoService.entregar(ot.id, kms_salida=45000, nivel_combustible_salida="Lleno")
        ot = db.session.get(OrdenTrabajo, ot.id)
        assert ot.estado == "entregado"
        assert ot.fecha_entrega == date.today()
        assert ot.kms_salida == 45000
        assert ot.nivel_combustible_salida == "Lleno"
        historial = HistorialVehiculo.query.filter_by(
            vehiculo_id=ot.vehiculo_id, orden_trabajo_id=ot.id
        ).all()
        assert len(historial) == 1


class TestRoutes:
    def test_agregar_item_route(self, client, db):
        _crear_admin(db)
        _, _, ot = _crear_ot(db)
        _login(client, "admin_otp@test.com", "admin123")
        resp = client.post(f"/ordenes-trabajo/items/agregar/{ot.id}", data={
            "descripcion": "Revisar frenos",
            "tiempo_minutos": "25",
            "csrf_token": "x",
        }, follow_redirects=True)
        assert resp.status_code == 200
        item = OrdenTrabajoItem.query.filter_by(orden_trabajo_id=ot.id).first()
        assert item is not None
        assert item.descripcion == "Revisar frenos"

    def test_toggle_item_route(self, client, db):
        _crear_admin(db)
        _, _, ot = _crear_ot(db)
        item = OrdenTrabajoService.agregar_item(ot.id, "Tarea")
        _login(client, "admin_otp@test.com", "admin123")
        resp = client.post(f"/ordenes-trabajo/items/toggle/{item.id}", data={"csrf_token": "x"},
                           follow_redirects=True)
        assert resp.status_code == 200
        assert db.session.get(OrdenTrabajoItem, item.id).completado is True

    def test_agregar_repuesto_route(self, client, db):
        _crear_admin(db)
        _, _, ot = _crear_ot(db)
        inv = _crear_inventario(db, cantidad=10)
        _login(client, "admin_otp@test.com", "admin123")
        resp = client.post(f"/ordenes-trabajo/repuestos/agregar/{ot.id}", data={
            "inventario_id": inv.id,
            "cantidad": "3",
            "precio_unitario": "15000",
            "nota": "",
            "csrf_token": "x",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert db.session.get(Inventario, inv.id).cantidad == 7

    def test_entregar_route(self, client, db):
        _crear_admin(db)
        _, _, ot = _crear_ot(db)
        _login(client, "admin_otp@test.com", "admin123")
        resp = client.post(f"/ordenes-trabajo/entregar/{ot.id}", data={
            "kms_salida": "50000",
            "nivel_combustible_salida": "1/2",
            "csrf_token": "x",
        }, follow_redirects=True)
        assert resp.status_code == 200
        ot = db.session.get(OrdenTrabajo, ot.id)
        assert ot.estado == "entregado"
        assert ot.nivel_combustible_salida == "1/2"

    def test_subir_firma_route(self, client, db, app):
        _crear_admin(db)
        _, _, ot = _crear_ot(db)
        _login(client, "admin_otp@test.com", "admin123")
        resp = client.post(
            f"/ordenes-trabajo/firma/{ot.id}",
            data={"tipo": "cliente", "firma": (io.BytesIO(_imagen_bytes("PNG")), "firma.png"),
                  "csrf_token": "x"},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        assert resp.status_code == 200
        ot = db.session.get(OrdenTrabajo, ot.id)
        assert ot.firma_cliente_path.startswith("/static/uploads/firmas/")

    def test_ver_muestra_checklist(self, client, db):
        _crear_admin(db)
        _, _, ot = _crear_ot(db)
        OrdenTrabajoService.agregar_item(ot.id, "Cambio de aceite", 30)
        _login(client, "admin_otp@test.com", "admin123")
        resp = client.get(f"/ordenes-trabajo/ver/{ot.id}")
        assert resp.status_code == 200
        assert b"Cambio de aceite" in resp.data
