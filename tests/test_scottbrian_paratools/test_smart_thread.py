"""test_smart_thread.py module."""

########################################################################
# Standard Library
########################################################################
from abc import ABC, abstractmethod
from collections import deque, defaultdict
from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto
from itertools import combinations
import logging
import random
import re
from sys import _getframe
import time
from typing import (Any, Callable, cast, Type, TypeAlias, TYPE_CHECKING,
                    Optional, Union)
import threading

########################################################################
# Third Party
########################################################################
import pytest
from scottbrian_utils.msgs import Msgs
from scottbrian_utils.log_verifier import LogVer
from scottbrian_utils.diag_msg import (get_formatted_call_sequence,
                                       get_caller_info)

########################################################################
# Local
########################################################################
import scottbrian_paratools.smart_thread as st

logger = logging.getLogger(__name__)
logger.debug('about to start the tests')


########################################################################
# Type alias
########################################################################
IntOrFloat: TypeAlias = Union[int, float]

StrOrList: TypeAlias = Union[str, list[str]]


########################################################################
# CommanderConfig
########################################################################
class AppConfig(Enum):
    ScriptStyle = auto()
    CurrentThreadApp = auto()
    RemoteThreadApp = auto()


########################################################################
# Test settings
########################################################################
commander_config_arg_list = [AppConfig.ScriptStyle,
                             AppConfig.CurrentThreadApp,
                             AppConfig.RemoteThreadApp]


########################################################################
# timeout_type used to specify whether to use timeout on various cmds
########################################################################
class TimeoutType(Enum):
    TimeoutNone = auto()
    TimeoutFalse = auto()
    TimeoutTrue = auto()


########################################################################
# Test settings
########################################################################
timeout_type_arg_list = [TimeoutType.TimeoutNone,
                         TimeoutType.TimeoutFalse,
                         TimeoutType.TimeoutTrue]
# timeout_type_arg_list = [TimeoutType.TimeoutTrue]

########################################################################
# Test settings for test_config_build_scenarios
########################################################################
num_registered_1_arg_list = [0, 1, 2]
# num_registered_1_arg_list = [0, 0, 0]

num_active_1_arg_list = [1, 2, 3]
# num_active_1_arg_list = [2]

num_stopped_1_arg_list = [0, 1, 2]
# num_stopped_1_arg_list = [2]

num_registered_2_arg_list = [0, 1, 2]
# num_registered_2_arg_list = [2]

num_active_2_arg_list = [1, 2, 3]
# num_active_2_arg_list = [1]

num_stopped_2_arg_list = [0, 1, 2]
# num_stopped_2_arg_list = [0]

########################################################################
# Test settings for test_recv_timeout_scenarios
########################################################################
num_receivers_arg_list = [1, 2, 3]
# num_receivers_arg_list = [2]

num_active_no_delay_senders_arg_list = [0, 1, 2]
# num_active_no_delay_senders_arg_list = [0]

num_active_delay_senders_arg_list = [0, 1, 2]
# num_active_delay_senders_arg_list = [1]

num_send_exit_senders_arg_list = [0, 1, 2]
# num_send_exit_senders_arg_list = [2]

num_nosend_exit_senders_arg_list = [0, 1, 2]
# num_nosend_exit_senders_arg_list = [2]

num_unreg_senders_arg_list = [0, 1, 2]
# num_unreg_senders_arg_list = [2]

num_reg_senders_arg_list = [0, 1, 2]
# num_reg_senders_arg_list = [0]

########################################################################
# Test settings for test_send_msg_timeout_scenarios
########################################################################
num_senders_arg_list = [1, 2, 3]
# num_senders_arg_list = [2]

num_active_targets_arg_list = [0, 1, 2]
# num_active_targets_arg_list = [0]

num_registered_targets_arg_list = [0, 1, 2]
# num_registered_targets_arg_list = [0]

num_unreg_timeouts_arg_list = [0, 1, 2]
# num_unreg_timeouts_arg_list = [0]

num_exit_timeouts_arg_list = [0, 1, 2]
# num_exit_timeouts_arg_list = [1]

num_full_q_timeouts_arg_list = [0, 1, 2]
# num_full_q_timeouts_arg_list = [0]


########################################################################
# SmartThread test exceptions
########################################################################
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


class CmdTimedOut(ErrorTstSmartThread):
    """The cmd took to long."""
    pass


class FailedToFindLogMsg(ErrorTstSmartThread):
    """An expected log message was not found."""
    pass


########################################################################
# ConfigCmd
########################################################################
class ConfigCmd(ABC):
    def __init__(self,
                 cmd_runners: StrOrList):

        # The serial number, line_num, and config_ver are filled in
        # by the ConfigVerifier add_cmd method just before queueing
        # the command.
        self.serial_num: int = 0
        self.line_num: int = 0
        self.config_ver: Optional["ConfigVerifier"] = None

        # specified_args are set in each subclass
        self.specified_args: dict[str, Any] = {}

        if isinstance(cmd_runners, str):
            cmd_runners = [cmd_runners]
        self.cmd_runners = cmd_runners

        self.arg_list: list[str] = ['cmd_runners',
                                    'serial_num',
                                    'line_num']

    def __repr__(self):
        if TYPE_CHECKING:
            __class__: Type[ConfigVerifier]
        classname = self.__class__.__name__
        parms = (f'serial={self.serial_num}, '
                 f'line={self.line_num}')
        comma = ', '
        for key, item in self.specified_args.items():
            if item:  # if not None
                if key in self.arg_list:
                    if type(item) is str:
                        parms += comma + f"{key}='{item}'"
                    else:
                        parms += comma + f"{key}={item}"
                    # comma = ', '  # after first item, now need comma
            if key == 'f1_create_items':
                parms += comma + f"{key}={item}"

        return f'{classname}({parms})'

    @abstractmethod
    def run_process(self, name: str) -> None:
        """Run the command.

        Args:
            name: name of thread running the command
        """
        pass


########################################################################
# ConfirmResponse
########################################################################
class ConfirmResponse(ConfigCmd):
    def __init__(self,
                 cmd_runners: StrOrList,
                 confirm_cmd: str,
                 confirm_serial_num: int,
                 confirmers: StrOrList
                 ) -> None:
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

        self.confirm_cmd = confirm_cmd
        self.confirm_serial_num = confirm_serial_num
        if isinstance(confirmers, str):
            confirmers = [confirmers]
        self.confirmers = confirmers
        self.arg_list += ['confirm_cmd',
                          'confirm_serial_num',
                          'targets']

    def run_process(self, name: str) -> None:
        """Run the command.

        Args:
            name: name of thread running the command
        """
        start_time = time.time()
        work_confirmers = self.confirmers.copy()
        while work_confirmers:
            for name in work_confirmers:
                # If the serial number is in the completed_cmds for
                # this name then the command was completed. Remove the
                # target name and break to start looking again with one
                # less target until no targets remain.
                if (self.confirm_serial_num in
                        self.config_ver.completed_cmds[name]):
                    work_confirmers.remove(name)
                    break
            time.sleep(0.2)
            if time.time() - start_time > 60:
                raise CmdTimedOut('ConfirmResponse took too long waiting '
                                  f'for {work_confirmers} to complete '
                                  f'cmd {self.confirm_cmd} with '
                                  f'serial_num {self.serial_num}.')


########################################################################
# CreateCommanderAutoStart
########################################################################
class CreateCommanderAutoStart(ConfigCmd):
    def __init__(self,
                 cmd_runners: StrOrList,
                 commander_name: str
                 ) -> None:
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

        self.commander_name = commander_name
        self.arg_list += ['commander_name']

    def run_process(self, name: str) -> None:
        """Run the command.

        Args:
            name: name of thread running the command
        """
        self.config_ver.create_commander_thread(
            name=self.commander_name,
            auto_start=True)


########################################################################
# CreateCommanderNoStart
########################################################################
class CreateCommanderNoStart(CreateCommanderAutoStart):
    def __init__(self,
                 cmd_runners: StrOrList,
                 commander_name: str
                 ) -> None:
        super().__init__(cmd_runners=cmd_runners,
                         commander_name=commander_name)
        self.specified_args = locals()  # used for __repr__

    def run_process(self, name: str) -> None:
        """Run the command.

        Args:
            name: name of thread running the command
        """
        self.config_ver.create_commander_thread(
            name=self.commander_name,
            auto_start=False)


########################################################################
# CreateF1AutoStart
########################################################################
class CreateF1AutoStart(ConfigCmd):
    def __init__(self,
                 cmd_runners: StrOrList,
                 f1_create_items: list["F1CreateItem"],
                 ) -> None:
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

        self.f1_create_items = f1_create_items

        self.args_list = ['f1_create_items']

    def run_process(self, name: str) -> None:
        """Run the command.

        Args:
            name: name of thread running the command
        """
        for f1_item in self.f1_create_items:
            self.config_ver.create_f1_thread(
                cmd_runner=name,
                name=f1_item.name,
                target=f1_item.target_rtn,
                app_config=f1_item.app_config,
                auto_start=True)


########################################################################
# CreateF1NoStart
########################################################################
class CreateF1NoStart(CreateF1AutoStart):
    def __init__(self,
                 cmd_runners: StrOrList,
                 f1_create_items: list["F1CreateItem"],
                 ) -> None:
        super().__init__(cmd_runners=cmd_runners,
                         f1_create_items=f1_create_items)
        self.specified_args = locals()  # used for __repr__

    def run_process(self, name: str) -> None:
        """Run the command.

        Args:
            name: name of thread running the command
        """
        for f1_item in self.f1_create_items:
            self.config_ver.create_f1_thread(
                cmd_runner=name,
                name=f1_item.name,
                target=f1_item.target_rtn,
                app_config=f1_item.app_config,
                auto_start=False)


########################################################################
# ExitThread
########################################################################
class ExitThread(ConfigCmd):
    def __init__(self,
                 cmd_runners: StrOrList) -> None:
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

    def run_process(self, name: str) -> None:
        """Run the command.

        Args:
            name: name of thread running the command
        """
        self.config_ver.exit_thread(f1_name=name)


########################################################################
# Join
########################################################################
class Join(ConfigCmd):
    def __init__(self,
                 cmd_runners: StrOrList,
                 join_names: StrOrList,
                 log_msg: Optional[str] = None) -> None:
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

        if isinstance(join_names, str):
            join_names = [join_names]
        self.join_names = join_names
        self.log_msg = log_msg
        self.arg_list += ['join_names']

    def run_process(self, name: str) -> None:
        """Run the command.

        Args:
            name: name of thread running the command
        """
        self.config_ver.handle_join(cmd_runner=name,
                                    join_names=self.join_names,
                                    log_msg=self.log_msg)


########################################################################
# JoinTimeoutFalse
########################################################################
class JoinTimeoutFalse(Join):
    def __init__(self,
                 cmd_runners: StrOrList,
                 join_names: StrOrList,
                 timeout: IntOrFloat,
                 log_msg: Optional[str] = None) -> None:
        super().__init__(cmd_runners=cmd_runners,
                         join_names=join_names,
                         log_msg=log_msg)
        self.specified_args = locals()  # used for __repr__

        self.timeout = timeout
        self.arg_list = ['timeout']

    def run_process(self, name: str) -> None:
        """Run the command.

        Args:
            name: name of thread running the command
        """
        self.config_ver.handle_join_tof(cmd_runner=name,
                                        join_names=self.join_names,
                                        timeout=self.timeout,
                                        log_msg=self.log_msg)


########################################################################
# JoinTimeoutTrue
########################################################################
class JoinTimeoutTrue(JoinTimeoutFalse):
    def __init__(self,
                 cmd_runners: StrOrList,
                 join_names: StrOrList,
                 timeout: IntOrFloat,
                 timeout_names: StrOrList,
                 log_msg: Optional[str] = None) -> None:
        super().__init__(cmd_runners=cmd_runners,
                         join_names=join_names,
                         timeout=timeout,
                         log_msg=log_msg)
        self.specified_args = locals()  # used for __repr__

        if isinstance(timeout_names, str):
            timeout_names = [timeout_names]
        self.timeout_names = timeout_names
        self.arg_list += ['timeout_names']

    def run_process(self, name: str) -> None:
        """Run the command.

        Args:
            name: name of thread running the command
        """
        if self.timeout_names:
            self.config_ver.handle_join_tot(cmd_runner=name,
                                            join_names=self.join_names,
                                            timeout=self.timeout,
                                            timeout_names=self.timeout_names,
                                            log_msg=self.log_msg)
        else:
            self.config_ver.handle_join_tof(cmd_runner=name,
                                            join_names=self.join_names,
                                            timeout=self.timeout,
                                            log_msg=self.log_msg)


########################################################################
# Pause
########################################################################
class Pause(ConfigCmd):
    def __init__(self,
                 cmd_runners: StrOrList,
                 pause_seconds: IntOrFloat) -> None:
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

        self.pause_seconds = pause_seconds

        self.arg_list += ['pause_seconds']

    def run_process(self, name: str) -> None:
        """Run the command.

        Args:
            name: name of thread running the command
        """
        time.sleep(self.pause_seconds)

########################################################################
# RecvMsg
########################################################################
class RecvMsg(ConfigCmd):
    def __init__(self,
                 cmd_runners: StrOrList,
                 senders: StrOrList,
                 exp_msgs: dict[str, Any],
                 del_deferred: Optional[StrOrList] = None,
                 log_msg: Optional[str] = None) -> None:
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

        if isinstance(senders, str):
            senders = [senders]
        self.senders = senders
        self.exp_msgs = exp_msgs

        if isinstance(del_deferred, str):
            del_deferred = [del_deferred]
        self.del_deferred = del_deferred
        self.log_msg = log_msg

        self.arg_list += ['senders']

    def run_process(self, name: str) -> None:
        """Run the command.

        Args:
            name: name of thread running the command
        """
        self.config_ver.handle_recv_msg(cmd_runner=name,
                                        senders=self.senders,
                                        exp_msgs=self.exp_msgs,
                                        del_deferred=self.del_deferred,
                                        log_msg=self.log_msg)


########################################################################
# RecvMsgTimeoutFalse
########################################################################
class RecvMsgTimeoutFalse(RecvMsg):
    def __init__(self,
                 cmd_runners: StrOrList,
                 senders: StrOrList,
                 exp_msgs: dict[str, Any],
                 timeout: IntOrFloat,
                 del_deferred: Optional[StrOrList] = None,
                 log_msg: Optional[str] = None) -> None:
        super().__init__(cmd_runners=cmd_runners,
                         senders=senders,
                         exp_msgs=exp_msgs,
                         del_deferred=del_deferred,
                         log_msg=log_msg)
        self.specified_args = locals()  # used for __repr__

        self.timeout = timeout

        self.arg_list += ['timeout']

    def run_process(self, name: str) -> None:
        """Run the command.

        Args:
            name: name of thread running the command
        """
        self.config_ver.handle_recv_msg_tof(
            cmd_runner=name,
            senders=self.senders,
            exp_msgs=self.exp_msgs,
            timeout=self.timeout,
            del_deferred=self.del_deferred,
            log_msg=self.log_msg)


########################################################################
# RecvMsgTimeoutTrue
########################################################################
class RecvMsgTimeoutTrue(RecvMsgTimeoutFalse):
    def __init__(self,
                 cmd_runners: StrOrList,
                 senders: StrOrList,
                 exp_msgs: dict[str, Any],
                 timeout: IntOrFloat,
                 timeout_names: StrOrList,
                 del_deferred: Optional[StrOrList] = None,
                 log_msg: Optional[str] = None) -> None:
        super().__init__(cmd_runners=cmd_runners,
                         senders=senders,
                         exp_msgs=exp_msgs,
                         timeout=timeout,
                         del_deferred=del_deferred,
                         log_msg=log_msg)
        self.specified_args = locals()  # used for __repr__

        if isinstance(timeout_names, str):
            timeout_names = [timeout_names]
        self.timeout_names = timeout_names

        self.arg_list += ['timeout_names']

    def run_process(self, name: str) -> None:
        """Run the command.

        Args:
            name: name of thread running the command
        """
        self.config_ver.handle_recv_msg_tot(
            cmd_runner=name,
            senders=self.senders,
            exp_msgs=self.exp_msgs,
            timeout=self.timeout,
            timeout_names=self.timeout_names,
            del_deferred=self.del_deferred,
            log_msg=self.log_msg)


########################################################################
# SendMsg
########################################################################
class SendMsg(ConfigCmd):
    def __init__(self,
                 cmd_runners: StrOrList,
                 receivers: StrOrList,
                 msgs_to_send: dict[str, Any],
                 log_msg: Optional[str] = None) -> None:
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

        if isinstance(receivers, str):
            receivers = [receivers]
        self.receivers = receivers
        self.msgs_to_send = msgs_to_send
        self.log_msg = log_msg

        self.arg_list += ['receivers']

    def run_process(self, name: str) -> None:
        """Run the command.

        Args:
            name: name of thread running the command
        """
        self.config_ver.handle_send_msg(
            cmd_runner=name,
            receivers=self.receivers,
            msg_to_send=self.msgs_to_send[name],
            log_msg=self.log_msg)


########################################################################
# SendMsgTimeoutFalse
########################################################################
class SendMsgTimeoutFalse(SendMsg):
    def __init__(self,
                 cmd_runners: StrOrList,
                 receivers: StrOrList,
                 msgs_to_send: dict[str, Any],
                 timeout: IntOrFloat,
                 # unreg_timeout_names: StrOrList,
                 # fullq_timeout_names: StrOrList,
                 log_msg: Optional[str] = None) -> None:
        super().__init__(
            cmd_runners=cmd_runners,
            receivers=receivers,
            msgs_to_send=msgs_to_send,
            log_msg=log_msg)
        self.specified_args = locals()  # used for __repr__

        self.timeout = timeout

        self.arg_list += ['timeout']

    def run_process(self, name: str) -> None:
        """Run the command.

        Args:
            name: name of thread running the command
        """
        self.config_ver.handle_send_msg_tof(
            cmd_runner=name,
            receivers=self.receivers,
            msg_to_send=self.msgs_to_send[name],
            timeout=self.timeout,
            log_msg=self.log_msg)


########################################################################
# SendMsgTimeoutTrue
########################################################################
class SendMsgTimeoutTrue(SendMsgTimeoutFalse):
    def __init__(self,
                 cmd_runners: StrOrList,
                 receivers: StrOrList,
                 msgs_to_send: dict[str, Any],
                 timeout: IntOrFloat,
                 unreg_timeout_names: StrOrList,
                 fullq_timeout_names: StrOrList,
                 log_msg: Optional[str] = None) -> None:
        super().__init__(
            cmd_runners=cmd_runners,
            receivers=receivers,
            msgs_to_send=msgs_to_send,
            timeout=timeout,
            # unreg_timeout_names=unreg_timeout_names,
            # fullq_timeout_names=fullq_timeout_names,
            log_msg=log_msg)
        self.specified_args = locals()  # used for __repr__

        self.arg_list += ['unreg_timeout_names',
                          'fullq_timeout_names']

        if isinstance(unreg_timeout_names, str):
            unreg_timeout_names = [unreg_timeout_names]
        self.unreg_timeout_names = unreg_timeout_names

        if isinstance(fullq_timeout_names, str):
            fullq_timeout_names = [fullq_timeout_names]
        self.fullq_timeout_names = fullq_timeout_names

    def run_process(self, name: str) -> None:
        """Run the command.

        Args:
            name: name of thread running the command
        """
        self.config_ver.handle_send_msg_tot(
            cmd_runner=name,
            receivers=self.receivers,
            msg_to_send=self.msgs_to_send[name],
            timeout=self.timeout,
            unreg_timeout_names=self.unreg_timeout_names,
            fullq_timeout_names=self.fullq_timeout_names,
            log_msg=self.log_msg)


########################################################################
# StartThread
########################################################################
class StartThread(ConfigCmd):
    def __init__(self,
                 cmd_runners: StrOrList,
                 start_names: StrOrList) -> None:
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

        if isinstance(start_names, str):
            start_names = [start_names]
        self.start_names = start_names

        self.arg_list += ['start_names']

    def run_process(self, name: str) -> None:
        """Run the command.

        Args:
            name: name of thread running the command
        """
        self.config_ver.start_thread(start_names=self.start_names)


########################################################################
# StopThread
########################################################################
class StopThread(ConfigCmd):
    def __init__(self,
                 cmd_runners: StrOrList,
                 stop_names: StrOrList) -> None:
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

        if isinstance(stop_names, str):
            stop_names = [stop_names]
        self.stop_names = stop_names

        self.arg_list += ['stop_names']

    def run_process(self, name: str) -> None:
        """Run the command.

        Args:
            name: name of thread running the command
        """
        self.config_ver.stop_thread(cmd_runner=name,
                                    stop_names=self.stop_names)


########################################################################
# Unregister
########################################################################
class Unregister(ConfigCmd):
    def __init__(self,
                 cmd_runners: StrOrList,
                 unregister_targets: StrOrList) -> None:
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

        if isinstance(unregister_targets, str):
            unregister_targets = [unregister_targets]
        self.unregister_targets = unregister_targets

        self.arg_list += ['unregister_targets']

    def run_process(self, name: str) -> None:
        """Run the command.

        Args:
            name: name of thread running the command
        """
        self.config_ver.unregister_threads(
            cmd_runner=name,
            unregister_targets=self.unregister_targets)


########################################################################
# ValidateConfig
########################################################################
class ValidateConfig(ConfigCmd):
    def __init__(self,
                 cmd_runners: StrOrList) -> None:
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

    def run_process(self, name: str) -> None:
        """Run the command.

        Args:
            name: name of thread running the command
        """
        self.config_ver.validate_config()


########################################################################
# VerifyAlive
########################################################################
class VerifyAlive(ConfigCmd):
    def __init__(self,
                 cmd_runners: StrOrList,
                 exp_alive_names: StrOrList) -> None:
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__


        if isinstance(exp_alive_names, str):
            exp_alive_names = [exp_alive_names]
        self.exp_alive_names = exp_alive_names

        self.arg_list += ['exp_alive_names']

    def run_process(self, name: str) -> None:
        """Run the command.

        Args:
            name: name of thread running the command
        """
        self.config_ver.verify_is_alive(names=self.exp_alive_names)


########################################################################
# VerifyAliveNot
########################################################################
class VerifyAliveNot(ConfigCmd):
    def __init__(self,
                 cmd_runners: StrOrList,
                 exp_not_alive_names: StrOrList) -> None:
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

        if isinstance(exp_not_alive_names, str):
            exp_not_alive_names = [exp_not_alive_names]
        self.exp_not_alive_names = exp_not_alive_names

        self.arg_list += ['exp_not_alive_names']

    def run_process(self, name: str) -> None:
        """Run the command.

        Args:
            name: name of thread running the command
        """
        self.config_ver.verify_is_alive_not(names=self.exp_not_alive_names)


########################################################################
# VerifyActive
########################################################################
class VerifyActive(ConfigCmd):
    def __init__(self,
                 cmd_runners: StrOrList,
                 exp_active_names: StrOrList) -> None:
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

        if isinstance(exp_active_names, str):
            exp_active_names = [exp_active_names]
        self.exp_active_names = exp_active_names

        self.arg_list += ['exp_active_names']

    def run_process(self, name: str) -> None:
        """Run the command.

        Args:
            name: name of thread running the command
        """
        self.config_ver.verify_is_active(
            cmd_runner=name,
            exp_active_names=self.exp_active_names)


########################################################################
# VerifyCounts
########################################################################
class VerifyCounts(ConfigCmd):
    def __init__(self,
                 cmd_runners: StrOrList,
                 exp_num_registered: int,
                 exp_num_active: int,
                 exp_num_stopped: int) -> None:
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

        self.exp_num_registered = exp_num_registered
        self.exp_num_active = exp_num_active
        self.exp_num_stopped = exp_num_stopped

        self.arg_list += ['exp_num_registered',
                          'exp_num_active',
                          'exp_num_stopped']

    def run_process(self, name: str) -> None:
        """Run the command.

        Args:
            name: name of thread running the command
        """
        self.config_ver.verify_counts(num_registered=self.exp_num_registered,
                                      num_active=self.exp_num_active,
                                      num_stopped=self.exp_num_stopped)


########################################################################
# VerifyInRegistry
########################################################################
class VerifyInRegistry(ConfigCmd):
    def __init__(self,
                 cmd_runners: StrOrList,
                 exp_in_registry_names: StrOrList) -> None:
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

        if isinstance(exp_in_registry_names, str):
            exp_in_registry_names = [exp_in_registry_names]
        self.exp_in_registry_names = exp_in_registry_names

        self.arg_list += ['exp_in_registry_names']

    def run_process(self, name: str) -> None:
        """Run the command.

        Args:
            name: name of thread running the command
        """
        self.config_ver.verify_in_registry(
            cmd_runner=name,
            exp_in_registry_names=self.exp_in_registry_names)


########################################################################
# VerifyInRegistryNot
########################################################################
class VerifyInRegistryNot(ConfigCmd):
    def __init__(self,
                 cmd_runners: StrOrList,
                 exp_not_in_registry_names: StrOrList) -> None:
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

        if isinstance(exp_not_in_registry_names, str):
            exp_not_in_registry_names = [exp_not_in_registry_names]
        self.exp_not_in_registry_names = exp_not_in_registry_names

        self.arg_list += ['exp_not_in_registry_names']

    def run_process(self, name: str) -> None:
        """Run the command.

        Args:
            name: name of thread running the command
        """
        self.config_ver.verify_in_registry_not(
            cmd_runner=name,
            exp_not_in_registry_names=self.exp_not_in_registry_names)


########################################################################
# VerifyRegistered
########################################################################
class VerifyRegistered(ConfigCmd):
    def __init__(self,
                 cmd_runners: StrOrList,
                 exp_registered_names: StrOrList) -> None:
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

        if isinstance(exp_registered_names, str):
            exp_registered_names = [exp_registered_names]
        self.exp_registered_names = exp_registered_names

        self.arg_list += ['exp_registered_names']

    def run_process(self, name: str) -> None:
        """Run the command.

        Args:
            name: name of thread running the command
        """
        self.config_ver.verify_is_registered(
            cmd_runner=name,
            exp_registered_names=self.exp_registered_names)


########################################################################
# VerifyPaired
########################################################################
class VerifyPaired(ConfigCmd):
    def __init__(self,
                 cmd_runners: StrOrList,
                 exp_paired_names: StrOrList) -> None:
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

        if isinstance(exp_paired_names, str):
            exp_paired_names = [exp_paired_names]
        self.exp_paired_names = exp_paired_names

        self.arg_list += ['exp_paired_names']

    def run_process(self, name: str) -> None:
        """Run the command.

        Args:
            name: name of thread running the command
        """
        self.config_ver.verify_paired(
            cmd_runner=name,
            exp_paired_names=self.exp_paired_names)


########################################################################
# VerifyPairedHalf
########################################################################
class VerifyPairedHalf(ConfigCmd):
    def __init__(self,
                 cmd_runners: StrOrList,
                 pair_names: list[str],
                 exp_half_paired_names: StrOrList) -> None:
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

        self.pair_names = pair_names
        if isinstance(exp_half_paired_names, str):
            exp_half_paired_names = [exp_half_paired_names]
        self.exp_half_paired_names = exp_half_paired_names

        self.arg_list += ['pair_names',
                          'exp_half_paired_names']

    def run_process(self, name: str) -> None:
        """Run the command.

        Args:
            name: name of thread running the command
        """
        self.config_ver.verify_paired_half(
            cmd_runner=name,
            pair_names=self.pair_names,
            half_paired_names=self.exp_half_paired_names)


########################################################################
# VerifyPairedNot
########################################################################
class VerifyPairedNot(ConfigCmd):
    def __init__(self,
                 cmd_runners: StrOrList,
                 exp_not_paired_names: StrOrList) -> None:
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

        if isinstance(exp_not_paired_names, str):
            exp_not_paired_names = [exp_not_paired_names]
        self.exp_not_paired_names = exp_not_paired_names

        self.arg_list += ['exp_not_paired_names']

    def run_process(self, name: str) -> None:
        """Run the command.

        Args:
            name: name of thread running the command
        """
        self.config_ver.verify_paired_not(
            cmd_runner=name,
            exp_not_paired_names=self.exp_not_paired_names)


########################################################################
# VerifyStatus
########################################################################
class VerifyStatus(ConfigCmd):
    def __init__(self,
                 cmd_runners: StrOrList,
                 check_status_names: StrOrList,
                 expected_status: st.ThreadStatus
                 ) -> None:
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

        if isinstance(check_status_names, str):
            check_status_names = [check_status_names]
        self.check_status_names = check_status_names

        self.expected_status = expected_status

        self.arg_list += ['check_status_names',
                          'expected_status']

    def run_process(self, name: str) -> None:
        """Run the command.

        Args:
            name: name of thread running the command
        """
        self.config_ver.verify_status(
            cmd_runner=name,
            check_status_names=self.check_status_names,
            expected_status=self.expected_status)


########################################################################
# WaitForRecvTimeouts
########################################################################
class WaitForRecvTimeouts(ConfigCmd):
    def __init__(self,
                 cmd_runners: StrOrList) -> None:
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

    def run_process(self, name: str) -> None:
        """Run the command.

        Args:
            name: name of thread running the command
        """
        self.config_ver.wait_for_recv_msg_timeouts(cmd_runner=name)


########################################################################
# WaitForSendTimeouts
########################################################################
class WaitForSendTimeouts(ConfigCmd):
    def __init__(self,
                 cmd_runners: StrOrList,
                 sender_names: StrOrList,
                 unreg_names: StrOrList,
                 fullq_names: StrOrList
                 ) -> None:
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

        if isinstance(sender_names, str):
            sender_names = [sender_names]
        self.sender_names = sender_names

        if isinstance(unreg_names, str):
            unreg_names = [unreg_names]
        self.unreg_names = unreg_names

        if isinstance(fullq_names, str):
            fullq_names = [fullq_names]
        self.fullq_names = fullq_names

        self.arg_list += ['sender_names',
                          'unreg_names',
                          'fullq_names']

    def run_process(self, name: str) -> None:
        """Run the command.

        Args:
            name: name of thread running the command
        """
        self.config_ver.wait_for_send_msg_timeouts(
            cmd_runner=name,
            sender_names=self.sender_names,
            unreg_names=self.unreg_names,
            fullq_names=self.fullq_names)


# ###############################################################################
# # Cmd Constants
# ###############################################################################
# Cmd = Enum('Cmd', 'Wait Wait_TOT Wait_TOF Wait_Clear Resume Sync Exit '
#                   'Next_Action')
#
# ###############################################################################
# # Action
# ###############################################################################
# Action = Enum('Action',
#               'MainWait '
#               'MainSync MainSync_TOT MainSync_TOF '
#               'MainResume MainResume_TOT MainResume_TOF '
#               'ThreadWait ThreadWait_TOT ThreadWait_TOF '
#               'ThreadResume ')
#
# ###############################################################################
# # action_arg fixtures
# ###############################################################################
# action_arg_list = [Action.MainWait,
#                    Action.MainSync,
#                    Action.MainSync_TOT,
#                    Action.MainSync_TOF,
#                    Action.MainResume,
#                    Action.MainResume_TOT,
#                    Action.MainResume_TOF,
#                    Action.ThreadWait,
#                    Action.ThreadWait_TOT,
#                    Action.ThreadWait_TOF,
#                    Action.ThreadResume]
#
# action_arg_list1 = [Action.MainWait
#                     # Action.MainResume,
#                     # Action.MainResume_TOT,
#                     # Action.MainResume_TOF,
#                     # Action.ThreadWait,
#                     # Action.ThreadWait_TOT,
#                     # Action.ThreadWait_TOF,
#                     # Action.ThreadResume
#                     ]
#
# action_arg_list2 = [  # Action.MainWait,
#                     # Action.MainResume,
#                     # Action.MainResume_TOT,
#                     Action.MainResume_TOF
#                     # Action.ThreadWait,
#                     # Action.ThreadWait_TOT,
#                     # Action.ThreadWait_TOF,
#                     # Action.ThreadResume
#                     ]
#
#
# @pytest.fixture(params=action_arg_list)  # type: ignore
# def action_arg1(request: Any) -> Any:
#     """Using different reply messages.
#
#     Args:
#         request: special fixture that returns the fixture params
#
#     Returns:
#         The params values are returned one at a time
#     """
#     return request.param
#
#
# @pytest.fixture(params=action_arg_list)  # type: ignore
# def action_arg2(request: Any) -> Any:
#     """Using different reply messages.
#
#     Args:
#         request: special fixture that returns the fixture params
#
#     Returns:
#         The params values are returned one at a time
#     """
#     return request.param


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
# num_registered_1_arg
###############################################################################
@pytest.fixture(params=num_registered_1_arg_list)  # type: ignore
def num_registered_1_arg(request: Any) -> int:
    """Number of threads to configur as registered.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


###############################################################################
# num_active_1_arg
###############################################################################
@pytest.fixture(params=num_active_1_arg_list)  # type: ignore
def num_active_1_arg(request: Any) -> int:
    """Number of threads to configur as registered.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


###############################################################################
# num_stopped_1_arg
###############################################################################
@pytest.fixture(params=num_stopped_1_arg_list)  # type: ignore
def num_stopped_1_arg(request: Any) -> int:
    """Number of threads to configur as registered.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


###############################################################################
# num_registered_2_arg
###############################################################################
@pytest.fixture(params=num_registered_2_arg_list)  # type: ignore
def num_registered_2_arg(request: Any) -> int:
    """Number of threads to configur as registered.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


###############################################################################
# num_active_2_arg
###############################################################################
@pytest.fixture(params=num_active_2_arg_list)  # type: ignore
def num_active_2_arg(request: Any) -> int:
    """Number of threads to configur as registered.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


###############################################################################
# num_stopped_2_arg
###############################################################################
@pytest.fixture(params=num_stopped_2_arg_list)  # type: ignore
def num_stopped_2_arg(request: Any) -> int:
    """Number of threads to configur as registered.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


###############################################################################
# commander_config_arg
###############################################################################
@pytest.fixture(params=commander_config_arg_list)  # type: ignore
def commander_config_arg(request: Any) -> AppConfig:
    """Type of send_msg timeout to test.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(AppConfig, request.param)


###############################################################################
# timeout_type_arg
###############################################################################
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
# num_receivers_arg
###############################################################################
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
# num_active_no_delay_senders_arg
###############################################################################
@pytest.fixture(params=num_active_no_delay_senders_arg_list)  # type: ignore
def num_active_no_delay_senders_arg(request: Any) -> int:
    """Number of threads to send msg immediately.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)

###############################################################################
# num_active_delay_senders_arg
###############################################################################
@pytest.fixture(params=num_active_delay_senders_arg_list)  # type: ignore
def num_active_delay_senders_arg(request: Any) -> int:
    """Number of threads to send msg after a delay.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


###############################################################################
# num_senders_exit_before_arg
###############################################################################
@pytest.fixture(params=num_send_exit_senders_arg_list)  # type: ignore
def num_send_exit_senders_arg(request: Any) -> int:
    """Number of threads to send msg and then exit.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


########################################################################
# num_senders_exit_before_arg
########################################################################
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
# num_active_targets_arg
###############################################################################
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
# num_exit_timeouts_arg
########################################################################
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
# num_active_no_target_arg
###############################################################################
num_active_no_target_arg_list = [1, 2, 3]


@pytest.fixture(params=num_active_no_target_arg_list)  # type: ignore
def num_active_no_target_arg(request: Any) -> int:
    """Which threads should exit before alpha recvs msg.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


###############################################################################
# num_no_delay_exit_arg
###############################################################################
num_no_delay_exit_arg_list = [0, 1, 2]


@pytest.fixture(params=num_no_delay_exit_arg_list)  # type: ignore
def num_no_delay_exit_arg(request: Any) -> int:
    """Which threads should exit before alpha recvs msg.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


###############################################################################
# num_delay_exit_arg
###############################################################################
num_delay_exit_arg_list = [0, 1, 2]


@pytest.fixture(params=num_delay_exit_arg_list)  # type: ignore
def num_delay_exit_arg(request: Any) -> int:
    """Which threads should exit before alpha recvs msg.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


###############################################################################
# num_no_delay_unreg_arg
###############################################################################
num_no_delay_unreg_arg_list = [0, 1, 2]


@pytest.fixture(params=num_no_delay_unreg_arg_list)  # type: ignore
def num_no_delay_unreg_arg(request: Any) -> int:
    """Which threads should exit before alpha recvs msg.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


###############################################################################
# num_delay_unreg_arg
###############################################################################
num_delay_unreg_arg_list = [0, 1, 2]


@pytest.fixture(params=num_delay_unreg_arg_list)  # type: ignore
def num_delay_unreg_arg(request: Any) -> int:
    """Which threads should exit before alpha recvs msg.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


###############################################################################
# num_no_delay_reg_arg
###############################################################################
num_no_delay_reg_arg_list = [0, 1, 2]


@pytest.fixture(params=num_no_delay_reg_arg_list)  # type: ignore
def num_no_delay_reg_arg(request: Any) -> int:
    """Which threads should exit before alpha recvs msg.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


###############################################################################
# num_delay_reg_arg
###############################################################################
num_delay_reg_arg_list = [0, 1, 2]


@pytest.fixture(params=num_delay_reg_arg_list)  # type: ignore
def num_delay_reg_arg(request: Any) -> int:
    """Which threads should exit before alpha recvs msg.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


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
# F1CreateItem
########################################################################
@dataclass
class F1CreateItem:
    """Class that has infor for f1 create."""
    name: str
    auto_start: bool
    target_rtn: Callable[..., Any]
    app_config: AppConfig = AppConfig.ScriptStyle


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
    found_del_pairs: dict[tuple[str, str, str], int]
    num_refresh: int = 0

    # expected_last_reg_updates: deque


@dataclass
class ThreadPairStatus:
    """Class that keeps pair status."""
    pending_ops_count: int
    # expected_last_reg_updates: deque


@dataclass
class MonitorAddItem:
    """Class keeps track of threads to add, start, delete, unreg."""
    cmd_runner: str
    thread_alive: bool
    auto_start: bool
    expected_status: st.ThreadStatus
    add_event: threading.Event


@dataclass
class RecvEventItem:
    """Class keeps track of threads to add, start, delete, unreg."""
    recv_event: threading.Event
    deferred_post_needed: bool
    senders: list[str]


@dataclass
class MonitorItem:
    """Class keeps track of threads to add, start, delete, unreg."""
    cmd_runner: str
    target_name: str
    process_name: str
    # del_event: threading.Event


hour_match = '([01][0-9]|20|21|22|23)'
min_sec_match = '[0-5][0-9]'
micro_sec_match = '[0-9]{6,6}'
time_match = (f'{hour_match}:{min_sec_match}:{min_sec_match}\.'
              f'{micro_sec_match}')


########################################################################
# LogSearchItem
########################################################################
class LogSearchItem(ABC):
    """Input to search log msgs."""
    def __init__(self,
                 search_str: str,
                 config_ver: "ConfigVerifier") -> None:
        """Initialize the LogItem.

        Args:
            search_str: regex style search string
            config_ver: configuration verifier
        """
        self.search_pattern = re.compile(search_str)
        self.config_ver: "ConfigVerifier" = config_ver

    @abstractmethod
    def get_found_log_item(self,
                           found_log_msg: str,
                           found_log_idx: int) -> "LogFoundItem":
        """Return a found log item.

        Args:
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found

        Returns:
            LogFoundItem containing found message and index
        """
        pass


########################################################################
# EnterRpaLogSearchItem
########################################################################
class EnterRpaLogSearchItem(LogSearchItem):
    """Input to search log msgs."""

    def __init__(self,
                 config_ver: "ConfigVerifier") -> None:
        """Initialize the LogItem.

        Args:
            config_ver: configuration verifier
        """
        super().__init__(
            search_str=f'[a-z]+ entered _refresh_pair_array',
            config_ver=config_ver
        )

    def get_found_log_item(self,
                           found_log_msg: str,
                           found_log_idx: int) -> "EnterRpaLogFoundItem":
        """Return a found log item.

        Args:
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found

        Returns:
            EnterRpaLogFoundItem containing found message and index
        """
        return EnterRpaLogFoundItem(
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
            config_ver=self.config_ver)


########################################################################
# UpdatePaLogSearchItem
########################################################################
class UpdatePaLogSearchItem(LogSearchItem):
    """Input to search log msgs."""

    def __init__(self,
                 config_ver: "ConfigVerifier") -> None:
        """Initialize the LogItem.

        Args:
            config_ver: configuration verifier
        """
        super().__init__(
            search_str=f'[a-z]+ updated _pair_array at UTC {time_match}',
            config_ver=config_ver
        )

    def get_found_log_item(self,
                           found_log_msg: str,
                           found_log_idx: int) -> "UpdatePaLogFoundItem":
        """Return a found log item.

        Args:
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found

        Returns:
            UpdatePaLogFoundItem containing found message and index
        """
        return UpdatePaLogFoundItem(
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
            config_ver=self.config_ver)


########################################################################
# RegUpdateLogSearchItem
########################################################################
class RegUpdateLogSearchItem(LogSearchItem):
    """Input to search log msgs."""

    def __init__(self,
                 config_ver: "ConfigVerifier") -> None:
        """Initialize the LogItem.

        Args:
            config_ver: configuration verifier
        """
        super().__init__(
            search_str=f'[a-z]+ did registry update at UTC {time_match}',
            config_ver=config_ver
        )

    def get_found_log_item(self,
                           found_log_msg: str,
                           found_log_idx: int) -> "RegUpdateLogFoundItem":
        """Return a found log item.

        Args:
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found

        Returns:
            UpdatePaLogFoundItem containing found message and index
        """
        return RegUpdateLogFoundItem(
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
            config_ver=self.config_ver)


########################################################################
# RegUpdateLogSearchItem
########################################################################
class RegRemoveLogSearchItem(LogSearchItem):
    """Input to search log msgs."""

    def __init__(self,
                 config_ver: "ConfigVerifier") -> None:
        """Initialize the LogItem.

        Args:
            config_ver: configuration verifier
        """
        super().__init__(
            search_str=("[a-z]+ removed [a-z]+ from registry for "
                        "process='(join|unregister)'"),
            config_ver=config_ver
        )

    def get_found_log_item(self,
                           found_log_msg: str,
                           found_log_idx: int) -> "RegRemoveLogFoundItem":
        """Return a found log item.

        Args:
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found

        Returns:
            UpdatePaLogFoundItem containing found message and index
        """
        return RegRemoveLogFoundItem(
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
            config_ver=self.config_ver)


########################################################################
# RegUpdateLogSearchItem
########################################################################
class JoinUnregLogSearchItem(LogSearchItem):
    """Input to search log msgs."""

    def __init__(self,
                 config_ver: "ConfigVerifier") -> None:
        """Initialize the LogItem.

        Args:
            config_ver: configuration verifier
        """
        super().__init__(
            search_str='[a-z]+ did successful (unregister|join) of [a-z]+\.',
            config_ver=config_ver
        )

    def get_found_log_item(self,
                           found_log_msg: str,
                           found_log_idx: int) -> "JoinUnregLogFoundItem":
        """Return a found log item.

        Args:
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found

        Returns:
            UpdatePaLogFoundItem containing found message and index
        """
        return JoinUnregLogFoundItem(
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
            config_ver=self.config_ver)


########################################################################
# RecvMsgLogSearchItem
########################################################################
class RecvMsgLogSearchItem(LogSearchItem):
    """Input to search log msgs."""

    def __init__(self,
                 config_ver: "ConfigVerifier") -> None:
        """Initialize the LogItem.

        Args:
            config_ver: configuration verifier
        """
        super().__init__(
            search_str=f'[a-z]+ received msg from [a-z]+',
            config_ver=config_ver
        )

    def get_found_log_item(self,
                           found_log_msg: str,
                           found_log_idx: int) -> "RecvMsgLogFoundItem":
        """Return a found log item.

        Args:
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found

        Returns:
            UpdatePaLogFoundItem containing found message and index
        """
        return RecvMsgLogFoundItem(
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
            config_ver=self.config_ver)


########################################################################
# LogFoundItem
########################################################################
class LogFoundItem(ABC):
    """Found log item."""
    def __init__(self,
                 found_log_msg: str,
                 found_log_idx: int,
                 config_ver: "ConfigVerifier") -> None:
        """Initialize the LogItem.

        Args:
            found_log_msg: regex style search string
            found_log_idx: index of log where the msg was found
            config_ver: configuration verifier
        """
        self.found_log_msg: str = found_log_msg
        self.found_log_idx = found_log_idx
        self.config_ver: "ConfigVerifier" = config_ver

    @abstractmethod
    def run_process(self) -> None:
        """Run the command for the log msg."""
        pass


########################################################################
# EnterRpaLogFoundItem
########################################################################
class EnterRpaLogFoundItem(LogFoundItem):
    """Found log item."""

    def __init__(self,
                 found_log_msg: str,
                 found_log_idx: int,
                 config_ver: "ConfigVerifier") -> None:
        """Initialize the LogItem.

        Args:
            found_log_msg: regex style search string
            found_log_idx: index of log where the msg was found
            config_ver: configuration verifier
        """
        super().__init__(
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
            config_ver=config_ver
        )

    def run_process(self):
        self.config_ver.handle_enter_rpa_log_msg(
            cmd_runner=self.found_log_msg.split(maxsplit=1)[0])


########################################################################
# UpdatePaLogFoundItem
########################################################################
class UpdatePaLogFoundItem(LogFoundItem):
    """Found log item."""

    def __init__(self,
                 found_log_msg: str,
                 found_log_idx: int,
                 config_ver: "ConfigVerifier") -> None:
        """Initialize the LogItem.

        Args:
            found_log_msg: regex style search string
            found_log_idx: index of log where the msg was found
            config_ver: configuration verifier
        """
        super().__init__(
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
            config_ver=config_ver
        )

    def run_process(self):
        self.config_ver.handle_pair_array_update(
            cmd_runner=self.found_log_msg.split(maxsplit=1)[0],
            upa_msg=self.found_log_msg,
            upa_msg_idx=self.found_log_idx)


########################################################################
# RegUpdateLogFoundItem
########################################################################
class RegUpdateLogFoundItem(LogFoundItem):
    """Found log item."""

    def __init__(self,
                 found_log_msg: str,
                 found_log_idx: int,
                 config_ver: "ConfigVerifier") -> None:
        """Initialize the LogItem.

        Args:
            found_log_msg: regex style search string
            found_log_idx: index of log where the msg was found
            config_ver: configuration verifier
        """
        super().__init__(
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
            config_ver=config_ver
        )

    def run_process(self):
        self.config_ver.handle_reg_update(
            cmd_runner=self.found_log_msg.split(maxsplit=1)[0],
            reg_update_msg=self.found_log_msg,
            reg_update_msg_log_idx=self.found_log_idx)


########################################################################
# RegUpdateLogFoundItem
########################################################################
class RegRemoveLogFoundItem(LogFoundItem):
    """Found log item."""

    def __init__(self,
                 found_log_msg: str,
                 found_log_idx: int,
                 config_ver: "ConfigVerifier") -> None:
        """Initialize the LogItem.

        Args:
            found_log_msg: regex style search string
            found_log_idx: index of log where the msg was found
            config_ver: configuration verifier
        """
        super().__init__(
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
            config_ver=config_ver
        )

    def run_process(self):
        self.config_ver.handle_reg_remove()


########################################################################
# RegUpdateLogFoundItem
########################################################################
class JoinUnregLogFoundItem(LogFoundItem):
    """Found log item."""

    def __init__(self,
                 found_log_msg: str,
                 found_log_idx: int,
                 config_ver: "ConfigVerifier") -> None:
        """Initialize the LogItem.

        Args:
            found_log_msg: regex style search string
            found_log_idx: index of log where the msg was found
            config_ver: configuration verifier
        """
        super().__init__(
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
            config_ver=config_ver
        )

    def run_process(self):
        split_msg = self.found_log_msg.split()
        self.config_ver.handle_join_unreg_update(
            cmd_runner=split_msg[0],
            target_name=split_msg[5].removesuffix('.'),
            process=split_msg[3],found_log_msg_idx=self.found_log_idx
        )


########################################################################
# RecvMsgLogFoundItem
########################################################################
class RecvMsgLogFoundItem(LogFoundItem):
    """Found log item."""

    def __init__(self,
                 found_log_msg: str,
                 found_log_idx: int,
                 config_ver: "ConfigVerifier") -> None:
        """Initialize the LogItem.

        Args:
            found_log_msg: regex style search string
            found_log_idx: index of log where the msg was found
            config_ver: configuration verifier
        """
        super().__init__(
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
            config_ver=config_ver
        )

    def run_process(self):
        split_msg = self.found_log_msg.split()

        self.config_ver.dec_ops_count(
            cmd_runner=split_msg[0],
            sender=split_msg[4])


LogSearchItems: TypeAlias = Union[EnterRpaLogSearchItem,
                                  UpdatePaLogSearchItem,
                                  RegUpdateLogSearchItem,
                                  RegRemoveLogSearchItem,
                                  JoinUnregLogSearchItem,
                                  RecvMsgLogSearchItem]


class ConfigVerifier:
    """Class that tracks and verifies the SmartThread configuration."""

    def __init__(self,
                 commander_name: str,
                 log_ver: LogVer,
                 caplog_to_use: pytest.CaptureFixture[str],
                 msgs: Msgs,
                 # commander_thread: Optional[threading.Thread] = None,
                 max_msgs: Optional[int] = 10) -> None:
        """Initialize the ConfigVerifier.

        Args:
            log_ver: the log verifier to track and verify log msgs
        """
        self.specified_args = locals()  # used for __repr__, see below
        self.commander_name = commander_name
        self.commander_thread_config_built = False

        self.monitor_thread = threading.Thread(target=self.monitor)
        self.monitor_exit = False
        self.monitor_del_items: list[MonitorItem] = []
        self.monitor_add_items: list[MonitorAddItem] = []

        self.cmd_suite: deque[ConfigCmd] = deque()
        self.cmd_serial_num: int = 0
        self.completed_cmds: dict[str, list[int]] = defaultdict(list)
        self.f1_process_cmds: dict[str, bool] = {}
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
        self.caplog_to_use = caplog_to_use
        self.msgs = msgs
        self.ops_lock = threading.RLock()
        self.commander_thread: Optional[st.SmartThread] = None
        self.f1_threads: dict[str, st.SmartThread] = {}
        self.all_threads: dict[str, st.SmartThread] = {}
        self.created_names: list[str] = []
        self.max_msgs = max_msgs
        self.join_target_names: list[str] = []
        self.send_exit_sender_names: list[str] = []
        self.receiver_names: list[str] = []

        self.pending_ops_counts: dict[tuple[str, str], dict[str, int]] = {}
        self.expected_num_recv_timouts: int = 0
        self.deleted_remotes_pending_count: dict[str, int] = defaultdict(int)
        self.deleted_remotes_complete_count: dict[str, int] = defaultdict(int)
        self.pair_array_refresh_count: dict[str, int] = defaultdict(int)
        self.del_def_pairs_count: dict[
            tuple[str, str, str], int] = defaultdict(int)
        self.del_def_pairs_msg_count: dict[
            tuple[str, str, str], int] = defaultdict(int)
        self.del_def_pairs_msg_ind_count: dict[
            tuple[str, str, str, str], int] = defaultdict(int)
        # self.del_nondef_pairs_msg_count: dict[
        #     tuple[str, str, str], int] = defaultdict(int)
        self.status_array_log_counts: dict[str, int] = defaultdict(int)
        self.found_reg_log_msgs: int = 0
        self.found_upa_log_msgs: int = 0
        self.found_rec_log_msgs: int = 0
        self.found_utc_log_msgs: dict[tuple[str, str], int] = defaultdict(int)
        self.found_update_pair_array_log_msgs: dict[str, int] = defaultdict(
            int)
        self.recv_msg_event_items: dict[str, RecvEventItem] = {}
        self.pending_recv_msg_par: dict[str, bool] = defaultdict(bool)

        self.log_start_idx: int = 0
        self.log_search_items: tuple[LogSearchItems, ...] = (
            EnterRpaLogSearchItem(config_ver=self),
            UpdatePaLogSearchItem(config_ver=self),
            RegUpdateLogSearchItem(config_ver=self),
            RegRemoveLogSearchItem(config_ver=self),
            JoinUnregLogSearchItem(config_ver=self),
            RecvMsgLogSearchItem(config_ver=self)
        )
        self.log_found_items: deque[LogFoundItem] = deque()

        self.monitor_thread.start()

    ####################################################################
    # __repr__
    ####################################################################
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

    # ####################################################################
    # # monitor
    # ####################################################################
    # def monitor(self):
    #     log_msg = 'monitor entered'
    #     self.log_ver.add_msg(log_msg=re.escape(log_msg))
    #     logger.debug(log_msg)
    #
    #     enter_rpa_search = f'[a-z]+ entered _refresh_pair_array'
    #     reg_remove_search = ("[a-z]+ removed [a-z]+ from registry for "
    #                          "process='(join|unregister)'")
    #     reg_search_msg = f'[a-z]+ did registry update at UTC {time_match}'
    #     del_search_msg = '[a-z]+ did successful (unregister|join) of [a-z]+\.'
    #     upa_search_msg = (f'[a-z]+ updated _pair_array at UTC {time_match}')
    #     recv_msg_search = f'[a-z]+ received msg from [a-z]+'
    #
    #     while not self.monitor_exit:
    #         # log_msg = 'monitor about to search'
    #         # self.log_ver.add_msg(log_msg=re.escape(log_msg))
    #         # logger.debug(log_msg)
    #
    #         found_reg_msg, reg_pos = self.get_log_msg(
    #             search_msg=reg_search_msg,
    #             skip_num=self.found_reg_log_msgs)
    #         found_del_msg, del_pos = self.get_log_msg(
    #             search_msg=del_search_msg,
    #             skip_num=self.found_del_log_msgs)
    #         found_upa_msg, upa_pos = self.get_log_msg(
    #             search_msg=upa_search_msg,
    #             skip_num=self.found_upa_log_msgs)
    #         found_rec_msg, rec_pos = self.get_log_msg(
    #             search_msg=recv_msg_search,
    #             skip_num=self.found_rec_log_msgs)
    #
    #         if (reg_pos == -1
    #                 and del_pos == -1
    #                 and upa_pos == -1 and
    #                 rec_pos == -1):
    #             time.sleep(.05)
    #             continue
    #
    #         selection_pos: list[int] = []
    #         if -1 < reg_pos:
    #             selection_pos.append(reg_pos)
    #         if -1 < del_pos:
    #             selection_pos.append(del_pos)
    #         if -1 < upa_pos:
    #             selection_pos.append(upa_pos)
    #         if -1 < rec_pos:
    #             selection_pos.append(rec_pos)
    #
    #         min_pos = min(selection_pos)
    #
    #         if min_pos == reg_pos:
    #             found_del_msg = ''
    #             found_upa_msg = ''
    #             found_rec_msg = ''
    #         elif min_pos == del_pos:
    #             found_reg_msg = ''
    #             found_upa_msg = ''
    #             found_rec_msg = ''
    #         elif min_pos == upa_pos:
    #             found_reg_msg = ''
    #             found_del_msg = ''
    #             found_rec_msg = ''
    #         else:
    #             found_reg_msg = ''
    #             found_del_msg = ''
    #             found_upa_msg = ''
    #
    #         if found_del_msg:
    #             log_msg = f'monitor {found_del_msg=}'
    #             self.log_ver.add_msg(log_msg=re.escape(log_msg))
    #             logger.debug(log_msg)
    #
    #             self.found_del_log_msgs += 1
    #
    #             split_msg = found_del_msg.split()
    #             cmd_runner = split_msg[0]
    #             process = split_msg[3]
    #             target_name = split_msg[5].removesuffix('.')
    #
    #             self.del_thread(
    #                 cmd_runner=cmd_runner,
    #                 del_name=target_name,
    #                 process=process,
    #                 del_msg_idx=del_pos)
    #
    #             with self.ops_lock:
    #                 for item in self.monitor_del_items:
    #                     if (item.cmd_runner == cmd_runner
    #                             and item.target_name == target_name
    #                             and item.process_name == 'join'):
    #                         self.monitor_del_items.remove(item)
    #                         break
    #
    #         if found_reg_msg:
    #             log_msg = f'monitor {found_reg_msg=}'
    #             self.log_ver.add_msg(log_msg=re.escape(log_msg))
    #             logger.debug(log_msg)
    #
    #             split_msg = found_reg_msg.split()
    #             cmd_runner = split_msg[0]
    #
    #             with self.ops_lock:
    #                 for item in self.monitor_add_items:
    #                     if item.cmd_runner == cmd_runner:
    #
    #                         self.add_thread(
    #                             name=cmd_runner,
    #                             thread_alive=item.thread_alive,
    #                             auto_start=item.auto_start,
    #                             expected_status=item.expected_status,
    #                             reg_update_msg=found_reg_msg,
    #                             reg_idx=reg_pos
    #                         )
    #                         item.add_event.set()
    #                         self.monitor_add_items.remove(item)
    #                         self.found_reg_log_msgs += 1
    #                         break
    #
    #         if found_upa_msg:
    #             log_msg = f'monitor {found_upa_msg=}'
    #             self.log_ver.add_msg(log_msg=re.escape(log_msg))
    #             logger.debug(log_msg)
    #
    #             self.found_upa_log_msgs += 1
    #
    #             split_msg = found_upa_msg.split()
    #             cmd_runner = split_msg[0]
    #
    #             self.handle_pair_array_update(
    #                 cmd_runner=cmd_runner,
    #                 upa_msg=found_upa_msg,
    #                 upa_msg_idx=upa_pos)
    #
    #         if found_rec_msg:
    #             log_msg = f'monitor {found_rec_msg=}'
    #             self.log_ver.add_msg(log_msg=re.escape(log_msg))
    #             logger.debug(log_msg)
    #
    #             self.found_rec_log_msgs += 1
    #
    #             split_msg = found_rec_msg.split()
    #             cmd_runner = split_msg[0]
    #             sender = split_msg[4]
    #
    #             self.dec_ops_count(
    #                 cmd_runner=cmd_runner,
    #                 sender=sender)

    ####################################################################
    # monitor
    ####################################################################
    def monitor(self):
        log_msg = 'monitor entered'
        self.log_ver.add_msg(log_msg=re.escape(log_msg))
        logger.debug(log_msg)

        while not self.monitor_exit:
            # log_msg = 'monitor about to search'
            # self.log_ver.add_msg(log_msg=re.escape(log_msg))
            # logger.debug(log_msg)

            self.get_log_msgs()

            while self.log_found_items:
                found_log_item = self.log_found_items.popleft()
                found_log_item.run_process()

            time.sleep(0.2)

    ####################################################################
    # abort_all_f1_threads
    ####################################################################
    def abort_all_f1_threads(self):
        for name, thread in self.f1_threads.items():
            self.add_log_msg(f'aborting f1_thread {name}, '
                             f'thread.is_alive(): {thread.thread.is_alive()}.')
            if thread.thread.is_alive():
                exit_cmd = ExitThread(cmd_runners=name)
                self.add_cmd_info(exit_cmd)
                self.msgs.queue_msg(name, exit_cmd)

    ####################################################################
    # add_cmd
    ####################################################################
    def add_cmd(self,
                cmd: ConfigCmd) -> int:
        """Add a command to the deque.

        Args:
            cmd: command to add

        Returns:
            the serial number for the command

        """
        serial_num = self.add_cmd_info(cmd=cmd, frame_num=2)
        self.cmd_suite.append(cmd)
        return serial_num

    ####################################################################
    # add_cmd_info
    ####################################################################
    def add_cmd_info(self,
                     cmd: ConfigCmd,
                     frame_num: int = 1) -> int:
        """Add a command to the deque.

        Args:
            cmd: command to add

        Returns:
            the serial number for the command
        """
        self.cmd_serial_num += 1
        cmd.serial_num = self.cmd_serial_num

        frame = _getframe(frame_num)
        caller_info = get_caller_info(frame)
        cmd.line_num = caller_info.line_num
        cmd.config_ver = self

        return self.cmd_serial_num

    ####################################################################
    # add_log_msg
    ####################################################################
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

    ####################################################################
    # add_thread
    ####################################################################
    def add_thread(self,
                   name: str,
                   thread_alive: bool,
                   auto_start: bool,
                   expected_status: st.ThreadStatus,
                   reg_update_msg: str,
                   reg_idx: int,
                   ) -> None:
        """Add a thread to the ConfigVerifier.

        Args:
            name: name to add
            thread_alive: the expected is_alive flag
            auto_start: indicates whether to start the thread
            expected_status: the expected ThreadStatus
            reg_update_msg: the register update msg use for the log msg
            reg_idx: index of reg_update_msg in the log
        """
        log_msg = f'add_thread entered for {name}'
        self.log_ver.add_msg(log_msg=log_msg)
        logger.debug(log_msg)

        self.expected_registered[name] = ThreadTracker(
            thread=self.all_threads[name],
            is_alive=thread_alive,
            exiting=False,
            is_auto_started=auto_start,
            status=expected_status,
            found_del_pairs=defaultdict(int)
        )

        update_pair_array_msg_needed = False

        copy_exp_reg_keys = list(self.expected_registered.keys())
        # copy_exp_reg_keys = list(log_array.status_array.keys()) + [name]
        copy_exp_reg_keys.sort()
        # if len(self.expected_registered) > 1:
        if len(copy_exp_reg_keys) > 1:
            pair_keys = combinations(copy_exp_reg_keys, 2)
            # pair_keys = combinations(
            #     sorted(self.expected_registered.keys()), 2)
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
                    update_pair_array_msg_needed = True

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
                    update_pair_array_msg_needed = True

        ################################################################
        # add log msgs
        ################################################################
        self.add_log_msg(
            f'{name} set status for thread {name} '
            'from undefined to ThreadStatus.Initializing')

        self.add_log_msg(
            f'{name} obtained _registry_lock, '
            'class name = SmartThread')

        self.handle_exp_status_log_msgs(log_idx=reg_idx,
                                        name=name)

        self.add_log_msg(
            f'{name} set status for thread {name} '
            'from ThreadStatus.Initializing to ThreadStatus.Registered')

        self.add_log_msg(f'{name} entered _refresh_pair_array')
        self.pair_array_refresh_count[name] += 1

        self.handle_deferred_delete_log_msgs(cmd_runner=name)

        # self.add_log_msg(
        #     f'{name} did registry update at UTC '
        #     f'{reg_update_time.strftime("%H:%M:%S.%f")}')

        self.add_log_msg(re.escape(reg_update_msg))

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
                update_pair_array_msg_needed = True
                self.add_log_msg(
                    f'{name} set status for thread {name} '
                    f'from ThreadStatus.Registered to ThreadStatus.Alive')
        if update_pair_array_msg_needed:
            upa_search_msg = (
                f"{name} updated _pair_array at UTC {time_match}")
            found_upa_msg, upa_pos = self.get_log_msg(
                search_msg=upa_search_msg,
                skip_num=self.found_update_pair_array_log_msgs[name])
            if found_upa_msg:
                self.found_update_pair_array_log_msgs[name] += 1
                self.add_log_msg(re.escape(found_upa_msg))

    ####################################################################
    # build_config
    ####################################################################
    def build_config(self,
                     cmd_runner: str,
                     num_registered: Optional[int] = 0,
                     num_active: Optional[int] = 1,
                     num_stopped: Optional[int] = 0
                     ) -> None:
        """Add ConfigCmd items to the queue.

        Args:
            cmd_runner: thread running the command
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

        if not self.commander_thread_config_built:
            self.build_create_suite(commander_name=self.commander_name)
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
            self.build_unreg_suite_num(num_to_unreg=num_reg_to_unreg)

        if num_stopped_to_join > 0:
            self.build_join_suite_num(
                cmd_runners=cmd_runner,
                num_to_join=num_stopped_to_join)

        # create threads with no_start
        if num_create_no_start > 0:
            self.build_f1_create_suite_num(
                    num_to_create=num_create_no_start,
                    auto_start=False)

        # start registered so we have actives to exit if need be
        if num_reg_to_start > 0:
            self.build_start_suite_num(num_to_start=num_reg_to_start)

        # create threads with auto_start
        if num_create_auto_start > 0:
            self.build_f1_create_suite_num(
                num_to_create=num_create_auto_start,
                auto_start=True)

        # Now that we have actives, do any needed exits
        if num_active_to_exit > 0:
            self.build_exit_suite_num(
                num_to_exit=num_active_to_exit)

        # Finally, join the stopped threads as needed
        if num_active_to_join > 0:
            self.build_join_suite_num(
                cmd_runners=cmd_runner,
                num_to_join=num_active_to_join)

        # verify the counts
        self.add_cmd(VerifyCounts(cmd_runners=cmd_runner,
                                  exp_num_registered=num_registered,
                                  exp_num_active=num_active,
                                  exp_num_stopped=num_stopped))

    ####################################################################
    # build_config_build_suite
    ####################################################################
    def build_config_build_suite(self,
                                 num_registered_1: int,
                                 num_active_1: int,
                                 num_stopped_1: int,
                                 num_registered_2: int,
                                 num_active_2: int,
                                 num_stopped_2: int
                         ) -> None:
        """Return a list of ConfigCmd items for config build.

        Args:
            num_registered_1: number of threads to initially build as
                registered
            num_active_1: number of threads to initially build as
                active
            num_stopped_1: number of threads to initially build as
                stopped
            num_registered_2: number of threads to reconfigured as
                registered
            num_active_2: number of threads to reconfigured as active
            num_stopped_2: number of threads to reconfigured as stopped

        Returns:
            a list of ConfigCmd items
        """
        self.build_config(
            cmd_runner=self.commander_name,
            num_registered=num_registered_1,
            num_active=num_active_1,
            num_stopped=num_stopped_1)
        self.build_config(
            cmd_runner=self.commander_name,
            num_registered=num_registered_2,
            num_active=num_active_2,
            num_stopped=num_stopped_2)

    ####################################################################
    # build_create_suite
    ####################################################################
    def build_create_suite(
            self,
            commander_name: Optional[str] = None,
            commander_auto_start: Optional[bool] = True,
            f1_create_items: Optional[list[F1CreateItem]] = None,
            validate_config: Optional[bool] = True
            ) -> None:
        """Return a list of ConfigCmd items for a create.

        Args:
            commander_name: specifies that a commander thread is to be
                created with this name
            commander_auto_start: specifies whether to start the
                commander thread during create
            f1_create_items: contain f1_names to create
            validate_config: indicates whether to do config validation

        Returns:
            a list of ConfigCmd items
        """
        if commander_name:
            if not {commander_name}.issubset(self.unregistered_names):
                raise InvalidInputDetected('Input commander name '
                                           f'{commander_name} not a subset of '
                                           'unregistered names '
                                           f'{self.unregistered_names}')
            self.unregistered_names -= {commander_name}
            if commander_auto_start:
                self.add_cmd(
                    CreateCommanderAutoStart(cmd_runners=commander_name,
                                             commander_name=commander_name))

                self.active_names |= {commander_name}
            else:
                self.add_cmd(
                    CreateCommanderNoStart(cmd_runners=commander_name,
                                           commander_name=commander_name))
                self.registered_names |= {commander_name}

        if f1_create_items:
            f1_names: list[str] = []
            f1_auto_start_names: list[str] = []
            f1_auto_items: list[F1CreateItem] = []
            f1_no_start_names: list[str] = []
            f1_no_start_items: list[F1CreateItem] = []
            for f1_create_item in f1_create_items:
                f1_names.append(f1_create_item.name)
                if f1_create_item.auto_start:
                    f1_auto_start_names.append(f1_create_item.name)
                    f1_auto_items.append(f1_create_item)
                else:
                    f1_no_start_names.append(f1_create_item.name)
                    f1_no_start_items.append(f1_create_item)
            if not set(f1_names).issubset(self.unregistered_names):
                self.abort_all_f1_threads()
                raise InvalidInputDetected(f'Input names {f1_names} not a '
                                           f'subset of unregistered names '
                                           f'{self.unregistered_names}')
            self.unregistered_names -= set(f1_names)
            if f1_auto_items:
                self.add_cmd(
                    CreateF1AutoStart(cmd_runners=self.commander_name,
                                      f1_create_items=f1_auto_items))

                self.active_names |= set(f1_auto_start_names)
            elif f1_no_start_items:
                self.add_cmd(
                    CreateF1NoStart(cmd_runners=self.commander_name,
                                    f1_create_items=f1_no_start_items))
                self.registered_names |= set(f1_no_start_names)

        if self.registered_names:
            self.add_cmd(VerifyRegistered(
                cmd_runners=self.commander_name,
                exp_registered_names=list(self.registered_names)))

        if self.active_names:
            self.add_cmd(VerifyActive(
                cmd_runners=self.commander_name,
                exp_active_names=list(self.active_names)))

        if validate_config:
            self.add_cmd(ValidateConfig(cmd_runners=self.commander_name))

    ####################################################################
    # build_exit_suite
    ####################################################################
    def build_exit_suite(self,
                         names: list[str],
                         validate_config: Optional[bool] = True
                         ) -> None:
        """Return a list of ConfigCmd items for a exit.

        Returns:
            a list of ConfigCmd items
        """
        if not set(names).issubset(self.active_names):
            self.abort_all_f1_threads()
            raise InvalidInputDetected(f'Input names {names} not a subset '
                                       f'of active names {self.active_names}')
        active_names = list(self.active_names - set(names))

        if names:
            self.add_cmd(StopThread(cmd_runners=self.commander_name,
                                    stop_names=names))
            if validate_config:
                self.add_cmd(Pause(cmd_runners=self.commander_name,
                                   pause_seconds=.2))
                self.add_cmd(VerifyAliveNot(cmd_runners=self.commander_name,
                                            exp_not_alive_names=names))
                self.add_cmd(VerifyStatus(
                    cmd_runners=self.commander_name,
                    check_status_names=names,
                    expected_status=st.ThreadStatus.Alive))

        if active_names and validate_config:
            self.add_cmd(VerifyAlive(cmd_runners=self.commander_name,
                                     exp_alive_names=active_names))
            self.add_cmd(VerifyStatus(
                cmd_runners=self.commander_name,
                check_status_names=active_names,
                expected_status=st.ThreadStatus.Alive))

        if validate_config:
            self.add_cmd(ValidateConfig(cmd_runners=self.commander_name))

        self.active_names -= set(names)
        self.stopped_names |= set(names)

    ####################################################################
    # build_exit_suite_num
    ####################################################################
    def build_exit_suite_num(self,
                             num_to_exit: int) -> None:
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

    ####################################################################
    # build_f1_create_suite_num
    ####################################################################
    def build_f1_create_suite_num(self,
                                  num_to_create: int,
                                  auto_start: Optional[bool] = True,
                                  validate_config: Optional[bool] = True
                                  ) -> None:
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
        f1_create_items: list[F1CreateItem] = []
        for idx, name in enumerate(names):
            if idx % 2:
                app_config = AppConfig.ScriptStyle
            else:
                app_config = AppConfig.RemoteThreadApp

            f1_create_items.append(F1CreateItem(name=name,
                                                auto_start=auto_start,
                                                target_rtn=outer_f1,
                                                app_config=app_config))

        self.build_create_suite(f1_create_items=f1_create_items,
                                validate_config=validate_config)

    ####################################################################
    # build_join_suite
    ####################################################################
    def build_join_suite(self,
                         cmd_runners: StrOrList,
                         join_target_names: list[str],
                         validate_config: Optional[bool] = True
                         ) -> None:
        """Return a list of ConfigCmd items for join.

        Args:
            cmd_runners: list of names to do the join
            join_target_names: the threads that are to be joined
            validate_config: specifies whether to validate the config
                after the join is done

        Returns:
            a list of ConfigCmd items
        """
        if isinstance(cmd_runners, str):
            cmd_runners = [cmd_runners]

        if not set(join_target_names).issubset(self.stopped_names):
            self.abort_all_f1_threads()
            raise InvalidInputDetected(f'Input {join_target_names} is not a '
                                       'subset of inactive names '
                                       f'{self.stopped_names}')

        if join_target_names:
            self.add_cmd(Join(
                cmd_runners=cmd_runners,
                join_names=join_target_names))
            self.add_cmd(VerifyInRegistryNot(
                cmd_runners=self.commander_name,
                exp_not_in_registry_names=join_target_names))
            self.add_cmd(VerifyPairedNot(
                cmd_runners=self.commander_name,
                exp_not_paired_names=join_target_names))

        if validate_config:
            self.add_cmd(ValidateConfig(cmd_runners=self.commander_name))

        self.unregistered_names |= set(join_target_names)
        self.stopped_names -= set(join_target_names)

    ####################################################################
    # build_join_suite
    ####################################################################
    def build_join_suite_num(self,
                             cmd_runners: StrOrList,
                             num_to_join: int) -> None:
        """Return a list of ConfigCmd items for join.

        Args:
            cmd_runners: threads running the command
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

        self.build_join_suite(
            cmd_runners=cmd_runners,
            join_target_names=names)

    ####################################################################
    # build_join_timeout_suite
    ####################################################################
    def build_join_timeout_suite(
            self,
            timeout_type: TimeoutType,
            num_active_no_target: int,
            num_no_delay_exit: int,
            num_delay_exit: int,
            num_no_delay_unreg: int,
            num_delay_unreg: int,
            num_no_delay_reg: int,
            num_delay_reg: int) -> None:
        """Return a list of ConfigCmd items for a create.

        Args:
            timeout_type: specifies TimeoutNone, TimeoutFalse,
                or TimeoutTrue
            num_active_no_target: number of threads that should be
                active and stay active during the join as non-targets
            num_no_delay_exit: number of threads that should be active
                and targeted for join, and then exited immediately to
                allow the join to succeed
            num_delay_exit: number of threads that should be active and
                targeted for join, and then be exited after a short
                delay to allow a TimeoutFalse join to succeed, and a
                long delay to cause a TimeoutTrue join to
                timeout and a TimeoutNone to eventually succeed
            num_no_delay_unreg: number of threads that should be
                unregistered and targeted for join, and then be
                be immediately created, started, exited to allow the
                join to succeed
            num_delay_unreg: number of threads that should be
                unregistered and targeted for join, and then be
                be created, started, exited after a short delay to allow
                a TimeoutFalse join to succeed, and a long delay to
                cause a TimeoutTrue join to timeout and a TimeoutNone to
                eventually succeed
            num_no_delay_reg: number of threads that should be
                registered and targeted for join, and then be
                be immediately started and exited to allow the
                join to succeed
            num_delay_reg: number of threads that should be registered
                and targeted for join, and then be started and exited
                after a short delay to allow a TimeoutFalse join to
                succeed, and a long delay to cause a TimeoutTrue join to
                timeout and a TimeoutNone to eventually succeed

        Returns:
            a list of ConfigCmd items
        """
        # Make sure we have enough threads. Note that we subtract 1 from
        # the count of unregistered names to ensure we have one thread
        # for the commander
        assert 1 < (num_active_no_target
                    + num_no_delay_exit
                    + num_delay_exit
                    + num_no_delay_unreg
                    + num_delay_unreg
                    + num_no_delay_reg
                    + num_delay_reg) <= len(self.unregistered_names) - 1

        if (timeout_type == TimeoutType.TimeoutFalse
                or timeout_type == TimeoutType.TimeoutTrue):
            assert (num_delay_exit
                    + num_delay_unreg
                    + num_delay_reg) > 0

        assert num_active_no_target > 0

        num_registered_needed = (
                num_no_delay_reg
                + num_delay_reg)

        num_active_needed = (
                num_active_no_target
                + num_no_delay_exit
                + num_delay_exit
                + 1)

        self.build_config(
            cmd_runner=self.commander_name,
            num_registered=num_registered_needed,
            num_active=num_active_needed)

        self.log_name_groups()

        # active_names = self.active_names.copy()
        # remove commander for now, but if we add it later we need to
        # be careful not to exit the commander
        unregistered_names = self.unregistered_names.copy()
        registered_names = self.registered_names.copy()
        active_names = self.active_names - {self.commander_name}

        ################################################################
        # choose receiver_names
        ################################################################
        active_no_target_names = self.choose_names(
            name_collection=active_names,
            num_names_needed=num_active_no_target,
            update_collection=True,
            var_name_for_log='active_no_target_names')

        ################################################################
        # choose active_no_delay_sender_names
        ################################################################
        no_delay_exit_names = self.choose_names(
            name_collection=active_names,
            num_names_needed=num_no_delay_exit,
            update_collection=True,
            var_name_for_log='no_delay_exit_names')

        ################################################################
        # choose active_delay_sender_names
        ################################################################
        delay_exit_names = self.choose_names(
            name_collection=active_names,
            num_names_needed=num_delay_exit,
            update_collection=True,
            var_name_for_log='delay_exit_names')

        ################################################################
        # choose send_exit_sender_names
        ################################################################
        no_delay_unreg_names = self.choose_names(
            name_collection=unregistered_names,
            num_names_needed=num_no_delay_unreg,
            update_collection=True,
            var_name_for_log='no_delay_unreg_names')

        ################################################################
        # choose nosend_exit_sender_names
        ################################################################
        delay_unreg_names = self.choose_names(
            name_collection=unregistered_names,
            num_names_needed=num_delay_unreg,
            update_collection=True,
            var_name_for_log='delay_unreg_names')

        ################################################################
        # choose unreg_sender_names
        ################################################################
        no_delay_reg_names = self.choose_names(
            name_collection=registered_names,
            num_names_needed=num_no_delay_reg,
            update_collection=True,
            var_name_for_log='no_delay_reg_names')

        ################################################################
        # choose reg_sender_names
        ################################################################
        delay_reg_names = self.choose_names(
            name_collection=registered_names,
            num_names_needed=num_delay_reg,
            update_collection=True,
            var_name_for_log='delay_reg_names')

        ################################################################
        # start by doing the recv_msgs, one for each sender
        ################################################################
        all_target_names: list[str] = (no_delay_exit_names
                                       + delay_exit_names
                                       + no_delay_unreg_names
                                       + delay_unreg_names
                                       + no_delay_reg_names
                                       + delay_reg_names)

        self.join_target_names = all_target_names

        all_timeout_names: list[str] = (delay_exit_names
                                        + delay_unreg_names
                                        + delay_reg_names)

        if len(all_target_names) % 2 == 0:
            log_msg = f'join log test: {self.get_ptime()}'
        else:
            log_msg = None

        ################################################################
        # start the join
        ################################################################
        if timeout_type == TimeoutType.TimeoutNone:
            confirm_cmd_to_use = 'Join'
            join_serial_num = self.add_cmd(
                Join(cmd_runners=active_no_target_names[0],
                     join_names=all_target_names,
                     log_msg=log_msg))
        elif timeout_type == TimeoutType.TimeoutFalse:
            confirm_cmd_to_use = 'JoinTimeoutFalse'
            join_serial_num = self.add_cmd(
                JoinTimeoutFalse(cmd_runners=active_no_target_names[0],
                                 join_names=all_target_names,
                                 timeout=4,
                                 log_msg=log_msg))
        else:  # TimeoutType.TimeoutTrue
            confirm_cmd_to_use = 'JoinTimeoutTrue'
            join_serial_num = self.add_cmd(
                JoinTimeoutTrue(cmd_runners=active_no_target_names[0],
                                join_names=all_target_names,
                                timeout=4,
                                timeout_names=all_timeout_names,
                                log_msg=log_msg))

        ################################################################
        # handle no_delay_exit_names
        ################################################################
        if no_delay_exit_names:
            self.build_exit_suite(names=no_delay_exit_names,
                                  validate_config=False)

        ################################################################
        # handle no_delay_unreg_names
        ################################################################
        if no_delay_unreg_names:
            f1_create_items: list[F1CreateItem] = []
            for idx, name in enumerate(no_delay_unreg_names):
                if idx % 2:
                    app_config = AppConfig.ScriptStyle
                else:
                    app_config = AppConfig.RemoteThreadApp

                f1_create_items.append(F1CreateItem(name=name,
                                                    auto_start=True,
                                                    target_rtn=outer_f1,
                                                    app_config=app_config))
            # for name in no_delay_unreg_names:
            #     f1_create_items.append(F1CreateItem(name=name,
            #                                         auto_start=True,
            #                                         target_rtn=outer_f1))
            self.build_create_suite(f1_create_items=f1_create_items,
                                    validate_config=False)
            self.build_exit_suite(names=no_delay_unreg_names,
                                  validate_config=False)

        ################################################################
        # handle no_delay_reg_names
        ################################################################
        if no_delay_reg_names:
            self.build_start_suite(start_names=no_delay_reg_names,
                                   validate_config=False)
            self.build_exit_suite(names=no_delay_reg_names,
                                  validate_config=False)

        ################################################################
        # pause for short or long delay
        ################################################################
        if (timeout_type == TimeoutType.TimeoutNone
                or timeout_type == TimeoutType.TimeoutFalse):
            self.add_cmd(
                Pause(cmd_runners=self.commander_name,
                      pause_seconds=1))
        elif timeout_type == TimeoutType.TimeoutTrue:
            self.add_cmd(
                Pause(cmd_runners=self.commander_name,
                      pause_seconds=5))

        ################################################################
        # handle delay_exit_names
        ################################################################
        if delay_exit_names:
            self.build_exit_suite(names=delay_exit_names,
                                  validate_config=False)

        ################################################################
        # handle delay_unreg_names
        ################################################################
        if delay_unreg_names:
            f1_create_items: list[F1CreateItem] = []
            for idx, name in enumerate(delay_unreg_names):
                if idx % 2:
                    app_config = AppConfig.ScriptStyle
                else:
                    app_config = AppConfig.RemoteThreadApp

                f1_create_items.append(F1CreateItem(name=name,
                                                    auto_start=True,
                                                    target_rtn=outer_f1,
                                                    app_config=app_config))
            # for name in delay_unreg_names:
            #     f1_create_items.append(F1CreateItem(name=name,
            #                                         auto_start=True,
            #                                         target_rtn=outer_f1))
            self.build_create_suite(f1_create_items=f1_create_items,
                                    validate_config=False)
            self.build_exit_suite(names=delay_unreg_names,
                                  validate_config=False)

        ################################################################
        # handle delay_reg_names
        ################################################################
        if delay_reg_names:
            self.build_start_suite(start_names=delay_reg_names,
                                   validate_config=False)
            self.build_exit_suite(names=delay_reg_names,
                                  validate_config=False)

        ################################################################
        # finally, confirm the recv_msg is done
        ################################################################
        self.add_cmd(
            ConfirmResponse(cmd_runners=self.commander_name,
                 confirm_cmd=confirm_cmd_to_use,
                 confirm_serial_num=join_serial_num,
                 confirmers=active_no_target_names[0]))

    ####################################################################
    # build_msg_suite
    ####################################################################
    def build_msg_suite(self,
                        from_names: list[str],
                        to_names: list[str]) -> None:
        """Return a list of ConfigCmd items for msgs.

        Returns:
            a list of ConfigCmd items
        """
        msgs_to_send: dict[str, str] = {}
        for from_name in from_names:
            msgs_to_send[from_name] = f'send test: {self.get_ptime()}'
        self.add_cmd(
            SendMsg(cmd_runners=from_names,
                    receivers=to_names,
                    msgs_to_send=msgs_to_send))

        self.add_cmd(
            RecvMsg(cmd_runners=to_names,
                    senders=from_names,
                    exp_msgs=msgs_to_send))

    ####################################################################
    # build_recv_msg_timeout_suite
    ####################################################################
    def build_recv_msg_timeout_suite(
            self,
            timeout_type: TimeoutType,
            num_receivers: int,
            num_active_no_delay_senders: int,
            num_active_delay_senders: int,
            num_send_exit_senders: int,
            num_nosend_exit_senders: int,
            num_unreg_senders: int,
            num_reg_senders: int) -> None:
        """Return a list of ConfigCmd items for a msg timeout.

        Args:
            timeout_type: specifies whether the recv_msg should
                be coded with timeout and whether the recv_msg should
                succeed or fail with a timeout
            num_receivers: number of threads that will do the
                recv_msg
            num_active_no_delay_senders: number of threads that are
                active and will do the send_msg immediately
            num_active_delay_senders: number of threads that are active
                and will do the send_msg after a delay
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
                + num_active_no_delay_senders
                + num_active_delay_senders
                + num_send_exit_senders
                + num_nosend_exit_senders
                + num_unreg_senders
                + num_reg_senders) <= len(self.unregistered_names) - 1

        assert num_receivers > 0

        assert (num_active_no_delay_senders
                + num_active_delay_senders
                + num_send_exit_senders
                + num_nosend_exit_senders
                + num_unreg_senders
                + num_reg_senders) > 0

        if (timeout_type == TimeoutType.TimeoutFalse
                or timeout_type == TimeoutType.TimeoutTrue):
            assert (num_active_delay_senders
                    + num_nosend_exit_senders
                    + num_unreg_senders
                    + num_reg_senders) > 0

        num_active_needed = (
                num_receivers
                + num_active_no_delay_senders
                + num_active_delay_senders
                + num_send_exit_senders
                + num_nosend_exit_senders
                + 1)

        self.build_config(
            cmd_runner=self.commander_name,
            num_registered=num_reg_senders,
            num_active=num_active_needed)

        self.log_name_groups()

        # active_names = self.active_names.copy()
        # remove commander for now, but if we add it later we need to
        # be careful not to exit the commander
        active_names = self.active_names - {self.commander_name}

        ################################################################
        # choose receiver_names
        ################################################################
        receiver_names = self.choose_names(
            name_collection=active_names,
            num_names_needed=num_receivers,
            update_collection=True,
            var_name_for_log='receiver_names')

        ################################################################
        # choose active_no_delay_sender_names
        ################################################################
        active_no_delay_sender_names = self.choose_names(
            name_collection=active_names,
            num_names_needed=num_active_no_delay_senders,
            update_collection=True,
            var_name_for_log='active_no_delay_sender_names')

        ################################################################
        # choose active_delay_sender_names
        ################################################################
        active_delay_sender_names = self.choose_names(
            name_collection=active_names,
            num_names_needed=num_active_delay_senders,
            update_collection=True,
            var_name_for_log='active_delay_sender_names')

        ################################################################
        # choose send_exit_sender_names
        ################################################################
        send_exit_sender_names = self.choose_names(
            name_collection=active_names,
            num_names_needed=num_send_exit_senders,
            update_collection=True,
            var_name_for_log='send_exit_sender_names')

        ################################################################
        # choose nosend_exit_sender_names
        ################################################################
        nosend_exit_sender_names = self.choose_names(
            name_collection=active_names,
            num_names_needed=num_nosend_exit_senders,
            update_collection=True,
            var_name_for_log='nosend_exit_sender_names')

        ################################################################
        # choose unreg_sender_names
        ################################################################
        unreg_sender_names = self.choose_names(
            name_collection=self.unregistered_names,
            num_names_needed=num_unreg_senders,
            update_collection=False,
            var_name_for_log='unreg_sender_names')

        ################################################################
        # choose reg_sender_names
        ################################################################
        reg_sender_names = self.choose_names(
            name_collection=self.registered_names,
            num_names_needed=num_reg_senders,
            update_collection=False,
            var_name_for_log='reg_sender_names')

        ################################################################
        # start by doing the recv_msgs, one for each sender
        ################################################################
        all_sender_names: list[str] = (active_no_delay_sender_names
                                       + active_delay_sender_names
                                       + send_exit_sender_names
                                       + nosend_exit_sender_names
                                       + unreg_sender_names
                                       + reg_sender_names)

        all_timeout_names: list[str] = (active_delay_sender_names
                                        + send_exit_sender_names
                                        + nosend_exit_sender_names
                                        + unreg_sender_names
                                        + reg_sender_names)

        self.set_recv_timeout(
            num_timeouts=len(all_timeout_names) * num_receivers)

        if len(all_sender_names) % 2 == 0:
            log_msg = f'recv_msg log test: {self.get_ptime()}'
        else:
            log_msg = None

        self.send_exit_sender_names = send_exit_sender_names.copy()
        self.receiver_names = receiver_names.copy()
        ################################################################
        # setup the messages to send
        ################################################################
        sender_msgs: dict[str, str] = {}
        for name in all_sender_names:
            sender_msgs[name] = (f'recv test: {name} sending msg '
                                 f'at {self.get_ptime()}')

        if timeout_type == TimeoutType.TimeoutNone:
            confirm_cmd_to_use = 'RecvMsg'
            recv_msg_serial_num = self.add_cmd(
                RecvMsg(cmd_runners=receiver_names,
                        senders=all_sender_names,
                        exp_msgs=sender_msgs,
                        del_deferred=send_exit_sender_names,
                        log_msg=log_msg))
        elif timeout_type == TimeoutType.TimeoutFalse:
            confirm_cmd_to_use = 'RecvMsgTimeoutFalse'
            recv_msg_serial_num = self.add_cmd(
                RecvMsgTimeoutFalse(
                    cmd_runners=receiver_names,
                    senders=all_sender_names,
                    exp_msgs=sender_msgs,
                    timeout=2,
                    del_deferred=send_exit_sender_names,
                    log_msg=log_msg))

        else:  # TimeoutType.TimeoutTrue
            confirm_cmd_to_use = 'RecvMsgTimeoutTrue'
            recv_msg_serial_num = self.add_cmd(
                RecvMsgTimeoutTrue(
                    cmd_runners=receiver_names,
                    senders=all_sender_names,
                    exp_msgs=sender_msgs,
                    timeout=2,
                    timeout_names=all_timeout_names,
                    del_deferred=send_exit_sender_names,
                    log_msg=log_msg))

        ################################################################
        # do send_msg from active_no_delay_senders
        ################################################################
        if active_no_delay_sender_names:
            # sender_1_msg_1[exit_name] = f'send test: {self.get_ptime()}'
            # log_msg = f'log test: {self.get_ptime()}'

            self.add_cmd(
                SendMsg(cmd_runners=active_no_delay_sender_names,
                        receivers=receiver_names,
                        msgs_to_send=sender_msgs))

        if (timeout_type == TimeoutType.TimeoutNone
                or timeout_type == TimeoutType.TimeoutFalse):
            self.add_cmd(
                Pause(cmd_runners=self.commander_name,
                      pause_seconds=1))
        elif timeout_type == TimeoutType.TimeoutTrue:
            self.add_cmd(
                Pause(cmd_runners=self.commander_name,
                      pause_seconds=3))
            self.add_cmd(WaitForRecvTimeouts(cmd_runners=self.commander_name))

        ################################################################
        # do send_msg from active_delay_senders
        ################################################################
        if active_delay_sender_names:
            self.add_cmd(
                SendMsg(cmd_runners=active_delay_sender_names,
                        receivers=receiver_names,
                        msgs_to_send=sender_msgs))

        ################################################################
        # do send_msg from send_exit_senders and then exit
        ################################################################
        if send_exit_sender_names:
            self.add_cmd(
                SendMsg(cmd_runners=send_exit_sender_names,
                        receivers=receiver_names,
                        msgs_to_send=sender_msgs))

            self.build_exit_suite(
                names=send_exit_sender_names, validate_config=False)
            self.build_join_suite(
                cmd_runners=self.commander_name,
                join_target_names=send_exit_sender_names,
                validate_config=False)

        ################################################################
        # exit the nosend_exit_senders, then resurrect and do send_msg
        ################################################################
        if nosend_exit_sender_names:
            self.build_exit_suite(
                names=nosend_exit_sender_names, validate_config=False)
            self.build_join_suite(
                cmd_runners=self.commander_name,
                join_target_names=nosend_exit_sender_names,
                validate_config=False)
            f1_create_items: list[F1CreateItem] = []
            for idx, name in enumerate(nosend_exit_sender_names):
                if idx % 2:
                    app_config = AppConfig.ScriptStyle
                else:
                    app_config = AppConfig.RemoteThreadApp

                f1_create_items.append(F1CreateItem(name=name,
                                                    auto_start=True,
                                                    target_rtn=outer_f1,
                                                    app_config=app_config))
            # for name in nosend_exit_sender_names:
            #     f1_create_items.append(F1CreateItem(name=name,
            #                                         auto_start=True,
            #                                         target_rtn=outer_f1))
            self.build_create_suite(
                f1_create_items=f1_create_items,
                validate_config=False)
            self.add_cmd(
                SendMsg(cmd_runners=nosend_exit_sender_names,
                        receivers=receiver_names,
                        msgs_to_send=sender_msgs))

        ################################################################
        # create and start the unreg_senders, then do send_msg
        ################################################################
        if unreg_sender_names:
            f1_create_items: list[F1CreateItem] = []
            for idx, name in enumerate(unreg_sender_names):
                if idx % 2:
                    app_config = AppConfig.ScriptStyle
                else:
                    app_config = AppConfig.RemoteThreadApp

                f1_create_items.append(F1CreateItem(name=name,
                                                    auto_start=True,
                                                    target_rtn=outer_f1,
                                                    app_config=app_config))
            # for name in unreg_sender_names:
            #     f1_create_items.append(F1CreateItem(name=name,
            #                                         auto_start=True,
            #                                         target_rtn=outer_f1))
            self.build_create_suite(
                f1_create_items=f1_create_items,
                validate_config=False)
            self.add_cmd(
                SendMsg(cmd_runners=unreg_sender_names,
                        receivers=receiver_names,
                        msgs_to_send=sender_msgs))

        ################################################################
        # start the reg_senders, then do send_msg
        ################################################################
        if reg_sender_names:
            self.build_start_suite(
                start_names=reg_sender_names,
                validate_config=False)
            self.add_cmd(
                SendMsg(cmd_runners=reg_sender_names,
                        receivers=receiver_names,
                        msgs_to_send=sender_msgs))

        ################################################################
        # finally, confirm the recv_msg is done
        ################################################################
        self.add_cmd(
            ConfirmResponse(
                cmd_runners=[self.commander_name],
                confirm_cmd=confirm_cmd_to_use,
                confirm_serial_num=recv_msg_serial_num,
                confirmers=receiver_names))

    ####################################################################
    # build_msg_timeout_suite
    ####################################################################
    def build_send_msg_timeout_suite(self,
                                     timeout_type: TimeoutType,
                                     num_senders: Optional[int] = 1,
                                     num_active_targets: Optional[int] = 1,
                                     num_registered_targets: Optional[int] = 0,
                                     num_unreg_timeouts: Optional[int] = 0,
                                     num_exit_timeouts: Optional[int] = 1,
                                     num_full_q_timeouts: Optional[int] = 0
                                     ) -> None:
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

        self.build_config(
            cmd_runner=self.commander_name,
            num_registered=num_registered_targets,
            num_active=num_active_needed)

        self.log_name_groups()
        # active_names = self.active_names.copy()
        # remove commander for now, but if we add it later we need to
        # be careful not to exit the commander
        active_names = self.active_names - {self.commander_name}

        ################################################################
        # choose sender_names
        ################################################################
        sender_names = self.choose_names(
            name_collection=active_names,
            num_names_needed=num_senders,
            update_collection=True,
            var_name_for_log='sender_names')

        ################################################################
        # choose active_target_names
        ################################################################
        active_target_names = self.choose_names(
            name_collection=active_names,
            num_names_needed=num_active_targets,
            update_collection=True,
            var_name_for_log='active_target_names')

        ################################################################
        # choose registered_target_names
        ################################################################
        registered_target_names = self.choose_names(
            name_collection=self.registered_names,
            num_names_needed=num_registered_targets,
            update_collection=False,
            var_name_for_log='registered_target_names')

        ################################################################
        # choose unreg_timeout_names
        ################################################################
        unreg_timeout_names = self.choose_names(
            name_collection=self.unregistered_names,
            num_names_needed=num_unreg_timeouts,
            update_collection=False,
            var_name_for_log='unreg_timeout_names')

        ################################################################
        # choose exit_names
        ################################################################
        exit_names = self.choose_names(
            name_collection=active_names,
            num_names_needed=num_exit_timeouts,
            update_collection=True,
            var_name_for_log='exit_names')

        ################################################################
        # choose full_q_names
        ################################################################
        full_q_names = self.choose_names(
            name_collection=active_names,
            num_names_needed=num_full_q_timeouts,
            update_collection=True,
            var_name_for_log='full_q_names')

        ################################################################
        # send msgs to senders so we have some on their queues so we
        # can verify partially paired for any threads that are exited
        ################################################################
        ################################################################
        # setup the messages to send
        ################################################################
        sender_msgs: dict[str, str] = {}
        for name in sender_names:
            sender_msgs[name] = (f'recv test: {name} sending msg '
                                 f'at {self.get_ptime()}')

        sender_1_msg_1: dict[str, str] = {}
        if exit_names and num_senders >= 2:
            for exit_name in exit_names:
                sender_1_msg_1[exit_name] = f'send test: {self.get_ptime()}'
                log_msg = f'log test: {self.get_ptime()}'

                send_msg_serial_num = self.add_cmd(
                    SendMsg(cmd_runners=exit_name,
                            receivers=sender_names[1],
                            msgs_to_send=sender_1_msg_1,
                            log_msg=log_msg))

                ########################################################
                # confirm the send_msg
                ########################################################
                self.add_cmd(
                    ConfirmResponse(cmd_runners=self.commander_name,
                                    confirm_cmd='SendMsg',
                                    confirm_serial_num=send_msg_serial_num,
                                    confirmers=[exit_name]))

        sender_2_msg_1: dict[str, str] = {}
        sender_2_msg_2: dict[str, str] = {}
        if exit_names and num_senders == 3:
            for exit_name in exit_names:
                sender_2_msg_1[exit_name] = f'send test: {self.get_ptime()}'
                send_msg_serial_num = self.add_cmd(
                    SendMsg(cmd_runners=exit_name,
                            receivers=sender_names[2],
                            msgs_to_send=sender_2_msg_1))

                ########################################################
                # confirm the send_msg
                ########################################################
                self.add_cmd(
                    ConfirmResponse(cmd_runners=[self.commander_name],
                                    confirm_cmd='SendMsg',
                                    confirm_serial_num=send_msg_serial_num,
                                    confirmers=[exit_name]))

                sender_2_msg_2[exit_name] = f'send test: {self.get_ptime()}'
                log_msg = f'log test: {self.get_ptime()}'

                send_msg_serial_num = self.add_cmd(
                    SendMsg(cmd_runners=exit_name,
                            receivers=sender_names[2],
                            msgs_to_send=sender_2_msg_2,
                            log_msg=log_msg))

                ########################################################
                # confirm the send_msg
                ########################################################
                self.add_cmd(
                    ConfirmResponse(cmd_runners=[self.commander_name],
                                    confirm_cmd='SendMsg',
                                    confirm_serial_num=send_msg_serial_num,
                                    confirmers=[exit_name]))

        ################################################################
        # send max msgs if needed
        ################################################################
        # fullq_msgs: list[str] = []
        if full_q_names:
            for idx in range(self.max_msgs):
                # send from each sender thread to ensure we get
                # exactly max_msgs on each pair between sender and the
                # full_q targets
                # fullq_msgs.append(f'send test: {self.get_ptime()}')
                send_msg_serial_num = self.add_cmd(
                    SendMsg(cmd_runners=sender_names,
                            receivers=full_q_names,
                            msgs_to_send=sender_msgs))

                ########################################################
                # confirm the send_msg
                ########################################################
                self.add_cmd(
                    ConfirmResponse(cmd_runners=[self.commander_name],
                                    confirm_cmd='SendMsg',
                                    confirm_serial_num=send_msg_serial_num,
                                    confirmers=sender_names))

        ################################################################
        # build exit and join suites for the exit names
        ################################################################
        if exit_names:
            for idx in range(1, num_exit_timeouts):
                # the idea here is to have the first exit_name have zero
                # msgs, the second will have 1 msg, etc, etc, etc...
                for num_msgs in range(idx):
                    log_msg = f'log test: {self.get_ptime()}'
                    send_msg_serial_num = self.add_cmd(
                        SendMsg(cmd_runners=sender_names,
                                receivers=exit_names[idx],
                                msgs_to_send=sender_msgs,
                                log_msg=log_msg))

                    ####################################################
                    # confirm the send_msg
                    ####################################################
                    self.add_cmd(
                        ConfirmResponse(cmd_runners=[self.commander_name],
                                        confirm_cmd='SendMsg',
                                        confirm_serial_num=send_msg_serial_num,
                                        confirmers=sender_names))

            self.build_exit_suite(names=exit_names)
            self.build_join_suite(
                cmd_runners=self.commander_name,
                join_target_names=exit_names)

            for exit_name in exit_names:
                self.add_cmd(VerifyPairedNot(
                    cmd_runners=self.commander_name,
                    exp_not_paired_names=[exit_name, sender_names[0]]))

            if num_senders >= 2:
                for exit_name in exit_names:
                    self.add_cmd(VerifyPairedHalf(
                        cmd_runners=self.commander_name,
                        pair_names=[exit_name, sender_names[1]],
                        exp_half_paired_names=sender_names[1]))

            if num_senders == 3:
                for exit_name in exit_names:
                    self.add_cmd(VerifyPairedHalf(
                        cmd_runners=self.commander_name,
                        pair_names=[exit_name, sender_names[2]],
                        exp_half_paired_names=sender_names[2]))

        all_targets: list[str] = (active_target_names
                                  + registered_target_names
                                  + unreg_timeout_names
                                  + exit_names
                                  + full_q_names)

        if timeout_type == TimeoutType.TimeoutTrue:
            send_msg_serial_num = self.add_cmd(
                SendMsgTimeoutTrue(
                    cmd_runners=sender_names,
                    receivers=all_targets,
                    msgs_to_send=sender_msgs,
                    timeout=2.0,
                    unreg_timeout_names=unreg_timeout_names+exit_names,
                    fullq_timeout_names=full_q_names))

            confirm_cmd_to_use = 'SendMsgTimeoutTrue'
            final_recv_names = active_target_names + registered_target_names
        else:
            if timeout_type == TimeoutType.TimeoutFalse:
                send_msg_serial_num = self.add_cmd(
                    SendMsgTimeoutFalse(
                        cmd_runners=sender_names,
                        receivers=all_targets,
                        msgs_to_send=sender_msgs,
                        timeout=3.0))

                confirm_cmd_to_use = 'SendMsgTimeoutFalse'
            else:
                send_msg_serial_num = self.add_cmd(
                    SendMsg(cmd_runners=sender_names,
                            receivers=all_targets,
                            msgs_to_send=sender_msgs))
                confirm_cmd_to_use = 'SendMsg'

            self.add_cmd(WaitForSendTimeouts(
                cmd_runners=self.commander_name,
                sender_names=sender_names,
                unreg_names=unreg_timeout_names + exit_names,
                fullq_names=full_q_names))

            # restore config by adding back the exited threads and
            # creating the un_reg threads so send_msg will complete
            # before timing out
            if unreg_timeout_names or exit_names:
                f1_create_items: list[F1CreateItem] = []
                for idx, name in enumerate(unreg_timeout_names + exit_names):
                    if idx % 2:
                        app_config = AppConfig.ScriptStyle
                    else:
                        app_config = AppConfig.RemoteThreadApp

                    f1_create_items.append(F1CreateItem(name=name,
                                                        auto_start=True,
                                                        target_rtn=outer_f1,
                                                        app_config=app_config))
                # for name in unreg_timeout_names + exit_names:
                #     f1_create_items.append(F1CreateItem(name=name,
                #                            auto_start=True,
                #                            target_rtn=outer_f1))
                self.build_create_suite(
                    f1_create_items=f1_create_items,
                    validate_config=False)

            # tell the fullq threads to read the stacked up msgs
            # so that the send_msg will complete
            if full_q_names:
                for idx in range(self.max_msgs):
                    self.add_cmd(
                        RecvMsg(cmd_runners=full_q_names,
                                senders=sender_names,
                                exp_msgs=sender_msgs))

            final_recv_names = all_targets

        ################################################################
        # confirm the send_msg
        ################################################################
        self.add_cmd(
            ConfirmResponse(cmd_runners=[self.commander_name],
                            confirm_cmd=confirm_cmd_to_use,
                            confirm_serial_num=send_msg_serial_num,
                            confirmers=sender_names))

        # start any registered threads
        if registered_target_names:
            self.build_start_suite(start_names=registered_target_names)

        # do RecvMsg to verify the SendMsg for targets
        if final_recv_names:
            log_msg = f'log test: {self.get_ptime()}'
            recv_msg_serial_num = self.add_cmd(
                RecvMsg(cmd_runners=final_recv_names,
                        senders=sender_names,
                        exp_msgs=sender_msgs,
                        log_msg=log_msg))

            ############################################################
            # confirm the recv_msg
            ############################################################
            self.add_cmd(
                ConfirmResponse(cmd_runners=[self.commander_name],
                                confirm_cmd='RecvMsg',
                                confirm_serial_num=recv_msg_serial_num,
                                confirmers=final_recv_names))

        ################################################################
        # do RecvMsg to verify the SendMsg for senders
        ################################################################
        if exit_names:
            if num_senders >= 2:
                for exit_name in exit_names:
                    recv_msg_serial_num = self.add_cmd(
                        RecvMsg(cmd_runners=sender_names[1],
                                senders=exit_name,
                                exp_msgs=sender_1_msg_1,
                                del_deferred=exit_name))

                    ####################################################
                    # confirm the recv_msg
                    ####################################################
                    self.add_cmd(
                        ConfirmResponse(cmd_runners=[self.commander_name],
                                        confirm_cmd='RecvMsg',
                                        confirm_serial_num=recv_msg_serial_num,
                                        confirmers=[sender_names[1]]))

            if num_senders == 3:
                for exit_name in exit_names:
                    recv_msg_serial_num = self.add_cmd(
                        RecvMsg(cmd_runners=sender_names[2],
                                senders=exit_name,
                                exp_msgs=sender_2_msg_1,
                                del_deferred=exit_name))

                    ####################################################
                    # confirm the recv_msg
                    ####################################################
                    self.add_cmd(
                        ConfirmResponse(cmd_runners=[self.commander_name],
                                        confirm_cmd='RecvMsg',
                                        confirm_serial_num=recv_msg_serial_num,
                                        confirmers=[sender_names[2]]))

                    recv_msg_serial_num = self.add_cmd(
                        RecvMsg(cmd_runners=sender_names[2],
                                senders=exit_name,
                                exp_msgs=sender_2_msg_2,
                                del_deferred=exit_name))

                    ####################################################
                    # confirm the recv_msg
                    ####################################################
                    self.add_cmd(
                        ConfirmResponse(cmd_runners=[self.commander_name],
                                        confirm_cmd='RecvMsg',
                                        confirm_serial_num=recv_msg_serial_num,
                                        confirmers=[sender_names[2]]))

            # exit the exit names again after senders have read their
            # pending messages, and then verify exit names and senders
            # are no longer paired
            if timeout_type != TimeoutType.TimeoutTrue:
                self.build_exit_suite(names=exit_names)
                self.build_join_suite(
                    cmd_runners=self.commander_name,
                    join_target_names=exit_names)

            for sender_name in sender_names:
                exp_not_paired = [sender_name] + exit_names
                self.add_cmd(VerifyPairedNot(
                    cmd_runners=self.commander_name,
                    exp_not_paired_names=exp_not_paired))

    ####################################################################
    # build_simple_scenario
    ####################################################################

    def build_simple_scenario(self) -> None:
        """Add config cmds to the scenario queue.

        """
        self.add_cmd(CreateCommanderAutoStart(
            cmd_runners='alpha',
            commander_name='alpha'))
        self.add_cmd(ValidateConfig(
            cmd_runners='alpha'))
        self.add_cmd(CreateF1AutoStart(
            cmd_runners='alpha',
            f1_create_items=[F1CreateItem(name='beta',
                                          auto_start=True,
                                          target_rtn=outer_f1),
                             F1CreateItem(name='charlie',
                                          auto_start=True,
                                          target_rtn=outer_f1,
                                          app_config
                                          =AppConfig.RemoteThreadApp)]))
        self.add_cmd(Pause(
            cmd_runners='alpha',
            pause_seconds=0.5))
        self.add_cmd(CreateF1NoStart(
            cmd_runners='alpha',
            f1_create_items=[F1CreateItem(name='delta',
                                          auto_start=False,
                                          target_rtn=outer_f1,
                                          app_config
                                          =AppConfig.ScriptStyle),
                             F1CreateItem(name='echo',
                                          auto_start=False,
                                          target_rtn=outer_f1,
                                          app_config
                                          =AppConfig.RemoteThreadApp)]))
        self.add_cmd(VerifyInRegistry(
            cmd_runners='alpha',
            exp_in_registry_names=['alpha', 'beta', 'charlie', 'delta',
                                   'echo']))
        self.add_cmd(VerifyAlive(
            cmd_runners='alpha',
            exp_alive_names=['alpha', 'beta', 'charlie']))
        self.add_cmd(VerifyAliveNot(
            cmd_runners='alpha',
            exp_not_alive_names=['delta', 'echo']))
        self.add_cmd(VerifyActive(
            cmd_runners='alpha',
            exp_active_names=['alpha', 'beta', 'charlie']))
        self.add_cmd(VerifyRegistered(
            cmd_runners='alpha',
            exp_registered_names=['delta', 'echo']))
        self.add_cmd(VerifyStatus(
            cmd_runners='alpha',
            check_status_names=['alpha', 'beta', 'charlie'],
            expected_status=st.ThreadStatus.Alive))
        self.add_cmd(VerifyStatus(
            cmd_runners='alpha',
            check_status_names=['delta', 'echo'],
            expected_status=st.ThreadStatus.Registered))
        self.add_cmd(VerifyPaired(
            cmd_runners='alpha',
            exp_paired_names=['alpha', 'beta', 'charlie', 'delta', 'echo']))
        self.add_cmd(StartThread(
            cmd_runners='alpha',
            start_names=['delta', 'echo']))
        self.add_cmd(VerifyAlive(
            cmd_runners='alpha',
            exp_alive_names=['alpha', 'beta', 'charlie', 'delta', 'echo']))
        self.add_cmd(VerifyActive(
            cmd_runners='alpha',
            exp_active_names=['alpha', 'beta', 'charlie', 'delta', 'echo']))
        self.add_cmd(VerifyStatus(
            cmd_runners='alpha',
            check_status_names=['alpha', 'beta', 'charlie', 'delta', 'echo'],
            expected_status=st.ThreadStatus.Alive))
        self.add_cmd(ValidateConfig(
            cmd_runners='alpha'))
        ################################################################
        # send_msg
        ################################################################
        msgs_to_send: dict[str, Any] = {'delta': 'send msg from delta',
                                        'echo': 'send msg from echo'}
        send_msg_serial_num = self.add_cmd(
            SendMsg(cmd_runners=['delta', 'echo'],
                    receivers=['alpha', 'beta', 'charlie'],
                    msgs_to_send=msgs_to_send))

        ################################################################
        # confirm the send_msg
        ################################################################
        self.add_cmd(
            ConfirmResponse(cmd_runners='alpha',
                            confirm_cmd='SendMsg',
                            confirm_serial_num=send_msg_serial_num,
                            confirmers=['delta', 'echo']))
        ################################################################
        # recv_msg
        ################################################################
        recv_msg_serial_num = self.add_cmd(
            RecvMsg(cmd_runners=['alpha', 'beta', 'charlie'],
                    senders=['delta', 'echo'],
                    exp_msgs=msgs_to_send,
                    log_msg='RecvMsg log message'))

        ################################################################
        # confirm the recv_msg
        ################################################################
        self.add_cmd(
            ConfirmResponse(cmd_runners='alpha',
                            confirm_cmd='RecvMsg',
                            confirm_serial_num=recv_msg_serial_num,
                            confirmers=['alpha', 'beta', 'charlie']))
        self.add_cmd(StopThread(cmd_runners='alpha',
                                stop_names=['beta', 'charlie',
                                            'delta', 'echo']))
        self.add_cmd(VerifyAliveNot(
            cmd_runners='alpha',
            exp_not_alive_names=['beta', 'charlie', 'delta', 'echo']))
        self.add_cmd(ValidateConfig(
            cmd_runners='alpha'))
        self.add_cmd(Join(
            cmd_runners='alpha',
            join_names=['beta', 'charlie', 'delta', 'echo']))
        # self.add_cmd(Pause(
        #     cmd_runners='alpha',
        #     pause_seconds=2))
        self.add_cmd(ValidateConfig(
            cmd_runners='alpha'))

    ####################################################################
    # build_start_suite
    ####################################################################
    def build_start_suite(self,
                          start_names: list[str],
                          validate_config: Optional[bool] = True
                          ) -> None:
        """Return a list of ConfigCmd items for unregister.

        Args:
            start_names: thread names to be started
            validate_config: indicates whether to validate the config

        """
        if not set(start_names).issubset(self.registered_names):
            self.abort_all_f1_threads()
            raise InvalidInputDetected(f'Input {start_names} is not a subset '
                                       'of registered names '
                                       f'{self.registered_names}')

        self.add_cmd(
            StartThread(cmd_runners=self.commander_name,
                        start_names=start_names))
        self.add_cmd(VerifyActive(
                cmd_runners=self.commander_name,
                exp_active_names=start_names))

        if validate_config:
            self.add_cmd(ValidateConfig(cmd_runners=self.commander_name))

        self.registered_names -= set(start_names)
        self.active_names |= set(start_names)

    ####################################################################
    # build_start_suite_num
    ####################################################################
    def build_start_suite_num(self,
                              num_to_start: int) -> None:
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

        return self.build_start_suite(start_names=names)


    ####################################################################
    # build_unreg_suite
    ####################################################################
    def build_unreg_suite(self,
                          names: list[str]) -> None:
        """Return a list of ConfigCmd items for unregister.

        Args:
            names: thread name to be unregistered

        """
        if not set(names).issubset(self.registered_names):
            self.abort_all_f1_threads()
            raise InvalidInputDetected(f'Input {names} is not a subset '
                                       'of registered names '
                                       f'{self.registered_names}')

        self.add_cmd(Unregister(cmd_runners=self.commander_name,
                                unregister_targets=names))
        self.add_cmd(VerifyInRegistryNot(
            cmd_runners=self.commander_name,
            exp_not_in_registry_names=names))
        self.add_cmd(VerifyPairedNot(
            cmd_runners=self.commander_name,
            exp_not_paired_names=names))

        self.add_cmd(ValidateConfig(cmd_runners=self.commander_name))

        self.registered_names -= set(names)
        self.unregistered_names |= set(names)

    ####################################################################
    # build_unreg_suite_num
    ####################################################################
    def build_unreg_suite_num(self,
                              num_to_unreg: int) -> None:
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

    ####################################################################
    # choose_names
    ####################################################################
    def choose_names(
            self,
            name_collection: set[str],
            num_names_needed: int,
            update_collection: bool,
            var_name_for_log: str) -> list[str]:
        """Return a list of names picked from a set and issue log msg.

        Args:
            name_collection: set of names to choose from
            num_names_needed: number of names to choose
            update_collection: indicates whether to remove the chosen names
                from the set of names
            var_name_for_log: variable name to use for the log msg

        Returns:
            a list of names
        """
        chosen_names: list[str] = []
        if num_names_needed > 0:
            chosen_names = list(
                random.sample(name_collection, num_names_needed))
        if update_collection:
            name_collection -= set(chosen_names)

        log_msg = f'{var_name_for_log}: {chosen_names}'
        self.log_ver.add_msg(log_msg=re.escape(log_msg))
        logger.debug(log_msg)

        return chosen_names

    ####################################################################
    # create_commander_thread
    ####################################################################
    def create_commander_thread(self,
                                name: str,
                                auto_start: bool) -> None:
        """Create the commander thread."""
        create_event = threading.Event()

        if not self.commander_thread:
            self.commander_thread = st.SmartThread(
                name=name, auto_start=auto_start, max_msgs=self.max_msgs)
        self.all_threads[name] = self.commander_thread

        self.monitor_add_items.append(MonitorAddItem(
            cmd_runner=name,
            thread_alive=True,
            auto_start=False,
            expected_status=st.ThreadStatus.Alive,
            add_event=create_event))

        log_msg = 'create_commander_thread waiting for monitor'
        self.log_ver.add_msg(log_msg=re.escape(log_msg))
        logger.debug(log_msg)
        create_event.wait()
        # item_found = True
        # while item_found:
        #     item_found = False
        #     with self.ops_lock:
        #         for item in self.monitor_add_items:
        #             if item.cmd_runner == name:
        #                 item_found = True
        #                 time.sleep(0.1)

        log_msg = 'create_commander_thread exiting'
        self.log_ver.add_msg(log_msg=re.escape(log_msg))
        logger.debug(log_msg)

    ####################################################################
    # create_f1_thread
    ####################################################################
    def create_f1_thread(self,
                         cmd_runner: str,
                         target: Callable,
                         name: str,
                         app_config: AppConfig,
                         auto_start: bool = True
                         ) -> None:
        """Create the f1_thread.

        Args:
            cmd_runner: name of thread doing the create
            target: the f1 routine that the thread will run
            name: name of the thread
            app_config: specifies the style of app to create
            auto_start: indicates whether the create should start the
                          thread
        """
        self.f1_process_cmds[name] = True

        if app_config == AppConfig.ScriptStyle:
            f1_thread = st.SmartThread(name=name,
                                       target=target,
                                       args=(name, self),
                                       auto_start=auto_start,
                                       max_msgs=self.max_msgs)
        elif app_config == AppConfig.RemoteThreadApp:
            f1_outer_app = OuterF1ThreadApp(
                config_ver=self,
                name=name,
                auto_start=auto_start,
                max_msgs=self.max_msgs)
            f1_thread = f1_outer_app.smart_thread

        self.f1_threads[name] = f1_thread
        self.all_threads[name] = f1_thread

        if auto_start:
            exp_status = st.ThreadStatus.Alive
        else:
            exp_status = st.ThreadStatus.Registered
        create_event = threading.Event()
        self.monitor_add_items.append(MonitorAddItem(
            cmd_runner=name,
            thread_alive=auto_start,
            auto_start=auto_start,
            expected_status=exp_status,
            add_event=create_event))

        log_msg = 'create_f1_thread waiting for monitor'
        self.log_ver.add_msg(log_msg=re.escape(log_msg))
        logger.debug(log_msg)
        create_event.wait()
        # item_found = True
        # while item_found:
        #     item_found = False
        #     with self.ops_lock:
        #         for item in self.monitor_add_items:
        #             if item.cmd_runner == name:
        #                 item_found = True
        #                 time.sleep(0.1)

        log_msg = 'create_f1_thread exiting'
        self.log_ver.add_msg(log_msg=re.escape(log_msg))
        logger.debug(log_msg)

    ####################################################################
    # dec_ops_count
    ####################################################################
    def dec_ops_count(self,
                      cmd_runner: str,
                      sender: str) -> None:
        """Decrement the pending operations count.

        Args:
            cmd_runner: the names of the thread whose count is to be
                decremented
            sender: the name of the threads that is paired with the
                cmd_runner

        """
        pair_key = st.SmartThread._get_pair_key(cmd_runner, sender)
        doc_log_msg = (f'dec_ops_count entered for {cmd_runner=} with '
                       f'{pair_key=}')
        self.log_ver.add_msg(log_msg=re.escape(doc_log_msg))
        logger.debug(doc_log_msg)

        with self.ops_lock:
            self.expected_pairs[pair_key][cmd_runner].pending_ops_count -= 1
            if self.expected_pairs[pair_key][cmd_runner].pending_ops_count < 0:
                self.abort_all_f1_threads()
                raise InvalidConfigurationDetected(
                    f'dec_ops_count for for pair_key {pair_key}, '
                    f'name {cmd_runner} was decremented below zero')

            # indicate that this thread might need to update pair array
            self.pending_recv_msg_par[cmd_runner] = True

            # remove sender from list if deferred delete is not needed
            self.recv_msg_event_items[cmd_runner].senders.remove(sender)

            # determine whether deferred delete is needed
            if (self.expected_pairs[pair_key][
                    cmd_runner].pending_ops_count == 0
                    and sender not in self.expected_pairs[pair_key].keys()):
                # we need to post later when we do the pair array update
                self.recv_msg_event_items[
                    cmd_runner].deferred_post_needed = True
                doc_log_msg = (f'dec_ops_count for {cmd_runner=} with '
                               f'{pair_key=} set deferred_post_needed')
                self.log_ver.add_msg(log_msg=re.escape(doc_log_msg))
                logger.debug(doc_log_msg)

            # post handle_recv_msg if all receives are now processed
            if (not self.recv_msg_event_items[cmd_runner].senders
                    and not self.recv_msg_event_items[
                        cmd_runner].deferred_post_needed):
                self.recv_msg_event_items[cmd_runner].recv_event.set()

    ####################################################################
    # dec_recv_timeout
    ####################################################################
    def dec_recv_timeout(self):
        with self.ops_lock:
            self.expected_num_recv_timouts -= 1

    ####################################################################
    # del_thread
    ####################################################################
    def del_thread(self,
                   cmd_runner: str,
                   del_name: str,
                   process: str,
                   del_msg_idx: int
                   ) -> None:
        """Delete the thread from the ConfigVerifier.

        Args:
            cmd_runner: name of thread doing the delete (for log msg)
            del_name: name of thread to be deleted
            process: names the process, either join or unregister
            del_msg_idx: index in the log for the del message
        """
        log_msg = (f'del_thread entered: {cmd_runner=}, '
                   f'{del_name=}, {process=}')
        self.log_ver.add_msg(log_msg=re.escape(log_msg))
        logger.debug(log_msg)

        updated_pair_array_msg_needed = False
        if process == 'join':
            from_status = st.ThreadStatus.Alive
        else:
            from_status = st.ThreadStatus.Registered

        self.expected_registered[del_name].is_alive = False
        self.expected_registered[del_name].status = st.ThreadStatus.Stopped
        self.add_log_msg(
            f'{cmd_runner} set status for thread '
            f'{del_name} '
            f'from {from_status} to '
            f'{st.ThreadStatus.Stopped}')

        self.handle_exp_status_log_msgs(log_idx=del_msg_idx)
        # for thread_name, tracker in self.expected_registered.items():
        #     if thread_name in log_array.status_array:
        #         is_alive = log_array.status_array[thread_name].is_alive
        #         status = log_array.status_array[thread_name].status
        #         repr_to_use = tracker.thread_repr
        #         if 'OuterF1ThreadApp' in repr_to_use:
        #             if is_alive:
        #                 repr_to_use = repr_to_use.replace(
        #                     'stopped',
        #                     'started')
        #                 if status != st.ThreadStatus.Registered:
        #                     repr_to_use = repr_to_use.replace(
        #                         'initial',
        #                         'started')
        #             else:
        #                 repr_to_use = repr_to_use.replace(
        #                     'started',
        #                     'stopped')
        #                 if status != st.ThreadStatus.Registered:
        #                     repr_to_use = repr_to_use.replace(
        #                         'initial',
        #                         'started')
        #
        #         log_msg = (
        #             f"key = {thread_name}, item = {repr_to_use}, "
        #             "item.thread.is_alive() = "
        #             f"{is_alive}, "
        #             f"status: {status}")
        #         self.add_log_msg(re.escape(log_msg))

        del self.expected_registered[del_name]
        self.deleted_remotes_complete_count[del_name] += 1
        self.add_log_msg(f'{cmd_runner} removed {del_name} from registry '
                         f'for {process=}')

        self.add_log_msg(f'{cmd_runner} entered _refresh_pair_array')

        pair_keys_to_delete = []
        with self.ops_lock:
            for pair_key in self.expected_pairs:
                if del_name not in pair_key:
                    continue
                if del_name == pair_key[0]:
                    other_name = pair_key[1]
                else:
                    other_name = pair_key[0]

                if del_name not in self.expected_pairs[pair_key].keys():
                    self.abort_all_f1_threads()
                    raise InvalidConfigurationDetected(
                        f'The expected_pairs for pair_key {pair_key} '
                        'contains an entry of '
                        f'{self.expected_pairs[pair_key]}  which does not '
                        f'include the {del_name=} being deleted')
                # if other_name not in self.expected_pairs[pair_key].keys():
                #     pair_keys_to_delete.append(pair_key)
                # elif self.expected_pairs[pair_key][
                #         other_name].pending_ops_count == 0:
                #     pair_keys_to_delete.append(pair_key)
                #     self.add_log_msg(re.escape(
                #         f"{name} removed status_blocks entry "
                #         f"for pair_key = {pair_key}, "
                #         f"name = {other_name}"))
                # else:
                #     del self.expected_pairs[pair_key][remote]

                if other_name not in self.expected_pairs[pair_key].keys():
                    pair_keys_to_delete.append(pair_key)
                else:
                    removed_search = (f'{cmd_runner} removed '
                                      f'{del_name} from registry')
                    removed_msg, rem_idx = self.get_log_msg(
                        search_msg=removed_search,
                        skip_num=0,
                        start_idx=0,
                        end_idx=del_msg_idx,
                        reverse_search=True)
                    if rem_idx == -1:
                        raise FailedToFindLogMsg('Missing log msg '
                                                 f'{removed_search=}')

                    # nondef_key = (
                    # pair_key[0], pair_key[1], other_name, cmd_runner)
                    # num_non_def = self.del_nondef_pairs_msg_count[
                    #     nondef_key]
                    nondef_log_msg = (
                        f"{cmd_runner} removed status_blocks entry "
                        f"for pair_key = {pair_key}, "
                        f"name = {other_name}")
                    ndef_msg, ndef_idx = self.get_log_msg(
                        search_msg=re.escape(nondef_log_msg),
                        skip_num=0,
                        start_idx=rem_idx,
                        end_idx=-1,
                        reverse_search=False)
                    # if self.find_log_msgs(
                    #         search_msgs=nondef_log_msg,
                    #         num_instances=num_non_def + 1):
                    if ndef_msg:
                        # self.del_nondef_pairs_msg_count[nondef_key] += 1
                        pair_keys_to_delete.append(pair_key)
                        self.add_log_msg(re.escape(nondef_log_msg))
                        log_msg = (f'del_thread for {cmd_runner=}, '
                                   f'{del_name=}, {process=} '
                                   f'found at {ndef_idx=}, {nondef_log_msg=}')
                        self.log_ver.add_msg(log_msg=re.escape(log_msg))
                        logger.debug(log_msg)
                    else:
                        log_msg = (f'del_thread for {cmd_runner=}, '
                                   f'{del_name=}, {process=} '
                                   f'did not find {nondef_log_msg=}')
                        self.log_ver.add_msg(log_msg=re.escape(log_msg))
                        logger.debug(log_msg)
                        del self.expected_pairs[pair_key][del_name]
                self.add_log_msg(re.escape(
                    f"{cmd_runner} removed status_blocks entry "
                    f"for pair_key = {pair_key}, "
                    f"name = {del_name}"))
                updated_pair_array_msg_needed = True

            for pair_key in pair_keys_to_delete:
                log_msg = (f'del_thread for {cmd_runner=}, '
                           f'{del_name=}, {process=} deleted '
                           f'{pair_key=}')
                self.log_ver.add_msg(log_msg=re.escape(log_msg))
                logger.debug(log_msg)
                del self.expected_pairs[pair_key]
                self.add_log_msg(re.escape(
                    f'{cmd_runner} removed _pair_array entry'
                    f' for pair_key = {pair_key}'))
                updated_pair_array_msg_needed = True

            # self.add_log_msg(re.escape(
            #     f'{cmd_runner} updated _pair_array at UTC '
            #     f'{copy_pair_deque.popleft().strftime("%H:%M:%S.%f")}')
            # )
            if updated_pair_array_msg_needed:
                upa_search_msg = (
                    f"{cmd_runner} updated _pair_array at UTC {time_match}")
                found_upa_msg, upa_pos = self.get_log_msg(
                    search_msg=upa_search_msg,
                    skip_num=self.found_update_pair_array_log_msgs[cmd_runner])
                if found_upa_msg:
                    self.found_update_pair_array_log_msgs[cmd_runner] += 1
                    self.add_log_msg(re.escape(found_upa_msg))

            pair_key = st.SmartThread._get_pair_key(cmd_runner,
                                                    del_name)
            utc_search_msg = (
                f"{cmd_runner} did cleanup of registry at UTC "
                f'{time_match}, '
                f"deleted \['{del_name}'\]")

            found_utc_msg, utc_pos = self.get_log_msg(
                search_msg=utc_search_msg,
                skip_num=self.found_utc_log_msgs[pair_key])
            if found_utc_msg:
                self.found_utc_log_msgs[pair_key] += 1
                log_msg = 'del_thread found a utc msg'
                self.log_ver.add_msg(log_msg=re.escape(log_msg))
                logger.debug(log_msg)

                self.add_log_msg(re.escape(found_utc_msg))
            # self.add_log_msg(re.escape(
            #     f"{cmd_runner} did cleanup of registry at UTC "
            #     f'{copy_reg_deque.popleft().strftime("%H:%M:%S.%f")}, '
            #     f"deleted ['{del_name}']"))

            self.add_log_msg(f'{cmd_runner} did successful '
                             f'{process} of {del_name}.')

        log_msg = (f'del_thread exit: {cmd_runner=}, '
                   f'{del_name=}, {process=}')
        self.log_ver.add_msg(log_msg=re.escape(log_msg))
        logger.debug(log_msg)

    ####################################################################
    # exit_thread
    ####################################################################
    def exit_thread(self,
                    f1_name: str):
        """Drive the commands received on the command queue.

        Args:
            f1_name: name of thread doing the command

        """
        self.f1_process_cmds[f1_name] = False

    ####################################################################
    # f1_driver
    ####################################################################
    def f1_driver(self,
                  f1_name: str):
        """Drive the commands received on the command queue.

        Args:
            f1_name: name of thread doing the command

        """
        self.log_ver.add_call_seq(
            name='f1_driver',
            seq='test_smart_thread.py::ConfigVerifier.f1_driver')

        # We will stay in this loop to process command while the
        # f1_process_cmds dictionary entry for f1_name is True. The
        # ConfigCmdExitThread cmd runProcess method will simply set the
        # dictionary entry for f1_name to False so that we will then
        # exit after we indicate that the cmd is complete
        while self.f1_process_cmds[f1_name]:

            cmd: ConfigCmd = self.msgs.get_msg(f1_name, timeout=None)

            cmd.run_process(name=f1_name)

            self.completed_cmds[f1_name].append(cmd.serial_num)

    ####################################################################
    # find_log_msgs
    ####################################################################
    def find_log_msgs(self,
                      search_msgs: StrOrList,
                      num_instances: int = 1) -> bool:
        if isinstance(search_msgs, str):
            search_msgs = [search_msgs]
        work_msgs: list[re.Pattern] = []
        for msg in search_msgs:
            work_msgs.append(re.compile(re.escape(msg)))
        num_tries_remaining = 2
        while num_tries_remaining:
            num_tries_remaining -= 1
            found_idxes: list[int] = []
            for idx in range(len(work_msgs)):
                found_idxes.append(0)
            for log_tuple in self.caplog_to_use.record_tuples:
                for idx, msg in enumerate(work_msgs):
                    if msg.match(log_tuple[2]):
                        found_idxes[idx] += 1
                        # if len(found_idxes) == len(work_msgs):
                        #     return True
            failed_instance_count = False
            for cnt in found_idxes:
                if cnt != num_instances:
                    failed_instance_count = True
                    break

            if failed_instance_count:
                if num_tries_remaining:
                    time.sleep(1.5)
                    continue
                return False

            if num_tries_remaining == 1:
                return True
            else:
                assert False

        return True

    ####################################################################
    # get_is_alive
    ####################################################################
    # def get_is_alive(self, name: str) -> bool:
    #     """Get the is_alive flag for the named thread.
    #
    #     Args:
    #         name: thread to get the is_alive flag
    #
    #     """
    #     if self.expected_registered[name].exiting:
    #         return self.expected_registered[name].thread.thread.is_alive()
    #     else:
    #         return self.expected_registered[name].is_alive

    ####################################################################
    # get_log_msg
    ####################################################################
    def get_log_msg(self,
                    search_msg: str,
                    skip_num: int = 0,
                    start_idx: int = 0,
                    end_idx: int = -1,
                    reverse_search: bool = False) -> str:
        """Search for a log message and return it.

        Args:
            search_msg: log message to search for as a regex
            skip_num: number of matches to skip
            start_idx: index from which to start
            end_idx: index of 1 past the index at which to stop
            reverse_search: indicates whether to search from the bottom

        Returns:
            the log message if found, otherwise an empty string
        """
        search_pattern: re.Pattern = re.compile(search_msg)
        num_skipped = 0
        work_log = self.caplog_to_use.record_tuples.copy()

        if end_idx == -1:
            end_idx = len(work_log)

        work_log = work_log[start_idx:end_idx]
        if reverse_search:
            work_log.reverse()

        for idx, log_tuple in enumerate(work_log):
            if search_pattern.match(log_tuple[2]):
                if num_skipped == skip_num:
                    if reverse_search:
                        ret_idx = start_idx + (len(work_log) - idx) - 1
                    else:
                        ret_idx = start_idx + idx
                    return log_tuple[2], ret_idx
                num_skipped += 1

        return '', -1

    ####################################################################
    # get_log_msgs
    ####################################################################
    def get_log_msgs(self):
        """Search for a log messages and return them in order."""
        # we should never call with an non-empty deque
        assert not self.log_found_items

        work_log = self.caplog_to_use.record_tuples.copy()

        end_idx = len(work_log)

        # return if no new log message have been issued since last call
        if self.log_start_idx >= end_idx:
            return

        work_log = work_log[self.log_start_idx:end_idx]
        # work_log.reverse()

        start_idx = self.log_start_idx
        found_idx = start_idx - 1

        for idx, log_tuple in enumerate(work_log):
            for log_search_item in self.log_search_items:
                if log_search_item.search_pattern.match(log_tuple[2]):
                    # found_idx = start_idx + (len(work_log) - idx) - 1
                    found_idx = start_idx + idx
                    found_log_item = log_search_item.get_found_log_item(
                        found_log_msg=log_tuple[2],
                        found_log_idx=found_idx
                    )
                    self.log_found_items.append(found_log_item)

        # update next starting point
        self.log_start_idx = found_idx + 1

    ####################################################################
    # get_ptime
    ####################################################################
    @staticmethod
    def get_ptime() -> str:
        """Returns a printable UTC time stamp.

        Returns:
            a timestamp as a strring
        """
        now_time = datetime.utcnow()
        print_time = now_time.strftime("%H:%M:%S.%f")

        return print_time

    ####################################################################
    # get_ptime
    ####################################################################
    def handle_deferred_delete_log_msgs(self,
                                        cmd_runner: str) -> bool:
        """Issue the log message for a deferred delete

        Args:
            cmd_runner: thread doing the delete

        Returns:
            True if the refresh array was updated, False otherwise
        """
        # Next, we need to figure out whether we did our own
        # delete and possible the delete for another receiver
        refresh_array_updated = False
        for del_def_key, count in self.del_def_pairs_count.items():
            if self.del_def_pairs_msg_count[del_def_key] < count:
                ind_key = (del_def_key[0],
                           del_def_key[1],
                           del_def_key[2],
                           cmd_runner)
                num_found = self.del_def_pairs_msg_ind_count[ind_key]
                # See if we removed the receiver (might be us).
                # Note that the sender will have been deleted by
                # the join if it went first (in which case we
                # will find one of the receivers doing the
                # delete for themselves or others.
                pair_key = (del_def_key[0], del_def_key[1])
                receiver_name = del_def_key[2]
                log_msg2 = (
                    f"{cmd_runner} removed status_blocks entry "
                    f"for pair_key = {pair_key}, "
                    f"name = {receiver_name}")
                log_msg3 = (
                    f'{cmd_runner} removed _pair_array entry'
                    f' for pair_key = {pair_key}')
                if self.find_log_msgs(
                        search_msgs=[log_msg2, log_msg3],
                        num_instances=num_found + 1):
                    refresh_array_updated = True
                    self.add_log_msg(re.escape(log_msg2))
                    self.add_log_msg(re.escape(log_msg3))

                    self.del_def_pairs_msg_count[del_def_key] += 1
                    self.del_def_pairs_msg_ind_count[ind_key] += 1

        return refresh_array_updated

    ####################################################################
    # handle_enter_rpa_log_msg
    ####################################################################
    def handle_enter_rpa_log_msg(self,
                                 cmd_runner: str) -> None:
        """Drive the commands received on the command queue.

        Args:
            cmd_runner: name of thread doing the pair array refresh

        """
        # There could be zero, one, or several threads that have
        # received a message aad have the potential to update the
        # pair array in the case where a deferred delete was done.
        # These thread names will have been added to the
        # pending_recv_msg_par when they issued the recv_msg log msg.
        # We are now handling the enter _pair_array_refresh log
        # message that follows the recv_msg, but also follows a register
        # update or delete. The race is on. If the issuer (cmd_runner)
        # of the enter _pair_array_refresh message is indeed the pending
        # recv_msg, then we will continue to allow that thread to
        # remain pending until the third step occurs, the pair array
        # updated log message is issued. Any other case will cause us to
        # reset the pending_recv_msg_par to empty.
        with self.ops_lock:
            if self.pending_recv_msg_par[cmd_runner]:
                self.pending_recv_msg_par = defaultdict(bool)
                self.pending_recv_msg_par[cmd_runner] = True
            else:  # anyone else is no longer eligible either
                self.pending_recv_msg_par = defaultdict(bool)

    ####################################################################
    # handle_exp_status_log_msgs
    ####################################################################
    def handle_exp_status_log_msgs(self,
                                   log_idx: int,
                                   name: Optional[str] = None
                                   ) -> None:
        """Add a thread to the ConfigVerifier.

        Args:
            log_idx: index of either register or delete msg
            name: name to check to skip log msg
        """
        for a_name, tracker in self.expected_registered.items():
            # ignore the new thread for now - we are in reg cleanup just
            # before we add the new thread
            if name and a_name == name:
                continue

            search_msg = f'key = {a_name}, item = SmartThread'

            log_msg, log_pos = self.get_log_msg(search_msg=search_msg,
                                                skip_num=0,
                                                start_idx=0,
                                                end_idx=log_idx,
                                                reverse_search=True)
            if log_msg:
                self.status_array_log_counts[a_name] += 1
                self.add_log_msg(re.escape(log_msg))

    ####################################################################
    # handle_join
    ####################################################################
    def handle_join(self,
                    cmd_runner: str,
                    join_names: list[str],
                    log_msg: str) -> None:

        """Handle the join execution and log msgs.

        Args:
            cmd_runner: name of thread doing the cmd
            join_names: target threads that we will join
            log_msg: log message to issue on the join (name be None)

        """
        self.log_ver.add_call_seq(
            name='handle_join',
            seq='test_smart_thread.py::ConfigVerifier.handle_join')

        for join_name in join_names:
            self.deleted_remotes_pending_count[join_name] += 1
            self.monitor_del_items.append(MonitorItem(
                cmd_runner=cmd_runner,
                target_name=join_name,
                process_name='join'))

        self.all_threads[cmd_runner].join(
            targets=set(join_names),
            log_msg=log_msg)

        if log_msg:
            log_msg_2 = (
                f'{self.log_ver.get_call_seq("handle_join")} ')
            log_msg_3 = re.escape(f'{log_msg}')
            for enter_exit in ('entry', 'exit'):
                log_msg_1 = re.escape(
                    f'join() {enter_exit}: {cmd_runner} to join '
                    f'{sorted(set(join_names))}. ')

                self.add_log_msg(log_msg_1 + log_msg_2 + log_msg_3)

        log_msg = 'handle_join waiting for monitor'
        self.log_ver.add_msg(log_msg=re.escape(log_msg))
        logger.debug(log_msg)


        while self.monitor_del_items:
            time.sleep(0.1)
        log_msg = 'handle_join exiting'
        self.log_ver.add_msg(log_msg=re.escape(log_msg))
        logger.debug(log_msg)

    ####################################################################
    # handle_join_tof
    ####################################################################
    def handle_join_tof(self,
                        cmd_runner: str,
                        join_names: list[str],
                        timeout: IntOrFloat,
                        log_msg: str) -> None:

        """Handle the join execution and log msgs.

        Args:
            cmd_runner: name of thread doing the cmd
            join_names: target threads that we will join
            timeout: timeout value to specify on join
            log_msg: log message to issue on the join (name be None)

        """
        self.log_ver.add_call_seq(
            name='handle_join_tof',
            seq='test_smart_thread.py::ConfigVerifier.handle_join_tof')

        for join_name in join_names:
            self.deleted_remotes_pending_count[join_name] += 1
            self.monitor_del_items.append(MonitorItem(
                cmd_runner=cmd_runner,
                target_name=join_name,
                process_name='join'))

        self.all_threads[cmd_runner].join(
            targets=set(join_names),
            timeout=timeout,
            log_msg=log_msg)

        if log_msg:
            log_msg_2 = (
                f'{self.log_ver.get_call_seq("handle_join_tof")} ')
            log_msg_3 = re.escape(f'{log_msg}')
            for enter_exit in ('entry', 'exit'):
                log_msg_1 = re.escape(
                    f'join() {enter_exit}: {cmd_runner} to join '
                    f'{sorted(set(join_names))}. ')

                self.add_log_msg(log_msg_1 + log_msg_2 + log_msg_3)

        log_msg = 'handle_join_tof waiting for monitor'
        self.log_ver.add_msg(log_msg=re.escape(log_msg))
        logger.debug(log_msg)
        while self.monitor_del_items:
            time.sleep(0.1)
        log_msg = 'handle_join_tof exiting'
        self.log_ver.add_msg(log_msg=re.escape(log_msg))
        logger.debug(log_msg)

    ####################################################################
    # handle_join_tot
    ####################################################################
    def handle_join_tot(self,
                        cmd_runner: str,
                        join_names: list[str],
                        timeout: IntOrFloat,
                        timeout_names: list[str],
                        log_msg: str) -> None:

        """Handle the join execution and log msgs.

        Args:
            cmd_runner: name of thread doing the cmd
            join_names: target threads that we will join
            timeout: timeout value to specify on join
            timeout_names: targets that are expected to timeout
            log_msg: log message to issue on the join (name be None)

        """
        self.log_ver.add_call_seq(
            name='handle_join_tot',
            seq='test_smart_thread.py::ConfigVerifier.handle_join_tot')

        for join_name in join_names:
            if timeout_names and join_name in timeout_names:
                continue
            self.deleted_remotes_pending_count[join_name] += 1
            self.monitor_del_items.append(MonitorItem(
                cmd_runner=cmd_runner,
                target_name=join_name,
                process_name='join'))

        with pytest.raises(st.SmartThreadJoinTimedOut):
            self.all_threads[cmd_runner].join(
                targets=set(join_names),
                timeout=timeout,
                log_msg=log_msg)

        timeout_log_msg = (
            f'{cmd_runner} raising SmartThreadJoinTimedOut '
            f'waiting for {sorted(set(timeout_names))}')
        self.log_ver.add_msg(
            log_name='scottbrian_paratools.smart_thread',
            log_level=logging.ERROR,
            log_msg=re.escape(timeout_log_msg))

        if log_msg:
            log_msg_2 = (
                f'{self.log_ver.get_call_seq("handle_join_tot")} ')
            log_msg_3 = re.escape(f'{log_msg}')
            log_msg_1 = re.escape(
                f'join() entry: {cmd_runner} to join '
                f'{sorted(set(join_names))}. ')

            self.add_log_msg(log_msg_1 + log_msg_2 + log_msg_3)

        log_msg = 'handle_join_tot waiting for monitor'
        self.log_ver.add_msg(log_msg=re.escape(log_msg))
        logger.debug(log_msg)
        while self.monitor_del_items:
            time.sleep(0.1)
        log_msg = 'handle_join_tot exiting'
        self.log_ver.add_msg(log_msg=re.escape(log_msg))
        logger.debug(log_msg)

    ####################################################################
    # handle_join_unreg_update
    ####################################################################
    def handle_join_unreg_update(self,
                                 cmd_runner: str,
                                 target_name: str,
                                 process: str,
                                 found_log_msg_idx: int) -> None:
        """Handle update pair array log message.

        Args:
            cmd_runner: name of thread that did the pair array update
            target_name: thread that we joined or unregistered
            process: either join or unreg
            found_log_msg_idx: index of the join unreg message in the
                log
        """
        self.del_thread(
            cmd_runner=cmd_runner,
            del_name=target_name,
            process=process,
            del_msg_idx=found_log_msg_idx)

        with self.ops_lock:
            for item in self.monitor_del_items:
                if (item.cmd_runner == cmd_runner
                        and item.target_name == target_name
                        and item.process_name == 'join'):
                    self.monitor_del_items.remove(item)
                    break

    ####################################################################
    # handle_pair_array_update
    ####################################################################
    def handle_pair_array_update(self,
                                 cmd_runner: str,
                                 upa_msg: str,
                                 upa_msg_idx: int) -> None:
        """Handle update pair array log message.

        Args:
            cmd_runner: name of thread that did the pair array update
            upa_msg: message for the pair array update
            upa_msg_idx: index of the update message in the log
        """
        hpau_log_msg = f'handle_pair_array_update entry for {cmd_runner=}'
        self.log_ver.add_msg(log_msg=re.escape(hpau_log_msg))
        logger.debug(hpau_log_msg)

        # if this is not for recv_msg then we have nothing to do here
        if not self.pending_recv_msg_par[cmd_runner]:
            return

        # ################################################################
        # # determine whether the update is by create, join, unregister,
        # # or recv_msg
        # ################################################################
        # recv_msg_search = f'{cmd_runner} received msg from [a-z]+'
        # enter_rpa_search = f'{cmd_runner} entered _refresh_pair_array'
        # reg_update_search = f'[a-z]+ did registry update at UTC {time_match}'
        # reg_remove_search = ("[a-z]+ removed [a-z]+ from registry for "
        #                      "process='(join|unregister)'")
        #
        # recv_msg_msg, rmm_idx = self.get_log_msg(
        #     search_msg=recv_msg_search,
        #     skip_num=0,
        #     start_idx=0,
        #     end_idx=upa_msg_idx,
        #     reverse_search=True)
        # if rmm_idx == -1:
        #     hpau_log_msg = (f'handle_pair_array_update for {cmd_runner=} '
        #                     f'returning: recv_msg not found')
        #     self.log_ver.add_msg(log_msg=re.escape(hpau_log_msg))
        #     logger.debug(hpau_log_msg)
        #     return  # not a recv_msg update
        #
        # enter_rpa_msg, erm_idx = self.get_log_msg(
        #     search_msg=enter_rpa_search,
        #     skip_num=0,
        #     start_idx=rmm_idx,
        #     end_idx=upa_msg_idx,
        #     reverse_search=True)
        # if erm_idx == -1:
        #     hpau_log_msg = (f'handle_pair_array_update for {cmd_runner=} '
        #                     f'returning: enter _refresh_pair_array not found')
        #     self.log_ver.add_msg(log_msg=re.escape(hpau_log_msg))
        #     logger.debug(hpau_log_msg)
        #     return  # not a recv_msg update
        #
        # reg_update_msg, rum_idx = self.get_log_msg(
        #     search_msg=reg_update_search,
        #     skip_num=0,
        #     start_idx=rmm_idx,
        #     end_idx=upa_msg_idx,
        #     reverse_search=True)
        # if rmm_idx < rum_idx:
        #     hpau_log_msg = (f'handle_pair_array_update for {cmd_runner=} '
        #                     f'returning: reg update found after recv_msg')
        #     self.log_ver.add_msg(log_msg=re.escape(hpau_log_msg))
        #     logger.debug(hpau_log_msg)
        #     return  # register did the update, not recv_msg
        #
        # reg_remove_msg, rrm_idx = self.get_log_msg(
        #     search_msg=reg_remove_search,
        #     skip_num=0,
        #     start_idx=rmm_idx,
        #     end_idx=upa_msg_idx,
        #     reverse_search=True)
        # if rmm_idx < rrm_idx:
        #     hpau_log_msg = (f'handle_pair_array_update for {cmd_runner=} '
        #                     f'returning: reg remove found after recv_msg')
        #     self.log_ver.add_msg(log_msg=re.escape(hpau_log_msg))
        #     logger.debug(hpau_log_msg)
        #     return  # join or unregister did the update, not recv_msg

        ################################################################
        # At this point we know that the recv_msg did the update
        ################################################################
        self.add_log_msg(re.escape(
            f'{cmd_runner} entered _refresh_pair_array'))

        self.update_pair_array(cmd_runner=cmd_runner,
                               upa_msg=upa_msg)

        if self.recv_msg_event_items[cmd_runner].deferred_post_needed:
            self.recv_msg_event_items[cmd_runner].recv_event.set()
            hpau_log_msg = (f'handle_pair_array_update for {cmd_runner=} '
                            f'posted handle_recv_msg')
            self.log_ver.add_msg(log_msg=re.escape(hpau_log_msg))
            logger.debug(hpau_log_msg)

        hpau_log_msg = f'handle_pair_array_update exit for {cmd_runner=}'
        self.log_ver.add_msg(log_msg=re.escape(hpau_log_msg))
        logger.debug(hpau_log_msg)

    ####################################################################
    # handle_recv_msg
    ####################################################################
    def handle_recv_msg(self,
                        cmd_runner: str,
                        senders: list[str],
                        exp_msgs: Any,
                        del_deferred: Union[list[str], None],
                        log_msg: str) -> None:

        """Handle the send_recv_cmd execution and log msgs.

        Args:
            cmd_runner: name of thread doing the cmd
            senders: names of the senders
            exp_msgs: expected messages by sender name
            del_deferred: names of senders who might exit and cause the
                receiver to be marked as delete deferred
            log_msg: log message to isee on recv_msg

        """
        handle_recv_log_msg = (f'{cmd_runner=} handle_recv entry for '
                               f'{senders=} and {del_deferred=}')
        self.log_ver.add_msg(log_msg=re.escape(handle_recv_log_msg))
        logger.debug(handle_recv_log_msg)

        self.log_ver.add_call_seq(
            name='handle_recv_msg',
            seq='test_smart_thread.py::ConfigVerifier.handle_recv_msg')

        self.recv_msg_event_items[cmd_runner] = RecvEventItem(
            recv_event=threading.Event(),
            deferred_post_needed=False,
            senders=senders.copy()
        )

        if del_deferred:
            with self.ops_lock:
                for del_sender in del_deferred:
                    pair_key = st.SmartThread._get_pair_key(cmd_runner,
                                                            del_sender)
                    del_def_key: tuple[str, str, str] = (pair_key[0],
                                                         pair_key[1],
                                                         cmd_runner)
                    self.del_def_pairs_count[del_def_key] += 1

        for from_name in senders:
            recvd_msg = self.all_threads[cmd_runner].recv_msg(
                remote=from_name,
                log_msg=log_msg)

            if log_msg:
                log_msg_2 = (
                    f'{self.log_ver.get_call_seq("handle_recv_msg")} ')
                log_msg_3 = re.escape(f'{log_msg}')
                for enter_exit in ('entry', 'exit'):
                    log_msg_1 = re.escape(
                        f'recv_msg() {enter_exit}: '
                        f'{cmd_runner} <- {from_name}. ')

                    self.add_log_msg(log_msg_1 + log_msg_2 + log_msg_3)

            assert recvd_msg == exp_msgs[from_name]

            recv_log_msg = f"{cmd_runner} received msg from {from_name}"
            self.log_ver.add_msg(
                log_name='scottbrian_paratools.smart_thread',
                log_level=logging.INFO,
                log_msg=recv_log_msg)

        wait_log_msg = f'{cmd_runner=} handle_recv waiting for monitor'
        self.log_ver.add_msg(log_msg=re.escape(wait_log_msg))
        logger.debug(wait_log_msg)

        self.recv_msg_event_items[cmd_runner].recv_event.wait()

        handle_recv_log_msg = f'{cmd_runner=} handle_recv exiting'
        self.log_ver.add_msg(log_msg=re.escape(handle_recv_log_msg))
        logger.debug(handle_recv_log_msg)

    ####################################################################
    # handle_recv_msg_tof
    ####################################################################
    def handle_recv_msg_tof(self,
                            cmd_runner: str,
                            senders: list[str],
                            exp_msgs: Any,
                            timeout: IntOrFloat,
                            del_deferred: Union[list[str], None],
                            log_msg: str) -> None:

        """Handle the send_recv_cmd execution and log msgs.

        Args:
            cmd_runner: name of thread doing the cmd
            senders: names of the senders
            exp_msgs: expected messages by sender name
            timeout: number of seconds to wait for message
            del_deferred: names of senders who might exit and cause the
                receiver to be marked as delete deferred
            log_msg: log message to isee on recv_msg

        """
        handle_recv_log_msg = (f'{cmd_runner=} handle_recv_tof entry for '
                               f'{senders=} and {del_deferred=}')
        self.log_ver.add_msg(log_msg=re.escape(handle_recv_log_msg))
        logger.debug(handle_recv_log_msg)

        self.log_ver.add_call_seq(
            name='handle_recv_msg_tof',
            seq='test_smart_thread.py::ConfigVerifier.handle_recv_msg_tof')

        self.recv_msg_event_items[cmd_runner] = RecvEventItem(
            recv_event=threading.Event(),
            deferred_post_needed=False,
            senders=senders.copy()
        )

        if del_deferred:
            with self.ops_lock:
                for del_sender in del_deferred:
                    pair_key = st.SmartThread._get_pair_key(cmd_runner,
                                                            del_sender)
                    del_def_key: tuple[str, str, str] = (pair_key[0],
                                                         pair_key[1],
                                                         cmd_runner)
                    self.del_def_pairs_count[del_def_key] += 1

        for from_name in senders:
            recvd_msg = self.all_threads[cmd_runner].recv_msg(
                remote=from_name,
                timeout=timeout,
                log_msg=log_msg)

            if log_msg:
                log_msg_2 = (
                    f'{self.log_ver.get_call_seq("handle_recv_msg_tof")} ')
                log_msg_3 = re.escape(f'{log_msg}')
                for enter_exit in ('entry', 'exit'):
                    log_msg_1 = re.escape(
                        f'recv_msg() {enter_exit}: '
                        f'{cmd_runner} <- {from_name}. ')

                    self.add_log_msg(log_msg_1 + log_msg_2 + log_msg_3)

            assert recvd_msg == exp_msgs[from_name]

            recv_log_msg = f"{cmd_runner} received msg from {from_name}"
            self.log_ver.add_msg(
                log_name='scottbrian_paratools.smart_thread',
                log_level=logging.INFO,
                log_msg=recv_log_msg)

        wait_log_msg = f'{cmd_runner=} handle_recv_tof waiting for monitor'
        self.log_ver.add_msg(log_msg=re.escape(wait_log_msg))
        logger.debug(wait_log_msg)

        self.recv_msg_event_items[cmd_runner].recv_event.wait()

        handle_recv_log_msg = f'{cmd_runner=} handle_recv_tof exiting'
        self.log_ver.add_msg(log_msg=re.escape(handle_recv_log_msg))
        logger.debug(handle_recv_log_msg)

    ####################################################################
    # handle_recv_msg_tot
    ####################################################################
    def handle_recv_msg_tot(self,
                            cmd_runner: str,
                            senders: list[str],
                            exp_msgs: Any,
                            timeout: IntOrFloat,
                            timeout_names: list[str],
                            del_deferred: Union[list[str], None],
                            log_msg: str) -> None:

        """Handle the send_recv_cmd execution and log msgs.

        Args:
            cmd_runner: name of thread doing the cmd
            senders: names of the senders
            exp_msgs: expected messages by sender name
            timeout: number of seconds to wait for message
            timeout_names: names of senders that are delayed to cause a
                timeout while receiving
            del_deferred: names of senders who might exit and cause the
                receiver to be marked as delete deferred
            log_msg: log message to isee on recv_msg

        """
        handle_recv_log_msg = (f'{cmd_runner=} handle_recv_tot entry for '
                               f'{senders=} and {del_deferred=}')
        self.log_ver.add_msg(log_msg=re.escape(handle_recv_log_msg))
        logger.debug(handle_recv_log_msg)

        self.log_ver.add_call_seq(
            name='handle_recv_msg_tot',
            seq='test_smart_thread.py::ConfigVerifier.handle_recv_msg_tot')

        non_timeout_senders = list(set(senders) - set(timeout_names))
        self.recv_msg_event_items[cmd_runner] = RecvEventItem(
            recv_event=threading.Event(),
            deferred_post_needed=False,
            senders=non_timeout_senders.copy()
        )

        if del_deferred:
            with self.ops_lock:
                for del_sender in del_deferred:
                    pair_key = st.SmartThread._get_pair_key(cmd_runner,
                                                            del_sender)
                    del_def_key: tuple[str, str, str] = (pair_key[0],
                                                         pair_key[1],
                                                         cmd_runner)
                    self.del_def_pairs_count[del_def_key] += 1

        timeout_true_value = timeout
        for from_name in senders:
            enter_exit_list = ('entry', 'exit')
            if from_name not in timeout_names:
                recvd_msg = self.all_threads[cmd_runner].recv_msg(
                    remote=from_name,
                    timeout=timeout_true_value,
                    log_msg=log_msg)
            else:
                enter_exit_list = ('entry', )
                with pytest.raises(st.SmartThreadRecvMsgTimedOut):
                    recvd_msg = self.all_threads[cmd_runner].recv_msg(
                        remote=from_name,
                        timeout=timeout_true_value,
                        log_msg=log_msg)

                # remaining timeouts are shorter so we don't have
                # to pause for the cumulative timeouts before
                # sending messages
                timeout_true_value = 0.2
                recv_log_msg = (
                    f'{cmd_runner} raising SmartThreadRecvMsgTimedOut '
                    f'waiting for {from_name}')
                self.log_ver.add_msg(
                    log_name='scottbrian_paratools.smart_thread',
                    log_level=logging.ERROR,
                    log_msg=recv_log_msg)
                self.dec_recv_timeout()

            if log_msg:
                log_msg_2 = (
                    f'{self.log_ver.get_call_seq("handle_recv_msg_tot")} ')
                log_msg_3 = re.escape(f'{log_msg}')
                for enter_exit in enter_exit_list:
                    log_msg_1 = re.escape(
                        f'recv_msg() {enter_exit}: '
                        f'{cmd_runner} <- {from_name}. ')

                    self.add_log_msg(log_msg_1 + log_msg_2 + log_msg_3)

            if 'exit' in enter_exit_list:
                assert recvd_msg == exp_msgs[from_name]

                recv_log_msg = f"{cmd_runner} received msg from {from_name}"
                self.log_ver.add_msg(
                    log_name='scottbrian_paratools.smart_thread',
                    log_level=logging.INFO,
                    log_msg=recv_log_msg)

        wait_log_msg = f'{cmd_runner=} handle_recv_tot waiting for monitor'
        self.log_ver.add_msg(log_msg=re.escape(wait_log_msg))
        logger.debug(wait_log_msg)

        self.recv_msg_event_items[cmd_runner].recv_event.wait()

        handle_recv_log_msg = f'{cmd_runner=} handle_recv_tof exiting'
        self.log_ver.add_msg(log_msg=re.escape(handle_recv_log_msg))
        logger.debug(handle_recv_log_msg)

    ####################################################################
    # handle_reg_remove
    ####################################################################
    def handle_reg_remove(self) -> None:

        """Handle the send_cmd execution and log msgs."""
        with self.ops_lock:
            # reg remove means that recv_msgs are no longer pending
            self.pending_recv_msg_par = defaultdict(bool)

    ####################################################################
    # handle_reg_update
    ####################################################################
    def handle_reg_update(self,
                          cmd_runner: str,
                          reg_update_msg: str,
                          reg_update_msg_log_idx) -> None:

        """Handle the send_cmd execution and log msgs.

        Args:
            cmd_runner: name of thread doing the cmd
            reg_update_msg: register update log message
            reg_update_msg_log_idx: index in the log for the message

        """
        with self.ops_lock:
            # reg update means that recv_msgs are no longer pending
            self.pending_recv_msg_par = defaultdict(bool)

            found_add_item = False
            for item in self.monitor_add_items:
                if item.cmd_runner == cmd_runner:
                    found_add_item = True
                    self.add_thread(
                        name=cmd_runner,
                        thread_alive=item.thread_alive,
                        auto_start=item.auto_start,
                        expected_status=item.expected_status,
                        reg_update_msg=reg_update_msg,
                        reg_idx=reg_update_msg_log_idx
                    )
                    item.add_event.set()
                    self.monitor_add_items.remove(item)
                    self.found_reg_log_msgs += 1
                    break
            if not found_add_item:
                raise InvalidConfigurationDetected(
                    f'{cmd_runner} issued log msg {reg_update_msg} '
                    f'but a monitor_add_item was not found')

    ####################################################################
    # handle_send_msg
    ####################################################################
    def handle_send_msg(self,
                        cmd_runner: str,
                        receivers: list[str],
                        msg_to_send: Any,
                        log_msg: str) -> None:

        """Handle the send_cmd execution and log msgs.

        Args:
            cmd_runner: name of thread doing the cmd
            receivers: names of threads to receive the message
            msg_to_send: message to send to the receivers
            log_msg: log message for send_msg to issue

        """
        self.log_ver.add_call_seq(
            name='handle_send_msg',
            seq='test_smart_thread.py::ConfigVerifier.handle_send_msg')
        ops_count_names = receivers.copy()
        self.inc_ops_count(ops_count_names, cmd_runner)

        self.all_threads[cmd_runner].send_msg(
            targets=set(receivers),
            msg=msg_to_send,
            log_msg=log_msg)

        if log_msg:
            log_msg_2 = f'{self.log_ver.get_call_seq("handle_send_msg")} '
            log_msg_3 = re.escape(f'{log_msg}')
            for enter_exit in ('entry', 'exit'):
                log_msg_1 = re.escape(
                    f'send_msg() {enter_exit}: {cmd_runner} -> '
                    f'{set(receivers)}. ')
                self.add_log_msg(log_msg_1 + log_msg_2 + log_msg_3)

        for name in ops_count_names:
            log_msg = f'{cmd_runner} sent message to {name}'
            self.log_ver.add_msg(
                log_name='scottbrian_paratools.smart_thread',
                log_level=logging.INFO,
                log_msg=log_msg)

    ####################################################################
    # handle_send_msg_tof
    ####################################################################
    def handle_send_msg_tof(
            self,
            cmd_runner: str,
            receivers: list[str],
            msg_to_send: Any,
            timeout: IntOrFloat,
            log_msg: str) -> None:

        """Handle the send_cmd execution and log msgs.

        Args:
            cmd_runner: name of thread doing the cmd
            receivers: names of threads to receive the message
            msg_to_send: message to send to the receivers
            timeout: number of seconds to specify on send_msg timeout
            log_msg: log message for send_msg to issue

        """
        self.log_ver.add_call_seq(
            name='handle_send_msg_tof',
            seq='test_smart_thread.py::ConfigVerifier.handle_send_msg_tof')
        ops_count_names = receivers.copy()
        self.inc_ops_count(ops_count_names, cmd_runner)

        self.all_threads[cmd_runner].send_msg(
            targets=set(receivers),
            msg=msg_to_send,
            log_msg=log_msg,
            timeout=timeout)

        if log_msg:
            log_msg_2 = f'{self.log_ver.get_call_seq("handle_send_msg_tof")} '
            log_msg_3 = re.escape(f'{log_msg}')
            for enter_exit in ('entry', 'exit'):
                log_msg_1 = re.escape(
                    f'send_msg() {enter_exit}: {cmd_runner} -> '
                    f'{set(receivers)}. ')
                self.add_log_msg(log_msg_1 + log_msg_2 + log_msg_3)

        for name in ops_count_names:
            log_msg = f'{cmd_runner} sent message to {name}'
            self.log_ver.add_msg(
                log_name='scottbrian_paratools.smart_thread',
                log_level=logging.INFO,
                log_msg=log_msg)

    ####################################################################
    # handle_send_msg_tot
    ####################################################################
    def handle_send_msg_tot(
            self,
            cmd_runner: str,
            receivers: list[str],
            msg_to_send: Any,
            timeout: IntOrFloat,
            unreg_timeout_names: list[str],
            fullq_timeout_names: list[str],
            log_msg: str) -> None:

        """Handle the send_cmd execution and log msgs.

        Args:
            cmd_runner: name of thread doing the cmd
            receivers: names of threads to receive the message
            msg_to_send: message to send to the receivers
            timeout: number of seconds to specify on send_msg timeout
            unreg_timeout_names: names that are unregistered
            fullq_timeout_names: names with a full msgq
            log_msg: log message for send_msg to issue

        """
        self.log_ver.add_call_seq(
            name='handle_send_msg_tot',
            seq='test_smart_thread.py::ConfigVerifier.handle_send_msg_tot')
        ops_count_names = receivers.copy()
        if unreg_timeout_names:
            ops_count_names = list(
                set(ops_count_names)
                - set(unreg_timeout_names))
        if fullq_timeout_names:
            ops_count_names = list(
                set(ops_count_names)
                - set(fullq_timeout_names))

        self.inc_ops_count(ops_count_names, cmd_runner)

        with pytest.raises(st.SmartThreadSendMsgTimedOut):
            self.all_threads[cmd_runner].send_msg(
                targets=set(receivers),
                msg=msg_to_send,
                log_msg=log_msg,
                timeout=timeout)

        unreg_timeout_msg = ''
        if unreg_timeout_names:
            unreg_timeout_msg = (
                'Remotes unregistered: '
                f'{sorted(set(unreg_timeout_names))}. ')

        fullq_timeout_msg = ''
        if fullq_timeout_names:
            fullq_timeout_msg = (
                'Remotes with full send queue: '
                f'{sorted(set(fullq_timeout_names))}.')

        self.add_log_msg(re.escape(
            f'{cmd_runner} timeout of a send_msg(). '
            f'Targets: {sorted(set(receivers))}. '
            f'{unreg_timeout_msg}'
            f'{fullq_timeout_msg}'))

        self.add_log_msg(
            'Raise SmartThreadSendMsgTimedOut',
            log_level=logging.ERROR)

        if log_msg:
            log_msg_2 = f'{self.log_ver.get_call_seq("handle_send_msg_tot")} '
            log_msg_3 = re.escape(f'{log_msg}')
            log_msg_1 = re.escape(
                f'send_msg() entry: {cmd_runner} -> '
                f'{set(receivers)}. ')
            self.add_log_msg(log_msg_1 + log_msg_2 + log_msg_3)

        for name in ops_count_names:
            log_msg = f'{cmd_runner} sent message to {name}'
            self.log_ver.add_msg(
                log_name='scottbrian_paratools.smart_thread',
                log_level=logging.INFO,
                log_msg=log_msg)

    ####################################################################
    # inc_ops_count
    ####################################################################
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

    ####################################################################
    # log_name_groups
    ####################################################################
    def log_name_groups(self) -> None:
        """Issue log msgs to show the names in each set."""
        log_msg = f'unregistered_names: {sorted(self.unregistered_names)}'
        self.log_ver.add_msg(log_msg=re.escape(log_msg))
        logger.debug(log_msg)

        log_msg = f'registered_names: {sorted(self.registered_names)}'
        self.log_ver.add_msg(log_msg=re.escape(log_msg))
        logger.debug(log_msg)

        log_msg = f'active_names: {sorted(self.active_names)}'
        self.log_ver.add_msg(log_msg=re.escape(log_msg))
        logger.debug(log_msg)

        log_msg = f'stopped_names: {sorted(self.stopped_names)}'
        self.log_ver.add_msg(log_msg=re.escape(log_msg))
        logger.debug(log_msg)

    ####################################################################
    # main_driver
    ####################################################################
    def main_driver(self) -> None:
        """Delete the thread from the ConfigVerifier."""
        self.log_ver.add_call_seq(
            name='main_driver',
            seq='test_smart_thread.py::ConfigVerifier.main_driver')

        while self.cmd_suite:
            cmd: ConfigCmd = self.cmd_suite.popleft()
            log_msg = f'config_cmd: {cmd}'
            self.log_ver.add_msg(log_msg=re.escape(log_msg))
            logger.debug(log_msg)

            for name in cmd.cmd_runners:
                if name == self.commander_name:
                    continue
                self.msgs.queue_msg(target=name,
                                    msg=cmd)

            if self.commander_name in cmd.cmd_runners:
                cmd.run_process(name=self.commander_name)
                self.completed_cmds[self.commander_name].append(cmd.serial_num)

        self.monitor_exit = True
        self.monitor_thread.join()

    ####################################################################
    # set_is_alive
    ####################################################################
    # def set_is_alive(self, target: str, value: bool, exiting: bool):
    #     """Set the is_alive flag and exiting flag.
    #
    #     Args:
    #         target: the thread to set the flags for
    #         value: the True or False value for is_alive flag
    #         exiting: the Tru or False value for the exiting flag
    #
    #     """
    #     with self.ops_lock:
    #         self.expected_registered[target].is_alive = value
    #         self.expected_registered[
    #             target].exiting = exiting

    ####################################################################
    # set_recv_timeout
    ####################################################################
    def set_recv_timeout(self, num_timeouts: int):
        with self.ops_lock:
            self.expected_num_recv_timouts = num_timeouts

    ####################################################################
    # start_thread
    ####################################################################
    def start_thread(self,
                     start_names: list[str]) -> None:
        """Start the named thread.

        Args:
            start_names: names of the threads to start
        """
        for start_name in start_names:
            self.f1_threads[start_name].start()
            self.expected_registered[start_name].is_alive = True
            self.expected_registered[start_name].status = st.ThreadStatus.Alive

            self.add_log_msg(
                f'{start_name} set status for thread {start_name} '
                'from ThreadStatus.Registered to ThreadStatus.Starting')
            self.add_log_msg(
                f'{start_name} set status for thread {start_name} '
                f'from ThreadStatus.Starting to ThreadStatus.Alive')
            self.add_log_msg(re.escape(
                f'{start_name} thread started, thread.is_alive() = True, '
                'status: ThreadStatus.Alive'))

    ####################################################################
    # stop_thread
    ####################################################################
    def stop_thread(self,
                    cmd_runner: str,
                    stop_names: list[str]) -> None:
        """Start the named thread.

        Args:
            cmd_runner: name of thread doing the stop thread
            stop_names: names of the threads to stop
        """
        for stop_name in stop_names:
            exit_cmd = ExitThread(cmd_runners=stop_name)
            self.add_cmd_info(exit_cmd)
            self.msgs.queue_msg(target=stop_name,
                                msg=exit_cmd)

        work_names = stop_names.copy()
        while work_names:
            for stop_name in work_names:
                if not self.all_threads[stop_name].thread.is_alive():
                    with self.ops_lock:
                        if stop_name in self.expected_registered:
                            self.expected_registered[
                                stop_name].is_alive = False
                    work_names.remove(stop_name)
                    break
                time.sleep(0.1)

    ####################################################################
    # unregister_threads
    ####################################################################
    def unregister_threads(self,
                           cmd_runner: str,
                           unregister_targets: list[str]) -> None:
        """Unregister the named threads.

        Args:
            cmd_runner: name of thread doing the unregister
            unregister_targets: names of threads to be unregistered
        """
        self.all_threads[cmd_runner].unregister(
            targets=set(unregister_targets))

        # self.del_thread(
        #     name=cmd_runner,
        #     num_remotes=len(unregister_targets),
        #     process='unregister'
        # )

    ####################################################################
    # unregister_threads
    ####################################################################
    def update_pair_array(self,
                          cmd_runner: str,
                          upa_msg: str) -> None:
        """Unregister the named threads.

        Args:
            cmd_runner: name of thread doing the update
            upa_msg: message that got us here

        """
        updated_pair_array_msg_needed = False
        pair_keys_to_delete = []
        with self.ops_lock:
            for pair_key in self.expected_pairs:
                if (pair_key[0] not in self.expected_registered
                        and pair_key[0] in self.expected_pairs[pair_key]):
                    del self.expected_pairs[pair_key][pair_key[0]]
                    updated_pair_array_msg_needed = True
                    self.add_log_msg(re.escape(
                        f"{cmd_runner} removed status_blocks entry "
                        f"for pair_key = {pair_key}, "
                        f"name = {pair_key[0]}"))
                if (pair_key[1] not in self.expected_registered
                        and pair_key[1] in self.expected_pairs[pair_key]):
                    del self.expected_pairs[pair_key][pair_key[1]]
                    updated_pair_array_msg_needed = True
                    self.add_log_msg(re.escape(
                        f"{cmd_runner} removed status_blocks entry "
                        f"for pair_key = {pair_key}, "
                        f"name = {pair_key[1]}"))
                if len(self.expected_pairs[pair_key]) == 1:
                    remaining_name = list(
                        self.expected_pairs[pair_key].keys())[0]
                    if self.expected_pairs[pair_key][
                            remaining_name].pending_ops_count == 0:
                        del self.expected_pairs[pair_key][remaining_name]
                        updated_pair_array_msg_needed = True
                        self.add_log_msg(re.escape(
                            f"{cmd_runner} removed status_blocks entry "
                            f"for pair_key = {pair_key}, "
                            f"name = {remaining_name}"))
                if not self.expected_pairs[pair_key]:
                    pair_keys_to_delete.append(pair_key)

            for pair_key in pair_keys_to_delete:
                del self.expected_pairs[pair_key]
                self.add_log_msg(re.escape(
                    f'{cmd_runner} removed _pair_array entry'
                    f' for pair_key = {pair_key}'))
                updated_pair_array_msg_needed = True
        if updated_pair_array_msg_needed:
            self.add_log_msg(re.escape(upa_msg))

    ####################################################################
    # validate_config
    ####################################################################
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
                    f'that has status of {thread.status} '
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
                        f'ConfigVerifier found that for the '
                        f'expected_pairs entry for pair_key {pair_key}, '
                        f'the entry for {name} has has a pending_ops_count '
                        f'of {ops_count}, but the SmartThread._pair_array'
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

    ####################################################################
    # verify_counts
    ####################################################################
    def verify_counts(self,
                      num_registered: Optional[int] = None,
                      num_active: Optional[int] = None,
                      num_stopped: Optional[int] = None) -> None:
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
                self.abort_all_f1_threads()
                raise InvalidConfigurationDetected(
                    f'verify_counts found expected {num_registered=} is not '
                    f'equal to {registered_found_real=} and/or '
                    f'{registered_found_mock=}')

        if num_active is not None:
            if not (num_active
                    == active_found_real
                    == active_found_mock):
                self.abort_all_f1_threads()
                raise InvalidConfigurationDetected(
                    f'verify_counts found expected {num_active=} is not '
                    f'equal to {active_found_real=} and/or '
                    f'{active_found_mock=}')

        if num_stopped is not None:
            if not (num_stopped
                    == stopped_found_real
                    == stopped_found_mock):
                self.abort_all_f1_threads()
                raise InvalidConfigurationDetected(
                    f'verify_counts found expected {num_stopped=} is not '
                    f'equal to {stopped_found_real=} and/or '
                    f'{stopped_found_mock=}')

    ####################################################################
    # verify_in_registry
    ####################################################################
    def verify_in_registry(self,
                           cmd_runner: str,
                           exp_in_registry_names: list[str]) -> None:
        """Verify that the given names are registered.

        Args:
            cmd_runner: name of thread doing the verify
            exp_in_registry_names: names of the threads to check for
                being in the registry

        """
        for exp_in_registry_name in exp_in_registry_names:
            if exp_in_registry_name not in st.SmartThread._registry:
                self.abort_all_f1_threads()
                raise InvalidConfigurationDetected(
                    f'verify_in_registry found {exp_in_registry_name} is not '
                    'registered in the real SmartThread._registry '
                    f'per {cmd_runner=}')
            if exp_in_registry_name not in self.expected_registered:
                self.abort_all_f1_threads()
                raise InvalidConfigurationDetected(
                    f'verify_in_registry found {exp_in_registry_name} is not '
                    'registered in the mock SmartThread._registry '
                    f'per {cmd_runner=}')

    ####################################################################
    # verify_in_registry_not
    ####################################################################
    def verify_in_registry_not(self,
                               cmd_runner: str,
                               exp_not_in_registry_names: list[str]
                               ) -> None:
        """Verify that the given names are not registered.

        Args:
            cmd_runner: name of thread doing the verify
            exp_not_in_registry_names: names of the threads to check for
                not being in the registry

        """
        for exp_not_in_registry_name in exp_not_in_registry_names:
            if exp_not_in_registry_name in st.SmartThread._registry:
                self.abort_all_f1_threads()
                raise InvalidConfigurationDetected(
                    f'verify_in_registry_not found {exp_not_in_registry_name} '
                    'is registered in the real SmartThread._registry per '
                    f'{cmd_runner=}')
            if exp_not_in_registry_name in self.expected_registered:
                self.abort_all_f1_threads()
                raise InvalidConfigurationDetected(
                    f'verify_in_registry_not found {exp_not_in_registry_name} '
                    'is registered in the mock expected_registered per '
                    f'{cmd_runner=}')

    ####################################################################
    # verify_is_active
    ####################################################################
    def verify_is_active(self,
                         cmd_runner: str,
                         exp_active_names: list[str]) -> None:
        """Verify that the given names are active.

        Args:
            cmd_runner: thread doing the verify
            exp_active_names: names of the threads to check for being
                active

        """
        self.verify_in_registry(cmd_runner=cmd_runner,
                                exp_in_registry_names=exp_active_names)
        self.verify_is_alive(names=exp_active_names)
        self.verify_status(
            cmd_runner=cmd_runner,
            check_status_names=exp_active_names,
            expected_status=st.ThreadStatus.Alive)
        if len(exp_active_names) > 1:
            self.verify_paired(
                cmd_runner=cmd_runner,
                exp_paired_names=exp_active_names)

    ####################################################################
    # verify_is_alive
    ####################################################################
    def verify_is_alive(self, names: list[str]) -> None:
        """Verify that the given names are alive.

        Args:
            names: names of the threads to check for being alive

        """
        for name in names:
            if not st.SmartThread._registry[name].thread.is_alive():
                self.abort_all_f1_threads()
                raise InvalidConfigurationDetected(
                    f'verify_is_alive found {name} has real is_alive = '
                    f'{st.SmartThread._registry[name].thread.is_alive()} '
                    'which is not equal to the expected is_alive of True ')
            if not self.expected_registered[name].is_alive:
                self.abort_all_f1_threads()
                raise InvalidConfigurationDetected(
                    f'verify_is_alive found {name} has mock is_alive = '
                    f'{self.expected_registered[name].is_alive} which is '
                    'not equal to the expected is_alive of True ')

    ####################################################################
    # verify_is_alive_not
    ####################################################################
    def verify_is_alive_not(self, names: list[str]) -> None:
        """Verify that the given names are not alive.

        Args:
            names: names of the threads to check for being not alive

        """
        for name in names:
            if st.SmartThread._registry[name].thread.is_alive():
                self.abort_all_f1_threads()
                raise InvalidConfigurationDetected(
                    f'verify_is_alive_not found {name} has real is_alive = '
                    f'{st.SmartThread._registry[name].thread.is_alive()} '
                    'which is not equal to the expected is_alive of False ')
            if self.expected_registered[name].is_alive:
                self.abort_all_f1_threads()
                raise InvalidConfigurationDetected(
                    f'verify_is_alive_not found {name} has mock is_alive = '
                    f'{self.expected_registered[name].is_alive} which is '
                    'not equal to the expected is_alive of False')

    ####################################################################
    # verify_is_registered
    ####################################################################
    def verify_is_registered(self,
                             cmd_runner: str,
                             exp_registered_names: list[str]) -> None:
        """Verify that the given names are registered only.

        Args:
            cmd_runner: thread doing the verify
            exp_registered_names: names of the threads to check for
                being registered

        """
        self.verify_in_registry(cmd_runner=cmd_runner,
                                exp_in_registry_names=exp_registered_names)
        self.verify_is_alive_not(names=exp_registered_names)
        self.verify_status(
            cmd_runner=cmd_runner,
            check_status_names=exp_registered_names,
            expected_status=st.ThreadStatus.Registered)
        if len(exp_registered_names) > 1:
            self.verify_paired(cmd_runner=cmd_runner,
                               exp_paired_names=exp_registered_names)

    ####################################################################
    # verify_paired
    ####################################################################
    def verify_paired(self,
                      cmd_runner: str,
                      exp_paired_names: list[str]) -> None:
        """Verify that the given names are paired.

        Args:
            cmd_runner: thread doing tyhe verify
            exp_paired_names: names of the threads to check for being
                paired

        """
        pair_keys = combinations(sorted(exp_paired_names), 2)
        for pair_key in pair_keys:
            if pair_key not in st.SmartThread._pair_array:
                self.abort_all_f1_threads()
                raise InvalidConfigurationDetected(
                    f'verify_paired found {pair_key=} is not '
                    f'in the real pair_array')
            if pair_key[0] not in st.SmartThread._pair_array[
                    pair_key].status_blocks:
                self.abort_all_f1_threads()
                raise InvalidConfigurationDetected(
                    f'verify_paired found {pair_key[0]=} does not '
                    f'have a status block in the real pair_array')
            if pair_key[1] not in st.SmartThread._pair_array[
                    pair_key].status_blocks:
                self.abort_all_f1_threads()
                raise InvalidConfigurationDetected(
                    f'verify_paired found {pair_key[1]=} does not '
                    f'have a status block in the real pair_array')

            if pair_key not in self.expected_pairs:
                self.abort_all_f1_threads()
                raise InvalidConfigurationDetected(
                    f'verify_paired found {pair_key=} is not '
                    f'in the mock pair_array')
            if pair_key[0] not in self.expected_pairs[pair_key]:
                self.abort_all_f1_threads()
                raise InvalidConfigurationDetected(
                    f'verify_paired found {pair_key[0]=} does not '
                    f'have a status block in the mock pair_array')
            if pair_key[1] not in self.expected_pairs[pair_key]:
                self.abort_all_f1_threads()
                raise InvalidConfigurationDetected(
                    f'verify_paired found {pair_key[1]=} does not '
                    f'have a status block in the mock pair_array')

    ####################################################################
    # verify_paired_half
    ####################################################################
    def verify_paired_half(self,
                           cmd_runner: str,
                           pair_names: list[str],
                           half_paired_names: list[str]) -> None:
        """Verify that the given names are half paired.

        Args:
            cmd_runner: thread doing the verify
            pair_names: names of the threads that form pair keys for
                half paired names
            half_paired_names: the names that should be in pair array
        """
        pair_keys = combinations(sorted(pair_names), 2)
        for pair_key in pair_keys:
            if pair_key not in st.SmartThread._pair_array:
                self.abort_all_f1_threads()
                raise InvalidConfigurationDetected(
                    f'verify_paired_half found {pair_key=} is not '
                    f'in the real pair_array')
            num_real_status_blocks = len(st.SmartThread._pair_array[
                    pair_key].status_blocks)
            if num_real_status_blocks != 1:
                self.abort_all_f1_threads()
                raise InvalidConfigurationDetected(
                    f'verify_paired_half found '
                    f'{num_real_status_blocks=} is not equal to 1 '
                    f'in the real pair_array')
            for name in half_paired_names:
                if (name in pair_key
                        and name not in st.SmartThread._pair_array[
                            pair_key].status_blocks):
                    self.abort_all_f1_threads()
                    raise InvalidConfigurationDetected(
                        f'verify_paired_half found '
                        f'{name=} does not have a status block '
                        f'in the real pair_array for {pair_key=}.')

            if pair_key not in self.expected_pairs:
                self.abort_all_f1_threads()
                raise InvalidConfigurationDetected(
                    f'verify_paired_half found {pair_key=} is not '
                    f'in the mock pair_array')
            num_mock_status_blocks = len(self.expected_pairs[pair_key])
            if num_mock_status_blocks != 1:
                self.abort_all_f1_threads()
                raise InvalidConfigurationDetected(
                    f'verify_paired_half found '
                    f'{num_mock_status_blocks=} is not 1 '
                    f'in the mock pair_array')
            for name in half_paired_names:
                if (name in pair_key
                        and name not in self.expected_pairs[pair_key]):
                    self.abort_all_f1_threads()
                    raise InvalidConfigurationDetected(
                        f'verify_paired_half found '
                        f'{name=} does not have a status block '
                        f'in the mock pair_array for {pair_key=}.')

    ####################################################################
    # verify_paired_not
    ####################################################################
    def verify_paired_not(self,
                          cmd_runner: str,
                          exp_not_paired_names: list[str]) -> None:
        """Verify that the given names are not paired.

        Args:
            cmd_runner: thread doing the verify
            exp_not_paired_names: names of the threads to check for
                being not paired

        """
        pair_keys = combinations(sorted(exp_not_paired_names), 2)
        for pair_key in pair_keys:
            if pair_key in st.SmartThread._pair_array:
                self.abort_all_f1_threads()
                raise InvalidConfigurationDetected(
                    f'verify_paired_not found {pair_key=} is in '
                    f'in the real pair_array')

            if pair_key in self.expected_pairs:
                self.abort_all_f1_threads()
                raise InvalidConfigurationDetected(
                    f'verify_paired_not found {pair_key=} is in '
                    f'in the mock pair_array')

    ####################################################################
    # verify_status
    ####################################################################
    def verify_status(self,
                      cmd_runner: str,
                      check_status_names: list[str],
                      expected_status: st.ThreadStatus) -> None:
        """Verify that the given names have the given status.

        Args:
            cmd_runner: thread doing the verify
            check_status_names: names of the threads to check for the
                given status
            expected_status: the status each thread is expected to have

        """
        for name in check_status_names:
            if not st.SmartThread._registry[name].status == expected_status:
                self.abort_all_f1_threads()
                raise InvalidConfigurationDetected(
                    f'verify_status found {name} has real status '
                    f'{st.SmartThread._registry[name].status} '
                    'not equal to the expected status of '
                    f'{expected_status} per {cmd_runner=}')
            if not self.expected_registered[name].status == expected_status:
                self.abort_all_f1_threads()
                raise InvalidConfigurationDetected(
                    f'verify_status found {name} has mock status '
                    f'{self.expected_registered[name].status} '
                    'not equal to the expected status of '
                    f'{expected_status} per {cmd_runner=}')

    ####################################################################
    # wait_for_recv_msg_timeouts
    ####################################################################
    def wait_for_recv_msg_timeouts(self,
                                   cmd_runner: str):
        """Verify that the receivers have timed out.

        Args:
            cmd_runner: thread doing the wait
        """
        while True:
            with self.ops_lock:
                if self.expected_num_recv_timouts == 0:
                    return
            time.sleep(0.1)

    ####################################################################
    # wait_for_msg_timeouts
    ####################################################################
    def wait_for_send_msg_timeouts(self,
                                  cmd_runner: str,
                                  sender_names: list[str],
                                  unreg_names: list[str],
                                  fullq_names: list[str]) -> None:
        """Verify that the senders have detected the timeout threads.

        Args:
            cmd_runner: thread doing the wait
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


########################################################################
# expand_cmds
########################################################################
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


########################################################################
# CommanderCurrentApp class
########################################################################
class CommanderCurrentApp:
    """Outer thread app for test."""
    def __init__(self,
                 config_ver: ConfigVerifier,
                 name: str,
                 max_msgs: int
                 ) -> None:
        """Initialize the object.

        Args:
            config_ver: configuration verifier and test support methods
            name: name of thread
            auto_start: True, start thread
            max_msgs: max number of messages for msg_q

        """
        self.config_ver = config_ver
        self.smart_thread = st.SmartThread(
            name=name,
            auto_start=False,
            max_msgs=max_msgs)

        self.config_ver.commander_thread = self.smart_thread

    def run(self) -> None:
        """Run the test."""
        self.config_ver.main_driver()


########################################################################
# OuterThreadApp class
########################################################################
class OuterThreadApp(threading.Thread):
    """Outer thread app for test."""
    def __init__(self,
                 config_ver: ConfigVerifier,
                 name: str,
                 # auto_start: bool,
                 max_msgs: int
                 ) -> None:
        """Initialize the object.

        Args:
            config_ver: configuration verifier and test support methods
            name: name of thread
            auto_start: True, start thread
            max_msgs: max number of messages for msg_q

        """
        super().__init__()
        self.config_ver = config_ver
        self.smart_thread = st.SmartThread(
            name=name,
            thread=self,
            auto_start=False,
            max_msgs=max_msgs)

        self.config_ver.commander_thread = self.smart_thread

    def run(self) -> None:
        """Run the test."""
        self.smart_thread._set_status(
            target_thread=self.smart_thread,
            new_status=st.ThreadStatus.Alive)
        self.config_ver.main_driver()


########################################################################
# OuterF1ThreadApp class
########################################################################
class OuterF1ThreadApp(threading.Thread):
    """Outer thread app for test."""
    def __init__(self,
                 config_ver: ConfigVerifier,
                 name: str,
                 auto_start: bool,
                 max_msgs: int
                 ) -> None:
        """Initialize the object.

        Args:
            config_ver: configuration verifier and test support methods
            name: name of thread
            auto_start: True, start thread
            max_msgs: max number of messages for msg_q

        """
        super().__init__()
        self.config_ver = config_ver
        self.smart_thread = st.SmartThread(
            name=name,
            thread=self,
            auto_start=False,
            max_msgs=max_msgs)
        if auto_start:
            self.smart_thread.start()

    def run(self) -> None:
        """Run the test."""
        log_msg_f1 = f'OuterF1ThreadApp.run() entry: {self.smart_thread.name=}'
        self.config_ver.log_ver.add_msg(log_msg=re.escape(log_msg_f1))
        logger.debug(log_msg_f1)

        self.config_ver.f1_driver(f1_name=self.smart_thread.name)

        ####################################################################
        # exit
        ####################################################################
        log_msg_f1 = f'OuterF1ThreadApp.run() exit: {self.smart_thread.name=}'
        self.config_ver.log_ver.add_msg(log_msg=re.escape(log_msg_f1))
        logger.debug(log_msg_f1)
        # self.config_ver.set_is_alive(target=self.smart_thread.name,
        #                              value=False,
        #                              exiting=True)

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


########################################################################
# outer_f1
########################################################################
def outer_f1(f1_name: str, f1_config_ver: ConfigVerifier):
    log_msg_f1 = f'outer_f1 entered for {f1_name}'
    f1_config_ver.log_ver.add_msg(log_msg=log_msg_f1)
    logger.debug(log_msg_f1)

    f1_config_ver.f1_driver(f1_name=f1_name)

    ####################################################################
    # exit
    ####################################################################
    log_msg_f1 = f'outer_f1 exiting for {f1_name}'
    f1_config_ver.log_ver.add_msg(log_msg=log_msg_f1)
    logger.debug(log_msg_f1)
    # f1_config_ver.set_is_alive(target=f1_name,
    #                            value=False,
    #                            exiting=True)


########################################################################
# TestSmartThreadScenarios class
########################################################################
class TestSmartThreadScenarios:
    """Test class for SmartThread scenarios."""

    ####################################################################
    # test_smart_thread_simple_scenarios
    ####################################################################
    def test_smart_thread_simple_scenarios(
            self,
            caplog: pytest.CaptureFixture[str],
            commander_config_arg: AppConfig
    ) -> None:
        """Test meta configuration scenarios.

        Args:
            caplog: pytest fixture to capture log output
            commander_config_arg: specifies the config for the commander

        """

        # args_for_scenario_builder: dict[str, Any] = {
        #     'timeout_type': timeout_type_arg,
        #     'num_receivers': num_receivers_arg,
        #     'num_active_no_delay_senders': num_active_no_delay_senders_arg,
        #     'num_active_delay_senders': num_active_delay_senders_arg,
        #     'num_send_exit_senders': num_send_exit_senders_arg,
        #     'num_nosend_exit_senders': num_nosend_exit_senders_arg,
        #     'num_unreg_senders': num_unreg_senders_arg,
        #     'num_reg_senders': num_reg_senders_arg
        # }

        args_for_scenario_builder: dict[str, Any] = {}

        self.scenario_driver(
            scenario_builder=ConfigVerifier.build_simple_scenario,
            scenario_builder_args=args_for_scenario_builder,
            caplog_to_use=caplog,
            commander_config=commander_config_arg)

    ####################################################################
    # test_smart_thread_meta_scenarios
    ####################################################################
    def test_config_build_scenarios(
            self,
            num_registered_1_arg: int,
            num_active_1_arg: int,
            num_stopped_1_arg: int,
            num_registered_2_arg: int,
            num_active_2_arg: int,
            num_stopped_2_arg: int,
            caplog: pytest.CaptureFixture[str]
    ) -> None:
        """Test meta configuration scenarios.

        Args:
            num_registered_1_arg: number of threads to initially build
                as registered
            num_active_1_arg: number of threads to initially build as
                active
            num_stopped_1_arg: number of threads to initially build as
                stopped
            num_registered_2_arg: number of threads to reconfigured as
                registered
            num_active_2_arg: number of threads to reconfigured as
                active
            num_stopped_2_arg: number of threads to reconfigured as
                stopped
            caplog: pytest fixture to capture log output

        """
        args_for_scenario_builder: dict[str, Any] = {
            'num_registered_1': num_registered_1_arg,
            'num_active_1': num_active_1_arg,
            'num_stopped_1': num_stopped_1_arg,
            'num_registered_2': num_registered_2_arg,
            'num_active_2': num_active_2_arg,
            'num_stopped_2': num_stopped_2_arg,
        }

        self.scenario_driver(
            scenario_builder=ConfigVerifier.build_config_build_suite,
            scenario_builder_args=args_for_scenario_builder,
            caplog_to_use=caplog)

    ####################################################################
    # test_smart_thread_join_errors
    ####################################################################
    def test_join_timeout_scenarios(
            self,
            timeout_type_arg: TimeoutType,
            num_active_no_target_arg: int,
            num_no_delay_exit_arg: int,
            num_delay_exit_arg: int,
            num_no_delay_unreg_arg: int,
            num_delay_unreg_arg: int,
            num_no_delay_reg_arg: int,
            num_delay_reg_arg: int,
            caplog: pytest.CaptureFixture[str]
            ) -> None:
        """Test error cases in the _regref remote array method.

        Args:
            caplog: pytest fixture to capture log output

        """
        assert num_active_no_target_arg > 0
        if timeout_type_arg == TimeoutType.TimeoutNone:
            if (num_no_delay_exit_arg
                    + num_delay_exit_arg
                    + num_no_delay_unreg_arg
                    + num_delay_unreg_arg
                    + num_no_delay_reg_arg
                    + num_delay_reg_arg) == 0:
                return
        else:
            if (num_delay_exit_arg
                    + num_delay_unreg_arg
                    + num_delay_reg_arg) == 0:
                return

        args_for_scenario_builder: dict[str, Any] = {
            'timeout_type': timeout_type_arg,
            'num_active_no_target': num_active_no_target_arg,
            'num_no_delay_exit': num_no_delay_exit_arg,
            'num_delay_exit': num_delay_exit_arg,
            'num_no_delay_unreg': num_no_delay_unreg_arg,
            'num_delay_unreg': num_delay_unreg_arg,
            'num_no_delay_reg': num_no_delay_reg_arg,
            'num_delay_reg': num_delay_reg_arg
        }

        self.scenario_driver(
            scenario_builder=ConfigVerifier.build_join_timeout_suite,
            scenario_builder_args=args_for_scenario_builder,
            caplog_to_use=caplog)

    ####################################################################
    # test_smart_thread_msg_timeout_scenarios
    ####################################################################
    def test_recv_msg_timeout_scenarios(
            self,
            timeout_type_arg: TimeoutType,
            num_receivers_arg: int,
            num_active_no_delay_senders_arg: int,
            num_active_delay_senders_arg: int,
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
            num_active_no_delay_senders_arg: number of threads that are
                active and will do the send_msg immediately
            num_active_delay_senders_arg: number of threads that are
                active and will do the send_msg after a delay
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
        if timeout_type_arg == TimeoutType.TimeoutNone:
            if (num_active_no_delay_senders_arg
                    + num_active_delay_senders_arg
                    + num_send_exit_senders_arg
                    + num_nosend_exit_senders_arg
                    + num_unreg_senders_arg
                    + num_reg_senders_arg) == 0:
                return
        else:
            if (num_active_delay_senders_arg
                    + num_nosend_exit_senders_arg
                    + num_unreg_senders_arg
                    + num_reg_senders_arg) == 0:
                return

        args_for_scenario_builder: dict[str, Any] = {
            'timeout_type': timeout_type_arg,
            'num_receivers': num_receivers_arg,
            'num_active_no_delay_senders': num_active_no_delay_senders_arg,
            'num_active_delay_senders': num_active_delay_senders_arg,
            'num_send_exit_senders': num_send_exit_senders_arg,
            'num_nosend_exit_senders': num_nosend_exit_senders_arg,
            'num_unreg_senders': num_unreg_senders_arg,
            'num_reg_senders': num_reg_senders_arg
        }

        self.scenario_driver(
            scenario_builder=ConfigVerifier.build_recv_msg_timeout_suite,
            scenario_builder_args=args_for_scenario_builder,
            caplog_to_use=caplog)

    ####################################################################
    # test_send_msg_timeout_scenarios
    ####################################################################
    def test_send_msg_timeout_scenarios(
            self,
            timeout_type_arg: TimeoutType,
            num_senders_arg: int,
            num_active_targets_arg: int,
            num_registered_targets_arg: int,
            num_unreg_timeouts_arg: int,
            num_exit_timeouts_arg: int,
            num_full_q_timeouts_arg: int,
            caplog: pytest.CaptureFixture[str]
    ) -> None:
        """Test meta configuration scenarios.

        Args:
            num_senders_arg: number of threads to send msgs
            num_active_targets_arg: number of active threads to recv
            num_registered_targets_arg: number registered thread to
                recv
            num_unreg_timeouts_arg: number of threads to be targets that
                cause a timeout by being unregistering
            num_exit_timeouts_arg: number of threads to be targets that
                cause a timeout by exiting
            num_full_q_timeouts_arg: number of threads to be targets
                that cause a timeout by having a full msgq
            caplog: pytest fixture to capture log output

        """
        total_arg_counts = (
                num_active_targets_arg
                + num_registered_targets_arg
                + num_unreg_timeouts_arg
                + num_exit_timeouts_arg
                + num_full_q_timeouts_arg)
        if timeout_type_arg == TimeoutType.TimeoutNone:
            if total_arg_counts == 0:
                return
        else:
            if (num_unreg_timeouts_arg
                    + num_exit_timeouts_arg
                    + num_full_q_timeouts_arg) == 0:
                return

        command_config_num = total_arg_counts % 3
        if command_config_num == 0:
            commander_config = AppConfig.ScriptStyle
        elif command_config_num == 1:
            commander_config = AppConfig.CurrentThreadApp
        else:
            commander_config = AppConfig.RemoteThreadApp

        args_for_scenario_builder: dict[str, Any] = {
            'timeout_type': timeout_type_arg,
            'num_senders': num_senders_arg,
            'num_active_targets': num_active_targets_arg,
            'num_registered_targets': num_registered_targets_arg,
            'num_unreg_timeouts': num_unreg_timeouts_arg,
            'num_exit_timeouts': num_exit_timeouts_arg,
            'num_full_q_timeouts': num_full_q_timeouts_arg
        }

        self.scenario_driver(
            scenario_builder=ConfigVerifier.build_send_msg_timeout_suite,
            scenario_builder_args=args_for_scenario_builder,
            caplog_to_use=caplog,
            commander_config=commander_config)

    ####################################################################
    # test_smart_thread_msg_timeout_scenarios
    ####################################################################
    def scenario_driver(
            self,
            scenario_builder: Callable[..., None],
            scenario_builder_args: dict[str, Any],
            caplog_to_use: pytest.CaptureFixture[str],
            commander_config: AppConfig = AppConfig.ScriptStyle
    ) -> None:
        """Build and run a scenario.

        Args:
            scenario_builder: the ConfigVerifier builder method to call
            scenario_builder_args: the args to pass to the builder
            caplog_to_use: the capsys to capture log messages
            commander_config: specifies how the commander will run

        """

        ################################################################
        # f1
        ################################################################
        def f1(f1_name: str, f1_config_ver: ConfigVerifier):
            log_msg_f1 = f'f1 entered for {f1_name}'
            log_ver.add_msg(log_level=logging.DEBUG,
                            log_msg=log_msg_f1)
            logger.debug(log_msg_f1)

            f1_config_ver.f1_driver(f1_name=f1_name)

            ############################################################
            # exit
            ############################################################
            log_msg_f1 = f'f1 exiting for {f1_name}'
            log_ver.add_msg(log_level=logging.DEBUG,
                            log_msg=log_msg_f1)
            logger.debug(log_msg_f1)
            # f1_config_ver.set_is_alive(target=f1_name,
            #                            value=False,
            #                            exiting=True)

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

        random.seed(42)
        msgs = Msgs()

        config_ver = ConfigVerifier(commander_name=commander_name,
                                    log_ver=log_ver,
                                    caplog_to_use=caplog_to_use,
                                    msgs=msgs,
                                    max_msgs=10)

        scenario_builder(config_ver,
                         **scenario_builder_args)

        config_ver.add_cmd(ValidateConfig(cmd_runners=commander_name))

        names = list(config_ver.active_names - {commander_name})
        config_ver.build_exit_suite(names=names)

        config_ver.build_join_suite(
            cmd_runners=[config_ver.commander_name],
            join_target_names=names)

        ################################################################
        # start commander
        ################################################################
        if commander_config == AppConfig.ScriptStyle:
            commander_thread = st.SmartThread(
                name=commander_name,
                max_msgs=10)
            config_ver.commander_thread = commander_thread
            config_ver.main_driver()
        elif commander_config == AppConfig.CurrentThreadApp:
            commander_current_app = CommanderCurrentApp(
                config_ver=config_ver,
                name=commander_name,
                max_msgs=10)
            commander_current_app.run()
        elif commander_config == AppConfig.RemoteThreadApp:
            outer_thread_app = OuterThreadApp(
                config_ver=config_ver,
                name=commander_name,
                max_msgs=10)
            outer_thread_app.start()
            outer_thread_app.join()

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(
            caplog=caplog_to_use)
        log_ver.print_match_results(match_results)
        log_ver.verify_log_results(match_results)

        logger.debug('mainline exiting')

    # ##################################################################
    # # test_smart_thread_scenarios
    # ##################################################################
    # def test_smart_thread_random_scenarios(
    #         self,
    #         random_seed_arg: int,
    #         caplog: pytest.CaptureFixture[str]
    # ) -> None:
    #     """Test meta configuration scenarios.
    #
    #     Args:
    #         caplog: pytest fixture to capture log output
    #
    #     """
    #
    #     random.seed(random_seed_arg)
    #     num_threads = random.randint(2, 8)
    #
    #     f1_names = list(config_ver.f1_thread_names.keys())
    #
    #     f1_names_to_use = random.sample(f1_names, num_threads)
    #
    #     names = ['alpha'] + f1_names_to_use


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
            _ = st.SmartThread(name=1)  # type: ignore

        test_thread = threading.Thread(target=f1)
        with pytest.raises(
                st.SmartThreadMutuallyExclusiveTargetThreadSpecified):

            _ = st.SmartThread(name='alpha', target=f1, thread=test_thread)

        with pytest.raises(st.SmartThreadArgsSpecificationWithoutTarget):
            _ = st.SmartThread(name='alpha', args=(1,))

        with pytest.raises(st.SmartThreadArgsSpecificationWithoutTarget):
            _ = st.SmartThread(name='alpha', kwargs={'arg1': 1})

        with pytest.raises(st.SmartThreadArgsSpecificationWithoutTarget):
            _ = st.SmartThread(name='alpha', args=(1,), kwargs={'arg1': 1})

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


#
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
