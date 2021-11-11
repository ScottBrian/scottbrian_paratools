"""Module smart_thread.

===========
SmartThread
===========

The SmartThread class provides functions for events and comminuication between threads.

:Example: create a SmartThread for mainline and a thread to use

>>> from scottbrian_paratools.smart_thread import SmartThread
>>> import threading
>>> import time
>>> class ShareMsg(SmartThread):
...     def __init__(self, name) -> None:
...         SmartThread.__init__(self, name)
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


The smart_thread module contains:

    1) SmartThread class with methods:

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


class SmartThreadIncorrectGroupNameSpecified(SmartThreadError):
    """SmartThread exception for a group_name that is not a str."""


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


###############################################################################
# SmartThread class
###############################################################################
class SmartThread:
    """Provides a pairing between two classes in separate threads."""

    ###########################################################################
    # Constants
    ###########################################################################
    pair_with_TIMEOUT: Final[int] = 60

    ###########################################################################
    # Registry
    ###########################################################################
    # The _registry is a dictionary of dictionaries. The first level is accessed via the group_name, and the
    # second level by name provided by the caller of _register. The _registry lock protects the entire
    # registry, meaning the top level.
    _registry_lock = threading.Lock()
    _registry: dict[str, dict[str, "SmartThread"]] = {}

    ###########################################################################
    # __init__
    ###########################################################################
    def __init__(
            self, *,
            name: str,
            group_name: Optional[str] = 'group1',
            thread: Optional[threading.Thread] = None
            ) -> None:
        """Initialize an instance of the SmartThread class.

        Args:
            name: name to be used to refer to this SmartThread
            group_name: name of group that the thread is to be associated with. This is used to allow more than one
                          pair in the same space.
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

        if not isinstance(group_name, str):
            raise SmartThreadIncorrectGroupNameSpecified(
                'Attempted SmartThread instantiation '
                f'with incorrect group_name of {group_name}.')
        self.group_name = group_name

        if thread:
            self.thread = thread
        else:
            self.thread = threading.current_thread()

        self.remote: Union[SmartThread, Any] = None

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

        :Example: instantiate a SmartThread and call repr

        >>> from scottbrian_paratools.smart_event import SmartThread
        >>> smart_thread = SmartThread(name='alpha')
        >>> repr(smart_thread)
        SmartThread(name="alpha")

        """
        if TYPE_CHECKING:
            __class__: Type[SmartThread]
        classname = self.__class__.__name__
        parms = f'group_name="{self.group_name}", name="{self.name}"'

        return f'{classname}({parms})'

    # ###########################################################################
    # # register
    # ###########################################################################
    # def _register(self) -> None:
    #     """Register SmartThread in the class registry.
    #
    #     Raises:
    #         SmartThreadIncorrectNameSpecified: The name for SmartThread must be of type
    #                                   str.
    #         SmartThreadNameAlreadyInUse: An entry for a SmartThread with name = *name*
    #                             is already registered and paired with
    #                             *remote name*.
    #
    #     Notes:
    #         1) Any old entries for SmartThreads whose threads are not alive
    #            are removed when this method is called by calling
    #            _clean_up_registry().
    #         2) Once a thread become not alive, it can not be resurrected.
    #            The SmartThread is bound to the thread it starts with. If the
    #            remote SmartThread thread that the SmartThread is paired with
    #            becomes not alive, we allow this SmartThread to pair with a new
    #            SmartThread on a new thread.
    #
    #     """
    #     with self.__class__._registry_lock:
    #         self.logger.debug(f'self.__class__.__name__ = {self.__class__.__name__}')
    #         self.logger.debug(f'registry_lock id = {id(self.__class__._registry_lock)}')
    #         # Remove any old entries
    #         self._clean_up_registry()
    #
    #         self.logger.debug(f'{self.__class__.__name__} registry id = {id(self.__class__._registry)}')
    #         self.logger.debug(f'{self.__class__.__name__} registry = {self.__class__._registry}')
    #
    #         # Make sure name is valid
    #         if not isinstance(self.name, str):
    #             raise SmartThreadIncorrectNameSpecified(
    #                 'The name for SmartThread must be of type str.')
    #
    #         # Make sure name not already taken
    #         if self.name in self.__class__._registry:
    #             raise SmartThreadNameAlreadyInUse(
    #                 f'An entry for a SmartThread with name = {self.name} is '
    #                 'already registered.')
    #
    #         # Add new SmartThread
    #         registry_copy = self.__class__._registry.copy()
    #         registry_copy[self.name] = self
    #         self.__class__._registry = registry_copy

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
            self.logger.debug(f'_registry_lock obtained, group_name = {self.group_name}, '
                              f'thread_name = {self.name}, class name = {self.__class__.__name__}')
            # if self.__class__.__name__ not in SmartThread._registry:  # first entry for this class
            #     SmartThread._registry[self.__class__.__name__] = {self.name: self}  # init registry for this class
            #     self.logger.debug(f'{self.name} registered first entry for class {self.__class__.__name__}')
            if self.group_name not in SmartThread._registry:  # first entry for this group
                SmartThread._registry[self.group_name] = {self.name: self}  # init registry for this class
                self.logger.debug(f'{self.name} registered first entry for group {self.group_name}')
            else:
                # Remove any old entries
                self._clean_up_registry()

                # Make sure name not already taken
                if self.name in SmartThread._registry[self.group_name]:
                    raise SmartThreadNameAlreadyInUse(
                        f'An entry for a SmartThread with name = {self.name} is '
                        'already registered.')

                # Add new SmartThread
                SmartThread._registry[self.group_name][self.name] = self
                self.logger.debug(f'{self.name} registered not first entry for group {self.group_name}')

    ###########################################################################
    # _clean_up_registry
    ###########################################################################
    #@classmethod
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
        for key, item in SmartThread._registry[self.group_name].items():
            # self.logger.debug(f'key {key} item {item}')
            if not item.thread.is_alive():
                keys_to_del.append(key)

            # if (item.remote is not None
            #         and not item.remote.thread.is_alive()):
            #     keys_to_del.append(key)

            if key != item.name:
                raise SmartThreadErrorInRegistry(f'Registry item with key {key} '
                                                f'has non-matching item.name '
                                                f'of {item.name}.')

        for key in keys_to_del:
            del SmartThread._registry[self.group_name][key]
            self.logger.debug(f'{key} removed from registry for group {self.group_name}')

    # ###########################################################################
    # # _clean_up_registry
    # ###########################################################################
    # #@classmethod
    # def _clean_up_registry(self) -> None:
    #     """Clean up any old not alive items in the registry.
    #
    #     Raises:
    #         SmartThreadErrorInRegistry: Registry item with key {key} has non-matching
    #                          item.name of {item.name}.
    #
    #     Notes:
    #         1) Must be called holding _registry_lock
    #
    #     """
    #     # Remove any old entries
    #     keys_to_del = []
    #     for key, item in self.__class__._registry.items():
    #         # self.logger.debug(f'key {key} item {item}')
    #         if not item.thread.is_alive():
    #             keys_to_del.append(key)
    #
    #         # if (item.remote is not None
    #         #         and not item.remote.thread.is_alive()):
    #         #     keys_to_del.append(key)
    #
    #         if key != item.name:
    #             raise SmartThreadErrorInRegistry(f'Registry item with key {key} '
    #                                   f'has non-matching item.name '
    #                                   f'of {item.name}.')
    #
    #     for key in keys_to_del:
    #         del self.__class__._registry[key]
    #         self.logger.debug(f'{key} removed from registry')

    ###########################################################################
    # pair_with
    ###########################################################################
    def pair_with(self, *,
                  remote_name: str,
                  log_msg: Optional[str] = None,
                  timeout: Union[int, float] = 60  # pair_with_TIMEOUT
                  ) -> None:
        """Establish a connection with the remote thread.

        After the SmartThread object is instantiated by both threads,
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
            SmartThreadAlreadyPairedWithRemote: A pair_with request by
                                       {self.name} with target of
                                       remote_name = {remote_name}
                                       can not be done since
                                       {self.name} is already paired
                                       with {self.remote.name}.
            SmartThreadIncorrectNameSpecified: Attempted SmartThread pair_with()
                                      with incorrect remote name of
                                      {remote_name}.
            SmartThreadRemotePairedWithOther: {self.name} detected that remote
                                {remote_name} is already paired with
                                {self.remote.remote.name}.
            SmartThreadPairWithSelfNotAllowed: {self.name} attempted to pair
                                    with itself using remote_name of
                                    {remote_name}.
            SmartThreadPairWithTimedOut: {self.name} timed out on a
                                pair_with() request with
                                remote_name = {remote_name}.

        Notes:
            1) A ``pair_with()`` request can only be done when the
               SmartThread is not already paired with another thread.
            2) Once the ''pair_with()'' request completes, the SmartThread is
               ready to issue requests.
            3) Unlike the other SmartEvent requests, the ''pair_with()''
               request is unable to detect when the remote thread becomes not
               alive. This is why the *timeout* argument is required, either
               explicitly or by default.

        :Example: instantiate SmartThread and issue ``pair_with()`` requests

        >>> from scottbrian_paratools.smart_event import SmartThread
        >>> import threading
        >>> def f1() -> None:
        ...     s_event = SmartThread(name='beta')
        ...     s_event.pair_with(remote_name='alpha')
        ...     s_event.wait()

        >>> a_smart_event = SmartThread(name='alpha')
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
                              f'pair with {remote_name} in group {self.group_name}. '
                              f'{caller_info} {log_msg}')

        self.verify_current_remote(skip_pair_check=True)
        if not isinstance(remote_name, str):
            raise SmartThreadIncorrectNameSpecified('Attempted SmartThread pair_with() '
                                         f'with incorrect remote name of'
                                         f' {remote_name}.')

        if remote_name == self.name:
            raise SmartThreadPairWithSelfNotAllowed(f'{self.name} attempted to pair'
                                         'with itself using remote_name of '
                                         f' {remote_name}.')

        # check to make sure not already paired (even to same remote)
        if self.remote is not None:
            if self.remote.thread.is_alive():
                raise SmartThreadAlreadyPairedWithRemote('A pair_with request by '
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
            # with self.__class__._registry_lock:
            with SmartThread._registry_lock:
                # Remove any old entries
                self._clean_up_registry()

                # find target in registry
                # we check to see whether the remote points to us, and if not
                # we need to keep trying until we time out in case we are
                # waiting for the remote old to get cleaned up
                if self.remote is None:  # if target not yet found
                    for key, item in SmartThread._registry[self.group_name].items():
                        if (key == remote_name
                                and (item.remote is None
                                     or item.remote.name == self.name)):
                            self.remote = item
                            break
                # do not make the following an else - we might have just found the remote in the above code
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
                            raise SmartThreadRemotePairedWithOther(
                                f'{self.name} detected that remote '
                                f'{remote_name} is already paired with '
                                f'{diag_remote_name}.')

                # check whether we are out of time
                if timeout < (time.time() - start_time):
                    self.remote = None
                    self.logger.debug(f'{self.name} timed out on a '
                                      'pair_with() request with '
                                      f'remote_name = {remote_name}.')
                    raise SmartThreadPairWithTimedOut(f'{self.name} timed out on a '
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
        if not skip_pair_check:
            self.verify_paired()

    ###########################################################################
    # check_remote
    ###########################################################################
    def check_remote(self) -> None:
        """Check whether remote is alive.

        Raises:
            SmartThreadRemoteThreadNotAlive: The remote thread is not alive.

        """
        self.verify_paired()
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
    def verify_paired(self) -> None:
        """Verify that we are paired.

        Raises:
            SmartThreadNotPaired: Both threads must be paired before any
                                   SmartThread services can be called.

        """
        # make sure that remote exists and it points back to us
        if (self.remote is None
                or self.remote.remote is None
                or self.remote.remote.name != self.name):
            # collect diag info and raise error
            diag_remote_remote = None
            diag_name = None
            if self.remote is not None:
                diag_remote_remote = self.remote.remote
                if self.remote.remote is not None:
                    diag_name = self.remote.remote.name
            self.logger.debug(f'{self.name} raising SmartThreadNotPaired. '
                              f'Remote = {self.remote}, '
                              f'remote.remote = {diag_remote_remote}, '
                              f'remote name = {diag_name}')
            raise SmartThreadNotPaired(
                'Both threads must be paired before any '
                'SmartThread services can be called. '
                f'Call sequence: {get_formatted_call_sequence(1, 2)}')
