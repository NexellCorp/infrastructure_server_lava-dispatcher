import logging

from lava_dispatcher.actions import BaseAction, null_or_empty_schema


class cmd_nexell_reset_or_reboot(BaseAction):

    parameters_schema = null_or_empty_schema

    def run(self):
        logging.debug("cmd_nexell_reset_or_reboot run")
        self.client.target_device.nexell_reset_or_reboot()
