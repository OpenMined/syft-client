justfile_dir := justfile_directory()

_cyan := '\033[0;36m'
_red := '\033[0;31m'
_green := '\033[0;32m'
_nc := '\033[0m'

# ---------------------------------------------------------------------------------------------------------------------
# Aliases

alias b := build
alias p := publish
alias bp:= bump-and-publish
# ---------------------------------------------------------------------------------------------------------------------


test-unit:
    #!/bin/bash
    uv run pytest -n auto ./tests/unit


test-integration:
    #!/bin/bash
    uv run pytest -s ./tests/integration


benchmark:
    #!/bin/bash
    python ./benchmarks/benchmark_loadtime.py


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


# Bump version (patch, minor, or major)
[group('version')]
bump part="patch":
    uvx bump2version --allow-dirty {{ part }}

# Show current version
[group('version')]
version:
    @python3 -c "import syft_client; print(syft_client.__version__)"

# Build syft client wheel
[group('build')]
build:
    @echo "{{ _cyan }}Building syft-client wheel...{{ _nc }}"
    rm -rf dist/
    uv build
    @echo "{{ _green }}Build complete!{{ _nc }}"

# Publish to PyPI
[group('publish')]
publish: build
    @echo "{{ _cyan }}Publishing to PyPI...{{ _nc }}"
    uvx twine upload dist/*
    @echo "{{ _green }}Publish complete!{{ _nc }}"

# Bump version and publish to PyPI
[group('publish')]
bump-and-publish part="patch":
    just bump {{ part }}
    just publish
    @echo "{{ _green }}Bump and publish complete!{{ _nc }}"

