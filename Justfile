justfile_dir := justfile_directory()


test-unit:
    #!/bin/bash
    pytest ./tests/unit


