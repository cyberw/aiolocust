import os
import re

import pytest

WINDOWS_DELAY = 1 if os.name == "nt" else 0


def assert_search(pattern, string):
    __tracebackhide__ = True  # Hides this helper function from the traceback
    if not re.search(pattern, string):
        pytest.fail(f"Could not find: '{pattern}'\n{string}")
