import logging

import uvicorn

from auth_template.config import Config
from auth_template.main import create_app


def main() -> None:
    config = Config()
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    uvicorn.run(
        create_app(config),
        host=config.http.host,
        port=config.http.port,
        limit_concurrency=config.http.concurrency,
        timeout_keep_alive=5,
        proxy_headers=False,
        access_log=False,
    )


if __name__ == '__main__':
    main()
