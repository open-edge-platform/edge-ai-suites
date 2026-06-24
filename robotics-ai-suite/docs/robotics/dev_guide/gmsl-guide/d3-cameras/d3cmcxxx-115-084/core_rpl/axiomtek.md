# Axiomtek ROBOX500 with D3CMCXXX-115-084

> **Note:** Axiomtek ROBOX500 supports either 4x or 8x GMSL camera interfaces.

## i2cdetect usage

Use i2cdetect from i2c-tools to verify I2C bus to GMSL2 deserializer and serializer ACPI device mapping.

```bash
i2cdetect -y <i2c_bus_number>
```

To perform a bounded scan:

```bash
i2cdetect -r -y <i2c_bus_number> 0x20 0x6f
```

Below is the ACPI device configuration table for D3CMCXXX-115-084 on Axiomtek ROBOX500.

## 4x D3CMCXXX-115-084 configuration

_Aggregated-link `SerDes` CSI-2 port 0 and 4 and I2C settings for GMSL Add-in-Card (AIC)_

| UEFI Custom Sensor  | Camera 1           | Camera 2           | Camera 3           | Camera 4           |
| ------------------- | ------------------ | ------------------ | ------------------ | ------------------ |
| Camera suffix       | a                  | b                  | c                  | d                  |
| Custom HID          | `D3000004`         | `D3000004`         | `D3000004`         | `D3000004`         |
| PPR Value           | 2                  | 2                  | 2                  | 2                  |
| PPR Unit            | 1                  | 1                  | 1                  | 1                  |
| Camera module label | `D3CMCXXX-115-084` | `D3CMCXXX-115-084` | `D3CMCXXX-115-084` | `D3CMCXXX-115-084` |
| MIPI Port (Index)   | 0                  | 1                  | 2                  | 3                  |
| LaneUsed            | x2                 | x2                 | x2                 | x2                 |
| Number of I2C       | 3                  | 3                  | 3                  | 3                  |
| I2C Channel         | I2C5               | I2C5               | I2C5               | I2C5               |
| Device0 I2C Address | 48                 | 4a                 | 68                 | 6c                 |
| Device1 I2C Address | 42                 | 44                 | 62                 | 64                 |
| Device2 I2C Address | 12                 | 14                 | 16                 | 18                 |
