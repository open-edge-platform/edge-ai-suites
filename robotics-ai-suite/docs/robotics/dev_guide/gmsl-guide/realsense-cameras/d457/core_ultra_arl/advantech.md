# Advantech AFE-R360 and ASR-A502 with RealSense D457

> **Note:** Advantech AFE-R360 and ASR-A502 series support up to 6x GMSL cameras.

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

For Advantech D457 layouts, run the scan for each configured channel mapping and confirm expected addresses appear on each bus.

Below are the ACPI device configuration tables for RealSense D457 used with the Advantech GMSL Input Module Card on AFE-R360 and ASR-A502 series.

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
| LaneUsed            | x2         | x2         | x2         | x2         |
| Number of I2C       | 3          | 3          | 3          | 3          |
| I2C Channel         | I2C1       | I2C1       | I2C2       | I2C2       |
| Device0 I2C Address | 12         | 14         | 12         | 14         |
| Device1 I2C Address | 42         | 44         | 42         | 44         |
| Device2 I2C Address | 48         | 48         | 48         | 48         |

## 6x D457 configuration

_Aggregated-link `SerDes` CSI-2 port 0, 4 and 5 and I2C settings for GMSL Add-in-Card (AIC)_

| UEFI Custom Sensor  | Camera 1   | Camera 2   | Camera 3   | Camera 4   | Camera 5 or N/A | Camera 6 or N/A |
| ------------------- | ---------- | ---------- | ---------- | ---------- | --------------- | --------------- |
| GMSL Camera suffix  | a          | g          | e          | f          | _k_             | _l_             |
| Custom HID          | `INTC10CD` | `INTC10CD` | `INTC10CD` | `INTC10CD` | `INTC10CD`      | `INTC10CD`      |
| PPR Value           | 2          | 2          | 2          | 2          | 2               | 2               |
| PPR Unit            | 1          | 1          | 1          | 1          | 1               | 1               |
| Camera module label | `d4xx`     | `d4xx`     | `d4xx`     | `d4xx`     | `d4xx`          | `d4xx`          |
| MIPI Port (Index)   | 0          | 0          | 4          | 5          | _4_             | _5_             |
| LaneUsed            | x2         | x2         | x2         | x2         | x2              | x2              |
| Number of I2C       | 3          | 3          | 3          | 3          | 3               | 3               |
| I2C Channel         | I2C1       | I2C1       | I2C2       | I2C2       | _I2C2_          | _I2C2_          |
| Device0 I2C Address | 12         | 14         | 16         | 18         | _12_            | _14_            |
| Device1 I2C Address | 42         | 44         | 62         | 42         | _64_            | _44_            |
| Device2 I2C Address | 48         | 48         | 48         | 4a         | _48_            | _4a_            |
