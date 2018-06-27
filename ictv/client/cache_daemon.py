#!/usr/bin/env python3
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
import os
import re
import shutil
import socket
import urllib.parse
from datetime import timezone
from queue import Queue, Empty
from threading import Thread
from xmlrpc.server import SimpleXMLRPCServer, SimpleXMLRPCRequestHandler

import requests
import werkzeug.http
from bs4 import BeautifulSoup
from requests import HTTPError

import logging

# Avoid using glibc resolver and its unavoidable internal cache mechanism
from urllib3.util import connection as con_lib
from requests.packages.urllib3.util import connection as con_req
_orig_create_connection = con_lib.create_connection


def patched_create_connection(address, *args, **kwargs):
    host, port = address
    try:
        sock = _orig_create_connection((host, port), *args, **kwargs)
    except socket.gaierror as gaie:
        logging.warning('gaierror occured, trying to reset libc dns cache', exc_info=True)
        try:
            import ctypes
            libc = ctypes.cdll.LoadLibrary('libc.so.6')
            try:
                res_init = libc.__res_init
            except AttributeError:
                raise gaie
            res_init()  # Flush libc DNS resolver cache
        except OSError:
            raise gaie
        sock = _orig_create_connection((host, port), *args, **kwargs)
    return sock


con_lib.create_connection = patched_create_connection
con_req.create_connection = patched_create_connection
# End DNS resolver monkey patching

_parent_dir_path = os.path.abspath(os.path.dirname(__file__))


class CrossOriginRequestHandler(SimpleXMLRPCRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def end_headers(self):  # Enable CORS on all requests
        self.send_header("Access-Control-Allow-Headers",
                         "Origin, X-Requested-With, Content-Type, Accept")
        self.send_header("Access-Control-Allow-Origin", "*")
        SimpleXMLRPCRequestHandler.end_headers(self)


def prepare_cached_version():
    global next_req_id
    req_id = next_req_id
    queue_status[req_id] = 'notready'
    client_mac = determine_mac_address(ictv_root_url)
    if client_mac:
        request_queue.put((req_id, '%s/screens/redirect/%s' % (ictv_root_url, client_mac)))
    else:  # No MAC address could be determined
        queue_status[req_id] = None
    next_req_id += 1
    return req_id


def get_status(req_id):
    return queue_status.get(req_id)


def caching_thread():
    global delete_list
    while running:
        try:
            req_id, page_url = request_queue.get(timeout=5)
            try:
                with requests.Session() as session:
                    session.headers['User-Agent'] = 'cache_daemon.py'
                    delete_files(delete_list)
                    delete_list = []
                    local_page_path = cache_page(session, page_url, check_for_slides=True)
                    queue_status[req_id] = 'file://' + local_page_path
                    if os.path.exists(last_page_path):
                        os.unlink(last_page_path)
                    try:
                        os.symlink(local_page_path, last_page_path)
                    except PermissionError:  # FS may not support symlink
                        shutil.copyfile(local_page_path, last_page_path)
            except:
                queue_status[req_id] = None
                logging.error('Caught exception', exc_info=True)
        except Empty:
            pass


def cache_page(session, page_url, check_for_slides=False):
    logging.info('cache %s', page_url)
    page_path = make_dirs(page_url, assets_path)
    timestamp = get_timestamp_for(page_path)

    try:
        response = session.get(page_url, headers=get_headers_for(timestamp))
        if response.status_code == 304:
            return get_path_with_date(page_path, None, timestamp)
        elif response.status_code != 200:
            response.raise_for_status()

        soup = BeautifulSoup(response.content, 'lxml', from_encoding=response.encoding)
        soup.head.append(soup.new_tag('meta', charset=response.encoding))

        if check_for_slides and soup.select_one('.slides') is None:
            raise Exception('Page at url %s does not contain reveal.js slides, but slides were expected', page_url)

        for link in soup.select('link[rel="stylesheet"]'):  # Cache CSS stylesheets
            css_url = urllib.parse.urljoin(page_url, link.get('href'))
            update_url(soup, session, link, 'href', css_url, assets_path)

        for e in soup.select('script[src], img[src]'):  # Cache img & script source files
            if e.attrs:  # Otherwise bs4 can return a <None></None> that breaks the code
                url = urllib.parse.urljoin(page_url, e['src'])
                update_url(soup, session, e, 'src', url, assets_path)

        for slide in soup.select('section[data-background-image]'):  # Cache reveal.js background images
            img_url = urllib.parse.urljoin(page_url, slide['data-background-image'])
            update_url(soup, session, slide, 'data-background-image', img_url, assets_path)

        for slide in soup.select('section[data-background-video]'):  # Cache reveal.js background images
            video_url = urllib.parse.urljoin(page_url, slide['data-background-video'])
            update_url(soup, session, slide, 'data-background-video', video_url, assets_path)

        for slide in soup.select('section[data-background-iframe]'):  # Cache reveal.js background iframes
            iframe_url = urllib.parse.urljoin(page_url, slide['data-background-iframe'])
            cache_path = cache_page(session, iframe_url)
            if cache_path:
                slide['data-background-iframe'] = 'file://' + cache_path
            else:
                slide.parent.decompose()

        for iframe in soup.select('iframe[src]'):  # Cache iframes
            iframe_url = urllib.parse.urljoin(page_url, iframe['src'])
            cache_path = cache_page(session, iframe_url)
            if cache_path:
                iframe['src'] = 'file://' + cache_path
            else:
                if soup.select_one('.slides') is None:
                    return None  # Propagate the asset failure
                else:
                    pass  # Find the capsule parent in ancestors

        if timestamp and timestamp != get_timestamp_from(response.headers):  # Check if the timestamp has changed despite receiving status 200
            for entry, _ in yield_matching_files_for(page_path):
                delete_list.append(entry.path)

        if 'Last-Modified' in response.headers:
            page_path = get_path_with_date(page_path, response.headers)

        with open(page_path, 'wb') as f:
            f.write(soup.prettify(encoding=response.encoding))
            f.flush()

    except OSError as e:
        logging.error('An error occured', exc_info=True)
        return None

    return page_path


def update_url(soup, session, element, attr, url, path):
    if not url.startswith('data:') and not url.startswith('file://'):
        original_link = element[attr]
        try:
            new_link = 'file://' + save_at(session, url, path)
            for d in soup.find_all(element.name, attrs={attr: original_link}):  # Handle duplicates elements in one pass
                d[attr] = new_link
        except HTTPError:
            logging.warning('HTTP error occurred while updating url %s', url, exc_info=True)
            if element.find_parent('html').select_one('.slides') is not None:
                capsule = element.parent if element.name == 'section' else element.find_parent('section').parent
                logging.info('Removing capsule containing element %s, i.e. %s', element, capsule)
                capsule.decompose()  # Removes the capsule containing slide with this asset
            else:
                raise


def save_at(session, url, path):
    logging.info('save %s', url)
    final_path = make_dirs(url, path)
    timestamp = get_timestamp_for(final_path)

    response = session.get(url, headers=get_headers_for(timestamp))
    if response.status_code == 200:
        if timestamp and timestamp != get_timestamp_from(response.headers):  # Check if the timestamp has changed despite receiving status 200
            for entry, _ in yield_matching_files_for(final_path):
                delete_list.append(entry.path)

        if 'Last-Modified' in response.headers:
            final_path = get_path_with_date(final_path, response.headers)
        with open(final_path, 'wb') as f:
            f.write(response.content)
    elif response.status_code == 304:
        final_path = get_path_with_date(final_path, None, timestamp)
    else:
        response.raise_for_status()

    return final_path


def make_dirs(url, path):
    filename = url.split('/')[-1]
    intermediate_dirs = urllib.parse.urlparse(url).path[1:-(len(filename) + 1)]
    final_dir = os.path.join(path, intermediate_dirs)
    os.makedirs(final_dir, exist_ok=True)
    return os.path.join(final_dir, filename)


def get_path_with_date(path, headers, timestamp=None):
    if timestamp is None:
        timestamp = get_timestamp_from(headers)
    file_path, ext = os.path.splitext(path)
    file_path += '_%d' % timestamp
    return file_path + ext


def delete_files(filelist):
    for path in filelist:
        try:
            os.unlink(path)
        except OSError:
            pass


def get_timestamp_for(path):
    timestamps = [0]
    for _, timestamp in yield_matching_files_for(path):
            timestamps.append(timestamp)
    return max(timestamps)


def get_timestamp_from(headers):
    return int(werkzeug.http.parse_date(headers['Last-Modified']).replace(tzinfo=timezone.utc).timestamp())


def yield_matching_files_for(path):
    filename, ext = os.path.splitext(os.path.basename(path))
    pattern = '%s_([0-9]{10})%s' % (re.escape(os.path.join(os.path.dirname(path), filename)), re.escape(ext))
    for entry in os.scandir(os.path.dirname(path)):
        if entry.is_file():
            match = re.fullmatch(pattern, entry.path)
            if match:
                yield entry, int(match.group(1))


def get_headers_for(timestamp):
    headers = {}
    if timestamp is not None:
        headers['If-Modified-Since'] = werkzeug.http.http_date(timestamp)
    return headers


def determine_mac_address(url):
    """ Determines which MAC address will be used to reached the host at the given url. """
    import socket
    import struct
    import fcntl
    from urllib.parse import urlparse

    def get_mac(ifname):
        return fcntl.ioctl(s.fileno(), 0x8927, struct.pack('256s', ifname[:15].encode()))[16+2:].hex()[:12]  # 0x8927 is SIOCGIFHWADDR

    def get_ip(ifname):
        return socket.inet_ntoa(fcntl.ioctl(s.fileno(), 0x8915, struct.pack('256s', ifname[:15].encode()))[20:24])  # 0x8915 is SIOCGIFADDR

    try:
        parsed_url = urlparse(url)
        s = socket.create_connection((parsed_url.hostname, parsed_url.port or (443 if parsed_url.scheme == 'https' else 80)), 10)
        local_addr, _ = s.getsockname()
        for _, name in socket.if_nameindex():
            try:
                if get_ip(name) == local_addr:
                    return get_mac(name)
            except OSError:
                pass
    except (TypeError, ValueError, OSError):
        logging.warning('Could not find MAC address', exc_info=True)
    return None

if __name__ == "__main__":
    running = True
    logging.basicConfig(format='%(asctime)s - %(levelname)s:%(name)s - %(message)s', filename='cache_daemon.log', level=logging.INFO)
    with open(os.path.join(_parent_dir_path, 'static', 'config.json'), 'r') as f:
        config = json.load(f)
    assets_path = os.path.join(_parent_dir_path, config['cached_assets_path'])
    last_page_path = os.path.join(_parent_dir_path, 'static', 'last_cached_page')
    ictv_root_url = config['ictv_root_url']

    if '%s' in ictv_root_url:  # Debug switch
        ictv_root_url = 'http://0.0.0.0:8080'

    next_req_id = 0
    queue_status = {}
    request_queue = Queue()
    delete_list = []
    cache_thread = Thread(target=caching_thread)
    cache_thread.start()

    server = SimpleXMLRPCServer((config['cache_daemon_host'], config['cache_daemon_port']),
                                requestHandler=CrossOriginRequestHandler, allow_none=True)
    server.register_introspection_functions()
    server.register_function(prepare_cached_version)
    server.register_function(get_status)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        running = False
