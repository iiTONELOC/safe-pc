from asyncio import sleep
from utm.utils.utils import send_key_to_pexpect_proc, strip_ansi_escape_sequences  # type: ignore

from pexpect import spawn as pe_spawn, TIMEOUT, EOF  # type: ignore


async def drive_installer(child: pe_spawn, root_password: str = "UseBetterPassword!23") -> None:  # type: ignore
    buffer = ""
    pwd_confirmed = False
    while True:
        try:
            # Output is inconsistent, read it in chunks in a non-blocking manner
            chunk = child.read_nonblocking(size=2048, timeout=2)  # type: ignore
            buffer += chunk  # type: ignore
            screen_buffer = strip_ansi_escape_sequences(buffer)  # type: ignore

            if "Welcome to the OPNSense installer" in screen_buffer:
                send_key_to_pexpect_proc("enter", child)
                buffer = ""

            elif "login:" in screen_buffer:
                child.send("installer\r")
                buffer = ""

            elif (
                "Choose one of the following tasks" in screen_buffer
                or "stripe  Stripe - No Redundancy" in screen_buffer
                or "Keymap Selection" in screen_buffer
            ):
                await sleep(2)
                send_key_to_pexpect_proc("enter", child)
                buffer = ""

            elif "Please select one or more disks to create a zpool" in screen_buffer:
                await sleep(2)
                if "*" not in screen_buffer:
                    child.send(" ")
                    await sleep(0.3)
                send_key_to_pexpect_proc("enter", child)
                buffer = ""

            elif "Password:" in screen_buffer and "Root Password" not in screen_buffer:
                child.send("opnsense\r")
                buffer = ""

            elif "Last Chance!" in screen_buffer:
                await sleep(1)
                send_key_to_pexpect_proc("tab", child)
                await sleep(0.5)
                send_key_to_pexpect_proc("enter", child)
                buffer = ""

            elif "Root Password" in screen_buffer and "Change root password" in screen_buffer:
                await sleep(1)
                if not pwd_confirmed:
                    send_key_to_pexpect_proc("enter", child)
                    await sleep(1)
                    child.send(root_password + "\r")
                    await sleep(1)
                    child.send(root_password + "\r")
                    pwd_confirmed = True
                    buffer = ""
                else:
                    send_key_to_pexpect_proc("down", child)
                    await sleep(0.5)
                    send_key_to_pexpect_proc("enter", child)
                    await sleep(0.5)
                    send_key_to_pexpect_proc("enter", child)
                    buffer = ""

            elif "The installation finished successfully" in screen_buffer:
                await sleep(1)
                send_key_to_pexpect_proc("ctrl_c", child)
                buffer = ""
                break

        except TIMEOUT:
            continue
        except EOF:
            break
