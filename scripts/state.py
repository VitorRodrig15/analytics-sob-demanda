"""Estado compartilhado entre os agentes do sistema multiagente (E5)."""

from dataclasses import dataclass, field


@dataclass
class AgentContext:
    pergunta: str
    intencao: str | None = None
    contexto_rag: list[dict] = field(default_factory=list)
    sql_gerado: str | None = None
    validacao_ok: bool | None = None
    motivo_rejeicao: str | None = None
    resultado_execucao: dict | None = None
    erro_execucao: str | None = None
    resposta_final: str = ""
    tentativas: int = 0
    historico: list[str] = field(default_factory=list)

    def registrar(self, evento: str) -> None:
        self.historico.append(evento)
