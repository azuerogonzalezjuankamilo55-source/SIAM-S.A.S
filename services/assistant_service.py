import logging
import re
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func

from database.db import db
from models.cliente import Cliente
from models.vehiculo import Vehiculo
from models.factura import Factura, FacturaDetalle
from models.inventario import Inventario
from models.servicio import Servicio
from models.mecanico import Mecanico
from models.orden_trabajo import OrdenTrabajo, ESTADOS_OT

logger = logging.getLogger("siam.assistant_service")


class AssistantService:

    @staticmethod
    def process_message(message: str) -> dict:
        msg_lower = message.lower().strip()
        logger.debug("Procesando mensaje: %s", msg_lower)

        intent, entities = AssistantService._classify_intent(msg_lower)

        if intent == "saludo":
            return AssistantService._handle_saludo()
        elif intent == "buscar_cliente":
            return AssistantService._buscar_cliente(entities)
        elif intent == "buscar_vehiculo":
            return AssistantService._buscar_vehiculo(entities)
        elif intent == "buscar_factura":
            return AssistantService._buscar_factura(entities)
        elif intent == "consultar_inventario":
            return AssistantService._consultar_inventario(entities)
        elif intent == "recomendar_mantenimiento":
            return AssistantService._recomendar_mantenimiento(entities)
        elif intent == "pregunta_sistema":
            return AssistantService._responder_pregunta(entities)
        elif intent == "contar_clientes":
            return AssistantService._contar_clientes()
        elif intent == "contar_vehiculos":
            return AssistantService._contar_vehiculos()
        elif intent == "contar_facturas":
            return AssistantService._contar_facturas()
        elif intent == "contar_ot":
            return AssistantService._contar_ot()
        elif intent == "stock_bajo":
            return AssistantService._stock_bajo()
        elif intent == "servicios_disponibles":
            return AssistantService._servicios_disponibles()
        elif intent == "ingresos_hoy":
            return AssistantService._ingresos_hoy()
        elif intent == "ayuda":
            return AssistantService._ayuda()
        else:
            return AssistantService._no_entiendo()

    @staticmethod
    def _classify_intent(msg: str) -> tuple:
        entities = {}

        patterns = [
            ("saludo", r"\b(hola|buenas|saludos|buen[oa]s|hey|qué tal|que tal)\b"),
            ("ayuda", r"\b(ayuda|help|qué puedes|que puedes|qué haces|que haces|funciones|comandos)\b"),
            ("buscar_cliente", r"\b(cliente|clientes|dueño|dueña|propietario)\b"),
            ("buscar_vehiculo", r"\b(veh[ií]culo|auto|carro|moto|placa|marca|modelo)\b"),
            ("buscar_factura", r"\b(factura|facturas|cuenta|recibo|pago)\b"),
            ("consultar_inventario", r"\b(inventario|stock|producto|productos|repuesto|pieza|existencia)\b"),
            ("recomendar_mantenimiento", r"\b(mantenimiento|revisi[oó]n|cambio|servicio|cada cu[áa]nto|cada cuanto|recomendar)\b"),
            ("stock_bajo", r"\b(stock bajo|agotado|sin stock|por agotar|inventario bajo|faltante)\b"),
            ("servicios_disponibles", r"\b(servicios|qu[eé] ofrecen|qu[eé] hacen|qu[eé] servicios|listado de servicios|tipos de servicio)\b"),
            ("ingresos_hoy", r"\b(ingresos? (de )?hoy|ganancia del d[ií]a|ventas de hoy|facturado hoy)\b"),
            ("contar_clientes", r"\b(cu[áa]ntos clientes|total clientes|n[uú]mero de clientes|clientes registrados)\b"),
            ("contar_vehiculos", r"\b(cu[áa]ntos veh[ií]culos|total veh[ií]culos|veh[ií]culos registrados|autos registrados)\b"),
            ("contar_facturas", r"\b(cu[áa]ntas facturas|total facturas|facturas emitidas|facturas registradas)\b"),
            ("contar_ot", r"\b(cu[áa]ntas o[td]|(o[td]|orden(es)? de trabajo) (activas|pendientes|en proceso|abiertas)|total (de )?ordenes)\b"),
        ]

        best_intent = None

        for intent_name, pattern in patterns:
            if re.search(pattern, msg):
                best_intent = intent_name
                break

        if best_intent in ("buscar_cliente", "buscar_vehiculo", "buscar_factura", "consultar_inventario", "recomendar_mantenimiento"):
            search_term = AssistantService._extract_search_term(msg, best_intent)
            if search_term:
                entities["query"] = search_term
            else:
                if best_intent in ("buscar_cliente", "buscar_vehiculo", "buscar_factura"):
                    all_items = AssistantService._list_all_for_intent(best_intent)
                    if all_items:
                        entities["list_all"] = all_items

        if best_intent is None:
            best_intent = "pregunta_sistema"
            entities["query"] = msg

        return best_intent, entities

    @staticmethod
    def _extract_search_term(msg: str, intent: str) -> str | None:
        stop_words = [
            "busca", "buscar", "encuentra", "dame", "muestra", "listar",
            "el", "la", "los", "las", "un", "una", "del", "de",
            "cliente", "clientes", "vehiculo", "vehículo", "vehiculos", "vehículos",
            "auto", "carro", "moto", "factura", "facturas",
            "inventario", "producto", "productos", "repuesto", "pieza",
            "informacion", "información", "datos", "detalle",
            "que", "qué", "cual", "cuál", "como", "cómo",
            "por", "para", "con", "sin", "sobre",
        ]

        cleaned = msg
        for word in stop_words:
            cleaned = re.sub(r'\b' + re.escape(word) + r'\b', ' ', cleaned)

        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned if len(cleaned) > 2 else None

    @staticmethod
    def _list_all_for_intent(intent: str) -> list[dict] | None:
        if intent == "buscar_cliente":
            clientes = Cliente.query.order_by(Cliente.nombre).limit(20).all()
            return [{"id": c.id, "nombre": c.nombre, "telefono": c.telefono or "—", "cedula": c.cedula or "—"} for c in clientes]
        elif intent == "buscar_vehiculo":
            vehiculos = Vehiculo.query.order_by(Vehiculo.placa).limit(20).all()
            return [{"id": v.id, "placa": v.placa, "marca": v.marca, "modelo": v.modelo, "anio": v.anio or "—"} for v in vehiculos]
        elif intent == "buscar_factura":
            facturas = Factura.query.order_by(Factura.created_at.desc()).limit(20).all()
            return [{"id": f.id, "numero": f.numero, "total": float(f.total), "estado": f.estado, "fecha": f.created_at.strftime("%Y-%m-%d")} for f in facturas]
        return None

    @staticmethod
    def _format_lista(items: list[dict], titulo: str, fields: list[tuple]) -> str:
        if not items:
            return f"No hay {titulo.lower()} registrados."

        lines = [f"**{titulo}** (mostrando {len(items)}):\n"]
        for item in items:
            parts = []
            for key, label in fields:
                val = item.get(key, "—")
                parts.append(f"{label}: {val}")
            lines.append("  • " + " | ".join(parts))
        return "\n".join(lines)

    @staticmethod
    def _handle_saludo() -> dict:
        return {
            "text": (
                "¡Hola! Soy el asistente virtual de SIAM. Puedo ayudarte con:\n\n"
                "• 🔍 **Buscar** clientes, vehículos, facturas e inventario\n"
                "• 📋 **Listar** registros del sistema\n"
                "• 🔧 **Recomendar** mantenimientos según el vehículo\n"
                "• 📊 **Responder** preguntas sobre el taller\n\n"
                "¿En qué puedo ayudarte?"
            ),
            "tipo": "texto",
        }

    @staticmethod
    def _ayuda() -> dict:
        return {
            "text": (
                "**Comandos útiles:**\n\n"
                "🔍 `Buscar cliente [nombre/cedula]`\n"
                "🔍 `Buscar vehículo [placa/marca]`\n"
                "🔍 `Buscar factura [número]`\n"
                "📦 `Consultar inventario [producto]`\n"
                "🔧 `Recomendar mantenimiento para [marca] [modelo] [año]`\n"
                "📊 `¿Cuántos clientes hay?`\n"
                "📊 `¿Cuáles son los servicios?`\n"
                "⚠️ `Stock bajo`\n"
                "💰 `Ingresos hoy`\n\n"
                "También puedes preguntar en lenguaje natural. ¡Inténtalo!"
            ),
            "tipo": "texto",
        }

    @staticmethod
    def _buscar_cliente(entities: dict) -> dict:
        query = entities.get("query")

        if "list_all" in entities:
            items = entities["list_all"]
            text = AssistantService._format_lista(
                items, "Clientes Registrados",
                [("nombre", "Nombre"), ("telefono", "Tel"), ("cedula", "Cédula")]
            )
            return {"text": text, "tipo": "lista_clientes", "items": items}

        if not query:
            return {"text": "¿Qué cliente deseas buscar? Puedes darme su nombre, cédula o teléfono.", "tipo": "texto"}

        clientes = Cliente.query.filter(
            db.or_(
                Cliente.nombre.ilike(f"%{query}%"),
                Cliente.cedula.ilike(f"%{query}%"),
                Cliente.telefono.ilike(f"%{query}%"),
            )
        ).limit(5).all()

        if not clientes:
            return {"text": f"No encontré clientes con «{query}».", "tipo": "texto"}

        items = []
        lines = [f"**Clientes encontrados para «{query}»:**\n"]
        for c in clientes:
            items.append({"id": c.id, "nombre": c.nombre, "telefono": c.telefono or "—", "cedula": c.cedula or "—", "correo": c.correo or "—"})
            vehiculos = Vehiculo.query.filter_by(cliente_id=c.id).all()
            v_text = ", ".join([f"{v.placa} ({v.marca} {v.modelo})" for v in vehiculos]) or "Ninguno"
            lines.append(f"  • **{c.nombre}** | Tel: {c.telefono or '—'} | Cédula: {c.cedula or '—'}")
            lines.append(f"    Vehículos: {v_text}")

        return {"text": "\n".join(lines), "tipo": "lista_clientes", "items": items}

    @staticmethod
    def _buscar_vehiculo(entities: dict) -> dict:
        query = entities.get("query")

        if "list_all" in entities:
            items = entities["list_all"]
            text = AssistantService._format_lista(
                items, "Vehículos Registrados",
                [("placa", "Placa"), ("marca", "Marca"), ("modelo", "Modelo"), ("anio", "Año")]
            )
            return {"text": text, "tipo": "lista_vehiculos", "items": items}

        if not query:
            return {"text": "¿Qué vehículo buscas? Dame la placa, marca o modelo.", "tipo": "texto"}

        vehiculos = Vehiculo.query.filter(
            db.or_(
                Vehiculo.placa.ilike(f"%{query}%"),
                Vehiculo.marca.ilike(f"%{query}%"),
                Vehiculo.modelo.ilike(f"%{query}%"),
            )
        ).limit(5).all()

        if not vehiculos:
            return {"text": f"No encontré vehículos con «{query}».", "tipo": "texto"}

        items = []
        lines = [f"**Vehículos encontrados para «{query}»:**\n"]
        for v in vehiculos:
            cliente = Cliente.query.get(v.cliente_id)
            nombre_cliente = cliente.nombre if cliente else "—"
            items.append({"id": v.id, "placa": v.placa, "marca": v.marca, "modelo": v.modelo, "anio": v.anio or "—", "cliente": nombre_cliente})
            lines.append(f"  • **{v.placa}** — {v.marca} {v.modelo} ({v.anio or 'Año?'})")
            lines.append(f"    Dueño: {nombre_cliente} | VIN: {v.vin or '—'} | Color: {v.color or '—'}")

        return {"text": "\n".join(lines), "tipo": "lista_vehiculos", "items": items}

    @staticmethod
    def _buscar_factura(entities: dict) -> dict:
        query = entities.get("query")

        if "list_all" in entities:
            items = entities["list_all"]
            text = AssistantService._format_lista(
                items, "Últimas Facturas",
                [("numero", "N°"), ("total", "Total"), ("estado", "Estado"), ("fecha", "Fecha")]
            )
            return {"text": text, "tipo": "lista_facturas", "items": items}

        if not query:
            return {"text": "¿Qué factura buscas? Puedes darme el número o el nombre del cliente.", "tipo": "texto"}

        facturas = Factura.query.filter(
            db.or_(
                Factura.numero.ilike(f"%{query}%"),
            )
        ).limit(5).all()

        if not facturas:
            facturas = Factura.query.join(Cliente, Cliente.id == Factura.cita_id).filter(
                Cliente.nombre.ilike(f"%{query}%")
            ).limit(5).all()

        if not facturas:
            return {"text": f"No encontré facturas con «{query}».", "tipo": "texto"}

        items = []
        lines = [f"**Facturas encontradas para «{query}»:**\n"]
        for f in facturas:
            items.append({"id": f.id, "numero": f.numero, "total": float(f.total), "estado": f.estado, "fecha": f.created_at.strftime("%Y-%m-%d")})
            lines.append(f"  • **{f.numero}** | ${float(f.total):,.0f} | *{f.estado.title()}* | {f.created_at.strftime('%d/%m/%Y')}")

        return {"text": "\n".join(lines), "tipo": "lista_facturas", "items": items}

    @staticmethod
    def _consultar_inventario(entities: dict) -> dict:
        query = entities.get("query")

        if not query:
            items = Inventario.query.order_by(Inventario.nombre).limit(15).all()
            if not items:
                return {"text": "El inventario está vacío.", "tipo": "texto"}
            lines = [f"**Inventario** (mostrando {len(items)} productos):\n"]
            for i in items:
                estado = "⚠️" if i.stock_bajo else "✅"
                lines.append(f"  {estado} **{i.nombre}** — Stock: {i.cantidad} | Precio: ${float(i.precio_venta or 0):,.0f}")
            return {"text": "\n".join(lines), "tipo": "texto"}

        productos = Inventario.query.filter(
            db.or_(
                Inventario.nombre.ilike(f"%{query}%"),
                Inventario.sku.ilike(f"%{query}%"),
                Inventario.descripcion.ilike(f"%{query}%"),
            )
        ).limit(5).all()

        if not productos:
            return {"text": f"No encontré productos con «{query}» en el inventario.", "tipo": "texto"}

        lines = [f"**Productos encontrados para «{query}»:**\n"]
        for p in productos:
            estado = "⚠️ STOCK BAJO" if p.stock_bajo else "✅ Stock OK"
            lines.append(f"  • **{p.nombre}** (SKU: {p.sku or '—'})")
            lines.append(f"    Cantidad: {p.cantidad} | Mínimo: {p.stock_minimo} | {estado}")
            lines.append(f"    Precio Venta: ${float(p.precio_venta or 0):,.0f} | Ubicación: {p.ubicacion or '—'}")

        return {"text": "\n".join(lines), "tipo": "texto"}

    @staticmethod
    def _recomendar_mantenimiento(entities: dict) -> dict:
        query = entities.get("query", "")

        marca = modelo = None
        anio = None

        marcas = re.findall(r'\b(chevrolet|renault|mazda|toyota|hyundai|kia|nissan|ford|volkswagen|fiat|bmw|mercedes|audi|susuki|mitsubishi|honda)\b', query.lower())
        if marcas:
            marca = marcas[0].title()

        anios = re.findall(r'\b(19\d{2}|20\d{2})\b', query)
        if anios:
            anio = int(anios[0])

        if not marca:
            vehiculos = Vehiculo.query.filter(
                db.or_(
                    Vehiculo.marca.ilike(f"%{query}%"),
                    Vehiculo.placa.ilike(f"%{query}%"),
                )
            ).limit(3).all()

            if vehiculos:
                v = vehiculos[0]
                marca = v.marca
                modelo = v.modelo
                anio = v.anio
            else:
                return {
                    "text": (
                        "Dime el vehículo para recomendarte su mantenimiento. "
                        "Ej: *«Recomienda mantenimiento para Toyota Corolla 2020»* "
                        "o *«Mantenimiento para ABC-123»*"
                    ),
                    "tipo": "texto",
                }

        if not modelo:
            rest = query
            if marca:
                rest = rest.lower().replace(marca.lower(), "").strip()
            words = rest.split()
            if words and not anio:
                modelo = " ".join([w for w in words if not re.match(r'\d+', w)])
            elif words:
                modelo = " ".join([w for w in words if not re.match(r'\d{4}', w)])

        recomendaciones = AssistantService._generar_recomendaciones(marca, modelo, anio)
        lines = [f"**Plan de Mantenimiento para {marca} {modelo or ''} {'(' + str(anio) + ')' if anio else ''}**\n"]
        lines.extend(recomendaciones)
        lines.append("\n💡 *¿Deseas agendar una cita para alguno de estos servicios?*")

        return {"text": "\n".join(lines), "tipo": "texto"}

    @staticmethod
    def _generar_recomendaciones(marca: str | None, modelo: str | None, anio: int | None) -> list:
        hoy = date.today()
        edad = hoy.year - anio if anio else None

        recomendaciones = [
            "🛢️ **Cambio de aceite y filtro** — Cada 5,000 km o 6 meses",
            "🔧 **Revisión de frenos** (pastillas, discos, líquido) — Cada 10,000 km",
        ]

        if edad is not None:
            if edad >= 1:
                recomendaciones.append("🔄 **Rotación de neumáticos** — Cada 10,000 km")
                recomendaciones.append("💨 **Filtro de aire** — Cada 15,000 km")
            if edad >= 2:
                recomendaciones.append("⚡ **Bujías y cables** — Cada 20,000 km")
                recomendaciones.append("🧊 **Líquido refrigerante** — Revisión anual")
            if edad >= 4:
                recomendaciones.append("🔩 **Correa de distribución** — Cada 60,000 km o 4 años")
                recomendaciones.append("🔋 **Batería** — Prueba de carga recomendada")
            if edad >= 6:
                recomendaciones.append("🛞 **Suspensión y amortiguadores** — Revisión general")
                recomendaciones.append("🌡️ **Termostato y bomba de agua** — Verificar estado")
            if edad >= 8:
                recomendaciones.append("⚠️ **Revisión integral recomendada** — El vehículo tiene más de 8 años")
        else:
            recomendaciones.extend([
                "🔄 **Rotación de neumáticos** — Cada 10,000 km",
                "💨 **Filtro de aire** — Cada 15,000 km",
                "⚡ **Bujías** — Cada 20,000 km",
            ])

        servicios = Servicio.query.filter(Servicio.activo == True).order_by(Servicio.nombre).all()
        if servicios:
            recomendaciones.append(f"\n📋 **Servicios disponibles en el taller ({len(servicios)}):**")
            for s in servicios[:5]:
                precio = f" — ${float(s.precio_estimado):,.0f}" if s.precio_estimado else ""
                recomendaciones.append(f"   • {s.nombre}{precio}")

        return recomendaciones

    @staticmethod
    def _responder_pregunta(entities: dict) -> dict:
        query = entities.get("query", "")

        respuestas = {
            r"\bhorarios?\b": "Nuestro horario de atención es **lunes a viernes de 7:00 AM a 6:00 PM** y **sábados de 8:00 AM a 1:00 PM**.",
            r"\bd[ií]as?\s+ (de )?entrega|tiempo.*reparaci[oó]n|demora": (
                "El tiempo de reparación depende del servicio. Un mantenimiento básico toma 1-2 horas. "
                "Trabajos mayores como motor o transmisión pueden tomar 2-5 días hábiles."
            ),
            r"\bgarant[ií]a": "Ofrecemos **3 meses de garantía** en servicios de reparación y **6 meses** en trabajos de motor y transmisión.",
            r"\bformas?\s* de pago|m[eé]todos?\s* de pago|pagos?\b": (
                "Aceptamos: **Efectivo, Tarjeta Débito, Tarjeta Crédito, Transferencia, PSE, Nequi y Daviplata**."
            ),
            r"\bdomicilio|recojan|a domicilio": "Sí, ofrecemos servicio de **recojo y entrega a domicilio** dentro del área urbana. Consulta disponibilidad.",
            r"\bprecios?\b|cu[aá]nto cuesta|cu[aá]nto vale|tarifas": (
                "Los precios varían según el servicio. Puedes consultar nuestros servicios en el módulo de **Servicios** "
                "o pedirme que te los muestre con *«lista de servicios»*."
            ),
            r"\bc[oó]mo\s+ (llegar|ubicaci[oó]n|d[ií]recci[oó]n|dónde|donde|encuentran)\b": (
                "Puedes consultar nuestra dirección en la **Configuración del Taller** (módulo Facturas > Configuración)."
            ),
            r"\bqu[eé] puedes hacer|funciones|capacidades": (
                "Puedo:\n"
                "• Buscar clientes, vehículos y facturas\n"
                "• Consultar el inventario\n"
                "• Recomendar mantenimientos según el vehículo\n"
                "• Mostrar estadísticas del taller\n"
                "• Responder preguntas sobre servicios y políticas\n\n"
                "¿Qué necesitas?"
            ),
            r"\bqui[eé]n eres|como te llamas|nombre": (
                "Soy el **Asistente IA de SIAM**, tu ayudante virtual para la gestión del taller. "
                "Estoy aquí para facilitar tu trabajo. ¿En qué puedo ayudarte?"
            ),
        }

        for pattern, respuesta in respuestas.items():
            if re.search(pattern, query.lower()):
                return {"text": respuesta, "tipo": "texto"}

        if re.search(r"\b(gracias|thanks|ok)\b", query.lower()):
            return {"text": "¡Con gusto! Siempre que necesites algo, aquí estoy. 😊", "tipo": "texto"}

        return {
            "text": (
                "No estoy seguro de cómo responder a eso. Puedes preguntarme:\n\n"
                "• *«Buscar cliente Juan»*\n"
                "• *«Recomienda mantenimiento para un Toyota 2020»*\n"
                "• *«¿Cuántos clientes hay?»*\n"
                "• *«Stock bajo»*\n"
                "• *«Ayuda»* para ver más opciones"
            ),
            "tipo": "texto",
        }

    @staticmethod
    def _contar_clientes() -> dict:
        total = Cliente.query.count()
        este_mes = Cliente.query.filter(
            func.extract("month", Cliente.created_at) == date.today().month,
            func.extract("year", Cliente.created_at) == date.today().year,
        ).count()
        return {
            "text": f"📊 **Clientes:**\n  • Total: **{total}**\n  • Registrados este mes: **{este_mes}**",
            "tipo": "texto",
        }

    @staticmethod
    def _contar_vehiculos() -> dict:
        total = Vehiculo.query.count()
        return {
            "text": f"🚗 **Vehículos registrados:** **{total}** en total.",
            "tipo": "texto",
        }

    @staticmethod
    def _contar_facturas() -> dict:
        total = Factura.query.count()
        pendientes = Factura.query.filter(Factura.estado == "pendiente").count()
        pagadas = Factura.query.filter(Factura.estado == "pagado").count()
        return {
            "text": f"📄 **Facturas:**\n  • Total: **{total}**\n  • Pendientes: **{pendientes}**\n  • Pagadas: **{pagadas}**",
            "tipo": "texto",
        }

    @staticmethod
    def _contar_ot() -> dict:
        total = OrdenTrabajo.query.count()
        activas = OrdenTrabajo.query.filter(
            OrdenTrabajo.estado.in_(["recibido", "diagnostico", "esperando_repuestos", "en_reparacion"])
        ).count()
        listas = OrdenTrabajo.query.filter(OrdenTrabajo.estado == "listo_entrega").count()
        entregadas = OrdenTrabajo.query.filter(OrdenTrabajo.estado == "entregado").count()
        return {
            "text": f"🔧 **Órdenes de Trabajo:**\n  • Total: **{total}**\n  • Activas: **{activas}**\n  • Listas para entrega: **{listas}**\n  • Entregadas: **{entregadas}**",
            "tipo": "texto",
        }

    @staticmethod
    def _stock_bajo() -> dict:
        items = Inventario.query.filter(
            Inventario.cantidad <= Inventario.stock_minimo
        ).order_by(Inventario.cantidad.asc()).limit(10).all()

        if not items:
            return {"text": "✅ No hay productos con stock bajo. ¡Todo en orden!", "tipo": "texto"}

        lines = [f"⚠️ **Productos con stock bajo** ({len(items)}):\n"]
        for i in items:
            urgente = "🚨" if i.cantidad == 0 else "⚠️"
            lines.append(f"  {urgente} **{i.nombre}** — Stock: {i.cantidad} (mínimo: {i.stock_minimo})")
            if i.proveedor:
                lines.append(f"    Proveedor: {i.proveedor}")

        return {"text": "\n".join(lines), "tipo": "texto"}

    @staticmethod
    def _servicios_disponibles() -> dict:
        servicios = Servicio.query.filter(Servicio.activo == True).order_by(Servicio.nombre).all()
        if not servicios:
            return {"text": "No hay servicios registrados actualmente.", "tipo": "texto"}

        lines = [f"📋 **Servicios disponibles** ({len(servicios)} en total):\n"]
        for s in servicios:
            precio = f"${float(s.precio_estimado):,.0f}" if s.precio_estimado else "Consultar"
            duracion = f"{s.duracion_estimada} min" if s.duracion_estimada else "—"
            lines.append(f"  • **{s.nombre}** — {precio} | {duracion}")
            if s.descripcion:
                lines.append(f"    {s.descripcion[:60]}{'...' if len(s.descripcion) > 60 else ''}")

        return {"text": "\n".join(lines), "tipo": "texto"}

    @staticmethod
    def _ingresos_hoy() -> dict:
        total = db.session.query(func.coalesce(func.sum(Factura.total), 0)).filter(
            Factura.estado.in_(["pagado", "parcial"]),
            func.date(Factura.created_at) == date.today(),
        ).scalar() or 0

        total_mes = db.session.query(func.coalesce(func.sum(Factura.total), 0)).filter(
            Factura.estado.in_(["pagado", "parcial"]),
            func.extract("month", Factura.created_at) == date.today().month,
            func.extract("year", Factura.created_at) == date.today().year,
        ).scalar() or 0

        return {
            "text": f"💰 **Ingresos:**\n  • Hoy: **${float(total):,.0f}**\n  • Este mes: **${float(total_mes):,.0f}**",
            "tipo": "texto",
        }

    @staticmethod
    def _no_entiendo() -> dict:
        return {
            "text": (
                "No entendí tu mensaje. Puedes pedir **ayuda** para ver mis funciones "
                "o simplemente preguntar en lenguaje natural."
            ),
            "tipo": "texto",
        }
