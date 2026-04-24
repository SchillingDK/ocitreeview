"""
FastAPI backend entry point.
Run with: uvicorn main:app --reload
"""
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from oci_fetcher import build_region_tree

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(title="OCI Tree View API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3010"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

REGIONS = ["eu-frankfurt-1", "eu-stockholm-1"]

# In-memory cache: stores the full tree response until force-reloaded.
_tree_cache: Optional[dict] = None


@app.get("/api/tree")
def get_full_tree(force: bool = Query(False, description="Pass true to bypass cache and re-fetch from OCI")):
    """Return the tree for all configured regions, served from cache unless force=true."""
    global _tree_cache
    if not force and _tree_cache is not None:
        return _tree_cache
    regions_data = [build_region_tree(region) for region in REGIONS]
    _tree_cache = {
        "cached_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "regions": regions_data,
    }
    return _tree_cache


@app.get("/api/tree/{region}")
def get_region_tree(region: str):
    """Return the tree for a single region (not cached)."""
    if region not in REGIONS:
        raise HTTPException(status_code=404, detail=f"Region '{region}' is not configured.")
    return build_region_tree(region)


@app.get("/api/regions")
def list_regions():
    return REGIONS
