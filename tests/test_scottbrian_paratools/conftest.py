"""conftest.py module for testing."""

###############################################################################
# Standard Library
###############################################################################
import logging
import queue
import threading
import time
import traceback
from typing import Any, cast, Dict, Final, Optional, Union

###############################################################################
# Third Party
###############################################################################
import pytest

###############################################################################
# Local
###############################################################################
from scottbrian_paratools.smart_event import ThreadPair


###############################################################################
# logging
###############################################################################
logging.basicConfig(filename='ThreadComm.log',
                    filemode='w',
                    level=logging.DEBUG,
                    format='%(asctime)s '
                           '[%(levelname)8s] '
                           '%(filename)s:'
                           '%(funcName)s:'
                           '%(lineno)d '
                           '%(message)s')

logger = logging.getLogger(__name__)


###############################################################################
# Thread exceptions
# The following fixture depends on the following pytest specification:
# -p no:threadexception

# For PyCharm, the above specification goes into field Additional Arguments
# found at Run -> edit configurations
#
# For tox, the above specification goes into tox.ini in the
# the string for the commands=
# For example, in tox.ini for the pytest section:
# [testenv:py{36, 37, 38, 39}-pytest]
# description = invoke pytest on the package
# deps =
#     pytest
#
# commands =
#     pytest --import-mode=importlib -p no:threadexception {posargs}
#
# Usage:
# The thread_exc is an autouse fixture which means it does not need to be
# specified as an argument in the test case methods. If a thread fails,
# such as an assert error, then thread_exc will capture the error and
# raise it for the thread, and will also raise it during cleanup
# processing for the mainline to ensure the test case fails. Without
# thread_exc, any uncaptured thread failure will appear in the output, but the
# test case itself will not fail.
# Also, if you need to issue the thread error earlier, before cleanup,
# then specify thread_exc as an argument on the test method and then in
# mainline issue:
#     thread_exc.raise_exc_if_one()
#
# When the above is done, cleanup will not raise the error again.
#
###############################################################################
@pytest.fixture(autouse=True)
def thread_exc(monkeypatch: Any) -> "ExcHook":
    """Instantiate and return a ThreadExc for testing.

    Args:
        monkeypatch: pytest fixture used to modify code for testing

    Returns:
        a thread exception handler

    """

    class ExcHook:
        def __init__(self):
            self.exc_err_msg1 = ''

        def raise_exc_if_one(self):
            if self.exc_err_msg1:
                exc_msg = self.exc_err_msg1
                self.exc_err_msg1 = ''
                raise Exception(f'{exc_msg}')

    logger.debug(f'hook before: {threading.excepthook}')
    exc_hook = ExcHook()

    def mock_threading_excepthook(args):
        exc_err_msg = (f'SmartEvent excepthook: {args.exc_type}, '
                       f'{args.exc_value}, {args.exc_traceback},'
                       f' {args.thread}')
        traceback.print_tb(args.exc_traceback)
        logger.debug(exc_err_msg)
        current_thread = threading.current_thread()
        logger.debug(f'excepthook current thread is {current_thread}')
        # ExcHook.exc_err_msg1 = exc_err_msg
        exc_hook.exc_err_msg1 = exc_err_msg
        raise Exception(f'SmartEvent thread test error: {exc_err_msg}')

    monkeypatch.setattr(threading, "excepthook", mock_threading_excepthook)
    logger.debug(f'hook after: {threading.excepthook}')
    new_hook = threading.excepthook

    yield exc_hook

    # clean the registry in SmartEvent class
    # SmartEvent._registry = {}

    # clean the registry in ThreadPair class
    ThreadPair._registry = {}

    # the following check ensures that the test case waited via join for
    # any started threads to come home
    assert threading.active_count() == 1
    exc_hook.raise_exc_if_one()

    # the following assert ensures -p no:threadexception was specified
    assert threading.excepthook == new_hook


###############################################################################
# dt_format_arg_list
###############################################################################
dt_format_arg_list = [None,
                      '%H:%M',
                      '%H:%M:%S',
                      '%m/%d %H:%M:%S',
                      '%b %d %H:%M:%S',
                      '%m/%d/%y %H:%M:%S',
                      '%m/%d/%Y %H:%M:%S',
                      '%b %d %Y %H:%M:%S',
                      '%a %b %d %Y %H:%M:%S',
                      '%a %b %d %H:%M:%S.%f',
                      '%A %b %d %H:%M:%S.%f',
                      '%A %B %d %H:%M:%S.%f'
                      ]


@pytest.fixture(params=dt_format_arg_list)  # type: ignore
def dt_format_arg(request: Any) -> str:
    """Using different time formats.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(str, request.param)


###############################################################################
# Cmd Exceptions classes
###############################################################################
class CmdTimedOut(Exception):
    """Cmds timed out exception class."""
    pass


###############################################################################
# Cmd Class
###############################################################################
class Cmds:
    """Cmd class for testing."""
    def __init__(self):
        """Initialize the object."""
        # self.alpha_cmd = queue.Queue(maxsize=10)
        # self.beta_cmd = queue.Queue(maxsize=10)
        self.cmd_array: Dict[str, Any] = {}
        self.cmd_lock = threading.Lock()
        self.l_msg: Any = None
        self.r_code: Any = None
        self.start_time: float = 0.0
        self.previous_start_time: float = 0.0
        self.clock_in_use = False
        self.iteration = 0

    def queue_cmd(self, who: str, cmd: Optional[Any] = 'go') -> None:
        """Place a cmd on the cmd queue for the specified who.

        Args:
            who: alpha when cmd is for alpha, beta when cmd is for beta
            cmd: command to place on queue

        """
        with self.cmd_lock:
            if who not in self.cmd_array:
                self.cmd_array[who] = queue.Queue(maxsize=10)

        self.cmd_array[who].put(cmd,
                                block=True,
                                timeout=0.5)

    def get_cmd(self,
                who: str,
                timeout: Optional[Union[float, int]] = 3) -> Any:
        """Get the next command for alpha to do.

        Args:
            who: alpha to get cmd for alpha to do, beta for cmd for beta to do
            timeout: number of seconds allowed for cmd response

        Returns:
            the cmd to perform

        Raises:
            CmdTimedOut: {who} timed out waiting for cmd

        """
        with self.cmd_lock:
            if who not in self.cmd_array:
                self.cmd_array[who] = queue.Queue(maxsize=10)

        start_time = time.time()
        while True:
            try:
                cmd = self.cmd_array[who].get(block=True, timeout=0.1)
                return cmd
            except queue.Empty:
                pass

            if timeout < (time.time() - start_time):
                raise CmdTimedOut(f'{who} timed out waiting for cmd')

    def pause(self, seconds: Union[int, float], iter: int) -> None:
        """Sleep for the number of input seconds relative to start_time.

        Args:
            seconds: number of seconds to pause
            iter: clock iteration to pause on

        """
        while iter != self.iteration:
            time.sleep(0.1)

        remaining_seconds = seconds - (time.time() - self.start_time)
        if remaining_seconds > 0:
            time.sleep(remaining_seconds)

    def start_clock(self, iter: int) -> None:
        """Set the start_time to the current time.

        Args:
            iter: iteration to set for the clock
        """
        while self.clock_in_use:
            time.sleep(0.1)
        self.clock_in_use = True
        self.start_time = time.time()
        self.iteration = iter

    def duration(self) -> float:
        """Return the number of seconds from the start_time.

        Returns:
            number of seconds from the start_time
        """
        ret_duration = time.time() - self.start_time
        self.clock_in_use = False
        return ret_duration

###############################################################################
# ThreadPairDesc class
###############################################################################
class ThreadPairDesc:
    """Describes a ThreadPair with name and thread to verify."""

    STATE_UNKNOWN: Final[int] = 0
    STATE_ALIVE_REGISTERED: Final[int] = 1
    STATE_NOT_ALIVE_REGISTERED: Final[int] = 2
    STATE_NOT_ALIVE_UNREGISTERED: Final[int] = 3

    def __init__(self,
                 name: Optional[str] = '',
                 thread_pair: Optional[Any] = None,
                 thread: Optional[threading.Thread] = None,  # type: ignore
                 state: Optional[int] = 0,  # 0 is unknown
                 paired_with: Optional[Any] = None) -> None:
        """Initialize the ThreadPairDesc.

        Args:
            name: name of the ThreadPair
            thread_pair: the ThreadPair being tracked by this desc
            thread: the thread associated with this ThreadPair
            state: describes whether the ThreadPair is alive and registered
            paired_with: names the ThreadPair paired with this one, if one

        """
        self.name = name
        self.thread_pair = thread_pair
        if thread is not None:
            self.thread = thread
        else:
            self.thread = threading.current_thread()

        self.state = state
        self.paired_with = paired_with

    def verify_state(self) -> None:
        """Verify the state of the ThreadPair."""
        self.verify_thread_pair_desc()
        if self.paired_with is not None:
            self.paired_with.verify_thread_pair_desc()

    ###########################################################################
    # verify_thread_pair_desc
    ###########################################################################
    def verify_thread_pair_desc(self) -> None:
        """Verify the ThreadPair object is initialized correctly."""
        assert isinstance(self.thread, threading.Thread)
        assert self.thread_pair.name == self.name
        assert self.thread_pair.thread is self.thread
        assert isinstance(self.thread_pair.debug_logging_enabled, bool)

        #######################################################################
        # verify state
        #######################################################################
        if self.state == ThreadPairDesc.STATE_ALIVE_REGISTERED:
            assert self.thread.is_alive()
            assert self.name in ThreadPair._registry
            assert ThreadPair._registry[self.name] is self.thread_pair
        elif self.state == ThreadPairDesc.STATE_NOT_ALIVE_REGISTERED:
            assert not self.thread.is_alive()
            assert self.name in ThreadPair._registry
            assert ThreadPair._registry[self.name] is self.thread_pair
        elif self.state == ThreadPairDesc.STATE_NOT_ALIVE_UNREGISTERED:
            assert not self.thread.is_alive()
            # the registry might have a new entry with the same name as a
            # residual ThreadPair, so we also need to check to make sure
            # the old ThreadPair is not in the registry
            assert (self.name not in ThreadPair._registry
                    or ThreadPair._registry[self.name] is not self.thread_pair)

        #######################################################################
        # verify paired with desc
        #######################################################################
        if self.paired_with is None:
            assert self.thread_pair.remote is None
        else:
            assert self.thread_pair.remote is self.paired_with.thread_pair
            # if current is alive, remote must point back to current
            if self.state == ThreadPairDesc.STATE_ALIVE_REGISTERED:
                assert self.thread_pair.remote.remote is self.thread_pair


###############################################################################
# ThreadPairDescs class
###############################################################################
class ThreadPairDescs:
    """Contains a collection of ThreadPairDesc items."""

    ###########################################################################
    # __init__
    ###########################################################################
    def __init__(self):
        """Initialize object."""
        self._descs_lock = threading.RLock()
        self.descs: Dict[str, ThreadPairDesc] = {}

    ###########################################################################
    # add_desc
    ###########################################################################
    def add_desc(self,
                 desc: ThreadPairDesc,
                 verify: bool = True) -> None:
        """Add desc to collection.

        Args:
            desc: the desc to add
            verify: specify False when verification should not be done

        """
        with self._descs_lock:
            self.cleanup_registry()
            desc.state = ThreadPairDesc.STATE_ALIVE_REGISTERED
            self.descs[desc.name] = desc
            if verify:
                self.verify_registry()

    ###########################################################################
    # thread_end
    ###########################################################################
    def thread_end(self,
                   name: str) -> None:
        """Update ThreadPairDescs to show a thread ended.

        Args:
            name: name of ThreadPair for desc to be updated

        """
        with self._descs_lock:
            # Note that this action does not cause registry cleanup
            # make sure thread is not alive
            assert not self.descs[name].thread_pair.thread.is_alive()

            # make sure we are transitioning correctly
            assert (self.descs[name].state
                    == ThreadPairDesc.STATE_ALIVE_REGISTERED)
            self.descs[name].state = ThreadPairDesc.STATE_NOT_ALIVE_REGISTERED

            ###################################################################
            # verify the registry
            ###################################################################
            self.verify_registry()

    ###########################################################################
    # cleanup
    ###########################################################################
    def cleanup(self) -> None:
        """Perform cleanup for ThreadPairDescs."""
        # Cleanup applies to all of the descs and is done
        # when first thing when a new ThreadPair is instantiated and
        # registered, or when a pair_with is done. This action is called
        # here for the other cases that trigger cleanup, such as
        # getting a ThreadPairRemoteThreadNotAlive error.
        with self._descs_lock:
            self.cleanup_registry()

            ###################################################################
            # verify the registry
            ###################################################################
            self.verify_registry()

    ###########################################################################
    # paired
    ###########################################################################
    def paired(self,
               name1: Optional[str] = '',
               name2: Optional[str] = '',
               verify: bool = True) -> None:
        """Update ThreadPairDescs to show paired status.

        Args:
            name1: name of ThreadPair for desc that is paired with name2
            name2: name of ThreadPair for desc that is paired with name1, or
                   null if name1 became unpaired
            verify: specify False when verification should not be done

        """
        with self._descs_lock:
            self.cleanup_registry()
            # make sure we can allow the pair
            assert self.descs[name1].thread_pair.thread.is_alive()
            assert (self.descs[name1].state
                    == ThreadPairDesc.STATE_ALIVE_REGISTERED)
            assert name1 in ThreadPair._registry
            assert name1 in self.descs

            # note that name2 will normally be the ThreadPairDesc
            # that we are pairing with, but it could be None in the case
            # where we are doing a second or subsequent pairing but the
            # remote fails to to do the pair, which means we lose the
            # residual name2 ThreadPairDesc
            if name2:
                assert name2 in ThreadPair._registry
                assert self.descs[name2].thread_pair.thread.is_alive()
                assert (self.descs[name2].state
                        == ThreadPairDesc.STATE_ALIVE_REGISTERED)
                assert name2 in ThreadPair._registry
                assert name2 in self.descs
                self.descs[name1].paired_with = self.descs[name2]
                self.descs[name2].paired_with = self.descs[name1]
            else:
                self.descs[name1].paired_with = None

            ###################################################################
            # verify the registry
            ###################################################################
            if verify:
                self.verify_registry()

    ###########################################################################
    # verify_registry
    ###########################################################################
    def verify_registry(self):
        """Verify the registry."""
        with self._descs_lock:
            num_registered = 0
            for key, item in self.descs.items():
                if (item.state == ThreadPairDesc.STATE_ALIVE_REGISTERED
                        or item.state
                        == ThreadPairDesc.STATE_NOT_ALIVE_REGISTERED):
                    num_registered += 1
                item.verify_state()

            assert len(ThreadPair._registry) == num_registered

    ###########################################################################
    # cleanup_registry
    ###########################################################################
    def cleanup_registry(self):
        """Cleanup the registry."""
        for key, item in self.descs.items():
            if item.state == ThreadPairDesc.STATE_NOT_ALIVE_REGISTERED:
                assert not item.thread_pair.thread.is_alive()
                item.state = ThreadPairDesc.STATE_NOT_ALIVE_UNREGISTERED
