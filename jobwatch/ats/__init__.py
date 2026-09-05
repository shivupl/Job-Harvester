from __future__ import annotations

from . import ashby, greenhouse, lever

ADAPTERS = {"greenhouse": greenhouse, "lever": lever, "ashby": ashby}
PROBE_ORDER = ["greenhouse", "lever", "ashby"]
