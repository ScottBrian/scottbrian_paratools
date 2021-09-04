"""test_thread_comm.py module."""

from enum import Enum
import time
import math
import pytest
from typing import Any, cast, List
from sys import _getframe
import threading
# from scottbrian_utils.diag_msg import diag_msg
from scottbrian_utils.thread_comm import (ThreadComm,
                                          ThreadCommSendFailed,
                                          ThreadCommRecvTimedOut)

from scottbrian_utils.smart_event import SmartEvent, WUCond

import logging

logger = logging.getLogger(__name__)
logger.debug('about to start the tests')


# class SmartEvent(threading.Event):
#     def __init__(self):
#         super().__init__()
#         self.exc = None
#
#     def wait(self, timeout=None):
#         if timeout:
#             t_out = min(0.1, timeout)
#         else:
#             t_out = 0.1
#         start_time = time.time()
#         while not super().wait(timeout=t_out):
#             if self.exc:
#                 raise self.exc
#             if timeout and (timeout <= (time.time() - start_time)):
#                 return False
#         return True
#
#     def set(self):
#         super().set()
#         if self.exc:
#             raise exc
#
#     def set_exc(self, exc):
#         self.exc = exc


###############################################################################
# ThreadComm test exceptions
###############################################################################
class ErrorTstThreadComm(Exception):
    """Base class for exception in this module."""
    pass


class IncorrectActionSpecified(ErrorTstThreadComm):
    """IncorrectActionSpecified exception class."""
    pass


class UnrecognizedMessageType(ErrorTstThreadComm):
    """UnrecognizedMessageType exception class."""
    pass


class UnrecognizedActionToDo(ErrorTstThreadComm):
    """UnrecognizedActionToDo exception class."""
    pass


###############################################################################
# Action
###############################################################################
Action = Enum('Action',
              'MainSend MainRecv '
              'ThreadSend ThreadRecv '
              'MainSendRecv ThreadSendRecv')

###############################################################################
# action_arg fixtures
###############################################################################
action_arg_list = [Action.MainSend, Action.MainRecv,
                   Action.ThreadSend, Action.ThreadRecv,
                   Action.MainSendRecv, Action.ThreadSendRecv]


@pytest.fixture(params=action_arg_list)  # type: ignore
def action1_arg(request: Any) -> Any:
    """Using different reply messages.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return request.param


@pytest.fixture(params=action_arg_list)  # type: ignore
def action2_arg(request: Any) -> Any:
    """Using different reply messages.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return request.param


@pytest.fixture(params=action_arg_list)  # type: ignore
def action3_arg(request: Any) -> Any:
    """Using different reply messages.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return request.param


###############################################################################
# msg_arg fixtures
###############################################################################
msg_arg_list = [(1, 2, 3),
                (0.1, 0.22, 0.33),
                ('word', 'word to', 'word to the wise')]


@pytest.fixture(params=msg_arg_list)  # type: ignore
def msg_arg1(request: Any) -> Any:
    """Using different requests.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return request.param


@pytest.fixture(params=msg_arg_list)  # type: ignore
def msg_arg2(request: Any) -> Any:
    """Using different requests.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return request.param


@pytest.fixture(params=msg_arg_list)  # type: ignore
def msg_arg3(request: Any) -> Any:
    """Using different requests.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return request.param


###############################################################################
# num_msg fixtures
###############################################################################
num_msg_arg_list = [1, 2, 3]


@pytest.fixture(params=num_msg_arg_list)  # type: ignore
def num_msg1_arg(request: Any) -> int:
    """Using different requests.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


@pytest.fixture(params=num_msg_arg_list)  # type: ignore
def num_msg2_arg(request: Any) -> int:
    """Using different requests.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


@pytest.fixture(params=num_msg_arg_list)  # type: ignore
def num_msg3_arg(request: Any) -> int:
    """Using different requests.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


###############################################################################
# TestThreadCommBasic class to test ThreadComm methods
###############################################################################
class TestThreadCommBasic:
    """Test class for ThreadComm basic tests."""

    ###########################################################################
    # repr for ThreadComm
    ###########################################################################
    def test_thread_comm_repr(self) -> None:
        """Test event with code repr."""
        thread_comm = ThreadComm()

        expected_repr_str = 'ThreadComm(max_msgs=16)'

        assert repr(thread_comm) == expected_repr_str

    ###########################################################################
    # test_thread_comm_set_thread_id
    ###########################################################################
    def test_thread_comm_set_and_get_thread_id(self) -> None:
        """Test set and get thread id."""
        thread_comm = ThreadComm()

        assert thread_comm.get_child_thread_id() == 0

        my_thread_id = threading.get_ident()

        thread_comm.set_child_thread_id()
        assert thread_comm.get_child_thread_id() == my_thread_id

        thread_comm.set_child_thread_id(3)
        assert thread_comm.get_child_thread_id() == 3

        thread_comm.set_child_thread_id('abc')
        assert thread_comm.get_child_thread_id() == 'abc'

    ###########################################################################
    # test_thread_comm_msg_waiting
    ###########################################################################
    def test_thread_comm_msg_waiting(self) -> None:
        """Test msg waiting method."""

        class ThreadCommApp(threading.Thread):
            def __init__(self,
                         thread_comm: ThreadComm) -> None:
                """Init the class.

                Args:
                    thread_comm: instance of ThreadComm

                """
                super().__init__()
                self.thread_comm = thread_comm
                self.thread_comm.set_child_thread_id()

            def run(self) -> None:
                assert not self.thread_comm.msg_waiting()

                # wait for mainline to send msg
                smart_event.wait(log_msg='beta wait 1')

                assert self.thread_comm.msg_waiting()
                assert self.thread_comm.recv() == 'hello'
                assert self.thread_comm.msg_waiting()
                assert self.thread_comm.recv() == 'world'
                assert not self.thread_comm.msg_waiting()

                self.thread_comm.send('goodbye')
                self.thread_comm.send('was nice seeing you')
                self.thread_comm.send('take care')

                smart_event.resume(log_msg='beta resume 2')

                smart_event.wait(log_msg='beta wait 2')
                assert self.thread_comm.msg_waiting()
                assert self.thread_comm.recv() == 'yep, you take care too'
                assert not self.thread_comm.msg_waiting()

        thread_comm = ThreadComm()
        smart_event = SmartEvent(alpha=threading.current_thread())
        thread_comm_app = ThreadCommApp(thread_comm)

        smart_event.register_thread(beta=thread_comm_app)

        assert not thread_comm.msg_waiting()

        thread_comm_app.start()
        smart_event.pause_until(WUCond.ThreadsReady)

        assert not thread_comm.msg_waiting()

        thread_comm.send('hello')
        assert not thread_comm.msg_waiting()
        thread_comm.send('world')
        assert not thread_comm.msg_waiting()

        # tell thread to check messages and send msg
        smart_event.resume(log_msg='alpha resume 1')

        smart_event.wait(log_msg='alpha wait 2')
        assert thread_comm.msg_waiting()
        assert thread_comm.recv() == 'goodbye'
        assert thread_comm.msg_waiting()
        assert thread_comm.recv() == 'was nice seeing you'
        assert thread_comm.msg_waiting()
        assert thread_comm.recv() == 'take care'
        assert not thread_comm.msg_waiting()

        thread_comm.send('yep, you take care too')
        smart_event.resume(log_msg='alpha resume 2')

        thread_comm_app.join()
        assert not thread_comm.msg_waiting()

    ###########################################################################
    # test_thread_comm_msg_waiting
    ###########################################################################
    def test_thread_comm_send_timeout(self) -> None:
        """Test send timeout method."""

        class ThreadCommApp(threading.Thread):
            def __init__(self,
                         thread_comm: ThreadComm,
                         thread_wait_e: threading.Event,
                         mainline_wait_e: threading.Event
                         ) -> None:
                """Init the class.

                Args:
                    thread_comm: instance of ThreadComm
                    thread_wait_e: event used to signal completion
                    mainline_wait_e: event

                """
                super().__init__()
                self.thread_comm = thread_comm
                self.thread_wait_e = thread_wait_e
                self.mainline_wait_e = mainline_wait_e
                self.exc = None
                self.thread_comm.set_child_thread_id()

            def thread_wait(self, reason, num=[]):
                if num:
                    num[0] += 1
                else:
                    num.append(1)
                line_no = _getframe(1).f_lineno
                logger.debug(f'Thread {line_no} wait #{num[0]}C: {reason}')
                self.thread_wait_e.wait()
                self.thread_wait_e.clear()
                logger.debug(f'Thread {line_no} end wait #{num[0]}C: {reason}')

            def thread_post(self, reason, num=[]):
                if num:
                    num[0] += 1
                else:
                    num.append(1)
                line_no = _getframe(1).f_lineno
                logger.debug(f'Thread {line_no} post mainline #{num[0]}B:'
                             f' {reason}')
                self.mainline_wait_e.set()

            def run(self) -> None:
                ###########################################################
                # Part 1 - mainline timeouts
                ###########################################################
                logger.debug('Thread starting part 1')
                assert not self.thread_comm.msg_waiting()
                self.thread_post('tell mainline thread started')

                self.thread_wait('mainline to send 3 msgs')

                time.sleep(5)
                assert self.thread_comm.msg_waiting()
                assert self.thread_comm.recv() == 'msg1'
                self.thread_wait('mainline to say read msg7')

                time.sleep(3)
                assert self.thread_comm.msg_waiting()
                assert self.thread_comm.recv() == 'msg2'
                assert self.thread_comm.msg_waiting()
                assert self.thread_comm.recv() == 'msg3'
                assert self.thread_comm.msg_waiting()
                assert self.thread_comm.recv() == 'msg4'
                time.sleep(1)
                assert self.thread_comm.msg_waiting()
                assert self.thread_comm.recv() == 'msg7'
                assert not self.thread_comm.msg_waiting()

                self.thread_wait('mainline to finish timeouts')
                self.thread_post('tell mainline finished part 1')

                ###########################################################
                # Part 2 - thread timeouts
                ###########################################################
                logger.debug('Thread starting part 2')
                self.thread_wait('signal from mainline to send 3 msgs')

                self.thread_comm.send('msg10')
                self.thread_comm.send('msg20')
                self.thread_comm.send('msg30')

                self.thread_post('tell mainline pause, read 1, and wait')

                t_start_time = time.time()
                self.thread_comm.send('msg40')
                t_duration_seconds = time.time() - t_start_time
                assert 5 <= t_duration_seconds <= 6

                t_start_time = time.time()
                with pytest.raises(ThreadCommSendFailed):
                    self.thread_comm.send('msg50', timeout=3)
                t_duration_seconds = time.time() - t_start_time
                assert 3 <= t_duration_seconds <= 4

                t_start_time = time.time()
                with pytest.raises(ThreadCommSendFailed):
                    self.thread_comm.send('msg60', timeout=5)
                t_duration_seconds = time.time() - t_start_time
                assert 5 <= t_duration_seconds <= 6

                self.thread_post('tell mainline to read msg70')
                t_start_time = time.time()
                self.thread_comm.send('msg70', timeout=5)
                t_duration_seconds = time.time() - t_start_time
                assert 3 <= t_duration_seconds <= 4

                self.thread_post('tell mainline we finished part 2')

                self.thread_wait('mainline to signal exit')

        def mainline_wait(wait_event, reason, num=[]):
            if num:
                num[0] += 1
            else:
                num.append(1)
            line_no = _getframe(1).f_lineno
            logger.debug(f'Mainline {line_no} wait #{num[0]}A: {reason}')
            wait_event.wait()
            wait_event.clear()
            logger.debug(f'Mainline {line_no} end wait #{num[0]}A: {reason}')

        def mainline_post(post_event, reason, num=[]):
            if num:
                num[0] += 1
            else:
                num.append(1)
            line_no = _getframe(1).f_lineno
            logger.debug(f'Mainline {line_no} post thread #{num[0]}D:'
                         f' {reason}')
            post_event.set()

        thread_comm = ThreadComm(3)
        thread_wait_event = threading.Event()
        mainline_wait_event = threading.Event()
        thread_comm_app = ThreadCommApp(thread_comm,
                                        thread_wait_event,
                                        mainline_wait_event)
        thread_comm_app.start()
        mainline_wait(mainline_wait_event, 'thread to start')

        #######################################################################
        # part 1 - mainline timeouts
        #######################################################################
        logger.debug('Mainline starting part 1')
        thread_comm.send('msg1')
        thread_comm.send('msg2')
        thread_comm.send('msg3')

        mainline_post(thread_wait_event, 'pause, then read first msg and wait')

        m_start_time = time.time()
        thread_comm.send('msg4')
        m_duration_seconds = time.time() - m_start_time
        assert 5 <= m_duration_seconds <= 6

        m_start_time = time.time()
        with pytest.raises(ThreadCommSendFailed):
            thread_comm.send('msg5', timeout=3)
        m_duration_seconds = time.time() - m_start_time
        assert 3 <= m_duration_seconds <= 4

        m_start_time = time.time()
        with pytest.raises(ThreadCommSendFailed):
            thread_comm.send('msg6', timeout=5)
        m_duration_seconds = time.time() - m_start_time
        assert 5 <= m_duration_seconds <= 6

        mainline_post(thread_wait_event, 'pause 3, read msg7, wait')

        m_start_time = time.time()
        thread_comm.send('msg7', timeout=5)
        m_duration_seconds = time.time() - m_start_time
        assert 3 <= m_duration_seconds <= 4

        mainline_post(thread_wait_event, 'done with timeouts')
        mainline_wait(mainline_wait_event, 'thread to finish part 1')

        #######################################################################
        # part 2 - thread timeouts
        #######################################################################
        logger.debug('Mainline starting part 2')
        assert not thread_comm.msg_waiting()

        mainline_post(thread_wait_event, 'tell thread to send 3 msgs')
        mainline_wait(mainline_wait_event, 'thread to finish 3 msgs')

        time.sleep(5)
        assert thread_comm.msg_waiting()
        assert thread_comm.recv() == 'msg10'
        mainline_wait(mainline_wait_event, 'thread to say read msg70')

        time.sleep(3)
        assert thread_comm.msg_waiting()
        assert thread_comm.recv() == 'msg20'
        assert thread_comm.msg_waiting()
        assert thread_comm.recv() == 'msg30'
        assert thread_comm.msg_waiting()
        assert thread_comm.recv() == 'msg40'
        time.sleep(1)
        assert thread_comm.msg_waiting()
        assert thread_comm.recv() == 'msg70'
        assert not thread_comm.msg_waiting()

        time.sleep(3)

        mainline_wait(mainline_wait_event, 'thread to finish timeouts')
        mainline_post(thread_wait_event, 'tell thread to exit')
        thread_comm_app.join()

    ###########################################################################
    # test_thread_comm_msg_waiting
    ###########################################################################
    def test_thread_comm_recv_timeout(self) -> None:
        """Test send timeout method.

        Raises:
            exc: exception from the ThreadCommApp

        """

        class ThreadCommApp(threading.Thread):
            def __init__(self,
                         thread_comm: ThreadComm,
                         thread_wait_e: threading.Event,
                         mainline_wait_e: threading.Event
                         ) -> None:
                """Init the class.

                Args:
                    thread_comm: instance of ThreadComm
                    thread_wait_e: event to wait on
                    mainline_wait_e: event used to signal completion

                """
                super().__init__()
                self.thread_comm = thread_comm
                self.thread_wait_e = thread_wait_e
                self.mainline_wait_e = mainline_wait_e
                self.exc = None
                self.thread_comm.set_child_thread_id()

            def thread_wait(self, reason, num=[]):
                if num:
                    num[0] += 1
                else:
                    num.append(1)
                line_no = _getframe(1).f_lineno
                logger.debug(f'Thread {line_no} wait #{num[0]}C: {reason}')
                self.thread_wait_e.wait()
                self.thread_wait_e.clear()
                logger.debug(f'Thread {line_no} end wait #{num[0]}C: {reason}')

            def thread_post(self, reason, num=[]):
                if num:
                    num[0] += 1
                else:
                    num.append(1)
                line_no = _getframe(1).f_lineno
                logger.debug(f'Thread {line_no} post mainline #{num[0]}B:'
                             f' {reason}')
                self.mainline_wait_e.set()

            def run(self) -> None:
                try:
                    ###########################################################
                    # Part 1 - mainline recv timeouts
                    ###########################################################
                    logger.debug('Thread starting part 1')
                    assert not self.thread_comm.msg_waiting()
                    self.thread_post('tell mainline thread started')

                    self.thread_wait('mainline to say pause, send, wait')

                    time.sleep(5)
                    self.thread_comm.send('msg1')
                    self.thread_wait('mainline to say pause, send msg2, wait')

                    time.sleep(3)
                    self.thread_comm.send('msg2')
                    assert not self.thread_comm.msg_waiting()
                    self.thread_wait('mainline to say recv msg10')

                    ###########################################################
                    # Part 2 - thread timeouts
                    ###########################################################
                    logger.debug('Thread starting part 2')

                    t_start_time = time.time()
                    assert self.thread_comm.recv() == 'msg10'
                    t_duration_seconds = time.time() - t_start_time
                    assert 5 <= t_duration_seconds <= 6

                    assert not self.thread_comm.msg_waiting()
                    t_start_time = time.time()
                    with pytest.raises(ThreadCommRecvTimedOut):
                        _ = self.thread_comm.recv(timeout=3)
                    t_duration_seconds = time.time() - t_start_time
                    assert 3 <= t_duration_seconds <= 4

                    assert not self.thread_comm.msg_waiting()
                    t_start_time = time.time()
                    with pytest.raises(ThreadCommRecvTimedOut):
                        _ = self.thread_comm.recv(timeout=5)
                    t_duration_seconds = time.time() - t_start_time
                    assert 5 <= t_duration_seconds <= 6

                    assert not self.thread_comm.msg_waiting()
                    self.thread_post('tell mainline pause, send msg11, wait')

                    t_start_time = time.time()
                    assert self.thread_comm.recv(timeout=5) == 'msg11'
                    t_duration_seconds = time.time() - t_start_time
                    assert 3 <= t_duration_seconds <= 4

                    self.thread_post('tell mainline we are done')
                    self.thread_wait('mainline to signal exit')

                except Exception as e:
                    self.exc = e

        def mainline_wait(wait_event, reason, num=[]):
            if num:
                num[0] += 1
            else:
                num.append(1)
            line_no = _getframe(1).f_lineno
            logger.debug(f'Mainline {line_no} wait #{num[0]}A: {reason}')
            wait_event.wait()
            wait_event.clear()
            logger.debug(f'Mainline {line_no} end wait #{num[0]}A: {reason}')

        def mainline_post(post_event, reason, num=[]):
            if num:
                num[0] += 1
            else:
                num.append(1)
            line_no = _getframe(1).f_lineno
            logger.debug(f'Mainline {line_no} post thread #{num[0]}D:'
                         f' {reason}')
            post_event.set()

        thread_comm = ThreadComm(3)
        thread_wait_event = threading.Event()
        mainline_wait_event = threading.Event()
        thread_comm_app = ThreadCommApp(thread_comm,
                                        thread_wait_event,
                                        mainline_wait_event)
        thread_comm_app.start()
        mainline_wait(mainline_wait_event, 'thread to start')

        #######################################################################
        # part 1 - mainline recv timeouts
        #######################################################################
        logger.debug('Mainline starting part 1')
        assert not thread_comm.msg_waiting()
        mainline_post(thread_wait_event, 'pause, then send msg and wait')

        m_start_time = time.time()
        assert thread_comm.recv() == 'msg1'
        m_duration_seconds = time.time() - m_start_time
        assert 5 <= m_duration_seconds <= 6

        m_start_time = time.time()
        with pytest.raises(ThreadCommRecvTimedOut):
            _ = thread_comm.recv(timeout=3)
        m_duration_seconds = time.time() - m_start_time
        assert 3 <= m_duration_seconds <= 4

        m_start_time = time.time()
        with pytest.raises(ThreadCommRecvTimedOut):
            _ = thread_comm.recv(timeout=5)
        m_duration_seconds = time.time() - m_start_time
        assert 5 <= m_duration_seconds <= 6

        # Thread will wait 3 seconds and then send
        mainline_post(thread_wait_event, 'pause, send msg2, wait')
        start_time = time.time()
        assert thread_comm.recv(timeout=5) == 'msg2'
        duration_seconds = time.time() - start_time
        assert 3 <= duration_seconds <= 4

        #######################################################################
        # part 2 - thread timeouts
        #######################################################################
        logger.debug('Mainline starting part 2')
        assert not thread_comm.msg_waiting()

        mainline_post(thread_wait_event, 'tell thread to recv msg10')

        time.sleep(5)
        thread_comm.send('msg10')

        mainline_wait(mainline_wait_event, 'thread to say send msg11')
        time.sleep(3)
        thread_comm.send('msg11')

        mainline_wait(mainline_wait_event, 'thread to say all done')

        assert not thread_comm.msg_waiting()

        mainline_post(thread_wait_event, 'tell thread to exit')
        thread_comm_app.join()

        if thread_comm_app.exc:
            print(thread_comm_app.exc)
            raise thread_comm_app.exc

    ###########################################################################
    # test_thread_comm_thread_app_combos
    ###########################################################################
    def test_thread_comm_thread_app_combos(self,
                                           action1_arg: Any,
                                           msg_arg1: Any,
                                           num_msg1_arg: int,
                                           action2_arg: Any,
                                           msg_arg2: Any,
                                           num_msg2_arg: int
                                           ) -> None:
        """Test the ThreadComm with ThreadApp combos.

        Args:
            action1_arg: the action to do for first batch
            msg_arg1: the messages to be sent for first batch
            num_msg1_arg: the number of messages to be sent for first batch
            action2_arg: the action to do for second batch
            msg_arg2: the messages to be sent for second batch
            num_msg2_arg: the number of messages to be sent for second batch

        Raises:
            IncorrectActionSpecified: The Action is not recognized

        """
        def get_exp_recv_msg(msg) -> Any:
            """Return the expected recv msg give the send msg.

            Args:
                msg: msg that is sent

            Returns:
                msg to be used to verify what was received

            Raises:
                UnrecognizedMessageType: The message type is not int, str,
                                         or float
            """
            if isinstance(msg, int):
                return msg * 10

            if isinstance(msg, str):
                ret_value = 0
                for letter in msg:
                    ret_value += ord(letter)
                return ret_value

            if isinstance(msg, float):
                return math.ceil(msg) + 10

            raise UnrecognizedMessageType('The message type is not int, str,'
                                          'or float')

        class ThreadCommApp(threading.Thread):
            def __init__(self,
                         action_event: threading.Event,
                         complete_event: threading.Event) -> None:
                super().__init__()
                self.thread_comm = ThreadComm()
                self.action_event = action_event
                self.action_to_do = [0]
                self.complete_event = complete_event
                self.msgs = [0]

            def run(self):
                """Thread to send and receive messages.

                Raises:
                    UnrecognizedActionToDo: ThreadCommApp received an
                                              unrecognized action
                """
                logger.debug('ThreadCommApp run started')
                self.thread_comm.set_child_thread_id()
                while True:
                    logger.debug('ThreadCommApp about to wait on action '
                                 'event')
                    self.action_event.wait()
                    self.action_event.clear()
                    if self.action_to_do[0] == 'send':
                        logger.debug('ThreadCommApp doing send')
                        for msg in self.msgs:
                            self.thread_comm.send(msg)
                            logger.debug('ThreadCommApp sent '
                                         f'message {msg}')
                        self.complete_event.set()
                    elif self.action_to_do[0] == 'pause_send':
                        logger.debug('ThreadCommApp doing pause_send')
                        time.sleep(1)
                        for msg in self.msgs:
                            self.thread_comm.send(msg)
                            logger.debug('ThreadCommApp sent '
                                         f'message {msg}')
                        self.complete_event.set()
                    elif self.action_to_do[0] == 'recv_reply':
                        logger.debug('ThreadCommApp doing recv_reply')
                        logger.debug('ThreadCommApp msgs = '
                                     f'{self.msgs}')
                        for msg in self.msgs:
                            recv_msg = self.thread_comm.recv()
                            logger.debug('ThreadCommApp received message '
                                         f'{recv_msg}')
                            assert recv_msg == msg
                            reply_msg = get_exp_recv_msg(msg)
                            self.thread_comm.send(reply_msg)
                        self.complete_event.set()
                    elif self.action_to_do[0] == 'recv_verify':
                        logger.debug('ThreadCommApp doing recv_verify')
                        for msg in self.msgs:
                            recv_msg = self.thread_comm.recv()
                            logger.debug('ThreadCommApp received message '
                                         f'{recv_msg}')
                            test_msg = get_exp_recv_msg(msg)
                            assert recv_msg == test_msg
                        self.complete_event.set()
                    elif self.action_to_do[0] == 'send_recv':
                        logger.debug('ThreadCommApp doing send_recv')
                        for msg in self.msgs:
                            recv_msg = self.thread_comm.send_recv(msg)
                            exp_recv_msg = get_exp_recv_msg(msg)
                            assert recv_msg == exp_recv_msg
                        self.complete_event.set()
                    elif self.action_to_do[0] == 'exit':
                        logger.debug('ThreadCommApp doing exit')
                        break
                    else:
                        raise UnrecognizedActionToDo('ThreadCommApp '
                                                     'received an '
                                                     'unrecognized action')

            def send_msg(self, msg):
                """Send message.

                Args:
                    msg: message to send
                """
                self.thread_comm.send(msg)

            def recv_msg(self) -> Any:
                """Receive message.

                Returns:
                    message received
                """
                return self.thread_comm.recv()

            def send_recv_msg(self, msg) -> Any:
                """Send message and receive response.

                Args:
                    msg: message to send

                Returns:
                    message received
                """
                return self.thread_comm.send_recv(msg)

        def f1(in_thread_comm: ThreadComm,
               action_event: threading.Event,
               action_to_do: List[Any],
               complete_event: threading.Event,
               msgs: List[Any],
               exc1: List[Any]) -> None:
            """Thread to send or receive messages.

            Args:
                in_thread_comm: instance of ThreadComm class
                action_event: event to wait on for action to perform
                action_to_do: send, recv, send_recv, or done
                complete_event: event to set when done with action
                msgs: list of message that are to be sent
                exc1: list to be set with exception

            Raises:
                UnrecognizedActionToDo: Thread received an unrecognized action

            """
            logger.debug('thread f1 started')
            while True:
                logger.debug('thread f1 about to wait on action event')
                action_event.wait()
                action_event.clear()
                if action_to_do[0] == 'send':
                    logger.debug('thread f1 doing send')
                    for msg in msgs:
                        in_thread_comm.send(msg)
                        logger.debug(f'thread f1 sent message {msg}')
                    complete_event.set()
                elif action_to_do[0] == 'pause_send':
                    logger.debug('thread f1 doing pause_send')
                    time.sleep(1)
                    for msg in msgs:
                        in_thread_comm.send(msg)
                        logger.debug(f'thread f1 sent message {msg}')
                    complete_event.set()
                elif action_to_do[0] == 'recv_reply':
                    logger.debug('thread f1 doing recv_reply')
                    logger.debug(f'thread f1 msgs = {msgs}')
                    for msg in msgs:
                        recv_msg = in_thread_comm.recv()
                        logger.debug('thread f1 received message '
                                     f'{recv_msg}')
                        assert recv_msg == msg
                        reply_msg = get_exp_recv_msg(msg)
                        in_thread_comm.send(reply_msg)
                    complete_event.set()
                elif action_to_do[0] == 'recv_verify':
                    logger.debug('thread f1 doing recv_verify')
                    for msg in msgs:
                        recv_msg = in_thread_comm.recv()
                        logger.debug('thread f1 received message '
                                     f'{recv_msg}')
                        test_msg = get_exp_recv_msg(msg)
                        assert recv_msg == test_msg
                    complete_event.set()
                elif action_to_do[0] == 'send_recv':
                    logger.debug('thread f1 doing send_recv')
                    for msg in msgs:
                        recv_msg = in_thread_comm.send_recv(msg)
                        exp_recv_msg = get_exp_recv_msg(msg)
                        assert recv_msg == exp_recv_msg
                    complete_event.set()
                elif action_to_do[0] == 'exit':
                    logger.debug('thread f1 doing exit')
                    break
                else:
                    raise UnrecognizedActionToDo('Thread received an '
                                                 'unrecognized action')

        thread_comm = ThreadComm()
        thread_action_event = SmartEvent()  # threading.Event()
        thread_actions = [0]
        thread_complete_event = SmartEvent()  # threading.Event()
        send_msgs = [0]

        f1_thread = threading.Thread(target=f1,
                                     args=(thread_comm,
                                           thread_action_event,
                                           thread_actions,
                                           thread_complete_event,
                                           send_msgs))

        logger.debug('main about to start f1 thread')
        f1_thread.start()

        logger.debug('main about to start ThreadCommApp')
        app_action_event = threading.Event()
        app_complete_event = threading.Event()
        thread_comm_app = ThreadCommApp(app_action_event, app_complete_event)
        thread_comm_app.start()

        super_msgs = []
        msg_list = []
        for i in range(num_msg1_arg):
            msg_list.append(msg_arg1[i])
        super_msgs.append(msg_list)
        msg_list = []
        for i in range(num_msg2_arg):
            msg_list.append(msg_arg2[i])
        super_msgs.append(msg_list)
        logger.debug(f'main super_msgs {super_msgs}')

        #######################################################################
        # action loop
        #######################################################################
        actions = []
        actions.append(action1_arg)
        actions.append(action2_arg)
        for action in actions:
            _ = send_msgs.pop(0)
            send_msgs.extend(super_msgs.pop(0))
            thread_comm_app.msgs = send_msgs
            if action == Action.MainSend:
                logger.debug('main starting Action.MainSend')
                logger.debug(f'main send_msgs = {send_msgs}')
                for msg in send_msgs:
                    logger.debug(f'main sending msg {msg}')
                    thread_comm.send(msg)
                    thread_comm_app.send_msg(msg)
                thread_actions[0] = 'recv_reply'
                thread_action_event.set()
                thread_comm_app.action_to_do[0] = 'recv_reply'
                thread_comm_app.action_event.set()
                # if exc[0]:
                #     raise exc[0]
                # if thread_comm_app.exc:
                #     raise thread_comm_app.exc
                for msg in send_msgs:
                    exp_recv_msg = get_exp_recv_msg(msg)
                    recv_msg = thread_comm.recv()
                    assert recv_msg == exp_recv_msg
                    recv_msg = thread_comm_app.recv_msg()
                    assert recv_msg == exp_recv_msg
                thread_complete_event.wait()
                thread_complete_event.clear()
                thread_comm_app.complete_event.wait()
                thread_comm_app.complete_event.clear()
            elif action == Action.MainRecv:
                logger.debug('main starting Action.MainRecv')
                thread_actions[0] = 'pause_send'
                thread_action_event.set()
                thread_comm_app.action_to_do[0] = 'pause_send'
                thread_comm_app.action_event.set()
                # if exc[0]:
                #     raise exc[0]
                # if thread_comm_app.exc:
                #     raise thread_comm_app.exc
                for msg in send_msgs:
                    recv_msg = thread_comm.recv()
                    assert recv_msg == msg
                    recv_msg = thread_comm_app.recv_msg()
                    assert recv_msg == msg
                    reply_msg = get_exp_recv_msg(msg)
                    thread_comm.send(reply_msg)
                    thread_comm_app.send_msg(reply_msg)
                thread_complete_event.wait()
                thread_complete_event.clear()
                thread_comm_app.complete_event.wait()
                thread_comm_app.complete_event.clear()
                thread_actions[0] = 'recv_verify'
                thread_action_event.set()
                thread_comm_app.action_to_do[0] = 'recv_verify'
                thread_comm_app.action_event.set()
                thread_complete_event.wait()
                thread_complete_event.clear()
                thread_comm_app.complete_event.wait()
                thread_comm_app.complete_event.clear()
            elif action == Action.ThreadSend:
                logger.debug('main starting Action.ThreadSend')
                thread_actions[0] = 'send'
                thread_action_event.set()
                thread_comm_app.action_to_do[0] = 'send'
                thread_comm_app.action_event.set()
                time.sleep(1)
                # if exc[0]:
                #     raise exc[0]
                # if thread_comm_app.exc:
                #     raise thread_comm_app.exc
                for msg in send_msgs:
                    recv_msg = thread_comm.recv()
                    assert recv_msg == msg
                    recv_msg = thread_comm_app.recv_msg()
                    assert recv_msg == msg
                    reply_msg = get_exp_recv_msg(msg)
                    thread_comm.send(reply_msg)
                    thread_comm_app.send_msg(reply_msg)
                thread_complete_event.wait()
                thread_complete_event.clear()
                thread_comm_app.complete_event.wait()
                thread_comm_app.complete_event.clear()
                thread_actions[0] = 'recv_verify'
                thread_action_event.set()
                thread_comm_app.action_to_do[0] = 'recv_verify'
                thread_comm_app.action_event.set()
                thread_complete_event.wait()
                thread_complete_event.clear()
                thread_comm_app.complete_event.wait()
                thread_comm_app.complete_event.clear()
            elif action == Action.ThreadRecv:
                logger.debug('main starting Action.ThreadRecv')
                thread_actions[0] = 'recv_reply'
                thread_action_event.set()
                thread_comm_app.action_to_do[0] = 'recv_reply'
                thread_comm_app.action_event.set()
                time.sleep(1)
                # if exc[0]:
                #     raise exc[0]
                # if thread_comm_app.exc:
                #     raise thread_comm_app.exc
                for msg in send_msgs:
                    thread_comm.send(msg)
                    thread_comm_app.send_msg(msg)
                for msg in send_msgs:
                    exp_recv_msg = get_exp_recv_msg(msg)
                    recv_msg = thread_comm.recv()
                    assert recv_msg == exp_recv_msg
                    recv_msg = thread_comm_app.recv_msg()
                    assert recv_msg == exp_recv_msg
                thread_complete_event.wait()
                thread_complete_event.clear()
                thread_comm_app.complete_event.wait()
                thread_comm_app.complete_event.clear()
            elif action == Action.MainSendRecv:
                logger.debug('main starting Action.MainSendRecv')
                thread_actions[0] = 'recv_reply'
                thread_action_event.set()
                thread_comm_app.action_to_do[0] = 'recv_reply'
                thread_comm_app.action_event.set()
                # if exc[0]:
                #     raise exc[0]
                # if thread_comm_app.exc:
                #     raise thread_comm_app.exc
                for msg in send_msgs:
                    exp_recv_msg = get_exp_recv_msg(msg)
                    recv_msg = thread_comm.send_recv(msg)
                    assert recv_msg == exp_recv_msg
                    recv_msg = thread_comm_app.send_recv_msg(msg)
                    assert recv_msg == exp_recv_msg
                thread_complete_event.wait()
                thread_complete_event.clear()
                thread_comm_app.complete_event.wait()
                thread_comm_app.complete_event.clear()
            elif action == Action.ThreadSendRecv:
                logger.debug('main starting Action.ThreadSendRecv')
                thread_actions[0] = 'send_recv'
                thread_action_event.set()
                thread_comm_app.action_to_do[0] = 'send_recv'
                thread_comm_app.action_event.set()
                time.sleep(1)
                # if exc[0]:
                #     raise exc[0]
                # if thread_comm_app.exc:
                #     raise thread_comm_app.exc
                for msg in send_msgs:
                    recv_msg = thread_comm.recv()
                    assert recv_msg == msg
                    recv_msg = thread_comm_app.recv_msg()
                    assert recv_msg == msg
                    reply_msg = get_exp_recv_msg(msg)
                    thread_comm.send(reply_msg)
                    thread_comm_app.send_msg(reply_msg)
                thread_complete_event.wait()
                thread_complete_event.clear()
                thread_comm_app.complete_event.wait()
                thread_comm_app.complete_event.clear()
            else:
                raise IncorrectActionSpecified('The Action is not recognized')

        logger.debug('main completed all actions')
        thread_actions[0] = 'exit'
        thread_action_event.set()
        f1_thread.join()

        thread_comm_app.action_to_do[0] = 'exit'
        thread_comm_app.action_event.set()
        thread_comm_app.join()

    ###########################################################################
    # test_thread_comm_simple_main_send
    ###########################################################################
    def test_thread_comm_simple_main_send(self,
                                          msg_arg: Any
                                          ) -> None:
        """Test the ThreadComm with main send.

        Args:
            msg_arg: the message to be sent by main

        """
        def f1(in_thread_comm: ThreadComm,
               exp_msg: int) -> None:
            """Thread to receive message.

            Args:
                in_thread_comm: the thread_comm to test
                exp_msg: expected message to receive

            """
            logger.debug('thread f1 about to recv msg')
            msg = in_thread_comm.recv()
            logger.debug(f'thread f1 received message {msg}')
            assert msg == exp_msg

        thread_comm = ThreadComm()

        f1_thread = threading.Thread(target=f1,
                                     args=(thread_comm,
                                           msg_arg))

        logger.debug('main about to start f1 thread')
        f1_thread.start()
        logger.debug(f'main about to send msg {msg_arg}')
        thread_comm.send(msg_arg)
        f1_thread.join()

    ###########################################################################
    # test_thread_comm_simple_main_send2
    ###########################################################################
    def test_thread_comm_simple_main_send2(self,
                                           msg_arg: Any
                                           ) -> None:
        """Test the ThreadComm with main send2.

        Args:
            msg_arg: the message to be sent by main

        """
        class ThreadCommApp(threading.Thread):
            def __init__(self,
                         exp_msg: Any) -> None:
                super().__init__()
                self.thread_comm = ThreadComm()
                self.exp_msg = exp_msg

            def run(self):
                """Thread to receive message."""
                logger.debug('thread f1 about to recv msg')
                msg = self.thread_comm.recv()
                logger.debug(f'thread f1 received message {msg}')
                assert msg == self.exp_msg

            def send_msg(self):
                self.thread_comm.send(self.exp_msg)

        logger.debug('main about to start f1 thread')
        thread_comm_app = ThreadCommApp(msg_arg)
        thread_comm_app.start()
        logger.debug(f'main about to send msg {msg_arg}')
        thread_comm_app.send_msg()
        thread_comm_app.join()

    ###########################################################################
    # test_thread_comm_simple_main_recv
    ###########################################################################
    def test_thread_comm_simple_main_recv(self,
                                          msg_arg: Any
                                          ) -> None:
        """Test the ThreadComm with main recv.

        Args:
            msg_arg: the message to be sent by thread

        """
        def f1(in_thread_comm: ThreadComm,
                msg: int) -> None:
            """Thread to receive message.

            Args:
                in_thread_comm: instance of ThreadComm
                msg: msg to send
            """
            logger.debug('thread f1 about to send msg')
            in_thread_comm.send(msg)
            logger.debug(f'thread f1 sent message {msg}')

        thread_comm = ThreadComm()

        f1_thread = threading.Thread(target=f1,
                                     args=(thread_comm,
                                           msg_arg))

        logger.debug('main about to start f1 thread')
        f1_thread.start()
        logger.debug('main about to receive msg from thread')
        msg_received = thread_comm.recv()
        f1_thread.join()
        assert msg_received == msg_arg

    ###########################################################################
    # test_thread_comm_simple_main_recv2
    ###########################################################################
    def test_thread_comm_simple_main_recv2(self,
                                           msg_arg: Any
                                           ) -> None:
        """Test the ThreadComm with main recv.

        Args:
            msg_arg: the message to be sent by thread

        """
        class ThreadCommApp(threading.Thread):
            def __init__(self,
                         msg: Any) -> None:
                super().__init__()
                self.thread_comm = ThreadComm()
                self.msg = msg

            def run(self):
                """Thread to receive message."""
                logger.debug('thread f1 about to send msg')
                self.thread_comm.send(self.msg)
                logger.debug(f'thread f1 sent message {self.msg}')

            def recv_msg(self):
                return self.thread_comm.recv()

        logger.debug('main about to start f1 thread')
        thread_comm_app = ThreadCommApp(msg_arg)
        thread_comm_app.start()
        logger.debug('main about to receive msg from thread')
        received_msg = thread_comm_app.recv_msg()
        thread_comm_app.join()

        assert received_msg == msg_arg

    ###########################################################################
    # test_thread_comm_simple_main_send_recv
    ###########################################################################
    def test_thread_comm_simple_main_send_recv(self,
                                               msg_arg: Any,
                                               reply_arg: Any
                                               ) -> None:
        """Test the ThreadComm with main send_recv.

        Args:
            msg_arg: the message to be sent by main
            reply_arg: message to be received by main

        """
        def f1(in_thread_comm: ThreadComm,
               exp_msg: Any,
               reply: Any) -> None:
            """Thread to receive and send reply message.

            Args:
                in_thread_comm: the ThreadComm object
                exp_msg: expected message
                reply: message to send back

            """
            logger.debug('thread f1 about to recv msg')
            msg = in_thread_comm.recv()
            assert msg == exp_msg
            logger.debug(f'thread f1 received message {msg}')
            logger.debug(f'thread f1 about to send reply {reply}')
            in_thread_comm.send(reply)
            logger.debug(f'thread f1 sent replay {reply}')

        thread_comm = ThreadComm()

        f1_thread = threading.Thread(target=f1,
                                     args=(thread_comm,
                                           msg_arg,
                                           reply_arg))

        logger.debug('main about to start f1 thread')

        f1_thread.start()
        logger.debug(f'main about to send msg {msg_arg} to thread and '
                     'receive reply')
        msg_received = thread_comm.send_recv(msg_arg)
        assert msg_received == reply_arg
        f1_thread.join()

    ###########################################################################
    # test_thread_comm_simple_main_send_recv2
    ###########################################################################
    def test_thread_comm_simple_main_send_recv2(self,
                                                msg_arg: Any,
                                                reply_arg: Any
                                                ) -> None:
        """Test the ThreadComm with main recv.

        Args:
            msg_arg: the message to be sent by main
            reply_arg: message to be received by main

        Raises:
            exc: exception from the ThreadCommApp

        """
        class ThreadCommApp(threading.Thread):
            def __init__(self,
                         exp_msg: Any,
                         reply: Any) -> None:
                super().__init__()
                self.thread_comm = ThreadComm()
                self.exp_msg = exp_msg
                self.reply = reply
                self.exc = None

            def run(self):
                """Thread to receive message."""
                try:
                    logger.debug('thread f1 about to recv msg')
                    msg = self.thread_comm.recv()
                    logger.debug(f'thread f1 received message {msg}')
                    assert msg == self.exp_msg
                    logger.debug('thread f1 about to send msg')
                    self.thread_comm.send(self.reply)
                    logger.debug(f'thread f1 sent message {self.reply}')
                except Exception as TCA_e:
                    self.exc = TCA_e

            def send_recv_msg(self, msg: Any):
                return self.thread_comm.send_recv(msg)

        logger.debug('main about to start f1 thread')
        thread_comm_app = ThreadCommApp(msg_arg, reply_arg)
        thread_comm_app.start()
        logger.debug('main about to send and receive msg from thread')
        received_msg = thread_comm_app.send_recv_msg(msg_arg)
        thread_comm_app.join()
        if thread_comm_app.exc:
            raise thread_comm_app.exc

        assert received_msg == reply_arg

    ###########################################################################
    # test_thread_comm_simple_thread_send_recv
    ###########################################################################
    def test_thread_comm_simple_thread_send_recv(self,
                                                 msg_arg: Any,
                                                 reply_arg: Any
                                                 ) -> None:
        """Test the ThreadComm with thread send_recv.

        Args:
            msg_arg: the message to be sent by thread
            reply_arg: message to be received by thread

        Raises:
            exc[0]: exception from thread

        """
        def f1(in_thread_comm: ThreadComm,
               msg: Any,
               exp_reply: Any,
               exc1: List[Any]) -> None:
            """Thread to send and receive reply message.

            Args:
                in_thread_comm: instance of ThreadComm
                msg: message to send
                exp_reply: expected reply to receive
                exc1: where to place any exceptions to mainline can see it

            """
            try:
                logger.debug(f'thread f1 about to send msg {msg} and receive')
                recv_msg = in_thread_comm.send_recv(msg)
                logger.debug(f'thread f1 received message {recv_msg}')
                assert recv_msg == exp_reply
            except Exception as f1_e:
                exc1[0] = f1_e

        thread_comm = ThreadComm()
        exc = [None]

        f1_thread = threading.Thread(target=f1,
                                     args=(thread_comm,
                                           msg_arg,
                                           reply_arg,
                                           exc))

        logger.debug('main about to start f1 thread')
        try:
            f1_thread.start()
            logger.debug('main about to recv msg and send reply to thread')
            msg_received = thread_comm.recv()
            assert msg_received == msg_arg
            thread_comm.send(reply_arg)
            f1_thread.join()
            if exc[0]:
                raise exc[0]
        except Exception as e:
            logger.exception(f'exception {e!r}')
            raise

    ###########################################################################
    # test_thread_comm_simple_thread_send_recv2
    ###########################################################################
    def test_thread_comm_simple_thread_send_recv2(self,
                                                  msg_arg: Any,
                                                  reply_arg: Any
                                                  ) -> None:
        """Test the ThreadComm with thread send_recv2.

        Args:
            msg_arg: the message to be sent by thread
            reply_arg: message to be received by thread

        Raises:
            exc: exception from the ThreadCommApp
        """
        class ThreadCommApp(threading.Thread):
            def __init__(self,
                         msg: Any,
                         exp_reply: Any) -> None:
                super().__init__()
                self.thread_comm = ThreadComm()
                self.msg = msg
                self.exp_reply = exp_reply
                self.exc = None

            def run(self):
                """Thread to receive message."""
                try:
                    logger.debug(
                        f'thread about to send msg {self.msg} and receive')
                    recv_msg = self.thread_comm.send_recv(self.msg)
                    logger.debug(f'thread f1 received message {recv_msg}')
                    assert recv_msg == self.exp_reply
                except Exception as TCA_e:
                    self.exc = TCA_e

            def recv_msg(self):
                return self.thread_comm.recv()

            def send_msg(self, msg):
                self.thread_comm.send(msg)

        logger.debug('main about to create and start ThreadCommApp')
        thread_comm_app = ThreadCommApp(msg_arg, reply_arg)
        thread_comm_app.start()
        logger.debug('main about to receive msg from thread')
        received_msg = thread_comm_app.recv_msg()
        logger.debug('main about to send reply to thread')
        thread_comm_app.send_msg(reply_arg)
        thread_comm_app.join()
        if thread_comm_app.exc:
            raise thread_comm_app.exc

        assert received_msg == msg_arg
