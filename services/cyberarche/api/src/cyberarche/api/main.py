from __future__ import annotations

import uvicorn

from cyberarche.api.bootstrap import create_app


def run() -> None:
    uvicorn.run(create_app(), host="0.0.0.0", port=8000)


if __name__ == "__main__":
    run()
