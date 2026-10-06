import os
import sys
from pathlib import Path

# Ensure Windows platform and software rendering for offscreen capture if needed,
# or windows platform with offscreen/WA_DontShowOnScreen.
os.environ["QT_QPA_PLATFORM"] = "windows"
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"

from PySide6.QtCore import Qt, QEventLoop, QTimer
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication

from clara.app import MainWindow
from clara.theme import apply_theme
from clara.models import Exam, Question, password_digest

def main():
    app = QApplication.instance() or QApplication(sys.argv)
    
    # Load fonts if available
    for font in ("segoeui.ttf", "segoeuib.ttf", "seguisb.ttf"):
        QFontDatabase.addApplicationFont(str(Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / font))

    apply_theme(app)

    output_dir = Path("screenshots")
    output_dir.mkdir(parents=True, exist_ok=True)

    window = MainWindow()
    window.resize(1200, 800)
    window.show()
    app.processEvents()

    # 1. Tela Inicial (Home)
    window.stack.setCurrentWidget(window.home)
    app.processEvents()
    window.grab().save(str(output_dir / "01_tela_inicial.png"))
    print("Salvo: 01_tela_inicial.png")

    # 2. Tela do Professor (Preparar Avaliação)
    window.teacher.title.setText("Avaliação de Engenharia de Software • 1º Semestre")
    window.teacher.institution.setText("Universidade de Tecnologia")
    window.teacher.minutes.setValue(45)
    window.teacher.instructions.setText("Leia todas as questões com atenção. Proibida consulta a materiais externos.")
    window.teacher.password.setText("senha1234")
    # Adicionar uma questão modelo
    window.teacher.tabs.setCurrentIndex(1)
    window.teacher.prompt.setText("Qual das seguintes linguagens oferece gerenciamento de memória seguro sem garbage collector?")
    window.teacher.options[0].setText("Python")
    window.teacher.options[1].setText("Rust")
    window.teacher.options[2].setText("Java")
    window.teacher.options[3].setText("PHP")
    window.teacher.correct.setCurrentIndex(1)
    window.teacher.save_question()
    
    window.stack.setCurrentWidget(window.teacher)
    app.processEvents()
    window.grab().save(str(output_dir / "02_preparar_avaliacao.png"))
    print("Salvo: 02_preparar_avaliacao.png")

    # 3. Tela de Instruções / Pré-prova (Preflight)
    demo_exam = Exam(
        title="Avaliação de Engenharia de Software",
        institution="Universidade de Tecnologia",
        instructions="Você terá 45 minutos para resolver as questões. Mantenha o foco na tela da avaliação.",
        mode="internal",
        minutes=45,
        exit_hash=password_digest("demonstracao"),
        questions=[
            Question("Qual linguagem combina controle de baixo nível com segurança de memória sem garbage collector?", ["Python", "Rust", "Java", "PHP"], 1),
            Question("Qual componente é responsável pela interface gráfica e renderização web no Clara Exam?", ["Tkinter", "PySide6 / Qt WebEngine", "Electron", "Flutter"], 1),
            Question("Qual mecanismo da API do Windows é utilizado pelo Clara Exam para interceptar atalhos de sistema?", ["DirectX", "Win32 Low-Level Keyboard Hooks", "WMI", "Windows Registry"], 1),
        ]
    )
    window.show_preflight(demo_exam)
    window.student.setText("Lucas Siqueira Apolinario")
    window.consent.setChecked(True)
    app.processEvents()
    window.grab().save(str(output_dir / "03_instrucoes_aluno.png"))
    print("Salvo: 03_instrucoes_aluno.png")

    # 4. Tela da Prova em Andamento (Sessão Ativa)
    window.start_button.click()
    app.processEvents()
    
    # Simula resposta na primeira questão e navegação
    session = window.session
    if session:
        session.group.button(1).click()  # Seleciona a opção B (Rust)
        app.processEvents()
        window.grab().save(str(output_dir / "04_prova_em_andamento.png"))
        print("Salvo: 04_prova_em_andamento.png")

        # 5. Tela de Resultado Final
        session.next.click()
        session.group.button(1).click()  # Opção B
        session.next.click()
        session.group.button(1).click()  # Opção B
        app.processEvents()
        session.finish("concluida")
        app.processEvents()
        window.grab().save(str(output_dir / "05_resultado_avaliacao.png"))
        print("Salvo: 05_resultado_avaliacao.png")

    window.close()
    print("Todas as capturas foram geradas com sucesso!")

if __name__ == "__main__":
    main()
