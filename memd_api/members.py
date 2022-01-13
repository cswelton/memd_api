from requests.exceptions import RequestException
import logging
import datetime
import json


class Base(object):
    _data = {}
    _fields_changed = []

    def __init__(self, *args, **kwargs):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        self._fields_changed = []

    def as_dict(self):
        return self._data

    def __setattr__(self, key, value):
        self._fields_changed.append(key)
        super(Base, self).__setattr__(key, value)


class Policy(Base):
    def __init__(self, client, externalID=None, policyId=None, benefitstart=None,
                 benefitend=None, plancode=None, data=None):
        self.externalID = externalID
        self._id = externalID
        self.policyId = policyId
        self.benefitstart=benefitstart
        self.benefitend=benefitend
        self.plancode=plancode
        self._client = client
        if data is None:
            self._data = {
                "externalid": self._id,
                "policyId": self.policyId,
                "benefitstart": benefitstart,
                "benefitend": benefitend,
                "plancode": plancode
            }
        else:
            self._data = data

        super().__init__()

    def terminate(self):
        url = f"{self._client.base_url}/v1/member/{self._id}/policy/{self.plancode}"
        payload = {
            "termdate": datetime.datetime.today().replace(hour=0).replace(minute=0).replace(second=0).replace(
                microsecond=0).isoformat()
        }
        self.logger.debug(f"Terminating policy for {self._id} {self.plancode}: {payload}")
        try:
            response_json = self._client._post_json(url, payload, raise_for_status=True)
            for elem in response_json:
                for k, v in elem.items():
                    if hasattr(self, k):
                        setattr(self, k, v)
            self._data = response_json
            self._fields_changed = []
            return response_json
        except RequestException as exc:
            self.logger.exception("Error Terminating Policy", exc_info=True)

    def save(self, dry_run=False):
        url = f"{self._client.base_url}/v1/partnermember/{self._id}/policy/"
        payload = {
            "benefitstart": self.benefitstart,
            "benefitend": self.benefitend,
            "plancode": self.plancode
        }
        if dry_run:
            return payload
        self.logger.debug(f"Updating policy for {self._id}: {payload}")
        try:
            response_json = self._client._post_json(url, payload, raise_for_status=True)
            for k, v in response_json.items():
                if hasattr(self, k):
                    setattr(self, k, v)
            self._data = response_json
            self._fields_changed = []
            return response_json
        except RequestException as exc:
            self.logger.exception("Error Updating Policy", exc_info=True)


class MemberName(object):
    def __init__(self, first=None, middle=None, last=None):
        self.first = first
        self.middle = middle
        self.last = last

    def to_dict(self):
        return {"first": self.first, "middle": self.middle, "last": self.last}


class PrimaryMember(Base):
    UPDATE_FIELDS = ("name.First", "name.Middle", "name.Last", "email", "phone", "dob", "gender", "address", "city", "state", "zipCode", "misc3")
    FIELDS_CHANGEABLE = ("name", "email", "phone", "dob", "gender", "address", "misc3")

    def __init__(self, client, **member_data):
        """
        :param member_dict: Member Info (via /v1/partnermember)
        """
        self._client = client
        self.load(**member_data)
        super().__init__()

    def load(self, **member_data):
        if "externalID" not in member_data:
            raise ValueError("externalID is required")
        self._id = member_data["externalID"]
        self.dependants = []
        self.policies = member_data.get("policies")
        if "name" in member_data:
            self.name = MemberName(**member_data["name"])
        for k in ("externalsubscriberid", "relationship", "misc1", "misc2", "misc3", "mrn", "rxDiscounts", "id",
                  "externalID", "email", "phone", "dob", "gender", "address", "termsAgreed", "subscriber",
                  "preferredLanguage", "fromImport", "plancode"):
            if k in member_data:
                setattr(self, k, member_data[k])
        self._data = member_data

    def terminate_policy(self, plancode, benefitend=None, dry_run=False):
        if benefitend is None:
            benefitend = datetime.datetime.today()
        benefitend = benefitend.replace(hour=0).replace(minute=0).replace(second=0).replace(
                microsecond=0).isoformat()
        self.logger.info(f"Terminating policy for {self._id} plancode {plancode} dry_run={dry_run}")
        payload = {
            "termdate": datetime.datetime.today().replace(hour=0).replace(minute=0).replace(second=0).replace(
                microsecond=0).isoformat()
        }
        if not dry_run:
            self.logger.debug(f"Terminating policy for {self._id} policy {plancode}")
            url = f"{self._client.base_url}/v1/member/{self._id}/policy/{plancode}"
            try:
                return self._client._post_json(url, payload, raise_for_status=True)
            except RequestException as exc:
                if hasattr(exc, 'response'):
                    if str(exc.response.status_code) == '404':
                        self.logger.warning(f"For member {self._id}, Tried to delete plancode {plancode} but it was not found")
        else:
            return payload

    def active_policies(self):
        return [p for p in self.policies if p["isactive"]]

    def deactivate_policies(self, dry_run=False, deactivated=[], _count=0):
        _count += 1
        if _count > 10:
            raise Exception(f"Too many attempts to deactivate policies for {self._id} ({_count})")
        if dry_run:
            active_policies = self.active_policies()
            for p in active_policies:
                deactivated.append({p["plancode"]: self.terminate_policy(p["plancode"], dry_run=True)})
        else:
            for p in self.active_policies():
                deactivated.append({p["plancode"]: self.terminate_policy(p["plancode"], dry_run=dry_run)})
                self.reload()
                return self.deactivate_policies(dry_run=dry_run, deactivated=deactivated, _count=_count)
        return deactivated

    def create_policy(self, plancode, benefitstart=None, dry_run=False):
        """
        :param plancode The Plancode
        :param benefitstart If set, must be a datetime when benefits start, defaults to today.
        """
        if benefitstart is None:
            benefitstart = datetime.datetime.today()
        benefitstart = benefitstart.replace(hour=0).replace(minute=0).replace(second=0).replace(
                microsecond=0).isoformat()
        benefitend = None
        new_policy_payload = {
            "benefitstart": benefitstart,
            "benefitend": benefitend,
            "plancode": plancode
        }
        if dry_run:
            result = {"terminated": self.active_policies()}
        else:
            result = {"terminated": self.deactivate_policies(dry_run=dry_run)}
        self.logger.info(f"Creating new policy for {self._id} plancode {plancode} dry_run={dry_run}")
        if not dry_run:
            url = f"{self._client.base_url}/v1/partnermember/{self._id}/policy/"
            try:
                result["created"] = self._client._post_json(url, new_policy_payload, raise_for_status=True)
            except RequestException as exc:
                self.logger.warning(f"Unable to create policy for {self._id}, plancode {plancode} not found")
                self.logger.warning("Reverting to previous policies")
                url = f"{self._client.base_url}/v1/partnermember/{self._id}/policy/"
                for policy in result["terminated"]:
                    payload = {
                        "benefitstart": benefitstart,
                        "benefitend": benefitend,
                        "plancode": policy["plancode"]
                    }
                    try:
                        self._client._post_json(url, payload, raise_for_status=True)
                    except RequestException as exc:
                        self.logger.warning(f"Error trying to revert policies for {self._id} plancode {policy['plancode']} {exc}")
                        continue
                raise
            finally:
                self.reload()
        else:
            result["created"] = new_policy_payload
        return result

    def reload(self):
        self.logger.debug("Reloading state")
        url = f"{self._client.base_url}/v1/partnermember/{self._id}"
        member_info = self._client._get_json(url, raise_for_status=True)
        self.load(**member_info)
        self.logger.debug("State reloaded")

    def ensure_plancode(self, plancode, benefitstart=None, dry_run=False):
        """ Checks memd api to see if plancode is active and if not activates it. """
        result = {"terminated": [], "created": []}
        for p in self.active_policies():
            if p["plancode"] == plancode:
                self.logger.debug(f"Plancode {plancode} is active")
                break
        else:
            result = self.create_policy(plancode, benefitstart=benefitstart, dry_run=dry_run)
        return result

    def update(self, dry_run=False, **kwargs):
        self.reload()
        update_dict = {k: v for k, v in self._data.items() if k not in ("dependents", "policies")}
        for k, v in kwargs.items():
            if k not in self.FIELDS_CHANGEABLE:
                self.logger.warning(f"Ignoring update for field {k}")
            else:
                update_dict[k] = v
        if dry_run:
            return update_dict
        url = f"{self._client.base_url}/v1/partnermember/{self._id}"
        self.logger.debug(f"Updating {self._id} with payload:\n{json.dumps(update_dict, indent=4)}")
        try:
            put_response_data = self._client._put_json(url, update_dict, raise_for_status=True)
            self.reload()
            return put_response_data
        except RequestException as exc:
            self.logger.exception("Error Updating Member", exc_info=True)
            raise

    def save(self, dry_run=False):
        update_dict = {}
        for f in self._fields_changed:
            if f in self.FIELDS_CHANGEABLE:
                val = getattr(self, f)
                if hasattr(val, "to_dict"):
                    update_dict[f] = val.to_dict()
                else:
                    update_dict[f] = val
            else:
                self.logger.warning(f"Ignoring update for field {f}")
        if dry_run:
            return update_dict
        url = f"{self._client.base_url}/v1/partnermember/{self._id}"
        try:
            member_data = self._client._put_json(url, update_dict, raise_for_status=True)
            self._fields_changed = []
            return member_data
        except RequestException as exc:
            self.logger.exception("Error Updating Member", exc_info=True)

