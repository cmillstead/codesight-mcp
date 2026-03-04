"""Security primitives ported from basalt-mcp."""

from .validation import (
    ValidationError,
    validate_path,
    assert_no_null_bytes,
    assert_safe_segments,
    assert_path_limits,
    assert_inside_root,
    assert_no_symlinked_parents,
)
from .errors import sanitize_error, strip_system_paths
from .boundaries import wrap_untrusted_content, make_meta
from .limits import (
    MAX_FILE_SIZE,
    MAX_FILE_COUNT,
    MAX_CONTEXT_LINES,
    MAX_PATH_LENGTH,
    MAX_DIRECTORY_DEPTH,
    MAX_INDEX_SIZE,
    MAX_SEARCH_RESULTS,
    GITHUB_API_TIMEOUT,
)
