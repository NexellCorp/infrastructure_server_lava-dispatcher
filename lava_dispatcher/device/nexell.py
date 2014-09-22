import logging
#import contextlib
import subprocess
import re
import time
import glob

from lava_dispatcher.device.bootloader import (
    BootloaderTarget,
)
from lava_dispatcher.errors import (
    CriticalError,
)
from lava_dispatcher.downloader import (
    download_image,
)
#from lava_dispatcher import deployment_data

from pexpect import TIMEOUT


class NexellTarget(BootloaderTarget):

    def __init__(self, context, config):
        super(NexellTarget, self).__init__(context, config)
        self._usb_device_id = None

    def nexell_reset_or_reboot(self):
        # after this command, board state is u-boot command line
        logging.debug("start command nexell_reset_or_reboot")
        print("nexell_reset_or_reboot start...")
        self.proc.sendline("reboot")
        print("end of sendline reboot")
        index =\
            self.proc.expect(
                ["Hit any key to stop", "- try 'help'", TIMEOUT], timeout=5)
        print("expect result %d" % index)
        if index == 0:
            print("succeed to reboot")
            self.proc.sendline("\n")
        elif index == 1:
            print("send reset command for bootloader")
            self.proc.sendline("reset")
            index =\
                self.proc.expect(["Hit any key to stop", TIMEOUT], timeout=5)
            if index == 0:
                print("succeed to reset")
                self.proc.sendline("\n")
            else:
                print("board state is unknown")
                raise CriticalError("Unknown Board State!!!")

    def _check_host_fastboot(self):
        #sudo apt-get install android-tools-fastboot
        try:
            subprocess.call(['fastboot'])
        except:
            raise \
                CriticalError("can't run fastboot, \
                 you should sudo apt-get install android-tools-fastboot!!!")

    def _get_device_id_from_usb_id(self, usb_id):
        output = subprocess.check_output(
            ["fastboot", "-s", usb_id, "getvar", "chip"],
            stderr=subprocess.STDOUT)
        #print("output1: %s" % output)
        pattern = re.compile(r'nxp[0-9]{4}')
        chip = pattern.search(output).group(0)
        output = subprocess.check_output(
            ["fastboot", "-s", usb_id, "getvar", "product"],
            stderr=subprocess.STDOUT)
        #print("output2: %s" % output)
        pattern = re.compile(r'(?P<PRODUCT>product:\s+)(?P<BOARD>[a-zA-Z]+)')
        product = pattern.search(output).group(2)
        #print("device id: %s-%s" % (product, chip))
        return ''.join([product, '-', chip])

    def _get_device_map_by_fastboot(self):
        output = subprocess.check_output(["fastboot", "devices", "-l"])
        usb_devices =\
            [device for device in output.split() if device.startswith('usb')]
        device_map = {}
        for usb_device in usb_devices:
            #print("usb_device: %s" % usb_device)
            device_map[
                self._get_device_id_from_usb_id(usb_id=usb_device)
            ] = usb_device
        print(device_map.keys())
        return device_map

    def _get_fastboot_device(self):
        target = self.context.job_data['target']
        self.proc.sendline("fastboot")
        index = self.proc.expect(["OTG cable Connected", TIMEOUT], timeout=5)
        if index != 0:
            raise \
                CriticalError("Check %s usb cable connected!!!"
                              % self.config.client_type)

        time.sleep(1)
        device_map = self._get_device_map_by_fastboot()
        if target not in device_map.keys():
            raise \
                CriticalError(
                    "target %s is not connected, check your device!!!"
                    % target)
        self._usb_device_id = device_map[target]

    def _get_flash_image_map(self, image_dir):
        file_name = "%s/partmap.txt" % image_dir
        try:
            f = open(file_name)
        except:
            CriticalError(
                "Can't open %s" % file_name
            )
        parts = []
        for d in f.readlines():
            if not d.startswith('#'):
                parts.append(d.split(':')[1])

        print(parts)

        partmap = {}
        for p in parts:
            pattern = "%s/%s.*" % (image_dir, p)
            n = glob.glob(pattern)
            if len(n) > 0:
                partmap[p] = n[0]

        print(partmap)
        return partmap

    def _fastboot_flash(self, part, image):
        try:
            subprocess.call(
                ['fastboot', '-c', self._usb_device_id, 'flash', part, image]
            )
        except:
            raise \
                CriticalError("can't run fastboot, \
                              part: %s, image: %s!!!") % (part, image)

    def _deploy_image_by_fastboot(self, image_dir):
        print("image_dir: %s" % image_dir)
        partmap = self._get_flash_image_map(image_dir)
        self._fastboot_flash('partmap', image_dir + '/' + 'partmap.txt')
        for k in partmap.keys():
            print("fastboot flash %s %s") % (k, partmap[k])
            self._fastboot_flash(k, partmap[k])

    def _clear_uboot_env(self):
        self.proc.sendline("setenv bootcmd")
        self.proc.sendline("setenv bootargs")
        self.proc.sendline("saveenv")

    def nexell_deploy_image(self, interface, image):
        print("nexell_deploy_image: interface %s, image %s"
              % (interface, image))

        if interface == "fastboot":
            if image is None:
                raise CriticalError("image is None!!!")

            self._check_host_fastboot()
            self._get_fastboot_device()
            fname = download_image(
                url_string=image,
                context=self.context,
                imgdir="/tmp"
            )
            if fname.endswith(".tar"):
                subprocess.call(['tar', 'xf', fname, '-C', '/tmp'])
                fname = fname.replace(".tar", "")

            self._deploy_image_by_fastboot(image_dir=fname)

            self.proc.sendcontrol('c')
            self.proc.sendcontrol('c')
            self.proc.sendline("\n")
            self._clear_uboot_env()
            time.sleep(1)


target_class = NexellTarget
