from multiprocessing import Process
from safe_pc.proxmox_auto_installer.back_end.server import main
from safe_pc.proxmox_auto_installer.scripts.build_css import build_css


def run_all():
    # simply run it do  not wait
    try:
        p1 = Process(target=build_css, args=[["", "dev"]])
        p1.start()
        p2 = Process(target=main)
        p2.start()
    except Exception as e:
        print(f"Error starting development server: {e}")
        exit(code=1)

    try:
        p1.join()
        p2.join()
    except KeyboardInterrupt:
        print("Development server stopped by user")
        p1.terminate()
        p2.terminate()


if __name__ == "__main__":
    run_all()
