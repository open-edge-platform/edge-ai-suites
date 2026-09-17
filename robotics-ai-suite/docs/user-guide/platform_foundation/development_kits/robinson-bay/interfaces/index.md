# Interfaces

The AAEON CEXD-INTRBL Development Kit provides physical interfaces for connecting cameras, sensors, and low-level robotics hardware.


Connecting a sensor or a control device usually requires configuring two sides:
1. **The development kit side** (covered here) — physical wiring to the chassis and enabling the ports in the BIOS or kernel.
2. **The sensor side** (covered in the [Sensors](../../../../components/sensors/index.md) section) — device-specific settings like I2C addresses, drivers, and software pipelines.

Select the interface you are using to configure the **development kit side**:

## Sensing Interfaces
*   **[GMSL](./gmsl.md)** — Use the FAKRA ports for long-reach cameras with SerDes modules. The kit features built-in deserializers.

## Control
*   **[CAN Bus](./can.md)** — Pinout for the isolated CAN FD channels.
*   **[GPIO](./gpio.md)** — 40-pin header exposing I2C, SPI, PWM, UART, and general purpose I/O.

<!--hide_directive
:::{toctree}
:caption: Components
:hidden:

GMSL <gmsl>
CAN Bus <can>
GPIO <gpio>
:::
hide_directive-->