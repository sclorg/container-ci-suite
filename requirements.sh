#!/bin/bash

set -ex

dnf install -y --nodocs gcc rpm-devel make git python3-devel

dnf clean all
