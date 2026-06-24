# Axiomtek ROBOX500 with OTOC1031

> **Note:** Axiomtek ROBOX500 supports either 4x or 8x GMSL camera interfaces.

## i2cdetect usage

Use i2cdetect from i2c-tools to verify I2C bus to GMSL2 deserializer and serializer ACPI device mapping.

```bash
i2cdetect -y <i2c_bus_number>
```

```bash
i2cdetect -r -y <i2c_bus_number> 0x20 0x6f
```

## 4x OTOC1031 configuration

_Aggregated-link `SerDes` CSI-2 port 0 and 4 and I2C settings for GMSL Add-in-Card (AIC)_

| UEFI Custom Sensor  | Camera 1   | Camera 2   | Camera 3   | Camera 4   |
| ------------------- | ---------- | ---------- | ---------- | ---------- |
| GMSL Camera suffix  | a          | b          | c          | d          |
| Custom HID          | `OTOC1031` | `OTOC1031` | `OTOC1031` | `OTOC1031` |
| PPR Value           | 2          | 2          | 2          | 2          |
| PPR Unit            | 1          | 1          | 1          | 1          |
| Camera module label | `otocam`   | `otocam`   | `otocam`   | `otocam`   |
| MIPI Port (Index)   | 0          | 1          | 2          | 3          |
| LaneUsed            | x2         | x2         | x2         | x2         |
| Number of I2C       | 3          | 3          | 3          | 3          |
| I2C Channel         | I2C5       | I2C5       | I2C5       | I2C5       |
| Device0 I2C Address | 10         | 11         | 10         | 11         |
| Device1 I2C Address | 18         | 19         | 18         | 19         |
| Device2 I2C Address | 48         | 4a         | 68         | 6c         |
