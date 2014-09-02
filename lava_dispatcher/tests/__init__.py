import unittest


def test_suite():
    module_names = [
        'lava_dispatcher.tests.test_config',
        'lava_dispatcher.tests.test_device_version',
        'linaro_dashboard_bundle.tests',
        'lava_dispatcher.tests.test_job',
        'lava_dispatcher.pipeline.test.test_basic',
        'lava_dispatcher.pipeline.test.test_job',
        'lava_dispatcher.pipeline.test.test_defs',
        'lava_dispatcher.pipeline.test.test_devices',
    ]
    loader = unittest.TestLoader()
    return loader.loadTestsFromNames(module_names)
