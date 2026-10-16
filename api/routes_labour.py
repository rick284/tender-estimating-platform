"""Labour true-cost calculator (stateless): shows the build-up while the estimator types. The saved rate goes through the normal edit draft."""
from __future__ import annotations
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from security import current_user
from tender_engine import labour_rate as lab

router = APIRouter(prefix="/api/labour", tags=["labour"])


@router.post("/calc")
async def calc(body: dict[str, Any], user: dict[str, Any] = Depends(current_user)):
    try:
        return lab.to_json(lab.compute(body))
    except (lab.LabourError, ValueError) as e:
        raise HTTPException(422, str(e))
