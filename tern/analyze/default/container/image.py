# -*- coding: utf-8 -*-
#
# Copyright (c) 2019-2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

"""
Analyze the container image in default mode
"""

import docker
import logging
import subprocess  # nosec

from tern.classes.notice import Notice
from tern.classes.docker_image import DockerImage
from tern.utils import constants
from tern.analyze.default.container import single_layer
from tern.analyze.default.container import multi_layer
from tern.analyze.default.dockerfile import helpers as dhelper
from tern.load import docker_api
from tern.report import formats


# global logger
logger = logging.getLogger(constants.logger_name)


def load_base_image():
    '''Create base image from dockerfile instructions and return the image'''
    base_image, dockerfile_lines = dhelper.get_dockerfile_base()
    # try to get image metadata
    if docker_api.dump_docker_image(base_image.repotag):
        # now see if we can load the image
        try:
            base_image.load_image()
        except (NameError,
                subprocess.CalledProcessError,
                IOError,
                docker.errors.APIError,
                ValueError,
                EOFError) as error:
            logger.warning('Error in loading base image: %s', str(error))
            base_image.origins.add_notice_to_origins(
                dockerfile_lines, Notice(str(error), 'error'))
    return base_image


def load_full_image(image_tag_string, digest_string):
    '''Create image object from image name and tag and return the object'''
    test_image = DockerImage(image_tag_string, digest_string)
    failure_origin = formats.image_load_failure.format(
        testimage=test_image.repotag)
    try:
        test_image.load_image()
    except (NameError,
            subprocess.CalledProcessError,
            IOError,
            docker.errors.APIError,
            ValueError,
            EOFError) as error:
        logger.warning('Error in loading image: %s', str(error))
        test_image.origins.add_notice_to_origins(
            failure_origin, Notice(str(error), 'error'))
    return test_image


def analyze(image_obj, redo=False, driver=None):
    """ Steps to analyze a container image (we assume it is a DockerImage
    object for now)
    1. Analyze the first layer to get a baseline list of packages
    3. Analyze subsequent layers
    4. Return the final image with all metadata filled in
    Options:
        redo: do not use the cache; False by default
        driver: mount using the chosen driver;
                If no driver is provided, we will use the kernel's
                overlayfs driver (only available with Linux mainline
                kernel version 4.0 or later)"""
    # set up empty master list of packages
    master_list = []
    # Analyze the first layer and get the shell
    shell = single_layer.analyze_first_layer(image_obj, master_list, redo)
    # Analyze the remaining layers if there are more
    if len(image_obj.layers) > 1:
        multi_layer.analyze_subsequent_layers(
            image_obj, shell, master_list, redo, driver)
    return image_obj
