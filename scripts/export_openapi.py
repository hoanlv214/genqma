"""Export OpenAPI 3.1.0 specification for static hosting and Vercel CDN deployment."""

import json
from pathlib import Path
import yaml

from backend.app.main import app

REPO_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_PUBLIC = REPO_ROOT / "frontend" / "public"

def export_specs():
    schema = app.openapi()

    # Write frontend/public/openapi.json
    FRONTEND_PUBLIC.mkdir(parents=True, exist_ok=True)
    json_path = FRONTEND_PUBLIC / "openapi.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2)
    print(f"Exported {json_path} ({len(json.dumps(schema))} bytes)")

    # Write frontend/public/openapi.yaml
    yaml_path = FRONTEND_PUBLIC / "openapi.yaml"
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(schema, f, sort_keys=False)
    print(f"Exported {yaml_path}")

    # Write root openapi.json for root accessibility
    root_json = REPO_ROOT / "openapi.json"
    with open(root_json, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2)
    print(f"Exported {root_json}")

if __name__ == "__main__":
    export_specs()
