import sys
import site
from pathlib import Path

# Support a source checkout as well as PyInstaller's bundled package.
if not getattr(sys, "frozen", False):
    root = Path(__file__).resolve().parents[1]
    site.addsitedir(str(root / ".provider-deps"))
    site.addsitedir(str(root / ".dev-deps"))
    sys.path[:0] = [str(root / "src"), str(root / ".provider-deps"), str(root / ".dev-deps")]

from nexis.main import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
