"""Export the API contract to docs/api/openapi.yaml.

Usage (from the project root):
    uv run --project backend python scripts/export_openapi.py

Run it after any change to routes or schemas, then commit the updated file.
The test tests/test_openapi_contract.py fails if you forget.
"""

from queryrag.main import app
from queryrag.openapi_contract import CONTRACT_PATH, render_openapi_yaml


def main() -> None:
    CONTRACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONTRACT_PATH.write_text(render_openapi_yaml(app), encoding="utf-8")
    print(f"Wrote {CONTRACT_PATH}")


if __name__ == "__main__":
    main()
