document.addEventListener('DOMContentLoaded', function () {
    initTooltips();
    initSidebar();
    initAnimations();
    initToast();
    initDeleteLinks();
    initConfirmForms();
    initDarkMode();
    initAjaxForms();
    initAjaxDelete();
    initLocationButton();
    initTableSearch();
    initFormLabels();
    initPasswordToggles();
    initNotificaciones();
});

/* Mostrar/ocultar contraseña en formularios de acceso y registro */
function initPasswordToggles() {
    document.querySelectorAll('[data-toggle-password]').forEach(function (btn) {
        if (btn.dataset.pwToggleBound === '1') return;
        btn.dataset.pwToggleBound = '1';
        btn.addEventListener('click', function () {
            var input = document.querySelector(btn.getAttribute('data-toggle-password'));
            if (!input) return;
            var mostrar = input.type === 'password';
            input.type = mostrar ? 'text' : 'password';
            var icono = btn.querySelector('i');
            if (icono) icono.className = mostrar ? 'fa-solid fa-eye-slash' : 'fa-solid fa-eye';
            btn.setAttribute('aria-label', mostrar ? 'Ocultar contraseña' : 'Mostrar contraseña');
        });
    });
}

function initTooltips() {
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (el) {
        return new bootstrap.Tooltip(el);
    });
}

function initSidebar() {
    var toggler = document.getElementById('sidebarToggler');
    var sidebar = document.querySelector('.sidebar');
    var backdrop = null;

    function closeSidebar() {
        if (!sidebar) return;
        sidebar.classList.remove('show');
        if (toggler) toggler.setAttribute('aria-expanded', 'false');
        if (backdrop) { backdrop.remove(); backdrop = null; }
    }

    function openSidebar() {
        if (!sidebar) return;
        sidebar.classList.add('show');
        if (toggler) toggler.setAttribute('aria-expanded', 'true');
        if (!backdrop) {
            backdrop = document.createElement('div');
            backdrop.className = 'sidebar-backdrop';
            backdrop.addEventListener('click', closeSidebar);
            document.body.appendChild(backdrop);
        }
    }

    if (toggler) {
        toggler.addEventListener('click', function () {
            if (sidebar && sidebar.classList.contains('show')) {
                closeSidebar();
            } else {
                openSidebar();
            }
        });
    }

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') closeSidebar();
    });

    var navLinks = document.querySelectorAll('.sidebar .nav-link');
    var currentPath = window.location.pathname;
    navLinks.forEach(function (link) {
        if (link.getAttribute('href') === currentPath) {
            link.classList.add('active');
        }
    });
}

function prefiereMovimientoReducido() {
    return window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

function initAnimations() {
    if (prefiereMovimientoReducido()) {
        document.documentElement.classList.add('aos-fallback');
        return;
    }
    if (typeof AOS !== 'undefined') {
        document.documentElement.classList.add('aos-ready');
        AOS.init({
            duration: 600,
            once: true,
            offset: 50,
        });
    } else {
        document.documentElement.classList.add('aos-fallback');
    }
}

function initToast() {
    var flashMessages = document.querySelectorAll('.alert-dismissible');
    flashMessages.forEach(function (alert) {
        setTimeout(function () {
            var bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 5000);
    });
}

function showToast(message, type) {
    type = type || 'info';
    var container = document.getElementById('toastContainer');
    if (!container) return;
    var icons = {
        success: 'fa-solid fa-circle-check',
        danger: 'fa-solid fa-circle-exclamation',
        warning: 'fa-solid fa-triangle-exclamation',
        info: 'fa-solid fa-circle-info'
    };
    var toast = document.createElement('div');
    toast.className = 'toast align-items-center text-bg-' + type + ' border-0 show';
    toast.setAttribute('role', 'alert');
    toast.innerHTML = '<div class="d-flex"><div class="toast-body"><i class="' + (icons[type] || icons.info) + ' me-2"></i>' + message + '</div><button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button></div>';
    container.appendChild(toast);
    var bsToast = new bootstrap.Toast(toast, { delay: 4000 });
    bsToast.show();
    toast.addEventListener('hidden.bs.toast', function () { toast.remove(); });
}

function getCSRFToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    if (meta) return meta.getAttribute('content');
    var input = document.querySelector('input[name="csrf_token"]');
    if (input) return input.value;
    return '';
}

function initDeleteLinks() {
    var deleteLinks = document.querySelectorAll('[data-confirm]:not(form)');
    deleteLinks.forEach(function (link) {
        link.addEventListener('click', function (e) {
            if (link.closest('form')) return;
            var msg = link.getAttribute('data-confirm') || '¿Estás seguro?';
            if (!confirm(msg)) {
                e.preventDefault();
                return;
            }
            e.preventDefault();
            var form = document.createElement('form');
            form.method = 'POST';
            form.action = link.getAttribute('href');
            form.style.display = 'none';
            var csrfInput = document.createElement('input');
            csrfInput.type = 'hidden';
            csrfInput.name = 'csrf_token';
            csrfInput.value = getCSRFToken();
            form.appendChild(csrfInput);
            document.body.appendChild(form);
            form.submit();
        });
    });
}

/* Confirmación para formularios destructivos: data-confirm-form (o
   data-confirm heredado) sobre <form>. Cancelar no ejecuta nada; al confirmar
   se deshabilitan los botones y se envía una sola vez (sin re-entrada). */
function initConfirmForms() {
    document.querySelectorAll('form[data-confirm-form], form[data-confirm]').forEach(function (form) {
        if (form.dataset.confirmBound === '1') return;
        form.dataset.confirmBound = '1';
        var msg = form.getAttribute('data-confirm-form') || form.getAttribute('data-confirm') || '¿Estás seguro de realizar esta acción?';
        form.addEventListener('submit', function (e) {
            e.preventDefault();
            if (form.dataset.enviando === '1') return;
            if (!window.confirm(msg)) return;
            form.dataset.enviando = '1';
            setTimeout(function () {
                form.querySelectorAll('button[type="submit"], input[type="submit"]').forEach(function (b) {
                    b.disabled = true;
                });
                form.submit();
            }, 0);
        });
    });
}

function initDarkMode() {
    var toggles = document.querySelectorAll('#darkModeToggle');
    toggles.forEach(function (toggle) {
        if (toggle) {
            toggle.addEventListener('click', function () {
                toggleTheme(toggle);
            });
        }
    });
    var saved = localStorage.getItem('bsTheme');
    if (saved) {
        document.documentElement.setAttribute('data-bs-theme', saved);
        updateToggleIcons(saved);
    }
}

function toggleTheme(toggle) {
    var html = document.documentElement;
    var theme = html.getAttribute('data-bs-theme') === 'dark' ? 'light' : 'dark';
    html.setAttribute('data-bs-theme', theme);
    localStorage.setItem('bsTheme', theme);
    updateToggleIcons(theme);
}

function updateToggleIcons(theme) {
    var allToggles = document.querySelectorAll('#darkModeToggle');
    allToggles.forEach(function (t) {
        var icon = t.querySelector('i');
        if (icon) {
            icon.className = theme === 'dark' ? 'fa-solid fa-moon' : 'fa-solid fa-sun';
        }
        var text = t.textContent || '';
        if (text.includes('Oscuro') || text.includes('Claro')) {
            t.innerHTML = t.innerHTML.replace(/Modo (Oscuro|Claro)/, 'Modo ' + (theme === 'dark' ? 'Oscuro' : 'Claro'));
        }
    });
}

/* ============================================================
   SIAM AJAX Module — Form submission without page reloads
   ============================================================ */

function initAjaxForms() {
    document.querySelectorAll('form[data-ajax="true"]').forEach(function (form) {
        form.addEventListener('submit', function (e) {
            e.preventDefault();
            var btn = form.querySelector('button[type="submit"], input[type="submit"]');
            var originalText = btn ? btn.innerHTML : '';
            setLoading(btn, true);
            clearFormErrors(form);

            var formData = new FormData(form);
            var url = form.getAttribute('action') || window.location.href;
            var method = form.getAttribute('method') || 'POST';

            fetch(url, {
                method: method.toUpperCase(),
                headers: {
                    'X-CSRFToken': getCSRFToken(),
                    'Accept': 'application/json'
                },
                body: formData
            })
            .then(function (response) {
                return response.json().then(function (data) {
                    return { status: response.status, data: data };
                });
            })
            .then(function (result) {
                setLoading(btn, false);
                if (result.data.success) {
                    showToast(result.data.message || 'Guardado correctamente.', 'success');
                    var redirect = form.getAttribute('data-redirect');
                    if (redirect) {
                        setTimeout(function () { window.location.href = redirect; }, 800);
                    } else if (result.data.redirect) {
                        setTimeout(function () { window.location.href = result.data.redirect; }, 800);
                    } else {
                        var table = document.querySelector('table[data-ajax-table]');
                        if (table) refreshTable(table);
                    }
                } else {
                    showToast(result.data.error || 'Error al guardar.', 'danger');
                }
            })
            .catch(function (err) {
                setLoading(btn, false);
                showToast('Error de conexión. Intenta nuevamente.', 'danger');
            });
        });
    });
}

function initAjaxDelete() {
    document.querySelectorAll('[data-ajax-delete]').forEach(function (el) {
        el.addEventListener('click', function (e) {
            e.preventDefault();
            var msg = el.getAttribute('data-confirm') || '¿Estás seguro de eliminar?';
            if (!confirm(msg)) return;
            var url = el.getAttribute('href');
            var row = el.closest('tr');

            fetch(url, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCSRFToken(),
                    'Accept': 'application/json'
                }
            })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.success) {
                    showToast('Eliminado correctamente.', 'success');
                    if (row) { row.remove(); }
                } else {
                    showToast(data.error || 'Error al eliminar.', 'danger');
                }
            })
            .catch(function () {
                showToast('Error de conexión.', 'danger');
            });
        });
    });
}

function setLoading(btn, isLoading) {
    if (!btn) return;
    if (isLoading) {
        btn._originalHTML = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status"></span> Guardando...';
    } else {
        btn.disabled = false;
        btn.innerHTML = btn._originalHTML || btn.innerHTML;
    }
}

function clearFormErrors(form) {
    form.querySelectorAll('.is-invalid').forEach(function (el) {
        el.classList.remove('is-invalid');
    });
    form.querySelectorAll('.invalid-feedback').forEach(function (el) {
        el.remove();
    });
}

function refreshTable(table) {
    if (!table) return;
    var url = table.getAttribute('data-ajax-table');
    if (!url) return;
    fetch(url, { headers: { 'Accept': 'application/json' } })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            if (data.rows) {
                var tbody = table.querySelector('tbody');
                if (tbody) tbody.innerHTML = data.rows;
            }
        })
        .catch(function () {});
}

/* ============================================================
   Geolocation / Emergency Assistance
   ============================================================ */

function initLocationButton() {
    document.querySelectorAll('[data-action="share-location"]').forEach(function (btn) {
        btn.addEventListener('click', function (e) {
            e.preventDefault();
            if (!navigator.geolocation) {
                showToast('Geolocalización no disponible en este navegador.', 'warning');
                return;
            }
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Obteniendo ubicación...';

            navigator.geolocation.getCurrentPosition(
                function (position) {
                    sendLocation(position.coords.latitude, position.coords.longitude, position.coords.accuracy, btn);
                },
                function (error) {
                    btn.disabled = false;
                    btn.innerHTML = '<i class="fa-solid fa-location-dot me-1"></i> Compartir ubicación';
                    var msg = 'No se pudo obtener la ubicación. ';
                    switch(error.code) {
                        case error.PERMISSION_DENIED: msg += 'Permiso denegado.'; break;
                        case error.POSITION_UNAVAILABLE: msg += 'No disponible.'; break;
                        case error.TIMEOUT: msg += 'Tiempo agotado.'; break;
                        default: msg += 'Error desconocido.';
                    }
                    showToast(msg, 'warning');
                },
                { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
            );
        });
    });
}

function sendLocation(lat, lng, accuracy, btn) {
    fetch('/api/ubicacion', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken(),
            'Accept': 'application/json'
        },
        body: JSON.stringify({
            latitude: lat,
            longitude: lng,
            accuracy: accuracy
        })
    })
    .then(function (r) { return r.json(); })
    .then(function (data) {
        btn.disabled = false;
        btn.innerHTML = '<i class="fa-solid fa-circle-check me-1"></i> Ubicación recibida';
        if (data.success) {
            showToast('Ubicación recibida correctamente.', 'success');
        } else {
            showToast(data.error || 'Error al enviar ubicación.', 'danger');
        }
    })
    .catch(function () {
        btn.disabled = false;
        btn.innerHTML = '<i class="fa-solid fa-location-dot me-1"></i> Compartir ubicación';
        showToast('Error al enviar ubicación.', 'danger');
    });
}

/* ============================================================
   Table client-side search — filters tbody rows by text
   ============================================================ */

function initTableSearch() {
    var inputs = document.querySelectorAll('input[data-table-search]');
    inputs.forEach(function (input) {
        var table = document.querySelector(input.getAttribute('data-table-search'));
        if (!table) return;
        input.addEventListener('input', function () {
            var q = input.value.toLowerCase().trim();
            var tbody = table.querySelector('tbody');
            if (!tbody) return;
            var rows = Array.prototype.slice.call(tbody.querySelectorAll('tr'));
            var placeholder = null;
            var visible = 0;
            rows.forEach(function (row) {
                if (row.querySelector('td[colspan]')) {
                    placeholder = row;
                    row.style.display = 'none';
                    return;
                }
                var match = !q || row.textContent.toLowerCase().indexOf(q) !== -1;
                row.style.display = match ? '' : 'none';
                if (match) visible++;
            });
            if (placeholder) {
                placeholder.style.display = (!q || visible === 0) ? '' : 'none';
            }
        });
    });
}

/* ============================================================
   Form labels — associa label con su campo (accesibilidad)
   ============================================================ */

function initFormLabels() {
    document.querySelectorAll('label.form-label').forEach(function (label) {
        if (label.getAttribute('for')) return;
        var control = label.nextElementSibling;
        if (!control) return;
        var tag = control.tagName;
        if (tag !== 'INPUT' && tag !== 'SELECT' && tag !== 'TEXTAREA') return;
        var name = control.getAttribute('name') || '';
        var id = control.getAttribute('id') || (name || 'campo') + '-' + Math.random().toString(36).slice(2, 7);
        control.setAttribute('id', id);
        label.setAttribute('for', id);
    });
}

/* ============================================================
   Chat Assistant — Modern chat UI
   ============================================================ */

function initChat() {
    var chatContainer = document.getElementById('chatMessages');
    if (!chatContainer) return;

    var form = document.getElementById('chatForm');
    var input = document.getElementById('chatInput');

    if (form && input) {
        var chatEnviando = false;
        form.addEventListener('submit', function (e) {
            e.preventDefault();
            if (chatEnviando) return;
            var text = input.value.trim();
            if (!text) return;
            chatEnviando = true;
            input.value = '';
            addChatMessage('user', text);
            showTyping();
            scrollChat();

            var submitBtn = form.querySelector('button[type="submit"], button:not([type])');
            if (submitBtn) submitBtn.disabled = true;
            if (input) input.disabled = true;

            var controller = new AbortController();
            var agotoTiempo = false;
            var timer = setTimeout(function () {
                agotoTiempo = true;
                controller.abort();
            }, 30000);

            fetch('/asistente/ask', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCSRFToken(),
                    'Accept': 'application/json'
                },
                body: JSON.stringify({ mensaje: text }),
                signal: controller.signal
            })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                clearTimeout(timer);
                hideTyping();
                if (data.respuesta) {
                    addChatMessage('assistant', data.respuesta, data.tipo, data.items, data.acciones);
                } else if (data.error) {
                    addChatMessage('assistant', 'Error: ' + data.error);
                } else {
                    addChatMessage('assistant', 'No pude procesar tu mensaje. Intenta nuevamente.');
                }
                scrollChat();
            })
            .catch(function () {
                clearTimeout(timer);
                hideTyping();
                addChatMessage('assistant',
                    agotoTiempo
                        ? 'La consulta tardó demasiado. Intenta de nuevo en unos momentos.'
                        : 'Error de conexión. Verifica tu conexión e intenta nuevamente.');
                scrollChat();
            })
            .finally(function () {
                chatEnviando = false;
                if (submitBtn) submitBtn.disabled = false;
                if (input) { input.disabled = false; input.focus(); }
            });
        });
    }

    initChatButtons();
}

function addChatMessage(role, text, type, items, acciones) {
    var container = document.getElementById('chatMessages');
    if (!container) return;

    var now = new Date();
    var time = now.getHours().toString().padStart(2, '0') + ':' + now.getMinutes().toString().padStart(2, '0');

    var div = document.createElement('div');
    div.className = 'chat-message chat-' + role + ' mb-3';
    div.setAttribute('data-aos', 'fade-up');
    div.setAttribute('data-aos-duration', '300');

    var avatar = role === 'user'
        ? '<span class="chat-avatar d-inline-flex align-items-center justify-content-center rounded-circle flex-shrink-0 bg-primary text-white order-2"><i class="fa-solid fa-user"></i></span>'
        : '<span class="chat-avatar d-inline-flex align-items-center justify-content-center rounded-circle flex-shrink-0 bg-dark border text-primary"><i class="fa-solid fa-robot"></i></span>';

    var html = '<div class="d-flex ' + (role === 'user' ? 'justify-content-end' : 'justify-content-start') + ' align-items-start gap-2">';
    html += avatar;
    html += '<div class="chat-bubble rounded-3 p-3 ' + (role === 'user' ? 'bg-primary text-white' : 'bg-dark border') + '" style="max-width: 80%;">';
    html += '<div class="chat-text">' + escapeHtml(text).replace(/\n/g, '<br>') + '</div>';
    html += '<div class="chat-time small ' + (role === 'user' ? 'text-white-50' : 'text-secondary') + ' mt-1">' + time + '</div>';

    if (type === 'lista_clientes' || type === 'lista_vehiculos' || type === 'lista_facturas') {
        if (items && items.length) {
            html += '<div class="mt-2"><a href="/' + type.replace('lista_', '') + '/" class="btn btn-sm btn-outline-primary">Ver todos</a></div>';
        }
    }

    if (acciones && acciones.length) {
        html += '<div class="mt-2 d-flex gap-2 flex-wrap chat-actions">';
        acciones.forEach(function (a) {
            var icono = a.icono ? '<i class="fa-solid ' + a.icono + ' me-1"></i>' : '';
            if (a.tipo === 'ubicacion') {
                html += '<button class="btn btn-sm btn-outline-info" data-action="share-location">' + icono + escapeHtml(a.texto) + '</button>';
            } else if (a.url) {
                html += '<a class="btn btn-sm btn-outline-primary" href="' + escapeHtml(a.url) + '">' + icono + escapeHtml(a.texto) + '</a>';
            } else {
                html += '<button class="btn btn-sm btn-outline-primary" data-action="url" data-url="' + escapeHtml(a.url || '') + '">' + icono + escapeHtml(a.texto) + '</button>';
            }
        });
        html += '</div>';
    } else if (type === 'botones' || text.includes('Compartir ubicación') || text.includes('Compartir mi ubicación')) {
        html += '<div class="mt-2 d-flex gap-2 flex-wrap chat-actions">';
        if (text.includes('ubicación') || text.includes('Ubicación')) {
            html += '<button class="btn btn-sm btn-outline-info" data-action="share-location"><i class="fa-solid fa-location-dot me-1"></i> Compartir ubicación</button>';
        }
        if (text.includes('asesor') || text.includes('Asesor')) {
            html += '<button class="btn btn-sm btn-outline-warning" onclick="showToast(\'Conectando con un asesor...\', \'info\')"><i class="fa-solid fa-user me-1"></i> Hablar con asesor</button>';
        }
        html += '</div>';
    }

    html += '</div></div>';
    div.innerHTML = html;
    container.appendChild(div);
}

function escapeHtml(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
        return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
}

function showTyping() {
    var container = document.getElementById('chatMessages');
    if (!container) return;
    var div = document.createElement('div');
    div.id = 'typingIndicator';
    div.className = 'chat-message chat-assistant mb-3';
    div.innerHTML = '<div class="d-flex justify-content-start"><div class="chat-bubble bg-dark border rounded-3 p-3"><div class="typing-dots"><span></span><span></span><span></span></div></div></div>';
    container.appendChild(div);
}

function hideTyping() {
    var el = document.getElementById('typingIndicator');
    if (el) el.remove();
}

function scrollChat() {
    var container = document.getElementById('chatMessages');
    if (container) {
        container.scrollTop = container.scrollHeight;
    }
}

function initChatButtons() {
    var container = document.getElementById('chatMessages');
    if (!container) return;
    container.addEventListener('click', function (e) {
        var btn = e.target.closest('[data-action]');
        if (!btn) return;
        e.stopPropagation();
        var action = btn.getAttribute('data-action');
        if (action === 'share-location') {
            compartirUbicacionDesdeChat(btn);
        }
    });
}

function compartirUbicacionDesdeChat(btn) {
    if (!navigator.geolocation) {
        addChatMessage('assistant', 'Tu navegador no soporta geolocalización.');
        return;
    }
    var original = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Obteniendo ubicación...';
    navigator.geolocation.getCurrentPosition(function (pos) {
        fetch('/api/ubicacion', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCSRFToken(), 'Accept': 'application/json' },
            body: JSON.stringify({
                latitude: pos.coords.latitude,
                longitude: pos.coords.longitude,
                accuracy: pos.coords.accuracy,
                descripcion: 'Solicitud de asistencia desde el asistente'
            })
        }).then(function (r) { return r.json(); })
        .then(function (data) {
            btn.disabled = false;
            btn.innerHTML = original;
            if (data.success) {
                addChatMessage('assistant', '📍 **Ubicación recibida** (solicitud #' + data.id + ')\n🚗 SIAM está buscando asistencia cercana...\n\nEstado: **Pendiente**. Te avisaremos cuando la asistencia esté en camino.');
                scrollChat();
            } else {
                addChatMessage('assistant', 'No se pudo enviar la ubicación: ' + (data.error || 'intenta nuevamente.'));
                scrollChat();
            }
        }).catch(function () {
            btn.disabled = false;
            btn.innerHTML = original;
            addChatMessage('assistant', 'Error de conexión al enviar la ubicación. Intenta nuevamente.');
            scrollChat();
        });
    }, function (err) {
        btn.disabled = false;
        btn.innerHTML = original;
        var msgs = { 1: 'Permiso denegado. Habilita la ubicación para compartirla.', 2: 'No se pudo obtener la ubicación.', 3: 'Tiempo agotado.' };
        addChatMessage('assistant', msgs[err.code] || 'Error de ubicación.');
        scrollChat();
    }, { enableHighAccuracy: true, timeout: 15000, maximumAge: 5000 });
}

/* ============================================================
   Notificaciones — campana con badge y menú
   ============================================================ */

function initNotificaciones() {
    var toggle = document.getElementById('notifToggle');
    if (!toggle) return;

    var badge = document.getElementById('notifBadge');
    var lista = document.getElementById('notifLista');
    var marcarTodas = document.getElementById('notifMarcarTodas');

    function actualizarBadge(count) {
        if (!badge) return;
        if (count > 0) {
            badge.textContent = count > 99 ? '99+' : String(count);
            badge.classList.remove('d-none');
        } else {
            badge.classList.add('d-none');
        }
    }

    function renderItems(items) {
        if (!lista) return;
        if (!items.length) {
            lista.innerHTML = '<div class="px-3 py-4 text-muted small text-center">No tienes notificaciones.</div>';
            return;
        }
        lista.innerHTML = items.map(function (n) {
            var clase = n.leida ? 'notif-item leida' : 'notif-item no-leida';
            var icono = { cita: 'fa-calendar-check', orden: 'fa-screwdriver-wrench', factura: 'fa-file-lines', cotizacion: 'fa-file-invoice-dollar', garantia: 'fa-shield-halved', recordatorio: 'fa-bell', pago: 'fa-credit-card', sistema: 'fa-circle-info' }[n.tipo] || 'fa-circle-info';
            var badgeTipo = '<span class="badge badge-soft-primary notif-tipo me-2"><i class="fa-solid ' + icono + '"></i></span>';
            var enlace = n.url ? (' href="' + n.url + '"') : '';
            return '<a' + enlace + ' class="notif-item d-flex text-decoration-none text-reset" data-id="' + n.id + '"' + (enlace ? '' : ' role="button"') + '>' +
                badgeTipo +
                '<div class="flex-grow-1 min-w-0">' +
                '<div class="d-flex justify-content-between align-items-start gap-2">' +
                '<span class="small fw-semibold text-truncate">' + n.titulo + '</span>' +
                (n.leida ? '' : '<span class="notif-punto"></span>') +
                '</div>' +
                (n.mensaje ? '<div class="small text-muted notif-msg">' + n.mensaje + '</div>' : '') +
                '</div></a>';
        }).join('');
    }

    function cargar() {
        fetch('/notificaciones/api/listar', { headers: { 'Accept': 'application/json' } })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (!data || !data.items) return;
                renderItems(data.items);
                actualizarBadge(data.items.filter(function (n) { return !n.leida; }).length);
            })
            .catch(function () {});
    }

    function marcar(id) {
        return fetch('/notificaciones/api/leer/' + id, {
            method: 'POST',
            headers: { 'X-CSRFToken': getCSRFToken(), 'Accept': 'application/json' }
        }).then(function (r) { return r.json(); });
    }

    lista.addEventListener('click', function (e) {
        var item = e.target.closest('.notif-item');
        if (!item) return;
        var id = item.getAttribute('data-id');
        if (id) marcar(id);
    });

    if (marcarTodas) {
        marcarTodas.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            fetch('/notificaciones/api/leer-todas', {
                method: 'POST',
                headers: { 'X-CSRFToken': getCSRFToken(), 'Accept': 'application/json' }
            }).then(function () { cargar(); });
        });
    }

    cargar();
    setInterval(cargar, 60000);
}
