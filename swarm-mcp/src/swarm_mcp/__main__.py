"""Точка входа: python -m swarm_mcp"""

import asyncio

from .server import main

asyncio.run(main())
