import asyncio
import os
import sys
import json

sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.core.security import EncryptionService

async def decrypt_bybit_keys(encrypted_data_string: str):
    encryption_service = EncryptionService()
    decrypted_keys = encryption_service.decrypt_keys(encrypted_data_string)
    print(json.dumps(decrypted_keys, indent=2))

if __name__ == "__main__":
    # This is the encrypted_data string from the previous step's output for Bybit
    bybit_encrypted_data = "gAAAAABpK0oJ8ADqqg1qRG-3o9VPfFgwzBmu65HQuT8cGU3PSCNZ5wC1L6I2z5qBzIFk3fc3QWVoohwOXK53cqoQOgKMPYJToi7qxl_76-vmX4p865tAAd3zedMrLrCe566oLeFAS56V5lDJ-j6154PlSz0odWlawjmMhx6UsbKLMwgHrkRHDVOHaAmBfVueyxrSkkKKMc4m"
    asyncio.run(decrypt_bybit_keys(bybit_encrypted_data))
