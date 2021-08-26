"""Module smart_event.

=============
SmartEvent
=============

You can use the SmartEvent class to coordinate activities between two
threads by using either of two schemes:

    1) ``wait()`` and ``resume()``
    2) ``sync()``.

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
at a time, with each thread being given a slice of time. So, unblocking a
thread with a ``resume()`` or a matching ``sync()`` does not
neccessarily cause that thread to begin processing immediately - it will
simply be unblocked and will run when it gets its slice of time.

One of the important features of SmartEvent is that it will detect when a
``wait()`` or ``sync()`` will fail to complete because either the other
thread has become inactive or because the other thread has issued a ``wait()``
request which now places both threads in a deadlock. When this happens, a
**SmartEventRemoteThreadNotAlive**, **SmartEventWaitDeadlockDetected**, or
**SmartEventConflictDeadlockDetected** error will be raised.


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
from typing import Any, Final, Optional, Type, TYPE_CHECKING, Union

###############################################################################
# Third Party
###############################################################################

###############################################################################
# Local
###############################################################################
from scottbrian_utils.diag_msg import get_formatted_call_sequence
from scottbrian_paratools.thread_pair import ThreadPair


###############################################################################
# SmartEvent class exceptions
###############################################################################
class SmartEventError(Exception):
    """Base class for exceptions in this module."""
    pass


class SmartEventConflictDeadlockDetected(SmartEventError):
    """SmartEvent exception for conflicting requests."""
    pass


class SmartEventInconsistentFlagSettings(SmartEventError):
    """SmartEvent exception for flag setting that are not valid."""
    pass


class SmartEventRemoteThreadNotAlive(SmartEventError):
    """SmartEvent exception for alpha or beta thread not alive."""
    pass


class SmartEventWaitDeadlockDetected(SmartEventError):
    """SmartEvent exception for wait deadlock detected."""
    pass


class SmartEventWaitUntilTimeout(SmartEventError):
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
class SmartEvent(ThreadPair):
    """Provides a coordination mechanism between two threads."""

    ###########################################################################
    # States of a SmartEvent
    #
    #     current              | remote
    # -------------------------|-----------------------------------------------
    #     reg | alive | remote | rem reg  | rem alive | r->N/s/o
    #  1)  no |  no   |  None  |    n/a   |     n/a    | n/a
    #  2)  no |  no   |  yes   |    no    |     no     | None
    #  3)  no |  no   |  yes   |    no    |     no     | self
    #  4)  no |  no   |  yes   |    no    |     no     | other
    #
    #  5)  no |  yes  |  None  |    n/a   |     n/a    | n/a
    #  6)  no |  yes  |  yes   |    no    |     no     | None
    #  7)  no |  yes  |  yes   |    no    |     no     | self
    #  8)  no |  yes  |  yes   |    no    |     no     | other

    #  9) yes |  no   |  None  |    n/a   |     n/a    | n/a
    # 10) yes |  no   |  yes   |    no    |     no     | None
    # 11) yes |  no   |  yes   |    no    |     no     | self
    # 12) yes |  no   |  yes   |    no    |     no     | other
    #
    # 13) yes |  yes  |  None  |    n/a   |     n/a    | n/a
    # 14) yes |  yes  |  yes   |    no    |     no     | None
    # 15) yes |  yes  |  yes   |    no    |     no     | self
    # 16) yes |  yes  |  yes   |    no    |     no     | other
    #
    # 17)  no |  no   |  None  |    n/a   |     n/a    | n/a
    # 18)  no |  no   |  yes   |    no    |     yes    | None
    # 19)  no |  no   |  yes   |    no    |     yes    | self
    # 20)  no |  no   |  yes   |    no    |     yes    | other
    #
    # 21)  no |  yes  |  None  |    n/a   |     n/a    | n/a
    # 22)  no |  yes  |  yes   |    no    |     yes    | None
    # 23)  no |  yes  |  yes   |    no    |     yes    | self
    # 24)  no |  yes  |  yes   |    no    |     yes    | other

    # 25) yes |  no   |  None  |    n/a   |     n/a    | n/a
    # 26) yes |  no   |  yes   |    no    |     yes    | None
    # 27) yes |  no   |  yes   |    no    |     yes    | self
    # 28) yes |  no   |  yes   |    no    |     yes    | other
    #
    # 29) yes |  yes  |  None  |    n/a   |     n/a    | n/a
    # 30) yes |  yes  |  yes   |    no    |     yes    | None
    # 31) yes |  yes  |  yes   |    no    |     yes    | self
    # 32) yes |  yes  |  yes   |    no    |     yes    | other
    #
    # 33)  no |  no   |  None  |    n/a   |     n/a    | n/a
    # 34)  no |  no   |  yes   |    yes   |     no     | None
    # 35)  no |  no   |  yes   |    yes   |     no     | self
    # 36)  no |  no   |  yes   |    yes   |     no     | other
    #
    # 37)  no |  yes  |  None  |    n/a   |     n/a    | n/a
    # 38)  no |  yes  |  yes   |    yes   |     no     | None
    # 39)  no |  yes  |  yes   |    yes   |     no     | self
    # 40)  no |  yes  |  yes   |    yes   |     no     | other

    # 41) yes |  no   |  None  |    n/a   |     n/a    | n/a
    # 42) yes |  no   |  yes   |    yes   |     no     | None
    # 43) yes |  no   |  yes   |    yes   |     no     | self
    # 44) yes |  no   |  yes   |    yes   |     no     | other
    #
    # 45) yes |  yes  |  None  |    n/a   |     n/a    | n/a
    # 46) yes |  yes  |  yes   |    yes   |     no     | None
    # 47) yes |  yes  |  yes   |    yes   |     no     | self
    # 48) yes |  yes  |  yes   |    yes   |     no     | other
    #
    # 49)  no |  no   |  None  |    n/a   |     n/a    | n/a
    # 50)  no |  no   |  yes   |    yes   |     yes    | None
    # 51)  no |  no   |  yes   |    yes   |     yes    | self
    # 52)  no |  no   |  yes   |    yes   |     yes    | other
    #
    # 53)  no |  yes  |  None  |    n/a   |     n/a    | n/a
    # 54)  no |  yes  |  yes   |    yes   |     yes    | None
    # 55)  no |  yes  |  yes   |    yes   |     yes    | self
    # 56)  no |  yes  |  yes   |    yes   |     yes    | other

    # 57) yes |  no   |  None  |    n/a   |     n/a    | n/a
    # 58) yes |  no   |  yes   |    yes   |     yes    | None
    # 59) yes |  no   |  yes   |    yes   |     yes    | self
    # 60) yes |  no   |  yes   |    yes   |     yes    | other
    #
    # 61) yes |  yes  |  None  |    n/a   |     n/a    | n/a
    # 62) yes |  yes  |  yes   |    yes   |     yes    | None
    # 63) yes |  yes  |  yes   |    yes   |     yes    | self
    # 64) yes |  yes  |  yes   |    yes   |     yes    | other
    #
    # Notes:
    # 1) Either a) thread ended after register (instantiation) and before
    # doing pair_with, or b) thread ended after a subsequent pair_with
    # (the remote is set to None) did not connect with the target
    # because the target failed to respond. In either case, the SmartEvent
    # was unregistered during clean up triggered by another instantiation,
    # pair_with, or SmartEventRemoteThreadNotAlive error.
    #
    # 2) Thread ended and was unregistered during cleanup. Remote was
    # still alive and went on to do case 1b.
    #
    # 3) Both threads ended and were unregistered during a cleanup.
    #
    # 4) Thread ended, remote went on to pair_with another thread and ended.
    # Both unregistered during cleanup.
    #
    # 5) SmartEvent instantiation started, but not yet completed to the
    # point of doing the registration. This would not be observable from
    # anywhere except perhaps from looking at the dictionaries in the
    # frames.
    #
    # 6) 7) and 8) SmartEvent alive and paired implies being registered,
    # so these cases are not possible except for a code error case.
    #
    # 9) Same as case 1 before cleanup is triggered.
    #
    # 10) Same as case 2 before cleanup is triggered, remote cleaned up.
    #
    # 11) Same as case 3 before cleanup is triggered, remote cleaned up.
    #
    # 12) Same as case 4 before cleanup is triggered, remote cleaned up.
    #
    # 13) SmartEvent alive and registered, not yet paired with remote.
    #
    # 14) SmartEvent alive, registered, in pair_with when remote ended before
    # doing pair_with and cleanup was triggered by some other thread. This is
    # a transitory state that will resolve when the pair_with times out.
    #
    # 15) Thread is alive and is paired to residual remote which ended and
    # was cleaned up.
    #
    # 16) This case can not happen except for a code error or during window
    # where current thread is in pair_with and remote was trying to pair with
    # other1 and then failed when it saw other1 was paired with other2. If
    # current is in pair_with, it will soon raise ThreadPairRemotePairedWithOther.
    #
    # 17) 21) 25) 29) Repeats of #1, 5, 9, 13, respectively.
    #
    # 18) 19) 20) 22) 23) 24) 26) 27) 28) 30) 31) 32) All not possible for
    # remote to be alive and unregistered after the current thread was able
    # to pair with it, except for coding error.
    #
    # 33) 37) 41) 45) Repeats of #1, 5, 9, 13, respectively.
    #
    # 34) 35) 36) same as #2, 3, 4 except remote not yet cleaned up.
    #
    # 38) 39) 40) same as #6, 7, 8, not possible.
    #
    # 42) 43) 44) same as 10, 11, 12 except remote also not yet cleaned up.
    #
    # 46) same as 14 except remote not yet cleaned up.
    #
    # 47) same as 15 except remote not yet cleaned up.
    #
    # 48) same as 16 except remote not yet cleaned up.
    #
    # 49) 53) 57) 61) repeats of 1, 5, 9, 13.
    #
    # 50) Same as 2 except remote tried to pair with other but other did not
    # respond, so remote has its remote as None (set by pair_with when
    # cleaning the residual remote).
    #
    # 51) same as 3, except remote stays alive and points back to current
    # residually.
    #
    # 52) same as 4, except remote stays alive and is paired to other.
    #
    # 54) 55) 56) same as #6, 7, 8, not possible.
    #
    # 58) 59) 60) same as 50) 51) 52) except current not yet cleaned up.
    #
    # 62) current thread in pair_up, remote has not yet called pair_with
    #
    # 63) This is the expected normal operational state where both threads
    # are active, registered, and paired
    #
    # 64) current is in pair_with waiting for remote to respond, but remote
    # has paired with other. Current will soon discover that remote
    # is paired with other and raise ThreadPairRemotePairedWithOther.
    #
    # Based on the above, the basic states can be summarized as:
    # 1) alive/registered
    # 2) not_alive/registered
    # 3) not_alive/unregistered
    #
    # the basic states flows are: action: instantiate
    #                             -> 1
    #                                action thread ends
    #                                -> 2
    #                                   action cleanup
    #                                   -> 3
    # Note that once a thread ends, it can not be resurrected.
    #
    # The enhanced states include a paired component
    # 1, 2, and 3 can be paired with None or with a 1, 2, or 3 (12
    # combinations). We will denote the states with the pairing as:
    #     current_state:None or current_state:remote_state
    #
    # Note that a remote can become not alive and the current SmartEvent,
    # if alive, can pair with a new alive remote.
    #
    # The enhanced flow:
    # instantiate -> 1:None
    #
    # 1:None -> pair_with remote_n -> 1:1
    #        -> current ends -> 2:None
    #
    # 1:1 -> remote ends -> 1:2
    #     -> current ends -> 2:1
    #
    # 1:2 -> cleanup -> 1:3
    #     -> current ends -> 2:2
    #     -> current pairs with new remote_n+1 -> 1:1
    #     -> current pairs, but remote does not pair -> 1:None
    #
    # 1:3 -> current ends -> 2:3
    #     -> current pairs with new remote_n+1 -> 1:1
    #     -> current pairs, but remote does not pair -> 1:None
    #
    # 2:None -> cleanup -> 3:None
    #
    # 2:1 -> cleanup -> 3:1
    #     -> remote ends -> 2:2
    #     -> remote pairs with new -> 2:1 (no change, except remote no
    #                                      longer points back to current,
    #                                      instead points to new remote)
    #     -> remote pairs with new that fails to complete -> 2:1 (no change,
    #                                      except remote no longer points
    #                                      back to current, instead points
    #                                      to None)
    #
    # 2:2 -> cleanup -> 3:3
    #
    # 2:3 -> cleanup -> 3:3
    #
    # 3:None (end state - no action can change this)
    #
    # 3:1 -> remote ends -> 3:2
    #     -> remote pairs with new -> 3:1 (no change, except remote no
    #                                      longer points back to current,
    #                                      instead points to new remote)
    #     -> remote pairs with new that fails to complete -> 3:1 (no change,
    #                                      except remote no longer points
    #                                      back to current, instead points
    #                                      to None)
    #
    # 3:2 -> cleanup -> 3:3
    #
    # 3:3 (end state - no action can change this
    #
    ###########################################################################

    ###########################################################################
    # Constants
    ###########################################################################
    pause_until_TIMEOUT: Final[int] = 16
    # pair_with_TIMEOUT: Final[int] = 60

    ###########################################################################
    # Registry
    ###########################################################################
    # _registry_lock = threading.Lock()
    # _registry: dict[str, "SmartEvent"] = {}

    ###########################################################################
    # SharedPairStatus Data Class
    ###########################################################################
    @dataclass
    class SharedPairStatus:
        """Shared area for status between paired SmartEvent objects."""
        status_lock = threading.Lock()
        sync_cleanup = False

    ###########################################################################
    # __init__
    ###########################################################################
    def __init__(
            self, *,
            name: str,
            thread: Optional[threading.Thread] = None
            ) -> None:
        """Initialize an instance of the SmartEvent class.

        Args:
            name: name to be used to refer to this SmartEvent
            thread: specifies the thread to use instead of the current
                      thread - needed when SmartEvent is instantiate in a
                      class that inherits threading.Thread in which case
                      thread=self is required

        Raises:
            ThreadPairIncorrectNameSpecified: Attempted SmartEvent instantiation
                                      with incorrect name of {name}.

        """
        ThreadPair.__init__(self, name=name, thread=thread)

        self.event = threading.Event()

        self.status: Union[SmartEvent.SharedPairStatus, Any] = None

        self.code: Any = None
        self.wait_wait: bool = False
        self.sync_wait: bool = False
        self.wait_timeout_specified: bool = False
        self.deadlock: bool = False
        self.conflict: bool = False

        # self.logger = logging.getLogger(__name__)
        # self.debug_logging_enabled = self.logger.isEnabledFor(logging.DEBUG)

    ###########################################################################
    # _reset
    ###########################################################################
    def _reset(self) -> None:
        """Reset the SmartEvent flags."""
        self.sync_wait = False
        self.wait_timeout_specified = False
        self.wait_wait = False

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
    # pair_with
    ###########################################################################
    def pair_with(self, *,
                  remote_name: str,
                  log_msg: Optional[str] = None,
                  timeout: Union[int, float] = 60  # pair_with_TIMEOUT
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
            ThreadPairAlreadyPairedWithRemote: A pair_with request by
                                       {self.name} with target of
                                       remote_name = {remote_name}
                                       can not be done since
                                       {self.name} is already paired
                                       with {self.remote.name}.
            ThreadPairIncorrectNameSpecified: Attempted SmartEvent
            pair_with()
                                      with incorrect remote name of
                                      {remote_name}.
            ThreadPairRemotePairedWithOther: {self.name} detected that remote
                                {remote_name} is already paired with
                                {self.remote.remote.name}.
            ThreadPairPairWithSelfNotAllowed: {self.name} attempted to pair
                                    with itself using remote_name of
                                    {remote_name}.
            ThreadPairPairWithTimedOut: {self.name} timed out on a
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
        caller_info = ''
        if log_msg and self.debug_logging_enabled:
            caller_info = get_formatted_call_sequence(latest=1, depth=1)
            self.logger.debug(f'pair_with() entered by {self.name} to '
                              f'pair with {remote_name}. '
                              f'{caller_info} {log_msg}')
        ThreadPair.pair_with(self,
                             remote_name=remote_name,
                             timeout=timeout)

        # If the remote has already created the
        # shared status area, use it. Otherwise, we
        # create it and the remote will use that.
        if self.remote.status is not None:
            self.status = self.remote.status
        else:
            self.status = self.SharedPairStatus()

        # if caller specified a log message to issue
        if log_msg and self.debug_logging_enabled:
            self.logger.debug(f'pair_with() exiting - {self.name} now '
                              f'paired with {remote_name}. '
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
               **SmartEventRemoteThreadNotAlive** error.

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
                #    raise the SmartEventWaitDeadlockDetected error. The remote could
                #    recover, in which case this resume will complete,
                #    or the thread could become inactive, in which case
                #    resume will see that and raise (via _check_remote
                #    method) the SmartEventRemoteThreadNotAlive error.
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
            SmartEventConflictDeadlockDetected: A ``sync()`` request was made by one
                                        thread and a ``wait()`` request was
                                        made by the other thread.

        Notes:
            1) If one thread makes a ``sync()`` request without **timeout**
               specified, and the other thread makes a ``wait()`` request to
               an event that was not **pre-resumed**, also without **timeout**
               specified, then both threads will recognize and raise a
               **SmartEventConflictDeadlockDetected** error. This is needed since
               neither the ``sync()`` request nor the ``wait()`` request has
               any chance of completing. The ``sync()`` request is waiting for
               a matching ``sync()`` request and the ``wait()`` request is
               waiting for a matching ``resume()`` request.
            2) If one thread makes a ``sync()`` request and the other thread
               becomes not alive, the ``sync()`` request raises a
               **SmartEventRemoteThreadNotAlive** error.

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
                        if not self.status.sync_cleanup:  # remote exited ph 2
                            break

                if not (self.wait_timeout_specified
                        or self.remote.wait_timeout_specified
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
                        'SmartEventConflictDeadlockDetected. '
                        f'self.remote.wait_wait = {self.remote.wait_wait}, '
                        f'self.event.is_set() = {self.event.is_set()}, '
                        f'self.remote.deadlock = {self.remote.deadlock}, '
                        f'self.remote.conflict = {self.remote.conflict}, '
                        f'self.remote.wait_timeout_specified = '
                        f'{self.remote.wait_timeout_specified}, '
                        f'self.wait_timeout_specified = '
                        f'{self.wait_timeout_specified}')
                    self.sync_wait = False
                    self.conflict = False
                    raise SmartEventConflictDeadlockDetected(
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
            SmartEventWaitDeadlockDetected: Both threads are deadlocked, each waiting
                                    on the other to ``resume()`` their event.
            SmartEventConflictDeadlockDetected: A ``sync()`` request was made by
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
               **SmartEventConflictDeadlockDetected** error. This is needed since
               neither the ``sync()`` request nor the ``wait()`` request has
               any chance of completing. The ``sync()`` request is waiting for
               a matching ``sync()`` request and the ``wait()`` request is
               waiting for a matching ``resume()`` request.
            2) If one thread makes a ``wait()`` request to an event that
               has not been **pre-resumed**, and without **timeout**
               specified, and the other thread makes a ``wait()`` request to
               an event that was not **pre-resumed**, also without **timeout**
               specified, then both threads will recognize and raise a
               **SmartEventWaitDeadlockDetected** error. This is needed since neither
               ``wait()`` request has any chance of completing as each
               ``wait()`` request is waiting for a matching ``resume()``
               request.
            3) If one thread makes a ``wait()`` request and the other thread
               becomes not alive, the ``wait()`` request raises a
               **SmartEventRemoteThreadNotAlive** error.

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
                    self.wait_timeout_specified = False
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
                                      'SmartEventConflictDeadlockDetected')
                    raise SmartEventConflictDeadlockDetected(
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
                                      'SmartEventWaitDeadlockDetected')
                    raise SmartEventWaitDeadlockDetected(
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
                    self.wait_timeout_specified = False
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
            SmartEventWaitUntilTimeout: The pause_until method timed out.

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
                                      'SmartEventWaitUntilTimeout')
                    raise SmartEventWaitUntilTimeout(
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
                                      'SmartEventWaitUntilTimeout')
                    raise SmartEventWaitUntilTimeout(
                        'The pause_until method timed out. '
                        f'Call sequence: {get_formatted_call_sequence(1,1)}')

                time.sleep(t_out)

    ###########################################################################
    # _check_remote
    ###########################################################################
    def _check_remote(self) -> None:
        """Check the remote flags for consistency and whether remote is alive.

        Raises:
            SmartEventInconsistentFlagSettings: The remote ThreadEvent flag settings
                                        are not valid.
            SmartEventRemoteThreadNotAlive: The alpha or beta thread is not alive

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
                              'SmartEventInconsistentFlagSettings. '
                              f'wait_wait: {self.remote.wait_wait}, '
                              f'sync_wait: {self.remote.sync_wait}, '
                              f'deadlock: {self.remote.deadlock}, '
                              f'conflict: {self.remote.conflict}, ')

            self._reset()  # reset flags

            raise SmartEventInconsistentFlagSettings(
                f'Thread {self.name} detected remote {self.remote.name} '
                f'SmartEvent flag settings are not valid.')

        if not self.remote.thread.is_alive():
            self.logger.debug(f'{self.name} raising '
                              'SmartEventRemoteThreadNotAlive.'
                              'Call sequence:'
                              f' {get_formatted_call_sequence()}')
            with self._registry_lock:
                # Remove any old entries
                self._clean_up_registry()

            self._reset()  # reset flags

            raise SmartEventRemoteThreadNotAlive(
                f'{self.name} has detected that {self.remote.name} '
                'thread is not alive.')
