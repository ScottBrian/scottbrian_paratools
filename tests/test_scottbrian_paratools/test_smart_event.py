"""test_smart_event.py module."""

from enum import Enum
from dataclasses import dataclass
import time
import pytest
from typing import Any, cast, List, Optional, Union
import threading
import queue
import re

from scottbrian_paratools.smart_event import (SmartEvent,
                                              WUCond,
                                              NeitherAlphaNorBetaSpecified,
                                              IncorrectThreadSpecified,
                                              DuplicateThreadSpecified,
                                              ThreadAlreadyRegistered,
                                              NotPaired,
                                              DetectedOpFromForeignThread,
                                              RemoteThreadNotAlive,
                                              WaitUntilTimeout,
                                              WaitDeadlockDetected,
                                              ConflictDeadlockDetected,
                                              InconsistentFlagSettings)

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
# verify_registry
###############################################################################
@dataclass
class SmartEventDesc:
    """Describes a SmartEvent with name and thread to verify."""
    smart_event: SmartEvent
    name: str
    thread: threading.Thread = None  # type: ignore
    paired_with: str = ''

def verify_registry(descs: List[SmartEventDesc]) -> None:
    """Verify that SmartEvent.registry is correct.

    Args:
        descs: one or more SmartEventDesc objects to verify

    """
    for desc in descs:
        assert (SmartEvent.registry[desc.name] is desc.smart_event)

        verify_smart_event_init(s_event_desc=desc)

        if desc.paired_with:
            assert (SmartEvent.registry[desc.paired_with]
                    is desc.smart_event.remote_smart_event)
        else:
            assert desc.smart_event.remote_smart_event is None


###############################################################################
# verify_smart_event_init
###############################################################################
def verify_smart_event_init(s_event_desc: SmartEventDesc) -> None:
    """Verify the SmartEvent object is initialized correctly.

    Args:
        s_event_desc: descriptor with SmartEvent object, name, and thread

    """
    assert isinstance(s_event_desc.thread, threading.Thread)
    assert isinstance(s_event_desc.smart_event.event, threading.Event)
    assert s_event_desc.smart_event.thread is s_event_desc.thread
    assert s_event_desc.smart_event.name == s_event_desc.name

    assert not s_event_desc.smart_event.wait_wait
    # assert not s_event_desc.smart_event.sync_wait
    assert not s_event_desc.smart_event.timeout_specified
    assert not s_event_desc.smart_event.deadlock
    assert not s_event_desc.smart_event.conflict
    assert not s_event_desc.smart_event.sync_cleanup
    assert s_event_desc.smart_event.code is None

    assert not s_event_desc.smart_event._sync_detected
    assert not s_event_desc.smart_event._deadlock_detected
    assert not s_event_desc.smart_event.sync_cleanup
    assert isinstance(s_event_desc.smart_event.debug_logging_enabled, bool)


###############################################################################
# outer_f1
###############################################################################
def outer_f1() -> None:
    """Outer function to test SmartEvent."""
    logger.debug('outer_f1 entered')
    s_event = SmartEvent(name='beta')
    desc = SmartEventDesc(smart_event=s_event,
                          name='beta',
                          thread=threading.current_thread(),
                          paired_with='')
    verify_registry([desc])

    s_event.pair_with(remote_name='alpha')
    desc.paired_with = 'alpha'
    verify_registry([desc])

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
    def __init__(self):
        """Initialize the object."""
        super().__init__()
        self.s_event = SmartEvent(name='beta')
        desc = SmartEventDesc(smart_event=self.s_event,
                              name='beta',
                              thread=self,
                              paired_with='')
        verify_registry([desc])

    def run(self):
        """Run the test."""
        print('beta run started')
        self.s_event.pair_with(remote_name='alpha')
        desc = SmartEventDesc(smart_event=self.s_event,
                              name='beta',
                              thread=threading.current_thread(),
                              paired_with='alpha')
        verify_registry([desc])

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
    def __init__(self):
        """Initialize the object."""
        threading.Thread.__init__(self)
        SmartEvent.__init__(self, name='beta')
        desc = SmartEventDesc(smart_event=self,
                              name='beta',
                              thread=self,
                              paired_with='')
        verify_registry([desc])

        # the following will fail with timeout because run has not yet
        # been started
        with pytest.raises(WaitUntilTimeout):
            self.pause_until(WUCond.ThreadsReady, timeout=0.005)

    def run(self):
        """Run the test."""
        print('beta run started')
        self.pair_with(remote_name='alpha')
        desc = SmartEventDesc(smart_event=self,
                              name='beta',
                              thread=threading.current_thread(),
                              paired_with='alpha')
        verify_registry([desc])

        assert self.sync(log_msg='outer beta sync point 1')
        assert self.wait(log_msg='outer f1 wait 12')
        assert self.sync(log_msg='outer beta sync point 2')
        assert self.resume(log_msg='outer f1 resume 23')
        assert self.sync(log_msg='outer beta sync point 3')

        logger.debug('beta run exiting')


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
        smart_event = SmartEvent(name='alpha')

        expected_repr_str = 'SmartEvent(name="alpha")'

        assert repr(smart_event) == expected_repr_str

        smart_event2 = SmartEvent(name="AlphaDog")

        expected_repr_str = 'SmartEvent(name="AlphaDog")'

        assert repr(smart_event2) == expected_repr_str

        def f1():
            s_event = SmartEvent(name='beta1')
            f1_expected_repr_str = 'SmartEvent(name="beta1")'
            assert repr(s_event) == f1_expected_repr_str

        def f2():
            s_event = SmartEvent(name='beta2')
            f1_expected_repr_str = 'SmartEvent(name="beta2")'
            assert repr(s_event) == f1_expected_repr_str

        a_thread1 = threading.Thread(target=f1)
        a_thread1.start()

        a_thread2 = threading.Thread(target=f2)
        a_thread2.start()

    ###########################################################################
    # test_smart_event_instantiate_with_errors
    ###########################################################################
    def test_smart_event_instantiate_with_errors(self) -> None:
        """Test register_thread alpha first."""
        alpha_t = threading.current_thread()
        smart_event = SmartEvent(name='alpha')

        assert len(SmartEvent.registry) == 1
        desc1 = SmartEventDesc(smart_event=smart_event,
                               name='alpha',
                               thread=threading.current_thread(),
                               paired_with='')
        verify_registry([desc1])

        # not OK to instantiate a new smart_event with same name
        with pytest.raises(NameAlreadyInUse):
            smart_event2 = SmartEvent(name='alpha')

        with pytest.raises(IncorrectNameSpecified):
            smart_event2 = SmartEvent(name=42)

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
        assert len(SmartEvent.registry) == 1

        verify_registry([desc1])

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

            assert len(SmartEvent.registry) == 2
            desca = SmartEventDesc(smart_event=smart_event,
                                   name='alpha',
                                   thread=alpha_t,
                                   paired_with='')
            descb = SmartEventDesc(smart_event=s_event,
                                   name=name,
                                   thread=threading.current_thread(),
                                   paired_with='')
            verify_registry([desca, descb])

            # not OK to pair with self
            with pytest.raises(PairWithSelfNotAllowed):
                s_event.pair_with(remote_name=name)

            s_event.pair_with(remote_name='alpha')

            assert len(SmartEvent.registry) == 2
            desca.paired_with = name
            descb.paired_with = 'alpha'
            verify_registry([desca, descb])

            # not OK to pair with remote a second time
            with pytest.raises(AlreadyPairedWithRemote):
                s_event.pair_with(remote_name='alpha')

            s_event.sync(log_msg=f'{name} f1 sync point 1')

            logger.debug(f'{name} f1 exiting')

        alpha_t = threading.current_thread()
        beta_t = threading.Thread(target=f1, arg=('beta',))

        smart_event = SmartEvent(name='alpha')

        assert len(SmartEvent.registry) == 1
        desc1 = SmartEventDesc(smart_event=smart_event,
                               name='alpha',
                               thread=threading.current_thread(),
                               paired_with='')
        verify_registry([desc1])

        beta_t.start()

        # not OK to pair with self
        with pytest.raises(PairWithSelfNotAllowed):
            smart_event.pair_with(remote_name='alpha')

        smart_event.pair_with(remote_name='beta')

        assert len(SmartEvent.registry) == 2
        desc1.paired_with = 'beta'
        desc2 = SmartEventDesc(smart_event=smart_event.remote_smart_event,
                               name='beta',
                               thread=beta_t,
                               paired_with='alpha')
        verify_registry([desc1, desc2])

        # not OK to pair with remote a second time
        with pytest.raises(AlreadyPairedWithRemote):
            smart_event.pair_with(remote_name='beta')

        smart_event.sync(log_msg='alpha sync point 1')

        beta_t.join()

        # at this point, f1 has ended. But, the registry will not have changed,
        # so everything will still show paired, even both alpha and beta
        # SmartEvents. Alpha SmartEvent will detect that beta is no longer
        # alive if a function is attempted.
        verify_registry([desc1, desc2])

        #######################################################################
        # second case - f1 with same name beta
        #######################################################################
        beta_t2 = threading.Thread(target=f1, arg=('beta',))
        beta_t2.start()

        smart_event.pair_with(remote_name='beta')

        desc2 = SmartEventDesc(smart_event=smart_event.remote_smart_event,
                               name='beta',
                               thread=beta_t2,
                               paired_with='alpha')

        assert len(SmartEvent.registry) == 2
        verify_registry([desc1, desc2])

        smart_event.sync(log_msg='alpha sync point 1 again')

        beta_t2.join()

        # at this point, f1 has ended. But, the registry will not have changed,
        # so everything will still show paired, even both alpha and beta
        # SmartEvents. Alpha SmartEvent will detect that beta is no longer
        # alive if a function is attempted.
        verify_registry([desc1, desc2])

        #######################################################################
        # third case, use different name for f1. Should clean up old beta
        # from the registry.
        #######################################################################
        beta_t3 = threading.Thread(target=f1, arg=('charlie',))
        beta_t3.start()

        smart_event.pair_with(remote_name='charlie')

        desc2 = SmartEventDesc(smart_event=smart_event.remote_smart_event,
                               name='charlie',
                               thread=beta_t3,
                               paired_with='alpha')

        assert len(SmartEvent.registry) == 2
        assert 'beta' not in SmartEvent.registry.keys()
        desc1.paired_with = 'charlie'
        verify_registry([desc1, desc2])

        smart_event.sync(log_msg='alpha sync point 1 again')

        beta_t3.join()

        # at this point, f1 has ended. But, the registry will not have changed,
        # so everything will still show paired, even both alpha and charlie
        # SmartEvents. Alpha SmartEvent will detect that charlie is no longer
        # alive if a function is attempted.
        verify_registry([desc1, desc2])

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

            assert len(SmartEvent.registry) == 2
            desca = SmartEventDesc(smart_event=smart_event,
                                   name='alpha',
                                   thread=alpha_t,
                                   paired_with='')
            descb = SmartEventDesc(smart_event=s_event,
                                   name=name,
                                   thread=threading.current_thread(),
                                   paied_with='')
            
            verify_registry([desca, descb])

            # not OK to pair with self
            with pytest.raises(PairWithSelfNotAllowed):
                s_event.pair_with(remote_name=name)

            s_event.pair_with(remote_name='alpha')

            assert len(SmartEvent.registry) == 2
            desca.paired_with = name
            descb.paired_with = 'alpha'
            verify_registry([desca, descb])

            # not OK to pair with remote a second time
            with pytest.raises(AlreadyPairedWithRemote):
                s_event.pair_with(remote_name='alpha')

            s_event.sync(log_msg=f'{name} f1 sync point 1')

            logger.debug(f'{name} f1 exiting')

        def f2(name: str) -> None:
            """Func to test instantiate SmartEvent.

            Args:
                name: name to use for s_event
            """
            logger.debug(f'{name} f2 entered')
            s_event = SmartEvent(name=name)

            assert len(SmartEvent.registry) == 4
            desca1 = SmartEventDesc(smart_event=smart_event,
                                    name='alpha',
                                    thread=alpha_t,
                                    paired_with='beta')
            desca2 = SmartEventDesc(smart_event=smart_event2,
                                    name='alpha2',
                                    thread=alpha_t,
                                    paired_with='')
            descb1 = SmartEventDesc(smart_event=smart_event.remote_smart_event,
                                    name='beta',
                                    thread=beta_t,
                                    paired_with='alpha')
            descb2 = SmartEventDesc(smart_event=s_event,
                                    name=name,
                                    thread=threading.current_thread(),
                                    paired_with = '')
            verify_registry([desca1, desca2, descb1, descb2])

            # not OK to pair with self
            with pytest.raises(PairWithSelfNotAllowed):
                s_event.pair_with(remote_name=name)
                
            with pytest.raises(RemoteAlreadyPairedWithOther):
                s_event.pair_with(remote_name='alpha')

            s_event.pair_with(remote_name='alpha2')

            assert len(SmartEvent.registry) == 4
            desca2.paired_with = name
            descb2.paired_with = 'alpha2'
            verify_registry([desca1, desca2, descb1, descb2])

            # not OK to pair with remote a second time
            with pytest.raises(AlreadyPairedWithRemote):
                smart_event.pair_with(remote_name='alpha2')

            s_event.sync(log_msg=f'{name} f1 sync point 1')

            logger.debug(f'{name} f2 exiting')

        alpha_t = threading.current_thread()
        beta_t = threading.Thread(target=f1, arg=('beta',))
        charlie_t = threading.Thread(target=f2, arg=('charlie',))

        smart_event = SmartEvent(name='alpha')

        assert len(SmartEvent.registry) == 1
        desc1 = SmartEventDesc(smart_event=smart_event,
                               name='alpha',
                               thread=threading.current_thread(),
                               paired_with='')
        verify_registry([desc1])

        beta_t.start()

        smart_event.pair_with(remote_name='beta')

        assert len(SmartEvent.registry) == 2
        desc1.paired_with='beta'
        desc2 = SmartEventDesc(smart_event=smart_event.remote_smart_event,
                               name='beta',
                               thread=beta_t,
                               paired_with='alpha')
        verify_registry([desc1, desc2])

        #######################################################################
        # pair with charlie
        #######################################################################

        smart_event2 = SmartEvent(name='alpha2')

        assert len(SmartEvent.registry) == 3
        desc3 = SmartEventDesc(smart_event=smart_event2,
                               name='alpha2',
                               thread=threading.current_thread(),
                               paired_with='')
        verify_registry([desc1, desc2, desc3])

        charlie_t.start()

        smart_event.pair_with(remote_name='charlie')

        assert len(SmartEvent.registry) == 4
        desc3.paired_with = 'charlie'
        desc4 = SmartEventDesc(smart_event=smart_event2.remote_smart_event,
                               name='charlie',
                               thread=charlie_t,
                               paired_with='alpha2')
        verify_registry([desc1, desc2, desc3, desc4])

        smart_event.sync(log_msg='alpha sync point 1')

        beta_t.join()

        smart_event2.sync(log_msg='alpha sync point 2')

        charlie_t.join()

        # at this point, f1 and f2 have ended. But, the registry will not have
        # changed, so everything will still show paired, even all
        # SmartEvents. Any SmartEvents requests will detect that
        # their pairs are no longer active.
        assert len(SmartEvent.registry) == 4
        verify_registry([desc1, desc2, desc3, desc4])

        # try to pair with old beta - should clean things up and wait
        with pytest.raises(PairWithTimedOut):
            smart_event.pair_with(remote_name='beta', timeout=1)

        desc1.paired_with = ''
        desc3.paired_with = ''
        assert len(SmartEvent.registry) == 2
        verify_registry([desc1, desc3])

        # try to pair with old charlie - should clean things up and wait
        with pytest.raises(PairWithTimedOut):
            smart_event2.pair_with(remote_name='charlie', timeout=1)

        assert len(SmartEvent.registry) == 2
        verify_registry([desc1, desc3])



    ###########################################################################
    # test_smart_event_register_threads_f1
    ###########################################################################
    def test_smart_event_register_threads_f1(self) -> None:
        """Test register_thread with f1."""
        #######################################################################
        # mainline and f1 - mainline sets beta
        #######################################################################
        logger.debug('start test 1')
        current_thread = threading.current_thread()
        logger.debug(f'mainline current thread is {current_thread}')

        def f1(s_event, ml_thread):
            print('f1 entered')
            my_c_thread = threading.current_thread()
            assert s_event.alpha.thread is ml_thread
            assert s_event.alpha.thread is alpha_t
            assert s_event.beta.thread is my_c_thread
            assert s_event.beta.thread is threading.current_thread()

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
            with pytest.raises(WaitUntilTimeout):
                s_event.pause_until(WUCond.ThreadsReady, timeout=0.002)
            with pytest.raises(NotPaired):
                s_event.pause_until(WUCond.RemoteWaiting, timeout=0.02)

            cmds.queue_cmd('alpha', Cmd.Exit)

            logger.debug('foreign1 about to pause_until ThreadsReady')
            s_event.pause_until(WUCond.ThreadsReady, timeout=10)

            with pytest.raises(DetectedOpFromForeignThread):
                s_event.pause_until(WUCond.RemoteWaiting, timeout=0.02)
            with pytest.raises(DetectedOpFromForeignThread):
                s_event.pause_until(WUCond.RemoteWaiting)
            with pytest.raises(DetectedOpFromForeignThread):
                s_event.wait()
            with pytest.raises(DetectedOpFromForeignThread):
                s_event.resume()
            with pytest.raises(DetectedOpFromForeignThread):
                s_event.sync()

            logger.debug('foreign1 exiting')

        cmds = Cmds()
        alpha_t = threading.current_thread()
        smart_event1 = SmartEvent(alpha=threading.current_thread())

        logger.debug(f'id(smart_event1.alpha.event) = '
                     f'{id(smart_event1.alpha.event)}')
        logger.debug(f'id(smart_event1.beta.event) = '
                     f'{id(smart_event1.beta.event)}')

        my_foreign1_thread = threading.Thread(target=foreign1,
                                              args=(smart_event1,))
        my_foreign1_thread.start()
        my_f1_thread = threading.Thread(target=f1,
                                        args=(smart_event1,
                                              threading.current_thread()))
        with pytest.raises(WaitUntilTimeout):
            smart_event1.pause_until(WUCond.ThreadsReady, timeout=0.002)
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

        _ = cmds.get_cmd('alpha')

        logger.debug('mainline about to register beta thread')
        smart_event1.register_thread(beta=my_f1_thread)
        logger.debug('mainline back from registering beta thread')

        with pytest.raises(WaitUntilTimeout):
            smart_event1.pause_until(WUCond.ThreadsReady, timeout=0.005)

        my_f1_thread.start()
        smart_event1.pause_until(WUCond.ThreadsReady, timeout=1)

        smart_event1.sync(log_msg='mainline sync point 1')

        logger.debug('about to pause_until RemoteWaiting')
        with pytest.raises(WaitUntilTimeout):
            smart_event1.pause_until(WUCond.RemoteWaiting, timeout=0.002)
        with pytest.raises(WaitUntilTimeout):
            smart_event1.pause_until(WUCond.RemoteWaiting, timeout=0.01)
        with pytest.raises(WaitUntilTimeout):
            smart_event1.pause_until(WUCond.RemoteWaiting, timeout=0.02)
        with pytest.raises(WaitUntilTimeout):
            smart_event1.pause_until(WUCond.RemoteWaiting, timeout=1)

        cmds.queue_cmd('beta', Cmd.Wait)

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

        with pytest.raises(RemoteThreadNotAlive):
            smart_event1.resume()

        with pytest.raises(RemoteThreadNotAlive):
            smart_event1.wait()

        with pytest.raises(RemoteThreadNotAlive):
            smart_event1.pause_until(WUCond.RemoteWaiting)

        with pytest.raises(RemoteThreadNotAlive):
            smart_event1.sync(log_msg='mainline sync point 3')

        assert smart_event1.alpha.thread is alpha_t
        assert smart_event1.beta.thread is my_f1_thread

        del smart_event1
        del my_f1_thread

    ###########################################################################
    # test_smart_event_outer_thread_f1
    ###########################################################################
    def test_smart_event_outer_thread_f1(self) -> None:
        """Test simple sequence with outer thread f1."""
        #######################################################################
        # mainline
        #######################################################################
        logger.debug('mainline starting')

        smart_event = SmartEvent(alpha=threading.current_thread())
        f1_thread = threading.Thread(target=outer_f1, args=(smart_event,))

        logger.debug('mainline about to register beta thread')
        smart_event.register_thread(beta=f1_thread)

        f1_thread.start()
        smart_event.pause_until(WUCond.ThreadsReady)

        smart_event.sync(log_msg='mainline sync point 1')

        smart_event.resume(log_msg='alpha resume 12')

        smart_event.sync(log_msg='mainline sync point 2')

        smart_event.wait(log_msg='alpha wait 23')

        smart_event.sync(log_msg='mainline sync point 3')

        f1_thread.join()

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

        smart_event = SmartEvent(alpha=threading.current_thread())
        thread_app = OuterThreadApp(smart_event)

        logger.debug('mainline about to register beta thread')
        smart_event.register_thread(beta=thread_app)

        thread_app.start()
        smart_event.pause_until(WUCond.ThreadsReady)

        smart_event.sync(log_msg='mainline sync point 1')

        smart_event.resume(log_msg='alpha resume 12')

        smart_event.sync(log_msg='mainline sync point 2')

        smart_event.wait(log_msg='alpha wait 23')

        smart_event.sync(log_msg='mainline sync point 3')

        thread_app.join()

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

        smart_event = SmartEvent()
        thread_event_app = OuterThreadEventApp()

        thread_event_app.start()

        smart_event.pause_until(WUCond.ThreadsReady)

        smart_event.sync(log_msg='mainline sync point 1')

        smart_event.resume(log_msg='alpha resume 12')

        smart_event.sync(log_msg='mainline sync point 2')

        smart_event.wait(log_msg='alpha wait 23')

        smart_event.sync(log_msg='mainline sync point 3')

        thread_event_app.join()

        logger.debug('mainline exiting')

    ###########################################################################
    # test_smart_event_register_threads_f1_part2
    ###########################################################################
    def test_smart_event_register_threads_f1_part2(self) -> None:
        """Test register_thread with f1 part2."""
        #######################################################################
        # mainline and f2 - f2 sets beta
        #######################################################################

        def f2(s_event, ml_thread):
            logger.debug('        f2 beta entered')
            my_c_thread = threading.current_thread()

            _ = cmds.get_cmd('beta')

            s_event.register_thread(beta=my_c_thread)
            assert s_event.alpha.thread is ml_thread
            assert s_event.alpha.thread is alpha_t
            assert s_event.beta.thread is my_c_thread
            assert s_event.beta.thread is threading.current_thread()

            s_event.sync(log_msg='f2 thread sync point 1')

            with pytest.raises(WaitDeadlockDetected):
                s_event.wait()

            s_event.sync(log_msg='f2 thread sync point 2')

            s_event.wait()  # clear the resume that comes after the deadlock

            s_event.sync(log_msg='f2 thread sync point 3')

            s_event.pause_until(WUCond.RemoteWaiting, timeout=2)
            with pytest.raises(WaitDeadlockDetected):
                s_event.wait()

            s_event.sync(log_msg='f2 thread sync point 4')

            s_event.resume()

        cmds = Cmds()
        alpha_t = threading.current_thread()
        smart_event2 = SmartEvent(alpha=threading.current_thread())

        with pytest.raises(WaitUntilTimeout):
            smart_event2.pause_until(WUCond.ThreadsReady, timeout=0.001)

        my_f2_thread = threading.Thread(target=f2, args=(smart_event2,
                                                         alpha_t))
        with pytest.raises(WaitUntilTimeout):
            smart_event2.pause_until(WUCond.ThreadsReady, timeout=0.01)

        with pytest.raises(NotPaired):
            smart_event2.pause_until(WUCond.RemoteWaiting, timeout=-0.002)
        with pytest.raises(NotPaired):
            smart_event2.pause_until(WUCond.RemoteWaiting, timeout=0)
        with pytest.raises(NotPaired):
            smart_event2.pause_until(WUCond.RemoteWaiting, timeout=0.002)
        with pytest.raises(NotPaired):
            smart_event2.pause_until(WUCond.RemoteWaiting, timeout=0.2)
        with pytest.raises(NotPaired):
            smart_event2.pause_until(WUCond.RemoteWaiting)

        my_f2_thread.start()

        with pytest.raises(WaitUntilTimeout):
            smart_event2.pause_until(WUCond.ThreadsReady, timeout=0.2)
        with pytest.raises(NotPaired):
            smart_event2.pause_until(WUCond.RemoteWaiting)

        cmds.queue_cmd('beta', Cmd.Exit)

        smart_event2.pause_until(WUCond.ThreadsReady)
        smart_event2.pause_until(WUCond.ThreadsReady, timeout=1)
        smart_event2.pause_until(WUCond.ThreadsReady, timeout=0)
        smart_event2.pause_until(WUCond.ThreadsReady, timeout=-1)
        smart_event2.pause_until(WUCond.ThreadsReady, timeout=-2)

        smart_event2.sync(log_msg='mainline sync point 1')

        with pytest.raises(WaitDeadlockDetected):
            smart_event2.wait()

        smart_event2.sync(log_msg='mainline sync point 2')

        smart_event2.resume()

        smart_event2.sync(log_msg='mainline sync point 3')

        with pytest.raises(WaitDeadlockDetected):
            smart_event2.wait()

        smart_event2.sync(log_msg='mainline sync point 4')

        assert smart_event2.wait()  # clear resume

        my_f2_thread.join()

        with pytest.raises(RemoteThreadNotAlive):
            smart_event2.resume()

        with pytest.raises(RemoteThreadNotAlive):
            smart_event2.wait()

        with pytest.raises(RemoteThreadNotAlive):
            smart_event2.sync(log_msg='mainline sync point 5')

        assert smart_event2.alpha.thread is alpha_t
        assert smart_event2.beta.thread is my_f2_thread

    ###########################################################################
    # test_smart_event_register_threads_thread_app
    ###########################################################################
    def test_smart_event_register_threads_thread_app(self) -> None:
        """Test register_thread with thread_app."""
        #######################################################################
        # mainline and ThreadApp - mainline sets beta
        #######################################################################
        class MyThread(threading.Thread):
            def __init__(self,
                         s_event: SmartEvent,
                         alpha_t1: threading.Thread):
                super().__init__()
                self.s_event = s_event
                self.alpha_t1 = alpha_t1

            def run(self):
                print('run started')
                assert self.s_event.alpha.thread is self.alpha_t1
                assert self.s_event.alpha.thread is alpha_t
                assert self.s_event.beta.thread is self
                my_run_thread = threading.current_thread()
                assert self.s_event.beta.thread is my_run_thread
                assert self.s_event.beta.thread is threading.current_thread()

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

        alpha_t = threading.current_thread()
        smart_event1 = SmartEvent(alpha=alpha_t)
        my_taa_thread = MyThread(smart_event1, alpha_t)
        smart_event1.register_thread(beta=my_taa_thread)
        my_taa_thread.start()

        smart_event1.pause_until(WUCond.ThreadsReady)

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

        with pytest.raises(RemoteThreadNotAlive):
            smart_event1.resume()

        with pytest.raises(RemoteThreadNotAlive):
            smart_event1.wait()

        with pytest.raises(RemoteThreadNotAlive):
            smart_event1.pause_until(WUCond.RemoteWaiting)

        with pytest.raises(RemoteThreadNotAlive):
            smart_event1.pause_until(WUCond.RemoteResume)

        assert smart_event1.alpha.thread is alpha_t
        assert smart_event1.beta.thread is my_taa_thread

        del smart_event1
        del my_taa_thread

        #######################################################################
        # mainline and ThreadApp - thread_app sets beta
        #######################################################################
        class MyThread2(threading.Thread):
            def __init__(self,
                         s_event: SmartEvent,
                         alpha_t1: threading.Thread):
                super().__init__()
                self.s_event = s_event
                self.s_event.register_thread(beta=self)
                self.alpha_t1 = alpha_t1

            def run(self):
                print('run started')
                assert self.s_event.alpha.thread is self.alpha_t1
                assert self.s_event.alpha.thread is alpha_t
                assert self.s_event.beta.thread is self
                my_run_thread = threading.current_thread()
                assert self.s_event.beta.thread is my_run_thread
                assert self.s_event.beta.thread is threading.current_thread()
                with pytest.raises(WaitDeadlockDetected):
                    self.s_event.wait()
                assert self.s_event.wait()
                self.s_event.pause_until(WUCond.ThreadsReady)
                self.s_event.pause_until(WUCond.RemoteWaiting)
                self.s_event.pause_until(WUCond.RemoteWaiting, timeout=2)

                self.s_event.resume()

        smart_event2 = SmartEvent()
        smart_event2.register_thread(alpha=alpha_t)
        my_tab_thread = MyThread2(smart_event2, alpha_t)
        my_tab_thread.start()

        smart_event2.pause_until(WUCond.ThreadsReady)
        smart_event2.pause_until(WUCond.RemoteWaiting)
        with pytest.raises(WaitDeadlockDetected):
            smart_event2.wait()
        smart_event2.resume()
        assert smart_event2.wait()

        my_tab_thread.join()

        with pytest.raises(RemoteThreadNotAlive):
            smart_event2.resume()

        with pytest.raises(RemoteThreadNotAlive):
            smart_event2.wait()

        with pytest.raises(RemoteThreadNotAlive):
            smart_event2.pause_until(WUCond.RemoteWaiting)

        with pytest.raises(RemoteThreadNotAlive):
            smart_event2.pause_until(WUCond.RemoteResume)

        assert smart_event2.alpha.thread is alpha_t
        assert smart_event2.beta.thread is my_tab_thread

    ###########################################################################
    # test_smart_event_register_threads_thread_event_app
    ###########################################################################
    def test_smart_event_register_threads_thread_event_app(self) -> None:
        """Test register_thread with thread_event_app."""
        #######################################################################
        # mainline and ThreadEventApp - mainline sets alpha and beta
        #######################################################################
        class MyThreadEvent1(threading.Thread, SmartEvent):
            def __init__(self,
                         alpha_t1: threading.Thread):
                threading.Thread.__init__(self)
                SmartEvent.__init__(self)
                self.alpha_t1 = alpha_t1
                with pytest.raises(WaitUntilTimeout):
                    self.pause_until(WUCond.ThreadsReady, timeout=0.1)

            def run(self):
                logger.debug('run started')
                self.pause_until(WUCond.ThreadsReady, timeout=0.1)
                assert self.alpha.thread is self.alpha_t1
                assert self.alpha.thread is alpha_t
                assert self.beta.thread is self
                my_run_thread = threading.current_thread()
                assert self.beta.thread is my_run_thread
                assert self.beta.thread is threading.current_thread()

                assert self.wait()
                self.pause_until(WUCond.RemoteWaiting, timeout=2)
                with pytest.raises(WaitDeadlockDetected):
                    self.wait()
                self.resume()
                logger.debug('run exiting')

        alpha_t = threading.current_thread()

        my_te1_thread = MyThreadEvent1(alpha_t)
        with pytest.raises(WaitUntilTimeout):
            my_te1_thread.pause_until(WUCond.ThreadsReady, timeout=0.005)

        my_te1_thread.register_thread(alpha=alpha_t)
        with pytest.raises(WaitUntilTimeout):
            my_te1_thread.pause_until(WUCond.ThreadsReady, timeout=0.005)

        my_te1_thread.register_thread(beta=my_te1_thread)
        with pytest.raises(WaitUntilTimeout):
            my_te1_thread.pause_until(WUCond.ThreadsReady, timeout=0.005)

        assert my_te1_thread.alpha.thread is alpha_t
        assert my_te1_thread.beta.thread is my_te1_thread

        my_te1_thread.start()
        my_te1_thread.pause_until(WUCond.ThreadsReady)
        my_te1_thread.resume()
        with pytest.raises(WaitDeadlockDetected):
            my_te1_thread.wait()

        assert my_te1_thread.wait()

        my_te1_thread.join()

        with pytest.raises(RemoteThreadNotAlive):
            my_te1_thread.resume()

        with pytest.raises(RemoteThreadNotAlive):
            my_te1_thread.wait()

        with pytest.raises(RemoteThreadNotAlive):
            my_te1_thread.pause_until(WUCond.RemoteWaiting)

        with pytest.raises(RemoteThreadNotAlive):
            my_te1_thread.pause_until(WUCond.RemoteResume)

        assert my_te1_thread.alpha.thread is alpha_t
        assert my_te1_thread.beta.thread is my_te1_thread

        del my_te1_thread

        #######################################################################
        # mainline and ThreadApp - mainline sets alpha thread_app sets beta
        #######################################################################
        class MyThreadEvent2(threading.Thread, SmartEvent):
            def __init__(self,
                         alpha_t1: threading.Thread):
                threading.Thread.__init__(self)
                SmartEvent.__init__(self, beta=self)
                self.alpha_t1 = alpha_t1
                with pytest.raises(WaitUntilTimeout):
                    self.pause_until(WUCond.ThreadsReady, timeout=0.005)

            def run(self):
                logger.debug('run started')
                self.pause_until(WUCond.ThreadsReady, timeout=0.005)
                assert self.alpha.thread is self.alpha_t1
                assert self.alpha.thread is alpha_t
                assert self.beta.thread is self
                my_run_thread = threading.current_thread()
                assert self.beta.thread is my_run_thread
                assert self.beta.thread is threading.current_thread()
                with pytest.raises(WaitDeadlockDetected):
                    self.wait()
                assert self.wait()
                self.resume()
                logger.debug('run exiting')

        my_te2_thread = MyThreadEvent2(alpha_t)
        with pytest.raises(WaitUntilTimeout):
            my_te2_thread.pause_until(WUCond.ThreadsReady, timeout=0.005)
        my_te2_thread.register_thread(alpha=alpha_t)
        with pytest.raises(WaitUntilTimeout):
            my_te2_thread.pause_until(WUCond.ThreadsReady, timeout=0.005)
        my_te2_thread.start()

        my_te2_thread.pause_until(WUCond.ThreadsReady)

        my_te2_thread.pause_until(WUCond.RemoteWaiting, timeout=2)
        with pytest.raises(WaitDeadlockDetected):
            my_te2_thread.wait()

        my_te2_thread.resume()
        assert my_te2_thread.wait()

        my_te2_thread.join()

        with pytest.raises(RemoteThreadNotAlive):
            my_te2_thread.resume()

        with pytest.raises(RemoteThreadNotAlive):
            my_te2_thread.wait()

        with pytest.raises(RemoteThreadNotAlive):
            my_te2_thread.pause_until(WUCond.RemoteWaiting, timeout=2)

        with pytest.raises(RemoteThreadNotAlive):
            my_te2_thread.pause_until(WUCond.RemoteResume, timeout=2)

        assert my_te2_thread.alpha.thread is alpha_t
        assert my_te2_thread.beta.thread is my_te2_thread

        del my_te2_thread

        #######################################################################
        # mainline and ThreadApp - thread_app sets alpha and beta
        #######################################################################
        class MyThreadEvent3(threading.Thread, SmartEvent):
            def __init__(self,
                         alpha_t1: threading.Thread):
                threading.Thread.__init__(self)
                SmartEvent.__init__(self, alpha=alpha_t)
                with pytest.raises(WaitUntilTimeout):
                    self.pause_until(WUCond.ThreadsReady, timeout=0.005)
                self.register_thread(beta=self)
                with pytest.raises(WaitUntilTimeout):
                    self.pause_until(WUCond.ThreadsReady, timeout=0.001)
                self.alpha_t1 = alpha_t1

            def run(self):
                logger.debug('run started')
                self.pause_until(WUCond.ThreadsReady, timeout=0.001)
                assert self.alpha.thread is self.alpha_t1
                assert self.alpha.thread is alpha_t
                assert self.beta.thread is self
                my_run_thread = threading.current_thread()
                assert self.beta.thread is my_run_thread
                assert self.beta.thread is threading.current_thread()

                self.pause_until(WUCond.RemoteResume, timeout=2)
                assert self.wait()
                self.pause_until(WUCond.RemoteWaiting, timeout=2)
                with pytest.raises(WaitDeadlockDetected):
                    self.wait()
                self.resume()
                logger.debug('run exiting')

        my_te3_thread = MyThreadEvent3(alpha_t)
        with pytest.raises(WaitUntilTimeout):
            my_te3_thread.pause_until(WUCond.ThreadsReady, timeout=0.005)
        my_te3_thread.start()

        my_te3_thread.pause_until(WUCond.ThreadsReady, timeout=2)
        my_te3_thread.resume()
        with pytest.raises(WaitDeadlockDetected):
            my_te3_thread.wait()
        assert my_te3_thread.wait()

        my_te3_thread.join()

        with pytest.raises(RemoteThreadNotAlive):
            my_te3_thread.resume()

        with pytest.raises(RemoteThreadNotAlive):
            my_te3_thread.wait(timeout=3)

        with pytest.raises(RemoteThreadNotAlive):
            my_te3_thread.pause_until(WUCond.RemoteWaiting)

        with pytest.raises(RemoteThreadNotAlive):
            my_te3_thread.pause_until(WUCond.RemoteResume)

        assert my_te3_thread.alpha.thread is alpha_t
        assert my_te3_thread.beta.thread is my_te3_thread

        del my_te3_thread

        #######################################################################
        # mainline and ThreadApp - thread_app sets alpha and beta alternative
        #######################################################################
        class MyThreadEvent4(threading.Thread, SmartEvent):
            def __init__(self,
                         alpha_t1: threading.Thread):
                threading.Thread.__init__(self)
                SmartEvent.__init__(self, alpha=alpha_t, beta=self)
                with pytest.raises(WaitUntilTimeout):
                    self.pause_until(WUCond.ThreadsReady, timeout=0.001)
                self.alpha_t1 = alpha_t1

            def run(self):
                logger.debug('run started')
                self.pause_until(WUCond.ThreadsReady, timeout=0.001)
                assert self.alpha.thread is self.alpha_t1
                assert self.alpha.thread is alpha_t
                assert self.beta.thread is self
                my_run_thread = threading.current_thread()
                assert self.beta.thread is my_run_thread
                assert self.beta.thread is threading.current_thread()
                with pytest.raises(WaitDeadlockDetected):
                    self.wait()
                assert self.wait()
                self.resume()
                logger.debug('run exiting')

        my_te4_thread = MyThreadEvent4(alpha_t)
        my_te4_thread.start()

        my_te4_thread.pause_until(WUCond.RemoteWaiting)
        with pytest.raises(WaitDeadlockDetected):
            my_te4_thread.wait()

        my_te4_thread.resume()
        assert my_te4_thread.wait()

        my_te4_thread.join()

        with pytest.raises(RemoteThreadNotAlive):
            my_te4_thread.resume()

        with pytest.raises(RemoteThreadNotAlive):
            my_te4_thread.wait()

        with pytest.raises(RemoteThreadNotAlive):
            my_te4_thread.pause_until(WUCond.RemoteWaiting)

        with pytest.raises(RemoteThreadNotAlive):
            my_te4_thread.pause_until(WUCond.RemoteResume)

        assert my_te4_thread.alpha.thread is alpha_t
        assert my_te4_thread.beta.thread is my_te4_thread

    ###########################################################################
    # test_smart_event_register_threads_two_f_threads
    ###########################################################################
    def test_smart_event_register_threads_two_f_threads(self) -> None:
        """Test register_thread with thread_event_app."""
        #######################################################################
        # two threads - mainline sets alpha and beta
        #######################################################################
        def fa1():
            logger.debug('fa1 entered')
            s_event = SmartEvent()
            my_fa_thread = threading.current_thread()
            assert s_event.thread is my_fa_thread
            assert SmartEvent.threads['alpha'] is my_fa_thread
            s_event.pause_until(WUCond.ThreadsReady)
            logger.debug('fa1 about to wait')
            s_event.wait()
            logger.debug('fa1 back from wait')
            s_event.resume()

        def fb1(s_event):
            logger.debug('fb1 entered')
            s_event = SmartEvent()
            my_fb_thread = threading.current_thread()
            assert s_event.thread is my_fb_thread
            assert SmartEvent.threads['alpha'] is my_fb_thread

            logger.debug('fb1 about to resume')
            s_event.resume()
            s_event.wait()

            _ = cmds.get_cmd('beta')

            with pytest.raises(RemoteThreadNotAlive):
                s_event.resume()

            with pytest.raises(RemoteThreadNotAlive):
                s_event.wait()

            with pytest.raises(RemoteThreadNotAlive):
                s_event.pause_until(WUCond.RemoteWaiting)

            with pytest.raises(WaitUntilTimeout):
                s_event.pause_until(WUCond.ThreadsReady, timeout=0.1)

        cmds = Cmds()

        fa1_thread = threading.Thread(target=fa1)

        fb1_thread = threading.Thread(target=fb1)

        logger.debug('starting fa1_thread')
        fa1_thread.start()
        logger.debug('starting fb1_thread')
        fb1_thread.start()

        fa1_thread.join()

        cmds.queue_cmd('beta', 'go')

        fb1_thread.join()

        del fa1_thread
        del fb1_thread

        #######################################################################
        # two threads - fa2 and fb2 set their own threads
        #######################################################################
        def fa2(s_event):
            logger.debug('fa2 entered')
            s_event = SmartEvent()
            my_fa_thread = threading.current_thread()

            assert s_event.thread is my_fa_thread
            assert SmartEvent.threads['alpha'] is my_fa_thread

            s_event.pause_until(WUCond.ThreadsReady)
            logger.debug('fa2 about to deadlock')
            with pytest.raises(WaitDeadlockDetected):
                logger.debug('fa2 about to wait')
                s_event.wait()
                logger.debug('fa2 back from wait')

            logger.debug('fa2 about to pause_until')
            s_event.pause_until(WUCond.ThreadsReady, timeout=2)
            logger.debug('fa2 about to resume')
            s_event.resume()

            s_event.wait()
            logger.debug('fa2 exiting')

        def fb2():
            logger.debug('fb2 entered')
            s_event = SmartEvent()
            my_fb_thread = threading.current_thread()

            assert s_event.thread is my_fb_thread
            assert SmartEvent.threads['beta'] is my_fb_thread

            s_event.pause_until(WUCond.ThreadsReady)
            logger.debug('fb2 about to deadlock')
            with pytest.raises(WaitDeadlockDetected):
                logger.debug('fb2 about to wait')
                s_event.wait()
                logger.debug('fb2 back from wait')

            logger.debug('fb2 about to pause_until')
            s_event.pause_until(WUCond.ThreadsReady, timeout=2)
            logger.debug('fb2 about to wait')
            s_event.wait()
            s_event.resume()

            _ = cmds.get_cmd('beta')

            logger.debug('fb2 about to try resume for RemoteThreadNotAlive')
            with pytest.raises(RemoteThreadNotAlive):
                s_event.resume()

            logger.debug('fb2 about to try wait for RemoteThreadNotAlive')
            s_event.alpha.clear()  # undo the last resume by fa1
            with pytest.raises(RemoteThreadNotAlive):
                s_event.wait()

            logger.debug('fb2 exiting')

        fa2_thread = threading.Thread(target=fa2)

        fb2_thread = threading.Thread(target=fb2)

        fa2_thread.start()
        fb2_thread.start()

        fa2_thread.join()

        cmds.queue_cmd('beta', 'go')

        fb2_thread.join()


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

        def f1(s_event):
            logger.debug('f1 beta entered')

            s_event.sync(log_msg='f1 beta sync point 1')

            cmds.queue_cmd('alpha', 'go')
            _ = cmds.get_cmd('beta')

            s_event.sync(log_msg='f1 beta sync point 2')

            s_event.resume(log_msg='f1 beta resume 3')

            s_event.sync(log_msg='f1 beta sync point 4')

            logger.debug('f1 beta exiting 5')

        logger.debug('mainline entered')
        cmds = Cmds()
        smart_event1 = SmartEvent(alpha=threading.current_thread())
        f1_thread = threading.Thread(target=f1, args=(smart_event1,))
        smart_event1.register_thread(beta=f1_thread)
        f1_thread.start()

        assert smart_event1.sync(log_msg='mainline sync point 1')

        _ = cmds.get_cmd('alpha')

        smart_event1.beta.deadlock = True
        smart_event1.beta.conflict = True
        with pytest.raises(InconsistentFlagSettings):
            smart_event1.resume(log_msg='alpha error resume 1a')
        smart_event1.beta.deadlock = False
        smart_event1.beta.conflict = False

        smart_event1.beta.waiting = True
        smart_event1.beta.sync_wait = True
        with pytest.raises(InconsistentFlagSettings):
            smart_event1.resume(log_msg='alpha error resume 1b')
        smart_event1.beta.waiting = False
        smart_event1.beta.sync_wait = False

        smart_event1.beta.deadlock = True
        with pytest.raises(InconsistentFlagSettings):
            smart_event1.resume(log_msg='alpha error resume 1c')
        smart_event1.beta.deadlock = False

        smart_event1.beta.conflict = True
        with pytest.raises(InconsistentFlagSettings):
            smart_event1.resume(log_msg='alpha error resume 1d')
        smart_event1.beta.conflict = False

        cmds.queue_cmd('beta', 'go')

        smart_event1.sync(log_msg='mainline sync point 2')

        smart_event1.wait(log_msg='mainline wait 3')

        smart_event1.sync(log_msg='mainline sync point 4')

        f1_thread.join()

        with pytest.raises(RemoteThreadNotAlive):
            smart_event1.resume(log_msg='mainline sync point 5')

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

        def f1(s_event):
            logger.debug('f1 beta entered')

            # assert False

            s_event.sync(log_msg='f1 beta sync point 1')

            s_event.wait()

            s_event.sync(log_msg='f1 beta sync point 2')

            s_event.resume()

            s_event.sync(log_msg='f1 beta sync point 3')

            s_event.sync(log_msg='f1 beta sync point 4')

            s_event.wait()

            logger.debug('f1 beta exiting')

        logger.debug('mainline entered')
        smart_event1 = SmartEvent(alpha=threading.current_thread())
        f1_thread = threading.Thread(target=f1, args=(smart_event1,))
        smart_event1.register_thread(beta=f1_thread)
        f1_thread.start()

        smart_event1.sync(log_msg='mainline sync point 1')

        smart_event1.resume()

        smart_event1.sync(log_msg='mainline sync point 2')

        smart_event1.wait()

        smart_event1.sync(log_msg='mainline sync point 3')

        smart_event1.resume()

        smart_event1.sync(log_msg='mainline sync point 4')

        f1_thread.join()

        # thread_exc.raise_exc()

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

        def f1(s_event):
            logger.debug('f1 beta entered')

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

            while not s_event.alpha.sync_wait:
                time.sleep(.1)

            # trick alpha into seeing conflict first by making beta
            # think alpha is waiting instead of sync_wait
            with s_event._wait_check_lock:
                s_event.alpha.sync_wait = False
                s_event.sync_cleanup = True
            # pre-resume to get beta thinking alpha is resumed and waiting
            # and will eventually leave (i.e., not a deadlock)
            s_event.resume()
            s_event.alpha.waiting = True

            with pytest.raises(ConflictDeadlockDetected):
                s_event.wait(log_msg='f1 beta wait 89')

            s_event.sync_cleanup = False

            assert s_event.sync(log_msg='f1 beta sync point 9')

            logger.debug('f1 beta exiting 10')

        logger.debug('mainline entered')
        smart_event1 = SmartEvent(alpha=threading.current_thread())
        f1_thread = threading.Thread(target=f1, args=(smart_event1,))
        smart_event1.register_thread(beta=f1_thread)
        f1_thread.start()

        assert smart_event1.sync(log_msg='mainline sync point 1')

        smart_event1.pause_until(WUCond.RemoteWaiting)

        # set remote.waiting to False to trick the following sync to not
        # see tha the remote is waiting so that the sync does not detect
        # the confict first. This will allow the remote to see the
        # conflict first and set the conflict bits so we can see that
        # section of code as executed in the coverage report.

        smart_event1.beta.waiting = False

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

        with pytest.raises(RemoteThreadNotAlive):
            smart_event1.sync(log_msg='mainline sync point 10')

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

        def f1(s_event):
            logger.debug('f1 entered')

            cmds.start_clock(iter=1)
            assert s_event.wait()
            assert 2 <= cmds.duration() <= 3
            assert not s_event.alpha.event.is_set()

            cmds.start_clock(iter=2)
            assert s_event.wait()
            assert 2 <= cmds.duration() <= 3
            assert not s_event.alpha.event.is_set()

            cmds.pause(2, iter=3)
            s_event.resume()
            cmds.pause(2, iter=4)
            s_event.resume()

        cmds = Cmds()
        smart_event = SmartEvent(alpha=threading.current_thread())
        beta_thread = threading.Thread(target=f1, args=(smart_event,))
        smart_event.register_thread(beta=beta_thread)
        beta_thread.start()

        cmds.pause(2, iter=1)
        smart_event.resume()

        cmds.pause(2, iter=2)
        smart_event.resume()

        cmds.start_clock(iter=3)
        assert smart_event.wait()
        assert 2 <= cmds.duration() <= 3
        assert not smart_event.beta.event.is_set()

        cmds.start_clock(iter=4)
        assert smart_event.wait()
        assert 2 <= cmds.duration() <= 3
        assert not smart_event.beta.event.is_set()

        beta_thread.join()

    ###########################################################################
    # test_smart_event_thread_app_clear
    ###########################################################################
    def test_smart_event_thread_app_clear(self) -> None:
        """Test smart event timeout with thread_app thread."""

        class MyThread(threading.Thread):
            def __init__(self,
                         s_event: SmartEvent) -> None:
                super().__init__()
                self.s_event = s_event
                self.s_event.register_thread(beta=self)

            def run(self):
                logger.debug('ThreadApp run entered')

                assert not self.s_event.alpha.event.is_set()
                assert not self.s_event.beta.event.is_set()

                self.s_event.sync(log_msg='beta run sync point 1')

                cmds.start_clock(iter=1)

                assert self.s_event.wait(log_msg='beta run wait 12')

                assert 2 <= cmds.duration() <= 3

                assert not self.s_event.alpha.event.is_set()
                assert not self.s_event.beta.event.is_set()

                self.s_event.sync(log_msg='beta run sync point 2')
                cmds.start_clock(iter=2)

                assert self.s_event.wait(log_msg='beta run wait 23')
                assert 2 <= cmds.duration() <= 3

                assert not self.s_event.alpha.event.is_set()
                assert not self.s_event.beta.event.is_set()
                self.s_event.sync(log_msg='beta run sync point 3')

                cmds.pause(2, iter=3)
                self.s_event.resume(log_msg='beta run resume 34')

                self.s_event.sync(log_msg='beta run sync point 4')

                cmds.pause(2, iter=4)
                self.s_event.resume(log_msg='beta run resume 45')

                self.s_event.sync(log_msg='beta run sync point 5')
                logger.debug('beta run exiting 910')

        cmds = Cmds()
        smart_event = SmartEvent(alpha=threading.current_thread())
        thread_app = MyThread(smart_event)
        thread_app.start()

        smart_event.pause_until(WUCond.ThreadsReady)
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

        assert not smart_event.alpha.event.is_set()
        assert not smart_event.beta.event.is_set()

        smart_event.sync(log_msg='mainline sync point 4')
        cmds.start_clock(iter=4)

        assert smart_event.wait(log_msg='mainline sync point 45')

        assert 2 <= cmds.duration() <= 3

        assert not smart_event.alpha.event.is_set()
        assert not smart_event.beta.event.is_set()
        smart_event.sync(log_msg='mainline sync point 5')

        thread_app.join()


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
        def f1(s_event):
            logger.debug('f1 entered')
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

        smart_event = SmartEvent(alpha=threading.current_thread())
        beta_thread = threading.Thread(target=f1, args=(smart_event,))
        smart_event.register_thread(beta=beta_thread)
        beta_thread.start()
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

    ###########################################################################
    # test_smart_event_f1_resume_time_out
    ###########################################################################
    def test_smart_event_f1_resume_time_out(self) -> None:
        """Test smart event wait timeout with f1 thread."""

        def f1(s_event: SmartEvent) -> None:
            """The remote thread for requests.

            Args:
                s_event: the smart event to test

            """
            logger.debug('f1 entered')
            # s_event.sync(log_msg='f1 beta sync point 1')

            # the first resume will set the flag ON and the flag will stay ON
            # since there is no matching wait
            assert not s_event.beta.event.is_set()
            assert s_event.resume(timeout=2)
            assert s_event.beta.event.is_set()

            # this second resume will timeout waiting for the flag to go OFF
            cmds.start_clock(iter=1)
            assert not s_event.resume(timeout=0.5)
            assert 0.5 <= cmds.duration() <= 0.75
            assert s_event.beta.event.is_set()

            s_event.sync(log_msg='f1 beta sync point 1')
            s_event.sync(log_msg='f1 beta sync point 2')

            # this first resume will complete within the timeout
            s_event.alpha.waiting = True  # simulate waiting
            s_event.alpha.deadlock = True  # simulate deadlock
            cmds.start_clock(iter=2)
            assert s_event.resume(timeout=1)
            assert 0.5 <= cmds.duration() <= 0.75

            # s_event.sync(log_msg='f1 beta sync point 3')
            s_event.sync(log_msg='f1 beta sync point 4')

            # this resume will timeout
            s_event.alpha.waiting = True  # simulate waiting
            s_event.alpha.deadlock = True  # simulate deadlock

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
            s_event.beta.deadlock = False
            s_event.beta.waiting = False

            s_event.sync(log_msg='f1 beta sync point 8')

            cmds.pause(0.75, iter=6)
            # clear the deadlock after resume timeout to cause ml to timeout
            s_event.beta.deadlock = False
            s_event.beta.waiting = False

            s_event.sync(log_msg='f1 beta sync point 9')

        cmds = Cmds()
        smart_event = SmartEvent(alpha=threading.current_thread())
        beta_thread = threading.Thread(target=f1, args=(smart_event,))
        smart_event.register_thread(beta=beta_thread)
        beta_thread.start()
        smart_event.pause_until(WUCond.ThreadsReady)
        smart_event.sync(log_msg='mainline sync point 1')

        # this wait will clear the flag - use timeout to prevent sync
        # from raising ConflictDeadlockDetected
        assert smart_event.beta.event.is_set()
        assert smart_event.wait(log_msg='mainline wait 12',
                                timeout=1)

        smart_event.sync(log_msg='mainline sync point 2')

        cmds.pause(0.5, iter=2)  # we purposely skipped iter=1

        # clear the deadlock within resume timeout to allow f1 resume to
        # complete
        smart_event.alpha.deadlock = False
        smart_event.alpha.waiting = False

        # smart_event.sync(log_msg='mainline sync point 3')
        smart_event.sync(log_msg='mainline sync point 4')

        cmds.pause(0.75, iter=3)

        # clear the deadlock after the resume timeout to cause f1 to timeout
        smart_event.alpha.deadlock = False
        smart_event.alpha.waiting = False

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
        smart_event.beta.waiting = True  # simulate waiting
        smart_event.beta.deadlock = True  # simulate deadlock
        cmds.start_clock(iter=5)
        assert smart_event.resume(timeout=1)
        assert 0.5 <= cmds.duration() <= 0.75

        smart_event.sync(log_msg='mainline sync point 8')

        # this resume will timeout
        smart_event.beta.waiting = True  # simulate waiting
        smart_event.beta.deadlock = True  # simulate deadlock
        cmds.start_clock(iter=6)
        assert not smart_event.resume(timeout=0.5)
        assert 0.5 <= cmds.duration() <= 0.75

        smart_event.sync(log_msg='mainline sync point 9')

        beta_thread.join()

    ###########################################################################
    # test_smart_event_thread_app_time_out
    ###########################################################################
    def test_smart_event_thread_app_time_out(self) -> None:
        """Test smart event timeout with thread_app thread."""
        class MyThread(threading.Thread):
            def __init__(self, s_event: SmartEvent):
                super().__init__()
                self.s_event = s_event
                self.s_event.register_thread(beta=self)

            def run(self):
                logger.debug('ThreadApp run entered')

                cmds.start_clock(iter=1)
                assert not self.s_event.wait(timeout=2)
                assert 2 <= cmds.duration() < 3

                assert self.s_event.sync(log_msg='beta sync point 1')
                assert self.s_event.sync(log_msg='beta sync point 2')

        cmds = Cmds()
        smart_event = SmartEvent(alpha=threading.current_thread())
        thread_app = MyThread(smart_event)
        thread_app.start()

        smart_event.pause_until(WUCond.ThreadsReady)

        assert smart_event.sync(log_msg='alpha sync point 1')

        cmds.start_clock(iter=2)
        assert not smart_event.wait(timeout=2)
        assert 2 <= cmds.duration() < 3

        assert smart_event.sync(log_msg='alpha sync point 2')

        thread_app.join()


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
        def f1(s_event):
            logger.debug('f1 entered')
            assert not s_event.alpha.code
            assert not s_event.beta.code
            assert not s_event.get_code()

            s_event.sync(log_msg='beta sync point 1')

            assert s_event.wait(timeout=2)
            assert not s_event.alpha.code
            assert s_event.beta.code == 42
            assert 42 == s_event.get_code()

            s_event.sync(log_msg='beta sync point 2')

            s_event.resume(code='forty-two')
            assert s_event.alpha.code == 'forty-two'
            assert s_event.beta.code == 42
            assert 42 == s_event.get_code()

            s_event.sync(log_msg='beta sync point 3')

            assert s_event.alpha.code == 'forty-two'
            assert s_event.beta.code == 42
            assert 42 == s_event.get_code()

            assert not s_event.wait(timeout=.5)

            assert s_event.alpha.code == 'forty-two'
            assert s_event.beta.code == 42
            assert 42 == s_event.get_code()

            s_event.sync(log_msg='beta sync point 4')
            s_event.sync(log_msg='beta sync point 5')

            assert s_event.alpha.code == 'forty-two'
            assert s_event.beta.code == 'twenty one'
            assert 'twenty one' == s_event.get_code()
            assert s_event.alpha.event.is_set()

        smart_event = SmartEvent(alpha=threading.current_thread())
        beta_thread = threading.Thread(target=f1, args=(smart_event,))
        smart_event.register_thread(beta=beta_thread)
        beta_thread.start()
        smart_event.pause_until(WUCond.ThreadsReady)

        smart_event.sync(log_msg='mainline sync point 1')

        assert not smart_event.get_code()
        assert not smart_event.alpha.code
        assert not smart_event.beta.code

        smart_event.resume(code=42)

        assert not smart_event.get_code()
        assert not smart_event.alpha.code
        assert smart_event.beta.code == 42

        smart_event.sync(log_msg='mainline sync point 2')

        assert smart_event.wait()

        assert smart_event.get_code() == 'forty-two'
        assert smart_event.alpha.code == 'forty-two'
        assert smart_event.beta.code == 42

        smart_event.sync(log_msg='mainline sync point 3')
        smart_event.sync(log_msg='mainline sync point 4')

        smart_event.resume(code='twenty one')

        smart_event.sync(log_msg='mainline sync point 5')

        beta_thread.join()

    ###########################################################################
    # test_smart_event_thread_app_event_code
    ###########################################################################
    def test_smart_event_thread_app_event_code(self) -> None:
        """Test smart event code with thread_app thread."""

        class MyThread(threading.Thread):
            def __init__(self, s_event: SmartEvent):
                super().__init__()
                self.s_event = s_event
                self.s_event.register_thread(beta=self)

            def run(self):
                logger.debug('ThreadApp run entered')
                assert self.s_event.get_code() is None
                assert not self.s_event.wait(timeout=2, log_msg='beta wait 1')

                self.s_event.sync(log_msg='beta sync point 2')
                self.s_event.sync(log_msg='beta sync point 3')

                assert self.s_event.alpha.event.is_set()
                assert self.s_event.beta.code == 42
                assert self.s_event.get_code() == 42

                self.s_event.resume(log_msg='beta resume 4',
                                    code='forty-two')

        smart_event = SmartEvent(alpha=threading.current_thread())
        thread_app = MyThread(smart_event)
        thread_app.start()
        smart_event.pause_until(WUCond.ThreadsReady)

        smart_event.sync(log_msg='mainline sync point 2')
        smart_event.resume(code=42)
        smart_event.sync(log_msg='mainline sync point 3')

        assert smart_event.wait(log_msg='mainline wait 4')
        assert smart_event.get_code() == 'forty-two'

        thread_app.join()

    ###########################################################################
    # test_smart_event_thread_event_app_event_code
    ###########################################################################
    def test_smart_event_thread_event_app_event_code(self) -> None:
        """Test smart event code with thread_event_app thread."""
        class MyThread(threading.Thread, SmartEvent):
            def __init__(self,
                         alpha: threading.Thread) -> None:
                threading.Thread.__init__(self)
                SmartEvent.__init__(self, alpha=alpha, beta=self)

            def run(self):
                logger.debug('ThreadApp run entered')

                assert not self.alpha.code
                assert not self.beta.code
                assert not self.get_code()

                self.sync(log_msg='beta sync point 1')

                assert not self.wait(timeout=0.5)

                assert not self.alpha.code
                assert not self.beta.code
                assert not self.get_code()

                self.sync(log_msg='beta sync point 2')
                self.sync(log_msg='beta sync point 3')

                assert not self.alpha.code
                assert self.beta.code == 42
                assert self.get_code() == 42

                self.resume(code='forty-two')

                assert self.alpha.code == 'forty-two'
                assert self.beta.code == 42
                assert self.get_code() == 42

                self.sync(log_msg='beta sync point 4')
                self.sync(log_msg='beta sync point 5')

                assert self.alpha.code == 'forty-two'
                assert self.beta.code == 42
                assert self.get_code() == 42

                assert self.wait(timeout=0.5, log_msg='beta wait 56')

                assert self.alpha.code == 'forty-two'
                assert self.beta.code == 42
                assert self.get_code() == 42

                self.sync(log_msg='beta sync point 6')

        thread_event_app = MyThread(alpha=threading.current_thread())
        thread_event_app.start()
        thread_event_app.pause_until(WUCond.ThreadsReady)

        assert not thread_event_app.alpha.code
        assert not thread_event_app.beta.code
        assert not thread_event_app.get_code()

        thread_event_app.sync(log_msg='mainline sync point 1')
        thread_event_app.sync(log_msg='mainline sync point 2')

        assert not thread_event_app.alpha.code
        assert not thread_event_app.beta.code
        assert not thread_event_app.get_code()

        thread_event_app.resume(code=42, log_msg='mainline resume for beta 56')

        assert not thread_event_app.alpha.code
        assert thread_event_app.beta.code == 42
        assert not thread_event_app.get_code()

        thread_event_app.sync(log_msg='mainline sync point 3')
        thread_event_app.sync(log_msg='mainline sync point 4')

        assert thread_event_app.alpha.code == 'forty-two'
        assert thread_event_app.beta.code == 42
        assert thread_event_app.get_code() == 'forty-two'

        assert thread_event_app.wait()

        assert thread_event_app.alpha.code == 'forty-two'
        assert thread_event_app.beta.code == 42
        assert thread_event_app.get_code() == 'forty-two'

        thread_event_app.sync(log_msg='mainline sync point 5')

        assert thread_event_app.alpha.code == 'forty-two'
        assert thread_event_app.beta.code == 42
        assert thread_event_app.get_code() == 'forty-two'

        thread_event_app.sync(log_msg='mainline sync point 6')

        thread_event_app.join()


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
        def f1(s_event, exp_log_msgs):
            exp_log_msgs.add_msg('f1 entered')
            logger.debug('f1 entered')

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

        smart_event = SmartEvent(alpha=threading.current_thread())
        beta_thread = threading.Thread(target=f1, args=(smart_event,
                                                        exp_log_msgs))
        smart_event.register_thread(beta=beta_thread)
        beta_thread.start()
        smart_event.pause_until(WUCond.ThreadsReady)

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
                         s_event: SmartEvent,
                         exp_log_msgs: ExpLogMsgs):
                super().__init__()
                self.s_event = s_event
                self.s_event.register_thread(beta=self)
                self.exp_log_msgs = exp_log_msgs

            def run(self):
                l_msg = 'ThreadApp run entered'
                self.exp_log_msgs.add_msg(l_msg)
                logger.debug(l_msg)

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

        smart_event = SmartEvent(alpha=threading.current_thread())
        thread_app = MyThread(smart_event, exp_log_msgs)
        thread_app.start()
        smart_event.pause_until(WUCond.ThreadsReady)

        exp_log_msgs.add_alpha_sync_msg('mainline sync point 1')
        smart_event.sync(log_msg='mainline sync point 1')

        smart_event.pause_until(WUCond.RemoteWaiting)

        exp_log_msgs.add_alpha_resume_msg(
            f'post thread {smart_event.beta.name} 23', True, 42)
        smart_event.resume(log_msg=f'post thread {smart_event.beta.name} 23',
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
                         alpha: threading.Thread,
                         exp_log_msgs: ExpLogMsgs):
                threading.Thread.__init__(self)
                SmartEvent.__init__(self, alpha=alpha, beta=self)
                self.exp_log_msgs = exp_log_msgs

            def run(self):
                self.exp_log_msgs.add_msg('ThreadApp run entered')
                logger.debug('ThreadApp run entered')

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

        thread_event_app = MyThread(alpha=threading.current_thread(),
                                    exp_log_msgs=exp_log_msgs)

        thread_event_app.start()

        thread_event_app.pause_until(WUCond.ThreadsReady)

        exp_log_msgs.add_alpha_sync_msg('mainline sync point 1')
        thread_event_app.sync(log_msg='mainline sync point 1')

        thread_event_app.pause_until(WUCond.RemoteWaiting)

        exp_log_msgs.add_alpha_resume_msg(
            f'post thread {thread_event_app.beta.name} 12')
        thread_event_app.resume(log_msg=f'post thread '
                                f'{thread_event_app.beta.name} 12')

        exp_log_msgs.add_alpha_sync_msg('mainline sync point 2')
        thread_event_app.sync(log_msg='mainline sync point 2')

        exp_log_msgs.add_alpha_wait_msg('wait for post from thread 23')
        assert thread_event_app.wait(log_msg='wait for post from thread 23')

        exp_log_msgs.add_alpha_sync_msg('mainline sync point 3')
        thread_event_app.sync(log_msg='mainline sync point 3')

        thread_event_app.join()

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

        smart_event = SmartEvent(alpha=threading.current_thread())

        cmds.l_msg = log_msg_arg1
        cmds.r_code = code_arg1

        f1_thread = threading.Thread(target=thread_func1,
                                     args=(smart_event,
                                           cmds,
                                           exp_log_msgs))
        smart_event.register_thread(beta=f1_thread)
        l_msg = 'mainline about to start thread_func1'
        exp_log_msgs.add_msg(l_msg)
        logger.debug(l_msg)

        f1_thread.start()
        smart_event.pause_until(WUCond.ThreadsReady, timeout=1)

        self.action_loop(smart_event=smart_event,
                         action1=action_arg1,
                         action2=action_arg2,
                         cmds=cmds,
                         exp_log_msgs=exp_log_msgs,
                         thread_exc1=thread_exc)

        l_msg = 'main completed all actions'
        exp_log_msgs.add_msg(l_msg)
        logger.debug(l_msg)

        cmds.queue_cmd('beta', Cmd.Exit)

        f1_thread.join()

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

        smart_event = SmartEvent()
        cmds.l_msg = log_msg_arg1
        cmds.r_code = code_arg1

        f1_thread = threading.Thread(target=thread_func1,
                                     args=(smart_event,
                                           cmds,
                                           exp_log_msgs))

        f2_thread = threading.Thread(target=self.action_loop,
                                     args=(smart_event,
                                           action_arg1,
                                           action_arg2,
                                           cmds,
                                           exp_log_msgs,
                                           thread_exc))
        smart_event.register_thread(alpha=f2_thread, beta=f1_thread)
        l_msg = 'mainline about to start thread_func1'
        exp_log_msgs.add_msg(l_msg)
        logger.debug(l_msg)

        f1_thread.start()
        f2_thread.start()
        smart_event.pause_until(WUCond.ThreadsReady, timeout=1)

        l_msg = 'main completed all actions'
        exp_log_msgs.add_msg(l_msg)
        logger.debug(l_msg)

        f2_thread.join()
        cmds.queue_cmd('beta', Cmd.Exit)

        f1_thread.join()

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
                         smart_event: SmartEvent,
                         cmds: Cmds,
                         exp_log_msgs: ExpLogMsgs
                         ) -> None:
                """Initialize the object.

                Args:
                    smart_event: the smart event to use
                    cmds: commands for beta to do
                    exp_log_msgs: container for expected log messages

                """
                super().__init__()
                self.smart_event = smart_event
                self.cmds = cmds
                self.exp_log_msgs = exp_log_msgs

            def run(self):
                """Thread to send and receive messages."""
                l_msg = 'SmartEventApp run started'
                self.exp_log_msgs.add_msg(l_msg)
                logger.debug(l_msg)
                thread_func1(
                    s_event=self.smart_event,
                    cmds=self.cmds,
                    exp_log_msgs=self.exp_log_msgs)

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

        smart_event = SmartEvent(alpha=threading.current_thread())

        cmds.l_msg = log_msg_arg1
        cmds.r_code = code_arg1

        f1_thread = SmartEventApp(smart_event,
                                  cmds,
                                  exp_log_msgs)

        smart_event.register_thread(beta=f1_thread)
        l_msg = 'mainline about to start SmartEventApp'
        exp_log_msgs.add_msg(l_msg)
        logger.debug(l_msg)

        f1_thread.start()
        smart_event.pause_until(WUCond.ThreadsReady, timeout=1)

        self.action_loop(smart_event=smart_event,
                         action1=action_arg1,
                         action2=action_arg2,
                         cmds=cmds,
                         exp_log_msgs=exp_log_msgs,
                         thread_exc1=thread_exc)

        l_msg = 'main completed all actions'
        exp_log_msgs.add_msg(l_msg)
        logger.debug(l_msg)
        cmds.queue_cmd('beta', Cmd.Exit)

        f1_thread.join()

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
                                    alpha=threading.current_thread(),
                                    beta=self)

                self.cmds = cmds
                self.exp_log_msgs = exp_log_msgs

            def run(self):
                """Thread to send and receive messages."""
                l_msg = 'SmartEventApp run started'
                self.exp_log_msgs.add_msg(l_msg)
                logger.debug(l_msg)
                thread_func1(
                    s_event=self,
                    cmds=self.cmds,
                    exp_log_msgs=self.exp_log_msgs)

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

        cmds.l_msg = log_msg_arg1
        cmds.r_code = code_arg1

        f1_thread = SmartEventApp(cmds,
                                  exp_log_msgs)

        l_msg = 'mainline about to start SmartEventApp'
        exp_log_msgs.add_msg(l_msg)
        logger.debug(l_msg)
        f1_thread.start()
        f1_thread.pause_until(WUCond.ThreadsReady, timeout=1)

        self.action_loop(smart_event=f1_thread,
                         action1=action_arg1,
                         action2=action_arg2,
                         cmds=cmds,
                         exp_log_msgs=exp_log_msgs,
                         thread_exc1=thread_exc)

        l_msg = 'main completed all actions'
        exp_log_msgs.add_msg(l_msg)
        logger.debug(l_msg)
        cmds.queue_cmd('beta', Cmd.Exit)

        f1_thread.join()

        if log_msg_arg1:
            exp_log_msgs.verify_log_msgs(caplog=caplog, log_enabled_tf=True)

    ###########################################################################
    # action loop
    ###########################################################################
    def action_loop(self,
                    smart_event: SmartEvent,
                    action1: Any,
                    action2: Any,
                    cmds: Any,
                    exp_log_msgs: Any,
                    thread_exc1: Any
                    ) -> None:
        """Actions to perform with the thread.

        Args:
            smart_event: smart event to test
            action1: first smart event request to do
            action2: second smart event request to do
            cmds: contains cmd queues and other test args
            exp_log_msgs: container for expected log messages
            thread_exc1: contains any uncaptured errors from thread

        Raises:
            IncorrectActionSpecified: The Action is not recognized
            UnrecognizedCmd: beta send mainline an unrecognized command

        """
        smart_event.pause_until(WUCond.ThreadsReady, timeout=1)
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
                    assert smart_event.alpha.code == cmds.r_code
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
                    assert smart_event.beta.code == cmds.r_code
                else:
                    assert smart_event.resume()
                    assert not smart_event.beta.code

                assert smart_event.alpha.event.is_set()
                cmds.queue_cmd('beta', Cmd.Wait)

            elif action == Action.MainResume_TOT:
                l_msg = 'main starting Action.MainResume_TOT'
                exp_log_msgs.add_msg(l_msg)
                logger.debug(l_msg)
                if cmds.r_code:
                    assert smart_event.resume(code=cmds.r_code, timeout=0.5)
                    assert smart_event.beta.code == cmds.r_code
                else:
                    assert smart_event.resume(timeout=0.5)
                    assert not smart_event.beta.code

                assert smart_event.alpha.event.is_set()
                cmds.queue_cmd('beta', Cmd.Wait)

            elif action == Action.MainResume_TOF:
                l_msg = 'main starting Action.MainResume_TOF'
                exp_log_msgs.add_msg(l_msg)
                logger.debug(l_msg)
                l_msg = (f'{smart_event.alpha.name} timeout '
                         r'of a resume\(\) request with '
                         r'current.event.is_set\(\) = True and '
                         'remote.deadlock = False')
                exp_log_msgs.add_msg(l_msg)

                assert not smart_event.alpha.event.is_set()
                # pre-resume to set flag
                if cmds.r_code:
                    assert smart_event.resume(code=cmds.r_code)
                    assert smart_event.beta.code == cmds.r_code
                else:
                    assert smart_event.resume()
                    assert not smart_event.beta.code

                assert smart_event.alpha.event.is_set()

                if cmds.r_code:
                    start_time = time.time()
                    assert not smart_event.resume(code=cmds.r_code,
                                                  timeout=0.3)
                    assert 0.3 <= (time.time() - start_time) <= 0.5
                    assert smart_event.beta.code == cmds.r_code
                else:
                    start_time = time.time()
                    assert not smart_event.resume(timeout=0.5)
                    assert 0.5 <= (time.time() - start_time) <= 0.75
                    assert not smart_event.beta.code

                assert smart_event.alpha.event.is_set()

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
                    assert smart_event.beta.code == cmds.r_code
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
                    assert smart_event.beta.code == cmds.r_code
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
                    assert smart_event.alpha.code == cmds.r_code
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
def thread_func1(s_event: SmartEvent,
                 cmds: any,
                 exp_log_msgs: Any,
                 ) -> None:
    """Thread to test SmartEvent scenarios.

    Args:
        s_event: instance of SmartEvent
        cmds: commands to do
        exp_log_msgs: expected log messages

    Raises:
        UnrecognizedCmd: Thread received an unrecognized command

    """
    l_msg = 'thread_func1 beta started'
    exp_log_msgs.add_msg(l_msg)
    logger.debug(l_msg)

    s_event.pause_until(WUCond.ThreadsReady, timeout=1)
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
                assert s_event.beta.code == cmds.r_code
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
                assert s_event.beta.code == cmds.r_code
                assert cmds.r_code == s_event.get_code()

            cmds.queue_cmd('alpha', Cmd.Next_Action)

        elif beta_cmd == Cmd.Wait_TOF:
            l_msg = 'thread_func1 doing Wait_TOF'
            exp_log_msgs.add_msg(l_msg)
            logger.debug(l_msg)
            l_msg = (f'{s_event.beta.name} timeout of a '
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
                assert s_event.beta.code == cmds.r_code
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
                assert s_event.alpha.code == cmds.r_code
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
                    ret_code: bool,
                    code: Optional[Any] = None
                    ) -> None:
        """Add an expected request message to the expected log messages.

        Args:
            l_msg: message to add
            who: either 'alpha or 'beta'
            req: one of 'sync', 'resume', or 'wait'
            ret_code: bool
            code: code for resume or None

        """
        l_enter_msg = req + r'\(\) entered '
        if code is not None:
            l_enter_msg += f'with code: {code} '

        l_exit_msg = req + r'\(\) exiting with ret_code '
        if ret_code:
            l_exit_msg += 'True '
        else:
            l_exit_msg += 'False '

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


###############################################################################
# ThreadCmd Class
###############################################################################
class Cmds:
    """Cmd class for testing."""
    def __init__(self):
        """Initialize the object."""
        self.alpha_cmd = queue.Queue(maxsize=10)
        self.beta_cmd = queue.Queue(maxsize=10)
        self.l_msg: Any = None
        self.r_code: Any = None
        self.start_time: float = 0.0
        self.previous_start_time: float = 0.0
        self.clock_in_use = False
        self.iteration = 0

    def queue_cmd(self, who: str, cmd: Any) -> None:
        """Place a cmd on the cmd queue for the specified who.

        Args:
            who: alpha when cmd is for alpha, beta when cmd is for beta
            cmd: command to place on queue

        Raises:
            ValueError: who must be alpha or beta

        """
        if who == 'alpha':
            self.alpha_cmd.put(cmd,
                               block=True,
                               timeout=0.5)
        elif who == 'beta':
            self.beta_cmd.put(cmd,
                              block=True,
                              timeout=0.5)
        else:
            raise ValueError

    def get_cmd(self, who: str) -> Any:
        """Get the next command for alpha to do.

        Args:
            who: alpha to get cmd for alpha to do, beta for cmd for beta to do

        Returns:
            the cmd to perform

        Raises:
            ValueError: who must be alpha or beta

        """
        while True:
            try:
                if who == 'alpha':
                    cmd = self.alpha_cmd.get(block=True, timeout=0.1)
                elif who == 'beta':
                    cmd = self.beta_cmd.get(block=True, timeout=0.1)
                else:
                    raise ValueError
                return cmd
            except queue.Empty:
                continue

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
