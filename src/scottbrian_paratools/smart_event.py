"""Module smart_event.

=============
SmartEvent
=============

You can use the SmartEvent class to coordinate activities between two
threads by using either of two schemes:

    1) ``wait()`` and ``resume()`` requests
    2) ``sync()`` requests.

With ``wait()``/``resume()``, one thread typically gives another
thread a task to do and then does a ``wait()``. When the other
thread completes the task, it does a ``resume()`` to unblock the ``wait()``.
It does not matter which role each thread has at any point as long as a
``wait()`` by one thread is matched with a ``resume()`` by the other. Also,
a ``resume()`` can preceed a ``wait()``, known as a **pre-resume**,
which will simply allow the ``wait()`` to proceed imediately without blocking.

The SmartEvent ``sync()`` request is used to ensure that two threads have
each reached a processing sync-point. The first thread to do a
``sync()`` request is blocked until the second thread does a matching
``sync()``, at which point both threads are allowed to proceed.

Note that the type of thread processing we are doing here is
multi-tasking and **not** multi-processing. As such, only one thread runs
at a time, with each thread be being given a slice of time. So, unblocking a
thread with a ``resume()`` or a matching ``sync()`` does not
neccessarily cause that thread to begin processing immediately - it will
simply be unblocked and will run when it gets its slice of time.

One of the important features of SmartEvent is that it will detect when a
``wait()`` or ``sync()`` will fail to complete because either the other
thread has become inactive or because the other thread has issued a ``wait()``
request which now places both threads in a deadlock. When this happens, a
**RemoteThreadNotAlive**, **WaitDeadlockDetected**, or
**ConflictDeadlockDetected** error will be raised.


:Example: create a SmartEvent for mainline and a thread to use

>>> from scottbrian_paratools.smart_event import SmartEvent
>>> import threading
>>> import time
>>> def f1() -> None:
...     print('f1 beta entered')
...     s_event = SmartEvent(name='beta')
...     s_event.pair_with(remote_name='alpha')
...     print('f1 beta is doing some work')
...     time.sleep(3)  # simulate an i/o task being done
...     print('f1 beta done - about to resume alpha')
...     s_event.resume()
>>> smart_event = SmartEvent(name='alpha')
>>> f1_thread = threading.Thread(target=f1)
>>> print('alpha about to start the beta thread')
>>> f1_thread.start()  # give beta a task to do
>>> smart_event.pair_with(remote_name='beta')
>>> time.sleep(2)  # simulate doing some work
>>> print('alpha about to wait for beta to complete its work')
>>> smart_event.wait()  # wait for beta to complete its task
>>> print('alpha back from wait')
alpha about to start the beta thread
f1 beta entered
f1 beta is doing some work
alpha about to wait for beta to complete
f1 beta done - about to resume alpha
alpha back from wait


The smart_event module contains:

    1) SmartEvent class with methods:

       a. get_code
       b. pair_with
       c. pause_until
       d. resume
       e. sync
       f. wait


"""
###############################################################################
# Standard Library
###############################################################################
from dataclasses import dataclass
from enum import Enum
import logging
import threading
import time
from typing import (Any, Dict, Final, Optional, Tuple, Type,
                    TYPE_CHECKING, Union)

###############################################################################
# Third Party
###############################################################################

###############################################################################
# Local
###############################################################################
from scottbrian_utils.diag_msg import get_formatted_call_sequence


###############################################################################
# SmartEvent class exceptions
###############################################################################
class SmartEventError(Exception):
    """Base class for exceptions in this module."""
    pass


class AlreadyPairedWithRemote(SmartEventError):
    """SmartEvent exception for pair_with that is already paired."""


class ConflictDeadlockDetected(SmartEventError):
    """SmartEvent exception for conflicting requests."""
    pass


class DetectedOpFromForeignThread(SmartEventError):
    """SmartEvent exception for attempted op from unregistered thread."""
    pass


class ErrorInRegistry(SmartEventError):
    """SmartEvent exception for registry error."""


class InconsistentFlagSettings(SmartEventError):
    """SmartEvent exception for flag setting that are not valid."""
    pass


class IncorrectNameSpecified(SmartEventError):
    """SmartEvent exception for a name that is not a str."""


class NameAlreadyInUse(SmartEventError):
    """SmartEvent exception for using a name already in use."""
    pass


class NotPaired(SmartEventError):
    """SmartEvent exception for alpha or beta thread not registered."""
    pass


class PairWithSelfNotAllowed(SmartEventError):
    """SmartEvent exception for pair_with target is self."""


class PairWithTimedOut(SmartEventError):
    """SmartEvent exception for pair_with that timed out."""


class RemotePairedWithOther(SmartEventError):
    """SmartEvent exception for pair_with target already paired."""


class RemoteThreadNotAlive(SmartEventError):
    """SmartEvent exception for alpha or beta thread not alive."""
    pass


class WaitDeadlockDetected(SmartEventError):
    """SmartEvent exception for wait deadlock detected."""
    pass


class WaitUntilTimeout(SmartEventError):
    """SmartEvent exception for pause_until timeout."""
    pass


###############################################################################
# pause_until conditions
###############################################################################
WUCond = Enum('WUCond',
              'ThreadsReady RemoteWaiting RemoteResume')


###############################################################################
# SmartEvent class
###############################################################################
class SmartEvent:
    """Provides a coordination mechanism between two threads."""

    pause_until_TIMEOUT: Final[int] = 16
    pair_with_TIMEOUT: Final[int] = 60

    ###########################################################################
    # Registry
    ###########################################################################
    _registry_lock = threading.Lock()
    _registry: dict[str, "SmartEvent"] = {}

    ###########################################################################
    # SharedPairStatus Data Class
    ###########################################################################
    @dataclass
    class SharedPairStatus:
        """Shared area for status between paired SmartEvents."""
        status_lock = threading.Lock()
        sync_cleanup = False

    ###########################################################################
    # __init__
    ###########################################################################
    def __init__(self, *,
                 name: str,
                 ) -> None:
        """Initialize an instance of the SmartEvent class.

        Args:
            name: name to be used to refer to this SmartEvent

        Raises:
            IncorrectNameSpecified: Attempted SmartEvent instantiation
                                      with incorrect name of {name}.

        """
        if not isinstance(name, str):
            raise IncorrectNameSpecified('Attempted SmartEvent instantiation '
                                         f'with incorrect name of {name}.')
        self.name = name
        self.thread = threading.current_thread()
        self.event = threading.Event()
        self.remote = None

        self.status = None

        self.code: Any = None
        self.wait_wait: bool = False
        self.sync_wait: bool = False
        self.timeout_specified: bool = False
        self.deadlock: bool = False
        self.conflict: bool = False

        self.logger = logging.getLogger(__name__)
        self.debug_logging_enabled = self.logger.isEnabledFor(logging.DEBUG)

        self._register()

    ###########################################################################
    # repr
    ###########################################################################
    def __repr__(self) -> str:
        """Return a representation of the class.

        Returns:
            The representation as how the class is instantiated

        :Example: instantiate a SmartEvent and call repr

        >>> from scottbrian_paratools.smart_event import SmartEvent
        >>> smart_event = SmartEvent(name='alpha')
        >>> repr(smart_event)
        SmartEvent(name="alpha")

        """
        if TYPE_CHECKING:
            __class__: Type[SmartEvent]
        classname = self.__class__.__name__
        parms = f'name="{self.name}"'

        return f'{classname}({parms})'

    ###########################################################################
    # get_code
    ###########################################################################
    def get_code(self) -> Any:
        """Get code from last ``resume()``.

        Returns:
            The code provided by the thread that did the ``resume()`` event

        :Example: instantiate SmartEvent and ``resume()`` with a code

        >>> from scottbrian_paratools.smart_event import SmartEvent
        >>> import threading
        >>> def f1() -> None:
        ...     print('f1 beta entered')
        ...     s_event = SmartEvent(name='beta')
        ...     s_event.pair_with(remote_name='alpha')
        ...     print('f1 about to wait')
        ...     s_event.wait()
        ...     print('f1 back from wait, about to retrieve code')
        ...     print(f'code = {s_event.get_code()}')

        >>> a_smart_event = SmartEvent(name='alpha')
        >>> f1_thread = threading.Thread(target=f1)
        >>> f1_thread.start()
        >>> a_smart_event.pair_with(remote_name='beta')
        >>> print('mainline about to resume f1 with a code of 42')
        >>> a_smart_event.resume(code=42)
        >>> f1_thread.join()
        f1 beta entered
        f1 about to wait
        mainline about to resume f1 with a code of 42
        f1 back from wait, about to retrieve code
        code = 42

        """
        return self.code

    ###########################################################################
    # register
    ###########################################################################
    def _register(self) -> None:
        """Register SmartEvent in the class registry.

        Raises:
            IncorrectNameSpecified: The name for SmartEvent must be of type
                                      str.
            NameAlreadyInUse: An entry for a SmartEvent with name = *name*
                                is already registered and paired with
                                *remote name*.

        Notes:
            1) Any old entries for SmartEvents whose threads are not alive
               are removed when this method is called by calling
               _clean_up_registry().
            2) Once a thread become not alive, it can not be resurrected.
               The SmartEvent is bound to the thread it starts with. If the
               remote SmartEvent thread that the SmartEvent is paired with
               becomes not alive, we allow this SmartEvent to pair with a new
               SmartEvent on a new thread.

        """
        with self._registry_lock:
            # Remove any old entries
            self._clean_up_registry()

            # Make sure name is valid
            if not isinstance(self.name, str):
                raise IncorrectNameSpecified('The name for SmartEvent must be'
                                             ' of type str.')

            # Make sure name not already taken
            if (self.name in self._registry
                    and self._registry[self.name].thread.is_alive()
                    and self._registry[self.name].remote is not None
                    and self._registry[self.name].remote.thread.is_alive()):
                raise NameAlreadyInUse(
                    f'An entry for a SmartEvent with name = {self.name} is '
                    'already registered and paired with '
                    f'{self._registry[self.name].remote.name}.')

            # Add new SmartEvent or replace old entry of same name
            self._registry[self.name] = self

    ###########################################################################
    # _clean_up_registry
    ###########################################################################
    def _clean_up_registry(self) -> None:
        """Clean up any old not alive items in the registry.

        Raises:
            ErrorInRegistry: Registry item with key {key} has non-matching
                             item.name of {item.name}.

        Notes:
            1) Must be called holding _registry_lock

        """
        # Remove any old entries
        keys_to_del = []
        for key, item in self._registry.items():
            if not item.thread.is_alive():
                keys_to_del.append(key)

            # if (item.remote is not None
            #         and not item.remote.thread.is_alive()):
            #     keys_to_del.append(key)

            if key != item.name:
                raise ErrorInRegistry(f'Registry item with key {key} '
                                      f'has non-matching item.name '
                                      f'of {item.name}.')

        for key in keys_to_del:
            del self._registry[key]

    ###########################################################################
    # pair_with
    ###########################################################################
    def pair_with(self, *,
                  remote_name: str,
                  log_msg: Optional[str] = None,
                  timeout: Optional[Union[int, float]] = pair_with_TIMEOUT
                  ) -> None:
        """Establish a connection with the remote thread.

        After the SmartEvent object is instantiated by both threads,
        both threads must issue matching ''pair_with()'' requests to
        establish a connection between the two threads.

        Args:
            remote_name: the name of the thread to pair with
            log_msg: log msg to log
            timeout: number of seconds to allow for ``pair_with()`` to
                       complete. The *timeout* specification is import to
                       prevent a hang from occuring in case the remote
                       thread is unable to complete its matching
                       ''pair_with()'' request.

        Raises:
            AlreadyPairedWithRemote: A pair_with request by
                                       {self.name} with target of
                                       remote_name = {remote_name}
                                       can not be done since
                                       {self.name} is already paired
                                       with {self.remote.name}.
            IncorrectNameSpecified: Attempted SmartEvent pair_with()
                                      with incorrect remote name of
                                      {remote_name}.
            RemotePairedWithOther: {self.name} detected that remote
                                {remote_name} is already paired with
                                {self.remote.remote.name}.
            PairWithSelfNotAllowed: {self.name} attempted to pair
                                    with itself using remote_name of
                                    {remote_name}.
            PairWithTimedOut: {self.name} timed out on a
                                pair_with() request with
                                remote_name = {remote_name}.

        Notes:
            1) A ``pair_with()`` request can only be done when the
               SmartEvent is not already paired with another thread.
            2) Once the ''pair_with()'' request completes, the SmartEvent is
               ready to issue requests.
            3) Unlike the other SmartEcvent requests, the ''pair_with()''
               request is unable to detect when the remothe thread become not
               alive. This is why the *timeout* argument is required, either
               explicitly or by default.

        :Example: instantiate SmartEvent and issue ``pair_with()`` requests

        >>> from scottbrian_paratools.smart_event import SmartEvent
        >>> import threading
        >>> def f1() -> None:
        ...     s_event = SmartEvent(name='beta')
        ...     s_event.pair_with(remote_name='alpha')
        ...     s_event.wait()

        >>> a_smart_event = SmartEvent(name='alpha')
        >>> f1_thread = threading.Thread(target=f1)
        >>> f1_thread.start()
        >>> a_smart_event.pair_with(remote_name='beta')
        >>> a_smart_event.resume()
        >>> f1_thread.join()

        """
        start_time = time.time()  # start the timeout clock

        # if caller specified a log message to issue
        caller_info = ''
        if log_msg and self.debug_logging_enabled:
            caller_info = get_formatted_call_sequence(latest=1, depth=1)
            self.logger.debug(f'pair_with() entered by {self.name} to '
                              f'pair with remote_name = {remote_name}. '
                              f'{caller_info} {log_msg}')

        if not isinstance(remote_name, str):
            raise IncorrectNameSpecified('Attempted SmartEvent pair_with() '
                                         f'with incorrect remote name of'
                                         f' {remote_name}.')

        if remote_name == self.name:
            raise PairWithSelfNotAllowed(f'{self.name} attempted to pair'
                                         'with itself using remote_name of '
                                         f' {remote_name}.')

        # check to make sure not already paired (even to same remote)
        if self.remote is not None:
            if self.remote.thread.is_alive():
                raise AlreadyPairedWithRemote('A pair_with request by '
                                              f'{self.name} with target of '
                                              f'remote_name = {remote_name} '
                                              f'can not be done since '
                                              f'{self.name} is already paired '
                                              f'with {self.remote.name}.')
            else:
                # we wait until now to clean the residual entry so that
                # any attempts to use SmartEvent will fail with
                # RemoteThreadNotAlive instead of NotPaired
                self.remote = None  # clean up residual not alive remote

        while True:
            # we hold the lock during most of this path to allow us to
            # back out of the pair by setting self.remote to None without
            # having to worry that the remote saw it with a value
            with self._registry_lock:
                # Remove any old entries
                self._clean_up_registry()

                # find target in registry
                # we check to see whether the remote point to us, and if not
                # we need to keep trying until we time out in case we are
                # waiting for the remote old to get cleaned up
                if self.remote is None:  # if target not yet found
                    for key, item in self._registry.items():
                        if (key == remote_name
                                and (item.remote is None
                                     or item.remote.name == self.name)):
                            self.remote = item
                            break

                if self.remote is not None:
                    if self.remote.remote is not None:
                        if self.remote.remote.name == self.name:
                            # If the remote has already created the
                            # shared status area, use it. Otherwise, we
                            # create it and the remote will use that.
                            if self.remote.status is not None:
                                self.status = self.remote.status
                            else:
                                self.status = self.SharedPairStatus()

                            break  # we are now paired
                        else:
                            diag_remote_name = self.remote.remote.name
                            self.remote = None
                            self.logger.debug(f'{self.name} unable to pair '
                                              f'with {remote_name} because '
                                              f'{remote_name} is paired with '
                                              f'{diag_remote_name}.')
                            raise RemotePairedWithOther(
                                f'{self.name} detected that remote '
                                f'{remote_name} is already paired with '
                                f'{diag_remote_name}.')

                # check whether we are out of time
                if timeout < (time.time() - start_time):
                    self.remote = None
                    self.logger.debug(f'{self.name} timed out on a '
                                      'pair_with() request with '
                                      f'remote_name = {remote_name}.')
                    raise PairWithTimedOut(f'{self.name} timed out on a '
                                           'pair_with() request with '
                                           f'remote_name = {remote_name}.')

            # pause to allow other side to run
            time.sleep(0.1)

        # if caller specified a log message to issue
        if log_msg and self.debug_logging_enabled:
            self.logger.debug(f'pair_with() exiting - {self.name} now '
                              f'paired with remote_name = {remote_name}. '
                              f'{caller_info} {log_msg}')

    ###########################################################################
    # resume
    ###########################################################################
    def resume(self, *,
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
               event will be completed immediatly.
            2) If the ``resume()`` request sees that the event has already
               been resumed, it will loop and wait for the event to be cleared
               under the assumption that the event was previously
               **pre-resumed** and a wait is imminent. The ``wait()`` will
               clear the event and the ``resume()`` request will simply resume
               it again as a **pre-resume**.
            3) If one thread makes a ``resume()`` request and the other thread
               becomes not alive, the ``resume()`` request raises a
               **RemoteThreadNotAlive** error.

        :Example: instantiate SmartEvent and ``resume()`` event that function
                    waits on

        >>> from scottbrian_paratools.smart_event import SmartEvent
        >>> import threading
        >>> def f1() -> None:
        ...     s_event = SmartEvent(name='beta')
        ...     s_event.pair_with(remote_name='alpha')
        ...     s_event.wait()

        >>> a_smart_event = SmartEvent(name='alpha')
        >>> f1_thread = threading.Thread(target=f1)
        >>> f1_thread.start()
        >>> a_smart_event.pair_with(remote_name='beta')
        >>> a_smart_event.resume()
        >>> f1_thread.join()

        """
        start_time = time.time()  # start the clock

        self._verify_current_remote()

        # if caller specified a log message to issue
        caller_info = ''
        if log_msg and self.debug_logging_enabled:
            code_msg = f' with code: {code} ' if code else ' '
            caller_info = get_formatted_call_sequence(latest=1, depth=1)
            self.logger.debug(f'resume() entered{code_msg}'
                              f'{caller_info} {log_msg}')

        while True:
            with self.status.status_lock:
                self._check_remote()
                ###############################################################
                # Cases where we loop until remote is ready:
                # 1) Remote waiting and event already resumed. This is a case
                #    where the remote was previously resumed and has not yet
                #    been given control to exit the wait. If and when that
                #    happens, this resume will complete as a pre-resume.
                # 2) Remote waiting and deadlock. The remote was flagged as
                #    being in a deadlock and has not been given control to
                #    raise the WaitDeadlockDetected error. The remote could
                #    recover, in which case this resume will complete,
                #    or the thread could become inactive, in which case
                #    resume will see that and raise (via _check_remote
                #    method) the RemoteThreadNotAlive error.
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
                if not (self.event.is_set()
                        or self.remote.deadlock
                        or (self.remote.conflict and self.remote.wait_wait)):
                    if code:  # if caller specified a code for remote thread
                        self.remote.code = code
                    self.event.set()  # wake remote thread
                    ret_code = True
                    break

                if timeout and (timeout < (time.time() - start_time)):
                    self.logger.debug(f'{self.name} timeout of a resume() '
                                      'request with self.event.is_set() = '
                                      f'{self.event.is_set()} and '
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
             log_msg: Optional[str] = None,
             timeout: Optional[Union[int, float]] = None) -> bool:
        """Sync up with the remote thread via a matching sync request.

        A ``sync()`` request made by the current thread waits until the remote
        thread makes a matching ``sync()`` request at which point both
        ``sync()`` requests are completed and control returned.

        Args:
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
            ConflictDeadlockDetected: A ``sync()`` request was made by one
                                        thread and a ``wait()`` request was
                                        made by the other thread.

        Notes:
            1) If one thread makes a ``sync()`` request without **timeout**
               specified, and the other thread makes a ``wait()`` request to
               an event that was not **pre-resumed**, also without **timeout**
               specified, then both threads will recognize and raise a
               **ConflictDeadlockDetected** error. This is needed since
               neither the ``sync()`` request nor the ``wait()`` request has
               any chance of completing. The ``sync()`` request is waiting for
               a matching ``sync()`` request and the ``wait()`` request is
               waiting for a matching ``resume()`` request.
            2) If one thread makes a ``sync()`` request and the other thread
               becomes not alive, the ``sync()`` request raises a
               **RemoteThreadNotAlive** error.

        :Example: instantiate a SmartEvent and sync the threads

        >>> from scottbrian_paratools.smart_event import SmartEvent
        >>> import threading
        >>> def f1() -> None:
        ...     s_event = SmartEvent(name='beta')
        ...     s_event.pair_with(remote_name='alpha')
        ...     s_event.sync()

        >>> smart_event = SmartEvent(name='alpha')
        >>> f1_thread = threading.Thread(target=f1, args=(smart_event,))
        >>> f1_thread.start()
        >>> smart_event.pair_with(remote_name='beta')
        >>> smart_event.sync()
        >>> f1_thread.join()

        """
        self._verify_current_remote()
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
                        if not self.status.sync_cleanup:  # remote exited phase 2
                            break

                if not (self.timeout_specified
                        or self.remote.timeout_specified
                        or self.conflict):
                    if (self.remote.wait_wait
                        and not (self.event.is_set()
                                 or self.remote.deadlock
                                 or self.remote.conflict)):
                        self.remote.conflict = True
                        self.conflict = True

                if self.conflict:
                    self.logger.debug(
                        f'{self.name} raising '
                        'ConflictDeadlockDetected. '
                        f'self.remote.wait_wait = {self.remote.wait_wait}, '
                        f'self.event.is_set() = {self.event.is_set()}, '
                        f'self.remote.deadlock = {self.remote.deadlock}, '
                        f'self.remote.conflict = {self.remote.conflict}, '
                        f'self.remote.timeout_specified = '
                        f'{self.remote.timeout_specified}, '
                        f'self.timeout_specified = '
                        f'{self.timeout_specified}')
                    self.sync_wait = False
                    self.conflict = False
                    raise ConflictDeadlockDetected(
                        'A sync request was made by thread '
                        f'{self.name} and a wait request was '
                        f'made by thread  {self.remote.name}.')

                self._check_remote()

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
             log_msg: Optional[str] = None,
             timeout: Optional[Union[int, float]] = None) -> bool:
        """Wait on event.

        Args:
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
            WaitDeadlockDetected: Both threads are deadlocked, each waiting
                                    on the other to ``resume()`` their event.
            ConflictDeadlockDetected: A ``sync()`` request was made by
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
               **ConflictDeadlockDetected** error. This is needed since
               neither the ``sync()`` request nor the ``wait()`` request has
               any chance of completing. The ``sync()`` request is waiting for
               a matching ``sync()`` request and the ``wait()`` request is
               waiting for a matching ``resume()`` request.
            2) If one thread makes a ``wait()`` request to an event that
               has not been **pre-resumed**, and without **timeout**
               specified, and the other thread makes a ``wait()`` request to
               an event that was not **pre-resumed**, also without **timeout**
               specified, then both threads will recognize and raise a
               **WaitDeadlockDetected** error. This is needed since neither
               ``wait()`` request has any chance of completing as each
               ``wait()`` request is waiting for a matching ``resume()``
               request.
            3) If one thread makes a ``wait()`` request and the other thread
               becomes not alive, the ``wait()`` request raises a
               **RemoteThreadNotAlive** error.

        :Example: instantiate a SmartEvent and ``wait()`` for function to
                  ``resume()``

        >>> from scottbrian_paratools.smart_event import SmartEvent
        >>> import threading
        >>> def f1() -> None:
        ...     s_event = SmartEvent(name='beta')
        ...     s_event.pair_with(remote_name='alpha')
        ...     time.sleep(1)
        ...     s_event.resume()

        >>> a_smart_event = SmartEvent(name='alpha')
        >>> f1_thread = threading.Thread(target=f1)
        >>> f1_thread.start()
        >>> a_smart_event.pair_with(remote_name='beta')
        >>> a_smart_event.wait()
        >>> f1_thread.join()

        """
        self._verify_current_remote()

        if timeout and (timeout > 0):
            t_out = min(0.1, timeout)
            self.timeout_specified = True
        else:
            t_out = 0.1
            self.timeout_specified = False

        caller_info = ''
        if log_msg and self.debug_logging_enabled:
            caller_info = get_formatted_call_sequence(latest=1, depth=1)
            self.logger.debug(f'wait() entered {caller_info} {log_msg}')

        self.wait_wait = True
        start_time = time.time()

        while True:
            ret_code = self.remote.event.wait(timeout=t_out)

            # We need to do the following checks while locked to prevent
            # either thread from setting the other thread's flags AFTER
            # the other thread has already detected those
            # conditions, set the flags, left, and is back with a new
            # request.
            with self.status.status_lock:
                # Now that we have the lock we need to determine whether
                # we were resumed between the call and getting the lock
                if ret_code or self.remote.event.is_set():
                    self.wait_wait = False
                    self.remote.event.clear()  # be ready for next wait
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

                if not (self.timeout_specified
                        or self.remote.timeout_specified
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
                    self.logger.debug(f'{self.name} raising '
                                      'ConflictDeadlockDetected')
                    raise ConflictDeadlockDetected(
                        'A sync request was made by thread '
                        f'{self.name} but remote thread '
                        f'{self.remote.name} detected deadlock instead '
                        'which indicates that the remote '
                        'thread did not make a matching sync '
                        'request.')

                if self.deadlock:
                    self.wait_wait = False
                    self.deadlock = False
                    self.logger.debug(f'{self.name} raising '
                                      'WaitDeadlockDetected')
                    raise WaitDeadlockDetected(
                        'Both threads are deadlocked, each waiting on '
                        'the other to resume their event.')

                self._check_remote()

                if timeout and (timeout < (time.time() - start_time)):
                    self.logger.debug(f'{self.name} timeout of a wait() '
                                      'request with self.wait_wait = '
                                      f'{self.wait_wait} and '
                                      'self.sync_wait ='
                                      f' {self.sync_wait}')
                    self.wait_wait = False
                    ret_code = False
                    break

        if log_msg and self.debug_logging_enabled:
            self.logger.debug(f'wait() exiting with ret_code {ret_code} '
                              f'{caller_info} {log_msg}')

        return ret_code

    ###########################################################################
    # pause_until
    ###########################################################################
    def pause_until(self,
                    cond: WUCond,
                    timeout: Optional[Union[int, float]] = None
                    ) -> None:
        """Wait until a specific condition is met.

        Args:
            cond: specifies to either wait for:
                1) the remote to call ``wait()`` (WUCond.RemoteWaiting)
                2) the remote to call ``resume()`` (WUCond.RemoteWaiting)
            timeout: number of seconds to allow for pause_until to succeed

        .. # noqa: DAR101

        Raises:
            WaitUntilTimeout: The pause_until method timed out.

        :Example: instantiate SmartEvent and wait for ready

        >>> from scottbrian_paratools.smart_event import SmartEvent
        >>> import threading
        >>> def f1() -> None:
        ...     s_event = SmartEvent(name='beta')
        ...     s_event.pair_with(remote_name='alpha')
        ...     s_event.wait()

        >>> a_smart_event = SmartEvent(name='alpha')
        >>> f1_thread = threading.Thread(target=f1)
        >>> f1_thread.start()
        >>> a_smart_event.pause_until(WUCond.RemoteWaiting)
        >>> a_smart_event.resume()
        >>> f1_thread.join()

        """
        if timeout and (timeout > 0):
            t_out = min(0.1, timeout)
        else:
            t_out = 0.1
        start_time = time.time()

        #######################################################################
        # Handle RemoteWaiting
        #######################################################################
        if cond == WUCond.RemoteWaiting:
            self._verify_current_remote()
            while True:
                # make sure we are waiting for a new resume, meaning that
                # the event is not resumed and we are not doing a sync_wait
                # which may indicate the thread did not get control
                # yet to return from a previous resume or sync
                if (self.remote.wait_wait
                        and not self.event.is_set()
                        and not self.remote.sync_wait):
                    return

                self._check_remote()

                if timeout and (timeout < (time.time() - start_time)):
                    self.logger.debug(f'{self.name} raising '
                                      'WaitUntilTimeout')
                    raise WaitUntilTimeout(
                        'The pause_until method timed out. '
                        f'Call sequence: {get_formatted_call_sequence(1,1)}')

                time.sleep(t_out)

        #######################################################################
        # Handle RemoteResume
        #######################################################################
        elif cond == WUCond.RemoteResume:
            self._verify_current_remote()
            while not self.remote.event.is_set():

                self._check_remote()

                if timeout and (timeout < (time.time() - start_time)):
                    self.logger.debug(f'{self.name} raising '
                                      'WaitUntilTimeout')
                    raise WaitUntilTimeout(
                        'The pause_until method timed out. '
                        f'Call sequence: {get_formatted_call_sequence(1,1)}')

                time.sleep(t_out)

    ###########################################################################
    # _check_remote
    ###########################################################################
    def _check_remote(self) -> None:
        """Check the remote flags for consistency and whether remote is alive.

        Raises:
            InconsistentFlagSettings: The remote ThreadEvent flag settings
                                        are not valid.
            RemoteThreadNotAlive: The alpha or beta thread is not alive

        """
        # error cases for remote flags
        # 1) both waiting and sync_wait
        # 2) waiting False and deadlock or conflict are True
        # 3) sync_wait False and deadlock or conflict are True
        # 4) sync_wait and deadlock
        # 5) deadlock True and conflict True
        if ((self.remote.deadlock and self.remote.conflict)
                or (self.remote.wait_wait and self.remote.sync_wait)
                or ((self.remote.deadlock or self.remote.conflict)
                    and not (self.remote.wait_wait or self.remote.sync_wait))):
            self.logger.debug(f'{self.name} raising '
                              'InconsistentFlagSettings. '
                              f'wait_wait: {self.remote.wait_wait}, '
                              f'sync_wait: {self.remote.sync_wait}, '
                              f'deadlock: {self.remote.deadlock}, '
                              f'conflict: {self.remote.conflict}, ')
            raise InconsistentFlagSettings(
                f'Thread {self.name} detected remote {self.remote.name} '
                f'SmartEvent flag settings are not valid.')

        if not self.remote.thread.is_alive():
            self.logger.debug(f'{self.name} raising '
                              'RemoteThreadNotAlive.'
                              'Call sequence:'
                              f' {get_formatted_call_sequence()}')
            with self._registry_lock:
                # Remove any old entries
                self._clean_up_registry()

            raise RemoteThreadNotAlive(
                f'The current thread has detected that {self.remote.name} '
                'thread is not alive.')

    ###########################################################################
    # _verify_current_remote
    ###########################################################################
    def _verify_current_remote(self) -> None:
        """Get the current and remote ThreadEvent objects.

        Raises:
            NotPaired: Both threads must be paired before any SmartEvent
                         services can be called.
            DetectedOpFromForeignThread: Any SmartEvent services must be
                                           called from the thread that
                                           originally instantiated the
                                           SmartEvent.

        """
        # We check for foreign thread first before checking for pairing
        # since we do not want a user who attempts to use SmartEvent from
        # a different thread to get a NotPaired error first and think
        # that the fix it to simply call pair_with from the foreign
        # thread.
        if self.thread is not threading.current_thread():
            self.logger.debug(f'{self.name } raising '
                              'DetectedOpFromForeignThread')
            raise DetectedOpFromForeignThread(
                'Any SmartEvent services must be called from the thread '
                'that originally instantiated the SmartEvent. '
                f'Call sequence: {get_formatted_call_sequence(1,2)}')

        # make sure that remote exists and it points back to us
        if (self.remote is None
                or self.remote.remote is None
                or self.remote.remote.name != self.name):
            self.logger.debug(f'{self.name} raising NotPaired')
            raise NotPaired(
                'Both threads must be paired before any '
                'SmartEvent services can be called. '
                f'Call sequence: {get_formatted_call_sequence(1,2)}')
