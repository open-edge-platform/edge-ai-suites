# SEAVO HB03 with RealSense D457

> **Note:** SEAVO HB03 supports up to 4x GMSL2 camera interfaces.

## i2cdetect usage

Use i2cdetect from i2c-tools to verify I2C bus to GMSL2 deserializer and serializer ACPI device mapping.

```bash
i2cdetect -y <i2c_bus_number>
```

Here, <i2c_bus_number> is the Linux I2C bus number assigned to the GMSL2 devices.

To perform a bounded scan (same pattern used in the GMSL AIC overview):

```bash
i2cdetect -r -y <i2c_bus_number> 0x20 0x6f
```

For this SEAVO 4x D457 layout, run the scan for each configured channel mapping and confirm expected addresses appear on each bus.

Below are the ACPI device configuration tables for RealSense D457 used with the SEAVO Embedded Computer HB03 Add-in-Card.

## 4x D457 configuration

_Aggregated-link `SerDes` CSI-2 port 0 and 4 and I2C settings for GMSL Add-in-Card (AIC)_

| UEFI Custom Sensor  | Camera 1   | Camera 2   | Camera 3   | Camera 4   |
| ------------------- | ---------- | ---------- | ---------- | ---------- |
| GMSL Camera suffix  | a          | g          | e          | k          |
| Custom HID          | `INTC10CD` | `INTC10CD` | `INTC10CD` | `INTC10CD` |
| PPR Value           | 2          | 2          | 2          | 2          |
| PPR Unit            | 1          | 1          | 1          | 1          |
| Camera module label | `d4xx`     | `d4xx`     | `d4xx`     | `d4xx`     |
| MIPI Port (Index)   | 0          | 0          | 4          | 4          |
| LaneUsed            | x4         | x4         | x4         | x4         |
| Number of I2C       | 3          | 3          | 3          | 3          |
| I2C Channel         | I2C1       | I2C1       | I2C0       | I2C0       |
| Device0 I2C Address | 12         | 14         | 12         | 14         |
| Device1 I2C Address | 42         | 44         | 42         | 44         |
| Device2 I2C Address | 48         | 48         | 48         | 48         |

> **Note:** GMSL2 aggregated-link `SerDes` CSI-2 ports 0 and 4 are intentionally set to `LaneUsed = x4` to improve Intel IPU6 DPHY signal-integrity behavior on SEAVO HB03.
