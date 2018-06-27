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

import os
import re
import shlex
import threading
from queue import Queue, Empty
from subprocess import Popen, PIPE

import logging
from pymediainfo import MediaInfo
from sqlobject import sqlhub

from ictv.database import SQLObjectThreadConnection

logger = logging.getLogger('transcoding_queue')


class TranscodingQueue:
    def __init__(self):
        self._running = True
        self._thread = threading.Thread(target=self._run_loop)
        self._task_queue = Queue()
        self._pending_tasks = {}  # A map of path to progress in pc
        self._thread.start()

    def __del__(self):
        self.stop()

    def stop(self):
        self._running = False
        self._thread.join()

    def enqueue_task(self, input_file, output_file, callback):
        logger.info('[Job %s -> %s] Added to queue', input_file, output_file)
        self._task_queue.put((input_file, output_file, callback))
        self._pending_tasks[output_file] = 0

    def get_progress(self, path):
        return self._pending_tasks.get(path)

    def _run_loop(self):
        sqlhub.threadConnection = SQLObjectThreadConnection.get_conn()
        while self._running:
            try:
                input_file, output_file, callback = self._task_queue.get(timeout=0.5)

                def update_progress(progress):
                    self._pending_tasks[output_file] = progress

                try:
                    logger.info('[Job %s -> %s] Started transcoding', input_file, output_file)
                    transcode_to_webm(input_file, output_file, update_progress)
                    callback(True)
                except:
                    logger.warning('[Job %s -> %s] Exception occured', input_file, output_file, exc_info=True)
                    callback(False)
            except Empty:
                continue


def transcode_to_webm(input_file, output_file, progress_callback):
    video_info = MediaInfo.parse(input_file)
    frame_count = int(video_info.tracks[0].frame_count)

    threads = (os.cpu_count() or 2) - 1
    video_crf = 31
    audio_rate = '192k'
    ffmpeg_args = ['ffmpeg', '-hide_banner', '-loglevel', 'warning', '-stats',
                   '-i', shlex.quote(input_file), '-c:v', 'libvpx-vp9', '-crf', str(video_crf), '-b:v', '0', '-b:a',
                   audio_rate, '-threads', str(threads), shlex.quote(output_file)]
    ffmpeg_job = Popen(' '.join(ffmpeg_args), shell=True, stdout=PIPE, stderr=PIPE, bufsize=0, universal_newlines=False)

    line = []
    frame_regex = re.compile(r'frame=\s*(\d+)\s*fps')
    while ffmpeg_job.poll() is None:
        c = ffmpeg_job.stderr.read(1)
        if c == b'\r' or c == b'\n':
            line = ''.join(line)
            try:
                current_frame = int(frame_regex.match(line).group(1))
                progress_callback(current_frame / frame_count)
            except:
                logger.warning('[Job %s -> %s] stderr: %s', input_file, output_file, line)
            line = []
        else:
            line.append(c.decode())

    if ffmpeg_job.returncode is not 0:
        logger.warning('[Job %s -> %s] stdout: %s', input_file, output_file,''.join(c.decode() for c in ffmpeg_job.stdout.readlines()))
        logger.warning('[Job %s -> %s] stderr: %s', input_file, output_file, ''.join(c.decode() for c in ffmpeg_job.stderr.readlines()))
        raise IOError('Transcoding failed with return code %d' % ffmpeg_job.returncode)

    logger.info('[Job %s -> %s] Transcoding completed', input_file, output_file)
