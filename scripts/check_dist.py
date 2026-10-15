"""Build-output contract and isolated wheel/sdist installation checks."""

from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import venv
import zipfile

from smoke import run


root = Path(__file__).resolve().parents[1]
wheels = list((root / "dist").glob("*.whl"))
sources = list((root / "dist").glob("*.tar.gz"))
assert len(wheels) == len(sources) == 1, "dist must contain one wheel and one sdist"
required = {"README.md", "LICENSE", "pyproject.toml", "docs/contracts.md", "docs/research.md", "docs/positioning.md", "tests/test_acceptance.py", "scripts/smoke.py", "src/rankreserve/examples/design.csv"}
with tarfile.open(sources[0]) as archive:
    names = {"/".join(Path(member.name).parts[1:]) for member in archive.getmembers()}
    assert required <= names, required - names
with zipfile.ZipFile(wheels[0]) as archive:
    names = archive.namelist()
    assert "rankreserve/examples/design.csv" in names
    info = archive.read(next(name for name in names if name.endswith(".dist-info/METADATA"))).decode()
    assert "Requires-Dist:" not in info, "runtime must have no third-party requirements"
for artifact in (wheels[0], sources[0]):
    with tempfile.TemporaryDirectory(prefix="rankreserve-install-") as temporary:
        directory = Path(temporary)
        venv.create(directory / "venv", with_pip=True)
        python = directory / "venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        subprocess.run([str(python), "-m", "pip", "install", "--no-deps", str(artifact)], cwd=directory, check=True, timeout=180)
        run(python)
        print(f"Verified isolated installation of {artifact.name}")
