# Axiomtek ROBOX500 with RealSense D457

> **Note:** Axiomtek ROBOX500 supports either 4x or 8x GMSL camera interfaces.

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

For Axiomtek D457 layouts, run the scan for each configured channel mapping and confirm expected addresses appear on each bus.

Below are the ACPI device configuration tables for RealSense D457 used with Axiomtek ROBOX500.

## 4x D457 configuration

_Standalone-link `SerDes` CSI-2 port 0, 1, 2 and 3 and I2C settings for GMSL Add-in-Card (AIC)_

| UEFI Custom Sensor  | Camera 1   | Camera 2   | Camera 3   | Camera 4   |
| ------------------- | ---------- | ---------- | ---------- | ---------- |
| Camera suffix       | a          | b          | c          | d          |
| Custom HID          | `INTC10CD` | `INTC10CD` | `INTC10CD` | `INTC10CD` |
| PPR Value           | 2          | 2          | 2          | 2          |
| PPR Unit            | 1          | 1          | 1          | 1          |
| Camera module label | `d4xx`     | `d4xx`     | `d4xx`     | `d4xx`     |
| MIPI Port (Index)   | 0          | 1          | 2          | 3          |
| LaneUsed            | x2         | x2         | x2         | x2         |
| Number of I2C       | 3          | 3          | 3          | 3          |
| I2C Channel         | I2C5       | I2C5       | I2C5       | I2C5       |
| Device0 I2C Address | 12         | 14         | 16         | 18         |
| Device1 I2C Address | 42         | 44         | 62         | 64         |
| Device2 I2C Address | 48         | 4a         | 68         | 6c         |

## 8x D457 configuration

_Aggregated-link `SerDes` CSI-2 port 0, 1, 2 and 3 and I2C settings for GMSL Add-in-Card (AIC)_

| UEFI Custom Sensor     | Camera 1   | Camera 2   | Camera 3   | Camera 4   | N/A        | N/A        | N/A        | N/A        |
| ---------------------- | ---------- | ---------- | ---------- | ---------- | ---------- | ---------- | ---------- | ---------- |
| Camera suffix (letter) | a          | b          | c          | d          | _g_        | _h_        | _i_        | _j_        |
| Custom HID             | `INTC10CD` | `INTC10CD` | `INTC10CD` | `INTC10CD` | `INTC10CD` | `INTC10CD` | `INTC10CD` | `INTC10CD` |
| PPR Value              | 2          | 2          | 2          | 2          | 2          | 2          | 2          | 2          |
| PPR Unit               | 1          | 1          | 1          | 1          | 1          | 1          | 1          | 1          |
| Camera module label    | `d4xx`     | `d4xx`     | `d4xx`     | `d4xx`     | `d4xx`     | `d4xx`     | `d4xx`     | `d4xx`     |
| MIPI Port (Index)      | 0          | 1          | 2          | 3          | 0          | 1          | 2          | 3          |
| LaneUsed               | x2         | x2         | x2         | x2         | x2         | x2         | x2         | x2         |
| Number of I2C          | 3          | 3          | 3          | 3          | 3          | 3          | 3          | 3          |
| I2C Channel            | I2C5       | I2C5       | I2C5       | I2C5       | _I2C5_     | _I2C5_     | _I2C5_     | _I2C5_     |
| Device0 I2C Address    | 12         | 14         | 16         | 18         | _13_       | _15_       | _17_       | _19_       |
| Device1 I2C Address    | 42         | 44         | 62         | 64         | _43_       | _45_       | _63_       | _65_       |
| Device2 I2C Address    | 48         | 4a         | 68         | 6c         | _48_       | _4a_       | _68_       | _6c_       |
