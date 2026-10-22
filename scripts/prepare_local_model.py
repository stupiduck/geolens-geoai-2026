"""Download a pinned Qwen GGUF and current CPU llama.cpp release locally; never touches servers."""
import argparse
import hashlib
import json
import platform
import urllib.request
import zipfile
from pathlib import Path

MODELS = {
    "2b": ("unsloth/Qwen3.5-2B-GGUF", "f6d5376be1edb4d416d56da11e5397a961aca8ae", "Qwen3.5-2B-Q4_K_M.gguf", "aaf42c8b7c3cab2bf3d69c355048d4a0ee9973d48f16c731c0520ee914699223"),
    "0.8b": ("unsloth/Qwen3.5-0.8B-GGUF", "6ab461498e2023f6e3c1baea90a8f0fe38ab64d0", "Qwen3.5-0.8B-Q4_K_M.gguf", "bd258782e35f7f458f8aced1adc053e6e92e89bc735ba3be89d38a06121dc517"),
}


def download(url, path, expected_size=None):
    if path.exists() and (expected_size is None or path.stat().st_size==expected_size):
        return
    partial = path.with_suffix(path.suffix + ".partial")
    if path.exists() and not partial.exists():
        path.replace(partial)
    offset = partial.stat().st_size if partial.exists() else 0
    request = urllib.request.Request(url, headers={"User-Agent": "GeoLens-development/0.1", **({"Range": f"bytes={offset}-"} if offset else {})})
    with urllib.request.urlopen(request, timeout=60) as source:
        mode = "ab" if offset and source.status == 206 else "wb"
        with partial.open(mode) as target:
            while chunk := source.read(1024 * 1024):
                target.write(chunk)
    if expected_size and partial.stat().st_size!=expected_size:
        raise RuntimeError(f"Incomplete download: {partial.stat().st_size}/{expected_size} bytes; rerun to resume")
    partial.replace(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=MODELS, default="2b")
    args = parser.parse_args()
    directory = Path("models")
    directory.mkdir(exist_ok=True)
    repo, revision, name, sha = MODELS[args.model]
    path = directory / name
    print("Downloading pinned model:", repo, flush=True)
    download(f"https://huggingface.co/{repo}/resolve/{revision}/{name}?download=true", path, 1280835840 if args.model=="2b" else 532517120)
    digest = hashlib.file_digest(path.open("rb"), "sha256").hexdigest()
    if digest != sha:
        raise RuntimeError("Model checksum mismatch; refusing to serve")
    suffix = "bin-win-cpu-x64.zip" if platform.system() == "Windows" else "bin-ubuntu-x64.tar.gz"
    with urllib.request.urlopen("https://api.github.com/repos/ggml-org/llama.cpp/releases?per_page=8", timeout=30) as response:
        releases = json.load(response)
    # /latest may point to a source-only semantic-version release; select a CPU binary release.
    release,asset=next((r,a) for r in releases for a in r["assets"] if a["name"].endswith(suffix))
    binary = directory / asset["name"]
    download(asset["browser_download_url"], binary)
    runtime = directory / "runtime"
    runtime.mkdir(exist_ok=True)
    if binary.suffix == ".zip":
        with zipfile.ZipFile(binary) as archive:
            archive.extractall(runtime)
    else:
        import tarfile
        with tarfile.open(binary) as archive:
            archive.extractall(runtime, filter="data")
    manifest = {"quant_repo": repo, "quant_revision": revision, "filename": name, "sha256": sha, "runtime_release": release["tag_name"], "runtime_asset": asset["name"]}
    (directory / "local-manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest), flush=True)


if __name__ == "__main__":
    main()
