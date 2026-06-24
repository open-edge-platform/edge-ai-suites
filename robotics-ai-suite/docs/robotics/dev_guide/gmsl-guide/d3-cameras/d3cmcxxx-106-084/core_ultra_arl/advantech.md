# Advantech AFE-R360 and ASR-A502 with D3CMCXXX-106-084

> **Note:** Advantech AFE-R360 and ASR-A502 series support up to 6x GMSL cameras.

## i2cdetect usage

Use i2cdetect from i2c-tools to verify I2C bus to GMSL2 deserializer and serializer ACPI device mapping.

```bash
i2cdetect -y <i2c_bus_number>
```

To perform a bounded scan:

```bash
i2cdetect -r -y <i2c_bus_number> 0x20 0x6f
```

Below is the ACPI device configuration table for D3CMCXXX-106-084 on Advantech.

## 2x D3CMCXXX-106-084 configuration

_Aggregated-link `SerDes` CSI-2 port 0 and 4 and I2C settings for GMSL Add-in-Card (AIC)_

| UEFI Custom Sensor  | Camera 1           | Camera 2           |
| ------------------- | ------------------ | ------------------ |
| GMSL Camera suffix  | a                  | e                  |
| Custom HID          | `D3000005`         | `D3000005`         |
| PPR Value           | 2                  | 2                  |
| PPR Unit            | 2                  | 2                  |
| Camera module label | `D3CMCXXX-106-084` | `D3CMCXXX-106-084` |
| MIPI Port (Index)   | 0                  | 4                  |
| LaneUsed            | x2                 | x2                 |
| Number of I2C       | 3                  | 3                  |
| I2C Channel         | I2C1               | I2C2               |
| Device0 I2C Address | 48                 | 48                 |
| Device1 I2C Address | 42                 | 44                 |
| Device2 I2C Address | 10                 | 12                 |
