"""Application services / use-case orchestration."""

from app.services.pipeline import EmailPipeline, PipelineResult

__all__ = ["EmailPipeline", "PipelineResult"]
