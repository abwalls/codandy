"""SQL DDL declarations read as tokens. Nothing is executed and no database is contacted.

String literal contents are never kept, so values in INSERT statements, defaults or comments
cannot reach the structure document.
"""

import re
from dataclasses import dataclass, field

from app.structure.common import MAX_NAME, RawEntity, RawField, RawLink, clip, line_range

WORD = re.compile(r"[^\W\d][\w$]*")
NUMBER = re.compile(r"\d+(?:\.\d+)?")
DOLLAR_QUOTE = re.compile(r"\$(?:[A-Za-z_]\w*)?\$")
MAX_TOKENS = 2_000_000
MAX_STATEMENTS = 100_000
# Words that end a column's type and start its constraints.
COLUMN_CONSTRAINTS = {
    "NOT", "NULL", "PRIMARY", "UNIQUE", "REFERENCES", "DEFAULT", "CONSTRAINT", "CHECK",
    "GENERATED", "AUTO_INCREMENT", "AUTOINCREMENT", "IDENTITY", "COLLATE", "COMMENT", "ON",
    "AS", "ENCODE",
}
TYPE_WORDS = {
    "INT", "INTEGER", "BIGINT", "SMALLINT", "TINYINT", "VARCHAR", "CHAR", "TEXT", "UUID",
    "BOOLEAN", "BOOL", "DATE", "DATETIME", "TIMESTAMP", "NUMERIC", "DECIMAL", "FLOAT", "REAL",
    "DOUBLE", "JSON", "JSONB", "BLOB", "BYTEA", "SERIAL", "BIGSERIAL", "NVARCHAR",
}


@dataclass(slots=True)
class Token:
    kind: str
    value: str
    line: int


def tokenize(text: str) -> tuple[list[Token], bool]:
    """Tokens with line numbers; comments dropped and string contents withheld."""
    tokens: list[Token] = []
    index, line, length = 0, 1, len(text)
    while index < length:
        if len(tokens) >= MAX_TOKENS:
            return tokens, True
        char = text[index]
        if char == "\n":
            line += 1
            index += 1
            continue
        if char.isspace():
            index += 1
            continue
        stop = None
        if text.startswith("--", index):
            end = text.find("\n", index)
            index = length if end < 0 else end
            continue
        if text.startswith("/*", index):
            end = text.find("*/", index + 2)
            stop = length if end < 0 else end + 2
        elif char == "'":
            position = index + 1
            while True:
                end = text.find("'", position)
                if end < 0:
                    stop = length
                    break
                if text.startswith("''", end):
                    position = end + 2
                    continue
                stop = end + 1
                break
            tokens.append(Token("string", "", line))
        elif char in "\"`":
            end = text.find(char, index + 1)
            stop = length if end < 0 else end + 1
            tokens.append(Token("quoted", text[index + 1:stop - (end >= 0)][:MAX_NAME], line))
        elif char == "[":
            end = text.find("]", index + 1)
            inner = text[index + 1:end] if end > index else ""
            if inner.strip() and "\n" not in inner and not inner.strip().isdigit() and len(inner) <= MAX_NAME:
                tokens.append(Token("quoted", inner, line))
                index = end + 1
            else:
                tokens.append(Token("punct", "[", line))
                index += 1
            continue
        elif char == "$" and (match := DOLLAR_QUOTE.match(text, index)):
            end = text.find(match.group(0), match.end())
            stop = length if end < 0 else end + len(match.group(0))
            tokens.append(Token("string", "", line))
        if stop is not None:
            line += text.count("\n", index, stop)
            index = stop
            continue
        match = WORD.match(text, index) or NUMBER.match(text, index)
        if match:
            kind = "word" if match.re is WORD else "number"
            tokens.append(Token(kind, match.group(0)[:MAX_NAME], line))
            index = match.end()
            continue
        tokens.append(Token("punct" if char in "(),;.]" else "other", char, line))
        index += 1
    return tokens, False


def split_statements(tokens: list[Token]) -> list[list[Token]]:
    statements, current = [], []
    for position, token in enumerate(tokens):
        if token.kind == "punct" and token.value == ";":
            if current:
                statements.append(current)
            current = []
            continue
        # SQL Server batches end with GO alone on its own line.
        if (token.kind == "word" and token.value.upper() == "GO"
                and (position == 0 or tokens[position - 1].line < token.line)
                and (position + 1 == len(tokens) or tokens[position + 1].line > token.line)):
            if current:
                statements.append(current)
            current = []
            continue
        current.append(token)
    if current:
        statements.append(current)
    return statements


class Cursor:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.index = 0

    def peek(self, offset: int = 0) -> Token | None:
        position = self.index + offset
        return self.tokens[position] if position < len(self.tokens) else None

    def is_word(self, *values: str, offset: int = 0) -> bool:
        token = self.peek(offset)
        return token is not None and token.kind == "word" and token.value.upper() in values

    def is_punct(self, value: str, offset: int = 0) -> bool:
        token = self.peek(offset)
        return token is not None and token.kind == "punct" and token.value == value

    def accept(self, *words: str) -> bool:
        if all(self.is_word(word, offset=offset) for offset, word in enumerate(words)):
            self.index += len(words)
            return True
        return False

    def take(self) -> Token | None:
        token = self.peek()
        if token is not None:
            self.index += 1
        return token

    def identifier(self) -> Token | None:
        token = self.peek()
        if token is not None and token.kind in {"word", "quoted"}:
            self.index += 1
            return token
        return None

    def qualified(self) -> list[str]:
        first = self.identifier()
        if first is None:
            return []
        parts = [first.value]
        while self.is_punct(".") and self.peek(1) is not None and self.peek(1).kind in {"word", "quoted"}:
            self.index += 1
            parts.append(self.take().value)
        return parts[-3:]

    def group(self) -> list[Token] | None:
        """Tokens inside the parentheses at the cursor, consuming the closing parenthesis."""
        if not self.is_punct("("):
            return None
        depth, start = 0, self.index + 1
        for position in range(self.index, len(self.tokens)):
            token = self.tokens[position]
            if token.kind == "punct" and token.value == "(":
                depth += 1
            elif token.kind == "punct" and token.value == ")":
                depth -= 1
                if depth == 0:
                    self.index = position + 1
                    return self.tokens[start:position]
        self.index = len(self.tokens)
        return None

    def rest(self) -> list[Token]:
        remaining = self.tokens[self.index:]
        self.index = len(self.tokens)
        return remaining


def split_commas(tokens: list[Token]) -> list[list[Token]]:
    parts, current, depth = [], [], 0
    for token in tokens:
        if token.kind == "punct" and token.value == "(":
            depth += 1
        elif token.kind == "punct" and token.value == ")":
            depth -= 1
        if depth == 0 and token.kind == "punct" and token.value == ",":
            parts.append(current)
            current = []
        else:
            current.append(token)
    if current:
        parts.append(current)
    return parts


def column_names(tokens: list[Token] | None) -> list[str]:
    names = []
    for part in split_commas(tokens or []):
        first = next((token for token in part if token.kind in {"word", "quoted"}), None)
        if first is not None:
            names.append(first.value)
    return names


def type_text(tokens: list[Token]) -> str:
    text = ""
    for token in tokens:
        if token.kind == "punct" and token.value in "([].,)":
            text = text.rstrip() + token.value + (" " if token.value == "," else "")
        elif token.kind in {"word", "number", "quoted"}:
            text += ("" if not text or text.endswith(("(", "[", ".", " ")) else " ") + token.value
    return clip(text, 60)


def key_of(parts: list[str]) -> str:
    return "table:" + ".".join(part.lower() for part in parts[-2:])


@dataclass(eq=False)
class ForeignKey:
    source: RawEntity
    columns: list[str]
    target: list[str]
    target_columns: list[str]
    path: str
    line: int
    constraint: str | None = None


@dataclass
class SqlSchema:
    """Declarations of one project directory, applied statement by statement in path order."""

    tables: dict[str, RawEntity] = field(default_factory=dict)
    foreign_keys: list[ForeignKey] = field(default_factory=list)
    statements: int = 0
    skipped: int = 0
    truncated: bool = False

    def apply(self, path: str, text: str) -> None:
        tokens, truncated = tokenize(text)
        self.truncated |= truncated
        for statement in split_statements(tokens):
            if self.statements >= MAX_STATEMENTS:
                self.truncated = True
                return
            self.statements += 1
            cursor = Cursor(statement)
            try:
                if cursor.accept("CREATE"):
                    self.create(cursor, path, statement)
                elif cursor.accept("ALTER", "TABLE"):
                    self.alter(cursor, path, statement)
                elif cursor.accept("DROP", "TABLE"):
                    self.drop(cursor)
            except (IndexError, AttributeError):
                self.skipped += 1

    def lookup(self, parts: list[str]) -> RawEntity | None:
        key = key_of(parts)
        if key in self.tables:
            return self.tables[key]
        if len(parts) == 1:
            matches = [entity for entity in self.tables.values()
                       if entity.table and entity.table.lower() == parts[0].lower()]
            return matches[0] if len(matches) == 1 else None
        return None

    def create(self, cursor: Cursor, path: str, statement: list[Token]) -> None:
        cursor.accept("OR", "REPLACE") or cursor.accept("OR", "ALTER")
        for modifier in ("GLOBAL", "LOCAL", "TEMP", "TEMPORARY", "UNLOGGED"):
            cursor.accept(modifier)
        view = cursor.accept("VIEW") or cursor.accept("MATERIALIZED", "VIEW")
        if not view and not cursor.accept("TABLE"):
            return
        exists = cursor.accept("IF", "NOT", "EXISTS")
        parts = cursor.qualified()
        if not parts:
            self.skipped += 1
            return
        key = key_of(parts)
        if exists and key in self.tables:
            return
        lines = line_range(statement[0].line, statement[-1].line)
        entity = RawEntity(
            name=parts[-1], kind="view" if view else "table", path=path, lines=lines,
            reason="SQL CREATE VIEW statement" if view else "SQL CREATE TABLE statement",
            table=parts[-1], namespace=parts[-2] if len(parts) > 1 else None,
            keys=tuple(dict.fromkeys((key, key_of(parts[-1:])))))
        if not view:
            body = cursor.group()
            if body is None:
                # CREATE TABLE ... AS SELECT, LIKE and PARTITION OF declare no readable columns.
                self.skipped += 1
                return
            for element in split_commas(body):
                self.element(entity, Cursor(element), path)
        self.remove(key)
        self.tables[key] = entity

    def element(self, entity: RawEntity, cursor: Cursor, path: str) -> None:
        constraint = None
        if cursor.accept("CONSTRAINT"):
            name = cursor.identifier()
            constraint = name.value if name else None
        if cursor.accept("PRIMARY", "KEY"):
            self.mark(entity, column_names(cursor.group()), primary=True)
        elif cursor.accept("UNIQUE"):
            cursor.accept("KEY") or cursor.accept("INDEX")
            if not cursor.is_punct("("):
                cursor.identifier()
            columns = column_names(cursor.group())
            if len(columns) == 1:
                self.mark(entity, columns, unique=True)
        elif cursor.accept("FOREIGN", "KEY"):
            if not cursor.is_punct("("):
                cursor.identifier()
            columns = column_names(cursor.group())
            if cursor.accept("REFERENCES"):
                self.reference(entity, columns, cursor, path, constraint)
        elif cursor.is_word("CHECK", "EXCLUDE", "LIKE", "PERIOD"):
            return
        elif cursor.is_word("KEY", "INDEX") and (
                cursor.is_punct("(", offset=1)
                or (cursor.peek(1) is not None and cursor.is_punct("(", offset=2)
                    and cursor.peek(1).value.upper() not in TYPE_WORDS)):
            return  # MySQL inline index
        elif constraint is None:
            self.column(entity, cursor, path)

    def column(self, entity: RawEntity, cursor: Cursor, path: str) -> None:
        name = cursor.identifier()
        if name is None:
            return
        type_tokens: list[Token] = []
        while (token := cursor.peek()) is not None and not (
                token.kind == "word" and token.value.upper() in COLUMN_CONSTRAINTS):
            if cursor.is_punct("("):
                inner = cursor.group() or []
                type_tokens.extend([Token("punct", "(", token.line), *inner,
                                    Token("punct", ")", token.line)])
            else:
                type_tokens.append(cursor.take())
        column = RawField(name=name.value, type=type_text(type_tokens), line=name.line)
        while cursor.peek() is not None:
            if cursor.accept("NOT", "NULL"):
                column.nullable = False
            elif cursor.accept("NULL"):
                column.nullable = True if column.nullable is None else column.nullable
            elif cursor.accept("PRIMARY", "KEY"):
                column.primary, column.nullable = True, False
            elif cursor.accept("UNIQUE"):
                column.unique = True
            elif cursor.accept("REFERENCES"):
                self.reference(entity, [column.name], cursor, path, None)
            elif cursor.accept("CONSTRAINT"):
                cursor.identifier()
            elif cursor.is_punct("("):
                cursor.group()
            else:
                cursor.take()
        entity.fields = [item for item in entity.fields if item.name.lower() != column.name.lower()]
        entity.fields.append(column)

    def reference(self, entity: RawEntity, columns: list[str], cursor: Cursor, path: str,
                  constraint: str | None) -> None:
        start = cursor.peek()
        parts = cursor.qualified()
        if not parts or not columns or start is None:
            return
        targets = column_names(cursor.group()) if cursor.is_punct("(") else []
        self.foreign_keys.append(ForeignKey(entity, columns, parts, targets, path, start.line,
                                            constraint.lower() if constraint else None))

    def mark(self, entity: RawEntity, columns: list[str], *, primary=False, unique=False) -> None:
        for name in columns:
            column = entity.field_named(name, fold=True)
            if column is None:
                continue
            if primary:
                column.primary, column.nullable = True, False
            if unique:
                column.unique = True

    def alter(self, cursor: Cursor, path: str, statement: list[Token]) -> None:
        cursor.accept("IF", "EXISTS")
        cursor.accept("ONLY")
        entity = self.lookup(cursor.qualified())
        if entity is None:
            self.skipped += 1
            return
        changed = False
        for action in split_commas(cursor.rest()):
            part = Cursor(action)
            if part.accept("ADD"):
                changed = True
                if part.is_word("CONSTRAINT", "PRIMARY", "UNIQUE", "FOREIGN", "CHECK"):
                    self.element(entity, part, path)
                else:
                    part.accept("COLUMN")
                    part.accept("IF", "NOT", "EXISTS")
                    self.column(entity, part, path)
            elif part.accept("DROP"):
                changed = True
                if part.accept("CONSTRAINT"):
                    part.accept("IF", "EXISTS")
                    name = part.identifier()
                    if name:
                        self.foreign_keys = [key for key in self.foreign_keys
                                             if not (key.source is entity
                                                     and key.constraint == name.value.lower())]
                else:
                    part.accept("COLUMN")
                    part.accept("IF", "EXISTS")
                    name = part.identifier()
                    if name:
                        dropped = name.value.lower()
                        entity.fields = [item for item in entity.fields
                                         if item.name.lower() != dropped]
                        self.foreign_keys = [key for key in self.foreign_keys if not (
                            key.source is entity
                            and dropped in {column.lower() for column in key.columns})]
        if changed and len(entity.more_evidence) < 7:
            entity.more_evidence.append((path, line_range(statement[0].line, statement[-1].line),
                                         "SQL ALTER TABLE statement"))

    def drop(self, cursor: Cursor) -> None:
        cursor.accept("IF", "EXISTS")
        for part in split_commas(cursor.rest()):
            parts = Cursor(part).qualified()
            entity = self.lookup(parts) if parts else None
            if entity is not None:
                self.remove(next(key for key, value in self.tables.items() if value is entity))

    def remove(self, key: str) -> None:
        entity = self.tables.pop(key, None)
        if entity is not None:
            self.foreign_keys = [item for item in self.foreign_keys if item.source is not entity]

    def declarations(self) -> tuple[list[RawEntity], list[RawLink]]:
        entities = list(self.tables.values())
        for entity in entities:
            for column in entity.fields:
                # SQL columns are nullable unless declared NOT NULL or part of a primary key.
                if column.nullable is None:
                    column.nullable = not column.primary
        links = []
        for key in self.foreign_keys:
            columns = [key.source.field_named(name, fold=True) for name in key.columns]
            for column in columns:
                if column is not None:
                    column.foreign = True
            primary = {item.name.lower() for item in key.source.fields if item.primary}
            names = {name.lower() for name in key.columns}
            one = (names == primary and bool(primary)) or (
                len(columns) == 1 and columns[0] is not None and columns[0].unique)
            nullable = [column.nullable for column in columns if column is not None]
            links.append(RawLink(
                source=key.source, source_fields=key.columns, target_key=key_of(key.target),
                target_name=".".join(key.target), target_fields=key.target_columns,
                source_cardinality="one" if one else "many", target_cardinality="one",
                source_optional=True,
                target_optional=any(nullable) if nullable else None,
                label=key.constraint or ", ".join(key.columns), basis="declared", path=key.path,
                lines=line_range(key.line), reason="SQL foreign key constraint"))
        return entities, links
