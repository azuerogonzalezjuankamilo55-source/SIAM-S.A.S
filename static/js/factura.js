(function () {
    'use strict';

    var IVA_RATE = (typeof IVA_RATE !== 'undefined') ? IVA_RATE : 0.19;

    function calcular() {
        var rows = document.querySelectorAll('.detalle-row');
        var subtotalGeneral = 0;

        rows.forEach(function (row) {
            var precio = parseFloat(row.querySelector('.precio-input').value) || 0;
            var cant = parseInt(row.querySelector('.cantidad-input').value) || 1;
            var subtotal = precio * cant;
            row.querySelector('.subtotal-cell').textContent = '$' + subtotal.toFixed(2);
            subtotalGeneral += subtotal;
        });

        var descuento = parseFloat(document.getElementById('descuento-input').value) || 0;
        var iva = subtotalGeneral * IVA_RATE;
        var total = subtotalGeneral + iva - descuento;

        document.getElementById('subtotal-total').textContent = '$' + subtotalGeneral.toFixed(2);
        document.getElementById('iva-total').textContent = '$' + iva.toFixed(2);
        document.getElementById('descuento-total').textContent = '-$' + descuento.toFixed(2);
        document.getElementById('total-general').innerHTML = '<strong>$' + total.toFixed(2) + '</strong>';
    }

    function attachEvents(row) {
        row.querySelectorAll('.precio-input, .cantidad-input').forEach(function (el) {
            el.addEventListener('input', calcular);
        });

        var select = row.querySelector('.servicio-select');
        if (select) {
            select.addEventListener('change', function () {
                var option = this.options[this.selectedIndex];
                var precio = option ? (option.dataset.precio || 0) : 0;
                row.querySelector('.precio-input').value = precio;
                calcular();
            });
        }

        var removeBtn = row.querySelector('.remove-row');
        if (removeBtn) {
            removeBtn.addEventListener('click', function () {
                if (document.querySelectorAll('.detalle-row').length > 1) {
                    row.remove();
                    calcular();
                }
            });
        }
    }

    document.addEventListener('DOMContentLoaded', function () {
        var addBtn = document.getElementById('add-row');
        if (addBtn) {
            addBtn.addEventListener('click', function () {
                var tbody = document.querySelector('#detalles-table tbody');
                var firstRow = tbody.querySelector('.detalle-row');
                var clone = firstRow.cloneNode(true);
                clone.querySelectorAll('input, select').forEach(function (el) { el.value = ''; });
                clone.querySelector('.cantidad-input').value = 1;
                clone.querySelector('.subtotal-cell').textContent = '$0.00';
                tbody.appendChild(clone);
                attachEvents(clone);
                calcular();
            });
        }

        document.querySelectorAll('.detalle-row').forEach(attachEvents);
        calcular();
    });

})();
