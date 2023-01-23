"""Module smart_thread.

===========
SmartThread
===========

The SmartThread class provides messaging, wait/resume, and sync
functions for threads in a multithreaded application. The functions have
deadlock detection and will also detect when a thread becomes not alive.

:Example: create a SmartThread for threads named alpha and beta

>>> import scottbrian_paratools.smart_thread as st
>>> def f1() -> None:
...     print('f1 beta entered')
...     beta_thread.send_msg(targets='alpha', msg='hi alpha, this is beta')
...     beta_thread.wait('remote=alpha')
...     print('f1 beta exiting')
>>> print('mainline entered')
>>> alpha_thread = st.SmartThread(name='alpha')
>>> beta_thread = st.SmartThread(name='beta', target=f1)
>>> beta_thread.smart_start()
>>> msg_from_beta=alpha_thread.recv_msg(remote='beta')
>>> print(msg_from_beta)
>>> alpha_thread.resume(targets='beta')
>>> alpha_thread.smart_join(targets='beta')
>>> print('mainline exiting')
mainline entered
f1 beta entered
hi alpha, this is beta
f1 beta exiting
mainline exiting


The smart_thread module contains:

    1) SmartThread class with methods:

       a. join
       b. recv_msg
       c. resume
       d. send_msg
       e. start
       f. sync
       g. wait

"""

########################################################################
# Standard Library
########################################################################
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from enum import auto, Enum, Flag
import logging
import queue
import sys
import threading
import time
from typing import (Any, Callable, ClassVar, Optional, Type, TypeAlias,
                    TYPE_CHECKING, Union)

########################################################################
# Third Party
########################################################################

########################################################################
# Local
########################################################################
from scottbrian_utils.diag_msg import get_formatted_call_sequence
from scottbrian_utils.timer import Timer
from scottbrian_locking import se_lock as sel


IntFloat: TypeAlias = Union[int, float]
OptIntFloat: TypeAlias = Optional[IntFloat]
StrListStrSetStr: TypeAlias = Union[str, list[str], set[str]]
OptStrListStrSetStr: TypeAlias = Optional[StrListStrSetStr]


########################################################################
# SmartThread class exceptions
########################################################################
class SmartThreadError(Exception):
    """Base class for exceptions in this module."""
    pass


class SmartThreadDetectedOpFromForeignThread(SmartThreadError):
    """SmartThread exception attempted op from unregistered thread."""
    pass


class SmartThreadErrorInRegistry(SmartThreadError):
    """SmartThread exception for registry error."""


class SmartThreadIncorrectNameSpecified(SmartThreadError):
    """SmartThread exception for a name that is not a str."""


class SmartThreadNameAlreadyInUse(SmartThreadError):
    """SmartThread exception for using a name already in use."""
    pass


class SmartThreadRemoteThreadNotAlive(SmartThreadError):
    """SmartThread exception for remote thread not alive."""


class SmartThreadConflictDeadlockDetected(SmartThreadError):
    """SmartThread exception for conflicting requests."""
    pass


# class SmartThreadInconsistentFlagSettings(SmartThreadError):
#     """SmartThread exception for flag setting that are not valid."""
#     pass


class SmartThreadWaitDeadlockDetected(SmartThreadError):
    """SmartThread exception for wait deadlock detected."""
    pass


# class SmartThreadWaitUntilTimeout(SmartThreadError):
#     """SmartThread exception for pause_until timeout."""
#     pass


class SmartThreadRequestTimedOut(SmartThreadError):
    """SmartThread exception for request timeout."""
    pass


class SmartThreadMutuallyExclusiveTargetThreadSpecified(SmartThreadError):
    """SmartThread exception mutually exclusive target and thread."""
    pass


# class SmartThreadRemoteSmartThreadMismatch(SmartThreadError):
#     """SmartThread exception remote_array SmartThread does not match
#     registry SmartThread.
#     """
#     pass


# class SmartThreadRemoteThreadMismatch(SmartThreadError):
#     """SmartThread exception remote_array SmartThread.thread does not
#     match registry SmartThread.thread.
#     """
#     pass


# class SmartThreadStatusLockMismatch(SmartThreadError):
#     """SmartThread exception remote_array status_lock does not match
#     remote.remote_array status_lock.
#     """
#     pass


# class SmartThreadRemoteMsgQMismatch(SmartThreadError):
#     """SmartThread exception remote_array remote msg_q does not match
#     remote.remote_array msg_q.
#     """
#     pass


# class SmartThreadSyncTimedOut(SmartThreadError):
#     """SmartThread exception sync timed out."""
#     pass


class SmartThreadArgsSpecificationWithoutTarget(SmartThreadError):
    """SmartThread exception args specified without target."""
    pass


class SmartThreadInvalidUnregister(SmartThreadError):
    """SmartThread exception for invalid unregister request."""
    pass


class SmartThreadInvalidInput(SmartThreadError):
    """SmartThread exception for invalid input on a request."""
    pass


########################################################################
# ReqType
# contains the type of request
########################################################################
class ReqType(Enum):
    Resume = auto()
    Sync = auto()
    Wait = auto()


########################################################################
# RequestBlock
# contains the remotes and timer returned from _common_setup
########################################################################

PairKey: TypeAlias = tuple[str, str]
PairKeyRemote: TypeAlias = tuple[PairKey, str]
@dataclass
class RequestBlock:
    """Setup block."""
    request_name: str
    remotes: set[str]
    pk_remotes: list[PairKeyRemote]
    timer: Timer
    raise_not_alive: bool
    do_refresh: bool
    stopped_remotes: set[str]
    conflict_remotes: set[str]
    deadlock_remotes: set[str]



########################################################################
# ErrorRemotes
# contains the remotes that were found to be stopped or in deadlock
########################################################################
@dataclass
class ErrorRemotes:
    """Error remotes."""
    stopped_remotes: set[str]
    conflict_remotes: set[str]
    deadlock_remotes: set[str]

########################################################################
# ThreadCreate Flags Class
# These flags are used to indicate how the SmartThread was created
# during initialization based on the arguments.
########################################################################
class ThreadCreate(Flag):
    """Thread create flags."""
    Current = auto()
    Target = auto()
    Thread = auto()


########################################################################
# ThreadStatus Flags Class
# These flags are used to indicate the life cycle of a SmartThread.
# Initializing is set in the __init__ method. The __init__ method calls
# _register and upon return the status of Registered is set. When
# the start method is called, the status is set to Starting, and after
# the start is done and the thread is alive, the status is set to Alive.
# When the join method is called and the thread becomes not alive,
# the status is set to Stopped which then allows the _clean_up_registry
# method to remove the SmartThread.
########################################################################
class ThreadStatus(Flag):
    """Thread status flags."""
    Unregistered = auto()
    Initializing = auto()
    Registered = auto()
    Starting = auto()
    Alive = auto()
    Stopped = auto()


########################################################################
# PairStatus Class
# Each remote_array entry has a pair_status variable to indicate whether
# both the local and remote threads are ready to interact.
########################################################################
PairStatus = Enum('PairStatus',
                  'NotReady '
                  'Ready ')


########################################################################
# WaitFor Class
# Used on the smart_wait to specify whether to wait for:
#     All: every remote specified in the remotes argument must
#         do a resume to complete the wait
#     Any: any remote that does a resume will complete the wait
########################################################################
class WaitFor(Enum):
    All = auto()
    Any = auto()


########################################################################
# SmartThread Class
########################################################################
class SmartThread:
    """Provides services among one or more threads."""

    ####################################################################
    # Constants
    ####################################################################

    ####################################################################
    # Registry
    ####################################################################
    # The _registry is a dictionary of SmartClass instances keyed by the
    # SmartThread name.
    _registry_lock: ClassVar[sel.SELock] = sel.SELock()
    _registry: ClassVar[dict[str, "SmartThread"]] = {}

    # time_last_pair_array_update is initially set to
    # datetime(2000, 1, 1, 12, 0, 0) and the _registry_last_update is
    # initially set to datetime(2000, 1, 1, 12, 0, 1) which will ensure
    # that each thread will initially refresh their remote_array when
    # instantiated.
    _registry_last_update: datetime = datetime(2000, 1, 1, 12, 0, 1)

    ####################################################################
    # ConnectionStatusBlock
    # Coordinates the various actions involved in satisfying a
    # send_msg, recv_msg, smart_wait, smart_resume, or smart_sync
    # request.
    ####################################################################
    @dataclass
    class ConnectionStatusBlock:
        """Connection status block."""
        wait_event: threading.Event
        sync_event: threading.Event
        msg_q: queue.Queue[Any]
        code: Any = None
        del_deferred: bool = False
        wait_wait: bool = False
        sync_wait: bool = False
        wait_timeout_specified: bool = False
        deadlock: bool = False
        conflict: bool = False

    @dataclass
    class ConnectionPair:
        """ConnectionPair class."""
        status_lock: threading.Lock
        pair_status: PairStatus
        status_blocks: dict[str, "SmartThread.ConnectionStatusBlock"]

    _pair_array: ClassVar[
        dict[PairKey, "SmartThread.ConnectionPair"]] = {}
    _pair_array_last_update: datetime = datetime(
        2000, 1, 1, 12, 0, 1)

    ####################################################################
    # __init__
    ####################################################################
    def __init__(self, *,
                 name: str,
                 target: Optional[Callable[..., Any]] = None,
                 args: Optional[tuple[Any, ...]] = None,
                 kwargs: Optional[dict[str, Any]] = None,
                 thread: Optional[threading.Thread] = None,
                 auto_start: Optional[bool] = True,
                 default_timeout: OptIntFloat = None,
                 max_msgs: Optional[int] = 0
                 ) -> None:
        """Initialize an instance of the SmartThread class.

        Args:
            name: name to be used to refer to this SmartThread. The name
                      may be the same as the threading.Thread name, but
                      it is not required that they be the same.
            target: specifies that a thread is to be created and started
                        with the given target. Mutually exclusive with
                        the *thread* specification. Note that the
                        threading.Thread will be created with *target*,
                        *args* if specified, and the *name*.
            args: args for the thread creation when *target* is
                      specified.
            kwargs: keyword args for the thread creation when *target*
                is specified.
            thread: specifies the thread to use instead of the current
                        thread - needed when SmartThread is instantiated
                        in a class that inherits threading.Thread in
                        which case thread=self is required. Mutually
                        exclusive with *target*.
            auto_start: specifies whether to start the thread. Valid for
                            target or thread only. Ignored when neither
                            target nor thread specified.
            default_timeout: the timeout value to use when a request is
                made and a timeout for the request is
                not specified. If default_timeout is
                specified, a value of zero or less will
                be equivalent to None, meaning that a
                default timeout will not be used.
            max_msgs: specifies the maximum number of messages that can
                occupy the message queue. Zero (the default) specifies
                no limit.

        Raises:
            SmartThreadIncorrectNameSpecified: Attempted SmartThread
                  instantiation with incorrect name of {name}.
            SmartThreadMutuallyExclusiveTargetThreadSpecified: Attempted
                  SmartThread instantiation with both target and thread
                  specified.
            SmartThreadArgsSpecificationWithoutTarget: Attempted
                  SmartThread instantiation with args specified and without
                  target specified.

        Notes:
              There are five possible timeout cases at the time a
              request is made:
              a. default_timeout = None, zero or less
                 request timeout = None, zero or less
                 result: the request will not timeout
              b. default_timeout = None, zero or less
                 request timeout = value above zero
                 result: request timeout value will be used
              c. default_timeout = above zero
                 request_timeout = None
                 result: default_timeout value will be used
              d. default_timeout = above zero
                 request_timeout = zero or less
                 result: the request will not time out
              e. default_timeout = value above zero
                 request_timeout = value above zero
                 result: request timeout value will be used

        """
        self.specified_args = locals()  # used for __repr__, see below

        self.logger = logging.getLogger(__name__)

        # Set a flag to use to make it easier to determine whether debug
        # logging is enabled
        self.debug_logging_enabled = self.logger.isEnabledFor(logging.DEBUG)

        if not isinstance(name, str):
            raise SmartThreadIncorrectNameSpecified(
                'Attempted SmartThread instantiation with incorrect name of '
                f'{name}.')
        self.name = name

        if target and thread:
            raise SmartThreadMutuallyExclusiveTargetThreadSpecified(
                'Attempted SmartThread instantiation with both target and '
                'thread specified.')

        if (not target) and (args or kwargs):
            raise SmartThreadArgsSpecificationWithoutTarget(
                'Attempted SmartThread instantiation with args or '
                'kwargs specified but without target specified.')

        if target:  # caller wants a thread created
            self.thread_create = ThreadCreate.Target
            self.thread = threading.Thread(target=target,
                                           args=args,
                                           kwargs=kwargs,
                                           name=name)
            # if args or kwargs:
            #     self.thread = threading.Thread(target=target,
            #                                    args=args,
            #                                    kwargs=kwargs,
            #                                    name=name)
            # else:
            #     self.thread = threading.Thread(target=target,
            #                                    name=name)
        elif thread:  # caller provided the thread to use
            self.thread_create = ThreadCreate.Thread
            self.thread = thread
            self.thread.name = name
        else:  # caller is running on the thread to be used
            self.thread_create = ThreadCreate.Current
            self.thread = threading.current_thread()
            self.thread.name = name

        self.status: ThreadStatus = ThreadStatus.Unregistered
        self._set_status(
            target_thread=self,
            new_status=ThreadStatus.Initializing)

        self.auto_start = auto_start

        self.default_timeout = default_timeout

        self.setup_block: RequestBlock = RequestBlock(
            request_name='init',
            remotes=set(),
            pk_remotes=[],
            timer=Timer(),
            raise_not_alive=False,
            do_refresh=False,
            stopped_remotes=set(),
            conflict_remotes=set(),
            deadlock_remotes=set())

        self.sync_request = False

        self.req_name: str = ''

        self.code = None

        self.max_msgs = max_msgs

        self.remotes_unregistered: set[str] = set()
        self.remotes_full_send_q: set[str] = set()

        self.request_timeout_names: set[str] = set()

        # register this new SmartThread so others can find us
        self._register()

        self.auto_started = False
        if self.auto_start and not self.thread.is_alive():
            self.smart_start()
            self.auto_started = True

    ####################################################################
    # repr
    ####################################################################
    def __repr__(self) -> str:
        """Return a representation of the class.

        Returns:
            The representation as how the class is instantiated

        :Example: instantiate a SmartThread and call repr

        >>> import scottbrian_paratools.smart_event as st
        >>> smart_thread = SmartThread(name='alpha')
        >>> repr(smart_thread)
        SmartThread(name='alpha')

        """
        if TYPE_CHECKING:
            __class__: Type[SmartThread]
        classname = self.__class__.__name__
        parms = f"name='{self.name}'"

        for key, item in self.specified_args.items():
            if item:  # if not None
                if key == 'target':
                    function_name = item.__name__
                    parms += ', ' + f'{key}={function_name}'
                elif key in ('args', 'thread', 'default_timeout'):
                    if item is not self:  # avoid recursive repr loop
                        parms += ', ' + f'{key}={item}'
        # elif key in ('args', 'thread', 'default_timeout'):
        return f'{classname}({parms})'

    ####################################################################
    # _get_status
    ####################################################################
    @staticmethod
    def _get_status(name: str) -> ThreadStatus:
        """Get the status of a thread.

        Args:
            name: name of thread to get status for

        Returns:
            The thread status
        """
        if name not in SmartThread._registry:
            return ThreadStatus.Unregistered
        if (not SmartThread._registry[name].thread.is_alive() and
                SmartThread._registry[name].status == ThreadStatus.Alive):
            return ThreadStatus.Stopped
        return SmartThread._registry[name].status

    ####################################################################
    # _set_status
    ####################################################################
    def _set_status(self,
                    target_thread: "SmartThread",
                    new_status: ThreadStatus) -> bool:
        """Set the status for a thread.

        Args:
            target_thread: thread to set status for
            new_status: the new status to be set

        Returns:
            True if status was changed, False otherwise
        """
        saved_status = target_thread.status
        if saved_status == new_status:
            return False
        target_thread.status = new_status

        self.logger.debug(
            f'{threading.current_thread().name} set '
            f'status for thread {target_thread.name} from {saved_status} to '
            f'{new_status}', stacklevel=2)
        return True

    ####################################################################
    # _register
    ####################################################################
    def _register(self) -> None:
        """Register SmartThread in the class registry.

        Raises:
            SmartThreadIncorrectNameSpecified: The name for SmartThread
                must be of type str.
            SmartThreadNameAlreadyInUse: An entry for a SmartThread with
                name = *name* is already registered for a different
                thread.

        Notes:
            1) Any old entries for SmartThreads whose threads are not
               alive are removed when this method is called by calling
               _clean_up_registry().
            2) Once a thread become not alive, it can not be
               resurrected. The SmartThread is bound to the thread it
               starts with.

        """
        # Make sure name is valid
        if not isinstance(self.name, str):
            raise SmartThreadIncorrectNameSpecified(
                'The name for SmartThread must be of type str.')

        with sel.SELockExcl(SmartThread._registry_lock):
            self.logger.debug(f'{threading.current_thread().name} obtained '
                              '_registry_lock, class name = '
                              f'{self.__class__.__name__}')

            # Remove any old entries
            self._clean_up_registry(process='register')

            # Add entry if not already present
            if self.name not in SmartThread._registry:
                SmartThread._registry[self.name] = self
                if self.thread.is_alive():
                    new_status = ThreadStatus.Alive
                else:
                    new_status = ThreadStatus.Registered
                self._set_status(
                    target_thread=self,
                    new_status=new_status)
                SmartThread._registry_last_update = datetime.utcnow()
                print_time = (SmartThread._registry_last_update
                              .strftime("%H:%M:%S.%f"))
                self.logger.debug(
                    f'{threading.current_thread().name} added {self.name} '
                    f'to SmartThread registry at UTC {print_time}')
                self._refresh_pair_array()
            elif SmartThread._registry[self.name] != self:
                raise SmartThreadNameAlreadyInUse(
                    f'An entry for a SmartThread with name = {self.name} is '
                    'already registered for a different thread.')

    ####################################################################
    # _clean_up_registry
    ####################################################################
    def _clean_up_registry(self,
                           process: str
                           ) -> None:
        """Clean up any old not alive items in the registry.

        Args:
            process: process being done for cleanup
        Returns:
            dictionary of log status items

        Raises:
            SmartThreadErrorInRegistry: Registry item with key {key} has
                non-matching item.name of {item.name}.

        Notes:
            1) Must be called holding _registry_lock

        """
        # Remove any old entries
        keys_to_del = []
        for key, item in SmartThread._registry.items():
            is_alive: bool = item.thread.is_alive()
            status: ThreadStatus = item.status
            self.logger.debug(
                f'key = {key}, item = {item}, '
                f'item.thread.is_alive() = {is_alive}, '
                f'status: {status}')
            if ((not item.thread.is_alive())
                    and (item.status & ThreadStatus.Stopped)):
                keys_to_del.append(key)

            if key != item.name:
                raise SmartThreadErrorInRegistry(
                    f'Registry item with key {key} has non-matching '
                    f'item.name of {item.name}.')

        changed = False
        for key in keys_to_del:
            del SmartThread._registry[key]
            changed = True
            self.logger.debug(f'{threading.current_thread().name} removed '
                              f'{key} from registry for {process=}')

        # update time only when we made a change, otherwise we can
        # get into an update loop where each remote sees that
        # _registry_last_update is later and calls _clean_up_registry
        # and sets _registry_last_update, and then this thread sees a
        # later time in _registry_last_update and calls _clean_up_registry
        # which leads to a forever ping pong...
        if changed:
            self._refresh_pair_array()
            SmartThread._registry_last_update = datetime.utcnow()
            print_time = (SmartThread._registry_last_update
                          .strftime("%H:%M:%S.%f"))
            self.logger.debug(f'{threading.current_thread().name} did cleanup '
                              f'of registry at UTC {print_time}, deleted '
                              f'{keys_to_del}')

    ####################################################################
    # start
    ####################################################################
    def smart_start(self) -> None:
        """Start the thread.

        :Example: instantiate a SmartThread and start the thread

        >>> import scottbrian_utils.smart_thread as st
        >>> def f1() -> None:
        ...     print('f1 beta entered')
        >>> beta_smart_thread = SmartThread(name='beta', target=f1)
        >>> beta_smart_thread.smart_start()
        f1 beta entered

        """
        with sel.SELockExcl(SmartThread._registry_lock):
            if not self.thread.is_alive():
                self._set_status(
                    target_thread=self,
                    new_status=ThreadStatus.Starting)
                # self.thread.start()
                threading.Thread.start(self.thread)

            if self.thread.is_alive():
                self._set_status(
                    target_thread=self,
                    new_status=ThreadStatus.Alive)

        self.logger.debug(
            f'{threading.current_thread().name} started thread {self.name}, '
            f'thread.is_alive(): {self.thread.is_alive()}, '
            f'status: {self.status}')

    ####################################################################
    # unregister
    ####################################################################
    def unregister(self, *,
                   targets: Union[str, set[str]],
                   log_msg: Optional[str] = None) -> None:
        """Unregister threads that were never started.

        Args:
            targets: thread names that are to be unregistered
            log_msg: log message to issue


        Notes:
            1) A thread that is created but not started remains in the
               registered state until it is started at which time it
               enters the active state

        :Example: instantiate SmartThread without auto_start and then
                      unregister the thread

        >>> import scottbrian_paratools.smart_event as st
        >>> def f1() -> None:
        ...     print('f1 beta entered')
        ...     beta_smart_thread.wait()
        ...     print('f1 beta exiting')

        >>> alpha_smart_thread = SmartThread(name='alpha')
        >>> beta_smart_thread = SmartThread(name='beta',
        ...                                 target=f1,
        ...                                 auto_start=False)
        >>> beta_smart_thread.unregister()

        """
        # get RequestBlock with targets in a set and a timer object
        sb = self._common_setup(remotes=targets, timeout=None)

        if log_msg and self.debug_logging_enabled:
            exit_log_msg = self._issue_entry_log_msg(
                prefix=f'{threading.current_thread().name} to unregister '
                       f'{sb.remotes}.',
                log_msg=log_msg)
        else:
            exit_log_msg = None

        work_remotes = sb.remotes.copy()

        while work_remotes:
            for remote in work_remotes:
                with sel.SELockExcl(SmartThread._registry_lock):
                    if remote not in SmartThread._registry:
                        raise SmartThreadInvalidUnregister(
                            f'{self.name} attempted to unregister '
                            f'remote thread {remote} which was not '
                            f'found in the registry.')
                    if SmartThread._registry[
                            remote].status != ThreadStatus.Registered:
                        raise SmartThreadInvalidUnregister(
                            f'{self.name} attempted to unregister '
                            f'remote thread {remote} which had the '
                            'incorrect status of '
                            f'{SmartThread._registry[remote].status} '
                            f'instead of the required status of '
                            f'{ThreadStatus.Registered}')

                    # indicate remove from registry
                    self._set_status(
                        target_thread=SmartThread._registry[remote],
                        new_status=ThreadStatus.Stopped)
                    # remove this thread from the registry
                    self._clean_up_registry(process='unregister')

                    self.logger.debug(
                        f'{self.name} did successful unregister of '
                        f'{remote}.')

                    # restart while loop with one less remote
                    work_remotes.remove(remote)
                    break

            if sb.timer.is_expired():
                self.logger.error(
                    f'{self.name} raising SmartThreadRequestTimedOut waiting '
                    f'for {work_remotes}')
                raise SmartThreadRequestTimedOut(
                    f'{self.name} timed out waiting for {work_remotes}.')

            time.sleep(0.2)

        if exit_log_msg:
            self.logger.debug(exit_log_msg)

    ####################################################################
    # join
    ####################################################################
    def smart_join(self, *,
                   targets: Union[str, set[str]],
                   log_msg: Optional[str] = None,
                   timeout: OptIntFloat = None) -> None:
        """Join with remote targets.

        Args:
            targets: thread names that are to be joined
            log_msg: log message to issue
            timeout: timeout to use instead of default timeout

        Raises:
            SmartThreadRequestTimedOut: join timed out waiting for targets.

        Notes:
            1) A ``resume()`` request can be done on an event that is not yet
               being waited upon. This is referred as a **pre-resume**. The
               remote thread doing a ``wait()`` request on a **pre-resume**
               event will get back control immediately.
            2) If the ``resume()`` request sees that the event has already
               been resumed, it will loop and wait for the event to be cleared
               under the assumption that the event was previously
               **pre-resumed** and a wait is imminent. The ``wait()`` will
               clear the event and the ``resume()`` request will simply resume
               it again as a **pre-resume**.
            3) If one thread makes a ``resume()`` request and the other thread
               becomes not alive, the ``resume()`` request raises a
               **SmartThreadRemoteThreadNotAlive** error.

        :Example: instantiate SmartThread and ``resume()`` event that function
                    waits on

        >>> import scottbrian_paratools.smart_event as st
        >>> def f1() -> None:
        ...     print('f1 beta entered')
        ...     beta_smart_thread.wait()
        ...     print('f1 beta exiting')

        >>> alpha_smart_thread = SmartThread(name='alpha')
        >>> beta_smart_thread = SmartThread(name='beta', target=f1)
        >>> alpha_smart_thread.resume()
        >>> beta_smart_thread.smart_join()

        """
        # get RequestBlock with targets in a set and a timer object
        sb = self._common_setup(remotes=targets, timeout=timeout)

        # if caller specified a log message to issue
        # log_msg_part2 = ''
        # if log_msg and self.debug_logging_enabled:
        #     log_msg_part2 = (
        #         f'{self.name} to join {sorted(sb.targets)}. '
        #         f'{get_formatted_call_sequence(latest=1, depth=1)} '
        #         f'{log_msg}')
        #     self.logger.debug(
        #         f'join() entered: {log_msg_part2}')
        if log_msg and self.debug_logging_enabled:
            exit_log_msg = self._issue_entry_log_msg(
                prefix=f'{self.name} to join {sorted(sb.remotes)}.',
                log_msg=log_msg)
        else:
            exit_log_msg = None

        work_remotes = sb.remotes.copy()

        while work_remotes:
            for remote in work_remotes:
                with sel.SELockExcl(SmartThread._registry_lock):
                    if remote in SmartThread._registry:
                        # Note that if the remote thread was never
                        # started, the following join will raise an
                        # error. If the thread is eventually started,
                        # we currently have no way to detect that and
                        # react. We can only hope that a failed join
                        # here will help give us a clue that something
                        # went wrong.
                        # Note also that we timeout each join after a
                        # short 0.2 seconds so that we release and
                        # re-obtain the registry lock in between
                        # attempts. This is done to ensure we don't
                        # deadlock with any of the other services
                        # (e.g., recv_msg)
                        try:
                            SmartThread._registry[remote].thread.join(
                              timeout=0.2)
                        except RuntimeError:
                            # We know the thread is registered, so
                            # we will skip it for now and come back to it
                            # later. If it never starts and exits then
                            # we will timeout (if timeout was specified)
                            continue
                        # we need to check to make sure the thread is
                        # not alive in case we timed out
                        if not SmartThread._registry[remote].thread.is_alive():
                            # indicate remove from registry
                            self._set_status(
                                target_thread=SmartThread._registry[remote],
                                new_status=ThreadStatus.Stopped)
                            # remove this thread from the registry
                            self._clean_up_registry(
                                process='join')

                            self.logger.debug(
                                f'{self.name} did successful join of '
                                f'{remote}.')

                            # restart while loop with one less remote
                            work_remotes.remove(remote)
                            break

            if sb.timer.is_expired():
                self.logger.error(
                    f'{self.name} raising SmartThreadRequestTimedOut waiting '
                    f'for {sorted(work_remotes)}')
                raise SmartThreadRequestTimedOut(
                    f'{self.name} timed out waiting for {work_remotes}.')

            time.sleep(0.2)

        if exit_log_msg:
            self.logger.debug(exit_log_msg)

    ####################################################################
    # _get_pair_key
    ####################################################################
    @staticmethod
    def _get_pair_key(name0: str,
                      name1: str) -> PairKey:
        """Return a key to use for the connection pair array.

        Args:
            name0: name to combine with name1
            name1: name to combine with name0

        Returns:
            the key to use for the connection pair array

        """
        if name0 < name1:
            return name0, name1
        else:
            return name1, name0

    ###########################################################################
    # _refresh_pair_array
    ###########################################################################
    def _refresh_pair_array(self) -> None:
        """Update the connection pair array from the _registry.

        Notes:
            1) A thread is registered during initialization and will
               initially not be alive until started.
            2) If a request is made that includes a yet to be registered
               thread, or one that is not yet alive, the request will
               loop until the remote thread becomes registered and
               alive.
            3) After a thread is registered and is alive, if it fails
               and become not alive, it will remain in the registry
               until its status is changed to Stopped to indicate it was
               once alive. Its status is set to Stopped when a join is
               done. This will allow a request to know whether to wait
               for the thread to become alive, or to raise an error for
               an attempted request on a thread that is no longer alive.
            4) The remote_array will simply mirror what is in the
               registry.

        Error cases:
            1) remote_array thread and registry thread do not match


        Expected cases:
            1) remote_array does not have a registry entry - add the
               registry entry to the remote array
            2) remote_array entry does not have flag set to indicate
               thread became not alive, but registry does have the flag
               set - simply set the flag in the remote_array entry -
               request will fail if remote is part of the request
            3) registry entry does not have a remote_array entry -
               remove remote_array entry

        """
        current_thread_name = threading.current_thread().name
        self.logger.debug(
            f'{current_thread_name} entered _refresh_pair_array')
        changed = False
        # scan registry and adjust status
        for name0, s_thread1 in (SmartThread._registry.items()):

            for name1, s_thread2 in (SmartThread._registry.items()):
                if name0 == name1:
                    continue

                # create new connection pair if needed
                pair_key = self._get_pair_key(name0, name1)
                if pair_key not in SmartThread._pair_array:
                    SmartThread._pair_array[pair_key] = (
                        SmartThread.ConnectionPair(
                            status_lock=threading.Lock(),
                            pair_status=PairStatus.Ready,
                            status_blocks={}
                        ))
                    self.logger.debug(
                        f'{current_thread_name} created '
                        '_refresh_pair_array with '
                        f'pair_key = {pair_key}')
                    changed = True

                # add status block for name0 and name1 if needed
                for name in (name0, name1):
                    if (name in SmartThread._pair_array[
                            pair_key].status_blocks):
                        # reset del_deferred in case it is ON and the
                        # other name is a resurrected thread
                        SmartThread._pair_array[
                            pair_key].status_blocks[
                            name].del_deferred = False
                    else:
                        # add an entry for this thread
                        SmartThread._pair_array[
                            pair_key].status_blocks[
                            name] = SmartThread.ConnectionStatusBlock(
                                    wait_event=threading.Event(),
                                    sync_event=threading.Event(),
                                    msg_q=queue.Queue(maxsize=self.max_msgs))
                        self.logger.debug(
                            f'{current_thread_name} added status_blocks entry '
                            f'for pair_key = {pair_key}, '
                            f'name = {name}')
                        changed = True

        # find removable entries in connection pair array
        connection_array_del_list = []
        for pair_key in SmartThread._pair_array.keys():
            # remove thread(s) from status_blocks if not registered
            for thread_name in pair_key:
                if (thread_name not in SmartThread._registry
                        and thread_name in SmartThread._pair_array[
                            pair_key].status_blocks):
                    _ = SmartThread._pair_array[
                            pair_key].status_blocks.pop(thread_name, None)
                    self.logger.debug(
                        f'{current_thread_name} removed status_blocks entry'
                        f' for pair_key = {pair_key}, name = {thread_name}')
                    changed = True

            # At this point, either or both threads of the pair will
            # have been removed if no longer registered. If only one
            # thread was removed, then the remaining thread is still
            # registered but should also be removed unless it has one or
            # more messages pending, in which case we need to leave the
            # entry in place to allow the thread to eventually read its
            # messages. For this case, we will set the del_pending flag
            # to indicate in the recv_msg method that once the msg_q is
            # empty, _refresh_pair_array should be called to clean up
            # this entry.
            if len(SmartThread._pair_array[pair_key].status_blocks) == 1:
                thread_name = list(SmartThread._pair_array[
                        pair_key].status_blocks.keys())[0]
                if (SmartThread._pair_array[
                        pair_key].status_blocks[thread_name].msg_q.empty()
                        and not SmartThread._pair_array[
                        pair_key].status_blocks[
                            thread_name].wait_event.is_set()
                        and not SmartThread._pair_array[
                        pair_key].status_blocks[
                            thread_name].sync_event.is_set()):
                    _ = SmartThread._pair_array[
                        pair_key].status_blocks.pop(thread_name, None)
                    self.logger.debug(
                        f'{current_thread_name} removed status_blocks entry'
                        f' for pair_key = {pair_key}, name = '
                        f'{thread_name}')
                    changed = True
                else:
                    SmartThread._pair_array[
                        pair_key].status_blocks[
                        thread_name].del_deferred = True
            # remove _connection_pair if both names are gone
            if not SmartThread._pair_array[
                    pair_key].status_blocks:
                connection_array_del_list.append(pair_key)

        for pair_key in connection_array_del_list:
            del SmartThread._pair_array[pair_key]
            self.logger.debug(
                f'{current_thread_name} removed _pair_array entry'
                f' for pair_key = {pair_key}')
            changed = True

        if changed:
            SmartThread._pair_array_last_update = datetime.utcnow()
            print_time = (SmartThread._pair_array_last_update
                          .strftime("%H:%M:%S.%f"))
            self.logger.debug(
                f'{current_thread_name} updated _pair_array'
                f' at UTC {print_time}')

    ####################################################################
    # send_msg
    ####################################################################
    def send_msg(self,
                 targets: Union[str, set[str]],
                 msg: Any,
                 log_msg: Optional[str] = None,
                 timeout: OptIntFloat = None) -> None:
        """Send a msg.

        Args:
            msg: the msg to be sent
            targets: names to send the message to
            log_msg: log message to issue
            timeout: number of seconds to wait for full queue to get
                       free slot

        Raises:
            SmartThreadRemoteThreadNotAlive: send_msg detected remote
                thread is not alive.
            SmartThreadRequestTimedOut: send_msg method unable to send
                the message within the allotted time, most likely
                because the remote receive queue is full of the
                maximum number of messages.

        :Example: instantiate a SmartThread and send a message

        >>> import scottbrian_utils.smart_thread as st
        >>> import threading
        >>> def f1() -> None:
        ...     print('f1 beta entered')
        ...     msg = beta_smart_thread.recv_msg(remote='alpha')
        ...     if msg == 'hello beta thread':
        ...         beta_smart_thread.send_msg(targets='alpha',
        ...                                    msg='hi alpha')
        ...     print('f1 beta exiting')
        >>> print('mainline alpha entered')
        >>> alpha_smart_thread = SmartThread(name='alpha')
        >>> beta_smart_thread = SmartThread(name='alpha', target=f1)
        >>> beta_smart_thread.smart_start()
        >>> alpha_smart_thread.send_msg('hello beta thread')
        >>> alpha_smart_thread.smart_join(targets='beta')
        >>> print(alpha_smart_thread.recv_msg(remote='beta'))
        >>> print('mainline alpha exiting')
        mainline alpha entered
        f1 beta entered
        f1 beta exiting
        hi alpha
        mainline alpha exiting

        """
        # get RequestBlock with targets in a set and a timer object
        sb = self._common_setup(remotes=targets, timeout=timeout)

        if log_msg and self.debug_logging_enabled:
            exit_log_msg = self._issue_entry_log_msg(
                prefix=f'{self.name} -> {targets}.',
                log_msg=log_msg)
        else:
            exit_log_msg = None

        work_remotes = sb.remotes.copy()
        self.remotes_unregistered = set()
        self.remotes_full_send_q = set()

        while work_remotes:
            for remote in work_remotes:
                pair_key = self._get_pair_key(self.name, remote)
                with sel.SELockShare(SmartThread._registry_lock):
                    # If the remote is not yet ready, continue with
                    # the next remote in the list.
                    # We are OK with leaving a message in the receiver
                    # msg_q if we think there is a chance the receiver
                    # will recv_msg to get it. But, if the receiver is
                    # stopped and is on its way out, its msg_q will be
                    # deleted and the message will be lost. So we will
                    # check for this and continue to wait in hopes that
                    # the thread will be resurrected.
                    if (remote not in SmartThread._registry
                            or ((not SmartThread._registry[
                                remote].thread.is_alive())
                                and (SmartThread._registry[remote].status
                                & (ThreadStatus.Alive
                                   | ThreadStatus.Stopped)))):
                        self.remotes_unregistered |= {remote}
                        continue

                    # If here, remote is in registry and is alive or
                    # will hopefully soon be alive.
                    # This also means we have an entry for the remote in
                    # the status_blocks in the connection array
                    try:
                        # place message on remote q
                        SmartThread._pair_array[
                            pair_key].status_blocks[
                            remote].msg_q.put(msg, timeout=0.01)
                        self.logger.info(
                            f'{self.name} sent message to {remote}')
                        # start while loop again with one less remote
                        work_remotes.remove(remote)
                        # we need to remove the remote from the unreg
                        # or fullq sets since the send now succeeded
                        if remote in self.remotes_unregistered:
                            self.remotes_unregistered -= {remote}
                        if remote in self.remotes_full_send_q:
                            self.remotes_full_send_q -= {remote}
                        break
                    except queue.Full:
                        # If the remote msg queue is full, move on to
                        # the next remote (if one). We will come back
                        # to the full remote later and hope that it
                        # reads its messages and frees up space on its
                        # queue before we time out.
                        self.remotes_full_send_q |= {remote}

            # we might have timed out, maybe trying to get the lock,
            # but if work_remotes is now empty then skip the timeout
            # error since the messages were sent
            if work_remotes and sb.timer.is_expired():
                unreg_timeout_msg = ''
                if self.remotes_unregistered:
                    unreg_timeout_msg = (
                        'Remotes unregistered: '
                        f'{sorted(self.remotes_unregistered)}. ')
                fullq_timeout_msg = ''
                if self.remotes_full_send_q:
                    fullq_timeout_msg = (
                        'Remotes with full send queue: '
                        f'{sorted(self.remotes_full_send_q)}.')
                self.logger.debug(f'{self.name} timeout of a send_msg(). '
                                  f'Targets: {sorted(sb.remotes)}. '
                                  f'{unreg_timeout_msg}'
                                  f'{fullq_timeout_msg}')

                self.logger.error('Raise SmartThreadRequestTimedOut')
                raise SmartThreadRequestTimedOut(
                    f'{self.name} send_msg method unable to send '
                    'the message within the allotted time. ')

            time.sleep(0.1)

        # if caller specified a log message to issue
        if exit_log_msg:
            self.logger.debug(exit_log_msg)

    ####################################################################
    # recv_msg
    ####################################################################
    def recv_msg(self,
                 remote: str,
                 log_msg: Optional[str] = None,
                 timeout: OptIntFloat = None) -> Any:
        """Receive a msg.

        Args:
            remote: thread we expect to send us a message
            log_msg: log message to issue
            timeout: number of seconds to wait for message

        Returns:
            message unless timeout occurs

        Raises:
            SmartThreadRequestTimedOut: recv_msg processing timed out
                waiting for a message to arrive.
            SmartThreadRemoteThreadNotAlive: send_msg detected remote
                thread is not alive.

        """
        # call _common_setup to get timer and verify current thread, but
        # we will use remote directly since _common_setup
        # inconveniently returns remote in a list
        sb = self._common_setup(remotes=remote, timeout=timeout)
        if log_msg and self.debug_logging_enabled:
            exit_log_msg = self._issue_entry_log_msg(
                prefix=f'{self.name} <- {remote}.',
                log_msg=log_msg)
        else:
            exit_log_msg = None
        pair_key = self._get_pair_key(self.name, remote)
        do_refresh = False
        while True:
            with sel.SELockShare(SmartThread._registry_lock):
                # We don't check to ensure remote is alive since it may
                # have sent us a message and then became not alive. So,
                # we try to get the message first, and if it's not there
                # we will check to see whether the remote is alive.

                # We do, however, need to check to make sure we have a
                # an entry in the connection_pair array. If the remote
                # has not yet started, there will not yet be an entry.
                # In that case, we need to give more timee to allow the
                # remote to get started.
                if pair_key in SmartThread._pair_array:
                    try:
                        # recv message from remote
                        ret_msg = SmartThread._pair_array[
                            pair_key].status_blocks[
                            self.name].msg_q.get(timeout=0.01)
                        self.logger.info(
                            f'{self.name} received msg from {remote}')
                        # if we had wanted to delete an entry in the
                        # pair array for this thread because the other
                        # thread exited, but we could not because this
                        # thread had a pending msg to recv, then we
                        # deferred the delete. If the msg_q for this
                        # thread is now empty as a result of this recv,
                        # we can go ahead and delete the pair, so
                        # set the flag to do a refresh (we can't do the
                        # refresh here because we need to hold the lock
                        # exclusive - see code below where we do the
                        # refresh)
                        if (SmartThread._pair_array[
                                pair_key].status_blocks[
                                self.name].del_deferred
                                and SmartThread._pair_array[
                                pair_key].status_blocks[
                                self.name].msg_q.empty()):
                            do_refresh = True
                        break
                    except queue.Empty:
                        # The msg queue was just now empty. The fact
                        # that the pair_key was valid implies the remote
                        # was registered at one time. If the remote is
                        # no longer in the status_blocks dict, then it
                        # became not alive and was removed from the
                        # registry. (No need to check the msg queue
                        # again - we are locked, meaning the remote was
                        # already gone - it could not have just now
                        # send us the msg and then get removed from the
                        # status_blocks without having obtained the lock
                        # exclusive.
                        # @sbt WAIT - this can't really happen. If the
                        # pair_key is valid, then the remote must be
                        # there unless it left us a msg and exiting,
                        # in which case we should have just read that
                        # msg. If the remote left without leaving us a
                        # msg, then the pair_key would not be valid.
                        # so, I don't think we can ever see this case
                        # where the remote is gone on a queue.empty
                        # condition.
                        if remote not in SmartThread._pair_array[
                                pair_key].status_blocks:
                            raise SmartThreadRemoteThreadNotAlive(
                                f'{self.name} send_msg detected {remote} '
                                'thread is not alive.')

            if sb.timer.is_expired():
                self.logger.error(
                    f'{self.name} raising SmartThreadRequestTimedOut '
                    f'waiting for {remote}')
                raise SmartThreadRequestTimedOut(
                    f'recv_msg {self.name} timed out waiting for message '
                    f'from {remote}.')

            time.sleep(0.1)

        if do_refresh:
            with sel.SELockExcl(SmartThread._registry_lock):
                self._refresh_pair_array()

        # if caller specified a log message to issue
        if exit_log_msg:
            self.logger.debug(exit_log_msg)

        return ret_msg

    ###########################################################################
    # send_recv
    ###########################################################################
    def send_recv(self,
                  msg: Any,
                  remote: str,
                  log_msg: Optional[str] = None,
                  timeout: OptIntFloat = None) -> Any:
        """Send a message and wait for reply.

        Args:
            msg: the msg to be sent
            remote: name of thread to send message to
            log_msg: log message to write to the log
            timeout: Number of seconds to wait for reply

        Returns:
              message unless send q is full or timeout occurs during
                recv

        :Example: instantiate a SmartThread and send a message

        >>> import scottbrian_utils.smart_thread as st
        >>> import threading
        >>> def f1(smart_thread: SmartThread) -> None:
        ...     msg = smart_thread.recv_msg()
        ...     if msg == 'hello thread':
        ...         smart_thread.send_msg('hi')
        >>> a_smart_thread = SmartThread()
        >>> thread = threading.Thread(target=f1, args=(a_smart_thread,))
        >>> thread.smart_start()
        >>> a_smart_thread.send_msg('hello thread')
        >>> print(a_smart_thread.recv_msg())
        hi

        >>> thread.smart_join()

        """
        timer = Timer(timeout=timeout,
                      default_timeout=self.default_timeout)

        self.send_msg(msg, targets={remote}, log_msg=log_msg,
                      timeout=timer.timeout)

        return self.recv_msg(remote=remote, log_msg=log_msg,
                             timeout=timer.timeout)

    ####################################################################
    # msg_waiting
    ####################################################################
    def msg_waiting(self) -> Union[str, None]:
        """Determine whether a message is waiting, ready to be received.

        Returns:
            Name of first remote we find whose message is waiting for us
            to pick up, or None otherwise

        :Example: instantiate a SmartThread and set the id to 5

        >>> import scottbrian_utils.smart_thread as st
        >>> class SmartThreadApp(threading.Thread):
        ...     def __init__(self,
        ...                  smart_thread: SmartThread,
        ...                  event: threading.Event) -> None:
        ...         super().__init__()
        ...         self.smart_thread = smart_thread
        ...         self.event = event
        ...         self.smart_thread.set_child_thread_id()
        ...     def run(self) -> None:
        ...         self.smart_thread.send_msg('goodbye')
        ...         self.event.set()
        >>> smart_thread = SmartThread()
        >>> event = threading.Event()
        >>> smart_thread_app = SmartThreadApp(smart_thread, event)
        >>> print(smart_thread.msg_waiting())
        False

        >>> smart_thread_app.smart_start()
        >>> event.wait()
        >>> print(smart_thread.msg_waiting())
        True

        >>> print(smart_thread.recv_msg())
        goodbye

        """
        with sel.SELockShare(SmartThread._registry_lock):
            for pair_key in SmartThread._pair_array:
                if pair_key[0] == self.name:
                    remote = pair_key[1]
                elif pair_key[1] == self.name:
                    remote = pair_key[0]
                else:
                    continue  # this pair is not for us
                if not SmartThread._pair_array[
                        pair_key].status_blocks[
                        self.name].msg_q.empty():
                    return remote

        return None  # nothing found

    ####################################################################
    # resume
    ####################################################################
    def smart_resume(self, *,
                     targets: Union[str, set[str]],
                     log_msg: Optional[str] = None,
                     timeout: OptIntFloat = None,
                     code: Optional[Any] = None,
                     raise_not_alive: bool = True) -> None:
        """Resume a waiting or soon to be waiting thread.

        Args:
            targets: names of threads that are to be resumed
            log_msg: log msg to log
            timeout: number of seconds to allow for ``resume()`` to complete
            code: code that waiter can retrieve with ``get_code()``
            raise_not_alive: If True, raise an error if any of the
                target threads have ended. If False, continue to wait
                for the target thread to become alive if not already
                alive. In either case, a timeout will be recognized if
                specified and the time expires before a thread is
                recognized as having ended.

        Raises:
            SmartThreadRemoteThreadNotAlive: resume() detected remote
                thread is not alive.
            SmartThreadRequestTimedOut: timed out waiting for targets.

        Notes:
            1) A ``resume()`` request can be done on an event that is not yet
               being waited upon. This is referred as a **pre-resume**. The
               remote thread doing a ``wait()`` request on a **pre-resume**
               event will get back control immediately.
            2) If the ``resume()`` request sees that the event has already
               been resumed, it will loop and wait for the event to be cleared
               under the assumption that the event was previously
               **pre-resumed** and a wait is imminent. The ``wait()`` will
               clear the event and the ``resume()`` request will simply resume
               it again as a **pre-resume**.
            3) If one thread makes a ``resume()`` request and the other thread
               becomes not alive, the ``resume()`` request raises a
               **SmartThreadRemoteThreadNotAlive** error, but only when
               raise_not_alive is True.
            4) The reason for allowing multiple targets is in support of
               a sync request among many threads. When one can also
               resume many non-sync waiters at once, it does not seem to
               be useful at this time.

        :Example: instantiate SmartThread and ``resume()`` event that function
                    waits on

        >>> import scottbrian_paratools.smart_event as st
        >>> def f1() -> None:
        ...     print('f1 beta entered')
        ...     beta_smart_thread.wait()
        ...     print('f1 beta exiting')

        >>> alpha_smart_thread = SmartThread(name='alpha')
        >>> beta_smart_thread = SmartThread(name='beta', target=f1)
        >>> alpha_smart_thread.resume()
        >>> beta_smart_thread.smart_join()

        """
        # get RequestBlock with targets in a set and a timer object
        if self.sync_request:
            self.req_name = 'smart_sync'
            sb = self.setup_block
        else:
            self.req_name = 'smart_resume'
            sb = self._common_setup(remotes=targets, timeout=timeout)

        if log_msg and self.debug_logging_enabled:
            code_msg = f' with code: {code}' if code else ''
            comma_msg = ',' if code and timeout else ''
            timeout_msg = f' with {timeout=}' if timeout else ''
            exit_log_msg = self._issue_entry_log_msg(
                prefix=f'{self.name} to resume targets '
                       f'{sorted(sb.remotes)}'
                       f'{code_msg}{comma_msg}{timeout_msg}.',
                log_msg=log_msg)
        else:
            exit_log_msg = None

        ################################################################
        # Cases where we loop until remote is ready:
        # 1) Remote waiting and event already resumed. This is a case
        #    where the remote was previously resumed and has not yet
        #    been given control to exit the wait. If and when that
        #    happens, this resume will complete as a pre-resume.
        # 2) Remote waiting and deadlock. The remote was flagged as
        #    being in a deadlock and has not been given control to
        #    raise the SmartThreadWaitDeadlockDetected error. The remote
        #    could recover, in which case this resume will complete,
        #    or the thread could become inactive, in which case
        #    resume will see that and raise the
        #    SmartThreadRemoteThreadNotAlive error.
        # 3) Remote not waiting and event resumed. This case
        #    indicates that a resume was previously done ahead of the
        #    wait as a pre-resume. In that case an eventual wait is
        #    expected to be requested by the remote thread to clear
        #    the flag at which time this resume will succeed in doing a
        #    pre-resume.
        ################################################################

        ################################################################
        # Cases where we do the resume:
        # 1) Remote is waiting, event is not resumed, and neither
        #    deadlock nor conflict flags are True. This is the most
        #    expected case in a normally running system where the
        #    remote put something in action and is now waiting on a
        #    response (the resume) that the action is complete.
        # 2) Remote is not waiting, not sync_wait, and event not
        #    resumed. This is a case where we will do a pre-resume and
        #    the remote is expected to do the wait momentarily.
        # 3) Remote is not waiting, but is sync waiting, and event not
        #    resumed. This case is identical to case 2 from a resume
        #    perspective since the sync_wait does not interfere with
        #    the event that the resume operates on. So, we will do
        #    a pre-resume and the expectation in that this
        #    thread will then complete the sync with the remote
        #    who will next do a wait against the pre-resume. The
        #    vertical time line for both sides could be represented as
        #    such:
        #
        #        Current Thread                   Remote Thread
        #                                           sync
        #              resume
        #              sync
        #                                           wait
        ###############################################################

        self.request_timeout_names = set()

        work_remotes = sb.remotes.copy()

        while work_remotes:
            num_start_loop_work_remotes = len(work_remotes)
            for remote in work_remotes:
                pair_key = self._get_pair_key(self.name, remote)
                with sel.SELockShare(SmartThread._registry_lock):
                    # If the remote is not yet ready, continue with
                    # the next remote in the list.
                    # We are OK with leaving a message in the receiver
                    # msg_q if we think there is a chance the receiver
                    # will recv_msg to get it. But, if the receiver is
                    # stopped and is on its way out, its msg_q will be
                    # deleted and the message will be lost. So we will
                    # check for this and continue to wait in hopes that
                    # the thread will be resurrected.
                    if (remote not in SmartThread._registry
                            or self._get_status(remote)
                            == ThreadStatus.Stopped):
                        continue

                    # If here, remote is in registry and is alive or
                    # will hopefully will be soon.
                    # This also means we have an entry for the remote in
                    # the status_blocks in the connection array
                    with SmartThread._pair_array[pair_key].status_lock:
                        remote_sb = SmartThread._pair_array[
                                    pair_key].status_blocks[remote]
                        if self.sync_request:
                            # for a sync request we check to see
                            # whether a previous sync is still
                            # in progress as indicated by the
                            # sync event being set. We also need
                            # to make sure there is not a
                            # pending conflict that the remote
                            # thread needs to clear. Note that
                            # we only worry about the conflict
                            # for sync - a wait conflict does
                            # not impede us here since we are
                            # using a different event block
                            if not (remote_sb.sync_event.is_set()
                                    or (remote_sb.conflict
                                        and remote_sb.sync_wait)):
                                # wake remote thread and start
                                # the while loop again with one
                                # less remote
                                remote_sb.sync_event.set()
                                work_remotes.remove(remote)
                                break
                        else:
                            # for a wait request we check to see
                            # whether a previous wait is still
                            # in progress as indicated by the
                            # wait event being set. We also need
                            # to make sure there is not a
                            # pending conflict that the remote
                            # thread needs to clear. Note that
                            # we only worry about the conflict
                            # for wait - a sync conflict does
                            # not impede us here since we are
                            # using a different event block
                            if not (remote_sb.wait_event.is_set()
                                    or (remote_sb.conflict
                                        and remote_sb.wait_wait)):

                                # set the code, if one
                                if code:
                                    remote_sb.code = code
                                # wake remote thread and start
                                # the while loop again with one
                                # less remote
                                remote_sb.wait_event.set()
                                work_remotes.remove(remote)
                                break

            # if no progress was made
            if len(work_remotes) == num_start_loop_work_remotes:
                # make the timeout work_remotes visible to test cases
                self.request_timeout_names = work_remotes

                if raise_not_alive or sb.timer.is_expired():
                    remotes_stopped: set[str] = set()
                    with sel.SELockShare(SmartThread._registry_lock):
                        for remote in work_remotes:
                            if (self._get_status(remote)
                                    == ThreadStatus.Stopped):
                                remotes_stopped |= {remote}

                    # If an error should be raised for stopped threads
                    if raise_not_alive and remotes_stopped:
                        error_msg = (
                            f'{self.name} raising '
                            'SmartThreadRemoteThreadNotAlive. '
                            f'While processing a {self.req_name}(), '
                            f'{self.name} detected that the following '
                            f'threads are stopped: {sorted(remotes_stopped)}.')
                        self.logger.error(error_msg)
                        raise SmartThreadRemoteThreadNotAlive(error_msg)

                    # Note that the timer will never be expired if timeout
                    # was not specified either explicitly on the smart_wait
                    # call or via a default timeout established when this
                    # SmartThread was instantiated.
                    if sb.timer.is_expired():
                        if remotes_stopped:
                            stopped_msg = (f' Stopped threads: '
                                           f'{sorted(remotes_stopped)}.')
                        else:
                            stopped_msg = ''
                        error_msg = (f'{self.name} raising '
                                     'SmartThreadRequestTimedOut. '
                                     f'{self.name} timed out on a '
                                     f'{self.req_name}() request while '
                                     'processing threads '
                                     f'{sorted(work_remotes)}.'
                                     f'{stopped_msg}')
                        self.logger.error(error_msg)
                        raise SmartThreadRequestTimedOut(error_msg)

            time.sleep(0.2)

        # if caller specified a log message to issue
        if exit_log_msg:
            self.logger.debug(exit_log_msg)

    # ####################################################################
    # # sync
    # ####################################################################
    # def smart_sync(self, *,
    #                targets: Union[str, set[str], list[str]],
    #                raise_not_alive: bool = True,
    #                log_msg: Optional[str] = None,
    #                timeout: OptIntFloat = None):
    #     """Sync up with the remote threads.
    #
    #     Each of the targets does a resume request to pre-resume the
    #     remote sync events, and then waits for each remote to resume
    #     their sync events. This ensures that each thread in the target
    #     set has reached the sync point before any thread moves forward
    #     from there.
    #
    #     Args:
    #         targets: remote threads we will sync with
    #         raise_not_alive: specifies whther to raise a not alive error
    #             when any of the targets are stopped
    #         log_msg: log msg for the log
    #         timeout: number of seconds to allow for sync to happen
    #
    #     Notes:
    #         1) If one thread makes a ``sync()`` request without
    #            **timeout** specified, and the other thread makes a
    #            ``wait()`` request to an event that was not
    #            **pre-resumed**, also without **timeout** specified,
    #            then both threads will recognize and raise a
    #            **SmartThreadConflictDeadlockDetected** error. This is
    #            needed since neither the ``sync()`` request nor the
    #            ``wait()`` request has any chance of completing. The
    #            ``sync()`` request is waiting for a matching ``sync()``
    #            request and the ``wait()`` request is waiting for a
    #            matching ``resume()`` request.
    #
    #     :Example: sync two threads
    #
    #     >>> import scottbrian_paratools.smart_event as st
    #     >>> def f1() -> None:
    #     ...     print('f2 beta entered')
    #     ...     beta_smart_thread = SmartThread(name='beta')
    #     ...     beta_smart_thread.sync(targets='alpha')
    #     ...     print('f2 beta exiting')
    #
    #     >>> print('mainline alpha entered')
    #     >>> alpha_smart_thread  = SmartThread(name='alpha')
    #     >>> beta_thread = threading.Thread(target=f1)
    #     >>> beta_thread.start()
    #     >>> alpha_smart_thread.sync(targets='beta')
    #     >>> alpha_smart_thread.join(targets='beta')
    #     >>> print('mainline alpha exiting')
    #     mainline alpha entered
    #     f2 beta entered
    #     f2 beta exiting
    #     mainline alpha exiting
    #
    #     """
    #     # get RequestBlock with targets in a set and a timer object
    #     self.setup_block = self._common_setup(targets=targets,
    #                                           timeout=timeout)
    #
    #     if log_msg and self.debug_logging_enabled:
    #         timeout_msg = f' with {timeout=}' if timeout else ''
    #         exit_log_msg = self._issue_entry_log_msg(
    #             prefix=f'{self.name} to sync with '
    #                    f'{self.setup_block.targets}{timeout_msg}.',
    #             log_msg=log_msg)
    #     else:
    #         exit_log_msg = None
    #
    #     self.sync_request = True
    #
    #     # a sync_request passes the targets and timeout via
    #     # self.setup_block to resume and wait
    #
    #     self.smart_resume(targets='',
    #                       raise_not_alive=raise_not_alive)
    #
    #     self.smart_wait(raise_not_alive=raise_not_alive)
    #
    #     self.sync_request = False
    #     if exit_log_msg:
    #         self.logger.debug(exit_log_msg)

    ####################################################################
    # smart_sync
    ####################################################################
    # def smart_sync(self, *,
    #                targets: Union[str, set[str], list[str]],
    #                raise_not_alive: bool = True,
    #                log_msg: Optional[str] = None,
    #                timeout: OptIntFloat = None):
    #     """Sync up with the remote threads.
    #
    #     Each of the targets does a resume request to pre-resume the
    #     remote sync events, and then waits for each remote to resume
    #     their sync events. This ensures that each thread in the target
    #     set has reached the sync point before any thread moves forward
    #     from there.
    #
    #     Args:
    #      targets: remote threads we will sync with
    #      raise_not_alive: specifies whther to raise a not alive error
    #          when any of the targets are stopped
    #      log_msg: log msg for the log
    #      timeout: number of seconds to allow for sync to happen
    #
    #     Notes:
    #      1) If one thread makes a ``sync()`` request without
    #         **timeout** specified, and the other thread makes a
    #         ``wait()`` request to an event that was not
    #         **pre-resumed**, also without **timeout** specified,
    #         then both threads will recognize and raise a
    #         **SmartThreadConflictDeadlockDetected** error. This is
    #         needed since neither the ``sync()`` request nor the
    #         ``wait()`` request has any chance of completing. The
    #         ``sync()`` request is waiting for a matching ``sync()``
    #         request and the ``wait()`` request is waiting for a
    #         matching ``resume()`` request.
    #
    #     :Example: sync two threads
    #
    #     >>> import scottbrian_paratools.smart_event as st
    #     >>> def f1() -> None:
    #     ...     print('f2 beta entered')
    #     ...     beta_smart_thread = SmartThread(name='beta')
    #     ...     beta_smart_thread.sync(targets='alpha')
    #     ...     print('f2 beta exiting')
    #
    #     >>> print('mainline alpha entered')
    #     >>> alpha_smart_thread  = SmartThread(name='alpha')
    #     >>> beta_thread = threading.Thread(target=f1)
    #     >>> beta_thread.smart_start()
    #     >>> alpha_smart_thread.sync(targets='beta')
    #     >>> alpha_smart_thread.smart_join(targets='beta')
    #     >>> print('mainline alpha exiting')
    #     mainline alpha entered
    #     f2 beta entered
    #     f2 beta exiting
    #     mainline alpha exiting
    #
    #     """
    #     if not targets:
    #         raise SmartThreadInvalidInput(f'{self.name} smart_sync request '
    #                                       'with no targets specified.')
    #     # get RequestBlock with targets in a set and a timer object
    #     self.setup_block = self._common_setup(targets=targets,
    #                                           timeout=timeout,
    #                                           raise_not_alive=raise_not_alive)
    #     if self.setup_block.timer.remaining_time():
    #         timeout_specified = True
    #     else:
    #         timeout_specified = False
    #
    #     self.req_name = 'smart_sync'
    #
    #     if log_msg and self.debug_logging_enabled:
    #         timeout_msg = f' with {timeout=}' if timeout_specified else ''
    #         exit_log_msg = self._issue_entry_log_msg(
    #             prefix=f'{self.name} to sync with '
    #                    f'{self.setup_block.targets}{timeout_msg}.',
    #             log_msg=log_msg)
    #     else:
    #         exit_log_msg = None
    #
    #     self.request_timeout_names = set()
    #
    #     do_refresh = False
    #
    #     remotes_stopped: set[str] = set()
    #     conflict_remotes: set[str] = set()
    #     deadlock_remotes: set[str] = set()
    #
    #     work_targets: set[str] = self.setup_block.targets.copy()
    #     threshold_completion_num = 0
    #     while len(work_targets) > threshold_completion_num:
    #         num_start_loop_work_targets = len(work_targets)
    #         for remote in work_targets:
    #             pair_key = self._get_pair_key(self.name, remote)
    #             with sel.SELockShare(SmartThread._registry_lock):
    #                 if pair_key in SmartThread._pair_array:
    #                     # having a pair_key in the array implies our entry
    #                     # exists - set local_sb for easy references
    #                     local_sb = SmartThread._pair_array[
    #                         pair_key].status_blocks[self.name]
    #
    #                     # lock needed to coordinate conflict/deadlock
    #                     with SmartThread._pair_array[pair_key].status_lock:
    #                         if not local_sb.sync_wait:
    #                             if (self._get_status(remote)
    #                                     == ThreadStatus.Stopped):
    #                                 remotes_stopped |= {remote}
    #                                 continue
    #                             if remote in SmartThread._pair_array[
    #                                     pair_key].status_blocks:
    #                                 remote_sb = SmartThread._pair_array[
    #                                     pair_key].status_blocks[remote]
    #                                 # for a sync request we check to see
    #                                 # whether a previous sync is still
    #                                 # in progress as indicated by the
    #                                 # sync event being set. We also need
    #                                 # to make sure there is not a
    #                                 # pending conflict that the remote
    #                                 # thread needs to clear. Note that
    #                                 # we only worry about the conflict
    #                                 # for sync - a wait conflict does
    #                                 # not impede us here since we are
    #                                 # using a different event block
    #                                 if not (remote_sb.sync_event.is_set()
    #                                         or (remote_sb.conflict
    #                                             and remote_sb.sync_wait)):
    #                                     # sync resume remote thread
    #                                     remote_sb.sync_event.set()
    #                                     local_sb.sync_wait = True
    #
    #                         if local_sb.sync_wait:
    #                             if local_sb.sync_event.is_set():
    #                                 local_sb.sync_wait = False
    #                                 local_sb.wait_timeout_specified = False
    #
    #                                 # be ready for next sync wait
    #                                 local_sb.sync_event.clear()
    #                                 if (local_sb.del_deferred and
    #                                         not local_sb.wait_event.is_set()):
    #                                     do_refresh = True
    #                                 self.logger.info(
    #                                     f'{self.name} smart_sync resumed by '
    #                                     f'{remote}')
    #                                 work_targets.remove(remote)
    #                                 # exit, we are done with this remote
    #                                 break
    #
    #                             local_sb.wait_timeout_specified = timeout_specified
    #                             # Check for error conditions first before
    #                             # checking whether the remote is alive. If the
    #                             # remote detects a deadlock or conflict issue,
    #                             # it will set the current sides bit and then
    #                             # raise an error and will likely be gone when we
    #                             # check. We want to raise the same error on
    #                             # this side.
    #                             #
    #                             # self.deadlock is set only by the remote. So,
    #                             # if self.deadlock is True, then remote has
    #                             # already detected the deadlock, set our flag,
    #                             # raised the deadlock on its side, and is now
    #                             # possibly ended or recovered and in a new wait.
    #                             # If self.deadlock is False, and remote is
    #                             # waiting and is not resumed then it will not be
    #                             # getting resumed by us since we are also
    #                             # waiting. So, we set self.remote.deadlock to
    #                             # tell it, and then we raise the error on our
    #                             # side. But, we don't do this if the
    #                             # self.remote.deadlock is already on as that
    #                             # suggests that we already told remote and
    #                             # raised the error, which implies that we are in
    #                             # a new wait and the remote has not yet woken up
    #                             # to deal with the earlier deadlock. We can
    #                             # simply ignore it for now.
    #                             if remote in SmartThread._pair_array[
    #                                     pair_key].status_blocks:
    #                                 remote_sb = SmartThread._pair_array[
    #                                     pair_key].status_blocks[remote]
    #                                 if not (local_sb.wait_timeout_specified
    #                                         or remote_sb.wait_timeout_specified
    #                                         or local_sb.deadlock
    #                                         or local_sb.conflict):
    #
    #                                     if (remote_sb.wait_wait
    #                                             and not
    #                                             (remote_sb.wait_event.is_set()
    #                                                 or remote_sb.deadlock
    #                                                 or remote_sb.conflict)):
    #                                         remote_sb.conflict = True
    #                                         local_sb.conflict = True
    #                                         self.logger.debug(
    #                                             f'TestDebug {self.name} sync '
    #                                             f'set remote and local '
    #                                             f'conflict flags {remote=}')
    #
    #                             if local_sb.conflict:
    #                                 conflict_remotes |= {remote}
    #                                 self.logger.debug(
    #                                     f'TestDebug {self.name} sync set '
    #                                     f'{conflict_remotes=}')
    #
    #         if do_refresh:
    #             with sel.SELockExcl(SmartThread._registry_lock):
    #                 self._refresh_pair_array()
    #             do_refresh = False
    #
    #         # if no progress was made
    #         if len(work_targets) == num_start_loop_work_targets:
    #             # make the timeout work_targets visible to test cases
    #             self.request_timeout_names = work_targets
    #
    #             if ((raise_not_alive and remotes_stopped)
    #                     or conflict_remotes
    #                     or deadlock_remotes
    #                     or self.setup_block.timer.is_expired()):
    #
    #                 # cleanup before doing the error
    #                 with sel.SELockShare(SmartThread._registry_lock):
    #                     self._sync_wait_error_cleanup(remotes=work_targets,
    #                                                   backout_request='sync')
    #
    #                 targets_msg = (f'while processing a {self.req_name} '
    #                                f'request with remotes '
    #                                f'{sorted(self.setup_block.targets)}.')
    #
    #                 pending_msg = (f' Remotes that are pending: '
    #                                f'{sorted(work_targets)}.')
    #
    #                 if remotes_stopped:
    #                     stopped_msg = (' Remotes that are stopped: '
    #                                    f'{sorted(remotes_stopped)}.')
    #                 else:
    #                     stopped_msg = ''
    #
    #                 if conflict_remotes:
    #                     if self.req_name == 'smart_sync':
    #                         remote_request = 'smart_wait'
    #                     else:
    #                         remote_request = 'smart_sync'
    #                     conflict_msg = (f' Remotes doing a {remote_request} '
    #                                     'request that are deadlocked: '
    #                                     f'{sorted(conflict_remotes)}.')
    #                 else:
    #                     conflict_msg = ''
    #
    #                 if deadlock_remotes:
    #                     deadlock_msg = (f' Remotes doing a smart_wait '
    #                                     'request that are deadlocked: '
    #                                     f'{sorted(deadlock_remotes)}.')
    #                 else:
    #                     deadlock_msg = ''
    #
    #                 msg_suite = (f'{targets_msg}{pending_msg}{stopped_msg}'
    #                              f'{conflict_msg}{deadlock_msg}')
    #
    #                 # If an error should be raised for stopped threads
    #                 if raise_not_alive and remotes_stopped:
    #                     error_msg = (
    #                         f'{self.name} raising '
    #                         f'SmartThreadRemoteThreadNotAlive {msg_suite}')
    #                     self.logger.error(error_msg)
    #                     raise SmartThreadRemoteThreadNotAlive(error_msg)
    #
    #                 if conflict_remotes:
    #                     error_msg = (
    #                         f'{self.name} raising '
    #                         f'SmartThreadConflictDeadlockDetected {msg_suite}')
    #                     self.logger.error(error_msg)
    #                     raise SmartThreadConflictDeadlockDetected(error_msg)
    #
    #                 if deadlock_remotes:
    #                     error_msg = (
    #                         f'{self.name} raising '
    #                         f'SmartThreadWaitDeadlockDetected {msg_suite}')
    #                     self.logger.error(error_msg)
    #                     raise SmartThreadWaitDeadlockDetected(error_msg)
    #
    #                 # Note that the timer will never be expired if timeout
    #                 # was not specified either explicitly on the smart_wait
    #                 # call or via a default timeout established when this
    #                 # SmartThread was instantiated.
    #                 if self.setup_block.timer.is_expired():
    #                     error_msg = (
    #                         f'{self.name} raising '
    #                         f'SmartThreadRequestTimedOut {msg_suite}')
    #                     self.logger.error(error_msg)
    #                     raise SmartThreadRequestTimedOut(error_msg)
    #
    #         time.sleep(0.2)
    #
    #     # if caller specified a log message to issue
    #     if exit_log_msg:
    #         self.logger.debug(exit_log_msg)

    ####################################################################
    # smart_sync
    ####################################################################
    def smart_sync(self, *,
                   targets: Union[str, set[str], list[str]],
                   raise_not_alive: bool = True,
                   log_msg: Optional[str] = None,
                   timeout: OptIntFloat = None):
        """Sync up with the remote threads.

        Each of the targets does a resume request to pre-resume the
        remote sync events, and then waits for each remote to resume
        their sync events. This ensures that each thread in the target
        set has reached the sync point before any thread moves forward
        from there.

        Args:
         targets: remote threads we will sync with
         raise_not_alive: specifies whther to raise a not alive error
             when any of the targets are stopped
         log_msg: log msg for the log
         timeout: number of seconds to allow for sync to happen

        Notes:
         1) If one thread makes a ``sync()`` request without
            **timeout** specified, and the other thread makes a
            ``wait()`` request to an event that was not
            **pre-resumed**, also without **timeout** specified,
            then both threads will recognize and raise a
            **SmartThreadConflictDeadlockDetected** error. This is
            needed since neither the ``sync()`` request nor the
            ``wait()`` request has any chance of completing. The
            ``sync()`` request is waiting for a matching ``sync()``
            request and the ``wait()`` request is waiting for a
            matching ``resume()`` request.

        :Example: sync two threads

        >>> import scottbrian_paratools.smart_event as st
        >>> def f1() -> None:
        ...     print('f2 beta entered')
        ...     beta_smart_thread = SmartThread(name='beta')
        ...     beta_smart_thread.sync(targets='alpha')
        ...     print('f2 beta exiting')

        >>> print('mainline alpha entered')
        >>> alpha_smart_thread  = SmartThread(name='alpha')
        >>> beta_thread = threading.Thread(target=f1)
        >>> beta_thread.smart_start()
        >>> alpha_smart_thread.sync(targets='beta')
        >>> alpha_smart_thread.smart_join(targets='beta')
        >>> print('mainline alpha exiting')
        mainline alpha entered
        f2 beta entered
        f2 beta exiting
        mainline alpha exiting

        """
        if not targets:
            raise SmartThreadInvalidInput(f'{self.name} smart_sync request '
                                          'with no targets specified.')
        # get RequestBlock with targets in a set and a timer object
        request_block = self._request_setup(
            request_name='smart_sync',
            remotes=targets,
            raise_not_alive=raise_not_alive,
            timeout=timeout)

        if setup_block.timer.remaining_time():
            timeout_specified = True
        else:
            timeout_specified = False

        if self.debug_logging_enabled:
            exit_log_msg = self._issue_entry_log_msg(
                request_block=request_block,
                log_msg=log_msg)
        else:
            exit_log_msg = None

        self._request_loop(req_name='smart_sync',
                           setup_block=setup_block,
                           threshold_completion_num=0)

        self.request_timeout_names = set()

        do_refresh = False

        remotes_stopped: set[str] = set()
        conflict_remotes: set[str] = set()
        deadlock_remotes: set[str] = set()

        work_remotes: set[str] = self.setup_block.remotes.copy()
        threshold_completion_num = 0
        while len(work_remotes) > threshold_completion_num:
            num_start_loop_work_remotes = len(work_remotes)
            for remote in work_remotes:
                pair_key = self._get_pair_key(self.name, remote)
                with sel.SELockShare(SmartThread._registry_lock):
                    if pair_key in SmartThread._pair_array:
                        # having a pair_key in the array implies our entry
                        # exists - set local_sb for easy references
                        local_sb = SmartThread._pair_array[
                            pair_key].status_blocks[self.name]

                        # lock needed to coordinate conflict/deadlock
                        with SmartThread._pair_array[pair_key].status_lock:
                            if not local_sb.sync_wait:
                                if (self._get_status(remote)
                                        == ThreadStatus.Stopped):
                                    remotes_stopped |= {remote}
                                    continue
                                if remote in SmartThread._pair_array[
                                        pair_key].status_blocks:
                                    remote_sb = SmartThread._pair_array[
                                        pair_key].status_blocks[remote]
                                    # for a sync request we check to see
                                    # whether a previous sync is still
                                    # in progress as indicated by the
                                    # sync event being set. We also need
                                    # to make sure there is not a
                                    # pending conflict that the remote
                                    # thread needs to clear. Note that
                                    # we only worry about the conflict
                                    # for sync - a wait conflict does
                                    # not impede us here since we are
                                    # using a different event block
                                    if not (remote_sb.sync_event.is_set()
                                            or (remote_sb.conflict
                                                and remote_sb.sync_wait)):
                                        # sync resume remote thread
                                        remote_sb.sync_event.set()
                                        local_sb.sync_wait = True

                            if local_sb.sync_wait:
                                if local_sb.sync_event.is_set():
                                    local_sb.sync_wait = False
                                    local_sb.wait_timeout_specified = False

                                    # be ready for next sync wait
                                    local_sb.sync_event.clear()
                                    if (local_sb.del_deferred and
                                            not local_sb.wait_event.is_set()):
                                        do_refresh = True
                                    self.logger.info(
                                        f'{self.name} smart_sync resumed by '
                                        f'{remote}')
                                    work_remotes.remove(remote)
                                    # exit, we are done with this remote
                                    break

                                local_sb.wait_timeout_specified = timeout_specified
                                # Check for error conditions first before
                                # checking whether the remote is alive. If the
                                # remote detects a deadlock or conflict issue,
                                # it will set the current sides bit and then
                                # raise an error and will likely be gone when we
                                # check. We want to raise the same error on
                                # this side.
                                #
                                # self.deadlock is set only by the remote. So,
                                # if self.deadlock is True, then remote has
                                # already detected the deadlock, set our flag,
                                # raised the deadlock on its side, and is now
                                # possibly ended or recovered and in a new wait.
                                # If self.deadlock is False, and remote is
                                # waiting and is not resumed then it will not be
                                # getting resumed by us since we are also
                                # waiting. So, we set self.remote.deadlock to
                                # tell it, and then we raise the error on our
                                # side. But, we don't do this if the
                                # self.remote.deadlock is already on as that
                                # suggests that we already told remote and
                                # raised the error, which implies that we are in
                                # a new wait and the remote has not yet woken up
                                # to deal with the earlier deadlock. We can
                                # simply ignore it for now.
                                if remote in SmartThread._pair_array[
                                        pair_key].status_blocks:
                                    remote_sb = SmartThread._pair_array[
                                        pair_key].status_blocks[remote]
                                    if not (local_sb.wait_timeout_specified
                                            or remote_sb.wait_timeout_specified
                                            or local_sb.deadlock
                                            or local_sb.conflict):

                                        if (remote_sb.wait_wait
                                                and not
                                                (remote_sb.wait_event.is_set()
                                                    or remote_sb.deadlock
                                                    or remote_sb.conflict)):
                                            remote_sb.conflict = True
                                            local_sb.conflict = True
                                            self.logger.debug(
                                                f'TestDebug {self.name} sync '
                                                f'set remote and local '
                                                f'conflict flags {remote=}')

                                if local_sb.conflict:
                                    conflict_remotes |= {remote}
                                    self.logger.debug(
                                        f'TestDebug {self.name} sync set '
                                        f'{conflict_remotes=}')

            if do_refresh:
                with sel.SELockExcl(SmartThread._registry_lock):
                    self._refresh_pair_array()
                do_refresh = False

            # if no progress was made
            if len(work_remotes) == num_start_loop_work_remotes:
                # make the timeout work_remotes visible to test cases
                self.request_timeout_names = work_remotes

                if ((raise_not_alive and remotes_stopped)
                        or conflict_remotes
                        or deadlock_remotes
                        or self.setup_block.timer.is_expired()):

                    # cleanup before doing the error
                    with sel.SELockShare(SmartThread._registry_lock):
                        self._sync_wait_error_cleanup(remotes=work_remotes,
                                                      backout_request='sync')

                    targets_msg = (f'while processing a {self.req_name} '
                                   f'request with remotes '
                                   f'{sorted(self.setup_block.remotes)}.')

                    pending_msg = (f' Remotes that are pending: '
                                   f'{sorted(work_remotes)}.')

                    if remotes_stopped:
                        stopped_msg = (' Remotes that are stopped: '
                                       f'{sorted(remotes_stopped)}.')
                    else:
                        stopped_msg = ''

                    if conflict_remotes:
                        if self.req_name == 'smart_sync':
                            remote_request = 'smart_wait'
                        else:
                            remote_request = 'smart_sync'
                        conflict_msg = (f' Remotes doing a {remote_request} '
                                        'request that are deadlocked: '
                                        f'{sorted(conflict_remotes)}.')
                    else:
                        conflict_msg = ''

                    if deadlock_remotes:
                        deadlock_msg = (f' Remotes doing a smart_wait '
                                        'request that are deadlocked: '
                                        f'{sorted(deadlock_remotes)}.')
                    else:
                        deadlock_msg = ''

                    msg_suite = (f'{targets_msg}{pending_msg}{stopped_msg}'
                                 f'{conflict_msg}{deadlock_msg}')

                    # If an error should be raised for stopped threads
                    if raise_not_alive and remotes_stopped:
                        error_msg = (
                            f'{self.name} raising '
                            f'SmartThreadRemoteThreadNotAlive {msg_suite}')
                        self.logger.error(error_msg)
                        raise SmartThreadRemoteThreadNotAlive(error_msg)

                    if conflict_remotes:
                        error_msg = (
                            f'{self.name} raising '
                            f'SmartThreadConflictDeadlockDetected {msg_suite}')
                        self.logger.error(error_msg)
                        raise SmartThreadConflictDeadlockDetected(error_msg)

                    if deadlock_remotes:
                        error_msg = (
                            f'{self.name} raising '
                            f'SmartThreadWaitDeadlockDetected {msg_suite}')
                        self.logger.error(error_msg)
                        raise SmartThreadWaitDeadlockDetected(error_msg)

                    # Note that the timer will never be expired if timeout
                    # was not specified either explicitly on the smart_wait
                    # call or via a default timeout established when this
                    # SmartThread was instantiated.
                    if self.setup_block.timer.is_expired():
                        error_msg = (
                            f'{self.name} raising '
                            f'SmartThreadRequestTimedOut {msg_suite}')
                        self.logger.error(error_msg)
                        raise SmartThreadRequestTimedOut(error_msg)

            time.sleep(0.2)

        # if caller specified a log message to issue
        if exit_log_msg:
            self.logger.debug(exit_log_msg)


    ####################################################################
    # _sync_wait_error_cleanup
    ####################################################################
    def _sync_wait_error_cleanup(self,
                                 remotes: set[str],
                                 backout_request: str) -> None:
        """Cleanup a failed sync request.

        Args:
            remotes: names of threads that need cleanup
            backout_request: sync or wait

        Notes:
            must be holding the registry lock at least shared
        """
        for remote in remotes:
            pair_key = self._get_pair_key(self.name, remote)
            if pair_key in SmartThread._pair_array:
                # having a pair_key in the array implies our entry
                # exists - set local_sb for easy references
                local_sb = SmartThread._pair_array[
                    pair_key].status_blocks[self.name]

                with SmartThread._pair_array[pair_key].status_lock:
                    # if we made it as far as having set the remote sync
                    # event, then we need to back that out, but only when
                    # the remote did not set out event yet
                    if backout_request == 'sync' and local_sb.sync_wait:
                        # if we are now set, then the remote did
                        # finally respond and this was a good sync,
                        # which also means the backout of the remote is
                        # no longer needed since it will have reset its
                        # sync_event when it set ours
                        local_sb.sync_wait = False
                        if local_sb.sync_event.is_set():
                            local_sb.sync_event.clear()
                        else:
                            if remote in SmartThread._pair_array[
                                    pair_key].status_blocks:
                                remote_sb = SmartThread._pair_array[
                                    pair_key].status_blocks[remote]
                                # backout the sync resume
                                remote_sb.sync_event.clear()
                    if backout_request == 'wait' and local_sb.wait_wait:
                        local_sb.wait_wait = False
                        local_sb.wait_event.clear()

                    local_sb.deadlock = False
                    local_sb.conflict = False
                    local_sb.wait_timeout_specified = False

    ####################################################################
    # wait
    ####################################################################
    def smart_wait(self, *,
                   remotes: StrListStrSetStr = None,
                   wait_for: WaitFor = WaitFor.All,
                   log_msg: Optional[str] = None,
                   timeout: OptIntFloat = None,
                   raise_not_alive: bool = True) -> None:
        """Wait on event.

        Args:
            remotes: names of threads that we expect to resume us
            wait_for: specifies whether to wait for only one remote or
                for all remotes
            log_msg: log msg to log
            timeout: number of seconds to allow for wait to be
                resumed
            raise_not_alive: If True, raise an error if the resume_name
                thread has ended. If False, continue to wait for a
                resume with the expectation that the resume_name will
                be restarted with a new thread. In either case, a
                timeout will be recognized if specified and the time
                expires before a thread is recognized as having ended.


        Raises:
            SmartThreadWaitDeadlockDetected: Two threads are
                deadlocked in a ''wait()'', each waiting on the other to
                ``resume()`` their event.
            SmartThreadConflictDeadlockDetected: A sync request was made
                by thread {self.name} but remote thread {remote}
                detected deadlock instead which indicates that the
                remote thread did not make a matching sync request.
            SmartThreadSmartWaitTimedOut: this thread timed out on a
                wait request waiting for a resume from the remote
                thread.
            SmartThreadRemoteThreadNotAlive: this thread wait detected
                the remote thread is not alive.

        Notes:
            1) If one thread makes a ``sync()`` request without
               **timeout** specified, and the other thread makes a
               ``wait()`` request to an event that was not
               **pre-resumed**, also without **timeout** specified, then
               both threads will recognize and raise a
               **SmartThreadConflictDeadlockDetected** error. This is
               needed since neither the ``sync()`` request nor the
               ``wait()`` request has any chance of completing. The
               ``sync()`` request is waiting for a matching ``sync()``
               request and the ``wait()`` request is waiting for a
               matching ``resume()`` request.
            2) If one thread makes a ``wait()`` request to an event that
               has not been **pre-resumed**, and without **timeout**
               specified, and the other thread makes a ``wait()``
               request to an event that was not **pre-resumed**, also
               without **timeout** specified, then both threads will
               recognize and raise a
               **SmartThreadWaitDeadlockDetected** error. This is needed
               since neither ``wait()`` request has any chance of
               completing as each ``wait()`` request is waiting for a
               matching ``resume()`` request.
            3) If one thread makes a ``wait()`` request and the other
               thread becomes not alive, the ``wait()`` request raises a
               **SmartThreadRemoteThreadNotAlive** error.

        :Example: ``wait()`` for function to ``resume()``

        >>> import scottbrian_paratools.smart_event as st
        >>> import threading
        >>> def f1() -> None:
        ...     beta_smart_thread = SmartThread(name='beta')
        ...     time.sleep(1)
        ...     beta_smart_thread.resume(targets='alpha')

        >>> alpha_smart_event = SmartThread(name='alpha')
        >>> f1_thread = threading.Thread(target=f1)
        >>> f1_thread.smart_start()
        >>> alpha_smart_event.wait(remote='beta')
        >>> alpha_smart_event.smart_join(targets='beta')

        """

        self.req_name = 'smart_wait'
        self.setup_block = self._common_setup(remotes=remotes, timeout=timeout)

        if wait_for == WaitFor.All:
            threshold_completion_num = 0
        else:
            threshold_completion_num = len(self.setup_block.remotes) - 1

        if self.setup_block.timer.remaining_time():
            timeout_specified = True
        else:
            timeout_specified = False

        if log_msg and self.debug_logging_enabled:
            timeout_msg = f' with {timeout=}' if timeout else ''
            exit_log_msg = self._issue_entry_log_msg(
                prefix=f'{self.name} to wait for '
                       f'{sorted(self.setup_block.remotes)}'
                       f'{timeout_msg}.',
                log_msg=log_msg)
        else:
            exit_log_msg = None

        do_refresh = False
        self.request_timeout_names = set()

        remotes_stopped: set[str] = set()
        conflict_remotes: set[str] = set()
        deadlock_remotes: set[str] = set()

        work_remotes = self.setup_block.remotes.copy()

        while len(work_remotes) > threshold_completion_num:
            num_start_loop_work_remotes = len(work_remotes)
            for remote in work_remotes:
                pair_key = self._get_pair_key(self.name, remote)

                with sel.SELockShare(SmartThread._registry_lock):
                    # The pair array will:
                    # 1) have an entry for both this thread and the remote
                    # 2) have an entry for only this thread if the remote
                    #    set the event for either wait or sync, or sent a
                    #    msg that has not yet been received, and then ended
                    # 3) neither thread if the remote has not yet registered
                    #    or has ended and did not set either event nor send
                    #    a msg that has not yet been received
                    if pair_key in SmartThread._pair_array:
                        # having a pair_key in the array implies our entry
                        # exists - set local_sb for easy references
                        local_sb = SmartThread._pair_array[
                            pair_key].status_blocks[self.name]

                        # lock needed to coordinate conflict/deadlock
                        with SmartThread._pair_array[pair_key].status_lock:

                            # We don't check to ensure remote is alive since
                            # it may have resumed us and then ended. So, we
                            # check the sync_event or wait_event first, and
                            # then we will check to see whether the remote
                            # is alive.

                            local_sb.wait_wait = True
                            if local_sb.wait_event.is_set():
                                local_sb.wait_wait = False
                                local_sb.wait_timeout_specified = False

                                # be ready for next wait
                                local_sb.wait_event.clear()
                                if (local_sb.del_deferred and
                                        not local_sb.sync_event.is_set()):
                                    do_refresh = True
                                self.logger.info(
                                    f'{self.name} smart_wait resumed by '
                                    f'{remote}')
                                work_remotes.remove(remote)
                                # exit, we are done with this remote
                                break

                            local_sb.wait_timeout_specified = timeout_specified
                            # Check for error conditions first before
                            # checking whether the remote is alive. If the
                            # remote detects a deadlock or conflict issue,
                            # it will set the current sides bit and then
                            # raise an error and will likely be gone when we
                            # check. We want to raise the same error on
                            # this side.
                            #
                            # self.deadlock is set only by the remote. So,
                            # if self.deadlock is True, then remote has
                            # already detected the deadlock, set our flag,
                            # raised the deadlock on its side, and is now
                            # possibly ended or recovered and in a new wait.
                            # If self.deadlock is False, and remote is
                            # waiting and is not resumed then it will not be
                            # getting resumed by us since we are also
                            # waiting. So, we set self.remote.deadlock to
                            # tell it, and then we raise the error on our
                            # side. But, we don't do this if the
                            # self.remote.deadlock is already on as that
                            # suggests that we already told remote and
                            # raised the error, which implies that we are in
                            # a new wait and the remote has not yet woken up
                            # to deal with the earlier deadlock. We can
                            # simply ignore it for now.
                            if remote in SmartThread._pair_array[
                                    pair_key].status_blocks:
                                remote_sb = SmartThread._pair_array[
                                    pair_key].status_blocks[remote]
                                if not (local_sb.wait_timeout_specified
                                        or remote_sb.wait_timeout_specified
                                        or local_sb.deadlock
                                        or local_sb.conflict):
                                    # the following checks apply to both
                                    # sync_wait and wait_wait
                                    if (remote_sb.sync_wait
                                            and not
                                            (remote_sb.sync_event.is_set()
                                                or remote_sb.conflict)):
                                        remote_sb.conflict = True
                                        local_sb.conflict = True
                                        self.logger.debug(
                                            f'TestDebug {self.name} wait '
                                            f'set remote and local '
                                            f'conflict flags {remote=}')
                                    elif (remote_sb.wait_wait
                                            # I think this is a bug to check
                                            # our wait_event, so I comment
                                            # it out for now and change it
                                            # to check the remote wait_event
                                            # and not
                                            # (local_sb.wait_event.is_set()
                                            and not
                                            (remote_sb.wait_event.is_set()
                                                or remote_sb.deadlock
                                                or remote_sb.conflict)):
                                        remote_sb.deadlock = True
                                        local_sb.deadlock = True
                                        self.logger.debug(
                                            f'TestDebug {self.name} wait '
                                            f'set remote and local '
                                            f'deadlock flags {remote=}')


                            if local_sb.conflict:
                                local_sb.sync_wait = False
                                local_sb.wait_wait = False
                                local_sb.conflict = False
                                local_sb.wait_timeout_specified = False
                                conflict_remotes |= {remote}
                                self.logger.debug(
                                    f'TestDebug {self.name} wait set '
                                    f'{conflict_remotes=}')

                            if local_sb.deadlock:
                                local_sb.sync_wait = False
                                local_sb.wait_wait = False
                                local_sb.deadlock = False
                                local_sb.wait_timeout_specified = False
                                deadlock_remotes |= {remote}
                                self.logger.debug(
                                    f'TestDebug {self.name} wait set '
                                    f'{deadlock_remotes=}')

            if do_refresh:
                with sel.SELockExcl(SmartThread._registry_lock):
                    self._refresh_pair_array()
                do_refresh = False

            # if no progress was made
            if len(work_remotes) == num_start_loop_work_remotes:
                # make the timeout work_remotes visible to test cases
                self.request_timeout_names = work_remotes

                if ((raise_not_alive and remotes_stopped)
                        or conflict_remotes
                        or deadlock_remotes
                        or self.setup_block.timer.is_expired()):

                    # cleanup before doing the error
                    with sel.SELockShare(SmartThread._registry_lock):
                        self._sync_wait_error_cleanup(remotes=work_remotes,
                                                      backout_request='wait')

                    targets_msg = (f'while processing a {self.req_name} '
                                   f'request with remotes '
                                   f'{sorted(self.setup_block.remotes)}.')

                    pending_msg = (f' Remotes that are pending: '
                                   f'{sorted(work_remotes)}.')

                    if remotes_stopped:
                        stopped_msg = (' Remotes that are stopped: '
                                       f'{sorted(remotes_stopped)}.')
                    else:
                        stopped_msg = ''

                    if conflict_remotes:
                        if self.req_name == 'smart_sync':
                            remote_request = 'smart_wait'
                        else:
                            remote_request = 'smart_sync'
                        conflict_msg = (f' Remotes doing a {remote_request} '
                                        'request that are deadlocked: '
                                        f'{sorted(conflict_remotes)}.')
                    else:
                        conflict_msg = ''

                    if deadlock_remotes:
                        deadlock_msg = (f' Remotes doing a smart_wait '
                                        'request that are deadlocked: '
                                        f'{sorted(deadlock_remotes)}.')
                    else:
                        deadlock_msg = ''

                    msg_suite = (f'{targets_msg}{pending_msg}{stopped_msg}'
                                 f'{conflict_msg}{deadlock_msg}')

                    # If an error should be raised for stopped threads
                    if raise_not_alive and remotes_stopped:
                        error_msg = (
                            f'{self.name} raising '
                            f'SmartThreadRemoteThreadNotAlive {msg_suite}')
                        self.logger.error(error_msg)
                        raise SmartThreadRemoteThreadNotAlive(error_msg)

                    if conflict_remotes:
                        error_msg = (
                            f'{self.name} raising '
                            f'SmartThreadConflictDeadlockDetected {msg_suite}')
                        self.logger.error(error_msg)
                        raise SmartThreadConflictDeadlockDetected(error_msg)

                    if deadlock_remotes:
                        error_msg = (
                            f'{self.name} raising '
                            f'SmartThreadWaitDeadlockDetected {msg_suite}')
                        self.logger.error(error_msg)
                        raise SmartThreadWaitDeadlockDetected(error_msg)

                    # Note that the timer will never be expired if timeout
                    # was not specified either explicitly on the smart_wait
                    # call or via a default timeout established when this
                    # SmartThread was instantiated.
                    if self.setup_block.timer.is_expired():
                        error_msg = (
                            f'{self.name} raising '
                            f'SmartThreadRequestTimedOut {msg_suite}')
                        self.logger.error(error_msg)
                        raise SmartThreadRequestTimedOut(error_msg)

            time.sleep(0.2)

        if exit_log_msg:
            self.logger.debug(exit_log_msg)

    ####################################################################
    # resume
    ####################################################################
    def _request_loop(self, *,
                      req_name: str,
                      setup_block: RequestBlock,
                      threshold_completion_num: int
                      ) -> None:
        """Main loop for each request.

        Each of the requests calls tghis method to perform the loop of
        the targets.

        Args:
            req_name: specifies the request
            setup_block: contains targets, timeout, and raise_not_alive
            threshold_conpletion_num: specifies loop ending
        """
        if setup_block.timer.remaining_time():
            timeout_specified = True
        else:
            timeout_specified = False

        self.request_timeout_names = set()

        self.do_refresh = False

        remotes_stopped: set[str] = set()
        conflict_remotes: set[str] = set()
        deadlock_remotes: set[str] = set()

        work_remotes: set[str] = setup_block.remotes.copy()

        while len(work_remotes) > threshold_completion_num:
            num_start_loop_work_remotes = len(work_remotes)
            for remote in work_remotes:
                pair_key = self._get_pair_key(self.name, remote)
                with sel.SELockShare(SmartThread._registry_lock):
                    if pair_key in SmartThread._pair_array:
                        # having a pair_key in the array implies our entry
                        # exists - set local_sb for easy references
                        local_sb = SmartThread._pair_array[
                            pair_key].status_blocks[self.name]

                        # lock needed to coordinate conflict/deadlock
                        with SmartThread._pair_array[pair_key].status_lock:

            if self.do_refresh:
                with sel.SELockExcl(SmartThread._registry_lock):
                    self._refresh_pair_array()
                self.do_refresh = False

            # if no progress was made
            if len(work_remotes) == num_start_loop_work_remotes:
                # make the timeout work_remotes visible to test cases
                self.request_timeout_names = work_remotes

                if ((setup_block.raise_not_alive and remotes_stopped)
                        or conflict_remotes
                        or deadlock_remotes
                        or setup_block.timer.is_expired()):

                    # cleanup before doing the error
                    with sel.SELockShare(SmartThread._registry_lock):
                        self._sync_wait_error_cleanup(remotes=work_remotes,
                                                      backout_request='sync')

                    targets_msg = (f'while processing a {req_name} '
                                   f'request with remotes '
                                   f'{sorted(setup_block.remotes)}.')

                    pending_msg = (f' Remotes that are pending: '
                                   f'{sorted(work_remotes)}.')

                    if remotes_stopped:
                        stopped_msg = (' Remotes that are stopped: '
                                       f'{sorted(remotes_stopped)}.')
                    else:
                        stopped_msg = ''

                    if conflict_remotes:
                        if req_name == 'smart_sync':
                            remote_request = 'smart_wait'
                        else:
                            remote_request = 'smart_sync'
                        conflict_msg = (f' Remotes doing a {remote_request} '
                                        'request that are deadlocked: '
                                        f'{sorted(conflict_remotes)}.')
                    else:
                        conflict_msg = ''

                    if deadlock_remotes:
                        deadlock_msg = (f' Remotes doing a smart_wait '
                                        'request that are deadlocked: '
                                        f'{sorted(deadlock_remotes)}.')
                    else:
                        deadlock_msg = ''

                    msg_suite = (f'{targets_msg}{pending_msg}{stopped_msg}'
                                 f'{conflict_msg}{deadlock_msg}')

                    # If an error should be raised for stopped threads
                    if setup_block.raise_not_alive and remotes_stopped:
                        error_msg = (
                            f'{self.name} raising '
                            f'SmartThreadRemoteThreadNotAlive {msg_suite}')
                        self.logger.error(error_msg)
                        raise SmartThreadRemoteThreadNotAlive(error_msg)

                    if conflict_remotes:
                        error_msg = (
                            f'{self.name} raising '
                            f'SmartThreadConflictDeadlockDetected {msg_suite}')
                        self.logger.error(error_msg)
                        raise SmartThreadConflictDeadlockDetected(error_msg)

                    if deadlock_remotes:
                        error_msg = (
                            f'{self.name} raising '
                            f'SmartThreadWaitDeadlockDetected {msg_suite}')
                        self.logger.error(error_msg)
                        raise SmartThreadWaitDeadlockDetected(error_msg)

                    # Note that the timer will never be expired if timeout
                    # was not specified either explicitly on the smart_wait
                    # call or via a default timeout established when this
                    # SmartThread was instantiated.
                    if setup_block.timer.is_expired():
                        error_msg = (
                            f'{self.name} raising '
                            f'SmartThreadRequestTimedOut {msg_suite}')
                        self.logger.error(error_msg)
                        raise SmartThreadRequestTimedOut(error_msg)

            time.sleep(0.2)

    ####################################################################
    # _process_sync
    ####################################################################
    def _process_sync(self, *,
                      pair_key: PairKey,
                      local_sb: ConnectionStatusBlock,
                      remote: str,
                      work_remotes: set[str],
                      error_remotes: ErrorRemotes
                      ) -> ErrorRemotes:
        """Do common setup for each request.

        Args:
            pair_key: the pair_key
            local_sb: connection block for this thread
            remote: name of remote thread
            work_remotes: work remotes
            error_remotes: contains stopped, conflict, and deadlock
                remotes

        Returns:
            A RequestBlock is returned that contains the timer and the set
            of threads to be processed

        """
        if not local_sb.sync_wait:
            if (self._get_status(remote)
                    == ThreadStatus.Stopped):
                error_remotes.remotes_stopped |= {remote}
                return error_remotes, False

            if remote in SmartThread._pair_array[
                pair_key].status_blocks:
                remote_sb = SmartThread._pair_array[
                    pair_key].status_blocks[remote]
                # for a sync request we check to see
                # whether a previous sync is still
                # in progress as indicated by the
                # sync event being set. We also need
                # to make sure there is not a
                # pending conflict that the remote
                # thread needs to clear. Note that
                # we only worry about the conflict
                # for sync - a wait conflict does
                # not impede us here since we are
                # using a different event block
                if not (remote_sb.sync_event.is_set()
                        or (remote_sb.conflict
                            and remote_sb.sync_wait)):
                    # sync resume remote thread
                    remote_sb.sync_event.set()
                    local_sb.sync_wait = True

        if local_sb.sync_wait:
            if local_sb.sync_event.is_set():
                local_sb.sync_wait = False
                local_sb.wait_timeout_specified = False

                # be ready for next sync wait
                local_sb.sync_event.clear()
                if (local_sb.del_deferred and
                        not local_sb.wait_event.is_set()):
                    self.do_refresh = True
                self.logger.info(
                    f'{self.name} smart_sync resumed by '
                    f'{remote}')
                work_remotes.remove(remote)
                # exit, we are done with this remote
                return error_remotes, True

            local_sb.wait_timeout_specified = timeout_specified
            # Check for error conditions first before
            # checking whether the remote is alive. If the
            # remote detects a deadlock or conflict issue,
            # it will set the current sides bit and then
            # raise an error and will likely be gone when we
            # check. We want to raise the same error on
            # this side.
            #
            # self.deadlock is set only by the remote. So,
            # if self.deadlock is True, then remote has
            # already detected the deadlock, set our flag,
            # raised the deadlock on its side, and is now
            # possibly ended or recovered and in a new wait.
            # If self.deadlock is False, and remote is
            # waiting and is not resumed then it will not be
            # getting resumed by us since we are also
            # waiting. So, we set self.remote.deadlock to
            # tell it, and then we raise the error on our
            # side. But, we don't do this if the
            # self.remote.deadlock is already on as that
            # suggests that we already told remote and
            # raised the error, which implies that we are in
            # a new wait and the remote has not yet woken up
            # to deal with the earlier deadlock. We can
            # simply ignore it for now.
            if remote in SmartThread._pair_array[
                pair_key].status_blocks:
                remote_sb = SmartThread._pair_array[
                    pair_key].status_blocks[remote]
                if not (local_sb.wait_timeout_specified
                        or remote_sb.wait_timeout_specified
                        or local_sb.deadlock
                        or local_sb.conflict):

                    if (remote_sb.wait_wait
                            and not
                            (remote_sb.wait_event.is_set()
                             or remote_sb.deadlock
                             or remote_sb.conflict)):
                        remote_sb.conflict = True
                        local_sb.conflict = True
                        self.logger.debug(
                            f'TestDebug {self.name} sync '
                            f'set remote and local '
                            f'conflict flags {remote=}')

            if local_sb.conflict:
                error_remotes.conflict_remotes |= {remote}
                self.logger.debug(
                    f'TestDebug {self.name} sync set '
                    f'{error_remotes.conflict_remotes=}')

        return error_remotes, False

    ####################################################################
    # _common_setup
    ####################################################################
    def _common_setup(self, *,
                      remotes: Union[str, set[str], list[str]],
                      raise_not_alive: bool,
                      timeout: OptIntFloat = None
                      ) -> RequestBlock:
        """Do common setup for each request.

        Args:
            remotes: remote threads for the request
            timeout: number of seconds to allow for request completion

        Returns:
            A RequestBlock is returned that contains the timer and the set
            of threads to be processed

        """
        timer = Timer(timeout=timeout, default_timeout=self.default_timeout)
        self.verify_thread_is_current()
        if isinstance(remotes, str):
            remotes = {remotes}
        elif isinstance(remotes, list):
            remotes = set(remotes)

        return RequestBlock(remotes=remotes,
                            timer=timer,
                            raise_not_alive=raise_not_alive)

    ####################################################################
    # _common_setup
    ####################################################################
    def _request_setup(self, *,
                       request_name: str,
                       remotes: Union[str, set[str], list[str]],
                       raise_not_alive: bool,
                       timeout: OptIntFloat = None
                       ) -> RequestBlock:
        """Do common setup for each request.

        Args:
            request_name: name of smart request
            remotes: remote threads for the request
            raise_not_alive: specifies whether to raise an error when
                a thread is stopped
            timeout: number of seconds to allow for request completion

        Returns:
            A RequestBlock is returned that contains the timer and the
            set of threads to be processed

        """
        timer = Timer(timeout=timeout, default_timeout=self.default_timeout)
        self.verify_thread_is_current()
        if isinstance(remotes, str):
            remotes = {remotes}
        elif isinstance(remotes, list):
            remotes = set(remotes)

        pk_remotes: list[PairKeyRemote] = []
        for remote in remotes:
            pair_key = self._get_pair_key(self.name, remote)
            pk_remotes.append((pair_key, remote))

        return RequestBlock(request_name=request_name,
                            remotes=remotes,
                            pk_remotes=pk_remotes,
                            timer=timer,
                            raise_not_alive=raise_not_alive,
                            do_refresh=False,
                            stopped_remotes=set(),
                            conflict_remotes=set(),
                            deadlock_remotes=set())

    ####################################################################
    # issue_entry_log_msg
    ####################################################################
    def _issue_entry_log_msg(
            self,
            request_block: RequestBlock,
            log_msg: Optional[str] = None,
            ) -> str:
        """Issue an entry log message.

        Args:
            request_block: contains the request specifications
            log_msg: log message to issue

        Returns:
            the log message to use for the exit call
        """
        log_msg_body = (
            f'targets: {sorted(request_block.remotes)} '
            f'timeout value: {request_block.timer_value()} '
            f'{get_formatted_call_sequence(latest=2, depth=1)}')

        if log_msg:
            log_msg_body += f' {log_msg}'

        entry_log_msg = (
            f'{request_block.request_name} entry: {log_msg_body}')

        exit_log_msg = (
            f'{request_block.request_name} exit: {log_msg_body}')

        self.logger.debug(entry_log_msg, stacklevel=2)
        return exit_log_msg

    ####################################################################
    # verify_thread_is_current
    ####################################################################
    def verify_thread_is_current(self) -> None:
        """Verify that SmartThread is running under the current thread.

        Raises:
            SmartThreadDetectedOpFromForeignThread: SmartThread services
                must be called from the thread that was originally
                assigned during instantiation of SmartThread.

        """
        if self.thread is not threading.current_thread():
            error_msg = (f'{threading.current_thread().name} raising '
                         'SmartThreadDetectedOpFromForeignThread. '
                         f'{self.thread=}, {threading.current_thread()=}. '
                         f'SmartThread services must be called from the '
                         f'thread that was originally assigned during '
                         f'instantiation of SmartThread. '
                         f'Call sequence: {get_formatted_call_sequence(1,2)}')
            self.logger.error(error_msg)
            raise SmartThreadDetectedOpFromForeignThread(error_msg)
