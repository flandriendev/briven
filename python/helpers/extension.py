from abc import abstractmethod
import os
from typing import Any
from python.helpers import extract_tools, files
from python.helpers.print_style import PrintStyle
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent import Agent


DEFAULT_EXTENSIONS_FOLDER = "python/extensions"
USER_EXTENSIONS_FOLDER = "usr/extensions"

_cache: dict[str, list[type["Extension"]]] = {}

# Patterns that are blocked in user-supplied extensions (from usr/ paths).
# Built-in extensions (python/extensions/) are trusted and skip this check.
_BLOCKED_PATTERNS = [
    "subprocess.call(",
    "subprocess.Popen(",
    "subprocess.run(",
    "os.system(",
    "os.popen(",
    "shutil.rmtree(",
    "eval(",
    "exec(",
    "__import__(",
]


class Extension:

    def __init__(self, agent: "Agent|None", **kwargs):
        self.agent: "Agent" = agent  # type: ignore < here we ignore the type check as there are currently no extensions without an agent
        self.kwargs = kwargs

    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        pass


def _get_disabled_extensions() -> set[str]:
    """Return a set of disabled extension filenames (without .py) from settings."""
    try:
        from python.helpers import settings
        s = settings.get_settings()
        raw = s.get("disabled_extensions", "")
        if not raw:
            return set()
        # Comma-separated list, e.g. "_48_atlas_hybrid_recall,_49_embed_new_entries"
        return {name.strip() for name in raw.split(",") if name.strip()}
    except Exception:
        return set()


def _security_check_file(file_path: str) -> bool:
    """
    Basic security check for user-supplied extensions (from usr/ paths).
    Returns True if safe, False if blocked patterns found.

    This is NOT a sandbox — it's a lightweight guard against accidental
    inclusion of dangerous patterns. Built-in extensions are trusted.
    """
    try:
        from python.helpers import settings
        s = settings.get_settings()
        if not s.get("extension_security_check", True):
            return True
    except Exception:
        pass

    try:
        content = files.read_file(file_path)
        if not content:
            return True
        for pattern in _BLOCKED_PATTERNS:
            if pattern in content:
                PrintStyle.warning(
                    f"Extension security: blocked '{os.path.basename(file_path)}' — "
                    f"contains disallowed pattern '{pattern}'. "
                    f"Move to python/extensions/ if this is intentional."
                )
                return False
    except Exception:
        pass
    return True


async def call_extensions(
    extension_point: str, agent: "Agent|None" = None, **kwargs
) -> Any:
    from python.helpers import projects, subagents

    # search for extension folders in all agent's paths
    paths = subagents.get_paths(agent, "extensions", extension_point, default_root="python")
    all_exts = [cls for path in paths for cls in _get_extensions(path)]

    # merge: first ocurrence of file name is the override
    unique = {}
    for cls in all_exts:
        file = _get_file_from_module(cls.__module__)
        if file not in unique:
            unique[file] = cls
    classes = sorted(
        unique.values(), key=lambda cls: _get_file_from_module(cls.__module__)
    )

    # Get disabled extensions set
    disabled = _get_disabled_extensions()

    # execute unique extensions (skip disabled ones)
    for cls in classes:
        ext_name = _get_file_from_module(cls.__module__)
        if ext_name in disabled:
            continue
        await cls(agent=agent).execute(**kwargs)


def _get_file_from_module(module_name: str) -> str:
    return module_name.split(".")[-1]


def _get_extensions(folder: str):
    global _cache
    folder = files.get_abs_path(folder)
    if folder in _cache:
        classes = _cache[folder]
    else:
        if not files.exists(folder):
            return []

        classes = extract_tools.load_classes_from_folder(folder, "*", Extension)

        # Security filter: for user extensions (from usr/ paths), post-filter
        # classes whose source files contain blocked patterns
        if "/usr/" in folder:
            safe_classes = []
            for cls in classes:
                # Resolve the source file for this class
                src_file = getattr(cls, "__module__", "")
                file_name = src_file.split(".")[-1] + ".py" if src_file else ""
                file_path = os.path.join(folder, file_name)
                if os.path.exists(file_path) and not _security_check_file(file_path):
                    continue  # skip blocked extension
                safe_classes.append(cls)
            classes = safe_classes

        _cache[folder] = classes

    return classes
