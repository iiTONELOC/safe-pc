import pytest
from pydantic import ValidationError
from safe_pc.proxmox_auto_installer.answer_file._global import (
    GlobalConfig,
    GLOBAL_CONFIG_DEFAULTS,
)


# --- Keyboard Tests ---
@pytest.mark.parametrize("keyboard", ["de", "fr", "en-us", "es"])
def test_keyboard_valid_patterns(keyboard):
    cfg = GlobalConfig(keyboard=keyboard)
    assert cfg.keyboard == keyboard


@pytest.mark.parametrize("invalid_keyboard", ["", "US", "en_US", "123", "u$", "a-b-c"])
def test_keyboard_invalid_patterns(invalid_keyboard):
    with pytest.raises(ValidationError):
        GlobalConfig(keyboard=invalid_keyboard)


def test_keyboard_not_in_allowed_list():
    with pytest.raises(ValidationError):
        GlobalConfig(keyboard="us")


# --- Country Tests ---
@pytest.mark.parametrize("country", ["US", "DE", "FR", "GB"])
def test_country_valid_patterns(country):
    cfg = GlobalConfig(country=country)
    assert cfg.country == country


@pytest.mark.parametrize("invalid_country", ["", "de_DE", "1a", "!!", "a-b-c"])
def test_country_invalid_patterns(invalid_country):
    with pytest.raises(ValidationError):
        GlobalConfig(country=invalid_country)


# --- Timezone Tests ---
@pytest.mark.parametrize(
    "timezone",
    ["America/New_York", "Europe/Berlin", "Asia/Tokyo", "Africa/Johannesburg"],
)
def test_timezone_valid_patterns(timezone):
    cfg = GlobalConfig(timezone=timezone)
    assert cfg.timezone == timezone


@pytest.mark.parametrize(
    "invalid_timezone",
    ["", "AmericaNewYork", "US/Eastern/Extra", "Invalid/Timezone", "GMT+5"],
)
def test_timezone_invalid_patterns(invalid_timezone):
    with pytest.raises(ValidationError):
        GlobalConfig(timezone=invalid_timezone)


def test_timezone_not_in_allowed_list():
    with pytest.raises(ValidationError):
        GlobalConfig(timezone="East/Berlin")


# --- FQDN Tests ---
@pytest.mark.parametrize(
    "fqdn", ["proxmox.lab.local", "test.example.com", "my-server.domain.org"]
)
def test_fqdn_valid_patterns(fqdn):
    cfg = GlobalConfig(fqdn=fqdn)
    assert cfg.fqdn == fqdn


@pytest.mark.parametrize(
    "invalid_fqdn",
    [
        "",
        "invalid_domain",
        "example",
        "foo..bar.com",
        "-start.invalid.com",
        "a" * 300 + ".com",
    ],
)
def test_fqdn_invalid_patterns(invalid_fqdn):
    with pytest.raises(ValidationError):
        GlobalConfig(fqdn=invalid_fqdn)


# --- Mailto Tests ---
@pytest.mark.parametrize(
    "mailto",
    [
        "root@localhost",
        "user@example.com",
        "first.last@domain.co.uk",
        "name+tag@domain.io",
    ],
)
def test_mailto_valid_patterns(mailto):
    cfg = GlobalConfig(mailto=mailto)
    assert cfg.mailto == mailto


@pytest.mark.parametrize(
    "invalid_mailto",
    ["", "plainaddress", "missing@tld", "bad@domain,com", "@missinguser.com"],
)
def test_mailto_invalid_patterns(invalid_mailto):
    with pytest.raises(ValidationError):
        GlobalConfig(mailto=invalid_mailto)


# --- Root Password Hashed Tests ---
def test_root_password_hashed_valid_pattern():
    valid_hash = GLOBAL_CONFIG_DEFAULTS["root_password_hashed"]
    cfg = GlobalConfig(
        root_password_hashed=valid_hash,
        keyboard=GLOBAL_CONFIG_DEFAULTS["keyboard"],
    )
    assert cfg.root_password_hashed == valid_hash


@pytest.mark.parametrize(
    "invalid_hash",
    [
        "",  # empty
        "$6$rounds=abc$12345678$" + "A" * 86,  # bad rounds
        "$6$rounds=656000$short$" + "A" * 86,  # salt too short
        "$6$rounds=656000$12345678$" + "A" * 80,  # hash too short
        "no_prefix$6$rounds=656000$12345678$" + "A" * 86,
    ],
)
def test_root_password_hashed_invalid_patterns(invalid_hash):
    with pytest.raises(ValidationError):
        GlobalConfig(root_password_hashed=invalid_hash)


# --- Alias & Serialization Tests ---
def test_alias_population_for_root_password():
    valid_hash = GLOBAL_CONFIG_DEFAULTS["root_password_hashed"]
    cfg = GlobalConfig(root_password_hashed=valid_hash)
    dumped = cfg.model_dump(by_alias=True)
    assert "root-password-hashed" in dumped
    assert dumped["root-password-hashed"] == valid_hash


# --- Full Valid Config ---
def test_full_valid__global():
    valid_hash = GLOBAL_CONFIG_DEFAULTS["root_password_hashed"]

    cfg = GlobalConfig(
        keyboard=GLOBAL_CONFIG_DEFAULTS["keyboard"],
        country=GLOBAL_CONFIG_DEFAULTS["country"],
        timezone=GLOBAL_CONFIG_DEFAULTS["timezone"],
        fqdn=GLOBAL_CONFIG_DEFAULTS["fqdn"],
        mailto=GLOBAL_CONFIG_DEFAULTS["mailto"],
        root_password_hashed=valid_hash,
    )

    assert cfg.keyboard == GLOBAL_CONFIG_DEFAULTS["keyboard"]
    assert cfg.country == GLOBAL_CONFIG_DEFAULTS["country"]
    assert cfg.timezone == GLOBAL_CONFIG_DEFAULTS["timezone"]
    assert cfg.fqdn == GLOBAL_CONFIG_DEFAULTS["fqdn"]
    assert cfg.mailto == GLOBAL_CONFIG_DEFAULTS["mailto"]
    assert cfg.root_password_hashed == valid_hash
