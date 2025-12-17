justfile_dir := justfile_directory()

_cyan := '\033[0;36m'
_red := '\033[0;31m'
_green := '\033[0;32m'
_nc := '\033[0m'

test-unit:
    #!/bin/bash
    uv run pytest ./tests/unit


test-integration:
    #!/bin/bash
    uv run pytest -s ./tests/integration


delete-syftboxes:
    #!/bin/bash
    python ./scripts/delete_syftboxes.py

clean:
    #!/bin/sh
    printf "{{ _cyan }}Cleaning up...{{ _nc }}\n"

    # Function to remove directories by name pattern
    remove_dirs() {
        dir_name=$1
        count=$(find . -type d -name "$dir_name" 2>/dev/null | wc -l)
        if [ "$count" -gt 0 ]; then
            printf "  {{ _red }}✗{{ _nc }} Removing %s %s directories\n" "$count" "$dir_name"
            find . -type d -name "$dir_name" -exec rm -rf {} + 2>/dev/null || true
        fi
    }

    remove_dirs "syft_client.egg-info"
    remove_dirs "__pycache__"
    remove_dirs ".pytest_cache"

    printf "{{ _green }}✓ Clean complete!{{ _nc }}\n"