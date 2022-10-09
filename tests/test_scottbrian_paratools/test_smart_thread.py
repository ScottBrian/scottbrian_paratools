"""test_smart_thread.py module."""

###############################################################################
# Standard Library
###############################################################################
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto
from itertools import combinations
import logging
import queue
import random
import re
import time
from typing import Any, Callable, cast, Type, TYPE_CHECKING, Optional
import threading

###############################################################################
# Third Party
###############################################################################
import pytest
from scottbrian_utils.msgs import Msgs, GetMsgTimedOut
from scottbrian_utils.log_verifier import LogVer
from scottbrian_utils.diag_msg import get_formatted_call_sequence

###############################################################################
# Local
###############################################################################
import scottbrian_paratools.smart_thread as st

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


class InvalidConfigurationDetected(ErrorTstSmartThread):
    """UnrecognizedCmd exception class."""
    pass


###############################################################################
# Config Scenarios
###############################################################################
class ConfigCmds(Enum):
    Create = auto()
    Start = auto()
    SendMsg = auto()
    RecvMsg = auto()
    Join = auto()
    VerifyRegistered = auto()
    VerifyNotRegistered = auto()
    VerifyPaired = auto()
    VerifyHalfPaired = auto()
    VerifyNotPaired = auto()
    VerifyAlive = auto()
    VerifyNotAlive = auto()
    VerifyStatus = auto()
    Exit = auto()


@dataclass
class ConfigCmd:
    cmd: ConfigCmds
    executor: Optional[str] = 'alpha'
    names: Optional[list[str]] = None
    auto_start: bool = True
    from_names: Optional[list[str]] = None
    to_names: Optional[list[str]] = None
    exp_status: Optional[st.ThreadStatus] = None
    half_paired_names: Optional[list[str]] = None


########################################################################
# 0) start alpha and beta threads
# 1) send msg from f1 to alpha
# 2) alpha recv msg
########################################################################
config_scenario_0 = (
    # 0) start alpha and beta threads
    ConfigCmd(cmd=ConfigCmds.Create, names=['beta']),

    ConfigCmd(cmd=ConfigCmds.VerifyRegistered, names=['alpha', 'beta']),
    ConfigCmd(cmd=ConfigCmds.VerifyPaired, names=['alpha', 'beta']),
    ConfigCmd(cmd=ConfigCmds.VerifyAlive, names=['alpha', 'beta']),
    ConfigCmd(cmd=ConfigCmds.VerifyStatus, names=['alpha', 'beta'],
              exp_status=st.ThreadStatus.Alive),

    # 1) send msg from f1 to alpha
    ConfigCmd(cmd=ConfigCmds.SendMsg, from_names=['beta'],
              to_names=['alpha']),

    # 2) alpha recv msg
    ConfigCmd(cmd=ConfigCmds.RecvMsg, from_names=['beta'],
              to_names=['alpha']),

    ConfigCmd(cmd=ConfigCmds.Exit, names=['beta']),

    ConfigCmd(cmd=ConfigCmds.VerifyAlive, names=['alpha']),
    ConfigCmd(cmd=ConfigCmds.VerifyStatus, names=['alpha'],
              exp_status=st.ThreadStatus.Alive),
    ConfigCmd(cmd=ConfigCmds.VerifyNotAlive, names=['beta']),
    ConfigCmd(cmd=ConfigCmds.VerifyStatus, names=['beta'],
              exp_status=st.ThreadStatus.Alive),

    ConfigCmd(cmd=ConfigCmds.Join, names=['beta']),
    ConfigCmd(cmd=ConfigCmds.VerifyRegistered, names=['alpha']),
    ConfigCmd(cmd=ConfigCmds.VerifyNotRegistered, names=['beta']),
    ConfigCmd(cmd=ConfigCmds.VerifyNotPaired, names=['alpha', 'beta']),
)

########################################################################
# 0) start alpha, beta, and charlie threads
# 1) beta and charlie send msg to alpha
# 2) beta and charlie exit
# 3) verify alpha half paired with beta
# 4) alpha recv msg from beta
# 5) verify no pair with beta
########################################################################
config_scenario_1 = (
    # 0) start alpha, beta, and charlie threads
    ConfigCmd(cmd=ConfigCmds.Create, names=['beta', 'charlie']),

    ConfigCmd(cmd=ConfigCmds.VerifyRegistered,
              names=['alpha', 'beta', 'charlie']),
    ConfigCmd(cmd=ConfigCmds.VerifyPaired, names=['alpha', 'beta', 'charlie']),
    ConfigCmd(cmd=ConfigCmds.VerifyAlive, names=['alpha', 'beta', 'charlie']),
    ConfigCmd(cmd=ConfigCmds.VerifyStatus, names=['alpha', 'beta', 'charlie'],
              exp_status=st.ThreadStatus.Alive),

    # 1) beta and charlie send msg to alpha
    ConfigCmd(cmd=ConfigCmds.SendMsg, from_names=['beta', 'charlie'],
              to_names=['alpha']),

    # 2) beta and charlie exit
    ConfigCmd(cmd=ConfigCmds.Exit, names=['beta', 'charlie']),

    ConfigCmd(cmd=ConfigCmds.VerifyAlive, names=['alpha']),
    ConfigCmd(cmd=ConfigCmds.VerifyStatus, names=['alpha'],
              exp_status=st.ThreadStatus.Alive),
    ConfigCmd(cmd=ConfigCmds.VerifyNotAlive, names=['beta', 'charlie']),
    ConfigCmd(cmd=ConfigCmds.VerifyStatus, names=['beta', 'charlie'],
              exp_status=st.ThreadStatus.Alive),

    # 3) join and verify alpha half paired with beta
    ConfigCmd(cmd=ConfigCmds.Join, names=['beta']),

    ConfigCmd(cmd=ConfigCmds.VerifyNotRegistered, names=['beta']),
    ConfigCmd(cmd=ConfigCmds.VerifyRegistered,
              names=['alpha', 'charlie']),
    ConfigCmd(cmd=ConfigCmds.VerifyPaired, names=['alpha', 'charlie']),
    ConfigCmd(cmd=ConfigCmds.VerifyHalfPaired,
              names=['alpha', 'beta'], half_paired_names=['alpha']),
    ConfigCmd(cmd=ConfigCmds.VerifyNotPaired, names=['beta', 'charlie']),

    # 4) alpha recv msg from beta
    ConfigCmd(cmd=ConfigCmds.RecvMsg, from_names=['beta', 'charlie'],
              to_names=['alpha']),

    # 5) verify not paired with beta
    ConfigCmd(cmd=ConfigCmds.VerifyPaired, names=['alpha', 'charlie']),
    ConfigCmd(cmd=ConfigCmds.VerifyNotPaired, names=['alpha', 'beta']),
    ConfigCmd(cmd=ConfigCmds.VerifyNotPaired, names=['beta', 'charlie']),


    ConfigCmd(cmd=ConfigCmds.Join, names=['charlie']),

    ConfigCmd(cmd=ConfigCmds.VerifyNotRegistered, names=['beta', 'charlie']),
    ConfigCmd(cmd=ConfigCmds.VerifyNotPaired,
              names=['alpha', 'beta', 'charlie']),
    ConfigCmd(cmd=ConfigCmds.VerifyAlive, names=['alpha']),
    ConfigCmd(cmd=ConfigCmds.VerifyStatus, names=['alpha'],
              exp_status=st.ThreadStatus.Alive),
)

########################################################################
# 0) start alpha and beta threads
# 1) beta exits
# 2) verify alpha and beta not paired
# 3) start beta thread again
# 4) verify alpha and beta are paired
# 5) beta send msg to alpha
# 6) beta exits
# 7) verify alpha half paired with beta
# 8) start beta again
# 9) verify alpha and beta are paired
# 10) beta exits
# 11) verify alpha half paired with beta
# 12) alpha recv msg from beta
# 13) verify alpha not paired with beta

########################################################################
config_scenario_2 = (
    # 0) start alpha and beta threads
    ConfigCmd(cmd=ConfigCmds.Create, names=['beta']),

    ConfigCmd(cmd=ConfigCmds.VerifyRegistered,
              names=['alpha', 'beta']),
    ConfigCmd(cmd=ConfigCmds.VerifyPaired, names=['alpha', 'beta']),
    ConfigCmd(cmd=ConfigCmds.VerifyAlive, names=['alpha', 'beta']),
    ConfigCmd(cmd=ConfigCmds.VerifyStatus, names=['alpha', 'beta'],
              exp_status=st.ThreadStatus.Alive),

    # 1) beta exits
    ConfigCmd(cmd=ConfigCmds.Exit, names=['beta']),

    ConfigCmd(cmd=ConfigCmds.VerifyAlive, names=['alpha']),
    ConfigCmd(cmd=ConfigCmds.VerifyStatus, names=['alpha'],
              exp_status=st.ThreadStatus.Alive),
    ConfigCmd(cmd=ConfigCmds.VerifyNotAlive, names=['beta']),
    ConfigCmd(cmd=ConfigCmds.VerifyStatus, names=['beta'],
              exp_status=st.ThreadStatus.Alive),

    ConfigCmd(cmd=ConfigCmds.Join, names=['beta']),

    # 2) verify alpha and beta not paired
    ConfigCmd(cmd=ConfigCmds.VerifyNotRegistered, names=['beta']),
    ConfigCmd(cmd=ConfigCmds.VerifyNotPaired,
              names=['alpha', 'beta']),
    ConfigCmd(cmd=ConfigCmds.VerifyAlive, names=['alpha']),
    ConfigCmd(cmd=ConfigCmds.VerifyStatus, names=['alpha'],
              exp_status=st.ThreadStatus.Alive),

    # 3) start beta thread again
    ConfigCmd(cmd=ConfigCmds.Create, names=['beta']),

    # 4) verify alpha and beta are paired
    ConfigCmd(cmd=ConfigCmds.VerifyRegistered,
              names=['alpha', 'beta']),
    ConfigCmd(cmd=ConfigCmds.VerifyPaired, names=['alpha', 'beta']),
    ConfigCmd(cmd=ConfigCmds.VerifyAlive, names=['alpha', 'beta']),
    ConfigCmd(cmd=ConfigCmds.VerifyStatus, names=['alpha', 'beta'],
              exp_status=st.ThreadStatus.Alive),


    # 5) beta send msg to alpha
    ConfigCmd(cmd=ConfigCmds.SendMsg, from_names=['beta'],
              to_names=['alpha']),

    # 6) beta exits
    ConfigCmd(cmd=ConfigCmds.Exit, names=['beta']),

    ConfigCmd(cmd=ConfigCmds.VerifyAlive, names=['alpha']),
    ConfigCmd(cmd=ConfigCmds.VerifyStatus, names=['alpha'],
              exp_status=st.ThreadStatus.Alive),
    ConfigCmd(cmd=ConfigCmds.VerifyNotAlive, names=['beta']),
    ConfigCmd(cmd=ConfigCmds.VerifyStatus, names=['beta'],
              exp_status=st.ThreadStatus.Alive),

    # 7) join and verify alpha half paired with beta
    ConfigCmd(cmd=ConfigCmds.Join, names=['beta']),
    ConfigCmd(cmd=ConfigCmds.VerifyNotRegistered, names=['beta']),
    ConfigCmd(cmd=ConfigCmds.VerifyRegistered,
              names=['alpha']),
    ConfigCmd(cmd=ConfigCmds.VerifyHalfPaired,
              names=['alpha', 'beta'], half_paired_names=['alpha']),

    # 8) start beta again
    ConfigCmd(cmd=ConfigCmds.Create, names=['beta']),

    # 9) verify alpha and beta are paired
    ConfigCmd(cmd=ConfigCmds.VerifyRegistered,
              names=['alpha', 'beta']),
    ConfigCmd(cmd=ConfigCmds.VerifyPaired, names=['alpha', 'beta']),
    ConfigCmd(cmd=ConfigCmds.VerifyAlive, names=['alpha', 'beta']),
    ConfigCmd(cmd=ConfigCmds.VerifyStatus, names=['alpha', 'beta'],
              exp_status=st.ThreadStatus.Alive),

    # 10) beta exits
    ConfigCmd(cmd=ConfigCmds.Exit, names=['beta']),

    ConfigCmd(cmd=ConfigCmds.VerifyAlive, names=['alpha']),
    ConfigCmd(cmd=ConfigCmds.VerifyStatus, names=['alpha'],
              exp_status=st.ThreadStatus.Alive),
    ConfigCmd(cmd=ConfigCmds.VerifyNotAlive, names=['beta']),
    ConfigCmd(cmd=ConfigCmds.VerifyStatus, names=['beta'],
              exp_status=st.ThreadStatus.Alive),

    # 11) join and verify alpha half paired with beta
    ConfigCmd(cmd=ConfigCmds.Join, names=['beta']),
    ConfigCmd(cmd=ConfigCmds.VerifyNotRegistered, names=['beta']),
    ConfigCmd(cmd=ConfigCmds.VerifyRegistered,
              names=['alpha']),
    ConfigCmd(cmd=ConfigCmds.VerifyHalfPaired,
              names=['alpha', 'beta'], half_paired_names=['alpha']),

    # 12) alpha recv msg from beta
    ConfigCmd(cmd=ConfigCmds.RecvMsg, from_names=['beta'],
              to_names=['alpha']),

    # 13) verify alpha not paired with beta
    ConfigCmd(cmd=ConfigCmds.VerifyNotPaired, names=['alpha', 'beta']),
    ConfigCmd(cmd=ConfigCmds.VerifyAlive, names=['alpha']),
    ConfigCmd(cmd=ConfigCmds.VerifyStatus, names=['alpha'],
              exp_status=st.ThreadStatus.Alive),
)

########################################################################
# 0) start alpha, beta, and charlie threads
# 1) charlie send msg to beta
# 2) beta recv msg from charlie
# 3) charlie send msg to beta
# 4) charlie exits
# 5) verify beta half paired with charlie
# 6) beta recv msg from charlie
# 7) verify beta and charlie not paired
# 8) exit beta
# 9) join beta and verify alpha not paired with beta
########################################################################
config_scenario_3 = (
    # 0) start alpha, beta, and charlie threads
    ConfigCmd(cmd=ConfigCmds.Create, names=['beta', 'charlie']),
    ConfigCmd(cmd=ConfigCmds.VerifyRegistered,
              names=['alpha', 'beta', 'charlie']),
    ConfigCmd(cmd=ConfigCmds.VerifyPaired, names=['alpha', 'beta', 'charlie']),
    ConfigCmd(cmd=ConfigCmds.VerifyAlive, names=['alpha', 'beta', 'charlie']),
    ConfigCmd(cmd=ConfigCmds.VerifyStatus, names=['alpha', 'beta', 'charlie'],
              exp_status=st.ThreadStatus.Alive),

    # 1) charlie send msg to beta
    ConfigCmd(cmd=ConfigCmds.SendMsg, from_names=['charlie'],
              to_names=['beta']),

    # 2) beta recv msg from charlie
    ConfigCmd(cmd=ConfigCmds.RecvMsg, from_names=['charlie'],
              to_names=['beta']),

    # 3) charlie send msg to beta
    ConfigCmd(cmd=ConfigCmds.SendMsg, from_names=['charlie'],
              to_names=['beta']),

    # 4) charlie exits
    ConfigCmd(cmd=ConfigCmds.Exit, names=['charlie']),
    ConfigCmd(cmd=ConfigCmds.VerifyAlive, names=['alpha', 'beta']),
    ConfigCmd(cmd=ConfigCmds.VerifyStatus, names=['alpha', 'beta'],
              exp_status=st.ThreadStatus.Alive),
    ConfigCmd(cmd=ConfigCmds.VerifyNotAlive, names=['charlie']),
    ConfigCmd(cmd=ConfigCmds.VerifyStatus, names=['charlie'],
              exp_status=st.ThreadStatus.Alive),

    # 5) join charlie and verify beta half paired with charlie
    ConfigCmd(cmd=ConfigCmds.Join, names=['charlie']),
    ConfigCmd(cmd=ConfigCmds.VerifyNotRegistered, names=['charlie']),
    ConfigCmd(cmd=ConfigCmds.VerifyRegistered,
              names=['alpha', 'beta']),
    ConfigCmd(cmd=ConfigCmds.VerifyPaired, names=['alpha', 'beta']),
    ConfigCmd(cmd=ConfigCmds.VerifyHalfPaired,
              names=['beta', 'charlie'], half_paired_names=['beta']),
    ConfigCmd(cmd=ConfigCmds.VerifyNotPaired, names=['alpha', 'charlie']),

    # 6) beta recv msg from charlie
    ConfigCmd(cmd=ConfigCmds.RecvMsg, from_names=['charlie'],
              to_names=['beta']),

    # 7) verify beta and charlie not paired
    ConfigCmd(cmd=ConfigCmds.VerifyPaired, names=['alpha', 'beta']),
    ConfigCmd(cmd=ConfigCmds.VerifyNotPaired, names=['alpha', 'charlie']),
    ConfigCmd(cmd=ConfigCmds.VerifyNotPaired, names=['beta', 'charlie']),

    # 8) exit beta
    ConfigCmd(cmd=ConfigCmds.Exit, names=['beta']),
    ConfigCmd(cmd=ConfigCmds.VerifyAlive, names=['alpha']),
    ConfigCmd(cmd=ConfigCmds.VerifyStatus, names=['alpha'],
              exp_status=st.ThreadStatus.Alive),
    ConfigCmd(cmd=ConfigCmds.VerifyNotAlive, names=['beta']),
    ConfigCmd(cmd=ConfigCmds.VerifyStatus, names=['beta'],
              exp_status=st.ThreadStatus.Alive),

    # 9) join beta and verify alpha not paired with beta
    ConfigCmd(cmd=ConfigCmds.Join, names=['beta']),
    ConfigCmd(cmd=ConfigCmds.VerifyNotRegistered, names=['beta', 'charlie']),
    ConfigCmd(cmd=ConfigCmds.VerifyRegistered,
              names=['alpha']),
    ConfigCmd(cmd=ConfigCmds.VerifyNotPaired,
              names=['alpha', 'beta', 'charlie']),
    ConfigCmd(cmd=ConfigCmds.VerifyAlive, names=['alpha']),
    ConfigCmd(cmd=ConfigCmds.VerifyStatus, names=['alpha'],
              exp_status=st.ThreadStatus.Alive),
)

########################################################################
# 0) start alpha and beta threads
# 1) verify alpha and beta are paired
# 2) beta send first msg to alpha
# 3) beta send second msg to alpha
# 4) beta exits
# 5) join beta
# 6) verify alpha half paired with beta
# 7) alpha recv first msg from beta
# 8) verify alpha still half paired with beta
# 9) alpha recv second msg from beta
# 10) verify alpha not paired with beta

########################################################################
config_scenario_4 = (
    # 0) start alpha and beta threads
    ConfigCmd(cmd=ConfigCmds.Create, names=['beta']),

    # 1) verify alpha and beta are paired
    ConfigCmd(cmd=ConfigCmds.VerifyRegistered,
              names=['alpha', 'beta']),
    ConfigCmd(cmd=ConfigCmds.VerifyPaired, names=['alpha', 'beta']),
    ConfigCmd(cmd=ConfigCmds.VerifyAlive, names=['alpha', 'beta']),
    ConfigCmd(cmd=ConfigCmds.VerifyStatus, names=['alpha', 'beta'],
              exp_status=st.ThreadStatus.Alive),

    # 2) beta send first msg to alpha
    ConfigCmd(cmd=ConfigCmds.SendMsg, from_names=['beta'],
              to_names=['alpha']),

    # 3) beta send second msg to alpha
    ConfigCmd(cmd=ConfigCmds.SendMsg, from_names=['beta'],
              to_names=['alpha']),

    # 4) beta exits
    ConfigCmd(cmd=ConfigCmds.Exit, names=['beta']),

    ConfigCmd(cmd=ConfigCmds.VerifyAlive, names=['alpha']),
    ConfigCmd(cmd=ConfigCmds.VerifyStatus, names=['alpha'],
              exp_status=st.ThreadStatus.Alive),
    ConfigCmd(cmd=ConfigCmds.VerifyNotAlive, names=['beta']),
    ConfigCmd(cmd=ConfigCmds.VerifyStatus, names=['beta'],
              exp_status=st.ThreadStatus.Alive),

    # 5) join beta
    ConfigCmd(cmd=ConfigCmds.Join, names=['beta']),

    ConfigCmd(cmd=ConfigCmds.VerifyNotRegistered, names=['beta']),
    ConfigCmd(cmd=ConfigCmds.VerifyRegistered,
              names=['alpha']),
    ConfigCmd(cmd=ConfigCmds.VerifyHalfPaired,
              names=['alpha', 'beta'], half_paired_names=['alpha']),

    # 6) verify alpha half paired with beta
    ConfigCmd(cmd=ConfigCmds.VerifyNotRegistered, names=['beta']),
    ConfigCmd(cmd=ConfigCmds.VerifyRegistered, names=['alpha']),
    ConfigCmd(cmd=ConfigCmds.VerifyHalfPaired,
              names=['alpha', 'beta'], half_paired_names=['alpha']),

    # 7) alpha recv first msg from beta
    ConfigCmd(cmd=ConfigCmds.RecvMsg, from_names=['beta'],
              to_names=['alpha']),

    # 8) verify alpha still half paired with beta
    ConfigCmd(cmd=ConfigCmds.VerifyNotRegistered, names=['beta']),
    ConfigCmd(cmd=ConfigCmds.VerifyRegistered, names=['alpha']),
    ConfigCmd(cmd=ConfigCmds.VerifyHalfPaired,
              names=['alpha', 'beta'], half_paired_names=['alpha']),

    # 9) alpha recv second msg from beta
    ConfigCmd(cmd=ConfigCmds.RecvMsg, from_names=['beta'],
              to_names=['alpha']),

    # 10) verify alpha not paired with beta
    ConfigCmd(cmd=ConfigCmds.VerifyNotPaired, names=['alpha', 'beta']),
    ConfigCmd(cmd=ConfigCmds.VerifyAlive, names=['alpha']),
    ConfigCmd(cmd=ConfigCmds.VerifyStatus, names=['alpha'],
              exp_status=st.ThreadStatus.Alive),
)

########################################################################
# 0) start alpha and beta threads, auto_start=False
# 1) start beta
# 2) send msg from f1 to alpha
# 3) alpha recv msg
########################################################################
config_scenario_5 = (
    # 0) start alpha and beta threads, auto_start=False
    ConfigCmd(cmd=ConfigCmds.Create, names=['beta'], auto_start=False),

    ConfigCmd(cmd=ConfigCmds.VerifyRegistered, names=['alpha', 'beta']),
    ConfigCmd(cmd=ConfigCmds.VerifyPaired, names=['alpha', 'beta']),
    ConfigCmd(cmd=ConfigCmds.VerifyAlive, names=['alpha']),
    ConfigCmd(cmd=ConfigCmds.VerifyStatus, names=['alpha'],
              exp_status=st.ThreadStatus.Alive),
    ConfigCmd(cmd=ConfigCmds.VerifyNotAlive, names=['beta']),
    ConfigCmd(cmd=ConfigCmds.VerifyStatus, names=['beta'],
              exp_status=st.ThreadStatus.Registered),

    # 1) start beta
    ConfigCmd(cmd=ConfigCmds.Start, names=['beta']),
    ConfigCmd(cmd=ConfigCmds.VerifyAlive, names=['alpha', 'beta']),
    ConfigCmd(cmd=ConfigCmds.VerifyStatus, names=['alpha', 'beta'],
              exp_status=st.ThreadStatus.Alive),


    # 2) send msg from f1 to alpha
    ConfigCmd(cmd=ConfigCmds.SendMsg, from_names=['beta'],
              to_names=['alpha']),

    # 3) alpha recv msg
    ConfigCmd(cmd=ConfigCmds.RecvMsg, from_names=['beta'],
              to_names=['alpha']),

    ConfigCmd(cmd=ConfigCmds.Exit, names=['beta']),

    ConfigCmd(cmd=ConfigCmds.VerifyAlive, names=['alpha']),
    ConfigCmd(cmd=ConfigCmds.VerifyStatus, names=['alpha'],
              exp_status=st.ThreadStatus.Alive),
    ConfigCmd(cmd=ConfigCmds.VerifyNotAlive, names=['beta']),
    ConfigCmd(cmd=ConfigCmds.VerifyStatus, names=['beta'],
              exp_status=st.ThreadStatus.Alive),

    ConfigCmd(cmd=ConfigCmds.Join, names=['beta']),
    ConfigCmd(cmd=ConfigCmds.VerifyRegistered, names=['alpha']),
    ConfigCmd(cmd=ConfigCmds.VerifyNotRegistered, names=['beta']),
    ConfigCmd(cmd=ConfigCmds.VerifyNotPaired, names=['alpha', 'beta']),
)

config_scenario_arg_list = [config_scenario_0,
                            config_scenario_1,
                            config_scenario_2,
                            config_scenario_3,
                            config_scenario_4,
                            config_scenario_5]


@pytest.fixture(params=config_scenario_arg_list)  # type: ignore
def config_scenario_arg(request: Any) -> tuple[ConfigCmd]:
    """Using different scenarios.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return request.param


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
# random_seed_arg
###############################################################################
random_seed_arg_list = [1]


@pytest.fixture(params=random_seed_arg_list)  # type: ignore
def random_seed_arg(request: Any) -> int:
    """Using different random seeds.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return request.param


###############################################################################
# num_threads_arg
###############################################################################
num_threads_arg_list = [1, 2, 3, 4, 5, 6, 7, 8]


@pytest.fixture(params=num_threads_arg_list)  # type: ignore
def num_threads_arg(request: Any) -> int:
    """Number of threads to create.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return request.param


###############################################################################
# recv_msg_after_join_arg
###############################################################################
recv_msg_after_join_arg_list = [1, 2, 3]


@pytest.fixture(params=recv_msg_after_join_arg_list)  # type: ignore
def recv_msg_after_join_arg(request: Any) -> int:
    """Which threads should exit before alpha recvs msg.

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


########################################################################
# TestSmartThreadLogMsgs class
########################################################################
@dataclass
class ThreadTracker:
    """Class that tracks each thread."""
    thread: st.SmartThread
    is_alive: bool
    exiting: bool
    is_auto_started: bool
    status: st.ThreadStatus
    thread_repr: str
    # expected_last_reg_updates: deque


@dataclass
class ThreadPairStatus:
    """Class that keeps pair status."""
    pending_ops_count: int
    # expected_last_reg_updates: deque


class ConfigVerifier:
    """Class that tracks and verifies the SmartThread configuration."""

    def __init__(self,
                 log_ver: LogVer,
                 msgs: Msgs) -> None:
        """Initialize the ConfigVerifier.

        Args:
            log_ver: the log verifier to track and verify log msgs
        """
        self.specified_args = locals()  # used for __repr__, see below
        self.expected_registered: dict[str, ThreadTracker] = {}
        self.expected_pairs: dict[tuple[str, str],
                                  dict[str, ThreadPairStatus]] = {}
        self.log_ver = log_ver
        self.msgs = msgs
        self.ops_lock = threading.Lock()
        self.alpha_thread: st.SmartThread = self.create_alpha_thread()
        self.f1_threads: dict[str, st.SmartThread] = {}
        self.f1_thread_names: dict[str, bool] = {
            'beta': True,
            'charlie': True,
            'delta': True,
            'echo': True,
            'fox': True,
            'george': True,
            'henry': True,
            'ida': True}

    def __repr__(self) -> str:
        """Return a representation of the class.

        Returns:
            The representation as how the class is instantiated

        """
        if TYPE_CHECKING:
            __class__: Type[ConfigVerifier]
        classname = self.__class__.__name__
        parms = ""
        comma = ''

        for key, item in self.specified_args.items():
            if item:  # if not None
                if key in ('log_ver',):
                    if type(item) is str:
                        parms += comma + f"{key}='{item}'"
                    else:
                        parms += comma + f"{key}={item}"
                    comma = ', '  # after first item, now need comma

        return f'{classname}({parms})'

    def verify_is_alive(self, names: list[str]) -> bool:
        """Verify that the given names are alive.

        Args:
            names: names of the threads to check for being alive

        """
        for name in names:
            if not st.SmartThread._registry[name].thread.is_alive():
                return False
            if not self.expected_registered[name].is_alive:
                return False
        return True

    def verify_is_not_alive(self, names: list[str]) -> bool:
        """Verify that the given names are not alive.

        Args:
            names: names of the threads to check for being not alive

        """
        for name in names:
            if st.SmartThread._registry[name].thread.is_alive():
                return False
            if self.expected_registered[name].is_alive:
                return False
        return True

    def verify_status(self, names: list[str],
                      expected_status: st.ThreadStatus) -> bool:
        """Verify that the given names have the given status.

        Args:
            names: names of the threads to check for the given status
            expected_status: the status each thread is expected to have

        """
        for name in names:
            if not st.SmartThread._registry[name].status == expected_status:
                return False
            if not self.expected_registered[name].status == expected_status:
                return False
        return True

    def verify_registered(self, names: list[str]) -> bool:
        """Verify that the given names are registered.

        Args:
            names: names of the threads to check for being registered

        """
        for name in names:
            if name not in st.SmartThread._registry:
                return False
            if name not in self.expected_registered:
                return False
        return True

    def verify_not_registered(self, names: list[str]) -> bool:
        """Verify that the given names are not registered.

        Args:
            names: names of the threads to check for being unregistered

        """
        for name in names:
            if name in st.SmartThread._registry:
                return False
            if name in self.expected_registered:
                return False
        return True

    def verify_paired(self, names: list[str]) -> bool:
        """Verify that the given names are paired.

        Args:
            names: names of the threads to check for being paired

        """
        pair_keys = combinations(sorted(names), 2)
        for pair_key in pair_keys:
            if pair_key not in st.SmartThread._pair_array:
                return False
            if pair_key[0] not in st.SmartThread._pair_array[
                pair_key].status_blocks:
                return False
            if pair_key[1] not in st.SmartThread._pair_array[
                pair_key].status_blocks:
                return False

            if pair_key not in self.expected_pairs:
                return False
            if pair_key[0] not in self.expected_pairs[pair_key]:
                return False
            if pair_key[1] not in self.expected_pairs[pair_key]:
                return False
        return True

    def verify_half_paired(self, names: list[str],
                           half_paired_names: list[str]) -> bool:
        """Verify that the given names are half paired.

        Args:
            names: names of the threads to check for being half paired
            half_paired_names: the names that should be in pair array
        """
        pair_keys = combinations(sorted(names), 2)
        for pair_key in pair_keys:
            if pair_key not in st.SmartThread._pair_array:
                return False
            if len(st.SmartThread._pair_array[
                    pair_key].status_blocks) != 1:
                return False
            for name in half_paired_names:
                if (name in pair_key
                        and name not in st.SmartThread._pair_array[
                            pair_key].status_blocks):
                    return False

            if pair_key not in self.expected_pairs:
                return False
            if len(self.expected_pairs[pair_key]) != 1:
                return False
            for name in half_paired_names:
                if (name in pair_key
                        and name not in self.expected_pairs[pair_key]):
                    return False
        return True

    def verify_not_paired(self, names: list[str]) -> bool:
        """Verify that the given names are not paired.

        Args:
            names: names of the threads to check for being not paired

        """
        pair_keys = combinations(sorted(names), 2)
        for pair_key in pair_keys:
            if pair_key in st.SmartThread._pair_array:
                return False

            if pair_key in self.expected_pairs:
                return False

        return True

    def get_is_alive(self, name: str) -> bool:
        """Get the is_alive flag for the named thread.

        Args:
            name: names of thread to get the is_alive flag

        """
        if self.expected_registered[name].exiting:
            return self.expected_registered[name].thread.thread.is_alive()
        else:
            return self.expected_registered[name].is_alive

    def create_alpha_thread(self) -> st.SmartThread:
        """Create the alpha thread."""

        alpha_thread = st.SmartThread(name='alpha')
        self.add_thread(
            name='alpha',
            thread=alpha_thread,
            thread_alive=True,
            auto_start=False,
            expected_status=st.ThreadStatus.Alive,
            thread_repr=repr(alpha_thread),
            reg_update_time=alpha_thread.time_last_registry_update[-1],
            pair_array_update_time=alpha_thread.time_last_pair_array_update[-1]
        )
        return alpha_thread

    def create_f1_thread(self,
                         target: Callable,
                         name: Optional[str] = None,
                         auto_start: bool = True
                         ) -> st.SmartThread:
        """Create the f1_thread.

        Args:
            target: the f1 routine that the thread will run
            name: name of the thread
            auto_start: indicates whether the create should start the
                          thread
        """
        if name is None:
            for thread_name, available in self.f1_thread_names.items():
                if available:
                    name = thread_name
                    self.f1_thread_names[name] = False
                    break
        self.f1_threads[name] = st.SmartThread(name=name,
                                               target=target,
                                               args=(name, self),
                                               auto_start=auto_start)
        if auto_start:
            exp_status = st.ThreadStatus.Alive
        else:
            exp_status = st.ThreadStatus.Registered
        self.add_thread(
            name=name,
            thread=self.f1_threads[name],
            thread_alive=auto_start,
            auto_start=auto_start,
            expected_status=exp_status,
            thread_repr=repr(self.f1_threads[name]),
            reg_update_time=self.f1_threads[
                name].time_last_registry_update[-1],
            pair_array_update_time=self.f1_threads[
                name].time_last_pair_array_update[-1]
        )

    def start_thread(self,
                     name: str) -> None:
        """Start the named thread.

        Args:
            name: name of the thread to start
        """
        self.f1_threads[name].start()
        self.expected_registered[name].is_alive = True
        self.expected_registered[name].status = st.ThreadStatus.Alive
        self.add_log_msg(
            f'{name} set status for thread {name} '
            'from ThreadStatus.Registered to ThreadStatus.Starting')
        self.add_log_msg(
            f'{name} set status for thread {name} '
            f'from ThreadStatus.Starting to ThreadStatus.Alive')
        self.add_log_msg(re.escape(
            f'{name} thread started, thread.is_alive() = True, '
            'status: ThreadStatus.Alive'))

    def add_thread(self,
                   name: str,
                   thread: st.SmartThread,
                   thread_alive: bool,
                   auto_start: bool,
                   expected_status: st.ThreadStatus,
                   thread_repr: str,
                   reg_update_time: datetime,
                   pair_array_update_time: datetime
                   ) -> None:
        """Add a thread to the ConfigVerifier.

        Args:
            name: name to add
            thread: the SmartThread to add
            thread_alive: the expeccted is_alive flag
            auto_start: indicates whther to start the thread
            expected_status: the expected ThreadStatus
            thread_repr: the string to be used in any log msgs
            reg_update_time: the register update time to use for the log
                               msg
            pair_array_update_time: the pair array update time to use
                                      for the log msg
        """

        self.expected_registered[name] = ThreadTracker(
            thread=thread,
            is_alive=thread_alive,
            exiting=False,
            is_auto_started=auto_start,
            status=expected_status,
            thread_repr=thread_repr
        )
        if len(self.expected_registered) > 1:
            pair_keys = combinations(
                sorted(self.expected_registered.keys()), 2)
            for pair_key in pair_keys:
                if name not in pair_key:
                    continue
                if pair_key not in self.expected_pairs:
                    self.expected_pairs[pair_key] = {
                        pair_key[0]: ThreadPairStatus(pending_ops_count=0),
                        pair_key[1]: ThreadPairStatus(pending_ops_count=0)}
                    self.add_log_msg(re.escape(
                        f"{name} created "
                        "_refresh_pair_array with "
                        f"pair_key = {pair_key}"))

                    for pair_name in pair_key:
                        self.add_log_msg(re.escape(
                            f"{name} added status_blocks entry "
                            f"for pair_key = {pair_key}, "
                            f"name = {pair_name}"))

                # if pair_key already exists, we need to add name
                # as a resurrected thread
                else:  # we already have a pair_key, need to add name
                    if not self.expected_pairs[pair_key]:
                        raise InvalidConfigurationDetected(
                            'Attempt to add thread to existing pair array '
                            'that has an empty ThreadPairStatus dict')
                    if name in self.expected_pairs[pair_key].keys():
                        raise InvalidConfigurationDetected(
                            'Attempt to add thread to pair array that already '
                            'has the thread in the pair array')
                    if name == pair_key[0]:
                        other_name = pair_key[1]
                    else:
                        other_name = pair_key[0]
                    if other_name not in self.expected_pairs[pair_key].keys():
                        raise InvalidConfigurationDetected(
                            'Attempt to add thread to pair array that did '
                            'not have the other name in the pair array')
                    # looks OK, just add in the new name
                    self.expected_pairs[pair_key][
                        name] = ThreadPairStatus(pending_ops_count=0)
                    self.add_log_msg(re.escape(
                        f"{name} added status_blocks entry "
                        f"for pair_key = {pair_key}, "
                        f"name = {name}"))

        ################################################################
        # add log msgs
        ################################################################
        self.add_log_msg(
            f'{name} set status for thread {name} '
            'from undefined to ThreadStatus.Initializing')

        self.add_log_msg(
            f'{name} obtained _registry_lock, '
            'class name = SmartThread')

        for a_name, tracker in self.expected_registered.items():
            # ignore the new thread for now - we are in reg cleanup just
            # before we add the new thread
            if a_name == name:
                continue
            self.add_log_msg(re.escape(
                f"key = {a_name}, item = {tracker.thread_repr}, "
                f"item.thread.is_alive() = {self.get_is_alive(a_name)}, "
                f"status: {tracker.status}"))

        self.add_log_msg(
            f'{name} set status for thread {name} '
            'from ThreadStatus.Initializing to ThreadStatus.Registered')

        self.add_log_msg(f'{name} entered _refresh_pair_array')

        self.add_log_msg(re.escape(
            f'{name} updated _pair_array at UTC '
            f'{pair_array_update_time.strftime("%H:%M:%S.%f")}'))

        self.add_log_msg(
            f'{name} did register update at UTC '
            f'{reg_update_time.strftime("%H:%M:%S.%f")}')

        if self.expected_registered[name].is_auto_started:
            self.add_log_msg(
                f'{name} set status for thread {name} '
                'from ThreadStatus.Registered to ThreadStatus.Starting')

            self.add_log_msg(
                f'{name} set status for thread {name} '
                f'from ThreadStatus.Starting to ThreadStatus.Alive')

            self.add_log_msg(re.escape(
                f'{name} thread started, '
                'thread.is_alive() = True, '
                'status: ThreadStatus.Alive'))
        else:
            if self.expected_registered[name].is_alive:
                self.add_log_msg(
                    f'{name} set status for thread {name} '
                    f'from ThreadStatus.Registered to ThreadStatus.Alive')

    def del_thread(self,
                   name: str,
                   remotes: list[str],
                   reg_update_times: deque,
                   pair_array_update_times: deque
                   ) -> None:
        """Delete the thread from the ConfigVerifier.

        Args:
            name: name of thread doing the delete (for log msg)
            remotes: names of threads to be deleted
            reg_update_times: register updte times to use for the log
                                msgs
            pair_array_update_times: pair array update times to use for
                                       the log msgs
        """
        reg_update_times.rotate(len(remotes))
        pair_array_update_times.rotate(len(remotes))
        for remote in remotes:
            self.expected_registered[remote].is_alive = False
            self.expected_registered[remote].status = st.ThreadStatus.Stopped
            self.add_log_msg(
                f'{name} set status for thread '
                f'{remote} '
                f'from {st.ThreadStatus.Alive} to '
                f'{st.ThreadStatus.Stopped}')

            for thread_name, tracker in self.expected_registered.items():
                self.add_log_msg(re.escape(
                    f"key = {thread_name}, item = {tracker.thread_repr}, "
                    "item.thread.is_alive() = "
                    f"{self.get_is_alive(thread_name)}, "
                    f"status: {tracker.status}"))

            del self.expected_registered[remote]
            self.add_log_msg(f'{remote} removed from registry')

            self.add_log_msg(f'{name} entered _refresh_pair_array')

            pair_keys_to_delete = []
            for pair_key in self.expected_pairs:
                if remote not in pair_key:
                    continue
                if remote == pair_key[0]:
                    other_name = pair_key[1]
                else:
                    other_name = pair_key[0]

                if remote not in self.expected_pairs[pair_key].keys():
                    raise InvalidConfigurationDetected(
                        f'The expected_pairs for pair_key {pair_key} '
                        'contains an entry of '
                        f'{self.expected_pairs[pair_key]}  which does not '
                        f'include the remote {remote} being deleted')
                if other_name not in self.expected_pairs[pair_key].keys():
                    pair_keys_to_delete.append(pair_key)
                elif self.expected_pairs[pair_key][
                        other_name].pending_ops_count == 0:
                    pair_keys_to_delete.append(pair_key)
                    self.add_log_msg(re.escape(
                        f"{name} removed status_blocks entry "
                        f"for pair_key = {pair_key}, "
                        f"name = {other_name}"))
                else:
                    del self.expected_pairs[pair_key][remote]
                self.add_log_msg(re.escape(
                    f"{name} removed status_blocks entry "
                    f"for pair_key = {pair_key}, "
                    f"name = {remote}"))

            for pair_key in pair_keys_to_delete:
                del self.expected_pairs[pair_key]
                self.add_log_msg(re.escape(
                    f'{name} removed _pair_array entry'
                    f' for pair_key = {pair_key}'))

            self.add_log_msg(re.escape(
                f'{name} updated _pair_array at UTC '
                f'{pair_array_update_times.popleft().strftime("%H:%M:%S.%f")}')
            )

            self.add_log_msg(re.escape(
                f"{name} did cleanup of registry at UTC "
                f'{reg_update_times.popleft().strftime("%H:%M:%S.%f")}, '
                f"deleted ['{remote}']"))

            self.add_log_msg(f'{name} did successful join of {remote}.')

    def inc_ops_count(self, targets: list[str], pair_with: str):
        """Increment the pending operations count.

        Args:
            targets: the names of the threads whose count is to be
                       incremented
            pair_with: the names of the threads that are paired with
                         the targets
        """
        with self.ops_lock:
            for target in targets:
                pair_key = st.SmartThread._get_pair_key(target, pair_with)
                self.expected_pairs[pair_key][target].pending_ops_count += 1

    def dec_ops_count(self,
                      target: str,
                      remote: str,
                      pair_array_update_times: deque):
        """Decrement the pending operations count.

        Args:
            target: the names of the thread whose count is to be
                      decremented
            remote: the name of the threads that is paired with
                         the target
            pair_array_update_times: pair array update times to be used
                                       for the log msgs
        """
        with self.ops_lock:
            pair_key = st.SmartThread._get_pair_key(target, remote)
            self.expected_pairs[pair_key][target].pending_ops_count -= 1
            if self.expected_pairs[pair_key][target].pending_ops_count < 0:
                raise InvalidConfigurationDetected(
                    f'dec_ops_count for for pair_key {pair_key}, '
                    f'name {target} was decremented below zero')
            if (self.expected_pairs[pair_key][target].pending_ops_count == 0
                    and remote not in self.expected_pairs[pair_key].keys()):
                del self.expected_pairs[pair_key]
                self.add_log_msg(f'{target} entered _refresh_pair_array')
                self.add_log_msg(re.escape(
                    f"{target} removed status_blocks entry "
                    f"for pair_key = {pair_key}, "
                    f"name = {target}"))
                self.add_log_msg(re.escape(
                    f'{target} removed _pair_array entry'
                    f' for pair_key = {pair_key}'))
                self.add_log_msg(re.escape(
                    f'{target} updated _pair_array at UTC '
                    f'{pair_array_update_times.pop().strftime("%H:%M:%S.%f")}'))

    def set_is_alive(self, target: str, value: bool, exiting: bool):
        """Set the is_alive flag and exiting flag.

        Args:
            target: the thread to set the flags for
            value: the True or False value for is_alive flag
            exiting: the Tru or False value for the exiting flag

        """
        with self.ops_lock:
            self.expected_registered[target].is_alive = value
            self.expected_registered[
                target].exiting = exiting

    def validate_config(self):
        """Validate that the SmartThread config is correct."""
        # verify real registry matches expected_registered
        for name, thread in st.SmartThread._registry.items():
            if name not in self.expected_registered:
                raise InvalidConfigurationDetected(
                    f'SmartThread registry has entry for name {name} '
                    f'that is missing from the expected_registry ')
            if (self.expected_registered[name].is_alive
                    != thread.thread.is_alive()):
                raise InvalidConfigurationDetected(
                    f'SmartThread registry has entry for name {name} '
                    f'that has is_alive of {thread.thread.is_alive()} '
                    f'which does not match the expected_registered '
                    f'is_alive of {self.expected_registered[name].is_alive}')
            if (self.expected_registered[name].status
                    != thread.status):
                raise InvalidConfigurationDetected(
                    f'SmartThread registry has entry for name {name} '
                    f'that has satus of {thread.status} '
                    f'which does not match the expected_registered '
                    f'status of {self.expected_registered[name].status}')

        # verify expected_registered matches real registry
        for name, tracker in self.expected_registered.items():
            if name not in st.SmartThread._registry:
                raise InvalidConfigurationDetected(
                    f'ConfigVerifier expected_registered has '
                    f'entry for name {name} '
                    f'that is missing from SmartThread._registry')

        # verify pair_array matches expected_pairs
        for pair_key in st.SmartThread._pair_array.keys():
            if pair_key not in self.expected_pairs:
                raise InvalidConfigurationDetected(
                    f'ConfigVerifier found pair_key {pair_key}'
                    f'in SmartThread._pair_array that is '
                    f'not found in expected_pairs: ')
            for name in st.SmartThread._pair_array[
                pair_key].status_blocks.keys():
                if name not in self.expected_pairs[pair_key].keys():
                    raise InvalidConfigurationDetected(
                        f'ConfigVerifier found name {name} in '
                        f'SmartThread._pair_array status_blocks for pair_key'
                        f' {pair_key}, but is missing in expected_pairs: ')
                if name not in self.expected_registered:
                    raise InvalidConfigurationDetected(
                        f'ConfigVerifier found name {name} in '
                        f'SmartThread._pair_array status_blocks for pair_key'
                        f' {pair_key}, but is missing in '
                        f'expected_registered: ')
                if len(self.expected_pairs[pair_key]) == 1:
                    if self.expected_pairs[pair_key][
                            name].pending_ops_count == 0:
                        raise InvalidConfigurationDetected(
                            f'ConfigVerifier found name {name} in '
                            f'SmartThread._pair_array status_blocks for '
                            f'pair_key {pair_key}, but it is a single name '
                            f'that has a pending_ops_count of zero')

                if (self.expected_pairs[pair_key][
                    name].pending_ops_count == 0
                        and not st.SmartThread._pair_array[
                            pair_key].status_blocks[name].msg_q.empty()):
                    raise InvalidConfigurationDetected(
                        f'ConfigVerifier found name {name} in '
                        'expected_pairs for '
                        f'pair_key  {pair_key}, and it has a '
                        'pending_ops_count of zero, but the '
                        'SmartThread._pair_array entry show the msg_q '
                        'is not empty')
                if (self.expected_pairs[pair_key][
                    name].pending_ops_count != 0
                        and st.SmartThread._pair_array[
                            pair_key].status_blocks[name].msg_q.empty()):
                    raise InvalidConfigurationDetected(
                        f'ConfigVerifier found name {name} in '
                        'expected_pairs for '
                        f'pair_key  {pair_key}, and it has a '
                        'pending_ops_count of non-zero, but the '
                        'SmartThread._pair_array entry show the msg_q '
                        'is empty')
        # verify expected_pairs matches pair_array
        for pair_key in self.expected_pairs:
            if pair_key not in st.SmartThread._pair_array:
                raise InvalidConfigurationDetected(
                    f'ConfigVerifier found pair_key {pair_key} in '
                    'expected_pairs but not in SmartThread._pair_array')
            for name in self.expected_pairs[pair_key].keys():
                if name not in st.SmartThread._pair_array[
                        pair_key].status_blocks:
                    raise InvalidConfigurationDetected(
                        f'ConfigVerifier found name {name} in '
                        f'expected_pairs for pair_key {pair_key}, but not in '
                        'SmartThread._pair_array status_blocks')

    def add_log_msg(self,
                    new_log_msg: str,
                    log_level: Optional[int] = logging.DEBUG) -> None:
        """Add log message to log_ver for SmartThread logger.

        Args:
            new_log_msg: msg to add to log_ver
            log_level: the logging severity level to use
        """
        self.log_ver.add_msg(
            log_name='scottbrian_paratools.smart_thread',
            log_level=log_level,
            log_msg=new_log_msg)


################################################################
# outer_f1
################################################################
def outer_f1(f1_name: str, f1_config_ver: ConfigVerifier):
    log_msg_f1 = f'outer_f1 entered for {f1_name}'
    f1_config_ver.log_ver.add_msg(log_msg=log_msg_f1)
    logger.debug(log_msg_f1)

    f1_driver(f1_name=f1_name, f1_config_ver=f1_config_ver)

    ############################################################
    # exit
    ############################################################
    log_msg_f1 = f'outer_f1 exiting for {f1_name}'
    f1_config_ver.log_ver.add_msg(log_msg=log_msg_f1)
    logger.debug(log_msg_f1)


################################################################
# f1_driver
################################################################
def f1_driver(f1_name: str, f1_config_ver: ConfigVerifier):

    while True:

        cmd_msg = f1_config_ver.msgs.get_msg(f1_name)

        if cmd_msg.cmd == ConfigCmds.Exit:
            break

        if cmd_msg.cmd == ConfigCmds.SendMsg:
            ####################################################
            # send one or more msgs
            ####################################################
            f1_config_ver.inc_ops_count(cmd_msg.to_names,
                                        f1_name)
            f1_config_ver.f1_threads[f1_name].send_msg(
                targets=cmd_msg.to_names,
                msg=cmd_msg)

            for f1_to_name in cmd_msg.to_names:
                log_msg_f1 = (f'{f1_name} sending message to '
                              f'{f1_to_name}')
                f1_config_ver.log_ver.add_msg(
                    log_name='scottbrian_paratools.smart_thread',
                    log_level=logging.INFO,
                    log_msg=log_msg_f1)

            f1_config_ver.msgs.queue_msg(
                'alpha', f'send done from {f1_name}')
        elif cmd_msg.cmd == ConfigCmds.RecvMsg:
            ####################################################
            # recv one or more msgs
            ####################################################
            for f1_from_name in cmd_msg.from_names:
                f1_config_ver.f1_threads[f1_name].recv_msg(
                    remote=f1_from_name,
                    timeout=3)

                f1_copy_pair_deque = (
                    f1_config_ver.f1_threads[f1_name]
                    .time_last_pair_array_update.copy())
                f1_config_ver.dec_ops_count(f1_name,
                                         f1_from_name,
                                         f1_copy_pair_deque)

                log_msg_f1 = (f"{f1_name} receiving msg from "
                              f"{f1_from_name}")
                f1_config_ver.log_ver.add_msg(
                    log_name='scottbrian_paratools.smart_thread',
                    log_level=logging.INFO,
                    log_msg=log_msg_f1)
            f1_config_ver.msgs.queue_msg(
                'alpha', f'recv done for {f1_name}')
        else:
            raise UnrecognizedCmd(
                f'The cmd_msg.cmd {cmd_msg.cmd} '
                'is not recognized')


########################################################################
# TestSmartThreadScenarios class
########################################################################
class TestSmartThreadScenarios:
    """Test class for SmartThread scenarios."""

    ####################################################################
    # test_smart_thread_scenarios
    ####################################################################
    def test_smart_thread_scenarios(
            self,
            config_scenario_arg: list[ConfigCmd],
            #f1_create_arg: int,
            caplog: pytest.CaptureFixture[str]
    ) -> None:
        """Test configuration scenarios.

        Args:
            config_scenario_arg: fixture for scenario to perform
            caplog: pytest fixture to capture log output

        """

        ################################################################
        # f1
        ################################################################
        def f1(f1_name: str, f1_config_ver: ConfigVerifier):
            log_msg_f1 = f'f1 entered for {f1_name}'
            log_ver.add_msg(log_level=logging.DEBUG,
                            log_msg=log_msg_f1)
            logger.debug(log_msg_f1)

            f1_driver(f1_name=f1_name, f1_config_ver=f1_config_ver)

            ############################################################
            # exit
            ############################################################
            log_msg_f1 = f'f1 exiting for {f1_name}'
            log_ver.add_msg(log_level=logging.DEBUG,
                            log_msg=log_msg_f1)
            logger.debug(log_msg_f1)

        ################################################################
        # Set up log verification and start tests
        ################################################################
        log_ver = LogVer(log_name=__name__)
        log_ver.add_call_seq(name='alpha',
                             seq=get_formatted_call_sequence())

        log_msg = 'mainline entered'
        log_ver.add_msg(log_msg=log_msg)
        logger.debug(log_msg)

        # log_msg = f'random_seed_arg: {random_seed_arg}'
        # log_ver.add_msg(log_msg=log_msg)
        # logger.debug(log_msg)

        msgs = Msgs()

        config_ver = ConfigVerifier(log_ver=log_ver,
                                    msgs=msgs)

        # random.seed(random_seed_arg)

        # num_threads_arg = 1  # random.randint(2, 3)

        # log_msg = f'num_threads: {num_threads_arg}'
        # log_ver.add_msg(log_msg=log_msg)
        # logger.debug(log_msg)
        num_f1_threads = 0
        for config_cmd in config_scenario_arg:
            log_msg = f'config_cmd: {config_cmd}'
            log_ver.add_msg(log_msg=re.escape(log_msg))
            logger.debug(log_msg)

            ############################################################
            # CreateMainThread
            ############################################################
            # if config_cmd.cmd == ConfigCmds.CreateMainThread:
            #     for new_name in config_cmd.names:
            #         config_ver.create_f1_thread(
            #             target=f1,
            #             name=new_name,
            #             auto_start=config_cmd.auto_start
            #         )
            ############################################################
            # CreateF1Thread
            ############################################################
            if config_cmd.cmd == ConfigCmds.Create:
                num_f1_threads += 1
                for new_name in config_cmd.names:
                    config_ver.create_f1_thread(
                        target=outer_f1,
                        name=new_name,
                        auto_start=config_cmd.auto_start
                    )
            elif config_cmd.cmd == ConfigCmds.Start:
                for name in config_cmd.names:
                    config_ver.start_thread(name=name)
            elif config_cmd.cmd == ConfigCmds.VerifyAlive:
                assert config_ver.verify_is_alive(config_cmd.names)

            elif config_cmd.cmd == ConfigCmds.VerifyNotAlive:
                assert config_ver.verify_is_not_alive(config_cmd.names)

            elif config_cmd.cmd == ConfigCmds.VerifyStatus:
                assert config_ver.verify_status(
                    names=config_cmd.names,
                    expected_status=config_cmd.exp_status)

            elif config_cmd.cmd == ConfigCmds.SendMsg:
                pending_responses = []
                for from_name in config_cmd.from_names:
                    pending_responses.append(
                        f'send done from {from_name}')
                    config_ver.msgs.queue_msg(target=from_name,
                                              msg=config_cmd)
                while pending_responses:
                    a_msg = config_ver.msgs.get_msg('alpha')
                    if a_msg in pending_responses:
                        pending_responses.remove(a_msg)
                    else:
                        raise UnrecognizedCmd(
                            f'A response of {a_msg} for the SendMsg is '
                            f'is not recognized')
                    time.sleep(0.1)

            elif config_cmd.cmd == ConfigCmds.RecvMsg:
                pending_responses = []
                for to_name in config_cmd.to_names:
                    if to_name == 'alpha':
                        continue
                    pending_responses.append(
                        f'recv done for {to_name}')
                    config_ver.msgs.queue_msg(target=to_name,
                                              msg=config_cmd)
                while pending_responses:
                    a_msg = config_ver.msgs.get_msg('alpha')
                    if a_msg in pending_responses:
                        pending_responses.remove(a_msg)
                    else:
                        raise UnrecognizedCmd(
                            f'A response of {a_msg} for the SendMsg is '
                            f'is not recognized')
                    time.sleep(0.1)

                if 'alpha' in config_cmd.to_names:
                    for from_name in config_cmd.from_names:
                        config_ver.alpha_thread.recv_msg(
                            remote=from_name,
                            timeout=3)
                        copy_pair_deque = (
                            config_ver.alpha_thread
                            .time_last_pair_array_update.copy())
                        config_ver.dec_ops_count('alpha',
                                                 from_name,
                                                 copy_pair_deque)

                        log_msg = (f"{'alpha'} receiving msg from "
                                   f"{from_name}")
                        log_ver.add_msg(
                            log_name='scottbrian_paratools.smart_thread',
                            log_level=logging.INFO,
                            log_msg=log_msg)

            elif config_cmd.cmd == ConfigCmds.Exit:
                for exit_thread_name in config_cmd.names:
                    config_ver.msgs.queue_msg(
                        target=exit_thread_name, msg=config_cmd)
                num_alive = 1
                while num_alive > 0:
                    num_alive = 0
                    for exit_thread_name in config_cmd.names:
                        if config_ver.f1_threads[
                                exit_thread_name].thread.is_alive():
                            num_alive += 1
                            time.sleep(.01)
                        else:
                            config_ver.set_is_alive(target=exit_thread_name,
                                                    value=False,
                                                    exiting=False)

            elif config_cmd.cmd == ConfigCmds.Join:
                config_ver.alpha_thread.join(targets=config_cmd.names)
                copy_reg_deque = (
                    config_ver.alpha_thread.time_last_registry_update
                    .copy())
                copy_pair_deque = (
                    config_ver.alpha_thread.time_last_pair_array_update
                    .copy())
                config_ver.del_thread(
                    name='alpha',
                    remotes=config_cmd.names,
                    reg_update_times=copy_reg_deque,
                    pair_array_update_times=copy_pair_deque)

            elif config_cmd.cmd == ConfigCmds.VerifyRegistered:
                assert config_ver.verify_registered(config_cmd.names)
            elif config_cmd.cmd == ConfigCmds.VerifyNotRegistered:
                assert config_ver.verify_not_registered(config_cmd.names)
            elif config_cmd.cmd == ConfigCmds.VerifyPaired:
                assert config_ver.verify_paired(config_cmd.names)
            elif config_cmd.cmd == ConfigCmds.VerifyHalfPaired:
                assert config_ver.verify_half_paired(
                    config_cmd.names, config_cmd.half_paired_names)
            elif config_cmd.cmd == ConfigCmds.VerifyNotPaired:
                assert config_ver.verify_not_paired(config_cmd.names)

            else:
                raise UnrecognizedCmd(f'The config_cmd.cmd {config_cmd.cmd} '
                                      'is not recognized')
            config_ver.validate_config()

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results)
        log_ver.verify_log_results(match_results)

        logger.debug('mainline exiting')

    ####################################################################
    # test_refresh_pair_array_log_msgs
    ####################################################################
    def test_smart_thread_simple_config(
            self,
            num_threads_arg: int,
            recv_msg_after_join_arg: int,
            caplog: pytest.CaptureFixture[str]
    ) -> None:
        """Test simple configuration scenarios.

        Args:
            num_threads_arg: fixture for number of threads to create
            recv_msg_after_join_arg: value used to determine how many
                                       threads are to receive the msg
                                       after the sending thread is gone
            caplog: pytest fixture to capture log output

        """

        ################################################################
        # f1
        ################################################################
        def f1(f1_name: str, f1_config_ver: ConfigVerifier):
            log_msg_f1 = f'f1 entered for {f1_name}'
            log_ver.add_msg(log_level=logging.DEBUG,
                            log_msg=log_msg_f1)
            logger.debug(log_msg_f1)

            cmd_msg = ''
            while cmd_msg != 'exit':

                cmd_msg = f1_config_ver.msgs.get_msg(f1_name)

                if cmd_msg == 'send_to_alpha':
                    ####################################################
                    # send msg to alpha
                    ####################################################
                    f1_config_ver.inc_ops_count(['alpha'], f1_name)
                    f1_config_ver.f1_threads[f1_name].send_msg(
                        targets='alpha', msg=cmd_msg)

                    log_msg_f1 = f'{f1_name} sending message to alpha'
                    log_ver.add_msg(
                        log_name='scottbrian_paratools.smart_thread',
                        log_level=logging.INFO,
                        log_msg=log_msg_f1)

            ############################################################
            # exit
            ############################################################
            log_msg_f1 = f'f1 exiting for {f1_name}'
            log_ver.add_msg(log_level=logging.DEBUG,
                            log_msg=log_msg_f1)
            logger.debug(log_msg_f1)

            f1_config_ver.set_is_alive(target=f1_name,
                                       value=False,
                                       exiting=True)

        ################################################################
        # Set up log verification and start tests
        ################################################################
        log_ver = LogVer(log_name=__name__)
        log_ver.add_call_seq(name='alpha',
                             seq=get_formatted_call_sequence())

        log_msg = 'mainline entered'
        log_ver.add_msg(log_msg=log_msg)
        logger.debug(log_msg)

        # log_msg = f'random_seed_arg: {random_seed_arg}'
        # log_ver.add_msg(log_msg=log_msg)
        # logger.debug(log_msg)

        msgs = Msgs()

        config_ver = ConfigVerifier(log_ver=log_ver,
                                    msgs=msgs)



        # random.seed(random_seed_arg)

        # num_threads_arg = 1  # random.randint(2, 3)

        log_msg = f'num_threads: {num_threads_arg}'
        log_ver.add_msg(log_msg=log_msg)
        logger.debug(log_msg)

        ################################################################
        # Create f1 threads
        ################################################################
        for thread_num in range(1, num_threads_arg):
            config_ver.create_f1_thread(target=f1)

        ################################################################
        # All creates completed, validate config
        ################################################################
        config_ver.validate_config()

        ################################################################
        # Tell f1 threads to proceed to send us a msg
        ################################################################
        for thread_name in config_ver.f1_threads.keys():
            # tell thread to proceed
            msgs.queue_msg(target=thread_name, msg='send_to_alpha')

        ################################################################
        # Recv msgs from remotes
        ################################################################
        if recv_msg_after_join_arg == 1:
            num_early_joins_to_do = 0
        elif recv_msg_after_join_arg == 2:
            num_early_joins_to_do = (num_threads_arg - 1) / 2
        else:
            num_early_joins_to_do = num_threads_arg - 1
        num_joins = 0
        joined_names = []
        for thread_name in config_ver.f1_threads.keys():
            if num_joins < num_early_joins_to_do:
                # tell thread to exit
                msgs.queue_msg(target=thread_name, msg='exit')
                config_ver.alpha_thread.join(targets=thread_name)
                copy_reg_deque = (
                    config_ver.alpha_thread.time_last_registry_update.copy())
                copy_pair_deque = (
                    config_ver.alpha_thread.time_last_pair_array_update.copy())
                config_ver.del_thread(
                    name='alpha',
                    remotes=[thread_name],
                    reg_update_times=copy_reg_deque,
                    pair_array_update_times=copy_pair_deque)
                joined_names.append(thread_name)
                num_joins += 1

            log_msg = f'mainline alpha receiving msg from {thread_name}'
            log_ver.add_msg(log_level=logging.DEBUG,
                            log_msg=log_msg)
            logger.debug(log_msg)

            config_ver.alpha_thread.recv_msg(remote=thread_name, timeout=3)
            copy_pair_deque = (
                config_ver.alpha_thread.time_last_pair_array_update.copy())
            config_ver.dec_ops_count('alpha', thread_name, copy_pair_deque)

            log_msg = f'alpha receiving msg from {thread_name}'
            log_ver.add_msg(
                log_name='scottbrian_paratools.smart_thread',
                log_level=logging.INFO,
                log_msg=log_msg)

        ################################################################
        # All msgs received, validate config
        ################################################################
        config_ver.validate_config()

        ################################################################
        # Tell f1 threads to exit
        ################################################################
        for thread_name in config_ver.f1_threads.keys():
            if thread_name in joined_names:
                continue
            msgs.queue_msg(target=thread_name, msg='exit')

        ################################################################
        # Join remotes
        ################################################################
        for thread_name in config_ver.f1_threads.keys():
            if thread_name in joined_names:
                continue
            config_ver.alpha_thread.join(targets=thread_name)
            copy_reg_deque = (
                config_ver.alpha_thread.time_last_registry_update.copy())
            copy_pair_deque = (
                config_ver.alpha_thread.time_last_pair_array_update.copy())
            config_ver.del_thread(
                name='alpha',
                remotes=[thread_name],
                reg_update_times=copy_reg_deque,
                pair_array_update_times=copy_pair_deque)

        ################################################################
        # All joins complete, validate config
        ################################################################
        config_ver.validate_config()

        ################################################################
        # verify logger messages
        ################################################################
        config_ver.validate_config()
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results)
        log_ver.verify_log_results(match_results)

        logger.debug('mainline exiting')


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
        """Test error cases for SmartThread."""
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

    ####################################################################
    # test_smart_thread_join_errors
    ####################################################################
    def test_smart_thread_join_errors(
            self,
            caplog: pytest.CaptureFixture[str]
            ) -> None:
        """Test error cases in the _regref remote array method.

        Args:
            caplog: pytest fixture to capture log output

        """
        ################################################################
        # Set up log verification and start tests
        ################################################################
        log_ver = LogVer(log_name=__name__)
        log_ver.add_call_seq(name='alpha',
                             seq=get_formatted_call_sequence())

        log_msg = 'mainline entered'
        log_ver.add_msg(log_msg=log_msg)
        logger.debug(log_msg)

        msgs = Msgs()

        config_ver = ConfigVerifier(log_ver=log_ver,
                                    msgs=msgs)

        ################################################################
        # CreateF1Thread
        ################################################################
        config_ver.create_f1_thread(target=outer_f1,
                                    name='beta',
                                    auto_start=True)

        ################################################################
        # verify the configuration
        ################################################################
        config_ver.validate_config()

        ################################################################
        # join before telling f1 to exit
        ################################################################
        exp_error = st.SmartThreadJoinTimedOut
        with pytest.raises(exp_error):
            config_ver.alpha_thread.join(targets='beta',
                                         timeout=2)

        config_ver.add_log_msg(re.escape(
            "alpha raising SmartThreadJoinTimedOut waiting "
            "for {'beta'}"),
            log_level=logging.ERROR
        )

        ################################################################
        # verify the configuration
        ################################################################
        config_ver.validate_config()

        ################################################################
        # tell beta to exit
        ################################################################
        config_cmd = ConfigCmd(cmd=ConfigCmds.Exit, names=['beta'])
        config_ver.msgs.queue_msg(
            target='beta', msg=config_cmd)

        ################################################################
        # verify the configuration
        ################################################################
        config_ver.validate_config()

        ################################################################
        # join beta - should be ok since after exit
        ################################################################
        config_ver.alpha_thread.join(targets='beta',
                                     timeout=2)
        copy_reg_deque = (
            config_ver.alpha_thread.time_last_registry_update
            .copy())
        copy_pair_deque = (
            config_ver.alpha_thread.time_last_pair_array_update
            .copy())
        config_ver.del_thread(
            name='alpha',
            remotes=config_cmd.names,
            reg_update_times=copy_reg_deque,
            pair_array_update_times=copy_pair_deque)

        ################################################################
        # verify the configuration
        ################################################################
        config_ver.validate_config()

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results)
        log_ver.verify_log_results(match_results)

        logger.debug('mainline exiting')


#
#
# class TestSmartThreadLogMsgs:
#     """Test class for SmartThread log msgs."""
#     ####################################################################
#     # test_refresh_pair_array_log_msgs
#     ####################################################################
#     def test_refresh_pair_array_log_msgs(
#             self,
#             caplog: pytest.CaptureFixture[str]
#             ) -> None:
#         """Test log msgs for _refresh_pair_array.
#
#         Args:
#             caplog: pytest fixture to capture log output
#
#         """
#         ################################################################
#         # f1
#         ################################################################
#         def f1(name: str):
#             log_msg_f1 = 'f1 entered'
#             log_ver.add_msg(log_level=logging.DEBUG,
#                             log_msg=log_msg_f1)
#             logger.debug(log_msg_f1)
#
#             msgs.get_msg('beta')
#
#             ############################################################
#             # send msg to alpha
#             ############################################################
#             beta_thread.send_msg(targets='alpha', msg='go now')
#
#             log_msg_f1 = f'beta sending message to alpha'
#             log_ver.add_msg(
#                 log_name='scottbrian_paratools.smart_thread',
#                 log_level=logging.INFO,
#                 log_msg=log_msg_f1)
#
#             # ############################################################
#             # # recv msg from alpha
#             # ############################################################
#             # msg1 = beta_thread.recv_msg(remote='alpha', timeout=3)
#             #
#             # log_msg_f1 = 'beta receiving msg from alpha'
#             # log_ver.add_msg(
#             #     log_name='scottbrian_paratools.smart_thread',
#             #     log_level=logging.INFO,
#             #     log_msg=log_msg_f1)
#             #
#             # log_msg_f1 = f'beta received msg: {msg1}'
#             # log_ver.add_msg(log_level=logging.DEBUG,
#             #                 log_msg=log_msg_f1)
#             # logger.debug(log_msg_f1)
#             #
#             # ############################################################
#             # # recv second msg from alpha
#             # ############################################################
#             # msg2 = beta_thread.recv_msg(remote='alpha', timeout=3)
#             #
#             # log_msg_f1 = 'beta receiving msg from alpha'
#             # log_ver.add_msg(
#             #     log_name='scottbrian_paratools.smart_thread',
#             #     log_level=logging.INFO,
#             #     log_msg=log_msg_f1)
#             #
#             # log_msg_f1 = f'beta received msg: {msg2}'
#             # log_ver.add_msg(log_level=logging.DEBUG,
#             #                 log_msg=log_msg_f1)
#             # logger.debug(log_msg_f1)
#             #
#             # ############################################################
#             # # recv third msg from alpha
#             # ############################################################
#             # msg3 = beta_thread.recv_msg(remote='alpha', timeout=3)
#             #
#             # log_msg_f1 = 'beta receiving msg from alpha'
#             # log_ver.add_msg(
#             #     log_name='scottbrian_paratools.smart_thread',
#             #     log_level=logging.INFO,
#             #     log_msg=log_msg_f1)
#             #
#             # log_msg_f1 = f'beta received msg: {msg3}'
#             # log_ver.add_msg(log_level=logging.DEBUG,
#             #                 log_msg=log_msg_f1)
#             # logger.debug(log_msg_f1)
#
#             ############################################################
#             # exit
#             ############################################################
#             log_msg_f1 = 'f1 exiting'
#             log_ver.add_msg(log_level=logging.DEBUG,
#                             log_msg=log_msg_f1)
#             logger.debug(log_msg_f1)
#
#         ################################################################
#         # Set up log verification and start tests
#         ################################################################
#         log_ver = LogVer(
#             log_name='test_scottbrian_paratools.test_smart_thread')
#         alpha_call_seq = (
#             'test_smart_thread.py::TestSmartThreadLogMsgs'
#             '.test_refresh_pair_array_log_msgs')
#         log_ver.add_call_seq(name='alpha',
#                              seq=alpha_call_seq)
#
#         log_msg = 'mainline entered'
#         log_ver.add_msg(log_msg=log_msg)
#         logger.debug(log_msg)
#
#         msgs = Msgs()
#
#         ################################################################
#         # Create alpha smart thread
#         ################################################################
#         log_msg = 'mainline creating alpha smart thread'
#         log_ver.add_msg(log_level=logging.DEBUG,
#                         log_msg=log_msg)
#         logger.debug(log_msg)
#
#         alpha_thread = st.SmartThread(name='alpha')
#
#         set_create_expected_log_msgs(alpha_thread, log_ver)
#
#         ################################################################
#         # Create beta smart thread
#         ################################################################
#         log_msg = 'mainline creating beta smart thread'
#         log_ver.add_msg(log_level=logging.DEBUG,
#                         log_msg=log_msg)
#         logger.debug(log_msg)
#
#         beta_thread = st.SmartThread(name='beta', target=f1, args=('beta',))
#
#         set_create_expected_log_msgs(beta_thread, log_ver, [alpha_thread])
#
#         msgs.queue_msg('beta')  # tell beta to proceed
#
#         ################################################################
#         # Start beta thread
#         ################################################################
#         # beta_thread.start()
#         #
#         # log_msg = (
#         #     'beta set status for thread beta '
#         #     'from ThreadStatus.Registered to ThreadStatus.Starting')
#         # log_ver.add_msg(
#         #     log_name='scottbrian_paratools.smart_thread',
#         #     log_level=logging.DEBUG,
#         #     log_msg=log_msg)
#         #
#         # log_msg = (
#         #     f'beta set status for thread beta '
#         #     f'from ThreadStatus.Starting to ThreadStatus.Alive')
#         # log_ver.add_msg(
#         #     log_name='scottbrian_paratools.smart_thread',
#         #     log_level=logging.DEBUG,
#         #     log_msg=log_msg)
#         #
#         # log_msg = re.escape(
#         #     'beta thread started, thread.is_alive() = True, '
#         #     'status: ThreadStatus.Alive')
#         # log_ver.add_msg(
#         #     log_name='scottbrian_paratools.smart_thread',
#         #     log_level=logging.DEBUG,
#         #     log_msg=log_msg)
#
#         ################################################################
#         # Recv msg from beta
#         ################################################################
#         time.sleep(.5)
#         log_msg = 'mainline alpha receiving msg from beta'
#         log_ver.add_msg(log_level=logging.DEBUG,
#                         log_msg=log_msg)
#         logger.debug(log_msg)
#
#         alpha_thread.recv_msg(remote='beta', timeout=3)
#
#         log_msg = f'alpha receiving msg from beta'
#         log_ver.add_msg(
#             log_name='scottbrian_paratools.smart_thread',
#             log_level=logging.INFO,
#             log_msg=log_msg)
#
#         ################################################################
#         # Join beta
#         ################################################################
#         alpha_thread.join(targets='beta')
#
#         set_join_expected_log_msgs(alpha_thread, log_ver, [beta_thread],
#                                    [alpha_thread])
#
#         # log_msg = re.escape(
#         #     "key = alpha, item = SmartThread(name='alpha'), "
#         #     "item.thread.is_alive() = True, status: ThreadStatus.Alive")
#         # log_ver.add_msg(
#         #     log_name='scottbrian_paratools.smart_thread',
#         #     log_level=logging.DEBUG,
#         #     log_msg=log_msg)
#         #
#         # log_msg = re.escape(
#         #     "key = beta, item = SmartThread(name='beta', target=f1, "
#         #     "args=('beta',)), item.thread.is_alive() = False, "
#         #     "status: ThreadStatus.Stopped")
#         # log_ver.add_msg(
#         #     log_name='scottbrian_paratools.smart_thread',
#         #     log_level=logging.DEBUG,
#         #     log_msg=log_msg)
#         #
#         # log_msg = 'beta removed from registry'
#         # log_ver.add_msg(
#         #     log_name='scottbrian_paratools.smart_thread',
#         #     log_level=logging.DEBUG,
#         #     log_msg=log_msg)
#         #
#         # log_msg = 'alpha entered _refresh_pair_array'
#         # log_ver.add_msg(
#         #     log_name='scottbrian_paratools.smart_thread',
#         #     log_level=logging.DEBUG,
#         #     log_msg=log_msg)
#         #
#         # log_msg = re.escape(
#         #     "alpha removed status_blocks entry "
#         #     "for pair_key = ('alpha', 'beta'), name = beta")
#         # log_ver.add_msg(
#         #     log_name='scottbrian_paratools.smart_thread',
#         #     log_level=logging.DEBUG,
#         #     log_msg=log_msg)
#         #
#         # update_time_f1 = (alpha_thread.time_last_pair_array_update
#         #                   .strftime("%H:%M:%S.%f"))
#         # log_msg = re.escape(
#         #     'alpha updated _pair_array at UTC '
#         #     f'{update_time_f1}')
#         # log_ver.add_msg(
#         #     log_name='scottbrian_paratools.smart_thread',
#         #     log_level=logging.DEBUG,
#         #     log_msg=log_msg)
#         #
#         # log_msg = re.escape(
#         #     "alpha did cleanup of registry at UTC "
#         #     f'{st.SmartThread._registry_last_update.strftime("%H:%M:%S.%f")}, '
#         #     "deleted ['beta']")
#         # log_ver.add_msg(
#         #     log_name='scottbrian_paratools.smart_thread',
#         #     log_level=logging.DEBUG,
#         #     log_msg=log_msg)
#         #
#         # log_msg = 'alpha did successful join of beta.'
#         # log_ver.add_msg(
#         #     log_name='scottbrian_paratools.smart_thread',
#         #     log_level=logging.DEBUG,
#         #     log_msg=log_msg)
#
#         ################################################################
#         # verify logger messages
#         ################################################################
#         time.sleep(1)
#         match_results = log_ver.get_match_results(caplog=caplog)
#         log_ver.print_match_results(match_results)
#         log_ver.verify_log_results(match_results)
#
#         logger.debug('mainline exiting')
#
# ########################################################################
# # TestSmartThreadBasic class
# ########################################################################
# class TestSmartThreadBasic:
#     """Test class for SmartThread basic tests."""
#     ####################################################################
#     # Basic Scenario1
#     ####################################################################
#     def test_smart_thread_with_msg_mixin1(self):
#
#         ################################################################
#         # f1
#         ################################################################
#         def f1():
#             logger.debug('f1 entered')
#
#             msgs.get_msg('beta')
#
#
#             # beta_smart_thread.wait(remote='alpha', log_msg='f1 wait 1')
#             # beta_smart_thread.sync(targets='alpha', log_msg='f1 sync 2')
#             beta_smart_thread.send_msg(msg='hi alpha, this is beta',
#                                        targets='alpha',
#                                        log_msg='f1 send_msg 3')
#             assert beta_smart_thread.recv_msg(remote='alpha',
#                                               log_msg='f1 recv_msg 4',
#                                               timeout=3) == (
#                                                   'hi beta, this is alpha')
#             # beta_smart_thread.resume(targets='alpha', log_msg='f1 resume 5')
#             msgs.queue_msg('alpha')
#             logger.debug('f1 exiting')
#
#         ####################################################################
#         # Create smart threads for the main thread (this thread) and f1
#         ####################################################################
#         logger.debug('mainline entered')
#         logger.debug('mainline creating alpha thread')
#
#         alpha_smart_thread = st.SmartThread(name='alpha')
#
#         logger.debug('mainline creating beta thread')
#
#         msgs = Msgs()
#
#         beta_smart_thread = st.SmartThread(name='beta', target=f1)
#         beta_smart_thread.start()
#
#         ####################################################################
#         # Interact with beta
#         ####################################################################
#         logger.debug('mainline interacting with beta')
#
#         msgs.queue_msg('beta')  # tell beta to proceed
#
#         # alpha_smart_thread.resume(targets='beta', log_msg='ml resume 1')
#         # alpha_smart_thread.sync(targets='beta', log_msg='ml sync 2')
#         assert alpha_smart_thread.recv_msg(remote='beta',
#                                            log_msg='ml recv_msg 3',
#                                            timeout=3) == (
#                                                'hi alpha, this is beta')
#         alpha_smart_thread.send_msg(msg='hi beta, this is alpha', targets='beta', log_msg='ml send_msg 4')
#         # alpha_smart_thread.wait(remote='beta', log_msg='f1 resume 5')
#         # # alpha_smart_thread.join(targets='beta', log_msg='ml join 6')
#         msgs.get_msg('alpha')  # wait for beta to tell us to proceed
#         beta_smart_thread.thread.join()
#
#         assert not beta_smart_thread.thread.is_alive()
#
#         logger.debug('mainline exiting')
#     ####################################################################
#     # Basic Scenario1
#     ####################################################################
#     def test_smart_thread_basic_scenario1(self):
#
#         ################################################################
#         # f1
#         ################################################################
#         def f1():
#             logger.debug('f1 entered')
#
#             msgs.get_msg('beta')
#             msgs.queue_msg('alpha')
#
#             # beta_smart_thread.wait(remote='alpha', log_msg='f1 wait 1')
#             # beta_smart_thread.sync(targets='alpha', log_msg='f1 sync 2')
#             # beta_smart_thread.send_msg(msg='hi alpha, this is beta', targets='alpha', log_msg='f1 send_msg 3')
#             # assert beta_smart_thread.recv_msg(remote='alpha', log_msg='f1 recv_msg 4') == 'hi beta, this is alpha'
#             # beta_smart_thread.resume(targets='alpha', log_msg='f1 resume 5')
#
#             logger.debug('f1 exiting')
#
#         ####################################################################
#         # Create smart threads for the main thread (this thread) and f1
#         ####################################################################
#         logger.debug('mainline entered')
#         logger.debug('mainline creating alpha thread')
#         alpha_smart_thread = st.SmartThread(name='alpha')
#
#         logger.debug('mainline creating beta thread')
#
#         msgs = Msgs()
#
#         beta_smart_thread = st.SmartThread(name='beta', target=f1)
#         beta_smart_thread.start()
#
#         ####################################################################
#         # Interact with beta
#         ####################################################################
#         logger.debug('mainline interacting with beta')
#
#         msgs.queue_msg('beta')
#         msgs.get_msg('alpha')
#         # alpha_smart_thread.resume(targets='beta', log_msg='ml resume 1')
#         # alpha_smart_thread.sync(targets='beta', log_msg='ml sync 2')
#         # assert alpha_smart_thread.recv_msg(remote='beta', log_msg='ml recv_msg 3') == 'hi alpha, this is beta'
#         # alpha_smart_thread.send_msg(msg='hi beta, this is alpha', targets='beta', log_msg='ml send_msg 4')
#         # alpha_smart_thread.wait(remote='beta', log_msg='f1 resume 5')
#         # # alpha_smart_thread.join(targets='beta', log_msg='ml join 6')
#
#         beta_smart_thread.thread.join()
#
#         assert not beta_smart_thread.thread.is_alive()
#
#         logger.debug('mainline exiting')
#
#     ####################################################################################################################
#     # Basic Scenario2
#     ####################################################################################################################
#     def test_smart_thread_basic_scenario2(self):
#         ####################################################################
#         # f1
#         ####################################################################
#         def f1():
#             logger.debug('f1 entered')
#             logger.debug(f'SmartThread._registry = {st.SmartThread._registry}')
#             beta_smart_thread.wait(remote='alpha', log_msg='f1 wait 1')
#             beta_smart_thread.sync(targets='alpha', log_msg='f1 sync 2')
#             beta_smart_thread.send_msg(msg='hi alpha, this is beta', targets='alpha', log_msg='f1 send_msg 3')
#             assert beta_smart_thread.recv_msg(remote='alpha', log_msg='f1 recv_msg 4') == 'hi beta, this is alpha'
#             beta_smart_thread.resume(targets='alpha', log_msg='f1 resume 5')
#
#             beta_smart_thread.wait(remote='charlie', log_msg='f1 wait 6')
#             beta_smart_thread.sync(targets='charlie', log_msg='f1 sync 7')
#             beta_smart_thread.send_msg(msg='hi charlie, this is beta', targets='charlie', log_msg='f1 send_msg 8')
#             assert beta_smart_thread.recv_msg(remote='charlie', log_msg='f1 recv_msg 9') == 'hi beta, this is charlie'
#             beta_smart_thread.resume(targets='charlie', log_msg='f1 resume 10')
#
#             logger.debug('f1 exiting')
#
#         ####################################################################
#         # f2
#         ####################################################################
#         def f2():
#             logger.debug('f2 entered')
#
#             charlie_smart_thread.wait(remote='alpha', log_msg='f2 wait 1')
#             charlie_smart_thread.sync(targets='alpha', log_msg='f2 sync 2')
#             charlie_smart_thread.send_msg(msg='hi alpha, this is charlie', targets='alpha', log_msg='f2 send_msg 3')
#             assert charlie_smart_thread.recv_msg(remote='alpha', log_msg='f2 recv_msg 4') == 'hi charlie, this is alpha'
#             charlie_smart_thread.resume(targets='alpha', log_msg='f2 resume 5')
#
#             charlie_smart_thread.resume(targets='beta', log_msg='f2 resume 6')
#             charlie_smart_thread.sync(targets='beta', log_msg='f2 sync 7')
#             assert charlie_smart_thread.recv_msg(remote='beta', log_msg='f2 recv_msg 9') == 'hi charlie, this is beta'
#             charlie_smart_thread.send_msg(msg='hi beta, this is charlie', targets='beta', log_msg='f2 send_msg 8')
#             charlie_smart_thread.wait(remote='beta', log_msg='f2 wait 10')
#
#             logger.debug('f2 exiting')
#
#         ####################################################################
#         # Create smart threads for the main thread (this thread), f1, and f2
#         ####################################################################
#         logger.debug('mainline entered')
#         logger.debug('mainline creating alpha thread')
#         alpha_smart_thread = st.SmartThread(name='alpha')
#
#         logger.debug('mainline creating beta thread')
#         # beta_thread = threading.Thread(name='beta', target=f1)
#         beta_smart_thread = st.SmartThread(name='beta', target=f1)
#         beta_smart_thread.thread.start()
#         logger.debug('mainline creating charlie thread')
#         # charlie_thread = threading.Thread(name='charlie', target=f2)
#         charlie_smart_thread = st.SmartThread(name='charlie', target=f2)
#         charlie_smart_thread.thread.start()
#
#         ####################################################################
#         # Interact with beta and charlie
#         ####################################################################
#         logger.debug('mainline interacting with beta')
#         alpha_smart_thread.resume(targets='beta', log_msg='ml resume 1')
#         alpha_smart_thread.sync(targets='beta', log_msg='ml sync 2')
#         assert alpha_smart_thread.recv_msg(remote='beta', log_msg='ml recv_msg 3') == 'hi alpha, this is beta'
#         alpha_smart_thread.send_msg(msg='hi beta, this is alpha', targets='beta', log_msg='ml send_msg 4')
#         alpha_smart_thread.wait(remote='beta', log_msg='f1 resume 5')
#
#         logger.debug('mainline interacting with charlie')
#         alpha_smart_thread.resume(targets='charlie', log_msg='ml resume 6')
#         alpha_smart_thread.sync(targets='charlie', log_msg='ml sync 7')
#         assert alpha_smart_thread.recv_msg(remote='charlie', log_msg='ml recv_msg 8') == 'hi alpha, this is charlie'
#         alpha_smart_thread.send_msg(msg='hi charlie, this is alpha', targets='charlie', log_msg='ml send_msg 9')
#         alpha_smart_thread.wait(remote='charlie', log_msg='f1 resume 10')
#
#         alpha_smart_thread.join(targets='beta', log_msg='ml join 11')
#         alpha_smart_thread.join(targets='charlie', log_msg='ml join 12')
#
#         logger.debug('mainline exiting')
#
#     ####################################################################################################################
#     # Basic Scenario3
#     ####################################################################################################################
#     def test_smart_thread_basic_scenario3(self):
#         ####################################################################
#         # f1
#         ####################################################################
#         def f1():
#             logger.debug('f1 entered')
#
#             beta_smart_thread.wait(remote='alpha', log_msg='f1 wait 1')
#             beta_smart_thread.sync(targets='alpha', log_msg='f1 sync 2')
#             beta_smart_thread.send_msg(msg='hi alpha, this is beta', targets='alpha', log_msg='f1 send_msg 3')
#             assert beta_smart_thread.recv_msg(remote='alpha', log_msg='f1 recv_msg 4') == 'hi beta, this is alpha'
#             beta_smart_thread.resume(targets='alpha', log_msg='f1 resume 5')
#
#             beta_smart_thread.wait(remote='charlie', log_msg='f1 wait 6')
#             beta_smart_thread.sync(targets='charlie', log_msg='f1 sync 7')
#             beta_smart_thread.send_msg(msg='hi charlie, this is beta', targets='charlie', log_msg='f1 send_msg 8')
#             assert beta_smart_thread.recv_msg(remote='charlie', log_msg='f1 recv_msg 9') == 'hi beta, this is charlie'
#             beta_smart_thread.resume(targets='charlie', log_msg='f1 resume 10')
#
#             logger.debug('f1 exiting')
#
#         ####################################################################
#         # f2
#         ####################################################################
#         def f2():
#             logger.debug('f2 entered')
#
#             charlie_smart_thread.wait(remote='alpha', log_msg='f2 wait 1')
#             charlie_smart_thread.sync(targets='alpha', log_msg='f2 sync 2')
#             charlie_smart_thread.send_msg(msg='hi alpha, this is charlie', targets='alpha', log_msg='f2 send_msg 3')
#             assert charlie_smart_thread.recv_msg(remote='alpha', log_msg='f2 recv_msg 4') == 'hi charlie, this is alpha'
#             charlie_smart_thread.resume(targets='alpha', log_msg='f2 resume 5')
#
#             charlie_smart_thread.resume(targets='beta', log_msg='f2 resume 6')
#             charlie_smart_thread.sync(targets='beta', log_msg='f2 sync 7')
#             assert charlie_smart_thread.recv_msg(remote='beta', log_msg='f2 recv_msg 9') == 'hi charlie, this is beta'
#             charlie_smart_thread.send_msg(msg='hi beta, this is charlie', targets='beta', log_msg='f2 send_msg 8')
#             charlie_smart_thread.wait(remote='beta', log_msg='f2 wait 10')
#
#             logger.debug('f2 exiting')
#
#         ####################################################################
#         # Create smart threads for the main thread (this thread), f1, and f2
#         ####################################################################
#         logger.debug('mainline entered')
#         logger.debug('mainline creating alpha thread')
#         alpha_smart_thread = st.SmartThread(name='alpha', default_timeout=10)
#
#         logger.debug('mainline creating beta thread')
#         beta_smart_thread = st.SmartThread(name='beta', target=f1)
#         beta_smart_thread.thread.start()
#         logger.debug('mainline creating charlie thread')
#         charlie_smart_thread = st.SmartThread(name='charlie', target=f2)
#         charlie_smart_thread.thread.start()
#
#         ####################################################################
#         # Interact with beta and charlie
#         ####################################################################
#         logger.debug('mainline interacting with beta and charlie')
#         alpha_smart_thread.resume(targets='beta', log_msg='ml resume 1')
#         alpha_smart_thread.resume(targets='charlie', log_msg='ml resume 2')
#         alpha_smart_thread.sync(targets='beta', log_msg='ml sync 3')
#         alpha_smart_thread.sync(targets='charlie', log_msg='ml sync 4')
#         assert alpha_smart_thread.recv_msg(remote='beta', log_msg='ml recv_msg 5') == 'hi alpha, this is beta'
#         assert alpha_smart_thread.recv_msg(remote='charlie', log_msg='ml recv_msg 6') == 'hi alpha, this is charlie'
#         alpha_smart_thread.send_msg(msg='hi beta, this is alpha', targets='beta', log_msg='ml send_msg 7')
#         alpha_smart_thread.send_msg(msg='hi charlie, this is alpha', targets='charlie', log_msg='ml send_msg 8')
#         alpha_smart_thread.wait(remote='beta', log_msg='f1 resume 9')
#         alpha_smart_thread.wait(remote='charlie', log_msg='f1 resume 10')
#
#         alpha_smart_thread.join(targets='beta', log_msg='ml join 11')
#         alpha_smart_thread.join(targets='charlie', log_msg='ml join 12')
#
#         logger.debug('mainline exiting')
#
#     ####################################################################################################################
#     # Basic Scenario4
#     ####################################################################################################################
#     def test_smart_thread_basic_scenario4(self):
#         ####################################################################
#         # f1
#         ####################################################################
#         def f1():
#             logger.debug('f1 entered')
#
#             beta_smart_thread.wait(remote='alpha', log_msg='f1 wait 1')
#             beta_smart_thread.sync(targets={'alpha', 'charlie'}, log_msg='f1 sync 2')
#             beta_smart_thread.send_msg(msg='hi alpha and charlie, this is beta', targets={'alpha', 'charlie'},
#                                        log_msg='f1 send_msg 3')
#             assert beta_smart_thread.recv_msg(remote='alpha', log_msg='f1 recv_msg 4') == 'hi beta and charlie, this is alpha'
#             assert beta_smart_thread.recv_msg(remote='charlie',
#                                         log_msg='f1 recv_msg 5') == 'hi alpha and beta, this is charlie'
#             beta_smart_thread.resume(targets={'alpha', 'charlie'}, log_msg='f1 resume 6')
#             beta_smart_thread.wait(remote='charlie', log_msg='f1 wait 7')
#
#             logger.debug('f1 exiting')
#
#         ####################################################################
#         # f2
#         ####################################################################
#         def f2():
#             logger.debug('f2 entered')
#
#             charlie_smart_thread.wait(remote='alpha', log_msg='f2 wait 1')
#             charlie_smart_thread.sync(targets={'alpha', 'beta'}, log_msg='f2 sync 2')
#             charlie_smart_thread.send_msg(msg='hi alpha and beta, this is charlie', targets={'alpha', 'beta'},
#                                           log_msg='f2 send_msg 3')
#             assert charlie_smart_thread.recv_msg(remote='alpha',
#                                            log_msg='f2 recv_msg 4') == 'hi beta and charlie, this is alpha'
#             assert charlie_smart_thread.recv_msg(remote='beta',
#                                            log_msg='f2 recv_msg 5') == 'hi alpha and charlie, this is beta'
#             charlie_smart_thread.wait(remote='beta', log_msg='f2 wait 6')
#             charlie_smart_thread.resume(targets={'alpha', 'beta'}, log_msg='f2 resume 7')
#
#             logger.debug('f2 exiting')
#
#         ####################################################################
#         # Create smart threads for the main thread (this thread), f1, and f2
#         ####################################################################
#         logger.debug('mainline entered')
#         logger.debug('mainline creating alpha thread')
#         alpha_smart_thread = st.SmartThread(name='alpha', default_timeout=10)
#
#         logger.debug('mainline creating beta thread')
#         beta_thread = threading.Thread(name='beta', target=f1)
#         beta_smart_thread = st.SmartThread(name='beta', thread=beta_thread, default_timeout=10)
#         beta_thread.start()
#         logger.debug('mainline creating charlie thread')
#         charlie_thread = threading.Thread(name='charlie', target=f2)
#         charlie_smart_thread = st.SmartThread(name='charlie', thread=charlie_thread, default_timeout=10)
#         charlie_thread.start()
#
#         ####################################################################
#         # Interact with beta and charlie
#         ####################################################################
#         logger.debug('mainline interacting with beta and charlie')
#
#         alpha_smart_thread.resume(targets={'beta', 'charlie'}, log_msg='ml resume 1')
#         alpha_smart_thread.sync(targets={'beta', 'charlie'}, log_msg='ml sync 2')
#         assert alpha_smart_thread.recv_msg(remote='beta', log_msg='ml recv_msg 3') == 'hi alpha and charlie, this is beta'
#         assert alpha_smart_thread.recv_msg(remote='charlie', log_msg='ml recv_msg 4') == 'hi alpha and beta, this is charlie'
#         alpha_smart_thread.send_msg(msg='hi beta and charlie, this is alpha', targets={'beta', 'charlie'},
#                                     log_msg='ml send_msg 5')
#         alpha_smart_thread.wait(remote='beta', log_msg='ml resume 6')
#         alpha_smart_thread.wait(remote='charlie', log_msg='ml resume 7')
#
#         alpha_smart_thread.join(targets={'beta', 'charlie'}, log_msg='ml join 8')
#
#         logger.debug('mainline exiting')
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
