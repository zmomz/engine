from pydantic import BaseModel

class DashboardOutput(BaseModel):
    tvl: float
    free_usdt: float
