from fastapi import APIRouter

router = APIRouter()

@router.get("/tvl")
async def get_tvl():
    # Placeholder for Total Value Locked
    return {"tvl": 1234567.89}

@router.get("/pnl")
async def get_pnl():
    # Placeholder for Profit and Loss
    return {"pnl": 12345.67}

@router.get("/active-groups-count")
async def get_active_groups_count():
    # Placeholder for active position groups count
    return {"count": 5}
