from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator, model_validator

from app.ingestion import validate_git_url, validate_ref


class RepositorySource(BaseModel):
    kind: Literal["git"] = "git"
    url: str
    ref: str | None = None

    _validate_url = field_validator("url")(validate_git_url)
    _validate_ref = field_validator("ref")(validate_ref)


class AnalysisCreate(BaseModel):
    source: RepositorySource


class AnalysisJob(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    status: Literal["queued", "analyzing", "complete", "failed"] = "queued"
    phase: str = "queued"
    progress: int = Field(default=0, ge=0, le=100)
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Evidence(BaseModel):
    path: str
    lines: str | None = None
    reason: str


class SourceFile(BaseModel):
    path: str
    text: str
    lines: int
    truncated: bool


class AtlasNode(BaseModel):
    id: str
    kind: str
    label: str
    detail: str
    path: str
    confidence: int = Field(ge=0, le=100)
    evidence: list[Evidence] = Field(default_factory=list)
    attributes: dict[str, str | int | bool] = Field(default_factory=dict)


class AtlasRelationship(BaseModel):
    source: str
    target: str
    type: Literal["CONTAINS", "IMPORTS", "RESOLVES_TO", "DEPENDS_ON", "ROUTES_TO", "CALLS"]
    resolution: Literal["resolved", "inferred", "unresolved"]
    confidence: int = Field(ge=0, le=100)
    evidence: list[Evidence]


class ReportStep(BaseModel):
    source: str
    target: str
    type: str
    resolution: Literal["resolved", "inferred", "unresolved"]


class ReportItem(BaseModel):
    id: str
    title: str
    description: str
    basis: Literal["observed", "inferred"]
    confidence: int = Field(ge=0, le=100)
    node_ids: list[str]
    evidence: list[Evidence]
    category: str
    metrics: dict[str, int] = Field(default_factory=dict)
    steps: list[ReportStep] = Field(default_factory=list)
    priority: Literal["low", "medium", "high"] | None = None
    effort: Literal["small", "medium", "large"] | None = None
    approach: list[str] = Field(default_factory=list)
    verification: list[str] = Field(default_factory=list)


class ReportSection(BaseModel):
    status: Literal["generated", "not_detected"]
    items: list[ReportItem]
    limitations: list[str]


class AtlasReport(BaseModel):
    summary: str
    architecture: ReportSection
    flows: ReportSection
    guide: ReportSection
    recommendations: ReportSection


class AtlasDocument(BaseModel):
    schema_version: Literal["0.2"] = "0.2"
    repository: dict[str, str]
    technologies: list[str]
    nodes: list[AtlasNode]
    relationships: list[AtlasRelationship]
    counts: dict[str, int]
    limitations: list[str]
    report: AtlasReport | None = None

    @model_validator(mode="after")
    def validate_graph(self):
        ids = {node.id for node in self.nodes}
        nodes_by_id = {node.id: node for node in self.nodes}
        if len(ids) != len(self.nodes):
            raise ValueError("Duplicate node identity")
        if any(edge.source not in ids or edge.target not in ids for edge in self.relationships):
            raise ValueError("Relationship references missing node")
        if self.report:
            edge_keys = {(e.source, e.target, e.type, e.resolution) for e in self.relationships}
            report_ids = set()
            for section in (self.report.architecture, self.report.flows, self.report.guide,
                            self.report.recommendations):
                if (section.status == "generated") != bool(section.items):
                    raise ValueError("Report status must match detected items")
                for item in section.items:
                    if item.id in report_ids:
                        raise ValueError("Duplicate report identity")
                    report_ids.add(item.id)
                    if not item.node_ids or not item.evidence:
                        raise ValueError("Report items require graph evidence")
                    if any(node_id not in ids for node_id in item.node_ids):
                        raise ValueError("Report references missing node")
                    evidence_keys = {(e.path, e.lines, e.reason)
                                     for node_id in item.node_ids
                                     for e in nodes_by_id[node_id].evidence}
                    if any((e.path, e.lines, e.reason) not in evidence_keys for e in item.evidence):
                        raise ValueError("Report evidence must come from its cited nodes")
                    if any((s.source, s.target, s.type, s.resolution) not in edge_keys
                           for s in item.steps):
                        raise ValueError("Report step must reference an existing relationship")
        return self
