#!/usr/bin/env python3
"""
Copyright (c) 2016 Hochschule Neubrandenburg.

Licensed under the EUPL, Version 1.1 or - as soon they will be approved
by the European Commission - subsequent versions of the EUPL (the
"Licence");

You may not use this work except in compliance with the Licence.

You may obtain a copy of the Licence at:

    http://ec.europa.eu/idabc/eupl

Unless required by applicable law or agreed to in writing, software
distributed under the Licence is distributed on an "AS IS" basis,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the Licence for the specific language governing permissions and
limitations under the Licence.
"""

import copy
import datetime as dt
import json
import logging
import threading
import time

from modules.prototype import Prototype

logger = logging.getLogger('openadms')


class Scheduler(Prototype):

    """
    Scheduler is used to manage the monitoring process by sending observations
    to a sensor. Each observation set is represented by a single job. Jobs are
    stored in a jobs list and will be executed at the given date/time. For each
    sensor a separate scheduler is needed.
    """

    def __init__(self, name, config_manager, sensor_manager):
        Prototype.__init__(self, name, config_manager, sensor_manager)
        self._jobs = []
        self.load_jobs()

        # Run the method self.run_jobs() within a thread.
        self._thread = threading.Thread(target=self.run_jobs)
        self._thread.daemon = True
        self._thread.start()

    def load_jobs(self):
        """Loads all observation sets from the configurations and creates jobs
        to put into the jobs list."""
        config = self._config_manager.config.get('Schedulers').get(self._name)
        port_name = config.get('Port')
        sensor_name = config.get('Sensor')
        schedules = config.get('Schedules')

        # Run through the schedules and create jobs.
        for schedule in schedules:
            observations = schedule.get('ObservationSets')

            for obs_name in observations:
                # Get all observations of the current observation set.
                obs = self._sensor_manager.get(sensor_name)\
                                          .get_observation(obs_name)

                if not obs:
                    logger.error('Observation "{}" not found'.format(obs_name))
                    continue

                # Create a new job.
                job = Job(obs_name,
                          port_name,
                          obs,
                          schedule['Enabled'],
                          schedule['StartDate'],
                          schedule['EndDate'],
                          schedule['Weekdays'],
                          self.publish)
                # Add the job to the jobs list.
                self.add(job)

    def add(self, job):
        """Appends a job to the jobs list."""
        self._jobs.append(job)
        logger.debug('Added job "{}" to scheduler "{}"'.format(job.name,
                                                               self._name))

    def run_jobs(self):
        """Threaded method to process the jobs queue."""
        while True:
            if self._is_paused:
                time.sleep(0.1)
                continue

            for job in self._jobs:
                if not job.enabled:
                    continue

                if job.has_expired():
                    continue

                if job.is_pending():
                    job.run()


class Job(object):

    """
    Job stores a observation set and sends single observations to callback
    function if they are within a given time frame.
    """

    def __init__(self, name, port_name, obs, enabled, start_date, end_date,
                 time_sheet, uplink):
        self._name = name               # Name of the job.
        self._port_name = port_name     # Name of the port.
        self._obs = obs                 # Observation object.
        self._enabled = enabled         # Is enabled or not.
        self._time_sheet = time_sheet   # The time sheet.
        self._uplink = uplink           # Callback function.

        # Used date and time formats.
        self._date_fmt = '%Y-%m-%d'
        self._time_fmt = '%H:%M:%S'

        # Convert date to date and time (00:00:00).
        self._start_date = self.get_datetime(start_date, self._date_fmt)
        self._end_date = self.get_datetime(end_date, self._date_fmt)

    def get_datetime(self, dt_str, dt_fmt):
        """Converts a date string to a time stamp."""
        return dt.datetime.strptime(dt_str, dt_fmt)

    def has_expired(self):
        """Checks if the job has expired."""
        now = dt.datetime.now()

        if now > self._end_date:
            logger.debug('Job has expired')
            return True

        return False

    def is_pending(self):
        """Checks whether or not the job is within the current time frame and
        ready for processing."""
        if not self._enabled:
            return False

        now = dt.datetime.now()

        # Are we within the date range of the job?
        if self._start_date <= now < self._end_date:
            # No days defined, go on.
            if len(self._time_sheet) == 0:
                return True

            # Name of the current day (e.g., "Monday").
            current_day = now.strftime('%A')

            # Ignore current day if it is not listed in the schedule.
            if current_day in self._time_sheet:
                # Time ranges of the current day.
                periods = self._time_sheet[current_day]

                # No given time range means the job should be executed
                # all day long.
                if len(periods) == 0:
                    return True

                # Check all time ranges of the current day.
                if len(periods) > 0:
                    for period in periods:
                        # Start and end time of the current day.
                        start_time = self.get_datetime(period['StartTime'],
                                                       self._time_fmt).time()
                        end_time = self.get_datetime(period['EndTime'],
                                                     self._time_fmt).time()

                        # Are we within the time range of the current day?
                        if start_time <= now.time() < end_time:
                            return True

        return False

    def run(self):
        """Iterates trough the observation set and sends observations to an
        external callback function."""
        # Continue if observation is disabled.
        if not self._obs.get('Enabled'):
            return

        # Disable the observation if it should run one time only (for
        # instance, for initialization purposes).
        if self._obs.get('Onetime'):
            self._obs.set('Enabled', False)

        # Make a deep copy, since we don't want to do any changes to the
        # observation in our observation set.
        obs_copy = copy.deepcopy(self._obs)
        # Insert the name of the port module or the virtual sensor at the
        # beginning of the receivers list.
        obs_copy.data['Receivers'].insert(0, self._port_name)

        logger.debug('Starting job "{}" for port "{}" ...'
                     .format(self._obs.get('Name'),
                             self._port_name))

        sleep_time = obs_copy.get('SleepTime')

        # Send the observation to the sensor.
        target = self._port_name
        header = {'Type': 'Observation'}
        payload = obs_copy.data

        # Fire and forget.
        self._uplink(target, header, payload)

        # Sleep until the next observation.
        time.sleep(sleep_time)

    @property
    def enabled(self):
        return self._enabled

    @property
    def name(self):
        return self._name
