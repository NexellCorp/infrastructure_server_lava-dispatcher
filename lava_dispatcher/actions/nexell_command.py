import logging

from lava_dispatcher.actions import BaseAction, null_or_empty_schema


class cmd_nexell_reset_or_reboot(BaseAction):

    parameters_schema = null_or_empty_schema

    def run(self):
        logging.debug("cmd_nexell_reset_or_reboot run")
        print("cmd_nexell_reset_or_reboot run")
        self.client.nexell_reset_or_reboot()


class cmd_nexell_deploy_image(BaseAction):

    parameters_schema = {
        'type': 'object',
        'properties': {
            'interface': {'type': 'string'},
            'image': {'type': 'string', 'optional': True},
        },
        'additionalProperties': False,
    }

    @classmethod
    def validate_parameters(cls, parameters):
        super(cmd_nexell_deploy_image, cls).validate_parameters(parameters)
        if parameters['interface'] == "fastboot":
            if 'image' not in parameters:
                raise ValueError('must specify image when interface is fastboot')

    def run(self, interface, image=None):
        print("cmd_nexell_deploy_image run")
        self.client.nexell_deploy_image(interface=interface, image=image)
