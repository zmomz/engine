from app.schemas.grid_config import RiskEngineConfig
import json
import sys

# Add backend to path
sys.path.append('/root/engine/backend')

config = RiskEngineConfig()
print(json.dumps(config.model_dump(mode='json')))
