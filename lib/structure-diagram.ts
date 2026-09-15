import type { StructureDocument, StructureEntity, StructureEntityLink, StructureType, StructureTypeLink } from "./structure-api";

export type LinkEndMark = { cardinality: "one" | "many" | "unknown"; optional: boolean | null };
export type DiagramRow = { name: string; type: string; badges: ("PK" | "FK" | "UQ")[]; nullable: boolean | null; line: number | null };
export type DiagramRecord = {
  id: string;
  title: string;
  subtitle: string;
  rows: DiagramRow[];
  hiddenRows: number;
  /** A reference target outside the drawn set: undeclared, ambiguous or in another folder. */
  stub: boolean;
  /** The entity or type this record represents, when there is one to focus. */
  refId: string | null;
};
export type DiagramLink = {
  id: string;
  /** Layout direction: ERD links run from the referenced table to the table holding the reference. */
  source: string;
  target: string;
  sourceRow: number | null;
  targetRow: number | null;
  /** Crow's-foot marks for the source and target ends (ERD only). */
  start: LinkEndMark | null;
  end: LinkEndMark | null;
  kind: "relation" | "field" | "extends";
  dashed: boolean;
  label: string;
  description: string;
};
export type DiagramView = { records: DiagramRecord[]; links: DiagramLink[]; total: number; hiddenRecords: number; hiddenLinks: number };

export const ROW_LIMIT = 16;
export const TYPE_KIND_LABELS: Record<StructureType["kind"], string> = {
  pydantic: "Pydantic model", dataclass: "Dataclass", typed_dict: "TypedDict", interface: "Interface", type_alias: "Object type",
};

export const typeFolder = (path: string) => (path.includes("/") ? path.slice(0, path.lastIndexOf("/")) : "");
const fileName = (path: string) => path.slice(path.lastIndexOf("/") + 1);

function rowIndex(record: DiagramRecord, names: string[]) {
  const wanted = new Set(names.map(name => name.toLowerCase()));
  const index = record.rows.findIndex(row => wanted.has(row.name.toLowerCase()));
  return index >= 0 ? index : null;
}

/** How many rows on one side of a relationship relate to one row on the other. */
export function cardinalityText(end: LinkEndMark) {
  if (end.cardinality === "unknown") return "an unstated number of";
  if (end.cardinality === "one") return end.optional === true ? "zero or one" : end.optional === false ? "exactly one" : "one";
  return end.optional === true ? "zero or more" : end.optional === false ? "one or more" : "many";
}

export function entitySubtitle(entity: StructureEntity) {
  const table = entity.table && entity.namespace ? `${entity.namespace}.${entity.table}` : entity.table !== entity.name ? entity.table : null;
  return [table, entity.kind].filter(Boolean).join(" · ");
}

export function entityKeys(field: StructureEntity["fields"][number]) {
  return [...(field.primary ? ["PK" as const] : []), ...(field.foreign ? ["FK" as const] : []), ...(field.unique && !field.primary ? ["UQ" as const] : [])];
}

export function describeEntityLink(link: StructureEntityLink, nameOf: (id: string | null) => string) {
  const child = nameOf(link.source.entity);
  const parent = link.target.entity ? nameOf(link.target.entity) : link.target.name;
  const fields = link.source.fields.length ? `.${link.source.fields.join(", ")}` : "";
  const basis = link.basis === "declared" ? "Declared reference" : "ORM relation";
  const state = link.resolution === "ambiguous" ? "; several declarations match the target" : link.resolution === "unresolved" ? "; the target is not declared in this schema" : "";
  return `${child}${fields} → ${parent}: each ${child} relates to ${cardinalityText(link.target)} ${parent}, and each ${parent} to ${cardinalityText(link.source)} ${child}. ${basis}${state}.`;
}

export type ErdOptions = { query?: string; focus?: string | null; keysOnly?: boolean; limit?: number };

/** Tables of one schema source, the most connected first, with stubs for undeclared targets. */
export function erdView(structure: StructureDocument, sourceId: string, options: ErdOptions = {}): DiagramView {
  const { query = "", focus = null, keysOnly = false, limit = 60 } = options;
  const entities = structure.entities.filter(entity => entity.source_id === sourceId);
  const links = structure.entity_links.filter(link => link.source_id === sourceId);
  const names = new Map(entities.map(entity => [entity.id, entity.name]));
  const nameOf = (id: string | null) => (id ? names.get(id) ?? id : "unknown");
  const degree = new Map<string, number>();
  for (const link of links) for (const id of [link.source.entity, link.target.entity]) if (id) degree.set(id, (degree.get(id) ?? 0) + 1);
  const needle = query.trim().toLowerCase();
  const near = focus ? new Set([focus, ...links.filter(link => link.source.entity === focus || link.target.entity === focus)
    .flatMap(link => [link.source.entity, link.target.entity]).filter((id): id is string => id !== null)]) : null;
  const shown = entities
    .filter(entity => (!needle || `${entity.name} ${entity.table ?? ""}`.toLowerCase().includes(needle)) && (!near || near.has(entity.id)))
    .sort((a, b) => Number(b.id === focus) - Number(a.id === focus) || (degree.get(b.id) ?? 0) - (degree.get(a.id) ?? 0) || a.name.localeCompare(b.name))
    .slice(0, limit);

  const records = new Map<string, DiagramRecord>();
  for (const entity of shown) {
    const fields = keysOnly ? entity.fields.filter(field => field.primary || field.foreign) : entity.fields;
    const rows = fields.slice(0, ROW_LIMIT).map(field => ({ name: field.name, type: field.type, badges: entityKeys(field), nullable: field.nullable, line: field.line }));
    records.set(entity.id, { id: entity.id, title: entity.name, subtitle: entitySubtitle(entity), rows, hiddenRows: entity.fields.length - rows.length + entity.omitted_fields, stub: false, refId: entity.id });
  }
  const stubs = new Map<string, DiagramRecord>();
  const drawn: DiagramLink[] = [];
  let hiddenLinks = 0;
  for (const link of links) {
    const child = link.source.entity ? records.get(link.source.entity) : undefined;
    let parent = link.target.entity ? records.get(link.target.entity) : undefined;
    if (!child || (link.target.entity && !parent)) {
      hiddenLinks++;
      continue;
    }
    if (!parent) {
      const id = `stub:${link.resolution}:${link.target.name}`;
      if (!stubs.has(id)) {
        stubs.set(id, { id, title: link.target.name, subtitle: link.resolution === "ambiguous" ? "several declarations match" : "not declared in this schema", rows: [], hiddenRows: 0, stub: true, refId: null });
      }
      parent = stubs.get(id)!;
    }
    drawn.push({
      id: link.id, source: parent.id, target: child.id,
      sourceRow: rowIndex(parent, link.target.fields) ?? (parent.rows.findIndex(row => row.badges.includes("PK")) >= 0 ? parent.rows.findIndex(row => row.badges.includes("PK")) : null),
      targetRow: rowIndex(child, link.source.fields),
      start: { cardinality: link.target.cardinality, optional: link.target.optional },
      end: { cardinality: link.source.cardinality, optional: link.source.optional },
      kind: "relation", dashed: link.basis !== "declared" || link.resolution !== "resolved", label: link.label,
      description: describeEntityLink(link, nameOf),
    });
  }
  return { records: [...records.values(), ...stubs.values()], links: drawn, total: entities.length, hiddenRecords: entities.length - shown.length, hiddenLinks };
}

export function contractAreas(structure: StructureDocument) {
  const counts = new Map<string, number>();
  for (const type of structure.types) counts.set(typeFolder(type.path), (counts.get(typeFolder(type.path)) ?? 0) + 1);
  return [...counts.entries()]
    .map(([id, count]) => ({ id, label: id || "Repository root", count }))
    .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label));
}

export function describeTypeLink(link: StructureTypeLink, nameOf: (id: string) => string) {
  const owner = `${nameOf(link.source)}${link.member ? `.${link.member}` : ""}`;
  const verb = link.kind === "extends" ? "extends" : "uses";
  const basis = link.resolution === "inferred" ? "inferred from a unique type name; the import was not verified" : "resolved in the same file or a local import";
  return `${owner} ${verb} ${nameOf(link.target)} (${basis}).`;
}

export type ContractOptions = { area?: string | null; query?: string; focus?: string | null; inheritance?: boolean; limit?: number };

/** Types in one folder (or a focused type's neighbourhood), with stubs for referenced types elsewhere. */
export function contractsView(structure: StructureDocument, options: ContractOptions = {}): DiagramView {
  const { area = null, query = "", focus = null, inheritance = true, limit = 60 } = options;
  const types = new Map(structure.types.map(type => [type.id, type]));
  const nameOf = (id: string) => types.get(id)?.name ?? id;
  const links = structure.type_links.filter(link => inheritance || link.kind !== "extends");
  const degree = new Map<string, number>();
  for (const link of links) for (const id of [link.source, link.target]) degree.set(id, (degree.get(id) ?? 0) + 1);
  const needle = query.trim().toLowerCase();
  const near = focus ? new Set([focus, ...links.filter(link => link.source === focus || link.target === focus).flatMap(link => [link.source, link.target])]) : null;
  const shown = structure.types
    .filter(type => (near ? near.has(type.id) : area === null || typeFolder(type.path) === area) && (!needle || type.name.toLowerCase().includes(needle)))
    .sort((a, b) => Number(b.id === focus) - Number(a.id === focus) || (degree.get(b.id) ?? 0) - (degree.get(a.id) ?? 0) || a.name.localeCompare(b.name))
    .slice(0, limit);

  const records = new Map<string, DiagramRecord>();
  for (const type of shown) {
    const rows = type.members.slice(0, ROW_LIMIT).map(member => ({ name: member.name, type: member.type, badges: [], nullable: null, line: member.line }));
    records.set(type.id, { id: type.id, title: type.name, subtitle: `${TYPE_KIND_LABELS[type.kind]} · ${fileName(type.path)}`, rows, hiddenRows: type.members.length - rows.length + type.omitted_members, stub: false, refId: type.id });
  }
  const stubs = new Map<string, DiagramRecord>();
  const drawn: DiagramLink[] = [];
  let hiddenLinks = 0;
  for (const link of links) {
    const owner = records.get(link.source);
    if (!owner) {
      if (records.has(link.target)) hiddenLinks++;
      continue;
    }
    let target = records.get(link.target) ?? stubs.get(link.target);
    if (!target) {
      const type = types.get(link.target)!;
      target = { id: `stub:${type.id}`, title: type.name, subtitle: `in ${typeFolder(type.path) || "the repository root"}`, rows: [], hiddenRows: 0, stub: true, refId: type.id };
      stubs.set(link.target, target);
    }
    drawn.push({
      id: link.id, source: owner.id, target: target.id,
      sourceRow: link.member ? rowIndex(owner, [link.member]) : null, targetRow: null,
      start: null, end: null, kind: link.kind === "extends" ? "extends" : "field", dashed: link.resolution === "inferred",
      label: link.member ?? "", description: describeTypeLink(link, nameOf),
    });
  }
  return { records: [...records.values(), ...stubs.values()], links: drawn, total: structure.types.length, hiddenRecords: structure.types.length - shown.length, hiddenLinks };
}

// Mermaid text export. Repository names are untrusted, so every identifier is reduced to a safe
// token and labels lose quotes and line breaks. The page never renders this text as a diagram.
function token(value: string, fallback: string, extra = "") {
  const cleaned = value.replace(new RegExp(`[^A-Za-z0-9_${extra}]+`, "g"), "_").replace(/^_+|_+$/g, "");
  if (!cleaned) return fallback;
  return /^[A-Za-z_]/.test(cleaned) ? cleaned : `_${cleaned}`;
}

function uniqueTokens(items: { id: string; name: string }[]) {
  const used = new Set<string>();
  const names = new Map<string, string>();
  for (const item of items) {
    const base = token(item.name, "unnamed");
    let name = base;
    for (let ordinal = 2; used.has(name); ordinal++) name = `${base}_${ordinal}`;
    used.add(name);
    names.set(item.id, name);
  }
  return names;
}

const label = (value: string) => `"${value.replace(/["\\\r\n]+/g, " ").trim().slice(0, 60) || "references"}"`;
// Mermaid marks: the left pair describes the left entity, the right pair the right entity.
// Optionality that is not stated is exported as zero-or-one or zero-or-more, the weaker claim.
const leftMark = (end: LinkEndMark) => (end.cardinality === "one" ? (end.optional === false ? "||" : "|o") : end.optional === false ? "}|" : "}o");
const rightMark = (end: LinkEndMark) => (end.cardinality === "one" ? (end.optional === false ? "||" : "o|") : end.optional === false ? "|{" : "o{");

export function mermaidErDiagram(entities: StructureEntity[], links: StructureEntityLink[]) {
  const names = uniqueTokens(entities.map(entity => ({ id: entity.id, name: entity.table ?? entity.name })));
  const lines = ["erDiagram"];
  for (const entity of entities) {
    if (!entity.fields.length) continue;
    lines.push(`    ${names.get(entity.id)} {`);
    for (const field of entity.fields) {
      const keys = entityKeys(field).map(key => (key === "UQ" ? "UK" : key)).join(", ");
      lines.push(`        ${token(field.type, "unknown")} ${token(field.name, "field")}${keys ? ` ${keys}` : ""}`);
    }
    lines.push("    }");
  }
  for (const link of links) {
    const child = link.source.entity ? names.get(link.source.entity) : undefined;
    const parent = link.target.entity ? names.get(link.target.entity) : undefined;
    if (!child || !parent) {
      lines.push(`    %% not drawn: ${child ?? "unknown"} references ${token(link.target.name, "unknown")} (${link.resolution})`);
      continue;
    }
    lines.push(`    ${parent} ${leftMark(link.target)}${link.basis === "declared" ? "--" : ".."}${rightMark(link.source)} ${child} : ${label(link.label)}`);
  }
  return `${lines.join("\n")}\n`;
}

export function mermaidClassDiagram(types: StructureType[], links: StructureTypeLink[]) {
  const names = uniqueTokens(types);
  const lines = ["classDiagram"];
  for (const type of types) {
    const name = names.get(type.id)!;
    if (!type.members.length) {
      lines.push(`    class ${name}`);
      continue;
    }
    lines.push(`    class ${name} {`);
    for (const member of type.members) lines.push(`        ${token(member.type.replace(/[[\]<>]/g, "~"), "unknown", "~")} ${token(member.name, "member")}`);
    lines.push("    }");
  }
  for (const link of links) {
    const source = names.get(link.source);
    const target = names.get(link.target);
    if (!source || !target) continue;
    if (link.kind === "extends") lines.push(`    ${target} <|-- ${source}`);
    else lines.push(`    ${source} ${link.resolution === "inferred" ? "..>" : "-->"} ${target} : ${token(link.member ?? "", "uses")}`);
  }
  return `${lines.join("\n")}\n`;
}
