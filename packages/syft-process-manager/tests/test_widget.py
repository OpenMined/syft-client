"""Test the ProcessHandle widget rendering and log polling behavior"""

import time
from pathlib import Path
from typing import Generator

import pytest
from fastapi import Request
from playwright.sync_api import sync_playwright
from syft_process_manager.display import backend_app
from syft_process_manager.display.backend_app import ensure_app_is_running
from syft_process_manager.display.widget import render_process_widget
from syft_process_manager.process_manager import ProcessManager

_request_counts: dict[str, int] = {}
_request_details: list[dict] = []


@backend_app.app.middleware("http")
async def count_requests(request: Request, call_next):
    path = request.url.path
    _request_counts[path] = _request_counts.get(path, 0) + 1
    _request_details.append(
        {
            "path": path,
            "query_params": dict(request.query_params),
            "method": request.method,
        }
    )
    response = await call_next(request)
    return response


@pytest.fixture
def request_counter():
    _request_counts.clear()
    _request_details.clear()

    class Counter:
        request_counts = _request_counts
        request_details = _request_details

    yield Counter()


@pytest.fixture
def widget_html(
    process_manager: ProcessManager,
) -> Generator[tuple[str, Path, Path], None, None]:
    handle = process_manager.create_and_run(
        name="widget-test-process",
        cmd=["python3", "-c", "import time; print('hello'); time.sleep(60)"],
    )
    time.sleep(0.5)

    port = ensure_app_is_running()
    backend_url = f"http://localhost:{port}"

    info = handle.info()
    html = render_process_widget(
        name=info["name"],
        status=info["status"],
        pid=info["pid"],
        uptime=info["uptime"],
        backend_url=backend_url,
        stdout_path=str(handle.config.stdout_path),
        stderr_path=str(handle.config.stderr_path),
    )

    yield html, handle.config.stdout_path, handle.config.stderr_path
    handle.terminate()


# skip
@pytest.mark.skip(reason="Flaky test + requires playwright setup")
def test_widget_polls_correct_endpoints(
    widget_html: tuple[str, Path, Path], request_counter
) -> None:
    html, stdout_path, _stderr_path = widget_html

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(html)
        time.sleep(3)

        # Verify polling is working
        assert "/read_lines" in request_counter.request_counts
        assert request_counter.request_counts["/read_lines"] >= 2

        # Verify correct file and parameters
        for req in request_counter.request_details:
            if req["path"] == "/read_lines":
                assert req["query_params"]["file_path"] == str(stdout_path)
                assert req["query_params"]["mode"] == "tail"
                assert req["query_params"]["num_lines"] == "20"
                assert req["method"] == "GET"

        browser.close()
