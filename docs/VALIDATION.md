# Validação da prévia

Os testes automatizados cobrem a política real compilada em Rust e o fluxo Qt de prova interna. Não equivalem a auditoria de segurança nem validam um modo de quiosque do Windows.

Ambiente desta entrega: Windows 11 x64, Python 3.13.7, Rust 1.97.1, PySide6/Qt 6.11.2 e PyInstaller 6.22.3. A suíte passou com **25 testes**. Tanto a versão empacotada em pasta quanto o executável único passaram no percurso interno, importação da extensão Rust, carregamento/conteúdo HTTPS e rejeição de navegação para uma origem não permitida. Os dois processos de validação encerraram com código 0. O executável único tem 214.578.644 bytes nesta entrega.

Foi encontrada e corrigida uma contaminação de dependências pelo `PATH` da máquina: o empacotador capturava uma biblioteca ICU de outro software. O script de build agora limita o `PATH` durante o empacotamento e limpa o cache de análise antes de gerar a distribuição.

## Testes

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Casos: origens parecidas, usuário em URL, mudança de protocolo/porta, subdomínios, URLs especiais, validação de arquivo, senha incorreta, round-trip de configuração, correção, respostas não preenchidas, preservação das respostas ao navegar, expiração única, resposta depois do prazo, falha de gravação, consentimento e bloqueio de recursos/páginas.

## Teste do executável

```powershell
$process = Start-Process -FilePath .\dist\ClaraExam.exe -ArgumentList '--smoke-test', 'build/validation-exe' -WindowStyle Hidden -PassThru -Wait
$process.ExitCode
Get-Content build/validation-exe/smoke-result.json
```

Esse modo de teste usa a plataforma offscreen do Qt, grava capturas das telas, percorre uma prova interna e instancia o Chromium empacotado. Abre `https://example.com` para conferir uma página HTTPS e testa o bloqueio de navegação para um endereço fora da lista. Os resultados de carregamento dependem da rede. Desativa aceleração de GPU apenas nesse modo de teste; o navegador normal preserva sua configuração padrão. Nenhuma opção desativa o sandbox do Chromium.

O modo de teste mantém os dados dentro do diretório de saída, sem criar sessões reais no perfil do usuário. Registra `packaged: true` quando executado pelo `.exe`. O arquivo `smoke-error.txt`, caso gerado, contém a falha. Use uma pasta nova a cada rodada para não confundir registros anteriores.

Ainda é necessário validar o aplicativo visualmente no desktop nativo, em máquinas limpas, com alunos/professores e com as plataformas de provas escolhidas, incluindo autenticação e envio de respostas.

## Correção de tema claro

O teste original offscreen não revelou a herança da paleta escura do Windows. A inicialização agora usa uma paleta clara completa, solicita o esquema claro ao Qt e define os indicadores das alternativas explicitamente. O teste de abertura começa com uma paleta escura para verificar essa correção.

O argumento adicional `--native-theme-test` usa o plugin Windows do Qt, mantendo as janelas de teste fora da tela para não interferir na sessão aberta. Foram inspecionadas as capturas de instruções, alternativas e resultado geradas com a renderização nativa e escala de 150%. A caixa de confirmação tem fundo claro, e as alternativas usam um indicador verde para a seleção.

## Recursos do Google Forms

A suíte foi ampliada para 35 testes: permissões de recursos separadas das de navegação, escopo por plataforma/tipo de recurso, redirecionamento de links curtos e rejeição de domínios parecidos. O formulário fornecido pelo usuário foi aberto sem preencher ou enviar respostas. Suas quatro folhas de estilo externas carregaram, com fontes e cartões restaurados. A requisição opcional para `play.google.com/log` permanece bloqueada e registrada no diagnóstico, sem exibir um aviso de página incompleta.

O modo de validação aceita `--external-url URL` para conferir uma página específica; ele não preenche campos nem envia formulários. A verificação do Google Forms exige presença do formulário, carregamento dos estilos e ausência de bloqueios de scripts/fontes. A entrega de respostas e formulários que exigem login não foram testados.

O executável atualizado foi compilado com sucesso. A tentativa de executar a validação final desse binário com a URL fornecida foi rejeitada pela política da ferramenta, sem justificativa específica além de `blocked by policy`. Portanto, a validação do formulário descrita acima ocorreu na execução pelo código-fonte; não há confirmação dessa checagem no binário final desta correção.

## Bloqueio de atalhos

Após a integração, passaram 53 testes Python e 3 testes Rust. Os testes Rust verificam combinações, teclas dos dois lados, repetição/liberação e preservação de digitação/AltGr. O teste nativo instala o gancho real, confere atividade, rejeita instalação duplicada, remove e reinstala o gancho e verifica liberação ao descartar o objeto. Não injeta Alt+Tab ou outros atalhos no desktop do usuário.

Os testes de interface verificam liberação antes de salvar o resultado, término/tempo/saída autorizada, senha incorreta, falha de instalação, falha de criação da sessão, interrupção da thread e retorno à tela cheia. Nenhum teste valida isolamento completo ou resistência a manipulação por administrador.

O modo `--smoke-test PASTA --native-theme-test --local-only` permite conferir o executável e o ciclo de bloqueio em uma prova local de exemplo, sem abrir sites. Ele também libera o gancho se a validação falhar.

O novo `dist/ClaraExam-atalhos.exe` passou nesse percurso local com código de saída 0: núcleo Rust carregado, prova interna concluída, gancho instalado e liberado e tema claro preservado sobre uma paleta escura. O resultado registra `packaged: true` e `network_tested: false`; esse teste não repete a validação de plataformas externas. Evidência em `docs/keyboard-validation.json`.

Referências: [LowLevelKeyboardProc](https://learn.microsoft.com/en-us/windows/win32/winmsg/lowlevelkeyboardproc) e [SetWindowsHookExW](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setwindowshookexw).

## Abertura do login do Google Forms

A suíte Python passou com 69 testes. A política permite a origem HTTPS exata `accounts.google.com` apenas no perfil Google Forms e seus recursos auxiliares já autorizados. Os testes cobrem redirecionamento, retorno ao formulário, origens falsas, protocolo/porta incorretos, escopo por plataforma e links de nova janela acionados pelo usuário. Links de login elegíveis carregam na página atual; outros pop-ups permanecem bloqueados. Não houve alteração no bloqueio de teclado.

`scripts/check_google_login.py` abriu o formulário e seu destino de autenticação no Qt WebEngine real, usando o plugin Windows com a janela oculta. Encerrou com código 0 e confirmou a página `/v3/signin/identifier`, o campo de identificação e quatro folhas de estilo. Não preencheu campos nem enviou respostas ou credenciais. Requisições opcionais de telemetria e favicon continuam bloqueadas sem aviso de falha da página. Evidência em `docs/google-login-validation.json`; captura local em `build/google-login/login.png`.

Isso confirma a abertura da tela, não uma autenticação completa. O Google pode rejeitar navegadores embutidos, conforme sua [documentação](https://support.google.com/accounts/answer/7675428?hl=en). Não foram testados senha, segundo fator, passkeys, SSO institucional ou submissão de prova autenticada. O teste de rede foi executado pelo código-fonte.

O executável `dist/ClaraExam-login.exe` foi gerado e passou no percurso local (`--native-theme-test --local-only`) com código 0: núcleo nativo, prova interna, instalação/liberação do bloqueio e tema claro. Resultado em `build/login-exe/smoke-result.json`, com `packaged: true` e `network_tested: false`.

## Recuperação da etapa de passkey

Após o relato de carregamento na tela “Sign in faster”, foram adicionados o cancelamento explícito de solicitações WebAuth UX não suportadas, orientação ao usuário, retorno ao formulário original durante o login e diagnóstico de origens bloqueadas em separado dos eventos de foco. A suíte passou com 74 testes, incluindo cancelamento antes da orientação, destino fixo de retorno, restrição desse retorno à tela de login e separação dos diagnósticos.

Não foi reproduzida a etapa autenticada da captura do usuário. A ausência de tratamento de WebAuth UX é uma lacuna confirmada no código, mas não confirma a causa daquele carregamento. Nenhum domínio adicional foi liberado por suposição. O cancelamento usa a [API documentada do Qt](https://doc.qt.io/qtforpython-6/PySide6/QtWebEngineCore/QWebEngineWebAuthUxRequest.html); não foi exercitado com uma passkey real ou Windows Hello.

O carregamento da tela de identificação foi repetido pelo código-fonte com sucesso e saída 0. O novo `dist/ClaraExam-login2.exe` passou no percurso local com saída 0, `packaged: true` e `network_tested: false`; evidência em `build/login2-exe/smoke-result.json`. Isso não valida o fluxo autenticado da captura.

## Data e hora no rodapé

Foi adicionado um rodapé compartilhado pelas provas internas e externas, com data em português e hora local em formato `HH:mm:ss`. O temporizador existente atualiza ambos a cada 500 ms, lendo também a data novamente para acompanhar a virada do dia. A contagem de tempo restante continua baseada em relógio monotônico.

Os 74 testes existentes passaram. O percurso local pelo código-fonte terminou com saída 0 e a captura `build/footer-final/04-avaliacao.png` foi inspecionada: data à esquerda e relógio à direita, em uma linha abaixo dos controles.

## Investigação do carregamento após login

Em 06/10/2026 foram consultados somente os metadados de bloqueio das sessões locais recentes. A tentativa mais recente registrou XHR/Ping em `play.google.com` e favicon em `www.google.com`; uma tentativa anterior registrou também XHR em `signaler-pa.googleapis.com`. Esses registros não comprovam a causa da espera após autenticação.

A política passou a permitir HTTPS em `play.google.com/log` apenas para XHR/Ping e `signaler-pa.googleapis.com` apenas para XHR, com primeira parte Google Forms ou Google Accounts no perfil Forms. As origens não foram adicionadas às páginas navegáveis. Isso substitui a decisão anterior de sempre bloquear a telemetria `/log`; trata-se de um ajuste de compatibilidade ainda sem validação autenticada.

Também foi corrigida uma lacuna: rejeições em `acceptNavigationRequest` agora entram no relatório, incluindo apenas origem e tipo de navegação. Os 83 testes passaram, cobrindo escopo, protocolos/portas/endereços falsos, separação de navegação e recursos e exclusão de credenciais/tokens dos diagnósticos. A tela inicial de login carregou com campo de identificação e quatro folhas de estilo; somente favicon bloqueado. Não houve teste com senha nem confirmação de resolução do loop relatado.

O processo de diagnóstico de rede produziu a captura e o resultado, mas permaneceu em execução durante o encerramento e precisou ser finalizado. Portanto, não se atribui código de saída 0 a essa checagem de rede. A investigação da etapa autenticada continua pendente.

## Redirecionamentos registrados na tentativa seguinte

O relatório local mais recente revelou `accounts.youtube.com` bloqueado como `NavigationSubFrame` e `myaccount.google.com` como `NavigationMainFrame`. As versões anteriores não registravam os bloqueios da camada de navegação, por isso a ausência deles nos relatórios antigos não demonstrava que o fluxo estava liberado.

O perfil Forms agora permite `accounts.youtube.com` somente como quadro/recurso interno enquanto a página principal está em `accounts.google.com`. Navegação principal para YouTube continua bloqueada. Ao sair de Google Accounts em direção a My Account, a aplicação rejeita a página de gerenciamento e agenda retorno ao formulário original no mesmo perfil; não lê nem usa parâmetros `continue` para escolher o destino. O servidor do formulário continua verificando a autenticação. My Account não foi adicionado às origens permitidas.

Passaram 90 testes. Os novos casos reproduzem as duas decisões de navegação registradas, verificam restrições de domínio/protocolo/porta, contexto de login, rejeição de navegação principal para YouTube e retorno fixo à prova. Não se atribui a esses testes uma confirmação de login completo com conta real.

## Identidade visual

O texto da marca na barra lateral foi substituído por um SVG com monograma C, verificação e nome Clara Exam. O SVG fica embutido em `clara.branding`, sem depender de caminhos externos no executável; a cópia editável está em `assets/clara-exam-logo.svg`. O widget fornece nome acessível e é renderizado pelo Qt SVG.

O percurso local pelo código-fonte passou, e a captura `build/logo-source/01-inicio.png` foi inspecionada na escala nativa do Windows. O logo apresenta contraste e não invade o texto ou a navegação.
