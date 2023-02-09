"""Module smart_thread.

===========
SmartThread
===========

The SmartThread class provides messaging, wait/resume, and sync
functions for threads in a multithreaded application. The functions have
deadlock detection and will also detect when a thread ends.

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
from collections.abc import Iterable
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from enum import auto, Enum, Flag
from itertools import combinations
import logging
import queue
import threading
import time
from typing import (Any, Callable, ClassVar, NamedTuple, Optional, Type,
                    TypeAlias, TYPE_CHECKING, Union)

########################################################################
# Third Party
########################################################################

########################################################################
# Local
########################################################################
from scottbrian_utils.diag_msg import get_formatted_call_sequence
from scottbrian_utils.timer import Timer
from scottbrian_locking import se_lock as sel

########################################################################
# Establish logger for SmartThread
########################################################################
logger = logging.getLogger(__name__)


########################################################################
# TypeAlias
########################################################################
IntFloat: TypeAlias = Union[int, float]
OptIntFloat: TypeAlias = Optional[IntFloat]
StrListStrSetStr: TypeAlias = Union[str, list[str], set[str]]
OptStrListStrSetStr: TypeAlias = Optional[StrListStrSetStr]

ConfigCmdCallable: TypeAlias = Callable[["RequestBlock", str], bool]
RequestCallable: TypeAlias = Callable[
    ["RequestBlock",
     "PairKeyRemote",
     "SmartThread.ConnectionStatusBlock"], bool]

ProcessRtn: TypeAlias = Union[ConfigCmdCallable, RequestCallable]


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


class SmartThreadWaitDeadlockDetected(SmartThreadError):
    """SmartThread exception for wait deadlock detected."""
    pass


class SmartThreadRequestTimedOut(SmartThreadError):
    """SmartThread exception for request timeout."""
    pass


class SmartThreadMutuallyExclusiveTargetThreadSpecified(SmartThreadError):
    """SmartThread exception mutually exclusive target and thread."""
    pass


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


class PairKey(NamedTuple):
    name0: str
    name1: str


class PairKeyRemote(NamedTuple):
    """NamedTuple for the request pair_key and remote name."""
    pair_key: PairKey
    remote: str

########################################################################
# RequestBlock
# contains the remotes and timer returned from _request_setup
########################################################################
@dataclass
class RequestBlock:
    """Setup block."""
    request_name: str
    process_rtn: ProcessRtn
    cleanup_rtn: Callable[[list[PairKeyRemote], str], None]
    get_block_lock: bool
    remotes: set[str]
    error_stopped_target: bool
    error_not_registered_target: bool
    completion_count: int
    pk_remotes: list[PairKeyRemote]
    timer: Timer
    do_refresh: bool
    exit_log_msg: Optional[str]
    msg_to_send: Any
    ret_msg: Any
    stopped_remotes: set[str]
    not_registered_remotes: set[str]
    conflict_remotes: set[str]
    deadlock_remotes: set[str]
    full_send_q_remotes: set[str]


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
# ThreadState Flags Class
# These flags are used to indicate the life cycle of a SmartThread.
# Initializing is set in the __init__ method. The __init__ method calls
# _register and upon return the state of Registered is set. When
# the start method is called, the state is set to Starting, and after
# the start is done and the thread is alive, the state is set to Alive.
# When the join method is called and the thread becomes not alive,
# the state is set to Stopped which then allows the _clean_up_registry
# method to remove the SmartThread.
########################################################################
class ThreadState(Flag):
    """Thread state flags."""
    Unregistered = auto()
    Initializing = auto()
    Registered = auto()
    Starting = auto()
    Alive = auto()
    Stopped = auto()


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
                 max_msgs: int = 0
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

        self.debug_logging_enabled = logger.isEnabledFor(logging.DEBUG)

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
        elif thread:  # caller provided the thread to use
            self.thread_create = ThreadCreate.Thread
            self.thread = thread
            self.thread.name = name
        else:  # caller is running on the thread to be used
            self.thread_create = ThreadCreate.Current
            self.thread = threading.current_thread()
            self.thread.name = name

        self.st_state: ThreadState = ThreadState.Unregistered
        self._set_state(
            target_thread=self,
            new_state=ThreadState.Initializing)

        self.auto_start = auto_start

        self.default_timeout = default_timeout

        self.code = None

        self.max_msgs = max_msgs

        self.remotes_unregistered: set[str] = set()
        self.remotes_full_send_q: set[str] = set()

        self.work_remotes: set[str] = set()
        self.work_pk_remotes: list[PairKeyRemote] = []

        # register this new SmartThread so others can find us
        self._register()

        self.start_issued = False
        self.auto_started = False
        if self.auto_start and not self.thread.is_alive():
            self.smart_start(self.name)
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
    # _get_state
    ####################################################################
    @staticmethod
    def _get_state(name: str) -> ThreadState:
        """Get the status of a thread.

        Args:
            name: name of thread to get status for

        Returns:
            The thread status
        """
        if name not in SmartThread._registry:
            return ThreadState.Unregistered
        if (not SmartThread._registry[name].thread.is_alive() and
                SmartThread._registry[name].st_state == ThreadState.Alive):
            return ThreadState.Stopped
        return SmartThread._registry[name].st_state

    ####################################################################
    # _set_status
    ####################################################################
    def _set_state(self,
                   target_thread: "SmartThread",
                   new_state: ThreadState) -> bool:
        """Set the state for a thread.

        Args:
            target_thread: thread to set status for
            new_state: the new status to be set

        Returns:
            True if status was changed, False otherwise
        """
        saved_status = target_thread.st_state
        if saved_status == new_state:
            return False
        target_thread.st_state = new_state

        logger.debug(
            f'{threading.current_thread().name} set '
            f'state for thread {target_thread.name} from {saved_status} to '
            f'{new_state}', stacklevel=2)
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
            logger.debug(f'{threading.current_thread().name} obtained '
                         '_registry_lock, class name = '
                         f'{self.__class__.__name__}')

            # Remove any old entries
            self._clean_up_registry(process='register')

            # Add entry if not already present
            if self.name not in SmartThread._registry:
                SmartThread._registry[self.name] = self
                if self.thread.is_alive():
                    new_state = ThreadState.Alive
                else:
                    new_state = ThreadState.Registered
                self._set_state(
                    target_thread=self,
                    new_state=new_state)
                SmartThread._registry_last_update = datetime.utcnow()
                print_time = (SmartThread._registry_last_update
                              .strftime("%H:%M:%S.%f"))
                logger.debug(
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

        Raises:
            SmartThreadErrorInRegistry: Registry item with key {key} has
                non-matching item.name of {item.name}.

        Notes:
            1) Must be called holding _registry_lock

        """
        # Remove any old entries
        keys_to_del = []
        for key, item in SmartThread._registry.items():
            logger.debug(
                f'key = {key}, item = {item}, '
                f'{item.thread.is_alive()=}, '
                f'{item.st_state=}')
            if ((not item.thread.is_alive())
                    and (item.st_state & ThreadState.Stopped)):
                keys_to_del.append(key)

            if key != item.name:
                raise SmartThreadErrorInRegistry(
                    f'Registry item with key {key} has non-matching '
                    f'item.name of {item.name}.')

        changed = False
        for key in keys_to_del:
            del SmartThread._registry[key]
            changed = True
            logger.debug(f'{threading.current_thread().name} removed '
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
            logger.debug(f'{threading.current_thread().name} did cleanup '
                         f'of registry at UTC {print_time}, deleted '
                         f'{keys_to_del}')

    ####################################################################
    # start
    ####################################################################
    def smart_start(self,
                    targets: Iterable,
                    error_stopped_target: bool = True,
                    timeout: OptIntFloat = None,
                    log_msg: Optional[str] = None) -> None:
        """Start the thread.

        Args:
            targets: names of smart threads to be started
            error_stopped_target: request will raise an error if any
                one of the targets is in a stopped state.
            timeout: timeout to wait for thread to become registered
            log_msg: log message to issue for request

        :Example: instantiate a SmartThread and start the thread

        >>> import scottbrian_utils.smart_thread as st
        >>> def f1() -> None:
        ...     print('f1 beta entered')
        >>> beta_smart_thread = SmartThread(name='beta', target=f1)
        >>> beta_smart_thread.smart_start()
        f1 beta entered

        """
        # get RequestBlock with targets in a set and a timer object
        request_block = self._request_setup(
            request_name='smart_start',
            remotes=targets,
            error_stopped_target=error_stopped_target,
            process_rtn=self._process_start,
            cleanup_rtn=None,
            get_block_lock=False,
            completion_count=0,
            timeout=timeout,
            log_msg=log_msg)

        self._config_cmd_loop(request_block=request_block)

        logger.debug(request_block.exit_log_msg)

    ####################################################################
    # _process_start
    ####################################################################
    def _process_start(self,
                       request_block: RequestBlock,
                       remote: str,
                       ) -> bool:
        """Process the smart_join request.

        Args:
            request_block: contains request related data
            remote: remote name

        Returns:
            True when request completed, False otherwise

        """
        if remote not in SmartThread._registry:
            self.remotes_unregistered |= {remote}
            return False

        if self._get_state(remote) == ThreadState.Stopped:
            request_block.stopped_remotes |= {remote}
            return False

        if (not SmartThread._registry[remote].thread.is_alive()
                and not SmartThread._registry[remote].start_issued):
            SmartThread._registry[remote].start_issued = True
            self._set_state(
                target_thread=SmartThread._registry[remote],
                new_state=ThreadState.Starting)
            # self.thread.start()
            threading.Thread.start(SmartThread._registry[remote].thread)

        if SmartThread._registry[remote].thread.is_alive():
            self._set_state(
                target_thread=SmartThread._registry[remote],
                new_state=ThreadState.Alive)

            logger.debug(
                f'{threading.current_thread().name} started thread '
                f'{SmartThread._registry[remote].name}, '
                'thread.is_alive(): '
                f'{SmartThread._registry[remote].thread.is_alive()}, '
                f'state: {SmartThread._registry[remote].st_state}')

            return True

        return False

    ####################################################################
    # unregister
    ####################################################################
    def unregister(self, *,
                   targets: Iterable,
                   timeout: OptIntFloat = None,
                   log_msg: Optional[str] = None) -> None:
        """Unregister threads that were never started.

        Args:
            targets: thread names that are to be unregistered
            timeout: timeout to use instead of default timeout
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
        request_block = self._request_setup(
            request_name='unregister',
            remotes=targets,
            error_stopped_target=False,
            error_not_registered_target=True,
            process_rtn=self._process_unregister,
            cleanup_rtn=None,
            get_block_lock=False,
            completion_count=0,
            timeout=timeout,
            log_msg=log_msg)

        self._config_cmd_loop(request_block=request_block)

        logger.debug(request_block.exit_log_msg)

    ####################################################################
    # _process_unregister
    ####################################################################
    def _process_unregister(self,
                            request_block: RequestBlock,
                            remote: str
                            ) -> bool:
        """Process the smart_join request.

        Args:
            request_block: contains request related data
            remote: remote name

        Returns:
            True when request completed, False otherwise

        """
        if self._get_state(remote) != ThreadState.Registered:
            request_block.not_registered_remotes |= {remote}
            return False

        # remove this thread from the registry
        self._set_state(
            target_thread=SmartThread._registry[remote],
            new_state=ThreadState.Stopped)
        self._clean_up_registry(process='unregister')

        logger.debug(
            f'{self.name} did successful unregister of '
            f'{remote}.')

        # restart while loop with one less remote
        return True

    ####################################################################
    # join
    ####################################################################
    def smart_join(self, *,
                   targets: Iterable,
                   timeout: OptIntFloat = None,
                   log_msg: Optional[str] = None) -> None:
        """Join with remote targets.

        Args:
            targets: thread names that are to be joined
            timeout: timeout to use instead of default timeout
            log_msg: log message to issue

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
        request_block = self._request_setup(
            request_name='smart_join',
            remotes=targets,
            error_stopped_target=False,
            process_rtn=self._process_smart_join,
            cleanup_rtn=None,
            get_block_lock=False,
            completion_count=0,
            timeout=timeout,
            log_msg=log_msg)

        self._config_cmd_loop(request_block=request_block)

        logger.debug(request_block.exit_log_msg)

    ####################################################################
    # _process_smart_join
    ####################################################################
    def _process_smart_join(self,
                            request_block: RequestBlock,
                            remote: str,
                            ) -> bool:
        """Process the smart_join request.

        Args:
            request_block: contains request related data
            remote: remote name

        Returns:
            True when request completed, False otherwise

        """
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
                SmartThread._registry[remote].thread.join(timeout=0.2)
            except RuntimeError:
                # We know the thread is registered, so
                # we will skip it for now and come back to it
                # later. If it never starts and exits then
                # we will timeout (if timeout was specified)
                return False

            # we need to check to make sure the thread is
            # not alive in case we timed out
            if not SmartThread._registry[remote].thread.is_alive():
                # indicate remove from registry
                self._set_state(
                    target_thread=SmartThread._registry[remote],
                    new_state=ThreadState.Stopped)
                # remove this thread from the registry
                self._clean_up_registry(
                    process='join')

                logger.debug(
                    f'{self.name} did successful join of '
                    f'{remote}.')

                # restart while loop with one less remote
                return True

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
               until its state is changed to Stopped to indicate it was
               once alive. Its state is set to Stopped when a join is
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
        logger.debug(f'{current_thread_name} entered _refresh_pair_array')
        changed = False
        # scan registry and adjust status

        # for name0, s_thread1 in (SmartThread._registry.items()):
        #
        #     for name1, s_thread2 in (SmartThread._registry.items()):
        #         if name0 == name1:
        #             continue
        pair_keys = combinations(sorted(SmartThread._registry.keys()), 2)
        for pair_key in pair_keys:
            # create new connection pair if needed
            # pair_key = self._get_pair_key(name0, name1)
            if pair_key not in SmartThread._pair_array:
                SmartThread._pair_array[pair_key] = (
                    SmartThread.ConnectionPair(
                        status_lock=threading.Lock(),
                        status_blocks={}
                    ))
                logger.debug(
                    f'{current_thread_name} created _refresh_pair_array with '
                    f'pair_key = {pair_key}')
                changed = True

            # add status block for name0 and name1 if needed
            # for name in (name0, name1):
            for name in pair_key:
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
                    logger.debug(
                        f'{current_thread_name} added status_blocks entry '
                        f'for pair_key = {pair_key}, name = {name}')
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
                    logger.debug(
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
                    logger.debug(
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
            logger.debug(
                f'{current_thread_name} removed _pair_array entry'
                f' for pair_key = {pair_key}')
            changed = True

        if changed:
            SmartThread._pair_array_last_update = datetime.utcnow()
            print_time = (SmartThread._pair_array_last_update
                          .strftime("%H:%M:%S.%f"))
            logger.debug(
                f'{current_thread_name} updated _pair_array'
                f' at UTC {print_time}')

    ####################################################################
    # send_msg
    ####################################################################
    def send_msg(self,
                 targets: Iterable,
                 msg: Any,
                 error_stopped_target: bool = True,
                 log_msg: Optional[str] = None,
                 timeout: OptIntFloat = None) -> None:
        """Send a msg.

        Args:
            msg: the msg to be sent
            targets: names to send the message to
            error_stopped_target: request will raise an error if any
                one of the targets is in a stopped state.
            log_msg: log message to issue
            timeout: number of seconds to wait for full queue to get
                       free slot

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
        request_block = self._request_setup(
            request_name='send_msg',
            remotes=targets,
            error_stopped_target=error_stopped_target,
            process_rtn=self._process_send_msg,
            cleanup_rtn=None,
            get_block_lock=False,
            completion_count=0,
            timeout=timeout,
            msg_to_send=msg,
            log_msg=log_msg)

        self.remotes_unregistered = set()
        self.remotes_full_send_q = set()
        self._request_loop(request_block=request_block)

        logger.debug(request_block.exit_log_msg)

    ####################################################################
    # _process_send_msg
    ####################################################################
    def _process_send_msg(self,
                          request_block: RequestBlock,
                          pk_remote: PairKeyRemote,
                          local_sb: ConnectionStatusBlock,
                          ) -> bool:
        """Process the send_msg request.

        Args:
            request_block: contains request related data
            pk_remote: the pair_key and remote name
            local_sb: connection block for this thread

        Returns:
            True when request completed, False otherwise

        """
        # If the remote is not yet ready, continue with
        # the next remote in the list.
        # We are OK with leaving a message in the receiver
        # msg_q if we think there is a chance the receiver
        # will recv_msg to get it. But, if the receiver is
        # stopped and is on its way out, its msg_q will be
        # deleted and the message will be lost. So we will
        # check for this and continue to wait in hopes that
        # the thread will be resurrected.
        if pk_remote.remote not in SmartThread._registry:
            self.remotes_unregistered |= {pk_remote.remote}
            return False

        if self._get_state(pk_remote.remote) == ThreadState.Stopped:
            request_block.stopped_remotes |= {pk_remote.remote}
            self.remotes_unregistered |= {pk_remote.remote}
            return False

        # If here, remote is in registry and is alive or
        # will hopefully soon be alive.
        # This also means we have an entry for the remote in
        # the status_blocks in the connection array
        try:
            # place message on remote q
            SmartThread._pair_array[
                pk_remote.pair_key].status_blocks[
                pk_remote.remote].msg_q.put(request_block.msg_to_send,
                                        timeout=0.01)
            logger.info(
                f'{self.name} sent message to {pk_remote.remote}')

            # we need to remove the remote from the unreg
            # or fullq sets since the send now succeeded
            self.remotes_unregistered -= {pk_remote.remote}
            request_block.full_send_q_remotes -= {pk_remote.remote}
            self.remotes_full_send_q -= {pk_remote.remote}
            return True
        except queue.Full:
            # If the remote msg queue is full, move on to
            # the next remote (if one). We will come back
            # to the full remote later and hope that it
            # reads its messages and frees up space on its
            # queue before we time out.
            request_block.full_send_q_remotes |= {pk_remote.remote}
            self.remotes_full_send_q |= {pk_remote.remote}

        return False

    ####################################################################
    # recv_msg
    ####################################################################
    def recv_msg(self,
                 remote: str,
                 error_stopped_target: bool = True,
                 log_msg: Optional[str] = None,
                 timeout: OptIntFloat = None) -> Any:
        """Receive a msg.

        Args:
            remote: thread we expect to send us a message
            error_stopped_target: request will raise an error if any
                one of the targets is in a stopped state.
            log_msg: log message to issue
            timeout: number of seconds to wait for message

        Returns:
            message unless timeout occurs

        """
        # get RequestBlock with targets in a set and a timer object
        request_block = self._request_setup(
            request_name='recv_msg',
            remotes=remote,
            error_stopped_target=error_stopped_target,
            process_rtn=self._process_recv_msg,
            cleanup_rtn=None,
            get_block_lock=False,
            completion_count=0,
            timeout=timeout,
            log_msg=log_msg)

        self._request_loop(request_block=request_block)

        logger.debug(request_block.exit_log_msg)

        return request_block.ret_msg

    ####################################################################
    # _process_recv_msg
    ####################################################################
    def _process_recv_msg(self,
                          request_block: RequestBlock,
                          pk_remote: PairKeyRemote,
                          local_sb: ConnectionStatusBlock,
                          ) -> bool:
        """Process the recv_msg request.

        Args:
            request_block: contains request related data
            pk_remote: the pair_key and remote name
            local_sb: connection block for this thread

        Returns:
            True when request completed, False otherwise

        """
        try:
            # recv message from remote
            request_block.ret_msg = local_sb.msg_q.get(timeout=0.01)
            logger.info(
                f'{self.name} received msg from {pk_remote.remote}')
            # if we had wanted to delete an entry in the
            # pair array for this thread because the other
            # thread exited, but we could not because this
            # thread had a pending msg to recv, then we
            # deferred the delete. If the msg_q for this
            # thread is now empty as a result of this recv,
            # we can go ahead and delete the pair, so
            # set the flag to do a refresh (we can't do the
            # refresh here because we need to hold the lock
            # exclusive)
            if local_sb.del_deferred and local_sb.msg_q.empty():
                request_block.do_refresh = True
            return True

        except queue.Empty:
            # The msg queue was just now empty which rules out that case
            # that the pair_key is valid only because of a deferred
            # delete. So, we know the remote is in the registry and in
            # the status block.
            if self._get_state(pk_remote.remote) == ThreadState.Stopped:
                request_block.stopped_remotes |= {pk_remote.remote}

        return False

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
                if pair_key.name0 == self.name:
                    remote = pair_key.name1
                elif pair_key.name1 == self.name:
                    remote = pair_key.name0
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
                     targets: Iterable,
                     error_stopped_target: bool = True,
                     log_msg: Optional[str] = None,
                     timeout: OptIntFloat = None,
                     code: Optional[Any] = None) -> None:
        """Resume a waiting or soon to be waiting thread.

        Args:
            targets: names of threads that are to be resumed
            error_stopped_target: request will raise an error if any
                one of the targets is in a stopped state.
            log_msg: log msg to log
            timeout: number of seconds to allow for ``resume()`` to complete
            code: code that waiter can retrieve with ``get_code()``

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
               error_stopped_target is True.
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

        # get RequestBlock with targets in a set and a timer object
        request_block = self._request_setup(
            request_name='smart_resume',
            remotes=targets,
            error_stopped_target=error_stopped_target,
            process_rtn=self._process_resume,
            cleanup_rtn=None,
            get_block_lock=True,
            completion_count=0,
            timeout=timeout,
            log_msg=log_msg)

        self._request_loop(request_block=request_block)

        logger.debug(request_block.exit_log_msg)

    ####################################################################
    # _process_resume
    ####################################################################
    def _process_resume(self,
                        request_block: RequestBlock,
                        pk_remote: PairKeyRemote,
                        local_sb: ConnectionStatusBlock,
                        ) -> bool:
        """Process the resume request.

        Args:
            request_block: contains request related data
            pk_remote: the pair_key and remote name
            local_sb: connection block for this thread

        Returns:
            True when request completed, False otherwise

        """
        # If the remote is not yet ready, continue with
        # the next remote in the list.
        # We are OK with leaving a message in the receiver
        # msg_q if we think there is a chance the receiver
        # will recv_msg to get it. But, if the receiver is
        # stopped and is on its way out, its msg_q will be
        # deleted and the message will be lost. So we will
        # check for this and continue to wait in hopes that
        # the thread will be resurrected.
        if pk_remote.remote not in SmartThread._registry:
            return False

        if self._get_state(pk_remote.remote) == ThreadState.Stopped:
            request_block.stopped_remotes |= {pk_remote.remote}
            return False

        # If here, remote is in registry and is alive or
        # will hopefully will be soon.
        # This also means we have an entry for the remote in
        # the status_blocks in the connection array
        remote_sb = SmartThread._pair_array[
            pk_remote.pair_key].status_blocks[pk_remote.remote]

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

            # # set the code, if one
            # if code:
            #     remote_sb.code = code
            # wake remote thread and start
            # the while loop again with one
            # less remote
            remote_sb.wait_event.set()
            return True

        return False

    ####################################################################
    # smart_sync
    ####################################################################
    def smart_sync(self, *,
                   targets: Iterable,
                   error_stopped_target: bool = True,
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
         error_stopped_target: request will raise an error if any
                one of the targets is in a stopped state.
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
            error_stopped_target=error_stopped_target,
            process_rtn=self._process_sync,
            cleanup_rtn=self._sync_wait_error_cleanup,
            get_block_lock=True,
            completion_count=0,
            timeout=timeout,
            log_msg=log_msg)

        self._request_loop(request_block=request_block)

        logger.debug(request_block.exit_log_msg)

    ####################################################################
    # _process_sync
    ####################################################################
    def _process_sync(self,
                      request_block: RequestBlock,
                      pk_remote: PairKeyRemote,
                      local_sb: ConnectionStatusBlock,
                      ) -> bool:
        """Process the sync request.

        Args:
            request_block: contains request related data
            pk_remote: the pair_key and remote name
            local_sb: connection block for this thread

        Returns:
            True when request completed, False otherwise

        """
        if not local_sb.sync_wait:
            if self._get_state(pk_remote.remote) == ThreadState.Stopped:
                request_block.stopped_remotes |= {pk_remote.remote}
                return False

            if pk_remote.remote in SmartThread._pair_array[
                    pk_remote.pair_key].status_blocks:
                remote_sb = SmartThread._pair_array[
                    pk_remote.pair_key].status_blocks[pk_remote.remote]
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
                    request_block.do_refresh = True
                logger.info(
                    f'{self.name} smart_sync resumed by '
                    f'{pk_remote.remote}')

                # exit, we are done with this remote
                return True

            local_sb.wait_timeout_specified = (
                request_block.timer.is_specified())
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
            if pk_remote.remote in SmartThread._pair_array[
                    pk_remote.pair_key].status_blocks:
                remote_sb = SmartThread._pair_array[
                    pk_remote.pair_key].status_blocks[pk_remote.remote]
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
                        logger.debug(
                            f'TestDebug {self.name} sync '
                            f'set remote and local '
                            f'conflict flags {pk_remote=}')

            if local_sb.conflict:
                request_block.conflict_remotes |= {pk_remote.remote}
                logger.debug(
                    f'TestDebug {self.name} sync set '
                    f'{request_block.conflict_remotes=}')

        return False

    ####################################################################
    # _sync_wait_error_cleanup
    ####################################################################
    def _sync_wait_error_cleanup(self,
                                 pk_remotes: list[PairKeyRemote],
                                 backout_request: str) -> None:
        """Cleanup a failed sync request.

        Args:
            pk_remotes: names of threads that need cleanup
            backout_request: sync or wait

        Notes:
            must be holding the registry lock at least shared
        """
        for pair_key, remote in pk_remotes:
            if pair_key in SmartThread._pair_array:
                # having a pair_key in the array implies our entry
                # exists - set local_sb for easy references
                local_sb = SmartThread._pair_array[
                    pair_key].status_blocks[self.name]

                with SmartThread._pair_array[pair_key].status_lock:
                    # if we made it as far as having set the remote sync
                    # event, then we need to back that out, but only when
                    # the remote did not set out event yet
                    if backout_request == 'smart_sync' and local_sb.sync_wait:
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
                    if backout_request == 'smart_wait' and local_sb.wait_wait:
                        local_sb.wait_wait = False
                        local_sb.wait_event.clear()

                    local_sb.deadlock = False
                    local_sb.conflict = False
                    local_sb.wait_timeout_specified = False

    ####################################################################
    # wait
    ####################################################################
    def smart_wait(self, *,
                   remotes: Iterable,
                   error_stopped_target: bool = True,
                   wait_for: WaitFor = WaitFor.All,
                   log_msg: Optional[str] = None,
                   timeout: OptIntFloat = None) -> None:
        """Wait on event.

        Args:
            remotes: names of threads that we expect to resume us
            error_stopped_target: request will raise an error if any
                one of the targets is in a stopped state.
            wait_for: specifies whether to wait for only one remote or
                for all remotes
            log_msg: log msg to log
            timeout: number of seconds to allow for wait to be
                resumed

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
        # get RequestBlock with targets in a set and a timer object
        request_block = self._request_setup(
            request_name='smart_wait',
            remotes=remotes,
            error_stopped_target=error_stopped_target,
            process_rtn=self._process_wait,
            cleanup_rtn=self._sync_wait_error_cleanup,
            get_block_lock=True,
            completion_count=0,
            timeout=timeout,
            log_msg=log_msg)

        if wait_for == WaitFor.Any:
            request_block.completion_count = len(request_block.remotes) - 1

        self._request_loop(request_block=request_block)

        logger.debug(request_block.exit_log_msg)

    ####################################################################
    # _process_wait
    ####################################################################
    def _process_wait(self,
                      request_block: RequestBlock,
                      pk_remote: PairKeyRemote,
                      local_sb: ConnectionStatusBlock,
                      ) -> bool:
        """Process the sync request.

        Args:
            request_block: contains request related data
            pk_remote: the pair_key and remote name
            local_sb: connection block for this thread

        Returns:
            True when request completed, False otherwise

        """
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
                request_block.do_refresh = True
            logger.info(
                f'{self.name} smart_wait resumed by '
                f'{pk_remote.remote}')
            return True

        local_sb.wait_timeout_specified = (
            request_block.timer.is_specified())
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
        if pk_remote.remote in SmartThread._pair_array[
                pk_remote.pair_key].status_blocks:
            remote_sb = SmartThread._pair_array[
                pk_remote.pair_key].status_blocks[pk_remote.remote]
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
                    logger.debug(
                        f'TestDebug {self.name} wait '
                        f'set remote and local '
                        f'conflict flags {pk_remote.remote=}')
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
                    logger.debug(
                        f'TestDebug {self.name} wait '
                        f'set remote and local '
                        f'deadlock flags {pk_remote.remote=}')

        if local_sb.conflict:
            local_sb.sync_wait = False
            local_sb.wait_wait = False
            local_sb.conflict = False
            local_sb.wait_timeout_specified = False
            request_block.conflict_remotes |= {pk_remote.remote}
            logger.debug(
                f'TestDebug {self.name} wait set {pk_remote.remote=}'
                f'{request_block.conflict_remotes=}')

        if local_sb.deadlock:
            local_sb.sync_wait = False
            local_sb.wait_wait = False
            local_sb.deadlock = False
            local_sb.wait_timeout_specified = False
            request_block.deadlock_remotes |= {pk_remote.remote}
            logger.debug(
                f'TestDebug {self.name} wait set {pk_remote.remote=}'
                f'{request_block.deadlock_remotes=}')

    ####################################################################
    # _config_cmd_loop
    ####################################################################
    def _config_cmd_loop(self, *,
                         request_block: RequestBlock,
                         ) -> None:
        """Main loop for each config command.

        Each of the requests calls this method to perform the loop of
        the targets.

        Args:
            request_block: contains targets, timeout, etc

        Raises:
            SmartThreadRequestTimedOut: request processing timed out
                waiting for the remote.
            SmartThreadRemoteThreadNotAlive: request detected remote
                thread is not alive.
            SmartThreadConflictDeadlockDetected: a deadlock was detected
                between a smart_sync request and a smart_wait request.
            SmartThreadWaitDeadlockDetected: a deadlock was detected
                between two smart_wait requests.

        """
        self.work_remotes: set[str] = request_block.remotes.copy()

        while len(self.work_remotes) > request_block.completion_count:
            num_start_loop_work_remotes = len(self.work_remotes)
            for remote in self.work_remotes.copy():
                with sel.SELockExcl(SmartThread._registry_lock):
                    if request_block.process_rtn(request_block,
                                                 remote):
                        self.work_remotes -= {remote}

            # if no progress was made
            if len(self.work_remotes) == num_start_loop_work_remotes:
                if ((request_block.error_stopped_target
                     and request_block.stopped_remotes)
                        or (request_block.error_not_registered_target
                            and request_block.not_registered_remotes)
                        or request_block.timer.is_expired()):

                    self._handle_loop_errors(request_block=request_block,
                                             pending_remotes=list(
                                                 self.work_remotes))

            time.sleep(0.2)

    ####################################################################
    # _request_loop
    ####################################################################
    def _request_loop(self, *,
                      request_block: RequestBlock,
                      ) -> None:
        """Main loop for each request.

        Each of the requests calls this method to perform the loop of
        the targets.

        Args:
            request_block: contains targets, timeout, etc

        Raises:
            SmartThreadRequestTimedOut: request processing timed out
                waiting for the remote.
            SmartThreadRemoteThreadNotAlive: request detected remote
                thread is not alive.
            SmartThreadConflictDeadlockDetected: a deadlock was detected
                between a smart_sync request and a smart_wait request.
            SmartThreadWaitDeadlockDetected: a deadlock was detected
                between two smart_wait requests.

        """
        self.work_pk_remotes: list[PairKeyRemote] = (
            request_block.pk_remotes.copy())

        while len(self.work_pk_remotes) > request_block.completion_count:
            num_start_loop_work_remotes = len(self.work_pk_remotes)
            for pk_remote in self.work_pk_remotes.copy():
                with sel.SELockShare(SmartThread._registry_lock):
                    if pk_remote.pair_key in SmartThread._pair_array:
                        # having a pair_key in the array implies our entry
                        # exists - set local_sb for easy references
                        local_sb = SmartThread._pair_array[
                            pk_remote.pair_key].status_blocks[self.name]

                        # lock needed to coordinate conflict/deadlock
                        with self._connection_block_lock(
                                lock=SmartThread._pair_array[
                                    pk_remote.pair_key].status_lock,
                                obtain_tf=request_block.get_block_lock):
                            if request_block.process_rtn(request_block,
                                                         pk_remote,
                                                         local_sb):
                                self.work_pk_remotes.remove(pk_remote)
                                request_block.stopped_remotes -= {
                                    pk_remote.remote}

            if request_block.do_refresh:
                with sel.SELockExcl(SmartThread._registry_lock):
                    self._refresh_pair_array()
                request_block.do_refresh = False

            # if no progress was made
            if len(self.work_pk_remotes) == num_start_loop_work_remotes:
                if ((request_block.error_stopped_target
                     and request_block.stopped_remotes)
                        or (request_block.error_not_registered_target
                            and request_block.not_registered_remotes)
                        or request_block.conflict_remotes
                        or request_block.deadlock_remotes
                        or request_block.timer.is_expired()):

                    # cleanup before doing the error
                    if request_block.cleanup_rtn:
                        with sel.SELockShare(SmartThread._registry_lock):
                            request_block.cleanup_rtn(
                                self.work_pk_remotes,
                                request_block.request_name)

                    pending_remotes = [remote for pk, remote in
                                       self.work_pk_remotes]
                    self._handle_loop_errors(request_block=request_block,
                                             pending_remotes=pending_remotes)

            time.sleep(0.2)

    ####################################################################
    # _handle_loop_errors
    ####################################################################
    def _handle_loop_errors(self, *,
                            request_block: RequestBlock,
                            pending_remotes: list[str]
                            ) -> None:
        """Raise an error if needed..

        Each of the requests calls this method to perform the loop of
        the targets.

        Args:
            request_block: contains targets, timeout, etc

        Raises:
            SmartThreadRequestTimedOut: request processing timed out
                waiting for the remote.
            SmartThreadRemoteThreadNotAlive: request detected remote
                thread is not alive.
            SmartThreadConflictDeadlockDetected: a deadlock was detected
                between a smart_sync request and a smart_wait request.
            SmartThreadWaitDeadlockDetected: a deadlock was detected
                between two smart_wait requests.

        """
        targets_msg = (f'while processing a '
                       f'{request_block.request_name} '
                       f'request with remotes '
                       f'{sorted(request_block.remotes)}.')

        pending_msg = (f' Remotes that are pending: '
                       f'{sorted(pending_remotes)}.')

        if request_block.stopped_remotes:
            stopped_msg = (
                ' Remotes that are stopped: '
                f'{sorted(request_block.stopped_remotes)}.')
        else:
            stopped_msg = ''

        if request_block.not_registered_remotes:
            not_registered_msg = (
                ' Remotes that are not registered: '
                f'{sorted(request_block.not_registered_remotes)}.')
        else:
            not_registered_msg = ''

        if request_block.conflict_remotes:
            if request_block.request_name == 'smart_sync':
                remote_request = 'smart_wait'
            else:
                remote_request = 'smart_sync'
            conflict_msg = (
                f' Remotes doing a {remote_request} '
                'request that are deadlocked: '
                f'{sorted(request_block.conflict_remotes)}.')
        else:
            conflict_msg = ''

        if request_block.deadlock_remotes:
            deadlock_msg = (
                f' Remotes doing a smart_wait '
                'request that are deadlocked: '
                f'{sorted(request_block.deadlock_remotes)}.')
        else:
            deadlock_msg = ''

        if request_block.full_send_q_remotes:
            full_send_q_msg = (
                f' Remotes who have a full send_q: '
                f'{sorted(request_block.full_send_q_remotes)}.')
        else:
            full_send_q_msg = ''

        msg_suite = (f'{targets_msg}{pending_msg}{stopped_msg}'
                     f'{not_registered_msg}{conflict_msg}'
                     f'{deadlock_msg}{full_send_q_msg}')

        # If an error should be raised for stopped threads
        if (request_block.error_stopped_target
                and request_block.stopped_remotes):
            error_msg = (
                f'{self.name} raising '
                f'SmartThreadRemoteThreadNotAlive {msg_suite}')
            logger.error(error_msg)
            raise SmartThreadRemoteThreadNotAlive(error_msg)

        if request_block.conflict_remotes:
            error_msg = (
                f'{self.name} raising '
                f'SmartThreadConflictDeadlockDetected {msg_suite}')
            logger.error(error_msg)
            raise SmartThreadConflictDeadlockDetected(error_msg)

        if request_block.deadlock_remotes:
            error_msg = (
                f'{self.name} raising '
                f'SmartThreadWaitDeadlockDetected {msg_suite}')
            logger.error(error_msg)
            raise SmartThreadWaitDeadlockDetected(error_msg)

        # Note that the timer will never be expired if timeout
        # was not specified either explicitly on the smart_wait
        # call or via a default timeout established when this
        # SmartThread was instantiated.
        if request_block.timer.is_expired():
            error_msg = (
                f'{self.name} raising '
                f'SmartThreadRequestTimedOut {msg_suite}')
            logger.error(error_msg)
            raise SmartThreadRequestTimedOut(error_msg)

    ####################################################################
    # _request_setup
    ####################################################################
    def _request_setup(self, *,
                       request_name: str,
                       process_rtn: Callable[
                           ["RequestBlock",
                            PairKeyRemote,
                            "SmartThread.ConnectionStatusBlock"], bool],
                       cleanup_rtn: Optional[Callable[[list[PairKeyRemote],
                                                       str], None]],
                       get_block_lock: bool,
                       remotes: Iterable,
                       error_stopped_target: bool,
                       error_not_registered_target: bool = False,
                       completion_count: int = 0,
                       timeout: OptIntFloat = None,
                       log_msg: Optional[str] = None,
                       msg_to_send: Any = None,
                       ) -> RequestBlock:
        """Do common setup for each request.

        Args:
            request_name: name of smart request
            process_rtn: method to process the request for each
                iteration of the request loop
            cleanup_rtn: method to back out a failed request
            get_block_lock: True or False
            remotes: remote threads for the request
            error_stopped_target: request will raise an error if any
                one of the targets is in a stopped state.
            error_not_registered_target: request will raise an error if
                any one of the targets is in any state other than
                registered.
            timeout: number of seconds to allow for request completion
            log_msg: caller log message to issue
            msg_to_send: send_msg message to send


        Returns:
            A RequestBlock is returned that contains the timer and the
            set of threads to be processed

        """
        timer = Timer(timeout=timeout, default_timeout=self.default_timeout)

        if not remotes:
            raise SmartThreadInvalidInput(f'{self.name} {request_name} '
                                          'request with no targets specified.')

        if isinstance(remotes, str):
            remotes = {remotes}
        else:
            remotes = set(remotes)

        if (request_name != 'smart_start'
                and threading.current_thread().name in remotes):
            raise SmartThreadInvalidInput(f'{self.name} {request_name} is '
                                          f'also a target: {remotes=}')

        pk_remotes: list[PairKeyRemote] = []

        if request_name in ('send_msg', 'recv_msg', 'smart_resume',
                            'smart_sync', 'smart_wait'):
            self.verify_thread_is_current()
            pk_remotes = [PairKeyRemote(
                self._get_pair_key(threading.current_thread().name,
                                   remote), remote) for remote in remotes]

        request_block = RequestBlock(
            request_name=request_name,
            process_rtn=process_rtn,
            cleanup_rtn=cleanup_rtn,
            get_block_lock=get_block_lock,
            remotes=remotes,
            error_stopped_target=error_stopped_target,
            error_not_registered_target=error_not_registered_target,
            completion_count=completion_count,
            pk_remotes=pk_remotes,
            timer=timer,
            do_refresh=False,
            exit_log_msg=None,
            msg_to_send=msg_to_send,
            ret_msg=None,
            stopped_remotes=set(),
            not_registered_remotes=set(),
            conflict_remotes=set(),
            deadlock_remotes=set(),
            full_send_q_remotes=set())

        if self.debug_logging_enabled:
            request_block.exit_log_msg = self._issue_entry_log_msg(
                request_block=request_block,
                log_msg=log_msg)

        return request_block

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
            f'requestor: {threading.current_thread().name} '
            f'targets: {sorted(request_block.remotes)} '
            f'timeout value: {request_block.timer.timeout_value()} '
            f'{get_formatted_call_sequence(latest=3, depth=1)}')

        if log_msg:
            log_msg_body += f' {log_msg}'

        entry_log_msg = (
            f'{request_block.request_name} entry: {log_msg_body}')

        exit_log_msg = (
            f'{request_block.request_name} exit: {log_msg_body}')

        logger.debug(entry_log_msg, stacklevel=3)
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
            logger.error(error_msg)
            raise SmartThreadDetectedOpFromForeignThread(error_msg)

    ####################################################################
    # verify_thread_is_current
    ####################################################################
    @contextmanager
    def _connection_block_lock(*args, **kwds) -> None:
        """Obtain the connection_block lock.

        This method is called from _request_loop to obtain the
        connection_block lock for those requests that need it
        (smart_resume, smart_wait, and smart_sync) and to not obtain
        it for those requests that do not need it (send_msg, recv_msg).
        This allows the code in _request_loop to use the with statement
        for the lock obtain with having to code around it.

        Args:
            lock: the lock to obtain
            obtain_tf: specifies whether to obtain the lock

        """
        # is request needs the lock
        if kwds['obtain_tf']:
            kwds['lock'].acquire()
        try:
            yield
        finally:
            # release the lock if it was obtained
            if kwds['obtain_tf']:
                kwds['lock'].release()
