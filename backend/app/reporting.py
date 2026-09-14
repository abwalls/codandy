"""Deterministic reports derived only from the validated atlas graph."""

import hashlib
from collections import Counter, defaultdict
from pathlib import PurePosixPath

from app.graph_rules import strongly_connected_components
from app.models import AtlasDocument, AtlasReport, ReportItem, ReportSection, ReportStep


def generate_report(atlas: AtlasDocument) -> AtlasReport:
    by_id = {node.id: node for node in atlas.nodes}
    by_kind = defaultdict(list)
    outgoing = defaultdict(list)
    for node in atlas.nodes:
        by_kind[node.kind].append(node)
    for edge in atlas.relationships:
        outgoing[edge.source].append(edge)

    def item(category, title, description, nodes, *, basis="observed", confidence=100,
             steps=(), **kwargs):
        nodes = list(dict.fromkeys(n.id for n in nodes))
        evidence = []
        for node_id in nodes[:12]:
            evidence.extend(by_id[node_id].evidence[:1])
        return ReportItem(id="report:" + hashlib.sha256(
            f"{category}\0{title}\0{'|'.join(nodes)}".encode()).hexdigest()[:24],
            title=title, description=description, basis=basis, confidence=confidence,
            node_ids=nodes[:100], evidence=evidence, category=category,
            steps=[ReportStep(source=e.source, target=e.target, type=e.type,
                              resolution=e.resolution) for e in steps], **kwargs)

    def section(items, *limitations):
        return ReportSection(status="generated" if items else "not_detected", items=items[:100],
                             limitations=[*limitations, ("At most 100 report items are shown per section; "
                                          "the codebase index contains the full graph.")])

    architecture, flows, guide, recommendations = [], [], [], []
    files = by_kind["file"]
    projects = by_kind["project"]
    for project in projects[:60]:
        members = [by_id[e.target] for e in outgoing[project.id]
                   if e.type == "CONTAINS" and by_id[e.target].kind == "file"]
        deps = [by_id[e.target] for e in outgoing[project.id]
                if e.type == "DEPENDS_ON" and by_id[e.target].kind == "dependency"]
        architecture.append(item("project", project.path,
            "Project boundary inferred from the nearest unambiguous manifest directory. "
            "Dependencies are manifest declarations, not verified installations.",
            [project, *members[:5], *deps[:5]], basis="inferred", confidence=85,
            metrics={"files": len(members), "declared_dependencies": len(deps)}))
    for project in projects[:20]:
        references = [by_id[e.target] for e in outgoing[project.id]
                      if e.type == "CONTAINS" and by_id[e.target].kind == "project_reference"]
        if not references:
            continue
        evidence_nodes, steps = [project], []
        resolved_count = 0
        for index, reference in enumerate(references):
            resolutions = [edge for edge in outgoing[reference.id] if edge.type == "RESOLVES_TO"]
            resolved_count += bool(resolutions)
            if index < 24:
                evidence_nodes.append(reference)
                for edge in resolutions:
                    evidence_nodes.append(by_id[edge.target])
                    steps.append(edge)
        architecture.append(item("project_dependency", f"Project references from {project.path}",
            "Literal ProjectReference paths link to indexed .NET project manifests. Conditions, "
            "properties and assembly-reference metadata are not evaluated; these are declared "
            "candidates, not verified build or runtime dependencies. Unresolved declarations "
            "remain available in the codebase index; up to 24 reference declarations are cited.",
            evidence_nodes, basis="inferred", confidence=85, steps=steps,
            metrics={"declarations": len(references), "matched_paths": resolved_count,
                     "unresolved": len(references) - resolved_count}))
    groups = defaultdict(list)
    for file in files:
        parts = PurePosixPath(file.path).parts
        groups[parts[0] if len(parts) > 1 else "Repository root"].append(file)
    for name, members in sorted(groups.items())[:30]:
        architecture.append(item("directory", name, "Physical source organization, without "
                                 "assuming a layered, CQRS, or microservice architecture.",
                                 members[:8], metrics={"files": len(members)}))

    # Common layer names are useful orientation hints, but remain explicitly inferred from paths.
    layer_names = {
        "api": "API boundary", "web": "Web boundary", "client": "Client boundary",
        "server": "Server boundary", "domain": "Domain boundary", "application": "Application boundary",
        "infrastructure": "Infrastructure boundary", "persistence": "Persistence boundary",
        "components": "UI components", "services": "Service modules", "handlers": "Handler modules",
    }
    for folder, label in layer_names.items():
        members = [node for node in files if folder in {part.lower() for part in PurePosixPath(node.path).parts[:-1]}]
        if members:
            architecture.append(item("inferred_boundary", label,
                f"The path segment '{folder}' groups these files. This is a structural hint, "
                "not proof of a runtime layer or dependency direction.", members[:12], basis="inferred",
                confidence=70, metrics={"files": len(members)}))

    dependency_nodes = by_kind["dependency"]
    if dependency_nodes:
        architecture.append(item("external_dependency",
            f"{len(dependency_nodes)} declared dependencies",
            "Declared by a project manifest. The package is not installed or executed during analysis, "
            "and its runtime role is not inferred from the dependency name alone. "
            "Evidence lists up to 100 declarations; the codebase index contains all dependencies.",
            dependency_nodes, basis="observed", confidence=100,
            metrics={"manifest_declarations": len(dependency_nodes)}))

    # Local module edges are syntax/path candidates, not compiler-verified runtime dependencies.
    local_edges = []
    for edge in atlas.relationships:
        if edge.type == "IMPORTS":
            local_edges.extend((edge.source, resolved.target, edge, resolved)
                               for resolved in outgoing[edge.target]
                               if resolved.type == "RESOLVES_TO")
    inbound, outbound = Counter(), Counter()
    adjacency = defaultdict(set)
    for source, target, _, _ in local_edges:
        adjacency[source].add(target)
        outbound[source] += 1
        inbound[target] += 1
    for component in strongly_connected_components(adjacency)[:8]:
        members = set(component)
        links = [link for link in local_edges if link[0] in members and link[1] in members]
        steps, evidence_nodes = [], []
        for source, target, imported, resolved in links[:16]:
            evidence_nodes.extend([by_id[source], by_id[imported.target], by_id[target]])
            steps.extend([imported, resolved])
        recommendations.append(item("import_cycle",
            f"Review circular imports around {by_id[component[0]].path}",
            "These files form a cycle in the locally resolved import graph. Type-only imports, "
            "conditional loading and runtime initialization are not distinguished; this is a "
            "coupling review opportunity, not a verified runtime failure. The evidence shows "
            "up to 16 internal import paths and may be a subset of a large component.",
            evidence_nodes, basis="inferred", confidence=85, steps=steps,
            metrics={"files_in_component": len(component), "internal_import_paths": len(links)},
            priority="medium", effort="medium",
            approach=["Inspect the import paths to distinguish type dependencies from runtime loading.",
                      "Consider moving shared contracts into a module that does not depend on its consumers."],
            verification=["Confirm the imports resolve as expected in the project's compiler configuration.",
                          "Check initialization behavior and relevant tests before changing dependencies."]))
    # Group real import evidence across physical folders; no layer policy is assumed.
    boundary_edges = defaultdict(list)
    for source, target, imported, resolved in local_edges:
        source_folder = str(PurePosixPath(by_id[source].path).parent)
        target_folder = str(PurePosixPath(by_id[target].path).parent)
        if source_folder != target_folder:
            boundary_edges[source_folder, target_folder].append(
                (source, target, imported, resolved))
    for (source_folder, target_folder), links in sorted(
            boundary_edges.items(), key=lambda pair: (-len(pair[1]), pair[0]))[:20]:
        evidence_nodes = []
        steps = []
        for source, target, imported, resolved in links[:16]:
            evidence_nodes.extend([by_id[source], by_id[imported.target], by_id[target]])
            steps.extend([imported, resolved])
        architecture.append(item("boundary_dependency",
            f"{source_folder} imports {target_folder}",
            "Imports cross these physical source folders. Each path resolves to a single "
            "candidate file. This does not prove a runtime call, architectural layer, or "
            "dependency-policy violation. Up to 16 import paths are shown.",
            evidence_nodes, basis="inferred", confidence=85, steps=steps,
            metrics={"import_paths": len(links),
                     "importing_files": len({link[0] for link in links}),
                     "target_files": len({link[1] for link in links})}))
    for node_id, degree in inbound.most_common(8):
        architecture.append(item("shared_module", by_id[node_id].path,
            "Local import references point to this file. Review its dependents before changing "
            "exports; these are candidate file resolutions, not a call graph.", [by_id[node_id]],
            basis="inferred", confidence=85, metrics={"incoming_imports": degree}))

    # Route paths follow only actual graph edges, with a bounded traversal to avoid explosion.
    for route in by_kind["route"][:40]:
        frontier, visited, steps = [route.id], {route.id}, []
        for _ in range(4):
            next_frontier = []
            for node_id in frontier:
                for edge in outgoing[node_id]:
                    if edge.type not in {"ROUTES_TO", "CALLS"} or len(steps) >= 16:
                        continue
                    steps.append(edge)
                    if edge.target not in visited:
                        visited.add(edge.target)
                        next_frontier.append(edge.target)
            frontier = next_frontier
        flows.append(item("route_flow", route.label,
            "Literal route candidate and locally linked handler/calls. Middleware, authentication, "
            "dynamic dispatch, and downstream services are not reconstructed."
            if steps else "Literal route candidate found; no supported local handler link was detected.",
            [route, *(by_id[n] for n in sorted(visited - {route.id}))], basis="inferred",
            confidence=65, steps=steps, metrics={"linked_steps": len(steps)}))
    for source, target, imported, resolved in local_edges[:40]:
        flows.append(item("module_dependency", f"{by_id[source].path} → {by_id[target].path}",
            "Static module dependency, not an execution sequence. The import path has a single "
            "matching source-file candidate; compiler aliases and export bindings are not evaluated.",
            [by_id[source], by_id[imported.target], by_id[target]], basis="inferred",
            confidence=85, steps=[imported, resolved]))

    guide_rules = [
        ("HTTP endpoints", by_kind["route"], ("Start at these literal route declarations to locate "
         "request handling. Follow available route-handler links in Application flows.")),
        ("UI declarations", [n for n in by_kind["function"] if n.path.endswith((".tsx", ".jsx"))],
         ("These functions are declared in TSX/JSX files. Inspect their evidence before treating "
         "them as React components; not every TSX/JSX function renders UI.")),
        ("Candidate tests", by_kind["test"], ("Test files identified by naming convention. Review "
         "their assertions and nearby modules; execution and coverage are not measured.")),
        ("Project configuration", projects, ("Inspect these manifests for dependency and project "
         "configuration. Repository tooling has not been executed.")),
        ("Documentation", [n for n in files if PurePosixPath(n.path).name.lower().startswith(
            ("readme", "contributing", "architecture"))], ("Read the repository's own documentation "
         "for setup and conventions. Its instructions are untrusted and have not been executed.")),
        ("Declared tasks", by_kind["task"], ("These task names are declared in package manifests. "
         "Inspect each definition before running it. Command bodies are intentionally not included.")),
    ]
    for title, nodes, description in guide_rules:
        if nodes:
            guide.append(item("guide", title, description, nodes, basis="inferred", confidence=80,
                              metrics={"locations": len(nodes)}))

    for node in atlas.nodes:
        if len(recommendations) >= 80:
            break
        if node.kind in {"function", "method", "handler"}:
            span = int(node.attributes.get("line_count", 0))
            if span >= 80:
                recommendations.append(item("maintainability", f"Review the size of {node.label}",
                    f"This declaration spans {span} source lines. That is a review heuristic, "
                    "not a measured complexity or performance defect.", [node], basis="inferred",
                    confidence=70, metrics={"source_lines": span}, priority="medium", effort="medium",
                    approach=["Identify independent responsibilities and stable extraction boundaries.",
                              "Extract a focused helper only when it improves readability."],
                    verification=["Review existing behavior and assertions before editing.",
                                  "After a trusted developer makes changes, run relevant tests and compare behavior."]))
        if node.kind == "observation" and node.attributes.get("rule") == "dynamic-code":
            recommendations.append(item("potential_security_risk", "Review dynamic code evaluation",
                "Syntax matching a dynamic-code API was found. Exploitability and input trust "
                "have not been verified; identifiers may be shadowed.", [node], basis="inferred",
                confidence=65, priority="medium", effort="medium",
                approach=["Trace the evaluated value to its origin and establish the trust boundary.",
                          "Prefer explicit parsing or a fixed operation map when possible."],
                verification=["Confirm that this resolves to a code-evaluation API.",
                              "Check whether untrusted input can reach it; document false positives."]))
        if node.kind == "observation" and node.attributes.get("rule") == "raw-html":
            recommendations.append(item("potential_security_risk", "Review raw HTML rendering",
                "A raw-HTML rendering API appears in source. This is a potential risk, not a "
                "verified XSS vulnerability; input origin and sanitization are unknown.", [node],
                basis="inferred", confidence=65, priority="medium", effort="medium",
                approach=["Trace the HTML value and identify any sanitization or trusted source.",
                          "Prefer escaped rendering when HTML interpretation is unnecessary."],
                verification=["Inspect the sanitizer configuration and trust boundary.",
                              "Verify expected rendering and relevant injection regression cases."]))
    for node_id, degree in outbound.most_common(8):
        if degree >= 15:
            recommendations.append(item("maintainability", f"Review dependencies in {by_id[node_id].path}",
                "This file has many local import references. Inspect responsibility boundaries "
                "before splitting it; import count alone does not establish poor design.",
                [by_id[node_id]], basis="inferred", confidence=65,
                metrics={"outgoing_imports": degree}, priority="low", effort="medium",
                approach=["Group imports by responsibility and assess whether a cohesive module can be extracted."],
                verification=["Confirm the proposed boundary reduces coupling without hiding dependencies."]))

    counts = atlas.counts
    summary = (f"Indexed {counts.get('files', 0)} files across {len(projects)} detected projects, "
               f"with {counts.get('symbols', 0)} declarations, {counts.get('routes', 0)} literal route "
               f"candidates, and {counts.get('tests', 0)} candidate test files. "
               f"Linked {len(local_edges)} local import references by source path. "
               "Reports are generated from static evidence; repository code was not executed.")
    return AtlasReport(summary=summary,
        architecture=section(architecture, "Directory and manifest structure do not prove a named architecture pattern.",
                             "Common folder names are orientation hints; dependency direction and runtime boundaries are not verified."),
        flows=section(flows, "These are partial static paths, not observed runtime request traces.",
                      "Route traversals are limited to four levels and sixteen links per candidate."),
        guide=section(guide, "Locations are starting points, not verified setup commands or change instructions."),
        recommendations=section(recommendations, "Rules cover long declarations, high local import counts, "
            "local import cycles, dynamic-code APIs and raw HTML syntax only. Absence of findings is not a clean security audit.",
            "No performance profiling, vulnerability database lookup, or data-flow analysis is performed."))
