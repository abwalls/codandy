"""structure-0.1: declared data models and data contracts, stored beside atlas 0.2.

Everything here is a static declaration read from source text. Nothing is imported, executed,
migrated or connected to, so a declared schema can differ from a live database.
"""

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.models import AtlasDocument

EXTRACTION_FAILED = (
    "Data model extraction failed for this report, so data model and contract diagrams are "
    "unavailable. Other report sections are unaffected.")
SourceKind = Literal["prisma", "sql", "sqlalchemy", "django"]
Cardinality = Literal["one", "many", "unknown"]


class StructureEvidence(BaseModel):
    path: str
    lines: str | None = None
    reason: str


class SchemaSource(BaseModel):
    """One declared schema: the declarations of one kind inside one project directory."""

    id: str
    kind: SourceKind
    root: str
    files: list[str] = Field(min_length=1)


class EntityField(BaseModel):
    name: str
    type: str = ""
    primary: bool = False
    unique: bool = False
    foreign: bool = False
    # None when neither the declaration nor the framework's documented default states it.
    nullable: bool | None = None
    line: int | None = Field(default=None, ge=1)


class Entity(BaseModel):
    id: str
    source_id: str
    name: str
    table: str | None = None
    namespace: str | None = None
    kind: Literal["table", "view", "model"]
    fields: list[EntityField]
    omitted_fields: int = Field(default=0, ge=0)
    node_id: str | None = None
    evidence: list[StructureEvidence] = Field(min_length=1)


class LinkEnd(BaseModel):
    entity: str | None = None
    name: str
    fields: list[str] = Field(default_factory=list)
    cardinality: Cardinality
    optional: bool | None = None


class EntityLink(BaseModel):
    """`source` declares the reference (it holds the foreign key); `target` is referenced.

    `target.cardinality` is how many target rows one source row relates to, and
    `source.cardinality` is how many source rows can relate to one target row.
    """

    id: str
    source_id: str
    source: LinkEnd
    target: LinkEnd
    label: str = ""
    basis: Literal["declared", "orm_relation"]
    resolution: Literal["resolved", "unresolved", "ambiguous"]
    evidence: list[StructureEvidence] = Field(min_length=1)


class TypeMember(BaseModel):
    name: str
    type: str = ""
    line: int | None = Field(default=None, ge=1)


class DataType(BaseModel):
    id: str
    name: str
    language: Literal["Python", "TypeScript"]
    kind: Literal["pydantic", "dataclass", "typed_dict", "interface", "type_alias"]
    path: str
    members: list[TypeMember]
    omitted_members: int = Field(default=0, ge=0)
    node_id: str | None = None
    evidence: list[StructureEvidence] = Field(min_length=1)


class TypeLink(BaseModel):
    id: str
    source: str
    target: str
    kind: Literal["extends", "field_type"]
    member: str | None = None
    resolution: Literal["resolved", "inferred"]
    evidence: list[StructureEvidence] = Field(min_length=1)


class StructureDocument(BaseModel):
    schema_version: Literal["structure-0.1"] = "structure-0.1"
    atlas_schema: Literal["0.2"] = "0.2"
    sources: list[SchemaSource] = Field(default_factory=list)
    entities: list[Entity] = Field(default_factory=list)
    entity_links: list[EntityLink] = Field(default_factory=list)
    types: list[DataType] = Field(default_factory=list)
    type_links: list[TypeLink] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_references(self):
        for label, ids in (("schema source", [source.id for source in self.sources]),
                           ("entity", [entity.id for entity in self.entities]),
                           ("entity link", [link.id for link in self.entity_links]),
                           ("type", [item.id for item in self.types]),
                           ("type link", [link.id for link in self.type_links])):
            if len(set(ids)) != len(ids):
                raise ValueError(f"Duplicate {label} identity")
        sources = {source.id for source in self.sources}
        owners = {}
        for entity in self.entities:
            if entity.source_id not in sources:
                raise ValueError("Entity references a missing schema source")
            owners[entity.id] = entity.source_id
        for link in self.entity_links:
            if owners.get(link.source.entity) != link.source_id:
                raise ValueError("An entity link must start at an entity of its schema source")
            if (link.resolution == "resolved") != (link.target.entity is not None):
                raise ValueError("Only resolved entity links name a target entity")
            if link.target.entity is not None and owners.get(link.target.entity) != link.source_id:
                raise ValueError("Entity links stay inside one schema source")
        types = {item.id for item in self.types}
        if any(link.source not in types or link.target not in types for link in self.type_links):
            raise ValueError("Type link references a missing type")
        return self


def validate_against_atlas(structure: StructureDocument, atlas: AtlasDocument) -> None:
    """Every cited path must be an indexed file and every node reference an atlas node."""
    files = {node.path for node in atlas.nodes if node.kind == "file"}
    ids = {node.id for node in atlas.nodes}
    evidence = [item for group in (*structure.entities, *structure.entity_links,
                                   *structure.types, *structure.type_links)
                for item in group.evidence]
    paths = [item.path for item in evidence]
    paths += [path for source in structure.sources for path in source.files]
    paths += [item.path for item in structure.types]
    if any(path not in files for path in paths):
        raise ValueError("Structure evidence must cite indexed files")
    if any(item.node_id is not None and item.node_id not in ids
           for item in (*structure.entities, *structure.types)):
        raise ValueError("Structure references a missing atlas node")


def checked_structure(structure: "StructureDocument | None",
                      atlas: AtlasDocument) -> StructureDocument:
    """The structure document if it matches this atlas, otherwise a visible failure."""
    if structure is not None:
        try:
            validate_against_atlas(structure, atlas)
            return structure
        except ValueError:
            pass
    return StructureDocument(limitations=[EXTRACTION_FAILED])
