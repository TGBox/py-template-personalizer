"""Template Personalizer for FastReport (.fr3) templates."""

from .config import PersonalizerConfig, load_config
from .personalizer import TemplatePersonalizer, ReplacementStats
from .fastreport_xml import FastReportXML

__all__ = [
    "PersonalizerConfig",
    "load_config",
    "TemplatePersonalizer",
    "ReplacementStats",
    "FastReportXML",
]
