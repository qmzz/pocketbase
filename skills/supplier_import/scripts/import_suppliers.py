#!/usr/bin/env python3
"""Import supplier information into PocketBase via REST API.

Supports JSON and CSV input. Designed for the repository's default collections:
- suppliers
- supplier_contacts
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

SUPPLIER_FIELDS = [
    "supplier_name",
    "supplier_code",
    "supplier_type",
    "status",
    "phone",
    "remark",
]
CONTACT_FIELDS = [
    "contact_name",
    "position",
    "mobile",
    "email",
    "wechat",
    "is_primary",
]

TRUE_VALUES = {"1", "true", "yes", "y", "是", "主", "主要", "primary"}
FALSE_VALUES = {"0", "false", "no", "n", "否", "非", ""}


class PocketBaseError(RuntimeError):
    pass


class PocketBaseClient:
    def __init__(self, base_url: str, token: str = "", timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    def request(self, method: str, path: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = self.base_url + path
        body = None
        headers = {"Accept": "application/json"}
        if data is not None:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
                if not raw:
                    return {}
                return json.loads(raw)
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace")
            raise PocketBaseError(f"HTTP {e.code} {method} {path}: {raw}") from e
        except urllib.error.URLError as e:
            raise PocketBaseError(f"Network error {method} {path}: {e}") from e

    def admin_login(self, email: str, password: str) -> None:
        # PocketBase v0.23+ admin auth endpoint.
        try:
            resp = self.request("POST", "/api/collections/_superusers/auth-with-password", {
                "identity": email,
                "password": password,
            })
        except PocketBaseError:
            # Older versions.
            resp = self.request("POST", "/api/admins/auth-with-password", {
                "identity": email,
                "password": password,
            })
        token = resp.get("token")
        if not token:
            raise PocketBaseError("Admin login succeeded but no token returned")
        self.token = token

    def list_records(self, collection: str, filter_expr: str, per_page: int = 1) -> List[Dict[str, Any]]:
        params = urllib.parse.urlencode({
            "page": 1,
            "perPage": per_page,
            "filter": filter_expr,
        })
        resp = self.request("GET", f"/api/collections/{collection}/records?{params}")
        return resp.get("items", [])

    def create_record(self, collection: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.request("POST", f"/api/collections/{collection}/records", payload)

    def update_record(self, collection: str, record_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.request("PATCH", f"/api/collections/{collection}/records/{record_id}", payload)


def pb_escape(value: Any) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


def compact_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in data.items() if v is not None and v != ""}


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    normalized = str(value).strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    return False


def normalize_supplier(row: Dict[str, Any]) -> Dict[str, Any]:
    supplier = {field: str(row.get(field, "")).strip() for field in SUPPLIER_FIELDS}
    supplier.setdefault("status", "启用")
    if not supplier.get("status"):
        supplier["status"] = "启用"
    return compact_dict(supplier)


def normalize_contact(row: Dict[str, Any]) -> Dict[str, Any]:
    contact: Dict[str, Any] = {}
    for field in CONTACT_FIELDS:
        value = row.get(field, "")
        if field == "is_primary":
            contact[field] = parse_bool(value)
        else:
            contact[field] = str(value).strip() if value is not None else ""
    return compact_dict(contact)


def load_json(path: Path) -> List[Dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        if "items" in data and isinstance(data["items"], list):
            data = data["items"]
        else:
            data = [data]
    if not isinstance(data, list):
        raise ValueError("JSON input must be an object, array, or {items: [...]} structure")
    return data


def load_csv(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    grouped: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for row in rows:
        supplier = normalize_supplier(row)
        key = (supplier.get("supplier_code", ""), supplier.get("supplier_name", ""))
        if not key[0] and not key[1]:
            continue
        if key not in grouped:
            grouped[key] = {**supplier, "contacts": []}
        contact = normalize_contact(row)
        if contact.get("contact_name"):
            grouped[key]["contacts"].append(contact)
    return list(grouped.values())


def load_input(path: Path) -> List[Dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return load_json(path)
    if suffix == ".csv":
        return load_csv(path)
    raise ValueError(f"Unsupported input file type: {suffix}. Use .json or .csv")


def normalize_items(items: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized = []
    for idx, item in enumerate(items, start=1):
        supplier = normalize_supplier(item)
        contacts = item.get("contacts", []) or []
        if isinstance(contacts, dict):
            contacts = [contacts]
        supplier["contacts"] = [normalize_contact(c) for c in contacts if normalize_contact(c).get("contact_name")]
        supplier["_row"] = idx
        normalized.append(supplier)
    return normalized


def validate_items(items: List[Dict[str, Any]]) -> List[str]:
    errors = []
    seen_codes = set()
    for item in items:
        row = item.get("_row")
        name = item.get("supplier_name")
        code = item.get("supplier_code")
        if not name:
            errors.append(f"row {row}: supplier_name is required")
        if code:
            if code in seen_codes:
                errors.append(f"row {row}: duplicate supplier_code in input: {code}")
            seen_codes.add(code)
        for cidx, contact in enumerate(item.get("contacts", []), start=1):
            if not contact.get("contact_name"):
                errors.append(f"row {row} contact {cidx}: contact_name is required")
    return errors


def supplier_lookup_filter(item: Dict[str, Any]) -> str:
    code = item.get("supplier_code")
    if code:
        return f'supplier_code = "{pb_escape(code)}"'
    return f'supplier_name = "{pb_escape(item.get("supplier_name", ""))}"'


def contact_lookup_filter(supplier_id: str, contact: Dict[str, Any]) -> str:
    name = pb_escape(contact.get("contact_name", ""))
    mobile = contact.get("mobile")
    if mobile:
        return f'supplier = "{supplier_id}" && contact_name = "{name}" && mobile = "{pb_escape(mobile)}"'
    return f'supplier = "{supplier_id}" && contact_name = "{name}"'


def import_items(
    client: PocketBaseClient,
    items: List[Dict[str, Any]],
    suppliers_collection: str,
    contacts_collection: str,
    upsert: bool,
    dry_run: bool,
) -> Dict[str, int]:
    stats = {
        "suppliers_created": 0,
        "suppliers_updated": 0,
        "contacts_created": 0,
        "contacts_updated": 0,
        "suppliers_skipped": 0,
        "contacts_skipped": 0,
    }

    for item in items:
        supplier_payload = {k: v for k, v in item.items() if k in SUPPLIER_FIELDS}
        supplier_id = None
        existing_supplier = None

        if upsert:
            found = client.list_records(suppliers_collection, supplier_lookup_filter(item), per_page=1) if not dry_run else []
            if found:
                existing_supplier = found[0]
                supplier_id = existing_supplier["id"]

        if dry_run:
            action = "update" if existing_supplier else "create"
            print(f"[DRY-RUN] supplier {action}: {supplier_payload.get('supplier_name')} ({supplier_payload.get('supplier_code', '-')})")
        elif existing_supplier:
            client.update_record(suppliers_collection, supplier_id, supplier_payload)
            stats["suppliers_updated"] += 1
        else:
            created = client.create_record(suppliers_collection, supplier_payload)
            supplier_id = created["id"]
            stats["suppliers_created"] += 1

        if dry_run and not supplier_id:
            supplier_id = "DRY_RUN_SUPPLIER_ID"

        for contact in item.get("contacts", []):
            contact_payload = {k: v for k, v in contact.items() if k in CONTACT_FIELDS}
            contact_payload["supplier"] = supplier_id

            existing_contact = None
            if upsert and not dry_run and supplier_id != "DRY_RUN_SUPPLIER_ID":
                found = client.list_records(contacts_collection, contact_lookup_filter(supplier_id, contact), per_page=1)
                if found:
                    existing_contact = found[0]

            if dry_run:
                action = "update" if existing_contact else "create"
                print(f"[DRY-RUN] contact {action}: {contact_payload.get('contact_name')} -> {supplier_payload.get('supplier_name')}")
            elif existing_contact:
                client.update_record(contacts_collection, existing_contact["id"], contact_payload)
                stats["contacts_updated"] += 1
            else:
                client.create_record(contacts_collection, contact_payload)
                stats["contacts_created"] += 1

        if not dry_run:
            time.sleep(0.03)

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Import suppliers into PocketBase via API")
    parser.add_argument("--base-url", required=True, help="PocketBase base URL, e.g. http://127.0.0.1:8090")
    parser.add_argument("--input", required=True, help="Input .json or .csv file")
    parser.add_argument("--token", default=os.getenv("PB_TOKEN", ""), help="PocketBase auth token; env PB_TOKEN supported")
    parser.add_argument("--admin-email", default=os.getenv("PB_ADMIN_EMAIL", ""), help="Admin email; env PB_ADMIN_EMAIL supported")
    parser.add_argument("--admin-password", default=os.getenv("PB_ADMIN_PASSWORD", ""), help="Admin password; env PB_ADMIN_PASSWORD supported")
    parser.add_argument("--suppliers-collection", default="suppliers")
    parser.add_argument("--contacts-collection", default="supplier_contacts")
    parser.add_argument("--upsert", dest="upsert", action="store_true", default=True, help="Update existing records when matched (default)")
    parser.add_argument("--no-upsert", dest="upsert", action="store_false", help="Always create new records")
    parser.add_argument("--dry-run", action="store_true", help="Validate and print planned actions without writing")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Input file not found: {input_path}", file=sys.stderr)
        return 2

    try:
        items = normalize_items(load_input(input_path))
        errors = validate_items(items)
        if errors:
            print("Validation failed:", file=sys.stderr)
            for err in errors:
                print(f"  - {err}", file=sys.stderr)
            return 2

        print(f"Loaded {len(items)} suppliers from {input_path}")
        print(f"Total contacts: {sum(len(i.get('contacts', [])) for i in items)}")

        client = PocketBaseClient(args.base_url, token=args.token)
        if not args.dry_run and not client.token:
            if not args.admin_email or not args.admin_password:
                print("Authentication required: provide --token/PB_TOKEN or --admin-email/--admin-password", file=sys.stderr)
                return 2
            client.admin_login(args.admin_email, args.admin_password)

        # In dry-run without token, skip remote collection checks to allow offline validation.
        if not args.dry_run:
            client.list_records(args.suppliers_collection, 'id != ""', per_page=1)
            client.list_records(args.contacts_collection, 'id != ""', per_page=1)

        stats = import_items(
            client=client,
            items=items,
            suppliers_collection=args.suppliers_collection,
            contacts_collection=args.contacts_collection,
            upsert=args.upsert,
            dry_run=args.dry_run,
        )

        print("\nImport report:")
        for key, value in stats.items():
            print(f"  {key}: {value}")
        if args.dry_run:
            print("\nDry-run complete. No data was written.")
        return 0
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
