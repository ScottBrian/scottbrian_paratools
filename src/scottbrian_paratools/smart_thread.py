"""Module smart_thread.

===========
SmartThread
===========

The SmartThread class provides enhanced functionality for parallel processing. Support is provided to detect when a
thread has terminated and will thus be unable to complete a task that another thread is waiting for. Also, a
communications facility is provided to allow threads to talk among themselves.

:Example: create a SmartThread for alpha and beta

>>> import scottbrian_paratools.smart_thread as st
>>> def f1() -> None:
...     print('f1 beta entered')
...     beta_thread.send_msg(msg='hi alpha, this is beta', remote='alpha')
...     beta_thread.wait('remote=alpha')
...     print('f1 beta exiting')
>>> print('mainline entered')
>>> alpha_thread = st.SmartThread(name='alpha')
>>> beta_thread = st.SmartThread(name='beta', target=f1)
>>> msg_from_beta=alpha_thread.recv_msg(target='beta')
>>> print(msg_from_beta)
>>> alpha_thread.resume(remote='beta')
>>> alpha_thread.join(remote='beta')
>>> print('mainline exiting')
mainline entered
f1 beta entered
hi alpha, this is beta
f1 beta exiting
mainline exiting


The smart_thread module contains:

    1) SmartThread class with methods:

       a. wait
       b. resume
       c. sync
       d. send_msg
       e. recv_msg

"""
###############################################################################
# Standard Library
###############################################################################
from dataclasses import dataclass
from enum import Enum
import logging
import queue
import threading
import time
from typing import Any, Callable, Final, Optional, Type, TYPE_CHECKING, Union

###############################################################################
# Third Party
###############################################################################

###############################################################################
# Local
###############################################################################
from scottbrian_utils.diag_msg import get_formatted_call_sequence


###############################################################################
# SmartThread class exceptions
###############################################################################
class SmartThreadError(Exception):
    """Base class for exceptions in this module."""
    pass


class SmartThreadAlreadyPairedWithRemote(SmartThreadError):
    """SmartThread exception for pair_with that is already paired."""
    pass


class SmartThreadDetectedOpFromForeignThread(SmartThreadError):
    """SmartThread exception for attempted op from unregistered thread."""
    pass


class SmartThreadErrorInRegistry(SmartThreadError):
    """SmartThread exception for registry error."""


class SmartThreadIncorrectNameSpecified(SmartThreadError):
    """SmartThread exception for a name that is not a str."""


class SmartThreadNameAlreadyInUse(SmartThreadError):
    """SmartThread exception for using a name already in use."""
    pass


class SmartThreadNotPaired(SmartThreadError):
    """SmartThread exception for alpha or beta thread not registered."""
    pass


class SmartThreadPairWithSelfNotAllowed(SmartThreadError):
    """SmartThread exception for pair_with target is self."""


class SmartThreadPairWithTimedOut(SmartThreadError):
    """SmartThread exception for pair_with that timed out."""


class SmartThreadRemoteThreadNotAlive(SmartThreadError):
    """SmartThread exception for remote thread not alive."""


class SmartThreadRemotePairedWithOther(SmartThreadError):
    """SmartThread exception for pair_with target already paired."""


class SmartThreadRemoteNotRegisteredTimeout(SmartThreadError):
    """SmartThread exception for timeout waiting for remote to register."""


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


class SmartThreadRecvTimedOut(SmartThreadError):
    """SmartThread exception for timeout waiting for message."""
    pass


class SmartThreadSendFailed(SmartThreadError):
    """SmartThread exception failure to send message."""
    pass


class SmartThreadRemoteNotPairedTimeout(SmartThreadError):
    """SmartThread exception timed out waiting for remote remote to pair with us."""
    pass


class SmartThreadMutuallyExclusiveTargetThreadSpecified(SmartThreadError):
    """SmartThread exception mutually exclusive target and thread were both specified."""
    pass


class SmartThreadRemoteThreadNotRegistered(SmartThreadError):
    """SmartThread exception remote thread is alive and exists in remote_array but not in _registry."""
    pass


class SmartThreadRemoteSmartThreadMismatch(SmartThreadError):
    """SmartThread exception remote_array SmartThread does not match registry SmartThread."""
    pass


class SmartThreadRemoteThreadMismatch(SmartThreadError):
    """SmartThread exception remote_array SmartThread.thread does not match registry SmartThread.thread."""
    pass


class SmartThreadSharedBlockMismatch(SmartThreadError):
    """SmartThread exception remote_array shared block does not match remote.remote_array shared block."""
    pass


class SmartThreadRemoteMsgQMismatch(SmartThreadError):
    """SmartThread exception remote_array remote msg_q does not match remote.remote_array msg_q."""
    pass

ThreadStatus = Enum('ThreadStatus',
                    'Initializing '
                    'Registered '
                    'Starting '
                    'Alive '
                    'Stopped ')

PairStatus = Enum('PairStatus',
                  'NotReady '
                  'Ready ')

###############################################################################
# SmartThread class
###############################################################################
class SmartThread:
    """Provides a connection to one or more threads."""

    ###########################################################################
    # Constants
    ###########################################################################
    pair_with_TIMEOUT: Final[int] = 60
    register_TIMEOUT: Final[int] = 30
    MAX_MSGS_DEFAULT: Final[int] = 16

    ###########################################################################
    # Registry
    ###########################################################################
    # The _registry is a dictionary of SmartClass instances keyed by the SmartThread name.
    _registry_lock = threading.Lock()
    _registry: dict[str, "SmartThread"] = {}
    _registry_last_update: float = 0.0

    ###########################################################################
    # SharedPairStatus Data Class
    ###########################################################################
    @dataclass
    class SharedPairBlock:
        """Shared area for status between paired SmartThread objects."""
        status_lock = threading.Lock()
        sync_cleanup = False

    @dataclass
    class ConnectionStatusBlock:
        remote_smart_thread: "SmartThread"
        shared_pair_block: "SmartThread.SharedPairBlock"
        msg_q: queue.Queue[Any] = queue.Queue()
        remote_msg_q: queue.Queue[Any] = None
        pair_status: PairStatus = PairStatus.NotReady
        event: threading.Event = threading.Event()
        code: Any = None
        wait_wait: bool = False
        sync_wait: bool = False
        wait_timeout_specified: bool = False
        deadlock: bool = False
        conflict: bool = False

    ###########################################################################
    # __init__
    ###########################################################################
    def __init__(self, *,
                 name: str,
                 target: Optional[Callable[..., Any]] = None,
                 thread: Optional[threading.Thread] = None,
                 default_timeout: Optional[float] = None
                 ) -> None:
        """Initialize an instance of the SmartThread class.

        Args:
            name: name to be used to refer to this SmartThread
            target: specifies that a thread is to be created and started
                      with the given target. Mutually exclusive with
                      thread specification.
            thread: specifies the thread to use instead of the current
                      thread - needed when SmartThread is instantiated in a
                      class that inherits threading.Thread in which case
                      thread=self is required. Mutually exclusive with
                      thread specification.
            default_timeout: There are four possible timeout specifications:
                               a. default_timeout = None, request timeout = None
                                      results in no timeout
                               b. default_timeout = None, request timeout = value
                                      results in request timeout being used
                               c. default_timeout = value, request_timeout = None
                                      results in default_timeout being used on a request
                               d. default_timeout = value, request_timeout = value
                                      results in request timeout being used


        Raises:
            SmartThreadIncorrectNameSpecified: Attempted SmartThread instantiation
                                      with incorrect name of {name}.

        """
        self.status: ThreadStatus = ThreadStatus.Initializing
        if not isinstance(name, str):
            raise SmartThreadIncorrectNameSpecified(
                'Attempted SmartThread instantiation '
                f'with incorrect name of {name}.')
        self.name = name

        if target and thread:
            raise SmartThreadMutuallyExclusiveTargetThreadSpecified(
                'Attempted SmartThread instantiation '
                'with both target and thread specified.')

        if target:
            self.thread = threading.Thread(target=target)
        elif thread:
            self.thread = thread
        else:
            self.thread = threading.current_thread()

        self.default_timeout = default_timeout

        self.remote: Optional[SmartThread.ConnectionStatusBlock] = None
        self.remote_array: dict[str, SmartThread.ConnectionStatusBlock] = {}  # known remotes from SmartThread._registry

        # remote_array_last_update is initially set to -1.0 and the _registry_last_update is initially set to 0.0
        # which will cause each thread to initially refresh their remote_array when instantiated.
        self.remote_array_last_update: float = -1.0  # last time that remote_array were refreshed

        self.logger = logging.getLogger(__name__)
        self.debug_logging_enabled = self.logger.isEnabledFor(logging.DEBUG)

        self._register()

        self.status = ThreadStatus.Registered

    ###########################################################################
    # repr
    ###########################################################################
    def __repr__(self) -> str:
        """Return a representation of the class.

        Returns:
            The representation as how the class is instantiated

        :Example: instantiate a SmartThread and call repr

        >>> import scottbrian_paratools.smart_event as st
        >>> smart_thread = SmartThread(name='alpha')
        >>> repr(smart_thread)
        SmartThread(name="alpha")

        """
        if TYPE_CHECKING:
            __class__: Type[SmartThread]
        classname = self.__class__.__name__
        parms = f'name="{self.name}"'

        return f'{classname}({parms})'

    ###########################################################################
    # register
    ###########################################################################
    def _register(self) -> None:
        """Register SmartThread in the class registry.

        Raises:
            SmartThreadIncorrectNameSpecified: The name for SmartThread must be of type
                                      str.
            SmartThreadNameAlreadyInUse: An entry for a SmartThread with name = *name*
                                is already registered and paired with
                                *remote name*.

        Notes:
            1) Any old entries for SmartThreads whose threads are not alive
               are removed when this method is called by calling
               _clean_up_registry().
            2) Once a thread become not alive, it can not be resurrected.
               The SmartThread is bound to the thread it starts with. If the
               remote SmartThread thread that the SmartThread is paired with
               becomes not alive, we allow this SmartThread to pair with a new
               SmartThread on a new thread.

        """
        # Make sure name is valid
        if not isinstance(self.name, str):
            raise SmartThreadIncorrectNameSpecified(
                'The name for SmartThread must be of type str.')

        with SmartThread._registry_lock:
            self.logger.debug(f'_registry_lock obtained, '
                              f'name = {self.name}, class name = {self.__class__.__name__}')

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

            SmartThread._registry_last_update = time.time()
            self.remote_array_last_update = SmartThread._registry_last_update

    ###########################################################################
    # _clean_up_registry
    ###########################################################################
    def _clean_up_registry(self) -> None:
        """Clean up any old not alive items in the registry.

        Raises:
            SmartThreadErrorInRegistry: Registry item with key {key} has non-matching
                             item.name of {item.name}.

        Notes:
            1) Must be called holding _registry_lock

        """
        # Remove any old entries
        keys_to_del = []
        for key, item in SmartThread._registry.items():
            self.logger.debug(f'key = {key}, item = {item}, item.thread.is_alive() = {item.thread.is_alive()}')
            if ((item.status == ThreadStatus.Alive or item.status == ThreadStatus.Stopped)
                    and not item.thread.is_alive()):
                keys_to_del.append(key)

            if key != item.name:
                raise SmartThreadErrorInRegistry(f'Registry item with key {key} '
                                                f'has non-matching item.name '
                                                f'of {item.name}.')

        for key in keys_to_del:
            del SmartThread._registry[key]
            self.logger.debug(f'{key} removed from registry')

    ###########################################################################
    # _refresh_remote_array
    ###########################################################################
    def _refresh_remote_array(self) -> None:
        """Update the remote_array based on the current state of the _registry.

        Notes:
            1) A thread is registered during initialization and will initially not be alive until started.
            2) If a request is made that includes a yet to be registered thread, or one that is not yet alive, the
               request will loop until the remote thread becomes registered and alive.
            3) After a thread is registered and is alive, if it fails and become not alive, it will remain in the
               registry until with an flag set to indicate it was once alive. It will be removed when a join is done.
               This flag will allow a request to know whether to wait for the thread to become alive, or to raise
               an error for an attempted request on a thread that is no longer alive.
            4) The remote_array will simply mirror what is in the registry.

        Error cases:
            1) remote_array thread and registry thread do not match
            2) remote_array shared_pair_block does not match remote shared_pair_block


        Expected cases:
            1) remote_array does not have a registry entry - add the registry entry to the remote array and get a
               shared_pair_block
            2) remote_array entry does not have flag set to indicate thread became not alive, but registry does have
               the flag set - simply set the flag in the remote_array entry - request will fail if remote is part of
               the request
            3) registry entry does not have a remote_array entry - join was done - remove remote_array entry - request
               will fail if the remote was part of the request

        """

        # class ConnectionStatusBlock:
        #     remote_smart_thread: "SmartThread"
        #     shared_pair_block: "SmartThread.SharedPairBlock"
        #     msg_q: queue.Queue[Any] = queue.Queue()
        #     remote_msg_q: queue.Queue[Any] = None
        #     pair_status: PairStatus = PairStatus.NotReady
        #     event: threading.Event = threading.Event()
        #     code: Any = None
        #     wait_wait: bool = False
        #     sync_wait: bool = False
        #     wait_timeout_specified: bool = False
        #     deadlock: bool = False
        #     conflict: bool = False
        with SmartThread._registry_lock:
            # scan registry and adjust status
            for key, item in SmartThread._registry.items():
                if item.thread.is_alive():
                    item.status = ThreadStatus.Alive
                elif item.status == ThreadStatus.Alive:
                    item.status = ThreadStatus.Stopped

                if key not in self.remote_array:
                    # we now add the remote_array entry for first time
                    if self.name in item.remote_array:  # remote already knows about us - use its shared_pair_block
                        self.remote_array[key] = SmartThread.ConnectionStatusBlock(
                            remote_smart_thread=item,
                            shared_pair_block=item.remote_array[self.name].shared_pair_block)
                    else:  # we are first to get started - create a new shared_pair_block
                        self.remote_array[key] = SmartThread.ConnectionStatusBlock(
                            remote_smart_thread=item,
                            shared_pair_block=SmartThread.SharedPairBlock())

            # scan remote_array
            remote_array_deletion_list = []
            for key, item in self.remote_array.items():
                if key not in SmartThread._registry:  # entry was removed from the registry
                    remote_array_deletion_list.append(key)
                else:
                    if item.remote_smart_thread is not SmartThread._registry[key]:
                        raise SmartThreadRemoteSmartThreadMismatch(
                            f'{self.name} has id(item.remote_smart_thread) {id(item.remote_smart_thread)} '
                            f'and id(SmartThread._registry[key]) {id(SmartThread._registry[key])}')
                    if item.remote_smart_thread.thread is not SmartThread._registry[key].thread:
                        raise SmartThreadRemoteThreadMismatch(
                            f'{self.name} has id(item.remote_smart_thread.thread) '
                            f'{id(item.remote_smart_thread.thread)} '
                            f'and id(SmartThread._registry[key].thread) {id(SmartThread._registry[key].thread)}')
                    if self.name in item.remote_smart_thread.remote_array:
                        if (item.shared_pair_block
                                is not item.remote_smart_thread.remote_array[self.name].shared_pair_block):
                            raise SmartThreadSharedBlockMismatch(
                                f'{self.name} has id(item.shared_pair_block) {id(item.shared_pair_block)} '
                                f'and id(item.remote_smart_thread.remote_array[self.name].shared_pair_block) '
                                f'{id(item.remote_smart_thread.remote_array[self.name].shared_pair_block)}')

                        if item.remote_msg_q:
                            if item.remote_msg_q is not item.remote_smart_thread.remote_array[self.name].msg_q:
                                raise SmartThreadRemoteMsgQMismatch(
                                    f'{self.name} has id(item.remote_msg_q) {id(item.remote_msg_q)} '
                                    f'and id(item.remote_smart_thread.remote_array[self.name].msg_q) '
                                    f'{id(item.remote_smart_thread.remote_array[self.name].msg_q)}')
                        item.remote_msg_q = item.remote_smart_thread.remote_array[self.name].msg_q
                        # we may have a newly alive entry or one that has been alive and already paired
                        if item.remote_smart_thread.thread.is_alive():
                            item.pair_status = PairStatus.Ready
                        else:
                            item.pair_status = PairStatus.NotReady

        self.remote_array_last_update = time.time()

    ###########################################################################
    # send_msg
    ###########################################################################
    def send_msg(self,
                 msg: Any,
                 target_set: Union[str, set[str]],
                 log_msg: Optional[str] = None,
                 timeout: Optional[Union[int, float]] = 10) -> None:
        """Send a msg.

        Args:
            msg: the msg to be sent
            target_set: names to send the message to
            timeout: number of seconds to wait for full queue to get free slot

        Raises:
            SmartThreadSendFailed: send_msg method unable to send the
                                    message because the send queue
                                    is full with the maximum
                                    number of messages.

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
        start_time = time.time()  # start the clock

        # if caller specified a log message to issue
        caller_info = ''
        if log_msg and self.debug_logging_enabled:
            caller_info = get_formatted_call_sequence(latest=1, depth=1)
            self.logger.debug(f'send_msg() entered: {self.name} -> {target_set} {caller_info} {log_msg}')

        self.verify_current_remote()

        if not isinstance(target_set, set):
            target_set = {target_set}

        work_target_set = target_set
        self._refresh_remote_array()

        while work_target_set:
            for remote in work_target_set:
                if self.remote_array_last_update < SmartThread._registry_last_update:
                    self._refresh_remote_array()

                if remote in self.remote_array and self.remote_array[remote].remote_smart_thread.thread.is_alive():
                    try:
                        self.logger.info(f'{self.name} sending message to {remote}')
                        self.remote_array[remote].remote_msg_q.put(msg, timeout=timeout)  # place message on remote q
                        work_target_set.remove(remote)
                        break  # start the while loop again with one less remote
                    except queue.Full:
                        self.logger.error('Raise SmartThreadSendFailed')
                        raise SmartThreadSendFailed(f'{self.name} send_msg method unable to send the '
                                                    'message because the send queue '
                                                    'is full with the maximum '
                                                    'number of messages.')

            if timeout and (timeout < (time.time() - start_time)):
                self.logger.debug(f'{self.name} timeout of a send_msg() ')
                break

            time.sleep(0.2)

        # if caller specified a log message to issue
        if log_msg and self.debug_logging_enabled:
            self.logger.debug(f'send_msg() exiting: {self.name} -> {target_set} {caller_info} {log_msg}')

    ###########################################################################
    # recv_msg
    ###########################################################################
    def recv_msg(self,
                 remote: str,
                 log_msg: Optional[str] = None,
                 timeout: Optional[Union[int, float]] = 10) -> Any:
        """Receive a msg.

        Args:
            timeout: number of seconds to wait for message

        Returns:
            message unless timeout occurs

        Raises:
            SmartThreadRecvTimedOut: recv_msg processing timed out
                                      waiting for a message to
                                      arrive.

        """
        caller_info = ''
        if log_msg and self.debug_logging_enabled:
            caller_info = get_formatted_call_sequence(latest=1, depth=1)
            self.logger.debug(f'recv_msg() entered: {self.name} <- {remote} '
                              f'{caller_info} {log_msg}')

        try:
            self.logger.info(f'{self.name} receiving msg from {remote}')
            self.logger.debug(f'recv_msg id(self.msg_q) = {id(self.msg_q)}')
            ret_msg = self.msg_q.get(timeout=timeout)  # recv message from remote
        except queue.Empty:
            self.logger.error(f'{self.name} raising SmartThreadRecvTimedOut waiting for {remote} ')
            raise SmartThreadRecvTimedOut(f'recv_msg {self.name} timed out waiting for message from {remote}.')
        # if caller specified a log message to issue
        if log_msg and self.debug_logging_enabled:
            self.logger.debug(f'recv_msg() exiting: {self.name} <- {remote} {caller_info} {log_msg}')

        return ret_msg

    ###########################################################################
    # send_recv
    ###########################################################################
    def send_recv(self,
                  msg: Any,
                  remote: str,
                  log_msg: Optional[str] = None,
                  timeout: Optional[Union[int, float]] = 30) -> Any:
        """Send a message and wait for reply.

        Args:
            msg: the msg to be sent
            timeout: Number of seconds to wait for reply

        Returns:
              message unless send q is full or timeout occurs during recv

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
        self.send_msg(msg, remote=remote, log_msg=log_msg, timeout=timeout)
        return self.recv_msg(remote=remote, log_msg=log_msg, timeout=timeout)
    
    ###########################################################################
    # msg_waiting
    ###########################################################################
    def msg_waiting(self) -> bool:
        """Determine whether a message is waiting, ready to be received.

        Returns:
            True if message is ready to receive, False otherwise

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
        return not self.msg_q.empty()



    ###########################################################################
    # join
    ###########################################################################
    def join(self, *,
             target_set: Union[str, set[str]],
             log_msg: Optional[str] = None,
             timeout: Optional[float] = None) -> None:
        """Join with remote targets.

        Args:
            target_set: thread names that are to be joined

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
        # if caller specified a log message to issue
        caller_info = ''
        if log_msg and self.debug_logging_enabled:
            caller_info = get_formatted_call_sequence(latest=1, depth=1)
            self.logger.debug(f'join() entered by {self.name} to join {remote} '
                              f'{caller_info} {log_msg}')
        self.verify_current_remote()

        if not isinstance(target_set, list):
            target_set = [target_set]

        for remote in target_set:
            remote_status = 'unknown'
            with SmartThread._registry_lock:
                if remote in SmartThread._registry:
                    SmartThread._registry[remote].status = ThreadStatus.Joining
                    SmartThread._registry[remote].thread.join(timeout=timeout)
                    if SmartThread._registry[remote].thread.is_alive():
                        SmartThread._registry[remote].status = ThreadStatus.Alive
                        remote_status = 'alive'
                    else:
                        SmartThread._registry[remote].status = ThreadStatus.Stopped
                        remote_status = 'not alive'
                else:
                    remote_status = 'unregistered'

                self._clean_up_registry()

            if log_msg and self.debug_logging_enabled:
                self.logger.debug(f'join() by {self.name} to join {remote} result remote status = {remote_status}.')

        if log_msg and self.debug_logging_enabled:
            self.logger.debug(f'join() by {self.name} to join {target_set} exiting. '
                              f'{caller_info} {log_msg}')

    ###########################################################################
    # resume
    ###########################################################################
    def resume(self, *,
               target_set: Union[str, set[str]],
               log_msg: Optional[str] = None,
               timeout: Optional[Union[int, float]] = None,
               code: Optional[Any] = None) -> bool:
        """Resume a waiting or soon to be waiting thread.

        Args:
            remote: name of thread that is to be resumed 
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
        start_time = time.time()  # start the clock

        timeout = None if (timeout and timeout <= 0) else timeout

        self.verify_current_remote()

        # if caller specified a log message to issue
        caller_info = ''
        if log_msg and self.debug_logging_enabled:
            code_msg = f' with code: {code} ' if code else ' '
            caller_info = get_formatted_call_sequence(latest=1, depth=1)
            self.logger.debug(f'resume() entered{code_msg} by {self.name} to resume {remote} '
                              f'{caller_info} {log_msg}')

        final_ret_code = True

        if not isinstance(target_set, list):
            target_set = [target_set]

        for remote in target_set:
            self.pair(remote=remote, start_time=start_time, timeout=timeout)

            ###############################################################
            # Cases where we loop until remote is ready:
            # 1) Remote waiting and event already resumed. This is a case
            #    where the remote was previously resumed and has not yet
            #    been given control to exit the wait. If and when that
            #    happens, this resume will complete as a pre-resume.
            # 2) Remote waiting and deadlock. The remote was flagged as
            #    being in a deadlock and has not been given control to
            #    raise the SmartThreadWaitDeadlockDetected error. The remote could
            #    recover, in which case this resume will complete,
            #    or the thread could become inactive, in which case
            #    resume will see that and raise (via check_remote
            #    method) the SmartThreadRemoteThreadNotAlive error.
            # 3) Remote not waiting and event resumed. This case
            #    indicates that a resume was previously done ahead of the
            #    wait as a pre-resume. In that case an eventual wait is
            #    expected to be requested by the remote thread to clear
            #    the flag at which time this resume will succeed in doing a
            #    pre-resume.
            ###############################################################

            ###############################################################
            # Cases where we do the resume:
            # 1) Remote is waiting, event is not resumed, and neither
            #    deadlock nor conflict flags are True. This is the most
            #    expected case in a normally running system where the
            #    remote put something in action and is now waiting on a
            #    response (via the resume) that the action is complete.
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
            while True:
                with self.status.status_lock:
                    if not (self.remote.event.is_set()
                            or self.remote.deadlock
                            or (self.remote.conflict and self.remote.wait_wait)):
                        if code:  # if caller specified a code for remote thread
                            self.remote.code = code
                        self.remote.event.set()  # wake remote thread
                        ret_code = True
                        break

                    if timeout and (timeout < (time.time() - start_time)):
                        self.logger.debug(f'{self.name} timeout of a resume() '
                                          'request with self.remote.event.is_set() = '
                                          f'{self.remote.event.is_set()} and '
                                          'self.remote.deadlock = '
                                          f'{self.remote.deadlock}')
                        ret_code = False
                        break

                time.sleep(0.2)
            final_ret_code = final_ret_code and ret_code
        # if caller specified a log message to issue
        if log_msg and self.debug_logging_enabled:
            self.logger.debug(f'resume() by {self.name} to resume {remote} exiting with ret_code {ret_code} '
                              f'{caller_info} {log_msg}')
        return final_ret_code

    ###########################################################################
    # sync
    ###########################################################################
    def sync(self, *,
             target_set: Union[str, set[str]],
             log_msg: Optional[str] = None,
             timeout: Optional[Union[int, float]] = None) -> bool:
        """Sync up with the remote thread via a matching sync request.

        A ``sync()`` request made by the current thread waits until the remote
        thread makes a matching ``sync()`` request at which point both
        ``sync()`` requests are completed and control returned.

        Args:
            remote: remote SmartThread we will sync with
            log_msg: log msg to log
            timeout: number of seconds to allow for sync to happen

        Returns:
            * ``True`` if **timeout** was not specified, or if it was
              specified and the ``sync()`` request completed within the
              specified number of seconds.
            * ``False`` if **timeout** was specified and the ``sync()``
              request did not complete within the specified number of
              seconds.

        Raises:
            SmartThreadConflictDeadlockDetected: A ``sync()`` request was made by one
                                        thread and a ``wait()`` request was
                                        made by the other thread.

        Notes:
            1) If one thread makes a ``sync()`` request without **timeout**
               specified, and the other thread makes a ``wait()`` request to
               an event that was not **pre-resumed**, also without **timeout**
               specified, then both threads will recognize and raise a
               **SmartThreadConflictDeadlockDetected** error. This is needed since
               neither the ``sync()`` request nor the ``wait()`` request has
               any chance of completing. The ``sync()`` request is waiting for
               a matching ``sync()`` request and the ``wait()`` request is
               waiting for a matching ``resume()`` request.
            2) If one thread makes a ``sync()`` request and the other thread
               becomes not alive, the ``sync()`` request raises a
               **SmartThreadRemoteThreadNotAlive** error.

        :Example: instantiate a SmartThread and sync the threads

        >>> import scottbrian_paratools.smart_event as st
        >>> import threading
        >>> def f1() -> None:
        ...     s_event = SmartThread(name='beta')
        ...     s_event.pair_with(remote_name='alpha')
        ...     s_event.sync()

        >>> smart_event = SmartThread(name='alpha')
        >>> f1_thread = threading.Thread(target=f1, args=(smart_event,))
        >>> f1_thread.start()
        >>> smart_event.pair_with(remote_name='beta')
        >>> smart_event.sync()
        >>> f1_thread.join()

        """
        start_time = time.time()

        timeout = None if (timeout and timeout <= 0) else timeout

        self.verify_current_remote()
        caller_info = ''
        if log_msg and self.debug_logging_enabled:
            caller_info = get_formatted_call_sequence(latest=1, depth=1)
            self.logger.debug(f'sync() entered by {self.name} to sync with {remote} {caller_info} {log_msg}')


        final_ret_code = True

        if not isinstance(target_set, list):
            target_set = [target_set]

        rem_group: dict[str, "SmartThread"] = {}
        status_group: dict[str, SmartThread.SharedPairStatus] = {}
        ret_codes: dict[str, bool] = {}

        for remote in target_set:
            self.pair(remote=remote, start_time=start_time, timeout=timeout)
            self.remote_group[remote] = self.remote
            status_group[remote] = self.status
            ret_codes[remote] = True
            self.status_bits[remote] = SmartThread.StatusBits(sync_wait=True)


        self.sync_wait = True


        #######################################################################
        # States:
        # self.remote.waiting is normal wait. Raise Conflict if not timeout on
        # either side.
        #
        # not remote sync_wait and sync_cleanup is remote in cleanup waiting
        # for us to set sync_cleanup to False
        #
        # self.remote.sync_wait and not sync_cleanup is remote waiting to see
        # us in sync_wait
        #
        # self.remote.sync_wait and sync_cleanup means we saw remote in
        # sync_wait and flipped sync_cleanup to True
        #
        #######################################################################
        # class StatusBits:
        #     code: Any = None
        #     wait_wait: bool = False
        #     sync_wait: bool = False
        #     wait_timeout_specified: bool = False
        #     deadlock: bool = False
        #     conflict: bool = False
        while True:
            for remote in remotes:
                while True:
                    with status_group[remote].status_lock:
                        if not (self.status_bits[remote].conflict or self.remote_group[remote].status_bits[self.name].conflict):
                            if self.status_bits[remote].sync_wait:  # we are phase 1
                                if self.remote_group[remote].status_bits[self.name].sync_wait:  # remote in phase 1
                                    # we now go to phase 2
                                    self.status_bits[remote].sync_wait = False
                                    status_group[remote].sync_cleanup = True
                                elif status_group[remote].sync_cleanup:  # remote in phase 2
                                    self.status_bits[remote].sync_wait = False
                                    status_group[remote].sync_cleanup = False
                                    break
                            else:  # we are phase 2
                                if not status_group[remote].sync_cleanup:  # remote exited ph 2
                                    break

                        if not (self.wait_timeout_specified
                                or self.remote.wait_timeout_specified
                                or self.status_bits[remote].conflict):
                            if (self.remote.wait_wait
                                and not (self.remote.event.is_set()
                                         or self.remote.deadlock
                                         or self.remote_group[remote].status_bits[self.name].conflict)):
                                self.remote_group[remote].status_bits[self.name].conflict = True
                                self.status_bits[remote].conflict = True

                        if self.status_bits[remote].conflict:
                            self.logger.debug(
                                f'{self.name} raising '
                                'SmartThreadConflictDeadlockDetected. '
                                f'self.remote.wait_wait = {self.remote.wait_wait}, '
                                f'self.remote.event.is_set() = {self.remote.event.is_set()}, '
                                f'self.remote.deadlock = {self.remote.deadlock}, '
                                f'self.remote.conflict = {self.remote_group[remote].status_bits[self.name].conflict}, '
                                f'self.remote.wait_timeout_specified = '
                                f'{self.remote.wait_timeout_specified}, '
                                f'self.wait_timeout_specified = '
                                f'{self.wait_timeout_specified}')
                            self.status_bits[remote].sync_wait = False
                            self.status_bits[remote].conflict = False
                            raise SmartThreadConflictDeadlockDetected(
                                'A sync request was made by thread '
                                f'{self.name} and a wait request was '
                                f'made by thread  {self.remote.name}.')
                        self.check_remote(remote=remote)

                        if timeout and (timeout < (time.time() - start_time)):
                            self.logger.debug(f'{self.name} timeout of a sync() '
                                              'request.')
                            self.status_bits[remote].sync_wait = False
                            ret_code = False
                            break

                    time.sleep(0.1)
                    final_ret_code = final_ret_code and ret_code

        if log_msg and self.debug_logging_enabled:
            self.logger.debug(f'sync() by {self.name} to sync with {remote} exiting with ret_code {ret_code} '
                              f'{caller_info} {log_msg}')

        return final_ret_code


    # def sync(self, *,
    #          remote: Union[str, list[str]],
    #          log_msg: Optional[str] = None,
    #          timeout: Optional[Union[int, float]] = None) -> bool:
    #     """Sync up with the remote thread via a matching sync request.
    #
    #     A ``sync()`` request made by the current thread waits until the remote
    #     thread makes a matching ``sync()`` request at which point both
    #     ``sync()`` requests are completed and control returned.
    #
    #     Args:
    #         remote: remote SmartThread we will sync with
    #         log_msg: log msg to log
    #         timeout: number of seconds to allow for sync to happen
    #
    #     Returns:
    #         * ``True`` if **timeout** was not specified, or if it was
    #           specified and the ``sync()`` request completed within the
    #           specified number of seconds.
    #         * ``False`` if **timeout** was specified and the ``sync()``
    #           request did not complete within the specified number of
    #           seconds.
    #
    #     Raises:
    #         SmartThreadConflictDeadlockDetected: A ``sync()`` request was made by one
    #                                     thread and a ``wait()`` request was
    #                                     made by the other thread.
    #
    #     Notes:
    #         1) If one thread makes a ``sync()`` request without **timeout**
    #            specified, and the other thread makes a ``wait()`` request to
    #            an event that was not **pre-resumed**, also without **timeout**
    #            specified, then both threads will recognize and raise a
    #            **SmartThreadConflictDeadlockDetected** error. This is needed since
    #            neither the ``sync()`` request nor the ``wait()`` request has
    #            any chance of completing. The ``sync()`` request is waiting for
    #            a matching ``sync()`` request and the ``wait()`` request is
    #            waiting for a matching ``resume()`` request.
    #         2) If one thread makes a ``sync()`` request and the other thread
    #            becomes not alive, the ``sync()`` request raises a
    #            **SmartThreadRemoteThreadNotAlive** error.
    #
    #     :Example: instantiate a SmartThread and sync the threads
    #
    #     >>> import scottbrian_paratools.smart_event as st
    #     >>> import threading
    #     >>> def f1() -> None:
    #     ...     s_event = SmartThread(name='beta')
    #     ...     s_event.pair_with(remote_name='alpha')
    #     ...     s_event.sync()
    #
    #     >>> smart_event = SmartThread(name='alpha')
    #     >>> f1_thread = threading.Thread(target=f1, args=(smart_event,))
    #     >>> f1_thread.start()
    #     >>> smart_event.pair_with(remote_name='beta')
    #     >>> smart_event.sync()
    #     >>> f1_thread.join()
    #
    #     """
    #     start_time = time.time()
    #
    #     timeout = None if (timeout and timeout <= 0) else timeout
    #
    #     self.verify_current_remote()
    #     caller_info = ''
    #     if log_msg and self.debug_logging_enabled:
    #         caller_info = get_formatted_call_sequence(latest=1, depth=1)
    #         self.logger.debug(f'sync() entered by {self.name} to sync with {remote} {caller_info} {log_msg}')
    #
    #     final_ret_code = True
    #
    #     if isinstance(remote, (tuple, list)):
    #         remotes = remote
    #     else:
    #         remotes = (remote,)
    #
    #     rem_group: dict["SmartThread"] = {}
    #     for remote in remotes:
    #         self.pair(remote=remote, start_time=start_time, timeout=timeout)
    #         rem_group[remote] = self.remote
    #
    #     self.sync_wait = True
    #
    #     #######################################################################
    #     # States:
    #     # self.remote.waiting is normal wait. Raise Conflict if not timeout on
    #     # either side.
    #     #
    #     # not remote sync_wait and sync_cleanup is remote in cleanup waiting
    #     # for us to set sync_cleanup to False
    #     #
    #     # self.remote.sync_wait and not sync_cleanup is remote waiting to see
    #     # us in sync_wait
    #     #
    #     # self.remote.sync_wait and sync_cleanup means we saw remote in
    #     # sync_wait and flipped sync_cleanup to True
    #     #
    #     #######################################################################
    #     while True:
    #         for remote in remotes:
    #             ret_code = True
    #
    #             while True:
    #                 with self.status.status_lock:
    #                     if not (self.conflict or self.remote.conflict):
    #                         if self.sync_wait:  # we are phase 1
    #                             if self.remote.sync_wait:  # remote in phase 1
    #                                 # we now go to phase 2
    #                                 self.sync_wait = False
    #                                 self.status.sync_cleanup = True
    #                             elif self.status.sync_cleanup:  # remote in phase 2
    #                                 self.sync_wait = False
    #                                 self.status.sync_cleanup = False
    #                                 break
    #                         else:  # we are phase 2
    #                             if not self.status.sync_cleanup:  # remote exited ph 2
    #                                 break
    #
    #                     if not (self.wait_timeout_specified
    #                             or self.remote.wait_timeout_specified
    #                             or self.conflict):
    #                         if (self.remote.wait_wait
    #                                 and not (self.remote.event.is_set()
    #                                          or self.remote.deadlock
    #                                          or self.remote.conflict)):
    #                             self.remote.conflict = True
    #                             self.conflict = True
    #
    #                     if self.conflict:
    #                         self.logger.debug(
    #                             f'{self.name} raising '
    #                             'SmartThreadConflictDeadlockDetected. '
    #                             f'self.remote.wait_wait = {self.remote.wait_wait}, '
    #                             f'self.remote.event.is_set() = {self.remote.event.is_set()}, '
    #                             f'self.remote.deadlock = {self.remote.deadlock}, '
    #                             f'self.remote.conflict = {self.remote.conflict}, '
    #                             f'self.remote.wait_timeout_specified = '
    #                             f'{self.remote.wait_timeout_specified}, '
    #                             f'self.wait_timeout_specified = '
    #                             f'{self.wait_timeout_specified}')
    #                         self.sync_wait = False
    #                         self.conflict = False
    #                         raise SmartThreadConflictDeadlockDetected(
    #                             'A sync request was made by thread '
    #                             f'{self.name} and a wait request was '
    #                             f'made by thread  {self.remote.name}.')
    #                     self.check_remote(remote=remote)
    #
    #                     if timeout and (timeout < (time.time() - start_time)):
    #                         self.logger.debug(f'{self.name} timeout of a sync() '
    #                                           'request.')
    #                         self.sync_wait = False
    #                         ret_code = False
    #                         break
    #
    #                 time.sleep(0.1)
    #                 final_ret_code = final_ret_code and ret_code
    #
    #     if log_msg and self.debug_logging_enabled:
    #         self.logger.debug(f'sync() by {self.name} to sync with {remote} exiting with ret_code {ret_code} '
    #                           f'{caller_info} {log_msg}')
    #
    #     return final_ret_code
    ###########################################################################
    # wait
    ###########################################################################
    def wait(self, *,
             remote: str,
             log_msg: Optional[str] = None,
             timeout: Optional[Union[int, float]] = None) -> bool:
        """Wait on event.

        Args:
            remote: name of remote that we expect to resume us
            log_msg: log msg to log
            timeout: number of seconds to allow for wait to complete

        Returns:
            * ``True`` if *timeout* was not specified, or if it was specified
              and the ``wait()`` request completed within the specified
              number of seconds.
            * ``False`` if *timeout* was specified and the ``wait()``
              request did not complete within the specified number of
              seconds.

        Raises:
            SmartThreadWaitDeadlockDetected: Both threads are deadlocked, each waiting
                                    on the other to ``resume()`` their event.
            SmartThreadConflictDeadlockDetected: A ``sync()`` request was made by
                                        the current thread but the
                                        but the remote thread
                                        detected deadlock instead
                                        which indicates that the
                                        remote thread did not make a
                                        matching ``sync()`` request.

        Notes:
            1) If one thread makes a ``sync()`` request without **timeout**
               specified, and the other thread makes a ``wait()`` request to
               an event that was not **pre-resumed**, also without **timeout**
               specified, then both threads will recognize and raise a
               **SmartThreadConflictDeadlockDetected** error. This is needed since
               neither the ``sync()`` request nor the ``wait()`` request has
               any chance of completing. The ``sync()`` request is waiting for
               a matching ``sync()`` request and the ``wait()`` request is
               waiting for a matching ``resume()`` request.
            2) If one thread makes a ``wait()`` request to an event that
               has not been **pre-resumed**, and without **timeout**
               specified, and the other thread makes a ``wait()`` request to
               an event that was not **pre-resumed**, also without **timeout**
               specified, then both threads will recognize and raise a
               **SmartThreadWaitDeadlockDetected** error. This is needed since neither
               ``wait()`` request has any chance of completing as each
               ``wait()`` request is waiting for a matching ``resume()``
               request.
            3) If one thread makes a ``wait()`` request and the other thread
               becomes not alive, the ``wait()`` request raises a
               **SmartThreadRemoteThreadNotAlive** error.

        :Example: instantiate a SmartThread and ``wait()`` for function to
                  ``resume()``

        >>> import scottbrian_paratools.smart_event as st
        >>> import threading
        >>> def f1() -> None:
        ...     s_event = SmartThread(name='beta')
        ...     s_event.pair_with(remote_name='alpha')
        ...     time.sleep(1)
        ...     s_event.resume()

        >>> a_smart_event = SmartThread(name='alpha')
        >>> f1_thread = threading.Thread(target=f1)
        >>> f1_thread.start()
        >>> a_smart_event.pair_with(remote_name='beta')
        >>> a_smart_event.wait()
        >>> f1_thread.join()

        """
        start_time = time.time()

        timeout = None if (timeout and timeout <= 0) else timeout
        if timeout:
            t_out = min(0.1, timeout)
            self.wait_timeout_specified = True
        else:
            t_out = 0.1
            self.wait_timeout_specified = False

        caller_info = ''
        if log_msg and self.debug_logging_enabled:
            caller_info = get_formatted_call_sequence(latest=1, depth=1)
            self.logger.debug(f'wait() entered by {self.name} to wait for {remote} {caller_info} {log_msg}')

        self.verify_current_remote()

        self.pair(remote=remote, start_time=start_time, timeout=timeout)

        self.wait_wait = True

        while True:
            ret_code = self.event.wait(timeout=t_out)

            # We need to do the following checks while locked to prevent
            # either thread from setting the other thread's flags AFTER
            # the other thread has already detected those
            # conditions, set the flags, left, and is back with a new
            # request.
            with self.status.status_lock:
                # Now that we have the lock we need to determine whether
                # we were resumed between the call and getting the lock
                if ret_code or self.event.is_set():
                    self.wait_wait = False
                    self.wait_timeout_specified = False
                    self.event.clear()  # be ready for next wait
                    ret_code = True
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
                # and is not resumed then it will not be getting resumed by us
                # since we are also waiting. So, we set self.remote.deadlock
                # to tell it, and then we raise the error on our side.
                # But, we don't do this if the self.remote.deadlock is
                # already on as that suggests that we already told
                # remote and raised the error, which implies that we are
                # in a new wait and the remote has not yet woken up to
                # deal with the earlier deadlock. We can simply ignore
                # it for now.

                if not (self.wait_timeout_specified
                        or self.remote.wait_timeout_specified
                        or self.deadlock
                        or self.conflict):
                    if (self.remote.sync_wait
                            and not (self.status.sync_cleanup
                                     or self.remote.conflict)):
                        self.remote.conflict = True
                        self.conflict = True
                        self.logger.debug(f'{self.name} detected conflict')
                    elif (self.remote.wait_wait
                            and not (self.event.is_set()
                                     or self.remote.deadlock
                                     or self.remote.conflict)):
                        self.remote.deadlock = True
                        self.deadlock = True
                        self.logger.debug(f'{self.name} detected deadlock')

                if self.conflict:
                    self.wait_wait = False
                    self.conflict = False
                    self.wait_timeout_specified = False
                    self.logger.debug(f'{self.name} raising '
                                      'SmartThreadConflictDeadlockDetected')
                    raise SmartThreadConflictDeadlockDetected(
                        'A sync request was made by thread '
                        f'{self.name} but remote thread '
                        f'{self.remote.name} detected deadlock instead '
                        'which indicates that the remote '
                        'thread did not make a matching sync '
                        'request.')

                if self.deadlock:
                    self.wait_wait = False
                    self.deadlock = False
                    self.wait_timeout_specified = False
                    self.logger.debug(f'{self.name} raising '
                                      'SmartThreadWaitDeadlockDetected')
                    raise SmartThreadWaitDeadlockDetected(
                        'Both threads are deadlocked, each waiting on '
                        'the other to resume their event.')
                self.check_remote(remote=remote)

                if timeout and (timeout < (time.time() - start_time)):
                    self.logger.debug(f'{self.name} timeout of a wait() '
                                      'request with self.wait_wait = '
                                      f'{self.wait_wait} and '
                                      'self.sync_wait ='
                                      f' {self.sync_wait}')
                    self.wait_wait = False
                    self.wait_timeout_specified = False
                    ret_code = False
                    break

        if log_msg and self.debug_logging_enabled:
            self.logger.debug(f'wait() by {self.name} to wait for {remote} exiting with ret_code {ret_code} '
                              f'{caller_info} {log_msg}')

        return ret_code

    ###########################################################################
    # verify_current_remote
    ###########################################################################
    def verify_current_remote(self,
                              skip_pair_check: Optional[bool] = False
                              ) -> None:
        """Check the current and remote ThreadEvent objects.

        Args:
            skip_pair_check: used by pair_with since the pairing in
                               not yet done

        Raises:
            SmartThreadDetectedOpFromForeignThread: Any SmartThread services must be
                                           called from the thread that
                                           originally instantiated the
                                           SmartThread.

        """
        # We check for foreign thread first before checking for pairing
        # since we do not want a user who attempts to use SmartThread from
        # a different thread to get a SmartThreadNotPaired error first and think
        # that the fix it to simply call pair_with from the foreign
        # thread.
        if self.thread is not threading.current_thread():
            self.logger.debug(f'{self.name } raising '
                              'SmartThreadDetectedOpFromForeignThread')
            raise SmartThreadDetectedOpFromForeignThread(
                'Any SmartThread services must be called from the thread '
                'that originally instantiated the SmartThread. '
                f'Call sequence: {get_formatted_call_sequence(1,2)}')

        # make sure that remote exists and it points back to us
        # if not skip_pair_check:
        #     self.verify_paired()

    ###########################################################################
    # check_remote
    ###########################################################################
    def check_remote(self,
                     remote: str) -> None:
        """Check whether remote is alive.

        Raises:
            SmartThreadRemoteThreadNotAlive: The remote thread is not alive.

        """
        # self.verify_paired()
        if not self.remote.thread.is_alive():
            self.logger.debug(f'{self.name} raising '
                              'SmartThreadRemoteThreadNotAlive.'
                              'Call sequence:'
                              f' {get_formatted_call_sequence()}')
            with SmartThread._registry_lock:
                # Remove any old entries
                self._clean_up_registry()

            raise SmartThreadRemoteThreadNotAlive(
                f'{self.name} has detected that {self.remote.name} '
                'thread is not alive.')
