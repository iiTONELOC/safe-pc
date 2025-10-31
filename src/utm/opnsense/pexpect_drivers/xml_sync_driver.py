from asyncio import sleep
from logging import getLogger
from utm.utils.utils import strip_ansi_escape_sequences  # type: ignore
from utm.opnsense.pexpect_drivers.file_c_streamer import stream_file_in_chunks  # type: ignore
from pexpect import spawn as pe_spawn, TIMEOUT, EOF  # type: ignore


logger = getLogger("utm.opnsense.xml_sync_driver")
base_prefix = "[OPNSense XMLSync Driver] "


async def xml_template_sync_driver(child: pe_spawn, template: str, script: str) -> bool:  # type: ignore

    buffer = ""
    merged = False
    waiting_for_reboot = False

    # send enter first to get past any initial prompts and ensure we see the main screen
    child.send("\r")
    await sleep(1)
    while not merged:
        try:
            # Output is inconsistent, read it in chunks in a non-blocking manner
            chunk = child.read_nonblocking(size=2048, timeout=2)  # type: ignore
            buffer += chunk  # type: ignore
            screen_buffer = strip_ansi_escape_sequences(buffer)  # type: ignore

            if "login:" in screen_buffer:
                child.send("root\r")
                await sleep(1)
                child.send("UseBetterPassword!23\r")  # default password, will be changed
                buffer = ""
            elif "Enter an option:" in screen_buffer:
                # use the shell
                child.send("8")  # Shell
                await sleep(1)
                child.send("\r")
                buffer = ""
            elif "root@OPNsense:~ # " in screen_buffer and not merged and not waiting_for_reboot:
                # backup config
                child.sendline("cp /conf/config.xml /conf/config.xml.bak")
                await sleep(1)

                # send encoded config file in chunks
                await stream_file_in_chunks(
                    template,
                    "/tmp/safety_config_b64.tmp",
                    "/tmp/safety_config.xml",
                    child,
                )

                # send the merge script
                await stream_file_in_chunks(
                    script,
                    "/tmp/xml_merge_b64.tmp",
                    "/tmp/xml_merge.py",
                    child,
                )

                # run the merge script
                child.sendline("python3 /tmp/xml_merge.py")
                await sleep(1)
                child.expect_exact("Configuration merged successfully.", timeout=30)
                child.sendline("rm -f /tmp/safety_config.xml")
                await sleep(1)
                child.sendline("/usr/local/etc/rc.reload_all")
                child.expect("Syncing OpenVPN settings...done.", timeout=120)

                child.sendline("reboot")

                waiting_for_reboot = True
                buffer = ""
                merged = True
                # shouldn't be necessary, but explicitly break here
                break

        except TIMEOUT:
            continue
        except EOF:
            break
        except Exception as e:
            logger.error(f"Error during XML template sync: {e}")
            return False

    buffer = ""
    await sleep(20)
    while waiting_for_reboot:
        try:
            # Output is inconsistent, read it in chunks in a non-blocking manner
            chunk = child.read_nonblocking(size=2048, timeout=2)  # type: ignore
            buffer += chunk  # type: ignore
            screen_buffer = strip_ansi_escape_sequences(buffer)  # type: ignore

            if "login:" in screen_buffer:
                child.send("root\r")
                await sleep(1)
                child.send("UseBetterPassword!23\r")  # default password, will be changed
                buffer = ""
            elif "Enter an option:" in screen_buffer:
                # use the shell
                child.send("8")  # Shell
                await sleep(1)
                child.send("\r")
                buffer = ""
            elif "root@SafeSense:~ # " in screen_buffer and waiting_for_reboot:
                child.sendline("configctl ids install rules")
                child.expect("OK", timeout=300)
                child.sendline("configctl ids update")
                child.expect("OK", timeout=300)
                await sleep(2)
                # exit shell
                child.sendline("exit")
                await sleep(1)
                child.sendcontrol("c")
                merged = True
                break
        except TIMEOUT:
            continue
        except EOF:
            break
        except Exception as e:
            logger.error(f"Error during XML template sync post-reboot: {e}")
            return False

    return True
