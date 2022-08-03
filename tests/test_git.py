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


import os

from pathlib import Path
import tempfile


from container_ci_suite.git import Git


class TestContainerCISuiteGit(object):

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp(suffix="ccs")
        self.git = Git(path=Path(os.path.join(self.tmpdir, "test_git")))
        (self.git.path / "barfoo").touch()

    def test_git_init(self):
        assert os.path.isdir(self.tmpdir)
        assert self.git.path.exists()
        assert (self.git.path / "barfoo").exists()
        self.git.repo
        assert self.git._repo

    def test_git_add_files(self):
        self.git.add_files()
        assert self.git._repo
        assert (self.git.path / ".git").is_dir()

    def test_git_config_settings(self):
        self.git.add_global_config(username="foo", mail="foo@bar")
        config_reader = self.git.repo.config_reader()
        assert config_reader
        assert config_reader.get_value("user", "name") == "foo"
        assert config_reader.get_value("user", "email") == "foo@bar"

    def test_create_repo_file(self):
        self.git.create_repo(commit_command="-m", message="important", username="foo", mail="foo@bar")
        assert self.git._repo
        assert (self.git.path / ".git").is_dir()
        config_reader = self.git.repo.config_reader()
        assert config_reader
        assert config_reader.get_value("user", "name") == "foo"
        assert config_reader.get_value("user", "email") == "foo@bar"
        commit = self.git.repo.head.commit
        assert commit
        assert commit.message.strip() == "important"
        assert commit.author.name == "foo"

    def tear_down(self):
        os.rmdir(self.tmpdir)
