import argparse
import json
import logging
import os
import sys
import yaml

from json_schema_validator.errors import ValidationError
from lava.tool.command import Command
from lava.tool.errors import CommandError
from lava.dispatcher.node import NodeDispatcher
import lava_dispatcher.config
from lava_dispatcher.config import get_config, get_device_config, list_devices
from lava_dispatcher.job import LavaTestJob, validate_job_data
from lava_dispatcher.pipeline.parser import JobParser
from lava_dispatcher.context import LavaContext
from lava_dispatcher.pipeline.action import Device
from lava_dispatcher.pipeline.device import NewDevice


class SetUserConfigDirAction(argparse.Action):
    def __call__(self, parser, namespace, value, option_string=None):
        lava_dispatcher.config.custom_config_path = value


class SetCustomConfigFile(argparse.Action):
    def __call__(self, parser, namespace, value, option_string=None):
        lava_dispatcher.config.custom_config_file = value


class DispatcherCommand(Command):
    @classmethod
    def register_arguments(cls, parser):
        super(DispatcherCommand, cls).register_arguments(parser)
        parser.add_argument(
            "--config-dir",
            default=None,
            action=SetUserConfigDirAction,
            help="Configuration directory override (currently %(default)s")
        parser.add_argument(
            "--config",
            default=None,
            action=SetCustomConfigFile,
            help="Custom config file")


class devices(DispatcherCommand):
    """
    Lists all the configured devices in this LAVA instance.
    """
    def invoke(self):
        for d in list_devices():
            print d


def run_legacy_job(job_data, oob_file, config, output_dir, validate):

    if os.getuid() != 0:
        logging.error("lava dispatch has to be run as root")
        exit(1)

    json_job_data = json.dumps(job_data)
    job = LavaTestJob(json_job_data, oob_file, config, output_dir)

    # FIXME Return status
    if validate:
        try:
            validate_job_data(job.job_data)
        except ValidationError as e:
            print e
    else:
        job.run()


def get_pipeline_runner(job):
    # additional arguments are now inside the context

    def run_pipeline_job(job_data, oob_file, config, output_dir, validate_only):
        # pipeline actions will add their own handlers.
        yaml_log = logging.getLogger("YAML")
        yaml_log.setLevel(logging.DEBUG)
        std_log = logging.getLogger("ASCII")

        stdhandler = logging.StreamHandler(oob_file)
        stdhandler.setLevel(logging.INFO)
        formatter = logging.Formatter('"%(asctime)s"\n%(message)s')
        stdhandler.setFormatter(formatter)
        std_log.addHandler(stdhandler)

        try:
            job.validate(simulate=validate_only)
            if not validate_only:
                job.run()
        except lava_dispatcher.pipeline.JobError as e:
            print(e)
            sys.exit(2)
    return run_pipeline_job


class dispatch(DispatcherCommand):
    """
    Run test scenarios on virtual and physical hardware
    """

    @classmethod
    def register_arguments(cls, parser):
        super(dispatch, cls).register_arguments(parser)
        parser.add_argument(
            "--oob-fd",
            default=None,
            type=int,
            help="Used internally by LAVA scheduler.")
        parser.add_argument(
            "--output-dir",
            default=None,
            help="Directory to put structured output in.")
        parser.add_argument(
            "--validate", action='store_true',
            help="Just validate the job file, do not execute any steps.")
        parser.add_argument(
            "--job-id", action='store', default=None,
            help=("Set the scheduler job identifier. "
                  "This alters process name for easier debugging"))
        parser.add_argument(
            "job_file",
            metavar="JOB",
            help="Test scenario file")
        parser.add_argument(
            "--target",
            default=None,
            help="Run the job on a specific target device"
        )

    def invoke(self):

        if self.args.oob_fd:
            oob_file = os.fdopen(self.args.oob_fd, 'w')
        else:
            oob_file = sys.stderr

        # config the python logging
        # FIXME: move to lava-tool
        # XXX: this is horrible, but: undo the logging setup lava-tool has
        # done.
        del logging.root.handlers[:]
        del logging.root.filters[:]
        FORMAT = '<LAVA_DISPATCHER>%(asctime)s %(levelname)s: %(message)s'
        DATEFMT = '%Y-%m-%d %I:%M:%S %p'
        logging.basicConfig(format=FORMAT, datefmt=DATEFMT)
        try:
            self.config = get_config()
        except CommandError as e:
            if self.args.output_dir:
                reporter = os.path.join(self.args.output_dir, "output.txt")
                with open(reporter, 'a') as f:
                    f.write("Configuration error: %s\n" % e)
            else:
                print(e)
            exit(1)
        logging.root.setLevel(self.config.logging_level)

        # Set process id if job-id was passed to dispatcher
        if self.args.job_id:
            try:
                from setproctitle import getproctitle, setproctitle
            except ImportError:
                logging.warning(
                    ("Unable to set import 'setproctitle', "
                     "process name cannot be changed"))
            else:
                setproctitle("%s [job: %s]" % (
                    getproctitle(), self.args.job_id))

        # Load the job file
        job_runner, job_data = self.parse_job_file(self.args.job_file, oob_file)

        # detect multinode and start a NodeDispatcher to work with the LAVA Coordinator.
        if not self.args.validate:
            if 'target_group' in job_data:
                node = NodeDispatcher(job_data, oob_file, self.args.output_dir)
                node.run()
                # the NodeDispatcher has started and closed.
                exit(0)
        if self.args.target is None:
            if 'target' not in job_data:
                logging.error("The job file does not specify a target device. "
                              "You must specify one using the --target option.")
                exit(1)
        else:
            job_data['target'] = self.args.target
        if self.args.output_dir and not os.path.isdir(self.args.output_dir):
            os.makedirs(self.args.output_dir)

        job_runner(job_data, oob_file, self.config, self.args.output_dir, self.args.validate)

    def parse_job_file(self, filename, oob_file):
        if filename.lower().endswith('.yaml') or filename.lower().endswith('.yml'):

            device = NewDevice(self.args.target)
            # FIXME: paths not standardised, so can't work from the command line yet.
            if not device.parameters:
                device = Device(self.args.target)
            parser = JobParser()
            # FIXME: use the parsed device_config instead of the old Device class so it can fail before the Pipeline is made.
            job = parser.parse(open(filename), device, output_dir=self.args.output_dir)
            # device.check_config(job)
            if 'target_group' in job.parameters:
                raise RuntimeError("Pipeline dispatcher does not yet support MultiNode")
            # TODO: job.parameters isn't really needed in the call to the context, remove later.
            job.context = LavaContext(self.args.target, self.config, oob_file, job.parameters, self.args.output_dir)
            return get_pipeline_runner(job), job.parameters

        # everything else is assumed to be JSON
        return run_legacy_job, json.load(open(filename))


class DeviceCommand(DispatcherCommand):

    @classmethod
    def register_arguments(cls, parser):
        super(DeviceCommand, cls).register_arguments(parser)
        parser.add_argument('device')

    @property
    def device_config(self):
        try:
            return get_device_config(self.args.device)
        except Exception:
            raise CommandError("no such device: %s" % self.args.device)


class connect(DeviceCommand):

    def invoke(self):
        os.execlp(
            'sh', 'sh', '-c', self.device_config.connection_command)


class power_cycle(DeviceCommand):

    def invoke(self):
        command = self.device_config.hard_reset_command
        if not command:
            raise CommandError(
                "%s does not have a power cycle command configured" %
                self.args.device)
        os.system(command)
