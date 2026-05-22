import os
import sys
import urllib.parse

from curl_cffi import requests
from bs4 import BeautifulSoup

BASE = os.environ.get("ANNAS_BASE", "https://annas-archive.pk")


TYPE_PARAMS = {
    "book": {},
    "fiction": {"content": "book_fiction"},
    "nonfiction": {"content": "book_nonfiction"},
    "magazine": {"content": "magazine"},
    "comic": {"content": "book_comic"},
    "article": {"src": "scihub"},
}


def search(query, type="book", limit=10):
    params = {"q": query, **TYPE_PARAMS.get(type, {})}
    r = requests.get(
        f"{BASE}/search?{urllib.parse.urlencode(params)}",
        impersonate="chrome",
        timeout=30,
    )
    r.raise_for_status()
    seen, out = set(), []
    for a in BeautifulSoup(r.text, "html.parser").select("a[href^='/md5/']"):
        md5 = a["href"].removeprefix("/md5/")
        title = a.get_text(strip=True)
        if md5 and title and md5 not in seen:
            seen.add(md5)
            out.append((md5, title))
            if len(out) >= limit:
                break
    return out


def download(md5):
    key = os.environ["ANNAS_KEY"]
    meta = requests.get(
        f"{BASE}/dyn/api/fast_download.json",
        params={"md5": md5, "key": key},
        impersonate="chrome",
        timeout=30,
    ).json()
    if not meta.get("download_url"):
        sys.exit(f"error: {meta}")
    url = meta["download_url"]
    name = urllib.parse.unquote(url.rsplit("/", 1)[-1]) or f"{md5}.bin"

    r = requests.get(url, impersonate="chrome", timeout=300, stream=True)
    r.raise_for_status()
    with open(name, "wb") as f:
        for chunk in r.iter_content(65536):
            f.write(chunk)

    info = meta.get("account_fast_download_info", {})
    size = os.path.getsize(name)
    print(f"{name}  ({size:,} bytes, {info.get('downloads_left', '?')} downloads left today)")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(f"usage: aa.py search [--type {'|'.join(TYPE_PARAMS)}] <query>  |  aa.py get <md5>")
    cmd = sys.argv[1]
    if cmd == "search":
        args = sys.argv[2:]
        type = "book"
        if "--type" in args:
            i = args.index("--type")
            type = args[i + 1]
            args = args[:i] + args[i + 2:]
        if type not in TYPE_PARAMS:
            sys.exit(f"unknown --type {type!r}; options: {', '.join(TYPE_PARAMS)}")
        for md5, title in search(" ".join(args), type=type):
            print(f"{md5}  {title}")
    elif cmd == "get":
        download(sys.argv[2])
    else:
        sys.exit(f"unknown command: {cmd}")
