# Clara Exam — prévia 0.1

Aplicativo desktop Windows em **Python + Rust**, com interface em português para preparar e realizar avaliações. Nome provisório, sem vínculo com o Safe Exam Browser.

**Este é um protótipo funcional, não um substituto de segurança do SEB. Não deve ser usado para provas oficiais nesta fase.**

## Experimentar

A versão atual está em **`dist/ClaraExam-logo.exe`**, com o novo logo vetorial na navegação lateral, além das melhorias anteriores de login, data, relógio e bloqueio de atalhos. Feche a versão anterior e abra esse arquivo. A primeira inicialização pode levar alguns segundos para extrair o motor do navegador. Os executáveis antigos foram preservados.

O build padrão gera a variante em pasta, `dist/ClaraExam/ClaraExam.exe`. A cópia dessa pasta que ficou da primeira entrega é anterior às correções; recompile antes de distribuí-la. Para distribuir essa variante, envie a pasta completa: o motor Chromium possui DLLs e um processo auxiliar. O build `-OneFile` gera novamente o executável único atualizado.

Na tela inicial, escolha **Experimentar uma prova de exemplo**. Informe um nome e confirme as instruções. A senha de saída do exemplo é `demonstracao`.

### Professor

1. Acesse **Preparar avaliação** e preencha título, duração, orientações e senha de saída.
2. Em **Prova por link**, informe a URL HTTPS e as demais origens exigidas por login, scripts e imagens. Não há integração nativa ou compatibilidade garantida com Moodle, Google Forms ou outro LMS. Teste a plataforma escolhida.
3. Em **Criar questões**, escreva questões de quatro alternativas, selecione o gabarito e adicione cada questão. Duplo clique permite editar uma questão já adicionada.
4. Exporte um arquivo `.clara.json` e compartilhe com a turma. Preserve a senha de saída com o responsável.

Links do Google Forms (`docs.google.com/forms/` e `forms.gle`) ativam automaticamente um perfil de recursos, inclusive ao importar arquivos de avaliação antigos. Ele permite estilos, scripts, fontes, imagens e carregamentos auxiliares em origens Google específicas, sem adicionar esses servidores à lista de páginas navegáveis. O endereço HTTPS `accounts.google.com` é permitido para autenticação; links de login que tentam abrir outra janela são direcionados à janela da prova quando acionados pelo usuário. Não libera Gmail, Drive ou pesquisa, salvo se o professor os adicionar explicitamente às origens permitidas. O perfil temporário não reutiliza o login do navegador pessoal.

O Google pode recusar autenticação em navegadores embutidos ([documentação oficial](https://support.google.com/accounts/answer/7675428?hl=en)). Foi verificado o carregamento da tela de identificação, sem inserir credenciais; login completo, desafios de segurança e SSO institucional não foram validados. Esta permissão não contorna restrições do Google. Uploads, vídeos e formulários institucionais restritos continuam sujeitos às limitações desta prévia.

Passkeys não são suportadas nesta prévia. Solicitações WebAuth UX recebidas pelo Qt são canceladas explicitamente, com orientação para escolher outro método. Na oferta do Google para criar uma chave, escolha **Not now / Agora não**. Durante o login, o botão **Voltar ao formulário** reabre somente o endereço original da avaliação no mesmo perfil temporário; se o login ainda não tiver terminado, o Google poderá solicitá-lo novamente. Bloqueios de rede são registrados em `browser_blocks` no relatório local, somente com origem, tipo e horário, sem URLs completas, tokens ou credenciais. Não contam como saídas de foco.

### Aluno

1. Escolha **Abrir avaliação** e importe o arquivo.
2. Confira as instruções, informe sua identificação e comece.
3. Na prova interna, navegue pelas questões e entregue para ver a correção. As respostas são salvas a cada alteração.
4. Na prova externa, envie as respostas **na própria plataforma** antes de concluir a sessão. Encerrar o Clara não confirma nem executa esse envio.

Ao expirar o tempo, a sessão termina. Provas internas são corrigidas localmente; em provas externas, respostas ainda não enviadas podem ser perdidas. Configure e teste também o limite de tempo no LMS.

## Implementado

- Interface Qt com áreas de preparação, instruções, avaliação e resultado.
- Dois formatos de avaliação: URL externa e múltipla escolha local.
- Núcleo Rust real, carregado como extensão nativa Python via PyO3.
- Comparação de origens HTTPS exatas, incluindo porta, sem permissões por substring.
- Filtro de navegação e de requisições do Qt WebEngine; novas janelas, downloads, uploads e permissões de câmera/microfone negados.
- Perfil de navegador temporário, sem reutilizar cookies do navegador pessoal.
- Tela cheia, senha para saída antecipada pela interface e cronômetro monotônico.
- Rodapé das provas internas e externas com dia da semana, data e relógio em formato de 24 horas, atualizados pelo horário local do computador. O cronômetro restante é independente do relógio civil.
- Gancho de teclado Windows em Rust, instalado apenas durante a avaliação e liberado ao encerrar. Bloqueia Alt+Tab/Alt+Esc, Alt+F4/Alt+Espaço, teclas Windows, Ctrl+Esc/Ctrl+Shift+Esc, F11/F12, Print Screen, tecla de menu, atalhos de DevTools (Ctrl+Shift+I/J/C/K), visualização de fonte (Ctrl+U), abertura de abas/arquivos, impressão/salvamento e recarga por teclado. Tab, Shift+Tab, digitação e combinações AltGr continuam disponíveis.
- Filtro de teclas dentro do Qt e retorno à tela cheia. A prova não inicia se a instalação do gancho falhar; interrupção detectada da thread de bloqueio encerra a sessão.
- Hash PBKDF2 da senha com salt aleatório, sem guardar a senha em texto.
- Salvamento atômico de respostas e registro local de perda de foco.
- Correção local e exportação JSON do resultado.

## Limites que precisam ser resolvidos para produção

- **Sem isolamento completo do Windows:** os atalhos comuns estão filtrados, mas Ctrl+Alt+Del, telas de segurança/UAC, aplicativos com maior privilégio, outros monitores e caminhos por mouse/gestos ainda podem permitir sair da prova ou abrir outros programas. O Windows pode remover um gancho que exceda seu prazo de resposta sem notificar o aplicativo. A propriedade de atividade acompanha a thread, não é uma atestação contínua do gancho. A proteção não equivale a um desktop isolado ou ao Keyboard Filter do Windows.
- **Sem confiança nas configurações:** arquivos não são assinados e podem ser editados. O aluno possui acesso ao gabarito local. A senha protege somente o fluxo da interface e não torna a configuração inviolável.
- **Sem servidor:** não há autenticação de professor/aluno, gestão institucional, envio confiável de resultados ou proteção contra adulteração do registro local.
- **Sem recuperação automática:** respostas locais permanecem em disco após falhas, mas ainda não há retomada da sessão pela interface.
- **Compatibilidade limitada:** pop-ups de autenticação, anexos, câmera, microfone, WebSockets e outros recursos podem impedir o funcionamento de plataformas externas. O bloqueio de rede é dentro do navegador; não é um firewall do sistema.
- Não existe suporte ao protocolo `.seb`, Browser Exam Key, App Signature Key ou autenticação SEB exigida por um LMS.
- Perda de foco é apenas um evento técnico; não comprova trapaça. Nenhum software no computador impede uso de outro aparelho ou ajuda externa.
- O `.exe` desta prévia não é assinado digitalmente e ainda não possui instalador, atualização automática ou validação em uma máquina Windows limpa.

## Dados

Nome informado, respostas, eventos de foco e resultado ficam em `%LOCALAPPDATA%/ClaraExam/sessions/`, em JSON legível. Não há captura de tela, câmera, microfone ou envio desses registros a terceiros. Sites externos recebem a navegação normal quando abertos. Os registros não são cifrados, assinados ou apagados automaticamente. A interface informa ao aluno sobre esse armazenamento antes da prova.

## Desenvolver e compilar

Requisitos: Windows x64, Python 3.11+, Rust estável e Visual Studio Build Tools com C++/Windows SDK.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install maturin "PySide6>=6.8,<7" pytest pyinstaller
maturin develop --release --locked
python launch.py
```

Para gerar o executável e executar os testes:

```powershell
.\scripts\build.ps1
# Alternativa: um único arquivo para distribuição
.\scripts\build.ps1 -OneFile
```

Se a instalação Rust da máquina estiver danificada, `python scripts/bootstrap_rust.py` prepara uma cópia isolada em `.tools/rust`, obtida dos servidores oficiais com verificação SHA-256. O script de build reconhece essa cópia. Não é necessário em instalações Rust normais.

### Organização

- `src/clara/app.py`: interface e ciclo de avaliação.
- `src/clara/browser.py`: perfil de navegador e restrições.
- `src/clara/models.py`: configuração, validação, senha e correção.
- `rust/lib.rs`: política de origem HTTPS, sem fallback Python permissivo.
- `rust/keyboard.rs`: política de atalhos e instalação/remoção do gancho Windows.
- `src/clara/shortcuts.py`: filtro de teclas do Qt usando a mesma política Rust.
- `tests/`: regras de acesso, validação, respostas, expiração e erros de armazenamento.
- `docs/ROADMAP.md`: etapas de evolução para um produto institucional.

As dependências Qt/PySide6 e seus componentes possuem termos de distribuição próprios. Preserve avisos e licenças ao preparar uma distribuição pública. Antes de incorporar código do SEB, examine sua licença; esta implementação foi criada separadamente.

## Referências técnicas

- [Visão geral do Safe Exam Browser](https://www.safeexambrowser.org/about_overview_en.html)
- [Qt WebEngine: interceptação de requisições](https://doc.qt.io/qt-6/qwebengineurlrequestinterceptor.html)
- [PyO3: compilação e distribuição](https://pyo3.rs/main/building-and-distribution.html)
- [Distribuição de aplicações Qt WebEngine](https://doc.qt.io/qt-6/qtwebengine-deploying.html)
