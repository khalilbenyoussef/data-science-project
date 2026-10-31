"""Agents du pipeline BIFlow."""

from biflow.agents.analyst import FinovaAnalystAgent
from biflow.agents.base import AgentError, BaseAgent
from biflow.agents.bi_analyst import BiAnalystAgent
from biflow.agents.collector import CollectorAgent
from biflow.agents.dashboard import DashboardAgent, DashboardSpecAgent
from biflow.agents.etl import EtlAgent
from biflow.agents.profiler import ProfilerAgent
from biflow.agents.quality import QualityAgent
from biflow.agents.semantic_kpi import SemanticKpiAgent

__all__ = [
    "AgentError",
    "BaseAgent",
    "BiAnalystAgent",
    "CollectorAgent",
    "DashboardAgent",
    "DashboardSpecAgent",
    "ProfilerAgent",
    "QualityAgent",
    "EtlAgent",
    "FinovaAnalystAgent",
    "SemanticKpiAgent",
]
