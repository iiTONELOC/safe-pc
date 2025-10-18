# generate a build of the project for the proxmox environment
import sys
import subprocess
from pathlib import Path


def main():
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

    # copy ansible into dist
    subprocess.run(["cp", "-r", str(project_root / "ansible"), str(safe_pc_dist / "ansible")])

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

    # move the toml from the root of dist/safe_pc/utm to dist/safe_pc
    subprocess.run(
        [
            "mv",
            str(src_dist / "utm" / "pyproject.toml"),
            str(safe_pc_dist / "pyproject.toml"),
        ]
    )

    print(f"Build completed. Distribution available at: {dist_dir / 'safe_pc'}")


if __name__ == "__main__":
    main()
