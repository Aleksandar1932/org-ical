import glob
import logging
import os
import sys
import tempfile
from argparse import Namespace
from pathlib import Path
from pprint import pprint
from shutil import copy2

from omegaconf import OmegaConf

from org_ical.ics_gcal import main
from org_ical.utils import Strategy, get_logger


def setup():
    logger = get_logger("setup")
    logger.info("setting up org-ical")
    home_dir = os.path.expanduser("~")
    config_dir = os.path.join(home_dir, ".config/org-ical")
    os.makedirs(config_dir, exist_ok=True)

    if not os.path.exists(os.path.join(config_dir, "config.yaml")):
        default_config = {
            "root_org_dir": os.path.join(home_dir, "org"),
            "strategy": Strategy.WHITELIST,
            "whitelist": ["journal.org"],
            "blacklist": [],
            "calendar": "testcalexport",
            "application_name": "gcal-emacs",
            "secret_path": "client_secret.json",
        }

        config = OmegaConf.create(default_config)
        with open(os.path.join(config_dir, "config.yaml"), "w") as config_file:
            OmegaConf.save(config=config, f=config_file.name)

    config = OmegaConf.load(os.path.join(config_dir, "config.yaml"))
    os.environ["CLIENT_SECRET_FILE"] = os.path.abspath(config.secret_path)
    logger.debug("secret path " + os.getenv("CLIENT_SECRET_FILE"))
    os.environ["APPLICATION_NAME"] = config.application_name
    logger.debug("application name " + os.getenv("APPLICATION_NAME"))
    logger.info("Created default config")

    return config_dir


if __name__ == "__main__":
    config_dir = setup()
    config = OmegaConf.load(os.path.join(config_dir, "config.yaml"))

    logger = get_logger("export")
    os.chdir(config.root_org_dir)
    with tempfile.TemporaryDirectory() as td:
        for file in glob.glob("**/*.org", recursive=True):
            skip = False
            if (
                config.strategy == Strategy.WHITELIST.name
                and file not in config.whitelist
            ):
                skip = True
            if config.strategy == Strategy.BLACKLIST.name and file in config.blacklist:
                skip = True

            if skip:
                logger.debug(f"Skipping {file}")
                continue
            copy2(file, os.path.join(td, file))

        os.chdir(td)

        # setup org-icalendar
        with open("test.el", "w") as testel:
            logger.debug("Dumping test.el")
            testel.write(
                """(setq org-icalendar-include-todo '(all))\n(setq org-icalendar-use-scheduled '(event-if-todo event-if-not-todo))\n(setq org-icalendar-use-deadline '(event-if-todo event-if-not-todo))"""
            )

        # exporting to ics
        for file in os.listdir(td):
            if file.endswith("org"):
                logger.info(f"Exporting {file} to ics")
                os.system(
                    f'emacs {file} --batch -l test.el --eval "(org-icalendar-export-to-ics)"'
                )

        for file in os.listdir(td):
            if file.endswith(".ics"):
                logger.info(f"Creating events for {file}")
                args = Namespace(ics=file, cal=config.calendar)
                main(args)
