"""Generate reporting assets and the companion's reproducible artifacts."""

from companion import artifacts, reporting_schema


if __name__ == "__main__":
    reporting_schema.generate()
    artifacts.main()
