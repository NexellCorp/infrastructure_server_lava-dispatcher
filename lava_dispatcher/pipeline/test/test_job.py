# Copyright (C) 2014 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
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

import os
import logging
import glob

from lava_dispatcher.pipeline.action import Pipeline, Action, RetryAction, JobError
from lava_dispatcher.pipeline.test.test_basic import Factory
from lava_dispatcher.tests.helper import LavaDispatcherTestCase
from lava_dispatcher.pipeline.actions.deploy.download import DownloaderAction
from lava_dispatcher.pipeline.job import Job
from lava_dispatcher.pipeline.actions.deploy import DeployAction
from lava_dispatcher.pipeline.actions.deploy.mount import (
    MountAction,
    LoopCheckAction,
    LoopMountAction,
    UnmountAction,
    OffsetAction
)
from lava_dispatcher.pipeline.actions.deploy.overlay import OverlayAction, CustomisationAction
from lava_dispatcher.pipeline.actions.deploy.testdef import TestDefinitionAction
from lava_dispatcher.pipeline.actions.boot.kvm import BootAction


class TestBasicJob(LavaDispatcherTestCase):

    def test_basic_actions(self):
        factory = Factory()
        job = factory.create_fake_qemu_job()
        self.assertIsInstance(job, Job)
        self.assertIsInstance(job.pipeline, Pipeline)


class TestKVMSimulation(LavaDispatcherTestCase):

    def test_kvm_simulation(self):
        """
        Build a pipeline which simulates a KVM LAVA job
        without using the formal objects (to avoid validating
        data known to be broken). The details are entirely
        arbitrary.
        """
        pipe = Pipeline()
        action = Action()
        action.name = "deploy_linaro_image"
        action.description = "deploy action using preset subactions in an internal pipe"
        action.summary = "deploy_linaro_image"
        # deliberately unlikely location
        # a successful validation would need to use the cwd
        action.parameters = {"image": "file:///none/images/bad-kvm-debian-wheezy.img"}
        pipe.add_action(action)
        self.assertEqual(action.level, "1")
        deploy_pipe = Pipeline(action)
        action = Action()
        action.name = "downloader"
        action.description = "download image wrapper, including an internal retry pipe"
        action.summary = "downloader"
        deploy_pipe.add_action(action)
        self.assertEqual(action.level, "1.1")
        # a formal RetryAction would contain a pre-built pipeline which can be inserted directly
        retry_pipe = Pipeline(action)
        action = Action()
        action.name = "wget"
        action.description = "do the download with retries"
        action.summary = "wget"
        retry_pipe.add_action(action)
        self.assertEqual(action.level, "1.1.1")
        action = Action()
        action.name = "checksum"
        action.description = "checksum the downloaded file"
        action.summary = "md5sum"
        deploy_pipe.add_action(action)
        self.assertEqual(action.level, "1.2")
        action = Action()
        action.name = "overlay"
        action.description = "apply lava overlay"
        action.summary = "overlay"
        deploy_pipe.add_action(action)
        self.assertEqual(action.level, "1.3")
        action = Action()
        action.name = "boot"
        action.description = "boot image"
        action.summary = "qemu"
        # cmd_line built from device configuration
        action.parameters = {
            'cmd_line': [
                'qemu-system-x86_64',
                '-machine accel=kvm:tcg',
                '-hda'
                '%s' % "tbd",
                '-nographic',
                '-net',
                'nic,model=virtio'
                '-net user'
            ]
        }
        pipe.add_action(action)
        self.assertEqual(action.level, "2")

        action = Action()
        action.name = "simulated"
        action.description = "lava test shell"
        action.summary = "simulated"
        # a formal lava test shell action would include an internal pipe
        # which would handle the run.sh
        pipe.add_action(action)
        self.assertEqual(action.level, "3")
        # a formal submit action would include an internal pipe to handle
        # the XMLRPC, including possible failure states and retries.
        action = Action()
        action.name = "submit"
        action.description = "submit results"
        action.summary = "submit"
        pipe.add_action(action)
        self.assertEqual(action.level, "4")
        self.assertEqual(len(pipe.describe().values()), 8)
        # uncomment to see the YAML dump of the pipeline.
        # print yaml.dump(pipe.describe())


class TestKVMBasicDeploy(LavaDispatcherTestCase):

    def setUp(self):
        super(TestKVMBasicDeploy, self).setUp()
        factory = Factory()
        self.job = factory.create_job('sample_jobs/kvm.yaml', self.config_dir)

    def test_deploy_job(self):
        self.assertEqual(self.job.parameters['output_dir'], self.config_dir)
        self.assertEqual(self.job.pipeline.job, self.job)
        for action in self.job.pipeline.actions:
            if isinstance(action, DeployAction):
                self.assertEqual(action.job, self.job)

    def test_kvm_basic_deploy(self):
        download = None
        mount = None
        checksum = None
        customise = None
        testdef = None
        overlay = None
        unmount = None
        self.assertTrue(os.path.exists(self.job.parameters['output_dir']))
        self.assertEqual(len(self.job.pipeline.describe().values()), 19)  # this will keep changing until KVM is complete.
        for action in self.job.pipeline.actions:
            if isinstance(action, DeployAction):
                # check parser has created a suitable deployment
                download = action.pipeline.children[action.pipeline][0]
                self.assertEqual(download.name, "download_action")
                checksum = action.pipeline.children[action.pipeline][1]
                self.assertEqual(checksum.name, "checksum_action")
                mount = action.pipeline.children[action.pipeline][2]
                self.assertIsInstance(mount.internal_pipeline, Pipeline)
                self.assertEqual(mount.name, "mount_action")
                customise = action.pipeline.children[action.pipeline][3]
                self.assertEqual(customise.name, "customise")
                testdef = action.pipeline.children[action.pipeline][4]
                self.assertEqual(testdef.name, "test-definition")
                overlay = action.pipeline.children[action.pipeline][5]
                self.assertEqual(overlay.name, "lava-overlay")
                unmount = action.pipeline.children[action.pipeline][6]
                self.assertEqual(unmount.name, "umount")
                with self.assertRaises(IndexError):
                    type(action.pipeline.children[action.pipeline][7])
                # FIXME: deployment includes overlaying the test definitions
                # deploy needs to download with retry
                self.assertTrue(isinstance(action.pipeline.children[action.pipeline][0], RetryAction))
                # checksum downloaded file
                # assert d contains a checksum action
                # mount with offset
                # assert d contains a mount action
                # check for customisation (TBD later)
                # FIXME: ensure next step happens without needing to umount & remount!
                # ensure the test definition action is inside the mount pipeline
                # load test definitions into the image
                # umount
            elif isinstance(action, Action):
                pass
            else:
                print action
                self.fail("No deploy action found")
        download.parse()
        self.assertEqual(download.reader, download._http_stream)
        self.assertIsInstance(download, DownloaderAction)
        self.assertIsInstance(download.log_handler, logging.FileHandler)
        self.assertIsInstance(checksum.log_handler, logging.FileHandler)
        self.assertIsInstance(mount.log_handler, logging.FileHandler)
        self.assertIsInstance(customise.log_handler, logging.FileHandler)
        self.assertIsInstance(testdef.log_handler, logging.FileHandler)
        self.assertIsInstance(overlay.log_handler, logging.FileHandler)
        self.assertIsInstance(unmount.log_handler, logging.FileHandler)
        self.assertIsInstance(unmount, RetryAction)

    def test_kvm_validate(self):
        try:
            self.job.pipeline.validate_actions()
        except JobError as exc:
            self.fail(exc)
        for action in self.job.pipeline.actions:
            self.assertTrue(action.valid)

    def test_download_actions(self):
        """
        Once the download module is converted to requests and
        individual actions, complete this placeholder
        """
        pass

    def test_kvm_basic_mount(self):
        mount = None
        for action in self.job.pipeline.actions:
            if isinstance(action, DeployAction):
                # check parser has created a suitable deployment
                mount = action.pipeline.children[action.pipeline][2]
                self.assertIsInstance(mount.internal_pipeline, Pipeline)
                self.assertIsInstance(mount, MountAction)
                customise = action.pipeline.children[action.pipeline][3]
                self.assertIsInstance(customise, CustomisationAction)
                testdef = action.pipeline.children[action.pipeline][4]
                self.assertIsInstance(testdef, TestDefinitionAction)
                overlay = action.pipeline.children[action.pipeline][5]
                self.assertIsInstance(overlay, OverlayAction)
                unmount = action.pipeline.children[action.pipeline][6]
                self.assertIsInstance(unmount, UnmountAction)
        self.assertTrue(mount.valid)
        self.assertEqual(len(mount.internal_pipeline.actions), 3)
        self.assertIsInstance(mount.internal_pipeline.actions[0], OffsetAction)
        self.assertIsInstance(mount.internal_pipeline.actions[1], LoopCheckAction)
        self.assertIsInstance(mount.internal_pipeline.actions[2], LoopMountAction)

    def test_kvm_basic_overlay(self):
        overlay = None
        for action in self.job.pipeline.actions:
            self.assertIsNotNone(action.name)
            if isinstance(action, DeployAction):
                overlay = action.pipeline.children[action.pipeline][5]
        self.assertIsNotNone(overlay)
        # these tests require that lava-dispatcher itself is installed, not just running tests from a git clone
        self.assertTrue(os.path.exists(overlay.lava_test_dir))
        self.assertIsNot(overlay.lava_test_dir, '/')
        self.assertNotIn('lava_multi_node_test_dir', dir(overlay))
        self.assertNotIn('lava_multi_node_cache_file', dir(overlay))
        self.assertNotIn('lava_lmp_test_dir', dir(overlay))
        self.assertNotIn('lava_lmp_cache_file', dir(overlay))
        self.assertEqual(overlay.default_pattern,
                         "(?P<test_case_id>.*-*)\\s+:\\s+(?P<result>(PASS|pass|FAIL|fail|SKIP|skip|UNKNOWN|unknown))")
        self.assertEqual(overlay.default_fixupdict,
                         {'PASS': 'pass', 'FAIL': 'fail', 'SKIP': 'skip',
                          'UNKNOWN': 'unknown'})
        self.assertIsNotNone(overlay.parameters['deployment_data']['lava_test_results_dir'])
        self.assertIsNotNone(overlay.parameters['deployment_data']['lava_test_sh_cmd'])
        self.assertEqual(overlay.parameters['deployment_data']['distro'], 'debian')
        self.assertIsNotNone(overlay.parameters['deployment_data']['lava_test_results_part_attr'])
        # look up the root_part element of the device config and ensure it is not None
        self.assertIsNotNone(getattr(overlay.job.device.config,
                                     overlay.parameters['deployment_data']['lava_test_results_part_attr']))
        self.assertIsNotNone(getattr(overlay.job.device.config,
                                     overlay.parameters['deployment_data']['lava_test_results_part_attr']))
        self.assertIsNotNone(glob.glob(os.path.join(overlay.lava_test_dir, 'lava-*')))

    def test_kvm_basic_boot(self):
        for action in self.job.pipeline.actions:
            if isinstance(action, BootAction):
                # get the action & populate it
                self.assertEqual(action.parameters['method'], 'kvm')

    def test_kvm_basic_test(self):
        for action in self.job.pipeline.actions:
            if action.name == 'test':
                # get the action & populate it
                self.assertEqual(len(action.parameters['definitions']), 2)

    def test_kvm_basic_submit(self):
        for action in self.job.pipeline.actions:
            if action.name == "submit_results":
                # get the action & populate it
                self.assertEqual(action.parameters['stream'], "/anonymous/codehelp/")
