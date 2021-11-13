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
import logging
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

    ###########################################################################
    # Registry
    ###########################################################################
    # The _registry is a dictionary of SmartClass instances keyed by the SmartThread name.
    _registry_lock = threading.Lock()
    _registry: dict[str, "SmartThread"] = {}

    ###########################################################################
    # SharedPairStatus Data Class
    ###########################################################################
    @dataclass
    class SharedPairStatus:
        """Shared area for status between paired SmartThread objects."""
        status_lock = threading.Lock()
        sync_cleanup = False

    ###########################################################################
    # __init__
    ###########################################################################
    def __init__(
            self, *,
            name: str,
            target: Optional[Callable[..., Any]] = None,
            thread: Optional[threading.Thread] = None
            ) -> None:
        """Initialize an instance of the SmartThread class.

        Args:
            name: name to be used to refer to this SmartThread
            target: specifies that a thread is to be created and started with the given target
            thread: specifies the thread to use instead of the current
                      thread - needed when SmartThread is instantiated in a
                      class that inherits threading.Thread in which case
                      thread=self is required

        Raises:
            SmartThreadIncorrectNameSpecified: Attempted SmartThread instantiation
                                      with incorrect name of {name}.

        """
        if not isinstance(name, str):
            raise SmartThreadIncorrectNameSpecified(
                'Attempted SmartThread instantiation '
                f'with incorrect name of {name}.')
        self.name = name

        if target:
            self.thread = threading.Thread(target=target)
        else:
            self.thread = threading.current_thread()

        # self.remote: dict[str, "SmartThread"] = {}
        self.remote: Optional["SmartThread"] = None
        
        self.event = threading.Event()

        self.status: Union[SmartThread.SharedPairStatus, Any] = None

        self.code: Any = None
        self.wait_wait: bool = False
        self.sync_wait: bool = False
        self.wait_timeout_specified: bool = False
        self.deadlock: bool = False
        self.conflict: bool = False

        self.logger = logging.getLogger(__name__)
        self.debug_logging_enabled = self.logger.isEnabledFor(logging.DEBUG)

        self._register()

        if target:
            self.thread.start()

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
            # self.logger.debug(f'key {key} item {item}')
            if not item.thread.is_alive():
                keys_to_del.append(key)

            if key != item.name:
                raise SmartThreadErrorInRegistry(f'Registry item with key {key} '
                                                f'has non-matching item.name '
                                                f'of {item.name}.')

        for key in keys_to_del:
            del SmartThread._registry[key]
            self.logger.debug(f'{key} removed from registry')

    ###########################################################################
    # resume
    ###########################################################################
    def resume(self, *,
               remote: str,
               log_msg: Optional[str] = None,
               timeout: Optional[Union[int, float]] = None,
               code: Optional[Any] = None) -> bool:
        """Resume a waiting or soon to be waiting thread.

        Args:
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

        self.verify_current_remote()

        # if caller specified a log message to issue
        caller_info = ''
        if log_msg and self.debug_logging_enabled:
            code_msg = f' with code: {code} ' if code else ' '
            caller_info = get_formatted_call_sequence(latest=1, depth=1)
            self.logger.debug(f'resume() entered{code_msg}'
                              f'{caller_info} {log_msg}')

        while True:
            with SmartThread._registry_lock:
                if remote not in SmartThread._registry:
                    if SmartThread.register_TIMEOUT < time.time() - start_time:  # remote has not yet registered
                        raise SmartThreadRemoteNotRegisteredTimeout(
                            f'{self.name} resume request timed out waiting for {remote} to register.')
                    continue
                else:
                    self.remote = SmartThread._registry[remote]  # get remote SmartThread
                    if self.remote.status is not None:
                        self.status = self.remote.status
                    else:
                        self.status = self.SharedPairStatus()
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

        # if caller specified a log message to issue
        if log_msg and self.debug_logging_enabled:
            self.logger.debug(f'resume() exiting with ret_code {ret_code} '
                              f'{caller_info} {log_msg}')
        return ret_code

    ###########################################################################
    # sync
    ###########################################################################
    def sync(self, *,
             remote: str,
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
        self.verify_current_remote()
        caller_info = ''
        if log_msg and self.debug_logging_enabled:
            caller_info = get_formatted_call_sequence(latest=1, depth=1)
            self.logger.debug(f'sync() entered {caller_info} {log_msg}')

        start_time = time.time()
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
        ret_code = True
        while True:
            with SmartThread._registry_lock:
                if remote not in SmartThread._registry:
                    if SmartThread.register_TIMEOUT < time.time() - start_time:  # remote has not yet registered
                        raise SmartThreadRemoteNotRegisteredTimeout(
                            f'{self.name} resume request timed out waiting for {remote} to register.')
                    continue
                else:
                    self.remote = SmartThread._registry[remote]  # get remote SmartThread
                    if self.remote.status is not None:
                        self.status = self.remote.status
                    else:
                        self.status = self.SharedPairStatus()
            with self.status.status_lock:
                if not (self.conflict or self.remote.conflict):
                    if self.sync_wait:  # we are phase 1
                        if self.remote.sync_wait:  # remote in phase 1
                            # we now go to phase 2
                            self.sync_wait = False
                            self.status.sync_cleanup = True
                        elif self.status.sync_cleanup:  # remote in phase 2
                            self.sync_wait = False
                            self.status.sync_cleanup = False
                            break
                    else:  # we are phase 2
                        if not self.status.sync_cleanup:  # remote exited ph 2
                            break

                if not (self.wait_timeout_specified
                        or self.remote.wait_timeout_specified
                        or self.conflict):
                    if (self.remote.wait_wait
                        and not (self.remote.event.is_set()
                                 or self.remote.deadlock
                                 or self.remote.conflict)):
                        self.remote.conflict = True
                        self.conflict = True

                if self.conflict:
                    self.logger.debug(
                        f'{self.name} raising '
                        'SmartThreadConflictDeadlockDetected. '
                        f'self.remote.wait_wait = {self.remote.wait_wait}, '
                        f'self.remote.event.is_set() = {self.remote.event.is_set()}, '
                        f'self.remote.deadlock = {self.remote.deadlock}, '
                        f'self.remote.conflict = {self.remote.conflict}, '
                        f'self.remote.wait_timeout_specified = '
                        f'{self.remote.wait_timeout_specified}, '
                        f'self.wait_timeout_specified = '
                        f'{self.wait_timeout_specified}')
                    self.sync_wait = False
                    self.conflict = False
                    raise SmartThreadConflictDeadlockDetected(
                        'A sync request was made by thread '
                        f'{self.name} and a wait request was '
                        f'made by thread  {self.remote.name}.')
                self.check_remote()

                if timeout and (timeout < (time.time() - start_time)):
                    self.logger.debug(f'{self.name} timeout of a sync() '
                                      'request.')
                    self.sync_wait = False
                    ret_code = False
                    break

            time.sleep(0.1)

        if log_msg and self.debug_logging_enabled:
            self.logger.debug(f'sync() exiting with ret_code {ret_code} '
                              f'{caller_info} {log_msg}')

        return ret_code

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
        self.verify_current_remote()

        if timeout and (timeout > 0):
            t_out = min(0.1, timeout)
            self.wait_timeout_specified = True
        else:
            t_out = 0.1
            self.wait_timeout_specified = False

        caller_info = ''
        if log_msg and self.debug_logging_enabled:
            caller_info = get_formatted_call_sequence(latest=1, depth=1)
            self.logger.debug(f'wait() entered {caller_info} {log_msg}')

        self.wait_wait = True
        start_time = time.time()

        while True:
            with SmartThread._registry_lock:
                if remote not in SmartThread._registry:
                    if SmartThread.register_TIMEOUT < time.time() - start_time:  # remote has not yet registered
                        raise SmartThreadRemoteNotRegisteredTimeout(
                            f'{self.name} resume request timed out waiting for {remote} to register.')
                    continue
                else:
                    self.remote = SmartThread._registry[remote]  # get remote SmartThread
                    if self.remote.status is not None:
                        self.status = self.remote.status
                    else:
                        self.status = self.SharedPairStatus()
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
                self.check_remote()

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
            self.logger.debug(f'wait() exiting with ret_code {ret_code} '
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
    def check_remote(self) -> None:
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

    ###########################################################################
    # verify_paired
    ###########################################################################
    # def verify_paired(self) -> None:
    #     """Verify that we are paired.
    #
    #     Raises:
    #         SmartThreadNotPaired: Both threads must be paired before any
    #                                SmartThread services can be called.
    #
    #     """
    #     # make sure that remote exists and it points back to us
    #     if (self.remote is None
    #             or self.remote.remote is None
    #             or self.remote.remote.name != self.name):
    #         # collect diag info and raise error
    #         diag_remote_remote = None
    #         diag_name = None
    #         if self.remote is not None:
    #             diag_remote_remote = self.remote.remote
    #             if self.remote.remote is not None:
    #                 diag_name = self.remote.remote.name
    #         self.logger.debug(f'{self.name} raising SmartThreadNotPaired. '
    #                           f'Remote = {self.remote}, '
    #                           f'remote.remote = {diag_remote_remote}, '
    #                           f'remote name = {diag_name}')
    #         raise SmartThreadNotPaired(
    #             'Both threads must be paired before any '
    #             'SmartThread services can be called. '
    #             f'Call sequence: {get_formatted_call_sequence(1, 2)}')
