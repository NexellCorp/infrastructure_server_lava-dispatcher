import logging
import contextlib
import subprocess

from lava_dispatcher.device.bootloader import (
    BootloaderTarget,
)
from lava_dispatcher.errors import (
    CriticalError,
)
from lava_dispatcher import deployment_data

from pexpect import TIMEOUT


class NexellTarget(BootloaderTarget):

    def __init__(self, context, config):
        super(NexellTarget, self).__init__(context, config)

    def nexell_reset_or_reboot(self):
        # after this command, board state is u-boot command line
        logging.debug("start command nexell_reset_or_reboot")
        print("nexell_reset_or_reboot start...")
        self.proc.sendline("reboot")
        print("end of sendline reboot")
        index = self.proc.expect(["Hit any key to stop", "- try 'help'", TIMEOUT], timeout=5)
        print("expect result %d" % index)
        if index == 0:
            print("succeed to reboot")
            self.proc.sendline("\n")
        elif index == 1:
            print("send reset command for bootloader")
            self.proc.sendline("reset")
            index = self.proc.expect(["Hit any key to stop", TIMEOUT], timeout=5)
            if index == 0:
                print("succeed to reset")
                self.proc.sendline("\n")
            else:
                print("board state is unknown")
                raise CriticalError("Unknown Board State!!!")

target_class = NexellTarget
