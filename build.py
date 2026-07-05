"""Build the distributable PyInstaller bundle.

Produces ``dist/baldrick`` containing ``baldrick.exe`` plus the user-editable
files (``config.yaml``, ``routes/``, ``fuel_maps/``) alongside it. The large
read-only ``map_data`` folder is bundled inside the executable's ``_internal``
directory by ``baldrick.spec``.
"""
import os
import shutil
import subprocess

DIST = os.path.join("dist", "baldrick")

if __name__ == "__main__":
    if os.path.exists(DIST):
        shutil.rmtree(DIST)
    if os.path.exists("./dist/baldrick.zip"):
        os.remove("./dist/baldrick.zip")

    subprocess.check_call(["pyinstaller", "baldrick.spec"])

    os.makedirs(os.path.join(DIST, "routes"), exist_ok=True)
    os.makedirs(os.path.join(DIST, "fuel_maps"), exist_ok=True)

    shutil.copy("./routes/example_route_file.yaml", os.path.join(DIST, "routes", "example_route_file.yaml"))
    shutil.copy("./fuel_maps/example_fuel_map.yaml", os.path.join(DIST, "fuel_maps", "example_fuel_map.yaml"))
    shutil.copy("config.yaml", os.path.join(DIST, "config.yaml"))

    print(f"Build complete: {DIST}")
