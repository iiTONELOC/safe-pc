from safe_pc.proxmox_auto_installer.constants import PROXMOX_ALLOWED_KEYBOARDS
from safe_pc.proxmox_auto_installer.utils.tzd import ProxmoxTimezoneHelper
from safe_pc.proxmox_auto_installer.utils.country_codes import ProxmoxCountryCodeHelper


def installer_data():
    """Get the data required for the installer settings page."""
    tz_helper = ProxmoxTimezoneHelper()
    cc_helper = ProxmoxCountryCodeHelper()
    # need to grab some data for the front end
    # we need our timezones, keyboard layouts, and list of countries

    key_layouts = PROXMOX_ALLOWED_KEYBOARDS
    tsz = tz_helper.get_timezones()
    ccd = cc_helper.get_country_codes()
    current_tz = tz_helper.get_local_timezone()
    current_country = tz_helper.get_local_country_code()
    return {
        "installerSettings": {
            "timezones": tsz,
            "keyboards": key_layouts,
            "countries": ccd,
            "currentTimezone": current_tz,
            "currentCountry": current_country,
        }
    }
