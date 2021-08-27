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
    ThreadPairNameAlreadyInUse,
    ThreadPairNotPaired,
    ThreadPairPairWithSelfNotAllowed,
    ThreadPairPairWithTimedOut,
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
                 name: str,
                 thread: Optional[threading.Thread] = None) -> None:
        """Initialize the Theta object.

        Args:
            name: name of the Theta
            thread: thread to use instead of threading.current_thread()

        """
        ThreadPair.__init__(self, name=name, thread=thread)
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
                 name: str,
                 thread: Optional[threading.Thread] = None) -> None:
        """Initialize the Sigma object.

        Args:
            name: name of the Sigma
            thread: thread to use instead of threading.current_thread()

        """
        ThreadPair.__init__(self, name=name, thread=thread)
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
                 name: str,
                 thread: Optional[threading.Thread] = None) -> None:
        """Initialize the Omega object.

        Args:
            name: name of the Omega
            thread: thread to use instead of threading.current_thread()

        """
        ThreadPair.__init__(self, name=name, thread=thread)
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
    t_pair = ThreadPair(name='beta')
    descs.add_desc(ThreadPairDesc(name='beta',
                                  thread_pair=t_pair))

    # tell alpha OK to verify (i.e., beta_thread_pair set with t_pair)
    cmds.queue_cmd('alpha', 'go')

    t_pair.pair_with(remote_name='alpha')

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
        self.t_pair = ThreadPair(name='beta', thread=self)

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
        ThreadPair.__init__(self, name='beta', thread=self)
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

        thread_pair = ThreadPair(name='alpha')
        descs.add_desc(ThreadPairDesc(name='alpha',
                                      thread_pair=thread_pair,
                                      thread=threading.current_thread()))

        expected_repr_str = 'ThreadPair(name="alpha")'

        assert repr(thread_pair) == expected_repr_str

        thread_pair2 = ThreadPair(name="AlphaDog")
        descs.add_desc(ThreadPairDesc(name='AlphaDog',
                                      thread_pair=thread_pair2,
                                      thread=threading.current_thread()))

        expected_repr_str = 'ThreadPair(name="AlphaDog")'

        assert repr(thread_pair2) == expected_repr_str

        def f1():
            t_pair = ThreadPair(name='beta1')
            descs.add_desc(ThreadPairDesc(name='beta1',
                                          thread_pair=t_pair,
                                          thread=threading.current_thread()))
            f1_expected_repr_str = 'ThreadPair(name="beta1")'
            assert repr(t_pair) == f1_expected_repr_str

            cmds.queue_cmd('alpha', 'go')
            cmds.get_cmd('beta1')

        def f2():
            t_pair = ThreadPair(name='beta2')
            descs.add_desc(ThreadPairDesc(name='beta2',
                                          thread_pair=t_pair,
                                          thread=threading.current_thread()))
            f1_expected_repr_str = 'ThreadPair(name="beta2")'
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

        thread_pair = ThreadPair(name='alpha')

        descs.add_desc(ThreadPairDesc(name='alpha',
                                      thread_pair=thread_pair,
                                      thread=threading.current_thread()))

        # not OK to instantiate a new thread_pair with same name
        with pytest.raises(ThreadPairNameAlreadyInUse):
            _ = ThreadPair(name='alpha')

        with pytest.raises(ThreadPairIncorrectNameSpecified):
            _ = ThreadPair(name=42)  # type: ignore

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
            t_pair = ThreadPair(name=name)
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

        thread_pair = ThreadPair(name='alpha')

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
            thread_pair = ThreadPair(name='alpha')  # create fresh

        beta_t3 = threading.Thread(target=f1, args=('charlie',))
        beta_t3.start()

        cmds.get_cmd('alpha')

        thread_pair.pair_with(remote_name='charlie')
        descs.paired('alpha', 'charlie')

        assert 'beta' not in ThreadPair._registry

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
            _ = ThreadPair(name='alpha2')

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
            t_pair = ThreadPair(name=name)

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

            t_pair.sync(log_msg=f'{name} f1 sync point 1')

            logger.debug(f'{name} f1 exiting')

        def f2(name: str) -> None:
            """Func to test instantiate ThreadPair.

            Args:
                name: name to use for t_pair
            """
            logger.debug(f'{name} f2 entered')
            t_pair = ThreadPair(name=name)

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

            t_pair.sync(log_msg=f'{name} f1 sync point 1')

            logger.debug(f'{name} f2 exiting')

        #######################################################################
        # mainline
        #######################################################################
        descs = ThreadPairDescs()

        cmds = Cmds()

        beta_t = threading.Thread(target=f1, args=('beta',))
        charlie_t = threading.Thread(target=f2, args=('charlie',))

        thread_pair = ThreadPair(name='alpha')

        descs.add_desc(ThreadPairDesc(name='alpha',
                                      thread_pair=thread_pair))

        beta_t.start()

        cmds.get_cmd('alpha')

        thread_pair.pair_with(remote_name='beta')

        #######################################################################
        # pair with charlie
        #######################################################################
        cmds.get_cmd('alpha')

        thread_pair2 = ThreadPair(name='alpha2')

        descs.add_desc(ThreadPairDesc(name='alpha2',
                                      thread_pair=thread_pair2))

        charlie_t.start()

        thread_pair2.pair_with(remote_name='charlie')

        cmds.get_cmd('alpha')

        thread_pair.sync(log_msg='alpha sync point 1')

        beta_t.join()

        descs.thread_end(name='beta')

        thread_pair2.sync(log_msg='alpha sync point 2')

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

        # cause cleanup via a sync request
        with pytest.raises(ThreadPairRemoteThreadNotAlive):
            thread_pair.sync(log_msg='mainline sync point 3')

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
            t_pair = ThreadPair(name='beta')

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
            t_pair = ThreadPair(name='charlie')

            descs.add_desc(ThreadPairDesc(name='charlie',
                                          thread_pair=t_pair),
                           verify=False)

            cmds.queue_cmd('alpha', 'go')
            t_pair.pair_with(remote_name='alpha')
            descs.paired('alpha', 'charlie', verify=False)

            cmds.queue_cmd('alpha', 'go')

            t_pair.sync(log_msg='charlie f1 sync point 1')

            logger.debug(f'charlie f2 exiting')

        #######################################################################
        # mainline
        #######################################################################
        descs = ThreadPairDescs()

        cmds = Cmds()

        beta_t = threading.Thread(target=f1)
        charlie_t = threading.Thread(target=f2)

        thread_pair = ThreadPair(name='alpha')

        descs.add_desc(ThreadPairDesc(name='alpha',
                                      thread_pair=thread_pair))

        beta_t.start()

        cmds.get_cmd('alpha')

        beta_se = ThreadPair._registry['beta']

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
        thread_pair.sync(log_msg='alpha sync point 1')

        charlie_t.join()

        descs.thread_end(name='charlie')

        # cause cleanup via a sync request
        with pytest.raises(ThreadPairRemoteThreadNotAlive):
            thread_pair.sync(log_msg='mainline sync point 3')

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
            t_pair = ThreadPair(name=name)

            descs.add_desc(ThreadPairDesc(name=name,
                                          thread_pair=t_pair))

            cmds.queue_cmd('alpha')

            t_pair.pair_with(remote_name=remote_name,
                              log_msg=f'f1 {name} pair with {remote_name} '
                                      f'for idx {idx}')

            t_pair.sync(log_msg=f'{name} f1 sync point 1')

            assert t_pair.sync(timeout=3,
                                log_msg=f'{name} f1 sync point 2')

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
        thread_pair0 = ThreadPair(name='alpha0')
        descs.add_desc(ThreadPairDesc(name='alpha0',
                                      thread_pair=thread_pair0))

        #######################################################################
        # create alpha1 ThreadPair and desc, and verify
        #######################################################################
        thread_pair1 = ThreadPair(name='alpha1')
        descs.add_desc(ThreadPairDesc(name='alpha1',
                                      thread_pair=thread_pair1))

        #######################################################################
        # create alpha2 ThreadPair and desc, and verify
        #######################################################################
        thread_pair2 = ThreadPair(name='alpha2')
        descs.add_desc(ThreadPairDesc(name='alpha2',
                                      thread_pair=thread_pair2))

        #######################################################################
        # create alpha3 ThreadPair and desc, and verify
        #######################################################################
        thread_pair3 = ThreadPair(name='alpha3')
        descs.add_desc(ThreadPairDesc(name='alpha3',
                                      thread_pair=thread_pair3))

        #######################################################################
        # start beta0 thread, and verify
        #######################################################################
        beta_t0.start()

        cmds.get_cmd('alpha')

        thread_pair0.pair_with(remote_name='beta0')

        thread_pair0.sync(log_msg='alpha0 sync point 1')
        descs.paired('alpha0', 'beta0')

        #######################################################################
        # start beta1 thread, and verify
        #######################################################################
        beta_t1.start()

        cmds.get_cmd('alpha')

        thread_pair1.pair_with(remote_name='beta1')

        thread_pair1.sync(log_msg='alpha1 sync point 1')
        descs.paired('alpha1', 'beta1')

        #######################################################################
        # start beta2 thread, and verify
        #######################################################################
        beta_t2.start()

        cmds.get_cmd('alpha')

        thread_pair2.pair_with(remote_name='beta2')

        thread_pair2.sync(log_msg='alpha2 sync point 1')
        descs.paired('alpha2', 'beta2')

        #######################################################################
        # start beta3 thread, and verify
        #######################################################################
        beta_t3.start()

        cmds.get_cmd('alpha')

        thread_pair3.pair_with(remote_name='beta3')

        thread_pair3.sync(log_msg='alpha3 sync point 1')
        descs.paired('alpha3', 'beta3')

        #######################################################################
        # let beta0 finish
        #######################################################################
        thread_pair0.sync(log_msg='alpha0 sync point 1')

        beta_t0.join()

        descs.thread_end(name='beta0')

        #######################################################################
        # replace old beta0 w new beta0 - should cleanup registry old beta0
        #######################################################################
        beta_t0 = threading.Thread(target=f1, args=('beta0', 'alpha0', 0))

        beta_t0.start()

        cmds.get_cmd('alpha')

        thread_pair0.pair_with(remote_name='beta0')

        thread_pair0.sync(log_msg='alpha0 sync point 1')
        descs.paired('alpha0', 'beta0')

        #######################################################################
        # let beta1 and beta3 finish
        #######################################################################
        thread_pair1.sync(log_msg='alpha1 sync point 2')
        beta_t1.join()
        descs.thread_end(name='beta1')

        thread_pair3.sync(log_msg='alpha3 sync point 3')
        beta_t3.join()
        descs.thread_end(name='beta3')

        #######################################################################
        # replace old beta1 w new beta1 - should cleanup old beta1 and beta3
        #######################################################################
        beta_t1 = threading.Thread(target=f1, args=('beta1', 'alpha1', 1))

        beta_t1.start()

        cmds.get_cmd('alpha')

        thread_pair1.pair_with(remote_name='beta1')

        thread_pair1.sync(log_msg='alpha1 sync point 1')
        descs.paired('alpha1', 'beta1')

        # should get not alive for beta3
        with pytest.raises(ThreadPairRemoteThreadNotAlive):
            thread_pair3.sync(log_msg='mainline sync point 4')

        # should still be the same
        descs.verify_registry()

        #######################################################################
        # get a new beta3 going
        #######################################################################
        beta_t3 = threading.Thread(target=f1, args=('beta3', 'alpha3', 3))

        beta_t3.start()

        cmds.get_cmd('alpha')

        thread_pair3.pair_with(remote_name='beta3')

        thread_pair3.sync(log_msg='alpha3 sync point 1')
        descs.paired('alpha3', 'beta3')

        #######################################################################
        # let beta1 and beta2 finish
        #######################################################################
        thread_pair1.sync(log_msg='alpha1 sync point 5')
        beta_t1.join()
        descs.thread_end(name='beta1')

        thread_pair2.sync(log_msg='alpha2 sync point 6')
        beta_t2.join()
        descs.thread_end(name='beta2')

        #######################################################################
        # trigger cleanup for beta1 and beta2
        #######################################################################
        with pytest.raises(ThreadPairRemoteThreadNotAlive):
            thread_pair2.sync(log_msg='alpha2 sync point 7')

        descs.cleanup()

        #######################################################################
        # should get ThreadPairRemoteThreadNotAlive for beta1 and beta2
        #######################################################################
        with pytest.raises(ThreadPairRemoteThreadNotAlive):
            thread_pair1.sync(log_msg='alpha1 sync point 8')

        with pytest.raises(ThreadPairRemoteThreadNotAlive):
            thread_pair2.sync(log_msg='alpha 2 sync point 9')

        descs.verify_registry()

        #######################################################################
        # get a new beta2 going
        #######################################################################
        beta_t2 = threading.Thread(target=f1, args=('beta2', 'alpha2', 2))

        beta_t2.start()

        cmds.get_cmd('alpha')

        thread_pair2.pair_with(remote_name='beta2')

        thread_pair2.sync(log_msg='alpha2 sync point 1')
        descs.paired('alpha2', 'beta2')

        thread_pair2.sync(log_msg='alpha2 sync point 2')
        beta_t2.join()
        descs.thread_end(name='beta2')

        #######################################################################
        # let beta0 complete
        #######################################################################
        thread_pair0.sync(log_msg='alpha0 sync point 2')
        beta_t0.join()
        descs.thread_end(name='beta0')

        #######################################################################
        # let beta3 complete
        #######################################################################
        thread_pair3.sync(log_msg='alpha0 sync point 2')
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
            print('beta f1 entered')
            t_pair = ThreadPair(name='beta')

            descs.add_desc(ThreadPairDesc(name='beta',
                                          thread_pair=t_pair))

            my_c_thread = threading.current_thread()
            assert t_pair.thread is my_c_thread
            assert t_pair.thread is threading.current_thread()

            t_pair.pair_with(remote_name='alpha')

            t_pair.sync(log_msg='f1 beta sync point 1')

            logger.debug('f1 beta about to enter cmd loop')

            while True:
                beta_cmd = cmds.get_cmd('beta')
                if beta_cmd == Cmd.Exit:
                    break

                logger.debug(f'thread_func1 received cmd: {beta_cmd}')

                if beta_cmd == Cmd.Wait:
                    assert t_pair.wait()

                elif beta_cmd == Cmd.Resume:
                    with pytest.raises(ThreadPairWaitUntilTimeout):
                        t_pair.pause_until(WUCond.RemoteWaiting,
                                            timeout=0.002)
                    with pytest.raises(ThreadPairWaitUntilTimeout):
                        t_pair.pause_until(WUCond.RemoteWaiting, timeout=0.01)
                    with pytest.raises(ThreadPairWaitUntilTimeout):
                        t_pair.pause_until(WUCond.RemoteWaiting, timeout=0.02)

                    t_pair.sync(log_msg='f1 beta sync point 2')

                    t_pair.pause_until(WUCond.RemoteWaiting)
                    t_pair.pause_until(WUCond.RemoteWaiting, timeout=0.001)
                    t_pair.pause_until(WUCond.RemoteWaiting, timeout=0.01)
                    t_pair.pause_until(WUCond.RemoteWaiting, timeout=0.02)
                    t_pair.pause_until(WUCond.RemoteWaiting, timeout=-0.02)
                    t_pair.pause_until(WUCond.RemoteWaiting, timeout=-1)
                    t_pair.pause_until(WUCond.RemoteWaiting, timeout=0)

                    t_pair.resume()

        def foreign1(t_pair):
            logger.debug('foreign1 entered')

            with pytest.raises(ThreadPairDetectedOpFromForeignThread):
                t_pair.resume()

            with pytest.raises(ThreadPairDetectedOpFromForeignThread):
                t_pair.pair_with(remote_name='beta')

            with pytest.raises(ThreadPairDetectedOpFromForeignThread):
                t_pair.pair_with(remote_name='beta', timeout=1)

            with pytest.raises(ThreadPairDetectedOpFromForeignThread):
                t_pair.pause_until(WUCond.RemoteWaiting, timeout=0.02)

            with pytest.raises(ThreadPairDetectedOpFromForeignThread):
                t_pair.pause_until(WUCond.RemoteWaiting, timeout=0.02)
            with pytest.raises(ThreadPairDetectedOpFromForeignThread):
                t_pair.pause_until(WUCond.RemoteWaiting)
            with pytest.raises(ThreadPairDetectedOpFromForeignThread):
                t_pair.wait()

            with pytest.raises(ThreadPairDetectedOpFromForeignThread):
                t_pair.sync()

            logger.debug('foreign1 exiting')

        cmds = Cmds()
        descs = ThreadPairDescs()

        thread_pair1 = ThreadPair(name='alpha')
        descs.add_desc(ThreadPairDesc(name='alpha',
                                      thread_pair=thread_pair1))

        alpha_t = threading.current_thread()
        my_f1_thread = threading.Thread(target=f1)
        my_foreign1_thread = threading.Thread(target=foreign1,
                                              args=(thread_pair1,))

        with pytest.raises(ThreadPairNotPaired):
            thread_pair1.pause_until(WUCond.RemoteWaiting, timeout=-0.002)
        with pytest.raises(ThreadPairNotPaired):
            thread_pair1.pause_until(WUCond.RemoteWaiting, timeout=0)
        with pytest.raises(ThreadPairNotPaired):
            thread_pair1.pause_until(WUCond.RemoteWaiting, timeout=0.002)
        with pytest.raises(ThreadPairNotPaired):
            thread_pair1.pause_until(WUCond.RemoteWaiting, timeout=0.2)
        with pytest.raises(ThreadPairNotPaired):
            thread_pair1.pause_until(WUCond.RemoteWaiting)

        logger.debug('mainline about to start beta thread')

        my_f1_thread.start()

        thread_pair1.pair_with(remote_name='beta')
        descs.paired('alpha', 'beta')

        thread_pair1.sync(log_msg='mainline sync point 1')

        cmds.queue_cmd('beta', Cmd.Wait)

        my_foreign1_thread.start()  # attempt to resume beta (should fail)

        my_foreign1_thread.join()

        logger.debug('about to pause_until RemoteWaiting')
        thread_pair1.pause_until(WUCond.RemoteWaiting)
        thread_pair1.pause_until(WUCond.RemoteWaiting, timeout=0.001)
        thread_pair1.pause_until(WUCond.RemoteWaiting, timeout=0.01)
        thread_pair1.pause_until(WUCond.RemoteWaiting, timeout=0.02)
        thread_pair1.pause_until(WUCond.RemoteWaiting, timeout=-0.02)
        thread_pair1.pause_until(WUCond.RemoteWaiting, timeout=-1)
        thread_pair1.pause_until(WUCond.RemoteWaiting, timeout=0)

        thread_pair1.resume()

        cmds.queue_cmd('beta', Cmd.Resume)

        thread_pair1.sync(log_msg='mainline sync point 2')

        assert thread_pair1.wait()

        cmds.queue_cmd('beta', Cmd.Exit)

        my_f1_thread.join()
        descs.thread_end(name='beta')

        with pytest.raises(ThreadPairRemoteThreadNotAlive):
            thread_pair1.resume()

        with pytest.raises(ThreadPairRemoteThreadNotAlive):
            thread_pair1.wait()

        with pytest.raises(ThreadPairRemoteThreadNotAlive):
            thread_pair1.pause_until(WUCond.RemoteWaiting)

        with pytest.raises(ThreadPairRemoteThreadNotAlive):
            thread_pair1.sync(log_msg='mainline sync point 3')

        assert thread_pair1.thread is alpha_t

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

        thread_pair = ThreadPair(name='alpha')
        descs.add_desc(ThreadPairDesc(name='alpha',
                                      thread_pair=thread_pair))

        f1_thread = threading.Thread(target=outer_f1, args=(cmds, descs))
        f1_thread.start()

        cmds.get_cmd('alpha')

        thread_pair.pair_with(remote_name='beta')
        descs.paired('alpha', 'beta')

        thread_pair.sync(log_msg='mainline sync point 1')

        thread_pair.resume(log_msg='alpha resume 12')

        thread_pair.sync(log_msg='mainline sync point 2')

        thread_pair.wait(log_msg='alpha wait 23')

        thread_pair.sync(log_msg='mainline sync point 3')

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

        thread_pair = ThreadPair(name='alpha')
        descs.add_desc(ThreadPairDesc(name='alpha',
                                      thread_pair=thread_pair))

        thread_app = OuterThreadApp(cmds=cmds, descs=descs)

        thread_app.start()

        cmds.get_cmd('alpha')
        thread_pair.pair_with(remote_name='beta', timeout=3)

        thread_pair.sync(log_msg='mainline sync point 1')

        thread_pair.resume(log_msg='alpha resume 12')

        thread_pair.sync(log_msg='mainline sync point 2')

        thread_pair.wait(log_msg='alpha wait 23')

        thread_pair.sync(log_msg='mainline sync point 3')

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
        thread_pair = ThreadPair(name='alpha')
        descs.add_desc(ThreadPairDesc(name='alpha',
                                      thread_pair=thread_pair))

        thread_event_app = OuterThreadEventApp(cmds=cmds, descs=descs)
        thread_event_app.start()

        cmds.get_cmd('alpha')

        thread_pair.pair_with(remote_name='beta', timeout=3)

        thread_pair.sync(log_msg='mainline sync point 1')

        thread_pair.resume(log_msg='alpha resume 12')

        thread_pair.sync(log_msg='mainline sync point 2')

        thread_pair.wait(log_msg='alpha wait 23')

        thread_pair.sync(log_msg='mainline sync point 3')

        thread_event_app.join()

        descs.thread_end(name='beta')

        logger.debug('mainline exiting')

    ###########################################################################
    # test_thread_pair_wait_deadlock_detection
    ###########################################################################
    def test_thread_pair_wait_deadlock_detection(self) -> None:
        """Test deadlock detection with f1."""
        #######################################################################
        # f1
        #######################################################################

        def f1(ml_thread):
            logger.debug('beta f1 beta entered')
            t_pair = ThreadPair(name='beta')

            descs.add_desc(ThreadPairDesc(name='beta',
                                          thread_pair=t_pair))

            my_c_thread = threading.current_thread()

            cmds.get_cmd('beta')

            t_pair.pair_with(remote_name='alpha')
            assert t_pair.remote.thread is ml_thread
            assert t_pair.remote.thread is alpha_t
            assert t_pair.thread is my_c_thread
            assert t_pair.thread is threading.current_thread()

            t_pair.sync(log_msg='beta f1 thread sync point 1')

            with pytest.raises(ThreadPairWaitDeadlockDetected):
                t_pair.wait()

            t_pair.sync(log_msg='beta f1 thread sync point 2')

            t_pair.wait()  # clear the resume that comes after the deadlock

            t_pair.sync(log_msg='beta f1 thread sync point 3')

            t_pair.pause_until(WUCond.RemoteWaiting, timeout=2)
            with pytest.raises(ThreadPairWaitDeadlockDetected):
                t_pair.wait()

            t_pair.sync(log_msg='beta f1 thread sync point 4')

            t_pair.resume()

        #######################################################################
        # mainline start
        #######################################################################
        cmds = Cmds()
        descs = ThreadPairDescs()
        alpha_t = threading.current_thread()
        thread_pair = ThreadPair(name='alpha')
        descs.add_desc(ThreadPairDesc(name='alpha',
                                      thread_pair=thread_pair))

        my_f1_thread = threading.Thread(target=f1, args=(alpha_t,))

        with pytest.raises(ThreadPairNotPaired):
            thread_pair.pause_until(WUCond.RemoteWaiting, timeout=-0.002)
        with pytest.raises(ThreadPairNotPaired):
            thread_pair.pause_until(WUCond.RemoteWaiting, timeout=0)
        with pytest.raises(ThreadPairNotPaired):
            thread_pair.pause_until(WUCond.RemoteWaiting, timeout=0.002)
        with pytest.raises(ThreadPairNotPaired):
            thread_pair.pause_until(WUCond.RemoteWaiting, timeout=0.2)
        with pytest.raises(ThreadPairNotPaired):
            thread_pair.pause_until(WUCond.RemoteWaiting)

        my_f1_thread.start()

        with pytest.raises(ThreadPairNotPaired):
            thread_pair.pause_until(WUCond.RemoteWaiting)

        # tell f1 to proceed to pair_with
        cmds.queue_cmd('beta', Cmd.Exit)

        thread_pair.pair_with(remote_name='beta', timeout=3)
        descs.paired('alpha', 'beta')

        thread_pair.sync(log_msg='mainline sync point 1')

        with pytest.raises(ThreadPairWaitDeadlockDetected):
            thread_pair.wait()

        thread_pair.sync(log_msg='mainline sync point 2')

        thread_pair.resume()

        thread_pair.sync(log_msg='mainline sync point 3')

        with pytest.raises(ThreadPairWaitDeadlockDetected):
            thread_pair.wait()

        thread_pair.sync(log_msg='mainline sync point 4')

        assert thread_pair.wait()  # clear resume

        my_f1_thread.join()
        descs.thread_end(name='beta')

        with pytest.raises(ThreadPairRemoteThreadNotAlive):
            thread_pair.resume()

        descs.cleanup()

        with pytest.raises(ThreadPairRemoteThreadNotAlive):
            thread_pair.wait()

        with pytest.raises(ThreadPairRemoteThreadNotAlive):
            thread_pair.sync(log_msg='mainline sync point 5')

        assert thread_pair.thread is alpha_t
        assert thread_pair.remote.thread is my_f1_thread

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
                self.t_pair = ThreadPair(name='beta', thread=self)
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

                with pytest.raises(ThreadPairWaitUntilTimeout):
                    self.t_pair.pause_until(WUCond.RemoteResume,
                                             timeout=0.009)
                self.t_pair.sync(log_msg='beta run sync point 1')
                self.t_pair.pause_until(WUCond.RemoteResume, timeout=5)
                self.t_pair.pause_until(WUCond.RemoteResume)

                assert self.t_pair.wait(log_msg='beta run wait 12')

                self.t_pair.sync(log_msg='beta run sync point 2')
                self.t_pair.sync(log_msg='beta run sync point 3')

                self.t_pair.resume()

                self.t_pair.sync(log_msg='beta run sync point 4')
                logger.debug('beta run exiting 45')

        #######################################################################
        # mainline starts
        #######################################################################
        cmds = Cmds()
        descs = ThreadPairDescs()
        alpha_t = threading.current_thread()
        thread_pair1 = ThreadPair(name='alpha')
        descs.add_desc(ThreadPairDesc(name='alpha',
                                      thread_pair=thread_pair1))

        my_taa_thread = MyThread(thread_pair1, alpha_t)

        my_taa_thread.start()

        cmds.get_cmd('alpha')

        thread_pair1.pair_with(remote_name='beta')

        thread_pair1.sync(log_msg='mainline sync point 1')

        assert thread_pair1.resume(log_msg='mainline resume 12')

        thread_pair1.sync(log_msg='mainline sync point 2')

        with pytest.raises(ThreadPairWaitUntilTimeout):
            thread_pair1.pause_until(WUCond.RemoteResume, timeout=0.009)

        thread_pair1.sync(log_msg='mainline sync point 3')

        thread_pair1.pause_until(WUCond.RemoteResume, timeout=5)
        thread_pair1.pause_until(WUCond.RemoteResume)

        assert thread_pair1.wait(log_msg='mainline wait 34')
        thread_pair1.sync(log_msg='mainline sync point 4')

        my_taa_thread.join()
        descs.thread_end('beta')

        with pytest.raises(ThreadPairRemoteThreadNotAlive):
            thread_pair1.resume()
        descs.cleanup()

        with pytest.raises(ThreadPairRemoteThreadNotAlive):
            thread_pair1.wait()

        with pytest.raises(ThreadPairRemoteThreadNotAlive):
            thread_pair1.pause_until(WUCond.RemoteWaiting)

        with pytest.raises(ThreadPairRemoteThreadNotAlive):
            thread_pair1.pause_until(WUCond.RemoteResume)

        with pytest.raises(ThreadPairPairWithTimedOut):
            thread_pair1.pair_with(remote_name='beta', timeout=1)
        descs.paired('alpha')

        with pytest.raises(ThreadPairNotPaired):
            thread_pair1.wait()

        with pytest.raises(ThreadPairNotPaired):
            thread_pair1.pause_until(WUCond.RemoteWaiting)

        with pytest.raises(ThreadPairNotPaired):
            thread_pair1.pause_until(WUCond.RemoteResume)

        assert thread_pair1.thread is alpha_t
        assert thread_pair1.remote is None

        descs.verify_registry()

    ###########################################################################
    # test_thread_pair_inner_thread_app2
    ###########################################################################
    def test_thread_pair_inner_thread_app2(self) -> None:
        """Test ThreadPair with thread_app."""
        #######################################################################
        # mainline and ThreadApp - mainline provide beta ThreadPair
        #######################################################################
        class MyThread2(threading.Thread):
            def __init__(self,
                         t_pair: ThreadPair,
                         alpha_t1: threading.Thread):
                super().__init__()
                self.t_pair = t_pair
                # not really a good idea to set the thread - this test case
                # may not be realistic - need to consider whether the idea
                # of passing in a pre-instantiated ThreadPair (which gets
                # its thread set during instantiation) is something we want
                # to support given that we have to change the thread
                self.t_pair.thread = self
                self.alpha_t1 = alpha_t1

            def run(self):
                print('run started')
                # normally, the add_desc is done just after the
                # instantiation, but
                # in this case the thread is not made alive until now, and the
                # add_desc checks that the thread is alive
                descs.add_desc(ThreadPairDesc(name='beta',
                                              thread_pair=self.t_pair,
                                              thread=self))

                cmds.queue_cmd('alpha')

                self.t_pair.pair_with(remote_name='alpha2')

                assert self.t_pair.remote.thread is self.alpha_t1
                assert self.t_pair.remote.thread is alpha_t
                assert self.t_pair.thread is self

                my_run_thread = threading.current_thread()
                assert self.t_pair.thread is my_run_thread
                assert self.t_pair.thread is threading.current_thread()

                with pytest.raises(ThreadPairWaitDeadlockDetected):
                    self.t_pair.wait()

                assert self.t_pair.wait()
                self.t_pair.pause_until(WUCond.RemoteWaiting)
                self.t_pair.pause_until(WUCond.RemoteWaiting, timeout=2)

                self.t_pair.resume()

        cmds = Cmds()
        descs = ThreadPairDescs()
        thread_pair2 = ThreadPair(name='alpha2')
        descs.add_desc(ThreadPairDesc(name='alpha2',
                                      thread_pair=thread_pair2))

        thread_pair3 = ThreadPair(name='beta')
        alpha_t = threading.current_thread()
        my_tab_thread = MyThread2(thread_pair3, alpha_t)
        my_tab_thread.start()

        cmds.get_cmd('alpha')

        thread_pair2.pair_with(remote_name='beta')
        descs.paired('alpha2', 'beta')

        thread_pair2.pause_until(WUCond.RemoteWaiting)
        with pytest.raises(ThreadPairWaitDeadlockDetected):
            thread_pair2.wait()
        thread_pair2.resume()
        assert thread_pair2.wait()

        my_tab_thread.join()
        descs.thread_end('beta')

        with pytest.raises(ThreadPairRemoteThreadNotAlive):
            thread_pair2.resume()
        descs.cleanup()

        with pytest.raises(ThreadPairRemoteThreadNotAlive):
            thread_pair2.wait()

        with pytest.raises(ThreadPairRemoteThreadNotAlive):
            thread_pair2.pause_until(WUCond.RemoteWaiting)

        with pytest.raises(ThreadPairRemoteThreadNotAlive):
            thread_pair2.pause_until(WUCond.RemoteResume)

        assert thread_pair2.thread is alpha_t
        assert thread_pair2.remote.thread is my_tab_thread

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
                ThreadPair.__init__(self, name='beta', thread=self)
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

                assert self.wait()
                self.pause_until(WUCond.RemoteWaiting, timeout=2)
                with pytest.raises(ThreadPairWaitDeadlockDetected):
                    self.wait()
                self.resume()
                logger.debug('run exiting')

        cmds = Cmds()
        descs = ThreadPairDescs()
        alpha_t = threading.current_thread()

        my_te1_thread = MyThreadEvent1(alpha_t)
        with pytest.raises(ThreadPairDetectedOpFromForeignThread):
            my_te1_thread.pause_until(WUCond.RemoteWaiting,
                                      timeout=0.005)

        with pytest.raises(ThreadPairDetectedOpFromForeignThread):
            my_te1_thread.wait(timeout=0.005)

        with pytest.raises(ThreadPairDetectedOpFromForeignThread):
            my_te1_thread.resume(timeout=0.005)

        with pytest.raises(ThreadPairDetectedOpFromForeignThread):
            my_te1_thread.sync(timeout=0.005)

        with pytest.raises(ThreadPairDetectedOpFromForeignThread):
            my_te1_thread.pair_with(remote_name='alpha', timeout=0.5)

        assert my_te1_thread.remote is None
        assert my_te1_thread.thread is my_te1_thread

        my_te1_thread.start()

        cmds.get_cmd('alpha')
        thread_pair = ThreadPair(name='alpha')
        descs.add_desc(ThreadPairDesc(name='alpha',
                                      thread_pair=thread_pair))

        with pytest.raises(ThreadPairNotPaired):
            thread_pair.sync()

        with pytest.raises(ThreadPairNotPaired):
            thread_pair.wait()

        with pytest.raises(ThreadPairNotPaired):
            thread_pair.resume()

        thread_pair.pair_with(remote_name='beta')

        thread_pair.resume()
        with pytest.raises(ThreadPairWaitDeadlockDetected):
            thread_pair.wait()

        assert thread_pair.wait()

        my_te1_thread.join()
        descs.thread_end('beta')

        with pytest.raises(ThreadPairRemoteThreadNotAlive):
            thread_pair.resume()

        with pytest.raises(ThreadPairRemoteThreadNotAlive):
            thread_pair.wait()

        with pytest.raises(ThreadPairRemoteThreadNotAlive):
            thread_pair.pause_until(WUCond.RemoteWaiting)

        with pytest.raises(ThreadPairRemoteThreadNotAlive):
            thread_pair.pause_until(WUCond.RemoteResume)

        assert my_te1_thread.remote is not None
        assert my_te1_thread.remote.thread is not None
        assert my_te1_thread.remote.thread is alpha_t
        assert my_te1_thread.thread is my_te1_thread

    ###########################################################################
    # test_thread_pair_inner_thread_event_app2
    ###########################################################################
    def test_thread_pair_inner_thread_event_app2(self) -> None:
        """Test ThreadPair with thread_event_app."""
        #######################################################################
        # mainline and ThreadApp - mainline sets alpha thread_app sets beta
        #######################################################################
        class MyThreadEvent2(threading.Thread, ThreadPair):
            def __init__(self,
                         alpha_t1: threading.Thread):
                threading.Thread.__init__(self)
                ThreadPair.__init__(self, name='beta', thread=self)
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
                descs.add_desc(ThreadPairDesc(name='beta',
                                              thread_pair=self,
                                              thread=self))

                cmds.queue_cmd('alpha')
                self.pair_with(remote_name='alpha')
                assert self.remote.thread is self.alpha_t1
                assert self.remote.thread is alpha_t

                descs.paired('alpha', 'beta')

                with pytest.raises(ThreadPairWaitDeadlockDetected):
                    self.wait()
                assert self.wait()
                self.resume()
                logger.debug('run exiting')

        cmds = Cmds()
        descs = ThreadPairDescs()
        alpha_t = threading.current_thread()
        my_te2_thread = MyThreadEvent2(alpha_t)

        my_te2_thread.start()

        cmds.get_cmd('alpha')
        thread_pair = ThreadPair(name='alpha')
        descs.add_desc(ThreadPairDesc(name='alpha',
                                      thread_pair=thread_pair))

        thread_pair.pair_with(remote_name='beta')

        thread_pair.pause_until(WUCond.RemoteWaiting, timeout=2)
        with pytest.raises(ThreadPairWaitDeadlockDetected):
            thread_pair.wait()

        assert thread_pair.resume()
        assert thread_pair.wait()

        my_te2_thread.join()
        descs.thread_end('beta')

        with pytest.raises(ThreadPairRemoteThreadNotAlive):
            thread_pair.resume()

        with pytest.raises(ThreadPairRemoteThreadNotAlive):
            thread_pair.wait()

        with pytest.raises(ThreadPairRemoteThreadNotAlive):
            thread_pair.pause_until(WUCond.RemoteWaiting, timeout=2)

        with pytest.raises(ThreadPairRemoteThreadNotAlive):
            thread_pair.pause_until(WUCond.RemoteResume, timeout=2)

        assert thread_pair.thread is alpha_t
        assert thread_pair.remote.thread is my_te2_thread

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
            t_pair = ThreadPair(name='fa1')
            descs.add_desc(ThreadPairDesc(name='fa1',
                                          thread_pair=t_pair,
                                          thread=my_fa_thread))

            assert t_pair.thread is my_fa_thread

            t_pair.pair_with(remote_name='fb1')
            descs.paired('fa1', 'fb1')

            logger.debug('fa1 about to wait')
            t_pair.wait()
            logger.debug('fa1 back from wait')
            t_pair.pause_until(WUCond.RemoteWaiting, timeout=2)
            t_pair.resume()

        def fb1():
            logger.debug('fb1 entered')
            my_fb_thread = threading.current_thread()
            t_pair = ThreadPair(name='fb1')
            descs.add_desc(ThreadPairDesc(name='fb1',
                                          thread_pair=t_pair,
                                          thread=my_fb_thread))

            assert t_pair.thread is my_fb_thread

            t_pair.pair_with(remote_name='fa1')

            logger.debug('fb1 about to resume')
            t_pair.resume()
            t_pair.wait()

            # tell mainline we are out of the wait - OK to do descs fa1 end
            cmds.queue_cmd('alpha')

            # wait for mainline to give to go ahead after doing descs fa1 end
            cmds.get_cmd('beta')

            with pytest.raises(ThreadPairRemoteThreadNotAlive):
                t_pair.resume()

            descs.cleanup()

            with pytest.raises(ThreadPairRemoteThreadNotAlive):
                t_pair.wait()

            with pytest.raises(ThreadPairRemoteThreadNotAlive):
                t_pair.pause_until(WUCond.RemoteWaiting)

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

    ###########################################################################
    # test_thread_pair_two_f_threads2
    ###########################################################################
    def test_thread_pair_two_f_threads2(self) -> None:
        """Test register_thread with thread_event_app."""
        #######################################################################
        # two threads - fa2 and fb2 set their own threads
        #######################################################################
        def fa2():
            logger.debug('fa2 entered')
            t_pair = ThreadPair(name='fa2')
            my_fa_thread = threading.current_thread()

            assert t_pair.thread is my_fa_thread
            descs.add_desc(ThreadPairDesc(name='fa2',
                                          thread_pair=t_pair,
                                          thread=my_fa_thread))

            t_pair.pair_with(remote_name='fb2')

            cmds.get_cmd('beta')
            logger.debug('fa2 about to deadlock')
            with pytest.raises(ThreadPairWaitDeadlockDetected):
                logger.debug('fa2 about to wait')
                t_pair.wait()
                logger.debug('fa2 back from wait')

            logger.debug('fa2 about to pause_until')
            t_pair.pause_until(WUCond.RemoteWaiting, timeout=2)
            logger.debug('fa2 about to resume')
            t_pair.resume()

            t_pair.wait()
            logger.debug('fa2 exiting')

        def fb2():
            logger.debug('fb2 entered')
            t_pair = ThreadPair(name='fb2')
            my_fb_thread = threading.current_thread()
            descs.add_desc(ThreadPairDesc(name='fb2',
                                          thread_pair=t_pair,
                                          thread=my_fb_thread))

            assert t_pair.thread is my_fb_thread

            t_pair.pair_with(remote_name='fa2')
            descs.paired('fa2', 'fb2')

            cmds.queue_cmd('beta')
            logger.debug('fb2 about to deadlock')
            with pytest.raises(ThreadPairWaitDeadlockDetected):
                logger.debug('fb2 about to wait')
                t_pair.wait()
                logger.debug('fb2 back from wait')

            logger.debug('fb2 about to pause_until')
            logger.debug('fb2 about to wait')
            t_pair.wait()
            t_pair.resume()

            # tell mainline we are out of the wait - OK to do descs fa1 end
            cmds.queue_cmd('alpha')

            # wait for mainline to give to go ahead after doing descs fa1 end
            cmds.get_cmd('beta')

            logger.debug('fb2 about to try resume for ThreadPairRemoteThreadNotAlive')
            with pytest.raises(ThreadPairRemoteThreadNotAlive):
                t_pair.resume()

            descs.cleanup()

            logger.debug('fb2 about to try wait for ThreadPairRemoteThreadNotAlive')

            with pytest.raises(ThreadPairRemoteThreadNotAlive):
                t_pair.wait()

            logger.debug('fb2 exiting')

        cmds = Cmds()
        descs = ThreadPairDescs()
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
    """Test ThreadPair resume() exceptions."""
    ###########################################################################
    # test_thread_pair_sync_f1
    ###########################################################################
    def test_thread_pair_resume_exc_f1(self) -> None:
        """Test register_thread with f1."""

        def f1():
            logger.debug('f1 beta entered')
            t_pair = ThreadPair(name='beta')
            descs.add_desc(ThreadPairDesc(name='beta',
                                          thread_pair=t_pair,
                                          thread=threading.current_thread()))

            cmds.queue_cmd('alpha')

            t_pair.pair_with(remote_name='alpha')
            descs.paired('alpha', 'beta')

            t_pair.sync(log_msg='f1 beta sync point 1')

            cmds.queue_cmd('alpha', 'go')
            cmds.get_cmd('beta')

            t_pair.sync(log_msg='f1 beta sync point 2')

            t_pair.resume(log_msg='f1 beta resume 3')

            t_pair.sync(log_msg='f1 beta sync point 4')

            logger.debug('f1 beta exiting 5')

        logger.debug('mainline entered')
        cmds = Cmds()
        descs = ThreadPairDescs()
        thread_pair1 = ThreadPair(name='alpha')
        descs.add_desc(ThreadPairDesc(name='alpha',
                                      thread_pair=thread_pair1,
                                      thread=threading.current_thread()))

        f1_thread = threading.Thread(target=f1)

        f1_thread.start()

        cmds.get_cmd('alpha')
        thread_pair1.pair_with(remote_name='beta')

        assert thread_pair1.sync(log_msg='mainline sync point 1')

        cmds.get_cmd('alpha')

        thread_pair1.remote.deadlock = True
        thread_pair1.remote.conflict = True
        with pytest.raises(ThreadPairInconsistentFlagSettings):
            thread_pair1.resume(log_msg='alpha error resume 1a')
        thread_pair1.remote.deadlock = False
        thread_pair1.remote.conflict = False

        thread_pair1.remote.wait_wait = True
        thread_pair1.remote.sync_wait = True
        with pytest.raises(ThreadPairInconsistentFlagSettings):
            thread_pair1.resume(log_msg='alpha error resume 1b')
        thread_pair1.remote.wait_wait = False
        thread_pair1.remote.sync_wait = False

        thread_pair1.remote.deadlock = True
        with pytest.raises(ThreadPairInconsistentFlagSettings):
            thread_pair1.resume(log_msg='alpha error resume 1c')
        thread_pair1.remote.deadlock = False

        thread_pair1.remote.conflict = True
        with pytest.raises(ThreadPairInconsistentFlagSettings):
            thread_pair1.resume(log_msg='alpha error resume 1d')
        thread_pair1.remote.conflict = False

        cmds.queue_cmd('beta', 'go')

        thread_pair1.sync(log_msg='mainline sync point 2')

        thread_pair1.wait(log_msg='mainline wait 3')

        thread_pair1.sync(log_msg='mainline sync point 4')

        f1_thread.join()
        descs.thread_end('beta')

        with pytest.raises(ThreadPairRemoteThreadNotAlive):
            thread_pair1.resume(log_msg='mainline sync point 5')

        descs.cleanup()

        logger.debug('mainline exiting')


###############################################################################
# TestSync Class
###############################################################################
class TestSync:
    """Test ThreadPair sync function."""

    ###########################################################################
    # test_thread_pair_sync_f1
    ###########################################################################
    def test_thread_pair_sync_f1(self) -> None:
        """Test register_thread with f1."""

        def f1():
            logger.debug('f1 beta entered')

            t_pair = ThreadPair(name='beta')
            descs.add_desc(ThreadPairDesc(name='beta',
                                          thread_pair=t_pair,
                                          thread=threading.current_thread()))
            cmds.queue_cmd('alpha')

            t_pair.pair_with(remote_name='alpha')

            t_pair.sync(log_msg='f1 beta sync point 1')

            t_pair.wait()

            t_pair.sync(log_msg='f1 beta sync point 2')

            t_pair.resume()

            t_pair.sync(log_msg='f1 beta sync point 3')

            t_pair.sync(log_msg='f1 beta sync point 4')

            t_pair.wait()

            logger.debug('f1 beta exiting')

        logger.debug('mainline entered')
        cmds = Cmds()
        descs = ThreadPairDescs()
        thread_pair1 = ThreadPair(name='alpha')
        descs.add_desc(ThreadPairDesc(name='alpha',
                                      thread_pair=thread_pair1,
                                      thread=threading.current_thread()))

        f1_thread = threading.Thread(target=f1)

        f1_thread.start()

        cmds.get_cmd('alpha')

        thread_pair1.pair_with(remote_name='beta')
        descs.paired('alpha', 'beta')

        thread_pair1.sync(log_msg='mainline sync point 1')

        thread_pair1.resume()

        thread_pair1.sync(log_msg='mainline sync point 2')

        thread_pair1.wait()

        thread_pair1.sync(log_msg='mainline sync point 3')

        thread_pair1.resume()

        thread_pair1.sync(log_msg='mainline sync point 4')

        f1_thread.join()
        descs.thread_end('beta')

        logger.debug('mainline exiting')

    ###########################################################################
    # test_thread_pair_sync_exc
    ###########################################################################
    def test_thread_pair_sync_exc(self,
                                  thread_exc: Any) -> None:
        """Test register_thread with f1.

        Args:
            thread_exc: capture thread exceptions
        """

        def f1():
            logger.debug('f1 beta entered')

            t_pair = ThreadPair(name='beta')
            descs.add_desc(ThreadPairDesc(name='beta',
                                          thread_pair=t_pair,
                                          thread=threading.current_thread()))
            cmds.queue_cmd('alpha')

            t_pair.pair_with(remote_name='alpha')
            descs.paired('alpha', 'beta')

            assert t_pair.sync(log_msg='f1 beta sync point 1')

            with pytest.raises(ThreadPairConflictDeadlockDetected):
                t_pair.wait(log_msg='f1 beta wait 2')

            assert t_pair.sync(log_msg='f1 beta sync point 3')

            t_pair.resume(log_msg='f1 beta resume 4')

            assert t_pair.sync(log_msg='f1 beta sync point 5')

            assert t_pair.wait(log_msg='f1 beta wait 6')

            t_pair.pause_until(WUCond.RemoteWaiting)

            t_pair.resume()

            assert t_pair.sync(log_msg='f1 beta sync point 8')

            # When one thread issues a sync request, and the other issues a
            # wait request, a conflict deadlock is recognized. The
            # process is of conflict detection is that one side recognizes the
            # conflict, sets a flag to tell the other side that the conflict
            # exists, and then raises the ThreadPairConflictDeadlockDetected error.
            # The other side, upon seeing the conflict flag set, will also
            # raise the ThreadPairConflictDeadlockDetected error.
            # We want to ensure that sync code that detects the conflict is
            # exercised here which requires setting certain flags in a way
            # that coaxes each side into behaving such that the sync
            # detection code will run. We will do this as follows:

            # make sure alpha is in sync code now looping in phase 1
            while not t_pair.remote.sync_wait:
                time.sleep(.1)

            # make alpha think it is in sync phase 2 and continue looping
            # until beta sets sync_cleanup from True back to False
            with t_pair.status.status_lock:
                t_pair.remote.sync_wait = False
                t_pair.status.sync_cleanup = True

            # pre-resume to set beta event and set alpha wait_wait to get beta
            # thinking alpha is resumed and waiting and will eventually
            # leave (i.e., get beta the think that alpha not in a sync
            # deadlock)
            t_pair.resume()
            t_pair.remote.wait_wait = True

            # Now issue the wait. There is no way to prove that alpha saw
            # the deadlock first, but we will see later whether the code
            # coverage will show that the sync detection code ran.
            with pytest.raises(ThreadPairConflictDeadlockDetected):
                t_pair.wait(log_msg='f1 beta wait 89')

            t_pair.status.sync_cleanup = False

            assert t_pair.sync(log_msg='f1 beta sync point 9')

            logger.debug('f1 beta exiting 10')

        logger.debug('mainline entered')
        cmds = Cmds()
        descs = ThreadPairDescs()
        thread_pair1 = ThreadPair(name='alpha')
        descs.add_desc(ThreadPairDesc(name='alpha',
                                      thread_pair=thread_pair1,
                                      thread=threading.current_thread()))

        f1_thread = threading.Thread(target=f1)

        f1_thread.start()

        cmds.get_cmd('alpha')
        thread_pair1.pair_with(remote_name='beta')

        assert thread_pair1.sync(log_msg='mainline sync point 1')

        # See the comments in f1 regarding the detection and handling of a
        # confict deadlock. We need to force the code in the following
        # scenario to behave such that beta will be the side that detects
        # the conflict. This will be done as follows:

        # make sure beta is looping in wait code
        thread_pair1.pause_until(WUCond.RemoteWaiting)

        # set remote.wait_wait to False to trick alpha in the folloiwng
        # sync request to think alpha is NOT in wait request code so
        # that alpha does not detect the conflict.
        thread_pair1.remote.wait_wait = False

        # Issue the sync request. If all goes well, beta will see the conflict
        # first, set the conflict flag and then raise the
        # ThreadPairConflictDeadlockDetected error. We can't prove that it worked out
        # that way, but the coverage report will tell us whether the
        # detection code in wait ran.
        with pytest.raises(ThreadPairConflictDeadlockDetected):
            thread_pair1.sync(log_msg='mainline sync point 2')

        assert thread_pair1.sync(log_msg='mainline sync point 3')

        assert thread_pair1.wait(log_msg='mainline wait 4')

        assert thread_pair1.sync(log_msg='mainline sync point 5')

        thread_pair1.resume(log_msg='mainline resume 6')

        assert not thread_pair1.sync(log_msg='mainline sync point 7',
                                     timeout=0.5)

        assert thread_pair1.wait()

        assert thread_pair1.sync(log_msg='mainline sync point 8')

        # thread will ensure we see conflict first
        with pytest.raises(ThreadPairConflictDeadlockDetected):
            thread_pair1.sync(log_msg='mainline sync point 10')

        logger.debug('mainline about to issue wait to clear trick pre-resume')
        thread_pair1.wait()  # clear the trick pre-resume from beta

        assert thread_pair1.sync(log_msg='mainline sync point 9')

        f1_thread.join()
        descs.thread_end('beta')

        with pytest.raises(ThreadPairRemoteThreadNotAlive):
            thread_pair1.sync(log_msg='mainline sync point 10')

        descs.cleanup()

        logger.debug('mainline exiting 9')


###############################################################################
# TestWaitClear Class
###############################################################################
class TestWaitClear:
    """Test ThreadPair clearing of event set flag."""
    ###########################################################################
    # test_thread_pair_f1_clear
    ###########################################################################
    def test_thread_pair_f1_clear(self) -> None:
        """Test smart event timeout with f1 thread."""

        def f1():
            logger.debug('f1 entered')
            t_pair = ThreadPair(name='beta')
            descs.add_desc(ThreadPairDesc(name='beta',
                                          thread_pair=t_pair,
                                          thread=threading.current_thread()))
            cmds.queue_cmd('alpha')

            t_pair.pair_with(remote_name='alpha')
            descs.paired('alpha', 'beta')

            cmds.start_clock(iter=1)
            assert t_pair.wait()
            assert 2 <= cmds.duration() <= 3
            assert not t_pair.remote.event.is_set()

            cmds.start_clock(iter=2)
            assert t_pair.wait()
            assert 2 <= cmds.duration() <= 3
            assert not t_pair.remote.event.is_set()

            cmds.pause(2, iter=3)
            t_pair.resume()
            cmds.pause(2, iter=4)
            t_pair.resume()

        cmds = Cmds()
        descs = ThreadPairDescs()
        thread_pair = ThreadPair(name='alpha')
        descs.add_desc(ThreadPairDesc(name='alpha',
                                      thread_pair=thread_pair,
                                      thread=threading.current_thread()))

        beta_thread = threading.Thread(target=f1)
        beta_thread.start()

        cmds.get_cmd('alpha')
        thread_pair.pair_with(remote_name='beta')

        cmds.pause(2, iter=1)
        thread_pair.resume()

        cmds.pause(2, iter=2)
        thread_pair.resume()

        cmds.start_clock(iter=3)
        assert thread_pair.wait()
        assert 2 <= cmds.duration() <= 3
        assert not thread_pair.remote.event.is_set()

        cmds.start_clock(iter=4)
        assert thread_pair.wait()
        assert 2 <= cmds.duration() <= 3
        assert not thread_pair.remote.event.is_set()

        beta_thread.join()
        descs.thread_end('beta')

    ###########################################################################
    # test_thread_pair_thread_app_clear
    ###########################################################################
    def test_thread_pair_thread_app_clear(self) -> None:
        """Test smart event timeout with thread_app thread."""

        class MyThread(threading.Thread):
            def __init__(self) -> None:
                super().__init__()
                self.t_pair = ThreadPair(name='beta', thread=self)

            def run(self):
                logger.debug('ThreadApp run entered')

                # t_pair = ThreadPair(name='beta')
                descs.add_desc(ThreadPairDesc(name='beta',
                                              thread_pair=self.t_pair,
                                              thread=self))
                cmds.queue_cmd('alpha')

                self.t_pair.pair_with(remote_name='alpha')

                assert not self.t_pair.remote.event.is_set()
                assert not self.t_pair.event.is_set()

                self.t_pair.sync(log_msg='beta run sync point 1')

                cmds.start_clock(iter=1)

                assert self.t_pair.wait(log_msg='beta run wait 12')

                assert 2 <= cmds.duration() <= 3

                assert not self.t_pair.remote.event.is_set()
                assert not self.t_pair.event.is_set()

                self.t_pair.sync(log_msg='beta run sync point 2')
                cmds.start_clock(iter=2)

                assert self.t_pair.wait(log_msg='beta run wait 23')
                assert 2 <= cmds.duration() <= 3

                assert not self.t_pair.remote.event.is_set()
                assert not self.t_pair.event.is_set()
                self.t_pair.sync(log_msg='beta run sync point 3')

                cmds.pause(2, iter=3)
                self.t_pair.resume(log_msg='beta run resume 34')

                self.t_pair.sync(log_msg='beta run sync point 4')

                cmds.pause(2, iter=4)
                self.t_pair.resume(log_msg='beta run resume 45')

                self.t_pair.sync(log_msg='beta run sync point 5')
                logger.debug('beta run exiting 910')

        cmds = Cmds()
        descs = ThreadPairDescs()
        thread_pair = ThreadPair(name='alpha')
        descs.add_desc(ThreadPairDesc(name='alpha',
                                      thread_pair=thread_pair,
                                      thread=threading.current_thread()))

        thread_app = MyThread()
        thread_app.start()

        cmds.get_cmd('alpha')
        thread_pair.pair_with(remote_name='beta')
        descs.paired('alpha', 'beta')

        thread_pair.sync(log_msg='mainline sync point 1')

        cmds.pause(2, iter=1)

        thread_pair.resume(log_msg='mainline resume 12')

        thread_pair.sync(log_msg='mainline sync point 2')

        cmds.pause(2, iter=2)

        thread_pair.resume(log_msg='mainline resume 23')
        thread_pair.sync(log_msg='mainline sync point 3')
        cmds.start_clock(iter=3)

        assert thread_pair.wait(log_msg='mainline wait 34')

        assert 2 <= cmds.duration() <= 3

        assert not thread_pair.event.is_set()
        assert not thread_pair.remote.event.is_set()

        thread_pair.sync(log_msg='mainline sync point 4')
        cmds.start_clock(iter=4)

        assert thread_pair.wait(log_msg='mainline sync point 45')

        assert 2 <= cmds.duration() <= 3

        assert not thread_pair.event.is_set()
        assert not thread_pair.remote.event.is_set()
        thread_pair.sync(log_msg='mainline sync point 5')

        thread_app.join()
        descs.thread_end('beta')


###############################################################################
# TestThreadPairTimeout Class
###############################################################################
class TestThreadPairTimeout:
    """Test ThreadPair timeout cases."""
    ###########################################################################
    # test_thread_pair_f1_wait_time_out
    ###########################################################################
    def test_thread_pair_f1_wait_time_out(self) -> None:
        """Test smart event wait timeout with f1 thread."""
        def f1():
            logger.debug('f1 entered')

            t_pair = ThreadPair(name='beta')
            descs.add_desc(ThreadPairDesc(name='beta',
                                          thread_pair=t_pair,
                                          thread=threading.current_thread()))
            cmds.queue_cmd('alpha')

            t_pair.pair_with(remote_name='alpha')
            descs.paired('alpha', 'beta')

            t_pair.sync(log_msg='f1 beta sync point 1')
            assert t_pair.wait(timeout=2)
            t_pair.sync(log_msg='f1 beta sync point 2')
            s_time = time.time()
            assert not t_pair.wait(timeout=0.5)
            assert 0.5 <= time.time() - s_time <= 0.75
            t_pair.sync(log_msg='f1 beta sync point 3')
            t_pair.pause_until(WUCond.RemoteWaiting)
            t_pair.resume(log_msg='f1 beta resume 34')
            t_pair.sync(log_msg='f1 beta sync point 4')
            t_pair.sync(log_msg='f1 beta sync point 5')

        cmds = Cmds()
        descs = ThreadPairDescs()
        thread_pair = ThreadPair(name='alpha')
        descs.add_desc(ThreadPairDesc(name='alpha',
                                      thread_pair=thread_pair,
                                      thread=threading.current_thread()))

        beta_thread = threading.Thread(target=f1)

        beta_thread.start()

        cmds.get_cmd('alpha')
        thread_pair.pair_with(remote_name='beta')

        thread_pair.pause_until(WUCond.ThreadsReady)
        thread_pair.sync(log_msg='mainline sync point 1')
        thread_pair.pause_until(WUCond.RemoteWaiting)
        thread_pair.resume(log_msg='mainline resume 12')
        thread_pair.sync(log_msg='mainline sync point 2')
        thread_pair.sync(log_msg='mainline sync point 3')
        assert thread_pair.wait(timeout=2)
        thread_pair.sync(log_msg='mainline sync point 4')
        start_time = time.time()
        assert not thread_pair.wait(timeout=0.75)
        assert 0.75 <= time.time() - start_time <= 1
        thread_pair.sync(log_msg='mainline sync point 5')

        beta_thread.join()
        descs.thread_end('beta')

    ###########################################################################
    # test_thread_pair_f1_resume_time_out
    ###########################################################################
    def test_thread_pair_f1_resume_time_out(self) -> None:
        """Test smart event wait timeout with f1 thread."""

        def f1() -> None:
            """The remote thread for requests."""
            logger.debug('f1 entered')

            t_pair = ThreadPair(name='beta')
            descs.add_desc(ThreadPairDesc(name='beta',
                                          thread_pair=t_pair,
                                          thread=threading.current_thread()))
            cmds.queue_cmd('alpha')

            t_pair.pair_with(remote_name='alpha')

            # t_pair.sync(log_msg='f1 beta sync point 1')

            # the first resume will set the flag ON and the flag will stay ON
            # since there is no matching wait
            assert not t_pair.event.is_set()
            assert t_pair.resume(timeout=2)
            assert t_pair.event.is_set()

            # this second resume will timeout waiting for the flag to go OFF
            cmds.start_clock(iter=1)
            assert not t_pair.resume(timeout=0.5)
            assert 0.5 <= cmds.duration() <= 0.75
            assert t_pair.event.is_set()

            t_pair.sync(log_msg='f1 beta sync point 1')
            t_pair.sync(log_msg='f1 beta sync point 2')

            # this first resume will complete within the timeout
            t_pair.remote.wait_wait = True  # simulate waiting
            t_pair.remote.deadlock = True  # simulate deadlock
            cmds.start_clock(iter=2)
            assert t_pair.resume(timeout=1)
            assert 0.5 <= cmds.duration() <= 0.75

            # t_pair.sync(log_msg='f1 beta sync point 3')
            t_pair.sync(log_msg='f1 beta sync point 4')

            # this resume will timeout
            t_pair.remote.wait_wait = True  # simulate waiting
            t_pair.remote.deadlock = True  # simulate deadlock

            cmds.start_clock(iter=3)
            assert not t_pair.resume(timeout=0.5)
            assert 0.5 <= cmds.duration() <= 0.75

            t_pair.sync(log_msg='f1 beta sync point 5')
            t_pair.sync(log_msg='f1 beta sync point 6')

            # this wait will clear the flag - use timeout to prevent f1 beta
            # sync from raising ThreadPairConflictDeadlockDetected
            assert t_pair.wait(log_msg='f1 beta wait 67',
                                timeout=1)

            t_pair.sync(log_msg='f1 beta sync point 7')

            cmds.pause(0.5, iter=5)  # we purposely skipped 4
            # clear the deadlock within the resume timeout to allow mainline
            # resume to complete
            t_pair.deadlock = False
            t_pair.wait_wait = False

            t_pair.sync(log_msg='f1 beta sync point 8')

            cmds.pause(0.75, iter=6)
            # clear the deadlock after resume timeout to cause ml to timeout
            t_pair.deadlock = False
            t_pair.wait_wait = False

            t_pair.sync(log_msg='f1 beta sync point 9')

        cmds = Cmds()
        descs = ThreadPairDescs()
        thread_pair = ThreadPair(name='alpha')
        descs.add_desc(ThreadPairDesc(name='alpha',
                                      thread_pair=thread_pair,
                                      thread=threading.current_thread()))

        beta_thread = threading.Thread(target=f1)

        beta_thread.start()

        cmds.get_cmd('alpha')
        thread_pair.pair_with(remote_name='beta')
        descs.paired('alpha', 'beta')

        thread_pair.pause_until(WUCond.ThreadsReady)
        thread_pair.sync(log_msg='mainline sync point 1')

        # this wait will clear the flag - use timeout to prevent sync
        # from raising ThreadPairConflictDeadlockDetected
        assert thread_pair.remote.event.is_set()
        assert thread_pair.wait(log_msg='mainline wait 12',
                                timeout=1)

        assert not thread_pair.wait_timeout_specified
        thread_pair.sync(log_msg='mainline sync point 2')

        cmds.pause(0.5, iter=2)  # we purposely skipped iter=1

        # clear the deadlock within resume timeout to allow f1 resume to
        # complete
        thread_pair.deadlock = False
        thread_pair.wait_wait = False

        # thread_pair.sync(log_msg='mainline sync point 3')
        thread_pair.sync(log_msg='mainline sync point 4')

        cmds.pause(0.75, iter=3)

        # clear the deadlock after the resume timeout to cause f1 to timeout
        thread_pair.deadlock = False
        thread_pair.wait_wait = False

        thread_pair.sync(log_msg='mainline sync point 5')

        # the first resume will set the flag ON and the flag will stay ON
        # since there is no matching wait
        assert thread_pair.resume(timeout=2)

        # this second resume will timeout waiting for the flag to go OFF
        cmds.start_clock(iter=4)
        assert not thread_pair.resume(timeout=0.3)
        assert 0.3 <= cmds.duration() <= 0.6

        thread_pair.sync(log_msg='mainline sync point 6')
        thread_pair.sync(log_msg='mainline sync point 7')

        # this first resume will complete within the timeout
        thread_pair.remote.wait_wait = True  # simulate waiting
        thread_pair.remote.deadlock = True  # simulate deadlock
        cmds.start_clock(iter=5)
        assert thread_pair.resume(timeout=1)
        assert 0.5 <= cmds.duration() <= 0.75

        thread_pair.sync(log_msg='mainline sync point 8')

        # this resume will timeout
        thread_pair.remote.wait_wait = True  # simulate waiting
        thread_pair.remote.deadlock = True  # simulate deadlock
        cmds.start_clock(iter=6)
        assert not thread_pair.resume(timeout=0.5)
        assert 0.5 <= cmds.duration() <= 0.75

        thread_pair.sync(log_msg='mainline sync point 9')

        beta_thread.join()
        descs.thread_end('beta')

    ###########################################################################
    # test_thread_pair_thread_app_time_out
    ###########################################################################
    def test_thread_pair_thread_app_time_out(self) -> None:
        """Test smart event timeout with thread_app thread."""
        class MyThread(threading.Thread):
            def __init__(self):
                super().__init__()
                self.t_pair = ThreadPair(name='beta', thread=self)

            def run(self):
                logger.debug('ThreadApp run entered')

                descs.add_desc(ThreadPairDesc(name='beta',
                                              thread_pair=self.t_pair,
                                              thread=self))
                cmds.queue_cmd('alpha')

                self.t_pair.pair_with(remote_name='alpha')
                descs.paired('alpha', 'beta')

                cmds.start_clock(iter=1)
                assert not self.t_pair.wait(timeout=2)
                assert 2 <= cmds.duration() < 3

                assert self.t_pair.sync(log_msg='beta sync point 1')
                assert self.t_pair.sync(log_msg='beta sync point 2')

        cmds = Cmds()
        descs = ThreadPairDescs()
        thread_pair = ThreadPair(name='alpha')
        descs.add_desc(ThreadPairDesc(name='alpha',
                                      thread_pair=thread_pair,
                                      thread=threading.current_thread()))

        thread_app = MyThread()
        thread_app.start()

        cmds.get_cmd('alpha')
        thread_pair.pair_with(remote_name='beta')

        assert thread_pair.sync(log_msg='alpha sync point 1')

        cmds.start_clock(iter=2)
        assert not thread_pair.wait(timeout=2)
        assert 2 <= cmds.duration() < 3

        assert thread_pair.sync(log_msg='alpha sync point 2')

        thread_app.join()
        descs.thread_end('beta')


###############################################################################
# TestThreadPairCode Class
###############################################################################
class TestThreadPairCode:
    """Test ThreadPair resume codes."""
    ###########################################################################
    # test_thread_pair_f1_event_code
    ###########################################################################
    def test_thread_pair_f1_event_code(self) -> None:
        """Test smart event code with f1 thread."""
        def f1():
            logger.debug('f1 entered')

            t_pair = ThreadPair(name='beta')
            descs.add_desc(ThreadPairDesc(name='beta',
                                          thread_pair=t_pair,
                                          thread=threading.current_thread()))
            cmds.queue_cmd('alpha')

            t_pair.pair_with(remote_name='alpha')

            assert not t_pair.remote.code
            assert not t_pair.code
            assert not t_pair.get_code()

            t_pair.sync(log_msg='beta sync point 1')

            assert t_pair.wait(timeout=2)
            assert not t_pair.remote.code
            assert t_pair.code == 42
            assert 42 == t_pair.get_code()

            t_pair.sync(log_msg='beta sync point 2')

            t_pair.resume(code='forty-two')
            assert t_pair.remote.code == 'forty-two'
            assert t_pair.code == 42
            assert 42 == t_pair.get_code()

            t_pair.sync(log_msg='beta sync point 3')

            assert t_pair.remote.code == 'forty-two'
            assert t_pair.code == 42
            assert 42 == t_pair.get_code()

            assert not t_pair.wait(timeout=.5)

            assert t_pair.remote.code == 'forty-two'
            assert t_pair.code == 42
            assert 42 == t_pair.get_code()

            t_pair.sync(log_msg='beta sync point 4')
            t_pair.sync(log_msg='beta sync point 5')

            assert t_pair.remote.code == 'forty-two'
            assert t_pair.code == 'twenty one'
            assert 'twenty one' == t_pair.get_code()
            assert t_pair.remote.event.is_set()

        cmds = Cmds()
        descs = ThreadPairDescs()
        thread_pair = ThreadPair(name='alpha')
        descs.add_desc(ThreadPairDesc(name='alpha',
                                      thread_pair=thread_pair,
                                      thread=threading.current_thread()))

        beta_thread = threading.Thread(target=f1)

        beta_thread.start()

        cmds.get_cmd('alpha')
        thread_pair.pair_with(remote_name='beta')
        descs.paired('alpha', 'beta')

        thread_pair.sync(log_msg='mainline sync point 1')

        assert not thread_pair.get_code()
        assert not thread_pair.code
        assert not thread_pair.remote.code

        thread_pair.resume(code=42)

        assert not thread_pair.get_code()
        assert not thread_pair.code
        assert thread_pair.remote.code == 42

        thread_pair.sync(log_msg='mainline sync point 2')

        assert thread_pair.wait()

        assert thread_pair.get_code() == 'forty-two'
        assert thread_pair.code == 'forty-two'
        assert thread_pair.remote.code == 42

        thread_pair.sync(log_msg='mainline sync point 3')
        thread_pair.sync(log_msg='mainline sync point 4')

        thread_pair.resume(code='twenty one')

        thread_pair.sync(log_msg='mainline sync point 5')

        beta_thread.join()
        thread_pair.code = None
        thread_pair.remote.code = None

        descs.thread_end('beta')

    ###########################################################################
    # test_thread_pair_thread_app_event_code
    ###########################################################################
    def test_thread_pair_thread_app_event_code(self) -> None:
        """Test smart event code with thread_app thread."""

        class MyThread(threading.Thread):
            def __init__(self):
                super().__init__()
                self.t_pair = ThreadPair(name='beta', thread=self)

            def run(self):
                logger.debug('ThreadApp run entered')

                descs.add_desc(ThreadPairDesc(name='beta',
                                              thread_pair=self.t_pair,
                                              thread=self))
                cmds.queue_cmd('alpha')

                self.t_pair.pair_with(remote_name='alpha')
                descs.paired('alpha', 'beta')

                assert self.t_pair.get_code() is None
                assert not self.t_pair.wait(timeout=2, log_msg='beta wait 1')

                self.t_pair.sync(log_msg='beta sync point 2')
                self.t_pair.sync(log_msg='beta sync point 3')

                assert self.t_pair.remote.event.is_set()
                assert self.t_pair.code == 42
                assert self.t_pair.get_code() == 42

                self.t_pair.resume(log_msg='beta resume 4',
                                    code='forty-two')

        cmds = Cmds()
        descs = ThreadPairDescs()
        thread_pair = ThreadPair(name='alpha')
        descs.add_desc(ThreadPairDesc(name='alpha',
                                      thread_pair=thread_pair,
                                      thread=threading.current_thread()))

        thread_app = MyThread()
        thread_app.start()

        cmds.get_cmd('alpha')
        thread_pair.pair_with(remote_name='beta')

        thread_pair.pause_until(WUCond.ThreadsReady)

        thread_pair.sync(log_msg='mainline sync point 2')
        thread_pair.resume(code=42)
        thread_pair.sync(log_msg='mainline sync point 3')

        assert thread_pair.wait(log_msg='mainline wait 4')
        assert thread_pair.get_code() == 'forty-two'

        thread_app.join()

        thread_pair.code = None
        thread_pair.remote.code = None

        descs.thread_end('beta')

    ###########################################################################
    # test_thread_pair_thread_event_app_event_code
    ###########################################################################
    def test_thread_pair_thread_event_app_event_code(self) -> None:
        """Test smart event code with thread_event_app thread."""
        class MyThread(threading.Thread, ThreadPair):
            def __init__(self) -> None:
                threading.Thread.__init__(self)
                ThreadPair.__init__(self, name='beta', thread=self)

            def run(self):
                logger.debug('ThreadApp run entered')

                descs.add_desc(ThreadPairDesc(name='beta',
                                              thread_pair=self,
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
        descs = ThreadPairDescs()
        thread_event_app = MyThread()
        thread_event_app.start()

        cmds.get_cmd('alpha')

        time.sleep(2)  # make beta loop in pair_with
        thread_pair = ThreadPair(name='alpha')
        descs.add_desc(ThreadPairDesc(name='alpha',
                                      thread_pair=thread_pair,
                                      thread=threading.current_thread()))

        thread_pair.pair_with(remote_name='beta')
        descs.paired('alpha', 'beta')

        assert not thread_pair.code
        assert not thread_pair.remote.code
        assert not thread_pair.get_code()

        thread_pair.sync(log_msg='mainline sync point 1')
        thread_pair.sync(log_msg='mainline sync point 2')

        assert not thread_pair.code
        assert not thread_pair.remote.code
        assert not thread_pair.get_code()

        thread_pair.resume(code=42, log_msg='mainline resume for beta 56')

        assert not thread_pair.code
        assert thread_pair.remote.code == 42
        assert not thread_pair.get_code()

        thread_pair.sync(log_msg='mainline sync point 3')
        thread_pair.sync(log_msg='mainline sync point 4')

        assert thread_pair.code == 'forty-two'
        assert thread_pair.remote.code == 42
        assert thread_pair.get_code() == 'forty-two'

        assert thread_pair.wait()

        assert thread_pair.code == 'forty-two'
        assert thread_pair.remote.code == 42
        assert thread_pair.get_code() == 'forty-two'

        thread_pair.sync(log_msg='mainline sync point 5')

        assert thread_pair.code == 'forty-two'
        assert thread_pair.remote.code == 42
        assert thread_pair.get_code() == 'forty-two'

        thread_pair.sync(log_msg='mainline sync point 6')

        thread_event_app.join()

        thread_pair.code = None
        thread_pair.remote.code = None

        descs.thread_end('beta')


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

            t_pair = ThreadPair(name='beta')
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

        thread_pair = ThreadPair(name='alpha')
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
                self.t_pair = ThreadPair(name='beta', thread=self)
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

        thread_pair = ThreadPair(name='alpha')
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
                ThreadPair.__init__(self, name='beta', thread=self)
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

        thread_pair = ThreadPair(name='alpha')
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
                self.thread_pair = ThreadPair(name='beta', thread=self)
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
        thread_pair = ThreadPair(name='alpha')
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
        t_pair = ThreadPair(name='beta')

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
