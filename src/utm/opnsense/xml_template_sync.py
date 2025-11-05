import secrets
import string
from os import environ, umask
from json import dumps
from pathlib import Path
from asyncio import gather
from logging import getLogger
from bcrypt import hashpw, gensalt  # type: ignore
from utm.utils.console_driver import ConsoleDriver
from utm.__main__ import run_command_async, setup_logging
from utm.opnsense.pexpect_drivers import xml_template_sync_driver  # type: ignore

from aiofiles import open as aio_open

project_root = "/opt/safe_pc"
logger = getLogger("utm.opnsense.xml_template_sync")


def gen_rand_username() -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "user_" + "".join(secrets.choice(alphabet) for _ in range(12))


async def gen_random_str(length: int) -> str:
    # run the openssl command to generate a random string of given length
    cmd = ["openssl", "rand", "-base64", str(length)]
    result = await run_command_async(*cmd, check=True)
    return result.stdout.strip()


async def gen_api_secret() -> tuple[str, str]:
    secret_plain = await gen_random_str(32)
    # hash the secret
    cmd = ["openssl", "passwd", "-6", secret_plain]
    out = await run_command_async(*cmd, check=True)
    hashed = out.stdout.strip()
    return secret_plain, hashed


def hash_user_password(password: str) -> str:
    # hash the user account pwd using bcrypt
    hashed = hashpw(password.encode("utf-8"), gensalt(rounds=12))
    return hashed.decode("utf-8")


async def read_file_content(file_path: Path) -> str:
    content = ""
    async with aio_open(file_path, mode="r") as f:
        content = await f.read()
    return content


async def write_credentials_file(vm_id: str, username: str, password: str, api_key: str, api_secret: str) -> None:
    creds_path = Path(f"{project_root}/credentials_opnsense_{vm_id}.txt")
    umask(0o077)
    # dump it as json so we can easily grab it later
    creds_content = dumps(
        {
            "user": username,
            "password": password,
            "api_key": api_key,
            "api_secret": api_secret,
        },
        indent=4,
    )
    async with aio_open(creds_path, mode="w") as f:
        await f.write(creds_content)

    # set file permissions to root-level read-only
    await run_command_async("chmod", "400", str(creds_path), check=True)
    logger.info(f"Credentials written to {creds_path}")
    return None


async def xml_template_sync(vm_id: str, root_password: str) -> bool:  # NOSONAR type: ignore
    # note: the root_passwords is used to fix the expected signature
    # the root password is for the root user, the password here is for the API user, which we create and is not root
    result = False

    try:
        username = gen_rand_username()
        password, api_key, (api_secret_plain, api_secret_hashed), template_content, xml_merge_script = await gather(
            gen_random_str(18),
            gen_random_str(32),
            gen_api_secret(),
            read_file_content(Path(f"{project_root}/safety_config.xml")),
            read_file_content(Path(f"{project_root}/src/utm/opnsense/xml_merger.py")),
        )

        password_hashed = hash_user_password(password)

        async with ConsoleDriver(int(vm_id), logger, "[OPNSense XMLSync] ") as console:
            template_content = (
                template_content.replace("{{SAFE_SENSE_USER}}", username)
                .replace("{{SAFE_SENSE_PWD}}", password_hashed)
                .replace("{{SAFE_SENSE_API_KEY}}", api_key)
                .replace("{{SAFE_SENSE_API_SECRET}}", api_secret_hashed)
            )
            result = await xml_template_sync_driver(console.child, template_content, xml_merge_script)  # type: ignore

        if not result:
            logger.error(f"[OPNSense XMLSync] XML template sync failed for VM ID {vm_id}.")
            return result
        else:
            logger.info(f"[OPNSense XMLSync] XML template sync completed for VM ID {vm_id}.")
            await write_credentials_file(vm_id, username, password, api_key, api_secret_plain)
            # await restart_vm(vm_id)

        return result
    except Exception as e:
        logger.error(f"Error during XML template synchronization: {e}")
        return result


if __name__ == "__main__":
    from asyncio import run

    async def main() -> None:
        setup_logging()
        await xml_template_sync("100", environ.get("SAFE_SENSE_PWD", "UseBetterPassword!23"))

    run(main())
