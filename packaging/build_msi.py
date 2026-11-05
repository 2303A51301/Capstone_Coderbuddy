"""Build a self-contained, per-user Windows x64 MSI without personal files."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request
import uuid
import xml.etree.ElementTree as ET
import zipfile


ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build" / "windows"
CACHE = BUILD / "downloads"
PAYLOAD = BUILD / "payload"
DIST = ROOT / "dist"
NS = "http://schemas.microsoft.com/wix/2006/wi"
ET.register_namespace("", NS)


def download(url: str, name: str) -> Path:
    target = CACHE / name
    if not target.exists():
        print(f"Downloading {name}", flush=True)
        partial = target.with_suffix(".partial")
        urllib.request.urlretrieve(url, partial)
        partial.replace(target)
    return target


def element(parent: ET.Element, tag: str, **attributes: str) -> ET.Element:
    return ET.SubElement(parent, f"{{{NS}}}{tag}", attributes)


def main() -> None:
    if sys.platform != "win32" or sys.maxsize <= 2**32:
        raise RuntimeError("Build on 64-bit Windows with Python 3.12.")
    if PAYLOAD.exists():
        raise RuntimeError(f"Payload already exists: {PAYLOAD}. Use a fresh build directory.")
    CACHE.mkdir(parents=True, exist_ok=True)
    DIST.mkdir(exist_ok=True)
    PAYLOAD.mkdir()
    runtime = PAYLOAD / "runtime"
    runtime.mkdir()
    python_zip = download(
        "https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip",
        "python-3.12.10-embed-amd64.zip",
    )
    with zipfile.ZipFile(python_zip) as archive:
        archive.extractall(runtime)
    (runtime / "python312._pth").write_text(
        "python312.zip\n.\nLib\\site-packages\n..\nimport site\n", encoding="ascii"
    )
    subprocess.run([
        sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
        "--no-compile", "--target", str(runtime / "Lib" / "site-packages"),
        "-r", str(ROOT / "requirements.txt"),
    ], check=True)
    node_version = "v24.19.0"
    node = download(f"https://nodejs.org/dist/{node_version}/win-x64/node.exe", "node.exe")
    checksums = download(f"https://nodejs.org/dist/{node_version}/SHASUMS256.txt", "node-SHASUMS256.txt")
    expected = next(
        line.split()[0] for line in checksums.read_text().splitlines()
        if line.split()[-1] == "win-x64/node.exe"
    )
    if hashlib.sha256(node.read_bytes()).hexdigest() != expected:
        raise RuntimeError("Node.js checksum mismatch.")
    shutil.copy2(node, runtime / "node.exe")
    for folder in ("app", "static"):
        shutil.copytree(ROOT / folder, PAYLOAD / folder, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for filename in ("README.md", "LICENSE", ".env.example"):
        shutil.copy2(ROOT / filename, PAYLOAD / filename)
    shutil.copy2(ROOT / "packaging" / "launch.py", PAYLOAD / "launch.py")
    shutil.copy2(ROOT / "packaging" / "CoderBuddy.cmd", PAYLOAD / "CoderBuddy.cmd")
    notices = PAYLOAD / "THIRD_PARTY_NOTICES"
    notices.mkdir()
    license_url = f"https://raw.githubusercontent.com/nodejs/node/{node_version}/LICENSE"
    shutil.copy2(download(license_url, "NODE-LICENSE.txt"), notices / "NODE-LICENSE.txt")
    subprocess.run([str(runtime / "python.exe"), "-c", "import app.main, pytest, uvicorn; print('Bundled Python imports OK')"],
                   cwd=PAYLOAD, check=True, env={
                       **os.environ, "WORKSPACE_ROOT": str(BUILD / "smoke-workspace"),
                       "RUN_DATABASE": str(BUILD / "smoke-data" / "runs.sqlite3"),
                   })
    subprocess.run([str(runtime / "node.exe"), "--check", str(PAYLOAD / "static" / "app.js")], check=True)
    secret_names = (".env", "coderbuddy.sqlite3")
    if any(p.name in secret_names for p in PAYLOAD.rglob("*")):
        raise RuntimeError("Personal configuration/data must not be packaged.")
    request = urllib.request.Request(
        "https://api.github.com/repos/wixtoolset/wix3/releases/tags/wix3141rtm",
        headers={"User-Agent": "CoderBuddy-MSI-builder"},
    )
    with urllib.request.urlopen(request) as response:
        release = json.load(response)
    wix_url = next(a["browser_download_url"] for a in release["assets"] if a["name"] == "wix314-binaries.zip")
    wix = BUILD / "wix"
    wix.mkdir(exist_ok=True)
    with zipfile.ZipFile(download(wix_url, "wix314-binaries.zip")) as archive:
        archive.extractall(wix)
    tree = ET.Element(f"{{{NS}}}Wix")
    product = element(tree, "Product", Id="*", Name="CoderBuddy-CaPStone",
                      Language="1033", Version="3.0.0", Manufacturer="CoderBuddy-CaPStone",
                      UpgradeCode="413B470E-6FD0-4FBC-A140-492EB00A34DE")
    element(product, "Package", InstallerVersion="500", Compressed="yes", InstallScope="perUser", Platform="x64")
    element(product, "MajorUpgrade", DowngradeErrorMessage="A newer version is already installed.")
    element(product, "MediaTemplate", EmbedCab="yes")
    target = element(product, "Directory", Id="TARGETDIR", Name="SourceDir")
    local = element(target, "Directory", Id="LocalAppDataFolder")
    programs = element(local, "Directory", Id="ProgramsFolder", Name="Programs")
    install = element(programs, "Directory", Id="INSTALLFOLDER", Name="CoderBuddy-CaPStone")
    menu = element(target, "Directory", Id="ProgramMenuFolder")
    menu_app = element(menu, "Directory", Id="ApplicationProgramsFolder", Name="CoderBuddy-CaPStone")
    directories = {Path("."): install}
    components = []
    for path in sorted(PAYLOAD.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(PAYLOAD)
        parent = Path(".")
        for part in relative.parts[:-1]:
            child = parent / part
            if child not in directories:
                directory_id = "D" + hashlib.sha256(str(child).encode()).hexdigest()[:24]
                directories[child] = element(directories[parent], "Directory", Id=directory_id, Name=part)
            parent = child
        identity = hashlib.sha256(str(relative).encode()).hexdigest()[:24]
        component_id = "C" + identity
        component = element(directories[parent], "Component", Id=component_id, Guid=str(uuid.uuid5(uuid.NAMESPACE_URL, "coderbuddy/" + relative.as_posix())), Win64="yes")
        element(component, "File", Id="F" + identity, Source=str(path), KeyPath="yes")
        components.append(component_id)
    shortcut = element(menu_app, "Component", Id="StartMenuShortcut", Guid="48231683-42CE-4988-9C3F-17428B6BA288", Win64="yes")
    element(shortcut, "Shortcut", Id="LaunchShortcut", Name="CoderBuddy-CaPStone", Target="[INSTALLFOLDER]CoderBuddy.cmd", WorkingDirectory="INSTALLFOLDER")
    element(shortcut, "RemoveFolder", Id="RemoveMenuFolder", On="uninstall")
    element(shortcut, "RegistryValue", Root="HKCU", Key="Software\\CoderBuddy-CaPStone", Name="installed", Type="integer", Value="1", KeyPath="yes")
    components.append("StartMenuShortcut")
    feature = element(product, "Feature", Id="Complete", Title="CoderBuddy-CaPStone", Level="1")
    for component_id in components:
        element(feature, "ComponentRef", Id=component_id)
    source = BUILD / "installer.wxs"
    ET.ElementTree(tree).write(source, encoding="utf-8", xml_declaration=True)
    obj = BUILD / "installer.wixobj"
    output = DIST / "CoderBuddy-CaPStone-3.0.0-x64.msi"
    subprocess.run([str(wix / "candle.exe"), "-nologo", "-out", str(obj), str(source)], check=True)
    subprocess.run([str(wix / "light.exe"), "-nologo", "-sval", "-out", str(output), str(obj)], check=True)
    print(f"Created {output} ({output.stat().st_size / 1024 / 1024:.1f} MB)")


if __name__ == "__main__":
    main()
