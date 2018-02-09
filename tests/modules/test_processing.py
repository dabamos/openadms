#!/usr/bin/env python3.6

"""Tests the classes of the processing modules."""

__author__ = 'Philipp Engel'
__copyright__ = 'Copyright (c) 2017 Hochschule Neubrandenburg'
__license__ = 'BSD-2-Clause'

import pytest

from testfixtures import LogCapture

from modules.processing import *


@pytest.fixture(scope='module')
def pre_processor(manager) -> PreProcessor:
    """Returns a PreProcessor object.

    Args:
        manager (Manager): Instance of ``core.Manager``.

    Returns:
        An instance of class ``module.processing.PreProcessor``.
    """
    return PreProcessor('preProcessor',
                        'modules.processing.PreProcessor',
                        manager)


@pytest.fixture(scope='module')
def rv_inspector(manager) -> ResponseValueInspector:
    """Returns a ResponseValueInspector object.

    Args:
        manager (Manager): Instance of ``core.Manager``.

    Returns:
        An instance of class ``module.processing.ResponseValueInspector``.
    """
    return ResponseValueInspector('responseValueInspector',
                                  'modules.processing.ResponseValueInspector',
                                  manager)


@pytest.fixture(scope='module')
def rc_inspector(manager) -> ReturnCodeInspector:
    """Returns a ReturnCodeInspector object.

    Args:
        manager (Manager): Instance of ``core.Manager``.

    Returns:
        An instance of class ``module.processing.ReturnCodeInspector``.
    """
    return ReturnCodeInspector('returnCodeInspector',
                               'modules.processing.ReturnCodeInspector',
                               manager)


@pytest.fixture(scope='module')
def unit_converter(manager) -> UnitConverter:
    """Returns a UnitConverter object.

    Args:
        manager (Manager): Instance of ``core.Manager``.

    Returns:
        An instance of class ``module.processing.UnitConverter``.
    """
    return UnitConverter('unitConverter',
                         'modules.processing.UnitConverter',
                         manager)


class TestPreProcessor(object):
    """
    Test for the ``module.processing.PreProcessor`` class.
    """

    def test_process_observation(self,
                                 pre_processor: PreProcessor,
                                 observations: List[Observation]) -> None:
        """Tests the processing of observations."""
        obs_in = observations[0]
        obs_out = pre_processor.process_observation(obs_in)

        assert obs_out.get_response_value('temperature') == 23.1
        assert obs_out.get_response_value('pressure') == 1011.3

    def test_is_float(self, pre_processor: PreProcessor) -> None:
        assert pre_processor.is_float('10.5') is True
        assert pre_processor.is_float('foo') is False

    def test_is_int(self, pre_processor: PreProcessor) -> None:
        assert pre_processor.is_float('10') is True
        assert pre_processor.is_float('10.5') is True
        assert pre_processor.is_float('foo') is False

    def test_sanitize(self, pre_processor: PreProcessor) -> None:
        assert pre_processor.sanitize('\n\r\t') == '\\n\\r\\t'

    def test_to_float(self, pre_processor: PreProcessor) -> None:
        assert pre_processor.to_float('10,5') == 10.5
        assert pre_processor.to_float('0.9995') == 0.9995
        assert pre_processor.to_float('foo') is None

    def test_to_int(self, pre_processor: PreProcessor) -> None:
        assert pre_processor.to_int('10') == 10
        assert pre_processor.to_int('10.5') is None
        assert pre_processor.to_int('foo') is None


class TestResponseValueInspector(object):
    """
    Test for the ``module.processing.ResponseValueInspector`` class.
    """

    def test_process_observation(self,
                                 rv_inspector: ResponseValueInspector,
                                 observations: List[Observation]) -> None:
        """Check whether valid log messages are created."""
        obs = observations[1]

        obs_name = obs.get('name')
        obs_target = obs.get('target')
        response_name = 'slopeDist'

        min_val = 10.0
        max_val = 100.0

        valid_val = 25.0
        lt_min_val = 0.0
        gt_max_val = 200.0

        with LogCapture() as log_capture:
            # Test 1 (observation not defined).
            obs.data['name'] = 'test'
            rv_inspector.process_observation(obs)

            # Test 2 (invalid response type).
            obs.data['name'] = obs_name
            obs.data['responseSets']['slopeDist']['value'] = 'test'
            rv_inspector.process_observation(obs)

            # Test 3 (success).
            obs.data['responseSets']['slopeDist']['value'] = valid_val
            rv_inspector.process_observation(obs)

            # Test 4 (response value less than minimum).
            obs.data['responseSets']['slopeDist']['value'] = lt_min_val
            rv_inspector.process_observation(obs)

            # Test 5 (response value greater than maximum).
            obs.data['responseSets']['slopeDist']['value'] = gt_max_val
            rv_inspector.process_observation(obs)

            # Capture log messages.
            log_capture.check(
                (rv_inspector.name,
                 'WARNING',
                 'Observation "{}" with target "{}" is '
                 'not defined'.format('test',
                                      obs_target)),
                (rv_inspector.name,
                 'WARNING',
                 'Response value "{}" of observation "{}" with target "{}" is '
                 'not a number'.format(response_name,
                                       obs_name,
                                       obs_target)),
                (rv_inspector.name,
                 'DEBUG',
                 'Response value "{}" of observation "{}" with target "{}" is '
                 'within the limits'.format(response_name,
                                            obs_name,
                                            obs_target)),
                (rv_inspector.name,
                 'CRITICAL',
                 'Response value "{}" of observation "{}" with target "{}" is '
                 'less than minimum ({} < {})'.format(response_name,
                                                      obs_name,
                                                      obs_target,
                                                      lt_min_val,
                                                      min_val)),
                (rv_inspector.name,
                 'CRITICAL',
                 'Response value "{}" of observation "{}" with target "{}" is '
                 'greater than maximum ({} > {})'.format(response_name,
                                                         obs_name,
                                                         obs_target,
                                                         gt_max_val,
                                                         max_val))
            )

    def test_is_number(self,
                       rv_inspector: ResponseValueInspector) -> None:
        assert rv_inspector.is_number('10') is True
        assert rv_inspector.is_number('10.5') is True
        assert rv_inspector.is_number('foo') is False


class TestReturnCodeInspector(object):
    """
    Test for the ``module.processing.ReturnCodeInspector`` class.
    """

    def test_process_observation(self,
                                 rc_inspector: ReturnCodeInspector,
                                 observations: List[Observation]) -> None:
        obs = rc_inspector.process_observation(observations[1])
        assert obs.data['corrupted'] is True

        obs.data['responseSets']['returnCode']['value'] = 13
        obs = rc_inspector.process_observation(obs)
        assert obs.data['attempts'] == 1
        assert obs.data['corrupted'] is False
        assert obs.data['nextReceiver'] == 0


class TestReturnCodeInspector(object):

    def test_process_observation(self,
                                 unit_converter: UnitConverter,
                                 observations: List[Observation]) -> None:
        pass

    def test_scale(self, unit_converter: UnitConverter) -> None:
        assert unit_converter.scale(10, 10) == 100