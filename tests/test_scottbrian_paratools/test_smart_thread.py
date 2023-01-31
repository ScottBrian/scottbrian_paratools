"""test_smart_thread.py module."""

########################################################################
# Standard Library
########################################################################
from abc import ABC, abstractmethod
from collections import deque, defaultdict
from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto
from itertools import combinations, chain
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
StrOrSet: TypeAlias = Union[str, set[str]]


########################################################################
# CommanderConfig
########################################################################
class AppConfig(Enum):
    ScriptStyle = auto()
    CurrentThreadApp = auto()
    RemoteThreadApp = auto()
    RemoteSmartThreadApp = auto()
    RemoteSmartThreadApp2 = auto()
    

########################################################################
# ResumeStyles
########################################################################
class Actors(Enum):
    ActiveBeforeActor = auto()
    ActiveAfterActor = auto()
    ActionExitActor = auto()
    ExitActionActor = auto()
    UnregActor = auto()
    RegActor = auto()


########################################################################
# DefDelScenario
########################################################################
class DefDelScenario(Enum):
    NormalRecv = auto()
    NormalWait = auto()
    ResurrectionRecv = auto()
    ResurrectionWait = auto()
    Recv0Recv1 = auto()
    Recv1Recv0 = auto()
    Wait0Wait1 = auto()
    Wait1Wait0 = auto()
    RecvWait = auto()
    WaitRecv = auto()
    RecvDel = auto()
    RecvAdd = auto()
    WaitDel = auto()
    WaitAdd = auto()


########################################################################
# ConflictDeadlockScenario
########################################################################
class ConflictDeadlockScenario(Enum):
    NormalSync = auto()
    NormalResumeWait = auto()
    ResumeSyncSyncWait = auto()
    SyncConflict = auto()
    WaitDeadlock = auto()


########################################################################
# Test settings for conflict_deadlock_scenarios
########################################################################
conflict_deadlock_arg_list = [
    ConflictDeadlockScenario.NormalSync,
    ConflictDeadlockScenario.NormalResumeWait,
    ConflictDeadlockScenario.ResumeSyncSyncWait,
    ConflictDeadlockScenario.SyncConflict,
    ConflictDeadlockScenario.WaitDeadlock,
]
# conflict_deadlock_arg_list = [ConflictDeadlockScenario.WaitDeadlock]

conflict_deadlock_arg_list2 = [
    ConflictDeadlockScenario.NormalSync,
    ConflictDeadlockScenario.NormalResumeWait,
    ConflictDeadlockScenario.ResumeSyncSyncWait,
    ConflictDeadlockScenario.SyncConflict,
    ConflictDeadlockScenario.WaitDeadlock,
]
# conflict_deadlock_arg_list2 = [ConflictDeadlockScenario.NormalResumeWait]

conflict_deadlock_arg_list3 = [
    ConflictDeadlockScenario.NormalSync,
    ConflictDeadlockScenario.NormalResumeWait,
    ConflictDeadlockScenario.ResumeSyncSyncWait,
    ConflictDeadlockScenario.SyncConflict,
    ConflictDeadlockScenario.WaitDeadlock,
]
# conflict_deadlock_arg_list3 = [ConflictDeadlockScenario.SyncConflict]

num_cd_actors_arg_list = [3, 4, 5, 6, 7, 8, 9]

# num_cd_actors_arg_list = [6]


########################################################################
# Test settings
########################################################################
commander_config_arg_list = [AppConfig.ScriptStyle,
                             AppConfig.CurrentThreadApp,
                             AppConfig.RemoteThreadApp,
                             AppConfig.RemoteSmartThreadApp,
                             AppConfig.RemoteSmartThreadApp2]

# commander_config_arg_list = [AppConfig.RemoteThreadApp]


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
# Test settings for test_def_del_scenarios
########################################################################
def_del_scenario_arg_list = [
    DefDelScenario.NormalRecv,
    DefDelScenario.NormalWait,
    DefDelScenario.ResurrectionRecv,
    DefDelScenario.ResurrectionWait,
    DefDelScenario.Recv0Recv1,
    DefDelScenario.Recv1Recv0,
    DefDelScenario.Wait0Wait1,
    DefDelScenario.Wait1Wait0,
    DefDelScenario.RecvWait,
    DefDelScenario.WaitRecv,
    DefDelScenario.RecvDel,
    DefDelScenario.RecvAdd,
    DefDelScenario.WaitDel,
    DefDelScenario.WaitAdd
]
# def_del_scenario_arg_list = [DefDelScenario.Recv0Recv1]

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
# num_active_no_delay_senders_arg_list = [1]  # .001

num_active_delay_senders_arg_list = [0, 1, 2]
# num_active_delay_senders_arg_list = [1]  # .65  0.0005

num_send_exit_senders_arg_list = [0, 1, 2]
# num_send_exit_senders_arg_list = [2]  # .65  0.0007

num_nosend_exit_senders_arg_list = [0, 1, 2]
# num_nosend_exit_senders_arg_list = [2]  # 1.05  0.50

num_unreg_senders_arg_list = [0, 1, 2]
# num_unreg_senders_arg_list = [2]  # .75 0.15

num_reg_senders_arg_list = [0, 1, 2]
# num_reg_senders_arg_list = [2]  # .75 .06

########################################################################
# Test settings for test_send_msg_timeout_scenarios
########################################################################
num_senders_arg_list = [1, 2, 3]
# num_senders_arg_list = [2]

num_active_targets_arg_list = [0, 1, 2]
# num_active_targets_arg_list = [3]  # 0.12

num_registered_targets_arg_list = [0, 1, 2]
# num_registered_targets_arg_list = [3]  # 0.11

num_unreg_timeouts_arg_list = [0, 1, 2]
# num_unreg_timeouts_arg_list = [3]  # 0.15

num_exit_timeouts_arg_list = [0, 1, 2]
# num_exit_timeouts_arg_list = [1]  # 0.11

num_full_q_timeouts_arg_list = [0, 1, 2]
# num_full_q_timeouts_arg_list = [3]  # 0.11

########################################################################
# Test settings for test_join_timeout_scenarios
########################################################################
num_active_no_target_arg_list = [1, 2, 3]
# num_active_no_target_arg_list = [3]

num_no_delay_exit_arg_list = [0, 1, 2]
# num_no_delay_exit_arg_list = [2]

num_delay_exit_arg_list = [0, 1, 2]
# num_delay_exit_arg_list = [2]

num_no_delay_unreg_arg_list = [0, 1, 2]
# num_no_delay_unreg_arg_list = [2]

num_delay_unreg_arg_list = [0, 1, 2]
# num_delay_unreg_arg_list = [2]

num_no_delay_reg_arg_list = [0, 1, 2]
# num_no_delay_reg_arg_list = [2]

num_delay_reg_arg_list = [0, 1, 2]
# num_delay_reg_arg_list = [2]

########################################################################
# Test settings for test_resume_timeout_scenarios
########################################################################
num_resumers_arg_list = [1, 2, 3]
num_active_arg_list = [0, 1, 2]
num_registered_before_arg_list = [0, 1, 2]
num_registered_after_arg_list = [0, 1, 2]
num_unreg_no_delay_arg_list = [0, 1, 2]
num_unreg_delay_arg_list = [0, 1, 2]
num_stopped_no_delay_arg_list = [0, 1, 2]
num_stopped_delay_arg_list = [0, 1, 2]

########################################################################
# Test settings for test_wait_timeout_scenarios
########################################################################
num_waiters_arg_list = [1, 2, 3]
# num_waiters_arg_list = [3]
num_actors_arg_list = [1, 2, 3]

actor_1_arg_list = [Actors.ActiveBeforeActor,
                    Actors.ActiveAfterActor,
                    Actors.ActionExitActor,
                    Actors.ExitActionActor,
                    Actors.UnregActor,
                    Actors.RegActor]
# actor_1_arg_list = [Actors.ActionExitActor]
num_actor_1_arg_list = [1, 2, 3]

actor_2_arg_list = [Actors.ActiveBeforeActor,
                    Actors.ActiveAfterActor,
                    Actors.ActionExitActor,
                    Actors.ExitActionActor,
                    Actors.UnregActor,
                    Actors.RegActor]
# actor_2_arg_list = [Actors.ActionExitActor]
num_actor_2_arg_list = [1, 2, 3]

actor_3_arg_list = [Actors.ActiveBeforeActor,
                    Actors.ActiveAfterActor,
                    Actors.ActionExitActor,
                    Actors.ExitActionActor,
                    Actors.UnregActor,
                    Actors.RegActor]
num_actor_3_arg_list = [1, 2, 3]


########################################################################
# Test settings for test_sync_scenarios
########################################################################
num_syncers_arg_list = [1, 2, 3, 16]
num_stopped_syncers_arg_list = [0, 1, 2, 3]
num_timeout_syncers_arg_list = [0, 1, 2, 3]
error_stopped_target_arg_list = [True, False]


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


class CmdFailed(ErrorTstSmartThread):
    """The cmd failed."""
    pass


class FailedToFindLogMsg(ErrorTstSmartThread):
    """An expected log message was not found."""
    pass


class FailedLockVerify(ErrorTstSmartThread):
    """An expected lock position was not found."""
    pass


class FailedDefDelVerify(ErrorTstSmartThread):
    """An expected condition was incorrect."""
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
            if item or key == 'error_stopped_target':  # if not None
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
    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
           cmd_runner: name of thread running the command
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
                          'confirmers']

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
           cmd_runner: name of thread running the command
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
            timeout_value = 60
            if time.time() - start_time > timeout_value:
                raise CmdTimedOut('ConfirmResponse serial_num '
                                  f'{self.serial_num} took longer than '
                                  f'{timeout_value} seconds waiting '
                                  f'for {work_confirmers} to complete '
                                  f'cmd {self.confirm_cmd} with '
                                  f'serial_num {self.confirm_serial_num}.')


########################################################################
# ConfirmResponseNot
########################################################################
class ConfirmResponseNot(ConfirmResponse):
    def __init__(self,
                 cmd_runners: StrOrList,
                 confirm_cmd: str,
                 confirm_serial_num: int,
                 confirmers: StrOrList
                 ) -> None:
        super().__init__(cmd_runners=cmd_runners,
                         confirm_cmd=confirm_cmd,
                         confirm_serial_num=confirm_serial_num,
                         confirmers=confirmers)
        self.specified_args = locals()  # used for __repr__

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
           cmd_runner: name of thread running the command
        """
        for name in self.confirmers:
            # If the serial number is in the completed_cmds for
            # this name then the command was completed. Remove the
            # target name and break to start looking again with one
            # less target until no targets remain.
            if (self.confirm_serial_num in
                    self.config_ver.completed_cmds[name]):
                raise CmdFailed('ConfirmResponseNot found that '
                                f'{name} completed {self.confirm_cmd=} '
                                f'with {self.serial_num=}.')


########################################################################
# CreateCommanderAutoStart
########################################################################
class CreateCommanderAutoStart(ConfigCmd):
    def __init__(self,
                 cmd_runners: StrOrList,
                 commander_name: str,
                 thread_alive: bool = True
                 ) -> None:
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

        self.commander_name = commander_name
        self.thread_alive = thread_alive
        self.arg_list += ['commander_name',
                          'thread_alive']

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
           cmd_runner: name of thread running the command
        """
        self.config_ver.create_commander_thread(
            cmd_runner=cmd_runner,
            name=self.commander_name,
            thread_alive=self.thread_alive,
            auto_start=True)


########################################################################
# CreateCommanderNoStart
########################################################################
class CreateCommanderNoStart(CreateCommanderAutoStart):
    def __init__(self,
                 cmd_runners: StrOrList,
                 commander_name: str,
                 thread_alive: bool = True
                 ) -> None:
        super().__init__(cmd_runners=cmd_runners,
                         commander_name=commander_name,
                         thread_alive=thread_alive)
        self.specified_args = locals()  # used for __repr__

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
           cmd_runner: name of thread running the command
        """
        self.config_ver.create_commander_thread(
            cmd_runner=cmd_runner,
            name=self.commander_name,
            thread_alive=self.thread_alive,
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

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
           cmd_runner: name of thread running the command
        """
        for f1_item in self.f1_create_items:
            self.config_ver.create_f1_thread(
                cmd_runner=cmd_runner,
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

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        for f1_item in self.f1_create_items:
            self.config_ver.create_f1_thread(
                cmd_runner=cmd_runner,
                name=f1_item.name,
                target=f1_item.target_rtn,
                app_config=f1_item.app_config,
                auto_start=False)


########################################################################
# ExitThread
########################################################################
class ExitThread(ConfigCmd):
    def __init__(self,
                 cmd_runners: StrOrList,
                 stopped_by: str) -> None:
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

        self.stopped_by = stopped_by

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.exit_thread(
            cmd_runner=cmd_runner,
            stopped_by=self.stopped_by)


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

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.handle_join(cmd_runner=cmd_runner,
                                    join_names=self.join_names,
                                    timeout_type=TimeoutType.TimeoutNone,
                                    timeout=0,
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
        self.arg_list += ['timeout']

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.handle_join(cmd_runner=cmd_runner,
                                    join_names=self.join_names,
                                    timeout_type=TimeoutType.TimeoutFalse,
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

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        if self.timeout_names:
            self.config_ver.handle_join(cmd_runner=cmd_runner,
                                        join_names=self.join_names,
                                        timeout_type=TimeoutType.TimeoutTrue,
                                        timeout=self.timeout,
                                        timeout_names=set(self.timeout_names),
                                        log_msg=self.log_msg)
        else:
            self.config_ver.handle_join(cmd_runner=cmd_runner,
                                        join_names=self.join_names,
                                        timeout_type=TimeoutType.TimeoutFalse,
                                        timeout=self.timeout,
                                        log_msg=self.log_msg)


########################################################################
# LockObtain
########################################################################
class LockObtain(ConfigCmd):
    def __init__(self,
                 cmd_runners: StrOrList) -> None:
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.lock_obtain(cmd_runner=cmd_runner)


########################################################################
# LockRelease
########################################################################
class LockRelease(ConfigCmd):
    def __init__(self,
                 cmd_runners: StrOrList) -> None:
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.lock_release(cmd_runner=cmd_runner)


########################################################################
# LockSwap
########################################################################
class LockSwap(ConfigCmd):
    def __init__(self,
                 cmd_runners: StrOrList,
                 new_positions: list[str]) -> None:
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

        self.new_positions = new_positions
        self.arg_list += ['new_positions']

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.lock_swap(cmd_runner=cmd_runner,
                                  new_positions=self.new_positions)


########################################################################
# LockSwap
########################################################################
class LockVerify(ConfigCmd):
    def __init__(self,
                 cmd_runners: StrOrList,
                 exp_positions: list[str]) -> None:
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

        self.exp_positions = exp_positions
        self.arg_list += ['exp_positions']

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.lock_verify(cmd_runner=cmd_runner,
                                    exp_positions=self.exp_positions,
                                    line_num=self.line_num)


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

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
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

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.handle_recv_msg(cmd_runner=cmd_runner,
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

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.handle_recv_msg_tof(
            cmd_runner=cmd_runner,
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

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.handle_recv_msg_tot(
            cmd_runner=cmd_runner,
            senders=self.senders,
            exp_msgs=self.exp_msgs,
            timeout=self.timeout,
            timeout_names=self.timeout_names,
            del_deferred=self.del_deferred,
            log_msg=self.log_msg)


########################################################################
# Resume
########################################################################
class Resume(ConfigCmd):
    def __init__(self,
                 cmd_runners: StrOrList,
                 targets: StrOrList,
                 stopped_names: StrOrList,
                 error_stopped_target: bool = True,
                 code: Optional[Any] = None,
                 log_msg: Optional[str] = None) -> None:
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

        if isinstance(targets, str):
            targets = [targets]
        self.targets = targets

        if isinstance(stopped_names, str):
            stopped_names = [stopped_names]
        self.stopped_names = stopped_names

        self.error_stopped_target = error_stopped_target

        self.code = code

        self.log_msg = log_msg

        self.arg_list += ['targets',
                          'error_stopped_target']

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.handle_resume(
            cmd_runner=cmd_runner,
            targets=set(self.targets),
            stopped_remotes=self.stopped_names,
            timeout=0,
            timeout_names=set(),
            timeout_type=TimeoutType.TimeoutNone,
            error_stopped_target=self.error_stopped_target,
            code=self.code,
            log_msg=self.log_msg)


########################################################################
# ResumeTimeoutFalse
########################################################################
class ResumeTimeoutFalse(Resume):
    def __init__(self,
                 cmd_runners: StrOrList,
                 targets: StrOrList,
                 stopped_names: StrOrList,
                 timeout: IntOrFloat,
                 error_stopped_target: bool = True,
                 code: Optional[Any] = None,
                 log_msg: Optional[str] = None) -> None:
        super().__init__(cmd_runners=cmd_runners,
                         targets=targets,
                         stopped_names=stopped_names,
                         error_stopped_target=error_stopped_target,
                         code=code,
                         log_msg=log_msg)
        self.specified_args = locals()  # used for __repr__

        self.timeout = timeout

        self.arg_list += ['timeout']

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.handle_resume(
            cmd_runner=cmd_runner,
            targets=set(self.targets),
            stopped_remotes=self.stopped_names,
            timeout=self.timeout,
            timeout_names=set(),
            timeout_type=TimeoutType.TimeoutFalse,
            error_stopped_target=self.error_stopped_target,
            code=self.code,
            log_msg=self.log_msg)


########################################################################
# ResumeTimeoutFalse
########################################################################
class ResumeTimeoutTrue(ResumeTimeoutFalse):
    def __init__(self,
                 cmd_runners: StrOrList,
                 targets: StrOrList,
                 stopped_names: StrOrList,
                 timeout: IntOrFloat,
                 timeout_names: StrOrList,
                 error_stopped_target: bool = True,
                 code: Optional[Any] = None,
                 log_msg: Optional[str] = None) -> None:
        super().__init__(cmd_runners=cmd_runners,
                         targets=targets,
                         stopped_names=stopped_names,
                         timeout=timeout,
                         error_stopped_target=error_stopped_target,
                         code=code,
                         log_msg=log_msg)
        self.specified_args = locals()  # used for __repr__

        if isinstance(timeout_names, str):
            timeout_names = [timeout_names]
        self.timeout_names = timeout_names

        self.arg_list += ['timeout_names']

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.handle_resume(
            cmd_runner=cmd_runner,
            targets=set(self.targets),
            stopped_remotes=self.stopped_names,
            timeout=self.timeout,
            timeout_names=set(self.timeout_names),
            timeout_type=TimeoutType.TimeoutTrue,
            error_stopped_target=self.error_stopped_target,
            code=self.code,
            log_msg=self.log_msg)


########################################################################
# SendMsg
########################################################################
class SendMsg(ConfigCmd):
    def __init__(self,
                 cmd_runners: StrOrList,
                 receivers: StrOrList,
                 msgs_to_send: dict[str, Any],
                 error_stopped_target: bool = True,
                 stopped_remotes: Optional[StrOrSet] = None,
                 log_msg: Optional[str] = None) -> None:
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

        if isinstance(receivers, str):
            receivers = [receivers]
        self.receivers = receivers
        self.msgs_to_send = msgs_to_send
        self.error_stopped_target = error_stopped_target

        if stopped_remotes and isinstance(stopped_remotes, str):
            stopped_remotes = {stopped_remotes}
        self.stopped_remotes = stopped_remotes

        self.log_msg = log_msg

        self.arg_list += ['receivers']

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.handle_send_msg(
            cmd_runner=cmd_runner,
            receivers=self.receivers,
            msg_to_send=self.msgs_to_send[cmd_runner],
            timeout_type=TimeoutType.TimeoutNone,
            timeout=0,
            error_stopped_target=self.error_stopped_target,
            unreg_timeout_names=None,
            fullq_timeout_names=None,
            stopped_remotes=self.stopped_remotes,
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
                 error_stopped_target: bool = True,
                 stopped_remotes: Optional[StrOrSet] = None,
                 # unreg_timeout_names: StrOrList,
                 # fullq_timeout_names: StrOrList,
                 log_msg: Optional[str] = None) -> None:
        super().__init__(
            cmd_runners=cmd_runners,
            receivers=receivers,
            msgs_to_send=msgs_to_send,
            error_stopped_target=error_stopped_target,
            stopped_remotes=stopped_remotes,
            log_msg=log_msg)
        self.specified_args = locals()  # used for __repr__

        self.timeout = timeout

        self.arg_list += ['timeout']

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.handle_send_msg(
            cmd_runner=cmd_runner,
            receivers=self.receivers,
            msg_to_send=self.msgs_to_send[cmd_runner],
            timeout_type=TimeoutType.TimeoutFalse,
            timeout=self.timeout,
            error_stopped_target=self.error_stopped_target,
            unreg_timeout_names=None,
            fullq_timeout_names=None,
            stopped_remotes=self.stopped_remotes,
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
                 error_stopped_target: bool = True,
                 stopped_remotes: Optional[StrOrSet] = None,
                 log_msg: Optional[str] = None) -> None:
        super().__init__(
            cmd_runners=cmd_runners,
            receivers=receivers,
            msgs_to_send=msgs_to_send,
            timeout=timeout,
            error_stopped_target=error_stopped_target,
            stopped_remotes=stopped_remotes,
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

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.handle_send_msg(
            cmd_runner=cmd_runner,
            receivers=self.receivers,
            msg_to_send=self.msgs_to_send[cmd_runner],
            timeout_type=TimeoutType.TimeoutTrue,
            timeout=self.timeout,
            error_stopped_target=self.error_stopped_target,
            unreg_timeout_names=set(self.unreg_timeout_names),
            fullq_timeout_names=set(self.fullq_timeout_names),
            stopped_remotes=self.stopped_remotes,
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

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.start_thread(
            cmd_runner=cmd_runner,
            start_names=self.start_names)


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

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.stop_thread(cmd_runner=cmd_runner,
                                    stop_names=self.stop_names)


########################################################################
# Sync
########################################################################
class Sync(ConfigCmd):
    def __init__(self,
                 cmd_runners: StrOrList,
                 targets: StrOrSet,
                 timeout: IntOrFloat = 0,
                 timeout_remotes: Optional[set[str]] = None,
                 stopped_remotes: Optional[set[str]] = None,
                 conflict_remotes: Optional[set[str]] = None,
                 error_stopped_target: bool = True,
                 log_msg: Optional[str] = None) -> None:
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

        if isinstance(targets, str):
            targets = {targets}
        self.targets = targets

        self.timeout = timeout

        if timeout_remotes:
            self.timeout_remotes = timeout_remotes
        else:
            self.timeout_remotes = set()

        if stopped_remotes:
            self.stopped_remotes = stopped_remotes
        else:
            self.stopped_remotes = set()

        if conflict_remotes:
            self.conflict_remotes = conflict_remotes
        else:
            self.conflict_remotes = set()

        self.error_stopped_target = error_stopped_target

        self.log_msg = log_msg

        self.arg_list += ['targets',
                          'timeout',
                          'stopped_remotes',
                          'timeout_remotes',
                          'error_stopped_target']

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        targets = self.targets - {cmd_runner}
        self.config_ver.handle_sync(
            cmd_runner=cmd_runner,
            targets=targets,
            timeout=self.timeout,
            timeout_remotes=self.timeout_remotes,
            stopped_remotes=self.stopped_remotes,
            conflict_remotes=self.conflict_remotes,
            timeout_type=TimeoutType.TimeoutNone,
            error_stopped_target=self.error_stopped_target,
            log_msg=self.log_msg)


########################################################################
# SyncTimeoutFalse
########################################################################
class SyncTimeoutFalse(Sync):
    def __init__(self,
                 cmd_runners: StrOrList,
                 targets: StrOrSet,
                 timeout: IntOrFloat,
                 stopped_remotes: Optional[set[str]] = None,
                 timeout_remotes: Optional[set[str]] = None,
                 conflict_remotes: Optional[set[str]] = None,
                 error_stopped_target: bool = True,
                 log_msg: Optional[str] = None) -> None:
        super().__init__(cmd_runners=cmd_runners,
                         targets=targets,
                         timeout=timeout,
                         timeout_remotes=timeout_remotes,
                         stopped_remotes=stopped_remotes,
                         conflict_remotes=conflict_remotes,
                         error_stopped_target=error_stopped_target,
                         log_msg=log_msg)
        self.specified_args = locals()  # used for __repr__

        self.arg_list += ['timeout']

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        targets = self.targets - {cmd_runner}
        self.config_ver.handle_sync(
            cmd_runner=cmd_runner,
            targets=targets,
            timeout=self.timeout,
            timeout_remotes=self.timeout_remotes,
            stopped_remotes=self.stopped_remotes,
            conflict_remotes=self.conflict_remotes,
            timeout_type=TimeoutType.TimeoutFalse,
            error_stopped_target=self.error_stopped_target,
            log_msg=self.log_msg)


########################################################################
# SyncTimeoutFalse
########################################################################
class SyncTimeoutTrue(SyncTimeoutFalse):
    def __init__(self,
                 cmd_runners: StrOrList,
                 targets: StrOrSet,
                 timeout: IntOrFloat,
                 timeout_remotes: set[str],
                 stopped_remotes: Optional[set[str]] = None,
                 conflict_remotes: Optional[set[str]] = None,
                 error_stopped_target: bool = True,
                 log_msg: Optional[str] = None) -> None:
        super().__init__(cmd_runners=cmd_runners,
                         targets=targets,
                         timeout=timeout,
                         timeout_remotes=timeout_remotes,
                         stopped_remotes=stopped_remotes,
                         conflict_remotes=conflict_remotes,
                         error_stopped_target=error_stopped_target,
                         log_msg=log_msg)
        self.specified_args = locals()  # used for __repr__

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        targets = self.targets - {cmd_runner}
        self.config_ver.handle_sync(
            cmd_runner=cmd_runner,
            targets=targets,
            timeout=self.timeout,
            timeout_remotes=self.timeout_remotes,
            stopped_remotes=self.stopped_remotes,
            conflict_remotes=self.conflict_remotes,
            timeout_type=TimeoutType.TimeoutTrue,
            error_stopped_target=self.error_stopped_target,
            log_msg=self.log_msg)


########################################################################
# Unregister
########################################################################
class Unregister(ConfigCmd):
    def __init__(self,
                 cmd_runners: StrOrList,
                 unregister_targets: StrOrList,
                 log_msg: Optional[str] = None) -> None:
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

        if isinstance(unregister_targets, str):
            unregister_targets = [unregister_targets]
        self.unregister_targets = unregister_targets

        self.log_msg = log_msg

        self.arg_list += ['unregister_targets']

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.handle_unregister(
            cmd_runner=cmd_runner,
            unregister_targets=self.unregister_targets,
            log_msg=self.log_msg)


########################################################################
# ValidateConfig
########################################################################
class ValidateConfig(ConfigCmd):
    def __init__(self,
                 cmd_runners: StrOrList) -> None:
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
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

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
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

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
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

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.verify_is_active(
            cmd_runner=cmd_runner,
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

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.verify_counts(num_registered=self.exp_num_registered,
                                      num_active=self.exp_num_active,
                                      num_stopped=self.exp_num_stopped)


########################################################################
# VerifyDefDel
########################################################################
class VerifyDefDel(ConfigCmd):
    def __init__(self,
                 cmd_runners: StrOrList,
                 def_del_scenario: DefDelScenario,
                 receiver_names: list[str],
                 sender_names: list[str],
                 waiter_names: list[str],
                 resumer_names: list[str],
                 del_names: list[str],
                 add_names: list[str],
                 deleter_names: list[str],
                 adder_names: list[str]
                 ) -> None:
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

        self.def_del_scenario = def_del_scenario
        self.receiver_names = receiver_names
        self.sender_names = sender_names
        self.waiter_names = waiter_names
        self.resumer_names = resumer_names
        self.del_names = del_names
        self.add_names = add_names
        self.deleter_names = deleter_names
        self.adder_names = adder_names

        self.arg_list += ['def_del_scenario']

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.verify_def_del(
            cmd_runner=cmd_runner,
            def_del_scenario=self.def_del_scenario,
            receiver_names=self.receiver_names,
            sender_names=self.sender_names,
            waiter_names=self.waiter_names,
            resumer_names=self.resumer_names,
            del_names=self.del_names,
            add_names=self.add_names,
            deleter_names=self.deleter_names,
            adder_names=self.adder_names
        )


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

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.verify_in_registry(
            cmd_runner=cmd_runner,
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

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.verify_in_registry_not(
            cmd_runner=cmd_runner,
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

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.verify_is_registered(
            cmd_runner=cmd_runner,
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

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.verify_paired(
            cmd_runner=cmd_runner,
            exp_paired_names=self.exp_paired_names)


########################################################################
# VerifyPairedHalf
########################################################################
class VerifyPairedHalf(ConfigCmd):
    def __init__(self,
                 cmd_runners: StrOrList,
                 removed_names: StrOrList,
                 exp_half_paired_names: StrOrList) -> None:
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

        if isinstance(removed_names, str):
            removed_names = [removed_names]
        self.removed_names = removed_names

        if isinstance(exp_half_paired_names, str):
            exp_half_paired_names = [exp_half_paired_names]
        self.exp_half_paired_names = exp_half_paired_names

        self.arg_list += ['removed_names',
                          'exp_half_paired_names']

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.verify_paired_half(
            cmd_runner=cmd_runner,
            removed_names=self.removed_names,
            exp_half_paired_names=self.exp_half_paired_names)


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

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.verify_paired_not(
            cmd_runner=cmd_runner,
            exp_not_paired_names=self.exp_not_paired_names)


########################################################################
# VerifyStatus
########################################################################
class VerifyStatus(ConfigCmd):
    def __init__(self,
                 cmd_runners: StrOrList,
                 check_status_names: StrOrList,
                 expected_status: st.ThreadState
                 ) -> None:
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

        if isinstance(check_status_names, str):
            check_status_names = [check_status_names]
        self.check_status_names = check_status_names

        self.expected_status = expected_status

        self.arg_list += ['check_status_names',
                          'expected_status']

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.verify_status(
            cmd_runner=cmd_runner,
            check_status_names=self.check_status_names,
            expected_status=self.expected_status)


########################################################################
# Wait
########################################################################
class Wait(ConfigCmd):
    def __init__(self,
                 cmd_runners: StrOrList,
                 resumers: StrOrList,
                 wait_for: st.WaitFor = st.WaitFor.All,
                 stopped_remotes: Optional[set[str]] = None,
                 conflict_remotes: Optional[set[str]] = None,
                 deadlock_remotes: Optional[set[str]] = None,
                 error_stopped_target: bool = True,
                 log_msg: Optional[str] = None) -> None:
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

        if isinstance(resumers, str):
            resumers = [resumers]
        self.resumers = resumers

        if stopped_remotes:
            self.stopped_remotes = stopped_remotes
        else:
            self.stopped_remotes = set()

        if conflict_remotes:
            self.conflict_remotes = conflict_remotes
        else:
            self.conflict_remotes = set()

        if deadlock_remotes:
            self.deadlock_remotes = deadlock_remotes
        else:
            self.deadlock_remotes = set()

        self.wait_for = wait_for
        self.log_msg = log_msg
        self.error_stopped_target = error_stopped_target

        self.arg_list += ['resumers',
                          'wait_for',
                          'error_stopped_target']

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.handle_wait(
            cmd_runner=cmd_runner,
            resumers=self.resumers,
            timeout=0,
            timeout_remotes=set(),
            stopped_remotes=self.stopped_remotes,
            conflict_remotes=self.conflict_remotes,
            deadlock_remotes=self.deadlock_remotes,
            timeout_type=TimeoutType.TimeoutNone,
            wait_for=self.wait_for,
            error_stopped_target=self.error_stopped_target,
            log_msg=self.log_msg)


########################################################################
# WaitTimeoutFalse
########################################################################
class WaitTimeoutFalse(Wait):
    def __init__(self,
                 cmd_runners: StrOrList,
                 resumers: StrOrList,
                 timeout: IntOrFloat,
                 wait_for: st.WaitFor = st.WaitFor.All,
                 stopped_remotes: Optional[set[str]] = None,
                 conflict_remotes: Optional[set[str]] = None,
                 deadlock_remotes: Optional[set[str]] = None,
                 error_stopped_target: bool = True,
                 log_msg: Optional[str] = None) -> None:
        super().__init__(cmd_runners=cmd_runners,
                         resumers=resumers,
                         stopped_remotes=stopped_remotes,
                         wait_for=wait_for,
                         conflict_remotes=conflict_remotes,
                         deadlock_remotes=deadlock_remotes,
                         error_stopped_target=error_stopped_target,
                         log_msg=log_msg)
        self.specified_args = locals()  # used for __repr__

        self.timeout = timeout

        self.arg_list += ['timeout']

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.handle_wait(
            cmd_runner=cmd_runner,
            resumers=self.resumers,
            timeout=self.timeout,
            timeout_remotes=set(),
            stopped_remotes=self.stopped_remotes,
            conflict_remotes=self.conflict_remotes,
            deadlock_remotes=self.deadlock_remotes,
            timeout_type=TimeoutType.TimeoutFalse,
            wait_for=self.wait_for,
            error_stopped_target=self.error_stopped_target,
            log_msg=self.log_msg)


########################################################################
# WaitTimeoutTrue
########################################################################
class WaitTimeoutTrue(WaitTimeoutFalse):
    def __init__(self,
                 cmd_runners: StrOrList,
                 resumers: StrOrList,
                 timeout: IntOrFloat,
                 timeout_remotes: set[str],
                 wait_for: st.WaitFor = st.WaitFor.All,
                 stopped_remotes: Optional[set[str]] = None,
                 conflict_remotes: Optional[set[str]] = None,
                 deadlock_remotes: Optional[set[str]] = None,
                 error_stopped_target: bool = True,
                 log_msg: Optional[str] = None
                 ) -> None:
        super().__init__(cmd_runners=cmd_runners,
                         resumers=resumers,
                         stopped_remotes=stopped_remotes,
                         wait_for=wait_for,
                         conflict_remotes=conflict_remotes,
                         deadlock_remotes=deadlock_remotes,
                         error_stopped_target=error_stopped_target,
                         timeout=timeout,
                         log_msg=log_msg)
        self.specified_args = locals()  # used for __repr__

        self.timeout_remotes = timeout_remotes

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.handle_wait(
            cmd_runner=cmd_runner,
            resumers=self.resumers,
            timeout=self.timeout,
            timeout_remotes=self.timeout_remotes,
            stopped_remotes=self.stopped_remotes,
            conflict_remotes=self.conflict_remotes,
            deadlock_remotes=self.deadlock_remotes,
            timeout_type=TimeoutType.TimeoutTrue,
            wait_for=self.wait_for,
            error_stopped_target=self.error_stopped_target,
            log_msg=self.log_msg)


########################################################################
# WaitForRecvTimeouts
########################################################################
class WaitForRecvTimeouts(ConfigCmd):
    def __init__(self,
                 cmd_runners: StrOrList) -> None:
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.wait_for_recv_msg_timeouts(cmd_runner=cmd_runner)


########################################################################
# WaitForResumeTimeouts
########################################################################
class WaitForResumeTimeouts(ConfigCmd):
    def __init__(self,
                 cmd_runners: StrOrList,
                 resumer_names: StrOrList,
                 timeout_names: StrOrList) -> None:
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

        if isinstance(resumer_names, str):
            resumer_names = [resumer_names]
        self.resumer_names = resumer_names

        if isinstance(timeout_names, str):
            timeout_names = [timeout_names]
        self.timeout_names = timeout_names

        self.arg_list += ['resumer_names',
                          'timeout_names']

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.wait_for_resume_timeouts(
            cmd_runner=cmd_runner,
            resumer_names=self.resumer_names,
            timeout_names=self.timeout_names)


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

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.wait_for_send_msg_timeouts(
            cmd_runner=cmd_runner,
            sender_names=self.sender_names,
            unreg_names=self.unreg_names,
            fullq_names=self.fullq_names)


########################################################################
# WaitForSyncTimeouts
########################################################################
class WaitForSyncTimeouts(ConfigCmd):
    def __init__(self,
                 cmd_runners: StrOrList,
                 syncer_names: StrOrList,
                 timeout_names: StrOrList,
                 ) -> None:
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

        if isinstance(syncer_names, str):
            syncer_names = [syncer_names]
        self.syncer_names = syncer_names

        if isinstance(timeout_names, str):
            timeout_names = [timeout_names]
        self.timeout_names = timeout_names

        self.arg_list += ['timeout_names',
                          'syncer_names']

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.wait_for_sync_timeouts(
            cmd_runner=cmd_runner,
            syncer_names=self.syncer_names,
            timeout_names=self.timeout_names)

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
# num_registered_1_arg
###############################################################################
@pytest.fixture(params=def_del_scenario_arg_list)  # type: ignore
def def_del_scenario_arg(request: Any) -> DefDelScenario:
    """Type of deferred delete to do.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(DefDelScenario, request.param)


###############################################################################
# conflict_deadlock_1_arg
###############################################################################
@pytest.fixture(params=conflict_deadlock_arg_list)  # type: ignore
def conflict_deadlock_1_arg(request: Any) -> ConflictDeadlockScenario:
    """Type of deferred delete to do.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(ConflictDeadlockScenario, request.param)


###############################################################################
# conflict_deadlock_2_arg
###############################################################################
@pytest.fixture(params=conflict_deadlock_arg_list2)  # type: ignore
def conflict_deadlock_2_arg(request: Any) -> ConflictDeadlockScenario:
    """Type of deferred delete to do.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(ConflictDeadlockScenario, request.param)


###############################################################################
# conflict_deadlock_3_arg
###############################################################################
@pytest.fixture(params=conflict_deadlock_arg_list3)  # type: ignore
def conflict_deadlock_3_arg(request: Any) -> ConflictDeadlockScenario:
    """Type of deferred delete to do.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(ConflictDeadlockScenario, request.param)


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
# num_resumers_arg
###############################################################################
@pytest.fixture(params=num_resumers_arg_list)  # type: ignore
def num_resumers_arg(request: Any) -> int:
    """Number of threads the do resumes.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


###############################################################################
# num_active_arg
###############################################################################
@pytest.fixture(params=num_active_arg_list)  # type: ignore
def num_active_arg(request: Any) -> int:
    """Number of active threads.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


###############################################################################
# num_registered_before_arg
###############################################################################
@pytest.fixture(params=num_registered_before_arg_list)  # type: ignore
def num_registered_before_arg(request: Any) -> int:
    """Number opf registered threads.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


###############################################################################
# num_registered_after_arg
###############################################################################
@pytest.fixture(params=num_registered_after_arg_list)  # type: ignore
def num_registered_after_arg(request: Any) -> int:
    """Number opf registered threads.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


###############################################################################
# num_unreg_no_delay_arg
###############################################################################
@pytest.fixture(params=num_unreg_no_delay_arg_list)  # type: ignore
def num_unreg_no_delay_arg(request: Any) -> int:
    """Number unregistered threads quickly created and started.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)

###############################################################################
# num_unreg_delay_arg
###############################################################################
@pytest.fixture(params=num_unreg_delay_arg_list)  # type: ignore
def num_unreg_delay_arg(request: Any) -> int:
    """Number unregistered threads slowly created and started.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


###############################################################################
# num_stopped_no_delay_arg
###############################################################################
@pytest.fixture(params=num_stopped_no_delay_arg_list)  # type: ignore
def num_stopped_no_delay_arg(request: Any) -> int:
    """Number stopped threads.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


###############################################################################
# num_stopped_delay_arg
###############################################################################
@pytest.fixture(params=num_stopped_delay_arg_list)  # type: ignore
def num_stopped_delay_arg(request: Any) -> int:
    """Number stopped threads quickly joined, created, and started.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


########################################################################
# num_waiters_arg
########################################################################
@pytest.fixture(params=num_waiters_arg_list)  # type: ignore
def num_waiters_arg(request: Any) -> int:
    """Number stopped threads quickly joined, created, and started.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


########################################################################
# num_syncers_arg
########################################################################
@pytest.fixture(params=num_syncers_arg_list)  # type: ignore
def num_syncers_arg(request: Any) -> int:
    """Number stopped threads quickly joined, created, and started.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


########################################################################
# num_stopped_syncers_arg
########################################################################
@pytest.fixture(params=num_stopped_syncers_arg_list)  # type: ignore
def num_stopped_syncers_arg(request: Any) -> int:
    """Number stopped threads quickly joined, created, and started.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


########################################################################
# num_timeout_syncers_arg
########################################################################
@pytest.fixture(params=num_timeout_syncers_arg_list)  # type: ignore
def num_timeout_syncers_arg(request: Any) -> int:
    """Number stopped threads quickly joined, created, and started.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


########################################################################
# error_stopped_target_arg
########################################################################
@pytest.fixture(params=error_stopped_target_arg_list)  # type: ignore
def error_stopped_target_arg(request: Any) -> bool:
    """Number stopped threads quickly joined, created, and started.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(bool, request.param)


########################################################################
# num_actors_arg
########################################################################
@pytest.fixture(params=num_actors_arg_list)  # type: ignore
def num_actors_arg(request: Any) -> int:
    """Number stopped threads quickly joined, created, and started.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


########################################################################
# num_cd_actors_arg
########################################################################
@pytest.fixture(params=num_cd_actors_arg_list)  # type: ignore
def num_cd_actors_arg(request: Any) -> int:
    """Number stopped threads quickly joined, created, and started.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)

########################################################################
# actor_1_arg
########################################################################
@pytest.fixture(params=actor_1_arg_list)  # type: ignore
def actor_1_arg(request: Any) -> Actors:
    """Type of actor tpo perfom the cmd.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(Actors, request.param)


########################################################################
# num_actor_1_arg
########################################################################
@pytest.fixture(params=num_actor_1_arg_list)  # type: ignore
def num_actor_1_arg(request: Any) -> int:
    """Number of actors for actor style 1.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


########################################################################
# actor_2_arg
########################################################################
@pytest.fixture(params=actor_2_arg_list)  # type: ignore
def actor_2_arg(request: Any) -> Actors:
    """Type of actor tpo perfom the cmd.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(Actors, request.param)


########################################################################
# num_actor_2_arg
########################################################################
@pytest.fixture(params=num_actor_2_arg_list)  # type: ignore
def num_actor_2_arg(request: Any) -> int:
    """Number of actors for actor style 1.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


########################################################################
# actor_3_arg
########################################################################
@pytest.fixture(params=actor_3_arg_list)  # type: ignore
def actor_3_arg(request: Any) -> Actors:
    """Type of actor tpo perfom the cmd.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(Actors, request.param)


########################################################################
# num_actor_3_arg
########################################################################
@pytest.fixture(params=num_actor_3_arg_list)  # type: ignore
def num_actor_3_arg(request: Any) -> int:
    """Number of actors for actor style 1.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


# ########################################################################
# # num_active_no_delay_resumers_arg
# ########################################################################
# @pytest.fixture(params=num_active_no_delay_resumers_arg_list)  # type: ignore
# def num_active_no_delay_resumers_arg(request: Any) -> int:
#     """Number stopped threads quickly joined, created, and started.
#
#     Args:
#         request: special fixture that returns the fixture params
#
#     Returns:
#         The params values are returned one at a time
#     """
#     return cast(int, request.param)
#
#
# ########################################################################
# # num_active_delay_resumers_arg
# ########################################################################
# @pytest.fixture(params=num_active_delay_resumers_arg_list)  # type: ignore
# def num_active_delay_resumers_arg(request: Any) -> int:
#     """Number stopped threads quickly joined, created, and started.
#
#     Args:
#         request: special fixture that returns the fixture params
#
#     Returns:
#         The params values are returned one at a time
#     """
#     return cast(int, request.param)
#
#
# ########################################################################
# # num_resume_exit_arg
# ########################################################################
# @pytest.fixture(params=num_resume_exit_arg_list)  # type: ignore
# def num_resume_exit_arg(request: Any) -> int:
#     """Number stopped threads quickly joined, created, and started.
#
#     Args:
#         request: special fixture that returns the fixture params
#
#     Returns:
#         The params values are returned one at a time
#     """
#     return cast(int, request.param)
#
#
# ########################################################################
# # num_noresume_exit_arg
# ########################################################################
# @pytest.fixture(params=num_noresume_exit_arg_list)  # type: ignore
# def num_noresume_exit_arg(request: Any) -> int:
#     """Number stopped threads quickly joined, created, and started.
#
#     Args:
#         request: special fixture that returns the fixture params
#
#     Returns:
#         The params values are returned one at a time
#     """
#     return cast(int, request.param)
#
#
# ########################################################################
# # num_unreg_resumers_arg
# ########################################################################
# @pytest.fixture(params=num_unreg_resumers_arg_list)  # type: ignore
# def num_unreg_resumers_arg(request: Any) -> int:
#     """Number stopped threads quickly joined, created, and started.
#
#     Args:
#         request: special fixture that returns the fixture params
#
#     Returns:
#         The params values are returned one at a time
#     """
#     return cast(int, request.param)
#
#
# ########################################################################
# # num_reg_resumers_arg
# ########################################################################
# @pytest.fixture(params=num_reg_resumers_arg_list)  # type: ignore
# def num_reg_resumers_arg(request: Any) -> int:
#     """Number stopped threads quickly joined, created, and started.
#
#     Args:
#         request: special fixture that returns the fixture params
#
#     Returns:
#         The params values are returned one at a time
#     """
#     return cast(int, request.param)


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
    status: st.ThreadState
    found_del_pairs: dict[tuple[str, str, str], int]
    num_refresh: int = 0
    stopped_by: str = ''


@dataclass
class ThreadPairStatus:
    """Class that keeps pair status."""
    pending_ops_count: int
    # pending_wait_count: int
    # expected_last_reg_updates: deque


@dataclass
class MonitorAddItem:
    """Class keeps track of threads to add, start, delete, unreg."""
    cmd_runner: str
    thread_alive: bool
    auto_start: bool
    expected_status: st.ThreadState


@dataclass
class UpaItem:
    upa_cmd_runner: str
    upa_type: str
    upa_target: str
    upa_def_del_name: str
    upa_process: str


@dataclass
class MonitorEventItem:
    """Class keeps track of threads to add, start, delete, unreg."""
    client_event: threading.Event
    targets: list[str]
    deferred_post_needed: bool = False


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
                 config_ver: "ConfigVerifier",
                 found_log_msg: str = '',
                 found_log_idx: int = 0,
                 ) -> None:
        """Initialize the LogItem.

        Args:
            search_str: regex style search string
            config_ver: configuration verifier
        """
        self.search_pattern = re.compile(search_str)
        self.config_ver: "ConfigVerifier" = config_ver
        self.found_log_msg = found_log_msg
        self.found_log_idx = found_log_idx

    @abstractmethod
    def get_found_log_item(self,
                           found_log_msg: str,
                           found_log_idx: int) -> "LogSearchItem":
        """Return a found log item.

        Args:
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found

        Returns:
            LogFoundItem containing found message and index
        """
        pass

    @abstractmethod
    def run_process(self) -> None:
        """Run the command for the log msg."""
        pass


########################################################################
# EnterRpaLogSearchItem
########################################################################
class EnterRpaLogSearchItem(LogSearchItem):
    """Input to search log msgs."""

    def __init__(self,
                 config_ver: "ConfigVerifier",
                 found_log_msg: str = '',
                 found_log_idx: int = 0,
                 ) -> None:
        """Initialize the LogItem.

        Args:
            config_ver: configuration verifier
        """
        super().__init__(
            search_str=f'[a-z]+ entered _refresh_pair_array',
            config_ver=config_ver,
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx
        )

    def get_found_log_item(self,
                           found_log_msg: str,
                           found_log_idx: int) -> "EnterRpaLogSearchItem":
        """Return a found log item.

        Args:
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found

        Returns:
            EnterRpaLogSearchItem containing found message and index
        """
        return EnterRpaLogSearchItem(
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
            config_ver=self.config_ver)

    def run_process(self):
        self.config_ver.handle_enter_rpa_log_msg(
            cmd_runner=self.found_log_msg.split(maxsplit=1)[0])


########################################################################
# UpdatePaLogSearchItem
########################################################################
class UpdatePaLogSearchItem(LogSearchItem):
    """Input to search log msgs."""

    def __init__(self,
                 config_ver: "ConfigVerifier",
                 found_log_msg: str = '',
                 found_log_idx: int = 0,
                 ) -> None:
        """Initialize the LogItem.

        Args:
            config_ver: configuration verifier
        """
        super().__init__(
            search_str=f'[a-z]+ updated _pair_array at UTC {time_match}',
            config_ver=config_ver,
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx
        )

    def get_found_log_item(self,
                           found_log_msg: str,
                           found_log_idx: int) -> "UpdatePaLogSearchItem":
        """Return a found log item.

        Args:
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found

        Returns:
            UpdatePaLogSearchItem containing found message and index
        """
        return UpdatePaLogSearchItem(
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
            config_ver=self.config_ver)

    def run_process(self):
        self.config_ver.handle_pair_array_update(
            cmd_runner=self.found_log_msg.split(maxsplit=1)[0],
            upa_msg=self.found_log_msg,
            upa_msg_idx=self.found_log_idx)


########################################################################
# RegUpdateLogSearchItem
########################################################################
class RegUpdateLogSearchItem(LogSearchItem):
    """Input to search log msgs."""

    def __init__(self,
                 config_ver: "ConfigVerifier",
                 found_log_msg: str = '',
                 found_log_idx: int = 0,
                 ) -> None:
        """Initialize the LogItem.

        Args:
            config_ver: configuration verifier
        """
        super().__init__(
            # search_str=f'[a-z]+ did registry update at UTC {time_match}',
            search_str=(f'[a-z]+ added [a-z]+ to SmartThread registry at UTC '
                        f'{time_match}'),
            config_ver=config_ver,
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx
        )

    def get_found_log_item(self,
                           found_log_msg: str,
                           found_log_idx: int) -> "RegUpdateLogSearchItem":
        """Return a found log item.

        Args:
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found

        Returns:
            RegUpdateLogSearchItem containing found message and index
        """
        return RegUpdateLogSearchItem(
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
            config_ver=self.config_ver)

    def run_process(self):
        split_msg = self.found_log_msg.split()
        self.config_ver.handle_reg_update(
            cmd_runner=split_msg[0],
            new_name=split_msg[2],
            reg_update_msg=self.found_log_msg,
            reg_update_msg_log_idx=self.found_log_idx)


########################################################################
# RegRemoveLogSearchItem
########################################################################
class RegRemoveLogSearchItem(LogSearchItem):
    """Input to search log msgs."""

    def __init__(self,
                 config_ver: "ConfigVerifier",
                 found_log_msg: str = '',
                 found_log_idx: int = 0,
                 ) -> None:
        """Initialize the LogItem.

        Args:
            config_ver: configuration verifier
        """
        super().__init__(
            search_str=("[a-z]+ removed [a-z]+ from registry for "
                        "process='(join|unregister)'"),
            config_ver=config_ver,
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx
        )

    def get_found_log_item(self,
                           found_log_msg: str,
                           found_log_idx: int) -> "RegRemoveLogSearchItem":
        """Return a found log item.

        Args:
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found

        Returns:
            RegRemoveLogSearchItem containing found message and index
        """
        return RegRemoveLogSearchItem(
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
            config_ver=self.config_ver)

    def run_process(self):
        split_msg = self.found_log_msg.split()
        process = split_msg[6].split(sep='=')[1]
        process = process[1:-1]

        self.config_ver.handle_reg_remove(cmd_runner=split_msg[0],
                                          del_name=split_msg[2],
                                          process=process,
                                          reg_rem_log_idx=self.found_log_idx)


########################################################################
# CleanRegLogSearchItem
########################################################################
class CleanRegLogSearchItem(LogSearchItem):
    """Input to search log msgs."""

    def __init__(self,
                 config_ver: "ConfigVerifier",
                 found_log_msg: str = '',
                 found_log_idx: int = 0,
                 ) -> None:
        """Initialize the LogItem.

        Args:
            config_ver: configuration verifier
        """
        super().__init__(
            search_str=(f"[a-z]+ did cleanup of registry at UTC {time_match}, "
                        "deleted \['[a-z]+'\]"),
            config_ver=config_ver,
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx
        )

    def get_found_log_item(self,
                           found_log_msg: str,
                           found_log_idx: int) -> "CleanRegLogSearchItem":
        """Return a found log item.

        Args:
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found

        Returns:
            CleanRegLogSearchItem containing found message and index
        """
        return CleanRegLogSearchItem(
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
            config_ver=self.config_ver)

    def run_process(self):
        self.config_ver.add_log_msg(re.escape(self.found_log_msg))
        self.config_ver.last_clean_reg_log_msg = self.found_log_msg


########################################################################
# RecvMsgLogSearchItem
########################################################################
class RecvMsgLogSearchItem(LogSearchItem):
    """Input to search log msgs."""

    def __init__(self,
                 config_ver: "ConfigVerifier",
                 found_log_msg: str = '',
                 found_log_idx: int = 0,
                 ) -> None:
        """Initialize the LogItem.

        Args:
            config_ver: configuration verifier
        """
        super().__init__(
            search_str=f'[a-z]+ received msg from [a-z]+',
            config_ver=config_ver,
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx
        )

    def get_found_log_item(self,
                           found_log_msg: str,
                           found_log_idx: int) -> "RecvMsgLogSearchItem":
        """Return a found log item.

        Args:
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found

        Returns:
            RecvMsgLogSearchItem containing found message and index
        """
        return RecvMsgLogSearchItem(
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
            config_ver=self.config_ver)

    def run_process(self):
        split_msg = self.found_log_msg.split()

        self.config_ver.dec_ops_count(
            cmd_runner=split_msg[0],
            sender=split_msg[4],
            dec_ops_type='recv_msg')


########################################################################
# WaitResumedLogSearchItem
########################################################################
class WaitResumedLogSearchItem(LogSearchItem):
    """Input to search log msgs."""

    def __init__(self,
                 config_ver: "ConfigVerifier",
                 found_log_msg: str = '',
                 found_log_idx: int = 0,
                 ) -> None:
        """Initialize the LogItem.

        Args:
            config_ver: configuration verifier
        """
        super().__init__(
            search_str=f'[a-z]+ smart_wait resumed by [a-z]+',
            config_ver=config_ver,
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx
        )

    def get_found_log_item(self,
                           found_log_msg: str,
                           found_log_idx: int) -> "WaitResumedLogSearchItem":
        """Return a found log item.

        Args:
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found

        Returns:
            WaitResumedLogSearchItem containing found message and index
        """
        return WaitResumedLogSearchItem(
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
            config_ver=self.config_ver)

    def run_process(self):
        split_msg = self.found_log_msg.split()

        self.config_ver.dec_ops_count(
            cmd_runner=split_msg[0],
            sender=split_msg[4],
            dec_ops_type='wait')


########################################################################
# StartedLogSearchItem
########################################################################
class StartedLogSearchItem(LogSearchItem):
    """Input to search log msgs."""

    def __init__(self,
                 config_ver: "ConfigVerifier",
                 found_log_msg: str = '',
                 found_log_idx: int = 0,
                 ) -> None:
        """Initialize the LogItem.

        Args:
            config_ver: configuration verifier
        """
        super().__init__(
            search_str=('[a-z]+ started thread [a-z]+, '
                        'thread.is_alive\(\): True, '
                        'status: ThreadStatus.Alive'),
            config_ver=config_ver,
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx
        )

    def get_found_log_item(self,
                           found_log_msg: str,
                           found_log_idx: int) -> "StartedLogSearchItem":
        """Return a found log item.

        Args:
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found

        Returns:
            StartedLogSearchItem containing found message and index
        """
        return StartedLogSearchItem(
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
            config_ver=self.config_ver)

    def run_process(self):
        split_msg = self.found_log_msg.split()

        self.config_ver.handle_started_log_msg(
            cmd_runner=split_msg[0],
            started_name=split_msg[3][0:-1])


########################################################################
# StoppedLogSearchItem
########################################################################
class StoppedLogSearchItem(LogSearchItem):
    """Input to search log msgs."""

    def __init__(self,
                 config_ver: "ConfigVerifier",
                 found_log_msg: str = '',
                 found_log_idx: int = 0,
                 ) -> None:
        """Initialize the LogItem.

        Args:
            config_ver: configuration verifier
        """
        super().__init__(
            search_str='[a-z]+ has been stopped by [a-z]+',
            config_ver=config_ver,
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx
        )

    def get_found_log_item(self,
                           found_log_msg: str,
                           found_log_idx: int) -> "StoppedLogSearchItem":
        """Return a found log item.

        Args:
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found

        Returns:
            StoppedLogSearchItem containing found message and index
        """
        return StoppedLogSearchItem(
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
            config_ver=self.config_ver)

    def run_process(self):
        split_msg = self.found_log_msg.split()

        self.config_ver.handle_stopped_log_msg(
            cmd_runner=split_msg[5],
            stopped_name=split_msg[0],
            log_idx=self.found_log_idx)


########################################################################
# CmdWaitingLogSearchItem
########################################################################
class CmdWaitingLogSearchItem(LogSearchItem):
    """Input to search log msgs."""

    def __init__(self,
                 config_ver: "ConfigVerifier",
                 found_log_msg: str = '',
                 found_log_idx: int = 0,
                 ) -> None:
        """Initialize the LogItem.

        Args:
            config_ver: configuration verifier
        """
        list_of_waiting_methods = ('(create_commander_thread'
                                   '|create_f1_thread'
                                   '|handle_join'
                                   '|handle_join_tof'
                                   '|handle_join_tot'
                                   '|handle_recv'
                                   '|handle_recv_tof'
                                   '|handle_recv_tot'
                                   '|handle_resume'
                                   '|handle_sync'
                                   '|handle_wait'
                                   '|handle_unregister)')
        super().__init__(
            search_str=(f"cmd_runner='[a-z]+' {list_of_waiting_methods} "
                        "waiting for monitor"),
            config_ver=config_ver,
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx
        )

    def get_found_log_item(self,
                           found_log_msg: str,
                           found_log_idx: int
                           ) -> "CmdWaitingLogSearchItem":
        """Return a found log item.

        Args:
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found

        Returns:
            CmdWaitingLogSearchItem containing found message and index
        """
        return CmdWaitingLogSearchItem(
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
            config_ver=self.config_ver)

    def run_process(self):
        split_msg = self.found_log_msg.split()
        cmd_runner = split_msg[0].split(sep='=')[1]
        cmd_runner = cmd_runner[1:-1]

        self.config_ver.handle_cmd_waiting_log_msg(
            cmd_runner=cmd_runner)


########################################################################
# SyncResumedLogSearchItem
########################################################################
class SyncResumedLogSearchItem(LogSearchItem):
    """Input to search log msgs."""

    def __init__(self,
                 config_ver: "ConfigVerifier",
                 found_log_msg: str = '',
                 found_log_idx: int = 0,
                 ) -> None:
        """Initialize the LogItem.

        Args:
            config_ver: configuration verifier
        """
        super().__init__(
            search_str=f'[a-z]+ smart_sync resumed by [a-z]+',
            config_ver=config_ver,
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx
        )

    def get_found_log_item(self,
                           found_log_msg: str,
                           found_log_idx: int
                           ) -> "SyncResumedLogSearchItem":
        """Return a found log item.

        Args:
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found

        Returns:
            SyncResumedLogSearchItem containing found message and index
        """
        return SyncResumedLogSearchItem(
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
            config_ver=self.config_ver)

    def run_process(self):
        self.config_ver.add_log_msg(self.found_log_msg,
                                    log_level=logging.INFO)


########################################################################
# TestDebugLogSearchItem
########################################################################
class TestDebugLogSearchItem(LogSearchItem):
    """Input to search log msgs."""

    def __init__(self,
                 config_ver: "ConfigVerifier",
                 found_log_msg: str = '',
                 found_log_idx: int = 0,
                 ) -> None:
        """Initialize the LogItem.

        Args:
            config_ver: configuration verifier
        """
        super().__init__(
            search_str=f'TestDebug [a-z]+ ',
            config_ver=config_ver,
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx
        )

    def get_found_log_item(self,
                           found_log_msg: str,
                           found_log_idx: int
                           ) -> "TestDebugLogSearchItem":
        """Return a found log item.

        Args:
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found

        Returns:
            SyncResumedLogSearchItem containing found message and index
        """
        return TestDebugLogSearchItem(
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
            config_ver=self.config_ver)

    def run_process(self):
        self.config_ver.add_log_msg(re.escape(self.found_log_msg),
                                    log_level=logging.DEBUG)


LogSearchItems: TypeAlias = Union[
    EnterRpaLogSearchItem,
    UpdatePaLogSearchItem,
    RegUpdateLogSearchItem,
    RegRemoveLogSearchItem,
    CleanRegLogSearchItem,
    RecvMsgLogSearchItem,
    WaitResumedLogSearchItem,
    StartedLogSearchItem,
    StoppedLogSearchItem,
    CmdWaitingLogSearchItem,
    SyncResumedLogSearchItem,
    TestDebugLogSearchItem]


@dataclass
class PaLogMsgsFound:
    entered_rpa: bool
    removed_sb_entry: list[tuple[str, str]]
    removed_pa_entry: list[tuple[str, str]]
    updated_pa: bool


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
        self.cmd_thread_alive = False
        self.cmd_thread_auto_start = False
        self.create_commander_event: threading.Event = threading.Event()

        self.monitor_thread = threading.Thread(target=self.monitor)
        self.monitor_exit = False
        # self.monitor_add_items: list[MonitorAddItem] = []
        self.monitor_add_items: dict[str, MonitorAddItem] = {}

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
        self.all_threads: dict[str, st.SmartThread] = {}
        self.max_msgs = max_msgs

        self.pending_ops_counts: dict[tuple[str, str], dict[str, int]] = {}
        self.expected_num_recv_timouts: int = 0

        # self.del_def_pairs_count: dict[
        #     tuple[str, str, str], int] = defaultdict(int)
        # self.del_def_pairs_msg_count: dict[
        #     tuple[str, str, str], int] = defaultdict(int)
        # self.del_def_pairs_msg_ind_count: dict[
        #     tuple[str, str, str, str], int] = defaultdict(int)

        self.del_deferred_list: list[tuple(tuple[str, str], str)] = []
        self.deferred_dels: dict[tuple[str, str], int] = defaultdict(int)

        # self.found_utc_log_msgs: dict[tuple[str, str], int]= defaultdict(int)
        self.found_update_pair_array_log_msgs: dict[str, int] = defaultdict(
            int)
        # self.recv_msg_event_items: dict[str, MonitorEventItem] = {}
        # self.join_event_items: dict[str, MonitorEventItem] = {}
        # self.unreg_event_items: dict[str, MonitorEventItem] = {}
        # self.started_event_items: dict[str, MonitorEventItem] = {}
        self.stopped_event_items: dict[str, MonitorEventItem] = {}
        self.cmd_waiting_event_items: dict[str, threading.Event] = {}

        self.stopping_names: list[str] = []

        self.recently_stopped: dict[str, int] = defaultdict(int)

        # self.pending_recv_msg_par: dict[str, bool] = defaultdict(bool)
        self.update_pair_array_items: deque[UpaItem] = deque()

        self.log_start_idx: int = 0
        self.log_search_items: tuple[LogSearchItems, ...] = (
            EnterRpaLogSearchItem(config_ver=self),
            UpdatePaLogSearchItem(config_ver=self),
            RegUpdateLogSearchItem(config_ver=self),
            RegRemoveLogSearchItem(config_ver=self),
            CleanRegLogSearchItem(config_ver=self),
            RecvMsgLogSearchItem(config_ver=self),
            WaitResumedLogSearchItem(config_ver=self),
            StartedLogSearchItem(config_ver=self),
            StoppedLogSearchItem(config_ver=self),
            CmdWaitingLogSearchItem(config_ver=self),
            SyncResumedLogSearchItem(config_ver=self),
            TestDebugLogSearchItem(config_ver=self)
        )
        self.last_update_pair_array_log_msg: str = ''
        self.add_thread_cmd_runner_for_upa_msg: str = ''

        self.last_clean_reg_log_msg: str = ''

        self.log_found_items: deque[LogSearchItem] = deque()

        self.monitor_event: threading.Event = threading.Event()
        self.monitor_condition: threading.Condition = threading.Condition()
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

    ####################################################################
    # monitor
    ####################################################################
    def monitor(self):
        self.log_test_msg('monitor entered')

        while not self.monitor_exit:
            self.monitor_event.wait()
            self.monitor_event.clear()

            while self.get_log_msgs():
                while self.log_found_items:
                    found_log_item = self.log_found_items.popleft()

                    # log the log msg being processed but mangle it a
                    # little so we don't find it again and get into a
                    # loop here
                    found_msg = found_log_item.found_log_msg
                    semi_msg = found_msg.replace(' ', ';', 3)
                    self.log_test_msg(f'monitor processing msg: {semi_msg}')

                    found_log_item.run_process()

            with self.monitor_condition:
                self.monitor_condition.notify_all()

    ####################################################################
    # abort_all_f1_threads
    ####################################################################
    def abort_all_f1_threads(self):
        for name, thread in self.all_threads.items():
            if name == self.commander_name:
                continue
            self.add_log_msg(f'aborting f1_thread {name}, '
                             f'thread.is_alive(): {thread.thread.is_alive()}.')
            if thread.thread.is_alive():
                exit_cmd = ExitThread(cmd_runners=name,
                                      stopped_by=self.commander_name)
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
            frame_num: how many frames back to go for line number

        Returns:
            the serial number for the command
        """
        self.cmd_serial_num += 1
        cmd.serial_num = self.cmd_serial_num

        frame = _getframe(frame_num)
        caller_info = get_caller_info(frame)
        cmd.line_num = caller_info.line_num
        cmd.config_ver = self
        del frame

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
                   cmd_runner: str,
                   new_name: str,
                   thread_alive: bool,
                   auto_start: bool,
                   expected_status: st.ThreadState,
                   reg_update_msg: str,
                   reg_idx: int,
                   ) -> None:
        """Add a thread to the ConfigVerifier.

        Args:
            cmd_runner: name of thread doing the cmd
            new_name: name of thread added to registry
            thread_alive: the expected is_alive flag
            auto_start: indicates whether to start the thread
            expected_status: the expected ThreadStatus
            reg_update_msg: the register update msg use for the log msg
            reg_idx: index of reg_update_msg in the log
        """
        self.log_test_msg(f'add_thread entered for {cmd_runner=}, '
                          f'{new_name=}, {thread_alive=}, {expected_status=}')

        self.expected_registered[new_name] = ThreadTracker(
            thread=self.all_threads[new_name],
            is_alive=thread_alive,
            exiting=False,
            is_auto_started=auto_start,
            status=expected_status,
            found_del_pairs=defaultdict(int)
        )

        ################################################################
        # add log msgs
        ################################################################
        self.add_log_msg(
            f'{cmd_runner} set status for thread {new_name} '
            'from ThreadStatus.Unregistered to ThreadStatus.Initializing')

        class_name = self.all_threads[new_name].__class__.__name__
        self.add_log_msg(
            f'{cmd_runner} obtained _registry_lock, '
            f'class name = {class_name}')

        self.handle_exp_status_log_msgs(log_idx=reg_idx,
                                        name=new_name)

        if thread_alive:
            self.add_log_msg(
                f'{cmd_runner} set status for thread {new_name} '
                'from ThreadStatus.Initializing to ThreadStatus.Alive')
        else:
            self.add_log_msg(
                f'{cmd_runner} set status for thread {new_name} '
                'from ThreadStatus.Initializing to ThreadStatus.Registered')
            if (self.expected_registered[new_name].is_auto_started
                    or class_name == 'OuterSmartThreadApp'
                    or class_name == 'OuterSmartThreadApp2'):
                self.add_log_msg(
                    f'{cmd_runner} set status for thread {new_name} '
                    'from ThreadStatus.Registered to ThreadStatus.Starting')

                self.add_log_msg(
                    f'{cmd_runner} set status for thread {new_name} '
                    f'from ThreadStatus.Starting to ThreadStatus.Alive')

                self.add_log_msg(re.escape(
                    f'{cmd_runner} started thread {new_name}, '
                    'thread.is_alive(): True, '
                    'status: ThreadStatus.Alive'))

        # self.add_log_msg(f'{cmd_runner} entered _refresh_pair_array')

        # self.handle_deferred_delete_log_msgs(cmd_runner=cmd_runner)
        # handle any deferred deletes
        # self.handle_deferred_deletes(cmd_runner=cmd_runner)
        self.add_log_msg(re.escape(reg_update_msg))

    ####################################################################
    # build_cd_normal_sync_suite
    ####################################################################
    def build_cd_normal_sync_suite(
            self,
            actor_names: list[str]) -> None:
        """Adds cmds to the cmd queue.

        Args:
            actor_names: names of threads that will do the sync

        """
        sync_serial_num = self.add_cmd(
            Sync(cmd_runners=actor_names,
                 targets=set(actor_names),
                 log_msg='cd normal sync test'))
        self.add_cmd(
            ConfirmResponse(cmd_runners=[self.commander_name],
                            confirm_cmd='Sync',
                            confirm_serial_num=sync_serial_num,
                            confirmers=list(actor_names)))

    ####################################################################
    # build_cd_normal_resume_wait_suite
    ####################################################################
    def build_cd_normal_resume_wait_suite(
            self,
            actor_names: list[str]) -> None:
        """Adds cmds to the cmd queue.

        Args:
            actor_names: names of threads that will do the sync

        """
        mid_point = len(actor_names)//2
        resumers = actor_names[0:mid_point]
        waiters = actor_names[mid_point:]
        resume_serial_num = self.add_cmd(
            Resume(cmd_runners=resumers,
                   targets=waiters,
                   stopped_names=[],
                   log_msg='cd normal resume wait test'))
        self.add_cmd(
            ConfirmResponse(
                cmd_runners=[self.commander_name],
                confirm_cmd='Resume',
                confirm_serial_num=resume_serial_num,
                confirmers=resumers))
        wait_serial_num = self.add_cmd(
            Wait(cmd_runners=waiters,
                 resumers=resumers,
                 stopped_remotes=set(),
                 wait_for=st.WaitFor.All,
                 log_msg='cd normal resume wait test'))
        self.add_cmd(
            ConfirmResponse(
                cmd_runners=[self.commander_name],
                confirm_cmd='Wait',
                confirm_serial_num=wait_serial_num,
                confirmers=waiters))

    ####################################################################
    # build_cd_resume_sync_sync_wait_suite
    ####################################################################
    def build_cd_resume_sync_sync_wait_suite(
            self,
            actor_names: list[str]) -> None:
        """Adds cmds to the cmd queue.

        Args:
            actor_names: names of threads that will do the sync

        """
        mid_point = len(actor_names) // 2
        resumers = actor_names[0:mid_point]
        waiters = actor_names[mid_point:]
        resume_serial_num = self.add_cmd(
            Resume(cmd_runners=resumers,
                   targets=waiters,
                   stopped_names=[],
                   log_msg='cd resume sync sync wait test'))
        self.add_cmd(
            ConfirmResponse(
                cmd_runners=[self.commander_name],
                confirm_cmd='Resume',
                confirm_serial_num=resume_serial_num,
                confirmers=resumers))
        sync_serial_num = self.add_cmd(
            Sync(cmd_runners=actor_names,
                 targets=set(actor_names),
                 log_msg='cd resume sync sync wait test'))
        self.add_cmd(
            ConfirmResponse(cmd_runners=[self.commander_name],
                            confirm_cmd='Sync',
                            confirm_serial_num=sync_serial_num,
                            confirmers=actor_names))
        wait_serial_num = self.add_cmd(
            Wait(cmd_runners=waiters,
                 resumers=resumers,
                 stopped_remotes=set(),
                 wait_for=st.WaitFor.All,
                 log_msg='cd resume sync sync wait test'))
        self.add_cmd(
            ConfirmResponse(
                cmd_runners=[self.commander_name],
                confirm_cmd='Wait',
                confirm_serial_num=wait_serial_num,
                confirmers=waiters))

    ####################################################################
    # build_cd_sync_conflict_suite
    ####################################################################
    def build_cd_sync_conflict_suite(
            self,
            actor_names: list[str]) -> None:
        """Adds cmds to the cmd queue.

        Args:
            actor_names: names of threads that will do the sync

        """
        mid_point = len(actor_names) // 2
        syncers = actor_names[0:mid_point]
        waiters = actor_names[mid_point:]

        sync_serial_num = self.add_cmd(
            Sync(cmd_runners=syncers,
                 targets=set(actor_names),
                 conflict_remotes=set(waiters),
                 log_msg='cd resume sync conflict test'))

        self.add_cmd(
            WaitForSyncTimeouts(
                cmd_runners=self.commander_name,
                syncer_names=syncers,
                timeout_names=waiters))

        wait_serial_num = self.add_cmd(
            Wait(cmd_runners=waiters,
                 resumers=syncers,
                 stopped_remotes=set(),
                 conflict_remotes=set(syncers),
                 wait_for=st.WaitFor.All,
                 log_msg='cd resume sync conflict test'))

        self.add_cmd(
            ConfirmResponse(cmd_runners=[self.commander_name],
                            confirm_cmd='Sync',
                            confirm_serial_num=sync_serial_num,
                            confirmers=syncers))

        self.add_cmd(
            ConfirmResponse(
                cmd_runners=[self.commander_name],
                confirm_cmd='Wait',
                confirm_serial_num=wait_serial_num,
                confirmers=waiters))

    ####################################################################
    # build_cd_wait_deadlock_suite
    ####################################################################
    def build_cd_wait_deadlock_suite(
            self,
            actor_names: list[str]) -> None:
        """Adds cmds to the cmd queue.

        Args:
            actor_names: names of threads that will do the sync

        """
        mid_point = len(actor_names) // 2
        waiters1 = actor_names[0:mid_point]
        waiters2 = actor_names[mid_point:]

        wait_serial_num_1 = self.add_cmd(
            Wait(cmd_runners=waiters1,
                 resumers=waiters2,
                 stopped_remotes=set(),
                 deadlock_remotes=set(waiters2),
                 wait_for=st.WaitFor.All,
                 log_msg='cd wait deadlock test'))

        wait_serial_num_2 = self.add_cmd(
            Wait(cmd_runners=waiters2,
                 resumers=waiters1,
                 stopped_remotes=set(),
                 deadlock_remotes=set(waiters1),
                 wait_for=st.WaitFor.All,
                 log_msg='cd wait deadlock test'))

        self.add_cmd(
            ConfirmResponse(
                cmd_runners=[self.commander_name],
                confirm_cmd='Wait',
                confirm_serial_num=wait_serial_num_1,
                confirmers=waiters1))

        self.add_cmd(
            ConfirmResponse(
                cmd_runners=[self.commander_name],
                confirm_cmd='Wait',
                confirm_serial_num=wait_serial_num_2,
                confirmers=waiters2))

    ####################################################################
    # build_conf_dead_scenario_suite
    ####################################################################
    def build_conf_dead_scenario_suite(
            self,
            scenario_list: list[ConflictDeadlockScenario],
            num_cd_actors: int) -> None:
        """Build ConfigCmd items for sync scenarios.

        Args:
            scenario_list: scenario 1, 2, and 3
            num_cd_actors: number of syncers, resumers, and waiters

        """
        actions: dict[ConflictDeadlockScenario, Callable[..., None]] = {
            ConflictDeadlockScenario.NormalSync:
                self.build_cd_normal_sync_suite,
            ConflictDeadlockScenario.NormalResumeWait:
                self.build_cd_normal_resume_wait_suite,
            ConflictDeadlockScenario.ResumeSyncSyncWait:
                self.build_cd_resume_sync_sync_wait_suite,
            ConflictDeadlockScenario.SyncConflict:
                self.build_cd_sync_conflict_suite,
            ConflictDeadlockScenario.WaitDeadlock:
                self.build_cd_wait_deadlock_suite,
        }
        # Make sure we have enough threads. Note that we subtract 1 from
        # the count of unregistered names to ensure we have one thread
        # for the commander
        assert num_cd_actors <= len(self.unregistered_names) - 1

        self.build_config(
            cmd_runner=self.commander_name,
            num_active=num_cd_actors + 1)

        self.log_name_groups()
        # active_names = self.active_names.copy()
        # remove commander for now, but if we add it later we need to
        # be careful not to exit the commander
        active_names = self.active_names - {self.commander_name}

        ################################################################
        # choose actor_names
        ################################################################
        actor_names = self.choose_names(
            name_collection=active_names,
            num_names_needed=num_cd_actors,
            update_collection=True,
            var_name_for_log='actor_names')

        for scenario in scenario_list:
            actions[scenario](actor_names=actor_names)

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
            cmd_runner: Optional[str] = None,
            commander_name: Optional[str] = None,
            commander_auto_start: Optional[bool] = True,
            f1_create_items: Optional[list[F1CreateItem]] = None,
            validate_config: Optional[bool] = True
            ) -> None:
        """Return a list of ConfigCmd items for a create.

        Args:
            cmd_runner: name of thread to do the creates
            commander_name: specifies that a commander thread is to be
                created with this name
            commander_auto_start: specifies whether to start the
                commander thread during create
            f1_create_items: contain f1_names to create
            validate_config: indicates whether to do config validation

        """
        if commander_name:
            self.commander_name = commander_name
        if cmd_runner:
            cmd_runner_to_use = cmd_runner
        else:
            cmd_runner_to_use = self.commander_name
        if commander_name:
            if not {commander_name}.issubset(self.unregistered_names):
                raise InvalidInputDetected('Input commander name '
                                           f'{commander_name} not a subset of '
                                           'unregistered names '
                                           f'{self.unregistered_names}')
            self.unregistered_names -= {commander_name}

            if commander_auto_start:
                self.add_cmd(
                    CreateCommanderAutoStart(cmd_runners=cmd_runner_to_use,
                                             commander_name=commander_name))

                self.active_names |= {commander_name}
            else:
                self.add_cmd(
                    CreateCommanderNoStart(cmd_runners=cmd_runner_to_use,
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
                    CreateF1AutoStart(cmd_runners=cmd_runner_to_use,
                                      f1_create_items=f1_auto_items))

                self.active_names |= set(f1_auto_start_names)
            elif f1_no_start_items:
                self.add_cmd(
                    CreateF1NoStart(cmd_runners=cmd_runner_to_use,
                                    f1_create_items=f1_no_start_items))
                self.registered_names |= set(f1_no_start_names)

        if self.registered_names:
            self.add_cmd(VerifyRegistered(
                cmd_runners=cmd_runner_to_use,
                exp_registered_names=list(self.registered_names)))

        if self.active_names:
            self.add_cmd(VerifyActive(
                cmd_runners=cmd_runner_to_use,
                exp_active_names=list(self.active_names)))

        if validate_config:
            self.add_cmd(ValidateConfig(cmd_runners=cmd_runner_to_use))

    ####################################################################
    # build_exit_suite
    ####################################################################
    def build_exit_suite(self,
                         cmd_runner: str,
                         names: list[str],
                         validate_config: Optional[bool] = True
                         ) -> None:
        """Add ConfigCmd items for an exit.

        Args:
            cmd_runner: name of thread that will do the cmd
            names: names of threads to exit
            validate_config: specifies whether to validate the
                configuration

        """
        if not set(names).issubset(self.active_names):
            self.abort_all_f1_threads()
            raise InvalidInputDetected(f'Input names {names} not a subset '
                                       f'of active names {self.active_names}')
        active_names = list(self.active_names - set(names))

        if names:
            self.add_cmd(StopThread(cmd_runners=cmd_runner,
                                    stop_names=names))
            if validate_config:
                self.add_cmd(Pause(cmd_runners=cmd_runner,
                                   pause_seconds=.2))
                self.add_cmd(VerifyAliveNot(cmd_runners=cmd_runner,
                                            exp_not_alive_names=names))
                self.add_cmd(VerifyStatus(
                    cmd_runners=cmd_runner,
                    check_status_names=names,
                    expected_status=st.ThreadState.Alive))

        if active_names and validate_config:
            self.add_cmd(VerifyAlive(cmd_runners=cmd_runner,
                                     exp_alive_names=active_names))
            self.add_cmd(VerifyStatus(
                cmd_runners=cmd_runner,
                check_status_names=active_names,
                expected_status=st.ThreadState.Alive))

        if validate_config:
            self.add_cmd(ValidateConfig(cmd_runners=cmd_runner))

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

        return self.build_exit_suite(cmd_runner=self.commander_name,
                                     names=names)

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
                cmd_runners=cmd_runners,
                exp_not_in_registry_names=join_target_names))
            self.add_cmd(VerifyPairedNot(
                cmd_runners=cmd_runners,
                exp_not_paired_names=join_target_names))

        if validate_config:
            self.add_cmd(ValidateConfig(cmd_runners=cmd_runners))

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

        timeout_time = (((num_no_delay_exit
                        + num_no_delay_unreg
                        + num_no_delay_reg) * 0.3)
                        + ((num_delay_exit
                           + num_delay_unreg
                           + num_delay_reg) * 0.6))

        if timeout_type == TimeoutType.TimeoutNone:
            pause_time = 0.5
        elif timeout_type == TimeoutType.TimeoutFalse:
            pause_time = 0.5
            timeout_time += (pause_time * 2)  # prevent timeout
        else:  # timeout True
            pause_time = timeout_time + 1  # force timeout

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
                                 timeout=timeout_time,
                                 log_msg=log_msg))
        else:  # TimeoutType.TimeoutTrue
            confirm_cmd_to_use = 'JoinTimeoutTrue'
            join_serial_num = self.add_cmd(
                JoinTimeoutTrue(cmd_runners=active_no_target_names[0],
                                join_names=all_target_names,
                                timeout=timeout_time,
                                timeout_names=all_timeout_names,
                                log_msg=log_msg))

        ################################################################
        # handle no_delay_exit_names
        ################################################################
        if no_delay_exit_names:
            self.build_exit_suite(cmd_runner=self.commander_name,
                                  names=no_delay_exit_names,
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

            self.build_create_suite(f1_create_items=f1_create_items,
                                    validate_config=False)
            self.build_exit_suite(cmd_runner=self.commander_name,
                                  names=no_delay_unreg_names,
                                  validate_config=False)

        ################################################################
        # handle no_delay_reg_names
        ################################################################
        if no_delay_reg_names:
            self.build_start_suite(start_names=no_delay_reg_names,
                                   validate_config=False)
            self.build_exit_suite(cmd_runner=self.commander_name,
                                  names=no_delay_reg_names,
                                  validate_config=False)

        ################################################################
        # pause for short or long delay
        ################################################################
        if (timeout_type == TimeoutType.TimeoutNone
                or timeout_type == TimeoutType.TimeoutFalse):
            self.add_cmd(
                Pause(cmd_runners=self.commander_name,
                      pause_seconds=pause_time))
        elif timeout_type == TimeoutType.TimeoutTrue:
            self.add_cmd(
                Pause(cmd_runners=self.commander_name,
                      pause_seconds=pause_time))

        ################################################################
        # handle delay_exit_names
        ################################################################
        if delay_exit_names:
            self.build_exit_suite(cmd_runner=self.commander_name,
                                  names=delay_exit_names,
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

            self.build_create_suite(f1_create_items=f1_create_items,
                                    validate_config=False)
            self.build_exit_suite(cmd_runner=self.commander_name,
                                  names=delay_unreg_names,
                                  validate_config=False)

        ################################################################
        # handle delay_reg_names
        ################################################################
        if delay_reg_names:
            self.build_start_suite(start_names=delay_reg_names,
                                   validate_config=False)
            self.build_exit_suite(cmd_runner=self.commander_name,
                                  names=delay_reg_names,
                                  validate_config=False)

        ################################################################
        # finally, confirm the recv_msg is done
        ################################################################
        self.add_cmd(
            ConfirmResponse(
                cmd_runners=self.commander_name,
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

        Args:
            from_names: names of threads that send
            to_name: names of threads that receive

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
    # build_def_del_suite
    ####################################################################
    def build_def_del_suite(
            self,
            def_del_scenario: DefDelScenario) -> None:
        """Return a list of ConfigCmd items for a deferred delete.

        Args:
            def_del_scenario: specifies type of test to do

        """
        num_receivers = 2
        num_senders = 1

        num_waiters = 2
        num_resumers = 1

        num_syncers = 2

        num_dels = 1
        num_adds = 1

        num_deleters = 1
        num_adders = 1

        num_lockers = 3
        
        num_active_needed = (num_receivers 
                             + num_senders 
                             + num_waiters 
                             + num_resumers
                             + num_syncers
                             + num_dels
                             + num_deleters
                             + num_adders
                             + num_lockers
                             + 1)  # plus 1 for the commander
        self.build_config(
            cmd_runner=self.commander_name,
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
        # choose sender_names
        ################################################################
        sender_names = self.choose_names(
            name_collection=active_names,
            num_names_needed=num_senders,
            update_collection=True,
            var_name_for_log='sender_names')

        ################################################################
        # choose waiter_names
        ################################################################
        waiter_names = self.choose_names(
            name_collection=active_names,
            num_names_needed=num_waiters,
            update_collection=True,
            var_name_for_log='waiter_names')

        ################################################################
        # choose resumer_names
        ################################################################
        resumer_names = self.choose_names(
            name_collection=active_names,
            num_names_needed=num_resumers,
            update_collection=True,
            var_name_for_log='resumer_names')

        ################################################################
        # choose resumer_names
        ################################################################
        syncer_names = self.choose_names(
            name_collection=active_names,
            num_names_needed=num_syncers,
            update_collection=True,
            var_name_for_log='syncer_names')

        ################################################################
        # choose del_names
        ################################################################
        del_names = self.choose_names(
            name_collection=active_names,
            num_names_needed=num_dels,
            update_collection=True,
            var_name_for_log='del_names')

        ################################################################
        # choose add_names
        ################################################################
        unregistered_names = self.unregistered_names.copy()
        add_names = self.choose_names(
            name_collection=unregistered_names,
            num_names_needed=num_adds,
            update_collection=True,
            var_name_for_log='add_names')

        ################################################################
        # choose deleter_names
        ################################################################
        deleter_names = self.choose_names(
            name_collection=active_names,
            num_names_needed=num_deleters,
            update_collection=True,
            var_name_for_log='deleter_names')

        ################################################################
        # choose adder_names
        ################################################################
        adder_names = self.choose_names(
            name_collection=active_names,
            num_names_needed=num_adders,
            update_collection=True,
            var_name_for_log='adder_names')

        ################################################################
        # choose locker_names
        ################################################################
        locker_names = self.choose_names(
            name_collection=active_names,
            num_names_needed=num_lockers,
            update_collection=True,
            var_name_for_log='locker_names')

        ################################################################
        # setup msgs to send
        ################################################################
        sender_msgs: dict[str, str] = {}
        for name in sender_names:
            sender_msgs[name] = (f'recv test: {name} sending msg '
                                 f'at {self.get_ptime()}')

        receivers: list[str] = []
        if (def_del_scenario == DefDelScenario.NormalRecv
                or def_del_scenario == DefDelScenario.ResurrectionRecv
                or def_del_scenario == DefDelScenario.Recv0Recv1
                or def_del_scenario == DefDelScenario.Recv1Recv0
                or def_del_scenario == DefDelScenario.RecvWait
                or def_del_scenario == DefDelScenario.WaitRecv
                or def_del_scenario == DefDelScenario.RecvDel
                or def_del_scenario == DefDelScenario.RecvAdd):
            receivers.append(receiver_names[0])
        if (def_del_scenario == DefDelScenario.Recv0Recv1
                or def_del_scenario == DefDelScenario.Recv1Recv0):
            receivers.append(receiver_names[1])

        waiters: list[str] = []
        if (def_del_scenario == DefDelScenario.NormalWait
                or def_del_scenario == DefDelScenario.ResurrectionWait
                or def_del_scenario == DefDelScenario.Wait0Wait1
                or def_del_scenario == DefDelScenario.Wait1Wait0
                or def_del_scenario == DefDelScenario.RecvWait
                or def_del_scenario == DefDelScenario.WaitRecv
                or def_del_scenario == DefDelScenario.WaitDel
                or def_del_scenario == DefDelScenario.WaitAdd):
            waiters.append(waiter_names[0])
        if (def_del_scenario == DefDelScenario.Wait0Wait1
                or def_del_scenario == DefDelScenario.Wait1Wait0):
            waiters.append(waiter_names[1])

        exiters: list[str] = []
        if (def_del_scenario == DefDelScenario.RecvDel
                or def_del_scenario == DefDelScenario.WaitDel):
            exiters.append(del_names[0])

        adders: list[str] = []
        if (def_del_scenario == DefDelScenario.RecvAdd
                or def_del_scenario == DefDelScenario.WaitAdd):
            adders.append(add_names[0])

        exit_names: list[str] = []
        if receivers:
            ############################################################
            # send a msg that will sit on the recv_msg msg_q (1 or 2)
            ############################################################
            exit_names.append(sender_names[0])
            send_msg_serial_num_0 = self.add_cmd(
                SendMsg(cmd_runners=sender_names[0],
                        receivers=receivers,
                        msgs_to_send=sender_msgs))
            self.add_cmd(
                ConfirmResponse(
                    cmd_runners=[self.commander_name],
                    confirm_cmd='SendMsg',
                    confirm_serial_num=send_msg_serial_num_0,
                    confirmers=sender_names[0]))
        if waiters:
            ############################################################
            # resume that will set wait bit
            ############################################################
            exit_names.append(resumer_names[0])
            resume_serial_num_0 = self.add_cmd(
                Resume(cmd_runners=resumer_names[0],
                       targets=waiters,
                       stopped_names=[]))
            self.add_cmd(
                ConfirmResponse(
                    cmd_runners=[self.commander_name],
                    confirm_cmd='Resume',
                    confirm_serial_num=resume_serial_num_0,
                    confirmers=resumer_names[0]))

        if (def_del_scenario != DefDelScenario.NormalRecv
                and def_del_scenario != DefDelScenario.NormalWait):
            ############################################################
            # exit the sender to create a half paired case
            ############################################################
            self.build_exit_suite(
                cmd_runner=self.commander_name,
                names=exit_names,
                validate_config=False)
            self.build_join_suite(
                cmd_runners=self.commander_name,
                join_target_names=exit_names,
                validate_config=False)

            if (def_del_scenario == DefDelScenario.ResurrectionRecv
                    or def_del_scenario == DefDelScenario.ResurrectionWait):
                ########################################################
                # resurrect the sender
                ########################################################
                f1_create_items: list[F1CreateItem] = []
                for idx, name in enumerate(exit_names):
                    if idx % 2:
                        app_config = AppConfig.ScriptStyle
                    else:
                        app_config = AppConfig.RemoteThreadApp

                    f1_create_items.append(F1CreateItem(name=name,
                                                        auto_start=True,
                                                        target_rtn=outer_f1,
                                                        app_config=app_config))
                self.build_create_suite(
                    f1_create_items=f1_create_items,
                    validate_config=False)

        lock_positions: list[str] = []
        ################################################################
        # get lock to keep the first recv_msg/wait getting too far ahead
        ################################################################
        obtain_lock_serial_num_0 = self.add_cmd(
            LockObtain(cmd_runners=locker_names[0]))
        lock_positions.append(locker_names[0])

        # we can confirm only this first lock obtain
        self.add_cmd(
            ConfirmResponse(
                cmd_runners=[self.commander_name],
                confirm_cmd='LockObtain',
                confirm_serial_num=obtain_lock_serial_num_0,
                confirmers=locker_names[0]))

        ################################################################
        # do the first recv or wait
        ################################################################
        if (def_del_scenario == DefDelScenario.NormalRecv
                or def_del_scenario == DefDelScenario.ResurrectionRecv
                or def_del_scenario == DefDelScenario.Recv0Recv1
                or def_del_scenario == DefDelScenario.Recv1Recv0
                or def_del_scenario == DefDelScenario.RecvWait
                # or def_del_scenario == DefDelScenario.WaitRecv
                or def_del_scenario == DefDelScenario.RecvDel
                or def_del_scenario == DefDelScenario.RecvAdd):
            cmd_0_name = 'RecvMsg'
            cmd_0_confirmer = receivers[0]
            cmd_0_serial_num = self.add_cmd(
                RecvMsg(cmd_runners=receivers[0],
                        senders=sender_names[0],
                        exp_msgs=sender_msgs,
                        # del_deferred=sender_names[0],
                        log_msg=f'def_del_recv_test_0'))
            first_cmd_lock_pos = receivers[0]
            lock_positions.append(receivers[0])

        elif (def_del_scenario == DefDelScenario.NormalWait
                or def_del_scenario == DefDelScenario.ResurrectionWait
                or def_del_scenario == DefDelScenario.Wait0Wait1
                or def_del_scenario == DefDelScenario.Wait1Wait0
                # or def_del_scenario == DefDelScenario.RecvWait
                or def_del_scenario == DefDelScenario.WaitRecv
                or def_del_scenario == DefDelScenario.WaitDel
                or def_del_scenario == DefDelScenario.WaitAdd):

            cmd_0_name = 'Wait'
            cmd_0_confirmer = waiters[0]
            cmd_0_serial_num = self.add_cmd(
                Wait(cmd_runners=waiters[0],
                     resumers=resumer_names[0],
                     stopped_remotes=set(),
                     wait_for=st.WaitFor.All,
                     error_stopped_target=False,
                     log_msg=f'def_del_wait_test_0'))

            first_cmd_lock_pos = waiters[0]
            lock_positions.append(waiters[0])

        self.add_cmd(
            LockVerify(cmd_runners=self.commander_name,
                       exp_positions=lock_positions.copy()))
        ################################################################
        # get lock to keep second recv_msg/wait/del/add behind first
        ################################################################
        obtain_lock_serial_num_1 = self.add_cmd(
            LockObtain(cmd_runners=locker_names[1]))
        lock_positions.append(locker_names[1])

        self.add_cmd(
            LockVerify(cmd_runners=self.commander_name,
                       exp_positions=lock_positions.copy()))

        ################################################################
        # do second recv_msg/wait/del/add behind first
        ################################################################
        second_cmd_lock_pos: str = ''
        cmd_1_name = ''
        cmd_1_confirmer = ''
        cmd_1_serial_num = 0
        if (def_del_scenario == DefDelScenario.Recv0Recv1
                or def_del_scenario == DefDelScenario.Recv1Recv0
                or def_del_scenario == DefDelScenario.WaitRecv):
            if def_del_scenario == DefDelScenario.WaitRecv:
                recv_name = receivers[0]
            else:
                recv_name = receivers[1]
            cmd_1_name = 'RecvMsg'
            cmd_1_confirmer = recv_name
            cmd_1_serial_num = self.add_cmd(
                RecvMsg(cmd_runners=recv_name,
                        senders=sender_names[0],
                        exp_msgs=sender_msgs,
                        # del_deferred=sender_names[0],
                        log_msg=f'def_del_recv_test_1'))
            second_cmd_lock_pos = recv_name
            lock_positions.append(recv_name)
        elif (def_del_scenario == DefDelScenario.Wait0Wait1
                or def_del_scenario == DefDelScenario.Wait1Wait0
                or def_del_scenario == DefDelScenario.RecvWait):

            if def_del_scenario == DefDelScenario.RecvWait:
                wait_name = waiters[0]
            else:
                wait_name = waiters[1]

            cmd_1_name = 'Wait'
            cmd_1_confirmer = wait_name
            cmd_1_serial_num = self.add_cmd(
                Wait(cmd_runners=wait_name,
                     resumers=resumer_names[0],
                     stopped_remotes=set(),
                     wait_for=st.WaitFor.All,
                     error_stopped_target=False,
                     log_msg=f'def_del_wait_test_1'))

            second_cmd_lock_pos = wait_name
            lock_positions.append(wait_name)
        elif (def_del_scenario == DefDelScenario.RecvDel
              or def_del_scenario == DefDelScenario.WaitDel):
            self.build_exit_suite(
                cmd_runner=deleter_names[0],
                names=[del_names[0]],
                validate_config=False)
            self.build_join_suite(
                cmd_runners=deleter_names[0],
                join_target_names=[del_names[0]],
                validate_config=False)
            second_cmd_lock_pos = deleter_names[0]
            lock_positions.append(deleter_names[0])
        elif (def_del_scenario == DefDelScenario.RecvAdd
              or def_del_scenario == DefDelScenario.WaitAdd):
            f1_create_items: list[F1CreateItem] = [
                F1CreateItem(
                    name=add_names[0],
                    auto_start=True,
                    target_rtn=outer_f1,
                    app_config=AppConfig.ScriptStyle)]
            self.build_create_suite(
                cmd_runner=adder_names[0],
                f1_create_items=f1_create_items,
                validate_config=False)
            second_cmd_lock_pos = adder_names[0]
            lock_positions.append(adder_names[0])

        self.add_cmd(
            LockVerify(cmd_runners=self.commander_name,
                       exp_positions=lock_positions.copy()))
        ################################################################
        # get lock to freeze first and second recv_msg/wait just
        # before the refresh so we can swap lock positions
        ################################################################
        obtain_lock_serial_num_2 = self.add_cmd(
            LockObtain(cmd_runners=locker_names[2]))
        lock_positions.append(locker_names[2])
        self.add_cmd(
            LockVerify(cmd_runners=self.commander_name,
                       exp_positions=lock_positions.copy()))

        ################################################################
        # release first lock to allow first recv_msg/wait to go
        ################################################################
        release_lock_serial_num_0 = self.add_cmd(
            LockRelease(cmd_runners=locker_names[0]))
        lock_positions.remove(locker_names[0])

        # releasing the first lock will allow the first recv/wait to go
        lock_positions.remove(first_cmd_lock_pos)

        # the first recv/wait will now get behind the last lock
        # waiter, but only for those cases that involve the deferred
        # delete
        if (def_del_scenario != DefDelScenario.NormalRecv
                and def_del_scenario != DefDelScenario.NormalWait
                and def_del_scenario != DefDelScenario.ResurrectionRecv
                and def_del_scenario != DefDelScenario.ResurrectionWait):
            lock_positions.append(first_cmd_lock_pos)

        self.add_cmd(
            ConfirmResponse(
                cmd_runners=[self.commander_name],
                confirm_cmd='LockRelease',
                confirm_serial_num=release_lock_serial_num_0,
                confirmers=locker_names[0]))

        self.add_cmd(
            LockVerify(cmd_runners=self.commander_name,
                       exp_positions=lock_positions.copy()))
        ################################################################
        # release second lock to allow second recv_msg/wait to go
        ################################################################
        release_lock_serial_num_1 = self.add_cmd(
            LockRelease(cmd_runners=locker_names[1]))
        lock_positions.remove(locker_names[1])

        # releasing the second lock will allow the second recv/wait to
        # go and then get the lock exclusive behind the last lock waiter
        if second_cmd_lock_pos:
            lock_positions.remove(second_cmd_lock_pos)
            # recv, wait, or add will get behind the 3rd lock, not del
            if (def_del_scenario != DefDelScenario.RecvDel
                    and def_del_scenario != DefDelScenario.WaitDel):
                lock_positions.append(second_cmd_lock_pos)

        self.add_cmd(
            ConfirmResponse(
                cmd_runners=[self.commander_name],
                confirm_cmd='LockRelease',
                confirm_serial_num=release_lock_serial_num_1,
                confirmers=locker_names[1]))

        self.add_cmd(
            LockVerify(cmd_runners=self.commander_name,
                       exp_positions=lock_positions.copy()))
        ################################################################
        # At this point we will have the first cmd behind the third
        # lock. If there is a second cmd, it will be behind the first
        # cmd. We now need to swap the lock positions for some
        # scenarios.
        ################################################################
        if (def_del_scenario == DefDelScenario.Recv1Recv0
                or def_del_scenario == DefDelScenario.Wait1Wait0):
            lock_pos_1 = lock_positions[1]
            lock_positions[1] = lock_positions[2]
            lock_positions[2] = lock_pos_1

            assert lock_positions[0] == locker_names[2]
            assert lock_positions[1] == second_cmd_lock_pos
            assert lock_positions[2] == first_cmd_lock_pos

            self.add_cmd(
                LockSwap(cmd_runners=self.commander_name,
                         new_positions=lock_positions))
            self.add_cmd(
                LockVerify(cmd_runners=self.commander_name,
                           exp_positions=lock_positions.copy()))

        ################################################################
        # release third lock to allow both recv_msg/wait to refresh
        ################################################################
        release_lock_serial_num_2 = self.add_cmd(
            LockRelease(cmd_runners=locker_names[2]))
        self.add_cmd(
            ConfirmResponse(
                cmd_runners=[self.commander_name],
                confirm_cmd='LockRelease',
                confirm_serial_num=release_lock_serial_num_2,
                confirmers=locker_names[2]))

        self.add_cmd(
            ConfirmResponse(
                cmd_runners=[self.commander_name],
                confirm_cmd=cmd_0_name,
                confirm_serial_num=cmd_0_serial_num,
                confirmers=cmd_0_confirmer))

        if cmd_1_name:
            self.add_cmd(
                ConfirmResponse(
                    cmd_runners=[self.commander_name],
                    confirm_cmd=cmd_1_name,
                    confirm_serial_num=cmd_1_serial_num,
                    confirmers=cmd_1_confirmer))

        self.add_cmd(
            LockVerify(cmd_runners=self.commander_name,
                       exp_positions=[]))

        ################################################################
        # check results
        ################################################################
        self.add_cmd(
            VerifyDefDel(
                cmd_runners=self.commander_name,
                def_del_scenario=def_del_scenario,
                receiver_names=receiver_names,
                sender_names=sender_names,
                waiter_names=waiter_names,
                resumer_names=resumer_names,
                del_names=del_names,
                add_names=add_names,
                deleter_names=deleter_names,
                adder_names=adder_names))

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

        timeout_time = ((num_active_no_delay_senders * 0.01)
                        + (num_active_delay_senders * 0.01)
                        + (num_send_exit_senders * 0.01)
                        + (num_nosend_exit_senders * 0.5)
                        + (num_unreg_senders * 0.2)
                        + (num_reg_senders * 0.1))

        if timeout_type == TimeoutType.TimeoutNone:
            pause_time = 0.5
        elif timeout_type == TimeoutType.TimeoutFalse:
            pause_time = 0.5
            timeout_time += (pause_time * 2)  # prevent timeout
        else:  # timeout True
            pause_time = timeout_time + 1  # force timeout

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
            self.add_cmd(
                SendMsg(cmd_runners=active_no_delay_sender_names,
                        receivers=receiver_names,
                        msgs_to_send=sender_msgs))

        self.add_cmd(
            Pause(cmd_runners=self.commander_name,
                  pause_seconds=pause_time))
        if timeout_type == TimeoutType.TimeoutTrue:
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
                cmd_runner=self.commander_name,
                names=send_exit_sender_names,
                validate_config=False)
            self.build_join_suite(
                cmd_runners=self.commander_name,
                join_target_names=send_exit_sender_names,
                validate_config=False)

        ################################################################
        # exit the nosend_exit_senders, then resurrect and do send_msg
        ################################################################
        if nosend_exit_sender_names:
            self.build_exit_suite(
                cmd_runner=self.commander_name,
                names=nosend_exit_sender_names,
                validate_config=False)
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
    # build_wait_timeout_suite
    ####################################################################
    def build_wait_scenario_suite(
            self,
            num_waiters: int,
            num_actors: int,
            actor_list: list[Actors]) -> None:
        """Adds cmds to the cmd queue.

        Args:
            num_waiters: number of threads that will do the wait
            num_actors: number of threads that will do the resume
            actor_list: contains the actors

        """
        actions: dict[Actors, Callable[..., None]] = {
            Actors.ActiveBeforeActor:
                self.build_resume_before_wait_timeout_suite,
            Actors.ActiveAfterActor:
                self.build_resume_after_wait_timeout_suite,
            Actors.ActionExitActor:
                self.build_resume_exit_wait_timeout_suite,
            Actors.ExitActionActor:
                self.build_exit_resume_wait_timeout_suite,
            Actors.UnregActor:
                self.build_unreg_resume_wait_timeout_suite,
            Actors.RegActor:
                self.build_reg_resume_wait_timeout_suite,
        }
        # Make sure we have enough threads. Note that we subtract 1 from
        # the count of unregistered names to ensure we have one thread
        # for the commander

        assert num_waiters > 0
        assert num_actors > 0
        assert (num_waiters + num_actors) <= len(self.unregistered_names) - 1

        # number needed for waiters, actors, and commander
        num_active_threads_needed = num_waiters + num_actors + 1

        self.build_config(
            cmd_runner=self.commander_name,
            num_active=num_active_threads_needed)

        self.log_name_groups()

        # active_names = self.active_names.copy()
        # remove commander for now, but if we add it later we need to
        # be careful not to exit the commander
        active_names = self.active_names - {self.commander_name}

        waiter_names = self.choose_names(
            name_collection=active_names,
            num_names_needed=num_waiters,
            update_collection=True,
            var_name_for_log='waiter_names')

        actor_names = self.choose_names(
            name_collection=active_names,
            num_names_needed=num_actors,
            update_collection=True,
            var_name_for_log='actor_names')

        for actor in actor_list:
            actions[actor](waiter_names=waiter_names,
                           actor_names=actor_names)

    ####################################################################
    # powerset
    ####################################################################
    @staticmethod
    def powerset(names: list[str]):
        """Returns a generator powerset of the input list of names.

        Args:
            names: names to use to make a powerset

        """
        # powerset([1,2,3]) --> () (1,) (2,) (3,) (1,2) (1,3) (2,3) (1,2,3)
        return chain.from_iterable(
            combinations(names, r) for r in range(len(names) + 1))

    ####################################################################
    # build_wait_active_suite
    ####################################################################
    def build_resume_before_wait_timeout_suite(
            self,
            waiter_names: list[str],
            actor_names: list[str]) -> None:
        """Adds cmds to the cmd queue.

        Args:
            waiter_names: names of threads that will do the wait
            actor_names: names of threads that will do the resume

        """
        error_stopped_target = True
        ################################################################
        # Loop to do combinations of resume names, the waiter names that
        # will be resumed - the remaining waiter names will timeout
        ################################################################
        for target_names in self.powerset(waiter_names.copy()):
            timeout_names = waiter_names
            if target_names:
                target_names = list(target_names)
                ########################################################
                # resume the waiters that are expected to succeed
                ########################################################
                resume_cmd_serial_num = self.add_cmd(
                    Resume(cmd_runners=actor_names,
                           targets=target_names,
                           stopped_names=[]))
                self.add_cmd(
                    ConfirmResponse(
                        cmd_runners=[self.commander_name],
                        confirm_cmd='Resume',
                        confirm_serial_num=resume_cmd_serial_num,
                        confirmers=actor_names))

                timeout_time = 1.5
                wait_serial_num = self.add_cmd(
                    WaitTimeoutFalse(
                        cmd_runners=target_names,
                        resumers=actor_names,
                        stopped_remotes=set(),
                        timeout=timeout_time,
                        wait_for=st.WaitFor.All,
                        error_stopped_target=error_stopped_target))

                self.add_cmd(
                    ConfirmResponse(
                        cmd_runners=[self.commander_name],
                        confirm_cmd='WaitTimeoutFalse',
                        confirm_serial_num=wait_serial_num,
                        confirmers=target_names))

                timeout_names = list(set(waiter_names) - set(target_names))

            if timeout_names:
                ########################################################
                # the timeout_names are expected to timeout since they
                # were not resumed
                ########################################################
                timeout_time = 0.5
                wait_serial_num = self.add_cmd(
                    WaitTimeoutTrue(
                        cmd_runners=timeout_names,
                        resumers=actor_names,
                        stopped_remotes=set(),
                        timeout=timeout_time,
                        timeout_remotes=set(actor_names),
                        wait_for=st.WaitFor.All,
                        error_stopped_target=error_stopped_target))

                self.add_cmd(
                    ConfirmResponse(
                        cmd_runners=[self.commander_name],
                        confirm_cmd='WaitTimeoutTrue',
                        confirm_serial_num=wait_serial_num,
                        confirmers=timeout_names))

    ####################################################################
    # build_wait_active_suite
    ####################################################################
    def build_resume_after_wait_timeout_suite(
            self,
            waiter_names: list[str],
            actor_names: list[str]) -> None:
        """Adds cmds to the cmd queue.

        Args:
            waiter_names: names of threads that will do the wait
            actor_names: names of threads that will do the resume

        """
        error_stopped_target = True
        ################################################################
        # Loop to do combinations of resume names, the waiter names that
        # will be resumed - the remaining waiter names will timeout
        ################################################################
        for target_names in self.powerset(waiter_names.copy()):
            timeout_names = waiter_names
            if target_names:
                ########################################################
                # resume the waiters that are expected to succeed
                ########################################################
                timeout_time = 1.5
                wait_serial_num = self.add_cmd(
                    WaitTimeoutFalse(
                        cmd_runners=list(target_names),
                        resumers=actor_names,
                        stopped_remotes=set(),
                        timeout=timeout_time,
                        wait_for=st.WaitFor.All,
                        error_stopped_target=error_stopped_target))

                resume_cmd_serial_num = self.add_cmd(
                    Resume(cmd_runners=actor_names,
                           targets=list(target_names),
                           stopped_names=[]))
                self.add_cmd(
                    ConfirmResponse(
                        cmd_runners=[self.commander_name],
                        confirm_cmd='Resume',
                        confirm_serial_num=resume_cmd_serial_num,
                        confirmers=actor_names))

                self.add_cmd(
                    ConfirmResponse(
                        cmd_runners=[self.commander_name],
                        confirm_cmd='WaitTimeoutFalse',
                        confirm_serial_num=wait_serial_num,
                        confirmers=list(target_names)))

                timeout_names = list(set(waiter_names) - set(target_names))

            if timeout_names:
                ########################################################
                # the timeout_names are expected to timeout since they
                # were not resumed
                ########################################################
                timeout_time = 0.5
                wait_serial_num = self.add_cmd(
                    WaitTimeoutTrue(
                        cmd_runners=timeout_names,
                        resumers=actor_names,
                        stopped_remotes=set(),
                        timeout=timeout_time,
                        timeout_remotes=set(actor_names),
                        wait_for=st.WaitFor.All,
                        error_stopped_target=error_stopped_target))
                self.add_cmd(
                    ConfirmResponse(
                        cmd_runners=[self.commander_name],
                        confirm_cmd='WaitTimeoutTrue',
                        confirm_serial_num=wait_serial_num,
                        confirmers=timeout_names))

    ####################################################################
    # build_wait_active_suite
    ####################################################################
    def build_resume_exit_wait_timeout_suite(
            self,
            waiter_names: list[str],
            actor_names: list[str]) -> None:
        """Adds cmds to the cmd queue.

        Args:
            waiter_names: names of threads that will do the wait
            actor_names: names of threads that will do the resume

        """
        error_stopped_target = True
        ################################################################
        # Loop to do combinations of resume names, the waiter names that
        # will be resumed - the remaining waiter names will timeout
        ################################################################
        for target_names in self.powerset(waiter_names.copy()):
            timeout_names = waiter_names
            if target_names:
                target_names = list(target_names)
                ########################################################
                # resume the waiters that are expected to succeed
                ########################################################
                resume_cmd_serial_num = self.add_cmd(
                    Resume(cmd_runners=actor_names,
                           targets=target_names,
                           stopped_names=[]))

                self.add_cmd(
                    ConfirmResponse(
                        cmd_runners=[self.commander_name],
                        confirm_cmd='Resume',
                        confirm_serial_num=resume_cmd_serial_num,
                        confirmers=actor_names))

                self.build_exit_suite(cmd_runner=self.commander_name,
                                      names=actor_names)
                self.build_join_suite(
                    cmd_runners=self.commander_name,
                    join_target_names=actor_names)

                for resumer_name in actor_names:
                    self.add_cmd(VerifyPairedHalf(
                        cmd_runners=self.commander_name,
                        removed_names=resumer_name,
                        exp_half_paired_names=target_names))

                timeout_time = 1.5
                wait_serial_num = self.add_cmd(
                    WaitTimeoutFalse(
                        cmd_runners=target_names,
                        resumers=actor_names,
                        stopped_remotes=set(),
                        timeout=timeout_time,
                        wait_for=st.WaitFor.All,
                        error_stopped_target=error_stopped_target))
                self.add_cmd(
                    ConfirmResponse(
                        cmd_runners=[self.commander_name],
                        confirm_cmd='WaitTimeoutFalse',
                        confirm_serial_num=wait_serial_num,
                        confirmers=target_names))

                f1_create_items: list[F1CreateItem] = []
                for idx, name in enumerate(actor_names):
                    if idx % 2:
                        app_config = AppConfig.ScriptStyle
                    else:
                        app_config = AppConfig.RemoteThreadApp

                    f1_create_items.append(F1CreateItem(name=name,
                                                        auto_start=True,
                                                        target_rtn=outer_f1,
                                                        app_config=app_config))
                self.build_create_suite(
                    f1_create_items=f1_create_items,
                    validate_config=False)

                timeout_names = list(set(waiter_names) - set(target_names))

            if timeout_names:
                ########################################################
                # the timeout_names are expected to timeout since they
                # were not resumed
                ########################################################
                timeout_time = 0.5
                wait_serial_num = self.add_cmd(
                    WaitTimeoutTrue(
                        cmd_runners=timeout_names,
                        resumers=actor_names,
                        stopped_remotes=set(),
                        timeout=timeout_time,
                        timeout_remotes=set(actor_names),
                        wait_for=st.WaitFor.All,
                        error_stopped_target=error_stopped_target))
                self.add_cmd(
                    ConfirmResponse(
                        cmd_runners=[self.commander_name],
                        confirm_cmd='WaitTimeoutTrue',
                        confirm_serial_num=wait_serial_num,
                        confirmers=timeout_names))

    ####################################################################
    # build_wait_active_suite
    ####################################################################
    def build_exit_resume_wait_timeout_suite(
            self,
            waiter_names: list[str],
            actor_names: list[str]) -> None:
        """Adds cmds to the cmd queue.

        Args:
            waiter_names: names of threads that will do the wait
            actor_names: names of threads that will do the resume

        """
        ################################################################
        # Loop to do combinations of resume names, the waiter names that
        # will be resumed - the remaining waiter names will timeout
        ################################################################
        for target_names in self.powerset(waiter_names.copy()):
            timeout_names = waiter_names

            if len(target_names) % 2:
                error_stopped_target = True
                stopped_names = set(actor_names.copy())
            else:
                error_stopped_target = False
                stopped_names = set()

            if target_names:
                target_names = list(target_names)

                timeout_time = 3.0
                wait_serial_num = self.add_cmd(
                    WaitTimeoutFalse(
                        cmd_runners=target_names,
                        resumers=actor_names,
                        stopped_remotes=stopped_names,
                        timeout=timeout_time,
                        wait_for=st.WaitFor.All,
                        error_stopped_target=error_stopped_target))

                self.build_exit_suite(cmd_runner=self.commander_name,
                                      names=actor_names)

                if error_stopped_target:
                    self.add_cmd(
                        ConfirmResponse(
                            cmd_runners=[self.commander_name],
                            confirm_cmd='WaitTimeoutFalse',
                            confirm_serial_num=wait_serial_num,
                            confirmers=target_names))

                self.build_join_suite(
                    cmd_runners=self.commander_name,
                    join_target_names=actor_names)

                f1_create_items: list[F1CreateItem] = []
                for idx, name in enumerate(actor_names):
                    if idx % 2:
                        app_config = AppConfig.ScriptStyle
                    else:
                        app_config = AppConfig.RemoteThreadApp

                    f1_create_items.append(F1CreateItem(name=name,
                                                        auto_start=True,
                                                        target_rtn=outer_f1,
                                                        app_config=app_config))
                self.build_create_suite(
                    f1_create_items=f1_create_items,
                    validate_config=False)

                if not error_stopped_target:
                    ########################################################
                    # resume the waiters that are expected to succeed
                    ########################################################
                    resume_cmd_serial_num = self.add_cmd(
                        Resume(cmd_runners=actor_names,
                               targets=target_names,
                               stopped_names=[]))

                    self.add_cmd(
                        ConfirmResponse(
                            cmd_runners=[self.commander_name],
                            confirm_cmd='Resume',
                            confirm_serial_num=resume_cmd_serial_num,
                            confirmers=actor_names))

                    self.add_cmd(
                        ConfirmResponse(
                            cmd_runners=[self.commander_name],
                            confirm_cmd='WaitTimeoutFalse',
                            confirm_serial_num=wait_serial_num,
                            confirmers=target_names))

                timeout_names = list(set(waiter_names) - set(target_names))

            if timeout_names:
                ########################################################
                # the timeout_names are expected to timeout since they
                # were not resumed
                ########################################################
                error_stopped_target = True
                exit_was_done = False
                if len(timeout_names) % 2:
                    stopped_names = set(actor_names.copy())
                    self.build_exit_suite(cmd_runner=self.commander_name,
                                          names=actor_names)
                    exit_was_done = True
                else:
                    stopped_names = set()

                timeout_time = 0.5
                wait_serial_num = self.add_cmd(
                    WaitTimeoutTrue(
                        cmd_runners=timeout_names,
                        resumers=actor_names,
                        stopped_remotes=stopped_names,
                        timeout=timeout_time,
                        timeout_remotes=set(actor_names),
                        wait_for=st.WaitFor.All,
                        error_stopped_target=error_stopped_target))
                self.add_cmd(
                    ConfirmResponse(
                        cmd_runners=[self.commander_name],
                        confirm_cmd='WaitTimeoutTrue',
                        confirm_serial_num=wait_serial_num,
                        confirmers=timeout_names))
                if exit_was_done:
                    self.build_join_suite(
                        cmd_runners=self.commander_name,
                        join_target_names=actor_names)

                    f1_create_items: list[F1CreateItem] = []
                    for idx, name in enumerate(actor_names):
                        if idx % 2:
                            app_config = AppConfig.ScriptStyle
                        else:
                            app_config = AppConfig.RemoteThreadApp

                        f1_create_items.append(
                            F1CreateItem(name=name,
                                         auto_start=True,
                                         target_rtn=outer_f1,
                                         app_config=app_config))
                    self.build_create_suite(
                        f1_create_items=f1_create_items,
                        validate_config=False)

    ####################################################################
    # build_wait_active_suite
    ####################################################################
    def build_unreg_resume_wait_timeout_suite(
            self,
            waiter_names: list[str],
            actor_names: list[str]) -> None:
        """Adds cmds to the cmd queue.

        Args:
            waiter_names: names of threads that will do the wait
            actor_names: names of threads that will do the resume

        """
        ################################################################
        # Loop to do combinations of resume names, the waiter names that
        # will be resumed - the remaining waiter names will timeout
        ################################################################
        error_stopped_target = True
        for target_names in self.powerset(waiter_names.copy()):
            if target_names:
                target_names = list(target_names)

                ########################################################
                # get actors into unreg state
                ########################################################
                self.build_exit_suite(cmd_runner=self.commander_name,
                                      names=actor_names)
                self.build_join_suite(
                    cmd_runners=self.commander_name,
                    join_target_names=actor_names)

                ########################################################
                # do the wait
                ########################################################
                wait_serial_num = self.add_cmd(
                    Wait(
                        cmd_runners=target_names,
                        resumers=actor_names,
                        stopped_remotes=set(),
                        wait_for=st.WaitFor.All,
                        error_stopped_target=error_stopped_target))

                ########################################################
                # get actors into active state
                ########################################################
                f1_create_items: list[F1CreateItem] = []
                for idx, name in enumerate(actor_names):
                    if idx % 2:
                        app_config = AppConfig.ScriptStyle
                    else:
                        app_config = AppConfig.RemoteThreadApp

                    f1_create_items.append(F1CreateItem(name=name,
                                                        auto_start=True,
                                                        target_rtn=outer_f1,
                                                        app_config=app_config))
                self.build_create_suite(
                    f1_create_items=f1_create_items,
                    validate_config=False)

                ########################################################
                # resume the waiters
                ########################################################
                resume_cmd_serial_num = self.add_cmd(
                    Resume(cmd_runners=actor_names,
                           targets=target_names,
                           stopped_names=[]))

                self.add_cmd(
                    ConfirmResponse(
                        cmd_runners=[self.commander_name],
                        confirm_cmd='Resume',
                        confirm_serial_num=resume_cmd_serial_num,
                        confirmers=actor_names))

                self.add_cmd(
                    ConfirmResponse(
                        cmd_runners=[self.commander_name],
                        confirm_cmd='Wait',
                        confirm_serial_num=wait_serial_num,
                        confirmers=target_names))

    ####################################################################
    # build_wait_active_suite
    ####################################################################
    def build_reg_resume_wait_timeout_suite(
            self,
            waiter_names: list[str],
            actor_names: list[str]) -> None:
        """Adds cmds to the cmd queue.

        Args:
            waiter_names: names of threads that will do the wait
            actor_names: names of threads that will do the resume

        """
        ################################################################
        # Loop to do combinations of resume names, the waiter names that
        # will be resumed - the remaining waiter names will timeout
        ################################################################
        error_stopped_target = True
        for target_names in self.powerset(waiter_names.copy()):
            if target_names:
                target_names = list(target_names)

                ########################################################
                # get actors into reg state
                ########################################################
                self.build_exit_suite(cmd_runner=self.commander_name,
                                      names=actor_names)
                self.build_join_suite(
                    cmd_runners=self.commander_name,
                    join_target_names=actor_names)

                f1_create_items: list[F1CreateItem] = []
                for idx, name in enumerate(actor_names):
                    if idx % 2:
                        app_config = AppConfig.ScriptStyle
                    else:
                        app_config = AppConfig.RemoteThreadApp

                    f1_create_items.append(F1CreateItem(name=name,
                                                        auto_start=False,
                                                        target_rtn=outer_f1,
                                                        app_config=app_config))
                self.build_create_suite(
                    f1_create_items=f1_create_items,
                    validate_config=False)

                ########################################################
                # do the wait
                ########################################################
                wait_serial_num = self.add_cmd(
                    Wait(
                        cmd_runners=target_names,
                        resumers=actor_names,
                        stopped_remotes=set(),
                        wait_for=st.WaitFor.All,
                        error_stopped_target=error_stopped_target))

                ########################################################
                # get actors into active state
                ########################################################
                self.build_start_suite(start_names=actor_names)

                ########################################################
                # resume the waiters
                ########################################################
                resume_cmd_serial_num = self.add_cmd(
                    Resume(cmd_runners=actor_names,
                           targets=target_names,
                           stopped_names=[]))

                self.add_cmd(
                    ConfirmResponse(
                        cmd_runners=[self.commander_name],
                        confirm_cmd='Resume',
                        confirm_serial_num=resume_cmd_serial_num,
                        confirmers=actor_names))

                self.add_cmd(
                    ConfirmResponse(
                        cmd_runners=[self.commander_name],
                        confirm_cmd='Wait',
                        confirm_serial_num=wait_serial_num,
                        confirmers=target_names))

    ####################################################################
    # build_msg_timeout_suite
    ####################################################################
    def build_resume_timeout_suite(self,
                                   timeout_type: TimeoutType,
                                   num_resumers: int,
                                   num_active: int,
                                   num_registered_before: int,
                                   num_registered_after: int,
                                   num_unreg_no_delay: int,
                                   num_unreg_delay: int,
                                   num_stopped_no_delay: int,
                                   num_stopped_delay: int
                                   ) -> None:
        """Add ConfigCmd items for smart_resume timeout scenarios.

        Args:
            timeout_type: specifies whether to issue the send_cmd with
                timeout, and is so whether the send_cmd should timeout
                or, by starting exited threads in time, not timeout
            num_resumers: number of threads doing resumes
            num_active: number threads active, thus no timeout
            num_registered_before: number threads registered, thus no
                 timeout, that wait before the resume is issued
            num_registered_after: number threads registered, thus no
                 timeout, that wait after the resume is issued
            num_unreg_no_delay: number threads unregistered before the
                resume is done, and are then created and started within
                the allowed timeout
            start, and started d active, thus no timeout
            num_unreg_delay: number threads unregistered before the
                resume is done, and are then created and started after
                the allowed timeout
            num_stopped_no_delay: number of threads stopped before the
                resume and are resurrected before a timeout
            num_stopped_delay: number of threads stopped before
                the resume and are resurrected after a timeout

        """
        # Make sure we have enough threads. Note that we subtract 1 from
        # the count of unregistered names to ensure we have one thread
        # for the commander
        assert (num_resumers
                + num_active
                + num_registered_before
                + num_registered_after
                + num_unreg_no_delay
                + num_unreg_delay
                + num_stopped_no_delay
                + num_stopped_delay) <= len(self.unregistered_names) - 1

        assert num_resumers > 0

        num_active_needed = (
                num_resumers
                + num_active
                + 1)  # plus 1 for commander

        timeout_time = ((num_active * 0.16)
                        + (num_registered_before * 0.16)
                        + (num_registered_after * 0.16)
                        + (num_unreg_no_delay * 0.32)
                        + (num_unreg_delay * 0.16)
                        + (num_stopped_no_delay * 0.32)
                        + (num_stopped_delay * 0.16))

        pause_time = 0.5
        if timeout_type == TimeoutType.TimeoutFalse:
            timeout_time *= 4  # prevent timeout
            pause_time = timeout_time * 0.10
        elif timeout_type == TimeoutType.TimeoutTrue:
            # timeout_time *= 0.5  # force timeout
            pause_time = timeout_time * 2

        self.build_config(
            cmd_runner=self.commander_name,
            num_registered=num_registered_before + num_registered_after,
            num_active=num_active_needed,
            num_stopped=num_stopped_no_delay + num_stopped_delay
        )

        self.log_name_groups()

        # remove commander for now, but if we add it later we need to
        # be careful not to exit the commander
        active_names = self.active_names - {self.commander_name}

        ################################################################
        # choose resumer_names
        ################################################################
        resumer_names = self.choose_names(
            name_collection=active_names,
            num_names_needed=num_resumers,
            update_collection=True,
            var_name_for_log='resumer_names')

        ################################################################
        # choose active_target_names
        ################################################################
        active_target_names = self.choose_names(
            name_collection=active_names,
            num_names_needed=num_active,
            update_collection=True,
            var_name_for_log='active_target_names')

        ################################################################
        # choose registered_names_before
        ################################################################
        registered_names_copy = self.registered_names.copy()
        registered_names_before = self.choose_names(
            name_collection=registered_names_copy,
            num_names_needed=num_registered_before,
            update_collection=True,
            var_name_for_log='registered_names_before')

        ################################################################
        # choose registered_names_after
        ################################################################
        registered_names_after = self.choose_names(
            name_collection=registered_names_copy,
            num_names_needed=num_registered_after,
            update_collection=True,
            var_name_for_log='registered_names_after')

        ################################################################
        # choose unreg_no_delay_names
        ################################################################
        unregistered_names = self.unregistered_names.copy()
        unreg_no_delay_names = self.choose_names(
            name_collection=unregistered_names,
            num_names_needed=num_unreg_no_delay,
            update_collection=True,
            var_name_for_log='unreg_no_delay_names')

        ################################################################
        # choose unreg_delay_names
        ################################################################
        unreg_delay_names = self.choose_names(
            name_collection=unregistered_names,
            num_names_needed=num_unreg_delay,
            update_collection=True,
            var_name_for_log='unreg_delay_names')

        ################################################################
        # choose stopped_no_delay_targets
        ################################################################
        stopped_names_copy = self.stopped_names.copy()
        stopped_no_delay_targets = self.choose_names(
            name_collection=stopped_names_copy,
            num_names_needed=num_stopped_no_delay,
            update_collection=True,
            var_name_for_log='stopped_no_delay_targets')

        ################################################################
        # choose stopped_delay_targets
        ################################################################
        stopped_delay_targets = self.choose_names(
            name_collection=stopped_names_copy,
            num_names_needed=num_stopped_delay,
            update_collection=True,
            var_name_for_log='stopped_delay_targets')

        all_targets: list[str] = (active_target_names
                                  + registered_names_before
                                  + registered_names_after
                                  + unreg_no_delay_names
                                  + unreg_delay_names
                                  + stopped_no_delay_targets
                                  + stopped_delay_targets)

        timeout_names = unreg_delay_names + stopped_delay_targets
        stopped_names = stopped_no_delay_targets + stopped_delay_targets

        if len(all_targets) % 2:
            error_stopped_target = True
        else:
            error_stopped_target = False

        ################################################################
        # issue smart_wait for active_target_names
        ################################################################
        if active_target_names:
            wait_active_target_serial_num = self.add_cmd(
                Wait(cmd_runners=active_target_names,
                     resumers=resumer_names,
                     stopped_remotes=set(),
                     wait_for=st.WaitFor.All,
                     error_stopped_target=True))

        ################################################################
        # start registered_names_before issue smart_wait
        ################################################################
        if registered_names_before:
            self.build_start_suite(start_names=registered_names_before)
            wait_reg_before_target_serial_num = self.add_cmd(
                Wait(cmd_runners=registered_names_before,
                     resumers=resumer_names,
                     stopped_remotes=set(),
                     wait_for=st.WaitFor.All,
                     error_stopped_target=True))

        ################################################################
        # issue smart_resume
        ################################################################
        if timeout_type == TimeoutType.TimeoutNone:
            resume_to_confirm = 'Resume'
            resume_serial_num = self.add_cmd(
                Resume(cmd_runners=resumer_names,
                       targets=all_targets,
                       stopped_names=stopped_names,
                       error_stopped_target=error_stopped_target))
        elif timeout_type == TimeoutType.TimeoutFalse:
            resume_to_confirm = 'ResumeTimeoutFalse'
            resume_serial_num = self.add_cmd(
                ResumeTimeoutFalse(
                    cmd_runners=resumer_names,
                    targets=all_targets,
                    stopped_names=stopped_names,
                    timeout=timeout_time,
                    error_stopped_target=error_stopped_target))
        else:
            resume_to_confirm = 'ResumeTimeoutTrue'
            resume_serial_num = self.add_cmd(
                ResumeTimeoutTrue(
                    cmd_runners=resumer_names,
                    targets=all_targets,
                    stopped_names=stopped_names,
                    timeout=timeout_time,
                    timeout_names=timeout_names,
                    error_stopped_target=error_stopped_target))

        ################################################################
        # prevent stopped_no_delay from getting started too soon
        ################################################################
        if error_stopped_target and stopped_names:
            self.add_cmd(
                ConfirmResponse(
                    cmd_runners=[self.commander_name],
                    confirm_cmd=resume_to_confirm,
                    confirm_serial_num=resume_serial_num,
                    confirmers=resumer_names))
        ################################################################
        # create and start unreg_no_delay_names and build smart_wait
        ################################################################
        if unreg_no_delay_names:
            f1_create_items: list[F1CreateItem] = []
            for idx, name in enumerate(unreg_no_delay_names):
                if idx % 2:
                    app_config = AppConfig.ScriptStyle
                else:
                    app_config = AppConfig.RemoteThreadApp

                f1_create_items.append(F1CreateItem(name=name,
                                                    auto_start=True,
                                                    target_rtn=outer_f1,
                                                    app_config=app_config))
            self.build_create_suite(
                f1_create_items=f1_create_items,
                validate_config=False)

            wait_unreg_no_delay_serial_num = self.add_cmd(
                Wait(cmd_runners=unreg_no_delay_names,
                     resumers=resumer_names,
                     stopped_remotes=set(),
                     wait_for=st.WaitFor.All,
                     error_stopped_target=True))

        ################################################################
        # build stopped_no_delay_targets smart_wait
        ################################################################
        if stopped_no_delay_targets:
            self.build_join_suite(
                cmd_runners=self.commander_name,
                join_target_names=stopped_no_delay_targets)

            for stopped_no_delay_name in stopped_no_delay_targets:
                self.add_cmd(VerifyPairedNot(
                    cmd_runners=self.commander_name,
                    exp_not_paired_names=stopped_no_delay_name))

            f1_create_items: list[F1CreateItem] = []
            for idx, name in enumerate(stopped_no_delay_targets):
                if idx % 2:
                    app_config = AppConfig.ScriptStyle
                else:
                    app_config = AppConfig.RemoteThreadApp

                f1_create_items.append(F1CreateItem(name=name,
                                                    auto_start=True,
                                                    target_rtn=outer_f1,
                                                    app_config=app_config))
            self.build_create_suite(
                f1_create_items=f1_create_items,
                validate_config=False)

            wait_stopped_no_delay_serial_num = self.add_cmd(
                Wait(cmd_runners=stopped_no_delay_targets,
                     resumers=resumer_names,
                     stopped_remotes=set(),
                     wait_for=st.WaitFor.All,
                     error_stopped_target=True))

        ################################################################
        # wait for resume timeouts to be known
        ################################################################
        if not (error_stopped_target and stopped_names):
            self.add_cmd(WaitForResumeTimeouts(
                cmd_runners=self.commander_name,
                resumer_names=resumer_names,
                timeout_names=timeout_names))

        self.add_cmd(Pause(
            cmd_runners='alpha',
            pause_seconds=pause_time))

        ################################################################
        # start registered_names_after and issue smart_wait
        ################################################################
        if registered_names_after:
            self.build_start_suite(start_names=registered_names_after)
            wait_reg_after_target_serial_num = self.add_cmd(
                Wait(cmd_runners=registered_names_after,
                     resumers=resumer_names,
                     stopped_remotes=set(),
                     wait_for=st.WaitFor.All,
                     error_stopped_target=True))

        ################################################################
        # build unreg_delay_names smart_wait
        ################################################################
        if unreg_delay_names:
            f1_create_items: list[F1CreateItem] = []
            for idx, name in enumerate(unreg_delay_names):
                if idx % 2:
                    app_config = AppConfig.ScriptStyle
                else:
                    app_config = AppConfig.RemoteThreadApp

                f1_create_items.append(F1CreateItem(name=name,
                                                    auto_start=False,
                                                    target_rtn=outer_f1,
                                                    app_config=app_config))
            self.build_create_suite(
                f1_create_items=f1_create_items,
                validate_config=False)

        ################################################################
        # build stopped_delay_targets smart_wait
        ################################################################
        if stopped_delay_targets:
            self.build_join_suite(
                cmd_runners=self.commander_name,
                join_target_names=stopped_delay_targets)

            for stopped_delay_name in stopped_delay_targets:
                self.add_cmd(VerifyPairedNot(
                    cmd_runners=self.commander_name,
                    exp_not_paired_names=stopped_delay_name))

            f1_create_items: list[F1CreateItem] = []
            for idx, name in enumerate(stopped_delay_targets):
                if idx % 2:
                    app_config = AppConfig.ScriptStyle
                else:
                    app_config = AppConfig.RemoteThreadApp

                f1_create_items.append(F1CreateItem(name=name,
                                                    auto_start=False,
                                                    target_rtn=outer_f1,
                                                    app_config=app_config))
            self.build_create_suite(
                f1_create_items=f1_create_items,
                validate_config=False)

            self.build_start_suite(start_names=stopped_delay_targets)
            wait_stopped_delay_serial_num = self.add_cmd(
                Wait(cmd_runners=stopped_delay_targets,
                     resumers=resumer_names,
                     stopped_remotes=set(),
                     wait_for=st.WaitFor.All,
                     error_stopped_target=True))

        if unreg_delay_names:
            self.build_start_suite(start_names=unreg_delay_names)
            wait_unreg_delay_serial_num = self.add_cmd(
                Wait(cmd_runners=unreg_delay_names,
                     resumers=resumer_names,
                     stopped_remotes=set(),
                     wait_for=st.WaitFor.All,
                     error_stopped_target=True))
        ####################################################
        # confirm the active target waits
        ####################################################
        if active_target_names:
            self.add_cmd(
                ConfirmResponse(
                    cmd_runners=[self.commander_name],
                    confirm_cmd='Wait',
                    confirm_serial_num=wait_active_target_serial_num,
                    confirmers=active_target_names))
        ####################################################
        # confirm the registered target waits
        ####################################################
        if registered_names_before:
            self.add_cmd(
                ConfirmResponse(
                    cmd_runners=[self.commander_name],
                    confirm_cmd='Wait',
                    confirm_serial_num=wait_reg_before_target_serial_num,
                    confirmers=registered_names_before))

        ####################################################
        # confirm the registered target waits
        ####################################################
        if registered_names_after:
            self.add_cmd(
                ConfirmResponse(
                    cmd_runners=[self.commander_name],
                    confirm_cmd='Wait',
                    confirm_serial_num=wait_reg_after_target_serial_num,
                    confirmers=registered_names_after))

        ####################################################
        # confirm the unreg_no_delay_names
        ####################################################
        if unreg_no_delay_names:
            if error_stopped_target and stopped_names:
                self.add_cmd(
                    ConfirmResponseNot(
                        cmd_runners=[self.commander_name],
                        confirm_cmd='Wait',
                        confirm_serial_num=wait_unreg_no_delay_serial_num,
                        confirmers=unreg_no_delay_names))

                resume_serial_num2 = self.add_cmd(
                    ResumeTimeoutFalse(
                        cmd_runners=resumer_names,
                        targets=unreg_no_delay_names,
                        stopped_names=[],
                        timeout=0.5,
                        error_stopped_target=True))
                self.add_cmd(
                    ConfirmResponse(
                        cmd_runners=[self.commander_name],
                        confirm_cmd='ResumeTimeoutTrue',
                        confirm_serial_num=resume_serial_num2,
                        confirmers=resumer_names))
            self.add_cmd(
                ConfirmResponse(
                    cmd_runners=[self.commander_name],
                    confirm_cmd='Wait',
                    confirm_serial_num=wait_unreg_no_delay_serial_num,
                    confirmers=unreg_no_delay_names))
        ####################################################
        # confirm the unreg_delay_names
        ####################################################
        if unreg_delay_names:
            if (timeout_type == TimeoutType.TimeoutTrue
                    or (error_stopped_target and stopped_names)):
                self.add_cmd(
                    ConfirmResponseNot(
                        cmd_runners=[self.commander_name],
                        confirm_cmd='Wait',
                        confirm_serial_num=wait_unreg_delay_serial_num,
                        confirmers=unreg_delay_names))

                resume_serial_num2 = self.add_cmd(
                    ResumeTimeoutFalse(
                        cmd_runners=resumer_names,
                        targets=unreg_delay_names,
                        stopped_names=[],
                        timeout=0.5,
                        error_stopped_target=True))
                self.add_cmd(
                    ConfirmResponse(
                        cmd_runners=[self.commander_name],
                        confirm_cmd='ResumeTimeoutTrue',
                        confirm_serial_num=resume_serial_num2,
                        confirmers=resumer_names))
            self.add_cmd(
                ConfirmResponse(
                    cmd_runners=[self.commander_name],
                    confirm_cmd='Wait',
                    confirm_serial_num=wait_unreg_delay_serial_num,
                    confirmers=unreg_delay_names))
        ####################################################
        # confirm the stopped_no_delay_targets
        ####################################################
        if stopped_no_delay_targets:
            if error_stopped_target and stopped_names:
                self.add_cmd(
                    ConfirmResponseNot(
                        cmd_runners=[self.commander_name],
                        confirm_cmd='Wait',
                        confirm_serial_num=wait_stopped_no_delay_serial_num,
                        confirmers=stopped_no_delay_targets))

                resume_serial_num2 = self.add_cmd(
                    ResumeTimeoutFalse(
                        cmd_runners=resumer_names,
                        targets=stopped_no_delay_targets,
                        stopped_names=[],
                        timeout=0.5,
                        error_stopped_target=True))
                self.add_cmd(
                    ConfirmResponse(
                        cmd_runners=[self.commander_name],
                        confirm_cmd='ResumeTimeoutTrue',
                        confirm_serial_num=resume_serial_num2,
                        confirmers=resumer_names))
            self.add_cmd(
                ConfirmResponse(
                    cmd_runners=[self.commander_name],
                    confirm_cmd='Wait',
                    confirm_serial_num=wait_stopped_no_delay_serial_num,
                    confirmers=stopped_no_delay_targets))

        ####################################################
        # confirm the stopped_names
        ####################################################
        if stopped_delay_targets:
            if (timeout_type == TimeoutType.TimeoutTrue
                    or (error_stopped_target and stopped_names)):
                self.add_cmd(
                    ConfirmResponseNot(
                        cmd_runners=[self.commander_name],
                        confirm_cmd='Wait',
                        confirm_serial_num=wait_stopped_delay_serial_num,
                        confirmers=stopped_delay_targets))

                resume_serial_num2 = self.add_cmd(
                    ResumeTimeoutFalse(
                        cmd_runners=resumer_names,
                        targets=stopped_delay_targets,
                        stopped_names=[],
                        timeout=0.5,
                        error_stopped_target=True))
                self.add_cmd(
                    ConfirmResponse(
                        cmd_runners=[self.commander_name],
                        confirm_cmd='ResumeTimeoutTrue',
                        confirm_serial_num=resume_serial_num2,
                        confirmers=resumer_names))
            self.add_cmd(
                ConfirmResponse(
                    cmd_runners=[self.commander_name],
                    confirm_cmd='Wait',
                    confirm_serial_num=wait_stopped_delay_serial_num,
                    confirmers=stopped_delay_targets))

        ####################################################
        # confirm the resumer_names
        ####################################################
        if not (error_stopped_target and stopped_names):
            self.add_cmd(
                ConfirmResponse(
                    cmd_runners=[self.commander_name],
                    confirm_cmd=resume_to_confirm,
                    confirm_serial_num=resume_serial_num,
                    confirmers=resumer_names))

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

        num_active_needed = (
                num_senders
                + num_active_targets
                + num_exit_timeouts
                + num_full_q_timeouts
                + 1)

        timeout_time = ((num_active_targets * 0.16)
                        + (num_registered_targets * 0.16)
                        + (num_unreg_timeouts * 0.50)
                        + (num_exit_timeouts * 0.50)
                        + (num_full_q_timeouts * 0.25 * self.max_msgs))

        if timeout_type == TimeoutType.TimeoutFalse:
            timeout_time *= 2  # prevent timeout
            timeout_time = max(timeout_time, 1)
        elif timeout_type == TimeoutType.TimeoutTrue:
            timeout_time *= 0.5  # force timeout

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
        if full_q_names:
            for idx in range(self.max_msgs):
                # send from each sender thread to ensure we get
                # exactly max_msgs on each pair between sender and the
                # full_q targets
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

            self.build_exit_suite(cmd_runner=self.commander_name,
                                  names=exit_names)
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
                        removed_names=exit_name,
                        exp_half_paired_names=sender_names[1]))

            if num_senders == 3:
                for exit_name in exit_names:
                    self.add_cmd(VerifyPairedHalf(
                        cmd_runners=self.commander_name,
                        removed_names=exit_name,
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
                    timeout=timeout_time,
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
                        timeout=timeout_time))

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
                self.build_exit_suite(cmd_runner=self.commander_name,
                                      names=exit_names)
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
        """Add config cmds to the scenario queue."""

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
                                          =AppConfig.RemoteThreadApp),
                             F1CreateItem(name='fox',
                                          auto_start=False,
                                          target_rtn=outer_f1,
                                          app_config
                                          =AppConfig.ScriptStyle),
                             F1CreateItem(name='george',
                                          auto_start=False,
                                          target_rtn=outer_f1,
                                          app_config
                                          =AppConfig.RemoteThreadApp)
                             ]))
        self.add_cmd(VerifyInRegistry(
            cmd_runners='alpha',
            exp_in_registry_names=['alpha', 'beta', 'charlie', 'delta',
                                   'echo', 'fox', 'george']))
        self.add_cmd(VerifyAlive(
            cmd_runners='alpha',
            exp_alive_names=['alpha', 'beta', 'charlie']))
        self.add_cmd(VerifyAliveNot(
            cmd_runners='alpha',
            exp_not_alive_names=['delta', 'echo', 'fox', 'george']))
        self.add_cmd(VerifyActive(
            cmd_runners='alpha',
            exp_active_names=['alpha', 'beta', 'charlie']))
        self.add_cmd(VerifyRegistered(
            cmd_runners='alpha',
            exp_registered_names=['delta', 'echo', 'fox', 'george']))
        self.add_cmd(VerifyStatus(
            cmd_runners='alpha',
            check_status_names=['alpha', 'beta', 'charlie'],
            expected_status=st.ThreadState.Alive))
        self.add_cmd(VerifyStatus(
            cmd_runners='alpha',
            check_status_names=['delta', 'echo', 'fox', 'george'],
            expected_status=st.ThreadState.Registered))
        self.add_cmd(VerifyPaired(
            cmd_runners='alpha',
            exp_paired_names=['alpha', 'beta', 'charlie', 'delta', 'echo',
                              'fox', 'george']))
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
            expected_status=st.ThreadState.Alive))
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
                    msgs_to_send=msgs_to_send,
                    log_msg='SendCmd test log message 1'))

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
                    log_msg='RecvMsg test log message 2'))

        ################################################################
        # confirm the recv_msg
        ################################################################
        self.add_cmd(
            ConfirmResponse(cmd_runners='alpha',
                            confirm_cmd='RecvMsg',
                            confirm_serial_num=recv_msg_serial_num,
                            confirmers=['alpha', 'beta', 'charlie']))

        ################################################################
        # wait
        ################################################################
        self.add_cmd(
            Wait(cmd_runners='beta',
                 resumers='charlie',
                 stopped_remotes=set(),
                 wait_for=st.WaitFor.All,
                 error_stopped_target=True,
                 log_msg='Wait test log message 3'))
        ################################################################
        # resume
        ################################################################
        self.add_cmd(
            Resume(cmd_runners='charlie',
                   targets='beta',
                   stopped_names=[],
                   log_msg='Resume test log message 4'))

        ################################################################
        # sync
        ################################################################
        self.add_cmd(
            Sync(cmd_runners='beta',
                 targets='charlie',
                 log_msg='Sync test log message 5'))
        self.add_cmd(
            Sync(cmd_runners='charlie',
                 targets='beta',
                 log_msg='Sync test log message 6'))

        ################################################################
        # stop all threads
        ################################################################

        self.add_cmd(StopThread(cmd_runners='alpha',
                                stop_names=['beta', 'charlie',
                                            'delta', 'echo']))
        self.add_cmd(VerifyAliveNot(
            cmd_runners='alpha',
            exp_not_alive_names=['beta', 'charlie', 'delta', 'echo',
                                 'fox', 'george']))
        self.add_cmd(ValidateConfig(
            cmd_runners='alpha'))
        self.add_cmd(Join(
            cmd_runners='alpha',
            join_names=['beta', 'charlie', 'delta', 'echo'],
            log_msg='Join test log message 7'))
        self.add_cmd(ValidateConfig(
            cmd_runners='alpha'))
        self.add_cmd(Unregister(
            cmd_runners='alpha',
            unregister_targets=['fox', 'george'],
            log_msg='Unregister test log message 8'))
        self.add_cmd(VerifyInRegistryNot(
            cmd_runners='alpha',
            exp_not_in_registry_names=['fox', 'george']))
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
    # build_sync_scenario_suite
    ####################################################################
    def build_sync_scenario_suite(self,
                                  timeout_type: TimeoutType,
                                  num_syncers: int,
                                  num_stopped_syncers: int,
                                  num_timeout_syncers: int,
                                  error_stopped_target: bool,
                                  ) -> None:
        """Build ConfigCmd items for sync scenarios.

        Args:
            timeout_type: timeout for None, False, or True
            num_syncers: number of threads that will successfully
                sync
            num_stopped_syncers: number of threads that will
                cause a not alive error
            num_timeout_syncers: number of threads that will
                cause a timeout error
            error_stopped_target: specifies whether to raise not alive
                for stopped syncers

        """
        # Make sure we have enough threads. Note that we subtract 1 from
        # the count of unregistered names to ensure we have one thread
        # for the commander
        assert (num_syncers
                + num_stopped_syncers
                + num_timeout_syncers) <= len(self.unregistered_names) - 1

        timeout_time = ((num_syncers * 0.64)
                        + (num_stopped_syncers * 0.64)
                        + (num_timeout_syncers * 0.64))

        pause_time = timeout_time
        if timeout_type == TimeoutType.TimeoutFalse:
            timeout_time *= 2  # prevent timeout
            timeout_time = max(timeout_time, 2)
        elif timeout_type == TimeoutType.TimeoutTrue:
            timeout_time *= 0.5  # force timeout

        self.build_config(
            cmd_runner=self.commander_name,
            num_registered=num_timeout_syncers,
            num_active=num_syncers + 1,
            num_stopped=num_stopped_syncers)

        self.log_name_groups()
        # active_names = self.active_names.copy()
        # remove commander for now, but if we add it later we need to
        # be careful not to exit the commander
        active_names = self.active_names - {self.commander_name}

        ################################################################
        # choose syncer_names
        ################################################################
        syncer_names = self.choose_names(
            name_collection=active_names,
            num_names_needed=num_syncers,
            update_collection=True,
            var_name_for_log='syncer_names')

        ################################################################
        # choose timeout_syncer_names
        ################################################################
        timeout_syncer_names = self.choose_names(
            name_collection=self.registered_names,
            num_names_needed=num_timeout_syncers,
            update_collection=False,
            var_name_for_log='timeout_syncer_names')

        ################################################################
        # choose stopped_syncer_names
        ################################################################
        stopped_syncer_names = self.choose_names(
            name_collection=self.stopped_names,
            num_names_needed=num_stopped_syncers,
            update_collection=False,
            var_name_for_log='stopped_syncer_names')

        all_targets: list[str] = (syncer_names
                                  + timeout_syncer_names
                                  + stopped_syncer_names)

        ################################################################
        # timeout True
        ################################################################
        if timeout_type == TimeoutType.TimeoutTrue:
            confirm_cmd_to_use = 'SyncTimeoutTrue'
            sync_serial_num = self.add_cmd(
                SyncTimeoutTrue(
                    cmd_runners=syncer_names,
                    targets=set(all_targets),
                    timeout=timeout_time,
                    timeout_remotes=set(timeout_syncer_names),
                    stopped_remotes=set(stopped_syncer_names),
                    error_stopped_target=error_stopped_target))
        else:
            ############################################################
            # timeout False
            ############################################################
            if timeout_type == TimeoutType.TimeoutFalse:
                confirm_cmd_to_use = 'SyncTimeoutFalse'
                sync_serial_num = self.add_cmd(
                    SyncTimeoutFalse(
                        cmd_runners=syncer_names,
                        targets=set(all_targets),
                        timeout=timeout_time,
                        timeout_remotes=set(timeout_syncer_names),
                        stopped_remotes=set(stopped_syncer_names),
                        error_stopped_target=error_stopped_target))
            else:
                ########################################################
                # timeout None
                ########################################################
                confirm_cmd_to_use = 'Sync'
                sync_serial_num = self.add_cmd(
                    Sync(cmd_runners=syncer_names,
                         targets=set(all_targets),
                         timeout=timeout_time,
                         timeout_remotes=set(timeout_syncer_names),
                         stopped_remotes=set(stopped_syncer_names),
                         error_stopped_target=error_stopped_target,
                         log_msg='sync test1'))

            self.add_cmd(Pause(cmd_runners=self.commander_name,
                               pause_seconds=pause_time))
            ############################################################
            # start the registered syncers to get them active
            ############################################################
            if timeout_syncer_names:
                self.build_start_suite(
                    start_names=list(timeout_syncer_names),
                    validate_config=False)

            ############################################################
            # join stopped syncers and then create to get them active
            ############################################################
            if stopped_syncer_names:
                self.build_join_suite(
                    cmd_runners=self.commander_name,
                    join_target_names=list(stopped_syncer_names))
                f1_create_items: list[F1CreateItem] = []
                for idx, name in enumerate(stopped_syncer_names):
                    if idx % 2:
                        app_config = AppConfig.ScriptStyle
                    else:
                        app_config = AppConfig.RemoteThreadApp

                    f1_create_items.append(F1CreateItem(name=name,
                                                        auto_start=True,
                                                        target_rtn=outer_f1,
                                                        app_config=app_config))
                self.build_create_suite(
                    f1_create_items=f1_create_items,
                    validate_config=False)

            ############################################################
            # do sync for newly started syncers
            ############################################################
            if ((not (stopped_syncer_names and error_stopped_target))
                    and (timeout_syncer_names or stopped_syncer_names)):
                started_cmd_runners = (list(timeout_syncer_names)
                                       + list(stopped_syncer_names))
                sync_serial_num2 = self.add_cmd(
                    Sync(cmd_runners=started_cmd_runners,
                         targets=set(all_targets),
                         timeout=timeout_time,
                         timeout_remotes=set(timeout_syncer_names),
                         stopped_remotes=set(stopped_syncer_names),
                         error_stopped_target=error_stopped_target,
                         log_msg='sync test2'))
                self.add_cmd(
                    ConfirmResponse(cmd_runners=[self.commander_name],
                                    confirm_cmd='Sync',
                                    confirm_serial_num=sync_serial_num2,
                                    confirmers=started_cmd_runners))

        ################################################################
        # confirm the sync
        ################################################################
        self.add_cmd(
            ConfirmResponse(cmd_runners=[self.commander_name],
                            confirm_cmd=confirm_cmd_to_use,
                            confirm_serial_num=sync_serial_num,
                            confirmers=list(syncer_names)))

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

        self.log_test_msg(f'{var_name_for_log}: {chosen_names}')

        return chosen_names

    ####################################################################
    # create_commander_thread
    ####################################################################
    def create_commander_thread(self,
                                cmd_runner: str,
                                name: str,
                                thread_alive: bool,
                                auto_start: bool) -> None:
        """Create the commander thread.

        Args:
            cmd_runner: name of thread doing the create
            name: name of new commander thread
            thread_alive: specifies whether the thread is already
                started
            auto_start: specifies whether to start the thread
        """
        self.log_test_msg(f'create_commander_thread entry: {cmd_runner=}')
        if not self.commander_thread:
            self.commander_thread = st.SmartThread(
                name=name, auto_start=auto_start, max_msgs=self.max_msgs)
        self.all_threads[name] = self.commander_thread

        if auto_start:
            exp_status = st.ThreadState.Alive
        else:
            exp_status = st.ThreadState.Registered
        with self.ops_lock:
            self.monitor_add_items[cmd_runner] = MonitorAddItem(
                cmd_runner=cmd_runner,
                thread_alive=self.cmd_thread_alive,
                auto_start=self.cmd_thread_auto_start,
                expected_status=exp_status)
            self.cmd_waiting_event_items[cmd_runner] = threading.Event()

        self.monitor_event.set()

        self.log_test_msg(f'{cmd_runner=} create_commander_thread waiting '
                          f'for monitor')

        self.cmd_waiting_event_items[cmd_runner].wait()
        with self.ops_lock:
            del self.monitor_add_items[cmd_runner]
            del self.cmd_waiting_event_items[cmd_runner]
            self.expected_registered[name].is_alive = True
            self.expected_registered[name].status = st.ThreadState.Alive

        self.log_test_msg(f'create_commander_thread exit: {cmd_runner=}')

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
        self.log_test_msg(f'create_f1_thread entry: {cmd_runner=}, '
                          f'{name=}')
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

        self.all_threads[name] = f1_thread

        if auto_start:
            exp_status = st.ThreadState.Alive
        else:
            exp_status = st.ThreadState.Registered

        with self.ops_lock:
            self.monitor_add_items[cmd_runner] = MonitorAddItem(
                cmd_runner=name,
                # thread_alive=auto_start,
                thread_alive=False,
                auto_start=auto_start,
                # expected_status=exp_status,
                expected_status=st.ThreadState.Registered)

            self.cmd_waiting_event_items[cmd_runner] = threading.Event()

        self.monitor_event.set()

        # self.log_test_msg(f'{cmd_runner=} create_f1_thread waiting for '
        #                   'monitor')
        self.log_test_msg(f'{cmd_runner=} create_f1_thread waiting '
                          f'for monitor')
        self.cmd_waiting_event_items[cmd_runner].wait()
        with self.ops_lock:
            del self.monitor_add_items[cmd_runner]
            del self.cmd_waiting_event_items[cmd_runner]

        self.log_test_msg(f'create_f1_thread exiting: {cmd_runner=}, '
                          f'{name=}')

    ####################################################################
    # dec_ops_count
    ####################################################################
    def dec_ops_count(self,
                      cmd_runner: str,
                      sender: str,
                      dec_ops_type: str) -> None:
        """Decrement the pending operations count.

        Args:
            cmd_runner: the names of the thread whose count is to be
                decremented
            sender: the name of the threads that is paired with the
                cmd_runner
            dec_ops_type: recv_msg or wait

        """
        pair_key = st.SmartThread._get_pair_key(cmd_runner, sender)
        self.log_test_msg(
            f'dec_ops_count entry: {cmd_runner=}, {pair_key=}')

        with self.ops_lock:
            self.expected_pairs[pair_key][cmd_runner].pending_ops_count -= 1
            ops_count = self.expected_pairs[pair_key][
                cmd_runner].pending_ops_count
            self.log_test_msg(f'dec_ops_count for {cmd_runner=} with '
                              f'{pair_key=} dec ops_count to {ops_count}')
            if self.expected_pairs[pair_key][cmd_runner].pending_ops_count < 0:
                self.abort_all_f1_threads()
                raise InvalidConfigurationDetected(
                    f'dec_ops_count for for pair_key {pair_key}, '
                    f'name {cmd_runner} was decremented below zero')

            # indicate that this thread might need to update pair array
            # self.pending_recv_msg_par[cmd_runner] = True

            # remove sender from list if deferred delete is not needed
            # self.recv_msg_event_items[cmd_runner].targets.remove(sender)

            # determine whether deferred delete is needed
            if (self.expected_pairs[pair_key][
                    cmd_runner].pending_ops_count == 0
                    and sender not in self.expected_pairs[pair_key].keys()):
                self.update_pair_array_items.append(UpaItem(
                    upa_cmd_runner=cmd_runner,
                    upa_type=dec_ops_type,
                    upa_target=sender,
                    upa_def_del_name=cmd_runner,
                    upa_process=''))

                # we need to post later when we do the pair array update
                # self.recv_msg_event_items[
                #     cmd_runner].deferred_post_needed = True
                # self.log_test_msg(f'dec_ops_count for {cmd_runner=} with '
                #                   f'{pair_key=} set deferred_post_needed')

            # post handle_recv_msg if all receives are now processed
            # if (not self.recv_msg_event_items[cmd_runner].targets
            #         and not self.recv_msg_event_items[
            #             cmd_runner].deferred_post_needed):
            #     self.recv_msg_event_items[cmd_runner].client_event.set()
            #     self.log_test_msg(f'dec_ops_count for {cmd_runner=} with '
            #                       f'{pair_key=} set client_event')

        self.log_test_msg(
            f'dec_ops_count exit: {cmd_runner=}, {pair_key=}')

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
        self.log_test_msg(f'del_thread entered: {cmd_runner=}, '
                          f'{del_name=}, {process=}')

        self.log_test_msg(f'del_thread exit: {cmd_runner=}, '
                          f'{del_name=}, {process=}')

    ####################################################################
    # exit_thread
    ####################################################################
    def exit_thread(self,
                    cmd_runner: str,
                    stopped_by: str):
        """Drive the commands received on the command queue.

        Args:
            cmd_runner: name of thread being stopped
            stopped_by: name of thread doing the stop

        """
        self.expected_registered[cmd_runner].stopped_by = stopped_by
        self.f1_process_cmds[cmd_runner] = False

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

            cmd.run_process(cmd_runner=f1_name)

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
    def get_log_msgs(self) -> bool:
        """Search for a log messages and return them in order.

        Returns:
            True, if messages were found, False otherwise
        """
        # we should never call with an non-empty deque
        assert not self.log_found_items

        work_log = self.caplog_to_use.record_tuples.copy()

        end_idx = len(work_log)

        # return if no new log message have been issued since last call
        if self.log_start_idx >= end_idx:
            return False

        work_log = work_log[self.log_start_idx:end_idx]

        for idx, log_tuple in enumerate(work_log, self.log_start_idx):
            for log_search_item in self.log_search_items:
                if log_search_item.search_pattern.match(log_tuple[2]):
                    found_log_item = log_search_item.get_found_log_item(
                        found_log_msg=log_tuple[2],
                        found_log_idx=idx
                    )
                    self.log_found_items.append(found_log_item)

        # update next starting point
        self.log_start_idx = end_idx

        if self.log_found_items:
            return True
        else:
            return False

    ####################################################################
    # get_ptime
    ####################################################################
    @staticmethod
    def get_ptime() -> str:
        """Returns a printable UTC time stamp.

        Returns:
            a timestamp as a string
        """
        now_time = datetime.utcnow()
        print_time = now_time.strftime("%H:%M:%S.%f")

        return print_time

    ####################################################################
    # handle_deferred_deletes
    ####################################################################
    def handle_deferred_deletes(self,
                                cmd_runner: str) -> bool:
        """Delete deferred deletes and issue log messages

        Args:
            cmd_runner: thread doing the delete

        Returns:
            True if the refresh array was updated, False otherwise
        """
        update_pair_array_msg_needed = False
        pair_keys_to_delete: list[tuple[str, str]] = []
        for del_def_key in self.del_deferred_list:
            pair_key = del_def_key[0]
            def_del_name = del_def_key[1]
            if pair_key[0] == def_del_name:
                sender_name = pair_key[1]
            else:
                sender_name = pair_key[0]

            if (pair_key in self.expected_pairs
                    and sender_name not in self.expected_pairs[pair_key]
                    and def_del_name in self.expected_pairs[pair_key]
                    and self.expected_pairs[pair_key][
                        def_del_name].pending_ops_count == 0):
                pair_keys_to_delete.append(pair_key)
                self.del_deferred_list.remove(del_def_key)
                update_pair_array_msg_needed = True
                self.add_log_msg(re.escape(
                    f"{cmd_runner} removed status_blocks entry "
                    f"for pair_key = {pair_key}, "
                    f"name = {def_del_name}"))

        for pair_key in pair_keys_to_delete:
            self.log_test_msg(f'handle_deferred_deletes for {cmd_runner=} '
                              f'deleted {pair_key=}')
            del self.expected_pairs[pair_key]
            self.add_log_msg(re.escape(
                f'{cmd_runner} removed _pair_array entry'
                f' for pair_key = {pair_key}'))
            update_pair_array_msg_needed = True

        return update_pair_array_msg_needed

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
        # received a message and have the potential to update the
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
        self.add_log_msg(re.escape(
            f'{cmd_runner} entered _refresh_pair_array'))
        # with self.ops_lock:
        #     if self.pending_recv_msg_par[cmd_runner]:
        #         self.pending_recv_msg_par = defaultdict(bool)
        #         self.pending_recv_msg_par[cmd_runner] = True
        #     else:  # anyone else is no longer eligible either
        #         self.pending_recv_msg_par = defaultdict(bool)

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

            # If a_name was recently stopped, the log msg idx was saved
            # in recently_stopped. If never stopped, the idx will be
            # zero
            stopped_log_idx = self.recently_stopped[a_name]

            search_msg = f'key = {a_name}, item = '

            log_msg, log_pos = self.get_log_msg(search_msg=search_msg,
                                                skip_num=0,
                                                start_idx=0,
                                                end_idx=log_idx,
                                                reverse_search=True)
            if not log_msg:
                self.abort_all_f1_threads()
                raise FailedToFindLogMsg(f'for {a_name=}')
            # the timing of the stop and the join make it difficult to
            # verify the is_alive and status, so we just accept this
            # status msg as is when there is a stop between the
            # issuing of the status message and the join
            elif (log_pos - 7) < stopped_log_idx < log_idx:
                self.add_log_msg(re.escape(log_msg))
                log_msg = f'handle_exp_status_log_msgs accept 1 for {a_name}'
                self.log_ver.add_msg(log_msg=re.escape(log_msg))
                logger.debug(log_msg)
            elif a_name in self.stopping_names:
                self.add_log_msg(re.escape(log_msg))
                log_msg = f'handle_exp_status_log_msgs accept 2 for {a_name}'
                self.log_ver.add_msg(log_msg=re.escape(log_msg))
                logger.debug(log_msg)
            else:
                split_msg = log_msg.split()
                is_alive = eval(split_msg[-3].removesuffix(','))
                status = eval('st.' + split_msg[-1])
                if (status == tracker.status
                        and is_alive == tracker.is_alive):
                    self.add_log_msg(re.escape(log_msg))
                    log_msg = (f'handle_exp_status_log_msgs verified '
                               f'for {a_name}')
                    self.log_ver.add_msg(log_msg=re.escape(log_msg))
                    logger.debug(log_msg)
                else:
                    self.abort_all_f1_threads()
                    raise FailedToFindLogMsg(f'for {a_name=} expected '
                                             f'{tracker.is_alive=}, '
                                             f'got {is_alive=} '
                                             f'{tracker.status=} '
                                             f'got {status=} '
                                             f'for {log_msg=} ')

    ####################################################################
    # handle_join
    ####################################################################
    def handle_join(self,
                    cmd_runner: str,
                    join_names: list[str],
                    log_msg: str,
                    timeout_type: TimeoutType = TimeoutType.TimeoutNone,
                    timeout: Optional[IntOrFloat] = None,
                    timeout_names: Optional[set[str]] = None
                    ) -> None:

        """Handle the join execution and log msgs.

        Args:
            cmd_runner: name of thread doing the cmd
            join_names: target threads that we will join
            log_msg: log message to issue on the join (name be None)
            timeout_type: None, False, or True
            timeout: value for timeout on join request
            timeout_names: threads that are expected to timeout

        """
        self.log_test_msg(f'handle_join entry: {cmd_runner=}, {join_names=}')
        self.log_ver.add_call_seq(
            name='smart_join',
            seq='test_smart_thread.py::ConfigVerifier.handle_join')

        start_time = time.time()
        enter_exit = ('entry', 'exit')
        if timeout_type == TimeoutType.TimeoutNone:
            self.all_threads[cmd_runner].smart_join(
                targets=set(join_names),
                log_msg=log_msg)

        elif timeout_type == TimeoutType.TimeoutFalse:
            self.all_threads[cmd_runner].smart_join(
                targets=set(join_names),
                timeout=timeout,
                log_msg=log_msg)

        elif timeout_type == TimeoutType.TimeoutTrue:
            enter_exit = ('entry', )
            error_msg = self.get_error_ms2(
                    cmd_runner=cmd_runner,
                    smart_request='smart_join',
                    targets=set(join_names),
                    pending_remotes=timeout_names,
                    error_str='SmartThreadRequestTimedOut')
            with pytest.raises(st.SmartThreadRequestTimedOut) as exc:
                self.all_threads[cmd_runner].smart_join(
                    targets=set(join_names),
                    timeout=timeout,
                    log_msg=log_msg)

            assert str(exc.value) == error_msg

            self.add_log_msg(
                self.get_error_msg(
                    cmd_runner=cmd_runner,
                    smart_request='smart_join',
                    targets=set(join_names),
                    pending_remotes=timeout_names,
                    error_str='SmartThreadRequestTimedOut'),
                log_level=logging.ERROR)

        self.add_request_log_msg(cmd_runner=cmd_runner,
                                 smart_request='smart_join',
                                 targets=set(join_names),
                                 timeout=timeout,
                                 timeout_type=timeout_type,
                                 enter_exit=enter_exit,
                                 log_msg=log_msg)

        elapsed_time: float = time.time() - start_time
        time_per_target: float = elapsed_time/len(join_names)

        self.monitor_event.set()

        with self.ops_lock:
            self.cmd_waiting_event_items[cmd_runner] = threading.Event()

        self.log_test_msg(f'{cmd_runner=} handle_join waiting for monitor')
        self.monitor_event.set()
        self.cmd_waiting_event_items[cmd_runner].wait()
        with self.ops_lock:
            del self.cmd_waiting_event_items[cmd_runner]

        self.log_test_msg(f'handle_join exiting with {elapsed_time=}, '
                          f'{len(join_names)=}, {time_per_target=}')

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

        # self.join_event_items[cmd_runner] = MonitorEventItem(
        #     client_event=threading.Event(),
        #     targets=join_names.copy()
        # )
        self.monitor_event.set()
        start_time = time.time()
        self.all_threads[cmd_runner].smart_join(
            targets=set(join_names),
            timeout=timeout,
            log_msg=log_msg)
        elapsed_time: float = time.time() - start_time
        time_per_target: float = elapsed_time / len(join_names)
        self.monitor_event.set()
        if log_msg:
            log_msg_2 = (
                f'{self.log_ver.get_call_seq("handle_join_tof")} ')
            log_msg_3 = re.escape(f'{log_msg}')
            for enter_exit in ('entry', 'exit'):
                log_msg_1 = re.escape(
                    f'join() {enter_exit}: {cmd_runner} to join '
                    f'{sorted(set(join_names))}. ')

                self.add_log_msg(log_msg_1 + log_msg_2 + log_msg_3)

        with self.ops_lock:
            self.cmd_waiting_event_items[cmd_runner] = threading.Event()

        self.log_test_msg(f'{cmd_runner=} handle_join_tof waiting for monitor')
        self.monitor_event.set()
        self.cmd_waiting_event_items[cmd_runner].wait()
        with self.ops_lock:
            del self.cmd_waiting_event_items[cmd_runner]

        self.log_test_msg(f'handle_join_tof exiting with {elapsed_time=}, '
                          f'{len(join_names)=}, {time_per_target=}')

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

        if timeout_names:
            target_names = list(set(join_names) - set(timeout_names))
        else:
            target_names = join_names.copy()

        # wait for monitor if we have names that will be deleted
        # if target_names:
        #     self.join_event_items[cmd_runner] = MonitorEventItem(
        #         client_event=threading.Event(),
        #         targets=target_names
        #     )
        self.monitor_event.set()
        start_time = time.time()
        with pytest.raises(st.SmartThreadJoinTimedOut):
            self.all_threads[cmd_runner].smart_join(
                targets=set(join_names),
                timeout=timeout,
                log_msg=log_msg)
        elapsed_time: float = time.time() - start_time
        time_per_target: float = elapsed_time / len(join_names)
        self.monitor_event.set()
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

        if target_names:
            with self.ops_lock:
                self.cmd_waiting_event_items[cmd_runner] = threading.Event()

            self.log_test_msg(
                f'{cmd_runner=} handle_join_tot waiting for monitor')
            self.monitor_event.set()
            self.cmd_waiting_event_items[cmd_runner].wait()
            with self.ops_lock:
                del self.cmd_waiting_event_items[cmd_runner]

        self.log_test_msg(f'handle_join_tot exiting with {elapsed_time=}, '
                          f'{len(join_names)=}, {time_per_target=}')

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
        self.log_test_msg(f'handle_pair_array_update entry for {cmd_runner=}')

        # self.add_log_msg(re.escape(
        #     f'{cmd_runner} entered _refresh_pair_array'))
        self.add_log_msg(re.escape(upa_msg))

        with self.ops_lock:
            while self.update_pair_array_items:
                upa_item = self.update_pair_array_items.popleft()

                if ((upa_item.upa_type == 'add' or upa_item.upa_type == 'del')
                        and upa_item.upa_cmd_runner != cmd_runner):
                    raise InvalidInputDetected(
                        f'handle_pair_array_update {cmd_runner=} found '
                        'a upa_item for add or del for '
                        f'{upa_item.upa_cmd_runner=} which is '
                        'not expected since the cmd_runner and key '
                        'should be one and the same')

                if upa_item.upa_type == 'add':
                    self.update_pair_array_add(cmd_runner=cmd_runner,
                                               upa_item=upa_item)
                elif upa_item.upa_type == 'del':
                    self.update_pair_array_del(cmd_runner=cmd_runner,
                                               upa_item=upa_item)
                elif upa_item.upa_type == 'recv_msg':
                    self.update_pair_array_def_del(cmd_runner=cmd_runner,
                                                    upa_item=upa_item)
                elif upa_item.upa_type == 'wait':
                    self.update_pair_array_def_del(cmd_runner=cmd_runner,
                                                    upa_item=upa_item)
        # handle any deferred deletes
        # self.handle_deferred_deletes(cmd_runner=cmd_runner):

        self.log_test_msg(f'handle_pair_array_update exit for {cmd_runner=}')

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
        self.log_test_msg(f'handle_recv entry: {cmd_runner=}, '
                          f'{senders=}, {del_deferred=}')

        self.log_ver.add_call_seq(
            name='recv_msg',
            seq='test_smart_thread.py::ConfigVerifier.handle_recv_msg')

        # self.recv_msg_event_items[cmd_runner] = MonitorEventItem(
        #     client_event=threading.Event(),
        #     deferred_post_needed=False,
        #     targets=senders.copy()
        # )

        if del_deferred:
            with self.ops_lock:
                for del_sender in del_deferred:
                    self.deferred_dels[(cmd_runner, del_sender)] += 1

        self.monitor_event.set()
        elapsed_time: float = 0
        for from_name in senders:
            start_time = time.time()
            recvd_msg = self.all_threads[cmd_runner].recv_msg(
                remote=from_name,
                log_msg=log_msg)
            elapsed_time += (time.time() - start_time)

            # if log_msg:
            #     log_msg_2 = (
            #         f'{self.log_ver.get_call_seq("handle_recv_msg")} ')
            #     log_msg_3 = re.escape(f'{log_msg}')
            #     for enter_exit in ('entry', 'exit'):
            #         log_msg_1 = re.escape(
            #             f'recv_msg() {enter_exit}: '
            #             f'{cmd_runner} <- {from_name}. ')
            #
            #         self.add_log_msg(log_msg_1 + log_msg_2 + log_msg_3)

            self.add_request_log_msg(cmd_runner=cmd_runner,
                                     smart_request='recv_msg',
                                     targets={from_name},
                                     timeout=0,
                                     timeout_type=TimeoutType.TimeoutNone,
                                     enter_exit=('entry', 'exit'),
                                     log_msg=log_msg)

            assert recvd_msg == exp_msgs[from_name]

            recv_log_msg = f"{cmd_runner} received msg from {from_name}"
            self.log_ver.add_msg(
                log_name='scottbrian_paratools.smart_thread',
                log_level=logging.INFO,
                log_msg=recv_log_msg)
        self.monitor_event.set()

        with self.ops_lock:
            self.cmd_waiting_event_items[cmd_runner] = threading.Event()

        self.log_test_msg(f'{cmd_runner=} handle_recv waiting for monitor')
        self.monitor_event.set()
        self.cmd_waiting_event_items[cmd_runner].wait()
        with self.ops_lock:
            # del self.recv_msg_event_items[cmd_runner]
            del self.cmd_waiting_event_items[cmd_runner]

        mean_elapsed_time = elapsed_time / len(senders)
        self.log_test_msg(f'handle_recv exiting {cmd_runner=}, '
                          f'{elapsed_time=}, {len(senders)=} '
                          f'{mean_elapsed_time=}')

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
        self.log_test_msg(f'handle_recv_tof entry: {cmd_runner=}, '
                          f'{senders=}, {del_deferred=}')

        self.log_ver.add_call_seq(
            name='recv_msg',
            seq='test_smart_thread.py::ConfigVerifier.handle_recv_msg_tof')

        # self.recv_msg_event_items[cmd_runner] = MonitorEventItem(
        #     client_event=threading.Event(),
        #     deferred_post_needed=False,
        #     targets=senders.copy()
        # )

        if del_deferred:
            with self.ops_lock:
                for del_sender in del_deferred:
                    self.deferred_dels[(cmd_runner, del_sender)] += 1

        self.monitor_event.set()
        elapsed_time: float = 0
        for from_name in senders:
            start_time = time.time()
            recvd_msg = self.all_threads[cmd_runner].recv_msg(
                remote=from_name,
                timeout=timeout,
                log_msg=log_msg)
            elapsed_time += (time.time() - start_time)

            # if log_msg:
            #     log_msg_2 = (
            #         f'{self.log_ver.get_call_seq("handle_recv_msg_tof")} ')
            #     log_msg_3 = re.escape(f'{log_msg}')
            #     for enter_exit in ('entry', 'exit'):
            #         log_msg_1 = re.escape(
            #             f'recv_msg() {enter_exit}: '
            #             f'{cmd_runner} <- {from_name}. ')
            #
            #         self.add_log_msg(log_msg_1 + log_msg_2 + log_msg_3)
            self.add_request_log_msg(cmd_runner=cmd_runner,
                                     smart_request='recv_msg',
                                     targets={from_name},
                                     timeout=0,
                                     timeout_type=TimeoutType.TimeoutFalse,
                                     enter_exit=('entry', 'exit'),
                                     log_msg=log_msg)

            assert recvd_msg == exp_msgs[from_name]

            recv_log_msg = f"{cmd_runner} received msg from {from_name}"
            self.log_ver.add_msg(
                log_name='scottbrian_paratools.smart_thread',
                log_level=logging.INFO,
                log_msg=recv_log_msg)

        self.monitor_event.set()

        with self.ops_lock:
            self.cmd_waiting_event_items[cmd_runner] = threading.Event()
        self.log_test_msg(f'{cmd_runner=} handle_recv_tof waiting for monitor')
        self.monitor_event.set()
        self.cmd_waiting_event_items[cmd_runner].wait()
        with self.ops_lock:
            # del self.recv_msg_event_items[cmd_runner]
            del self.cmd_waiting_event_items[cmd_runner]

        mean_elapsed_time = elapsed_time / len(senders)
        self.log_test_msg(f'handle_recv_tof exit: {cmd_runner=}, '
                          f'{elapsed_time=}, {len(senders)=}, '
                          f'{mean_elapsed_time=}')

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
        self.log_test_msg(f'handle_recv_tot entry: {cmd_runner=}, '
                          f'{senders=} and {del_deferred=}')

        self.log_ver.add_call_seq(
            name='recv_msg',
            seq='test_smart_thread.py::ConfigVerifier.handle_recv_msg_tot')

        non_timeout_senders = list(set(senders) - set(timeout_names))

        # if non_timeout_senders:
        #     self.recv_msg_event_items[cmd_runner] = MonitorEventItem(
        #         client_event=threading.Event(),
        #         deferred_post_needed=False,
        #         targets=non_timeout_senders.copy()
        #     )

        if del_deferred:
            with self.ops_lock:
                for del_sender in del_deferred:
                    self.deferred_dels[(cmd_runner, del_sender)] += 1
        self.monitor_event.set()
        timeout_true_value = timeout
        # elapsed_time: float = 0
        for from_name in senders:
            enter_exit_list = ('entry', 'exit')
            if from_name not in timeout_names:
                # start_time = time.time()
                recvd_msg = self.all_threads[cmd_runner].recv_msg(
                    remote=from_name,
                    timeout=timeout_true_value,
                    log_msg=log_msg)
                # elapsed_time += (time.time() - start_time)
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

            # if log_msg:
            #     log_msg_2 = (
            #         f'{self.log_ver.get_call_seq("handle_recv_msg_tot")} ')
            #     log_msg_3 = re.escape(f'{log_msg}')
            #     for enter_exit in enter_exit_list:
            #         log_msg_1 = re.escape(
            #             f'recv_msg() {enter_exit}: '
            #             f'{cmd_runner} <- {from_name}. ')
            #
            #         self.add_log_msg(log_msg_1 + log_msg_2 + log_msg_3)
            self.add_request_log_msg(cmd_runner=cmd_runner,
                                     smart_request='recv_msg',
                                     targets={from_name},
                                     timeout=0,
                                     timeout_type=TimeoutType.TimeoutTrue,
                                     enter_exit=enter_exit_list,
                                     log_msg=log_msg)

            if 'exit' in enter_exit_list:
                assert recvd_msg == exp_msgs[from_name]

                recv_log_msg = f"{cmd_runner} received msg from {from_name}"
                self.log_ver.add_msg(
                    log_name='scottbrian_paratools.smart_thread',
                    log_level=logging.INFO,
                    log_msg=recv_log_msg)

        self.monitor_event.set()

        if non_timeout_senders:
            with self.ops_lock:
                self.cmd_waiting_event_items[cmd_runner] = threading.Event()
            self.log_test_msg(
                f'{cmd_runner=} handle_recv_tot waiting for monitor')
            self.monitor_event.set()
            self.cmd_waiting_event_items[cmd_runner].wait()
            with self.ops_lock:
                # del self.recv_msg_event_items[cmd_runner]
                del self.cmd_waiting_event_items[cmd_runner]

        self.log_test_msg(f'handle_recv_tof exit: {cmd_runner=}')

    ####################################################################
    # handle_recv_waiting_log_msg
    ####################################################################
    def handle_cmd_waiting_log_msg(self,
                                   cmd_runner: str) -> None:

        """Handle the send_cmd execution and log msgs.

        Args:
            cmd_runner: name of thread doing the cmd

        """
        self.cmd_waiting_event_items[cmd_runner].set()

    ####################################################################
    # handle_reg_remove
    ####################################################################
    def handle_reg_remove(self,
                          cmd_runner: str,
                          del_name: str,
                          process: str,
                          reg_rem_log_idx: int
                          ) -> None:

        """Handle the send_cmd execution and log msgs.

        Args:
            cmd_runner: name of thread doing the cmd
            del_name: name of thread being removed
            process: either join or unregister
            reg_rem_log_idx: index in log messages for reg remove msg
        """
        self.log_test_msg(f'handle_reg_remove entered: {cmd_runner=}, '
                          f'{del_name=}, {process=}')

        # with self.ops_lock:
        #     # reg remove means that recv_msgs are no longer pending
        #     self.pending_recv_msg_par = defaultdict(bool)

        with self.ops_lock:
            if process == 'join':
                from_status = st.ThreadState.Alive
            else:
                from_status = st.ThreadState.Registered

            self.expected_registered[del_name].is_alive = False
            self.expected_registered[del_name].status = st.ThreadState.Stopped
            self.add_log_msg(
                f'{cmd_runner} set status for thread '
                f'{del_name} '
                f'from {from_status} to '
                f'{st.ThreadState.Stopped}')

            self.handle_exp_status_log_msgs(log_idx=reg_rem_log_idx)

            del self.expected_registered[del_name]

            self.add_log_msg(f'{cmd_runner} removed {del_name} from registry '
                             f'for {process=}')

            # self.add_log_msg(f'{cmd_runner} entered _refresh_pair_array')

            self.update_pair_array_items.append(UpaItem(
                upa_cmd_runner=cmd_runner,
                upa_type='del',
                upa_target=del_name,
                upa_def_del_name='',
                upa_process=process))

    ####################################################################
    # handle_reg_update
    ####################################################################
    def handle_reg_update(self,
                          cmd_runner: str,
                          new_name: str,
                          reg_update_msg: str,
                          reg_update_msg_log_idx) -> None:

        """Handle the reg update log msg.

        Args:
            cmd_runner: name of thread doing the cmd
            new_name: name of thread added to the registry
            reg_update_msg: register update log message
            reg_update_msg_log_idx: index in the log for the message

        """
        # with self.ops_lock:
        #     # reg update means that recv_msgs are no longer pending
        #     self.pending_recv_msg_par = defaultdict(bool)

        found_add_item = False
        while not found_add_item:
            with self.ops_lock:
                # for item in self.monitor_add_items:
                if cmd_runner in self.monitor_add_items:
                    found_add_item = True
                    item = self.monitor_add_items[cmd_runner]
                    self.add_thread(
                        cmd_runner=cmd_runner,
                        new_name=new_name,
                        thread_alive=item.thread_alive,
                        auto_start=item.auto_start,
                        expected_status=item.expected_status,
                        reg_update_msg=reg_update_msg,
                        reg_idx=reg_update_msg_log_idx
                    )
                    # item.add_event.set()
                    # self.monitor_add_items.remove(item)

                    if new_name != self.commander_name:
                        self.update_pair_array_items.append(UpaItem(
                            upa_cmd_runner=cmd_runner,
                            upa_type='add',
                            upa_target=new_name,
                            upa_def_del_name='',
                            upa_process=''))
                    break
            if not found_add_item:
                time.sleep(0.1)

    ####################################################################
    # handle_resume
    ####################################################################
    def handle_resume(self,
                      cmd_runner: str,
                      targets: set[str],
                      stopped_remotes: list[str],
                      timeout: IntOrFloat,
                      timeout_names: set[str],
                      timeout_type: TimeoutType,
                      error_stopped_target: bool,
                      code: Optional[Any] = None,
                      log_msg: Optional[str] = None) -> None:
        """Resume a waiter.

        Args:
            cmd_runner: thread doing the wait
            targets: names of threads to be resumed
            stopped_remotes: threads that are stopped and will result in
                a not alive error being raised if error_stopped_target is
                True
            timeout: timeout value for smart_resume
            timeout_names: names that will cause timeout
            timeout_type: None, False, or True
            error_stopped_target: specifies that smart_resume should raise an
                error if any targets are not alive
            code: code to provide to waiter
            log_msg: log msg for smart_resume
        """
        self.log_test_msg(f'handle_resume entry: {cmd_runner=}, {targets=}')

        self.log_ver.add_call_seq(
            name='smart_resume',
            seq='test_smart_thread.py::ConfigVerifier.handle_resume')

        enter_exit = ('entry', 'exit')
        if error_stopped_target and stopped_remotes:
            enter_exit = ('entry', )
            with pytest.raises(st.SmartThreadRemoteThreadNotAlive):
                if timeout_type == TimeoutType.TimeoutNone:
                    self.all_threads[cmd_runner].smart_resume(
                        targets=targets,
                        error_stopped_target=error_stopped_target,
                        log_msg=log_msg)
                else:
                    self.all_threads[cmd_runner].smart_resume(
                        targets=targets,
                        timeout=timeout,
                        error_stopped_target=error_stopped_target,
                        log_msg=log_msg)

            self.add_log_msg(
                self.get_error_msg(
                    cmd_runner=cmd_runner,
                    smart_request='smart_resume',
                    targets=targets,
                    error_str='SmartThreadRemoteThreadNotAlive',
                    stopped_remotes=set(stopped_remotes)),
                log_level=logging.ERROR)

        elif timeout_type == TimeoutType.TimeoutNone:
            self.inc_ops_count(targets.copy(), cmd_runner)
            self.all_threads[cmd_runner].smart_resume(
                targets=targets,
                error_stopped_target=error_stopped_target,
                log_msg=log_msg)

        elif timeout_type == TimeoutType.TimeoutFalse:
            self.inc_ops_count(targets.copy(), cmd_runner)
            self.all_threads[cmd_runner].smart_resume(
                targets=targets,
                timeout=timeout,
                error_stopped_target=error_stopped_target,
                log_msg=log_msg)

        elif timeout_type == TimeoutType.TimeoutTrue:
            enter_exit = ('entry', )
            with pytest.raises(st.SmartThreadRequestTimedOut):
                self.all_threads[cmd_runner].smart_resume(
                    targets=targets,
                    timeout=timeout,
                    error_stopped_target=error_stopped_target,
                    log_msg=log_msg)

            self.add_log_msg(
                self.get_error_msg(
                    cmd_runner=cmd_runner,
                    smart_request='smart_resume',
                    targets=targets,
                    error_str='SmartThreadRequestTimedOut',
                    stopped_remotes=set(stopped_remotes)),
                log_level=logging.ERROR)

        self.add_request_log_msg(cmd_runner=cmd_runner,
                                 smart_request='smart_resume',
                                 targets=targets,
                                 timeout=timeout,
                                 timeout_type=timeout_type,
                                 enter_exit=enter_exit,
                                 log_msg=log_msg)

        with self.ops_lock:
            self.cmd_waiting_event_items[cmd_runner] = threading.Event()
        self.log_test_msg(
            f'{cmd_runner=} handle_resume waiting for monitor')
        self.monitor_event.set()
        self.cmd_waiting_event_items[cmd_runner].wait()
        with self.ops_lock:
            del self.cmd_waiting_event_items[cmd_runner]

        self.log_test_msg(f'handle_resume exit: {cmd_runner=}, {targets=}')

    ####################################################################
    # handle_send_msg
    ####################################################################
    def handle_send_msg(self,
                        cmd_runner: str,
                        receivers: list[str],
                        msg_to_send: Any,
                        log_msg: str,
                        timeout_type: TimeoutType = TimeoutType.TimeoutNone,
                        timeout: IntOrFloat = 0,
                        error_stopped_target: bool = True,
                        unreg_timeout_names: Optional[set[str]] = None,
                        fullq_timeout_names: Optional[set[str]] = None,
                        stopped_remotes: Optional[set[str]] = None) -> None:

        """Handle the send_cmd execution and log msgs.

        Args:
            cmd_runner: name of thread doing the cmd
            receivers: names of threads to receive the message
            msg_to_send: message to send to the receivers
            log_msg: log message for send_msg to issue
            timeout_type: specifies None, False, or True
            timeout: value to use for timeout on the send_msg request
            error_stopped_target: specifies whether to raise error when
                threads are stopped
            stopped_remotes: names of threads that are stopped

        """
        self.log_test_msg(f'handle_send entry: {cmd_runner=}, {receivers=} ')
        self.log_ver.add_call_seq(
            name='send_msg',
            seq='test_smart_thread.py::ConfigVerifier.handle_send_msg')
        ops_count_names = receivers.copy()

        if unreg_timeout_names:
            ops_count_names = list(
                set(ops_count_names)
                - set(unreg_timeout_names))
        if fullq_timeout_names:
            ops_count_names = list(
                set(ops_count_names)
                - set(fullq_timeout_names))

        if stopped_remotes:
            ops_count_names = list(
                set(ops_count_names)
                - stopped_remotes)

        self.inc_ops_count(ops_count_names, cmd_runner)

        elapsed_time: float = 0
        start_time = time.time()

        enter_exit = ('entry', 'exit')
        if error_stopped_target and stopped_remotes:
            enter_exit = ('entry', )
            with pytest.raises(st.SmartThreadRemoteThreadNotAlive):
                if timeout_type == TimeoutType.TimeoutNone:
                    self.all_threads[cmd_runner].send_msg(
                        targets=set(receivers),
                        msg=msg_to_send,
                        error_stopped_target=error_stopped_target,
                        log_msg=log_msg)
                else:
                    self.all_threads[cmd_runner].send_msg(
                        targets=set(receivers),
                        msg=msg_to_send,
                        timeout=timeout,
                        error_stopped_target=error_stopped_target,
                        log_msg=log_msg)

            self.add_log_msg(
                self.get_error_msg(
                    cmd_runner=cmd_runner,
                    smart_request='send_msg',
                    targets=set(receivers),
                    error_str='SmartThreadRemoteThreadNotAlive',
                    stopped_remotes=stopped_remotes),
                log_level=logging.ERROR)

        elif timeout_type == TimeoutType.TimeoutNone:
            self.all_threads[cmd_runner].send_msg(
                targets=set(receivers),
                msg=msg_to_send,
                error_stopped_target=error_stopped_target,
                log_msg=log_msg)
            elapsed_time += (time.time() - start_time)
        elif timeout_type == TimeoutType.TimeoutFalse:
            self.all_threads[cmd_runner].send_msg(
                targets=set(receivers),
                msg=msg_to_send,
                timeout=timeout,
                error_stopped_target=error_stopped_target,
                log_msg=log_msg)
            elapsed_time += (time.time() - start_time)
        elif timeout_type == TimeoutType.TimeoutTrue:
            enter_exit = ('entry', )
            with pytest.raises(st.SmartThreadRequestTimedOut):
                self.all_threads[cmd_runner].send_msg(
                    targets=set(receivers),
                    msg=msg_to_send,
                    timeout=timeout,
                    error_stopped_target=error_stopped_target,
                    log_msg=log_msg)
            elapsed_time += (time.time() - start_time)
            self.add_log_msg(
                self.get_error_msg(
                    cmd_runner=cmd_runner,
                    smart_request='send_msg',
                    targets=set(receivers),
                    error_str='SmartThreadRequestTimedOut',
                    stopped_remotes=set(stopped_remotes)),
                log_level=logging.ERROR)

        self.add_request_log_msg(cmd_runner=cmd_runner,
                                 smart_request='send_msg',
                                 targets=set(receivers),
                                 timeout=timeout,
                                 timeout_type=timeout_type,
                                 enter_exit=enter_exit,
                                 log_msg=log_msg)
        for name in ops_count_names:
            log_msg = f'{cmd_runner} sent message to {name}'
            self.log_ver.add_msg(
                log_name='scottbrian_paratools.smart_thread',
                log_level=logging.INFO,
                log_msg=log_msg)

        mean_elapsed_time = elapsed_time / len(receivers)
        self.log_test_msg(f'handle_send exit: {cmd_runner=} '
                          f'{elapsed_time=}, {len(receivers)=} '
                          f'{mean_elapsed_time=}')

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
    # handle_started_log_msg
    ####################################################################
    def handle_started_log_msg(self,
                               cmd_runner: str,
                               started_name: str) -> None:
        """Set the status for a thread that was started.

        Args:
            cmd_runner: the names of the thread that was started
            started_name: name of thread that was started
        """
        self.log_test_msg(f'handle_started_log_msg entry: {cmd_runner=}, '
                          f'{started_name=}')
        self.expected_registered[started_name].is_alive = True
        self.expected_registered[started_name].status = st.ThreadState.Alive
        # self.started_event_items['alpha'].targets.remove(cmd_runner)
        # if not self.started_event_items['alpha'].targets:
        #     self.started_event_items['alpha'].client_event.set()

    ####################################################################
    # handle_stopped_log_msg
    ####################################################################
    def handle_stopped_log_msg(self,
                               cmd_runner: str,
                               stopped_name: str,
                               log_idx) -> None:
        """Set the status for a thread that was started.

        Args:
            cmd_runner: the names of the thread that did the stop
            stopped_name: name of thread that was stopped
            log_idx: index of stopped log msg

        """
        with self.ops_lock:
            self.recently_stopped[stopped_name] = log_idx
            if stopped_name in self.expected_registered:
                self.expected_registered[stopped_name].is_alive = False
            self.stopped_event_items[cmd_runner].targets.remove(stopped_name)
            if not self.stopped_event_items[cmd_runner].targets:
                self.stopped_event_items[cmd_runner].client_event.set()

    ####################################################################
    # handle_sync
    ####################################################################
    def handle_sync(self,
                    cmd_runner: str,
                    targets: set[str],
                    timeout: IntOrFloat,
                    timeout_remotes: set[str],
                    stopped_remotes: set[str],
                    conflict_remotes: set[str],
                    timeout_type: TimeoutType,
                    error_stopped_target: bool,
                    log_msg: Optional[str] = None) -> None:
        """Issue smart_sync.

        Args:
            cmd_runner: the names of the thread that did the stop
            targets: name of remotes to sync with
            timeout: value to use for timeout
            timeout_remotes: names of threads that cause timeout
            stopped_remotes: remotes that will cause a not alive error
            conflict_remotes: remotes that are doing a wait instead
                of a sync which will cause a deadlock
            timeout_type: specifies whether timeout is None, False, or
                True
            error_stopped_target: specifies whether to raise not alive error
            log_msg: log msg to be specified with the sync request
        """
        self.log_test_msg(f'{cmd_runner=} handle_sync entry for '
                          f'{targets=}, {timeout_type=}, {error_stopped_target=}')

        self.log_ver.add_call_seq(
            name='smart_sync',
            seq='test_smart_thread.py::ConfigVerifier.handle_sync')

        assert targets
        exp_completed_syncs: set[str] = targets.copy()
        enter_exit = ('entry', 'exit')
        if error_stopped_target and stopped_remotes:
            exp_completed_syncs -= stopped_remotes
            exp_completed_syncs -= timeout_remotes
            enter_exit = ('entry',)
            assert targets
            with pytest.raises(st.SmartThreadRemoteThreadNotAlive):
                if timeout_type == TimeoutType.TimeoutNone:
                    self.all_threads[cmd_runner].smart_sync(
                        targets=targets,
                        error_stopped_target=error_stopped_target,
                        log_msg=log_msg)
                else:
                    self.all_threads[cmd_runner].smart_sync(
                        targets=targets,
                        timeout=timeout,
                        error_stopped_target=error_stopped_target,
                        log_msg=log_msg)

            self.add_log_msg(
                self.get_error_msg(
                    cmd_runner=cmd_runner,
                    smart_request='smart_sync',
                    targets=targets,
                    error_str='SmartThreadRemoteThreadNotAlive',
                    stopped_remotes=stopped_remotes,
                    conflict_remotes=conflict_remotes),
                log_level=logging.ERROR)

        elif conflict_remotes:
            enter_exit = ('entry',)
            with pytest.raises(st.SmartThreadConflictDeadlockDetected):
                if timeout_type == TimeoutType.TimeoutNone:
                    self.all_threads[cmd_runner].smart_sync(
                        targets=targets,
                        error_stopped_target=error_stopped_target,
                        log_msg=log_msg)
                else:
                    self.all_threads[cmd_runner].smart_sync(
                        targets=targets,
                        timeout=timeout,
                        error_stopped_target=error_stopped_target,
                        log_msg=log_msg)

            self.add_log_msg(
                self.get_error_msg(
                    cmd_runner=cmd_runner,
                    smart_request='smart_sync',
                    targets=targets,
                    error_str='SmartThreadConflictDeadlockDetected',
                    stopped_remotes=stopped_remotes,
                    conflict_remotes=conflict_remotes),
                log_level=logging.ERROR)

        elif timeout_type == TimeoutType.TimeoutNone:
            self.all_threads[cmd_runner].smart_sync(
                targets=targets,
                error_stopped_target=error_stopped_target,
                log_msg=log_msg)

        elif timeout_type == TimeoutType.TimeoutFalse:
            self.all_threads[cmd_runner].smart_sync(
                targets=targets,
                timeout=timeout,
                error_stopped_target=error_stopped_target,
                log_msg=log_msg)

        elif timeout_type == TimeoutType.TimeoutTrue:
            exp_completed_syncs -= stopped_remotes
            exp_completed_syncs -= timeout_remotes
            enter_exit = ('entry',)
            with pytest.raises(st.SmartThreadRequestTimedOut):
                self.all_threads[cmd_runner].smart_sync(
                    targets=targets,
                    timeout=timeout,
                    error_stopped_target=error_stopped_target,
                    log_msg=log_msg)

            self.add_log_msg(
                self.get_error_msg(
                    cmd_runner=cmd_runner,
                    smart_request='smart_sync',
                    targets=targets,
                    error_str='SmartThreadRequestTimedOut',
                    pending_remotes=timeout_remotes,
                    stopped_remotes=stopped_remotes,
                    conflict_remotes=conflict_remotes),
                log_level=logging.ERROR)

        self.add_request_log_msg(cmd_runner=cmd_runner,
                                 smart_request='smart_sync',
                                 targets=targets,
                                 timeout=timeout,
                                 timeout_type=timeout_type,
                                 enter_exit=enter_exit,
                                 log_msg=log_msg)

        self.monitor_event.set()

        if exp_completed_syncs:
            with self.ops_lock:
                self.cmd_waiting_event_items[cmd_runner] = threading.Event()
            self.log_test_msg(
                f'{cmd_runner=} handle_sync waiting for monitor')
            self.monitor_event.set()
            self.cmd_waiting_event_items[cmd_runner].wait()
            with self.ops_lock:
                del self.cmd_waiting_event_items[cmd_runner]

        self.log_test_msg(f'{cmd_runner=} handle_sync exit for '
                          f'{targets=}, {error_stopped_target=}')

    ####################################################################
    # get_request_log_msg
    ####################################################################
    def add_request_log_msg(self,
                            cmd_runner: str,
                            smart_request: str,
                            targets: set[str],
                            timeout: IntOrFloat,
                            timeout_type: TimeoutType,
                            enter_exit: tuple[str, ...],
                            log_msg: Optional[str] = None) -> None:
        """Build and add the request log message.

        Args:
            cmd_runner: thread doing the request
            smart_request: name of smart_request
            targets: target of the smart request
            timeout: timeout value
            timeout_type: None, False, True
            enter_exit: enter and exit or just enter
            log_msg: log message to append

        """
        log_msg_body = re.escape(f'requestor: {cmd_runner} '
                                 f'targets: {sorted(targets)} ')
        if timeout > 0 and timeout_type != TimeoutType.TimeoutNone:
            log_msg_body += f'timeout value: {timeout} '
        else:
            log_msg_body += f'timeout value: None '

        # do not use re.escape for call sequence - it has regex
        log_msg_body += f'{self.log_ver.get_call_seq(smart_request)}'

        if log_msg:
            log_msg_body += f' {re.escape(log_msg)}'

        for enter_exit in enter_exit:
            self.add_log_msg(f'{smart_request} {enter_exit}: {log_msg_body}')

    ####################################################################
    # get_timeout_msg
    ####################################################################
    def get_error_msg(self,
                      cmd_runner: str,
                      smart_request: str,
                      targets: set[str],
                      error_str: str,
                      pending_remotes: Optional[set[str]] = None,
                      stopped_remotes: Optional[set[str]] = None,
                      conflict_remotes: Optional[set[str]] = None,
                      deadlock_remotes: Optional[set[str]] = None
                      ) -> str:
        """Build the timeout message.

        Args:
            cmd_runner: thread doing the request
            smart_request: name of smart_request
            targets: target of the smart request
            error_str: smart_thread error as string
            pending_remotes: names of threads that are pending
            stopped_remotes: names of threads that are stopped
            conflict_remotes: names of sync/wait deadlock threads
            deadlock_remotes: names of wait/wait deadlock threads

        Returns:
            error msg string for log and raise

        """
        targets_msg = re.escape(
            f'while processing a {smart_request} '
            f'request with remotes '
            f'{sorted(targets)}.')

        if not pending_remotes:
            pending_remotes = self.all_threads[
                cmd_runner].request_timeout_names
        pending_msg = re.escape(
            f' Remotes that are pending: '
            f'{sorted(pending_remotes)}.')

        if stopped_remotes:
            stopped_msg = re.escape(
                ' Remotes that are stopped: '
                f'{sorted(stopped_remotes)}.')
        else:
            stopped_msg = ''

        if conflict_remotes:
            if smart_request == 'smart_sync':
                remote_request = 'smart_wait'
            else:
                remote_request = 'smart_sync'
            cr_search = "\[(,| "
            for name in conflict_remotes:
                cr_search += "|'" + name + "'"
            cr_search += ")+\]"
            conflict_msg = (f' Remotes doing a {remote_request} '
                            'request that are deadlocked: '
                            f'{cr_search}.')
        else:
            conflict_msg = ''

        if deadlock_remotes:
            dr_search = "\[(,| "
            for name in deadlock_remotes:
                dr_search += "|'" + name + "'"
            dr_search += ")+\]"
            deadlock_msg = (f' Remotes doing a smart_wait '
                            'request that are deadlocked: '
                            f'{dr_search}.')
        else:
            deadlock_msg = ''

        return (
            f'{cmd_runner} raising {error_str} {targets_msg}'
            f'{pending_msg}{stopped_msg}{conflict_msg}{deadlock_msg}')

    ####################################################################
    # get_timeout_msg
    ####################################################################
    def get_error_ms2(self,
                      cmd_runner: str,
                      smart_request: str,
                      targets: set[str],
                      error_str: str,
                      pending_remotes: Optional[set[str]] = None,
                      stopped_remotes: Optional[set[str]] = None,
                      conflict_remotes: Optional[set[str]] = None,
                      deadlock_remotes: Optional[set[str]] = None
                      ) -> str:
        """Build the timeout message.

        Args:
            cmd_runner: thread doing the request
            smart_request: name of smart_request
            targets: target of the smart request
            error_str: smart_thread error as string
            pending_remotes: names of threads that are pending
            stopped_remotes: names of threads that are stopped
            conflict_remotes: names of sync/wait deadlock threads
            deadlock_remotes: names of wait/wait deadlock threads

        Returns:
            error msg string for log and raise

        """
        targets_msg = (
            f'while processing a {smart_request} '
            f'request with remotes '
            f'{sorted(targets)}.')

        if not pending_remotes:
            pending_remotes = self.all_threads[
                cmd_runner].request_timeout_names
        pending_msg = (
            f' Remotes that are pending: '
            f'{sorted(pending_remotes)}.')

        if stopped_remotes:
            stopped_msg = (
                ' Remotes that are stopped: '
                f'{sorted(stopped_remotes)}.')
        else:
            stopped_msg = ''

        if conflict_remotes:
            if smart_request == 'smart_sync':
                remote_request = 'smart_wait'
            else:
                remote_request = 'smart_sync'
            cr_search = "\[(,| "
            for name in conflict_remotes:
                cr_search += "|'" + name + "'"
            cr_search += ")+\]"
            conflict_msg = (f' Remotes doing a {remote_request} '
                            'request that are deadlocked: '
                            f'{cr_search}.')
        else:
            conflict_msg = ''

        if deadlock_remotes:
            dr_search = "\[(,| "
            for name in deadlock_remotes:
                dr_search += "|'" + name + "'"
            dr_search += ")+\]"
            deadlock_msg = (f' Remotes doing a smart_wait '
                            'request that are deadlocked: '
                            f'{dr_search}.')
        else:
            deadlock_msg = ''

        return (
            f'{cmd_runner} raising {error_str} {targets_msg}'
            f'{pending_msg}{stopped_msg}{conflict_msg}{deadlock_msg}')

    ####################################################################
    # handle_unregister
    ####################################################################
    def handle_unregister(self,
                          cmd_runner: str,
                          unregister_targets: list[str],
                          log_msg: Optional[str] = None) -> None:
        """Unregister the named threads.

        Args:
            cmd_runner: name of thread doing the unregister
            unregister_targets: names of threads to be unregistered
            log_msg: log msg for the unregister request

        """
        self.log_test_msg(f'handle_unregister entry for {cmd_runner=}, '
                          f'{unregister_targets=}')

        self.log_ver.add_call_seq(
            name='unregister',
            seq='test_smart_thread.py::ConfigVerifier.handle_unregister')

        self.all_threads[cmd_runner].unregister(
            targets=set(unregister_targets),
            log_msg=log_msg)

        self.monitor_event.set()

        with self.ops_lock:
            self.cmd_waiting_event_items[cmd_runner] = threading.Event()

        self.log_test_msg(f'{cmd_runner=} handle_unregister waiting for '
                          f'monitor')

        self.add_request_log_msg(cmd_runner=cmd_runner,
                                 smart_request='unregister',
                                 targets=set(unregister_targets),
                                 timeout=0,
                                 timeout_type=TimeoutType.TimeoutNone,
                                 enter_exit=('entry', 'exit'),
                                 log_msg=log_msg)

        self.cmd_waiting_event_items[cmd_runner].wait()
        with self.ops_lock:
            del self.cmd_waiting_event_items[cmd_runner]

        self.log_test_msg(f'handle_unregister exiting: {cmd_runner=}')

    ####################################################################
    # handle_wait
    ####################################################################
    def handle_wait(self,
                    cmd_runner: str,
                    resumers: list[str],
                    timeout: IntOrFloat,
                    timeout_remotes: set[str],
                    stopped_remotes: set[str],
                    conflict_remotes: set[str],
                    deadlock_remotes: set[str],
                    timeout_type: TimeoutType,
                    wait_for: st.WaitFor,
                    error_stopped_target: bool,
                    log_msg: Optional[str] = None) -> None:
        """Wait for a resume.

        Args:
            cmd_runner: thread doing the wait
            resumers: threads doing the resume
            timeout: value to use on smart_wait timeout arg
            timeout_remotes: names of threads that will cause timeout
            stopped_remotes: names of thread that will cause not_alive
            conflict_remotes: names of threads that will cause conflict
            deadlock_remotes: names of threads that will cause deadlock
            timeout_type: specifies None, False, or True
            wait_for: specifies how many resumers to wait for
            error_stopped_target: specifies whether to raise error for a
                stopped resumer
            log_msg: optional log message to specify on the smart_wait

        """
        self.log_test_msg(f'handle_wait entry for {cmd_runner=}, '
                          f'{resumers=}, {stopped_remotes=}, '
                          f'{error_stopped_target=}')

        self.log_ver.add_call_seq(
            name='smart_wait',
            seq='test_smart_thread.py::ConfigVerifier.handle_wait')

        exp_completed_resumers: set[str] = (set(resumers)
                                            - timeout_remotes
                                            - conflict_remotes
                                            - deadlock_remotes
                                            - stopped_remotes)
        enter_exit = ('entry', 'exit')
        if error_stopped_target and stopped_remotes:
            enter_exit = ('entry',)
            with pytest.raises(st.SmartThreadRemoteThreadNotAlive):
                if timeout_type == TimeoutType.TimeoutNone:
                    self.all_threads[cmd_runner].smart_wait(
                        remotes=resumers,
                        wait_for=wait_for,
                        error_stopped_target=error_stopped_target,
                        log_msg=log_msg)
                else:
                    self.all_threads[cmd_runner].smart_wait(
                        remotes=resumers,
                        wait_for=wait_for,
                        timeout=timeout,
                        error_stopped_target=error_stopped_target,
                        log_msg=log_msg)

            self.add_log_msg(
                self.get_error_msg(
                    cmd_runner=cmd_runner,
                    smart_request='smart_wait',
                    targets=set(resumers),
                    error_str='SmartThreadRemoteThreadNotAlive',
                    stopped_remotes=stopped_remotes,
                    conflict_remotes=conflict_remotes),
                log_level=logging.ERROR)

        elif conflict_remotes:
            enter_exit = ('entry',)
            with pytest.raises(st.SmartThreadConflictDeadlockDetected):
                if timeout_type == TimeoutType.TimeoutNone:
                    self.all_threads[cmd_runner].smart_wait(
                        remotes=resumers,
                        wait_for=wait_for,
                        error_stopped_target=error_stopped_target,
                        log_msg=log_msg)
                else:
                    self.all_threads[cmd_runner].smart_wait(
                        remotes=resumers,
                        wait_for=wait_for,
                        timeout=timeout,
                        error_stopped_target=error_stopped_target,
                        log_msg=log_msg)

            self.add_log_msg(
                self.get_error_msg(
                    cmd_runner=cmd_runner,
                    smart_request='smart_wait',
                    targets=set(resumers),
                    error_str='SmartThreadConflictDeadlockDetected',
                    stopped_remotes=stopped_remotes,
                    conflict_remotes=conflict_remotes,
                    deadlock_remotes=deadlock_remotes),
                log_level=logging.ERROR)
        elif deadlock_remotes:
            enter_exit = ('entry',)
            with pytest.raises(st.SmartThreadWaitDeadlockDetected):
                if timeout_type == TimeoutType.TimeoutNone:
                    self.all_threads[cmd_runner].smart_wait(
                        remotes=resumers,
                        wait_for=wait_for,
                        error_stopped_target=error_stopped_target,
                        log_msg=log_msg)
                else:
                    self.all_threads[cmd_runner].smart_wait(
                        remotes=resumers,
                        wait_for=wait_for,
                        timeout=timeout,
                        error_stopped_target=error_stopped_target,
                        log_msg=log_msg)

            self.add_log_msg(
                self.get_error_msg(
                    cmd_runner=cmd_runner,
                    smart_request='smart_wait',
                    targets=set(resumers),
                    error_str='SmartThreadWaitDeadlockDetected',
                    stopped_remotes=stopped_remotes,
                    conflict_remotes=conflict_remotes,
                    deadlock_remotes=deadlock_remotes),
                log_level=logging.ERROR)
        elif timeout_type == TimeoutType.TimeoutNone:
            self.all_threads[cmd_runner].smart_wait(
                remotes=resumers,
                wait_for=wait_for,
                error_stopped_target=error_stopped_target,
                log_msg=log_msg)

        elif timeout_type == TimeoutType.TimeoutFalse:
            self.all_threads[cmd_runner].smart_wait(
                remotes=resumers,
                wait_for=wait_for,
                timeout=timeout,
                error_stopped_target=error_stopped_target,
                log_msg=log_msg)

        elif timeout_type == TimeoutType.TimeoutTrue:
            enter_exit = ('entry',)
            with pytest.raises(st.SmartThreadRequestTimedOut):
                self.all_threads[cmd_runner].smart_wait(
                    remotes=resumers,
                    wait_for=wait_for,
                    timeout=timeout,
                    error_stopped_target=error_stopped_target,
                    log_msg=log_msg)

            self.add_log_msg(
                self.get_error_msg(
                    cmd_runner=cmd_runner,
                    smart_request='smart_wait',
                    targets=set(resumers),
                    error_str='SmartThreadRequestTimedOut',
                    pending_remotes=timeout_remotes,
                    stopped_remotes=stopped_remotes,
                    conflict_remotes=conflict_remotes),
                log_level=logging.ERROR)

        self.add_request_log_msg(cmd_runner=cmd_runner,
                                 smart_request='smart_wait',
                                 targets=set(resumers),
                                 timeout=timeout,
                                 timeout_type=timeout_type,
                                 enter_exit=enter_exit,
                                 log_msg=log_msg)

        for resumer in exp_completed_resumers:
            self.monitor_event.set()
            self.add_log_msg(
                new_log_msg=f'{cmd_runner} smart_wait resumed by {resumer}',
                log_level=logging.INFO)

        if exp_completed_resumers:
            with self.ops_lock:
                self.cmd_waiting_event_items[cmd_runner] = threading.Event()
            self.log_test_msg(
                f'{cmd_runner=} handle_wait waiting for monitor')
            self.monitor_event.set()
            self.cmd_waiting_event_items[cmd_runner].wait()
            with self.ops_lock:
                del self.cmd_waiting_event_items[cmd_runner]

        self.log_test_msg(f'handle_wait exit for {cmd_runner=}, '
                          f'{resumers=}, {stopped_remotes=}, '
                          f'{error_stopped_target=}')

    # ####################################################################
    # # handle_wait
    # ####################################################################
    # def handle_wait(self,
    #                 cmd_runner: str,
    #                 resumers: DictAliveAndStatus,
    #                 wait_for: st.WaitFor,
    #                 error_stopped_target: bool,
    #                 log_msg: Optional[str] = None) -> None:
    #     """Wait for a resume.
    #
    #     Args:
    #         cmd_runner: thread doing the wait
    #         resumers: threads doing the resume
    #         wait_for: specifies how many resumers to wait for
    #         error_stopped_target: specifies whether to raise error for a
    #             stopped resumer
    #         log_msg: optional log message to specify on the smart_wait
    #
    #     """
    #     self.log_test_msg(f'{cmd_runner=} handle_wait entry for '
    #                       f'{resumers=}, {error_stopped_target=}')
    #
    #     self.log_ver.add_call_seq(
    #         name='handle_wait',
    #         seq='test_smart_thread.py::ConfigVerifier.handle_wait')
    #
    #     non_stopped_resumers = set(resumers)
    #     if error_stopped_target:
    #         for resumer in resumers.keys():
    #             if resumers[resumer].status == st.ThreadState.Stopped:
    #                 non_stopped_resumers -= {resumer}
    #
    #     enter_exit = ('entry', 'exit')
    #     for resumer in resumers.keys():
    #         if (error_stopped_target
    #                 and (resumers[resumer].status == st.ThreadState.Stopped)):
    #             with pytest.raises(st.SmartThreadRemoteThreadNotAlive):
    #                 self.all_threads[cmd_runner].smart_wait(
    #                     remotes=resumer,
    #                     wait_for=wait_for,
    #                     error_stopped_target=error_stopped_target,
    #                     log_msg=log_msg)
    #
    #             enter_exit = ('entry', )
    #             if log_msg:
    #                 log_msg_2 = (
    #                     f'{self.log_ver.get_call_seq("handle_wait")} ')
    #                 log_msg_3 = re.escape(f'{log_msg}')
    #                 for enter_exit in enter_exit:
    #                     log_msg_1 = re.escape(
    #                         f'smart_wait() {enter_exit}: '
    #                         f'{cmd_runner} to wait for {resumer}. ')
    #
    #                     self.add_log_msg(log_msg_1 + log_msg_2 + log_msg_3)
    #
    #             self.add_log_msg(
    #                 new_log_msg=re.escape(
    #                     f'{cmd_runner} raising '
    #                     'SmartThreadRemoteThreadNotAlive. '
    #                     f'{cmd_runner} smart_wait is not resumed and '
    #                     f'detected thread {resumer=} has ended.'),
    #                 log_level=logging.ERROR)
    #
    #         else:
    #             self.all_threads[cmd_runner].smart_wait(
    #                 remotes=resumer,
    #                 wait_for=wait_for,
    #                 error_stopped_target=error_stopped_target,
    #                 log_msg=log_msg)
    #
    #             enter_exit = ('entry', 'exit')
    #             if log_msg:
    #                 log_msg_2 = (
    #                     f'{self.log_ver.get_call_seq("handle_wait")} ')
    #                 log_msg_3 = re.escape(f'{log_msg}')
    #                 for enter_exit in enter_exit:
    #                     log_msg_1 = re.escape(
    #                         f'smart_wait() {enter_exit}: '
    #                         f'{cmd_runner} to wait for {resumer}. ')
    #
    #                     self.add_log_msg(log_msg_1 + log_msg_2 + log_msg_3)
    #
    #             self.monitor_event.set()
    #             self.add_log_msg(
    #                 new_log_msg=(f'{cmd_runner} smart_wait resumed by '
    #                              f'{resumer}'),
    #                 log_level=logging.INFO)
    #
    #     if non_stopped_resumers:
    #         with self.ops_lock:
    #             self.cmd_waiting_event_items[cmd_runner] = threading.Event()
    #         self.log_test_msg(
    #             f'{cmd_runner=} handle_wait waiting for monitor')
    #         self.monitor_event.set()
    #         self.cmd_waiting_event_items[cmd_runner].wait()
    #         with self.ops_lock:
    #             del self.cmd_waiting_event_items[cmd_runner]
    #
    #     self.log_test_msg(f'{cmd_runner=} handle_wait exit for '
    #                       f'{resumers=}, {error_stopped_target=}')
    #
    # ####################################################################
    # # handle_wait_tof
    # ####################################################################
    # def handle_wait_tof(self,
    #                     cmd_runner: str,
    #                     resumers: DictAliveAndStatus,
    #                     wait_for: st.WaitFor,
    #                     error_stopped_target: bool,
    #                     timeout: IntOrFloat,
    #                     log_msg: Optional[str] = None) -> None:
    #     """Wait for a resume, timeout specified, timeout not expected.
    #
    #     Args:
    #         cmd_runner: thread doing the wait
    #         resumers: threads doing the resume
    #         wait_for: specifies how many resumers to wait for
    #         error_stopped_target: specifies whether to raise error for a
    #             stopped resumer
    #         timeout: timeout value to specify on the smart_wait
    #         log_msg: optional log message to specify on the smart_wait
    #     """
    #     self.log_test_msg(f'{cmd_runner=} handle_wait_tof entry for '
    #                       f'{resumers=}, {error_stopped_target=}, {timeout=}')
    #
    #     self.log_ver.add_call_seq(
    #         name='handle_wait_tof',
    #         seq='test_smart_thread.py::ConfigVerifier.handle_wait_tof')
    #
    #     non_stopped_resumers = set(resumers)
    #     if error_stopped_target:
    #         for resumer in resumers.keys():
    #             if resumers[resumer].status == st.ThreadState.Stopped:
    #                 non_stopped_resumers -= {resumer}
    #
    #     for resumer in resumers.keys():
    #         if (error_stopped_target
    #                 and (resumers[resumer].status == st.ThreadState.Stopped)):
    #             with pytest.raises(st.SmartThreadRemoteThreadNotAlive):
    #                 self.all_threads[cmd_runner].smart_wait(
    #                     remotes=resumer,
    #                     wait_for=wait_for,
    #                     error_stopped_target=error_stopped_target,
    #                     timeout=timeout,
    #                     log_msg=log_msg
    #                 )
    #
    #             enter_exit = ('entry',)
    #             if log_msg:
    #                 log_msg_2 = (
    #                     f'{self.log_ver.get_call_seq("handle_wait_tof")} ')
    #                 log_msg_3 = re.escape(f'{log_msg}')
    #                 for enter_exit in enter_exit:
    #                     log_msg_1 = re.escape(
    #                         f'smart_wait() {enter_exit}: '
    #                         f'{cmd_runner} to wait for {resumer} with '
    #                         f'{timeout=}. ')
    #
    #                     self.add_log_msg(log_msg_1 + log_msg_2 + log_msg_3)
    #
    #             self.add_log_msg(
    #                 new_log_msg=re.escape(
    #                     f'{cmd_runner} raising '
    #                     'SmartThreadRemoteThreadNotAlive. '
    #                     f'{cmd_runner} smart_wait is not resumed and '
    #                     f'detected thread {resumer=} has ended.'),
    #                 log_level=logging.ERROR)
    #         else:
    #             self.all_threads[cmd_runner].smart_wait(
    #                 remotes=resumer,
    #                 wait_for=wait_for,
    #                 error_stopped_target=error_stopped_target,
    #                 timeout=timeout,
    #                 log_msg=log_msg
    #             )
    #             enter_exit = ('entry', 'exit')
    #             if log_msg:
    #                 log_msg_2 = (
    #                     f'{self.log_ver.get_call_seq("handle_wait_tof")} ')
    #                 log_msg_3 = re.escape(f'{log_msg}')
    #                 for enter_exit in enter_exit:
    #                     log_msg_1 = re.escape(
    #                         f'smart_wait() {enter_exit}: '
    #                         f'{cmd_runner} to wait for {resumer} with '
    #                         f'{timeout=}. ')
    #
    #                     self.add_log_msg(log_msg_1 + log_msg_2 + log_msg_3)
    #
    #             self.monitor_event.set()
    #             self.add_log_msg(
    #                 new_log_msg=(f'{cmd_runner} smart_wait resumed by '
    #                              f'{resumer}'),
    #                 log_level=logging.INFO)
    #
    #     if non_stopped_resumers:
    #         with self.ops_lock:
    #             self.cmd_waiting_event_items[cmd_runner] = threading.Event()
    #         self.log_test_msg(
    #             f'{cmd_runner=} handle_wait_tof waiting for monitor')
    #         self.monitor_event.set()
    #         self.cmd_waiting_event_items[cmd_runner].wait()
    #         with self.ops_lock:
    #             # del self.recv_msg_event_items[cmd_runner]
    #             del self.cmd_waiting_event_items[cmd_runner]
    #
    #     self.log_test_msg(f'{cmd_runner=} handle_wait_tof exit for '
    #                       f'{resumers=}, {error_stopped_target=}, {timeout=}')
    #
    # ####################################################################
    # # handle_wait_tot
    # ####################################################################
    # def handle_wait_tot(self,
    #                     cmd_runner: str,
    #                     resumers: list[str],
    #                     stopped_remotes: set[str],
    #                     timeout_remotes: set[str],
    #                     wait_for: st.WaitFor,
    #                     error_stopped_target: bool,
    #                     timeout: IntOrFloat,
    #                     log_msg: Optional[str] = None
    #                     ) -> None:
    #     """Wait for a resume, timeout specified, timeout expected.
    #
    #     Args:
    #         cmd_runner: thread doing the wait
    #         resumers: threads doing the resume
    #         stopped_remotes: names of threads that are stopped
    #         timeout_remotes: names of remotes that will cause timeout
    #         wait_for: specifies how many resumers to wait for
    #         error_stopped_target: specifies whether to raise error for a
    #             stopped resumer
    #         timeout: timeout value to specify on the smart_wait
    #         log_msg: optional log message to specify on the smart_wait
    #
    #     """
    #     self.log_test_msg(f'{cmd_runner=} handle_wait_tot entry for '
    #                       f'{resumers=}, {error_stopped_target=}, {timeout=}')
    #
    #     self.log_ver.add_call_seq(
    #         name='handle_wait',
    #         seq='test_smart_thread.py::ConfigVerifier.handle_wait')
    #
    #     if error_stopped_target and stopped_remotes:
    #         with pytest.raises(st.SmartThreadRemoteThreadNotAlive):
    #             self.all_threads[cmd_runner].smart_wait(
    #                 remotes=resumers,
    #                 wait_for=wait_for,
    #                 error_stopped_target=error_stopped_target,
    #                 timeout=timeout,
    #                 log_msg=log_msg
    #             )
    #
    #         enter_exit = ('entry', )
    #         if log_msg:
    #             log_msg_2 = (
    #                 f'{self.log_ver.get_call_seq("handle_wait_tot")} ')
    #             log_msg_3 = re.escape(f'{log_msg}')
    #             for enter_exit in enter_exit:
    #                 log_msg_1 = re.escape(
    #                     f'smart_wait() {enter_exit}: '
    #                     f'{cmd_runner} to wait for {resumer} with '
    #                     f'{timeout=}. ')
    #
    #                 self.add_log_msg(log_msg_1 + log_msg_2 + log_msg_3)
    #
    #         self.add_log_msg(
    #             new_log_msg=re.escape(
    #                 f'{cmd_runner} raising '
    #                 'SmartThreadRemoteThreadNotAlive. '
    #                 f'While processing a smart_wait(), '
    #                 f'{cmd_runner} detected that the following '
    #                 f'threads are stopped: {sorted(stopped_remotes)}.'),
    #             log_level=logging.ERROR)
    #     else:
    #         with pytest.raises(st.SmartThreadRequestTimedOut):
    #             self.all_threads[cmd_runner].smart_wait(
    #                 remotes=resumers,
    #                 wait_for=wait_for,
    #                 error_stopped_target=error_stopped_target,
    #                 timeout=timeout,
    #                 log_msg=log_msg
    #             )
    #
    #         enter_exit = ('entry', )
    #         if log_msg:
    #             log_msg_2 = (
    #                 f'{self.log_ver.get_call_seq("handle_wait_tot")} ')
    #             log_msg_3 = re.escape(f'{log_msg}')
    #             for enter_exit in enter_exit:
    #                 log_msg_1 = re.escape(
    #                     f'smart_wait() {enter_exit}: '
    #                     f'{cmd_runner} to wait for {resumer} with '
    #                     f'{timeout=}. ')
    #
    #                 self.add_log_msg(log_msg_1 + log_msg_2 + log_msg_3)
    #
    #         if stopped_remotes:
    #             stopped_msg = (f' Stopped threads: '
    #                            f'{sorted(stopped_remotes)}.')
    #         else:
    #             stopped_msg = ''
    #         self.add_log_msg(re.escape(
    #              f'{cmd_runner} raising '
    #              'SmartThreadRequestTimedOut. '
    #              f'{cmd_runner} timed out on a '
    #              f'smart_wait() request while processing '
    #              f'threads {sorted(timeout_remotes)}.'
    #              f'{stopped_msg}'),
    #             log_level=logging.ERROR)
    #
    #     self.log_test_msg(f'{cmd_runner=} handle_wait_tot exit for '
    #                       f'{resumers=}, {error_stopped_target=}, {timeout=}')

    # ####################################################################
    # # handle_wait_waiting_log_msg
    # ####################################################################
    # def handle_wait_waiting_log_msg(self,
    #                                 cmd_runner: str) -> None:
    #
    #     """Handle the send_cmd execution and log msgs.
    #
    #     Args:
    #         cmd_runner: name of thread doing the cmd
    #
    #     """
    #     self.recv_msg_event_items[cmd_runner].client_event.set()

    ####################################################################
    # inc_ops_count
    ####################################################################
    def inc_ops_count(self, targets: list[str], remote: str) -> None:
        """Increment the pending operations count.

        Args:
            targets: the names of the threads whose count is to be
                       incremented
            remote: the names of the threads that are paired with
                         the targets
        """
        self.log_test_msg(f'inc_ops_count entry: {targets=}, {remote=}')
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
                    ops_count = self.expected_pairs[pair_key][
                        target].pending_ops_count
                    self.log_test_msg(f'inc_ops_count for {pair_key=}, '
                                      f'{target=} set to {ops_count=}')
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
                    ops_count = self.pending_ops_counts[pair_key][target]
                    self.log_test_msg(f'inc_ops_count for {pair_key=}, '
                                      f'{target=} set pending {ops_count=}')

        self.log_test_msg(f'inc_ops_count exit: {targets=}, {remote=}')

    ####################################################################
    # lock_obtain
    ####################################################################
    def lock_obtain(self, cmd_runner: str) -> None:
        """Increment the pending operations count.

        Args:
            cmd_runner: name of thread that will get the lock
        """
        st.SmartThread._registry_lock.obtain_excl(timeout=60)

    ####################################################################
    # lock_obtain
    ####################################################################
    def lock_release(self, cmd_runner: str) -> None:
        """Increment the pending operations count.

        Args:
            cmd_runner: name of thread that will get the lock
        """
        st.SmartThread._registry_lock.release()

    ####################################################################
    # lock_obtain
    ####################################################################
    def lock_swap(self,
                  cmd_runner: str,
                  new_positions: list[str]) -> None:
        """Increment the pending operations count.

        Args:
            cmd_runner: name of thread that will get the lock
            new_positions: the desired positions on the lock queue
        """
        assert len(new_positions) == len(
            st.SmartThread._registry_lock.owner_wait_q)
        with self.ops_lock:
            for idx, pos_name in enumerate(new_positions):
                if (st.SmartThread._registry_lock.owner_wait_q[idx].thread.name
                        != pos_name):
                    save_pos = st.SmartThread._registry_lock.owner_wait_q[idx]
                    # find our desired position
                    new_pos = None
                    # for (idx2, owner_waiter in enumerate(
                    #            st.SmartThread._registry_lock.owner_wait_q)):
                    for idx2 in range(len(
                            st.SmartThread._registry_lock.owner_wait_q)):

                        if (st.SmartThread._registry_lock.owner_wait_q[idx2]
                                .thread.name == pos_name):
                            new_pos = (
                                st.SmartThread._registry_lock.owner_wait_q[
                                    idx2])
                            break
                    assert new_pos is not None
                    st.SmartThread._registry_lock.owner_wait_q[idx] = new_pos
                    st.SmartThread._registry_lock.owner_wait_q[idx2] = save_pos

    ####################################################################
    # lock_verify
    ####################################################################
    def lock_verify(self,
                    cmd_runner: str,
                    exp_positions: list[str],
                    line_num: int) -> None:
        """Increment the pending operations count.

        Args:
            cmd_runner: name of thread that will get the lock
            exp_positions: the expected positions on the lock queue
            line_num: the line number where the cmd was issued
        """
        start_time = time.time()
        timeout_value = 30
        lock_verified = False
        while not lock_verified:
            lock_verified = True  # assume lock will verify
            with self.ops_lock:
                if (len(exp_positions) != len(
                        st.SmartThread._registry_lock.owner_wait_q)):
                    lock_verified = False
                else:
                    for idx, expected_name in enumerate(exp_positions):
                        if (st.SmartThread._registry_lock.owner_wait_q[
                                idx].thread.name != expected_name):
                            lock_verified = False
                            break
                if not lock_verified:
                    time.sleep(0.2)
                    if (time.time() - start_time) > timeout_value:
                        raise FailedLockVerify(
                            f'lock_verify from {line_num=} timed out after'
                            f' {timeout_value} seconds waiting for the '
                            f'{exp_positions=} to match \n'
                            f'{st.SmartThread._registry_lock.owner_wait_q=} ')

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
    # log_test_msg
    ####################################################################
    def log_test_msg(self,
                     log_msg: str) -> None:
        """Issue log msgs for test rtn.

        Args:
            log_msg: the message to log

        """
        self.log_ver.add_msg(log_msg=re.escape(log_msg))
        logger.debug(log_msg, stacklevel=2)

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
                cmd.run_process(cmd_runner=self.commander_name)
                self.completed_cmds[self.commander_name].append(cmd.serial_num)

        self.monitor_exit = True
        self.monitor_event.set()
        self.monitor_thread.join()

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
                     cmd_runner: str,
                     start_names: list[str]) -> None:
        """Start the named thread.

        Args:
            cmd_runner: thread doing the starts
            start_names: names of the threads to start
        """
        self.log_test_msg(f'{cmd_runner=} start_thread entry '
                          f'for {start_names=}')

        # self.started_event_items[cmd_runner] = MonitorEventItem(
        #     client_event=threading.Event(),
        #     deferred_post_needed=False,
        #     targets=start_names.copy()
        # )
        for start_name in start_names:
            self.monitor_event.set()
            self.all_threads[start_name].smart_start()
            # self.expected_registered[start_name].is_alive = True
            # self.expected_registered[
            #     start_name].status = st.ThreadState.Alive
            self.monitor_event.set()

            self.add_log_msg(
                f'{cmd_runner} set status for thread {start_name} '
                'from ThreadStatus.Registered to ThreadStatus.Starting')
            self.add_log_msg(
                f'{cmd_runner} set status for thread {start_name} '
                f'from ThreadStatus.Starting to ThreadStatus.Alive')
            self.add_log_msg(re.escape(
                f'{cmd_runner} started thread {start_name}, '
                'thread.is_alive(): True, status: ThreadStatus.Alive'))

        self.monitor_event.set()
        # start_log_msg = f'{cmd_runner=} start_thread waiting for monitor'
        # self.log_ver.add_msg(log_msg=re.escape(start_log_msg))
        # logger.debug(start_log_msg)

        # waiting forever here means alpha is not the cmd_runner for the
        # start_thread as hard coded in handle_started_log_msg.
        # need to fix that.
        # self.started_event_items[cmd_runner].client_event.wait()

        self.log_test_msg(f'{cmd_runner=} start_thread exiting '
                          f'for {start_names=}')

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
        self.log_test_msg(f'{cmd_runner=} stop_thread entry for {stop_names=}')

        self.stopped_event_items[cmd_runner] = MonitorEventItem(
            client_event=threading.Event(),
            targets=stop_names.copy()
        )

        for stop_name in stop_names:
            self.stopping_names.append(stop_name)
            self.monitor_event.set()
            exit_cmd = ExitThread(cmd_runners=stop_name,
                                  stopped_by=cmd_runner)
            self.add_cmd_info(exit_cmd)
            self.msgs.queue_msg(target=stop_name,
                                msg=exit_cmd)

        work_names = stop_names.copy()
        while work_names:
            for stop_name in work_names:
                if not self.all_threads[stop_name].thread.is_alive():
                    self.log_test_msg(f'{stop_name} has been stopped by '
                                      f'{cmd_runner}')
                    self.monitor_event.set()
                    # with self.ops_lock:
                    #     if stop_name in self.expected_registered:
                    #         self.expected_registered[
                    #             stop_name].is_alive = False
                    work_names.remove(stop_name)
                    break
                time.sleep(0.05)

        self.log_test_msg(f'{cmd_runner=} stop_thread waiting for monitor')
        self.monitor_event.set()
        self.stopped_event_items[cmd_runner].client_event.wait()

        self.log_test_msg(f'{cmd_runner=} stop_thread exiting for '
                          f'{stop_names=}')

    ####################################################################
    # update_pair_array
    ####################################################################
    def update_pair_array_add(self,
                              cmd_runner: str,
                              upa_item: UpaItem) -> None:
        """Unregister the named threads.

        Args:
            cmd_runner: name of thread doing the update
            upa_item: describes what the update is for

        """
        self.log_test_msg(f'update_pair_array_add entry: {cmd_runner=}, '
                          f'{upa_item=}')
        # self.log_test_msg(f'{self.expected_registered.keys()=}')
        # for pair_key in self.expected_pairs.keys():
        #     self.log_test_msg(f'{pair_key} exists in pair_array '
        #                       f'with {self.expected_pairs[pair_key]=}')

        new_name = upa_item.upa_target
        if len(self.expected_registered.keys()) > 1:
            pair_keys = combinations(
                sorted(self.expected_registered.keys()), 2)
            for pair_key in pair_keys:
                if new_name not in pair_key:
                    continue
                if new_name == pair_key[0]:
                    other_name = pair_key[1]
                else:
                    other_name = pair_key[0]
                name_poc = 0
                other_poc = 0
                if pair_key in self.pending_ops_counts:
                    if new_name in self.pending_ops_counts[pair_key]:
                        name_poc = self.pending_ops_counts[
                            pair_key][new_name]
                        self.pending_ops_counts[pair_key][new_name] = 0
                    if other_name in self.pending_ops_counts[pair_key]:
                        other_poc = self.pending_ops_counts[pair_key][
                            other_name]
                        self.pending_ops_counts[pair_key][other_name] = 0

                if pair_key not in self.expected_pairs:
                    self.expected_pairs[pair_key] = {
                        new_name: ThreadPairStatus(
                            pending_ops_count=name_poc),
                        other_name: ThreadPairStatus(
                            pending_ops_count=other_poc)}
                    self.add_log_msg(re.escape(
                        f"{cmd_runner} created "
                        "_refresh_pair_array with "
                        f"pair_key = {pair_key}"))

                    for pair_name in pair_key:
                        self.add_log_msg(re.escape(
                            f"{cmd_runner} added status_blocks entry "
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
                    if new_name in self.expected_pairs[pair_key].keys():
                        self.abort_all_f1_threads()
                        raise InvalidConfigurationDetected(
                            f'{cmd_runner} attempted to add {new_name} to '
                            f'pair array for {pair_key=} that already '
                            'has the thread in the pair array')
                    if new_name == pair_key[0]:
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
                        new_name] = ThreadPairStatus(
                        pending_ops_count=name_poc)
                    self.add_log_msg(re.escape(
                        f"{cmd_runner} added status_blocks entry "
                        f"for pair_key = {pair_key}, "
                        f"name = {new_name}"))

    ####################################################################
    # update_pair_array
    ####################################################################
    def update_pair_array_del(self,
                              cmd_runner: str,
                              upa_item: UpaItem) -> None:
        """Unregister the named threads.

        Args:
            cmd_runner: name of thread doing the update
            upa_item: describes what the update is for

        """
        del_name = upa_item.upa_target
        process = upa_item.upa_process
        pair_keys_to_delete = []
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

            if other_name not in self.expected_pairs[pair_key].keys():
                pair_keys_to_delete.append(pair_key)
            else:
                if self.expected_pairs[pair_key][
                        other_name].pending_ops_count == 0:
                    pair_keys_to_delete.append(pair_key)
                    self.add_log_msg(re.escape(
                        f"{cmd_runner} removed status_blocks entry "
                        f"for pair_key = {pair_key}, "
                        f"name = {other_name}"))
                else:
                    # remember for next update by recv_msg or wait
                    del_def_key = (pair_key, other_name)
                    self.del_deferred_list.append(del_def_key)

                    # best we can do is delete the del_name for now
                    del self.expected_pairs[pair_key][del_name]

            self.add_log_msg(re.escape(
                f"{cmd_runner} removed status_blocks entry "
                f"for pair_key = {pair_key}, "
                f"name = {del_name}"))

        for pair_key in pair_keys_to_delete:
            self.log_test_msg(f'update_pair_array_del for {cmd_runner=}, '
                              f'{del_name=}, {process=} deleted '
                              f'{pair_key=}')

            del self.expected_pairs[pair_key]
            self.add_log_msg(re.escape(
                f'{cmd_runner} removed _pair_array entry'
                f' for pair_key = {pair_key}'))

            # split_msg = self.last_clean_reg_log_msg.split()
            # if (split_msg[0] != cmd_runner
            #         or split_msg[9] != f"['{del_name}']"):
            #     raise FailedToFindLogMsg(f'del_thread {cmd_runner=}, '
            #                              f'{del_name} did not match '
            #                              f'{self.last_clean_reg_log_msg=} ')
            # self.add_log_msg(re.escape(self.last_clean_reg_log_msg))

        self.add_log_msg(f'{cmd_runner} did successful '
                         f'{process} of {del_name}.')

    ####################################################################
    # update_pair_array
    ####################################################################
    def update_pair_array_def_del(self,
                                  cmd_runner: str,
                                  upa_item: UpaItem) -> None:
        """Unregister the named threads.

        Args:
            cmd_runner: name of thread doing the update
            upa_item: describes what the update is for

        """
        def_del_name = upa_item.upa_def_del_name
        target_name = upa_item.upa_target

        # It is possible that the target_name could have been resurrected if
        # an add was done between the time that recv_msg issued the
        # recvd msg log msg its entry to refresh_pair_array. In this
        # case, the updated pair array log message must be for some
        # other update the recv_msg found, such as another deferred
        # delete that was also done between the above mentioned events

        pair_key = st.SmartThread._get_pair_key(def_del_name, target_name)

        if (target_name not in self.expected_registered
                and pair_key in self.expected_pairs
                and target_name not in self.expected_pairs[pair_key].keys()
                and self.expected_pairs[pair_key][
                    def_del_name].pending_ops_count == 0):
            del self.expected_pairs[pair_key]

            self.add_log_msg(re.escape(
                f"{cmd_runner} removed status_blocks entry "
                f"for pair_key = {pair_key}, "
                f"name = {def_del_name}"))

            self.add_log_msg(re.escape(
                f'{cmd_runner} removed _pair_array entry'
                f' for pair_key = {pair_key}'))

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
                    'that is missing from the expected_registry. '
                    f'{self.expected_registered.keys()=}')
            if (self.expected_registered[name].is_alive
                    != thread.thread.is_alive()):
                self.abort_all_f1_threads()
                raise InvalidConfigurationDetected(
                    f'SmartThread registry has entry for name {name} '
                    f'that has is_alive of {thread.thread.is_alive()} '
                    f'which does not match the expected_registered '
                    f'is_alive of {self.expected_registered[name].is_alive}')
            if (self.expected_registered[name].status
                    != thread.st_state):
                self.abort_all_f1_threads()
                raise InvalidConfigurationDetected(
                    f'SmartThread registry has entry for name {name} '
                    f'that has status of {thread.st_state} '
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
                    f'ConfigVerifier found pair_key {pair_key} '
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
                            pair_key].status_blocks[name].msg_q.empty()
                        and not st.SmartThread._pair_array[
                            pair_key].status_blocks[name].wait_event.is_set()
                        and not st.SmartThread._pair_array[
                            pair_key].status_blocks[name].sync_event.is_set()):
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
                if thread.st_state == st.ThreadState.Alive:
                    active_found_real += 1
            else:
                if thread.st_state == st.ThreadState.Registered:
                    registered_found_real += 1
                elif (thread.st_state == st.ThreadState.Alive
                        or thread.st_state == st.ThreadState.Stopped):
                    stopped_found_real += 1

        registered_found_mock = 0
        active_found_mock = 0
        stopped_found_mock = 0
        for name, thread_tracker in self.expected_registered.items():
            if thread_tracker.is_alive:
                if thread_tracker.status == st.ThreadState.Alive:
                    active_found_mock += 1
            else:
                if thread_tracker.status == st.ThreadState.Registered:
                    registered_found_mock += 1
                elif (thread_tracker.status == st.ThreadState.Alive
                        or thread_tracker.status == st.ThreadState.Stopped):
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
    # verify_def_del
    ####################################################################
    def verify_def_del(self,
                       cmd_runner: str,
                       def_del_scenario: DefDelScenario,
                       receiver_names: list[str],
                       sender_names: list[str],
                       waiter_names: list[str],
                       resumer_names: list[str],
                       del_names: list[str],
                       add_names: list[str],
                       deleter_names: list[str],
                       adder_names: list[str]
                       ) -> None:
        """Verify that the given counts are correct.

        Args:
            cmd_runner: name of thread doing the cmd
            def_del_scenario: deferred delete scenario to verify
            receiver_names: names that do recv_msg
            sender_names: names that do send_msg
            waiter_names: names that do smart_wait
            resumer_names: names that do smart_resume
            del_names: names deleted during recv or wait
            add_names: names added during recv or wait
            deleter_names: names that do the delete
            adder_names: names that do the add

        """
        ################################################################
        # start by gathering log messages, both expected and not
        ################################################################
        ################################################################
        # get first config_cmd recv_msg log msg
        ################################################################
        search_msg = ("config_cmd: RecvMsg\(serial=[0-9]+, line=[0-9]+, "
                      f"cmd_runners='{receiver_names[0]}', "
                      f"senders='{sender_names[0]}'\)")

        cc_recv_0_log_msg, cc_recv_0_log_pos = self.get_log_msg(
            search_msg=search_msg,
            skip_num=0,
            start_idx=0,
            # end_idx=log_idx,
            reverse_search=False)

        ################################################################
        # get first wait config_cmd log msg
        ################################################################
        search_msg = ("config_cmd: Wait\(serial=[0-9]+, line=[0-9]+, "
                      f"cmd_runners='{waiter_names[0]}', "
                      f"resumers=")

        cc_wait_0_log_msg, cc_wait_0_log_pos = self.get_log_msg(
            search_msg=search_msg,
            skip_num=0,
            start_idx=0,
            # end_idx=log_idx,
            reverse_search=False)

        # if cc_recv_0_log_msg and cc_wait_0_log_msg:
        #     raise FailedDefDelVerify('verify_def_del found both recv_msg '
        #                              'and wait initial config_cmd log '
        #                              'messages - only one or the other is '
        #                              'expected.'
        #                              f'{cc_recv_0_log_msg=}. '
        #                              f'{cc_wait_0_log_msg=}.')
        if not cc_recv_0_log_msg and not cc_wait_0_log_msg:
            raise FailedDefDelVerify('verify_def_del found neither recv_msg '
                                     'nor wait initial config_cmd log '
                                     'messages - one and only one is '
                                     'expected.')
        if cc_recv_0_log_msg:
            start_log_idx = cc_recv_0_log_pos + 1
        else:
            start_log_idx = cc_wait_0_log_pos + 1

        ################################################################
        # get config_cmd log msg for VerifyDefDel
        ################################################################
        search_msg = ("config_cmd: VerifyDefDel\(serial=[0-9]+, line=[0-9]+, "
                      f"cmd_runners='{self.commander_name}', "
                      f"def_del_scenario=")

        cc_verify_dd_log_msg, cc_verify_dd_log_pos = self.get_log_msg(
            search_msg=search_msg,
            skip_num=0,
            start_idx=start_log_idx,
            # end_idx=log_idx,
            reverse_search=False)

        if not cc_verify_dd_log_msg:
            raise FailedDefDelVerify('verify_def_del failed to find the '
                                     'VerifyDefDel config_cmd log msg')
        end_log_idx = cc_verify_dd_log_pos

        ################################################################
        # get first recv_msg log msg
        ################################################################
        search_msg = (f'{receiver_names[0]} received msg from '
                      f'{sender_names[0]}')

        recv_0_log_msg, recv_0_log_pos = self.get_log_msg(
            search_msg=search_msg,
            skip_num=0,
            start_idx=start_log_idx,
            end_idx=end_log_idx,
            reverse_search=False)

        ################################################################
        # get first recv_msg pair array log msgs found
        ################################################################
        recv_0_pa_msgs_found = self.find_def_del_pair_array_msgs(
            cmd_runner=receiver_names[0],
            deleted_names=[sender_names[0], resumer_names[0]],
            def_del_names=receiver_names + waiter_names,
            start_log_idx=start_log_idx,
            end_log_idx=end_log_idx)

        ################################################################
        # get second recv_msg log msg
        ################################################################
        search_msg = (f'{receiver_names[1]} received msg from '
                      f'{sender_names[0]}')

        recv_1_log_msg, recv_1_log_pos = self.get_log_msg(
            search_msg=search_msg,
            skip_num=0,
            start_idx=start_log_idx,
            end_idx=end_log_idx,
            reverse_search=False)

        ################################################################
        # get second recv_msg pair array log msgs found
        ################################################################
        recv_1_pa_msgs_found = self.find_def_del_pair_array_msgs(
            cmd_runner=receiver_names[1],
            deleted_names=[sender_names[0], resumer_names[0]],
            def_del_names=receiver_names + waiter_names,
            start_log_idx=start_log_idx,
            end_log_idx=end_log_idx)
        ################################################################
        # get first wait log msg
        ################################################################
        search_msg = (f'{waiter_names[0]} smart_wait resumed by '
                      f'{resumer_names[0]}')

        wait_0_log_msg, wait_0_log_pos = self.get_log_msg(
            search_msg=search_msg,
            skip_num=0,
            start_idx=start_log_idx,
            end_idx=end_log_idx,
            reverse_search=False)

        ################################################################
        # get first wait pair array log msgs found
        ################################################################
        wait_0_pa_msgs_found = self.find_def_del_pair_array_msgs(
            cmd_runner=waiter_names[0],
            deleted_names=[sender_names[0], resumer_names[0]],
            def_del_names=receiver_names + waiter_names,
            start_log_idx=start_log_idx,
            end_log_idx=end_log_idx)

        ################################################################
        # get second wait log msg
        ################################################################
        search_msg = (f'{waiter_names[1]} smart_wait resumed by '
                      f'{resumer_names[0]}')

        wait_1_log_msg, wait_1_log_pos = self.get_log_msg(
            search_msg=search_msg,
            skip_num=0,
            start_idx=start_log_idx,
            end_idx=end_log_idx,
            reverse_search=False)

        ################################################################
        # get second wait pair array log msgs found
        ################################################################
        wait_1_pa_msgs_found = self.find_def_del_pair_array_msgs(
            cmd_runner=waiter_names[1],
            deleted_names=[sender_names[0], resumer_names[0]],
            def_del_names=receiver_names + waiter_names,
            start_log_idx=start_log_idx,
            end_log_idx=end_log_idx)

        ################################################################
        # get second wait pair array log msgs found
        ################################################################
        del_pa_msgs_found = self.find_def_del_pair_array_msgs(
            cmd_runner=deleter_names[0],
            deleted_names=[sender_names[0], resumer_names[0]],
            def_del_names=receiver_names + waiter_names,
            start_log_idx=start_log_idx,
            end_log_idx=end_log_idx)

        ################################################################
        # get second wait pair array log msgs found
        ################################################################
        add_pa_msgs_found = self.find_def_del_pair_array_msgs(
            cmd_runner=adder_names[0],
            deleted_names=[sender_names[0], resumer_names[0]],
            def_del_names=receiver_names + waiter_names,
            start_log_idx=start_log_idx,
            end_log_idx=end_log_idx)

        ################################################################
        # verify real variables
        ################################################################
        pair_key_exists: dict[tuple[str, str], bool] = {}
        for deleted_name in sender_names + resumer_names:
            for def_del_name in receiver_names + waiter_names:
                pair_key = st.SmartThread._get_pair_key(name0=deleted_name,
                                                        name1=def_del_name)
                if pair_key in st.SmartThread._pair_array:
                    pair_key_exists[pair_key] = True
                    if pair_key not in self.expected_pairs:
                        raise InvalidConfigurationDetected(
                            f'verify_def_del found {pair_key=} is in real '
                            'pair array but is not in mock pair array')
                else:
                    pair_key_exists[pair_key] = False
                    if pair_key in self.expected_pairs:
                        raise InvalidConfigurationDetected(
                            f'verify_def_del found {pair_key=} is not in '
                            'real pair array but is in mock pair array')

        ################################################################
        # verify for NormalRecv and ResurrectionRecv
        ################################################################
        if (def_del_scenario == DefDelScenario.NormalRecv
                or def_del_scenario == DefDelScenario.ResurrectionRecv):
            if not recv_0_log_msg:
                raise FailedDefDelVerify(
                    f'verify_def_del {def_del_scenario=} failed to find the '
                    'recv_0_log_msg')
            if recv_1_log_msg or wait_0_log_msg or wait_1_log_msg:
                raise FailedDefDelVerify(
                    f'verify_def_del {def_del_scenario=} found an '
                    'unexpected log msg: '
                    f'{recv_1_log_msg=}, '
                    f'{wait_0_log_msg=}, '
                    f'{wait_1_log_msg=}')

            if (recv_0_pa_msgs_found.entered_rpa
                    or recv_0_pa_msgs_found.updated_pa
                    or recv_1_pa_msgs_found.entered_rpa
                    or recv_1_pa_msgs_found.updated_pa
                    or wait_0_pa_msgs_found.entered_rpa
                    or wait_0_pa_msgs_found.updated_pa
                    or wait_1_pa_msgs_found.entered_rpa
                    or wait_1_pa_msgs_found.updated_pa
                    or del_pa_msgs_found.entered_rpa
                    or del_pa_msgs_found.updated_pa
                    or add_pa_msgs_found.entered_rpa
                    or add_pa_msgs_found.updated_pa):
                raise FailedDefDelVerify(
                    f'verify_def_del {def_del_scenario=} found an '
                    'unexpected pair array activity '
                    f'{recv_0_pa_msgs_found.entered_rpa=}, '
                    f'{recv_0_pa_msgs_found.updated_pa=}, '
                    f'{recv_1_pa_msgs_found.updated_pa=}, '
                    f'{wait_0_pa_msgs_found.entered_rpa=}, '
                    f'{wait_0_pa_msgs_found.updated_pa=}, '
                    f'{wait_1_pa_msgs_found.entered_rpa=}, '
                    f'{wait_1_pa_msgs_found.updated_pa=}, '
                    f'{del_pa_msgs_found.entered_rpa=}, ' 
                    f'{del_pa_msgs_found.updated_pa=}, ' 
                    f'{add_pa_msgs_found.entered_rpa=}, ' 
                    f'{add_pa_msgs_found.updated_pa=}')
            if (len(recv_0_pa_msgs_found.removed_sb_entry)
                    or len(recv_0_pa_msgs_found.removed_pa_entry)
                    or len(recv_1_pa_msgs_found.removed_sb_entry)
                    or len(recv_1_pa_msgs_found.removed_pa_entry)
                    or len(wait_0_pa_msgs_found.removed_sb_entry)
                    or len(wait_0_pa_msgs_found.removed_pa_entry)
                    or len(wait_1_pa_msgs_found.removed_sb_entry)
                    or len(wait_1_pa_msgs_found.removed_pa_entry)
                    or len(del_pa_msgs_found.removed_sb_entry)
                    or len(del_pa_msgs_found.removed_pa_entry)
                    or len(add_pa_msgs_found.removed_sb_entry)
                    or len(add_pa_msgs_found.removed_pa_entry)):
                raise FailedDefDelVerify(
                    f'verify_def_del {def_del_scenario=} found an '
                    'unexpected pair array activity '
                    f'{recv_0_pa_msgs_found.removed_sb_entry=}, '
                    f'{recv_0_pa_msgs_found.removed_pa_entry=}, '
                    f'{recv_1_pa_msgs_found.removed_sb_entry=}, '
                    f'{recv_1_pa_msgs_found.removed_pa_entry=}, '
                    f'{wait_0_pa_msgs_found.removed_sb_entry=}, '
                    f'{wait_0_pa_msgs_found.removed_pa_entry=}, '
                    f'{wait_1_pa_msgs_found.removed_sb_entry=}, '
                    f'{wait_1_pa_msgs_found.removed_pa_entry=}, '
                    f'{del_pa_msgs_found.removed_sb_entry=}, '
                    f'{del_pa_msgs_found.removed_pa_entry=}, '
                    f'{add_pa_msgs_found.removed_sb_entry=}, '
                    f'{add_pa_msgs_found.removed_pa_entry=}')

        ################################################################
        # verify for NormalWait and ResurrectionWait
        ################################################################
        if (def_del_scenario == DefDelScenario.NormalWait
                or def_del_scenario == DefDelScenario.ResurrectionWait):
            if not wait_0_log_msg:
                raise FailedDefDelVerify(
                    f'verify_def_del {def_del_scenario=} failed to find the '
                    'recv_0_log_msg')
            if recv_0_log_msg or recv_1_log_msg or wait_1_log_msg:
                raise FailedDefDelVerify(
                    f'verify_def_del {def_del_scenario=} found an '
                    'unexpected log msg: '
                    f'{recv_1_log_msg=}, '
                    f'{wait_0_log_msg=}, '
                    f'{wait_1_log_msg=}')

            if (recv_0_pa_msgs_found.entered_rpa
                    or recv_0_pa_msgs_found.updated_pa
                    or recv_1_pa_msgs_found.entered_rpa
                    or recv_1_pa_msgs_found.updated_pa
                    or wait_0_pa_msgs_found.entered_rpa
                    or wait_0_pa_msgs_found.updated_pa
                    or wait_1_pa_msgs_found.entered_rpa
                    or wait_1_pa_msgs_found.updated_pa
                    or del_pa_msgs_found.entered_rpa
                    or del_pa_msgs_found.updated_pa
                    or add_pa_msgs_found.entered_rpa
                    or add_pa_msgs_found.updated_pa):
                raise FailedDefDelVerify(
                    f'verify_def_del {def_del_scenario=} found an '
                    'unexpected pair array activity '
                    f'{recv_0_pa_msgs_found.entered_rpa=}, '
                    f'{recv_0_pa_msgs_found.updated_pa=}, '
                    f'{recv_1_pa_msgs_found.updated_pa=}, '
                    f'{wait_0_pa_msgs_found.entered_rpa=}, '
                    f'{wait_0_pa_msgs_found.updated_pa=}, '
                    f'{wait_1_pa_msgs_found.entered_rpa=}, '
                    f'{wait_1_pa_msgs_found.updated_pa=}, '
                    f'{del_pa_msgs_found.entered_rpa=}, '
                    f'{del_pa_msgs_found.updated_pa=}, '
                    f'{add_pa_msgs_found.entered_rpa=}, '
                    f'{add_pa_msgs_found.updated_pa=}')

            if (len(recv_0_pa_msgs_found.removed_sb_entry)
                    or len(recv_0_pa_msgs_found.removed_pa_entry)
                    or len(recv_1_pa_msgs_found.removed_sb_entry)
                    or len(recv_1_pa_msgs_found.removed_pa_entry)
                    or len(wait_0_pa_msgs_found.removed_sb_entry)
                    or len(wait_0_pa_msgs_found.removed_pa_entry)
                    or len(wait_1_pa_msgs_found.removed_sb_entry)
                    or len(wait_1_pa_msgs_found.removed_pa_entry)
                    or len(del_pa_msgs_found.removed_sb_entry)
                    or len(del_pa_msgs_found.removed_pa_entry)
                    or len(add_pa_msgs_found.removed_sb_entry)
                    or len(add_pa_msgs_found.removed_pa_entry)):
                raise FailedDefDelVerify(
                    f'verify_def_del {def_del_scenario=} found an '
                    'unexpected pair array activity '
                    f'{recv_0_pa_msgs_found.removed_sb_entry=}, '
                    f'{recv_0_pa_msgs_found.removed_pa_entry=}, '
                    f'{recv_1_pa_msgs_found.removed_sb_entry=}, '
                    f'{recv_1_pa_msgs_found.removed_pa_entry=}, '
                    f'{wait_0_pa_msgs_found.removed_sb_entry=}, '
                    f'{wait_0_pa_msgs_found.removed_pa_entry=}, '
                    f'{wait_1_pa_msgs_found.removed_sb_entry=}, '
                    f'{wait_1_pa_msgs_found.removed_pa_entry=}, '
                    f'{del_pa_msgs_found.removed_sb_entry=}, '
                    f'{del_pa_msgs_found.removed_pa_entry=}, '
                    f'{add_pa_msgs_found.removed_sb_entry=}, '
                    f'{add_pa_msgs_found.removed_pa_entry=}')

        ################################################################
        # verify for Recv0Recv1
        ################################################################
        if def_del_scenario == DefDelScenario.Recv0Recv1:
            if not (recv_0_log_msg and recv_1_log_msg):
                raise FailedDefDelVerify(
                    f'verify_def_del {def_del_scenario=} failed to find the '
                    'one or both recv messages:  '
                    f'{recv_0_log_msg=}, '
                    f'{recv_1_log_msg=}')
            if wait_0_log_msg or wait_1_log_msg:
                raise FailedDefDelVerify(
                    f'verify_def_del {def_del_scenario=} found an '
                    'unexpected log msg: '
                    f'{wait_0_log_msg=}, '
                    f'{wait_1_log_msg=}')

            if ((not recv_0_pa_msgs_found.entered_rpa)
                    or (not recv_0_pa_msgs_found.updated_pa)
                    or (not recv_1_pa_msgs_found.entered_rpa)
                    or recv_1_pa_msgs_found.updated_pa
                    or wait_0_pa_msgs_found.entered_rpa
                    or wait_0_pa_msgs_found.updated_pa
                    or wait_1_pa_msgs_found.entered_rpa
                    or wait_1_pa_msgs_found.updated_pa
                    or del_pa_msgs_found.entered_rpa
                    or del_pa_msgs_found.updated_pa
                    or add_pa_msgs_found.entered_rpa
                    or add_pa_msgs_found.updated_pa):
                raise FailedDefDelVerify(
                    f'verify_def_del {def_del_scenario=} found an '
                    'unexpected pair array activity '
                    f'\n{recv_0_pa_msgs_found.entered_rpa=}, '
                    f'{recv_0_pa_msgs_found.updated_pa=}, '
                    f'\n{recv_1_pa_msgs_found.entered_rpa=}, '
                    f'{recv_1_pa_msgs_found.updated_pa=}, '
                    f'\n{wait_0_pa_msgs_found.entered_rpa=}, '
                    f'{wait_0_pa_msgs_found.updated_pa=}, '
                    f'\n{wait_1_pa_msgs_found.entered_rpa=}, '
                    f'{wait_1_pa_msgs_found.updated_pa=}, '
                    f'\n{del_pa_msgs_found.entered_rpa=}, ' 
                    f'{del_pa_msgs_found.updated_pa=}, ' 
                    f'\n{add_pa_msgs_found.entered_rpa=}, ' 
                    f'{add_pa_msgs_found.updated_pa=}')
            if ((len(recv_0_pa_msgs_found.removed_sb_entry) == 0)
                    or (len(recv_0_pa_msgs_found.removed_pa_entry) == 0)
                    or len(recv_1_pa_msgs_found.removed_sb_entry)
                    or len(recv_1_pa_msgs_found.removed_pa_entry)
                    or len(wait_0_pa_msgs_found.removed_sb_entry)
                    or len(wait_0_pa_msgs_found.removed_pa_entry)
                    or len(wait_1_pa_msgs_found.removed_sb_entry)
                    or len(wait_1_pa_msgs_found.removed_pa_entry)
                    or len(del_pa_msgs_found.removed_sb_entry)
                    or len(del_pa_msgs_found.removed_pa_entry)
                    or len(add_pa_msgs_found.removed_sb_entry)
                    or len(add_pa_msgs_found.removed_pa_entry)):
                raise FailedDefDelVerify(
                    f'verify_def_del {def_del_scenario=} found an '
                    'unexpected pair array activity '
                    f'\n{recv_0_pa_msgs_found.removed_sb_entry=}, '
                    f'{recv_0_pa_msgs_found.removed_pa_entry=}, '
                    f'\n{recv_1_pa_msgs_found.removed_sb_entry=}, '
                    f'{recv_1_pa_msgs_found.removed_pa_entry=}, '
                    f'\n{wait_0_pa_msgs_found.removed_sb_entry=}, '
                    f'{wait_0_pa_msgs_found.removed_pa_entry=}, '
                    f'\n{wait_1_pa_msgs_found.removed_sb_entry=}, '
                    f'{wait_1_pa_msgs_found.removed_pa_entry=}, '
                    f'\n{del_pa_msgs_found.removed_sb_entry=}, '
                    f'{del_pa_msgs_found.removed_pa_entry=}, '
                    f'\n{add_pa_msgs_found.removed_sb_entry=}, '
                    f'{add_pa_msgs_found.removed_pa_entry=}')
            exp_pair_keys: list[tuple[str, str]] = []
            pair_key = st.SmartThread._get_pair_key(name0=sender_names[0],
                                                    name1=receiver_names[0])
            exp_pair_keys.append(pair_key)
            pair_key = st.SmartThread._get_pair_key(name0=sender_names[0],
                                                    name1=receiver_names[1])
            exp_pair_keys.append(pair_key)

            for pair_key in exp_pair_keys:
                if (pair_key not in recv_0_pa_msgs_found.removed_sb_entry
                        or pair_key
                        not in recv_0_pa_msgs_found.removed_pa_entry):
                    raise FailedDefDelVerify(
                        f'verify_def_del {def_del_scenario=} detected '
                        f'that {pair_key=} from {exp_pair_keys=} is missing '
                        f'from {recv_0_pa_msgs_found.removed_sb_entry=} or '
                        f'{recv_0_pa_msgs_found.removed_pa_entry=}')
            for pair_key in recv_0_pa_msgs_found.removed_sb_entry:
                if pair_key not in exp_pair_keys:
                    raise FailedDefDelVerify(
                        f'verify_def_del {def_del_scenario=} detected '
                        f'that {pair_key=} from '
                        f'{recv_0_pa_msgs_found.removed_sb_entry=} is '
                        f'missing from {exp_pair_keys=}')
            for pair_key in recv_0_pa_msgs_found.removed_pa_entry:
                if pair_key not in exp_pair_keys:
                    raise FailedDefDelVerify(
                        f'verify_def_del {def_del_scenario=} detected '
                        f'that {pair_key=} from '
                        f'{recv_0_pa_msgs_found.removed_pa_entry=} is '
                        f'missing from {exp_pair_keys=}')

        ################################################################
        # verify for Recv1Recv0
        ################################################################
        if def_del_scenario == DefDelScenario.Recv1Recv0:
            if not (recv_0_log_msg and recv_1_log_msg):
                raise FailedDefDelVerify(
                    f'verify_def_del {def_del_scenario=} failed to find the '
                    'one or both recv messages:  '
                    f'{recv_0_log_msg=}, '
                    f'{recv_1_log_msg=}')
            if wait_0_log_msg or wait_1_log_msg:
                raise FailedDefDelVerify(
                    f'verify_def_del {def_del_scenario=} found an '
                    'unexpected log msg: '
                    f'{wait_0_log_msg=}, '
                    f'{wait_1_log_msg=}')

            if ((not recv_0_pa_msgs_found.entered_rpa)
                    or recv_0_pa_msgs_found.updated_pa
                    or (not recv_1_pa_msgs_found.entered_rpa)
                    or (not recv_1_pa_msgs_found.updated_pa)
                    or wait_0_pa_msgs_found.entered_rpa
                    or wait_0_pa_msgs_found.updated_pa
                    or wait_1_pa_msgs_found.entered_rpa
                    or wait_1_pa_msgs_found.updated_pa
                    or del_pa_msgs_found.entered_rpa
                    or del_pa_msgs_found.updated_pa
                    or add_pa_msgs_found.entered_rpa
                    or add_pa_msgs_found.updated_pa):
                raise FailedDefDelVerify(
                    f'verify_def_del {def_del_scenario=} found an '
                    'unexpected pair array activity '
                    f'\n{recv_0_pa_msgs_found.entered_rpa=}, '
                    f'{recv_0_pa_msgs_found.updated_pa=}, '
                    f'\n{recv_1_pa_msgs_found.entered_rpa=}, '
                    f'{recv_1_pa_msgs_found.updated_pa=}, '
                    f'\n{wait_0_pa_msgs_found.entered_rpa=}, '
                    f'{wait_0_pa_msgs_found.updated_pa=}, '
                    f'\n{wait_1_pa_msgs_found.entered_rpa=}, '
                    f'{wait_1_pa_msgs_found.updated_pa=}, '
                    f'\n{del_pa_msgs_found.entered_rpa=}, ' 
                    f'{del_pa_msgs_found.updated_pa=}, ' 
                    f'\n{add_pa_msgs_found.entered_rpa=}, ' 
                    f'{add_pa_msgs_found.updated_pa=}')
            if (len(recv_0_pa_msgs_found.removed_sb_entry)
                    or len(recv_0_pa_msgs_found.removed_pa_entry)
                    or (len(recv_1_pa_msgs_found.removed_sb_entry) == 0)
                    or (len(recv_1_pa_msgs_found.removed_pa_entry) == 0)
                    or len(wait_0_pa_msgs_found.removed_sb_entry)
                    or len(wait_0_pa_msgs_found.removed_pa_entry)
                    or len(wait_1_pa_msgs_found.removed_sb_entry)
                    or len(wait_1_pa_msgs_found.removed_pa_entry)
                    or len(del_pa_msgs_found.removed_sb_entry)
                    or len(del_pa_msgs_found.removed_pa_entry)
                    or len(add_pa_msgs_found.removed_sb_entry)
                    or len(add_pa_msgs_found.removed_pa_entry)):
                raise FailedDefDelVerify(
                    f'verify_def_del {def_del_scenario=} found an '
                    'unexpected pair array activity '
                    f'{recv_0_pa_msgs_found.removed_sb_entry=}, '
                    f'{recv_0_pa_msgs_found.removed_pa_entry=}, '
                    f'{recv_1_pa_msgs_found.removed_sb_entry=}, '
                    f'{recv_1_pa_msgs_found.removed_pa_entry=}, '
                    f'{wait_0_pa_msgs_found.removed_sb_entry=}, '
                    f'{wait_0_pa_msgs_found.removed_pa_entry=}, '
                    f'{wait_1_pa_msgs_found.removed_sb_entry=}, '
                    f'{wait_1_pa_msgs_found.removed_pa_entry=}, '
                    f'{del_pa_msgs_found.removed_sb_entry=}, '
                    f'{del_pa_msgs_found.removed_pa_entry=}, '
                    f'{add_pa_msgs_found.removed_sb_entry=}, '
                    f'{add_pa_msgs_found.removed_pa_entry=}')
            exp_pair_keys: list[tuple[str, str]] = []
            pair_key = st.SmartThread._get_pair_key(name0=sender_names[0],
                                                    name1=receiver_names[0])
            exp_pair_keys.append(pair_key)
            pair_key = st.SmartThread._get_pair_key(name0=sender_names[0],
                                                    name1=receiver_names[1])
            exp_pair_keys.append(pair_key)

            for pair_key in exp_pair_keys:
                if (pair_key not in recv_1_pa_msgs_found.removed_sb_entry
                        or pair_key
                        not in recv_1_pa_msgs_found.removed_pa_entry):
                    raise FailedDefDelVerify(
                        f'verify_def_del {def_del_scenario=} detected '
                        f'that {pair_key=} from {exp_pair_keys=} is missing '
                        f'from {recv_1_pa_msgs_found.removed_sb_entry=} or '
                        f'{recv_1_pa_msgs_found.removed_pa_entry=}')
            for pair_key in recv_1_pa_msgs_found.removed_sb_entry:
                if pair_key not in exp_pair_keys:
                    raise FailedDefDelVerify(
                        f'verify_def_del {def_del_scenario=} detected '
                        f'that {pair_key=} from '
                        f'{recv_1_pa_msgs_found.removed_sb_entry=} is '
                        f'missing from {exp_pair_keys=}')
            for pair_key in recv_1_pa_msgs_found.removed_pa_entry:
                if pair_key not in exp_pair_keys:
                    raise FailedDefDelVerify(
                        f'verify_def_del {def_del_scenario=} detected '
                        f'that {pair_key=} from '
                        f'{recv_1_pa_msgs_found.removed_pa_entry=} is '
                        f'missing from {exp_pair_keys=}')

        ################################################################
        # verify for Wait0Wait1
        ################################################################
        if def_del_scenario == DefDelScenario.Wait0Wait1:
            if not (wait_0_log_msg and wait_1_log_msg):
                raise FailedDefDelVerify(
                    f'verify_def_del {def_del_scenario=} failed to find the '
                    'one or both wait messages:  '
                    f'{wait_0_log_msg=}, '
                    f'{wait_1_log_msg=}')
            if recv_0_log_msg or recv_1_log_msg:
                raise FailedDefDelVerify(
                    f'verify_def_del {def_del_scenario=} found an '
                    'unexpected log msg: '
                    f'{recv_0_log_msg=}, '
                    f'{recv_1_log_msg=}')

            if (recv_0_pa_msgs_found.entered_rpa
                    or recv_0_pa_msgs_found.updated_pa
                    or recv_1_pa_msgs_found.entered_rpa
                    or recv_1_pa_msgs_found.updated_pa
                    or (not wait_0_pa_msgs_found.entered_rpa)
                    or (not wait_0_pa_msgs_found.updated_pa)
                    or (not wait_1_pa_msgs_found.entered_rpa)
                    or wait_1_pa_msgs_found.updated_pa
                    or del_pa_msgs_found.entered_rpa
                    or del_pa_msgs_found.updated_pa
                    or add_pa_msgs_found.entered_rpa
                    or add_pa_msgs_found.updated_pa):
                raise FailedDefDelVerify(
                    f'verify_def_del {def_del_scenario=} found an '
                    'unexpected pair array activity '
                    f'{recv_0_pa_msgs_found.entered_rpa=}, '
                    f'{recv_0_pa_msgs_found.updated_pa=}, '
                    f'{recv_1_pa_msgs_found.updated_pa=}, '
                    f'{wait_0_pa_msgs_found.entered_rpa=}, '
                    f'{wait_0_pa_msgs_found.updated_pa=}, '
                    f'{wait_1_pa_msgs_found.entered_rpa=}, '
                    f'{wait_1_pa_msgs_found.updated_pa=}, '
                    f'{del_pa_msgs_found.entered_rpa=}, ' 
                    f'{del_pa_msgs_found.updated_pa=}, ' 
                    f'{add_pa_msgs_found.entered_rpa=}, ' 
                    f'{add_pa_msgs_found.updated_pa=}')
            if (len(recv_0_pa_msgs_found.removed_sb_entry)
                    or len(recv_0_pa_msgs_found.removed_pa_entry)
                    or len(recv_1_pa_msgs_found.removed_sb_entry)
                    or len(recv_1_pa_msgs_found.removed_pa_entry)
                    or (len(wait_0_pa_msgs_found.removed_sb_entry) == 0)
                    or (len(wait_0_pa_msgs_found.removed_pa_entry) == 0)
                    or len(wait_1_pa_msgs_found.removed_sb_entry)
                    or len(wait_1_pa_msgs_found.removed_pa_entry)
                    or len(del_pa_msgs_found.removed_sb_entry)
                    or len(del_pa_msgs_found.removed_pa_entry)
                    or len(add_pa_msgs_found.removed_sb_entry)
                    or len(add_pa_msgs_found.removed_pa_entry)):
                raise FailedDefDelVerify(
                    f'verify_def_del {def_del_scenario=} found an '
                    'unexpected pair array activity '
                    f'{recv_0_pa_msgs_found.removed_sb_entry=}, '
                    f'{recv_0_pa_msgs_found.removed_pa_entry=}, '
                    f'{recv_1_pa_msgs_found.removed_sb_entry=}, '
                    f'{recv_1_pa_msgs_found.removed_pa_entry=}, '
                    f'{wait_0_pa_msgs_found.removed_sb_entry=}, '
                    f'{wait_0_pa_msgs_found.removed_pa_entry=}, '
                    f'{wait_1_pa_msgs_found.removed_sb_entry=}, '
                    f'{wait_1_pa_msgs_found.removed_pa_entry=}, '
                    f'{del_pa_msgs_found.removed_sb_entry=}, '
                    f'{del_pa_msgs_found.removed_pa_entry=}, '
                    f'{add_pa_msgs_found.removed_sb_entry=}, '
                    f'{add_pa_msgs_found.removed_pa_entry=}')
            exp_pair_keys: list[tuple[str, str]] = []
            pair_key = st.SmartThread._get_pair_key(name0=resumer_names[0],
                                                    name1=waiter_names[0])
            exp_pair_keys.append(pair_key)
            pair_key = st.SmartThread._get_pair_key(name0=resumer_names[0],
                                                    name1=waiter_names[1])
            exp_pair_keys.append(pair_key)

            for pair_key in exp_pair_keys:
                if (pair_key not in wait_0_pa_msgs_found.removed_sb_entry
                        or pair_key
                        not in wait_0_pa_msgs_found.removed_pa_entry):
                    raise FailedDefDelVerify(
                        f'verify_def_del {def_del_scenario=} detected '
                        f'that {pair_key=} from {exp_pair_keys=} is missing '
                        f'from {wait_0_pa_msgs_found.removed_sb_entry=} or '
                        f'{wait_0_pa_msgs_found.removed_pa_entry=}')
            for pair_key in wait_0_pa_msgs_found.removed_sb_entry:
                if pair_key not in exp_pair_keys:
                    raise FailedDefDelVerify(
                        f'verify_def_del {def_del_scenario=} detected '
                        f'that {pair_key=} from '
                        f'{wait_0_pa_msgs_found.removed_sb_entry=} is '
                        f'missing from {exp_pair_keys=}')
            for pair_key in wait_0_pa_msgs_found.removed_pa_entry:
                if pair_key not in exp_pair_keys:
                    raise FailedDefDelVerify(
                        f'verify_def_del {def_del_scenario=} detected '
                        f'that {pair_key=} from '
                        f'{wait_0_pa_msgs_found.removed_pa_entry=} is '
                        f'missing from {exp_pair_keys=}')

        ################################################################
        # verify for Wait1Wait0
        ################################################################
        if def_del_scenario == DefDelScenario.Wait1Wait0:
            if not (wait_0_log_msg and wait_1_log_msg):
                raise FailedDefDelVerify(
                    f'verify_def_del {def_del_scenario=} failed to find the '
                    'one or both wait messages:  '
                    f'{wait_0_log_msg=}, '
                    f'{wait_1_log_msg=}')
            if recv_0_log_msg or recv_1_log_msg:
                raise FailedDefDelVerify(
                    f'verify_def_del {def_del_scenario=} found an '
                    'unexpected log msg: '
                    f'{recv_0_log_msg=}, '
                    f'{recv_1_log_msg=}')

            if (recv_0_pa_msgs_found.entered_rpa
                    or recv_0_pa_msgs_found.updated_pa
                    or recv_1_pa_msgs_found.entered_rpa
                    or recv_1_pa_msgs_found.updated_pa
                    or (not wait_0_pa_msgs_found.entered_rpa)
                    or wait_0_pa_msgs_found.updated_pa
                    or (not wait_1_pa_msgs_found.entered_rpa)
                    or (not wait_1_pa_msgs_found.updated_pa)
                    or del_pa_msgs_found.entered_rpa
                    or del_pa_msgs_found.updated_pa
                    or add_pa_msgs_found.entered_rpa
                    or add_pa_msgs_found.updated_pa):
                raise FailedDefDelVerify(
                    f'verify_def_del {def_del_scenario=} found an '
                    'unexpected pair array activity '
                    f'{recv_0_pa_msgs_found.entered_rpa=}, '
                    f'{recv_0_pa_msgs_found.updated_pa=}, '
                    f'{recv_1_pa_msgs_found.updated_pa=}, '
                    f'{wait_0_pa_msgs_found.entered_rpa=}, '
                    f'{wait_0_pa_msgs_found.updated_pa=}, '
                    f'{wait_1_pa_msgs_found.entered_rpa=}, '
                    f'{wait_1_pa_msgs_found.updated_pa=}, '
                    f'{del_pa_msgs_found.entered_rpa=}, ' 
                    f'{del_pa_msgs_found.updated_pa=}, ' 
                    f'{add_pa_msgs_found.entered_rpa=}, ' 
                    f'{add_pa_msgs_found.updated_pa=}')
            if (len(recv_0_pa_msgs_found.removed_sb_entry)
                    or len(recv_0_pa_msgs_found.removed_pa_entry)
                    or len(recv_1_pa_msgs_found.removed_sb_entry)
                    or len(recv_1_pa_msgs_found.removed_pa_entry)
                    or len(wait_0_pa_msgs_found.removed_sb_entry)
                    or len(wait_0_pa_msgs_found.removed_pa_entry)
                    or (len(wait_1_pa_msgs_found.removed_sb_entry) == 0)
                    or (len(wait_1_pa_msgs_found.removed_pa_entry) == 0)
                    or len(del_pa_msgs_found.removed_sb_entry)
                    or len(del_pa_msgs_found.removed_pa_entry)
                    or len(add_pa_msgs_found.removed_sb_entry)
                    or len(add_pa_msgs_found.removed_pa_entry)):
                raise FailedDefDelVerify(
                    f'verify_def_del {def_del_scenario=} found an '
                    'unexpected pair array activity '
                    f'{recv_0_pa_msgs_found.removed_sb_entry=}, '
                    f'{recv_0_pa_msgs_found.removed_pa_entry=}, '
                    f'{recv_1_pa_msgs_found.removed_sb_entry=}, '
                    f'{recv_1_pa_msgs_found.removed_pa_entry=}, '
                    f'{wait_0_pa_msgs_found.removed_sb_entry=}, '
                    f'{wait_0_pa_msgs_found.removed_pa_entry=}, '
                    f'{wait_1_pa_msgs_found.removed_sb_entry=}, '
                    f'{wait_1_pa_msgs_found.removed_pa_entry=}, '
                    f'{del_pa_msgs_found.removed_sb_entry=}, '
                    f'{del_pa_msgs_found.removed_pa_entry=}, '
                    f'{add_pa_msgs_found.removed_sb_entry=}, '
                    f'{add_pa_msgs_found.removed_pa_entry=}')
            exp_pair_keys: list[tuple[str, str]] = []
            pair_key = st.SmartThread._get_pair_key(name0=resumer_names[0],
                                                    name1=waiter_names[0])
            exp_pair_keys.append(pair_key)
            pair_key = st.SmartThread._get_pair_key(name0=resumer_names[0],
                                                    name1=waiter_names[1])
            exp_pair_keys.append(pair_key)

            for pair_key in exp_pair_keys:
                if (pair_key not in wait_1_pa_msgs_found.removed_sb_entry
                        or pair_key
                        not in wait_1_pa_msgs_found.removed_pa_entry):
                    raise FailedDefDelVerify(
                        f'verify_def_del {def_del_scenario=} detected '
                        f'that {pair_key=} from {exp_pair_keys=} is missing '
                        f'from {wait_1_pa_msgs_found.removed_sb_entry=} or '
                        f'{wait_1_pa_msgs_found.removed_pa_entry=}')
            for pair_key in wait_1_pa_msgs_found.removed_sb_entry:
                if pair_key not in exp_pair_keys:
                    raise FailedDefDelVerify(
                        f'verify_def_del {def_del_scenario=} detected '
                        f'that {pair_key=} from '
                        f'{wait_1_pa_msgs_found.removed_sb_entry=} is '
                        f'missing from {exp_pair_keys=}')
            for pair_key in wait_1_pa_msgs_found.removed_pa_entry:
                if pair_key not in exp_pair_keys:
                    raise FailedDefDelVerify(
                        f'verify_def_del {def_del_scenario=} detected '
                        f'that {pair_key=} from '
                        f'{wait_1_pa_msgs_found.removed_pa_entry=} is '
                        f'missing from {exp_pair_keys=}')

        ################################################################
        # verify for RecvWait
        ################################################################
        if def_del_scenario == DefDelScenario.RecvWait:
            if not (recv_0_log_msg and wait_0_log_msg):
                raise FailedDefDelVerify(
                    f'verify_def_del {def_del_scenario=} failed to find the '
                    'one or both wait messages:  '
                    f'{recv_0_log_msg=}, '
                    f'{wait_0_log_msg=}')
            if recv_1_log_msg or wait_1_log_msg:
                raise FailedDefDelVerify(
                    f'verify_def_del {def_del_scenario=} found an '
                    'unexpected log msg: '
                    f'{recv_1_log_msg=}, '
                    f'{wait_1_log_msg=}')

            if ((not recv_0_pa_msgs_found.entered_rpa)
                    or (not recv_0_pa_msgs_found.updated_pa)
                    or recv_1_pa_msgs_found.entered_rpa
                    or recv_1_pa_msgs_found.updated_pa
                    or (not wait_0_pa_msgs_found.entered_rpa)
                    or wait_0_pa_msgs_found.updated_pa
                    or wait_1_pa_msgs_found.entered_rpa
                    or wait_1_pa_msgs_found.updated_pa
                    or del_pa_msgs_found.entered_rpa
                    or del_pa_msgs_found.updated_pa
                    or add_pa_msgs_found.entered_rpa
                    or add_pa_msgs_found.updated_pa):
                raise FailedDefDelVerify(
                    f'verify_def_del {def_del_scenario=} found an '
                    'unexpected pair array activity '
                    f'{recv_0_pa_msgs_found.entered_rpa=}, '
                    f'{recv_0_pa_msgs_found.updated_pa=}, '
                    f'{recv_1_pa_msgs_found.updated_pa=}, '
                    f'{wait_0_pa_msgs_found.entered_rpa=}, '
                    f'{wait_0_pa_msgs_found.updated_pa=}, '
                    f'{wait_1_pa_msgs_found.entered_rpa=}, '
                    f'{wait_1_pa_msgs_found.updated_pa=}, '
                    f'{del_pa_msgs_found.entered_rpa=}, ' 
                    f'{del_pa_msgs_found.updated_pa=}, ' 
                    f'{add_pa_msgs_found.entered_rpa=}, ' 
                    f'{add_pa_msgs_found.updated_pa=}')
            if ((len(recv_0_pa_msgs_found.removed_sb_entry) == 0)
                    or (len(recv_0_pa_msgs_found.removed_pa_entry) == 0)
                    or len(recv_1_pa_msgs_found.removed_sb_entry)
                    or len(recv_1_pa_msgs_found.removed_pa_entry)
                    or len(wait_0_pa_msgs_found.removed_sb_entry)
                    or len(wait_0_pa_msgs_found.removed_pa_entry)
                    or len(wait_1_pa_msgs_found.removed_sb_entry)
                    or len(wait_1_pa_msgs_found.removed_pa_entry)
                    or len(del_pa_msgs_found.removed_sb_entry)
                    or len(del_pa_msgs_found.removed_pa_entry)
                    or len(add_pa_msgs_found.removed_sb_entry)
                    or len(add_pa_msgs_found.removed_pa_entry)):
                raise FailedDefDelVerify(
                    f'verify_def_del {def_del_scenario=} found an '
                    'unexpected pair array activity '
                    f'{recv_0_pa_msgs_found.removed_sb_entry=}, '
                    f'{recv_0_pa_msgs_found.removed_pa_entry=}, '
                    f'{recv_1_pa_msgs_found.removed_sb_entry=}, '
                    f'{recv_1_pa_msgs_found.removed_pa_entry=}, '
                    f'{wait_0_pa_msgs_found.removed_sb_entry=}, '
                    f'{wait_0_pa_msgs_found.removed_pa_entry=}, '
                    f'{wait_1_pa_msgs_found.removed_sb_entry=}, '
                    f'{wait_1_pa_msgs_found.removed_pa_entry=}, '
                    f'{del_pa_msgs_found.removed_sb_entry=}, '
                    f'{del_pa_msgs_found.removed_pa_entry=}, '
                    f'{add_pa_msgs_found.removed_sb_entry=}, '
                    f'{add_pa_msgs_found.removed_pa_entry=}')
            exp_pair_keys: list[tuple[str, str]] = []
            pair_key = st.SmartThread._get_pair_key(name0=sender_names[0],
                                                    name1=receiver_names[0])
            exp_pair_keys.append(pair_key)
            pair_key = st.SmartThread._get_pair_key(name0=resumer_names[0],
                                                    name1=waiter_names[0])
            exp_pair_keys.append(pair_key)

            for pair_key in exp_pair_keys:
                if (pair_key not in recv_0_pa_msgs_found.removed_sb_entry
                        or pair_key
                        not in recv_0_pa_msgs_found.removed_pa_entry):
                    raise FailedDefDelVerify(
                        f'verify_def_del {def_del_scenario=} detected '
                        f'that {pair_key=} from {exp_pair_keys=} is missing '
                        f'from {recv_0_pa_msgs_found.removed_sb_entry=} or '
                        f'{recv_0_pa_msgs_found.removed_pa_entry=}')
            for pair_key in recv_0_pa_msgs_found.removed_sb_entry:
                if pair_key not in exp_pair_keys:
                    raise FailedDefDelVerify(
                        f'verify_def_del {def_del_scenario=} detected '
                        f'that {pair_key=} from '
                        f'{recv_0_pa_msgs_found.removed_sb_entry=} is '
                        f'missing from {exp_pair_keys=}')
            for pair_key in recv_0_pa_msgs_found.removed_pa_entry:
                if pair_key not in exp_pair_keys:
                    raise FailedDefDelVerify(
                        f'verify_def_del {def_del_scenario=} detected '
                        f'that {pair_key=} from '
                        f'{recv_0_pa_msgs_found.removed_pa_entry=} is '
                        f'missing from {exp_pair_keys=}')

        ################################################################
        # verify for WaitRecv
        ################################################################
        if def_del_scenario == DefDelScenario.WaitRecv:
            if not (recv_0_log_msg and wait_0_log_msg):
                raise FailedDefDelVerify(
                    f'verify_def_del {def_del_scenario=} failed to find the '
                    'one or both wait messages:  '
                    f'{recv_0_log_msg=}, '
                    f'{wait_0_log_msg=}')
            if recv_1_log_msg or wait_1_log_msg:
                raise FailedDefDelVerify(
                    f'verify_def_del {def_del_scenario=} found an '
                    'unexpected log msg: '
                    f'{recv_1_log_msg=}, '
                    f'{wait_1_log_msg=}')

            if ((not recv_0_pa_msgs_found.entered_rpa)
                    or recv_0_pa_msgs_found.updated_pa
                    or recv_1_pa_msgs_found.entered_rpa
                    or recv_1_pa_msgs_found.updated_pa
                    or (not wait_0_pa_msgs_found.entered_rpa)
                    or (not wait_0_pa_msgs_found.updated_pa)
                    or wait_1_pa_msgs_found.entered_rpa
                    or wait_1_pa_msgs_found.updated_pa
                    or del_pa_msgs_found.entered_rpa
                    or del_pa_msgs_found.updated_pa
                    or add_pa_msgs_found.entered_rpa
                    or add_pa_msgs_found.updated_pa):
                raise FailedDefDelVerify(
                    f'verify_def_del {def_del_scenario=} found an '
                    'unexpected pair array activity '
                    f'{recv_0_pa_msgs_found.entered_rpa=}, '
                    f'{recv_0_pa_msgs_found.updated_pa=}, '
                    f'{recv_1_pa_msgs_found.updated_pa=}, '
                    f'{wait_0_pa_msgs_found.entered_rpa=}, '
                    f'{wait_0_pa_msgs_found.updated_pa=}, '
                    f'{wait_1_pa_msgs_found.entered_rpa=}, '
                    f'{wait_1_pa_msgs_found.updated_pa=}, '
                    f'{del_pa_msgs_found.entered_rpa=}, ' 
                    f'{del_pa_msgs_found.updated_pa=}, ' 
                    f'{add_pa_msgs_found.entered_rpa=}, ' 
                    f'{add_pa_msgs_found.updated_pa=}')
            if (len(recv_0_pa_msgs_found.removed_sb_entry)
                    or len(recv_0_pa_msgs_found.removed_pa_entry)
                    or len(recv_1_pa_msgs_found.removed_sb_entry)
                    or len(recv_1_pa_msgs_found.removed_pa_entry)
                    or (len(wait_0_pa_msgs_found.removed_sb_entry) == 0)
                    or (len(wait_0_pa_msgs_found.removed_pa_entry) == 0)
                    or len(wait_1_pa_msgs_found.removed_sb_entry)
                    or len(wait_1_pa_msgs_found.removed_pa_entry)
                    or len(del_pa_msgs_found.removed_sb_entry)
                    or len(del_pa_msgs_found.removed_pa_entry)
                    or len(add_pa_msgs_found.removed_sb_entry)
                    or len(add_pa_msgs_found.removed_pa_entry)):
                raise FailedDefDelVerify(
                    f'verify_def_del {def_del_scenario=} found an '
                    'unexpected pair array activity '
                    f'{recv_0_pa_msgs_found.removed_sb_entry=}, '
                    f'{recv_0_pa_msgs_found.removed_pa_entry=}, '
                    f'{recv_1_pa_msgs_found.removed_sb_entry=}, '
                    f'{recv_1_pa_msgs_found.removed_pa_entry=}, '
                    f'{wait_0_pa_msgs_found.removed_sb_entry=}, '
                    f'{wait_0_pa_msgs_found.removed_pa_entry=}, '
                    f'{wait_1_pa_msgs_found.removed_sb_entry=}, '
                    f'{wait_1_pa_msgs_found.removed_pa_entry=}, '
                    f'{del_pa_msgs_found.removed_sb_entry=}, '
                    f'{del_pa_msgs_found.removed_pa_entry=}, '
                    f'{add_pa_msgs_found.removed_sb_entry=}, '
                    f'{add_pa_msgs_found.removed_pa_entry=}')
            exp_pair_keys: list[tuple[str, str]] = []
            pair_key = st.SmartThread._get_pair_key(name0=sender_names[0],
                                                    name1=receiver_names[0])
            exp_pair_keys.append(pair_key)
            pair_key = st.SmartThread._get_pair_key(name0=resumer_names[0],
                                                    name1=waiter_names[0])
            exp_pair_keys.append(pair_key)

            for pair_key in exp_pair_keys:
                if (pair_key not in wait_0_pa_msgs_found.removed_sb_entry
                        or pair_key
                        not in wait_0_pa_msgs_found.removed_pa_entry):
                    raise FailedDefDelVerify(
                        f'verify_def_del {def_del_scenario=} detected '
                        f'that {pair_key=} from {exp_pair_keys=} is missing '
                        f'from {wait_0_pa_msgs_found.removed_sb_entry=} or '
                        f'{wait_0_pa_msgs_found.removed_pa_entry=}')
            for pair_key in wait_0_pa_msgs_found.removed_sb_entry:
                if pair_key not in exp_pair_keys:
                    raise FailedDefDelVerify(
                        f'verify_def_del {def_del_scenario=} detected '
                        f'that {pair_key=} from '
                        f'{wait_0_pa_msgs_found.removed_sb_entry=} is '
                        f'missing from {exp_pair_keys=}')
            for pair_key in wait_0_pa_msgs_found.removed_pa_entry:
                if pair_key not in exp_pair_keys:
                    raise FailedDefDelVerify(
                        f'verify_def_del {def_del_scenario=} detected '
                        f'that {pair_key=} from '
                        f'{wait_0_pa_msgs_found.removed_pa_entry=} is '
                        f'missing from {exp_pair_keys=}')

        ################################################################
        # verify for RecvDel
        ################################################################
        if def_del_scenario == DefDelScenario.RecvDel:
            if not recv_0_log_msg:
                raise FailedDefDelVerify(
                    f'verify_def_del {def_del_scenario=} failed to find the '
                    'recv message:  '
                    f'{recv_0_log_msg=}')
            if recv_1_log_msg or wait_0_log_msg or wait_1_log_msg:
                raise FailedDefDelVerify(
                    f'verify_def_del {def_del_scenario=} found an '
                    'unexpected log msg: '
                    f'{recv_1_log_msg=}, '
                    f'{wait_0_log_msg=}, '
                    f'{wait_1_log_msg=}')

            if ((not recv_0_pa_msgs_found.entered_rpa)
                    or recv_0_pa_msgs_found.updated_pa
                    or recv_1_pa_msgs_found.entered_rpa
                    or recv_1_pa_msgs_found.updated_pa
                    or wait_0_pa_msgs_found.entered_rpa
                    or wait_0_pa_msgs_found.updated_pa
                    or wait_1_pa_msgs_found.entered_rpa
                    or wait_1_pa_msgs_found.updated_pa
                    or (not del_pa_msgs_found.entered_rpa)
                    or (not del_pa_msgs_found.updated_pa)
                    or add_pa_msgs_found.entered_rpa
                    or add_pa_msgs_found.updated_pa):
                raise FailedDefDelVerify(
                    f'verify_def_del {def_del_scenario=} found an '
                    'unexpected pair array activity '
                    f'\n{recv_0_pa_msgs_found.entered_rpa=}, '
                    f'{recv_0_pa_msgs_found.updated_pa=}, '
                    f'\n{recv_1_pa_msgs_found.entered_rpa=}, '
                    f'{recv_1_pa_msgs_found.updated_pa=}, '
                    f'\n{wait_0_pa_msgs_found.entered_rpa=}, '
                    f'{wait_0_pa_msgs_found.updated_pa=}, '
                    f'\n{wait_1_pa_msgs_found.entered_rpa=}, '
                    f'{wait_1_pa_msgs_found.updated_pa=}, '
                    f'\n{del_pa_msgs_found.entered_rpa=}, ' 
                    f'{del_pa_msgs_found.updated_pa=}, ' 
                    f'\n{add_pa_msgs_found.entered_rpa=}, ' 
                    f'{add_pa_msgs_found.updated_pa=}')
            if (len(recv_0_pa_msgs_found.removed_sb_entry)
                    or len(recv_0_pa_msgs_found.removed_pa_entry)
                    or len(recv_1_pa_msgs_found.removed_sb_entry)
                    or len(recv_1_pa_msgs_found.removed_pa_entry)
                    or len(wait_0_pa_msgs_found.removed_sb_entry)
                    or len(wait_0_pa_msgs_found.removed_pa_entry)
                    or len(wait_1_pa_msgs_found.removed_sb_entry)
                    or len(wait_1_pa_msgs_found.removed_pa_entry)
                    or (len(del_pa_msgs_found.removed_sb_entry) == 0)
                    or (len(del_pa_msgs_found.removed_pa_entry) == 0)
                    or len(add_pa_msgs_found.removed_sb_entry)
                    or len(add_pa_msgs_found.removed_pa_entry)):
                raise FailedDefDelVerify(
                    f'verify_def_del {def_del_scenario=} found an '
                    'unexpected pair array activity '
                    f'{recv_0_pa_msgs_found.removed_sb_entry=}, '
                    f'{recv_0_pa_msgs_found.removed_pa_entry=}, '
                    f'{recv_1_pa_msgs_found.removed_sb_entry=}, '
                    f'{recv_1_pa_msgs_found.removed_pa_entry=}, '
                    f'{wait_0_pa_msgs_found.removed_sb_entry=}, '
                    f'{wait_0_pa_msgs_found.removed_pa_entry=}, '
                    f'{wait_1_pa_msgs_found.removed_sb_entry=}, '
                    f'{wait_1_pa_msgs_found.removed_pa_entry=}, '
                    f'{del_pa_msgs_found.removed_sb_entry=}, '
                    f'{del_pa_msgs_found.removed_pa_entry=}, '
                    f'{add_pa_msgs_found.removed_sb_entry=}, '
                    f'{add_pa_msgs_found.removed_pa_entry=}')
            exp_pair_keys: list[tuple[str, str]] = []
            pair_key = st.SmartThread._get_pair_key(name0=sender_names[0],
                                                    name1=receiver_names[0])

            exp_pair_keys.append(pair_key)

            for pair_key in exp_pair_keys:
                if (pair_key not in del_pa_msgs_found.removed_sb_entry
                        or pair_key
                        not in del_pa_msgs_found.removed_pa_entry):
                    raise FailedDefDelVerify(
                        f'verify_def_del {def_del_scenario=} detected '
                        f'that {pair_key=} from {exp_pair_keys=} is missing '
                        f'from {del_pa_msgs_found.removed_sb_entry=} or '
                        f'{del_pa_msgs_found.removed_pa_entry=}')
            for pair_key in del_pa_msgs_found.removed_sb_entry:
                if pair_key not in exp_pair_keys:
                    raise FailedDefDelVerify(
                        f'verify_def_del {def_del_scenario=} detected '
                        f'that {pair_key=} from '
                        f'{del_pa_msgs_found.removed_sb_entry=} is '
                        f'missing from {exp_pair_keys=}')
            for pair_key in del_pa_msgs_found.removed_pa_entry:
                if pair_key not in exp_pair_keys:
                    raise FailedDefDelVerify(
                        f'verify_def_del {def_del_scenario=} detected '
                        f'that {pair_key=} from '
                        f'{del_pa_msgs_found.removed_pa_entry=} is '
                        f'missing from {exp_pair_keys=}')

        ################################################################
        # verify for RecvAdd
        ################################################################
        if def_del_scenario == DefDelScenario.RecvAdd:
            if not recv_0_log_msg:
                raise FailedDefDelVerify(
                    f'verify_def_del {def_del_scenario=} failed to find the '
                    'recv message:  '
                    f'{recv_0_log_msg=}')
            if recv_1_log_msg or wait_0_log_msg or wait_1_log_msg:
                raise FailedDefDelVerify(
                    f'verify_def_del {def_del_scenario=} found an '
                    'unexpected log msg: '
                    f'{recv_1_log_msg=}, '
                    f'{wait_0_log_msg=}, '
                    f'{wait_1_log_msg=}')

            if (not recv_0_pa_msgs_found.entered_rpa
                    or recv_0_pa_msgs_found.updated_pa
                    or recv_1_pa_msgs_found.entered_rpa
                    or recv_1_pa_msgs_found.updated_pa
                    or wait_0_pa_msgs_found.entered_rpa
                    or wait_0_pa_msgs_found.updated_pa
                    or wait_1_pa_msgs_found.entered_rpa
                    or wait_1_pa_msgs_found.updated_pa
                    or del_pa_msgs_found.entered_rpa
                    or del_pa_msgs_found.updated_pa
                    or not add_pa_msgs_found.entered_rpa
                    or not add_pa_msgs_found.updated_pa):
                raise FailedDefDelVerify(
                    f'verify_def_del {def_del_scenario=} found an '
                    'unexpected pair array activity '
                    f'\n{recv_0_pa_msgs_found.entered_rpa=}, '
                    f'{recv_0_pa_msgs_found.updated_pa=}, '
                    f'\n{recv_1_pa_msgs_found.entered_rpa=}, '
                    f'{recv_1_pa_msgs_found.updated_pa=}, '
                    f'\n{wait_0_pa_msgs_found.entered_rpa=}, '
                    f'{wait_0_pa_msgs_found.updated_pa=}, '
                    f'\n{wait_1_pa_msgs_found.entered_rpa=}, '
                    f'{wait_1_pa_msgs_found.updated_pa=}, '
                    f'\n{del_pa_msgs_found.entered_rpa=}, ' 
                    f'{del_pa_msgs_found.updated_pa=}, ' 
                    f'\n{add_pa_msgs_found.entered_rpa=}, ' 
                    f'{add_pa_msgs_found.updated_pa=}')
            if (len(recv_0_pa_msgs_found.removed_sb_entry)
                    or len(recv_0_pa_msgs_found.removed_pa_entry)
                    or len(recv_1_pa_msgs_found.removed_sb_entry)
                    or len(recv_1_pa_msgs_found.removed_pa_entry)
                    or len(wait_0_pa_msgs_found.removed_sb_entry)
                    or len(wait_0_pa_msgs_found.removed_pa_entry)
                    or len(wait_1_pa_msgs_found.removed_sb_entry)
                    or len(wait_1_pa_msgs_found.removed_pa_entry)
                    or len(del_pa_msgs_found.removed_sb_entry)
                    or len(del_pa_msgs_found.removed_pa_entry)
                    or (len(add_pa_msgs_found.removed_sb_entry) == 0)
                    or (len(add_pa_msgs_found.removed_pa_entry) == 0)):
                raise FailedDefDelVerify(
                    f'verify_def_del {def_del_scenario=} found an '
                    'unexpected pair array activity '
                    f'{recv_0_pa_msgs_found.removed_sb_entry=}, '
                    f'{recv_0_pa_msgs_found.removed_pa_entry=}, '
                    f'{recv_1_pa_msgs_found.removed_sb_entry=}, '
                    f'{recv_1_pa_msgs_found.removed_pa_entry=}, '
                    f'{wait_0_pa_msgs_found.removed_sb_entry=}, '
                    f'{wait_0_pa_msgs_found.removed_pa_entry=}, '
                    f'{wait_1_pa_msgs_found.removed_sb_entry=}, '
                    f'{wait_1_pa_msgs_found.removed_pa_entry=}, '
                    f'{del_pa_msgs_found.removed_sb_entry=}, '
                    f'{del_pa_msgs_found.removed_pa_entry=}, '
                    f'{add_pa_msgs_found.removed_sb_entry=}, '
                    f'{add_pa_msgs_found.removed_pa_entry=}')
            exp_pair_keys: list[tuple[str, str]] = []
            pair_key = st.SmartThread._get_pair_key(name0=sender_names[0],
                                                    name1=receiver_names[0])

            exp_pair_keys.append(pair_key)

            for pair_key in exp_pair_keys:
                if (pair_key not in add_pa_msgs_found.removed_sb_entry
                        or pair_key
                        not in add_pa_msgs_found.removed_pa_entry):
                    raise FailedDefDelVerify(
                        f'verify_def_del {def_del_scenario=} detected '
                        f'that {pair_key=} from {exp_pair_keys=} is missing '
                        f'from {add_pa_msgs_found.removed_sb_entry=} or '
                        f'{add_pa_msgs_found.removed_pa_entry=}')
            for pair_key in add_pa_msgs_found.removed_sb_entry:
                if pair_key not in exp_pair_keys:
                    raise FailedDefDelVerify(
                        f'verify_def_del {def_del_scenario=} detected '
                        f'that {pair_key=} from '
                        f'{add_pa_msgs_found.removed_sb_entry=} is '
                        f'missing from {exp_pair_keys=}')
            for pair_key in add_pa_msgs_found.removed_pa_entry:
                if pair_key not in exp_pair_keys:
                    raise FailedDefDelVerify(
                        f'verify_def_del {def_del_scenario=} detected '
                        f'that {pair_key=} from '
                        f'{add_pa_msgs_found.removed_pa_entry=} is '
                        f'missing from {exp_pair_keys=}')

        ################################################################
        # verify for WaitDel
        ################################################################
        if def_del_scenario == DefDelScenario.WaitDel:
            if not wait_0_log_msg:
                raise FailedDefDelVerify(
                    f'verify_def_del {def_del_scenario=} failed to find the '
                    'wait message:  '
                    f'{wait_0_log_msg=}')
            if recv_0_log_msg or recv_1_log_msg or wait_1_log_msg:
                raise FailedDefDelVerify(
                    f'verify_def_del {def_del_scenario=} found an '
                    'unexpected log msg: '
                    f'{recv_0_log_msg=}, '
                    f'{recv_1_log_msg=}, '
                    f'{wait_1_log_msg=}')

            if (recv_0_pa_msgs_found.entered_rpa
                    or recv_0_pa_msgs_found.updated_pa
                    or recv_1_pa_msgs_found.entered_rpa
                    or recv_1_pa_msgs_found.updated_pa
                    or (not wait_0_pa_msgs_found.entered_rpa)
                    or wait_0_pa_msgs_found.updated_pa
                    or wait_1_pa_msgs_found.entered_rpa
                    or wait_1_pa_msgs_found.updated_pa
                    or (not del_pa_msgs_found.entered_rpa)
                    or (not del_pa_msgs_found.updated_pa)
                    or add_pa_msgs_found.entered_rpa
                    or add_pa_msgs_found.updated_pa):
                raise FailedDefDelVerify(
                    f'verify_def_del {def_del_scenario=} found an '
                    'unexpected pair array activity '
                    f'{recv_0_pa_msgs_found.entered_rpa=}, '
                    f'{recv_0_pa_msgs_found.updated_pa=}, '
                    f'{recv_1_pa_msgs_found.updated_pa=}, '
                    f'{wait_0_pa_msgs_found.entered_rpa=}, '
                    f'{wait_0_pa_msgs_found.updated_pa=}, '
                    f'{wait_1_pa_msgs_found.entered_rpa=}, '
                    f'{wait_1_pa_msgs_found.updated_pa=}, '
                    f'{del_pa_msgs_found.entered_rpa=}, ' 
                    f'{del_pa_msgs_found.updated_pa=}, ' 
                    f'{add_pa_msgs_found.entered_rpa=}, ' 
                    f'{add_pa_msgs_found.updated_pa=}')
            if (len(recv_0_pa_msgs_found.removed_sb_entry)
                    or len(recv_0_pa_msgs_found.removed_pa_entry)
                    or len(recv_1_pa_msgs_found.removed_sb_entry)
                    or len(recv_1_pa_msgs_found.removed_pa_entry)
                    or len(wait_0_pa_msgs_found.removed_sb_entry)
                    or len(wait_0_pa_msgs_found.removed_pa_entry)
                    or len(wait_1_pa_msgs_found.removed_sb_entry)
                    or len(wait_1_pa_msgs_found.removed_pa_entry)
                    or (len(del_pa_msgs_found.removed_sb_entry) == 0)
                    or (len(del_pa_msgs_found.removed_pa_entry) == 0)
                    or len(add_pa_msgs_found.removed_sb_entry)
                    or len(add_pa_msgs_found.removed_pa_entry)):
                raise FailedDefDelVerify(
                    f'verify_def_del {def_del_scenario=} found an '
                    'unexpected pair array activity '
                    f'{recv_0_pa_msgs_found.removed_sb_entry=}, '
                    f'{recv_0_pa_msgs_found.removed_pa_entry=}, '
                    f'{recv_1_pa_msgs_found.removed_sb_entry=}, '
                    f'{recv_1_pa_msgs_found.removed_pa_entry=}, '
                    f'{wait_0_pa_msgs_found.removed_sb_entry=}, '
                    f'{wait_0_pa_msgs_found.removed_pa_entry=}, '
                    f'{wait_1_pa_msgs_found.removed_sb_entry=}, '
                    f'{wait_1_pa_msgs_found.removed_pa_entry=}, '
                    f'{del_pa_msgs_found.removed_sb_entry=}, '
                    f'{del_pa_msgs_found.removed_pa_entry=}, '
                    f'{add_pa_msgs_found.removed_sb_entry=}, '
                    f'{add_pa_msgs_found.removed_pa_entry=}')
            exp_pair_keys: list[tuple[str, str]] = []
            pair_key = st.SmartThread._get_pair_key(name0=resumer_names[0],
                                                    name1=waiter_names[0])

            exp_pair_keys.append(pair_key)

            for pair_key in exp_pair_keys:
                if (pair_key not in del_pa_msgs_found.removed_sb_entry
                        or pair_key
                        not in del_pa_msgs_found.removed_pa_entry):
                    raise FailedDefDelVerify(
                        f'verify_def_del {def_del_scenario=} detected '
                        f'that {pair_key=} from {exp_pair_keys=} is missing '
                        f'from {del_pa_msgs_found.removed_sb_entry=} or '
                        f'{del_pa_msgs_found.removed_pa_entry=}')
            for pair_key in del_pa_msgs_found.removed_sb_entry:
                if pair_key not in exp_pair_keys:
                    raise FailedDefDelVerify(
                        f'verify_def_del {def_del_scenario=} detected '
                        f'that {pair_key=} from '
                        f'{del_pa_msgs_found.removed_sb_entry=} is '
                        f'missing from {exp_pair_keys=}')
            for pair_key in del_pa_msgs_found.removed_pa_entry:
                if pair_key not in exp_pair_keys:
                    raise FailedDefDelVerify(
                        f'verify_def_del {def_del_scenario=} detected '
                        f'that {pair_key=} from '
                        f'{del_pa_msgs_found.removed_pa_entry=} is '
                        f'missing from {exp_pair_keys=}')

        ################################################################
        # verify for WaitAdd
        ################################################################
        if def_del_scenario == DefDelScenario.WaitAdd:
            if not wait_0_log_msg:
                raise FailedDefDelVerify(
                    f'verify_def_del {def_del_scenario=} failed to find the '
                    'recv message:  '
                    f'{wait_0_log_msg=}')
            if recv_0_log_msg or recv_1_log_msg or wait_1_log_msg:
                raise FailedDefDelVerify(
                    f'verify_def_del {def_del_scenario=} found an '
                    'unexpected log msg: '
                    f'{recv_0_log_msg=}, '
                    f'{recv_1_log_msg=}, '
                    f'{wait_1_log_msg=}')

            if (recv_0_pa_msgs_found.entered_rpa
                    or recv_0_pa_msgs_found.updated_pa
                    or recv_1_pa_msgs_found.entered_rpa
                    or recv_1_pa_msgs_found.updated_pa
                    or not wait_0_pa_msgs_found.entered_rpa
                    or wait_0_pa_msgs_found.updated_pa
                    or wait_1_pa_msgs_found.entered_rpa
                    or wait_1_pa_msgs_found.updated_pa
                    or del_pa_msgs_found.entered_rpa
                    or del_pa_msgs_found.updated_pa
                    or not add_pa_msgs_found.entered_rpa
                    or not add_pa_msgs_found.updated_pa):
                raise FailedDefDelVerify(
                    f'verify_def_del {def_del_scenario=} found an '
                    'unexpected pair array activity '
                    f'\n{recv_0_pa_msgs_found.entered_rpa=}, '
                    f'{recv_0_pa_msgs_found.updated_pa=}, '
                    f'\n{recv_1_pa_msgs_found.entered_rpa=}, '
                    f'{recv_1_pa_msgs_found.updated_pa=}, '
                    f'\n{wait_0_pa_msgs_found.entered_rpa=}, '
                    f'{wait_0_pa_msgs_found.updated_pa=}, '
                    f'\n{wait_1_pa_msgs_found.entered_rpa=}, '
                    f'{wait_1_pa_msgs_found.updated_pa=}, '
                    f'\n{del_pa_msgs_found.entered_rpa=}, ' 
                    f'{del_pa_msgs_found.updated_pa=}, ' 
                    f'\n{add_pa_msgs_found.entered_rpa=}, ' 
                    f'{add_pa_msgs_found.updated_pa=}')
            if (len(recv_0_pa_msgs_found.removed_sb_entry)
                    or len(recv_0_pa_msgs_found.removed_pa_entry)
                    or len(recv_1_pa_msgs_found.removed_sb_entry)
                    or len(recv_1_pa_msgs_found.removed_pa_entry)
                    or len(wait_0_pa_msgs_found.removed_sb_entry)
                    or len(wait_0_pa_msgs_found.removed_pa_entry)
                    or len(wait_1_pa_msgs_found.removed_sb_entry)
                    or len(wait_1_pa_msgs_found.removed_pa_entry)
                    or len(del_pa_msgs_found.removed_sb_entry)
                    or len(del_pa_msgs_found.removed_pa_entry)
                    or (len(add_pa_msgs_found.removed_sb_entry) == 0)
                    or (len(add_pa_msgs_found.removed_pa_entry) == 0)):
                raise FailedDefDelVerify(
                    f'verify_def_del {def_del_scenario=} found an '
                    'unexpected pair array activity '
                    f'{recv_0_pa_msgs_found.removed_sb_entry=}, '
                    f'{recv_0_pa_msgs_found.removed_pa_entry=}, '
                    f'{recv_1_pa_msgs_found.removed_sb_entry=}, '
                    f'{recv_1_pa_msgs_found.removed_pa_entry=}, '
                    f'{wait_0_pa_msgs_found.removed_sb_entry=}, '
                    f'{wait_0_pa_msgs_found.removed_pa_entry=}, '
                    f'{wait_1_pa_msgs_found.removed_sb_entry=}, '
                    f'{wait_1_pa_msgs_found.removed_pa_entry=}, '
                    f'{del_pa_msgs_found.removed_sb_entry=}, '
                    f'{del_pa_msgs_found.removed_pa_entry=}, '
                    f'{add_pa_msgs_found.removed_sb_entry=}, '
                    f'{add_pa_msgs_found.removed_pa_entry=}')
            exp_pair_keys: list[tuple[str, str]] = []
            pair_key = st.SmartThread._get_pair_key(name0=resumer_names[0],
                                                    name1=waiter_names[0])

            exp_pair_keys.append(pair_key)

            for pair_key in exp_pair_keys:
                if (pair_key not in add_pa_msgs_found.removed_sb_entry
                        or pair_key
                        not in add_pa_msgs_found.removed_pa_entry):
                    raise FailedDefDelVerify(
                        f'verify_def_del {def_del_scenario=} detected '
                        f'that {pair_key=} from {exp_pair_keys=} is missing '
                        f'from {add_pa_msgs_found.removed_sb_entry=} or '
                        f'{add_pa_msgs_found.removed_pa_entry=}')
            for pair_key in add_pa_msgs_found.removed_sb_entry:
                if pair_key not in exp_pair_keys:
                    raise FailedDefDelVerify(
                        f'verify_def_del {def_del_scenario=} detected '
                        f'that {pair_key=} from '
                        f'{add_pa_msgs_found.removed_sb_entry=} is '
                        f'missing from {exp_pair_keys=}')
            for pair_key in add_pa_msgs_found.removed_pa_entry:
                if pair_key not in exp_pair_keys:
                    raise FailedDefDelVerify(
                        f'verify_def_del {def_del_scenario=} detected '
                        f'that {pair_key=} from '
                        f'{add_pa_msgs_found.removed_pa_entry=} is '
                        f'missing from {exp_pair_keys=}')

    ####################################################################
    # find_pair_array_msgs
    ####################################################################
    def find_def_del_pair_array_msgs(self,
                                     cmd_runner: str,
                                     deleted_names: list[str],
                                     def_del_names: list[str],
                                     start_log_idx: int,
                                     end_log_idx: int
                                     ) -> PaLogMsgsFound:
        """Find pair array update log msgs for the given names.

        Args:
            cmd_runner: name of thread doing the pair array updates
            deleted_names: names of threads that were previously deleted
                that caused the def_del_names to be a deferred delete
            def_del_names: names of deferred delete threads
            start_log_idx: index of where to start the log msgs search
            end_log_idx: index where to stop the log msgs search

        Returns:
            a set of bool indicators for which messages were found
        """
        ################################################################
        # find entered refresh pair array log msg
        ################################################################
        search_msg = f'{cmd_runner} entered _refresh_pair_array'

        log_msg, log_pos = self.get_log_msg(
            search_msg=search_msg,
            skip_num=0,
            start_idx=start_log_idx,
            end_idx=end_log_idx,
            reverse_search=False)

        if log_msg:
            entered_rpa_log_msg_found = True
        else:
            entered_rpa_log_msg_found = False

        ################################################################
        # find removed status_blocks entry log msgs
        ################################################################
        found_removed_status_block_msgs: list[tuple[str, str]] = []
        found_removed_pa_entry_msgs: list[tuple[str, str]] = []
        for deleted_name in deleted_names:
            for def_del_name in def_del_names:
                pair_key = st.SmartThread._get_pair_key(name0=deleted_name,
                                                        name1=def_del_name)
                search_msg1 = (f"{cmd_runner} removed status_blocks entry "
                               f"for pair_key = "
                               f"\('{pair_key[0]}', '{pair_key[1]}'\), "
                               f"name = {def_del_name}")
                search_msg2 = (f"{cmd_runner} removed _pair_array entry "
                               f"for pair_key = "
                               f"\('{pair_key[0]}', '{pair_key[1]}'\)")

                log_msg1, log_pos1 = self.get_log_msg(
                    search_msg=search_msg1,
                    skip_num=0,
                    start_idx=start_log_idx,
                    end_idx=end_log_idx,
                    reverse_search=False)

                if log_msg1:
                    found_removed_status_block_msgs.append(pair_key)

                log_msg2, log_pos2 = self.get_log_msg(
                    search_msg=search_msg2,
                    skip_num=0,
                    start_idx=start_log_idx,
                    end_idx=end_log_idx,
                    reverse_search=False)

                if log_msg2:
                    found_removed_pa_entry_msgs.append(pair_key)

        ################################################################
        # get updated pair array log msg
        ################################################################
        search_msg = (f'{cmd_runner} updated _pair_array at UTC '
                      f'{time_match}')

        log_msg, log_pos = self.get_log_msg(
            search_msg=search_msg,
            skip_num=0,
            start_idx=start_log_idx,
            end_idx=end_log_idx,
            reverse_search=False)

        if log_msg:
            upa_log_msg_found = True
        else:
            upa_log_msg_found = False

        return PaLogMsgsFound(
            entered_rpa=entered_rpa_log_msg_found,
            removed_sb_entry=found_removed_status_block_msgs,
            removed_pa_entry=found_removed_pa_entry_msgs,
            updated_pa=upa_log_msg_found)

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
        with self.monitor_condition:
            self.monitor_event.set()
            self.monitor_condition.wait()

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
        with self.monitor_condition:
            self.monitor_event.set()
            self.monitor_condition.wait()

        self.verify_in_registry(cmd_runner=cmd_runner,
                                exp_in_registry_names=exp_active_names)
        self.verify_is_alive(names=exp_active_names)
        self.verify_status(
            cmd_runner=cmd_runner,
            check_status_names=exp_active_names,
            expected_status=st.ThreadState.Alive)
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
        with self.monitor_condition:
            self.monitor_event.set()
            self.monitor_condition.wait()
        with self.monitor_condition:
            self.monitor_event.set()
            self.monitor_condition.wait()
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
            expected_status=st.ThreadState.Registered)
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
                           removed_names: list[str],
                           exp_half_paired_names: list[str]) -> None:
        """Verify that the given names are half paired.

        Args:
            cmd_runner: thread doing the verify
            removed_names: names of the threads that were removed
            exp_half_paired_names: the names that should be in pair array
        """
        for removed_name in removed_names:
            for exp_remaining_name in exp_half_paired_names:
                pair_key = st.SmartThread._get_pair_key(removed_name,
                                                        exp_remaining_name)
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
                if exp_remaining_name not in st.SmartThread._pair_array[
                                pair_key].status_blocks:
                    self.abort_all_f1_threads()
                    raise InvalidConfigurationDetected(
                        f'verify_paired_half found '
                        f'{exp_remaining_name=} does not have a status block '
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
                if exp_remaining_name not in self.expected_pairs[pair_key]:
                    self.abort_all_f1_threads()
                    raise InvalidConfigurationDetected(
                        f'verify_paired_half found '
                        f'{exp_remaining_name=} does not have a status block '
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
                      expected_status: st.ThreadState) -> None:
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
                    if self.all_threads[sender].remotes_unregistered:
                        test_unregs = sorted(
                            self.all_threads[sender].remotes_unregistered)
                    if self.all_threads[sender].remotes_full_send_q:
                        test_fullqs = sorted(
                            self.all_threads[sender].remotes_full_send_q)

                if unregs == test_unregs and fullqs == test_fullqs:
                    work_senders.remove(sender)

            time.sleep(0.1)
            assert time.time() < start_time + 30  # allow 30 seconds

    ####################################################################
    # wait_for_resume_timeouts
    ####################################################################
    def wait_for_resume_timeouts(self,
                                 cmd_runner: str,
                                 resumer_names: list[str],
                                 timeout_names: list[str]) -> None:
        """Verify that the resumers have detected the timeout threads.

        Args:
            cmd_runner: thread doing the wait
            resumer_names: names of threads doing the resumes
            timeout_names: names of the threads to check for timeout

        """
        timeouts: set[str] = set()
        if timeout_names:
            timeouts = set(sorted(timeout_names))

        work_resumers = resumer_names.copy()
        start_time = time.time()
        while work_resumers:
            for resumer in work_resumers:
                test_timeouts = set(sorted(self.all_threads[
                                resumer].resume_timeout_names))
                if timeouts == test_timeouts:
                    work_resumers.remove(resumer)
                    break

            time.sleep(0.1)
            if start_time + 30 < time.time():
                raise CmdTimedOut('wait_for_resume_timeouts timed out '
                                  f'with {work_resumers=}, '
                                  f'{timeouts=}, {sorted(test_timeouts)=}')

    ####################################################################
    # wait_for_sync_timeouts
    ####################################################################
    def wait_for_sync_timeouts(self,
                                 cmd_runner: str,
                                 syncer_names: list[str],
                                 timeout_names: list[str]) -> None:
        """Verify that the resumers have detected the timeout threads.

        Args:
            cmd_runner: thread doing the check
            syncer_names: names doing the sync
            timeout_names: names of the threads to check for timeout

        """
        timeouts: set[str] = set()
        if timeout_names:
            timeouts = set(sorted(timeout_names))

        work_syncers = syncer_names.copy()
        start_time = time.time()
        while work_syncers:
            for syncer in work_syncers:
                test_timeouts = set(sorted(self.all_threads[
                                syncer].sync_timeout_names))
                if timeouts == test_timeouts:
                    work_syncers.remove(syncer)
                    break

            time.sleep(0.1)
            if start_time + 30 < time.time():
                raise CmdTimedOut('wait_for_sync_timeouts timed out '
                                  f'with {work_syncers=}, '
                                  f'{timeouts=}, {test_timeouts=}')
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
            max_msgs: max number of messages for msg_q

        """
        super().__init__()
        threading.current_thread().name = name
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
            new_status=st.ThreadState.Alive)
        name = self.smart_thread.name
        self.config_ver.add_log_msg(
            f'{name} set status for thread {name} from '
            'ThreadStatus.Registered to ThreadStatus.Alive'
        )

        self.config_ver.main_driver()


########################################################################
# OuterSmartThreadApp class
########################################################################
class OuterSmartThreadApp(st.SmartThread, threading.Thread):
    """Outer thread app for test with both thread and SmartThread."""
    def __init__(self,
                 config_ver: ConfigVerifier,
                 name: str,
                 max_msgs: int
                 ) -> None:
        """Initialize the object.

        Args:
            config_ver: configuration verifier and test support methods
            name: name of thread
            max_msgs: max number of messages for msg_q

        """
        # super().__init__()
        threading.Thread.__init__(self)
        threading.current_thread().name = name
        st.SmartThread.__init__(
            self,
            name=name,
            thread=self,
            auto_start=False,
            max_msgs=max_msgs)
        self.config_ver = config_ver
        self.config_ver.commander_thread = self

    def run(self) -> None:
        """Run the test."""
        self._set_status(
            target_thread=self,
            new_status=st.ThreadState.Alive)
        self.config_ver.main_driver()


########################################################################
# OuterSmartThreadApp2 class
########################################################################
class OuterSmartThreadApp2(threading.Thread, st.SmartThread):
    """Outer thread app for test with both thread and SmartThread."""
    def __init__(self,
                 config_ver: ConfigVerifier,
                 name: str,
                 max_msgs: int
                 ) -> None:
        """Initialize the object.

        Args:
            config_ver: configuration verifier and test support methods
            name: name of thread
            max_msgs: max number of messages for msg_q

        """
        # super().__init__()
        threading.Thread.__init__(self)
        threading.current_thread().name = name
        st.SmartThread.__init__(
            self,
            name=name,
            thread=self,
            auto_start=False,
            max_msgs=max_msgs)
        self.config_ver = config_ver
        self.config_ver.commander_thread = self

    def run(self) -> None:
        """Run the test."""
        self._set_status(
            target_thread=self,
            new_status=st.ThreadState.Alive)
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
            self.smart_thread.smart_start()

    def run(self) -> None:
        """Run the test."""
        log_msg_f1 = f'OuterF1ThreadApp.run() entry: {self.smart_thread.name=}'
        self.config_ver.log_ver.add_msg(log_msg=re.escape(log_msg_f1))
        logger.debug(log_msg_f1)

        self.config_ver.f1_driver(f1_name=self.smart_thread.name)
        # stopped_by = self.config_ver.expected_registered[
        #     self.smart_thread.name].stopped_by
        #
        # log_msg_f1 = (f'{self.smart_thread.name} has been '
        #               f'stopped by {stopped_by}')
        # self.config_ver.log_ver.add_msg(log_msg=log_msg_f1)
        # logger.debug(log_msg_f1)
        # self.config_ver.monitor_event.set()

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
        args_for_scenario_builder: dict[str, Any] = {}

        self.scenario_driver(
            scenario_builder=ConfigVerifier.build_simple_scenario,
            scenario_builder_args=args_for_scenario_builder,
            caplog_to_use=caplog,
            commander_config=commander_config_arg)

    ####################################################################
    # test_config_build_scenarios
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
    # test_join_timeout_scenarios
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
    # test_def_del_scenarios
    ####################################################################
    def test_def_del_scenarios(
            self,
            def_del_scenario_arg: DefDelScenario,
            caplog: pytest.CaptureFixture[str]
    ) -> None:
        """Test meta configuration scenarios.

        Args:
            def_del_scenario_arg: specifies the type of test to do
            caplog: pytest fixture to capture log output

        """
        command_config_num = def_del_scenario_arg.value % 5
        if command_config_num == 0:
            commander_config = AppConfig.ScriptStyle
        elif command_config_num == 1:
            commander_config = AppConfig.CurrentThreadApp
        elif command_config_num == 2:
            commander_config = AppConfig.RemoteThreadApp
        elif command_config_num == 3:
            commander_config = AppConfig.RemoteSmartThreadApp
        else:
            commander_config = AppConfig.RemoteSmartThreadApp2

        args_for_scenario_builder: dict[str, Any] = {
            'def_del_scenario': def_del_scenario_arg
        }

        self.scenario_driver(
            scenario_builder=ConfigVerifier.build_def_del_suite,
            scenario_builder_args=args_for_scenario_builder,
            caplog_to_use=caplog,
            commander_config=commander_config
        )

    ####################################################################
    # test_recv_msg_timeout_scenarios
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
        total_arg_counts = (
                num_active_no_delay_senders_arg
                + num_active_delay_senders_arg
                + num_send_exit_senders_arg
                + num_nosend_exit_senders_arg
                + num_unreg_senders_arg
                + num_reg_senders_arg)
        if timeout_type_arg == TimeoutType.TimeoutNone:
            if total_arg_counts == 0:
                return
        else:
            if (num_active_delay_senders_arg
                    + num_nosend_exit_senders_arg
                    + num_unreg_senders_arg
                    + num_reg_senders_arg) == 0:
                return

        command_config_num = total_arg_counts % 5
        if command_config_num == 0:
            commander_config = AppConfig.ScriptStyle
        elif command_config_num == 1:
            commander_config = AppConfig.CurrentThreadApp
        elif command_config_num == 2:
            commander_config = AppConfig.RemoteThreadApp
        elif command_config_num == 3:
            commander_config = AppConfig.RemoteSmartThreadApp
        else:
            commander_config = AppConfig.RemoteSmartThreadApp2

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
            caplog_to_use=caplog,
            commander_config=commander_config
        )

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

        command_config_num = total_arg_counts % 5
        if command_config_num == 0:
            commander_config = AppConfig.ScriptStyle
        elif command_config_num == 1:
            commander_config = AppConfig.CurrentThreadApp
        elif command_config_num == 2:
            commander_config = AppConfig.RemoteThreadApp
        elif command_config_num == 3:
            commander_config = AppConfig.RemoteSmartThreadApp
        else:
            commander_config = AppConfig.RemoteSmartThreadApp2

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
    # test_resume_timeout_scenarios
    ####################################################################
    def test_resume_timeout_scenarios(
            self,
            timeout_type_arg: TimeoutType,
            num_resumers_arg: int,
            num_active_arg: int,
            num_registered_before_arg: int,
            num_registered_after_arg: int,
            num_unreg_no_delay_arg: int,
            num_unreg_delay_arg: int,
            num_stopped_no_delay_arg: int,
            num_stopped_delay_arg: int,
            caplog: pytest.CaptureFixture[str]
    ) -> None:
        """Test meta configuration scenarios.

        Args:
            timeout_type_arg: specifies whether to issue the resume with
                timeout, and is so whether the resume should timeout
                or, by starting exited threads in time, not timeout
            num_resumers_arg: number of threads doing resumes
            num_active_arg: number threads active, thus no timeout
            num_registered_before_arg: number threads registered, thus
                no timeout, issued before the resume is issued
            num_registered_after_arg: number threads registered, thus no
                timeout, issued after the resume is issued
            num_unreg_no_delay_arg: number threads unregistered before
                the resume is done, and are then created and started
                within the allowed timeout
            num_unreg_delay_arg: number threads unregistered before the
                resume is done, and are then created and started after
                the allowed timeout
            num_stopped_no_delay_arg: number of threads stopped before the resume
                and cause a timeout
            num_stopped_delay_arg: number of threads stopped
                before the resume and are then joined, created, and
                started within the allowed timeout
            caplog: pytest fixture to capture log output

        """
        total_arg_counts = (
                num_active_arg
                + num_registered_before_arg
                + num_registered_after_arg
                + num_unreg_no_delay_arg
                + num_unreg_delay_arg
                + num_stopped_no_delay_arg
                + num_stopped_delay_arg)
        if timeout_type_arg == TimeoutType.TimeoutNone:
            if total_arg_counts == 0:
                return
        else:
            if (num_unreg_delay_arg + num_stopped_delay_arg) == 0:
                return

        command_config_num = total_arg_counts % 5
        if command_config_num == 0:
            commander_config = AppConfig.ScriptStyle
        elif command_config_num == 1:
            commander_config = AppConfig.CurrentThreadApp
        elif command_config_num == 2:
            commander_config = AppConfig.RemoteThreadApp
        elif command_config_num == 3:
            commander_config = AppConfig.RemoteSmartThreadApp
        else:
            commander_config = AppConfig.RemoteSmartThreadApp2

        args_for_scenario_builder: dict[str, Any] = {
            'timeout_type': timeout_type_arg,
            'num_resumers': num_resumers_arg,
            'num_active': num_active_arg,
            'num_registered_before': num_registered_before_arg,
            'num_registered_after': num_registered_after_arg,
            'num_unreg_no_delay': num_unreg_no_delay_arg,
            'num_unreg_delay': num_unreg_delay_arg,
            'num_stopped_no_delay': num_stopped_no_delay_arg,
            'num_stopped_delay': num_stopped_delay_arg
        }

        self.scenario_driver(
            scenario_builder=ConfigVerifier.build_resume_timeout_suite,
            scenario_builder_args=args_for_scenario_builder,
            caplog_to_use=caplog,
            commander_config=commander_config)

    ####################################################################
    # test_wait_timeout_scenarios
    ####################################################################
    def test_wait_scenarios(
            self,
            num_waiters_arg: int,
            num_actors_arg: int,
            actor_1_arg: Actors,
            actor_2_arg: Actors,
            actor_3_arg: Actors,
            caplog: pytest.CaptureFixture[str]
    ) -> None:
        """Test wait scenarios.

        Args:
            num_waiters_arg: number of threads that will do the wait
            num_actors_arg: number of actor threads
            actor_1_arg: type of actor that will do the first resume
            actor_2_arg: type of actor that will do the second resume
            actor_3_arg: type of actor that will do the third resume
            caplog: pytest fixture to capture log output

        """
        total_arg_counts = (
                num_waiters_arg
                + num_actors_arg)

        command_config_num = total_arg_counts % 5
        if command_config_num == 0:
            commander_config = AppConfig.ScriptStyle
        elif command_config_num == 1:
            commander_config = AppConfig.CurrentThreadApp
        elif command_config_num == 2:
            commander_config = AppConfig.RemoteThreadApp
        elif command_config_num == 3:
            commander_config = AppConfig.RemoteSmartThreadApp
        else:
            commander_config = AppConfig.RemoteSmartThreadApp2

        # args_for_scenario_builder: dict[str, Any] = {
        #     'num_waiters': num_waiters_arg,
        #     'actor_list': [(actor_1_arg, num_actor_1_arg),
        #                    (actor_2_arg, num_actor_2_arg),
        #                    (actor_3_arg, num_actor_3_arg)]
        # }
        args_for_scenario_builder: dict[str, Any] = {
            'num_waiters': num_waiters_arg,
            'num_actors': num_actors_arg,
            'actor_list': [actor_1_arg, actor_2_arg, actor_3_arg,]
        }

        self.scenario_driver(
            scenario_builder=ConfigVerifier.build_wait_scenario_suite,
            scenario_builder_args=args_for_scenario_builder,
            caplog_to_use=caplog,
            commander_config=commander_config
        )

    ####################################################################
    # test_sync_scenarios
    ####################################################################
    def test_sync_scenarios(
            self,
            timeout_type_arg: TimeoutType,
            num_syncers_arg: int,
            num_stopped_syncers_arg: int,
            num_timeout_syncers_arg: int,
            error_stopped_target_arg: bool,
            caplog: pytest.CaptureFixture[str]
    ) -> None:
        """Test smart_sync scenarios.

        Args:
            timeout_type_arg: timeout for None, False, or True
            num_syncers_arg: number of threads that will successfully
                sync
            num_stopped_syncers_arg: number of threads that will
                cause a not alive error
            num_timeout_syncers_arg: number of threads that will
                cause a timeout error
            error_stopped_target_arg: specifies whether to raise not alive
                for stopped syncers
            caplog: pytest fixture to capture log output

        """
        total_arg_counts = (
                num_syncers_arg
                + num_stopped_syncers_arg
                + num_timeout_syncers_arg)

        if total_arg_counts < 2:  # we need at least two to sync
            return

        if (timeout_type_arg == TimeoutType.TimeoutTrue
                and ((num_stopped_syncers_arg
                     + num_timeout_syncers_arg) == 0)):
            return

        command_config_num = total_arg_counts % 5
        if command_config_num == 0:
            commander_config = AppConfig.ScriptStyle
        elif command_config_num == 1:
            commander_config = AppConfig.CurrentThreadApp
        elif command_config_num == 2:
            commander_config = AppConfig.RemoteThreadApp
        elif command_config_num == 3:
            commander_config = AppConfig.RemoteSmartThreadApp
        else:
            commander_config = AppConfig.RemoteSmartThreadApp2

        args_for_scenario_builder: dict[str, Any] = {
            'timeout_type': timeout_type_arg,
            'num_syncers': num_syncers_arg,
            'num_stopped_syncers': num_stopped_syncers_arg,
            'num_timeout_syncers': num_timeout_syncers_arg,
            'error_stopped_target': error_stopped_target_arg
        }

        self.scenario_driver(
            scenario_builder=ConfigVerifier.build_sync_scenario_suite,
            scenario_builder_args=args_for_scenario_builder,
            caplog_to_use=caplog,
            commander_config=commander_config
        )

    ####################################################################
    # test_deadlock_conflict_scenarios
    ####################################################################
    def test_conflict_deadlock_scenarios(
            self,
            conflict_deadlock_1_arg: ConflictDeadlockScenario,
            conflict_deadlock_2_arg: ConflictDeadlockScenario,
            conflict_deadlock_3_arg: ConflictDeadlockScenario,
            num_cd_actors_arg: int,
            caplog: pytest.CaptureFixture[str]
    ) -> None:
        """Test smart_sync scenarios.

        Args:
            conflict_deadlock_1_arg: first scenario
            conflict_deadlock_2_arg: second scenario
            conflict_deadlock_3_arg: third scenario
            num_cd_actors_arg: number syncers, resumers, and waiters
            caplog: pytest fixture to capture log output

        """
        command_config_num = num_cd_actors_arg % 5
        if command_config_num == 0:
            commander_config = AppConfig.ScriptStyle
        elif command_config_num == 1:
            commander_config = AppConfig.CurrentThreadApp
        elif command_config_num == 2:
            commander_config = AppConfig.RemoteThreadApp
        elif command_config_num == 3:
            commander_config = AppConfig.RemoteSmartThreadApp
        else:
            commander_config = AppConfig.RemoteSmartThreadApp2

        args_for_scenario_builder: dict[str, Any] = {
            'scenario_list': [conflict_deadlock_1_arg,
                              conflict_deadlock_2_arg,
                              conflict_deadlock_3_arg],
            'num_cd_actors': num_cd_actors_arg
        }

        self.scenario_driver(
            scenario_builder=ConfigVerifier.build_conf_dead_scenario_suite,
            scenario_builder_args=args_for_scenario_builder,
            caplog_to_use=caplog,
            commander_config=commander_config
        )

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

        log_msg = f'scenario builder: {scenario_builder}'
        log_ver.add_msg(log_msg=log_msg)
        logger.debug(log_msg)

        log_msg = f'scenario args: {scenario_builder_args}'
        log_ver.add_msg(log_msg=re.escape(log_msg))
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
        config_ver.build_exit_suite(cmd_runner=commander_name,
                                    names=names)

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
            config_ver.cmd_thread_alive = True
            config_ver.cmd_thread_auto_start = True
            config_ver.main_driver()
        elif commander_config == AppConfig.CurrentThreadApp:
            commander_current_app = CommanderCurrentApp(
                config_ver=config_ver,
                name=commander_name,
                max_msgs=10)
            config_ver.cmd_thread_alive = True
            config_ver.cmd_thread_auto_start = False
            commander_current_app.run()
        elif commander_config == AppConfig.RemoteThreadApp:
            outer_thread_app = OuterThreadApp(
                config_ver=config_ver,
                name=commander_name,
                max_msgs=10)
            config_ver.cmd_thread_alive = False
            config_ver.cmd_thread_auto_start = False
            outer_thread_app.start()
            outer_thread_app.join()
        elif commander_config == AppConfig.RemoteSmartThreadApp:
            outer_thread_app = OuterSmartThreadApp(
                config_ver=config_ver,
                name=commander_name,
                max_msgs=10)
            config_ver.cmd_thread_alive = False
            config_ver.cmd_thread_auto_start = False
            outer_thread_app.smart_start()
            threading.Thread.join(outer_thread_app)
        elif commander_config == AppConfig.RemoteSmartThreadApp2:
            outer_thread_app = OuterSmartThreadApp2(
                config_ver=config_ver,
                name=commander_name,
                max_msgs=10)
            config_ver.cmd_thread_alive = False
            config_ver.cmd_thread_auto_start = False
            outer_thread_app.smart_start()
            threading.Thread.join(outer_thread_app)

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
