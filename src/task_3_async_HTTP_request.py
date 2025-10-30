import asyncio
import json
from typing import Dict, List

import aiohttp


async def fetch_urls(urls: List[str], file_path: str) -> Dict[str, int]:
    semaphore = asyncio.Semaphore(5)
    timeout = aiohttp.ClientTimeout(total=10)

    async def fetch_one(url: str, session: aiohttp.ClientSession) -> tuple[str, int]:
        async with semaphore:
            try:
                async with session.get(url) as resp:
                    return url, resp.status
            except (asyncio.TimeoutError, aiohttp.ClientError, Exception):
                return url, 0

    async with aiohttp.ClientSession(timeout=timeout) as session:
        tasks = [asyncio.create_task(fetch_one(url, session)) for url in urls]
        pairs = await asyncio.gather(*tasks)

    results = {url: code for url, code in pairs}

    with open(file_path, "w", encoding="utf-8") as file:
        for url in urls:
            res = {"url": url, "status_code": results[url]}
            file.write(json.dumps(res, ensure_ascii=False) + "\n")

    return results


if __name__ == "__main__":
    urls = [
        "https://example.com",
        "https://httpbin.org/status/404",
        "https://nonexistent.url",
    ]
    asyncio.run(fetch_urls(urls, "./results.jsonl"))
