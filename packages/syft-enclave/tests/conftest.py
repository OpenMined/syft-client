def pytest_addoption(parser):
    parser.addoption(
        "--model-size",
        default="270m",
        help="Gemma model size to test: 270m, 1b, 4b, 12b, 27b, or 'all'",
    )
