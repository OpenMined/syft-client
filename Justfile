justfile_dir := justfile_directory()


test-unit:
    #!/bin/bash
    pytest ./tests/unit


test-integration:
    #!/bin/bash
    pytest -s ./tests/integration


delete-syftboxes:
    #!/bin/bash
    python ./scripts/delete_syftboxes.py

