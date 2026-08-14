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
            "repuesto", "repuestos", "pieza", "piezas", "parte", "accesorio",
            "para mi carro", "para mi moto", "para carros", "para motos",
        ],
        "saludo": [
            "hola", "buenas", "saludos", "buenos", "hey",
            "qu\u00e9 tal", "que tal",
        ],
        "facturacion": [
            "facturaci\u00f3n", "facturacion", "facturo", "facturar", "c\u00f3mo facturo",
            "como facturo", "c\u00f3mo facturar", "como facturar", "cu\u00e1ndo se factura",
            "cuando se factura",
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
            "repuesto", "repuestos", "pieza", "piezas", "existencia",
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

    # Intents de peticiones concretas: se revisan antes que los síntomas y antes
    # que los intents genéricos para no confundir, p. ej. "¿cuánto cuesta cambiar frenos?".
    REQUEST_PATTERNS: list[tuple[str, list[str]]] = [
        ("cita_agendar", [
            "quiero una cita", "quiero cita", "agendar cita", "agendar una cita",
            "reservar cita", "programar cita", "solicitar cita", "necesito una cita",
            "pedir cita", "turno", "agendar",
            "llevar mi carro", "llevar mi moto", "llevar mi veh\u00edculo", "llevar mi vehiculo",
            "llevarlo al taller", "llevarla al taller", "llevar mi carro al taller",
            "llevar mi moto al taller", "agendar una revisi\u00f3n", "agendar una revision",
            "necesito una revisi\u00f3n", "necesito una revision", "quiere llevar mi carro",
            "quiere llevar mi moto", "quiero llevar mi carro", "quiero llevar mi moto",
        ]),
        ("sedes_mas_cercana", [
            "sede m\u00e1s cercana", "sede mas cercana", "m\u00e1s cercana", "mas cercana",
            "m\u00e1s cerca", "mas cerca", "cerca de m\u00ed", "cerca de mi",
            "como llegar", "c\u00f3mo llegar", "cu\u00e1l sede", "cual sede",
            "qu\u00e9 sede", "que sede", "d\u00f3nde queda la sede", "donde queda la sede",
        ]),
        ("precio_servicio", [
            "cu\u00e1nto cuesta cambiar", "cuanto cuesta cambiar",
            "cu\u00e1nto cuesta un", "cuanto cuesta un", "cu\u00e1nto cuesta la",
            "cuanto cuesta la", "cu\u00e1nto cuesta una", "cuanto cuesta una",
            "precio del", "precio de la", "precio de un", "precio de una",
            "valor del", "valor de un", "cu\u00e1nto cobran", "cuanto cobran",
            "cotizaci\u00f3n", "cotizacion", "presupuesto",
        ]),
        ("mantenimiento_preventivo", [
            "cambio de aceite", "cada cu\u00e1nto", "cada cuanto", "cada cuantos km",
            "filtro de aire", "filtro de aceite", "filtros", "revisi\u00f3n general",
            "revision general", "mantenimiento preventivo", "puesta a punto",
            "calibraci\u00f3n de llantas", "calibracion de llantas",
            "cu\u00e1ndo debo cambiar", "cuando debo cambiar", "cambiar el aceite",
            "cu\u00e1ndo cambio aceite", "cuando cambio aceite", "debo cambiar aceite",
            "cu\u00e1nto cambio el aceite", "cuanto cambio el aceite",
        ]),
        ("aceite_tipo", [
            "qu\u00e9 aceite", "que aceite", "qu\u00e9 tipo de aceite", "que tipo de aceite",
            "aceite usa", "aceite lleva", "aceite le echo", "aceite le hecho",
            "aceite debo usar", "aceite para mi",
        ]),
    ]

    # Síntomas mecánicos: se revisan antes que los intents genéricos.
    SYMPTOM_PATTERNS: list[tuple[str, list[str]]] = [
        ("diagnostico_arranque", [
            "no prende", "no arranca", "no enciende", "no quiere prender",
            "no da arranque", "no da motor", "quiere prender y no", "no prende nada",
            "no quiere arrancar", "no enciende nada",
        ]),
        ("check_engine", [
            "check engine", "testigo", "luz de motor", "luz del tablero",
            "luz de aceite", "se\u00f1al de motor", "codigo de error", "c\u00f3digo de error",
            "esc\u00e1ner", "escaner", "scanner", "prende el testigo",
            "se encendi\u00f3 el testigo", "se encendio el testigo", "testigo del tablero",
        ]),
        ("diagnostico_calentamiento", [
            "se calienta", "calienta mucho", "sobrecalienta", "botando vapor",
            "echando vapor", "sale vapor", "temperatura alta", "fiebre",
            "se est\u00e1 calentando", "se esta calentando", "est\u00e1 calentando",
            "esta calentando", "se calentando", "calentando mucho",
        ]),
        ("diagnostico_humo", [
            "echa humo", "botando humo", "saca humo", "sacando humo",
            "humo blanco", "humo negro", "humo azul", "humo",
            "est\u00e1 echando humo", "esta echando humo", "est\u00e1 botando humo",
            "esta botando humo", "echando humo",
            "olor a gasolina", "huele a gasolina", "olor a quemado", "huele a quemado",
            "huele a humo", "olor a humo",
        ]),
        ("diagnostico_frenos", [
            "no frena", "frena mal", "pedal blando", "pedal esponjoso",
            "pedal duro", "frenada", "l\u00edquido de frenos", "liquido de frenos",
            "pastillas de freno", "discos de freno", "chirr", "chirrido",
        ]),
        ("diagnostico_llanta", [
            "pinchada", "pincho", "pinch\u00f3", "revent\u00f3", "reviento", "revienta",
            "neum\u00e1tico", "neumatico", "v\u00e1lvula", "valvula", "perdida de aire",
            "pierde aire", "llanta desinflada", "se pinch\u00f3", "se pincho",
        ]),
        ("bateria", [
            "bater\u00eda descargada", "bateria descargada", "no carga la bateria",
            "no carga la bater\u00eda", "alternador", "bornes", "terminales",
            "pasacorriente", "pasa corriente", "cables de paso", "no me arranca",
        ]),
        ("diagnostico_apagado", [
            "se apaga", "se muere", "se corta", "se apaga solo", "se apaga sola",
            "se apaga en marcha", "se apaga cuando", "apaga y no prende",
            "se est\u00e1 apagando", "se esta apagando", "se apagando",
        ]),
        ("diagnostico_aceleracion", [
            "no acelera", "no responde", "sin potencia", "jalonea", "acelera mal",
            "se ahoga", "no pasa de", "pierde fuerza", "no me acelera",
        ]),
        ("diagnostico_vibraciones", [
            "vibra", "vibraci\u00f3n", "vibracion", "tiembla", "temblor",
            "tronando", "truena", "hace ruido", "ruido raro", "ruido extra",
            "sonido raro", "rueda dura", "est\u00e1 vibrando", "esta vibrando",
            "vibrando", "vibra al frenar", "vibra cuando",
        ]),
    ]

    # Intents de datos administrativos: solo personal del taller (no clientes).
    BUSINESS_ONLY: set[str] = {
        "buscar_cliente", "buscar_vehiculo", "buscar_factura",
        "contar_clientes", "contar_vehiculos", "contar_facturas", "contar_ot",
        "ingresos_hoy", "stock_bajo",
    }

    # Intents que un cliente puede usar, pero sin exponer el inventario del taller.
    CLIENT_GENERIC: set[str] = {"consultar_inventario", "repuestos"}

    @staticmethod
    def process_message(message: str, usuario=None) -> dict:
        msg_lower = message.lower().strip()
        logger.debug("Procesando mensaje: %s", msg_lower)

        intent, entities = AssistantService._classify_intent(msg_lower)

        es_cliente = bool(usuario and getattr(usuario, "es_cliente", False))

        if es_cliente and intent in AssistantService.BUSINESS_ONLY:
            return AssistantService._informacion_administrativa()
        if es_cliente and intent in AssistantService.CLIENT_GENERIC:
            return AssistantService._respuesta_repuestos_cliente()

        if intent == "saludo":
            return AssistantService._handle_saludo()
        elif intent == "facturacion":
            return AssistantService._facturacion(usuario)
        elif intent == "cita_agendar":
            return AssistantService._cita_agendar(usuario)
        elif intent == "sedes_mas_cercana":
            return AssistantService._sedes_mas_cercana()
        elif intent == "precio_servicio":
            return AssistantService._precio_servicio(entities)
        elif intent == "mantenimiento_preventivo":
            return AssistantService._mantenimiento_preventivo()
        elif intent == "aceite_tipo":
            return AssistantService._aceite_tipo()
        elif intent == "diagnostico_arranque":
            return AssistantService._diagnostico_arranque()
        elif intent == "check_engine":
            return AssistantService._check_engine()
        elif intent == "diagnostico_calentamiento":
            return AssistantService._diagnostico_calentamiento()
        elif intent == "diagnostico_humo":
            return AssistantService._diagnostico_humo()
        elif intent == "diagnostico_frenos":
            return AssistantService._diagnostico_frenos()
        elif intent == "diagnostico_llanta":
            return AssistantService._diagnostico_llanta()
        elif intent == "bateria":
            return AssistantService._bateria()
        elif intent == "diagnostico_apagado":
            return AssistantService._diagnostico_apagado()
        elif intent == "diagnostico_aceleracion":
            return AssistantService._diagnostico_aceleracion()
        elif intent == "diagnostico_vibraciones":
            return AssistantService._diagnostico_vibraciones()
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
        entities = {"query": msg}

        for intent_name, keywords in AssistantService.REQUEST_PATTERNS + AssistantService.SYMPTOM_PATTERNS:
            pattern = r'\b(?:' + '|'.join(re.escape(k) for k in keywords) + r')\b'
            if re.search(pattern, msg):
                return intent_name, entities

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
                "\U0001f527 **Mec\u00e1nica y mantenimiento**: carros, motos y veh\u00edculos de carga\n"
                "\U0001f50d **Diagn\u00f3stico**: s\u00edntomas como que no prende, se calienta, echa humo o vibra\n"
                "\U0001f4cd **Sedes y asistencia**: sede m\u00e1s cercana o si est\u00e1s varado\n"
                "\U0001f4c5 **Citas**: agendar o consultar servicios\n"
                "\U0001f4cb **Gesti\u00f3n**: buscar clientes, veh\u00edculos, facturas e inventario (personal autorizado)\n\n"
                "\u00bfEn qu\u00e9 puedo ayudarte?"
            ),
            "tipo": "texto",
        }

    @staticmethod
    def _facturacion(usuario=None) -> dict:
        es_cliente = bool(usuario and getattr(usuario, "es_cliente", False))
        if es_cliente:
            return {
                "text": (
                    "En tu portal de cliente puedes ver **tus facturas y pagos** "
                    "en la secci\u00f3n **Mis Facturas**.\n"
                    "Si necesitas el detalle de una factura espec\u00edfica o tienes dudas "
                    "sobre un pago, cont\u00e1ctanos y te ayudamos."
                ),
                "tipo": "texto",
            }
        return {
            "text": (
                "La **facturaci\u00f3n** se gestiona desde el m\u00f3dulo **Facturas**: "
                "crear facturas asociadas a \u00f3rdenes de trabajo, registrar pagos "
                "parciales o totales y descargar el PDF.\n"
                "Puedes pedirme cosas como *\u00abbuscar factura 12\u00bb* o *\u00abfacturas de hoy\u00bb*."
            ),
            "tipo": "texto",
        }

    @staticmethod
    def _ayuda() -> dict:
        return {
            "text": (
                "**Puedes preguntarme en lenguaje natural**, por ejemplo:\n\n"
                "\U0001f697 \u00abMi carro no prende\u00bb\n"
                "\U0001f3cd\ufe0f \u00ab\u00bfPor qu\u00e9 vibra mi carro?\u00bb\n"
                "\U0001f9f1 \u00ab\u00bfQu\u00e9 significa el Check Engine?\u00bb\n"
                "\U0001f32b\ufe0f \u00abLa moto echa humo blanco\u00bb\n"
                "\U0001f321\ufe0f \u00abMi carro se est\u00e1 calentando\u00bb\n"
                "\U0001f6de \u00abSe me pinch\u00f3 una llanta\u00bb\n"
                "\U0001f527 \u00ab\u00bfCada cu\u00e1nto cambio el aceite?\u00bb\n"
                "\U0001f4b0 \u00ab\u00bfCu\u00e1nto cuesta cambiar frenos?\u00bb\n"
                "\U0001f4cd \u00ab\u00bfCu\u00e1l es la sede m\u00e1s cercana?\u00bb\n"
                "\U0001f4c5 \u00abQuiero agendar una cita\u00bb\n"
                "\U0001f6a8 \u00abEstoy varado\u00bb\n\n"
                "Tambi\u00e9n, si eres personal autorizado: \u00abbuscar cliente Juan\u00bb, "
                "\u00abconsultar inventario\u00bb, \u00abstock bajo\u00bb o \u00abingresos hoy\u00bb."
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
            cliente = db.session.get(Cliente, v.cliente_id)
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
    def _respuesta_diagnostico(titulo: str, causas: list, consejo: str, grave: bool = False) -> dict:
        lines = [f"**{titulo}**\n", "Eso **podr\u00eda deberse a**:\n"]
        for c in causas:
            lines.append(f"  \u2022 {c}")
        if grave:
            lines.append(f"\n\u26a0\ufe0f **Seguridad:** {consejo}")
        else:
            lines.append(f"\n\U0001f527 **Lo recomendable:** {consejo}")
        lines.append(
            "\n\U0001f4a1 *No puedo dar un diagn\u00f3stico definitivo por chat. "
            "Lo ideal es que un t\u00e9cnico revise el veh\u00edculo.*"
        )
        if grave:
            lines.append("\nSi est\u00e1s varado o necesitas ayuda, comparte tu ubicaci\u00f3n.")
        return {"text": "\n".join(lines), "tipo": "botones"}

    @staticmethod
    def _diagnostico_arranque() -> dict:
        return AssistantService._respuesta_diagnostico(
            "\U0001f511 El veh\u00edculo no arranca",
            [
                "Bater\u00eda descargada o bornes flojos/corroidos.",
                "Fallo en el motor de arranque o en el interruptor.",
                "Problema de combustible: bomba, filtro o inyectores.",
                "Buj\u00edas o bobinas de encendido en mal estado.",
            ],
            "revisar el estado de la bater\u00eda y, si no arranca, "
            "solicitar asistencia para una revisi\u00f3n en el taller.",
            grave=True,
        )

    @staticmethod
    def _check_engine() -> dict:
        return AssistantService._respuesta_diagnostico(
            "\U0001f4a1 Testigo de motor (Check Engine)",
            [
                "Un sensor del motor (por ejemplo, ox\u00edgeno o temperatura).",
                "Buj\u00edas o bobinas en mal estado.",
                "Tapa de combustible floja (com\u00fan y sencillo de resolver).",
                "Problema de combustible o de emisiones.",
            ],
            "escanear el c\u00f3digo de error con un equipo de diagn\u00f3stico "
            "para conocer la causa exacta y revisarlo en el taller.",
        )

    @staticmethod
    def _diagnostico_calentamiento() -> dict:
        return AssistantService._respuesta_diagnostico(
            "\U0001f321\ufe0f El veh\u00edculo se calienta",
            [
                "Bajo nivel de l\u00edquido refrigerante o fuga.",
                "Termostato da\u00f1ado (no abre correctamente).",
                "Bomba de agua fallando.",
                "Ventilador del radiador que no funciona.",
            ],
            "si el indicador llega a la zona roja o sale vapor, det\u00e9n el veh\u00edculo "
            "en un lugar seguro, apaga el motor y espera a que enfr\u00ede. "
            "No contin\u00faes conduciendo para evitar da\u00f1os graves al motor.",
            grave=True,
        )

    @staticmethod
    def _diagnostico_humo() -> dict:
        return AssistantService._respuesta_diagnostico(
            "\U0001f32b\ufe0f El veh\u00edculo echa humo",
            [
                "Humo **blanco**: podr\u00eda indicar l\u00edquido refrigerante quem\u00e1ndose "
                "(empaque de culata o culata).",
                "Humo **negro**: exceso de combustible (inyecci\u00f3n o filtro de aire sucio).",
                "Humo **azul**: podr\u00eda ser aceite quem\u00e1ndose (aros o sellos de v\u00e1lvula).",
            ],
            "revisarlo en el taller para identificar el origen. "
            "Si el humo es abundante o hay olor a gasolina, no contin\u00faes conduciendo "
            "y solicita asistencia.",
            grave=True,
        )

    @staticmethod
    def _diagnostico_frenos() -> dict:
        return AssistantService._respuesta_diagnostico(
            "\U0001f6a8 Problema de frenos",
            [
                "Pastillas o discos desgastados.",
                "Bajo nivel de l\u00edquido de frenos o fuga.",
                "Aire en el sistema (pedal blando o esponjoso).",
                "Pinzas o cilindros de freno da\u00f1ados.",
            ],
            "si sientes que el veh\u00edculo no frena o el pedal est\u00e1 blando, "
            "det\u00e9n el veh\u00edculo en un lugar seguro y **no lo conduzcas**. "
            "Solicita asistencia de inmediato.",
            grave=True,
        )

    @staticmethod
    def _aceite_tipo() -> dict:
        return {
            "text": (
                "El tipo de aceite correcto depende de la **marca, modelo y motor** "
                "de tu veh\u00edculo.\n"
                "Puedes verificarlo en el **manual del propietario** o en la tapa "
                "de llenado del motor.\n\n"
                "No te doy un grado de aceite exacto por chat para no recomendarte "
                "algo equivocado. En el taller podemos verificar el aceite adecuado "
                "y hacer el cambio."
            ),
            "tipo": "texto",
        }

    @staticmethod
    def _diagnostico_llanta() -> dict:
        return AssistantService._respuesta_diagnostico(
            "\U0001f6de Problema con la llanta",
            [
                "Pinchazo o perforaci\u00f3n.",
                "P\u00e9rdida lenta de aire por la v\u00e1lvula o el rin.",
                "Desgaste irregular o cortes en la llanta.",
            ],
            "si est\u00e1 desinflada, cambia por la de repuesto en un lugar seguro "
            "o solicita asistencia. Revisa la presi\u00f3n de las cuatro llantas.",
            grave=True,
        )

    @staticmethod
    def _bateria() -> dict:
        return AssistantService._respuesta_diagnostico(
            "\U0001f50b Problema con la bater\u00eda",
            [
                "Bater\u00eda descargada o en fin de vida \u00fatil.",
                "Bornes flojos o con corrosi\u00f3n.",
                "El alternador no est\u00e1 cargando correctamente.",
                "Consumo de corriente con el motor apagado.",
            ],
            "verificar el voltaje y el estado de los bornes. "
            "Si quedaste varado, solicita asistencia para un paso de corriente o revisi\u00f3n.",
            grave=True,
        )

    @staticmethod
    def _diagnostico_apagado() -> dict:
        return AssistantService._respuesta_diagnostico(
            "\u26d4 El veh\u00edculo se apaga en marcha",
            [
                "Bomba de combustible o filtro obstruido.",
                "Sensor de posici\u00f3n del cig\u00fce\u00f1al en mal estado.",
                "Bobinas o buj\u00edas fallando.",
                "Problema el\u00e9ctrico intermitente.",
            ],
            "revisarlo en el taller; si se apaga de forma intermitente, "
            "podr\u00eda dejarte varado. Considera solicitar asistencia.",
            grave=True,
        )

    @staticmethod
    def _diagnostico_aceleracion() -> dict:
        return AssistantService._respuesta_diagnostico(
            "\u26a1 Sin potencia o no acelera",
            [
                "Filtro de aire o de combustible sucios.",
                "Inyectores obstruidos.",
                "Buj\u00edas o cables de encendido en mal estado.",
                "Sensor de ox\u00edgeno o de flujo de aire fallando.",
            ],
            "revisar filtros y encendido en el taller para descartar problemas mayores.",
        )

    @staticmethod
    def _diagnostico_vibraciones() -> dict:
        return AssistantService._respuesta_diagnostico(
            "\u2699\ufe0f Vibraciones o ruidos",
            [
                "Neum\u00e1ticos desbalanceados o desalineados.",
                "Soportes del motor desgastados.",
                "Buj\u00edas o cables en mal estado (vibra al acelerar).",
                "Si vibra al frenar, podr\u00edan ser los discos de freno.",
            ],
            "revisar balanceo, alineaci\u00f3n y soportes en el taller.",
        )

    @staticmethod
    def _mantenimiento_preventivo() -> dict:
        return {
            "text": (
                "\U0001f527 **Mantenimiento preventivo**\n\n"
                "Como referencia general (consulta el manual de tu veh\u00edculo):\n"
                "  \u2022 **Aceite y filtro**: cada 5,000 km o 6 meses.\n"
                "  \u2022 **Frenos**: revisi\u00f3n cada 10,000 km.\n"
                "  \u2022 **Filtro de aire**: cada 15,000 km.\n"
                "  \u2022 **Rotaci\u00f3n de llantas**: cada 10,000 km.\n"
                "  \u2022 **L\u00edquido de frenos y refrigerante**: revisi\u00f3n anual.\n\n"
                "\U0001f4a1 Los intervalos exactos dependen de la marca y el modelo. "
                "\u00bfQuieres agendar una cita para una revisi\u00f3n?"
            ),
            "tipo": "botones",
        }

    @staticmethod
    def _cita_agendar(usuario) -> dict:
        if usuario and getattr(usuario, "es_cliente", False):
            ruta = "/portal/citas/solicitar"
            extra = " desde tu portal de cliente (**Mis Citas**)."
        else:
            ruta = "/citas/"
            extra = " desde el m\u00f3dulo de **Citas**."
        return {
            "text": (
                "Claro. Puedes agendar una cita" + extra +
                "\n\U0001f4c5 Ruta: " + ruta
            ),
            "tipo": "texto",
        }

    @staticmethod
    def _sedes_mas_cercana() -> dict:
        return {
            "text": (
                "\U0001f4cd Puedes ver nuestras sedes en **Sedes y Asistencia** (/sedes/).\n"
                "Usa el bot\u00f3n **\u00abUsar mi ubicaci\u00f3n\u00bb** para calcular la distancia "
                "a cada sede y te mostraremos autom\u00e1ticamente la **m\u00e1s cercana**.\n"
                "Tambi\u00e9n puedes solicitar asistencia desde esa p\u00e1gina si est\u00e1s varado."
            ),
            "tipo": "texto",
        }

    @staticmethod
    def _precio_servicio(entities: dict) -> dict:
        msg = (entities.get("query") or "").lower()
        servicios = Servicio.query.filter(Servicio.activo == True).all()
        match = None
        for s in servicios:
            if s.nombre and s.nombre.lower() in msg:
                match = s
                break
        if not match:
            for kw in [
                "frenos", "freno", "aceite", "revisi\u00f3n", "revision",
                "mantenimiento", "suspensi\u00f3n", "suspension", "buj\u00edas", "bujias",
                "filtro", "afinaci\u00f3n", "afinacion", "balanceo", "alineaci\u00f3n", "alineacion",
                "transmisi\u00f3n", "transmision", "embrague", "amortiguadores",
            ]:
                match = Servicio.query.filter(
                    Servicio.nombre.ilike(f"%{kw}%"), Servicio.activo == True
                ).first()
                if match:
                    break
        if match:
            precio = f"${float(match.precio_estimado):,.0f}" if match.precio_estimado else "Consultar"
            duracion = f" | {match.duracion_estimada} min" if match.duracion_estimada else ""
            return {
                "text": (
                    f"**{match.nombre}**: {precio}{duracion}\n\n"
                    "\u00bfDeseas agendar una cita para este servicio?"
                ),
                "tipo": "texto",
            }
        return {
            "text": (
                "No dispongo del precio exacto para eso en este momento. "
                "Te recomiendo **contactar a SIAM** o solicitar una **cotizaci\u00f3n** "
                "para confirmar el valor."
            ),
            "tipo": "texto",
        }

    @staticmethod
    def _informacion_administrativa() -> dict:
        return {
            "text": (
                "Esa informaci\u00f3n es administrativa del taller y solo est\u00e1 disponible "
                "para el personal autorizado.\n"
                "Para lo que necesites, puedes consultar tus **veh\u00edculos**, **citas**, "
                "**\u00f3rdenes** y **facturas** en tu portal de cliente."
            ),
            "tipo": "texto",
        }

    @staticmethod
    def _respuesta_repuestos_cliente() -> dict:
        return {
            "text": (
                "S\u00ed, manejamos repuestos y accesorios para autom\u00f3viles, motos "
                "y veh\u00edculos de carga en nuestras sedes.\n"
                "Para confirmar **disponibilidad y precio** del repuesto que necesitas, "
                "te recomiendo contactar a la sede m\u00e1s cercana."
            ),
            "tipo": "texto",
        }

    @staticmethod
    def _no_entiendo() -> dict:
        return {
            "text": (
                "No estoy seguro de c\u00f3mo responder a eso. Puedes preguntarme cosas como:\n\n"
                "\U0001f697 *\u00abMi carro no prende\u00bb*\n"
                "\U0001f3cd\ufe0f *\u00ab\u00bfPor qu\u00e9 vibra mi carro?\u00bb*\n"
                "\U0001f32b\ufe0f *\u00abLa moto echa humo\u00bb*\n"
                "\U0001f6de *\u00abNecesito cambiar una llanta\u00bb*\n"
                "\U0001f527 *\u00ab\u00bfCada cu\u00e1nto cambio el aceite?\u00bb*\n"
                "\U0001f4cd *\u00ab\u00bfCu\u00e1l es la sede m\u00e1s cercana?\u00bb*\n"
                "\U0001f4c5 *\u00abQuiero agendar una cita\u00bb*\n\n"
                "O pide **ayuda** para ver todas mis funciones."
            ),
            "tipo": "texto",
        }
