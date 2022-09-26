"""test_smart_thread.py module."""

###############################################################################
# Standard Library
###############################################################################
from datetime import datetime
from enum import Enum
import logging
import queue
import re
import time
from typing import Any, Callable, cast, Final, Optional, Union
import threading

###############################################################################
# Third Party
###############################################################################
import pytest
from scottbrian_utils.msgs import Msgs, GetMsgTimedOut
from scottbrian_utils.log_verifier import LogVer

###############################################################################
# Local
###############################################################################
from .conftest import Cmds, ThreadPairDesc, ThreadPairDescs, ExpLogMsgs

import scottbrian_paratools.smart_thread as st

# from scottbrian_paratools.smart_thread import (
#     SmartThread,
#     SmartThreadAlreadyPairedWithRemote,
#     SmartThreadDetectedOpFromForeignThread,
#     SmartThreadErrorInRegistry,
#     SmartThreadIncorrectNameSpecified,
#     SmartThreadIncorrectGroupNameSpecified,
#     SmartThreadNameAlreadyInUse,
#     SmartThreadNotPaired,
#     SmartThreadPairWithSelfNotAllowed,
#     SmartThreadPairWithTimedOut,
#     SmartThreadRemoteThreadNotAlive,
#     SmartThreadRemotePairedWithOther)

import logging

logger = logging.getLogger(__name__)
logger.debug('about to start the tests')


###############################################################################
# SmartThread test exceptions
###############################################################################
class ErrorTstSmartThread(Exception):
    """Base class for exception in this module."""
    pass


class IncorrectActionSpecified(ErrorTstSmartThread):
    """IncorrectActionSpecified exception class."""
    pass


class UnrecognizedCmd(ErrorTstSmartThread):
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


# ###############################################################################
# # TestSmartThreadBasic class to test SmartThread methods
# ###############################################################################
# ###############################################################################
# # Theta class
# ###############################################################################
# class Theta(SmartThread):
#     """Theta test class."""
#     def __init__(self,
#                  group_name: str,
#                  name: str,
#                  thread: Optional[threading.Thread] = None) -> None:
#         """Initialize the Theta object.
#
#         Args:
#             name: name of the Theta
#             thread: thread to use instead of threading.current_thread()
#
#         """
#         SmartThread.__init__(self, group_name=group_name, name=name, thread=thread)
#         self.var1 = 'theta'
#
#
# ###############################################################################
# # ThetaDesc class
# ###############################################################################
# class ThetaDesc(SmartThreadDesc):
#     """Describes a Theta with name and thread to verify."""
#     def __init__(self,
#                  group_name: Optional[str] = 'group1',
#                  name: Optional[str] = '',
#                  theta: Optional[Theta] = None,
#                  thread: Optional[threading.Thread] = None,  # type: ignore
#                  state: Optional[int] = 0,  # 0 is unknown
#                  paired_with: Optional[Any] = None) -> None:
#         """Initialize the ThetaDesc.
#
#         Args:
#             name: name of the Theta
#             theta: the Theta being tracked by this desc
#             thread: the thread associated with this Theta
#             state: describes whether the Theta is alive and registered
#             paired_with: names the Theta paired with this one, if one
#
#         """
#         SmartThreadDesc.__init__(self,
#                                 smart_thread=theta,
#                                 state=state,
#                                 paired_with=paired_with)
#
#     def verify_state(self) -> None:
#         """Verify the state of the Theta."""
#         SmartThreadDesc.verify_state(self)
#         self.verify_theta_desc()
#         if self.paired_with is not None:
#             self.paired_with.verify_theta_desc()
#
#     ###########################################################################
#     # verify_theta_desc
#     ###########################################################################
#     def verify_theta_desc(self) -> None:
#         """Verify the Theta object is initialized correctly."""
#         assert isinstance(self.smart_thread, Theta)
#
#         assert self.smart_thread.var1 == 'theta'
#
#
# ###############################################################################
# # Sigma class
# ###############################################################################
# class Sigma(SmartThread):
#     """Sigma test class."""
#     def __init__(self,
#                  group_name: str,
#                  name: str,
#                  thread: Optional[threading.Thread] = None) -> None:
#         """Initialize the Sigma object.
#
#         Args:
#             name: name of the Sigma
#             thread: thread to use instead of threading.current_thread()
#
#         """
#         SmartThread.__init__(self, group_name=group_name, name=name, thread=thread)
#         self.var1 = 17
#         self.var2 = 'sigma'
#
#
# ###############################################################################
# # SigmaDesc class
# ###############################################################################
# class SigmaDesc(SmartThreadDesc):
#     """Describes a Sigma with name and thread to verify."""
#     def __init__(self,
#                  group_name: Optional[str] = 'group1',
#                  name: Optional[str] = '',
#                  sigma: Optional[Sigma] = None,
#                  thread: Optional[threading.Thread] = None,  # type: ignore
#                  state: Optional[int] = 0,  # 0 is unknown
#                  paired_with: Optional[Any] = None) -> None:
#         """Initialize the SigmaDesc.
#
#         Args:
#             name: name of the Sigma
#             sigma: the Sigma being tracked by this desc
#             thread: the thread associated with this Sigma
#             state: describes whether the Sigma is alive and registered
#             paired_with: names the Sigma paired with this one, if one
#
#         """
#         SmartThreadDesc.__init__(self,
#                                 smart_thread=sigma,
#                                 state=state,
#                                 paired_with=paired_with)
#
#     def verify_state(self) -> None:
#         """Verify the state of the Sigma."""
#         SmartThreadDesc.verify_state(self)
#         self.verify_sigma_desc()
#         if self.paired_with is not None:
#             self.paired_with.verify_sigma_desc()
#
#     ###########################################################################
#     # verify_sigma_desc
#     ###########################################################################
#     def verify_sigma_desc(self) -> None:
#         """Verify the Sigma object is initialized correctly."""
#         assert isinstance(self.smart_thread, Sigma)
#
#         assert self.smart_thread.var1 == 17
#         assert self.smart_thread.var2 == 'sigma'
#
#
# ###############################################################################
# # Omega class
# ###############################################################################
# class Omega(SmartThread):
#     """Omega test class."""
#     def __init__(self,
#                  group_name: str,
#                  name: str,
#                  thread: Optional[threading.Thread] = None) -> None:
#         """Initialize the Omega object.
#
#         Args:
#             name: name of the Omega
#             thread: thread to use instead of threading.current_thread()
#
#         """
#         SmartThread.__init__(self, group_name=group_name, name=name, thread=thread)
#         self.var1 = 42
#         self.var2 = 64.9
#         self.var3 = 'omega'
#
#
# ###############################################################################
# # OmegaDesc class
# ###############################################################################
# class OmegaDesc(SmartThreadDesc):
#     """Describes a Omega with name and thread to verify."""
#     def __init__(self,
#                  group_name: Optional[str] = 'group1',
#                  name: Optional[str] = '',
#                  omega: Optional[Omega] = None,
#                  thread: Optional[threading.Thread] = None,  # type: ignore
#                  state: Optional[int] = 0,  # 0 is unknown
#                  paired_with: Optional[Any] = None) -> None:
#         """Initialize the OmegaDesc.
#
#         Args:
#             name: name of the Omega
#             omega: the Omega being tracked by this desc
#             thread: the thread associated with this Omega
#             state: describes whether the Omega is alive and registered
#             paired_with: names the Omega paired with this one, if one
#
#         """
#         SmartThreadDesc.__init__(self,
#                                 smart_thread=omega,
#                                 state=state,
#                                 paired_with=paired_with)
#
#     def verify_state(self) -> None:
#         """Verify the state of the Omega."""
#         SmartThreadDesc.verify_state(self)
#         self.verify_omega_desc()
#         if self.paired_with is not None:
#             self.paired_with.verify_omega_desc()
#
#     ###########################################################################
#     # verify_omega_desc
#     ###########################################################################
#     def verify_omega_desc(self) -> None:
#         """Verify the Omega object is initialized correctly."""
#         assert isinstance(self.smart_thread, Omega)
#
#         assert self.smart_thread.var1 == 42
#         assert self.smart_thread.var2 == 64.9
#         assert self.smart_thread.var3 == 'omega'
#
#
# ###############################################################################
# # outer_f1
# ###############################################################################
# def outer_f1(cmds: Cmds,
#              descs: SmartThreadDescs,
#              ) -> None:
#     """Outer function to test SmartThread.
#
#     Args:
#         cmds: Cmds object to tell alpha when to go
#         descs: tracks set of SmartThreadDesc items
#
#     """
#     logger.debug('outer_f1 entered')
#     t_pair = SmartThread(group_name='group1', name='beta')
#     descs.add_desc(SmartThreadDesc(smart_thread=t_pair))
#
#     # tell alpha OK to verify (i.e., beta_smart_thread set with t_pair)
#     cmds.queue_cmd('alpha', 'go')
#
#     t_pair.pair_with(remote_name='alpha')
#
#     cmds.get_cmd('beta')
#
#     logger.debug('outer f1 exiting')
#
#
# ###############################################################################
# # OuterThreadApp class
# ###############################################################################
# class OuterThreadApp(threading.Thread):
#     """Outer thread app for test."""
#     def __init__(self,
#                  cmds: Cmds,
#                  descs: SmartThreadDescs
#                  ) -> None:
#         """Initialize the object.
#
#         Args:
#             cmds: used to tell alpha to go
#             descs: tracks set of SmartThreadDescs items
#
#         """
#         super().__init__()
#         self.cmds = cmds
#         self.descs = descs
#         self.t_pair = SmartThread(group_name='group1', name='beta', thread=self)
#
#     def run(self) -> None:
#         """Run the test."""
#         print('beta run started')
#
#         # normally, the add_desc is done just after the instantiation, but
#         # in this case the thread is not made alive until now, and the
#         # add_desc checks that the thread is alive
#         self.descs.add_desc(SmartThreadDesc(smart_thread=self.t_pair))
#
#         self.cmds.queue_cmd('alpha')
#
#         self.t_pair.pair_with(remote_name='alpha')
#         self.descs.paired('alpha', 'beta')
#
#         self.cmds.get_cmd('beta')
#
#         logger.debug('beta run exiting')
#
#
# ###############################################################################
# # OuterThreadEventApp class
# ###############################################################################
# class OuterThreadEventApp(threading.Thread, SmartThread):
#     """Outer thread event app for test."""
#     def __init__(self,
#                  cmds: Cmds,
#                  descs: SmartThreadDescs) -> None:
#         """Initialize the object.
#
#         Args:
#             cmds: used to send cmds between threads
#             descs: tracks set of SmartThreadDesc items
#
#         """
#         threading.Thread.__init__(self)
#         SmartThread.__init__(self, group_name='group1', name='beta', thread=self)
#         self.cmds = cmds
#         self.descs = descs
#
#     def run(self):
#         """Run the test."""
#         print('beta run started')
#
#         # normally, the add_desc is done just after the instantiation, but
#         # in this case the thread is not made alive until now, and the
#         # add_desc checks that the thread is alive
#         self.descs.add_desc(SmartThreadDesc(smart_thread=self))
#
#         self.cmds.queue_cmd('alpha')
#
#         self.pair_with(remote_name='alpha', timeout=3)
#         self.descs.paired('alpha', 'beta')
#
#         self.cmds.get_cmd('beta')
#
#         logger.debug('beta run exiting')
#

########################################################################
# TestSmartThreadErrors class
########################################################################
class TestSmartThreadErrors:
    """Test class for SmartThread error tests."""
    ####################################################################
    # Basic Scenario1
    ####################################################################
    def test_smart_thread_instantiation_errors(self):
        ################################################################
        # f1
        ################################################################
        def f1():
            logger.debug('f1 entered')
            logger.debug('f1 exiting')

        ####################################################################
        # Create smart thread with bad name
        ####################################################################
        logger.debug('mainline entered')

        logger.debug('mainline creating bad name thread')

        with pytest.raises(st.SmartThreadIncorrectNameSpecified):
            _ = st.SmartThread(name=1)

        test_thread = threading.Thread(target=f1)
        with pytest.raises(
                st.SmartThreadMutuallyExclusiveTargetThreadSpecified):

            _ = st.SmartThread(name='alpha', target=f1, thread=test_thread)

        with pytest.raises(st.SmartThreadArgsSpecificationWithoutTarget):
            _ = st.SmartThread(name='alpha', args=(1,))

        alpha_thread = st.SmartThread(name='alpha')
        alpha_thread.name = 1
        with pytest.raises(st.SmartThreadIncorrectNameSpecified):
            alpha_thread._register()

        # we still have alpha with name changed to 1
        # which will cause the following registry error
        # when we try to create another thread
        with pytest.raises(st.SmartThreadErrorInRegistry):
            _ = st.SmartThread(name='alpha')

        alpha_thread.name = 'alpha'  # restore name

        with pytest.raises(st.SmartThreadNameAlreadyInUse):
            _ = st.SmartThread(name='alpha')

        logger.debug('mainline exiting')

    def test_smart_thread_refresh_remote_array_errors(
            self,
            caplog: pytest.CaptureFixture[str]
            ) -> None:
        """Test error cases in the _regref remote array method.

        Args:
            caplog: pytest fixture to capture log output

        """
        ################################################################
        # f1
        ################################################################
        def f1(name: str):
            log_msg_f1 = 'f1 entered'
            log_ver.add_msg(log_level=logging.DEBUG,
                            log_msg=log_msg_f1)
            logger.debug(log_msg_f1)

            ############################################################
            # send msg to alpha
            ############################################################
            beta_thread.send_msg(targets='alpha', msg='go now')

            log_msg_f1 = 'beta entered _refresh_remote_array'
            log_ver.add_msg(
                log_name='scottbrian_paratools.smart_thread',
                log_level=logging.DEBUG,
                log_msg=log_msg_f1)

            update_time_f1 = (beta_thread.time_last_pair_array_update
                              .strftime("%H:%M:%S.%f"))
            log_msg_f1 = re.escape(
                'beta updated registry and remote_array at UTC '
                f'{update_time_f1}')
            log_ver.add_msg(
                log_name='scottbrian_paratools.smart_thread',
                log_level=logging.DEBUG,
                log_msg=log_msg_f1)

            log_msg_f1 = 'beta entered _refresh_remote_array'
            log_ver.add_msg(
                log_name='scottbrian_paratools.smart_thread',
                log_level=logging.DEBUG,
                log_msg=log_msg_f1)

            log_msg_f1 = f'beta sending message to alpha'
            log_ver.add_msg(
                log_name='scottbrian_paratools.smart_thread',
                log_level=logging.INFO,
                log_msg=log_msg_f1)

            ############################################################
            # recv msg from alpha
            ############################################################
            msg1 = beta_thread.recv_msg(remote='alpha', timeout=3)

            log_msg_f1 = 'beta receiving msg from alpha'
            log_ver.add_msg(
                log_name='scottbrian_paratools.smart_thread',
                log_level=logging.INFO,
                log_msg=log_msg_f1)

            log_msg_f1 = f'beta received msg: {msg1}'
            log_ver.add_msg(log_level=logging.DEBUG,
                            log_msg=log_msg_f1)
            logger.debug(log_msg_f1)

            ############################################################
            # recv second msg from alpha
            ############################################################
            msg2 = beta_thread.recv_msg(remote='alpha', timeout=3)

            log_msg_f1 = 'beta receiving msg from alpha'
            log_ver.add_msg(
                log_name='scottbrian_paratools.smart_thread',
                log_level=logging.INFO,
                log_msg=log_msg_f1)

            log_msg_f1 = f'beta received msg: {msg2}'
            log_ver.add_msg(log_level=logging.DEBUG,
                            log_msg=log_msg_f1)
            logger.debug(log_msg_f1)

            ############################################################
            # recv third msg from alpha
            ############################################################
            msg3 = beta_thread.recv_msg(remote='alpha', timeout=3)

            log_msg_f1 = 'beta receiving msg from alpha'
            log_ver.add_msg(
                log_name='scottbrian_paratools.smart_thread',
                log_level=logging.INFO,
                log_msg=log_msg_f1)

            log_msg_f1 = f'beta received msg: {msg3}'
            log_ver.add_msg(log_level=logging.DEBUG,
                            log_msg=log_msg_f1)
            logger.debug(log_msg_f1)

            ############################################################
            # exit
            ############################################################
            log_msg_f1 = 'f1 exiting'
            log_ver.add_msg(log_level=logging.DEBUG,
                            log_msg=log_msg_f1)
            logger.debug(log_msg_f1)

        ################################################################
        # Set up log verification and start tests
        ################################################################
        log_ver = LogVer(
            log_name='test_scottbrian_paratools.test_smart_thread')
        alpha_call_seq = (
            'test_smart_thread.py::TestSmartThreadErrors'
            '.test_smart_thread_refresh_remote_array_errors')
        log_ver.add_call_seq(name='alpha',
                             seq=alpha_call_seq)

        log_msg = 'mainline entered'
        log_ver.add_msg(log_level=logging.DEBUG,
                        log_msg=log_msg)
        logger.debug(log_msg)

        ################################################################
        # Create alpha smart thread
        ################################################################
        log_msg = 'mainline creating alpha smart thread'
        log_ver.add_msg(log_level=logging.DEBUG,
                        log_msg=log_msg)
        logger.debug(log_msg)

        alpha_thread = st.SmartThread(name='alpha')

        log_msg = 'status for thread alpha set to ThreadStatus.Initializing'
        log_ver.add_msg(
            log_name='scottbrian_paratools.smart_thread',
            log_level=logging.DEBUG,
            log_msg=log_msg)

        log_msg = ('alpha obtained _registry_lock, '
                   'class name = SmartThread')
        log_ver.add_msg(
            log_name='scottbrian_paratools.smart_thread',
            log_level=logging.DEBUG,
            log_msg=log_msg)

        log_msg = 'alpha registered'
        log_ver.add_msg(
            log_name='scottbrian_paratools.smart_thread',
            log_level=logging.DEBUG,
            log_msg=log_msg)

        log_msg = (
            'alpha did register update at UTC '
            f'{st.SmartThread._registry_last_update.strftime("%H:%M:%S.%f")}')

        log_ver.add_msg(
            log_name='scottbrian_paratools.smart_thread',
            log_level=logging.DEBUG,
            log_msg=log_msg)

        log_msg = 'status for thread alpha set to ThreadStatus.Alive'
        log_ver.add_msg(
            log_name='scottbrian_paratools.smart_thread',
            log_level=logging.DEBUG,
            log_msg=log_msg)

        ################################################################
        # Create beta smart thread
        ################################################################
        log_msg = 'mainline creating beta smart thread'
        log_ver.add_msg(log_level=logging.DEBUG,
                        log_msg=log_msg)
        logger.debug(log_msg)

        beta_thread = st.SmartThread(name='beta', target=f1, args=('beta',))

        log_msg = 'status for thread beta set to ThreadStatus.Initializing'
        log_ver.add_msg(
            log_name='scottbrian_paratools.smart_thread',
            log_level=logging.DEBUG,
            log_msg=log_msg)

        log_msg = ('beta obtained _registry_lock, '
                   'class name = SmartThread')
        log_ver.add_msg(
            log_name='scottbrian_paratools.smart_thread',
            log_level=logging.DEBUG,
            log_msg=log_msg)

        log_msg = re.escape(
            "key = alpha, item = SmartThread(name='alpha'), "
            "item.thread.is_alive() = True, status: ThreadStatus.Alive")
        log_ver.add_msg(
            log_name='scottbrian_paratools.smart_thread',
            log_level=logging.DEBUG,
            log_msg=log_msg)

        log_msg = 'beta registered'
        log_ver.add_msg(
            log_name='scottbrian_paratools.smart_thread',
            log_level=logging.DEBUG,
            log_msg=log_msg)

        log_msg = (
            'beta did register update at UTC '
            f'{st.SmartThread._registry_last_update.strftime("%H:%M:%S.%f")}')
        log_ver.add_msg(
            log_name='scottbrian_paratools.smart_thread',
            log_level=logging.DEBUG,
            log_msg=log_msg)

        log_msg = 'status for thread beta set to ThreadStatus.Registered'
        log_ver.add_msg(
            log_name='scottbrian_paratools.smart_thread',
            log_level=logging.DEBUG,
            log_msg=log_msg)

        ################################################################
        # Start beta thread
        ################################################################
        beta_thread.start()

        log_msg = 'status for thread beta set to ThreadStatus.Starting'
        log_ver.add_msg(
            log_name='scottbrian_paratools.smart_thread',
            log_level=logging.DEBUG,
            log_msg=log_msg)

        log_msg = re.escape(
            'beta thread started, thread.is_alive() = True, '
            'status: ThreadStatus.Alive')
        log_ver.add_msg(
            log_name='scottbrian_paratools.smart_thread',
            log_level=logging.DEBUG,
            log_msg=log_msg)

        ################################################################
        # Recv msg from beta
        ################################################################
        time.sleep(.5)
        log_msg = 'mainline alpha receiving msg from beta'
        log_ver.add_msg(log_level=logging.DEBUG,
                        log_msg=log_msg)
        logger.debug(log_msg)

        alpha_thread.recv_msg(remote='beta', timeout=3)

        log_msg = 'alpha entered _refresh_remote_array'
        log_ver.add_msg(
            log_name='scottbrian_paratools.smart_thread',
            log_level=logging.DEBUG,
            log_msg=log_msg)

        update_time = (alpha_thread.time_last_pair_array_update
                       .strftime("%H:%M:%S.%f"))
        log_msg = re.escape(
            'alpha updated registry and remote_array at UTC '
            f'{update_time}')
        log_ver.add_msg(
            log_name='scottbrian_paratools.smart_thread',
            log_level=logging.DEBUG,
            log_msg=log_msg)

        log_msg = f'alpha receiving msg from beta'
        log_ver.add_msg(
            log_name='scottbrian_paratools.smart_thread',
            log_level=logging.INFO,
            log_msg=log_msg)

        ################################################################
        # Corrupt remote array first time to cause error
        ################################################################
        log_msg = 'mainline alpha corrupting remote array'
        log_ver.add_msg(log_level=logging.DEBUG,
                        log_msg=log_msg)
        logger.debug(log_msg)
        alpha_thread.remote_array['beta'].remote_smart_thread = alpha_thread
        alpha_thread.time_last_remote_check = datetime(2000, 1, 1, 12, 0, 1)

        ################################################################
        # Send msg to beta (should cause error)
        ################################################################
        log_msg = 'mainline alpha sending message to beta'
        log_ver.add_msg(log_level=logging.DEBUG,
                        log_msg=log_msg)
        logger.debug(log_msg)

        with pytest.raises(st.SmartThreadRemoteSmartThreadMismatch):
            alpha_thread.send_msg(targets='beta',
                                  msg='proceed1',
                                  timeout=3)

        log_msg = f'alpha entered _refresh_remote_array'
        log_ver.add_msg(
            log_name='scottbrian_paratools.smart_thread',
            log_level=logging.DEBUG,
            log_msg=log_msg)

        # log_msg = f'beta entered _refresh_remote_array'
        # log_ver.add_msg(
        #     log_name='scottbrian_paratools.smart_thread',
        #     log_level=logging.DEBUG,
        #     log_msg=log_msg)
        ################################################################
        # Restore remote array
        ################################################################
        log_msg = 'mainline alpha restoring remote array'
        log_ver.add_msg(log_level=logging.DEBUG,
                        log_msg=log_msg)
        logger.debug(log_msg)

        alpha_thread.remote_array['beta'].remote_smart_thread = beta_thread

        ################################################################
        # Send msg to beta (should be OK this time)
        ################################################################
        log_msg = 'mainline alpha sending msg to beta second time'
        log_ver.add_msg(log_level=logging.DEBUG,
                        log_msg=log_msg)
        logger.debug(log_msg)

        alpha_thread.send_msg(targets='beta',
                              msg='proceed1',
                              timeout=3)

        log_msg = f'alpha entered _refresh_remote_array'
        log_ver.add_msg(
            log_name='scottbrian_paratools.smart_thread',
            log_level=logging.DEBUG,
            log_msg=log_msg)

        log_msg = f'alpha sending message to beta'
        log_ver.add_msg(
            log_name='scottbrian_paratools.smart_thread',
            log_level=logging.INFO,
            log_msg=log_msg)

        ################################################################
        # Corrupt remote array second time to cause error
        ################################################################
        log_msg = 'mainline alpha corrupting remote array second time'
        log_ver.add_msg(log_level=logging.DEBUG,
                        log_msg=log_msg)
        logger.debug(log_msg)

        # set a new lock into beta remote array entry for alpha
        beta_thread.remote_array['alpha'].status_lock = threading.Lock()

        alpha_thread.time_last_remote_check = datetime(2000, 1, 1, 12, 0, 1)

        ################################################################
        # Send msg to beta (should cause error)
        ################################################################
        log_msg = 'mainline alpha sending message to beta'
        log_ver.add_msg(log_level=logging.DEBUG,
                        log_msg=log_msg)
        logger.debug(log_msg)

        with pytest.raises(st.SmartThreadStatusLockMismatch):
            alpha_thread.send_msg(targets='beta',
                                  msg='proceeed2',
                                  timeout=3)

        log_msg = f'alpha entered _refresh_remote_array'
        log_ver.add_msg(
            log_name='scottbrian_paratools.smart_thread',
            log_level=logging.DEBUG,
            log_msg=log_msg)

        ################################################################
        # Restore remote array
        ################################################################
        log_msg = 'mainline alpha restoring remote array'
        log_ver.add_msg(log_level=logging.DEBUG,
                        log_msg=log_msg)
        logger.debug(log_msg)

        beta_thread.remote_array['alpha'].status_lock = (
            alpha_thread.remote_array['beta'].status_lock)

        ################################################################
        # Send msg to beta (should be OK this time)
        ################################################################
        log_msg = 'mainline alpha sending msg to beta fourth time'
        log_ver.add_msg(log_level=logging.DEBUG,
                        log_msg=log_msg)
        logger.debug(log_msg)

        alpha_thread.send_msg(targets='beta',
                              msg='proceeed2',
                              timeout=3)

        log_msg = f'alpha entered _refresh_remote_array'
        log_ver.add_msg(
            log_name='scottbrian_paratools.smart_thread',
            log_level=logging.DEBUG,
            log_msg=log_msg)

        log_msg = f'alpha sending message to beta'
        log_ver.add_msg(
            log_name='scottbrian_paratools.smart_thread',
            log_level=logging.INFO,
            log_msg=log_msg)

        ################################################################
        # Corrupt remote array third time to cause error
        ################################################################
        log_msg = 'mainline alpha corrupting remote array third time'
        log_ver.add_msg(log_level=logging.DEBUG,
                        log_msg=log_msg)
        logger.debug(log_msg)

        # set a new queue into beta remote array entry for alpha
        beta_thread.remote_array['alpha'].remote_msg_q = queue.Queue()

        alpha_thread.time_last_remote_check = datetime(2000, 1, 1, 12, 0, 1)

        ################################################################
        # Send msg to beta (should cause error)
        ################################################################
        log_msg = 'mainline alpha sending message to beta'
        log_ver.add_msg(log_level=logging.DEBUG,
                        log_msg=log_msg)
        logger.debug(log_msg)

        with pytest.raises(st.SmartThreadRemoteMsgQMismatch):
            alpha_thread.send_msg(targets='beta',
                                  msg='exit',
                                  timeout=3)

        log_msg = f'alpha entered _refresh_remote_array'
        log_ver.add_msg(
            log_name='scottbrian_paratools.smart_thread',
            log_level=logging.DEBUG,
            log_msg=log_msg)

        ################################################################
        # Restore remote array
        ################################################################
        log_msg = 'mainline alpha restoring remote array'
        log_ver.add_msg(log_level=logging.DEBUG,
                        log_msg=log_msg)
        logger.debug(log_msg)

        beta_thread.remote_array['alpha'].remote_msg_q = (
            alpha_thread.remote_array['beta'].msg_q)

        ################################################################
        # Send msg to beta (should be OK this time)
        ################################################################
        log_msg = 'mainline alpha sending msg to beta fourth time'
        log_ver.add_msg(log_level=logging.DEBUG,
                        log_msg=log_msg)
        logger.debug(log_msg)

        alpha_thread.send_msg(targets='beta',
                              msg='exit',
                              timeout=3)

        log_msg = f'alpha entered _refresh_remote_array'
        log_ver.add_msg(
            log_name='scottbrian_paratools.smart_thread',
            log_level=logging.DEBUG,
            log_msg=log_msg)

        log_msg = f'alpha sending message to beta'
        log_ver.add_msg(
            log_name='scottbrian_paratools.smart_thread',
            log_level=logging.INFO,
            log_msg=log_msg)
        ################################################################
        # Join beta
        ################################################################
        alpha_thread.join(targets='beta')

        log_msg = 'beta removed from registry'
        log_ver.add_msg(
            log_name='scottbrian_paratools.smart_thread',
            log_level=logging.DEBUG,
            log_msg=log_msg)

        log_msg = 'alpha did successful join of beta.'
        log_ver.add_msg(
            log_name='scottbrian_paratools.smart_thread',
            log_level=logging.DEBUG,
            log_msg=log_msg)

        log_msg = re.escape(
            "key = alpha, item = SmartThread(name='alpha'), "
            "item.thread.is_alive() = True")
        log_ver.add_msg(
            log_name='scottbrian_paratools.smart_thread',
            log_level=logging.DEBUG,
            log_msg=log_msg)

        log_msg = re.escape(
            "key = beta, item = SmartThread(name='beta', target=f1, "
            "args=('beta',)), item.thread.is_alive() = False")
        log_ver.add_msg(
            log_name='scottbrian_paratools.smart_thread',
            log_level=logging.DEBUG,
            log_msg=log_msg)

        log_msg = re.escape(
            "alpha did cleanup of registry at UTC "
            f'{st.SmartThread._registry_last_update.strftime("%H:%M:%S.%f")}, '
            "deleted ['beta']")
        log_ver.add_msg(
            log_name='scottbrian_paratools.smart_thread',
            log_level=logging.DEBUG,
            log_msg=log_msg)

        ################################################################
        # verify logger messages
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results)
        # log_ver.verify_log_results(match_results)

        logger.debug('mainline exiting')



    def test_smart_thread_refresh_remote_array_errors2(self):
        ################################################################
        # f1
        ################################################################
        def f1(name: str):
            logger.debug('f1 entered')
            if name == 'beta':
                msg1 = beta_thread.recv_msg(remote='alpha')
            else:
                charlie_thread.send_msg(targets='alpha', msg='go now')
                msg1 = charlie_thread.recv_msg(remote='alpha', timeout=3)
            logger.debug(f'{name} received msg: {msg1}')
            logger.debug('f1 exiting')

        ####################################################################
        # Create smart thread with bad name
        ####################################################################
        logger.debug('mainline entered')

        logger.debug('mainline creating alpha smart thread')
        alpha_thread = st.SmartThread(name='alpha')

        logger.debug('mainline creating beta smart thread')
        beta_thread = st.SmartThread(name='beta', target=f1, args=('beta',))
        beta_thread.start()

        logger.debug('mainline alpha sending msg to beta')

        alpha_thread.send_msg(targets='beta',
                              msg='exit',
                              timeout=3)
        alpha_thread.join(targets='beta')

        logger.debug('mainline creating charlie smart thread')
        charlie_thread = st.SmartThread(name='charlie',
                                        target=f1,
                                        args=('charlie',))
        charlie_thread.start()

        logger.debug('mainline alpha sending msg to charlie')
        msg = alpha_thread.recv_msg(remote='charlie', timeout=3)

        logger.debug('mainline alpha corrupting remote array')
        alpha_thread.remote_array['charlie'].remote_smart_thread = alpha_thread
        alpha_thread.time_last_pair_array_update = datetime(2000, 1, 1, 12, 0, 1)
        logger.debug('mainline alpha sending msg to charlie')
        with pytest.raises(st.SmartThreadRemoteSmartThreadMismatch):
            alpha_thread.send_msg(targets='charlie',
                                  msg='exit',
                                  timeout=3)
        logger.debug('mainline alpha restoring remote array')
        alpha_thread.remote_array['charlie'].remote_smart_thread = \
            charlie_thread
        alpha_thread.send_msg(targets='charlie',
                              msg='exit',
                              timeout=3)
        alpha_thread.join(targets='charlie')

        logger.debug('mainline exiting')


########################################################################
# TestSmartThreadLogMsgs class
########################################################################
########################################################################
# set_expected_log_msgs
########################################################################
def set_create_expected_log_msgs(
        smart_thread: st.SmartThread,
        log_ver: LogVer,
        existing_threads: Optional[list[st.SmartThread]] = None
        ) -> None:
    name = smart_thread.name
    log_msg = (
        f'{name} set status for thread {name} '
        'from undefined to ThreadStatus.Initializing')
    log_ver.add_msg(
        log_name='scottbrian_paratools.smart_thread',
        log_level=logging.DEBUG,
        log_msg=log_msg)

    log_msg = (f'{name} obtained _registry_lock, '
               'class name = SmartThread')
    log_ver.add_msg(
        log_name='scottbrian_paratools.smart_thread',
        log_level=logging.DEBUG,
        log_msg=log_msg)

    if existing_threads:
        for a_thread in existing_threads:
            log_msg = re.escape(
                f"key = {a_thread.name}, item = {a_thread}, "
                f"item.thread.is_alive() = {a_thread.thread.is_alive()}, "
                f"status: {a_thread.status}")
            log_ver.add_msg(
                log_name='scottbrian_paratools.smart_thread',
                log_level=logging.DEBUG,
                log_msg=log_msg)

    log_msg = (
        f'{name} set status for thread {name} '
        'from ThreadStatus.Initializing to ThreadStatus.Registered')
    log_ver.add_msg(
        log_name='scottbrian_paratools.smart_thread',
        log_level=logging.DEBUG,
        log_msg=log_msg)

    log_msg = f'{name} entered _refresh_pair_array'
    log_ver.add_msg(
        log_name='scottbrian_paratools.smart_thread',
        log_level=logging.DEBUG,
        log_msg=log_msg)

    if ((smart_thread.thread_create & st.ThreadCreate.Current)
            or not smart_thread.auto_start):
        log_msg = (
            f'{name} set status for thread {name} '
            f'from ThreadStatus.Registered to ThreadStatus.Alive')
        log_ver.add_msg(
            log_name='scottbrian_paratools.smart_thread',
            log_level=logging.DEBUG,
            log_msg=log_msg)

    if existing_threads:
        for a_thread in existing_threads:
            if name < a_thread.name:
                pair_key = (name, a_thread.name)
            else:
                pair_key = (a_thread.name, name)

            log_msg = re.escape(
                f"{name} created "
                "_refresh_pair_array with "
                f"pair_key = {pair_key}")
            log_ver.add_msg(
                log_name='scottbrian_paratools.smart_thread',
                log_level=logging.DEBUG,
                log_msg=log_msg)

            for pair_name in pair_key:
                log_msg = re.escape(
                    f"{name} added status_blocks entry "
                    f"for pair_key = {pair_key}, "
                    f"name = {pair_name}")
                log_ver.add_msg(
                    log_name='scottbrian_paratools.smart_thread',
                    log_level=logging.DEBUG,
                    log_msg=log_msg)

    update_time = (smart_thread.time_last_pair_array_update
                   .strftime("%H:%M:%S.%f"))
    log_msg = re.escape(
        f'{name} updated _pair_array at UTC '
        f'{update_time}')
    log_ver.add_msg(
        log_name='scottbrian_paratools.smart_thread',
        log_level=logging.DEBUG,
        log_msg=log_msg)

    log_msg = (
        f'{name} did register update at UTC '
        f'{st.SmartThread._registry_last_update.strftime("%H:%M:%S.%f")}')

    log_ver.add_msg(
        log_name='scottbrian_paratools.smart_thread',
        log_level=logging.DEBUG,
        log_msg=log_msg)

    if smart_thread.auto_started:
        log_msg = (
            f'{name} set status for thread {name} '
            'from ThreadStatus.Registered to ThreadStatus.Starting')
        log_ver.add_msg(
            log_name='scottbrian_paratools.smart_thread',
            log_level=logging.DEBUG,
            log_msg=log_msg)

        log_msg = (
            f'{name} set status for thread {name} '
            f'from ThreadStatus.Starting to ThreadStatus.Alive')
        log_ver.add_msg(
            log_name='scottbrian_paratools.smart_thread',
            log_level=logging.DEBUG,
            log_msg=log_msg)

        log_msg = re.escape(
            f'{name} thread started, '
            f'thread.is_alive() = {smart_thread.thread.is_alive()}, '
            'status: ThreadStatus.Alive')
        log_ver.add_msg(
            log_name='scottbrian_paratools.smart_thread',
            log_level=logging.DEBUG,
            log_msg=log_msg)

def set_join_expected_log_msgs(
        smart_thread: st.SmartThread,
        log_ver: LogVer,
        targets: list[st.SmartThread],
        existing_threads: Optional[list[st.SmartThread]] = None
        ) -> None:

    name = smart_thread.name

    if existing_threads:
        for a_thread in existing_threads:
            if name < a_thread.name:
                pair_key = (name, a_thread.name)
            else:
                pair_key = (a_thread.name, name)

        log_msg = re.escape(
            "key = alpha, item = SmartThread(name='alpha'), "
            "item.thread.is_alive() = True, status: ThreadStatus.Alive")
        log_ver.add_msg(
            log_name='scottbrian_paratools.smart_thread',
            log_level=logging.DEBUG,
            log_msg=log_msg)

        log_msg = re.escape(
            "key = beta, item = SmartThread(name='beta', target=f1, "
            "args=('beta',)), item.thread.is_alive() = False, "
            "status: ThreadStatus.Stopped")
        log_ver.add_msg(
            log_name='scottbrian_paratools.smart_thread',
            log_level=logging.DEBUG,
            log_msg=log_msg)

    for a_targ in targets:
        log_msg = f'{a_targ.name} removed from registry'
        log_ver.add_msg(
            log_name='scottbrian_paratools.smart_thread',
            log_level=logging.DEBUG,
            log_msg=log_msg)

        log_msg = f'{name} entered _refresh_pair_array'
        log_ver.add_msg(
            log_name='scottbrian_paratools.smart_thread',
            log_level=logging.DEBUG,
            log_msg=log_msg)

        if existing_threads:
            for a_thread in existing_threads:
                if a_targ.name < a_thread.name:
                    pair_key = (a_targ.name, a_thread.name)
                else:
                    pair_key = (a_thread.name, a_targ.name)
                log_msg = re.escape(
                    f"{name} removed status_blocks entry "
                    f"for pair_key = {pair_key}, "
                    f"name = {a_targ.name}")
                log_ver.add_msg(
                    log_name='scottbrian_paratools.smart_thread',
                    log_level=logging.DEBUG,
                    log_msg=log_msg)
                if not st.SmartThread._pair_array[
                        pair_key].status_blocks:
                    log_msg = (
                        f'{name} removed _pair_array entry'
                        f' for pair_key = {pair_key}')
                    log_ver.add_msg(
                        log_name='scottbrian_paratools.smart_thread',
                        log_level=logging.DEBUG,
                        log_msg=log_msg)


        update_time = (smart_thread.time_last_pair_array_update
                          .strftime("%H:%M:%S.%f"))
        log_msg = re.escape(
            f'{name} updated _pair_array at UTC '
            f'{update_time}')
        log_ver.add_msg(
            log_name='scottbrian_paratools.smart_thread',
            log_level=logging.DEBUG,
            log_msg=log_msg)

        log_msg = re.escape(
            f"{name} did cleanup of registry at UTC "
            f'{st.SmartThread._registry_last_update.strftime("%H:%M:%S.%f")}, '
            f"deleted ['{a_targ.name}']")
        log_ver.add_msg(
            log_name='scottbrian_paratools.smart_thread',
            log_level=logging.DEBUG,
            log_msg=log_msg)

        log_msg = f'{name} did successful join of {a_targ.name}.'
        log_ver.add_msg(
            log_name='scottbrian_paratools.smart_thread',
            log_level=logging.DEBUG,
            log_msg=log_msg)


class TestSmartThreadLogMsgs:
    """Test class for SmartThread log msgs."""
    ####################################################################
    # test_refresh_pair_array_log_msgs
    ####################################################################
    def test_refresh_pair_array_log_msgs(
            self,
            caplog: pytest.CaptureFixture[str]
            ) -> None:
        """Test log msgs for _refresh_pair_array.

        Args:
            caplog: pytest fixture to capture log output

        """
        ################################################################
        # f1
        ################################################################
        def f1(name: str):
            log_msg_f1 = 'f1 entered'
            log_ver.add_msg(log_level=logging.DEBUG,
                            log_msg=log_msg_f1)
            logger.debug(log_msg_f1)

            msgs.get_msg('beta')

            ############################################################
            # send msg to alpha
            ############################################################
            beta_thread.send_msg(targets='alpha', msg='go now')

            log_msg_f1 = f'beta sending message to alpha'
            log_ver.add_msg(
                log_name='scottbrian_paratools.smart_thread',
                log_level=logging.INFO,
                log_msg=log_msg_f1)

            # ############################################################
            # # recv msg from alpha
            # ############################################################
            # msg1 = beta_thread.recv_msg(remote='alpha', timeout=3)
            #
            # log_msg_f1 = 'beta receiving msg from alpha'
            # log_ver.add_msg(
            #     log_name='scottbrian_paratools.smart_thread',
            #     log_level=logging.INFO,
            #     log_msg=log_msg_f1)
            #
            # log_msg_f1 = f'beta received msg: {msg1}'
            # log_ver.add_msg(log_level=logging.DEBUG,
            #                 log_msg=log_msg_f1)
            # logger.debug(log_msg_f1)
            #
            # ############################################################
            # # recv second msg from alpha
            # ############################################################
            # msg2 = beta_thread.recv_msg(remote='alpha', timeout=3)
            #
            # log_msg_f1 = 'beta receiving msg from alpha'
            # log_ver.add_msg(
            #     log_name='scottbrian_paratools.smart_thread',
            #     log_level=logging.INFO,
            #     log_msg=log_msg_f1)
            #
            # log_msg_f1 = f'beta received msg: {msg2}'
            # log_ver.add_msg(log_level=logging.DEBUG,
            #                 log_msg=log_msg_f1)
            # logger.debug(log_msg_f1)
            #
            # ############################################################
            # # recv third msg from alpha
            # ############################################################
            # msg3 = beta_thread.recv_msg(remote='alpha', timeout=3)
            #
            # log_msg_f1 = 'beta receiving msg from alpha'
            # log_ver.add_msg(
            #     log_name='scottbrian_paratools.smart_thread',
            #     log_level=logging.INFO,
            #     log_msg=log_msg_f1)
            #
            # log_msg_f1 = f'beta received msg: {msg3}'
            # log_ver.add_msg(log_level=logging.DEBUG,
            #                 log_msg=log_msg_f1)
            # logger.debug(log_msg_f1)

            ############################################################
            # exit
            ############################################################
            log_msg_f1 = 'f1 exiting'
            log_ver.add_msg(log_level=logging.DEBUG,
                            log_msg=log_msg_f1)
            logger.debug(log_msg_f1)

        ################################################################
        # Set up log verification and start tests
        ################################################################
        log_ver = LogVer(
            log_name='test_scottbrian_paratools.test_smart_thread')
        alpha_call_seq = (
            'test_smart_thread.py::TestSmartThreadLogMsgs'
            '.test_refresh_pair_array_log_msgs')
        log_ver.add_call_seq(name='alpha',
                             seq=alpha_call_seq)

        log_msg = 'mainline entered'
        log_ver.add_msg(log_msg=log_msg)
        logger.debug(log_msg)

        msgs = Msgs()

        ################################################################
        # Create alpha smart thread
        ################################################################
        log_msg = 'mainline creating alpha smart thread'
        log_ver.add_msg(log_level=logging.DEBUG,
                        log_msg=log_msg)
        logger.debug(log_msg)

        alpha_thread = st.SmartThread(name='alpha')

        set_create_expected_log_msgs(alpha_thread, log_ver)

        ################################################################
        # Create beta smart thread
        ################################################################
        log_msg = 'mainline creating beta smart thread'
        log_ver.add_msg(log_level=logging.DEBUG,
                        log_msg=log_msg)
        logger.debug(log_msg)

        beta_thread = st.SmartThread(name='beta', target=f1, args=('beta',))

        set_create_expected_log_msgs(beta_thread, log_ver, [alpha_thread])

        msgs.queue_msg('beta')  # tell beta to proceed

        ################################################################
        # Start beta thread
        ################################################################
        # beta_thread.start()
        #
        # log_msg = (
        #     'beta set status for thread beta '
        #     'from ThreadStatus.Registered to ThreadStatus.Starting')
        # log_ver.add_msg(
        #     log_name='scottbrian_paratools.smart_thread',
        #     log_level=logging.DEBUG,
        #     log_msg=log_msg)
        #
        # log_msg = (
        #     f'beta set status for thread beta '
        #     f'from ThreadStatus.Starting to ThreadStatus.Alive')
        # log_ver.add_msg(
        #     log_name='scottbrian_paratools.smart_thread',
        #     log_level=logging.DEBUG,
        #     log_msg=log_msg)
        #
        # log_msg = re.escape(
        #     'beta thread started, thread.is_alive() = True, '
        #     'status: ThreadStatus.Alive')
        # log_ver.add_msg(
        #     log_name='scottbrian_paratools.smart_thread',
        #     log_level=logging.DEBUG,
        #     log_msg=log_msg)

        ################################################################
        # Recv msg from beta
        ################################################################
        time.sleep(.5)
        log_msg = 'mainline alpha receiving msg from beta'
        log_ver.add_msg(log_level=logging.DEBUG,
                        log_msg=log_msg)
        logger.debug(log_msg)

        alpha_thread.recv_msg(remote='beta', timeout=3)

        log_msg = f'alpha receiving msg from beta'
        log_ver.add_msg(
            log_name='scottbrian_paratools.smart_thread',
            log_level=logging.INFO,
            log_msg=log_msg)

        ################################################################
        # Join beta
        ################################################################
        alpha_thread.join(targets='beta')

        set_join_expected_log_msgs(alpha_thread, log_ver, [beta_thread],
                                   [alpha_thread])

        # log_msg = re.escape(
        #     "key = alpha, item = SmartThread(name='alpha'), "
        #     "item.thread.is_alive() = True, status: ThreadStatus.Alive")
        # log_ver.add_msg(
        #     log_name='scottbrian_paratools.smart_thread',
        #     log_level=logging.DEBUG,
        #     log_msg=log_msg)
        #
        # log_msg = re.escape(
        #     "key = beta, item = SmartThread(name='beta', target=f1, "
        #     "args=('beta',)), item.thread.is_alive() = False, "
        #     "status: ThreadStatus.Stopped")
        # log_ver.add_msg(
        #     log_name='scottbrian_paratools.smart_thread',
        #     log_level=logging.DEBUG,
        #     log_msg=log_msg)
        #
        # log_msg = 'beta removed from registry'
        # log_ver.add_msg(
        #     log_name='scottbrian_paratools.smart_thread',
        #     log_level=logging.DEBUG,
        #     log_msg=log_msg)
        #
        # log_msg = 'alpha entered _refresh_pair_array'
        # log_ver.add_msg(
        #     log_name='scottbrian_paratools.smart_thread',
        #     log_level=logging.DEBUG,
        #     log_msg=log_msg)
        #
        # log_msg = re.escape(
        #     "alpha removed status_blocks entry "
        #     "for pair_key = ('alpha', 'beta'), name = beta")
        # log_ver.add_msg(
        #     log_name='scottbrian_paratools.smart_thread',
        #     log_level=logging.DEBUG,
        #     log_msg=log_msg)
        #
        # update_time_f1 = (alpha_thread.time_last_pair_array_update
        #                   .strftime("%H:%M:%S.%f"))
        # log_msg = re.escape(
        #     'alpha updated _pair_array at UTC '
        #     f'{update_time_f1}')
        # log_ver.add_msg(
        #     log_name='scottbrian_paratools.smart_thread',
        #     log_level=logging.DEBUG,
        #     log_msg=log_msg)
        #
        # log_msg = re.escape(
        #     "alpha did cleanup of registry at UTC "
        #     f'{st.SmartThread._registry_last_update.strftime("%H:%M:%S.%f")}, '
        #     "deleted ['beta']")
        # log_ver.add_msg(
        #     log_name='scottbrian_paratools.smart_thread',
        #     log_level=logging.DEBUG,
        #     log_msg=log_msg)
        #
        # log_msg = 'alpha did successful join of beta.'
        # log_ver.add_msg(
        #     log_name='scottbrian_paratools.smart_thread',
        #     log_level=logging.DEBUG,
        #     log_msg=log_msg)

        ################################################################
        # verify logger messages
        ################################################################
        time.sleep(1)
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results)
        log_ver.verify_log_results(match_results)

        logger.debug('mainline exiting')


########################################################################
# TestSmartThreadBasic class
########################################################################
class TestSmartThreadBasic:
    """Test class for SmartThread basic tests."""
    ####################################################################
    # Basic Scenario1
    ####################################################################
    def test_smart_thread_with_msg_mixin1(self):

        ################################################################
        # f1
        ################################################################
        def f1():
            logger.debug('f1 entered')

            msgs.get_msg('beta')


            # beta_smart_thread.wait(remote='alpha', log_msg='f1 wait 1')
            # beta_smart_thread.sync(targets='alpha', log_msg='f1 sync 2')
            beta_smart_thread.send_msg(msg='hi alpha, this is beta',
                                       targets='alpha',
                                       log_msg='f1 send_msg 3')
            assert beta_smart_thread.recv_msg(remote='alpha',
                                              log_msg='f1 recv_msg 4',
                                              timeout=3) == (
                                                  'hi beta, this is alpha')
            # beta_smart_thread.resume(targets='alpha', log_msg='f1 resume 5')
            msgs.queue_msg('alpha')
            logger.debug('f1 exiting')

        ####################################################################
        # Create smart threads for the main thread (this thread) and f1
        ####################################################################
        logger.debug('mainline entered')
        logger.debug('mainline creating alpha thread')

        alpha_smart_thread = st.SmartThread(name='alpha')

        logger.debug('mainline creating beta thread')

        msgs = Msgs()

        beta_smart_thread = st.SmartThread(name='beta', target=f1)
        beta_smart_thread.start()

        ####################################################################
        # Interact with beta
        ####################################################################
        logger.debug('mainline interacting with beta')

        msgs.queue_msg('beta')  # tell beta to proceed

        # alpha_smart_thread.resume(targets='beta', log_msg='ml resume 1')
        # alpha_smart_thread.sync(targets='beta', log_msg='ml sync 2')
        assert alpha_smart_thread.recv_msg(remote='beta',
                                           log_msg='ml recv_msg 3',
                                           timeout=3) == (
                                               'hi alpha, this is beta')
        alpha_smart_thread.send_msg(msg='hi beta, this is alpha', targets='beta', log_msg='ml send_msg 4')
        # alpha_smart_thread.wait(remote='beta', log_msg='f1 resume 5')
        # # alpha_smart_thread.join(targets='beta', log_msg='ml join 6')
        msgs.get_msg('alpha')  # wait for beta to tell us to proceed
        beta_smart_thread.thread.join()

        assert not beta_smart_thread.thread.is_alive()

        logger.debug('mainline exiting')
    ####################################################################
    # Basic Scenario1
    ####################################################################
    def test_smart_thread_basic_scenario1(self):

        ################################################################
        # f1
        ################################################################
        def f1():
            logger.debug('f1 entered')

            msgs.get_msg('beta')
            msgs.queue_msg('alpha')

            # beta_smart_thread.wait(remote='alpha', log_msg='f1 wait 1')
            # beta_smart_thread.sync(targets='alpha', log_msg='f1 sync 2')
            # beta_smart_thread.send_msg(msg='hi alpha, this is beta', targets='alpha', log_msg='f1 send_msg 3')
            # assert beta_smart_thread.recv_msg(remote='alpha', log_msg='f1 recv_msg 4') == 'hi beta, this is alpha'
            # beta_smart_thread.resume(targets='alpha', log_msg='f1 resume 5')

            logger.debug('f1 exiting')

        ####################################################################
        # Create smart threads for the main thread (this thread) and f1
        ####################################################################
        logger.debug('mainline entered')
        logger.debug('mainline creating alpha thread')
        alpha_smart_thread = st.SmartThread(name='alpha')

        logger.debug('mainline creating beta thread')

        msgs = Msgs()

        beta_smart_thread = st.SmartThread(name='beta', target=f1)
        beta_smart_thread.start()

        ####################################################################
        # Interact with beta
        ####################################################################
        logger.debug('mainline interacting with beta')

        msgs.queue_msg('beta')
        msgs.get_msg('alpha')
        # alpha_smart_thread.resume(targets='beta', log_msg='ml resume 1')
        # alpha_smart_thread.sync(targets='beta', log_msg='ml sync 2')
        # assert alpha_smart_thread.recv_msg(remote='beta', log_msg='ml recv_msg 3') == 'hi alpha, this is beta'
        # alpha_smart_thread.send_msg(msg='hi beta, this is alpha', targets='beta', log_msg='ml send_msg 4')
        # alpha_smart_thread.wait(remote='beta', log_msg='f1 resume 5')
        # # alpha_smart_thread.join(targets='beta', log_msg='ml join 6')

        beta_smart_thread.thread.join()

        assert not beta_smart_thread.thread.is_alive()

        logger.debug('mainline exiting')

    ####################################################################################################################
    # Basic Scenario2
    ####################################################################################################################
    def test_smart_thread_basic_scenario2(self):
        ####################################################################
        # f1
        ####################################################################
        def f1():
            logger.debug('f1 entered')
            logger.debug(f'SmartThread._registry = {st.SmartThread._registry}')
            beta_smart_thread.wait(remote='alpha', log_msg='f1 wait 1')
            beta_smart_thread.sync(targets='alpha', log_msg='f1 sync 2')
            beta_smart_thread.send_msg(msg='hi alpha, this is beta', targets='alpha', log_msg='f1 send_msg 3')
            assert beta_smart_thread.recv_msg(remote='alpha', log_msg='f1 recv_msg 4') == 'hi beta, this is alpha'
            beta_smart_thread.resume(targets='alpha', log_msg='f1 resume 5')

            beta_smart_thread.wait(remote='charlie', log_msg='f1 wait 6')
            beta_smart_thread.sync(targets='charlie', log_msg='f1 sync 7')
            beta_smart_thread.send_msg(msg='hi charlie, this is beta', targets='charlie', log_msg='f1 send_msg 8')
            assert beta_smart_thread.recv_msg(remote='charlie', log_msg='f1 recv_msg 9') == 'hi beta, this is charlie'
            beta_smart_thread.resume(targets='charlie', log_msg='f1 resume 10')

            logger.debug('f1 exiting')

        ####################################################################
        # f2
        ####################################################################
        def f2():
            logger.debug('f2 entered')

            charlie_smart_thread.wait(remote='alpha', log_msg='f2 wait 1')
            charlie_smart_thread.sync(targets='alpha', log_msg='f2 sync 2')
            charlie_smart_thread.send_msg(msg='hi alpha, this is charlie', targets='alpha', log_msg='f2 send_msg 3')
            assert charlie_smart_thread.recv_msg(remote='alpha', log_msg='f2 recv_msg 4') == 'hi charlie, this is alpha'
            charlie_smart_thread.resume(targets='alpha', log_msg='f2 resume 5')

            charlie_smart_thread.resume(targets='beta', log_msg='f2 resume 6')
            charlie_smart_thread.sync(targets='beta', log_msg='f2 sync 7')
            assert charlie_smart_thread.recv_msg(remote='beta', log_msg='f2 recv_msg 9') == 'hi charlie, this is beta'
            charlie_smart_thread.send_msg(msg='hi beta, this is charlie', targets='beta', log_msg='f2 send_msg 8')
            charlie_smart_thread.wait(remote='beta', log_msg='f2 wait 10')

            logger.debug('f2 exiting')

        ####################################################################
        # Create smart threads for the main thread (this thread), f1, and f2
        ####################################################################
        logger.debug('mainline entered')
        logger.debug('mainline creating alpha thread')
        alpha_smart_thread = st.SmartThread(name='alpha')

        logger.debug('mainline creating beta thread')
        # beta_thread = threading.Thread(name='beta', target=f1)
        beta_smart_thread = st.SmartThread(name='beta', target=f1)
        beta_smart_thread.thread.start()
        logger.debug('mainline creating charlie thread')
        # charlie_thread = threading.Thread(name='charlie', target=f2)
        charlie_smart_thread = st.SmartThread(name='charlie', target=f2)
        charlie_smart_thread.thread.start()

        ####################################################################
        # Interact with beta and charlie
        ####################################################################
        logger.debug('mainline interacting with beta')
        alpha_smart_thread.resume(targets='beta', log_msg='ml resume 1')
        alpha_smart_thread.sync(targets='beta', log_msg='ml sync 2')
        assert alpha_smart_thread.recv_msg(remote='beta', log_msg='ml recv_msg 3') == 'hi alpha, this is beta'
        alpha_smart_thread.send_msg(msg='hi beta, this is alpha', targets='beta', log_msg='ml send_msg 4')
        alpha_smart_thread.wait(remote='beta', log_msg='f1 resume 5')

        logger.debug('mainline interacting with charlie')
        alpha_smart_thread.resume(targets='charlie', log_msg='ml resume 6')
        alpha_smart_thread.sync(targets='charlie', log_msg='ml sync 7')
        assert alpha_smart_thread.recv_msg(remote='charlie', log_msg='ml recv_msg 8') == 'hi alpha, this is charlie'
        alpha_smart_thread.send_msg(msg='hi charlie, this is alpha', targets='charlie', log_msg='ml send_msg 9')
        alpha_smart_thread.wait(remote='charlie', log_msg='f1 resume 10')

        alpha_smart_thread.join(targets='beta', log_msg='ml join 11')
        alpha_smart_thread.join(targets='charlie', log_msg='ml join 12')

        logger.debug('mainline exiting')

    ####################################################################################################################
    # Basic Scenario3
    ####################################################################################################################
    def test_smart_thread_basic_scenario3(self):
        ####################################################################
        # f1
        ####################################################################
        def f1():
            logger.debug('f1 entered')

            beta_smart_thread.wait(remote='alpha', log_msg='f1 wait 1')
            beta_smart_thread.sync(targets='alpha', log_msg='f1 sync 2')
            beta_smart_thread.send_msg(msg='hi alpha, this is beta', targets='alpha', log_msg='f1 send_msg 3')
            assert beta_smart_thread.recv_msg(remote='alpha', log_msg='f1 recv_msg 4') == 'hi beta, this is alpha'
            beta_smart_thread.resume(targets='alpha', log_msg='f1 resume 5')

            beta_smart_thread.wait(remote='charlie', log_msg='f1 wait 6')
            beta_smart_thread.sync(targets='charlie', log_msg='f1 sync 7')
            beta_smart_thread.send_msg(msg='hi charlie, this is beta', targets='charlie', log_msg='f1 send_msg 8')
            assert beta_smart_thread.recv_msg(remote='charlie', log_msg='f1 recv_msg 9') == 'hi beta, this is charlie'
            beta_smart_thread.resume(targets='charlie', log_msg='f1 resume 10')

            logger.debug('f1 exiting')

        ####################################################################
        # f2
        ####################################################################
        def f2():
            logger.debug('f2 entered')

            charlie_smart_thread.wait(remote='alpha', log_msg='f2 wait 1')
            charlie_smart_thread.sync(targets='alpha', log_msg='f2 sync 2')
            charlie_smart_thread.send_msg(msg='hi alpha, this is charlie', targets='alpha', log_msg='f2 send_msg 3')
            assert charlie_smart_thread.recv_msg(remote='alpha', log_msg='f2 recv_msg 4') == 'hi charlie, this is alpha'
            charlie_smart_thread.resume(targets='alpha', log_msg='f2 resume 5')

            charlie_smart_thread.resume(targets='beta', log_msg='f2 resume 6')
            charlie_smart_thread.sync(targets='beta', log_msg='f2 sync 7')
            assert charlie_smart_thread.recv_msg(remote='beta', log_msg='f2 recv_msg 9') == 'hi charlie, this is beta'
            charlie_smart_thread.send_msg(msg='hi beta, this is charlie', targets='beta', log_msg='f2 send_msg 8')
            charlie_smart_thread.wait(remote='beta', log_msg='f2 wait 10')

            logger.debug('f2 exiting')

        ####################################################################
        # Create smart threads for the main thread (this thread), f1, and f2
        ####################################################################
        logger.debug('mainline entered')
        logger.debug('mainline creating alpha thread')
        alpha_smart_thread = st.SmartThread(name='alpha', default_timeout=10)

        logger.debug('mainline creating beta thread')
        beta_smart_thread = st.SmartThread(name='beta', target=f1)
        beta_smart_thread.thread.start()
        logger.debug('mainline creating charlie thread')
        charlie_smart_thread = st.SmartThread(name='charlie', target=f2)
        charlie_smart_thread.thread.start()

        ####################################################################
        # Interact with beta and charlie
        ####################################################################
        logger.debug('mainline interacting with beta and charlie')
        alpha_smart_thread.resume(targets='beta', log_msg='ml resume 1')
        alpha_smart_thread.resume(targets='charlie', log_msg='ml resume 2')
        alpha_smart_thread.sync(targets='beta', log_msg='ml sync 3')
        alpha_smart_thread.sync(targets='charlie', log_msg='ml sync 4')
        assert alpha_smart_thread.recv_msg(remote='beta', log_msg='ml recv_msg 5') == 'hi alpha, this is beta'
        assert alpha_smart_thread.recv_msg(remote='charlie', log_msg='ml recv_msg 6') == 'hi alpha, this is charlie'
        alpha_smart_thread.send_msg(msg='hi beta, this is alpha', targets='beta', log_msg='ml send_msg 7')
        alpha_smart_thread.send_msg(msg='hi charlie, this is alpha', targets='charlie', log_msg='ml send_msg 8')
        alpha_smart_thread.wait(remote='beta', log_msg='f1 resume 9')
        alpha_smart_thread.wait(remote='charlie', log_msg='f1 resume 10')

        alpha_smart_thread.join(targets='beta', log_msg='ml join 11')
        alpha_smart_thread.join(targets='charlie', log_msg='ml join 12')

        logger.debug('mainline exiting')

    ####################################################################################################################
    # Basic Scenario4
    ####################################################################################################################
    def test_smart_thread_basic_scenario4(self):
        ####################################################################
        # f1
        ####################################################################
        def f1():
            logger.debug('f1 entered')

            beta_smart_thread.wait(remote='alpha', log_msg='f1 wait 1')
            beta_smart_thread.sync(targets={'alpha', 'charlie'}, log_msg='f1 sync 2')
            beta_smart_thread.send_msg(msg='hi alpha and charlie, this is beta', targets={'alpha', 'charlie'},
                                       log_msg='f1 send_msg 3')
            assert beta_smart_thread.recv_msg(remote='alpha', log_msg='f1 recv_msg 4') == 'hi beta and charlie, this is alpha'
            assert beta_smart_thread.recv_msg(remote='charlie',
                                        log_msg='f1 recv_msg 5') == 'hi alpha and beta, this is charlie'
            beta_smart_thread.resume(targets={'alpha', 'charlie'}, log_msg='f1 resume 6')
            beta_smart_thread.wait(remote='charlie', log_msg='f1 wait 7')

            logger.debug('f1 exiting')

        ####################################################################
        # f2
        ####################################################################
        def f2():
            logger.debug('f2 entered')

            charlie_smart_thread.wait(remote='alpha', log_msg='f2 wait 1')
            charlie_smart_thread.sync(targets={'alpha', 'beta'}, log_msg='f2 sync 2')
            charlie_smart_thread.send_msg(msg='hi alpha and beta, this is charlie', targets={'alpha', 'beta'},
                                          log_msg='f2 send_msg 3')
            assert charlie_smart_thread.recv_msg(remote='alpha',
                                           log_msg='f2 recv_msg 4') == 'hi beta and charlie, this is alpha'
            assert charlie_smart_thread.recv_msg(remote='beta',
                                           log_msg='f2 recv_msg 5') == 'hi alpha and charlie, this is beta'
            charlie_smart_thread.wait(remote='beta', log_msg='f2 wait 6')
            charlie_smart_thread.resume(targets={'alpha', 'beta'}, log_msg='f2 resume 7')

            logger.debug('f2 exiting')

        ####################################################################
        # Create smart threads for the main thread (this thread), f1, and f2
        ####################################################################
        logger.debug('mainline entered')
        logger.debug('mainline creating alpha thread')
        alpha_smart_thread = st.SmartThread(name='alpha', default_timeout=10)

        logger.debug('mainline creating beta thread')
        beta_thread = threading.Thread(name='beta', target=f1)
        beta_smart_thread = st.SmartThread(name='beta', thread=beta_thread, default_timeout=10)
        beta_thread.start()
        logger.debug('mainline creating charlie thread')
        charlie_thread = threading.Thread(name='charlie', target=f2)
        charlie_smart_thread = st.SmartThread(name='charlie', thread=charlie_thread, default_timeout=10)
        charlie_thread.start()

        ####################################################################
        # Interact with beta and charlie
        ####################################################################
        logger.debug('mainline interacting with beta and charlie')

        alpha_smart_thread.resume(targets={'beta', 'charlie'}, log_msg='ml resume 1')
        alpha_smart_thread.sync(targets={'beta', 'charlie'}, log_msg='ml sync 2')
        assert alpha_smart_thread.recv_msg(remote='beta', log_msg='ml recv_msg 3') == 'hi alpha and charlie, this is beta'
        assert alpha_smart_thread.recv_msg(remote='charlie', log_msg='ml recv_msg 4') == 'hi alpha and beta, this is charlie'
        alpha_smart_thread.send_msg(msg='hi beta and charlie, this is alpha', targets={'beta', 'charlie'},
                                    log_msg='ml send_msg 5')
        alpha_smart_thread.wait(remote='beta', log_msg='ml resume 6')
        alpha_smart_thread.wait(remote='charlie', log_msg='ml resume 7')

        alpha_smart_thread.join(targets={'beta', 'charlie'}, log_msg='ml join 8')

        logger.debug('mainline exiting')
#     ###########################################################################
#     # repr for SmartThread
#     ###########################################################################
#     def test_smart_thread_repr(self,
#                               thread_exc: Any) -> None:
#         """Test event with code repr.
#
#         Args:
#             thread_exc: captures thread exceptions
#
#         """
#         descs = SmartThreadDescs()
#
#         smart_thread = SmartThread(name='alpha')
#         descs.add_desc(SmartThreadDesc(smart_thread=smart_thread))
#
#         expected_repr_str = 'SmartThread(group_name="group1", name="alpha")'
#
#         assert repr(smart_thread) == expected_repr_str
#
#         smart_thread2 = SmartThread(group_name="group1", name="AlphaDog")
#         descs.add_desc(SmartThreadDesc(smart_thread=smart_thread2))
#
#         expected_repr_str = 'SmartThread(group_name="group1", name="AlphaDog")'
#
#         assert repr(smart_thread2) == expected_repr_str
#
#         def f1():
#             t_pair = SmartThread(group_name='group1', name='beta1')
#             descs.add_desc(SmartThreadDesc(smart_thread=t_pair))
#             f1_expected_repr_str = 'SmartThread(group_name="group1", name="beta1")'
#             assert repr(t_pair) == f1_expected_repr_str
#
#             cmds.queue_cmd('alpha', 'go')
#             cmds.get_cmd('beta1')
#
#         def f2():
#             t_pair = SmartThread(group_name='group1', name='beta2')
#             descs.add_desc(SmartThreadDesc(smart_thread=t_pair))
#             f1_expected_repr_str = 'SmartThread(group_name="group1", name="beta2")'
#             assert repr(t_pair) == f1_expected_repr_str
#             cmds.queue_cmd('alpha', 'go')
#             cmds.get_cmd('beta2')
#
#         cmds = Cmds()
#         a_thread1 = threading.Thread(target=f1)
#         a_thread1.start()
#
#         cmds.get_cmd('alpha')
#
#         a_thread2 = threading.Thread(target=f2)
#         a_thread2.start()
#
#         cmds.get_cmd('alpha')
#         cmds.queue_cmd('beta1', 'go')
#         a_thread1.join()
#         descs.thread_end('beta1')
#         cmds.queue_cmd('beta2', 'go')
#         a_thread2.join()
#         descs.thread_end('beta2')
#
#     ###########################################################################
#     # test_smart_thread_instantiate_with_errors
#     ###########################################################################
#     def test_smart_thread_instantiate_with_errors(self) -> None:
#         """Test register_thread alpha first."""
#
#         descs = SmartThreadDescs()
#
#         smart_thread = SmartThread(group_name='group1', name='alpha')
#
#         descs.add_desc(SmartThreadDesc(smart_thread=smart_thread))
#
#         # not OK to instantiate a new smart_thread with same name
#         with pytest.raises(SmartThreadNameAlreadyInUse):
#             _ = SmartThread(group_name='group1', name='alpha')
#
#         with pytest.raises(SmartThreadIncorrectNameSpecified):
#             _ = SmartThread(group_name='group1', name=42)  # type: ignore
#
#         # try to pair with unknown remote
#         with pytest.raises(SmartThreadPairWithTimedOut):
#             smart_thread.pair_with(remote_name='beta', timeout=0.1)
#
#         # try to pair with bad name
#         with pytest.raises(SmartThreadIncorrectNameSpecified):
#             smart_thread.pair_with(remote_name=3)  # type: ignore
#
#         # make sure everything still the same
#
#         descs.verify_registry()
#
#     ###########################################################################
#     # test_smart_thread_pairing_with_errors
#     ###########################################################################
#     def test_smart_thread_pairing_with_errors(self) -> None:
#         """Test register_thread during instantiation."""
#         def f1(name: str) -> None:
#             """Func to test instantiate SmartThread.
#
#             Args:
#                 name: name to use for t_pair
#             """
#             logger.debug(f'{name} f1 entered')
#             t_pair = SmartThread(group_name='group1', name=name)
#             descs.add_desc(SmartThreadDesc(smart_thread=t_pair))
#
#             cmds.queue_cmd('alpha', 'go')
#
#             # not OK to pair with self
#             with pytest.raises(SmartThreadPairWithSelfNotAllowed):
#                 t_pair.pair_with(remote_name=name)
#
#             t_pair.pair_with(remote_name='alpha')
#
#             # not OK to pair with remote a second time
#             with pytest.raises(SmartThreadAlreadyPairedWithRemote):
#                 t_pair.pair_with(remote_name='alpha')
#
#             cmds.get_cmd('beta')
#
#             logger.debug(f'{name} f1 exiting')
#
#         cmds = Cmds()
#
#         descs = SmartThreadDescs()
#
#         beta_t = threading.Thread(target=f1, args=('beta',))
#
#         smart_thread = SmartThread(group_name='group1', name='alpha')
#
#         descs.add_desc(SmartThreadDesc(smart_thread=smart_thread))
#         beta_t.start()
#
#         # not OK to pair with self
#         with pytest.raises(SmartThreadPairWithSelfNotAllowed):
#             smart_thread.pair_with(remote_name='alpha')
#
#         cmds.get_cmd('alpha')
#
#         smart_thread.pair_with(remote_name='beta')
#         descs.paired('alpha', 'beta')
#
#         # not OK to pair with remote a second time
#         with pytest.raises(SmartThreadAlreadyPairedWithRemote):
#             smart_thread.pair_with(remote_name='beta')
#
#         cmds.queue_cmd('beta')
#
#         beta_t.join()
#
#         descs.thread_end(name='beta')
#
#         # at this point, f1 has ended. But, the registry will not have changed,
#         # so everything will still show paired, even both alpha and beta
#         # SmartThreads. Alpha SmartThread will detect that beta is no longer
#         # alive if a function is attempted.
#
#         descs.verify_registry()
#
#         #######################################################################
#         # second case - f1 with same name beta
#         #######################################################################
#         beta_t2 = threading.Thread(target=f1, args=('beta',))
#         beta_t2.start()
#
#         cmds.get_cmd('alpha')
#
#         smart_thread.pair_with(remote_name='beta')
#         descs.paired('alpha', 'beta')
#
#         cmds.queue_cmd('beta')
#
#         beta_t2.join()
#
#         descs.thread_end(name='beta')
#
#         # at this point, f1 has ended. But, the registry will not have changed,
#         # so everything will still show paired, even both alpha and beta
#         # SmartThreads. Alpha SmartThread will detect that beta is no longer
#         # alive if a function is attempted.
#         descs.verify_registry()
#
#         #######################################################################
#         # third case, use different name for f1. Should clean up old beta
#         # from the registry.
#         #######################################################################
#         with pytest.raises(SmartThreadNameAlreadyInUse):
#             smart_thread = SmartThread(group_name='group1', name='alpha')  # create fresh
#
#         beta_t3 = threading.Thread(target=f1, args=('charlie',))
#         beta_t3.start()
#
#         cmds.get_cmd('alpha')
#
#         smart_thread.pair_with(remote_name='charlie')
#         descs.paired('alpha', 'charlie')
#
#         assert 'beta' not in SmartThread._registry[smart_thread.group_name]
#
#         cmds.queue_cmd('beta')
#
#         beta_t3.join()
#
#         descs.thread_end(name='charlie')
#
#         # at this point, f1 has ended. But, the registry will not have changed,
#         # so everything will still show paired, even both alpha and charlie
#         # SmartThreads. Alpha SmartThread will detect that charlie is no longer
#         # alive if a function is attempted.
#
#         # change name in SmartThread, then register a new entry to force the
#         # SmartThreadErrorInRegistry error
#         smart_thread.remote.name = 'bad_name'
#         with pytest.raises(SmartThreadErrorInRegistry):
#             _ = SmartThread(group_name='group1', name='alpha2')
#
#         # restore the good name to allow verify_registry to succeed
#         smart_thread.remote.name = 'charlie'
#
#         descs.verify_registry()
#
#     ###########################################################################
#     # test_smart_thread_pairing_with_multiple_threads
#     ###########################################################################
#     def test_smart_thread_pairing_with_multiple_threads(self) -> None:
#         """Test register_thread during instantiation."""
#         def f1(name: str) -> None:
#             """Func to test instantiate SmartThread.
#
#             Args:
#                 name: name to use for t_pair
#             """
#             logger.debug(f'{name} f1 entered')
#             t_pair = SmartThread(group_name='group1', name=name)
#
#             descs.add_desc(SmartThreadDesc(smart_thread=t_pair))
#
#             # not OK to pair with self
#             with pytest.raises(SmartThreadPairWithSelfNotAllowed):
#                 t_pair.pair_with(remote_name=name)
#
#             cmds.queue_cmd('alpha', 'go')
#
#             t_pair.pair_with(remote_name='alpha')
#             descs.paired('alpha', 'beta')
#
#             # alpha needs to wait until we are officially paired to avoid
#             # timing issue when pairing with charlie
#             cmds.queue_cmd('alpha')
#
#             # not OK to pair with remote a second time
#             with pytest.raises(SmartThreadAlreadyPairedWithRemote):
#                 t_pair.pair_with(remote_name='alpha')
#
#             cmds.queue_cmd('alpha', 'go')
#
#             cmds.get_cmd('beta')
#
#             logger.debug(f'{name} f1 exiting')
#
#         def f2(name: str) -> None:
#             """Func to test instantiate SmartThread.
#
#             Args:
#                 name: name to use for t_pair
#             """
#             logger.debug(f'{name} f2 entered')
#             t_pair = SmartThread(group_name='group1', name=name)
#
#             descs.add_desc(SmartThreadDesc(smart_thread=t_pair))
#
#             # not OK to pair with self
#             with pytest.raises(SmartThreadPairWithSelfNotAllowed):
#                 t_pair.pair_with(remote_name=name)
#
#             with pytest.raises(SmartThreadPairWithTimedOut):
#                 t_pair.pair_with(remote_name='alpha', timeout=1)
#
#             t_pair.pair_with(remote_name='alpha2')
#
#             descs.paired('alpha2', 'charlie')
#
#             # not OK to pair with remote a second time
#             with pytest.raises(SmartThreadAlreadyPairedWithRemote):
#                 t_pair.pair_with(remote_name='alpha2')
#
#             cmds.queue_cmd('alpha', 'go')
#
#             cmds.get_cmd('charlie')
#
#             logger.debug(f'{name} f2 exiting')
#
#         #######################################################################
#         # mainline
#         #######################################################################
#         descs = SmartThreadDescs()
#
#         cmds = Cmds()
#
#         beta_t = threading.Thread(target=f1, args=('beta',))
#         charlie_t = threading.Thread(target=f2, args=('charlie',))
#
#         smart_thread = SmartThread(group_name='group1', name='alpha')
#
#         descs.add_desc(SmartThreadDesc(smart_thread=smart_thread))
#
#         beta_t.start()
#
#         cmds.get_cmd('alpha')
#
#         smart_thread.pair_with(remote_name='beta')
#
#         #######################################################################
#         # pair with charlie
#         #######################################################################
#         cmds.get_cmd('alpha')
#
#         smart_thread2 = SmartThread(group_name='group1', name='alpha2')
#
#         descs.add_desc(SmartThreadDesc(smart_thread=smart_thread2))
#
#         charlie_t.start()
#
#         smart_thread2.pair_with(remote_name='charlie')
#
#         cmds.get_cmd('alpha')
#
#         cmds.queue_cmd('beta')
#
#         beta_t.join()
#
#         descs.thread_end(name='beta')
#
#         cmds.queue_cmd('charlie')
#
#         charlie_t.join()
#
#         descs.thread_end(name='charlie')
#
#         # at this point, f1 and f2 have ended. But, the registry will not have
#         # changed, so everything will still show paired, even all
#         # SmartThreads. Any SmartThreads requests will detect that
#         # their pairs are no longer active and will trigger cleanup to
#         # remove any not alive entries from the registry. The SmartThread
#         # objects for not alive threads remain pointed to by the alive
#         # entries so that they may still report SmartThreadRemoteThreadNotAlive.
#         descs.verify_registry()
#
#         # cause cleanup by calling cleanup directly
#         smart_thread._clean_up_registry()
#
#         descs.cleanup()
#
#         # try to pair with old beta - should timeout
#         with pytest.raises(SmartThreadPairWithTimedOut):
#             smart_thread.pair_with(remote_name='beta', timeout=1)
#
#         # the pair_with sets smart_thread.remote to none before trying the
#         # pair_with, and leaves it None when pair_with fails
#         descs.paired('alpha')
#
#         # try to pair with old charlie - should timeout
#         with pytest.raises(SmartThreadPairWithTimedOut):
#             smart_thread.pair_with(remote_name='charlie', timeout=1)
#
#         # try to pair with nobody - should timeout
#         with pytest.raises(SmartThreadPairWithTimedOut):
#             smart_thread.pair_with(remote_name='nobody', timeout=1)
#
#         # try to pair with old beta - should timeout
#         with pytest.raises(SmartThreadPairWithTimedOut):
#             smart_thread2.pair_with(remote_name='beta', timeout=1)
#
#         # the pair_with sets smart_thread.remote to none before trying the
#         # pair_with, and leaves it None when pair_with fails
#         descs.paired('alpha2')
#
#         # try to pair with old charlie - should timeout
#         with pytest.raises(SmartThreadPairWithTimedOut):
#             smart_thread2.pair_with(remote_name='charlie', timeout=1)
#
#         # try to pair with nobody - should timeout
#         with pytest.raises(SmartThreadPairWithTimedOut):
#             smart_thread2.pair_with(remote_name='nobody', timeout=1)
#
#         descs.verify_registry()
#
#     ###########################################################################
#     # test_smart_thread_pairing_with_multiple_threads
#     ###########################################################################
#     def test_smart_thread_remote_pair_with_other_error(self) -> None:
#         """Test pair_with error case."""
#         def f1() -> None:
#             """Func to test pair_with SmartThread."""
#             logger.debug('beta f1 entered')
#             t_pair = SmartThread(group_name='group1', name='beta')
#
#             descs.add_desc(SmartThreadDesc(smart_thread=t_pair))
#
#             cmds.queue_cmd('alpha', 'go')
#             with pytest.raises(SmartThreadRemotePairedWithOther):
#                 t_pair.pair_with(remote_name='alpha')
#
#             cmds.get_cmd('beta')
#             logger.debug(f'beta f1 exiting')
#
#         def f2() -> None:
#             """Func to test pair_with SmartThread."""
#             logger.debug('charlie f2 entered')
#             t_pair = SmartThread(group_name='group1', name='charlie')
#
#             descs.add_desc(SmartThreadDesc(smart_thread=t_pair),
#                            verify=False)
#
#             cmds.queue_cmd('alpha', 'go')
#             t_pair.pair_with(remote_name='alpha')
#             descs.paired('alpha', 'charlie', verify=False)
#
#             cmds.queue_cmd('alpha', 'go')
#
#             cmds.get_cmd('charlie')
#
#             logger.debug(f'charlie f2 exiting')
#
#         #######################################################################
#         # mainline
#         #######################################################################
#         descs = SmartThreadDescs()
#
#         cmds = Cmds()
#
#         beta_t = threading.Thread(target=f1)
#         charlie_t = threading.Thread(target=f2)
#
#         smart_thread = SmartThread(group_name='group1', name='alpha')
#
#         descs.add_desc(SmartThreadDesc(smart_thread=smart_thread))
#
#         beta_t.start()
#
#         cmds.get_cmd('alpha')
#
#         beta_se = SmartThread._registry[smart_thread.group_name]['beta']
#
#         # make sure beta has alpha as target of pair_with
#         while beta_se.remote is None:
#             time.sleep(1)
#
#         #######################################################################
#         # pair with charlie
#         #######################################################################
#         charlie_t.start()
#
#         cmds.get_cmd('alpha')
#
#         smart_thread.pair_with(remote_name='charlie')
#
#         cmds.get_cmd('alpha')
#
#         cmds.queue_cmd('beta')
#
#         # wait for beta to raise SmartThreadRemotePairedWithOther and end
#         beta_t.join()
#
#         descs.thread_end(name='beta')
#
#         # sync up with charlie to allow charlie to exit
#         cmds.queue_cmd('charlie')
#
#         charlie_t.join()
#
#         descs.thread_end(name='charlie')
#
#         # cause cleanup by calling cleanup directly
#         smart_thread._clean_up_registry()
#
#         descs.cleanup()
#
#     ###########################################################################
#     # test_smart_thread_pairing_cleanup
#     ###########################################################################
#     def test_smart_thread_pairing_cleanup(self) -> None:
#         """Test register_thread during instantiation."""
#         def f1(name: str, remote_name: str, idx: int) -> None:
#             """Func to test instantiate SmartThread.
#
#             Args:
#                 name: name to use for t_pair
#                 remote_name: name to pair with
#                 idx: index into beta_smart_threads
#
#             """
#             logger.debug(f'{name} f1 entered, remote {remote_name}, idx {idx}')
#             t_pair = SmartThread(group_name='group1', name=name)
#
#             descs.add_desc(SmartThreadDesc(smart_thread=t_pair))
#
#             cmds.queue_cmd('alpha')
#
#             t_pair.pair_with(remote_name=remote_name,
#                              log_msg=f'f1 {name} pair with {remote_name} '
#                                      f'for idx {idx}')
#
#             cmds.queue_cmd('alpha')
#
#             cmds.get_cmd(name)
#
#             logger.debug(f'{name} f1 exiting')
#
#         #######################################################################
#         # mainline start
#         #######################################################################
#         cmds = Cmds()
#
#         descs = SmartThreadDescs()
#
#         #######################################################################
#         # create 4 beta threads
#         #######################################################################
#         beta_t0 = threading.Thread(target=f1, args=('beta0', 'alpha0', 0))
#         beta_t1 = threading.Thread(target=f1, args=('beta1', 'alpha1', 1))
#         beta_t2 = threading.Thread(target=f1, args=('beta2', 'alpha2', 2))
#         beta_t3 = threading.Thread(target=f1, args=('beta3', 'alpha3', 3))
#
#         #######################################################################
#         # create alpha0 SmartThread and desc, and verify
#         #######################################################################
#         smart_thread0 = SmartThread(group_name='group1', name='alpha0')
#         descs.add_desc(SmartThreadDesc(smart_thread=smart_thread0))
#
#         #######################################################################
#         # create alpha1 SmartThread and desc, and verify
#         #######################################################################
#         smart_thread1 = SmartThread(group_name='group1', name='alpha1')
#         descs.add_desc(SmartThreadDesc(smart_thread=smart_thread1))
#
#         #######################################################################
#         # create alpha2 SmartThread and desc, and verify
#         #######################################################################
#         smart_thread2 = SmartThread(group_name='group1', name='alpha2')
#         descs.add_desc(SmartThreadDesc(smart_thread=smart_thread2))
#
#         #######################################################################
#         # create alpha3 SmartThread and desc, and verify
#         #######################################################################
#         smart_thread3 = SmartThread(group_name='group1', name='alpha3')
#         descs.add_desc(SmartThreadDesc(smart_thread=smart_thread3))
#
#         #######################################################################
#         # start beta0 thread, and verify
#         #######################################################################
#         beta_t0.start()
#
#         cmds.get_cmd('alpha')
#
#         smart_thread0.pair_with(remote_name='beta0')
#
#         cmds.get_cmd('alpha')
#         descs.paired('alpha0', 'beta0')
#
#         #######################################################################
#         # start beta1 thread, and verify
#         #######################################################################
#         beta_t1.start()
#
#         cmds.get_cmd('alpha')
#
#         smart_thread1.pair_with(remote_name='beta1')
#
#         cmds.get_cmd('alpha')
#         descs.paired('alpha1', 'beta1')
#
#         #######################################################################
#         # start beta2 thread, and verify
#         #######################################################################
#         beta_t2.start()
#
#         cmds.get_cmd('alpha')
#
#         smart_thread2.pair_with(remote_name='beta2')
#
#         cmds.get_cmd('alpha')
#         descs.paired('alpha2', 'beta2')
#
#         #######################################################################
#         # start beta3 thread, and verify
#         #######################################################################
#         beta_t3.start()
#
#         cmds.get_cmd('alpha')
#
#         smart_thread3.pair_with(remote_name='beta3')
#
#         cmds.get_cmd('alpha')
#         descs.paired('alpha3', 'beta3')
#
#         #######################################################################
#         # let beta0 finish
#         #######################################################################
#         cmds.queue_cmd('beta0')
#
#         beta_t0.join()
#
#         descs.thread_end(name='beta0')
#
#         #######################################################################
#         # replace old beta0 w new beta0 - should cleanup registry old beta0
#         #######################################################################
#         beta_t0 = threading.Thread(target=f1, args=('beta0', 'alpha0', 0))
#
#         beta_t0.start()
#
#         cmds.get_cmd('alpha')
#
#         smart_thread0.pair_with(remote_name='beta0')
#
#         cmds.get_cmd('alpha')
#         descs.paired('alpha0', 'beta0')
#
#         #######################################################################
#         # let beta1 and beta3 finish
#         #######################################################################
#         cmds.queue_cmd('beta1')
#         beta_t1.join()
#         descs.thread_end(name='beta1')
#
#         cmds.queue_cmd('beta3')
#         beta_t3.join()
#         descs.thread_end(name='beta3')
#
#         #######################################################################
#         # replace old beta1 w new beta1 - should cleanup old beta1 and beta3
#         #######################################################################
#         beta_t1 = threading.Thread(target=f1, args=('beta1', 'alpha1', 1))
#
#         beta_t1.start()
#
#         cmds.get_cmd('alpha')
#
#         smart_thread1.pair_with(remote_name='beta1')
#
#         cmds.get_cmd('alpha')
#         descs.paired('alpha1', 'beta1')
#
#         # should get not alive for beta3
#         with pytest.raises(SmartThreadRemoteThreadNotAlive):
#             smart_thread3.check_remote()
#         descs.cleanup()
#
#         # should still be the same
#         descs.verify_registry()
#
#         #######################################################################
#         # get a new beta3 going
#         #######################################################################
#         beta_t3 = threading.Thread(target=f1, args=('beta3', 'alpha3', 3))
#
#         beta_t3.start()
#
#         cmds.get_cmd('alpha')
#
#         smart_thread3.pair_with(remote_name='beta3')
#
#         cmds.get_cmd('alpha')
#         descs.paired('alpha3', 'beta3')
#
#         #######################################################################
#         # let beta1 and beta2 finish
#         #######################################################################
#         cmds.queue_cmd('beta1')
#         beta_t1.join()
#         descs.thread_end(name='beta1')
#
#         cmds.queue_cmd('beta2')
#         beta_t2.join()
#         descs.thread_end(name='beta2')
#
#         #######################################################################
#         # trigger cleanup for beta1 and beta2
#         #######################################################################
#         # should get not alive for beta1
#         with pytest.raises(SmartThreadRemoteThreadNotAlive):
#             smart_thread1.check_remote()
#         descs.cleanup()
#
#         descs.cleanup()
#
#         #######################################################################
#         # should get SmartThreadRemoteThreadNotAlive for beta1 and beta2
#         #######################################################################
#         with pytest.raises(SmartThreadRemoteThreadNotAlive):
#             smart_thread1.check_remote()
#
#         with pytest.raises(SmartThreadRemoteThreadNotAlive):
#             smart_thread2.check_remote()
#
#         descs.verify_registry()
#
#         #######################################################################
#         # get a new beta2 going and then allow to end
#         #######################################################################
#         beta_t2 = threading.Thread(target=f1, args=('beta2', 'alpha2', 2))
#
#         beta_t2.start()
#
#         cmds.get_cmd('alpha')
#
#         smart_thread2.pair_with(remote_name='beta2')
#
#         cmds.get_cmd('alpha')
#         descs.paired('alpha2', 'beta2')
#
#         cmds.queue_cmd('beta2')
#         beta_t2.join()
#         descs.thread_end(name='beta2')
#
#         #######################################################################
#         # let beta0 complete
#         #######################################################################
#         cmds.queue_cmd('beta0')
#         beta_t0.join()
#         descs.thread_end(name='beta0')
#
#         #######################################################################
#         # let beta3 complete
#         #######################################################################
#         cmds.queue_cmd('beta3')
#         beta_t3.join()
#         descs.thread_end(name='beta3')
#
#     ###########################################################################
#     # test_smart_thread_foreign_op_detection
#     ###########################################################################
#     def test_smart_thread_foreign_op_detection(self) -> None:
#         """Test register_thread with f1."""
#         #######################################################################
#         # mainline and f1 - mainline pairs with beta
#         #######################################################################
#         logger.debug('start test 1')
#
#         def f1():
#             logger.debug('beta f1 entered')
#             t_pair = SmartThread(group_name='group1', name='beta')
#
#             descs.add_desc(SmartThreadDesc(smart_thread=t_pair))
#
#             cmds.queue_cmd('alpha')
#             my_c_thread = threading.current_thread()
#             assert t_pair.thread is my_c_thread
#             assert t_pair.thread is threading.current_thread()
#
#             t_pair.pair_with(remote_name='alpha')
#
#             cmds.get_cmd('beta')
#
#             logger.debug('beta f1 exiting')
#
#         def foreign1(t_pair):
#             logger.debug('foreign1 entered')
#
#             with pytest.raises(SmartThreadDetectedOpFromForeignThread):
#                 t_pair.verify_current_remote()
#
#             logger.debug('foreign1 exiting')
#
#         cmds = Cmds()
#         descs = SmartThreadDescs()
#
#         smart_thread1 = SmartThread(group_name='group1', name='alpha')
#         descs.add_desc(SmartThreadDesc(smart_thread=smart_thread1))
#
#         alpha_t = threading.current_thread()
#         my_f1_thread = threading.Thread(target=f1)
#         my_foreign1_thread = threading.Thread(target=foreign1,
#                                               args=(smart_thread1,))
#
#         with pytest.raises(SmartThreadNotPaired):
#             smart_thread1.check_remote()
#
#         logger.debug('mainline about to start beta thread')
#
#         my_f1_thread.start()
#
#         cmds.get_cmd('alpha')
#
#         smart_thread1.pair_with(remote_name='beta')
#         descs.paired('alpha', 'beta')
#
#         my_foreign1_thread.start()  # attempt to resume beta (should fail)
#
#         my_foreign1_thread.join()
#
#         cmds.queue_cmd('beta')  # tell beta to end
#
#         my_f1_thread.join()
#         descs.thread_end(name='beta')
#
#         with pytest.raises(SmartThreadRemoteThreadNotAlive):
#             smart_thread1.check_remote()
#         descs.cleanup()
#
#         assert smart_thread1.thread is alpha_t
#
#         descs.verify_registry()
#
#     ###########################################################################
#     # test_smart_thread_outer_thread_f1
#     ###########################################################################
#     def test_smart_thread_outer_thread_f1(self) -> None:
#         """Test simple sequence with outer thread f1."""
#         #######################################################################
#         # mainline
#         #######################################################################
#         logger.debug('mainline starting')
#
#         cmds = Cmds()
#         descs = SmartThreadDescs()
#
#         smart_thread = SmartThread(group_name='group1', name='alpha')
#         descs.add_desc(SmartThreadDesc(smart_thread=smart_thread))
#
#         f1_thread = threading.Thread(target=outer_f1, args=(cmds, descs))
#         f1_thread.start()
#
#         cmds.get_cmd('alpha')
#
#         smart_thread.pair_with(remote_name='beta')
#         descs.paired('alpha', 'beta')
#
#         cmds.queue_cmd('beta')
#
#         f1_thread.join()
#         descs.thread_end(name='beta')
#
#         logger.debug('mainline exiting')
#
#     ###########################################################################
#     # test_smart_thread_outer_thread_app
#     ###########################################################################
#     def test_smart_thread_outer_thread_app(self) -> None:
#         """Test simple sequence with outer thread app."""
#         #######################################################################
#         # mainline
#         #######################################################################
#         logger.debug('mainline starting')
#         cmds = Cmds()
#         descs = SmartThreadDescs()
#
#         smart_thread = SmartThread(group_name='group1', name='alpha')
#         descs.add_desc(SmartThreadDesc(smart_thread=smart_thread))
#
#         thread_app = OuterThreadApp(cmds=cmds, descs=descs)
#
#         thread_app.start()
#
#         cmds.get_cmd('alpha')
#         smart_thread.pair_with(remote_name='beta', timeout=3)
#
#         cmds.queue_cmd('beta')
#
#         thread_app.join()
#         descs.thread_end(name='beta')
#
#         logger.debug('mainline exiting')
#
#     ###########################################################################
#     # test_smart_thread_outer_thread_app
#     ###########################################################################
#     def test_smart_thread_outer_thread_event_app(self) -> None:
#         """Test simple sequence with outer thread event app."""
#         #######################################################################
#         # mainline
#         #######################################################################
#         logger.debug('mainline starting')
#         cmds = Cmds()
#         descs = SmartThreadDescs()
#         smart_thread = SmartThread(group_name='group1', name='alpha')
#         descs.add_desc(SmartThreadDesc(smart_thread=smart_thread))
#
#         thread_event_app = OuterThreadEventApp(cmds=cmds, descs=descs)
#         thread_event_app.start()
#
#         cmds.get_cmd('alpha')
#
#         smart_thread.pair_with(remote_name='beta', timeout=3)
#
#         cmds.queue_cmd('beta')
#
#         thread_event_app.join()
#
#         descs.thread_end(name='beta')
#
#         logger.debug('mainline exiting')
#
#     ###########################################################################
#     # test_smart_thread_inner_thread_app
#     ###########################################################################
#     def test_smart_thread_inner_thread_app(self) -> None:
#         """Test SmartThread with thread_app."""
#         #######################################################################
#         # ThreadApp
#         #######################################################################
#         class MyThread(threading.Thread):
#             """MyThread class to test SmartThread."""
#
#             def __init__(self,
#                          alpha_smart_thread: SmartThread,
#                          alpha_smart_thread: threading.Thread
#                          ) -> None:
#                 """Initialize the object.
#
#                 Args:
#                     alpha_smart_thread: alpha SmartThread to use for verification
#                     alpha_smart_thread: alpha thread to use for verification
#
#                 """
#                 super().__init__()
#                 self.t_pair = SmartThread(group_name='group1', name='beta', thread=self)
#                 self.alpha_t_pair = alpha_smart_thread
#                 self.alpha_smart_thread = alpha_smart_thread
#
#             def run(self):
#                 """Run the tests."""
#                 logger.debug('run started')
#
#                 # normally, the add_desc is done just after the
#                 # instantiation, but
#                 # in this case the thread is not made alive until now, and the
#                 # add_desc checks that the thread is alive
#                 descs.add_desc(SmartThreadDesc(smart_thread=self.t_pair))
#
#                 cmds.queue_cmd('alpha')
#                 self.t_pair.pair_with(remote_name='alpha')
#                 descs.paired('alpha', 'beta')
#
#                 assert self.t_pair.remote is self.alpha_t_pair
#                 assert (self.t_pair.remote.thread
#                         is self.alpha_smart_thread)
#                 assert self.t_pair.remote.thread is alpha_t
#                 assert self.t_pair.thread is self
#                 my_run_thread = threading.current_thread()
#                 assert self.t_pair.thread is my_run_thread
#                 assert self.t_pair.thread is threading.current_thread()
#
#                 cmds.get_cmd('beta')
#                 logger.debug('beta run exiting 45')
#
#         #######################################################################
#         # mainline starts
#         #######################################################################
#         cmds = Cmds()
#         descs = SmartThreadDescs()
#         alpha_t = threading.current_thread()
#         smart_thread1 = SmartThread(group_name='group1', name='alpha')
#         descs.add_desc(SmartThreadDesc(smart_thread=smart_thread1))
#
#         my_taa_thread = MyThread(smart_thread1, alpha_t)
#
#         my_taa_thread.start()
#
#         cmds.get_cmd('alpha')
#
#         smart_thread1.pair_with(remote_name='beta')
#
#         cmds.queue_cmd('beta')
#
#         my_taa_thread.join()
#         descs.thread_end('beta')
#
#         with pytest.raises(SmartThreadRemoteThreadNotAlive):
#             smart_thread1.check_remote()
#         descs.cleanup()
#
#         with pytest.raises(SmartThreadPairWithTimedOut):
#             smart_thread1.pair_with(remote_name='beta', timeout=1)
#         descs.paired('alpha')
#
#         with pytest.raises(SmartThreadNotPaired):
#             smart_thread1.check_remote()
#
#         assert smart_thread1.thread is alpha_t
#         assert smart_thread1.remote is None
#
#         descs.verify_registry()
#
#     ###########################################################################
#     # test_smart_thread_inner_thread_event_app
#     ###########################################################################
#     def test_smart_thread_inner_thread_event_app(self) -> None:
#         """Test SmartThread with thread_event_app."""
#         #######################################################################
#         # mainline and ThreadEventApp - mainline sets alpha and beta
#         #######################################################################
#         class MyThreadEvent1(threading.Thread, SmartThread):
#             def __init__(self,
#                          alpha_t1: threading.Thread):
#                 threading.Thread.__init__(self)
#                 SmartThread.__init__(self, group_name='group1', name='beta', thread=self)
#                 self.alpha_t1 = alpha_t1
#
#             def run(self):
#                 logger.debug('run started')
#                 # normally, the add_desc is done just after the
#                 # instantiation, but
#                 # in this case the thread is not made alive until now, and the
#                 # add_desc checks that the thread is alive
#                 descs.add_desc(SmartThreadDesc(smart_thread=self))
#                 cmds.queue_cmd('alpha')
#                 self.pair_with(remote_name='alpha')
#                 descs.paired('alpha', 'beta')
#
#                 assert self.remote.thread is self.alpha_t1
#                 assert self.remote.thread is alpha_t
#                 assert self.thread is self
#                 my_run_thread = threading.current_thread()
#                 assert self.thread is my_run_thread
#                 assert self.thread is threading.current_thread()
#
#                 cmds.get_cmd('beta')
#                 logger.debug('run exiting')
#
#         cmds = Cmds()
#         descs = SmartThreadDescs()
#         alpha_t = threading.current_thread()
#
#         my_te1_thread = MyThreadEvent1(alpha_t)
#         with pytest.raises(SmartThreadDetectedOpFromForeignThread):
#             my_te1_thread.verify_current_remote()
#
#         with pytest.raises(SmartThreadDetectedOpFromForeignThread):
#             my_te1_thread.pair_with(remote_name='alpha', timeout=0.5)
#
#         assert my_te1_thread.remote is None
#         assert my_te1_thread.thread is my_te1_thread
#
#         my_te1_thread.start()
#
#         cmds.get_cmd('alpha')
#         smart_thread = SmartThread(group_name='group1', name='alpha')
#         descs.add_desc(SmartThreadDesc(smart_thread=smart_thread))
#
#         with pytest.raises(SmartThreadNotPaired):
#             smart_thread.verify_current_remote()
#
#         smart_thread.pair_with(remote_name='beta')
#
#         cmds.queue_cmd('beta')
#
#         my_te1_thread.join()
#         descs.thread_end('beta')
#
#         with pytest.raises(SmartThreadRemoteThreadNotAlive):
#             smart_thread.check_remote()
#         descs.cleanup()
#
#         assert my_te1_thread.remote is not None
#         assert my_te1_thread.remote.thread is not None
#         assert my_te1_thread.remote.thread is alpha_t
#         assert my_te1_thread.thread is my_te1_thread
#
#     ###########################################################################
#     # test_smart_thread_two_f_threads
#     ###########################################################################
#     def test_smart_thread_two_f_threads(self) -> None:
#         """Test register_thread with thread_event_app."""
#         #######################################################################
#         # two threads - mainline sets alpha and beta
#         #######################################################################
#         def fa1():
#             logger.debug('fa1 entered')
#             my_fa_thread = threading.current_thread()
#             t_pair = SmartThread(group_name='group1', name='fa1')
#             descs.add_desc(SmartThreadDesc(smart_thread=t_pair))
#
#             assert t_pair.thread is my_fa_thread
#
#             t_pair.pair_with(remote_name='fb1')
#             descs.paired('fa1', 'fb1')
#
#             logger.debug('fa1 about to wait')
#             cmds.get_cmd('fa1')
#             logger.debug('fa1 exiting')
#
#         def fb1():
#             logger.debug('fb1 entered')
#             my_fb_thread = threading.current_thread()
#             t_pair = SmartThread(group_name='group1', name='fb1')
#             descs.add_desc(SmartThreadDesc(smart_thread=t_pair))
#
#             assert t_pair.thread is my_fb_thread
#
#             t_pair.pair_with(remote_name='fa1')
#
#             logger.debug('fb1 about to resume')
#             cmds.queue_cmd('fa1')
#
#             # tell mainline we are out of the wait - OK to do descs fa1 end
#             cmds.queue_cmd('alpha')
#
#             # wait for mainline to give to go ahead after doing descs fa1 end
#             cmds.get_cmd('beta')
#
#             with pytest.raises(SmartThreadRemoteThreadNotAlive):
#                 t_pair.check_remote()
#
#             descs.cleanup()
#
#         #######################################################################
#         # mainline
#         #######################################################################
#         cmds = Cmds()
#         descs = SmartThreadDescs()
#         fa1_thread = threading.Thread(target=fa1)
#
#         fb1_thread = threading.Thread(target=fb1)
#
#         logger.debug('starting fa1_thread')
#         fa1_thread.start()
#         logger.debug('starting fb1_thread')
#         fb1_thread.start()
#
#         fa1_thread.join()
#         cmds.get_cmd('alpha')
#         descs.thread_end('fa1')
#
#         cmds.queue_cmd('beta', 'go')
#
#         fb1_thread.join()
#         descs.thread_end('fb1')
#
#
# ###############################################################################
# # TestTheta Class
# ###############################################################################
# class TestTheta:
#     """Test SmartThread with two classes."""
#     ###########################################################################
#     # test_smart_thread_theta
#     ###########################################################################
#     def test_smart_thread_theta(self) -> None:
#         """Test theta class."""
#
#         def f1():
#             logger.debug('f1 beta entered')
#             f1_theta = Theta(group_name='group1', name='beta')
#             descs.add_desc(ThetaDesc(name='beta',
#                                      theta=f1_theta,
#                                      thread=threading.current_thread()))
#
#             cmds.queue_cmd('alpha')
#
#             f1_theta.pair_with(remote_name='alpha')
#             descs.paired('alpha', 'beta')
#
#             cmds.queue_cmd('alpha', 'go')
#             cmds.get_cmd('beta')
#
#             assert f1_theta.var1 == 999
#
#             f1_theta.var1 = 'theta'  # restore to init value to allow verify to work
#
#             logger.debug('f1 beta exiting 5')
#
#         logger.debug('mainline entered')
#         cmds = Cmds()
#         descs = SmartThreadDescs()
#         ml_theta = Theta(group_name='group1', name='alpha')
#         descs.add_desc(ThetaDesc(name='alpha',
#                                  theta=ml_theta,
#                                  thread=threading.current_thread()))
#
#         f1_thread = threading.Thread(target=f1)
#
#         f1_thread.start()
#
#         cmds.get_cmd('alpha')
#         ml_theta.pair_with(remote_name='beta')
#
#         cmds.get_cmd('alpha')
#
#         ml_theta.remote.var1 = 999
#
#         cmds.queue_cmd('beta', 'go')
#
#         f1_thread.join()
#         descs.thread_end('beta')
#
#         with pytest.raises(SmartThreadRemoteThreadNotAlive):
#             ml_theta.check_remote()
#
#         descs.cleanup()
#
#         logger.debug('mainline exiting')
#
#
# ###############################################################################
# # TestSigma Class
# ###############################################################################
# class TestSigma:
#     """Test SmartThread with two classes."""
#     ###########################################################################
#     # test_smart_thread_sigma
#     ###########################################################################
#     def test_smart_thread_sigma(self) -> None:
#         """Test sigma class."""
#
#         def f1():
#             logger.debug('f1 beta entered')
#             f1_sigma = Sigma(group_name='group1', name='beta')
#             descs.add_desc(SigmaDesc(name='beta',
#                                      sigma=f1_sigma,
#                                      thread=threading.current_thread()))
#
#             cmds.queue_cmd('alpha')
#
#             f1_sigma.pair_with(remote_name='alpha')
#             descs.paired('alpha', 'beta')
#
#             cmds.queue_cmd('alpha', 'go')
#             cmds.get_cmd('beta')
#
#             assert f1_sigma.var1 == 999
#             assert f1_sigma.remote.var1 == 17
#
#             assert f1_sigma.var2 == 'sigma'
#             assert f1_sigma.remote.var2 == 'sigma'
#
#             f1_sigma.var1 = 17  # restore to init value to allow verify to work
#             f1_sigma.remote.var2 = 'test1'
#
#             logger.debug('f1 beta exiting 5')
#
#         logger.debug('mainline entered')
#         cmds = Cmds()
#         descs = SmartThreadDescs()
#         ml_sigma = Sigma(group_name='group1', name='alpha')
#         descs.add_desc(SigmaDesc(name='alpha',
#                                  sigma=ml_sigma,
#                                  thread=threading.current_thread()))
#
#         f1_thread = threading.Thread(target=f1)
#
#         f1_thread.start()
#
#         cmds.get_cmd('alpha')
#         ml_sigma.pair_with(remote_name='beta')
#
#         cmds.get_cmd('alpha')
#
#         ml_sigma.remote.var1 = 999
#
#         cmds.queue_cmd('beta', 'go')
#
#         f1_thread.join()
#
#         assert ml_sigma.var2 == 'test1'
#         ml_sigma.var2 = 'sigma'  # restore for verify
#
#         descs.thread_end('beta')
#
#         with pytest.raises(SmartThreadRemoteThreadNotAlive):
#             ml_sigma.check_remote()
#
#         descs.cleanup()
#
#         logger.debug('mainline exiting')
#
#
# ###############################################################################
# # TestOmega Class
# ###############################################################################
# class TestOmega:
#     """Test SmartThread with two classes."""
#     ###########################################################################
#     # test_smart_thread_omega
#     ###########################################################################
#     def test_smart_thread_omega(self) -> None:
#         """Test omega class."""
#
#         def f1():
#             logger.debug('f1 beta entered')
#             f1_omega = Omega(group_name='group1', name='beta')
#             descs.add_desc(OmegaDesc(name='beta',
#                                      omega=f1_omega,
#                                      thread=threading.current_thread()))
#
#             cmds.queue_cmd('alpha')
#
#             f1_omega.pair_with(remote_name='alpha')
#             descs.paired('alpha', 'beta')
#
#             cmds.queue_cmd('alpha', 'go')
#             cmds.get_cmd('beta')
#
#             assert f1_omega.var1 == 999
#             assert f1_omega.remote.var1 == 42
#
#             assert f1_omega.var2 == 64.9
#             assert f1_omega.remote.var2 == 64.9
#
#             assert f1_omega.var3 == 'omega'
#             assert f1_omega.remote.var3 == 'omega'
#
#             f1_omega.var1 = 42  # restore to init value to allow verify to work
#             f1_omega.remote.var2 = 'test_omega'
#
#             logger.debug('f1 beta exiting 5')
#
#         logger.debug('mainline entered')
#         cmds = Cmds()
#         descs = SmartThreadDescs()
#         ml_omega = Omega(group_name='group1', name='alpha')
#         descs.add_desc(OmegaDesc(name='alpha',
#                                  omega=ml_omega,
#                                  thread=threading.current_thread()))
#
#         f1_thread = threading.Thread(target=f1)
#
#         f1_thread.start()
#
#         cmds.get_cmd('alpha')
#         ml_omega.pair_with(remote_name='beta')
#
#         cmds.get_cmd('alpha')
#
#         ml_omega.remote.var1 = 999
#
#         cmds.queue_cmd('beta', 'go')
#
#         f1_thread.join()
#
#         assert ml_omega.var2 == 'test_omega'
#         ml_omega.var2 = 64.9  # restore for verify
#
#         descs.thread_end('beta')
#
#         with pytest.raises(SmartThreadRemoteThreadNotAlive):
#             ml_omega.check_remote()
#
#         descs.cleanup()
#
#         logger.debug('mainline exiting')
#
#
# ###############################################################################
# # TestThetaSigma Class
# ###############################################################################
# class TestThetaSigma:
#     """Test SmartThread with two classes."""
#     ###########################################################################
#     # test_smart_thread_theta_sigma
#     ###########################################################################
#     def test_smart_thread_theta_sigma_unique_names(self) -> None:
#         """Test theta and sigma."""
#
#         def f1():
#             logger.debug('f1 beta entered')
#             f1_theta = Theta(group_name='group1', name='beta_theta')
#             theta_descs.add_desc(ThetaDesc(name='beta_theta',
#                                            theta=f1_theta,
#                                            thread=threading.current_thread()))
#
#             f1_sigma = Sigma(group_name='group2', name='beta_sigma')
#             sigma_descs.add_desc(SigmaDesc(group_name='group2',
#                                            name='beta_sigma',
#                                            sigma=f1_sigma,
#                                            thread=threading.current_thread()))
#
#             cmds.queue_cmd('alpha')
#
#             f1_theta.pair_with(remote_name='alpha_theta')
#             theta_descs.paired('alpha_theta', 'beta_theta')
#
#             f1_sigma.pair_with(remote_name='alpha_sigma')
#             sigma_descs.paired('alpha_sigma', 'beta_sigma')
#
#             cmds.queue_cmd('alpha', 'go')
#             cmds.get_cmd('beta')
#
#             assert f1_theta.var1 == 999
#             assert f1_theta.remote.var1 == 'theta'
#
#             assert f1_sigma.var1 == 999
#             assert f1_sigma.remote.var1 == 17
#
#             assert f1_sigma.var2 == 'sigma'
#             assert f1_sigma.remote.var2 == 'sigma'
#
#             f1_theta.var1 = 'theta'  # restore to init value for verify
#             f1_theta.remote.var2 = 'test_theta'
#
#             f1_sigma.var1 = 17  # restore to init value to allow verify to work
#             f1_sigma.remote.var2 = 'test1'
#
#             logger.debug('f1 beta exiting')
#
#         logger.debug('mainline entered')
#         cmds = Cmds()
#         theta_descs = SmartThreadDescs()
#         sigma_descs = SmartThreadDescs()
#
#         ml_theta = Theta(group_name='group1', name='alpha_theta')
#
#         theta_descs.add_desc(ThetaDesc(name='alpha_theta',
#                                        theta=ml_theta,
#                                        thread=threading.current_thread()))
#
#         ml_sigma = Sigma(group_name='group2', name='alpha_sigma')
#         sigma_descs.add_desc(SigmaDesc(group_name='group2',
#                                        name='alpha_sigma',
#                                        sigma=ml_sigma,
#                                        thread=threading.current_thread()))
#
#         f1_thread = threading.Thread(target=f1)
#
#         f1_thread.start()
#
#         cmds.get_cmd('alpha')
#         ml_theta.pair_with(remote_name='beta_theta')
#         ml_sigma.pair_with(remote_name='beta_sigma')
#
#         cmds.get_cmd('alpha')
#
#         ml_theta.remote.var1 = 999
#         ml_sigma.remote.var1 = 999
#
#         cmds.queue_cmd('beta', 'go')
#
#         f1_thread.join()
#
#         assert ml_theta.var2 == 'test_theta'
#         ml_theta.var2 = 'theta'  # restore for verify
#
#         assert ml_sigma.var2 == 'test1'
#         ml_sigma.var2 = 'sigma'  # restore for verify
#
#         theta_descs.thread_end('beta_theta')
#         sigma_descs.thread_end('beta_sigma')
#
#         with pytest.raises(SmartThreadRemoteThreadNotAlive):
#             ml_theta.check_remote()
#
#         with pytest.raises(SmartThreadRemoteThreadNotAlive):
#             ml_sigma.check_remote()
#
#         theta_descs.cleanup()
#         sigma_descs.cleanup()
#
#         logger.debug('mainline exiting')
#
#     ###########################################################################
#     # test_smart_thread_theta_sigma
#     ###########################################################################
#     def test_smart_thread_theta_sigma_same_names(self) -> None:
#         """Test theta and sigma."""
#
#         def f1():
#             logger.debug('f1 beta entered')
#             f1_theta = Theta(group_name='group1', name='beta')
#             theta_descs.add_desc(ThetaDesc(name='beta',
#                                            theta=f1_theta,
#                                            thread=threading.current_thread()))
#
#             f1_sigma = Sigma(group_name='group2', name='beta')
#             sigma_descs.add_desc(SigmaDesc(group_name='group2',
#                                            name='beta',
#                                            sigma=f1_sigma,
#                                            thread=threading.current_thread()))
#
#             cmds.queue_cmd('alpha')
#
#             f1_theta.pair_with(remote_name='alpha')
#             theta_descs.paired('alpha', 'beta')
#
#             f1_sigma.pair_with(remote_name='alpha')
#             sigma_descs.paired('alpha', 'beta')
#
#             cmds.queue_cmd('alpha', 'go')
#             cmds.get_cmd('beta')
#
#             assert f1_theta.var1 == 999
#             assert f1_theta.remote.var1 == 'theta'
#
#             assert f1_sigma.var1 == 999
#             assert f1_sigma.remote.var1 == 17
#
#             assert f1_sigma.var2 == 'sigma'
#             assert f1_sigma.remote.var2 == 'sigma'
#
#             f1_theta.var1 = 'theta'  # restore to init value for verify
#             f1_theta.remote.var2 = 'test_theta'
#
#             f1_sigma.var1 = 17  # restore to init value to allow verify to work
#             f1_sigma.remote.var2 = 'test1'
#
#             logger.debug('f1 beta exiting')
#
#         logger.debug('mainline entered')
#         cmds = Cmds()
#         theta_descs = SmartThreadDescs()
#         sigma_descs = SmartThreadDescs()
#
#         ml_theta = Theta(group_name='group1', name='alpha')
#
#         theta_descs.add_desc(ThetaDesc(name='alpha',
#                                        theta=ml_theta,
#                                        thread=threading.current_thread()))
#
#         ml_sigma = Sigma(group_name='group2', name='alpha')
#         sigma_descs.add_desc(SigmaDesc(group_name='group2',
#                                        name='alpha',
#                                        sigma=ml_sigma,
#                                        thread=threading.current_thread()))
#
#         f1_thread = threading.Thread(target=f1)
#
#         f1_thread.start()
#
#         cmds.get_cmd('alpha')
#         ml_theta.pair_with(remote_name='beta')
#         ml_sigma.pair_with(remote_name='beta')
#
#         cmds.get_cmd('alpha')
#
#         ml_theta.remote.var1 = 999
#         ml_sigma.remote.var1 = 999
#
#         cmds.queue_cmd('beta', 'go')
#
#         f1_thread.join()
#
#         assert ml_theta.var2 == 'test_theta'
#         ml_theta.var2 = 'theta'  # restore for verify
#
#         assert ml_sigma.var2 == 'test1'
#         ml_sigma.var2 = 'sigma'  # restore for verify
#
#         theta_descs.thread_end('beta')
#         sigma_descs.thread_end('beta')
#
#         with pytest.raises(SmartThreadRemoteThreadNotAlive):
#             ml_theta.check_remote()
#
#         with pytest.raises(SmartThreadRemoteThreadNotAlive):
#             ml_sigma.check_remote()
#
#         theta_descs.cleanup()
#         sigma_descs.cleanup()
#
#         logger.debug('mainline exiting')
#
#
# ###############################################################################
# # TestSmartThreadLogger Class
# ###############################################################################
# class TestSmartThreadLogger:
#     """Test log messages."""
#     ###########################################################################
#     # test_smart_thread_f1_event_logger
#     ###########################################################################
#     def test_smart_thread_f1_event_logger(self,
#                                          caplog,
#                                          log_enabled_arg) -> None:
#         """Test smart event logger with f1 thread.
#
#         Args:
#             caplog: fixture to capture log messages
#             log_enabled_arg: fixture to indicate whether log is enabled
#
#         """
#         def f1():
#             exp_log_msgs.add_msg('f1 entered')
#             logger.debug('f1 entered')
#
#             l_msg = '_registry_lock obtained, group_name = group1, thread_name = beta, class name = SmartThread'
#             exp_log_msgs.add_msg(l_msg)
#             l_msg = 'beta registered not first entry for group group1'
#             exp_log_msgs.add_msg(l_msg)
#             t_pair = SmartThread(group_name='group1', name='beta')
#
#             descs.add_desc(SmartThreadDesc(smart_thread=t_pair))
#             cmds.queue_cmd('alpha')
#
#             exp_log_msgs.add_beta_pair_with_msg('beta pair_with alpha 1',
#                                                 ['beta', 'alpha'])
#             t_pair.pair_with(remote_name='alpha',
#                               log_msg='beta pair_with alpha 1')
#
#             descs.paired('alpha', 'beta')
#             cmds.get_cmd('beta')
#
#         cmds = Cmds()
#         descs = SmartThreadDescs()
#         if log_enabled_arg:
#             logging.getLogger().setLevel(logging.DEBUG)
#         else:
#             logging.getLogger().setLevel(logging.INFO)
#
#         alpha_call_seq = ('test_smart_thread.py::TestSmartThreadLogger.'
#                           'test_smart_thread_f1_event_logger')
#         beta_call_seq = ('test_smart_thread.py::f1')
#         exp_log_msgs = ExpLogMsgs(alpha_call_seq, beta_call_seq)
#         l_msg = 'mainline started'
#         exp_log_msgs.add_msg(l_msg)
#         logger.debug(l_msg)
#
#         l_msg = '_registry_lock obtained, group_name = group1, thread_name = alpha, class name = SmartThread'
#         exp_log_msgs.add_msg(l_msg)
#         l_msg = 'alpha registered first entry for group group1'
#         exp_log_msgs.add_msg(l_msg)
#         smart_thread = SmartThread(group_name='group1', name='alpha')
#         descs.add_desc(SmartThreadDesc(smart_thread=smart_thread))
#
#         beta_smart_thread = threading.Thread(target=f1)
#
#         beta_smart_thread.start()
#
#         cmds.get_cmd('alpha')
#         exp_log_msgs.add_alpha_pair_with_msg('alpha pair_with beta 1',
#                                              ['alpha', 'beta'])
#         smart_thread.pair_with(remote_name='beta',
#                               log_msg='alpha pair_with beta 1')
#
#         cmds.queue_cmd('beta')
#
#         beta_smart_thread.join()
#         descs.thread_end('beta')
#
#         exp_log_msgs.add_msg('mainline all tests complete')
#         logger.debug('mainline all tests complete')
#
#         exp_log_msgs.verify_log_msgs(caplog=caplog,
#                                      log_enabled_tf=log_enabled_arg)
#
#         # restore root to debug
#         logging.getLogger().setLevel(logging.DEBUG)
#
#     ###########################################################################
#     # test_smart_thread_thread_app_event_logger
#     ###########################################################################
#     def test_smart_thread_thread_app_event_logger(self,
#                                                  caplog,
#                                                  log_enabled_arg) -> None:
#         """Test smart event logger with thread_app thread.
#
#         Args:
#             caplog: fixture to capture log messages
#             log_enabled_arg: fixture to indicate whether log is enabled
#
#         """
#         class MyThread(threading.Thread):
#             def __init__(self,
#                          exp_log_msgs1: ExpLogMsgs):
#                 super().__init__()
#                 self.t_pair = SmartThread(group_name='group1', name='beta', thread=self)
#                 self.exp_log_msgs = exp_log_msgs1
#                 l_msg = '_registry_lock obtained, group_name = group1, thread_name = beta, class name = SmartThread'
#                 self.exp_log_msgs.add_msg(l_msg)
#                 l_msg = 'beta registered not first entry for group group1'
#                 self.exp_log_msgs.add_msg(l_msg)
#
#             def run(self):
#                 l_msg = 'ThreadApp run entered'
#                 self.exp_log_msgs.add_msg(l_msg)
#                 logger.debug(l_msg)
#
#                 descs.add_desc(SmartThreadDesc(smart_thread=self.t_pair))
#                 cmds.queue_cmd('alpha')
#
#                 self.exp_log_msgs.add_beta_pair_with_msg('beta pair alpha 2',
#                                                          ['beta', 'alpha'])
#                 self.t_pair.pair_with(remote_name='alpha',
#                                        log_msg='beta pair alpha 2')
#                 cmds.get_cmd('beta')
#
#
#
#         cmds = Cmds()
#         descs = SmartThreadDescs()
#         if log_enabled_arg:
#             logging.getLogger().setLevel(logging.DEBUG)
#         else:
#             logging.getLogger().setLevel(logging.INFO)
#
#         alpha_call_seq = ('test_smart_thread.py::TestSmartThreadLogger.'
#                           'test_smart_thread_thread_app_event_logger')
#
#         #beta_call_seq = 'test_smart_thread.py::MyThread.run'
#         beta_call_seq = 'test_smart_thread.py::run'
#         exp_log_msgs = ExpLogMsgs(alpha_call_seq, beta_call_seq)
#         l_msg = 'mainline starting'
#         exp_log_msgs.add_msg(l_msg)
#         logger.debug(l_msg)
#
#         l_msg = '_registry_lock obtained, group_name = group1, thread_name = alpha, class name = SmartThread'
#         exp_log_msgs.add_msg(l_msg)
#         l_msg = 'alpha registered first entry for group group1'
#         exp_log_msgs.add_msg(l_msg)
#         smart_thread = SmartThread(group_name='group1', name='alpha')
#         descs.add_desc(SmartThreadDesc(smart_thread=smart_thread))
#
#         thread_app = MyThread(exp_log_msgs)
#         thread_app.start()
#
#         cmds.get_cmd('alpha')
#         exp_log_msgs.add_alpha_pair_with_msg('alpha pair beta 2',
#                                              ['alpha', 'beta'])
#         smart_thread.pair_with(remote_name='beta',
#                               log_msg='alpha pair beta 2')
#         descs.paired('alpha', 'beta')
#
#         cmds.queue_cmd('beta')
#
#         thread_app.join()
#
#         smart_thread.code = None
#         smart_thread.remote.code = None
#
#         descs.thread_end('beta')
#
#         l_msg = 'mainline all tests complete'
#         exp_log_msgs.add_msg(l_msg)
#         logger.debug('mainline all tests complete')
#
#         exp_log_msgs.verify_log_msgs(caplog=caplog,
#                                      log_enabled_tf=log_enabled_arg)
#
#         # restore root to debug
#         logging.getLogger().setLevel(logging.DEBUG)
#
#     ###########################################################################
#     # test_smart_thread_thread_event_app_event_logger
#     ###########################################################################
#     def test_smart_thread_thread_event_app_event_logger(self,
#                                                        caplog,
#                                                        log_enabled_arg
#                                                        ) -> None:
#         """Test smart event logger with thread_event_app thread.
#
#         Args:
#             caplog: fixture to capture log messages
#             log_enabled_arg: fixture to indicate whether log is enabled
#
#         """
#         class MyThread(threading.Thread, SmartThread):
#             def __init__(self,
#                          exp_log_msgs1: ExpLogMsgs):
#                 threading.Thread.__init__(self)
#                 SmartThread.__init__(self, group_name='group1', name='beta', thread=self)
#                 self.exp_log_msgs = exp_log_msgs1
#                 l_msg = '_registry_lock obtained, group_name = group1, thread_name = beta, class name = MyThread'
#                 self.exp_log_msgs.add_msg(l_msg)
#                 l_msg = 'beta registered not first entry for group group1'
#                 self.exp_log_msgs.add_msg(l_msg)
#
#             def run(self):
#                 self.exp_log_msgs.add_msg('ThreadApp run entered')
#                 logger.debug('ThreadApp run entered')
#
#                 descs.add_desc(SmartThreadDesc(smart_thread=self))
#                 cmds.queue_cmd('alpha')
#
#                 self.exp_log_msgs.add_beta_pair_with_msg('beta to alpha 3',
#                                                          ['beta', 'alpha'])
#                 self.pair_with(remote_name='alpha',
#                                log_msg='beta to alpha 3')
#                 descs.paired('alpha', 'beta')
#
#                 cmds.get_cmd('beta')
#
#         cmds = Cmds()
#         descs = SmartThreadDescs()
#         if log_enabled_arg:
#             logging.getLogger().setLevel(logging.DEBUG)
#         else:
#             logging.getLogger().setLevel(logging.INFO)
#
#         alpha_call_seq = ('test_smart_thread.py::TestSmartThreadLogger.'
#                           'test_smart_thread_thread_event_app_event_logger')
#
#         beta_call_seq = 'test_smart_thread.py::run'
#         exp_log_msgs = ExpLogMsgs(alpha_call_seq, beta_call_seq)
#         l_msg = 'mainline starting'
#         exp_log_msgs.add_msg(l_msg)
#         logger.debug(l_msg)
#
#         l_msg = '_registry_lock obtained, group_name = group1, thread_name = alpha, class name = SmartThread'
#         exp_log_msgs.add_msg(l_msg)
#         l_msg = 'alpha registered first entry for group group1'
#         exp_log_msgs.add_msg(l_msg)
#         smart_thread = SmartThread(group_name='group1', name='alpha')
#         descs.add_desc(SmartThreadDesc(smart_thread=smart_thread))
#
#         thread_event_app = MyThread(exp_log_msgs1=exp_log_msgs)
#
#         thread_event_app.start()
#
#         cmds.get_cmd('alpha')
#
#         exp_log_msgs.add_alpha_pair_with_msg('alpha to beta 3',
#                                              ['alpha', 'beta'])
#         smart_thread.pair_with(remote_name='beta',
#                               log_msg='alpha to beta 3')
#
#         cmds.queue_cmd('beta')
#
#         thread_event_app.join()
#         descs.thread_end('beta')
#
#         exp_log_msgs.add_msg('mainline all tests complete')
#         logger.debug('mainline all tests complete')
#
#         exp_log_msgs.verify_log_msgs(caplog=caplog,
#                                      log_enabled_tf=log_enabled_arg)
#
#         # restore root to debug
#         logging.getLogger().setLevel(logging.DEBUG)
#
#
# ###############################################################################
# # TestCombos Class
# ###############################################################################
# class TestCombos:
#     """Test various combinations of SmartThread."""
#     ###########################################################################
#     # test_smart_thread_thread_f1_combos
#     ###########################################################################
#     def test_smart_thread_f1_combos(self,
#                                    action_arg1: Any,
#                                    code_arg1: Any,
#                                    log_msg_arg1: Any,
#                                    action_arg2: Any,
#                                    caplog: Any,
#                                    thread_exc: Any) -> None:
#         """Test the SmartThread with f1 combos.
#
#         Args:
#             action_arg1: first action
#             code_arg1: whether to set and recv a code
#             log_msg_arg1: whether to specify a log message
#             action_arg2: second action
#             caplog: fixture to capture log messages
#             thread_exc: intercepts thread exceptions
#
#         """
#         alpha_call_seq = ('test_smart_thread.py::TestCombos.action_loop')
#         beta_call_seq = ('test_smart_thread.py::thread_func1')
#         exp_log_msgs = ExpLogMsgs(alpha_call_seq, beta_call_seq)
#         l_msg = 'mainline entered'
#         exp_log_msgs.add_msg(l_msg)
#         logger.debug(l_msg)
#
#         cmds = Cmds()
#         descs = SmartThreadDescs()
#
#         cmds.l_msg = log_msg_arg1
#         cmds.r_code = code_arg1
#
#         f1_thread = threading.Thread(target=thread_func1,
#                                      args=(cmds,
#                                            descs,
#                                            exp_log_msgs))
#
#         l_msg = 'mainline about to start thread_func1'
#         exp_log_msgs.add_msg(l_msg)
#         logger.debug(l_msg)
#
#         f1_thread.start()
#
#         self.action_loop(action1=action_arg1,
#                          action2=action_arg2,
#                          cmds=cmds,
#                          descs=descs,
#                          exp_log_msgs=exp_log_msgs,
#                          thread_exc1=thread_exc)
#
#         l_msg = 'main completed all actions'
#         exp_log_msgs.add_msg(l_msg)
#         logger.debug(l_msg)
#
#         cmds.queue_cmd('beta', Cmd.Exit)
#
#         f1_thread.join()
#         descs.thread_end('beta')
#
#         if log_msg_arg1:
#             exp_log_msgs.verify_log_msgs(caplog=caplog, log_enabled_tf=True)
#
#     ###########################################################################
#     # test_smart_thread_thread_f1_combos
#     ###########################################################################
#     def test_smart_thread_f1_f2_combos(self,
#                                       action_arg1: Any,
#                                       code_arg1: Any,
#                                       log_msg_arg1: Any,
#                                       action_arg2: Any,
#                                       caplog: Any,
#                                       thread_exc: Any) -> None:
#         """Test the SmartThread with f1 anf f2 combos.
#
#         Args:
#             action_arg1: first action
#             code_arg1: whether to set and recv a code
#             log_msg_arg1: whether to specify a log message
#             action_arg2: second action
#             caplog: fixture to capture log messages
#             thread_exc: intercepts thread exceptions
#
#         """
#         alpha_call_seq = ('test_smart_thread.py::TestCombos.action_loop')
#         beta_call_seq = ('test_smart_thread.py::thread_func1')
#         exp_log_msgs = ExpLogMsgs(alpha_call_seq, beta_call_seq)
#         l_msg = 'mainline entered'
#         exp_log_msgs.add_msg(l_msg)
#         logger.debug(l_msg)
#
#         cmds = Cmds()
#         descs = SmartThreadDescs()
#
#         cmds.l_msg = log_msg_arg1
#         cmds.r_code = code_arg1
#
#         f1_thread = threading.Thread(target=thread_func1,
#                                      args=(cmds,
#                                            descs,
#                                            exp_log_msgs))
#
#         f2_thread = threading.Thread(target=self.action_loop,
#                                      args=(action_arg1,
#                                            action_arg2,
#                                            cmds,
#                                            descs,
#                                            exp_log_msgs,
#                                            thread_exc))
#
#         l_msg = 'mainline about to start thread_func1'
#         exp_log_msgs.add_msg(l_msg)
#         logger.debug(l_msg)
#
#         f1_thread.start()
#         f2_thread.start()
#
#         l_msg = 'main completed all actions'
#         exp_log_msgs.add_msg(l_msg)
#         logger.debug(l_msg)
#
#         f2_thread.join()
#         descs.thread_end('alpha')
#         cmds.queue_cmd('beta', Cmd.Exit)
#
#         f1_thread.join()
#         descs.thread_end('beta')
#
#         if log_msg_arg1:
#             exp_log_msgs.verify_log_msgs(caplog=caplog, log_enabled_tf=True)
#
#     ###########################################################################
#     # test_smart_thread_thread_thread_app_combos
#     ###########################################################################
#     def test_smart_thread_thread_app_combos(self,
#                                            action_arg1: Any,
#                                            code_arg1: Any,
#                                            log_msg_arg1: Any,
#                                            action_arg2: Any,
#                                            caplog: Any,
#                                            thread_exc: Any) -> None:
#         """Test the SmartThread with ThreadApp combos.
#
#         Args:
#             action_arg1: first action
#             code_arg1: whether to set and recv a code
#             log_msg_arg1: whether to specify a log message
#             action_arg2: second action
#             caplog: fixture to capture log messages
#             thread_exc: intercepts thread exceptions
#
#         """
#         class SmartThreadApp(threading.Thread):
#             """SmartThreadApp class with thread."""
#             def __init__(self,
#                          cmds: Cmds,
#                          exp_log_msgs: ExpLogMsgs
#                          ) -> None:
#                 """Initialize the object.
#
#                 Args:
#                     cmds: commands for beta to do
#                     exp_log_msgs: container for expected log messages
#
#                 """
#                 super().__init__()
#                 self.smart_thread = SmartThread(group_name='group1', name='beta', thread=self)
#                 self.cmds = cmds
#                 self.exp_log_msgs = exp_log_msgs
#
#             def run(self):
#                 """Thread to send and receive messages."""
#                 l_msg = 'SmartThreadApp run started'
#                 self.exp_log_msgs.add_msg(l_msg)
#                 logger.debug(l_msg)
#                 thread_func1(
#                     cmds=self.cmds,
#                     descs=descs,
#                     exp_log_msgs=self.exp_log_msgs,
#                     smart_thread=self.smart_thread)
#
#                 l_msg = 'SmartThreadApp run exiting'
#                 self.exp_log_msgs.add_msg(l_msg)
#                 logger.debug(l_msg)
#
#         alpha_call_seq = ('test_smart_thread.py::TestCombos.action_loop')
#         beta_call_seq = ('test_smart_thread.py::thread_func1')
#         exp_log_msgs = ExpLogMsgs(alpha_call_seq, beta_call_seq)
#         l_msg = 'mainline entered'
#         exp_log_msgs.add_msg(l_msg)
#         logger.debug(l_msg)
#
#         cmds = Cmds()
#         descs = SmartThreadDescs()
#
#         cmds.l_msg = log_msg_arg1
#         cmds.r_code = code_arg1
#
#         f1_thread = SmartThreadApp(cmds,
#                                   exp_log_msgs)
#
#         l_msg = 'mainline about to start SmartThreadApp'
#         exp_log_msgs.add_msg(l_msg)
#         logger.debug(l_msg)
#
#         f1_thread.start()
#
#         self.action_loop(action1=action_arg1,
#                          action2=action_arg2,
#                          cmds=cmds,
#                          descs=descs,
#                          exp_log_msgs=exp_log_msgs,
#                          thread_exc1=thread_exc)
#
#         l_msg = 'main completed all actions'
#         exp_log_msgs.add_msg(l_msg)
#         logger.debug(l_msg)
#         cmds.queue_cmd('beta', Cmd.Exit)
#
#         f1_thread.join()
#         descs.thread_end('beta')
#
#         if log_msg_arg1:
#             exp_log_msgs.verify_log_msgs(caplog=caplog, log_enabled_tf=True)
#
#     ###########################################################################
#     # test_smart_thread_thread_thread_app_combos
#     ###########################################################################
#     def test_smart_thread_thread_event_app_combos(self,
#                                                  action_arg1: Any,
#                                                  code_arg1: Any,
#                                                  log_msg_arg1: Any,
#                                                  action_arg2: Any,
#                                                  caplog: Any,
#                                                  thread_exc: Any) -> None:
#         """Test the SmartThread with ThreadApp combos.
#
#         Args:
#             action_arg1: first action
#             code_arg1: whether to set and recv a code
#             log_msg_arg1: whether to specify a log message
#             action_arg2: second action
#             caplog: fixture to capture log messages
#             thread_exc: intercepts thread exceptions
#
#         """
#         class SmartThreadApp(threading.Thread, SmartThread):
#             """SmartThreadApp class with thread and event."""
#             def __init__(self,
#                          cmds: Cmds,
#                          exp_log_msgs: ExpLogMsgs
#                          ) -> None:
#                 """Initialize the object.
#
#                 Args:
#                     cmds: commands for beta to do
#                     exp_log_msgs: container for expected log messages
#
#                 """
#                 threading.Thread.__init__(self)
#                 SmartThread.__init__(self,
#                                     group_name='group1',
#                                     name='beta',
#                                     thread=self)
#
#                 self.cmds = cmds
#                 self.exp_log_msgs = exp_log_msgs
#
#             def run(self):
#                 """Thread to send and receive messages."""
#                 l_msg = 'SmartThreadApp run started'
#                 self.exp_log_msgs.add_msg(l_msg)
#                 logger.debug(l_msg)
#                 thread_func1(
#                     cmds=self.cmds,
#                     descs=descs,
#                     exp_log_msgs=self.exp_log_msgs,
#                     smart_thread=self)
#
#                 l_msg = 'SmartThreadApp run exiting'
#                 self.exp_log_msgs.add_msg(l_msg)
#                 logger.debug(l_msg)
#
#         alpha_call_seq = ('test_smart_thread.py::TestCombos.action_loop')
#         beta_call_seq = ('test_smart_thread.py::thread_func1')
#         exp_log_msgs = ExpLogMsgs(alpha_call_seq, beta_call_seq)
#         l_msg = 'mainline entered'
#         exp_log_msgs.add_msg(l_msg)
#         logger.debug(l_msg)
#
#         cmds = Cmds()
#         descs = SmartThreadDescs()
#
#         cmds.l_msg = log_msg_arg1
#         cmds.r_code = code_arg1
#
#         f1_thread = SmartThreadApp(cmds,
#                                   exp_log_msgs)
#
#         l_msg = 'mainline about to start SmartThreadApp'
#         exp_log_msgs.add_msg(l_msg)
#         logger.debug(l_msg)
#         f1_thread.start()
#
#         self.action_loop(action1=action_arg1,
#                          action2=action_arg2,
#                          cmds=cmds,
#                          descs=descs,
#                          exp_log_msgs=exp_log_msgs,
#                          thread_exc1=thread_exc)
#
#         l_msg = 'main completed all actions'
#         exp_log_msgs.add_msg(l_msg)
#         logger.debug(l_msg)
#         cmds.queue_cmd('beta', Cmd.Exit)
#
#         f1_thread.join()
#         descs.thread_end('beta')
#
#         if log_msg_arg1:
#             exp_log_msgs.verify_log_msgs(caplog=caplog, log_enabled_tf=True)
#
#     ###########################################################################
#     # action loop
#     ###########################################################################
#     def action_loop(self,
#                     action1: Any,
#                     action2: Any,
#                     cmds: Cmds,
#                     descs: SmartThreadDescs,
#                     exp_log_msgs: Any,
#                     thread_exc1: Any
#                     ) -> None:
#         """Actions to perform with the thread.
#
#         Args:
#             action1: first smart event request to do
#             action2: second smart event request to do
#             cmds: contains cmd queues and other test args
#             descs: tracking and verification for registry
#             exp_log_msgs: container for expected log messages
#             thread_exc1: contains any uncaptured errors from thread
#
#         Raises:
#             IncorrectActionSpecified: The Action is not recognized
#             UnrecognizedCmd: beta send mainline an unrecognized command
#
#         """
#         cmds.get_cmd('alpha')  # go1
#         smart_thread = SmartThread(group_name='group1', name='alpha')
#         descs.add_desc(SmartThreadDesc(smart_thread=smart_thread))
#         cmds.queue_cmd('beta')  # go2
#         smart_thread.pair_with(remote_name='beta')
#         cmds.get_cmd('alpha')  # go3
#
#         actions = []
#         actions.append(action1)
#         actions.append(action2)
#         for action in actions:
#
#             if action == Action.MainWait:
#                 l_msg = 'main starting Action.MainWait'
#                 exp_log_msgs.add_msg(l_msg)
#                 logger.debug(l_msg)
#
#                 cmds.queue_cmd('beta', Cmd.Resume)
#                 assert smart_thread.wait()
#                 if cmds.r_code:
#                     assert smart_thread.code == cmds.r_code
#                     assert cmds.r_code == smart_thread.get_code()
#
#             elif action == Action.MainSync:
#                 l_msg = 'main starting Action.MainSync'
#                 exp_log_msgs.add_msg(l_msg)
#                 logger.debug(l_msg)
#
#                 cmds.queue_cmd('beta', Cmd.Sync)
#
#                 if cmds.l_msg:
#                     exp_log_msgs.add_alpha_sync_msg(cmds.l_msg, True)
#                     assert smart_thread.sync(log_msg=cmds.l_msg)
#                 else:
#                     assert smart_thread.sync()
#
#             elif action == Action.MainSync_TOT:
#                 l_msg = 'main starting Action.MainSync_TOT'
#                 exp_log_msgs.add_msg(l_msg)
#                 logger.debug(l_msg)
#
#                 cmds.queue_cmd('beta', Cmd.Sync)
#
#                 if cmds.l_msg:
#                     exp_log_msgs.add_alpha_sync_msg(cmds.l_msg, True)
#                     assert smart_thread.sync(timeout=5,
#                                             log_msg=cmds.l_msg)
#                 else:
#                     assert smart_thread.sync(timeout=5)
#
#             elif action == Action.MainSync_TOF:
#                 l_msg = 'main starting Action.MainSync_TOF'
#                 exp_log_msgs.add_msg(l_msg)
#                 logger.debug(l_msg)
#                 l_msg = r'alpha timeout of a sync\(\) request.'
#                 exp_log_msgs.add_msg(l_msg)
#
#                 if cmds.l_msg:
#                     exp_log_msgs.add_alpha_sync_msg(cmds.l_msg, False)
#                     assert not smart_thread.sync(timeout=0.3,
#                                                 log_msg=cmds.l_msg)
#                 else:
#                     assert not smart_thread.sync(timeout=0.3)
#
#                 # for this case, we did not tell beta to do anything, so
#                 # we need to tell ourselves to go to next action.
#                 # Note that we could use a continue, but we also want
#                 # to check for thread exception which is what we do
#                 # at the bottom
#                 cmds.queue_cmd('alpha', Cmd.Next_Action)
#
#             elif action == Action.MainResume:
#                 l_msg = 'main starting Action.MainResume'
#                 exp_log_msgs.add_msg(l_msg)
#                 logger.debug(l_msg)
#                 if cmds.r_code:
#                     assert smart_thread.resume(code=cmds.r_code)
#                     assert smart_thread.remote.code == cmds.r_code
#                 else:
#                     assert smart_thread.resume()
#                     assert not smart_thread.remote.code
#
#                 assert smart_thread.event.is_set()
#                 cmds.queue_cmd('beta', Cmd.Wait)
#
#             elif action == Action.MainResume_TOT:
#                 l_msg = 'main starting Action.MainResume_TOT'
#                 exp_log_msgs.add_msg(l_msg)
#                 logger.debug(l_msg)
#                 if cmds.r_code:
#                     assert smart_thread.resume(code=cmds.r_code, timeout=0.5)
#                     assert smart_thread.remote.code == cmds.r_code
#                 else:
#                     assert smart_thread.resume(timeout=0.5)
#                     assert not smart_thread.remote.code
#
#                 assert smart_thread.event.is_set()
#                 cmds.queue_cmd('beta', Cmd.Wait)
#
#             elif action == Action.MainResume_TOF:
#                 l_msg = 'main starting Action.MainResume_TOF'
#                 exp_log_msgs.add_msg(l_msg)
#                 logger.debug(l_msg)
#                 l_msg = (f'{smart_thread.name} timeout '
#                          r'of a resume\(\) request with '
#                          r'self.event.is_set\(\) = True and '
#                          'self.remote.deadlock = False')
#                 exp_log_msgs.add_msg(l_msg)
#
#                 assert not smart_thread.event.is_set()
#                 # pre-resume to set flag
#                 if cmds.r_code:
#                     assert smart_thread.resume(code=cmds.r_code)
#                     assert smart_thread.remote.code == cmds.r_code
#                 else:
#                     assert smart_thread.resume()
#                     assert not smart_thread.remote.code
#
#                 assert smart_thread.event.is_set()
#
#                 if cmds.r_code:
#                     start_time = time.time()
#                     assert not smart_thread.resume(code=cmds.r_code,
#                                                   timeout=0.3)
#                     assert 0.3 <= (time.time() - start_time) <= 0.5
#                     assert smart_thread.remote.code == cmds.r_code
#                 else:
#                     start_time = time.time()
#                     assert not smart_thread.resume(timeout=0.5)
#                     assert 0.5 <= (time.time() - start_time) <= 0.75
#                     assert not smart_thread.remote.code
#
#                 assert smart_thread.event.is_set()
#
#                 # tell thread to clear wait
#                 cmds.queue_cmd('beta', Cmd.Wait_Clear)
#
#             elif action == Action.ThreadWait:
#                 l_msg = 'main starting Action.ThreadWait'
#                 exp_log_msgs.add_msg(l_msg)
#                 logger.debug(l_msg)
#
#                 cmds.queue_cmd('beta', Cmd.Wait)
#                 smart_thread.pause_until(WUCond.RemoteWaiting)
#                 if cmds.r_code:
#                     smart_thread.resume(code=cmds.r_code)
#                     assert smart_thread.remote.code == cmds.r_code
#                 else:
#                     smart_thread.resume()
#
#             elif action == Action.ThreadWait_TOT:
#                 l_msg = 'main starting Action.ThreadWait_TOT'
#                 exp_log_msgs.add_msg(l_msg)
#                 logger.debug(l_msg)
#
#                 cmds.queue_cmd('beta', Cmd.Wait_TOT)
#                 smart_thread.pause_until(WUCond.RemoteWaiting)
#                 # time.sleep(0.3)
#                 if cmds.r_code:
#                     smart_thread.resume(code=cmds.r_code)
#                     assert smart_thread.remote.code == cmds.r_code
#                 else:
#                     smart_thread.resume()
#
#             elif action == Action.ThreadWait_TOF:
#                 l_msg = 'main starting Action.ThreadWait_TOF'
#                 exp_log_msgs.add_msg(l_msg)
#                 logger.debug(l_msg)
#
#                 cmds.queue_cmd('beta', Cmd.Wait_TOF)
#                 smart_thread.pause_until(WUCond.RemoteWaiting)
#
#             elif action == Action.ThreadResume:
#                 l_msg = 'main starting Action.ThreadResume'
#                 exp_log_msgs.add_msg(l_msg)
#                 logger.debug(l_msg)
#
#                 cmds.queue_cmd('beta', Cmd.Resume)
#                 smart_thread.pause_until(WUCond.RemoteResume)
#                 assert smart_thread.wait()
#                 if cmds.r_code:
#                     assert smart_thread.code == cmds.r_code
#                     assert cmds.r_code == smart_thread.get_code()
#             else:
#                 raise IncorrectActionSpecified('The Action is not recognized')
#
#             while True:
#                 thread_exc1.raise_exc_if_one()  # detect thread error
#                 alpha_cmd = cmds.get_cmd('alpha')
#                 if alpha_cmd == Cmd.Next_Action:
#                     break
#                 else:
#                     raise UnrecognizedCmd
#
#         # clear the codes to allow verify registry to work
#         smart_thread.code = None
#         smart_thread.remote.code = None
#
#
# ###############################################################################
# # thread_func1
# ###############################################################################
# def thread_func1(cmds: Cmds,
#                  descs: SmartThreadDescs,
#                  exp_log_msgs: Any,
#                  t_pair: Optional[SmartThread] = None,
#                  ) -> None:
#     """Thread to test SmartThread scenarios.
#
#     Args:
#         cmds: commands to do
#         descs: used to verify registry and SmartThread status
#         exp_log_msgs: expected log messages
#         t_pair: instance of SmartThread
#
#     Raises:
#         UnrecognizedCmd: Thread received an unrecognized command
#
#     """
#     l_msg = 'thread_func1 beta started'
#     exp_log_msgs.add_msg(l_msg)
#     logger.debug(l_msg)
#
#     if t_pair is None:
#         t_pair = SmartThread(group_name='group1', name='beta')
#
#     descs.add_desc(SmartThreadDesc(smart_thread=t_pair))
#     cmds.queue_cmd('alpha', 'go1')
#     cmds.get_cmd('beta')  # go2
#     t_pair.pair_with(remote_name='alpha')
#     descs.paired('alpha', 'beta')
#     cmds.queue_cmd('alpha', 'go3')
#
#     while True:
#         beta_cmd = cmds.get_cmd('beta')
#         if beta_cmd == Cmd.Exit:
#             break
#
#         l_msg = f'thread_func1 received cmd: {beta_cmd}'
#         exp_log_msgs.add_msg(l_msg)
#         logger.debug(l_msg)
#
#         if beta_cmd == Cmd.Wait:
#             l_msg = 'thread_func1 doing Wait'
#             exp_log_msgs.add_msg(l_msg)
#             logger.debug(l_msg)
#             if cmds.l_msg:
#                 exp_log_msgs.add_beta_wait_msg(cmds.l_msg, True)
#                 assert t_pair.wait(log_msg=cmds.l_msg)
#             else:
#                 assert t_pair.wait()
#             if cmds.r_code:
#                 assert t_pair.code == cmds.r_code
#                 assert cmds.r_code == t_pair.get_code()
#
#             cmds.queue_cmd('alpha', Cmd.Next_Action)
#
#         elif beta_cmd == Cmd.Wait_TOT:
#             l_msg = 'thread_func1 doing Wait_TOT'
#             exp_log_msgs.add_msg(l_msg)
#             logger.debug(l_msg)
#             if cmds.l_msg:
#                 exp_log_msgs.add_beta_wait_msg(cmds.l_msg, True)
#                 assert t_pair.wait(log_msg=cmds.l_msg)
#             else:
#                 assert t_pair.wait()
#             if cmds.r_code:
#                 assert t_pair.code == cmds.r_code
#                 assert cmds.r_code == t_pair.get_code()
#
#             cmds.queue_cmd('alpha', Cmd.Next_Action)
#
#         elif beta_cmd == Cmd.Wait_TOF:
#             l_msg = 'thread_func1 doing Wait_TOF'
#             exp_log_msgs.add_msg(l_msg)
#             logger.debug(l_msg)
#             l_msg = (f'{t_pair.name} timeout of a '
#                      r'wait\(\) request with '
#                      'self.wait_wait = True and '
#                      'self.sync_wait = False')
#             exp_log_msgs.add_msg(l_msg)
#
#             start_time = time.time()
#             if cmds.l_msg:
#                 exp_log_msgs.add_beta_wait_msg(cmds.l_msg, False)
#                 assert not t_pair.wait(timeout=0.5,
#                                         log_msg=cmds.l_msg)
#             else:
#                 assert not t_pair.wait(timeout=0.5)
#             assert 0.5 < (time.time() - start_time) < 0.75
#
#             cmds.queue_cmd('alpha', Cmd.Next_Action)
#
#         elif beta_cmd == Cmd.Wait_Clear:
#             l_msg = 'thread_func1 doing Wait_Clear'
#             exp_log_msgs.add_msg(l_msg)
#             logger.debug(l_msg)
#             if cmds.l_msg:
#                 exp_log_msgs.add_beta_wait_msg(cmds.l_msg, True)
#                 assert t_pair.wait(log_msg=cmds.l_msg)
#             else:
#                 assert t_pair.wait()
#
#             if cmds.r_code:
#                 assert t_pair.code == cmds.r_code
#                 assert cmds.r_code == t_pair.get_code()
#
#             cmds.queue_cmd('alpha', Cmd.Next_Action)
#
#         elif beta_cmd == Cmd.Sync:
#             l_msg = 'thread_func1 beta doing Sync'
#             exp_log_msgs.add_msg(l_msg)
#             logger.debug(l_msg)
#
#             if cmds.l_msg:
#                 exp_log_msgs.add_beta_sync_msg(cmds.l_msg, True)
#                 assert t_pair.sync(log_msg=cmds.l_msg)
#             else:
#                 assert t_pair.sync()
#
#             cmds.queue_cmd('alpha', Cmd.Next_Action)
#
#         elif beta_cmd == Cmd.Resume:
#             l_msg = 'thread_func1 beta doing Resume'
#             exp_log_msgs.add_msg(l_msg)
#             logger.debug(l_msg)
#             if cmds.r_code:
#                 if cmds.l_msg:
#                     exp_log_msgs.add_beta_resume_msg(cmds.l_msg,
#                                                      True,
#                                                      cmds.r_code)
#                     assert t_pair.resume(code=cmds.r_code,
#                                           log_msg=cmds.l_msg)
#                 else:
#                     assert t_pair.resume(code=cmds.r_code)
#                 assert t_pair.remote.code == cmds.r_code
#             else:
#                 if cmds.l_msg:
#                     exp_log_msgs.add_beta_resume_msg(cmds.l_msg, True)
#                     assert t_pair.resume(log_msg=cmds.l_msg)
#                 else:
#                     assert t_pair.resume()
#
#             cmds.queue_cmd('alpha', Cmd.Next_Action)
#         else:
#             raise UnrecognizedCmd('Thread received an unrecognized cmd')
#
#     l_msg = 'thread_func1 beta exiting'
#     exp_log_msgs.add_msg(l_msg)
#     logger.debug(l_msg)
