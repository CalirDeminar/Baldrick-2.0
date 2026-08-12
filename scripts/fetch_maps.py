"""Download shareable map assets from a GitHub Release."""
from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
import zipfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_REPO = "CalirDeminar/Baldrick-2.0"
MAPS_ASSET_PATTERN = re.compile(r"^baldrick-maps-.*\.zip$", re.IGNORECASE)


def _api_get(url: str) -> dict | list:
    request = Request(url, headers={"Accept": "application/vnd.github+json"})
    with urlopen(request) as response:
        return json.load(response)


def _download(url: str, dest: Path) -> None:
    request = Request(url, headers={"Accept": "application/octet-stream"})
    with urlopen(request) as response, dest.open("wb") as out:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)


def resolve_release(repo: str, tag: str | None) -> dict:
    if tag:
        return _api_get(f"https://api.github.com/repos/{repo}/releases/tags/{tag}")
    return _api_get(f"https://api.github.com/repos/{repo}/releases/latest")


def find_maps_asset(release: dict) -> dict:
    for asset in release.get("assets", []):
        name = asset.get("name", "")
        if MAPS_ASSET_PATTERN.match(name):
            return asset
    asset_names = ", ".join(asset.get("name", "") for asset in release.get("assets", [])) or "(none)"
    raise RuntimeError(
        f"No baldrick-maps-*.zip asset found in release {release.get('tag_name', '?')}. Assets: {asset_names}"
    )


def extract_maps_zip(zip_path: Path, output_dir: Path) -> None:
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.namelist():
            if member.endswith("/"):
                continue
            if not member.startswith("map_data/"):
                raise RuntimeError(f"Unexpected path in maps zip: {member}")
            target = output_dir.parent / member
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member) as src, target.open("wb") as dst:
                dst.write(src.read())


def fetch_maps(*, repo: str, tag: str | None, output_dir: Path) -> Path:
    release = resolve_release(repo, tag)
    asset = find_maps_asset(release)
    asset_name = asset["name"]
    download_url = asset["browser_download_url"]

    with tempfile.TemporaryDirectory() as tmp:
        zip_path = Path(tmp) / asset_name
        print(f"Downloading {asset_name} from {release.get('tag_name', 'release')}...")
        _download(download_url, zip_path)
        extract_maps_zip(zip_path, output_dir)

    print(f"Extracted shareable maps into {output_dir.resolve()}")
    return output_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch shareable map assets from a GitHub Release.")
    parser.add_argument("--repo", default=DEFAULT_REPO, help=f"GitHub repo (default: {DEFAULT_REPO})")
    parser.add_argument("--tag", default=None, help="Release tag (default: latest release)")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "map_data",
        help="Destination map_data directory (default: repo map_data/)",
    )
    args = parser.parse_args()

    try:
        fetch_maps(repo=args.repo, tag=args.tag, output_dir=args.output_dir)
    except (HTTPError, URLError, RuntimeError, zipfile.BadZipFile) as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
