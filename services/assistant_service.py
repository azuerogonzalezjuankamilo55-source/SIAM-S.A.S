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

    INTENT_KEYWORDS = {
        "asistencia_emergencia": [
            "varado", "qued\u00e9", "tirado", "da\u00f1\u00f3", "no prende",
            "emergencia", "gr\u00faa", "auxilio", "quede", "dano", "grua",
        ],
        "asistencia_con_ubicacion": [
            "recoger", "venir", "ubicaci\u00f3n", "ubicacion", "estoy en",
        ],
        "vehiculos_carga_pesada": [
            "cami\u00f3n", "camion", "tractomula", "carga pesada", "pesado", "camiones",
        ],
        "ubicaciones": [
            "d\u00f3nde est\u00e1n", "donde estan", "d\u00f3nde quedan", "donde quedan",
            "sedes", "sucursales",
        ],
        "precios_y_pagos": [
            "precio", "tarjeta", "PSE", "Nequi", "Daviplata",
            "cotizaci\u00f3n", "cotizacion",
            "cu\u00e1nto cuesta", "cuanto cuesta",
            "qu\u00e9 m\u00e9todos de pago", "que metodos de pago",
            "m\u00e9todos de pago", "metodos de pago", "formas de pago",
        ],
        "repuestos": [
            "repuesto", "pieza", "parte", "accesorio", "para mi carro", "para mi moto",
        ],
        "saludo": [
            "hola", "buenas", "saludos", "buenos", "hey",
            "qu\u00e9 tal", "que tal",
        ],
        "ayuda": [
            "ayuda", "help", "qu\u00e9 puedes", "que puedes",
            "qu\u00e9 haces", "que haces", "funciones", "comandos",
            "qu\u00e9 puedes hacer", "que puedes hacer",
        ],
        "contar_clientes": [
            "cu\u00e1ntos clientes", "cuantos clientes",
            "total clientes", "n\u00famero de clientes", "numero de clientes",
            "clientes registrados",
        ],
        "contar_vehiculos": [
            "cu\u00e1ntos veh\u00edculos", "cuantos vehiculos",
            "total veh\u00edculos", "total vehiculos",
            "veh\u00edculos registrados", "vehiculos registrados",
            "autos registrados",
        ],
        "contar_facturas": [
            "cu\u00e1ntas facturas", "cuantas facturas",
            "total facturas", "facturas emitidas", "facturas registradas",
        ],
        "contar_ot": [
            "cu\u00e1ntas ot", "cuantas ot",
            "cu\u00e1ntas odt", "cuantas odt",
            "ot activas", "odt activas",
            "ordenes de trabajo activas", "\u00f3rdenes de trabajo activas",
            "total ordenes", "total \u00f3rdenes", "total de ordenes", "total de \u00f3rdenes",
        ],
        "ingresos_hoy": [
            "ingresos hoy", "ingreso hoy",
            "ganancia del d\u00eda", "ganancia del dia",
            "ventas de hoy", "facturado hoy",
        ],
        "servicios_disponibles": [
            "qu\u00e9 ofrecen", "que ofrecen",
            "qu\u00e9 hacen", "que hacen",
            "qu\u00e9 servicios", "que servicios",
            "listado de servicios", "tipos de servicio",
            "servicios disponibles",
        ],
        "stock_bajo": [
            "stock bajo", "agotado", "sin stock", "por agotar",
            "inventario bajo", "faltante",
        ],
        "consultar_inventario": [
            "inventario", "stock", "producto", "productos",
            "repuesto", "pieza", "existencia",
        ],
        "buscar_cliente": [
            "cliente", "clientes", "due\u00f1o", "due\u00f1a",
            "propietario", "dueno", "duena",
        ],
        "buscar_vehiculo": [
            "veh\u00edculo", "vehiculo", "veh\u00edculos", "vehiculos",
            "auto", "carro", "moto", "placa", "marca", "modelo",
        ],
        "buscar_factura": [
            "factura", "facturas", "cuenta", "recibo", "pago",
        ],
        "recomendar_mantenimiento": [
            "mantenimiento", "revisi\u00f3n", "revision",
            "cambio", "servicio",
            "cada cu\u00e1nto", "cada cuanto", "recomendar",
        ],
    }

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
        elif intent == "asistencia_emergencia":
            return AssistantService._asistencia_emergencia()
        elif intent == "precios_y_pagos":
            return AssistantService._precios_y_pagos()
        elif intent == "asistencia_con_ubicacion":
            return AssistantService._asistencia_con_ubicacion()
        elif intent == "vehiculos_carga_pesada":
            return AssistantService._vehiculos_carga_pesada()
        elif intent == "ubicaciones":
            return AssistantService._ubicaciones()
        elif intent == "repuestos":
            return AssistantService._repuestos(entities)
        else:
            return AssistantService._no_entiendo()

    @staticmethod
    def _classify_intent(msg: str) -> tuple:
        entities = {}

        for intent_name, keywords in AssistantService.INTENT_KEYWORDS.items():
            pattern = r'\b(?:' + '|'.join(re.escape(k) for k in keywords) + r')\b'
            if re.search(pattern, msg):
                if intent_name in (
                    "buscar_cliente", "buscar_vehiculo", "buscar_factura",
                    "consultar_inventario", "recomendar_mantenimiento",
                    "repuestos",
                ):
                    search_term = AssistantService._extract_search_term(msg, intent_name)
                    if search_term:
                        entities["query"] = search_term
                    else:
                        if intent_name in ("buscar_cliente", "buscar_vehiculo", "buscar_factura"):
                            all_items = AssistantService._list_all_for_intent(intent_name)
                            if all_items:
                                entities["list_all"] = all_items
                return intent_name, entities

        entities["query"] = msg
        return "pregunta_sistema", entities

    @staticmethod
    def _asistencia_emergencia() -> dict:
        return {
            "text": "Claro. Podemos ayudarte con asistencia. Puedes solicitar atenci\u00f3n de un asesor o compartir tu ubicaci\u00f3n para que podamos coordinar la asistencia.",
            "tipo": "botones",
        }

    @staticmethod
    def _precios_y_pagos() -> dict:
        return {
            "text": "Contamos con diferentes m\u00e9todos de pago, como tarjetas d\u00e9bito y cr\u00e9dito, PSE, Nequi y Daviplata. Para conocer el precio exacto de un servicio podemos ayudarte a solicitar una cotizaci\u00f3n.",
            "tipo": "botones",
        }

    @staticmethod
    def _asistencia_con_ubicacion() -> dict:
        return {
            "text": "Claro. Para poder ayudarte mejor, \u00bfpodr\u00edas compartir tu ubicaci\u00f3n?",
            "tipo": "botones",
        }

    @staticmethod
    def _vehiculos_carga_pesada() -> dict:
        return {
            "text": "S\u00ed. Podemos atender veh\u00edculos de carga pesada. Si deseas, podemos ponerte en contacto con un asesor para revisar tu caso.",
            "tipo": "botones",
        }

    @staticmethod
    def _ubicaciones() -> dict:
        return {
            "text": "Contamos con diferentes sedes. Nuestra sede principal est\u00e1 en Soacha, Cundinamarca. \u00bfQuieres ver todas nuestras sedes?",
            "tipo": "botones",
        }

    @staticmethod
    def _repuestos(entities: dict) -> dict:
        query = entities.get("query")
        if query:
            return AssistantService._consultar_inventario(entities)
        return {
            "text": "S\u00ed. Podemos ayudarte a consultar disponibilidad de repuestos para motos, autom\u00f3viles y veh\u00edculos de carga pesada. \u00bfQu\u00e9 repuesto necesitas?",
            "tipo": "botones",
        }

    @staticmethod
    def _extract_search_term(msg: str, intent: str) -> str | None:
        stop_words = [
            "busca", "buscar", "encuentra", "dame", "muestra", "listar",
            "el", "la", "los", "las", "un", "una", "del", "de",
            "cliente", "clientes", "vehiculo", "veh\u00edculo", "vehiculos", "veh\u00edculos",
            "auto", "carro", "moto", "factura", "facturas",
            "inventario", "producto", "productos", "repuesto", "pieza",
            "informacion", "informaci\u00f3n", "datos", "detalle",
            "que", "qu\u00e9", "cual", "cu\u00e1l", "como", "c\u00f3mo",
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
            return [{"id": c.id, "nombre": c.nombre, "telefono": c.telefono or "\u2014", "cedula": c.cedula or "\u2014"} for c in clientes]
        elif intent == "buscar_vehiculo":
            vehiculos = Vehiculo.query.order_by(Vehiculo.placa).limit(20).all()
            return [{"id": v.id, "placa": v.placa, "marca": v.marca, "modelo": v.modelo, "anio": v.anio or "\u2014"} for v in vehiculos]
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
                val = item.get(key, "\u2014")
                parts.append(f"{label}: {val}")
            lines.append("  \u2022 " + " | ".join(parts))
        return "\n".join(lines)

    @staticmethod
    def _handle_saludo() -> dict:
        return {
            "text": (
                "\u00a1Hola! Soy el asistente virtual de SIAM. Puedo ayudarte con:\n\n"
                "\u2022 \U0001f50d **Buscar** clientes, veh\u00edculos, facturas e inventario\n"
                "\u2022 \U0001f4cb **Listar** registros del sistema\n"
                "\u2022 \U0001f527 **Recomendar** mantenimientos seg\u00fan el veh\u00edculo\n"
                "\u2022 \U0001f4ca **Responder** preguntas sobre el taller\n\n"
                "\u00bfEn qu\u00e9 puedo ayudarte?"
            ),
            "tipo": "texto",
        }

    @staticmethod
    def _ayuda() -> dict:
        return {
            "text": (
                "**Comandos \u00fatiles:**\n\n"
                "\U0001f50d `Buscar cliente [nombre/cedula]`\n"
                "\U0001f50d `Buscar veh\u00edculo [placa/marca]`\n"
                "\U0001f50d `Buscar factura [n\u00famero]`\n"
                "\U0001f4e6 `Consultar inventario [producto]`\n"
                "\U0001f527 `Recomendar mantenimiento para [marca] [modelo] [a\u00f1o]`\n"
                "\U0001f4ca `\u00bfCu\u00e1ntos clientes hay?`\n"
                "\U0001f4ca `\u00bfCu\u00e1les son los servicios?`\n"
                "\u26a0\ufe0f `Stock bajo`\n"
                "\U0001f4b0 `Ingresos hoy`\n\n"
                "Tambi\u00e9n puedes preguntar en lenguaje natural. \u00a1Int\u00e9ntalo!"
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
                [("nombre", "Nombre"), ("telefono", "Tel"), ("cedula", "C\u00e9dula")]
            )
            return {"text": text, "tipo": "lista_clientes", "items": items}

        if not query:
            return {"text": "\u00bfQu\u00e9 cliente deseas buscar? Puedes darme su nombre, c\u00e9dula o tel\u00e9fono.", "tipo": "texto"}

        clientes = Cliente.query.filter(
            db.or_(
                Cliente.nombre.ilike(f"%{query}%"),
                Cliente.cedula.ilike(f"%{query}%"),
                Cliente.telefono.ilike(f"%{query}%"),
            )
        ).limit(5).all()

        if not clientes:
            return {"text": f"No encontr\u00e9 clientes con \u00ab{query}\u00bb.", "tipo": "texto"}

        items = []
        lines = [f"**Clientes encontrados para \u00ab{query}\u00bb:**\n"]
        for c in clientes:
            items.append({"id": c.id, "nombre": c.nombre, "telefono": c.telefono or "\u2014", "cedula": c.cedula or "\u2014", "correo": c.correo or "\u2014"})
            vehiculos = Vehiculo.query.filter_by(cliente_id=c.id).all()
            v_text = ", ".join([f"{v.placa} ({v.marca} {v.modelo})" for v in vehiculos]) or "Ninguno"
            lines.append(f"  \u2022 **{c.nombre}** | Tel: {c.telefono or '\u2014'} | C\u00e9dula: {c.cedula or '\u2014'}")
            lines.append(f"    Veh\u00edculos: {v_text}")

        return {"text": "\n".join(lines), "tipo": "lista_clientes", "items": items}

    @staticmethod
    def _buscar_vehiculo(entities: dict) -> dict:
        query = entities.get("query")

        if "list_all" in entities:
            items = entities["list_all"]
            text = AssistantService._format_lista(
                items, "Veh\u00edculos Registrados",
                [("placa", "Placa"), ("marca", "Marca"), ("modelo", "Modelo"), ("anio", "A\u00f1o")]
            )
            return {"text": text, "tipo": "lista_vehiculos", "items": items}

        if not query:
            return {"text": "\u00bfQu\u00e9 veh\u00edculo buscas? Dame la placa, marca o modelo.", "tipo": "texto"}

        vehiculos = Vehiculo.query.filter(
            db.or_(
                Vehiculo.placa.ilike(f"%{query}%"),
                Vehiculo.marca.ilike(f"%{query}%"),
                Vehiculo.modelo.ilike(f"%{query}%"),
            )
        ).limit(5).all()

        if not vehiculos:
            return {"text": f"No encontr\u00e9 veh\u00edculos con \u00ab{query}\u00bb.", "tipo": "texto"}

        items = []
        lines = [f"**Veh\u00edculos encontrados para \u00ab{query}\u00bb:**\n"]
        for v in vehiculos:
            cliente = Cliente.query.get(v.cliente_id)
            nombre_cliente = cliente.nombre if cliente else "\u2014"
            items.append({"id": v.id, "placa": v.placa, "marca": v.marca, "modelo": v.modelo, "anio": v.anio or "\u2014", "cliente": nombre_cliente})
            lines.append(f"  \u2022 **{v.placa}** \u2014 {v.marca} {v.modelo} ({v.anio or 'A\u00f1o?'})")
            lines.append(f"    Due\u00f1o: {nombre_cliente} | VIN: {v.vin or '\u2014'} | Color: {v.color or '\u2014'}")

        return {"text": "\n".join(lines), "tipo": "lista_vehiculos", "items": items}

    @staticmethod
    def _buscar_factura(entities: dict) -> dict:
        query = entities.get("query")

        if "list_all" in entities:
            items = entities["list_all"]
            text = AssistantService._format_lista(
                items, "\u00daltimas Facturas",
                [("numero", "N\u00b0"), ("total", "Total"), ("estado", "Estado"), ("fecha", "Fecha")]
            )
            return {"text": text, "tipo": "lista_facturas", "items": items}

        if not query:
            return {"text": "\u00bfQu\u00e9 factura buscas? Puedes darme el n\u00famero o el nombre del cliente.", "tipo": "texto"}

        facturas = Factura.query.filter(
            db.or_(
                Factura.numero.ilike(f"%{query}%"),
            )
        ).limit(5).all()

        if not facturas:
            from models.cita import Cita
            facturas = Factura.query.join(Cita, Cita.id == Factura.cita_id).join(Cliente, Cliente.id == Cita.cliente_id).filter(
                Cliente.nombre.ilike(f"%{query}%")
            ).limit(5).all()

        if not facturas:
            return {"text": f"No encontr\u00e9 facturas con \u00ab{query}\u00bb.", "tipo": "texto"}

        items = []
        lines = [f"**Facturas encontradas para \u00ab{query}\u00bb:**\n"]
        for f in facturas:
            items.append({"id": f.id, "numero": f.numero, "total": float(f.total), "estado": f.estado, "fecha": f.created_at.strftime("%Y-%m-%d")})
            lines.append(f"  \u2022 **{f.numero}** | ${float(f.total):,.0f} | *{f.estado.title()}* | {f.created_at.strftime('%d/%m/%Y')}")

        return {"text": "\n".join(lines), "tipo": "lista_facturas", "items": items}

    @staticmethod
    def _consultar_inventario(entities: dict) -> dict:
        query = entities.get("query")

        if not query:
            items = Inventario.query.order_by(Inventario.nombre).limit(15).all()
            if not items:
                return {"text": "El inventario est\u00e1 vac\u00edo.", "tipo": "texto"}
            lines = [f"**Inventario** (mostrando {len(items)} productos):\n"]
            for i in items:
                estado = "\u26a0\ufe0f" if i.stock_bajo else "\u2705"
                lines.append(f"  {estado} **{i.nombre}** \u2014 Stock: {i.cantidad} | Precio: ${float(i.precio_venta or 0):,.0f}")
            return {"text": "\n".join(lines), "tipo": "texto"}

        productos = Inventario.query.filter(
            db.or_(
                Inventario.nombre.ilike(f"%{query}%"),
                Inventario.sku.ilike(f"%{query}%"),
                Inventario.descripcion.ilike(f"%{query}%"),
            )
        ).limit(5).all()

        if not productos:
            return {"text": f"No encontr\u00e9 productos con \u00ab{query}\u00bb en el inventario.", "tipo": "texto"}

        lines = [f"**Productos encontrados para \u00ab{query}\u00bb:**\n"]
        for p in productos:
            estado = "\u26a0\ufe0f STOCK BAJO" if p.stock_bajo else "\u2705 Stock OK"
            lines.append(f"  \u2022 **{p.nombre}** (SKU: {p.sku or '\u2014'})")
            lines.append(f"    Cantidad: {p.cantidad} | M\u00ednimo: {p.stock_minimo} | {estado}")
            lines.append(f"    Precio Venta: ${float(p.precio_venta or 0):,.0f} | Ubicaci\u00f3n: {p.ubicacion or '\u2014'}")

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
                        "Dime el veh\u00edculo para recomendarte su mantenimiento. "
                        "Ej: *\u00abRecomienda mantenimiento para Toyota Corolla 2020\u00bb* "
                        "o *\u00abMantenimiento para ABC-123\u00bb*"
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
        lines.append("\n\U0001f4a1 *\u00bfDeseas agendar una cita para alguno de estos servicios?*")

        return {"text": "\n".join(lines), "tipo": "texto"}

    @staticmethod
    def _generar_recomendaciones(marca: str | None, modelo: str | None, anio: int | None) -> list:
        hoy = date.today()
        edad = hoy.year - anio if anio else None

        recomendaciones = [
            "\U0001f6e2\ufe0f **Cambio de aceite y filtro** \u2014 Cada 5,000 km o 6 meses",
            "\U0001f527 **Revisi\u00f3n de frenos** (pastillas, discos, l\u00edquido) \u2014 Cada 10,000 km",
        ]

        if edad is not None:
            if edad >= 1:
                recomendaciones.append("\U0001f504 **Rotaci\u00f3n de neum\u00e1ticos** \u2014 Cada 10,000 km")
                recomendaciones.append("\U0001f4a8 **Filtro de aire** \u2014 Cada 15,000 km")
            if edad >= 2:
                recomendaciones.append("\u26a1 **Buj\u00edas y cables** \u2014 Cada 20,000 km")
                recomendaciones.append("\U0001f9ca **L\u00edquido refrigerante** \u2014 Revisi\u00f3n anual")
            if edad >= 4:
                recomendaciones.append("\U0001f529 **Correa de distribuci\u00f3n** \u2014 Cada 60,000 km o 4 a\u00f1os")
                recomendaciones.append("\U0001f50b **Bater\u00eda** \u2014 Prueba de carga recomendada")
            if edad >= 6:
                recomendaciones.append("\U0001f6de **Suspensi\u00f3n y amortiguadores** \u2014 Revisi\u00f3n general")
                recomendaciones.append("\U0001f321\ufe0f **Termostato y bomba de agua** \u2014 Verificar estado")
            if edad >= 8:
                recomendaciones.append("\u26a0\ufe0f **Revisi\u00f3n integral recomendada** \u2014 El veh\u00edculo tiene m\u00e1s de 8 a\u00f1os")
        else:
            recomendaciones.extend([
                "\U0001f504 **Rotaci\u00f3n de neum\u00e1ticos** \u2014 Cada 10,000 km",
                "\U0001f4a8 **Filtro de aire** \u2014 Cada 15,000 km",
                "\u26a1 **Buj\u00edas** \u2014 Cada 20,000 km",
            ])

        servicios = Servicio.query.filter(Servicio.activo == True).order_by(Servicio.nombre).all()
        if servicios:
            recomendaciones.append(f"\n\U0001f4cb **Servicios disponibles en el taller ({len(servicios)}):**")
            for s in servicios[:5]:
                precio = f" \u2014 ${float(s.precio_estimado):,.0f}" if s.precio_estimado else ""
                recomendaciones.append(f"   \u2022 {s.nombre}{precio}")

        return recomendaciones

    @staticmethod
    def _responder_pregunta(entities: dict) -> dict:
        query = entities.get("query", "")

        respuestas = {
            r"\bhorarios?\b": "Nuestro horario de atenci\u00f3n es **lunes a viernes de 7:00 AM a 6:00 PM** y **s\u00e1bados de 8:00 AM a 1:00 PM**.",
            r"\bd[i\u00ed]as?\s+ (de )?entrega|tiempo.*reparaci[o\u00f3]n|demora": (
                "El tiempo de reparaci\u00f3n depende del servicio. Un mantenimiento b\u00e1sico toma 1-2 horas. "
                "Trabajos mayores como motor o transmisi\u00f3n pueden tomar 2-5 d\u00edas h\u00e1biles."
            ),
            r"\bgarant[i\u00ed]a": "Ofrecemos **3 meses de garant\u00eda** en servicios de reparaci\u00f3n y **6 meses** en trabajos de motor y transmisi\u00f3n.",
            r"\bformas?\s* de pago|m[e\u00e9]todos?\s* de pago|pagos?\b": (
                "Aceptamos: **Efectivo, Tarjeta D\u00e9bito, Tarjeta Cr\u00e9dito, Transferencia, PSE, Nequi y Daviplata**."
            ),
            r"\bdomicilio|recojan|a domicilio": "S\u00ed, ofrecemos servicio de **recojo y entrega a domicilio** dentro del \u00e1rea urbana. Consulta disponibilidad.",
            r"\bprecios?\b|cu[a\u00e1]nto cuesta|cu[a\u00e1]nto vale|tarifas": (
                "Los precios var\u00edan seg\u00fan el servicio. Puedes consultar nuestros servicios en el m\u00f3dulo de **Servicios** "
                "o pedirme que te los muestre con *\u00ablista de servicios\u00bb*."
            ),
            r"\bc[o\u00f3]mo\s+ (llegar|ubicaci[o\u00f3]n|d[i\u00ed]recci[o\u00f3]n|d\u00f3nde|donde|encuentran)\b": (
                "Puedes consultar nuestra direcci\u00f3n en la **Configuraci\u00f3n del Taller** (m\u00f3dulo Facturas > Configuraci\u00f3n)."
            ),
            r"\bqu[e\u00e9] puedes hacer|funciones|capacidades": (
                "Puedo:\n"
                "\u2022 Buscar clientes, veh\u00edculos y facturas\n"
                "\u2022 Consultar el inventario\n"
                "\u2022 Recomendar mantenimientos seg\u00fan el veh\u00edculo\n"
                "\u2022 Mostrar estad\u00edsticas del taller\n"
                "\u2022 Responder preguntas sobre servicios y pol\u00edticas\n\n"
                "\u00bfQu\u00e9 necesitas?"
            ),
            r"\bqui[e\u00e9]n eres|como te llamas|nombre": (
                "Soy el **Asistente IA de SIAM**, tu ayudante virtual para la gesti\u00f3n del taller. "
                "Estoy aqu\u00ed para facilitar tu trabajo. \u00bfEn qu\u00e9 puedo ayudarte?"
            ),
        }

        for pattern, respuesta in respuestas.items():
            if re.search(pattern, query.lower()):
                return {"text": respuesta, "tipo": "texto"}

        if re.search(r"\b(gracias|thanks|ok)\b", query.lower()):
            return {"text": "\u00a1Con gusto! Siempre que necesites algo, aqu\u00ed estoy. \U0001f60a", "tipo": "texto"}

        return {
            "text": (
                "No estoy seguro de c\u00f3mo responder a eso. Puedes preguntarme:\n\n"
                "\u2022 *\u00abBuscar cliente Juan\u00bb*\n"
                "\u2022 *\u00abRecomienda mantenimiento para un Toyota 2020\u00bb*\n"
                "\u2022 *\u00ab\u00bfCu\u00e1ntos clientes hay?\u00bb*\n"
                "\u2022 *\u00abStock bajo\u00bb*\n"
                "\u2022 *\u00abAyuda\u00bb* para ver m\u00e1s opciones"
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
            "text": f"\U0001f4ca **Clientes:**\n  \u2022 Total: **{total}**\n  \u2022 Registrados este mes: **{este_mes}**",
            "tipo": "texto",
        }

    @staticmethod
    def _contar_vehiculos() -> dict:
        total = Vehiculo.query.count()
        return {
            "text": f"\U0001f697 **Veh\u00edculos registrados:** **{total}** en total.",
            "tipo": "texto",
        }

    @staticmethod
    def _contar_facturas() -> dict:
        total = Factura.query.count()
        pendientes = Factura.query.filter(Factura.estado == "pendiente").count()
        pagadas = Factura.query.filter(Factura.estado == "pagado").count()
        return {
            "text": f"\U0001f4c4 **Facturas:**\n  \u2022 Total: **{total}**\n  \u2022 Pendientes: **{pendientes}**\n  \u2022 Pagadas: **{pagadas}**",
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
            "text": f"\U0001f527 **\u00d3rdenes de Trabajo:**\n  \u2022 Total: **{total}**\n  \u2022 Activas: **{activas}**\n  \u2022 Listas para entrega: **{listas}**\n  \u2022 Entregadas: **{entregadas}**",
            "tipo": "texto",
        }

    @staticmethod
    def _stock_bajo() -> dict:
        items = Inventario.query.filter(
            Inventario.cantidad <= Inventario.stock_minimo
        ).order_by(Inventario.cantidad.asc()).limit(10).all()

        if not items:
            return {"text": "\u2705 No hay productos con stock bajo. \u00a1Todo en orden!", "tipo": "texto"}

        lines = [f"\u26a0\ufe0f **Productos con stock bajo** ({len(items)}):\n"]
        for i in items:
            urgente = "\U0001f6a8" if i.cantidad == 0 else "\u26a0\ufe0f"
            lines.append(f"  {urgente} **{i.nombre}** \u2014 Stock: {i.cantidad} (m\u00ednimo: {i.stock_minimo})")
            if i.proveedor:
                lines.append(f"    Proveedor: {i.proveedor}")

        return {"text": "\n".join(lines), "tipo": "texto"}

    @staticmethod
    def _servicios_disponibles() -> dict:
        servicios = Servicio.query.filter(Servicio.activo == True).order_by(Servicio.nombre).all()
        if not servicios:
            return {"text": "No hay servicios registrados actualmente.", "tipo": "texto"}

        lines = [f"\U0001f4cb **Servicios disponibles** ({len(servicios)} en total):\n"]
        for s in servicios:
            precio = f"${float(s.precio_estimado):,.0f}" if s.precio_estimado else "Consultar"
            duracion = f"{s.duracion_estimada} min" if s.duracion_estimada else "\u2014"
            lines.append(f"  \u2022 **{s.nombre}** \u2014 {precio} | {duracion}")
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
            "text": f"\U0001f4b0 **Ingresos:**\n  \u2022 Hoy: **${float(total):,.0f}**\n  \u2022 Este mes: **${float(total_mes):,.0f}**",
            "tipo": "texto",
        }

    @staticmethod
    def _no_entiendo() -> dict:
        return {
            "text": (
                "No entend\u00ed tu mensaje. Puedes pedir **ayuda** para ver mis funciones "
                "o simplemente preguntar en lenguaje natural."
            ),
            "tipo": "texto",
        }
