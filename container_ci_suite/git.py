# MIT License
#
# Copyright (c) 2018-2019 Red Hat, Inc.

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import logging
import os

from pathlib import Path
from git import Repo


logging.basicConfig(format="%(levelname)s:%(message)s", level=logging.DEBUG)
logger = logging.getLogger(__name__)


class Git(object):

    def __init__(self, path: Path):
        self.path: Path = path
        self._repo = None
        logger.info(f"Creating git repo in path {path}")
        self.path.mkdir()

    @property
    def repo(self):
        if not self._repo:
            self._repo = Repo.init(self.path)
            assert not self._repo.bare
        return self._repo

    def add_files(self):
        """
        Function adds all files to git
        """
        print(f"WOrking dir {os.getcwd()}")
        self.repo.git.add(all=True)

    def add_global_config(self, username: str, mail: str):
        """
        Function adds username and mail to git config file
        :param username: str, Specify username added to git config file
        :param mail: str, Specify mail added to git config file
        """
        logger.info(f"Adding to repo username {username} and email {mail}")
        self.repo.config_writer().set_value("user", "name", username).release()
        self.repo.config_writer().set_value("user", "email", mail).release()

    def commit_files(self, commit_command: str = "-am", message: str = "init commit"):
        """
        Commit files to repo defined by path
        :param commit_command: str, Default commit command is -am
        :param message: str, Commit message. Default is "init commit"
        """
        logger.info(f"Commit changes to git repo by commit command message {message}")
        self.repo.git.commit(commit_command, message)

    def create_repo(self, commit_command: str, message: str, username: str = None, mail: str = None):
        """
        Function adds files into repository, updates global configuration file with username and mail
        and commit changes to the repository
        :param commit_command: str, define commit_command. Default is '-am'
        :param message: str, define commit message. Default is 'init commit'
        :param username: str, define username which will be added to git config
        :param mail: str, define mail which will be added to git config
        """
        os.chdir(self.path)
        if username and mail:
            self.add_global_config(username=username, mail=mail)
        self.add_files()
        self.commit_files(commit_command, message=message)
