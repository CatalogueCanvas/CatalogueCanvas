from __future__ import annotations
import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path

import tomli_w


@dataclass
class SiteConfig:
    title: str = "My Catalog"
    description: str = "My catalog of items"
    base_url: str = ""
    author: str = ""
    theme: str = "dark"


@dataclass
class BuildConfig:
    items_per_page: int = 12
    image_format: str = "webp"
    image_scale: float = 2.5


@dataclass
class PathsConfig:
    ingestion_dir: str = "ingestion"
    output_dir: str = "output"
    db_path: str = "config/catalog.db"
    backup_dir: str = ""


@dataclass
class LLMConfig:
    provider: str = "lmstudio"
    api_url: str = "http://localhost:1234/v1/chat/completions"
    model: str = "google/gemma-4-12b-qat"
    api_key_env: str = ""
    item_type: str = "image"
    summary_focus: str = "the item's notable characteristics"


@dataclass
class IngestConfig:
    compress_other_files: bool = False


@dataclass
class CatalogConfig:
    site: SiteConfig = field(default_factory=SiteConfig)
    build: BuildConfig = field(default_factory=BuildConfig)
    paths: PathsConfig = field(default_factory=PathsConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    ingest: IngestConfig = field(default_factory=IngestConfig)


def load_config(config_dir: Path) -> CatalogConfig:
    cfg = CatalogConfig()

    config_path = config_dir / "config.toml"
    if config_path.exists():
        with open(config_path, "rb") as f:
            data = tomllib.load(f)
        s = data.get("site", {})
        b = data.get("build", {})
        p = data.get("paths", {})
        l = data.get("llm", {})
        i = data.get("ingest", {})
        cfg = CatalogConfig(
            site=SiteConfig(**{k: v for k, v in s.items() if k in SiteConfig.__dataclass_fields__}),
            build=BuildConfig(**{k: v for k, v in b.items() if k in BuildConfig.__dataclass_fields__}),
            paths=PathsConfig(**{k: v for k, v in p.items() if k in PathsConfig.__dataclass_fields__}),
            llm=LLMConfig(**{k: v for k, v in l.items() if k in LLMConfig.__dataclass_fields__}),
            ingest=IngestConfig(**{k: v for k, v in i.items() if k in IngestConfig.__dataclass_fields__}),
        )

    return cfg


def save_config(config_dir: Path, cfg: CatalogConfig) -> Path:
    config_path = config_dir / "config.toml"
    data = {
        "site": asdict(cfg.site),
        "build": asdict(cfg.build),
        "paths": asdict(cfg.paths),
        "llm": asdict(cfg.llm),
        "ingest": asdict(cfg.ingest),
    }
    config_dir.mkdir(parents=True, exist_ok=True)
    with open(config_path, "wb") as f:
        tomli_w.dump(data, f)
    return config_path
