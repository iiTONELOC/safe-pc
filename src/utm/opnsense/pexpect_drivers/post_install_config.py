from os import environ
from re import search
from asyncio import sleep
from logging import getLogger
from utm.utils.utils import strip_ansi_escape_sequences  # type: ignore
from utm.utils.console_driver import ConsoleDriver
from pexpect import spawn as pe_spawn, TIMEOUT, EOF  # type: ignore


logger = getLogger("utm.opnsense.post_install_config")
base_prefix = "[OPNSense Post-Install Configurator] "

# This is DIRTY but it works - took longer than it should to get dyanmic WAN, REFACTOR AT OWN RISK!
# This configurator does not assume that the WAN or LAN are on a specific interface
# The WAN is set first and assigned via DHCP. After if an address is not found then
# Interface assignments are swapped and DHCP on WAN is reattempted, this will indefinitely loop
# Until a WAN IP has been assigned
# DHCP is enabled on the LAN interface with a pool from .100 to .225


async def drive_configurator(child: pe_spawn, root_password: str = "UseBetterPassword!23") -> None:  # type: ignore
    buffer = ""
    wan_interface = ""
    lan_interface = ""
    configured = False
    wan_configured = False
    lan_configured = False

    SAFE_LAN_PREFIX = environ.get("SAFE_LAN_PREFIX", "10.3.8")
    SAFE_LAN_FW_HOST = environ.get("SAFE_LAN_FW_HOST", f"{SAFE_LAN_PREFIX}.1")
    SAFE_PC_SUBNET_BIT_COUNT = int(environ.get("SAFE_LAN_BIT_COUNT", "24"))

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
                # Assign WAN via DHCP
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

                    # ------------------ Wait to see if WAN got an address -----------------
                    # get the lan interface name, in case we need to swap them
                    child.expect(r"LAN\s*\((\w+)\)")
                    lan_interface = child.match.group(1)  # type: ignore

                    # grab the wan interface name and its hopefully assigned ip
                    await sleep(1)  # we have optional checks, so we need to wait or it returns early
                    child.expect(r"WAN\s*\(([^)]+)\)\s*->(?:\s*v4(?:/DHCP4)?:\s*([\d.]+/\d+))?")
                    wan_interface = child.match.group(1)  # type: ignore
                    wan_ip = child.match.group(2)  # type: ignore

                    if wan_ip:
                        wan_ip = wan_ip.strip()  # type: ignore

                    if wan_ip is not None and wan_ip != "":
                        wan_configured = True
                        logger.info(f"{base_prefix}WAN interface {wan_interface} configured with IP {wan_ip}.")
                        buffer = ""
                        child.send("\r")  # proceed
                    else:
                        # need to reconfigure wan
                        wan_configured = False

                        child.expect("Enter an option:")
                        await sleep(1)
                        child.send("1\r")  # Assign interfaces
                        # expects are not working here so, swapped with sleeps and sends
                        # child.expect("Do you want to configure LAGGs now? [y/N]")
                        await sleep(1)
                        child.send("\r")  # no laggs
                        # child.expect("Do you want to configure VLANs now? [y/N]")
                        await sleep(1)
                        child.send("\r")  # no vlans
                        # child.expect("Enter the WAN interface name or 'a' for auto-detection:")
                        await sleep(1)
                        child.send(f"{lan_interface}\r")  # wan didnt originally receive dhcp, set to lan interface
                        # child.expect(
                        #     "Enter the LAN interface name or 'a' for auto-detection\nNOTE: this enables full Firewalling/NAT mode."
                        # )
                        await sleep(1.5)
                        child.send(f"{wan_interface}\r")  # set lan to wan interface
                        # update variables
                        current_wan = lan_interface  # type: ignore
                        lan_interface = wan_interface  # type: ignore
                        wan_interface = current_wan  # type: ignore
                        # child.expect("Enter the Optional interface 1 name or 'a' for auto-detection:")
                        await sleep(1)
                        child.send("\r")  # no opt1
                        # child.expect("Do you want to proceed? [y/N]")
                        await sleep(1)
                        child.send("y\r")
                        buffer = ""

            elif "Available interfaces:" in screen_buffer and wan_configured and not lan_configured:
                # Assign LAN to 10.3.8.1/24
                lan_number = search(r"(\d+) - LAN", screen_buffer)
                if lan_number:
                    child.send(f"{lan_number.group(1)}\r")
                    await sleep(1)
                    child.expect("Configure IPv4 address LAN interface via DHCP?")
                    child.send("n\r")
                    child.expect("Enter the new LAN IPv4 address. Press <ENTER> for none")
                    child.send(f"{SAFE_LAN_FW_HOST}\r")
                    child.expect("Enter the new LAN IPv4 subnet bit count")
                    child.send(f"f{SAFE_PC_SUBNET_BIT_COUNT}\r")
                    child.expect("For a LAN, press <ENTER> for none")
                    child.send("\r")
                    child.expect("Configure IPv6 address LAN interface via DHCP6?")
                    child.send("n\r")  # no ipv6
                    child.expect("Enter the new LAN IPv6 address. Press <ENTER> for none")
                    child.send("\r")  # skip ipv6 address
                    child.expect("Do you want to enable the DHCP server on LAN?")
                    child.send("y\r")  # enable dhcp server on lan
                    child.expect("Enter the start address of the IPv4 client address range")
                    child.send(f"{SAFE_LAN_PREFIX}.100\r")  # dhcp start
                    child.expect("Enter the end address of the IPv4 client address range")
                    child.send(f"{SAFE_LAN_PREFIX}.225\r")  # dhcp end
                    child.expect("Do you want to change the web GUI protocol from HTTPS to HTTP?")
                    child.send("n\r")  # dont change gui port
                    child.expect("Do you want to generate a new self-signed web GUI certificate?")
                    child.send("n\r")  # dont change cert
                    # child.expect("Restore web GUI access defaults?")
                    await sleep(1)
                    child.send("n\r")  # dont restore defaults
                    await sleep(1)
                    child.send("\r")  # proceed
                    lan_configured = True
                    wan_configured = True
                    break

        except TIMEOUT:
            continue
        except EOF:
            break


async def main() -> None:

    try:
        async with ConsoleDriver(100, logger, base_prefix) as console:
            logger.info(f"{base_prefix}Starting post-install configuration for VM ID 100.")
            await drive_configurator(console.child, environ.get("SAFE_SENSE_PWD", "UseBetterPassword!23"))  # type: ignore
            # the main installer has finished its job, now we need to configure the system
    except Exception as e:
        logger.error(f"{base_prefix}Error during post-install configuration: {e}")


if __name__ == "__main__":
    from asyncio import run
    from utm.__main__ import setup_logging

    setup_logging()
    run(main())
