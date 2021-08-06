"""Module se_lock.

========
SELock
========

The SELock is a shared/exclusive lock that you can use to safely read
and write shared resources in a multi-threaded application.

:Example: use SELock to coordinate access to a shared resource



>>> from scottbrian_utils.se_lock import SELock
>>> a = 0
>>> a_lock = SELock()
>>> # Get lock in shared mode
>>> with a_lock(SELock.SHARE):  # read a
>>>     print(a)

>>> # Get lock in exclusive mode
>>> with a_lock(SELock.EXCL):  # write to a
>>>     a = 1
>>>     print(a)


The se_lock module contains:

    1) SELock class with methods:

       a. obtain_lock
       b. release_lock
    2) Error exception classes:

       a. IncorrectModeSpecified

    3) SELock context manager

"""
# import time
import threading
# import queue
# import inspect

# from datetime import timedelta
# from typing import (Any, Callable, cast, Dict, Final, NamedTuple, Optional,
#                     Tuple, Type, TYPE_CHECKING, TypeVar, Union)
from typing import (Any, Final, List, NamedTuple, Type, TYPE_CHECKING)
# import functools
# from wrapt.decorators import decorator  # type: ignore
# from scottbrian_utils.diag_msg import diag_msg

import logging

logger = logging.getLogger(__name__)


###############################################################################
# SELock class exceptions
###############################################################################
class SELockError(Exception):
    """Base class for exceptions in this module."""
    pass


class IncorrectModeSpecified(SELockError):
    """SELock exception for an incorrect mode specification."""
    pass


class AttemptedReleaseOfUnownedLock(SELockError):
    """SELock exception for attempted release of unowned lock."""
    pass


###############################################################################
# SELock Class
###############################################################################
class SELock:
    """Provides a share/exclusive lock.

    The SELock class is used to coordinate read/write access to shared
    resources in a multi-threaded application.
    """

    class LockWaiter(NamedTuple):
        """NamedTuple for the lock request queue item."""
        mode: int
        event: threading.Event

    SHARE: Final[int] = 1
    EXCL: Final[int] = 2

    RC_OK: Final[int] = 0

    ###########################################################################
    # init
    ###########################################################################
    def __init__(self) -> None:
        """Initialize an instance of the SELock class.

        :Example: instantiate an SELock

        >>> from scottbrian_utils.se_lock import SELock
        >>> se_lock = SELock()
        >>> print(se_lock)
        SELock()

        """
        #######################################################################
        # Set vars
        #######################################################################
        self.se_lock_lock = threading.Lock()
        self.owner_count = 0  # 0 is free, >0 is share count, -1 is exclusive
        self.wait_q: List[SELock.LockWaiter] = []

    ###########################################################################
    # len
    ###########################################################################
    def __len__(self) -> int:
        """Return the number of items in the wait_q.

        Returns:
            The number of entries in the wait_q as an integer

        :Example: instantiate a se_lock and get the len

        >>> from scottbrian_utils.se_lock import SELock
        >>> a_lock = SELock()
        >>> print(len(a_lock))
        0

        """
        return len(self.wait_q)

    ###########################################################################
    # repr
    ###########################################################################
    def __repr__(self) -> str:
        """Return a representation of the class.

        Returns:
            The representation as how the class is instantiated

        :Example: instantiate a SELock and call repr on the instance

         >>> from scottbrian_utils.se_lock import SELock
        >>> a_lock = SELock()
        >>> repr(a_lock)
        SELock()

        """
        if TYPE_CHECKING:
            __class__: Type[SELock]
        classname = self.__class__.__name__
        parms = ''

        return f'{classname}({parms})'

    ###########################################################################
    # obtain
    ###########################################################################
    def obtain(self, mode: int) -> None:
        """Method to obtain the SELock.

        Args:
            mode: specifies whether to obtain the lock in shared mode
                    (mode=SELock.SHARE) or exclusive mode (mode=SELock.EXCL)

        Raises:
            IncorrectModeSpecified: For SELock obtain, the mode
                                    must be specified as either
                                    SELock.SHARE or SELock.EXCL.

        """
        with self.se_lock_lock:
            if mode == SELock.EXCL:
                if self.owner_count == 0:
                    self.owner_count = -1
                    return
            elif mode == SELock.SHARE:  # obtain share mode
                if ((self.owner_count == 0)
                        or ((self.owner_count > 0) and (not self.wait_q))):
                    self.owner_count += 1
                    return
            else:
                raise IncorrectModeSpecified('For SELock obtain, the mode '
                                             'must be specified as either '
                                             'SELock.SHARE or SELock.EXCL')
            wait_event = threading.Event()
            self.wait_q.append(SELock.LockWaiter(mode=mode,
                                                 event=wait_event))
        wait_event.wait()

    ###########################################################################
    # release
    ###########################################################################
    def release(self) -> None:
        """Method to release the SELock.

        Raises:
            AttemptedReleaseOfUnownedLock: A release of the SELock was
                                             attempted when the owner count
                                             was zero which indicates no
                                             owners currently hold the lock.
        """
        with self.se_lock_lock:
            # The owner_count is -1 if owned exclusive, or > 0 if owned shared.
            # The owner count should not be zero here since we are releasing.
            if self.owner_count == 0:
                raise AttemptedReleaseOfUnownedLock('A release of the '
                                                    'SELock was '
                                                    'attempted when the owner'
                                                    'count was zero which '
                                                    'indicates no owners '
                                                    'currently hold the lock.')
            if self.owner_count > 0:
                self.owner_count -= 1  # release by shared owner
            elif self.owner_count == -1:
                self.owner_count = 0

            # if lock now free, handle any waiters
            if (self.owner_count == 0) and self.wait_q:
                if self.wait_q[0].mode == SELock.EXCL:
                    waiter = self.wait_q.pop(0)
                    self.owner_count = -1
                    waiter.event.set()  # wake up the exclusive waiter
                    return  # all done
                # if we are here, we have one of more share waiters
                while self.wait_q:
                    if self.wait_q[0].mode == SELock.EXCL:
                        return
                    waiter = self.wait_q.pop(0)
                    self.owner_count += 1
                    waiter.event.set()  # wake up shared waiter


###############################################################################
# SELock Context Manager for Shared Control
###############################################################################
class SELockShare:
    """Class for SELockShared."""
    def __init__(self, se_lock: SELock) -> None:
        """Initialize shared lock context manager.

        Args:
            se_lock: instance of SELock

        """
        self.se_lock = se_lock

    def __enter__(self) -> None:
        """Context manager enter method."""
        self.se_lock.obtain(SELock.SHARE)

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit method.

        Args:
            exc_type: exception type or None
            exc_val: exception value or None
            exc_tb: exception traceback or None

        """
        self.se_lock.release()


###############################################################################
# SELock Context Manager for Exclusive Control
###############################################################################
class SELockExcl:
    """Class for SELockExcl."""

    def __init__(self, se_lock: SELock) -> None:
        """Initialize exclusive lock context manager.

        Args:
            se_lock: instance of SELock

        """
        self.se_lock = se_lock

    def __enter__(self) -> None:
        """Context manager enter method."""
        self.se_lock.obtain(SELock.EXCL)

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit method.

        Args:
            exc_type: exception type or None
            exc_val: exception value or None
            exc_tb: exception traceback or None

        """
        self.se_lock.release()
