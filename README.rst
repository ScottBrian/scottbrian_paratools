====================
scottbrian-paratools
====================

Intro
=====

This collection provides tools to assist with parallel processing.

1. You can use SmartEvent to coordinate activities among threads.
2. You can use ThreadComm to send messages between threads.
3. You can use SeLock for shared and exclusive locking among threads.
4. You can use SmartThread to help with uncaptured exceptions in threads.

You can use the SmartEvent class to coordinate activities between two
threads by using either of two schemes:

    1) ``wait()`` and ``resume()`` requests
    2) ``sync()`` requests.

With ``wait()``/``resume()``, one thread typically gives another
thread a task to do and then does a ``wait()``. When the other
thread completes the task, it does a ``resume()`` to unblock the ``wait()``.
It does not matter which role each thread has at any point as long as a
``wait()`` by one thread is matched with a ``resume()`` by the other. Also,
a ``resume()`` can preceed a ``wait()``, known as a **pre-resume**,
which will simply allow the ``wait()`` to proceed imediately without blocking.

The SmartEvent ``sync()`` request is used to ensure that two threads have
each reached a processing sync-point. The first thread to do a
``sync()`` request is blocked until the second thread does a matching
``sync()``, at which point both threads are allowed to proceed.

:Example: create a SmartEvent for mainline and a thread to use

>>> from scottbrian_utils.smart_event import SmartEvent
>>> import threading
>>> import time
>>> def f1(s_event: SmartEvent) -> None:
...     print('f1 beta entered - will do some work')
...     time.sleep(3)  # simulate an i/o task being done
...     print('f1 beta done - about to resume alpha')
...     s_event.resume()
>>> smart_event = SmartEvent(alpha=threading.current_thread())
>>> f1_thread = threading.Thread(target=f1, args=(smart_event,)
>>> smart_event.register_thread(beta=f1_thread)
>>> print('alpha about to start the beta thread')
>>> f1_thread.smart_start()  # give beta a task to do
>>> smart_event.pause_until(WUCond.ThreadsReady)  # ensure thread is alive
>>> time.sleep(2)  # simulate doing some work
>>> print('alpha about to wait for beta to complete')
>>> smart_event.wait()  # wait for beta to complete its task
>>> print('alpha back from wait')
alpha about to start the beta thread
f1 beta entered - will do some work
alpha about to wait for beta to complete
f1 beta done - about to resume alpha
alpha back from wait


You can use the ThreadComm class to set up a two way communication link
between two threads. This allows one thread to send and receive messages
with another thread. The messages can be anything, such as strings, numbers,
lists, or any other type of object. Yu can send messages via the smart_send
method and receive messages via the recv_msg method. You can also send a
message and wait for a reply with the send_rcv_msg.

>>> from scottbrian_utils.smart_event import SmartEvent
>>> import threading
>>> import time
>>> def f1(s_event: SmartEvent) -> None:
...     print('f1 beta entered - will do some work')
...     time.sleep(3)  # simulate an i/o task being done
...     print('f1 beta done - about to resume alpha')
...     s_event.resume()
>>> smart_event = SmartEvent(alpha=threading.current_thread())
>>> f1_thread = threading.Thread(target=f1, args=(smart_event,)
>>> smart_event.register_thread(beta=f1_thread)
>>> print('alpha about to start the beta thread')
>>> f1_thread.smart_start()  # give beta a task to do
>>> smart_event.pause_until(WUCond.ThreadsReady)  # ensure thread is alive
>>> time.sleep(2)  # simulate doing some work
>>> print('alpha about to wait for beta to complete')
>>> smart_event.wait()  # wait for beta to complete its task
>>> print('alpha back from wait')
alpha about to start the beta thread
f1 beta entered - will do some work
alpha about to wait for beta to complete
f1 beta done - about to resume alpha
alpha back from wait


You can use the ThreadComm class to set up a two way communication link
between two threads. This allows one thread to send and receive messages
with another thread. The messages can be anything, such as strings, numbers,
lists, or any other type of object. Yu can send messages via the smart_send
method and receive messages via the recv_msg method. You can also send a
message and wait for a reply with the send_rcv_msg.

>>> from scottbrian_utils.smart_event import SmartEvent
>>> import threading
>>> import time
>>> def f1(s_event: SmartEvent) -> None:
...     print('f1 beta entered - will do some work')
...     time.sleep(3)  # simulate an i/o task being done
...     print('f1 beta done - about to resume alpha')
...     s_event.resume()
>>> smart_event = SmartEvent(alpha=threading.current_thread())
>>> f1_thread = threading.Thread(target=f1, args=(smart_event,)
>>> smart_event.register_thread(beta=f1_thread)
>>> print('alpha about to start the beta thread')
>>> f1_thread.start()  # give beta a task to do
>>> smart_event.pause_until(WUCond.ThreadsReady)  # ensure thread is alive
>>> time.sleep(2)  # simulate doing some work
>>> print('alpha about to wait for beta to complete')
>>> smart_event.wait()  # wait for beta to complete its task
>>> print('alpha back from wait')
alpha about to start the beta thread
f1 beta entered - will do some work
alpha about to wait for beta to complete
f1 beta done - about to resume alpha
alpha back from wait


You can use the ThreadComm class to set up a two way communication link
between two threads. This allows one thread to send and receive messages
with another thread. The messages can be anything, such as strings, numbers,
lists, or any other type of object. Yu can send messages via the smart_send
method and receive messages via the recv_msg method. You can also send a
message and wait for a reply with the send_rcv_msg.

:Example: use ThreadComm to pass a value to a thread and get a response

>>> from scottbrian_utils.thread_comm import ThreadComm
>>> import threading
>>> import time
>>> thread_comm = ThreadComm()
>>> def f1(in_thread_comm):
...     time.sleep(3)
...     while True:
...         msg = in_thread_comm.recv_msg()
...         if msg == 42:
...             print(f'f1 received message {msg}')
...             in_thread_comm.smart_send(17)
...         elif msg == 'exit':
...             print(f'received message {msg}')
...             break
>>> f1_thread = threading.Thread(target=f1, args=(thread_comm,)
>>> f1_thread.smart_start()
>>> print(f'mainline about to send {42}')
mainline about to send 42

>>> msg = thread_comm.send_recv(42)
f1 received message 42

>>> print(f'mainline sent {42} and received {msg}')
mainline sent 42 and received 17

>>> time.sleep(3)
>>> thread_comm.send('exit')
received message exit


The SELock is a shared/exclusive lock that you can use to safely read
and write shared resources in a multi-threaded application.

>>> from scottbrian_utils.thread_comm import ThreadComm
>>> import threading
>>> import time
>>> thread_comm = ThreadComm()
>>> def f1(in_thread_comm):
...     time.sleep(3)
...     while True:
...         msg = in_thread_comm.recv_msg()
...         if msg == 42:
...             print(f'f1 received message {msg}')
...             in_thread_comm.send_msg(17)
...         elif msg == 'exit':
...             print(f'received message {msg}')
...             break
>>> f1_thread = threading.Thread(target=f1, args=(thread_comm,)
>>> f1_thread.smart_start()
>>> print(f'mainline about to send {42}')
mainline about to send 42

>>> msg = thread_comm.send_recv(42)
f1 received message 42

>>> print(f'mainline sent {42} and received {msg}')
mainline sent 42 and received 17

>>> time.sleep(3)
>>> thread_comm.send('exit')
received message exit


The SELock is a shared/exclusive lock that you can use to safely read
and write shared resources in a multi-threaded application.

>>> from scottbrian_utils.thread_comm import ThreadComm
>>> import threading
>>> import time
>>> thread_comm = ThreadComm()
>>> def f1(in_thread_comm):
...     time.sleep(3)
...     while True:
...         msg = in_thread_comm.recv_msg()
...         if msg == 42:
...             print(f'f1 received message {msg}')
...             in_thread_comm.send_msg(17)
...         elif msg == 'exit':
...             print(f'received message {msg}')
...             break
>>> f1_thread = threading.Thread(target=f1, args=(thread_comm,)
>>> f1_thread.start()
>>> print(f'mainline about to send {42}')
mainline about to send 42

>>> msg = thread_comm.send_recv(42)
f1 received message 42

>>> print(f'mainline sent {42} and received {msg}')
mainline sent 42 and received 17

>>> time.sleep(3)
>>> thread_comm.send('exit')
received message exit


The SELock is a shared/exclusive lock that you can use to safely read
and write shared resources in a multi-threaded application.

>>> from scottbrian_utils.thread_comm import ThreadComm
>>> import threading
>>> import time
>>> thread_comm = ThreadComm()
>>> def f1(in_thread_comm):
...     time.sleep(3)
...     while True:
...         msg = in_thread_comm.recv_msg()
...         if msg == 42:
...             print(f'f1 received message {msg}')
...             in_thread_comm.smart_send(17)
...         elif msg == 'exit':
...             print(f'received message {msg}')
...             break
>>> f1_thread = threading.Thread(target=f1, args=(thread_comm,)
>>> f1_thread.smart_start()
>>> print(f'mainline about to send {42}')
mainline about to send 42

>>> msg = thread_comm.send_recv(42)
f1 received message 42

>>> print(f'mainline sent {42} and received {msg}')
mainline sent 42 and received 17

>>> time.sleep(3)
>>> thread_comm.send('exit')
received message exit


The SELock is a shared/exclusive lock that you can use to safely read
and write shared resources in a multi-threaded application.

>>> from scottbrian_utils.thread_comm import ThreadComm
>>> import threading
>>> import time
>>> thread_comm = ThreadComm()
>>> def f1(in_thread_comm):
...     time.sleep(3)
...     while True:
...         msg = in_thread_comm.recv_msg()
...         if msg == 42:
...             print(f'f1 received message {msg}')
...             in_thread_comm.send_msg(17)
...         elif msg == 'exit':
...             print(f'received message {msg}')
...             break
>>> f1_thread = threading.Thread(target=f1, args=(thread_comm,)
>>> f1_thread.smart_start()
>>> print(f'mainline about to send {42}')
mainline about to send 42

>>> msg = thread_comm.send_recv(42)
f1 received message 42

>>> print(f'mainline sent {42} and received {msg}')
mainline sent 42 and received 17

>>> time.sleep(3)
>>> thread_comm.send('exit')
received message exit


The SELock is a shared/exclusive lock that you can use to safely read
and write shared resources in a multi-threaded application.

>>> from scottbrian_utils.thread_comm import ThreadComm
>>> import threading
>>> import time
>>> thread_comm = ThreadComm()
>>> def f1(in_thread_comm):
...     time.sleep(3)
...     while True:
...         msg = in_thread_comm.recv_msg()
...         if msg == 42:
...             print(f'f1 received message {msg}')
...             in_thread_comm.send_msg(17)
...         elif msg == 'exit':
...             print(f'received message {msg}')
...             break
>>> f1_thread = threading.Thread(target=f1, args=(thread_comm,)
>>> f1_thread.start()
>>> print(f'mainline about to send {42}')
mainline about to send 42

>>> msg = thread_comm.send_recv(42)
f1 received message 42

>>> print(f'mainline sent {42} and received {msg}')
mainline sent 42 and received 17

>>> time.sleep(3)
>>> thread_comm.send('exit')
received message exit


The SELock is a shared/exclusive lock that you can use to safely read
and write shared resources in a multi-threaded application.

>>> from scottbrian_utils.thread_comm import ThreadComm
>>> import threading
>>> import time
>>> thread_comm = ThreadComm()
>>> def f1(in_thread_comm):
...     time.sleep(3)
...     while True:
...         msg = in_thread_comm.recv_msg()
...         if msg == 42:
...             print(f'f1 received message {msg}')
...             in_thread_comm.send_msg(17)
...         elif msg == 'exit':
...             print(f'received message {msg}')
...             break
>>> f1_thread = threading.Thread(target=f1, args=(thread_comm,)
>>> f1_thread.smart_start()
>>> print(f'mainline about to send {42}')
mainline about to send 42

>>> msg = thread_comm.send_recv(42)
f1 received message 42

>>> print(f'mainline sent {42} and received {msg}')
mainline sent 42 and received 17

>>> time.sleep(3)
>>> thread_comm.send('exit')
received message exit


The SELock is a shared/exclusive lock that you can use to safely read
and write shared resources in a multi-threaded application.

>>> from scottbrian_utils.thread_comm import ThreadComm
>>> import threading
>>> import time
>>> thread_comm = ThreadComm()
>>> def f1(in_thread_comm):
...     time.sleep(3)
...     while True:
...         msg = in_thread_comm.recv_msg()
...         if msg == 42:
...             print(f'f1 received message {msg}')
...             in_thread_comm.smart_send(17)
...         elif msg == 'exit':
...             print(f'received message {msg}')
...             break
>>> f1_thread = threading.Thread(target=f1, args=(thread_comm,)
>>> f1_thread.smart_start()
>>> print(f'mainline about to send {42}')
mainline about to send 42

>>> msg = thread_comm.send_recv(42)
f1 received message 42

>>> print(f'mainline sent {42} and received {msg}')
mainline sent 42 and received 17

>>> time.sleep(3)
>>> thread_comm.send('exit')
received message exit


The SELock is a shared/exclusive lock that you can use to safely read
and write shared resources in a multi-threaded application.

>>> from scottbrian_utils.thread_comm import ThreadComm
>>> import threading
>>> import time
>>> thread_comm = ThreadComm()
>>> def f1(in_thread_comm):
...     time.sleep(3)
...     while True:
...         msg = in_thread_comm.recv_msg()
...         if msg == 42:
...             print(f'f1 received message {msg}')
...             in_thread_comm.send_msg(17)
...         elif msg == 'exit':
...             print(f'received message {msg}')
...             break
>>> f1_thread = threading.Thread(target=f1, args=(thread_comm,)
>>> f1_thread.start()
>>> print(f'mainline about to send {42}')
mainline about to send 42

>>> msg = thread_comm.send_recv(42)
f1 received message 42

>>> print(f'mainline sent {42} and received {msg}')
mainline sent 42 and received 17

>>> time.sleep(3)
>>> thread_comm.send('exit')
received message exit


The SELock is a shared/exclusive lock that you can use to safely read
and write shared resources in a multi-threaded application.

>>> from scottbrian_utils.thread_comm import ThreadComm
>>> import threading
>>> import time
>>> thread_comm = ThreadComm()
>>> def f1(in_thread_comm):
...     time.sleep(3)
...     while True:
...         msg = in_thread_comm.recv_msg()
...         if msg == 42:
...             print(f'f1 received message {msg}')
...             in_thread_comm.send_msg(17)
...         elif msg == 'exit':
...             print(f'received message {msg}')
...             break
>>> f1_thread = threading.Thread(target=f1, args=(thread_comm,)
>>> f1_thread.smart_start()
>>> print(f'mainline about to send {42}')
mainline about to send 42

>>> msg = thread_comm.send_recv(42)
f1 received message 42

>>> print(f'mainline sent {42} and received {msg}')
mainline sent 42 and received 17

>>> time.sleep(3)
>>> thread_comm.send('exit')
received message exit


The SELock is a shared/exclusive lock that you can use to safely read
and write shared resources in a multi-threaded application.

>>> from scottbrian_utils.thread_comm import ThreadComm
>>> import threading
>>> import time
>>> thread_comm = ThreadComm()
>>> def f1(in_thread_comm):
...     time.sleep(3)
...     while True:
...         msg = in_thread_comm.recv_msg()
...         if msg == 42:
...             print(f'f1 received message {msg}')
...             in_thread_comm.smart_send(17)
...         elif msg == 'exit':
...             print(f'received message {msg}')
...             break
>>> f1_thread = threading.Thread(target=f1, args=(thread_comm,)
>>> f1_thread.smart_start()
>>> print(f'mainline about to send {42}')
mainline about to send 42

>>> msg = thread_comm.send_recv(42)
f1 received message 42

>>> print(f'mainline sent {42} and received {msg}')
mainline sent 42 and received 17

>>> time.sleep(3)
>>> thread_comm.send('exit')
received message exit


The SELock is a shared/exclusive lock that you can use to safely read
and write shared resources in a multi-threaded application.

>>> from scottbrian_utils.thread_comm import ThreadComm
>>> import threading
>>> import time
>>> thread_comm = ThreadComm()
>>> def f1(in_thread_comm):
...     time.sleep(3)
...     while True:
...         msg = in_thread_comm.recv_msg()
...         if msg == 42:
...             print(f'f1 received message {msg}')
...             in_thread_comm.send_msg(17)
...         elif msg == 'exit':
...             print(f'received message {msg}')
...             break
>>> f1_thread = threading.Thread(target=f1, args=(thread_comm,)
>>> f1_thread.start()
>>> print(f'mainline about to send {42}')
mainline about to send 42

>>> msg = thread_comm.send_recv(42)
f1 received message 42

>>> print(f'mainline sent {42} and received {msg}')
mainline sent 42 and received 17

>>> time.sleep(3)
>>> thread_comm.send('exit')
received message exit


The SELock is a shared/exclusive lock that you can use to safely read
and write shared resources in a multi-threaded application.

>>> from scottbrian_utils.thread_comm import ThreadComm
>>> import threading
>>> import time
>>> thread_comm = ThreadComm()
>>> def f1(in_thread_comm):
...     time.sleep(3)
...     while True:
...         msg = in_thread_comm.recv_msg()
...         if msg == 42:
...             print(f'f1 received message {msg}')
...             in_thread_comm.send_msg(17)
...         elif msg == 'exit':
...             print(f'received message {msg}')
...             break
>>> f1_thread = threading.Thread(target=f1, args=(thread_comm,)
>>> f1_thread.smart_start()
>>> print(f'mainline about to send {42}')
mainline about to send 42

>>> msg = thread_comm.send_recv(42)
f1 received message 42

>>> print(f'mainline sent {42} and received {msg}')
mainline sent 42 and received 17

>>> time.sleep(3)
>>> thread_comm.send('exit')
received message exit


The SELock is a shared/exclusive lock that you can use to safely read
and write shared resources in a multi-threaded application.

>>> from scottbrian_utils.thread_comm import ThreadComm
>>> import threading
>>> import time
>>> thread_comm = ThreadComm()
>>> def f1(in_thread_comm):
...     time.sleep(3)
...     while True:
...         msg = in_thread_comm.recv_msg()
...         if msg == 42:
...             print(f'f1 received message {msg}')
...             in_thread_comm.send_msg(17)
...         elif msg == 'exit':
...             print(f'received message {msg}')
...             break
>>> f1_thread = threading.Thread(target=f1, args=(thread_comm,)
>>> f1_thread.smart_start()
>>> print(f'mainline about to send {42}')
mainline about to send 42

>>> msg = thread_comm.send_recv(42)
f1 received message 42

>>> print(f'mainline sent {42} and received {msg}')
mainline sent 42 and received 17

>>> time.sleep(3)
>>> thread_comm.send('exit')
received message exit


The SELock is a shared/exclusive lock that you can use to safely read
and write shared resources in a multi-threaded application.

>>> from scottbrian_utils.thread_comm import ThreadComm
>>> import threading
>>> import time
>>> thread_comm = ThreadComm()
>>> def f1(in_thread_comm):
...     time.sleep(3)
...     while True:
...         msg = in_thread_comm.recv_msg()
...         if msg == 42:
...             print(f'f1 received message {msg}')
...             in_thread_comm.smart_send(17)
...         elif msg == 'exit':
...             print(f'received message {msg}')
...             break
>>> f1_thread = threading.Thread(target=f1, args=(thread_comm,)
>>> f1_thread.start()
>>> print(f'mainline about to send {42}')
mainline about to send 42

>>> msg = thread_comm.send_recv(42)
f1 received message 42

>>> print(f'mainline sent {42} and received {msg}')
mainline sent 42 and received 17

>>> time.sleep(3)
>>> thread_comm.send('exit')
received message exit


The SELock is a shared/exclusive lock that you can use to safely read
and write shared resources in a multi-threaded application.

>>> from scottbrian_utils.thread_comm import ThreadComm
>>> import threading
>>> import time
>>> thread_comm = ThreadComm()
>>> def f1(in_thread_comm):
...     time.sleep(3)
...     while True:
...         msg = in_thread_comm.recv_msg()
...         if msg == 42:
...             print(f'f1 received message {msg}')
...             in_thread_comm.send_msg(17)
...         elif msg == 'exit':
...             print(f'received message {msg}')
...             break
>>> f1_thread = threading.Thread(target=f1, args=(thread_comm,)
>>> f1_thread.smart_start()
>>> print(f'mainline about to send {42}')
mainline about to send 42

>>> msg = thread_comm.send_recv(42)
f1 received message 42

>>> print(f'mainline sent {42} and received {msg}')
mainline sent 42 and received 17

>>> time.sleep(3)
>>> thread_comm.send('exit')
received message exit


The SELock is a shared/exclusive lock that you can use to safely read
and write shared resources in a multi-threaded application.

>>> from scottbrian_utils.thread_comm import ThreadComm
>>> import threading
>>> import time
>>> thread_comm = ThreadComm()
>>> def f1(in_thread_comm):
...     time.sleep(3)
...     while True:
...         msg = in_thread_comm.recv_msg()
...         if msg == 42:
...             print(f'f1 received message {msg}')
...             in_thread_comm.send_msg(17)
...         elif msg == 'exit':
...             print(f'received message {msg}')
...             break
>>> f1_thread = threading.Thread(target=f1, args=(thread_comm,)
>>> f1_thread.smart_start()
>>> print(f'mainline about to send {42}')
mainline about to send 42

>>> msg = thread_comm.send_recv(42)
f1 received message 42

>>> print(f'mainline sent {42} and received {msg}')
mainline sent 42 and received 17

>>> time.sleep(3)
>>> thread_comm.send('exit')
received message exit


The SELock is a shared/exclusive lock that you can use to safely read
and write shared resources in a multi-threaded application.

>>> from scottbrian_utils.thread_comm import ThreadComm
>>> import threading
>>> import time
>>> thread_comm = ThreadComm()
>>> def f1(in_thread_comm):
...     time.sleep(3)
...     while True:
...         msg = in_thread_comm.recv_msg()
...         if msg == 42:
...             print(f'f1 received message {msg}')
...             in_thread_comm.smart_send(17)
...         elif msg == 'exit':
...             print(f'received message {msg}')
...             break
>>> f1_thread = threading.Thread(target=f1, args=(thread_comm,)
>>> f1_thread.start()
>>> print(f'mainline about to send {42}')
mainline about to send 42

>>> msg = thread_comm.send_recv(42)
f1 received message 42

>>> print(f'mainline sent {42} and received {msg}')
mainline sent 42 and received 17

>>> time.sleep(3)
>>> thread_comm.send('exit')
received message exit


The SELock is a shared/exclusive lock that you can use to safely read
and write shared resources in a multi-threaded application.

>>> from scottbrian_utils.thread_comm import ThreadComm
>>> import threading
>>> import time
>>> thread_comm = ThreadComm()
>>> def f1(in_thread_comm):
...     time.sleep(3)
...     while True:
...         msg = in_thread_comm.recv_msg()
...         if msg == 42:
...             print(f'f1 received message {msg}')
...             in_thread_comm.send_msg(17)
...         elif msg == 'exit':
...             print(f'received message {msg}')
...             break
>>> f1_thread = threading.Thread(target=f1, args=(thread_comm,)
>>> f1_thread.smart_start()
>>> print(f'mainline about to send {42}')
mainline about to send 42

>>> msg = thread_comm.send_recv(42)
f1 received message 42

>>> print(f'mainline sent {42} and received {msg}')
mainline sent 42 and received 17

>>> time.sleep(3)
>>> thread_comm.send('exit')
received message exit


The SELock is a shared/exclusive lock that you can use to safely read
and write shared resources in a multi-threaded application.

>>> from scottbrian_utils.thread_comm import ThreadComm
>>> import threading
>>> import time
>>> thread_comm = ThreadComm()
>>> def f1(in_thread_comm):
...     time.sleep(3)
...     while True:
...         msg = in_thread_comm.recv_msg()
...         if msg == 42:
...             print(f'f1 received message {msg}')
...             in_thread_comm.send_msg(17)
...         elif msg == 'exit':
...             print(f'received message {msg}')
...             break
>>> f1_thread = threading.Thread(target=f1, args=(thread_comm,)
>>> f1_thread.smart_start()
>>> print(f'mainline about to send {42}')
mainline about to send 42

>>> msg = thread_comm.send_recv(42)
f1 received message 42

>>> print(f'mainline sent {42} and received {msg}')
mainline sent 42 and received 17

>>> time.sleep(3)
>>> thread_comm.send('exit')
received message exit


The SELock is a shared/exclusive lock that you can use to safely read
and write shared resources in a multi-threaded application.

>>> from scottbrian_utils.thread_comm import ThreadComm
>>> import threading
>>> import time
>>> thread_comm = ThreadComm()
>>> def f1(in_thread_comm):
...     time.sleep(3)
...     while True:
...         msg = in_thread_comm.recv_msg()
...         if msg == 42:
...             print(f'f1 received message {msg}')
...             in_thread_comm.send_msg(17)
...         elif msg == 'exit':
...             print(f'received message {msg}')
...             break
>>> f1_thread = threading.Thread(target=f1, args=(thread_comm,)
>>> f1_thread.start()
>>> print(f'mainline about to send {42}')
mainline about to send 42

>>> msg = thread_comm.send_recv(42)
f1 received message 42

>>> print(f'mainline sent {42} and received {msg}')
mainline sent 42 and received 17

>>> time.sleep(3)
>>> thread_comm.send('exit')
received message exit


The SELock is a shared/exclusive lock that you can use to safely read
and write shared resources in a multi-threaded application.

:Example: use SELock to coordinate access to a shared resource



>>> from scottbrian_utils.se_lock import SELock
>>> a = 0
>>> a_lock = SELock()
>>> # Get lock in shared mode
>>> with a_lock(SELock.SHARE):  # read a
>>>     print(a)

>>> # Get lock in exclusive mode
>>> with a_lock(SELock.EXCL):  # write to a
>>>     a = 1
>>>     print(a)



.. image:: https://img.shields.io/badge/security-bandit-yellow.svg
    :target: https://github.com/PyCQA/bandit
    :alt: Security Status

.. image:: https://readthedocs.org/projects/pip/badge/?version=stable
    :target: https://pip.pypa.io/en/stable/?badge=stable
    :alt: Documentation Status


Installation
============

Linux:

``pip install scottbrian-paratools``


Development setup
=================

See tox.ini

Release History
===============

* 1.0.0
    * Initial release


Meta
====

Scott Tuttle

Distributed under the MIT license. See ``LICENSE`` for more information.


Contributing
============

1. Fork it (<https://github.com/yourname/yourproject/fork>)
2. Create your feature branch (`git checkout -b feature/fooBar`)
3. Commit your changes (`git commit -am 'Add some fooBar'`)
4. Push to the branch (`git push origin feature/fooBar`)
5. Create a new Pull Request


