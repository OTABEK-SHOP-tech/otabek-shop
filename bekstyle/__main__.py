"""Run with: python -m bekstyle"""

import os
import uvicorn
from bekstyle.config import settings

def main():
    port = int(os.getenv("PORT", settings.PORT or 8000))
    host = os.getenv("HOST", "0.0.0.0")

    # Run FastAPI app with lifespan starting aiogram bot
    uvicorn.run(
        "bekstyle.api.server:app",
        host=host,
        port=port,
        reload=False,
    )

if __name__ == "__main__":
    main()
