import logging
import contextlib
import subprocess
import re
import time
import glob
import os

from lava_dispatcher.device.bootloader import (
    BootloaderTarget,
)
from lava_dispatcher.errors import (
    CriticalError,
)
from lava_dispatcher.downloader import (
    download_image,
)
from lava_dispatcher import deployment_data

from pexpect import TIMEOUT


class NexellTarget(BootloaderTarget):

    def __init__(self, context, config):
        super(NexellTarget, self).__init__(context, config)
        self._usb_device_id = None
        self._master_ps1_pattern = None
        # overriding
        self._scratch_dir = "/tmp"
        self._boot_type = None
        # for file_system
        self._file_system_called = False 

    def nexell_reset_or_reboot(self):
        # after this command, board state is u-boot command line
        logging.info("start command nexell_reset_or_reboot")
        expect_response_list = ["Hit any key to stop", "nxp4330#", "nxp5430#", "- try 'help'", "BAT:", TIMEOUT]
        logging.debug("nexell_reset_or_reboot start...")
        self.proc.sendcontrol('c')
        self.proc.sendline("reboot")
        logging.debug("end of sendline reboot")
        index = self.proc.expect(expect_response_list, timeout=5)
        logging.debug("expect result %d" % index)
        #if index < 5:
        if index < (len(expect_response_list) - 1):
            if index == 4:
                self.proc.sendcontrol('c')
            logging.info("succeed to reboot")
            self.proc.sendline("\n")
        else:
            logging.info("send reset command for bootloader")
            #time.sleep(1)
            self.proc.sendline("reset")
            index = self.proc.expect(expect_response_list, timeout=5)
            if index < (len(expect_response_list) - 1):
                if index == 4:
                    self.proc.sendcontrol('c')
                logging.info("succeed to reset")
                self.proc.sendline("\n")
            else:
                logging.info("board state is unknown")
                raise CriticalError("Unknown Board State!!!")

        time.sleep(1)

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
        print("output1: %s" % output)
        pattern = re.compile(r'nxp[0-9]{4}')
        chip = pattern.search(output).group(0)
        output = subprocess.check_output(
            ["fastboot", "-s", usb_id, "getvar", "product"],
            stderr=subprocess.STDOUT)
        print("output2: %s" % output)
        pattern = re.compile(r'(?P<PRODUCT>product:\s+)(?P<BOARD>[a-zA-Z]+)')
        product = pattern.search(output).group(2)
        print("device id: %s-%s" % (product, chip))
        return ''.join([product, '-', chip])

    def _get_device_map_by_fastboot(self):
        output = subprocess.check_output(["fastboot", "devices", "-l"])
        usb_devices =\
            [device for device in output.split() if device.startswith('usb')]
        device_map = {}
        for usb_device in usb_devices:
            print("usb_device: %s" % usb_device)
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

        time.sleep(2)
        device_map = self._get_device_map_by_fastboot()
        print device_map.keys()
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

    def _check_boot_image_args(self, params):
        print(params.keys())
        if 'type' not in params.keys():
            raise CriticalError("You should add type parameter!")
        if 'check_msg' not in params.keys():
            raise CriticalError("You should add check_msg parameter!")
        if 'timeout' not in params.keys():
            raise CriticalError("You should add timeout parameter!")

    def _boot_raw_image(self, params):
        if 'commands' in params.keys():
            for command in params['commands']:
                print("set commands: " + command)
                self.proc.sendline(command)
        else:
            print("pass commands setting")

    def _check_android_logcat_msg(self, logcat_msg, timeout):
        print("_check_android_logcat_msg: %s, %d" % (logcat_msg, timeout))
        self.proc.sendline("\n")
        self.proc.sendline("\n")
        self.proc.sendline("\n")
        time.sleep(1)
        self.proc.sendline("logcat")
        index = self.proc.expect([logcat_msg, TIMEOUT], timeout=timeout)
        if index != 0:
            raise CriticalError("Timeout for android booting")
        self.proc.sendcontrol('c')
        self.proc.sendcontrol('c')

        print("Complete check android booting")

    def _android_input_event(self, events):
        for event in events:
            logging.info("USER Input Event: %s" % event)
            self.proc.sendline(event)
            time.sleep(1)

    def nexell_boot_image(self, params):
        logging.info("nexell_boot_image")
        self._check_boot_image_args(params)
        self.nexell_reset_or_reboot()

        if params['type'] in ['raw', 'android']:
            self._boot_raw_image(params)

        self.proc.sendline("boot")
        time.sleep(1)
        index = self.proc.expect([params['check_msg'], TIMEOUT], timeout=int(params['timeout']))
        if index != 0:
            raise CriticalError("Timeout for booting")

        if params['type'] == 'android':
            if 'logcat_check_msg' in params.keys() and 'logcat_check_timeout' in params.keys():
                self._check_android_logcat_msg(params['logcat_check_msg'], int(params['logcat_check_timeout']))
            if 'input_event' in params.keys():
                self._android_input_event(params['input_event'])
            self.deployment_data = deployment_data.nexell_android
            self._boot_type = 'android'
            product = self.context.job_data['target'].split('-')[0]
            # self.deployment_data['TESTER_PS1'] = "root@{}:/ #".format(product)
            # self.deployment_data['TESTER_PS1_PATTERN'] = "root@{}:/ #".format(product)
            # print("TESTER_PS1: " + self.deployment_data['TESTER_PS1'])
            self.MASTER_PS1_PATTTERN = "root@{}:/ #".format(product)
            self._master_ps1_pattern = "root@{}:/ #".format(product)
            print("self.MASTER_PS1_PATTERN: %s, _master_ps1_pattern: %s" %
                (self.MASTER_PS1_PATTERN, self._master_ps1_pattern))

    def nexell_android_ready_working(self, params):
        logging.info("nexell_android_ready_working")
        self.proc.sendline(params['display_on_command'])
        if 'input_event' in params.keys():
            self._android_input_event(params['input_event'])

    # overriding
    @contextlib.contextmanager
    def file_system(self, partition, directory):
        logging.info('attempting to access master filesystem %r:%s',
                     partition, directory)
        # yield self.deployment_data['lava_test_dir']
        if self._file_system_called is False:
            subprocess.call(["rm", "-rf", "/tmp/lava"])
            self._file_system_called = True
        yield '/tmp/lava'

    def _push_files_to_target(self, host_dir, target_dir):
        files = os.listdir(host_dir)
        self.proc.sendline("mkdir -p %s" % target_dir)
        self.proc.sendline("chmod -R 777 %s" % target_dir)
        for f in files:
            full = host_dir + '/' + f
            if os.path.isdir(full):
                dest_dir = target_dir + '/' + os.path.basename(full)
                self._push_files_to_target(full, dest_dir)
            else:
                subprocess.call(["adb", "-s", self.config.adb_serialno, "push", full, target_dir])

    def power_on(self):
        logging.info("NexellTarget::power_on()")
        output = subprocess.check_output(["pwd"], stderr=subprocess.STDOUT)
        logging.info("current dir: %s" % output)
        # install lava_test_shells
        target_dir = "/data/lava-%s" % self.context.job_data['target']
        self.proc.sendline("mkdir -p %s" % target_dir)
        self.proc.sendline("chmod -R 777 %s" % target_dir)

        prefix = "/tmp/lava"
        push_files = os.listdir(prefix)

        try:
            subprocess.call(['adb', 'devices'])
        except:
            subprocess.call(['apt-get', 'install', '--yes', 'android-tools-adb'])

        print("adb_serialno: %s" % self.config.adb_serialno)

        self._push_files_to_target(prefix, target_dir)

        self.proc.sendline("chmod -R 777 %s/bin" % target_dir)
        return self.proc


target_class = NexellTarget
