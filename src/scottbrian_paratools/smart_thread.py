"""Module smart_thread.py.

===========
SmartThread
===========

The SmartThread class makes it easy to create and use threads in a
multithreaded application. It provides configuration, messaging,
and resume/wait/sync methods It will also detect various error
conditions, such as when a thread becomes unresponsive because it has
ended.

SmartThread is built on top of the Python threading module. There are
three cases where SmartThread can be instantiated:

    1) SmartThread is instantiated with no arguments for *target* nor
       *thread*. Internal variable *thread* is set from
       ''threading.current_thread()''.
    2) SmartThread is instantiated with a *target* argument that
       specifies a routine that is to get control in a new thread.
       Internal variable *thread* is set from ''threading.Thread()''
       with the *target* argument. The remote thread can be started
       immediately when *auto_start* is True (the default), or later by
       issuing ''smart_start()'' for the SmartThread object.
    3) SmartThread is instantiated with a *thread* argument that
       specifies an instance of threading.Thread that is to be bound to
       the internal *thread* variable. This can be useful for a remote
       thread that was created via ''threading.Thread()'' and now
       wishes to use the SmartThread requests.

Each SmartThread instance has a name as provided during instantiation
with the *name* argument. The name is used on the various SmartThread
methods to identify the specific instance.

A SmartThread configuration is composed of class variables that include
a dictionary for a registry, and another dictionary called a pair array
for an array of status blocks. Each status block has a dictionary with
two items, one for each of two SmartThread instances, and is used to
coordinate the SmartThread requests between them. There is a status
block for each combination of SmartThread instances.

Each SmartThread is in a specific state at any one time. These states
are described as a ThreadState as follows:

    1) ThreadState.Unregistered: a SmartThread instance does not yet
       exist in the registry, or its thread has ended and the
       SmartThread was removed from the registry.
    2) ThreadState.Initializing: the SmartThread instance is created and
       is being initialized, but has not yet been registered. This state
       occurs only while the SmartThread __init__ method is running.
    3) ThreadState.Registered: the SmartThread instance exists and is in
       the registry, but the thread has not yet been stated.
    4) ThreadState.Starting: the SmartThread instance exists and is in
       the registry, and the thread is being started by
       ''smart_start()''. This state only applies when the SmartThread
       is created with *target* and ''smart_start()'' is invoked. When
       the SmartThread is created from the current thread, the state
       moves from ThreadState.Initializing to ThreadState.Alive.
    5) ThreadState.Alive: the SmartThread instance exists and is in the
       registry, and the thread has been started and is alive (threading
       is_alive method returns True).
    6) Threading.Stopped: the SmartThread instance exists and is in the
       registry, but the thread has ended. Note that from the
       perspective of some SmartThread requests, if the target of the
       request was not in the Threading.Stopped state when the request
       was initiated, and the thread then ends and a new SmartThread
       instance of the same name is created and enters the
       ThreadState.Registered or ThreadState.Alive state, it is still
       considered to be in the Threading.Stopped state for the duration
       of the request.

The SmartThread requests can be divided into category's as follows:

    1) SmartThread configuration commands: ''smart_start()'',
       ''smart_unreg()'', and ''smart_join()''
    2) SmartThread paired requests: ''smart_send()'' paired with
       ''smart_recv()'' and ''smart_resume()'' paired with
       ''smart_wait()''. These can be subdivided as follows:

           a) throw requests: ''smart_send() and ''smart_resume()''
           b) catch requests: ''smart_recv()'' and ''smart_wait()''
    3) SmartThread handshake requests: ''smart_sync()''

The SmartThread instantiation process and the configuration
commands require various ThreadState states and affect the configuration
and ThreadState transitions:

    1) SmartThread instantiation:
        a) requires ThreadState.Unregistered. An an error is raised
           if a different SmartThread instance of the same name is
           found in the registry
        b) moves the state to ThreadState.Initializing
        c) creates a dictionary entry in the registry and then invokes
           the threading ''is_alive()'' method. If the thread is not yet
           alive, moves the state to ThreadState.Registered. If the
           thread is already alive, move the state to ThreadState.Alive
        d) when other SmartThread instances exist, builds pairs of
           status blocks in the pair array
        e) if the thread is not yet alive and *auto_start* is True,
           ''smart_start()'' is called.
    2) ''smart_start()'':
        a) requires ThreadState.Registered. An error is raised if the
           SmartThread instance is in any other state
        b) moves the state to ThreadState.Starting
        c) invokes threading ''start()''
        d) moves the state to ThreadState.Alive.
    3) ''smart_unreg()'':
        a) requires ThreadState.Registered. An error is raised if the
           SmartThread instance is in any other state
        b) removes the SmartThread instance from the registry and
           removes the status blocks from the pair array for any an all
           combinations involving the SmartThread being unregistered
        c) by virtue of being removed from the registry, the state
           becomes ThreadState.Unregistered
        d) the SmartThread instance may remain is scope, but it can
           not be started or enacted upon by any command at this point.
           The name can be used again for a newly created instance.
    4) ''smart_join()'':
        a) requires ThreadState.Registered, ThreadState.Starting,
           ThreadState.Alive, or ThreadState.Stopped. An error is raised
           if the SmartThread instance is in any other state. If needed,
           ''smart_join()'' will loop until the SmartThread instance
           enters ThreadState.Stopped or a timeout is recognized
        b) removes the SmartThread instance from the registry and
           removes the status blocks from the pair array for any an all
           combinations involving the SmartThread being unregistered
        c) by virtue of being removed from the registry, the state
           becomes ThreadState.Unregistered
        d) the SmartThread instance may remain is scope, but it can
           not be started or enacted upon by any command at this point.
           The name can be used again for a newly created instance.

The SmartThread paired and handshake requests require that their targets
be in state ThreadState.Alive before completing the request. Each of
request will allow their targets to initially be in states
ThreadState.Unregistered, ThreadState.Starting, or
ThreadState.Registered and will loop until the SmartThread instance
enters ThreadState.Alive or a timeout is recognized. An error is raised
if the SmartThread instance is recognized to be in state
ThreadState.Stopped, whether explicitly or by virtue of having
transitioned to ThreadState.Stopped and then resurrected as a new
instance with the same SmartThread name.


:Example 1: Create a SmartThread configuration for threads named
            alpha and beta, send and receive a message, and resume a
            wait. Note the use of auto_start=False and invoking
            ''smart_start()''.

.. code-block:: python

    from scottbrian_paratools.smart_thread import SmartThread, RecvMsgs

    def f1() -> None:
        print('f1 beta entered')
        beta_smart_thread.smart_send(receivers='alpha',
                                     msg='hi alpha, this is beta')
        beta_smart_thread.smart_wait(resumers='alpha')
        print('f1 beta exiting')

    print('mainline alpha entered')
    alpha_smart_thread = SmartThread(name='alpha')
    beta_smart_thread = SmartThread(name='beta',
                                    target=f1,
                                    auto_start=False)
    beta_smart_thread.smart_start()
    recvd_msgs = RecvMsgs()
    alpha_smart_thread.smart_recv(
        received_msgs=recvd_msgs,
        senders='beta')
    print(recvd_msgs.recv_msgs['beta'])
    alpha_smart_thread.smart_resume(waiters='beta')
    alpha_smart_thread.smart_join(targets='beta')
    print('mainline alpha exiting')

.. invisible-code-block: python

    del SmartThread._registry['alpha']

Expected output for Example 1::

    mainline alpha entered
    f1 beta entered\
    ['hi alpha, this is beta']
    f1 beta exiting
    mainline alpha exiting


:Example 2: Create a SmartThread configuration for threads named
            alpha and beta, send and receive a message, and resume a
            wait. Note the use of auto_start=True and passing the
            SmartThread instance to the target via the thread_parm_name.

.. code-block:: python

    from scottbrian_paratools.smart_thread import SmartThread, RecvMsgs

    def f1(smart_thread: SmartThread) -> None:
        print('f1 beta entered')
        smart_thread.smart_send(receivers='alpha',
                                msg='hi alpha, this is beta')
        smart_thread.smart_wait(resumers='alpha')
        print('f1 beta exiting')

    print('mainline alpha entered')
    alpha_smart_thread = SmartThread(name='alpha')
    SmartThread(name='beta',
                target=f1,
                auto_start=True,
                thread_parm_name='smart_thread')
    recvd_msgs = RecvMsgs()
    alpha_smart_thread.smart_recv(
        received_msgs=recvd_msgs,
        senders='beta')
    print(recvd_msgs.recv_msgs['beta'])
    alpha_smart_thread.smart_resume(waiters='beta')
    alpha_smart_thread.smart_join(targets='beta')
    print('mainline alpha exiting')

.. invisible-code-block: python

    del SmartThread._registry['alpha']

Expected output for Example 2::

    mainline alpha entered
    f1 beta entered
    ['hi alpha, this is beta']
    f1 beta exiting
    mainline alpha exiting


:Example 3: Create a SmartThread configuration for threads named
            alpha and beta, send and receive a message, and resume a
            wait. Note the use of threading.Thread to create and start
            the beta thread and having the target thread instantiate the
            SmartThread.

.. code-block:: python

    from scottbrian_paratools.smart_thread import SmartThread, RecvMsgs
    import threading

    def f1() -> None:
        print('f1 beta entered')
        beta_smart_thread = SmartThread(name='beta')
        beta_smart_thread.smart_send(receivers='alpha',
                                     msg='hi alpha, this is beta')
        beta_smart_thread.smart_wait(resumers='alpha')
        print('f1 beta exiting')

    print('mainline alpha entered')
    alpha_smart_thread = SmartThread(name='alpha')
    beta_thread = threading.Thread(target=f1, name='beta')
    beta_thread.start()
    recvd_msgs = RecvMsgs()
    alpha_smart_thread.smart_recv(
        received_msgs=recvd_msgs,
        senders='beta')
    print(recvd_msgs.recv_msgs['beta'])
    alpha_smart_thread.smart_resume(waiters='beta')
    alpha_smart_thread.smart_join(targets='beta')
    print('mainline alpha exiting')

.. invisible-code-block: python

    del SmartThread._registry['alpha']

Expected output for Example 3::

    mainline alpha entered
    f1 beta entered
    ['hi alpha, this is beta']
    f1 beta exiting
    mainline alpha exiting


:Example 4: Create a SmartThread configuration for threads named alpha
            and beta, send and receive a message, and resume a wait.
            Note the use of the ThreadApp class that inherits
            threading.Thread as a base and uses a run method. This
            example demonstrates the use of the *thread* argument on the
            SmartThread instantiation.

.. code-block:: python

    from scottbrian_paratools.smart_thread import SmartThread, RecvMsgs
    import threading
    import time

    class ThreadApp(threading.Thread):
        def __init__(self, name: str) -> None:
            super().__init__(name=name)
            self.smart_thread = SmartThread(
                name=name,
                thread=self,
                auto_start=False)
            self.smart_thread.smart_start()

        def run(self) -> None:
            print(f'{self.smart_thread.name} entry to run method')
            self.smart_thread.smart_send(msg='hi alpha, this is beta',
                                         receivers='alpha')
            time.sleep(1)
            print(f'{self.smart_thread.name} about to wait')
            self.smart_thread.smart_wait(resumers='alpha')
            print(f'{self.smart_thread.name} exiting run method')

    print('mainline alpha entered')
    alpha_smart_thread = SmartThread(name='alpha')
    ThreadApp(name='beta')
    recvd_msgs = RecvMsgs()
    alpha_smart_thread.smart_recv(
        received_msgs=recvd_msgs,
        senders='beta')
    print(recvd_msgs.recv_msgs['beta'])
    time.sleep(2)
    print('alpha about to resume beta')
    alpha_smart_thread.smart_resume(waiters='beta')
    alpha_smart_thread.smart_join(targets='beta')
    print('mainline alpha exiting')

.. invisible-code-block: python

    del SmartThread._registry['alpha']

Expected output for Example 4::

    mainline alpha entered
    beta entry to run method
    ['hi alpha, this is beta']
    beta about to wait
    alpha about to resume beta
    beta exiting run method
    mainline alpha exiting


:Example 5: Create a SmartThread configuration for threads named alpha
            and beta, send and receive a message, and resume a wait. Note
            the use of the SmartThreadApp class that multiplicatively
            inherits threading.Thread and SmartThread and uses a run
            method. This example demonstrates the use of the *thread*
            argument on the SmartThread instantiation.

.. code-block:: python

    from scottbrian_paratools.smart_thread import SmartThread, RecvMsgs
    import threading
    import time

    class SmartThreadApp(threading.Thread, SmartThread):
        def __init__(self, name: str) -> None:
            threading.Thread.__init__(self, name=name)
            SmartThread.__init__(self,
                                 name=name,
                                 thread=self,
                                 auto_start=True)

        def run(self) -> None:
            print(f'{self.name} entry to run method')
            self.smart_send(msg='hi alpha, this is beta',
                            receivers='alpha')
            time.sleep(1)
            print(f'{self.name} about to wait')
            self.smart_wait(resumers='alpha')
            print(f'{self.name} exiting run method')

    print('mainline alpha entered')
    alpha_smart_thread = SmartThread(name='alpha')
    SmartThreadApp(name='beta')
    recvd_msgs = RecvMsgs()
    alpha_smart_thread.smart_recv(
        received_msgs=recvd_msgs,
        senders='beta')
    print(recvd_msgs.recv_msgs['beta'])
    time.sleep(2)
    print('alpha about to resume beta')
    alpha_smart_thread.smart_resume(waiters='beta')
    alpha_smart_thread.smart_join(targets='beta')
    print('mainline alpha exiting')

.. invisible-code-block: python

    del SmartThread._registry['alpha']

Expected output for Example5::

    mainline alpha entered
    beta entry to run method
    ['hi alpha, this is beta']
    beta about to wait
    alpha about to resume beta
    beta exiting run method
    mainline alpha exiting

"""

########################################################################
# Standard Library
########################################################################
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from enum import auto, Enum, Flag, StrEnum
import logging
import queue
import threading
import time
from typing import (Any, Callable, ClassVar, NamedTuple, Optional, Type,
                    TypeAlias, TYPE_CHECKING, Union)

########################################################################
# Third Party
########################################################################

########################################################################
# Local
########################################################################
from scottbrian_utils.diag_msg import get_formatted_call_sequence
from scottbrian_utils.timer import Timer
from scottbrian_locking import se_lock as sel

########################################################################
# Establish logger for SmartThread
########################################################################
logger = logging.getLogger(__name__)


########################################################################
# TypeAlias
########################################################################
IntFloat: TypeAlias = Union[int, float]
OptIntFloat: TypeAlias = Optional[IntFloat]

ConfigCmdCallable: TypeAlias = Callable[["RequestBlock", str], bool]
RequestCallable: TypeAlias = Callable[
    ["RequestBlock",
     "PairKeyRemote",
     "SmartThread.ConnectionStatusBlock"], bool]

ProcessRtn: TypeAlias = Union[ConfigCmdCallable, RequestCallable]

# SendMsgs: TypeAlias = dict[str, list[Any]]


@dataclass
class SendMsgs:
    """Class used for a set of messages to send."""
    send_msgs: dict[str, list[Any]]

# def make_def_dict():
#     return defaultdict(list)
#
# @dataclass
# class RecvMsgs:
#     """Class used for a set of messages to send."""
#     recv_msgs: dict[str, list[Any]] = field(
#         default_factory=make_def_dict)


########################################################################
# SmartThread class exceptions
########################################################################
class SmartThreadError(Exception):
    """Base class for exceptions in this module."""
    pass


class SmartThreadDetectedOpFromForeignThread(SmartThreadError):
    """SmartThread exception attempted op from unregistered thread."""
    pass


class SmartThreadErrorInRegistry(SmartThreadError):
    """SmartThread exception for registry error."""


class SmartThreadIncorrectNameSpecified(SmartThreadError):
    """SmartThread exception for a name that is not a str."""


class SmartThreadNameAlreadyInUse(SmartThreadError):
    """SmartThread exception for using a name already in use."""
    pass


class SmartThreadRemoteThreadNotAlive(SmartThreadError):
    """SmartThread exception for remote thread not alive."""


class SmartThreadRemoteThreadNotRegistered(SmartThreadError):
    """SmartThread exception for remote thread not registered."""


class SmartThreadDeadlockDetected(SmartThreadError):
    """SmartThread exception for deadlock detected."""
    pass


class SmartThreadRequestTimedOut(SmartThreadError):
    """SmartThread exception for request timeout."""
    pass


class SmartThreadMutuallyExclusiveTargetThreadSpecified(SmartThreadError):
    """SmartThread exception mutually exclusive target and thread."""
    pass


class SmartThreadArgsSpecificationWithoutTarget(SmartThreadError):
    """SmartThread exception args specified without target."""
    pass


class SmartThreadInvalidUnregister(SmartThreadError):
    """SmartThread exception for invalid smart_unreg request."""
    pass


class SmartThreadInvalidInput(SmartThreadError):
    """SmartThread exception for invalid input on a request."""
    pass


class SmartThreadWorkDataException(SmartThreadError):
    """SmartThread exception for unexpected data encountered."""
    pass


class SmartThreadNoRemoteTargets(SmartThreadError):
    """SmartThread exception for no remote requestors."""
    pass


class SmartThreadIncorrectData(SmartThreadError):
    """SmartThread exception for incorrect data."""
    pass


class SmartThreadAlreadyStarted(SmartThreadError):
    """SmartThread exception for smart_start already started."""
    pass


class SmartThreadMultipleTargetsForSelfStart(SmartThreadError):
    """SmartThread exception for smart_start with multiple targets."""
    pass


class SmartThreadAlreadyExists(SmartThreadError):
    """SmartThread exception for smart_init of same thread."""
    pass


########################################################################
# ReqType
# contains the type of request
########################################################################
class ReqType(StrEnum):
    """Request for SmartThread."""
    NoReq = auto()
    Smart_init = auto()
    Smart_start = auto()
    Smart_unreg = auto()
    Smart_join = auto()
    Smart_send = auto()
    Smart_recv = auto()
    Smart_resume = auto()
    Smart_sync = auto()
    Smart_wait = auto()


########################################################################
# ReqCategory
# contains the category of the request
########################################################################
class ReqCategory(Enum):
    """Category for SmartThread request."""
    Config = auto()
    Throw = auto()
    Catch = auto()
    Handshake = auto()


class PairKey(NamedTuple):
    """Names the remote threads in a pair in the pair array."""
    name0: str
    name1: str


class PairKeyRemote(NamedTuple):
    """NamedTuple for the request pair_key and remote name."""
    pair_key: PairKey
    remote: str
    create_time: float


########################################################################
# RequestBlock
# contains the remotes and timer returned from _request_setup
########################################################################
@dataclass
class RequestBlock:
    """Setup block."""
    request: ReqType
    process_rtn: ProcessRtn
    cleanup_rtn: Callable[[set[str], str], None]
    get_block_lock: bool
    remotes: set[str]
    error_stopped_target: bool
    error_not_registered_target: bool
    completion_count: int
    pk_remotes: list[PairKeyRemote]
    timer: Timer
    do_refresh: bool
    exit_log_msg: Optional[str]
    msg_to_send: Any
    stopped_remotes: set[str]
    not_registered_remotes: set[str]
    deadlock_remotes: set[str]
    full_send_q_remotes: set[str]
    request_max_interval: IntFloat = 0.0
    remote_deadlock_request: ReqType = ReqType.NoReq


########################################################################
# ThreadCreate Flags Class
# These flags are used to indicate how the SmartThread was created
# during initialization based on the arguments.
########################################################################
class ThreadCreate(Flag):
    """Thread create flags."""
    Current = auto()
    Target = auto()
    Thread = auto()


########################################################################
# ThreadState Flags Class
# These flags are used to indicate the life cycle of a SmartThread.
# Initializing is set in the __init__ method. The __init__ method calls
# _register and upon return the state of Registered is set. When
# the start method is called, the state is set to Starting, and after
# the start is done and the thread is alive, the state is set to Alive.
# When the join method is called and the thread becomes not alive,
# the state is set to Stopped which then allows the _clean_registry
# method to remove the SmartThread.
########################################################################
class ThreadState(Flag):
    """Thread state flags."""
    Unregistered = auto()
    Initializing = auto()
    Registered = auto()
    Starting = auto()
    Alive = auto()
    Stopped = auto()


########################################################################
# WaitFor Class
# Used on the smart_wait to specify whether to wait for:
#     All: every remote specified in the remotes argument must
#         do a resume to complete the wait
#     Any: any remote that does a resume will complete the wait
########################################################################
class WaitFor(Enum):
    """Choices for how many remote threads required for completion."""
    All = auto()
    Any = auto()


########################################################################
# SmartThread Class
########################################################################
class SmartThread:
    """Provides services among one or more threads."""

    ####################################################################
    # Constants
    ####################################################################

    ####################################################################
    # Registry
    ####################################################################
    # The _registry is a dictionary of SmartClass instances keyed by the
    # SmartThread name.
    _registry_lock: ClassVar[sel.SELock] = sel.SELock()
    _registry: ClassVar[dict[str, "SmartThread"]] = {}

    # init update time used in log messages when registry is changed
    _registry_last_update: datetime = datetime(2000, 1, 1, 12, 0, 1)

    _create_pair_array_entry_time: float = 0.0

    ####################################################################
    # TargetThread is used to override the threading.Thread run
    # method so that we can set the ThreadState directly and avoid some
    # of the asynchronous effects of starting the thread and having it
    # finish before we can set the state from Starting to Alive
    ####################################################################
    class TargetThread(threading.Thread):
        """Thread class used for SmartThread target."""
        def __init__(self, *,
                     smart_thread: "SmartThread",
                     target: Callable[..., Any],
                     name: str,
                     args: Optional[tuple[Any, ...]] = None,
                     kwargs: Optional[dict[str, Any]] = None,
                     ) -> None:
            """Initialize the TargetThread instance.

            Args:
                smart_thread: the instance of SmartThread for this
                    TargetThread
                target: the target routine to be give control in a
                    new thread
                name: name of thread
                args: arguments to pass to the target routine
                kwargs: keyword arguments to pass to the target routine

            """
            super().__init__(target=target,
                             args=args or (),
                             kwargs=kwargs or {},
                             name=name)
            self.smart_thread = smart_thread

        def run(self) -> None:
            """Invoke the target when the thread is started."""
            try:
                self._target(*self._args, **self._kwargs)
            finally:
                # Avoid a refcycle if the thread is running a function with
                # an argument that has a member that points to the thread.
                del self._target, self._args, self._kwargs

    ####################################################################
    # ConnectionStatusBlock
    # Coordinates the various actions involved in satisfying a
    # smart_send, smart_recv, smart_wait, smart_resume, or smart_sync
    # request.
    #
    # Notes:
    #     1) target_create_timee is used to ensure that a catch type
    #        request (smart_recv or wait) or handshake request (sync)
    #        are satisfied by the remote that was in the configuration
    #        when the request was initiated. Normally, each request will
    #        periodically check the remote state and will raise an error
    #        if the remote has stopped. There is, however, the
    #        possibility that the remote will be started again
    #        (resurrected) and could potentially complete the request
    #        before the current thread notices that the remote had been
    #        stopped. We don't want a resurrected remote to complete the
    #        request, so the remote will check to ensure its create time
    #        is equal target_create_time before completing the request.
    #     2) request_pending is used to prevent the pair array item from
    #        being removed, and this is needed to ensure that the
    #        target_create_time remains valid.
    #
    ####################################################################
    @dataclass
    class ConnectionStatusBlock:
        """Connection status block."""
        name: str
        create_time: float
        target_create_time: float
        wait_event: threading.Event
        sync_event: threading.Event
        msg_q: queue.Queue[Any]
        code: Any = None
        request: ReqType = ReqType.NoReq
        remote_deadlock_request: ReqType = ReqType.NoReq
        del_deferred: bool = False
        recv_wait: bool = False
        wait_wait: bool = False
        sync_wait: bool = False
        deadlock: bool = False
        request_pending: bool = False

    @dataclass
    class ConnectionPair:
        """ConnectionPair class."""
        status_lock: threading.Lock
        status_blocks: dict[str, "SmartThread.ConnectionStatusBlock"]

    _pair_array: ClassVar[
        dict[PairKey, "SmartThread.ConnectionPair"]] = {}
    _pair_array_last_update: datetime = datetime(
        2000, 1, 1, 12, 0, 1)

    # the following constant is the amount of time we will allow
    # for a request to complete while holding the registry lock before
    # checking the remote state
    K_REQUEST_MIN_INTERVAL: IntFloat = 0.01

    # the following constant is the default amount of time we will allow
    # for a request to complete while holding the registry lock after
    # determining that the remote state is alive
    K_REQUEST_MAX_INTERVAL: IntFloat = 1.0

    ####################################################################
    # __init__
    ####################################################################
    def __init__(self, *,
                 name: str,
                 target: Optional[Callable[..., Any]] = None,
                 args: Optional[tuple[Any, ...]] = None,
                 kwargs: Optional[dict[str, Any]] = None,
                 thread_parm_name: Optional[str] = None,
                 thread: Optional[threading.Thread] = None,
                 auto_start: Optional[bool] = True,
                 default_timeout: OptIntFloat = None,
                 max_msgs: int = 0,
                 request_max_interval: IntFloat = K_REQUEST_MAX_INTERVAL
                 ) -> None:
        """Initialize an instance of the SmartThread class.

        Args:
            name: name to be used to refer to this SmartThread. The name
                will be used to set the threading.Thread name. If it is
                desired that threading.Thread.name remain unchanged,
                specify the threading.Thread name.
            target: specifies that a thread is to be created and started
                        with the given target. Mutually exclusive with
                        the *thread* specification. Note that the
                        threading.Thread will be created with *target*,
                        *args* if specified, and the *name*.
            args: args for the thread creation when *target* is
                      specified.
            kwargs: keyword args for the thread creation when *target*
                is specified.
            thread_parm_name: specifies the keyword name to use to pass
                the smart_thread instance to the target routine.
            thread: specifies the thread to use instead of the current
                        thread - needed when SmartThread is instantiated
                        in a class that inherits threading.Thread in
                        which case thread=self is required. Mutually
                        exclusive with *target*.
            auto_start: specifies whether to start the thread. Valid for
                            target or thread only. Ignored when neither
                            target nor thread specified.
            default_timeout: the timeout value to use when a request is
                made and a timeout for the request is
                not specified. If default_timeout is
                specified, a value of zero or less will
                be equivalent to None, meaning that a
                default timeout will not be used.
            max_msgs: specifies the maximum number of messages that can
                occupy the message queue. Zero (the default) specifies
                no limit.
            request_max_interval: used to control the sleep time when
                waiting for a request to complete

        Raises:
            SmartThreadIncorrectNameSpecified: Attempted SmartThread
                  instantiation with incorrect name of {name}.
            SmartThreadMutuallyExclusiveTargetThreadSpecified: Attempted
                  SmartThread instantiation with both target and thread
                  specified.
            SmartThreadArgsSpecificationWithoutTarget: Attempted
                  SmartThread instantiation with args specified and without
                  target specified.


        The various combinations of the SmartThread initialization
        *default_timeout* specification and an individual request
        *timeout* specification determine whether a request can
        timeout and which timeout value will be used. In the following
        table:

            - None means the argument was either omitted or None
              was specified
            - zero means 0 was specified
            - neg means a negative value was specified
            - pos means a positive, non-zero value was specified

        +-----------------+-----------------+----------------------+
        | default_timeout | request timeout | result               |
        +=================+=================+======================+
        | None, zero, neg | None, zero, neg | no timeout           |
        +-----------------+-----------------+----------------------+
        | None, zero, neg | pos             | request timeout used |
        +-----------------+-----------------+----------------------+
        | pos             | None            | default_timeout used |
        +-----------------+-----------------+----------------------+
        | pos             | zero, neg       | no timeout           |
        +-----------------+-----------------+----------------------+
        | pos             | pos             | request timeout used |
        +-----------------+-----------------+----------------------+

        """
        self.specified_args = locals()  # used for __repr__, see below

        self.debug_logging_enabled = logger.isEnabledFor(logging.DEBUG)

        # set the cmd_runner name if it is valid (if not valid, we raise
        # an error after we issue the smart_init entry log message with
        # the current thread name)
        if not thread and not target and isinstance(name, str):
            self.cmd_runner = name
        else:
            self.cmd_runner = threading.current_thread().name

        self.request: ReqType = ReqType.Smart_init

        exit_log_msg = self._issue_entry_log_msg(
            request=ReqType.Smart_init,
            remotes={name},
            latest=2)

        if not isinstance(name, str):
            error_msg = (
                f'SmartThread {threading.current_thread().name} raising '
                'SmartThreadIncorrectNameSpecified error while processing '
                'request smart_init. '
                f'The input {name=} is incorrect. Please specify a str for'
                f'the name.')
            logger.error(error_msg)
            raise SmartThreadIncorrectNameSpecified(error_msg)
        self.name = name

        if target and thread:
            error_msg = (
                f'SmartThread {threading.current_thread().name} raising '
                'SmartThreadMutuallyExclusiveTargetThreadSpecified error '
                'while processing request smart_init. '
                'Arguments for mutually exclusive parameters target and '
                'thread were both specified. Please specify only one or '
                'target or thread.')
            raise SmartThreadMutuallyExclusiveTargetThreadSpecified(error_msg)

        if (not target) and (args or kwargs):
            error_msg = (
                f'SmartThread {threading.current_thread().name} raising '
                'SmartThreadArgsSpecificationWithoutTarget error while '
                'processing request smart_init. '
                'Arguments for parameters args or kwargs were specified, '
                'but an argument for the target parameter was not '
                'specified. Please specify target or remove args and '
                'kwargs.')
            logger.error(error_msg)
            raise SmartThreadArgsSpecificationWithoutTarget(error_msg)

        if target:  # caller wants a thread created
            self.thread_create = ThreadCreate.Target

            keyword_args: Optional[dict[str, Any]] = None
            if kwargs:
                keyword_args = kwargs.copy()
                if thread_parm_name:
                    keyword_args[thread_parm_name] = self
            else:
                if thread_parm_name:
                    keyword_args = {thread_parm_name: self}

            self.thread = SmartThread.TargetThread(
                    smart_thread=self,
                    target=target,
                    args=args,
                    kwargs=keyword_args,
                    name=name)
        elif thread:  # caller provided the thread to use
            self.thread_create = ThreadCreate.Thread
            self.thread = thread
            # self.thread.name = name
        else:  # caller is running on the thread to be used
            self.thread_create = ThreadCreate.Current
            self.thread = threading.current_thread()
            # self.thread.name = name

        self.cmd_lock = threading.Lock()

        self.st_state: ThreadState = ThreadState.Unregistered
        self._set_state(
            target_thread=self,
            new_state=ThreadState.Initializing)

        self.auto_start = auto_start

        self.default_timeout = default_timeout

        self.code = None

        self.max_msgs = max_msgs
        self.request_max_interval = request_max_interval

        self.started_targets: set[str] = set()
        self.unreged_targets: set[str] = set()
        self.joined_targets: set[str] = set()
        # self.recvd_msgs: dict[str, list[Any]] = defaultdict(list)
        self.recvd_msgs: dict[str, list[Any]] = {}
        self.sent_targets: set[str] = set()
        self.resumed_by: set[str] = set()
        self.resumed_targets: set[str] = set()
        self.synced_targets: set[str] = set()

        self.work_remotes: set[str] = set()
        self.work_pk_remotes: list[PairKeyRemote] = []
        self.missing_remotes: set[str] = set()
        self.found_pk_remotes: list[PairKeyRemote] = []

        # set create time to zero - we will update create_time in
        # the _register method under lock
        self.create_time: float = 0.0

        # register this new SmartThread so others can find us
        self._register()

        # set the thread name only after _register was successful to
        # avoid having to restore the name in the case of a duplicate
        # thread error
        self.thread.name = name

        self.auto_started = False

        if self.auto_start:
            if self.thread.is_alive():
                extra_text = 'auto_start obviated'
            else:
                self.auto_started = True
                extra_text = 'auto_start will proceed'
        else:
            extra_text = 'auto_start not requested'

        logger.info(f'{self.cmd_runner} completed initialization of '
                    f'{self.name}: {self.thread_create}, '
                    f'{self.st_state}, {extra_text}.')

        self.request: ReqType = ReqType.NoReq

        if self.auto_started:
            self.smart_start(self.name)
            # We are running under some other thread than the one
            # that was started and we are using that started threads
            # smart_thread instance to do the start. The newly started
            # thread could issue a request using this same instance. So,
            # we need to be careful and not make any changes that could
            # affect the new thread.

        logger.debug(exit_log_msg)

    ####################################################################
    # repr
    ####################################################################
    def __repr__(self) -> str:
        """Return a representation of the class.

        Returns:
            The representation as how the class is instantiated

        :Example 1: instantiate a SmartThread and call repr

        .. code-block: python

            from scottbrian_paratools.smart_thread import SmartThread
            smart_thread = SmartThread(name='alpha')
            repr(smart_thread)

        .. invisible-code-block: python

            del SmartThread._registry['alpha']

        Expected out for Example 1::

            "SmartThread(name='alpha')"

        """
        if TYPE_CHECKING:
            __class__: Type[SmartThread]  # noqa: F842
        classname = self.__class__.__name__
        parms = f"name='{self.name}'"

        for key, item in self.specified_args.items():
            if item:  # if not None
                if key == 'target':
                    function_name = item.__name__
                    parms += ', ' + f'{key}={function_name}'
                elif key in ('args', 'kwargs', 'thread', 'default_timeout'):
                    if item is not self:  # avoid recursive repr loop
                        parms += ', ' + f'{key}={item}'
        # elif key in ('args', 'thread', 'default_timeout'):
        return f'{classname}({parms})'

    ####################################################################
    # _get_state
    ####################################################################
    @staticmethod
    def _get_state(name: str) -> ThreadState:
        """Get the status of a thread.

        Args:
            name: name of thread to get status for

        Returns:
            The thread status

        Notes:
            Must be called holding the registry lock either shared or
            exclusive
        """
        if name not in SmartThread._registry:
            return ThreadState.Unregistered

        # When we start the thread, we set the state to Starting and
        # then call threading start which sets is_alive to true. When we
        # get back we immediately set the state Alive. If the started
        # thread were to call _get_state, we would want it to see itself
        # as Alive. Thus, if is_alive is true here and the state is
        # Starting, return Alive.

        # $$$ wait: this can't happen since the lock must be held, so
        # the started thread will not be able to see Starting - only
        # will be able to see Alive. Comment out the following code and
        # see if any error show up while testing:
        # if (SmartThread._registry[name].thread.is_alive()
        #         and SmartThread._registry[name].st_state
        #         == ThreadState.Starting):
        #     return ThreadState.Alive

        # is_alive will be False when the thread has not yet been
        # started or after the thread has ended. For the former, the
        # ThreadState will probably be Registered. For the latter it
        # will be Alive, in which case we can safely return Stopped.
        if (not SmartThread._registry[name].thread.is_alive() and
                SmartThread._registry[name].st_state == ThreadState.Alive):
            return ThreadState.Stopped

        # For all other cases, we can rely on the state being correct
        return SmartThread._registry[name].st_state

    ####################################################################
    # _get_target_state
    ####################################################################
    @staticmethod
    def _get_target_state(pk_remote: PairKeyRemote) -> ThreadState:
        """Get status of thread that is target of a request.

        Args:
            pk_remote: contains target thread info

        Returns:
            The thread status

        Notes:
            Must be called holding the registry lock either shared or
            exclusive
        """
        if pk_remote.remote not in SmartThread._registry:
            # if this remote was created before, then it was stopped
            if pk_remote.create_time > 0.0:
                return ThreadState.Stopped
            else:
                return ThreadState.Unregistered

        if (not SmartThread._registry[pk_remote.remote].thread.is_alive()
                and SmartThread._registry[
                    pk_remote.remote].st_state == ThreadState.Alive):
            return ThreadState.Stopped

        if (pk_remote.pair_key in SmartThread._pair_array
                and pk_remote.remote in SmartThread._pair_array[
                    pk_remote.pair_key].status_blocks
                and SmartThread._pair_array[pk_remote.pair_key].status_blocks[
                    pk_remote.remote].create_time != pk_remote.create_time):
            return ThreadState.Stopped

        return SmartThread._registry[pk_remote.remote].st_state

    ####################################################################
    # _set_status
    ####################################################################
    def _set_state(self,
                   target_thread: "SmartThread",
                   new_state: ThreadState) -> None:
        """Set the state for a thread.

        Args:
            target_thread: thread to set status for
            new_state: the new status to be set

        Returns:
            True if status was changed, False otherwise

        Notes:
            Must be called holding the registry lock exclusive

        """
        saved_status = target_thread.st_state
        target_thread.st_state = new_state

        logger.debug(
            f'{self.cmd_runner} set '
            f'state for thread {target_thread.name} from {saved_status} to '
            f'{new_state}',
            stacklevel=2)

    ####################################################################
    # _register
    ####################################################################
    def _register(self) -> None:
        """Register SmartThread in the class registry.

        Raises:
            SmartThreadIncorrectNameSpecified: The name for SmartThread
                must be of type str.
            SmartThreadNameAlreadyInUse: An entry for a SmartThread with
                name = *name* is already registered for a different
                thread.

        Notes:
            1) Any old entries for SmartThreads whose threads are not
               alive are removed when this method is called by calling
               _clean_registry().
            2) Once a thread become not alive, it can not be
               resurrected. The SmartThread is bound to the thread it
               starts with.

        """
        logger.debug(f'{self.request.value} _register entry: '
                     f'cmd_runner: {self.cmd_runner}, '
                     f'target: {self.name}')
        with sel.SELockExcl(SmartThread._registry_lock):
            ############################################################
            # Remove any old entries from registry and pair array
            ############################################################
            self._clean_registry()
            self._clean_pair_array()

            ############################################################
            # Add new name to registry
            ############################################################
            if self.name not in SmartThread._registry:
                # verify that the new instance is not already in the
                # registry under a different name
                for key, item in SmartThread._registry.items():
                    if item.thread is self.thread:
                        error_msg = (
                            f'SmartThread {threading.current_thread().name} '
                            f'raising SmartThreadAlreadyExists error while '
                            f'processing request {self.request.value}. '
                            'While attempting to register a new SmartThread '
                            f'with name {self.name} and thread '
                            f'{self.thread}, it was detected that a registry '
                            'entry already exists for a SmartThread with '
                            f'the same thread {item.thread} for name {key}.')
                        logger.error(error_msg)
                        raise SmartThreadAlreadyExists(error_msg)
                # get a unique time stamp for create_time
                self.create_time = time.time()
                while self.create_time == (
                        SmartThread._create_pair_array_entry_time):
                    self.create_time = time.time()

                # update last create time
                SmartThread._create_pair_array_entry_time = self.create_time

                SmartThread._registry[self.name] = self

                SmartThread._registry_last_update = datetime.utcnow()
                print_time = (SmartThread._registry_last_update
                              .strftime("%H:%M:%S.%f"))
                logger.debug(
                    f'{self.cmd_runner} added {self.name} '
                    f'to SmartThread registry at UTC {print_time}')

                self._set_state(
                    target_thread=self,
                    new_state=ThreadState.Registered)
                if self.thread.is_alive():
                    self._set_state(
                        target_thread=self,
                        new_state=ThreadState.Alive)

                ########################################################
                # add new name to the pair array
                ########################################################
                self._add_to_pair_array()

            elif SmartThread._registry[self.name] != self:
                error_msg = (
                    f'SmartThread {threading.current_thread().name} raising '
                    f'SmartThreadNameAlreadyInUse error while processing '
                    f'request {self.request.value}. '
                    f'While attempting to register a new SmartThread with '
                    f'name {self.name} and ID {id(self)}, it was detected '
                    'that a registry entry already exists for a SmartThread '
                    f'with name {self.name} but a different ID of '
                    f'{id(SmartThread._registry[self.name])}.')
                logger.error(error_msg)
                raise SmartThreadNameAlreadyInUse(error_msg)

        logger.debug(f'{self.request.value} _register exit: '
                     f'cmd_runner: {self.cmd_runner}, '
                     f'target: {self.name}')

    ####################################################################
    # _clean_registry
    ####################################################################
    def _clean_registry(self) -> None:
        """Clean up any old not alive items in the registry.

        Raises:
            SmartThreadErrorInRegistry: Registry item with key {key} has
                non-matching item.name of {item.name}.

        Notes:
            1) Must be called holding _registry_lock

        """
        logger.debug(f'{self.request.value} _clean_registry entry: '
                     f'cmd_runner: {self.cmd_runner}')
        # Remove any old entries
        keys_to_del = []
        for key, item in SmartThread._registry.items():
            # Note that for display purposes _get_state will return
            # stopped instead of alive when the thread is not alive and
            # state is alive. The decision to delete this item, however,
            # is done only when the st_state is stopped as that
            # indicates that a smart_unreg or smart_join has been
            # requested. We could have designed _clean_registry to go
            # ahead and delete entries when they are not alive with
            # ThreadState.Alive, meaning that any request other than
            # smart_unreg or smart_join could cause the "stopped"
            # entries to be deleted, but this would have led to
            # unpredictable and inconsistent behavior depending on the
            # mix of requests.
            is_alive = item.thread.is_alive()
            state = self._get_state(name=key)
            logger.debug(
                f'name={key}, {is_alive=}, state={state}, '
                f'smart_thread={item}')
            if item.st_state == ThreadState.Stopped:
                keys_to_del.append(key)

            if key != item.name:
                error_msg = (
                    f'SmartThread {threading.current_thread().name} raising '
                    f'SmartThreadErrorInRegistry error while processing '
                    f'request {self.request.value}. '
                    f'Registry item with key {key} has non-matching '
                    f'item.name of {item.name}.')
                logger.error(error_msg)
                raise SmartThreadErrorInRegistry(error_msg)

        changed = False
        for key in keys_to_del:
            del SmartThread._registry[key]
            changed = True
            logger.debug(f'{self.cmd_runner} removed {key} from registry for '
                         f'request: {self.request.value}')
            logger.debug(
                f'{self.cmd_runner} set '
                f'state for thread {key} from {ThreadState.Stopped} to '
                f'{ThreadState.Unregistered}', stacklevel=1)

        # update time only when we made a change
        if changed:
            SmartThread._registry_last_update = datetime.utcnow()
            print_time = (SmartThread._registry_last_update
                          .strftime("%H:%M:%S.%f"))
            logger.debug(f'{self.cmd_runner} did cleanup of registry at UTC '
                         f'{print_time}, deleted {sorted(keys_to_del)}')

        logger.debug(f'{self.request.value} _clean_registry exit: '
                     f'cmd_runner: {self.cmd_runner}')

    ###########################################################################
    # _clean_pair_array
    ###########################################################################
    def _clean_pair_array(self) -> None:
        """Remove pair array entries as needed."""
        logger.debug(f'{self.request.value} _clean_pair_array entry: '
                     f'cmd_runner: {self.cmd_runner}')
        changed = False

        # find removable entries in connection pair array
        connection_array_del_list = []
        for pair_key in SmartThread._pair_array.keys():
            # remove thread(s) from status_blocks if not registered
            for thread_name in pair_key:
                if (thread_name not in SmartThread._registry
                        and thread_name in SmartThread._pair_array[
                            pair_key].status_blocks):
                    rem_entry = SmartThread._pair_array[
                            pair_key].status_blocks[
                            thread_name]
                    extra_msg = ''
                    if not rem_entry.msg_q.empty():
                        extra_msg += ', with non-empty msg_q'
                    if rem_entry.wait_event.is_set():
                        extra_msg += ', with wait event set'
                    if rem_entry.sync_event.is_set():
                        extra_msg += ', with sync event set'
                    SmartThread._pair_array[
                            pair_key].status_blocks.pop(thread_name, None)

                    logger.debug(
                        f'{self.cmd_runner} removed status_blocks entry for '
                        f'{pair_key}, name = {thread_name}{extra_msg}')
                    changed = True

            # At this point, either or both threads of the pair will
            # have been removed if no longer registered. If only one
            # thread was removed, then the remaining thread is still
            # registered but should also be removed unless it has one or
            # more messages pending, a wait pending, or is in the middle
            # of a request, in which case we need to leave the entry in
            # place to allow the thread to eventually read its messages
            # or recognize the wait or complete the request. For this
            # case, we will set the del_pending flag to indicate in the
            # request methods that once the request is completed,
            # _clean_pair_array should be called to clean up this
            # entry.
            if len(SmartThread._pair_array[pair_key].status_blocks) == 1:
                thread_name = list(SmartThread._pair_array[
                        pair_key].status_blocks.keys())[0]
                remaining_sb = SmartThread._pair_array[
                        pair_key].status_blocks[thread_name]
                if (not remaining_sb.request_pending
                        and remaining_sb.msg_q.empty()
                        and not remaining_sb.wait_event.is_set()
                        and not remaining_sb.sync_event.is_set()):
                    SmartThread._pair_array[
                        pair_key].status_blocks.pop(thread_name, None)
                    logger.debug(
                        f'{self.cmd_runner} removed status_blocks entry for '
                        f'{pair_key}, name = {thread_name}')
                    changed = True
                else:
                    SmartThread._pair_array[
                        pair_key].status_blocks[
                        thread_name].del_deferred = True
                    extra_msg = ''
                    comma = ''
                    if remaining_sb.request_pending:
                        extra_msg += 'pending request'
                        comma = ','
                    if not remaining_sb.msg_q.empty():
                        extra_msg += f'{comma} non-empty msg_q'
                        comma = ','
                    if remaining_sb.wait_event.is_set():
                        extra_msg += f'{comma} wait event set'
                        comma = ','
                    if remaining_sb.sync_event.is_set():
                        extra_msg += f'{comma} sync event set'

                    logger.debug(
                        f'{self.cmd_runner} removal deferred for '
                        f'status_blocks entry for {pair_key}, '
                        f'name = {thread_name}, reasons: {extra_msg}')

            # remove _connection_pair if both names are gone
            if not SmartThread._pair_array[
                    pair_key].status_blocks:
                connection_array_del_list.append(pair_key)

        for pair_key in connection_array_del_list:
            del SmartThread._pair_array[pair_key]
            logger.debug(
                f'{self.cmd_runner} removed _pair_array entry for {pair_key}')
            changed = True

        if changed:
            SmartThread._pair_array_last_update = datetime.utcnow()
            print_time = (SmartThread._pair_array_last_update
                          .strftime("%H:%M:%S.%f"))
            logger.debug(
                f'{self.cmd_runner} did cleanup of _pair_array at UTC'
                f' {print_time}')

        logger.debug(f'{self.request.value} _clean_pair_array exit: '
                     f'cmd_runner: {self.cmd_runner}')

    ###########################################################################
    # _add_to_pair_array
    ###########################################################################
    def _add_to_pair_array(self) -> None:
        """Add a new thread to the pair array.

        Raises:
            SmartThreadIncorrectData: the pair array data structures
            are incorrect.

        Notes:
            1) A thread is registered during initialization and will
               initially not be alive until started.
            2) If a request is made that includes a yet to be registered
               thread, or one that is not yet alive, the request will
               loop until the remote thread becomes registered and
               alive and its state becomes ThreadState.Alive.
            3) After a thread is registered and is alive, if it fails
               and become not alive, it will remain in the registry
               until its state is changed to Stopped to indicate it was
               once alive. Its state is set to Stopped when a
               TargetThread ends, when a smart_unreg is done, or when a
               smart_join is done. This will allow a request to know
               whether to wait for the thread to become alive, or to
               raise an error for an attempted request on a thread that
               is no longer alive.

        """
        logger.debug(f'{self.request.value} _add_to_pair_array entry: '
                     f'cmd_runner: {self.cmd_runner}, '
                     f'target: {self.name}')

        changed = False
        for existing_name in SmartThread._registry:
            if existing_name == self.name:
                continue
            changed = True  # we will add the new name
            pair_key: PairKey = self._get_pair_key(self.name, existing_name)
            if pair_key in SmartThread._pair_array:
                num_status_blocks = len(SmartThread._pair_array[
                                            pair_key].status_blocks)
                if num_status_blocks == 0:
                    error_msg = (
                        f'SmartThread {threading.current_thread().name} '
                        f'raising SmartThreadIncorrectData error while '
                        f'processing request {self.request.value}. '
                        f'While attempting to add {self.name} to the pair '
                        f'array, it was detected that pair_key {pair_key} is '
                        f'already in the pair array with an empty '
                        f'status_blocks.')
                    logger.error(error_msg)
                    raise SmartThreadIncorrectData(error_msg)
                elif num_status_blocks == 1:
                    if self.name in SmartThread._pair_array[
                            pair_key].status_blocks:
                        error_msg = (
                            f'SmartThread {threading.current_thread().name} '
                            f'raising SmartThreadIncorrectData error while '
                            f'processing request {self.request.value}. '
                            f'While attempting to add {self.name} to the pair '
                            f'array, it was detected that pair_key {pair_key} '
                            f'is already in the pair array with a '
                            f'status_blocks entry containing {self.name}.')
                        logger.error(error_msg)
                        raise SmartThreadIncorrectData(error_msg)
                    if (existing_name in SmartThread._pair_array[
                            pair_key].status_blocks
                            and not SmartThread._pair_array[
                            pair_key].status_blocks[
                                existing_name].del_deferred):
                        error_msg = (
                            f'SmartThread {threading.current_thread().name} '
                            f'raising SmartThreadIncorrectData error while '
                            f'processing request {self.request.value}. '
                            f'While attempting to add {self.name} to the pair '
                            f'array, it was detected that pair_key {pair_key} '
                            f'is already in the pair array with a '
                            f'status_blocks entry containing {existing_name} '
                            f'that is not del_deferred.')
                        logger.error(error_msg)
                        raise SmartThreadIncorrectData(error_msg)
                else:
                    existing_names = SmartThread._pair_array[
                        pair_key].status_blocks.keys()
                    error_msg = (
                        f'SmartThread {threading.current_thread().name} '
                        f'raising SmartThreadIncorrectData error while '
                        f'processing request {self.request.value}. '
                        f'While attempting to add {self.name} to the pair '
                        f'array, it was detected that pair_key {pair_key} '
                        'is already in the pair array with a '
                        'status_blocks entry containing entries for '
                        f'{sorted(existing_names)}.')
                    logger.error(error_msg)
                    raise SmartThreadIncorrectData(error_msg)

            # proceed with valid pair_array
            else:  # pair_key not in SmartThread._pair_array:
                SmartThread._pair_array[pair_key] = (
                    SmartThread.ConnectionPair(
                        status_lock=threading.Lock(),
                        status_blocks={}
                    ))
                logger.debug(
                    f'{self.cmd_runner} added {pair_key} to the '
                    f'_pair_array')
            # add status block entries
            self._add_status_block_entry(
                cmd_runner=self.cmd_runner,
                pair_key=pair_key,
                add_name=self.name)

            if existing_name not in SmartThread._pair_array[
                    pair_key].status_blocks:
                self._add_status_block_entry(
                    cmd_runner=self.cmd_runner,
                    pair_key=pair_key,
                    add_name=existing_name)
            else:  # entry already exists
                # reset del_deferred in case it is ON and the new name
                # is a resurrected thread
                SmartThread._pair_array[pair_key].status_blocks[
                    existing_name].del_deferred = False

            # Find and update a zero create time in work_pk_remotes.
            # Check for existing_name doing a request and is
            # waiting for the new thread to be added as
            # indicated by being in the missing_remotes set
            if self.name in SmartThread._registry[
                    existing_name].missing_remotes:
                # we need to erase the name from the missing
                # list in case the new thread becomes stopped,
                # and then is started again with a new create
                # time, and then we add it again to the
                # found_pk_remotes as another entry with the
                # same pair_key and name, but a different
                # create time which would likely lead to an
                # error
                SmartThread._registry[
                    existing_name].missing_remotes.remove(self.name)

                # update the found_pk_remotes so that other_name
                # will see that we have a new entry and add
                # it to its work_pk_remotes
                create_time = SmartThread._registry[self.name].create_time
                SmartThread._registry[
                    existing_name].found_pk_remotes.append(
                    PairKeyRemote(pair_key,
                                  self.name,
                                  create_time))

                SmartThread._pair_array[pair_key].status_blocks[
                    existing_name].request_pending = True
                SmartThread._pair_array[pair_key].status_blocks[
                    existing_name].request = SmartThread._registry[
                            existing_name].request

        if changed:
            SmartThread._pair_array_last_update = datetime.utcnow()
            print_time = (SmartThread._pair_array_last_update
                          .strftime("%H:%M:%S.%f"))
            logger.debug(
                f'{self.cmd_runner} updated _pair_array at UTC {print_time}')

        logger.debug(f'{self.request.value} _add_to_pair_array exit: '
                     f'cmd_runner: {self.cmd_runner}, '
                     f'target: {self.name}')

    ###########################################################################
    # _add_status_block_entry
    ###########################################################################
    def _add_status_block_entry(self,
                                cmd_runner: str,
                                pair_key: PairKey,
                                add_name: str) -> None:
        """Add a status block entry.

        Args:
            cmd_runner: thread name doing the add
            pair_key: pair_key for new entry
            add_name: new name to add

        """
        create_time = SmartThread._registry[add_name].create_time
        SmartThread._pair_array[pair_key].status_blocks[
            add_name] = SmartThread.ConnectionStatusBlock(
            name=add_name,
            create_time=create_time,
            target_create_time=0.0,
            wait_event=threading.Event(),
            sync_event=threading.Event(),
            msg_q=queue.Queue(maxsize=self.max_msgs))

        logger.debug(
            f'{cmd_runner} added status_blocks entry '
            f'for {pair_key}, name = {add_name}')

    ####################################################################
    # _get_pair_key
    ####################################################################
    @staticmethod
    def _get_pair_key(name0: str,
                      name1: str) -> PairKey:
        """Return a key to use for the connection pair array.

        Args:
            name0: name to combine with name1
            name1: name to combine with name0

        Returns:
            the key to use for the connection pair array

        """
        if name0 < name1:
            return PairKey(name0, name1)
        else:
            return PairKey(name1, name0)

    ########################################################################
    # _get_set
    ########################################################################
    @staticmethod
    def _get_set(item: Optional[Iterable] = None):
        return set({item} if isinstance(item, str) else item or '')

    ####################################################################
    # start
    ####################################################################
    def smart_start(self,
                    targets: Optional[Iterable] = None,
                    log_msg: Optional[str] = None) -> set[str]:
        """Start the smart thread.

        Args:
            targets: thread names to be started
            log_msg: additional text to append to the debug log message
                that is issued on request entry and exit

        Returns:
            A set of thread names that were successfully started.

        **Example 1:** Create and start a SmartThread

        .. code-block:: python

            from scottbrian_paratools.smart_thread import SmartThread
            def f1() -> None:
                print('f1 beta entered')
                print('f1 beta exiting')

            print('mainline alpha entered')
            alpha_smart_thread = SmartThread(name='alpha')
            beta_smart_thread = SmartThread(name='beta',
                                            target=f1,
                                            auto_start=False)
            print('alpha about to start beta')
            beta_smart_thread.smart_start()
            alpha_smart_thread.smart_join(targets='beta')
            print('mainline alpha exiting')

        .. invisible-code-block: python

            del SmartThread._registry['alpha']

        Expected output for Example 1::

            mainline alpha entered
            alpha about to start beta
            f1 beta entered
            f1 beta exiting
            mainline alpha exiting

        **Example 2:** Create and start two SmartThread threads.

        .. code-block:: python

            from scottbrian_paratools.smart_thread import SmartThread
            import time
            def f1_beta() -> None:
                print('f1_beta entered')
                print('f1_beta exiting')
            def f2_charlie() -> None:
                time.sleep(1)
                print('f2_charlie entered')
                print('f2_charlie exiting')
            print('mainline alpha entered')
            alpha_smart_thread = SmartThread(name='alpha')
            beta_smart_thread = SmartThread(name='beta',
                                            target=f1_beta,
                                            auto_start=False)
            charlie_smart_thread = SmartThread(name='charlie',
                                               target=f2_charlie,
                                               auto_start=False)
            print('alpha about to start beta and charlie')
            alpha_smart_thread.smart_start(targets=['beta', 'charlie'])
            alpha_smart_thread.smart_join(targets=['beta', 'charlie'])
            print('mainline alpha exiting')

        .. invisible-code-block: python

            del SmartThread._registry['alpha']

        Expected output for Example 2::

            mainline alpha entered
            alpha about to start beta and charlie
            f1_beta entered
            f1_beta exiting
            f2_charlie entered
            f2_charlie exiting
            mainline alpha exiting

        """
        # smart_start is the only cmd that can be issued with itself as
        # the target running under any other thread. That means two or
        # more threads could be doing smart_start against the same
        # smart_thread instance. We use the self.cmd_lock to prevent
        # more than one start at a time. The first start will work, the
        # others will fail with an already started error.
        with self.cmd_lock:
            if not targets:
                targets = {self.name}
            else:
                targets = self._get_set(targets)

            if self.name not in targets:
                self._verify_thread_is_current(request=ReqType.Smart_start)
            else:
                if len(targets) > 1:
                    error_msg = (
                        f'SmartThread {threading.current_thread().name} '
                        f'raising SmartThreadMultipleTargetsForSelfStart '
                        f'error while processing request smart_start. '
                        'Request smart_start can not be done for multiple '
                        f'targets {targets} when one of the targets is also '
                        f'the smart_thread instance, in this case {self.name}.'
                    )
                    logger.error(error_msg)
                    raise SmartThreadMultipleTargetsForSelfStart(error_msg)
                with sel.SELockExcl(SmartThread._registry_lock):
                    if self.thread.is_alive():
                        error_msg = (
                            f'SmartThread {threading.current_thread().name} '
                            'raising SmartThreadAlreadyStarted error while '
                            'processing request smart_start. '
                            f'Unable to start {self.name} because {self.name} '
                            'has already been started.')
                        logger.error(error_msg)
                        raise SmartThreadAlreadyStarted(error_msg)
                    if self._get_state(self.name) != ThreadState.Registered:
                        error_msg = (
                            f'SmartThread {threading.current_thread().name} '
                            'raising SmartThreadRemoteThreadNotRegistered '
                            'error while processing request smart_start. '
                            f'Unable to start {self.name} because {self.name} '
                            'is not registered.')
                        logger.error(error_msg)
                        raise SmartThreadRemoteThreadNotRegistered(error_msg)

            self.request = ReqType.Smart_start
            self.started_targets = set()
            request_block = self._request_setup(
                remotes=targets,
                error_stopped_target=True,
                error_not_registered_target=True,
                process_rtn=self._process_start,
                cleanup_rtn=None,
                get_block_lock=False,
                completion_count=0,
                timeout=0,
                log_msg=log_msg)

            self.work_remotes: set[str] = request_block.remotes.copy()
            for remote in self.work_remotes.copy():
                with sel.SELockExcl(SmartThread._registry_lock):
                    if request_block.process_rtn(request_block,
                                                 remote):
                        self.work_remotes -= {remote}

            if request_block.not_registered_remotes:
                self._handle_loop_errors(request_block=request_block,
                                         pending_remotes=[])

            if self.name not in targets:
                # We are running under some other thread than the one
                # that was started. If we used a smart_thread instance
                # that is also the target, then we can't clear the
                # request because the started thread might do a request
                # under its thread using this same instance. So, we need
                # to be careful to not make any changes that could
                # affect the new thread.
                self.request = ReqType.NoReq

            logger.debug(request_block.exit_log_msg)

            return self.started_targets

    ####################################################################
    # _process_start
    ####################################################################
    def _process_start(self,
                       request_block: RequestBlock,
                       remote: str,
                       ) -> bool:
        """Process the smart_join request.

        Args:
            request_block: contains request related data
            remote: remote name

        Returns:
            True when request completed, False otherwise

        """
        if self._get_state(remote) == ThreadState.Registered:
            self._set_state(
                target_thread=SmartThread._registry[remote],
                new_state=ThreadState.Starting)
            SmartThread._registry[remote].thread.start()
            # At this point, the thread was started and the threading
            # start bootstrap method received control and set the Event
            # that threading start waits on. The bootstrap method will
            # call run, the thread will execute, and eventually the
            # thread will end. So, at this point, either run has not yet
            # been called, the thread is running, or the thread is
            # already stopped. The is_alive() method will return True
            # if the Event is set (it is) and will return False when
            # the thread is stopped. So, we can rely on is_alive here
            # to correctly reflect whether the thread is alive or has
            # already ended. Since we are holding the registry lock
            # exclusive, the configuration can not change and a join
            # will wait behind us. Regardless of whether the thread is
            # alive and running or has already ended, we will set the
            # thread state to Alive. This is not a problem since the
            # _get_state method will return Stopped state if is_alive()
            # is False and the state is Alive. Note that setting Alive
            # here is our way of saying that if is_alive() is False,
            # it's not because the thread was not yet started, but
            # instead means that the thread started and already ended.

            self._set_state(
                target_thread=SmartThread._registry[remote],
                new_state=ThreadState.Alive)
            self.started_targets |= {remote}
        else:
            # if here, the remote is not registered
            request_block.not_registered_remotes |= {remote}

        return True  # there are no cases that need to allow more time

    ####################################################################
    # smart_unreg
    ####################################################################
    def smart_unreg(self, *,
                    targets: Iterable,
                    log_msg: Optional[str] = None) -> set[str]:
        """Unregister threads that were never started.

        Args:
            targets: thread names that are to be unregistered
            log_msg: additional text to append to the debug log message
                that is issued on request entry and exit

        Returns:
            A set of thread names that were successfully unregistered.

        Notes:
            1) A thread that is created but not started remains in the
               registered state until it is either started or
               unregistered.

        Raises:
            SmartThreadRemoteThreadNotRegistered: smart_unreg detected
                one or more target threads that were not in the
                registered state.

        **Example 1:** Create and unregister a SmartThread thread.

        .. # noqa: DAR402

        .. code-block:: python

            from scottbrian_paratools.smart_thread import SmartThread

            def f1_beta() -> None:
                print('f1_beta entered')
                print('f1_beta exiting')

            print('mainline alpha entered')
            alpha_smart_thread = SmartThread(name='alpha')
            print('alpha about to create beta')
            beta_smart_thread = SmartThread(name='beta',
                                            target=f1_beta,
                                            auto_start=False)
            print('alpha about to unregister beta')
            alpha_smart_thread.smart_unreg(targets='beta')
            print('mainline alpha exiting')

        .. invisible-code-block: python

            del SmartThread._registry['alpha']

        Expected output for Example 1::

            mainline alpha entered
            alpha about to create beta
            alpha about to unregister beta
            mainline alpha exiting

        """
        self._verify_thread_is_current(request=ReqType.Smart_unreg)
        self.request = ReqType.Smart_unreg
        self.unreged_targets = set()
        request_block = self._request_setup(
            remotes=targets,
            error_stopped_target=False,
            error_not_registered_target=True,
            process_rtn=None,
            cleanup_rtn=None,
            get_block_lock=False,
            completion_count=0,
            timeout=0,
            log_msg=log_msg)

        # self._config_cmd_loop(request_block=request_block)

        # @sbt what is this doing for us? it only locks the thread
        # against itself
        with self.cmd_lock:
            self.work_remotes: set[str] = request_block.remotes.copy()
            with sel.SELockExcl(SmartThread._registry_lock):
                for remote in self.work_remotes.copy():
                    if self._get_state(remote) != ThreadState.Registered:
                        request_block.not_registered_remotes |= {remote}
                        self.work_remotes -= {remote}
                    else:
                        self._set_state(
                            target_thread=SmartThread._registry[remote],
                            new_state=ThreadState.Stopped)

                        self.work_remotes -= {remote}
                        self.unreged_targets |= {remote}

                # remove threads from the registry
                self._clean_registry()
                self._clean_pair_array()

                if self.unreged_targets:
                    logger.info(
                        f'{self.name} did successful smart_unreg of '
                        f'{sorted(self.unreged_targets)}.')

                if (request_block.error_not_registered_target
                        and request_block.not_registered_remotes):
                    self._handle_loop_errors(
                        request_block=request_block,
                        pending_remotes=list(
                            self.work_remotes))

        self.request = ReqType.NoReq

        logger.debug(request_block.exit_log_msg)

        return self.unreged_targets

    ####################################################################
    # join
    ####################################################################
    def smart_join(self, *,
                   targets: Iterable,
                   timeout: OptIntFloat = None,
                   log_msg: Optional[str] = None) -> set[str]:
        """Wait for target thread to end.

        Args:
            targets: thread names that are to be joined
            timeout: timeout to use instead of default timeout
            log_msg: additional text to append to the debug log message
                that is issued on request entry and exit

        Returns:
            A set of thread names that were successfully joined.

        Raises:
            SmartThreadRequestTimedOut: join timed out waiting for
                targets to end.

        **Example 1:** Create and join a SmartThread thread.

        .. # noqa: DAR402

        .. code-block:: python

            from scottbrian_paratools.smart_thread import SmartThread
            import time

            def f1_beta() -> None:
                print('f1_beta entered')
                print('f1_beta exiting')

            print('mainline alpha entered')
            alpha_smart_thread = SmartThread(name='alpha')
            print('alpha about to create beta')
            beta_smart_thread = SmartThread(name='beta',
                                            target=f1_beta)
            time.sleep(1)
            print('alpha about to join beta')
            alpha_smart_thread.smart_join(targets='beta')
            print('mainline alpha exiting')


        .. invisible-code-block: python

            del SmartThread._registry['alpha']

        Expected output for Example 1::

            mainline alpha entered
            alpha about to create beta
            f1_beta entered
            f1_beta exiting
            alpha about to join beta
            mainline alpha exiting


        """
        self._verify_thread_is_current(request=ReqType.Smart_join)
        self.request = ReqType.Smart_join
        self.joined_targets = set()
        # get RequestBlock with targets in a set and a timer object
        request_block = self._request_setup(
            remotes=targets,
            error_stopped_target=False,
            process_rtn=self._process_smart_join,
            cleanup_rtn=None,
            get_block_lock=False,
            completion_count=0,
            timeout=timeout,
            log_msg=log_msg)

        # self._config_cmd_loop(request_block=request_block)
        with self.cmd_lock:
            self.joined_targets: set[str] = set()
            self.work_remotes: set[str] = request_block.remotes.copy()
            while self.work_remotes:
                joined_remotes: set[str] = set()
                with sel.SELockExcl(SmartThread._registry_lock):
                    for remote in self.work_remotes.copy():
                        if remote in SmartThread._registry:
                            if request_block.process_rtn(request_block,
                                                         remote):
                                self.work_remotes -= {remote}
                                joined_remotes |= {remote}
                        else:
                            logger.debug(f'{self.cmd_runner} determined that '
                                         f'thread {remote} is already in '
                                         f'state {ThreadState.Unregistered}')
                            self.work_remotes -= {remote}
                            joined_remotes |= {remote}

                    # remove threads from the registry
                    if joined_remotes:
                        self.joined_targets |= joined_remotes
                        # must remain under lock for these two calls
                        self._clean_registry()
                        self._clean_pair_array()
                        logger.info(
                            f'{self.name} did successful smart_join of '
                            f'{sorted(joined_remotes)}.')
                        logger.info(
                            f'{self.name} smart_join completed targets: '
                            f'{sorted(self.joined_targets)}, pending '
                            f'targets: {sorted(self.work_remotes)}')
                    else:  # no progress was made
                        time.sleep(0.2)
                        if request_block.timer.is_expired():
                            self._handle_loop_errors(
                                request_block=request_block,
                                pending_remotes=list(self.work_remotes))

        self.request = ReqType.NoReq

        logger.debug(request_block.exit_log_msg)

        return self.joined_targets

    ####################################################################
    # _process_smart_join
    ####################################################################
    def _process_smart_join(self,
                            request_block: RequestBlock,
                            remote: str,
                            ) -> bool:
        """Process the smart_join request.

        Args:
            request_block: contains request related data
            remote: remote name

        Returns:
            True when request completed, False otherwise

        """
        # if the remote is not in the registry then either it was never
        # created, or it was created as a ThreadTarget which ended and
        # set its state to stopped and then got removed by a command
        # that called _clean_registry. In either case, we have
        # nothing to do and can simply return True to move on to the
        # next target.

        # Note that if the remote thread was never
        # started, the following join will raise an
        # error. If the thread is eventually started,
        # we currently have no way to detect that and
        # react. We can only hope that a failed join
        # here will help give us a clue that something
        # went wrong.
        # Note also that we timeout each join after a
        # short 0.2 seconds so that we release and
        # re-obtain the registry lock in between
        # attempts. This is done to ensure we don't
        # deadlock with any of the other services
        # (e.g., smart_recv)
        try:
            SmartThread._registry[remote].thread.join(timeout=0.2)
        except RuntimeError:
            # We know the thread is registered, so
            # we will skip it for now and come back to it
            # later. If it never starts and exits then
            # we will timeout (if timeout was specified)
            return False

        # we need to check to make sure the thread is
        # not alive in case we timed out on the thread.join above
        if SmartThread._registry[remote].thread.is_alive():
            return False  # give thread more time to end
        else:
            self._set_state(
                target_thread=SmartThread._registry[remote],
                new_state=ThreadState.Stopped)

        # restart while loop with one less remote
        return True

    ####################################################################
    # smart_send
    ####################################################################
    def smart_send(self,
                   msg: Optional[Any] = None,
                   receivers: Optional[Iterable] = None,
                   msg_dict: Optional[dict[str, Any]] = None,
                   timeout: OptIntFloat = None,
                   log_msg: Optional[str] = None) -> set[str]:
        """Send one or more messages to remote threads.

        Args:
            msg: the msg to be sent. This may be a single item or a
                collection of items in any type of data structure.
                *receivers* is required when *msg* is specified. *msg*
                is mutually exclusive with *msg_dict*. The same message
                in *msg* is sent to every thread named in *receivers*.
                For separate messages, use *msg_dict* instead.
            receivers: names of remote threads to send the message to.
                *msgs* is required when *receivers* is specified.
                *receivers* is mutually exclusive with *msg_dict*.
            msg_dict: a dictionary of messages to be sent, keyed by the
                names of the remote threads to receive them. Using
                *msg_dict* allows different message to be sent to each
                thread. *msg_dict* is mutually exclusive with *msg* and
                *receivers*.
            timeout: number of seconds allowed for the *smart_send* to
                complete. The *smart_send* will send messages to the
                remote threads only when they are alive. If any of the
                threads to be sent messages to are in states
                ThreadState.Unregistered, ThreadState.Initializing,
                ThreadState.Registered, or ThreadState.Starting, then
                *smart_send* will wait and send the message to the
                thread as soon as it enters state ThreadState.Alive.
                *smart_send* will raise an error if any one target
                thread fails to achieve state ThreadState.Alive within
                the number of seconds specified in *timeout*.
                If *timeout* is not specified, *smart_send* will
                continue to wait and will not raise a timeout error.
                Note that is any target thread enters the state
                ThreadState.Stopped, *smart_send* will raise an error
                regardless of whether *timeout* was specified and
                regardless of how much time has passed.
            log_msg: additional text to append to the debug log message
                that is issued on request entry and exit

        Returns:
            A set of the thread names that were sent a message. Note
            that if *smart_send* raises an error, the thread names that
            were sent a message thus far can be recovered from field
            *sent_targets* in the SmartThread object that issued the
            *smart_send*.

        Raises:
            SmartThreadRemoteThreadNotAlive: target thread was
                stopped.
            SmartThreadRequestTimedOut: request timed out before targets
                became alive.
            SmartThreadNoRemoteTargets: {self.name} issued a smart_send
                request but there are no remote receivers in the
                configuration to send to.

        .. # noqa: DAR402

        *smart_send* can be used to send a single message or multiple
        messages to single or to multiple remote threads. A message can
        be of any type (e.g., text, int, float, list, set, dict, or
        class object). Note that the item being sent is not copied.

        Examples in this section cover the following cases:

            1) send a single message to a single remote thread
            2) send a single message to multiple remote threads
            3) send multiple messages to a single remote thread
            4) send multiple messages to multiple remote threads
            6) send any mixture of single and multiple messages
               individually to each remote thread via *msg_dict*.

        **Example 1:** send a single message to a single remote thread

        .. code-block:: python

            from scottbrian_paratools.smart_thread import SmartThread, RecvMsgs

            def f1(smart_thread: SmartThread) -> None:
                print('f1 beta entered')
                recvd_msgs = RecvMsgs()
                smart_thread.smart_recv(
                    received_msgs=recvd_msgs,
                    senders='alpha')
                print(recvd_msgs.recv_msgs['alpha'])
                print('f1 beta exiting')

            print('mainline alpha entered')
            logger.debug('mainline entered')
            alpha_smart_thread = SmartThread(name='alpha')
            SmartThread(name='beta',
                        target=f1,
                        thread_parm_name='smart_thread')
            alpha_smart_thread.smart_send(msg='hello beta', receivers='beta')
            alpha_smart_thread.smart_join(targets='beta')
            print('mainline alpha exiting')

        .. invisible-code-block: python

            del SmartThread._registry['alpha']

        Expected output for Example 1::

            mainline alpha entered
            f1 beta entered
            ['hello beta']
            f1 beta exiting
            mainline alpha exiting

        **Example 2:** send a single message to multiple remote threads

        .. code-block:: python

            from scottbrian_paratools.smart_thread import SmartThread, RecvMsgs
            import time

            def f1(smart_thread: SmartThread) -> None:
                if smart_thread.name == 'charlie':
                    time.sleep(0.5)  # delay for non-interleaved msgs
                print(f'f1 {smart_thread.name} entered')
                recvd_msgs = RecvMsgs()
                smart_thread.smart_recv(
                    received_msgs=recvd_msgs,
                    senders='alpha')
                print(recvd_msgs.recv_msgs['alpha'])
                print(f'f1 {smart_thread.name} exiting')
            print('mainline alpha entered')
            alpha_smart_thread = SmartThread(name='alpha')
            SmartThread(name='beta',
                        target=f1,
                        thread_parm_name='smart_thread')
            SmartThread(name='charlie',
                        target=f1,
                        thread_parm_name='smart_thread')
            alpha_smart_thread.smart_send(msg='hello remotes',
                                          receivers=('beta', 'charlie'))
            alpha_smart_thread.smart_join(targets=('beta', 'charlie'))
            print('mainline alpha exiting')

        .. invisible-code-block: python

            del SmartThread._registry['alpha']

        Expected output for Example 2::

            mainline alpha entered
            f1 beta entered
            ['hello remotes']
            f1 beta exiting
            f1 charlie entered
            ['hello remotes']
            f1 charlie exiting
            mainline alpha exiting


        **Example 3:** send multiple messages to a single remote thread

        .. code-block:: python

            from scottbrian_paratools.smart_thread import SmartThread, RecvMsgs

            def f1(smart_thread: SmartThread) -> None:
                print(f'f1 {smart_thread.name} entered')
                recvd_msgs = RecvMsgs()
                smart_thread.smart_recv(
                    received_msgs=recvd_msgs,
                    senders='alpha')
                print(recvd_msgs.recv_msgs['alpha'])
                print(f'f1 {smart_thread.name} exiting')

            print('mainline alpha entered')
            alpha_smart_thread = SmartThread(name='alpha')
            SmartThread(name='beta',
                        target=f1,
                        thread_parm_name='smart_thread')
            alpha_smart_thread.smart_send(msg=('hello beta',
                                          'have a great day', 42))
            alpha_smart_thread.smart_join(targets='beta')
            print('mainline alpha exiting')

        .. invisible-code-block: python

            del SmartThread._registry['alpha']

        Expected output for Example 3::

            mainline alpha entered
            f1 beta entered
            [('hello beta', 'have a great day', 42)]
            f1 beta exiting
            mainline alpha exiting

        **Example 4:** send multiple messages to multiple remote threads

        .. code-block:: python

            from scottbrian_paratools.smart_thread import SmartThread, RecvMsgs

            def f1(smart_thread: SmartThread,
                   wait_for: Optional[str] = None,
                   resume_target: Optional[str] = None) -> None:
                if wait_for:
                    smart_thread.smart_wait(resumers=wait_for)
                print(f'f1 {smart_thread.name} entered')
                recvd_msgs = RecvMsgs()
                smart_thread.smart_recv(
                    received_msgs=recvd_msgs,
                    senders='alpha')
                print(recvd_msgs.recv_msgs['alpha'])
                print(f'f1 {smart_thread.name} exiting')
                if resume_target:
                    smart_thread.smart_resume(waiters=resume_target)

            print('mainline alpha entered')
            alpha_smart_thread = SmartThread(name='alpha')
            SmartThread(name='beta',
                        target=f1,
                        thread_parm_name='smart_thread',
                        kwargs={'resume_target': 'charlie'})
            SmartThread(name='charlie',
                        target=f1,
                        thread_parm_name='smart_thread',
                        kwargs={'wait_for': 'beta',
                                'resume_target': 'delta'})
            SmartThread(name='delta',
                        target=f1,
                        thread_parm_name='smart_thread',
                        kwargs={'wait_for': 'charlie',
                                'resume_target': 'alpha'})
            alpha_smart_thread.smart_send(
                msg=['hello remotes', 'have a great day', 42],
                receivers=['beta', 'charlie', 'delta'])
            alpha_smart_thread.smart_wait(resumers='delta')
            alpha_smart_thread.smart_join(targets=('beta', 'charlie', 'delta'))
            print('mainline alpha exiting')

        .. invisible-code-block: python

            del SmartThread._registry['alpha']

        Expected output for Example 4::

            mainline alpha entered
            f1 beta entered
            [['hello remotes', 'have a great day', 42]]
            f1 beta exiting
            f1 charlie entered
            [['hello remotes', 'have a great day', 42]]
            f1 charlie exiting
            f1 delta entered
            [['hello remotes', 'have a great day', 42]]
            f1 delta exiting
            mainline alpha exiting

        **Example 5:** send any mixture of single and multiple messages
        individually to each remote thread using a SendMsg object

        .. code-block:: python

            from scottbrian_paratools.smart_thread import (SmartThread,
                                                           SendMsgs)

            def f1(smart_thread: SmartThread,
                   wait_for: Optional[str] = None,
                   resume_target: Optional[str] = None) -> None:
                if wait_for:
                    smart_thread.smart_wait(resumers=wait_for)
                print(f'f1 {smart_thread.name} entered')
                recvd_msgs = RecvMsgs()
                smart_thread.smart_recv(
                    received_msgs=recvd_msgs,
                    senders='alpha')
                print(recvd_msgs.recv_msgs['alpha'])
                print(f'f1 {smart_thread.name} exiting')
                if resume_target:
                    smart_thread.smart_resume(waiters=resume_target)

            print('mainline alpha entered')
            alpha_smart_thread = SmartThread(name='alpha')
            SmartThread(name='beta',
                        target=f1,
                        thread_parm_name='smart_thread',
                        kwargs={'resume_target': 'charlie'})
            SmartThread(name='charlie',
                        target=f1,
                        thread_parm_name='smart_thread',
                        kwargs={'wait_for': 'beta',
                                'resume_target': 'delta'})
            SmartThread(name='delta',
                        target=f1,
                        thread_parm_name='smart_thread',
                        kwargs={'wait_for': 'charlie',
                                'resume_target': 'alpha'})
            msgs_to_send = SendMsgs(send_msgs={
                'beta': 'hi beta',
                'charlie': ('hi charlie', 'have a great day'),
                'delta': [42, 'hi delta', {'nums': (1, 2, 3)}]})
            alpha_smart_thread.smart_send(msg=msgs_to_send)
            alpha_smart_thread.smart_wait(resumers='delta')
            alpha_smart_thread.smart_join(targets=('beta', 'charlie', 'delta'))
            print('mainline alpha exiting')

        .. invisible-code-block: python

            del SmartThread._registry['alpha']

        Expected output for Example 5::

            mainline alpha entered
            f1 beta entered
            ['hi beta']
            f1 beta exiting
            f1 charlie entered
            [('hi charlie', 'have a great day')]
            f1 charlie exiting
            f1 delta entered
            [[42, 'hi delta', {'nums': (1, 2, 3)}]]
            f1 delta exiting
            mainline alpha exiting

        """
        self._verify_thread_is_current(request=ReqType.Smart_send)
        self.request = ReqType.Smart_send
        self.sent_targets = set()
        remotes: set[str]
        work_msgs: dict[str, Any]

        # Note that we need to determine which combinations of arguments
        # were specified for mutual exclusive checks. After that we will
        # determine whether the specified arguments are valid.
        if msg is not None and receivers is not None:
            if msg_dict is not None:
                error_msg = (
                    f'SmartThread {threading.current_thread().name} raising '
                    'SmartThreadInvalidInput error while processing request '
                    'smart_send. '
                    'Mutually exclusive arguments msg and msg_dict were both '
                    'specified. Please specify only one of msg or msg_dict.')
                logger.error(error_msg)
                raise SmartThreadInvalidInput(error_msg)
            remotes = self._get_set(receivers)
            if not remotes:
                error_msg = (
                    f'SmartThread {threading.current_thread().name} raising '
                    'SmartThreadNoRemoteTargets error while processing '
                    'request smart_send. '
                    f'The receivers argument {receivers=} does not specify '
                    'any receivers.'
                )
                logger.error(error_msg)
                raise SmartThreadNoRemoteTargets(error_msg)
            work_msgs = {remote: msg for remote in remotes}
        elif msg_dict is not None:
            if msg is not None or receivers is not None:
                error_msg = (
                    f'SmartThread {threading.current_thread().name} raising '
                    'SmartThreadInvalidInput error while processing request '
                    'smart_send. '
                    'Mutually exclusive arguments msg_dict and msg or '
                    'msg_dict and receivers were specified.'
                )
                logger.error(error_msg)
                raise SmartThreadInvalidInput(error_msg)

            remotes = set(msg_dict.keys())
            if not remotes:
                error_msg = (
                    f'SmartThread {threading.current_thread().name} raising '
                    'SmartThreadNoRemoteTargets error while processing '
                    'request smart_send. '
                    f'Argument {msg_dict=} was specified with no items.'
                )
                logger.error(error_msg)
                raise SmartThreadNoRemoteTargets(error_msg)
            work_msgs = msg_dict
        else:
            error_msg = (
                f'SmartThread {threading.current_thread().name} raising '
                'SmartThreadInvalidInput error while processing request '
                'smart_send. '
                'The smart_send request failed to specify '
                'msg_dict, or failed to specify both msg and receivers.'
            )
            logger.error(error_msg)
            raise SmartThreadInvalidInput(error_msg)

        # get RequestBlock with targets in a set and a timer object
        request_block = self._request_setup(
            remotes=remotes,
            error_stopped_target=True,
            process_rtn=self._process_send_msg,
            cleanup_rtn=None,
            get_block_lock=False,
            completion_count=len(remotes),
            timeout=timeout,
            msg_to_send=work_msgs,
            log_msg=log_msg)

        self._request_loop(request_block=request_block)

        self.request = ReqType.NoReq

        logger.debug(request_block.exit_log_msg)

        return self.sent_targets

    ####################################################################
    # _process_send_msg
    ####################################################################
    def _process_send_msg(self,
                          request_block: RequestBlock,
                          pk_remote: PairKeyRemote,
                          local_sb: ConnectionStatusBlock,
                          ) -> bool:
        """Process the smart_send request.

        Args:
            request_block: contains request related data
            pk_remote: the pair_key and remote name
            local_sb: connection block for this thread

        Returns:
            True when request completed, False otherwise

        """
        ################################################################
        # The expected path if for the target to be alive and for the
        # msg_q to be empty. In this case, we deliver the msg and
        # return True, and we expect the target to retrieve the msg.
        #
        # If the target msg_q is full we will raise an error.
        #
        # If the target has not yet started and become alive, we will
        # return False and try again after a short pause (unless and
        # until we timeout if timeout was specified).
        #
        # If the target is currently stopped or was stopped since
        # starting this request and is now resurrected, we consider it
        # as stopped and return True. Even though we could deliver the
        # msg if the target is alive now after having been stopped, we
        # can't know whether the target expects the msg at this point.
        # So, we simply consider the target as stopped and return True.
        #
        # If the target is stopped with unread msgs on its msg_q,
        # a log entry is written.
        ################################################################

        remote_state = self._get_target_state(pk_remote)

        if remote_state == ThreadState.Alive:
            # If here, remote is in registry and is alive. This also
            # means we have an entry for the remote in the
            # pair_array

            # setup a reference
            remote_sb = SmartThread._pair_array[
                    pk_remote.pair_key].status_blocks[
                    pk_remote.remote]

            if (remote_sb.target_create_time == 0.0
                    or remote_sb.target_create_time
                    == local_sb.create_time):
                ########################################################
                # put the msg on the target msg_q
                ########################################################
                try:
                    remote_sb.msg_q.put(request_block.msg_to_send[
                                            pk_remote.remote],
                                        timeout=0.01)
                    logger.info(
                        f'{self.name} smart_send sent message to '
                        f'{pk_remote.remote}')

                    self.sent_targets |= {pk_remote.remote}
                    return True
                except queue.Full:
                    # We fail this request when the msg_q is full
                    request_block.full_send_q_remotes |= {pk_remote.remote}
                    return False  # give the remote some more time
        else:
            if remote_state == ThreadState.Stopped:
                request_block.stopped_remotes |= {pk_remote.remote}
                logger.debug(
                    f'{self.name} smart_send detected remote '
                    f'{pk_remote.remote} is stopped')
                # request_block.do_refresh = True
                return True  # we are done with this remote

        return False  # give the remote some more time

    ####################################################################
    # smart_recv
    ####################################################################
    def smart_recv(self,
                   senders: Iterable,
                   sender_count: Optional[int] = None,
                   timeout: OptIntFloat = None,
                   log_msg: Optional[str] = None) -> dict[str, list[Any]]:
        """Receive one or more messages from remote threads.

        Args:
            senders: thread names whose sent messages are to be
                received.
            sender_count: the least number of *senders* that must send a
                message to satisfy the *smart_recv*. If not specified,
                *sender_count* will default to the number of names
                specified for *senders*. If specified, *sender_count*
                must be an integer between 1 and the number of
                *senders*, inclusive.
            timeout: number of seconds to wait for messages
            log_msg: additional text to append to the debug log message
                that is issued on request entry and exit

        Returns:
            A dictionary where the keys are the sender names, and each
            entry contains a list of one or more received messages.
            Note that if *smart_recv* raises an error, the messages
            collected thus far can be recovered from field *recvd_msgs*
            in the SmartThread object that issued the *smart_recv*.

        Raises:
            SmartThreadRemoteThreadNotAlive: target thread was
                stopped.
            SmartThreadRequestTimedOut: request timed out before
                message was received.
            SmartThreadDeadlockDetected: a smart_recv specified a sender
                that issued a smart_recv, smart_wait, or
                smart_sync.

        .. # noqa: DAR402

        Note:

            1) A deadlock will occur between two threads when they both
               issue a request that waits for the other thread to
               respond. The following combinations can lead to a
               deadlock:

                 a) smart_wait vs smart_wait
                 b) smart_wait vs smart_recv
                 c) smart_wait vs smart_sync
                 d) smart_recv vs smart_recv
                 e) smart_recv vs smart_sync

               Note that a smart_wait will not deadlock if the
               wait_event was already resumed earlier by a smart_resume,
               and a smart_recv will not deadlock if a message was
               already delivered earlier by a smart_send.

        For *smart_recv*, a message is any type (e.g., text, lists,
        sets, class objects, etc.). *smart_recv* can be used to receive
        a single message or multiple messages from a single remote
        thread or from multiple remote threads. *smart_recv* will
        return messages in a dictionary indexed by sender thread name.

        When *smart_recv* gets control, it will check its message
        queues for each of the specified senders. If *sender_count* is
        specified, *smart_recv* will return with any found messages as
        soon as the number of threads named in *senders* equals or
        exceeds the *sender_count*. If *sender_count* is not specified,
        *smart_recv* will return with any found messages as soon as all
        *senders* have sent at least one message. If timeout is
        specified, *smart_recv* will raise a timeout error if the
        required number of senders has not yet been achieved within the
        specified time. If any of the specified *senders* are stopped
        before the *smart_recv* has completed, *smart_recv* will raise
        an error.

        If *smart_recv* raises an error, any messages that were received
        will be placed into the SmartThread object in field recvd_msgs
        in case the caller needs to recover them.

        Examples in this section cover the following cases:

            1) receive a single message from a single remote thread
            2) receive a single message from multiple remote threads
            3) receive multiple messages from a single remote thread
            4) receive multiple messages from multiple remote threads

        **Example 1:** receive a single message from a single remote
        thread

        .. code-block:: python

            from scottbrian_paratools.smart_thread import SmartThread
            def f1(smart_thread: SmartThread) -> None:
                print('f1 beta entered')
                smart_thread.smart_send(msg='hi alpha',
                                        receivers='alpha')
                print('f1 beta exiting')

            print('mainline alpha entered')
            alpha_smart_thread = SmartThread(name='alpha')
            beta_smart_thread = SmartThread(name='beta',
                                            target=f1,
                                            thread_parm_name='smart_thread')
            my_msg = alpha_smart_thread.smart_recv(senders='beta')
            print(my_msg)
            alpha_smart_thread.smart_join(targets='beta')
            print('mainline alpha exiting')

        .. invisible-code-block: python

            del SmartThread._registry['alpha']

        Expected output for Example 1::

            mainline alpha entered
            f1 beta entered
            f1 beta exiting
            {'beta': ['hi alpha']}
            mainline alpha exiting

        **Example 2:** receive a single message from multiple remote
        threads

        .. code-block:: python

            from scottbrian_paratools.smart_thread import SmartThread
            import time

            def f1(smart_thread: SmartThread) -> None:
                print(f'f1 {smart_thread.name} entered')
                smart_thread.smart_send(msg=f'{smart_thread.name} says hi',
                                        receivers='alpha')
                print(f'f1 {smart_thread.name} exiting')

            print('mainline alpha entered')
            alpha_smart_thread = SmartThread(name='alpha')
            beta_smart_thread = SmartThread(name='beta',
                                            target=f1,
                                            thread_parm_name='smart_thread')
            time.sleep(0.2)
            charlie_smart_thread = SmartThread(name='charlie',
                                               target=f1,
                                               thread_parm_name='smart_thread')
            time.sleep(0.2)
            my_msg = alpha_smart_thread.smart_recv(senders=('beta', 'charlie'))
            print(my_msg['beta'])
            print(my_msg['charlie'])
            alpha_smart_thread.smart_join(targets=('beta', 'charlie'))
            print('mainline alpha exiting')

        .. invisible-code-block: python

            del SmartThread._registry['alpha']

        Expected output for Example 2::

            mainline alpha entered
            f1 beta entered
            f1 beta exiting
            f1 charlie entered
            f1 charlie exiting
            ['beta says hi']
            ['charlie says hi']
            mainline alpha exiting

        **Example 3:** receive multiple messages from a single remote
        thread

        .. code-block:: python

            from scottbrian_paratools.smart_thread import SmartThread

            def f1(greeting: str, smart_thread: SmartThread) -> None:
                print(f'f1 {smart_thread.name} entered')
                smart_thread.smart_send(msg=f'{greeting}', receivers='alpha')
                smart_thread.smart_send(msg=["great to be here",
                                             "life is good"],
                                        receivers='alpha')
                smart_thread.smart_send(msg=("we should do lunch sometime",
                                             "Tuesday afternoons are best"),
                                        receivers='alpha')
                print(f'f1 {smart_thread.name} exiting')

            print('mainline alpha entered')
            alpha_smart_thread = SmartThread(name='alpha')
            beta_smart_thread = SmartThread(name='beta',
                                            target=f1,
                                            thread_parm_name='smart_thread',
                                            args=('hi',))
            my_msg = alpha_smart_thread.smart_recv(senders='beta')
            print(my_msg)
            alpha_smart_thread.smart_join(targets='beta')
            print('mainline alpha exiting')

        .. invisible-code-block: python

            del SmartThread._registry['alpha']

        Expected output for Example 3::
            mainline alpha entered
            f1 beta entered
            f1 beta exiting
            {'beta': ['hi', ["it's great to be here", "life is good"],
            ("let's do lunch sometime", "Tuesday afternoons are best")]}
            mainline alpha exiting

        **Example 4:** receive any mixture of single and multiple
        messages from specified remote threads

        .. code-block:: python

            from scottbrian_paratools.smart_thread import SmartThread

            def f1(greeting: str,
                   smart_thread: SmartThread,
                   wait_for: Optional[str] = None,
                   resume_target: Optional[str] = None) -> None:
                if wait_for:
                   smart_thread.smart_wait(resumers=wait_for)
                print(f'f1 {smart_thread.name} entered')
                smart_thread.smart_send(msg=f'{greeting}', receivers='alpha')
                if smart_thread.name in ('charlie', 'delta'):
                    smart_thread.smart_send(msg=["miles to go", (1, 2, 3)],
                                            receivers='alpha')
                if smart_thread.name == 'delta':
                    smart_thread.smart_send(msg={'forty_two': 42, 42: 42},
                                            receivers='alpha')
                print(f'f1 {smart_thread.name} exiting')
                if resume_target:
                    smart_thread.smart_resume(waiters=resume_target)

            print('mainline alpha entered')
            alpha_smart_thread = SmartThread(name='alpha')
            beta_smart_thread = SmartThread(name='beta',
                                            target=f1,
                                            thread_parm_name='smart_thread',
                                            args=('hi',),
                                            kwargs={
                                                'resume_target':'charlie'})
            charlie_smart_thread = SmartThread(name='charlie',
                                               target=f1,
                                               thread_parm_name='smart_thread',
                                               args=('hello',),
                                               kwargs={
                                                   'wait_for': 'beta',
                                                   'resume_target':'delta'})
            delta_smart_thread = SmartThread(name='delta',
                                             target=f1,
                                             thread_parm_name='smart_thread',
                                             args=('aloha',),
                                             kwargs={'wait_for': 'charlie',
                                                     'resume_target': 'alpha'})
            alpha_smart_thread.smart_wait(resumers='delta')
            my_msg = alpha_smart_thread.smart_recv(senders={'beta', 'delta'})
            print(my_msg['beta'])
            print(my_msg['delta'])
            my_msg = alpha_smart_thread.smart_recv(senders={'charlie'})
            print(my_msg)
            alpha_smart_thread.smart_join(targets=('beta',
                                                   'charlie',
                                                   'delta'))
            print('mainline alpha exiting')

        .. invisible-code-block: python

            del SmartThread._registry['alpha']

        Expected output for Example 4::

            mainline alpha entered
            f1 beta entered
            f1 beta exiting
            f1 charlie entered
            f1 charlie exiting
            f1 delta entered
            f1 delta exiting
            ['hi']
            ['aloha', ['miles to go', (1, 2, 3)], {'forty_two': 42, 42: 42}]
            {'charlie': ['hi'], ['miles to go', (1, 2, 3)]}
            mainline alpha exiting

        """
        self._verify_thread_is_current(request=ReqType.Smart_recv)
        self.request = ReqType.Smart_recv
        self.recvd_msgs = {}

        if sender_count is None:
            completion_count = len(self._get_set(senders))
        else:
            if (not isinstance(sender_count, int)
                    or sender_count < 1
                    or len(self._get_set(senders)) < sender_count):
                error_msg = (
                    f'SmartThread {threading.current_thread().name} raising '
                    'SmartThreadInvalidInput error while processing request '
                    'smart_recv. '
                    f'The value specified for {sender_count=} is not valid. '
                    'The number of specified senders is '
                    f'{len(self._get_set(senders))}. The value for '
                    'sender_count must be an integer between 1 and the '
                    'number of specified senders, inclusive.')
                logger.error(error_msg)
                raise SmartThreadInvalidInput(error_msg)
            completion_count = sender_count

        # get RequestBlock with targets in a set and a timer object
        request_block = self._request_setup(
            remotes=senders,
            error_stopped_target=True,
            process_rtn=self._process_recv_msg,
            cleanup_rtn=None,
            get_block_lock=False,
            completion_count=completion_count,
            timeout=timeout,
            log_msg=log_msg)

        self._request_loop(request_block=request_block)

        logger.debug(request_block.exit_log_msg)

        self.request = ReqType.NoReq

        return self.recvd_msgs

    ####################################################################
    # _process_recv_msg
    ####################################################################
    def _process_recv_msg(self,
                          request_block: RequestBlock,
                          pk_remote: PairKeyRemote,
                          local_sb: ConnectionStatusBlock,
                          ) -> bool:
        """Process the smart_recv request.

        Args:
            request_block: contains request related data
            pk_remote: the pair_key and remote name
            local_sb: connection block for this thread

        Returns:
            True when request completed, False otherwise

        """
        # We start off assuming the remote is alive and we have a msg,
        # meaning we make the timeout_value very small just to test
        # the msg_q. If there is no msg, we check the remote state
        # and to decide whether to fail the smart_recv (remote
        # stopped), try to retrieve the msg again with a longer
        # timeout_value (remote alive), or return False to give
        # the remote more time (remote is not alive, but not stopped)

        for timeout_value in (SmartThread.K_REQUEST_MIN_INTERVAL,
                              request_block.request_max_interval):
            try:
                # recv message from remote
                with SmartThread._pair_array[pk_remote.pair_key].status_lock:
                    recvd_msg = local_sb.msg_q.get(timeout=timeout_value)
                    # self.recvd_msgs[pk_remote.remote].append(recvd_msg)
                    self.recvd_msgs[pk_remote.remote] = [recvd_msg]
                    while not local_sb.msg_q.empty():
                        recvd_msg = local_sb.msg_q.get()
                        self.recvd_msgs[pk_remote.remote].append(recvd_msg)

                    if ((num_msgs := len(self.recvd_msgs[pk_remote.remote]))
                            > 1):
                        msg_msgs = 'msgs'
                    else:
                        msg_msgs = 'msg'
                    logger.info(
                        f'{self.name} smart_recv received {num_msgs} '
                        f'{msg_msgs} from {pk_remote.remote}')
                    # reset recv_wait after we get messages instead of
                    # before so as to avoid having the flag being
                    # momentarily False with the msg_q empty in the
                    # small gap between the try attempt and an
                    # exception. This will prevent the remote from
                    # missing a deadlock detection case during the gap.
                    local_sb.recv_wait = False

                # if here, msg_q was not empty (i.e., no exception)

                # if we had wanted to delete an entry in the
                # pair array for this thread because the other
                # thread exited, but we could not because this
                # thread had a pending msg to recv, then we
                # deferred the delete. If the msg_q for this
                # thread is now empty as a result of this recv,
                # we can go ahead and delete the pair, so
                # set the flag to do a refresh
                # if (local_sb.del_deferred
                #         and not local_sb.wait_event.is_set()
                #         and not local_sb.sync_event.is_set()):
                #     request_block.do_refresh = True
                return True

            except queue.Empty:
                # The msg queue was just now empty which rules out
                # that case that the pair_key is valid only because
                # of a deferred delete. So, we know the remote is in
                # the registry and in the status block.

                # remote_state = self._get_target_state(pk_remote)
                #
                # if remote_state == ThreadState.Stopped:
                #     request_block.stopped_remotes |= {pk_remote.remote}
                #     request_block.do_refresh = True
                #     return True  # we are done with this remote
                #
                # if remote_state != ThreadState.Alive:
                #     return False  # remote needs more time
                with SmartThread._pair_array[pk_remote.pair_key].status_lock:
                    local_sb.recv_wait = True
                    # Check for error conditions first before
                    # checking whether the remote is alive. If the
                    # remote detects a deadlock issue,
                    # it will set the flags in our entry and then
                    # raise an error and will likely be gone when we
                    # check. We want to raise the same error on
                    # this side.
                    #
                    # self.deadlock is set only by the remote. So,
                    # if self.deadlock is True, then remote has
                    # already detected the deadlock, set our flag,
                    # raised the deadlock on its side, and is now
                    # possibly ended or recovered and in a new wait.
                    # If self.deadlock is False, and remote is
                    # waiting and is not resumed then it will not be
                    # getting resumed by us since we are also
                    # waiting. So, we set self.remote.deadlock to
                    # tell it, and then we raise the error on our
                    # side. But, we don't do this if the
                    # self.remote.deadlock is already on as that
                    # suggests that we already told remote and
                    # raised the error, which implies that we are in
                    # a new wait and the remote has not yet woken up
                    # to deal with the earlier deadlock. We can
                    # simply ignore it for now.
                    # We could allow the deadlock to persist if timeout
                    # was specified on either request since the timeout
                    # will eventually break the deadlock, but the end
                    # result is similar in that an error will be raised.
                    # It will be better to raise the error sooner than
                    # waiting for the timeout expiration error.
                    if pk_remote.remote in SmartThread._pair_array[
                            pk_remote.pair_key].status_blocks:
                        remote_sb = SmartThread._pair_array[
                            pk_remote.pair_key].status_blocks[pk_remote.remote]

                        self._check_for_deadlock(local_sb=local_sb,
                                                 remote_sb=remote_sb)

                    if local_sb.deadlock:
                        local_sb.deadlock = False
                        local_sb.recv_wait = False
                        request_block.deadlock_remotes |= {pk_remote.remote}
                        request_block.remote_deadlock_request = (
                            local_sb.remote_deadlock_request)
                        logger.debug(
                            f'TestDebug {self.name} recv set '
                            f'{pk_remote.remote=}'
                            f'{request_block.deadlock_remotes=}')
                        return True

                    if self._get_target_state(
                            pk_remote) == ThreadState.Stopped:
                        request_block.stopped_remotes |= {pk_remote.remote}
                        logger.debug(
                            f'{self.name} smart_recv detected remote '
                            f'{pk_remote.remote} is stopped')
                        # request_block.do_refresh = True
                        local_sb.recv_wait = False
                        return True  # we are done with this remote
                    else:
                        # if not stopped, then we know remote is active
                        # since we set sync_wait to True
                        return False  # remote needs more time

    ####################################################################
    # wait
    ####################################################################
    def smart_wait(self, *,
                   resumers: Optional[Iterable] = None,
                   resumer_count: Optional[int] = None,
                   timeout: OptIntFloat = None,
                   log_msg: Optional[str] = None) -> set[str]:
        """Wait until resumed.

        Args:
            resumers: thread names that the *smart_wait* expects to
                provide matching *smart_resume* requests.
            resumer_count: the least number of *resumers* that must
                provide a matching *smart_resume* to satisfy the
                *smart_wait*. If not specified, *resumer_count* will
                default to the number of names specified for *resumers*.
                If specified, *resumer_count* must be an integer between
                1 and the number of *resumers*, inclusive.
            timeout: number of seconds to allow for *smart_wait* to be
                resumed.
            log_msg: additional text to append to the debug log message
                that is issued on request entry and exit

        Returns:
            A set of thread names that *smart_wait* detects as having
            provided a matching *smart_resume*. The number of names in
            the set may be larger than the value specified for
            *resumer_count*. If *smart_wait* raises an error, the set of
            names collected thus far can be recovered from field
            *resumed_by* in the SmartThread object that issued the
            *smart_wait*.

        Raises:
            SmartThreadDeadlockDetected: a smart_wait specified a
                resumer that issued a smart_recv, smart_wait, or
                smart_sync.
            SmartThreadRemoteThreadNotAlive: resumer thread was
                stopped.
            SmartThreadRequestTimedOut: request timed out before
                being resumed.
        .. # noqa DAR402

        Notes:

            1) A deadlock will occur between two threads when they both
               issue a request that waits for the other thread to
               respond. The following combinations can lead to a
               deadlock:

                 a) smart_wait vs smart_wait
                 b) smart_wait vs smart_recv
                 c) smart_wait vs smart_sync
                 d) smart_recv vs smart_recv
                 e) smart_recv vs smart_sync

               Note that a smart_wait will not deadlock if the
               wait_event was already resumed earlier by a smart_resume,
               and a smart_recv will not deadlock if a message was
               already delivered earlier by a smart_send.

        smart_wait waits until it is resumed. These are the cases:

            1) smart_wait can provide one remote thread name as an
               argument for the *resumers* parameter and will then wait
               until that resumer issues a matching smart_resume.
            2) smart_wait can provide multiple remote thread names as an
               argument for the *resumers* parameter and will then wait
               for:
               a) at least the number of resumes specified for
                  *resumer_count*
               b) all specified *resumers* if *resumer_count* is not
                  specified

        *smart_wait* will raise an error if any of the specified
        *resumers* become inactive before the *smart_wait* is satisfied.

        If timeout is specified, *smart_wait* will raise an error if not
        satisfied within the specified time.

        Note that a smart_resume can be issued before the smart_wait is
        issued, in which case the smart_wait will return immediately
        if any and all expected resumes were already issued.

        Examples in this section cover the following cases:

            1) smart_wait followed by smart_resume
            2) smart_wait preceded by smart_resume
            3) smart_wait for multiple resumers
            4) smart_wait for multiple resumers with resumer_count

        **Example 1:** smart_wait followed by smart_resume

        .. code-block:: python

            from scottbrian_paratools.smart_thread import SmartThread
            import time

            def f1(smart_thread: SmartThread) -> None:
                print(f'f1 {smart_thread.name} about to wait')
                resumers = smart_thread.smart_wait(resumers='alpha')
                print(f'f1 {smart_thread.name} resumed by {resumers=}')

            print('mainline alpha entered')
            alpha_smart_thread = SmartThread(name='alpha')
            beta_smart_thread = SmartThread(name='beta',
                                            target=f1,
                                            thread_parm_name='smart_thread')
            time.sleep(1)  # allow time for smart_wait to be issued
            print('alpha about to resume beta')
            alpha_smart_thread.smart_resume(waiters='beta')
            alpha_smart_thread.smart_join(targets='beta')
            print('mainline alpha exiting')

        .. invisible-code-block: python

            del SmartThread._registry['alpha']

        Expected output for Example 1::

            mainline alpha entered
            f1 beta about to wait
            alpha about to resume beta
            f1 beta resumed by resumers=['alpha']
            mainline alpha exiting

        **Example 2:** smart_wait preceded by smart_resume

        .. code-block:: python

            from scottbrian_paratools.smart_thread import SmartThread
            import time

            def f1(smart_thread: SmartThread) -> None:
                time.sleep(1)  # allow time for smart_resume to be issued
                print(f'f1 {smart_thread.name} about to wait')
                resumers = smart_thread.smart_wait(resumers='alpha')
                print(f'f1 {smart_thread.name} resumed by {resumers=}')

            print('mainline alpha entered')
            alpha_smart_thread = SmartThread(name='alpha')
            beta_smart_thread = SmartThread(name='beta',
                                            target=f1,
                                            thread_parm_name='smart_thread')
            print('alpha about to resume beta')
            alpha_smart_thread.smart_resume(waiters='beta')
            alpha_smart_thread.smart_join(targets='beta')
            print('mainline alpha exiting')

        .. invisible-code-block: python

            del SmartThread._registry['alpha']

        Expected output for Example 2::

            mainline alpha entered
            alpha about to resume beta
            f1 beta about to wait
            f1 beta resumed by resumers=['alpha']
            mainline alpha exiting

        **Example 3:** smart_wait for multiple resumers

        .. code-block:: python

            from scottbrian_paratools.smart_thread import SmartThread, WaitFor
            import time

            def f1(smart_thread: SmartThread) -> None:
                print(f'f1 {smart_thread.name} about to resume alpha')
                smart_thread.smart_resume(waiters='alpha')

            print('mainline alpha entered')
            alpha_smart_thread = SmartThread(name='alpha')
            beta_smart_thread = SmartThread(name='beta',
                                            target=f1,
                                            thread_parm_name='smart_thread')
            time.sleep(1)  # allow time for alpha to wait
            charlie_smart_thread = SmartThread(name='charlie',
                                               target=f1,
                                               thread_parm_name='smart_thread')
            time.sleep(1)  # allow time for alpha to wait
            delta_smart_thread = SmartThread(name='delta',
                                             target=f1,
                                             thread_parm_name='smart_thread')
            time.sleep(1)  # allow time for alpha to wait
            print('alpha about to wait for all threads')
            resumers = alpha_smart_thread.smart_wait(
                resumers=['beta', 'charlie', 'delta'])
            print(f'f1 alpha resumed by resumers={sorted(resumers)}')
            alpha_smart_thread.smart_join(targets=['beta', 'charlie', 'delta'])
            print('mainline alpha exiting')

        .. invisible-code-block: python

            del SmartThread._registry['alpha']

        Expected output for Example 3::

            mainline alpha entered
            f1 beta about to resume alpha
            f1 charlie about to resume alpha
            f1 delta about to resume alpha
            alpha about to wait for all threads
            alpha resumed by resumers=['beta', 'charlie', 'delta']
            mainline alpha exiting

        **Example 4:** smart_wait for multiple resumers with WaitFor.Any

        .. code-block:: python

            from scottbrian_paratools.smart_thread import SmartThread, WaitFor
            import time

            def f1(smart_thread: SmartThread) -> None:
                print(f'f1 {smart_thread.name} about to resume alpha')
                smart_thread.smart_resume(waiters='alpha')

            print('mainline alpha entered')
            alpha_smart_thread = SmartThread(name='alpha')
            beta_smart_thread = SmartThread(name='beta',
                                            target=f1,
                                            thread_parm_name='smart_thread')
            time.sleep(1)
            charlie_smart_thread = SmartThread(name='charlie',
                                               target=f1,
                                               thread_parm_name='smart_thread')
            time.sleep(1)
            print('alpha about to wait for any threads')
            resumers = alpha_smart_thread.smart_wait(
                resumers=['beta', 'charlie', 'delta'])
            print(f'alpha resumed by resumers={sorted(resumers)}')
            delta_smart_thread = SmartThread(name='delta',
                                             target=f1,
                                             thread_parm_name='smart_thread')
            time.sleep(1)  # allow time for alpha to wait
            print('alpha about to wait for any threads')
            resumers = alpha_smart_thread.smart_wait(
                resumers=['beta', 'charlie', 'delta'])
            print(f'alpha resumed by resumers={sorted(resumers)}')
            alpha_smart_thread.smart_join(targets=['beta', 'charlie', 'delta'])
            print('mainline alpha exiting')

        .. invisible-code-block: python

            del SmartThread._registry['alpha']

        Expected output for Example 4::

            mainline alpha entered
            f1 beta about to resume alpha
            f1 charlie about to resume alpha
            alpha about to wait for any threads
            alpha resumed by resumers=['beta', 'charlie']
            f1 delta about to resume alpha
            alpha about to wait for any threads
            alpha resumed by resumers=['delta']
            mainline alpha exiting

        """
        self._verify_thread_is_current(request=ReqType.Smart_wait)
        self.request = ReqType.Smart_wait
        self.resumed_by = set()

        if resumer_count is None:
            completion_count = len(self._get_set(resumers))
        else:
            if (not isinstance(resumer_count, int)
                    or resumer_count < 1
                    or len(self._get_set(resumers)) < resumer_count):
                error_msg = (
                    f'SmartThread {threading.current_thread().name} raising '
                    'SmartThreadInvalidInput error while processing request '
                    'smart_wait. '
                    f'The value specified for {resumer_count=} is not valid. '
                    'The number of specified resumers is '
                    f'{len(self._get_set(resumers))}. The value for '
                    'resumer_count must be an integer between 1 and the '
                    'number of specified resumers, inclusive.')
                logger.error(error_msg)
                raise SmartThreadInvalidInput(error_msg)
            completion_count = resumer_count

        # get RequestBlock with targets in a set and a timer object
        request_block = self._request_setup(
            remotes=resumers,
            error_stopped_target=True,
            process_rtn=self._process_wait,
            cleanup_rtn=self._sync_wait_error_cleanup,
            get_block_lock=True,
            completion_count=completion_count,
            timeout=timeout,
            log_msg=log_msg)

        self._request_loop(request_block=request_block)

        logger.debug(request_block.exit_log_msg)

        self.request = ReqType.NoReq

        return self.resumed_by

    ####################################################################
    # _process_wait
    ####################################################################
    def _process_wait(self,
                      request_block: RequestBlock,
                      pk_remote: PairKeyRemote,
                      local_sb: ConnectionStatusBlock,
                      ) -> bool:
        """Process the sync request.

        Args:
            request_block: contains request related data
            pk_remote: the pair_key and remote name
            local_sb: connection block for this thread

        Returns:
            True when request completed, False otherwise

        """
        # We don't check to ensure remote is alive since it may have
        # resumed us and then ended. So, we check the wait_event first,
        # and then we will check to see whether the remote is alive.
        # We start off assuming remote has set our wait event,
        # meaning we make the timeout_value very small just to test
        # the event. If the event is not set, we check the remote state
        # and to decide whether to fail the smart_wait (remote
        # stopped), try again with a longer
        # timeout_value (remote alive), or return False to give
        # the remote more time (remote is not alive, but no stopped)
        for timeout_value in (SmartThread.K_REQUEST_MIN_INTERVAL,
                              request_block.request_max_interval):
            if local_sb.wait_event.wait(timeout=timeout_value):
                # We need to the lock to coordinate with the remote
                # deadlock detection code to prevent:
                # 1) the remote sees that the wait_wait flag is True
                # 2) we reset wait_wait
                # 3) we clear the wait event
                # 4) the remote sees the wait event is clear and decides
                #    we have a deadlock
                with SmartThread._pair_array[pk_remote.pair_key].status_lock:
                    local_sb.wait_wait = False

                    # be ready for next wait
                    local_sb.wait_event.clear()

                # if (local_sb.del_deferred
                #         and local_sb.msg_q.empty()
                #         and not local_sb.sync_event.is_set()):
                #     request_block.do_refresh = True
                logger.info(
                    f'{self.name} smart_wait resumed by '
                    f'{pk_remote.remote}')
                self.resumed_by |= {pk_remote.remote}

                return True

            with SmartThread._pair_array[pk_remote.pair_key].status_lock:
                local_sb.wait_wait = True
                # Check for error conditions first before
                # checking whether the remote is alive. If the
                # remote detects a deadlock issue,
                # it will set the flags in our entry and then
                # raise an error and will likely be gone when we
                # check. We want to raise the same error on
                # this side.
                #
                # self.deadlock is set only by the remote. So,
                # if self.deadlock is True, then remote has
                # already detected the deadlock, set our flag,
                # raised the deadlock on its side, and is now
                # possibly ended or recovered and in a new wait.
                # If self.deadlock is False, and remote is
                # waiting and is not resumed then it will not be
                # getting resumed by us since we are also
                # waiting. So, we set self.remote.deadlock to
                # tell it, and then we raise the error on our
                # side. But, we don't do this if the
                # self.remote.deadlock is already on as that
                # suggests that we already told remote and
                # raised the error, which implies that we are in
                # a new wait and the remote has not yet woken up
                # to deal with the earlier deadlock. We can
                # simply ignore it for now.
                if pk_remote.remote in SmartThread._pair_array[
                        pk_remote.pair_key].status_blocks:
                    remote_sb = SmartThread._pair_array[
                        pk_remote.pair_key].status_blocks[pk_remote.remote]
                    self._check_for_deadlock(local_sb=local_sb,
                                             remote_sb=remote_sb)

                if local_sb.deadlock:
                    local_sb.deadlock = False
                    local_sb.wait_wait = False
                    request_block.deadlock_remotes |= {pk_remote.remote}
                    logger.debug(
                        f'TestDebug {self.name} wait set {pk_remote.remote=}'
                        f'{request_block.deadlock_remotes=}')
                    return True

                if self._get_target_state(pk_remote) == ThreadState.Stopped:
                    request_block.stopped_remotes |= {pk_remote.remote}
                    logger.debug(
                        f'{self.name} smart_wait detected remote '
                        f'{pk_remote.remote} is stopped')
                    # request_block.do_refresh = True
                    local_sb.wait_wait = False
                    return True  # we are done with this remote
                else:
                    # if not stopped, then we know remote is active
                    # since we set sync_wait to True
                    return False  # remote needs more time

    ####################################################################
    # resume
    ####################################################################
    def smart_resume(self, *,
                     waiters: Iterable,
                     timeout: OptIntFloat = None,
                     log_msg: Optional[str] = None) -> set[str]:
        """Resume a waiting or soon to be waiting thread.

        Args:
            waiters: names of threads that are to be resumed
            timeout: number of seconds to allow for ``resume()`` to
                complete
            log_msg: additional text to append to the debug log message
                that is issued on request entry and exit

        Returns:
            A set of the thread names that were resumed. Note that if
            *smart_resume* raises an error, the thread names that
            were resumed thus far can be recovered from field
            *resumed_targets* in the SmartThread object that issued the
            *smart_resume*.

        Raises:
            SmartThreadRemoteThreadNotAlive: waiter thread was
                stopped.
            SmartThreadRequestTimedOut: request timed out before
                being resumed.

        .. # noqa: DAR402

        **Notes:**

            1) The ``smart_wait()`` and ``smart_resume()`` processing
               use a threading event to coordinate the wait and resume.
               The ``smart_wait()`` will wait on the event and the
               ``smart_resume()`` will set the event, not necessarily
               in that order.
            2) A ``smart_resume()`` request can set the event for a
               waiter that has not yet issued a ``smart_wait()``. This
               is referred to as a **pre-resume**. The remote thread
               doing a ``smart_wait()`` request in this case will simply
               see that the event is already set, clear it, and return
               immediately.
            3) Once the ``smart_resume()`` request has set the waiter's
               event, it is unpredictable when the waiter will clear
               the event. If a subsequent ``smart_resume()`` is issued
               before the event has been cleared, it will loop until the
               waiter clears it or a timeout occurs.
            4) ``smart_resume()`` will set the event only for a thread
               that is in the alive state. Once the event is set, the
               ``smart_resume()`` is considered complete. The waiter
               thread may subsequently fail and move to the stopped
               state before clearing the event. No error is raised by
               ``smart_resume()`` nor ``smart_wait()`` in this case. A
               debug log message is issued when a thread is removed
               from the configuration with its wait event still set.

        smart_resume is used for the following cases:

            1) to resume a thread that is blocked after having issued a
               smart_wait
            2) to pre-resume a thread that will be issuing a smart_wait.
               In this case, the smart_wait will simply see that it has
               already been resumed and will return immediately.
            3) to resume or pre-resume multiple threads as a combination
               of zero or more case #1 scenarios and zero or more case
               #2 scenarios.

        An error is raised if any of the specified waiter threads are
        stopped.

        A smart_resume may be issued for any number of waiters that are
        in any combination of unregistered, registered, or alive states.
        smart_resume will perform the resume only when a waiter is in
        the alive state. If timeout is specified, a timeout error is
        raised if one or more waiters fail to achieve the alive state
        within the specified time.

        Another case involving a timeout can occur when a previous
        smart_wait has not yet completed after having been resumed,
        and a new resume is issued. See the notes section above for a
        more thorough explanation.

        **Example 1:** Invoke ''smart_resume()'' for threads that invoke
        ''smart_wait()'' both before and after the ''smart_resume()''

        .. code-block:: python

            from scottbrian_paratools.smart_thread import SmartThread
            import time

            def f1_beta(smart_thread: SmartThread) -> None:
                print(f'f1_beta about to wait')
                smart_thread.smart_wait(resumers='alpha')
                print(f'f1_beta back from wait')

            def f2_charlie(smart_thread: SmartThread) -> None:
                time.sleep(1)
                print(f'f2_charlie about to wait')
                smart_thread.smart_wait(resumers='alpha')
                time.sleep(1)
                print(f'f2_charlie back from wait')

            def f3_delta(smart_thread: SmartThread) -> None:
                time.sleep(4)
                print(f'f3_delta about to wait')
                smart_thread.smart_wait(resumers='alpha')
                print(f'f3_delta back from wait')

            def f4_echo(smart_thread: SmartThread) -> None:
                time.sleep(5)
                print(f'f4_echo about to wait')
                smart_thread.smart_wait(resumers='alpha')
                print(f'f4_echo back from wait')

            print('mainline alpha entered')
            alpha_smart_thread = SmartThread(name='alpha')
            beta_smart_thread = SmartThread(name='beta',
                                            target=f1_beta,
                                            thread_parm_name='smart_thread')
            charlie_smart_thread = SmartThread(name='charlie',
                                               target=f2_charlie,
                                               thread_parm_name='smart_thread')
            delta_smart_thread = SmartThread(name='delta',
                                             target=f3_delta,
                                             thread_parm_name='smart_thread')
            echo_smart_thread = SmartThread(name='echo',
                                            target=f4_echo,
                                            thread_parm_name='smart_thread')
            time.sleep(2)
            print('alpha about to resume threads')
            alpha_smart_thread.smart_resume(waiters=('beta',
                                                     'charlie',
                                                     'delta',
                                                     'echo'))
            alpha_smart_thread.smart_join(targets=['beta',
                                                   'charlie',
                                                   'delta',
                                                   'echo'])
            print('mainline alpha exiting')

        .. invisible-code-block: python

            del SmartThread._registry['alpha']

        Expected output for Example 1:

            mainline alpha entered
            f1_beta about to wait
            f2_charlie about to wait
            alpha about to resume threads
            f1_beta back from wait
            f2_charlie back from wait
            f3_delta about to wait
            f3_delta back from wait
            f4_echo about to wait
            f4_echo back from wait
            mainline alpha exiting

        """
        ################################################################
        # Cases where we loop until remote is ready:
        # 1) Remote waiting and event already resumed. This is a case
        #    where the remote was previously resumed and has not yet
        #    been given control to exit the wait. If and when that
        #    happens, this resume will complete as a pre-resume.
        # 2) Remote waiting and deadlock. The remote was flagged as
        #    being in a deadlock and has not been given control to
        #    raise the SmartThreadDeadlockDetected error. The remote
        #    could recover, in which case this resume will complete,
        #    or the thread could become inactive, in which case
        #    resume will see that and raise the
        #    SmartThreadRemoteThreadNotAlive error.
        # 3) Remote not waiting and event resumed. This case
        #    indicates that a resume was previously done ahead of the
        #    wait as a pre-resume. In that case an eventual wait is
        #    expected to be requested by the remote thread to clear
        #    the flag at which time this resume will succeed in doing a
        #    pre-resume.
        ################################################################

        ################################################################
        # Cases where we do the resume:
        # 1) Remote is waiting, event is not resumed, and the deadlock
        #    flag is False. This is the most expected case in a
        #    normally running system where the remote put something in
        #    action and is now waiting on a response (the resume) that
        #    the action is complete.
        # 2) Remote is not waiting, not sync_wait, and event not
        #    resumed. This is a case where we will do a pre-resume and
        #    the remote is expected to do the wait momentarily.
        # 3) Remote is not waiting, but is sync waiting, and event not
        #    resumed. This case is identical to case 2 from a resume
        #    perspective since the sync_wait does not interfere with
        #    the event that the resume operates on. So, we will do
        #    a pre-resume and the expectation in that this
        #    thread will then complete the sync with the remote
        #    who will next do a wait against the pre-resume. The
        #    vertical time line for both sides could be represented as
        #    such:
        #
        #        Current Thread                   Remote Thread
        #                                           sync
        #              resume
        #              sync
        #                                           wait
        ###############################################################
        self._verify_thread_is_current(request=ReqType.Smart_resume)
        self.request = ReqType.Smart_resume
        self.resumed_targets = set()
        # get RequestBlock with targets in a set and a timer object
        request_block = self._request_setup(
            remotes=waiters,
            error_stopped_target=True,
            process_rtn=self._process_resume,
            cleanup_rtn=None,
            get_block_lock=True,
            completion_count=len(self._get_set(waiters)),
            timeout=timeout,
            log_msg=log_msg)

        self._request_loop(request_block=request_block)

        self.request = ReqType.NoReq

        logger.debug(request_block.exit_log_msg)

        return self.resumed_targets

    ####################################################################
    # _process_resume
    ####################################################################
    def _process_resume(self,
                        request_block: RequestBlock,
                        pk_remote: PairKeyRemote,
                        local_sb: ConnectionStatusBlock,
                        ) -> bool:
        """Process the resume request.

        Args:
            request_block: contains request related data
            pk_remote: the pair_key and remote name
            local_sb: connection block for this thread

        Returns:
            True when request completed, False otherwise

        """
        remote_state = self._get_target_state(pk_remote)

        if remote_state == ThreadState.Alive:
            # If here, remote is in registry and is alive. This also
            # implies we have an entry for the remote in the
            # pair_array

            # set up a reference
            remote_sb = SmartThread._pair_array[
                pk_remote.pair_key].status_blocks[
                pk_remote.remote]

            ########################################################
            # set wait_event
            ########################################################
            # For a resume request we check to see whether a
            # previous wait is still in progress as indicated by the
            # wait event being set, or if it has yet to recognize a
            # deadlock.
            if not (remote_sb.wait_event.is_set()
                    or remote_sb.deadlock):
                if (remote_sb.target_create_time == 0.0
                        or remote_sb.target_create_time
                        == local_sb.create_time):
                    # wake remote thread and start
                    # the while loop again with one
                    # less remote
                    remote_sb.wait_event.set()
                    logger.info(
                        f'{self.name} smart_resume resumed '
                        f'{pk_remote.remote}')
                    self.resumed_targets |= {pk_remote.remote}
                    return True
        else:
            if remote_state == ThreadState.Stopped:
                request_block.stopped_remotes |= {pk_remote.remote}
                logger.debug(
                    f'{self.name} smart_resume detected remote '
                    f'{pk_remote.remote} is stopped')
                # request_block.do_refresh = True
                return True  # we are done with this remote

        # remote is not yet alive, has pending wait, or pending deadlock
        return False  # give the remote some more time

    ####################################################################
    # smart_sync
    ####################################################################
    def smart_sync(self, *,
                   targets: Iterable,
                   timeout: OptIntFloat = None,
                   log_msg: Optional[str] = None) -> set[str]:
        """Sync up with remote threads.

        Args:
            targets: remote threads we will sync with
            timeout: number of seconds to allow for sync to happen
            log_msg: additional text to append to the debug log message
                that is issued on request entry and exit

        Returns:
            A set of the thread names that were synced. Note that if
            *smart_sync* raises an error, the thread names that
            were synced thus far can be recovered from field
            *synced_targets* in the SmartThread object that issued the
            *smart_sync*.

        Notes:
            1) A deadlock will occur between two threads when they both
               issue a request that waits for the other thread to
               respond. The following combinations can lead to a
               deadlock:

                 a) smart_wait vs smart_wait
                 b) smart_wait vs smart_recv
                 c) smart_wait vs smart_sync
                 d) smart_recv vs smart_recv
                 e) smart_recv vs smart_sync

               Note that a smart_wait will not deadlock if the
               wait_event was already resumed earlier by a smart_resume,
               and a smart_recv will not deadlock if a message was
               already delivered earlier by a smart_send.

        Each thread that invokes ''smart_sync()'' first sets the sync
        event for each target, and the waits on its corresponding sync
        event for each target. This ensures that every thread has
        reached the sync point before any thread moves forward from
        there.

        **Example 1:** Invoke ``smart_sync()`` for three threads

        .. code-block:: python

            from scottbrian_paratools.smart_thread import SmartThread
            import time

            def f1_beta(smart_thread: SmartThread) -> None:
                print('f1_beta about to sync with alpha and charlie')
                smart_thread.smart_sync(targets=['alpha', 'charlie'])
                print('f1_beta back from sync')

            def f2_charlie(smart_thread: SmartThread) -> None:
                print('f2_charlie about to sync with alpha and beta')
                smart_thread.smart_sync(targets=['alpha', 'beta'])
                time.sleep(1)
                print('f2_charlie back from sync')

            print('mainline alpha entered')
            alpha_smart_thread  = SmartThread(name='alpha')
            beta_smart_thread = SmartThread(name='beta',
                                            target=f1_beta,
                                            thread_parm_name='smart_thread')
            time.sleep(1)
            charlie_smart_thread = SmartThread(name='charlie',
                                               target=f2_charlie,
                                               thread_parm_name='smart_thread')
            time.sleep(1)
            print('alpha about to sync with beta and charlie')
            alpha_smart_thread.smart_sync(targets=['beta', 'charlie'])
            time.sleep(2)
            print('alpha back from sync')
            alpha_smart_thread.smart_join(targets=['beta', 'charlie'])
            print('mainline alpha exiting')

        .. invisible-code-block: python

            del SmartThread._registry['alpha']

        Expected output for Example 1:

            mainline alpha entered
            f1_beta about to sync with alpha and charlie
            f2_charlie about to sync with alpha and beta
            alpha about to sync with beta and charlie
            f1_beta back from sync
            f2_charlie back from sync
            alpha back from sync
            mainline alpha exiting

        """
        self._verify_thread_is_current(request=ReqType.Smart_sync)
        self.request = ReqType.Smart_sync
        self.synced_targets = set()
        # get RequestBlock with targets in a set and a timer object
        request_block = self._request_setup(
            remotes=targets,
            error_stopped_target=True,
            process_rtn=self._process_sync,
            cleanup_rtn=self._sync_wait_error_cleanup,
            get_block_lock=True,
            completion_count=len(self._get_set(targets)),
            timeout=timeout,
            log_msg=log_msg)

        self._request_loop(request_block=request_block)

        self.request = ReqType.NoReq

        logger.debug(request_block.exit_log_msg)

        return self.synced_targets

    ####################################################################
    # _process_sync
    ####################################################################
    def _process_sync(self,
                      request_block: RequestBlock,
                      pk_remote: PairKeyRemote,
                      local_sb: ConnectionStatusBlock,
                      ) -> bool:
        """Process the sync request.

        Args:
            request_block: contains request related data
            pk_remote: the pair_key and remote name
            local_sb: connection block for this thread

        Returns:
            True when request completed, False otherwise

        """
        ####################################################
        # set remote sync_event
        ####################################################
        if not local_sb.sync_wait:
            remote_state = self._get_target_state(pk_remote)
            if remote_state != ThreadState.Alive:
                if remote_state == ThreadState.Stopped:
                    request_block.stopped_remotes |= {pk_remote.remote}
                    logger.debug(
                        f'{self.name} smart_sync detected remote '
                        f'{pk_remote.remote} is stopped')
                    # request_block.do_refresh = True
                    return True  # we are done with this remote
                else:
                    return False  # remote needs more time
            else:
                # If here, remote is in registry and is alive. This also
                # means we have an entry for the remote in the
                # pair_array

                # set a reference
                remote_sb = SmartThread._pair_array[
                    pk_remote.pair_key].status_blocks[pk_remote.remote]

                with SmartThread._pair_array[pk_remote.pair_key].status_lock:
                    # for a sync request we check to see whether a
                    # previous sync is still in progress as indicated by
                    # the sync event being set. We also need to make
                    # sure there is not a pending deadlock that the
                    # remote thread needs to clear.
                    # if not (remote_sb.sync_event.is_set()
                    #         or (remote_sb.conflict
                    #             and remote_sb.sync_wait)):
                    if not (remote_sb.sync_event.is_set()
                            or remote_sb.deadlock):
                        if (remote_sb.target_create_time == 0.0
                                or remote_sb.target_create_time
                                == local_sb.create_time):
                            # sync resume remote thread
                            remote_sb.sync_event.set()
                            local_sb.sync_wait = True
                            logger.info(
                                f'{self.name} smart_sync set event for '
                                f'{pk_remote.remote}')
                        else:
                            return False
                    else:
                        return False  # remote needs more time

        ################################################################
        # Wait on our sync_event (if here, sync_wait is True).
        # Note that remote may have set the sync_event and then stopped.
        # This is OK, but if the sync_event is not set and the remote is
        # stopped, that is not OK.
        ################################################################
        for timeout_value in (SmartThread.K_REQUEST_MIN_INTERVAL,
                              request_block.request_max_interval):
            if local_sb.sync_event.wait(timeout=timeout_value):
                # We need the lock to coordinate with the remote
                # deadlock detection code to prevent:
                # 1) the remote sees that the sync_wait flag is True
                # 2) we reset sync_wait
                # 3) we clear the sync event
                # 4) the remote sees the sync event is clear and decides
                #    we have a deadlock
                with SmartThread._pair_array[pk_remote.pair_key].status_lock:
                    local_sb.sync_wait = False

                    # be ready for next sync wait
                    local_sb.sync_event.clear()

                # if (local_sb.del_deferred
                #         and local_sb.msg_q.empty()
                #         and not local_sb.wait_event.is_set()):
                #     request_block.do_refresh = True
                logger.info(
                    f'{self.name} smart_sync achieved with '
                    f'{pk_remote.remote}')
                self.synced_targets |= {pk_remote.remote}
                # exit, we are done with this remote
                return True

            # Check for error conditions first before checking whether
            # the remote is alive. If the remote detects a deadlock
            # issue, it will set the flags in our entry and then raise
            # an error and will likely be gone when we check. We want to
            # raise the same error on this side.

            with SmartThread._pair_array[pk_remote.pair_key].status_lock:
                if pk_remote.remote in SmartThread._pair_array[
                        pk_remote.pair_key].status_blocks:
                    remote_sb = SmartThread._pair_array[
                        pk_remote.pair_key].status_blocks[pk_remote.remote]
                    self._check_for_deadlock(local_sb=local_sb,
                                             remote_sb=remote_sb)

                    if (local_sb.deadlock or self._get_target_state(
                            pk_remote)
                            == ThreadState.Stopped):
                        remote_sb.sync_event.clear()
                        logger.info(
                            f'{self.name} smart_sync backout reset '
                            f'remote sync_event for {pk_remote.remote}')
                        # request_block.do_refresh = True

                if local_sb.deadlock:
                    local_sb.deadlock = False
                    local_sb.sync_wait = False
                    request_block.deadlock_remotes |= {pk_remote.remote}
                    logger.debug(
                        f'TestDebug {self.name} sync set '
                        f'{request_block.deadlock_remotes=}')
                    return True  # we are done with this remote

                if self._get_target_state(pk_remote) == ThreadState.Stopped:
                    request_block.stopped_remotes |= {pk_remote.remote}
                    logger.debug(
                        f'{self.name} smart_sync detected remote '
                        f'{pk_remote.remote} is stopped')
                    # request_block.do_refresh = True
                    # local_sb.sync_wait = False
                    return True  # we are done with this remote
                else:
                    # if not stopped, then we know remote is active
                    # since we set sync_wait to True
                    return False  # remote needs more time

    ####################################################################
    # _sync_wait_error_cleanup
    ####################################################################
    def _sync_wait_error_cleanup(self,
                                 remotes: set[str],
                                 backout_request: str) -> None:
        """Cleanup a failed sync request.

        Args:
            remotes: names of threads that need cleanup
            backout_request: sync or wait

        Notes:
            1) must be holding the registry lock at least shared
            2) It is possible during cleanup to find that a request that
               had failed for timeout is now completed. We could figure
               out if all such requests are now complete and no other
               requests have suffered an unresolvable error, and then
               we can skip the timeout error and allow the request to
               return as a success. The additional code to do that,
               however, would seem more costly than reasonable for this
               case which would seem rare.
        """
        for remote in remotes:
            pair_key = self._get_pair_key(self.name, remote)
            if pair_key in SmartThread._pair_array:
                # having a pair_key in the array implies our entry
                # exists - set local_sb for easy references
                local_sb = SmartThread._pair_array[
                    pair_key].status_blocks[self.name]
                with SmartThread._pair_array[pair_key].status_lock:
                    # if we made it as far as having set the remote sync
                    # event, then we need to back that out, but only when
                    # the remote did not set our event yet
                    if backout_request == 'smart_sync' and local_sb.sync_wait:
                        # if we are now set, then the remote did
                        # finally respond and this was a good sync,
                        # which also means the backout of the remote is
                        # no longer needed since it will have reset its
                        # sync_event when it set ours
                        local_sb.sync_wait = False
                        if local_sb.sync_event.is_set():
                            local_sb.sync_event.clear()
                            logger.info(
                                f'{self.name} smart_sync backout reset '
                                f'local sync_event for {remote}')
                        else:
                            if remote in SmartThread._pair_array[
                                    pair_key].status_blocks:
                                remote_sb = SmartThread._pair_array[
                                    pair_key].status_blocks[remote]
                                # backout the sync resume
                                if remote_sb.sync_event.is_set():
                                    remote_sb.sync_event.clear()
                                    logger.info(
                                        f'{self.name} smart_sync backout '
                                        'reset remote sync_event for '
                                        f'{remote}')

                    if backout_request == 'smart_wait' and local_sb.wait_wait:
                        local_sb.wait_wait = False
                        local_sb.wait_event.clear()

                    local_sb.deadlock = False

    ####################################################################
    # _request_loop
    ####################################################################
    def _request_loop(self, *,
                      request_block: RequestBlock,
                      ) -> None:
        """Main loop for each request.

        Args:
            request_block: contains requestors, timeout, etc

        Raises:
            SmartThreadRequestTimedOut: request processing timed out
                waiting for the remote.
            SmartThreadRemoteThreadNotAlive: request detected remote
                thread is not alive.
            SmartThreadDeadlockDetected: a deadlock was detected
                between two requests.

        .. # noqa: DAR402

        Note(s):

            1) request_pending is used to keep the cmd_runner pair_array
               entry from being removed between the times the lock is
               dropped until we have completed the request and any
               cleanup that is needed for a failed request

        """
        continue_request_loop = True
        while continue_request_loop:
            # determine timeout_value to use for request
            if request_block.timer.is_specified():
                request_block.request_max_interval = min(
                    self.request_max_interval,
                    (request_block.timer.remaining_time()
                     / max(1, len(self.work_pk_remotes)))
                )
            else:
                request_block.request_max_interval = (
                    self.request_max_interval)

            work_pk_remotes_copy = self.work_pk_remotes.copy()
            for pk_remote in work_pk_remotes_copy:
                # we need to hold the lock to ensure the pair_array
                # remains stable while getting local_sb. The
                # request_pending flag in our entry will prevent our
                # entry for being removed (but not the remote)
                with sel.SELockShare(SmartThread._registry_lock):
                    if self.found_pk_remotes:
                        pk_remote = self._handle_found_pk_remotes(
                            pk_remote=pk_remote,
                            work_pk_remotes=work_pk_remotes_copy
                        )

                    if pk_remote.pair_key in SmartThread._pair_array:
                        # having a pair_key in the array implies our
                        # entry exists - set local_sb for easy
                        # references. Note, however, that the remote
                        # entry may not exist when our local entry was
                        # a deferred delete case.
                        local_sb = SmartThread._pair_array[
                            pk_remote.pair_key].status_blocks[self.name]

                        # Getting back True from the process_rtn means
                        # we are done with this remote, either because
                        # the command was successful or there was an
                        # unresolvable error which will be processed
                        # later after all remotes are processed.
                        # Getting back False means the remote is not yet
                        # ready to participate in the request, so we
                        # keep it in the work list and try again until
                        # it works (unless and until we encounter an
                        # unresolvable error with any request, or we
                        # eventually timeout when timeout is specified)
                        if request_block.process_rtn(request_block,
                                                     pk_remote,
                                                     local_sb):
                            self.work_pk_remotes.remove(pk_remote)

                            # We may have been able to successfully
                            # complete this request despite not yet
                            # having an alive remote (smart_recv and
                            # wait, for example, do not require an alive
                            # remote if the message or wait bit was
                            # previously delivered or set). We thus need
                            # to make sure we remove such a remote from
                            # the missing set to prevent its
                            # resurrection from setting request_pending.
                            self.missing_remotes -= {pk_remote.remote}
                            local_sb.target_create_time = 0.0
                            local_sb.request_pending = False
                            if (local_sb.del_deferred
                                    and local_sb.msg_q.empty()
                                    and not local_sb.wait_event.is_set()
                                    and not local_sb.sync_event.is_set()):
                                request_block.do_refresh = True
                            local_sb.request = ReqType.NoReq

                if request_block.do_refresh:
                    logger.debug(
                        f'{self.name} {self.request.value} calling refresh, '
                        f'remaining remotes: {self.work_pk_remotes}')
                    with sel.SELockExcl(SmartThread._registry_lock):
                        self._clean_registry()
                        self._clean_pair_array()
                    request_block.do_refresh = False

            if ((self.request == ReqType.Smart_send
                    and request_block.completion_count
                    <= len(self.sent_targets))
                    or (self.request == ReqType.Smart_recv
                        and request_block.completion_count
                        <= len(self.recvd_msgs.keys()))
                    or (self.request == ReqType.Smart_resume
                        and request_block.completion_count
                        <= len(self.resumed_targets))
                    or (self.request == ReqType.Smart_wait
                        and request_block.completion_count
                        <= len(self.resumed_by))
                    or (self.request == ReqType.Smart_sync
                        and request_block.completion_count
                        <= len(self.synced_targets))):
                # clear request_pending for remaining work remotes
                for pair_key, remote, _ in self.work_pk_remotes:
                    if pair_key in SmartThread._pair_array:
                        # having a pair_key in the array implies our
                        # entry exists
                        SmartThread._pair_array[
                            pair_key].status_blocks[
                            self.name].request_pending = False
                        SmartThread._pair_array[
                            pair_key].status_blocks[
                            self.name].request = ReqType.NoReq
                break

            # handle any error or timeout cases - don't worry about any
            # remotes that were still pending - we need to fail the
            # request as soon as we know about any unresolvable
            # failures. Note that we ignore stopped_remotes when no
            # remotes are specified. This will be the case when recv
            # had no remotes and is looking for any message from any
            # thread in the configuration, or wait had no remotes and is
            # looking for  a resume from any thread in the
            # configuration. In those two cases, we will refresh our
            # list of threads to try and keep trying. For send, though,
            # no remotes means either a broadcast to any and all active
            # threads or a SendMsgs was provided. For broadcast, we are
            # done after one loop regardless of whether there were any
            # active threads and we will thus not reach the following
            # code. For the SendMsg case, we do need to raise an error
            # for stopped targets.
            if ((request_block.stopped_remotes and request_block.remotes)
                    or request_block.deadlock_remotes
                    or request_block.timer.is_expired()):

                # cleanup before doing the error
                with sel.SELockExcl(SmartThread._registry_lock):
                    if request_block.cleanup_rtn:
                        request_block.cleanup_rtn(
                            request_block.remotes,
                            request_block.request.value)

                    # clear request_pending for remaining work remotes
                    for pair_key, remote, _ in self.work_pk_remotes:
                        if pair_key in SmartThread._pair_array:
                            # having a pair_key in the array implies our
                            # entry exists
                            local_sb = SmartThread._pair_array[
                                pair_key].status_blocks[self.name]
                            local_sb.request_pending = False
                            local_sb.request = ReqType.NoReq
                            local_sb.recv_wait = False
                            local_sb.wait_wait = False
                            local_sb.sync_wait = False
                            local_sb.deadlock = False

                    pending_remotes = [remote for pk, remote, _ in
                                       self.work_pk_remotes]
                    # logger.debug(
                    #     f'{self.name} {self.request.value} calling refresh, '
                    #     f'remaining remotes: {self.work_pk_remotes}')
                    self.work_pk_remotes = []
                    self.missing_remotes = []
                    # self._clean_registry()
                    # self._clean_pair_array()

                self._handle_loop_errors(request_block=request_block,
                                         pending_remotes=pending_remotes)

            time.sleep(0.2)

        ################################################################
        # cleanup
        ################################################################
        if self.work_pk_remotes:
            with sel.SELockShare(SmartThread._registry_lock):
                self.work_pk_remotes = []

    ####################################################################
    # _set_work_pk_remotes
    ####################################################################
    def _set_work_pk_remotes(self,
                             remotes: set[str]) -> None:
        """Update the work_pk_remotes with newly found threads.

        Args:
            remotes: names of threads that are targets for the
                request

        """
        pk_remotes: list[PairKeyRemote] = []

        with sel.SELockExcl(SmartThread._registry_lock):
            self.missing_remotes: set[str] = set()
            for remote in remotes:
                if remote in SmartThread._registry:
                    target_create_time = SmartThread._registry[
                        remote].create_time
                else:
                    target_create_time = 0.0

                pair_key = self._get_pair_key(self.name, remote)
                if pair_key in SmartThread._pair_array:
                    local_sb = SmartThread._pair_array[
                        pair_key].status_blocks[self.name]
                    local_sb.request_pending = True
                    local_sb.request = self.request
                    local_sb.target_create_time = target_create_time
                pk_remote = PairKeyRemote(pair_key=pair_key,
                                          remote=remote,
                                          create_time=target_create_time)
                pk_remotes.append(pk_remote)

                # if we just added a pk_remote that has not yet
                # come into existence
                if target_create_time == 0.0:
                    # tell _clean_pair_array that we are looking
                    # for this remote
                    self.missing_remotes |= {remote}

            # we need to set the work remotes before releasing the
            # lock - any starts or deletes need to be accounted for
            # starting now
            self.work_pk_remotes: list[PairKeyRemote] = (
                pk_remotes.copy())
            self.found_pk_remotes: list[PairKeyRemote] = []
            logger.debug(f'{self.name} {self.request.value} setup complete '
                         f'for targets: {pk_remotes}')

    ####################################################################
    # _handle_found_pk_remotes
    ####################################################################
    def _handle_found_pk_remotes(self,
                                 pk_remote: PairKeyRemote,
                                 work_pk_remotes: list[PairKeyRemote]
                                 ) -> PairKeyRemote:
        """Update the work_pk_remotes with newly found threads.

        Args:
            pk_remote: the current pk_remote currently being processed
                in _request_loop
            work_pk_remotes: list of pk_remotes currently being
                processed in _request_loop

        Returns:
            the input pk_remote is returned either as is, or updated
            with a non-zero create_time serial if it is among the
            found pk_remotes

        Raises:
            SmartThreadWorkDataException: _handle_found_pk_remotes
                failed to find an entry for {found_pk_remote=} in
                {self.work_pk_remotes=}.

        """
        ret_pk_remote = pk_remote
        for found_pk_remote in self.found_pk_remotes:
            test_pk_remote = PairKeyRemote(found_pk_remote.pair_key,
                                           found_pk_remote.remote,
                                           0.0)
            try:
                idx = self.work_pk_remotes.index(test_pk_remote)
                self.work_pk_remotes[idx] = PairKeyRemote(
                    found_pk_remote.pair_key,
                    found_pk_remote.remote,
                    found_pk_remote.create_time)
                # if we are currently processing the newly found
                # pk_remote then return the updated version with the
                # non-zero create_time
                if pk_remote.remote == found_pk_remote.remote:
                    ret_pk_remote = PairKeyRemote(
                        found_pk_remote.pair_key,
                        found_pk_remote.remote,
                        found_pk_remote.create_time)

            except ValueError:
                error_msg = (
                    f'SmartThread {threading.current_thread().name} raising '
                    'SmartThreadWorkDataException error while processing '
                    f'request {self.request}. '
                    f'An expected entry for {found_pk_remote=} was not '
                    f'found in {self.work_pk_remotes=}.')
                logger.error(error_msg)
                raise SmartThreadWorkDataException(error_msg)

            try:
                idx = work_pk_remotes.index(test_pk_remote)
                work_pk_remotes[idx] = PairKeyRemote(
                    found_pk_remote.pair_key,
                    found_pk_remote.remote,
                    found_pk_remote.create_time)

            except ValueError:
                error_msg = (
                    f'SmartThread {threading.current_thread().name} raising '
                    'SmartThreadWorkDataException error while processing '
                    f'request {self.request}. '
                    f'An expected entry for {found_pk_remote=} was not '
                    f'found in {work_pk_remotes=}.')
                logger.error(error_msg)
                raise SmartThreadWorkDataException(error_msg)

        self.found_pk_remotes = []

        return ret_pk_remote

    ####################################################################
    # _handle_loop_errors
    ####################################################################
    def _handle_loop_errors(self, *,
                            request_block: RequestBlock,
                            pending_remotes: list[str]
                            ) -> None:
        """Raise an error if needed.

        Args:
            request_block: contains targets, timeout, etc
            pending_remotes: remotes that have not either not responded
                or were found to be in an incorrect state

        Raises:
            SmartThreadRequestTimedOut: request processing timed out
                waiting for the remote.
            SmartThreadRemoteThreadNotAlive: request detected remote
                thread is not alive.
            SmartThreadDeadlockDetected: a deadlock was detected
                between two requests.
            SmartThreadRemoteThreadNotRegistered: the remote thread is
                not in the ThreadState.Registered state as required.

        """
        targets_msg = (f'while processing a '
                       f'{request_block.request.value} '
                       f'request with targets '
                       f'{sorted(request_block.remotes)}.')

        pending_msg = (f' Remotes that are pending: '
                       f'{sorted(pending_remotes)}.')

        if request_block.stopped_remotes:
            stopped_msg = (
                ' Remotes that are stopped: '
                f'{sorted(request_block.stopped_remotes)}.')
        else:
            stopped_msg = ''

        if request_block.not_registered_remotes:
            not_registered_msg = (
                ' Remotes that are not registered: '
                f'{sorted(request_block.not_registered_remotes)}.')
        else:
            not_registered_msg = ''

        if request_block.deadlock_remotes:
            deadlock_msg = (
                f' Remotes that are deadlocked: '
                f'{sorted(request_block.deadlock_remotes)}.')
        else:
            deadlock_msg = ''

        if request_block.full_send_q_remotes:
            full_send_q_msg = (
                f' Remotes that have a full send_q: '
                f'{sorted(request_block.full_send_q_remotes)}.')
        else:
            full_send_q_msg = ''

        msg_suite = (f'{targets_msg}{pending_msg}{stopped_msg}'
                     f'{not_registered_msg}{deadlock_msg}{full_send_q_msg}')

        # If an error should be raised for stopped threads
        if (request_block.error_stopped_target
                and request_block.stopped_remotes):
            error_msg = (
                f'{self.name} raising '
                f'SmartThreadRemoteThreadNotAlive {msg_suite}')
            logger.error(error_msg)
            raise SmartThreadRemoteThreadNotAlive(error_msg)

        # If an error should be raised for unregistered threads
        if (request_block.error_not_registered_target
                and request_block.not_registered_remotes):
            error_msg = (
                f'{self.name} raising '
                f'SmartThreadRemoteThreadNotRegistered {msg_suite}')
            logger.error(error_msg)
            raise SmartThreadRemoteThreadNotRegistered(error_msg)

        if request_block.deadlock_remotes:
            error_msg = (
                f'{self.name} raising '
                f'SmartThreadDeadlockDetected {msg_suite}')
            logger.error(error_msg)
            raise SmartThreadDeadlockDetected(error_msg)

        # Note that the timer will never be expired if timeout
        # was not specified either explicitly on the smart_wait
        # call or via a default timeout established when this
        # SmartThread was instantiated.
        if request_block.timer.is_expired():
            error_msg = (
                f'{self.name} raising '
                f'SmartThreadRequestTimedOut {msg_suite}')
            logger.error(error_msg)
            raise SmartThreadRequestTimedOut(error_msg)

    ####################################################################
    # _check_for_deadlock
    ####################################################################
    def _check_for_deadlock(self, *,
                            local_sb: ConnectionStatusBlock,
                            remote_sb: ConnectionStatusBlock) -> None:
        """Check the remote thread for deadlock requests.

        Args:
            local_sb: connection block for this thread
            remote_sb: connection block for remote thread

        Notes:
            1) must be entered holding the status_lock

        """
        # If the deadlock has already been detected by
        # the remote, then the remote will have set local_sb.deadlock
        # to let us know. No need to analyse this side. Just
        # drop down to the code below and return.
        if not local_sb.deadlock:
            if (remote_sb.sync_wait
                    and not local_sb.request == ReqType.Smart_sync
                    and not (remote_sb.sync_event.is_set()
                             or remote_sb.deadlock)):
                remote_sb.deadlock = True
                remote_sb.remote_deadlock_request = local_sb.request
                local_sb.deadlock = True
                local_sb.remote_deadlock_request = ReqType.Smart_sync
                logger.debug(
                    f'TestDebug {self.name} {self.request=} '
                    f'set remote (sync_wait) and local '
                    f'deadlock flags {remote_sb.name=}')
            elif (remote_sb.wait_wait
                    and not (remote_sb.wait_event.is_set()
                             or remote_sb.deadlock)):
                remote_sb.deadlock = True
                remote_sb.remote_deadlock_request = local_sb.request
                local_sb.deadlock = True
                local_sb.remote_deadlock_request = ReqType.Smart_wait
                logger.debug(
                    f'TestDebug {self.name} {self.request=} '
                    f'set remote (wait) and local '
                    f'deadlock flags {remote_sb.name=}')
            elif (remote_sb.recv_wait
                    and not (not remote_sb.msg_q.empty()
                             or remote_sb.deadlock)):
                remote_sb.deadlock = True
                remote_sb.remote_deadlock_request = local_sb.request
                local_sb.deadlock = True
                local_sb.remote_deadlock_request = ReqType.Smart_recv
                logger.debug(
                    f'TestDebug {self.name} {self.request=} '
                    f'set remote (recv_wait) and local '
                    f'deadlock flags {remote_sb.name=}')

    ####################################################################
    # _request_setup
    ####################################################################
    def _request_setup(self, *,
                       process_rtn: Callable[
                           ["RequestBlock",
                            PairKeyRemote,
                            "SmartThread.ConnectionStatusBlock"], bool],
                       cleanup_rtn: Optional[Callable[[set[str]], None]],
                       get_block_lock: bool,
                       error_stopped_target: bool,
                       remotes: Optional[Iterable] = None,
                       error_not_registered_target: bool = False,
                       completion_count: int = 0,
                       timeout: OptIntFloat = None,
                       log_msg: Optional[str] = None,
                       msg_to_send: Optional[dict[str, Any]] = None
                       ) -> RequestBlock:
        """Do common setup for each request.

        Args:
            process_rtn: method to process the request for each
                iteration of the request loop
            cleanup_rtn: method to back out a failed request
            get_block_lock: True or False
            remotes: remote threads for the request
            error_stopped_target: request will raise an error if any
                one of the targets is in a stopped state.
            error_not_registered_target: request will raise an error if
                any one of the targets is in any state other than
                registered.
            completion_count: how many request need to succeed
            timeout: number of seconds to allow for request completion
            log_msg: caller log message to issue
            msg_to_send: smart_send message to send


        Returns:
            A RequestBlock is returned that contains the timer and the
            set of threads to be processed

        Raises:
            SmartThreadInvalidInput: {name} {request.value} request with
                no targets specified.

        """
        timer = Timer(timeout=timeout, default_timeout=self.default_timeout)

        self.cmd_runner = threading.current_thread().name

        if not remotes:
            error_msg = (
                f'SmartThread {threading.current_thread().name} raising '
                'SmartThreadInvalidInput error while processing '
                f'request {self.request}. '
                f'Remote threads are required for the request but none were '
                f'specified.')
            logger.error(error_msg)
            raise SmartThreadInvalidInput(error_msg)
        else:
            if isinstance(remotes, str):
                remotes = {remotes}
            else:
                remotes = set(remotes)

        exit_log_msg = self._issue_entry_log_msg(
            request=self.request,
            remotes=remotes,
            timeout_value=timer.timeout_value(),
            log_msg=log_msg)

        if (remotes and self.request != ReqType.Smart_start
                and self.cmd_runner in remotes):
            error_msg = (
                f'SmartThread {threading.current_thread().name} raising '
                f'SmartThreadInvalidInput error while processing request '
                f'{self.request.value}. '
                f'Targets {sorted(remotes)} includes {self.cmd_runner} '
                f'which is not permitted except for request smart_start.'
            )
            logger.error(error_msg)
            raise SmartThreadInvalidInput(error_msg)

        pk_remotes: list[PairKeyRemote] = []

        if self.request in (ReqType.Smart_send, ReqType.Smart_recv,
                            ReqType.Smart_resume, ReqType.Smart_sync,
                            ReqType.Smart_wait):
            self._set_work_pk_remotes(remotes=remotes)

        request_block = RequestBlock(
            request=self.request,
            process_rtn=process_rtn,
            cleanup_rtn=cleanup_rtn,
            get_block_lock=get_block_lock,
            remotes=remotes,
            error_stopped_target=error_stopped_target,
            error_not_registered_target=error_not_registered_target,
            completion_count=completion_count,
            pk_remotes=pk_remotes,
            timer=timer,
            do_refresh=False,
            exit_log_msg=exit_log_msg,
            msg_to_send=msg_to_send,
            stopped_remotes=set(),
            not_registered_remotes=set(),
            deadlock_remotes=set(),
            full_send_q_remotes=set())

        return request_block

    ####################################################################
    # issue_entry_log_msg
    ####################################################################
    def _issue_entry_log_msg(
            self,
            request: ReqType,
            remotes: set[str],
            timeout_value: Optional[IntFloat] = None,
            log_msg: Optional[str] = None,
            latest: int = 3
            ) -> str:
        """Issue an entry log message.

        Args:
            request: request being processed
            remotes: thread names of the request targets
            timeout_value: value that will be used for request timeout
            log_msg: log message to append to the log msg

        Returns:
            the log message to use for the exit call

        """
        log_msg_body = (
            f'requestor: {self.cmd_runner}, '
            f'targets: {sorted(remotes)} '
            f'timeout value: {timeout_value} '
            f'{get_formatted_call_sequence(latest=latest, depth=1)}')

        if log_msg:
            log_msg_body += f' {log_msg}'

        entry_log_msg = (
            f'{request.value} entry: {log_msg_body}')

        exit_log_msg = (
            f'{request.value} exit: {log_msg_body}')

        logger.debug(entry_log_msg, stacklevel=latest)
        return exit_log_msg

    ####################################################################
    # _verify_thread_is_current
    ####################################################################
    def _verify_thread_is_current(self,
                                  request: ReqType) -> None:
        """Verify that SmartThread is running under the current thread.

        Args:
            request: the request that is being processed

        Raises:
            SmartThreadDetectedOpFromForeignThread: SmartThread services
                must be called from the thread that was originally
                assigned during instantiation of SmartThread.

        """
        if self.thread is not threading.current_thread():
            error_msg = (
                f'SmartThread {threading.current_thread().name} raising '
                f'SmartThreadDetectedOpFromForeignThread error '
                f'while processing request {request.value}. '
                f'The SmartThread object used for the invocation is '
                f'associated with thread {self.thread} which does not match '
                f'caller thread {threading.current_thread()} as required.')
            logger.error(error_msg)
            raise SmartThreadDetectedOpFromForeignThread(error_msg)

    ####################################################################
    # _connection_block_lock
    ####################################################################
    # @contextmanager
    # def _connection_block_lock(*args, **kwds) -> None:
    #     """Obtain the connection_block lock.
    #
    #     This method is called from _request_loop to obtain the
    #     connection_block lock for those requests that need it
    #     (smart_resume, smart_wait, and smart_sync) and to not obtain
    #     it for those requests that do not need it (smart_send, smart_recv).
    #     This allows the code in _request_loop to use the with statement
    #     for the lock obtain with having to code around it.
    #
    #     Args:
    #         args: the lock to obtain
    #         kwds: whether to obtain the lock
    #
    #     """
    #     # is request needs the lock
    #     if kwds['obtain_tf']:
    #         kwds['lock'].acquire()
    #     try:
    #         yield
    #     finally:
    #         # release the lock if it was obtained
    #         if kwds['obtain_tf']:
    #             kwds['lock'].release()
