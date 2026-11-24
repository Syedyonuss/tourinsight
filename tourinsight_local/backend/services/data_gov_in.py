"""Optional Open Government Data Platform connector (data.gov.in).

A resource ID and API key are selected/provided by the project operator. Field names
are configurable because each government dataset can publish a different schema.
Secrets remain server-side in the local .env file.
"""
from __future__ import annotations

import csv
import io
import os
from typing import Any

import httpx

from backend.services.ingest import import_tourism_csv

API_BASE = "https://api.data.gov.in/resource/"
DEFAULT_LIMIT = 1000
MAX_PAGE_LIMIT = 5000


def connector_status() -> dict[str, Any]:
    key = os.getenv("DATA_GOV_IN_API_KEY", "").strip()
    resource_id = os.getenv("DATA_GOV_IN_RESOURCE_ID", "").strip()
    return {
        "configured": bool(key and resource_id),
        "resource_id": resource_id or None,
        "api_key_present": bool(key),
        "field_mapping": {
            "destination": os.getenv("DATA_GOV_IN_DESTINATION_FIELD", "destination"),
            "year": os.getenv("DATA_GOV_IN_YEAR_FIELD", "year"),
            "month": os.getenv("DATA_GOV_IN_MONTH_FIELD", "month"),
            "visitors": os.getenv("DATA_GOV_IN_VISITORS_FIELD", "visitors"),
            "capacity_per_month": os.getenv("DATA_GOV_IN_CAPACITY_FIELD", "capacity_per_month"),
        },
        "note": "The API key is stored only in the local server environment and is never returned to the browser.",
    }


async def sync_tourism_resource() -> dict[str, Any]:
    key = os.getenv("DATA_GOV_IN_API_KEY", "").strip()
    resource_id = os.getenv("DATA_GOV_IN_RESOURCE_ID", "").strip()
    if not key or not resource_id:
        raise ValueError(
            "Configure DATA_GOV_IN_API_KEY and DATA_GOV_IN_RESOURCE_ID in .env, then restart TourInsight."
        )

    mapping = connector_status()["field_mapping"]
    try:
        limit = min(max(int(os.getenv("DATA_GOV_IN_PAGE_SIZE", str(DEFAULT_LIMIT))), 1), DEFAULT_LIMIT)
        max_records = min(max(int(os.getenv("DATA_GOV_IN_MAX_RECORDS", "5000")), 1), MAX_PAGE_LIMIT)
    except ValueError as exc:
        raise ValueError("DATA_GOV_IN_PAGE_SIZE and DATA_GOV_IN_MAX_RECORDS must be whole numbers.") from exc
    if any(not str(value).strip() for value in mapping.values()):
        raise ValueError("All data.gov.in field-mapping values must be non-empty column names.")
    source_name = os.getenv("DATA_GOV_IN_SOURCE_NAME", "data.gov.in tourism resource").strip() or "data.gov.in tourism resource"
    url = API_BASE + resource_id
    records: list[dict[str, Any]] = []

    async with httpx.AsyncClient(timeout=35.0, headers={"User-Agent": "TourInsightLocal/1.0 (open-data connector)"}) as client:
        offset = 0
        while offset < max_records:
            page_size = min(limit, max_records - offset)
            response = await client.get(
                url,
                params={"api-key": key, "format": "json", "offset": offset, "limit": page_size},
            )
            response.raise_for_status()
            payload = response.json()
            page = payload.get("records") or payload.get("data") or []
            if not isinstance(page, list):
                raise ValueError("The selected data.gov.in resource did not return a records array.")
            if not page:
                break
            records.extend(x for x in page if isinstance(x, dict))
            offset += len(page)
            if len(page) < page_size:
                break

    if not records:
        raise ValueError("The selected data.gov.in resource returned no records.")

    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=["destination", "year", "month", "visitors", "capacity_per_month", "notes"])
    writer.writeheader()
    missing_fields = set()
    for item in records:
        dest = item.get(mapping["destination"])
        year = item.get(mapping["year"])
        month = item.get(mapping["month"])
        visitors = item.get(mapping["visitors"])
        if dest in (None, "") or year in (None, "") or month in (None, "") or visitors in (None, ""):
            missing_fields.add("one or more required mapped fields")
            continue
        capacity_field = mapping["capacity_per_month"]
        writer.writerow({
            "destination": dest,
            "year": year,
            "month": month,
            "visitors": visitors,
            "capacity_per_month": item.get(capacity_field, ""),
            "notes": f"data.gov.in resource {resource_id}; imported via API",
        })

    csv_bytes = output.getvalue().encode("utf-8")
    if csv_bytes.count(b"\n") <= 1:
        fields = ", ".join(sorted(missing_fields)) or "required fields"
        raise ValueError(
            f"No importable rows. Check the .env field mapping for destination/year/month/visitors; missing {fields}."
        )

    result = import_tourism_csv(csv_bytes, f"data.gov.in-{resource_id}.csv", source_name)
    result.update({
        "source": "data.gov.in",
        "resource_id": resource_id,
        "records_fetched": len(records),
        "mapped_rows": csv_bytes.count(b"\n") - 1,
        "max_records_limit": max_records,
        "note": "Rows were validated and upserted using TourInsight's destination/year/month key. Confirm resource coverage and units before analysis.",
    })
    return result
