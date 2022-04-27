import requests
import csv
from time import sleep
import mimetypes
import aiohttp
import asyncio

limit = 10


async def download_images():
    async with asyncio.Semaphore(limit):
        async with aiohttp.ClientSession() as session:
            with open('Image.csv', 'r', encoding='utf-8-sig') as input_file:
                reader = csv.DictReader(input_file)
                for row in reader:
                    async with session.get(url=row['Image URL']) as response:
                        content = await response.read()
                        extension = mimetypes.guess_extension(response.headers["Content-Type"])
                        with open(f'Downloads/{row["Lot #"]}{extension}', 'wb') as image_file:
                            image_file.write(content)


async def main():
    await download_images()


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
