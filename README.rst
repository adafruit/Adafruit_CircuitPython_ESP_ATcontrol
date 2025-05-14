Introduction
============

.. image:: https://readthedocs.org/projects/adafruit-circuitpython-esp-atcontrol/badge/?version=latest
    :target: https://docs.circuitpython.org/projects/esp-atcontrol/en/latest/
    :alt: Documentation Status

.. image:: https://raw.githubusercontent.com/adafruit/Adafruit_CircuitPython_Bundle/main/badges/adafruit_discord.svg
    :target: https://adafru.it/discord
    :alt: Discord

.. image:: https://github.com/adafruit/Adafruit_CircuitPython_ESP_ATcontrol/workflows/Build%20CI/badge.svg
    :target: https://github.com/adafruit/Adafruit_CircuitPython_ESP_ATcontrol/actions/
    :alt: Build Status

.. image:: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json
    :target: https://github.com/astral-sh/ruff
    :alt: Code Style: Ruff

This library is no longer supported! The library is being left available for continued usage, however, Adafruit is no longer supporting it.
===========================================================================================================================================

Use the ESP AT command sent to communicate with the Interwebs. Its slow, but works to get data into CircuitPython

Command set: https://www.espressif.com/sites/default/files/documentation/4a-esp8266_at_instruction_set_en.pdf

Examples: https://www.espressif.com/sites/default/files/documentation/4b-esp8266_at_command_examples_en.pdf


Dependencies
=============
This driver depends on:

* `Adafruit CircuitPython <https://github.com/adafruit/circuitpython>`_
* `Adafruit CircuitPython ConnectionManager <https://github.com/adafruit/Adafruit_CircuitPython_ConnectionManager/>`_
* `Adafruit CircuitPython Requests <https://github.com/adafruit/Adafruit_CircuitPython_Requests/>`_

Please ensure all dependencies are available on the CircuitPython filesystem.
This is easily achieved by downloading
`the Adafruit library and driver bundle <https://github.com/adafruit/Adafruit_CircuitPython_Bundle>`_.

Installing from PyPI
--------------------

On supported GNU/Linux systems like the Raspberry Pi, you can install the driver locally `from
PyPI <https://pypi.org/project/adafruit-circuitpython-esp-atcontrol/>`_. To install for current user:

.. code-block:: shell

    pip3 install adafruit-circuitpython-esp-atcontrol

To install system-wide (this may be required in some cases):

.. code-block:: shell

    sudo pip3 install adafruit-circuitpython-esp-atcontrol

To install in a virtual environment in your current project:

.. code-block:: shell

    mkdir project-name && cd project-name
    python3 -m venv .venv
    source .venv/bin/activate
    pip3 install adafruit-circuitpython-esp-atcontrol

Usage Example
=============

See examples folder for full demos


Documentation
=============

API documentation for this library can be found on `Read the Docs <https://docs.circuitpython.org/projects/esp-atcontrol/en/latest/>`_.

For information on building library documentation, please check out `this guide <https://learn.adafruit.com/creating-and-sharing-a-circuitpython-library/sharing-our-docs-on-readthedocs#sphinx-5-1>`_.

Contributing
============

Contributions are welcome! Please read our `Code of Conduct
<https://github.com/adafruit/Adafruit_CircuitPython_espATcontrol/blob/main/CODE_OF_CONDUCT.md>`_
before contributing to help this project stay welcoming.
