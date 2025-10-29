import asyncio
import aiohttp
import json


async def fetch_url(
        session: aiohttp.ClientSession,
        url: str,
        semaphore: asyncio.Semaphore
) -> dict:
    async with semaphore:
        try:
            timeout = aiohttp.ClientTimeout(total=300, connect=10)

            async with session.get(url, timeout=timeout) as response:
                response.raise_for_status()

                content = await response.json()
                print(url)
                return {
                    "url": url,
                    "content": content
                }

        except asyncio.TimeoutError:
            return {"url": url, "error": "timeout"}

        except aiohttp.ClientError as e:
            return {"url": url, "error": f"client_error: {str(e)}"}

        except json.JSONDecodeError as e:
            return {"url": url, "error": "invalid_json"}

        except Exception as e:
            return {"url": url, "error": f"unexpected: {str(e)}"}


async def fetch_urls(
        input_file: str,
        output_file: str = "result.jsonl",
        max_concurrent: int = 5,
        chunk_size: int = 100
):
    urls = []
    with open(input_file, 'r', encoding='utf-8') as file:
        urls = [line.strip() for line in file if line.strip()]

    total_urls = len(urls)

    semaphore = asyncio.Semaphore(max_concurrent)

    connector = aiohttp.TCPConnector(
        limit=max_concurrent,
        limit_per_host=2,
        ttl_dns_cache=300
    )

    timeout = aiohttp.ClientTimeout(total=600)

    async with aiohttp.ClientSession(
            connector=connector,
            timeout=timeout
    ) as session:

        for i in range(0, total_urls, chunk_size):
            chunk_urls = urls[i:i + chunk_size]

            tasks = [
                fetch_url(session, url, semaphore)
                for url in chunk_urls
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            with open(output_file, 'a', encoding='utf-8') as file:
                for result in results:
                    print(result)
                    if isinstance(result, Exception):
                        continue

                    if "error" not in result:
                        json_line = json.dumps(result, ensure_ascii=False)
                        file.write(json_line + '\n')


if __name__ == "__main__":
    asyncio.run(fetch_urls("./urls.txt", "./results2.jsonl", 5, 2))
