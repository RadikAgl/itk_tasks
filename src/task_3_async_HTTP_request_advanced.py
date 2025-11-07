import asyncio
import json
import logging
import random
from asyncio import Lock, Queue
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import aiofiles
import aiohttp
from aiofiles.threadpool.text import AsyncTextIOWrapper

logging.basicConfig(filename="app.log", encoding="utf-8", level=logging.INFO)


def parse_and_dump(url: str, body: bytes) -> str:
    data = json.loads(body)
    return json.dumps(
        {"url": url, "content": data}, ensure_ascii=False, separators=(",", ":")
    )


async def fetch_url(
    session: aiohttp.ClientSession,
    queue: Queue[Optional[str]],
    write_lock: Lock,
    out_file: AsyncTextIOWrapper,
    json_executor: ThreadPoolExecutor,
    max_retries: int = 3,
):
    loop = asyncio.get_running_loop()
    while True:
        url = await queue.get()
        try:
            if url is None:
                break

            for attempt in range(max_retries):
                try:
                    async with session.get(
                        url, allow_redirects=True, max_redirects=10
                    ) as resp:
                        resp.raise_for_status()
                        body = await resp.read()
                        line = await loop.run_in_executor(
                            json_executor, parse_and_dump, url, body
                        )

                        async with write_lock:
                            await out_file.write(line + "\n")

                        break

                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    logging.error(
                        f"url: {url}. Ошибка соединения: {e}. Попытка {attempt + 1} не удалась.",
                        exc_info=True,
                    )
                    await asyncio.sleep(0.01 * (2**attempt) + random.random())

                except (aiohttp.ContentTypeError, json.JSONDecodeError) as e:
                    logging.error(
                        f"url: {url}. Неверный формат данных. {e}", exc_info=True
                    )
                    break

                except (
                    Exception
                ) as e:  # тут я не стал делать повторные попытки. Исключения, требующие
                    # повторных запросов можно добавить в верхний except
                    logging.error(
                        f"url: {url}. Непредвиденная ошибка: {e}. Попытка {attempt + 1} не удалась.",
                        exc_info=True,
                    )
                    break

        finally:
            queue.task_done()


async def prepare_url(input_file: str, queue: Queue[Optional[str]], concurrency: int):
    async with aiofiles.open(input_file, mode="r", encoding="utf-8") as in_file:
        async for line in in_file:
            url = line.strip()
            if not url:
                continue
            await queue.put(url)
    for _ in range(concurrency):
        await queue.put(None)


async def fetch_urls(
    input_file: str, output_file: str = "result.jsonl", max_concurrent: int = 5
):
    write_lock = Lock()
    queue = asyncio.Queue(maxsize=max_concurrent)
    producers = [asyncio.create_task(prepare_url(input_file, queue, max_concurrent))]

    connector = aiohttp.TCPConnector(
        limit=max_concurrent, limit_per_host=max_concurrent
    )
    timeout = aiohttp.ClientTimeout(
        total=10
    )  # уменьшил, чтобы долго не ждать завершения программы

    json_executor = ThreadPoolExecutor(max_workers=4)
    try:
        async with (
            aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers={"Accept": "application/json"},
            ) as session,
            aiofiles.open(output_file, mode="a", encoding="utf-8") as out_file,
        ):
            consumers = [
                asyncio.create_task(
                    fetch_url(session, queue, write_lock, out_file, json_executor)
                )
                for _ in range(max_concurrent)
            ]

            await asyncio.gather(*producers)
            await queue.join()
            await asyncio.gather(*consumers, return_exceptions=True)
    finally:
        json_executor.shutdown(wait=True, cancel_futures=True)


if __name__ == "__main__":
    asyncio.run(fetch_urls("./urls.txt", "./results2.jsonl", 5))
