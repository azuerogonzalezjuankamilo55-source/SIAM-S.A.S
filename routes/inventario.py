import logging
from typing import Any

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user

from models.inventario import Inventario
from models.categoria_inventario import CategoriaInventario
from models.movimiento_inventario import MovimientoInventario
from database.db import db
from forms import InventarioForm, MovimientoInventarioForm, CategoriaInventarioForm

logger = logging.getLogger("siam.routes.inventario")
inventario_bp = Blueprint("inventario", __name__, url_prefix="/inventario")


@inventario_bp.route("/")
@login_required
def listar() -> Any:
    categoria_id = request.args.get("categoria_id", type=int)
    stock_bajo = request.args.get("stock_bajo", type=bool)
    q = Inventario.query

    if categoria_id:
        q = q.filter(Inventario.categoria_id == categoria_id)
    if stock_bajo:
        q = q.filter(Inventario.cantidad <= Inventario.stock_minimo)

    items = q.order_by(Inventario.nombre).all()
    categorias = CategoriaInventario.query.order_by(CategoriaInventario.nombre).all()
    return render_template("inventario/listar.html", items=items, categorias=categorias)


@inventario_bp.route("/crear", methods=["GET", "POST"])
@login_required
def crear() -> Any:
    form = InventarioForm()
    if form.validate_on_submit():
        item = Inventario(
            nombre=form.nombre.data,
            descripcion=form.descripcion.data,
            sku=form.sku.data or None,
            codigo_barras=form.codigo_barras.data or None,
            ubicacion=form.ubicacion.data or None,
            cantidad=form.cantidad.data or 0,
            precio_compra=form.precio_compra.data,
            precio_venta=form.precio_venta.data,
            proveedor=form.proveedor.data,
            categoria_id=form.categoria_id.data or None,
            stock_minimo=form.stock_minimo.data or 0,
            stock_critico=form.stock_critico.data or 0,
        )
        db.session.add(item)
        db.session.flush()

        item.registrar_movimiento(
            tipo="entrada",
            cantidad=item.cantidad,
            usuario_id=current_user.id,
            motivo="Inventario inicial",
        )
        db.session.commit()
        logger.info("Producto creado: %s (SKU=%s)", item.nombre, item.sku)
        flash("Producto agregado al inventario", "success")
        return redirect(url_for("inventario.listar"))
    return render_template("inventario/form.html", form=form)


@inventario_bp.route("/ver/<int:id>")
@login_required
def ver(id: int) -> Any:
    item = Inventario.query.get_or_404(id)
    movimientos = item.movimientos
    return render_template("inventario/ver.html", item=item, movimientos=movimientos)


@inventario_bp.route("/editar/<int:id>", methods=["GET", "POST"])
@login_required
def editar(id: int) -> Any:
    item = Inventario.query.get_or_404(id)
    form = InventarioForm(obj=item)
    if form.validate_on_submit():
        cantidad_anterior = item.cantidad
        form.populate_obj(item)
        if item.cantidad != cantidad_anterior:
            item.registrar_movimiento(
                tipo="ajuste",
                cantidad=item.cantidad,
                usuario_id=current_user.id,
                motivo="Ajuste por edición de producto",
            )
        db.session.commit()
        logger.info("Producto actualizado: %s", item.nombre)
        flash("Producto actualizado", "success")
        return redirect(url_for("inventario.listar"))
    return render_template("inventario/form.html", form=form, item=item)


@inventario_bp.route("/eliminar/<int:id>")
@login_required
def eliminar(id: int) -> Any:
    item = Inventario.query.get_or_404(id)
    db.session.delete(item)
    db.session.commit()
    logger.info("Producto eliminado: %s", item.nombre)
    flash("Producto eliminado", "success")
    return redirect(url_for("inventario.listar"))


@inventario_bp.route("/movimiento/<int:id>", methods=["GET", "POST"])
@login_required
def movimiento(id: int) -> Any:
    item = Inventario.query.get_or_404(id)
    form = MovimientoInventarioForm()
    if form.validate_on_submit():
        tipo = form.tipo.data
        cantidad = form.cantidad.data
        item.registrar_movimiento(
            tipo=tipo,
            cantidad=cantidad,
            usuario_id=current_user.id,
            motivo=form.motivo.data,
            referencia=form.referencia.data,
        )
        db.session.commit()
        logger.info("Movimiento registrado: %s x%d en %s", tipo, cantidad, item.nombre)
        flash(f"{'Entrada' if tipo == 'entrada' else 'Salida' if tipo == 'salida' else 'Ajuste'} registrada", "success")
        return redirect(url_for("inventario.ver", id=item.id))
    return render_template("inventario/movimiento.html", form=form, item=item)


@inventario_bp.route("/alertas")
@login_required
def alertas() -> Any:
    stock_bajo = (
        Inventario.query
        .filter(Inventario.cantidad <= Inventario.stock_minimo)
        .order_by(Inventario.cantidad.asc())
        .all()
    )
    stock_critico = (
        Inventario.query
        .filter(Inventario.cantidad <= Inventario.stock_critico, Inventario.stock_critico > 0)
        .order_by(Inventario.cantidad.asc())
        .all()
    )
    sin_stock = (
        Inventario.query
        .filter(Inventario.cantidad == 0)
        .order_by(Inventario.nombre)
        .all()
    )
    return render_template(
        "inventario/alertas.html",
        stock_bajo=stock_bajo,
        stock_critico=stock_critico,
        sin_stock=sin_stock,
    )


@inventario_bp.route("/categorias")
@login_required
def listar_categorias() -> Any:
    categorias = CategoriaInventario.query.order_by(CategoriaInventario.nombre).all()
    return render_template("inventario/categorias.html", categorias=categorias)


@inventario_bp.route("/categorias/crear", methods=["GET", "POST"])
@login_required
def crear_categoria() -> Any:
    form = CategoriaInventarioForm()
    if form.validate_on_submit():
        cat = CategoriaInventario(
            nombre=form.nombre.data,
            descripcion=form.descripcion.data,
            padre_id=form.padre_id.data or None,
        )
        db.session.add(cat)
        db.session.commit()
        logger.info("Categoría creada: %s", cat.nombre)
        flash("Categoría creada", "success")
        return redirect(url_for("inventario.listar_categorias"))
    return render_template("inventario/categoria_form.html", form=form)


@inventario_bp.route("/categorias/editar/<int:id>", methods=["GET", "POST"])
@login_required
def editar_categoria(id: int) -> Any:
    cat = CategoriaInventario.query.get_or_404(id)
    form = CategoriaInventarioForm(obj=cat)
    if form.validate_on_submit():
        cat.nombre = form.nombre.data
        cat.descripcion = form.descripcion.data
        cat.padre_id = form.padre_id.data or None
        db.session.commit()
        logger.info("Categoría actualizada: %s", cat.nombre)
        flash("Categoría actualizada", "success")
        return redirect(url_for("inventario.listar_categorias"))
    return render_template("inventario/categoria_form.html", form=form, cat=cat)


@inventario_bp.route("/categorias/eliminar/<int:id>")
@login_required
def eliminar_categoria(id: int) -> Any:
    cat = CategoriaInventario.query.get_or_404(id)
    items_asociados = Inventario.query.filter(Inventario.categoria_id == id).count()
    if items_asociados > 0:
        flash(f"No se puede eliminar: {items_asociados} producto(s) usan esta categoría", "danger")
        return redirect(url_for("inventario.listar_categorias"))
    CategoriaInventario.query.filter(CategoriaInventario.padre_id == id).update(
        {CategoriaInventario.padre_id: None}
    )
    db.session.delete(cat)
    db.session.commit()
    logger.info("Categoría eliminada: %s", cat.nombre)
    flash("Categoría eliminada", "success")
    return redirect(url_for("inventario.listar_categorias"))
