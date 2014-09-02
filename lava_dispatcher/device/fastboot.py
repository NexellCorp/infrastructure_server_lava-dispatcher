# Copyright (C) 2014 Linaro Limited
#
# Author: Tyler Baker <tyler.baker@linaro.org>
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
# Derived From: dummy.py
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
# along
# with this program; if not, see <http://www.gnu.org/licenses>.

import contextlib
import logging
import subprocess

from lava_dispatcher.device.target import Target
import lava_dispatcher.device.fastboot_drivers as drivers
from lava_dispatcher import deployment_data
from lava_dispatcher.client.base import (
    NetworkCommandRunner,
)
from lava_dispatcher.errors import (
    CriticalError,
)


class FastbootTarget(Target):

    def __init__(self, context, config):
        super(FastbootTarget, self).__init__(context, config)
        self.proc = None
        self._target_type = None
        self._booted = False
        self._reset_boot = False
        self._image_deployment = False
        self._ramdisk_deployment = False
        self._use_boot_cmds = False

        driver = self.config.fastboot_driver
        if driver is None:
            raise CriticalError(
                "Required configuration entry missing: fastboot_driver")

        driver_class = drivers.__getattribute__(driver)

        self.driver = driver_class(self)

    def deploy_linaro_kernel(self, kernel, ramdisk, dtb, modules, rootfs, nfsrootfs,
                             bootloader, firmware, bl1, bl2, bl31, rootfstype,
                             bootloadertype, target_type):
        self._target_type = target_type
        self._use_boot_cmds = True
        if rootfs is not None:
            self._image_deployment = True
        else:
            self._ramdisk_deployment = True
        self.deployment_data = deployment_data.get(self._target_type)
        self._enter_fastboot()
        self.driver.deploy_linaro_kernel(kernel, ramdisk, dtb, modules, rootfs, nfsrootfs,
                                         bootloader, firmware, bl1, bl2, bl31, rootfstype,
                                         bootloadertype, self._target_type, self.scratch_dir)

    def deploy_android(self, boot, system, userdata, rootfstype,
                       bootloadertype, target_type):
        self._target_type = target_type
        self._image_deployment = True
        self.deployment_data = deployment_data.get(self._target_type)
        self._enter_fastboot()
        self.driver.deploy_android(boot, system, userdata, rootfstype,
                                   bootloadertype, self._target_type,
                                   self.scratch_dir)

    def get_device_version(self):
        # this is tricky, because fastboot does not have a visible version
        # number. For now let's use just the adb version number.
        return subprocess.check_output(
            "%s version | sed 's/.* version //'" % self.config.adb_command,
            shell=True
        ).strip()

    def is_booted(self):
        return self._booted

    def reset_boot(self):
        self._reset_boot = True

    def power_on(self):
        if self._booted and self._target_type != 'android':
            self._setup_prompt()
            return self.proc
        if self.proc is not None:
            logging.warning('device already powered on, powering off first')
            self.power_off(self.proc)
            self.proc = None
        self._enter_fastboot()
        if self._use_boot_cmds:
            boot_cmds = ''.join(self._load_boot_cmds(default=self.driver.get_default_boot_cmds()))
            self.driver.boot(boot_cmds)
        else:
            self.driver.boot()
        if self.proc is None:
            self.proc = self.driver.connect()
        self._auto_login(self.proc)
        self._wait_for_prompt(self.proc, self.config.test_image_prompts,
                              self.config.boot_linaro_timeout)
        self._setup_prompt()
        self._booted = True
        return self.proc

    def power_off(self, proc):
        super(FastbootTarget, self).power_off(proc)
        if self.config.power_off_cmd:
            self.context.run_command(self.config.power_off_cmd)
        self.driver.finalize(proc)

    @contextlib.contextmanager
    def file_system(self, partition, directory):
        if self._reset_boot:
            self._booted = False
            self._reset_boot = False
            raise Exception("Operation timed out, resetting platform!")
        if not self._booted:
            if self._target_type == 'android':
                self.context.client.boot_linaro_android_image()
            else:
                self.context.client.boot_linaro_image()
        if self._image_deployment:
            if self._target_type != 'android':
                pat = self.tester_ps1_pattern
                incrc = self.tester_ps1_includes_rc
                runner = NetworkCommandRunner(self, pat, incrc)
                with self._python_file_system(runner, directory, pat) as root:
                    logging.debug("Accessing the file system at %s" % root)
                    yield root
            else:
                with self.driver.adb_file_system(partition, directory) as root:
                    logging.debug("Accessing the file system at %s", root)
                    yield root
        else:
                pat = self.tester_ps1_pattern
                incrc = self.tester_ps1_includes_rc
                runner = NetworkCommandRunner(self, pat, incrc)
                with self._busybox_file_system(runner, directory) as root:
                    logging.debug("Accessing the file system at %s" % root)
                    yield root

    def _enter_fastboot(self):
        # Device needs to be forced into fastboot mode
        if not self.driver.in_fastboot():
            if self.config.fastboot_driver == 'capri' or \
               self.config.fastboot_driver == 'pxa1928dkb':
                # Connect to serial
                self.proc = self.driver.connect()
                # Hard reset the platform
                if self.config.hard_reset_command:
                    self._hard_reboot(self.proc)
                else:
                    self._soft_reboot(self.proc)
                # Enter u-boot
                self._enter_bootloader(self.proc)
                # Enter fastboot mode
                self.proc.sendline(self.config.start_fastboot_command)
            else:
                # Enter fastboot mode
                self.driver.enter_fastboot()

    def _setup_prompt(self):
        self.proc.sendline("")
        self.proc.sendline("")
        self.proc.sendline('export PS1="%s"' % self.tester_ps1)

target_class = FastbootTarget
