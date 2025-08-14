# python_app/crawler/source_loader.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List, Optional
import yaml

# Kandidaten-Pfade: .../crawler/data/sources.yaml ODER .../data/sources.yaml
_THIS_DIR = Path(__file__).resolve().parent
_CANDIDATES = [
    _THIS_DIR / "data" / "sources.yaml",          # python_app/crawler/data/sources.yaml
    _THIS_DIR.parent / "data" / "sources.yaml",   # python_app/data/sources.yaml
]

def _find_sources_path() -> Path:
    for p in _CANDIDATES:
        if p.exists():
            return p
    raise FileNotFoundError(
        "sources.yaml nicht gefunden. Probiert:\n  - " + "\n  - ".join(str(p) for p in _CANDIDATES)
    )

def load_sources_raw() -> Any:
    path = _find_sources_path()
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data

def _normalize_sources(data: Any) -> List[Dict[str, Any]]:
    """
    Unterstützt zwei Formate:

    1) Mapping (empfohlen):
       kingkalli:
         start_url: ...
         headers: ...
         enabled: true

    2) Liste:
       sources:
         - name: kingkalli
           start_url: ...
           headers: ...
           enabled: true
    """
    # Mapping-Format (Top-Level-Keys = namen)
    if isinstance(data, dict) and "sources" not in data:
        items = []
        for name, cfg in data.items():
            if not isinstance(cfg, dict):
                continue
            cfg = {"name": name, **cfg}
            items.append(cfg)
        return items

    # Listenformat unter "sources"
    if isinstance(data, dict) and isinstance(data.get("sources"), list):
        items = []
        for cfg in data["sources"]:
            if isinstance(cfg, dict):
                items.append(cfg)
        return items

    return []

def load_sources() -> List[Dict[str, Any]]:
    data = load_sources_raw()
    items = _normalize_sources(data)
    # nur aktivierte Quellen
    return [s for s in items if s.get("enabled", True)]

def get_source(name: str) -> Optional[Dict[str, Any]]:
    items = load_sources()
    for s in items:
        if s.get("name") == name:
            return s
    # Nicht gefunden: verfügbare Namen auflisten
    available = ", ".join(sorted([s.get("name", "?") for s in items])) or "—"
    raise KeyError(f"Quelle '{name}' nicht gefunden. Verfügbar: {available}")
