"""Cross-platform development entry point."""

import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "orchestra.api.app:app",
        host=os.getenv("ORCHESTRA_HOST", "127.0.0.1"),
        port=int(os.getenv("ORCHESTRA_PORT", "8000")),
        reload=os.getenv("ORCHESTRA_RELOAD", "true").lower() == "true",
    )
