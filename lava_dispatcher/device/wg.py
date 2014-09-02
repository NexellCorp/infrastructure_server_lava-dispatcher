# Copyright (C) 2014 Linaro Limited
#
# Author: Dave Pigott <dave.pigott@linaro.org>
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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.    See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along
# with this program; if not, see <http://www.gnu.org/licenses>.

import pexpect
import os
import logging
from time import sleep
from contextlib import contextmanager

from lava_dispatcher.device.master import MasterImageTarget
from lava_dispatcher.utils import extract_tar
from lava_dispatcher.errors import (
    CriticalError,
    OperationFailed,
)


class WGTarget(MasterImageTarget):

    def __init__(self, context, config):
        super(WGTarget, self).__init__(context, config)

        self.test_bl1 = None
        self.test_fip = None

        if (self.config.bl1_image_filename is None or
                self.config.bl1_image_files is None or
                self.config.fip_image_filename is None or
                self.config.fip_image_files is None or
                self.config.wg_bl1_path is None or
                self.config.wg_bl1_backup_path is None or
                self.config.wg_fip_path is None or
                self.config.wg_fip_backup_path is None or
                self.config.wg_usb_mass_storage_device is None):

            raise CriticalError(
                "WG devices must specify all "
                "of the following configuration variables: "
                "bl1_image_filename, bl1_image_files, "
                "fip_image_filename, fip_image_files, "
                "wg_bl1_path, wg_bl1_bacup_path "
                "wg_fip_path, wg_fip backup_path "
                "wg_usb_mass_storage_device")

    ##################################################################
    # methods inherited from MasterImageTarget and overriden here
    ##################################################################

    def _load_test_firmware(self):
        with self._mcc_setup() as mount_point:
            self._install_test_firmware(mount_point)

    def _load_master_firmware(self):
        with self._mcc_setup() as mount_point:
            self._restore_firmware_backup(mount_point)

    def _deploy_android_tarballs(self, master, boot, system, data):
        super(WGTarget, self)._deploy_android_tarballs(master, boot,
                                                       system, data)
        # android images have boot files inside boot/ in the tarball
        self._extract_firmware_from_tarball(boot)

    def _deploy_tarballs(self, boot_tgz, root_tgz, rootfstype):
        super(WGTarget, self)._deploy_tarballs(boot_tgz, root_tgz,
                                               rootfstype)
        self._extract_firmware_from_tarball(boot_tgz)

    ##################################################################
    # implementation-specific methods
    ##################################################################

    @contextmanager
    def _mcc_setup(self):
        """
        This method will manage the context for manipulating the USB mass
        storage device, and pass the mount point where the USB MSD is mounted
        to the inner block.

        Example:

            with self._mcc_setup() as mount_point:
                do_stuff_with(mount_point)


        This can be used for example to copy files from/to the USB MSD.
        Mounting and unmounting is managed by this method, so the inner block
        does not have to handle that.
        """

        mount_point = os.path.join(self.scratch_dir, 'wg-usb')
        if not os.path.exists(mount_point):
            os.makedirs(mount_point)

        self._enter_mcc()
        self._mount_usbmsd(mount_point)
        try:
            yield mount_point
        finally:
            self._umount_usbmsd(mount_point)
            self._leave_mcc()

    def _enter_mcc(self):
        match_id = self.proc.expect([
            self.config.wg_stop_autoboot_prompt,
            pexpect.EOF, pexpect.TIMEOUT], timeout=120)
        if match_id != 0:
            msg = 'Unable to intercept MCC boot prompt'
            logging.error(msg)
            raise OperationFailed(msg)
        self.proc.sendline("")
        match_id = self.proc.expect([
            'Cmd>',
            pexpect.EOF, pexpect.TIMEOUT], timeout=120)
        if match_id != 0:
            msg = 'MCC boot prompt not found'
            logging.error(msg)
            raise OperationFailed(msg)

    def _mount_usbmsd(self, mount_point):
        self.proc.sendline("USB_ON")
        self.proc.expect(['Cmd>'])

        # wait a few seconds so that the kernel on the host detects the USB
        # mass storage interface exposed by the WG
        sleep(5)

        usb_device = self.config.wg_usb_mass_storage_device

        # Try to mount the MMC device. If we detect a failure when mounting. Toggle
        # the USB MSD interface, and try again. If we fail again, raise an OperationFailed
        # except to retry to the boot process.
        if self.context.run_command('mount %s %s' % (usb_device, mount_point)) != 0:
            self.proc.sendline("USB_OFF")
            self.proc.expect(['Cmd>'])
            self.proc.sendline("USB_ON")
            self.proc.expect(['Cmd>'])
            sleep(5)
            if self.context.run_command('mount %s %s' % (usb_device, mount_point)) != 0:
                msg = "Failed to mount MMC on host"
                logging.exception(msg)
                raise OperationFailed(msg)

    def _umount_usbmsd(self, mount_point):
        self.context.run_command_with_retries('umount %s' % mount_point)
        self.proc.sendline("USB_OFF")
        self.proc.expect(['Cmd>'])

    def _leave_mcc(self):
        self.proc.sendline("reboot")

    def _extract_firmware_from_tarball(self, tarball):

        extract_tar(tarball, self.scratch_dir)

        self.test_bl1 = self._copy_first_find_from_list(self.scratch_dir, self.scratch_dir,
                                                        self.config.bl1_image_files,
                                                        self.config.bl1_image_filename)

        self.test_fip = self._copy_first_find_from_list(self.scratch_dir, self.scratch_dir,
                                                        self.config.fip_image_files,
                                                        self.config.fip_image_filename)

    def _restore_firmware_backup(self, mount_point):
        bl1_path = self.config.wg_bl1_path
        bl1 = os.path.join(mount_point, bl1_path)
        bl1_backup_path = self.config.wg_bl1_backup_path
        bl1_backup = os.path.join(mount_point, bl1_backup_path)

        if os.path.exists(bl1_backup):
            # restore the firmware backup
            self.context.run_command_with_retries('cp %s %s' % (bl1_backup, bl1))
        else:
            # no existing backup yet means that this is the first time ever;
            # the firmware in there is the good one, and we backup it up.
            self.context.run_command_with_retries('cp %s %s' % (bl1, bl1_backup))

        fip_path = self.config.wg_fip_path
        fip = os.path.join(mount_point, fip_path)
        fip_backup_path = self.config.wg_fip_backup_path
        fip_backup = os.path.join(mount_point, fip_backup_path)

        if os.path.exists(fip_backup):
            # restore the firmware backup
            self.context.run_command_with_retries('cp %s %s' % (fip_backup, fip))
        else:
            # no existing backup yet means that this is the first time ever;
            # the firmware in there is the good one, and we backup it up.
            self.context.run_command_with_retries('cp %s %s' % (fip, fip_backup))

    def _install_test_firmware(self, mount_point):
        bl1_path = self.config.wg_bl1_path
        bl1 = os.path.join(mount_point, bl1_path)

        if os.path.exists(self.test_bl1):
            self.context.run_command('cp %s %s' % (self.test_bl1, bl1))
        else:
            raise CriticalError("No path to bl1 firmware")

        fip_path = self.config.wg_fip_path
        fip = os.path.join(mount_point, fip_path)

        if os.path.exists(self.test_fip):
            self.context.run_command('cp %s %s' % (self.test_fip, fip))
        else:
            raise CriticalError("No path to fip firmware")


target_class = WGTarget
