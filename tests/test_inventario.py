import pytest
from datetime import date
from decimal import Decimal

from models import Usuario, Inventario
from models.movimiento_inventario import MovimientoInventario
from models.recordatorio import Recordatorio
from services.inventario_service import InventarioService


def _crear_admin(db):
    u = Usuario(nombre="Admin", correo="admin_inv@test.com", rol="admin")
    u.set_password("admin123")
    db.session.add(u)
    db.session.commit()
    return u


def _crear_item(db, nombre="Filtro", cantidad=10, stock_minimo=5, stock_critico=2,
                precio_compra=Decimal("100.00"), precio_venta=Decimal("150.00")):
    item = Inventario(
        nombre=nombre,
        cantidad=cantidad,
        stock_minimo=stock_minimo,
        stock_critico=stock_critico,
        precio_compra=precio_compra,
        precio_venta=precio_venta,
    )
    db.session.add(item)
    db.session.commit()
    return item


def _login(client, correo="admin_inv@test.com", password="admin123"):
    return client.post("/auth/login", data={"correo": correo, "password": password},
                       follow_redirects=True)


class TestMovimientos:
    def test_entrada(self, db):
        item = _crear_item(db, cantidad=5)
        InventarioService.registrar_movimiento(item, "entrada", 3, 1, motivo="Compra")
        item = db.session.get(Inventario, item.id)
        assert item.cantidad == 8
        mov = MovimientoInventario.query.filter_by(inventario_id=item.id).first()
        assert mov.tipo == "entrada"
        assert mov.saldo_anterior == 5
        assert mov.saldo_posterior == 8

    def test_salida_no_negativo(self, db):
        item = _crear_item(db, cantidad=2)
        InventarioService.registrar_movimiento(item, "salida", 5, 1)
        item = db.session.get(Inventario, item.id)
        assert item.cantidad == 0

    def test_baja_pone_stock_cero(self, db):
        item = _crear_item(db, cantidad=7)
        InventarioService.registrar_movimiento(item, "baja", 0, 1, motivo="Baja")
        item = db.session.get(Inventario, item.id)
        assert item.cantidad == 0

    def test_tipo_invalido(self, db):
        item = _crear_item(db)
        with pytest.raises(ValueError):
            InventarioService.registrar_movimiento(item, "fantasma", 1, 1)

    def test_cantidad_invalida(self, db):
        item = _crear_item(db)
        with pytest.raises(ValueError):
            InventarioService.registrar_movimiento(item, "salida", 0, 1)


class TestCostoPromedio:
    def test_costo_inicial(self, db):
        item = _crear_item(db, cantidad=0)
        InventarioService.registrar_movimiento(item, "entrada", 10, 1,
                                               costo_unitario=Decimal("100.00"))
        item = db.session.get(Inventario, item.id)
        assert item.costo_promedio == Decimal("100.00")

    def test_costo_ponderado(self, db):
        item = _crear_item(db, cantidad=0)
        InventarioService.registrar_movimiento(item, "entrada", 10, 1,
                                               costo_unitario=Decimal("100.00"))
        InventarioService.registrar_movimiento(item, "entrada", 10, 1,
                                               costo_unitario=Decimal("200.00"))
        item = db.session.get(Inventario, item.id)
        assert item.cantidad == 20
        assert item.costo_promedio == Decimal("150.00")

    def test_salida_no_afecta_costo(self, db):
        item = _crear_item(db, cantidad=0)
        InventarioService.registrar_movimiento(item, "entrada", 10, 1,
                                               costo_unitario=Decimal("100.00"))
        InventarioService.registrar_movimiento(item, "salida", 5, 1)
        item = db.session.get(Inventario, item.id)
        assert item.costo_promedio == Decimal("100.00")


class TestBajas:
    def test_dar_baja(self, db):
        u = _crear_admin(db)
        item = _crear_item(db, cantidad=7)
        InventarioService.dar_baja(item, "Producto dañado", u.id)
        item = db.session.get(Inventario, item.id)
        assert item.es_baja
        assert not item.activo
        assert item.motivo_baja == "Producto dañado"
        assert item.usuario_baja_id == u.id
        assert item.cantidad == 0
        mov = MovimientoInventario.query.filter_by(inventario_id=item.id, tipo="baja").first()
        assert mov is not None

    def test_dar_baja_sin_motivo(self, db):
        u = _crear_admin(db)
        item = _crear_item(db)
        with pytest.raises(ValueError):
            InventarioService.dar_baja(item, "   ", u.id)

    def test_dar_baja_repetida(self, db):
        u = _crear_admin(db)
        item = _crear_item(db)
        InventarioService.dar_baja(item, "Motivo", u.id)
        with pytest.raises(ValueError):
            InventarioService.dar_baja(item, "Otro motivo", u.id)

    def test_restaurar(self, db):
        u = _crear_admin(db)
        item = _crear_item(db)
        InventarioService.dar_baja(item, "Motivo", u.id)
        InventarioService.restaurar(item, u.id)
        item = db.session.get(Inventario, item.id)
        assert not item.es_baja
        assert item.activo
        assert item.motivo_baja is None
        assert item.usuario_baja_id is None

    def test_restaurar_no_baja(self, db):
        u = _crear_admin(db)
        item = _crear_item(db)
        with pytest.raises(ValueError):
            InventarioService.restaurar(item, u.id)

    def test_stock_bajo_ignora_baja(self, db):
        u = _crear_admin(db)
        item = _crear_item(db, cantidad=0, stock_minimo=5)
        assert item.stock_bajo
        InventarioService.dar_baja(item, "Motivo", u.id)
        item = db.session.get(Inventario, item.id)
        assert not item.stock_bajo


class TestValorizacion:
    def test_valor_total(self, db):
        _crear_item(db, nombre="A", cantidad=10, precio_compra=Decimal("100.00"), stock_minimo=0)
        _crear_item(db, nombre="B", cantidad=5, precio_compra=Decimal("200.00"), stock_minimo=0)
        data = InventarioService.valorizacion()
        assert data["total_productos"] == 2
        assert data["total_valor"] == 2000.0
        assert data["items_bajo"] == 0

    def test_baja_no_se_valoriza(self, db):
        u = _crear_admin(db)
        item = _crear_item(db, nombre="A", cantidad=10, precio_compra=Decimal("100.00"))
        InventarioService.dar_baja(item, "Motivo", u.id)
        data = InventarioService.valorizacion()
        assert data["total_productos"] == 0
        assert data["total_valor"] == 0.0


class TestKardex:
    def test_get_kardex_filtros(self, db):
        item = _crear_item(db)
        InventarioService.registrar_movimiento(item, "entrada", 5, 1, motivo="Compra")
        InventarioService.registrar_movimiento(item, "salida", 2, 1, motivo="OT-1")
        assert len(InventarioService.get_kardex()) == 2
        assert len(InventarioService.get_kardex(tipo="entrada")) == 1
        assert len(InventarioService.get_kardex(inventario_id=item.id)) == 2
        assert len(InventarioService.get_kardex(tipo="ajuste")) == 0


class TestAlertasReposicion:
    def test_genera_para_stock_bajo(self, db):
        _crear_item(db, nombre="Filtro", cantidad=2, stock_minimo=5)
        creados = InventarioService.generar_alertas_reposicion()
        assert creados == 1
        rec = Recordatorio.query.filter_by(tipo="reposicion").first()
        assert rec is not None
        assert rec.titulo == "Reponer: Filtro"
        assert rec.vehiculo_id is None
        assert rec.estado == "pendiente"

    def test_no_duplica(self, db):
        _crear_item(db, nombre="Filtro", cantidad=0, stock_minimo=5)
        assert InventarioService.generar_alertas_reposicion() == 1
        assert InventarioService.generar_alertas_reposicion() == 0
        assert Recordatorio.query.count() == 1

    def test_stock_ok_no_genera(self, db):
        _crear_item(db, nombre="Filtro", cantidad=50, stock_minimo=5)
        assert InventarioService.generar_alertas_reposicion() == 0


class TestRoutes:
    def test_listar_solo_activos(self, client, db):
        _crear_admin(db)
        _login(client)
        u = Usuario.query.filter_by(correo="admin_inv@test.com").first()
        item = _crear_item(db, nombre="Filtro")
        InventarioService.dar_baja(item, "Motivo", u.id)
        resp = client.get("/inventario/")
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        assert "Filtro" not in html
        resp = client.get("/inventario/?incluir_bajas=1")
        html = resp.data.decode("utf-8")
        assert "Filtro" in html

    def test_kardex_route(self, client, db):
        _crear_admin(db)
        _login(client)
        resp = client.get("/inventario/kardex")
        assert resp.status_code == 200

    def test_baja_route(self, client, db):
        u = _crear_admin(db)
        _login(client)
        item = _crear_item(db)
        resp = client.post(f"/inventario/baja/{item.id}",
                           data={"motivo": "Obsoleto", "csrf_token": "x"},
                           follow_redirects=True)
        assert resp.status_code == 200
        item = db.session.get(Inventario, item.id)
        assert item.es_baja

    def test_baja_route_sin_motivo(self, client, db):
        _crear_admin(db)
        _login(client)
        item = _crear_item(db)
        resp = client.post(f"/inventario/baja/{item.id}",
                           data={"motivo": "", "csrf_token": "x"},
                           follow_redirects=True)
        assert resp.status_code == 200
        item = db.session.get(Inventario, item.id)
        assert not item.es_baja

    def test_restaurar_route(self, client, db):
        u = _crear_admin(db)
        _login(client)
        item = _crear_item(db)
        InventarioService.dar_baja(item, "Motivo", u.id)
        resp = client.post(f"/inventario/restaurar/{item.id}",
                           data={"csrf_token": "x"}, follow_redirects=True)
        assert resp.status_code == 200
        item = db.session.get(Inventario, item.id)
        assert not item.es_baja

    def test_generar_alertas_route(self, client, db):
        _crear_admin(db)
        _login(client)
        _crear_item(db, nombre="Filtro", cantidad=1, stock_minimo=5)
        resp = client.post("/inventario/alertas/generar-recordatorios",
                           data={"csrf_token": "x"}, follow_redirects=True)
        assert resp.status_code == 200
        assert Recordatorio.query.filter_by(tipo="reposicion").count() == 1
        assert "1 alertas" in resp.data.decode("utf-8")

    def test_reposicion_visible_admin_recordatorios(self, client, db):
        _crear_admin(db)
        _login(client)
        _crear_item(db, nombre="Filtro", cantidad=0, stock_minimo=5)
        InventarioService.generar_alertas_reposicion()
        resp = client.get("/recordatorios/")
        assert resp.status_code == 200
        assert "Reponer: Filtro" in resp.data.decode("utf-8")
