import csv
import re
from pathlib import Path
from playwright.sync_api import sync_playwright

PASTA_ERROS = Path("erros")
PASTA_ERROS.mkdir(exist_ok=True)

URL_PEC = "https://aparecidadotaboado.esus.ms.gov.br/"
URL_CADASTRO = (
    "https://aparecidadotaboado.esus.ms.gov.br/"
    "gestaoCadastros/cadastro-individual"
)

ARQUIVO_ENTRADA = "cadastros.csv"
ARQUIVO_RESULTADO = "resultado.csv"

PAUSA_ENTRE_CADASTROS = 1500


def somente_numeros(valor):
    return re.sub(r"\D", "", str(valor))


def validar_dados(cpf, cep):
    cpf = somente_numeros(cpf)
    cep = somente_numeros(cep)

    if len(cpf) != 11:
        raise ValueError("CPF não possui 11 dígitos")

    if len(cep) != 8:
        raise ValueError("CEP não possui 8 dígitos")

    return cpf, cep


def registrar_resultado(cpf, cep, status, observacao=""):
    arquivo_existe = Path(ARQUIVO_RESULTADO).exists()

    with open(
        ARQUIVO_RESULTADO,
        "a",
        newline="",
        encoding="utf-8-sig"
    ) as arquivo:

        writer = csv.writer(arquivo)

        if not arquivo_existe:
            writer.writerow([
                "CPF",
                "CEP",
                "STATUS",
                "OBSERVACAO"
            ])

        writer.writerow([
            cpf,
            cep,
            status,
            observacao
        ])


def alterar_cep(page, cpf, cep):

    print("\n" + "=" * 60)
    print("Processando CPF:", cpf)
    print("Novo CEP:", cep)
    print("=" * 60)

    # --------------------------------------------------
    # 1. Abre Cadastro Individual
    # --------------------------------------------------

    page.goto(
        URL_CADASTRO,
        wait_until="domcontentloaded"
    )

    page.wait_for_timeout(1000)

    # --------------------------------------------------
    # 2. Pesquisa CPF
    # --------------------------------------------------

    busca = page.locator(
        "input[name='nomeCpfCns']"
    )

    busca.wait_for(
        state="visible",
        timeout=10000
    )

    busca.fill(cpf)

    page.get_by_role(
        "button",
        name="Buscar cadastro"
    ).click()

    page.wait_for_timeout(1500)

    # --------------------------------------------------
    # 3. Confirma que encontrou um cadastro
    # --------------------------------------------------

    visualizar = page.get_by_text(
        "Visualizar",
        exact=True
    )

    if visualizar.count() != 1:
        raise Exception(
            f"Esperava 1 cadastro, mas encontrei "
            f"{visualizar.count()} resultado(s)"
        )

    visualizar.click()

    page.wait_for_timeout(1200)

    # --------------------------------------------------
    # 4. Atualizar cadastro
    # --------------------------------------------------

    page.get_by_role(
        "button",
        name="Atualizar cadastro"
    ).click()

    page.wait_for_timeout(800)

    # --------------------------------------------------
    # 5. Continuar sem login
    # --------------------------------------------------

    continuar = page.get_by_role(
        "button",
        name="Continuar sem login"
    )

    continuar.wait_for(
        state="visible",
        timeout=10000
    )

    continuar.click()

    # --------------------------------------------------
    # 6. Aguarda formulário
    # --------------------------------------------------

    campo_cep = page.locator(
        "input[name='endereco.cep']"
    )

    campo_cep.wait_for(
        state="visible",
        timeout=10000
    )

    # --------------------------------------------------
    # 7. Guarda endereço ANTES
    # --------------------------------------------------

    campos_protegidos = {
        "UF": "input[name='endereco.uf']",
        "Município": "input[name='endereco.municipio']",
        "Bairro": "input[name='endereco.bairro']",
        "Tipo logradouro": "input[name='endereco.tipoLogradouro']",
        "Logradouro": "input[name='endereco.logradouro']",
        "Número": "input[name='endereco.numero']",
        "Complemento": "input[name='endereco.complemento']",
        "Ponto de referência": "input[name='endereco.pontoReferencia']",
    }

    antes = {}

    for nome, seletor in campos_protegidos.items():
        antes[nome] = page.locator(
            seletor
        ).input_value()

    cep_anterior = campo_cep.input_value()

    print("CEP anterior:", repr(cep_anterior))

    # --------------------------------------------------
    # 8. ALTERA SOMENTE O CEP
    # --------------------------------------------------

    cep_atual_numeros = somente_numeros(cep_anterior)

    if cep_atual_numeros == cep:
        print("✓ CEP já estava correto.")
        print("Não será necessário salvar.")

        return cep_anterior, cep_anterior, True

    else:
        print(
            f"Alterando CEP: "
            f"{cep_anterior!r} -> {cep}"
        )

        campo_cep.scroll_into_view_if_needed()
        campo_cep.click()

        campo_cep.press("Control+A")
        campo_cep.press("Backspace")

        campo_cep.press_sequentially(
            cep,
            delay=80
        )

        # NÃO clicar em Pesquisar
        campo_cep.press("Tab")

        # Dá tempo para o PEC processar o campo
        page.wait_for_timeout(2000)

    cep_depois = campo_cep.input_value()

    print("CEP no campo:", repr(cep_depois))

    # --------------------------------------------------
    # 9. Valida CEP
    # --------------------------------------------------

    cep_resultante = somente_numeros(
        cep_depois
    )

    if cep_resultante != cep:
        raise Exception(
            f"CEP não ficou correto. "
            f"Esperado: {cep} | "
            f"Encontrado: {cep_depois}"
        )

    # --------------------------------------------------
    # 10. Confere os outros campos
    # --------------------------------------------------

    alteracoes_indevidas = []

    for nome, seletor in campos_protegidos.items():

        depois = page.locator(
            seletor
        ).input_value()

        if antes[nome] != depois:
            alteracoes_indevidas.append(
                f"{nome}: "
                f"{antes[nome]!r} -> {depois!r}"
            )

    if alteracoes_indevidas:

        detalhes = "; ".join(
            alteracoes_indevidas
        )

        raise Exception(
            "Outro campo do endereço mudou: "
            + detalhes
        )

    print(
        "✓ Demais campos do endereço "
        "permaneceram iguais."
    )

    # --------------------------------------------------
    # 11. Confere campo SITUAÇÃO DE RUA
    # --------------------------------------------------

    situacao_sim = page.locator(
        "input[name='statusSituacaoRua'][value='SIM']"
    )

    situacao_nao = page.locator(
        "input[name='statusSituacaoRua'][value='NAO']"
    )

    sim_marcado = situacao_sim.is_checked()
    nao_marcado = situacao_nao.is_checked()

    if not sim_marcado and not nao_marcado:

        print(
            "⚠ Campo situação de rua não preenchido."
        )

        print(
            "Marcando NÃO..."
        )

        # situacao_nao.check(force=True)
        try:
            situacao_nao.focus()
            situacao_nao.press("Space")
            page.wait_for_timeout(300)

            if not situacao_nao.is_checked():
                situacao_nao.check(force=True)

        except Exception:
            situacao_nao.focus()
            situacao_nao.press("Space")

        page.wait_for_timeout(500)

        if not situacao_nao.is_checked():
            raise Exception(
                "Não foi possível marcar 'Não' no campo situação de rua."
            )

        page.wait_for_timeout(500)

        # Confirma que realmente marcou
        if not situacao_nao.is_checked():
            raise Exception(
                "Não foi possível marcar "
                "'Não' no campo situação de rua."
            )

        print(
            "✓ Situação de rua marcada como NÃO."
        )

    elif sim_marcado:

        print(
            "✓ Situação de rua já estava preenchida: SIM."
        )

    else:

        print(
            "✓ Situação de rua já estava preenchida: NÃO."
        )

    # --------------------------------------------------
    # 12. Salvar
    # --------------------------------------------------

    salvar = page.locator(
        "button[data-cy='FormFooter.salvar']"
    )

    salvar.wait_for(
        state="visible",
        timeout=10000
    )

    salvar.scroll_into_view_if_needed()

    print(
        "Aguardando o PEC ficar pronto para salvar..."
    )

    page.wait_for_timeout(3000)

    print("Salvando...")

    try:

        salvar.click(
            timeout=10000
        )

    except Exception:

        print(
            "O botão está visível, mas algum elemento "
            "do PEC está bloqueando o clique."
        )

        print(
            "Tentando acionar o botão pelo teclado..."
        )

        salvar.focus()
        salvar.press("Enter")

    # --------------------------------------------------
    # 13. Aguarda confirmação do salvamento
    # --------------------------------------------------

    print(
        "Aguardando confirmação do salvamento..."
    )

    # Agora espera até 60 segundos
    for tentativa in range(60):

        page.wait_for_timeout(1000)

        if "/edit" not in page.url:
            break

    else:
        raise Exception(
            "O PEC permaneceu na tela de edição "
            "por 60 segundos após a tentativa de salvar."
        )

    print("✓ Cadastro salvo.")
    print("URL:", page.url)

    return cep_anterior, cep_depois, False


# ======================================================
# PROGRAMA PRINCIPAL
# ======================================================

with open(
    ARQUIVO_ENTRADA,
    "r",
    encoding="utf-8-sig"
) as arquivo:

    registros = list(
        csv.DictReader(arquivo)
    )


print(
    f"\n{len(registros)} cadastro(s) "
    "encontrado(s) na planilha."
)


with sync_playwright() as p:

    browser = p.chromium.launch(
        headless=False
    )

    page = browser.new_page()

    # --------------------------------------------------
    # Login manual
    # --------------------------------------------------

    page.goto(
        URL_PEC,
        wait_until="domcontentloaded"
    )

    print("\nFaça o login manualmente no PEC.")

    input(
        "Quando estiver logada, "
        "pressione ENTER aqui... "
    )

    # --------------------------------------------------
    # Processa planilha
    # --------------------------------------------------

    for numero, registro in enumerate(
        registros,
        start=1
    ):

        cpf_original = registro.get(
            "CPF",
            ""
        )

        cep_original = registro.get(
            "CEP",
            ""
        )

        print(
            f"\n[{numero}/{len(registros)}]"
        )

        try:

            cpf, cep = validar_dados(
                cpf_original,
                cep_original
            )

            cep_anterior, cep_gravado, cep_ja_estava_correto = alterar_cep(
                page,
                cpf,
                cep
            )

            if cep_ja_estava_correto:
                registrar_resultado(
                    cpf,
                    cep,
                    "CEP JÁ ESTAVA CORRETO",
                    f"CEP atual: {cep_anterior}"
                )

            else:
                registrar_resultado(
                    cpf,
                    cep,
                    "OK",
                    f"CEP anterior: {cep_anterior}; "
                    f"novo: {cep_gravado}"
                )

        except Exception as erro:

            print("\n❌ ERRO:")
            print(erro)

            cpf_limpo = somente_numeros(
                cpf_original
            )

            cep_limpo = somente_numeros(
                cep_original
            )

            # Tira um print da tela no momento do erro
            try:

                caminho_print = (
                    PASTA_ERROS /
                    f"{cpf_limpo}_erro.png"
                )

                page.screenshot(
                    path=str(caminho_print),
                    full_page=True
                )

                print(
                    f"📸 Print do erro salvo em: "
                    f"{caminho_print}"
                )

            except Exception as erro_print:

                print(
                    "Não foi possível salvar "
                    "o print do erro:"
                )

                print(erro_print)

            registrar_resultado(
                cpf_limpo,
                cep_limpo,
                "ERRO",
                str(erro)
            )

            print(
                "Pulando para o próximo cadastro..."
            )

        page.wait_for_timeout(
            PAUSA_ENTRE_CADASTROS
        )

    print("\n" + "=" * 60)
    print("PROCESSAMENTO FINALIZADO")
    print("=" * 60)

    input(
        "\nPressione ENTER para "
        "fechar o navegador..."
    )

    browser.close()
