import asyncio
import aiohttp
import aiofiles
import urllib.parse as up
import sys
import os
import subprocess

from tqdm import tqdm

async def download_ts_file(session, url, folder, log=sys.stdout, retries=3):
    for _ in range(retries):
        try:
            async with session.get(url) as response:
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                ts_content = bytearray()
                with tqdm(total=total_size, unit='B', unit_scale=True, desc=url.split('/')[-1], leave=False, file=log) as pbar:
                    async for chunk in response.content.iter_any():  # iter_any() allows streaming mode
                        ts_content.extend(chunk)
                        downloaded += len(chunk)
                        pbar.update(len(chunk))
                return ts_content
        except aiohttp.ClientError as e:
            print(f"Error downloading {url}: {e}")
            if retries == 0:
                raise
            retries -= 1
            await asyncio.sleep(1)  # Wait before retrying
    return None

async def concatenate_ts_files(ts_files, output_file):
    with open('filelist.txt', 'w') as filelist:
        for ts_file in ts_files:
            filelist.write(f"file '{ts_file}'\n")
    subprocess.run(['ffmpeg', '-f', 'concat', '-safe', '0', '-i', 'filelist.txt', '-c', 'copy', output_file])
    os.remove('filelist.txt')

async def process_m3u8(session, url, fname, folder, log=sys.stdout):
    async with session.get(url) as response:
        m3u8_content = await response.text()
        ts_files = []
        tasks = []
        count = 0  # Counter for file numbering
        for line in m3u8_content.split("\n"):
            if line.startswith("#") or not line.strip():
                continue
            full_url = up.urljoin(url, line.strip())
            if ".ts" in full_url:
                task = asyncio.create_task(download_ts_file(session, full_url, folder, log=log))
                tasks.append(task)
                count += 1
        ts_contents = await asyncio.gather(*tasks)
        for i, ts_content in enumerate(ts_contents):
            ts_filename = f"{folder}/{i}.ts"  # Save ts file in folder
            async with aiofiles.open(ts_filename, 'wb') as f:
                await f.write(ts_content)
            ts_files.append(ts_filename)
        await concatenate_ts_files(ts_files, fname)

async def download_m3u8(url, fname, folder):
    async with aiohttp.ClientSession() as session:
        await process_m3u8(session, url, fname, folder)

async def main():
    urls_file = "urls.txt"
    with open(urls_file, 'r') as f:
        urls = f.readlines()
    for i, url in enumerate(urls):
        url = url.strip()
        folder = f"{i}"  # Create folder for each url
        os.makedirs(folder, exist_ok=True)
        fname = f"{i}.mp4"  # Output mp4 file name based on index
        await download_m3u8(url, fname, folder)

if __name__ == "__main__":
    asyncio.run(main())
