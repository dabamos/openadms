#!/usr/bin/env python3
"""
Copyright (c) 2017 Hochschule Neubrandenburg.

Licenced under the EUPL, Version 1.1 or - as soon they will be approved
by the European Commission - subsequent versions of the EUPL (the
"Licence");

You may not use this work except in compliance with the Licence.

You may obtain a copy of the Licence at:

    https://joinup.ec.europa.eu/community/eupl/og_page/eupl

Unless required by applicable law or agreed to in writing, software
distributed under the Licence is distributed on an "AS IS" basis,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the Licence for the specific language governing permissions and
limitations under the Licence.
"""

"""Module for data processing (pre-processing, atmospheric corrections,
transformations, and so on)."""

__author__ = 'Philipp Engel'
__copyright__ = 'Copyright (c) 2017 Hochschule Neubrandenburg'
__license__ = 'EUPL'

import re

from core.observation import Observation
from module.prototype import Prototype


class PreProcessor(Prototype):
    """
    Extracts values from the raw response of a given observation set and
    converts them to the defined types.
    """

    def __init__(self, name, type, manager):
        Prototype.__init__(self, name, type, manager)

    def process_observation(self, obs):
        """Extracts the values from the raw responses of the observation
        using regular expressions."""
        for set_name, request_set in obs.get('requestSets').items():
            response = request_set.get('response')
            response_pattern = request_set.get('responsePattern')

            if response is None or response == '':
                self.logger.error('No response in observation "{}" with ID "{}"'
                                  .format(obs.get('name'), obs.get('id')))
                continue

            pattern = re.compile(response_pattern)
            match = pattern.search(response)

            if not match:
                self.logger.error('Response "{}" of request "{}" of '
                                  'observation "{}" with ID "{}" from sensor '
                                  '"{}" on port "{}" does not match extraction '
                                  'pattern'.format(self.sanitize(response),
                                                   set_name,
                                                   obs.get('name'),
                                                   obs.get('id'),
                                                   obs.get('sensorName'),
                                                   obs.get('portName')))
                return obs

            # The regular expression pattern needs a least one defined group
            # by using the braces "(" and ")". Otherwise, the extraction of the
            # values fails.
            #
            # Right: "(.*)"
            # Wrong: ".*"
            if pattern.groups == 0:
                self.logger.error('No group(s) defined in regular expression '
                                  'pattern of observation "{}" with ID "{}"'
                                  .format(obs.get('name'), obs.get('id')))
                return obs

            # Convert the type of the parsed raw values from string to the
            # actual data type (float, int).
            response_sets = obs.get('responseSets')

            for group_name, raw_value in match.groupdict().items():
                if not raw_value:
                    self.logger.error('No raw value found for response set '
                                      '"{}" of observation "{}" with ID "{}"'
                                      .format(group_name,
                                              obs.get('name'),
                                              obs.get('id')))
                    continue

                response_set = response_sets.get(group_name)

                if not response_set:
                    self.logger.error('Response set "{}" of observation "{}" '
                                      'with ID "{}" not defined'
                                      .format(group_name,
                                              obs.get('name'),
                                              obs.get('id')))
                    continue

                response_type = response_set.get('type').lower()

                if response_type == 'float':
                    # Convert raw value to float.
                    # Replace comma by dot.
                    response_value = self.to_float(raw_value)
                elif response_type == 'integer':
                    # Convert raw value to int.
                    response_value = self.to_int(raw_value)
                else:
                    # "Convert" raw value to string.
                    response_value = raw_value

                if response_value is not None:
                    self.logger.debug('Extracted "{}" from raw response "{}" '
                                      'of observation "{}" with ID "{}"'
                                      .format(response_value,
                                              group_name,
                                              obs.get('name'),
                                              obs.get('id')))
                    response_set['value'] = response_value

        return obs

    def to_float(self, raw_value):
        dot_value = raw_value.replace(',', '.')

        if self.is_float(dot_value):
            response_value = float(dot_value)
            return response_value
        else:
            self.logger.warning('Value "{}" could not be converted '
                                '(not float)'.format(raw_value))
            return None

    def to_int(self, raw_value):
        if self.is_int(raw_value):
            response_value = int(raw_value)
            return response_value
        else:
            self.logger.warning('Value "{}" could not be converted '
                                '(not integer)'.format(raw_value))
            return None

    def is_int(self, value):
        """Returns whether a value is int or not."""
        try:
            int(value)
            return True
        except ValueError:
            return False

    def is_float(self, value):
        """Returns whether a value is float or not."""
        try:
            float(value)
            return True
        except ValueError:
            return False

    def sanitize(self, s):
        """Removes some non-printable characters from a string."""
        return s.replace('\n', '\\n')\
                .replace('\r', '\\r')\
                .replace('\t', '\\t')


class ReturnCodes(object):
    """
    ReturnCodes stores a dictionary of return codes of sensors of Leica
    Geosystems. The dictionary is server and has the following structure:

        {
            return code: [ log level, retry measurement, log message ]
        }

    The return code numbers and messages are take from the GeoCOM reference
    manual of the Leica TPS 1200, TS 30, and TM 30 total stations. The log
    level can be set to these values:

        5: CRITICAL,
        4: ERROR,
        3: WARNING,
        2: INFO,
        1: DEBUG,
        0: NONE.

    Please choose a proper value for each return code.
    """
    codes = {
        2:    [4, False, 'Unknown error, result unspecified'],
        3:    [3, False, 'Invalid result'],
        4:    [4, False, 'Fatal error'],
        5:    [4, False, 'GeoCOM command unknown (not implemented yet)'],
        6:    [4, False, 'Function execution timed out (result unspecified)'],
        13:   [4, True,  'System busy'],
        514:  [4, False, 'Several targets detected'],
        1283: [3, False, 'Measurement without full correction'],
        1284: [3, False, 'Accuracy can not be guaranteed'],
        1285: [4, True,  'Only angle measurement valid'],
        1288: [3, False, 'Only angle measurement valid, but without full '\
                         'correction'],
        1292: [4, True,  'Distance measurement not done (no aim, etc.)'],
        8704: [4, True,  'Position not reached'],
        8708: [4, True,  'Position not exactly reached'],
        8710: [4, True,  'No target detected'],
        8711: [4, False, 'Multiple targets detected'],
        8716: [4, True,  'Target position not exactly reached'],
    }


class ReturnCodeInspector(Prototype):
    """
    ReturnCodeInspector inspects the return code in an observation sent by
    sensors of Leica Geosystems and creates an appropriate log message.
    """

    def __init__(self, name, type, manager):
        Prototype.__init__(self, name, type, manager)
        config = self._config_manager.get(self._name)

        self._response_sets = config.get('responseSets')
        self._retries = config.get('retries')

    def process_observation(self, obs):
        for response_set in self._response_sets:
            return_code = obs.get_value('responseSets', response_set, 'value')

            # Key is zero or not in response set.
            if return_code is None or return_code == 0:
                continue

            # Get level and error message of the return code.
            error_values = ReturnCodes.codes.get(return_code)
            lvl, retry, msg = error_values

            attempts = obs.get('attempts', 0)

            # Retry measurement.
            if retry and attempts < self._retries:
                obs.set('attempts', attempts + 1)
                obs.set('nextReceiver', 0)
                obs.set('corrupted', False)

                self.logger.info('Retrying observation "{}" with ID "{}" due '
                                 'to return code {} of response "{}" '
                                 '(attempt {} of {})'.format(obs.get('name'),
                                                             obs.get('id'),
                                                             return_code,
                                                             response_set,
                                                             attempts + 1,
                                                             self._retries))
            else:
                obs.set('corrupted', True)

                if error_values:
                    # Return code related log message.
                    self.logger.log(lvl * 10, 'Observation "{}" with ID "{}": '
                                              '{} (code {} in response "{}")'
                                              .format(obs.get('name'),
                                                      obs.get('id'),
                                                      msg,
                                                      return_code,
                                                      response_set))

                else:
                    # Generic log message.
                    self.logger.error('Error occurred on observation "{}" '
                                      '(code {} in response "{}")'
                                      .format(obs.get('name'),
                                              return_code,
                                              response_set))
            return obs

        return obs


class UnitConverter(Prototype):
    """
    UnitConverter can be used to convert response values of arbitrary
    observations. For instance, a response in centimeters can be converted to
    meters by setting a scale factor.
    """

    def __init__(self, name, type, manager):
        Prototype.__init__(self, name, type, manager)
        config = self._config_manager.get(self._name)
        self._conversion_table = config.get('conversionTable')

    def process_observation(self, obs):
        for name, entry in self._conversion_table.items():
            response_set = obs.get('responseSets').get(name)

            if not response_set:
                continue

            src_value = response_set.get('value')
            src_unit = response_set.get('unit')

            if not src_value or not src_unit:
                continue

            if src_unit != entry.get('sourceUnit'):
                self.logger.warning('Unit "{}" of response "{}" of observation '
                                    '"{}" with ID "{}" does not match "{}"'
                                    .format(src_unit,
                                            name,
                                            obs.get('name'),
                                            obs.get('id'),
                                            entry.get('sourceUnit')))
                continue

            if entry.get('conversionType') == 'scale':
                dgn_value = self._scale(float(src_value),
                                        entry.get('scalingValue'))
                dgn_unit = entry.get('designatedUnit')

                self.logger.info('Converted response "{}" of observation "{}" '
                                 'with ID "{}" from {:.4f} {} to {:.4f} {}'
                                 .format(name,
                                         obs.get('name'),
                                         obs.get('id'),
                                         src_value,
                                         src_unit,
                                         dgn_value,
                                         dgn_unit))

                response_set = Observation.create_response_set(
                    'float',
                    dgn_unit,
                    round(dgn_value, 5)
                )

                obs.data['responseSets'][name] = response_set

        return obs

    def _scale(self, value: float, factor: float) -> float:
        """Scales value by factor.

        Args:
            value (float): Value to scale.
            factor (float): Scaling factor.

        Returns:
            Scaled value.
        """
        return value * factor
