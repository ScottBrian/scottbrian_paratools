"""test_thread_pair.py module."""

###############################################################################
# Standard Library
###############################################################################
from enum import Enum
import logging
import time
from typing import Any, cast, Dict, Final, List, Optional, Union
import threading

###############################################################################
# Third Party
###############################################################################
import pytest

###############################################################################
# Local
###############################################################################
from .conftest import Cmds, ThreadPairDesc, ThreadPairDescs, ExpLogMsgs



from scottbrian_paratools.thread_pair import (
    ThreadPair,
    ThreadPairAlreadyPairedWithRemote,
    ThreadPairDetectedOpFromForeignThread,
    ThreadPairErrorInRegistry,
    ThreadPairIncorrectNameSpecified,
    ThreadPairIncorrectGroupNameSpecified,
    ThreadPairNameAlreadyInUse,
    ThreadPairNotPaired,
    ThreadPairPairWithSelfNotAllowed,
    ThreadPairPairWithTimedOut,
    ThreadPairRemoteThreadNotAlive,
    ThreadPairRemotePairedWithOther)

import logging

logger = logging.getLogger(__name__)
logger.debug('about to start the tests')


###############################################################################
# ThreadPair test exceptions
###############################################################################
class ErrorTstThreadPair(Exception):
    """Base class for exception in this module."""
    pass


class IncorrectActionSpecified(ErrorTstThreadPair):
    """IncorrectActionSpecified exception class."""
    pass


class UnrecognizedCmd(ErrorTstThreadPair):
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
# TestThreadPairBasic class to test ThreadPair methods
###############################################################################
###############################################################################
# Theta class
###############################################################################
class Theta(ThreadPair):
    """Theta test class."""
    def __init__(self,
                 group_name: str,
                 name: str,
                 thread: Optional[threading.Thread] = None) -> None:
        """Initialize the Theta object.

        Args:
            name: name of the Theta
            thread: thread to use instead of threading.current_thread()

        """
        ThreadPair.__init__(self, group_name=group_name, name=name, thread=thread)
        self.var1 = 'theta'


###############################################################################
# ThetaDesc class
###############################################################################
class ThetaDesc(ThreadPairDesc):
    """Describes a Theta with name and thread to verify."""
    def __init__(self,
                 name: Optional[str] = '',
                 theta: Optional[Theta] = None,
                 thread: Optional[threading.Thread] = None,  # type: ignore
                 state: Optional[int] = 0,  # 0 is unknown
                 paired_with: Optional[Any] = None) -> None:
        """Initialize the ThetaDesc.

        Args:
            name: name of the Theta
            theta: the Theta being tracked by this desc
            thread: the thread associated with this Theta
            state: describes whether the Theta is alive and registered
            paired_with: names the Theta paired with this one, if one

        """
        ThreadPairDesc.__init__(self,
                                name=name,
                                thread_pair=theta,
                                thread=thread,
                                state=state,
                                paired_with=paired_with)

    def verify_state(self) -> None:
        """Verify the state of the Theta."""
        ThreadPairDesc.verify_state(self)
        self.verify_theta_desc()
        if self.paired_with is not None:
            self.paired_with.verify_theta_desc()

    ###########################################################################
    # verify_theta_desc
    ###########################################################################
    def verify_theta_desc(self) -> None:
        """Verify the Theta object is initialized correctly."""
        assert isinstance(self.thread_pair, Theta)

        assert self.thread_pair.var1 == 'theta'


###############################################################################
# Sigma class
###############################################################################
class Sigma(ThreadPair):
    """Sigma test class."""
    def __init__(self,
                 group_name: str,
                 name: str,
                 thread: Optional[threading.Thread] = None) -> None:
        """Initialize the Sigma object.

        Args:
            name: name of the Sigma
            thread: thread to use instead of threading.current_thread()

        """
        ThreadPair.__init__(self, group_name=group_name, name=name, thread=thread)
        self.var1 = 17
        self.var2 = 'sigma'


###############################################################################
# SigmaDesc class
###############################################################################
class SigmaDesc(ThreadPairDesc):
    """Describes a Sigma with name and thread to verify."""
    def __init__(self,
                 name: Optional[str] = '',
                 sigma: Optional[Sigma] = None,
                 thread: Optional[threading.Thread] = None,  # type: ignore
                 state: Optional[int] = 0,  # 0 is unknown
                 paired_with: Optional[Any] = None) -> None:
        """Initialize the SigmaDesc.

        Args:
            name: name of the Sigma
            sigma: the Sigma being tracked by this desc
            thread: the thread associated with this Sigma
            state: describes whether the Sigma is alive and registered
            paired_with: names the Sigma paired with this one, if one

        """
        ThreadPairDesc.__init__(self,
                                name=name,
                                thread_pair=sigma,
                                thread=thread,
                                state=state,
                                paired_with=paired_with)

    def verify_state(self) -> None:
        """Verify the state of the Sigma."""
        ThreadPairDesc.verify_state(self)
        self.verify_sigma_desc()
        if self.paired_with is not None:
            self.paired_with.verify_sigma_desc()

    ###########################################################################
    # verify_sigma_desc
    ###########################################################################
    def verify_sigma_desc(self) -> None:
        """Verify the Sigma object is initialized correctly."""
        assert isinstance(self.thread_pair, Sigma)

        assert self.thread_pair.var1 == 17
        assert self.thread_pair.var2 == 'sigma'


###############################################################################
# Omega class
###############################################################################
class Omega(ThreadPair):
    """Omega test class."""
    def __init__(self,
                 group_name: str,
                 name: str,
                 thread: Optional[threading.Thread] = None) -> None:
        """Initialize the Omega object.

        Args:
            name: name of the Omega
            thread: thread to use instead of threading.current_thread()

        """
        ThreadPair.__init__(self, group_name=group_name, name=name, thread=thread)
        self.var1 = 42
        self.var2 = 64.9
        self.var3 = 'omega'


###############################################################################
# OmegaDesc class
###############################################################################
class OmegaDesc(ThreadPairDesc):
    """Describes a Omega with name and thread to verify."""
    def __init__(self,
                 name: Optional[str] = '',
                 omega: Optional[Omega] = None,
                 thread: Optional[threading.Thread] = None,  # type: ignore
                 state: Optional[int] = 0,  # 0 is unknown
                 paired_with: Optional[Any] = None) -> None:
        """Initialize the OmegaDesc.

        Args:
            name: name of the Omega
            omega: the Omega being tracked by this desc
            thread: the thread associated with this Omega
            state: describes whether the Omega is alive and registered
            paired_with: names the Omega paired with this one, if one

        """
        ThreadPairDesc.__init__(self,
                                name=name,
                                thread_pair=omega,
                                thread=thread,
                                state=state,
                                paired_with=paired_with)

    def verify_state(self) -> None:
        """Verify the state of the Omega."""
        ThreadPairDesc.verify_state(self)
        self.verify_omega_desc()
        if self.paired_with is not None:
            self.paired_with.verify_omega_desc()

    ###########################################################################
    # verify_omega_desc
    ###########################################################################
    def verify_omega_desc(self) -> None:
        """Verify the Omega object is initialized correctly."""
        assert isinstance(self.thread_pair, Omega)

        assert self.thread_pair.var1 == 42
        assert self.thread_pair.var2 == 64.9
        assert self.thread_pair.var3 == 'omega'


###############################################################################
# outer_f1
###############################################################################
def outer_f1(cmds: Cmds,
             descs: ThreadPairDescs,
             ) -> None:
    """Outer function to test ThreadPair.

    Args:
        cmds: Cmds object to tell alpha when to go
        descs: tracks set of ThreadPairDesc items

    """
    logger.debug('outer_f1 entered')
    t_pair = ThreadPair(group_name='group1', name='beta')
    descs.add_desc(ThreadPairDesc(name='beta',
                                  thread_pair=t_pair))

    # tell alpha OK to verify (i.e., beta_thread_pair set with t_pair)
    cmds.queue_cmd('alpha', 'go')

    t_pair.pair_with(remote_name='alpha')

    cmds.get_cmd('beta')

    logger.debug('outer f1 exiting')


###############################################################################
# OuterThreadApp class
###############################################################################
class OuterThreadApp(threading.Thread):
    """Outer thread app for test."""
    def __init__(self,
                 cmds: Cmds,
                 descs: ThreadPairDescs
                 ) -> None:
        """Initialize the object.

        Args:
            cmds: used to tell alpha to go
            descs: tracks set of ThreadPairDescs items

        """
        super().__init__()
        self.cmds = cmds
        self.descs = descs
        self.t_pair = ThreadPair(group_name='group1', name='beta', thread=self)

    def run(self) -> None:
        """Run the test."""
        print('beta run started')

        # normally, the add_desc is done just after the instantiation, but
        # in this case the thread is not made alive until now, and the
        # add_desc checks that the thread is alive
        self.descs.add_desc(ThreadPairDesc(name='beta',
                                           thread_pair=self.t_pair,
                                           thread=self))

        self.cmds.queue_cmd('alpha')

        self.t_pair.pair_with(remote_name='alpha')
        self.descs.paired('alpha', 'beta')

        self.cmds.get_cmd('beta')

        logger.debug('beta run exiting')


###############################################################################
# OuterThreadEventApp class
###############################################################################
class OuterThreadEventApp(threading.Thread, ThreadPair):
    """Outer thread event app for test."""
    def __init__(self,
                 cmds: Cmds,
                 descs: ThreadPairDescs) -> None:
        """Initialize the object.

        Args:
            cmds: used to send cmds between threads
            descs: tracks set of ThreadPairDesc items

        """
        threading.Thread.__init__(self)
        ThreadPair.__init__(self, group_name='group1', name='beta', thread=self)
        self.cmds = cmds
        self.descs = descs

    def run(self):
        """Run the test."""
        print('beta run started')

        # normally, the add_desc is done just after the instantiation, but
        # in this case the thread is not made alive until now, and the
        # add_desc checks that the thread is alive
        self.descs.add_desc(ThreadPairDesc(name='beta',
                                           thread_pair=self,
                                           thread=self))

        self.cmds.queue_cmd('alpha')

        self.pair_with(remote_name='alpha', timeout=3)
        self.descs.paired('alpha', 'beta')

        self.cmds.get_cmd('beta')

        logger.debug('beta run exiting')


###############################################################################
# TestThreadPairBasic class
###############################################################################
class TestThreadPairBasic:
    """Test class for ThreadPair basic tests."""

    ###########################################################################
    # repr for ThreadPair
    ###########################################################################
    def test_thread_pair_repr(self,
                              thread_exc: Any) -> None:
        """Test event with code repr.

        Args:
            thread_exc: captures thread exceptions

        """
        descs = ThreadPairDescs()

        thread_pair = ThreadPair(group_name='group1', name='alpha')
        descs.add_desc(ThreadPairDesc(name='alpha',
                                      thread_pair=thread_pair,
                                      thread=threading.current_thread()))

        expected_repr_str = 'ThreadPair(group_name="group1", name="alpha")'

        assert repr(thread_pair) == expected_repr_str

        thread_pair2 = ThreadPair(group_name="group1", name="AlphaDog")
        descs.add_desc(ThreadPairDesc(name='AlphaDog',
                                      thread_pair=thread_pair2,
                                      thread=threading.current_thread()))

        expected_repr_str = 'ThreadPair(group_name="group1", name="AlphaDog")'

        assert repr(thread_pair2) == expected_repr_str

        def f1():
            t_pair = ThreadPair(group_name='group1', name='beta1')
            descs.add_desc(ThreadPairDesc(name='beta1',
                                          thread_pair=t_pair,
                                          thread=threading.current_thread()))
            f1_expected_repr_str = 'ThreadPair(group_name="group1", name="beta1")'
            assert repr(t_pair) == f1_expected_repr_str

            cmds.queue_cmd('alpha', 'go')
            cmds.get_cmd('beta1')

        def f2():
            t_pair = ThreadPair(group_name='group1', name='beta2')
            descs.add_desc(ThreadPairDesc(name='beta2',
                                          thread_pair=t_pair,
                                          thread=threading.current_thread()))
            f1_expected_repr_str = 'ThreadPair(group_name="group1", name="beta2")'
            assert repr(t_pair) == f1_expected_repr_str
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
    # test_thread_pair_instantiate_with_errors
    ###########################################################################
    def test_thread_pair_instantiate_with_errors(self) -> None:
        """Test register_thread alpha first."""

        descs = ThreadPairDescs()

        thread_pair = ThreadPair(group_name='group1', name='alpha')

        descs.add_desc(ThreadPairDesc(name='alpha',
                                      thread_pair=thread_pair,
                                      thread=threading.current_thread()))

        # not OK to instantiate a new thread_pair with same name
        with pytest.raises(ThreadPairNameAlreadyInUse):
            _ = ThreadPair(group_name='group1', name='alpha')

        with pytest.raises(ThreadPairIncorrectNameSpecified):
            _ = ThreadPair(group_name='group1', name=42)  # type: ignore

        # try to pair with unknown remote
        with pytest.raises(ThreadPairPairWithTimedOut):
            thread_pair.pair_with(remote_name='beta', timeout=0.1)

        # try to pair with bad name
        with pytest.raises(ThreadPairIncorrectNameSpecified):
            thread_pair.pair_with(remote_name=3)  # type: ignore

        # make sure everything still the same

        descs.verify_registry()

    ###########################################################################
    # test_thread_pair_pairing_with_errors
    ###########################################################################
    def test_thread_pair_pairing_with_errors(self) -> None:
        """Test register_thread during instantiation."""
        def f1(name: str) -> None:
            """Func to test instantiate ThreadPair.

            Args:
                name: name to use for t_pair
            """
            logger.debug(f'{name} f1 entered')
            t_pair = ThreadPair(group_name='group1', name=name)
            descs.add_desc(ThreadPairDesc(name=name,
                                          thread_pair=t_pair))

            cmds.queue_cmd('alpha', 'go')

            # not OK to pair with self
            with pytest.raises(ThreadPairPairWithSelfNotAllowed):
                t_pair.pair_with(remote_name=name)

            t_pair.pair_with(remote_name='alpha')

            # not OK to pair with remote a second time
            with pytest.raises(ThreadPairAlreadyPairedWithRemote):
                t_pair.pair_with(remote_name='alpha')

            cmds.get_cmd('beta')

            logger.debug(f'{name} f1 exiting')

        cmds = Cmds()

        descs = ThreadPairDescs()

        beta_t = threading.Thread(target=f1, args=('beta',))

        thread_pair = ThreadPair(group_name='group1', name='alpha')

        descs.add_desc(ThreadPairDesc(name='alpha',
                                      thread_pair=thread_pair,
                                      thread=threading.current_thread()))
        beta_t.start()

        # not OK to pair with self
        with pytest.raises(ThreadPairPairWithSelfNotAllowed):
            thread_pair.pair_with(remote_name='alpha')

        cmds.get_cmd('alpha')

        thread_pair.pair_with(remote_name='beta')
        descs.paired('alpha', 'beta')

        # not OK to pair with remote a second time
        with pytest.raises(ThreadPairAlreadyPairedWithRemote):
            thread_pair.pair_with(remote_name='beta')

        cmds.queue_cmd('beta')

        beta_t.join()

        descs.thread_end(name='beta')

        # at this point, f1 has ended. But, the registry will not have changed,
        # so everything will still show paired, even both alpha and beta
        # ThreadPairs. Alpha ThreadPair will detect that beta is no longer
        # alive if a function is attempted.

        descs.verify_registry()

        #######################################################################
        # second case - f1 with same name beta
        #######################################################################
        beta_t2 = threading.Thread(target=f1, args=('beta',))
        beta_t2.start()

        cmds.get_cmd('alpha')

        thread_pair.pair_with(remote_name='beta')
        descs.paired('alpha', 'beta')

        cmds.queue_cmd('beta')

        beta_t2.join()

        descs.thread_end(name='beta')

        # at this point, f1 has ended. But, the registry will not have changed,
        # so everything will still show paired, even both alpha and beta
        # ThreadPairs. Alpha ThreadPair will detect that beta is no longer
        # alive if a function is attempted.
        descs.verify_registry()

        #######################################################################
        # third case, use different name for f1. Should clean up old beta
        # from the registry.
        #######################################################################
        with pytest.raises(ThreadPairNameAlreadyInUse):
            thread_pair = ThreadPair(group_name='group1', name='alpha')  # create fresh

        beta_t3 = threading.Thread(target=f1, args=('charlie',))
        beta_t3.start()

        cmds.get_cmd('alpha')

        thread_pair.pair_with(remote_name='charlie')
        descs.paired('alpha', 'charlie')

        assert 'beta' not in ThreadPair._registry[thread_pair.group_name]

        cmds.queue_cmd('beta')

        beta_t3.join()

        descs.thread_end(name='charlie')

        # at this point, f1 has ended. But, the registry will not have changed,
        # so everything will still show paired, even both alpha and charlie
        # ThreadPairs. Alpha ThreadPair will detect that charlie is no longer
        # alive if a function is attempted.

        # change name in ThreadPair, then register a new entry to force the
        # ThreadPairErrorInRegistry error
        thread_pair.remote.name = 'bad_name'
        with pytest.raises(ThreadPairErrorInRegistry):
            _ = ThreadPair(group_name='group1', name='alpha2')

        # restore the good name to allow verify_registry to succeed
        thread_pair.remote.name = 'charlie'

        descs.verify_registry()

    ###########################################################################
    # test_thread_pair_pairing_with_multiple_threads
    ###########################################################################
    def test_thread_pair_pairing_with_multiple_threads(self) -> None:
        """Test register_thread during instantiation."""
        def f1(name: str) -> None:
            """Func to test instantiate ThreadPair.

            Args:
                name: name to use for t_pair
            """
            logger.debug(f'{name} f1 entered')
            t_pair = ThreadPair(group_name='group1', name=name)

            descs.add_desc(ThreadPairDesc(name=name,
                                          thread_pair=t_pair))

            # not OK to pair with self
            with pytest.raises(ThreadPairPairWithSelfNotAllowed):
                t_pair.pair_with(remote_name=name)

            cmds.queue_cmd('alpha', 'go')

            t_pair.pair_with(remote_name='alpha')
            descs.paired('alpha', 'beta')

            # alpha needs to wait until we are officially paired to avoid
            # timing issue when pairing with charlie
            cmds.queue_cmd('alpha')

            # not OK to pair with remote a second time
            with pytest.raises(ThreadPairAlreadyPairedWithRemote):
                t_pair.pair_with(remote_name='alpha')

            cmds.queue_cmd('alpha', 'go')

            cmds.get_cmd('beta')

            logger.debug(f'{name} f1 exiting')

        def f2(name: str) -> None:
            """Func to test instantiate ThreadPair.

            Args:
                name: name to use for t_pair
            """
            logger.debug(f'{name} f2 entered')
            t_pair = ThreadPair(group_name='group1', name=name)

            descs.add_desc(ThreadPairDesc(name=name,
                                          thread_pair=t_pair))

            # not OK to pair with self
            with pytest.raises(ThreadPairPairWithSelfNotAllowed):
                t_pair.pair_with(remote_name=name)

            with pytest.raises(ThreadPairPairWithTimedOut):
                t_pair.pair_with(remote_name='alpha', timeout=1)

            t_pair.pair_with(remote_name='alpha2')

            descs.paired('alpha2', 'charlie')

            # not OK to pair with remote a second time
            with pytest.raises(ThreadPairAlreadyPairedWithRemote):
                t_pair.pair_with(remote_name='alpha2')

            cmds.queue_cmd('alpha', 'go')

            cmds.get_cmd('charlie')

            logger.debug(f'{name} f2 exiting')

        #######################################################################
        # mainline
        #######################################################################
        descs = ThreadPairDescs()

        cmds = Cmds()

        beta_t = threading.Thread(target=f1, args=('beta',))
        charlie_t = threading.Thread(target=f2, args=('charlie',))

        thread_pair = ThreadPair(group_name='group1', name='alpha')

        descs.add_desc(ThreadPairDesc(name='alpha',
                                      thread_pair=thread_pair))

        beta_t.start()

        cmds.get_cmd('alpha')

        thread_pair.pair_with(remote_name='beta')

        #######################################################################
        # pair with charlie
        #######################################################################
        cmds.get_cmd('alpha')

        thread_pair2 = ThreadPair(group_name='group1', name='alpha2')

        descs.add_desc(ThreadPairDesc(name='alpha2',
                                      thread_pair=thread_pair2))

        charlie_t.start()

        thread_pair2.pair_with(remote_name='charlie')

        cmds.get_cmd('alpha')

        cmds.queue_cmd('beta')

        beta_t.join()

        descs.thread_end(name='beta')

        cmds.queue_cmd('charlie')

        charlie_t.join()

        descs.thread_end(name='charlie')

        # at this point, f1 and f2 have ended. But, the registry will not have
        # changed, so everything will still show paired, even all
        # ThreadPairs. Any ThreadPairs requests will detect that
        # their pairs are no longer active and will trigger cleanup to
        # remove any not alive entries from the registry. The ThreadPair
        # objects for not alive threads remain pointed to by the alive
        # entries so that they may still report ThreadPairRemoteThreadNotAlive.
        descs.verify_registry()

        # cause cleanup by calling cleanup directly
        thread_pair._clean_up_registry()

        descs.cleanup()

        # try to pair with old beta - should timeout
        with pytest.raises(ThreadPairPairWithTimedOut):
            thread_pair.pair_with(remote_name='beta', timeout=1)

        # the pair_with sets thread_pair.remote to none before trying the
        # pair_with, and leaves it None when pair_with fails
        descs.paired('alpha')

        # try to pair with old charlie - should timeout
        with pytest.raises(ThreadPairPairWithTimedOut):
            thread_pair.pair_with(remote_name='charlie', timeout=1)

        # try to pair with nobody - should timeout
        with pytest.raises(ThreadPairPairWithTimedOut):
            thread_pair.pair_with(remote_name='nobody', timeout=1)

        # try to pair with old beta - should timeout
        with pytest.raises(ThreadPairPairWithTimedOut):
            thread_pair2.pair_with(remote_name='beta', timeout=1)

        # the pair_with sets thread_pair.remote to none before trying the
        # pair_with, and leaves it None when pair_with fails
        descs.paired('alpha2')

        # try to pair with old charlie - should timeout
        with pytest.raises(ThreadPairPairWithTimedOut):
            thread_pair2.pair_with(remote_name='charlie', timeout=1)

        # try to pair with nobody - should timeout
        with pytest.raises(ThreadPairPairWithTimedOut):
            thread_pair2.pair_with(remote_name='nobody', timeout=1)

        descs.verify_registry()

    ###########################################################################
    # test_thread_pair_pairing_with_multiple_threads
    ###########################################################################
    def test_thread_pair_remote_pair_with_other_error(self) -> None:
        """Test pair_with error case."""
        def f1() -> None:
            """Func to test pair_with ThreadPair."""
            logger.debug('beta f1 entered')
            t_pair = ThreadPair(group_name='group1', name='beta')

            descs.add_desc(ThreadPairDesc(name='beta',
                                          thread_pair=t_pair))

            cmds.queue_cmd('alpha', 'go')
            with pytest.raises(ThreadPairRemotePairedWithOther):
                t_pair.pair_with(remote_name='alpha')

            cmds.get_cmd('beta')
            logger.debug(f'beta f1 exiting')

        def f2() -> None:
            """Func to test pair_with ThreadPair."""
            logger.debug('charlie f2 entered')
            t_pair = ThreadPair(group_name='group1', name='charlie')

            descs.add_desc(ThreadPairDesc(name='charlie',
                                          thread_pair=t_pair),
                           verify=False)

            cmds.queue_cmd('alpha', 'go')
            t_pair.pair_with(remote_name='alpha')
            descs.paired('alpha', 'charlie', verify=False)

            cmds.queue_cmd('alpha', 'go')

            cmds.get_cmd('charlie')

            logger.debug(f'charlie f2 exiting')

        #######################################################################
        # mainline
        #######################################################################
        descs = ThreadPairDescs()

        cmds = Cmds()

        beta_t = threading.Thread(target=f1)
        charlie_t = threading.Thread(target=f2)

        thread_pair = ThreadPair(group_name='group1', name='alpha')

        descs.add_desc(ThreadPairDesc(name='alpha',
                                      thread_pair=thread_pair))

        beta_t.start()

        cmds.get_cmd('alpha')

        beta_se = ThreadPair._registry[thread_pair.group_name]['beta']

        # make sure beta has alpha as target of pair_with
        while beta_se.remote is None:
            time.sleep(1)

        #######################################################################
        # pair with charlie
        #######################################################################
        charlie_t.start()

        cmds.get_cmd('alpha')

        thread_pair.pair_with(remote_name='charlie')

        cmds.get_cmd('alpha')

        cmds.queue_cmd('beta')

        # wait for beta to raise ThreadPairRemotePairedWithOther and end
        beta_t.join()

        descs.thread_end(name='beta')

        # sync up with charlie to allow charlie to exit
        cmds.queue_cmd('charlie')

        charlie_t.join()

        descs.thread_end(name='charlie')

        # cause cleanup by calling cleanup directly
        thread_pair._clean_up_registry()

        descs.cleanup()

    ###########################################################################
    # test_thread_pair_pairing_cleanup
    ###########################################################################
    def test_thread_pair_pairing_cleanup(self) -> None:
        """Test register_thread during instantiation."""
        def f1(name: str, remote_name: str, idx: int) -> None:
            """Func to test instantiate ThreadPair.

            Args:
                name: name to use for t_pair
                remote_name: name to pair with
                idx: index into beta_thread_pairs

            """
            logger.debug(f'{name} f1 entered, remote {remote_name}, idx {idx}')
            t_pair = ThreadPair(group_name='group1', name=name)

            descs.add_desc(ThreadPairDesc(name=name,
                                          thread_pair=t_pair))

            cmds.queue_cmd('alpha')

            t_pair.pair_with(remote_name=remote_name,
                             log_msg=f'f1 {name} pair with {remote_name} '
                                     f'for idx {idx}')

            cmds.queue_cmd('alpha')

            cmds.get_cmd(name)

            logger.debug(f'{name} f1 exiting')

        #######################################################################
        # mainline start
        #######################################################################
        cmds = Cmds()

        descs = ThreadPairDescs()

        #######################################################################
        # create 4 beta threads
        #######################################################################
        beta_t0 = threading.Thread(target=f1, args=('beta0', 'alpha0', 0))
        beta_t1 = threading.Thread(target=f1, args=('beta1', 'alpha1', 1))
        beta_t2 = threading.Thread(target=f1, args=('beta2', 'alpha2', 2))
        beta_t3 = threading.Thread(target=f1, args=('beta3', 'alpha3', 3))

        #######################################################################
        # create alpha0 ThreadPair and desc, and verify
        #######################################################################
        thread_pair0 = ThreadPair(group_name='group1', name='alpha0')
        descs.add_desc(ThreadPairDesc(name='alpha0',
                                      thread_pair=thread_pair0))

        #######################################################################
        # create alpha1 ThreadPair and desc, and verify
        #######################################################################
        thread_pair1 = ThreadPair(group_name='group1', name='alpha1')
        descs.add_desc(ThreadPairDesc(name='alpha1',
                                      thread_pair=thread_pair1))

        #######################################################################
        # create alpha2 ThreadPair and desc, and verify
        #######################################################################
        thread_pair2 = ThreadPair(group_name='group1', name='alpha2')
        descs.add_desc(ThreadPairDesc(name='alpha2',
                                      thread_pair=thread_pair2))

        #######################################################################
        # create alpha3 ThreadPair and desc, and verify
        #######################################################################
        thread_pair3 = ThreadPair(group_name='group1', name='alpha3')
        descs.add_desc(ThreadPairDesc(name='alpha3',
                                      thread_pair=thread_pair3))

        #######################################################################
        # start beta0 thread, and verify
        #######################################################################
        beta_t0.start()

        cmds.get_cmd('alpha')

        thread_pair0.pair_with(remote_name='beta0')

        cmds.get_cmd('alpha')
        descs.paired('alpha0', 'beta0')

        #######################################################################
        # start beta1 thread, and verify
        #######################################################################
        beta_t1.start()

        cmds.get_cmd('alpha')

        thread_pair1.pair_with(remote_name='beta1')

        cmds.get_cmd('alpha')
        descs.paired('alpha1', 'beta1')

        #######################################################################
        # start beta2 thread, and verify
        #######################################################################
        beta_t2.start()

        cmds.get_cmd('alpha')

        thread_pair2.pair_with(remote_name='beta2')

        cmds.get_cmd('alpha')
        descs.paired('alpha2', 'beta2')

        #######################################################################
        # start beta3 thread, and verify
        #######################################################################
        beta_t3.start()

        cmds.get_cmd('alpha')

        thread_pair3.pair_with(remote_name='beta3')

        cmds.get_cmd('alpha')
        descs.paired('alpha3', 'beta3')

        #######################################################################
        # let beta0 finish
        #######################################################################
        cmds.queue_cmd('beta0')

        beta_t0.join()

        descs.thread_end(name='beta0')

        #######################################################################
        # replace old beta0 w new beta0 - should cleanup registry old beta0
        #######################################################################
        beta_t0 = threading.Thread(target=f1, args=('beta0', 'alpha0', 0))

        beta_t0.start()

        cmds.get_cmd('alpha')

        thread_pair0.pair_with(remote_name='beta0')

        cmds.get_cmd('alpha')
        descs.paired('alpha0', 'beta0')

        #######################################################################
        # let beta1 and beta3 finish
        #######################################################################
        cmds.queue_cmd('beta1')
        beta_t1.join()
        descs.thread_end(name='beta1')

        cmds.queue_cmd('beta3')
        beta_t3.join()
        descs.thread_end(name='beta3')

        #######################################################################
        # replace old beta1 w new beta1 - should cleanup old beta1 and beta3
        #######################################################################
        beta_t1 = threading.Thread(target=f1, args=('beta1', 'alpha1', 1))

        beta_t1.start()

        cmds.get_cmd('alpha')

        thread_pair1.pair_with(remote_name='beta1')

        cmds.get_cmd('alpha')
        descs.paired('alpha1', 'beta1')

        # should get not alive for beta3
        with pytest.raises(ThreadPairRemoteThreadNotAlive):
            thread_pair3.check_remote()
        descs.cleanup()

        # should still be the same
        descs.verify_registry()

        #######################################################################
        # get a new beta3 going
        #######################################################################
        beta_t3 = threading.Thread(target=f1, args=('beta3', 'alpha3', 3))

        beta_t3.start()

        cmds.get_cmd('alpha')

        thread_pair3.pair_with(remote_name='beta3')

        cmds.get_cmd('alpha')
        descs.paired('alpha3', 'beta3')

        #######################################################################
        # let beta1 and beta2 finish
        #######################################################################
        cmds.queue_cmd('beta1')
        beta_t1.join()
        descs.thread_end(name='beta1')

        cmds.queue_cmd('beta2')
        beta_t2.join()
        descs.thread_end(name='beta2')

        #######################################################################
        # trigger cleanup for beta1 and beta2
        #######################################################################
        # should get not alive for beta1
        with pytest.raises(ThreadPairRemoteThreadNotAlive):
            thread_pair1.check_remote()
        descs.cleanup()

        descs.cleanup()

        #######################################################################
        # should get ThreadPairRemoteThreadNotAlive for beta1 and beta2
        #######################################################################
        with pytest.raises(ThreadPairRemoteThreadNotAlive):
            thread_pair1.check_remote()

        with pytest.raises(ThreadPairRemoteThreadNotAlive):
            thread_pair2.check_remote()

        descs.verify_registry()

        #######################################################################
        # get a new beta2 going and then allow to end
        #######################################################################
        beta_t2 = threading.Thread(target=f1, args=('beta2', 'alpha2', 2))

        beta_t2.start()

        cmds.get_cmd('alpha')

        thread_pair2.pair_with(remote_name='beta2')

        cmds.get_cmd('alpha')
        descs.paired('alpha2', 'beta2')

        cmds.queue_cmd('beta2')
        beta_t2.join()
        descs.thread_end(name='beta2')

        #######################################################################
        # let beta0 complete
        #######################################################################
        cmds.queue_cmd('beta0')
        beta_t0.join()
        descs.thread_end(name='beta0')

        #######################################################################
        # let beta3 complete
        #######################################################################
        cmds.queue_cmd('beta3')
        beta_t3.join()
        descs.thread_end(name='beta3')

    ###########################################################################
    # test_thread_pair_foreign_op_detection
    ###########################################################################
    def test_thread_pair_foreign_op_detection(self) -> None:
        """Test register_thread with f1."""
        #######################################################################
        # mainline and f1 - mainline pairs with beta
        #######################################################################
        logger.debug('start test 1')

        def f1():
            logger.debug('beta f1 entered')
            t_pair = ThreadPair(group_name='group1', name='beta')

            descs.add_desc(ThreadPairDesc(name='beta',
                                          thread_pair=t_pair))

            cmds.queue_cmd('alpha')
            my_c_thread = threading.current_thread()
            assert t_pair.thread is my_c_thread
            assert t_pair.thread is threading.current_thread()

            t_pair.pair_with(remote_name='alpha')

            cmds.get_cmd('beta')

            logger.debug('beta f1 exiting')

        def foreign1(t_pair):
            logger.debug('foreign1 entered')

            with pytest.raises(ThreadPairDetectedOpFromForeignThread):
                t_pair.verify_current_remote()

            logger.debug('foreign1 exiting')

        cmds = Cmds()
        descs = ThreadPairDescs()

        thread_pair1 = ThreadPair(group_name='group1', name='alpha')
        descs.add_desc(ThreadPairDesc(name='alpha',
                                      thread_pair=thread_pair1))

        alpha_t = threading.current_thread()
        my_f1_thread = threading.Thread(target=f1)
        my_foreign1_thread = threading.Thread(target=foreign1,
                                              args=(thread_pair1,))

        with pytest.raises(ThreadPairNotPaired):
            thread_pair1.check_remote()

        logger.debug('mainline about to start beta thread')

        my_f1_thread.start()

        cmds.get_cmd('alpha')

        thread_pair1.pair_with(remote_name='beta')
        descs.paired('alpha', 'beta')

        my_foreign1_thread.start()  # attempt to resume beta (should fail)

        my_foreign1_thread.join()

        cmds.queue_cmd('beta')  # tell beta to end

        my_f1_thread.join()
        descs.thread_end(name='beta')

        with pytest.raises(ThreadPairRemoteThreadNotAlive):
            thread_pair1.check_remote()
        descs.cleanup()

        assert thread_pair1.thread is alpha_t

        descs.verify_registry()

    ###########################################################################
    # test_thread_pair_outer_thread_f1
    ###########################################################################
    def test_thread_pair_outer_thread_f1(self) -> None:
        """Test simple sequence with outer thread f1."""
        #######################################################################
        # mainline
        #######################################################################
        logger.debug('mainline starting')

        cmds = Cmds()
        descs = ThreadPairDescs()

        thread_pair = ThreadPair(group_name='group1', name='alpha')
        descs.add_desc(ThreadPairDesc(name='alpha',
                                      thread_pair=thread_pair))

        f1_thread = threading.Thread(target=outer_f1, args=(cmds, descs))
        f1_thread.start()

        cmds.get_cmd('alpha')

        thread_pair.pair_with(remote_name='beta')
        descs.paired('alpha', 'beta')

        cmds.queue_cmd('beta')

        f1_thread.join()
        descs.thread_end(name='beta')

        logger.debug('mainline exiting')

    ###########################################################################
    # test_thread_pair_outer_thread_app
    ###########################################################################
    def test_thread_pair_outer_thread_app(self) -> None:
        """Test simple sequence with outer thread app."""
        #######################################################################
        # mainline
        #######################################################################
        logger.debug('mainline starting')
        cmds = Cmds()
        descs = ThreadPairDescs()

        thread_pair = ThreadPair(group_name='group1', name='alpha')
        descs.add_desc(ThreadPairDesc(name='alpha',
                                      thread_pair=thread_pair))

        thread_app = OuterThreadApp(cmds=cmds, descs=descs)

        thread_app.start()

        cmds.get_cmd('alpha')
        thread_pair.pair_with(remote_name='beta', timeout=3)

        cmds.queue_cmd('beta')

        thread_app.join()
        descs.thread_end(name='beta')

        logger.debug('mainline exiting')

    ###########################################################################
    # test_thread_pair_outer_thread_app
    ###########################################################################
    def test_thread_pair_outer_thread_event_app(self) -> None:
        """Test simple sequence with outer thread event app."""
        #######################################################################
        # mainline
        #######################################################################
        logger.debug('mainline starting')
        cmds = Cmds()
        descs = ThreadPairDescs()
        thread_pair = ThreadPair(group_name='group1', name='alpha')
        descs.add_desc(ThreadPairDesc(name='alpha',
                                      thread_pair=thread_pair))

        thread_event_app = OuterThreadEventApp(cmds=cmds, descs=descs)
        thread_event_app.start()

        cmds.get_cmd('alpha')

        thread_pair.pair_with(remote_name='beta', timeout=3)

        cmds.queue_cmd('beta')

        thread_event_app.join()

        descs.thread_end(name='beta')

        logger.debug('mainline exiting')

    ###########################################################################
    # test_thread_pair_inner_thread_app
    ###########################################################################
    def test_thread_pair_inner_thread_app(self) -> None:
        """Test ThreadPair with thread_app."""
        #######################################################################
        # ThreadApp
        #######################################################################
        class MyThread(threading.Thread):
            """MyThread class to test ThreadPair."""

            def __init__(self,
                         alpha_thread_pair: ThreadPair,
                         alpha_thread: threading.Thread
                         ) -> None:
                """Initialize the object.

                Args:
                    alpha_thread_pair: alpha ThreadPair to use for verification
                    alpha_thread: alpha thread to use for verification

                """
                super().__init__()
                self.t_pair = ThreadPair(group_name='group1', name='beta', thread=self)
                self.alpha_t_pair = alpha_thread_pair
                self.alpha_thread = alpha_thread

            def run(self):
                """Run the tests."""
                logger.debug('run started')

                # normally, the add_desc is done just after the
                # instantiation, but
                # in this case the thread is not made alive until now, and the
                # add_desc checks that the thread is alive
                descs.add_desc(ThreadPairDesc(name='beta',
                                              thread_pair=self.t_pair,
                                              thread=self))

                cmds.queue_cmd('alpha')
                self.t_pair.pair_with(remote_name='alpha')
                descs.paired('alpha', 'beta')

                assert self.t_pair.remote is self.alpha_t_pair
                assert (self.t_pair.remote.thread
                        is self.alpha_thread)
                assert self.t_pair.remote.thread is alpha_t
                assert self.t_pair.thread is self
                my_run_thread = threading.current_thread()
                assert self.t_pair.thread is my_run_thread
                assert self.t_pair.thread is threading.current_thread()

                cmds.get_cmd('beta')
                logger.debug('beta run exiting 45')

        #######################################################################
        # mainline starts
        #######################################################################
        cmds = Cmds()
        descs = ThreadPairDescs()
        alpha_t = threading.current_thread()
        thread_pair1 = ThreadPair(group_name='group1', name='alpha')
        descs.add_desc(ThreadPairDesc(name='alpha',
                                      thread_pair=thread_pair1))

        my_taa_thread = MyThread(thread_pair1, alpha_t)

        my_taa_thread.start()

        cmds.get_cmd('alpha')

        thread_pair1.pair_with(remote_name='beta')

        cmds.queue_cmd('beta')

        my_taa_thread.join()
        descs.thread_end('beta')

        with pytest.raises(ThreadPairRemoteThreadNotAlive):
            thread_pair1.check_remote()
        descs.cleanup()

        with pytest.raises(ThreadPairPairWithTimedOut):
            thread_pair1.pair_with(remote_name='beta', timeout=1)
        descs.paired('alpha')

        with pytest.raises(ThreadPairNotPaired):
            thread_pair1.check_remote()

        assert thread_pair1.thread is alpha_t
        assert thread_pair1.remote is None

        descs.verify_registry()

    ###########################################################################
    # test_thread_pair_inner_thread_event_app
    ###########################################################################
    def test_thread_pair_inner_thread_event_app(self) -> None:
        """Test ThreadPair with thread_event_app."""
        #######################################################################
        # mainline and ThreadEventApp - mainline sets alpha and beta
        #######################################################################
        class MyThreadEvent1(threading.Thread, ThreadPair):
            def __init__(self,
                         alpha_t1: threading.Thread):
                threading.Thread.__init__(self)
                ThreadPair.__init__(self, group_name='group1', name='beta', thread=self)
                self.alpha_t1 = alpha_t1

            def run(self):
                logger.debug('run started')
                # normally, the add_desc is done just after the
                # instantiation, but
                # in this case the thread is not made alive until now, and the
                # add_desc checks that the thread is alive
                descs.add_desc(ThreadPairDesc(name='beta',
                                              thread_pair=self,
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

                cmds.get_cmd('beta')
                logger.debug('run exiting')

        cmds = Cmds()
        descs = ThreadPairDescs()
        alpha_t = threading.current_thread()

        my_te1_thread = MyThreadEvent1(alpha_t)
        with pytest.raises(ThreadPairDetectedOpFromForeignThread):
            my_te1_thread.verify_current_remote()

        with pytest.raises(ThreadPairDetectedOpFromForeignThread):
            my_te1_thread.pair_with(remote_name='alpha', timeout=0.5)

        assert my_te1_thread.remote is None
        assert my_te1_thread.thread is my_te1_thread

        my_te1_thread.start()

        cmds.get_cmd('alpha')
        thread_pair = ThreadPair(group_name='group1', name='alpha')
        descs.add_desc(ThreadPairDesc(name='alpha',
                                      thread_pair=thread_pair))

        with pytest.raises(ThreadPairNotPaired):
            thread_pair.verify_current_remote()

        thread_pair.pair_with(remote_name='beta')

        cmds.queue_cmd('beta')

        my_te1_thread.join()
        descs.thread_end('beta')

        with pytest.raises(ThreadPairRemoteThreadNotAlive):
            thread_pair.check_remote()
        descs.cleanup()

        assert my_te1_thread.remote is not None
        assert my_te1_thread.remote.thread is not None
        assert my_te1_thread.remote.thread is alpha_t
        assert my_te1_thread.thread is my_te1_thread

    ###########################################################################
    # test_thread_pair_two_f_threads
    ###########################################################################
    def test_thread_pair_two_f_threads(self) -> None:
        """Test register_thread with thread_event_app."""
        #######################################################################
        # two threads - mainline sets alpha and beta
        #######################################################################
        def fa1():
            logger.debug('fa1 entered')
            my_fa_thread = threading.current_thread()
            t_pair = ThreadPair(group_name='group1', name='fa1')
            descs.add_desc(ThreadPairDesc(name='fa1',
                                          thread_pair=t_pair,
                                          thread=my_fa_thread))

            assert t_pair.thread is my_fa_thread

            t_pair.pair_with(remote_name='fb1')
            descs.paired('fa1', 'fb1')

            logger.debug('fa1 about to wait')
            cmds.get_cmd('fa1')
            logger.debug('fa1 exiting')

        def fb1():
            logger.debug('fb1 entered')
            my_fb_thread = threading.current_thread()
            t_pair = ThreadPair(group_name='group1', name='fb1')
            descs.add_desc(ThreadPairDesc(name='fb1',
                                          thread_pair=t_pair,
                                          thread=my_fb_thread))

            assert t_pair.thread is my_fb_thread

            t_pair.pair_with(remote_name='fa1')

            logger.debug('fb1 about to resume')
            cmds.queue_cmd('fa1')

            # tell mainline we are out of the wait - OK to do descs fa1 end
            cmds.queue_cmd('alpha')

            # wait for mainline to give to go ahead after doing descs fa1 end
            cmds.get_cmd('beta')

            with pytest.raises(ThreadPairRemoteThreadNotAlive):
                t_pair.check_remote()

            descs.cleanup()

        #######################################################################
        # mainline
        #######################################################################
        cmds = Cmds()
        descs = ThreadPairDescs()
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


###############################################################################
# TestTheta Class
###############################################################################
class TestTheta:
    """Test ThreadPair with two classes."""
    ###########################################################################
    # test_thread_pair_theta
    ###########################################################################
    def test_thread_pair_theta(self) -> None:
        """Test theta class."""

        def f1():
            logger.debug('f1 beta entered')
            f1_theta = Theta(group_name='group1', name='beta')
            descs.add_desc(ThetaDesc(name='beta',
                                     theta=f1_theta,
                                     thread=threading.current_thread()))

            cmds.queue_cmd('alpha')

            f1_theta.pair_with(remote_name='alpha')
            descs.paired('alpha', 'beta')

            cmds.queue_cmd('alpha', 'go')
            cmds.get_cmd('beta')

            assert f1_theta.var1 == 999

            f1_theta.var1 = 'theta'  # restore to init value to allow verify to work

            logger.debug('f1 beta exiting 5')

        logger.debug('mainline entered')
        cmds = Cmds()
        descs = ThreadPairDescs()
        ml_theta = Theta(group_name='group1', name='alpha')
        descs.add_desc(ThetaDesc(name='alpha',
                                 theta=ml_theta,
                                 thread=threading.current_thread()))

        f1_thread = threading.Thread(target=f1)

        f1_thread.start()

        cmds.get_cmd('alpha')
        ml_theta.pair_with(remote_name='beta')

        cmds.get_cmd('alpha')

        ml_theta.remote.var1 = 999

        cmds.queue_cmd('beta', 'go')

        f1_thread.join()
        descs.thread_end('beta')

        with pytest.raises(ThreadPairRemoteThreadNotAlive):
            ml_theta.check_remote()

        descs.cleanup()

        logger.debug('mainline exiting')


###############################################################################
# TestSigma Class
###############################################################################
class TestSigma:
    """Test ThreadPair with two classes."""
    ###########################################################################
    # test_thread_pair_sigma
    ###########################################################################
    def test_thread_pair_sigma(self) -> None:
        """Test sigma class."""

        def f1():
            logger.debug('f1 beta entered')
            f1_sigma = Sigma(group_name='group1', name='beta')
            descs.add_desc(SigmaDesc(name='beta',
                                     sigma=f1_sigma,
                                     thread=threading.current_thread()))

            cmds.queue_cmd('alpha')

            f1_sigma.pair_with(remote_name='alpha')
            descs.paired('alpha', 'beta')

            cmds.queue_cmd('alpha', 'go')
            cmds.get_cmd('beta')

            assert f1_sigma.var1 == 999
            assert f1_sigma.remote.var1 == 17

            assert f1_sigma.var2 == 'sigma'
            assert f1_sigma.remote.var2 == 'sigma'

            f1_sigma.var1 = 17  # restore to init value to allow verify to work
            f1_sigma.remote.var2 = 'test1'

            logger.debug('f1 beta exiting 5')

        logger.debug('mainline entered')
        cmds = Cmds()
        descs = ThreadPairDescs()
        ml_sigma = Sigma(group_name='group1', name='alpha')
        descs.add_desc(SigmaDesc(name='alpha',
                                 sigma=ml_sigma,
                                 thread=threading.current_thread()))

        f1_thread = threading.Thread(target=f1)

        f1_thread.start()

        cmds.get_cmd('alpha')
        ml_sigma.pair_with(remote_name='beta')

        cmds.get_cmd('alpha')

        ml_sigma.remote.var1 = 999

        cmds.queue_cmd('beta', 'go')

        f1_thread.join()

        assert ml_sigma.var2 == 'test1'
        ml_sigma.var2 = 'sigma'  # restore for verify

        descs.thread_end('beta')

        with pytest.raises(ThreadPairRemoteThreadNotAlive):
            ml_sigma.check_remote()

        descs.cleanup()

        logger.debug('mainline exiting')


###############################################################################
# TestOmega Class
###############################################################################
class TestOmega:
    """Test ThreadPair with two classes."""
    ###########################################################################
    # test_thread_pair_omega
    ###########################################################################
    def test_thread_pair_omega(self) -> None:
        """Test omega class."""

        def f1():
            logger.debug('f1 beta entered')
            f1_omega = Omega(group_name='group1', name='beta')
            descs.add_desc(OmegaDesc(name='beta',
                                     omega=f1_omega,
                                     thread=threading.current_thread()))

            cmds.queue_cmd('alpha')

            f1_omega.pair_with(remote_name='alpha')
            descs.paired('alpha', 'beta')

            cmds.queue_cmd('alpha', 'go')
            cmds.get_cmd('beta')

            assert f1_omega.var1 == 999
            assert f1_omega.remote.var1 == 42

            assert f1_omega.var2 == 64.9
            assert f1_omega.remote.var2 == 64.9

            assert f1_omega.var3 == 'omega'
            assert f1_omega.remote.var3 == 'omega'

            f1_omega.var1 = 42  # restore to init value to allow verify to work
            f1_omega.remote.var2 = 'test_omega'

            logger.debug('f1 beta exiting 5')

        logger.debug('mainline entered')
        cmds = Cmds()
        descs = ThreadPairDescs()
        ml_omega = Omega(group_name='group1', name='alpha')
        descs.add_desc(OmegaDesc(name='alpha',
                                 omega=ml_omega,
                                 thread=threading.current_thread()))

        f1_thread = threading.Thread(target=f1)

        f1_thread.start()

        cmds.get_cmd('alpha')
        ml_omega.pair_with(remote_name='beta')

        cmds.get_cmd('alpha')

        ml_omega.remote.var1 = 999

        cmds.queue_cmd('beta', 'go')

        f1_thread.join()

        assert ml_omega.var2 == 'test_omega'
        ml_omega.var2 = 64.9  # restore for verify

        descs.thread_end('beta')

        with pytest.raises(ThreadPairRemoteThreadNotAlive):
            ml_omega.check_remote()

        descs.cleanup()

        logger.debug('mainline exiting')


###############################################################################
# TestThetaSigma Class
###############################################################################
class TestThetaSigma:
    """Test ThreadPair with two classes."""
    ###########################################################################
    # test_thread_pair_theta_sigma
    ###########################################################################
    def test_thread_pair_theta_sigma_unique_names(self) -> None:
        """Test theta and sigma."""

        def f1():
            logger.debug('f1 beta entered')
            f1_theta = Theta(group_name='group1', name='beta_theta')
            theta_descs.add_desc(ThetaDesc(name='beta_theta',
                                           theta=f1_theta,
                                           thread=threading.current_thread()))

            f1_sigma = Sigma(group_name='group1', name='beta_sigma')
            sigma_descs.add_desc(SigmaDesc(name='beta_sigma',
                                           sigma=f1_sigma,
                                           thread=threading.current_thread()))

            cmds.queue_cmd('alpha')

            f1_theta.pair_with(remote_name='alpha_theta')
            theta_descs.paired('alpha_theta', 'beta_theta')

            f1_sigma.pair_with(remote_name='alpha_sigma')
            sigma_descs.paired('alpha_sigma', 'beta_sigma')

            cmds.queue_cmd('alpha', 'go')
            cmds.get_cmd('beta')

            assert f1_theta.var1 == 999
            assert f1_theta.remote.var1 == 'theta'

            assert f1_sigma.var1 == 999
            assert f1_sigma.remote.var1 == 17

            assert f1_sigma.var2 == 'sigma'
            assert f1_sigma.remote.var2 == 'sigma'

            f1_theta.var1 = 'theta'  # restore to init value for verify
            f1_theta.remote.var2 = 'test_theta'

            f1_sigma.var1 = 17  # restore to init value to allow verify to work
            f1_sigma.remote.var2 = 'test1'

            logger.debug('f1 beta exiting')

        logger.debug('mainline entered')
        cmds = Cmds()
        theta_descs = ThreadPairDescs()
        sigma_descs = ThreadPairDescs()

        ml_theta = Theta(group_name='group1', name='alpha_theta')

        theta_descs.add_desc(ThetaDesc(name='alpha_theta',
                                       theta=ml_theta,
                                       thread=threading.current_thread()))

        ml_sigma = Sigma(group_name='group1', name='alpha_sigma')
        sigma_descs.add_desc(SigmaDesc(name='alpha_sigma',
                                       sigma=ml_sigma,
                                       thread=threading.current_thread()))

        f1_thread = threading.Thread(target=f1)

        f1_thread.start()

        cmds.get_cmd('alpha')
        ml_theta.pair_with(remote_name='beta_theta')
        ml_sigma.pair_with(remote_name='beta_sigma')

        cmds.get_cmd('alpha')

        ml_theta.remote.var1 = 999
        ml_sigma.remote.var1 = 999

        cmds.queue_cmd('beta', 'go')

        f1_thread.join()

        assert ml_theta.var2 == 'test_theta'
        ml_theta.var2 = 'theta'  # restore for verify

        assert ml_sigma.var2 == 'test1'
        ml_sigma.var2 = 'sigma'  # restore for verify

        theta_descs.thread_end('beta_theta')
        sigma_descs.thread_end('beta_sigma')

        with pytest.raises(ThreadPairRemoteThreadNotAlive):
            ml_theta.check_remote()

        with pytest.raises(ThreadPairRemoteThreadNotAlive):
            ml_sigma.check_remote()

        theta_descs.cleanup()
        sigma_descs.cleanup()

        logger.debug('mainline exiting')

    ###########################################################################
    # test_thread_pair_theta_sigma
    ###########################################################################
    def test_thread_pair_theta_sigma_same_names(self) -> None:
        """Test theta and sigma."""

        def f1():
            logger.debug('f1 beta entered')
            f1_theta = Theta(group_name='group1', name='beta')
            theta_descs.add_desc(ThetaDesc(name='beta',
                                           theta=f1_theta,
                                           thread=threading.current_thread()))

            f1_sigma = Sigma(group_name='group1', name='beta')
            sigma_descs.add_desc(SigmaDesc(name='beta',
                                           sigma=f1_sigma,
                                           thread=threading.current_thread()))

            cmds.queue_cmd('alpha')

            f1_theta.pair_with(remote_name='alpha')
            theta_descs.paired('alpha', 'beta')

            f1_sigma.pair_with(remote_name='alpha')
            sigma_descs.paired('alpha', 'beta')

            cmds.queue_cmd('alpha', 'go')
            cmds.get_cmd('beta')

            assert f1_theta.var1 == 999
            assert f1_theta.remote.var1 == 'theta'

            assert f1_sigma.var1 == 999
            assert f1_sigma.remote.var1 == 17

            assert f1_sigma.var2 == 'sigma'
            assert f1_sigma.remote.var2 == 'sigma'

            f1_theta.var1 = 'theta'  # restore to init value for verify
            f1_theta.remote.var2 = 'test_theta'

            f1_sigma.var1 = 17  # restore to init value to allow verify to work
            f1_sigma.remote.var2 = 'test1'

            logger.debug('f1 beta exiting')

        logger.debug('mainline entered')
        cmds = Cmds()
        theta_descs = ThreadPairDescs()
        sigma_descs = ThreadPairDescs()

        ml_theta = Theta(group_name='group1', name='alpha')

        theta_descs.add_desc(ThetaDesc(name='alpha',
                                       theta=ml_theta,
                                       thread=threading.current_thread()))

        ml_sigma = Sigma(group_name='group1', name='alpha')
        sigma_descs.add_desc(SigmaDesc(name='alpha',
                                       sigma=ml_sigma,
                                       thread=threading.current_thread()))

        f1_thread = threading.Thread(target=f1)

        f1_thread.start()

        cmds.get_cmd('alpha')
        ml_theta.pair_with(remote_name='beta')
        ml_sigma.pair_with(remote_name='beta')

        cmds.get_cmd('alpha')

        ml_theta.remote.var1 = 999
        ml_sigma.remote.var1 = 999

        cmds.queue_cmd('beta', 'go')

        f1_thread.join()

        assert ml_theta.var2 == 'test_theta'
        ml_theta.var2 = 'theta'  # restore for verify

        assert ml_sigma.var2 == 'test1'
        ml_sigma.var2 = 'sigma'  # restore for verify

        theta_descs.thread_end('beta')
        sigma_descs.thread_end('beta')

        with pytest.raises(ThreadPairRemoteThreadNotAlive):
            ml_theta.check_remote()

        with pytest.raises(ThreadPairRemoteThreadNotAlive):
            ml_sigma.check_remote()

        theta_descs.cleanup()
        sigma_descs.cleanup()

        logger.debug('mainline exiting')


###############################################################################
# TestThreadPairLogger Class
###############################################################################
class TestThreadPairLogger:
    """Test log messages."""
    ###########################################################################
    # test_thread_pair_f1_event_logger
    ###########################################################################
    def test_thread_pair_f1_event_logger(self,
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

            t_pair = ThreadPair(group_name='group1', name='beta')
            descs.add_desc(ThreadPairDesc(name='beta',
                                          thread_pair=t_pair,
                                          thread=threading.current_thread()))
            cmds.queue_cmd('alpha')

            exp_log_msgs.add_beta_pair_with_msg('beta pair_with alpha 1',
                                                ['beta', 'alpha'])
            t_pair.pair_with(remote_name='alpha',
                              log_msg='beta pair_with alpha 1')

            descs.paired('alpha', 'beta')

            exp_log_msgs.add_beta_sync_msg('beta sync point 1')
            t_pair.sync(log_msg='beta sync point 1')

            exp_log_msgs.add_beta_wait_msg('wait for mainline to post 12')
            assert t_pair.wait(log_msg='wait for mainline to post 12')

            exp_log_msgs.add_beta_sync_msg('beta sync point 2')
            t_pair.sync(log_msg='beta sync point 2')

            exp_log_msgs.add_beta_resume_msg('post mainline 23')
            t_pair.resume(log_msg='post mainline 23')

            exp_log_msgs.add_beta_sync_msg('beta sync point 3')
            t_pair.sync(log_msg='beta sync point 3')

            exp_log_msgs.add_beta_sync_msg('beta sync point 4')
            t_pair.sync(log_msg='beta sync point 4')

        cmds = Cmds()
        descs = ThreadPairDescs()
        if log_enabled_arg:
            logging.getLogger().setLevel(logging.DEBUG)
        else:
            logging.getLogger().setLevel(logging.INFO)

        alpha_call_seq = ('test_thread_pair.py::TestThreadPairLogger.'
                          'test_thread_pair_f1_event_logger')
        beta_call_seq = ('test_thread_pair.py::f1')
        exp_log_msgs = ExpLogMsgs(alpha_call_seq, beta_call_seq)
        l_msg = 'mainline started'
        exp_log_msgs.add_msg(l_msg)
        logger.debug(l_msg)

        thread_pair = ThreadPair(group_name='group1', name='alpha')
        descs.add_desc(ThreadPairDesc(name='alpha',
                                      thread_pair=thread_pair,
                                      thread=threading.current_thread()))

        beta_thread = threading.Thread(target=f1)

        beta_thread.start()

        cmds.get_cmd('alpha')
        exp_log_msgs.add_alpha_pair_with_msg('alpha pair_with beta 1',
                                             ['alpha', 'beta'])
        thread_pair.pair_with(remote_name='beta',
                              log_msg='alpha pair_with beta 1')

        exp_log_msgs.add_alpha_sync_msg('mainline sync point 1')
        thread_pair.sync(log_msg='mainline sync point 1')
        thread_pair.pause_until(WUCond.RemoteWaiting)

        exp_log_msgs.add_alpha_resume_msg('post beta 12')
        thread_pair.resume(log_msg='post beta 12')

        exp_log_msgs.add_alpha_sync_msg('mainline sync point 2')
        thread_pair.sync(log_msg='mainline sync point 2')

        exp_log_msgs.add_alpha_sync_msg('mainline sync point 3')
        thread_pair.sync(log_msg='mainline sync point 3')

        exp_log_msgs.add_alpha_wait_msg('wait for pre-post 23')
        assert thread_pair.wait(log_msg='wait for pre-post 23')

        exp_log_msgs.add_alpha_sync_msg('mainline sync point 4')
        thread_pair.sync(log_msg='mainline sync point 4')

        beta_thread.join()
        descs.thread_end('beta')

        exp_log_msgs.add_msg('mainline all tests complete')
        logger.debug('mainline all tests complete')

        exp_log_msgs.verify_log_msgs(caplog=caplog,
                                     log_enabled_tf=log_enabled_arg)

        # restore root to debug
        logging.getLogger().setLevel(logging.DEBUG)

    ###########################################################################
    # test_thread_pair_thread_app_event_logger
    ###########################################################################
    def test_thread_pair_thread_app_event_logger(self,
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
                self.t_pair = ThreadPair(group_name='group1', name='beta', thread=self)
                self.exp_log_msgs = exp_log_msgs1

            def run(self):
                l_msg = 'ThreadApp run entered'
                self.exp_log_msgs.add_msg(l_msg)
                logger.debug(l_msg)

                descs.add_desc(ThreadPairDesc(name='beta',
                                              thread_pair=self.t_pair,
                                              thread=self))
                cmds.queue_cmd('alpha')

                self.exp_log_msgs.add_beta_pair_with_msg('beta pair alpha 2',
                                                         ['beta', 'alpha'])
                self.t_pair.pair_with(remote_name='alpha',
                                       log_msg='beta pair alpha 2')

                self.exp_log_msgs.add_beta_sync_msg('beta sync point 1')
                self.t_pair.sync(log_msg='beta sync point 1')

                self.exp_log_msgs.add_beta_wait_msg('wait 12')
                assert self.t_pair.wait(log_msg='wait 12')

                self.exp_log_msgs.add_beta_sync_msg('beta sync point 2')
                self.t_pair.sync(log_msg='beta sync point 2')

                self.t_pair.pause_until(WUCond.RemoteWaiting)

                self.exp_log_msgs.add_beta_resume_msg('post mainline 34',
                                                      True, 'forty-two')
                self.t_pair.resume(code='forty-two',
                                    log_msg='post mainline 34')

                self.exp_log_msgs.add_beta_sync_msg('beta sync point 3')
                self.t_pair.sync(log_msg='beta sync point 3')

                self.exp_log_msgs.add_beta_sync_msg('beta sync point 4')
                self.t_pair.sync(log_msg='beta sync point 4')

        cmds = Cmds()
        descs = ThreadPairDescs()
        if log_enabled_arg:
            logging.getLogger().setLevel(logging.DEBUG)
        else:
            logging.getLogger().setLevel(logging.INFO)

        alpha_call_seq = ('test_thread_pair.py::TestThreadPairLogger.'
                          'test_thread_pair_thread_app_event_logger')

        beta_call_seq = 'test_thread_pair.py::MyThread.run'
        exp_log_msgs = ExpLogMsgs(alpha_call_seq, beta_call_seq)
        l_msg = 'mainline starting'
        exp_log_msgs.add_msg(l_msg)
        logger.debug(l_msg)

        thread_pair = ThreadPair(group_name='group1', name='alpha')
        descs.add_desc(ThreadPairDesc(name='alpha',
                                      thread_pair=thread_pair,
                                      thread=threading.current_thread()))

        thread_app = MyThread(exp_log_msgs)
        thread_app.start()

        cmds.get_cmd('alpha')
        exp_log_msgs.add_alpha_pair_with_msg('alpha pair beta 2',
                                             ['alpha', 'beta'])
        thread_pair.pair_with(remote_name='beta',
                              log_msg='alpha pair beta 2')
        descs.paired('alpha', 'beta')

        exp_log_msgs.add_alpha_sync_msg('mainline sync point 1')
        thread_pair.sync(log_msg='mainline sync point 1')

        thread_pair.pause_until(WUCond.RemoteWaiting)

        exp_log_msgs.add_alpha_resume_msg(
            f'post thread {thread_pair.remote.name} 23', True, 42)
        thread_pair.resume(log_msg=f'post thread {thread_pair.remote.name} 23',
                           code=42)

        exp_log_msgs.add_alpha_sync_msg('mainline sync point 2')
        thread_pair.sync(log_msg='mainline sync point 2')

        exp_log_msgs.add_alpha_wait_msg('wait for post from thread 34')
        assert thread_pair.wait(log_msg='wait for post from thread 34')

        exp_log_msgs.add_alpha_sync_msg('mainline sync point 3')
        thread_pair.sync(log_msg='mainline sync point 3')
        exp_log_msgs.add_alpha_sync_msg('mainline sync point 4')
        thread_pair.sync(log_msg='mainline sync point 4')

        thread_app.join()

        thread_pair.code = None
        thread_pair.remote.code = None

        descs.thread_end('beta')

        l_msg = 'mainline all tests complete'
        exp_log_msgs.add_msg(l_msg)
        logger.debug('mainline all tests complete')

        exp_log_msgs.verify_log_msgs(caplog=caplog,
                                     log_enabled_tf=log_enabled_arg)

        # restore root to debug
        logging.getLogger().setLevel(logging.DEBUG)

    ###########################################################################
    # test_thread_pair_thread_event_app_event_logger
    ###########################################################################
    def test_thread_pair_thread_event_app_event_logger(self,
                                                       caplog,
                                                       log_enabled_arg
                                                       ) -> None:
        """Test smart event logger with thread_event_app thread.

        Args:
            caplog: fixture to capture log messages
            log_enabled_arg: fixture to indicate whether log is enabled

        """
        class MyThread(threading.Thread, ThreadPair):
            def __init__(self,
                         exp_log_msgs1: ExpLogMsgs):
                threading.Thread.__init__(self)
                ThreadPair.__init__(self, group_name='group1', name='beta', thread=self)
                self.exp_log_msgs = exp_log_msgs1

            def run(self):
                self.exp_log_msgs.add_msg('ThreadApp run entered')
                logger.debug('ThreadApp run entered')

                descs.add_desc(ThreadPairDesc(name='beta',
                                              thread_pair=self,
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
        descs = ThreadPairDescs()
        if log_enabled_arg:
            logging.getLogger().setLevel(logging.DEBUG)
        else:
            logging.getLogger().setLevel(logging.INFO)

        alpha_call_seq = ('test_thread_pair.py::TestThreadPairLogger.'
                          'test_thread_pair_thread_event_app_event_logger')

        beta_call_seq = 'test_thread_pair.py::MyThread.run'
        exp_log_msgs = ExpLogMsgs(alpha_call_seq, beta_call_seq)
        l_msg = 'mainline starting'
        exp_log_msgs.add_msg(l_msg)
        logger.debug(l_msg)

        thread_pair = ThreadPair(group_name='group1', name='alpha')
        descs.add_desc(ThreadPairDesc(name='alpha',
                                      thread_pair=thread_pair,
                                      thread=threading.current_thread()))

        thread_event_app = MyThread(exp_log_msgs1=exp_log_msgs)

        thread_event_app.start()

        cmds.get_cmd('alpha')

        exp_log_msgs.add_alpha_pair_with_msg('alpha to beta 3',
                                             ['alpha', 'beta'])
        thread_pair.pair_with(remote_name='beta',
                              log_msg='alpha to beta 3')

        exp_log_msgs.add_alpha_sync_msg('mainline sync point 1')
        thread_pair.sync(log_msg='mainline sync point 1')

        thread_pair.pause_until(WUCond.RemoteWaiting)

        exp_log_msgs.add_alpha_resume_msg(
            f'post thread {thread_event_app.name} 12')
        thread_pair.resume(log_msg=f'post thread '
                           f'{thread_event_app.name} 12')

        exp_log_msgs.add_alpha_sync_msg('mainline sync point 2')
        thread_pair.sync(log_msg='mainline sync point 2')

        exp_log_msgs.add_alpha_wait_msg('wait for post from thread 23')
        assert thread_pair.wait(log_msg='wait for post from thread 23')

        exp_log_msgs.add_alpha_sync_msg('mainline sync point 3')
        thread_pair.sync(log_msg='mainline sync point 3')

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
    """Test various combinations of ThreadPair."""
    ###########################################################################
    # test_thread_pair_thread_f1_combos
    ###########################################################################
    def test_thread_pair_f1_combos(self,
                                   action_arg1: Any,
                                   code_arg1: Any,
                                   log_msg_arg1: Any,
                                   action_arg2: Any,
                                   caplog: Any,
                                   thread_exc: Any) -> None:
        """Test the ThreadPair with f1 combos.

        Args:
            action_arg1: first action
            code_arg1: whether to set and recv a code
            log_msg_arg1: whether to specify a log message
            action_arg2: second action
            caplog: fixture to capture log messages
            thread_exc: intercepts thread exceptions

        """
        alpha_call_seq = ('test_thread_pair.py::TestCombos.action_loop')
        beta_call_seq = ('test_thread_pair.py::thread_func1')
        exp_log_msgs = ExpLogMsgs(alpha_call_seq, beta_call_seq)
        l_msg = 'mainline entered'
        exp_log_msgs.add_msg(l_msg)
        logger.debug(l_msg)

        cmds = Cmds()
        descs = ThreadPairDescs()

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
    # test_thread_pair_thread_f1_combos
    ###########################################################################
    def test_thread_pair_f1_f2_combos(self,
                                      action_arg1: Any,
                                      code_arg1: Any,
                                      log_msg_arg1: Any,
                                      action_arg2: Any,
                                      caplog: Any,
                                      thread_exc: Any) -> None:
        """Test the ThreadPair with f1 anf f2 combos.

        Args:
            action_arg1: first action
            code_arg1: whether to set and recv a code
            log_msg_arg1: whether to specify a log message
            action_arg2: second action
            caplog: fixture to capture log messages
            thread_exc: intercepts thread exceptions

        """
        alpha_call_seq = ('test_thread_pair.py::TestCombos.action_loop')
        beta_call_seq = ('test_thread_pair.py::thread_func1')
        exp_log_msgs = ExpLogMsgs(alpha_call_seq, beta_call_seq)
        l_msg = 'mainline entered'
        exp_log_msgs.add_msg(l_msg)
        logger.debug(l_msg)

        cmds = Cmds()
        descs = ThreadPairDescs()

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
                                           descs,
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
    # test_thread_pair_thread_thread_app_combos
    ###########################################################################
    def test_thread_pair_thread_app_combos(self,
                                           action_arg1: Any,
                                           code_arg1: Any,
                                           log_msg_arg1: Any,
                                           action_arg2: Any,
                                           caplog: Any,
                                           thread_exc: Any) -> None:
        """Test the ThreadPair with ThreadApp combos.

        Args:
            action_arg1: first action
            code_arg1: whether to set and recv a code
            log_msg_arg1: whether to specify a log message
            action_arg2: second action
            caplog: fixture to capture log messages
            thread_exc: intercepts thread exceptions

        """
        class ThreadPairApp(threading.Thread):
            """ThreadPairApp class with thread."""
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
                self.thread_pair = ThreadPair(group_name='group1', name='beta', thread=self)
                self.cmds = cmds
                self.exp_log_msgs = exp_log_msgs

            def run(self):
                """Thread to send and receive messages."""
                l_msg = 'ThreadPairApp run started'
                self.exp_log_msgs.add_msg(l_msg)
                logger.debug(l_msg)
                thread_func1(
                    cmds=self.cmds,
                    descs=descs,
                    exp_log_msgs=self.exp_log_msgs,
                    thread_pair=self.thread_pair)

                l_msg = 'ThreadPairApp run exiting'
                self.exp_log_msgs.add_msg(l_msg)
                logger.debug(l_msg)

        alpha_call_seq = ('test_thread_pair.py::TestCombos.action_loop')
        beta_call_seq = ('test_thread_pair.py::thread_func1')
        exp_log_msgs = ExpLogMsgs(alpha_call_seq, beta_call_seq)
        l_msg = 'mainline entered'
        exp_log_msgs.add_msg(l_msg)
        logger.debug(l_msg)

        cmds = Cmds()
        descs = ThreadPairDescs()

        cmds.l_msg = log_msg_arg1
        cmds.r_code = code_arg1

        f1_thread = ThreadPairApp(cmds,
                                  exp_log_msgs)

        l_msg = 'mainline about to start ThreadPairApp'
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
    # test_thread_pair_thread_thread_app_combos
    ###########################################################################
    def test_thread_pair_thread_event_app_combos(self,
                                                 action_arg1: Any,
                                                 code_arg1: Any,
                                                 log_msg_arg1: Any,
                                                 action_arg2: Any,
                                                 caplog: Any,
                                                 thread_exc: Any) -> None:
        """Test the ThreadPair with ThreadApp combos.

        Args:
            action_arg1: first action
            code_arg1: whether to set and recv a code
            log_msg_arg1: whether to specify a log message
            action_arg2: second action
            caplog: fixture to capture log messages
            thread_exc: intercepts thread exceptions

        """
        class ThreadPairApp(threading.Thread, ThreadPair):
            """ThreadPairApp class with thread and event."""
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
                ThreadPair.__init__(self,
                                    group_name='group1',
                                    name='beta',
                                    thread=self)

                self.cmds = cmds
                self.exp_log_msgs = exp_log_msgs

            def run(self):
                """Thread to send and receive messages."""
                l_msg = 'ThreadPairApp run started'
                self.exp_log_msgs.add_msg(l_msg)
                logger.debug(l_msg)
                thread_func1(
                    cmds=self.cmds,
                    descs=descs,
                    exp_log_msgs=self.exp_log_msgs,
                    thread_pair=self)

                l_msg = 'ThreadPairApp run exiting'
                self.exp_log_msgs.add_msg(l_msg)
                logger.debug(l_msg)

        alpha_call_seq = ('test_thread_pair.py::TestCombos.action_loop')
        beta_call_seq = ('test_thread_pair.py::thread_func1')
        exp_log_msgs = ExpLogMsgs(alpha_call_seq, beta_call_seq)
        l_msg = 'mainline entered'
        exp_log_msgs.add_msg(l_msg)
        logger.debug(l_msg)

        cmds = Cmds()
        descs = ThreadPairDescs()

        cmds.l_msg = log_msg_arg1
        cmds.r_code = code_arg1

        f1_thread = ThreadPairApp(cmds,
                                  exp_log_msgs)

        l_msg = 'mainline about to start ThreadPairApp'
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
                    descs: ThreadPairDescs,
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
        cmds.get_cmd('alpha')  # go1
        thread_pair = ThreadPair(group_name='group1', name='alpha')
        descs.add_desc(ThreadPairDesc(name='alpha',
                                      thread_pair=thread_pair,
                                      thread=threading.current_thread()))
        cmds.queue_cmd('beta')  # go2
        thread_pair.pair_with(remote_name='beta')
        cmds.get_cmd('alpha')  # go3

        actions = []
        actions.append(action1)
        actions.append(action2)
        for action in actions:

            if action == Action.MainWait:
                l_msg = 'main starting Action.MainWait'
                exp_log_msgs.add_msg(l_msg)
                logger.debug(l_msg)

                cmds.queue_cmd('beta', Cmd.Resume)
                assert thread_pair.wait()
                if cmds.r_code:
                    assert thread_pair.code == cmds.r_code
                    assert cmds.r_code == thread_pair.get_code()

            elif action == Action.MainSync:
                l_msg = 'main starting Action.MainSync'
                exp_log_msgs.add_msg(l_msg)
                logger.debug(l_msg)

                cmds.queue_cmd('beta', Cmd.Sync)

                if cmds.l_msg:
                    exp_log_msgs.add_alpha_sync_msg(cmds.l_msg, True)
                    assert thread_pair.sync(log_msg=cmds.l_msg)
                else:
                    assert thread_pair.sync()

            elif action == Action.MainSync_TOT:
                l_msg = 'main starting Action.MainSync_TOT'
                exp_log_msgs.add_msg(l_msg)
                logger.debug(l_msg)

                cmds.queue_cmd('beta', Cmd.Sync)

                if cmds.l_msg:
                    exp_log_msgs.add_alpha_sync_msg(cmds.l_msg, True)
                    assert thread_pair.sync(timeout=5,
                                            log_msg=cmds.l_msg)
                else:
                    assert thread_pair.sync(timeout=5)

            elif action == Action.MainSync_TOF:
                l_msg = 'main starting Action.MainSync_TOF'
                exp_log_msgs.add_msg(l_msg)
                logger.debug(l_msg)
                l_msg = r'alpha timeout of a sync\(\) request.'
                exp_log_msgs.add_msg(l_msg)

                if cmds.l_msg:
                    exp_log_msgs.add_alpha_sync_msg(cmds.l_msg, False)
                    assert not thread_pair.sync(timeout=0.3,
                                                log_msg=cmds.l_msg)
                else:
                    assert not thread_pair.sync(timeout=0.3)

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
                    assert thread_pair.resume(code=cmds.r_code)
                    assert thread_pair.remote.code == cmds.r_code
                else:
                    assert thread_pair.resume()
                    assert not thread_pair.remote.code

                assert thread_pair.event.is_set()
                cmds.queue_cmd('beta', Cmd.Wait)

            elif action == Action.MainResume_TOT:
                l_msg = 'main starting Action.MainResume_TOT'
                exp_log_msgs.add_msg(l_msg)
                logger.debug(l_msg)
                if cmds.r_code:
                    assert thread_pair.resume(code=cmds.r_code, timeout=0.5)
                    assert thread_pair.remote.code == cmds.r_code
                else:
                    assert thread_pair.resume(timeout=0.5)
                    assert not thread_pair.remote.code

                assert thread_pair.event.is_set()
                cmds.queue_cmd('beta', Cmd.Wait)

            elif action == Action.MainResume_TOF:
                l_msg = 'main starting Action.MainResume_TOF'
                exp_log_msgs.add_msg(l_msg)
                logger.debug(l_msg)
                l_msg = (f'{thread_pair.name} timeout '
                         r'of a resume\(\) request with '
                         r'self.event.is_set\(\) = True and '
                         'self.remote.deadlock = False')
                exp_log_msgs.add_msg(l_msg)

                assert not thread_pair.event.is_set()
                # pre-resume to set flag
                if cmds.r_code:
                    assert thread_pair.resume(code=cmds.r_code)
                    assert thread_pair.remote.code == cmds.r_code
                else:
                    assert thread_pair.resume()
                    assert not thread_pair.remote.code

                assert thread_pair.event.is_set()

                if cmds.r_code:
                    start_time = time.time()
                    assert not thread_pair.resume(code=cmds.r_code,
                                                  timeout=0.3)
                    assert 0.3 <= (time.time() - start_time) <= 0.5
                    assert thread_pair.remote.code == cmds.r_code
                else:
                    start_time = time.time()
                    assert not thread_pair.resume(timeout=0.5)
                    assert 0.5 <= (time.time() - start_time) <= 0.75
                    assert not thread_pair.remote.code

                assert thread_pair.event.is_set()

                # tell thread to clear wait
                cmds.queue_cmd('beta', Cmd.Wait_Clear)

            elif action == Action.ThreadWait:
                l_msg = 'main starting Action.ThreadWait'
                exp_log_msgs.add_msg(l_msg)
                logger.debug(l_msg)

                cmds.queue_cmd('beta', Cmd.Wait)
                thread_pair.pause_until(WUCond.RemoteWaiting)
                if cmds.r_code:
                    thread_pair.resume(code=cmds.r_code)
                    assert thread_pair.remote.code == cmds.r_code
                else:
                    thread_pair.resume()

            elif action == Action.ThreadWait_TOT:
                l_msg = 'main starting Action.ThreadWait_TOT'
                exp_log_msgs.add_msg(l_msg)
                logger.debug(l_msg)

                cmds.queue_cmd('beta', Cmd.Wait_TOT)
                thread_pair.pause_until(WUCond.RemoteWaiting)
                # time.sleep(0.3)
                if cmds.r_code:
                    thread_pair.resume(code=cmds.r_code)
                    assert thread_pair.remote.code == cmds.r_code
                else:
                    thread_pair.resume()

            elif action == Action.ThreadWait_TOF:
                l_msg = 'main starting Action.ThreadWait_TOF'
                exp_log_msgs.add_msg(l_msg)
                logger.debug(l_msg)

                cmds.queue_cmd('beta', Cmd.Wait_TOF)
                thread_pair.pause_until(WUCond.RemoteWaiting)

            elif action == Action.ThreadResume:
                l_msg = 'main starting Action.ThreadResume'
                exp_log_msgs.add_msg(l_msg)
                logger.debug(l_msg)

                cmds.queue_cmd('beta', Cmd.Resume)
                thread_pair.pause_until(WUCond.RemoteResume)
                assert thread_pair.wait()
                if cmds.r_code:
                    assert thread_pair.code == cmds.r_code
                    assert cmds.r_code == thread_pair.get_code()
            else:
                raise IncorrectActionSpecified('The Action is not recognized')

            while True:
                thread_exc1.raise_exc_if_one()  # detect thread error
                alpha_cmd = cmds.get_cmd('alpha')
                if alpha_cmd == Cmd.Next_Action:
                    break
                else:
                    raise UnrecognizedCmd

        # clear the codes to allow verify registry to work
        thread_pair.code = None
        thread_pair.remote.code = None


###############################################################################
# thread_func1
###############################################################################
def thread_func1(cmds: Cmds,
                 descs: ThreadPairDescs,
                 exp_log_msgs: Any,
                 t_pair: Optional[ThreadPair] = None,
                 ) -> None:
    """Thread to test ThreadPair scenarios.

    Args:
        cmds: commands to do
        descs: used to verify registry and ThreadPair status
        exp_log_msgs: expected log messages
        t_pair: instance of ThreadPair

    Raises:
        UnrecognizedCmd: Thread received an unrecognized command

    """
    l_msg = 'thread_func1 beta started'
    exp_log_msgs.add_msg(l_msg)
    logger.debug(l_msg)

    if t_pair is None:
        t_pair = ThreadPair(group_name='group1', name='beta')

    descs.add_desc(ThreadPairDesc(name='beta',
                                  thread_pair=t_pair,
                                  thread=threading.current_thread()))
    cmds.queue_cmd('alpha', 'go1')
    cmds.get_cmd('beta')  # go2
    t_pair.pair_with(remote_name='alpha')
    descs.paired('alpha', 'beta')
    cmds.queue_cmd('alpha', 'go3')

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
                assert t_pair.wait(log_msg=cmds.l_msg)
            else:
                assert t_pair.wait()
            if cmds.r_code:
                assert t_pair.code == cmds.r_code
                assert cmds.r_code == t_pair.get_code()

            cmds.queue_cmd('alpha', Cmd.Next_Action)

        elif beta_cmd == Cmd.Wait_TOT:
            l_msg = 'thread_func1 doing Wait_TOT'
            exp_log_msgs.add_msg(l_msg)
            logger.debug(l_msg)
            if cmds.l_msg:
                exp_log_msgs.add_beta_wait_msg(cmds.l_msg, True)
                assert t_pair.wait(log_msg=cmds.l_msg)
            else:
                assert t_pair.wait()
            if cmds.r_code:
                assert t_pair.code == cmds.r_code
                assert cmds.r_code == t_pair.get_code()

            cmds.queue_cmd('alpha', Cmd.Next_Action)

        elif beta_cmd == Cmd.Wait_TOF:
            l_msg = 'thread_func1 doing Wait_TOF'
            exp_log_msgs.add_msg(l_msg)
            logger.debug(l_msg)
            l_msg = (f'{t_pair.name} timeout of a '
                     r'wait\(\) request with '
                     'self.wait_wait = True and '
                     'self.sync_wait = False')
            exp_log_msgs.add_msg(l_msg)

            start_time = time.time()
            if cmds.l_msg:
                exp_log_msgs.add_beta_wait_msg(cmds.l_msg, False)
                assert not t_pair.wait(timeout=0.5,
                                        log_msg=cmds.l_msg)
            else:
                assert not t_pair.wait(timeout=0.5)
            assert 0.5 < (time.time() - start_time) < 0.75

            cmds.queue_cmd('alpha', Cmd.Next_Action)

        elif beta_cmd == Cmd.Wait_Clear:
            l_msg = 'thread_func1 doing Wait_Clear'
            exp_log_msgs.add_msg(l_msg)
            logger.debug(l_msg)
            if cmds.l_msg:
                exp_log_msgs.add_beta_wait_msg(cmds.l_msg, True)
                assert t_pair.wait(log_msg=cmds.l_msg)
            else:
                assert t_pair.wait()

            if cmds.r_code:
                assert t_pair.code == cmds.r_code
                assert cmds.r_code == t_pair.get_code()

            cmds.queue_cmd('alpha', Cmd.Next_Action)

        elif beta_cmd == Cmd.Sync:
            l_msg = 'thread_func1 beta doing Sync'
            exp_log_msgs.add_msg(l_msg)
            logger.debug(l_msg)

            if cmds.l_msg:
                exp_log_msgs.add_beta_sync_msg(cmds.l_msg, True)
                assert t_pair.sync(log_msg=cmds.l_msg)
            else:
                assert t_pair.sync()

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
                    assert t_pair.resume(code=cmds.r_code,
                                          log_msg=cmds.l_msg)
                else:
                    assert t_pair.resume(code=cmds.r_code)
                assert t_pair.remote.code == cmds.r_code
            else:
                if cmds.l_msg:
                    exp_log_msgs.add_beta_resume_msg(cmds.l_msg, True)
                    assert t_pair.resume(log_msg=cmds.l_msg)
                else:
                    assert t_pair.resume()

            cmds.queue_cmd('alpha', Cmd.Next_Action)
        else:
            raise UnrecognizedCmd('Thread received an unrecognized cmd')

    l_msg = 'thread_func1 beta exiting'
    exp_log_msgs.add_msg(l_msg)
    logger.debug(l_msg)
