/* Paginacao: salto direto e navegacao por teclado.
 *
 * Por que existe: o campo "ir para pagina" precisa preservar os filtros da
 * URL atual. Se a pessoa filtrou por setor e salta para a pagina 37, o
 * filtro tem de continuar valendo — senao ela perde o contexto e acha que
 * o sistema "voltou tudo".
 */
(function () {
    'use strict';

    function irPara(pagina, form) {
        var url = new URL(window.location.href);
        url.searchParams.set('page', pagina);
        window.location.href = url.toString();
    }

    function iniciarSalto() {
        document.querySelectorAll('[data-pgn-form]').forEach(function (form) {
            var input = form.querySelector('[data-pgn-input]');
            if (!input) return;

            form.addEventListener('submit', function (evento) {
                evento.preventDefault();
                var valor = parseInt(input.value, 10);
                var max = parseInt(input.getAttribute('max'), 10) || 1;
                if (isNaN(valor)) return;
                if (valor < 1) valor = 1;
                if (valor > max) valor = max;
                irPara(valor, form);
            });
        });
    }

    function iniciarTeclado() {
        document.querySelectorAll('[data-pgn]').forEach(function (pgn) {
            var campo = pgn.querySelector('[data-pgn-input]');
            // So age quando o foco esta dentro da paginacao, para nao
            // sequestrar as setas de quem esta digitando num filtro.
            pgn.addEventListener('keydown', function (evento) {
                if (evento.target === campo) return;

                var mapa = {
                    Home: 'first',
                    End: 'last',
                    ArrowLeft: 'prev',
                    ArrowRight: 'next'
                };
                var alvo = mapa[evento.key];
                if (!alvo) return;

                var link = pgn.querySelector('[data-tecla="' + evento.key + '"]');
                if (link) {
                    evento.preventDefault();
                    window.location.href = link.getAttribute('href');
                }
            });
        });
    }

    function iniciar() {
        iniciarSalto();
        iniciarTeclado();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', iniciar);
    } else {
        iniciar();
    }
})();
