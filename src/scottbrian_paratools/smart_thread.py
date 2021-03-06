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
>>> beta_thread.start()
>>> msg_from_beta=alpha_thread.recv_msg(remote='beta')
>>> print(msg_from_beta)
>>> alpha_thread.resume(targets='beta')
>>> alpha_thread.join(targets='beta')
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
from dataclasses import dataclass
from datetime import datetime
from enum import auto, Enum, Flag
import logging
import queue
import threading
import time
from typing import Any, Callable, Final, Optional, Type, TYPE_CHECKING, Union

########################################################################
# Third Party
########################################################################

########################################################################
# Local
########################################################################
from scottbrian_utils.diag_msg import get_formatted_call_sequence


########################################################################
# SmartThread class exceptions
########################################################################
class SmartThreadError(Exception):
    """Base class for exceptions in this module."""
    pass


class SmartThreadDetectedOpFromForeignThread(SmartThreadError):
    """SmartThread exception for attempted op from unregistered
    thread.
    """
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


class SmartThreadInconsistentFlagSettings(SmartThreadError):
    """SmartThread exception for flag setting that are not valid."""
    pass


class SmartThreadWaitDeadlockDetected(SmartThreadError):
    """SmartThread exception for wait deadlock detected."""
    pass


class SmartThreadWaitUntilTimeout(SmartThreadError):
    """SmartThread exception for pause_until timeout."""
    pass


class SmartThreadRecvMsgTimedOut(SmartThreadError):
    """SmartThread exception for timeout waiting for message."""
    pass


class SmartThreadSendMsgFailed(SmartThreadError):
    """SmartThread exception failure to send message."""
    pass


class SmartThreadMutuallyExclusiveTargetThreadSpecified(SmartThreadError):
    """SmartThread exception mutually exclusive target and thread
    specified.
    """
    pass


class SmartThreadRemoteSmartThreadMismatch(SmartThreadError):
    """SmartThread exception remote_array SmartThread does not match
    registry SmartThread.
    """
    pass


class SmartThreadRemoteThreadMismatch(SmartThreadError):
    """SmartThread exception remote_array SmartThread.thread does not
    match registry SmartThread.thread.
    """
    pass


class SmartThreadStatusLockMismatch(SmartThreadError):
    """SmartThread exception remote_array status_lock does not match
    remote.remote_array status_lock.
    """
    pass


class SmartThreadRemoteMsgQMismatch(SmartThreadError):
    """SmartThread exception remote_array remote msg_q does not match
    remote.remote_array msg_q.
    """
    pass


class SmartThreadJoinTimedOut(SmartThreadError):
    """SmartThread exception join timed out."""
    pass


class SmartThreadResumeTimedOut(SmartThreadError):
    """SmartThread exception resume timed out."""
    pass


class SmartThreadWaitTimedOut(SmartThreadError):
    """SmartThread exception wait timed out."""
    pass


class SmartThreadSyncTimedOut(SmartThreadError):
    """SmartThread exception sync timed out."""
    pass


class SmartThreadArgsSpecificationWithoutTarget(SmartThreadError):
    """SmartThread exception args specified without target."""
    pass


########################################################################
# SmartThread class exceptions
# this should go into utilities
########################################################################
class Timer:
    def __init__(self,
                 timeout: Optional[Union[int, float]] = None,
                 default_timeout: Optional[Union[int, float]] = None) -> None:
        """Initialize a timer object.

        Args:
            timeout: value to use for timeout
            default_timeout: value to use if timeout is None

        """
        self.start_time = time.time()
        # we have either a timeout <= 0 or None which means no timeout
        # can happen, or we have a timeout with a positive value which
        # we will use, or we will use the default timeout which could
        # also be None, in which again means no timeout can happen
        if timeout and timeout <= 0:
            self._timeout = None
        else:
            self._timeout = timeout or default_timeout

    @property
    def timeout(self):
        if self._timeout:  # if not None
            # make sure not negative
            ret_timeout = max(0.01,
                              self._timeout - (time.time() - self.start_time))
        else:
            ret_timeout = None
        return ret_timeout  # return value of remaining time for timeout

    def is_expired(self) -> bool:
        """Return either True or False for the timer."""
        if self.timeout and self.timeout < (time.time() - self.start_time):
            return True  # we timed out
        else:
            # time remaining, or timeout is None which never expires
            return False


########################################################################
# SetupBlock
# contains the targets and timer returned from _common_setup
########################################################################
@dataclass
class SetupBlock:
    targets: set[str]
    timer: Timer


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
    _registry_lock = threading.Lock()
    _registry: dict[str, "SmartThread"] = {}

    # time_last_remote_update is initially set to
    # datetime(2000, 1, 1, 12, 0, 0) and the _registry_last_update is
    # initially set to datetime(2000, 1, 1, 12, 0, 1) which will ensure
    # that each thread will initially refresh their remote_array when
    # instantiated.
    _registry_last_update: datetime = datetime(2000, 1, 1, 12, 0, 1)

    ####################################################################
    # ConnectionStatusBlock
    # Each remote_array entry is a ConnectionStatusBlock which is used
    # to coordinate the various actions involved in satisfying a
    # send_msg, recv_msg, wait, resume, or sync request.
    ####################################################################
    @dataclass
    class ConnectionStatusBlock:
        remote_smart_thread: "SmartThread"
        status_lock: threading.Lock
        msg_q: queue.Queue[Any]
        event: threading.Event
        sync_event: threading.Event
        remote_msg_q: queue.Queue[Any] = None
        pair_status: PairStatus = PairStatus.NotReady
        code: Any = None
        wait_wait: bool = False
        sync_wait: bool = False
        wait_timeout_specified: bool = False
        deadlock: bool = False
        conflict: bool = False

    ####################################################################
    # __init__
    ####################################################################
    def __init__(self, *,
                 name: str,
                 target: Optional[Callable[..., Any]] = None,
                 args: Optional[tuple[...]] = None,
                 thread: Optional[threading.Thread] = None,
                 default_timeout: Optional[Union[int, float]] = None
                 ) -> None:
        """Initialize an instance of the SmartThread class.

        Args:
            name: name to be used to refer to this SmartThread. The name
                    may be the same as the threading.Thread name, but it
                    is not required that they be the same.
            target: specifies that a thread is to be created and started
                      with the given target. Mutually exclusive with the
                      *thread* specification. Note that the
                      threading.Thread will be created with *target*,
                      *args* if specified, and the *name*.
            args: args for the thread creation when *target* is
                    specified.
            thread: specifies the thread to use instead of the current
                      thread - needed when SmartThread is instantiated
                      in a class that inherits threading.Thread in which
                      case thread=self is required. Mutually exclusive
                      with *thread*.
            default_timeout: the timeout value to use when a request is
                               made and a timeout for the request is not
                               specified. If default_timeout is
                               specified, a value of zero or less will
                               be equivalent to None, meaning that a
                               default timeout will not be used.
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
                 result: the request will not timeout
              e. default_timeout = value above zero
                 request_timeout = value above zero
                 result: request timeout value will be used


        Raises:
            SmartThreadIncorrectNameSpecified: Attempted SmartThread
              instantiation with incorrect name of {name}.

            SmartThreadMutuallyExclusiveTargetThreadSpecified: Attempted
              SmartThread instantiation with both target and thread
              specified.

            SmartThreadArgsSpecificationWithoutTarget: Attempted
              SmartThread instantiation with args specified and without
              target specified.

        """
        self.specified_args = locals()

        self.status: ThreadStatus = ThreadStatus.Initializing

        if not isinstance(name, str):
            raise SmartThreadIncorrectNameSpecified(
                'Attempted SmartThread instantiation with incorrect name of '
                f'{name}.')
        self.name = name

        if target and thread:
            raise SmartThreadMutuallyExclusiveTargetThreadSpecified(
                'Attempted SmartThread instantiation with both target and '
                'thread specified.')

        if (not target) and args:
            raise SmartThreadArgsSpecificationWithoutTarget(
                'Attempted SmartThread instantiation with args specified and '
                'without target specified.')

        if target:  # caller wants a thread created
            if args:
                self.thread = threading.Thread(target=target,
                                               args=args,
                                               name=name)
            else:
                self.thread = threading.Thread(target=target,
                                               name=name)
        elif thread:  # caller provided the thread to use
            self.thread = thread
        else:  # caller is running on the thread to be used
            self.thread = threading.current_thread()

        self.default_timeout = default_timeout

        self.sync_request = False

        self.code = None

        # The following remote_array is used to keep track of who we
        # know and to process the various requests. The known remotes
        # are obtained from the SmartThread._registry as updated in
        # _refresh_remote_array.
        self.remote_array: dict[str, SmartThread.ConnectionStatusBlock] = {}

        # time_last_remote_update is initially set to
        # datetime(2000, 1, 1, 12, 0, 0) and the _registry_last_update
        # is initially set to datetime(2000, 1, 1, 12, 0, 1) which will
        # ensure that each thread will initially refresh their
        # remote_array when instantiated.
        self.time_last_remote_update: datetime = datetime(2000, 1, 1, 12, 0, 0)

        self.logger = logging.getLogger(__name__)

        # Set a flag to use to make it easier to determine whether debug
        # logging is enabled
        self.debug_logging_enabled = self.logger.isEnabledFor(logging.DEBUG)

        # register this new SmartThread to others can find us
        self._register()

        if self.thread.ident is None:  # if thread not yet started
            # indicate we are simply registered and waiting to be
            # started (as opposed to being not alive and stopped because
            # the thread failed)
            self.status = ThreadStatus.Registered
        else:  # thread is alive or possibly failed already
            # we will say alive for now and determine later if it has
            # failed
            self.status = ThreadStatus.Alive

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
                    parms += ', ' + f'{key}={item}'

        return f'{classname}({parms})'

    ####################################################################
    # register
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

        with SmartThread._registry_lock:
            self.logger.debug(f'{self.name} obtained _registry_lock, '
                              f'class name = {self.__class__.__name__}')

            # Remove any old entries
            self._clean_up_registry()

            # Add entry if not already present
            if self.name not in SmartThread._registry:
                SmartThread._registry[self.name] = self
                self.logger.debug(f'{self.name} registered')
            elif SmartThread._registry[self.name] != self:
                raise SmartThreadNameAlreadyInUse(
                    f'An entry for a SmartThread with name = {self.name} is '
                    'already registered for a different thread.')

            SmartThread._registry_last_update = datetime.utcnow()
            self.logger.debug(
                f'{self.name} did register update at UTC '
                f'{SmartThread._registry_last_update.strftime("%H:%M:%S.%f")}')

    ####################################################################
    # _clean_up_registry
    ####################################################################
    def _clean_up_registry(self) -> None:
        """Clean up any old not alive items in the registry.

        Raises:
            SmartThreadErrorInRegistry: Registry item with key {key} has
              non-matching item.name of {item.name}.

        Notes:
            1) Must be called holding _registry_lock

        """
        # Remove any old entries
        keys_to_del = []
        for key, item in SmartThread._registry.items():
            self.logger.debug(
                f'key = {key}, item = {item}, '
                f'item.thread.is_alive() = {item.thread.is_alive()}')
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
            self.logger.debug(f'{key} removed from registry')

        if changed:
            SmartThread._registry_last_update = datetime.utcnow()
            print_time = (SmartThread._registry_last_update
                          .strftime("%H:%M:%S.%f"))
            self.logger.debug(f'{self.name} did cleanup of registry at UTC '
                              f'{print_time}, deleted {keys_to_del}')

    ###########################################################################
    # _refresh_remote_array
    ###########################################################################
    def _refresh_remote_array(self) -> None:
        """Update the remote_array from the _registry.

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
            2) remote_array entry does not have flag set to indicate thread became not alive, but registry does have
               the flag set - simply set the flag in the remote_array entry - request will fail if remote is part of
               the request
            3) registry entry does not have a remote_array entry -
               remove remote_array entry

        """
        changed = False
        with SmartThread._registry_lock:
            # scan registry and adjust status
            for key, item in SmartThread._registry.items():
                saved_status = item.status
                if item.thread.is_alive():
                    item.status = ThreadStatus.Alive

                if saved_status != item.status:
                    changed = True

                if (key != self.name) and (key not in self.remote_array):
                    # we now add the remote_array entry for first time
                    if self.name in item.remote_array:
                        # remote already knows about us - use its status_lock

                        remote_cb = item.remote_array[self.name]
                        self.remote_array[key] = (
                            SmartThread.ConnectionStatusBlock(
                                remote_smart_thread=item,
                                status_lock=remote_cb.status_lock,
                                msg_q=queue.Queue(),
                                event=threading.Event(),
                                sync_event=threading.Event()
                            ))
                        local_cb = self.remote_array[key]
                        local_cb.remote_msg_q = remote_cb.msg_q
                        remote_cb.remote_msg_q = local_cb.msg_q
                        local_cb.pair_status = PairStatus.Ready
                        remote_cb.pair_status = PairStatus.Ready
                    else:
                        # we are first to get started - create a new
                        # status lock
                        self.remote_array[key] = (
                            SmartThread.ConnectionStatusBlock(
                                remote_smart_thread=item,
                                status_lock=threading.Lock(),
                                msg_q=queue.Queue(),
                                event=threading.Event(),
                                sync_event=threading.Event()
                            ))
                    changed = True

            # scan remote_array
            remote_array_deletion_list = []
            for key, item in self.remote_array.items():
                if key not in SmartThread._registry:
                    # entry was removed from the registry
                    remote_array_deletion_list.append(key)
                else:
                    if (item.remote_smart_thread
                            is not SmartThread._registry[key]):
                        raise SmartThreadRemoteSmartThreadMismatch(
                            f'{self.name} has id(item.remote_smart_thread) = '
                            f'{id(item.remote_smart_thread)} '
                            'and id(SmartThread._registry[key]) = '
                            f'{id(SmartThread._registry[key])}')
                    if (item.remote_smart_thread.thread
                            is not SmartThread._registry[key].thread):
                        raise SmartThreadRemoteThreadMismatch(
                            f'{self.name} has '
                            'id(item.remote_smart_thread.thread) = '
                            f'{id(item.remote_smart_thread.thread)} '
                            'and id(SmartThread._registry[key].thread) = '
                            f'{id(SmartThread._registry[key].thread)}')
                    # The following code checks to make sure the remote
                    # and us have the same shared items. Note that if
                    # the remote does not know about us yet, it will
                    # eventually discover we are here when it does a
                    # request that causes this method to get control.
                    # If the remote does know about us then it means
                    # that it should have the same shared items.
                    if self.name in item.remote_smart_thread.remote_array:
                        remote_cb = (item.remote_smart_thread
                                     .remote_array[self.name])
                        if item.status_lock is not remote_cb.status_lock:
                            raise SmartThreadStatusLockMismatch(
                                f'{self.name} has id(item.status_lock) = '
                                f'{id(item.status_lock)} and '
                                f'remote_cb.status_lock = '
                                f'{id(remote_cb.status_lock)}')

                        # if item.remote_msg_q:
                        if ((item.remote_msg_q is not remote_cb.msg_q)
                                or (remote_cb.remote_msg_q is not item.msg_q)):
                            raise SmartThreadRemoteMsgQMismatch(
                                f'{self.name} has id(item.remote_msg_q) = '
                                f'{id(item.remote_msg_q)}, '
                                'id(remote_cb.msg_q) = '
                                f'{id(remote_cb.msg_q)},'
                                'id(remote_cb.remote_msg_q) = '
                                f'{id(remote_cb.remote_msg_q)}, '
                                f'id(item.msg_q) = {id(item.msg_q)}')

            for key in remote_array_deletion_list:
                del self.remote_array[key]
                changed = True
                self.logger.debug(f'{key} removed from remote_array')

            if changed:
                SmartThread._registry_last_update = datetime.utcnow()
                self.time_last_remote_update = (SmartThread
                                                ._registry_last_update)
                print_time = (SmartThread._registry_last_update
                              .strftime("%H:%M:%S.%f"))
                self.logger.debug(
                    f'{self.name} updated registry and remote_array at UTC '
                    f'{print_time}')

    ####################################################################
    # start
    ####################################################################
    def start(self) -> None:
        """Start the thread.

        :Example: instantiate a SmartThread and start the thread

        >>> import scottbrian_utils.smart_thread as st
        >>> def f1() -> None:
        ...     print('f1 beta entered')
        >>> beta_smart_thread = SmartThread(name='beta', target=f1)
        >>> beta_smart_thread.start()
        f1 beta entered

        """
        self.status = ThreadStatus.Starting
        self.thread.start()
        if self.thread.is_alive():
            self.status = ThreadStatus.Alive

    ####################################################################
    # send_msg
    ####################################################################
    def send_msg(self,
                 targets: Union[str, set[str]],
                 msg: Any,
                 log_msg: Optional[str] = None,
                 timeout: Optional[Union[int, float]] = None) -> None:
        """Send a msg.

        Args:
            msg: the msg to be sent
            targets: names to send the message to
            log_msg: log message to issue
            timeout: number of seconds to wait for full queue to get
                       free slot

        Raises:
            SmartThreadSendMsgFailed: send_msg method unable to send the
                                    message because the send queue
                                    is full with the maximum
                                    number of messages.

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
        >>> beta_smart_thread.start()
        >>> alpha_smart_thread.send_msg('hello beta thread')
        >>> alpha_smart_thread.join(targets='beta')
        >>> print(alpha_smart_thread.recv_msg(remote='beta'))
        >>> print('mainline alpha exiting')
        mainline alpha entered
        f1 beta entered
        f1 beta exiting
        hi alpha
        mainline alpha exiting

        """
        # get SetupBlock with targets in a set and a timer object
        sb = self._common_setup(targets=targets, timeout=timeout)

        # if caller specified a log message to issue
        caller_info = ''
        if log_msg and self.debug_logging_enabled:
            caller_info = get_formatted_call_sequence(latest=1, depth=1)
            self.logger.debug(f'send_msg() entered: {self.name} -> {targets} '
                              f'{caller_info} {log_msg}')

        work_targets = sb.targets.copy()

        while work_targets:
            for remote in work_targets:
                # we need to handle the case where a remote we want to
                # send a message to is not yet registered and alive. We
                # call _refresh_remote_array to get the latest changes
                # but only if we see that the registry has changed
                # (_registry_last_update).
                if (self.time_last_remote_update
                        < SmartThread._registry_last_update):
                    self._refresh_remote_array()

                if remote in self.remote_array:
                    local_cb = self.remote_array[remote]
                    if not local_cb.remote_smart_thread.thread.is_alive():
                        # we need to check the status for Alive or
                        # Stopped before raising the not alive error
                        # since the thread could be registered but not
                        # yet started, in which case we need to give it
                        # more time
                        if (local_cb.remote_smart_thread.status
                                & (ThreadStatus.Alive
                                   | ThreadStatus.Stopped)):
                            raise SmartThreadRemoteThreadNotAlive(
                                f'{self.name} send_msg detected {remote} '
                                'thread is not alive.')
                    else:
                        try:
                            self.logger.info(
                                f'{self.name} sending message to {remote}')
                            # place message on remote q
                            local_cb.remote_msg_q.put(msg)

                            # start the while loop again with one less
                            # remote
                            work_targets.remove(remote)
                            break
                        except queue.Full:
                            self.logger.error('Raise SmartThreadSendMsgFailed')
                            raise SmartThreadSendMsgFailed(
                                f'{self.name} send_msg method unable to send '
                                f'the message because the send queue is full '
                                f'with the maximum number of messages.')

            if sb.timer.is_expired():
                self.logger.debug(f'{self.name} timeout of a send_msg() ')
                break

            time.sleep(0.2)

        # if caller specified a log message to issue
        if log_msg and self.debug_logging_enabled:
            self.logger.debug(f'send_msg() exiting: {self.name} -> '
                              f'{sb.targets} {caller_info} {log_msg}')

    ####################################################################
    # recv_msg
    ####################################################################
    def recv_msg(self,
                 remote: str,
                 log_msg: Optional[str] = None,
                 timeout: Optional[Union[int, float]] = None) -> Any:
        """Receive a msg.

        Args:
            remote: thread we expect to send us a message
            log_msg: log message to issue
            timeout: number of seconds to wait for message

        Returns:
            message unless timeout occurs

        Raises:
            SmartThreadRecvMsgTimedOut: recv_msg processing timed out
              waiting for a message to arrive.

        """
        timer = Timer(timeout=timeout, default_timeout=self.default_timeout)

        caller_info = ''
        if log_msg and self.debug_logging_enabled:
            caller_info = get_formatted_call_sequence(latest=1, depth=1)
            self.logger.debug(f'recv_msg() entered: {self.name} <- {remote} '
                              f'{caller_info} {log_msg}')

        while True:
            # we need to handle the case where a remote we want to recv
            # a message from is not yet registered and alive. We call
            # _refresh_remote_array to get the latest changes but only
            # if we see that the registry has changed
            # (_registry_last_update).
            if (self.time_last_remote_update
                    < SmartThread._registry_last_update):
                self._refresh_remote_array()

            if remote in self.remote_array:
                local_cb = self.remote_array[remote]
                # We don't check to ensure remote is alive since it may
                # have sent us a message and then became not alive. So,
                # we try to get the message first, and it it's not there
                # we will check to see whether the remote is alive.
                try:
                    self.logger.info(
                        f'{self.name} receiving msg from {remote}')
                    # recv message from remote
                    ret_msg = local_cb.msg_q.get()
                    break
                except queue.Empty:
                    pass

                # we need to check the status for Alive or Stopped
                # before raising the not alive error since the thread
                # could be registered but not yet started, in which case
                # we need to give it more time
                if ((not local_cb.remote_smart_thread.thread.is_alive())
                        and (local_cb.remote_smart_thread.status
                             & (ThreadStatus.Alive
                                | ThreadStatus.Stopped))):
                    raise SmartThreadRemoteThreadNotAlive(
                        f'{self.name} send_msg detected {remote} thread is '
                        'not alive.')

            if timer.is_expired():
                self.logger.error(
                    f'{self.name} raising SmartThreadRecvMsgTimedOut waiting '
                    f'for {remote} ')
                raise SmartThreadRecvMsgTimedOut(
                    f'recv_msg {self.name} timed out waiting for message from '
                    f'{remote}.')

            time.sleep(0.2)

        # if caller specified a log message to issue
        if log_msg and self.debug_logging_enabled:
            self.logger.debug(f'recv_msg() exiting: {self.name} <- {remote} '
                              f'{caller_info} {log_msg}')

        return ret_msg

    ###########################################################################
    # send_recv
    ###########################################################################
    def send_recv(self,
                  msg: Any,
                  remote: str,
                  log_msg: Optional[str] = None,
                  timeout: Optional[Union[int, float]] = None) -> Any:
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
        >>> thread.start()
        >>> a_smart_thread.send_msg('hello thread')
        >>> print(a_smart_thread.recv_msg())
        hi

        >>> thread.join()

        """
        timer = Timer(timeout=timeout, default_timeout=self.default_timeout)

        self.send_msg(msg, targets={remote}, log_msg=log_msg, timeout=timer.timeout)

        return self.recv_msg(remote=remote, log_msg=log_msg, timeout=timer.timeout)
    
    ####################################################################
    # msg_waiting
    ####################################################################
    def msg_waiting(self) -> str:
        """Determine whether a message is waiting, ready to be received.

        Returns:
            Name of remote whose message is waiting for us to pick up, empty string otherwise

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

        >>> smart_thread_app.start()
        >>> event.wait()
        >>> print(smart_thread.msg_waiting())
        True

        >>> print(smart_thread.recv_msg())
        goodbye

        """
        # We need to handle the case where a remote is ready to send us a message but we have not yet seen the remote,
        # So, we need to call _refresh_remote_array to get the latest changes
        # but only if we see that the registry has changed (_registry_last_update).
        if self.time_last_remote_update < SmartThread._registry_last_update:
            self._refresh_remote_array()

        for key, item in self.remote_array.items():
            if not item.msg_q.empty():
                return key

        return ""  # nothing found, return empty string

    ####################################################################
    # join
    ####################################################################
    def join(self, *,
             targets: Union[str, set[str]],
             log_msg: Optional[str] = None,
             timeout: Optional[Union[int, float]] = None) -> None:
        """Join with remote targets.

        Args:
            targets: thread names that are to be joined
            log_msg: log message to issue
            timeout: timeout to use instead of default timeout

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
        >>> beta_smart_thread.join()

        """
        # get SetupBlock with targets in a set and a timer object
        sb = self._common_setup(targets=targets, timeout=timeout)

        # if caller specified a log message to issue
        caller_info = ''
        if log_msg and self.debug_logging_enabled:
            caller_info = get_formatted_call_sequence(latest=1, depth=1)
            self.logger.debug(
                f'join() entered by {self.name} to join {sb.targets} '
                f'{caller_info} {log_msg}')

        work_targets = sb.targets.copy()

        while work_targets:
            for remote in work_targets:
                # we need to handle the case where a remote we want to
                # join is not in out remote_array. We call
                # _refresh_remote_array to get the latest changes but
                # only if we see that the registry has changed
                # (_registry_last_update).
                if (self.time_last_remote_update
                        < SmartThread._registry_last_update):
                    self._refresh_remote_array()

                if remote in self.remote_array:
                    local_cb = self.remote_array[remote]
                    # Note that if the remote thread was never started,
                    # the following join will raise an error. If the
                    # thread is eventually started, we currently have no
                    # way to detect that and react. We can only hope
                    # that a failed join in that case will be adequate.
                    if sb.timer.timeout:
                        local_cb.remote_smart_thread.thread.join(
                            timeout=sb.timer.timeout / len(work_targets))
                    else:
                        local_cb.remote_smart_thread.thread.join()

                    # we need to check to make sure the thread is not
                    # alive in case we timeout out
                    if not local_cb.remote_smart_thread.thread.is_alive():
                        # indicate remove from registry
                        local_cb.remote_smart_thread.status = (ThreadStatus
                                                               .Stopped)
                        # remove this thread from the registry
                        with SmartThread._registry_lock:
                            self._clean_up_registry()
                        self.logger.debug(
                            f'{self.name} did successful join of {remote}.')

                        # start the while loop again with one less remote
                        work_targets.remove(remote)
                        break

            if sb.timer.is_expired():
                self.logger.debug(f'{self.name} timeout of a join() ')
                self.logger.error(
                    f'{self.name} raising SmartThreadJoinTimedOut waiting '
                    f'for {work_targets} ')
                raise SmartThreadJoinTimedOut(
                    f'{self.name} timed out waiting for {work_targets}.')

            time.sleep(0.2)

        if log_msg and self.debug_logging_enabled:
            self.logger.debug(
                f'join() by {self.name} to join {sb.targets} exiting. '
                f'{caller_info} {log_msg}')

    ####################################################################
    # resume
    ####################################################################
    def resume(self, *,
               targets: Union[str, set[str]],
               log_msg: Optional[str] = None,
               timeout: Optional[Union[int, float]] = None,
               code: Optional[Any] = None) -> None:
        """Resume a waiting or soon to be waiting thread.

        Args:
            targets: names of threads that are to be resumed
            log_msg: log msg to log
            timeout: number of seconds to allow for ``resume()`` to complete
            code: code that waiter can retrieve with ``get_code()``

        Returns:
            * ``True`` if *timeout* was not specified, or if it was specified
              and the ``resume()`` request completed within the specified
              number of seconds.
            * ``False`` if *timeout* was specified and the ``resume()``
              request did not complete within the specified number of
              seconds.

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
        >>> beta_smart_thread.join()

        """
        # get SetupBlock with targets in a set and a timer object
        sb = self._common_setup(targets=targets, timeout=timeout)

        # if caller specified a log message to issue
        caller_info = ''
        if log_msg and self.debug_logging_enabled:
            code_msg = f' with code: {code}' if code else ''
            caller_info = get_formatted_call_sequence(latest=1, depth=1)
            self.logger.debug(f'resume() entered{code_msg} by {self.name} to '
                              f'resume {targets} {caller_info} {log_msg}')

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
        #    the event that the resume operates on. So, we will so
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

        work_targets = sb.targets.copy()

        while work_targets:
            for remote in work_targets:
                # we need to handle the case where a remote we want to
                # resume is not yet registered and alive. We call
                # _refresh_remote_array to get the latest changes but
                # only if we see that the registry has changed
                # (_registry_last_update).
                if (self.time_last_remote_update
                        < SmartThread._registry_last_update):
                    self._refresh_remote_array()

                if remote in self.remote_array:
                    local_cb = self.remote_array[remote]
                    if not local_cb.remote_smart_thread.thread.is_alive():
                        # we need to check the status for Alive or
                        # Stopped before raising the not alive error
                        # since the thread could be registered but not
                        # yet started, in which case we need to give it
                        # more time
                        if (local_cb.remote_smart_thread.status
                                & (ThreadStatus.Alive | ThreadStatus.Stopped)):
                            raise SmartThreadRemoteThreadNotAlive(
                                f'{self.name} resume() detected {remote} '
                                'thread is not alive.')
                    else:
                        if local_cb.pair_status == PairStatus.Ready:
                            with local_cb.status_lock:
                                remote_cb = (local_cb.remote_smart_thread
                                             .remote_array[self.name])
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
                                    if not (remote_cb.sync_event.is_set()
                                            or (remote_cb.conflict
                                                and remote_cb.sync_wait)):
                                        # wake remote thread and start
                                        # the while loop again with one
                                        # less remote
                                        remote_cb.sync_event.set()
                                        work_targets.remove(remote)
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
                                    if not (remote_cb.event.is_set()
                                            or (remote_cb.conflict
                                                and remote_cb.wait_wait)):

                                        # set the code, if one
                                        if code:
                                            remote_cb.code = code
                                        # wake remote thread and start
                                        # the while loop again with one
                                        # less remote
                                        remote_cb.event.set()
                                        work_targets.remove(remote)
                                        break

            if sb.timer.is_expired():
                self.logger.debug(f'{self.name} timeout of a resume() request')
                self.logger.error(
                    f'{self.name} raising SmartThreadResumeTimedOut waiting '
                    f'for {work_targets}')
                raise SmartThreadResumeTimedOut(
                    f'{self.name} timed out waiting for {work_targets}.')

            time.sleep(0.2)

        # if caller specified a log message to issue
        if log_msg and self.debug_logging_enabled:
            self.logger.debug(f'resume() by {self.name} to resume '
                              f'{sb.targets} exiting '
                              f'{caller_info} {log_msg}')

    ####################################################################
    # sync
    ####################################################################
    def sync(self, *,
             targets: Union[str, set[str]],
             log_msg: Optional[str] = None,
             timeout: Optional[Union[int, float]] = None):
        """Sync up with the remote threads.

        Each of the targets does a resume request to pre-resume the
        remote sync events, and then waits for each remote to resume
        their sync events. This ensures that each thread in the target
        set has reached the sync point before any thread moves forward
        from there.

        Args:
            targets: remote threads we will sync with
            log_msg: log msg for the log
            timeout: number of seconds to allow for sync to happen

        Raises:
            SmartThreadConflictDeadlockDetected: A ``sync()`` request
              was unable to complete becasue another thread was
              attempting a ``wait()`` request.

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
        >>> beta_thread.start()
        >>> alpha_smart_thread.sync(targets='beta')
        >>> alpha_smart_thread.join(targets='beta')
        >>> print('mainline alpha exiting')
        mainline alpha entered
        f2 beta entered
        f2 beta exiting
        mainline alpha exiting

        """
        # get SetupBlock with targets in a set and a timer object
        sb = self._common_setup(targets=targets, timeout=timeout)

        caller_info = ''
        if log_msg and self.debug_logging_enabled:
            caller_info = get_formatted_call_sequence(latest=1, depth=1)
            self.logger.debug(f'sync() entered by {self.name} to sync with '
                              f'{targets} {caller_info} {log_msg}')

        self.sync_request = True
        self.resume(targets=sb.targets,
                    timeout=sb.timer.timeout)
        work_targets = sb.targets.copy()

        for remote in work_targets:
            self.wait(remote=remote, timeout=sb.timer.timeout)

        self.sync_request = False
        if log_msg and self.debug_logging_enabled:
            self.logger.debug(f'sync() by {self.name} to sync with '
                              f'{sb.targets} exiting {caller_info} {log_msg}')

    ####################################################################
    # wait
    ####################################################################
    def wait(self, *,
             remote: str,
             log_msg: Optional[str] = None,
             timeout: Optional[Union[int, float]] = None) -> None:
        """Wait on event.

        Args:
            remote: name of remote that we expect to resume us
            log_msg: log msg to log
            timeout: number of seconds to allow for wait to complete

        Raises:
            SmartThreadWaitDeadlockDetected: Two threads are
              deadlocked in a ''wait()'', each waiting on the other to
              ``resume()`` their event.
            SmartThreadConflictDeadlockDetected: A sync request was made
              by thread {self.name} but remote thread {remote} detected
              deadlock instead which indicates that the remote thread
              did not make a matching sync request.

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
        >>> f1_thread.start()
        >>> alpha_smart_event.wait(remote='beta')
        >>> alpha_smart_event.join(targets='beta')

        """
        # get SetupBlock with targets in a set and a timer object
        sb = self._common_setup(targets=remote, timeout=timeout)

        caller_info = ''
        if log_msg and self.debug_logging_enabled:
            caller_info = get_formatted_call_sequence(latest=1, depth=1)
            self.logger.debug(f'wait() entered by {self.name} to wait for '
                              f'{remote} {caller_info} {log_msg}')

        while True:
            # we need to handle the case where a remote we want to wait
            # for is not yet registered and alive. We call
            # _refresh_remote_array to get the latest changes but only
            # if we see that the registry has changed
            # (_registry_last_update).
            if (self.time_last_remote_update
                    < SmartThread._registry_last_update):
                self._refresh_remote_array()

            if remote in self.remote_array:
                local_cb = self.remote_array[remote]
                # We don't check to ensure remote is alive since it may
                # have resumed and then became not alive. So, we try to
                # get the event checked first, and it it's not set then
                # we will check to see whether the remote is alive
                if sb.timer.timeout:
                    local_cb.wait_timeout_specified = True
                else:
                    local_cb.wait_timeout_specified = False

                if self.sync_request:
                    local_cb.sync_wait = True
                    if self.remote_array[remote].sync_event.is_set():
                        local_cb.sync_wait = False
                        local_cb.wait_timeout_specified = False

                        # be ready for next sync wait
                        local_cb.sync_event.clear()
                        break
                else:
                    local_cb.wait_wait = True
                    if self.remote_array[remote].event.is_set():
                        local_cb.wait_wait = False
                        local_cb.wait_timeout_specified = False

                        # be ready for next wait
                        local_cb.event.clear()
                        break

                # Check for error conditions first before checking
                # whether the remote is alive. If the remote detects a
                # deadlock or conflict issue, it will set the current
                # sides bit and then raise an error and will likely be
                # gone when we check. We want to raise the same error on
                # this side.

                # self.deadlock is set only by the remote. So, if
                # self.deadlock is True, then remote has already
                # detected the deadlock, set our flag, raised
                # the deadlock on its side, and is now possibly in a new
                # wait. If self.deadlock if False, and remote is waiting
                # and is not resumed then it will not be getting resumed
                # by us since we are also waiting. So, we set
                # self.remote.deadlock to tell it, and then we raise the
                # error on our side. But, we don't do this if the
                # self.remote.deadlock is already on as that suggests
                # that we already told remote and raised the error,
                # which implies that we are in a new wait and the remote
                # has not yet woken up to deal with the earlier
                # deadlock. We can simply ignore it for now.
                if not local_cb.remote_smart_thread.thread.is_alive():
                    # we need to check the status for Alive or Stopped
                    # before raising the not alive error since the
                    # thread could be registered but not yet started,
                    # in which case we need to give it more time
                    if (local_cb.remote_smart_thread.status
                            & (ThreadStatus.Alive | ThreadStatus.Stopped)):
                        raise SmartThreadRemoteThreadNotAlive(
                            f'{self.name} wait detected {remote} thread is not '
                            'alive.')
                else:
                    if local_cb.pair_status == PairStatus.Ready:
                        with local_cb.status_lock:
                            if self.sync_request:
                                if local_cb.sync_event.is_set():
                                    local_cb.sync_wait = False
                                    local_cb.wait_timeout_specified = False

                                    # be ready for next sync wait
                                    local_cb.sync_event.clear()
                                    break
                            else:
                                if local_cb.event.is_set():
                                    local_cb.wait_wait = False
                                    local_cb.wait_timeout_specified = False

                                    # be ready for next wait
                                    local_cb.event.clear()
                                    break

                            remote_cb = (local_cb.remote_smart_thread
                                         .remote_array[self.name])
                            if not (local_cb.wait_timeout_specified
                                    or remote_cb.wait_timeout_specified
                                    or local_cb.deadlock
                                    or local_cb.conflict):
                                # the following checks apply to both
                                # sync_wait and wait_wait
                                if (remote_cb.sync_wait
                                        and not (remote_cb.sync_event.is_set()
                                                 or remote_cb.conflict)):
                                    remote_cb.conflict = True
                                    local_cb.conflict = True
                                    self.logger.debug(f'{self.name} detected '
                                                      'conflict with '
                                                      f'{remote}')
                                elif (remote_cb.wait_wait
                                        and not (local_cb.event.is_set()
                                                 or remote_cb.deadlock
                                                 or remote_cb.conflict)):
                                    remote_cb.deadlock = True
                                    local_cb.deadlock = True
                                    self.logger.debug(f'{self.name} detected '
                                                      'deadlock with '
                                                      f'{remote}')

                            if local_cb.conflict:
                                local_cb.wait_wait = False
                                local_cb.conflict = False
                                local_cb.wait_timeout_specified = False
                                self.logger.debug(
                                    f'{self.name} raising '
                                    'SmartThreadConflictDeadlockDetected')
                                raise SmartThreadConflictDeadlockDetected(
                                    'A sync request was made by thread '
                                    f'{self.name} but remote thread '
                                    f'{remote} detected deadlock instead '
                                    'which indicates that the remote '
                                    'thread did not make a matching sync '
                                    'request.')

                            if local_cb.deadlock:
                                local_cb.wait_wait = False
                                local_cb.deadlock = False
                                local_cb.wait_timeout_specified = False
                                self.logger.debug(
                                    f'{self.name} raising '
                                    'SmartThreadWaitDeadlockDetected')
                                raise SmartThreadWaitDeadlockDetected(
                                    'Both threads are deadlocked, each '
                                    'waiting on the other to resume their '
                                    'event.')

            if sb.timer.is_expired():
                if remote in self.remote_array:
                    self.logger.error(
                        f'{self.name} raising SmartThreadWaitTimedOut waiting '
                        f'for {remote} with '
                        f'self.remote_array[remote].wait_wait '
                        f'= {self.remote_array[remote].wait_wait} and '
                        f'self.remote_array[remote].sync_wait '
                        f'= {self.remote_array[remote].sync_wait}')
                    self.remote_array[remote].sync_wait = False
                    self.remote_array[remote].wait_wait = False
                    self.remote_array[remote].wait_timeout_specified = False
                else:
                    self.logger.error(
                        f'{self.name} raising SmartThreadWaitTimedOut waiting '
                        f'for {remote} which is not found in the '
                        'remote_array.')

                raise SmartThreadWaitTimedOut(
                    f'recv_msg {self.name} timed out waiting for resume from '
                    f'{remote}.')

            time.sleep(0.2)

        if log_msg and self.debug_logging_enabled:
            self.logger.debug(
                f'wait() by {self.name} to wait for {remote} exiting '
                f' {caller_info} {log_msg}')

    ####################################################################
    # _common_setup
    ####################################################################
    def _common_setup(self, *,
                      targets: Union[str, set[str]],
                      timeout: Optional[Union[int, float]] = None
                      ) -> SetupBlock:
        """Do common setup for each request.

        Args:
            targets: remote threads for the request
            timeout: number of seconds to allow for request completion

        """
        timer = Timer(timeout=timeout, default_timeout=self.default_timeout)
        self.verify_thread_is_current()
        if isinstance(targets, str):
            targets = {targets}

        return SetupBlock(targets=targets, timer=timer)

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
            self.logger.debug(f'{self.name } raising '
                              'SmartThreadDetectedOpFromForeignThread. '
                              f'self.thread is {self.thread}, '
                              'threading.current_thread() is '
                              f'{threading.current_thread()}')
            raise SmartThreadDetectedOpFromForeignThread(
                'SmartThread services must be called from the thread '
                'that was originally assigned during instantiation of '
                'SmartThread. '
                f'Call sequence: {get_formatted_call_sequence(1,2)}')
