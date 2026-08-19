"""Regenerate and validate the portable post-semantic episode schema examples."""

from companion import reporting_schema


if __name__ == "__main__":
    reporting_schema.generate()
    reporting_schema.validate_assets()
    print("PASS reporting schema: valid example accepted; invalid example rejected")
