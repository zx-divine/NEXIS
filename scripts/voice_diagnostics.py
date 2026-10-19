"""Development standalone launcher; production voice never uses Desktop paths."""

from pathlib import Path
import site
import sys

root = Path(__file__).resolve().parents[1]
site.addsitedir(str(Path(__file__).resolve().parents[1] / ".provider-deps"))
site.addsitedir(str(root / ".dev-deps"))
sys.path.insert(0, str(root / "src"))
from nexis.ui.voice_diagnostics import main  # noqa: E402

raise SystemExit(main())
