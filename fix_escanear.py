# Read the file
with open('core/templates/core/industria/escanear.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the end of the file and fix it
old_end = '''            const media = nGaps > 0 ? somaGaps / nGaps : 9999;
                        const veioDeLeitor = nGaps >= 3 && media <= GAP_LEITOR;
                        timer = setTimeout(function () {
                            if (campo.value.trim().length >= MIN_CHARS) enviar();
                        }, veioDeLeitor ? ESPERA_LEITOR : ESPERA_HUMANO);
                    });

                    // Enter envia na hora
                    campo.addEventListener('keydown', function (e) {
                        if (e.key === 'Enter') {
                            e.preventDefault();
                            clearTimeout(timer);
                            enviar();
                        }
                    });
                })();
            </script>

            <style>
            /* ---- Botões de mesa (grid responsivo) ---- */
            .prod-mesa-btns {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(85px, 1fr));
                gap: 8px;
                margin-top: 12px;
            }

            .prod-btn-mesa {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                gap: 6px;
                min-height: 50px;
                padding: 0 16px;
                border-radius: var(--cv-radius);
                font-size: 0.95rem;
                font-weight: 600;
                border: 2px solid var(--cv-line);
                background: var(--cv-surface);
                color: var(--cv-text);
                text-decoration: none;
                cursor: pointer;
                transition: all var(--cv-dur) var(--cv-ease);
            }
            .prod-btn-mesa:hover {
                border-color: var(--cv-blue);
                background: var(--cv-blue-soft);
                color: var(--cv-blue);
                transform: translateY(-1px);
                box-shadow: var(--cv-shadow-sm);
            }
            .prod-btn-mesa:active {
                transform: translateY(0);
            }
            </style>
            {% endblock %}'''

new_end = '''            const media = nGaps > 0 ? somaGaps / nGaps : 9999;
            const veioDeLeitor = nGaps >= 3 && media <= GAP_LEITOR;
            timer = setTimeout(function () {
                if (campo.value.trim().length >= MIN_CHARS) enviar();
            }, veioDeLeitor ? ESPERA_LEITOR : ESPERA_HUMANO);
        });

        // Enter envia na hora
        campo.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                clearTimeout(timer);
                enviar();
            }
        });
    })();
</script>

<style>
/* ---- Botões de mesa (grid responsivo) ---- */
.prod-mesa-btns {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(85px, 1fr));
    gap: 8px;
    margin-top: 12px;
}

.prod-btn-mesa {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    min-height: 50px;
    padding: 0 16px;
    border-radius: var(--cv-radius);
    font-size: 0.95rem;
    font-weight: 600;
    border: 2px solid var(--cv-line);
    background: var(--cv-surface);
    color: var(--cv-text);
    text-decoration: none;
    cursor: pointer;
    transition: all var(--cv-dur) var(--cv-ease);
}
.prod-btn-mesa:hover {
    border-color: var(--cv-blue);
    background: var(--cv-blue-soft);
    color: var(--cv-blue);
    transform: translateY(-1px);
    box-shadow: var(--cv-shadow-sm);
}
.prod-btn-mesa:active {
    transform: translateY(0);
}
</style>
{% endblock %}'''

if old_end in content:
    content = content.replace(old_end, new_end)
    with open('core/templates/core/industria/escanear.html', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Fixed!")
else:
    print("Pattern not found!")
    # Let's find what's actually there
    idx = content.find('const media = nGaps > 0')
    if idx >= 0:
        print("Found at:", idx)
        print(content[idx:idx+500])