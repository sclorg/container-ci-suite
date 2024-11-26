# -*- coding: utf-8 -*-
#
# Copyright Contributors to the Conu project.
# SPDX-License-Identifier: MIT
#

from __future__ import print_function, unicode_literals


class ContainerCIException(Exception):
    """ Generic exception when something goes wrong """


class ContainerCITimeout(ContainerCIException):
    pass


class ContainerCICountExceeded(ContainerCIException):
    pass
