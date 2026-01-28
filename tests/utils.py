import re

import pytest


def assert_search(pattern, string):
    __tracebackhide__ = True  # Hides this helper function from the traceback
    if not re.search(pattern, string):
        pytest.fail(f"Could not find: '{pattern}'\n{string}")
