from models.vehiculo import Vehiculo


class VehiculoService:

    @staticmethod
    def listar_para_select(cliente_id: int) -> list[dict]:
        """Lista de vehículos de un cliente en formato para <select> (JSON)."""
        vehiculos = Vehiculo.query.filter_by(cliente_id=cliente_id).all()
        return [
            {"id": v.id, "texto": f"{v.marca} {v.modelo} - {v.placa}"}
            for v in vehiculos
        ]
