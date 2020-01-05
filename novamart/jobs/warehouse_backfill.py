"""Warehouse backfill: copy every serving-DB table into BigQuery.

Mechanism (per table, driven by warehouse_manifest.json):
  1. `gcloud sql export csv` with an explicit column-cast SELECT (timestamps
     rendered UTC, NULLs as a sentinel so blank text stays blank)
  2. `bq load` into the matching dataset (public.* -> novamart.*,
     analytics.* -> analytics.*) with the manifest schema

Requires: gcloud + bq authenticated; a staging GCS prefix the Cloud SQL
service agent can write to. Exports are serialized (Cloud SQL runs one
import/export operation at a time); loads run as they land.

    python -m novamart.jobs.warehouse_backfill --project P --instance I \
        --staging gs://bucket/exports [--only public.orders]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys

NULL = "__PGNULL__"
MANIFEST = pathlib.Path(__file__).with_name("warehouse_manifest.json")


def cast_expr(col: str, pg_type: str) -> str:
    if pg_type.startswith("timestamp with time zone"):
        return ("to_char(" + col + " AT TIME ZONE 'UTC', "
                "'YYYY-MM-DD\"T\"HH24:MI:SS.US') || '+00:00'")
    if pg_type == "boolean":
        return col + "::text"
    if pg_type.startswith(("bigint", "integer", "smallint", "numeric",
                           "double precision", "real", "date", "uuid",
                           "timestamp without time zone")):
        return col + "::text"
    return col  # text stays text


def sh(argv: list[str]) -> None:
    print("+", " ".join(argv), flush=True)
    subprocess.run(argv, check=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--instance", required=True)
    ap.add_argument("--staging", required=True, help="gs:// prefix for CSV exports")
    ap.add_argument("--database", default="novamart")
    ap.add_argument("--only", action="append", default=None)
    args = ap.parse_args()

    manifest = json.loads(MANIFEST.read_text())
    tables = {k: v for k, v in manifest["tables"].items()
              if not args.only or k in args.only}
    for i, (table, cols) in enumerate(sorted(tables.items()), 1):
        schema_name, name = table.split(".")
        dataset = "novamart" if schema_name == "public" else schema_name
        select = ", ".join(
            "COALESCE(" + cast_expr(c, t) + ", '" + NULL + "')" if t != "text"
            else "COALESCE(" + c + ", '" + NULL + "')"
            for c, t in cols)
        uri = args.staging.rstrip("/") + "/" + table + ".csv"
        print("[" + str(i) + "/" + str(len(tables)) + "] " + table, flush=True)
        sh(["gcloud", "sql", "export", "csv", args.instance, uri,
            "--database", args.database, "--query",
            "SELECT " + select + " FROM " + table + " ORDER BY 1",
            "--project", args.project, "--quiet"])
        bq_schema = ",".join(c + ":" + manifest["bq_types"][table][j]
                             for j, (c, _) in enumerate(cols))
        sh(["bq", "--project_id", args.project, "load", "--replace",
            "--source_format=CSV", "--null_marker=" + NULL,
            dataset + "." + name, uri, bq_schema])
    print("backfill complete: " + str(len(tables)) + " tables", flush=True)


if __name__ == "__main__":
    sys.exit(main())
