"""SIAM Management CLI.

Uso:
    python manage.py create-admin --nombre Admin --correo admin@siam.com --password secreto
    python manage.py seed
    python manage.py migrate
"""

import click


@click.group()
def cli():
    pass


@cli.command()
@click.option("--nombre", default="Administrador", help="Nombre del administrador")
@click.option("--correo", default="admin@siam.com", help="Correo del administrador")
@click.option("--password", default="admin123", help="Contraseña del administrador")
def create_admin(nombre, correo, password):
    """Crea el usuario administrador inicial."""
    from app import create_app
    from database.db import db
    from models.usuario import Usuario

    app = create_app()
    with app.app_context():
        existe = Usuario.query.filter_by(correo=correo).first()
        if existe:
            click.echo(f"El usuario {correo} ya existe.")
            return

        admin = Usuario(
            nombre=nombre,
            correo=correo,
            rol="admin",
        )
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        click.echo(f"Administrador creado: {correo}")


@cli.command()
def seed():
    """Puebla la base de datos con datos de ejemplo."""
    from app import create_app
    from database.db import db
    from models.cliente import Cliente
    from models.vehiculo import Vehiculo
    from models.servicio import Servicio
    from models.mecanico import Mecanico
    from models.inventario import Inventario

    app = create_app()
    with app.app_context():
        if Servicio.query.first():
            click.echo("La base de datos ya contiene datos. Omite seed.")
            return

        servicios = [
            Servicio(nombre="Cambio de aceite", descripcion="Cambio de aceite y filtro", precio_estimado=45000, duracion_estimada=30, categoria="Mantenimiento"),
            Servicio(nombre="Alineación y balanceo", descripcion="Alineación de dirección y balanceo de llantas", precio_estimado=35000, duracion_estimada=45, categoria="Llantas"),
            Servicio(nombre="Revisión de frenos", descripcion="Inspección y mantenimiento del sistema de frenos", precio_estimado=55000, duracion_estimada=60, categoria="Mecánica"),
            Servicio(nombre="Diagnóstico computarizado", descripcion="Escanéo electrónico del vehículo", precio_estimado=60000, duracion_estimada=30, categoria="Diagnóstico"),
            Servicio(nombre="Cambio de llantas", descripcion="Montaje y balanceo de llantas nuevas", precio_estimado=25000, duracion_estimada=40, categoria="Llantas"),
        ]
        db.session.add_all(servicios)

        mecanicos = [
            Mecanico(nombre="Carlos Méndez", telefono="3001234567", especialidad="Motor y transmisión"),
            Mecanico(nombre="Ana Giraldo", telefono="3007654321", especialidad="Sistema eléctrico"),
            Mecanico(nombre="Pedro Ramírez", telefono="3009876543", especialidad="Frenos y suspensión"),
        ]
        db.session.add_all(mecanicos)

        inventario = [
            Inventario(nombre="Aceite 10W-40", cantidad=20, precio_compra=18000, precio_venta=35000, categoria="Aceites", stock_minimo=5),
            Inventario(nombre="Filtro de aceite", cantidad=15, precio_compra=8000, precio_venta=15000, categoria="Filtros", stock_minimo=5),
            Inventario(nombre="Pastillas de freno", cantidad=8, precio_compra=25000, precio_venta=45000, categoria="Frenos", stock_minimo=3),
            Inventario(nombre="Bujías (juego x4)", cantidad=6, precio_compra=12000, precio_venta=22000, categoria="Eléctrico", stock_minimo=2),
        ]
        db.session.add_all(inventario)

        db.session.commit()
        click.echo("Datos de ejemplo insertados correctamente.")


@cli.command()
def migrate():
    """Ejecuta migraciones pendientes (atajo para flask db upgrade)."""
    from flask_migrate import upgrade
    from app import create_app

    app = create_app()
    with app.app_context():
        upgrade()
        click.echo("Migraciones ejecutadas.")


if __name__ == "__main__":
    cli()
