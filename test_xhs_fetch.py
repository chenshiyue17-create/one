import asyncio
import httpx
from lxml.etree import HTML

async def test():
    url = "https://www.xiaohongshu.com/explore/65f69e6b0000000012012674" # Example public note
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "referer": "https://www.xiaohongshu.com/"
    }
    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
        resp = await client.get(url)
        print(f"Status: {resp.status_code}")
        html_tree = HTML(resp.text)
        scripts = html_tree.xpath("//script/text()")
        for script in scripts:
            if "window.__INITIAL_STATE__" in script:
                print("Found window.__INITIAL_STATE__")
                print(script[:100])
            if "initial-state" in script:
                print("Found initial-state")

if __name__ == "__main__":
    asyncio.run(test())
