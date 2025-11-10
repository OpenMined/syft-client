justfile_dir := justfile_directory()


test-unit:
    #!/bin/bash
    uv run pytest ./tests/unit


test-integration:
    #!/bin/bash
    uv run pytest -s ./tests/integration


delete-syftboxes:
    #!/bin/bash
    python ./scripts/delete_syftboxes.py

