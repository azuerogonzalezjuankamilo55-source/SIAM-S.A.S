document.addEventListener('DOMContentLoaded', function () {
    initTooltips();
    initSidebar();
    initAnimations();
    initToast();
    initConfirmDialogs();
    initDeleteLinks();
    initDarkMode();
    initAjaxForms();
    initAjaxDelete();
    initLocationButton();
});

function initTooltips() {
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (el) {
        return new bootstrap.Tooltip(el);
    });
}

function initSidebar() {
    var toggler = document.querySelector('[data-bs-toggle="collapse"][data-bs-target=".sidebar"]');
    if (toggler) {
        toggler.addEventListener('click', function () {
            document.querySelector('.sidebar').classList.toggle('show');
        });
    }
    var navLinks = document.querySelectorAll('.sidebar .nav-link');
    var currentPath = window.location.pathname;
    navLinks.forEach(function (link) {
        if (link.getAttribute('href') === currentPath) {
            link.classList.add('active');
        }
    });
}

function initAnimations() {
    if (typeof AOS !== 'undefined') {
        AOS.init({
            duration: 600,
            once: true,
            offset: 50,
        });
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
        success: 'bi-check-circle-fill',
        danger: 'bi-exclamation-circle-fill',
        warning: 'bi-exclamation-triangle-fill',
        info: 'bi-info-circle-fill'
    };
    var toast = document.createElement('div');
    toast.className = 'toast align-items-center text-bg-' + type + ' border-0 show';
    toast.setAttribute('role', 'alert');
    toast.innerHTML = '<div class="d-flex"><div class="toast-body"><i class="bi ' + (icons[type] || icons.info) + ' me-2"></i>' + message + '</div><button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button></div>';
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

function initConfirmDialogs() {
    document.querySelectorAll('[data-confirm]').forEach(function (el) {
        el.addEventListener('click', function (e) {
            var msg = el.getAttribute('data-confirm') || '¿Estás seguro?';
            if (!confirm(msg)) {
                e.preventDefault();
            }
        });
    });
}

function initDeleteLinks() {
    var deleteLinks = document.querySelectorAll('[data-confirm]');
    deleteLinks.forEach(function (link) {
        link.addEventListener('click', function (e) {
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

function initDarkMode() {
    var toggles = document.querySelectorAll('#darkModeToggle, #darkModeToggleSidebar');
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
    var allToggles = document.querySelectorAll('#darkModeToggle, #darkModeToggleSidebar');
    allToggles.forEach(function (t) {
        var icon = t.querySelector('i');
        if (icon) {
            icon.className = theme === 'dark' ? 'bi bi-moon-stars' : 'bi bi-sun';
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
                    btn.innerHTML = '<i class="bi bi-geo-alt me-1"></i> Compartir ubicación';
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
        btn.innerHTML = '<i class="bi bi-check-circle me-1"></i> Ubicación recibida';
        if (data.success) {
            showToast('Ubicación recibida correctamente.', 'success');
        } else {
            showToast(data.error || 'Error al enviar ubicación.', 'danger');
        }
    })
    .catch(function () {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-geo-alt me-1"></i> Compartir ubicación';
        showToast('Error al enviar ubicación.', 'danger');
    });
}

/* ============================================================
   Dashboard Auto-Refresh (polling ligero)
   ============================================================ */

if (document.getElementById('dashboardStats')) {
    setInterval(function () {
        var container = document.getElementById('dashboardStats');
        if (!container) return;
        var url = container.getAttribute('data-refresh-url') || '/dashboard/api/stats';
        fetch(url, { headers: { 'Accept': 'application/json' } })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                Object.keys(data).forEach(function (key) {
                    var el = document.getElementById('stat-' + key);
                    if (el) el.textContent = data[key];
                });
            })
            .catch(function () {});
    }, 30000);
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
        form.addEventListener('submit', function (e) {
            e.preventDefault();
            var text = input.value.trim();
            if (!text) return;
            input.value = '';
            addChatMessage('user', text);
            showTyping();
            scrollChat();

            fetch('/asistente/ask', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCSRFToken(),
                    'Accept': 'application/json'
                },
                body: JSON.stringify({ mensaje: text })
            })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                hideTyping();
                if (data.respuesta) {
                    addChatMessage('assistant', data.respuesta, data.tipo, data.items);
                } else if (data.error) {
                    addChatMessage('assistant', 'Error: ' + data.error);
                }
                scrollChat();
            })
            .catch(function () {
                hideTyping();
                addChatMessage('assistant', 'Error de conexión. Intenta nuevamente.');
                scrollChat();
            });
        });
    }

    initChatButtons();
}

function addChatMessage(role, text, type, items) {
    var container = document.getElementById('chatMessages');
    if (!container) return;

    var now = new Date();
    var time = now.getHours().toString().padStart(2, '0') + ':' + now.getMinutes().toString().padStart(2, '0');

    var div = document.createElement('div');
    div.className = 'chat-message chat-' + role + ' mb-3';
    div.setAttribute('data-aos', 'fade-up');
    div.setAttribute('data-aos-duration', '300');

    var html = '<div class="d-flex ' + (role === 'user' ? 'justify-content-end' : 'justify-content-start') + '">';
    html += '<div class="chat-bubble rounded-3 p-3 ' + (role === 'user' ? 'bg-primary text-white' : 'bg-dark border') + '" style="max-width: 80%;">';
    html += '<div class="chat-text">' + text.replace(/\n/g, '<br>') + '</div>';
    html += '<div class="chat-time small ' + (role === 'user' ? 'text-white-50' : 'text-secondary') + ' mt-1">' + time + '</div>';

    if (type === 'lista_clientes' || type === 'lista_vehiculos' || type === 'lista_facturas') {
        if (items && items.length) {
            html += '<div class="mt-2"><a href="/' + type.replace('lista_', '') + '/" class="btn btn-sm btn-outline-primary">Ver todos</a></div>';
        }
    }

    if (type === 'botones' || text.includes('Compartir ubicación') || text.includes('Compartir mi ubicación')) {
        html += '<div class="mt-2 d-flex gap-2 flex-wrap chat-actions">';
        if (text.includes('ubicación') || text.includes('Ubicación')) {
            html += '<button class="btn btn-sm btn-outline-info" data-action="share-location"><i class="bi bi-geo-alt me-1"></i> Compartir ubicación</button>';
        }
        if (text.includes('asesor') || text.includes('Asesor')) {
            html += '<button class="btn btn-sm btn-outline-warning" onclick="showToast(\'Conectando con un asesor...\', \'info\')"><i class="bi bi-person me-1"></i> Hablar con asesor</button>';
        }
        html += '</div>';
    }

    html += '</div></div>';
    div.innerHTML = html;
    container.appendChild(div);
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
    document.querySelectorAll('.chat-actions button').forEach(function (btn) {
        btn.addEventListener('click', function (e) {
            e.stopPropagation();
            var action = btn.getAttribute('data-action');
            if (action === 'share-location') {
                btn.click();
            }
        });
    });
}
