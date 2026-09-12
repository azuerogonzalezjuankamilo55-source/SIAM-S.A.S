import logging
from datetime import date
from typing import Any

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from flask_wtf.csrf import validate_csrf

from models.inventario import Inventario
from models.categoria_inventario import CategoriaInventario
from models.movimiento_inventario import MovimientoInventario, TIPOS_MOVIMIENTO
from models.recordatorio import Recordatorio
from database.db import db
from forms import InventarioForm, MovimientoInventarioForm, CategoriaInventarioForm
from database.commit import safe_commit, json_success, json_error
from services.inventario_service import InventarioService
from decorators import staff_blueprint_guard

logger = logging.getLogger("siam.routes.inventario")
inventario_bp = Blueprint("inventario", __name__, url_prefix="/inventario")
inventario_bp.before_request(staff_blueprint_guard)


@inventario_bp.route("/")
@login_required
def listar() -> Any:
    categoria_id = request.args.get("categoria_id", type=int)
    _sb = (request.args.get("stock_bajo") or "").strip().lower()
    stock_bajo = _sb in ("1", "true", "yes", "on", "si")
    incluir_bajas = request.args.get("incluir_bajas") == "1"
    q = Inventario.query

    if not incluir_bajas:
        q = q.filter(Inventario.activo.is_(True))
    if categoria_id:
        q = q.filter(Inventario.categoria_id == categoria_id)
    if stock_bajo:
        q = q.filter(Inventario.cantidad <= Inventario.stock_minimo)

    items = q.order_by(Inventario.nombre).all()
    categorias = CategoriaInventario.query.order_by(CategoriaInventario.nombre).all()
    valorizacion = InventarioService.valorizacion()
    return render_template(
        "inventario/listar.html",
        items=items,
        categorias=categorias,
        valorizacion=valorizacion,
    )


@inventario_bp.route("/crear", methods=["GET", "POST"])
@login_required
def crear() -> Any:
    form = InventarioForm()
    if form.validate_on_submit():
        try:
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
            safe_commit()
            logger.info("Producto creado: %s (SKU=%s)", item.nombre, item.sku)
            if request.is_json:
                return json_success(message="Producto agregado al inventario.")
            flash("Producto agregado al inventario", "success")
            return redirect(url_for("inventario.listar"))
        except Exception as e:
            db.session.rollback()
            if request.is_json:
                return json_error(message=str(e))
            flash(str(e), "danger")
    return render_template("inventario/form.html", form=form)


@inventario_bp.route("/ver/<int:id>")
@login_required
def ver(id: int) -> Any:
    item = db.get_or_404(Inventario, id)
    movimientos = item.movimientos
    return render_template("inventario/ver.html", item=item, movimientos=movimientos)


@inventario_bp.route("/editar/<int:id>", methods=["GET", "POST"])
@login_required
def editar(id: int) -> Any:
    item = db.get_or_404(Inventario, id)
    form = InventarioForm(obj=item)
    if form.validate_on_submit():
        try:
            cantidad_anterior = item.cantidad
            form.populate_obj(item)
            if item.cantidad != cantidad_anterior:
                item.registrar_movimiento(
                    tipo="ajuste",
                    cantidad=item.cantidad,
                    usuario_id=current_user.id,
                    motivo="Ajuste por edición de producto",
                )
            safe_commit()
            logger.info("Producto actualizado: %s", item.nombre)
            if request.is_json:
                return json_success(message="Producto actualizado.")
            flash("Producto actualizado", "success")
            return redirect(url_for("inventario.listar"))
        except Exception as e:
            db.session.rollback()
            if request.is_json:
                return json_error(message=str(e))
            flash(str(e), "danger")
    return render_template("inventario/form.html", form=form, item=item)


@inventario_bp.route("/baja/<int:id>", methods=["POST"])
@login_required
def baja(id: int) -> Any:
    item = db.get_or_404(Inventario, id)
    motivo = request.form.get("motivo") or ""
    try:
        InventarioService.dar_baja(item, motivo, current_user.id)
        logger.info("Producto dado de baja: %s", item.nombre)
        if request.is_json:
            return json_success(message="Producto dado de baja.")
        flash("Producto dado de baja", "success")
        return redirect(url_for("inventario.ver", id=item.id))
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return json_error(message=str(e))
        flash(str(e), "danger")
        return redirect(url_for("inventario.ver", id=item.id))


@inventario_bp.route("/restaurar/<int:id>", methods=["POST"])
@login_required
def restaurar(id: int) -> Any:
    item = db.get_or_404(Inventario, id)
    try:
        InventarioService.restaurar(item, current_user.id)
        logger.info("Producto restaurado: %s", item.nombre)
        if request.is_json:
            return json_success(message="Producto restaurado.")
        flash("Producto restaurado", "success")
        return redirect(url_for("inventario.ver", id=item.id))
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return json_error(message=str(e))
        flash(str(e), "danger")
        return redirect(url_for("inventario.ver", id=item.id))


@inventario_bp.route("/kardex")
@login_required
def kardex() -> Any:
    inventario_id = request.args.get("inventario_id", type=int)
    tipo = request.args.get("tipo") or ""
    fecha_desde_raw = request.args.get("fecha_desde") or ""
    fecha_hasta_raw = request.args.get("fecha_hasta") or ""
    if tipo not in TIPOS_MOVIMIENTO:
        tipo = ""
    try:
        fecha_desde = date.fromisoformat(fecha_desde_raw) if fecha_desde_raw else None
    except ValueError:
        fecha_desde = None
    try:
        fecha_hasta = date.fromisoformat(fecha_hasta_raw) if fecha_hasta_raw else None
    except ValueError:
        fecha_hasta = None

    movimientos = InventarioService.get_kardex(
        inventario_id=inventario_id,
        tipo=tipo or None,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
    )
    productos = Inventario.query.filter_by(activo=True).order_by(Inventario.nombre).all()
    return render_template(
        "inventario/kardex.html",
        movimientos=movimientos,
        productos=productos,
        filtro_inventario=inventario_id,
        filtro_tipo=tipo,
        filtro_desde=fecha_desde_raw,
        filtro_hasta=fecha_hasta_raw,
    )


@inventario_bp.route("/movimiento/<int:id>", methods=["GET", "POST"])
@login_required
def movimiento(id: int) -> Any:
    item = db.get_or_404(Inventario, id)
    form = MovimientoInventarioForm()
    if form.validate_on_submit():
        try:
            tipo = form.tipo.data
            cantidad = form.cantidad.data
            InventarioService.registrar_movimiento(
                item=item,
                tipo=tipo,
                cantidad=cantidad,
                usuario_id=current_user.id,
                motivo=form.motivo.data,
                referencia=form.referencia.data,
            )
            safe_commit()
            logger.info("Movimiento registrado: %s x%d en %s", tipo, cantidad, item.nombre)
            if request.is_json:
                return json_success(message=f"{'Entrada' if tipo == 'entrada' else 'Salida' if tipo == 'salida' else 'Ajuste'} registrada.")
            flash(f"{'Entrada' if tipo == 'entrada' else 'Salida' if tipo == 'salida' else 'Ajuste'} registrada", "success")
            return redirect(url_for("inventario.ver", id=item.id))
        except Exception as e:
            db.session.rollback()
            if request.is_json:
                return json_error(message=str(e))
            flash(str(e), "danger")
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
        .filter(Inventario.cantidad == 0, Inventario.activo.is_(True))
        .order_by(Inventario.nombre)
        .all()
    )
    reposiciones_pendientes = (
        Recordatorio.query
        .filter_by(tipo="reposicion", estado="pendiente")
        .count()
    )
    return render_template(
        "inventario/alertas.html",
        stock_bajo=stock_bajo,
        stock_critico=stock_critico,
        sin_stock=sin_stock,
        reposiciones_pendientes=reposiciones_pendientes,
    )


@inventario_bp.route("/alertas/generar-recordatorios", methods=["POST"])
@login_required
def generar_alertas() -> Any:
    try:
        creados = InventarioService.generar_alertas_reposicion()
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return json_error(message=str(e))
        flash(str(e), "danger")
        return redirect(url_for("inventario.alertas"))
    if request.is_json:
        return json_success(message=f"{creados} alertas de reposición generadas.")
    flash(f"{creados} alertas de reposición generadas.", "success" if creados else "info")
    return redirect(url_for("inventario.alertas"))


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
        try:
            cat = CategoriaInventario(
                nombre=form.nombre.data,
                descripcion=form.descripcion.data,
                padre_id=form.padre_id.data or None,
            )
            db.session.add(cat)
            safe_commit()
            logger.info("Categoría creada: %s", cat.nombre)
            if request.is_json:
                return json_success(message="Categoría creada.")
            flash("Categoría creada", "success")
            return redirect(url_for("inventario.listar_categorias"))
        except Exception as e:
            db.session.rollback()
            if request.is_json:
                return json_error(message=str(e))
            flash(str(e), "danger")
    return render_template("inventario/categoria_form.html", form=form)


@inventario_bp.route("/categorias/editar/<int:id>", methods=["GET", "POST"])
@login_required
def editar_categoria(id: int) -> Any:
    cat = db.get_or_404(CategoriaInventario, id)
    form = CategoriaInventarioForm(obj=cat)
    if form.validate_on_submit():
        try:
            cat.nombre = form.nombre.data
            cat.descripcion = form.descripcion.data
            cat.padre_id = form.padre_id.data or None
            safe_commit()
            logger.info("Categoría actualizada: %s", cat.nombre)
            if request.is_json:
                return json_success(message="Categoría actualizada.")
            flash("Categoría actualizada", "success")
            return redirect(url_for("inventario.listar_categorias"))
        except Exception as e:
            db.session.rollback()
            if request.is_json:
                return json_error(message=str(e))
            flash(str(e), "danger")
    return render_template("inventario/categoria_form.html", form=form, cat=cat)


@inventario_bp.route("/categorias/eliminar/<int:id>", methods=["POST"])
@login_required
def eliminar_categoria(id: int) -> Any:
    try:
        csrf_token = request.headers.get("X-CSRFToken") or request.form.get("csrf_token")
        if csrf_token:
            validate_csrf(csrf_token)
    except Exception:
        if request.is_json:
            return jsonify({"error": "CSRF inválido"}), 403
        flash("Error de validación. Intenta de nuevo.", "danger")
        return redirect(url_for("inventario.listar_categorias"))
    cat = db.get_or_404(CategoriaInventario, id)
    items_asociados = Inventario.query.filter(Inventario.categoria_id == id).count()
    if items_asociados > 0:
        if request.is_json:
            return json_error(message=f"No se puede eliminar: {items_asociados} producto(s) usan esta categoría")
        flash(f"No se puede eliminar: {items_asociados} producto(s) usan esta categoría", "danger")
        return redirect(url_for("inventario.listar_categorias"))
    try:
        CategoriaInventario.query.filter(CategoriaInventario.padre_id == id).update(
            {CategoriaInventario.padre_id: None}
        )
        db.session.delete(cat)
        safe_commit()
        logger.info("Categoría eliminada: %s", cat.nombre)
        if request.is_json:
            return json_success(message="Categoría eliminada.")
        flash("Categoría eliminada", "success")
        return redirect(url_for("inventario.listar_categorias"))
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return json_error(message=str(e))
        flash(str(e), "danger")
        return redirect(url_for("inventario.listar_categorias"))
