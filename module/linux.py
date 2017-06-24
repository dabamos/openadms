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

import time
import threading

import RPi.GPIO as GPIO

from core.observation import Observation
from module.prototype import Prototype


class InterruptCounter(Prototype):
    """
    Counts GPIO interrupts on a single pin of a Raspberry Pi single-board
    computer. Works on Linux only."""

    def __init__(self, name, type, manager):
        Prototype.__init__(self, name, type, manager)
        config = self._config_manager.get(self._name)

        self._gpio = config.get('gpio')
        self._bounce_time = config.get('bounceTime')
        self._count_time = config.get('countTime')
        self._receiver = config.get('receiver')
        self._sensor_name = config.get('sensorName')

        self._counter = 0
        self._thread = None
        self._lock = threading.Lock()

        self.init_gpio()

    def __del__(self):
        GPIO.cleanup()

    def init_gpio(self):
        # Set SoC as reference.
        GPIO.setmode(GPIO.BCM)
        # Set pin as input and activate pull-down resistor.
        GPIO.setup(self._gpio,
                   GPIO.IN,
                   pull_up_down=GPIO.PUD_DOWN)
        # Add interrupt event.
        GPIO.add_event_detect(self._gpio,
                              GPIO.RISING,
                              callback=self._interrupt,
                              bouncetime=self._bounce_time)

    def _interrupt(self, channel):
        self._lock.acquire()

        try:
            self._counter += 1
            self.logger.debug('Counted interrupt {} on GPIO pin {}'
                              .format(self._counter, self._gpio))
        finally:
            self._lock.release()

    def run(self):
        t1 = time.time()
        t2 = t1

        while self._is_running:
            dt = t2 - t1
            time.sleep(self._count_time - dt)
            t1 = time.time()
            counter = 0

            self._lock.acquire()

            try:
                counter = self._counter
                self._counter = 0
            finally:
                self._lock.release()

            self._fire(counter)
            t2 = time.time()

    def _fire(self, c: int) -> None:
        obs = Observation()

        response_sets = {
            'GPIO{}'.format(self._gpio):
                Observation.create_response_set('int', 'none', c)
        }

        obs.set('id', 'GPIO{}'.format(self._gpio))
        obs.set('name', 'interrupts')
        obs.set('nextReceiver', 0)
        obs.set('portName', 'GPIO{}'.format(self._gpio))
        obs.set('receivers', [self._receiver])
        obs.set('responseSets', response_sets)
        obs.set('sensorName', self._sensor_name) 
        obs.set('timeStamp', time.time())

        self.publish_observation(obs)

    def start(self):
        if self._is_running:
            return

        self.logger.debug('Starting worker "{}" ...'.format(self._name))
        self._is_running = True

        # Run the method self.run() within a thread.
        self._thread = threading.Thread(target=self.run)
        self._thread.daemon = True
        self._thread.start()

