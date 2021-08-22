"""test_smart_event.py module."""

from enum import Enum
from dataclasses import dataclass
import time
import pytest
from typing import Any, cast, Dict, Final, List, NamedTuple, Optional, Union
import threading
import queue
import re

from scottbrian_paratools.smart_event import (SmartEvent,
                                              WUCond,
                                              AlreadyPairedWithRemote,
                                              ConflictDeadlockDetected,
                                              DetectedOpFromForeignThread,
                                              ErrorInRegistry,
                                              InconsistentFlagSettings,
                                              IncorrectNameSpecified,
                                              NameAlreadyInUse,
                                              NotPaired,
                                              PairWithSelfNotAllowed,
                                              PairWithTimedOut,
                                              RemotePairedWithOther,
                                              RemoteThreadNotAlive,
                                              WaitDeadlockDetected,
                                              WaitUntilTimeout)

import logging

logger = logging.getLogger(__name__)
logger.debug('about to start the tests')


###############################################################################
# SmartEvent test exceptions
###############################################################################
class ErrorTstSmartEvent(Exception):
    """Base class for exception in this module."""
    pass


class IncorrectActionSpecified(ErrorTstSmartEvent):
    """IncorrectActionSpecified exception class."""
    pass


class UnrecognizedMessageType(ErrorTstSmartEvent):
    """UnrecognizedMessageType exception class."""
    pass


class UnrecognizedCmd(ErrorTstSmartEvent):
    """UnrecognizedCmd exception class."""
    pass


class CmdTimedOut(ErrorTstSmartEvent):
    """Cmds timed out exception class."""
    pass


###############################################################################
# Cmd Constants
###############################################################################
Cmd = Enum('Cmd', 'Wait Wait_TOT Wait_TOF Wait_Clear Resume Sync Exit '
                  'Next_Action')

###############################################################################
# Action
###############################################################################
Action = Enum('Action',
              'MainWait '
              'MainSync MainSync_TOT MainSync_TOF '
              'MainResume MainResume_TOT MainResume_TOF '
              'ThreadWait ThreadWait_TOT ThreadWait_TOF '
              'ThreadResume ')

###############################################################################
# action_arg fixtures
###############################################################################
action_arg_list = [Action.MainWait,
                   Action.MainSync,
                   Action.MainSync_TOT,
                   Action.MainSync_TOF,
                   Action.MainResume,
                   Action.MainResume_TOT,
                   Action.MainResume_TOF,
                   Action.ThreadWait,
                   Action.ThreadWait_TOT,
                   Action.ThreadWait_TOF,
                   Action.ThreadResume]

action_arg_list1 = [Action.MainWait
                    # Action.MainResume,
                    # Action.MainResume_TOT,
                    # Action.MainResume_TOF,
                    # Action.ThreadWait,
                    # Action.ThreadWait_TOT,
                    # Action.ThreadWait_TOF,
                    # Action.ThreadResume
                    ]

action_arg_list2 = [  # Action.MainWait,
                    # Action.MainResume,
                    # Action.MainResume_TOT,
                    Action.MainResume_TOF
                    # Action.ThreadWait,
                    # Action.ThreadWait_TOT,
                    # Action.ThreadWait_TOF,
                    # Action.ThreadResume
                    ]


@pytest.fixture(params=action_arg_list)  # type: ignore
def action_arg1(request: Any) -> Any:
    """Using different reply messages.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return request.param


@pytest.fixture(params=action_arg_list)  # type: ignore
def action_arg2(request: Any) -> Any:
    """Using different reply messages.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return request.param


###############################################################################
# timeout_arg fixtures
###############################################################################
timeout_arg_list = [None, 'TO_False', 'TO_True']


@pytest.fixture(params=timeout_arg_list)  # type: ignore
def timeout_arg1(request: Any) -> Any:
    """Using different requests.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return request.param


@pytest.fixture(params=timeout_arg_list)  # type: ignore
def timeout_arg2(request: Any) -> Any:
    """Using different requests.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return request.param


###############################################################################
# code fixtures
###############################################################################
code_arg_list = [None, 42]


@pytest.fixture(params=code_arg_list)  # type: ignore
def code_arg1(request: Any) -> Any:
    """Using different codes.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


@pytest.fixture(params=code_arg_list)  # type: ignore
def code_arg2(request: Any) -> Any:
    """Using different codes.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


###############################################################################
# log_msg fixtures
###############################################################################
log_msg_arg_list = [None, 'log msg1']


@pytest.fixture(params=log_msg_arg_list)  # type: ignore
def log_msg_arg1(request: Any) -> Any:
    """Using different log messages.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


@pytest.fixture(params=log_msg_arg_list)  # type: ignore
def log_msg_arg2(request: Any) -> Any:
    """Using different log messages.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


###############################################################################
# log_enabled fixtures
###############################################################################
log_enabled_list = [True, False]


@pytest.fixture(params=log_enabled_list)  # type: ignore
def log_enabled_arg(request: Any) -> bool:
    """Using different log messages.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(bool, request.param)


###############################################################################
# TestSmartEventBasic class to test SmartEvent methods
###############################################################################
###############################################################################
# ThreadCmd Class
###############################################################################
class Cmds:
    """Cmd class for testing."""
    def __init__(self):
        """Initialize the object."""
        # self.alpha_cmd = queue.Queue(maxsize=10)
        # self.beta_cmd = queue.Queue(maxsize=10)
        self.cmd_array: Dict[str, Any] = {}
        self.cmd_lock = threading.Lock()
        self.l_msg: Any = None
        self.r_code: Any = None
        self.start_time: float = 0.0
        self.previous_start_time: float = 0.0
        self.clock_in_use = False
        self.iteration = 0

    def queue_cmd(self, who: str, cmd: Optional[Any] = 'go') -> None:
        """Place a cmd on the cmd queue for the specified who.

        Args:
            who: alpha when cmd is for alpha, beta when cmd is for beta
            cmd: command to place on queue

        Raises:
            ValueError: who must be alpha or beta

        """
        with self.cmd_lock:
            if who not in self.cmd_array:
                self.cmd_array[who] = queue.Queue(maxsize=10)

        self.cmd_array[who].put(cmd,
                                block=True,
                                timeout=0.5)

        # if who == 'alpha':
        #     self.alpha_cmd.put(cmd,
        #                        block=True,
        #                        timeout=0.5)
        # elif who == 'beta':
        #     self.beta_cmd.put(cmd,
        #                       block=True,
        #                       timeout=0.5)
        # else:
        #     raise ValueError

    def get_cmd(self,
            who: str,
            timeout: Optional[Union[float, int]] = 3) -> Any:
        """Get the next command for alpha to do.

        Args:
            who: alpha to get cmd for alpha to do, beta for cmd for beta to do

        Returns:
            the cmd to perform

        Raises:
            ValueError: who must be alpha or beta

        """
        with self.cmd_lock:
            if who not in self.cmd_array:
                self.cmd_array[who] = queue.Queue(maxsize=10)

        start_time = time.time()
        while True:
            try:
                cmd = self.cmd_array[who].get(block=True, timeout=0.1)
                return cmd
            except queue.Empty:
                pass

            if timeout < (time.time() - start_time):
                raise CmdTimedOut(f'{who} timed out waiting for cmd')


        # while True:
        #     try:
        #         if who == 'alpha':
        #             cmd = self.alpha_cmd.get(block=True, timeout=0.1)
        #         elif who == 'beta':
        #             cmd = self.beta_cmd.get(block=True, timeout=0.1)
        #         else:
        #             raise ValueError
        #         return cmd
        #     except queue.Empty:
        #         continue

    def pause(self, seconds: Union[int, float], iter: int) -> None:
        """Sleep for the number of input seconds relative to start_time.

        Args:
            seconds: number of seconds to pause
            iter: clock iteration to pause on

        """
        while iter != self.iteration:
            time.sleep(0.1)

        # self.previous_start_time = self.start_time

        remaining_seconds = seconds - (time.time() - self.start_time)
        if remaining_seconds > 0:
            time.sleep(remaining_seconds)

    def start_clock(self, iter: int) -> None:
        """Set the start_time to the current time.

        Args:
            iter: iteration to set for the clock
        """
        while self.clock_in_use:
            time.sleep(0.1)
        self.clock_in_use = True
        self.start_time = time.time()
        self.iteration = iter

    def duration(self) -> float:
        """Return the number of seconds from the start_time.

        Returns:
            number of seconds from the start_time
        """
        ret_duration = time.time() - self.start_time
        self.clock_in_use = False
        return ret_duration

###############################################################################
# verify_registry
###############################################################################
class SmartEventDesc:
    """Describes a SmartEvent with name and thread to verify."""

    STATE_UNKNOWN: Final[int] = 0
    STATE_ALIVE_REGISTERED: Final[int] = 1
    STATE_NOT_ALIVE_REGISTERED: Final[int] = 2
    STATE_NOT_ALIVE_UNREGISTERED: Final[int] = 3

    def __init__(self,
                 name: Optional[str] = '',
                 s_event: Optional[SmartEvent] = None,
                 thread: Optional[threading.Thread] = None,  # type: ignore
                 state: Optional[int] = 0,  # 0 is unknown
                 paired_with: Optional[Any] = None) -> None:
        self.name = name
        self.s_event = s_event
        if thread is not None:
            self.thread = thread
        else:
            self.thread = threading.current_thread()

        self.state = state
        self.paired_with = paired_with

    def verify_state(self) -> None:
        self.verify_smart_event_desc()
        if self.paired_with is not None:
            self.paired_with.verify_smart_event_desc()

    ###########################################################################
    # verify_smart_event_init
    ###########################################################################
    def verify_smart_event_desc(self) -> None:
        """Verify the SmartEvent object is initialized correctly."""
        assert isinstance(self.s_event, SmartEvent)
        assert isinstance(self.s_event.event, threading.Event)
        assert isinstance(self.thread, threading.Thread)

        assert self.s_event.name == self.name
        assert self.s_event.thread is self.thread

        assert not self.s_event.wait_wait
        assert not self.s_event.wait_timeout_specified
        assert not self.s_event.deadlock
        assert not self.s_event.conflict
        assert self.s_event.code is None

        assert isinstance(self.s_event.debug_logging_enabled, bool)

        #######################################################################
        # verify state
        #######################################################################
        if self.state == SmartEventDesc.STATE_ALIVE_REGISTERED:
            assert self.thread.is_alive()
            assert self.name in SmartEvent._registry
            assert SmartEvent._registry[self.name] is self.s_event
        elif self.state == SmartEventDesc.STATE_NOT_ALIVE_REGISTERED:
            assert not self.thread.is_alive()
            assert self.name in SmartEvent._registry
            assert SmartEvent._registry[self.name] is self.s_event
        elif self.state == SmartEventDesc.STATE_NOT_ALIVE_UNREGISTERED:
            assert not self.thread.is_alive()
            # the registry might have a new entry with the same name as a
            # residual SmartEvent, so we also need to check to make sure
            # the old SmartEvent is not in the registry
            assert (self.name not in SmartEvent._registry
                    or SmartEvent._registry[self.name] is not self.s_event)

        #######################################################################
        # verify paired with desc
        #######################################################################
        if self.paired_with is None:
            assert self.s_event.remote is None
        else:
            assert self.s_event.remote is self.paired_with.s_event
            # if current is alive, remote must point back to current
            if self.state == SmartEventDesc.STATE_ALIVE_REGISTERED:
                assert self.s_event.remote.remote is self.s_event


class SmartEventDescs:
    """Contains a collection of SmartEventDesc items."""

    ###########################################################################
    # __init__
    ###########################################################################
    def __init__(self):
        """Initialize object."""
        self._descs_lock = threading.RLock()
        self.descs: Dict[str, SmartEventDesc] = {}

    ###########################################################################
    # add_desc
    ###########################################################################
    def add_desc(self, desc: SmartEventDesc) -> None:
        """Add desc to collection.

        Args:
            desc: the desc to add

        """
        with self._descs_lock:
            self.cleanup_registry()
            desc.state = SmartEventDesc.STATE_ALIVE_REGISTERED
            self.descs[desc.name] = desc
            self.verify_registry()

    ###########################################################################
    # thread_end
    ###########################################################################
    def thread_end(self,
                   name: str) -> None:
        """Update SmartEventDescs to show a thread ended.

        Args:
            name: name of SmartEvent for desc to be updated

        """
        with self._descs_lock:
            # Note that this action does not cause registry cleanup
            # make sure thread is not alive
            assert not self.descs[name].s_event.thread.is_alive()

            # make sure we are transitioning correctly
            assert (self.descs[name].state
                    == SmartEventDesc.STATE_ALIVE_REGISTERED)
            self.descs[name].state = SmartEventDesc.STATE_NOT_ALIVE_REGISTERED

            ###################################################################
            # verify the registry
            ###################################################################
            self.verify_registry()

    ###########################################################################
    # cleanup
    ###########################################################################
    def cleanup(self) -> None:
        """Perform cleanup for SmartEventDescs."""

        # Cleanup applies to all of the descs and is done
        # when first thing when a new SmartEvent is instantiated and
        # registered, or when a pair_with is done. This action is called
        # here for the other cases that trigger cleanup, such as
        # getting a RemoteThreadNotAlive error.
        with self._descs_lock:
            self.cleanup_registry()

            ###################################################################
            # verify the registry
            ###################################################################
            self.verify_registry()

    ###########################################################################
    # paired
    ###########################################################################
    def paired(self,
               name1: Optional[str] = '',
               name2: Optional[str] = '') -> None:
        """Update SmartEventDescs to show paired status.

        Args:
            name1: name of SmartEvent for desc that is paired with name2
            name2: name of SmartEvent for desc that is paired with name1, or
                   null if name1 became unpaired

        """
        with self._descs_lock:
            self.cleanup_registry()
            # make sure we can allow the pair
            assert self.descs[name1].s_event.thread.is_alive()
            assert (self.descs[name1].state
                    == SmartEventDesc.STATE_ALIVE_REGISTERED)
            assert name1 in SmartEvent._registry
            assert name1 in self.descs

            # note that name2 will normally be the SmartEventDesc
            # that we are pairing with, but it could be None in the case
            # where we are doing a second or subsequent pairing but the
            # remote fails to to do the pair, which means we lose the
            # residual name2 SmartEventDesc
            if name2:
                assert name2 in SmartEvent._registry
                assert self.descs[name2].s_event.thread.is_alive()
                assert (self.descs[name2].state
                        == SmartEventDesc.STATE_ALIVE_REGISTERED)
                assert name2 in SmartEvent._registry
                assert name2 in self.descs
                self.descs[name1].paired_with = self.descs[name2]
                self.descs[name2].paired_with = self.descs[name1]
            else:
                self.descs[name1].paired_with = None

            ###################################################################
            # verify the registry
            ###################################################################
            self.verify_registry()

    ###########################################################################
    # verify_registry
    ###########################################################################
    def verify_registry(self):
        with self._descs_lock:
            num_registered = 0
            for key, item in self.descs.items():
                if (item.state == SmartEventDesc.STATE_ALIVE_REGISTERED
                        or item.state
                        == SmartEventDesc.STATE_NOT_ALIVE_REGISTERED):
                    num_registered += 1
                item.verify_state()

            assert len(SmartEvent._registry) == num_registered

    ###########################################################################
    # cleanup_registry
    ###########################################################################
    def cleanup_registry(self):
        for key, item in self.descs.items():
            if item.state == SmartEventDesc.STATE_NOT_ALIVE_REGISTERED:
                assert not item.s_event.thread.is_alive()
                item.state = SmartEventDesc.STATE_NOT_ALIVE_UNREGISTERED


###############################################################################
# outer_f1
###############################################################################
def outer_f1(cmds: Cmds,
             descs: SmartEventDescs,
             ) -> None:
    """Outer function to test SmartEvent.

    Args:
        cmds: Cmds object to tell alpha when to go
        descs: tracks set of SmartEventDesc items

    """
    logger.debug('outer_f1 entered')
    s_event = SmartEvent(name='beta')
    descs.add_desc(SmartEventDesc(name='beta',
                                  s_event=s_event))

    # tell alpha OK to verify (i.e., beta_smart_event set with s_event)
    cmds.queue_cmd('alpha', 'go')

    s_event.pair_with(remote_name='alpha')

    assert s_event.sync(log_msg='outer beta sync point 1')
    assert s_event.wait(log_msg='outer f1 wait 12')
    assert s_event.sync(log_msg='outer beta sync point 2')
    assert s_event.resume(log_msg='outer f1 resume 23')
    assert s_event.sync(log_msg='outer beta sync point 3')

    logger.debug('outer f1 exiting')


###############################################################################
# OuterThreadApp class
###############################################################################
class OuterThreadApp(threading.Thread):
    """Outer thread app for test."""
    def __init__(self,
                 cmds: Cmds,
                 descs: SmartEventDescs
                 ) -> None:
        """Initialize the object.

        Args:
            cmds: used to tell alpha to go
            descs: tracks set of SmartEventDescs items

        """
        super().__init__()
        self.cmds = cmds
        self.descs = descs
        self.s_event = SmartEvent(name='beta', thread=self)

    def run(self) -> None:
        """Run the test."""
        print('beta run started')

        # normally, the add_desc is done just after the instantiation, but
        # in this case the thread is not made alive until now, and the
        # add_desc checks that the thread is alive
        self.descs.add_desc(SmartEventDesc(name='beta',
                                           s_event=self.s_event,
                                           thread=self))

        self.cmds.queue_cmd('alpha')

        self.s_event.pair_with(remote_name='alpha')
        self.descs.paired('alpha', 'beta')

        assert self.s_event.sync(log_msg='outer beta sync point 1')
        assert self.s_event.wait(log_msg='outer f1 wait 12')
        assert self.s_event.sync(log_msg='outer beta sync point 2')
        assert self.s_event.resume(log_msg='outer f1 resume 23')
        assert self.s_event.sync(log_msg='outer beta sync point 3')

        logger.debug('beta run exiting')


###############################################################################
# OuterThreadEventApp class
###############################################################################
class OuterThreadEventApp(threading.Thread, SmartEvent):
    """Outer thread event app for test."""
    def __init__(self,
                 cmds: Cmds,
                 descs: SmartEventDescs) -> None:
        """Initialize the object.

        Args:
            descs: tracks set of SmartEventDesc items

        """
        threading.Thread.__init__(self)
        SmartEvent.__init__(self, name='beta', thread=self)
        self.cmds = cmds
        self.descs = descs

    def run(self):
        """Run the test."""
        print('beta run started')

        # normally, the add_desc is done just after the instantiation, but
        # in this case the thread is not made alive until now, and the
        # add_desc checks that the thread is alive
        self.descs.add_desc(SmartEventDesc(name='beta',
                                           s_event=self,
                                           thread=self))

        self.cmds.queue_cmd('alpha')

        self.pair_with(remote_name='alpha', timeout=3)
        self.descs.paired('alpha', 'beta')

        assert self.sync(log_msg='outer beta sync point 1')
        assert self.wait(log_msg='outer f1 wait 12')
        assert self.sync(log_msg='outer beta sync point 2')
        assert self.resume(log_msg='outer f1 resume 23')
        assert self.sync(log_msg='outer beta sync point 3')

        logger.debug('beta run exiting')


###############################################################################
# TestSmartEventBasic class
###############################################################################
class TestSmartEventBasic:
    """Test class for SmartEvent basic tests."""

    ###########################################################################
    # repr for SmartEvent
    ###########################################################################
    def test_smart_event_repr(self,
                              thread_exc: Any) -> None:
        """Test event with code repr.

        Args:
            thread_exc: captures thread exceptions

        """
        descs = SmartEventDescs()

        smart_event = SmartEvent(name='alpha')
        descs.add_desc(SmartEventDesc(name='alpha',
                                      s_event=smart_event,
                                      thread=threading.current_thread()))

        expected_repr_str = 'SmartEvent(name="alpha")'

        assert repr(smart_event) == expected_repr_str

        smart_event2 = SmartEvent(name="AlphaDog")
        descs.add_desc(SmartEventDesc(name='AlphaDog',
                                      s_event=smart_event2,
                                      thread=threading.current_thread()))

        expected_repr_str = 'SmartEvent(name="AlphaDog")'

        assert repr(smart_event2) == expected_repr_str

        def f1():
            s_event = SmartEvent(name='beta1')
            descs.add_desc(SmartEventDesc(name='beta1',
                                          s_event=s_event,
                                          thread=threading.current_thread()))
            f1_expected_repr_str = 'SmartEvent(name="beta1")'
            assert repr(s_event) == f1_expected_repr_str

            cmds.queue_cmd('alpha', 'go')
            cmds.get_cmd('beta1')

        def f2():
            s_event = SmartEvent(name='beta2')
            descs.add_desc(SmartEventDesc(name='beta2',
                                          s_event=s_event,
                                          thread=threading.current_thread()))
            f1_expected_repr_str = 'SmartEvent(name="beta2")'
            assert repr(s_event) == f1_expected_repr_str
            cmds.queue_cmd('alpha', 'go')
            cmds.get_cmd('beta2')

        cmds = Cmds()
        a_thread1 = threading.Thread(target=f1)
        a_thread1.start()

        cmds.get_cmd('alpha')

        a_thread2 = threading.Thread(target=f2)
        a_thread2.start()

        cmds.get_cmd('alpha')
        cmds.queue_cmd('beta1', 'go')
        a_thread1.join()
        descs.thread_end('beta1')
        cmds.queue_cmd('beta2', 'go')
        a_thread2.join()
        descs.thread_end('beta2')

    ###########################################################################
    # test_smart_event_instantiate_with_errors
    ###########################################################################
    def test_smart_event_instantiate_with_errors(self) -> None:
        """Test register_thread alpha first."""
        alpha_t = threading.current_thread()

        descs = SmartEventDescs()

        smart_event = SmartEvent(name='alpha')

        descs.add_desc(SmartEventDesc(name='alpha',
                                      s_event=smart_event,
                                      thread=threading.current_thread()))

        # not OK to instantiate a new smart_event with same name
        with pytest.raises(NameAlreadyInUse):
            smart_event2 = SmartEvent(name='alpha')

        with pytest.raises(IncorrectNameSpecified):
            smart_event2 = SmartEvent(name=42)  # type: ignore

        # try wait, resume, and pause_until without having been paired
        with pytest.raises(NotPaired):
            smart_event.wait()

        with pytest.raises(NotPaired):
            smart_event.resume()

        with pytest.raises(NotPaired):
            smart_event.pause_until(WUCond.RemoteWaiting)

        # try to pair with unknown remote
        with pytest.raises(PairWithTimedOut):
            smart_event.pair_with(remote_name='beta', timeout=0.1)

        # try to pair with bad name
        with pytest.raises(IncorrectNameSpecified):
            smart_event.pair_with(remote_name=3)  # type: ignore

        # make sure everything still the same

        descs.verify_registry()

    ###########################################################################
    # test_smart_event_pairing_with_errors
    ###########################################################################
    def test_smart_event_pairing_with_errors(self) -> None:
        """Test register_thread during instantiation."""
        def f1(name: str) -> None:
            """Func to test instantiate SmartEvent.

            Args:
                name: name to use for s_event
            """
            logger.debug(f'{name} f1 entered')
            s_event = SmartEvent(name=name)
            descs.add_desc(SmartEventDesc(name=name,
                                          s_event=s_event))

            cmds.queue_cmd('alpha', 'go')

            # not OK to pair with self
            with pytest.raises(PairWithSelfNotAllowed):
                s_event.pair_with(remote_name=name)

            s_event.pair_with(remote_name='alpha')

            # not OK to pair with remote a second time
            with pytest.raises(AlreadyPairedWithRemote):
                s_event.pair_with(remote_name='alpha')

            s_event.sync(timeout=3,
                         log_msg=f'{name} f1 sync point 1')

            logger.debug(f'{name} f1 exiting')

        cmds = Cmds()

        descs = SmartEventDescs()

        beta_t = threading.Thread(target=f1, args=('beta',))

        smart_event = SmartEvent(name='alpha')

        descs.add_desc(SmartEventDesc(name='alpha',
                                      s_event=smart_event,
                                      thread=threading.current_thread()))
        beta_t.start()

        # not OK to pair with self
        with pytest.raises(PairWithSelfNotAllowed):
            smart_event.pair_with(remote_name='alpha')

        cmds.get_cmd('alpha')

        smart_event.pair_with(remote_name='beta')
        descs.paired('alpha', 'beta')

        # not OK to pair with remote a second time
        with pytest.raises(AlreadyPairedWithRemote):
            smart_event.pair_with(remote_name='beta')

        smart_event.sync(log_msg='alpha sync point 1')

        beta_t.join()

        descs.thread_end(name='beta')

        # at this point, f1 has ended. But, the registry will not have changed,
        # so everything will still show paired, even both alpha and beta
        # SmartEvents. Alpha SmartEvent will detect that beta is no longer
        # alive if a function is attempted.
        descs.verify_registry()

        #######################################################################
        # second case - f1 with same name beta
        #######################################################################
        beta_t2 = threading.Thread(target=f1, args=('beta',))
        beta_t2.start()

        cmds.get_cmd('alpha')

        smart_event.pair_with(remote_name='beta')
        descs.paired('alpha', 'beta')

        smart_event.sync(log_msg='alpha sync point 1 again')

        beta_t2.join()

        descs.thread_end(name='beta')

        # at this point, f1 has ended. But, the registry will not have changed,
        # so everything will still show paired, even both alpha and beta
        # SmartEvents. Alpha SmartEvent will detect that beta is no longer
        # alive if a function is attempted.
        descs.verify_registry()

        #######################################################################
        # third case, use different name for f1. Should clean up old beta
        # from the registry.
        #######################################################################
        with pytest.raises(NameAlreadyInUse):
            smart_event = SmartEvent(name='alpha')  # create fresh

        beta_t3 = threading.Thread(target=f1, args=('charlie',))
        beta_t3.start()

        cmds.get_cmd('alpha')

        smart_event.pair_with(remote_name='charlie')
        descs.paired('alpha', 'charlie')

        assert 'beta' not in SmartEvent._registry

        smart_event.sync(log_msg='alpha sync point 1 again')

        beta_t3.join()

        descs.thread_end(name='charlie')

        # at this point, f1 has ended. But, the registry will not have changed,
        # so everything will still show paired, even both alpha and charlie
        # SmartEvents. Alpha SmartEvent will detect that charlie is no longer
        # alive if a function is attempted.
        descs.verify_registry()

    ###########################################################################
    # test_smart_event_pairing_with_multiple_threads
    ###########################################################################
    def test_smart_event_pairing_with_multiple_threads(self) -> None:
        """Test register_thread during instantiation."""
        def f1(name: str) -> None:
            """Func to test instantiate SmartEvent.

            Args:
                name: name to use for s_event
            """
            logger.debug(f'{name} f1 entered')
            s_event = SmartEvent(name=name)

            descs.add_desc(SmartEventDesc(name=name,
                                          s_event=s_event))

            # not OK to pair with self
            with pytest.raises(PairWithSelfNotAllowed):
                s_event.pair_with(remote_name=name)

            cmds.queue_cmd('alpha', 'go')

            s_event.pair_with(remote_name='alpha')
            descs.paired('alpha', 'beta')

            # alpha needs to wait until we are officially paired to avoid
            # timing issue when pairing with charlie
            cmds.queue_cmd('alpha')

            # not OK to pair with remote a second time
            with pytest.raises(AlreadyPairedWithRemote):
                s_event.pair_with(remote_name='alpha')

            cmds.queue_cmd('alpha', 'go')

            s_event.sync(log_msg=f'{name} f1 sync point 1')

            logger.debug(f'{name} f1 exiting')

        def f2(name: str) -> None:
            """Func to test instantiate SmartEvent.

            Args:
                name: name to use for s_event
            """
            logger.debug(f'{name} f2 entered')
            s_event = SmartEvent(name=name)

            descs.add_desc(SmartEventDesc(name=name,
                                          s_event=s_event))

            # not OK to pair with self
            with pytest.raises(PairWithSelfNotAllowed):
                s_event.pair_with(remote_name=name)
                
            with pytest.raises(PairWithTimedOut):
                s_event.pair_with(remote_name='alpha', timeout=1)

            s_event.pair_with(remote_name='alpha2')

            descs.paired('alpha2', 'charlie')

            # not OK to pair with remote a second time
            with pytest.raises(AlreadyPairedWithRemote):
                s_event.pair_with(remote_name='alpha2')

            cmds.queue_cmd('alpha', 'go')

            s_event.sync(log_msg=f'{name} f1 sync point 1')

            logger.debug(f'{name} f2 exiting')

        #######################################################################
        # mainline
        #######################################################################
        descs = SmartEventDescs()

        cmds = Cmds()

        beta_t = threading.Thread(target=f1, args=('beta',))
        charlie_t = threading.Thread(target=f2, args=('charlie',))

        smart_event = SmartEvent(name='alpha')

        descs.add_desc(SmartEventDesc(name='alpha',
                                      s_event=smart_event))

        beta_t.start()

        cmds.get_cmd('alpha')

        smart_event.pair_with(remote_name='beta')

        #######################################################################
        # pair with charlie
        #######################################################################
        cmds.get_cmd('alpha')

        smart_event2 = SmartEvent(name='alpha2')

        descs.add_desc(SmartEventDesc(name='alpha2',
                                      s_event=smart_event2))

        charlie_t.start()

        smart_event2.pair_with(remote_name='charlie')

        cmds.get_cmd('alpha')

        smart_event.sync(log_msg='alpha sync point 1')

        beta_t.join()

        descs.thread_end(name='beta')

        smart_event2.sync(log_msg='alpha sync point 2')

        charlie_t.join()

        descs.thread_end(name='charlie')

        # at this point, f1 and f2 have ended. But, the registry will not have
        # changed, so everything will still show paired, even all
        # SmartEvents. Any SmartEvents requests will detect that
        # their pairs are no longer active and will trigger cleanup to
        # remove any not alive entries from the registry. The SmartEvent
        # objects for not alive threads remain pointed to by the alive
        # entries so that they may still report RemoteThreadNotAlive.
        descs.verify_registry()

        # cause cleanup via a sync request
        with pytest.raises(RemoteThreadNotAlive):
            smart_event.sync(log_msg='mainline sync point 3')

        descs.cleanup()

        # try to pair with old beta - should timeout
        with pytest.raises(PairWithTimedOut):
            smart_event.pair_with(remote_name='beta', timeout=1)

        # the pair_with sets smart_event.remote to none before trying the
        # pair_with, and leaves it None when pair_with fails
        descs.paired('alpha')

        # try to pair with old charlie - should timeout
        with pytest.raises(PairWithTimedOut):
            smart_event.pair_with(remote_name='charlie', timeout=1)

        # try to pair with nobody - should timeout
        with pytest.raises(PairWithTimedOut):
            smart_event.pair_with(remote_name='nobody', timeout=1)

        # try to pair with old beta - should timeout
        with pytest.raises(PairWithTimedOut):
            smart_event2.pair_with(remote_name='beta', timeout=1)

        # the pair_with sets smart_event.remote to none before trying the
        # pair_with, and leaves it None when pair_with fails
        descs.paired('alpha2')

        # try to pair with old charlie - should timeout
        with pytest.raises(PairWithTimedOut):
            smart_event2.pair_with(remote_name='charlie', timeout=1)

        # try to pair with nobody - should timeout
        with pytest.raises(PairWithTimedOut):
            smart_event2.pair_with(remote_name='nobody', timeout=1)

        descs.verify_registry()

    ###########################################################################
    # test_smart_event_pairing_cleanup
    ###########################################################################
    def test_smart_event_pairing_cleanup(self) -> None:
        """Test register_thread during instantiation."""
        def f1(name: str, remote_name: str, idx: int) -> None:
            """Func to test instantiate SmartEvent.

            Args:
                name: name to use for s_event
                remote_name: name to pair with
                idx: index into beta_smart_events

            """
            logger.debug(f'{name} f1 entered, remote {remote_name}, idx {idx}')
            s_event = SmartEvent(name=name)

            descs.add_desc(SmartEventDesc(name=name,
                                          s_event=s_event))

            cmds.queue_cmd('alpha')

            s_event.pair_with(remote_name=remote_name,
                              log_msg=f'f1 {name} pair with {remote_name} '
                                      f'for idx {idx}')

            s_event.sync(log_msg=f'{name} f1 sync point 1')

            assert s_event.sync(timeout=3,
                                log_msg=f'{name} f1 sync point 2')

            logger.debug(f'{name} f1 exiting')

        #######################################################################
        # mainline start
        #######################################################################
        cmds = Cmds()

        descs = SmartEventDescs()

        #######################################################################
        # create 4 beta threads
        #######################################################################
        beta_t0 = threading.Thread(target=f1, args=('beta0', 'alpha0', 0))
        beta_t1 = threading.Thread(target=f1, args=('beta1', 'alpha1', 1))
        beta_t2 = threading.Thread(target=f1, args=('beta2', 'alpha2', 2))
        beta_t3 = threading.Thread(target=f1, args=('beta3', 'alpha3', 3))

        #######################################################################
        # create alpha0 SmartEvent and desc, and verify
        #######################################################################
        smart_event0 = SmartEvent(name='alpha0')
        descs.add_desc(SmartEventDesc(name='alpha0',
                                      s_event=smart_event0))

        #######################################################################
        # create alpha1 SmartEvent and desc, and verify
        #######################################################################
        smart_event1 = SmartEvent(name='alpha1')
        descs.add_desc(SmartEventDesc(name='alpha1',
                                      s_event=smart_event1))

        #######################################################################
        # create alpha2 SmartEvent and desc, and verify
        #######################################################################
        smart_event2 = SmartEvent(name='alpha2')
        descs.add_desc(SmartEventDesc(name='alpha2',
                                      s_event=smart_event2))

        #######################################################################
        # create alpha3 SmartEvent and desc, and verify
        #######################################################################
        smart_event3 = SmartEvent(name='alpha3')
        descs.add_desc(SmartEventDesc(name='alpha3',
                                      s_event=smart_event3))

        #######################################################################
        # start beta0 thread, and verify
        #######################################################################
        beta_t0.start()

        cmds.get_cmd('alpha')

        smart_event0.pair_with(remote_name='beta0')

        smart_event0.sync(log_msg='alpha0 sync point 1')
        descs.paired('alpha0', 'beta0')

        #######################################################################
        # start beta1 thread, and verify
        #######################################################################
        beta_t1.start()

        cmds.get_cmd('alpha')

        smart_event1.pair_with(remote_name='beta1')

        smart_event1.sync(log_msg='alpha1 sync point 1')
        descs.paired('alpha1', 'beta1')

        #######################################################################
        # start beta2 thread, and verify
        #######################################################################
        beta_t2.start()

        cmds.get_cmd('alpha')

        smart_event2.pair_with(remote_name='beta2')

        smart_event2.sync(log_msg='alpha2 sync point 1')
        descs.paired('alpha2', 'beta2')

        #######################################################################
        # start beta3 thread, and verify
        #######################################################################
        beta_t3.start()

        cmds.get_cmd('alpha')

        smart_event3.pair_with(remote_name='beta3')

        smart_event3.sync(log_msg='alpha3 sync point 1')
        descs.paired('alpha3', 'beta3')

        #######################################################################
        # let beta0 finish
        #######################################################################
        smart_event0.sync(log_msg='alpha0 sync point 1')

        beta_t0.join()

        descs.thread_end(name='beta0')

        #######################################################################
        # replace old beta0 w new beta0 - should cleanup registry old beta0
        #######################################################################
        beta_t0 = threading.Thread(target=f1, args=('beta0', 'alpha0', 0))

        beta_t0.start()

        cmds.get_cmd('alpha')

        smart_event0.pair_with(remote_name='beta0')

        smart_event0.sync(log_msg='alpha0 sync point 1')
        descs.paired('alpha0', 'beta0')

        #######################################################################
        # let beta1 and beta3 finish
        #######################################################################
        smart_event1.sync(log_msg='alpha1 sync point 2')
        beta_t1.join()
        descs.thread_end(name='beta1')

        smart_event3.sync(log_msg='alpha3 sync point 3')
        beta_t3.join()
        descs.thread_end(name='beta3')

        #######################################################################
        # replace old beta1 w new beta1 - should cleanup old beta1 and beta3
        #######################################################################
        beta_t1 = threading.Thread(target=f1, args=('beta1', 'alpha1', 1))

        beta_t1.start()

        cmds.get_cmd('alpha')

        smart_event1.pair_with(remote_name='beta1')

        smart_event1.sync(log_msg='alpha1 sync point 1')
        descs.paired('alpha1', 'beta1')

        # should get not alive for beta3
        with pytest.raises(RemoteThreadNotAlive):
            smart_event3.sync(log_msg='mainline sync point 4')

        # should still be the same
        descs.verify_registry()

        #######################################################################
        # get a new beta3 going
        #######################################################################
        beta_t3 = threading.Thread(target=f1, args=('beta3', 'alpha3', 3))

        beta_t3.start()

        cmds.get_cmd('alpha')

        smart_event3.pair_with(remote_name='beta3')

        smart_event3.sync(log_msg='alpha3 sync point 1')
        descs.paired('alpha3', 'beta3')

        #######################################################################
        # let beta1 and beta2 finish
        #######################################################################
        smart_event1.sync(log_msg='alpha1 sync point 5')
        beta_t1.join()
        descs.thread_end(name='beta1')

        smart_event2.sync(log_msg='alpha2 sync point 6')
        beta_t2.join()
        descs.thread_end(name='beta2')

        #######################################################################
        # trigger cleanup for beta1 and beta2
        #######################################################################
        with pytest.raises(RemoteThreadNotAlive):
            smart_event2.sync(log_msg='alpha2 sync point 7')

        descs.cleanup()

        #######################################################################
        # should get RemoteThreadNotAlive for beta1 and beta2
        #######################################################################
        with pytest.raises(RemoteThreadNotAlive):
            smart_event1.sync(log_msg='alpha1 sync point 8')

        with pytest.raises(RemoteThreadNotAlive):
            smart_event2.sync(log_msg='alpha 2 sync point 9')

        descs.verify_registry()

        #######################################################################
        # get a new beta2 going
        #######################################################################
        beta_t2 = threading.Thread(target=f1, args=('beta2', 'alpha2', 2))

        beta_t2.start()

        cmds.get_cmd('alpha')

        smart_event2.pair_with(remote_name='beta2')

        smart_event2.sync(log_msg='alpha2 sync point 1')
        descs.paired('alpha2', 'beta2')

        smart_event2.sync(log_msg='alpha2 sync point 2')
        beta_t2.join()
        descs.thread_end(name='beta2')

        #######################################################################
        # let beta0 complete
        #######################################################################
        smart_event0.sync(log_msg='alpha0 sync point 2')
        beta_t0.join()
        descs.thread_end(name='beta0')

        #######################################################################
        # let beta3 complete
        #######################################################################
        smart_event3.sync(log_msg='alpha0 sync point 2')
        beta_t3.join()
        descs.thread_end(name='beta3')

    ###########################################################################
    # test_smart_event_foreign_op_detection
    ###########################################################################
    def test_smart_event_foreign_op_detection(self) -> None:
        """Test register_thread with f1."""
        #######################################################################
        # mainline and f1 - mainline pairs with beta
        #######################################################################
        logger.debug('start test 1')

        def f1():
            print('beta f1 entered')
            s_event = SmartEvent(name='beta')

            descs.add_desc(SmartEventDesc(name='beta',
                                          s_event=s_event))

            my_c_thread = threading.current_thread()
            assert s_event.thread is my_c_thread
            assert s_event.thread is threading.current_thread()

            s_event.pair_with(remote_name='alpha')

            s_event.sync(log_msg='f1 beta sync point 1')

            logger.debug('f1 beta about to enter cmd loop')

            while True:
                beta_cmd = cmds.get_cmd('beta')
                if beta_cmd == Cmd.Exit:
                    break

                logger.debug(f'thread_func1 received cmd: {beta_cmd}')

                if beta_cmd == Cmd.Wait:
                    assert s_event.wait()

                elif beta_cmd == Cmd.Resume:
                    with pytest.raises(WaitUntilTimeout):
                        s_event.pause_until(WUCond.RemoteWaiting,
                                            timeout=0.002)
                    with pytest.raises(WaitUntilTimeout):
                        s_event.pause_until(WUCond.RemoteWaiting, timeout=0.01)
                    with pytest.raises(WaitUntilTimeout):
                        s_event.pause_until(WUCond.RemoteWaiting, timeout=0.02)

                    s_event.sync(log_msg='f1 beta sync point 2')

                    s_event.pause_until(WUCond.RemoteWaiting)
                    s_event.pause_until(WUCond.RemoteWaiting, timeout=0.001)
                    s_event.pause_until(WUCond.RemoteWaiting, timeout=0.01)
                    s_event.pause_until(WUCond.RemoteWaiting, timeout=0.02)
                    s_event.pause_until(WUCond.RemoteWaiting, timeout=-0.02)
                    s_event.pause_until(WUCond.RemoteWaiting, timeout=-1)
                    s_event.pause_until(WUCond.RemoteWaiting, timeout=0)

                    s_event.resume()

        def foreign1(s_event):
            logger.debug('foreign1 entered')

            with pytest.raises(DetectedOpFromForeignThread):
                s_event.resume()

            with pytest.raises(DetectedOpFromForeignThread):
                s_event.pair_with(remote_name='beta')

            with pytest.raises(DetectedOpFromForeignThread):
                s_event.pair_with(remote_name='beta', timeout=1)

            with pytest.raises(DetectedOpFromForeignThread):
                s_event.pause_until(WUCond.RemoteWaiting, timeout=0.02)

            with pytest.raises(DetectedOpFromForeignThread):
                s_event.pause_until(WUCond.RemoteWaiting, timeout=0.02)
            with pytest.raises(DetectedOpFromForeignThread):
                s_event.pause_until(WUCond.RemoteWaiting)
            with pytest.raises(DetectedOpFromForeignThread):
                s_event.wait()

            with pytest.raises(DetectedOpFromForeignThread):
                s_event.sync()

            logger.debug('foreign1 exiting')

        cmds = Cmds()
        descs = SmartEventDescs()

        smart_event1 = SmartEvent(name='alpha')
        descs.add_desc(SmartEventDesc(name='alpha',
                                      s_event=smart_event1))

        alpha_t = threading.current_thread()
        my_f1_thread = threading.Thread(target=f1)
        my_foreign1_thread = threading.Thread(target=foreign1,
                                              args=(smart_event1,))

        with pytest.raises(NotPaired):
            smart_event1.pause_until(WUCond.RemoteWaiting, timeout=-0.002)
        with pytest.raises(NotPaired):
            smart_event1.pause_until(WUCond.RemoteWaiting, timeout=0)
        with pytest.raises(NotPaired):
            smart_event1.pause_until(WUCond.RemoteWaiting, timeout=0.002)
        with pytest.raises(NotPaired):
            smart_event1.pause_until(WUCond.RemoteWaiting, timeout=0.2)
        with pytest.raises(NotPaired):
            smart_event1.pause_until(WUCond.RemoteWaiting)

        logger.debug('mainline about to start beta thread')

        my_f1_thread.start()

        smart_event1.pair_with(remote_name='beta')
        descs.paired('alpha', 'beta')

        smart_event1.sync(log_msg='mainline sync point 1')

        cmds.queue_cmd('beta', Cmd.Wait)

        my_foreign1_thread.start()  # attempt to resume beta (should fail)

        my_foreign1_thread.join()

        logger.debug('about to pause_until RemoteWaiting')
        smart_event1.pause_until(WUCond.RemoteWaiting)
        smart_event1.pause_until(WUCond.RemoteWaiting, timeout=0.001)
        smart_event1.pause_until(WUCond.RemoteWaiting, timeout=0.01)
        smart_event1.pause_until(WUCond.RemoteWaiting, timeout=0.02)
        smart_event1.pause_until(WUCond.RemoteWaiting, timeout=-0.02)
        smart_event1.pause_until(WUCond.RemoteWaiting, timeout=-1)
        smart_event1.pause_until(WUCond.RemoteWaiting, timeout=0)

        smart_event1.resume()

        cmds.queue_cmd('beta', Cmd.Resume)

        smart_event1.sync(log_msg='mainline sync point 2')

        assert smart_event1.wait()

        cmds.queue_cmd('beta', Cmd.Exit)

        my_f1_thread.join()
        descs.thread_end(name='beta')

        with pytest.raises(RemoteThreadNotAlive):
            smart_event1.resume()

        with pytest.raises(RemoteThreadNotAlive):
            smart_event1.wait()

        with pytest.raises(RemoteThreadNotAlive):
            smart_event1.pause_until(WUCond.RemoteWaiting)

        with pytest.raises(RemoteThreadNotAlive):
            smart_event1.sync(log_msg='mainline sync point 3')

        assert smart_event1.thread is alpha_t

    ###########################################################################
    # test_smart_event_outer_thread_f1
    ###########################################################################
    def test_smart_event_outer_thread_f1(self) -> None:
        """Test simple sequence with outer thread f1."""
        #######################################################################
        # mainline
        #######################################################################
        logger.debug('mainline starting')

        cmds = Cmds()
        descs = SmartEventDescs()

        smart_event = SmartEvent(name='alpha')
        descs.add_desc(SmartEventDesc(name='alpha',
                                      s_event=smart_event))

        f1_thread = threading.Thread(target=outer_f1, args=(cmds, descs))
        f1_thread.start()

        cmds.get_cmd('alpha')

        smart_event.pair_with(remote_name='beta')
        descs.paired('alpha', 'beta')

        smart_event.sync(log_msg='mainline sync point 1')

        smart_event.resume(log_msg='alpha resume 12')

        smart_event.sync(log_msg='mainline sync point 2')

        smart_event.wait(log_msg='alpha wait 23')

        smart_event.sync(log_msg='mainline sync point 3')

        f1_thread.join()
        descs.thread_end(name='beta')

        logger.debug('mainline exiting')

    ###########################################################################
    # test_smart_event_outer_thread_app
    ###########################################################################
    def test_smart_event_outer_thread_app(self) -> None:
        """Test simple sequence with outer thread app."""
        #######################################################################
        # mainline
        #######################################################################
        logger.debug('mainline starting')
        cmds = Cmds()
        descs = SmartEventDescs()

        smart_event = SmartEvent(name='alpha')
        descs.add_desc(SmartEventDesc(name='alpha',
                                      s_event=smart_event))

        thread_app = OuterThreadApp(cmds=cmds, descs=descs)

        thread_app.start()

        cmds.get_cmd('alpha')
        smart_event.pair_with(remote_name='beta', timeout=3)

        smart_event.sync(log_msg='mainline sync point 1')

        smart_event.resume(log_msg='alpha resume 12')

        smart_event.sync(log_msg='mainline sync point 2')

        smart_event.wait(log_msg='alpha wait 23')

        smart_event.sync(log_msg='mainline sync point 3')

        thread_app.join()
        descs.thread_end(name='beta')

        logger.debug('mainline exiting')

    ###########################################################################
    # test_smart_event_outer_thread_app
    ###########################################################################
    def test_smart_event_outer_thread_event_app(self) -> None:
        """Test simple sequence with outer thread event app."""
        #######################################################################
        # mainline
        #######################################################################
        logger.debug('mainline starting')
        cmds = Cmds()
        descs = SmartEventDescs()
        smart_event = SmartEvent(name='alpha')
        descs.add_desc(SmartEventDesc(name='alpha',
                                      s_event=smart_event))

        thread_event_app = OuterThreadEventApp(cmds=cmds, descs=descs)
        thread_event_app.start()

        cmds.get_cmd('alpha')

        smart_event.pair_with(remote_name='beta', timeout=3)

        smart_event.sync(log_msg='mainline sync point 1')

        smart_event.resume(log_msg='alpha resume 12')

        smart_event.sync(log_msg='mainline sync point 2')

        smart_event.wait(log_msg='alpha wait 23')

        smart_event.sync(log_msg='mainline sync point 3')

        thread_event_app.join()

        descs.thread_end(name='beta')

        logger.debug('mainline exiting')

    ###########################################################################
    # test_smart_event_wait_deadlock_detection
    ###########################################################################
    def test_smart_event_wait_deadlock_detection(self) -> None:
        """Test deadlock detection with f1."""
        #######################################################################
        # f1
        #######################################################################

        def f1(ml_thread):
            logger.debug('beta f1 beta entered')
            s_event = SmartEvent(name='beta')

            descs.add_desc(SmartEventDesc(name='beta',
                                          s_event=s_event))

            my_c_thread = threading.current_thread()

            cmds.get_cmd('beta')

            s_event.pair_with(remote_name='alpha')
            assert s_event.remote.thread is ml_thread
            assert s_event.remote.thread is alpha_t
            assert s_event.thread is my_c_thread
            assert s_event.thread is threading.current_thread()

            s_event.sync(log_msg='beta f1 thread sync point 1')

            with pytest.raises(WaitDeadlockDetected):
                s_event.wait()

            s_event.sync(log_msg='beta f1 thread sync point 2')

            s_event.wait()  # clear the resume that comes after the deadlock

            s_event.sync(log_msg='beta f1 thread sync point 3')

            s_event.pause_until(WUCond.RemoteWaiting, timeout=2)
            with pytest.raises(WaitDeadlockDetected):
                s_event.wait()

            s_event.sync(log_msg='beta f1 thread sync point 4')

            s_event.resume()

        #######################################################################
        # mainline start
        #######################################################################
        cmds = Cmds()
        descs = SmartEventDescs()
        alpha_t = threading.current_thread()
        smart_event = SmartEvent(name='alpha')
        descs.add_desc(SmartEventDesc(name='alpha',
                                      s_event=smart_event))

        my_f1_thread = threading.Thread(target=f1, args=(alpha_t,))

        with pytest.raises(NotPaired):
            smart_event.pause_until(WUCond.RemoteWaiting, timeout=-0.002)
        with pytest.raises(NotPaired):
            smart_event.pause_until(WUCond.RemoteWaiting, timeout=0)
        with pytest.raises(NotPaired):
            smart_event.pause_until(WUCond.RemoteWaiting, timeout=0.002)
        with pytest.raises(NotPaired):
            smart_event.pause_until(WUCond.RemoteWaiting, timeout=0.2)
        with pytest.raises(NotPaired):
            smart_event.pause_until(WUCond.RemoteWaiting)

        my_f1_thread.start()

        with pytest.raises(NotPaired):
            smart_event.pause_until(WUCond.RemoteWaiting)

        # tell f1 to proceed to pair_with
        cmds.queue_cmd('beta', Cmd.Exit)

        smart_event.pair_with(remote_name='beta', timeout=3)
        descs.paired('alpha', 'beta')

        smart_event.sync(log_msg='mainline sync point 1')

        with pytest.raises(WaitDeadlockDetected):
            smart_event.wait()

        smart_event.sync(log_msg='mainline sync point 2')

        smart_event.resume()

        smart_event.sync(log_msg='mainline sync point 3')

        with pytest.raises(WaitDeadlockDetected):
            smart_event.wait()

        smart_event.sync(log_msg='mainline sync point 4')

        assert smart_event.wait()  # clear resume

        my_f1_thread.join()
        descs.thread_end(name='beta')

        with pytest.raises(RemoteThreadNotAlive):
            smart_event.resume()

        descs.cleanup()

        with pytest.raises(RemoteThreadNotAlive):
            smart_event.wait()

        with pytest.raises(RemoteThreadNotAlive):
            smart_event.sync(log_msg='mainline sync point 5')

        assert smart_event.thread is alpha_t
        assert smart_event.remote.thread is my_f1_thread

    ###########################################################################
    # test_smart_event_inner_thread_app
    ###########################################################################
    def test_smart_event_inner_thread_app(self) -> None:
        """Test SmartEvent with thread_app."""
        #######################################################################
        # ThreadApp
        #######################################################################
        class MyThread(threading.Thread):
            """MyThread class to test SmartEvent."""

            def __init__(self,
                         alpha_smart_event: SmartEvent,
                         alpha_thread: threading.Thread
                         ) -> None:
                """Initialize the object.

                Args:
                    alpha_smart_event: alpha SmartEvent to use for verification
                    alpha_thread: alpha thread to use for verification
                    beta_smart_events: used to tell alpha the beta SmartEvent

                """
                super().__init__()
                self.s_event = SmartEvent(name='beta', thread=self)
                self.alpha_s_event = alpha_smart_event
                self.alpha_thread = alpha_thread

            def run(self):
                """Run the tests."""
                logger.debug('run started')

                # normally, the add_desc is done just after the
                # instantiation, but
                # in this case the thread is not made alive until now, and the
                # add_desc checks that the thread is alive
                descs.add_desc(SmartEventDesc(name='beta',
                                              s_event=self.s_event,
                                              thread=self))

                cmds.queue_cmd('alpha')
                self.s_event.pair_with(remote_name='alpha')
                descs.paired('alpha', 'beta')

                assert self.s_event.remote is self.alpha_s_event
                assert (self.s_event.remote.thread
                        is self.alpha_thread)
                assert self.s_event.remote.thread is alpha_t
                assert self.s_event.thread is self
                my_run_thread = threading.current_thread()
                assert self.s_event.thread is my_run_thread
                assert self.s_event.thread is threading.current_thread()

                with pytest.raises(WaitUntilTimeout):
                    self.s_event.pause_until(WUCond.RemoteResume,
                                             timeout=0.009)
                self.s_event.sync(log_msg='beta run sync point 1')
                self.s_event.pause_until(WUCond.RemoteResume, timeout=5)
                self.s_event.pause_until(WUCond.RemoteResume)

                assert self.s_event.wait(log_msg='beta run wait 12')

                self.s_event.sync(log_msg='beta run sync point 2')
                self.s_event.sync(log_msg='beta run sync point 3')

                self.s_event.resume()

                self.s_event.sync(log_msg='beta run sync point 4')
                logger.debug('beta run exiting 45')

        #######################################################################
        # mainline starts
        #######################################################################
        cmds = Cmds()
        descs = SmartEventDescs()
        alpha_t = threading.current_thread()
        smart_event1 = SmartEvent(name='alpha')
        descs.add_desc(SmartEventDesc(name='alpha',
                                      s_event=smart_event1))

        my_taa_thread = MyThread(smart_event1, alpha_t)

        my_taa_thread.start()

        cmds.get_cmd('alpha')

        smart_event1.pair_with(remote_name='beta')

        smart_event1.sync(log_msg='mainline sync point 1')

        assert smart_event1.resume(log_msg='mainline resume 12')

        smart_event1.sync(log_msg='mainline sync point 2')

        with pytest.raises(WaitUntilTimeout):
            smart_event1.pause_until(WUCond.RemoteResume, timeout=0.009)

        smart_event1.sync(log_msg='mainline sync point 3')

        smart_event1.pause_until(WUCond.RemoteResume, timeout=5)
        smart_event1.pause_until(WUCond.RemoteResume)

        assert smart_event1.wait(log_msg='mainline wait 34')
        smart_event1.sync(log_msg='mainline sync point 4')

        my_taa_thread.join()
        descs.thread_end('beta')

        with pytest.raises(RemoteThreadNotAlive):
            smart_event1.resume()
        descs.cleanup()

        with pytest.raises(RemoteThreadNotAlive):
            smart_event1.wait()

        with pytest.raises(RemoteThreadNotAlive):
            smart_event1.pause_until(WUCond.RemoteWaiting)

        with pytest.raises(RemoteThreadNotAlive):
            smart_event1.pause_until(WUCond.RemoteResume)

        with pytest.raises(PairWithTimedOut):
            smart_event1.pair_with(remote_name='beta', timeout=1)
        descs.paired('alpha')

        with pytest.raises(NotPaired):
            smart_event1.wait()

        with pytest.raises(NotPaired):
            smart_event1.pause_until(WUCond.RemoteWaiting)

        with pytest.raises(NotPaired):
            smart_event1.pause_until(WUCond.RemoteResume)

        assert smart_event1.thread is alpha_t
        assert smart_event1.remote is None

        descs.verify_registry()

    ###########################################################################
    # test_smart_event_inner_thread_app2
    ###########################################################################
    def test_smart_event_inner_thread_app2(self) -> None:
        """Test SmartEvent with thread_app."""
        #######################################################################
        # mainline and ThreadApp - mainline provide beta SmartEvent
        #######################################################################
        class MyThread2(threading.Thread):
            def __init__(self,
                         s_event: SmartEvent,
                         alpha_t1: threading.Thread):
                super().__init__()
                self.s_event = s_event
                # not really a good idea to set the thread - this test case
                # may not be realistic - need to consider whether the idea
                # of passing in a pre-instantiated SmartEvent (which gets
                # its thread set during instantiation) is something we want
                # to support given that we have to change the thread
                self.s_event.thread = self
                self.alpha_t1 = alpha_t1

            def run(self):
                print('run started')
                # normally, the add_desc is done just after the
                # instantiation, but
                # in this case the thread is not made alive until now, and the
                # add_desc checks that the thread is alive
                descs.add_desc(SmartEventDesc(name='beta',
                                              s_event=self.s_event,
                                              thread=self))

                cmds.queue_cmd('alpha')

                self.s_event.pair_with(remote_name='alpha2')

                assert self.s_event.remote.thread is self.alpha_t1
                assert self.s_event.remote.thread is alpha_t
                assert self.s_event.thread is self

                my_run_thread = threading.current_thread()
                assert self.s_event.thread is my_run_thread
                assert self.s_event.thread is threading.current_thread()

                with pytest.raises(WaitDeadlockDetected):
                    self.s_event.wait()

                assert self.s_event.wait()
                self.s_event.pause_until(WUCond.RemoteWaiting)
                self.s_event.pause_until(WUCond.RemoteWaiting, timeout=2)

                self.s_event.resume()

        cmds = Cmds()
        descs = SmartEventDescs()
        smart_event2 = SmartEvent(name='alpha2')
        descs.add_desc(SmartEventDesc(name='alpha2',
                                      s_event=smart_event2))

        smart_event3 = SmartEvent(name='beta')
        alpha_t = threading.current_thread()
        my_tab_thread = MyThread2(smart_event3, alpha_t)
        my_tab_thread.start()

        cmds.get_cmd('alpha')

        smart_event2.pair_with(remote_name='beta')
        descs.paired('alpha2', 'beta')

        smart_event2.pause_until(WUCond.RemoteWaiting)
        with pytest.raises(WaitDeadlockDetected):
            smart_event2.wait()
        smart_event2.resume()
        assert smart_event2.wait()

        my_tab_thread.join()
        descs.thread_end('beta')

        with pytest.raises(RemoteThreadNotAlive):
            smart_event2.resume()
        descs.cleanup()

        with pytest.raises(RemoteThreadNotAlive):
            smart_event2.wait()

        with pytest.raises(RemoteThreadNotAlive):
            smart_event2.pause_until(WUCond.RemoteWaiting)

        with pytest.raises(RemoteThreadNotAlive):
            smart_event2.pause_until(WUCond.RemoteResume)

        assert smart_event2.thread is alpha_t
        assert smart_event2.remote.thread is my_tab_thread

        descs.verify_registry()

    ###########################################################################
    # test_smart_event_inner_thread_event_app
    ###########################################################################
    def test_smart_event_inner_thread_event_app(self) -> None:
        """Test SmartEvent with thread_event_app."""
        #######################################################################
        # mainline and ThreadEventApp - mainline sets alpha and beta
        #######################################################################
        class MyThreadEvent1(threading.Thread, SmartEvent):
            def __init__(self,
                         alpha_t1: threading.Thread):
                threading.Thread.__init__(self)
                SmartEvent.__init__(self, name='beta', thread=self)
                self.alpha_t1 = alpha_t1

            def run(self):
                logger.debug('run started')
                # normally, the add_desc is done just after the
                # instantiation, but
                # in this case the thread is not made alive until now, and the
                # add_desc checks that the thread is alive
                descs.add_desc(SmartEventDesc(name='beta',
                                              s_event=self,
                                              thread=self))
                cmds.queue_cmd('alpha')
                self.pair_with(remote_name='alpha')
                descs.paired('alpha', 'beta')

                assert self.remote.thread is self.alpha_t1
                assert self.remote.thread is alpha_t
                assert self.thread is self
                my_run_thread = threading.current_thread()
                assert self.thread is my_run_thread
                assert self.thread is threading.current_thread()

                assert self.wait()
                self.pause_until(WUCond.RemoteWaiting, timeout=2)
                with pytest.raises(WaitDeadlockDetected):
                    self.wait()
                self.resume()
                logger.debug('run exiting')

        cmds = Cmds()
        descs = SmartEventDescs()
        alpha_t = threading.current_thread()

        my_te1_thread = MyThreadEvent1(alpha_t)
        with pytest.raises(DetectedOpFromForeignThread):
            my_te1_thread.pause_until(WUCond.RemoteWaiting,
                                      timeout=0.005)

        with pytest.raises(DetectedOpFromForeignThread):
            my_te1_thread.wait(timeout=0.005)

        with pytest.raises(DetectedOpFromForeignThread):
            my_te1_thread.resume(timeout=0.005)

        with pytest.raises(DetectedOpFromForeignThread):
            my_te1_thread.sync(timeout=0.005)

        with pytest.raises(DetectedOpFromForeignThread):
            my_te1_thread.pair_with(remote_name='alpha', timeout=0.5)

        assert my_te1_thread.remote is None
        assert my_te1_thread.thread is my_te1_thread

        my_te1_thread.start()

        cmds.get_cmd('alpha')
        smart_event = SmartEvent(name='alpha')
        descs.add_desc(SmartEventDesc(name='alpha',
                                      s_event=smart_event))

        with pytest.raises(NotPaired):
            smart_event.sync()

        with pytest.raises(NotPaired):
            smart_event.wait()

        with pytest.raises(NotPaired):
            smart_event.resume()

        smart_event.pair_with(remote_name='beta')

        smart_event.resume()
        with pytest.raises(WaitDeadlockDetected):
            smart_event.wait()

        assert smart_event.wait()

        my_te1_thread.join()
        descs.thread_end('beta')

        with pytest.raises(RemoteThreadNotAlive):
            smart_event.resume()

        with pytest.raises(RemoteThreadNotAlive):
            smart_event.wait()

        with pytest.raises(RemoteThreadNotAlive):
            smart_event.pause_until(WUCond.RemoteWaiting)

        with pytest.raises(RemoteThreadNotAlive):
            smart_event.pause_until(WUCond.RemoteResume)

        assert my_te1_thread.remote is not None
        assert my_te1_thread.remote.thread is not None
        assert my_te1_thread.remote.thread is alpha_t
        assert my_te1_thread.thread is my_te1_thread

    ###########################################################################
    # test_smart_event_inner_thread_event_app2
    ###########################################################################
    def test_smart_event_inner_thread_event_app2(self) -> None:
        """Test SmartEvent with thread_event_app."""

        #######################################################################
        # mainline and ThreadApp - mainline sets alpha thread_app sets beta
        #######################################################################
        class MyThreadEvent2(threading.Thread, SmartEvent):
            def __init__(self,
                         alpha_t1: threading.Thread):
                threading.Thread.__init__(self)
                SmartEvent.__init__(self, name='beta', thread=self)
                self.alpha_t1 = alpha_t1

            def run(self):
                logger.debug('run started')

                assert self.remote is None
                assert self.thread is self

                my_run_thread = threading.current_thread()
                assert self.thread is my_run_thread
                assert self.thread is threading.current_thread()

                # normally, the add_desc is done just after the
                # instantiation, but
                # in this case the thread is not made alive until now, and the
                # add_desc checks that the thread is alive
                descs.add_desc(SmartEventDesc(name='beta',
                                              s_event=self,
                                              thread=self))

                cmds.queue_cmd('alpha')
                self.pair_with(remote_name='alpha')
                assert self.remote.thread is self.alpha_t1
                assert self.remote.thread is alpha_t

                descs.paired('alpha', 'beta')

                with pytest.raises(WaitDeadlockDetected):
                    self.wait()
                assert self.wait()
                self.resume()
                logger.debug('run exiting')

        cmds = Cmds()
        descs = SmartEventDescs()
        alpha_t = threading.current_thread()
        my_te2_thread = MyThreadEvent2(alpha_t)

        my_te2_thread.start()

        cmds.get_cmd('alpha')
        smart_event = SmartEvent(name='alpha')
        descs.add_desc(SmartEventDesc(name='alpha',
                                      s_event=smart_event))

        smart_event.pair_with(remote_name='beta')

        smart_event.pause_until(WUCond.RemoteWaiting, timeout=2)
        with pytest.raises(WaitDeadlockDetected):
            smart_event.wait()

        assert smart_event.resume()
        assert smart_event.wait()

        my_te2_thread.join()
        descs.thread_end('beta')

        with pytest.raises(RemoteThreadNotAlive):
            smart_event.resume()

        with pytest.raises(RemoteThreadNotAlive):
            smart_event.wait()

        with pytest.raises(RemoteThreadNotAlive):
            smart_event.pause_until(WUCond.RemoteWaiting, timeout=2)

        with pytest.raises(RemoteThreadNotAlive):
            smart_event.pause_until(WUCond.RemoteResume, timeout=2)

        assert smart_event.thread is alpha_t
        assert smart_event.remote.thread is my_te2_thread

    ###########################################################################
    # test_smart_event_two_f_threads
    ###########################################################################
    def test_smart_event_two_f_threads(self) -> None:
        """Test register_thread with thread_event_app."""
        #######################################################################
        # two threads - mainline sets alpha and beta
        #######################################################################
        def fa1():
            logger.debug('fa1 entered')
            my_fa_thread = threading.current_thread()
            s_event = SmartEvent(name='fa1')
            descs.add_desc(SmartEventDesc(name='fa1',
                                          s_event=s_event,
                                          thread=my_fa_thread))

            assert s_event.thread is my_fa_thread

            s_event.pair_with(remote_name='fb1')
            descs.paired('fa1', 'fb1')

            logger.debug('fa1 about to wait')
            s_event.wait()
            logger.debug('fa1 back from wait')
            s_event.pause_until(WUCond.RemoteWaiting, timeout=2)
            s_event.resume()

        def fb1():
            logger.debug('fb1 entered')
            my_fb_thread = threading.current_thread()
            s_event = SmartEvent(name='fb1')
            descs.add_desc(SmartEventDesc(name='fb1',
                                          s_event=s_event,
                                          thread=my_fb_thread))

            assert s_event.thread is my_fb_thread

            s_event.pair_with(remote_name='fa1')

            logger.debug('fb1 about to resume')
            s_event.resume()
            s_event.wait()

            # tell mainline we are out of the wait - OK to do descs fa1 end
            cmds.queue_cmd('alpha')

            # wait for mainline to give to go ahead after doing descs fa1 end
            cmds.get_cmd('beta')

            with pytest.raises(RemoteThreadNotAlive):
                s_event.resume()

            descs.cleanup()

            with pytest.raises(RemoteThreadNotAlive):
                s_event.wait()

            with pytest.raises(RemoteThreadNotAlive):
                s_event.pause_until(WUCond.RemoteWaiting)

        #######################################################################
        # mainline
        #######################################################################
        cmds = Cmds()
        descs = SmartEventDescs()
        fa1_thread = threading.Thread(target=fa1)

        fb1_thread = threading.Thread(target=fb1)

        logger.debug('starting fa1_thread')
        fa1_thread.start()
        logger.debug('starting fb1_thread')
        fb1_thread.start()

        fa1_thread.join()
        cmds.get_cmd('alpha')
        descs.thread_end('fa1')

        cmds.queue_cmd('beta', 'go')

        fb1_thread.join()
        descs.thread_end('fb1')

    ###########################################################################
    # test_smart_event_two_f_threads2
    ###########################################################################
    def test_smart_event_two_f_threads2(self) -> None:
        """Test register_thread with thread_event_app."""

        #######################################################################
        # two threads - fa2 and fb2 set their own threads
        #######################################################################
        def fa2():
            logger.debug('fa2 entered')
            s_event = SmartEvent(name='fa2')
            my_fa_thread = threading.current_thread()

            assert s_event.thread is my_fa_thread
            descs.add_desc(SmartEventDesc(name='fa2',
                                          s_event=s_event,
                                          thread=my_fa_thread))

            s_event.pair_with(remote_name='fb2')

            cmds.get_cmd('beta')
            logger.debug('fa2 about to deadlock')
            with pytest.raises(WaitDeadlockDetected):
                logger.debug('fa2 about to wait')
                s_event.wait()
                logger.debug('fa2 back from wait')

            logger.debug('fa2 about to pause_until')
            s_event.pause_until(WUCond.RemoteWaiting, timeout=2)
            logger.debug('fa2 about to resume')
            s_event.resume()

            s_event.wait()
            logger.debug('fa2 exiting')

        def fb2():
            logger.debug('fb2 entered')
            s_event = SmartEvent(name='fb2')
            my_fb_thread = threading.current_thread()
            descs.add_desc(SmartEventDesc(name='fb2',
                                          s_event=s_event,
                                          thread=my_fb_thread))

            assert s_event.thread is my_fb_thread

            s_event.pair_with(remote_name='fa2')
            descs.paired('fa2', 'fb2')

            cmds.queue_cmd('beta')
            logger.debug('fb2 about to deadlock')
            with pytest.raises(WaitDeadlockDetected):
                logger.debug('fb2 about to wait')
                s_event.wait()
                logger.debug('fb2 back from wait')

            logger.debug('fb2 about to pause_until')
            logger.debug('fb2 about to wait')
            s_event.wait()
            s_event.resume()

            # tell mainline we are out of the wait - OK to do descs fa1 end
            cmds.queue_cmd('alpha')

            # wait for mainline to give to go ahead after doing descs fa1 end
            cmds.get_cmd('beta')

            logger.debug('fb2 about to try resume for RemoteThreadNotAlive')
            with pytest.raises(RemoteThreadNotAlive):
                s_event.resume()

            descs.cleanup()

            logger.debug('fb2 about to try wait for RemoteThreadNotAlive')

            with pytest.raises(RemoteThreadNotAlive):
                s_event.wait()

            logger.debug('fb2 exiting')

        cmds = Cmds()
        descs = SmartEventDescs()
        fa2_thread = threading.Thread(target=fa2)

        fb2_thread = threading.Thread(target=fb2)

        fa2_thread.start()
        fb2_thread.start()

        fa2_thread.join()

        cmds.get_cmd('alpha')

        descs.thread_end('fa2')

        cmds.queue_cmd('beta', 'go')

        fb2_thread.join()
        descs.thread_end('fb2')


###############################################################################
# TestResumeExc Class
###############################################################################
class TestResumeExc:
    """Test SmartEvent resume() exceptions."""
    ###########################################################################
    # test_smart_event_sync_f1
    ###########################################################################
    def test_smart_event_resume_exc_f1(self) -> None:
        """Test register_thread with f1."""

        def f1():
            logger.debug('f1 beta entered')
            s_event = SmartEvent(name='beta')
            descs.add_desc(SmartEventDesc(name='beta',
                                          s_event=s_event,
                                          thread=threading.current_thread()))

            cmds.queue_cmd('alpha')

            s_event.pair_with(remote_name='alpha')
            descs.paired('alpha', 'beta')

            s_event.sync(log_msg='f1 beta sync point 1')

            cmds.queue_cmd('alpha', 'go')
            cmds.get_cmd('beta')

            s_event.sync(log_msg='f1 beta sync point 2')

            s_event.resume(log_msg='f1 beta resume 3')

            s_event.sync(log_msg='f1 beta sync point 4')

            logger.debug('f1 beta exiting 5')

        logger.debug('mainline entered')
        cmds = Cmds()
        descs = SmartEventDescs()
        smart_event1 = SmartEvent(name='alpha')
        descs.add_desc(SmartEventDesc(name='alpha',
                                      s_event=smart_event1,
                                      thread=threading.current_thread()))

        f1_thread = threading.Thread(target=f1)

        f1_thread.start()

        cmds.get_cmd('alpha')
        smart_event1.pair_with(remote_name='beta')

        assert smart_event1.sync(log_msg='mainline sync point 1')

        cmds.get_cmd('alpha')

        smart_event1.remote.deadlock = True
        smart_event1.remote.conflict = True
        with pytest.raises(InconsistentFlagSettings):
            smart_event1.resume(log_msg='alpha error resume 1a')
        smart_event1.remote.deadlock = False
        smart_event1.remote.conflict = False

        smart_event1.remote.wait_wait = True
        smart_event1.remote.sync_wait = True
        with pytest.raises(InconsistentFlagSettings):
            smart_event1.resume(log_msg='alpha error resume 1b')
        smart_event1.remote.wait_wait = False
        smart_event1.remote.sync_wait = False

        smart_event1.remote.deadlock = True
        with pytest.raises(InconsistentFlagSettings):
            smart_event1.resume(log_msg='alpha error resume 1c')
        smart_event1.remote.deadlock = False

        smart_event1.remote.conflict = True
        with pytest.raises(InconsistentFlagSettings):
            smart_event1.resume(log_msg='alpha error resume 1d')
        smart_event1.remote.conflict = False

        cmds.queue_cmd('beta', 'go')

        smart_event1.sync(log_msg='mainline sync point 2')

        smart_event1.wait(log_msg='mainline wait 3')

        smart_event1.sync(log_msg='mainline sync point 4')

        f1_thread.join()
        descs.thread_end('beta')

        with pytest.raises(RemoteThreadNotAlive):
            smart_event1.resume(log_msg='mainline sync point 5')

        descs.cleanup()

        logger.debug('mainline exiting')


###############################################################################
# TestSync Class
###############################################################################
class TestSync:
    """Test SmartEvent sync function."""

    ###########################################################################
    # test_smart_event_sync_f1
    ###########################################################################
    def test_smart_event_sync_f1(self) -> None:
        """Test register_thread with f1."""

        def f1():
            logger.debug('f1 beta entered')

            s_event = SmartEvent(name='beta')
            descs.add_desc(SmartEventDesc(name='beta',
                                          s_event=s_event,
                                          thread=threading.current_thread()))
            cmds.queue_cmd('alpha')

            s_event.pair_with(remote_name='alpha')

            s_event.sync(log_msg='f1 beta sync point 1')

            s_event.wait()

            s_event.sync(log_msg='f1 beta sync point 2')

            s_event.resume()

            s_event.sync(log_msg='f1 beta sync point 3')

            s_event.sync(log_msg='f1 beta sync point 4')

            s_event.wait()

            logger.debug('f1 beta exiting')

        logger.debug('mainline entered')
        cmds = Cmds()
        descs = SmartEventDescs()
        smart_event1 = SmartEvent(name='alpha')
        descs.add_desc(SmartEventDesc(name='alpha',
                                      s_event=smart_event1,
                                      thread=threading.current_thread()))

        f1_thread = threading.Thread(target=f1)

        f1_thread.start()

        cmds.get_cmd('alpha')

        smart_event1.pair_with(remote_name='beta')
        descs.paired('alpha', 'beta')

        smart_event1.sync(log_msg='mainline sync point 1')

        smart_event1.resume()

        smart_event1.sync(log_msg='mainline sync point 2')

        smart_event1.wait()

        smart_event1.sync(log_msg='mainline sync point 3')

        smart_event1.resume()

        smart_event1.sync(log_msg='mainline sync point 4')

        f1_thread.join()
        descs.thread_end('beta')

        logger.debug('mainline exiting')

    ###########################################################################
    # test_smart_event_sync_exc
    ###########################################################################
    def test_smart_event_sync_exc(self,
                                  thread_exc: Any) -> None:
        """Test register_thread with f1.

        Args:
            thread_exc: capture thread exceptions
        """

        def f1():
            logger.debug('f1 beta entered')

            s_event = SmartEvent(name='beta')
            descs.add_desc(SmartEventDesc(name='beta',
                                          s_event=s_event,
                                          thread=threading.current_thread()))
            cmds.queue_cmd('alpha')

            s_event.pair_with(remote_name='alpha')
            descs.paired('alpha', 'beta')

            assert s_event.sync(log_msg='f1 beta sync point 1')

            with pytest.raises(ConflictDeadlockDetected):
                s_event.wait(log_msg='f1 beta wait 2')

            assert s_event.sync(log_msg='f1 beta sync point 3')

            s_event.resume(log_msg='f1 beta resume 4')

            assert s_event.sync(log_msg='f1 beta sync point 5')

            assert s_event.wait(log_msg='f1 beta wait 6')

            s_event.pause_until(WUCond.RemoteWaiting)

            s_event.resume()

            assert s_event.sync(log_msg='f1 beta sync point 8')

            # When one thread issues a sync request, and the other issues a
            # wait request, a conflict deadlock is recognized. The
            # process is of conflict detection is that one side recognizes the
            # conflict, sets a flag to tell the other side that the conflict
            # exists, and then raises the ConflictDeadlockDetected error.
            # The other side, upon seeing the conflict flag set, will also
            # raise the ConflictDeadlockDetected error.
            # We want to ensure that sync code that detects the conflict is
            # exercised here which requires setting certain flags in a way
            # that coaxes each side into behaving such that the sync
            # detection code will run. We will do this as follows:

            # make sure alpha is in sync code now looping in phase 1
            while not s_event.remote.sync_wait:
                time.sleep(.1)

            # make alpha think it is in sync phase 2 and continue looping
            # until beta sets sync_cleanup from True back to False
            with s_event.status.status_lock:
                s_event.remote.sync_wait = False
                s_event.status.sync_cleanup = True

            # pre-resume to set beta event and set alpha wait_wait to get beta
            # thinking alpha is resumed and waiting and will eventually
            # leave (i.e., get beta the think that alpha not in a sync
            # deadlock)
            s_event.resume()
            s_event.remote.wait_wait = True

            # Now issue the wait. There is no way to prove that alpha saw
            # the deadlock first, but we will see later whether the code
            # coverage will show that the sync detection code ran.
            with pytest.raises(ConflictDeadlockDetected):
                s_event.wait(log_msg='f1 beta wait 89')

            s_event.status.sync_cleanup = False

            assert s_event.sync(log_msg='f1 beta sync point 9')

            logger.debug('f1 beta exiting 10')

        logger.debug('mainline entered')
        cmds = Cmds()
        descs = SmartEventDescs()
        smart_event1 = SmartEvent(name='alpha')
        descs.add_desc(SmartEventDesc(name='alpha',
                                      s_event=smart_event1,
                                      thread=threading.current_thread()))

        f1_thread = threading.Thread(target=f1)

        f1_thread.start()

        cmds.get_cmd('alpha')
        smart_event1.pair_with(remote_name='beta')

        assert smart_event1.sync(log_msg='mainline sync point 1')

        # See the comments in f1 regarding the detection and handling of a
        # confict deadlock. We need to force the code in the following
        # scenario to behave such that beta will be the side that detects
        # the conflict. This will be done as follows:

        # make sure beta is looping in wait code
        smart_event1.pause_until(WUCond.RemoteWaiting)

        # set remote.wait_wait to False to trick alpha in the folloiwng
        # sync request to think alpha is NOT in wait request code so
        # that alpha does not detect the conflict.
        smart_event1.remote.wait_wait = False

        # Issue the sync request. If all goes well, beta will see the conflict
        # first, set the conflict flag and then raise the
        # ConflictDeadlockDetected error. We can't prove that it worked out
        # that way, but the coverage report will tell us whether the
        # detection code in wait ran.
        with pytest.raises(ConflictDeadlockDetected):
            smart_event1.sync(log_msg='mainline sync point 2')

        assert smart_event1.sync(log_msg='mainline sync point 3')

        assert smart_event1.wait(log_msg='mainline wait 4')

        assert smart_event1.sync(log_msg='mainline sync point 5')

        smart_event1.resume(log_msg='mainline resume 6')

        assert not smart_event1.sync(log_msg='mainline sync point 7',
                                     timeout=0.5)

        assert smart_event1.wait()

        assert smart_event1.sync(log_msg='mainline sync point 8')

        # thread will ensure we see conflict first
        with pytest.raises(ConflictDeadlockDetected):
            smart_event1.sync(log_msg='mainline sync point 10')

        logger.debug('mainline about to issue wait to clear trick pre-resume')
        smart_event1.wait()  # clear the trick pre-resume from beta

        assert smart_event1.sync(log_msg='mainline sync point 9')

        f1_thread.join()
        descs.thread_end('beta')

        with pytest.raises(RemoteThreadNotAlive):
            smart_event1.sync(log_msg='mainline sync point 10')

        descs.cleanup()

        logger.debug('mainline exiting 9')


###############################################################################
# TestWaitClear Class
###############################################################################
class TestWaitClear:
    """Test SmartEvent clearing of event set flag."""
    ###########################################################################
    # test_smart_event_f1_clear
    ###########################################################################
    def test_smart_event_f1_clear(self) -> None:
        """Test smart event timeout with f1 thread."""

        def f1():
            logger.debug('f1 entered')
            s_event = SmartEvent(name='beta')
            descs.add_desc(SmartEventDesc(name='beta',
                                          s_event=s_event,
                                          thread=threading.current_thread()))
            cmds.queue_cmd('alpha')

            s_event.pair_with(remote_name='alpha')
            descs.paired('alpha', 'beta')

            cmds.start_clock(iter=1)
            assert s_event.wait()
            assert 2 <= cmds.duration() <= 3
            assert not s_event.remote.event.is_set()

            cmds.start_clock(iter=2)
            assert s_event.wait()
            assert 2 <= cmds.duration() <= 3
            assert not s_event.remote.event.is_set()

            cmds.pause(2, iter=3)
            s_event.resume()
            cmds.pause(2, iter=4)
            s_event.resume()

        cmds = Cmds()
        descs = SmartEventDescs()
        smart_event = SmartEvent(name='alpha')
        descs.add_desc(SmartEventDesc(name='alpha',
                                      s_event=smart_event,
                                      thread=threading.current_thread()))

        beta_thread = threading.Thread(target=f1)
        beta_thread.start()

        cmds.get_cmd('alpha')
        smart_event.pair_with(remote_name='beta')

        cmds.pause(2, iter=1)
        smart_event.resume()

        cmds.pause(2, iter=2)
        smart_event.resume()

        cmds.start_clock(iter=3)
        assert smart_event.wait()
        assert 2 <= cmds.duration() <= 3
        assert not smart_event.remote.event.is_set()

        cmds.start_clock(iter=4)
        assert smart_event.wait()
        assert 2 <= cmds.duration() <= 3
        assert not smart_event.remote.event.is_set()

        beta_thread.join()
        descs.thread_end('beta')

    ###########################################################################
    # test_smart_event_thread_app_clear
    ###########################################################################
    def test_smart_event_thread_app_clear(self) -> None:
        """Test smart event timeout with thread_app thread."""

        class MyThread(threading.Thread):
            def __init__(self) -> None:
                super().__init__()
                self.s_event = SmartEvent(name='beta', thread=self)

            def run(self):
                logger.debug('ThreadApp run entered')

                # s_event = SmartEvent(name='beta')
                descs.add_desc(SmartEventDesc(name='beta',
                                              s_event=self.s_event,
                                              thread=self))
                cmds.queue_cmd('alpha')

                self.s_event.pair_with(remote_name='alpha')

                assert not self.s_event.remote.event.is_set()
                assert not self.s_event.event.is_set()

                self.s_event.sync(log_msg='beta run sync point 1')

                cmds.start_clock(iter=1)

                assert self.s_event.wait(log_msg='beta run wait 12')

                assert 2 <= cmds.duration() <= 3

                assert not self.s_event.remote.event.is_set()
                assert not self.s_event.event.is_set()

                self.s_event.sync(log_msg='beta run sync point 2')
                cmds.start_clock(iter=2)

                assert self.s_event.wait(log_msg='beta run wait 23')
                assert 2 <= cmds.duration() <= 3

                assert not self.s_event.remote.event.is_set()
                assert not self.s_event.event.is_set()
                self.s_event.sync(log_msg='beta run sync point 3')

                cmds.pause(2, iter=3)
                self.s_event.resume(log_msg='beta run resume 34')

                self.s_event.sync(log_msg='beta run sync point 4')

                cmds.pause(2, iter=4)
                self.s_event.resume(log_msg='beta run resume 45')

                self.s_event.sync(log_msg='beta run sync point 5')
                logger.debug('beta run exiting 910')

        cmds = Cmds()
        descs = SmartEventDescs()
        smart_event = SmartEvent(name='alpha')
        descs.add_desc(SmartEventDesc(name='alpha',
                                      s_event=smart_event,
                                      thread=threading.current_thread()))

        thread_app = MyThread()
        thread_app.start()

        cmds.get_cmd('alpha')
        smart_event.pair_with(remote_name='beta')
        descs.paired('alpha', 'beta')

        smart_event.sync(log_msg='mainline sync point 1')

        cmds.pause(2, iter=1)

        smart_event.resume(log_msg='mainline resume 12')

        smart_event.sync(log_msg='mainline sync point 2')

        cmds.pause(2, iter=2)

        smart_event.resume(log_msg='mainline resume 23')
        smart_event.sync(log_msg='mainline sync point 3')
        cmds.start_clock(iter=3)

        assert smart_event.wait(log_msg='mainline wait 34')

        assert 2 <= cmds.duration() <= 3

        assert not smart_event.event.is_set()
        assert not smart_event.remote.event.is_set()

        smart_event.sync(log_msg='mainline sync point 4')
        cmds.start_clock(iter=4)

        assert smart_event.wait(log_msg='mainline sync point 45')

        assert 2 <= cmds.duration() <= 3

        assert not smart_event.event.is_set()
        assert not smart_event.remote.event.is_set()
        smart_event.sync(log_msg='mainline sync point 5')

        thread_app.join()
        descs.thread_end('beta')


###############################################################################
# TestSmartEventTimeout Class
###############################################################################
class TestSmartEventTimeout:
    """Test SmartEvent timeout cases."""
    ###########################################################################
    # test_smart_event_f1_wait_time_out
    ###########################################################################
    def test_smart_event_f1_wait_time_out(self) -> None:
        """Test smart event wait timeout with f1 thread."""
        def f1():
            logger.debug('f1 entered')

            s_event = SmartEvent(name='beta')
            descs.add_desc(SmartEventDesc(name='beta',
                                          s_event=s_event,
                                          thread=threading.current_thread()))
            cmds.queue_cmd('alpha')

            s_event.pair_with(remote_name='alpha')
            descs.paired('alpha', 'beta')

            s_event.sync(log_msg='f1 beta sync point 1')
            assert s_event.wait(timeout=2)
            s_event.sync(log_msg='f1 beta sync point 2')
            s_time = time.time()
            assert not s_event.wait(timeout=0.5)
            assert 0.5 <= time.time() - s_time <= 0.75
            s_event.sync(log_msg='f1 beta sync point 3')
            s_event.pause_until(WUCond.RemoteWaiting)
            s_event.resume(log_msg='f1 beta resume 34')
            s_event.sync(log_msg='f1 beta sync point 4')
            s_event.sync(log_msg='f1 beta sync point 5')

        cmds = Cmds()
        descs = SmartEventDescs()
        smart_event = SmartEvent(name='alpha')
        descs.add_desc(SmartEventDesc(name='alpha',
                                      s_event=smart_event,
                                      thread=threading.current_thread()))

        beta_thread = threading.Thread(target=f1)

        beta_thread.start()

        cmds.get_cmd('alpha')
        smart_event.pair_with(remote_name='beta')

        smart_event.pause_until(WUCond.ThreadsReady)
        smart_event.sync(log_msg='mainline sync point 1')
        smart_event.pause_until(WUCond.RemoteWaiting)
        smart_event.resume(log_msg='mainline resume 12')
        smart_event.sync(log_msg='mainline sync point 2')
        smart_event.sync(log_msg='mainline sync point 3')
        assert smart_event.wait(timeout=2)
        smart_event.sync(log_msg='mainline sync point 4')
        start_time = time.time()
        assert not smart_event.wait(timeout=0.75)
        assert 0.75 <= time.time() - start_time <= 1
        smart_event.sync(log_msg='mainline sync point 5')

        beta_thread.join()
        descs.thread_end('beta')

    ###########################################################################
    # test_smart_event_f1_resume_time_out
    ###########################################################################
    def test_smart_event_f1_resume_time_out(self) -> None:
        """Test smart event wait timeout with f1 thread."""

        def f1() -> None:
            """The remote thread for requests."""
            logger.debug('f1 entered')

            s_event = SmartEvent(name='beta')
            descs.add_desc(SmartEventDesc(name='beta',
                                          s_event=s_event,
                                          thread=threading.current_thread()))
            cmds.queue_cmd('alpha')

            s_event.pair_with(remote_name='alpha')

            # s_event.sync(log_msg='f1 beta sync point 1')

            # the first resume will set the flag ON and the flag will stay ON
            # since there is no matching wait
            assert not s_event.event.is_set()
            assert s_event.resume(timeout=2)
            assert s_event.event.is_set()

            # this second resume will timeout waiting for the flag to go OFF
            cmds.start_clock(iter=1)
            assert not s_event.resume(timeout=0.5)
            assert 0.5 <= cmds.duration() <= 0.75
            assert s_event.event.is_set()

            s_event.sync(log_msg='f1 beta sync point 1')
            s_event.sync(log_msg='f1 beta sync point 2')

            # this first resume will complete within the timeout
            s_event.remote.wait_wait = True  # simulate waiting
            s_event.remote.deadlock = True  # simulate deadlock
            cmds.start_clock(iter=2)
            assert s_event.resume(timeout=1)
            assert 0.5 <= cmds.duration() <= 0.75

            # s_event.sync(log_msg='f1 beta sync point 3')
            s_event.sync(log_msg='f1 beta sync point 4')

            # this resume will timeout
            s_event.remote.wait_wait = True  # simulate waiting
            s_event.remote.deadlock = True  # simulate deadlock

            cmds.start_clock(iter=3)
            assert not s_event.resume(timeout=0.5)
            assert 0.5 <= cmds.duration() <= 0.75

            s_event.sync(log_msg='f1 beta sync point 5')
            s_event.sync(log_msg='f1 beta sync point 6')

            # this wait will clear the flag - use timeout to prevent f1 beta
            # sync from raising ConflictDeadlockDetected
            assert s_event.wait(log_msg='f1 beta wait 67',
                                timeout=1)

            s_event.sync(log_msg='f1 beta sync point 7')

            cmds.pause(0.5, iter=5)  # we purposely skipped 4
            # clear the deadlock within the resume timeout to allow mainline
            # resume to complete
            s_event.deadlock = False
            s_event.wait_wait = False

            s_event.sync(log_msg='f1 beta sync point 8')

            cmds.pause(0.75, iter=6)
            # clear the deadlock after resume timeout to cause ml to timeout
            s_event.deadlock = False
            s_event.wait_wait = False

            s_event.sync(log_msg='f1 beta sync point 9')

        cmds = Cmds()
        descs = SmartEventDescs()
        smart_event = SmartEvent(name='alpha')
        descs.add_desc(SmartEventDesc(name='alpha',
                                      s_event=smart_event,
                                      thread=threading.current_thread()))

        beta_thread = threading.Thread(target=f1)

        beta_thread.start()

        cmds.get_cmd('alpha')
        smart_event.pair_with(remote_name='beta')
        descs.paired('alpha', 'beta')

        smart_event.pause_until(WUCond.ThreadsReady)
        smart_event.sync(log_msg='mainline sync point 1')

        # this wait will clear the flag - use timeout to prevent sync
        # from raising ConflictDeadlockDetected
        assert smart_event.remote.event.is_set()
        assert smart_event.wait(log_msg='mainline wait 12',
                                timeout=1)

        assert not smart_event.wait_timeout_specified
        smart_event.sync(log_msg='mainline sync point 2')

        cmds.pause(0.5, iter=2)  # we purposely skipped iter=1

        # clear the deadlock within resume timeout to allow f1 resume to
        # complete
        smart_event.deadlock = False
        smart_event.wait_wait = False

        # smart_event.sync(log_msg='mainline sync point 3')
        smart_event.sync(log_msg='mainline sync point 4')

        cmds.pause(0.75, iter=3)

        # clear the deadlock after the resume timeout to cause f1 to timeout
        smart_event.deadlock = False
        smart_event.wait_wait = False

        smart_event.sync(log_msg='mainline sync point 5')

        # the first resume will set the flag ON and the flag will stay ON
        # since there is no matching wait
        assert smart_event.resume(timeout=2)

        # this second resume will timeout waiting for the flag to go OFF
        cmds.start_clock(iter=4)
        assert not smart_event.resume(timeout=0.3)
        assert 0.3 <= cmds.duration() <= 0.6

        smart_event.sync(log_msg='mainline sync point 6')
        smart_event.sync(log_msg='mainline sync point 7')

        # this first resume will complete within the timeout
        smart_event.remote.wait_wait = True  # simulate waiting
        smart_event.remote.deadlock = True  # simulate deadlock
        cmds.start_clock(iter=5)
        assert smart_event.resume(timeout=1)
        assert 0.5 <= cmds.duration() <= 0.75

        smart_event.sync(log_msg='mainline sync point 8')

        # this resume will timeout
        smart_event.remote.wait_wait = True  # simulate waiting
        smart_event.remote.deadlock = True  # simulate deadlock
        cmds.start_clock(iter=6)
        assert not smart_event.resume(timeout=0.5)
        assert 0.5 <= cmds.duration() <= 0.75

        smart_event.sync(log_msg='mainline sync point 9')

        beta_thread.join()
        descs.thread_end('beta')

    ###########################################################################
    # test_smart_event_thread_app_time_out
    ###########################################################################
    def test_smart_event_thread_app_time_out(self) -> None:
        """Test smart event timeout with thread_app thread."""
        class MyThread(threading.Thread):
            def __init__(self):
                super().__init__()
                self.s_event = SmartEvent(name='beta', thread=self)

            def run(self):
                logger.debug('ThreadApp run entered')

                descs.add_desc(SmartEventDesc(name='beta',
                                              s_event=self.s_event,
                                              thread=self))
                cmds.queue_cmd('alpha')

                self.s_event.pair_with(remote_name='alpha')
                descs.paired('alpha', 'beta')

                cmds.start_clock(iter=1)
                assert not self.s_event.wait(timeout=2)
                assert 2 <= cmds.duration() < 3

                assert self.s_event.sync(log_msg='beta sync point 1')
                assert self.s_event.sync(log_msg='beta sync point 2')

        cmds = Cmds()
        descs = SmartEventDescs()
        smart_event = SmartEvent(name='alpha')
        descs.add_desc(SmartEventDesc(name='alpha',
                                      s_event=smart_event,
                                      thread=threading.current_thread()))

        thread_app = MyThread()
        thread_app.start()

        cmds.get_cmd('alpha')
        smart_event.pair_with(remote_name='beta')

        assert smart_event.sync(log_msg='alpha sync point 1')

        cmds.start_clock(iter=2)
        assert not smart_event.wait(timeout=2)
        assert 2 <= cmds.duration() < 3

        assert smart_event.sync(log_msg='alpha sync point 2')

        thread_app.join()
        descs.thread_end('beta')


###############################################################################
# TestSmartEventCode Class
###############################################################################
class TestSmartEventCode:
    """Test SmartEvent resume codes."""
    ###########################################################################
    # test_smart_event_f1_event_code
    ###########################################################################
    def test_smart_event_f1_event_code(self) -> None:
        """Test smart event code with f1 thread."""
        def f1():
            logger.debug('f1 entered')

            s_event = SmartEvent(name='beta')
            descs.add_desc(SmartEventDesc(name='beta',
                                          s_event=s_event,
                                          thread=threading.current_thread()))
            cmds.queue_cmd('alpha')

            s_event.pair_with(remote_name='alpha')

            assert not s_event.remote.code
            assert not s_event.code
            assert not s_event.get_code()

            s_event.sync(log_msg='beta sync point 1')

            assert s_event.wait(timeout=2)
            assert not s_event.remote.code
            assert s_event.code == 42
            assert 42 == s_event.get_code()

            s_event.sync(log_msg='beta sync point 2')

            s_event.resume(code='forty-two')
            assert s_event.remote.code == 'forty-two'
            assert s_event.code == 42
            assert 42 == s_event.get_code()

            s_event.sync(log_msg='beta sync point 3')

            assert s_event.remote.code == 'forty-two'
            assert s_event.code == 42
            assert 42 == s_event.get_code()

            assert not s_event.wait(timeout=.5)

            assert s_event.remote.code == 'forty-two'
            assert s_event.code == 42
            assert 42 == s_event.get_code()

            s_event.sync(log_msg='beta sync point 4')
            s_event.sync(log_msg='beta sync point 5')

            assert s_event.remote.code == 'forty-two'
            assert s_event.code == 'twenty one'
            assert 'twenty one' == s_event.get_code()
            assert s_event.remote.event.is_set()

        cmds = Cmds()
        descs = SmartEventDescs()
        smart_event = SmartEvent(name='alpha')
        descs.add_desc(SmartEventDesc(name='alpha',
                                      s_event=smart_event,
                                      thread=threading.current_thread()))

        beta_thread = threading.Thread(target=f1)

        beta_thread.start()

        cmds.get_cmd('alpha')
        smart_event.pair_with(remote_name='beta')
        descs.paired('alpha', 'beta')

        smart_event.sync(log_msg='mainline sync point 1')

        assert not smart_event.get_code()
        assert not smart_event.code
        assert not smart_event.remote.code

        smart_event.resume(code=42)

        assert not smart_event.get_code()
        assert not smart_event.code
        assert smart_event.remote.code == 42

        smart_event.sync(log_msg='mainline sync point 2')

        assert smart_event.wait()

        assert smart_event.get_code() == 'forty-two'
        assert smart_event.code == 'forty-two'
        assert smart_event.remote.code == 42

        smart_event.sync(log_msg='mainline sync point 3')
        smart_event.sync(log_msg='mainline sync point 4')

        smart_event.resume(code='twenty one')

        smart_event.sync(log_msg='mainline sync point 5')

        beta_thread.join()
        smart_event.code = None
        smart_event.remote.code = None

        descs.thread_end('beta')

    ###########################################################################
    # test_smart_event_thread_app_event_code
    ###########################################################################
    def test_smart_event_thread_app_event_code(self) -> None:
        """Test smart event code with thread_app thread."""

        class MyThread(threading.Thread):
            def __init__(self):
                super().__init__()
                self.s_event = SmartEvent(name='beta', thread=self)

            def run(self):
                logger.debug('ThreadApp run entered')

                descs.add_desc(SmartEventDesc(name='beta',
                                              s_event=self.s_event,
                                              thread=self))
                cmds.queue_cmd('alpha')

                self.s_event.pair_with(remote_name='alpha')
                descs.paired('alpha', 'beta')

                assert self.s_event.get_code() is None
                assert not self.s_event.wait(timeout=2, log_msg='beta wait 1')

                self.s_event.sync(log_msg='beta sync point 2')
                self.s_event.sync(log_msg='beta sync point 3')

                assert self.s_event.remote.event.is_set()
                assert self.s_event.code == 42
                assert self.s_event.get_code() == 42

                self.s_event.resume(log_msg='beta resume 4',
                                    code='forty-two')

        cmds = Cmds()
        descs = SmartEventDescs()
        smart_event = SmartEvent(name='alpha')
        descs.add_desc(SmartEventDesc(name='alpha',
                                      s_event=smart_event,
                                      thread=threading.current_thread()))

        thread_app = MyThread()
        thread_app.start()

        cmds.get_cmd('alpha')
        smart_event.pair_with(remote_name='beta')

        smart_event.pause_until(WUCond.ThreadsReady)

        smart_event.sync(log_msg='mainline sync point 2')
        smart_event.resume(code=42)
        smart_event.sync(log_msg='mainline sync point 3')

        assert smart_event.wait(log_msg='mainline wait 4')
        assert smart_event.get_code() == 'forty-two'

        thread_app.join()

        smart_event.code = None
        smart_event.remote.code = None

        descs.thread_end('beta')

    ###########################################################################
    # test_smart_event_thread_event_app_event_code
    ###########################################################################
    def test_smart_event_thread_event_app_event_code(self) -> None:
        """Test smart event code with thread_event_app thread."""
        class MyThread(threading.Thread, SmartEvent):
            def __init__(self) -> None:
                threading.Thread.__init__(self)
                SmartEvent.__init__(self, name='beta', thread=self)

            def run(self):
                logger.debug('ThreadApp run entered')

                descs.add_desc(SmartEventDesc(name='beta',
                                              s_event=self,
                                              thread=self))
                cmds.queue_cmd('alpha')

                self.pair_with(remote_name='alpha')

                assert not self.remote.code
                assert not self.code
                assert not self.get_code()

                self.sync(log_msg='beta sync point 1')

                assert not self.wait(timeout=0.5)

                assert not self.remote.code
                assert not self.code
                assert not self.get_code()

                self.sync(log_msg='beta sync point 2')
                self.sync(log_msg='beta sync point 3')

                assert not self.remote.code
                assert self.code == 42
                assert self.get_code() == 42

                self.resume(code='forty-two')

                assert self.remote.code == 'forty-two'
                assert self.code == 42
                assert self.get_code() == 42

                self.sync(log_msg='beta sync point 4')
                self.sync(log_msg='beta sync point 5')

                assert self.remote.code == 'forty-two'
                assert self.code == 42
                assert self.get_code() == 42

                assert self.wait(timeout=0.5, log_msg='beta wait 56')

                assert self.remote.code == 'forty-two'
                assert self.code == 42
                assert self.get_code() == 42

                self.sync(log_msg='beta sync point 6')

        cmds = Cmds()
        descs = SmartEventDescs()
        thread_event_app = MyThread()
        thread_event_app.start()

        cmds.get_cmd('alpha')

        time.sleep(2)  # make beta loop in pair_with
        smart_event = SmartEvent(name='alpha')
        descs.add_desc(SmartEventDesc(name='alpha',
                                      s_event=smart_event,
                                      thread=threading.current_thread()))

        smart_event.pair_with(remote_name='beta')
        descs.paired('alpha', 'beta')

        assert not smart_event.code
        assert not smart_event.remote.code
        assert not smart_event.get_code()

        smart_event.sync(log_msg='mainline sync point 1')
        smart_event.sync(log_msg='mainline sync point 2')

        assert not smart_event.code
        assert not smart_event.remote.code
        assert not smart_event.get_code()

        smart_event.resume(code=42, log_msg='mainline resume for beta 56')

        assert not smart_event.code
        assert smart_event.remote.code == 42
        assert not smart_event.get_code()

        smart_event.sync(log_msg='mainline sync point 3')
        smart_event.sync(log_msg='mainline sync point 4')

        assert smart_event.code == 'forty-two'
        assert smart_event.remote.code == 42
        assert smart_event.get_code() == 'forty-two'

        assert smart_event.wait()

        assert smart_event.code == 'forty-two'
        assert smart_event.remote.code == 42
        assert smart_event.get_code() == 'forty-two'

        smart_event.sync(log_msg='mainline sync point 5')

        assert smart_event.code == 'forty-two'
        assert smart_event.remote.code == 42
        assert smart_event.get_code() == 'forty-two'

        smart_event.sync(log_msg='mainline sync point 6')

        thread_event_app.join()

        smart_event.code = None
        smart_event.remote.code = None

        descs.thread_end('beta')


###############################################################################
# TestSmartEventLogger Class
###############################################################################
class TestSmartEventLogger:
    """Test log messages."""
    ###########################################################################
    # test_smart_event_f1_event_logger
    ###########################################################################
    def test_smart_event_f1_event_logger(self,
                                         caplog,
                                         log_enabled_arg) -> None:
        """Test smart event logger with f1 thread.

        Args:
            caplog: fixture to capture log messages
            log_enabled_arg: fixture to indicate whether log is enabled

        """
        def f1():
            exp_log_msgs.add_msg('f1 entered')
            logger.debug('f1 entered')

            s_event = SmartEvent(name='beta')
            descs.add_desc(SmartEventDesc(name='beta',
                                          s_event=s_event,
                                          thread=threading.current_thread()))
            cmds.queue_cmd('alpha')

            exp_log_msgs.add_beta_pair_with_msg('beta pair_with alpha 1',
                                                ['beta', 'alpha'])
            s_event.pair_with(remote_name='alpha',
                              log_msg='beta pair_with alpha 1')

            descs.paired('alpha', 'beta')

            exp_log_msgs.add_beta_sync_msg('beta sync point 1')
            s_event.sync(log_msg='beta sync point 1')

            exp_log_msgs.add_beta_wait_msg('wait for mainline to post 12')
            assert s_event.wait(log_msg='wait for mainline to post 12')

            exp_log_msgs.add_beta_sync_msg('beta sync point 2')
            s_event.sync(log_msg='beta sync point 2')

            exp_log_msgs.add_beta_resume_msg('post mainline 23')
            s_event.resume(log_msg='post mainline 23')

            exp_log_msgs.add_beta_sync_msg('beta sync point 3')
            s_event.sync(log_msg='beta sync point 3')

            exp_log_msgs.add_beta_sync_msg('beta sync point 4')
            s_event.sync(log_msg='beta sync point 4')

        cmds = Cmds()
        descs = SmartEventDescs()
        if log_enabled_arg:
            logging.getLogger().setLevel(logging.DEBUG)
        else:
            logging.getLogger().setLevel(logging.INFO)

        alpha_call_seq = ('test_smart_event.py::TestSmartEventLogger.'
                          'test_smart_event_f1_event_logger')
        beta_call_seq = ('test_smart_event.py::f1')
        exp_log_msgs = ExpLogMsgs(alpha_call_seq, beta_call_seq)
        l_msg = 'mainline started'
        exp_log_msgs.add_msg(l_msg)
        logger.debug(l_msg)

        smart_event = SmartEvent(name='alpha')
        descs.add_desc(SmartEventDesc(name='alpha',
                                      s_event=smart_event,
                                      thread=threading.current_thread()))

        beta_thread = threading.Thread(target=f1)

        beta_thread.start()

        cmds.get_cmd('alpha')
        exp_log_msgs.add_alpha_pair_with_msg('alpha pair_with beta 1',
                                             ['alpha', 'beta'])
        smart_event.pair_with(remote_name='beta',
                              log_msg='alpha pair_with beta 1')

        exp_log_msgs.add_alpha_sync_msg('mainline sync point 1')
        smart_event.sync(log_msg='mainline sync point 1')
        smart_event.pause_until(WUCond.RemoteWaiting)

        exp_log_msgs.add_alpha_resume_msg('post beta 12')
        smart_event.resume(log_msg='post beta 12')

        exp_log_msgs.add_alpha_sync_msg('mainline sync point 2')
        smart_event.sync(log_msg='mainline sync point 2')

        exp_log_msgs.add_alpha_sync_msg('mainline sync point 3')
        smart_event.sync(log_msg='mainline sync point 3')

        exp_log_msgs.add_alpha_wait_msg('wait for pre-post 23')
        assert smart_event.wait(log_msg='wait for pre-post 23')

        exp_log_msgs.add_alpha_sync_msg('mainline sync point 4')
        smart_event.sync(log_msg='mainline sync point 4')

        beta_thread.join()
        descs.thread_end('beta')

        exp_log_msgs.add_msg('mainline all tests complete')
        logger.debug('mainline all tests complete')

        exp_log_msgs.verify_log_msgs(caplog=caplog,
                                     log_enabled_tf=log_enabled_arg)

        # restore root to debug
        logging.getLogger().setLevel(logging.DEBUG)

    ###########################################################################
    # test_smart_event_thread_app_event_logger
    ###########################################################################
    def test_smart_event_thread_app_event_logger(self,
                                                 caplog,
                                                 log_enabled_arg) -> None:
        """Test smart event logger with thread_app thread.

        Args:
            caplog: fixture to capture log messages
            log_enabled_arg: fixture to indicate whether log is enabled

        """
        class MyThread(threading.Thread):
            def __init__(self,
                         exp_log_msgs1: ExpLogMsgs):
                super().__init__()
                self.s_event = SmartEvent(name='beta', thread=self)
                self.exp_log_msgs = exp_log_msgs1

            def run(self):
                l_msg = 'ThreadApp run entered'
                self.exp_log_msgs.add_msg(l_msg)
                logger.debug(l_msg)

                descs.add_desc(SmartEventDesc(name='beta',
                                              s_event=self.s_event,
                                              thread=self))
                cmds.queue_cmd('alpha')

                self.exp_log_msgs.add_beta_pair_with_msg('beta pair alpha 2',
                                                         ['beta', 'alpha'])
                self.s_event.pair_with(remote_name='alpha',
                                       log_msg='beta pair alpha 2')

                self.exp_log_msgs.add_beta_sync_msg('beta sync point 1')
                self.s_event.sync(log_msg='beta sync point 1')

                self.exp_log_msgs.add_beta_wait_msg('wait 12')
                assert self.s_event.wait(log_msg='wait 12')

                self.exp_log_msgs.add_beta_sync_msg('beta sync point 2')
                self.s_event.sync(log_msg='beta sync point 2')

                self.s_event.pause_until(WUCond.RemoteWaiting)

                self.exp_log_msgs.add_beta_resume_msg('post mainline 34',
                                                      True, 'forty-two')
                self.s_event.resume(code='forty-two',
                                    log_msg='post mainline 34')

                self.exp_log_msgs.add_beta_sync_msg('beta sync point 3')
                self.s_event.sync(log_msg='beta sync point 3')

                self.exp_log_msgs.add_beta_sync_msg('beta sync point 4')
                self.s_event.sync(log_msg='beta sync point 4')

        cmds = Cmds()
        descs = SmartEventDescs()
        if log_enabled_arg:
            logging.getLogger().setLevel(logging.DEBUG)
        else:
            logging.getLogger().setLevel(logging.INFO)

        alpha_call_seq = ('test_smart_event.py::TestSmartEventLogger.'
                          'test_smart_event_thread_app_event_logger')

        beta_call_seq = 'test_smart_event.py::MyThread.run'
        exp_log_msgs = ExpLogMsgs(alpha_call_seq, beta_call_seq)
        l_msg = 'mainline starting'
        exp_log_msgs.add_msg(l_msg)
        logger.debug(l_msg)

        smart_event = SmartEvent(name='alpha')
        descs.add_desc(SmartEventDesc(name='alpha',
                                      s_event=smart_event,
                                      thread=threading.current_thread()))

        thread_app = MyThread(exp_log_msgs)
        thread_app.start()

        cmds.get_cmd('alpha')
        exp_log_msgs.add_alpha_pair_with_msg('alpha pair beta 2',
                                             ['alpha', 'beta'])
        smart_event.pair_with(remote_name='beta')
        descs.paired('alpha', 'beta')

        exp_log_msgs.add_alpha_sync_msg('mainline sync point 1')
        smart_event.sync(log_msg='mainline sync point 1')

        smart_event.pause_until(WUCond.RemoteWaiting)

        exp_log_msgs.add_alpha_resume_msg(
            f'post thread {smart_event.remote.name} 23', True, 42)
        smart_event.resume(log_msg=f'post thread {smart_event.remote.name} 23',
                           code=42)

        exp_log_msgs.add_alpha_sync_msg('mainline sync point 2')
        smart_event.sync(log_msg='mainline sync point 2')

        exp_log_msgs.add_alpha_wait_msg('wait for post from thread 34')
        assert smart_event.wait(log_msg='wait for post from thread 34')

        exp_log_msgs.add_alpha_sync_msg('mainline sync point 3')
        smart_event.sync(log_msg='mainline sync point 3')
        exp_log_msgs.add_alpha_sync_msg('mainline sync point 4')
        smart_event.sync(log_msg='mainline sync point 4')

        thread_app.join()

        smart_event.code = None
        smart_event.remote.code = None

        descs.thread_end('beta')

        l_msg = 'mainline all tests complete'
        exp_log_msgs.add_msg(l_msg)
        logger.debug('mainline all tests complete')

        exp_log_msgs.verify_log_msgs(caplog=caplog,
                                     log_enabled_tf=log_enabled_arg)

        # restore root to debug
        logging.getLogger().setLevel(logging.DEBUG)

    ###########################################################################
    # test_smart_event_thread_event_app_event_logger
    ###########################################################################
    def test_smart_event_thread_event_app_event_logger(self,
                                                       caplog,
                                                       log_enabled_arg
                                                       ) -> None:
        """Test smart event logger with thread_event_app thread.

        Args:
            caplog: fixture to capture log messages
            log_enabled_arg: fixture to indicate whether log is enabled

        """
        class MyThread(threading.Thread, SmartEvent):
            def __init__(self,
                         exp_log_msgs1: ExpLogMsgs):
                threading.Thread.__init__(self)
                SmartEvent.__init__(self, name='beta', thread=self)
                self.exp_log_msgs = exp_log_msgs1

            def run(self):
                self.exp_log_msgs.add_msg('ThreadApp run entered')
                logger.debug('ThreadApp run entered')

                descs.add_desc(SmartEventDesc(name='beta',
                                              s_event=self,
                                              thread=self))
                cmds.queue_cmd('alpha')

                self.exp_log_msgs.add_beta_pair_with_msg('beta to alpha 3',
                                                         ['beta', 'alpha'])
                self.pair_with(remote_name='alpha',
                               log_msg='beta to alpha 3')
                descs.paired('alpha', 'beta')

                self.exp_log_msgs.add_beta_sync_msg('beta sync point 1')
                self.sync(log_msg='beta sync point 1')

                self.exp_log_msgs.add_beta_wait_msg(
                    'wait for mainline to post 12')
                assert self.wait(log_msg='wait for mainline to post 12')

                self.exp_log_msgs.add_beta_sync_msg('beta sync point 2')
                self.sync(log_msg='beta sync point 2')

                self.pause_until(WUCond.RemoteWaiting)

                self.exp_log_msgs.add_beta_resume_msg('post mainline 23')
                self.resume(log_msg='post mainline 23')

                self.exp_log_msgs.add_beta_sync_msg('beta sync point 3')
                self.sync(log_msg='beta sync point 3')

        cmds = Cmds()
        descs = SmartEventDescs()
        if log_enabled_arg:
            logging.getLogger().setLevel(logging.DEBUG)
        else:
            logging.getLogger().setLevel(logging.INFO)

        alpha_call_seq = ('test_smart_event.py::TestSmartEventLogger.'
                          'test_smart_event_thread_event_app_event_logger')

        beta_call_seq = 'test_smart_event.py::MyThread.run'
        exp_log_msgs = ExpLogMsgs(alpha_call_seq, beta_call_seq)
        l_msg = 'mainline starting'
        exp_log_msgs.add_msg(l_msg)
        logger.debug(l_msg)

        smart_event = SmartEvent(name='alpha')
        descs.add_desc(SmartEventDesc(name='alpha',
                                      s_event=smart_event,
                                      thread=threading.current_thread()))

        thread_event_app = MyThread(exp_log_msgs1=exp_log_msgs)

        thread_event_app.start()

        cmds.get_cmd('alpha')

        exp_log_msgs.add_alpha_pair_with_msg('alpha to beta 3',
                                             ['alpha', 'beta'])
        smart_event.pair_with(remote_name='beta',
                              log_msg='alpha to beta 3')

        exp_log_msgs.add_alpha_sync_msg('mainline sync point 1')
        smart_event.sync(log_msg='mainline sync point 1')

        smart_event.pause_until(WUCond.RemoteWaiting)

        exp_log_msgs.add_alpha_resume_msg(
            f'post thread {thread_event_app.name} 12')
        smart_event.resume(log_msg=f'post thread '
                           f'{thread_event_app.name} 12')

        exp_log_msgs.add_alpha_sync_msg('mainline sync point 2')
        smart_event.sync(log_msg='mainline sync point 2')

        exp_log_msgs.add_alpha_wait_msg('wait for post from thread 23')
        assert smart_event.wait(log_msg='wait for post from thread 23')

        exp_log_msgs.add_alpha_sync_msg('mainline sync point 3')
        smart_event.sync(log_msg='mainline sync point 3')

        thread_event_app.join()
        descs.thread_end('beta')

        exp_log_msgs.add_msg('mainline all tests complete')
        logger.debug('mainline all tests complete')

        exp_log_msgs.verify_log_msgs(caplog=caplog,
                                     log_enabled_tf=log_enabled_arg)

        # restore root to debug
        logging.getLogger().setLevel(logging.DEBUG)


###############################################################################
# TestCombos Class
###############################################################################
class TestCombos:
    """Test various combinations of SmartEvent."""
    ###########################################################################
    # test_smart_event_thread_f1_combos
    ###########################################################################
    def test_smart_event_f1_combos(self,
                                   action_arg1: Any,
                                   code_arg1: Any,
                                   log_msg_arg1: Any,
                                   action_arg2: Any,
                                   caplog: Any,
                                   thread_exc: Any) -> None:
        """Test the SmartEvent with f1 combos.

        Args:
            action_arg1: first action
            code_arg1: whether to set and recv a code
            log_msg_arg1: whether to specify a log message
            action_arg2: second action
            caplog: fixture to capture log messages
            thread_exc: intercepts thread exceptions

        """
        alpha_call_seq = ('test_smart_event.py::TestCombos.action_loop')
        beta_call_seq = ('test_smart_event.py::thread_func1')
        exp_log_msgs = ExpLogMsgs(alpha_call_seq, beta_call_seq)
        l_msg = 'mainline entered'
        exp_log_msgs.add_msg(l_msg)
        logger.debug(l_msg)

        cmds = Cmds()
        descs = SmartEventDescs()

        cmds.l_msg = log_msg_arg1
        cmds.r_code = code_arg1

        f1_thread = threading.Thread(target=thread_func1,
                                     args=(cmds,
                                           descs,
                                           exp_log_msgs))

        l_msg = 'mainline about to start thread_func1'
        exp_log_msgs.add_msg(l_msg)
        logger.debug(l_msg)

        f1_thread.start()

        self.action_loop(action1=action_arg1,
                         action2=action_arg2,
                         cmds=cmds,
                         exp_log_msgs=exp_log_msgs,
                         thread_exc1=thread_exc)

        l_msg = 'main completed all actions'
        exp_log_msgs.add_msg(l_msg)
        logger.debug(l_msg)

        cmds.queue_cmd('beta', Cmd.Exit)

        f1_thread.join()
        descs.thread_end('beta')

        if log_msg_arg1:
            exp_log_msgs.verify_log_msgs(caplog=caplog, log_enabled_tf=True)

    ###########################################################################
    # test_smart_event_thread_f1_combos
    ###########################################################################
    def test_smart_event_f1_f2_combos(self,
                                      action_arg1: Any,
                                      code_arg1: Any,
                                      log_msg_arg1: Any,
                                      action_arg2: Any,
                                      caplog: Any,
                                      thread_exc: Any) -> None:
        """Test the SmartEvent with f1 anf f2 combos.

        Args:
            action_arg1: first action
            code_arg1: whether to set and recv a code
            log_msg_arg1: whether to specify a log message
            action_arg2: second action
            caplog: fixture to capture log messages
            thread_exc: intercepts thread exceptions

        """
        alpha_call_seq = ('test_smart_event.py::TestCombos.action_loop')
        beta_call_seq = ('test_smart_event.py::thread_func1')
        exp_log_msgs = ExpLogMsgs(alpha_call_seq, beta_call_seq)
        l_msg = 'mainline entered'
        exp_log_msgs.add_msg(l_msg)
        logger.debug(l_msg)

        cmds = Cmds()
        descs = SmartEventDescs()

        cmds.l_msg = log_msg_arg1
        cmds.r_code = code_arg1

        f1_thread = threading.Thread(target=thread_func1,
                                     args=(cmds,
                                           descs,
                                           exp_log_msgs))

        f2_thread = threading.Thread(target=self.action_loop,
                                     args=(action_arg1,
                                           action_arg2,
                                           cmds,
                                           exp_log_msgs,
                                           thread_exc))

        l_msg = 'mainline about to start thread_func1'
        exp_log_msgs.add_msg(l_msg)
        logger.debug(l_msg)

        f1_thread.start()
        f2_thread.start()

        l_msg = 'main completed all actions'
        exp_log_msgs.add_msg(l_msg)
        logger.debug(l_msg)

        f2_thread.join()
        descs.thread_end('alpha')
        cmds.queue_cmd('beta', Cmd.Exit)

        f1_thread.join()
        descs.thread_end('beta')

        if log_msg_arg1:
            exp_log_msgs.verify_log_msgs(caplog=caplog, log_enabled_tf=True)

    ###########################################################################
    # test_smart_event_thread_thread_app_combos
    ###########################################################################
    def test_smart_event_thread_app_combos(self,
                                           action_arg1: Any,
                                           code_arg1: Any,
                                           log_msg_arg1: Any,
                                           action_arg2: Any,
                                           caplog: Any,
                                           thread_exc: Any) -> None:
        """Test the SmartEvent with ThreadApp combos.

        Args:
            action_arg1: first action
            code_arg1: whether to set and recv a code
            log_msg_arg1: whether to specify a log message
            action_arg2: second action
            caplog: fixture to capture log messages
            thread_exc: intercepts thread exceptions

        """
        class SmartEventApp(threading.Thread):
            """SmartEventApp class with thread."""
            def __init__(self,
                         cmds: Cmds,
                         exp_log_msgs: ExpLogMsgs
                         ) -> None:
                """Initialize the object.

                Args:
                    cmds: commands for beta to do
                    exp_log_msgs: container for expected log messages

                """
                super().__init__()
                self.smart_event = SmartEvent(name='beta', thread=self)
                self.cmds = cmds
                self.exp_log_msgs = exp_log_msgs

            def run(self):
                """Thread to send and receive messages."""
                l_msg = 'SmartEventApp run started'
                self.exp_log_msgs.add_msg(l_msg)
                logger.debug(l_msg)
                thread_func1(
                    cmds=self.cmds,
                    descs=descs,
                    exp_log_msgs=self.exp_log_msgs,
                    s_event=self.smart_event)

                l_msg = 'SmartEventApp run exiting'
                self.exp_log_msgs.add_msg(l_msg)
                logger.debug(l_msg)

        alpha_call_seq = ('test_smart_event.py::TestCombos.action_loop')
        beta_call_seq = ('test_smart_event.py::thread_func1')
        exp_log_msgs = ExpLogMsgs(alpha_call_seq, beta_call_seq)
        l_msg = 'mainline entered'
        exp_log_msgs.add_msg(l_msg)
        logger.debug(l_msg)

        cmds = Cmds()
        descs = SmartEventDescs()

        cmds.l_msg = log_msg_arg1
        cmds.r_code = code_arg1

        f1_thread = SmartEventApp(cmds,
                                  exp_log_msgs)

        l_msg = 'mainline about to start SmartEventApp'
        exp_log_msgs.add_msg(l_msg)
        logger.debug(l_msg)

        f1_thread.start()

        self.action_loop(action1=action_arg1,
                         action2=action_arg2,
                         cmds=cmds,
                         descs=descs,
                         exp_log_msgs=exp_log_msgs,
                         thread_exc1=thread_exc)

        l_msg = 'main completed all actions'
        exp_log_msgs.add_msg(l_msg)
        logger.debug(l_msg)
        cmds.queue_cmd('beta', Cmd.Exit)

        f1_thread.join()
        descs.thread_end('beta')

        if log_msg_arg1:
            exp_log_msgs.verify_log_msgs(caplog=caplog, log_enabled_tf=True)

    ###########################################################################
    # test_smart_event_thread_thread_app_combos
    ###########################################################################
    def test_smart_event_thread_event_app_combos(self,
                                                 action_arg1: Any,
                                                 code_arg1: Any,
                                                 log_msg_arg1: Any,
                                                 action_arg2: Any,
                                                 caplog: Any,
                                                 thread_exc: Any) -> None:
        """Test the SmartEvent with ThreadApp combos.

        Args:
            action_arg1: first action
            code_arg1: whether to set and recv a code
            log_msg_arg1: whether to specify a log message
            action_arg2: second action
            caplog: fixture to capture log messages
            thread_exc: intercepts thread exceptions

        """
        class SmartEventApp(threading.Thread, SmartEvent):
            """SmartEventApp class with thread and event."""
            def __init__(self,
                         cmds: Cmds,
                         exp_log_msgs: ExpLogMsgs
                         ) -> None:
                """Initialize the object.

                Args:
                    cmds: commands for beta to do
                    exp_log_msgs: container for expected log messages

                """
                threading.Thread.__init__(self)
                SmartEvent.__init__(self,
                                    name='alpha',
                                    thread=self)

                self.cmds = cmds
                self.exp_log_msgs = exp_log_msgs

            def run(self):
                """Thread to send and receive messages."""
                l_msg = 'SmartEventApp run started'
                self.exp_log_msgs.add_msg(l_msg)
                logger.debug(l_msg)
                thread_func1(
                    cmds=self.cmds,
                    descs=descs,
                    exp_log_msgs=self.exp_log_msgs,
                    s_event=self)

                l_msg = 'SmartEventApp run exiting'
                self.exp_log_msgs.add_msg(l_msg)
                logger.debug(l_msg)

        alpha_call_seq = ('test_smart_event.py::TestCombos.action_loop')
        beta_call_seq = ('test_smart_event.py::thread_func1')
        exp_log_msgs = ExpLogMsgs(alpha_call_seq, beta_call_seq)
        l_msg = 'mainline entered'
        exp_log_msgs.add_msg(l_msg)
        logger.debug(l_msg)

        cmds = Cmds()
        descs = SmartEventDescs()

        cmds.l_msg = log_msg_arg1
        cmds.r_code = code_arg1

        f1_thread = SmartEventApp(cmds,
                                  exp_log_msgs)

        l_msg = 'mainline about to start SmartEventApp'
        exp_log_msgs.add_msg(l_msg)
        logger.debug(l_msg)
        f1_thread.start()

        self.action_loop(action1=action_arg1,
                         action2=action_arg2,
                         cmds=cmds,
                         descs=descs,
                         exp_log_msgs=exp_log_msgs,
                         thread_exc1=thread_exc)

        l_msg = 'main completed all actions'
        exp_log_msgs.add_msg(l_msg)
        logger.debug(l_msg)
        cmds.queue_cmd('beta', Cmd.Exit)

        f1_thread.join()
        descs.thread_end('beta')

        if log_msg_arg1:
            exp_log_msgs.verify_log_msgs(caplog=caplog, log_enabled_tf=True)

    ###########################################################################
    # action loop
    ###########################################################################
    def action_loop(self,
                    action1: Any,
                    action2: Any,
                    cmds: Cmds,
                    descs: SmartEventDescs,
                    exp_log_msgs: Any,
                    thread_exc1: Any
                    ) -> None:
        """Actions to perform with the thread.

        Args:
            action1: first smart event request to do
            action2: second smart event request to do
            cmds: contains cmd queues and other test args
            descs: tracking and verification for registry
            exp_log_msgs: container for expected log messages
            thread_exc1: contains any uncaptured errors from thread

        Raises:
            IncorrectActionSpecified: The Action is not recognized
            UnrecognizedCmd: beta send mainline an unrecognized command

        """
        smart_event = SmartEvent(name='alpha')
        descs.add_desc(SmartEventDesc(name='alpha',
                                      s_event=smart_event,
                                      thread=threading.current_thread()))
        cmds.get_cmd('alpha')
        smart_event.pair_with(remote_name='beta')

        actions = []
        actions.append(action1)
        actions.append(action2)
        for action in actions:

            if action == Action.MainWait:
                l_msg = 'main starting Action.MainWait'
                exp_log_msgs.add_msg(l_msg)
                logger.debug(l_msg)

                cmds.queue_cmd('beta', Cmd.Resume)
                assert smart_event.wait()
                if cmds.r_code:
                    assert smart_event.code == cmds.r_code
                    assert cmds.r_code == smart_event.get_code()

            elif action == Action.MainSync:
                l_msg = 'main starting Action.MainSync'
                exp_log_msgs.add_msg(l_msg)
                logger.debug(l_msg)

                cmds.queue_cmd('beta', Cmd.Sync)

                if cmds.l_msg:
                    exp_log_msgs.add_alpha_sync_msg(cmds.l_msg, True)
                    assert smart_event.sync(log_msg=cmds.l_msg)
                else:
                    assert smart_event.sync()

            elif action == Action.MainSync_TOT:
                l_msg = 'main starting Action.MainSync_TOT'
                exp_log_msgs.add_msg(l_msg)
                logger.debug(l_msg)

                cmds.queue_cmd('beta', Cmd.Sync)

                if cmds.l_msg:
                    exp_log_msgs.add_alpha_sync_msg(cmds.l_msg, True)
                    assert smart_event.sync(timeout=5,
                                            log_msg=cmds.l_msg)
                else:
                    assert smart_event.sync(timeout=5)

            elif action == Action.MainSync_TOF:
                l_msg = 'main starting Action.MainSync_TOF'
                exp_log_msgs.add_msg(l_msg)
                logger.debug(l_msg)
                l_msg = r'alpha timeout of a sync\(\) request.'
                exp_log_msgs.add_msg(l_msg)

                if cmds.l_msg:
                    exp_log_msgs.add_alpha_sync_msg(cmds.l_msg, False)
                    assert not smart_event.sync(timeout=0.3,
                                                log_msg=cmds.l_msg)
                else:
                    assert not smart_event.sync(timeout=0.3)

                # for this case, we did not tell beta to do anything, so
                # we need to tell ourselves to go to next action.
                # Note that we could use a continue, but we also want
                # to check for thread exception which is what we do
                # at the bottom
                cmds.queue_cmd('alpha', Cmd.Next_Action)

            elif action == Action.MainResume:
                l_msg = 'main starting Action.MainResume'
                exp_log_msgs.add_msg(l_msg)
                logger.debug(l_msg)
                if cmds.r_code:
                    assert smart_event.resume(code=cmds.r_code)
                    assert smart_event.remote.code == cmds.r_code
                else:
                    assert smart_event.resume()
                    assert not smart_event.remote.code

                assert smart_event.event.is_set()
                cmds.queue_cmd('beta', Cmd.Wait)

            elif action == Action.MainResume_TOT:
                l_msg = 'main starting Action.MainResume_TOT'
                exp_log_msgs.add_msg(l_msg)
                logger.debug(l_msg)
                if cmds.r_code:
                    assert smart_event.resume(code=cmds.r_code, timeout=0.5)
                    assert smart_event.remote.code == cmds.r_code
                else:
                    assert smart_event.resume(timeout=0.5)
                    assert not smart_event.remote.code

                assert smart_event.event.is_set()
                cmds.queue_cmd('beta', Cmd.Wait)

            elif action == Action.MainResume_TOF:
                l_msg = 'main starting Action.MainResume_TOF'
                exp_log_msgs.add_msg(l_msg)
                logger.debug(l_msg)
                l_msg = (f'{smart_event.name} timeout '
                         r'of a resume\(\) request with '
                         r'current.event.is_set\(\) = True and '
                         'remote.deadlock = False')
                exp_log_msgs.add_msg(l_msg)

                assert not smart_event.event.is_set()
                # pre-resume to set flag
                if cmds.r_code:
                    assert smart_event.resume(code=cmds.r_code)
                    assert smart_event.remote.code == cmds.r_code
                else:
                    assert smart_event.resume()
                    assert not smart_event.remote.code

                assert smart_event.event.is_set()

                if cmds.r_code:
                    start_time = time.time()
                    assert not smart_event.resume(code=cmds.r_code,
                                                  timeout=0.3)
                    assert 0.3 <= (time.time() - start_time) <= 0.5
                    assert smart_event.remote.code == cmds.r_code
                else:
                    start_time = time.time()
                    assert not smart_event.resume(timeout=0.5)
                    assert 0.5 <= (time.time() - start_time) <= 0.75
                    assert not smart_event.remote.code

                assert smart_event.event.is_set()

                # tell thread to clear wait
                cmds.queue_cmd('beta', Cmd.Wait_Clear)

            elif action == Action.ThreadWait:
                l_msg = 'main starting Action.ThreadWait'
                exp_log_msgs.add_msg(l_msg)
                logger.debug(l_msg)

                cmds.queue_cmd('beta', Cmd.Wait)
                smart_event.pause_until(WUCond.RemoteWaiting)
                if cmds.r_code:
                    smart_event.resume(code=cmds.r_code)
                    assert smart_event.remote.code == cmds.r_code
                else:
                    smart_event.resume()

            elif action == Action.ThreadWait_TOT:
                l_msg = 'main starting Action.ThreadWait_TOT'
                exp_log_msgs.add_msg(l_msg)
                logger.debug(l_msg)

                cmds.queue_cmd('beta', Cmd.Wait_TOT)
                smart_event.pause_until(WUCond.RemoteWaiting)
                # time.sleep(0.3)
                if cmds.r_code:
                    smart_event.resume(code=cmds.r_code)
                    assert smart_event.remote.code == cmds.r_code
                else:
                    smart_event.resume()

            elif action == Action.ThreadWait_TOF:
                l_msg = 'main starting Action.ThreadWait_TOF'
                exp_log_msgs.add_msg(l_msg)
                logger.debug(l_msg)

                cmds.queue_cmd('beta', Cmd.Wait_TOF)
                smart_event.pause_until(WUCond.RemoteWaiting)

            elif action == Action.ThreadResume:
                l_msg = 'main starting Action.ThreadResume'
                exp_log_msgs.add_msg(l_msg)
                logger.debug(l_msg)

                cmds.queue_cmd('beta', Cmd.Resume)
                smart_event.pause_until(WUCond.RemoteResume)
                assert smart_event.wait()
                if cmds.r_code:
                    assert smart_event.code == cmds.r_code
                    assert cmds.r_code == smart_event.get_code()
            else:
                raise IncorrectActionSpecified('The Action is not recognized')

            while True:
                thread_exc1.raise_exc_if_one()  # detect thread error
                alpha_cmd = cmds.get_cmd('alpha')
                if alpha_cmd == Cmd.Next_Action:
                    break
                else:
                    raise UnrecognizedCmd


###############################################################################
# thread_func1
###############################################################################
def thread_func1(cmds: Cmds,
                 descs: SmartEventDescs,
                 exp_log_msgs: Any,
                 s_event: Optional[SmartEvent] = None,
                 ) -> None:
    """Thread to test SmartEvent scenarios.

    Args:
        cmds: commands to do
        descs: used to verify registry and SmartEvent status
        exp_log_msgs: expected log messages
        s_event: instance of SmartEvent

    Raises:
        UnrecognizedCmd: Thread received an unrecognized command

    """
    l_msg = 'thread_func1 beta started'
    exp_log_msgs.add_msg(l_msg)
    logger.debug(l_msg)

    if s_event is None:
        s_event = SmartEvent(name='beta')

    descs.add_desc(SmartEventDesc(name='beta',
                                  s_event=s_event,
                                  thread=threading.current_thread()))
    cmds.queue_cmd('alpha')
    s_event.pair_with(remote_name='alpha')
    descs.paired('alpha', 'beta')

    while True:
        beta_cmd = cmds.get_cmd('beta')
        if beta_cmd == Cmd.Exit:
            break

        l_msg = f'thread_func1 received cmd: {beta_cmd}'
        exp_log_msgs.add_msg(l_msg)
        logger.debug(l_msg)

        if beta_cmd == Cmd.Wait:
            l_msg = 'thread_func1 doing Wait'
            exp_log_msgs.add_msg(l_msg)
            logger.debug(l_msg)
            if cmds.l_msg:
                exp_log_msgs.add_beta_wait_msg(cmds.l_msg, True)
                assert s_event.wait(log_msg=cmds.l_msg)
            else:
                assert s_event.wait()
            if cmds.r_code:
                assert s_event.code == cmds.r_code
                assert cmds.r_code == s_event.get_code()

            cmds.queue_cmd('alpha', Cmd.Next_Action)

        elif beta_cmd == Cmd.Wait_TOT:
            l_msg = 'thread_func1 doing Wait_TOT'
            exp_log_msgs.add_msg(l_msg)
            logger.debug(l_msg)
            if cmds.l_msg:
                exp_log_msgs.add_beta_wait_msg(cmds.l_msg, True)
                assert s_event.wait(log_msg=cmds.l_msg)
            else:
                assert s_event.wait()
            if cmds.r_code:
                assert s_event.code == cmds.r_code
                assert cmds.r_code == s_event.get_code()

            cmds.queue_cmd('alpha', Cmd.Next_Action)

        elif beta_cmd == Cmd.Wait_TOF:
            l_msg = 'thread_func1 doing Wait_TOF'
            exp_log_msgs.add_msg(l_msg)
            logger.debug(l_msg)
            l_msg = (f'{s_event.name} timeout of a '
                     r'wait\(\) request with '
                     'current.waiting = True and current.sync_wait = False')
            exp_log_msgs.add_msg(l_msg)

            start_time = time.time()
            if cmds.l_msg:
                exp_log_msgs.add_beta_wait_msg(cmds.l_msg, False)
                assert not s_event.wait(timeout=0.5,
                                        log_msg=cmds.l_msg)
            else:
                assert not s_event.wait(timeout=0.5)
            assert 0.5 < (time.time() - start_time) < 0.75

            cmds.queue_cmd('alpha', Cmd.Next_Action)

        elif beta_cmd == Cmd.Wait_Clear:
            l_msg = 'thread_func1 doing Wait_Clear'
            exp_log_msgs.add_msg(l_msg)
            logger.debug(l_msg)
            if cmds.l_msg:
                exp_log_msgs.add_beta_wait_msg(cmds.l_msg, True)
                assert s_event.wait(log_msg=cmds.l_msg)
            else:
                assert s_event.wait()

            if cmds.r_code:
                assert s_event.code == cmds.r_code
                assert cmds.r_code == s_event.get_code()

            cmds.queue_cmd('alpha', Cmd.Next_Action)

        elif beta_cmd == Cmd.Sync:
            l_msg = 'thread_func1 beta doing Sync'
            exp_log_msgs.add_msg(l_msg)
            logger.debug(l_msg)

            if cmds.l_msg:
                exp_log_msgs.add_beta_sync_msg(cmds.l_msg, True)
                assert s_event.sync(log_msg=cmds.l_msg)
            else:
                assert s_event.sync()

            cmds.queue_cmd('alpha', Cmd.Next_Action)

        elif beta_cmd == Cmd.Resume:
            l_msg = 'thread_func1 beta doing Resume'
            exp_log_msgs.add_msg(l_msg)
            logger.debug(l_msg)
            if cmds.r_code:
                if cmds.l_msg:
                    exp_log_msgs.add_beta_resume_msg(cmds.l_msg,
                                                     True,
                                                     cmds.r_code)
                    assert s_event.resume(code=cmds.r_code,
                                          log_msg=cmds.l_msg)
                else:
                    assert s_event.resume(code=cmds.r_code)
                assert s_event.remote.code == cmds.r_code
            else:
                if cmds.l_msg:
                    exp_log_msgs.add_beta_resume_msg(cmds.l_msg, True)
                    assert s_event.resume(log_msg=cmds.l_msg)
                else:
                    assert s_event.resume()

            cmds.queue_cmd('alpha', Cmd.Next_Action)
        else:
            raise UnrecognizedCmd('Thread received an unrecognized cmd')

    l_msg = 'thread_func1 beta exiting'
    exp_log_msgs.add_msg(l_msg)
    logger.debug(l_msg)


###############################################################################
# ExpLogMsg class
###############################################################################
class ExpLogMsgs:
    """Expected Log Messages Class."""

    def __init__(self,
                 alpha_call_seq: str,
                 beta_call_seq: str) -> None:
        """Initialize object.

        Args:
             alpha_call_seq: expected alpha call seq for log messages
             beta_call_seq: expected beta call seq for log messages

        """
        self.exp_alpha_call_seq = alpha_call_seq + ':[0-9]* '
        self.exp_beta_call_seq = beta_call_seq + ':[0-9]* '
        self.pair_with_req = r'pair_with\(\) '
        self.sync_req = r'sync\(\) '
        self.resume_req = r'resume\(\) '
        self.wait_req = r'wait\(\) '
        self.entered_str = 'entered '
        self.with_code = 'with code: '
        self.exit_str = 'exiting with ret_code '
        self.expected_messages = []

    def add_req_msg(self,
                    l_msg: str,
                    who: str,
                    req: str,
                    ret_code: Optional[bool] = None,
                    code: Optional[Any] = None,
                    pair: Optional[List[str]] = None
                    ) -> None:
        """Add an expected request message to the expected log messages.

        Args:
            l_msg: message to add
            who: either 'alpha or 'beta'
            req: one of 'pair_with', 'sync', 'resume', or 'wait'
            ret_code: bool
            code: code for resume or None

        """
        l_enter_msg = req + r'\(\) entered '
        if code is not None:
            l_enter_msg += f'with code: {code} '
        if pair is not None:
            l_enter_msg += f'by {pair[0]} to pair with {pair[1]}. '

        l_exit_msg = req + r'\(\) exiting with ret_code '
        if ret_code is not None:
            if ret_code:
                l_exit_msg += 'True '
            else:
                l_exit_msg += 'False '

        if pair is not None:
            l_exit_msg = (req + r'\(\)' + f' exiting - {pair[0]} now paired '
                                          f'with {pair[1]}. ')

        if who == 'alpha':
            l_enter_msg += self.exp_alpha_call_seq + l_msg
            l_exit_msg += self.exp_alpha_call_seq + l_msg
        else:
            l_enter_msg += self.exp_beta_call_seq + l_msg
            l_exit_msg += self.exp_beta_call_seq + l_msg

        self.expected_messages.append(re.compile(l_enter_msg))
        self.expected_messages.append(re.compile(l_exit_msg))

    def add_msg(self, l_msg: str) -> None:
        """Add a general message to the expected log messages.

        Args:
            l_msg: message to add
        """
        self.expected_messages.append(re.compile(l_msg))

    def add_alpha_pair_with_msg(self,
                                l_msg: str,
                                pair: List[str]) -> None:
        """Add alpha pair with message to expected log messages.

        Args:
            l_msg: log message to add
            pair: the paired by and paired to names

        """
        self.add_req_msg(l_msg=l_msg,
                         who='alpha',
                         req='pair_with',
                         pair=pair)

    def add_alpha_sync_msg(self,
                           l_msg: str,
                           ret_code: Optional[bool] = True) -> None:
        """Add alpha sync message to expected log messages.

        Args:
            l_msg: log message to add
            ret_code: True or False

        """
        self.add_req_msg(l_msg=l_msg,
                         who='alpha',
                         req='sync',
                         ret_code=ret_code)

    def add_alpha_resume_msg(self,
                             l_msg: str,
                             ret_code: Optional[bool] = True,
                             code: Optional[Any] = None) -> None:
        """Add alpha resume message to expected log messages.

        Args:
            l_msg: log message to add
            ret_code: True or False
            code: code to add to message

        """
        self.add_req_msg(l_msg=l_msg,
                         who='alpha',
                         req='resume',
                         ret_code=ret_code,
                         code=code)

    def add_alpha_wait_msg(self,
                           l_msg: str,
                           ret_code: Optional[bool] = True) -> None:
        """Add alpha wait message to expected log messages.

        Args:
            l_msg: log message to add
            ret_code: True or False

        """
        self.add_req_msg(l_msg=l_msg,
                         who='alpha',
                         req='wait',
                         ret_code=ret_code)

    def add_beta_pair_with_msg(self,
                               l_msg: str,
                               pair: List[str]) -> None:
        """Add beta pair with message to expected log messages.

        Args:
            l_msg: log message to add
            pair: the paired by and paired to names

        """
        self.add_req_msg(l_msg=l_msg,
                         who='beta',
                         req='pair_with',
                         pair=pair)

    def add_beta_sync_msg(self,
                          l_msg: str,
                          ret_code: Optional[bool] = True) -> None:
        """Add beta sync message to expected log messages.

        Args:
            l_msg: log message to add
            ret_code: True or False

        """
        self.add_req_msg(l_msg=l_msg,
                         who='beta',
                         req='sync',
                         ret_code=ret_code)

    def add_beta_resume_msg(self,
                            l_msg: str,
                            ret_code: Optional[bool] = True,
                            code: Optional[Any] = None) -> None:
        """Add beta resume message to expected log messages.

        Args:
            l_msg: log message to add
            ret_code: True or False
            code: code to add to message

        """
        self.add_req_msg(l_msg=l_msg,
                         who='beta',
                         req='resume',
                         ret_code=ret_code,
                         code=code)

    def add_beta_wait_msg(self,
                          l_msg: str,
                          ret_code: Optional[bool] = True) -> None:
        """Add beta wait message to expected log messages.

        Args:
            l_msg: log message to add
            ret_code: True or False

        """
        self.add_req_msg(l_msg=l_msg,
                         who='beta',
                         req='wait',
                         ret_code=ret_code)

    ###########################################################################
    # verify log messages
    ###########################################################################
    def verify_log_msgs(self,
                        caplog: Any,
                        log_enabled_tf: bool) -> None:
        """Verify that each log message issued is as expected.

        Args:
            caplog: pytest fixture that captures log messages
            log_enabled_tf: indicated whether log is enabled

        """
        num_log_records_found = 0
        log_records_found = []
        caplog_recs = []
        for record in caplog.records:
            caplog_recs.append(record.msg)

        for idx, record in enumerate(caplog.records):
            # print(record.msg)
            # print(self.exp_log_msgs)
            for idx2, l_msg in enumerate(self.expected_messages):
                if l_msg.match(record.msg):
                    # print(l_msg.match(record.msg))
                    self.expected_messages.pop(idx2)
                    caplog_recs.remove(record.msg)
                    log_records_found.append(record.msg)
                    num_log_records_found += 1
                    break

        print(f'\nnum_log_records_found: '
              f'{num_log_records_found} of {len(caplog.records)}')

        print(('*' * 8) + ' matched log records found ' + ('*' * 8))
        for log_msg in log_records_found:
            print(log_msg)

        print(('*' * 8) + ' remaining unmatched log records ' + ('*' * 8))
        for log_msg in caplog_recs:
            print(log_msg)

        print(('*' * 8) + ' remaining expected log records ' + ('*' * 8))
        for exp_lm in self.expected_messages:
            print(exp_lm)

        if log_enabled_tf:
            assert not self.expected_messages
            assert num_log_records_found == len(caplog.records)
        else:
            assert self.expected_messages
            assert num_log_records_found == 0
