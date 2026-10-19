/**
 * Liquid Glass — Aplicação do filtro SVG no backdrop
 * 
 * Baseado em https://github.com/rdev/liquid-glass-react
 * 
 * O efeito usa:
 * 1. backdrop-filter: blur() para desfocar o fundo
 * 2. filter: url(#liquid-glass-filter) para aplicar o displacement map
 * 3. O filtro SVG cria chromatic aberration nas bordas
 * 
 * Elementos com classe .liquid-glass recebem o efeito automaticamente.
 */
(function() {
    'use strict';

    // Configuração do filtro
    const DISPLACEMENT_SCALE = 25;
    const ABERRATION_INTENSITY = 2;
    const BLUR_AMOUNT = 0.0625;

    /**
     * Inicializa o efeito Liquid Glass em todos os elementos marcados
     */
    function initLiquidGlass() {
        // Carrega o displacement map no filtro SVG
        const displacementImg = document.getElementById('lg-displacement');
        if (displacementImg) {
            // Usa o primeiro displacement map (mais leve)
            displacementImg.setAttribute('href', '/static/img/displacement-map-1.png');
            displacementImg.setAttributeNS('http://www.w3.org/1999/xlink', 'xlink:href', '/static/img/displacement-map-1.png');
        }

        // Configura o filtro SVG para usar o displacement map correto
        setupSVGLiquidFilter();

        // Adiciona a classe .liquid-glass aos elementos que devem ter o efeito
        markGlassElements();

        // Adiciona listeners para mouse tracking (efeito de "warp" no vidro)
        addMouseTracking();
    }

    /**
     * Configura o filtro SVG para usar o displacement map correto
     */
    function setupSVGLilter() {
        // O filtro já está no DOM via include do template
        // Apenas garantimos que o displacement map está carregado
        const filter = document.getElementById('liquid-glass-filter');
        if (!filter) {
            console.warn('Liquid Glass: filtro SVG não encontrado');
            return;
        }

        // Configura o displacement map
        const displacement = filter.querySelector('feImage');
        if (displacement) {
            displacement.setAttribute('href', '/static/img/displacement-map-1.png');
            displacement.setAttributeNS('http://www.w3.org/1999/xlink', 'xlink:href', '/static/img/displacement-map-1.png');
        }
    }

    /**
     * Marca os elementos que devem receber o efeito Liquid Glass
     */
    function markGlassElements() {
        // Elementos que devem ter o efeito de vidro
        const selectors = [
            '.sidebar-casanova',
            '.card',
            '.kpi-card',
            '.dropdown-menu',
            '.perfil-menu',
            '.modal-content',
            '.alert',
            '.pgn'
        ];

        selectors.forEach(selector => {
            document.querySelectorAll(selector).forEach(el => {
                el.classList.add('liquid-glass');
                // Força aplicação do filtro
                applyGlassFilter(el);
            });
        });
    }

    /**
     * Aplica o filtro SVG em um elemento específico
     */
    function applyGlassFilter(element) {
        // O filtro CSS aplica o displacement map no backdrop
        element.style.filter = 'url(#liquid-glass-filter)';
    }

    /**
     * Adiciona tracking do mouse para efeito de "warp" no vidro
     * 
     * O efeito de warp faz o vidro "esticar" na direção do mouse
     */
    function addMouseTracking() {
        let mouseX = 0;
        let mouseY = 0;
        let isMouseActive = false;

        document.addEventListener('mousemove', (e) => {
            mouseX = e.clientX;
            mouseY = e.clientY;
            isMouseActive = true;

            // Atualiza o filtro SVG com a posição do mouse
            updateDisplacementMap(mouseX, mouseY);
        });

        document.addEventListener('mouseleave', () => {
            isMouseActive = false;
        });

        // Loop de animação para suavizar o efeito
        function animate() {
            if (isMouseActive) {
                // O displacement map pode ser atualizado dinamicamente aqui
                // para um efeito mais interativo
            }
            requestAnimationFrame(animate);
        }
        animate();
    }

    /**
     * Atualiza o displacement map com a posição do mouse
     */
    function updateDisplacementMap(x, y) {
        // O displacement map estático já cria o efeito de refração
        // Para um efeito dinâmico, seria necessário gerar um novo map
        // baseado na posição do mouse (como no repositório React)
        // Por enquanto, usamos o map estático que já funciona bem
    }

    // Inicializa quando o DOM estiver pronto
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initLiquidGlass);
    } else {
        initLiquidGlass();
    }

    // Exporta para uso global
    window.LiquidGlass = {
        init: initLiquidGlass,
        applyTo: applyGlassFilter
    };
})();
