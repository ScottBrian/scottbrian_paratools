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
import math
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


class InvalidInputDetected(ErrorTstSmartThread):
    """The input is not correct."""
    pass


###############################################################################
# Config Scenarios
###############################################################################
class ConfigCmds(Enum):
    CreateCommanderNoStart = auto()
    CreateCommanderAutoStart = auto()
    CreateNoStart = auto()
    CreateAutoStart = auto()
    Start = auto()
    Unregister = auto()
    SendMsg = auto()
    SendMsgTimeoutTrue = auto()
    SendMsgTimeoutFalse = auto()
    RecvMsg = auto()
    RecvMsgTimeoutTrue = auto()
    RecvMsgTimeoutFalse = auto()
    Join = auto()
    Pause = auto()
    ConfirmResponse = auto()
    ValidateConfig = auto()
    VerifyCounts = auto()
    VerifyRegistered = auto()
    VerifyNotRegistered = auto()
    VerifyPaired = auto()
    VerifyHalfPaired = auto()
    VerifyNotPaired = auto()
    VerifyAlive = auto()
    VerifyNotAlive = auto()
    VerifyActive = auto()
    VerifyStopped = auto()
    VerifyStatus = auto()
    WaitForMsgTimeouts = auto()
    Exit = auto()


@dataclass
class ConfigCmd:
    cmd: ConfigCmds
    names: Optional[list[str]] = None
    commander_name: Optional[str] = None
    auto_start: bool = True
    from_names: Optional[list[str]] = None
    to_names: Optional[list[str]] = None
    msg_to_send: Optional[Any] = None
    log_msg: Optional[str] = None
    unreg_timeout_names: Optional[list[str]] = None
    fullq_timeout_names: Optional[list[str]] = None
    exp_status: Optional[st.ThreadStatus] = None
    half_paired_names: Optional[list[str]] = None
    pause_seconds: Optional[float] = None
    timeout: Optional[float] = None
    confirm_response: Optional[bool] = False
    confirm_response_cmd: Optional[ConfigCmds] = None
    num_registered: Optional[int] = None
    num_active: Optional[int] = None
    num_stopped: Optional[int] = None


########################################################################
# timeout_type used to specify whether to use timeout on various cmds
########################################################################
class TimeoutType(Enum):
    TimeoutNone = auto()
    TimeoutFalse = auto()
    TimeoutTrue = auto()


########################################################################
# RecvMsgParms used to specify the args for testing recv_msg
########################################################################
@dataclass
class RecvMsgParms:
    timeout_type: TimeoutType
    num_active_senders: int
    num_send_exit_senders: int
    num_nosend_exit_senders: int
    num_unreg_senders: int
    num_reg_senders: int
    num_receivers: int
    caplog_to_use: pytest.CaptureFixture[str]

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
    ConfigCmd(cmd=ConfigCmds.CreateAutoStart, names=['beta', 'charlie']),

    ConfigCmd(cmd=ConfigCmds.VerifyRegistered,
              names=['alpha', 'beta', 'charlie']),
    ConfigCmd(cmd=ConfigCmds.VerifyPaired, names=['alpha', 'beta', 'charlie']),
    ConfigCmd(cmd=ConfigCmds.VerifyAlive, names=['alpha', 'beta', 'charlie']),
    ConfigCmd(cmd=ConfigCmds.VerifyStatus, names=['alpha', 'beta', 'charlie'],
              exp_status=st.ThreadStatus.Alive),

    # 1) beta and charlie send msg to alpha
    ConfigCmd(cmd=ConfigCmds.SendMsg, names=['beta', 'charlie'],
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
              names=['alpha']),

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
    ConfigCmd(cmd=ConfigCmds.CreateAutoStart, names=['beta']),

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
    ConfigCmd(cmd=ConfigCmds.CreateAutoStart, names=['beta']),

    # 4) verify alpha and beta are paired
    ConfigCmd(cmd=ConfigCmds.VerifyRegistered,
              names=['alpha', 'beta']),
    ConfigCmd(cmd=ConfigCmds.VerifyPaired, names=['alpha', 'beta']),
    ConfigCmd(cmd=ConfigCmds.VerifyAlive, names=['alpha', 'beta']),
    ConfigCmd(cmd=ConfigCmds.VerifyStatus, names=['alpha', 'beta'],
              exp_status=st.ThreadStatus.Alive),


    # 5) beta send msg to alpha
    ConfigCmd(cmd=ConfigCmds.SendMsg, names=['beta'],
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
    ConfigCmd(cmd=ConfigCmds.CreateAutoStart, names=['beta']),

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
              names=['alpha']),

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
    ConfigCmd(cmd=ConfigCmds.CreateAutoStart, names=['beta', 'charlie']),
    ConfigCmd(cmd=ConfigCmds.VerifyRegistered,
              names=['alpha', 'beta', 'charlie']),
    ConfigCmd(cmd=ConfigCmds.VerifyPaired, names=['alpha', 'beta', 'charlie']),
    ConfigCmd(cmd=ConfigCmds.VerifyAlive, names=['alpha', 'beta', 'charlie']),
    ConfigCmd(cmd=ConfigCmds.VerifyStatus, names=['alpha', 'beta', 'charlie'],
              exp_status=st.ThreadStatus.Alive),

    # 1) charlie send msg to beta
    ConfigCmd(cmd=ConfigCmds.SendMsg, names=['charlie'],
              to_names=['beta']),

    # 2) beta recv msg from charlie
    ConfigCmd(cmd=ConfigCmds.RecvMsg, from_names=['charlie'],
              names=['beta']),

    # 3) charlie send msg to beta
    ConfigCmd(cmd=ConfigCmds.SendMsg, names=['charlie'],
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
              names=['beta']),

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
    ConfigCmd(cmd=ConfigCmds.CreateAutoStart, names=['beta']),

    # 1) verify alpha and beta are paired
    ConfigCmd(cmd=ConfigCmds.VerifyRegistered,
              names=['alpha', 'beta']),
    ConfigCmd(cmd=ConfigCmds.VerifyPaired, names=['alpha', 'beta']),
    ConfigCmd(cmd=ConfigCmds.VerifyAlive, names=['alpha', 'beta']),
    ConfigCmd(cmd=ConfigCmds.VerifyStatus, names=['alpha', 'beta'],
              exp_status=st.ThreadStatus.Alive),

    # 2) beta send first msg to alpha
    ConfigCmd(cmd=ConfigCmds.SendMsg, names=['beta'],
              to_names=['alpha']),

    # 3) beta send second msg to alpha
    ConfigCmd(cmd=ConfigCmds.SendMsg, names=['beta'],
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
              names=['alpha']),

    # 8) verify alpha still half paired with beta
    ConfigCmd(cmd=ConfigCmds.VerifyNotRegistered, names=['beta']),
    ConfigCmd(cmd=ConfigCmds.VerifyRegistered, names=['alpha']),
    ConfigCmd(cmd=ConfigCmds.VerifyHalfPaired,
              names=['alpha', 'beta'], half_paired_names=['alpha']),

    # 9) alpha recv second msg from beta
    ConfigCmd(cmd=ConfigCmds.RecvMsg, from_names=['beta'],
              names=['alpha']),

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
    ConfigCmd(cmd=ConfigCmds.CreateNoStart, names=['beta'],
              auto_start=False),

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
    ConfigCmd(cmd=ConfigCmds.SendMsg, names=['beta'],
              to_names=['alpha']),

    # 3) alpha recv msg
    ConfigCmd(cmd=ConfigCmds.RecvMsg, from_names=['beta'],
              names=['alpha']),

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

config_scenario_arg_list = [config_scenario_1,
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
random_seed_arg_list = [1, 2, 3]


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
num_threads_arg_list = [3, 8, 16]


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
# build_config_arg
###############################################################################
build_config_arg_list = [
    (0, 1, 0), (0, 1, 1), (0, 1, 2), (0, 1, 3), (0, 1, 4),
    (0, 2, 0), (0, 2, 1), (0, 2, 2), (0, 2, 3), (0, 2, 4),
    (0, 3, 0), (0, 3, 1), (0, 3, 2), (0, 3, 3), (0, 3, 4),
    (0, 4, 0), (0, 4, 1), (0, 4, 2), (0, 4, 3), (0, 4, 4),
    (1, 1, 0), (1, 1, 1), (1, 1, 2), (1, 1, 3), (1, 1, 4),
    (1, 2, 0), (1, 2, 1), (1, 2, 2), (1, 2, 3), (1, 2, 4),
    (1, 3, 0), (1, 3, 1), (1, 3, 2), (1, 3, 3), (1, 3, 4),
    (1, 4, 0), (1, 4, 1), (1, 4, 2), (1, 4, 3), (1, 4, 4),
    (2, 1, 0), (2, 1, 1), (2, 1, 2), (2, 1, 3), (2, 1, 4),
    (2, 2, 0), (2, 2, 1), (2, 2, 2), (2, 2, 3), (2, 2, 4),
    (2, 3, 0), (2, 3, 1), (2, 3, 2), (2, 3, 3), (2, 3, 4),
    (2, 4, 0), (2, 4, 1), (2, 4, 2), (2, 4, 3), (2, 4, 4),
    (3, 1, 0), (3, 1, 1), (3, 1, 2), (3, 1, 3), (3, 1, 4),
    (3, 2, 0), (3, 2, 1), (3, 2, 2), (3, 2, 3), (3, 2, 4),
    (3, 3, 0), (3, 3, 1), (3, 3, 2), (3, 3, 3), (3, 3, 4),
    (3, 4, 0), (3, 4, 1), (3, 4, 2), (3, 4, 3), (3, 4, 4),
    (4, 1, 0), (4, 1, 1), (4, 1, 2), (4, 1, 3), (4, 1, 4),
    (4, 2, 0), (4, 2, 1), (4, 2, 2), (4, 2, 3), (4, 2, 4),
    (4, 3, 0), (4, 3, 1), (4, 3, 2), (4, 3, 3), (4, 3, 4),
    (4, 4, 0), (4, 4, 1), (4, 4, 2), (4, 4, 3), (4, 4, 4),
]

# build_config_arg_list = [
#     (0, 1, 0),
#     (1, 1, 0),
# ]


@pytest.fixture(params=build_config_arg_list)  # type: ignore
def build_config_arg(request: Any) -> tuple[int, int, int]:
    """Number of registered, active, and stopped threads to create.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(tuple[int, int, int], request.param)


###############################################################################
# build_config2_arg
###############################################################################


@pytest.fixture(params=build_config_arg_list)  # type: ignore
def build_config2_arg(request: Any) -> tuple[int, int, int]:
    """Number of registered, active, and stopped threads to create.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(tuple[int, int, int], request.param)


###############################################################################
# timeout_type_arg
###############################################################################
timeout_type_arg_list = [TimeoutType.TimeoutNone,
                         TimeoutType.TimeoutFalse,
                         TimeoutType.TimeoutTrue]


@pytest.fixture(params=timeout_type_arg_list)  # type: ignore
def timeout_type_arg(request: Any) -> TimeoutType:
    """Type of send_msg timeout to test.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(TimeoutType, request.param)


###############################################################################
# num_senders_arg
###############################################################################
num_senders_arg_list = [1, 2, 3]
# num_senders_arg_list = [2]


@pytest.fixture(params=num_senders_arg_list)  # type: ignore
def num_senders_arg(request: Any) -> int:
    """Number of threads to send msg.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


###############################################################################
# num_active_senders_arg
###############################################################################
num_active_senders_arg_list = [0, 1, 2]
num_active_senders_arg_list = [1]


@pytest.fixture(params=num_active_senders_arg_list)  # type: ignore
def num_active_senders_arg(request: Any) -> int:
    """Number of threads to send msg.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


###############################################################################
# num_senders_exit_before_arg
###############################################################################
num_send_exit_senders_arg_list = [0, 1, 2]


@pytest.fixture(params=num_send_exit_senders_arg_list)  # type: ignore
def num_send_exit_senders_arg(request: Any) -> int:
    """Number of threads to send msg and then exit.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


###############################################################################
# num_senders_exit_before_arg
###############################################################################
num_nosend_exit_senders_arg_list = [0, 1, 2]


@pytest.fixture(params=num_nosend_exit_senders_arg_list)  # type: ignore
def num_nosend_exit_senders_arg(request: Any) -> int:
    """Number of threads to exit and send msg after create (resurrect).

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


###############################################################################
# num_unreg_senders_arg
###############################################################################
num_unreg_senders_arg_list = [0, 1, 2]


@pytest.fixture(params=num_unreg_senders_arg_list)  # type: ignore
def num_unreg_senders_arg(request: Any) -> int:
    """Number of threads to be unregistered and send msg after create.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


###############################################################################
# num_reg_senders_arg
###############################################################################
num_reg_senders_arg_list = [0, 1, 2]


@pytest.fixture(params=num_reg_senders_arg_list)  # type: ignore
def num_reg_senders_arg(request: Any) -> int:
    """Number of threads to be registered and send msg after start.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


###############################################################################
# num_receivers_arg
###############################################################################
num_receivers_arg_list = [1, 2, 3]


@pytest.fixture(params=num_receivers_arg_list)  # type: ignore
def num_receivers_arg(request: Any) -> int:
    """Number of threads to receive msgs.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


###############################################################################
# num_active_targets_arg
###############################################################################
num_active_targets_arg_list = [0, 1, 2]
# num_active_targets_arg_list = [1]


@pytest.fixture(params=num_active_targets_arg_list)  # type: ignore
def num_active_targets_arg(request: Any) -> int:
    """Number of threads to be active at time of send.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


###############################################################################
# num_registered_targets_arg
###############################################################################
num_registered_targets_arg_list = [0, 1, 2]
# num_registered_targets_arg_list = [0]


@pytest.fixture(params=num_registered_targets_arg_list)  # type: ignore
def num_registered_targets_arg(request: Any) -> int:
    """Number of threads to be registered at time of send.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


########################################################################
# num_timeouts_arg
# send_msg: (unreg, exit, fullq)
# recv_msg: (unreg, exit, reg)
# note that we need at least 1, so no (0, 0, 0)
########################################################################
num_timeouts_arg_list = [(0, 0, 1), (0, 0, 2), (0, 0, 3),
                         (0, 1, 0), (0, 1, 1), (0, 1, 2), (0, 1, 3),
                         (0, 2, 0), (0, 2, 1), (0, 2, 2), (0, 2, 3),
                         (0, 3, 0), (0, 3, 1), (0, 3, 2), (0, 3, 3),
                         (1, 0, 0), (1, 0, 1), (1, 0, 2), (1, 0, 3),
                         (1, 1, 0), (1, 1, 1), (1, 1, 2), (1, 1, 3),
                         (1, 2, 0), (1, 2, 1), (1, 2, 2), (1, 2, 3),
                         (1, 3, 0), (1, 3, 1), (1, 3, 2), (1, 3, 3),
                         (2, 0, 0), (2, 0, 1), (2, 0, 2), (2, 0, 3),
                         (2, 1, 0), (2, 1, 1), (2, 1, 2), (2, 1, 3),
                         (2, 2, 0), (2, 2, 1), (2, 2, 2), (2, 2, 3),
                         (2, 3, 0), (2, 3, 1), (2, 3, 2), (2, 3, 3),
                         (3, 0, 0), (3, 0, 1), (3, 0, 2), (3, 0, 3),
                         (3, 1, 0), (3, 1, 1), (3, 1, 2), (3, 1, 3),
                         (3, 2, 0), (3, 2, 1), (3, 2, 2), (3, 2, 3),
                         (3, 3, 0), (3, 3, 1), (3, 3, 2), (3, 3, 3)]

# num_timeouts_arg_list = [(0, 2, 0)]
@pytest.fixture(params=num_timeouts_arg_list)  # type: ignore
def num_timeouts_arg(request: Any) -> tuple[int, int, int]:
    """Number of threads to timeout by unreg, exit, or fullq.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(tuple[int, int, int], request.param)


########################################################################
# num_exit_timeouts_arg
########################################################################
num_exit_timeouts_arg_list = [0, 1, 2, 3]


@pytest.fixture(params=num_exit_timeouts_arg_list)  # type: ignore
def num_exit_timeouts_arg(request: Any) -> int:
    """Number of threads to exit before msg is sent.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


########################################################################
# num_unreg_timeouts_arg
########################################################################
num_unreg_timeouts_arg_list = [1, 2, 3]


@pytest.fixture(params=num_unreg_timeouts_arg_list)  # type: ignore
def num_unreg_timeouts_arg(request: Any) -> int:
    """Number of threads to be unregistered at time of send.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


########################################################################
# num_full_q_timeouts_arg
########################################################################
num_full_q_timeouts_arg_list = [0, 1, 2, 3]


@pytest.fixture(params=num_full_q_timeouts_arg_list)  # type: ignore
def num_full_q_timeouts_arg(request: Any) -> int:
    """Number of threads to have full queue at time of send.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


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
                 commander_name: str,
                 log_ver: LogVer,
                 msgs: Msgs,
                 max_msgs: Optional[int] = 10) -> None:
        """Initialize the ConfigVerifier.

        Args:
            log_ver: the log verifier to track and verify log msgs
        """
        self.specified_args = locals()  # used for __repr__, see below
        self.commander_name = commander_name
        self.commander_thread_config_built = False
        self.thread_names: list[str] = [
            'alpha', 'beta', 'charlie', 'delta',
            'echo', 'fox', 'george', 'henry',
            'ida', 'jack', 'king', 'love',
            'mary', 'nancy', 'oscar', 'peter',
            'queen', 'roger', 'sam', 'tom',
            'uncle', 'victor', 'wanda', 'xander'
        ]
        self.unregistered_names: set[str] = set(self.thread_names)
        # self.unregistered_names.remove(commander_name)
        self.registered_names: set[str] = set()
        self.active_names: set[str] = set()
        self.stopped_names: set[str] = set()
        self.expected_registered: dict[str, ThreadTracker] = {}
        self.expected_pairs: dict[tuple[str, str],
                                  dict[str, ThreadPairStatus]] = {}
        self.log_ver = log_ver
        self.msgs = msgs
        self.ops_lock = threading.Lock()
        self.commander_thread: st.SmartThread = None
        self.f1_threads: dict[str, st.SmartThread] = {}
        self.created_names: list[str] = []
        self.max_msgs = max_msgs

        self.pending_ops_counts: dict[tuple[str, str], dict[str, int]] = {}
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

    def create_commander_thread(self,
                                name: str,
                                auto_start: bool) -> None:
        """Create the commander thread."""

        self.commander_thread = st.SmartThread(
            name=name, auto_start=auto_start, max_msgs=self.max_msgs)
        self.add_thread(
            name=name,
            thread=self.commander_thread,
            thread_alive=True,
            auto_start=False,
            expected_status=st.ThreadStatus.Alive,
            thread_repr=repr(self.commander_thread),
            reg_update_time=self.commander_thread
            .time_last_registry_update[-1],
            pair_array_update_time=self.commander_thread
            .time_last_pair_array_update[-1]
        )

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
                                               auto_start=auto_start,
                                               max_msgs=self.max_msgs)
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
        # assert {name}.issubset(self.stopped_names)
        # self.stopped_names -= {name}
        # self.active_names |= {name}
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

    def unregister_thread(self, names: list[str]) -> None:
        """Unregister the named thread.

        Args:
            names: names of threads to be unregistered
        """
        self.commander_thread.unregister(targets=set(names))
        copy_reg_deque = (
            self.commander_thread.time_last_registry_update.copy())
        copy_pair_deque = (
            self.commander_thread.time_last_pair_array_update.copy())
        copy_unreg_names = self.commander_thread.unregister_names.copy()
        self.del_thread(
            name=self.commander_name,
            remotes=names,
            reg_update_times=copy_reg_deque,
            pair_array_update_times=copy_pair_deque,
            process_names=copy_unreg_names,
            process='unregister'
        )

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
            thread_alive: the expected is_alive flag
            auto_start: indicates whether to start the thread
            expected_status: the expected ThreadStatus
            thread_repr: the string to be used in any log msgs
            reg_update_time: the register update time to use for the log
                               msg
            pair_array_update_time: the pair array update time to use
                                      for the log msg
        """
        # self.unregistered_names -= {name}
        # if auto_start:
        #     self.active_names |= {name}
        # else:
        #     self.stopped_names |= {name}

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
                if name == pair_key[0]:
                    other_name = pair_key[1]
                else:
                    other_name = pair_key[0]
                name_poc = 0
                other_poc = 0
                if pair_key in self.pending_ops_counts:
                    if name in self.pending_ops_counts[pair_key]:
                        name_poc = self.pending_ops_counts[pair_key][name]
                        self.pending_ops_counts[pair_key][name] = 0
                    if other_name in self.pending_ops_counts[pair_key]:
                        other_poc = self.pending_ops_counts[pair_key][
                            other_name]
                        self.pending_ops_counts[pair_key][other_name] = 0

                if pair_key not in self.expected_pairs:
                    self.expected_pairs[pair_key] = {
                        name: ThreadPairStatus(pending_ops_count=name_poc),
                        other_name: ThreadPairStatus(
                            pending_ops_count=other_poc)}
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
                        self.abort_all_f1_threads()
                        raise InvalidConfigurationDetected(
                            'Attempt to add thread to existing pair array '
                            'that has an empty ThreadPairStatus dict')
                    if name in self.expected_pairs[pair_key].keys():
                        self.abort_all_f1_threads()
                        raise InvalidConfigurationDetected(
                            'Attempt to add thread to pair array that already '
                            'has the thread in the pair array')
                    if name == pair_key[0]:
                        other_name = pair_key[1]
                    else:
                        other_name = pair_key[0]
                    if other_name not in self.expected_pairs[pair_key].keys():
                        self.abort_all_f1_threads()
                        raise InvalidConfigurationDetected(
                            'Attempt to add thread to pair array that did '
                            'not have the other name in the pair array')
                    # looks OK, just add in the new name
                    self.expected_pairs[pair_key][
                        name] = ThreadPairStatus(pending_ops_count=name_poc)
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
                   pair_array_update_times: deque,
                   process_names: deque,
                   process: str  # join or unregister
                   ) -> None:
        """Delete the thread from the ConfigVerifier.

        Args:
            name: name of thread doing the delete (for log msg)
            remotes: names of threads to be deleted
            reg_update_times: register update times to use for the log
                                msgs
            pair_array_update_times: pair array update times to use for
                                       the log msgs
            process_names: deque of names unreged or joined, in order
            process: names the process, either join or unregister
        """
        reg_update_times.rotate(len(remotes))
        pair_array_update_times.rotate(len(remotes))
        process_names.rotate(len(remotes))
        if process == 'join':
            from_status = st.ThreadStatus.Alive
        else:
            from_status = st.ThreadStatus.Registered
        for idx in range(len(remotes)):
            remote = process_names.popleft()
            self.expected_registered[remote].is_alive = False
            self.expected_registered[remote].status = st.ThreadStatus.Stopped
            self.add_log_msg(
                f'{name} set status for thread '
                f'{remote} '
                f'from {from_status} to '
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
                    self.abort_all_f1_threads()
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

            self.add_log_msg(f'{name} did successful {process} of {remote}.')

    def abort_all_f1_threads(self):
        for name, thread in self.f1_threads.items():
            self.add_log_msg(f'aborting f1_thread {name}, '
                             f'thread.is_alive(): {thread.thread.is_alive()}.')
            if thread.thread.is_alive():
                self.msgs.queue_msg(name, ConfigCmd(cmd=ConfigCmds.Exit,
                                                    names=[name],
                                                    confirm_response=False))

    def get_is_alive(self, name: str) -> bool:
        """Get the is_alive flag for the named thread.

        Args:
            name: names of thread to get the is_alive flag

        """
        if self.expected_registered[name].exiting:
            return self.expected_registered[name].thread.thread.is_alive()
        else:
            return self.expected_registered[name].is_alive

    def inc_ops_count(self, targets: list[str], remote: str):
        """Increment the pending operations count.

        Args:
            targets: the names of the threads whose count is to be
                       incremented
            remote: the names of the threads that are paired with
                         the targets
        """
        with self.ops_lock:
            for target in targets:
                pair_key = st.SmartThread._get_pair_key(target, remote)
                # check to make sure remote is paired - might not have
                # started yet. Note that we also need to check to make
                # sure the target is in the expected pairs in case it
                # was removed but the other thread remained because it
                # has a pending ops count (and non-empty msg_q)
                if (pair_key in self.expected_pairs and
                        target in self.expected_pairs[pair_key]):
                    self.expected_pairs[pair_key][
                        target].pending_ops_count += 1
                else:
                    # we are assuming that the remote will be started
                    # while send_msg is running and that the msg
                    # will be delivered (otherwise we should not have
                    # called inc_ops_count)
                    if pair_key not in self.pending_ops_counts:
                        self.pending_ops_counts[pair_key] = {}
                    if target in self.pending_ops_counts[pair_key]:
                        self.pending_ops_counts[pair_key][target] += 1
                    else:
                        self.pending_ops_counts[pair_key][target] = 1

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
                self.abort_all_f1_threads()
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
                self.abort_all_f1_threads()
                raise InvalidConfigurationDetected(
                    f'SmartThread registry has entry for name {name} '
                    f'that is missing from the expected_registry ')
            if (self.expected_registered[name].is_alive
                    != thread.thread.is_alive()):
                self.abort_all_f1_threads()
                raise InvalidConfigurationDetected(
                    f'SmartThread registry has entry for name {name} '
                    f'that has is_alive of {thread.thread.is_alive()} '
                    f'which does not match the expected_registered '
                    f'is_alive of {self.expected_registered[name].is_alive}')
            if (self.expected_registered[name].status
                    != thread.status):
                self.abort_all_f1_threads()
                raise InvalidConfigurationDetected(
                    f'SmartThread registry has entry for name {name} '
                    f'that has satus of {thread.status} '
                    f'which does not match the expected_registered '
                    f'status of {self.expected_registered[name].status}')

        # verify expected_registered matches real registry
        for name, tracker in self.expected_registered.items():
            if name not in st.SmartThread._registry:
                self.abort_all_f1_threads()
                raise InvalidConfigurationDetected(
                    f'ConfigVerifier expected_registered has '
                    f'entry for name {name} '
                    f'that is missing from SmartThread._registry')

        # verify pair_array matches expected_pairs
        for pair_key in st.SmartThread._pair_array.keys():
            if pair_key not in self.expected_pairs:
                self.abort_all_f1_threads()
                raise InvalidConfigurationDetected(
                    f'ConfigVerifier found pair_key {pair_key}'
                    f'in SmartThread._pair_array that is '
                    f'not found in expected_pairs: ')
            for name in st.SmartThread._pair_array[
                pair_key].status_blocks.keys():
                if name not in self.expected_pairs[pair_key].keys():
                    self.abort_all_f1_threads()
                    raise InvalidConfigurationDetected(
                        f'ConfigVerifier found name {name} in '
                        f'SmartThread._pair_array status_blocks for pair_key'
                        f' {pair_key}, but is missing in expected_pairs: ')
                if name not in self.expected_registered:
                    self.abort_all_f1_threads()
                    raise InvalidConfigurationDetected(
                        f'ConfigVerifier found name {name} in '
                        f'SmartThread._pair_array status_blocks for pair_key'
                        f' {pair_key}, but is missing in '
                        f'expected_registered: ')
                if len(self.expected_pairs[pair_key]) == 1:
                    if self.expected_pairs[pair_key][
                            name].pending_ops_count == 0:
                        self.abort_all_f1_threads()
                        raise InvalidConfigurationDetected(
                            f'ConfigVerifier found name {name} in '
                            f'SmartThread._pair_array status_blocks for '
                            f'pair_key {pair_key}, but it is a single name '
                            f'that has a pending_ops_count of zero')

                if (self.expected_pairs[pair_key][
                    name].pending_ops_count == 0
                        and not st.SmartThread._pair_array[
                            pair_key].status_blocks[name].msg_q.empty()):
                    self.abort_all_f1_threads()
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
                    ops_count = self.expected_pairs[pair_key][
                        name].pending_ops_count
                    self.abort_all_f1_threads()
                    raise InvalidConfigurationDetected(
                        f'ConfigVerifier found that the expected_pairs '
                        f'entry for pair_key {pair_key}, the entry for '
                        f'{name} has has a pending_ops_count of '
                        f'{ops_count}, but the SmartThread._pair_array'
                        f' entry for {name} has a an empty msg_q')
        # verify expected_pairs matches pair_array
        for pair_key in self.expected_pairs:
            if pair_key not in st.SmartThread._pair_array:
                self.abort_all_f1_threads()
                raise InvalidConfigurationDetected(
                    f'ConfigVerifier found pair_key {pair_key} in '
                    'expected_pairs but not in SmartThread._pair_array')
            for name in self.expected_pairs[pair_key].keys():
                if name not in st.SmartThread._pair_array[
                        pair_key].status_blocks:
                    self.abort_all_f1_threads()
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
    # build_create_suite
    ################################################################
    def build_create_suite(self,
                           commander_name: Optional[str] = None,
                           commander_auto_start: Optional[bool] = True,
                           names: Optional[list[str]] = None,
                           auto_start: Optional[bool] = True,
                           validate_config: Optional[bool] = True
                           ) -> list[ConfigCmd]:
        """Return a list of ConfigCmd items for a create.

        Args:
            commander_name: specifies that a commander thread is to be
                created with this name
            commander_auto_start: specifies whether to start the
                commander thread during create
            names: names to use on the create
            auto_start: specifies whether to start threads during create
            validate_config: indicates whether to do config validation

        Returns:
            a list of ConfigCmd items
        """
        ret_suite = []
        if commander_name:
            if not {commander_name}.issubset(self.unregistered_names):
                self.abort_all_f1_threads()
                raise InvalidInputDetected('Input commander name '
                                           f'{commander_name} not a subset of '
                                           'unregistered names '
                                           f'{self.unregistered_names}')
            self.unregistered_names -= {commander_name}
            if commander_auto_start:
                ret_suite.extend([
                    ConfigCmd(cmd=ConfigCmds.CreateCommanderAutoStart,
                              commander_name=commander_name)])

                self.active_names |= {commander_name}
            else:
                ret_suite.extend([
                    ConfigCmd(cmd=ConfigCmds.CreateCommanderNoStart,
                              commander_name=commander_name)])
                self.registered_names |= {commander_name}

        if names:
            if not set(names).issubset(self.unregistered_names):
                self.abort_all_f1_threads()
                raise InvalidInputDetected(f'Input names {names} not a '
                                           f'subset of unregistered names '
                                           f'{self.unregistered_names}')
            self.unregistered_names -= set(names)
            if auto_start:
                ret_suite.extend([
                    ConfigCmd(cmd=ConfigCmds.CreateAutoStart,
                              names=names)])
                self.active_names |= set(names)
            else:
                ret_suite.extend([
                    ConfigCmd(cmd=ConfigCmds.CreateNoStart,
                              names=names)])
                self.registered_names |= set(names)

        if self.registered_names:
            ret_suite.extend([
                ConfigCmd(cmd=ConfigCmds.VerifyRegistered,
                          names=list(self.registered_names))])

        if self.active_names:
            ret_suite.extend([
                ConfigCmd(cmd=ConfigCmds.VerifyActive,
                          names=list(self.active_names))])
        if validate_config:
            ret_suite.extend([
                ConfigCmd(cmd=ConfigCmds.ValidateConfig)])

        return ret_suite

    ################################################################
    # build_f1_create_suite_num
    ################################################################
    def build_f1_create_suite_num(self,
                                  num_to_create: int,
                                  auto_start: Optional[bool] = True,
                                  validate_config: Optional[bool] = True
                                  ) -> list[ConfigCmd]:
        """Return a list of ConfigCmd items for a create.

        Args:
            num_to_create: number of f1 threads to create
            auto_start: indicates whether to use auto_start
            validate_config: indicates whether to do config validation

        Returns:
            a list of ConfigCmd items
        """
        assert num_to_create > 0
        if len(self.unregistered_names) < num_to_create:
            self.abort_all_f1_threads()
            raise InvalidInputDetected(
                f'Input num_to_create {num_to_create} '
                f'is greater than the number of '
                f'unregistered threads '
                f'{len(self.unregistered_names)}')

        names: list[str] = list(
            random.sample(self.unregistered_names, num_to_create))

        return self.build_create_suite(names=names,
                                       auto_start=auto_start,
                                       validate_config=validate_config)

    ################################################################
    # build_unreg_suite
    ################################################################
    def build_unreg_suite(self,
                          names: list[str]) -> list[ConfigCmd]:
        """Return a list of ConfigCmd items for unregister.

        Args:
            names: thread name to be unregistered

        Returns:
            a list of ConfigCmd items
        """
        if not set(names).issubset(self.registered_names):
            self.abort_all_f1_threads()
            raise InvalidInputDetected(f'Input {names} is not a subset '
                                       'of registered names '
                                       f'{self.registered_names}')

        ret_suite = [
            ConfigCmd(cmd=ConfigCmds.Unregister, names=names),
            ConfigCmd(cmd=ConfigCmds.VerifyNotRegistered, names=names),
            ConfigCmd(cmd=ConfigCmds.VerifyNotPaired, names=names)]

        ret_suite.extend([ConfigCmd(cmd=ConfigCmds.ValidateConfig)])

        self.registered_names -= set(names)
        self.unregistered_names |= set(names)

        return ret_suite

    ################################################################
    # build_unreg_suite_num
    ################################################################
    def build_unreg_suite_num(self,
                              num_to_unreg: int) -> list[ConfigCmd]:
        """Return a list of ConfigCmd items for unregister.

        Args:
            num_to_unreg: number of threads to be unregistered

        Returns:
            a list of ConfigCmd items
        """
        assert num_to_unreg > 0
        if len(self.registered_names) < num_to_unreg:
            self.abort_all_f1_threads()
            raise InvalidInputDetected(f'Input num_to_unreg {num_to_unreg} '
                                       f'is greater than the number of '
                                       f'registered threads '
                                       f'{len(self.registered_names)}')

        names: list[str] = list(
            random.sample(self.registered_names, num_to_unreg))

        return self.build_unreg_suite(names=names)

    ################################################################
    # build_start_suite
    ################################################################
    def build_start_suite(self,
                          names: list[str]) -> list[ConfigCmd]:
        """Return a list of ConfigCmd items for unregister.

        Args:
            names: thread name to be started

        Returns:
            a list of ConfigCmd items
        """
        if not set(names).issubset(self.registered_names):
            self.abort_all_f1_threads()
            raise InvalidInputDetected(f'Input {names} is not a subset '
                                       'of registered names '
                                       f'{self.registered_names}')

        ret_suite = [
            ConfigCmd(cmd=ConfigCmds.Start, names=names),
            ConfigCmd(cmd=ConfigCmds.VerifyActive,
                      names=names),
            ConfigCmd(cmd=ConfigCmds.ValidateConfig)]

        self.registered_names -= set(names)
        self.active_names |= set(names)

        return ret_suite

    ################################################################
    # build_start_suite_num
    ################################################################
    def build_start_suite_num(self,
                              num_to_start: int) -> list[ConfigCmd]:
        """Return a list of ConfigCmd items for unregister.

        Args:
            num_to_start: number of threads to be started

        Returns:
            a list of ConfigCmd items
        """
        assert num_to_start > 0
        if len(self.registered_names) < num_to_start:
            self.abort_all_f1_threads()
            raise InvalidInputDetected(f'Input num_to_start {num_to_start} '
                                       f'is greater than the number of '
                                       f'registered threads '
                                       f'{len(self.registered_names)}')

        names: list[str] = list(
            random.sample(self.registered_names, num_to_start))

        return self.build_start_suite(names=names)

    ################################################################
    # build_config
    ################################################################
    def build_config(self,
                     num_registered: Optional[int] = 0,
                     num_active: Optional[int] = 1,
                     num_stopped: Optional[int] = 0
                     ) -> list[ConfigCmd]:
        """Return a list of ConfigCmd items for config.

        Args:
            num_registered: number of threads that need to be
                registered but not yet started (meaning state is
                Registered)
            num_active: number of threads that need to be active
                (meaning state is Active)
            num_stopped: number of threads that need to have exited but
                not yet joined (meaning state is Stopped)

        Returns:
            a list of ConfigCmd items

        Note: the number of registered, active, and stopped must not
            exceed the number of thread_names

        """
        assert (num_registered
                + num_active
                + num_stopped) <= len(self.thread_names)
        assert num_active >= 1  # always need at least 1 for commander

        ret_suite = []

        if not self.commander_thread_config_built:
            ret_suite.extend(self.build_create_suite(
                commander_name=self.commander_name))
            self.commander_thread_config_built = True
            # num_active -= 1  # one less active thread to create

        num_adjust_registered = len(self.registered_names) - num_registered
        num_adjust_active = len(self.active_names) - num_active
        num_adjust_stopped = len(self.stopped_names) - num_stopped

        num_create_auto_start = 0
        num_create_no_start = 0
        num_reg_to_unreg = 0
        num_reg_to_start = 0
        num_active_to_exit = 0
        num_stopped_to_join = 0
        num_active_to_join = 0

        # determine how many to start for active and stopped
        if num_adjust_registered > 0:  # if surplus of registered
            num_adjust_act_stop = num_adjust_active + num_adjust_stopped
            if num_adjust_act_stop < 0:  # if shortage
                num_reg_to_start = min(num_adjust_registered,
                                       -num_adjust_act_stop)
                num_adjust_registered -= num_reg_to_start
                num_adjust_active += num_reg_to_start

            if num_adjust_registered > 0:  # if still surplus
                num_reg_to_unreg = num_adjust_registered
                num_adjust_registered = 0
        elif num_adjust_registered < 0:
            num_create_no_start = -num_adjust_registered
            num_adjust_registered = 0

        if num_adjust_active > 0:  # if surplus
            if num_adjust_stopped < 0:  # need more
                num_active_to_exit = min(num_adjust_active,
                                         -num_adjust_stopped)
                num_adjust_active -= num_active_to_exit
                num_adjust_stopped += num_active_to_exit

            if num_adjust_active > 0:  # if still surplus
                num_active_to_exit += num_adjust_active
                num_active_to_join = num_adjust_active
                num_adjust_active = 0
        elif num_adjust_active < 0:  # if need more
            num_create_auto_start += -num_adjust_active
            num_adjust_active = 0

        if num_adjust_stopped > 0:  # if surplus
            num_stopped_to_join += num_adjust_stopped
            num_adjust_stopped = 0
        elif num_adjust_stopped < 0:  # if we need more
            num_create_auto_start += -num_adjust_stopped
            num_active_to_exit += -num_adjust_stopped
            num_adjust_stopped = 0

        # start by reducing surpluses
        if num_reg_to_unreg > 0:
            ret_suite.extend(
                self.build_unreg_suite_num(num_to_unreg=num_reg_to_unreg))

        if num_stopped_to_join > 0:
            ret_suite.extend(
                self.build_join_suite_num(num_to_join=num_stopped_to_join))

        # create threads with no_start
        if num_create_no_start > 0:
            ret_suite.extend(
                self.build_f1_create_suite_num(
                    num_to_create=num_create_no_start,
                    auto_start=False))

        # start registered so we have actives to exit if need be
        if num_reg_to_start > 0:
            ret_suite.extend(self.build_start_suite_num(
                num_to_start=num_reg_to_start))

        # create threads with auto_start
        if num_create_auto_start > 0:
            ret_suite.extend(self.build_f1_create_suite_num(
                num_to_create=num_create_auto_start,
                auto_start=True))

        # Now that we have actives, do any needed exits
        if num_active_to_exit > 0:
            ret_suite.extend(self.build_exit_suite_num(
                num_to_exit=num_active_to_exit))

        # Finally, join the stopped threads as needed
        if num_active_to_join > 0:
            ret_suite.extend(self.build_join_suite_num(
                num_to_join=num_active_to_join))

        # verify the counts
        ret_suite.extend([
            ConfigCmd(cmd=ConfigCmds.VerifyCounts,
                      num_registered=num_registered,
                      num_active=num_active,
                      num_stopped=num_stopped)])

        return ret_suite

    ################################################################
    # build_recv_msg_timeout_suite
    ################################################################
    def build_recv_msg_timeout_suite(
            self,
            timeout_type: TimeoutType,
            num_receivers: int,
            num_active_senders: int,
            num_send_exit_senders: int,
            num_nosend_exit_senders: int,
            num_unreg_senders: int,
            num_reg_senders: int) -> list[ConfigCmd]:
        """Return a list of ConfigCmd items for a msg timeout.

        Args:
            timeout_type: specifies whether the recv_msg should
                be coded with timeout and whether the recv_msg should
                succeed or fail with a timeout
            num_receivers: number of threads that will do the
                recv_msg
            num_active_senders: number of threads that are active
                and will do the send_msg
            num_send_exit_senders: number of threads that are active
                and will do the send_msg and then exit
            num_nosend_exit_senders: number of threads that are
                active and will not do the send_msg and then exit
            num_unreg_senders: number of threads that are
                unregistered and will be created and started and then
                do the send_msg
            num_reg_senders: number of threads that are registered
                and will be started and then do the send_msg

        Returns:
            a list of ConfigCmd items
        """
        # Make sure we have enough threads. Note that we subtract 1 from
        # the count of unregistered names to ensure we have one thread
        # for the commander
        assert (num_receivers
                + num_active_senders
                + num_send_exit_senders
                + num_nosend_exit_senders
                + num_unreg_senders
                + num_reg_senders) <= len(self.unregistered_names) - 1

        assert num_receivers > 0

        assert (num_active_senders
                + num_send_exit_senders
                + num_nosend_exit_senders
                + num_unreg_senders
                + num_reg_senders) > 0

        ret_suite = []

        num_active_needed = (
                num_receivers
                + num_active_senders
                + num_send_exit_senders
                + num_nosend_exit_senders
                + 1)

        ret_suite = (self.build_config(
            num_registered=num_reg_senders,
            num_active=num_active_needed))

        # active_names = self.active_names.copy()
        # remove commander for now, but if we add it later we need to
        # be careful not to exit the commander
        active_names = self.active_names - {self.commander_name}

        ################################################################
        # choose receiver_names
        ################################################################
        receiver_names: list[str] = list(
            random.sample(active_names, num_receivers))
        active_names -= set(receiver_names)

        log_msg = f'receiver_names: {receiver_names}'
        self.log_ver.add_msg(log_msg=re.escape(log_msg))
        logger.debug(log_msg)

        ################################################################
        # choose active_sender_names
        ################################################################
        active_sender_names: list[str] = []
        if num_active_senders > 0:
            active_sender_names = list(
                random.sample(active_names, num_active_senders))
            active_names -= set(active_sender_names)

        log_msg = f'active_sender_names: {active_sender_names}'
        self.log_ver.add_msg(log_msg=re.escape(log_msg))
        logger.debug(log_msg)

        ################################################################
        # choose send_exit_sender_names
        ################################################################
        send_exit_sender_names: list[str] = []
        if num_send_exit_senders > 0:
            send_exit_sender_names = list(
                random.sample(active_names, num_send_exit_senders))
            active_names -= set(send_exit_sender_names)

        log_msg = f'send_exit_sender_names: {send_exit_sender_names}'
        self.log_ver.add_msg(log_msg=re.escape(log_msg))
        logger.debug(log_msg)

        ################################################################
        # choose nosend_exit_sender_names
        ################################################################
        nosend_exit_sender_names: list[str] = []
        if num_nosend_exit_senders > 0:
            nosend_exit_sender_names: list[str] = list(
                random.sample(active_names, num_nosend_exit_senders))
            active_names -= set(nosend_exit_sender_names)

        log_msg = f'nosend_exit_sender_names: {nosend_exit_sender_names}'
        self.log_ver.add_msg(log_msg=re.escape(log_msg))
        logger.debug(log_msg)

        ################################################################
        # choose unreg_sender_names
        ################################################################
        unreg_sender_names: list[str] = []
        if num_unreg_senders > 0:
            unreg_sender_names = list(
                random.sample(self.unregistered_names, num_unreg_senders))

        log_msg = f'unreg_sender_names: {unreg_sender_names}'
        self.log_ver.add_msg(log_msg=re.escape(log_msg))
        logger.debug(log_msg)

        ################################################################
        # choose reg_sender_names
        ################################################################
        reg_sender_names: list[str] = []
        if num_reg_senders > 0:
            reg_sender_names = list(
                random.sample(self.registered_names, num_reg_senders))

        log_msg = f'reg_sender_names: {reg_sender_names}'
        self.log_ver.add_msg(log_msg=re.escape(log_msg))
        logger.debug(log_msg)

        ################################################################
        # start by doing the recv_msgs, one for each sender
        ################################################################
        all_sender_names: list[str] = (active_sender_names
                                       + send_exit_sender_names
                                       + nosend_exit_sender_names
                                       + unreg_sender_names
                                       + reg_sender_names)
        sender_1_msg_1 = f'recv test: {self.get_ptime()}'
        ret_suite.extend([
            ConfigCmd(cmd=ConfigCmds.RecvMsg,
                      names=receiver_names,
                      from_names=all_sender_names,
                      msg_to_send=sender_1_msg_1,
                      confirm_response=False)])
            # ConfigCmd(cmd=ConfigCmds.ConfirmResponse,
            #           names=receiver_names,
            #           confirm_response_cmd=ConfigCmds.RecvMsg)])

        ################################################################
        # do send_msg from active senders
        ################################################################
        if active_sender_names:
            # sender_1_msg_1[exit_name] = f'send test: {self.get_ptime()}'
            # log_msg = f'log test: {self.get_ptime()}'

            ret_suite.extend([
                ConfigCmd(cmd=ConfigCmds.SendMsg,
                          names=active_sender_names,
                          to_names=receiver_names,
                          msg_to_send=sender_1_msg_1,
                          # log_msg=log_msg,
                          confirm_response=True),
                ConfigCmd(cmd=ConfigCmds.ConfirmResponse,
                          names=active_sender_names,
                          confirm_response_cmd=ConfigCmds.SendMsg)])

        return ret_suite

    ################################################################
    # build_msg_timeout_suite
    ################################################################
    def build_msg_timeout_suite(self,
                                timeout_type: TimeoutType,
                                num_senders: Optional[int] = 1,
                                num_active_targets: Optional[int] = 1,
                                num_registered_targets: Optional[int] = 0,
                                num_unreg_timeouts: Optional[int] = 0,
                                num_exit_timeouts: Optional[int] = 1,
                                num_full_q_timeouts: Optional[int] = 0
                                ) -> list[ConfigCmd]:
        """Return a list of ConfigCmd items for a msg timeout.

        Args:
            timeout_type: specifies whether to issue the send_cmd with
                timeout, and is so whether the send_cmd should timeout
                or, by starting exited threads in time, not timeout
            num_senders: specifies number of threads that will send msg
            num_active_targets: specifies number of threads to receive
                the msg,
                including those that are registered only or expected to
                cause the timeout
            num_registered_targets: specifies the number of targets that
                should be registered only (i.e., not yet started)
            num_unreg_timeouts: specifies the number of threads that
                should cause timeout by being unregistered
            num_exit_timeouts: specifies the number of threads that
                should be exited and joined to cause timeout
            num_full_q_timeouts: specifies the number of threads that
                should cause timeout by having a full msg queue

        Returns:
            a list of ConfigCmd items
        """
        # Make sure we have enough threads. Note that we subtract 1 from
        # the count of unregistered names to ensure we have one thread
        # for the commander
        assert (num_senders
                + num_active_targets
                + num_registered_targets
                + num_unreg_timeouts
                + num_exit_timeouts
                + num_full_q_timeouts) <= len(self.unregistered_names) - 1

        assert num_senders > 0

        assert (num_unreg_timeouts
                + num_exit_timeouts
                + num_full_q_timeouts) > 0

        # for the exit timeout case, we send zero msgs for the first
        # thread, then 1 for the second thread, 2 for the third, etc.,
        # so we need to make sure we don't exceed the max number of
        # messages that can be received
        assert num_exit_timeouts < self.max_msgs

        ret_suite = []

        num_active_needed = (
                num_senders
                + num_active_targets
                + num_exit_timeouts
                + num_full_q_timeouts
                + 1)

        ret_suite = (self.build_config(
            num_registered=num_registered_targets,
            num_active=num_active_needed))

        # active_names = self.active_names.copy()
        # remove commander for now, but if we add it later we need to
        # be careful not to exit the commander
        print(f'\nself.active_names: {self.active_names}')

        active_names = self.active_names - {self.commander_name}

        print(f'active_names 1: {active_names}')

        sender_names: list[str] = list(
            random.sample(active_names, num_senders))
        active_names -= set(sender_names)

        print(f'sender_names: {sender_names}')
        print(f'active_names 2: {active_names}')

        active_target_names: list[str] = []
        if num_active_targets > 0:
            active_target_names = list(
                random.sample(active_names,
                              num_active_targets))
            active_names -= set(active_target_names)

        print(f'active_target_names: {active_target_names}')
        print(f'active_names 3: {active_names}')

        registered_target_names: list[str] = []
        if num_registered_targets > 0:
            registered_target_names = list(
                random.sample(self.registered_names,
                              num_registered_targets))
        print(f'registered_target_names: {registered_target_names}')

        unreg_timeout_names: list[str] = []
        if num_unreg_timeouts > 0:
            unreg_timeout_names = list(
                random.sample(self.unregistered_names,
                              num_unreg_timeouts))

        print(f'unreg_timeout_names: {unreg_timeout_names}')

        exit_names: list[str] = []
        if num_exit_timeouts > 0:
            exit_names = list(
                random.sample(active_names,
                              num_exit_timeouts))
            active_names -= set(exit_names)

        print(f'exit_names: {exit_names}')
        print(f'active_names 4: {active_names}')

        full_q_names: list[str] = []
        if num_full_q_timeouts > 0:
            full_q_names = list(
                random.sample(active_names,
                              num_full_q_timeouts))
            active_names -= set(full_q_names)

        print(f'full_q_names: {full_q_names}')
        print(f'active_names 5: {active_names}')

        log_msg = f'sender_names: {sender_names}'
        self.log_ver.add_msg(log_msg=re.escape(log_msg))
        logger.debug(log_msg)

        log_msg = f'active_target_names: {active_target_names}'
        self.log_ver.add_msg(log_msg=re.escape(log_msg))
        logger.debug(log_msg)

        log_msg = f'registered_target_names: {registered_target_names}'
        self.log_ver.add_msg(log_msg=re.escape(log_msg))
        logger.debug(log_msg)

        log_msg = f'unreg_timeout_names: {unreg_timeout_names}'
        self.log_ver.add_msg(log_msg=re.escape(log_msg))
        logger.debug(log_msg)

        log_msg = f'exit_names: {exit_names}'
        self.log_ver.add_msg(log_msg=re.escape(log_msg))
        logger.debug(log_msg)

        log_msg = f'full_q_names: {full_q_names}'
        self.log_ver.add_msg(log_msg=re.escape(log_msg))
        logger.debug(log_msg)

        ################################################################
        # send msgs to senders so we have some on their queues so we
        # can verify partially paired for any threads that are exited
        ################################################################
        sender_1_msg_1: dict[str, str] = {}
        if exit_names and num_senders >= 2:
            for exit_name in exit_names:
                sender_1_msg_1[exit_name] = f'send test: {self.get_ptime()}'
                log_msg = f'log test: {self.get_ptime()}'

                ret_suite.extend([
                    ConfigCmd(cmd=ConfigCmds.SendMsg,
                              names=[exit_name],
                              to_names=[sender_names[1]],
                              msg_to_send=sender_1_msg_1[exit_name],
                              log_msg=log_msg,
                              confirm_response=True),
                    ConfigCmd(cmd=ConfigCmds.ConfirmResponse,
                              names=[exit_name],
                              confirm_response_cmd=ConfigCmds.SendMsg)])

        sender_2_msg_1: dict[str, str] = {}
        sender_2_msg_2: dict[str, str] = {}
        if exit_names and num_senders == 3:
            for exit_name in exit_names:
                sender_2_msg_1[exit_name] = f'send test: {self.get_ptime()}'
                ret_suite.extend([
                    ConfigCmd(cmd=ConfigCmds.SendMsg,
                              names=[exit_name],
                              to_names=[sender_names[2]],
                              msg_to_send=sender_2_msg_1[exit_name],
                              confirm_response=True),
                    ConfigCmd(cmd=ConfigCmds.ConfirmResponse,
                              names=[exit_name],
                              confirm_response_cmd=ConfigCmds.SendMsg)])
                sender_2_msg_2[exit_name] = f'send test: {self.get_ptime()}'
                log_msg = f'log test: {self.get_ptime()}'
                # for enter_exit in ('entered', 'exiting'):
                #     self.add_log_msg(re.escape(
                #         f'send_msg() {enter_exit}: {exit_name} -> '
                #         f'{sender_names[2]} '
                #         f'{self.log_ver.get_call_seq("main_driver")} '
                #         f'{log_msg}'))

                ret_suite.extend([
                    ConfigCmd(cmd=ConfigCmds.SendMsg,
                              names=[exit_name],
                              to_names=[sender_names[2]],
                              msg_to_send=sender_2_msg_2[exit_name],
                              log_msg=log_msg,
                              confirm_response=True),
                    ConfigCmd(cmd=ConfigCmds.ConfirmResponse,
                              names=[exit_name],
                              confirm_response_cmd=ConfigCmds.SendMsg)])

        ################################################################
        # send max msgs if needed
        ################################################################
        fullq_msgs: list[str] = []
        if full_q_names:
            for idx in range(self.max_msgs):
                # send from each sender thread to ensure we get
                # exactly max_msgs on each pair between sender and the
                # full_q targets
                fullq_msgs.append(f'send test: {self.get_ptime()}')
                ret_suite.extend([ConfigCmd(cmd=ConfigCmds.SendMsg,
                                            names=sender_names,
                                            to_names=full_q_names,
                                            msg_to_send=fullq_msgs[idx],
                                            confirm_response=True)])
                ret_suite.extend([ConfigCmd(
                    cmd=ConfigCmds.ConfirmResponse,
                    names=sender_names,
                    confirm_response_cmd=ConfigCmds.SendMsg)])

        ################################################################
        # build exit and join suites for the exit names
        ################################################################
        if exit_names:
            for idx in range(1, num_exit_timeouts):
                # the idea here is to have the first exit_name have zero
                # msgs, the second will have 1 msg, etc, etc, etc...
                for num_msgs in range(idx):
                    msg_to_send = f'send test: {self.get_ptime()}'
                    for sender_name in sender_names:
                        log_msg = f'log test: {self.get_ptime()}'
                        # for enter_exit in ('entered', 'exiting'):
                        #     self.add_log_msg(re.escape(
                        #         f'send_msg() {enter_exit}: {sender_name} -> '
                        #         f'{exit_names[idx]} '
                        #         f'{self.log_ver.get_call_seq("main_driver")} '
                        #         f'{log_msg}'))

                    ret_suite.extend([ConfigCmd(cmd=ConfigCmds.SendMsg,
                                                names=sender_names,
                                                to_names=[exit_names[idx]],
                                                msg_to_send=msg_to_send,
                                                log_msg=log_msg,
                                                confirm_response=True)])
                    ret_suite.extend([ConfigCmd(
                        cmd=ConfigCmds.ConfirmResponse,
                        names=sender_names,
                        confirm_response_cmd=ConfigCmds.SendMsg)])

            ret_suite.extend(self.build_exit_suite(names=exit_names))
            ret_suite.extend(self.build_join_suite(names=exit_names))

            for exit_name in exit_names:
                ret_suite.extend([ConfigCmd(
                    cmd=ConfigCmds.VerifyNotPaired,
                    names=[exit_name, sender_names[0]])])

            if num_senders >= 2:
                for exit_name in exit_names:
                    ret_suite.extend([ConfigCmd(
                        cmd=ConfigCmds.VerifyHalfPaired,
                        names=[exit_name, sender_names[1]],
                        half_paired_names=sender_names[1])])

            if num_senders == 3:
                for exit_name in exit_names:
                    ret_suite.extend([ConfigCmd(
                        cmd=ConfigCmds.VerifyHalfPaired,
                        names=[exit_name, sender_names[2]],
                        half_paired_names=sender_names[2])])

        all_targets: list[str] = (active_target_names
                                  + registered_target_names
                                  + unreg_timeout_names
                                  + exit_names
                                  + full_q_names)

        msg_to_send = f'send test: {self.get_ptime()}'
        final_recv_names = []
        if timeout_type == TimeoutType.TimeoutTrue:
            for sender_name in sender_names:
                log_msg = f'log test: {self.get_ptime()}'
                # self.add_log_msg(re.escape(
                #     f'send_msg() entered: {sender_name} -> '
                #     f'{set(all_targets)} '
                #     f'{self.log_ver.get_call_seq("main_driver")} '
                #     f'{log_msg}'))

            ret_suite.extend([
                ConfigCmd(cmd=ConfigCmds.SendMsgTimeoutTrue,
                          names=sender_names,
                          to_names=all_targets,
                          msg_to_send=msg_to_send,
                          unreg_timeout_names=unreg_timeout_names+exit_names,
                          fullq_timeout_names=full_q_names,
                          timeout=2.0,
                          confirm_response=True),
                ConfigCmd(cmd=ConfigCmds.ConfirmResponse,
                          names=sender_names,
                          confirm_response_cmd=ConfigCmds.SendMsgTimeoutTrue)])
            final_recv_names = active_target_names + registered_target_names
        else:
            if timeout_type == TimeoutType.TimeoutFalse:
                for sender_name in sender_names:
                    log_msg = f'log test: {self.get_ptime()}'
                    # for enter_exit in ('entered', 'exiting'):
                    #     self.add_log_msg(re.escape(
                    #         f'send_msg() {enter_exit}: {sender_name} -> '
                    #         f'{set(all_targets)} '
                    #         f'{self.log_ver.get_call_seq("main_driver")} '
                    #         f'{log_msg}'))
                ret_suite.extend([
                    ConfigCmd(cmd=ConfigCmds.SendMsgTimeoutFalse,
                              names=sender_names,
                              to_names=all_targets,
                              msg_to_send=msg_to_send,
                              unreg_timeout_names=unreg_timeout_names + exit_names,
                              fullq_timeout_names=full_q_names,
                              timeout=3.0,
                              confirm_response=True)])
                confirm_response_to_use = ConfigCmds.SendMsgTimeoutFalse
            else:
                ret_suite.extend([
                    ConfigCmd(
                        cmd=ConfigCmds.SendMsg,
                        names=sender_names,
                        to_names=all_targets,
                        msg_to_send=msg_to_send,
                        unreg_timeout_names=unreg_timeout_names + exit_names,
                        fullq_timeout_names=full_q_names,
                        confirm_response=True)])

                confirm_response_to_use = ConfigCmds.SendMsg

            ret_suite.extend([ConfigCmd(
                cmd=ConfigCmds.WaitForMsgTimeouts,
                names=sender_names,
                unreg_timeout_names=unreg_timeout_names + exit_names,
                fullq_timeout_names=full_q_names)])

            # restore config by adding back the exited threads and
            # creating the un_reg threads so send_msg will complete
            # before timing out
            if unreg_timeout_names or exit_names:
                ret_suite.extend(self.build_create_suite(
                    names=unreg_timeout_names + exit_names,
                    validate_config=False))

            # tell the fullq threads to read the stacked up msgs
            # so that the send_msg will complete
            if full_q_names:
                for idx in range(self.max_msgs):
                    ret_suite.extend([
                        ConfigCmd(cmd=ConfigCmds.RecvMsg,
                                  names=full_q_names,
                                  from_names=sender_names,
                                  msg_to_send=fullq_msgs[idx],
                                  confirm_response=False)])

            ret_suite.extend([
                ConfigCmd(cmd=ConfigCmds.ConfirmResponse,
                          names=sender_names,
                          confirm_response_cmd=confirm_response_to_use)
            ])
            final_recv_names = all_targets

        # start any registered threads
        if registered_target_names:
            ret_suite.extend(self.build_start_suite(
                names=registered_target_names))

        # do RecvMsg to verify the SendMsg for targets
        ret_suite.extend([
            ConfigCmd(cmd=ConfigCmds.RecvMsg,
                      names=final_recv_names,
                      from_names=sender_names,
                      msg_to_send=msg_to_send,
                      timeout=3,
                      confirm_response=True),
            ConfigCmd(cmd=ConfigCmds.ConfirmResponse,
                      names=final_recv_names,
                      confirm_response_cmd=ConfigCmds.RecvMsg)
        ])

        ################################################################
        # do RecvMsg to verify the SendMsg for senders
        ################################################################
        if exit_names and num_senders >= 2:
            for exit_name in exit_names:
                ret_suite.extend([
                    ConfigCmd(cmd=ConfigCmds.RecvMsg,
                              names=[sender_names[1]],
                              from_names=[exit_name],
                              msg_to_send=sender_1_msg_1[exit_name],
                              confirm_response=True),
                    ConfigCmd(cmd=ConfigCmds.ConfirmResponse,
                              names=[sender_names[1]],
                              confirm_response_cmd=ConfigCmds.RecvMsg)])

        if exit_names and num_senders == 3:
            for exit_name in exit_names:
                ret_suite.extend([
                    ConfigCmd(cmd=ConfigCmds.RecvMsg,
                              names=[sender_names[2]],
                              from_names=[exit_name],
                              msg_to_send=sender_2_msg_1[exit_name],
                              confirm_response=True),
                    ConfigCmd(cmd=ConfigCmds.ConfirmResponse,
                              names=[sender_names[2]],
                              confirm_response_cmd=ConfigCmds.RecvMsg)])
                ret_suite.extend([
                    ConfigCmd(cmd=ConfigCmds.RecvMsg,
                              names=[sender_names[2]],
                              from_names=[exit_name],
                              msg_to_send=sender_2_msg_2[exit_name],
                              confirm_response=True),
                    ConfigCmd(cmd=ConfigCmds.ConfirmResponse,
                              names=[sender_names[2]],
                              confirm_response_cmd=ConfigCmds.RecvMsg)])

        return ret_suite

    ################################################################
    # get_ptime
    ################################################################
    @staticmethod
    def get_ptime() -> str:
        """Returns a printable UTC time stamp.

        Returns:
            a timestamp as a strring
        """
        now_time = datetime.utcnow()
        print_time = now_time.strftime("%H:%M:%S.%f")

        return print_time

    ################################################################
    # build_msg_suite
    ################################################################
    @staticmethod
    def build_msg_suite(from_names: list[str],
                        to_names: list[str]) -> list[ConfigCmd]:
        """Return a list of ConfigCmd items for msgs.

        Returns:
            a list of ConfigCmd items
        """
        msg_to_send = f'send test: {self.get_ptime()}'
        return [
            ConfigCmd(cmd=ConfigCmds.SendMsg, names=from_names,
                      to_names=to_names,
                      msg_to_send=msg_to_send),
            ConfigCmd(cmd=ConfigCmds.RecvMsg, from_names=from_names,
                      names=to_names)]

    ################################################################
    # build_exit_suite
    ################################################################
    def build_exit_suite(self,
                         names: list[str],
                         ) -> list[ConfigCmd]:
        """Return a list of ConfigCmd items for a exit.

        Returns:
            a list of ConfigCmd items
        """
        if not set(names).issubset(self.active_names):
            self.abort_all_f1_threads()
            raise InvalidInputDetected(f'Input names {names} not a subset '
                                       f'of active names {self.active_names}')
        active_names = list(self.active_names - set(names))
        ret_suite = []
        if names:
            ret_suite.extend([
                ConfigCmd(cmd=ConfigCmds.Exit, names=names),
                ConfigCmd(cmd=ConfigCmds.VerifyNotAlive, names=names),
                ConfigCmd(cmd=ConfigCmds.VerifyStatus, names=names,
                          exp_status=st.ThreadStatus.Alive)])
        if active_names:
            ret_suite.extend([
                ConfigCmd(cmd=ConfigCmds.VerifyAlive, names=active_names),
                ConfigCmd(cmd=ConfigCmds.VerifyStatus, names=active_names,
                          exp_status=st.ThreadStatus.Alive)])
        ret_suite.extend([ConfigCmd(cmd=ConfigCmds.ValidateConfig)])

        self.active_names -= set(names)
        self.stopped_names |= set(names)

        return ret_suite

    ################################################################
    # build_exit_suite_num
    ################################################################
    def build_exit_suite_num(self,
                             num_to_exit: int) -> list[ConfigCmd]:
        """Return a list of ConfigCmd items for unregister.

        Args:
            num_to_exit: number of threads to exit

        Returns:
            a list of ConfigCmd items
        """
        assert num_to_exit > 0
        if (len(self.active_names) - 1) < num_to_exit:
            self.abort_all_f1_threads()
            raise InvalidInputDetected(f'Input num_to_exit {num_to_exit} '
                                       f'is greater than the number of '
                                       f'registered threads '
                                       f'{len(self.active_names)}')

        names: list[str] = list(
            random.sample(self.active_names - {self.commander_name},
                          num_to_exit))

        return self.build_exit_suite(names=names)

    ################################################################
    # build_join_suite
    ################################################################
    def build_join_suite(self,
                         names: list[str]) -> list[ConfigCmd]:
        """Return a list of ConfigCmd items for join.

        Args:
            names: list of names to join

        Returns:
            a list of ConfigCmd items
        """
        if not set(names).issubset(self.stopped_names):
            self.abort_all_f1_threads()
            raise InvalidInputDetected(f'Input {names} is not a subset '
                                       'of inactive names '
                                       f'{self.stopped_names}')

        ret_suite = []
        if names:
            ret_suite.extend([
                ConfigCmd(cmd=ConfigCmds.Join, names=names),
                ConfigCmd(cmd=ConfigCmds.VerifyNotRegistered, names=names),
                ConfigCmd(cmd=ConfigCmds.VerifyNotPaired, names=names)])

        ret_suite.extend([ConfigCmd(cmd=ConfigCmds.ValidateConfig)])

        self.unregistered_names |= set(names)
        self.stopped_names -= set(names)

        return ret_suite

    ################################################################
    # build_join_suite
    ################################################################
    def build_join_suite_num(self,
                             num_to_join: int) -> list[ConfigCmd]:
        """Return a list of ConfigCmd items for join.

        Args:
            num_to_join: number of threads to join

        Returns:
            a list of ConfigCmd items
        """
        assert num_to_join > 0
        if len(self.stopped_names) < num_to_join:
            self.abort_all_f1_threads()
            raise InvalidInputDetected(f'Input num_to_join {num_to_join} '
                                       f'is greater than the number of '
                                       f'stopped threads '
                                       f'{len(self.stopped_names)}')

        names: list[str] = list(
            random.sample(self.stopped_names, num_to_join))

        return self.build_join_suite(names=names)

    ################################################################
    # verify_is_registered
    ################################################################
    def verify_is_registered(self, names: list[str]) -> bool:
        """Verify that the given names are registered only.

        Args:
            names: names of the threads to check for being registered

        """
        if not self.verify_registered(names=names):
            return False
        if not self.verify_is_not_alive(names=names):
            return False
        if not self.verify_status(names=names,
                                  expected_status=st.ThreadStatus.Registered):
            return False
        if len(names) > 1 and not self.verify_paired(names=names):
            return False

        return True

    def verify_is_active(self, names: list[str]) -> bool:
        """Verify that the given names are active.

        Args:
            names: names of the threads to check for being active

        """
        if not self.verify_registered(names=names):
            return False
        if not self.verify_is_alive(names=names):
            return False
        if not self.verify_status(names=names,
                                  expected_status=st.ThreadStatus.Alive):
            return False
        if len(names) > 1 and not self.verify_paired(names=names):
            return False

        return True

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

    def verify_counts(self,
                      num_registered: Optional[int] = None,
                      num_active: Optional[int] = None,
                      num_stopped: Optional[int] = None) -> bool:
        """Verify that the given counts are correct.

        Args:
            num_registered: number of expected registered only threads
            num_active: number of expected active threads
            num_stopped: number of expected stopped threads

        """
        registered_found_real = 0
        active_found_real = 0
        stopped_found_real = 0
        for name, thread in st.SmartThread._registry.items():
            if thread.thread.is_alive():
                if thread.status == st.ThreadStatus.Alive:
                    active_found_real += 1
            else:
                if thread.status == st.ThreadStatus.Registered:
                    registered_found_real += 1
                elif (thread.status == st.ThreadStatus.Alive
                        or thread.status == st.ThreadStatus.Stopped):
                    stopped_found_real += 1

        registered_found_mock = 0
        active_found_mock = 0
        stopped_found_mock = 0
        for name, thread_tracker in self.expected_registered.items():
            if thread_tracker.is_alive:
                if thread_tracker.status == st.ThreadStatus.Alive:
                    active_found_mock += 1
            else:
                if thread_tracker.status == st.ThreadStatus.Registered:
                    registered_found_mock += 1
                elif (thread_tracker.status == st.ThreadStatus.Alive
                        or thread_tracker.status == st.ThreadStatus.Stopped):
                    stopped_found_mock += 1

        if num_registered is not None:
            if not (num_registered
                    == registered_found_real
                    == registered_found_mock):
                return False

        if num_active is not None:
            if not (num_active
                    == active_found_real
                    == active_found_mock):
                return False

        if num_stopped is not None:
            if not (num_stopped
                    == stopped_found_real
                    == stopped_found_mock):
                return False

        return True

    def wait_for_msg_timeouts(self,
                              sender_names: list[str],
                              unreg_names: list[str],
                              fullq_names: list[str]) -> None:
        """Verify that the senders have detected the timeout threads.

        Args:
            sender_names: names of the threads to check for timeout
                threads
            unreg_names: threads that cause timeout by being
                unregistered
            fullq_names: threads that cause timeout because their msg_q
                is full

        """
        unregs = []
        if unreg_names:
            unregs = sorted(unreg_names)
        fullqs = []
        if fullq_names:
            fullqs = sorted(fullq_names)

        work_senders = sender_names.copy()
        start_time = time.time()
        while work_senders:
            for sender in work_senders:
                test_unregs = []
                test_fullqs = []
                if sender == self.commander_name:
                    if self.commander_thread.remotes_unregistered:
                        test_unregs = sorted(
                            self.commander_thread.remotes_unregistered)
                    if self.commander_thread.remotes_full_send_q:
                        test_fullqs = sorted(
                            self.commander_thread.remotes_full_send_q)
                else:
                    if self.f1_threads[sender].remotes_unregistered:
                        test_unregs = sorted(
                            self.f1_threads[sender].remotes_unregistered)
                    if self.f1_threads[sender].remotes_full_send_q:
                        test_fullqs = sorted(
                            self.f1_threads[sender].remotes_full_send_q)

                if unregs == test_unregs and fullqs == test_fullqs:
                    work_senders.remove(sender)

            time.sleep(0.1)
            assert time.time() < start_time + 30  # allow 30 seconds

        return

################################################################
# expand_cmds
################################################################
def expand_list(nested_list: list[Any]) -> list[Any]:
    """Return a list of items from a nested list of lists.

    Args:
        nested_list: a list containing nested lists of items

    Returns:
        a single list of items
    """
    ret_list: list[Any] = []
    for item in nested_list:
        if isinstance(item, list):
            ret_list.extend(expand_list(item))
        else:
            ret_list.append(item)
    return ret_list


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

    commander_name = f1_config_ver.commander_thread.name
    f1_config_ver.log_ver.add_call_seq(
        name='f1_driver',
        seq='test_smart_thread.py::f1_driver')

    while True:

        cmd_msg: ConfigCmd = f1_config_ver.msgs.get_msg(
            f1_name, timeout=None)

        if cmd_msg.cmd == ConfigCmds.Exit:
            if cmd_msg.confirm_response:
                f1_config_ver.msgs.queue_msg(
                    commander_name,
                    f'{cmd_msg.cmd} completed by {f1_name}')
            break

        if (cmd_msg.cmd == ConfigCmds.SendMsg
                or cmd_msg.cmd == ConfigCmds.SendMsgTimeoutFalse
                or cmd_msg.cmd == ConfigCmds.SendMsgTimeoutTrue):
            ####################################################
            # send one or more msgs
            ####################################################
            ops_count_names = cmd_msg.to_names.copy()
            if cmd_msg.cmd == ConfigCmds.SendMsgTimeoutTrue:
                if cmd_msg.unreg_timeout_names:
                    ops_count_names = list(
                        set(ops_count_names)
                        - set(cmd_msg.unreg_timeout_names))
                if cmd_msg.fullq_timeout_names:
                    ops_count_names = list(
                        set(ops_count_names)
                        - set(cmd_msg.fullq_timeout_names))

            f1_config_ver.inc_ops_count(ops_count_names,
                                        f1_name)

            # enter_exit_list: list[str] = []
            if cmd_msg.cmd == ConfigCmds.SendMsg:
                enter_exit_list = ('entered', 'exiting')
                f1_config_ver.f1_threads[f1_name].send_msg(
                    targets=set(cmd_msg.to_names),
                    msg=cmd_msg.msg_to_send,
                    log_msg=cmd_msg.log_msg)
            elif cmd_msg.cmd == ConfigCmds.SendMsgTimeoutFalse:
                enter_exit_list = ('entered', 'exiting')
                f1_config_ver.f1_threads[f1_name].send_msg(
                    targets=set(cmd_msg.to_names),
                    msg=cmd_msg.msg_to_send,
                    log_msg=cmd_msg.log_msg,
                    timeout=cmd_msg.timeout)
            else:
                enter_exit_list = ('entered')
                with pytest.raises(st.SmartThreadSendMsgTimedOut):
                    f1_config_ver.f1_threads[f1_name].send_msg(
                        targets=set(cmd_msg.to_names),
                        msg=cmd_msg.msg_to_send,
                        log_msg=cmd_msg.log_msg,
                        timeout=cmd_msg.timeout)

                unreg_timeout_msg = ''
                if cmd_msg.unreg_timeout_names:
                    unreg_timeout_msg = (
                        'Remotes unregistered: '
                        f'{sorted(set(cmd_msg.unreg_timeout_names))}. ')
                fullq_timeout_msg = ''
                if cmd_msg.fullq_timeout_names:
                    fullq_timeout_msg = (
                        'Remotes with full send queue: '
                        f'{sorted(set(cmd_msg.fullq_timeout_names))}.')

                f1_config_ver.add_log_msg(re.escape(
                    f'{f1_name} timeout of a send_msg(). '
                    f'Targets: {sorted(set(cmd_msg.to_names))}. '
                    f'{unreg_timeout_msg}'
                    f'{fullq_timeout_msg}'))
                f1_config_ver.add_log_msg(
                    'Raise SmartThreadSendMsgTimedOut',
                    log_level=logging.ERROR)

            if cmd_msg.log_msg:
                log_msg_2 = (
                    f'{f1_config_ver.log_ver.get_call_seq("f1_driver")} ')
                log_msg_3 = re.escape(f'{cmd_msg.log_msg}')
                for enter_exit in enter_exit_list:
                    log_msg_1 = re.escape(
                        f'send_msg() {enter_exit}: {f1_name} -> '
                        f'{set(cmd_msg.to_names)} ')

                    f1_config_ver.add_log_msg(log_msg_1
                                              + log_msg_2
                                              + log_msg_3)

            for f1_to_name in ops_count_names:
                # print(f'cmd_msg.cmd: {cmd_msg.cmd} '
                #       f'ops_count_names: {ops_count_names}')
                log_msg_f1 = (f'{f1_name} sent message to '
                              f'{f1_to_name}')
                f1_config_ver.log_ver.add_msg(
                    log_name='scottbrian_paratools.smart_thread',
                    log_level=logging.INFO,
                    log_msg=log_msg_f1)

        # elif cmd_msg.cmd == ConfigCmds.SendMsgTimeoutTrue:
        #     ####################################################
        #     # send one or more msgs
        #     ####################################################
        #     with pytest.raises(st.SmartThreadSendMsgTimedOut):
        #         f1_config_ver.f1_threads[f1_name].send_msg(
        #             targets=cmd_msg.to_names,
        #             msg=cmd_msg,
        #             timeout=cmd_msg.timeout)
        #
        #     f1_config_ver.add_log_msg(re.escape(
        #         f'{f1_name} timeout of a send_msg()'))
        #     f1_config_ver.add_log_msg(
        #         'Raise SmartThreadSendMsgTimedOut',
        #         log_level=logging.ERROR)

        elif cmd_msg.cmd == ConfigCmds.RecvMsg:
            ####################################################
            # recv one or more msgs
            ####################################################
            for f1_from_name in cmd_msg.from_names:
                recvd_msg = f1_config_ver.f1_threads[f1_name].recv_msg(
                    remote=f1_from_name,
                    timeout=3)

                assert recvd_msg == cmd_msg.msg_to_send

                f1_copy_pair_deque = (
                    f1_config_ver.f1_threads[f1_name]
                    .time_last_pair_array_update.copy())
                f1_config_ver.dec_ops_count(f1_name,
                                            f1_from_name,
                                            f1_copy_pair_deque)

                log_msg_f1 = (f"{f1_name} received msg from "
                              f"{f1_from_name}")
                f1_config_ver.log_ver.add_msg(
                    log_name='scottbrian_paratools.smart_thread',
                    log_level=logging.INFO,
                    log_msg=log_msg_f1)

        elif cmd_msg.cmd == ConfigCmds.Pause:
            time.sleep(cmd_msg.pause_seconds)
        else:
            raise UnrecognizedCmd(
                f'The cmd_msg.cmd {cmd_msg.cmd} '
                'is not recognized')

        if cmd_msg.confirm_response:
            f1_config_ver.msgs.queue_msg(
                    commander_name, f'{cmd_msg.cmd} completed by {f1_name}')


################################################################
# main_driver
################################################################
def main_driver(config_ver: ConfigVerifier,
                scenario: list[ConfigCmd]) -> None:
    commander_name = config_ver.commander_name
    config_ver.log_ver.add_call_seq(
        name='main_driver',
        seq='test_smart_thread.py::main_driver')
    for config_cmd in scenario:
        log_msg = f'config_cmd: {config_cmd}'
        config_ver.log_ver.add_msg(log_msg=re.escape(log_msg))
        logger.debug(log_msg)

        ############################################################
        # CreateF1Thread
        ############################################################
        if config_cmd.cmd == ConfigCmds.CreateCommanderAutoStart:
            config_ver.create_commander_thread(
                name=config_cmd.commander_name,
                auto_start=True)
        elif config_cmd.cmd == ConfigCmds.CreateCommanderNoStart:
            config_ver.create_commander_thread(
                name=config_cmd.commander_name,
                auto_start=False)
        elif config_cmd.cmd == ConfigCmds.CreateAutoStart:
            for new_name in config_cmd.names:
                config_ver.create_f1_thread(
                    target=outer_f1,
                    name=new_name,
                    auto_start=True
                )
        elif config_cmd.cmd == ConfigCmds.CreateNoStart:
            for new_name in config_cmd.names:
                config_ver.create_f1_thread(
                    target=outer_f1,
                    name=new_name,
                    auto_start=False
                )
        elif config_cmd.cmd == ConfigCmds.Unregister:
            config_ver.unregister_thread(names=config_cmd.names)

        elif config_cmd.cmd == ConfigCmds.Start:
            for name in config_cmd.names:
                config_ver.start_thread(name=name)

        elif config_cmd.cmd == ConfigCmds.VerifyAlive:
            assert config_ver.verify_is_alive(config_cmd.names)

        elif config_cmd.cmd == ConfigCmds.VerifyActive:
            assert config_ver.verify_is_active(config_cmd.names)

        elif config_cmd.cmd == ConfigCmds.VerifyCounts:
            assert config_ver.verify_counts(config_cmd.num_registered,
                                            config_cmd.num_active,
                                            config_cmd.num_stopped)

        elif config_cmd.cmd == ConfigCmds.VerifyNotAlive:
            assert config_ver.verify_is_not_alive(config_cmd.names)

        elif config_cmd.cmd == ConfigCmds.VerifyStatus:
            assert config_ver.verify_status(
                names=config_cmd.names,
                expected_status=config_cmd.exp_status)

        elif (config_cmd.cmd == ConfigCmds.SendMsg
              or config_cmd.cmd == ConfigCmds.SendMsgTimeoutTrue
              or config_cmd.cmd == ConfigCmds.SendMsgTimeoutFalse):

            for name in config_cmd.names:
                if name == commander_name:
                    continue
                config_ver.msgs.queue_msg(target=name,
                                          msg=config_cmd)

            if commander_name in config_cmd.names:
                ops_count_names = config_cmd.to_names.copy()
                if config_cmd.cmd == ConfigCmds.SendMsgTimeoutFalse:
                    if config_cmd.unreg_timeout_names:
                        ops_count_names = list(
                            set(ops_count_names) - set(
                                config_cmd.unreg_timeout_names))
                    if config_cmd.fullq_timeout_names:
                        ops_count_names = list(
                            set(ops_count_names) - set(
                                config_cmd.fullq_timeout_names))

                config_ver.inc_ops_count(ops_count_names,
                                         commander_name)

                if config_cmd.cmd == ConfigCmds.SendMsg:
                    enter_exit_list = ('entered', 'exiting')
                    config_ver.commander_thread.send_msg(
                        targets=set(config_cmd.to_names),
                        msg=config_cmd.msg_to_send,
                        log_msg=config_cmd.log_msg)
                elif config_cmd.cmd == ConfigCmds.SendMsgTimeoutFalse:
                    enter_exit_list = ('entered', 'exiting')
                    config_ver.commander_thread.send_msg(
                        targets=set(config_cmd.to_names),
                        msg=config_cmd.msg_to_send,
                        log_msg=config_cmd.log_msg,
                        timeout=config_cmd.timeout)
                else:
                    enter_exit_list = ('entered')
                    with pytest.raises(st.SmartThreadSendMsgTimedOut):
                        config_ver.commander_thread.send_msg(
                            targets=set(config_cmd.to_names),
                            msg=config_cmd.msg_to_send,
                            log_msg=config_cmd.log_msg,
                            timeout=config_cmd.timeout)

                    unreg_timeout_msg = ''
                    if config_cmd.unreg_timeout_names:
                        unreg_timeout_msg = (
                            'Remotes unregistered: '
                            f'{sorted(set(config_cmd.unreg_timeout_names))}. ')
                    fullq_timeout_msg = ''
                    if config_cmd.fullq_timeout_names:
                        fullq_timeout_msg = (
                            'Remotes with full send queue: '
                            f'{sorted(set(config_cmd.fullq_timeout_names))}.')

                    config_ver.add_log_msg(re.escape(
                        f'{commander_name} timeout of a send_msg(). '
                        f'{unreg_timeout_msg}'
                        f'{fullq_timeout_msg}'))

                    config_ver.add_log_msg(
                        'Raise SmartThreadSendMsgTimedOut',
                        log_level=logging.ERROR)

                if config_cmd.log_msg:

                    log_msg_2 = (
                        f'{config_ver.log_ver.get_call_seq("main_driver")} ')
                    log_msg_3 = re.escape(f'{config_cmd.log_msg}')
                    for enter_exit in enter_exit_list:
                        log_msg_1 = re.escape(
                            f'send_msg() {enter_exit}: main_driver -> '
                            f'{set(config_cmd.to_names)} ')
                        # config_ver.add_log_msg(re.escape(
                        #     f'send_msg() {enter_exit}: main_driver -> '
                        #     f'{set(config_cmd.to_names)} ') +
                        #     f'{config_ver.log_ver.get_call_seq("main_driver")}'
                        #     f' {config_cmd.log_msg}'))
                        config_ver.add_log_msg(log_msg_1
                                               + log_msg_2
                                               + log_msg_3)

                for name in ops_count_names:
                    log_msg = (f'{commander_name} sent message to '
                               f'{name}')
                    config_ver.log_ver.add_msg(
                        log_name='scottbrian_paratools.smart_thread',
                        log_level=logging.INFO,
                        log_msg=log_msg)

        elif config_cmd.cmd == ConfigCmds.RecvMsg:
            for name in config_cmd.names:
                if name == commander_name:
                    continue
                config_ver.msgs.queue_msg(target=name,
                                          msg=config_cmd)
            if commander_name in config_cmd.names:
                for from_name in config_cmd.from_names:
                    recvd_msg = config_ver.commander_thread.recv_msg(
                        remote=from_name,
                        timeout=3)

                    assert recvd_msg == config_cmd.msg_to_send

                    copy_pair_deque = (
                        config_ver.commander_thread
                        .time_last_pair_array_update.copy())
                    config_ver.dec_ops_count(commander_name,
                                             from_name,
                                             copy_pair_deque)

                    log_msg = (f"{commander_name} received msg from "
                               f"{from_name}")
                    config_ver.log_ver.add_msg(
                        log_name='scottbrian_paratools.smart_thread',
                        log_level=logging.INFO,
                        log_msg=log_msg)

        elif config_cmd.cmd == ConfigCmds.Pause:
            for pause_name in config_cmd.names:
                if pause_name == commander_name:
                    continue
                config_ver.msgs.queue_msg(
                    target=pause_name, msg=config_cmd)
            if commander_name in config_cmd.names:
                time.sleep(config_cmd.pause_seconds)
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
            config_ver.commander_thread.join(targets=set(config_cmd.names))
            copy_reg_deque = (
                config_ver.commander_thread.time_last_registry_update
                .copy())
            copy_pair_deque = (
                config_ver.commander_thread.time_last_pair_array_update
                .copy())
            copy_join_names = config_ver.commander_thread.join_names.copy()
            config_ver.del_thread(
                name=commander_name,
                remotes=config_cmd.names,
                reg_update_times=copy_reg_deque,
                pair_array_update_times=copy_pair_deque,
                process_names=copy_join_names,
                process='join'
                )

        elif config_cmd.cmd == ConfigCmds.VerifyRegistered:
            assert config_ver.verify_is_registered(config_cmd.names)
        elif config_cmd.cmd == ConfigCmds.VerifyNotRegistered:
            assert config_ver.verify_not_registered(config_cmd.names)
        elif config_cmd.cmd == ConfigCmds.VerifyPaired:
            assert config_ver.verify_paired(config_cmd.names)
        elif config_cmd.cmd == ConfigCmds.VerifyHalfPaired:
            assert config_ver.verify_half_paired(
                config_cmd.names, config_cmd.half_paired_names)
        elif config_cmd.cmd == ConfigCmds.VerifyNotPaired:
            assert config_ver.verify_not_paired(config_cmd.names)
        elif config_cmd.cmd == ConfigCmds.ValidateConfig:
            config_ver.validate_config()
        elif config_cmd.cmd == ConfigCmds.WaitForMsgTimeouts:
            config_ver.wait_for_msg_timeouts(
                sender_names=config_cmd.names,
                unreg_names=config_cmd.unreg_timeout_names,
                fullq_names=config_cmd.fullq_timeout_names)
        elif config_cmd.cmd == ConfigCmds.ConfirmResponse:
            pending_responses = []
            for name in config_cmd.names:
                pending_responses.append(
                    f'{config_cmd.confirm_response_cmd} completed by {name}')
            while pending_responses:
                a_msg = config_ver.msgs.get_msg(commander_name, timeout=None)
                if a_msg in pending_responses:
                    pending_responses.remove(a_msg)
                else:
                    logger.debug(f'main raising UnrecognizedCmd for a_msg '
                                 f'{a_msg}')
                    config_ver.abort_all_f1_threads()
                    raise UnrecognizedCmd(
                        f'A response of {a_msg} for the SendMsg is '
                        'not recognized')
                time.sleep(0.1)
        else:
            config_ver.abort_all_f1_threads()
            raise UnrecognizedCmd(f'The config_cmd.cmd {config_cmd.cmd} '
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

        main_driver(main_name='alpha',
                    config_ver=config_ver,
                    scenario=config_scenario_arg)
        # random.seed(random_seed_arg)

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results)
        log_ver.verify_log_results(match_results)

        logger.debug('mainline exiting')

    ####################################################################
    # test_smart_thread_meta_scenarios
    ####################################################################
    def test_smart_thread_meta_scenarios(
            self,
            caplog: pytest.CaptureFixture[str]
    ) -> None:
        """Test meta configuration scenarios.

        Args:
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
        commander_name = 'alpha'
        log_ver = LogVer(log_name=__name__)
        log_ver.add_call_seq(name=commander_name,
                             seq=get_formatted_call_sequence())

        log_msg = 'mainline entered'
        log_ver.add_msg(log_msg=log_msg)
        logger.debug(log_msg)

        # log_msg = f'random_seed_arg: {random_seed_arg}'
        # log_ver.add_msg(log_msg=log_msg)
        # logger.debug(log_msg)

        msgs = Msgs()

        config_ver = ConfigVerifier(commander_name=commander_name,
                                    log_ver=log_ver,
                                    msgs=msgs)

        names = ['beta', 'charlie']
        scenario: list[Any] = config_ver.build_create_suite(
            names=names, commander_name=commander_name, auto_start=True)

        scenario.extend([ConfigCmd(
            cmd=ConfigCmds.ValidateConfig)])

        scenario.extend([ConfigCmd(cmd=ConfigCmds.Pause,
                                   names=[commander_name],
                                   pause_seconds=1.5)])

        scenario.extend(config_ver.build_exit_suite(names=['charlie']))
        scenario.extend(config_ver.build_join_suite(names=['charlie']))
        msg_to_send = f'send test: {config_ver.get_ptime()}'
        scenario.extend([ConfigCmd(cmd=ConfigCmds.SendMsgTimeoutTrue,
                                   names=['beta'],
                                   to_names=['charlie'],
                                   msg_to_send=msg_to_send,
                                   unreg_timeout_names=['charlie'],
                                   timeout=1.5,
                                   confirm_response=True)])
        scenario.extend([ConfigCmd(
            cmd=ConfigCmds.ConfirmResponse,
            names=['beta'],
            confirm_response_cmd=ConfigCmds.SendMsgTimeoutTrue)])

        scenario.extend([ConfigCmd(cmd=ConfigCmds.Pause,
                                   names=[commander_name],
                                   pause_seconds=2.0)])

        msg_to_send = f'send test: {config_ver.get_ptime()}'
        scenario.extend([ConfigCmd(cmd=ConfigCmds.SendMsgTimeoutFalse,
                                   names=['beta'],
                                   to_names=['charlie'],
                                   msg_to_send=msg_to_send,
                                   timeout=2.0)])
        scenario.extend([ConfigCmd(cmd=ConfigCmds.Pause,
                                   names=[commander_name],
                                   pause_seconds=1.0)])

        scenario.extend(config_ver.build_create_suite(
            names=['charlie'],
            validate_config=False))

        msg_to_send = f'send test: {config_ver.get_ptime()}'
        scenario.extend([ConfigCmd(cmd=ConfigCmds.SendMsg,
                                   names=['beta'],
                                   to_names=['charlie'],
                                   msg_to_send=msg_to_send,
                                   confirm_response=True)])

        scenario.extend([ConfigCmd(
            cmd=ConfigCmds.ConfirmResponse,
            names=['beta'],
            confirm_response_cmd=ConfigCmds.SendMsg)])

        scenario.extend([ConfigCmd(
            cmd=ConfigCmds.ValidateConfig)])

        names = list(config_ver.active_names - {commander_name})
        scenario.extend(config_ver.build_exit_suite(names=names))

        scenario.extend(config_ver.build_join_suite(names=names))

        main_driver(config_ver=config_ver,
                    scenario=scenario)
        # random.seed(random_seed_arg)

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results)
        log_ver.verify_log_results(match_results)

        logger.debug('mainline exiting')

    ####################################################################
    # test_smart_thread_msg_timeout_scenarios
    ####################################################################
    def test_recv_msg_timeout_scenarios(
            self,
            timeout_type_arg: TimeoutType,
            num_receivers_arg: int,
            num_active_senders_arg: int,
            num_send_exit_senders_arg: int,
            num_nosend_exit_senders_arg: int,
            num_unreg_senders_arg: int,
            num_reg_senders_arg: int,
            caplog: pytest.CaptureFixture[str]
    ) -> None:
        """Test meta configuration scenarios.

        Args:
            timeout_type_arg: specifies whether the recv_msg should
                be coded with timeout and whether the recv_msg should
                succeed or fail with a timeout
            num_receivers_arg: number of threads that will do the
                recv_msg
            num_active_senders_arg: number of threads that are active
                and will do the send_msg
            num_send_exit_senders_arg: number of threads that are active
                and will do the send_msg and then exit
            num_nosend_exit_senders_arg: number of threads that are
                active and will not do the send_msg and then exit
            num_unreg_senders_arg: number of threads that are
                unregistered and will be created and started and then
                do the send_msg
            num_reg_senders_arg: number of threads that are registered
                and will be started and then do the send_msg
            caplog: pytest fixture to capture log output

        """

    ####################################################################
    # test_smart_thread_msg_timeout_scenarios
    ####################################################################
    def msg_timeout_driver(
            self,
            send_or_recv: str,
            recv_args: Optional[RecvMsgParms] = None
    ) -> None:
        """Test meta configuration scenarios.

        Args:
            send_or_recv: specifies whether we are doing a send_msg
                timeout scenario or a recv_msg timeout scenario
            recv_args: provides the args to use for recv_msg timeout

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
        commander_name = 'alpha'
        log_ver = LogVer(log_name=__name__)
        log_ver.add_call_seq(name=commander_name,
                             seq=get_formatted_call_sequence())

        log_msg = 'mainline entered'
        log_ver.add_msg(log_msg=log_msg)
        logger.debug(log_msg)

        # log_msg = f'random_seed_arg: {random_seed_arg}'
        # log_ver.add_msg(log_msg=log_msg)
        # logger.debug(log_msg)
        random.seed(42)
        msgs = Msgs()

        config_ver = ConfigVerifier(commander_name=commander_name,
                                    log_ver=log_ver,
                                    msgs=msgs,
                                    max_msgs=10)

        scenario: list[Any] = []

        if send_or_recv == 'recv':
            scenario.extend(
                config_ver.build_recv_msg_timeout_suite(
                    timeout_type=recv_args.timeout_type,
                    num_receivers=recv_args.num_receivers,
                    num_active_senders=recv_args.num_active_senders,
                    num_send_exit_senders=recv_args.num_send_exit_senders,
                    num_nosend_exit_senders=recv_args.num_nosend_exit_senders,
                    num_unreg_senders=recv_args.num_unreg_senders,
                    num_reg_senders=recv_args.num_reg_senders))

        scenario.extend([ConfigCmd(
            cmd=ConfigCmds.ValidateConfig)])

        names = list(config_ver.active_names - {commander_name})
        scenario.extend(config_ver.build_exit_suite(names=names))

        scenario.extend(config_ver.build_join_suite(names=names))

        main_driver(config_ver=config_ver,
                    scenario=scenario)

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results)
        log_ver.verify_log_results(match_results)

        logger.debug('mainline exiting')

    ####################################################################
    # test_smart_thread_msg_timeout_scenarios
    ####################################################################
    def test_smart_thread_msg_timeout_scenarios(
            self,
            timeout_type_arg: TimeoutType,
            num_senders_arg: int,
            num_active_targets_arg: int,
            num_registered_targets_arg: int,
            num_timeouts_arg: tuple[int, int, int],
            caplog: pytest.CaptureFixture[str]
    ) -> None:
        """Test meta configuration scenarios.

        Args:
            num_senders_arg: number of threads to send msgs
            num_active_targets_arg: number of active threads to recv
            num_registered_targets_arg: number registered thread to
                recv
            num_timeouts_arg: number of threads to be targets that
                cause a timeout by exit, unreg, or fullq
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
        commander_name = 'alpha'
        log_ver = LogVer(log_name=__name__)
        log_ver.add_call_seq(name=commander_name,
                             seq=get_formatted_call_sequence())

        log_msg = 'mainline entered'
        log_ver.add_msg(log_msg=log_msg)
        logger.debug(log_msg)

        # log_msg = f'random_seed_arg: {random_seed_arg}'
        # log_ver.add_msg(log_msg=log_msg)
        # logger.debug(log_msg)
        random.seed(42)
        msgs = Msgs()

        config_ver = ConfigVerifier(commander_name=commander_name,
                                    log_ver=log_ver,
                                    msgs=msgs,
                                    max_msgs=10)

        scenario: list[Any] = []

        scenario.extend(
            config_ver.build_msg_timeout_suite(
                timeout_type=timeout_type_arg,
                num_senders=num_senders_arg,
                num_active_targets=num_active_targets_arg,
                num_registered_targets=num_registered_targets_arg,
                num_unreg_timeouts=num_timeouts_arg[0],
                num_exit_timeouts=num_timeouts_arg[1],
                num_full_q_timeouts=num_timeouts_arg[2]))

        scenario.extend([ConfigCmd(
            cmd=ConfigCmds.ValidateConfig)])

        names = list(config_ver.active_names - {commander_name})
        scenario.extend(config_ver.build_exit_suite(names=names))

        scenario.extend(config_ver.build_join_suite(names=names))

        main_driver(config_ver=config_ver,
                    scenario=scenario)

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results)
        log_ver.verify_log_results(match_results)

        logger.debug('mainline exiting')

    ####################################################################
    # test_smart_thread_msg_timeout_scenarios
    ####################################################################
    def test_smart_thread_msg_timeout_false_scenarios(
            self,
            num_senders_arg: int,
            num_active_targets_arg: int,
            num_registered_targets_arg: int,
            num_timeouts_arg: tuple[int, int, int],
            caplog: pytest.CaptureFixture[str]
    ) -> None:
        """Test meta configuration scenarios.

        Args:
            num_senders_arg: number of threads to send msgs
            num_active_targets_arg: number of active threads to recv
            num_registered_targets_arg: number registered thread to
                recv
            num_timeouts_arg: number of threads to be targets that
                cause a timeout by exit, unreg, or fullq
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
        commander_name = 'alpha'
        log_ver = LogVer(log_name=__name__)
        log_ver.add_call_seq(name=commander_name,
                             seq=get_formatted_call_sequence())

        log_msg = 'mainline entered'
        log_ver.add_msg(log_msg=log_msg)
        logger.debug(log_msg)

        # log_msg = f'random_seed_arg: {random_seed_arg}'
        # log_ver.add_msg(log_msg=log_msg)
        # logger.debug(log_msg)
        random.seed(42)
        msgs = Msgs()

        config_ver = ConfigVerifier(commander_name=commander_name,
                                    log_ver=log_ver,
                                    msgs=msgs,
                                    max_msgs=10)

        scenario: list[Any] = []

        # scenario.extend([ConfigCmd(cmd=ConfigCmds.Pause,
        #                            names=[commander_name],
        #                            pause_seconds=1.5)])
        # scenario.extend([ConfigCmd(cmd=ConfigCmds.Pause,
        #                            names=[commander_name],
        #                            pause_seconds=1.5)])

        # f1_active_names = config_ver.active_names - {commander_name}
        # msg_names: list[str] = random.sample(f1_active_names, 2)
        # exit_name = msg_names[0]
        # sender_name = msg_names[1]
        # scenario.extend(config_ver.build_exit_suite(names=[exit_name]))
        # scenario.extend(config_ver.build_join_suite(names=[exit_name]))
        # scenario.extend([ConfigCmd(cmd=ConfigCmds.SendMsgTimeoutTrue,
        #                            names=[sender_name],
        #                            to_names=[exit_name],
        #                            timeout=1.5,
        #                            confirm_response=True)])
        # scenario.extend([ConfigCmd(
        #     cmd=ConfigCmds.ConfirmResponse,
        #     names=[sender_name],
        #     confirm_response_cmd=ConfigCmds.SendMsgTimeoutTrue)])
        scenario.extend(
            config_ver.build_msg_timeout_false_suite(
                num_senders=num_senders_arg,
                num_active_targets=num_active_targets_arg,
                num_registered_targets=num_registered_targets_arg,
                num_unreg_timeouts=num_timeouts_arg[0],
                num_exit_timeouts=num_timeouts_arg[1],
                num_full_q_timeouts=num_timeouts_arg[2]))

        # scenario.extend([ConfigCmd(cmd=ConfigCmds.Pause,
        #                            names=[commander_name],
        #                            pause_seconds=2.0)])

        # scenario.extend([ConfigCmd(cmd=ConfigCmds.SendMsgTimeoutFalse,
        #                            names=[sender_name],
        #                            to_names=[exit_name],
        #                            timeout=2.0)])
        # scenario.extend([ConfigCmd(cmd=ConfigCmds.Pause,
        #                            names=[commander_name],
        #                            pause_seconds=1.0)])
        #
        # scenario.extend(config_ver.build_create_suite(
        #     names=[exit_name],
        #     validate_config=False))
        #
        # scenario.extend([ConfigCmd(cmd=ConfigCmds.SendMsg,
        #                            names=[sender_name],
        #                            to_names=[exit_name],
        #                            confirm_response=True)])
        #
        # scenario.extend([ConfigCmd(
        #     cmd=ConfigCmds.ConfirmResponse,
        #     names=[sender_name],
        #     confirm_response_cmd=ConfigCmds.SendMsg)])

        scenario.extend([ConfigCmd(
            cmd=ConfigCmds.ValidateConfig)])

        names = list(config_ver.active_names - {commander_name})
        scenario.extend(config_ver.build_exit_suite(names=names))

        scenario.extend(config_ver.build_join_suite(names=names))

        main_driver(config_ver=config_ver,
                    scenario=scenario)

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results)
        log_ver.verify_log_results(match_results)

        logger.debug('mainline exiting')

    ####################################################################
    # test_smart_thread_meta_scenarios
    ####################################################################
    def test_smart_thread_meta_scenarios3(
            self,
            build_config_arg: tuple[int, int, int],
            build_config2_arg: tuple[int, int, int],
            caplog: pytest.CaptureFixture[str]
    ) -> None:
        """Test meta configuration scenarios.

        Args:
            build_config_arg: determines the config to build
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
        commander_name = 'alpha'
        log_ver = LogVer(log_name=__name__)
        log_ver.add_call_seq(name=commander_name,
                             seq=get_formatted_call_sequence())

        log_msg = 'mainline entered'
        log_ver.add_msg(log_msg=log_msg)
        logger.debug(log_msg)

        msgs = Msgs()

        config_ver = ConfigVerifier(commander_name=commander_name,
                                    log_ver=log_ver,
                                    msgs=msgs)

        scenario: list[Any] = config_ver.build_config(
            num_registered=build_config_arg[0],
            num_active=build_config_arg[1],
            num_stopped=build_config_arg[2])

        scenario.extend(config_ver.build_config(
            num_registered=build_config2_arg[0],
            num_active=build_config2_arg[1],
            num_stopped=build_config2_arg[2]))

        exit_names = list(config_ver.active_names - {commander_name})
        scenario.extend(config_ver.build_exit_suite(names=exit_names))
        scenario.extend(config_ver.build_join_suite(names=exit_names))

        scenario.extend([ConfigCmd(
            cmd=ConfigCmds.ValidateConfig)])

        main_driver(config_ver=config_ver,
                    scenario=scenario)

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results)
        log_ver.verify_log_results(match_results)

        logger.debug('mainline exiting')

    ####################################################################
    # test_smart_thread_scenarios
    ####################################################################
    def test_smart_thread_random_scenarios(
            self,
            random_seed_arg: int,
            caplog: pytest.CaptureFixture[str]
    ) -> None:
        """Test meta configuration scenarios.

        Args:
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

        random.seed(random_seed_arg)
        num_threads = random.randint(2, 8)

        log_msg = (f'random_seed_arg: {random_seed_arg}, '
                   f'num_threads: {num_threads}')
        log_ver.add_msg(log_msg=log_msg)
        logger.debug(log_msg)

        msgs = Msgs()

        config_ver = ConfigVerifier(log_ver=log_ver,
                                    msgs=msgs)

        f1_names = list(config_ver.f1_thread_names.keys())

        f1_names_to_use = random.sample(f1_names, num_threads)

        names = ['alpha'] + f1_names_to_use

        scenario: list[Any] = config_ver.build_create_suite(names=names)

        num_msg_names = random.randint(2, num_threads)
        num_to_names = random.randint(1, num_msg_names-1)
        from_msg_names = random.sample(f1_names_to_use, num_msg_names)
        to_names_selection = ['alpha'] + from_msg_names
        to_names = random.sample(to_names_selection, num_to_names)
        for to_name in to_names:
            if to_name == 'alpha':
                continue
            from_msg_names.remove(to_name)

        scenario.extend(config_ver.build_msg_suite(
            from_names=from_msg_names,
            to_names=to_names))

        scenario.extend(config_ver.build_exit_suite(
            names=f1_names_to_use))
        scenario.extend(config_ver.build_join_suite(
            names=f1_names_to_use))

        main_driver(main_name='alpha',
                    config_ver=config_ver,
                    scenario=scenario)
        # random.seed(random_seed_arg)

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

                cmd_msg = f1_config_ver.msgs.get_msg(f1_name, timeout=None)

                if cmd_msg == 'send_to_alpha':
                    ####################################################
                    # send msg to alpha
                    ####################################################
                    f1_config_ver.inc_ops_count(['alpha'], f1_name)
                    f1_config_ver.f1_threads[f1_name].send_msg(
                        targets='alpha', msg=cmd_msg)

                    log_msg_f1 = f'{f1_name} sent message to alpha'
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

        # num_threads = 1  random.randint(1, 3)

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
                config_ver.commander_thread.join(targets=thread_name)
                copy_reg_deque = (
                    config_ver.commander_thread.time_last_registry_update.copy())
                copy_pair_deque = (
                    config_ver.commander_thread.time_last_pair_array_update.copy())
                copy_join_names = config_ver.commander_thread.join_names.copy()
                config_ver.del_thread(
                    name='alpha',
                    remotes=[thread_name],
                    reg_update_times=copy_reg_deque,
                    pair_array_update_times=copy_pair_deque,
                    process_names=copy_join_names,
                    process='join')
                joined_names.append(thread_name)
                num_joins += 1

            log_msg = f'mainline alpha received msg from {thread_name}'
            log_ver.add_msg(log_level=logging.DEBUG,
                            log_msg=log_msg)
            logger.debug(log_msg)

            config_ver.commander_thread.recv_msg(remote=thread_name, timeout=3)
            copy_pair_deque = (
                config_ver.commander_thread.time_last_pair_array_update.copy())
            config_ver.dec_ops_count('alpha', thread_name, copy_pair_deque)

            log_msg = f'alpha received msg from {thread_name}'
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
            config_ver.commander_thread.join(targets=thread_name)
            copy_reg_deque = (
                config_ver.commander_thread.time_last_registry_update.copy())
            copy_pair_deque = (
                config_ver.commander_thread.time_last_pair_array_update.copy())
            copy_join_names = config_ver.commander_thread.join_names.copy()
            config_ver.del_thread(
                name='alpha',
                remotes=[thread_name],
                reg_update_times=copy_reg_deque,
                pair_array_update_times=copy_pair_deque,
                process_names=copy_join_names,
                process='join')

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
            config_ver.commander_thread.join(targets='beta',
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
        config_ver.commander_thread.join(targets='beta',
                                     timeout=2)
        copy_reg_deque = (
            config_ver.commander_thread.time_last_registry_update
            .copy())
        copy_pair_deque = (
            config_ver.commander_thread.time_last_pair_array_update
            .copy())
        copy_join_names = config_ver.commander_thread.join_names.copy()
        config_ver.del_thread(
            name='alpha',
            remotes=config_cmd.names,
            reg_update_times=copy_reg_deque,
            pair_array_update_times=copy_pair_deque,
            process_names=copy_join_names,
            process='join')

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
#             log_msg_f1 = f'beta sent message to alpha'
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
#             # log_msg_f1 = 'beta received msg from alpha'
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
#             # log_msg_f1 = 'beta received msg from alpha'
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
#             # log_msg_f1 = 'beta received msg from alpha'
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
#         log_msg = 'mainline alpha received msg from beta'
#         log_ver.add_msg(log_level=logging.DEBUG,
#                         log_msg=log_msg)
#         logger.debug(log_msg)
#
#         alpha_thread.recv_msg(remote='beta', timeout=3)
#
#         log_msg = f'alpha received msg from beta'
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
