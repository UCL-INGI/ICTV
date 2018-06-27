"""
People erroneously think that any function registered via atexit.register()
will be executed on interpreter exit.
This is not always true. For example, in case of SIGTERM:

    import atexit, os, signal

    @atexit.register
    def cleanup():
        print("on exit")  # XXX this never gets printed

    os.kill(os.getpid(), signal.SIGTERM)

The correct way to make sure the exit function is always executed is to
register it via signal.signal().
That has a drawback though: in case a third-party module has already
registered a function for SIGTERM, your new function will overwrite the
old one, which will never be executed:

    import os, signal

    def old(*args):
        print("old")  # this never gets printed

    def new(*args):
        print "new"

    signal.signal(signal.SIGTERM, old)
    signal.signal(signal.SIGTERM, new)
    os.kill(os.getpid(), signal.SIGTERM)

This recipe attempts to address both issues so that:

- the exit function is always executed for all exit signals (SIGTERM,
  SIGINT, SIGQUIT, SIGHUP).
- any exit function previously registered via atexit.register() or
  signal.signal() will be executed as well (after the new one).

Note: exit function will not be executed in case of SIGKILL, SIGSTOP or
os._exit().

Note about Windows: signals are not supported meaning exit function will
be executed only on interpreter exit but not on SIGINT, SIGTERM, etc.

Note about Windows: signals are only partially supported meaning a
function which was previously registered via signal.signal() will be
executed only on interpreter exit, but not if the process receives
a signal. Apparently this is a limitation either of Windows or the
signal module, see:
http://bugs.python.org/issue26350

Author: Giampaolo Rodola' <g.rodola [AT] gmail [DOT] com>
License: MIT
"""

import atexit
import os
import signal
import sys


_registered_exit_funs = set()
_executed_exit_funs = set()
if os.name == 'posix':
    # https://en.wikipedia.org/wiki/Unix_signal#POSIX_signals
    _exit_signals = frozenset([
        signal.SIGTERM,  # sent by kill cmd by default
        signal.SIGINT,  # CTRL ^ C, aka KeyboardInterrupt
        signal.SIGQUIT,  # CTRL ^ D
        # signal.SIGHUP,  # terminal closed or daemon rotating files
        signal.SIGABRT,  # os.abort()
    ])
else:
    _exit_signals = frozenset([
        signal.SIGTERM,
        signal.SIGINT,  # CTRL ^ C
        signal.SIGABRT,  # os.abort()
        signal.SIGBREAK,  # CTRL ^ break / signal.CTRL_BREAK_EVENT
    ])


def register_exit_fun(fun, signals=_exit_signals):
    """Register a function which will be executed on clean interpreter
    exit or in case one of the `signals` is received by this process
    (differently from atexit.register()).

    Also, it makes sure to execute any previously registered signal
    handler as well. If any, it will be executed after `fun`.

    Functions which were already registered or executed will be
    skipped.

    Exit function will not be executed on SIGKILL, SIGSTOP or
    os._exit(0).
    """
    def fun_wrapper():
        if fun not in _executed_exit_funs:
            try:
                fun()
            finally:
                _executed_exit_funs.add(fun)

    def signal_wrapper(signum=None, frame=None):
        if signum is not None:
            pass
            # You may want to add some logging here.
            # XXX: if logging module is used it may complain with
            # "No handlers could be found for logger"
            # smap = dict([(getattr(signal, x), x) for x in dir(signal)
            #              if x.startswith('SIG')])
            # print("signal {} received by process with PID {}".format(
            #     smap.get(signum, signum), os.getpid()))
        fun_wrapper()
        # Only return the original signal this process was hit with
        # in case fun returns with no errors, otherwise process will
        # return with sig 1.
        if signum is not None:
            sys.exit(signum)

    if not callable(fun):
        raise TypeError("{!r} is not callable".format(fun))
    set([fun])  # raise exc if obj is not hash-able

    for sig in signals:
        # Register function for this signal and pop() the previously
        # registered one (if any). This can either be a callable,
        # SIG_IGN (ignore signal) or SIG_DFL (perform default action
        # for signal).
        old_handler = signal.signal(sig, signal_wrapper)
        if old_handler not in (signal.SIG_DFL, signal.SIG_IGN):
            # ...just for extra safety.
            if not callable(old_handler):
                continue
            # This is needed otherwise we'll get a KeyboardInterrupt
            # strace on interpreter exit, even if the process exited
            # with sig 0.
            if (sig == signal.SIGINT and
                    old_handler is signal.default_int_handler):
                continue
            # There was a function which was already registered for this
            # signal. Register it again so it will get executed (after our
            # new fun).
            if old_handler not in _registered_exit_funs:
                atexit.register(old_handler)
                _registered_exit_funs.add(old_handler)

    # This further registration will be executed in case of clean
    # interpreter exit (no signals received).
    if fun not in _registered_exit_funs or not signals:
        atexit.register(fun_wrapper)
        _registered_exit_funs.add(fun)