"""
Service layer — business logic between API routes and the database / connectors.

Available services:
  DedupService         — weighted similarity scoring for duplicate investigations
  BaselineService      — last-healthy window selection and metric comparison
  BaselineStrategy     — enum of baseline selection strategies
  RemediationService   — action candidate generation and approval flow
  RetentionService     — per-org data retention and purge
  ExportService        — investigation export (JSON / Markdown)
  MappingService       — service map management and auto-discovery
"""
from .dedup_service import DedupService, DedupScore, DedupResult
from .baseline_service import BaselineService, BaselineStrategy, Baseline, ComparisonResult
from .remediation_service import RemediationService, ActionCandidate, ActionResult, RiskLevel
from .retention_service import RetentionService
from .export_service import ExportService, ExportResult
from .mapping_service import MappingService, DiscoveredService, MappingConfidence

__all__ = [
    # Dedup
    "DedupService",
    "DedupScore",
    "DedupResult",
    # Baseline
    "BaselineService",
    "BaselineStrategy",
    "Baseline",
    "ComparisonResult",
    # Remediation
    "RemediationService",
    "ActionCandidate",
    "ActionResult",
    "RiskLevel",
    # Retention
    "RetentionService",
    # Export
    "ExportService",
    "ExportResult",
    # Mapping
    "MappingService",
    "DiscoveredService",
    "MappingConfidence",
]
