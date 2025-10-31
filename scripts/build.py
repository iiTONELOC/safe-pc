# generate a build of the project for the proxmox environment

import sys
import subprocess
from os import getenv
from pathlib import Path


DEV_PROX_USER = getenv("SAFE_PC_DEV_PROX_USER", "root")
DEV_PROX_HOST = getenv("SAFE_PC_DEV_PROX_HOST", "10.0.2.238")


def main(dev: bool = False):
    print("Building UTM for Proxmox...")
    # move to the root of the project
    project_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(project_root))
    # create the dist folder if it doesn't exist
    dist_dir = project_root / "dist"
    if not dist_dir.exists():
        dist_dir.mkdir(parents=True, exist_ok=True)

    # make a safe_pc directory in dist
    safe_pc_dist = dist_dir / "safe_pc"
    if safe_pc_dist.exists():
        subprocess.run(["rm", "-rf", str(safe_pc_dist)])
    safe_pc_dist.mkdir(parents=True, exist_ok=True)

    # create a src directory in dist/safe_pc
    src_dist = safe_pc_dist / "src"
    src_dist.mkdir(parents=True, exist_ok=True)

    # copy utm only into dist/src
    subprocess.run(
        [
            "rsync",
            "-a",
            "--exclude",
            "__pycache__",
            str(project_root / "src" / "utm") + "/",
            str(src_dist / "utm"),
        ]
    )

    # move the pyproject.toml and copy the opnsense config from the root of dist/safe_pc/utm to dist/safe_pc
    subprocess.run(["mv", str(src_dist / "utm" / "pyproject.toml"), str(safe_pc_dist / "pyproject.toml")])
    subprocess.run(["cp", str(project_root / "safety_config.xml"), str(safe_pc_dist)])

    # if dev flag is set, deploy to proxmox
    if dev:
        print("Deploying development build to Proxmox...")
        subprocess.run(
            [
                "scp",
                "-r",
                str(safe_pc_dist) + "/.",
                f"{DEV_PROX_USER}@{DEV_PROX_HOST}:/opt/safe_pc/",
            ]
        )

    # create a requirements.txt file in dist/safe_pc
    # read the pyproject.toml to get the dependencies

    requirements_file = safe_pc_dist / "requirements.txt"

    reqs = """
httpx>=0.28.1,<0.29.0
aiofiles>=24.1.0,<25.0.0
ansible>=12.1.0,<13.0.0
tqdm>=4.67.1,<5.0.0
pexpect>=4.9.0,<5.0.0
bcrypt>=5.0.0,<6.0.0
    """

    with open(requirements_file, "w") as f:
        f.write(reqs.strip() + "\n")

    print(f"Build completed. Distribution available at: {dist_dir / 'safe_pc'}")


def main_dev():
    main(dev=True)


if __name__ == "__main__":
    main(dev="--dev" in sys.argv)
