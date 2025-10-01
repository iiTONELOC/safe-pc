from safe_pc.proxmox_auto_installer.constants import PROXMOX_ALLOWED_KEYBOARDS
from safe_pc.proxmox_auto_installer.utils.tzd import ProxmoxTimezoneHelper
from safe_pc.proxmox_auto_installer.utils.country_codes import ProxmoxCountryCodeHelper
from fastapi import FastAPI
from fastapi.templating import Jinja2Templates


class APIRoutes:
    tz_helper = ProxmoxTimezoneHelper()
    cc_helper = ProxmoxCountryCodeHelper()

    @staticmethod
    def register(
        app: FastAPI,
        templates: Jinja2Templates,
        dev: bool = False,
    ):
        # return a 200 hello work json response for testing
        @app.get(path="/api/installer-data")
        async def installer_data():
            # need to grab some data for the front end
            # we need our timezones, keyboard layouts, and list of countries

            key_layouts = PROXMOX_ALLOWED_KEYBOARDS
            tsz = APIRoutes.tz_helper.get_timezones()
            ccd = APIRoutes.cc_helper.get_country_codes()
            current_tz = APIRoutes.tz_helper.get_local_timezone()
            current_country = APIRoutes.tz_helper.get_local_country_code()
            print(f"CURRENT COUNTRY: {current_country}")
            return {
                "installerSettings": {
                    "timezones": tsz,
                    "keyboards": key_layouts,
                    "countries": ccd,
                    "currentTimezone": current_tz,
                    "currentCountry": current_country,
                }
            }
