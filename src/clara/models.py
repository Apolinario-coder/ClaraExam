from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from dataclasses import asdict, dataclass, field
from pathlib import Path

from clara._core import https_origin


def password_digest(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 300_000)
    return f"pbkdf2-sha256${salt}${digest.hex()}"


def check_password(password: str, encoded: str) -> bool:
    try:
        algorithm, salt, digest = encoded.split("$")
        if algorithm != "pbkdf2-sha256" or len(salt) != 32 or len(digest) != 64:
            return False
        return hmac.compare_digest(password_digest(password, salt), encoded)
    except (ValueError, TypeError):
        return False


@dataclass
class Question:
    prompt: str
    options: list[str]
    correct: int

    def validate(self):
        if not isinstance(self.prompt, str) or not 1 <= len(self.prompt.strip()) <= 5000:
            raise ValueError("Cada questão precisa de um enunciado de até 5.000 caracteres.")
        if not isinstance(self.options, list) or len(self.options) != 4 or any(
            not isinstance(o, str) or not 1 <= len(o.strip()) <= 1000 for o in self.options
        ):
            raise ValueError("Preencha as quatro alternativas de cada questão.")
        if type(self.correct) is not int or self.correct not in range(4):
            raise ValueError("Selecione uma alternativa correta.")


@dataclass
class Exam:
    title: str
    institution: str
    instructions: str
    mode: str
    minutes: int
    exit_hash: str
    start_url: str = ""
    allowed_origins: list[str] = field(default_factory=list)
    questions: list[Question] = field(default_factory=list)
    version: int = 1

    def validate(self):
        if type(self.version) is not int or self.version != 1 or self.mode not in ("external", "internal"):
            raise ValueError("Formato de avaliação não suportado.")
        for value, limit in ((self.title, 160), (self.institution, 160), (self.instructions, 10000)):
            if not isinstance(value, str) or len(value) > limit:
                raise ValueError("Texto inválido ou acima do limite.")
        if not self.title.strip():
            raise ValueError("Informe o título da avaliação.")
        if type(self.minutes) is not int or not 1 <= self.minutes <= 480:
            raise ValueError("A duração deve ser entre 1 e 480 minutos.")
        if not isinstance(self.exit_hash, str):
            raise ValueError("Credencial de saída inválida.")
        parts = self.exit_hash.split("$")
        try:
            valid = (len(parts) == 3 and parts[0] == "pbkdf2-sha256"
                     and len(parts[1]) == 32 and len(parts[2]) == 64
                     and len(bytes.fromhex(parts[1])) == 16
                     and len(bytes.fromhex(parts[2])) == 32)
        except ValueError:
            valid = False
        if not valid:
            raise ValueError("Credencial de saída inválida.")
        if self.mode == "external":
            if not isinstance(self.start_url, str) or len(self.start_url) > 8000:
                raise ValueError("Endereço da avaliação inválido.")
            start_origin = https_origin(self.start_url)
            if not isinstance(self.allowed_origins, list) or len(self.allowed_origins) > 100:
                raise ValueError("Informe no máximo 100 origens permitidas.")
            if any(not isinstance(o, str) or len(o) > 8000 for o in self.allowed_origins):
                raise ValueError("Origem permitida inválida.")
            self.allowed_origins = sorted({start_origin, *(https_origin(o) for o in self.allowed_origins)})
        else:
            if not 1 <= len(self.questions) <= 100:
                raise ValueError("Inclua de 1 a 100 questões.")
            for question in self.questions:
                question.validate()

    def save(self, path: Path):
        self.validate()
        atomic_json(path, asdict(self))

    @classmethod
    def load(cls, path: Path) -> Exam:
        if path.stat().st_size > 2_000_000:
            raise ValueError("Arquivo acima do limite de 2 MB.")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            data["questions"] = [Question(**q) for q in data.get("questions", [])]
            exam = cls(**data)
            exam.validate()
            return exam
        except (KeyError, TypeError, AttributeError, RecursionError) as error:
            raise ValueError("O arquivo não contém uma avaliação válida.") from error

    def grade(self, answers: dict[int, int]) -> dict:
        correct = sum(answers.get(i) == q.correct for i, q in enumerate(self.questions))
        total = len(self.questions)
        return {"correct": correct, "total": total, "percent": round(100 * correct / total, 1) if total else 0}


def atomic_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)
