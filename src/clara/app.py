from __future__ import annotations

import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import Qt, QDateTime, QEvent, QLocale, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QComboBox, QFileDialog, QFormLayout,
    QFrame, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget,
    QMainWindow, QMessageBox, QProgressBar, QPushButton, QRadioButton,
    QScrollArea, QSpinBox, QStackedWidget, QTabWidget, QTextEdit, QVBoxLayout, QWidget,
)

from clara.models import Exam, Question, atomic_json, check_password, password_digest
from clara._core import start_keyboard_guard
from clara.shortcuts import restricted_event
from clara.theme import apply_theme
from clara.web_policy import is_google_form
from clara.branding import BrandLogo


def label(text, role=None):
    widget = QLabel(text)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    widget.setWordWrap(True)
    if role:
        widget.setObjectName(role)
    return widget


def button(text, callback, primary=False):
    widget = QPushButton(text)
    if primary:
        widget.setObjectName("primary")
    widget.clicked.connect(callback)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    return widget


def box():
    widget = QFrame()
    widget.setObjectName("card")
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(24, 22, 24, 22)
    layout.setSpacing(14)
    return widget, layout


def page(title, subtitle):
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(36, 28, 36, 28)
    layout.setSpacing(18)
    layout.addWidget(label(title, "heading"))
    layout.addWidget(label(subtitle, "muted"))
    return widget, layout


def scroll(content):
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setWidget(content)
    return area


def show_error(parent, error):
    QMessageBox.warning(parent, "Vamos conferir um detalhe", str(error))


class Teacher(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.questions = []
        self.editing = None
        outer = QVBoxLayout(self)
        content, layout = page("Prepare sua próxima avaliação", "Defina o conteúdo, oriente a turma e compartilhe um arquivo de avaliação.")
        outer.addWidget(scroll(content))
        card, fields = box()
        form = QFormLayout()
        form.setSpacing(12)
        self.title = QLineEdit()
        self.title.setPlaceholderText("Ex.: Matemática • 2º ano • Unidade 3")
        self.institution = QLineEdit()
        self.institution.setPlaceholderText("Nome da escola ou instituição")
        self.minutes = QSpinBox()
        self.minutes.setRange(1, 480)
        self.minutes.setValue(60)
        self.minutes.setSuffix(" minutos")
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setPlaceholderText("Pelo menos 8 caracteres; guarde com o responsável")
        self.instructions = QTextEdit()
        self.instructions.setPlaceholderText("O que o aluno precisa saber antes de começar?")
        self.instructions.setMaximumHeight(100)
        for name, widget in (("Título", self.title), ("Instituição", self.institution),
                             ("Duração", self.minutes), ("Senha de saída", self.password),
                             ("Instruções", self.instructions)):
            form.addRow(name, widget)
        fields.addLayout(form)
        layout.addWidget(card)
        self.tabs = QTabWidget()
        external = QWidget()
        ef = QFormLayout(external)
        ef.setContentsMargins(20, 20, 20, 20)
        self.url = QLineEdit()
        self.url.setPlaceholderText("https://sua-plataforma.edu/prova")
        self.origins = QTextEdit()
        self.origins.setPlaceholderText("https://login.sua-plataforma.edu\nhttps://static.sua-plataforma.edu")
        self.origins.setMaximumHeight(95)
        ef.addRow("Link da prova", self.url)
        ef.addRow("Outros sites necessários", self.origins)
        ef.addRow(label("Um endereço HTTPS por linha. O site inicial é incluído automaticamente. Valide login, imagens e envio da prova antes de usar com a turma.", "muted"))
        ef.addRow(label("Google Forms: estilos, scripts, fontes e imagens recebem ajuste automático de compatibilidade.", "muted"))
        self.tabs.addTab(external, "Prova por link")
        internal = QWidget()
        il = QVBoxLayout(internal)
        il.setContentsMargins(20, 20, 20, 20)
        self.question_list = QListWidget()
        self.question_list.setMaximumHeight(125)
        self.question_list.itemDoubleClicked.connect(self.edit_question)
        il.addWidget(self.question_list)
        il.addWidget(label("Duplo clique em uma questão para editar.", "muted"))
        self.prompt = QTextEdit()
        self.prompt.setPlaceholderText("Escreva o enunciado da questão…")
        self.prompt.setMaximumHeight(95)
        il.addWidget(self.prompt)
        self.options = [QLineEdit() for _ in range(4)]
        for index, option in enumerate(self.options):
            option.setPlaceholderText(f"Alternativa {chr(65 + index)}")
            il.addWidget(option)
        self.correct = QComboBox()
        self.correct.addItems([f"Resposta correta: {letter}" for letter in "ABCD"])
        il.addWidget(self.correct)
        row = QHBoxLayout()
        self.save_question_button = button("Adicionar questão", self.save_question)
        row.addWidget(self.save_question_button)
        row.addWidget(button("Remover selecionada", self.remove_question))
        il.addLayout(row)
        self.tabs.addTab(internal, "Criar questões")
        layout.addWidget(self.tabs)
        layout.addWidget(label("Versão experimental: configurações sem assinatura e gabarito local acessível no arquivo. Use apenas em demonstrações; provas oficiais exigem servidor e proteção adicional.", "notice"))
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(button("Exportar avaliação", self.export, True))
        layout.addLayout(row)

    def refresh_questions(self):
        self.question_list.clear()
        for i, q in enumerate(self.questions):
            self.question_list.addItem(f"{i + 1:02d}   {q.prompt[:90]}   •   Resposta {chr(65 + q.correct)}")

    def clear_editor(self):
        self.editing = None
        self.prompt.clear()
        for option in self.options:
            option.clear()
        self.save_question_button.setText("Adicionar questão")

    def edit_question(self, item):
        self.editing = self.question_list.row(item)
        question = self.questions[self.editing]
        self.prompt.setPlainText(question.prompt)
        for widget, value in zip(self.options, question.options):
            widget.setText(value)
        self.correct.setCurrentIndex(question.correct)
        self.save_question_button.setText("Salvar alteração")

    def save_question(self):
        try:
            question = Question(self.prompt.toPlainText().strip(), [w.text().strip() for w in self.options], self.correct.currentIndex())
            question.validate()
            if self.editing is None:
                if len(self.questions) >= 100:
                    raise ValueError("O limite é de 100 questões por avaliação.")
                self.questions.append(question)
            else:
                self.questions[self.editing] = question
            self.clear_editor()
            self.refresh_questions()
        except ValueError as error:
            show_error(self, error)

    def remove_question(self):
        index = self.question_list.currentRow()
        if index >= 0:
            self.questions.pop(index)
            self.clear_editor()
            self.refresh_questions()

    def export(self):
        try:
            if len(self.password.text()) < 8:
                raise ValueError("Escolha uma senha de saída com pelo menos 8 caracteres.")
            if self.tabs.currentIndex() == 1 and (self.prompt.toPlainText().strip() or any(w.text().strip() for w in self.options)):
                raise ValueError("Adicione ou salve a questão em edição antes de exportar.")
            exam = Exam(
                title=self.title.text().strip(), institution=self.institution.text().strip(),
                instructions=self.instructions.toPlainText().strip(),
                mode="external" if self.tabs.currentIndex() == 0 else "internal",
                minutes=self.minutes.value(), exit_hash=password_digest(self.password.text()),
                start_url=self.url.text().strip(),
                allowed_origins=[o.strip() for o in self.origins.toPlainText().splitlines() if o.strip()],
                questions=list(self.questions) if self.tabs.currentIndex() == 1 else [],
            )
            exam.validate()
            target, _ = QFileDialog.getSaveFileName(self, "Compartilhar avaliação", "avaliacao.clara.json", "Avaliação Clara (*.clara.json)")
            if target:
                exam.save(Path(target))
                QMessageBox.information(self, "Avaliação exportada", "Envie esse arquivo aos alunos. A senha de saída deve ficar apenas com o responsável.\n\nTeste todo o percurso da avaliação antes de distribuir.")
        except (OSError, ValueError) as error:
            show_error(self, error)


class Session(QWidget):
    completed = Signal(dict)
    ending = Signal()

    def __init__(self, exam, student, parent=None):
        super().__init__(parent)
        self.exam = exam
        self.student = student
        self.answers = {}
        self.index = 0
        self.finished = False
        self.browser = None
        self.events = []
        self.browser_blocks = []
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.deadline = time.monotonic() + exam.minutes * 60
        self.session_id = str(uuid.uuid4())
        self.storage = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "ClaraExam" / "sessions" / f"{self.session_id}.json"
        self.last_save_error = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 20, 26, 20)
        layout.setSpacing(12)
        top = QHBoxLayout()
        top.addWidget(label(exam.title, "subheading"), 1)
        self.clock = label("", "subheading")
        top.addWidget(self.clock)
        top.addWidget(button("Pedir saída", self.request_exit))
        layout.addLayout(top)
        layout.addWidget(label(f"{student}   •   {exam.institution or 'Avaliação'}   •   Sessão experimental", "muted"))
        self.status = label("Respostas salvas neste computador. Não há envio para um servidor." if exam.mode == "internal" else "Envie suas respostas pela própria plataforma antes de concluir.", "success")
        layout.addWidget(self.status)
        if exam.mode == "external":
            from clara.browser import ExamBrowser
            self.browser = ExamBrowser(exam, self)
            self.browser.message.connect(self.browser_message)
            self.browser.interceptor.requestBlocked.connect(self.record_browser_block)
            self.browser.exam_page.navigationBlocked.connect(self.record_browser_block)
            layout.addWidget(self.browser, 1)
            footer = QHBoxLayout()
            footer.addWidget(button("Recarregar página", self.reload_page))
            self.return_to_form_button = button("Voltar ao formulário", self.browser.return_to_form)
            self.return_to_form_button.setVisible(False)
            self.browser.loginActive.connect(self.return_to_form_button.setVisible)
            footer.addWidget(self.return_to_form_button)
            footer.addStretch()
            footer.addWidget(button("Já enviei • Concluir sessão", self.submit, True))
            layout.addLayout(footer)
        else:
            self.progress = QProgressBar()
            self.progress.setRange(0, len(exam.questions))
            self.progress.setTextVisible(False)
            layout.addWidget(self.progress)
            self.question_card, self.question_layout = box()
            layout.addWidget(scroll(self.question_card), 1)
            controls = QHBoxLayout()
            self.previous = button("← Anterior", lambda: self.navigate(-1))
            self.next = button("Próxima →", lambda: self.navigate(1))
            controls.addWidget(self.previous)
            self.counter = label("")
            controls.addWidget(self.counter, 1, Qt.AlignmentFlag.AlignCenter)
            controls.addWidget(self.next)
            controls.addWidget(button("Entregar avaliação", self.submit, True))
            layout.addLayout(controls)
            self.render_question()
        date_time_footer = QHBoxLayout()
        self.today_label = label("", "muted")
        self.today_label.setWordWrap(False)
        self.today_label.setAccessibleName("Data de hoje")
        self.wall_clock = label("", "muted")
        self.wall_clock.setWordWrap(False)
        self.wall_clock.setAccessibleName("Horário atual do computador")
        self.wall_clock.setToolTip("Horário local do computador. O tempo restante da prova aparece no topo.")
        date_time_footer.addWidget(self.today_label)
        date_time_footer.addStretch()
        date_time_footer.addWidget(self.wall_clock)
        layout.addLayout(date_time_footer)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(500)
        self.tick()
        self.persist()

    def browser_message(self, text):
        if not self.last_save_error:
            self.status.setText(text)

    def record_browser_block(self, origin, kind):
        if not self.finished:
            # Interceptor emits only origins and resource types, never credentials,
            # URL query strings, cookie values or response bodies.
            self.browser_blocks.append({"type": "recurso_bloqueado", "origin": origin,
                                "resource_type": kind, "at": datetime.now(timezone.utc).isoformat()})
            self.persist()

    def reload_page(self):
        if QMessageBox.question(self, "Recarregar página?", "Respostas ainda não salvas na plataforma podem ser perdidas. Continuar?") == QMessageBox.StandardButton.Yes:
            self.browser.reload()

    def render_question(self):
        while self.question_layout.count():
            child = self.question_layout.takeAt(0)
            if child.widget():
                child.widget().hide()
                child.widget().deleteLater()
        if hasattr(self, "group"):
            self.group.deleteLater()
        q = self.exam.questions[self.index]
        self.question_layout.addWidget(label(f"QUESTÃO {self.index + 1:02d}", "eyebrow"))
        self.question_layout.addWidget(label(q.prompt, "subheading"))
        self.group = QButtonGroup(self)
        for i, option in enumerate(q.options):
            row = QWidget()
            row_layout = QHBoxLayout(row)
            choice = QRadioButton(f"{chr(65 + i)}.")
            choice.setAccessibleName(f"Alternativa {chr(65 + i)}: {option}")
            self.group.addButton(choice, i)
            choice.setChecked(self.answers.get(self.index) == i)
            row_layout.addWidget(choice)
            option_label = label(option)
            option_label.mousePressEvent = lambda event, target=choice: target.click()
            row_layout.addWidget(option_label, 1)
            self.question_layout.addWidget(row)
        self.group.idClicked.connect(self.answer)
        self.question_layout.addStretch()
        self.previous.setEnabled(self.index > 0)
        self.next.setEnabled(self.index < len(self.exam.questions) - 1)
        self.update_counter()

    def update_counter(self):
        self.counter.setText(f"{self.index + 1} de {len(self.exam.questions)}   •   {len(self.answers)} respondidas")
        self.progress.setValue(len(self.answers))

    def answer(self, choice):
        if self.finished:
            return
        if time.monotonic() >= self.deadline:
            self.finish("tempo_encerrado")
            return
        self.answers[self.index] = choice
        self.update_counter()
        self.persist()

    def navigate(self, delta):
        self.index = max(0, min(len(self.exam.questions) - 1, self.index + delta))
        self.render_question()

    def tick(self):
        now = QDateTime.currentDateTime()
        locale = QLocale("pt_BR")
        self.today_label.setText("Hoje: " + locale.toString(now.date(), "dddd, dd/MM/yyyy"))
        self.wall_clock.setText("Hora: " + now.toString("HH:mm:ss"))
        remaining = max(0, int(self.deadline - time.monotonic()))
        self.clock.setText(f"{remaining // 60:02d}:{remaining % 60:02d} restantes")
        if time.monotonic() >= self.deadline:
            self.finish("tempo_encerrado")

    def record_focus(self):
        if not self.finished:
            self.events.append({"type": "app_perdeu_foco", "at": datetime.now(timezone.utc).isoformat()})
            self.persist()

    def report(self, reason="em_andamento"):
        return {
            "session_id": self.session_id, "exam": self.exam.title, "student": self.student,
            "mode": self.exam.mode, "started_at": self.started_at, "status": reason,
            "recorded_at": datetime.now(timezone.utc).isoformat(), "answers": self.answers,
            "grade": self.exam.grade(self.answers) if self.exam.mode == "internal" and reason != "em_andamento" else None,
            "events": self.events, "browser_blocks": self.browser_blocks, "verified": False,
            "note": "Registro local experimental. Perda de foco não comprova trapaça. Não comprova entrega em plataformas externas.",
        }

    def persist(self, reason="em_andamento"):
        report = self.report(reason)
        try:
            atomic_json(self.storage, report)
            if self.last_save_error:
                self.status.setText("Registro local salvo novamente.")
            self.last_save_error = False
        except OSError:
            self.last_save_error = True
            self.status.setText("Não foi possível salvar neste computador. Avise o responsável e exporte o resultado ao concluir.")
        return report

    def request_exit(self):
        password, accepted = QInputDialog.getText(self, "Saída autorizada", "Senha do responsável:", QLineEdit.EchoMode.Password)
        if not self.finished and accepted:
            if check_password(password, self.exam.exit_hash):
                self.finish("interrompida_pelo_responsavel")
            else:
                show_error(self, "Senha incorreta. Peça ajuda ao responsável.")

    def submit(self):
        text = (f"Você respondeu {len(self.answers)} de {len(self.exam.questions)} questões. Entregar agora?"
                if self.exam.mode == "internal" else "Você já enviou a prova na plataforma? Encerrar aqui não envia respostas nem confirma a entrega.")
        if QMessageBox.question(self, "Concluir avaliação", text) == QMessageBox.StandardButton.Yes:
            self.finish("concluida" if self.exam.mode == "internal" else "encerrada_sem_verificacao_de_entrega")

    def finish(self, reason):
        if self.finished:
            return
        self.finished = True
        self.timer.stop()
        self.ending.emit()
        if self.browser:
            self.browser.dispose()
        report = self.persist(reason)
        report["saved_to"] = str(self.storage) if not self.last_save_error else None
        self.completed.emit(report)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Clara Exam • Avaliações com clareza")
        self.resize(1180, 820)
        self.setMinimumSize(900, 640)
        self.session = None
        self.keyboard_guard = None
        self.protection_timer = QTimer(self)
        self.protection_timer.setInterval(500)
        self.protection_timer.timeout.connect(self.check_protection)
        self.exam = None
        canvas = QWidget()
        canvas.setObjectName("canvas")
        main = QHBoxLayout(canvas)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)
        self.sidebar = QWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(224)
        nav = QVBoxLayout(self.sidebar)
        nav.setContentsMargins(22, 32, 22, 24)
        nav.setSpacing(12)
        nav.addWidget(BrandLogo(self.sidebar))
        nav.addWidget(label("Espaço para aprender.\nFoco para avaliar."))
        nav.addSpacing(36)
        self.stack = QStackedWidget()
        for text, action in (("01   Início", lambda: self.stack.setCurrentWidget(self.home)),
                             ("02   Preparar avaliação", lambda: self.stack.setCurrentWidget(self.teacher)),
                             ("03   Realizar avaliação", self.import_exam)):
            item = button(text, action)
            item.setObjectName("nav")
            nav.addWidget(item)
        nav.addStretch()
        nav.addWidget(label("PRÉVIA 0.1\nUso experimental"))
        main.addWidget(self.sidebar)
        main.addWidget(self.stack, 1)
        self.setCentralWidget(canvas)
        self.home = self.make_home()
        self.teacher = Teacher()
        self.stack.addWidget(self.home)
        self.stack.addWidget(self.teacher)
        self.preflight = None
        self.result_page = None
        QApplication.instance().applicationStateChanged.connect(self.application_state)
        QApplication.instance().aboutToQuit.connect(self.release_keyboard_guard)
        QApplication.instance().installEventFilter(self)

    def make_home(self):
        content, layout = page("Uma boa avaliação começa\ncom tranquilidade.", "Um lugar simples para preparar a prova e ajudar cada aluno a se concentrar.")
        layout.addWidget(label("SEU PRÓXIMO PASSO", "eyebrow"))
        for title, description, action_text, action in (
            ("Sou professor", "Crie questões com correção automática ou conecte uma prova da sua plataforma. Defina as orientações em um só lugar.", "Preparar avaliação →", lambda: self.stack.setCurrentWidget(self.teacher)),
            ("Vou realizar uma prova", "Abra o arquivo enviado pelo professor, confira as instruções e comece quando estiver pronto.", "Abrir avaliação →", self.import_exam),
        ):
            card, cl = box()
            cl.addWidget(label(title, "subheading"))
            cl.addWidget(label(description, "muted"))
            cl.addWidget(button(action_text, action, True), 0, Qt.AlignmentFlag.AlignLeft)
            layout.addWidget(card)
        row = QHBoxLayout()
        row.addWidget(button("Experimentar uma prova de exemplo", self.demo))
        row.addStretch()
        layout.addLayout(row)
        layout.addWidget(label("Durante a prova, o aplicativo bloqueia atalhos comuns para trocar de janela ou sair da tela cheia. Ainda não isola todo o Windows.", "notice"))
        layout.addStretch()
        return scroll(content)

    def demo(self):
        exam = Exam("Uma volta pelo Clara", "Avaliação de exemplo", "Explore as questões, acompanhe seu progresso e veja o resultado ao finalizar.\nSenha de saída deste exemplo: demonstracao", "internal", 10, password_digest("demonstracao"), questions=[
            Question("Qual é o resultado de 12 × 8?", ["80", "88", "96", "108"], 2),
            Question("Qual destes hábitos ajuda a se preparar para uma avaliação?", ["Ignorar as instruções", "Revisar o conteúdo com antecedência", "Começar sem conferir o tempo", "Deixar todas as questões em branco"], 1),
            Question("Um triângulo possui quantos lados?", ["Dois", "Três", "Quatro", "Cinco"], 1),
        ])
        self.show_preflight(exam)

    def import_exam(self):
        path, _ = QFileDialog.getOpenFileName(self, "Abrir avaliação", "", "Avaliação Clara (*.clara.json);;JSON (*.json)")
        if path:
            try:
                self.show_preflight(Exam.load(Path(path)))
            except (ValueError, OSError, UnicodeError) as error:
                show_error(self, error)

    def show_preflight(self, exam):
        self.exam = exam
        if self.preflight:
            self.stack.removeWidget(self.preflight)
            self.preflight.deleteLater()
        content, layout = page("Tudo pronto para começar?", "Confira os detalhes da sua avaliação antes de iniciar o tempo.")
        card, cl = box()
        cl.addWidget(label(exam.title, "subheading"))
        kind = f"{len(exam.questions)} questões • correção local" if exam.mode == "internal" else "Prova em plataforma externa"
        cl.addWidget(label(f"{exam.institution or 'Avaliação'}   •   {exam.minutes} minutos   •   {kind}", "muted"))
        cl.addWidget(label(exam.instructions or "Siga as orientações do responsável pela avaliação."))
        if exam.mode == "external":
            cl.addWidget(label(f"Endereço inicial: {exam.start_url}"))
            cl.addWidget(label("Sites permitidos:\n" + "\n".join(exam.allowed_origins), "muted"))
            if is_google_form(exam.start_url):
                cl.addWidget(label("Compatibilidade Google Forms ativada: os recursos visuais e scripts necessários podem carregar sem liberar esses servidores como páginas de navegação.", "muted"))
        layout.addWidget(card)
        self.student = QLineEdit()
        self.student.setMaxLength(160)
        self.student.setPlaceholderText("Seu nome ou identificação na turma")
        layout.addWidget(label("Como devemos identificar seu resultado?", "subheading"))
        layout.addWidget(self.student)
        layout.addWidget(label("Ao começar, o aplicativo ocupará a tela inteira e bloqueará atalhos como Alt+Tab, F11 e F12. A saída antecipada exige a senha do responsável. Saídas de foco serão registradas; não há câmera, microfone ou gravação da tela.", "muted"))
        layout.addWidget(label("Proteção experimental: o Windows e outros programas ainda podem ser acessados por caminhos que este aplicativo não controla. Não use esta prévia como garantia contra trapaça.", "notice"))
        self.consent = QCheckBox("Li as instruções e estou pronto para começar.")
        layout.addWidget(self.consent)
        self.start_button = button("Começar avaliação →", self.start_session, True)
        self.start_button.setEnabled(False)
        self.consent.toggled.connect(self.update_start)
        self.student.textChanged.connect(self.update_start)
        layout.addWidget(self.start_button)
        layout.addStretch()
        self.preflight = scroll(content)
        self.stack.addWidget(self.preflight)
        self.stack.setCurrentWidget(self.preflight)

    def update_start(self):
        self.start_button.setEnabled(self.consent.isChecked() and bool(self.student.text().strip()))

    def start_session(self):
        if self.session or not self.consent.isChecked() or not self.student.text().strip():
            return
        try:
            self.exam.validate()
            self.keyboard_guard = start_keyboard_guard()
            self.session = Session(self.exam, self.student.text().strip())
            self.session.ending.connect(self.release_keyboard_guard)
            self.session.completed.connect(self.show_result)
            self.stack.addWidget(self.session)
            self.stack.setCurrentWidget(self.session)
            self.sidebar.hide()
            self.showFullScreen()
            self.protection_timer.start()
        except Exception as error:
            self.release_keyboard_guard()
            if self.session:
                self.session.timer.stop()
                if self.session.browser:
                    self.session.browser.dispose()
                self.stack.removeWidget(self.session)
                self.session.deleteLater()
                self.session = None
            self.sidebar.show()
            self.showNormal()
            show_error(self, error)

    def release_keyboard_guard(self):
        self.protection_timer.stop()
        if self.keyboard_guard:
            self.keyboard_guard.stop()
            self.keyboard_guard = None

    def check_protection(self):
        if self.session and not self.session.finished:
            if not self.keyboard_guard or not self.keyboard_guard.active:
                self.session.finish("falha_bloqueio")

    def show_result(self, report):
        self.release_keyboard_guard()
        previous = self.session
        self.session = None
        self.showNormal()
        self.sidebar.show()
        content, layout = page("Sessão encerrada", "Confira o registro desta tentativa.")
        card, cl = box()
        cl.addWidget(label(report["exam"], "subheading"))
        cl.addWidget(label(f"Participante: {report['student']}"))
        reasons = {"concluida": "Avaliação entregue localmente", "tempo_encerrado": "O tempo da avaliação terminou", "interrompida_pelo_responsavel": "Avaliação interrompida pelo responsável", "encerrada_sem_verificacao_de_entrega": "Sessão externa encerrada; entrega não verificada"}
        reasons["falha_bloqueio"] = "Sessão interrompida: o bloqueio de atalhos deixou de responder. Avise o responsável."
        cl.addWidget(label(reasons[report["status"]], "muted"))
        grade = report["grade"]
        if grade:
            cl.addWidget(label(f"{grade['correct']} de {grade['total']} acertos  •  {grade['percent']}%", "heading"))
        else:
            cl.addWidget(label("A nota e a confirmação de envio devem ser consultadas na plataforma da prova. O Clara não envia as respostas automaticamente.", "notice"))
        cl.addWidget(label(f"{len(report['events'])} saídas de foco registradas. Esses eventos não comprovam trapaça.", "muted"))
        layout.addWidget(card)
        layout.addWidget(label("Registro local experimental, sem assinatura ou autenticação por servidor.", "notice"))
        layout.addWidget(label(f"Registro salvo em: {report['saved_to']}" if report["saved_to"] else "Falha no salvamento automático. Exporte o resultado antes de sair.", "muted"))
        layout.addWidget(button("Exportar resultado JSON", lambda: self.export_report(report), True))
        layout.addWidget(button("Voltar ao início", lambda: self.stack.setCurrentWidget(self.home)))
        layout.addStretch()
        if self.result_page:
            self.stack.removeWidget(self.result_page)
            self.result_page.deleteLater()
        self.result_page = scroll(content)
        self.stack.addWidget(self.result_page)
        self.stack.setCurrentWidget(self.result_page)
        if previous:
            self.stack.removeWidget(previous)
            previous.deleteLater()

    def export_report(self, report):
        path, _ = QFileDialog.getSaveFileName(self, "Exportar resultado", "resultado.json", "JSON (*.json)")
        if path:
            try:
                atomic_json(Path(path), report)
            except OSError as error:
                show_error(self, error)

    def application_state(self, state):
        if self.session and state != Qt.ApplicationState.ApplicationActive:
            self.session.record_focus()

    def closeEvent(self, event):
        if self.session and not self.session.finished:
            event.ignore()
            self.session.request_exit()
        else:
            self.release_keyboard_guard()
            event.accept()

    def eventFilter(self, watched, event):
        if self.session and not self.session.finished and event.type() in (
                QEvent.Type.ShortcutOverride, QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            if restricted_event(event):
                event.accept()
                return True
        return super().eventFilter(watched, event)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange and self.session and not self.session.finished:
            QTimer.singleShot(0, self.enforce_fullscreen)

    def enforce_fullscreen(self):
        if self.session and not self.session.finished and not self.isFullScreen():
            self.showFullScreen()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Clara Exam")
    app.setOrganizationName("ClaraExam")
    apply_theme(app)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
