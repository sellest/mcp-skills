"""Entry point: mcp-skills [--data DIR] [--host HOST] [--port PORT]."""

import argparse
import logging
import os

import uvicorn

from .server import create_app
from .storage import SkillStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve Markdown skills over MCP")
    parser.add_argument("--data", default=os.environ.get("SKILLS_DATA_DIR", "/data/skills"))
    parser.add_argument("--host", default=os.environ.get("SKILLS_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("SKILLS_PORT", "6004")))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    # The SDK logs every stateless request at INFO; keep only our own events.
    for noisy in ("mcp", "fastmcp", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    app = create_app(SkillStore(args.data))
    uvicorn.run(app, host=args.host, port=args.port, access_log=False, log_level="info")


if __name__ == "__main__":
    main()
