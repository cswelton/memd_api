from .utils import load_env
from .members import PrimaryMember
import requests
import datetime
from jsonschema import validate
import logging


class Client:
    PRIMARY_MEMBER_SCHEMA = {
        "type": "object",
        "properties": {
            "externalID": {
                "type": "string"
            },
            "name": {
                "type": "object",
                "properties": {
                    "First": {
                        "type": "string"
                    },
                    "Last": {
                        "type": "string"
                    }
                },
                "additionalProperties": False,
                "required": ["First", "Last"]
            },
            "email": {
                "type": "string"
            },
            "phone": {
                "type": "string"
            },
            "dob": {
                "type": "string"
            },
            "gender": {
                "type": "string"
            },
            "address": {
                "type": "object",
                "properties": {
                    "address1": {
                        "type": "string"
                    },
                    "address2": {
                        "type": ["string", "null"]
                    },
                    "city": {
                        "type": "string"
                    },
                    "state": {
                        "type": "string"
                    },
                    "zipCode": {
                        "type": "string"
                    }
                },
                "required": ["address1", "address2", "city", "state", "zipCode"],
                "additionalProperties": False
            },
            "rxDiscounts": {
                "type": "object"
            },
            "termsAgreed": {
                "type": "boolean"
            },
            "preferredLanguage": {
                "const": "NP"
            },
            "plancode": {
                "type": "string"
            },
            "relationship": {
                "const": "18"
            },
            "misc3": {
                "type": "string"
            },
            "benefitstart": {
                "type": "string"
            },
            "benefitend": {
                "type": "string"
            }
        },
        "additionalProperties": False,
        "required": ["externalID", "name", "email", "phone", "dob", "gender", "address", "rxDiscounts",
                     "termsAgreed", "preferredLanguage", "plancode", "relationship", "benefitstart", "benefitend"]
    }
    _session = None

    def __init__(self, dict_config=None):
        """
        Client Configuration:
        Can be set by passing dict_config
        Or
        Set using environment variables:
        MEMD_API_BASE_URL
        MEMD_API_USERNAME
        MEMD_API_PASSWORD
        MEMD_API_CLIENT_ID
        MEMD_API_CLIENT_SECRET
        :param dict_config (dict) If set, must contain keys for base_url, username, password, client_id, client_secret
        """
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        self._access_token = None
        self._access_token_type = 'bearer'
        self._access_token_expires_in = 0
        self._access_token_last_refreshed = None
        if dict_config is not None:
            if not isinstance(dict_config, dict):
                raise ValueError("dict_config must be of type dict, got %s" % type(dict_config))
            for f in ("base_url", "username", "password", "client_id", "client_secret"):
                if f not in dict_config:
                    raise ValueError(f"Required key {f} not set in dict_config")
            self.base_url = dict_config.get("base_url")
            self.username = dict_config.get("username")
            self.password = dict_config.get("password")
            self.client_id = dict_config.get("client_id")
            self.client_secret = dict_config.get("client_secret")
        else:
            self.base_url = load_env("MEMD_API_BASE_URL")
            self.username = load_env("MEMD_API_USERNAME")
            self.password = load_env("MEMD_API_PASSWORD")
            self.client_id = load_env("MEMD_API_CLIENT_ID")
            self.client_secret = load_env("MEMD_API_CLIENT_SECRET")
        if self.base_url.endswith("/"):
            self.base_url = self.base_url[:-1]

    @property
    def access_token(self):
        if self._access_token is None:
            self._set_token()
        return self._access_token

    @property
    def session(self):
        if self._session is None:
            s = requests.Session()
            s.headers.update({
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.access_token}"
            })
            self._session = s
        if self._token_needs_refresh():
            self._set_token()
            self._session.headers.update({
                "Authorization": f"Bearer {self.access_token}"
            })
        return self._session

    def _token_needs_refresh(self):
        if self._access_token_last_refreshed is None:
            return True
        expires_at = self._access_token_last_refreshed + datetime.timedelta(seconds=self._access_token_expires_in)
        return expires_at <= datetime.datetime.utcnow()

    def _set_token(self):
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        payload = f"grant_type=password&username={self.username}&password={self.password}&client_id={self.client_id}&client_secret={self.client_secret}"
        url = f"{self.base_url}/v2/token"
        self.logger.debug("Retrieving Bearer Token")
        response = requests.request("POST", url, headers=headers, data=payload)
        self.logger.debug(f"{response.request.url} {response.status_code} {response.reason}")
        response.raise_for_status()
        data = response.json()
        self._access_token = data["access_token"]
        self._access_token_type = data["token_type"]
        self._access_token_expires_in = data["expires_in"]
        self._access_token_last_refreshed = datetime.datetime.utcnow()
        self.logger.debug(f"Refreshed token, expires in {self._access_token_expires_in}")

    def _post_json(self, url, payload, raise_for_status=True):
        r = self.session.post(url, json=payload)
        if raise_for_status:
            try:
                r.raise_for_status()
            except requests.exceptions.RequestException as exc:
                msg = f"{url} {r.status_code} {r.reason}\nError: {exc}\nHeaders:\n"
                for header, value in r.headers.items():
                    msg += f"  {header}: {value}\n"
                msg += f"Body:\n{r.text}"
                self.logger.error(msg)
                raise
        self.logger.debug(f"{r.request.url} {r.status_code} {r.reason}")
        return r.json()

    def _put_json(self, url, payload, raise_for_status=True):
        r = self.session.put(url, json=payload)
        if raise_for_status:
            try:
                r.raise_for_status()
            except requests.exceptions.RequestException as exc:
                msg = f"{url} {r.status_code} {r.reason}\nError: {exc}\nHeaders:\n"
                for header, value in r.headers.items():
                    msg += f"  {header}: {value}\n"
                msg += f"Body:\n{r.text}"
                self.logger.error(msg)
                raise
        self.logger.debug(f"{r.request.url} {r.status_code} {r.reason}")
        return r.json()

    def _get_json(self, url, raise_for_status=True):
        r = self.session.get(url, headers={"Accept": "application/json"})
        if raise_for_status:
            try:
                r.raise_for_status()
            except requests.exceptions.RequestException as exc:
                msg = f"{url} {r.status_code} {r.reason}\nError: {exc}\nHeaders:\n"
                for header, value in r.headers.items():
                    msg += f"  {header}: {value}\n"
                msg += f"Body:\n{r.text}"
                self.logger.error(msg)
                raise
        self.logger.debug(f"{r.request.url} {r.status_code} {r.reason}")
        return r.json()

    def validate_member(self, member_dict):
        validate(member_dict, self.PRIMARY_MEMBER_SCHEMA)

    def get_primary_member(self, external_id):
        url = f"{self.base_url}/v1/partnermember/{external_id}"
        member_data = self._get_json(url, raise_for_status=True)
        return PrimaryMember(self, **member_data)

    def create_primary_member(self, member_dict):
        """
        Creates a new primary member
        :param member_dict: (dict) Member Configuration based on PRIMARY_MEMBER_SCHEMA
        :return:
        """
        validate(member_dict, self.PRIMARY_MEMBER_SCHEMA)
        url = f"{self.base_url}/v1/partnermember"
        member_data = self._post_json(url, member_dict, raise_for_status=True)
        return PrimaryMember(self, **member_data)

    def get_or_create_primary_member(self, member_dict, ensure_plancode=True, dry_run=False):
        """
        Either creates a new primary member or retrieves an existing one
        :param member_dict: (dict) Member Configuration based on PRIMARY_MEMBER_SCHEMA
        :return:
        """
        validate(member_dict, self.PRIMARY_MEMBER_SCHEMA)
        external_id = member_dict['externalID']
        benefitstart = datetime.datetime.fromisoformat(member_dict['benefitstart'])
        plancode = member_dict["plancode"]
        url = f"{self.base_url}/v1/partnermember/{external_id}"
        r = self.session.get(url, headers={"Accept": "application/json"})
        try:
            r.raise_for_status()
        except requests.exceptions.RequestException as exc:
            self.logger.debug(f"{exc.request.url} {exc.response.status_code} {exc.response.reason}")
            self.logger.info(f"Primary member with ID {external_id} not found, creating new member.")
            member = self.create_primary_member(member_dict)
        else:
            self.logger.info(f"Primary member {external_id} found.")
            member_data = r.json()
            member = PrimaryMember(self, **member_data)
        if ensure_plancode:
            self.logger.info(f"Ensuring plancode {plancode} benefitstart: {benefitstart}")
            member.ensure_plancode(plancode, benefitstart=benefitstart, dry_run=dry_run)
        return member
