# -*- coding: utf-8 -*-
#
#    This file belongs to the ICTV project, written by Nicolas Detienne,
#    Francois Michel, Maxime Piraux, Pierre Reinbold and Ludovic Taffin
#    at Université catholique de Louvain.
#
#    Copyright (C) 2016-2018  Université catholique de Louvain (UCL, Belgium)
#
#    ICTV is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    ICTV is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with ICTV.  If not, see <http://www.gnu.org/licenses/>.

import json
import sched
import smtplib
from datetime import datetime, timedelta

from sqlobject import sqlhub

from ictv.database import SQLObjectThreadConnection
from logging import getLogger
from threading import Thread, Lock

import time

import zlib

import web

from ictv.models.user import User
from ictv.common.json_datetime import DateTimeEncoder
from ictv.common.logging import init_logger


class EmailDigester(object):  # TODO: Move pending emails storage to the database
    """
        An utility class that permits to send email to users while avoiding spams and generating automatically digests.
        Mails are sent using web.py sendmail function and thus SMTP configuration has to be set up in web.py.

        The details of its behavior is as follows: after created, all users are considered ready to receive email.
        When an email is added to be sent, the EmailDigester will schedule its sending with a slight delay.
        This will allow other emails that could quickly follow this one to be included and digested into a single email
        to the user.
        When an email is effectively sent to an user, this user will be marked as not ready to receive any emails before
        a certain time period. During that period, all emails added to be sent for this user will be digested. And after
        that period, they will be all sent in a single digested email.

        When adding an email, you have to provide an unique hash that represents this email. This prevents duplicated
        messages to be sent to the user.
    """
    def __init__(self, timedelta, subject, wait_delay=30):
        """
            :param timedelta: The minimum interval between two mails received by an user
            :param subject: The subject of the mail to be send.
            :param wait_delay: The additional delay in seconds before sending an email when the user is free to receive emails
        """
        self._s = sched.scheduler(timefunc=time.time)
        self._running = True
        self._t = Thread(target=self._run_sched)
        self._t.start()
        self._digest = {}  # An user id to string mapping storing the state of the message to be sent to the user once the digest process finished.
        self._digest_hashes = {}  # An user id to set mapping storing all the hashes of the messages to be sent to the user
        self._last_email = {}  # An user id to datetime storing the last time an email was sent to the user
        self._interval = timedelta
        self._subject = subject
        self._wait_delay = wait_delay
        self._logger = getLogger('email_digester_'+hex(zlib.adler32(subject.encode())))
        init_logger(self._logger.name)
        self._lock = Lock()  # Prevents race condition when adding and sending emails
        self._logger.info('EmailDigester initialized with parameters:\n%s' % json.dumps(
            {'timedelta': timedelta, 'subject': subject}, cls=DateTimeEncoder))

    def __del__(self):
        self.stop()

    def add_email(self, user, msg, msg_hash):
        """
            Add this message to the list of messages to be sent to the user once the digest process finishes.
            The message should end with a new line.
            If the given message is already present in the digest of this user, it will not be added. This test is based
            on the given hash.
        """
        self._lock.acquire()
        if msg_hash not in self._digest_hashes.get(user.id, set()):
            self._digest[user.id] = self._digest.get(user.id, '') + msg
            hash_set = self._digest_hashes.get(user.id, set())
            hash_set.add(msg_hash)
            self._digest_hashes[user.id] = hash_set
            if user.id not in self._last_email:
                # The user has not received any emails recently, we can send this one directly.
                # But because this email may be the first one of a short series, we will wait a bit before doing so.
                self._s.enter(self._wait_delay, 1, self._send_email, kwargs={'user_id': user.id})
                # Prevent further scheduling for this user
                self._last_email[user.id] = datetime.now() + timedelta(seconds=self._wait_delay)
            self._logger.info('An email was scheduled to be sent to %s with content:\n%s' % (user.email, msg))
        self._lock.release()

    def _send_email(self, user_id):
        self._lock.acquire()
        if user_id in self._digest:
            user_email = User.get(user_id).email
            try:
                web.sendmail(web.config.smtp_sendername, user_email, self._subject, self._digest[user_id])
                del self._digest[user_id]
                del self._digest_hashes[user_id]
                self._last_email[user_id] = datetime.now()
                self._s.enter(self._interval.total_seconds(), 1, self._send_email, kwargs={'user_id': user_id})
                self._logger.debug('Next email batch will be in %d seconds for user %s' % (self._interval.total_seconds(), user_email))
            except smtplib.SMTPException:
                self._logger.error('An error occured when sending email to %s' % user_email, exc_info=True)
        else:
            del self._last_email[user_id]  # An email can be sent at any moment in the future
        self._lock.release()

    def _run_sched(self):
        sqlhub.threadConnection = SQLObjectThreadConnection.get_conn()
        while self._running:
            self._s.run(blocking=False)  # TODO: Is there a better way to run this ?
            time.sleep(0.5)

    def stop(self):
        if self._running:
            self._running = False
            self._t.join()
            self._logger.info('EmailDigester was terminated')
