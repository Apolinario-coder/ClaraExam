# Caminho para uma versão institucional

## 1. Experiência e compatibilidade

Validar esta prévia com professores e alunos: preparação, revisão, compartilhamento, acessibilidade, perda de conexão e encerramento. Escolher a primeira plataforma externa suportada e testar autenticação, mídia, acessibilidade e entrega de ponta a ponta. Adicionar importação/edição de avaliações existentes, banco de questões, tipos de questão adicionais e relatórios de turma.

## 2. Autoridade e resultados no servidor

Construir uma API Python com usuários, papéis, instituições, avaliações, tentativas e recebimento idempotente das respostas. Usar banco transacional. Gabarito e correção oficial ficam no servidor; a máquina do aluno não deve recebê-los antecipadamente. Emitir configurações assinadas com validade, versão e identificação da instituição. Vincular a tentativa à configuração e à identidade autenticada. Planejar operação com conectividade intermitente e recuperação sem ampliar o prazo da prova.

## 3. Núcleo Windows em Rust

Definir o modelo de ameaça para laboratórios gerenciados e computadores pessoais. Implementar isolamento suportado pelo Windows, serviço com privilégios mínimos quando necessário e canal IPC autenticado. Planejar bloqueios de atalhos e processos com acessibilidade e exceções explícitas. Implementar watchdog, recuperação após falha e restauração garantida do ambiente. Não encerrar processos ou alterar políticas do sistema sem um fluxo informado e reversível.

O núcleo atual valida origens e instala um gancho temporário para bloquear atalhos comuns durante a avaliação. O gancho é removido ao encerrar e não altera políticas persistentes. Ainda faltam desktop isolado, políticas de processos e validação de integridade; o gancho não deve ser apresentado como atestado de integridade do dispositivo.

## 4. Integrações de prova

Criar uma integração explícita com o LMS: atestação da versão/configuração, início e término da tentativa, regras de reentrada e estado de envio. Não simular identificadores do SEB para contornar exigências do LMS. Avaliar o protocolo oficial e a autorização necessária para interoperabilidade real.

## 5. Distribuição e validação

Instalador Windows assinado, associação de arquivos, atualizações assinadas, política de suporte e versões mínimas. Testes em Windows 10/11 conforme versões suportadas pelo produto, contas sem administrador, múltiplos monitores, leitores de tela, escala de DPI e diferentes layouts de teclado. Revisão de segurança independente antes de anunciar resistência a fraude. Definir retenção, exclusão e acesso aos registros, assim como um procedimento humano para incidentes durante a prova.

## Critério de lançamento

Não promover a prévia a versão segura apenas porque ela gera um `.exe` ou bloqueia URLs. O lançamento institucional depende de configuração autenticada, entrega confiável, isolamento validado, recuperação do computador e testes de acessibilidade e segurança com o modelo de ameaça documentado.
