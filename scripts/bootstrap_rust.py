"""Prepare an isolated official Rust toolchain when the host installation is broken."""
import hashlib
import pathlib
import shutil
import tarfile
import tomllib
import urllib.request

VERSION = "1.97.1"
TARGET = "x86_64-pc-windows-msvc"
ROOT = pathlib.Path(__file__).resolve().parents[1] / ".tools"


def main():
    ROOT.mkdir(exist_ok=True)
    with urllib.request.urlopen(f"https://static.rust-lang.org/dist/channel-rust-{VERSION}.toml", timeout=60) as response:
        manifest = tomllib.loads(response.read().decode())
    destination = ROOT / "rust"
    destination.mkdir(exist_ok=True)
    for name in ("rustc", "rust-std", "cargo"):
        package = manifest["pkg"][name]["target"][TARGET]
        archive = ROOT / f"{name}-{VERSION}.tar.xz"
        if not archive.exists():
            print(f"Downloading {name} {VERSION}", flush=True)
            with urllib.request.urlopen(package["xz_url"], timeout=120) as response, archive.open("wb") as output:
                shutil.copyfileobj(response, output)
        if hashlib.file_digest(archive.open("rb"), "sha256").hexdigest() != package["xz_hash"]:
            raise RuntimeError(f"Checksum mismatch: {archive}")
        print(f"Verified {name}; extracting", flush=True)
        component = f"rust-std-{TARGET}" if name == "rust-std" else name
        with tarfile.open(archive) as bundle:
            for member in bundle.getmembers():
                parts = pathlib.PurePosixPath(member.name).parts
                if len(parts) < 3 or parts[1] != component or not member.isfile():
                    continue
                relative = pathlib.Path(*parts[2:])
                target = (destination / relative).resolve()
                if not target.is_relative_to(destination.resolve()):
                    raise RuntimeError("Invalid archive path")
                target.parent.mkdir(parents=True, exist_ok=True)
                with bundle.extractfile(member) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)
    print(f"Rust ready: {destination}", flush=True)


if __name__ == "__main__":
    main()
