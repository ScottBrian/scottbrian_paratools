"""test_se_lock.py module."""

import pytest
import math
import time
from typing import Any, cast, Union, NamedTuple

import threading

from scottbrian_utils.flower_box import print_flower_box_msg as flowers
from scottbrian_utils.diag_msg import diag_msg

from scottbrian_utils.se_lock import SELock, SELockShare, SELockExcl
from scottbrian_utils.se_lock import IncorrectModeSpecified
from scottbrian_utils.se_lock import AttemptedReleaseOfUnownedLock

###############################################################################
# SELock test exceptions
###############################################################################
class ErrorTstSELock(Exception):
    """Base class for exception in this module."""
    pass


class InvalidRouteNum(ErrorTstSELock):
    """InvalidRouteNum exception class."""
    pass


class InvalidModeNum(ErrorTstSELock):
    """InvalidModeNum exception class."""
    pass


class BadRequestStyleArg(ErrorTstSELock):
    """BadRequestStyleArg exception class."""
    pass


###############################################################################
# requests_arg fixture
###############################################################################
requests_arg_list = [1, 2, 3]


@pytest.fixture(params=requests_arg_list)  # type: ignore
def requests_arg(request: Any) -> int:
    """Using different requests.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


###############################################################################
# seconds_arg fixture
###############################################################################
seconds_arg_list = [0.1, 0.5, 1, 2]


@pytest.fixture(params=seconds_arg_list)  # type: ignore
def seconds_arg(request: Any) -> Union[int, float]:
    """Using different seconds.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(Union[int, float], request.param)



###############################################################################
# request_style_arg fixture
###############################################################################
request_style_arg_list = [0, 1, 2, 3, 4, 5, 6]


@pytest.fixture(params=request_style_arg_list)  # type: ignore
def request_style_arg(request: Any) -> int:
    """Using different early_count values.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


###############################################################################
# TestSELockBasic class to test SELock methods
###############################################################################
class TestSELockErrors:
    """TestSELock class."""

    def test_se_lock_bad_args(self) -> None:
        """test_se_lock using bad arguments."""
        #######################################################################
        # bad requests
        #######################################################################
        with pytest.raises(IncorrectModeSpecified):
            a_lock = SELock()
            a_lock.obtain(mode=0)

        with pytest.raises(AttemptedReleaseOfUnownedLock):
            a_lock = SELock()
            a_lock.release()


###############################################################################
# TestSELockBasic class to test SELock methods
###############################################################################
class TestSELockBasic:

    ###########################################################################
    # len checks
    ###########################################################################
    def test_se_lock_len(self) -> None:
        """Test the len of se_lock.

        Args:
            requests_arg: fixture that provides args
            mode_arg: se_lock mode to use

        """
        # create a se_lock and add some waiters

        def excl_func1(a_se_lock, a_event1) -> None:
            """Function to wait for exclusive lock.

            Args:
                a_se_lock: instance of SELock
            """
            with SELockExcl(a_se_lock):
                print('excl_func1 got lock exclusive')
                a_event1.wait()

        def excl_func2(a_se_lock, a_event2) -> None:
            """Function to wait for exclusive lock.

            Args:
                a_se_lock: instance of SELock
            """
            with SELockExcl(a_se_lock):
                print('excl_func2 got lock exclusive')
                a_event2.wait()

        a_lock = SELock()
        a_event1 = threading.Event()
        a_event2 = threading.Event()

        with SELockShare(a_lock):
            assert len(a_lock) == 0
            f1_thread = threading.Thread(target=excl_func1, args=(a_lock,
                                                                  a_event1))
            f1_thread.start()
            time.sleep(1)
            assert len(a_lock) == 1

            f2_thread = threading.Thread(target=excl_func2, args=(a_lock,
                                                                  a_event2))
            f2_thread.start()
            time.sleep(1)
            assert len(a_lock) == 2

        time.sleep(1)
        assert len(a_lock) == 1

        a_event1.set()
        f1_thread.join()
        time.sleep(1)
        assert len(a_lock) == 0

        a_event2.set()
        f2_thread.join()
        assert len(a_lock) == 0

    ###########################################################################
    # repr
    ###########################################################################
    def test_se_lock_repr(self) -> None:
        """test_se_lock repr mode 1 with various requests and seconds.

        Args:
            requests_arg: fixture that provides args
            seconds_arg: fixture that provides args

        """
        a_se_lock = SELock()

        expected_repr_str = 'SELock()'

        assert repr(a_se_lock) == expected_repr_str




###############################################################################
# TestSELock class
###############################################################################
class TestSELock:
    """Class TestSELock.

    The following section tests various scenarios of shared and exclusive
    locking.

    We will try combinations of shared and exclusive obtains and verify that
    the order is requests is maintained.

    Scenario:
       1) obtain 0 to 3 shared - verify
       2) obtain 0 to 3 exclusive - verify
       3) obtain 0 to 3 shared - verify
       4) obtain 0 to 3 exclusive - verify

    """

    ###########################################################################
    # test_se_lock_async
    ###########################################################################
    def test_se_lock_no_with(self,
                             num_share_group1: int,
                             num_excl_group2: int,
                             num_share_group3: int,
                             num_excl_group4: int
                             ) -> None:
        """Method to test se_lock without using with context manager.

        Args:
            num_share_group1: number of shared obtains to do for group1
            num_excl_group2: number of exclusive obtains to do for group2
            num_share_group3: number of shared obtains to do for group3
            num_excl_group4: number of exclusive obtains to do for group4
        """
        class ThreadEvent(NamedTuple):
            thread: threading.Thread
            event: threading.Event

        def f1(a_lock, a_event, mode):
            """Function to get the lock and wait.

            Args:
                a_lock: instance of SELock
                a_event: instance of threading.Event
                mode: shared or exclusive
            """
            a_lock.obtain(mode=mode)
            a_event.wait()
            a_lock.release()

        a_lock = SELock()
        group1 = []
        for idx in range(num_share_group1):
            a_event = threading.Event()
            a_thread = threading.Thread(target=f1, args=(a_lock,
                                                         a_event,
                                                         SELock.SHARE
                                                         ))
            a_thread.start()
            group1.append(ThreadEvent(a_thread, a_event))






    ###########################################################################
    # test_se_lock_sync
    ###########################################################################
    def test_se_lock_sync(self,
            requests_arg: int,
            seconds_arg: Union[int, float],
            early_count_arg: int,
            send_interval_mult_arg: float,
            request_style_arg: int
    ) -> None:
        """Method to start se_lock sync tests

        Args:
            requests_arg: number of requests per interval from fixture
            seconds_arg: interval for number of requests from fixture
            early_count_arg: count used for sync with early count algo
            send_interval_mult_arg: interval between each send of a request
            request_style_arg: chooses function args mix
        """
        send_interval = (seconds_arg / requests_arg) * send_interval_mult_arg
        self.se_lock_router(requests=requests_arg,
                             seconds=seconds_arg,
                             mode=SELock.MODE_SYNC_EC,
                             early_count=0,
                             lb_threshold=0,
                             send_interval=send_interval,
                             request_style=request_style_arg)

    ###########################################################################
    # test_se_lock_sync_ec
    ###########################################################################
    def test_se_lock_sync_ec(self,
            requests_arg: int,
            seconds_arg: Union[int, float],
            early_count_arg: int,
            send_interval_mult_arg: float,
            request_style_arg: int
    ) -> None:
        """Method to start se_lock sync_ec tests

        Args:
            requests_arg: number of requests per interval from fixture
            seconds_arg: interval for number of requests from fixture
            early_count_arg: count used for sync with early count algo
            send_interval_mult_arg: interval between each send of a request
            request_style_arg: chooses function args mix
        """
        send_interval = (seconds_arg / requests_arg) * send_interval_mult_arg
        self.se_lock_router(requests=requests_arg,
                             seconds=seconds_arg,
                             mode=SELock.MODE_SYNC_EC,
                             early_count=early_count_arg,
                             lb_threshold=0,
                             send_interval=send_interval,
                             request_style=request_style_arg)

    ###########################################################################
    # test_se_lock_sync_lb
    ###########################################################################
    def test_se_lock_sync_lb(self,
            requests_arg: int,
            seconds_arg: Union[int, float],
            lb_threshold_arg: Union[int, float],
            send_interval_mult_arg: float,
            request_style_arg: int
    ) -> None:
        """Method to start se_lock sync_lb tests

        Args:
            requests_arg: number of requests per interval from fixture
            seconds_arg: interval for number of requests from fixture
            lb_threshold_arg: threshold used with sync leaky bucket algo
            send_interval_mult_arg: interval between each send of a request
            request_style_arg: chooses function args mix
        """
        send_interval = (seconds_arg / requests_arg) * send_interval_mult_arg
        self.se_lock_router(requests=requests_arg,
                             seconds=seconds_arg,
                             mode=SELock.MODE_SYNC_LB,
                             early_count=0,
                             lb_threshold=lb_threshold_arg,
                             send_interval=send_interval,
                             request_style=request_style_arg)

    ###########################################################################
    # se_lock_router
    ###########################################################################
    def se_lock_router(self,
            requests: int,
            seconds: Union[int, float],
            mode: int,
            early_count: int,
            lb_threshold: Union[int, float],
            send_interval: float,
            request_style: int
    ) -> None:
        """Method test_se_lock_router.

        Args:
            requests: number of requests per interval
            seconds: interval for number of requests
            mode: async or sync_EC or sync_LB
            early_count: count used for sync with early count algo
            lb_threshold: threshold used with sync leaky bucket algo
            send_interval: interval between each send of a request
            request_style: chooses function args mix

        Raises:
            BadRequestStyleArg: The request style arg must be 0 to 6
        """
        request_multiplier = 32
        #######################################################################
        # Instantiate SELock
        #######################################################################
        if mode == SELock.MODE_ASYNC:
            a_se_lock = SELock(requests=requests,
                                  seconds=seconds,
                                  mode=SELock.MODE_ASYNC,
                                  async_q_size=(requests
                                                * request_multiplier)
                                  )
        elif mode == SELock.MODE_SYNC:
            a_se_lock = SELock(requests=requests,
                                  seconds=seconds,
                                  mode=SELock.MODE_SYNC
                                  )
        elif mode == SELock.MODE_SYNC_EC:
            a_se_lock = SELock(requests=requests,
                                  seconds=seconds,
                                  mode=SELock.MODE_SYNC_EC,
                                  early_count=early_count
                                  )
        elif mode == SELock.MODE_SYNC_LB:
            a_se_lock = SELock(requests=requests,
                                  seconds=seconds,
                                  mode=SELock.MODE_SYNC_LB,
                                  lb_threshold=lb_threshold
                                  )
        else:
            raise InvalidModeNum('The Mode must be 1, 2, 3, or 4')

        #######################################################################
        # Instantiate Request Validator
        #######################################################################
        request_validator = RequestValidator(requests=requests,
                                             seconds=seconds,
                                             mode=mode,
                                             early_count=early_count,
                                             lb_threshold=lb_threshold,
                                             request_mult=request_multiplier,
                                             send_interval=send_interval)

        #######################################################################
        # Make requests and validate
        #######################################################################
        if request_style == 0:
            for i in range(requests * request_multiplier):
                # 0
                rc = a_se_lock.send_request(request_validator.request0)
                if mode == SELock.MODE_ASYNC:
                    assert rc is SELock.RC_OK
                else:
                    assert rc == i
                time.sleep(send_interval)

            if mode == SELock.MODE_ASYNC:
                a_se_lock.start_shutdown(shutdown_type=
                                          SELock.TYPE_SHUTDOWN_SOFT)

            request_validator.validate_series()  # validate for the series

        elif request_style == 1:
            for i in range(requests * request_multiplier):
                # 1
                rc = a_se_lock.send_request(request_validator.request1, i)
                exp_rc = i if mode != SELock.MODE_ASYNC else SELock.RC_OK
                assert rc == exp_rc
                time.sleep(send_interval)

            if mode == SELock.MODE_ASYNC:
                a_se_lock.start_shutdown(shutdown_type=
                                          SELock.TYPE_SHUTDOWN_SOFT)
            request_validator.validate_series()  # validate for the series

        elif request_style == 2:
            for i in range(requests * request_multiplier):
                # 2
                rc = a_se_lock.send_request(request_validator.request2,
                                             i,
                                             requests)
                exp_rc = i if mode != SELock.MODE_ASYNC else SELock.RC_OK
                assert rc == exp_rc
                time.sleep(send_interval)

            if mode == SELock.MODE_ASYNC:
                a_se_lock.start_shutdown(shutdown_type=
                                          SELock.TYPE_SHUTDOWN_SOFT)
            request_validator.validate_series()  # validate for the series

        elif request_style == 3:
            for i in range(requests * request_multiplier):
                # 3
                rc = a_se_lock.send_request(request_validator.request3, idx=i)
                exp_rc = i if mode != SELock.MODE_ASYNC else SELock.RC_OK
                assert rc == exp_rc
                time.sleep(send_interval)

            if mode == SELock.MODE_ASYNC:
                a_se_lock.start_shutdown(shutdown_type=
                                          SELock.TYPE_SHUTDOWN_SOFT)
            request_validator.validate_series()  # validate for the series

        elif request_style == 4:
            for i in range(requests * request_multiplier):
                # 4
                rc = a_se_lock.send_request(request_validator.request4,
                                             idx=i,
                                             seconds=seconds)
                exp_rc = i if mode != SELock.MODE_ASYNC else SELock.RC_OK
                assert rc == exp_rc
                time.sleep(send_interval)

            if mode == SELock.MODE_ASYNC:
                a_se_lock.start_shutdown(shutdown_type=
                                          SELock.TYPE_SHUTDOWN_SOFT)
            request_validator.validate_series()  # validate for the series

        elif request_style == 5:
            for i in range(requests * request_multiplier):
                # 5
                rc = a_se_lock.send_request(request_validator.request5,
                                             i,
                                             interval=send_interval)
                exp_rc = i if mode != SELock.MODE_ASYNC else SELock.RC_OK
                assert rc == exp_rc
                time.sleep(send_interval)

            if mode == SELock.MODE_ASYNC:
                a_se_lock.start_shutdown(shutdown_type=
                                          SELock.TYPE_SHUTDOWN_SOFT)
            request_validator.validate_series()  # validate for the series

        elif request_style == 6:
            for i in range(requests * request_multiplier):
                # 6
                rc = a_se_lock.send_request(request_validator.request6,
                                             i,
                                             requests,
                                             seconds=seconds,
                                             interval=send_interval)
                exp_rc = i if mode != SELock.MODE_ASYNC else SELock.RC_OK
                assert rc == exp_rc
                time.sleep(send_interval)

            if mode == SELock.MODE_ASYNC:
                a_se_lock.start_shutdown(shutdown_type=
                                          SELock.TYPE_SHUTDOWN_SOFT)
            request_validator.validate_series()  # validate for the series

        else:
            raise BadRequestStyleArg('The request style arg must be 0 to 6')

    ###########################################################################
    # test_pie_se_lock_async
    ###########################################################################
    def test_pie_se_lock_async(self,
            requests_arg: int,
            seconds_arg: Union[int, float],
            send_interval_mult_arg: float
    ) -> None:
        """Method to start se_lock mode1 tests

        Args:
            requests_arg: number of requests per interval from fixture
            seconds_arg: interval for number of requests from fixture
            send_interval_mult_arg: interval between each send of a request
        """
        #######################################################################
        # Instantiate Request Validator
        #######################################################################
        request_multiplier = 32
        send_interval = (seconds_arg / requests_arg) * send_interval_mult_arg
        request_validator = RequestValidator(requests=requests_arg,
                                             seconds=seconds_arg,
                                             mode=SELock.MODE_ASYNC,
                                             early_count=0,
                                             lb_threshold=0,
                                             request_mult=request_multiplier,
                                             send_interval=send_interval)

        #######################################################################
        # Decorate functions with se_lock
        #######################################################################
        @se_lock(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=SELock.MODE_ASYNC)
        def f0():
            request_validator.callback0()

        @se_lock(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=SELock.MODE_ASYNC)
        def f1(idx):
            request_validator.callback1(idx)

        @se_lock(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=SELock.MODE_ASYNC)
        def f2(idx, requests):
            request_validator.callback2(idx, requests)

        @se_lock(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=SELock.MODE_ASYNC)
        def f3(*, idx):
            request_validator.callback3(idx=idx)

        @se_lock(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=SELock.MODE_ASYNC)
        def f4(*, idx, seconds):
            request_validator.callback4(idx=idx, seconds=seconds)

        @se_lock(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=SELock.MODE_ASYNC)
        def f5(idx, *, interval):
            request_validator.callback5(idx,
                                        interval=interval)

        @se_lock(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=SELock.MODE_ASYNC)
        def f6(idx, requests, *, seconds, interval):
            request_validator.callback6(idx,
                                        requests,
                                        seconds=seconds,
                                        interval=interval)

        #######################################################################
        # Invoke the functions
        #######################################################################
        for i in range(requests_arg * request_multiplier):
            rc = f0()
            assert rc is None
            time.sleep(send_interval)
        request_validator.validate_series()  # validate for the series
        f0.se_lock.start_shutdown()

        for i in range(requests_arg * request_multiplier):
            rc = f1(i)
            assert rc is None
            time.sleep(send_interval)
        request_validator.validate_series()  # validate for the series
        f1.se_lock.start_shutdown()

        for i in range(requests_arg * request_multiplier):
            rc = f2(i, requests_arg)
            assert rc is None
            time.sleep(send_interval)
        request_validator.validate_series()  # validate for the series
        f2.se_lock.start_shutdown()

        for i in range(requests_arg * request_multiplier):
            rc = f3(idx=i)
            assert rc is None
            time.sleep(send_interval)
        request_validator.validate_series()  # validate for the series
        f3.se_lock.start_shutdown()

        for i in range(requests_arg * request_multiplier):
            rc = f4(idx=i, seconds=seconds_arg)
            assert rc is None
            time.sleep(send_interval)
        request_validator.validate_series()  # validate for the series
        f4.se_lock.start_shutdown()

        for i in range(requests_arg * request_multiplier):
            rc = f5(idx=i, interval=send_interval_mult_arg)
            assert rc is None
            time.sleep(send_interval)
        request_validator.validate_series()  # validate for the series
        f5.se_lock.start_shutdown()

        for i in range(requests_arg * request_multiplier):
            rc = f6(i, requests_arg,
                    seconds=seconds_arg, interval=send_interval_mult_arg)
            assert rc is None
            time.sleep(send_interval)
        request_validator.validate_series()  # validate for the series
        f6.se_lock.start_shutdown()

    ###########################################################################
    # test_se_lock_sync
    ###########################################################################
    def test_pie_se_lock_sync(self,
            requests_arg: int,
            seconds_arg: Union[int, float],
            send_interval_mult_arg: float
    ) -> None:
        """Method to start se_lock sync tests

        Args:
            requests_arg: number of requests per interval from fixture
            seconds_arg: interval for number of requests from fixture
            send_interval_mult_arg: interval between each send of a request
        """
        #######################################################################
        # Instantiate Request Validator
        #######################################################################
        request_multiplier = 32
        send_interval = (seconds_arg / requests_arg) * send_interval_mult_arg
        request_validator = RequestValidator(requests=requests_arg,
                                             seconds=seconds_arg,
                                             mode=SELock.MODE_SYNC,
                                             early_count=0,
                                             lb_threshold=0,
                                             request_mult=request_multiplier,
                                             send_interval=send_interval)

        #######################################################################
        # Decorate functions with se_lock
        #######################################################################
        @se_lock(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=SELock.MODE_SYNC)
        def f0():
            request_validator.callback0()
            return 42

        @se_lock(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=SELock.MODE_SYNC)
        def f1(idx):
            request_validator.callback1(idx)
            return idx + 42 + 1

        @se_lock(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=SELock.MODE_SYNC)
        def f2(idx, requests):
            request_validator.callback2(idx, requests)
            return idx + 42 + 2

        @se_lock(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=SELock.MODE_SYNC)
        def f3(*, idx):
            request_validator.callback3(idx=idx)
            return idx + 42 + 3

        @se_lock(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=SELock.MODE_SYNC)
        def f4(*, idx, seconds):
            request_validator.callback4(idx=idx, seconds=seconds)
            return idx + 42 + 4

        @se_lock(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=SELock.MODE_SYNC)
        def f5(idx, *, interval):
            request_validator.callback5(idx,
                                        interval=interval)
            return idx + 42 + 5

        @se_lock(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=SELock.MODE_SYNC)
        def f6(idx, requests, *, seconds, interval):
            request_validator.callback6(idx,
                                        requests,
                                        seconds=seconds,
                                        interval=interval)
            return idx + 42 + 6

        #######################################################################
        # Invoke the functions
        #######################################################################
        for i in range(requests_arg * request_multiplier):
            rc = f0()
            assert rc == 0
            time.sleep(send_interval)
        request_validator.validate_series()  # validate for the series

        for i in range(requests_arg * request_multiplier):
            rc = f1(i)
            assert rc == i + 42 + 1
            time.sleep(send_interval)
        request_validator.validate_series()  # validate for the series

        for i in range(requests_arg * request_multiplier):
            rc = f2(i, requests_arg)
            assert rc == i + 42 + 2
            time.sleep(send_interval)
        request_validator.validate_series()  # validate for the series

        for i in range(requests_arg * request_multiplier):
            rc = f3(idx=i)
            assert rc == i + 42 + 3
            time.sleep(send_interval)
        request_validator.validate_series()  # validate for the series

        for i in range(requests_arg * request_multiplier):
            rc = f4(idx=i, seconds=seconds_arg)
            assert rc == i + 42 + 4
            time.sleep(send_interval)
        request_validator.validate_series()  # validate for the series

        for i in range(requests_arg * request_multiplier):
            rc = f5(idx=i, interval=send_interval_mult_arg)
            assert rc == i + 42 + 5
            time.sleep(send_interval)
        request_validator.validate_series()  # validate for the series

        for i in range(requests_arg * request_multiplier):
            rc = f6(i, requests_arg,
                    seconds=seconds_arg, interval=send_interval_mult_arg)
            assert rc == i + 42 + 6
            time.sleep(send_interval)
        request_validator.validate_series()  # validate for the series

    ###########################################################################
    # test_se_lock_sync_ec
    ###########################################################################
    def test_pie_se_lock_sync_ec(self,
            requests_arg: int,
            seconds_arg: Union[int, float],
            early_count_arg: int,
            send_interval_mult_arg: float
    ) -> None:
        """Method to start se_lock sync_ec tests

        Args:
            requests_arg: number of requests per interval from fixture
            seconds_arg: interval for number of requests from fixture
            early_count_arg: count used for sync with early count algo
            send_interval_mult_arg: interval between each send of a request
        """
        #######################################################################
        # Instantiate Request Validator
        #######################################################################
        request_multiplier = 32
        send_interval = (seconds_arg / requests_arg) * send_interval_mult_arg
        request_validator = RequestValidator(requests=requests_arg,
                                             seconds=seconds_arg,
                                             mode=SELock.MODE_SYNC_EC,
                                             early_count=early_count_arg,
                                             lb_threshold=0,
                                             request_mult=request_multiplier,
                                             send_interval=send_interval)

        #######################################################################
        # Decorate functions with se_lock
        #######################################################################
        @se_lock(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=SELock.MODE_SYNC_EC,
                  early_count=early_count_arg)
        def f0():
            request_validator.callback0()
            return 42

        @se_lock(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=SELock.MODE_SYNC_EC,
                  early_count=early_count_arg)
        def f1(idx):
            request_validator.callback1(idx)
            return idx + 42 + 1

        @se_lock(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=SELock.MODE_SYNC_EC,
                  early_count=early_count_arg)
        def f2(idx, requests):
            request_validator.callback2(idx, requests)
            return idx + 42 + 2

        @se_lock(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=SELock.MODE_SYNC_EC,
                  early_count=early_count_arg)
        def f3(*, idx):
            request_validator.callback3(idx=idx)
            return idx + 42 + 3

        @se_lock(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=SELock.MODE_SYNC_EC,
                  early_count=early_count_arg)
        def f4(*, idx, seconds):
            request_validator.callback4(idx=idx, seconds=seconds)
            return idx + 42 + 4

        @se_lock(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=SELock.MODE_SYNC_EC,
                  early_count=early_count_arg)
        def f5(idx, *, interval):
            request_validator.callback5(idx,
                                        interval=interval)
            return idx + 42 + 5

        @se_lock(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=SELock.MODE_SYNC_EC,
                  early_count=early_count_arg)
        def f6(idx, requests, *, seconds, interval):
            request_validator.callback6(idx,
                                        requests,
                                        seconds=seconds,
                                        interval=interval)
            return idx + 42 + 6

        #######################################################################
        # Invoke the functions
        #######################################################################
        for i in range(requests_arg * request_multiplier):
            rc = f0()
            assert rc == 0
            time.sleep(send_interval)
        request_validator.validate_series()  # validate for the series

        for i in range(requests_arg * request_multiplier):
            rc = f1(i)
            assert rc == i + 42 + 1
            time.sleep(send_interval)
        request_validator.validate_series()  # validate for the series

        for i in range(requests_arg * request_multiplier):
            rc = f2(i, requests_arg)
            assert rc == i + 42 + 2
            time.sleep(send_interval)
        request_validator.validate_series()  # validate for the series

        for i in range(requests_arg * request_multiplier):
            rc = f3(idx=i)
            assert rc == i + 42 + 3
            time.sleep(send_interval)
        request_validator.validate_series()  # validate for the series

        for i in range(requests_arg * request_multiplier):
            rc = f4(idx=i, seconds=seconds_arg)
            assert rc == i + 42 + 4
            time.sleep(send_interval)
        request_validator.validate_series()  # validate for the series

        for i in range(requests_arg * request_multiplier):
            rc = f5(idx=i, interval=send_interval_mult_arg)
            assert rc == i + 42 + 5
            time.sleep(send_interval)
        request_validator.validate_series()  # validate for the series

        for i in range(requests_arg * request_multiplier):
            rc = f6(i, requests_arg,
                    seconds=seconds_arg, interval=send_interval_mult_arg)
            assert rc == i + 42 + 6
            time.sleep(send_interval)
        request_validator.validate_series()  # validate for the series

    ###########################################################################
    # test_se_lock_sync_lb
    ###########################################################################
    def test_pie_se_lock_sync_lb(self,
            requests_arg: int,
            seconds_arg: Union[int, float],
            lb_threshold_arg: Union[int, float],
            send_interval_mult_arg: float
    ) -> None:
        """Method to start se_lock sync_lb tests

        Args:
            requests_arg: number of requests per interval from fixture
            seconds_arg: interval for number of requests from fixture
            lb_threshold_arg: threshold used with sync leaky bucket algo
            send_interval_mult_arg: interval between each send of a request
        """
        #######################################################################
        # Instantiate Request Validator
        #######################################################################
        request_multiplier = 32
        send_interval = (seconds_arg / requests_arg) * send_interval_mult_arg
        request_validator = RequestValidator(requests=requests_arg,
                                             seconds=seconds_arg,
                                             mode=SELock.MODE_SYNC_LB,
                                             early_count=0,
                                             lb_threshold=lb_threshold_arg,
                                             request_mult=request_multiplier,
                                             send_interval=send_interval)

        #######################################################################
        # Decorate functions with se_lock
        #######################################################################
        @se_lock(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=SELock.MODE_SYNC_LB,
                  lb_threshold=lb_threshold_arg)
        def f0():
            request_validator.callback0()
            return 42

        @se_lock(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=SELock.MODE_SYNC_LB,
                  lb_threshold=lb_threshold_arg)
        def f1(idx):
            request_validator.callback1(idx)
            return idx + 42 + 1

        @se_lock(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=SELock.MODE_SYNC_LB,
                  lb_threshold=lb_threshold_arg)
        def f2(idx, requests):
            request_validator.callback2(idx, requests)
            return idx + 42 + 2

        @se_lock(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=SELock.MODE_SYNC_LB,
                  lb_threshold=lb_threshold_arg)
        def f3(*, idx):
            request_validator.callback3(idx=idx)
            return idx + 42 + 3

        @se_lock(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=SELock.MODE_SYNC_LB,
                  lb_threshold=lb_threshold_arg)
        def f4(*, idx, seconds):
            request_validator.callback4(idx=idx, seconds=seconds)
            return idx + 42 + 4

        @se_lock(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=SELock.MODE_SYNC_LB,
                  lb_threshold=lb_threshold_arg)
        def f5(idx, *, interval):
            request_validator.callback5(idx,
                                        interval=interval)
            return idx + 42 + 5

        @se_lock(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=SELock.MODE_SYNC_LB,
                  lb_threshold=lb_threshold_arg)
        def f6(idx, requests, *, seconds, interval):
            request_validator.callback6(idx,
                                        requests,
                                        seconds=seconds,
                                        interval=interval)
            return idx + 42 + 6

        #######################################################################
        # Invoke the functions
        #######################################################################
        for i in range(requests_arg * request_multiplier):
            rc = f0()
            assert rc == 0
            time.sleep(send_interval)
        request_validator.validate_series()  # validate for the series

        for i in range(requests_arg * request_multiplier):
            rc = f1(i)
            assert rc == i + 42 + 1
            time.sleep(send_interval)
        request_validator.validate_series()  # validate for the series

        for i in range(requests_arg * request_multiplier):
            rc = f2(i, requests_arg)
            assert rc == i + 42 + 2
            time.sleep(send_interval)
        request_validator.validate_series()  # validate for the series

        for i in range(requests_arg * request_multiplier):
            rc = f3(idx=i)
            assert rc == i + 42 + 3
            time.sleep(send_interval)
        request_validator.validate_series()  # validate for the series

        for i in range(requests_arg * request_multiplier):
            rc = f4(idx=i, seconds=seconds_arg)
            assert rc == i + 42 + 4
            time.sleep(send_interval)
        request_validator.validate_series()  # validate for the series

        for i in range(requests_arg * request_multiplier):
            rc = f5(idx=i, interval=send_interval_mult_arg)
            assert rc == i + 42 + 5
            time.sleep(send_interval)
        request_validator.validate_series()  # validate for the series

        for i in range(requests_arg * request_multiplier):
            rc = f6(i, requests_arg,
                    seconds=seconds_arg, interval=send_interval_mult_arg)
            assert rc == i + 42 + 6
            time.sleep(send_interval)
        request_validator.validate_series()  # validate for the series

    ###########################################################################
    # test_se_lock_shutdown_error
    ###########################################################################
    def test_se_lock_shutdown_error(self) -> None:
        """Method to test attempted shutdown in sync mode."""
        #######################################################################
        # call start_shutdown for sync mode
        #######################################################################
        a_se_lock1 = SELock(requests=1,
                               seconds=4,
                               mode=SELock.MODE_SYNC)

        a_var = [0]

        def f1(a) -> None:
            a[0] += 1

        for i in range(4):
            a_se_lock1.send_request(f1, a_var)

        with pytest.raises(AttemptedShutdownForSyncSELock):
            a_se_lock1.start_shutdown()

        assert a_var[0] == 4

        # the following requests should not get ignored
        for i in range(6):
            a_se_lock1.send_request(f1, a_var)

        # the count should not have changed
        assert a_var[0] == 10

    ###########################################################################
    # test_se_lock_shutdown
    ###########################################################################
    def test_se_lock_shutdown(self) -> None:
        """Method to test shutdown scenarios."""
        #######################################################################
        # call start_shutdown
        #######################################################################
        b_se_lock1 = SELock(requests=1,
                               seconds=4,
                               mode=SELock.MODE_ASYNC)

        b_var = [0]

        def f2(b) -> None:
            b[0] += 1

        for i in range(32):
            b_se_lock1.send_request(f2, b_var)

        time.sleep(14)  # allow 4 requests to be scheduled
        b_se_lock1.start_shutdown()

        assert b_var[0] == 4

        # the following requests should get ignored
        for i in range(32):
            b_se_lock1.send_request(f2, b_var)

        # the count should not have changed
        assert b_var[0] == 4

    ###########################################################################
    # test_pie_se_lock_shutdown
    ###########################################################################
    def test_pie_se_lock_shutdown(self) -> None:
        #######################################################################
        # test 3 - shutdown events with pie se_lock
        #######################################################################
        start_shutdown = threading.Event()
        shutdown_complete = threading.Event()
        c_var = [0]

        @se_lock(requests=1,
                  seconds=4,
                  mode=SELock.MODE_ASYNC)
        def f3(c) -> None:
            c[0] += 1

        for i in range(32):
            f3(c_var)

        time.sleep(14)  # allow 4 requests to be scheduled

        f3.se_lock.start_shutdown()
        # start_shutdown.set()
        # shutdown_complete.wait()

        assert c_var[0] == 4

        # the following requests should get ignored
        for i in range(32):
            f3(c_var)

        # the count should not have changed
        assert c_var[0] == 4


###############################################################################
# RequestValidator class
###############################################################################
class RequestValidator:
    def __init__(self,
            requests,
            seconds,
            mode,
            early_count,
            lb_threshold,
            request_mult,
            send_interval) -> None:
        self.requests = requests
        self.seconds = seconds
        self.mode = mode
        self.early_count = early_count
        self.lb_threshold = lb_threshold
        self.request_mult = request_mult
        self.send_interval = send_interval
        self.idx = -1
        self.req_times = []
        self.normalized_times = []
        self.normalized_intervals = []
        self.mean_interval = 0
        # calculate parms

        self.total_requests = requests * request_mult
        print('total requests:', self.total_requests)
        self.target_interval = seconds / requests

        self.max_interval = max(self.target_interval,
                                self.send_interval)

        print('self.max_interval:', self.max_interval)
        self.min_interval = min(self.target_interval,
                                self.send_interval)

        self.exp_total_time = self.max_interval * self.total_requests
        print('self.exp_total_time:', self.exp_total_time)

        self.target_interval_1pct = self.target_interval * 0.01
        self.target_interval_5pct = self.target_interval * 0.05
        self.target_interval_10pct = self.target_interval * 0.10
        self.target_interval_15pct = self.target_interval * 0.15

        self.max_interval_1pct = self.max_interval * 0.01
        self.max_interval_5pct = self.max_interval * 0.05
        self.max_interval_10pct = self.max_interval * 0.10
        self.max_interval_15pct = self.max_interval * 0.15

        self.min_interval_1pct = self.min_interval * 0.01
        self.min_interval_5pct = self.min_interval * 0.05
        self.min_interval_10pct = self.min_interval * 0.10
        self.min_interval_15pct = self.min_interval * 0.15

        self.reset()

    def reset(self):
        self.idx = -1
        self.req_times = []
        self.normalized_times = []
        self.normalized_intervals = []
        self.mean_interval = 0

    def validate_series(self):
        """Validate the requests."""

        self.sleep_time = 0
        # if self.mode == SELock.MODE_ASYNC:
        #     assert len(self.req_times) == self.total_requests
        # while True:
        #     print('len(self.req_times):', len(self.req_times))
        #     if len(self.req_times) == self.total_requests:
        #         break
        #     time.sleep(1)
        #     self.sleep_time += 1
        #     # diag_msg('len(self.req_times)', len(self.req_times),
        #     #          'self.total_requests', self.total_requests,
        #     #          'sleep_time:', sleep_time)
        #     assert self.sleep_time <= math.ceil(self.exp_total_time) + 5

        assert len(self.req_times) == self.total_requests
        base_time = self.req_times[0][1]
        prev_time = base_time
        for idx, req_item in enumerate(self.req_times):
            assert idx == req_item[0]
            cur_time = req_item[1]
            self.normalized_times.append(cur_time - base_time)
            self.normalized_intervals.append(cur_time - prev_time)
            prev_time = cur_time

        self.mean_interval = self.normalized_times[-1] / (
                    self.total_requests - 1)

        if ((self.mode == SELock.MODE_ASYNC) or
                (self.mode == SELock.MODE_SYNC) or
                (self.target_interval <= self.send_interval)):
            self.validate_async_sync()
        elif self.mode == SELock.MODE_SYNC_EC:
            self.validate_sync_ec()
        elif self.mode == SELock.MODE_SYNC_LB:
            self.validate_sync_lb()
        else:
            raise InvalidModeNum('Mode must be 1, 2, 3, or 4')

        self.reset()

    def validate_async_sync(self):
        num_early = 0
        num_early_1pct = 0
        num_early_5pct = 0
        num_early_10pct = 0
        num_early_15pct = 0

        num_late = 0
        num_late_1pct = 0
        num_late_5pct = 0
        num_late_10pct = 0
        num_late_15pct = 0

        for interval in self.normalized_intervals[1:]:
            if interval < self.target_interval:
                num_early += 1
            if interval < self.target_interval - self.target_interval_1pct:
                num_early_1pct += 1
            if interval < self.target_interval - self.target_interval_5pct:
                num_early_5pct += 1
            if interval < self.target_interval - self.target_interval_10pct:
                num_early_10pct += 1
            if interval < self.target_interval - self.target_interval_15pct:
                num_early_15pct += 1

            if self.max_interval < interval:
                num_late += 1
            if self.max_interval + self.max_interval_1pct < interval:
                num_late_1pct += 1
            if self.max_interval + self.max_interval_5pct < interval:
                num_late_5pct += 1
            if self.max_interval + self.max_interval_10pct < interval:
                num_late_10pct += 1
            if self.max_interval + self.max_interval_15pct < interval:
                num_late_15pct += 1

        print('num_requests_sent1:', self.total_requests)
        print('num_early1:', num_early)
        print('num_early_1pct1:', num_early_1pct)
        print('num_early_5pct1:', num_early_5pct)
        print('num_early_10pct1:', num_early_10pct)
        print('num_early_15pct1:', num_early_15pct)

        print('num_late1:', num_late)
        print('num_late_1pct1:', num_late_1pct)
        print('num_late_5pct1:', num_late_5pct)
        print('num_late_10pct1:', num_late_10pct)
        print('num_late_15pct1:', num_late_15pct)

        # assert num_early_10pct == 0
        # assert num_early_5pct == 0
        # assert num_early_1pct == 0

        if self.target_interval < self.send_interval:
            assert num_early == 0

        # assert num_late_15pct == 0
        # assert num_late_5pct == 0
        # assert num_late_1pct == 0
        # assert num_late == 0

        self.exp_total_time = self.max_interval * self.total_requests
        print('self.exp_total_time:', self.exp_total_time)
        extra_exp_total_time = self.mean_interval * self.total_requests
        print('extra_exp_total_time:', extra_exp_total_time)
        mean_late_pct = ((self.mean_interval - self.max_interval) /
                         self.max_interval) * 100
        print(f'mean_late_pct: {mean_late_pct:.2f}%')

        extra_time_pct = ((extra_exp_total_time - self.exp_total_time) /
                          self.exp_total_time) * 100

        print(f'extra_time_pct: {extra_time_pct:.2f}%')

        num_to_add = extra_exp_total_time - self.exp_total_time
        print(f'num_to_add: {num_to_add:.2f}')

        print(f'sleep_time: {self.sleep_time}')

        print('self.max_interval:', self.max_interval)
        print('self.mean_interval:', self.mean_interval)
        assert self.max_interval <= self.mean_interval

    def validate_sync_ec(self):
        num_short_early = 0
        num_short_early_1pct = 0
        num_short_early_5pct = 0
        num_short_early_10pct = 0

        num_short_late = 0
        num_short_late_1pct = 0
        num_short_late_5pct = 0
        num_short_late_10pct = 0

        num_long_early = 0
        num_long_early_1pct = 0
        num_long_early_5pct = 0
        num_long_early_10pct = 0

        num_long_late = 0
        num_long_late_1pct = 0
        num_long_late_5pct = 0
        num_long_late_10pct = 0

        long_interval = (((self.early_count + 1) * self.target_interval)
                         - (self.early_count * self.min_interval))

        for idx, interval in enumerate(self.normalized_intervals[1:], 1):
            if idx % (self.early_count + 1):  # if long interval expected
                if interval < long_interval:
                    num_long_early += 1
                if interval < long_interval - self.target_interval_1pct:
                    num_long_early_1pct += 1
                if interval < long_interval - self.target_interval_5pct:
                    num_long_early_5pct += 1
                if interval < (long_interval - self.target_interval_10pct):
                    num_long_early_10pct += 1

                if self.max_interval < interval:
                    num_long_late += 1
                if self.max_interval + self.max_interval_1pct < interval:
                    num_long_late_1pct += 1
                if self.max_interval + self.max_interval_5pct < interval:
                    num_long_late_5pct += 1
                if self.max_interval + self.max_interval_10pct < interval:
                    num_long_late_10pct += 1
            else:
                if interval < self.min_interval:
                    num_short_early += 1
                if interval < self.min_interval - self.min_interval_1pct:
                    num_short_early_1pct += 1
                if interval < self.min_interval - self.min_interval_5pct:
                    num_short_early_5pct += 1
                if interval < (self.min_interval - self.min_interval_10pct):
                    num_short_early_10pct += 1

                if self.min_interval < interval:
                    num_short_late += 1
                if self.min_interval + self.min_interval_1pct < interval:
                    num_short_late_1pct += 1
                if self.min_interval + self.min_interval_5pct < interval:
                    num_short_late_5pct += 1
                if self.min_interval + self.min_interval_10pct < interval:
                    num_short_late_10pct += 1

        print('num_requests_sent2:', self.total_requests)
        print('num_early2:', num_long_early)
        print('num_early_1pct2:', num_long_early_1pct)
        print('num_early_5pct2:', num_long_early_5pct)
        print('num_early_10pct2:', num_long_early_10pct)

        print('num_late2:', num_long_late)
        print('num_late_1pct2:', num_long_late_1pct)
        print('num_late_5pct2:', num_long_late_5pct)
        print('num_late_10pct2:', num_long_late_10pct)

        print('num_early2:', num_short_early)
        print('num_early_1pct2:', num_short_early_1pct)
        print('num_early_5pct2:', num_short_early_5pct)
        print('num_early_10pct2:', num_short_early_10pct)

        print('num_late2:', num_short_late)
        print('num_late_1pct2:', num_short_late_1pct)
        print('num_late_5pct2:', num_short_late_5pct)
        print('num_late_10pct2:', num_short_late_10pct)

        assert num_long_early_10pct == 0
        # assert num_long_early_5pct == 0
        # assert num_long_early_5pct == 0
        # assert num_long_early == 0

        assert num_long_late_10pct == 0
        # assert num_long_late_5pct == 0
        # assert num_long_late_1pct == 0
        # assert num_long_late == 0

        assert num_short_early_10pct == 0
        # assert num_short_early_5pct == 0
        # assert num_short_early_5pct == 0
        # assert num_short_early == 0

        assert num_short_late_10pct == 0
        # assert num_short_late_5pct == 0
        # assert num_short_late_1pct == 0
        # assert num_short_late == 0

        assert self.target_interval <= self.mean_interval

    def validate_sync_lb(self):
        amt_added_per_send = self.target_interval - self.send_interval
        num_sends_before_trigger = (math.floor(self.lb_threshold /
                                               amt_added_per_send))
        amt_remaining_in_bucket = (self.lb_threshold
                                   - (num_sends_before_trigger
                                      * self.send_interval))
        amt_over = self.send_interval - amt_remaining_in_bucket

        trigger_interval = self.send_interval + amt_over
        trigger_interval_1pct = trigger_interval * 0.01
        trigger_interval_5pct = trigger_interval * 0.05
        trigger_interval_10pct = trigger_interval * 0.10

        num_short_early = 0
        num_short_early_1pct = 0
        num_short_early_5pct = 0
        num_short_early_10pct = 0

        num_short_late = 0
        num_short_late_1pct = 0
        num_short_late_5pct = 0
        num_short_late_10pct = 0

        num_trigger_early = 0
        num_trigger_early_1pct = 0
        num_trigger_early_5pct = 0
        num_trigger_early_10pct = 0

        num_trigger_late = 0
        num_trigger_late_1pct = 0
        num_trigger_late_5pct = 0
        num_trigger_late_10pct = 0

        num_early = 0
        num_early_1pct = 0
        num_early_5pct = 0
        num_early_10pct = 0

        num_late = 0
        num_late_1pct = 0
        num_late_5pct = 0
        num_late_10pct = 0

        # the following assert ensures our request_multiplier is sufficient
        # to get the bucket filled and then some
        assert (num_sends_before_trigger + 8) < len(self.normalized_intervals)

        for idx, interval in enumerate(self.normalized_intervals[1:], 1):
            if idx <= num_sends_before_trigger:
                if interval < self.min_interval:
                    num_short_early += 1
                if interval < self.min_interval - self.min_interval_1pct:
                    num_short_early_1pct += 1
                if interval < self.min_interval - self.min_interval_5pct:
                    num_short_early_5pct += 1
                if interval < (self.min_interval - self.min_interval_10pct):
                    num_short_early_10pct += 1

                if self.min_interval < interval:
                    num_short_late += 1
                if self.min_interval + self.min_interval_1pct < interval:
                    num_short_late_1pct += 1
                if self.min_interval + self.min_interval_5pct < interval:
                    num_short_late_5pct += 1
                if self.min_interval + self.min_interval_10pct < interval:
                    num_short_late_10pct += 1
            elif idx == num_sends_before_trigger + 1:
                if interval < trigger_interval:
                    num_trigger_early += 1
                if interval < trigger_interval - trigger_interval_1pct:
                    num_trigger_early_1pct += 1
                if interval < trigger_interval - trigger_interval_5pct:
                    num_trigger_early_5pct += 1
                if interval < trigger_interval - trigger_interval_10pct:
                    num_trigger_early_10pct += 1

                if trigger_interval < interval:
                    num_trigger_late += 1
                if trigger_interval + trigger_interval_1pct < interval:
                    num_trigger_late_1pct += 1
                if trigger_interval + trigger_interval_5pct < interval:
                    num_trigger_late_5pct += 1
                if trigger_interval + trigger_interval_10pct < interval:
                    num_trigger_late_10pct += 1
            else:
                if interval < self.target_interval:
                    num_early += 1
                if interval < self.target_interval - self.target_interval_1pct:
                    num_early_1pct += 1
                if interval < self.target_interval - self.target_interval_5pct:
                    num_early_5pct += 1
                if interval < self.target_interval - \
                        self.target_interval_10pct:
                    num_early_10pct += 1

                if self.max_interval < interval:
                    num_late += 1
                if self.max_interval + self.max_interval_1pct < interval:
                    num_late_1pct += 1
                if self.max_interval + self.max_interval_5pct < interval:
                    num_late_5pct += 1
                if self.max_interval + self.max_interval_10pct < interval:
                    num_late_10pct += 1

        print('num_requests_sent3:', self.total_requests)

        print('num_short_early3:', num_short_early)
        print('num_short_early_1pct3:', num_short_early_1pct)
        print('num_short_early_5pct3:', num_short_early_5pct)
        print('num_short_early_10pct3:', num_short_early_10pct)

        print('num_short_late3:', num_short_late)
        print('num_short_late_1pct3:', num_short_late_1pct)
        print('num_short_late_5pct3:', num_short_late_5pct)
        print('num_short_late_10pct3:', num_short_late_10pct)

        print('num_trigger_early3:', num_trigger_early)
        print('num_trigger_early_1pct3:', num_trigger_early_1pct)
        print('num_trigger_early_5pct3:', num_trigger_early_5pct)
        print('num_trigger_early_10pct3:', num_trigger_early_10pct)

        print('num_trigger_late3:', num_trigger_late)
        print('num_trigger_late_1pct3:', num_trigger_late_1pct)
        print('num_trigger_late_5pct3:', num_trigger_late_5pct)
        print('num_trigger_late_10pct3:', num_trigger_late_10pct)

        print('num_early3:', num_early)
        print('num_early_1pct3:', num_early_1pct)
        print('num_early_5pct3:', num_early_5pct)
        print('num_early_10pct3:', num_early_10pct)

        print('num_late3:', num_late)
        print('num_late_1pct3:', num_late_1pct)
        print('num_late_5pct3:', num_late_5pct)
        print('num_late_10pct3:', num_late_10pct)

        assert num_short_early_10pct == 0
        assert num_short_late_10pct == 0

        assert num_trigger_early_10pct == 0
        assert num_trigger_late_10pct == 0

        assert num_early_10pct == 0
        assert num_late_10pct == 0

        exp_mean_interval = ((self.send_interval * num_sends_before_trigger)
                             + trigger_interval
                             + (self.target_interval
                                * (self.total_requests
                                   - (num_sends_before_trigger + 1)))
                             ) / (self.total_requests - 1)

        assert exp_mean_interval <= self.mean_interval

    def request0(self) -> int:
        """Request0 target.

        Returns:
            the index reflected back
        """
        self.idx += 1
        self.req_times.append((self.idx, time.time()))
        return self.idx

    def request1(self, idx: int) -> int:
        """Request1 target.

        Args:
            idx: the index of the call

        Returns:
            the index reflected back
        """
        self.req_times.append((idx, time.time()))
        assert idx == self.idx + 1
        self.idx = idx
        return idx

    def request2(self, idx: int, requests: int) -> int:
        """Request2 target.

        Args:
            idx: the index of the call
            requests: number of requests for the se_lock

        Returns:
            the index reflected back
        """
        self.req_times.append((idx, time.time()))
        assert idx == self.idx + 1
        assert requests == self.requests
        self.idx = idx
        return idx

    def request3(self, *, idx: int) -> int:
        """Request3 target.

        Args:
            idx: the index of the call

        Returns:
            the index reflected back
        """
        self.req_times.append((idx, time.time()))
        assert idx == self.idx + 1
        self.idx = idx
        return idx

    def request4(self, *, idx: int, seconds: int) -> int:
        """Request4 target.

        Args:
            idx: the index of the call
            seconds: number of seconds for the se_lock

        Returns:
            the index reflected back
        """
        self.req_times.append((idx, time.time()))
        assert idx == self.idx + 1
        assert seconds == self.seconds
        self.idx = idx
        return idx

    def request5(self, idx: int, *, interval: float) -> int:
        """Request5 target.

        Args:
            idx: the index of the call
            interval: the interval used between requests

        Returns:
            the index reflected back
        """
        self.req_times.append((idx, time.time()))
        assert idx == self.idx + 1
        assert interval == self.send_interval
        self.idx = idx
        return idx

    def request6(self,
            idx: int,
            requests: int,
            *,
            seconds: int,
            interval: float) -> int:
        """Request5 target.

         Args:
            idx: the index of the call
            requests: number of requests for the se_lock
            seconds: number of seconds for the se_lock
            interval: the interval used between requests

        Returns:
            the index reflected back
        """
        self.req_times.append((idx, time.time()))
        assert idx == self.idx + 1
        assert requests == self.requests
        assert seconds == self.seconds
        assert interval == self.send_interval
        self.idx = idx
        return idx

    ###########################################################################
    # Queue callback targets
    ###########################################################################
    def callback0(self) -> None:
        """Queue the callback for request0."""
        self.idx += 1
        self.req_times.append((self.idx, time.time()))

    def callback1(self, idx: int) -> None:
        """Queue the callback for request0.

        Args:
            idx: index of the request call
        """
        self.req_times.append((idx, time.time()))
        assert idx == self.idx + 1
        self.idx = idx

    def callback2(self, idx: int, requests: int) -> None:
        """Queue the callback for request0.

        Args:
            idx: index of the request call
            requests: number of requests for the se_lock
        """
        self.req_times.append((idx, time.time()))
        assert idx == self.idx + 1
        assert requests == self.requests
        self.idx = idx

    def callback3(self, *, idx: int):
        """Queue the callback for request0.

        Args:
            idx: index of the request call
        """
        self.req_times.append((idx, time.time()))
        assert idx == self.idx + 1
        self.idx = idx

    def callback4(self, *, idx: int, seconds: int) -> None:
        """Queue the callback for request0.

        Args:
            idx: index of the request call
            seconds: number of seconds for the se_lock
        """
        self.req_times.append((idx, time.time()))
        assert idx == self.idx + 1
        assert seconds == self.seconds
        self.idx = idx

    def callback5(self,
            idx: int,
            *,
            interval: float) -> None:
        """Queue the callback for request0.

        Args:
            idx: index of the request call
            interval: interval between requests
        """
        self.req_times.append((idx, time.time()))
        assert idx == self.idx + 1
        assert interval == self.send_interval
        self.idx = idx

    def callback6(self,
            idx: int,
            requests: int,
            *,
            seconds: int,
            interval: float) -> None:
        """Queue the callback for request0.

        Args:
            idx: index of the request call
            requests: number of requests for the se_lock
            seconds: number of seconds for the se_lock
            interval: interval between requests
        """
        self.req_times.append((idx, time.time()))
        assert idx == self.idx + 1
        assert requests == self.requests
        assert seconds == self.seconds
        assert interval == self.send_interval
        self.idx = idx


###############################################################################
# TestSELockDocstrings class
###############################################################################
class TestSELockDocstrings:
    """Class TestSELockDocstrings."""

    def test_se_lock_with_example_1(self) -> None:
        """Method test_se_lock_with_example_1."""
        flowers('Example of SELock for README:')

        from scottbrian_utils.se_lock import SELock, SELockShare, SELockExcl
        a = 0
        a_lock = SELock()

        # Get lock in shared mode
        with SELockShare(a_lock):  # read a
            print(a)

        # Get lock in exclusive mode
        with SELockExcl(a_lock):  # write to a
            a = 1
            print(a)
