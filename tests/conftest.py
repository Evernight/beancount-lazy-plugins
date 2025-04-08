"""
Dummy conftest.py for beancount_lazy_plugins.

If you don't know what this is for, just leave it empty.
Read more about conftest.py under:
- https://docs.pytest.org/en/stable/fixture.html
- https://docs.pytest.org/en/stable/writing_plugins.html
"""

import pytest

def pytest_addoption(parser):
    """Add command line options for pytest."""
    parser.addoption(
        "--capture-output",
        action="store_true",
        help="Capture test output files for reference",
    )

@pytest.fixture
def capture_output(request):
    """Fixture to determine if we should capture output files."""
    return request.config.getoption("--capture-output")