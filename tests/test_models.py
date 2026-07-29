import pytest
from models import (
    Usuario, Cliente, Vehiculo, Servicio,
    Mecanico, Cita, Factura, FacturaDetalle, Inventario,
)


class TestUsuario:
    def test_set_password(self, db):
        u = Usuario(nombre="Test", correo="test@test.com")
        u.set_password("secreto")
        assert u.password_hash != "secreto"
        assert u.check_password("secreto")
        assert not u.check_password("otra")

    def test_repr(self, db):
        u = Usuario(nombre="Test", correo="a@b.com", rol="admin")
        assert "a@b.com" in repr(u)


class TestCliente:
    def test_crear_cliente(self, db):
        c = Cliente(nombre="Juan", telefono="123", cedula="ABC")
        db.session.add(c)
        db.session.commit()
        assert c.id is not None
        assert repr(c) == f"<Cliente {c.id}:Juan>"


class TestVehiculo:
    def test_crear_vehiculo(self, db):
        c = Cliente(nombre="Juan")
        db.session.add(c)
        db.session.commit()
        v = Vehiculo(cliente_id=c.id, marca="Toyota", modelo="Corolla", placa="ABC-123")
        db.session.add(v)
        db.session.commit()
        assert v.id is not None


class TestServicio:
    def test_crear_servicio(self, db):
        s = Servicio(nombre="Cambio aceite", precio_estimado=50000)
        db.session.add(s)
        db.session.commit()
        assert s.id is not None


class TestMecanico:
    def test_crear_mecanico(self, db):
        m = Mecanico(nombre="Carlos", especialidad="Motor")
        db.session.add(m)
        db.session.commit()
        assert m.id is not None


class TestCita:
    def test_crear_cita(self, db):
        c = Cliente(nombre="Juan")
        db.session.add(c)
        db.session.commit()
        v = Vehiculo(cliente_id=c.id, marca="Toyota", modelo="Corolla", placa="ABC-123")
        db.session.add(v)
        db.session.commit()
        from datetime import date, time
        cita = Cita(cliente_id=c.id, vehiculo_id=v.id, fecha=date.today(), hora=time(10, 0))
        db.session.add(cita)
        db.session.commit()
        assert cita.id is not None
        assert cita.estado == "pendiente"


class TestFactura:
    def test_crear_factura(self, db):
        c = Cliente(nombre="Juan")
        db.session.add(c)
        db.session.flush()
        v = Vehiculo(cliente_id=c.id, marca="T", modelo="C", placa="X")
        db.session.add(v)
        db.session.flush()
        from datetime import date, time
        cita = Cita(cliente_id=c.id, vehiculo_id=v.id, fecha=date.today(), hora=time(10, 0))
        db.session.add(cita)
        db.session.flush()
        s = Servicio(nombre="Aceite")
        db.session.add(s)
        db.session.flush()
        factura = Factura(cita_id=cita.id, numero="FAC-000001", subtotal=100, iva=19, total=119)
        db.session.add(factura)
        db.session.flush()
        detalle = FacturaDetalle(factura_id=factura.id, servicio_id=s.id, cantidad=1, precio_unitario=100, subtotal=100)
        db.session.add(detalle)
        db.session.commit()
        assert factura.id is not None
        assert len(factura.detalles) == 1


class TestInventario:
    def test_stock_bajo(self, db):
        item = Inventario(nombre="Filtro", cantidad=2, stock_minimo=5)
        assert item.stock_bajo is True
        item.cantidad = 10
        assert item.stock_bajo is False

    def test_repr(self, db):
        item = Inventario(nombre="Aceite", cantidad=10)
        assert "Aceite" in repr(item)
