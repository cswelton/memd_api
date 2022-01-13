import click
import logging
import configparser
import json
import uuid
import names
import datetime
import os
import shutil

LOG_FORMAT_STR = '[%(asctime)s][%(name)s:%(levelname)s] %(message)s'
HOME_DIR = os.path.expanduser("~/.memd_api")
CONF_DIR = os.path.join(HOME_DIR, "conf")
if not os.path.isdir(HOME_DIR):
    os.mkdir(HOME_DIR)
if not os.path.isdir(CONF_DIR):
    os.mkdir(CONF_DIR)
this_dir, this_filename = os.path.split(__file__)
DEFAULT_API_CONFIG_PATH = os.path.join(this_dir, "data", "api.ini")
DEFAULT_JSON_CONFIG_PATH = os.path.join(this_dir, "data", "defaults.json")
if not os.path.isfile(os.path.join(CONF_DIR, "api.ini")):
    shutil.copyfile(DEFAULT_API_CONFIG_PATH, os.path.join(CONF_DIR, "api.ini"))
if not os.path.isfile(os.path.join(CONF_DIR, "defaults.json")):
    shutil.copyfile(DEFAULT_JSON_CONFIG_PATH, os.path.join(CONF_DIR, "defaults.json"))


def load_config(config_file=None):
    conf = {}
    if config_file is None:
        return conf
    elif config_file.endswith(".json"):
        with open(config_file, "r") as fp:
            conf = json.load(fp)
    elif config_file.endswith(".ini"):
        parser = configparser.ConfigParser(interpolation=None)
        parser.read([config_file])
        for section in parser.sections():
            conf[section] = {}
            for k, v in parser.items(section):
                conf[section][k] = v
    return conf


@click.group()
@click.option("-l", "--log-level",
              type=click.Choice(["debug", "info", "warning", "critical", "null"], case_sensitive=False),
              default="warning", show_default=True)
@click.option("-m", "--mode", type=click.Choice(["prod", "test"], case_sensitive=False), default="prod",
              show_default=True, help="In test mode, output is written to files.")
@click.option("--api-config", type=click.Path(), required=True, default=os.path.join(CONF_DIR, "api.ini"),
              show_default=True)
@click.option("--output-directory", type=click.Path(), default=HOME_DIR, show_default=True,
              help="Where to store files in test mode.")
@click.pass_context
def cli(ctx, log_level, mode, api_config, output_directory):
    ctx.ensure_object(dict)
    if api_config:
        if not os.path.isfile(api_config):
            shutil.copyfile(DEFAULT_API_CONFIG_PATH, api_config)
    api_config_data = load_config(api_config)
    for _ in ("base_url", "username", "password", "client_id", "client_secret"):
        if not api_config_data.get("api", {}).get(_):
            raise click.BadOptionUsage("api_config", f"api_config missing {_}")
    ctx.obj["api_config"] = api_config_data
    ctx.obj["mode"] = mode
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    if log_level == "null":
        handler = logging.NullHandler()
        logger.addHandler(handler)
    else:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(LOG_FORMAT_STR)
        handler.setFormatter(formatter)
        level_map = {
            "debug": logging.DEBUG,
            "info": logging.INFO,
            "warning": logging.WARNING,
            "critical": logging.CRITICAL
        }
        handler.setLevel(level_map[log_level])
        logger.addHandler(handler)

    ctx.obj["output_directory"] = output_directory
    os.makedirs(ctx.obj["output_directory"], exist_ok=True)
    create_dir = os.path.join(ctx.obj["output_directory"], "create")
    response_dir = os.path.join(ctx.obj["output_directory"], "response")
    update_dir = os.path.join(ctx.obj["output_directory"], "update")
    current_dir = os.path.join(ctx.obj["output_directory"], "current")
    os.makedirs(create_dir, exist_ok=True)
    os.makedirs(response_dir, exist_ok=True)
    os.makedirs(update_dir, exist_ok=True)
    os.makedirs(current_dir, exist_ok=True)
    ctx.obj["create_dir"] = create_dir
    ctx.obj["response_dir"] = response_dir
    ctx.obj["update_dir"] = update_dir
    ctx.obj["current_dir"] = current_dir
    ctx.obj["logger"] = logger


@cli.group()
@click.pass_context
def member(ctx):
    pass


def validate_uuid(ctx, param, value):
    if value:
        try:
            return str(uuid.UUID(value, version=4))
        except Exception as exc:
            raise click.BadParameter("Not UUID Format: %s" % exc)


def iter_json_files(filename, dirs_to_check=[], include_filepath=False):
    paths_to_check = []
    if os.path.isfile(filename):
        paths_to_check.append(filename)
    else:
        for d in dirs_to_check:
            os.makedirs(d, exist_ok=True)
            fpath = os.path.join(d, filename)
            if os.path.isfile(fpath):
                paths_to_check.append(fpath)
    for file_path in paths_to_check:
        with open(file_path, "r") as fp:
            try:
                data = json.load(fp)
            except:
                pass
            else:
                if include_filepath:
                    yield file_path, data
                else:
                    yield data


@member.command()
@click.option("--defaults", type=click.Path(exists=True), default=os.path.join(CONF_DIR, "defaults.json"), show_default=True)
@click.option("--from-json", type=click.Path())
@click.option("--external-id", type=click.UNPROCESSED, callback=validate_uuid)
@click.option("--first-name", type=str)
@click.option("--last-name", type=str)
@click.option("--email", type=str)
@click.option("--plan-code", type=str, default="DWA57Q83", show_default=True)
@click.option("--dry-run", is_flag=True)
@click.pass_context
def create(ctx, defaults, from_json, external_id, first_name, last_name, email, plan_code, dry_run):
    logger = ctx.obj["logger"]
    logger.debug("Creating Primary Member Invoked")
    options = {}
    if defaults:
        try:
            options.update(load_config(defaults))
        except Exception as exc:
            raise click.BadOptionUsage("defaults", str(exc))
    if from_json:
        for json_data in iter_json_files(from_json, dirs_to_check=[ctx.obj["create_dir"]]):
            options.update(json_data)
            break
        else:
            raise click.BadOptionUsage("from_json", "File Not Found")
    if external_id is not None:
        options.update(externalID=external_id)
    elif "externalID" not in options:
        external_id=str(uuid.uuid4())
        logger.debug(f"Generated external id {external_id}")
        options.update(externalID=external_id)
    if "name" not in options:
        options["name"] = {}
    if first_name is not None:
        options["name"]["First"] = first_name
    elif "First" not in options["name"]:
        options["name"]["First"] = names.get_first_name()
    if last_name is not None:
        options["name"]["Last"] = last_name
    elif "Last" not in options["name"]:
        options["name"]["Last"] = names.get_last_name()
    if email is not None:
        options["email"] = email
    elif "email" not in options:
        email = options["name"]["First"][0].lower() + options["name"]["Last"].lower() + "@localhost.com"
        options["email"] = email
    if "benefitstart" not in options:
        benefit_start = datetime.datetime.today().replace(hour=0).replace(minute=0).replace(second=0).replace(
            microsecond=0).isoformat()
        options.update(benefitstart=benefit_start)
    if "plancode" not in options:
        options.update(plancode=plan_code)

    logger.debug(f"Created Member Payload:\n{json.dumps(options, indent=4)}")

    from .client import Client
    client = Client(ctx.obj["api_config"]["api"])
    client.validate_member(options)
    logger.debug("Validated Payload")
    filename = "%s_%s.json" % (options["name"]["First"].lower(), options["name"]["Last"].lower())
    if ctx.obj["mode"] == 'test':
        with open(os.path.join(ctx.obj["create_dir"], filename), "w") as fp:
            json.dump(options, fp, indent=4)
    if dry_run:
        #click.echo(json.dumps(options, indent=4))
        click.echo(options["externalID"])
    else:
        from .client import Client
        client = Client(ctx.obj["api_config"]["api"])
        logger.debug("Client Token: %s" % client.access_token)
        member = client.create_primary_member(options)
        member_data = member._data
        if ctx.obj["mode"] == 'test':
            with open(os.path.join(ctx.obj["response_dir"], filename), "w") as fp:
                json.dump(member_data, fp, indent=4)
            with open(os.path.join(ctx.obj["current_dir"], filename), "w") as fp:
                json.dump(member_data, fp, indent=4)
        click.echo(member_data["externalID"])


@member.command()
@click.argument("json-filename", type=click.Path())
@click.pass_context
def get_id(ctx, json_filename):
    logger = ctx.obj["logger"]
    logger.debug(f"Getting id from {json_filename}")
    for json_data in iter_json_files(
            json_filename, dirs_to_check=[ctx.obj["current_dir"], ctx.obj["create_dir"], ctx.obj["response_dir"]]):
        if "externalID" in json_data:
            click.echo(json_data["externalID"])
            break
    else:
        raise click.BadOptionUsage("from_json", "File Not Found")


@member.command()
@click.argument("external_id", type=click.UNPROCESSED, callback=validate_uuid)
@click.option("--refresh-current", is_flag=True)
@click.pass_context
def inspect(ctx, external_id, refresh_current):
    logger = ctx.obj["logger"]
    logger.debug(f"Inspecting Primary Member {external_id}")
    from .client import Client
    client = Client(ctx.obj["api_config"]["api"])
    logger.debug("Client Token: %s" % client.access_token)
    member = client.get_primary_member(external_id)
    member_data = member._data
    if refresh_current:
        filename = "%s_%s.json" % (member.name.first.lower(), member.name.last.lower())
        current_filepath = os.path.join(ctx.obj["current_dir"], filename)
        with open(current_filepath, "w") as fp:
            json.dump(member_data, fp, indent=4)
    click.echo(json.dumps(member_data, indent=4, default=str))


@member.command()
@click.pass_context
def ls(ctx):
    logger = ctx.obj["logger"]
    logger.debug("Listing Primary Members Invoked")
    click.echo("Listing Primary Members")


def validate_jsonstr(ctx, param, value):
    if value:
        try:
            return json.loads(value)
        except Exception as exc:
            raise click.BadParameter("%s" % exc)


@member.command()
@click.argument("external-id")
@click.option("--json-string", type=click.UNPROCESSED, callback=validate_jsonstr)
@click.option("--json-file", type=click.Path())
@click.option("--dry-run", is_flag=True)
@click.pass_context
def update(ctx, external_id, json_string, json_file, dry_run):
    logger = ctx.obj["logger"]
    logger.debug("Update Primary Member Invoked")
    update_data = None
    if json_string and json_file:
        raise click.UsageError("Cannot use --json-string and --json-file together")
    if json_string:
        update_data = json_string
    elif json_file:
        for filepath, json_data in iter_json_files(json_file, dirs_to_check=[ctx.obj["update_dir"]], include_filepath=True):
            update_data = json_data
            break
        else:
            raise click.BadOptionUsage("json_file", "File Not Found")
    if update_data is None:
        raise click.UsageError("--json-string or --json-file required")
    from .client import Client
    client = Client(ctx.obj["api_config"]["api"])
    logger.debug("Client Token: %s" % client.access_token)
    member = client.get_primary_member(external_id)
    if "externalID" in update_data:
        del update_data["externalID"]
    response_data = member.update(dry_run=dry_run, **update_data)
    response_data.update(externalID=external_id)
    if ctx.obj["mode"] == 'test':
        with open(filepath, "w") as fp:
            json.dump(response_data, fp, indent=4)
        current_filepath = os.path.join(ctx.obj["current_dir"], os.path.basename(filepath))
        with open(current_filepath, "w") as fp:
            json.dump(response_data, fp, indent=4)
    click.echo(json.dumps(response_data, indent=4))

@member.command()
@click.pass_context
@click.argument("external_id", type=click.UNPROCESSED, callback=validate_uuid)
@click.argument("plancode", type=str)
@click.option("--dry-run", is_flag=True)
def add_policy(ctx, external_id, plancode, dry_run):
    logger = ctx.obj["logger"]
    logger.debug("Create Policy Command Invoked")
    from .client import Client
    client = Client(ctx.obj["api_config"]["api"])
    logger.debug("Client Token: %s" % client.access_token)
    member = client.get_primary_member(external_id)
    response = member.create_policy(plancode, dry_run=dry_run)
    filename = "%s_%s.json" % (member.name.first.lower(), member.name.last.lower())
    current_filepath = os.path.join(ctx.obj["current_dir"], filename)
    if ctx.obj["mode"] == 'test':
        with open(current_filepath, "w") as fp:
            json.dump(member._data, fp, indent=4)
    click.echo(json.dumps(response, indent=4))


@member.command()
@click.argument("external-id", type=click.UNPROCESSED, callback=validate_uuid)
@click.option("--dry-run", is_flag=True)
@click.pass_context
def rm(ctx, external_id, dry_run):
    logger = ctx.obj["logger"]
    logger.debug("Remove Policy Command Invoked")
    from .client import Client
    client = Client(ctx.obj["api_config"]["api"])
    member = client.get_primary_member(external_id)
    response = member.deactivate_policies(dry_run=dry_run)
    click.echo(json.dumps(response, indent=4))

