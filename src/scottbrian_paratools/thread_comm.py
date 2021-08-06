"""Module thread_comm.

=============
ThreadComm
=============

You can use the ThreadComm class to set up a two way communication link
between two threads. This allows one thread to send and receive messages
with another thread. The messages can be anything, such as strings, numbers,
lists, or any other type of object. You can send messages via the send_msg
method and receive messages via the recv_msg method. You can also send a
message and wait for a reply with the send_rcv_msg.

:Example: use ThreadComm to pass a value to a thread and get a response

>>> from scottbrian_utils.thread_comm import ThreadComm
>>> import threading
>>> import time
>>> thread_comm = ThreadComm()
>>> def f1(in_thread_comm):
...     time.sleep(3)
...     while True:
...         msg = in_thread_comm.recv_msg()
...         if msg == 42:
...             print(f'f1 received message {msg}')
...             in_thread_comm.send_msg(17)
...         elif msg == 'exit':
...             print(f'received message {msg}')
...             break
>>> f1_thread = threading.Thread(target=f1, args=(thread_comm,)
>>> f1_thread.start()
>>> print(f'mainline about to send {42}')
mainline about to send 42

>>> msg = thread_comm.send_recv(42)
f1 received message 42

>>> print(f'mainline sent {42} and received {msg}')
mainline sent 42 and received 17

>>> time.sleep(3)
>>> thread_comm.send('exit')
received message exit


The thread_comm module contains:

    1) ThreadComm class with methods:

       a. send
       b. recv
       c. send_recv

"""
# import time
import threading
import queue
from typing import (Any, Final, Optional, Type, TYPE_CHECKING, Union)

# from scottbrian_utils.diag_msg import diag_msg

import logging


###############################################################################
# ThreadComm class exceptions
###############################################################################
class ThreadCommError(Exception):
    """Base class for exceptions in this module."""
    pass


class ThreadCommSendFailed(ThreadCommError):
    """ThreadComm exception failure to send message."""
    pass


class ThreadCommRecvTimedOut(ThreadCommError):
    """ThreadComm exception for timeout waiting for message."""
    pass


###############################################################################
# ThreadComm class
###############################################################################
class ThreadComm:
    """Provides a communication link between threads."""

    MAX_MSGS_DEFAULT: Final[int] = 16

    def __init__(self,
                 max_msgs: Optional[int] = None
                 ) -> None:
        """Initialize an instance of the ThreadComm class.

        Args:
            max_msgs: Number of messages that can be placed onto the send
                        queue until being received. Once the max has
                        been reached, no more sends will be allowed
                        until messages are received from the queue. The
                        default is 16
        """
        if max_msgs:
            self.max_msgs = max_msgs
        else:
            self.max_msgs = ThreadComm.MAX_MSGS_DEFAULT
        self.main_send: queue.Queue[Any] = queue.Queue(maxsize=self.max_msgs)
        self.main_recv: queue.Queue[Any] = queue.Queue(maxsize=self.max_msgs)

        self.main_thread_id = threading.get_ident()
        self.child_thread_id: Any = 0
        self.logger = logging.getLogger(__name__)
        self.debug_logging_enabled = self.logger.isEnabledFor(logging.DEBUG)
        self.logger.info('ThreadComm created by thread ID '
                         f'{self.main_thread_id}')

    ###########################################################################
    # repr
    ###########################################################################
    def __repr__(self) -> str:
        """Return a representation of the class.

        Returns:
            The representation as how the class is instantiated

        :Example: instantiate an ThreadComm

        >>> from scottbrian_utils.thread_comm import ThreadComm
        >>> thread_comm = ThreadComm()
        >>> repr(thread_comm)
        ThreadComm(max_msgs=16)

        """
        if TYPE_CHECKING:
            __class__: Type[ThreadComm]
        classname = self.__class__.__name__
        parms = f'max_msgs={self.max_msgs}'

        return f'{classname}({parms})'

    ###########################################################################
    # set_child_thread_id
    ###########################################################################
    def set_child_thread_id(self,
                            child_thread_id: Optional[Any] = None
                            ) -> None:
        """Set child thread id.

        Args:
            child_thread_id: the id to set. The default is None which will set
                               the id to the caller's thread id

        :Example: instantiate a ThreadComm and set the id to 5

        >>> from scottbrian_utils.thread_comm import ThreadComm
        >>> thread_comm = ThreadComm()
        >>> thread_comm.set_child_thread_id(5)
        >>> print(thread_comm.get_child_thread_id())
        5
        """
        if child_thread_id:
            self.child_thread_id = child_thread_id
        else:
            self.child_thread_id = threading.get_ident()

    ###########################################################################
    # get_child_thread_id
    ###########################################################################
    def get_child_thread_id(self) -> Any:
        """Get child thread id.

        Returns:
            child thread id

        :Example: instantiate a ThreadComm and set the id to 5

        >>> from scottbrian_utils.thread_comm import ThreadComm
        >>> thread_comm = ThreadComm()
        >>> thread_comm.set_child_thread_id('child_A')
        >>> print(thread_comm.get_child_thread_id())
        child_A

        """
        return self.child_thread_id

    ###########################################################################
    # send
    ###########################################################################
    def send(self,
             msg: Any,
             timeout: Optional[Union[int, float]] = None) -> None:
        """Send a msg.

        Args:
            msg: the msg to be sent
            timeout: number of seconds to wait for full queue to get free slot

        Raises:
            ThreadCommSendFailed: send method unable to send the
                                    message because the send queue
                                    is full with the maximum
                                    number of messages.

        :Example: instantiate a ThreadComm and send a message

        >>> from scottbrian_utils.thread_comm import ThreadComm
        >>> import threading
        >>> def f1(thread_comm: ThreadComm) -> None:
        ...     msg = thread_comm.recv()
        ...     if msg == 'hello thread':
        ...         thread_comm.send('hi')
        >>> a_thread_comm = ThreadComm()
        >>> thread = threading.Thread(target=f1, args=(a_thread_comm,))
        >>> thread.start()
        >>> a_thread_comm.send('hello thread')
        >>> print(a_thread_comm.recv())
        hi

        >>> thread.join()

        """
        try:
            if self.main_thread_id == threading.get_ident():  # if main
                self.logger.info(f'ThreadComm main {self.main_thread_id} sending '
                            f'msg to child {self.child_thread_id}')
                self.main_send.put(msg, timeout=timeout)  # send to child
            else:  # else not main
                self.logger.info(f'ThreadComm child {self.child_thread_id} '
                            f'sending msg to main {self.main_thread_id}')
                self.main_recv.put(msg, timeout=timeout)  # send to main
        except queue.Full:
            self.logger.error('Raise ThreadCommSendFailed')
            raise ThreadCommSendFailed('send method unable to send the '
                                       'message because the send queue '
                                       'is full with the maximum '
                                       'number of messages.')

    ###########################################################################
    # recv
    ###########################################################################
    def recv(self, timeout: Optional[Union[int, float]] = None) -> Any:
        """Send a msg.

        Args:
            timeout: number of seconds to wait for message

        Returns:
            message unless timeout occurs

        Raises:
            ThreadCommRecvTimedOut: recv processing timed out
                                      waiting for a message to
                                      arrive.

        """
        try:
            if self.main_thread_id == threading.get_ident():  # if main
                self.logger.info(f'ThreadComm main {self.main_thread_id} receiving '
                            f'msg from child {self.child_thread_id}')
                return self.main_recv.get(timeout=timeout)  # recv from child
            else:  # else child
                self.logger.info(f'ThreadComm child {self.child_thread_id} '
                            f'receiving msg from main {self.main_thread_id}')
                return self.main_send.get(timeout=timeout)  # recv from main
        except queue.Empty:
            self.logger.error('Raise ThreadCommRecvTimedOut')
            raise ThreadCommRecvTimedOut('recv processing timed out '
                                         'waiting for a message to '
                                         'arrive.')

    ###########################################################################
    # send_recv
    ###########################################################################
    def send_recv(self,
                  msg: Any,
                  timeout: Optional[Union[int, float]] = None) -> Any:
        """Send a message and wait for reply.

        Args:
            msg: the msg to be sent
            timeout: Number of seconds to wait for reply

        Returns:
              message unless send q is full or timeout occurs during recv

        :Example: instantiate a ThreadComm and send a message

        >>> from scottbrian_utils.thread_comm import ThreadComm
        >>> import threading
        >>> def f1(thread_comm: ThreadComm) -> None:
        ...     msg = thread_comm.recv()
        ...     if msg == 'hello thread':
        ...         thread_comm.send('hi')
        >>> a_thread_comm = ThreadComm()
        >>> thread = threading.Thread(target=f1, args=(a_thread_comm,))
        >>> thread.start()
        >>> a_thread_comm.send('hello thread')
        >>> print(a_thread_comm.recv())
        hi

        >>> thread.join()

        """
        self.send(msg, timeout=timeout)
        return self.recv(timeout=timeout)

    ###########################################################################
    # msg_waiting
    ###########################################################################
    def msg_waiting(self) -> bool:
        """Determine whether a message is waiting, ready to be received.

        Returns:
            True if message is ready to receive, False otherwise

        :Example: instantiate a ThreadComm and set the id to 5

        >>> from scottbrian_utils.thread_comm import ThreadComm
        >>> class ThreadCommApp(threading.Thread):
        ...     def __init__(self,
        ...                  thread_comm: ThreadComm,
        ...                  event: threading.Event) -> None:
        ...         super().__init__()
        ...         self.thread_comm = thread_comm
        ...         self.event = event
        ...         self.thread_comm.set_child_thread_id()
        ...     def run(self) -> None:
        ...         self.thread_comm.send('goodbye')
        ...         self.event.set()
        >>> thread_comm = ThreadComm()
        >>> event = threading.Event()
        >>> thread_comm_app = ThreadCommApp(thread_comm, event)
        >>> print(thread_comm.msg_waiting())
        False

        >>> thread_comm_app.start()
        >>> event.wait()
        >>> print(thread_comm.msg_waiting())
        True

        >>> print(thread_comm.recv())
        goodbye

        """
        if self.main_thread_id == threading.get_ident():
            return not self.main_recv.empty()
        else:
            return not self.main_send.empty()
