"""
Author: Anthony Tropeano
CYBV498: Senior Capstone in Cyber Operations
Date: 2025-09-22
Description: This module provides tests for the Proxmox Answer File Utils Module.
"""

import pytest
from capstone.proxmox.answer_file.utils import gen_ans_file_with

test_answer_file_data: dict[str, dict[str, str | list[str]]] = {
    "global": {
        "keyboard:": "en-us",
        "country": "us",
        "timezone": "America/New_York",
        "fqdn": "proxmox.local",
        "mailto": "root@localhost",
        "root-password-hashed": "",
    },
    "network": {
        "source": "from-answer",
        "cidr": "10.0.4.254/24",
        "gateway": "10.0.4.1",
        "dns": "10.0.4.1",
        "filter.ID_NET_NAME": "eth0",
    },
    "disk-setup": {
        "filesystem": "zfs",
        "zfs.raid": "raid1",
        "disk-list": ["/dev/sda"],
    },
}


# test the gen_ans_file_with function with valid inputs


def test_gen_ans_file_with_valid_inputs(monkeypatch: pytest.MonkeyPatch) -> None:
    # monkeypatch getpass.getpass to return a strong password twice
    monkeypatch.setattr(
        "capstone.proxmox.answer_file.utils.getpass",
        lambda *args, **kwargs: "StrongP@ssw0rd!",  # type: ignore
    )
    print("\n GENERATED ANSWER FILE \n")
    ans_file_str = gen_ans_file_with("eth0", "/dev/sda")
    print(ans_file_str)
    assert isinstance(ans_file_str, str)
    assert "[global]" in ans_file_str
    assert "[network]" in ans_file_str
    assert "[disk-setup]" in ans_file_str
    assert "root-password-hashed" in ans_file_str
    assert "StrongP@ssw0rd!" not in ans_file_str  # ensure password is not in the output
    assert "eth0" in ans_file_str
    assert "/dev/sda" in ans_file_str
    assert "keyboard" in ans_file_str
    assert "country" in ans_file_str
    assert "timezone" in ans_file_str
    assert "cidr" in ans_file_str
    assert "gateway" in ans_file_str
    assert "dns" in ans_file_str
    assert "filesystem" in ans_file_str
    assert "zfs.raid" in ans_file_str
    assert "disk-list" in ans_file_str
    assert "filter.ID_NET_NAME" in ans_file_str
