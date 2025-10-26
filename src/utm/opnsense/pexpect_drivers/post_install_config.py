from os import environ
from re import search
from asyncio import sleep
from logging import getLogger
from utm.utils.utils import strip_ansi_escape_sequences  # type: ignore
from utm.utils.console_driver import ConsoleDriver
from pexpect import spawn as pe_spawn, TIMEOUT, EOF  # type: ignore


logger = getLogger("utm.opnsense.post_install_config")
base_prefix = "[OPNSense Post-Install Configurator] "


async def drive_configurator(child: pe_spawn, root_password: str = "UseBetterPassword!23") -> None:  # type: ignore
    buffer = ""
    # configure networking
    configured = False
    wan_configured = False
    lan_configured = False

    # login
    while not configured:
        try:
            # Output is inconsistent, read it in chunks in a non-blocking manner
            chunk = child.read_nonblocking(size=2048, timeout=2)  # type: ignore
            buffer += chunk  # type: ignore
            screen_buffer = strip_ansi_escape_sequences(buffer)  # type: ignore

            if "login:" in screen_buffer:
                child.send("root\r")
                buffer = ""
            elif "Password:" in screen_buffer:
                child.send(root_password + "\r")
                await sleep(1)
                buffer = ""
            elif "Enter an option:" in screen_buffer and not configured:
                # Configure WAN first
                child.send("2\r")  # Assign interfaces
                await sleep(1)
                buffer = ""
            elif "Available interfaces:" in screen_buffer and not wan_configured and not lan_configured:
                # Assign WAN to em0
                # stract the numer for the wan interface from the screen buffer
                # 2 - WAN
                wan_number = search(r"(\d+) - WAN", screen_buffer)
                if wan_number:
                    child.send(f"{wan_number.group(1)}\r")
                    await sleep(1)
                    # y to set ipv4 dhcp
                    child.expect("Configure IPv4 address WAN interface via DHCP?")
                    child.send("y\r")
                    child.expect("Configure IPv6 address WAN interface via DHCP6?")
                    child.send("n\r")  # no ipv6
                    child.expect("Enter the new WAN IPv6 address. Press <ENTER> for none")
                    child.send("\r")  # skip ipv6 address
                    child.expect("Do you want to change the web GUI protocol from HTTPS to HTTP?")
                    child.send("n\r")  # dont reset GUI protocol
                    child.expect("Do you want to generate a new self-signed web GUI certificate?")
                    child.send("n\r")  # dont regen cert
                    child.expect("Restore web GUI access defaults?")
                    child.send("n\r")  # dont restore defaults
                    buffer = ""
                    wan_configured = True

            elif "Available interfaces:" in screen_buffer and wan_configured and not lan_configured:
                # Assign LAN to 10.0.30.80/24
                lan_number = search(r"(\d+) - LAN", screen_buffer)
                if lan_number:
                    child.send(f"{lan_number.group(1)}\r")
                    child.expect("Configure IPv4 address LAN interface via DHCP?")
                    child.send("n\r")
                    child.expect("Enter the new LAN IPv4 address. Press <ENTER> for none")
                    child.send("10.3.8.1\r")
                    child.expect("Enter the new LAN IPv4 subnet bit count")
                    child.send("24\r")
                    child.expect("For a LAN, press <ENTER> for none")
                    child.send("\r")
                    child.expect("Configure IPv6 address LAN interface via DHCP6?")
                    child.send("n\r")  # no ipv6
                    child.expect("Enter the new LAN IPv6 address. Press <ENTER> for none")
                    child.send("\r")  # skip ipv6 address
                    child.expect("Do you want to enable the DHCP server on LAN?")
                    child.send("y\r")  # enable dhcp server on lan
                    child.expect("Enter the start address of the IPv4 client address range")
                    child.send("10.3.8.100\r")  # dhcp start
                    child.expect("Enter the end address of the IPv4 client address range")
                    child.send("10.3.8.225\r")  # dhcp end
                    child.expect("Do you want to change the web GUI protocol from HTTPS to HTTP?")
                    child.send("n\r")  # dont change gui port
                    child.expect("Do you want to generate a new self-signed web GUI certificate?")
                    child.send("n\r")  # dont change cert
                    child.expect("Restore web GUI access defaults?")
                    child.send("n\r")  # dont restore defaults
                    buffer = ""
                    lan_configured = True

            if wan_configured and lan_configured:
                configured = True
        except TIMEOUT:
            continue
        except EOF:
            break


async def main() -> None:

    try:
        async with ConsoleDriver(100, logger, base_prefix) as console:
            logger.info(f"{base_prefix}Starting post-install configuration for VM ID 100.")
            await drive_configurator(console.child, environ.get("SAFE_SENSE_PWD", None) or "UseBetterPassword!23")  # type: ignore
            # the main installer has finished its job, now we need to configure the system
    except Exception as e:
        logger.error(f"{base_prefix}Error during post-install configuration: {e}")


if __name__ == "__main__":
    from asyncio import run
    from utm.__main__ import setup_logging

    setup_logging()
    run(main())
