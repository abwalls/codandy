import json
import time

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.analyzer import analyze_repository
from app.settings import Settings
from app.structure import extract
from app.structure.extract import build_structure, extract_structure
from app.structure.models import (
    EXTRACTION_FAILED,
    StructureDocument,
    checked_structure,
    validate_against_atlas,
)
from app.structure.prisma import strip_comment

PRISMA = """// Orders domain
datasource db {
  provider = "postgresql"
  url      = "postgresql://admin:hunter2@db.internal:5432/shop"
}

generator client {
  provider = "prisma-client-js"
}

model User {
  id      Int     @id @default(autoincrement())
  email   String  @unique
  name    String? // comment with "quotes"
  website String  @default("https://example.com/a//b")
  orders  Order[]
  @@map("users")
}

model Product {
  id    Int         @id @default(autoincrement())
  name  String
  price Decimal     @db.Decimal(10, 2)
  items OrderItem[]
  tags  Tag[]
  @@map("products")
}

model Order {
  id         Int         @id @default(autoincrement())
  user_id    Int
  user       User        @relation(fields: [user_id], references: [id])
  created_at DateTime    @default(now())
  items      OrderItem[]
  coupon     Coupon?     @relation(fields: [coupon_id], references: [id])
  coupon_id  Int?
  @@map("orders")
}

model OrderItem {
  order_id   Int
  product_id Int
  quantity   Int
  order      Order   @relation(fields: [order_id], references: [id])
  product    Product @relation(fields: [product_id], references: [id])
  @@id([order_id, product_id])
  @@map("order_items")
}

model Tag {
  id       Int       @id
  products Product[]
  @@map("tags")
}
"""

SQL_INIT = """-- 001: users and products
CREATE TABLE IF NOT EXISTS "users" (
  id SERIAL PRIMARY KEY,
  email VARCHAR(255) NOT NULL UNIQUE,
  name TEXT
);
/* CREATE TABLE ignored_in_comment (id int); */
CREATE TABLE products (
  id serial PRIMARY KEY,
  name text NOT NULL,
  price numeric(10, 2) DEFAULT 0
);
INSERT INTO users (email) VALUES ('CREATE TABLE fake (id int); hunter2');
CREATE FUNCTION touch() RETURNS trigger AS $$ BEGIN CREATE TABLE nope (id int); END; $$
LANGUAGE plpgsql;
"""

SQL_ORDERS = """CREATE TABLE public.orders (
  id bigserial PRIMARY KEY,
  user_id integer NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  created_at timestamp with time zone DEFAULT now()
);
CREATE TABLE order_items (
  order_id bigint NOT NULL,
  product_id integer NOT NULL,
  quantity integer NOT NULL,
  PRIMARY KEY (order_id, product_id),
  CONSTRAINT order_items_order_fk FOREIGN KEY (order_id) REFERENCES public.orders (id)
);
ALTER TABLE ONLY order_items
  ADD CONSTRAINT order_items_product_fk FOREIGN KEY (product_id) REFERENCES products(id);
CREATE TABLE tags (id int PRIMARY KEY);
CREATE TABLE product_tags (product_id int REFERENCES products, tag_id int REFERENCES tags);
CREATE TABLE audit (id int, actor_id int REFERENCES accounts(id));
DROP TABLE IF EXISTS audit;
CREATE TABLE reviews (id int PRIMARY KEY, author_id int REFERENCES accounts(id));
CREATE VIEW order_totals AS SELECT 1;
"""

SQLALCHEMY = '''from typing import Optional

from sqlalchemy import Column, ForeignKey, Integer, Numeric, String, Table
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


product_tags = Table("product_tags", Base.metadata)


class TimestampMixin:
    created_at = Column(String(32))


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    name: Mapped[Optional[str]]
    orders: Mapped[list["Order"]] = relationship(back_populates="user")


class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    price = Column(Numeric(10, 2))
    tags = relationship("Tag", secondary=product_tags)


class Order(TimestampMixin, Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    user: Mapped["User"] = relationship(back_populates="orders")


class OrderItem(Base):
    __tablename__ = "order_items"
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), primary_key=True)
    product_id = Column(Integer, ForeignKey(Product.id), primary_key=True)
    quantity: Mapped[int]


class Tag(Base):
    __tablename__ = "tags"
    id: Mapped[int] = mapped_column(primary_key=True)
'''

DJANGO = '''from django.conf import settings
from django.db import models


class Timestamped(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


class User(models.Model):
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=100, null=True)

    class Meta:
        db_table = "users"


class Product(models.Model):
    name = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    tags = models.ManyToManyField("Tag")

    class Meta:
        db_table = "products"


class Order(Timestamped):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)

    class Meta:
        db_table = "orders"


class OrderItem(models.Model):
    order = models.ForeignKey("shop.Order", on_delete=models.CASCADE)
    product = models.ForeignKey("Product", on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()

    class Meta:
        db_table = "order_items"


class Tag(models.Model):
    label = models.SlugField(unique=True)
    parent = models.ForeignKey("self", null=True, on_delete=models.CASCADE)

    class Meta:
        db_table = "tags"
'''

SCHEMAS = '''from dataclasses import dataclass
from typing import ClassVar, TypedDict

from pydantic import BaseModel


class ApiModel(BaseModel):
    model_config = {"frozen": True}


class Money(ApiModel):
    amount: str
    currency: str = "USD"


class LineItem(ApiModel):
    sku: str
    price: Money
    _cache: dict = {}


class OrderView(ApiModel):
    id: int
    items: list[LineItem]
    total: "Money"
    kind: ClassVar[str] = "order"
    note: str | None = None


@dataclass
class Page:
    items: list[OrderView]
    cursor: str | None


class Filters(TypedDict):
    status: str
'''

VIEWS = '''from pydantic import BaseModel

from .schemas import Money


class Refund(BaseModel):
    amount: Money
'''

LEGACY = '''from pydantic import BaseModel


class Money(BaseModel):
    cents: int


class Invoice(BaseModel):
    total: Money
'''

TYPES = '''export interface Entity { id: string }
export interface Customer extends Entity {
  name: string;
  orders?: OrderSummary[];
  "display-name": string;
  greet(): void;
}
export type OrderSummary = { id: string; total: number; customer: Customer | null };
type Alias = string;
'''

PROPS = '''interface Props { customer: Customer }
export function Card(props: Props) { return null; }
'''

CORE = {"users", "products", "orders", "order_items"}
CORE_LINKS = {("orders", "users", "many", "one"), ("order_items", "orders", "many", "one"),
              ("order_items", "products", "many", "one")}


def write(root, files):
    for path, text in files.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")


def analyze(root, **settings):
    limits = Settings(**settings)
    atlas = analyze_repository(root, "https://github.com/org/repo.git", None, limits,
                               lambda *_: None)
    return atlas, extract_structure(root, atlas, limits)


@pytest.fixture
def shop(tmp_path):
    write(tmp_path, {
        "web/package.json": "{}", "web/prisma/schema.prisma": PRISMA,
        "db/migrations/001_init.sql": SQL_INIT, "db/migrations/002_orders.sql": SQL_ORDERS,
        "sa/requirements.txt": "sqlalchemy\n", "sa/models.py": SQLALCHEMY,
        "dj/requirements.txt": "django\n", "dj/shop/models.py": DJANGO,
        "api/schemas.py": SCHEMAS, "api/views.py": VIEWS, "api/legacy.py": LEGACY,
        "web/src/types.ts": TYPES, "web/src/card.tsx": PROPS,
    })
    return analyze(tmp_path)


def source_view(structure, kind):
    source = next(item for item in structure.sources if item.kind == kind)
    entities = {entity.id: entity for entity in structure.entities if entity.source_id == source.id}
    links = [link for link in structure.entity_links if link.source_id == source.id]
    return source, entities, links


def core_links(entities, links):
    table = {key: entity.table for key, entity in entities.items()}
    return {(table[link.source.entity], table[link.target.entity], link.source.cardinality,
             link.target.cardinality)
            for link in links if link.basis == "declared" and link.target.entity
            and table[link.source.entity] in CORE and table[link.target.entity] in CORE}


def test_orders_domain_is_equivalent_across_frameworks(shop):
    atlas, structure = shop
    validate_against_atlas(structure, atlas)
    assert {source.kind: source.root for source in structure.sources} == {
        "prisma": "web", "sql": "", "sqlalchemy": "sa", "django": "dj"}
    for kind in ("prisma", "sql", "sqlalchemy", "django"):
        _, entities, links = source_view(structure, kind)
        assert CORE <= {entity.table for entity in entities.values()}, kind
        assert core_links(entities, links) == CORE_LINKS, kind
    # Round-trips through JSON, which is what the API serves and the snapshot stores.
    assert StructureDocument.model_validate_json(structure.model_dump_json()) == structure


def test_prisma_declarations_keep_keys_and_never_read_datasources(shop):
    _, structure = shop
    serialized = structure.model_dump_json()
    assert "hunter2" not in serialized and "db.internal" not in serialized
    _, entities, links = source_view(structure, "prisma")
    by_name = {entity.name: entity for entity in entities.values()}
    user = {field.name: field for field in by_name["User"].fields}
    assert set(user) == {"id", "email", "name", "website"}  # relation fields are not columns
    assert user["id"].primary and user["email"].unique and user["name"].nullable is True
    item = {field.name: field for field in by_name["OrderItem"].fields}
    assert item["order_id"].primary and item["product_id"].primary and item["order_id"].foreign
    many = [link for link in links if link.basis == "orm_relation"]
    assert [(by_name["Product"].id, "many", "many")] == [
        (link.source.entity, link.source.cardinality, link.target.cardinality) for link in many]
    coupon = next(link for link in links if link.label == "coupon")
    assert (coupon.resolution, coupon.target.entity, coupon.target.name) == (
        "unresolved", None, "Coupon")
    assert coupon.target.optional is True
    assert by_name["User"].evidence[0].lines == "11-18"
    assert strip_comment('url "https://a//b" // note') == 'url "https://a//b" '


def test_sql_declarations_follow_statements_in_path_order(shop):
    _, structure = shop
    assert "hunter2" not in structure.model_dump_json()
    _, entities, links = source_view(structure, "sql")
    by_table = {entity.table: entity for entity in entities.values()}
    assert set(by_table) == {"users", "products", "orders", "order_items", "tags", "product_tags",
                             "reviews", "order_totals"}
    assert by_table["order_totals"].kind == "view"
    assert by_table["orders"].namespace == "public"
    users = {field.name: field for field in by_table["users"].fields}
    assert users["email"].type == "VARCHAR(255)" and users["email"].unique
    assert users["email"].nullable is False and users["name"].nullable is True
    orders = {field.name: field for field in by_table["orders"].fields}
    assert orders["created_at"].type == "timestamp with time zone"
    assert orders["user_id"].foreign
    item = next(link for link in links if link.label == "order_items_product_fk")
    assert item.target.entity == by_table["products"].id
    assert [evidence.reason for evidence in by_table["order_items"].evidence] == [
        "SQL CREATE TABLE statement", "SQL ALTER TABLE statement"]
    missing = next(link for link in links if link.source.entity == by_table["reviews"].id)
    assert (missing.resolution, missing.target.name) == ("unresolved", "accounts")
    join = [link for link in links if link.source.entity == by_table["product_tags"].id]
    assert {link.target.entity for link in join} == {by_table["products"].id, by_table["tags"].id}


def test_sqlalchemy_models_use_mapped_annotations_and_mixins(shop):
    _, structure = shop
    _, entities, links = source_view(structure, "sqlalchemy")
    by_name = {entity.name: entity for entity in entities.values()}
    assert set(by_name) == {"User", "Product", "Order", "OrderItem", "Tag"}
    user = {field.name: field for field in by_name["User"].fields}
    assert user["name"].nullable is True and user["email"].nullable is False
    assert user["email"].type == "String" and user["email"].unique
    # Mixin columns keep their line because the mixin is declared in the same file.
    mixin = next(field for field in by_name["Order"].fields if field.name == "created_at")
    assert mixin.line == SQLALCHEMY.splitlines().index("    created_at = Column(String(32))") + 1
    relations = [(by_name_of(entities, link.source.entity), by_name_of(entities, link.target.entity),
                  link.basis) for link in links if link.basis == "orm_relation"]
    # relationship() views of declared foreign keys are not drawn twice.
    assert relations == [("Product", "Tag", "orm_relation")]
    product = next(link for link in links if link.source.fields == ["product_id"])
    assert product.target.entity == by_name["Product"].id


def by_name_of(entities, identity):
    return entities[identity].name if identity else None


def test_django_models_apply_documented_defaults(shop):
    _, structure = shop
    _, entities, links = source_view(structure, "django")
    by_name = {entity.name: entity for entity in entities.values()}
    assert "Timestamped" not in by_name
    user = by_name["User"]
    assert user.table == "users"
    assert (user.fields[0].name, user.fields[0].type, user.fields[0].primary) == (
        "id", "AutoField (implicit)", True)
    fields = {field.name: field for field in by_name["Order"].fields}
    assert fields["created_at"].line == 6 and fields["user"].foreign
    assert fields["reviewer"].nullable is True
    reviewer = next(link for link in links if link.label == "reviewer")
    assert (reviewer.resolution, reviewer.target.name) == ("unresolved", "settings.AUTH_USER_MODEL")
    parent = next(link for link in links if link.label == "parent")
    assert parent.target.entity == by_name["Tag"].id and parent.target.optional is True
    tags = next(link for link in links if link.label == "tags")
    assert (tags.basis, tags.source.cardinality, tags.target.cardinality) == (
        "orm_relation", "many", "many")


def test_data_contracts_resolve_by_file_import_then_unique_name(shop):
    atlas, structure = shop
    types = {(item.path, item.name): item for item in structure.types}
    assert {item.kind for item in types.values()} == {
        "pydantic", "dataclass", "typed_dict", "interface", "type_alias"}
    view = types[("api/schemas.py", "OrderView")]
    assert [member.name for member in view.members] == ["id", "items", "total", "note"]
    assert [member.name for member in types[("api/schemas.py", "LineItem")].members] == [
        "sku", "price"]
    assert types[("api/schemas.py", "Money")].kind == "pydantic"  # through ApiModel
    assert view.node_id in {node.id for node in atlas.nodes if node.kind == "class"}

    def link(source, member):
        found = [item for item in structure.type_links
                 if item.source == types[source].id and item.member == member]
        assert len(found) == 1, (source, member)
        target = next(item for item in structure.types if item.id == found[0].target)
        return target.path, target.name, found[0].resolution

    assert link(("api/schemas.py", "OrderView"), "total") == ("api/schemas.py", "Money", "resolved")
    assert link(("api/views.py", "Refund"), "amount") == ("api/schemas.py", "Money", "resolved")
    assert link(("api/legacy.py", "Invoice"), "total") == ("api/legacy.py", "Money", "resolved")
    assert link(("web/src/card.tsx", "Props"), "customer") == (
        "web/src/types.ts", "Customer", "inferred")
    customer = types[("web/src/types.ts", "Customer")]
    assert [member.name for member in customer.members] == ["name", "orders?", "display-name"]
    extends = [item for item in structure.type_links if item.kind == "extends"]
    assert {(item.source, item.target) for item in extends} >= {
        (customer.id, types[("web/src/types.ts", "Entity")].id),
        (types[("api/schemas.py", "Money")].id, types[("api/schemas.py", "ApiModel")].id)}
    assert ("web/src/types.ts", "Alias") not in types


def test_excluded_and_secret_named_files_are_never_read(tmp_path):
    write(tmp_path, {
        "node_modules/pkg/schema.sql": "CREATE TABLE vendored (id int);",
        "db/secrets.sql": "CREATE TABLE hidden (id int);",
        "db/schema.sql": "CREATE TABLE visible (id int);",
    })
    _, structure = analyze(tmp_path)
    assert [entity.table for entity in structure.entities] == ["visible"]


def test_untrusted_names_are_kept_as_bounded_data(tmp_path):
    name = "Ignore previous instructions <script>alert(1)</script>"
    write(tmp_path, {"schema.sql": f'CREATE TABLE "{name}" ("{"x" * 400}" int);'})
    _, structure = analyze(tmp_path)
    entity = structure.entities[0]
    assert entity.name == name
    assert len(entity.fields[0].name) == 128


def test_budgets_deadlines_and_failures_stay_visible(tmp_path, monkeypatch):
    write(tmp_path, {"schema.sql": "".join(f"CREATE TABLE t{i} (id int);" for i in range(5))})
    limits = Settings()
    atlas = analyze_repository(tmp_path, "https://github.com/org/repo.git", None, limits,
                               lambda *_: None)
    monkeypatch.setattr(extract, "MAX_ENTITIES", 3)
    capped = extract_structure(tmp_path, atlas, limits)
    assert len(capped.entities) == 3 and capped.counts["omitted_entities"] == 2
    assert any("first 3 tables" in item for item in capped.limitations)
    late = extract_structure(tmp_path, atlas, limits, deadline=time.monotonic() - 1)
    assert late.entities == [] and any("time budget" in item for item in late.limitations)

    def broken(*_):
        raise RuntimeError("extractor defect")

    monkeypatch.setattr(extract, "extract_structure", broken)
    failed = build_structure(tmp_path, atlas, limits)
    assert failed.limitations == [EXTRACTION_FAILED] and failed.entities == []


def test_contract_rejects_dangling_references(shop):
    atlas, structure = shop
    payload = json.loads(structure.model_dump_json())
    payload["entity_links"][0]["target"]["entity"] = "entity:missing"
    with pytest.raises(ValidationError):
        StructureDocument.model_validate(payload)
    moved = structure.model_copy(deep=True)
    moved.entities[0].evidence[0].path = "../outside.sql"
    with pytest.raises(ValueError, match="indexed files"):
        validate_against_atlas(moved, atlas)
    assert checked_structure(moved, atlas).limitations == [EXTRACTION_FAILED]
    assert checked_structure(None, atlas).limitations == [EXTRACTION_FAILED]


def test_structure_endpoint_persists_with_the_report(tmp_path, monkeypatch):
    from contextlib import contextmanager

    from app import jobs
    from app.main import app, settings
    from app.report_storage import ReportStorage

    repository = tmp_path / "repository"
    write(repository, {"schema.sql": SQL_INIT, ".git/HEAD": "ref: refs/heads/main\n",
                       ".git/refs/heads/main": "a" * 40})

    @contextmanager
    def clone(*_):
        yield repository

    monkeypatch.setattr(jobs, "clone_repository", clone)
    monkeypatch.setattr(settings, "report_root", str(tmp_path / "reports"))
    with TestClient(app) as client:
        created = client.post("/api/analyses", json={"source": {
            "url": "https://github.com/org/repo"}}).json()["id"]
        deadline = time.monotonic() + 30
        while client.get(f"/api/analyses/{created}").json()["status"] not in {"complete", "failed"}:
            assert time.monotonic() < deadline
            time.sleep(0.05)
        response = client.get(f"/api/analyses/{created}/structure")
        assert response.status_code == 200
        assert {entity["table"] for entity in response.json()["entities"]} == {"users", "products"}
        assert json.loads((repository / ".codandy" / "structure.json").read_text(
            encoding="utf-8")) == response.json()
        unknown = "00000000-0000-4000-8000-000000000000"
        assert client.get(f"/api/analyses/{unknown}/structure").status_code == 404
    with TestClient(app) as client:
        assert client.get(f"/api/analyses/{created}/structure").json() == response.json()
    # A report saved before diagrams existed restores without them.
    storage = ReportStorage(str(tmp_path / "reports"))
    snapshot = storage.load(10)[0]
    storage.save(snapshot.model_copy(update={"structure": None}))
    with TestClient(app) as client:
        missing = client.get(f"/api/analyses/{created}/structure")
        assert missing.status_code == 404
        assert "Run the analysis again" in missing.json()["detail"]
        assert client.get(f"/api/analyses/{created}/atlas").status_code == 200
