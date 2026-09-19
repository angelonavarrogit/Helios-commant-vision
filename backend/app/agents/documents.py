"""HELIOS DOCS — Document agent (Phase 14).

Analyzes text extracted from an attachment (PDF/Excel/Word) and produces
structured findings: the likely document type (invoice, statement, contract,
policy, receipt, other) and whether it needs attention.

Design
------
- **Deterministic** keyword detection over the extracted text (ES/EN).
- **UNTRUSTED input.** The document text came from outside; it is analyzed as
  data, never obeyed. Any long numbers (account/PAN) are masked in the summary.
- **Read-only.** Findings only.

The agent is separate from the email agents because documents arrive as
attachment bytes, extracted by ``services.documents.extract_text`` first.
"""

from __future__ import annotations

from app.agents.base import AgentResult, Finding
from app.security.masking import mask_numbers_in_text

_DOC_TYPE_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("invoice", ("invoice", "factura", "amount due", "importe")),
    ("statement", ("statement", "estado de cuenta", "account summary", "balance")),
    ("contract", ("contract", "contrato", "agreement", "terms and conditions", "cláusula")),
    ("policy", ("policy", "póliza", "poliza", "coverage", "cobertura")),
    ("receipt", ("receipt", "recibo", "payment confirmation", "comprobante")),
)

# Documents of these types generally warrant the user's attention.
_ATTENTION_TYPES = frozenset({"invoice", "contract", "statement"})


class DocumentAgent:
    """Detects the type and salient facts of a document from its text."""

    name = "documents"

    def analyze_document(self, text: str, *, filename: str | None = None) -> AgentResult:
        """Return findings for a document's extracted text.

        Empty or unrecognized text yields an empty, low-confidence result.
        """
        if not text or not text.strip():
            return AgentResult(agent_name=self.name, confidence=0.0)

        lowered = text.lower()
        doc_type = self._detect_type(lowered)
        if doc_type is None:
            return AgentResult(agent_name=self.name, confidence=0.2)

        needs_review = doc_type in _ATTENTION_TYPES
        detail: dict[str, object] = {"doc_type": doc_type}
        if filename:
            detail["filename"] = filename

        summary = mask_numbers_in_text(f"Detected {doc_type} document.")
        finding = Finding(kind=doc_type, summary=summary, detail=detail, needs_review=needs_review)
        return AgentResult(
            agent_name=self.name,
            findings=[finding],
            requires_action=needs_review,
            confidence=0.7,
        )

    @staticmethod
    def _detect_type(lowered: str) -> str | None:
        for doc_type, keywords in _DOC_TYPE_KEYWORDS:
            if any(k in lowered for k in keywords):
                return doc_type
        return None
