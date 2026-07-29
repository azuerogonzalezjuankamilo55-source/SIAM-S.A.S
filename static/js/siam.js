document.addEventListener('DOMContentLoaded', function () {
    initTooltips();
    initSidebar();
    initAnimations();
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
