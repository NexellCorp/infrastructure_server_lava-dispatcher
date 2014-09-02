# Copyright (C) 2011 Linaro Limited
#
# Author: Paul Larson <paul.larson@linaro.org>
#
# This file is part of LAVA Dispatcher.
#
# LAVA Dispatcher is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# LAVA Dispatcher is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses>.

from lava_dispatcher.actions import BaseAction
from lava_dispatcher import deployment_data


class cmd_deploy_linaro_image(BaseAction):

    # This is how the schema for parameters should look, but there are bugs in
    # json_schema_validation that means it doesn't work (see
    # https://github.com/zyga/json-schema-validator/pull/6).

    # parameters_schema = {
    #     'type': [
    #         {
    #             'type': 'object',
    #             'properties': {
    #                 'image': {'type': 'string'},
    #                 },
    #             'additionalProperties': False,
    #             },
    #         {
    #             'type': 'object',
    #             'properties': {
    #                 'hwpack': {'type': 'string'},
    #                 'rootfs': {'type': 'string'},
    #                 'rootfstype': {'type': 'string', 'optional': True, 'default': 'ext3'},
    #                 },
    #             'additionalProperties': False,
    #             },
    #         ],
    #     }

    parameters_schema = {
        'type': 'object',
        'properties': {
            'hwpack': {'type': 'string', 'optional': True},
            'rootfs': {'type': 'string', 'optional': True},
            'image': {'type': 'string', 'optional': True},
            'dtb': {'type': 'string', 'optional': True},
            'customize': {'type': 'object', 'optional': True},
            'rootfstype': {'type': 'string', 'optional': True},
            'bootloadertype': {'type': 'string', 'optional': True,
                               'default': 'u_boot'},
            'login_prompt': {'type': 'string', 'optional': True},
            'password_prompt': {'type': 'string', 'optional': True},
            'username': {'type': 'string', 'optional': True},
            'password': {'type': 'string', 'optional': True},
            'login_commands': {'type': 'array', 'items': {'type': 'string'},
                               'optional': True},
            'role': {'type': 'string', 'optional': True},
        },
        'additionalProperties': False,
    }

    @classmethod
    def validate_parameters(cls, parameters):
        super(cmd_deploy_linaro_image, cls).validate_parameters(parameters)
        if 'hwpack' in parameters:
            if 'rootfs' not in parameters:
                raise ValueError('must specify rootfs when specifying hwpack')
            if 'image' in parameters:
                raise ValueError('cannot specify image and hwpack')
        elif 'image' not in parameters:
            raise ValueError('must specify image if not specifying a hwpack')
        if 'login_prompt' in parameters:
            if 'username' not in parameters:
                raise ValueError('must specify a username when specifying \
                      a login prompt')
        if 'password_prompt' in parameters:
            if 'password' not in parameters:
                raise ValueError('must specify a password when specifying \
                      a password prompt')
        if 'login_prompt' not in parameters or \
           'password_prompt' not in parameters:
            if 'login_commands' in parameters:
                raise ValueError('must specify a login prompt or password \
                      prompt when specifying login commands')

    def run(self, hwpack=None, rootfs=None, image=None, dtb=None,
            rootfstype='ext4', bootloadertype='u_boot', login_prompt=None,
            password_prompt=None, username=None, password=None,
            login_commands=None, customize=None):
        if login_prompt is not None:
            self.client.config.login_prompt = login_prompt
        if password_prompt is not None:
            self.client.config.password_prompt = password_prompt
        if username is not None:
            self.client.config.username = username
        if password is not None:
            self.client.config.password = password
        if login_commands is not None:
            self.client.config.login_commands = login_commands
        if customize is not None:
            self.client.config.customize = customize
        self.client.deploy_linaro(
            hwpack=hwpack, rootfs=rootfs, image=image, dtb=dtb,
            rootfstype=rootfstype, bootloadertype=bootloadertype,)


cmd_deploy_image = cmd_deploy_linaro_image


class cmd_deploy_linaro_android_image(BaseAction):

    parameters_schema = {
        'type': 'object',
        'properties': {
            'boot': {'type': 'string'},
            'system': {'type': 'string', 'optional': True},
            'data': {'type': 'string', 'optional': True},
            'rootfstype': {'type': 'string', 'optional': True,
                           'default': 'ext4'},
            'bootloadertype': {'type': 'string', 'optional': True,
                               'default': 'u_boot'},
            'target_type': {'type': 'string', 'enum': ['ubuntu', 'oe', 'android', 'fedora'],
                            'optional': True, 'default': 'android'},
            'login_prompt': {'type': 'string', 'optional': True},
            'password_prompt': {'type': 'string', 'optional': True},
            'username': {'type': 'string', 'optional': True},
            'password': {'type': 'string', 'optional': True},
            'login_commands': {'type': 'array', 'items': {'type': 'string'},
                               'optional': True},
            'role': {'type': 'string', 'optional': True},
        },
        'additionalProperties': False,
    }

    @classmethod
    def validate_parameters(cls, parameters):
        super(cmd_deploy_linaro_android_image, cls).validate_parameters(parameters)
        if 'login_prompt' in parameters:
            if 'username' not in parameters:
                raise ValueError('must specify a username when specifying \
                      a login prompt')
        if 'password_prompt' in parameters:
            if 'password' not in parameters:
                raise ValueError('must specify a password when specifying \
                      a password prompt')
        if 'login_prompt' not in parameters or \
           'password_prompt' not in parameters:
            if 'login_commands' in parameters:
                raise ValueError('must specify a login prompt or password \
                      prompt when specifying login commands')

    def run(self, boot=None, system=None, data=None, rootfstype='ext4', bootloadertype='u_boot',
            target_type='android', login_prompt=None, password_prompt=None, username=None,
            password=None, login_commands=None):
        if login_prompt is not None:
            self.client.config.login_prompt = login_prompt
        if password_prompt is not None:
            self.client.config.password_prompt = password_prompt
        if username is not None:
            self.client.config.username = username
        if password is not None:
            self.client.config.password = password
        if login_commands is not None:
            self.client.config.login_commands = login_commands
        self.client.deploy_linaro_android(boot=boot, system=system, data=data,
                                          rootfstype=rootfstype,
                                          bootloadertype=bootloadertype,
                                          target_type=target_type)


cmd_deploy_android_image = cmd_deploy_linaro_android_image


class cmd_deploy_linaro_kernel(BaseAction):

    parameters_schema = {
        'type': 'object',
        'properties': {
            'kernel': {'type': 'string', 'optional': False},
            'ramdisk': {'type': 'string', 'optional': True},
            'dtb': {'type': 'string', 'optional': True},
            'modules': {'type': 'string', 'optional': True},
            'rootfs': {'type': 'string', 'optional': True},
            'nfsrootfs': {'type': 'string', 'optional': True},
            'bootloader': {'type': 'string', 'optional': True},
            'firmware': {'type': 'string', 'optional': True},
            'bl1': {'type': 'string', 'optional': True},
            'bl2': {'type': 'string', 'optional': True},
            'bl31': {'type': 'string', 'optional': True},
            'rootfstype': {'type': 'string', 'optional': True},
            'bootloadertype': {'type': 'string', 'optional': True,
                               'default': 'u_boot'},
            'target_type': {'type': 'string', 'enum': ['ubuntu', 'oe', 'android', 'fedora'],
                            'optional': True, 'default': 'oe'},
            'login_prompt': {'type': 'string', 'optional': True},
            'password_prompt': {'type': 'string', 'optional': True},
            'username': {'type': 'string', 'optional': True},
            'password': {'type': 'string', 'optional': True},
            'login_commands': {'type': 'array', 'items': {'type': 'string'},
                               'optional': True},
            'role': {'type': 'string', 'optional': True},
        },
        'additionalProperties': False,
    }

    @classmethod
    def validate_parameters(cls, parameters):
        super(cmd_deploy_linaro_kernel, cls).validate_parameters(parameters)
        if 'kernel' not in parameters:
            raise ValueError('must specify a kernel')
        if 'login_prompt' in parameters:
            if 'username' not in parameters:
                raise ValueError('must specify a username when specifying \
                      a login prompt')
        if 'password_prompt' in parameters:
            if 'password' not in parameters:
                raise ValueError('must specify a password when specifying \
                      a password prompt')
        if 'login_prompt' not in parameters or \
           'password_prompt' not in parameters:
            if 'login_commands' in parameters:
                raise ValueError('must specify a login prompt or password \
                      prompt when specifying login commands')

    def run(self,
            kernel=None, ramdisk=None, dtb=None, modules=None, rootfs=None,
            nfsrootfs=None, bootloader=None, firmware=None, bl1=None, bl2=None,
            bl31=None, rootfstype='ext4', bootloadertype='u_boot', target_type='oe',
            login_prompt=None, password_prompt=None, username=None,
            password=None, login_commands=None):
        if login_prompt is not None:
            self.client.config.login_prompt = login_prompt
        if password_prompt is not None:
            self.client.config.password_prompt = password_prompt
        if username is not None:
            self.client.config.username = username
        if password is not None:
            self.client.config.password = password
        if login_commands is not None:
            self.client.config.login_commands = login_commands
        self.client.deploy_linaro_kernel(
            kernel=kernel, ramdisk=ramdisk, dtb=dtb, modules=modules,
            rootfs=rootfs, nfsrootfs=nfsrootfs, bootloader=bootloader,
            firmware=firmware, bl1=bl1, bl2=bl2, bl31=bl31,
            rootfstype=rootfstype, bootloadertype=bootloadertype,
            target_type=target_type)


cmd_deploy_kernel = cmd_deploy_linaro_kernel


class cmd_dummy_deploy(BaseAction):

    parameters_schema = {
        'type': 'object',
        'properties': {
            'target_type': {'type': 'string', 'enum': ['ubuntu', 'oe', 'android', 'fedora']},
            'role': {'type': 'string', 'optional': True},
        },
        'additionalProperties': False,
    }

    def run(self, target_type):
        device = self.client.target_device
        device.deployment_data = deployment_data.get(target_type)
