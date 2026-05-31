import subprocess
import shutil
import os

if __name__ == "__main__":
    if not os.path.exists('./dist/baldrick'):
        os.makedirs('./dist/baldrick')
    if os.path.exists('./dist/baldrick'):
        shutil.rmtree('./dist/baldrick')
    if os.path.exists('./dist/baldrick.zip'):
        os.remove('./dist/baldrick.zip')
    subprocess.call(r"PyInstaller baldrick.spec")
    os.mkdir('./dist/baldrick/routes')
    os.mkdir('./dist/baldrick/fuel_maps')
    shutil.copy('./routes/example_route_file.yaml', 'dist/baldrick/routes/example_route_file.yaml')
    shutil.copy('./fuel_maps/example_fuel_map.yaml', 'dist/baldrick/fuel_maps/example_fuel_map.yaml')
    shutil.copy('config.yaml', 'dist/baldrick/config.yaml')