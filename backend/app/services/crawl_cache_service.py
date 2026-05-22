from __future__ import annotations

import hashlib
import json
from typing import Any, Optional

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.app.models.crawl_cache import CrawlCache
from backend.app.core.time import shanghai_now


def get_cache(db: Session, cache_key: str) -> Optional[dict[str, Any]]:
    cache = db.scalars(
        select(CrawlCache).where(CrawlCache.cache_key == cache_key)
    ).first()
    if cache:
        if not cache.is_expired:
            return cache.payload
        else:
            db.delete(cache)
            db.commit()
    return None


def set_cache(db: Session, cache_key: str, payload: dict[str, Any]) -> None:
    # Cleanup old caches for same key
    db.execute(delete(CrawlCache).where(CrawlCache.cache_key == cache_key))
    
    cache = CrawlCache(cache_key=cache_key, payload=payload, created_at=shanghai_now())
    db.add(cache)
    db.commit()


def generate_cache_key(prefix: str, params: dict[str, Any]) -> str:
    # Sort keys to ensure consistent hashing
    param_str = json.dumps(params, sort_keys=True)
    return f"{prefix}:{hashlib.md5(param_str.encode()).hexdigest()}"


def purge_expired_cache(db: Session) -> int:
    from datetime import timedelta
    expired_at = shanghai_now() - timedelta(days=7)
    result = db.execute(delete(CrawlCache).where(CrawlCache.created_at < expired_at))
    db.commit()
    return result.rowcount
