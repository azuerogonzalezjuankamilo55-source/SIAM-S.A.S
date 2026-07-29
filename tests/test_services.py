from decimal import Decimal
from datetime import date, time

import pytest
from models import Cliente, Vehiculo, Servicio, Cita, Mecanico
from services.factura_service import FacturaService, FacturaInput
from services.dashboard_service import DashboardService
from exceptions import NotFoundException, BusinessRuleException


class TestFacturaService:
    def test_generar_factura_exitoso(self, db):
        c = Cliente(nombre="Juan")
        db.session.add(c)
        db.session.commit()
        v = Vehiculo(cliente_id=c.id, marca="T", modelo="C", placa="X")
        db.session.add(v)
        db.session.commit()
        m = Mecanico(nombre="Carlos")
        db.session.add(m)
        db.session.commit()
        cita = Cita(cliente_id=c.id, vehiculo_id=v.id, mecanico_id=m.id, fecha=date.today(), hora=time(10, 0))
        db.session.add(cita)
        db.session.commit()
        s = Servicio(nombre="Aceite", precio_estimado=50000)
        db.session.add(s)
        db.session.commit()

        input_data = FacturaInput(
            cita_id=cita.id,
            servicio_ids=[s.id],
            precios=[Decimal("50000")],
            cantidades=[1],
            descuento=Decimal("0"),
            metodo_pago="Efectivo",
        )
        factura = FacturaService.generar(input_data)
        assert factura.id is not None
        assert factura.total == Decimal("59500.00")
        assert factura.estado == "pendiente"

    def test_generar_factura_cita_inexistente(self, db):
        input_data = FacturaInput(
            cita_id=9999,
            servicio_ids=[1],
            precios=[Decimal("100")],
            cantidades=[1],
            descuento=Decimal("0"),
            metodo_pago="Efectivo",
        )
        with pytest.raises(NotFoundException):
            FacturaService.generar(input_data)

    def test_generar_factura_sin_servicios(self, db):
        c = Cliente(nombre="Juan")
        db.session.add(c)
        db.session.commit()
        v = Vehiculo(cliente_id=c.id, marca="T", modelo="C", placa="X")
        db.session.add(v)
        db.session.commit()
        cita = Cita(cliente_id=c.id, vehiculo_id=v.id, fecha=date.today(), hora=time(10, 0))
        db.session.add(cita)
        db.session.commit()

        input_data = FacturaInput(
            cita_id=cita.id,
            servicio_ids=[],
            precios=[],
            cantidades=[],
            descuento=Decimal("0"),
            metodo_pago="Efectivo",
        )
        with pytest.raises(BusinessRuleException):
            FacturaService.generar(input_data)


class TestDashboardService:
    def test_get_data_vacio(self, db):
        data = DashboardService.get_data()
        assert data.total_clientes == 0
        assert data.total_vehiculos == 0
        assert data.citas_hoy == 0
        assert data.ingresos_hoy == 0.0
