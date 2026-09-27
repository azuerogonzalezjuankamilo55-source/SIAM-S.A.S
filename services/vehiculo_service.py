from models.vehiculo import Vehiculo


class VehiculoService:
    """Identificacion legible de vehiculos.

    Todo selector de vehiculo de SIAM usa `descriptor` para que un cliente con
    varios vehiculos pueda distinguirlos. Los datos provienen del modelo, no se
    inventan: si `anio` o `tipo` estan vacios simplemente se omiten.
    """

    @staticmethod
    def descriptor(vehiculo: Vehiculo | None) -> str:
        """Texto unico de identificacion: placa, marca, modelo, anio y tipo.

        Ejemplo: "ABC123 - Chevrolet Onix - 2022 - Carro"
        """
        if vehiculo is None:
            return ""
        partes = [
            (vehiculo.placa or "").strip().upper(),
            " ".join(p for p in ((vehiculo.marca or "").strip(), (vehiculo.modelo or "").strip()) if p),
        ]
        if vehiculo.anio:
            partes.append(str(vehiculo.anio))
        if vehiculo.tipo:
            partes.append(vehiculo.tipo_label)
        return " - ".join(p for p in partes if p)

    @staticmethod
    def to_dict(vehiculo: Vehiculo) -> dict:
        """Payload completo para selects poblados por JavaScript."""
        return {
            "id": vehiculo.id,
            "placa": vehiculo.placa,
            "marca": vehiculo.marca,
            "modelo": vehiculo.modelo,
            "anio": vehiculo.anio,
            "tipo": vehiculo.tipo,
            "tipo_label": vehiculo.tipo_label,
            "texto": VehiculoService.descriptor(vehiculo),
        }

    @staticmethod
    def listar_para_select(cliente_id: int) -> list[dict]:
        """Vehiculos de un cliente en formato para <select> (JSON)."""
        vehiculos = (
            Vehiculo.query.filter_by(cliente_id=cliente_id).order_by(Vehiculo.placa).all()
        )
        return [VehiculoService.to_dict(v) for v in vehiculos]

    @staticmethod
    def listar_para_choices(cliente_id: int) -> list[tuple[int, str]]:
        """Vehiculos de un cliente como (id, texto) para SelectField de WTForms."""
        return [
            (v.id, VehiculoService.descriptor(v))
            for v in Vehiculo.query.filter_by(cliente_id=cliente_id)
            .order_by(Vehiculo.placa)
            .all()
        ]
