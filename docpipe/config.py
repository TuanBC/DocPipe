import os
from pathlib import Path
from types import SimpleNamespace

import yaml

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "config" / "pipeline.yaml"


def _ns(d):
    if isinstance(d, dict):
        return SimpleNamespace(**{k: _ns(v) for k, v in d.items()})
    return d


def load(path=None):
    """Load the YAML config. To route through the LiteLLM proxy without editing the file, set
    DOCPIPE_MODEL (e.g. openai/luna), DOCPIPE_API_BASE (http://127.0.0.1:4010/v1) and DOCPIPE_API_KEY."""
    with open(path or DEFAULT_PATH, encoding="utf-8") as f:
        cfg = _ns(yaml.safe_load(f))
    if os.environ.get("DOCPIPE_MODEL"):
        cfg.model.name = os.environ["DOCPIPE_MODEL"]
    if os.environ.get("DOCPIPE_API_BASE"):
        cfg.model.api_base = os.environ["DOCPIPE_API_BASE"]
    cfg.model.api_key = os.environ.get("DOCPIPE_API_KEY")
    _defaults(cfg)
    cfg.kb.openviking.home_out = cfg.paths.out  # only this output dir publishes to the KB (see pipeline._publishes)
    if os.environ.get("DOCPIPE_OV_URL"):
        cfg.kb.openviking.url = os.environ["DOCPIPE_OV_URL"]
    if os.environ.get("DOCPIPE_OV_API_KEY"):
        cfg.kb.openviking.api_key = os.environ["DOCPIPE_OV_API_KEY"]
    if os.environ.get("DOCPIPE_KB_BACKEND"):
        cfg.kb.backend = os.environ["DOCPIPE_KB_BACKEND"]
    return cfg


DEFAULTS = {
    "ocr": {"dpi": 150, "max_llm_pages": 40, "kb_fulltext_max_chars": 60000},
    "kb": {"backend": "local", "openviking": {"url": "http://127.0.0.1:1933", "api_key": None,
                                               "root": "viking://resources/docpipe", "auto_ingest": False, "timeout": 600}},
}


def _merge(ns, defaults):
    for k, v in defaults.items():
        if not hasattr(ns, k):
            setattr(ns, k, _ns(v))
        elif isinstance(v, dict):
            _merge(getattr(ns, k), v)


def _defaults(cfg):
    """Older config files (eval copies) lack the ocr/kb sections; fill them so every module can rely on them."""
    _merge(cfg, DEFAULTS)
    if not hasattr(cfg.taxonomy, "statement_doc_types"):
        cfg.taxonomy.statement_doc_types = ["financial_statements"]
