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

    from scottbrian_paratools.smart_thread import SmartThread
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
    msg_from_beta = alpha_smart_thread.smart_recv(senders='beta')
    print(msg_from_beta)
    alpha_smart_thread.smart_resume(waiters='beta')
    alpha_smart_thread.smart_join(targets='beta')
    print('mainline exiting')

.. invisible-code-block: python

    del SmartThread._registry['alpha']

Expected output for Example 1::

    mainline entered
    f1 beta entered
    {'beta': ['hi alpha, this is beta']}
    f1 beta exiting
    mainline alpha exiting


:Example 2: Create a SmartThread configuration for threads named
            alpha and beta, send and receive a message, and resume a
            wait. Note the use of auto_start=True and passing the
            SmartThread instance to the target via the thread_parm_name.

.. code-block:: python

    from scottbrian_paratools.smart_thread import SmartThread
    def f1(smart_thread: SmartThread) -> None:
        print('f1 beta entered')
        smart_thread.smart_send(receivers='alpha',
                                msg='hi alpha, this is beta')
        smart_thread.smart_wait(resumers='alpha')
        print('f1 beta exiting')
    print('mainline alpha entered')
    alpha_smart_thread = SmartThread(name='alpha')
    beta_smart_thread = SmartThread(name='beta',
                              target=f1,
                              auto_start=True,
                              thread_parm_name='smart_thread')
    msg_from_beta = alpha_smart_thread.smart_recv(senders='beta')
    print(msg_from_beta)
    alpha_smart_thread.smart_resume(waiters='beta')
    alpha_smart_thread.smart_join(targets='beta')
    print('mainline exiting')

.. invisible-code-block: python

    del SmartThread._registry['alpha']

Expected output for Example 2::

    mainline alpha entered
    f1 beta entered
    {'beta': ['hi alpha, this is beta']}
    f1 beta exiting
    mainline alpha exiting


:Example 3: Create a SmartThread configuration for threads named
            alpha and beta, send and receive a message, and resume a
            wait. Note the use of threading.Thread to create and start
            the beta thread and having the target thread instantiate the
            SmartThread.

.. code-block:: python

    from scottbrian_paratools.smart_thread import SmartThread
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
    msg_from_beta = alpha_smart_thread.smart_recv(senders='beta')
    print(msg_from_beta)
    alpha_smart_thread.smart_resume(waiters='beta')
    alpha_smart_thread.smart_join(targets='beta')
    print('mainline alpha exiting')

.. invisible-code-block: python

    del SmartThread._registry['alpha']

Expected output for Example 3::

    mainline entered
    f1 beta entered
    {'beta': ['hi alpha, this is beta']}
    f1 beta exiting
    mainline alpha exiting


:Example 4: Create a SmartThread configuration for threads named alpha
            and beta, send and receive a message, and resume a wait.
            Note the use of the ThreadApp class that inherits
            threading.Thread as a base and uses a run method. This
            example demonstrates the use of the *thread* argument on the
            SmartThread instantiation.

.. code-block:: python

    from scottbrian_paratools.smart_thread import SmartThread
    import threading
    import time

    class ThreadApp(threading.Thread):
        def __init__(self, name: str) -> None:
            super().__init__(name=name)
            self.smart_thread = SmartThread(name=name,
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
    thread_app = ThreadApp(name='beta')
    my_msg = alpha_smart_thread.smart_recv(senders='beta')
    print(my_msg)
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
    {'beta': ['hi alpha, this is beta']}
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

    from scottbrian_paratools.smart_thread import SmartThread
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
    thread_app = SmartThreadApp(name='beta')
    my_msg = alpha_smart_thread.smart_recv(senders='beta')
    print(my_msg)
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
    {'beta': ['hi alpha, this is beta']}
    beta about to wait
    alpha about to resume beta
    beta exiting run method
    mainline alpha exiting

"""

########################################################################
# Standard Library
########################################################################
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
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

def make_def_dict():
    return defaultdict(list)

@dataclass
class RecvMsgs:
    """Class used for a set of messages to send."""
    recv_msgs: dict[str, list[Any]] = field(
        default_factory=make_def_dict)

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
    cleanup_rtn: Callable[[list[PairKeyRemote], str], None]
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
    ret_msg: RecvMsgs
    ret_resume_result: set[str]
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

                # with sel.SELockExcl(SmartThread._registry_lock):
                #     self.smart_thread._set_state(
                #         target_thread=self.smart_thread,
                #         new_state=ThreadState.Stopped)
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

        if not thread and not target:
            self.cmd_runner = name
        else:
            self.cmd_runner = threading.current_thread().name

        self.request: ReqType = ReqType.Smart_init

        exit_log_msg = self._issue_entry_log_msg(
            request=ReqType.Smart_init,
            remotes={name},
            latest=2)

        if not isinstance(name, str):
            raise SmartThreadIncorrectNameSpecified(
                'Attempted SmartThread instantiation with incorrect name of '
                f'{name}.')
        self.name = name

        if target and thread:
            raise SmartThreadMutuallyExclusiveTargetThreadSpecified(
                'Attempted SmartThread instantiation with both target and '
                'thread specified.')

        if (not target) and (args or kwargs):
            raise SmartThreadArgsSpecificationWithoutTarget(
                'Attempted SmartThread instantiation with args or '
                'kwargs specified but without target specified.')

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
            self.thread.name = name
        else:  # caller is running on the thread to be used
            self.thread_create = ThreadCreate.Current
            self.thread = threading.current_thread()
            self.thread.name = name

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

        self.work_remotes: set[str] = set()
        self.work_pk_remotes: list[PairKeyRemote] = []
        self.missing_remotes: set[str] = set()
        self.found_pk_remotes: list[PairKeyRemote] = []

        # set create time to zero - we will update create_time in
        # the _register method under lock
        self.create_time: float = 0.0

        # register this new SmartThread so others can find us
        self._register()

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
        self.wait_for_any = False

        if self.auto_started:
            self.smart_start(self.name)

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
    @staticmethod
    def _set_state(target_thread: "SmartThread",
                   new_state: ThreadState) -> bool:
        """Set the state for a thread.

        Args:
            target_thread: thread to set status for
            new_state: the new status to be set

        Returns:
            True if status was changed, False otherwise
        """
        saved_status = target_thread.st_state
        if saved_status == new_state:
            return False
        target_thread.st_state = new_state

        logger.debug(
            f'{threading.current_thread().name} set '
            f'state for thread {target_thread.name} from {saved_status} to '
            f'{new_state}', stacklevel=2)
        return True

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
                # get a unique time stamp for create_time
                create_time = time.time()
                while create_time == (
                        SmartThread._create_pair_array_entry_time):
                    create_time = time.time()
                # update last create time
                SmartThread._create_pair_array_entry_time = create_time
                self.create_time = create_time
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
                raise SmartThreadNameAlreadyInUse(
                    f'An entry for a SmartThread with name = {self.name} is '
                    'already registered for a different thread.')

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
                raise SmartThreadErrorInRegistry(
                    f'Registry item with key {key} has non-matching '
                    f'item.name of {item.name}.')

        changed = False
        for key in keys_to_del:
            del SmartThread._registry[key]
            changed = True
            logger.debug(f'{self.cmd_runner} removed {key} from registry for '
                         f'request {self.request.value}')
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
                         f'{print_time}, deleted {keys_to_del}')

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
                    raise SmartThreadIncorrectData(
                        f'{self.cmd_runner} detected in '
                        f'_add_to_pair_array while adding {self.name} that '
                        f'pair_key {pair_key} is already in the pair array '
                        f'with an empty status_blocks.')
                elif num_status_blocks == 1:
                    if self.name in SmartThread._pair_array[
                            pair_key].status_blocks:
                        raise SmartThreadIncorrectData(
                            f'{self.cmd_runner} detected in '
                            f'_add_to_pair_array while adding {self.name} '
                            f'that pair_key {pair_key} is already in the pair '
                            f'array with an existing status_blocks entry for '
                            f'{self.name}.')
                    if (existing_name in SmartThread._pair_array[
                            pair_key].status_blocks
                            and not SmartThread._pair_array[
                            pair_key].status_blocks[
                                existing_name].del_deferred):
                        raise SmartThreadIncorrectData(
                            f'{self.cmd_runner} detected in '
                            f'_add_to_pair_array while adding {self.name} '
                            f'that pair_key {pair_key} is already in the pair '
                            f'array with an existing status_blocks entry for '
                            f'{existing_name} that is not del_deferred.')
                else:
                    raise SmartThreadIncorrectData(
                        f'{self.cmd_runner} detected in '
                        f'_add_to_pair_array while adding {self.name} that '
                        f'pair_key {pair_key} is already in the pair array '
                        f'with an existing status_blocks entry for two or '
                        f'more entries.')

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
                logger.debug(
                    f'TestDebug {self.cmd_runner} set request_pending in '
                    f'refresh for {pair_key=}, {existing_name=}')

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
                    log_msg: Optional[str] = None) -> None:
        """Start the smart thread.

        Args:
            targets: names of smart threads to be started
            log_msg: additional text to append to the debug log message
                that is issued on request entry and exit

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
        # get RequestBlock with targets in a set and a timer object
        self.request = ReqType.Smart_start
        if not targets:
            targets = self.name
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

        self._config_cmd_loop(request_block=request_block)

        self.request = ReqType.NoReq

        logger.debug(request_block.exit_log_msg)

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
            # At this point, the thread was started and the bootstrap
            # method received control and set the Event that start waits
            # on. The bootstrap method will call run and eventually the
            # thread will end. So, at this point, either run has not yet
            # been called, the thread is running, or the thread is
            # already stopped. The is_alive() method will return True
            # if the Event is set (it is) and will return False when
            # the thread is stopped. So, we can rely on is_alive here
            # will set the correct state. Since we are holding
            # the registry lock exclusive, the configuration can not
            # change and a join will wait behind us. The only thing that
            # could happen is we get back True from is_alive and set
            # the state to alive, but then the thread ends and now we
            # still show it as alive. This is not a problem since the
            # _get_state method will detect that case and return stopped
            # as the state
            if SmartThread._registry[remote].thread.is_alive():
                self._set_state(
                    target_thread=SmartThread._registry[remote],
                    new_state=ThreadState.Alive)
            else:  # start failed or thread finished already
                self._set_state(
                    target_thread=SmartThread._registry[remote],
                    new_state=ThreadState.Stopped)
        else:
            # if here, the remote is not registered
            request_block.not_registered_remotes |= {remote}

        return True  # there are no cases that need to allow more time

    ####################################################################
    # smart_unreg
    ####################################################################
    def smart_unreg(self, *,
                    targets: Iterable,
                    log_msg: Optional[str] = None) -> None:
        """Unregister threads that were never started.

        Args:
            targets: thread names that are to be unregistered
            log_msg: additional text to append to the debug log message
                that is issued on request entry and exit

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
        self.request = ReqType.Smart_unreg
        request_block = self._request_setup(
            remotes=targets,
            error_stopped_target=False,
            error_not_registered_target=True,
            process_rtn=self._process_unregister,
            cleanup_rtn=None,
            get_block_lock=False,
            completion_count=0,
            timeout=0,
            log_msg=log_msg)

        # self._config_cmd_loop(request_block=request_block)

        unreged_remotes: set[str] = set()
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
                        unreged_remotes |= {remote}

                # remove threads from the registry
                self._clean_registry()
                self._clean_pair_array()

                if unreged_remotes:
                    logger.info(
                        f'{self.name} did successful smart_unreg of '
                        f'{sorted(unreged_remotes)}.')

                if (request_block.error_not_registered_target
                        and request_block.not_registered_remotes):
                    self._handle_loop_errors(
                        request_block=request_block,
                        pending_remotes=list(
                            self.work_remotes))

        self.request = ReqType.NoReq

        logger.debug(request_block.exit_log_msg)

    ####################################################################
    # _process_unregister
    ####################################################################
    def _process_unregister(self,
                            request_block: RequestBlock,
                            remote: str
                            ) -> bool:
        """Process the smart_join request.

        Args:
            request_block: contains request related data
            remote: remote name

        Returns:
            True when request completed, False otherwise

        """
        if self._get_state(remote) != ThreadState.Registered:
            request_block.not_registered_remotes |= {remote}
            return False

        # remove this thread from the registry
        self._set_state(
            target_thread=SmartThread._registry[remote],
            new_state=ThreadState.Stopped)
        # self._clean_registry()
        # self._clean_pair_array()

        # logger.debug(
        #     f'{self.name} did successful smart_unreg of {remote}.')

        # restart while loop with one less remote
        return True

    ####################################################################
    # join
    ####################################################################
    def smart_join(self, *,
                   targets: Iterable,
                   timeout: OptIntFloat = None,
                   log_msg: Optional[str] = None) -> None:
        """Wait for target thread to end.

        Args:
            targets: thread names that are to be joined
            timeout: timeout to use instead of default timeout
            log_msg: additional text to append to the debug log message
                that is issued on request entry and exit

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
        self.request = ReqType.Smart_join
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
            completed_targets: set[str] = set()
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
                        completed_targets |= joined_remotes
                        # must remain under lock for these two calls
                        self._clean_registry()
                        self._clean_pair_array()
                        logger.info(
                            f'{self.name} did successful smart_join of '
                            f'{sorted(joined_remotes)}.')
                        logger.info(
                            f'{self.name} smart_join completed targets: '
                            f'{sorted(completed_targets)}, pending '
                            f'targets: {sorted(self.work_remotes)}')
                    else:  # no progress was made
                        time.sleep(0.2)
                        if request_block.timer.is_expired():
                            self._handle_loop_errors(
                                request_block=request_block,
                                pending_remotes=list(self.work_remotes))

        self.request = ReqType.NoReq

        logger.debug(request_block.exit_log_msg)

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
    # _process_smart_join
    ####################################################################
    # def _process_smart_join(self,
    #                         request_block: RequestBlock,
    #                         remote: str,
    #                         ) -> bool:
    #     """Process the smart_join request.
    #
    #     Args:
    #         request_block: contains request related data
    #         remote: remote name
    #
    #     Returns:
    #         True when request completed, False otherwise
    #
    #     """
    #     # if the remote is not in the registry then either it was never
    #     # created, or it was created as a ThreadTarget which ended and
    #     # set its state to stopped and then got removed by a command
    #     # that called _clean_registry. In either case, we have
    #     # nothing to do and can simply return True to move on to the
    #     # next target.
    #     if remote in SmartThread._registry:
    #         # Note that if the remote thread was never
    #         # started, the following join will raise an
    #         # error. If the thread is eventually started,
    #         # we currently have no way to detect that and
    #         # react. We can only hope that a failed join
    #         # here will help give us a clue that something
    #         # went wrong.
    #         # Note also that we timeout each join after a
    #         # short 0.2 seconds so that we release and
    #         # re-obtain the registry lock in between
    #         # attempts. This is done to ensure we don't
    #         # deadlock with any of the other services
    #         # (e.g., smart_recv)
    #         try:
    #             SmartThread._registry[remote].thread.join(timeout=0.2)
    #         except RuntimeError:
    #             # We know the thread is registered, so
    #             # we will skip it for now and come back to it
    #             # later. If it never starts and exits then
    #             # we will timeout (if timeout was specified)
    #             return False
    #
    #         # we need to check to make sure the thread is
    #         # not alive in case we timed out
    #         if SmartThread._registry[remote].thread.is_alive():
    #             return False  # give thread more time to end
    #         else:
    #             # set state to stopped
    #             self._set_state(
    #                 target_thread=SmartThread._registry[remote],
    #                 new_state=ThreadState.Stopped)
    #             # remove this thread from the registry
    #             self._clean_registry(target=remote)
    #             self._clean_pair_array(target=remote)
    #
    #     logger.debug(
    #         f'{self.name} did successful join of {remote}.')
    #
    #     # restart while loop with one less remote
    #
    #     return True

    ####################################################################
    # smart_send
    ####################################################################
    def smart_send(self,
                   msg: Any,
                   receivers: Optional[Iterable] = None,
                   timeout: OptIntFloat = None,
                   log_msg: Optional[str] = None) -> None:
        """Send one or more messages to remote threads.

        Args:
            msg: the msg to be sent. This may be a single item or a
                collection of items in any type of data structure.
            receivers: names of remote threads to send the message to.
                If None, the message will be sent to all remote
                threads that are alive.
            timeout: number of seconds to wait for the targets to become
                alive and ready to accept messages
            log_msg: additional text to append to the debug log message
                that is issued on request entry and exit

        Raises:
            SmartThreadRemoteThreadNotAlive: target thread was
                stopped.
            SmartThreadRequestTimedOut: request timed out before targets
                became alive.
            SmartThreadNoRemoteTargets: {self.name} issued a smart_send
                request but there are no remote receivers in the
                configuration to send to.

        .. # noqa: DAR402

        :rtype: None

        *smart_send* can be used to send a single message or multiple
        messages to a single remote thread, to multiple remote threads,
        or to every active remote thread in the configuration. A message
        is any type (e.g., text, int, float, list, set, or
        class object).

        The *msg* arg species the message or messages to be sent. A
        special case exists where the message can be specified as an
        instance of the SendMsgs class where the messages for one or
        more targets are placed into a dictionary indexed by the target
        names. The *receiver* arg must be omitted when a SendMsgs object
        is specified.

        The *receivers* arg specifies the names of remote threads that
        the message is to be sent to. There are two cases where
        *receivers* is not specified:

            1) when a SendMsgs object is specified for the *msgs* arg.
            2) when a broadcast message is to be sent to all remote
               threads in the configuration that are currently active
               when the *smart_send* is issued.

        The thread names specified for *receivers* or in a SendMsgs
        object may be in states unregistered, registered, or alive.
        *smart_send* will complete the send for any *receivers* that are
        in the unregistered or registered state as soon as they go to
        the alive state. If timeout is specified, a timeout error will
        be raised if any threads did not become alive with the
        specified amount of time.

        An error will be raised if any receivers are stopped before the
        message can be sent to them. This is true for receivers that are
        specified as an argument for *receivers*, specified in the
        SendMsgs object, or chosen for a broadcast message because they
        were alive at the time of the *send_msg*.


        Examples in this section cover the following cases:

            1) send a single message to a single remote thread
            2) send a single message to multiple remote threads
            3) send a single message to all remote threads in the
               configuration
            4) send multiple messages to a single remote thread
            5) send multiple messages to multiple remote threads
            6) send any mixture of single and multiple messages
               individually to each remote thread

        **Example 1:** send a single message to a single remote thread

        .. code-block:: python

            from scottbrian_paratools.smart_thread import SmartThread

            def f1(smart_thread: SmartThread) -> None:
                print('f1 beta entered')
                my_msg = smart_thread.smart_recv(senders='alpha')
                print(my_msg)
                print('f1 beta exiting')

            print('mainline alpha entered')
            alpha_smart_thread = SmartThread(name='alpha')
            beta_smart_thread = SmartThread(name='beta',
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
            {'alpha': 'hello beta'}
            f1 beta exiting
            mainline alpha exiting

        **Example 2:** send a single message to multiple remote threads

        .. code-block:: python

            from scottbrian_paratools.smart_thread import SmartThread
            import time

            def f1(smart_thread: SmartThread) -> None:
                if smart_thread.name == 'charlie':
                    time.sleep(0.5)  # delay for non-interleaved msgs
                print(f'f1 {smart_thread.name} entered')
                my_msg = smart_thread.smart_recv(senders='alpha')
                print(my_msg)
                print(f'f1 {smart_thread.name} exiting')

            print('mainline alpha entered')
            alpha_smart_thread = SmartThread(name='alpha')
            beta_smart_thread = SmartThread(name='beta',
                                            target=f1,
                                            thread_parm_name='smart_thread')
            charlie_smart_thread = SmartThread(name='charlie',
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
            {'alpha': ['hello remotes']}
            f1 beta exiting
            f1 charlie entered
            {'alpha': ['hello remotes']}
            f1 charlie exiting
            mainline alpha exiting

        **Example 3:** send a single message to all alive remote threads
        in the configuration as a broadcast (by simply omitting the
        *receivers* argument). Note the use of smart_wait and
        smart_resume being used here to make sure the print output
        is in the expected ordered.

        .. code-block:: python

            from scottbrian_paratools.smart_thread import SmartThread

            def f1(smart_thread: SmartThread,
                   wait_for: Optional[str] = None,
                   resume_target: Optional[str] = None) -> None:
                if wait_for:
                    smart_thread.smart_wait(resumers=wait_for)
                print(f'f1 {smart_thread.name} entered')
                my_msg = smart_thread.smart_recv(senders='alpha')
                print(my_msg)
                print(f'f1 {smart_thread.name} exiting')
                if resume_target:
                    smart_thread.smart_resume(waiters=resume_target)

            print('mainline alpha entered')
            alpha_smart_thread = SmartThread(name='alpha')
            beta_smart_thread = SmartThread(name='beta',
                                            target=f1,
                                            thread_parm_name='smart_thread',
                                            kwargs={
                                                'resume_target':'charlie'})
            charlie_smart_thread = SmartThread(name='charlie',
                                               target=f1,
                                               thread_parm_name='smart_thread',
                                               kwargs={
                                                   'wait_for': 'beta',
                                                   'resume_target': 'delta'})
            delta_smart_thread = SmartThread(name='delta',
                                             target=f1,
                                             thread_parm_name='smart_thread',
                                             kwargs={
                                                 'wait_for': 'charlie',
                                                 'resume_target': 'alpha'})
            alpha_smart_thread.smart_send(msg='hello remotes')
            alpha_smart_thread.smart_wait(resumers='delta')
            alpha_smart_thread.smart_join(targets=('beta', 'charlie', 'delta'))
            print('mainline alpha exiting')

        .. invisible-code-block: python

            del SmartThread._registry['alpha']

        Expected output for Example 3::

            mainline alpha entered
            f1 beta entered
            {'alpha': ['hello remotes']}
            f1 beta exiting
            f1 charlie entered
            {'alpha': ['hello remotes']}
            f1 charlie exiting
            f1 delta entered
            {'alpha': ['hello remotes']}
            f1 delta exiting
            mainline alpha exiting

        **Example 4:** send multiple messages to a single remote thread

        .. code-block:: python

            from scottbrian_paratools.smart_thread import SmartThread

            def f1(smart_thread: SmartThread) -> None:
                print(f'f1 {smart_thread.name} entered')
                my_msg = smart_thread.smart_recv(senders='alpha')
                print(my_msg)
                print(f'f1 {smart_thread.name} exiting')

            print('mainline alpha entered')
            alpha_smart_thread = SmartThread(name='alpha')
            beta_smart_thread = SmartThread(name='beta',
                                            target=f1,
                                            thread_parm_name='smart_thread')
            alpha_smart_thread.smart_send(msg=('hello beta',
                                               'have a great day', 42))
            alpha_smart_thread.smart_join(targets='beta')
            print('mainline alpha exiting')

        .. invisible-code-block: python

            del SmartThread._registry['alpha']

        Expected output for Example 4::

            mainline alpha entered
            f1 beta entered
            {'alpha': [('hello beta', 'have a great day', 42)]}
            f1 beta exiting
            mainline alpha exiting

        **Example 5:** send multiple messages to multiple remote threads

        .. code-block:: python

            from scottbrian_paratools.smart_thread import SmartThread

            def f1(smart_thread: SmartThread,
                   wait_for: Optional[str] = None,
                   resume_target: Optional[str] = None) -> None:
                if wait_for:
                    smart_thread.smart_wait(resumers=wait_for)
                print(f'f1 {smart_thread.name} entered')
                my_msg = smart_thread.smart_recv(senders='alpha')
                print(my_msg)
                print(f'f1 {smart_thread.name} exiting')
                if resume_target:
                    smart_thread.smart_resume(waiters=resume_target)

            print('mainline alpha entered')
            alpha_smart_thread = SmartThread(name='alpha')
            beta_smart_thread = SmartThread(name='beta',
                                            target=f1,
                                            thread_parm_name='smart_thread',
                                            kwargs={
                                                'resume_target':'charlie'})
            charlie_smart_thread = SmartThread(name='charlie',
                                               target=f1,
                                               thread_parm_name='smart_thread',
                                               kwargs={
                                                   'wait_for': 'beta',
                                                   'resume_target': 'delta'})
            delta_smart_thread = SmartThread(name='delta',
                                             target=f1,
                                             thread_parm_name='smart_thread',
                                             kwargs={
                                                 'wait_for': 'charlie',
                                                 'resume_target': 'alpha'})
            alpha_smart_thread.smart_send(msg=['hello remotes',
                                               'have a great day', 42],
                                          receivers=['beta',
                                                     'charlie',
                                                     'delta'])
            alpha_smart_thread.smart_wait(resumers='delta')
            alpha_smart_thread.smart_join(targets=('beta', 'charlie', 'delta'))
            print('mainline alpha exiting')

        .. invisible-code-block: python

            del SmartThread._registry['alpha']

        Expected output for Example 5::

            mainline alpha entered
            f1 beta entered
            {'alpha': [['hello remotes', 'have a great day', 42]]}
            f1 beta exiting
            f1 charlie entered
            {'alpha': [['hello remotes', 'have a great day', 42]]}
            f1 charlie exiting
            f1 delta entered
            {'alpha': [['hello remotes', 'have a great day', 42]]}
            f1 delta exiting
            mainline alpha exiting

        **Example 6:** send any mixture of single and multiple messages
        individually to each remote thread

        .. code-block:: python

            from scottbrian_paratools.smart_thread import SmartThread

            def f1(smart_thread: SmartThread,
                   wait_for: Optional[str] = None,
                   resume_target: Optional[str] = None) -> None:
                if wait_for:
                    smart_thread.smart_wait(resumers=wait_for)
                print(f'f1 {smart_thread.name} entered')
                my_msg = smart_thread.smart_recv(senders='alpha')
                print(my_msg)
                print(f'f1 {smart_thread.name} exiting')
                if resume_target:
                    smart_thread.smart_resume(waiters=resume_target)

            print('mainline alpha entered')
            alpha_smart_thread = SmartThread(name='alpha')
            beta_smart_thread = SmartThread(name='beta',
                                            target=f1,
                                            thread_parm_name='smart_thread',
                                            kwargs={
                                                'resume_target':'charlie'})
            charlie_smart_thread = SmartThread(name='charlie',
                                               target=f1,
                                               thread_parm_name='smart_thread',
                                               kwargs={
                                                   'wait_for': 'beta',
                                                   'resume_target': 'delta'})
            delta_smart_thread = SmartThread(name='delta',
                                             target=f1,
                                             thread_parm_name='smart_thread',
                                             kwargs={
                                                 'wait_for': 'charlie',
                                                 'resume_target': 'alpha'})
            msgs_to_send = SendMsgs(send_msgs= {
                'beta': 'hi beta',
                'charlie': ('hi charlie', 'have a great day'),
                'delta': [42, 'hi delta', {'nums': (1, 2, 3)}]})
            alpha_smart_thread.smart_send(msg=msgs_to_send)
            alpha_smart_thread.smart_wait(resumers='delta')
            alpha_smart_thread.smart_join(targets=('beta', 'charlie', 'delta'))
            print('mainline alpha exiting')

        .. invisible-code-block: python

            del SmartThread._registry['alpha']

        Expected output for Example 6::

            mainline alpha entered
            f1 beta entered
            {'alpha': 'hi beta'}
            f1 beta exiting
            f1 charlie entered
            {'alpha': [('hi charlie', 'have a great day')]}
            f1 charlie exiting
            f1 delta entered
            {'alpha': [[42, 'hi delta', {'nums': (1, 2, 3)}]]}
            f1 delta exiting
            mainline alpha exiting

        """
        self.request = ReqType.Smart_send
        work_targets: set[str]
        if not receivers:
            if isinstance(msg, SendMsgs):
                work_targets = set(msg.send_msgs.keys())
            else:
                work_targets = set()
                with sel.SELockShare(SmartThread._registry_lock):
                    for remote in SmartThread._registry:
                        if (remote != self.name and
                                self._get_state(remote) == ThreadState.Alive):
                            work_targets |= {remote}
        else:
            work_targets = self._get_set(receivers)

        if not work_targets:
            raise SmartThreadNoRemoteTargets(
                f'{self.name} issued a smart_send request but there are '
                'no remote receivers in the configuration to send to')

        work_msgs: SendMsgs
        if isinstance(msg, SendMsgs):
            work_msgs = msg
        else:
            work_msgs = SendMsgs({})
            for target in work_targets:
                work_msgs.send_msgs[target] = msg

        # get RequestBlock with targets in a set and a timer object
        request_block = self._request_setup(
            remotes=work_targets,
            error_stopped_target=True,
            process_rtn=self._process_send_msg,
            cleanup_rtn=None,
            get_block_lock=False,
            completion_count=0,
            timeout=timeout,
            msg_to_send=work_msgs,
            log_msg=log_msg)

        self._request_loop(request_block=request_block)

        self.request = ReqType.NoReq

        logger.debug(request_block.exit_log_msg)

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
                    remote_sb.msg_q.put(request_block.msg_to_send.send_msgs[
                                            pk_remote.remote],
                                        timeout=0.01)
                    logger.info(
                        f'{self.name} smart_send sent message to '
                        f'{pk_remote.remote}')

                    return True
                except queue.Full:
                    # We fail this request when the msg_q is full
                    request_block.full_send_q_remotes |= {pk_remote.remote}
                    return True  # we are done with this target
        else:
            if remote_state == ThreadState.Stopped:
                request_block.stopped_remotes |= {pk_remote.remote}
                # request_block.do_refresh = True
                return True  # we are done with this remote

        return False  # give the remote some more time

    ####################################################################
    # smart_recv
    ####################################################################
    def smart_recv(self,
                   received_msgs: RecvMsgs,
                   senders: Optional[Iterable] = None,
                   timeout: OptIntFloat = None,
                   log_msg: Optional[str] = None) -> None:
        """Receive one or more messages from remote threads.

        Args:
            senders: thread names whose sent messages are to be received
            received_msgs: the RecvMsgs object where messages will be
                placed as they are received
            timeout: number of seconds to wait for message
            log_msg: additional text to append to the debug log message
                that is issued on request entry and exit

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
               and a smart_recv will not deadlock is a message was
               already delivered earlier by a smart_send.

        For *smart_recv*, a message is any type (e.g., text, lists,
        sets, class objects). *smart_recv* can be used to receive a
        single message or multiple messages from a single remote
        thread, from multiple remote threads, or from every remote
        thread in the configuration. *smart_recv* will return
        messages in a dictionary indexed by sender thread name.

        When *smart_recv* gets control, it will check its message
        queues for each of the specified senders and place any messages
        found into the received_msgs dictionary (type RecvMsgs) and
        then return. If no messages were initially found, *smart_recv*
        will continue to periodically check until one or more messages
        arrive, at which point it place then into the received_msgs and
        return them. If timeout is specified, *smart_recv* will raise a
        timeout error if no messages appear within the specified time.

        If no senders are specified, the *smart_recv* will check its
        message queues for all threads in the current configuration. If
        no messages are found, *smart_recv* will continue to check all
        threads in the current configuration, even as the configuration
        changes. When no senders are specifies, *smart_recv* will not
        raise an error if any of the remote threads become inactive. In
        this way, a thread acting as a server can issue the *smart_recv*
        to simply park itself on the message queues of all threads
        currently in the configuration and return with any messages as
        soon as they arrive.

        If senders are specified, *smart_recv* will look for messages
        only on its message queues for the specified senders. Unlike
        the "no senders specified" case, *smart_recv* will raise an
        error if any of the specified senders become inactive.

        If *smart_recv* raises an error, any messages that were received
        will have been placed into *received_msgs* and will thus be
        available to the caller during its recovery processing.

        Examples in this section cover the following cases:

            1) receive a single message from a single remote thread
            2) receive a single message from multiple remote threads
            3) receive a single message from all remote threads in the
               configuration
            4) receive multiple messages from a single remote thread
            5) receive multiple messages from multiple remote threads

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

        **Example 3:** receive a single message from all remote threads
        in the configuration

        .. code-block:: python

            from scottbrian_paratools.smart_thread import SmartThread
            import time

            def f1(greeting: str, smart_thread: SmartThread) -> None:
                print(f'f1 {smart_thread.name} entered')
                smart_thread.smart_send(msg=f'{greeting}',
                                        receivers='alpha')
                print(f'f1 {smart_thread.name} exiting')

            print('mainline alpha entered')
            alpha_smart_thread = SmartThread(name='alpha')
            beta_smart_thread = SmartThread(name='beta',
                                            target=f1,
                                            thread_parm_name='smart_thread',
                                            args=('hi',))
            time.sleep(0.2)
            charlie_smart_thread = SmartThread(name='charlie',
                                               target=f1,
                                               thread_parm_name='smart_thread',
                                               args=('hello',))
            time.sleep(0.2)
            delta_smart_thread = SmartThread(name='delta',
                                             target=f1,
                                             thread_parm_name='smart_thread',
                                             args=('aloha',))
            time.sleep(0.2)
            my_msg = alpha_smart_thread.smart_recv()
            print(my_msg['beta'])
            print(my_msg['charlie'])
            print(my_msg['delta'])
            alpha_smart_thread.smart_join(targets=('beta',
                                                   'charlie',
                                                   'delta'))
            print('mainline alpha exiting')

        .. invisible-code-block: python

            del SmartThread._registry['alpha']

        Expected output for Example 3::

            mainline alpha entered
            f1 beta entered
            f1 beta exiting
            f1 charlie entered
            f1 charlie exiting
            f1 delta entered
            f1 delta exiting
            ['hi']
            ['hello']
            ['aloha']
            mainline alpha exiting

        **Example 4:** receive multiple messages from a single remote
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

        Expected output for Example 4::
            mainline alpha entered
            f1 beta entered
            f1 beta exiting
            {'beta': ['hi', ["it's great to be here", "life is good"],
            ("let's do lunch sometime", "Tuesday afternoons are best")]}
            mainline alpha exiting

        **Example 5:** receive any mixture of single and multiple
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

        Expected output for Example 5::

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
        self.request = ReqType.Smart_recv
        # get RequestBlock with targets in a set and a timer object
        request_block = self._request_setup(
            remotes=senders,
            error_stopped_target=True,
            process_rtn=self._process_recv_msg,
            cleanup_rtn=None,
            get_block_lock=False,
            completion_count=0,
            timeout=timeout,
            log_msg=log_msg)

        request_block.ret_msg = received_msgs
        self._request_loop(request_block=request_block)

        logger.debug(request_block.exit_log_msg)

        self.request = ReqType.NoReq

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
        # We start off assuming remote is alive and we have a msg,
        # meaning we make the timeout_value very small just to test
        # the msg_q. If there is no msg, we check the remote state
        # and to decide whether to fail the smart_recv (remote
        # stopped), try to retrieve the msg again with a longer
        # timeout_value (remote alive), or return False to give
        # the remote more time (remote is not alive, but no stopped)
        # for timeout_value in (SmartThread.K_REQUEST_MIN_INTERVAL,
        #                       request_block.request_max_interval):
        #     try:
        #         # recv message from remote
        #         request_block.ret_msg = local_sb.msg_q.get(
        #             timeout=timeout_value)
        #         logger.info(
        #             f'{self.name} received msg from {pk_remote.remote}')
        #         # if we had wanted to delete an entry in the
        #         # pair array for this thread because the other
        #         # thread exited, but we could not because this
        #         # thread had a pending msg to recv, then we
        #         # deferred the delete. If the msg_q for this
        #         # thread is now empty as a result of this recv,
        #         # we can go ahead and delete the pair, so
        #         # set the flag to do a refresh
        #         if local_sb.del_deferred and local_sb.msg_q.empty():
        #             request_block.do_refresh = True
        #         return True
        #
        #     except queue.Empty:
        #         # The msg queue was just now empty which rules out
        #         # that case that the pair_key is valid only because
        #         # of a deferred delete. So, we know the remote is in
        #         # the registry and in the status block.
        #
        #         remote_state = self._get_target_state(pk_remote)
        #
        #         if remote_state == ThreadState.Stopped:
        #             request_block.stopped_remotes |= {pk_remote.remote}
        #             request_block.do_refresh = True
        #             return True  # we are done with this remote
        #
        #         if remote_state != ThreadState.Alive:
        #             return False  # remote needs more time

        # return False
        for timeout_value in (SmartThread.K_REQUEST_MIN_INTERVAL,
                              request_block.request_max_interval):
            try:
                # logger.debug(f'TestDebug {self.name} checking for message '
                #              f'from {pk_remote.remote}')
                received_msgs: list[Any] = []
                # recv message from remote
                with SmartThread._pair_array[pk_remote.pair_key].status_lock:
                    recvd_msg = local_sb.msg_q.get(
                        timeout=timeout_value)
                    received_msgs.append(recvd_msg)
                    logger.info(
                        f'{self.name} smart_recv received msg from '
                        f'{pk_remote.remote}')
                    while not local_sb.msg_q.empty():
                        recvd_msg = local_sb.msg_q.get()
                        received_msgs.append(recvd_msg)
                    # reset recv_wait after we get messages instead of
                    # before so as to avoid having the flag being
                    # momentarily False with the msg_q empty in the
                    # small gap between the try attempt and an
                    # exception. This will prevent the remote from
                    # missing a deadlock detection case during the gap.
                    local_sb.recv_wait = False

                # if here, msg_q was not empty (i.e., no exception)
                request_block.ret_msg.recv_msgs[pk_remote.remote] = received_msgs
                logger.debug(f'TestDebug {self.name} got message '
                             f'from {pk_remote.remote}, {received_msgs=}')
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
                   wait_for: WaitFor = WaitFor.All,
                   resumed_by: Optional[set[str]] = None,
                   timeout: OptIntFloat = None,
                   log_msg: Optional[str] = None) -> None:
        """Wait until resumed.

        Args:
            resumers: names of threads that we expect to resume us
            wait_for: specifies whether to wait for only one remote or
                for all remotes
            resumed_by: list of thread names that the wait detected as
                having done a resume. Note that the list is a subset of
                the specified *resumers*. If the *wait_for*
                specification is WaitFor.All, then *resumed_by* will
                be equal to *resumers*.
            timeout: number of seconds to allow for wait to be
                resumed
            log_msg: additional text to append to the debug log message
                that is issued on request entry and exit

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
               and a smart_recv will not deadlock is a message was
               already delivered earlier by a smart_send.

        smart_wait waits until it is resumed. These are the cases:

            1) smart_wait can provide one remote thread name as an
               argument for the *resumers* parameter and will then wait
               until that resumer issues a matching smart_resume.
            2) smart_wait can provide multiple remote thread names as an
               argument for the *resumers* parameter and:
               a) with *wait_for* specified as WaitFor.All, wait for all
               resumers to issue a matching smart_resume.
               b) with *wait_for* specified as WaitFor.Any, wait until
               at least one resumer issues a matching smart_resume.
            3) smart_wait can omit the specification of *resumers*. In
               this case, smart_wait will wait until at least one thread
               in the configuration does a matching smart_resume. The
               configuration can change with new threads becoming
               active and other threads being stopped while smart_wait
               continues to wait.

        For cases 1 and 2: an error is raised if any of the specified
        resumer threads is stopped before it issues the smart_resume.

        For cases 1, 2, and 3: if timeout is specified, a timeout error
        is raised if the smart_wait is not resumed within the specified
        time.

        Note that a smart_resume can be issued before the smart_wait is
        issued, in which case the smart_wait will return immediately
        if any and all expected resumes were already issued.

        Examples in this section cover the following cases:

            1) smart_wait followed by smart_resume
            2) smart_wait preceded by smart_resume
            3) smart_wait for multiple resumers with WaitFor.All
            4) smart_wait for multiple resumers with WaitFor.Any
            5) smart_wait for any resumers in configuration

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

        **Example 3:** smart_wait for multiple resumers with WaitFor.All

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
                resumers=['beta', 'charlie', 'delta'],
                wait_for=WaitFor.All)
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
                resumers=['beta', 'charlie', 'delta'],
                wait_for=WaitFor.Any)
            print(f'alpha resumed by resumers={sorted(resumers)}')
            delta_smart_thread = SmartThread(name='delta',
                                             target=f1,
                                             thread_parm_name='smart_thread')
            time.sleep(1)  # allow time for alpha to wait
            print('alpha about to wait for any threads')
            resumers = alpha_smart_thread.smart_wait(
                resumers=['beta', 'charlie', 'delta'],
                wait_for=WaitFor.Any)
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

        **Example 5:** smart_wait for any resumers in configuration

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
            resumers = alpha_smart_thread.smart_wait()
            print(f'alpha resumed by resumers={sorted(resumers)}')
            delta_smart_thread = SmartThread(name='delta',
                                             target=f1,
                                             thread_parm_name='smart_thread')
            time.sleep(1)  # allow time for alpha to wait
            print('alpha about to wait for any threads')
            resumers = alpha_smart_thread.smart_wait()
            print(f'alpha resumed by resumers={sorted(resumers)}')
            alpha_smart_thread.smart_join(targets=['beta', 'charlie', 'delta'])
            print('mainline alpha exiting')

        .. invisible-code-block: python

            del SmartThread._registry['alpha']

        Expected output for Example 5::

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
        self.request = ReqType.Smart_wait
        # get RequestBlock with targets in a set and a timer object
        request_block = self._request_setup(
            remotes=resumers,
            error_stopped_target=True,
            process_rtn=self._process_wait,
            cleanup_rtn=self._sync_wait_error_cleanup,
            get_block_lock=True,
            completion_count=0,
            timeout=timeout,
            log_msg=log_msg)

        if wait_for == WaitFor.Any:
            self.wait_for_any = True
            request_block.completion_count = len(request_block.remotes) - 1

        if resumed_by is None:
            # we will set to an empty set to make processing easier
            request_block.ret_resume_result = set()
        elif isinstance(resumed_by, set):
            request_block.ret_resume_result = resumed_by
        else:
            raise SmartThreadInvalidInput(
                f'{self.name} processing a smart_wait detected that'
                f' {resumed_by=} is neither None nor a set')

        self._request_loop(request_block=request_block)

        logger.debug(request_block.exit_log_msg)

        self.request = ReqType.NoReq
        self.wait_for_any = False

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
                request_block.ret_resume_result |= {pk_remote.remote}
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
                     log_msg: Optional[str] = None) -> None:
        """Resume a waiting or soon to be waiting thread.

        Args:
            waiters: names of threads that are to be resumed
            timeout: number of seconds to allow for ``resume()`` to
                complete
            log_msg: additional text to append to the debug log message
                that is issued on request entry and exit

        Raises:
            SmartThreadRemoteThreadNotAlive: waiter thread was
                stopped.
            SmartThreadRequestTimedOut: request timed out before
                being resumed.

        .. # noqa: DAR402

        :rtype: None

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
        self.request = ReqType.Smart_resume
        # get RequestBlock with targets in a set and a timer object
        request_block = self._request_setup(
            remotes=waiters,
            error_stopped_target=True,
            process_rtn=self._process_resume,
            cleanup_rtn=None,
            get_block_lock=True,
            completion_count=0,
            timeout=timeout,
            log_msg=log_msg)

        self._request_loop(request_block=request_block)

        self.request = ReqType.NoReq

        logger.debug(request_block.exit_log_msg)

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
                    return True
        else:
            if remote_state == ThreadState.Stopped:
                request_block.stopped_remotes |= {pk_remote.remote}
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
                   log_msg: Optional[str] = None):
        """Sync up with remote threads.

        Args:
            targets: remote threads we will sync with
            timeout: number of seconds to allow for sync to happen
            log_msg: additional text to append to the debug log message
                that is issued on request entry and exit

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
               and a smart_recv will not deadlock is a message was
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
        self.request = ReqType.Smart_sync
        # get RequestBlock with targets in a set and a timer object
        request_block = self._request_setup(
            remotes=targets,
            error_stopped_target=True,
            process_rtn=self._process_sync,
            cleanup_rtn=self._sync_wait_error_cleanup,
            get_block_lock=True,
            completion_count=0,
            timeout=timeout,
            log_msg=log_msg)

        self._request_loop(request_block=request_block)

        self.request = ReqType.NoReq

        logger.debug(request_block.exit_log_msg)

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
                    # request_block.do_refresh = True
                    return True  # we are done with this remote
                else:
                    return False  # remote needs more time
            else:
                # If here, remote is in registry and is alive. This also
                # means we have an entry for the remote in the
                # pair_array

                # setup a reference
                remote_sb = SmartThread._pair_array[
                    pk_remote.pair_key].status_blocks[
                    pk_remote.remote]
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
                # We need to the lock to coordinate with the remote
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

                # exit, we are done with this remote
                return True

            # Check for error conditions first before
            # checking whether the remote is alive. If the
            # remote detects a deadlock issue,
            # it will set the flags in our entry and then
            # raise an error and will likely be gone when we
            # check. We want to raise the same error on
            # this side.

            if pk_remote.remote in SmartThread._pair_array[
                    pk_remote.pair_key].status_blocks:
                remote_sb = SmartThread._pair_array[
                    pk_remote.pair_key].status_blocks[pk_remote.remote]

                with SmartThread._pair_array[pk_remote.pair_key].status_lock:
                    self._check_for_deadlock(local_sb=local_sb,
                                             remote_sb=remote_sb)

                    if (local_sb.deadlock or self._get_target_state(
                            pk_remote)
                            == ThreadState.Stopped):
                        remote_sb.sync_event.clear()
                        # request_block.do_refresh = True

            if local_sb.deadlock:
                request_block.deadlock_remotes |= {pk_remote.remote}
                local_sb.sync_wait = False
                logger.debug(
                    f'TestDebug {self.name} sync set '
                    f'{request_block.deadlock_remotes=}')
                return True  # we are done with this remote

            if self._get_target_state(pk_remote) == ThreadState.Stopped:
                request_block.stopped_remotes |= {pk_remote.remote}
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
                    # the remote did not set out event yet
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
                                remote_sb.sync_event.clear()
                                logger.info(
                                    f'{self.name} smart_sync backout reset '
                                    f'remote sync_event for {remote}')
                    if backout_request == 'smart_wait' and local_sb.wait_wait:
                        local_sb.wait_wait = False
                        local_sb.wait_event.clear()

                    local_sb.deadlock = False

    ####################################################################
    # _config_cmd_loop
    ####################################################################
    def _config_cmd_loop(self, *,
                         request_block: RequestBlock,
                         ) -> None:
        """Main loop for each config command.

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

        """
        with self.cmd_lock:
            self.work_remotes: set[str] = request_block.remotes.copy()

            while len(self.work_remotes) > request_block.completion_count:
                num_start_loop_work_remotes = len(self.work_remotes)
                for remote in self.work_remotes.copy():
                    with sel.SELockExcl(SmartThread._registry_lock):
                        if request_block.process_rtn(request_block,
                                                     remote):
                            self.work_remotes -= {remote}

                # if no progress was made
                if len(self.work_remotes) == num_start_loop_work_remotes:
                    if ((request_block.error_stopped_target
                         and request_block.stopped_remotes)
                            or (request_block.error_not_registered_target
                                and request_block.not_registered_remotes)
                            or request_block.timer.is_expired()):
                        self._handle_loop_errors(request_block=request_block,
                                                 pending_remotes=list(
                                                     self.work_remotes))

                time.sleep(0.2)

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
                     / len(self.work_pk_remotes))
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
                        # references
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
                            # having an alive remote (smart_recv and wait,
                            # for example, do not require an alive
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

            # handle any error or timeout cases - don't worry about any
            # remotes that were still pending - we need to fail the
            # request as soon as we know about any unresolvable failures
            if ((request_block.stopped_remotes and request_block.remotes
                 and not (self.request == ReqType.Smart_wait
                          and self.wait_for_any
                          and request_block.ret_resume_result))
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
                            SmartThread._pair_array[
                                pair_key].status_blocks[
                                self.name].request_pending = False
                            SmartThread._pair_array[
                                pair_key].status_blocks[
                                self.name].request = ReqType.NoReq

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

            if request_block.remotes:  # remotes were specified
                if len(self.work_pk_remotes) <= request_block.completion_count:
                    continue_request_loop = False
            else:
                if (request_block.request == ReqType.Smart_recv
                        and request_block.ret_msg.recv_msgs):
                    continue_request_loop = False
                elif (request_block.request == ReqType.Smart_wait
                      and request_block.ret_resume_result):
                    continue_request_loop = False
                else:  # keep looking
                    self._set_work_pk_remotes(request_block.request)
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
                             request: ReqType,
                             remotes: Optional[set[str]] = None) -> None:
        """Update the work_pk_remotes with newly found threads.

        Args:
            request: type of request being performed
            remotes: names of threads that are targets for the
                request

        """
        pk_remotes: list[PairKeyRemote] = []

        with sel.SELockExcl(SmartThread._registry_lock):
            if not remotes:
                remotes: set[str] = set()
                for pair_key, item in SmartThread._pair_array.items():
                    if self.name not in pair_key:
                        continue

                    local_sb = SmartThread._pair_array[
                            pair_key].status_blocks[self.name]
                    if ((request == ReqType.Smart_recv
                            and not local_sb.msg_q.empty())
                            or (request == ReqType.Smart_wait
                                and local_sb.wait_event.is_set())):
                        if self.name == pair_key[0]:
                            remotes |= {pair_key[1]}
                        else:
                            remotes |= {pair_key[0]}

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
                raise SmartThreadWorkDataException(
                    f'_handle_found_pk_remotes failed to find an '
                    f'entry for {found_pk_remote=} in '
                    f'{self.work_pk_remotes=}')

            try:
                idx = work_pk_remotes.index(test_pk_remote)
                work_pk_remotes[idx] = PairKeyRemote(
                    found_pk_remote.pair_key,
                    found_pk_remote.remote,
                    found_pk_remote.create_time)

            except ValueError:
                raise SmartThreadWorkDataException(
                    f'_handle_found_pk_remotes failed to find an '
                    f'entry for {found_pk_remote=} in '
                    f'{self.work_pk_remotes=}')

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
                f' Remotes who have a full send_q: '
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
        # if the deadlock has already been detected by
        # the remote, no need to analyse this side. Just
        # drop down to the code below to return with the
        # error.
        if not local_sb.deadlock:
            # the following checks apply to both
            # sync_wait and wait_wait
            if (remote_sb.sync_wait
                    and not local_sb.request == ReqType.Smart_sync
                    and not (remote_sb.sync_event.is_set()
                             or remote_sb.deadlock)):
                remote_sb.deadlock = True
                remote_sb.remote_deadlock_request = local_sb.request
                local_sb.deadlock = True
                local_sb.remote_deadlock_request = ReqType.Smart_sync
                logger.debug(
                    f'TestDebug {self.name} wait '
                    f'set remote and local '
                    f'deadlock flags {remote_sb.name=}')
            elif (remote_sb.wait_wait
                    and not (remote_sb.wait_event.is_set()
                             or remote_sb.deadlock)):
                remote_sb.deadlock = True
                remote_sb.remote_deadlock_request = local_sb.request
                local_sb.deadlock = True
                local_sb.remote_deadlock_request = ReqType.Smart_wait
                logger.debug(
                    f'TestDebug {self.name} wait '
                    f'set remote and local '
                    f'deadlock flags {remote_sb.name=}')
            elif (remote_sb.recv_wait
                    and (remote_sb.msg_q.empty()
                         or remote_sb.deadlock)):
                remote_sb.deadlock = True
                remote_sb.remote_deadlock_request = local_sb.request
                local_sb.deadlock = True
                local_sb.remote_deadlock_request = ReqType.Smart_recv
                logger.debug(
                    f'TestDebug {self.name} wait '
                    f'set remote and local '
                    f'deadlock flags {remote_sb.name=}')

    ####################################################################
    # _request_setup
    ####################################################################
    def _request_setup(self, *,
                       process_rtn: Callable[
                           ["RequestBlock",
                            PairKeyRemote,
                            "SmartThread.ConnectionStatusBlock"], bool],
                       cleanup_rtn: Optional[Callable[[list[PairKeyRemote],
                                                       str], None]],
                       get_block_lock: bool,
                       error_stopped_target: bool,
                       remotes: Optional[Iterable] = None,
                       error_not_registered_target: bool = False,
                       completion_count: int = 0,
                       timeout: OptIntFloat = None,
                       log_msg: Optional[str] = None,
                       msg_to_send: Optional[SendMsgs] = None,
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
            if self.request not in (ReqType.Smart_recv, ReqType.Smart_wait):
                raise SmartThreadInvalidInput(
                    f'{self.name} {self.request.value} '
                    'request with no targets specified.')
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

        if self.request not in (ReqType.Smart_start,
                                ReqType.Smart_unreg,
                                ReqType.Smart_join):
            self.verify_thread_is_current()

        if (remotes and self.request != ReqType.Smart_start
                and self.cmd_runner in remotes):
            raise SmartThreadInvalidInput(f'{self.name} {self.request.value} '
                                          f'is also a target: {remotes=}')

        pk_remotes: list[PairKeyRemote] = []

        if self.request in (ReqType.Smart_send, ReqType.Smart_recv,
                            ReqType.Smart_resume, ReqType.Smart_sync,
                            ReqType.Smart_wait):
            self._set_work_pk_remotes(request=self.request,
                                      remotes=remotes)

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
            ret_msg=None,
            ret_resume_result=None,
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
        if remotes:
            targets_to_use = sorted(remotes)
        else:
            # targets_to_use = 'eligible per request'
            targets_to_use = ['']
        log_msg_body = (
            f'requestor: {self.cmd_runner}, '
            f'targets: {targets_to_use} '
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
    # verify_thread_is_current
    ####################################################################
    def verify_thread_is_current(self) -> None:
        """Verify that SmartThread is running under the current thread.

        Raises:
            SmartThreadDetectedOpFromForeignThread: SmartThread services
                must be called from the thread that was originally
                assigned during instantiation of SmartThread.

        """
        if self.thread is not threading.current_thread():
            error_msg = (f'{self.cmd_runner} raising '
                         'SmartThreadDetectedOpFromForeignThread. '
                         f'{self.thread=}, {threading.current_thread()=}. '
                         f'SmartThread services must be called from the '
                         f'thread that was originally assigned during '
                         f'instantiation of SmartThread. '
                         f'Call sequence: {get_formatted_call_sequence(1,2)}')
            logger.error(error_msg)
            raise SmartThreadDetectedOpFromForeignThread(error_msg)

    ####################################################################
    # verify_thread_is_current
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
