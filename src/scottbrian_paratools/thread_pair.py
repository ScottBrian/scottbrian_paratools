"""Module thread_pair.

==========
ThreadPair
==========

The ThreadPair class is used as a base class for SmartEvent and ThreadComm.

:Example: create a SmartEvent for mainline and a thread to use

>>> from scottbrian_paratools.thread_pair import ThreadPair
>>> import threading
>>> import time
>>> class ShareMsg(ThreadPair):
...     def __init__(self, name) -> None:
...         ThreadPair.__init__(self, name)
...         self.message: Any = 0
...     def give_msg(self, msg: Any) -> None:
...         self.message = msg
...     def get_msg(self) -> Any:
...         return self.remote.message
>>> def f1() -> None:
...     print('f1 beta entered')
...     f1_msg = ShareMsg(name='beta')
...     f1_msg.pair_with(remote_name='alpha')
...     print('f1 beta giving alpha a message')
...     f1_msg.give_msg(42)
...     time.sleep(3)  # allow time for alpha to get msg
...     print('f1 beta exiting')
>>> ml_msg = ShareMsg(name='alpha')
>>> f1_thread = threading.Thread(target=f1)
>>> print('alpha about to start the beta thread')
>>> f1_thread.start()  # start f1 beta
>>> ml_msg.pair_with(remote_name='beta')
>>> time.sleep(2)  # give beta time to give message
>>> print(f'message from f1 beta is {ml_msg.get_msg()}')
alpha about to start the beta thread
f1 beta entered
f1 beta giving alpha a message
message from f1 beta is 42
f1 beta exiting


The thred_pair module contains:

    1) ThreadPair class with methods:

       a. pair_with

"""
###############################################################################
# Standard Library
###############################################################################
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


###############################################################################
# SmartEvent class exceptions
###############################################################################
class ThreadPairError(Exception):
    """Base class for exceptions in this module."""
    pass


class ThreadPairAlreadyPairedWithRemote(ThreadPairError):
    """SmartEvent exception for pair_with that is already paired."""
    pass

class ThreadPairDetectedOpFromForeignThread(ThreadPairError):
    """SmartEvent exception for attempted op from unregistered thread."""
    pass


class ThreadPairErrorInRegistry(ThreadPairError):
    """SmartEvent exception for registry error."""


class ThreadPairIncorrectNameSpecified(ThreadPairError):
    """SmartEvent exception for a name that is not a str."""


class ThreadPairNameAlreadyInUse(ThreadPairError):
    """SmartEvent exception for using a name already in use."""
    pass


class ThreadPairNotPaired(ThreadPairError):
    """SmartEvent exception for alpha or beta thread not registered."""
    pass


class ThreadPairPairWithSelfNotAllowed(ThreadPairError):
    """SmartEvent exception for pair_with target is self."""


class ThreadPairPairWithTimedOut(ThreadPairError):
    """SmartEvent exception for pair_with that timed out."""


class ThreadPairRemotePairedWithOther(ThreadPairError):
    """SmartEvent exception for pair_with target already paired."""


###############################################################################
# ThreadPair class
###############################################################################
class ThreadPair:
    """Provides a pairing between two classes in separate threads."""

    ###########################################################################
    # Constants
    ###########################################################################
    pair_with_TIMEOUT: Final[int] = 60

    ###########################################################################
    # Registry
    ###########################################################################
    _registry_lock = threading.Lock()
    _registry: dict[str, "SmartEvent"] = {}

    ###########################################################################
    # __init__
    ###########################################################################
    def __init__(
            self, *,
            name: str,
            thread: Optional[threading.Thread] = None
            ) -> None:
        """Initialize an instance of the ThreadPair class.

        Args:
            name: name to be used to refer to this ThreadPair
            thread: specifies the thread to use instead of the current
                      thread - needed when ThreadPair is instantiated in a
                      class that inherits threading.Thread in which case
                      thread=self is required

        Raises:
            ThreadPairIncorrectNameSpecified: Attempted SmartEvent instantiation
                                      with incorrect name of {name}.

        """
        if not isinstance(name, str):
            raise ThreadPairIncorrectNameSpecified('Attempted SmartEvent instantiation '
                                         f'with incorrect name of {name}.')
        self.name = name

        if thread:
            self.thread = thread
        else:
            self.thread = threading.current_thread()

        self.remote: Union[ThreadPair, Any] = None

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

        >>> from scottbrian_paratools.smart_event import ThreadPair
        >>> thread_pair = ThreadPair(name='alpha')
        >>> repr(thread_pair)
        ThreadPair(name="alpha")

        """
        if TYPE_CHECKING:
            __class__: Type[SmartEvent]
        classname = self.__class__.__name__
        parms = f'name="{self.name}"'

        return f'{classname}({parms})'

    ###########################################################################
    # register
    ###########################################################################
    def _register(self) -> None:
        """Register ThreadPair in the class registry.

        Raises:
            ThreadPairIncorrectNameSpecified: The name for ThreadPair must be of type
                                      str.
            ThreadPairNameAlreadyInUse: An entry for a ThreadPair with name = *name*
                                is already registered and paired with
                                *remote name*.

        Notes:
            1) Any old entries for ThreadPairs whose threads are not alive
               are removed when this method is called by calling
               _clean_up_registry().
            2) Once a thread become not alive, it can not be resurrected.
               The ThreadPair is bound to the thread it starts with. If the
               remote ThreadPair thread that the ThreadPair is paired with
               becomes not alive, we allow this ThreadPair to pair with a new
               ThreadPair on a new thread.

        """
        with self._registry_lock:
            # Remove any old entries
            self._clean_up_registry()

            # Make sure name is valid
            if not isinstance(self.name, str):
                raise ThreadPairIncorrectNameSpecified(
                    'The name for ThreadPair must be of type str.')

            # Make sure name not already taken
            if self.name in self._registry:
                raise ThreadPairNameAlreadyInUse(
                    f'An entry for a ThreadPair with name = {self.name} is '
                    'already registered.')

            # Add new ThreadPair
            self._registry[self.name] = self

    ###########################################################################
    # _clean_up_registry
    ###########################################################################
    def _clean_up_registry(self) -> None:
        """Clean up any old not alive items in the registry.

        Raises:
            ThreadPairErrorInRegistry: Registry item with key {key} has non-matching
                             item.name of {item.name}.

        Notes:
            1) Must be called holding _registry_lock

        """
        # Remove any old entries
        keys_to_del = []
        for key, item in self._registry.items():
            # self.logger.debug(f'key {key} item {item}')
            if not item.thread.is_alive():
                keys_to_del.append(key)

            # if (item.remote is not None
            #         and not item.remote.thread.is_alive()):
            #     keys_to_del.append(key)

            if key != item.name:
                raise ThreadPairErrorInRegistry(f'Registry item with key {key} '
                                      f'has non-matching item.name '
                                      f'of {item.name}.')

        for key in keys_to_del:
            del self._registry[key]
            self.logger.debug(f'{key} removed from registry')

    ###########################################################################
    # pair_with
    ###########################################################################
    def pair_with(self, *,
                  remote_name: str,
                  log_msg: Optional[str] = None,
                  timeout: Union[int, float] = 60  # pair_with_TIMEOUT
                  ) -> None:
        """Establish a connection with the remote thread.

        After the ThreadPair object is instantiated by both threads,
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
            ThreadPairIncorrectNameSpecified: Attempted ThreadPair pair_with()
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
               ThreadPair is not already paired with another thread.
            2) Once the ''pair_with()'' request completes, the ThreadPair is
               ready to issue requests.
            3) Unlike the other SmartEcvent requests, the ''pair_with()''
               request is unable to detect when the remothe thread become not
               alive. This is why the *timeout* argument is required, either
               explicitly or by default.

        :Example: instantiate ThreadPair and issue ``pair_with()`` requests

        >>> from scottbrian_paratools.smart_event import ThreadPair
        >>> import threading
        >>> def f1() -> None:
        ...     s_event = ThreadPair(name='beta')
        ...     s_event.pair_with(remote_name='alpha')
        ...     s_event.wait()

        >>> a_smart_event = ThreadPair(name='alpha')
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
                              f'pair with {remote_name}. '
                              f'{caller_info} {log_msg}')

        self._verify_current_remote(skip_pair_check=True)
        if not isinstance(remote_name, str):
            raise ThreadPairIncorrectNameSpecified('Attempted ThreadPair pair_with() '
                                         f'with incorrect remote name of'
                                         f' {remote_name}.')

        if remote_name == self.name:
            raise ThreadPairPairWithSelfNotAllowed(f'{self.name} attempted to pair'
                                         'with itself using remote_name of '
                                         f' {remote_name}.')

        # check to make sure not already paired (even to same remote)
        if self.remote is not None:
            if self.remote.thread.is_alive():
                raise ThreadPairAlreadyPairedWithRemote('A pair_with request by '
                                              f'{self.name} with target of '
                                              f'remote_name = {remote_name} '
                                              f'can not be done since '
                                              f'{self.name} is already paired '
                                              f'with {self.remote.name}.')
            else:
                # we wait until now to clean the residual for diagnostic
                # purposes for the derived class which may want to raise an
                # error when it attempts to access the remote thread
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
                        if self.remote.remote is self:  # if us
                            # If the remote has already created the
                            # shared status area, use it. Otherwise, we
                            # create it and the remote will use that.
                            # if self.remote.status is not None:
                            #     self.status = self.remote.status
                            # else:
                            #     self.status = self.SharedPairStatus()

                            break  # we are now paired
                        elif self.remote.remote.thread.is_alive():
                            diag_remote_name = self.remote.remote.name
                            self.remote = None
                            self.logger.debug(f'{self.name} unable to pair '
                                              f'with {remote_name} because '
                                              f'{remote_name} is paired with '
                                              f'{diag_remote_name}.')
                            raise ThreadPairRemotePairedWithOther(
                                f'{self.name} detected that remote '
                                f'{remote_name} is already paired with '
                                f'{diag_remote_name}.')

                # check whether we are out of time
                if timeout < (time.time() - start_time):
                    self.remote = None
                    self.logger.debug(f'{self.name} timed out on a '
                                      'pair_with() request with '
                                      f'remote_name = {remote_name}.')
                    raise ThreadPairPairWithTimedOut(f'{self.name} timed out on a '
                                           'pair_with() request with '
                                           f'remote_name = {remote_name}.')

            # pause to allow other side to run
            time.sleep(0.1)

        # if caller specified a log message to issue
        if log_msg and self.debug_logging_enabled:
            self.logger.debug(f'pair_with() exiting - {self.name} now '
                              f'paired with {remote_name}. '
                              f'{caller_info} {log_msg}')

    ###########################################################################
    # _verify_current_remote
    ###########################################################################
    def _verify_current_remote(self,
                               skip_pair_check: Optional[bool] = False
                               ) -> None:
        """Get the current and remote ThreadEvent objects.

        Args:
            skip_pair_check: used by pair_with since the pairing in
                               not yet done

        Raises:
            ThreadPairNotPaired: Both threads must be paired before any ThreadPair
                         services can be called.
            ThreadPairDetectedOpFromForeignThread: Any ThreadPair services must be
                                           called from the thread that
                                           originally instantiated the
                                           ThreadPair.

        """
        # We check for foreign thread first before checking for pairing
        # since we do not want a user who attempts to use SmartEvent from
        # a different thread to get a ThreadPairNotPaired error first and think
        # that the fix it to simply call pair_with from the foreign
        # thread.
        if self.thread is not threading.current_thread():
            self.logger.debug(f'{self.name } raising '
                              'ThreadPairDetectedOpFromForeignThread')
            raise ThreadPairDetectedOpFromForeignThread(
                'Any SmartEvent services must be called from the thread '
                'that originally instantiated the SmartEvent. '
                f'Call sequence: {get_formatted_call_sequence(1,2)}')

        # make sure that remote exists and it points back to us
        if (not skip_pair_check
                and (self.remote is None
                     or self.remote.remote is None
                     or self.remote.remote.name != self.name)):
            self.logger.debug(f'{self.name} raising ThreadPairNotPaired')
            raise ThreadPairNotPaired(
                'Both threads must be paired before any '
                'SmartEvent services can be called. '
                f'Call sequence: {get_formatted_call_sequence(1,2)}')
