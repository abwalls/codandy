import { z } from "zod";

// structure-0.1: declared data models and data contracts, served beside atlas 0.2.
// Mirrors backend/app/structure/models.py; keep both schemas in step.
const evidence = z.object({ path: z.string(), lines: z.string().nullable().optional(), reason: z.string() });
const cardinality = z.enum(["one", "many", "unknown"]);
const line = z.number().int().min(1).nullable();
const entityField = z.object({
  name: z.string(), type: z.string(), primary: z.boolean(), unique: z.boolean(), foreign: z.boolean(),
  nullable: z.boolean().nullable(), line,
});
const linkEnd = z.object({ entity: z.string().nullable(), name: z.string(), fields: z.array(z.string()), cardinality, optional: z.boolean().nullable() });
const entity = z.object({
  id: z.string(), source_id: z.string(), name: z.string(), table: z.string().nullable(), namespace: z.string().nullable(),
  kind: z.enum(["table", "view", "model"]), fields: z.array(entityField), omitted_fields: z.number().int().min(0),
  node_id: z.string().nullable(), evidence: z.array(evidence).min(1),
});
const entityLink = z.object({
  id: z.string(), source_id: z.string(), source: linkEnd, target: linkEnd, label: z.string(),
  basis: z.enum(["declared", "orm_relation"]), resolution: z.enum(["resolved", "unresolved", "ambiguous"]),
  evidence: z.array(evidence).min(1),
});
const dataType = z.object({
  id: z.string(), name: z.string(), language: z.enum(["Python", "TypeScript"]),
  kind: z.enum(["pydantic", "dataclass", "typed_dict", "interface", "type_alias"]), path: z.string(),
  members: z.array(z.object({ name: z.string(), type: z.string(), line })), omitted_members: z.number().int().min(0),
  node_id: z.string().nullable(), evidence: z.array(evidence).min(1),
});
const typeLink = z.object({
  id: z.string(), source: z.string(), target: z.string(), kind: z.enum(["extends", "field_type"]),
  member: z.string().nullable(), resolution: z.enum(["resolved", "inferred"]), evidence: z.array(evidence).min(1),
});

export const structureSchema = z.object({
  schema_version: z.literal("structure-0.1"),
  atlas_schema: z.literal("0.2"),
  sources: z.array(z.object({ id: z.string(), kind: z.enum(["prisma", "sql", "sqlalchemy", "django"]), root: z.string(), files: z.array(z.string()).min(1) })),
  entities: z.array(entity),
  entity_links: z.array(entityLink),
  types: z.array(dataType),
  type_links: z.array(typeLink),
  counts: z.record(z.number().int()),
  limitations: z.array(z.string()),
}).superRefine((document, context) => {
  const fail = (message: string) => context.addIssue({ code: z.ZodIssueCode.custom, message });
  for (const [label, ids] of [["schema source", document.sources.map(item => item.id)], ["entity", document.entities.map(item => item.id)],
    ["entity link", document.entity_links.map(item => item.id)], ["type", document.types.map(item => item.id)], ["type link", document.type_links.map(item => item.id)]] as const) {
    if (new Set(ids).size !== ids.length) fail(`Duplicate ${label} identity`);
  }
  const sources = new Set(document.sources.map(item => item.id));
  const owners = new Map(document.entities.map(item => [item.id, item.source_id]));
  if (document.entities.some(item => !sources.has(item.source_id))) fail("Entity references a missing schema source");
  for (const link of document.entity_links) {
    if (link.source.entity === null || owners.get(link.source.entity) !== link.source_id) fail("An entity link must start at an entity of its schema source");
    if ((link.resolution === "resolved") !== (link.target.entity !== null)) fail("Only resolved entity links name a target entity");
    if (link.target.entity !== null && owners.get(link.target.entity) !== link.source_id) fail("Entity links stay inside one schema source");
  }
  const types = new Set(document.types.map(item => item.id));
  if (document.type_links.some(link => !types.has(link.source) || !types.has(link.target))) fail("Type link references a missing type");
});

export type StructureDocument = z.infer<typeof structureSchema>;
export type StructureEntity = StructureDocument["entities"][number];
export type StructureEntityLink = StructureDocument["entity_links"][number];
export type StructureType = StructureDocument["types"][number];
export type StructureTypeLink = StructureDocument["type_links"][number];
export type SchemaSourceKind = StructureDocument["sources"][number]["kind"];
