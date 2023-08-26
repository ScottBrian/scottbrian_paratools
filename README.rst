====================
scottbrian-paratools
====================

Intro
=====

The SmartThread class makes it easy to create and use threads in a
multi-threaded application. It provides configuration, messaging,
and resume/wait/sync methods, and will also detect various error
conditions, such as when a thread becomes unresponsive because it has
ended.

Example: Create a SmartThread configuration for two threads:

The 'alpha' thread is created in mainline, and the 'beta' thread is a new thread that will get control in the f1
routine. 'beta' will need access to its SmartThread instance, and this is accomplished by passing the instance
f1 via the thread_parm_name argument.

.. code-block:: python

    from scottbrian_paratools.smart_thread import SmartThread
    def f1(smart_thread: SmartThread) -> None:
        print('f1 beta entered')
        beta_smart_thread.smart_send(receivers='alpha',
                                     msg='hi alpha, this is beta')
        beta_smart_thread.smart_wait(resumers='alpha')
        print('f1 beta exiting')
    print('mainline alpha entered')

    alpha_smart_thread = SmartThread(name='alpha')
    beta_smart_thread = SmartThread(name='beta',
                                    target=f1,
                                    auto_start=True,
                                    thread_parm_name='beta_smart_thread')
    msg_from_beta = alpha_smart_thread.smart_recv(senders='beta')
    print(msg_from_beta)

    alpha_smart_thread.smart_resume(waiters='beta')
    alpha_smart_thread.smart_join(targets='beta')
    print('mainline alpha exiting')


Expected output for Example 1:

.. code-block:: python

    mainline alpha entered
    {'beta': ['hi alpha, this is beta']}
    mainline alpha exiting



.. image:: https://img.shields.io/badge/security-bandit-yellow.svg
    :target: https://github.com/PyCQA/bandit
    :alt: Security Status

.. image:: https://readthedocs.org/projects/pip/badge/?version=stable
    :target: https://pip.pypa.io/en/stable/?badge=stable
    :alt: Documentation Status


Installation
============

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