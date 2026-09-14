export type AtlasNodeKind =
  | "client"
  | "route"
  | "handler"
  | "service"
  | "repository"
  | "database";

export type AtlasNode = {
  id: string;
  kind: AtlasNodeKind;
  label: string;
  detail: string;
  path: string;
  lines?: string;
  confidence: number;
  calls: string[];
  calledBy: string[];
};

export type AtlasRelationship = {
  source: string;
  target: string;
  type: "CALLS" | "ROUTES_TO" | "READS" | "WRITES";
};

export type CodeAtlas = {
  schemaVersion: "0.1";
  repository: {
    name: string;
    branch: string;
    commit: string;
    analyzedAt: string;
  };
  summary: {
    description: string;
    architecture: string;
    confidence: number;
    technologies: string[];
  };
  counts: {
    files: number;
    symbols: number;
    routes: number;
    relationships: number;
    tests: number;
  };
  nodes: AtlasNode[];
  relationships: AtlasRelationship[];
};

export const demoAtlas: CodeAtlas = {
  schemaVersion: "0.1",
  repository: {
    name: "northstar/banking-platform",
    branch: "main",
    commit: "b7ac129",
    analyzedAt: "Sep 12, 2026",
  },
  summary: {
    description:
      "A React banking portal backed by an ASP.NET Core API, PostgreSQL, and event-driven notification services.",
    architecture: "Vertical Slice Architecture + CQRS",
    confidence: 92,
    technologies: ["React 19", "ASP.NET Core", "MediatR", "EF Core", "PostgreSQL"],
  },
  counts: {
    files: 284,
    symbols: 1942,
    routes: 47,
    relationships: 183,
    tests: 312,
  },
  nodes: [
    {
      id: "component:react:LoginForm",
      kind: "client",
      label: "LoginForm",
      detail: "Collects credentials and submits the authentication request.",
      path: "client/src/features/auth/LoginForm.tsx",
      lines: "18–92",
      confidence: 99,
      calls: ["route:http:POST:/api/auth/login"],
      calledBy: [],
    },
    {
      id: "route:http:POST:/api/auth/login",
      kind: "route",
      label: "POST /api/auth/login",
      detail: "Public authentication endpoint that maps the request to LoginCommand.",
      path: "src/Api/Auth/AuthController.cs",
      lines: "24–41",
      confidence: 100,
      calls: ["method:csharp:LoginHandler.Handle"],
      calledBy: ["component:react:LoginForm"],
    },
    {
      id: "method:csharp:LoginHandler.Handle",
      kind: "handler",
      label: "LoginHandler.Handle",
      detail: "Coordinates user lookup, password validation, and token issuance.",
      path: "src/Application/Auth/Login/LoginHandler.cs",
      lines: "22–71",
      confidence: 97,
      calls: ["method:csharp:UserRepository.GetByEmail", "method:csharp:JwtTokenService.Generate"],
      calledBy: ["route:http:POST:/api/auth/login"],
    },
    {
      id: "method:csharp:UserRepository.GetByEmail",
      kind: "repository",
      label: "UserRepository.GetByEmail",
      detail: "Loads the active user and authentication fields from PostgreSQL.",
      path: "src/Infrastructure/Users/UserRepository.cs",
      lines: "35–58",
      confidence: 95,
      calls: ["database:postgres:Users"],
      calledBy: ["method:csharp:LoginHandler.Handle"],
    },
    {
      id: "method:csharp:JwtTokenService.Generate",
      kind: "service",
      label: "JwtTokenService.Generate",
      detail: "Builds signed access and refresh tokens from user claims.",
      path: "src/Infrastructure/Auth/JwtTokenService.cs",
      lines: "19–64",
      confidence: 96,
      calls: [],
      calledBy: ["method:csharp:LoginHandler.Handle"],
    },
    {
      id: "database:postgres:Users",
      kind: "database",
      label: "PostgreSQL · Users",
      detail: "Primary identity table configured through BankingDbContext.",
      path: "src/Infrastructure/Persistence/BankingDbContext.cs",
      lines: "14–46",
      confidence: 93,
      calls: [],
      calledBy: ["method:csharp:UserRepository.GetByEmail"],
    },
  ],
  relationships: [
    { source: "component:react:LoginForm", target: "route:http:POST:/api/auth/login", type: "ROUTES_TO" },
    { source: "route:http:POST:/api/auth/login", target: "method:csharp:LoginHandler.Handle", type: "CALLS" },
    { source: "method:csharp:LoginHandler.Handle", target: "method:csharp:UserRepository.GetByEmail", type: "CALLS" },
    { source: "method:csharp:LoginHandler.Handle", target: "method:csharp:JwtTokenService.Generate", type: "CALLS" },
    { source: "method:csharp:UserRepository.GetByEmail", target: "database:postgres:Users", type: "READS" },
  ],
};
